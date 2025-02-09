import os
import json
from typing import List, Optional
from fastapi import FastAPI, HTTPException
from pydantic import BaseModel
from dotenv import load_dotenv
import aiohttp
from datetime import datetime
from pathlib import Path
import asyncio
from contextlib import asynccontextmanager

# Load environment variables
load_dotenv()

# Initialize FastAPI app
@asynccontextmanager
async def lifespan(app: FastAPI):
    """Lifecycle manager for FastAPI app"""
    # Start update loop on startup
    task = asyncio.create_task(update_loop())
    yield
    # Cancel update loop on shutdown
    task.cancel()

app = FastAPI(
    title="TRMNL MBTA Schedule Display",
    lifespan=lifespan
)

# Configuration model
class RouteConfig(BaseModel):
    """Configuration model for a single route"""
    route_id: str

# Schedule prediction model
class Prediction(BaseModel):
    route_id: str
    stop_id: str
    arrival_time: Optional[str]
    departure_time: Optional[str]

# Global configuration
CONFIG_FILE = "config.json"
MBTA_API_KEY = os.getenv("MBTA_API_KEY")
TRMNL_WEBHOOK_URL = os.getenv("TRMNL_WEBHOOK_URL")
MBTA_API_BASE = "https://api-v3.mbta.com"

# Headers for MBTA API
HEADERS = {"x-api-key": MBTA_API_KEY} if MBTA_API_KEY else {}

def load_config() -> RouteConfig:
    """Load configuration from file."""
    try:
        with open(CONFIG_FILE, "r") as f:
            return RouteConfig(**json.load(f))
    except FileNotFoundError:
        default_config = RouteConfig(route_id="")
        save_config(default_config)
        return default_config

def save_config(config: RouteConfig):
    """Save configuration to file."""
    with open(CONFIG_FILE, "w") as f:
        json.dump(config.dict(), f, indent=2)

async def get_stop_info(stop_id: str) -> str:
    """Fetch stop name from MBTA API."""
    async with aiohttp.ClientSession() as session:
        async with session.get(
            f"{MBTA_API_BASE}/stops/{stop_id}",
            headers=HEADERS
        ) as response:
            if response.status != 200:
                return stop_id
            data = await response.json()
            return data.get("data", {}).get("attributes", {}).get("name", stop_id)

async def get_route_stops(route_id: str) -> List[str]:
    """Fetch all stops for a given route from MBTA API."""
    async with aiohttp.ClientSession() as session:
        async with session.get(
            f"{MBTA_API_BASE}/stops",
            params={"filter[route]": route_id},
            headers=HEADERS
        ) as response:
            if response.status != 200:
                raise HTTPException(status_code=response.status, detail="MBTA API error")
            data = await response.json()
            return [stop["id"] for stop in data.get("data", [])]

async def fetch_predictions(route_id: str) -> List[Prediction]:
    """Fetch predictions from MBTA API."""
    stops = await get_route_stops(route_id)
    
    params = {
        "filter[route]": route_id,
        "filter[stop]": ",".join(stops),
        "sort": "departure_time",
        "include": "route,stop"
    }
    
    async with aiohttp.ClientSession() as session:
        async with session.get(
            f"{MBTA_API_BASE}/predictions",
            params=params,
            headers=HEADERS
        ) as response:
            if response.status != 200:
                raise HTTPException(status_code=response.status, detail="MBTA API error")
            data = await response.json()
            
            predictions = []
            for pred in data.get("data", []):
                attributes = pred.get("attributes", {})
                predictions.append(
                    Prediction(
                        route_id=pred["relationships"]["route"]["data"]["id"],
                        stop_id=pred["relationships"]["stop"]["data"]["id"],
                        arrival_time=attributes.get("arrival_time"),
                        departure_time=attributes.get("departure_time")
                    )
                )
            return predictions

async def update_trmnl_display(predictions: List[Prediction]):
    """Send updates to TRMNL display via webhook."""
    if not TRMNL_WEBHOOK_URL:
        print("Error: TRMNL webhook URL not configured")
        raise HTTPException(status_code=500, detail="TRMNL webhook URL not configured")
    
    config = load_config()
    
    # Get next arrival for each stop
    stop_predictions = {}
    for pred in predictions:
        departure = pred.departure_time or pred.arrival_time
        if departure:
            dt = datetime.fromisoformat(departure.replace("Z", "+00:00"))
            if pred.stop_id not in stop_predictions:
                stop_name = await get_stop_info(pred.stop_id)
                stop_predictions[pred.stop_id] = {
                    "stop_name": stop_name,
                    "time": dt.strftime("%I:%M %p")
                }
    
    template_data = {
        "route_id": config.route_id,
        "stops": list(stop_predictions.values()),
        "last_updated": datetime.now().strftime("%I:%M %p")
    }
    
    print(f"Sending update to TRMNL: {template_data}")
    
    async with aiohttp.ClientSession() as session:
        response = await session.post(
            TRMNL_WEBHOOK_URL,
            json=template_data
        )
        print(f"TRMNL response status: {response.status}")
        if response.status != 200:
            response_text = await response.text()
            print(f"TRMNL error response: {response_text}")

@app.get("/config", response_model=RouteConfig)
async def get_config():
    """Get current configuration."""
    return load_config()

@app.post("/config")
async def update_config(config: RouteConfig):
    """Update configuration."""
    save_config(config)
    return {"status": "success", "route": config.route_id}

@app.post("/webhook/update")
async def update_schedule():
    """Manually trigger an update of the schedule display."""
    config = load_config()
    predictions = await fetch_predictions(config.route_id)
    await update_trmnl_display(predictions)
    return {"status": "success", "predictions_count": len(predictions)}

async def update_loop():
    """Main loop to update the display periodically"""
    while True:
        try:
            print("Fetching new predictions...")
            config = load_config()
            predictions = await fetch_predictions(config.route_id)
            print(f"Got {len(predictions)} predictions")
            await update_trmnl_display(predictions)
            await asyncio.sleep(30)
        except Exception as e:
            print(f"Error in update loop: {str(e)}")
            await asyncio.sleep(5)

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)

# Create default config file if it doesn't exist
if not os.path.exists(CONFIG_FILE):
    save_config(RouteConfig(route_id="")) 