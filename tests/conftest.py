import json
import os
from pathlib import Path

import pytest

# Test configuration file path
TEST_CONFIG_FILE = Path(__file__).parent / "test_config.json"


@pytest.fixture(autouse=True)
def use_test_config():
    """Automatically use test config for all tests."""
    from src.mbta.constants import CONFIG_FILE
    with pytest.MonkeyPatch().context() as m:
        m.setattr("src.mbta.constants.CONFIG_FILE", TEST_CONFIG_FILE)
        yield


@pytest.fixture(autouse=True)
def clear_stop_cache():
    """Clear the stop info cache between tests to prevent test interference."""
    from src.mbta.constants import _stop_info_cache
    # Clear the cache before each test
    _stop_info_cache.clear()
    yield
    # Clear the cache after each test
    _stop_info_cache.clear()


@pytest.fixture
def test_config_file(tmp_path):
    """Create a temporary config file for testing."""
    config_file = tmp_path / "test_config.json"
    config_data = {"route_id": "Red"}
    config_file.write_text(json.dumps(config_data))
    return str(config_file)


@pytest.fixture
def mock_mbta_response():
    """Mock MBTA API response data."""
    return {"data": {"attributes": {"name": "Test Stop"}}}


@pytest.fixture
def mock_mbta_stops_response():
    """Mock MBTA API stops response data."""
    return {"data": [{"id": "stop_test", "attributes": {"name": "Test Stop", "latitude": 42.3601}}]}


@pytest.fixture
def mock_mbta_predictions_response():
    """Mock MBTA API predictions response data."""
    return {
        "data": [
            {
                "id": "prediction_1",
                "type": "prediction",
                "attributes": {
                    "arrival_time": "2025-01-16T10:30:00-05:00",
                    "departure_time": "2025-01-16T10:30:00-05:00",
                    "direction_id": 0,
                    "status": "On time"
                },
                "relationships": {
                    "route": {"data": {"id": "Orange"}},
                    "stop": {"data": {"id": "stop_oak_grove"}}
                }
            },
            {
                "id": "prediction_2",
                "type": "prediction",
                "attributes": {
                    "arrival_time": "2025-01-16T10:45:00-05:00",
                    "departure_time": "2025-01-16T10:45:00-05:00",
                    "direction_id": 1,
                    "status": "On time"
                },
                "relationships": {
                    "route": {"data": {"id": "Orange"}},
                    "stop": {"data": {"id": "stop_malden_center"}}
                }
            }
        ]
    }


@pytest.fixture
def mock_mbta_scheduled_times_response():
    """Mock MBTA API scheduled times response data."""
    return {
        "data": [
            {
                "id": "schedule_1",
                "type": "schedule",
                "attributes": {
                    "departure_time": "2025-01-16T11:00:00-05:00",
                    "direction_id": 0
                },
                "relationships": {
                    "stop": {"data": {"id": "70036"}}
                }
            },
            {
                "id": "schedule_2",
                "type": "schedule",
                "attributes": {
                    "departure_time": "2025-01-16T11:15:00-05:00",
                    "direction_id": 1
                },
                "relationships": {
                    "stop": {"data": {"id": "70037"}}
                }
            }
        ]
    }


@pytest.fixture
def mock_mbta_routes_response():
    """Mock MBTA API routes response data."""
    return {
        "data": [
            {
                "id": "Orange",
                "type": "route",
                "attributes": {
                    "name": "Orange Line",
                    "type": 1
                }
            },
            {
                "id": "Red",
                "type": "route",
                "attributes": {
                    "name": "Red Line",
                    "type": 1
                }
            }
        ]
    }


@pytest.fixture
def mock_mbta_error_response():
    """Mock MBTA API error response."""
    return {
        "errors": [
            {
                "status": "400",
                "title": "Bad Request",
                "detail": "Invalid route ID"
            }
        ]
    }
