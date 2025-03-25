import asyncio
from typing import List, Dict, Annotated
import datetime
from contextlib import asynccontextmanager
from fastapi import FastAPI, Depends
from fastapi_utilities import repeat_every
from a import retrieve_all
from sqlmodel import Field, Session, create_engine, SQLModel, Column, JSON, select
import json
import logging

class Seating(SQLModel, table=True):
    id: int | None = Field(default=None, primary_key=True)
    date: str
    name: str
    branch_id: int 
    area: str
    seat: str
    availability: List[bool] = Field(sa_column=Column(JSON))
    start_time: datetime.datetime
    end_time: datetime.datetime

DATABASE_URL = "sqlite:///nlb.db"
engine = create_engine(DATABASE_URL, echo=False)

# only show warnings and nothing else in the console
logging.getLogger('sqlalchemy.engine').setLevel(logging.WARNING)

def get_session():
    with Session(engine) as session:
        yield session

SessionDep = Annotated[Session, Depends(get_session)]

# run on start-up and every hour after
@repeat_every(seconds=60 * 60, wait_first=False)
async def hourly():
    # only scrape between 7am and 9pm
    current_time = datetime.datetime.now().time()
    if current_time < datetime.time(7, 0) or current_time > datetime.time(21, 0):
        print("Hourly cron not at specified time")
        return

    try:
        seatings = [retrieve_all(True), retrieve_all(False)] if datetime.datetime.now().hour >= 12 else [retrieve_all(False)]

        SQLModel.metadata.drop_all(bind=engine)
        SQLModel.metadata.create_all(engine)
        with Session(engine) as session:
            # Iterate through each date's data
            for seating in seatings:
                date = seating["date"]
                for branch in seating["branches"]:
                    for seat in branch["seats"]:
                        db_seating = Seating(
                            date=date,
                            name=branch["name"],
                            branch_id=branch["id"],
                            area=seat["area"],
                            seat=seat["seat"],
                            availability=seat["availability"],
                            start_time=datetime.datetime.fromisoformat(branch["start_time"]),
                            end_time=datetime.datetime.fromisoformat(branch["end_time"])
                        )
                        session.add(db_seating)
            session.commit()
    except Exception as e:
        print(f"Error updating seating data: {e}")

@asynccontextmanager
async def lifespan(app: FastAPI):
    asyncio.create_task(hourly())
    yield

app = FastAPI(lifespan=lifespan)

@app.get("/branches")
def get_branches(session: SessionDep):
    result = {}
    dates = session.exec(select(Seating.date).distinct().order_by(Seating.date))
    for date in dates:
        branches = session.exec(select(
            Seating.branch_id, Seating.name
        ).where(Seating.date == date).distinct())

        branches_data = []
        for branch_id, name in branches:
            # get all branch seatings
            branch_seatings = session.exec(select(Seating).where(
                Seating.date == date,
                Seating.branch_id == branch_id
            )).all()
            
            current, total = 0, 0
            for seating in branch_seatings:
                current += sum(1 for available in seating.availability if available)
                total += len(seating.availability)
            
            branches_data.append({
                'id': branch_id,
                'name': name,
                'current_capacity': current,
                'total_capacity': total
            })
        result[date] = branches_data

    return result

@app.get("/seatings/{date}/{branch_id}")
def get_seatings(date: str, branch_id: int, session: SessionDep):
    # Query seatings for given date and branch
    seatings = session.exec(select(Seating).where(
        Seating.date == date,
        Seating.branch_id == branch_id
    )).all()
    
    if not seatings:
        return {"error": "No data found"}

    result = {}
    for seating in seatings:
        if seating.area not in result:
            result[seating.area] = {
                "area": seating.area,
                "start_time": seating.start_time.isoformat(),
                "end_time": seating.end_time.isoformat(),
                "seats": {}
            }
        result[seating.area]["seats"][seating.seat] = seating.availability
    return list(result.values())
