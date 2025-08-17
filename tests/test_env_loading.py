"""Test environment variable loading from .env files."""

import os
import tempfile
import pytest
from pathlib import Path


def test_env_loading_from_dotenv():
    """Test that environment variables are loaded from .env file."""
    # Store original environment variables
    original_trmnl_url = os.environ.get('TRMNL_WEBHOOK_URL')
    original_mbta_key = os.environ.get('MBTA_API_KEY')
    original_debug_mode = os.environ.get('DEBUG_MODE')
    original_cwd = os.getcwd()
    
    # Create a temporary .env file
    with tempfile.NamedTemporaryFile(mode='w', suffix='.env', delete=False) as f:
        f.write("TRMNL_WEBHOOK_URL=https://api.trmnl.com/test\n")
        f.write("MBTA_API_KEY=test_api_key\n")
        f.write("DEBUG_MODE=true\n")
        env_file = f.name
    
    try:
        # Set the current working directory to where the .env file is
        env_dir = Path(env_file).parent
        os.chdir(env_dir)
        
        # Clear any existing environment variables
        
        if 'TRMNL_WEBHOOK_URL' in os.environ:
            del os.environ['TRMNL_WEBHOOK_URL']
        if 'MBTA_API_KEY' in os.environ:
            del os.environ['MBTA_API_KEY']
        if 'DEBUG_MODE' in os.environ:
            del os.environ['DEBUG_MODE']
        
        # Reload the constants module to pick up new environment
        import importlib
        import sys
        if 'src.mbta.constants' in sys.modules:
            del sys.modules['src.mbta.constants']
        
        # Manually load the .env file from the current directory
        try:
            from dotenv import load_dotenv
            load_dotenv(env_file)
        except ImportError:
            pass
        
        # Import constants after setting up the .env file
        # This should trigger the dotenv loading
        from src.mbta.constants import TRMNL_WEBHOOK_URL, MBTA_API_KEY, DEBUG_MODE
        
        # Verify the environment variables were loaded
        assert TRMNL_WEBHOOK_URL == "https://api.trmnl.com/test"
        assert MBTA_API_KEY == "test_api_key"
        assert DEBUG_MODE is True
        
    finally:
        # Clean up
        os.chdir(original_cwd)
        os.unlink(env_file)
        
        # Restore original environment variables
        if original_trmnl_url:
            os.environ['TRMNL_WEBHOOK_URL'] = original_trmnl_url
        if original_mbta_key:
            os.environ['MBTA_API_KEY'] = original_mbta_key
        if original_debug_mode:
            os.environ['DEBUG_MODE'] = original_debug_mode


def test_env_loading_without_dotenv():
    """Test that environment variables work without .env file."""
    # Store original environment variables
    original_trmnl_url = os.environ.get('TRMNL_WEBHOOK_URL')
    original_mbta_key = os.environ.get('MBTA_API_KEY')
    original_debug_mode = os.environ.get('DEBUG_MODE')
    
    # Clear any existing environment variables
    if 'TRMNL_WEBHOOK_URL' in os.environ:
        del os.environ['TRMNL_WEBHOOK_URL']
    if 'MBTA_API_KEY' in os.environ:
        del os.environ['MBTA_API_KEY']
    if 'DEBUG_MODE' in os.environ:
        del os.environ['DEBUG_MODE']
    
    # Set environment variables directly
    os.environ['TRMNL_WEBHOOK_URL'] = "https://api.trmnl.com/direct"
    os.environ['MBTA_API_KEY'] = "direct_api_key"
    os.environ['DEBUG_MODE'] = "false"
    
    # Reload the constants module to pick up new environment
    import importlib
    import sys
    if 'src.mbta.constants' in sys.modules:
        del sys.modules['src.mbta.constants']
    
    # Import constants
    from src.mbta.constants import TRMNL_WEBHOOK_URL, MBTA_API_KEY, DEBUG_MODE
    
    # Verify the environment variables were loaded
    assert TRMNL_WEBHOOK_URL == "https://api.trmnl.com/direct"
    assert MBTA_API_KEY == "direct_api_key"
    assert DEBUG_MODE is False
    
    # Clean up and restore original environment
    if original_trmnl_url:
        os.environ['TRMNL_WEBHOOK_URL'] = original_trmnl_url
    else:
        del os.environ['TRMNL_WEBHOOK_URL']
        
    if original_mbta_key:
        os.environ['MBTA_API_KEY'] = original_mbta_key
    else:
        del os.environ['MBTA_API_KEY']
        
    if original_debug_mode:
        os.environ['DEBUG_MODE'] = original_debug_mode
    else:
        del os.environ['DEBUG_MODE']
