from faster_whisper import WhisperModel
import os
import sys

class FasterWhisperSTT:
    def __init__(self, model_size="base.en", device="cpu", compute_type="int8"):
        print(f"Loading Whisper model: {model_size}...", file=sys.stderr)
        # Using cpu and int8 for broad compatibility
        self.model = WhisperModel(model_size, device=device, compute_type=compute_type)
        print("Whisper model loaded.", file=sys.stderr)

    def transcribe(self, audio_data):
        """
        Transcribe audio data (numpy array, float32, 16kHz).
        """
        if len(audio_data) == 0:
            return ""
        
        segments, info = self.model.transcribe(audio_data, beam_size=5)
        text = " ".join([segment.text for segment in segments]).strip()
        return text
