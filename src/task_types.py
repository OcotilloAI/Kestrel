"""Task types for Manager/Coder agent communication.

Uses dataclasses for structured task management with XML serialization
support for Qwen3-Coder compatibility.
"""

import re
from dataclasses import dataclass, field
from enum import Enum
from typing import List, Optional


class TaskStatus(Enum):
    """Status of a task in the execution pipeline."""
    PENDING = "pending"
    IN_PROGRESS = "in_progress"
    COMPLETED = "completed"
    FAILED = "failed"
    BLOCKED = "blocked"


@dataclass
class Task:
    """A single task assigned by the Manager to the Coder."""
    id: str
    description: str
    success_criteria: str
    dependencies: List[str] = field(default_factory=list)
    status: TaskStatus = TaskStatus.PENDING
    result: Optional[str] = None
    errors: List[str] = field(default_factory=list)
    retries: int = 0


@dataclass
class TaskPlan:
    """A plan produced by the Manager from user intent."""
    intent: str
    confidence: float
    tasks: List[Task]
    needs_clarification: Optional[str] = None


@dataclass
class TaskResult:
    """Result reported by the Coder after task execution."""
    status: TaskStatus
    summary: str
    files_changed: List[str] = field(default_factory=list)
    tested: bool = False
    errors: List[str] = field(default_factory=list)


def parse_plan_xml(content: str) -> Optional[TaskPlan]:
    """Parse a <plan> XML block from LLM output.

    Expected format:
    <plan>
      <intent>User's goal</intent>
      <confidence>0.85</confidence>
      <clarify>Question if needed</clarify>
      <task id="1">
        <description>What to do</description>
        <criteria>How to verify</criteria>
        <depends>task_id</depends>
      </task>
    </plan>
    """
    plan_match = re.search(r"<plan>([\s\S]*?)</plan>", content)
    if not plan_match:
        return None

    plan_text = plan_match.group(1)

    # Extract intent
    intent_match = re.search(r"<intent>([\s\S]*?)</intent>", plan_text)
    intent = intent_match.group(1).strip() if intent_match else ""

    # Extract confidence
    conf_match = re.search(r"<confidence>([\d.]+)</confidence>", plan_text)
    confidence = float(conf_match.group(1)) if conf_match else 0.5

    # Extract clarification question (optional)
    clarify_match = re.search(r"<clarify>([\s\S]*?)</clarify>", plan_text)
    needs_clarification = clarify_match.group(1).strip() if clarify_match else None
    if needs_clarification == "":
        needs_clarification = None

    # Extract tasks
    tasks: List[Task] = []
    task_blocks = re.findall(r'<task\s+id=["\']?(\d+)["\']?>([\s\S]*?)</task>', plan_text)

    for task_id, task_text in task_blocks:
        desc_match = re.search(r"<description>([\s\S]*?)</description>", task_text)
        criteria_match = re.search(r"<criteria>([\s\S]*?)</criteria>", task_text)
        depends_match = re.search(r"<depends>([\s\S]*?)</depends>", task_text)

        description = desc_match.group(1).strip() if desc_match else ""
        criteria = criteria_match.group(1).strip() if criteria_match else ""
        depends_text = depends_match.group(1).strip() if depends_match else ""
        dependencies = [d.strip() for d in depends_text.split(",") if d.strip()]

        tasks.append(Task(
            id=task_id,
            description=description,
            success_criteria=criteria,
            dependencies=dependencies,
        ))

    return TaskPlan(
        intent=intent,
        confidence=confidence,
        tasks=tasks,
        needs_clarification=needs_clarification,
    )


def parse_result_xml(content: str) -> Optional[TaskResult]:
    """Parse a <result> XML block from Coder output.

    Expected format:
    <result>
      <status>success|partial|failed</status>
      <summary>What was accomplished</summary>
      <files>path1.py, path2.py</files>
      <tested>true</tested>
      <errors>Error message if any</errors>
    </result>
    """
    result_match = re.search(r"<result>([\s\S]*?)</result>", content)
    if not result_match:
        return None

    result_text = result_match.group(1)

    # Extract status
    status_match = re.search(r"<status>([\s\S]*?)</status>", result_text)
    status_str = status_match.group(1).strip().lower() if status_match else "failed"

    status_map = {
        "success": TaskStatus.COMPLETED,
        "completed": TaskStatus.COMPLETED,
        "partial": TaskStatus.IN_PROGRESS,
        "failed": TaskStatus.FAILED,
        "error": TaskStatus.FAILED,
    }
    status = status_map.get(status_str, TaskStatus.FAILED)

    # Extract summary
    summary_match = re.search(r"<summary>([\s\S]*?)</summary>", result_text)
    summary = summary_match.group(1).strip() if summary_match else ""

    # Extract files changed
    files_match = re.search(r"<files>([\s\S]*?)</files>", result_text)
    files_text = files_match.group(1).strip() if files_match else ""
    files_changed = [f.strip() for f in files_text.split(",") if f.strip()]

    # Extract tested flag
    tested_match = re.search(r"<tested>([\s\S]*?)</tested>", result_text)
    tested_str = tested_match.group(1).strip().lower() if tested_match else "false"
    tested = tested_str in ("true", "yes", "1")

    # Extract errors
    errors_match = re.search(r"<errors>([\s\S]*?)</errors>", result_text)
    errors_text = errors_match.group(1).strip() if errors_match else ""
    errors = [errors_text] if errors_text else []

    return TaskResult(
        status=status,
        summary=summary,
        files_changed=files_changed,
        tested=tested,
        errors=errors,
    )
