import os
import sys
from stt import FasterWhisperSTT
from tts import PiperTTS
from audio import AudioRecorder
from agent_session import AgentSession
from agent_runner import AgentRunner
import asyncio
from llm_client import LLMClient

# Configuration
# Path is relative to CWD
PIPER_BIN = "./piper-bin/piper/piper"
PIPER_MODEL = "piper-data/en_US-lessac-medium.onnx"
def main():
    print("Initializing Kestrel...", file=sys.stderr)
    
    # Initialize components
    try:
        stt = FasterWhisperSTT()
        tts = PiperTTS(PIPER_BIN, PIPER_MODEL)
        recorder = AudioRecorder()
        agent_session = AgentSession(cwd=os.getcwd())
        agent_runner = AgentRunner(LLMClient())
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
    except Exception as e:
        print(f"Initialization Error: {e}", file=sys.stderr)
        return
    
    tts.speak("Kestrel is ready. Listening.")

    try:
        while True:
            # 1. Listen
            audio_data = recorder.record_until_silence()
            if len(audio_data) == 0:
                continue

            # 2. Transcribe
            user_text = stt.transcribe(audio_data)
            print(f"User: {user_text}", file=sys.stderr)
            
            if not user_text.strip():
                continue

            if "goodbye" in user_text.lower():
                tts.speak("Goodbye!")
                break

            async def run_agent(text: str) -> str:
                response_chunks = []
                async for event in agent_runner.run(agent_session, text):
                    if event.get("type") == "assistant":
                        response_chunks.append(event.get("content", ""))
                return "".join(response_chunks).strip()

            try:
                reply = loop.run_until_complete(run_agent(user_text))
                if reply:
                    tts.speak(reply)
            except Exception as e:
                print(f"Agent error: {e}", file=sys.stderr)

    except KeyboardInterrupt:
        print("\nStopping...", file=sys.stderr)
    finally:
        loop.close()

if __name__ == "__main__":
    main()
