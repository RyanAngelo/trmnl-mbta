# Standard library imports
import asyncio
import fcntl
import json
import logging
import os
import re
from contextlib import asynccontextmanager
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional, Pattern, Tuple

# Third-party imports
import aiohttp
from dotenv import load_dotenv
from fastapi import Depends, FastAPI, HTTPException, Request, Security
from fastapi.middleware.cors import CORSMiddleware
from fastapi.security import APIKeyHeader
from slowapi import Limiter, _rate_limit_exceeded_handler
from slowapi.errors import RateLimitExceeded
from slowapi.util import get_remote_address

# Local imports
from src.mbta.api import get_scheduled_times
from src.mbta.models import RouteConfig, Prediction
from src.mbta.constants import (
    ALLOWED_ORIGINS, DEBUG_MODE, MBTA_API_KEY, TRMNL_WEBHOOK_URL, API_KEY,
    MBTA_API_BASE, HEADERS, TEMPLATE_PATH, CONFIG_FILE, VALID_ROUTE_PATTERN,
    VALID_STOP_PATTERN, STOP_ORDER
)

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    handlers=[logging.FileHandler("mbta.log"), logging.StreamHandler()],
)
logger = logging.getLogger(__name__)

# Load environment variables
load_dotenv()

# Configure rate limiter
limiter = Limiter(key_func=get_remote_address)

# Debug mode flag
DEBUG_MODE = os.getenv("DEBUG_MODE", "false").lower() == "true"

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

# Stop order for each line (inbound direction)
STOP_ORDER = {
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
    ],
    "Red": [
        "Alewife",
        "Davis",
        "Porter",
        "Harvard",
        "Central",
        "Kendall/MIT",
        "Charles/MGH",
        "Park Street",
        "Downtown Crossing",
        "South Station",
        "Broadway",
        "Andrew",
        "JFK/UMass",
        "Savin Hill",
        "Fields Corner",
        "Shawmut",
        "Ashmont",
        "North Quincy",
        "Wollaston",
        "Quincy Center",
        "Quincy Adams",
        "Braintree"
    ],
    "Blue": [
        "Wonderland",
        "Revere Beach",
        "Beachmont",
        "Suffolk Downs",
        "Orient Heights",
        "Wood Island",
        "Airport",
        "Maverick",
        "Bowdoin",
        "Government Center",
        "State",
        "Aquarium",
        "Maverick"
    ]
}

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


_stop_info_cache = {}  # Cache for stop information


async def get_stop_info(stop_id: str) -> str:
    """Get stop information from the MBTA API."""
    if stop_id in _stop_info_cache:
        return _stop_info_cache[stop_id]
    try:
        async with aiohttp.ClientSession() as session:
            async with session.get(f"{MBTA_API_BASE}/stops/{stop_id}", headers=HEADERS) as response:
                if response.status == 200:
                    data = await response.json()
                    stop_name = data["data"]["attributes"]["name"]
                    _stop_info_cache[stop_id] = stop_name
                    return stop_name
                else:
                    logger.warning(f"Invalid stop_id format: {stop_id}")
                    return "Unknown Stop"
    except Exception as e:
        logger.error(f"Error fetching stop info: {str(e)}")
        return "Unknown Stop"


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


async def update_trmnl_display(
    line_name: str,
    last_updated: str,
    stop_predictions: Dict[str, Dict[str, List[str]]],
    stop_names: Dict[str, str],
) -> None:
    """Update the TRMNL display with the latest predictions.

    The function uses a compact variable naming scheme for the template:

    Header Variables:
    - l: Line name (e.g., "Red", "Orange", "Blue")
    - u: Last updated time in short format (e.g., "2:15p")

    Stop Variables (where X is the stop index from 0-11):
    - nX: Stop name (e.g., "n0" = "Assembly")
    - iX1: First inbound prediction time (e.g., "i01" = "2:15p")
    - iX2: Second inbound prediction time (e.g., "i02" = "2:30p")
    - iX3: Third inbound prediction time (e.g., "i03" = "2:45p")
    - oX1: First outbound prediction time (e.g., "o01" = "2:20p")
    - oX2: Second outbound prediction time (e.g., "o02" = "2:35p")
    - oX3: Third outbound prediction time (e.g., "o03" = "2:50p")

    Example for Assembly station (index 0):
    - n0: "Assembly"
    - i01: "2:15p" (first inbound train)
    - i02: "2:30p" (second inbound train)
    - i03: "2:45p" (third inbound train)
    - o01: "2:20p" (first outbound train)
    - o02: "2:35p" (second outbound train)
    - o03: "2:50p" (third outbound train)
    """
    # Initialize base variables for the template
    merge_vars = {
        "l": line_name,  # Line name (e.g., "Orange")
        "u": convert_to_short_time(last_updated),  # Last updated time (e.g., "2:15p")
    }

    # Get the ordered stops for this route
    ordered_stops = STOP_ORDER.get(line_name, [])
    
    # Create a mapping of stop names to their IDs
    name_to_id = {name: stop_id for stop_id, name in stop_names.items()}
    
    # Process stops in the correct order
    for stop_idx, stop_name in enumerate(ordered_stops[:12]):  # Limit to 12 stops
        if stop_name in name_to_id:
            stop_id = name_to_id[stop_name]
            predictions = stop_predictions.get(stop_id, {"inbound": [], "outbound": []})

            # Add stop name: nX where X is the stop index (0-11)
            merge_vars[f"n{stop_idx}"] = stop_name

            # Add predictions for each direction
            for direction in ["inbound", "outbound"]:
                # i for inbound, o for outbound
                direction_letter = "i" if direction == "inbound" else "o"

                # Add up to 3 predictions per direction
                # Format: [i|o]X[1|2|3] where:
                # - i/o is the direction
                # - X is the stop index (0-11)
                # - 1/2/3 is the prediction number
                for i in range(1, 4):  # Always create 3 slots for each direction
                    if i <= len(predictions[direction]):
                        merge_vars[f"{direction_letter}{stop_idx}{i}"] = convert_to_short_time(predictions[direction][i-1])
                    else:
                        merge_vars[f"{direction_letter}{stop_idx}{i}"] = ""  # Empty string for no prediction

    # If in debug mode, output to log instead of sending to TRMNL
    if DEBUG_MODE:
        debug_output = format_debug_output(merge_vars, line_name)
        logger.info("Debug output:\n%s", debug_output)
        return

    # Implement exponential backoff for rate limiting
    base_delay = 1  # Start with 1 second delay
    max_delay = 900  # Maximum delay of 15 minutes (900 seconds)
    max_attempts = 5  # Maximum number of retry attempts
    attempt = 0

    while attempt < max_attempts:  # Limit retries to max_attempts
        async with aiohttp.ClientSession(timeout=REQUEST_TIMEOUT) as session:
            try:
                logger.info("Sending update to TRMNL: {'merge_variables': %s}", merge_vars)
                response = await session.post(
                    TRMNL_WEBHOOK_URL,
                    headers={"Content-Type": "application/json"},
                    json={"merge_variables": merge_vars},
                )

                response_text = await response.text()
                logger.info("TRMNL response status: %d", response.status)
                logger.info("TRMNL response body: %s", response_text)

                if response.status == 200:
                    return  # Success, exit the function
                elif response.status == 429:  # Too Many Requests
                    # Get retry delay from header or calculate exponential backoff
                    retry_after = response.headers.get("Retry-After")
                    if retry_after:
                        try:
                            delay = int(retry_after)
                        except ValueError:
                            delay = min(base_delay * (2**attempt), max_delay)
                    else:
                        delay = min(base_delay * (2**attempt), max_delay)

                    if attempt < max_attempts - 1:  # Only log warning if we're going to retry
                        logger.warning(
                            "Rate limited by TRMNL. Retrying in %d seconds... (Attempt %d)",
                            delay,
                            attempt + 1,
                        )
                        await asyncio.sleep(delay)
                else:
                    logger.error(
                        "Unexpected response from TRMNL: %d - %s", response.status, response_text
                    )
                    if attempt < max_attempts - 1:  # Only retry if not last attempt
                        delay = min(base_delay * (2**attempt), max_delay)
                        await asyncio.sleep(delay)

            except Exception as e:
                logger.error("Error sending to TRMNL: %s", str(e))
                if attempt < max_attempts - 1:  # Only retry if not last attempt
                    delay = min(base_delay * (2**attempt), max_delay)
                    await asyncio.sleep(delay)

            attempt += 1

    # If we've exhausted all retries, log a final error
    if attempt >= max_attempts:
        logger.error("Failed to update TRMNL display after %d attempts", max_attempts)


def format_debug_output(merge_vars: Dict[str, str], line_name: str) -> str:
    """Format debug output in a readable way for console or file."""
    now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    output = [
        f"=== {line_name} Line Predictions ({now}) ===",
        f"Last Updated: {merge_vars.get('u', 'N/A')}",
        "",
        "Stop Name          | Inbound 1 | Outbound 1 | Inbound 2 | Outbound 2 | Inbound 3 | Outbound 3",
        "------------------|-----------|------------|-----------|------------|-----------|------------"
    ]
    
    # Get the ordered stops for this line
    ordered_stops = STOP_ORDER.get(line_name, [])
    
    # Process each stop in the correct order
    for stop_name in ordered_stops[:12]:  # Limit to 12 stops
        # Find the index of this stop in the merge_vars
        stop_idx = None
        for i in range(12):
            if merge_vars.get(f"n{i}", "") == stop_name:
                stop_idx = i
                break
        
        if stop_idx is None:
            continue
            
        # Get predictions for this stop
        inbound1 = merge_vars.get(f"i{stop_idx}1", "")
        outbound1 = merge_vars.get(f"o{stop_idx}1", "")
        inbound2 = merge_vars.get(f"i{stop_idx}2", "")
        outbound2 = merge_vars.get(f"o{stop_idx}2", "")
        inbound3 = merge_vars.get(f"i{stop_idx}3", "")
        outbound3 = merge_vars.get(f"o{stop_idx}3", "")
        
        # Format the line
        line = f"{stop_name:<18} | {inbound1:>9} | {outbound1:>10} | {inbound2:>9} | {outbound2:>10} | {inbound3:>9} | {outbound3:>10}"
        output.append(line)
    
    return "\n".join(output)


def convert_to_short_time(time_str: str) -> str:
    """Convert time from '01:29 PM' to '1:29p' format or '01:29 AM' to '1:29a' format."""
    try:
        time_obj = datetime.strptime(time_str, "%I:%M %p")
        period = "a" if time_obj.strftime("%p") == "AM" else "p"
        return time_obj.strftime("%-I:%M") + period  # %-I removes leading zero
    except ValueError:
        return time_str  # Return original if parsing fails


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
    return {"status": "success"}


async def process_predictions(
    predictions: List[Prediction],
) -> Tuple[Dict[str, Dict[str, List[str]]], Dict[str, str]]:
    """Process predictions into a format suitable for display."""
    stop_predictions = {}  # type: Dict[str, Dict[str, List[str]]]
    stop_names = {}  # type: Dict[str, str]
    
    # Get the route ID from the first prediction or use default
    route_id = predictions[0].route_id if predictions else "Orange"  # Default to Orange if no predictions
    
    # Get the ordered stops for this route
    ordered_stops = STOP_ORDER.get(route_id, [])
    
    # First, get all stop information in parallel if we have predictions
    if predictions:
        unique_stop_ids = {pred.stop_id for pred in predictions}
        await asyncio.gather(*[get_stop_info(stop_id) for stop_id in unique_stop_ids])
    
    # Group predictions by stop and direction
    stop_times = {}  # type: Dict[str, Dict[str, List[str]]]
    for pred in predictions:
        departure = pred.departure_time or pred.arrival_time
        if departure:
            stop_name = _stop_info_cache.get(pred.stop_id, "Unknown Stop")
            if stop_name == "Unknown Stop":
                continue
            if stop_name not in stop_times:
                stop_times[stop_name] = {"inbound": [], "outbound": []}
            dt = datetime.fromisoformat(departure.replace("Z", "+00:00"))
            time_str = dt.strftime("%I:%M %p")
            # Swap direction mapping: 0 = outbound (toward Oak Grove), 1 = inbound (toward Forest Hills)
            direction = "outbound" if pred.direction_id == 0 else "inbound"
            stop_times[stop_name][direction].append(time_str)
    
    # Always fetch scheduled times to fill gaps when we don't have enough real-time predictions
    logger.info("Fetching scheduled times to supplement real-time predictions")
    scheduled_times = await get_scheduled_times(route_id)
    
    # Process each stop in the correct order, even if there are no predictions
    for stop_idx, stop_name in enumerate(ordered_stops[:12]):  # Limit to 12 stops
        stop_id = f"stop_{stop_idx}"
        stop_names[stop_id] = stop_name
        stop_predictions[stop_id] = {"inbound": [], "outbound": []}
        
        if stop_name in stop_times:
            for direction in ["inbound", "outbound"]:
                real_times = []
                scheduled_times_list = []
                seen_times = set()
                for time_str in stop_times[stop_name][direction][:]:
                    try:
                        # Parse the time string and create a timezone-aware datetime for comparison
                        time_obj = datetime.strptime(time_str, "%I:%M %p")
                        # Assume the time is in the same timezone as the current date
                        # We'll use the date from the first scheduled time if available
                        if scheduled_times:
                            first_scheduled = scheduled_times[0].get("attributes", {}).get("departure_time")
                            if first_scheduled:
                                # Extract the date from the first scheduled time
                                scheduled_dt = datetime.fromisoformat(first_scheduled.replace("Z", "+00:00"))
                                # Combine the date from scheduled time with the time from real-time
                                time_obj = time_obj.replace(
                                    year=scheduled_dt.year,
                                    month=scheduled_dt.month,
                                    day=scheduled_dt.day,
                                    tzinfo=scheduled_dt.tzinfo
                                )
                        if time_str not in seen_times:
                            real_times.append((time_obj, time_str))
                            seen_times.add(time_str)
                    except ValueError:
                        if time_str not in seen_times:
                            real_times.append((None, time_str))
                            seen_times.add(time_str)
                # Sort real-time
                real_times_sorted = sorted(real_times, key=lambda x: x[0] if x[0] else x[1])
                combined = [t[1] for t in real_times_sorted]
                latest_real_time = real_times_sorted[-1][0] if real_times_sorted else None
                # Now, collect scheduled times (from scheduled_times) that are later than the latest real-time
                for schedule in scheduled_times:
                    attributes = schedule.get("attributes", {})
                    departure = attributes.get("departure_time")
                    if departure:
                        stop_id_sched = schedule["relationships"]["stop"]["data"]["id"]
                        stop_name_sched = _stop_info_cache.get(stop_id_sched, "Unknown Stop")
                        if stop_name_sched == stop_name:
                            dt = datetime.fromisoformat(departure.replace("Z", "+00:00"))
                            time_str = dt.strftime("%I:%M %p")
                            direction_sched = "outbound" if attributes.get("direction_id", 0) == 0 else "inbound"
                            if direction_sched == direction and time_str not in seen_times:
                                # Ensure both datetimes are timezone-aware for comparison
                                if latest_real_time is None:
                                    # If no real-time predictions, include all scheduled times
                                    scheduled_times_list.append((dt, time_str))
                                    seen_times.add(time_str)
                                elif latest_real_time.tzinfo is None:
                                    # If latest_real_time is naive, assume it's in the same timezone as dt
                                    latest_real_time = latest_real_time.replace(tzinfo=dt.tzinfo)
                                    if dt > latest_real_time:
                                        scheduled_times_list.append((dt, time_str))
                                        seen_times.add(time_str)
                                else:
                                    # Both are timezone-aware, compare directly
                                    if dt > latest_real_time:
                                        scheduled_times_list.append((dt, time_str))
                                        seen_times.add(time_str)
                scheduled_times_sorted = sorted(scheduled_times_list, key=lambda x: x[0] if x[0] else x[1])
                if len(combined) < 3:
                    combined += [t[1] for t in scheduled_times_sorted[:3-len(combined)]]
                stop_predictions[stop_id][direction] = combined[:3]
        else:
            continue
    
    return stop_predictions, stop_names


async def update_display(predictions: List[Prediction]) -> None:
    """Process predictions and update the TRMNL display."""
    if not TRMNL_WEBHOOK_URL:
        logger.error("Error: TRMNL webhook URL not configured")
        raise HTTPException(status_code=500, detail="TRMNL webhook URL not configured")

    config = safe_load_config()
    logger.info(f"Current route config: {config.route_id}")

    stop_predictions, stop_names = await process_predictions(predictions)

    await update_trmnl_display(
        line_name=config.route_id,
        last_updated=datetime.now().strftime("%I:%M %p"),
        stop_predictions=stop_predictions,
        stop_names=stop_names,
    )


@app.post("/webhook")
async def webhook(request: Request) -> Dict[str, Any]:
    """Handle incoming webhooks from MBTA."""
    config = safe_load_config()
    predictions = await fetch_predictions(config.route_id)
    await update_display(predictions)
    return {"status": "success", "predictions_count": len(predictions)}


async def update_loop() -> None:
    """Main update loop."""
    while True:
        try:
            await run_once()
        except Exception as e:
            logger.error(f"Error in update loop: {str(e)}")
        await asyncio.sleep(30)  # Update every 30 seconds


async def run_once() -> None:
    """Run one update cycle."""
    try:
        config = safe_load_config()
        predictions = await fetch_predictions(config.route_id)
        print(f"Got {len(predictions)} predictions")
        await update_display(predictions)
        print("Update complete")
    except Exception as e:
        logger.error(f"Error running once: {str(e)}")


# Create default config file if it doesn't exist
if not os.path.exists(CONFIG_FILE):
    safe_save_config(RouteConfig(route_id="Red"))
