"""
Unit tests for system status reporting functionality
Tests health information reporting for all components
Validates: Requirements 10.3
"""

import pytest
from unittest.mock import Mock, AsyncMock, patch
from datetime import datetime, timedelta
from collections import deque

from src.bot.performance_monitor import PerformanceMonitor, SystemHealthSnapshot, MetricType, PerformanceMetric
from src.bot.discord_client import AviationGirlBot
from src.bot.config_manager import BotConfiguration


class TestSystemStatusReporting:
    """Test system status reporting and health information display"""
    
    @pytest.fixture
    def performance_monitor(self):
        """Create performance monitor instance"""
        return PerformanceMonitor(data_dir="test_data")
    
    @pytest.fixture
    def mock_config(self):
        """Mock bot configuration"""
        config = Mock(spec=BotConfiguration)
        config.discord = Mock()
        config.discord.command_prefix = "!"
        config.discord.token = "test_token"
        return config
    
    @pytest.fixture
    def bot_with_monitor(self, mock_config, performance_monitor):
        """Create bot instance with performance monitor"""
        with patch('src.bot.discord_client.commands.Bot.__init__'):
            bot = AviationGirlBot(mock_config)
            bot.performance_monitor = performance_monitor
            bot.embed_builder = Mock()
            bot.embed_builder.create_info_embed = Mock(return_value=Mock())
            bot.embed_builder.colors = {"success": 0x00FF00, "warning": 0xFFFF00, "error": 0xFF0000}
            return bot
    
    def test_system_health_report_with_healthy_system(self, performance_monitor):
        """Test system health report generation with healthy system"""
        # Add a healthy system snapshot
        healthy_snapshot = SystemHealthSnapshot(
            timestamp=datetime.utcnow(),
            ai_model_healthy=True,
            rag_system_healthy=True,
            memory_system_healthy=True,
            discord_api_healthy=True,
            overall_health_score=0.95,
            active_users=25,
            active_conversations=15,
            error_rate=0.01,
            avg_response_time=1.2
        )
        performance_monitor.health_snapshots.append(healthy_snapshot)
        
        report = performance_monitor.get_system_health_report()
        
        assert report["status"] == "healthy"
        assert report["overall_health_score"] == 0.95
        assert report["components"]["ai_model"] == True
        assert report["components"]["rag_system"] == True
        assert report["components"]["memory_system"] == True
        assert report["components"]["discord_api"] == True
        assert report["metrics"]["active_users"] == 25
        assert report["metrics"]["active_conversations"] == 15
        assert report["metrics"]["error_rate"] == 0.01
        assert report["metrics"]["avg_response_time"] == 1.2
    
    def test_system_health_report_with_degraded_system(self, performance_monitor):
        """Test system health report generation with degraded system"""
        # Add a degraded system snapshot
        degraded_snapshot = SystemHealthSnapshot(
            timestamp=datetime.utcnow(),
            ai_model_healthy=True,
            rag_system_healthy=False,  # RAG system down
            memory_system_healthy=True,
            discord_api_healthy=True,
            overall_health_score=0.7,
            active_users=10,
            active_conversations=5,
            error_rate=0.05,
            avg_response_time=2.5
        )
        performance_monitor.health_snapshots.append(degraded_snapshot)
        
        report = performance_monitor.get_system_health_report()
        
        assert report["status"] == "degraded"
        assert report["overall_health_score"] == 0.7
        assert report["components"]["ai_model"] == True
        assert report["components"]["rag_system"] == False
        assert report["metrics"]["error_rate"] == 0.05
        assert report["metrics"]["avg_response_time"] == 2.5
    
    def test_system_health_report_with_critical_system(self, performance_monitor):
        """Test system health report generation with critical system state"""
        # Add a critical system snapshot
        critical_snapshot = SystemHealthSnapshot(
            timestamp=datetime.utcnow(),
            ai_model_healthy=False,  # AI model down
            rag_system_healthy=False,  # RAG system down
            memory_system_healthy=True,
            discord_api_healthy=False,  # Discord API issues
            overall_health_score=0.2,
            active_users=2,
            active_conversations=0,
            error_rate=0.25,
            avg_response_time=10.0
        )
        performance_monitor.health_snapshots.append(critical_snapshot)
        
        report = performance_monitor.get_system_health_report()
        
        assert report["status"] == "critical"
        assert report["overall_health_score"] == 0.2
        assert report["components"]["ai_model"] == False
        assert report["components"]["rag_system"] == False
        assert report["components"]["discord_api"] == False
        assert report["metrics"]["error_rate"] == 0.25
        assert report["metrics"]["avg_response_time"] == 10.0
    
    def test_system_health_report_with_no_data(self, performance_monitor):
        """Test system health report when no health data is available"""
        # Ensure no health snapshots
        performance_monitor.health_snapshots.clear()
        
        report = performance_monitor.get_system_health_report()
        
        assert report["status"] == "no_data"
        assert "No health data available" in report["message"]
    
    def test_user_engagement_report_generation(self, performance_monitor):
        """Test user engagement report generation"""
        current_time = datetime.utcnow()
        
        # Add user activity data
        performance_monitor.user_activity[123] = {
            "message_count": 50,
            "last_activity": current_time - timedelta(minutes=30),  # Active in last hour
            "session_start": current_time - timedelta(hours=2),
            "total_session_time": 3600.0,  # 1 hour
            "avg_response_satisfaction": 4.2,
            "satisfaction_ratings": [4, 4, 5, 4, 4]
        }
        
        performance_monitor.user_activity[456] = {
            "message_count": 25,
            "last_activity": current_time - timedelta(hours=12),  # Active in last 24h but not 1h
            "session_start": current_time - timedelta(hours=13),
            "total_session_time": 1800.0,  # 30 minutes
            "avg_response_satisfaction": 3.8,
            "satisfaction_ratings": [4, 3, 4, 4]
        }
        
        performance_monitor.user_activity[789] = {
            "message_count": 5,
            "last_activity": current_time - timedelta(days=2),  # Not active recently
            "session_start": current_time - timedelta(days=2),
            "total_session_time": 600.0,  # 10 minutes
            "avg_response_satisfaction": 3.5,
            "satisfaction_ratings": [3, 4, 3]
        }
        
        report = performance_monitor.get_user_engagement_report()
        
        assert report["active_users_1h"] == 1  # Only user 123
        assert report["active_users_24h"] == 2  # Users 123 and 456
        assert report["total_users"] == 3  # All users
        assert report["total_messages"] == 80  # 50 + 25 + 5
        assert report["total_session_time_hours"] == 2.0  # (3600 + 1800 + 600) / 3600
        assert 3.5 <= report["avg_satisfaction_score"] <= 4.2  # Average of satisfaction scores
        assert report["satisfaction_ratings_count"] == 3  # All users have ratings
    
    def test_resource_usage_tracking(self, performance_monitor):
        """Test resource usage tracking and reporting"""
        current_time = datetime.utcnow()
        
        # Add resource usage data
        performance_monitor.resource_usage["cpu_usage"].extend([
            (current_time - timedelta(minutes=5), 45.2),
            (current_time - timedelta(minutes=4), 52.1),
            (current_time - timedelta(minutes=3), 48.7),
            (current_time - timedelta(minutes=2), 51.3),
            (current_time - timedelta(minutes=1), 49.8)
        ])
        
        performance_monitor.resource_usage["memory_usage"].extend([
            (current_time - timedelta(minutes=5), 1024.5),
            (current_time - timedelta(minutes=4), 1156.2),
            (current_time - timedelta(minutes=3), 1089.7),
            (current_time - timedelta(minutes=2), 1134.8),
            (current_time - timedelta(minutes=1), 1098.3)
        ])
        
        usage = performance_monitor._get_current_resource_usage()
        
        assert "cpu_usage" in usage
        assert "memory_usage" in usage
        
        cpu_stats = usage["cpu_usage"]
        assert cpu_stats["current"] == 49.8  # Last value
        assert 45.0 <= cpu_stats["average"] <= 55.0  # Average of values
        assert cpu_stats["max"] == 52.1  # Maximum value
        assert cpu_stats["min"] == 45.2  # Minimum value
        
        memory_stats = usage["memory_usage"]
        assert memory_stats["current"] == 1098.3
        assert 1000.0 <= memory_stats["average"] <= 1200.0
    
    @pytest.mark.asyncio
    async def test_health_command_shows_comprehensive_report(self, bot_with_monitor):
        """Test health command displays comprehensive system health information"""
        # Set up health snapshot
        healthy_snapshot = SystemHealthSnapshot(
            timestamp=datetime.utcnow(),
            ai_model_healthy=True,
            rag_system_healthy=True,
            memory_system_healthy=False,  # One component unhealthy
            discord_api_healthy=True,
            overall_health_score=0.75,
            active_users=20,
            active_conversations=12,
            error_rate=0.03,
            avg_response_time=1.8
        )
        bot_with_monitor.performance_monitor.health_snapshots.append(healthy_snapshot)
        
        # Mock context
        ctx = Mock()
        ctx.send = AsyncMock()
        
        await bot_with_monitor.health_command(ctx)
        
        # Verify embed was created
        bot_with_monitor.embed_builder.create_info_embed.assert_called_once()
        call_args = bot_with_monitor.embed_builder.create_info_embed.call_args[0]
        assert "System Health Report" in call_args[0]
        assert "DEGRADED" in call_args[1].upper()  # Overall status
        
        # Verify embed was sent
        ctx.send.assert_called_once()
    
    @pytest.mark.asyncio
    async def test_health_command_handles_missing_performance_monitor(self, mock_config):
        """Test health command handles missing performance monitor gracefully"""
        with patch('src.bot.discord_client.commands.Bot.__init__'):
            bot = AviationGirlBot(mock_config)
            bot.performance_monitor = None  # No performance monitor
            bot.embed_builder = Mock()
            bot.embed_builder.create_error_embed = Mock(return_value=Mock())
            
            ctx = Mock()
            ctx.send = AsyncMock()
            
            await bot.health_command.callback(bot, ctx)
            
            # Verify error embed was created
            bot.embed_builder.create_error_embed.assert_called_once()
            call_args = bot.embed_builder.create_error_embed.call_args[0]
            assert "Performance Monitor Unavailable" in call_args[0]
            
            ctx.send.assert_called_once()
    
    @pytest.mark.asyncio
    async def test_performance_command_shows_time_windowed_stats(self, bot_with_monitor):
        """Test performance command displays statistics for different time windows"""
        # Mock performance stats
        bot_with_monitor.performance_monitor.get_performance_stats = Mock()
        bot_with_monitor.performance_monitor.get_performance_stats.side_effect = [
            # 1 hour stats
            {
                'overall': {
                    'avg_response_time': 1.5,
                    'error_rate': 0.02,
                    'active_users': 15,
                    'user_engagement_score': 4.1
                },
                'components': {
                    'ai_orchestrator': {'avg_response_time': 1.2, 'error_rate': 0.01},
                    'rag_system': {'avg_response_time': 0.8, 'error_rate': 0.005}
                }
            },
            # 24 hour stats
            {
                'overall': {
                    'avg_response_time': 1.8,
                    'error_rate': 0.025,
                    'active_users': 45,
                    'user_engagement_score': 3.9
                },
                'components': {
                    'ai_orchestrator': {'avg_response_time': 1.4, 'error_rate': 0.015},
                    'rag_system': {'avg_response_time': 0.9, 'error_rate': 0.008}
                }
            }
        ]
        
        ctx = Mock()
        ctx.send = AsyncMock()
        
        await bot_with_monitor.performance_command(ctx)
        
        # Verify performance stats were requested for both time windows
        assert bot_with_monitor.performance_monitor.get_performance_stats.call_count == 2
        calls = bot_with_monitor.performance_monitor.get_performance_stats.call_args_list
        assert calls[0][0][0] == 1  # 1 hour
        assert calls[1][0][0] == 24  # 24 hours
        
        # Verify embed was created and sent
        bot_with_monitor.embed_builder.create_info_embed.assert_called_once()
        ctx.send.assert_called_once()
    
    @pytest.mark.asyncio
    async def test_performance_command_handles_missing_performance_monitor(self, mock_config):
        """Test performance command handles missing performance monitor gracefully"""
        with patch('src.bot.discord_client.commands.Bot.__init__'):
            bot = AviationGirlBot(mock_config)
            bot.performance_monitor = None
            bot.embed_builder = Mock()
            bot.embed_builder.create_error_embed = Mock(return_value=Mock())
            
            ctx = Mock()
            ctx.send = AsyncMock()
            
            await bot.performance_command.callback(bot, ctx)
            
            # Verify error embed was created
            bot.embed_builder.create_error_embed.assert_called_once()
            call_args = bot.embed_builder.create_error_embed.call_args[0]
            assert "Performance Monitor Unavailable" in call_args[0]
            
            ctx.send.assert_called_once()
    
    def test_component_health_tracking(self, performance_monitor):
        """Test individual component health tracking"""
        # Test update_component_health method
        performance_monitor.update_component_health("ai_model", True)
        performance_monitor.update_component_health("rag_system", False)
        performance_monitor.update_component_health("memory_system", True)
        
        # Verify component stats are updated
        assert "ai_model" in performance_monitor.component_stats
        assert "rag_system" in performance_monitor.component_stats
        assert "memory_system" in performance_monitor.component_stats
    
    def test_metric_recording_and_retrieval(self, performance_monitor):
        """Test metric recording and retrieval functionality"""
        current_time = datetime.utcnow()
        
        # Record some metrics
        metric1 = PerformanceMetric(
            timestamp=current_time,
            metric_type=MetricType.RESPONSE_TIME,
            component="ai_orchestrator",
            value=1.25,
            metadata={"user_id": 123}
        )
        
        metric2 = PerformanceMetric(
            timestamp=current_time,
            metric_type=MetricType.ERROR_RATE,
            component="rag_system",
            value=0.02,
            metadata={"error_type": "timeout"}
        )
        
        performance_monitor.metrics.append(metric1)
        performance_monitor.metrics.append(metric2)
        
        # Verify metrics are stored
        assert len(performance_monitor.metrics) == 2
        assert performance_monitor.metrics[0].component == "ai_orchestrator"
        assert performance_monitor.metrics[1].component == "rag_system"
        assert performance_monitor.metrics[0].value == 1.25
        assert performance_monitor.metrics[1].value == 0.02
    
    def test_health_score_calculation_logic(self, performance_monitor):
        """Test health score calculation and status determination"""
        test_cases = [
            (0.95, "healthy"),
            (0.85, "healthy"),
            (0.75, "degraded"),
            (0.65, "degraded"),
            (0.55, "unhealthy"),
            (0.45, "unhealthy"),
            (0.35, "critical"),
            (0.15, "critical")
        ]
        
        for health_score, expected_status in test_cases:
            snapshot = SystemHealthSnapshot(
                timestamp=datetime.utcnow(),
                ai_model_healthy=True,
                rag_system_healthy=True,
                memory_system_healthy=True,
                discord_api_healthy=True,
                overall_health_score=health_score,
                active_users=10,
                active_conversations=5,
                error_rate=0.01,
                avg_response_time=1.0
            )
            
            performance_monitor.health_snapshots.clear()
            performance_monitor.health_snapshots.append(snapshot)
            
            report = performance_monitor.get_system_health_report()
            assert report["status"] == expected_status, f"Health score {health_score} should result in status '{expected_status}', got '{report['status']}'"
    
    def test_resource_usage_data_structure(self, performance_monitor):
        """Test resource usage data structure and limits"""
        current_time = datetime.utcnow()
        
        # Add more data than the deque limit to test maxlen
        for i in range(150):  # More than maxlen=100
            timestamp = current_time - timedelta(minutes=i)
            performance_monitor.resource_usage["cpu_usage"].append((timestamp, 50.0 + i))
        
        # Verify deque respects maxlen
        assert len(performance_monitor.resource_usage["cpu_usage"]) == 100
        
        # Verify most recent data is preserved
        latest_timestamp, latest_value = performance_monitor.resource_usage["cpu_usage"][-1]
        assert latest_value == 50.0  # Most recent value (i=0)
    
    @pytest.mark.asyncio
    async def test_admin_health_command_comprehensive_diagnostics(self, bot_with_monitor):
        """Test admin health command provides comprehensive diagnostics"""
        # Mock all required methods
        bot_with_monitor.performance_monitor.get_system_health_report = Mock(return_value={
            "status": "healthy",
            "overall_health_score": 0.9,
            "timestamp": datetime.utcnow().isoformat(),
            "resource_usage": {
                "cpu_usage": {"current": 45.2, "average": 42.1},
                "memory_usage": {"current": 1024.5, "average": 1000.2}
            }
        })
        
        bot_with_monitor.performance_monitor.get_performance_stats = Mock(return_value={
            'overall': {
                'avg_response_time': 1.3,
                'error_rate': 0.015,
                'active_users': 25,
                'user_engagement_score': 4.2
            },
            'total_metrics': 1500
        })
        
        bot_with_monitor.performance_monitor.get_user_engagement_report = Mock(return_value={
            'active_users_24h': 45,
            'active_users_1h': 12,
            'total_users': 150,
            'total_messages': 2500
        })
        
        # Mock error handler
        bot_with_monitor.error_handler = Mock()
        bot_with_monitor.error_handler.get_error_statistics = Mock(return_value={
            'recovery_success_rate': 0.95,
            'most_common_category': 'network_timeout'
        })
        
        # Mock startup report
        bot_with_monitor.startup_report = Mock()
        bot_with_monitor.startup_report.overall_status = Mock()
        bot_with_monitor.startup_report.overall_status.value = "passed"
        bot_with_monitor.startup_report.passed_checks = 8
        bot_with_monitor.startup_report.failed_checks = 0
        bot_with_monitor.startup_report.warning_checks = 1
        
        # Mock context with admin permissions
        ctx = Mock()
        ctx.send = AsyncMock()
        ctx.author = Mock()
        ctx.author.guild_permissions = Mock()
        ctx.author.guild_permissions.administrator = True
        
        # Mock the permission check decorator
        with patch('discord.ext.commands.has_permissions', lambda **kwargs: lambda func: func):
            await bot_with_monitor.admin_health_command(ctx)
        
        # Verify comprehensive data was collected
        bot_with_monitor.performance_monitor.get_system_health_report.assert_called_once()
        bot_with_monitor.performance_monitor.get_performance_stats.assert_called_once_with(24)
        bot_with_monitor.performance_monitor.get_user_engagement_report.assert_called_once()
        
        # Verify embed was created and sent
        bot_with_monitor.embed_builder.create_info_embed.assert_called_once()
        ctx.send.assert_called_once()
    
    def test_health_snapshot_data_integrity(self):
        """Test SystemHealthSnapshot data integrity and validation"""
        current_time = datetime.utcnow()
        
        snapshot = SystemHealthSnapshot(
            timestamp=current_time,
            ai_model_healthy=True,
            rag_system_healthy=False,
            memory_system_healthy=True,
            discord_api_healthy=True,
            overall_health_score=0.75,
            active_users=20,
            active_conversations=15,
            error_rate=0.03,
            avg_response_time=1.8
        )
        
        # Verify all fields are properly set
        assert snapshot.timestamp == current_time
        assert snapshot.ai_model_healthy == True
        assert snapshot.rag_system_healthy == False
        assert snapshot.memory_system_healthy == True
        assert snapshot.discord_api_healthy == True
        assert snapshot.overall_health_score == 0.75
        assert snapshot.active_users == 20
        assert snapshot.active_conversations == 15
        assert snapshot.error_rate == 0.03
        assert snapshot.avg_response_time == 1.8
    
    def test_performance_metric_data_integrity(self):
        """Test PerformanceMetric data integrity and validation"""
        current_time = datetime.utcnow()
        
        metric = PerformanceMetric(
            timestamp=current_time,
            metric_type=MetricType.RESPONSE_TIME,
            component="test_component",
            value=2.5,
            metadata={"test_key": "test_value", "user_id": 123}
        )
        
        # Verify all fields are properly set
        assert metric.timestamp == current_time
        assert metric.metric_type == MetricType.RESPONSE_TIME
        assert metric.component == "test_component"
        assert metric.value == 2.5
        assert metric.metadata["test_key"] == "test_value"
        assert metric.metadata["user_id"] == 123