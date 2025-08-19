import asyncio
from typing import List, Dict, Annotated
import datetime
from contextlib import asynccontextmanager
from fastapi import FastAPI, Depends
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

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)
# only show warnings and nothing else in the console for sqlalchemy
logging.getLogger('sqlalchemy.engine').setLevel(logging.WARNING)

def get_session():
    with Session(engine) as session:
        yield session

SessionDep = Annotated[Session, Depends(get_session)]

async def update_seating_data():
    current_datetime = datetime.datetime.now()

    try:
        logger.info(f"Starting data update at {current_datetime}")
        seatings = [retrieve_all(True), retrieve_all(False)] if current_datetime.hour >= 12 else [retrieve_all(False)]
        logger.info(f"Retrieved {len(seatings)} seating dataset(s)")

        logger.info("Recreating database tables...")
        SQLModel.metadata.drop_all(bind=engine)
        SQLModel.metadata.create_all(engine)
        
        # Insert data
        logger.info("Inserting seating data into database...")
        with Session(engine) as session:
            total_records = 0
            # Iterate through each date's data
            for seating in seatings:
                date = seating["date"]
                logger.info(f"Processing data for date: {date}")
                
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
                        total_records += 1
            
            session.commit()
            logger.info(f"Successfully inserted {total_records} seating records at {datetime.datetime.now()}")
            
    except Exception as e:
        logger.error(f"Error updating seating data at {datetime.datetime.now()}: {e}")

async def background_task():
    """Background task that runs every hour"""
    logger.info("Background task started")
    
    while True:
        try:
            await update_seating_data()
            # Wait for 1 hour (3600 seconds)
            logger.info("Waiting 1 hour until next update...")
            await asyncio.sleep(3600)
        except Exception as e:
            logger.error(f"Error in background task: {e}")
            # Wait 5 minutes before retrying on error
            await asyncio.sleep(300)

@asynccontextmanager
async def lifespan(app: FastAPI):
    # Start the background task
    task = asyncio.create_task(background_task())
    logger.info("Application started - background task created")
    
    try:
        yield
    finally:
        # Clean up the task when shutting down
        task.cancel()
        try:
            await task
        except asyncio.CancelledError:
            logger.info("Background task cancelled during shutdown")

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
