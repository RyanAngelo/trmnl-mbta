import logging
from datetime import datetime
from typing import List, Dict, Any
import aiohttp

from src.mbta.constants import MBTA_API_BASE, HEADERS
from src.mbta.models import Prediction

logger = logging.getLogger(__name__)

# API request timeout
REQUEST_TIMEOUT = aiohttp.ClientTimeout(total=10)  # 10 seconds timeout

async def get_stop_info(stop_id: str) -> str:
    """Get stop name from stop ID."""
    async with aiohttp.ClientSession(timeout=REQUEST_TIMEOUT) as session:
        async with session.get(
            f"{MBTA_API_BASE}/stops/{stop_id}",
            headers=HEADERS
        ) as response:
            if response.status == 200:
                data = await response.json()
                return data["data"]["attributes"]["name"]
            else:
                logger.error(f"Error fetching stop info: {response.status}")
                return stop_id

async def get_route_stops(route_id: str) -> List[str]:
    """Get all stops for a route."""
    async with aiohttp.ClientSession(timeout=REQUEST_TIMEOUT) as session:
        async with session.get(
            f"{MBTA_API_BASE}/stops?filter[route]={route_id}",
            headers=HEADERS
        ) as response:
            data = await response.json()
            return [stop["id"] for stop in data["data"]]

async def get_scheduled_times(route_id: str) -> List[Dict[str, Any]]:
    """Fetch scheduled service times from MBTA API."""
    params = {
        "filter[route]": route_id,
        "filter[date]": datetime.now().strftime("%Y-%m-%d"),
        "sort": "departure_time",
        "include": "route,stop",
    }

    async with aiohttp.ClientSession(timeout=REQUEST_TIMEOUT) as session:
        async with session.get(
            f"{MBTA_API_BASE}/schedules", params=params, headers=HEADERS
        ) as response:
            if response.status != 200:
                logger.warning(f"Failed to fetch scheduled times: {response.status}")
                return []
            data = await response.json()
            return data.get("data", [])

async def fetch_predictions(route_id: str) -> List[Prediction]:
    """Fetch predictions for a route."""
    url = f"{MBTA_API_BASE}/predictions"
    params = {
        "filter[route]": route_id,
        "include": "stop",
        "sort": "stop_sequence",
        "page[limit]": 100
    }

    async with aiohttp.ClientSession(timeout=REQUEST_TIMEOUT) as session:
        async with session.get(url, params=params, headers=HEADERS) as response:
            if response.status != 200:
                logger.error(f"Error fetching predictions: {response.status}")
                return []

            data = await response.json()
            predictions = []
            for pred in data["data"]:
                prediction = Prediction(
                    route_id=pred["relationships"]["route"]["data"]["id"],
                    stop_id=pred["relationships"]["stop"]["data"]["id"],
                    arrival_time=pred["attributes"].get("arrival_time"),
                    departure_time=pred["attributes"].get("departure_time"),
                    direction_id=pred["attributes"]["direction_id"],
                    status=pred["attributes"].get("status")
                )
                predictions.append(prediction)
            return predictions

async def get_stop_locations(route_id: str) -> dict:
    """Get stop locations for a route."""
    async with aiohttp.ClientSession(timeout=REQUEST_TIMEOUT) as session:
        async with session.get(
            f"{MBTA_API_BASE}/stops?filter[route]={route_id}",
            headers=HEADERS
        ) as response:
            if response.status == 200:
                data = await response.json()
                return {
                    stop["id"]: stop["attributes"]["name"]
                    for stop in data["data"]
                }
            else:
                logger.error(f"Error fetching stop locations: {response.status}")
                return {} 