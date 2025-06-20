import os
import re
from pathlib import Path
from typing import Pattern

# Load environment variables
ALLOWED_ORIGINS = os.getenv("ALLOWED_ORIGINS", "http://localhost:8000").split(",")
DEBUG_MODE = os.getenv("DEBUG_MODE", "false").lower() == "true"
MBTA_API_KEY = os.getenv("MBTA_API_KEY")
TRMNL_WEBHOOK_URL = os.getenv("TRMNL_WEBHOOK_URL")
API_KEY = os.getenv("API_KEY")

# API Configuration
MBTA_API_BASE = "https://api-v3.mbta.com"
HEADERS = {"x-api-key": MBTA_API_KEY} if MBTA_API_KEY else {}

# File paths
TEMPLATE_PATH = Path(__file__).parent.parent.parent / "templates" / "trmnl-template.html"
CONFIG_FILE = Path(__file__).parent.parent.parent / "config.json"

# Validation patterns
VALID_ROUTE_PATTERN: Pattern = re.compile(r"^(Red|Orange|Blue|Green-[A-E]|[0-9]+|[A-Z]+[0-9]+)$")
VALID_STOP_PATTERN: Pattern = re.compile(r"^[a-zA-Z0-9-]+$")

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

# Bus route colors (using MBTA bus colors)
BUS_COLORS = {
    "1": "#FF6B35",    # Orange
    "4": "#FF6B35",    # Orange
    "7": "#FF6B35",    # Orange
    "8": "#FF6B35",    # Orange
    "9": "#FF6B35",    # Orange
    "10": "#FF6B35",   # Orange
    "11": "#FF6B35",   # Orange
    "14": "#FF6B35",   # Orange
    "15": "#FF6B35",   # Orange
    "16": "#FF6B35",   # Orange
    "17": "#FF6B35",   # Orange
    "18": "#FF6B35",   # Orange
    "19": "#FF6B35",   # Orange
    "21": "#FF6B35",   # Orange
    "22": "#FF6B35",   # Orange
    "23": "#FF6B35",   # Orange
    "24": "#FF6B35",   # Orange
    "26": "#FF6B35",   # Orange
    "28": "#FF6B35",   # Orange
    "29": "#FF6B35",   # Orange
    "30": "#FF6B35",   # Orange
    "31": "#FF6B35",   # Orange
    "32": "#FF6B35",   # Orange
    "33": "#FF6B35",   # Orange
    "34": "#FF6B35",   # Orange
    "34E": "#FF6B35",  # Orange
    "35": "#FF6B35",   # Orange
    "36": "#FF6B35",   # Orange
    "37": "#FF6B35",   # Orange
    "38": "#FF6B35",   # Orange
    "39": "#FF6B35",   # Orange
    "40": "#FF6B35",   # Orange
    "41": "#FF6B35",   # Orange
    "42": "#FF6B35",   # Orange
    "43": "#FF6B35",   # Orange
    "44": "#FF6B35",   # Orange
    "45": "#FF6B35",   # Orange
    "47": "#FF6B35",   # Orange
    "50": "#FF6B35",   # Orange
    "51": "#FF6B35",   # Orange
    "52": "#FF6B35",   # Orange
    "55": "#FF6B35",   # Orange
    "57": "#FF6B35",   # Orange
    "59": "#FF6B35",   # Orange
    "60": "#FF6B35",   # Orange
    "62": "#FF6B35",   # Orange
    "64": "#FF6B35",   # Orange
    "65": "#FF6B35",   # Orange
    "66": "#FF6B35",   # Orange
    "67": "#FF6B35",   # Orange
    "68": "#FF6B35",   # Orange
    "69": "#FF6B35",   # Orange
    "70": "#FF6B35",   # Orange
    "71": "#FF6B35",   # Orange
    "72": "#FF6B35",   # Orange
    "73": "#FF6B35",   # Orange
    "74": "#FF6B35",   # Orange
    "75": "#FF6B35",   # Orange
    "76": "#FF6B35",   # Orange
    "77": "#FF6B35",   # Orange
    "78": "#FF6B35",   # Orange
    "79": "#FF6B35",   # Orange
    "80": "#FF6B35",   # Orange
    "83": "#FF6B35",   # Orange
    "84": "#FF6B35",   # Orange
    "85": "#FF6B35",   # Orange
    "86": "#FF6B35",   # Orange
    "87": "#FF6B35",   # Orange
    "88": "#FF6B35",   # Orange
    "89": "#FF6B35",   # Orange
    "90": "#FF6B35",   # Orange
    "91": "#FF6B35",   # Orange
    "92": "#FF6B35",   # Orange
    "93": "#FF6B35",   # Orange
    "94": "#FF6B35",   # Orange
    "95": "#FF6B35",   # Orange
    "96": "#FF6B35",   # Orange
    "97": "#FF6B35",   # Orange
    "99": "#FF6B35",   # Orange
    "100": "#FF6B35",  # Orange
    "101": "#FF6B35",  # Orange
    "104": "#FF6B35",  # Orange
    "105": "#FF6B35",  # Orange
    "106": "#FF6B35",  # Orange
    "108": "#FF6B35",  # Orange
    "109": "#FF6B35",  # Orange
    "110": "#FF6B35",  # Orange
    "111": "#FF6B35",  # Orange
    "112": "#FF6B35",  # Orange
    "114": "#FF6B35",  # Orange
    "116": "#FF6B35",  # Orange
    "117": "#FF6B35",  # Orange
    "119": "#FF6B35",  # Orange
    "120": "#FF6B35",  # Orange
    "121": "#FF6B35",  # Orange
    "131": "#FF6B35",  # Orange
    "132": "#FF6B35",  # Orange
    "134": "#FF6B35",  # Orange
    "136": "#FF6B35",  # Orange
    "137": "#FF6B35",  # Orange
    "170": "#FF6B35",  # Orange
    "171": "#FF6B35",  # Orange
    "201": "#FF6B35",  # Orange
    "202": "#FF6B35",  # Orange
    "210": "#FF6B35",  # Orange
    "211": "#FF6B35",  # Orange
    "212": "#FF6B35",  # Orange
    "214": "#FF6B35",  # Orange
    "215": "#FF6B35",  # Orange
    "216": "#FF6B35",  # Orange
    "217": "#FF6B35",  # Orange
    "220": "#FF6B35",  # Orange
    "221": "#FF6B35",  # Orange
    "222": "#FF6B35",  # Orange
    "225": "#FF6B35",  # Orange
    "230": "#FF6B35",  # Orange
    "236": "#FF6B35",  # Orange
    "238": "#FF6B35",  # Orange
    "240": "#FF6B35",  # Orange
    "245": "#FF6B35",  # Orange
    "247": "#FF6B35",  # Orange
    "248": "#FF6B35",  # Orange
    "249": "#FF6B35",  # Orange
    "325": "#FF6B35",  # Orange
    "326": "#FF6B35",  # Orange
    "350": "#FF6B35",  # Orange
    "351": "#FF6B35",  # Orange
    "352": "#FF6B35",  # Orange
    "354": "#FF6B35",  # Orange
    "355": "#FF6B35",  # Orange
    "411": "#FF6B35",  # Orange
    "424": "#FF6B35",  # Orange
    "426": "#FF6B35",  # Orange
    "428": "#FF6B35",  # Orange
    "429": "#FF6B35",  # Orange
    "430": "#FF6B35",  # Orange
    "434": "#FF6B35",  # Orange
    "435": "#FF6B35",  # Orange
    "436": "#FF6B35",  # Orange
    "439": "#FF6B35",  # Orange
    "441": "#FF6B35",  # Orange
    "442": "#FF6B35",  # Orange
    "449": "#FF6B35",  # Orange
    "450": "#FF6B35",  # Orange
    "451": "#FF6B35",  # Orange
    "456": "#FF6B35",  # Orange
    "465": "#FF6B35",  # Orange
    "501": "#FF6B35",  # Orange
    "502": "#FF6B35",  # Orange
    "503": "#FF6B35",  # Orange
    "504": "#FF6B35",  # Orange
    "505": "#FF6B35",  # Orange
    "553": "#FF6B35",  # Orange
    "554": "#FF6B35",  # Orange
    "555": "#FF6B35",  # Orange
    "556": "#FF6B35",  # Orange
    "558": "#FF6B35",  # Orange
    "701": "#FF6B35",  # Orange
    "708": "#FF6B35",  # Orange
    "709": "#FF6B35",  # Orange
    "710": "#FF6B35",  # Orange
    "712": "#FF6B35",  # Orange
    "713": "#FF6B35",  # Orange
    "714": "#FF6B35",  # Orange
    "716": "#FF6B35",  # Orange
    "720": "#FF6B35",  # Orange
    "721": "#FF6B35",  # Orange
    "722": "#FF6B35",  # Orange
    "725": "#FF6B35",  # Orange
    "726": "#FF6B35",  # Orange
    "741": "#FF6B35",  # Orange
    "742": "#FF6B35",  # Orange
    "743": "#FF6B35",  # Orange
    "747": "#FF6B35",  # Orange
    "748": "#FF6B35",  # Orange
    "749": "#FF6B35",  # Orange
    "751": "#FF6B35",  # Orange
    "852": "#FF6B35",  # Orange
    "SL1": "#FF6B35",  # Orange
    "SL2": "#FF6B35",  # Orange
    "SL3": "#FF6B35",  # Orange
    "SL4": "#FF6B35",  # Orange
    "SL5": "#FF6B35",  # Orange
    "SLW": "#FF6B35",  # Orange
} 