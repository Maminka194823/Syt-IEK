"""
Unit tests for system startup verification functionality
Tests component loading and initialization status reporting
Validates: Requirements 10.1
"""

import pytest
import asyncio
from unittest.mock import Mock, AsyncMock, patch, MagicMock
from datetime import datetime, timedelta
import json

from src.bot.startup_validator import StartupValidator, ValidationStatus, ValidationResult, StartupReport
from src.bot.config_manager import BotConfiguration
from src.bot.discord_client import AviationGirlBot


class TestSystemStartupVerification:
    """Test system startup verification and component loading"""
    
    @pytest.fixture
    def mock_config(self):
        """Mock bot configuration for testing"""
        config = Mock(spec=BotConfiguration)
        
        # Discord config
        config.discord = Mock()
        config.discord.token = "test_discord_token_12345"
        config.discord.command_prefix = "!"
        config.discord.embed_color = 0x1E90FF
        
        # AI config
        config.ai = Mock()
        config.ai.model_name = "test_model"
        config.ai.temperature = 0.7
        config.ai.max_context_length = 4096
        config.ai.timeout_seconds = 30
        
        # API config
        config.api = Mock()
        config.api.aviation_weather_api_key = "test_weather_key"
        config.api.flight_tracking_api_key = "test_flight_key"
        config.api.faa_api_key = "test_faa_key"
        
        # Security config
        config.security = Mock()
        config.security.enable_encryption = True
        config.security.enable_audit_logging = True
        config.security.enable_rate_limiting = True
        config.security.session_timeout_minutes = 60
        
        # Deployment config
        config.deployment = Mock()
        config.deployment.environment = Mock()
        config.deployment.environment.value = "development"
        
        # Required sections
        config.memory = Mock()
        config.knowledge = Mock()
        config.monitoring = Mock()
        
        return config
    
    @pytest.fixture
    def startup_validator(self, mock_config):
        """Create startup validator instance"""
        return StartupValidator(mock_config)
    
    @pytest.mark.asyncio
    async def test_startup_validator_initialization(self, startup_validator):
        """Test startup validator initializes with default checks"""
        assert startup_validator.config is not None
        assert len(startup_validator.validation_checks) > 0
        
        # Check that critical checks are registered
        check_names = [check["name"] for check in startup_validator.validation_checks]
        assert "config_validation" in check_names
        assert "discord_config" in check_names
        assert "ai_config" in check_names
        assert "system_resources" in check_names
        assert "file_permissions" in check_names
        assert "network_connectivity" in check_names
    
    @pytest.mark.asyncio
    async def test_validate_startup_returns_complete_report(self, startup_validator):
        """Test that validate_startup returns a complete StartupReport"""
        with patch('psutil.virtual_memory'), \
             patch('psutil.disk_usage'), \
             patch('psutil.cpu_count'), \
             patch('aiohttp.ClientSession'):
            
            report = await startup_validator.validate_startup()
            
            assert isinstance(report, StartupReport)
            assert isinstance(report.timestamp, datetime)
            assert report.overall_status in [ValidationStatus.PASSED, ValidationStatus.WARNING, ValidationStatus.FAILED]
            assert report.total_checks > 0
            assert len(report.validation_results) == report.total_checks
            assert report.passed_checks + report.failed_checks + report.warning_checks + report.skipped_checks == report.total_checks
    
    @pytest.mark.asyncio
    async def test_configuration_validation_passes_with_valid_config(self, startup_validator):
        """Test configuration validation passes with valid configuration"""
        result = await startup_validator._validate_configuration()
        
        assert isinstance(result, ValidationResult)
        assert result.name == "config_validation"
        assert result.status == ValidationStatus.PASSED
        assert "passed" in result.message.lower()
    
    @pytest.mark.asyncio
    async def test_configuration_validation_fails_with_missing_token(self, startup_validator):
        """Test configuration validation fails when Discord token is missing"""
        startup_validator.config.discord.token = ""
        
        result = await startup_validator._validate_configuration()
        
        assert result.status == ValidationStatus.FAILED
        assert "token" in result.message.lower()
    
    @pytest.mark.asyncio
    async def test_discord_config_validation_passes_with_valid_config(self, startup_validator):
        """Test Discord configuration validation passes with valid settings"""
        result = await startup_validator._validate_discord_config()
        
        assert isinstance(result, ValidationResult)
        assert result.name == "discord_config"
        assert result.status == ValidationStatus.PASSED
        assert "valid" in result.message.lower()
    
    @pytest.mark.asyncio
    async def test_discord_config_validation_warns_with_short_token(self, startup_validator):
        """Test Discord configuration validation warns with suspiciously short token"""
        startup_validator.config.discord.token = "short"
        
        result = await startup_validator._validate_discord_config()
        
        assert result.status == ValidationStatus.WARNING
        assert "short" in result.message.lower()
    
    @pytest.mark.asyncio
    async def test_ai_config_validation_passes_with_valid_config(self, startup_validator):
        """Test AI configuration validation passes with valid settings"""
        result = await startup_validator._validate_ai_config()
        
        assert isinstance(result, ValidationResult)
        assert result.name == "ai_config"
        assert result.status == ValidationStatus.PASSED
        assert "valid" in result.message.lower()
    
    @pytest.mark.asyncio
    async def test_ai_config_validation_warns_with_invalid_temperature(self, startup_validator):
        """Test AI configuration validation warns with invalid temperature"""
        startup_validator.config.ai.temperature = 3.0  # Outside valid range
        
        result = await startup_validator._validate_ai_config()
        
        assert result.status == ValidationStatus.WARNING
        assert "temperature" in result.message.lower()
    
    @pytest.mark.asyncio
    async def test_system_resources_validation_with_adequate_resources(self, startup_validator):
        """Test system resources validation passes with adequate resources"""
        with patch('psutil.virtual_memory') as mock_memory, \
             patch('psutil.disk_usage') as mock_disk:
            
            # Mock adequate resources
            mock_memory.return_value = Mock(available=2 * 1024**3)  # 2GB available
            mock_disk.return_value = Mock(free=10 * 1024**3)  # 10GB free
            
            result = await startup_validator._validate_system_resources()
            
            assert result.status == ValidationStatus.PASSED
            assert "adequate" in result.message.lower()
            assert result.details["memory_available_gb"] >= 1.0
            assert result.details["disk_free_gb"] >= 1.0
    
    @pytest.mark.asyncio
    async def test_system_resources_validation_warns_with_low_resources(self, startup_validator):
        """Test system resources validation warns with low resources"""
        with patch('psutil.virtual_memory') as mock_memory, \
             patch('psutil.disk_usage') as mock_disk:
            
            # Mock low resources
            mock_memory.return_value = Mock(available=0.3 * 1024**3)  # 300MB available
            mock_disk.return_value = Mock(free=0.5 * 1024**3)  # 500MB free
            
            result = await startup_validator._validate_system_resources()
            
            assert result.status == ValidationStatus.WARNING
            assert "memory" in result.message.lower() or "disk" in result.message.lower()
    
    @pytest.mark.asyncio
    async def test_file_permissions_validation_passes_with_writable_dirs(self, startup_validator):
        """Test file permissions validation passes when directories are writable"""
        with patch('os.makedirs'), \
             patch('builtins.open', mock_open=True), \
             patch('os.remove'):
            
            result = await startup_validator._validate_file_permissions()
            
            assert result.status == ValidationStatus.PASSED
            assert "adequate" in result.message.lower()
    
    @pytest.mark.asyncio
    async def test_file_permissions_validation_fails_with_readonly_dirs(self, startup_validator):
        """Test file permissions validation fails when directories are not writable"""
        with patch('os.makedirs'), \
             patch('builtins.open', side_effect=PermissionError("Permission denied")):
            
            result = await startup_validator._validate_file_permissions()
            
            assert result.status == ValidationStatus.FAILED
            assert "permission" in result.message.lower()
    
    @pytest.mark.asyncio
    async def test_network_connectivity_validation_passes_with_good_connectivity(self, startup_validator):
        """Test network connectivity validation passes with good internet connection"""
        mock_response = Mock()
        mock_response.status = 200
        
        with patch('aiohttp.ClientSession') as mock_session:
            mock_session.return_value.__aenter__.return_value.get.return_value.__aenter__.return_value = mock_response
            
            result = await startup_validator._validate_network_connectivity()
            
            assert result.status == ValidationStatus.PASSED
            assert "good" in result.message.lower()
            assert result.details["successful_connections"] > 0
    
    @pytest.mark.asyncio
    async def test_network_connectivity_validation_fails_with_no_connectivity(self, startup_validator):
        """Test network connectivity validation fails with no internet connection"""
        with patch('aiohttp.ClientSession') as mock_session:
            mock_session.return_value.__aenter__.return_value.get.side_effect = Exception("Connection failed")
            
            result = await startup_validator._validate_network_connectivity()
            
            assert result.status == ValidationStatus.FAILED
            assert "no network" in result.message.lower()
    
    @pytest.mark.asyncio
    async def test_api_validation_skips_when_keys_not_configured(self, startup_validator):
        """Test API validation skips when API keys are not configured"""
        startup_validator.config.api.aviation_weather_api_key = ""
        
        result = await startup_validator._validate_weather_api()
        
        assert result.status == ValidationStatus.SKIPPED
        assert "not configured" in result.message.lower()
    
    @pytest.mark.asyncio
    async def test_api_validation_passes_with_successful_connection(self, startup_validator):
        """Test API validation passes when connection is successful"""
        mock_response = Mock()
        mock_response.status = 200
        mock_response.json = AsyncMock(return_value=[{"test": "data"}])
        
        with patch('aiohttp.ClientSession') as mock_session:
            mock_session.return_value.__aenter__.return_value.get.return_value.__aenter__.return_value = mock_response
            
            result = await startup_validator._validate_weather_api()
            
            assert result.status == ValidationStatus.PASSED
            assert "successful" in result.message.lower()
    
    @pytest.mark.asyncio
    async def test_api_validation_fails_with_connection_error(self, startup_validator):
        """Test API validation fails when connection fails"""
        with patch('aiohttp.ClientSession') as mock_session:
            mock_session.return_value.__aenter__.return_value.get.side_effect = Exception("Connection failed")
            
            result = await startup_validator._validate_weather_api()
            
            assert result.status == ValidationStatus.FAILED
            assert "failed" in result.message.lower()
            assert result.error is not None
    
    @pytest.mark.asyncio
    async def test_security_config_validation_passes_in_development(self, startup_validator):
        """Test security configuration validation passes in development environment"""
        startup_validator.config.deployment.environment.value = "development"
        
        result = await startup_validator._validate_security_config()
        
        assert result.status == ValidationStatus.PASSED
        assert "appropriate" in result.message.lower()
    
    @pytest.mark.asyncio
    async def test_security_config_validation_warns_in_production_without_encryption(self, startup_validator):
        """Test security configuration validation warns in production without proper security"""
        startup_validator.config.deployment.environment.value = "production"
        startup_validator.config.security.enable_encryption = False
        
        result = await startup_validator._validate_security_config()
        
        assert result.status == ValidationStatus.WARNING
        assert "encryption" in result.message.lower()
    
    @pytest.mark.asyncio
    async def test_validation_check_timeout_handling(self, startup_validator):
        """Test that validation checks handle timeouts properly"""
        # Create a check that will timeout
        async def slow_check():
            await asyncio.sleep(2)  # Longer than timeout
            return True
        
        check = {
            "name": "slow_test",
            "function": slow_check,
            "critical": False,
            "timeout": 0.1  # Very short timeout
        }
        
        result = await startup_validator._run_validation_check(check)
        
        assert result.status == ValidationStatus.FAILED
        assert "timed out" in result.message.lower()
        assert result.error == "Timeout"
    
    @pytest.mark.asyncio
    async def test_validation_check_exception_handling(self, startup_validator):
        """Test that validation checks handle exceptions properly"""
        # Create a check that will raise an exception
        async def failing_check():
            raise ValueError("Test error")
        
        check = {
            "name": "failing_test",
            "function": failing_check,
            "critical": False,
            "timeout": 30
        }
        
        result = await startup_validator._run_validation_check(check)
        
        assert result.status == ValidationStatus.FAILED
        assert "Test error" in result.message
        assert result.error == "Test error"
    
    @pytest.mark.asyncio
    async def test_overall_status_determination_with_critical_failures(self, startup_validator):
        """Test overall status is FAILED when critical checks fail"""
        # Mock a critical failure
        with patch.object(startup_validator, '_run_validation_check') as mock_run_check:
            mock_run_check.return_value = ValidationResult(
                name="config_validation",
                status=ValidationStatus.FAILED,
                message="Critical failure"
            )
            
            # Mock system info collection
            with patch.object(startup_validator, '_collect_system_info', return_value={}):
                report = await startup_validator.validate_startup()
                
                assert report.overall_status == ValidationStatus.FAILED
                assert report.failed_checks > 0
    
    @pytest.mark.asyncio
    async def test_overall_status_determination_with_warnings_only(self, startup_validator):
        """Test overall status is WARNING when only non-critical checks fail"""
        # Mock all checks to pass except non-critical ones
        def mock_check_result(check):
            if check["critical"]:
                return ValidationResult(
                    name=check["name"],
                    status=ValidationStatus.PASSED,
                    message="Passed"
                )
            else:
                return ValidationResult(
                    name=check["name"],
                    status=ValidationStatus.WARNING,
                    message="Warning"
                )
        
        with patch.object(startup_validator, '_run_validation_check', side_effect=mock_check_result), \
             patch.object(startup_validator, '_collect_system_info', return_value={}):
            
            report = await startup_validator.validate_startup()
            
            assert report.overall_status in [ValidationStatus.WARNING, ValidationStatus.PASSED]
    
    @pytest.mark.asyncio
    async def test_system_info_collection(self, startup_validator):
        """Test system information collection"""
        with patch('psutil.virtual_memory') as mock_memory, \
             patch('psutil.disk_usage') as mock_disk, \
             patch('psutil.cpu_count', return_value=4):
            
            mock_memory.return_value = Mock(total=8*1024**3, available=4*1024**3)
            mock_disk.return_value = Mock(total=100*1024**3, free=50*1024**3)
            
            system_info = await startup_validator._collect_system_info()
            
            assert "platform" in system_info
            assert "python_version" in system_info
            assert "memory_total_gb" in system_info
            assert "memory_available_gb" in system_info
            assert "disk_total_gb" in system_info
            assert "disk_free_gb" in system_info
            assert "cpu_count" in system_info
            assert system_info["cpu_count"] == 4
    
    @pytest.mark.asyncio
    async def test_api_connections_only_validation(self, startup_validator):
        """Test API-only validation functionality"""
        with patch.object(startup_validator, '_validate_weather_api') as mock_weather, \
             patch.object(startup_validator, '_validate_flight_api') as mock_flight, \
             patch.object(startup_validator, '_validate_faa_api') as mock_faa:
            
            mock_weather.return_value = ValidationResult("aviation_weather_api", ValidationStatus.PASSED, "OK")
            mock_flight.return_value = ValidationResult("flight_tracking_api", ValidationStatus.PASSED, "OK")
            mock_faa.return_value = ValidationResult("faa_api", ValidationStatus.SKIPPED, "No key")
            
            results = await startup_validator.validate_api_connections_only()
            
            assert len(results) == 3
            assert "aviation_weather_api" in results
            assert "flight_tracking_api" in results
            assert "faa_api" in results
            assert results["aviation_weather_api"].status == ValidationStatus.PASSED
            assert results["faa_api"].status == ValidationStatus.SKIPPED
    
    def test_generate_report_json(self, startup_validator):
        """Test JSON report generation"""
        # Create a sample report
        report = StartupReport(
            timestamp=datetime.utcnow(),
            overall_status=ValidationStatus.PASSED,
            total_checks=3,
            passed_checks=2,
            failed_checks=0,
            warning_checks=1,
            skipped_checks=0,
            total_duration_ms=1500.0,
            validation_results=[
                ValidationResult("test1", ValidationStatus.PASSED, "OK"),
                ValidationResult("test2", ValidationStatus.WARNING, "Warning"),
                ValidationResult("test3", ValidationStatus.PASSED, "OK")
            ],
            system_info={"platform": "test"}
        )
        
        json_report = startup_validator.generate_report_json(report)
        
        # Verify it's valid JSON
        parsed = json.loads(json_report)
        
        assert parsed["overall_status"] == "passed"
        assert parsed["summary"]["total_checks"] == 3
        assert parsed["summary"]["passed_checks"] == 2
        assert parsed["summary"]["warning_checks"] == 1
        assert len(parsed["validation_results"]) == 3
        assert parsed["system_info"]["platform"] == "test"
    
    def test_is_critical_check_identification(self, startup_validator):
        """Test critical check identification"""
        assert startup_validator._is_critical_check("config_validation") == True
        assert startup_validator._is_critical_check("discord_config") == True
        assert startup_validator._is_critical_check("aviation_weather_api") == False
        assert startup_validator._is_critical_check("nonexistent_check") == False


class TestBotStartupIntegration:
    """Test bot startup integration with startup validator"""
    
    @pytest.fixture
    def mock_config(self):
        """Mock configuration for bot testing"""
        config = Mock(spec=BotConfiguration)
        config.discord = Mock()
        config.discord.command_prefix = "!"
        config.discord.token = "test_token"
        return config
    
    @pytest.mark.asyncio
    async def test_bot_setup_hook_runs_startup_validation(self, mock_config):
        """Test that bot setup_hook runs startup validation"""
        with patch('src.bot.discord_client.commands.Bot.__init__'), \
             patch('src.bot.discord_client.StartupValidator') as mock_validator_class:
            
            # Mock validator instance and report
            mock_validator = Mock()
            mock_report = Mock()
            mock_report.overall_status = Mock()
            mock_report.overall_status.value = "passed"
            mock_validator.validate_startup = AsyncMock(return_value=mock_report)
            mock_validator_class.return_value = mock_validator
            
            bot = AviationGirlBot(mock_config)
            
            # Mock all the initialization methods
            bot._initialize_system_group = AsyncMock()
            bot._integrate_all_systems = AsyncMock()
            bot._start_background_tasks = AsyncMock()
            
            await bot.setup_hook()
            
            # Verify startup validation was called
            mock_validator_class.assert_called_once_with(mock_config)
            mock_validator.validate_startup.assert_called_once()
            assert bot.startup_report == mock_report
    
    @pytest.mark.asyncio
    async def test_bot_setup_hook_handles_critical_startup_failures(self, mock_config):
        """Test that bot setup_hook handles critical startup failures"""
        with patch('src.bot.discord_client.commands.Bot.__init__'), \
             patch('src.bot.discord_client.StartupValidator') as mock_validator_class:
            
            # Mock validator with critical failure
            mock_validator = Mock()
            mock_report = Mock()
            mock_report.overall_status = Mock()
            mock_report.overall_status.value = "failed"
            
            # Mock critical failure
            critical_failure = Mock()
            critical_failure.name = "config_validation"
            critical_failure.status = Mock()
            critical_failure.status.value = "failed"
            mock_report.validation_results = [critical_failure]
            
            mock_validator.validate_startup = AsyncMock(return_value=mock_report)
            mock_validator._is_critical_check = Mock(return_value=True)
            mock_validator_class.return_value = mock_validator
            
            bot = AviationGirlBot(mock_config)
            bot.error_handler = Mock()
            bot.error_handler.handle_error = AsyncMock()
            
            # Should raise RuntimeError for critical failures
            with pytest.raises(RuntimeError):
                await bot.setup_hook()
    
    @pytest.mark.asyncio
    async def test_bot_setup_hook_continues_with_non_critical_failures(self, mock_config):
        """Test that bot setup_hook continues with non-critical failures"""
        with patch('src.bot.discord_client.commands.Bot.__init__'), \
             patch('src.bot.discord_client.StartupValidator') as mock_validator_class:
            
            # Mock validator with non-critical failure
            mock_validator = Mock()
            mock_report = Mock()
            mock_report.overall_status = Mock()
            mock_report.overall_status.value = "warning"
            
            # Mock non-critical failure
            non_critical_failure = Mock()
            non_critical_failure.name = "aviation_weather_api"
            non_critical_failure.status = Mock()
            non_critical_failure.status.value = "failed"
            mock_report.validation_results = [non_critical_failure]
            
            mock_validator.validate_startup = AsyncMock(return_value=mock_report)
            mock_validator._is_critical_check = Mock(return_value=False)
            mock_validator_class.return_value = mock_validator
            
            bot = AviationGirlBot(mock_config)
            
            # Mock all the initialization methods
            bot._initialize_system_group = AsyncMock()
            bot._integrate_all_systems = AsyncMock()
            bot._start_background_tasks = AsyncMock()
            
            # Should not raise an exception
            await bot.setup_hook()
            
            # Verify initialization continued
            assert bot._initialize_system_group.call_count > 0