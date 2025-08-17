import logging
from datetime import datetime
from typing import Dict, List, Any, Tuple
import aiohttp
import asyncio

from src.mbta.constants import TEMPLATE_PATH, TRMNL_WEBHOOK_URL, DEBUG_MODE, STOP_ORDER, MAX_PREDICTIONS_PER_DIRECTION, _stop_info_cache
from src.mbta.models import Prediction
from src.mbta.api import get_stop_info, get_scheduled_times, get_route_stops

logger = logging.getLogger(__name__)

# Rate limiting for TRMNL webhooks (12 per hour = 1 every 5 minutes)
class TRMNLRateLimiter:
    def __init__(self, max_updates_per_hour: int = 12):
        self.max_updates_per_hour = max_updates_per_hour
        self.updates_this_hour = 0
        self.hour_start = datetime.now().replace(minute=0, second=0, microsecond=0)
        self.min_interval_seconds = 3600 // max_updates_per_hour  # 300 seconds = 5 minutes
        self.last_update_time = None
    
    def can_update(self) -> bool:
        """Check if we can send an update based on rate limits."""
        now = datetime.now()
        
        # Check if we've moved to a new hour
        current_hour_start = now.replace(minute=0, second=0, microsecond=0)
        if current_hour_start > self.hour_start:
            # New hour, reset counters
            self.updates_this_hour = 0
            self.hour_start = current_hour_start
            self.last_update_time = None
        
        # Check if we've hit the hourly limit
        if self.updates_this_hour >= self.max_updates_per_hour:
            logger.info(f"Rate limit reached: {self.updates_this_hour}/{self.max_updates_per_hour} updates this hour")
            return False
        
        # Check minimum interval between updates
        if self.last_update_time:
            time_since_last = (now - self.last_update_time).total_seconds()
            if time_since_last < self.min_interval_seconds:
                logger.debug(f"Rate limiting: {time_since_last:.1f}s since last update, need {self.min_interval_seconds}s")
                return False
        
        return True
    
    def record_update(self):
        """Record that an update was sent."""
        self.updates_this_hour += 1
        self.last_update_time = datetime.now()
        logger.info(f"Webhook sent: {self.updates_this_hour}/{self.max_updates_per_hour} updates this hour")

# Global rate limiter instance
_rate_limiter = TRMNLRateLimiter()

def get_rate_limit_status() -> Dict[str, Any]:
    """Get current rate limiting status for display."""
    return {
        "updates_this_hour": _rate_limiter.updates_this_hour,
        "max_updates_per_hour": _rate_limiter.max_updates_per_hour,
        "can_update": _rate_limiter.can_update(),
        "min_interval_seconds": _rate_limiter.min_interval_seconds,
        "last_update_time": _rate_limiter.last_update_time
    }

def get_line_color(line_name: str) -> str:
    """Get the hex color for a subway line."""
    colors = {
        "Red": "#FA2D27",
        "Orange": "#FF8C00", 
        "Blue": "#003DA5",
        "Green": "#00843D",
        "Silver": "#7C878E",
        "Purple": "#800080"
    }
    return colors.get(line_name, "#333333")

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

    # Build merge_variables object for TRMNL
    merge_variables = {
        "l": line_name,  # Line name
        "u": last_updated,  # Last updated time
        "c": get_line_color(line_name),  # Line color
    }

    # Add stop predictions
    for i, (stop_id, predictions) in enumerate(stop_predictions.items()):
        stop_name = stop_names.get(stop_id, stop_id)
        merge_variables[f"n{i}"] = stop_name

        # Add inbound predictions
        for j, time in enumerate(predictions.get("inbound", [])):
            merge_variables[f"i{i}{j+1}"] = time

        # Add outbound predictions
        for j, time in enumerate(predictions.get("outbound", [])):
            merge_variables[f"o{i}{j+1}"] = time

    # Fill in any missing variables with empty strings
    for i in range(12):  # Maximum 12 stops
        merge_variables.setdefault(f"n{i}", "")
        for j in range(1, MAX_PREDICTIONS_PER_DIRECTION + 1):  # 3 predictions each direction
            merge_variables.setdefault(f"i{i}{j}", "")
            merge_variables.setdefault(f"o{i}{j}", "")

    # Check rate limiting before sending to TRMNL
    if not _rate_limiter.can_update():
        # Rate limited - fall back to debug mode
        logger.info("Rate limited - falling back to debug mode")
        debug_output = format_debug_output(merge_variables, line_name)
        logger.info(f"Debug output:\n{debug_output}")
        return

    if DEBUG_MODE:
        # In debug mode, output to console instead of sending to TRMNL
        debug_output = format_debug_output(merge_variables, line_name)
        logger.info(f"Debug output:\n{debug_output}")
        return

    # Send to TRMNL
    if not TRMNL_WEBHOOK_URL:
        logger.error("TRMNL_WEBHOOK_URL not set")
        return
    
    # Validate webhook URL format
    if not TRMNL_WEBHOOK_URL.startswith(('http://', 'https://')):
        logger.error(f"Invalid TRMNL_WEBHOOK_URL format: {TRMNL_WEBHOOK_URL}")
        return
    
    # Check for common TRMNL URL patterns
    if 'trmnl.com' not in TRMNL_WEBHOOK_URL and 'trmnl' not in TRMNL_WEBHOOK_URL.lower():
        logger.warning(f"TRMNL_WEBHOOK_URL doesn't contain 'trmnl': {TRMNL_WEBHOOK_URL}")

    try:
        # Log what we're sending for debugging
        webhook_data = {
            "html": template,
            "merge_variables": merge_variables
        }
        logger.info(f"Sending webhook to TRMNL with {len(merge_variables)} variables")
        logger.info(f"Webhook URL: {TRMNL_WEBHOOK_URL}")
        logger.debug(f"Webhook data: {webhook_data}")
        
        # Log sample variables for debugging
        sample_vars = {k: v for k, v in merge_variables.items() if k in ['l', 'u', 'c', 'n0', 'i01', 'o01']}
        logger.info(f"Sample variables: {sample_vars}")
        
        async with aiohttp.ClientSession() as session:
            async with session.post(
                TRMNL_WEBHOOK_URL,
                json=webhook_data,
                headers={"Content-Type": "application/json"}
            ) as response:
                if response.status == 200:
                    logger.info("Successfully updated TRMNL display")
                    _rate_limiter.record_update()
                elif response.status == 429:
                    # Rate limited - log and continue (next update is only 30 seconds away)
                    retry_after = response.headers.get("Retry-After")
                    if retry_after:
                        logger.warning(f"Rate limited by TRMNL. Retry-After: {retry_after} seconds. Will retry on next update cycle.")
                    else:
                        logger.warning("Rate limited by TRMNL. Will retry on next update cycle.")
                else:
                    # Try to get response body for better error information
                    try:
                        response_text = await response.text()
                        logger.error(f"Error updating TRMNL display: {response.status} - {response_text}")
                    except Exception:
                        logger.error(f"Error updating TRMNL display: {response.status}")
    except Exception as e:
        logger.error(f"Error sending update to TRMNL: {str(e)}")

def format_debug_output(merge_variables: Dict[str, str], line_name: str) -> str:
    """Format predictions for debug output."""
    now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    
    # Count active stops
    active_stops = sum(1 for i in range(12) if merge_variables.get(f"n{i}", ""))
    
    # Get rate limiting status
    rate_status = get_rate_limit_status()
    rate_info = f"📊 Rate Limit: {rate_status['updates_this_hour']}/{rate_status['max_updates_per_hour']} updates this hour"
    if not rate_status['can_update']:
        rate_info += " (RATE LIMITED)"
    
    output = [
        f"🚇 {line_name} Line Predictions",
        f"📅 {now}",
        f"🕐 Last Updated: {merge_variables['u']}",
        f"📍 Active Stops: {active_stops}",
        f"{rate_info}",
        "",
        "Stop Name          | Inbound 1 | Outbound 1 | Inbound 2 | Outbound 2 | Inbound 3 | Outbound 3",
        "=" * 80
    ]

    for i in range(12):
        stop_name = merge_variables.get(f"n{i}", "")
        if not stop_name:
            continue

        # Get times for this stop
        inbound_times = [merge_variables.get(f'i{i}{j}', '') for j in range(1, 4)]
        outbound_times = [merge_variables.get(f'o{i}{j}', '') for j in range(1, 4)]
        
        # Only show stops that have at least one time
        if any(inbound_times) or any(outbound_times):
            row = [
                f"{stop_name:<16}",
                f"{inbound_times[0]:<10}",
                f"{outbound_times[0]:<11}",
                f"{inbound_times[1]:<10}",
                f"{outbound_times[1]:<11}",
                f"{inbound_times[2]:<10}",
                f"{outbound_times[2]:<10}"
            ]
            output.append(" | ".join(row))

    output.append("")
    output.append("💡 Times shown are next departures from each stop")
    
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

    # Debug: Log some sample predictions
    logger.info(f"Processing {len(predictions)} predictions for route {route_id}")
    if predictions:
        sample_pred = predictions[0]
        logger.info(f"Sample prediction: route_id={sample_pred.route_id}, stop_id={sample_pred.stop_id}, "
                   f"departure_time={sample_pred.departure_time}, arrival_time={sample_pred.arrival_time}, "
                   f"direction_id={sample_pred.direction_id}")

    # First, get all stop information in parallel if we have predictions
    if predictions:
        unique_stop_ids = {pred.stop_id for pred in predictions}
        logger.info(f"Loading stop information for {len(unique_stop_ids)} unique stops from predictions: {list(unique_stop_ids)[:5]}...")
        
        # Add detailed logging for stop info gathering
        logger.info("Starting to gather stop information...")
        stop_info_tasks = [get_stop_info(stop_id) for stop_id in unique_stop_ids]
        stop_info_results = await asyncio.gather(*stop_info_tasks, return_exceptions=True)
        
        # Log results
        successful_stops = 0
        failed_stops = 0
        for i, result in enumerate(stop_info_results):
            stop_id = list(unique_stop_ids)[i]
            if isinstance(result, Exception):
                logger.error(f"Failed to get stop info for {stop_id}: {result}")
                failed_stops += 1
            else:
                logger.debug(f"Successfully got stop info for {stop_id}: {result}")
                successful_stops += 1
        
        logger.info(f"Stop info gathering complete: {successful_stops} successful, {failed_stops} failed")
        
        # Debug: Check cache contents right after gathering
        logger.info(f"Cache contents after gathering: {len(_stop_info_cache)} entries")
        for stop_id, stop_name in list(_stop_info_cache.items())[:5]:  # Show first 5
            logger.info(f"  {stop_id} -> {stop_name}")

    # Group predictions by stop and direction
    stop_times = {}  # type: Dict[str, Dict[str, List[str]]]
    for pred in predictions:
        departure = pred.departure_time or pred.arrival_time
        if departure:
            stop_name = _stop_info_cache.get(pred.stop_id, "Unknown Stop")
            if stop_name == "Unknown Stop":
                logger.debug(f"Skipping prediction for unknown stop: {pred.stop_id}")
                continue
            if stop_name not in stop_times:
                stop_times[stop_name] = {"inbound": [], "outbound": []}
            dt = datetime.fromisoformat(departure.replace("Z", "+00:00"))
            time_str = dt.strftime("%I:%M %p")
            # Swap direction mapping: 0 = outbound (toward Oak Grove), 1 = inbound (toward Forest Hills)
            direction = "outbound" if pred.direction_id == 0 else "inbound"
            stop_times[stop_name][direction].append(time_str)
            logger.debug(f"Added prediction: {stop_name} {direction} {time_str}")
            
    # Debug: Log what we found in stop_times
    logger.info(f"Found real-time predictions for {len(stop_times)} stops: {list(stop_times.keys())}")
    for stop_name, directions in stop_times.items():
        logger.info(f"  {stop_name}: inbound={len(directions['inbound'])}, outbound={len(directions['outbound'])}")
    
    # Debug: Log what's in the stop cache
    logger.info(f"Stop cache contains {len(_stop_info_cache)} entries")
    for stop_id, stop_name in list(_stop_info_cache.items())[:10]:  # Show first 10
        logger.info(f"  {stop_id} -> {stop_name}")
            
    # Always fetch scheduled times to fill gaps when we don't have enough real-time predictions
    logger.info("Fetching scheduled times to supplement real-time predictions")
    scheduled_times = await get_scheduled_times(route_id)
    logger.info(f"Retrieved {len(scheduled_times)} scheduled times for processing")
    
    # Debug: Log some sample scheduled times
    if scheduled_times:
        sample_sched = scheduled_times[0]
        logger.info(f"Sample scheduled time: stop_id={sample_sched.get('relationships', {}).get('stop', {}).get('data', {}).get('id')}, "
                   f"departure_time={sample_sched.get('attributes', {}).get('departure_time')}, "
                   f"direction_id={sample_sched.get('attributes', {}).get('direction_id')}")
    
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

    logger.info(f"Using ordered stops: {ordered_stops[:5]}...")

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
            
            # Get current time for filtering
            current_time = datetime.now().astimezone()
            
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
                        
                        # Filter out past times
                        if time_obj and time_obj <= current_time:
                            logger.debug(f"Filtering out past time: {time_str} (current: {current_time.strftime('%I:%M %p')})")
                            continue  # Skip past times
                            
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
            
            # Now, collect scheduled times (from scheduled_times) that are later than the latest real-time AND current time
            for schedule in scheduled_times:
                attributes = schedule.get("attributes", {})
                departure = attributes.get("departure_time")
                if departure:
                    # Get stop ID from relationships and then get stop name from cache
                    stop_id_sched = schedule.get("relationships", {}).get("stop", {}).get("data", {}).get("id")
                    if stop_id_sched:
                        stop_name_sched = _stop_info_cache.get(stop_id_sched, "Unknown Stop")
                        if stop_name_sched == stop_name:
                            dt = datetime.fromisoformat(departure.replace("Z", "+00:00"))
                            time_str = dt.strftime("%I:%M %p")
                            direction_sched = "outbound" if attributes.get("direction_id", 0) == 0 else "inbound"
                            if direction_sched == direction and time_str not in seen_times:
                                # First, ensure the time is in the future
                                if dt <= current_time:
                                    logger.debug(f"Filtering out past scheduled time: {time_str} for {stop_name}")
                                    continue  # Skip past times
                                
                                # Then, ensure both datetimes are timezone-aware for comparison
                                if latest_real_time is None:
                                    # If no real-time predictions, include future scheduled times
                                    scheduled_times_list.append((dt, time_str))
                                    seen_times.add(time_str)
                                    logger.debug(f"Added scheduled time (no real-time): {time_str} for {stop_name}")
                                elif latest_real_time.tzinfo is None:
                                    # If latest_real_time is naive, assume it's in the same timezone as dt
                                    latest_real_time = latest_real_time.replace(tzinfo=dt.tzinfo)
                                    if dt > latest_real_time:
                                        scheduled_times_list.append((dt, time_str))
                                        seen_times.add(time_str)
                                        logger.debug(f"Added scheduled time (after real-time): {time_str} for {stop_name}")
                                else:
                                    # Both are timezone-aware, compare directly
                                    if dt > latest_real_time:
                                        scheduled_times_list.append((dt, time_str))
                                        seen_times.add(time_str)
                                        logger.debug(f"Added scheduled time (after real-time): {time_str} for {stop_name}")
            
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
