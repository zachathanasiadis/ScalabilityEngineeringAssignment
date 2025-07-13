from locust import HttpUser, task, between
import random
import time

class HashUser(HttpUser):
    wait_time = between(0.1, 0.5)  # simulate real usage pacing

    @task(2)
    def hash_sha256(self):
        string = f"loadtest-{random.randint(0, 999999)}"
        with self.client.post("/hash/sha256", json={"string": string}, catch_response=True) as response:
            if response.status_code == 200:
                task_id = response.json().get("task_id")
                self.poll_task(task_id)

    @task(2)
    def hash_md5(self):
        string = f"loadtest-{random.randint(0, 999999)}"
        with self.client.post("/hash/md5", json={"string": string}, catch_response=True) as response:
            if response.status_code == 200:
                task_id = response.json().get("task_id")
                self.poll_task(task_id)

    @task(1)
    def hash_argon2(self):
        string = f"loadtest-{random.randint(0, 999999)}"
        with self.client.post("/hash/argon2", json={"string": string}, catch_response=True) as response:
            if response.status_code == 200:
                task_id = response.json().get("task_id")
                self.poll_task(task_id)

    def poll_task(self, task_id):
        for _ in range(10):  # try for 10 polls (timeout ~10s)
            r = self.client.get(f"/task/{task_id}")
            if r.status_code == 200 and r.json().get("status") == "completed":
                break
            time.sleep(1)
