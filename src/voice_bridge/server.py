"""
WebRTC Voice Bridge Server.

Handles WebRTC signaling and audio streaming for real-time voice interaction.
Uses aiortc for WebRTC implementation.
"""

import asyncio
import json
import logging
import uuid
from typing import Optional, Callable, Awaitable, Dict, Any
from dataclasses import dataclass, field
import numpy as np
import time

from fastapi import FastAPI, WebSocket, WebSocketDisconnect, HTTPException
from fastapi.responses import HTMLResponse, JSONResponse
from pydantic import BaseModel

logger = logging.getLogger(__name__)


# Check for aiortc availability
try:
    from aiortc import RTCPeerConnection, RTCSessionDescription, MediaStreamTrack
    from aiortc.contrib.media import MediaRelay
    from av import AudioFrame
    AIORTC_AVAILABLE = True
except ImportError:
    AIORTC_AVAILABLE = False
    logger.warning("aiortc not installed - WebRTC features disabled")


@dataclass
class VoiceBridgeConfig:
    """Voice bridge configuration."""
    # Audio settings
    sample_rate: int = 16000
    channels: int = 1
    
    # STT settings
    stt_model: str = "base.en"
    stt_device: str = "cpu"
    
    # TTS settings
    tts_enabled: bool = True
    tts_voice: str = "default"
    
    # Connection settings
    ice_servers: list = field(default_factory=lambda: [
        {"urls": ["stun:stun.l.google.com:19302"]}
    ])
    
    # Timeouts
    connection_timeout: float = 30.0
    idle_timeout: float = 300.0  # 5 minutes


class VoiceBridgeSession:
    """
    Represents an active voice bridge session.
    
    Each browser connection gets its own session with:
    - WebRTC peer connection
    - Audio processor
    - Transcript history
    """
    
    def __init__(
        self,
        session_id: str,
        config: VoiceBridgeConfig,
        on_transcript: Optional[Callable[[str, str, np.ndarray], Awaitable[Optional[str]]]] = None,
    ):
        self.session_id = session_id
        self.config = config
        self.on_transcript = on_transcript
        
        self.pc: Optional["RTCPeerConnection"] = None
        self.data_channel = None
        self.audio_track = None
        
        self.created_at = time.time()
        self.last_activity = time.time()
        self.transcript_history: list[dict] = []
        
        self._audio_processor = None
        self._closed = False
    
    @property
    def audio_processor(self):
        """Lazy-load audio processor."""
        if self._audio_processor is None:
            from .stream_processor import AudioStreamProcessor, ProcessorConfig
            from .vad import VADConfig
            
            self._audio_processor = AudioStreamProcessor(
                on_transcript=self._handle_transcript,
                on_speech_start=self._on_speech_start,
                on_speech_end=self._on_speech_end,
                config=ProcessorConfig(
                    sample_rate=self.config.sample_rate,
                    stt_model=self.config.stt_model,
                    stt_device=self.config.stt_device,
                    vad_config=VADConfig(
                        sample_rate=self.config.sample_rate,
                    ),
                ),
            )
        return self._audio_processor
    
    async def _handle_transcript(self, text: str, audio: np.ndarray) -> Optional[str]:
        """Handle transcribed speech."""
        self.last_activity = time.time()
        
        # Record in history
        self.transcript_history.append({
            "role": "user",
            "text": text,
            "timestamp": time.time(),
        })
        
        # Send transcript to client via data channel
        if self.data_channel and self.data_channel.readyState == "open":
            self.data_channel.send(json.dumps({
                "type": "transcript",
                "text": text,
                "final": True,
            }))
        
        # Call external handler
        response = None
        if self.on_transcript:
            response = await self.on_transcript(self.session_id, text, audio)
        
        if response:
            self.transcript_history.append({
                "role": "assistant",
                "text": response,
                "timestamp": time.time(),
            })
            
            # Send response to client
            if self.data_channel and self.data_channel.readyState == "open":
                self.data_channel.send(json.dumps({
                    "type": "response",
                    "text": response,
                }))
            
            # TODO: Generate TTS and stream back
        
        return response
    
    async def _on_speech_start(self):
        """Called when speech starts."""
        if self.data_channel and self.data_channel.readyState == "open":
            self.data_channel.send(json.dumps({
                "type": "speech_start",
            }))
    
    async def _on_speech_end(self):
        """Called when speech ends (before STT)."""
        if self.data_channel and self.data_channel.readyState == "open":
            self.data_channel.send(json.dumps({
                "type": "speech_end",
                "processing": True,
            }))
    
    async def close(self):
        """Close the session."""
        if self._closed:
            return
        
        self._closed = True
        
        if self.pc:
            await self.pc.close()
        
        logger.info(f"Session {self.session_id} closed")


class VoiceBridgeServer:
    """
    WebRTC voice bridge server.
    
    Provides HTTP endpoints for WebRTC signaling and manages
    voice sessions.
    
    Usage:
        async def handle_transcript(session_id, text, audio):
            # Process with your agent
            return "I heard: " + text
        
        server = VoiceBridgeServer(on_transcript=handle_transcript)
        server.mount(app, prefix="/voice")
    """
    
    def __init__(
        self,
        on_transcript: Optional[Callable[[str, str, np.ndarray], Awaitable[Optional[str]]]] = None,
        config: Optional[VoiceBridgeConfig] = None,
    ):
        """
        Initialize the voice bridge server.
        
        Args:
            on_transcript: Callback for transcribed speech.
                          Receives (session_id, text, audio_array).
                          Return string for TTS response.
            config: Server configuration
        """
        self.config = config or VoiceBridgeConfig()
        self.on_transcript = on_transcript
        
        self.sessions: Dict[str, VoiceBridgeSession] = {}
        self._relay = MediaRelay() if AIORTC_AVAILABLE else None
    
    def mount(self, app: FastAPI, prefix: str = "/voice"):
        """
        Mount voice bridge routes on a FastAPI app.
        
        Adds:
        - POST {prefix}/offer - WebRTC offer/answer
        - GET {prefix}/session/{id} - Session info
        - DELETE {prefix}/session/{id} - Close session
        - GET {prefix}/client - Test client HTML
        """
        
        @app.post(f"{prefix}/offer")
        async def webrtc_offer(request: dict):
            """Handle WebRTC offer and return answer."""
            if not AIORTC_AVAILABLE:
                raise HTTPException(500, "aiortc not installed")
            
            return await self._handle_offer(request)
        
        @app.get(f"{prefix}/session/{{session_id}}")
        async def get_session(session_id: str):
            """Get session information."""
            session = self.sessions.get(session_id)
            if not session:
                raise HTTPException(404, "Session not found")
            
            return {
                "session_id": session_id,
                "created_at": session.created_at,
                "last_activity": session.last_activity,
                "transcript_count": len(session.transcript_history),
            }
        
        @app.delete(f"{prefix}/session/{{session_id}}")
        async def close_session(session_id: str):
            """Close a session."""
            session = self.sessions.pop(session_id, None)
            if session:
                await session.close()
                return {"status": "closed"}
            raise HTTPException(404, "Session not found")
        
        @app.get(f"{prefix}/client", response_class=HTMLResponse)
        async def test_client():
            """Serve test client HTML."""
            return self._get_client_html()
        
        @app.get(f"{prefix}/status")
        async def status():
            """Get server status."""
            return {
                "aiortc_available": AIORTC_AVAILABLE,
                "active_sessions": len(self.sessions),
                "config": {
                    "sample_rate": self.config.sample_rate,
                    "stt_model": self.config.stt_model,
                    "tts_enabled": self.config.tts_enabled,
                },
            }
    
    async def _handle_offer(self, request: dict) -> dict:
        """Handle WebRTC offer and create answer."""
        offer = RTCSessionDescription(
            sdp=request["sdp"],
            type=request["type"]
        )
        
        # Create session
        session_id = str(uuid.uuid4())[:8]
        session = VoiceBridgeSession(
            session_id=session_id,
            config=self.config,
            on_transcript=self.on_transcript,
        )
        
        # Create peer connection
        pc = RTCPeerConnection(configuration={
            "iceServers": self.config.ice_servers
        })
        session.pc = pc
        
        @pc.on("connectionstatechange")
        async def on_connectionstatechange():
            logger.info(f"Session {session_id} connection state: {pc.connectionState}")
            if pc.connectionState in ("failed", "closed"):
                await self._cleanup_session(session_id)
        
        @pc.on("track")
        def on_track(track: MediaStreamTrack):
            logger.info(f"Session {session_id} received track: {track.kind}")
            
            if track.kind == "audio":
                session.audio_track = track
                # Start processing audio
                asyncio.create_task(self._process_audio_track(session, track))
        
        @pc.on("datachannel")
        def on_datachannel(channel):
            logger.info(f"Session {session_id} data channel: {channel.label}")
            session.data_channel = channel
            
            @channel.on("message")
            def on_message(message):
                logger.debug(f"Session {session_id} received: {message}")
        
        # Set remote description and create answer
        await pc.setRemoteDescription(offer)
        answer = await pc.createAnswer()
        await pc.setLocalDescription(answer)
        
        self.sessions[session_id] = session
        logger.info(f"Created session {session_id}")
        
        return {
            "session_id": session_id,
            "sdp": pc.localDescription.sdp,
            "type": pc.localDescription.type,
        }
    
    async def _process_audio_track(
        self,
        session: VoiceBridgeSession,
        track: "MediaStreamTrack"
    ):
        """Process incoming audio track."""
        logger.info(f"Starting audio processing for session {session.session_id}")
        
        try:
            while True:
                try:
                    frame: AudioFrame = await asyncio.wait_for(
                        track.recv(),
                        timeout=5.0
                    )
                except asyncio.TimeoutError:
                    # Check if session still active
                    if session._closed:
                        break
                    continue
                
                # Convert frame to numpy array
                # aiortc AudioFrame is in s16 format by default
                audio_data = frame.to_ndarray()
                
                # Convert to float32 and normalize
                if audio_data.dtype == np.int16:
                    audio_data = audio_data.astype(np.float32) / 32768.0
                
                # Handle stereo -> mono
                if len(audio_data.shape) > 1 and audio_data.shape[0] > 1:
                    audio_data = np.mean(audio_data, axis=0)
                
                audio_data = audio_data.flatten()
                
                # Resample if needed (aiortc typically gives 48kHz)
                if frame.sample_rate != session.config.sample_rate:
                    # Simple resampling
                    ratio = session.config.sample_rate / frame.sample_rate
                    new_length = int(len(audio_data) * ratio)
                    audio_data = np.interp(
                        np.linspace(0, len(audio_data), new_length),
                        np.arange(len(audio_data)),
                        audio_data
                    ).astype(np.float32)
                
                # Feed to processor
                await session.audio_processor.feed(audio_data)
                
        except Exception as e:
            logger.error(f"Audio processing error for {session.session_id}: {e}")
        
        logger.info(f"Audio processing ended for session {session.session_id}")
    
    async def _cleanup_session(self, session_id: str):
        """Clean up a session."""
        session = self.sessions.pop(session_id, None)
        if session:
            await session.close()
    
    def _get_client_html(self) -> str:
        """Get the test client HTML."""
        # Load from file if exists, otherwise return embedded
        try:
            import os
            client_path = os.path.join(
                os.path.dirname(__file__),
                "client",
                "index.html"
            )
            with open(client_path) as f:
                return f.read()
        except FileNotFoundError:
            return self._embedded_client_html()
    
    def _embedded_client_html(self) -> str:
        """Embedded minimal test client."""
        return """
<!DOCTYPE html>
<html>
<head>
    <title>Voice Bridge Test</title>
    <style>
        body { font-family: system-ui; max-width: 800px; margin: 2em auto; padding: 0 1em; }
        button { padding: 1em 2em; font-size: 1.1em; margin: 0.5em; }
        #status { padding: 1em; background: #f0f0f0; border-radius: 8px; margin: 1em 0; }
        #transcript { min-height: 200px; border: 1px solid #ccc; padding: 1em; border-radius: 8px; }
        .user { color: blue; }
        .assistant { color: green; }
        .system { color: gray; font-style: italic; }
    </style>
</head>
<body>
    <h1>🎤 Voice Bridge Test</h1>
    
    <div id="status">Click Connect to start</div>
    
    <div>
        <button id="connectBtn" onclick="connect()">Connect</button>
        <button id="disconnectBtn" onclick="disconnect()" disabled>Disconnect</button>
    </div>
    
    <h2>Transcript</h2>
    <div id="transcript"></div>
    
    <script>
        let pc = null;
        let dc = null;
        let localStream = null;
        
        function log(msg, cls = 'system') {
            const div = document.getElementById('transcript');
            const p = document.createElement('p');
            p.className = cls;
            p.textContent = msg;
            div.appendChild(p);
            div.scrollTop = div.scrollHeight;
        }
        
        function setStatus(msg) {
            document.getElementById('status').textContent = msg;
        }
        
        async function connect() {
            try {
                setStatus('Requesting microphone...');
                localStream = await navigator.mediaDevices.getUserMedia({ 
                    audio: {
                        echoCancellation: true,
                        noiseSuppression: true,
                        sampleRate: 16000
                    } 
                });
                
                setStatus('Creating peer connection...');
                pc = new RTCPeerConnection({
                    iceServers: [{ urls: 'stun:stun.l.google.com:19302' }]
                });
                
                // Add audio track
                localStream.getTracks().forEach(track => {
                    pc.addTrack(track, localStream);
                });
                
                // Create data channel
                dc = pc.createDataChannel('control');
                dc.onopen = () => log('Data channel opened');
                dc.onmessage = (e) => {
                    const msg = JSON.parse(e.data);
                    if (msg.type === 'transcript') {
                        log('You: ' + msg.text, 'user');
                    } else if (msg.type === 'response') {
                        log('Assistant: ' + msg.text, 'assistant');
                    } else if (msg.type === 'speech_start') {
                        setStatus('🎤 Listening...');
                    } else if (msg.type === 'speech_end') {
                        setStatus('⏳ Processing...');
                    }
                };
                
                pc.onconnectionstatechange = () => {
                    setStatus('Connection: ' + pc.connectionState);
                    if (pc.connectionState === 'connected') {
                        setStatus('🟢 Connected - Speak now!');
                    }
                };
                
                // Create offer
                const offer = await pc.createOffer();
                await pc.setLocalDescription(offer);
                
                // Wait for ICE gathering
                await new Promise(resolve => {
                    if (pc.iceGatheringState === 'complete') {
                        resolve();
                    } else {
                        pc.onicegatheringstatechange = () => {
                            if (pc.iceGatheringState === 'complete') resolve();
                        };
                    }
                });
                
                setStatus('Sending offer...');
                
                // Send to server
                const response = await fetch('/voice/offer', {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify({
                        sdp: pc.localDescription.sdp,
                        type: pc.localDescription.type
                    })
                });
                
                const answer = await response.json();
                log('Session: ' + answer.session_id);
                
                await pc.setRemoteDescription({
                    sdp: answer.sdp,
                    type: answer.type
                });
                
                document.getElementById('connectBtn').disabled = true;
                document.getElementById('disconnectBtn').disabled = false;
                
            } catch (err) {
                setStatus('Error: ' + err.message);
                console.error(err);
            }
        }
        
        function disconnect() {
            if (pc) {
                pc.close();
                pc = null;
            }
            if (localStream) {
                localStream.getTracks().forEach(t => t.stop());
                localStream = null;
            }
            dc = null;
            
            document.getElementById('connectBtn').disabled = false;
            document.getElementById('disconnectBtn').disabled = true;
            setStatus('Disconnected');
            log('Disconnected');
        }
    </script>
</body>
</html>
"""
