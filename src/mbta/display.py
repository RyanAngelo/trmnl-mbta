import logging
from datetime import datetime
from typing import Dict, List, Any, Tuple
import aiohttp
import asyncio

from src.mbta.constants import TEMPLATE_PATH, TRMNL_WEBHOOK_URL, DEBUG_MODE, STOP_ORDER
from src.mbta.models import Prediction
from src.mbta.api import get_stop_info, get_scheduled_times

logger = logging.getLogger(__name__)

# Cache for stop information
_stop_info_cache = {}

def convert_to_short_time(time_str: str) -> str:
    """Convert ISO time string to short format (e.g., '2:15p')."""
    if not time_str:
        return ""
    dt = datetime.fromisoformat(time_str.replace("Z", "+00:00"))
    local_time = dt.astimezone()
    return local_time.strftime("%-I:%M%p").lower().replace(":00", "")

def get_line_color(route_id: str) -> str:
    """Get the color for a line."""
    colors = {
        "Red": "#FA2D27",
        "Orange": "#FD8A03",
        "Blue": "#2F5DA6",
        "Green-B": "#00843D",
        "Green-C": "#00843D",
        "Green-D": "#00843D",
        "Green-E": "#00843D"
    }
    return colors.get(route_id, "#000000")

async def update_trmnl_display(
    line_name: str,
    line_color: str,
    last_updated: str,
    stop_predictions: Dict[str, Dict[str, List[str]]],
    stop_names: Dict[str, str],
) -> None:
    """Update the TRMNL display with new predictions."""
    if not TEMPLATE_PATH.exists():
        logger.error(f"Template file not found: {TEMPLATE_PATH}")
        return

    with open(TEMPLATE_PATH, "r") as f:
        template = f.read()

    # Replace variables in template
    merge_vars = {
        "l": line_name,  # Line name
        "c": line_color,  # Line color
        "u": last_updated,  # Last updated time
    }

    # Add stop predictions
    for i, (stop_id, predictions) in enumerate(stop_predictions.items()):
        stop_name = stop_names.get(stop_id, stop_id)
        merge_vars[f"n{i}"] = stop_name

        # Add inbound predictions
        for j, time in enumerate(predictions.get("inbound", [])):
            merge_vars[f"i{i}{j+1}"] = time

        # Add outbound predictions
        for j, time in enumerate(predictions.get("outbound", [])):
            merge_vars[f"o{i}{j+1}"] = time

    # Fill in any missing variables with empty strings
    for i in range(12):  # Maximum 12 stops
        merge_vars.setdefault(f"n{i}", "")
        for j in range(1, 4):  # 3 predictions each direction
            merge_vars.setdefault(f"i{i}{j}", "")
            merge_vars.setdefault(f"o{i}{j}", "")

    # Replace all variables in template
    for var, value in merge_vars.items():
        template = template.replace("{{" + var + "}}", value)

    if DEBUG_MODE:
        # In debug mode, output to console instead of sending to TRMNL
        debug_output = format_debug_output(merge_vars, line_name)
        logger.info(f"Debug output:\n{debug_output}")
        return

    # Send to TRMNL
    if not TRMNL_WEBHOOK_URL:
        logger.error("TRMNL_WEBHOOK_URL not set")
        return

    try:
        async with aiohttp.ClientSession() as session:
            async with session.post(
                TRMNL_WEBHOOK_URL,
                json={"html": template}
            ) as response:
                if response.status != 200:
                    logger.error(f"Error updating TRMNL display: {response.status}")
    except Exception as e:
        logger.error(f"Error sending update to TRMNL: {str(e)}")

def format_debug_output(merge_vars: Dict[str, str], line_name: str) -> str:
    """Format predictions for debug output."""
    now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    output = [
        f"=== {line_name} Line Predictions ({now}) ===",
        f"Last Updated: {merge_vars['u']}\n",
        "Stop Name          | Inbound 1 | Outbound 1 | Inbound 2 | Outbound 2 | Inbound 3 | Outbound 3"
        "-" * 80
    ]

    for i in range(12):
        stop_name = merge_vars.get(f"n{i}", "")
        if not stop_name:
            continue

        row = [
            f"{stop_name:<16}",
            f"{merge_vars.get(f'i{i}1', ''):<10}",
            f"{merge_vars.get(f'o{i}1', ''):<11}",
            f"{merge_vars.get(f'i{i}2', ''):<10}",
            f"{merge_vars.get(f'o{i}2', ''):<11}",
            f"{merge_vars.get(f'i{i}3', ''):<10}",
            f"{merge_vars.get(f'o{i}3', ''):<10}"
        ]
        output.append(" | ".join(row))

    return "\n".join(output)

async def process_predictions(
    predictions: List[Prediction],
) -> Tuple[Dict[str, Dict[str, List[str]]], Dict[str, str]]:
    """Process predictions into a format suitable for display."""
    stop_predictions: Dict[str, Dict[str, List[str]]] = {}
    stop_names: Dict[str, str] = {}

    # Get the route ID from the first prediction or use default
    route_id = predictions[0].route_id if predictions else "Orange"  # Default to Orange if no predictions

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
                stop_times[stop_name] = {"0": [], "1": []}
            dt = datetime.fromisoformat(departure.replace("Z", "+00:00"))
            time_str = dt.strftime("%I:%M %p")
            direction = str(pred.direction_id)
            stop_times[stop_name][direction].append(time_str)

    # If no real-time predictions, try to get scheduled times
    if not predictions:
        logger.info("No real-time predictions available, fetching scheduled times")
        scheduled_times = await get_scheduled_times(route_id)
        
        # Process scheduled times
        for schedule in scheduled_times:
            attributes = schedule.get("attributes", {})
            departure = attributes.get("departure_time")
            if departure:
                stop_id = schedule["relationships"]["stop"]["data"]["id"]
                stop_name = _stop_info_cache.get(stop_id, "Unknown Stop")
                if stop_name == "Unknown Stop":
                    continue
                if stop_name not in stop_times:
                    stop_times[stop_name] = {"0": [], "1": []}
                dt = datetime.fromisoformat(departure.replace("Z", "+00:00"))
                time_str = dt.strftime("%I:%M %p")
                direction = str(attributes.get("direction_id", 0))
                stop_times[stop_name][direction].append(time_str)

    # Process each stop in the correct order, even if there are no predictions
    for stop_idx, stop_name in enumerate(STOP_ORDER.get(route_id, [])[:12]):  # Limit to 12 stops
        # Generate a unique stop ID for this stop
        stop_id = f"stop_{stop_idx}"
        stop_names[stop_id] = stop_name
        stop_predictions[stop_id] = {"0": [], "1": []}
        
        # If we have predictions for this stop, add them
        if stop_name in stop_times:
            # Sort times for each direction
            for direction in ["0", "1"]:
                times = sorted(stop_times[stop_name][direction])
                # Take up to 3 predictions for each direction
                stop_predictions[stop_id][direction] = times[:3]

    return stop_predictions, stop_names 