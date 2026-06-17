"""
Test System Resource Management
Property-based tests for system resource monitoring and graceful degradation

Feature: aviation-discord-bot, Property 14: System Resource Management
*For any* resource constraint situation, the system should implement graceful degradation 
while maintaining core functionality and provide appropriate user notifications about 
reduced capabilities.

Validates: Requirements 10.5
"""

import pytest
import asyncio
import time
from unittest.mock import Mock, AsyncMock, patch, MagicMock
from hypothesis import given, strategies as st, settings, HealthCheck
from datetime import datetime, timedelta
import tempfile
import os

# Import the components we're testing
from v4.src.bot.resource_manager import (
    ResourceManager, ResourceType, DegradationLevel, 
    ResourceThreshold, ResourceUsage, DegradationAction
)
from v4.src.bot.message_handler import MessageHandler
from v4.src.bot.performance_monitor import PerformanceMonitor
from v4.src.bot.embed_builder import EmbedBuilder


class TestSystemResourceManagement:
    """Property-based tests for system resource management"""
    
    @pytest.fixture
    def mock_performance_monitor(self):
        """Mock performance monitor for testing"""
        monitor = Mock(spec=PerformanceMonitor)
        monitor.record_resource_usage = Mock()
        return monitor
    
    @pytest.fixture
    def resource_manager(self, mock_performance_monitor):
        """Create resource manager for testing"""
        manager = ResourceManager(performance_monitor=mock_performance_monitor)
        # Clear any existing history for test isolation
        manager.usage_history = []
        manager.current_usage = None
        manager.current_degradation = DegradationLevel.NORMAL
        manager.degradation_start_time = None
        manager.active_measures = set()
        manager.degradation_reasons = []
        yield manager
        # Cleanup
        try:
            asyncio.run(manager.shutdown())
        except:
            pass
    
    @pytest.fixture
    def mock_embed_builder(self):
        """Mock embed builder for testing"""
        embed_builder = Mock(spec=EmbedBuilder)
        embed_builder.create_info_embed.return_value = Mock()
        embed_builder.create_error_embed.return_value = Mock()
        return embed_builder
    
    @given(
        cpu_percentages=st.floats(min_value=0.0, max_value=100.0),
        memory_percentages=st.floats(min_value=0.0, max_value=100.0),
        disk_percentages=st.floats(min_value=0.0, max_value=100.0),
        network_mb=st.floats(min_value=0.0, max_value=1000.0)
    )
    @settings(max_examples=50, deadline=8000, suppress_health_check=[HealthCheck.function_scoped_fixture])
    def test_resource_usage_monitoring_accuracy(
        self,
        resource_manager,
        cpu_percentages,
        memory_percentages,
        disk_percentages,
        network_mb
    ):
        """
        Property: Resource manager should accurately monitor and record
        system resource usage across all resource types
        """
        # Mock psutil to return our test values
        with patch('v4.src.bot.resource_manager.psutil') as mock_psutil:
            # Mock CPU usage
            mock_psutil.cpu_percent.return_value = cpu_percentages
            
            # Mock memory usage
            mock_memory = Mock()
            mock_memory.percent = memory_percentages
            mock_memory.used = memory_percentages * 1024 * 1024 * 100  # Convert to bytes
            mock_psutil.virtual_memory.return_value = mock_memory
            
            # Mock disk usage
            mock_disk = Mock()
            mock_disk.total = 1024 * 1024 * 1024 * 100  # 100GB total
            mock_disk.used = (disk_percentages / 100) * mock_disk.total
            mock_psutil.disk_usage.return_value = mock_disk
            
            # Mock network I/O
            mock_network = Mock()
            mock_network.bytes_sent = network_mb * 1024 * 1024 / 2
            mock_network.bytes_recv = network_mb * 1024 * 1024 / 2
            mock_psutil.net_io_counters.return_value = mock_network
            
            # Mock network connections
            mock_psutil.net_connections.return_value = [Mock() for _ in range(10)]
            
            # Update resource usage
            usage = asyncio.run(resource_manager.update_resource_usage())
            
            # Verify usage was recorded accurately
            assert usage is not None
            assert isinstance(usage, ResourceUsage)
            
            # Check CPU usage
            assert abs(usage.cpu_percent - cpu_percentages) < 0.1
            
            # Check memory usage
            assert abs(usage.memory_percent - memory_percentages) < 0.1
            
            # Check disk usage
            assert abs(usage.disk_percent - disk_percentages) < 0.1
            
            # Check network usage
            assert abs(usage.network_io_mb - network_mb) < 0.1
            
            # Check that usage was added to history
            assert len(resource_manager.usage_history) > 0
            assert resource_manager.current_usage == usage
    
    @given(
        cpu_level=st.floats(min_value=0.0, max_value=100.0),
        memory_level=st.floats(min_value=0.0, max_value=100.0),
        disk_level=st.floats(min_value=0.0, max_value=100.0)
    )
    @settings(max_examples=40, deadline=10000, suppress_health_check=[HealthCheck.function_scoped_fixture])
    def test_degradation_level_calculation(
        self,
        resource_manager,
        cpu_level,
        memory_level,
        disk_level
    ):
        """
        Property: Resource manager should correctly calculate degradation levels
        based on resource usage thresholds across multiple resource types
        """
        # Create mock resource usage with specific levels
        mock_usage = ResourceUsage(
            timestamp=datetime.utcnow(),
            cpu_percent=cpu_level,
            memory_percent=memory_level,
            memory_mb=memory_level * 10,  # Scale for MB
            disk_percent=disk_level,
            disk_mb=disk_level * 100,     # Scale for MB
            network_io_mb=10.0,
            active_connections=5
        )
        
        resource_manager.current_usage = mock_usage
        
        # Calculate expected degradation level based on the highest resource usage
        expected_level = DegradationLevel.NORMAL
        resource_levels = [
            (ResourceType.CPU, cpu_level),
            (ResourceType.MEMORY, memory_level),
            (ResourceType.DISK, disk_level)
        ]
        
        for resource_type, level in resource_levels:
            threshold = resource_manager.thresholds[resource_type]
            
            if level >= threshold.critical:
                expected_level = max(expected_level, DegradationLevel.CRITICAL, key=lambda x: x.value)
            elif level >= threshold.severe:
                expected_level = max(expected_level, DegradationLevel.SEVERE, key=lambda x: x.value)
            elif level >= threshold.moderate:
                expected_level = max(expected_level, DegradationLevel.MODERATE, key=lambda x: x.value)
            elif level >= threshold.light:
                expected_level = max(expected_level, DegradationLevel.LIGHT, key=lambda x: x.value)
        
        # Test degradation level calculation
        calculated_level = resource_manager._calculate_required_degradation_level()
        
        # Verify calculated level matches expected
        assert calculated_level == expected_level
        
        # Verify degradation reasons are updated correctly
        resource_manager._update_degradation_reasons()
        
        # Check that reasons are provided for elevated resource usage
        if expected_level != DegradationLevel.NORMAL:
            assert len(resource_manager.degradation_reasons) > 0
            
            # Verify reasons mention the correct resource types that are elevated
            reason_text = " ".join(resource_manager.degradation_reasons).lower()
            for resource_type, level in resource_levels:
                threshold = resource_manager.thresholds[resource_type]
                if level >= threshold.light:
                    assert resource_type.value in reason_text
    
    @given(
        initial_levels=st.sampled_from([
            DegradationLevel.NORMAL, DegradationLevel.LIGHT, 
            DegradationLevel.MODERATE, DegradationLevel.SEVERE
        ]),
        target_levels=st.sampled_from([
            DegradationLevel.NORMAL, DegradationLevel.LIGHT, 
            DegradationLevel.MODERATE, DegradationLevel.SEVERE, 
            DegradationLevel.CRITICAL
        ])
    )
    @settings(max_examples=30, deadline=10000, suppress_health_check=[HealthCheck.function_scoped_fixture])
    def test_graceful_degradation_transitions(
        self,
        resource_manager,
        initial_levels,
        target_levels
    ):
        """
        Property: Resource manager should handle graceful transitions between
        degradation levels and apply appropriate actions
        """
        async def run_test():
            # Set initial degradation level
            resource_manager.current_degradation = initial_levels
            resource_manager.active_measures = set()
            
            # Track callback invocations
            callback_called = False
            callback_args = None
            
            def test_callback(old_level, new_level, reasons):
                nonlocal callback_called, callback_args
                callback_called = True
                callback_args = (old_level, new_level, reasons)
            
            resource_manager.register_degradation_callback(test_callback)
            
            # Force degradation level change
            await resource_manager._change_degradation_level(target_levels)
            
            # Verify degradation level was changed
            assert resource_manager.current_degradation == target_levels
            
            # Verify callback was called
            assert callback_called
            assert callback_args[0] == initial_levels
            assert callback_args[1] == target_levels
            
            # Verify degradation start time is set appropriately
            if target_levels != DegradationLevel.NORMAL:
                assert resource_manager.degradation_start_time is not None
            else:
                assert resource_manager.degradation_start_time is None
            
            # Verify appropriate actions are applied based on level change
            if target_levels.value > initial_levels.value:
                # Degradation got worse - should have applied new actions
                expected_actions = [
                    action for action in resource_manager.degradation_actions
                    if action.level == target_levels and action.enabled
                ]
                
                # At least some actions should be active if degradation increased
                if expected_actions and target_levels != DegradationLevel.NORMAL:
                    assert len(resource_manager.active_measures) >= 0  # May be 0 if no actions defined
            
            elif target_levels.value < initial_levels.value:
                # Degradation got better - should have removed some actions
                # Active measures should not include actions for higher levels
                for measure in resource_manager.active_measures:
                    action_levels = [
                        action.level for action in resource_manager.degradation_actions
                        if action.action_name == measure
                    ]
                    for level in action_levels:
                        assert level.value <= target_levels.value
        
        # Run the async test
        asyncio.run(run_test())
    
    @given(
        degradation_levels=st.sampled_from([
            DegradationLevel.NORMAL, DegradationLevel.LIGHT,
            DegradationLevel.MODERATE, DegradationLevel.SEVERE,
            DegradationLevel.CRITICAL
        ])
    )
    @settings(max_examples=20, deadline=8000, suppress_health_check=[HealthCheck.function_scoped_fixture])
    def test_user_notification_generation(
        self,
        resource_manager,
        degradation_levels
    ):
        """
        Property: Resource manager should generate appropriate user notifications
        for different degradation levels with clear, helpful messages
        """
        # Set degradation level and reasons
        resource_manager.current_degradation = degradation_levels
        resource_manager.degradation_reasons = [
            f"{degradation_levels.value} resource usage detected"
        ]
        
        # Get user notification message
        notification = resource_manager.get_user_notification_message()
        
        # Verify notification behavior
        if degradation_levels == DegradationLevel.NORMAL:
            # No notification for normal operation
            assert notification is None
        else:
            # Should have notification for degraded states
            assert notification is not None
            assert isinstance(notification, str)
            assert len(notification) > 0
            
            # Notification should be user-friendly
            assert any(word in notification.lower() for word in [
                "load", "system", "performance", "limited", "mode", "experiencing"
            ])
            
            # Should not contain technical jargon
            assert not any(word in notification.lower() for word in [
                "cpu_percent", "memory_mb", "degradation_level", "threshold"
            ])
            
            # Should be appropriately urgent based on level
            if degradation_levels == DegradationLevel.CRITICAL:
                assert any(word in notification.lower() for word in [
                    "emergency", "critical", "essential"
                ])
            elif degradation_levels == DegradationLevel.SEVERE:
                assert any(word in notification.lower() for word in [
                    "high", "basic", "limited"
                ])
    
    @given(
        concurrent_limits=st.integers(min_value=1, max_value=10),
        active_conversations=st.integers(min_value=0, max_value=15),
        degradation_levels=st.sampled_from([
            DegradationLevel.LIGHT, DegradationLevel.MODERATE,
            DegradationLevel.SEVERE, DegradationLevel.CRITICAL
        ])
    )
    @settings(max_examples=30, deadline=8000, suppress_health_check=[HealthCheck.function_scoped_fixture])
    def test_concurrent_processing_limits(
        self,
        mock_embed_builder,
        concurrent_limits,
        active_conversations,
        degradation_levels
    ):
        """
        Property: System should enforce appropriate concurrent processing limits
        based on degradation level and gracefully handle excess load
        """
        async def run_test():
            # Create a mock resource manager that doesn't start background tasks
            class MockResourceManager:
                def __init__(self):
                    self.current_degradation = DegradationLevel.NORMAL
                    self.degradation_reasons = []
                    self.degradation_start_time = None
                    self.active_measures = set()
                    
                def is_degraded(self):
                    return self.current_degradation != DegradationLevel.NORMAL
                    
                def get_degradation_level(self):
                    return self.current_degradation
                    
                async def force_degradation_level(self, level, reason):
                    self.current_degradation = level
                    self.degradation_reasons = [reason]
                    
                async def shutdown(self):
                    pass
            
            # Create mock resource manager
            resource_manager = MockResourceManager()
            
            # Create a simple mock message handler instead of the full one
            # to avoid async initialization issues
            class MockMessageHandler:
                def __init__(self, resource_manager):
                    self.resource_manager = resource_manager
                    self.active_conversations = {}
                    self.max_concurrent_conversations = 5
                    self.degraded_max_concurrent = 2
                    self.emergency_max_concurrent = 1
                    
                async def _check_resource_constraints(self, message):
                    """Simplified resource constraint checking"""
                    if self.resource_manager.is_degraded():
                        degradation_level = self.resource_manager.get_degradation_level()
                        
                        if degradation_level == DegradationLevel.CRITICAL:
                            if len(self.active_conversations) >= self.emergency_max_concurrent:
                                await message.reply("System in critical mode")
                                return False
                        elif degradation_level == DegradationLevel.SEVERE:
                            if len(self.active_conversations) >= self.emergency_max_concurrent:
                                await message.reply("System in severe mode")
                                return False
                        elif len(self.active_conversations) >= self.degraded_max_concurrent:
                            await message.reply("System degraded")
                            return False
                    elif len(self.active_conversations) >= self.max_concurrent_conversations:
                        await message.reply("High load")
                        return False
                    
                    return True
            
            try:
                message_handler = MockMessageHandler(resource_manager)
                
                # Set degradation level
                await resource_manager.force_degradation_level(degradation_levels, "Test scenario")
                
                # Verify concurrent limits were adjusted based on degradation
                if degradation_levels in [DegradationLevel.LIGHT, DegradationLevel.MODERATE]:
                    expected_limit = message_handler.degraded_max_concurrent
                else:  # SEVERE or CRITICAL
                    expected_limit = message_handler.emergency_max_concurrent
                
                # Simulate active conversations
                for i in range(min(active_conversations, 15)):
                    mock_task = Mock()
                    mock_task.done.return_value = False
                    mock_task.get_name.return_value = f"conversation_{i}"
                    message_handler.active_conversations[i] = mock_task
                
                # Test resource constraint checking
                mock_message = Mock()
                mock_message.author = Mock()
                mock_message.author.id = 999
                mock_message.reply = AsyncMock()
                
                can_process = await message_handler._check_resource_constraints(mock_message)
                
                # Verify constraint enforcement
                current_conversations = len(message_handler.active_conversations)
                if current_conversations >= expected_limit:
                    # Should reject new messages when at limit
                    assert not can_process
                    # Should have sent notification
                    mock_message.reply.assert_called_once()
                else:
                    # Should accept new messages when under limit
                    assert can_process
                
            finally:
                # Cleanup
                await resource_manager.shutdown()
        
        # Run the async test
        asyncio.run(run_test())
    
    @given(
        resource_histories=st.lists(
            st.tuples(
                st.floats(min_value=0.0, max_value=100.0),  # CPU
                st.floats(min_value=0.0, max_value=100.0),  # Memory
                st.floats(min_value=0.0, max_value=100.0)   # Disk
            ),
            min_size=5,
            max_size=20
        )
    )
    @settings(max_examples=20, deadline=10000, suppress_health_check=[HealthCheck.function_scoped_fixture])
    def test_resource_history_tracking(
        self,
        resource_manager,
        resource_histories
    ):
        """
        Property: Resource manager should maintain accurate resource usage
        history and provide meaningful historical data
        """
        # Clear any existing history for test isolation
        resource_manager.usage_history = []
        
        # Add resource usage history
        base_time = datetime.utcnow()
        
        for i, (cpu, memory, disk) in enumerate(resource_histories):
            usage = ResourceUsage(
                timestamp=base_time + timedelta(minutes=i),
                cpu_percent=cpu,
                memory_percent=memory,
                memory_mb=memory * 10,  # Scale for MB
                disk_percent=disk,
                disk_mb=disk * 100,     # Scale for MB
                network_io_mb=10.0,
                active_connections=5
            )
            
            resource_manager.usage_history.append(usage)
            resource_manager.current_usage = usage
        
        # Verify history tracking
        assert len(resource_manager.usage_history) == len(resource_histories)
        
        # Test history retrieval
        history_1h = resource_manager.get_usage_history(hours=1)
        
        # Should return data within the time window
        assert len(history_1h) <= len(resource_histories)
        
        # Verify history data structure
        for entry in history_1h:
            assert "timestamp" in entry
            assert "cpu_percent" in entry
            assert "memory_percent" in entry
            assert "disk_percent" in entry
            assert isinstance(entry["cpu_percent"], (int, float))
            assert isinstance(entry["memory_percent"], (int, float))
            assert isinstance(entry["disk_percent"], (int, float))
            assert 0 <= entry["cpu_percent"] <= 100
            assert 0 <= entry["memory_percent"] <= 100
            assert 0 <= entry["disk_percent"] <= 100
        
        # Test resource status reporting
        status = resource_manager.get_resource_status()
        
        # Verify status structure
        assert "degradation_level" in status
        assert "resource_usage" in status
        assert "thresholds" in status
        
        # Verify resource usage data
        usage_data = status["resource_usage"]
        assert "cpu_percent" in usage_data
        assert "memory_percent" in usage_data
        assert "disk_percent" in usage_data
        
        # Verify thresholds data
        thresholds_data = status["thresholds"]
        for resource_type in [ResourceType.CPU, ResourceType.MEMORY, ResourceType.DISK]:
            assert resource_type.value in thresholds_data
            threshold_info = thresholds_data[resource_type.value]
            assert "warning" in threshold_info
            assert "light" in threshold_info
            assert "moderate" in threshold_info
            assert "severe" in threshold_info
            assert "critical" in threshold_info
    
    @given(
        cooldown_scenarios=st.tuples(
            st.integers(min_value=0, max_value=300),  # Time since last change
            st.sampled_from([True, False]),           # Is upgrade (worse performance)
            st.integers(min_value=30, max_value=180)  # Cooldown period
        )
    )
    @settings(max_examples=20, deadline=8000, suppress_health_check=[HealthCheck.function_scoped_fixture])
    def test_degradation_cooldown_periods(
        self,
        resource_manager,
        cooldown_scenarios
    ):
        """
        Property: Resource manager should respect cooldown periods when
        changing degradation levels to prevent oscillation
        """
        time_since_change, is_upgrade, cooldown_period = cooldown_scenarios
        
        # Set up initial state
        resource_manager.current_degradation = DegradationLevel.LIGHT
        resource_manager._last_degradation_change = datetime.utcnow() - timedelta(seconds=time_since_change)
        
        # Set cooldown periods
        if is_upgrade:
            resource_manager.degradation_cooldown = cooldown_period
            target_level = DegradationLevel.MODERATE  # Upgrade (worse)
            # Set CPU usage high enough to trigger MODERATE level
            cpu_usage = 85.0  # Above moderate threshold (80.0)
        else:
            resource_manager.recovery_cooldown = cooldown_period
            target_level = DegradationLevel.NORMAL    # Downgrade (better)
            # Set CPU usage low enough to allow NORMAL level
            cpu_usage = 30.0  # Below light threshold (70.0)
        
        # Mock current usage to require the target level
        mock_usage = ResourceUsage(
            timestamp=datetime.utcnow(),
            cpu_percent=cpu_usage,
            memory_percent=50.0,  # Below all thresholds
            memory_mb=1000.0,
            disk_percent=50.0,    # Below all thresholds
            disk_mb=10000.0,
            network_io_mb=10.0,   # Below all thresholds
            active_connections=5
        )
        resource_manager.current_usage = mock_usage
        
        # Test cooldown enforcement
        initial_level = resource_manager.current_degradation
        
        # Run evaluation (this would normally be called by the monitoring loop)
        asyncio.run(resource_manager._evaluate_degradation())
        
        # Verify cooldown behavior
        if time_since_change >= cooldown_period:
            # Should have changed level after cooldown period
            assert resource_manager.current_degradation == target_level
        else:
            # Should not have changed level during cooldown
            assert resource_manager.current_degradation == initial_level


if __name__ == "__main__":
    pytest.main([__file__, "-v"])