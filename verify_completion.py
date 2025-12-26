import asyncio
import websockets
import sys
import time
import httpx
import os

async def test_kestrel_completion():
    # 0. Wait for server
    print("Waiting for server to be ready...")
    async with httpx.AsyncClient() as client:
        for _ in range(30): # Wait up to 5 minutes (30 * 10s)
            try:
                resp = await client.get("http://localhost:8000/sessions")
                if resp.status_code == 200:
                    print("Server is ready.")
                    break
            except:
                pass
            print(".", end='', flush=True)
            await asyncio.sleep(10)
        else:
            print("Server timed out.")
            return

    # 1. Create Session
    async with httpx.AsyncClient() as client:
        print("Creating session...")
        try:
            resp = await client.post("http://localhost:8000/session/create", json={"cwd": "/workspace"})
            resp.raise_for_status()
            session_id = resp.json()["session_id"]
            print(f"Created session: {session_id}")
        except Exception as e:
            print(f"Failed to create session: {e}")
            return

    uri = f"ws://localhost:8000/ws/{session_id}"
    
    print(f"Connecting to {uri}...")
    try:
        async with websockets.connect(uri) as websocket:
            # Wait for greeting
            await websocket.recv()
            
            prompt = "Create a complete, single-file FastAPI app in 'workspace/test_app/main.py' that handles EV charging stats (duration, kWh, peak, location, food). Include a simple HTML form and a list display in the same file using Jinja2 or raw HTML responses. Write the full code now."
            
            print(f"Sending prompt...")
            await websocket.send(prompt)
            
            print("Monitoring agent for 3 minutes...")
            start_time = time.time()
            while time.time() - start_time < 180:
                try:
                    message = await asyncio.wait_for(websocket.recv(), timeout=1.0)
                    print(message[:80].replace('\n', ' '))
                except asyncio.TimeoutError:
                    print(".", end='', flush=True)
                except websockets.exceptions.ConnectionClosed:
                    break

            print("\nTime up. Checking filesystem...")
            app_file = "workspace/test_app/main.py"
            if os.path.exists(app_file):
                size = os.path.getsize(app_file)
                print(f"File {app_file} exists. Size: {size} bytes")
                if size > 100:
                    print("[PASS] Agent successfully wrote the application code.")
                    with open(app_file, 'r') as f:
                        print("--- Content Preview ---")
                        print(f.read(200))
                else:
                    print("[FAIL] File is too small or empty.")
            else:
                print(f"[FAIL] File {app_file} was never created.")

    except Exception as e:
        print(f"Test failed: {e}")

if __name__ == "__main__":
    asyncio.run(test_kestrel_completion())
