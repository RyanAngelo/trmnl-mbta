# Testing Lessons Learned: Scheduled Times Issue

## Problem Summary

The "scheduled times 0" issue occurred because the scheduled times API and predictions API use different stop ID formats, but the unit tests didn't catch this real-world complexity.

## Why the Original Tests Failed to Catch the Issue

### 1. **Artificial Test Data**
**Problem**: Tests used simplified, artificial data that didn't reflect real-world complexity.

```python
# Test data - artificial
"stop": {"data": {"id": "stop_oak_grove"}}

# Real-world data - different format
"stop": {"data": {"id": "70036"}}  # Actual MBTA stop ID
```

**Lesson**: Test data should mirror real-world data formats, even if it makes tests more complex.

### 2. **Pre-populated Dependencies**
**Problem**: Tests manually set up dependencies that would be empty or different in production.

```python
# Test setup - artificial
_stop_info_cache["stop_oak_grove"] = "Oak Grove"

# Real-world - cache was empty because get_stop_info() wasn't working
_stop_info_cache = {}  # Empty in production
```

**Lesson**: Tests should verify that dependencies work correctly, not assume they're pre-populated.

### 3. **Over-mocking**
**Problem**: Tests mocked too many components, hiding integration issues.

```python
# Test - mocked response
with patch("src.mbta.display.get_scheduled_times", return_value=mock_scheduled_times):

# Real-world - actual API call with different stop ID formats
```

**Lesson**: Integration tests are needed alongside unit tests to catch issues between components.

### 4. **Missing Edge Cases**
**Problem**: Tests didn't cover the scenario where different APIs return different data formats.

**Lesson**: Test edge cases and error conditions, not just happy paths.

## Improved Testing Approach

### 1. **Realistic Test Data**
```python
# Better test data that mirrors real-world formats
mock_scheduled_times = [
    {
        "attributes": {"departure_time": "2024-06-21T10:00:00-04:00"},
        "relationships": {"stop": {"data": {"id": "70036"}}},  # Real MBTA stop ID
        "stop_name": "Oak Grove"  # What our fix adds
    }
]
```

### 2. **Integration Tests**
```python
async def test_scheduled_times_with_real_stop_id_formats():
    """Test that scheduled times work with real-world stop ID formats."""
    # Tests the integration between different API formats
```

### 3. **Error Condition Tests**
```python
async def test_scheduled_times_without_stop_name_field():
    """Test graceful handling when stop_name field is missing."""
    # Tests how the system behaves when expected data is missing
```

### 4. **API Response Tests**
```python
async def test_get_scheduled_times_with_stop_information():
    """Test that API function properly extracts stop information."""
    # Tests the actual API response parsing logic
```

## Best Practices for Future Testing

### 1. **Use Real Data Formats**
- Mirror actual API response formats in tests
- Use real stop IDs, not artificial ones
- Test with realistic data volumes

### 2. **Test Integration Points**
- Don't just test individual functions
- Test how components work together
- Verify data flows between different APIs

### 3. **Test Error Conditions**
- Test missing data scenarios
- Test API failures
- Test edge cases and boundary conditions

### 4. **Minimize Mocking**
- Mock external dependencies (APIs, databases)
- Don't mock internal logic unless necessary
- Use integration tests to verify real behavior

### 5. **Test Data Consistency**
- Verify that data formats are consistent across APIs
- Test data transformation logic
- Ensure stop ID mapping works correctly

## Conclusion

The original tests were too isolated and used artificial data, which prevented them from catching real-world integration issues. By improving test data realism and adding integration tests, we can catch similar issues in the future.

**Key Takeaway**: Unit tests are necessary but not sufficient. Integration tests with realistic data are essential for catching real-world issues.
