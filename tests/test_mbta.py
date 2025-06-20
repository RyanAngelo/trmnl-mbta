import asyncio
from unittest.mock import AsyncMock, call, patch

import pytest

from mbta.main import (
    get_stop_info,
    get_stop_locations,
    logger,
    safe_load_config,
    update_trmnl_display,
    convert_to_short_time,
    process_predictions,
)
from mbta.api import get_scheduled_times


@pytest.fixture
def mock_logger():
    """Mock logger for tests."""
    with patch.object(logger, "info") as mock_info, patch.object(
        logger, "warning"
    ) as mock_warning, patch.object(logger, "error") as mock_error:
        yield {"info": mock_info, "warning": mock_warning, "error": mock_error}


@pytest.fixture
def mock_webhook_url():
    """Mock TRMNL webhook URL for tests."""
    with patch("mbta.main.TRMNL_WEBHOOK_URL", "https://api.trmnl.com/test"):
        yield


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


@pytest.mark.asyncio
async def test_update_trmnl_display_success(mock_logger, mock_webhook_url):
    """Test successful TRMNL display update."""
    with patch("aiohttp.ClientSession.post") as mock_post:
        mock_response = AsyncMock()
        mock_response.status = 200
        mock_post.return_value.__aenter__.return_value = mock_response

        await update_trmnl_display(
            line_name="Orange",
            last_updated="2:15p",
            stop_predictions={"stop_0": {"0": ["2:20p"], "1": ["2:25p"]}},
            stop_names={"stop_0": "Oak Grove"},
        )

        mock_post.assert_called_once()
        call_args = mock_post.call_args
        assert call_args[1]["json"]["html"] is not None


@pytest.mark.asyncio
async def test_update_trmnl_display_rate_limit_with_retry_after(mock_logger, mock_webhook_url):
    """Test TRMNL display update with rate limit and retry-after header."""
    with patch("aiohttp.ClientSession.post") as mock_post:
        mock_response = AsyncMock()
        mock_response.status = 429
        mock_response.headers = {"Retry-After": "60"}
        mock_post.return_value.__aenter__.return_value = mock_response

        await update_trmnl_display(
            line_name="Orange",
            last_updated="2:15p",
            stop_predictions={"stop_0": {"0": ["2:20p"], "1": ["2:25p"]}},
            stop_names={"stop_0": "Oak Grove"},
        )

        mock_logger.error.assert_called_with("Rate limited by TRMNL API. Retry after 60 seconds.")


@pytest.mark.asyncio
async def test_update_trmnl_display_rate_limit_without_retry_after(mock_logger, mock_webhook_url):
    """Test TRMNL display update with rate limit but no retry-after header."""
    with patch("aiohttp.ClientSession.post") as mock_post:
        mock_response = AsyncMock()
        mock_response.status = 429
        mock_response.headers = {}
        mock_post.return_value.__aenter__.return_value = mock_response

        await update_trmnl_display(
            line_name="Orange",
            last_updated="2:15p",
            stop_predictions={"stop_0": {"0": ["2:20p"], "1": ["2:25p"]}},
            stop_names={"stop_0": "Oak Grove"},
        )

        mock_logger.error.assert_called_with("Rate limited by TRMNL API. Retry after 30 seconds.")


@pytest.mark.asyncio
async def test_update_trmnl_display_other_error(mock_logger, mock_webhook_url):
    """Test TRMNL display update with other HTTP error."""
    with patch("aiohttp.ClientSession.post") as mock_post:
        mock_response = AsyncMock()
        mock_response.status = 500
        mock_post.return_value.__aenter__.return_value = mock_response

        await update_trmnl_display(
            line_name="Orange",
            last_updated="2:15p",
            stop_predictions={"stop_0": {"0": ["2:20p"], "1": ["2:25p"]}},
            stop_names={"stop_0": "Oak Grove"},
        )

        mock_logger.error.assert_called_with("Error updating TRMNL display: 500")


@pytest.mark.asyncio
async def test_update_trmnl_display_network_error(mock_logger, mock_webhook_url):
    """Test TRMNL display update with network error."""
    with patch("aiohttp.ClientSession.post") as mock_post:
        mock_post.side_effect = Exception("Network error")

        await update_trmnl_display(
            line_name="Orange",
            last_updated="2:15p",
            stop_predictions={"stop_0": {"0": ["2:20p"], "1": ["2:25p"]}},
            stop_names={"stop_0": "Oak Grove"},
        )

        mock_logger.error.assert_called_with("Error sending update to TRMNL: Network error")


def test_convert_to_short_time():
    """Test time format conversion."""
    # Test PM times
    assert convert_to_short_time("01:29 PM") == "1:29p"
    assert convert_to_short_time("11:59 PM") == "11:59p"
    
    # Test AM times
    assert convert_to_short_time("01:29 AM") == "1:29a"
    assert convert_to_short_time("11:59 AM") == "11:59a"
    
    # Test invalid format
    assert convert_to_short_time("invalid") == "invalid"


@pytest.mark.asyncio
async def test_get_scheduled_times(mock_logger):
    """Test fetching scheduled times from MBTA API."""
    # Create mock response with scheduled times
    mock_response = AsyncMock()
    mock_response.status = 200
    mock_response.json.return_value = {
        "data": [
            {
                "attributes": {
                    "departure_time": "2024-04-06T06:00:00-04:00",
                    "direction_id": 0
                },
                "relationships": {
                    "stop": {"data": {"id": "stop1"}}
                }
            },
            {
                "attributes": {
                    "departure_time": "2024-04-06T06:15:00-04:00",
                    "direction_id": 1
                },
                "relationships": {
                    "stop": {"data": {"id": "stop2"}}
                }
            }
        ]
    }
    
    with patch("aiohttp.ClientSession.get") as mock_get:
        mock_get.return_value.__aenter__.return_value = mock_response
        
        result = await get_scheduled_times("Orange")
        assert len(result) == 2
        assert result[0]["attributes"]["departure_time"] == "2024-04-06T06:00:00-04:00"
        assert result[1]["attributes"]["departure_time"] == "2024-04-06T06:15:00-04:00"


@pytest.mark.asyncio
async def test_get_scheduled_times_error(mock_logger):
    """Test handling of API errors when fetching scheduled times."""
    # Create mock response with error
    mock_response = AsyncMock()
    mock_response.status = 500
    
    with patch("aiohttp.ClientSession.get") as mock_get, \
         patch("mbta.api.logger") as mock_api_logger:
        mock_get.return_value.__aenter__.return_value = mock_response
        mock_api_logger.warning = mock_logger["warning"]
        
        result = await get_scheduled_times("Orange")
        assert result == []
        mock_logger["warning"].assert_called_once()


@pytest.mark.asyncio
async def test_process_predictions_with_scheduled_times(mock_logger):
    """Test processing predictions with scheduled times when no real-time predictions exist."""
    # Mock the get_scheduled_times function to return some scheduled times
    mock_scheduled_times = [
        {
            "attributes": {
                "departure_time": "2024-04-06T06:00:00-04:00",
                "direction_id": 0
            },
            "relationships": {
                "stop": {"data": {"id": "stop1"}}
            }
        },
        {
            "attributes": {
                "departure_time": "2024-04-06T06:15:00-04:00",
                "direction_id": 1
            },
            "relationships": {
                "stop": {"data": {"id": "stop2"}}
            }
        }
    ]
    
    with patch("mbta.api.get_scheduled_times", return_value=mock_scheduled_times), \
         patch("mbta.main.get_stop_info") as mock_get_stop_info:
        # Set up stop info cache
        mock_get_stop_info.side_effect = lambda stop_id: {
            "stop1": "Oak Grove",
            "stop2": "Malden Center"
        }.get(stop_id, "Unknown Stop")
        
        # Process empty predictions list
        stop_predictions, stop_names = await process_predictions([])
        
        # Verify that scheduled times were processed
        assert len(stop_predictions) > 0
        assert len(stop_names) > 0
        
        # Verify that Oak Grove is first
        first_stop_id = next(iter(stop_names))
        assert stop_names[first_stop_id] == "Oak Grove"
        
        # Verify that scheduled times are included
        for stop_id, predictions in stop_predictions.items():
            assert "0" in predictions  # inbound direction
            assert "1" in predictions  # outbound direction


@pytest.mark.asyncio
async def test_process_predictions_with_no_times(mock_logger):
    """Test processing predictions when there are no real-time or scheduled times."""
    with patch("mbta.api.get_scheduled_times", return_value=[]):
        stop_predictions, stop_names = await process_predictions([])
        
        # Verify that we still get the stop names in the correct order
        assert len(stop_names) > 0
        first_stop_id = next(iter(stop_names))
        assert stop_names[first_stop_id] == "Oak Grove"
        
        # Verify that all prediction slots are empty
        for stop_id, predictions in stop_predictions.items():
            assert predictions["0"] == []  # inbound direction
            assert predictions["1"] == []  # outbound direction


@pytest.mark.asyncio
async def test_bus_route_validation():
    """Test that bus routes are properly validated."""
    from src.mbta.constants import VALID_ROUTE_PATTERN
    
    # Test valid bus routes
    assert VALID_ROUTE_PATTERN.match("1")
    assert VALID_ROUTE_PATTERN.match("66")
    assert VALID_ROUTE_PATTERN.match("SL1")
    assert VALID_ROUTE_PATTERN.match("501")
    
    # Test valid subway routes
    assert VALID_ROUTE_PATTERN.match("Red")
    assert VALID_ROUTE_PATTERN.match("Orange")
    assert VALID_ROUTE_PATTERN.match("Blue")
    assert VALID_ROUTE_PATTERN.match("Green-B")
    
    # Test invalid routes
    assert not VALID_ROUTE_PATTERN.match("Invalid")
    assert not VALID_ROUTE_PATTERN.match("ABC")


@pytest.mark.asyncio
async def test_bus_route_stops():
    """Test fetching stops for bus routes."""
    from src.mbta.api import get_route_stops
    
    mock_bus_stops_response = {
        "data": [
            {"id": "stop1", "attributes": {"name": "Bus Stop 1"}},
            {"id": "stop2", "attributes": {"name": "Bus Stop 2"}},
            {"id": "stop3", "attributes": {"name": "Bus Stop 3"}}
        ]
    }
    
    with patch("aiohttp.ClientSession.get") as mock_get:
        mock_response = AsyncMock()
        mock_response.status = 200
        mock_response.json.return_value = mock_bus_stops_response
        mock_get.return_value.__aenter__.return_value = mock_response

        result = await get_route_stops("66")
        assert result == ["stop1", "stop2", "stop3"]


@pytest.mark.asyncio
async def test_bus_route_config():
    """Test that bus routes can be configured."""
    from src.mbta.models import RouteConfig
    
    # Test valid bus route configuration
    config = RouteConfig(route_id="66")
    assert config.route_id == "66"
    
    # Test invalid bus route configuration
    with pytest.raises(ValueError, match="Invalid route_id format"):
        RouteConfig(route_id="Invalid")
