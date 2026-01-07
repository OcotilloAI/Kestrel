"""Manager Agent for high-level task orchestration.

The Manager understands user intent, decomposes complex requests into tasks,
dispatches to the Coder agent, and validates results before presenting to user.
"""

import os
from typing import AsyncGenerator, Dict, Any, List, Optional

from agent_session import AgentSession
from llm_client import LLMClient
from task_types import Task, TaskPlan, TaskResult, TaskStatus, parse_plan_xml, parse_result_xml


MANAGER_SYSTEM_PROMPT = """You are the Manager for a voice-first coding assistant. Your responsibilities:
1. UNDERSTAND: Parse the user's spoken request into clear intent
2. DECOMPOSE: Break complex requests into ordered, atomic tasks
3. DELEGATE: Assign each task to the Coder with clear success criteria
4. VALIDATE: Check results before presenting to user
5. ADAPT: If a task fails, propose recovery before escalating

Output using XML tags:

<plan>
  <intent>Brief summary of user's goal</intent>
  <confidence>0.85</confidence>
  <clarify>Question if needed, otherwise omit this tag</clarify>
  <task id="1">
    <description>What to do</description>
    <criteria>How to verify completion</criteria>
    <depends></depends>
  </task>
  <task id="2">
    <description>Next step</description>
    <criteria>Success criteria</criteria>
    <depends>1</depends>
  </task>
</plan>

Rules:
- Keep tasks atomic and verifiable (each task should have a clear done state)
- Prefer sensible defaults over asking questions
- Limit to 5 tasks maximum; merge related work
- Flag risky operations (delete, overwrite important files) in task criteria
- If unclear, include <clarify> with a single focused question
- Always include at least one task, even for simple requests
"""


class ManagerAgent:
    """High-level orchestrator that manages task decomposition and coder dispatch."""

    def __init__(
        self,
        llm_client: LLMClient,
        coder_agent: Any,  # CoderAgent, imported at runtime to avoid circular import
        max_retries: int = 2,
    ) -> None:
        self.client = llm_client
        self.coder = coder_agent
        self.max_retries = max_retries
        self.model = os.environ.get(
            "LLM_MANAGER_MODEL",
            os.environ.get("LLM_CONTROLLER_MODEL", llm_client.model)
        )

    async def decompose_intent(
        self,
        user_text: str,
        context: Optional[str] = None,
    ) -> TaskPlan:
        """Convert user request into a structured TaskPlan."""
        messages: List[Dict[str, str]] = [
            {"role": "system", "content": MANAGER_SYSTEM_PROMPT},
        ]

        if context:
            messages.append({
                "role": "system",
                "content": f"Context from prior conversation:\n{context}"
            })

        messages.append({"role": "user", "content": user_text})

        response = await self.client.chat(messages, model_override=self.model)

        plan = parse_plan_xml(response)
        if plan is None:
            # Fallback: create a single task from the raw request
            plan = TaskPlan(
                intent=user_text,
                confidence=0.5,
                tasks=[Task(
                    id="1",
                    description=user_text,
                    success_criteria="Task completed without errors",
                )],
            )

        return plan

    async def process_request(
        self,
        session: AgentSession,
        user_text: str,
        context: Optional[str] = None,
    ) -> AsyncGenerator[Dict[str, Any], None]:
        """Main entry point for voice requests.

        1. Decompose intent into tasks
        2. If clarification needed, yield question and return
        3. For each task: dispatch to coder, validate, adapt on failure
        4. Produce final summary
        """
        # Step 1: Decompose intent
        yield {
            "type": "manager",
            "role": "manager",
            "content": "Analyzing request...",
            "source": "manager",
        }

        plan = await self.decompose_intent(user_text, context)

        # Step 2: Check for clarification
        if plan.needs_clarification:
            yield {
                "type": "clarify",
                "role": "manager",
                "content": plan.needs_clarification,
                "source": "manager",
            }
            return

        # Emit the plan
        task_list = "\n".join(
            f"  {t.id}. {t.description}" for t in plan.tasks
        )
        yield {
            "type": "plan",
            "role": "manager",
            "content": f"Plan (confidence: {plan.confidence:.0%}):\n{task_list}",
            "source": "manager",
            "metadata": {
                "intent": plan.intent,
                "confidence": plan.confidence,
                "task_count": len(plan.tasks),
            },
        }

        # Step 3: Execute tasks
        completed_tasks: List[str] = []
        task_results: Dict[str, TaskResult] = {}

        for task in plan.tasks:
            # Check dependencies
            missing_deps = [d for d in task.dependencies if d not in completed_tasks]
            if missing_deps:
                yield {
                    "type": "system",
                    "role": "manager",
                    "content": f"Skipping task {task.id}: waiting for dependencies {missing_deps}",
                    "source": "manager",
                }
                continue

            # Emit task start
            yield {
                "type": "task_start",
                "role": "manager",
                "content": f"Starting task {task.id}: {task.description}",
                "source": "manager",
                "metadata": {"task_id": task.id},
            }

            # Execute task with retries - yields coder events
            result: Optional[TaskResult] = None
            async for event in self._execute_task_with_retry(session, task, plan):
                if "_result" in event:
                    result = event["_result"]
                else:
                    # Forward coder event to websocket
                    yield event

            if result is None:
                result = TaskResult(
                    status=TaskStatus.FAILED,
                    summary="No result returned from task execution",
                    errors=["Internal error"],
                )

            task_results[task.id] = result

            if result.status == TaskStatus.COMPLETED:
                completed_tasks.append(task.id)
                yield {
                    "type": "task_complete",
                    "role": "manager",
                    "content": f"Task {task.id} completed: {result.summary}",
                    "source": "manager",
                    "metadata": {
                        "task_id": task.id,
                        "files_changed": result.files_changed,
                        "tested": result.tested,
                    },
                }
            else:
                yield {
                    "type": "task_failed",
                    "role": "manager",
                    "content": f"Task {task.id} failed: {'; '.join(result.errors) or 'Unknown error'}",
                    "source": "manager",
                    "metadata": {"task_id": task.id, "errors": result.errors},
                }
                # For high autonomy, continue to next task instead of stopping
                # (unless it's a dependency for remaining tasks)

        # Step 4: Generate final summary
        completed_count = len(completed_tasks)
        total_count = len(plan.tasks)
        all_files = []
        for r in task_results.values():
            all_files.extend(r.files_changed)

        if completed_count == total_count:
            summary = f"Completed all {total_count} tasks for: {plan.intent}"
        else:
            summary = f"Completed {completed_count}/{total_count} tasks for: {plan.intent}"

        if all_files:
            summary += f"\nFiles changed: {', '.join(set(all_files))}"

        yield {
            "type": "summary",
            "role": "manager",
            "content": summary,
            "source": "manager",
            "metadata": {
                "completed": completed_count,
                "total": total_count,
                "files_changed": list(set(all_files)),
            },
        }

    async def _execute_task_with_retry(
        self,
        session: AgentSession,
        task: Task,
        plan: TaskPlan,
    ) -> AsyncGenerator[Dict[str, Any], TaskResult]:
        """Execute a task with retry logic on failure.

        Yields coder events, then returns TaskResult via StopIteration.
        """
        last_result: Optional[TaskResult] = None

        for attempt in range(self.max_retries + 1):
            # Build task prompt for coder
            task_prompt = self._build_coder_prompt(task, plan, last_result)

            # Run coder agent
            coder_output_parts: List[str] = []
            async for event in self.coder.run(session, task_prompt):
                # Collect coder output to parse result
                if event.get("type") == "assistant":
                    coder_output_parts.append(event.get("content", ""))

                # Add task context to event
                event["metadata"] = event.get("metadata", {})
                event["metadata"]["task_id"] = task.id
                event["metadata"]["attempt"] = attempt + 1

                # Yield coder events so they get sent to websocket
                yield event

            # Parse result from coder output
            full_output = "\n".join(coder_output_parts)
            result = parse_result_xml(full_output)

            if result is None:
                # Coder didn't emit structured result - infer from output
                if "error" in full_output.lower() or "failed" in full_output.lower():
                    result = TaskResult(
                        status=TaskStatus.FAILED,
                        summary="Task execution encountered errors",
                        errors=[full_output[:500]],
                    )
                else:
                    result = TaskResult(
                        status=TaskStatus.COMPLETED,
                        summary=full_output[:200] if full_output else "Task completed",
                    )

            if result.status == TaskStatus.COMPLETED:
                # Yield final result as special event
                yield {"_result": result}
                return

            last_result = result

            if attempt < self.max_retries:
                # Will retry with context about the failure
                continue

        # All retries exhausted
        final_result = last_result or TaskResult(
            status=TaskStatus.FAILED,
            summary="Task failed after all retries",
            errors=["Max retries exceeded"],
        )
        yield {"_result": final_result}

    def _build_coder_prompt(
        self,
        task: Task,
        plan: TaskPlan,
        last_result: Optional[TaskResult] = None,
    ) -> str:
        """Build a prompt for the coder agent for a specific task."""
        prompt = f"""Execute this task:

Task: {task.description}
Success Criteria: {task.success_criteria}
Overall Goal: {plan.intent}
"""
        if last_result and last_result.errors:
            prompt += f"""
Previous Attempt Failed:
{'; '.join(last_result.errors)}

Please try a different approach.
"""
        return prompt

    async def validate_result(
        self,
        task: Task,
        result: TaskResult,
    ) -> bool:
        """Validate that result meets task success criteria.

        For now, trust the coder's self-reported status.
        Future: Use LLM to validate result against criteria.
        """
        return result.status == TaskStatus.COMPLETED

    async def replan_on_failure(
        self,
        task: Task,
        error: str,
        plan: TaskPlan,
    ) -> Optional[TaskPlan]:
        """Generate a recovery plan when a task fails.

        Returns a new plan with recovery steps, or None to escalate to user.
        """
        messages: List[Dict[str, str]] = [
            {"role": "system", "content": MANAGER_SYSTEM_PROMPT},
            {"role": "user", "content": f"""
The following task failed:
Task: {task.description}
Error: {error}

Overall goal: {plan.intent}

Generate a recovery plan with alternative approaches, or respond with:
<plan>
  <intent>Cannot recover</intent>
  <confidence>0.0</confidence>
  <clarify>Question for user about how to proceed</clarify>
</plan>
"""},
        ]

        response = await self.client.chat(messages, model_override=self.model)
        recovery_plan = parse_plan_xml(response)

        if recovery_plan and recovery_plan.confidence > 0.3:
            return recovery_plan

        return None
