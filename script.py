import requests
import os

strings = []

if not os.path.exists("rockyou.txt"):
    url = "https://github.com/brannondorsey/naive-hashcat/releases/download/data/rockyou.txt"
    r = requests.get(url)
    with open("rockyou.txt", "wb") as f:
        f.write(r.content)

with open("rockyou.txt", "r", encoding="utf-8", errors="ignore") as f:
    strings = [line.strip() for line in f]

for string in strings[:10]:
    response = requests.post(
        "http://localhost:8000/hash/sha256",
        json={"string": string}
    )

    print(response.json())

response = requests.get(
    "http://localhost:8000/hashes"
)

print(response.json())
