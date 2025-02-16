import os
import json
import logging
from typing import List, Optional, Pattern
from fastapi import FastAPI, HTTPException, Depends, Security, Request
from fastapi.security import APIKeyHeader
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, validator
from dotenv import load_dotenv
import aiohttp
from datetime import datetime
from pathlib import Path
import asyncio
from contextlib import asynccontextmanager
from slowapi import Limiter, _rate_limit_exceeded_handler
from slowapi.util import get_remote_address
from slowapi.errors import RateLimitExceeded
import re
import fcntl

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    handlers=[logging.FileHandler("mbta.log"), logging.StreamHandler()],
)
logger = logging.getLogger(__name__)

# Load environment variables
load_dotenv()

# Get allowed origins from environment variable or use default
ALLOWED_ORIGINS = os.getenv("ALLOWED_ORIGINS", "http://localhost:8000").split(",")

# Configure rate limiter
limiter = Limiter(key_func=get_remote_address)


# Initialize FastAPI app
@asynccontextmanager
async def lifespan(app: FastAPI):
    """Lifecycle manager for FastAPI app"""
    # Start update loop on startup
    task = asyncio.create_task(update_loop())
    yield
    # Cancel update loop on shutdown
    task.cancel()


app = FastAPI(title="TRMNL MBTA Schedule Display", lifespan=lifespan)
app.state.limiter = limiter
app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)

# Add CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=ALLOWED_ORIGINS,
    allow_credentials=True,
    allow_methods=["GET", "POST"],
    allow_headers=["Content-Type", "Authorization", "X-API-Key"],
    expose_headers=["X-RateLimit-Limit", "X-RateLimit-Remaining", "X-RateLimit-Reset"],
    max_age=3600,  # Cache preflight requests for 1 hour
)

# Constants for validation
VALID_ROUTE_PATTERN: Pattern = re.compile(r"^(Red|Orange|Blue|Green-[A-E])$")
VALID_STOP_PATTERN: Pattern = re.compile(r"^[a-zA-Z0-9-]+$")


# Configuration model
class RouteConfig(BaseModel):
    """Configuration model for a single route"""

    route_id: str

    @validator("route_id")
    def validate_route_id(cls, v):
        """Validate route_id format"""
        if not VALID_ROUTE_PATTERN.match(v):
            raise ValueError("Invalid route_id format")
        return v


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
TEMPLATE_PATH = Path(__file__).parent.parent.parent / "templates" / "trmnl-template.html"
CONFIG_FILE = Path(__file__).parent.parent.parent / "config.json"
MBTA_API_KEY = os.getenv("MBTA_API_KEY")
TRMNL_WEBHOOK_URL = os.getenv("TRMNL_WEBHOOK_URL")
MBTA_API_BASE = "https://api-v3.mbta.com"

# Headers for MBTA API
HEADERS = {"x-api-key": MBTA_API_KEY} if MBTA_API_KEY else {}

# API request timeout
REQUEST_TIMEOUT = aiohttp.ClientTimeout(total=10)  # 10 seconds timeout

# API Security
API_KEY = os.getenv("API_KEY")
if not API_KEY:
    logger.warning("API_KEY not set in environment variables. API endpoints will be unprotected!")

api_key_header = APIKeyHeader(name="X-API-Key", auto_error=False)


async def verify_api_key(api_key: str = Security(api_key_header)):
    """Verify the API key."""
    if not API_KEY:
        return  # Skip validation if API_KEY is not set
    if not api_key:
        raise HTTPException(
            status_code=401,
            detail="Missing API Key",
            headers={"WWW-Authenticate": "ApiKey"},
        )
    if api_key != API_KEY:
        raise HTTPException(
            status_code=403,
            detail="Invalid API Key",
            headers={"WWW-Authenticate": "ApiKey"},
        )
    return api_key


def safe_save_config(config: RouteConfig):
    """Save configuration to file with proper locking."""
    try:
        os.makedirs(os.path.dirname(CONFIG_FILE), exist_ok=True)
        with open(CONFIG_FILE, "w") as f:
            # Get an exclusive lock
            fcntl.flock(f.fileno(), fcntl.LOCK_EX)
            try:
                json.dump(config.dict(), f, indent=2)
            finally:
                # Release the lock
                fcntl.flock(f.fileno(), fcntl.LOCK_UN)
    except IOError as e:
        logger.error(f"Error saving config: {str(e)}")
        raise HTTPException(status_code=500, detail="Could not save configuration")


def safe_load_config() -> RouteConfig:
    """Load configuration from file with proper error handling."""
    try:
        if not os.path.exists(CONFIG_FILE):
            default_config = RouteConfig(route_id="Red")
            safe_save_config(default_config)
            return default_config

        with open(CONFIG_FILE, "r") as f:
            # Get a shared lock for reading
            fcntl.flock(f.fileno(), fcntl.LOCK_SH)
            try:
                config_data = json.load(f)
            finally:
                # Release the lock
                fcntl.flock(f.fileno(), fcntl.LOCK_UN)
            return RouteConfig(**config_data)
    except (IOError, json.JSONDecodeError) as e:
        logger.error(f"Error loading config: {str(e)}")
        raise HTTPException(status_code=500, detail="Could not load configuration")


async def get_stop_info(stop_id: str) -> str:
    """Fetch stop name from MBTA API."""
    if not VALID_STOP_PATTERN.match(stop_id):
        logger.warning(f"Invalid stop_id format: {stop_id}")
        return "Invalid Stop"

    async with aiohttp.ClientSession(timeout=REQUEST_TIMEOUT) as session:
        async with session.get(f"{MBTA_API_BASE}/stops/{stop_id}", headers=HEADERS) as response:
            if response.status != 200:
                return stop_id
            data = await response.json()
            return data.get("data", {}).get("attributes", {}).get("name", stop_id)


async def get_route_stops(route_id: str) -> List[str]:
    """Fetch all stops for a given route from MBTA API."""
    async with aiohttp.ClientSession() as session:
        async with session.get(
            f"{MBTA_API_BASE}/stops", params={"filter[route]": route_id}, headers=HEADERS
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
        "include": "route,stop",
    }

    async with aiohttp.ClientSession() as session:
        async with session.get(
            f"{MBTA_API_BASE}/predictions", params=params, headers=HEADERS
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
                        status=attributes.get("status"),
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
            },
            headers=HEADERS,
        ) as response:
            if response.status != 200:
                return {}
            data = await response.json()
            return {
                stop["attributes"]["name"]: {
                    "latitude": stop["attributes"]["latitude"],
                }
                for stop in data.get("data", [])
            }


async def update_trmnl_display(predictions: List[Prediction]):
    """Send updates to TRMNL display via webhook."""
    if not TRMNL_WEBHOOK_URL:
        logger.error("Error: TRMNL webhook URL not configured")
        raise HTTPException(status_code=500, detail="TRMNL webhook URL not configured")

    config = safe_load_config()
    logger.info(f"Current route config: {config.route_id}")

    # Get predictions for each stop and direction
    stop_predictions = {}
    for pred in predictions:
        departure = pred.departure_time or pred.arrival_time
        if departure:
            dt = datetime.fromisoformat(departure.replace("Z", "+00:00"))
            stop_name = await get_stop_info(pred.stop_id)
            # MBTA API: direction_id 0 = outbound, 1 = inbound
            direction = "inbound" if pred.direction_id == 1 else "outbound"

            logger.info(
                f"Stop: {stop_name}, Direction ID: {pred.direction_id}, Direction: {direction}, Time: {dt.strftime('%I:%M %p')}"
            )

            if stop_name not in stop_predictions:
                stop_predictions[stop_name] = {
                    "stop_name": stop_name,
                    "inbound": [],
                    "outbound": [],
                }

            # Add prediction with timestamp for sorting
            if len(stop_predictions[stop_name][direction]) < 3:
                prediction_data = {
                    "time": dt.strftime("%I:%M %p"),
                    "timestamp": dt.timestamp(),
                    "status": pred.status or "Scheduled",
                }
                stop_predictions[stop_name][direction].append(prediction_data)

                # Sort predictions by timestamp
                stop_predictions[stop_name][direction].sort(key=lambda x: x["timestamp"])

    # Get stop locations and determine line direction
    stop_locations = await get_stop_locations(config.route_id)
    sorted_stops = list(stop_predictions.values())  # Default to unsorted
    if stop_locations:
        # Sort stops from north to south
        sorted_stops = sorted(
            stop_predictions.values(),
            key=lambda x: -stop_locations.get(x["stop_name"], {"latitude": 0})["latitude"],
        )

    # Create numbered variables for each stop
    merge_vars = {
        "line_name": config.route_id,
        "line_color": get_line_color(config.route_id),
        "last_updated": datetime.now().strftime("%I:%M %p"),
    }

    # Add numbered stop variables with inbound/outbound times
    for i, stop in enumerate(sorted_stops):
        merge_vars[f"stop_{i}_name"] = stop["stop_name"]

        # Add sorted inbound times
        for j, pred in enumerate(sorted(stop["inbound"], key=lambda x: x["timestamp"])[:3], 1):
            merge_vars[f"stop_{i}_inbound_{j}"] = pred["time"]

        # Add sorted outbound times
        for j, pred in enumerate(sorted(stop["outbound"], key=lambda x: x["timestamp"])[:3], 1):
            merge_vars[f"stop_{i}_outbound_{j}"] = pred["time"]

    merge_vars["stop_count"] = len(sorted_stops)

    template_data = {"merge_variables": merge_vars}

    logger.info(f"Sending update to TRMNL: {template_data}")

    async with aiohttp.ClientSession() as session:
        try:
            response = await session.post(
                TRMNL_WEBHOOK_URL, json=template_data, headers={"Content-Type": "application/json"}
            )
            logger.info(f"TRMNL response status: {response.status}")
            response_text = await response.text()
            logger.info(f"TRMNL response body: {response_text}")

            if response.status != 200:
                logger.error(f"TRMNL error response: {response_text}")
        except Exception as e:
            logger.error(f"Error sending to TRMNL: {str(e)}")


def get_line_color(route_id: str) -> str:
    """Return the color code for a given MBTA line."""
    colors = {
        "Red": "#FA2D27",
        "Orange": "#FFA500",
        "Green-B": "#00843D",
        "Green-C": "#00843D",
        "Green-D": "#00843D",
        "Green-E": "#00843D",
        "Blue": "#2F5DA6",
    }
    return colors.get(route_id, "#666666")  # Default gray if line not found


@app.get("/config", response_model=RouteConfig)
@limiter.limit("60/minute")
async def get_config(request: Request, api_key: str = Depends(verify_api_key)):
    """Get current configuration."""
    return safe_load_config()


@app.post("/config")
@limiter.limit("10/minute")
async def update_config(
    config: RouteConfig, request: Request, api_key: str = Depends(verify_api_key)
):
    """Update configuration."""
    safe_save_config(config)
    return {"status": "success", "route": config.route_id}


@app.post("/webhook/update")
@limiter.limit("30/minute")
async def update_schedule(request: Request, api_key: str = Depends(verify_api_key)):
    """Manually trigger an update of the schedule display."""
    config = safe_load_config()
    predictions = await fetch_predictions(config.route_id)
    await update_trmnl_display(predictions)
    return {"status": "success", "predictions_count": len(predictions)}


async def update_loop():
    """Main loop to update the display periodically"""
    while True:
        try:
            print("Fetching new predictions...")
            config = safe_load_config()
            predictions = await fetch_predictions(config.route_id)
            print(f"Got {len(predictions)} predictions")
            await update_trmnl_display(predictions)
            await asyncio.sleep(30)
        except Exception as e:
            print(f"Error in update loop: {str(e)}")
            await asyncio.sleep(5)


async def run_once():
    """Run a single update and exit."""
    try:
        current_time = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        print(f"\n[{current_time}] Starting update...")
        config = safe_load_config()
        predictions = await fetch_predictions(config.route_id)
        print(f"Got {len(predictions)} predictions")
        await update_trmnl_display(predictions)
        print("Update complete")
    except Exception as e:
        print(f"Error in update: {str(e)}")
        raise e


# Create default config file if it doesn't exist
if not os.path.exists(CONFIG_FILE):
    safe_save_config(RouteConfig(route_id="Red"))
