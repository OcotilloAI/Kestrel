import os
import subprocess
from pathlib import Path
from typing import Dict, Any, Tuple, List

# Import validation tools
try:
    from agent_tools_validation import (
        VALIDATION_TOOL_DEFINITIONS,
        run_validation_tool,
    )
    _HAS_VALIDATION_TOOLS = True
except ImportError:
    VALIDATION_TOOL_DEFINITIONS = []
    _HAS_VALIDATION_TOOLS = False


def _resolve_path(cwd: str, path_str: str) -> Tuple[Path, str]:
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


def list_dir(cwd: str, path: str = ".") -> Dict[str, Any]:
    resolved, _ = _resolve_path(cwd, path)
    if not resolved.exists() or not resolved.is_dir():
        raise ValueError(f"Directory not found: {path}")
    entries = sorted(os.listdir(resolved))
    return {"path": path, "entries": entries}


def read_file(cwd: str, path: str) -> Dict[str, Any]:
    resolved, _ = _resolve_path(cwd, path)
    if not resolved.exists() or not resolved.is_file():
        raise ValueError(f"File not found: {path}")
    content = resolved.read_text(encoding="utf-8", errors="ignore")
    return {"path": path, "content": content}


def write_file(cwd: str, path: str, content: str) -> Dict[str, Any]:
    resolved, _ = _resolve_path(cwd, path)
    resolved.parent.mkdir(parents=True, exist_ok=True)
    resolved.write_text(content or "", encoding="utf-8")
    return {"path": path, "bytes_written": len(content or "")}


def append_file(cwd: str, path: str, content: str) -> Dict[str, Any]:
    resolved, _ = _resolve_path(cwd, path)
    resolved.parent.mkdir(parents=True, exist_ok=True)
    with resolved.open("a", encoding="utf-8") as handle:
        handle.write(content or "")
    return {"path": path, "bytes_written": len(content or "")}


def run_shell(cwd: str, command: str, timeout: int = 60) -> Dict[str, Any]:
    if not command:
        raise ValueError("Command is required.")
    try:
        result = subprocess.run(
            command,
            cwd=cwd,
            shell=True,
            capture_output=True,
            text=True,
            timeout=timeout,
        )
        output = (result.stdout or "") + (result.stderr or "")
        return {
            "command": command,
            "exit_code": result.returncode,
            "output": output.strip(),
        }
    except subprocess.TimeoutExpired:
        return {
            "command": command,
            "exit_code": -1,
            "output": f"Command timed out after {timeout} seconds. Long-running servers should be started with '&' to run in background.",
        }


TOOL_DEFINITIONS: List[Dict[str, Any]] = [
    {
        "type": "function",
        "function": {
            "name": "shell",
            "description": "Run a shell command in the session working directory.",
            "parameters": {
                "type": "object",
                "properties": {
                    "command": {"type": "string", "description": "Shell command to execute."}
                },
                "required": ["command"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "list_dir",
            "description": "List entries in a directory relative to the session working directory.",
            "parameters": {
                "type": "object",
                "properties": {
                    "path": {"type": "string", "description": "Relative path to list."}
                },
                "required": ["path"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "read_file",
            "description": "Read a file relative to the session working directory.",
            "parameters": {
                "type": "object",
                "properties": {
                    "path": {"type": "string", "description": "Relative file path to read."}
                },
                "required": ["path"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "write_file",
            "description": "Write content to a file relative to the session working directory.",
            "parameters": {
                "type": "object",
                "properties": {
                    "path": {"type": "string", "description": "Relative file path to write."},
                    "content": {"type": "string", "description": "File content."}
                },
                "required": ["path", "content"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "append_file",
            "description": "Append content to a file relative to the session working directory.",
            "parameters": {
                "type": "object",
                "properties": {
                    "path": {"type": "string", "description": "Relative file path to append to."},
                    "content": {"type": "string", "description": "Content to append."}
                },
                "required": ["path", "content"],
            },
        },
    },
]

# Extend with validation tools if available
if _HAS_VALIDATION_TOOLS:
    TOOL_DEFINITIONS.extend(VALIDATION_TOOL_DEFINITIONS)
