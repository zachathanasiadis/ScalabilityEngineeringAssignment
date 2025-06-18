from fastapi import FastAPI
from pydantic import BaseModel

app = FastAPI()


@app.get("/")
def root():
    counter = increment_counter()
    return {"counter": counter}


counter = 0


def increment_counter() -> int:
    global counter
    counter += 1
    return counter
