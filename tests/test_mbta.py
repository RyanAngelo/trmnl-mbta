import asyncio
from unittest.mock import AsyncMock, call, patch

import pytest

from mbta.main import (
    get_line_color,
    get_stop_info,
    get_stop_locations,
    logger,
    safe_load_config,
    update_trmnl_display,
)


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


@pytest.mark.asyncio
async def test_update_trmnl_display_success(mock_logger, mock_webhook_url):
    """Test successful update to TRMNL display."""
    # Create mock response
    mock_response = AsyncMock()
    mock_response.status = 200
    mock_response.text = AsyncMock(return_value="Success")
    # Create mock session with proper async context manager behavior
    mock_session = AsyncMock()
    mock_session.__aenter__.return_value = mock_session
    mock_session.post.return_value = mock_response

    async def mock_sleep(seconds):
        pass

    with patch("aiohttp.ClientSession", return_value=mock_session), patch(
        "asyncio.sleep", mock_sleep
    ):
        await update_trmnl_display(
            line_name="Orange",
            line_color="#FFA500",
            last_updated="1:00 PM",
            stop_predictions={},
            stop_names={},
        )
        # Verify the request was made with correct parameters
        mock_session.post.assert_called_once()
        call_args = mock_session.post.call_args[1]
        assert call_args["headers"]["Content-Type"] == "application/json"
        assert "merge_variables" in call_args["json"]
        # Verify the merge variables
        merge_vars = call_args["json"]["merge_variables"]
        assert merge_vars["l"] == "Orange"
        assert merge_vars["c"] == "#FFA500"
        assert merge_vars["u"] == "1:00p"
        # Verify no stop variables are present when no stops are provided
        for i in range(12):
            assert f"n{i}" not in merge_vars
            assert f"i{i}1" not in merge_vars
            assert f"i{i}2" not in merge_vars
            assert f"o{i}1" not in merge_vars
            assert f"o{i}2" not in merge_vars
        # Verify logging
        mock_logger["info"].assert_has_calls(
            [
                call("Sending update to TRMNL: {'merge_variables': %s}", merge_vars),
                call("TRMNL response status: %d", 200),
                call("TRMNL response body: %s", "Success"),
            ]
        )


@pytest.mark.asyncio
async def test_update_trmnl_display_rate_limit_with_retry_after(mock_logger, mock_webhook_url):
    """Test rate limiting with Retry-After header."""
    # Create mock responses
    mock_response1 = AsyncMock()
    mock_response1.status = 429
    mock_response1.headers = {"Retry-After": "5"}
    mock_response1.text = AsyncMock(return_value="Rate Limited")
    mock_response2 = AsyncMock()
    mock_response2.status = 200
    mock_response2.text = AsyncMock(return_value="Success")
    # Create mock session with proper async context manager behavior
    mock_session = AsyncMock()
    mock_session.__aenter__.return_value = mock_session
    mock_session.post.side_effect = [mock_response1, mock_response2]
    # Track sleep calls
    sleep_calls = []

    async def mock_sleep(seconds):
        sleep_calls.append(seconds)

    with patch("aiohttp.ClientSession", return_value=mock_session), patch(
        "asyncio.sleep", mock_sleep
    ):
        await update_trmnl_display(
            line_name="Orange",
            line_color="#FFA500",
            last_updated="1:00 PM",
            stop_predictions={},
            stop_names={},
        )
        assert mock_session.post.call_count == 2
        assert sleep_calls == [5]  # Should use Retry-After value
        mock_logger["warning"].assert_called_once_with(
            "Rate limited by TRMNL. Retrying in %d seconds... (Attempt %d)", 5, 1
        )


@pytest.mark.asyncio
async def test_update_trmnl_display_rate_limit_without_retry_after(mock_logger, mock_webhook_url):
    """Test rate limiting without Retry-After header."""
    # Create mock responses
    mock_response1 = AsyncMock()
    mock_response1.status = 429
    mock_response1.headers = {}
    mock_response1.text = AsyncMock(return_value="Rate Limited")
    mock_response2 = AsyncMock()
    mock_response2.status = 200
    mock_response2.text = AsyncMock(return_value="Success")
    # Create mock session with proper async context manager behavior
    mock_session = AsyncMock()
    mock_session.__aenter__.return_value = mock_session
    mock_session.post.side_effect = [mock_response1, mock_response2]
    # Track sleep calls
    sleep_calls = []

    async def mock_sleep(seconds):
        sleep_calls.append(seconds)

    with patch("aiohttp.ClientSession", return_value=mock_session), patch(
        "asyncio.sleep", mock_sleep
    ):
        await update_trmnl_display(
            line_name="Orange",
            line_color="#FFA500",
            last_updated="1:00 PM",
            stop_predictions={},
            stop_names={},
        )
        assert mock_session.post.call_count == 2
        assert sleep_calls == [1]  # Should use base delay on first retry
        mock_logger["warning"].assert_called_once_with(
            "Rate limited by TRMNL. Retrying in %d seconds... (Attempt %d)", 1, 1
        )


@pytest.mark.asyncio
async def test_update_trmnl_display_other_error(mock_logger, mock_webhook_url):
    """Test handling of other error responses."""
    # Create mock responses
    mock_response1 = AsyncMock()
    mock_response1.status = 500
    mock_response1.text = AsyncMock(return_value="Server Error")
    mock_response2 = AsyncMock()
    mock_response2.status = 200
    mock_response2.text = AsyncMock(return_value="Success")
    # Create mock session with proper async context manager behavior
    mock_session = AsyncMock()
    mock_session.__aenter__.return_value = mock_session
    mock_session.post.side_effect = [mock_response1, mock_response2]
    # Track sleep calls
    sleep_calls = []

    async def mock_sleep(seconds):
        sleep_calls.append(seconds)

    with patch("aiohttp.ClientSession", return_value=mock_session), patch(
        "asyncio.sleep", mock_sleep
    ):
        await update_trmnl_display(
            line_name="Orange",
            line_color="#FFA500",
            last_updated="1:00 PM",
            stop_predictions={},
            stop_names={},
        )
        assert mock_session.post.call_count == 2
        assert sleep_calls == [1]  # Should use base delay on first retry
        mock_logger["error"].assert_called_with(
            "Unexpected response from TRMNL: %d - %s", 500, "Server Error"
        )


@pytest.mark.asyncio
async def test_update_trmnl_display_network_error(mock_logger, mock_webhook_url):
    """Test handling of network errors."""
    # Create mock responses
    error = asyncio.TimeoutError("Connection timed out")
    mock_response2 = AsyncMock()
    mock_response2.status = 200
    mock_response2.text = AsyncMock(return_value="Success")
    # Create mock session with proper async context manager behavior
    mock_session = AsyncMock()
    mock_session.__aenter__.return_value = mock_session
    mock_session.post.side_effect = [error, mock_response2]
    # Track sleep calls
    sleep_calls = []

    async def mock_sleep(seconds):
        sleep_calls.append(seconds)

    with patch("aiohttp.ClientSession", return_value=mock_session), patch(
        "asyncio.sleep", mock_sleep
    ):
        await update_trmnl_display(
            line_name="Orange",
            line_color="#FFA500",
            last_updated="1:00 PM",
            stop_predictions={},
            stop_names={},
        )
        assert mock_session.post.call_count == 2
        assert sleep_calls == [1]  # Should use base delay on first retry
        mock_logger["error"].assert_called_with(
            "Error sending to TRMNL: %s", "Connection timed out"
        )
