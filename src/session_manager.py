import uuid
import logging
import os
import shutil
import subprocess
import json
import base64
from pathlib import Path
from typing import Dict, Optional, List, Any

from agent_session import AgentSession
from naming import generate_name

class SessionManager:
    def __init__(self, workdir_root: str = None):
        self._sessions: Dict[str, AgentSession] = {}
        self._session_metadata: Dict[str, Dict[str, Any]] = {}
        self._transcripts: Dict[str, List[Dict[str, Any]]] = {}
        self._transcript_paths: Dict[str, Path] = {}
        self.logger = logging.getLogger("SessionManager")
        
        # Determine root storage for sessions
        if workdir_root:
             self.workdir_root = Path(workdir_root)
        else:
             self.workdir_root = Path(os.environ.get("KESTREL_WORKDIR", os.getcwd()))
        
        self.sessions_dir = self.workdir_root / "sessions"
        self.sessions_dir.mkdir(parents=True, exist_ok=True)

    def create_session(self, cwd: str = None, copy_from_path: str = None) -> str:
        """
        Create a new agent session using Git-based hierarchy.
        
        - New Session: Creates 'workspace/{project_name}/main' and initializes a git repo.
        - Clone Session: Clones the source git repo into 'workspace/{project_name}/{branch_name}'.
        """
        session_id = str(uuid.uuid4())
        
        # 1. Determine Paths
        if cwd:
            # Explicit CWD (Shared Session or manual) - No new git logic, just attach
            final_cwd = Path(cwd)
            # Try to derive project/session names from path structure if possible
            if final_cwd.parent.parent.name == "workspace":
                 session_name = f"{final_cwd.parent.name}/{final_cwd.name}"
            else:
                 session_name = final_cwd.name
                 
        elif copy_from_path:
            # CLONE (Branching)
            source_path = Path(copy_from_path)
            if not source_path.exists():
                 raise ValueError(f"Source path {source_path} does not exist")
            
            # Assume structure: .../{project}/{branch}
            project_dir = source_path.parent
            
            # Generate new branch name (adjective-noun)
            branch_name = generate_name()
            final_cwd = project_dir / branch_name
            session_name = f"{project_dir.name}/{branch_name}"
            
            self.logger.info(f"Cloning git repo from {source_path} to {final_cwd}")
            if final_cwd.exists():
                raise ValueError(f"Destination path {final_cwd} already exists")
            
            # Git Clone
            try:
                # We clone locally. 
                subprocess.run(["git", "clone", str(source_path), str(final_cwd)], check=True)
                # Configure user for this repo to allow commits
                subprocess.run(["git", "config", "user.email", "kestrel@ocotillo.ai"], cwd=final_cwd, check=True)
                subprocess.run(["git", "config", "user.name", "Kestrel Agent"], cwd=final_cwd, check=True)
                subprocess.run(["git", "checkout", "-b", branch_name], cwd=final_cwd, check=True)
            except subprocess.CalledProcessError as e:
                self.logger.error(f"Git clone failed: {e}")
                # Fallback to copy if not a git repo?
                self.logger.info("Fallback to file copy...")
                try:
                    final_cwd.mkdir(parents=True, exist_ok=True)
                    self._copy_contents(source_path, final_cwd)
                except Exception as copy_error:
                    self.logger.error(f"Fallback copy failed: {copy_error}")
                    raise

        else:
            # NEW PROJECT
            project_name = generate_name()
            project_dir = self.workdir_root / project_name
            final_cwd = project_dir / "main"
            session_name = f"{project_name}/main"
            
            if final_cwd.exists():
                raise ValueError(f"Destination path {final_cwd} already exists")
            final_cwd.mkdir(parents=True, exist_ok=True)
            
            # Git Init
            try:
                subprocess.run(["git", "init"], cwd=final_cwd, check=True)
                subprocess.run(["git", "config", "user.email", "kestrel@ocotillo.ai"], cwd=final_cwd, check=True)
                subprocess.run(["git", "config", "user.name", "Kestrel Agent"], cwd=final_cwd, check=True)
                
                # Initial Commit
                subprocess.run(["git", "add", "."], cwd=final_cwd, check=True)
                subprocess.run(["git", "commit", "-m", "Initial commit by Kestrel"], cwd=final_cwd, check=True)
                
            except subprocess.CalledProcessError as e:
                self.logger.error(f"Git init failed: {e}")

        # Ensure directory exists (redundant for new logic but safe)
        if not final_cwd.exists():
            final_cwd.mkdir(parents=True, exist_ok=True)

        project_root = self._resolve_project_root(final_cwd)
        branch_name = None
        if project_root and self._is_relative_to(final_cwd, project_root):
            branch_name = final_cwd.name
        session = AgentSession(cwd=str(final_cwd))
        self._sessions[session_id] = session
        self._session_metadata[session_id] = {
            "id": session_id,
            "name": session_name,
            "cwd": str(final_cwd),
            "project_root": str(project_root) if project_root else None,
            "branch_name": branch_name,
        }
        self._transcripts[session_id] = []
        transcript_path = self._build_transcript_path(branch_name, project_root, session_id)
        self._transcript_paths[session_id] = transcript_path
        if transcript_path.exists():
            context_seed = self._extract_context_seed(transcript_path)
            history_seed = self._extract_history_seed(transcript_path, max_events=6)
            if history_seed:
                session.history.extend(history_seed)
            if context_seed:
                self._session_metadata[session_id]["context_seed"] = context_seed
            if transcript_path.stat().st_size > 0:
                self._session_metadata[session_id]["welcome_sent"] = True
        self.logger.info(f"Created session '{session_name}' ({session_id}) in {final_cwd}")
        return session_id

    def _copy_contents(self, src: Path, dst: Path):
        for item in src.iterdir():
            if item.name == "sessions": continue # Don't recursive copy sessions dir if we are at root
            
            dest_path = dst / item.name
            if item.is_dir():
                shutil.copytree(item, dest_path, dirs_exist_ok=True)
            else:
                shutil.copy2(item, dest_path)

    def get_session(self, session_id: str) -> Optional[AgentSession]:
        """Retrieve an active session by ID."""
        return self._sessions.get(session_id)
        
    def get_session_metadata(self, session_id: str) -> Optional[Dict]:
        return self._session_metadata.get(session_id)

    def list_projects(self) -> List[str]:
        """List all project directories in the workspace."""
        if not self.workdir_root.exists():
            return []
        return [d.name for d in self.workdir_root.iterdir() if d.is_dir() and (d / "main").exists()]

    def list_branches(self, project_name: str) -> List[str]:
        """List all branches (subdirectories) within a project."""
        project_dir = self.workdir_root / project_name
        if not project_dir.exists():
            return []
        return [d.name for d in project_dir.iterdir() if d.is_dir() and (d / ".git").exists()]

    def delete_project(self, project_name: str) -> bool:
        """Delete an entire project and all its branches."""
        project_dir = self.workdir_root / project_name
        if not project_dir.exists():
            return False
        
        # Ensure we're not deleting an active session's directory
        sessions_to_kill = [
            sid for sid, meta in self._session_metadata.items() 
            if self._is_relative_to(Path(meta.get("cwd", "")), project_dir)
        ]
        for sid in sessions_to_kill:
            self.kill_session(sid)
            
        shutil.rmtree(project_dir)
        self.logger.info(f"Deleted project {project_name}")
        return True

    def create_branch(self, project_name: str, branch_name: Optional[str] = None, source_branch: str = "main") -> str:
        project_dir = self.workdir_root / project_name
        source_dir = project_dir / source_branch
        if not source_dir.exists():
            raise ValueError(f"Source branch {source_branch} does not exist")

        branch_name = branch_name or generate_name()
        branch_dir = project_dir / branch_name
        if branch_dir.exists():
            raise ValueError(f"Destination path {branch_dir} already exists")

        try:
            subprocess.run(["git", "clone", str(source_dir), str(branch_dir)], check=True)
            subprocess.run(["git", "config", "user.email", "kestrel@ocotillo.ai"], cwd=branch_dir, check=True)
            subprocess.run(["git", "config", "user.name", "Kestrel Agent"], cwd=branch_dir, check=True)
            subprocess.run(["git", "checkout", "-b", branch_name], cwd=branch_dir, check=True)
        except subprocess.CalledProcessError as e:
            self.logger.error(f"Branch clone failed: {e}")
            raise

        return branch_name

    def delete_branch(self, project_name: str, branch_name: str) -> bool:
        """Delete a branch directory inside a project."""
        branch_dir = self.workdir_root / project_name / branch_name
        if not branch_dir.exists():
            return False

        sessions_to_kill = [
            sid for sid, meta in self._session_metadata.items()
            if self._is_relative_to(Path(meta.get("cwd", "")), branch_dir)
        ]
        for sid in sessions_to_kill:
            self.kill_session(sid)

        shutil.rmtree(branch_dir)
        self.logger.info(f"Deleted branch {project_name}/{branch_name}")
        return True

    def merge_branch_into_main(self, project_name: str, branch_name: str) -> bool:
        if branch_name == "main":
            raise ValueError("Cannot merge main into itself")
        project_dir = self.workdir_root / project_name
        main_dir = project_dir / "main"
        branch_dir = project_dir / branch_name
        if not main_dir.exists():
            raise ValueError(f"Main branch does not exist for project {project_name}")
        if not branch_dir.exists():
            raise ValueError(f"Branch {branch_name} does not exist")

        remote_name = f"kestrel_{branch_name}"
        try:
            subprocess.run(["git", "remote", "remove", remote_name], cwd=main_dir, check=False)
            subprocess.run(["git", "remote", "add", remote_name, str(branch_dir)], cwd=main_dir, check=True)
            subprocess.run(["git", "fetch", remote_name, branch_name], cwd=main_dir, check=True)
            subprocess.run(["git", "merge", "--no-edit", "FETCH_HEAD"], cwd=main_dir, check=True)
            subprocess.run(["git", "remote", "remove", remote_name], cwd=main_dir, check=False)
        except subprocess.CalledProcessError as e:
            self.logger.error(f"Merge failed: {e}")
            raise
        return True

    def sync_branch_from_main(self, project_name: str, branch_name: str) -> bool:
        if branch_name == "main":
            raise ValueError("Main is already up to date")
        project_dir = self.workdir_root / project_name
        main_dir = project_dir / "main"
        branch_dir = project_dir / branch_name
        if not main_dir.exists():
            raise ValueError(f"Main branch does not exist for project {project_name}")
        if not branch_dir.exists():
            raise ValueError(f"Branch {branch_name} does not exist")

        remote_name = "kestrel_main"
        try:
            subprocess.run(["git", "remote", "remove", remote_name], cwd=branch_dir, check=False)
            subprocess.run(["git", "remote", "add", remote_name, str(main_dir)], cwd=branch_dir, check=True)
            subprocess.run(["git", "fetch", remote_name, "main"], cwd=branch_dir, check=True)
            subprocess.run(["git", "merge", "--no-edit", "FETCH_HEAD"], cwd=branch_dir, check=True)
            subprocess.run(["git", "remote", "remove", remote_name], cwd=branch_dir, check=False)
        except subprocess.CalledProcessError as e:
            self.logger.error(f"Sync failed: {e}")
            raise
        return True

    def _is_relative_to(self, path: Path, base: Path) -> bool:
        try:
            path.resolve().relative_to(base.resolve())
            return True
        except ValueError:
            return False

    def rename_session(self, session_id: str, new_name: str) -> bool:
        """Rename an active session."""
        if session_id in self._session_metadata:
            self._session_metadata[session_id]["name"] = new_name
            self.logger.info(f"Renamed session {session_id} to '{new_name}'")
            return True
        return False

    def list_sessions(self) -> List[Dict[str, Any]]:
        """List all active sessions."""
        return [
            {
                "id": sid,
                "alive": True,
                "name": self._session_metadata.get(sid, {}).get("name", "Unknown"),
                "cwd": self._session_metadata.get(sid, {}).get("cwd"),
            }
            for sid in self._sessions.keys()
        ]

    def kill_session(self, session_id: str) -> bool:
        """Terminate a specific session."""
        if session_id in self._sessions:
            del self._sessions[session_id]
            if session_id in self._session_metadata:
                 del self._session_metadata[session_id]
            if session_id in self._transcripts:
                del self._transcripts[session_id]
            if session_id in self._transcript_paths:
                del self._transcript_paths[session_id]
            self.logger.info(f"Killed session {session_id}")
            return True
        return False

    def shutdown_all(self):
        """Terminate all sessions."""
        for sid in list(self._sessions.keys()):
            self.kill_session(sid)

    def _resolve_project_root(self, cwd: Path) -> Optional[Path]:
        cwd = cwd.resolve()
        try:
            rel = cwd.relative_to(self.workdir_root.resolve())
        except ValueError:
            return None
        parts = rel.parts
        if len(parts) >= 2:
            return self.workdir_root / parts[0]
        return None

    def _build_transcript_path(self, branch_name: Optional[str], project_root: Optional[Path], session_id: str) -> Path:
        if project_root:
            session_dir = project_root / ".kestrel"
            session_dir.mkdir(parents=True, exist_ok=True)
            file_name = f"{branch_name}.jsonl" if branch_name else f"{session_id}.jsonl"
            return session_dir / file_name
        return self.sessions_dir / f"{session_id}.jsonl"

    def record_event(self, session_id: str, event: Dict[str, Any]) -> None:
        if session_id not in self._transcripts:
            self._transcripts[session_id] = []
            meta = self._session_metadata.get(session_id, {})
            project_root = Path(meta["project_root"]) if meta.get("project_root") else None
            branch_name = meta.get("branch_name")
            self._transcript_paths[session_id] = self._build_transcript_path(branch_name, project_root, session_id)
        content = event.get("content", "")
        if content is None:
            content = ""
        if not isinstance(content, str):
            content = str(content)
        encoded = base64.b64encode(content.encode("utf-8")).decode("ascii")
        stored_event = dict(event)
        stored_event["source"] = stored_event.get("source") or stored_event.get("role") or stored_event.get("type") or "unknown"
        stored_event["body_b64"] = encoded
        stored_event.pop("content", None)
        self._transcripts[session_id].append(stored_event)
        path = self._transcript_paths.get(session_id)
        if not path:
            return
        try:
            with path.open("a", encoding="utf-8") as handle:
                handle.write(json.dumps(stored_event, ensure_ascii=True) + "\n")
        except Exception:
            self.logger.exception("Failed to append transcript event")

    def get_transcript(self, session_id: str) -> List[Dict[str, Any]]:
        meta = self._session_metadata.get(session_id, {})
        project_root = Path(meta["project_root"]) if meta.get("project_root") else None
        branch_name = meta.get("branch_name")
        path = self._build_transcript_path(branch_name, project_root, session_id)
        events: List[Dict[str, Any]] = []
        if path.exists():
            try:
                with path.open("r", encoding="utf-8") as handle:
                    for line in handle:
                        line = line.strip()
                        if not line:
                            continue
                        events.append(json.loads(line))
            except Exception:
                self.logger.exception("Failed to read transcript file")
        if not events:
            events = list(self._transcripts.get(session_id, []))
        decoded: List[Dict[str, Any]] = []
        for event in events:
            body_b64 = event.get("body_b64")
            if body_b64:
                try:
                    content = base64.b64decode(body_b64.encode("ascii")).decode("utf-8")
                except Exception:
                    content = ""
            else:
                content = event.get("content", "")
            decoded_event = dict(event)
            decoded_event["content"] = content
            decoded.append(decoded_event)
        return self._aggregate_transcript(decoded)

    def _extract_context_seed(self, path: Path) -> str:
        last_user = None
        last_plan = None
        try:
            with path.open("r", encoding="utf-8") as handle:
                for line in handle:
                    line = line.strip()
                    if not line:
                        continue
                    try:
                        event = json.loads(line)
                    except json.JSONDecodeError:
                        continue
                    content_b64 = event.get("body_b64")
                    if content_b64:
                        try:
                            content = base64.b64decode(content_b64.encode("ascii")).decode("utf-8")
                        except Exception:
                            content = ""
                    else:
                        content = str(event.get("content", ""))
                    role = event.get("role")
                    source = event.get("source")
                    if role == "user" and content:
                        last_user = content
                    if source == "controller" and "Proposed plan" in content:
                        last_plan = content
        except Exception:
            return ""
        parts: List[str] = []
        if last_user:
            parts.append(f"Last user request: {last_user}")
        if last_plan:
            parts.append(f"Last plan:\n{last_plan}")
        return "\n".join(parts).strip()

    def _extract_history_seed(self, path: Path, max_events: int = 6) -> List[Dict[str, str]]:
        seeded: List[Dict[str, str]] = []
        try:
            with path.open("r", encoding="utf-8") as handle:
                events = []
                for line in handle:
                    line = line.strip()
                    if not line:
                        continue
                    try:
                        events.append(json.loads(line))
                    except json.JSONDecodeError:
                        continue
        except Exception:
            return seeded
        for event in reversed(events):
            if len(seeded) >= max_events:
                break
            role = event.get("role")
            if role not in {"user", "assistant"}:
                continue
            content_b64 = event.get("body_b64")
            if content_b64:
                try:
                    content = base64.b64decode(content_b64.encode("ascii")).decode("utf-8")
                except Exception:
                    content = ""
            else:
                content = str(event.get("content", ""))
            if not content:
                continue
            seeded.append({"role": role, "content": content})
        seeded.reverse()
        return seeded

    def _aggregate_transcript(self, events: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        aggregated: List[Dict[str, Any]] = []
        buffer_event: Optional[Dict[str, Any]] = None
        buffer_key: Optional[tuple] = None

        def flush():
            nonlocal buffer_event, buffer_key
            if buffer_event:
                aggregated.append(buffer_event)
            buffer_event = None
            buffer_key = None

        def merge_text(prev: str, nxt: str) -> str:
            if not prev:
                return nxt
            if not nxt:
                return prev
            if prev.endswith(("\n", " ")):
                return prev + nxt
            if nxt.startswith((" ", "\n", "\t", "'", ".", ",", "!", "?", ":", ";", ")", "]", "}", "%")):
                return prev + nxt
            return f"{prev} {nxt}"

        for event in events:
            content = event.get("content", "")
            if content is None:
                content = ""
            if not isinstance(content, str):
                content = str(content)
            if content == "":
                continue

            key = (event.get("type"), event.get("role"), event.get("source"))
            mergeable = event.get("type") in {"assistant", "detail", "system"}

            if buffer_event and buffer_key == key and mergeable:
                buffer_event["content"] = merge_text(buffer_event.get("content", ""), content)
                buffer_event["timestamp"] = event.get("timestamp", buffer_event.get("timestamp"))
                continue

            flush()
            buffer_event = dict(event)
            buffer_event["content"] = content
            buffer_key = key

        flush()
        return aggregated
