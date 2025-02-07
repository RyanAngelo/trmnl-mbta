import os
import json
from typing import List, Optional
from fastapi import FastAPI, HTTPException
from pydantic import BaseModel
from dotenv import load_dotenv
import aiohttp
from datetime import datetime
from pathlib import Path

# Load environment variables
load_dotenv()

# Initialize FastAPI app
app = FastAPI(title="TRMNL MBTA Schedule Display")

# Configuration model
class RouteConfig(BaseModel):
    routes: List[str]
    stops: List[str]

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
        default_config = RouteConfig(routes=[], stops=[])
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

async def fetch_predictions(route_ids: List[str], stop_ids: List[str]) -> List[Prediction]:
    """Fetch predictions from MBTA API."""
    params = {
        "filter[route]": ",".join(route_ids),
        "filter[stop]": ",".join(stop_ids),
        "sort": "departure_time",
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
        raise HTTPException(status_code=500, detail="TRMNL webhook URL not configured")
    
    # Prepare prediction data
    formatted_predictions = []
    for pred in predictions:
        departure = pred.departure_time or pred.arrival_time
        if departure:
            dt = datetime.fromisoformat(departure.replace("Z", "+00:00"))
            stop_name = await get_stop_info(pred.stop_id)
            formatted_predictions.append({
                "route_id": pred.route_id,
                "stop_name": stop_name,
                "time": dt.strftime("%I:%M %p")
            })
    
    # Prepare data for TRMNL template
    template_data = {
        "predictions": formatted_predictions,
        "last_updated": datetime.now().strftime("%I:%M %p"),
        "total_predictions": len(formatted_predictions)
    }
    
    # Send to TRMNL
    async with aiohttp.ClientSession() as session:
        await session.post(
            TRMNL_WEBHOOK_URL,
            json=template_data
        )

@app.get("/config", response_model=RouteConfig)
async def get_config():
    """Get current configuration."""
    return load_config()

@app.post("/config")
async def update_config(config: RouteConfig):
    """Update configuration."""
    save_config(config)
    return {"status": "success"}

@app.post("/webhook/update")
async def update_schedule():
    """Manually trigger an update of the schedule display."""
    config = load_config()
    predictions = await fetch_predictions(config.routes, config.stops)
    await update_trmnl_display(predictions)
    return {"status": "success", "predictions_count": len(predictions)}

# Create default config file if it doesn't exist
if not os.path.exists(CONFIG_FILE):
    save_config(RouteConfig(routes=[], stops=[])) 