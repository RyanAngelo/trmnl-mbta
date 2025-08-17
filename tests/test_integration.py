"""
Integration tests for MBTA API.

These tests make real API calls and should be run sparingly.
Use environment variable INTEGRATION_TESTS=true to enable them.
"""

import os
import pytest
from src.mbta.api import get_stop_info, get_route_stops, fetch_predictions


@pytest.mark.skipif(
    os.getenv("INTEGRATION_TESTS") != "true",
    reason="Integration tests disabled. Set INTEGRATION_TESTS=true to enable."
)
class TestMBTAIntegration:
    """Integration tests that make real API calls to MBTA."""
    
    @pytest.mark.asyncio
    async def test_get_stop_info_integration(self):
        """Test getting stop info from real MBTA API."""
        # Use a known stop ID
        stop_name = await get_stop_info("70036")  # Oak Grove
        assert stop_name is not None
        assert "Oak Grove" in stop_name
    
    @pytest.mark.asyncio
    async def test_get_route_stops_integration(self):
        """Test getting route stops from real MBTA API."""
        stops = await get_route_stops("Orange")
        assert len(stops) > 0
        assert "70036" in stops  # Oak Grove should be in Orange line
    
    @pytest.mark.asyncio
    async def test_fetch_predictions_integration(self):
        """Test fetching predictions from real MBTA API."""
        predictions = await fetch_predictions("Orange", ["70036"])
        # Predictions might be empty depending on time of day
        assert isinstance(predictions, list)
