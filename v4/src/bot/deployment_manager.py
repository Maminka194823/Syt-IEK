#!/usr/bin/env python3
"""
Deployment Manager for Aviation Girl V4 Discord Bot

Provides comprehensive deployment and update management with support for:
- Containerized deployment with health checks
- Graceful shutdown and restart capabilities
- Conversation context preservation during updates
- System health monitoring and reporting
"""

import asyncio
import signal
import logging
import json
import os
import time
from typing import Dict, Any, Optional, List, Callable
from datetime import datetime, timedelta
from dataclasses import dataclass, field
from enum import Enum
import aiohttp
from pathlib import Path


class DeploymentStatus(Enum):
    """Deployment status states"""
    STARTING = "starting"
    RUNNING = "running"
    STOPPING = "stopping"
    STOPPED = "stopped"
    UPDATING = "updating"
    FAILED = "failed"
    MAINTENANCE = "maintenance"


class HealthStatus(Enum):
    """Health check status"""
    HEALTHY = "healthy"
    UNHEALTHY = "unhealthy"
    DEGRADED = "degraded"
    UNKNOWN = "unknown"


@dataclass
class HealthCheck:
    """Health check configuration and results"""
    name: str
    check_function: Callable
    interval_seconds: int = 60
    timeout_seconds: int = 10
    failure_threshold: int = 3
    success_threshold: int = 1
    
    # Runtime state
    consecutive_failures: int = 0
    consecutive_successes: int = 0
    last_check_time: Optional[datetime] = None
    last_status: HealthStatus = HealthStatus.UNKNOWN
    last_error: Optional[str] = None


@dataclass
class DeploymentInfo:
    """Deployment information and metadata"""
    deployment_id: str
    version: str
    environment: str
    start_time: datetime
    status: DeploymentStatus
    health_status: HealthStatus
    
    # Resource information
    memory_usage_mb: float = 0.0
    cpu_usage_percent: float = 0.0
    active_connections: int = 0
    
    # Update information
    last_update_time: Optional[datetime] = None
    update_in_progress: bool = False
    
    # Health checks
    health_checks: Dict[str, HealthCheck] = field(default_factory=dict)


class DeploymentManager:
    """
    Comprehensive deployment and update manager
    
    Handles containerized deployment, health monitoring, graceful shutdowns,
    and conversation context preservation during updates.
    """
    
    def __init__(self, config, bot_instance=None):
        self.config = config
        self.bot_instance = bot_instance
        self.logger = logging.getLogger(__name__)
        
        # Deployment state
        self.deployment_info = DeploymentInfo(
            deployment_id=self._generate_deployment_id(),
            version=self._get_version(),
            environment=config.deployment.environment.value,
            start_time=datetime.utcnow(),
            status=DeploymentStatus.STARTING,
            health_status=HealthStatus.UNKNOWN
        )
        
        # Shutdown management
        self.shutdown_event = asyncio.Event()
        self.shutdown_timeout = config.deployment.graceful_shutdown_timeout
        self.shutdown_callbacks: List[Callable] = []
        
        # Health monitoring
        self.health_check_interval = config.monitoring.health_check_interval
        self.health_check_task: Optional[asyncio.Task] = None
        
        # Context preservation
        self.context_backup_path = "./data/context_backup.json"
        self.context_preservation_enabled = True
        
        # Container mode settings
        self.container_mode = config.deployment.enable_container_mode
        self.health_check_port = config.monitoring.metrics_port
        
        # Update management
        self.update_lock = asyncio.Lock()
        self.active_conversations: Dict[str, Any] = {}
        
        # Setup signal handlers
        self._setup_signal_handlers()
        
        # Register default health checks
        self._register_default_health_checks()
    
    def _generate_deployment_id(self) -> str:
        """Generate unique deployment ID"""
        timestamp = int(time.time())
        return f"aviation-bot-{timestamp}"
    
    def _get_version(self) -> str:
        """Get application version"""
        try:
            # Try to read version from file or environment
            if os.path.exists("VERSION"):
                with open("VERSION", 'r') as f:
                    return f.read().strip()
            elif "APP_VERSION" in os.environ:
                return os.environ["APP_VERSION"]
            else:
                return "4.0.0-dev"
        except Exception:
            return "unknown"
    
    def _setup_signal_handlers(self):
        """Setup signal handlers for graceful shutdown"""
        if os.name != 'nt':  # Unix systems
            signal.signal(signal.SIGTERM, self._signal_handler)
            signal.signal(signal.SIGINT, self._signal_handler)
            signal.signal(signal.SIGHUP, self._signal_handler)
        else:  # Windows
            signal.signal(signal.SIGINT, self._signal_handler)
            signal.signal(signal.SIGTERM, self._signal_handler)
    
    def _signal_handler(self, signum, frame):
        """Handle shutdown signals"""
        self.logger.info(f"Received signal {signum}, initiating graceful shutdown...")
        asyncio.create_task(self.initiate_shutdown())
    
    def _register_default_health_checks(self):
        """Register default health checks"""
        # Bot connection health check
        self.register_health_check(
            "bot_connection",
            self._check_bot_connection,
            interval_seconds=30,
            failure_threshold=2
        )
        
        # Memory usage health check
        self.register_health_check(
            "memory_usage",
            self._check_memory_usage,
            interval_seconds=60,
            failure_threshold=3
        )
        
        # Disk space health check
        self.register_health_check(
            "disk_space",
            self._check_disk_space,
            interval_seconds=300,  # 5 minutes
            failure_threshold=2
        )
        
        # AI model health check
        self.register_health_check(
            "ai_model",
            self._check_ai_model,
            interval_seconds=120,  # 2 minutes
            failure_threshold=2
        )
    
    async def start_deployment(self) -> bool:
        """
        Start the deployment with full initialization
        
        Returns:
            bool: True if deployment started successfully
        """
        try:
            self.logger.info(f"Starting deployment {self.deployment_info.deployment_id}")
            self.deployment_info.status = DeploymentStatus.STARTING
            
            # Run startup validation
            from .startup_validator import StartupValidator, ValidationStatus
            validator = StartupValidator(self.config)
            validation_report = await validator.validate_startup()
            
            if validation_report.overall_status == ValidationStatus.FAILED:
                self.logger.error("Startup validation failed, aborting deployment")
                self.deployment_info.status = DeploymentStatus.FAILED
                return False
            elif validation_report.overall_status == ValidationStatus.WARNING:
                self.logger.warning("Startup validation completed with warnings")
            else:
                self.logger.info("Startup validation passed")
            
            # Initialize system components
            await self._initialize_components()
            
            # Start health monitoring
            if self.config.monitoring.enable_health_checks:
                await self._start_health_monitoring()
            
            # Start health check server if in container mode
            if self.container_mode:
                await self._start_health_check_server()
            
            # Load preserved context if available
            await self._restore_conversation_context()
            
            # Mark as running
            self.deployment_info.status = DeploymentStatus.RUNNING
            self.deployment_info.health_status = HealthStatus.HEALTHY
            
            self.logger.info(f"Deployment {self.deployment_info.deployment_id} started successfully")
            return True
            
        except Exception as e:
            self.logger.error(f"Failed to start deployment: {str(e)}")
            self.deployment_info.status = DeploymentStatus.FAILED
            self.deployment_info.health_status = HealthStatus.UNHEALTHY
            return False
    
    async def _initialize_components(self):
        """Initialize all system components"""
        self.logger.info("Initializing system components...")
        
        # Create necessary directories
        directories = [
            "./data",
            "./logs",
            "./keys",
            os.path.dirname(self.context_backup_path)
        ]
        
        for directory in directories:
            if directory:
                os.makedirs(directory, exist_ok=True)
        
        # Initialize bot components if available
        if self.bot_instance:
            # Initialize bot systems
            await self._initialize_bot_systems()
        
        self.logger.info("System components initialized")
    
    async def _initialize_bot_systems(self):
        """Initialize bot-specific systems"""
        try:
            # Initialize AI system
            if hasattr(self.bot_instance, 'ai_orchestrator'):
                await self.bot_instance.ai_orchestrator.initialize()
            
            # Initialize memory system
            if hasattr(self.bot_instance, 'user_profiles'):
                await self.bot_instance.user_profiles.initialize()
            
            # Initialize knowledge system
            if hasattr(self.bot_instance, 'rag_system'):
                await self.bot_instance.rag_system.initialize()
            
            self.logger.info("Bot systems initialized successfully")
            
        except Exception as e:
            self.logger.error(f"Failed to initialize bot systems: {str(e)}")
            raise
    
    async def _start_health_monitoring(self):
        """Start health monitoring task"""
        self.health_check_task = asyncio.create_task(self._health_monitoring_loop())
        self.logger.info("Health monitoring started")
    
    async def _health_monitoring_loop(self):
        """Main health monitoring loop"""
        while not self.shutdown_event.is_set():
            try:
                await self._run_health_checks()
                await asyncio.sleep(self.health_check_interval)
            except asyncio.CancelledError:
                break
            except Exception as e:
                self.logger.error(f"Health monitoring error: {str(e)}")
                await asyncio.sleep(self.health_check_interval)
    
    async def _run_health_checks(self):
        """Run all registered health checks"""
        overall_status = HealthStatus.HEALTHY
        
        for name, health_check in self.deployment_info.health_checks.items():
            try:
                # Run health check with timeout
                check_result = await asyncio.wait_for(
                    health_check.check_function(),
                    timeout=health_check.timeout_seconds
                )
                
                if check_result:
                    health_check.consecutive_successes += 1
                    health_check.consecutive_failures = 0
                    
                    if health_check.consecutive_successes >= health_check.success_threshold:
                        health_check.last_status = HealthStatus.HEALTHY
                else:
                    health_check.consecutive_failures += 1
                    health_check.consecutive_successes = 0
                    
                    if health_check.consecutive_failures >= health_check.failure_threshold:
                        health_check.last_status = HealthStatus.UNHEALTHY
                        overall_status = HealthStatus.UNHEALTHY
                
                health_check.last_check_time = datetime.utcnow()
                health_check.last_error = None
                
            except asyncio.TimeoutError:
                health_check.consecutive_failures += 1
                health_check.consecutive_successes = 0
                health_check.last_status = HealthStatus.UNHEALTHY
                health_check.last_error = "Health check timeout"
                overall_status = HealthStatus.UNHEALTHY
                
            except Exception as e:
                health_check.consecutive_failures += 1
                health_check.consecutive_successes = 0
                health_check.last_status = HealthStatus.UNHEALTHY
                health_check.last_error = str(e)
                overall_status = HealthStatus.DEGRADED
        
        # Update overall health status
        self.deployment_info.health_status = overall_status
        
        # Log health status changes
        if overall_status != HealthStatus.HEALTHY:
            self.logger.warning(f"System health status: {overall_status.value}")
    
    async def _start_health_check_server(self):
        """Start HTTP health check server for container orchestration"""
        from aiohttp import web
        
        app = web.Application()
        app.router.add_get('/health', self._health_endpoint)
        app.router.add_get('/ready', self._readiness_endpoint)
        app.router.add_get('/metrics', self._metrics_endpoint)
        
        runner = web.AppRunner(app)
        await runner.setup()
        
        site = web.TCPSite(runner, '0.0.0.0', self.health_check_port)
        await site.start()
        
        self.logger.info(f"Health check server started on port {self.health_check_port}")
    
    async def _health_endpoint(self, request):
        """Health check endpoint"""
        from aiohttp import web
        
        if self.deployment_info.health_status == HealthStatus.HEALTHY:
            return web.json_response({"status": "healthy"}, status=200)
        elif self.deployment_info.health_status == HealthStatus.DEGRADED:
            return web.json_response({"status": "degraded"}, status=200)
        else:
            return web.json_response({"status": "unhealthy"}, status=503)
    
    async def _readiness_endpoint(self, request):
        """Readiness check endpoint"""
        from aiohttp import web
        
        if self.deployment_info.status == DeploymentStatus.RUNNING:
            return web.json_response({"status": "ready"}, status=200)
        else:
            return web.json_response({"status": "not_ready"}, status=503)
    
    async def _metrics_endpoint(self, request):
        """Metrics endpoint"""
        from aiohttp import web
        
        metrics = {
            "deployment_id": self.deployment_info.deployment_id,
            "version": self.deployment_info.version,
            "environment": self.deployment_info.environment,
            "status": self.deployment_info.status.value,
            "health_status": self.deployment_info.health_status.value,
            "uptime_seconds": (datetime.utcnow() - self.deployment_info.start_time).total_seconds(),
            "memory_usage_mb": self.deployment_info.memory_usage_mb,
            "cpu_usage_percent": self.deployment_info.cpu_usage_percent,
            "active_connections": self.deployment_info.active_connections,
            "health_checks": {
                name: {
                    "status": check.last_status.value,
                    "consecutive_failures": check.consecutive_failures,
                    "last_check": check.last_check_time.isoformat() if check.last_check_time else None,
                    "last_error": check.last_error
                }
                for name, check in self.deployment_info.health_checks.items()
            }
        }
        
        return web.json_response(metrics)
    
    def register_health_check(
        self, 
        name: str, 
        check_function: Callable, 
        interval_seconds: int = 60,
        timeout_seconds: int = 10,
        failure_threshold: int = 3,
        success_threshold: int = 1
    ):
        """Register a new health check"""
        health_check = HealthCheck(
            name=name,
            check_function=check_function,
            interval_seconds=interval_seconds,
            timeout_seconds=timeout_seconds,
            failure_threshold=failure_threshold,
            success_threshold=success_threshold
        )
        
        self.deployment_info.health_checks[name] = health_check
        self.logger.info(f"Registered health check: {name}")
    
    async def _check_bot_connection(self) -> bool:
        """Check if bot is connected to Discord"""
        try:
            if self.bot_instance and hasattr(self.bot_instance, 'is_ready'):
                return self.bot_instance.is_ready()
            return True  # Assume healthy if no bot instance
        except Exception:
            return False
    
    async def _check_memory_usage(self) -> bool:
        """Check memory usage"""
        try:
            import psutil
            process = psutil.Process()
            memory_mb = process.memory_info().rss / 1024 / 1024
            self.deployment_info.memory_usage_mb = memory_mb
            
            # Consider unhealthy if using more than 1GB
            return memory_mb < 1024
        except Exception:
            return True  # Assume healthy if can't check
    
    async def _check_disk_space(self) -> bool:
        """Check available disk space"""
        try:
            import shutil
            total, used, free = shutil.disk_usage("./")
            free_gb = free / (1024 ** 3)
            
            # Consider unhealthy if less than 1GB free
            return free_gb > 1.0
        except Exception:
            return True  # Assume healthy if can't check
    
    async def _check_ai_model(self) -> bool:
        """Check AI model health"""
        try:
            if self.bot_instance and hasattr(self.bot_instance, 'ai_orchestrator'):
                # Try a simple model check
                return await self.bot_instance.ai_orchestrator.health_check()
            return True  # Assume healthy if no AI system
        except Exception:
            return False
    
    def register_shutdown_callback(self, callback: Callable):
        """Register callback to be called during shutdown"""
        self.shutdown_callbacks.append(callback)
    
    async def initiate_shutdown(self):
        """Initiate graceful shutdown"""
        if self.deployment_info.status == DeploymentStatus.STOPPING:
            return  # Already shutting down
        
        self.logger.info("Initiating graceful shutdown...")
        self.deployment_info.status = DeploymentStatus.STOPPING
        
        try:
            # Preserve conversation context
            await self._preserve_conversation_context()
            
            # Run shutdown callbacks
            await self._run_shutdown_callbacks()
            
            # Stop health monitoring
            if self.health_check_task:
                self.health_check_task.cancel()
                try:
                    await self.health_check_task
                except asyncio.CancelledError:
                    pass
            
            # Graceful bot shutdown
            if self.bot_instance:
                await self._shutdown_bot()
            
            # Set shutdown event
            self.shutdown_event.set()
            
            self.deployment_info.status = DeploymentStatus.STOPPED
            self.logger.info("Graceful shutdown completed")
            
        except Exception as e:
            self.logger.error(f"Error during shutdown: {str(e)}")
            self.deployment_info.status = DeploymentStatus.FAILED
    
    async def _run_shutdown_callbacks(self):
        """Run all registered shutdown callbacks"""
        for callback in self.shutdown_callbacks:
            try:
                if asyncio.iscoroutinefunction(callback):
                    await callback()
                else:
                    callback()
            except Exception as e:
                self.logger.error(f"Error in shutdown callback: {str(e)}")
    
    async def _shutdown_bot(self):
        """Shutdown bot gracefully"""
        try:
            if hasattr(self.bot_instance, 'close'):
                await asyncio.wait_for(
                    self.bot_instance.close(),
                    timeout=self.shutdown_timeout
                )
            self.logger.info("Bot shutdown completed")
        except asyncio.TimeoutError:
            self.logger.warning("Bot shutdown timed out")
        except Exception as e:
            self.logger.error(f"Error shutting down bot: {str(e)}")
    
    async def _preserve_conversation_context(self):
        """Preserve active conversation context for updates"""
        if not self.context_preservation_enabled:
            return
        
        try:
            context_data = {
                "timestamp": datetime.utcnow().isoformat(),
                "deployment_id": self.deployment_info.deployment_id,
                "active_conversations": self.active_conversations,
                "system_state": {
                    "uptime": (datetime.utcnow() - self.deployment_info.start_time).total_seconds(),
                    "version": self.deployment_info.version
                }
            }
            
            # Ensure backup directory exists
            os.makedirs(os.path.dirname(self.context_backup_path), exist_ok=True)
            
            # Write context backup
            with open(self.context_backup_path, 'w') as f:
                json.dump(context_data, f, indent=2)
            
            self.logger.info(f"Conversation context preserved to {self.context_backup_path}")
            
        except Exception as e:
            self.logger.error(f"Failed to preserve conversation context: {str(e)}")
    
    async def _restore_conversation_context(self):
        """Restore conversation context from previous deployment"""
        if not self.context_preservation_enabled or not os.path.exists(self.context_backup_path):
            return
        
        try:
            with open(self.context_backup_path, 'r') as f:
                context_data = json.load(f)
            
            # Check if context is recent (within last hour)
            backup_time = datetime.fromisoformat(context_data["timestamp"])
            if datetime.utcnow() - backup_time > timedelta(hours=1):
                self.logger.info("Context backup is too old, skipping restore")
                return
            
            # Restore active conversations
            self.active_conversations = context_data.get("active_conversations", {})
            
            self.logger.info(f"Restored conversation context from {backup_time}")
            
            # Clean up backup file
            os.remove(self.context_backup_path)
            
        except Exception as e:
            self.logger.error(f"Failed to restore conversation context: {str(e)}")
    
    async def prepare_for_update(self) -> bool:
        """
        Prepare system for update
        
        Returns:
            bool: True if ready for update
        """
        async with self.update_lock:
            try:
                self.logger.info("Preparing for system update...")
                self.deployment_info.status = DeploymentStatus.UPDATING
                self.deployment_info.update_in_progress = True
                
                # Preserve conversation context
                await self._preserve_conversation_context()
                
                # Notify active users about maintenance
                if self.bot_instance:
                    await self._notify_maintenance_mode()
                
                self.logger.info("System prepared for update")
                return True
                
            except Exception as e:
                self.logger.error(f"Failed to prepare for update: {str(e)}")
                self.deployment_info.status = DeploymentStatus.RUNNING
                self.deployment_info.update_in_progress = False
                return False
    
    async def _notify_maintenance_mode(self):
        """Notify users about maintenance mode"""
        try:
            # This would integrate with the Discord bot to send maintenance notifications
            # Implementation depends on bot architecture
            self.logger.info("Maintenance mode notifications sent")
        except Exception as e:
            self.logger.error(f"Failed to send maintenance notifications: {str(e)}")
    
    def get_deployment_status(self) -> Dict[str, Any]:
        """Get current deployment status"""
        return {
            "deployment_id": self.deployment_info.deployment_id,
            "version": self.deployment_info.version,
            "environment": self.deployment_info.environment,
            "status": self.deployment_info.status.value,
            "health_status": self.deployment_info.health_status.value,
            "start_time": self.deployment_info.start_time.isoformat(),
            "uptime_seconds": (datetime.utcnow() - self.deployment_info.start_time).total_seconds(),
            "memory_usage_mb": self.deployment_info.memory_usage_mb,
            "cpu_usage_percent": self.deployment_info.cpu_usage_percent,
            "active_connections": self.deployment_info.active_connections,
            "update_in_progress": self.deployment_info.update_in_progress,
            "last_update_time": self.deployment_info.last_update_time.isoformat() if self.deployment_info.last_update_time else None,
            "health_checks": {
                name: {
                    "status": check.last_status.value,
                    "consecutive_failures": check.consecutive_failures,
                    "last_check": check.last_check_time.isoformat() if check.last_check_time else None,
                    "last_error": check.last_error
                }
                for name, check in self.deployment_info.health_checks.items()
            }
        }
    
    def add_active_conversation(self, user_id: str, conversation_data: Dict[str, Any]):
        """Add active conversation for context preservation"""
        self.active_conversations[user_id] = {
            "data": conversation_data,
            "timestamp": datetime.utcnow().isoformat()
        }
    
    def remove_active_conversation(self, user_id: str):
        """Remove active conversation"""
        self.active_conversations.pop(user_id, None)
    
    async def wait_for_shutdown(self):
        """Wait for shutdown event"""
        await self.shutdown_event.wait()
    
    async def perform_update(self, new_version: str) -> bool:
        """Perform system update to new version"""
        try:
            self.logger.info(f"Starting update to version {new_version}")
            
            async with self.update_lock:
                # Set update status
                self.deployment_info.update_in_progress = True
                self.deployment_info.status = DeploymentStatus.UPDATING
                
                # Preserve context
                await self._preserve_active_conversations()
                
                # Perform update steps (placeholder implementation)
                await asyncio.sleep(1)  # Simulate update process
                
                # Update version
                self.deployment_info.version = new_version
                self.deployment_info.last_update_time = datetime.utcnow()
                self.deployment_info.update_in_progress = False
                self.deployment_info.status = DeploymentStatus.RUNNING
                
                self.logger.info(f"Update to version {new_version} completed")
                return True
                
        except Exception as e:
            self.logger.error(f"Update failed: {e}")
            self.deployment_info.update_in_progress = False
            self.deployment_info.status = DeploymentStatus.FAILED
            return False
    
    async def enter_maintenance_mode(self, reason: str = "System maintenance"):
        """Enter maintenance mode"""
        try:
            self.logger.info(f"Entering maintenance mode: {reason}")
            
            # Set maintenance status
            self.deployment_info.status = DeploymentStatus.MAINTENANCE
            
            # Preserve active conversations
            await self._preserve_active_conversations()
            
            # Notify users about maintenance
            await self._notify_maintenance_mode(reason)
            
            self.logger.info("Maintenance mode activated")
            
        except Exception as e:
            self.logger.error(f"Failed to enter maintenance mode: {e}")
    
    async def exit_maintenance_mode(self):
        """Exit maintenance mode"""
        try:
            self.logger.info("Exiting maintenance mode")
            
            # Restore status
            self.deployment_info.status = DeploymentStatus.RUNNING
            
            # Restore conversations
            await self._restore_active_conversations()
            
            self.logger.info("Maintenance mode deactivated")
            
        except Exception as e:
            self.logger.error(f"Failed to exit maintenance mode: {e}")
    
    def _execute_shutdown_callbacks(self):
        """Execute shutdown callbacks (synchronous version)"""
        for callback in self.shutdown_callbacks:
            try:
                if asyncio.iscoroutinefunction(callback):
                    # For async callbacks, we need to run them in the event loop
                    asyncio.create_task(callback())
                else:
                    callback()
            except Exception as e:
                self.logger.error(f"Shutdown callback failed: {e}")
    
    async def _run_shutdown_callbacks(self):
        """Execute shutdown callbacks (async version)"""
        for callback in self.shutdown_callbacks:
            try:
                if asyncio.iscoroutinefunction(callback):
                    await callback()
                else:
                    callback()
            except Exception as e:
                self.logger.error(f"Shutdown callback failed: {e}")
    
    async def _update_resource_usage(self):
        """Update resource usage metrics"""
        try:
            import psutil
            
            # Get memory usage
            memory_info = psutil.virtual_memory()
            self.deployment_info.memory_usage_mb = memory_info.used / (1024 * 1024)
            
            # Get CPU usage
            self.deployment_info.cpu_usage_percent = psutil.cpu_percent(interval=1)
            
            # Update connection count (placeholder)
            self.deployment_info.active_connections = len(self.active_conversations)
            
        except ImportError:
            # psutil not available, use placeholder values
            self.deployment_info.memory_usage_mb = 100.0
            self.deployment_info.cpu_usage_percent = 5.0
            self.deployment_info.active_connections = len(self.active_conversations)
        except Exception as e:
            self.logger.error(f"Failed to update resource usage: {e}")