"""
Standalone Voice Bridge server for testing.

Run with:
    python -m src.voice_bridge.standalone

Then open http://localhost:8765/voice/client
"""

import asyncio
import logging
import numpy as np
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
import uvicorn

from .server import VoiceBridgeServer, VoiceBridgeConfig

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


# Create FastAPI app
app = FastAPI(
    title="Voice Bridge",
    description="WebRTC voice interface for Kestrel",
    version="0.1.0",
)

# CORS for browser access
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


async def handle_transcript(session_id: str, text: str, audio: np.ndarray) -> str:
    """
    Handle transcribed speech.
    
    This is where you'd integrate with Kestrel's task system.
    For now, just echo back.
    """
    logger.info(f"[{session_id}] User said: {text}")
    
    # Simple echo response
    response = f"I heard you say: {text}"
    
    # TODO: Integrate with Kestrel
    # - Create task from transcript
    # - Execute via agent
    # - Return summary
    
    return response


# Create and mount voice bridge
voice_bridge = VoiceBridgeServer(
    on_transcript=handle_transcript,
    config=VoiceBridgeConfig(
        stt_model="base.en",
        stt_device="cpu",
        tts_enabled=True,
    ),
)
voice_bridge.mount(app, prefix="/voice")


@app.get("/")
async def root():
    """Redirect to voice client."""
    from fastapi.responses import RedirectResponse
    return RedirectResponse(url="/voice/client")


@app.get("/health")
async def health():
    """Health check."""
    return {"status": "ok", "service": "voice-bridge"}


def main():
    """Run the standalone server."""
    print("\n" + "="*60)
    print("🎤 Voice Bridge Standalone Server")
    print("="*60)
    print("\nOpen in browser: http://localhost:8765/voice/client")
    print("\nPress Ctrl+C to stop\n")
    
    uvicorn.run(
        app,
        host="0.0.0.0",
        port=8765,
        log_level="info",
    )


if __name__ == "__main__":
    main()
