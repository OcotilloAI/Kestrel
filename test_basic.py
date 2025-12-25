import asyncio
import websockets
import sys

async def test_connection():
    uri = "ws://localhost:8000/ws"
    try:
        async with websockets.connect(uri) as websocket:
            print("Connected to WebSocket")
            
            # Wait for greeting
            greeting = await websocket.recv()
            print(f"Received: {greeting}")
            
            # Send hello
            print("Sending: Hello")
            await websocket.send("Hello")
            
            # Wait for response (timeout 5s)
            response = await asyncio.wait_for(websocket.recv(), timeout=5.0)
            print(f"Received: {response}")
            
    except Exception as e:
        print(f"Test failed: {e}")

if __name__ == "__main__":
    # Ensure server is running before this
    print("Run this after starting the server with ./start.sh")
    # asyncio.run(test_connection()) 
    # Commented out to not run automatically in tool, just providing the file.
