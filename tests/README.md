# Tests

This directory contains the test suite for the trmnl-mbta project.

## Test Configuration

Tests use a dedicated configuration file (`test_config.json`) instead of the main `config/config.json` file. This ensures that:

1. Tests don't interfere with the main application configuration
2. Tests have consistent, predictable configuration values
3. Tests can be run independently of the main application setup

### Configuration Setup

- **Test Config File**: `tests/test_config.json`
- **Main Config File**: `config/config.json`

The test configuration is automatically applied to all tests via the `use_test_config` fixture in `conftest.py`. This fixture patches the `CONFIG_FILE` constant to point to the test configuration file.

### Test Configuration Values

The test configuration uses the following values:
- `route_id`: "Orange"

These values are chosen to be different from the main configuration to ensure tests are using the correct file.

### Running Tests

Tests can be run using pytest:

```bash
# Run all tests
pytest

# Run specific test file
pytest tests/test_mbta.py

# Run specific test
pytest tests/test_mbta.py::test_load_config
```
