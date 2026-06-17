"""
Test Performance Monitoring and Metrics
Property-based tests for comprehensive performance monitoring and metrics collection

Feature: aviation-discord-bot, Property 13: Performance Monitoring and Metrics
*For any* system operation, the bot should track response times, error rates, 
user engagement statistics, and provide performance metrics for monitoring and optimization.

Validates: Requirements 10.4
"""

import pytest
import asyncio
import time
from unittest.mock import Mock, AsyncMock, patch
from hypothesis import given, strategies as st, settings, HealthCheck
from datetime import datetime, timedelta
import tempfile
import os
import json

# Import the components we're testing
from v4.src.bot.performance_monitor import (
    PerformanceMonitor, OperationTracker, MetricType, 
    PerformanceMetric, SystemHealthSnapshot, track_performance
)
from v4.src.bot.message_handler import MessageHandler
from v4.src.bot.embed_builder import EmbedBuilder


class TestPerformanceMonitoringAndMetrics:
    """Property-based tests for performance monitoring and metrics"""
    
    @pytest.fixture
    def performance_monitor(self):
        """Create performance monitor for testing"""
        temp_dir = tempfile.mkdtemp()
        monitor = PerformanceMonitor(data_dir=temp_dir)
        yield monitor
        # Cleanup
        try:
            asyncio.run(monitor.shutdown())
        except:
            pass
    
    @pytest.fixture
    def mock_embed_builder(self):
        """Mock embed builder for testing"""
        embed_builder = Mock(spec=EmbedBuilder)
        embed_builder.create_error_embed.return_value = Mock()
        embed_builder.create_info_embed.return_value = Mock()
        return embed_builder
    
    @given(
        operation_ids=st.text(min_size=1, max_size=50),
        component_names=st.sampled_from([
            "message_handler", "ai_orchestrator", "rag_system", 
            "memory_system", "embed_builder", "discord_client"
        ]),
        operation_durations=st.floats(min_value=0.001, max_value=10.0),
        success_rates=st.booleans()
    )
    @settings(max_examples=50, deadline=10000, suppress_health_check=[HealthCheck.function_scoped_fixture])
    def test_operation_tracking_accuracy(
        self, 
        performance_monitor,
        operation_ids, 
        component_names, 
        operation_durations,
        success_rates
    ):
        """
        Property: Performance monitor should accurately track operation 
        start/end times and calculate correct durations
        """
        # Start operation tracking
        tracking_id = performance_monitor.start_operation(
            operation_ids, 
            component_names,
            {"test_metadata": "test_value"}
        )
        
        # Verify tracking ID was generated
        assert tracking_id is not None
        assert isinstance(tracking_id, str)
        assert len(tracking_id) > 0
        
        # Verify operation is being tracked
        assert tracking_id in performance_monitor.active_operations
        
        # Simulate operation duration
        time.sleep(min(operation_durations, 0.1))  # Cap sleep to prevent test slowdown
        
        # End operation tracking
        measured_duration = performance_monitor.end_operation(
            tracking_id, 
            success_rates,
            {"result_metadata": "test_result"}
        )
        
        # Verify operation was removed from active tracking
        assert tracking_id not in performance_monitor.active_operations
        
        # Verify duration measurement is reasonable
        assert measured_duration > 0
        assert measured_duration < 1.0  # Should be less than 1 second for our test
        
        # Verify component statistics were updated
        stats = performance_monitor.component_stats[component_names]
        assert stats["total_operations"] > 0
        assert stats["total_time"] > 0
        
        if not success_rates:
            assert stats["error_count"] > 0
        
        # Verify metric was recorded
        assert len(performance_monitor.metrics) > 0
        
        # Find the response time metric
        response_time_metrics = [
            m for m in performance_monitor.metrics 
            if m.metric_type == MetricType.RESPONSE_TIME and m.component == component_names
        ]
        assert len(response_time_metrics) > 0
        
        latest_metric = response_time_metrics[-1]
        assert latest_metric.value == measured_duration
        assert latest_metric.metadata["success"] == success_rates
    
    @given(
        user_ids=st.integers(min_value=1, max_value=1000000),
        activity_types=st.sampled_from(["message", "feedback", "interaction"]),
        message_counts=st.integers(min_value=1, max_value=100),
        feedback_ratings=st.integers(min_value=-1, max_value=1)
    )
    @settings(max_examples=50, deadline=8000, suppress_health_check=[HealthCheck.function_scoped_fixture])
    def test_user_engagement_tracking(
        self,
        performance_monitor,
        user_ids,
        activity_types,
        message_counts,
        feedback_ratings
    ):
        """
        Property: Performance monitor should accurately track user engagement
        including message counts, session times, and satisfaction ratings
        """
        # Record multiple user activities
        for i in range(min(message_counts, 10)):  # Limit to prevent test slowdown
            if activity_types == "message":
                performance_monitor.record_user_activity(
                    user_ids, 
                    "message",
                    {"message_length": 50 + i}
                )
            elif activity_types == "feedback":
                performance_monitor.record_user_activity(
                    user_ids,
                    "feedback",
                    {"rating": feedback_ratings}
                )
            else:
                performance_monitor.record_user_activity(
                    user_ids,
                    activity_types,
                    {"interaction_type": "test"}
                )
        
        # Verify user activity was tracked
        assert user_ids in performance_monitor.user_activity
        user_stats = performance_monitor.user_activity[user_ids]
        
        # Verify activity counts
        if activity_types == "message":
            assert user_stats["message_count"] >= min(message_counts, 10)
            assert user_stats["last_activity"] is not None
            assert user_stats["session_start"] is not None
        
        if activity_types == "feedback":
            assert len(user_stats["satisfaction_ratings"]) >= min(message_counts, 10)
            # Average satisfaction should be calculated correctly
            if user_stats["satisfaction_ratings"]:
                expected_avg = sum(user_stats["satisfaction_ratings"][-10:]) / len(user_stats["satisfaction_ratings"][-10:])
                assert abs(user_stats["avg_response_satisfaction"] - expected_avg) < 0.001
        
        # Verify metrics were recorded
        engagement_metrics = [
            m for m in performance_monitor.metrics 
            if m.metric_type == MetricType.USER_ENGAGEMENT
        ]
        assert len(engagement_metrics) >= min(message_counts, 10)
        
        # Verify user engagement report
        engagement_report = performance_monitor.get_user_engagement_report()
        assert "total_users" in engagement_report
        assert engagement_report["total_users"] >= 1
        assert "total_messages" in engagement_report
    
    @given(
        error_types=st.sampled_from([
            "validation_error", "network_error", "timeout_error",
            "database_error", "api_error", "processing_error"
        ]),
        component_names=st.sampled_from([
            "message_handler", "ai_orchestrator", "rag_system", 
            "memory_system", "discord_api"
        ]),
        error_counts=st.integers(min_value=1, max_value=20)
    )
    @settings(max_examples=40, deadline=8000, suppress_health_check=[HealthCheck.function_scoped_fixture])
    def test_error_rate_tracking(
        self,
        performance_monitor,
        error_types,
        component_names,
        error_counts
    ):
        """
        Property: Performance monitor should accurately track error rates
        and provide meaningful error statistics
        """
        # Record multiple errors
        for i in range(min(error_counts, 15)):  # Limit to prevent test slowdown
            performance_monitor.record_error(
                component_names,
                error_types,
                {"error_instance": i, "severity": "medium"}
            )
        
        # Verify component error count was updated
        stats = performance_monitor.component_stats[component_names]
        assert stats["error_count"] >= min(error_counts, 15)
        
        # Verify error metrics were recorded
        error_metrics = [
            m for m in performance_monitor.metrics 
            if m.metric_type == MetricType.ERROR_RATE and m.component == component_names
        ]
        assert len(error_metrics) >= min(error_counts, 15)
        
        # Verify error metadata
        for metric in error_metrics:
            assert metric.value == 1.0  # Each error is recorded as 1.0
            assert "error_type" in metric.metadata
            assert metric.metadata["error_type"] == error_types
        
        # Verify performance statistics include error information
        perf_stats = performance_monitor.get_performance_stats(time_window_hours=1)
        assert "components" in perf_stats
        
        if component_names in perf_stats["components"]:
            component_stats = perf_stats["components"][component_names]
            assert "error_count" in component_stats
            assert component_stats["error_count"] >= min(error_counts, 15)
            assert "error_rate" in component_stats
            assert 0 <= component_stats["error_rate"] <= 1
    
    @given(
        cpu_percentages=st.floats(min_value=0.0, max_value=100.0),
        memory_mb=st.floats(min_value=100.0, max_value=8192.0),
        disk_mb=st.floats(min_value=1000.0, max_value=100000.0),
        network_kb=st.floats(min_value=0.0, max_value=10000.0)
    )
    @settings(max_examples=30, deadline=6000, suppress_health_check=[HealthCheck.function_scoped_fixture])
    def test_resource_usage_tracking(
        self,
        performance_monitor,
        cpu_percentages,
        memory_mb,
        disk_mb,
        network_kb
    ):
        """
        Property: Performance monitor should track system resource usage
        and provide accurate resource utilization metrics
        """
        # Record resource usage
        performance_monitor.record_resource_usage(
            cpu_percentages,
            memory_mb,
            disk_mb,
            network_kb
        )
        
        # Verify resource usage was stored
        assert len(performance_monitor.resource_usage["cpu_usage"]) > 0
        assert len(performance_monitor.resource_usage["memory_usage"]) > 0
        assert len(performance_monitor.resource_usage["disk_usage"]) > 0
        assert len(performance_monitor.resource_usage["network_usage"]) > 0
        
        # Verify resource values
        latest_cpu = performance_monitor.resource_usage["cpu_usage"][-1]
        latest_memory = performance_monitor.resource_usage["memory_usage"][-1]
        latest_disk = performance_monitor.resource_usage["disk_usage"][-1]
        latest_network = performance_monitor.resource_usage["network_usage"][-1]
        
        assert latest_cpu[1] == cpu_percentages
        assert latest_memory[1] == memory_mb
        assert latest_disk[1] == disk_mb
        assert latest_network[1] == network_kb
        
        # Verify resource metrics were recorded
        resource_metrics = [
            m for m in performance_monitor.metrics 
            if m.metric_type == MetricType.RESOURCE_USAGE
        ]
        assert len(resource_metrics) >= 4  # cpu, memory, disk, network
        
        # Verify system health report includes resource usage
        health_report = performance_monitor.get_system_health_report()
        if "resource_usage" in health_report:
            resource_usage = health_report["resource_usage"]
            
            # Check that resource types are present
            expected_resources = ["cpu_usage", "memory_usage", "disk_usage", "network_usage"]
            for resource_type in expected_resources:
                if resource_type in resource_usage:
                    assert "current" in resource_usage[resource_type]
                    assert "average" in resource_usage[resource_type]
    
    @given(
        operations_counts=st.integers(min_value=1, max_value=1000),
        time_windows=st.floats(min_value=1.0, max_value=3600.0),
        component_names=st.sampled_from([
            "message_handler", "ai_orchestrator", "rag_system"
        ])
    )
    @settings(max_examples=30, deadline=6000, suppress_health_check=[HealthCheck.function_scoped_fixture])
    def test_throughput_tracking(
        self,
        performance_monitor,
        operations_counts,
        time_windows,
        component_names
    ):
        """
        Property: Performance monitor should accurately calculate and track
        system throughput (operations per second)
        """
        # Record throughput
        performance_monitor.record_throughput(
            component_names,
            operations_counts,
            time_windows
        )
        
        # Calculate expected throughput
        expected_throughput = operations_counts / time_windows
        
        # Verify throughput metric was recorded
        throughput_metrics = [
            m for m in performance_monitor.metrics 
            if m.metric_type == MetricType.THROUGHPUT and m.component == component_names
        ]
        assert len(throughput_metrics) > 0
        
        latest_metric = throughput_metrics[-1]
        assert abs(latest_metric.value - expected_throughput) < 0.001  # Allow for floating point precision
        assert latest_metric.metadata["operations_count"] == operations_counts
        assert latest_metric.metadata["time_window"] == time_windows
    
    @given(
        health_scores=st.floats(min_value=0.0, max_value=1.0),
        active_user_counts=st.integers(min_value=0, max_value=1000),
        error_rates=st.floats(min_value=0.0, max_value=1.0),
        response_times=st.floats(min_value=0.001, max_value=10.0)
    )
    @settings(max_examples=30, deadline=8000, suppress_health_check=[HealthCheck.function_scoped_fixture])
    def test_system_health_monitoring(
        self,
        performance_monitor,
        health_scores,
        active_user_counts,
        error_rates,
        response_times
    ):
        """
        Property: Performance monitor should provide accurate system health
        monitoring with meaningful health scores and status reporting
        """
        # Simulate system activity to generate health data
        # Add some response time metrics
        for i in range(5):
            tracking_id = performance_monitor.start_operation(f"test_op_{i}", "test_component")
            time.sleep(0.001)  # Small delay
            performance_monitor.end_operation(tracking_id, True)
        
        # Add some user activity
        for user_id in range(min(active_user_counts, 10)):
            performance_monitor.record_user_activity(user_id, "message", {"test": True})
        
        # Trigger health collection
        asyncio.run(performance_monitor._collect_system_health())
        
        # Verify health snapshots were created
        assert len(performance_monitor.health_snapshots) > 0
        
        latest_snapshot = performance_monitor.health_snapshots[-1]
        assert isinstance(latest_snapshot, SystemHealthSnapshot)
        assert 0 <= latest_snapshot.overall_health_score <= 1
        assert latest_snapshot.active_users >= 0
        assert latest_snapshot.error_rate >= 0
        assert latest_snapshot.avg_response_time >= 0
        
        # Verify system health report
        health_report = performance_monitor.get_system_health_report()
        assert "status" in health_report
        assert health_report["status"] in ["healthy", "degraded", "unhealthy", "critical"]
        assert "overall_health_score" in health_report
        assert 0 <= health_report["overall_health_score"] <= 1
        assert "components" in health_report
        assert "metrics" in health_report
    
    @given(
        time_windows=st.integers(min_value=1, max_value=24),
        metric_counts=st.integers(min_value=10, max_value=100)
    )
    @settings(max_examples=20, deadline=10000, suppress_health_check=[HealthCheck.function_scoped_fixture])
    def test_performance_statistics_accuracy(
        self,
        performance_monitor,
        time_windows,
        metric_counts
    ):
        """
        Property: Performance monitor should provide accurate performance
        statistics aggregated over specified time windows
        """
        # Generate test metrics
        for i in range(min(metric_counts, 50)):  # Limit to prevent test slowdown
            # Add response time metrics
            tracking_id = performance_monitor.start_operation(f"op_{i}", "test_component")
            time.sleep(0.001)
            performance_monitor.end_operation(tracking_id, i % 5 != 0)  # 20% error rate
            
            # Add user activity
            performance_monitor.record_user_activity(i % 10, "message", {"test": True})
        
        # Get performance statistics
        stats = performance_monitor.get_performance_stats(time_window_hours=time_windows)
        
        # Verify statistics structure
        assert "time_window_hours" in stats
        assert stats["time_window_hours"] == time_windows
        assert "total_metrics" in stats
        assert stats["total_metrics"] >= 0
        assert "components" in stats
        assert "overall" in stats
        
        # Verify overall statistics
        overall = stats["overall"]
        assert "avg_response_time" in overall
        assert "error_rate" in overall
        assert "active_users" in overall
        assert overall["avg_response_time"] >= 0
        assert 0 <= overall["error_rate"] <= 1
        assert overall["active_users"] >= 0
        
        # Verify component statistics
        if "test_component" in stats["components"]:
            component_stats = stats["components"]["test_component"]
            assert "total_operations" in component_stats
            assert "avg_response_time" in component_stats
            assert "error_rate" in component_stats
            assert component_stats["total_operations"] > 0
            assert component_stats["avg_response_time"] > 0
            assert 0 <= component_stats["error_rate"] <= 1
    
    @given(
        operation_names=st.text(min_size=1, max_size=30),
        component_names=st.sampled_from(["test_component", "another_component"])
    )
    @settings(max_examples=20, deadline=8000, suppress_health_check=[HealthCheck.function_scoped_fixture])
    def test_operation_tracker_context_manager(
        self,
        performance_monitor,
        operation_names,
        component_names
    ):
        """
        Property: OperationTracker context manager should properly track
        operations and handle both successful and failed operations
        """
        initial_metric_count = len(performance_monitor.metrics)
        
        # Test successful operation
        with OperationTracker(performance_monitor, operation_names, component_names, {"test": "metadata"}):
            time.sleep(0.001)  # Simulate work
        
        # Verify metric was recorded for successful operation
        assert len(performance_monitor.metrics) > initial_metric_count
        
        # Find the response time metric
        response_metrics = [
            m for m in performance_monitor.metrics 
            if m.metric_type == MetricType.RESPONSE_TIME and m.component == component_names
        ]
        assert len(response_metrics) > 0
        
        latest_metric = response_metrics[-1]
        assert latest_metric.metadata["success"] == True
        assert "test" in latest_metric.metadata
        
        # Test failed operation
        initial_metric_count = len(performance_monitor.metrics)
        
        try:
            with OperationTracker(performance_monitor, operation_names + "_fail", component_names):
                time.sleep(0.001)
                raise ValueError("Test error")
        except ValueError:
            pass  # Expected
        
        # Verify metric was recorded for failed operation
        assert len(performance_monitor.metrics) > initial_metric_count
        
        # Find the latest response time metric
        response_metrics = [
            m for m in performance_monitor.metrics 
            if m.metric_type == MetricType.RESPONSE_TIME and m.component == component_names
        ]
        
        # Find the failed operation metric
        failed_metrics = [m for m in response_metrics if not m.metadata.get("success", True)]
        assert len(failed_metrics) > 0
        
        failed_metric = failed_metrics[-1]
        assert failed_metric.metadata["success"] == False
        assert "error_type" in failed_metric.metadata
        assert failed_metric.metadata["error_type"] == "ValueError"


if __name__ == "__main__":
    pytest.main([__file__, "-v"])