import subprocess
import threading
import queue
import re
import time
import sys
import os

class GooseWrapper:
    def __init__(self, executable=None):
        if executable is None:
            self.executable = os.environ.get("GOOSE_BIN", "goose")
        else:
            self.executable = executable
        
        self.process = None
        self.output_queue = queue.Queue()
        self.running = False
        self.read_thread = None

    def start(self, cwd=None):
        cmd = [self.executable, "session"]
        
        # Determine working directory
        work_dir = cwd if cwd else os.getcwd()
        print(f"Starting Goose in: {work_dir}", file=sys.stderr)

        self.process = subprocess.Popen(
            cmd,
            cwd=work_dir,
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

    def restart(self, cwd=None):
        self.stop()
        time.sleep(1) # Give it a moment to release resources
        self.output_queue = queue.Queue() # Clear old output
        self.start(cwd)

    def _read_stdout(self):
        while self.running:
            try:
                # Read raw bytes unbuffered
                data = os.read(self.process.stdout.fileno(), 1024)
                if not data:
                    if self.process.poll() is not None:
                        break
                    time.sleep(0.01)
                    continue
                
                text = data.decode('utf-8', errors='replace')
                self.output_queue.put(text)
            except Exception:
                break

    def _read_stderr(self):
        while self.running and self.process.poll() is None:
            try:
                line = self.process.stderr.readline()
                if line:
                    # Capture stderr for logs/status
                    self.output_queue.put(f"[LOG] {line}")
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
        """Generator yielding chunks"""
        while True:
            try:
                chunk = self.output_queue.get_nowait()
                clean_chunk = self._clean_ansi(chunk)
                if clean_chunk:
                    yield clean_chunk
            except queue.Empty:
                break

    def _clean_ansi(self, text):
        ansi_escape = re.compile(r'\x1B(?:[@-Z\\-_]|[\[0-?]*[@-~])')
        return ansi_escape.sub('', text)

    def is_alive(self):
        return self.process is not None and self.process.poll() is None

    def return_code(self):
        return self.process.poll() if self.process else None

    def stop(self):
        self.running = False
        if self.process:
            self.process.terminate()
            try:
                self.process.wait(timeout=2)
            except subprocess.TimeoutExpired:
                self.process.kill()
