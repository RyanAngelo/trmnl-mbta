import logging
from datetime import datetime
from typing import Dict, List, Any, Tuple
import aiohttp
import asyncio

from src.mbta.constants import TEMPLATE_PATH, TRMNL_WEBHOOK_URL, DEBUG_MODE, STOP_ORDER, MAX_PREDICTIONS_PER_DIRECTION
from src.mbta.models import Prediction
from src.mbta.api import get_stop_info, get_scheduled_times, get_route_stops

logger = logging.getLogger(__name__)

# Cache for stop information
_stop_info_cache = {}

def convert_to_short_time(time_str: str) -> str:
    """Convert ISO time string to short format (e.g., '2:15p')."""
    if not time_str:
        return ""
    try:
        dt = datetime.fromisoformat(time_str.replace("Z", "+00:00"))
        local_time = dt.astimezone()
        return local_time.strftime("%-I:%M%p").lower().replace(":00", "")
    except ValueError:
        # Return original string if it's not a valid ISO format
        return time_str

async def update_trmnl_display(
    line_name: str,
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
        for j in range(1, MAX_PREDICTIONS_PER_DIRECTION + 1):  # 3 predictions each direction
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

async def get_bus_stop_order(route_id: str) -> List[str]:
    """Get the stop order for a bus route from the MBTA API."""
    try:
        stops = await get_route_stops(route_id)
        stop_names = []
        
        # Get stop names for all stops
        for stop_id in stops:
            stop_name = await get_stop_info(stop_id)
            if stop_name and stop_name != "Unknown Stop":
                stop_names.append(stop_name)
        
        return stop_names
    except Exception as e:
        logger.error(f"Error getting bus stop order for route {route_id}: {str(e)}")
        return []

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
        logger.info(f"Loading stop information for {len(unique_stop_ids)} unique stops from predictions: {list(unique_stop_ids)[:5]}...")
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
    logger.info(f"Retrieved {len(scheduled_times)} scheduled times for processing")
    
    # Get stop information for all stops in scheduled times
    if scheduled_times:
        unique_stop_ids = {schedule["relationships"]["stop"]["data"]["id"] for schedule in scheduled_times}
        logger.info(f"Loading stop information for {len(unique_stop_ids)} unique stops from scheduled times")
        await asyncio.gather(*[get_stop_info(stop_id) for stop_id in unique_stop_ids])
    
    # Get the ordered stops for this route
    if route_id in STOP_ORDER:
        # Use predefined stop order for subway lines
        ordered_stops = STOP_ORDER[route_id]
    else:
        # For bus routes, get the stop order dynamically
        ordered_stops = await get_bus_stop_order(route_id)

    # Process each stop in the correct order, even if there are no predictions
    for stop_idx, stop_name in enumerate(ordered_stops[:12]):  # Limit to 12 stops
        # Generate a unique stop ID for this stop
        stop_id = f"stop_{stop_idx}"
        stop_names[stop_id] = stop_name
        stop_predictions[stop_id] = {"inbound": [], "outbound": []}
        
        for direction in ["inbound", "outbound"]:
            # Separate real-time and scheduled times
            real_times = []
            scheduled_times_list = []
            seen_times = set()
            
            # First, collect real-time times (from predictions) if they exist
            if stop_name in stop_times:
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
            
            # Sort real-time - filter out None values for sorting, but keep them for display
            real_times_with_datetime = [(t[0], t[1]) for t in real_times if t[0] is not None]
            real_times_without_datetime = [(t[0], t[1]) for t in real_times if t[0] is None]
            
            # Sort times with valid datetime objects
            real_times_sorted = sorted(real_times_with_datetime, key=lambda x: x[0])
            # Add times without datetime at the end (they'll be sorted alphabetically)
            real_times_sorted.extend(sorted(real_times_without_datetime, key=lambda x: x[1]))
            
            combined = [t[1] for t in real_times_sorted]
            latest_real_time = real_times_sorted[-1][0] if real_times_sorted and real_times_sorted[-1][0] is not None else None
            
            # Now, collect scheduled times (from scheduled_times) that are later than the latest real-time
            for schedule in scheduled_times:
                attributes = schedule.get("attributes", {})
                departure = attributes.get("departure_time")
                if departure:
                    stop_name_sched = schedule.get("stop_name", "Unknown Stop")
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
            
            # Sort scheduled times - filter out None values for sorting
            scheduled_times_with_datetime = [(t[0], t[1]) for t in scheduled_times_list if t[0] is not None]
            scheduled_times_without_datetime = [(t[0], t[1]) for t in scheduled_times_list if t[0] is None]
            
            # Sort times with valid datetime objects
            scheduled_times_sorted = sorted(scheduled_times_with_datetime, key=lambda x: x[0])
            # Add times without datetime at the end (they'll be sorted alphabetically)
            scheduled_times_sorted.extend(sorted(scheduled_times_without_datetime, key=lambda x: x[1]))
            if len(combined) < MAX_PREDICTIONS_PER_DIRECTION:
                combined += [t[1] for t in scheduled_times_sorted[:MAX_PREDICTIONS_PER_DIRECTION-len(combined)]]
            stop_predictions[stop_id][direction] = combined[:MAX_PREDICTIONS_PER_DIRECTION]
            
            # Log summary for this stop/direction
            logger.info(f"{stop_name} {direction}: real_times={len(real_times)}, scheduled_times={len(scheduled_times_list)}, combined={combined}")

    return stop_predictions, stop_names


def calculate_prediction_hash(predictions: List[Prediction]) -> int:
    """Calculate a hash of predictions for change detection."""
    # Convert None values to empty strings for sorting to avoid comparison errors
    prediction_tuples = sorted([
        (pred.route_id, pred.stop_id, pred.departure_time or "", pred.arrival_time or "", pred.direction_id)
        for pred in predictions
    ])
    return hash(str(prediction_tuples)) 