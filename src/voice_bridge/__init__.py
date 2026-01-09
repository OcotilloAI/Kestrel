"""
Voice Bridge - WebRTC streaming audio for voice-driven interaction.

This module provides real-time bidirectional voice communication:
- Browser connects via WebRTC
- Audio streams to server
- VAD detects speech boundaries
- STT transcribes in real-time
- Responses streamed back as TTS audio
"""

from .server import VoiceBridgeServer
from .stream_processor import AudioStreamProcessor
from .vad import VoiceActivityDetector

__all__ = [
    "VoiceBridgeServer",
    "AudioStreamProcessor", 
    "VoiceActivityDetector",
]
