#!/usr/bin/env python3
"""
Script to run multiple FastAPI app instances for horizontal scaling
"""

import subprocess
import sys
import os
import time
from multiprocessing import Process

def run_app_instance(port, app_name):
    """Run a single FastAPI app instance"""
    env = os.environ.copy()
    env['APP_NAME'] = app_name
    env['PORT'] = str(port)
    
    cmd = [
        sys.executable, 
        "-m", "uvicorn", 
        "main:app", 
        "--host", "0.0.0.0",
        "--port", str(port),
        "--reload"
    ]
    
    print(f"Starting {app_name} on port {port}")
    subprocess.run(cmd, env=env)

def run_multiple_instances(num_instances=3, start_port=8001):
    """Run multiple app instances"""
    processes = []
    
    try:
        for i in range(num_instances):
            port = start_port + i
            app_name = f"hash-api-{i+1}"
            
            p = Process(target=run_app_instance, args=(port, app_name))
            p.start()
            processes.append(p)
            
            # Small delay between starts
            time.sleep(1)
        
        print(f"Started {num_instances} app instances")
        print("Press Ctrl+C to stop all instances")
        
        # Wait for all processes
        for p in processes:
            p.join()
            
    except KeyboardInterrupt:
        print("\nStopping all instances...")
        for p in processes:
            p.terminate()
        
        # Wait for processes to terminate
        for p in processes:
            p.join()
        
        print("All instances stopped")

if __name__ == "__main__":
    import argparse
    
    parser = argparse.ArgumentParser(description='Run multiple FastAPI app instances')
    parser.add_argument('--instances', '-i', type=int, default=3, help='Number of instances to run')
    parser.add_argument('--start-port', '-p', type=int, default=8001, help='Starting port number')
    
    args = parser.parse_args()
    
    run_multiple_instances(args.instances, args.start_port)
