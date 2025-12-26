import httpx
import asyncio
import time

async def trigger_and_diagnose():
    """
    Creates a new session to trigger the bug and allow for log inspection.
    """
    print("--- Starting Crash Diagnosis ---")
    
    # Create a new isolated session (same as UI)
    try:
        async with httpx.AsyncClient() as client:
            print("Creating a new isolated session...")
            # Use a timeout to avoid waiting forever if server is down
            resp = await client.post("http://localhost:8000/session/create", json={}, timeout=20.0)
            resp.raise_for_status()
            data = resp.json()
            session_id = data["session_id"]
            print(f"Session created successfully: {session_id}")
            print("Waiting for 30 seconds to observe logs for any crash...")
            
            # Wait to see if the crash happens spontaneously after creation
            await asyncio.sleep(30)
            
            print("Test period finished.")
            print("Please check the docker logs now for any 'KILL SESSION' messages.")

    except httpx.RequestError as e:
        print(f"\n[ERROR] Could not connect to the server: {e}")
        print("Please ensure the Kestrel container is running.")
    except Exception as e:
        print(f"\n[ERROR] An unexpected error occurred: {e}")

if __name__ == "__main__":
    asyncio.run(trigger_and_diagnose())
