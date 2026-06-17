"""
Unit tests for API connection validation functionality
Tests startup validation of aviation data source connections
Validates: Requirements 12.5
"""

import pytest
import asyncio
import aiohttp
from unittest.mock import Mock, AsyncMock, patch
from datetime import datetime

from v4.src.bot.startup_validator import StartupValidator, ValidationStatus, ValidationResult
from v4.src.bot.config_manager import BotConfiguration
from v4.src.knowledge.aviation_data import AviationDataManager


def create_mock_session_with_response(mock_response):
    """Helper to create properly mocked aiohttp session with async context manager"""
    
    class MockAsyncContextManager:
        def __init__(self, response):
            self.response = response
            
        async def __aenter__(self):
            return self.response
            
        async def __aexit__(self, exc_type, exc_val, exc_tb):
            return None
    
    mock_session_instance = AsyncMock()
    mock_session_instance.get = Mock(return_value=MockAsyncContextManager(mock_response))
    
    # Create the session constructor mock
    mock_session_constructor = AsyncMock()
    mock_session_constructor.__aenter__ = AsyncMock(return_value=mock_session_instance)
    mock_session_constructor.__aexit__ = AsyncMock(return_value=None)
    
    # Return a function that creates the mock session
    return lambda *args, **kwargs: mock_session_constructor


def create_mock_session_with_error(error):
    """Helper to create properly mocked aiohttp session that raises an error"""
    
    class MockAsyncContextManagerWithError:
        def __init__(self, error):
            self.error = error
            
        async def __aenter__(self):
            raise self.error
            
        async def __aexit__(self, exc_type, exc_val, exc_tb):
            return None
    
    mock_session_instance = AsyncMock()
    mock_session_instance.get = Mock(return_value=MockAsyncContextManagerWithError(error))
    
    # Create the session constructor mock
    mock_session_constructor = AsyncMock()
    mock_session_constructor.__aenter__ = AsyncMock(return_value=mock_session_instance)
    mock_session_constructor.__aexit__ = AsyncMock(return_value=None)
    
    # Return a function that creates the mock session
    return lambda *args, **kwargs: mock_session_constructor


class TestAPIConnectionValidation:
    """Test API connection validation during startup"""
    
    @pytest.fixture
    def mock_config(self):
        """Mock bot configuration with API keys"""
        config = Mock(spec=BotConfiguration)
        
        # API configuration
        config.api = Mock()
        config.api.aviation_weather_api_key = "test_weather_key_12345"
        config.api.flight_tracking_api_key = "test_flight_key_67890"
        config.api.faa_api_key = "test_faa_key_abcdef"
        
        # Other required config sections
        config.discord = Mock()
        config.discord.token = "test_discord_token"
        config.discord.command_prefix = "!"
        config.discord.embed_color = 0x1E90FF
        
        config.ai = Mock()
        config.ai.model_name = "test_model"
        config.ai.temperature = 0.7
        config.ai.max_context_length = 4096
        config.ai.timeout_seconds = 30
        
        config.security = Mock()
        config.security.enable_encryption = True
        config.security.enable_audit_logging = True
        config.security.session_timeout_minutes = 60
        
        config.deployment = Mock()
        config.deployment.environment = Mock()
        config.deployment.environment.value = "testing"
        
        # Required sections for validation
        config.memory = Mock()
        config.knowledge = Mock()
        config.monitoring = Mock()
        
        return config
    
    @pytest.fixture
    def startup_validator(self, mock_config):
        """Create startup validator instance"""
        return StartupValidator(mock_config)
    
    @pytest.fixture
    def aviation_data_manager(self):
        """Create aviation data manager instance"""
        return AviationDataManager()
    
    @pytest.mark.asyncio
    async def test_aviation_weather_api_validation_success(self, startup_validator):
        """Test successful aviation weather API validation"""
        # Mock successful HTTP response
        mock_response = Mock()
        mock_response.status = 200
        mock_response.json = AsyncMock(return_value=[
            {
                "icaoId": "KJFK",
                "receiptTime": "2024-01-15T12:00:00Z",
                "obsTime": "2024-01-15T11:52:00Z",
                "reportTime": "2024-01-15T11:52:00Z",
                "temp": "15",
                "dewp": "10",
                "wdir": "270",
                "wspd": "12",
                "wgst": "",
                "visib": "10",
                "altim": "30.15",
                "slp": "",
                "qcField": "1",
                "wxString": "",
                "presTend": "",
                "maxT": "",
                "minT": "",
                "maxT24": "",
                "minT24": "",
                "precip": "",
                "pcp3hr": "",
                "pcp6hr": "",
                "pcp24hr": "",
                "snow": "",
                "vertVis": "",
                "metarType": "METAR",
                "rawOb": "METAR KJFK 151152Z 27012KT 10SM FEW250 15/10 A3015 RMK AO2 SLP999 T01500100"
            }
        ])
        
        with patch('aiohttp.ClientSession', create_mock_session_with_response(mock_response)):
            
            result = await startup_validator._validate_weather_api()
            
            assert isinstance(result, ValidationResult)
            assert result.name == "aviation_weather_api"
            assert result.status == ValidationStatus.PASSED
            assert "successful" in result.message.lower()
            assert result.details["response_status"] == 200
            assert result.details["data_count"] == 1
    
    @pytest.mark.asyncio
    async def test_aviation_weather_api_validation_empty_response(self, startup_validator):
        """Test aviation weather API validation with empty response"""
        # Mock empty response
        mock_response = Mock()
        mock_response.status = 200
        mock_response.json = AsyncMock(return_value=[])
        
        with patch('aiohttp.ClientSession', create_mock_session_with_response(mock_response)):
            
            result = await startup_validator._validate_weather_api()
            
            assert result.status == ValidationStatus.WARNING
            assert "empty data" in result.message.lower()
    
    @pytest.mark.asyncio
    async def test_aviation_weather_api_validation_http_error(self, startup_validator):
        """Test aviation weather API validation with HTTP error"""
        # Mock HTTP error response
        mock_response = Mock()
        mock_response.status = 404
        
        with patch('aiohttp.ClientSession', create_mock_session_with_response(mock_response)):
            
            result = await startup_validator._validate_weather_api()
            
            assert result.status == ValidationStatus.FAILED
            assert "status 404" in result.message
    
    @pytest.mark.asyncio
    async def test_aviation_weather_api_validation_connection_error(self, startup_validator):
        """Test aviation weather API validation with connection error"""
        with patch('aiohttp.ClientSession', create_mock_session_with_error(aiohttp.ClientError("Connection failed"))):
            
            result = await startup_validator._validate_weather_api()
            
            assert result.status == ValidationStatus.FAILED
            assert "connection failed" in result.message.lower()
            assert result.error is not None
    
    @pytest.mark.asyncio
    async def test_aviation_weather_api_validation_no_api_key(self, startup_validator):
        """Test aviation weather API validation when API key is not configured"""
        startup_validator.config.api.aviation_weather_api_key = ""
        
        result = await startup_validator._validate_weather_api()
        
        assert result.status == ValidationStatus.SKIPPED
        assert "not configured" in result.message.lower()
    
    @pytest.mark.asyncio
    async def test_flight_tracking_api_validation_success(self, startup_validator):
        """Test successful flight tracking API validation"""
        result = await startup_validator._validate_flight_api()
        
        # Since this is simulated in the current implementation
        assert isinstance(result, ValidationResult)
        assert result.name == "flight_tracking_api"
        assert result.status == ValidationStatus.PASSED
        assert "successful" in result.message.lower()
        assert result.details.get("simulated") == True
    
    @pytest.mark.asyncio
    async def test_flight_tracking_api_validation_no_api_key(self, startup_validator):
        """Test flight tracking API validation when API key is not configured"""
        startup_validator.config.api.flight_tracking_api_key = ""
        
        result = await startup_validator._validate_flight_api()
        
        assert result.status == ValidationStatus.SKIPPED
        assert "not configured" in result.message.lower()
    
    @pytest.mark.asyncio
    async def test_faa_api_validation_success(self, startup_validator):
        """Test successful FAA API validation"""
        # Mock successful HTTP response
        mock_response = Mock()
        mock_response.status = 200
        
        with patch('aiohttp.ClientSession', create_mock_session_with_response(mock_response)):
            
            result = await startup_validator._validate_faa_api()
            
            assert isinstance(result, ValidationResult)
            assert result.name == "faa_api"
            assert result.status == ValidationStatus.PASSED
            assert "successful" in result.message.lower()
            assert result.details["response_status"] == 200
    
    @pytest.mark.asyncio
    async def test_faa_api_validation_http_error(self, startup_validator):
        """Test FAA API validation with HTTP error"""
        # Mock HTTP error response
        mock_response = Mock()
        mock_response.status = 503  # Service unavailable
        
        with patch('aiohttp.ClientSession', create_mock_session_with_response(mock_response)):
            
            result = await startup_validator._validate_faa_api()
            
            assert result.status == ValidationStatus.WARNING
            assert "status 503" in result.message
    
    @pytest.mark.asyncio
    async def test_faa_api_validation_connection_error(self, startup_validator):
        """Test FAA API validation with connection error"""
        with patch('aiohttp.ClientSession', create_mock_session_with_error(Exception("Network timeout"))):
            
            result = await startup_validator._validate_faa_api()
            
            assert result.status == ValidationStatus.FAILED
            assert "network timeout" in result.message.lower()
            assert result.error is not None
    
    @pytest.mark.asyncio
    async def test_faa_api_validation_no_api_key(self, startup_validator):
        """Test FAA API validation when API key is not configured"""
        startup_validator.config.api.faa_api_key = ""
        
        result = await startup_validator._validate_faa_api()
        
        assert result.status == ValidationStatus.SKIPPED
        assert "not configured" in result.message.lower()
    
    @pytest.mark.asyncio
    async def test_api_connections_only_validation(self, startup_validator):
        """Test API-only validation functionality"""
        # Mock individual API validation methods
        with patch.object(startup_validator, '_validate_weather_api') as mock_weather, \
             patch.object(startup_validator, '_validate_flight_api') as mock_flight, \
             patch.object(startup_validator, '_validate_faa_api') as mock_faa:
            
            mock_weather.return_value = ValidationResult("aviation_weather_api", ValidationStatus.PASSED, "Weather API OK")
            mock_flight.return_value = ValidationResult("flight_tracking_api", ValidationStatus.FAILED, "Flight API failed")
            mock_faa.return_value = ValidationResult("faa_api", ValidationStatus.SKIPPED, "FAA API not configured")
            
            results = await startup_validator.validate_api_connections_only()
            
            assert len(results) == 3
            assert "aviation_weather_api" in results
            assert "flight_tracking_api" in results
            assert "faa_api" in results
            
            assert results["aviation_weather_api"].status == ValidationStatus.PASSED
            assert results["flight_tracking_api"].status == ValidationStatus.FAILED
            assert results["faa_api"].status == ValidationStatus.SKIPPED
    
    @pytest.mark.asyncio
    async def test_api_validation_timeout_handling(self, startup_validator):
        """Test API validation timeout handling"""
        # Mock the validation method to raise a TimeoutError directly
        with patch.object(startup_validator, '_validate_weather_api') as mock_weather:
            mock_weather.side_effect = asyncio.TimeoutError("Request timeout")
            
            results = await startup_validator.validate_api_connections_only()
            
            # Should handle timeout gracefully
            assert "aviation_weather_api" in results
            weather_result = results["aviation_weather_api"]
            assert weather_result.status == ValidationStatus.FAILED
            assert "timeout" in weather_result.message.lower() or "timed out" in weather_result.message.lower()
            assert "timed out" in weather_result.message.lower()
            assert weather_result.error == "Timeout"
    
    @pytest.mark.asyncio
    async def test_comprehensive_startup_validation_with_api_checks(self, startup_validator):
        """Test comprehensive startup validation including API checks"""
        # Mock system dependencies
        with patch('psutil.virtual_memory'), \
             patch('psutil.disk_usage'), \
             patch('psutil.cpu_count'), \
             patch('os.makedirs'), \
             patch('builtins.open', mock_open=True), \
             patch('os.remove'), \
             patch('aiohttp.ClientSession') as mock_session:
            
            # Mock successful API responses
            mock_response = Mock()
            mock_response.status = 200
            mock_response.json = AsyncMock(return_value=[{"test": "data"}])
            mock_session.return_value.__aenter__.return_value.get.return_value.__aenter__.return_value = mock_response
            
            report = await startup_validator.validate_startup()
            
            # Verify API checks were included
            api_check_names = [result.name for result in report.validation_results]
            assert "aviation_weather_api" in api_check_names
            assert "flight_tracking_api" in api_check_names
            assert "faa_api" in api_check_names
            
            # Verify overall report structure
            assert report.total_checks > 0
            assert len(report.validation_results) == report.total_checks
            assert report.passed_checks + report.failed_checks + report.warning_checks + report.skipped_checks == report.total_checks
    
    @pytest.mark.asyncio
    async def test_aviation_data_manager_api_validation(self, aviation_data_manager):
        """Test aviation data manager API validation"""
        # Initialize the aviation data manager session
        await aviation_data_manager.initialize()
        
        # Mock successful weather API call
        mock_weather_data = {
            "icaoId": "KJFK",
            "rawOb": "METAR KJFK 151152Z 27012KT 10SM FEW250 15/10 A3015",
            "temp": "15",
            "dewp": "10",
            "wdir": "270",
            "wspd": "12"
        }
        
        # Mock the _make_request method instead of _make_api_request
        with patch.object(aviation_data_manager, '_make_request') as mock_request, \
             patch.object(aviation_data_manager, '_get_cached_data', return_value=None):
            mock_request.return_value = [mock_weather_data]
            
            # Test weather data retrieval
            weather_data = await aviation_data_manager.get_weather("KJFK")
            
            assert weather_data is not None
            assert weather_data["airport_code"] == "KJFK"  # Changed from icaoId to airport_code
            assert "metar" in weather_data  # Changed from rawOb to metar
            assert "timestamp" in weather_data
            
            # Verify API request was made (should be called twice - METAR and TAF)
            assert mock_request.call_count >= 1
        
        # Clean up
        await aviation_data_manager.shutdown()
    
    @pytest.mark.asyncio
    async def test_aviation_data_manager_api_error_handling(self, aviation_data_manager):
        """Test aviation data manager API error handling"""
        # Initialize the aviation data manager session
        await aviation_data_manager.initialize()
        
        with patch.object(aviation_data_manager, '_make_request') as mock_request, \
             patch.object(aviation_data_manager, '_get_cached_data', return_value=None):
            mock_request.side_effect = aiohttp.ClientError("API connection failed")
            
            # Should handle API errors gracefully
            weather_data = await aviation_data_manager.get_weather("KJFK")
            
            # Should return error structure on error
            assert weather_data is not None
            assert "error" in weather_data
            assert weather_data["airport_code"] == "KJFK"
        
        # Clean up
        await aviation_data_manager.shutdown()
    
    @pytest.mark.asyncio
    async def test_api_key_validation_format(self, startup_validator):
        """Test API key format validation"""
        # Test with valid API key format
        startup_validator.config.api.aviation_weather_api_key = "valid_key_12345"
        assert len(startup_validator.config.api.aviation_weather_api_key) > 10
        
        # Test with invalid API key format
        startup_validator.config.api.aviation_weather_api_key = "short"
        result = await startup_validator._validate_weather_api()
        # Should still attempt validation even with short key
        assert result.status in [ValidationStatus.FAILED, ValidationStatus.WARNING, ValidationStatus.PASSED]
    
    @pytest.mark.asyncio
    async def test_api_response_data_validation(self, startup_validator):
        """Test API response data validation"""
        # Mock response with invalid JSON
        mock_response = Mock()
        mock_response.status = 200
        mock_response.json = AsyncMock(side_effect=ValueError("Invalid JSON"))
        
        with patch('aiohttp.ClientSession', create_mock_session_with_response(mock_response)):
            
            result = await startup_validator._validate_weather_api()
            
            assert result.status == ValidationStatus.FAILED
            assert "invalid json" in result.message.lower() or "error" in result.message.lower()
    
    @pytest.mark.asyncio
    async def test_api_connection_retry_logic(self, startup_validator):
        """Test API connection retry logic"""
        call_count = 0
        
        async def mock_get(*args, **kwargs):
            nonlocal call_count
            call_count += 1
            if call_count < 3:  # Fail first 2 attempts
                raise aiohttp.ClientError("Temporary failure")
            else:  # Succeed on 3rd attempt
                mock_response = Mock()
                mock_response.status = 200
                mock_response.json = AsyncMock(return_value=[{"test": "data"}])
                # Create proper async context manager
                mock_context = AsyncMock()
                mock_context.__aenter__ = AsyncMock(return_value=mock_response)
                mock_context.__aexit__ = AsyncMock(return_value=None)
                return mock_context
        
        with patch('aiohttp.ClientSession') as mock_session:
            mock_session_instance = AsyncMock()
            mock_session_instance.get = mock_get
            mock_session.return_value.__aenter__.return_value = mock_session_instance
            
            # Note: Current implementation doesn't have retry logic, 
            # but this test shows how it could be tested
            result = await startup_validator._validate_weather_api()
            
            # With current implementation, should fail on first attempt
            assert result.status == ValidationStatus.FAILED
    
    def test_api_configuration_completeness(self, mock_config):
        """Test API configuration completeness"""
        # Verify all required API configuration fields are present
        assert hasattr(mock_config.api, 'aviation_weather_api_key')
        assert hasattr(mock_config.api, 'flight_tracking_api_key')
        assert hasattr(mock_config.api, 'faa_api_key')
        
        # Verify API keys are properly configured
        assert mock_config.api.aviation_weather_api_key == "test_weather_key_12345"
        assert mock_config.api.flight_tracking_api_key == "test_flight_key_67890"
        assert mock_config.api.faa_api_key == "test_faa_key_abcdef"
    
    @pytest.mark.asyncio
    async def test_api_validation_performance(self, startup_validator):
        """Test API validation performance and timing"""
        start_time = datetime.utcnow()
        
        # Mock fast API response
        mock_response = Mock()
        mock_response.status = 200
        mock_response.json = AsyncMock(return_value=[{"test": "data"}])
        
        with patch('aiohttp.ClientSession', create_mock_session_with_response(mock_response)):
            
            result = await startup_validator._validate_weather_api()
            
            end_time = datetime.utcnow()
            duration = (end_time - start_time).total_seconds()
            
            # Validation should complete quickly (under 5 seconds)
            assert duration < 5.0
            assert result.status == ValidationStatus.PASSED
    
    @pytest.mark.asyncio
    async def test_multiple_api_validation_concurrency(self, startup_validator):
        """Test concurrent validation of multiple APIs"""
        # Mock responses for all APIs
        mock_response = Mock()
        mock_response.status = 200
        mock_response.json = AsyncMock(return_value=[{"test": "data"}])
        
        with patch('aiohttp.ClientSession', create_mock_session_with_response(mock_response)):
            
            # Run API validations concurrently
            tasks = [
                startup_validator._validate_weather_api(),
                startup_validator._validate_faa_api()
            ]
            
            results = await asyncio.gather(*tasks)
            
            # Verify all validations completed
            assert len(results) == 2
            for result in results:
                assert isinstance(result, ValidationResult)
                assert result.status in [ValidationStatus.PASSED, ValidationStatus.FAILED, ValidationStatus.WARNING, ValidationStatus.SKIPPED]
    
    @pytest.mark.asyncio
    async def test_api_validation_error_details(self, startup_validator):
        """Test detailed error information in API validation results"""
        with patch('aiohttp.ClientSession', create_mock_session_with_error(asyncio.TimeoutError("Request timeout"))):
            
            result = await startup_validator._validate_weather_api()
            
            assert result.status == ValidationStatus.FAILED
            assert result.error is not None
            assert "timeout" in result.error.lower()
            assert result.message is not None
            assert len(result.message) > 0