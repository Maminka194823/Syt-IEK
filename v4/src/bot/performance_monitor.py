"""
V4 Performance Monitor
Comprehensive performance monitoring and metrics collection
Tracks response times, error rates, and user engagement statistics
"""

import time
import asyncio
import logging
from typing import Dict, Any, List, Optional, Callable
from datetime import datetime, timedelta
from dataclasses import dataclass, field
from collections import defaultdict, deque
import json
import os
from enum import Enum
import statistics


class MetricType(Enum):
    """Types of metrics being tracked"""
    RESPONSE_TIME = "response_time"
    ERROR_RATE = "error_rate"
    USER_ENGAGEMENT = "user_engagement"
    SYSTEM_HEALTH = "system_health"
    THROUGHPUT = "throughput"
    RESOURCE_USAGE = "resource_usage"


@dataclass
class PerformanceMetric:
    """Individual performance metric data point"""
    timestamp: datetime
    metric_type: MetricType
    component: str
    value: float
    metadata: Dict[str, Any] = field(default_factory=dict)


@dataclass
class SystemHealthSnapshot:
    """System health snapshot at a point in time"""
    timestamp: datetime
    ai_model_healthy: bool
    rag_system_healthy: bool
    memory_system_healthy: bool
    discord_api_healthy: bool
    overall_health_score: float
    active_users: int
    active_conversations: int
    error_rate: float
    avg_response_time: float


class PerformanceMonitor:
    """
    Comprehensive performance monitoring system
    Collects metrics, tracks system health, and provides diagnostics
    """
    
    def __init__(self, data_dir: str = "data/metrics"):
        self.data_dir = data_dir
        self.metrics_file = os.path.join(data_dir, "performance_metrics.json")
        self.health_file = os.path.join(data_dir, "system_health.json")
        
        # In-memory metric storage (recent data)
        self.metrics = deque(maxlen=10000)  # Keep last 10k metrics
        self.health_snapshots = deque(maxlen=1000)  # Keep last 1k health snapshots
        
        # Real-time tracking
        self.active_operations = {}  # operation_id -> start_time
        self.component_stats = defaultdict(lambda: {
            "total_operations": 0,
            "total_time": 0.0,
            "error_count": 0,
            "last_operation": None
        })
        
        # User engagement tracking
        self.user_activity = defaultdict(lambda: {
            "message_count": 0,
            "last_activity": None,
            "session_start": None,
            "total_session_time": 0.0,
            "avg_response_satisfaction": 0.0,
            "satisfaction_ratings": []
        })
        
        # System resource tracking
        self.resource_usage = {
            "cpu_usage": deque(maxlen=100),
            "memory_usage": deque(maxlen=100),
            "disk_usage": deque(maxlen=100),
            "network_usage": deque(maxlen=100)
        }
        
        # Configuration
        self.metric_retention_hours = 24
        self.health_check_interval = 60  # seconds
        self.auto_save_interval = 300  # seconds (5 minutes)
        
        # Ensure data directory exists
        os.makedirs(data_dir, exist_ok=True)
        
        # Start background tasks
        self._background_tasks = []
        self._start_background_monitoring()
    
    def _start_background_monitoring(self):
        """Start background monitoring tasks"""
        try:
            # Only start background tasks if we're in an async context
            try:
                loop = asyncio.get_running_loop()
                # Health monitoring task
                health_task = loop.create_task(self._health_monitoring_loop())
                self._background_tasks.append(health_task)
                
                # Auto-save task
                save_task = loop.create_task(self._auto_save_loop())
                self._background_tasks.append(save_task)
                
                # Cleanup task
                cleanup_task = loop.create_task(self._cleanup_loop())
                self._background_tasks.append(cleanup_task)
            except RuntimeError:
                # No event loop running, skip background tasks
                logging.info("No event loop running, skipping background monitoring tasks")
            
        except Exception as e:
            logging.error(f"Failed to start background monitoring: {e}")
    
    async def _health_monitoring_loop(self):
        """Background task for periodic health monitoring"""
        while True:
            try:
                await asyncio.sleep(self.health_check_interval)
                await self._collect_system_health()
            except asyncio.CancelledError:
                break
            except Exception as e:
                logging.error(f"Error in health monitoring loop: {e}")
    
    async def _auto_save_loop(self):
        """Background task for auto-saving metrics"""
        while True:
            try:
                await asyncio.sleep(self.auto_save_interval)
                await self.save_metrics_to_disk()
            except asyncio.CancelledError:
                break
            except Exception as e:
                logging.error(f"Error in auto-save loop: {e}")
    
    async def _cleanup_loop(self):
        """Background task for cleaning up old metrics"""
        while True:
            try:
                await asyncio.sleep(3600)  # Run every hour
                self._cleanup_old_metrics()
            except asyncio.CancelledError:
                break
            except Exception as e:
                logging.error(f"Error in cleanup loop: {e}")
    
    def start_operation(self, operation_id: str, component: str, metadata: Dict[str, Any] = None) -> str:
        """
        Start tracking a performance operation
        Returns operation tracking ID
        """
        tracking_id = f"{component}_{operation_id}_{int(time.time() * 1000)}"
        
        self.active_operations[tracking_id] = {
            "start_time": time.time(),
            "component": component,
            "operation_id": operation_id,
            "metadata": metadata or {}
        }
        
        return tracking_id
    
    def end_operation(self, tracking_id: str, success: bool = True, metadata: Dict[str, Any] = None) -> float:
        """
        End tracking a performance operation
        Returns operation duration in seconds
        """
        if tracking_id not in self.active_operations:
            logging.warning(f"Unknown operation tracking ID: {tracking_id}")
            return 0.0
        
        operation = self.active_operations.pop(tracking_id)
        duration = time.time() - operation["start_time"]
        component = operation["component"]
        
        # Update component statistics
        stats = self.component_stats[component]
        stats["total_operations"] += 1
        stats["total_time"] += duration
        stats["last_operation"] = datetime.utcnow()
        
        if not success:
            stats["error_count"] += 1
        
        # Record performance metric
        metric = PerformanceMetric(
            timestamp=datetime.utcnow(),
            metric_type=MetricType.RESPONSE_TIME,
            component=component,
            value=duration,
            metadata={
                **operation.get("metadata", {}),
                **(metadata or {}),
                "success": success,
                "operation_id": operation["operation_id"]
            }
        )
        
        self.metrics.append(metric)
        
        return duration
    
    def record_error(self, component: str, error_type: str, metadata: Dict[str, Any] = None):
        """Record an error occurrence"""
        # Update component error count
        self.component_stats[component]["error_count"] += 1
        
        # Record error rate metric
        metric = PerformanceMetric(
            timestamp=datetime.utcnow(),
            metric_type=MetricType.ERROR_RATE,
            component=component,
            value=1.0,  # Error occurred
            metadata={
                "error_type": error_type,
                **(metadata or {})
            }
        )
        
        self.metrics.append(metric)
    
    def record_user_activity(
        self, 
        user_id: int, 
        activity_type: str, 
        metadata: Dict[str, Any] = None
    ):
        """Record user activity for engagement tracking"""
        current_time = datetime.utcnow()
        user_stats = self.user_activity[user_id]
        
        # Update user statistics
        if activity_type == "message":
            user_stats["message_count"] += 1
            
            # Track session time
            if user_stats["session_start"] is None:
                user_stats["session_start"] = current_time
            
            if user_stats["last_activity"]:
                session_gap = (current_time - user_stats["last_activity"]).total_seconds()
                if session_gap > 1800:  # 30 minutes gap = new session
                    user_stats["session_start"] = current_time
                else:
                    user_stats["total_session_time"] += session_gap
        
        elif activity_type == "feedback":
            # Record satisfaction rating
            rating = metadata.get("rating", 0) if metadata else 0
            user_stats["satisfaction_ratings"].append(rating)
            
            # Calculate average satisfaction
            if user_stats["satisfaction_ratings"]:
                user_stats["avg_response_satisfaction"] = statistics.mean(
                    user_stats["satisfaction_ratings"][-10:]  # Last 10 ratings
                )
        
        user_stats["last_activity"] = current_time
        
        # Record engagement metric
        metric = PerformanceMetric(
            timestamp=current_time,
            metric_type=MetricType.USER_ENGAGEMENT,
            component="user_activity",
            value=1.0,
            metadata={
                "user_id": user_id,
                "activity_type": activity_type,
                **(metadata or {})
            }
        )
        
        self.metrics.append(metric)
    
    def record_throughput(self, component: str, operations_count: int, time_window: float):
        """Record throughput metrics (operations per second)"""
        throughput = operations_count / time_window if time_window > 0 else 0
        
        metric = PerformanceMetric(
            timestamp=datetime.utcnow(),
            metric_type=MetricType.THROUGHPUT,
            component=component,
            value=throughput,
            metadata={
                "operations_count": operations_count,
                "time_window": time_window
            }
        )
        
        self.metrics.append(metric)
    
    def record_resource_usage(
        self, 
        cpu_percent: float, 
        memory_mb: float, 
        disk_mb: float = None, 
        network_kb: float = None
    ):
        """Record system resource usage"""
        current_time = datetime.utcnow()
        
        # Store in resource tracking
        self.resource_usage["cpu_usage"].append((current_time, cpu_percent))
        self.resource_usage["memory_usage"].append((current_time, memory_mb))
        
        if disk_mb is not None:
            self.resource_usage["disk_usage"].append((current_time, disk_mb))
        
        if network_kb is not None:
            self.resource_usage["network_usage"].append((current_time, network_kb))
        
        # Record as metrics
        for resource_type, value in [
            ("cpu", cpu_percent),
            ("memory", memory_mb),
            ("disk", disk_mb),
            ("network", network_kb)
        ]:
            if value is not None:
                metric = PerformanceMetric(
                    timestamp=current_time,
                    metric_type=MetricType.RESOURCE_USAGE,
                    component="system",
                    value=value,
                    metadata={"resource_type": resource_type}
                )
                self.metrics.append(metric)
    
    async def _collect_system_health(self):
        """Collect system health snapshot"""
        try:
            current_time = datetime.utcnow()
            
            # Calculate error rates
            recent_metrics = [
                m for m in self.metrics 
                if (current_time - m.timestamp).total_seconds() < 300  # Last 5 minutes
            ]
            
            error_metrics = [m for m in recent_metrics if m.metric_type == MetricType.ERROR_RATE]
            total_operations = len([m for m in recent_metrics if m.metric_type == MetricType.RESPONSE_TIME])
            
            error_rate = len(error_metrics) / max(total_operations, 1)
            
            # Calculate average response time
            response_times = [
                m.value for m in recent_metrics 
                if m.metric_type == MetricType.RESPONSE_TIME
            ]
            avg_response_time = statistics.mean(response_times) if response_times else 0.0
            
            # Count active users and conversations
            active_users = len([
                user_id for user_id, stats in self.user_activity.items()
                if stats["last_activity"] and 
                (current_time - stats["last_activity"]).total_seconds() < 1800  # 30 minutes
            ])
            
            active_conversations = len(self.active_operations)
            
            # Calculate overall health score (0-1)
            health_factors = []
            
            # Error rate factor (lower is better)
            health_factors.append(max(0, 1 - (error_rate * 2)))
            
            # Response time factor (lower is better, target < 2 seconds)
            health_factors.append(max(0, 1 - (avg_response_time / 5)))
            
            # Resource usage factor (if available)
            if self.resource_usage["cpu_usage"]:
                recent_cpu = [usage for _, usage in list(self.resource_usage["cpu_usage"])[-10:]]
                avg_cpu = statistics.mean(recent_cpu) if recent_cpu else 0
                health_factors.append(max(0, 1 - (avg_cpu / 100)))
            
            overall_health_score = statistics.mean(health_factors) if health_factors else 0.5
            
            # Create health snapshot
            snapshot = SystemHealthSnapshot(
                timestamp=current_time,
                ai_model_healthy=True,  # Would be updated by actual health checks
                rag_system_healthy=True,  # Would be updated by actual health checks
                memory_system_healthy=True,  # Would be updated by actual health checks
                discord_api_healthy=True,  # Would be updated by actual health checks
                overall_health_score=overall_health_score,
                active_users=active_users,
                active_conversations=active_conversations,
                error_rate=error_rate,
                avg_response_time=avg_response_time
            )
            
            self.health_snapshots.append(snapshot)
            
            # Record health metric
            metric = PerformanceMetric(
                timestamp=current_time,
                metric_type=MetricType.SYSTEM_HEALTH,
                component="system",
                value=overall_health_score,
                metadata={
                    "active_users": active_users,
                    "active_conversations": active_conversations,
                    "error_rate": error_rate,
                    "avg_response_time": avg_response_time
                }
            )
            
            self.metrics.append(metric)
            
        except Exception as e:
            logging.error(f"Error collecting system health: {e}")
    
    def get_performance_stats(self, time_window_hours: int = 1) -> Dict[str, Any]:
        """Get comprehensive performance statistics"""
        current_time = datetime.utcnow()
        cutoff_time = current_time - timedelta(hours=time_window_hours)
        
        # Filter recent metrics
        recent_metrics = [
            m for m in self.metrics 
            if m.timestamp >= cutoff_time
        ]
        
        # Group metrics by type and component
        stats = {
            "time_window_hours": time_window_hours,
            "total_metrics": len(recent_metrics),
            "components": {},
            "overall": {
                "avg_response_time": 0.0,
                "error_rate": 0.0,
                "throughput": 0.0,
                "active_users": 0,
                "user_engagement_score": 0.0
            }
        }
        
        # Component-specific statistics
        for component, component_stats in self.component_stats.items():
            if component_stats["total_operations"] > 0:
                avg_response_time = component_stats["total_time"] / component_stats["total_operations"]
                error_rate = component_stats["error_count"] / component_stats["total_operations"]
                
                stats["components"][component] = {
                    "total_operations": component_stats["total_operations"],
                    "avg_response_time": avg_response_time,
                    "error_rate": error_rate,
                    "error_count": component_stats["error_count"],
                    "last_operation": component_stats["last_operation"].isoformat() if component_stats["last_operation"] else None
                }
        
        # Overall statistics
        response_time_metrics = [m for m in recent_metrics if m.metric_type == MetricType.RESPONSE_TIME]
        if response_time_metrics:
            stats["overall"]["avg_response_time"] = statistics.mean([m.value for m in response_time_metrics])
        
        error_metrics = [m for m in recent_metrics if m.metric_type == MetricType.ERROR_RATE]
        total_operations = len(response_time_metrics)
        if total_operations > 0:
            stats["overall"]["error_rate"] = len(error_metrics) / total_operations
        
        # User engagement statistics
        active_users = len([
            user_id for user_id, user_stats in self.user_activity.items()
            if user_stats["last_activity"] and 
            (current_time - user_stats["last_activity"]).total_seconds() < time_window_hours * 3600
        ])
        
        stats["overall"]["active_users"] = active_users
        
        if self.user_activity:
            satisfaction_scores = [
                user_stats["avg_response_satisfaction"] 
                for user_stats in self.user_activity.values()
                if user_stats["avg_response_satisfaction"] > 0
            ]
            if satisfaction_scores:
                stats["overall"]["user_engagement_score"] = statistics.mean(satisfaction_scores)
        
        return stats
    
    def get_system_health_report(self) -> Dict[str, Any]:
        """Get current system health report"""
        if not self.health_snapshots:
            return {"status": "no_data", "message": "No health data available"}
        
        latest_snapshot = self.health_snapshots[-1]
        
        # Determine overall status
        if latest_snapshot.overall_health_score >= 0.8:
            status = "healthy"
        elif latest_snapshot.overall_health_score >= 0.6:
            status = "degraded"
        elif latest_snapshot.overall_health_score >= 0.4:
            status = "unhealthy"
        else:
            status = "critical"
        
        return {
            "status": status,
            "overall_health_score": latest_snapshot.overall_health_score,
            "timestamp": latest_snapshot.timestamp.isoformat(),
            "components": {
                "ai_model": latest_snapshot.ai_model_healthy,
                "rag_system": latest_snapshot.rag_system_healthy,
                "memory_system": latest_snapshot.memory_system_healthy,
                "discord_api": latest_snapshot.discord_api_healthy
            },
            "metrics": {
                "active_users": latest_snapshot.active_users,
                "active_conversations": latest_snapshot.active_conversations,
                "error_rate": latest_snapshot.error_rate,
                "avg_response_time": latest_snapshot.avg_response_time
            },
            "resource_usage": self._get_current_resource_usage()
        }
    
    def _get_current_resource_usage(self) -> Dict[str, Any]:
        """Get current resource usage statistics"""
        usage = {}
        
        for resource_type, data in self.resource_usage.items():
            if data:
                recent_data = list(data)[-10:]  # Last 10 data points
                values = [value for _, value in recent_data]
                if values:
                    usage[resource_type] = {
                        "current": values[-1],
                        "average": statistics.mean(values),
                        "max": max(values),
                        "min": min(values)
                    }
        
        return usage
    
    def get_user_engagement_report(self) -> Dict[str, Any]:
        """Get user engagement statistics"""
        current_time = datetime.utcnow()
        
        # Active users (last 24 hours)
        active_users_24h = len([
            user_id for user_id, stats in self.user_activity.items()
            if stats["last_activity"] and 
            (current_time - stats["last_activity"]).total_seconds() < 86400
        ])
        
        # Active users (last hour)
        active_users_1h = len([
            user_id for user_id, stats in self.user_activity.items()
            if stats["last_activity"] and 
            (current_time - stats["last_activity"]).total_seconds() < 3600
        ])
        
        # Calculate engagement metrics
        total_messages = sum(stats["message_count"] for stats in self.user_activity.values())
        total_session_time = sum(stats["total_session_time"] for stats in self.user_activity.values())
        
        satisfaction_scores = [
            stats["avg_response_satisfaction"] 
            for stats in self.user_activity.values()
            if stats["avg_response_satisfaction"] > 0
        ]
        
        return {
            "active_users_24h": active_users_24h,
            "active_users_1h": active_users_1h,
            "total_users": len(self.user_activity),
            "total_messages": total_messages,
            "total_session_time_hours": total_session_time / 3600,
            "avg_satisfaction_score": statistics.mean(satisfaction_scores) if satisfaction_scores else 0.0,
            "satisfaction_ratings_count": len(satisfaction_scores)
        }
    
    async def save_metrics_to_disk(self):
        """Save metrics to disk for persistence"""
        try:
            # Prepare metrics data
            metrics_data = []
            for metric in list(self.metrics):
                metrics_data.append({
                    "timestamp": metric.timestamp.isoformat(),
                    "metric_type": metric.metric_type.value,
                    "component": metric.component,
                    "value": metric.value,
                    "metadata": metric.metadata
                })
            
            # Save metrics
            with open(self.metrics_file, 'w') as f:
                json.dump(metrics_data, f, indent=2)
            
            # Prepare health data
            health_data = []
            for snapshot in list(self.health_snapshots):
                health_data.append({
                    "timestamp": snapshot.timestamp.isoformat(),
                    "ai_model_healthy": snapshot.ai_model_healthy,
                    "rag_system_healthy": snapshot.rag_system_healthy,
                    "memory_system_healthy": snapshot.memory_system_healthy,
                    "discord_api_healthy": snapshot.discord_api_healthy,
                    "overall_health_score": snapshot.overall_health_score,
                    "active_users": snapshot.active_users,
                    "active_conversations": snapshot.active_conversations,
                    "error_rate": snapshot.error_rate,
                    "avg_response_time": snapshot.avg_response_time
                })
            
            # Save health data
            with open(self.health_file, 'w') as f:
                json.dump(health_data, f, indent=2)
            
            logging.info(f"Saved {len(metrics_data)} metrics and {len(health_data)} health snapshots")
            
        except Exception as e:
            logging.error(f"Error saving metrics to disk: {e}")
    
    def _cleanup_old_metrics(self):
        """Clean up old metrics to prevent memory bloat"""
        current_time = datetime.utcnow()
        cutoff_time = current_time - timedelta(hours=self.metric_retention_hours)
        
        # Clean up metrics
        original_count = len(self.metrics)
        self.metrics = deque([
            m for m in self.metrics if m.timestamp >= cutoff_time
        ], maxlen=self.metrics.maxlen)
        
        # Clean up health snapshots
        original_health_count = len(self.health_snapshots)
        self.health_snapshots = deque([
            s for s in self.health_snapshots if s.timestamp >= cutoff_time
        ], maxlen=self.health_snapshots.maxlen)
        
        cleaned_metrics = original_count - len(self.metrics)
        cleaned_health = original_health_count - len(self.health_snapshots)
        
        if cleaned_metrics > 0 or cleaned_health > 0:
            logging.info(f"Cleaned up {cleaned_metrics} old metrics and {cleaned_health} old health snapshots")
    
    def update_component_health(self, component: str, is_healthy: bool):
        """Update component health status"""
        if self.health_snapshots:
            latest_snapshot = self.health_snapshots[-1]
            
            # Update component health in the latest snapshot
            if component == "ai_model":
                latest_snapshot.ai_model_healthy = is_healthy
            elif component == "rag_system":
                latest_snapshot.rag_system_healthy = is_healthy
            elif component == "memory_system":
                latest_snapshot.memory_system_healthy = is_healthy
            elif component == "discord_api":
                latest_snapshot.discord_api_healthy = is_healthy
            
            # Recalculate overall health score
            health_components = [
                latest_snapshot.ai_model_healthy,
                latest_snapshot.rag_system_healthy,
                latest_snapshot.memory_system_healthy,
                latest_snapshot.discord_api_healthy
            ]
            
            healthy_count = sum(health_components)
            latest_snapshot.overall_health_score = healthy_count / len(health_components)
    
    async def shutdown(self):
        """Shutdown performance monitor and cleanup"""
        try:
            # Cancel background tasks
            for task in self._background_tasks:
                task.cancel()
            
            # Wait for tasks to complete
            if self._background_tasks:
                await asyncio.gather(*self._background_tasks, return_exceptions=True)
            
            # Save final metrics
            await self.save_metrics_to_disk()
            
            logging.info("Performance monitor shutdown complete")
            
        except Exception as e:
            logging.error(f"Error during performance monitor shutdown: {e}")


# Context manager for operation tracking
class OperationTracker:
    """Context manager for tracking operation performance"""
    
    def __init__(self, monitor: PerformanceMonitor, operation_id: str, component: str, metadata: Dict[str, Any] = None):
        self.monitor = monitor
        self.operation_id = operation_id
        self.component = component
        self.metadata = metadata or {}
        self.tracking_id = None
        self.success = True
    
    def __enter__(self):
        self.tracking_id = self.monitor.start_operation(
            self.operation_id, 
            self.component, 
            self.metadata
        )
        return self
    
    def __exit__(self, exc_type, exc_val, exc_tb):
        if exc_type is not None:
            self.success = False
            self.metadata["error_type"] = exc_type.__name__
            self.metadata["error_message"] = str(exc_val)
        
        if self.tracking_id:
            duration = self.monitor.end_operation(
                self.tracking_id, 
                self.success, 
                self.metadata
            )
            return False  # Don't suppress exceptions
    
    async def __aenter__(self):
        return self.__enter__()
    
    async def __aexit__(self, exc_type, exc_val, exc_tb):
        return self.__exit__(exc_type, exc_val, exc_tb)


# Decorator for automatic performance tracking
def track_performance(component: str, operation_id: str = None):
    """Decorator for automatic performance tracking"""
    def decorator(func):
        async def async_wrapper(*args, **kwargs):
            # Try to get monitor from first argument (self)
            monitor = None
            if args and hasattr(args[0], 'performance_monitor'):
                monitor = args[0].performance_monitor
            
            if monitor:
                op_id = operation_id or func.__name__
                async with OperationTracker(monitor, op_id, component):
                    return await func(*args, **kwargs)
            else:
                return await func(*args, **kwargs)
        
        def sync_wrapper(*args, **kwargs):
            # Try to get monitor from first argument (self)
            monitor = None
            if args and hasattr(args[0], 'performance_monitor'):
                monitor = args[0].performance_monitor
            
            if monitor:
                op_id = operation_id or func.__name__
                with OperationTracker(monitor, op_id, component):
                    return func(*args, **kwargs)
            else:
                return func(*args, **kwargs)
        
        # Return appropriate wrapper based on function type
        if asyncio.iscoroutinefunction(func):
            return async_wrapper
        else:
            return sync_wrapper
    
    return decorator