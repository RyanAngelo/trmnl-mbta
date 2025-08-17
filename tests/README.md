# Testing Strategy

This project uses a comprehensive testing strategy with both unit tests and optional integration tests.

## Test Types

### Unit Tests (Default)
- **Location**: `tests/test_mbta.py`
- **Purpose**: Test application logic with mocked external dependencies
- **Speed**: Fast (no network calls)
- **Reliability**: High (no external dependencies)
- **Coverage**: All application functionality

### Integration Tests (Optional)
- **Location**: `tests/test_integration.py`
- **Purpose**: Test against real MBTA API
- **Speed**: Slower (network calls)
- **Reliability**: Depends on MBTA API availability
- **Usage**: Run sparingly to verify API compatibility

## Running Tests

### Unit Tests (Recommended)
```bash
# Run all unit tests
python -m pytest tests/

# Run specific test file
python -m pytest tests/test_mbta.py

# Run with coverage
python -m pytest tests/ --cov=src
```

### Integration Tests
```bash
# Enable and run integration tests
INTEGRATION_TESTS=true python -m pytest tests/test_integration.py

# Run all tests including integration
INTEGRATION_TESTS=true python -m pytest tests/
```

## Mock Data

The tests use comprehensive mock data to simulate MBTA API responses:

### Available Mock Fixtures
- `mock_mbta_response`: Basic API response
- `mock_mbta_stops_response`: Stops data
- `mock_mbta_predictions_response`: Real-time predictions
- `mock_mbta_scheduled_times_response`: Scheduled times
- `mock_mbta_routes_response`: Route information
- `mock_mbta_error_response`: API error responses

### Benefits of Mocking
- **Fast execution**: No network latency
- **Reliable**: No API downtime issues
- **Predictable**: Known test data
- **Comprehensive**: Can test edge cases and errors
- **Cost-effective**: No API quota usage

## Test Configuration

### pytest.ini
- Unit tests run by default
- Integration tests are ignored unless explicitly enabled
- Warnings are disabled for cleaner output
- Async tests are automatically detected

### Test Data
- All datetime objects are timezone-aware
- Test data uses relative time offsets (future dates)
- Tests work regardless of when they're executed

## Best Practices

1. **Use unit tests for development**: Fast feedback loop
2. **Run integration tests occasionally**: Verify API compatibility
3. **Mock external dependencies**: Ensure test reliability
4. **Test edge cases**: Use mock data to simulate unusual scenarios
5. **Keep tests independent**: No shared state between tests

## Adding New Tests

### Unit Test Example
```python
@pytest.mark.asyncio
async def test_new_feature(mock_mbta_response):
    """Test new feature with mocked data."""
    with patch("aiohttp.ClientSession.get") as mock_get:
        mock_response = AsyncMock()
        mock_response.status = 200
        mock_response.json.return_value = mock_mbta_response
        mock_get.return_value.__aenter__.return_value = mock_response
        
        # Test your function
        result = await your_function()
        assert result == expected_value
```

### Integration Test Example
```python
@pytest.mark.skipif(
    os.getenv("INTEGRATION_TESTS") != "true",
    reason="Integration tests disabled"
)
@pytest.mark.asyncio
async def test_new_feature_integration():
    """Test new feature with real API."""
    result = await your_function()
    assert result is not None
```
