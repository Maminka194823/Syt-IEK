"""
V4 Resource Manager
System resource monitoring and graceful degradation management
Monitors CPU, memory, disk usage and implements degradation strategies
"""

import psutil
import asyncio
import logging
from typing import Dict, Any, List, Optional, Callable
from datetime import datetime, timedelta
from dataclasses import dataclass
from enum import Enum
import json
import os


class ResourceType(Enum):
    """Types of system resources being monitored"""
    CPU = "cpu"
    MEMORY = "memory"
    DISK = "disk"
    NETWORK = "network"


class DegradationLevel(Enum):
    """Levels of system degradation"""
    NORMAL = 0
    LIGHT = 1
    MODERATE = 2
    SEVERE = 3
    CRITICAL = 4
    
    def __str__(self):
        """String representation for logging and display"""
        return {
            0: "normal",
            1: "light", 
            2: "moderate",
            3: "severe",
            4: "critical"
        }[self.value]


@dataclass
class ResourceThreshold:
    """Resource usage thresholds for degradation levels"""
    warning: float  # Start monitoring more closely
    light: float    # Light degradation
    moderate: float # Moderate degradation
    severe: float   # Severe degradation
    critical: float # Critical degradation


@dataclass
class ResourceUsage:
    """Current resource usage snapshot"""
    timestamp: datetime
    cpu_percent: float
    memory_percent: float
    memory_mb: float
    disk_percent: float
    disk_mb: float
    network_io_mb: float
    active_connections: int


@dataclass
class DegradationAction:
    """Action to take during resource degradation"""
    level: DegradationLevel
    resource_type: ResourceType
    action_name: str
    description: str
    enabled: bool = True


class ResourceManager:
    """
    System resource monitoring and graceful degradation manager
    Monitors system resources and implements degradation strategies
    """
    
    def __init__(self, performance_monitor=None):
        self.performance_monitor = performance_monitor
        
        # Resource monitoring
        self.current_usage = None
        self.usage_history = []
        self.max_history_size = 1000
        
        # Resource thresholds (percentages)
        self.thresholds = {
            ResourceType.CPU: ResourceThreshold(
                warning=60.0,
                light=70.0,
                moderate=80.0,
                severe=90.0,
                critical=95.0
            ),
            ResourceType.MEMORY: ResourceThreshold(
                warning=70.0,
                light=80.0,
                moderate=85.0,
                severe=90.0,
                critical=95.0
            ),
            ResourceType.DISK: ResourceThreshold(
                warning=80.0,
                light=85.0,
                moderate=90.0,
                severe=95.0,
                critical=98.0
            ),
            ResourceType.NETWORK: ResourceThreshold(
                warning=50.0,  # MB/s
                light=75.0,
                moderate=100.0,
                severe=150.0,
                critical=200.0
            )
        }
        
        # Current degradation state
        self.current_degradation = DegradationLevel.NORMAL
        self.degradation_reasons = []
        self.degradation_start_time = None
        
        # Degradation actions
        self.degradation_actions = self._setup_degradation_actions()
        
        # Active degradation measures
        self.active_measures = set()
        
        # Configuration
        self.monitoring_interval = 10  # seconds
        self.degradation_cooldown = 60  # seconds before upgrading degradation level
        self.recovery_cooldown = 120   # seconds before reducing degradation level
        
        # Background monitoring
        self._monitoring_task = None
        self._last_degradation_change = datetime.utcnow()
        
        # Callbacks for degradation events
        self.degradation_callbacks = []
        
        # Start monitoring
        self.start_monitoring()
    
    async def initialize(self):
        """
        Initialize resource manager (async placeholder for compatibility)
        The actual initialization is done in __init__
        """
        # Nothing to do here - initialization is synchronous and done in __init__
        pass
    
    def _setup_degradation_actions(self) -> List[DegradationAction]:
        """Setup available degradation actions"""
        return [
            # Light degradation actions
            DegradationAction(
                DegradationLevel.LIGHT,
                ResourceType.CPU,
                "reduce_ai_concurrency",
                "Reduce concurrent AI processing to 1 request at a time"
            ),
            DegradationAction(
                DegradationLevel.LIGHT,
                ResourceType.MEMORY,
                "clear_caches",
                "Clear non-essential caches and temporary data"
            ),
            DegradationAction(
                DegradationLevel.LIGHT,
                ResourceType.DISK,
                "cleanup_logs",
                "Clean up old log files and temporary data"
            ),
            
            # Moderate degradation actions
            DegradationAction(
                DegradationLevel.MODERATE,
                ResourceType.CPU,
                "disable_background_tasks",
                "Disable non-essential background processing"
            ),
            DegradationAction(
                DegradationLevel.MODERATE,
                ResourceType.MEMORY,
                "reduce_context_size",
                "Reduce conversation context and knowledge retrieval size"
            ),
            DegradationAction(
                DegradationLevel.MODERATE,
                ResourceType.DISK,
                "disable_metrics_storage",
                "Disable detailed metrics storage to disk"
            ),
            
            # Severe degradation actions
            DegradationAction(
                DegradationLevel.SEVERE,
                ResourceType.CPU,
                "basic_responses_only",
                "Switch to basic response mode without AI processing"
            ),
            DegradationAction(
                DegradationLevel.SEVERE,
                ResourceType.MEMORY,
                "minimal_memory_mode",
                "Use minimal memory footprint, disable advanced features"
            ),
            DegradationAction(
                DegradationLevel.SEVERE,
                ResourceType.DISK,
                "memory_only_mode",
                "Operate entirely in memory without disk writes"
            ),
            
            # Critical degradation actions
            DegradationAction(
                DegradationLevel.CRITICAL,
                ResourceType.CPU,
                "emergency_mode",
                "Emergency mode: minimal functionality only"
            ),
            DegradationAction(
                DegradationLevel.CRITICAL,
                ResourceType.MEMORY,
                "emergency_mode",
                "Emergency mode: minimal functionality only"
            ),
            DegradationAction(
                DegradationLevel.CRITICAL,
                ResourceType.DISK,
                "emergency_mode",
                "Emergency mode: minimal functionality only"
            )
        ]
    
    def start_monitoring(self):
        """Start background resource monitoring"""
        if self._monitoring_task is None or self._monitoring_task.done():
            try:
                loop = asyncio.get_running_loop()
                self._monitoring_task = loop.create_task(self._monitoring_loop())
            except RuntimeError:
                # No event loop running
                logging.info("No event loop running, resource monitoring will be manual")
    
    async def _monitoring_loop(self):
        """Background monitoring loop"""
        while True:
            try:
                await asyncio.sleep(self.monitoring_interval)
                await self.update_resource_usage()
                await self._evaluate_degradation()
            except asyncio.CancelledError:
                break
            except Exception as e:
                logging.error(f"Error in resource monitoring loop: {e}")
    
    async def update_resource_usage(self) -> ResourceUsage:
        """Update current resource usage"""
        try:
            # Get CPU usage
            cpu_percent = psutil.cpu_percent(interval=1)
            
            # Get memory usage
            memory = psutil.virtual_memory()
            memory_percent = memory.percent
            memory_mb = memory.used / (1024 * 1024)
            
            # Get disk usage
            disk = psutil.disk_usage('/')
            disk_percent = (disk.used / disk.total) * 100
            disk_mb = disk.used / (1024 * 1024)
            
            # Get network I/O
            network = psutil.net_io_counters()
            network_io_mb = (network.bytes_sent + network.bytes_recv) / (1024 * 1024)
            
            # Get active connections (approximate)
            try:
                connections = len(psutil.net_connections())
            except (psutil.AccessDenied, psutil.NoSuchProcess):
                connections = 0
            
            # Create usage snapshot
            usage = ResourceUsage(
                timestamp=datetime.utcnow(),
                cpu_percent=cpu_percent,
                memory_percent=memory_percent,
                memory_mb=memory_mb,
                disk_percent=disk_percent,
                disk_mb=disk_mb,
                network_io_mb=network_io_mb,
                active_connections=connections
            )
            
            self.current_usage = usage
            
            # Add to history
            self.usage_history.append(usage)
            if len(self.usage_history) > self.max_history_size:
                self.usage_history.pop(0)
            
            # Report to performance monitor if available
            if self.performance_monitor:
                self.performance_monitor.record_resource_usage(
                    cpu_percent,
                    memory_mb,
                    disk_mb,
                    network_io_mb / 1024  # Convert to KB for consistency
                )
            
            return usage
            
        except Exception as e:
            logging.error(f"Error updating resource usage: {e}")
            return self.current_usage
    
    async def _evaluate_degradation(self):
        """Evaluate if degradation level should change"""
        if not self.current_usage:
            return
        
        current_time = datetime.utcnow()
        
        # Calculate required degradation level based on current usage
        required_level = self._calculate_required_degradation_level()
        
        # Check if we need to change degradation level
        if required_level != self.current_degradation:
            # Check cooldown periods
            time_since_change = (current_time - self._last_degradation_change).total_seconds()
            
            # If upgrading degradation (worse performance)
            if required_level.value > self.current_degradation.value:
                if time_since_change >= self.degradation_cooldown:
                    await self._change_degradation_level(required_level)
            
            # If downgrading degradation (better performance)
            elif required_level.value < self.current_degradation.value:
                if time_since_change >= self.recovery_cooldown:
                    await self._change_degradation_level(required_level)
    
    def _calculate_required_degradation_level(self) -> DegradationLevel:
        """Calculate the required degradation level based on current resource usage"""
        if not self.current_usage:
            return DegradationLevel.NORMAL
        
        max_level = DegradationLevel.NORMAL
        
        # Check each resource type
        for resource_type, threshold in self.thresholds.items():
            current_value = self._get_current_resource_value(resource_type)
            
            if current_value >= threshold.critical:
                max_level = max(max_level, DegradationLevel.CRITICAL, key=lambda x: x.value)
            elif current_value >= threshold.severe:
                max_level = max(max_level, DegradationLevel.SEVERE, key=lambda x: x.value)
            elif current_value >= threshold.moderate:
                max_level = max(max_level, DegradationLevel.MODERATE, key=lambda x: x.value)
            elif current_value >= threshold.light:
                max_level = max(max_level, DegradationLevel.LIGHT, key=lambda x: x.value)
        
        return max_level
    
    def _get_current_resource_value(self, resource_type: ResourceType) -> float:
        """Get current value for a specific resource type"""
        if not self.current_usage:
            return 0.0
        
        if resource_type == ResourceType.CPU:
            return self.current_usage.cpu_percent
        elif resource_type == ResourceType.MEMORY:
            return self.current_usage.memory_percent
        elif resource_type == ResourceType.DISK:
            return self.current_usage.disk_percent
        elif resource_type == ResourceType.NETWORK:
            return self.current_usage.network_io_mb
        
        return 0.0
    
    async def _change_degradation_level(self, new_level: DegradationLevel):
        """Change the current degradation level"""
        old_level = self.current_degradation
        self.current_degradation = new_level
        self._last_degradation_change = datetime.utcnow()
        
        if new_level != DegradationLevel.NORMAL and self.degradation_start_time is None:
            self.degradation_start_time = datetime.utcnow()
        elif new_level == DegradationLevel.NORMAL:
            self.degradation_start_time = None
        
        # Update degradation reasons
        self._update_degradation_reasons()
        
        # Apply degradation actions
        await self._apply_degradation_actions(old_level, new_level)
        
        # Notify callbacks
        await self._notify_degradation_callbacks(old_level, new_level)
        
        # Log the change
        logging.warning(f"Degradation level changed from {str(old_level)} to {str(new_level)}")
        if self.degradation_reasons:
            logging.warning(f"Degradation reasons: {', '.join(self.degradation_reasons)}")
    
    def _update_degradation_reasons(self):
        """Update the list of reasons for current degradation"""
        self.degradation_reasons = []
        
        if not self.current_usage:
            return
        
        for resource_type, threshold in self.thresholds.items():
            current_value = self._get_current_resource_value(resource_type)
            
            if current_value >= threshold.critical:
                self.degradation_reasons.append(f"{resource_type.value} usage critical ({current_value:.1f}%)")
            elif current_value >= threshold.severe:
                self.degradation_reasons.append(f"{resource_type.value} usage severe ({current_value:.1f}%)")
            elif current_value >= threshold.moderate:
                self.degradation_reasons.append(f"{resource_type.value} usage moderate ({current_value:.1f}%)")
            elif current_value >= threshold.light:
                self.degradation_reasons.append(f"{resource_type.value} usage elevated ({current_value:.1f}%)")
    
    async def _apply_degradation_actions(self, old_level: DegradationLevel, new_level: DegradationLevel):
        """Apply appropriate degradation actions"""
        # If degradation is getting worse, apply new actions
        if new_level.value > old_level.value:
            actions_to_apply = [
                action for action in self.degradation_actions
                if action.level == new_level and action.enabled
            ]
            
            for action in actions_to_apply:
                await self._execute_degradation_action(action, True)
        
        # If degradation is getting better, remove some actions
        elif new_level.value < old_level.value:
            actions_to_remove = [
                action for action in self.degradation_actions
                if action.level.value > new_level.value and action.action_name in self.active_measures
            ]
            
            for action in actions_to_remove:
                await self._execute_degradation_action(action, False)
    
    async def _execute_degradation_action(self, action: DegradationAction, enable: bool):
        """Execute a specific degradation action"""
        try:
            if enable:
                logging.info(f"Applying degradation action: {action.description}")
                self.active_measures.add(action.action_name)
                
                # Execute specific actions
                if action.action_name == "reduce_ai_concurrency":
                    await self._reduce_ai_concurrency()
                elif action.action_name == "clear_caches":
                    await self._clear_caches()
                elif action.action_name == "cleanup_logs":
                    await self._cleanup_logs()
                elif action.action_name == "disable_background_tasks":
                    await self._disable_background_tasks()
                elif action.action_name == "reduce_context_size":
                    await self._reduce_context_size()
                elif action.action_name == "disable_metrics_storage":
                    await self._disable_metrics_storage()
                elif action.action_name == "basic_responses_only":
                    await self._enable_basic_responses_only()
                elif action.action_name == "minimal_memory_mode":
                    await self._enable_minimal_memory_mode()
                elif action.action_name == "memory_only_mode":
                    await self._enable_memory_only_mode()
                elif action.action_name == "emergency_mode":
                    await self._enable_emergency_mode()
            
            else:
                logging.info(f"Removing degradation action: {action.description}")
                self.active_measures.discard(action.action_name)
                
                # Reverse specific actions
                if action.action_name == "reduce_ai_concurrency":
                    await self._restore_ai_concurrency()
                elif action.action_name == "disable_background_tasks":
                    await self._enable_background_tasks()
                elif action.action_name == "reduce_context_size":
                    await self._restore_context_size()
                elif action.action_name == "disable_metrics_storage":
                    await self._enable_metrics_storage()
                elif action.action_name == "basic_responses_only":
                    await self._disable_basic_responses_only()
                elif action.action_name == "minimal_memory_mode":
                    await self._disable_minimal_memory_mode()
                elif action.action_name == "memory_only_mode":
                    await self._disable_memory_only_mode()
                elif action.action_name == "emergency_mode":
                    await self._disable_emergency_mode()
        
        except Exception as e:
            logging.error(f"Error executing degradation action {action.action_name}: {e}")
    
    # Degradation action implementations
    
    async def _reduce_ai_concurrency(self):
        """Reduce AI processing concurrency"""
        # This would be implemented by the message handler
        pass
    
    async def _restore_ai_concurrency(self):
        """Restore normal AI processing concurrency"""
        pass
    
    async def _clear_caches(self):
        """Clear non-essential caches"""
        # This would clear various system caches
        import gc
        gc.collect()
    
    async def _cleanup_logs(self):
        """Clean up old log files"""
        # This would clean up old log files
        pass
    
    async def _disable_background_tasks(self):
        """Disable non-essential background tasks"""
        pass
    
    async def _enable_background_tasks(self):
        """Re-enable background tasks"""
        pass
    
    async def _reduce_context_size(self):
        """Reduce conversation context size"""
        pass
    
    async def _restore_context_size(self):
        """Restore normal context size"""
        pass
    
    async def _disable_metrics_storage(self):
        """Disable detailed metrics storage"""
        pass
    
    async def _enable_metrics_storage(self):
        """Re-enable metrics storage"""
        pass
    
    async def _enable_basic_responses_only(self):
        """Enable basic response mode"""
        pass
    
    async def _disable_basic_responses_only(self):
        """Disable basic response mode"""
        pass
    
    async def _enable_minimal_memory_mode(self):
        """Enable minimal memory mode"""
        pass
    
    async def _disable_minimal_memory_mode(self):
        """Disable minimal memory mode"""
        pass
    
    async def _enable_memory_only_mode(self):
        """Enable memory-only mode"""
        pass
    
    async def _disable_memory_only_mode(self):
        """Disable memory-only mode"""
        pass
    
    async def _enable_emergency_mode(self):
        """Enable emergency mode"""
        pass
    
    async def _disable_emergency_mode(self):
        """Disable emergency mode"""
        pass
    
    async def _notify_degradation_callbacks(self, old_level: DegradationLevel, new_level: DegradationLevel):
        """Notify registered callbacks about degradation changes"""
        for callback in self.degradation_callbacks:
            try:
                if asyncio.iscoroutinefunction(callback):
                    await callback(old_level, new_level, self.degradation_reasons)
                else:
                    callback(old_level, new_level, self.degradation_reasons)
            except Exception as e:
                logging.error(f"Error in degradation callback: {e}")
    
    def register_degradation_callback(self, callback: Callable):
        """Register a callback for degradation level changes"""
        self.degradation_callbacks.append(callback)
    
    def get_resource_status(self) -> Dict[str, Any]:
        """Get current resource status"""
        if not self.current_usage:
            return {"status": "no_data"}
        
        return {
            "timestamp": self.current_usage.timestamp.isoformat(),
            "degradation_level": str(self.current_degradation),
            "degradation_reasons": self.degradation_reasons,
            "degradation_duration": (
                (datetime.utcnow() - self.degradation_start_time).total_seconds()
                if self.degradation_start_time else 0
            ),
            "active_measures": list(self.active_measures),
            "resource_usage": {
                "cpu_percent": self.current_usage.cpu_percent,
                "memory_percent": self.current_usage.memory_percent,
                "memory_mb": self.current_usage.memory_mb,
                "disk_percent": self.current_usage.disk_percent,
                "disk_mb": self.current_usage.disk_mb,
                "network_io_mb": self.current_usage.network_io_mb,
                "active_connections": self.current_usage.active_connections
            },
            "thresholds": {
                resource_type.value: {
                    "warning": threshold.warning,
                    "light": threshold.light,
                    "moderate": threshold.moderate,
                    "severe": threshold.severe,
                    "critical": threshold.critical
                }
                for resource_type, threshold in self.thresholds.items()
            }
        }
    
    def get_usage_history(self, hours: int = 1) -> List[Dict[str, Any]]:
        """Get resource usage history"""
        cutoff_time = datetime.utcnow() - timedelta(hours=hours)
        
        recent_usage = [
            usage for usage in self.usage_history
            if usage.timestamp >= cutoff_time
        ]
        
        return [
            {
                "timestamp": usage.timestamp.isoformat(),
                "cpu_percent": usage.cpu_percent,
                "memory_percent": usage.memory_percent,
                "memory_mb": usage.memory_mb,
                "disk_percent": usage.disk_percent,
                "disk_mb": usage.disk_mb,
                "network_io_mb": usage.network_io_mb,
                "active_connections": usage.active_connections
            }
            for usage in recent_usage
        ]
    
    def is_degraded(self) -> bool:
        """Check if system is currently degraded"""
        return self.current_degradation != DegradationLevel.NORMAL
    
    def get_degradation_level(self) -> DegradationLevel:
        """Get current degradation level"""
        return self.current_degradation
    
    def get_user_notification_message(self) -> Optional[str]:
        """Get user-friendly notification message about current degradation"""
        if self.current_degradation == DegradationLevel.NORMAL:
            return None
        
        messages = {
            DegradationLevel.LIGHT: "I'm experiencing slightly higher system load. Response times may be a bit slower than usual.",
            DegradationLevel.MODERATE: "I'm currently under moderate system load. Some advanced features may be temporarily limited.",
            DegradationLevel.SEVERE: "I'm experiencing high system load. I'm operating in basic mode to maintain stability.",
            DegradationLevel.CRITICAL: "I'm currently in emergency mode due to critical system load. Only essential functions are available."
        }
        
        base_message = messages.get(self.current_degradation, "I'm experiencing system issues.")
        
        if self.degradation_reasons:
            reason_summary = "This is due to high " + ", ".join([
                reason.split()[0] for reason in self.degradation_reasons[:2]
            ]) + " usage."
            return f"{base_message} {reason_summary}"
        
        return base_message
    
    async def force_degradation_level(self, level: DegradationLevel, reason: str = "Manual override"):
        """Force a specific degradation level (for testing or manual control)"""
        old_level = self.current_degradation
        self.current_degradation = level
        self.degradation_reasons = [reason]
        self._last_degradation_change = datetime.utcnow()
        
        if level != DegradationLevel.NORMAL and self.degradation_start_time is None:
            self.degradation_start_time = datetime.utcnow()
        elif level == DegradationLevel.NORMAL:
            self.degradation_start_time = None
        
        await self._apply_degradation_actions(old_level, level)
        await self._notify_degradation_callbacks(old_level, level)
        
        logging.info(f"Forced degradation level to {str(level)}: {reason}")
    
    async def shutdown(self):
        """Shutdown resource manager"""
        if self._monitoring_task and not self._monitoring_task.done():
            self._monitoring_task.cancel()
            try:
                await self._monitoring_task
            except asyncio.CancelledError:
                pass
        
        # Reset to normal operation
        if self.current_degradation != DegradationLevel.NORMAL:
            await self._change_degradation_level(DegradationLevel.NORMAL)
        
        logging.info("Resource manager shutdown complete")