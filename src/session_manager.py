import uuid
import logging
import os
import shutil
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
        Create a new Goose session.
        """
        session_id = str(uuid.uuid4())
        session_name = generate_name()
        
        # Determine actual working directory
        if cwd:
            final_cwd = Path(cwd)
            # If using a shared CWD, the name is just the directory name
            session_name = final_cwd.name
        else:
            final_cwd = self.sessions_dir / session_id
        
        # Ensure directory exists
        if not final_cwd.exists():
            final_cwd.mkdir(parents=True, exist_ok=True)
            
            # Handle cloning if requested and directory was just created
            if copy_from_path:
                source_path = Path(copy_from_path)
                if source_path.exists() and source_path.is_dir():
                    self.logger.info(f"Cloning session files from {source_path} to {final_cwd}")
                    self._copy_contents(source_path, final_cwd)

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
