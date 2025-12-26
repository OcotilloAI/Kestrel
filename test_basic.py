import asyncio
import websockets
import sys

async def test_connection():
    uri = "ws://localhost:8000/ws"
    try:
        async with websockets.connect(uri) as websocket:
            print("Connected to WebSocket")
            
            # Send hello
            print("Sending: Hello")
            await websocket.send("Hello")
            
            # Listen for response with inactivity timeout
            while True:
                try:
                    # Wait for ANY message (log or response)
                    # 30s inactivity timeout (generous for model loading steps)
                    message = await asyncio.wait_for(websocket.recv(), timeout=30.0)
                    
                    print(f"Received: {message}")
                    
                    if message.startswith("ERROR:"):
                        raise Exception(f"Backend reported error: {message}")
                    
                    if "G: [LOG]" in message:
                        # It's a log message, keep waiting
                        continue
                        
                    # It's a response! (Simple check, assumes anything else is a response)
                    if message.startswith("G: ") and "[LOG]" not in message:
                        print("Success: Received response from Goose.")
                        break
                        
                except asyncio.TimeoutError:
                    raise Exception("Test failed: Timed out waiting for activity (Stalled for 30s)")
                    
    except Exception as e:
        import traceback
        traceback.print_exc()
        print(f"Test failed: {type(e).__name__}: {e}")

if __name__ == "__main__":
    # Ensure server is running before this
    print("Run this after starting the server with ./start.sh")
    asyncio.run(test_connection()) 
    # Commented out to not run automatically in tool, just providing the file.
