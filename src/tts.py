import subprocess
import os
import sys

class PiperTTS:
    def __init__(self, piper_path, model_path, speed=1.0):
        self.piper_path = piper_path
        self.model_path = model_path
        self.speed = speed

    def speak(self, text):
        """Synthesize speech and play it immediately."""
        if not text.strip():
            return

        # echo "text" | piper ... | aplay
        cmd = [
            self.piper_path,
            "--model", self.model_path,
            "--output_raw",
            "--length_scale", str(1.0/self.speed)
        ]

        try:
            piper_proc = subprocess.Popen(
                cmd,
                stdin=subprocess.PIPE,
                stdout=subprocess.PIPE,
                stderr=subprocess.DEVNULL
            )
            
            aplay_proc = subprocess.Popen(
                ["aplay", "-r", "22050", "-f", "S16_LE", "-t", "raw", "-q"],
                stdin=piper_proc.stdout,
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL
            )
            
            # Close piper stdout in parent
            if piper_proc.stdout:
                piper_proc.stdout.close()

            piper_proc.communicate(input=text.encode('utf-8'))
            aplay_proc.wait()

        except Exception as e:
            print(f"TTS Error: {e}", file=sys.stderr)
