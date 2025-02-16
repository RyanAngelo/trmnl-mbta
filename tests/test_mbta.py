from unittest.mock import patch, AsyncMock
from mbta.main import safe_load_config, get_line_color, get_stop_locations, get_stop_info
import pytest


def test_get_line_color():
    """Test line color mapping."""
    assert get_line_color("Red") == "#FA2D27"
    assert get_line_color("Orange") == "#FFA500"
    assert get_line_color("Unknown") == "#666666"


def test_load_config(test_config_file):
    """Test loading configuration from file."""
    with patch("mbta.main.CONFIG_FILE", test_config_file):
        config = safe_load_config()
        assert config.route_id == "Red"


@pytest.mark.asyncio
async def test_get_stop_info(mock_mbta_response):
    """Test fetching stop information."""
    with patch("aiohttp.ClientSession.get") as mock_get:
        mock_response = AsyncMock()
        mock_response.status = 200
        mock_response.json.return_value = mock_mbta_response
        mock_get.return_value.__aenter__.return_value = mock_response

        result = await get_stop_info("test-stop")
        assert result == "Test Stop"


@pytest.mark.asyncio
async def test_get_stop_locations(mock_mbta_stops_response):
    """Test fetching stop locations."""
    with patch("aiohttp.ClientSession.get") as mock_get:
        mock_response = AsyncMock()
        mock_response.status = 200
        mock_response.json.return_value = mock_mbta_stops_response
        mock_get.return_value.__aenter__.return_value = mock_response

        result = await get_stop_locations("Red")
        assert result["Test Stop"]["latitude"] == 42.3601
