import json
import pytest
from mbta.main import RouteConfig

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
    return {
        "data": {
            "attributes": {
                "name": "Test Stop"
            }
        }
    }

@pytest.fixture
def mock_mbta_stops_response():
    """Mock MBTA API stops response data."""
    return {
        "data": [
            {
                "attributes": {
                    "name": "Test Stop",
                    "latitude": 42.3601
                }
            }
        ]
    } 