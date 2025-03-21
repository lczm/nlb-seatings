import asyncio
from typing import List, Dict
from contextlib import asynccontextmanager
from fastapi import FastAPI
from fastapi_utilities import repeat_every
from a import retrieve_all

# in ram storage... easier to manage
seatings: List[Dict] = []

# run on start-up and every hour after
@repeat_every(seconds=60 * 60, wait_first=False)
async def hourly():
    global seatings
    try:
        seatings = [
            retrieve_all(False), retrieve_all(True)
        ]
    except Exception as e:
        print(f"Error updating seating data: {e}")

@asynccontextmanager
async def lifespan(app: FastAPI):
    asyncio.create_task(hourly())
    yield

app = FastAPI(lifespan=lifespan)

@app.get("/seatings")
def read_seatings():
    return seatings
