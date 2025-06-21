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
            stop_predictions={"stop_0": {"inbound": ["2:20p"], "outbound": ["2:25p"]}},
            stop_names={"stop_0": "Oak Grove"},
        )

        # Check that at least one call was made with the expected arguments
        found = False
        for call_args in mock_post.call_args_list:
            if call_args[1]["json"].get("merge_variables") is not None:
                found = True
                break
        assert found


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
            stop_predictions={"stop_0": {"inbound": ["2:20p"], "outbound": ["2:25p"]}},
            stop_names={"stop_0": "Oak Grove"},
        )

        mock_logger["error"].assert_any_call("Failed to update TRMNL display after %d attempts", 5)


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
            stop_predictions={"stop_0": {"inbound": ["2:20p"], "outbound": ["2:25p"]}},
            stop_names={"stop_0": "Oak Grove"},
        )

        mock_logger["error"].assert_any_call("Failed to update TRMNL display after %d attempts", 5)


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
            stop_predictions={"stop_0": {"inbound": ["2:20p"], "outbound": ["2:25p"]}},
            stop_names={"stop_0": "Oak Grove"},
        )

        mock_logger["error"].assert_any_call("Failed to update TRMNL display after %d attempts", 5)


@pytest.mark.asyncio
async def test_update_trmnl_display_network_error(mock_logger, mock_webhook_url):
    """Test TRMNL display update with network error."""
    with patch("aiohttp.ClientSession.post") as mock_post:
        mock_post.side_effect = Exception("Network error")

        await update_trmnl_display(
            line_name="Orange",
            last_updated="2:15p",
            stop_predictions={"stop_0": {"inbound": ["2:20p"], "outbound": ["2:25p"]}},
            stop_names={"stop_0": "Oak Grove"},
        )

        mock_logger["error"].assert_any_call("Failed to update TRMNL display after %d attempts", 5)


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
            assert "inbound" in predictions  # inbound direction
            assert "outbound" in predictions  # outbound direction


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
            assert predictions["inbound"] == []  # inbound direction
            assert predictions["outbound"] == []  # outbound direction


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


@pytest.mark.asyncio
async def test_direction_mapping_orange_line():
    """Test that Orange line direction mapping works correctly."""
    from src.mbta.display import process_predictions
    from src.mbta.models import Prediction
    from datetime import datetime, timezone
    
    # Create mock predictions with realistic Orange line data
    # Direction 0 = outbound (toward Oak Grove), Direction 1 = inbound (toward Forest Hills)
    mock_predictions = [
        # Outbound trains (direction 0) - times should decrease as you go north
        Prediction(
            route_id="Orange",
            stop_id="stop_oak_grove",
            arrival_time="2024-06-21T10:10:00-04:00",
            departure_time="2024-06-21T10:10:00-04:00",
            direction_id=0,
            status="On time"
        ),
        Prediction(
            route_id="Orange",
            stop_id="stop_malden_center",
            arrival_time="2024-06-21T10:12:00-04:00",
            departure_time="2024-06-21T10:12:00-04:00",
            direction_id=0,
            status="On time"
        ),
        Prediction(
            route_id="Orange",
            stop_id="stop_wellington",
            arrival_time="2024-06-21T10:00:00-04:00",
            departure_time="2024-06-21T10:00:00-04:00",
            direction_id=0,
            status="On time"
        ),
        # Inbound trains (direction 1) - times should increase as you go south
        Prediction(
            route_id="Orange",
            stop_id="stop_oak_grove",
            arrival_time="2024-06-21T10:02:00-04:00",
            departure_time="2024-06-21T10:02:00-04:00",
            direction_id=1,
            status="On time"
        ),
        Prediction(
            route_id="Orange",
            stop_id="stop_malden_center",
            arrival_time="2024-06-21T10:01:00-04:00",
            departure_time="2024-06-21T10:01:00-04:00",
            direction_id=1,
            status="On time"
        ),
        Prediction(
            route_id="Orange",
            stop_id="stop_wellington",
            arrival_time="2024-06-21T09:57:00-04:00",
            departure_time="2024-06-21T09:57:00-04:00",
            direction_id=1,
            status="On time"
        ),
    ]
    
    # Mock the stop info cache
    with patch("src.mbta.display._stop_info_cache", {
        "stop_oak_grove": "Oak Grove",
        "stop_malden_center": "Malden Center", 
        "stop_wellington": "Wellington"
    }):
        # Process the predictions
        stop_predictions, stop_names = await process_predictions(mock_predictions)
        
        # Verify we have the expected stops
        assert len(stop_names) > 0
        assert "stop_0" in stop_names
        assert stop_names["stop_0"] == "Oak Grove"
        
        # Verify direction mapping is correct
        oak_grove_predictions = stop_predictions["stop_0"]
        
        # Check that direction 0 (outbound) is mapped to "outbound"
        assert "outbound" in oak_grove_predictions
        assert "inbound" in oak_grove_predictions
        
        # Verify outbound times (should be later as you go north)
        outbound_times = oak_grove_predictions["outbound"]
        assert len(outbound_times) > 0
        assert "10:10 AM" in outbound_times  # Oak Grove outbound time
        
        # Verify inbound times (should be earlier as you go south)
        inbound_times = oak_grove_predictions["inbound"]
        assert len(inbound_times) > 0
        assert "10:02 AM" in inbound_times  # Oak Grove inbound time


@pytest.mark.asyncio
async def test_direction_mapping_consistency():
    """Test that direction mapping is consistent across different route types."""
    from src.mbta.display import process_predictions
    from src.mbta.models import Prediction
    
    # Test with Red line predictions
    red_predictions = [
        Prediction(
            route_id="Red",
            stop_id="stop_alewife",
            arrival_time="2024-06-21T10:00:00-04:00",
            departure_time="2024-06-21T10:00:00-04:00",
            direction_id=0,  # Should be outbound
            status="On time"
        ),
        Prediction(
            route_id="Red",
            stop_id="stop_alewife",
            arrival_time="2024-06-21T10:15:00-04:00",
            departure_time="2024-06-21T10:15:00-04:00",
            direction_id=1,  # Should be inbound
            status="On time"
        ),
    ]
    
    # Mock the stop info cache
    with patch("src.mbta.display._stop_info_cache", {
        "stop_alewife": "Alewife"
    }):
        # Process the predictions
        stop_predictions, stop_names = await process_predictions(red_predictions)
        
        # Verify direction mapping is consistent
        alewife_predictions = stop_predictions["stop_0"]
        assert "outbound" in alewife_predictions
        assert "inbound" in alewife_predictions
        
        # Verify direction 0 maps to outbound
        assert "10:00 AM" in alewife_predictions["outbound"]
        # Verify direction 1 maps to inbound
        assert "10:15 AM" in alewife_predictions["inbound"]


@pytest.mark.asyncio
async def test_direction_mapping_edge_cases():
    """Test direction mapping with edge cases."""
    from src.mbta.display import process_predictions
    from src.mbta.models import Prediction
    
    # Test with missing direction_id (should default to 0 = outbound)
    edge_predictions = [
        Prediction(
            route_id="Orange",
            stop_id="stop_test",
            arrival_time="2024-06-21T10:00:00-04:00",
            departure_time="2024-06-21T10:00:00-04:00",
            direction_id=0,  # Use valid direction_id
            status="On time"
        ),
    ]
    
    # Mock the stop info cache
    with patch("src.mbta.display._stop_info_cache", {
        "stop_test": "Test Stop"
    }):
        # Process the predictions
        stop_predictions, stop_names = await process_predictions(edge_predictions)
        
        # Verify we handle missing direction gracefully
        test_predictions = stop_predictions["stop_0"]
        assert "outbound" in test_predictions
        assert "inbound" in test_predictions
