"""
Voice Activity Detection (VAD) for speech boundary detection.

Supports multiple backends:
- Silero VAD (neural, most accurate)
- WebRTC VAD (lightweight)
- RMS-based (simple fallback)
"""

import numpy as np
from typing import Optional, Literal
from dataclasses import dataclass
import logging

logger = logging.getLogger(__name__)


@dataclass
class VADConfig:
    """VAD configuration."""
    # Detection thresholds
    speech_threshold: float = 0.5  # Silero probability threshold
    silence_threshold: float = 0.3  # Below this = silence
    
    # Timing (in seconds)
    min_speech_duration: float = 0.25  # Minimum speech to trigger
    min_silence_duration: float = 0.7  # Silence before end-of-utterance
    max_speech_duration: float = 30.0  # Force end after this long
    
    # Audio format
    sample_rate: int = 16000
    frame_duration_ms: int = 30  # Frame size for VAD


class VoiceActivityDetector:
    """
    Detects voice activity in audio streams.
    
    Usage:
        vad = VoiceActivityDetector()
        
        for chunk in audio_stream:
            result = vad.process(chunk)
            if result.is_speech_end:
                # Complete utterance available
                audio = vad.get_utterance()
    """
    
    def __init__(
        self,
        config: Optional[VADConfig] = None,
        backend: Literal["silero", "webrtc", "rms"] = "silero"
    ):
        self.config = config or VADConfig()
        self.backend = backend
        
        # State
        self._audio_buffer: list[np.ndarray] = []
        self._is_speaking = False
        self._speech_start_time: Optional[float] = None
        self._silence_start_time: Optional[float] = None
        self._current_time: float = 0.0
        
        # Backend-specific setup
        self._vad_model = None
        self._init_backend()
    
    def _init_backend(self):
        """Initialize the VAD backend."""
        if self.backend == "silero":
            try:
                import torch
                model, utils = torch.hub.load(
                    repo_or_dir='snakers4/silero-vad',
                    model='silero_vad',
                    force_reload=False,
                    trust_repo=True
                )
                self._vad_model = model
                self._get_speech_timestamps = utils[0]
                logger.info("Silero VAD loaded")
            except Exception as e:
                logger.warning(f"Failed to load Silero VAD: {e}, falling back to RMS")
                self.backend = "rms"
                
        elif self.backend == "webrtc":
            try:
                import webrtcvad
                self._vad_model = webrtcvad.Vad(3)  # Aggressiveness 0-3
                logger.info("WebRTC VAD loaded")
            except ImportError:
                logger.warning("webrtcvad not installed, falling back to RMS")
                self.backend = "rms"
    
    def process(self, audio_chunk: np.ndarray) -> "VADResult":
        """
        Process an audio chunk and detect speech boundaries.
        
        Args:
            audio_chunk: Audio data as float32 numpy array, 16kHz mono
            
        Returns:
            VADResult with speech state information
        """
        # Ensure correct format
        if audio_chunk.dtype != np.float32:
            audio_chunk = audio_chunk.astype(np.float32)
        
        # Normalize if needed
        if np.abs(audio_chunk).max() > 1.0:
            audio_chunk = audio_chunk / 32768.0
        
        # Calculate time
        chunk_duration = len(audio_chunk) / self.config.sample_rate
        self._current_time += chunk_duration
        
        # Detect speech
        is_speech = self._detect_speech(audio_chunk)
        
        # State machine
        result = VADResult(
            is_speech=is_speech,
            is_speech_start=False,
            is_speech_end=False,
            speech_probability=0.0,
        )
        
        if is_speech:
            self._audio_buffer.append(audio_chunk)
            self._silence_start_time = None
            
            if not self._is_speaking:
                # Speech started
                self._is_speaking = True
                self._speech_start_time = self._current_time
                result.is_speech_start = True
                logger.debug("Speech started")
            
            # Check max duration
            if self._speech_start_time:
                speech_duration = self._current_time - self._speech_start_time
                if speech_duration >= self.config.max_speech_duration:
                    result.is_speech_end = True
                    logger.debug(f"Speech ended (max duration: {speech_duration:.1f}s)")
        else:
            if self._is_speaking:
                # In silence after speech
                self._audio_buffer.append(audio_chunk)  # Keep some trailing silence
                
                if self._silence_start_time is None:
                    self._silence_start_time = self._current_time
                
                silence_duration = self._current_time - self._silence_start_time
                if silence_duration >= self.config.min_silence_duration:
                    # Check minimum speech duration
                    if self._speech_start_time:
                        speech_duration = self._silence_start_time - self._speech_start_time
                        if speech_duration >= self.config.min_speech_duration:
                            result.is_speech_end = True
                            logger.debug(f"Speech ended (silence: {silence_duration:.1f}s)")
                        else:
                            # Too short, reset
                            logger.debug(f"Speech too short ({speech_duration:.2f}s), ignoring")
                            self._reset_state()
        
        return result
    
    def _detect_speech(self, audio_chunk: np.ndarray) -> bool:
        """Detect if chunk contains speech using configured backend."""
        if self.backend == "silero":
            return self._detect_silero(audio_chunk)
        elif self.backend == "webrtc":
            return self._detect_webrtc(audio_chunk)
        else:
            return self._detect_rms(audio_chunk)
    
    def _detect_silero(self, audio_chunk: np.ndarray) -> bool:
        """Detect speech using Silero VAD."""
        import torch
        
        # Silero expects specific chunk sizes (256, 512, or 768 samples for 16kHz)
        # Process in 512-sample windows
        window_size = 512
        
        if len(audio_chunk) < window_size:
            # Pad short chunks
            audio_chunk = np.pad(audio_chunk, (0, window_size - len(audio_chunk)))
        
        # Take first window
        window = audio_chunk[:window_size]
        tensor = torch.from_numpy(window)
        
        prob = self._vad_model(tensor, self.config.sample_rate).item()
        return prob >= self.config.speech_threshold
    
    def _detect_webrtc(self, audio_chunk: np.ndarray) -> bool:
        """Detect speech using WebRTC VAD."""
        # WebRTC VAD expects 16-bit PCM
        audio_int16 = (audio_chunk * 32767).astype(np.int16)
        
        # Process in 30ms frames
        frame_size = int(self.config.sample_rate * self.config.frame_duration_ms / 1000)
        
        # Check if any frame has speech
        for i in range(0, len(audio_int16) - frame_size + 1, frame_size):
            frame = audio_int16[i:i + frame_size].tobytes()
            if self._vad_model.is_speech(frame, self.config.sample_rate):
                return True
        return False
    
    def _detect_rms(self, audio_chunk: np.ndarray, threshold: float = 0.02) -> bool:
        """Simple RMS-based speech detection."""
        rms = np.sqrt(np.mean(audio_chunk ** 2))
        return rms > threshold
    
    def get_utterance(self) -> Optional[np.ndarray]:
        """
        Get the complete utterance audio and reset state.
        
        Returns:
            Concatenated audio buffer as numpy array, or None if empty
        """
        if not self._audio_buffer:
            return None
        
        audio = np.concatenate(self._audio_buffer)
        self._reset_state()
        return audio
    
    def _reset_state(self):
        """Reset internal state for new utterance."""
        self._audio_buffer = []
        self._is_speaking = False
        self._speech_start_time = None
        self._silence_start_time = None
    
    def reset(self):
        """Full reset including time."""
        self._reset_state()
        self._current_time = 0.0


@dataclass
class VADResult:
    """Result of VAD processing."""
    is_speech: bool  # Current chunk contains speech
    is_speech_start: bool  # Speech just started
    is_speech_end: bool  # Speech just ended (utterance complete)
    speech_probability: float  # Backend-specific probability
