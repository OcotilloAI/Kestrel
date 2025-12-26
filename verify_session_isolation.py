import requests
import time
import sys

API_URL = "http://localhost:8000"

def verify_isolation():
    print("1. Creating Session A (Isolated)...")
    try:
        # Request explicit isolation by sending cwd: "." which maps to None in my logic?
        # Wait, in the code:
        # if cwd_param == ".": cwd_param = None
        # So sending "." means "auto-managed isolated session"
        
        res_a = requests.post(f"{API_URL}/session/create", json={"cwd": "."})
        data_a = res_a.json()
        id_a = data_a["session_id"]
        cwd_a = data_a["cwd"]
        print(f"Session A: {id_a} in {cwd_a}")
        
        if "sessions" not in cwd_a:
            print("FAILURE: Session A is not in sessions directory")
            sys.exit(1)
            
    except Exception as e:
        print(f"Error: {e}")
        sys.exit(1)

    print("\n2. Creating Session B (Isolated)...")
    try:
        res_b = requests.post(f"{API_URL}/session/create", json={"cwd": "."})
        data_b = res_b.json()
        id_b = data_b["session_id"]
        cwd_b = data_b["cwd"]
        print(f"Session B: {id_b} in {cwd_b}")
        
        if cwd_a == cwd_b:
             print("FAILURE: Sessions A and B share the same directory!")
             sys.exit(1)
             
    except Exception as e:
        print(f"Error: {e}")
        sys.exit(1)

    print("\nSUCCESS: Sessions are isolated in separate directories.")

if __name__ == "__main__":
    verify_isolation()
