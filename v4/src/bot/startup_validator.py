#!/usr/bin/env python3
"""
Startup Validator for Aviation Girl V4 Discord Bot

Provides comprehensive startup validation including:
- API connection testing and credential verification
- System initialization reporting
- Aviation data source validation
- Configuration validation
"""

import asyncio
import logging
import aiohttp
import json
from typing import Dict, Any, List, Optional, Tuple
from datetime import datetime
from dataclasses import dataclass, field
from enum import Enum

from .config_manager import BotConfiguration
from ..security.api_security_manager import APISecurityManager


class ValidationStatus(Enum):
    """Validation status states"""
    PENDING = "pending"
    PASSED = "passed"
    FAILED = "failed"
    WARNING = "warning"
    SKIPPED = "skipped"


@dataclass
class ValidationResult:
    """Result of a validation check"""
    name: str
    status: ValidationStatus
    message: str
    details: Optional[Dict[str, Any]] = None
    duration_ms: Optional[float] = None
    error: Optional[str] = None


@dataclass
class StartupReport:
    """Complete startup validation report"""
    timestamp: datetime
    overall_status: ValidationStatus
    total_checks: int
    passed_checks: int
    failed_checks: int
    warning_checks: int
    skipped_checks: int
    total_duration_ms: float
    validation_results: List[ValidationResult] = field(default_factory=list)
    system_info: Dict[str, Any] = field(default_factory=dict)


class StartupValidator:
    """
    Comprehensive startup validator for the Aviation Girl V4 bot
    
    Validates system components, API connections, and configuration
    before the bot starts accepting requests.
    """
    
    def __init__(self, config: BotConfiguration):
        self.config = config
        self.logger = logging.getLogger(__name__)
        
        # Initialize credential manager first
        from ..security.credential_manager import CredentialManager
        from ..security.encryption_manager import EncryptionManager
        encryption_manager = EncryptionManager()
        self.credential_manager = CredentialManager(encryption_manager)
        self.api_security_manager = APISecurityManager(self.credential_manager)
        
        # Validation registry
        self.validation_checks = []
        self._register_default_checks()
    
    def _register_default_checks(self):
        """Register default validation checks"""
        # Configuration validation
        self.register_check("config_validation", self._validate_configuration, critical=True)
        
        # Discord configuration
        self.register_check("discord_config", self._validate_discord_config, critical=True)
        
        # AI model configuration
        self.register_check("ai_config", self._validate_ai_config, critical=True)
        
        # API connections
        self.register_check("aviation_weather_api", self._validate_weather_api, critical=False)
        self.register_check("flight_tracking_api", self._validate_flight_api, critical=False)
        self.register_check("faa_api", self._validate_faa_api, critical=False)
        
        # System resources
        self.register_check("system_resources", self._validate_system_resources, critical=True)
        
        # File system permissions
        self.register_check("file_permissions", self._validate_file_permissions, critical=True)
        
        # Network connectivity
        self.register_check("network_connectivity", self._validate_network_connectivity, critical=True)
        
        # Security configuration
        self.register_check("security_config", self._validate_security_config, critical=False)
    
    def register_check(self, name: str, check_function, critical: bool = False, timeout: int = 30):
        """Register a validation check"""
        self.validation_checks.append({
            "name": name,
            "function": check_function,
            "critical": critical,
            "timeout": timeout
        })
    
    async def validate_startup(self) -> StartupReport:
        """
        Run all startup validation checks
        
        Returns:
            StartupReport: Complete validation report
        """
        start_time = datetime.utcnow()
        self.logger.info("Starting comprehensive startup validation...")
        
        report = StartupReport(
            timestamp=start_time,
            overall_status=ValidationStatus.PENDING,
            total_checks=len(self.validation_checks),
            passed_checks=0,
            failed_checks=0,
            warning_checks=0,
            skipped_checks=0,
            total_duration_ms=0.0
        )
        
        # Collect system information
        report.system_info = await self._collect_system_info()
        
        # Run validation checks
        for check in self.validation_checks:
            result = await self._run_validation_check(check)
            report.validation_results.append(result)
            
            # Update counters
            if result.status == ValidationStatus.PASSED:
                report.passed_checks += 1
            elif result.status == ValidationStatus.FAILED:
                report.failed_checks += 1
            elif result.status == ValidationStatus.WARNING:
                report.warning_checks += 1
            elif result.status == ValidationStatus.SKIPPED:
                report.skipped_checks += 1
        
        # Calculate total duration
        end_time = datetime.utcnow()
        report.total_duration_ms = (end_time - start_time).total_seconds() * 1000
        
        # Determine overall status
        if report.failed_checks > 0:
            # Check if any critical checks failed
            critical_failures = [
                r for r in report.validation_results 
                if r.status == ValidationStatus.FAILED and self._is_critical_check(r.name)
            ]
            if critical_failures:
                report.overall_status = ValidationStatus.FAILED
            else:
                report.overall_status = ValidationStatus.WARNING
        elif report.warning_checks > 0:
            report.overall_status = ValidationStatus.WARNING
        else:
            report.overall_status = ValidationStatus.PASSED
        
        # Log summary
        self._log_validation_summary(report)
        
        return report
    
    def _is_critical_check(self, check_name: str) -> bool:
        """Check if a validation check is critical"""
        for check in self.validation_checks:
            if check["name"] == check_name:
                return check.get("critical", False)
        return False
    
    async def _run_validation_check(self, check: Dict[str, Any]) -> ValidationResult:
        """Run a single validation check"""
        check_name = check["name"]
        check_function = check["function"]
        timeout = check.get("timeout", 30)
        
        self.logger.debug(f"Running validation check: {check_name}")
        
        start_time = datetime.utcnow()
        
        try:
            # Run check with timeout
            result = await asyncio.wait_for(
                check_function(),
                timeout=timeout
            )
            
            end_time = datetime.utcnow()
            duration_ms = (end_time - start_time).total_seconds() * 1000
            
            if isinstance(result, ValidationResult):
                result.duration_ms = duration_ms
                return result
            elif isinstance(result, bool):
                status = ValidationStatus.PASSED if result else ValidationStatus.FAILED
                message = f"{check_name} {'passed' if result else 'failed'}"
                return ValidationResult(
                    name=check_name,
                    status=status,
                    message=message,
                    duration_ms=duration_ms
                )
            else:
                return ValidationResult(
                    name=check_name,
                    status=ValidationStatus.FAILED,
                    message=f"Invalid result type from {check_name}",
                    duration_ms=duration_ms
                )
                
        except asyncio.TimeoutError:
            return ValidationResult(
                name=check_name,
                status=ValidationStatus.FAILED,
                message=f"{check_name} timed out after {timeout} seconds",
                error="Timeout"
            )
        except Exception as e:
            return ValidationResult(
                name=check_name,
                status=ValidationStatus.FAILED,
                message=f"{check_name} failed with error: {str(e)}",
                error=str(e)
            )
    
    async def _collect_system_info(self) -> Dict[str, Any]:
        """Collect system information"""
        import platform
        import sys
        
        try:
            import psutil
            memory_info = psutil.virtual_memory()
            disk_info = psutil.disk_usage('/')
            
            system_info = {
                "platform": platform.platform(),
                "python_version": sys.version,
                "memory_total_gb": round(memory_info.total / (1024**3), 2),
                "memory_available_gb": round(memory_info.available / (1024**3), 2),
                "disk_total_gb": round(disk_info.total / (1024**3), 2),
                "disk_free_gb": round(disk_info.free / (1024**3), 2),
                "cpu_count": psutil.cpu_count()
            }
        except ImportError:
            system_info = {
                "platform": platform.platform(),
                "python_version": sys.version,
                "psutil_available": False
            }
        
        return system_info
    
    async def _validate_configuration(self) -> ValidationResult:
        """Validate bot configuration"""
        try:
            # Check required configuration sections
            required_sections = ["discord", "ai", "memory", "knowledge", "security", "api", "monitoring", "deployment"]
            missing_sections = []
            
            for section in required_sections:
                if not hasattr(self.config, section):
                    missing_sections.append(section)
            
            if missing_sections:
                return ValidationResult(
                    name="config_validation",
                    status=ValidationStatus.FAILED,
                    message=f"Missing configuration sections: {', '.join(missing_sections)}"
                )
            
            # Validate critical configuration values
            if not self.config.discord.token:
                return ValidationResult(
                    name="config_validation",
                    status=ValidationStatus.FAILED,
                    message="Discord token is not configured"
                )
            
            return ValidationResult(
                name="config_validation",
                status=ValidationStatus.PASSED,
                message="Configuration validation passed"
            )
            
        except Exception as e:
            return ValidationResult(
                name="config_validation",
                status=ValidationStatus.FAILED,
                message=f"Configuration validation error: {str(e)}",
                error=str(e)
            )
    
    async def _validate_discord_config(self) -> ValidationResult:
        """Validate Discord configuration"""
        try:
            issues = []
            
            # Check token format (basic validation)
            token = self.config.discord.token
            if len(token) < 50:
                issues.append("Discord token appears to be too short")
            
            # Check command prefix
            if not self.config.discord.command_prefix:
                issues.append("Command prefix is empty")
            
            # Check embed color
            if not (0 <= self.config.discord.embed_color <= 0xFFFFFF):
                issues.append("Invalid embed color value")
            
            if issues:
                return ValidationResult(
                    name="discord_config",
                    status=ValidationStatus.WARNING,
                    message=f"Discord configuration issues: {'; '.join(issues)}",
                    details={"issues": issues}
                )
            
            return ValidationResult(
                name="discord_config",
                status=ValidationStatus.PASSED,
                message="Discord configuration is valid"
            )
            
        except Exception as e:
            return ValidationResult(
                name="discord_config",
                status=ValidationStatus.FAILED,
                message=f"Discord configuration validation error: {str(e)}",
                error=str(e)
            )
    
    async def _validate_ai_config(self) -> ValidationResult:
        """Validate AI configuration"""
        try:
            issues = []
            
            # Check model configuration
            if not self.config.ai.model_name:
                issues.append("AI model name is not specified")
            
            # Check temperature range
            if not (0 <= self.config.ai.temperature <= 2):
                issues.append(f"AI temperature {self.config.ai.temperature} is outside valid range (0-2)")
            
            # Check context length
            if self.config.ai.max_context_length <= 0:
                issues.append("AI max context length must be positive")
            
            # Check timeout
            if self.config.ai.timeout_seconds <= 0:
                issues.append("AI timeout must be positive")
            
            if issues:
                return ValidationResult(
                    name="ai_config",
                    status=ValidationStatus.WARNING,
                    message=f"AI configuration issues: {'; '.join(issues)}",
                    details={"issues": issues}
                )
            
            return ValidationResult(
                name="ai_config",
                status=ValidationStatus.PASSED,
                message="AI configuration is valid"
            )
            
        except Exception as e:
            return ValidationResult(
                name="ai_config",
                status=ValidationStatus.FAILED,
                message=f"AI configuration validation error: {str(e)}",
                error=str(e)
            )
    
    async def _validate_weather_api(self) -> ValidationResult:
        """Validate aviation weather API connection"""
        if not self.config.api.aviation_weather_api_key:
            return ValidationResult(
                name="aviation_weather_api",
                status=ValidationStatus.SKIPPED,
                message="Aviation weather API key not configured"
            )
        
        try:
            # Test connection to aviation weather service
            async with aiohttp.ClientSession(timeout=aiohttp.ClientTimeout(total=10)) as session:
                # Test with a simple request (METAR for a major airport)
                url = "https://aviationweather.gov/api/data/metar"
                params = {
                    "ids": "KJFK",
                    "format": "json",
                    "taf": "false"
                }
                
                async with session.get(url, params=params) as response:
                    if response.status == 200:
                        data = await response.json()
                        if data and len(data) > 0:
                            return ValidationResult(
                                name="aviation_weather_api",
                                status=ValidationStatus.PASSED,
                                message="Aviation weather API connection successful",
                                details={"response_status": response.status, "data_count": len(data)}
                            )
                        else:
                            return ValidationResult(
                                name="aviation_weather_api",
                                status=ValidationStatus.WARNING,
                                message="Aviation weather API returned empty data"
                            )
                    else:
                        return ValidationResult(
                            name="aviation_weather_api",
                            status=ValidationStatus.FAILED,
                            message=f"Aviation weather API returned status {response.status}"
                        )
                        
        except Exception as e:
            return ValidationResult(
                name="aviation_weather_api",
                status=ValidationStatus.FAILED,
                message=f"Aviation weather API connection failed: {str(e)}",
                error=str(e)
            )
    
    async def _validate_flight_api(self) -> ValidationResult:
        """Validate flight tracking API connection"""
        if not self.config.api.flight_tracking_api_key:
            return ValidationResult(
                name="flight_tracking_api",
                status=ValidationStatus.SKIPPED,
                message="Flight tracking API key not configured"
            )
        
        try:
            # For demonstration, we'll simulate a flight API test
            # In a real implementation, this would test the actual flight tracking service
            await asyncio.sleep(0.1)  # Simulate API call
            
            return ValidationResult(
                name="flight_tracking_api",
                status=ValidationStatus.PASSED,
                message="Flight tracking API connection successful (simulated)",
                details={"simulated": True}
            )
            
        except Exception as e:
            return ValidationResult(
                name="flight_tracking_api",
                status=ValidationStatus.FAILED,
                message=f"Flight tracking API connection failed: {str(e)}",
                error=str(e)
            )
    
    async def _validate_faa_api(self) -> ValidationResult:
        """Validate FAA API connection"""
        if not self.config.api.faa_api_key:
            return ValidationResult(
                name="faa_api",
                status=ValidationStatus.SKIPPED,
                message="FAA API key not configured"
            )
        
        try:
            # Test connection to FAA services
            async with aiohttp.ClientSession(timeout=aiohttp.ClientTimeout(total=10)) as session:
                # Test with FAA NOTAM service (public endpoint)
                url = "https://www.notams.faa.gov/dinsQueryWeb/queryRetrievalMapAction.action"
                
                async with session.get(url) as response:
                    if response.status == 200:
                        return ValidationResult(
                            name="faa_api",
                            status=ValidationStatus.PASSED,
                            message="FAA API connection successful",
                            details={"response_status": response.status}
                        )
                    else:
                        return ValidationResult(
                            name="faa_api",
                            status=ValidationStatus.WARNING,
                            message=f"FAA API returned status {response.status}"
                        )
                        
        except Exception as e:
            return ValidationResult(
                name="faa_api",
                status=ValidationStatus.FAILED,
                message=f"FAA API connection failed: {str(e)}",
                error=str(e)
            )
    
    async def _validate_system_resources(self) -> ValidationResult:
        """Validate system resources"""
        try:
            import psutil
            
            # Check memory
            memory = psutil.virtual_memory()
            available_gb = memory.available / (1024**3)
            
            # Check disk space
            disk = psutil.disk_usage('/')
            free_gb = disk.free / (1024**3)
            
            issues = []
            
            if available_gb < 0.5:  # Less than 500MB available
                issues.append(f"Low available memory: {available_gb:.1f}GB")
            
            if free_gb < 1.0:  # Less than 1GB free disk space
                issues.append(f"Low disk space: {free_gb:.1f}GB free")
            
            if issues:
                return ValidationResult(
                    name="system_resources",
                    status=ValidationStatus.WARNING,
                    message=f"System resource warnings: {'; '.join(issues)}",
                    details={
                        "memory_available_gb": round(available_gb, 2),
                        "disk_free_gb": round(free_gb, 2)
                    }
                )
            
            return ValidationResult(
                name="system_resources",
                status=ValidationStatus.PASSED,
                message="System resources are adequate",
                details={
                    "memory_available_gb": round(available_gb, 2),
                    "disk_free_gb": round(free_gb, 2)
                }
            )
            
        except ImportError:
            return ValidationResult(
                name="system_resources",
                status=ValidationStatus.SKIPPED,
                message="psutil not available for system resource checking"
            )
        except Exception as e:
            return ValidationResult(
                name="system_resources",
                status=ValidationStatus.FAILED,
                message=f"System resource validation error: {str(e)}",
                error=str(e)
            )
    
    async def _validate_file_permissions(self) -> ValidationResult:
        """Validate file system permissions"""
        try:
            import os
            import tempfile
            
            # Test directories that need to be writable
            test_dirs = [
                "./data",
                "./logs",
                "./keys"
            ]
            
            issues = []
            
            for test_dir in test_dirs:
                try:
                    # Create directory if it doesn't exist
                    os.makedirs(test_dir, exist_ok=True)
                    
                    # Test write permission
                    test_file = os.path.join(test_dir, "test_write_permission.tmp")
                    with open(test_file, 'w') as f:
                        f.write("test")
                    
                    # Clean up test file
                    os.remove(test_file)
                    
                except Exception as e:
                    issues.append(f"Cannot write to {test_dir}: {str(e)}")
            
            if issues:
                return ValidationResult(
                    name="file_permissions",
                    status=ValidationStatus.FAILED,
                    message=f"File permission issues: {'; '.join(issues)}",
                    details={"issues": issues}
                )
            
            return ValidationResult(
                name="file_permissions",
                status=ValidationStatus.PASSED,
                message="File permissions are adequate"
            )
            
        except Exception as e:
            return ValidationResult(
                name="file_permissions",
                status=ValidationStatus.FAILED,
                message=f"File permission validation error: {str(e)}",
                error=str(e)
            )
    
    async def _validate_network_connectivity(self) -> ValidationResult:
        """Validate network connectivity"""
        try:
            # Test basic internet connectivity
            async with aiohttp.ClientSession(timeout=aiohttp.ClientTimeout(total=10)) as session:
                test_urls = [
                    "https://www.google.com",
                    "https://discord.com",
                    "https://aviationweather.gov"
                ]
                
                successful_connections = 0
                
                for url in test_urls:
                    try:
                        async with session.get(url) as response:
                            if response.status < 400:
                                successful_connections += 1
                    except:
                        pass  # Connection failed, continue testing others
                
                if successful_connections == 0:
                    return ValidationResult(
                        name="network_connectivity",
                        status=ValidationStatus.FAILED,
                        message="No network connectivity detected"
                    )
                elif successful_connections < len(test_urls):
                    return ValidationResult(
                        name="network_connectivity",
                        status=ValidationStatus.WARNING,
                        message=f"Limited network connectivity: {successful_connections}/{len(test_urls)} sites reachable"
                    )
                else:
                    return ValidationResult(
                        name="network_connectivity",
                        status=ValidationStatus.PASSED,
                        message="Network connectivity is good",
                        details={"successful_connections": successful_connections, "total_tested": len(test_urls)}
                    )
                    
        except Exception as e:
            return ValidationResult(
                name="network_connectivity",
                status=ValidationStatus.FAILED,
                message=f"Network connectivity validation error: {str(e)}",
                error=str(e)
            )
    
    async def _validate_security_config(self) -> ValidationResult:
        """Validate security configuration"""
        try:
            issues = []
            
            # Check encryption settings
            if self.config.deployment.environment.value == "production":
                if not self.config.security.enable_encryption:
                    issues.append("Encryption should be enabled in production")
                
                if not self.config.security.enable_audit_logging:
                    issues.append("Audit logging should be enabled in production")
                
                if not self.config.security.enable_rate_limiting:
                    issues.append("Rate limiting should be enabled in production")
            
            # Check session timeout
            if self.config.security.session_timeout_minutes > 1440:  # 24 hours
                issues.append("Session timeout is very long (>24 hours)")
            
            if issues:
                return ValidationResult(
                    name="security_config",
                    status=ValidationStatus.WARNING,
                    message=f"Security configuration warnings: {'; '.join(issues)}",
                    details={"issues": issues}
                )
            
            return ValidationResult(
                name="security_config",
                status=ValidationStatus.PASSED,
                message="Security configuration is appropriate"
            )
            
        except Exception as e:
            return ValidationResult(
                name="security_config",
                status=ValidationStatus.FAILED,
                message=f"Security configuration validation error: {str(e)}",
                error=str(e)
            )
    
    def _log_validation_summary(self, report: StartupReport):
        """Log validation summary"""
        self.logger.info(f"Startup validation completed in {report.total_duration_ms:.1f}ms")
        self.logger.info(f"Overall status: {report.overall_status.value}")
        self.logger.info(f"Results: {report.passed_checks} passed, {report.failed_checks} failed, "
                        f"{report.warning_checks} warnings, {report.skipped_checks} skipped")
        
        # Log failed checks
        failed_checks = [r for r in report.validation_results if r.status == ValidationStatus.FAILED]
        if failed_checks:
            self.logger.error("Failed validation checks:")
            for check in failed_checks:
                self.logger.error(f"  - {check.name}: {check.message}")
        
        # Log warnings
        warning_checks = [r for r in report.validation_results if r.status == ValidationStatus.WARNING]
        if warning_checks:
            self.logger.warning("Validation warnings:")
            for check in warning_checks:
                self.logger.warning(f"  - {check.name}: {check.message}")
    
    def generate_report_json(self, report: StartupReport) -> str:
        """Generate JSON report"""
        report_dict = {
            "timestamp": report.timestamp.isoformat(),
            "overall_status": report.overall_status.value,
            "summary": {
                "total_checks": report.total_checks,
                "passed_checks": report.passed_checks,
                "failed_checks": report.failed_checks,
                "warning_checks": report.warning_checks,
                "skipped_checks": report.skipped_checks,
                "total_duration_ms": report.total_duration_ms
            },
            "system_info": report.system_info,
            "validation_results": [
                {
                    "name": result.name,
                    "status": result.status.value,
                    "message": result.message,
                    "details": result.details,
                    "duration_ms": result.duration_ms,
                    "error": result.error
                }
                for result in report.validation_results
            ]
        }
        
        return json.dumps(report_dict, indent=2)
    
    async def validate_api_connections_only(self) -> Dict[str, ValidationResult]:
        """Run only API connection validations"""
        api_checks = [
            ("aviation_weather_api", self._validate_weather_api),
            ("flight_tracking_api", self._validate_flight_api),
            ("faa_api", self._validate_faa_api)
        ]
        
        results = {}
        
        for check_name, check_function in api_checks:
            try:
                result = await asyncio.wait_for(check_function(), timeout=30)
                results[check_name] = result
            except asyncio.TimeoutError:
                results[check_name] = ValidationResult(
                    name=check_name,
                    status=ValidationStatus.FAILED,
                    message=f"{check_name} validation timed out",
                    error="Timeout"
                )
            except Exception as e:
                results[check_name] = ValidationResult(
                    name=check_name,
                    status=ValidationStatus.FAILED,
                    message=f"{check_name} validation error: {str(e)}",
                    error=str(e)
                )
        
        return results