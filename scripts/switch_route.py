#!/usr/bin/env python3
"""
Utility script to switch between different MBTA routes for testing.
"""

import json
import sys
from pathlib import Path

CONFIG_FILE = Path(__file__).parent.parent / "config.json"

def switch_route(route_id: str):
    """Switch to a different route."""
    config = {"route_id": route_id}
    
    with open(CONFIG_FILE, "w") as f:
        json.dump(config, f, indent=2)
    
    print(f"Switched to route: {route_id}")

def main():
    if len(sys.argv) != 2:
        print("Usage: python switch_route.py <route_id>")
        print("\nExamples:")
        print("  python switch_route.py Orange    # Subway line")
        print("  python switch_route.py 66        # Bus route")
        print("  python switch_route.py SL1       # Silver Line")
        print("  python switch_route.py 501       # Express bus")
        sys.exit(1)
    
    route_id = sys.argv[1]
    switch_route(route_id)

if __name__ == "__main__":
    main() 