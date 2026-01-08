"""Tests for enhanced session capture (Phase 1)."""
import json
import tempfile
from pathlib import Path

import sys
sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from session_manager import SessionManager


class TestTypedEventRecording:
    """Test the new typed event recording methods."""

    def setup_method(self):
        self.tmpdir = tempfile.mkdtemp()
        self.sm = SessionManager(self.tmpdir)
        self.sid = self.sm.create_session()

    def test_record_stt_raw(self):
        self.sm.record_stt_raw(
            self.sid,
            "hello world",
            source="whisper",
            audio_duration_ms=1500,
            model="whisper-large-v3",
            confidence=0.95,
        )
        transcript = self.sm.get_transcript(self.sid)
        ev = transcript[-1]
        
        assert ev["type"] == "stt_raw"
        assert ev["source"] == "whisper"
        assert ev["content"] == "hello world"
        assert ev["meta"]["audio_duration_ms"] == 1500
        assert ev["meta"]["model"] == "whisper-large-v3"
        assert ev["meta"]["confidence"] == 0.95
        assert "ts" in ev

    def test_record_user_intent(self):
        self.sm.record_user_intent(
            self.sid,
            "Create a REST API endpoint",
            original_stt_ts="2026-01-08T00:00:00.000Z",
            clarification_needed=False,
            inferred_context=["project:kestrel"],
        )
        transcript = self.sm.get_transcript(self.sid)
        ev = transcript[-1]
        
        assert ev["type"] == "user_intent"
        assert ev["source"] == "controller"
        assert ev["content"] == "Create a REST API endpoint"
        assert ev["meta"]["original_stt_ts"] == "2026-01-08T00:00:00.000Z"
        assert ev["meta"]["inferred_context"] == ["project:kestrel"]

    def test_record_agent_stream(self):
        self.sm.record_agent_stream(
            self.sid,
            "Writing file src/api.py...",
            source="claude-code",
            stream="stdout",
            task_id="task_001",
            chunk_seq=1,
        )
        transcript = self.sm.get_transcript(self.sid)
        ev = transcript[-1]
        
        assert ev["type"] == "agent_stream"
        assert ev["source"] == "claude-code"
        assert ev["meta"]["stream"] == "stdout"
        assert ev["meta"]["task_id"] == "task_001"
        assert ev["meta"]["chunk_seq"] == 1

    def test_record_tool_call(self):
        self.sm.record_tool_call(
            self.sid,
            tool_name="write_file",
            arguments='{"path": "test.py", "content": "print(1)"}',
            call_id="call_001",
            task_id="task_001",
        )
        transcript = self.sm.get_transcript(self.sid)
        ev = transcript[-1]
        
        assert ev["type"] == "tool_call"
        assert ev["meta"]["tool_name"] == "write_file"
        assert ev["meta"]["call_id"] == "call_001"

    def test_record_tool_result(self):
        self.sm.record_tool_result(
            self.sid,
            tool_name="write_file",
            result="File written successfully",
            call_id="call_001",
            success=True,
            duration_ms=45,
        )
        transcript = self.sm.get_transcript(self.sid)
        ev = transcript[-1]
        
        assert ev["type"] == "tool_result"
        assert ev["meta"]["success"] is True
        assert ev["meta"]["duration_ms"] == 45

    def test_record_summary(self):
        self.sm.record_summary(
            self.sid,
            "I created the API endpoint. Next: add tests.",
            task_id="task_001",
            files_changed=["src/api.py", "src/routes.py"],
            tts_voice="nova",
        )
        transcript = self.sm.get_transcript(self.sid)
        ev = transcript[-1]
        
        assert ev["type"] == "summary"
        assert ev["source"] == "summarizer"
        assert ev["meta"]["files_changed"] == ["src/api.py", "src/routes.py"]
        assert ev["meta"]["tts_voice"] == "nova"

    def test_record_system_event(self):
        self.sm.record_system_event(
            self.sid,
            "Session resumed from checkpoint",
            event_type="session_resumed",
            severity="info",
        )
        transcript = self.sm.get_transcript(self.sid)
        ev = transcript[-1]
        
        assert ev["type"] == "system"
        assert ev["meta"]["event"] == "session_resumed"
        assert ev["meta"]["severity"] == "info"

    def test_full_interaction_flow(self):
        """Test a complete interaction: STT → intent → tool → summary."""
        # User speaks
        self.sm.record_stt_raw(self.sid, "add a health check endpoint", source="whisper")
        
        # Controller interprets
        self.sm.record_user_intent(self.sid, "Add /health endpoint returning {status: ok}")
        
        # Coder calls tool
        self.sm.record_tool_call(
            self.sid,
            tool_name="write_file",
            arguments='{"path": "src/health.py"}',
            call_id="c1",
        )
        
        # Tool responds
        self.sm.record_tool_result(self.sid, "write_file", "OK", call_id="c1", success=True)
        
        # Summarizer speaks result
        self.sm.record_summary(
            self.sid,
            "Added health check endpoint at /health. Next: test it.",
            files_changed=["src/health.py"],
        )
        
        transcript = self.sm.get_transcript(self.sid)
        assert len(transcript) == 5
        assert [e["type"] for e in transcript] == [
            "stt_raw", "user_intent", "tool_call", "tool_result", "summary"
        ]

    def test_jsonl_persistence(self):
        """Verify events are persisted to JSONL file."""
        self.sm.record_stt_raw(self.sid, "test persistence", source="browser_stt")
        
        # Read raw file
        path = self.sm._transcript_paths[self.sid]
        assert path.exists()
        
        with open(path) as f:
            lines = f.readlines()
        
        assert len(lines) >= 1
        ev = json.loads(lines[-1])
        assert ev["type"] == "stt_raw"
        assert "body_b64" in ev  # Content is base64 encoded
        assert "ts" in ev


if __name__ == "__main__":
    import pytest
    pytest.main([__file__, "-v"])
