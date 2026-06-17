#!/usr/bin/env python3
"""
Configuration Manager for Aviation Girl V4 Discord Bot

Provides comprehensive configuration management with support for:
- Environment variables
- Configuration files (JSON, YAML)
- Environment-specific behavior adaptation
- Configuration validation and error reporting
- Hot reloading of configuration
"""

import os
import json
import yaml
import logging
from typing import Dict, Any, Optional, List, Union
from pathlib import Path
from dataclasses import dataclass, field
from enum import Enum
import asyncio
from datetime import datetime
from dotenv import load_dotenv


class Environment(Enum):
    """Supported deployment environments"""
    DEVELOPMENT = "development"
    STAGING = "staging"
    PRODUCTION = "production"
    TESTING = "testing"


@dataclass
class DiscordConfig:
    """Discord-specific configuration"""
    token: str
    command_prefix: str = "!"
    auto_reply_on_mention: bool = True
    auto_reply_on_reply: bool = True
    max_message_length: int = 2000
    embed_color: int = 0x1E90FF
    status_message: str = "Flying high! ✈️"
    activity_type: str = "watching"


@dataclass
class AIConfig:
    """AI model configuration"""
    model_name: str = "qwen2.5"
    model_path: Optional[str] = None
    max_context_length: int = 4096
    temperature: float = 0.7
    top_p: float = 0.9
    max_tokens: int = 512
    timeout_seconds: int = 30
    enable_streaming: bool = False


@dataclass
class MemoryConfig:
    """Memory system configuration"""
    enable_user_memory: bool = True
    enable_conversation_history: bool = True
    max_conversation_history: int = 50
    max_context_messages: int = 10
    memory_retention_days: int = 30
    auto_prune_enabled: bool = True
    relevance_threshold: float = 0.5


@dataclass
class KnowledgeConfig:
    """Knowledge base and RAG configuration"""
    enable_rag: bool = True
    vector_db_path: str = "./data/vector_db"
    embedding_model: str = "sentence-transformers/all-MiniLM-L6-v2"
    max_search_results: int = 5
    similarity_threshold: float = 0.7
    enable_real_time_data: bool = True
    cache_ttl_seconds: int = 300


@dataclass
class SecurityConfig:
    """Security and privacy configuration"""
    enable_encryption: bool = True
    encryption_key_path: str = "./keys/encryption.key"
    enable_audit_logging: bool = True
    audit_log_path: str = "./logs/audit.log"
    max_login_attempts: int = 3
    session_timeout_minutes: int = 60
    enable_rate_limiting: bool = True


@dataclass
class APIConfig:
    """External API configuration"""
    aviation_weather_api_key: Optional[str] = None
    flight_tracking_api_key: Optional[str] = None
    faa_api_key: Optional[str] = None
    request_timeout: int = 30
    max_retries: int = 3
    retry_delay: float = 1.0
    enable_caching: bool = True
    cache_ttl: int = 300


@dataclass
class MonitoringConfig:
    """System monitoring configuration"""
    enable_metrics: bool = True
    metrics_port: int = 8080
    enable_health_checks: bool = True
    health_check_interval: int = 60
    log_level: str = "INFO"
    log_file_path: str = "./logs/aviation_bot.log"
    max_log_file_size: int = 10485760  # 10MB
    log_backup_count: int = 5


@dataclass
class DeploymentConfig:
    """Deployment-specific configuration"""
    environment: Environment = Environment.DEVELOPMENT
    debug_mode: bool = False
    enable_hot_reload: bool = False
    graceful_shutdown_timeout: int = 30
    max_concurrent_requests: int = 100
    worker_threads: int = 4
    enable_container_mode: bool = False


@dataclass
class BotConfiguration:
    """Complete bot configuration"""
    discord: DiscordConfig
    ai: AIConfig = field(default_factory=AIConfig)
    memory: MemoryConfig = field(default_factory=MemoryConfig)
    knowledge: KnowledgeConfig = field(default_factory=KnowledgeConfig)
    security: SecurityConfig = field(default_factory=SecurityConfig)
    api: APIConfig = field(default_factory=APIConfig)
    monitoring: MonitoringConfig = field(default_factory=MonitoringConfig)
    deployment: DeploymentConfig = field(default_factory=DeploymentConfig)


class ConfigurationError(Exception):
    """Configuration-related errors"""
    pass


class ConfigManager:
    """
    Comprehensive configuration manager for the Aviation Girl V4 bot
    
    Supports multiple configuration sources with precedence:
    1. Environment variables (highest priority)
    2. Configuration files
    3. Default values (lowest priority)
    """
    
    def __init__(self, config_file: Optional[str] = None):
        self.config_file = config_file
        self.config: Optional[BotConfiguration] = None
        self.config_watchers: List[asyncio.Task] = []
        self.validation_errors: List[str] = []
        
        # Load .env file
        load_dotenv()
        
        # Environment variable prefixes
        self.env_prefix = "AVIATION_BOT_"
        
        # Configuration file search paths
        self.config_search_paths = [
            "./config/bot_config.json",
            "./config/bot_config.yaml",
            "./config/bot_config.yml",
            "./bot_config.json",
            "./bot_config.yaml",
            "./bot_config.yml",
            os.path.expanduser("~/.aviation_bot/config.json"),
            os.path.expanduser("~/.aviation_bot/config.yaml"),
        ]
        
        self.logger = logging.getLogger(__name__)
    
    async def load_configuration(self) -> BotConfiguration:
        """
        Load configuration from all sources with proper precedence
        
        Returns:
            BotConfiguration: Complete validated configuration
            
        Raises:
            ConfigurationError: If configuration is invalid or required values missing
        """
        try:
            # Start with default configuration
            config_dict = self._get_default_config()
            
            # Load from configuration file
            file_config = await self._load_config_file()
            if file_config:
                config_dict = self._merge_configs(config_dict, file_config)
            
            # Override with environment variables
            env_config = self._load_env_config()
            if env_config:
                config_dict = self._merge_configs(config_dict, env_config)
            
            # Create configuration object
            self.config = self._create_config_object(config_dict)
            
            # Validate configuration
            await self._validate_configuration()
            
            # Apply environment-specific adaptations
            self._adapt_for_environment()
            
            self.logger.info(f"Configuration loaded successfully for environment: {self.config.deployment.environment.value}")
            return self.config
            
        except Exception as e:
            error_msg = f"Failed to load configuration: {str(e)}"
            self.logger.error(error_msg)
            raise ConfigurationError(error_msg) from e
    
    def _get_default_config(self) -> Dict[str, Any]:
        """Get default configuration values"""
        return {
            "discord": {
                "token": "",  # Must be provided
                "command_prefix": "!",
                "auto_reply_on_mention": True,
                "auto_reply_on_reply": True,
                "max_message_length": 2000,
                "embed_color": 0x1E90FF,
                "status_message": "Flying high! ✈️",
                "activity_type": "watching"
            },
            "ai": {
                "model_name": "qwen2.5",
                "model_path": None,
                "max_context_length": 4096,
                "temperature": 0.7,
                "top_p": 0.9,
                "max_tokens": 512,
                "timeout_seconds": 30,
                "enable_streaming": False
            },
            "memory": {
                "enable_user_memory": True,
                "enable_conversation_history": True,
                "max_conversation_history": 50,
                "max_context_messages": 10,
                "memory_retention_days": 30,
                "auto_prune_enabled": True,
                "relevance_threshold": 0.5
            },
            "knowledge": {
                "enable_rag": True,
                "vector_db_path": "./data/vector_db",
                "embedding_model": "sentence-transformers/all-MiniLM-L6-v2",
                "max_search_results": 5,
                "similarity_threshold": 0.7,
                "enable_real_time_data": True,
                "cache_ttl_seconds": 300
            },
            "security": {
                "enable_encryption": True,
                "encryption_key_path": "./keys/encryption.key",
                "enable_audit_logging": True,
                "audit_log_path": "./logs/audit.log",
                "max_login_attempts": 3,
                "session_timeout_minutes": 60,
                "enable_rate_limiting": True
            },
            "api": {
                "aviation_weather_api_key": None,
                "flight_tracking_api_key": None,
                "faa_api_key": None,
                "request_timeout": 30,
                "max_retries": 3,
                "retry_delay": 1.0,
                "enable_caching": True,
                "cache_ttl": 300
            },
            "monitoring": {
                "enable_metrics": True,
                "metrics_port": 8080,
                "enable_health_checks": True,
                "health_check_interval": 60,
                "log_level": "INFO",
                "log_file_path": "./logs/aviation_bot.log",
                "max_log_file_size": 10485760,
                "log_backup_count": 5
            },
            "deployment": {
                "environment": "development",
                "debug_mode": False,
                "enable_hot_reload": False,
                "graceful_shutdown_timeout": 30,
                "max_concurrent_requests": 100,
                "worker_threads": 4,
                "enable_container_mode": False
            }
        }
    
    async def _load_config_file(self) -> Optional[Dict[str, Any]]:
        """Load configuration from file"""
        config_file = self.config_file
        
        # If no specific file provided, search for config files
        if not config_file:
            for path in self.config_search_paths:
                if os.path.exists(path):
                    config_file = path
                    break
        
        if not config_file or not os.path.exists(config_file):
            self.logger.info("No configuration file found, using defaults and environment variables")
            return None
        
        try:
            with open(config_file, 'r', encoding='utf-8') as f:
                if config_file.endswith(('.yaml', '.yml')):
                    config_data = yaml.safe_load(f)
                else:
                    config_data = json.load(f)
            
            self.logger.info(f"Loaded configuration from: {config_file}")
            return config_data
            
        except Exception as e:
            error_msg = f"Failed to load configuration file {config_file}: {str(e)}"
            self.logger.error(error_msg)
            raise ConfigurationError(error_msg) from e
    
    def _load_env_config(self) -> Dict[str, Any]:
        """Load configuration from environment variables"""
        env_config = {}
        
        # Discord configuration
        discord_config = {}
        if token := os.getenv(f"{self.env_prefix}DISCORD_TOKEN"):
            discord_config["token"] = token
        if prefix := os.getenv(f"{self.env_prefix}DISCORD_PREFIX"):
            discord_config["command_prefix"] = prefix
        if status := os.getenv(f"{self.env_prefix}DISCORD_STATUS"):
            discord_config["status_message"] = status
        
        if discord_config:
            env_config["discord"] = discord_config
        
        # AI configuration
        ai_config = {}
        if model := os.getenv(f"{self.env_prefix}AI_MODEL"):
            ai_config["model_name"] = model
        if path := os.getenv(f"{self.env_prefix}AI_MODEL_PATH"):
            ai_config["model_path"] = path
        if temp := os.getenv(f"{self.env_prefix}AI_TEMPERATURE"):
            ai_config["temperature"] = float(temp)
        
        if ai_config:
            env_config["ai"] = ai_config
        
        # API configuration
        api_config = {}
        if weather_key := os.getenv(f"{self.env_prefix}WEATHER_API_KEY"):
            api_config["aviation_weather_api_key"] = weather_key
        if flight_key := os.getenv(f"{self.env_prefix}FLIGHT_API_KEY"):
            api_config["flight_tracking_api_key"] = flight_key
        if faa_key := os.getenv(f"{self.env_prefix}FAA_API_KEY"):
            api_config["faa_api_key"] = faa_key
        
        if api_config:
            env_config["api"] = api_config
        
        # Deployment configuration
        deployment_config = {}
        if env := os.getenv(f"{self.env_prefix}ENVIRONMENT"):
            deployment_config["environment"] = env
        if debug := os.getenv(f"{self.env_prefix}DEBUG"):
            deployment_config["debug_mode"] = debug.lower() in ("true", "1", "yes")
        if container := os.getenv(f"{self.env_prefix}CONTAINER_MODE"):
            deployment_config["enable_container_mode"] = container.lower() in ("true", "1", "yes")
        
        if deployment_config:
            env_config["deployment"] = deployment_config
        
        # Monitoring configuration
        monitoring_config = {}
        if log_level := os.getenv(f"{self.env_prefix}LOG_LEVEL"):
            monitoring_config["log_level"] = log_level.upper()
        if metrics_port := os.getenv(f"{self.env_prefix}METRICS_PORT"):
            monitoring_config["metrics_port"] = int(metrics_port)
        
        if monitoring_config:
            env_config["monitoring"] = monitoring_config
        
        if env_config:
            self.logger.info("Loaded configuration from environment variables")
        
        return env_config
    
    def _merge_configs(self, base: Dict[str, Any], override: Dict[str, Any]) -> Dict[str, Any]:
        """Recursively merge configuration dictionaries"""
        result = base.copy()
        
        for key, value in override.items():
            if key in result and isinstance(result[key], dict) and isinstance(value, dict):
                result[key] = self._merge_configs(result[key], value)
            else:
                result[key] = value
        
        return result
    
    def _create_config_object(self, config_dict: Dict[str, Any]) -> BotConfiguration:
        """Create BotConfiguration object from dictionary"""
        try:
            # Create individual config objects
            discord_config = DiscordConfig(**config_dict["discord"])
            ai_config = AIConfig(**config_dict["ai"])
            memory_config = MemoryConfig(**config_dict["memory"])
            knowledge_config = KnowledgeConfig(**config_dict["knowledge"])
            security_config = SecurityConfig(**config_dict["security"])
            api_config = APIConfig(**config_dict["api"])
            monitoring_config = MonitoringConfig(**config_dict["monitoring"])
            
            # Handle deployment config with enum conversion
            deployment_dict = config_dict["deployment"].copy()
            if isinstance(deployment_dict["environment"], str):
                deployment_dict["environment"] = Environment(deployment_dict["environment"])
            deployment_config = DeploymentConfig(**deployment_dict)
            
            return BotConfiguration(
                discord=discord_config,
                ai=ai_config,
                memory=memory_config,
                knowledge=knowledge_config,
                security=security_config,
                api=api_config,
                monitoring=monitoring_config,
                deployment=deployment_config
            )
            
        except Exception as e:
            error_msg = f"Failed to create configuration object: {str(e)}"
            self.logger.error(error_msg)
            raise ConfigurationError(error_msg) from e
    
    async def _validate_configuration(self) -> None:
        """Validate configuration and collect errors"""
        self.validation_errors = []
        
        if not self.config:
            self.validation_errors.append("Configuration object is None")
            return
        
        # Validate Discord configuration
        if not self.config.discord.token:
            self.validation_errors.append("Discord token is required")
        
        # Validate AI configuration
        if self.config.ai.temperature < 0 or self.config.ai.temperature > 2:
            self.validation_errors.append("AI temperature must be between 0 and 2")
        
        if self.config.ai.max_context_length <= 0:
            self.validation_errors.append("AI max context length must be positive")
        
        # Validate paths
        paths_to_check = [
            ("vector_db_path", self.config.knowledge.vector_db_path),
            ("encryption_key_path", self.config.security.encryption_key_path),
            ("audit_log_path", self.config.security.audit_log_path),
            ("log_file_path", self.config.monitoring.log_file_path),
        ]
        
        for path_name, path_value in paths_to_check:
            if path_value:
                path_dir = os.path.dirname(path_value)
                if path_dir and not os.path.exists(path_dir):
                    try:
                        os.makedirs(path_dir, exist_ok=True)
                        self.logger.info(f"Created directory for {path_name}: {path_dir}")
                    except Exception as e:
                        self.validation_errors.append(f"Cannot create directory for {path_name}: {path_dir} - {str(e)}")
        
        # Validate port numbers
        if not (1024 <= self.config.monitoring.metrics_port <= 65535):
            self.validation_errors.append("Metrics port must be between 1024 and 65535")
        
        # Validate memory settings
        if self.config.memory.relevance_threshold < 0 or self.config.memory.relevance_threshold > 1:
            self.validation_errors.append("Memory relevance threshold must be between 0 and 1")
        
        # If there are validation errors, raise exception
        if self.validation_errors:
            error_msg = "Configuration validation failed:\n" + "\n".join(f"- {error}" for error in self.validation_errors)
            self.logger.error(error_msg)
            raise ConfigurationError(error_msg)
        
        self.logger.info("Configuration validation passed")
    
    def _adapt_for_environment(self) -> None:
        """Adapt configuration based on deployment environment"""
        if not self.config:
            return
        
        env = self.config.deployment.environment
        
        if env == Environment.DEVELOPMENT:
            # Development environment adaptations
            self.config.deployment.debug_mode = True
            self.config.deployment.enable_hot_reload = True
            self.config.monitoring.log_level = "DEBUG"
            self.config.ai.timeout_seconds = 60  # Longer timeout for debugging
            
        elif env == Environment.STAGING:
            # Staging environment adaptations
            self.config.deployment.debug_mode = False
            self.config.deployment.enable_hot_reload = False
            self.config.monitoring.log_level = "INFO"
            self.config.monitoring.enable_metrics = True
            
        elif env == Environment.PRODUCTION:
            # Production environment adaptations
            self.config.deployment.debug_mode = False
            self.config.deployment.enable_hot_reload = False
            self.config.monitoring.log_level = "WARNING"
            self.config.monitoring.enable_metrics = True
            self.config.security.enable_encryption = True
            self.config.security.enable_audit_logging = True
            self.config.security.enable_rate_limiting = True
            
        elif env == Environment.TESTING:
            # Testing environment adaptations
            self.config.deployment.debug_mode = True
            self.config.monitoring.log_level = "DEBUG"
            self.config.memory.enable_user_memory = False  # Don't persist during tests
            self.config.api.enable_caching = False  # Fresh data for tests
        
        self.logger.info(f"Applied environment-specific adaptations for: {env.value}")
    
    def get_config(self) -> BotConfiguration:
        """Get current configuration"""
        if not self.config:
            raise ConfigurationError("Configuration not loaded. Call load_configuration() first.")
        return self.config
    
    async def reload_configuration(self) -> BotConfiguration:
        """Reload configuration from all sources"""
        self.logger.info("Reloading configuration...")
        return await self.load_configuration()
    
    def get_validation_errors(self) -> List[str]:
        """Get configuration validation errors"""
        return self.validation_errors.copy()
    
    def export_config(self, file_path: str, format: str = "json") -> None:
        """Export current configuration to file"""
        if not self.config:
            raise ConfigurationError("No configuration to export")
        
        # Convert config to dictionary
        config_dict = {
            "discord": {
                "token": "***REDACTED***",  # Don't export sensitive data
                "command_prefix": self.config.discord.command_prefix,
                "auto_reply_on_mention": self.config.discord.auto_reply_on_mention,
                "auto_reply_on_reply": self.config.discord.auto_reply_on_reply,
                "max_message_length": self.config.discord.max_message_length,
                "embed_color": self.config.discord.embed_color,
                "status_message": self.config.discord.status_message,
                "activity_type": self.config.discord.activity_type
            },
            "ai": {
                "model_name": self.config.ai.model_name,
                "model_path": self.config.ai.model_path,
                "max_context_length": self.config.ai.max_context_length,
                "temperature": self.config.ai.temperature,
                "top_p": self.config.ai.top_p,
                "max_tokens": self.config.ai.max_tokens,
                "timeout_seconds": self.config.ai.timeout_seconds,
                "enable_streaming": self.config.ai.enable_streaming
            },
            "deployment": {
                "environment": self.config.deployment.environment.value,
                "debug_mode": self.config.deployment.debug_mode,
                "enable_hot_reload": self.config.deployment.enable_hot_reload,
                "graceful_shutdown_timeout": self.config.deployment.graceful_shutdown_timeout,
                "max_concurrent_requests": self.config.deployment.max_concurrent_requests,
                "worker_threads": self.config.deployment.worker_threads,
                "enable_container_mode": self.config.deployment.enable_container_mode
            }
            # Add other sections as needed, excluding sensitive data
        }
        
        try:
            with open(file_path, 'w', encoding='utf-8') as f:
                if format.lower() == "yaml":
                    yaml.dump(config_dict, f, default_flow_style=False, indent=2)
                else:
                    json.dump(config_dict, f, indent=2)
            
            self.logger.info(f"Configuration exported to: {file_path}")
            
        except Exception as e:
            error_msg = f"Failed to export configuration: {str(e)}"
            self.logger.error(error_msg)
            raise ConfigurationError(error_msg) from e
    
    def get_config_summary(self) -> Dict[str, Any]:
        """Get a summary of current configuration (without sensitive data)"""
        if not self.config:
            return {"status": "not_loaded"}
        
        return {
            "status": "loaded",
            "environment": self.config.deployment.environment.value,
            "debug_mode": self.config.deployment.debug_mode,
            "discord_prefix": self.config.discord.command_prefix,
            "ai_model": self.config.ai.model_name,
            "memory_enabled": self.config.memory.enable_user_memory,
            "rag_enabled": self.config.knowledge.enable_rag,
            "security_enabled": self.config.security.enable_encryption,
            "metrics_enabled": self.config.monitoring.enable_metrics,
            "log_level": self.config.monitoring.log_level,
            "validation_errors": len(self.validation_errors)
        }