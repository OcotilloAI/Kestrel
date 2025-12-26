import asyncio
import websockets
import sys
import json

async def test_connection():
    uri = "ws://localhost:8000/ws"
    print(f"Connecting to {uri}...")
    try:
        async with websockets.connect(uri) as websocket:
            print("Connected to WebSocket")
            
            # Send a prompt simulation (the frontend sends raw text)
            test_message = "What are the three laws of robotics?"
            print(f"Sending: {test_message}")
            await websocket.send(test_message)
            
            # We expect a stream of responses. 
            # We'll listen for a few seconds or until we get some content.
            print("Listening for response stream...")
            
            timeout = 30.0 # Give it some time, model inference might be slow initially
            try:
                start_time = asyncio.get_event_loop().time()
                while (asyncio.get_event_loop().time() - start_time) < timeout:
                    # Wait for next message with a short timeout to keep loop responsive
                    response = await asyncio.wait_for(websocket.recv(), timeout=2.0)
                    print(f"Received chunk: {response}")
                    
                    if "G:" in response:
                        # Found valid response prefix
                        break
            except asyncio.TimeoutError:
                print("Timed out waiting for specific response, but connection was open.")
            
            print("Test Complete.")

    except Exception as e:
        print(f"Test failed: {e}")
        sys.exit(1)

if __name__ == "__main__":
    asyncio.run(test_connection())
