import argparse
import asyncio

import uvicorn

from src.mbta.main import app, run_once

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="MBTA Schedule Display")
    parser.add_argument("--once", action="store_true", help="Run once and exit")
    args = parser.parse_args()

    if args.once:
        # Run once and exit
        asyncio.run(run_once())
    else:
        # Run web server as normal
        uvicorn.run(app, host="0.0.0.0", port=8000)
