import subprocess
import threading
import queue
import re
import time
import sys

class GooseWrapper:
    def __init__(self, executable="./goose-bin"):
        self.executable = executable
        self.process = None
        self.output_queue = queue.Queue()
        self.running = False
        self.read_thread = None

    def start(self):
        cmd = [self.executable, "session"]
        
        self.process = subprocess.Popen(
            cmd,
            stdin=subprocess.PIPE,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            bufsize=1  # Line buffered
        )
        self.running = True
        
        self.read_thread = threading.Thread(target=self._read_stdout)
        self.read_thread.daemon = True
        self.read_thread.start()
        
        # We might also want to read stderr
        self.stderr_thread = threading.Thread(target=self._read_stderr)
        self.stderr_thread.daemon = True
        self.stderr_thread.start()

    def _read_stdout(self):
        while self.running and self.process.poll() is None:
            try:
                line = self.process.stdout.readline()
                if line:
                    self.output_queue.put(line)
                else:
                    if self.process.poll() is not None:
                        break
            except Exception:
                break

    def _read_stderr(self):
        while self.running and self.process.poll() is None:
            try:
                line = self.process.stderr.readline()
                if line:
                    # Stderr often contains logs/spinners. We might ignore or log them.
                    pass 
                else:
                    if self.process.poll() is not None:
                        break
            except Exception:
                break

    def send_input(self, text):
        if self.process and self.process.stdin:
            try:
                self.process.stdin.write(text + "\n")
                self.process.stdin.flush()
            except BrokenPipeError:
                pass

    def get_output(self):
        """Generator yielding lines"""
        while True:
            try:
                line = self.output_queue.get_nowait()
                clean_line = self._clean_ansi(line)
                if clean_line.strip():
                    yield clean_line
            except queue.Empty:
                break

    def _clean_ansi(self, text):
        ansi_escape = re.compile(r'\x1B(?:[@-Z\\-_]|[\[0-?]*[@-~])')
        return ansi_escape.sub('', text)

    def stop(self):
        self.running = False
        if self.process:
            self.process.terminate()
            try:
                self.process.wait(timeout=2)
            except subprocess.TimeoutExpired:
                self.process.kill()
