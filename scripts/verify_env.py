#!/usr/bin/env python3
"""
Environment verification script for TRMNL MBTA.
This script checks that all required environment variables are properly loaded.
"""

import os
import sys
from pathlib import Path

# Load environment variables from .env file
try:
    from dotenv import load_dotenv
    load_dotenv()
except ImportError:
    # python-dotenv not available, continue without it
    pass

# Add the src directory to the Python path
src_path = str(Path(__file__).parent.parent / "src")
if src_path not in sys.path:
    sys.path.insert(0, src_path)

def check_env_variables():
    """Check that all required environment variables are set."""
    print("🔍 Checking environment variables...")
    
    # Check if .env file exists
    env_file = Path(__file__).parent.parent / ".env"
    if env_file.exists():
        print(f"✅ .env file found: {env_file}")
    else:
        print(f"⚠️  .env file not found: {env_file}")
    
    # Check required environment variables
    required_vars = {
        "MBTA_API_KEY": "MBTA API key from https://api-v3.mbta.com/",
        "TRMNL_WEBHOOK_URL": "TRMNL webhook URL from your TRMNL dashboard"
    }
    
    optional_vars = {
        "DEBUG_MODE": "Debug mode (true/false, defaults to false)"
    }
    
    print("\n📋 Required Environment Variables:")
    all_good = True
    
    for var, description in required_vars.items():
        value = os.getenv(var)
        if value:
            # Mask sensitive values
            if var == "MBTA_API_KEY":
                masked_value = value[:8] + "..." if len(value) > 8 else "***"
            else:
                masked_value = value
            print(f"✅ {var}: {masked_value}")
        else:
            print(f"❌ {var}: NOT SET")
            print(f"   Description: {description}")
            all_good = False
    
    print("\n📋 Optional Environment Variables:")
    for var, description in optional_vars.items():
        value = os.getenv(var, "not set (using default)")
        print(f"ℹ️  {var}: {value}")
        print(f"   Description: {description}")
    
    # Test importing constants
    print("\n🧪 Testing module imports...")
    try:
        from mbta.constants import MBTA_API_KEY, TRMNL_WEBHOOK_URL, DEBUG_MODE
        print("✅ Successfully imported constants module")
        
        if MBTA_API_KEY:
            print("✅ MBTA_API_KEY loaded correctly")
        else:
            print("❌ MBTA_API_KEY not loaded")
            all_good = False
            
        if TRMNL_WEBHOOK_URL:
            print("✅ TRMNL_WEBHOOK_URL loaded correctly")
        else:
            print("❌ TRMNL_WEBHOOK_URL not loaded")
            all_good = False
            
        print(f"✅ DEBUG_MODE: {DEBUG_MODE}")
        
    except Exception as e:
        print(f"❌ Error importing constants: {e}")
        all_good = False
    
    print("\n" + "="*50)
    if all_good:
        print("🎉 All environment variables are properly configured!")
        return 0
    else:
        print("⚠️  Some environment variables are missing or incorrectly configured.")
        print("\nTo fix this:")
        print("1. Create a .env file in the project root")
        print("2. Add your environment variables:")
        print("   MBTA_API_KEY=your_mbta_api_key_here")
        print("   TRMNL_WEBHOOK_URL=your_trmnl_webhook_url_here")
        print("   DEBUG_MODE=false")
        return 1

if __name__ == "__main__":
    sys.exit(check_env_variables())
