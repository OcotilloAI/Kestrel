import uuid
import logging
import os
import shutil
import subprocess
from pathlib import Path
from typing import Dict, Optional, List, Any

from goose_wrapper import GooseWrapper
from naming import generate_name

class SessionManager:
    def __init__(self, workdir_root: str = None):
        self._sessions: Dict[str, GooseWrapper] = {}
        self._session_metadata: Dict[str, Dict[str, Any]] = {}
        self.logger = logging.getLogger("SessionManager")
        
        # Determine root storage for sessions
        if workdir_root:
             self.workdir_root = Path(workdir_root)
        else:
             self.workdir_root = Path(os.environ.get("GOOSE_WORKDIR", os.getcwd()))
        
        self.sessions_dir = self.workdir_root / "sessions"
        self.sessions_dir.mkdir(parents=True, exist_ok=True)

    def create_session(self, cwd: str = None, copy_from_path: str = None) -> str:
        """
        Create a new Goose session using Git-based hierarchy.
        
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
                
                # Copy hints
                root_hints = self.workdir_root / ".goosehints"
                if root_hints.exists():
                    shutil.copy2(root_hints, final_cwd / ".goosehints")
                    
                # Initial Commit
                subprocess.run(["git", "add", "."], cwd=final_cwd, check=True)
                subprocess.run(["git", "commit", "-m", "Initial commit by Kestrel"], cwd=final_cwd, check=True)
                
            except subprocess.CalledProcessError as e:
                self.logger.error(f"Git init failed: {e}")

        # Ensure directory exists (redundant for new logic but safe)
        if not final_cwd.exists():
            final_cwd.mkdir(parents=True, exist_ok=True)

        wrapper = GooseWrapper()
        
        try:
            wrapper.start(cwd=str(final_cwd))
            self._sessions[session_id] = wrapper
            self._session_metadata[session_id] = {
                "id": session_id,
                "name": session_name,
                "cwd": str(final_cwd),
            }
            self.logger.info(f"Created session '{session_name}' ({session_id}) in {final_cwd}")
            return session_id
        except Exception as e:
            self.logger.error(f"Failed to start session: {e}")
            raise

    def _copy_contents(self, src: Path, dst: Path):
        for item in src.iterdir():
            if item.name == "sessions": continue # Don't recursive copy sessions dir if we are at root
            
            dest_path = dst / item.name
            if item.is_dir():
                shutil.copytree(item, dest_path, dirs_exist_ok=True)
            else:
                shutil.copy2(item, dest_path)

    def get_session(self, session_id: str) -> Optional[GooseWrapper]:
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
                "alive": wrapper.is_alive(),
                "name": self._session_metadata.get(sid, {}).get("name", "Unknown"),
                "cwd": self._session_metadata.get(sid, {}).get("cwd")
            } 
            for sid, wrapper in self._sessions.items()
        ]

    def kill_session(self, session_id: str) -> bool:
        """Terminate a specific session."""
        wrapper = self._sessions.get(session_id)
        if wrapper:
            wrapper.stop()
            del self._sessions[session_id]
            if session_id in self._session_metadata:
                 del self._session_metadata[session_id]
            self.logger.info(f"Killed session {session_id}")
            return True
        return False

    def shutdown_all(self):
        """Terminate all sessions."""
        for sid in list(self._sessions.keys()):
            self.kill_session(sid)
