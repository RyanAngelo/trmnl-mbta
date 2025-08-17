import os
import re
from pathlib import Path
from typing import Pattern

# Load environment variables from .env file
try:
    from dotenv import load_dotenv
    load_dotenv()
except ImportError:
    # python-dotenv not available, continue without it
    pass

# Load environment variables
DEBUG_MODE = os.getenv("DEBUG_MODE", "false").lower() == "true"
MBTA_API_KEY = os.getenv("MBTA_API_KEY")
TRMNL_WEBHOOK_URL = os.getenv("TRMNL_WEBHOOK_URL")

# Validate required environment variables
if not MBTA_API_KEY:
    print("WARNING: MBTA_API_KEY environment variable is not set")
if not TRMNL_WEBHOOK_URL:
    print("WARNING: TRMNL_WEBHOOK_URL environment variable is not set")

# API Configuration
MBTA_API_BASE = "https://api-v3.mbta.com"
HEADERS = {"x-api-key": MBTA_API_KEY} if MBTA_API_KEY else {}

# File paths
TEMPLATE_PATH = Path(__file__).parent.parent.parent / "templates" / "trmnl-template.html"
CONFIG_FILE = Path(__file__).parent.parent.parent / "config" / "config.json"

# Validation patterns
VALID_ROUTE_PATTERN: Pattern = re.compile(r"^(Red|Orange|Blue|Green-[A-E]|[0-9]+|[A-Z]+[0-9]+)$")
VALID_STOP_PATTERN: Pattern = re.compile(r"^[a-zA-Z0-9-]+$")

# Display configuration
MAX_PREDICTIONS_PER_DIRECTION = 3  # Maximum number of predictions to show per direction per stop

# Global cache for stop information (to avoid circular imports)
_stop_info_cache = {}

# Stop order for each line (inbound direction) - only for subway lines
STOP_ORDER = {
    "Orange": [
        "Oak Grove", "Malden Center", "Wellington", "Assembly", "Sullivan Square",
        "Community College", "North Station", "Haymarket", "State", "Downtown Crossing",
        "Chinatown", "Tufts Medical Center", "Back Bay", "Massachusetts Avenue",
        "Ruggles", "Roxbury Crossing", "Jackson Square", "Stony Brook",
        "Green Street", "Forest Hills"
    ],
    "Red": [
        "Alewife", "Davis", "Porter", "Harvard", "Central", "Kendall/MIT",
        "Charles/MGH", "Park Street", "Downtown Crossing", "South Station",
        "Broadway", "Andrew", "JFK/UMass", "Savin Hill", "Fields Corner",
        "Shawmut", "Ashmont", "North Quincy", "Wollaston", "Quincy Center",
        "Quincy Adams", "Braintree"
    ],
    "Blue": [
        "Wonderland", "Revere Beach", "Beachmont", "Suffolk Downs", "Orient Heights",
        "Wood Island", "Airport", "Maverick", "Bowdoin", "Government Center",
        "State", "Aquarium", "Maverick"
    ]
} 
