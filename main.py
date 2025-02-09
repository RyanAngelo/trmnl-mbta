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
    """Schedule prediction model"""
    route_id: str
    stop_id: str
    arrival_time: Optional[str]
    departure_time: Optional[str]
    direction_id: int
    status: Optional[str]

# Global configuration
CONFIG_FILE = "config.json"
MBTA_API_KEY = os.getenv("MBTA_API_KEY")
TRMNL_WEBHOOK_URL = os.getenv("TRMNL_WEBHOOK_URL")
MBTA_API_BASE = "https://api-v3.mbta.com"

# Print webhook URL for debugging
print("TRMNL Webhook URL:", TRMNL_WEBHOOK_URL)

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
                        departure_time=attributes.get("departure_time"),
                        direction_id=attributes.get("direction_id", 0),
                        status=attributes.get("status")
                    )
                )
            return predictions

async def get_stop_locations(route_id: str) -> dict:
    """Fetch all stops with their locations for a given route."""
    async with aiohttp.ClientSession() as session:
        async with session.get(
            f"{MBTA_API_BASE}/stops",
            params={
                "filter[route]": route_id,
                "include": "route"
            },
            headers=HEADERS
        ) as response:
            if response.status != 200:
                return {}
            data = await response.json()
            return {
                stop["attributes"]["name"]: {
                    "latitude": stop["attributes"]["latitude"],
                    "longitude": stop["attributes"]["longitude"]
                }
                for stop in data.get("data", [])
            }

async def update_trmnl_display(predictions: List[Prediction]):
    """Send updates to TRMNL display via webhook."""
    if not TRMNL_WEBHOOK_URL:
        print("Error: TRMNL webhook URL not configured")
        raise HTTPException(status_code=500, detail="TRMNL webhook URL not configured")
    
    config = load_config()
    print(f"Current route config: {config.route_id}")
    
    # Get predictions for each stop and direction
    stop_predictions = {}
    for pred in predictions:
        departure = pred.departure_time or pred.arrival_time
        if departure:
            dt = datetime.fromisoformat(departure.replace("Z", "+00:00"))
            stop_name = await get_stop_info(pred.stop_id)
            direction = "inbound" if pred.direction_id == 1 else "outbound"
            
            if stop_name not in stop_predictions:
                stop_predictions[stop_name] = {
                    "stop_name": stop_name,
                    "inbound": [],
                    "outbound": []
                }
            
            if len(stop_predictions[stop_name][direction]) < 3:  # Keep only 3 predictions per direction
                stop_predictions[stop_name][direction].append({
                    "time": dt.strftime("%I:%M %p"),
                    "status": pred.status or "Scheduled"
                })
    
    # Get stop locations and determine line direction
    stop_locations = await get_stop_locations(config.route_id)
    if stop_locations:
        # Find the most northern and southern stops to determine direction
        stops_by_lat = sorted(stop_locations.items(), key=lambda x: x[1]["latitude"])
        north_stop = stops_by_lat[-1][0]
        south_stop = stops_by_lat[0][0]
        
        # Sort stops from north to south
        sorted_stops = sorted(
            stop_predictions.values(),
            key=lambda x: -stop_locations.get(x["stop_name"], {"latitude": 0})["latitude"]
        )
    
    # Create numbered variables for each stop
    merge_vars = {
        "line_name": config.route_id,
        "line_color": get_line_color(config.route_id),
        "last_updated": datetime.now().strftime("%I:%M %p")
    }
    
    # Add numbered stop variables with inbound/outbound times
    for i, stop in enumerate(sorted_stops):
        merge_vars[f"stop_{i}_name"] = stop["stop_name"]
        
        # Add inbound times without status
        for j, pred in enumerate(stop["inbound"][:3], 1):
            merge_vars[f"stop_{i}_inbound_{j}"] = pred['time']
        
        # Add outbound times without status
        for j, pred in enumerate(stop["outbound"][:3], 1):
            merge_vars[f"stop_{i}_outbound_{j}"] = pred['time']
    
    merge_vars["stop_count"] = len(sorted_stops)

    template_data = {
        "merge_variables": merge_vars
    }
    
    print(f"Sending update to TRMNL: {template_data}")
    
    async with aiohttp.ClientSession() as session:
        try:
            response = await session.post(
                TRMNL_WEBHOOK_URL,
                json=template_data,
                headers={"Content-Type": "application/json"}
            )
            print(f"TRMNL response status: {response.status}")
            response_text = await response.text()
            print(f"TRMNL response body: {response_text}")
            
            if response.status != 200:
                print(f"TRMNL error response: {response_text}")
        except Exception as e:
            print(f"Error sending to TRMNL: {str(e)}")

def get_line_color(route_id: str) -> str:
    """Return the color code for a given MBTA line."""
    colors = {
        "Red": "#FA2D27",
        "Orange": "#FFA500",
        "Green-B": "#00843D",
        "Green-C": "#00843D",
        "Green-D": "#00843D",
        "Green-E": "#00843D",
        "Blue": "#2F5DA6"
    }
    return colors.get(route_id, "#666666")  # Default gray if line not found

def get_stop_order(route_id: str) -> dict:
    """Return the order of stops for a given line."""
    orders = {
        "Orange": [
            "Oak Grove", 
            "Malden Center",
            "Wellington",
            "Assembly",
            "Sullivan Square",
            "Community College",
            "North Station",
            "Haymarket",
            "State",
            "Downtown Crossing",
            "Chinatown",
            "Tufts Medical Center",
            "Back Bay",
            "Massachusetts Avenue",
            "Ruggles",
            "Roxbury Crossing",
            "Jackson Square",
            "Stony Brook",
            "Green Street",
            "Forest Hills"
        ]
    }
    return {stop: idx for idx, stop in enumerate(orders.get(route_id, []))}

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