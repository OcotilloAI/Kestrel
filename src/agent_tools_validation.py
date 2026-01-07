"""Validation tools for the enhanced Coder agent.

Provides code validation, test execution, and git status tools
to enable high-autonomy execution with verification.
"""

import ast
import json
import os
import subprocess
from pathlib import Path
from typing import Dict, Any, Optional, Tuple


def _resolve_path(cwd: str, path_str: str) -> Tuple[Path, str]:
    """Resolve a path relative to working directory with security check."""
    if not path_str:
        raise ValueError("Path is required.")
    cwd_path = Path(cwd).resolve()
    if os.path.isabs(path_str):
        candidate = Path(path_str).resolve()
        if not str(candidate).startswith(str(cwd_path)):
            raise ValueError("Path escapes the working directory.")
        return candidate, str(candidate)
    candidate = (cwd_path / path_str).resolve()
    if not str(candidate).startswith(str(cwd_path)):
        raise ValueError("Path escapes the working directory.")
    return candidate, str(candidate)


def validate_syntax(cwd: str, language: str, content: str) -> Dict[str, Any]:
    """Validate code syntax before writing to disk.

    Supports: python, json, yaml
    Returns: {valid: bool, errors: [...]}
    """
    language = language.lower().strip()
    errors = []

    if language in ("python", "py"):
        try:
            ast.parse(content)
        except SyntaxError as e:
            errors.append({
                "line": e.lineno,
                "column": e.offset,
                "message": str(e.msg),
            })

    elif language == "json":
        try:
            json.loads(content)
        except json.JSONDecodeError as e:
            errors.append({
                "line": e.lineno,
                "column": e.colno,
                "message": e.msg,
            })

    elif language in ("yaml", "yml"):
        try:
            import yaml
            yaml.safe_load(content)
        except Exception as e:
            errors.append({
                "line": getattr(e, "problem_mark", {}).line if hasattr(e, "problem_mark") else 1,
                "message": str(e),
            })

    elif language in ("javascript", "js", "typescript", "ts"):
        # For JS/TS, we'd need node to validate - skip for now
        # Could use: node --check <file> or esbuild
        pass

    else:
        # Unknown language - return valid with warning
        return {
            "valid": True,
            "language": language,
            "errors": [],
            "warnings": [f"Syntax validation not implemented for {language}"],
        }

    return {
        "valid": len(errors) == 0,
        "language": language,
        "errors": errors,
    }


def run_tests(
    cwd: str,
    path: Optional[str] = None,
    test_filter: Optional[str] = None,
    framework: Optional[str] = None,
    timeout: int = 120,
) -> Dict[str, Any]:
    """Run tests and return structured results.

    Auto-detects test framework if not specified.
    Uses builder container for isolated execution.
    """
    # Determine test command
    test_cmd = None

    if framework:
        framework = framework.lower()
        if framework == "pytest":
            test_cmd = "pytest"
        elif framework == "jest":
            test_cmd = "npm test"
        elif framework == "unittest":
            test_cmd = "python -m unittest"
    else:
        # Auto-detect
        cwd_path = Path(cwd)
        if (cwd_path / "pytest.ini").exists() or (cwd_path / "pyproject.toml").exists():
            test_cmd = "pytest"
        elif (cwd_path / "package.json").exists():
            test_cmd = "npm test"
        elif list(cwd_path.glob("test_*.py")):
            test_cmd = "pytest"
        else:
            test_cmd = "pytest"  # Default fallback

    # Add path/filter if specified
    if path:
        test_cmd = f"{test_cmd} {path}"
    if test_filter:
        if "pytest" in test_cmd:
            test_cmd = f"{test_cmd} -k '{test_filter}'"
        elif "jest" in test_cmd:
            test_cmd = f"{test_cmd} -- --testNamePattern='{test_filter}'"

    # Add pytest options for cleaner output
    if "pytest" in test_cmd:
        test_cmd = f"{test_cmd} --tb=short -q"

    # Execute via builder container
    full_cmd = f'docker compose exec -T builder bash -lc "{test_cmd}"'

    try:
        result = subprocess.run(
            full_cmd,
            cwd=cwd,
            shell=True,
            capture_output=True,
            text=True,
            timeout=timeout,
        )

        output = (result.stdout or "") + (result.stderr or "")

        # Parse test results from output
        passed = 0
        failed = 0
        skipped = 0
        failures = []

        # pytest format: "X passed, Y failed, Z skipped"
        import re
        pytest_summary = re.search(
            r"(\d+)\s+passed.*?(\d+)\s+failed.*?(\d+)\s+skipped",
            output,
            re.IGNORECASE,
        )
        if pytest_summary:
            passed = int(pytest_summary.group(1))
            failed = int(pytest_summary.group(2))
            skipped = int(pytest_summary.group(3))
        else:
            # Simpler pattern
            passed_match = re.search(r"(\d+)\s+passed", output, re.IGNORECASE)
            failed_match = re.search(r"(\d+)\s+failed", output, re.IGNORECASE)
            if passed_match:
                passed = int(passed_match.group(1))
            if failed_match:
                failed = int(failed_match.group(1))

        # Extract failure details
        failure_blocks = re.findall(
            r"FAILED\s+([^\s]+).*?(?=FAILED|$)",
            output,
            re.DOTALL,
        )
        for block in failure_blocks[:5]:  # Limit to 5 failures
            failures.append({"name": block.strip()[:100]})

        return {
            "command": test_cmd,
            "exit_code": result.returncode,
            "passed": passed,
            "failed": failed,
            "skipped": skipped,
            "failures": failures,
            "output": output[:2000],  # Truncate for context window
        }

    except subprocess.TimeoutExpired:
        return {
            "command": test_cmd,
            "exit_code": -1,
            "error": f"Test execution timed out after {timeout} seconds",
            "passed": 0,
            "failed": 0,
            "failures": [],
        }
    except Exception as e:
        return {
            "command": test_cmd,
            "exit_code": -1,
            "error": str(e),
            "passed": 0,
            "failed": 0,
            "failures": [],
        }


def git_status(cwd: str, path: str = ".", include_diff: bool = False) -> Dict[str, Any]:
    """Get clean git status information.

    Returns: {branch, clean, staged, modified, untracked, ahead, behind}
    """
    resolved, _ = _resolve_path(cwd, path)

    try:
        # Get current branch
        branch_result = subprocess.run(
            ["git", "rev-parse", "--abbrev-ref", "HEAD"],
            cwd=str(resolved),
            capture_output=True,
            text=True,
        )
        branch = branch_result.stdout.strip() if branch_result.returncode == 0 else "unknown"

        # Get status
        status_result = subprocess.run(
            ["git", "status", "--porcelain"],
            cwd=str(resolved),
            capture_output=True,
            text=True,
        )

        staged = []
        modified = []
        untracked = []

        if status_result.returncode == 0:
            for line in status_result.stdout.strip().split("\n"):
                if not line:
                    continue
                status_code = line[:2]
                file_path = line[3:]

                if status_code[0] in "MADRC":  # Staged changes
                    staged.append(file_path)
                if status_code[1] in "MD":  # Unstaged changes
                    modified.append(file_path)
                if status_code == "??":  # Untracked
                    untracked.append(file_path)

        # Get ahead/behind count
        ahead = 0
        behind = 0
        try:
            ab_result = subprocess.run(
                ["git", "rev-list", "--left-right", "--count", f"{branch}...origin/{branch}"],
                cwd=str(resolved),
                capture_output=True,
                text=True,
            )
            if ab_result.returncode == 0:
                parts = ab_result.stdout.strip().split()
                if len(parts) == 2:
                    ahead = int(parts[0])
                    behind = int(parts[1])
        except Exception:
            pass

        result: Dict[str, Any] = {
            "branch": branch,
            "clean": len(staged) == 0 and len(modified) == 0,
            "staged": staged,
            "modified": modified,
            "untracked": untracked,
            "ahead": ahead,
            "behind": behind,
        }

        # Optionally include diff
        if include_diff:
            diff_result = subprocess.run(
                ["git", "diff"],
                cwd=str(resolved),
                capture_output=True,
                text=True,
            )
            result["diff"] = diff_result.stdout[:3000]  # Truncate

        return result

    except Exception as e:
        return {
            "error": str(e),
            "branch": "unknown",
            "clean": False,
            "staged": [],
            "modified": [],
            "untracked": [],
        }


def git_diff(
    cwd: str,
    path: Optional[str] = None,
    staged: bool = False,
    commit: Optional[str] = None,
) -> Dict[str, Any]:
    """Show git diff for working directory or specific files."""
    cmd = ["git", "diff"]

    if staged:
        cmd.append("--staged")
    if commit:
        cmd.append(commit)
    if path:
        resolved, _ = _resolve_path(cwd, path)
        cmd.append(str(resolved))

    try:
        result = subprocess.run(
            cmd,
            cwd=cwd,
            capture_output=True,
            text=True,
        )

        return {
            "command": " ".join(cmd),
            "exit_code": result.returncode,
            "diff": result.stdout[:5000],  # Truncate for context window
        }
    except Exception as e:
        return {
            "command": " ".join(cmd),
            "error": str(e),
        }


# Tool definitions for registration
VALIDATION_TOOL_DEFINITIONS = [
    {
        "type": "function",
        "function": {
            "name": "validate_syntax",
            "description": "Validate code syntax before writing. Returns errors if invalid.",
            "parameters": {
                "type": "object",
                "properties": {
                    "language": {
                        "type": "string",
                        "description": "Programming language (python, json, yaml, javascript, typescript)",
                    },
                    "content": {
                        "type": "string",
                        "description": "Code content to validate",
                    },
                },
                "required": ["language", "content"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "run_tests",
            "description": "Run tests and return structured results. Auto-detects test framework.",
            "parameters": {
                "type": "object",
                "properties": {
                    "path": {
                        "type": "string",
                        "description": "Test file or directory (optional)",
                    },
                    "filter": {
                        "type": "string",
                        "description": "Test name pattern filter (optional)",
                    },
                    "framework": {
                        "type": "string",
                        "description": "Test framework: pytest, jest, unittest (optional, auto-detected)",
                    },
                    "timeout": {
                        "type": "integer",
                        "description": "Timeout in seconds (default: 120)",
                    },
                },
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "git_status",
            "description": "Get git status: branch, staged/modified/untracked files, ahead/behind count.",
            "parameters": {
                "type": "object",
                "properties": {
                    "path": {
                        "type": "string",
                        "description": "Directory to check (default: current)",
                    },
                    "include_diff": {
                        "type": "boolean",
                        "description": "Include diff content (default: false)",
                    },
                },
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "git_diff",
            "description": "Show git diff for working directory or specific files.",
            "parameters": {
                "type": "object",
                "properties": {
                    "path": {
                        "type": "string",
                        "description": "File or directory to diff (optional)",
                    },
                    "staged": {
                        "type": "boolean",
                        "description": "Show staged changes only (default: false)",
                    },
                    "commit": {
                        "type": "string",
                        "description": "Compare against specific commit (optional)",
                    },
                },
            },
        },
    },
]


def run_validation_tool(
    cwd: str, name: str, args: Dict[str, Any]
) -> Optional[Dict[str, Any]]:
    """Run a validation tool by name. Returns None if tool not found."""
    if name == "validate_syntax":
        return validate_syntax(
            cwd,
            args.get("language", ""),
            args.get("content", ""),
        )
    if name == "run_tests":
        return run_tests(
            cwd,
            path=args.get("path"),
            test_filter=args.get("filter"),
            framework=args.get("framework"),
            timeout=args.get("timeout", 120),
        )
    if name == "git_status":
        return git_status(
            cwd,
            path=args.get("path", "."),
            include_diff=args.get("include_diff", False),
        )
    if name == "git_diff":
        return git_diff(
            cwd,
            path=args.get("path"),
            staged=args.get("staged", False),
            commit=args.get("commit"),
        )
    return None
