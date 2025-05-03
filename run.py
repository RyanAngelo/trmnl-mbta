import argparse
import asyncio
import sys
from pathlib import Path

import uvicorn

# Add the src directory to the Python path
src_path = str(Path(__file__).parent / "src")
if src_path not in sys.path:
    sys.path.insert(0, src_path)

from mbta.main import app, run_once

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
