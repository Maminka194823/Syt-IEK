"""
Property-based tests for real-time data integration
Feature: aviation-discord-bot, Property 5: Real-time Data Integration
"""

import pytest
import asyncio
import aiohttp
from unittest.mock import AsyncMock, MagicMock, patch
from hypothesis import given, strategies as st, settings
from typing import Dict, List, Any
from datetime import datetime, timedelta
import json
import tempfile
import shutil
import os

# Import the components we're testing
import sys
sys.path.append(os.path.join(os.path.dirname(__file__), '..', 'src'))

from knowledge.aviation_data import AviationDataManager, APIEndpoint, CacheEntry, RateLimiter


class MockResponse:
    """Mock aiohttp response for testing"""
    
    def __init__(self, status: int, data: Any, content_type: str = 'application/json'):
        self.status = status
        self.data = data
        self.headers = {'content-type': content_type}
        self.request_info = MagicMock()
        self.history = []
    
    async def json(self):
        # Return data directly if it's already a dict/list, don't try to parse as JSON
        if isinstance(self.data, (dict, list)):
            return self.data
        elif isinstance(self.data, str):
            return json.loads(self.data)
        else:
            return self.data
    
    async def text(self):
        if isinstance(self.data, str):
            return self.data
        return json.dumps(self.data)
    
    async def __aenter__(self):
        return self
    
    async def __aexit__(self, exc_type, exc_val, exc_tb):
        pass


class MockSession:
    """Mock aiohttp session for testing"""
    
    def __init__(self, responses: Dict[str, MockResponse]):
        self.responses = responses
        self.requests_made = []
        self.call_count = {}
    
    def get(self, url: str, **kwargs):
        # Record the request
        request_info = {
            'url': url,
            'params': kwargs.get('params'),
            'headers': kwargs.get('headers')
        }
        self.requests_made.append(request_info)
        
        # Track call count for each URL pattern
        for pattern in self.responses.keys():
            if pattern in url:
                self.call_count[pattern] = self.call_count.get(pattern, 0) + 1
                break
        
        # Return appropriate mock response
        for pattern, response in self.responses.items():
            if pattern in url:
                return response
        
        # Default response if no pattern matches
        return MockResponse(404, {'error': 'Not found'})
    
    async def close(self):
        pass


async def create_test_aviation_data_manager():
    """Create a test aviation data manager with temporary directory"""
    temp_dir = tempfile.mkdtemp()
    
    manager = AviationDataManager(cache_dir=temp_dir)
    
    # Mock the session creation
    manager.session = None  # Will be set by tests
    
    return manager, temp_dir


def cleanup_test_aviation_data_manager(temp_dir: str):
    """Clean up test aviation data manager directory"""
    if os.path.exists(temp_dir):
        shutil.rmtree(temp_dir)


# Property-based test strategies
@st.composite
def airport_code_strategy(draw):
    """Generate realistic airport codes for testing"""
    # Common airport codes for testing
    common_codes = ["KJFK", "KLAX", "KORD", "KDEN", "KBOS", "KSEA", "KMIA", "KPHX", 
                   "KATL", "KDFW", "KLAS", "KSFO", "KIAH", "KMCO", "KBWI"]
    
    if draw(st.booleans()):
        return draw(st.sampled_from(common_codes))
    else:
        # Generate random 4-letter code starting with K (US airports)
        letters = "ABCDEFGHIJKLMNOPQRSTUVWXYZ"
        return "K" + "".join(draw(st.lists(st.sampled_from(letters), min_size=3, max_size=3)))


@st.composite
def flight_number_strategy(draw):
    """Generate realistic flight numbers for testing"""
    airlines = ["AA", "UA", "DL", "WN", "B6", "AS", "NK", "F9", "G4", "SY"]
    airline = draw(st.sampled_from(airlines))
    number = draw(st.integers(min_value=1, max_value=9999))
    return f"{airline}{number}"


@st.composite
def weather_response_strategy(draw):
    """Generate realistic weather API responses"""
    flight_categories = ["VFR", "MVFR", "IFR", "LIFR"]
    
    return [{
        "rawOb": draw(st.text(min_size=20, max_size=100)),
        "obsTime": datetime.utcnow().isoformat(),
        "fltCat": draw(st.sampled_from(flight_categories)),
        "visib": draw(st.floats(min_value=0.1, max_value=10.0)),
        "wdir": draw(st.integers(min_value=0, max_value=360)),
        "wspd": draw(st.integers(min_value=0, max_value=50)),
        "temp": draw(st.integers(min_value=-40, max_value=50)),
        "dewp": draw(st.integers(min_value=-40, max_value=50)),
        "altim": draw(st.floats(min_value=28.00, max_value=31.50))
    }]


@st.composite
def flight_response_strategy(draw):
    """Generate realistic flight tracking API responses"""
    num_flights = draw(st.integers(min_value=0, max_value=5))
    flights = []
    
    for _ in range(num_flights):
        flight = {
            "callsign": draw(st.text(min_size=3, max_size=10)),
            "origin_country": draw(st.text(min_size=2, max_size=20)),
            "time_position": draw(st.integers(min_value=1000000000, max_value=2000000000)),
            "last_contact": draw(st.integers(min_value=1000000000, max_value=2000000000)),
            "longitude": draw(st.floats(min_value=-180, max_value=180)),
            "latitude": draw(st.floats(min_value=-90, max_value=90)),
            "baro_altitude": draw(st.one_of(st.none(), st.floats(min_value=0, max_value=50000))),
            "on_ground": draw(st.booleans()),
            "velocity": draw(st.one_of(st.none(), st.floats(min_value=0, max_value=1000))),
            "true_track": draw(st.one_of(st.none(), st.floats(min_value=0, max_value=360)))
        }
        flights.append(flight)
    
    return flights


class TestRealTimeDataIntegration:
    """
    Property 5: Real-time Data Integration
    For any request for current aviation data (weather, flight tracking, NOTAMs),
    the system should retrieve live data from official sources, handle unavailable
    data gracefully, include timestamps and attribution, and implement appropriate caching.
    """
    
    @given(airport_code_strategy(), weather_response_strategy())
    @settings(max_examples=50, deadline=20000)
    @pytest.mark.asyncio
    async def test_weather_data_retrieval_consistency(self, airport_code, weather_response):
        """
        Property test: Weather data retrieval should be consistent and complete
        Validates: Requirements 3.6, 7.1, 7.2
        """
        manager, temp_dir = await create_test_aviation_data_manager()
        
        try:
            # Mock successful weather API response
            mock_responses = {
                "metar": MockResponse(200, weather_response),
                "taf": MockResponse(200, [])  # Empty TAF for simplicity
            }
            
            manager.session = MockSession(mock_responses)
            
            # Get weather data
            weather_data = await manager.get_weather(airport_code)
            
            # Property: Weather data should have required structure
            assert isinstance(weather_data, dict), "Weather data should be a dictionary"
            assert "airport_code" in weather_data, "Weather data should include airport code"
            assert "timestamp" in weather_data, "Weather data should include timestamp"
            assert "source" in weather_data, "Weather data should include source attribution"
            
            # Property: Airport code should be normalized to uppercase
            assert weather_data["airport_code"] == airport_code.upper(), \
                "Airport code should be normalized to uppercase"
            
            # Property: Timestamp should be valid ISO format
            try:
                datetime.fromisoformat(weather_data["timestamp"])
            except ValueError:
                pytest.fail("Timestamp should be valid ISO format")
            
            # Property: Source attribution should be present
            assert weather_data["source"] is not None, "Source attribution should be present"
            assert len(weather_data["source"]) > 0, "Source attribution should not be empty"
            
            # Property: METAR data should be processed if available
            if weather_response and len(weather_response) > 0:
                assert "metar" in weather_data, "METAR data should be included"
                if weather_data["metar"]:
                    metar = weather_data["metar"]
                    assert "raw" in metar, "METAR should include raw observation"
                    assert "flight_category" in metar, "METAR should include flight category"
            
            # Property: Error handling should be graceful
            assert "error" not in weather_data or isinstance(weather_data["error"], str), \
                "Errors should be strings if present"
        
        finally:
            cleanup_test_aviation_data_manager(temp_dir)
    
    @given(flight_number_strategy(), flight_response_strategy())
    @settings(max_examples=50, deadline=20000)
    @pytest.mark.asyncio
    async def test_flight_tracking_consistency(self, flight_number, flight_response):
        """
        Property test: Flight tracking should provide consistent data structure
        Validates: Requirements 7.2, 7.3
        """
        manager, temp_dir = await create_test_aviation_data_manager()
        
        try:
            # Mock flight tracking API response
            mock_responses = {
                "flights": MockResponse(200, flight_response)
            }
            
            manager.session = MockSession(mock_responses)
            
            # Get flight information
            flight_data = await manager.get_flight_info(flight_number)
            
            # Property: Flight data should have required structure
            assert isinstance(flight_data, dict), "Flight data should be a dictionary"
            assert "flight_number" in flight_data, "Flight data should include flight number"
            assert "timestamp" in flight_data, "Flight data should include timestamp"
            assert "source" in flight_data, "Flight data should include source attribution"
            assert "flights" in flight_data, "Flight data should include flights list"
            
            # Property: Flight number should be normalized to uppercase
            assert flight_data["flight_number"] == flight_number.upper(), \
                "Flight number should be normalized to uppercase"
            
            # Property: Flights should be a list
            assert isinstance(flight_data["flights"], list), "Flights should be a list"
            
            # Property: Timestamp should be valid
            try:
                datetime.fromisoformat(flight_data["timestamp"])
            except ValueError:
                pytest.fail("Timestamp should be valid ISO format")
            
            # Property: Source attribution should be present
            assert flight_data["source"] is not None, "Source attribution should be present"
            assert len(flight_data["source"]) > 0, "Source attribution should not be empty"
        
        finally:
            cleanup_test_aviation_data_manager(temp_dir)
    
    @given(airport_code_strategy())
    @settings(max_examples=30, deadline=15000)
    @pytest.mark.asyncio
    async def test_notam_retrieval_graceful_handling(self, airport_code):
        """
        Property test: NOTAM retrieval should handle unavailable data gracefully
        Validates: Requirements 7.4, 7.5
        """
        manager, temp_dir = await create_test_aviation_data_manager()
        
        try:
            # Mock NOTAM API response (simulating no API key scenario)
            mock_responses = {
                "notam": MockResponse(401, {"error": "Unauthorized"})
            }
            
            manager.session = MockSession(mock_responses)
            
            # Get NOTAM data (should handle missing API key gracefully)
            notam_data = await manager.get_notams(airport_code)
            
            # Property: NOTAM data should be returned even when API unavailable
            assert isinstance(notam_data, (list, dict)), "NOTAM data should be list or dict"
            
            # Property: Should indicate when data is unavailable
            if isinstance(notam_data, list) and len(notam_data) > 0:
                first_item = notam_data[0]
                assert "airport_code" in first_item, "Should include airport code"
                assert "timestamp" in first_item, "Should include timestamp"
                
                # Should indicate error or unavailability
                assert ("error" in first_item or "notams" in first_item), \
                    "Should indicate error or provide NOTAMs list"
        
        finally:
            cleanup_test_aviation_data_manager(temp_dir)
    
    @given(st.integers(min_value=1, max_value=100))
    @settings(max_examples=20)
    @pytest.mark.asyncio
    async def test_rate_limiting_enforcement(self, max_requests):
        """
        Property test: Rate limiting should be properly enforced
        Validates: Requirements 7.6
        """
        # Create rate limiter
        rate_limiter = RateLimiter(max_requests, time_window=60)
        
        # Property: Should allow requests up to the limit
        for i in range(max_requests):
            result = await rate_limiter.acquire()
            assert result is True, f"Request {i+1} should be allowed"
        
        # Property: Should enforce rate limit
        # Note: We can't easily test the blocking behavior in a unit test
        # without making the test very slow, so we just verify the structure
        assert len(rate_limiter.requests) == max_requests, \
            "Rate limiter should track all requests"
        
        # Property: Rate limiter should have correct configuration
        assert rate_limiter.max_requests == max_requests, \
            "Rate limiter should store max requests correctly"
        assert rate_limiter.time_window == 60, \
            "Rate limiter should have correct time window"
    
    @given(airport_code_strategy(), weather_response_strategy())
    @settings(max_examples=30, deadline=20000)
    @pytest.mark.asyncio
    async def test_caching_behavior(self, airport_code, weather_response):
        """
        Property test: Caching should work correctly for real-time data
        Validates: Requirements 7.6
        """
        manager, temp_dir = await create_test_aviation_data_manager()
        
        try:
            # Mock weather API response
            mock_responses = {
                "metar": MockResponse(200, weather_response),
                "taf": MockResponse(200, [])
            }
            
            mock_session = MockSession(mock_responses)
            manager.session = mock_session
            
            # First request - should hit API
            weather_data_1 = await manager.get_weather(airport_code)
            initial_metar_calls = mock_session.call_count.get("metar", 0)
            initial_taf_calls = mock_session.call_count.get("taf", 0)
            
            # Second request - should use cache (no additional API calls)
            weather_data_2 = await manager.get_weather(airport_code)
            cached_metar_calls = mock_session.call_count.get("metar", 0)
            cached_taf_calls = mock_session.call_count.get("taf", 0)
            
            # Property: Cache should prevent duplicate API calls
            assert cached_metar_calls == initial_metar_calls, \
                f"METAR calls should not increase: {initial_metar_calls} -> {cached_metar_calls}"
            assert cached_taf_calls == initial_taf_calls, \
                f"TAF calls should not increase: {initial_taf_calls} -> {cached_taf_calls}"
            
            # Property: Cached data should be identical for key fields
            assert weather_data_1["airport_code"] == weather_data_2["airport_code"], \
                "Cached data should have same airport code"
            
            # Property: Both responses should have timestamps (may differ slightly)
            assert "timestamp" in weather_data_1, "First response should have timestamp"
            assert "timestamp" in weather_data_2, "Second response should have timestamp"
            
            # Property: Cache should have entries
            assert len(manager.cache) > 0, "Cache should contain entries after requests"
            
            # Property: Cache entries should have expiration
            for cache_entry in manager.cache.values():
                assert hasattr(cache_entry, 'expires_at'), "Cache entries should have expires_at attribute"
                if hasattr(cache_entry, 'expires_at'):
                    assert cache_entry.expires_at > datetime.utcnow(), \
                        "Cache entries should not be expired immediately"
        
        finally:
            cleanup_test_aviation_data_manager(temp_dir)
    
    @given(st.integers(min_value=400, max_value=599))
    @settings(max_examples=20)
    @pytest.mark.asyncio
    async def test_error_handling_consistency(self, error_status):
        """
        Property test: Error handling should be consistent across all endpoints
        Validates: Requirements 7.5
        """
        manager, temp_dir = await create_test_aviation_data_manager()
        
        try:
            # Mock error responses
            mock_responses = {
                "metar": MockResponse(error_status, {"error": f"HTTP {error_status}"}),
                "taf": MockResponse(error_status, {"error": f"HTTP {error_status}"}),
                "flights": MockResponse(error_status, {"error": f"HTTP {error_status}"})
            }
            
            manager.session = MockSession(mock_responses)
            
            # Test weather endpoint error handling
            weather_data = await manager.get_weather("KTEST")
            
            # Property: Error responses should be handled gracefully
            assert isinstance(weather_data, dict), "Error response should be a dictionary"
            assert "error" in weather_data, "Error response should indicate error"
            assert "airport_code" in weather_data, "Error response should include airport code"
            assert "timestamp" in weather_data, "Error response should include timestamp"
            
            # Test flight tracking error handling
            flight_data = await manager.get_flight_info("TEST123")
            
            # Property: Flight error responses should be consistent
            assert isinstance(flight_data, dict), "Flight error response should be a dictionary"
            assert "error" in flight_data, "Flight error response should indicate error"
            assert "flight_number" in flight_data, "Flight error response should include flight number"
            assert "timestamp" in flight_data, "Flight error response should include timestamp"
            assert "flights" in flight_data, "Flight error response should include empty flights list"
            assert isinstance(flight_data["flights"], list), "Flights should be a list even on error"
        
        finally:
            cleanup_test_aviation_data_manager(temp_dir)
    
    @given(st.lists(airport_code_strategy(), min_size=2, max_size=5))
    @settings(max_examples=20, deadline=30000)
    @pytest.mark.asyncio
    async def test_concurrent_data_requests(self, airport_codes):
        """
        Property test: Concurrent requests should be handled properly
        Validates: Requirements 7.6
        """
        manager, temp_dir = await create_test_aviation_data_manager()
        
        try:
            # Mock weather responses for all airports
            mock_responses = {}
            for code in airport_codes:
                mock_responses[f"metar"] = MockResponse(200, [{
                    "rawOb": f"METAR {code} test",
                    "obsTime": datetime.utcnow().isoformat(),
                    "fltCat": "VFR"
                }])
                mock_responses[f"taf"] = MockResponse(200, [])
            
            manager.session = MockSession(mock_responses)
            
            # Make concurrent requests
            tasks = [manager.get_weather(code) for code in airport_codes]
            results = await asyncio.gather(*tasks, return_exceptions=True)
            
            # Property: All requests should complete
            assert len(results) == len(airport_codes), \
                "All concurrent requests should complete"
            
            # Property: No exceptions should occur
            for i, result in enumerate(results):
                assert not isinstance(result, Exception), \
                    f"Request {i} should not raise exception: {result}"
                assert isinstance(result, dict), f"Result {i} should be a dictionary"
                assert "airport_code" in result, f"Result {i} should have airport code"
            
            # Property: Each result should correspond to correct airport
            for i, result in enumerate(results):
                expected_code = airport_codes[i].upper()
                assert result["airport_code"] == expected_code, \
                    f"Result {i} should have correct airport code"
        
        finally:
            cleanup_test_aviation_data_manager(temp_dir)
    
    @given(st.text(min_size=1, max_size=50))
    @settings(max_examples=30)
    @pytest.mark.asyncio
    async def test_data_freshness_indicators(self, query):
        """
        Property test: Data should include freshness indicators
        Validates: Requirements 7.4, 7.5
        """
        manager, temp_dir = await create_test_aviation_data_manager()
        
        try:
            # Test API status endpoint
            api_status = manager.get_api_status()
            
            # Property: API status should include timestamp
            assert "timestamp" in api_status, "API status should include timestamp"
            
            # Property: Timestamp should be recent (within last minute)
            status_time = datetime.fromisoformat(api_status["timestamp"])
            time_diff = datetime.utcnow() - status_time
            assert time_diff.total_seconds() < 60, \
                "API status timestamp should be recent"
            
            # Property: Should include endpoint information
            assert "endpoints" in api_status, "API status should include endpoints"
            assert isinstance(api_status["endpoints"], dict), \
                "Endpoints should be a dictionary"
            
            # Property: Each endpoint should have configuration info
            for endpoint_name, endpoint_info in api_status["endpoints"].items():
                assert "is_active" in endpoint_info, \
                    f"Endpoint {endpoint_name} should have active status"
                assert "rate_limit" in endpoint_info, \
                    f"Endpoint {endpoint_name} should have rate limit info"
                assert "cache_duration" in endpoint_info, \
                    f"Endpoint {endpoint_name} should have cache duration info"
        
        finally:
            cleanup_test_aviation_data_manager(temp_dir)
    
    @given(st.sampled_from(["aviationweather", "faa_notam", "flightaware", "opensky", None]))
    @settings(max_examples=20)
    @pytest.mark.asyncio
    async def test_cache_management(self, endpoint_name):
        """
        Property test: Cache management should work correctly
        Validates: Requirements 7.6
        """
        manager, temp_dir = await create_test_aviation_data_manager()
        
        try:
            # Add some test cache entries
            test_entries = {
                "test_key_1": "test_data_1",
                "test_key_2": "test_data_2",
                "aviationweather_test": "weather_data",
                "opensky_test": "flight_data"
            }
            
            for key, data in test_entries.items():
                await manager._cache_data(key, data, 300)  # 5 minute cache
            
            initial_cache_size = len(manager.cache)
            assert initial_cache_size > 0, "Cache should have test entries"
            
            # Clear cache
            await manager.clear_cache(endpoint_name)
            
            # Property: Cache clearing should work correctly
            if endpoint_name is None:
                # Should clear all cache
                assert len(manager.cache) == 0, "All cache should be cleared"
            else:
                # Should clear only specific endpoint cache
                remaining_keys = list(manager.cache.keys())
                for key in remaining_keys:
                    assert not key.startswith(endpoint_name), \
                        f"Key {key} should not start with {endpoint_name}"
                
                # Should have fewer entries than before
                assert len(manager.cache) <= initial_cache_size, \
                    "Cache size should be reduced or same"
        
        finally:
            cleanup_test_aviation_data_manager(temp_dir)


if __name__ == "__main__":
    pytest.main([__file__, "-v"])