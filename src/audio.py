import sounddevice as sd
import numpy as np
import time
import sys

class AudioRecorder:
    def __init__(self, sample_rate=16000, channels=1):
        self.sample_rate = sample_rate
        self.channels = channels

    def record_until_silence(self, threshold=0.02, silence_duration=1.5, chunk_size=1024):
        """
        Record audio until silence is detected for 'silence_duration' seconds.
        Simple RMS-based VAD.
        """
        print("Listening...", file=sys.stderr)
        audio_buffer = []
        silence_start = None
        has_speech = False
        start_time = time.time()
        
        try:
            with sd.InputStream(samplerate=self.sample_rate, channels=self.channels, dtype='float32') as stream:
                while True:
                    chunk, overflowed = stream.read(chunk_size)
                    # Convert chunk to numpy array if it isn't already (sounddevice returns numpy array)
                    rms = np.sqrt(np.mean(chunk**2))
                    audio_buffer.append(chunk)

                    if rms > threshold:
                        silence_start = None
                        has_speech = True
                    else:
                        if silence_start is None:
                            silence_start = time.time()
                        elif time.time() - silence_start > silence_duration:
                            if has_speech:
                                break
                            else:
                                # If we haven't heard speech yet, we just keep waiting?
                                # Or if we wait too long (e.g. 10s) without speech, we return empty?
                                if time.time() - start_time > 10.0:
                                    return np.array([], dtype=np.float32)
                                
        except Exception as e:
            print(f"Audio Error: {e}", file=sys.stderr)
            return np.array([], dtype=np.float32)
        
        print("Processing...", file=sys.stderr)
        return np.concatenate(audio_buffer, axis=0).flatten()
