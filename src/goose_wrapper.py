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

        # Set environment variables for the subprocess
        env = os.environ.copy()
        env["GOOSE_ALLOW_UNSTABLE"] = "1"
        self._apply_gooseenv_file(env, work_dir)
        self._apply_venv_env(env, work_dir)

        self.process = subprocess.Popen(
            cmd,
            cwd=work_dir,
            stdin=subprocess.PIPE,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            bufsize=1,  # Line buffered
            env=env
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
        # Use line buffering provided by the file object
        for line in iter(self.process.stdout.readline, ''):
            if self.running:
                self.output_queue.put(line)
            else:
                break

    def _read_stderr(self):
        for line in iter(self.process.stderr.readline, ''):
            if self.running:
                # Capture stderr for logs/status
                self.output_queue.put(f"[LOG] {line}")
            else:
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

    def _apply_venv_env(self, env, work_dir):
        venv_path = env.get("GOOSE_VENV")
        if not venv_path:
            for candidate in (".venv", "venv"):
                candidate_path = os.path.join(work_dir, candidate)
                if os.path.isdir(candidate_path):
                    venv_path = candidate_path
                    break
        if not venv_path:
            return

        venv_bin = os.path.join(venv_path, "bin")
        env["VIRTUAL_ENV"] = venv_path
        env["PATH"] = f"{venv_bin}:{env.get('PATH', '')}"

    def _apply_gooseenv_file(self, env, work_dir):
        env_path = os.path.join(work_dir, ".gooseenv")
        if not os.path.isfile(env_path):
            return
        try:
            with open(env_path, "r", encoding="utf-8") as handle:
                for line in handle:
                    line = line.strip()
                    if not line or line.startswith("#") or "=" not in line:
                        continue
                    key, value = line.split("=", 1)
                    env[key.strip()] = value.strip()
        except Exception:
            return

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
