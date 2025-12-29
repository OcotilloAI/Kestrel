import os
import subprocess
from pathlib import Path
from typing import Dict, Any, Tuple


def _resolve_path(cwd: str, path_str: str) -> Tuple[Path, str]:
    if not path_str:
        raise ValueError("Path is required.")
    if os.path.isabs(path_str):
        raise ValueError("Absolute paths are not allowed. Use a path relative to the working directory.")
    cwd_path = Path(cwd).resolve()
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


def run_shell(cwd: str, command: str) -> Dict[str, Any]:
    if not command:
        raise ValueError("Command is required.")
    result = subprocess.run(
        command,
        cwd=cwd,
        shell=True,
        capture_output=True,
        text=True,
    )
    output = (result.stdout or "") + (result.stderr or "")
    return {
        "command": command,
        "exit_code": result.returncode,
        "output": output.strip(),
    }
