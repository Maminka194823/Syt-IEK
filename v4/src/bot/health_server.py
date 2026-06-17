"""
Health Check Server for Aviation Girl V4 Discord Bot
Provides HTTP endpoints for health monitoring and system status
"""

import asyncio
import json
import logging
from datetime import datetime, timedelta
from typing import Dict, Any, Optional
import aiohttp
from aiohttp import web
import psutil
import os
import sys
from pathlib import Path

class HealthCheckServer:
    """
    HTTP server providing health check and monitoring endpoints
    """
    
    def __init__(self, bot_instance=None, port: int = 8081, metrics_port: int = 8080):
        self.bot = bot_instance
        self.port = port
        self.metrics_port = metrics_port
        self.app = web.Application()
        self.metrics_app = web.Application()
        self.start_time = datetime.utcnow()
        self.last_health_check = None
        self.health_status = {
            "overall_healthy": False,
            "components": {},
            "last_check": None
        }
        
        # Setup routes
        self._setup_routes()
        
        # Performance metrics
        self.metrics = {
            "requests_total": 0,
            "requests_by_endpoint": {},
            "response_times": [],
            "errors_total": 0,
            "last_request_time": None
        }
    
    def _setup_routes(self):
        """Setup HTTP routes for health checks"""
        # Health check routes
        self.app.router.add_get('/health', self.health_check)
        self.app.router.add_get('/health/detailed', self.detailed_health_check)
        self.app.router.add_get('/ready', self.readiness_check)
        self.app.router.add_get('/alive', self.liveness_check)
        self.app.router.add_get('/status', self.system_status)
        
        # Metrics routes
        self.metrics_app.router.add_get('/metrics', self.prometheus_metrics)
        self.metrics_app.router.add_get('/metrics/json', self.json_metrics)
        
        # Add middleware for request tracking
        self.app.middlewares.append(self._request_middleware)
        self.metrics_app.middlewares.append(self._request_middleware)
    
    @web.middleware
    async def _request_middleware(self, request, handler):
        """Middleware to track requests and response times"""
        start_time = datetime.utcnow()
        endpoint = request.path
        
        try:
            response = await handler(request)
            
            # Track metrics
            self.metrics["requests_total"] += 1
            self.metrics["last_request_time"] = start_time
            
            if endpoint not in self.metrics["requests_by_endpoint"]:
                self.metrics["requests_by_endpoint"][endpoint] = 0
            self.metrics["requests_by_endpoint"][endpoint] += 1
            
            # Track response time
            response_time = (datetime.utcnow() - start_time).total_seconds() * 1000
            self.metrics["response_times"].append(response_time)
            
            # Keep only last 1000 response times
            if len(self.metrics["response_times"]) > 1000:
                self.metrics["response_times"] = self.metrics["response_times"][-1000:]
            
            return response
            
        except Exception as e:
            self.metrics["errors_total"] += 1
            logging.error(f"Health server error: {e}")
            raise
    
    async def health_check(self, request):
        """Basic health check endpoint"""
        try:
            # Perform basic health check
            is_healthy = await self._check_basic_health()
            
            status_code = 200 if is_healthy else 503
            response_data = {
                "status": "healthy" if is_healthy else "unhealthy",
                "timestamp": datetime.utcnow().isoformat(),
                "uptime_seconds": (datetime.utcnow() - self.start_time).total_seconds()
            }
            
            return web.json_response(response_data, status=status_code)
            
        except Exception as e:
            logging.error(f"Health check error: {e}")
            return web.json_response(
                {"status": "error", "message": str(e)},
                status=500
            )
    
    async def detailed_health_check(self, request):
        """Detailed health check with component status"""
        try:
            health_data = await self._perform_detailed_health_check()
            
            status_code = 200 if health_data["overall_healthy"] else 503
            return web.json_response(health_data, status=status_code)
            
        except Exception as e:
            logging.error(f"Detailed health check error: {e}")
            return web.json_response(
                {"status": "error", "message": str(e)},
                status=500
            )
    
    async def readiness_check(self, request):
        """Readiness check - is the bot ready to serve requests"""
        try:
            is_ready = await self._check_readiness()
            
            status_code = 200 if is_ready else 503
            response_data = {
                "ready": is_ready,
                "timestamp": datetime.utcnow().isoformat()
            }
            
            return web.json_response(response_data, status=status_code)
            
        except Exception as e:
            logging.error(f"Readiness check error: {e}")
            return web.json_response(
                {"ready": False, "error": str(e)},
                status=500
            )
    
    async def liveness_check(self, request):
        """Liveness check - is the bot process alive"""
        try:
            # Simple liveness check - if we can respond, we're alive
            response_data = {
                "alive": True,
                "timestamp": datetime.utcnow().isoformat(),
                "pid": os.getpid()
            }
            
            return web.json_response(response_data, status=200)
            
        except Exception as e:
            logging.error(f"Liveness check error: {e}")
            return web.json_response(
                {"alive": False, "error": str(e)},
                status=500
            )
    
    async def system_status(self, request):
        """Comprehensive system status"""
        try:
            status_data = await self._get_system_status()
            return web.json_response(status_data, status=200)
            
        except Exception as e:
            logging.error(f"System status error: {e}")
            return web.json_response(
                {"status": "error", "message": str(e)},
                status=500
            )
    
    async def prometheus_metrics(self, request):
        """Prometheus-format metrics"""
        try:
            metrics_text = await self._generate_prometheus_metrics()
            return web.Response(
                text=metrics_text,
                content_type='text/plain; version=0.0.4; charset=utf-8'
            )
            
        except Exception as e:
            logging.error(f"Prometheus metrics error: {e}")
            return web.Response(
                text=f"# Error generating metrics: {e}",
                status=500,
                content_type='text/plain'
            )
    
    async def json_metrics(self, request):
        """JSON-format metrics"""
        try:
            metrics_data = await self._get_json_metrics()
            return web.json_response(metrics_data, status=200)
            
        except Exception as e:
            logging.error(f"JSON metrics error: {e}")
            return web.json_response(
                {"error": str(e)},
                status=500
            )
    
    async def _check_basic_health(self) -> bool:
        """Perform basic health check"""
        try:
            # Check if bot instance is available and responsive
            if self.bot is None:
                return False
            
            # Check if bot is connected to Discord
            if hasattr(self.bot, 'is_ready') and not self.bot.is_ready():
                return False
            
            # Check system resources
            memory_percent = psutil.virtual_memory().percent
            if memory_percent > 95:  # More than 95% memory usage
                return False
            
            disk_percent = psutil.disk_usage('/').percent
            if disk_percent > 95:  # More than 95% disk usage
                return False
            
            return True
            
        except Exception as e:
            logging.error(f"Basic health check failed: {e}")
            return False
    
    async def _perform_detailed_health_check(self) -> Dict[str, Any]:
        """Perform detailed health check of all components"""
        health_data = {
            "overall_healthy": True,
            "timestamp": datetime.utcnow().isoformat(),
            "uptime_seconds": (datetime.utcnow() - self.start_time).total_seconds(),
            "components": {}
        }
        
        # Check Discord connection
        discord_healthy = await self._check_discord_health()
        health_data["components"]["discord"] = {
            "healthy": discord_healthy,
            "status": "connected" if discord_healthy else "disconnected"
        }
        
        # Check AI system
        ai_healthy = await self._check_ai_health()
        health_data["components"]["ai_system"] = {
            "healthy": ai_healthy,
            "status": "operational" if ai_healthy else "error"
        }
        
        # Check memory system
        memory_healthy = await self._check_memory_system_health()
        health_data["components"]["memory_system"] = {
            "healthy": memory_healthy,
            "status": "operational" if memory_healthy else "error"
        }
        
        # Check knowledge system
        knowledge_healthy = await self._check_knowledge_system_health()
        health_data["components"]["knowledge_system"] = {
            "healthy": knowledge_healthy,
            "status": "operational" if knowledge_healthy else "error"
        }
        
        # Check system resources
        resources_healthy = await self._check_system_resources()
        health_data["components"]["system_resources"] = resources_healthy
        
        # Check external APIs
        apis_healthy = await self._check_external_apis()
        health_data["components"]["external_apis"] = apis_healthy
        
        # Determine overall health
        component_health = [
            discord_healthy,
            ai_healthy,
            memory_healthy,
            knowledge_healthy,
            resources_healthy["healthy"],
            apis_healthy["healthy"]
        ]
        
        health_data["overall_healthy"] = all(component_health)
        
        # Cache the result
        self.health_status = health_data
        self.last_health_check = datetime.utcnow()
        
        return health_data
    
    async def _check_readiness(self) -> bool:
        """Check if the bot is ready to serve requests"""
        try:
            if self.bot is None:
                return False
            
            # Check if all systems are initialized
            if hasattr(self.bot, 'is_ready') and not self.bot.is_ready():
                return False
            
            # Check if startup is complete
            if hasattr(self.bot, 'startup_report') and self.bot.startup_report is None:
                return False
            
            return True
            
        except Exception as e:
            logging.error(f"Readiness check failed: {e}")
            return False
    
    async def _check_discord_health(self) -> bool:
        """Check Discord connection health"""
        try:
            if self.bot is None:
                return False
            
            if hasattr(self.bot, 'is_ready'):
                return self.bot.is_ready()
            
            return True
            
        except Exception as e:
            logging.error(f"Discord health check failed: {e}")
            return False
    
    async def _check_ai_health(self) -> bool:
        """Check AI system health"""
        try:
            if self.bot is None or not hasattr(self.bot, 'ai_model'):
                return False
            
            # Check if AI model is loaded
            if self.bot.ai_model is None:
                return False
            
            return True
            
        except Exception as e:
            logging.error(f"AI health check failed: {e}")
            return False
    
    async def _check_memory_system_health(self) -> bool:
        """Check memory system health"""
        try:
            if self.bot is None:
                return False
            
            # Check if user profiles system is available
            if hasattr(self.bot, 'user_profiles') and self.bot.user_profiles is None:
                return False
            
            return True
            
        except Exception as e:
            logging.error(f"Memory system health check failed: {e}")
            return False
    
    async def _check_knowledge_system_health(self) -> bool:
        """Check knowledge system health"""
        try:
            if self.bot is None:
                return False
            
            # Check if knowledge base is available
            if hasattr(self.bot, 'knowledge_base') and self.bot.knowledge_base is None:
                return False
            
            return True
            
        except Exception as e:
            logging.error(f"Knowledge system health check failed: {e}")
            return False
    
    async def _check_system_resources(self) -> Dict[str, Any]:
        """Check system resource health"""
        try:
            # Memory usage
            memory = psutil.virtual_memory()
            memory_healthy = memory.percent < 90
            
            # Disk usage
            disk = psutil.disk_usage('/')
            disk_healthy = disk.percent < 90
            
            # CPU usage
            cpu_percent = psutil.cpu_percent(interval=1)
            cpu_healthy = cpu_percent < 90
            
            return {
                "healthy": memory_healthy and disk_healthy and cpu_healthy,
                "memory": {
                    "percent": memory.percent,
                    "available_gb": memory.available / (1024**3),
                    "healthy": memory_healthy
                },
                "disk": {
                    "percent": disk.percent,
                    "free_gb": disk.free / (1024**3),
                    "healthy": disk_healthy
                },
                "cpu": {
                    "percent": cpu_percent,
                    "healthy": cpu_healthy
                }
            }
            
        except Exception as e:
            logging.error(f"System resources check failed: {e}")
            return {"healthy": False, "error": str(e)}
    
    async def _check_external_apis(self) -> Dict[str, Any]:
        """Check external API connectivity"""
        api_status = {
            "healthy": True,
            "apis": {}
        }
        
        # Check Discord API
        try:
            async with aiohttp.ClientSession(timeout=aiohttp.ClientTimeout(total=10)) as session:
                async with session.get('https://discord.com/api/v10/gateway') as response:
                    discord_healthy = response.status == 200
                    api_status["apis"]["discord"] = {
                        "healthy": discord_healthy,
                        "status_code": response.status
                    }
        except Exception as e:
            api_status["apis"]["discord"] = {
                "healthy": False,
                "error": str(e)
            }
        
        # Check general internet connectivity
        try:
            async with aiohttp.ClientSession(timeout=aiohttp.ClientTimeout(total=5)) as session:
                async with session.get('https://www.google.com') as response:
                    internet_healthy = response.status == 200
                    api_status["apis"]["internet"] = {
                        "healthy": internet_healthy,
                        "status_code": response.status
                    }
        except Exception as e:
            api_status["apis"]["internet"] = {
                "healthy": False,
                "error": str(e)
            }
        
        # Determine overall API health
        api_health_statuses = [
            api_status["apis"].get("discord", {}).get("healthy", False),
            api_status["apis"].get("internet", {}).get("healthy", False)
        ]
        
        api_status["healthy"] = any(api_health_statuses)  # At least one API should work
        
        return api_status
    
    async def _get_system_status(self) -> Dict[str, Any]:
        """Get comprehensive system status"""
        status = {
            "timestamp": datetime.utcnow().isoformat(),
            "uptime_seconds": (datetime.utcnow() - self.start_time).total_seconds(),
            "process": {
                "pid": os.getpid(),
                "python_version": sys.version,
                "working_directory": os.getcwd()
            },
            "system": {
                "platform": sys.platform,
                "cpu_count": psutil.cpu_count(),
                "memory_total_gb": psutil.virtual_memory().total / (1024**3)
            }
        }
        
        # Add bot-specific status if available
        if self.bot:
            bot_status = {}
            
            if hasattr(self.bot, 'user') and self.bot.user:
                bot_status["bot_user"] = {
                    "id": self.bot.user.id,
                    "name": self.bot.user.name
                }
            
            if hasattr(self.bot, 'guilds'):
                bot_status["guild_count"] = len(self.bot.guilds)
            
            if hasattr(self.bot, 'latency'):
                bot_status["latency_ms"] = round(self.bot.latency * 1000, 2)
            
            status["bot"] = bot_status
        
        return status
    
    async def _generate_prometheus_metrics(self) -> str:
        """Generate Prometheus format metrics"""
        metrics_lines = []
        
        # Basic metrics
        metrics_lines.append(f"# HELP aviationgirl_requests_total Total number of requests")
        metrics_lines.append(f"# TYPE aviationgirl_requests_total counter")
        metrics_lines.append(f"aviationgirl_requests_total {self.metrics['requests_total']}")
        
        metrics_lines.append(f"# HELP aviationgirl_errors_total Total number of errors")
        metrics_lines.append(f"# TYPE aviationgirl_errors_total counter")
        metrics_lines.append(f"aviationgirl_errors_total {self.metrics['errors_total']}")
        
        # Response time metrics
        if self.metrics["response_times"]:
            avg_response_time = sum(self.metrics["response_times"]) / len(self.metrics["response_times"])
            metrics_lines.append(f"# HELP aviationgirl_response_time_ms Average response time in milliseconds")
            metrics_lines.append(f"# TYPE aviationgirl_response_time_ms gauge")
            metrics_lines.append(f"aviationgirl_response_time_ms {avg_response_time:.2f}")
        
        # System metrics
        memory = psutil.virtual_memory()
        metrics_lines.append(f"# HELP aviationgirl_memory_usage_percent Memory usage percentage")
        metrics_lines.append(f"# TYPE aviationgirl_memory_usage_percent gauge")
        metrics_lines.append(f"aviationgirl_memory_usage_percent {memory.percent}")
        
        cpu_percent = psutil.cpu_percent()
        metrics_lines.append(f"# HELP aviationgirl_cpu_usage_percent CPU usage percentage")
        metrics_lines.append(f"# TYPE aviationgirl_cpu_usage_percent gauge")
        metrics_lines.append(f"aviationgirl_cpu_usage_percent {cpu_percent}")
        
        # Uptime
        uptime_seconds = (datetime.utcnow() - self.start_time).total_seconds()
        metrics_lines.append(f"# HELP aviationgirl_uptime_seconds Uptime in seconds")
        metrics_lines.append(f"# TYPE aviationgirl_uptime_seconds counter")
        metrics_lines.append(f"aviationgirl_uptime_seconds {uptime_seconds}")
        
        return '\n'.join(metrics_lines) + '\n'
    
    async def _get_json_metrics(self) -> Dict[str, Any]:
        """Get metrics in JSON format"""
        # Calculate response time statistics
        response_time_stats = {}
        if self.metrics["response_times"]:
            response_times = self.metrics["response_times"]
            response_time_stats = {
                "average_ms": sum(response_times) / len(response_times),
                "min_ms": min(response_times),
                "max_ms": max(response_times),
                "count": len(response_times)
            }
        
        # System metrics
        memory = psutil.virtual_memory()
        disk = psutil.disk_usage('/')
        cpu_percent = psutil.cpu_percent()
        
        return {
            "timestamp": datetime.utcnow().isoformat(),
            "uptime_seconds": (datetime.utcnow() - self.start_time).total_seconds(),
            "requests": {
                "total": self.metrics["requests_total"],
                "by_endpoint": self.metrics["requests_by_endpoint"],
                "errors_total": self.metrics["errors_total"],
                "last_request": self.metrics["last_request_time"].isoformat() if self.metrics["last_request_time"] else None
            },
            "response_times": response_time_stats,
            "system": {
                "memory": {
                    "percent": memory.percent,
                    "available_gb": memory.available / (1024**3),
                    "total_gb": memory.total / (1024**3)
                },
                "disk": {
                    "percent": disk.percent,
                    "free_gb": disk.free / (1024**3),
                    "total_gb": disk.total / (1024**3)
                },
                "cpu": {
                    "percent": cpu_percent
                }
            }
        }
    
    async def start(self):
        """Start the health check server"""
        try:
            # Start health check server
            health_runner = web.AppRunner(self.app)
            await health_runner.setup()
            health_site = web.TCPSite(health_runner, '0.0.0.0', self.port)
            await health_site.start()
            
            # Start metrics server
            metrics_runner = web.AppRunner(self.metrics_app)
            await metrics_runner.setup()
            metrics_site = web.TCPSite(metrics_runner, '0.0.0.0', self.metrics_port)
            await metrics_site.start()
            
            logging.info(f"Health check server started on port {self.port}")
            logging.info(f"Metrics server started on port {self.metrics_port}")
            
        except Exception as e:
            logging.error(f"Failed to start health check server: {e}")
            raise
    
    async def stop(self):
        """Stop the health check server"""
        try:
            # Stop servers gracefully
            logging.info("Stopping health check servers...")
            
        except Exception as e:
            logging.error(f"Error stopping health check server: {e}")


# Standalone health check server for testing
async def main():
    """Run standalone health check server for testing"""
    logging.basicConfig(level=logging.INFO)
    
    health_server = HealthCheckServer()
    await health_server.start()
    
    try:
        # Keep the server running
        while True:
            await asyncio.sleep(1)
    except KeyboardInterrupt:
        logging.info("Shutting down health check server...")
        await health_server.stop()


if __name__ == "__main__":
    asyncio.run(main())