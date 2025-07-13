#!/usr/bin/env python3
"""
Simple Locust load testing file for Hash API endpoints
Usage: locust -f locustfile.py --host http://localhost:8000/
"""

import random
import string
from time import sleep
from locust import HttpUser, task, constant


class HashAPIUser(HttpUser):
    """User that tests hash API endpoints"""

    wait_time = constant(1)  # Wait 1 second between requests
    ready_tasks_id = []

    def generate_test_string(self, length=1000):
        """Generate a random string of specified length"""
        return ''.join(random.choices(
            string.ascii_letters + string.digits + string.punctuation + ' ',
            k=length
        ))

    @task(3)
    def test_sha256_hash(self):
        """Test SHA256 hash endpoint"""
        test_string = self.generate_test_string()
        response = self.client.post("/hash/sha256", json={"string": test_string})

        if response.status_code == 200:
            data = response.json()
            task_id = data.get('task_id')
            if task_id:
                self.ready_tasks_id.append(task_id)

    @task(3)
    def test_md5_hash(self):
        """Test MD5 hash endpoint"""
        test_string = self.generate_test_string()
        response = self.client.post("/hash/md5", json={"string": test_string})

        if response.status_code == 200:
            data = response.json()
            task_id = data.get('task_id')
            if task_id:
                self.ready_tasks_id.append(task_id)

    @task(3)
    def test_argon2_hash(self):
        """Test Argon2 hash endpoint"""
        test_string = self.generate_test_string()
        response = self.client.post("/hash/argon2", json={"string": test_string})

        if response.status_code == 200:
            data = response.json()
            task_id = data.get('task_id')
            if task_id:
                self.ready_tasks_id.append(task_id)

    @task(3)
    def check_random_task_status(self):
        """Check status of a random task ID"""
        # You could store task IDs and check them later
        task_id = random.choice(self.ready_tasks_id)  # Example
        self.client.get(f"/task/{task_id}")