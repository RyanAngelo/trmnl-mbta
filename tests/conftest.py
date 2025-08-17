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
