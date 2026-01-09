"""
Audio stream processor for real-time voice interaction.

Handles:
- Audio chunk buffering and resampling
- VAD-based utterance detection
- STT integration
- Turn-taking management
"""

import asyncio
import numpy as np
from typing import Optional, Callable, Awaitable
from dataclasses import dataclass, field
import logging
import time

from .vad import VoiceActivityDetector, VADConfig

logger = logging.getLogger(__name__)


@dataclass
class ProcessorConfig:
    """Audio processor configuration."""
    # Audio format
    sample_rate: int = 16000
    channels: int = 1
    
    # VAD settings
    vad_config: VADConfig = field(default_factory=VADConfig)
    
    # STT settings  
    stt_model: str = "base.en"
    stt_device: str = "cpu"
    
    # Processing
    min_audio_length: float = 0.5  # Minimum seconds to process
    max_pending_duration: float = 60.0  # Max buffered audio before force-process


class AudioStreamProcessor:
    """
    Processes streaming audio for voice interaction.
    
    Integrates VAD, STT, and callback handling for complete
    utterance processing.
    
    Usage:
        async def handle_transcript(text: str, audio: np.ndarray):
            print(f"User said: {text}")
            return "I heard you!"  # TTS response
        
        processor = AudioStreamProcessor(
            on_transcript=handle_transcript
        )
        
        # Feed audio chunks
        for chunk in audio_stream:
            await processor.feed(chunk)
    """
    
    def __init__(
        self,
        on_transcript: Optional[Callable[[str, np.ndarray], Awaitable[Optional[str]]]] = None,
        on_speech_start: Optional[Callable[[], Awaitable[None]]] = None,
        on_speech_end: Optional[Callable[[], Awaitable[None]]] = None,
        config: Optional[ProcessorConfig] = None,
    ):
        """
        Initialize the audio processor.
        
        Args:
            on_transcript: Async callback when speech is transcribed.
                          Receives (text, audio). Return string for TTS response.
            on_speech_start: Async callback when speech begins
            on_speech_end: Async callback when speech ends (before STT)
            config: Processor configuration
        """
        self.config = config or ProcessorConfig()
        self.on_transcript = on_transcript
        self.on_speech_start = on_speech_start
        self.on_speech_end = on_speech_end
        
        # VAD
        self.vad = VoiceActivityDetector(
            config=self.config.vad_config,
            backend="silero"
        )
        
        # STT (lazy loaded)
        self._stt = None
        
        # State
        self._is_processing = False
        self._last_transcript: Optional[str] = None
        self._stats = ProcessorStats()
    
    @property
    def stt(self):
        """Lazy-load STT model."""
        if self._stt is None:
            from ..stt import FasterWhisperSTT
            logger.info(f"Loading STT model: {self.config.stt_model}")
            self._stt = FasterWhisperSTT(
                model_size=self.config.stt_model,
                device=self.config.stt_device,
            )
        return self._stt
    
    async def feed(self, audio_chunk: np.ndarray) -> Optional[str]:
        """
        Feed an audio chunk into the processor.
        
        Args:
            audio_chunk: Audio data (float32, 16kHz, mono)
            
        Returns:
            Transcript if utterance completed, None otherwise
        """
        self._stats.chunks_received += 1
        
        # Process through VAD
        result = self.vad.process(audio_chunk)
        
        # Handle state transitions
        if result.is_speech_start:
            self._stats.utterances_started += 1
            if self.on_speech_start:
                await self.on_speech_start()
        
        if result.is_speech_end:
            if self.on_speech_end:
                await self.on_speech_end()
            
            # Get complete utterance and transcribe
            return await self._process_utterance()
        
        return None
    
    async def _process_utterance(self) -> Optional[str]:
        """Process a complete utterance through STT."""
        audio = self.vad.get_utterance()
        
        if audio is None or len(audio) == 0:
            return None
        
        # Check minimum length
        duration = len(audio) / self.config.sample_rate
        if duration < self.config.min_audio_length:
            logger.debug(f"Audio too short ({duration:.2f}s), skipping")
            return None
        
        self._is_processing = True
        start_time = time.time()
        
        try:
            # Run STT in thread pool to not block
            loop = asyncio.get_event_loop()
            transcript = await loop.run_in_executor(
                None,
                self.stt.transcribe,
                audio
            )
            
            elapsed = time.time() - start_time
            self._stats.transcriptions += 1
            self._stats.total_stt_time += elapsed
            
            logger.info(f"Transcribed ({duration:.1f}s audio in {elapsed:.2f}s): {transcript}")
            
            if transcript and transcript.strip():
                self._last_transcript = transcript
                
                # Call handler
                if self.on_transcript:
                    response = await self.on_transcript(transcript, audio)
                    return response
                
                return transcript
            
            return None
            
        finally:
            self._is_processing = False
    
    async def flush(self) -> Optional[str]:
        """
        Force process any buffered audio.
        
        Useful when stream ends or for interruption handling.
        """
        # Simulate speech end to trigger processing
        audio = self.vad.get_utterance()
        if audio is not None and len(audio) > 0:
            # Put it back and process
            self.vad._audio_buffer = [audio]
            return await self._process_utterance()
        return None
    
    def reset(self):
        """Reset processor state."""
        self.vad.reset()
        self._is_processing = False
        self._last_transcript = None
    
    @property
    def is_processing(self) -> bool:
        """Whether currently processing an utterance."""
        return self._is_processing
    
    @property
    def stats(self) -> "ProcessorStats":
        """Get processing statistics."""
        return self._stats


@dataclass
class ProcessorStats:
    """Processing statistics."""
    chunks_received: int = 0
    utterances_started: int = 0
    transcriptions: int = 0
    total_stt_time: float = 0.0
    
    @property
    def avg_stt_time(self) -> float:
        """Average STT processing time."""
        if self.transcriptions == 0:
            return 0.0
        return self.total_stt_time / self.transcriptions


class ResamplingBuffer:
    """
    Buffer that handles audio resampling.
    
    Useful when input sample rate differs from processing rate.
    """
    
    def __init__(
        self,
        input_rate: int,
        output_rate: int = 16000,
        channels: int = 1
    ):
        self.input_rate = input_rate
        self.output_rate = output_rate
        self.channels = channels
        self._buffer: list[np.ndarray] = []
    
    def write(self, audio: np.ndarray) -> np.ndarray:
        """
        Write audio and get resampled output.
        
        Args:
            audio: Input audio at input_rate
            
        Returns:
            Resampled audio at output_rate
        """
        if self.input_rate == self.output_rate:
            return audio
        
        # Simple resampling using numpy interp
        # For production, use librosa or scipy.signal.resample
        input_samples = len(audio)
        output_samples = int(input_samples * self.output_rate / self.input_rate)
        
        x_old = np.linspace(0, 1, input_samples)
        x_new = np.linspace(0, 1, output_samples)
        
        resampled = np.interp(x_new, x_old, audio).astype(np.float32)
        return resampled
