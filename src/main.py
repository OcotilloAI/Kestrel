import os
import time
import sys
import numpy as np
from stt import FasterWhisperSTT
from tts import PiperTTS
from audio import AudioRecorder
from goose_wrapper import GooseWrapper

# Configuration
# Path is relative to CWD
PIPER_BIN = "./piper-bin/piper/piper"
PIPER_MODEL = "piper-data/en_US-lessac-medium.onnx"
GOOSE_BIN = "./goose-bin"

def main():
    print("Initializing Kestrel...", file=sys.stderr)
    
    # Initialize components
    try:
        stt = FasterWhisperSTT()
        tts = PiperTTS(PIPER_BIN, PIPER_MODEL)
        recorder = AudioRecorder()
        goose = GooseWrapper(GOOSE_BIN)
    except Exception as e:
        print(f"Initialization Error: {e}", file=sys.stderr)
        return
    
    print("Starting Goose Agent...", file=sys.stderr)
    try:
        goose.start()
    except Exception as e:
        print(f"Failed to start Goose: {e}", file=sys.stderr)
        return

    tts.speak("Goose is ready. Listening.")
    
    # Wait a bit for Goose to initialize (it might print a welcome message)
    time.sleep(2)
    # Drain initial output
    for line in goose.get_output():
        print(f"Goose Init: {line.strip()}", file=sys.stderr)

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

            # 3. Send to Goose
            goose.send_input(user_text)
            
            # 4. Read Goose Response & Speak
            accumulated_sentence = ""
            start_wait = time.time()
            got_response = False
            
            # Max wait time for ANY response
            max_wait_total = 30.0 
            start_total_wait = time.time()

            while True:
                lines = list(goose.get_output())
                
                if lines:
                    got_response = True
                    start_wait = time.time() # Reset silence timeout
                    
                    for line in lines:
                        print(f"Goose: {line.strip()}", file=sys.stderr)
                        
                        # Filter prompt
                        if ">" in line and len(line) < 20: 
                            continue 
                        # Filter "Goose is thinking" or similar if needed
                        
                        accumulated_sentence += " " + line.strip()
                        
                        if line.strip().endswith(('.', '!', '?', ':')):
                             tts.speak(accumulated_sentence)
                             accumulated_sentence = ""

                # Conditions to stop waiting:
                # 1. We got response AND silence for X seconds
                if got_response and (time.time() - start_wait > 1.5):
                    # Flush remaining
                    if accumulated_sentence.strip():
                        tts.speak(accumulated_sentence)
                    break
                
                # 2. Timeout waiting for ANY response
                if not got_response and (time.time() - start_total_wait > max_wait_total):
                    print("Goose timed out.", file=sys.stderr)
                    break

                time.sleep(0.1)

    except KeyboardInterrupt:
        print("\nStopping...", file=sys.stderr)
    finally:
        goose.stop()

if __name__ == "__main__":
    main()
