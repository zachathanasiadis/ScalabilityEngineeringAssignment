#!/usr/bin/env python3
"""
Log Monitor Script for Scalability Engineering Project
This script helps monitor which app instances and workers are handling requests
"""

import os
import time
import subprocess
import threading
from datetime import datetime
import re

class LogMonitor:
    def __init__(self):
        self.containers = [
            "scalability-engineering-project-app1-1",
            "scalability-engineering-project-app2-1",
            "scalability-engineering-project-app3-1",
            "scalability-engineering-project-worker1-1",
            "scalability-engineering-project-worker2-1",
            "scalability-engineering-project-worker3-1",
            "lb_main"
        ]

    def monitor_container_logs(self, container_name, color_code):
        """Monitor logs for a specific container"""
        try:
            cmd = ["docker", "logs", "-f", "--tail", "10", container_name]
            process = subprocess.Popen(
                cmd,
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT,
                universal_newlines=True,
                bufsize=1
            )

            for line in iter(process.stdout.readline, ''):
                if line.strip():
                    timestamp = datetime.now().strftime("%H:%M:%S")
                    print(f"\033[{color_code}m[{timestamp}] {container_name}: {line.strip()}\033[0m")

        except Exception as e:
            print(f"Error monitoring {container_name}: {e}")

    def start_monitoring(self):
        """Start monitoring all containers"""
        print("🔍 Starting log monitoring for all containers...")
        print("=" * 80)

        # Color codes for different containers
        colors = ["32", "33", "34", "35", "36", "31", "37"]  # Green, Yellow, Blue, Magenta, Cyan, Red, White

        threads = []

        for i, container in enumerate(self.containers):
            color = colors[i % len(colors)]
            thread = threading.Thread(
                target=self.monitor_container_logs,
                args=(container, color),
                daemon=True
            )
            thread.start()
            threads.append(thread)

        try:
            # Keep the main thread alive
            while True:
                time.sleep(1)
        except KeyboardInterrupt:
            print("\n\n🛑 Stopping log monitoring...")

def show_container_stats():
    """Show current container statistics"""
    print("\n📊 Container Statistics:")
    print("=" * 50)

    try:
        # Get container stats
        result = subprocess.run(
            ["docker", "stats", "--no-stream", "--format", "table {{.Container}}\t{{.CPUPerc}}\t{{.MemUsage}}"],
            capture_output=True,
            text=True
        )

        print(result.stdout)
    except Exception as e:
        print(f"Error getting container stats: {e}")

def show_help():
    """Show help information"""
    print("""
🔧 Scalability Engineering Project - Log Monitor

Usage: python monitor_logs.py [option]

Options:
  monitor     - Start real-time log monitoring (default)
  stats       - Show container statistics
  help        - Show this help message
  test        - Send test requests to see load balancing

Examples:
  python monitor_logs.py
  python monitor_logs.py monitor
  python monitor_logs.py stats
  python monitor_logs.py test

📋 What to look for:
  - [hash-api-1/2/3] - Shows which app instance handled the request
  - [worker-1/2/3] - Shows which worker processed the task
  - Cache HIT/MISS - Shows cache effectiveness
  - Task queuing and completion flow

🎯 Testing Cache:
  1. Send same request twice - should see cache HIT on second request
  2. Check /cache/stats endpoint for cache statistics
  3. Use /cache/clear to reset cache

🔄 Testing Load Balancing:
  1. Send multiple requests quickly
  2. Watch logs to see different app instances handling them
  3. Check /lb/stats for load balancer statistics
    """)

def send_test_requests():
    """Send test requests to demonstrate load balancing and caching"""
    print("🧪 Sending test requests...")
    print("=" * 40)

    import requests
    import json

    base_url = "http://localhost:8000"

    # Test data
    test_strings = ["hello", "world", "test", "cache", "worker"]

    try:
        for i, test_string in enumerate(test_strings):
            print(f"\n📤 Test {i+1}: Sending SHA256 request for '{test_string}'")

            # Send SHA256 request
            response = requests.post(
                f"{base_url}/hash/sha256",
                json={"string": test_string}
            )

            if response.status_code == 200:
                result = response.json()
                task_id = result.get("task_id")
                print(f"✅ Task {task_id} queued successfully")

                # Wait a bit and check task status
                time.sleep(2)

                status_response = requests.get(f"{base_url}/task/{task_id}")
                if status_response.status_code == 200:
                    status_result = status_response.json()
                    print(f"📊 Task {task_id} status: {status_result.get('status')}")

                    # If completed, send the same request again to test cache
                    if status_result.get('status') == 'completed':
                        print(f"🔄 Sending same request again to test cache...")
                        cache_response = requests.post(
                            f"{base_url}/hash/sha256",
                            json={"string": test_string}
                        )

                        if cache_response.status_code == 200:
                            cache_result = cache_response.json()
                            if cache_result.get("source") == "cache":
                                print("🎯 Cache HIT! Request served from cache")
                            else:
                                print("❌ Cache MISS - something might be wrong")

            else:
                print(f"❌ Request failed: {response.status_code}")

            time.sleep(1)

        # Show cache stats
        print("\n📈 Cache Statistics:")
        cache_stats = requests.get(f"{base_url}/cache/stats")
        if cache_stats.status_code == 200:
            stats = cache_stats.json()
            print(json.dumps(stats, indent=2))

        # Show load balancer stats
        print("\n⚖️  Load Balancer Statistics:")
        lb_stats = requests.get(f"{base_url}/lb/stats")
        if lb_stats.status_code == 200:
            stats = lb_stats.json()
            print(json.dumps(stats, indent=2))

    except Exception as e:
        print(f"❌ Error sending test requests: {e}")

if __name__ == "__main__":
    import sys

    if len(sys.argv) > 1:
        command = sys.argv[1].lower()

        if command == "stats":
            show_container_stats()
        elif command == "help":
            show_help()
        elif command == "test":
            send_test_requests()
        elif command == "monitor":
            LogMonitor().start_monitoring()
        else:
            print(f"Unknown command: {command}")
            show_help()
    else:
        LogMonitor().start_monitoring()