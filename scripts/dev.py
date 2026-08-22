import subprocess
import sys
import os
import time

def run_dev():
    base_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    web_dir = os.path.join(base_dir, "web")
    
    print("=== Starting Governance-API Local Development Environment ===")
    print("Backend API:  http://localhost:8080")
    print("Frontend UI:  http://localhost:3000")
    print("Press Ctrl+C to terminate both servers.\n")

    cmd_backend = [sys.executable, "-m", "uvicorn", "app.main:app", "--port", "8080", "--reload"]
    cmd_frontend = [sys.executable, "-m", "http.server", "3000", "--directory", web_dir]

    p_backend = subprocess.Popen(cmd_backend, cwd=base_dir)
    p_frontend = subprocess.Popen(cmd_frontend, cwd=base_dir)

    try:
        while True:
            time.sleep(1)
    except KeyboardInterrupt:
        print("\nShutting down dev servers...")
        p_backend.terminate()
        p_frontend.terminate()
        p_backend.wait()
        p_frontend.wait()
        print("Dev servers stopped.")

if __name__ == "__main__":
    run_dev()
