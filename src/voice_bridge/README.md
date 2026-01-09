# Voice Bridge

Real-time WebRTC voice communication for Kestrel.

## Architecture

```
┌─────────────┐         WebRTC          ┌─────────────────┐
│   Browser   │◄───────────────────────►│  Voice Bridge   │
│  (Client)   │  Audio + Data Channel   │    (Server)     │
└─────────────┘                         └────────┬────────┘
                                                 │
                                    ┌────────────┼────────────┐
                                    ▼            ▼            ▼
                              ┌─────────┐  ┌─────────┐  ┌─────────┐
                              │   VAD   │  │   STT   │  │   TTS   │
                              │ (silero)│  │(whisper)│  │ (piper) │
                              └─────────┘  └─────────┘  └─────────┘
```

## Components

### VoiceBridgeServer (`server.py`)
WebRTC signaling and media server. Handles:
- ICE candidate exchange
- SDP offer/answer negotiation
- Audio track reception/transmission
- Data channel for transcripts & control

### AudioStreamProcessor (`stream_processor.py`)
Processes incoming audio streams:
- Buffers audio chunks
- Integrates with VAD for utterance detection
- Feeds complete utterances to STT
- Manages turn-taking

### VoiceActivityDetector (`vad.py`)
Detects speech vs silence:
- Silero VAD (neural, accurate)
- Fallback: WebRTC VAD or RMS-based

## Usage

```python
from voice_bridge import VoiceBridgeServer

async def on_transcript(session_id: str, text: str):
    """Called when speech is transcribed."""
    print(f"[{session_id}] User said: {text}")
    # Process with Kestrel, return response
    return "I heard you say: " + text

server = VoiceBridgeServer(
    on_transcript=on_transcript,
    stt_model="base.en",
    tts_enabled=True,
)

# Add routes to existing FastAPI app
server.mount(app, prefix="/voice")
```

## Client

The `client/` directory contains a test web UI:
- Microphone access via getUserMedia
- WebRTC peer connection
- Real-time transcript display
- Audio playback for TTS responses

## Dependencies

```
aiortc          # WebRTC for Python
silero-vad      # Voice activity detection
faster-whisper  # Speech-to-text
piper-tts       # Text-to-speech (optional)
```

## Quick Start

```bash
# Install dependencies
pip install aiortc av numpy faster-whisper

# For Silero VAD (recommended)
pip install torch

# Run standalone test server
cd /path/to/Kestrel
python -m src.voice_bridge.standalone
```

Then open http://localhost:8765/voice/client

## Integration with Kestrel

```python
# In your main server.py
from voice_bridge import VoiceBridgeServer

voice_bridge = VoiceBridgeServer(
    on_transcript=handle_voice_transcript
)
voice_bridge.mount(app, prefix="/voice")

async def handle_voice_transcript(session_id: str, text: str, audio: np.ndarray):
    # Route to Kestrel task processing
    # Return response for TTS
    return f"Working on: {text}"
```

## Status

🚧 **In Development**

- [x] WebRTC signaling server
- [x] Audio stream processing  
- [x] VAD integration (Silero/WebRTC/RMS)
- [x] STT via faster-whisper
- [ ] TTS response streaming
- [x] Browser test client

## Next Steps

1. **Test basic flow:** Connect browser, speak, see transcripts
2. **Integrate with Kestrel sessions:** Route transcripts to task execution
3. **Add TTS streaming:** Send audio responses back to browser
4. **Production hardening:** Error handling, reconnection, metrics
