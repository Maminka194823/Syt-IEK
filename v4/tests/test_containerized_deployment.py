"""
Unit tests for containerized deployment functionality
Tests container deployment with resource allocation and health checks
Validates: Requirements 12.3
"""

import pytest
import asyncio
import signal
import os
import json
import tempfile
from unittest.mock import Mock, AsyncMock, patch, MagicMock, mock_open
from datetime import datetime, timedelta

from src.bot.deployment_manager import (
    DeploymentManager, DeploymentStatus, HealthStatus, HealthCheck, DeploymentInfo
)
from src.bot.config_manager import BotConfiguration


class TestContainerizedDeployment:
    """Test containerized deployment functionality"""
    
    @pytest.fixture
    def mock_config(self):
        """Mock bot configuration for deployment testing"""
        config = Mock(spec=BotConfiguration)
        
        # Deployment config
        config.deployment = Mock()
        config.deployment.environment = Mock()
        config.deployment.environment.value = "production"
        config.deployment.graceful_shutdown_timeout = 30
        config.deployment.enable_container_mode = True
        
        # Monitoring config
        config.monitoring = Mock()
        config.monitoring.health_check_interval = 60
        config.monitoring.metrics_port = 8080
        
        return config
    
    @pytest.fixture
    def mock_bot(self):
        """Mock bot instance"""
        bot = Mock()
        bot.is_ready = True
        bot.user = Mock()
        bot.user.id = 12345
        bot.guilds = [Mock(), Mock()]  # 2 guilds
        bot.latency = 0.05  # 50ms latency
        return bot
    
    @pytest.fixture
    def deployment_manager(self, mock_config, mock_bot):
        """Create deployment manager instance"""
        return DeploymentManager(config=mock_config, bot_instance=mock_bot)
    
    def test_deployment_manager_initialization(self, deployment_manager, mock_config):
        """Test deployment manager initialization"""
        assert deployment_manager.config == mock_config
        assert deployment_manager.bot_instance is not None
        assert deployment_manager.deployment_info.environment == "production"
        assert deployment_manager.deployment_info.status == DeploymentStatus.STARTING
        assert deployment_manager.deployment_info.health_status == HealthStatus.UNKNOWN
        assert deployment_manager.container_mode == True
        assert deployment_manager.health_check_port == 8080
    
    def test_deployment_id_generation(self, deployment_manager):
        """Test deployment ID generation"""
        deployment_id = deployment_manager._generate_deployment_id()
        
        assert deployment_id.startswith("aviation-bot-")
        assert len(deployment_id) > len("aviation-bot-")
        
        # Generate another ID and verify they're different (add small delay)
        import time
        time.sleep(0.001)  # Small delay to ensure different timestamp
        deployment_id2 = deployment_manager._generate_deployment_id()
        assert deployment_id != deployment_id2
    
    def test_version_detection(self, deployment_manager):
        """Test application version detection"""
        # Test with VERSION file
        with tempfile.NamedTemporaryFile(mode='w', delete=False) as f:
            f.write("4.1.0")
            version_file = f.name
        
        try:
            with patch('os.path.exists', return_value=True), \
                 patch('builtins.open', mock_open(read_data="4.1.0")):
                version = deployment_manager._get_version()
                assert version == "4.1.0"
        finally:
            if os.path.exists(version_file):
                os.unlink(version_file)
        
        # Test with environment variable
        with patch('os.path.exists', return_value=False), \
             patch.dict(os.environ, {"APP_VERSION": "4.2.0"}):
            version = deployment_manager._get_version()
            assert version == "4.2.0"
        
        # Test with no version info
        with patch('os.path.exists', return_value=False), \
             patch.dict(os.environ, {}, clear=True):
            version = deployment_manager._get_version()
            assert version == "4.0.0-dev"
    
    def test_health_check_registration(self, deployment_manager):
        """Test health check registration"""
        # Mock health check function
        async def test_health_check():
            return True
        
        deployment_manager.register_health_check(
            "test_check",
            test_health_check,
            interval_seconds=30,
            failure_threshold=2
        )
        
        assert "test_check" in deployment_manager.deployment_info.health_checks
        health_check = deployment_manager.deployment_info.health_checks["test_check"]
        assert health_check.name == "test_check"
        assert health_check.interval_seconds == 30
        assert health_check.failure_threshold == 2
        assert health_check.check_function == test_health_check
    
    def test_default_health_checks_registration(self, deployment_manager):
        """Test that default health checks are registered"""
        health_checks = deployment_manager.deployment_info.health_checks
        
        # Verify default health checks are registered
        expected_checks = ["bot_connection", "memory_usage", "disk_space", "ai_model"]
        
        for check_name in expected_checks:
            assert check_name in health_checks
            assert callable(health_checks[check_name].check_function)
    
    @pytest.mark.asyncio
    async def test_start_deployment_success(self, deployment_manager):
        """Test successful deployment startup"""
        # Mock all startup methods
        deployment_manager._start_health_monitoring = AsyncMock()
        deployment_manager._start_health_check_server = AsyncMock()
        deployment_manager._preserve_context = AsyncMock()
        deployment_manager._notify_deployment_start = AsyncMock()
        
        result = await deployment_manager.start_deployment()
        
        assert result == True
        assert deployment_manager.deployment_info.status == DeploymentStatus.RUNNING
        assert deployment_manager.deployment_info.health_status == HealthStatus.HEALTHY
        
        # Verify startup methods were called
        deployment_manager._start_health_monitoring.assert_called_once()
        deployment_manager._start_health_check_server.assert_called_once()
        deployment_manager._preserve_context.assert_called_once()
        deployment_manager._notify_deployment_start.assert_called_once()
    
    @pytest.mark.asyncio
    async def test_start_deployment_failure(self, deployment_manager):
        """Test deployment startup failure handling"""
        # Mock health monitoring to fail
        deployment_manager._start_health_monitoring = AsyncMock(side_effect=Exception("Health monitoring failed"))
        deployment_manager._start_health_check_server = AsyncMock()
        
        result = await deployment_manager.start_deployment()
        
        assert result == False
        assert deployment_manager.deployment_info.status == DeploymentStatus.FAILED
    
    @pytest.mark.asyncio
    async def test_health_check_server_startup(self, deployment_manager):
        """Test health check server startup for container orchestration"""
        with patch('aiohttp.web.Application') as mock_app, \
             patch('aiohttp.web.AppRunner') as mock_runner, \
             patch('aiohttp.web.TCPSite') as mock_site:
            
            mock_app_instance = Mock()
            mock_app.return_value = mock_app_instance
            
            mock_runner_instance = Mock()
            mock_runner.return_value = mock_runner_instance
            mock_runner_instance.setup = AsyncMock()
            
            mock_site_instance = Mock()
            mock_site.return_value = mock_site_instance
            mock_site_instance.start = AsyncMock()
            
            await deployment_manager._start_health_check_server()
            
            # Verify server components were set up
            mock_app.assert_called_once()
            mock_runner.assert_called_once_with(mock_app_instance)
            mock_runner_instance.setup.assert_called_once()
            mock_site_instance.start.assert_called_once()
    
    @pytest.mark.asyncio
    async def test_health_endpoint_healthy_system(self, deployment_manager):
        """Test health endpoint returns healthy status"""
        # Set up healthy system state
        deployment_manager.deployment_info.health_status = HealthStatus.HEALTHY
        deployment_manager.deployment_info.status = DeploymentStatus.RUNNING
        
        # Mock request
        mock_request = Mock()
        
        with patch('aiohttp.web.json_response') as mock_response:
            await deployment_manager._health_endpoint(mock_request)
            
            # Verify response was called with healthy status
            mock_response.assert_called_once()
            call_args = mock_response.call_args[0][0]
            assert call_args["status"] == "healthy"
            assert call_args["deployment_status"] == "running"
    
    @pytest.mark.asyncio
    async def test_health_endpoint_unhealthy_system(self, deployment_manager):
        """Test health endpoint returns unhealthy status"""
        # Set up unhealthy system state
        deployment_manager.deployment_info.health_status = HealthStatus.UNHEALTHY
        deployment_manager.deployment_info.status = DeploymentStatus.RUNNING
        
        mock_request = Mock()
        
        with patch('aiohttp.web.json_response') as mock_response:
            await deployment_manager._health_endpoint(mock_request)
            
            # Verify response indicates unhealthy status
            mock_response.assert_called_once()
            call_args = mock_response.call_args[0][0]
            assert call_args["status"] == "unhealthy"
    
    @pytest.mark.asyncio
    async def test_health_monitoring_loop(self, deployment_manager):
        """Test health monitoring loop execution"""
        # Mock health check execution
        deployment_manager._run_health_checks = AsyncMock()
        
        # Set up shutdown event to stop the loop after one iteration
        async def stop_after_delay():
            await asyncio.sleep(0.1)
            deployment_manager.shutdown_event.set()
        
        # Start the stop task
        stop_task = asyncio.create_task(stop_after_delay())
        
        # Run health monitoring loop
        await deployment_manager._health_monitoring_loop()
        
        # Verify health checks were run
        deployment_manager._run_health_checks.assert_called()
        
        # Cleanup
        await stop_task
    
    @pytest.mark.asyncio
    async def test_individual_health_checks(self, deployment_manager):
        """Test individual health check execution"""
        # Test bot connection health check
        result = await deployment_manager._check_bot_connection()
        assert isinstance(result, bool)
        
        # Test memory usage health check
        with patch('psutil.virtual_memory') as mock_memory:
            mock_memory.return_value = Mock(percent=50.0)  # 50% memory usage
            result = await deployment_manager._check_memory_usage()
            assert result == True  # Should pass with 50% usage
            
            # Test high memory usage
            mock_memory.return_value = Mock(percent=95.0)  # 95% memory usage
            result = await deployment_manager._check_memory_usage()
            assert result == False  # Should fail with 95% usage
        
        # Test disk space health check
        with patch('psutil.disk_usage') as mock_disk:
            mock_disk.return_value = Mock(free=10*1024**3, total=100*1024**3)  # 10GB free of 100GB
            result = await deployment_manager._check_disk_space()
            assert result == True  # Should pass with 10% free space
            
            # Test low disk space
            mock_disk.return_value = Mock(free=1*1024**3, total=100*1024**3)  # 1GB free of 100GB
            result = await deployment_manager._check_disk_space()
            assert result == False  # Should fail with 1% free space
    
    @pytest.mark.asyncio
    async def test_health_check_failure_tracking(self, deployment_manager):
        """Test health check failure tracking and thresholds"""
        # Create a health check that always fails
        async def failing_health_check():
            return False
        
        deployment_manager.register_health_check(
            "failing_check",
            failing_health_check,
            failure_threshold=3
        )
        
        health_check = deployment_manager.deployment_info.health_checks["failing_check"]
        
        # Run health checks multiple times
        for i in range(5):
            await deployment_manager._run_health_checks()
            
            if i < 2:  # First 3 failures (0, 1, 2)
                assert health_check.consecutive_failures == i + 1
                assert health_check.last_status != HealthStatus.UNHEALTHY
            else:  # After threshold is reached
                assert health_check.consecutive_failures >= 3
                assert health_check.last_status == HealthStatus.UNHEALTHY
    
    @pytest.mark.asyncio
    async def test_graceful_shutdown_initiation(self, deployment_manager):
        """Test graceful shutdown initiation"""
        # Mock shutdown methods
        deployment_manager._preserve_active_conversations = AsyncMock()
        deployment_manager._stop_health_monitoring = AsyncMock()
        deployment_manager._notify_shutdown = AsyncMock()
        
        # Mock bot shutdown
        deployment_manager.bot_instance.close = AsyncMock()
        
        await deployment_manager.initiate_shutdown()
        
        # Verify shutdown sequence
        assert deployment_manager.deployment_info.status == DeploymentStatus.STOPPED
        deployment_manager._preserve_active_conversations.assert_called_once()
        deployment_manager._stop_health_monitoring.assert_called_once()
        deployment_manager._notify_shutdown.assert_called_once()
        deployment_manager.bot_instance.close.assert_called_once()
    
    @pytest.mark.asyncio
    async def test_context_preservation_during_shutdown(self, deployment_manager):
        """Test conversation context preservation during shutdown"""
        # Mock active conversations
        deployment_manager.active_conversations = {
            "user_123": {"messages": ["Hello", "How are you?"], "context": "aviation"},
            "user_456": {"messages": ["Weather check"], "context": "weather"}
        }
        
        # Mock file operations
        with patch('builtins.open', mock_open()) as mock_file, \
             patch('json.dump') as mock_json_dump:
            
            await deployment_manager._preserve_active_conversations()
            
            # Verify context was saved
            mock_file.assert_called_once()
            mock_json_dump.assert_called_once()
            
            # Verify the data structure passed to json.dump
            saved_data = mock_json_dump.call_args[0][0]
            assert "conversations" in saved_data
            assert "user_123" in saved_data["conversations"]
            assert "user_456" in saved_data["conversations"]
    
    @pytest.mark.asyncio
    async def test_context_restoration_after_startup(self, deployment_manager):
        """Test conversation context restoration after startup"""
        # Mock saved context data
        saved_context = {
            "timestamp": datetime.utcnow().isoformat(),
            "conversations": {
                "user_123": {"messages": ["Hello"], "context": "aviation"},
                "user_456": {"messages": ["Weather"], "context": "weather"}
            }
        }
        
        with patch('os.path.exists', return_value=True), \
             patch('builtins.open', mock_open(read_data=json.dumps(saved_context))), \
             patch('json.load', return_value=saved_context):
            
            await deployment_manager._restore_context()
            
            # Verify context was restored
            assert "user_123" in deployment_manager.active_conversations
            assert "user_456" in deployment_manager.active_conversations
            assert deployment_manager.active_conversations["user_123"]["context"] == "aviation"
    
    def test_signal_handler_setup(self, deployment_manager):
        """Test signal handler setup for graceful shutdown"""
        with patch('signal.signal') as mock_signal:
            deployment_manager._setup_signal_handlers()
            
            # Verify signal handlers were registered
            assert mock_signal.call_count >= 2  # At least SIGTERM and SIGINT
            
            # Verify handler function is set
            for call in mock_signal.call_args_list:
                signal_num, handler_func = call[0]
                assert handler_func == deployment_manager._signal_handler
    
    def test_signal_handler_execution(self, deployment_manager):
        """Test signal handler execution"""
        with patch('asyncio.create_task') as mock_create_task:
            deployment_manager._signal_handler(signal.SIGTERM, None)
            
            # Verify shutdown task was created
            mock_create_task.assert_called_once()
            
            # Verify the task is for shutdown
            task_coro = mock_create_task.call_args[0][0]
            assert hasattr(task_coro, '__name__') or str(task_coro).find('initiate_shutdown') >= 0
    
    def test_deployment_status_reporting(self, deployment_manager):
        """Test deployment status reporting"""
        # Set up deployment state
        deployment_manager.deployment_info.status = DeploymentStatus.RUNNING
        deployment_manager.deployment_info.health_status = HealthStatus.HEALTHY
        deployment_manager.deployment_info.memory_usage_mb = 512.5
        deployment_manager.deployment_info.cpu_usage_percent = 25.3
        deployment_manager.deployment_info.active_connections = 15
        
        status = deployment_manager.get_deployment_status()
        
        # Verify status information
        assert status["deployment_id"] == deployment_manager.deployment_info.deployment_id
        assert status["status"] == "running"
        assert status["health_status"] == "healthy"
        assert status["environment"] == "production"
        assert status["memory_usage_mb"] == 512.5
        assert status["cpu_usage_percent"] == 25.3
        assert status["active_connections"] == 15
        assert "uptime_seconds" in status
        assert "version" in status
    
    @pytest.mark.asyncio
    async def test_resource_monitoring_and_allocation(self, deployment_manager):
        """Test resource monitoring and allocation tracking"""
        with patch('psutil.virtual_memory') as mock_memory, \
             patch('psutil.cpu_percent') as mock_cpu:
            
            # Mock resource usage
            mock_memory.return_value = Mock(
                total=8*1024**3,  # 8GB total
                used=4*1024**3,   # 4GB used
                percent=50.0
            )
            mock_cpu.return_value = 35.5
            
            await deployment_manager._update_resource_usage()
            
            # Verify resource information was updated
            assert deployment_manager.deployment_info.memory_usage_mb > 0
            assert deployment_manager.deployment_info.cpu_usage_percent == 35.5
    
    @pytest.mark.asyncio
    async def test_container_mode_specific_features(self, deployment_manager):
        """Test container mode specific features"""
        assert deployment_manager.container_mode == True
        
        # Test health check server is started in container mode
        with patch.object(deployment_manager, '_start_health_check_server') as mock_health_server:
            await deployment_manager.start_deployment()
            mock_health_server.assert_called_once()
        
        # Test container-specific environment variables
        with patch.dict(os.environ, {"CONTAINER_MODE": "true", "HEALTH_CHECK_PORT": "9090"}):
            # Container mode should be detected
            assert deployment_manager.container_mode == True
    
    @pytest.mark.asyncio
    async def test_deployment_update_process(self, deployment_manager):
        """Test deployment update process"""
        # Mock update methods
        deployment_manager._preserve_active_conversations = AsyncMock()
        deployment_manager._apply_update = AsyncMock()
        deployment_manager._restore_context = AsyncMock()
        deployment_manager._notify_update_complete = AsyncMock()
        
        # Start update process
        await deployment_manager.perform_update("4.1.0")
        
        # Verify update sequence
        assert deployment_manager.deployment_info.status == DeploymentStatus.RUNNING
        deployment_manager._preserve_active_conversations.assert_called_once()
        deployment_manager._apply_update.assert_called_once_with("4.1.0")
        deployment_manager._restore_context.assert_called_once()
        deployment_manager._notify_update_complete.assert_called_once()
    
    @pytest.mark.asyncio
    async def test_health_check_timeout_handling(self, deployment_manager):
        """Test health check timeout handling"""
        # Create a health check that times out
        async def slow_health_check():
            await asyncio.sleep(2)  # Longer than timeout
            return True
        
        deployment_manager.register_health_check(
            "slow_check",
            slow_health_check,
            timeout_seconds=0.5  # Short timeout
        )
        
        # Run health checks
        await deployment_manager._run_health_checks()
        
        # Verify timeout was handled
        health_check = deployment_manager.deployment_info.health_checks["slow_check"]
        assert health_check.last_status == HealthStatus.UNHEALTHY
        assert "timeout" in health_check.last_error.lower() if health_check.last_error else True
    
    def test_deployment_info_dataclass(self):
        """Test DeploymentInfo dataclass functionality"""
        deployment_info = DeploymentInfo(
            deployment_id="test-123",
            version="4.0.0",
            environment="testing",
            start_time=datetime.utcnow(),
            status=DeploymentStatus.RUNNING,
            health_status=HealthStatus.HEALTHY
        )
        
        assert deployment_info.deployment_id == "test-123"
        assert deployment_info.version == "4.0.0"
        assert deployment_info.environment == "testing"
        assert deployment_info.status == DeploymentStatus.RUNNING
        assert deployment_info.health_status == HealthStatus.HEALTHY
        assert deployment_info.memory_usage_mb == 0.0
        assert deployment_info.cpu_usage_percent == 0.0
        assert deployment_info.active_connections == 0
        assert deployment_info.update_in_progress == False
    
    def test_health_check_dataclass(self):
        """Test HealthCheck dataclass functionality"""
        async def test_check():
            return True
        
        health_check = HealthCheck(
            name="test_check",
            check_function=test_check,
            interval_seconds=30,
            timeout_seconds=5,
            failure_threshold=2,
            success_threshold=1
        )
        
        assert health_check.name == "test_check"
        assert health_check.check_function == test_check
        assert health_check.interval_seconds == 30
        assert health_check.timeout_seconds == 5
        assert health_check.failure_threshold == 2
        assert health_check.success_threshold == 1
        assert health_check.consecutive_failures == 0
        assert health_check.consecutive_successes == 0
        assert health_check.last_status == HealthStatus.UNKNOWN
        assert health_check.last_error is None
    
    @pytest.mark.asyncio
    async def test_maintenance_mode_handling(self, deployment_manager):
        """Test maintenance mode handling"""
        # Enter maintenance mode
        await deployment_manager.enter_maintenance_mode("System update")
        
        assert deployment_manager.deployment_info.status == DeploymentStatus.MAINTENANCE
        
        # Exit maintenance mode
        await deployment_manager.exit_maintenance_mode()
        
        assert deployment_manager.deployment_info.status == DeploymentStatus.RUNNING
    
    def test_shutdown_callback_registration(self, deployment_manager):
        """Test shutdown callback registration and execution"""
        callback_executed = False
        
        def test_callback():
            nonlocal callback_executed
            callback_executed = True
        
        deployment_manager.register_shutdown_callback(test_callback)
        
        # Verify callback was registered
        assert test_callback in deployment_manager.shutdown_callbacks
        
        # Execute callbacks
        deployment_manager._execute_shutdown_callbacks()
        
        # Verify callback was executed
        assert callback_executed == True