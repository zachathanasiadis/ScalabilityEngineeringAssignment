from fastapi import FastAPI
from pydantic import BaseModel
import hashlib

app = FastAPI()

str_to_hash256_mappings = {}
str_to_md5_mappings = {}

class InputString(BaseModel):
    string: str


@app.post("/hash/sha256")
def convert_str_to_sha256(input: InputString):
    string = input.string
    sha256 = hashlib.sha256()
    sha256.update(string.encode())
    hashed_string = sha256.hexdigest()
    str_to_hash256_mappings[string] = hashed_string
    return {"SHA256 Digest": hashed_string}


@app.post("/hash/md5")
def convert_str_to_md5(input: InputString):
    string = input.string
    md5 = hashlib.md5()
    md5.update(string.encode())
    hashed_string = md5.hexdigest()
    str_to_md5_mappings[string] = hashed_string
    return {"MD5 Digest": hashed_string}


@app.get("/hashes")
def get_hashes():
    return {"SHA256": str_to_hash256_mappings, "MD5": str_to_md5_mappings}
