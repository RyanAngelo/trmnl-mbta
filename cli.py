#!/usr/bin/env python3
"""
TRMNL MBTA Schedule Display - Command Line Application
Fetches MBTA predictions and updates TRMNL display without web server overhead.
"""

import asyncio
import logging
import os
import sys
from datetime import datetime
from pathlib import Path

# Add the src directory to the Python path
src_path = str(Path(__file__).parent / "src")
if src_path not in sys.path:
    sys.path.insert(0, src_path)

from mbta.api import fetch_predictions, get_scheduled_times
from mbta.config import safe_load_config
from mbta.display import process_predictions, update_trmnl_display, get_rate_limit_status
from mbta.models import Prediction

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# Global variable to track prediction changes
_last_prediction_hash = None

def calculate_prediction_hash(predictions: list[Prediction]) -> int:
    """Calculate a hash of predictions for change detection."""
    # Convert None values to empty strings for sorting to avoid comparison errors
    prediction_tuples = sorted([
        (pred.route_id, pred.stop_id, pred.departure_time or "", pred.arrival_time or "", pred.direction_id)
        for pred in predictions
    ])
    return hash(str(prediction_tuples))

async def run_once() -> None:
    """Run one update cycle."""
    global _last_prediction_hash
    
    try:
        config = safe_load_config()
        predictions = await fetch_predictions(config.route_id)
        print(f"Got {len(predictions)} predictions for {config.route_id} line")
        
        # Check if predictions have changed using hash comparison
        prediction_hash = calculate_prediction_hash(predictions)
        
        if prediction_hash != _last_prediction_hash:
            _last_prediction_hash = prediction_hash
            await update_display(predictions)
            print("✅ Update complete - predictions changed")
        else:
            logger.info("Predictions unchanged, skipping display update")
            print("⏭️  Skipped update - no changes detected")
        
        # Show rate limiting status
        rate_status = get_rate_limit_status()
        print(f"📊 Rate limit: {rate_status['updates_this_hour']}/{rate_status['max_updates_per_hour']} updates this hour")
            
    except Exception as e:
        logger.error(f"Error running once: {str(e)}")
        print(f"❌ Error: {str(e)}")

async def update_display(predictions: list[Prediction]) -> None:
    """Process predictions and update the TRMNL display."""
    config = safe_load_config()
    logger.info(f"Current route config: {config.route_id}")

    stop_predictions, stop_names = await process_predictions(predictions)

    await update_trmnl_display(
        line_name=config.route_id,
        last_updated=datetime.now().strftime("%I:%M %p"),
        stop_predictions=stop_predictions,
        stop_names=stop_names,
    )

async def update_loop(interval: int = 30) -> None:
    """Main update loop."""
    print(f"🚇 Starting TRMNL MBTA Schedule Display")
    print(f"⏰ Update interval: {interval} seconds")
    print(f"📊 Rate limiting: Max 12 webhooks per hour (1 every 5 minutes)")
    print(f"🔄 Press Ctrl+C to stop\n")
    
    while True:
        try:
            await run_once()
        except Exception as e:
            logger.error(f"Error in update loop: {str(e)}")
            print(f"❌ Error in update loop: {str(e)}")
        
        await asyncio.sleep(interval)

async def main():
    """Main entry point."""
    import argparse
    
    parser = argparse.ArgumentParser(description="TRMNL MBTA Schedule Display")
    parser.add_argument("--once", action="store_true", help="Run once and exit")
    parser.add_argument("--interval", type=int, default=30, help="Update interval in seconds (default: 30)")
    parser.add_argument("--route", help="Override route from config")
    args = parser.parse_args()

    # Override route if specified
    if args.route:
        config = safe_load_config()
        config.route_id = args.route
        from mbta.config import safe_save_config
        safe_save_config(config)
        print(f"🔄 Route updated to: {args.route}")

    if args.once:
        # Run once and exit
        print("🔄 Running once...")
        await run_once()
        print("✅ Done")
    else:
        # Run continuous update loop
        try:
            await update_loop(args.interval)
        except KeyboardInterrupt:
            print("\n🛑 Stopping...")
            print("👋 Goodbye!")

if __name__ == "__main__":
    asyncio.run(main())
