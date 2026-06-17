"""
Unit tests for configuration support functionality
Tests environment variable and config file support
Validates: Requirements 12.1
"""

import pytest
import os
import json
import yaml
import tempfile
from unittest.mock import Mock, patch, mock_open
from pathlib import Path

from src.bot.config_manager import (
    BotConfiguration, ConfigManager, DiscordConfig, AIConfig, MemoryConfig,
    KnowledgeConfig, SecurityConfig, APIConfig, MonitoringConfig, DeploymentConfig,
    Environment, ConfigurationError
)


class TestConfigurationSupport:
    """Test configuration support including environment variables and config files"""
    
    @pytest.fixture
    def config_manager(self):
        """Create config manager instance"""
        return ConfigManager()
    
    @pytest.fixture
    def sample_config_dict(self):
        """Sample configuration dictionary"""
        return {
            "discord": {
                "token": "test_discord_token",
                "command_prefix": "!",
                "auto_reply_on_mention": True,
                "max_message_length": 2000,
                "embed_color": 0x1E90FF,
                "status_message": "Flying high! ✈️",
                "activity_type": "watching"
            },
            "ai": {
                "model_name": "qwen2.5",
                "temperature": 0.7,
                "max_context_length": 4096,
                "timeout_seconds": 30
            },
            "memory": {
                "enable_user_memory": True,
                "max_conversation_history": 50,
                "memory_retention_days": 30
            },
            "knowledge": {
                "enable_rag": True,
                "max_search_results": 5,
                "similarity_threshold": 0.7
            },
            "security": {
                "enable_encryption": True,
                "enable_audit_logging": True,
                "session_timeout_minutes": 60
            },
            "api": {
                "aviation_weather_api_key": "test_weather_key",
                "flight_tracking_api_key": "test_flight_key",
                "faa_api_key": "test_faa_key"
            },
            "monitoring": {
                "enable_metrics": True,
                "log_level": "INFO",
                "metrics_port": 8080
            },
            "deployment": {
                "environment": "development",
                "debug_mode": True,
                "enable_hot_reload": True
            }
        }
    
    @pytest.fixture
    def temp_config_file(self, sample_config_dict):
        """Create temporary config file"""
        with tempfile.NamedTemporaryFile(mode='w', suffix='.json', delete=False) as f:
            json.dump(sample_config_dict, f)
            temp_file = f.name
        
        yield temp_file
        
        # Cleanup
        if os.path.exists(temp_file):
            os.unlink(temp_file)
    
    def test_discord_config_creation(self):
        """Test DiscordConfig creation with various parameters"""
        # Test with minimal parameters
        config = DiscordConfig(token="test_token")
        assert config.token == "test_token"
        assert config.command_prefix == "!"
        assert config.auto_reply_on_mention == True
        assert config.max_message_length == 2000
        assert config.embed_color == 0x1E90FF
        
        # Test with custom parameters
        custom_config = DiscordConfig(
            token="custom_token",
            command_prefix="?",
            auto_reply_on_mention=False,
            max_message_length=1500,
            embed_color=0xFF0000,
            status_message="Custom status",
            activity_type="playing"
        )
        assert custom_config.token == "custom_token"
        assert custom_config.command_prefix == "?"
        assert custom_config.auto_reply_on_mention == False
        assert custom_config.max_message_length == 1500
        assert custom_config.embed_color == 0xFF0000
        assert custom_config.status_message == "Custom status"
        assert custom_config.activity_type == "playing"
    
    def test_ai_config_creation(self):
        """Test AIConfig creation with various parameters"""
        # Test with defaults
        config = AIConfig()
        assert config.model_name == "qwen2.5"
        assert config.temperature == 0.7
        assert config.max_context_length == 4096
        assert config.timeout_seconds == 30
        
        # Test with custom parameters
        custom_config = AIConfig(
            model_name="custom_model",
            temperature=0.9,
            max_context_length=8192,
            timeout_seconds=60,
            enable_streaming=True
        )
        assert custom_config.model_name == "custom_model"
        assert custom_config.temperature == 0.9
        assert custom_config.max_context_length == 8192
        assert custom_config.timeout_seconds == 60
        assert custom_config.enable_streaming == True
    
    def test_environment_enum_values(self):
        """Test Environment enum values"""
        assert Environment.DEVELOPMENT.value == "development"
        assert Environment.STAGING.value == "staging"
        assert Environment.PRODUCTION.value == "production"
        assert Environment.TESTING.value == "testing"
        
        # Test enum creation from string
        assert Environment("development") == Environment.DEVELOPMENT
        assert Environment("production") == Environment.PRODUCTION
    
    def test_config_manager_initialization(self):
        """Test ConfigManager initialization"""
        # Test with default parameters
        manager = ConfigManager()
        assert manager.config_file is None
        assert manager.config is None
        assert manager.env_prefix == "AVIATION_BOT_"
        assert len(manager.config_search_paths) > 0
        
        # Test with custom config file
        custom_manager = ConfigManager(config_file="custom_config.json")
        assert custom_manager.config_file == "custom_config.json"
    
    def test_environment_variable_loading(self, config_manager):
        """Test loading configuration from environment variables"""
        env_vars = {
            "AVIATION_BOT_DISCORD_TOKEN": "env_discord_token",
            "AVIATION_BOT_DISCORD_PREFIX": "?",
            "AVIATION_BOT_DISCORD_STATUS": "Custom Status",
            "AVIATION_BOT_AI_MODEL": "custom_model",
            "AVIATION_BOT_AI_TEMPERATURE": "0.9",
            "AVIATION_BOT_WEATHER_API_KEY": "env_weather_key",
            "AVIATION_BOT_FLIGHT_API_KEY": "env_flight_key",
            "AVIATION_BOT_FAA_API_KEY": "env_faa_key",
            "AVIATION_BOT_ENVIRONMENT": "production",
            "AVIATION_BOT_DEBUG": "false",
            "AVIATION_BOT_LOG_LEVEL": "WARNING",
            "AVIATION_BOT_METRICS_PORT": "9090"
        }
        
        with patch.dict(os.environ, env_vars):
            env_config = config_manager._load_env_config()
            
            # Verify Discord configuration
            assert env_config["discord"]["token"] == "env_discord_token"
            assert env_config["discord"]["command_prefix"] == "?"
            assert env_config["discord"]["status_message"] == "Custom Status"
            
            # Verify AI configuration
            assert env_config["ai"]["model_name"] == "custom_model"
            assert env_config["ai"]["temperature"] == 0.9
            
            # Verify API configuration
            assert env_config["api"]["aviation_weather_api_key"] == "env_weather_key"
            assert env_config["api"]["flight_tracking_api_key"] == "env_flight_key"
            assert env_config["api"]["faa_api_key"] == "env_faa_key"
            
            # Verify deployment configuration
            assert env_config["deployment"]["environment"] == "production"
            assert env_config["deployment"]["debug_mode"] == False
            
            # Verify monitoring configuration
            assert env_config["monitoring"]["log_level"] == "WARNING"
            assert env_config["monitoring"]["metrics_port"] == 9090
    
    def test_environment_variable_loading_with_no_vars(self, config_manager):
        """Test environment variable loading when no variables are set"""
        # Clear any existing environment variables
        env_vars_to_clear = [key for key in os.environ.keys() if key.startswith("AVIATION_BOT_")]
        
        with patch.dict(os.environ, {}, clear=False):
            for var in env_vars_to_clear:
                if var in os.environ:
                    del os.environ[var]
            
            env_config = config_manager._load_env_config()
            
            # Should return empty dict when no environment variables are set
            assert env_config == {}
    
    @pytest.mark.asyncio
    async def test_config_file_loading_json(self, config_manager, temp_config_file):
        """Test loading configuration from JSON file"""
        config_manager.config_file = temp_config_file
        
        file_config = await config_manager._load_config_file()
        
        assert file_config is not None
        assert file_config["discord"]["token"] == "test_discord_token"
        assert file_config["ai"]["model_name"] == "qwen2.5"
        assert file_config["deployment"]["environment"] == "development"
    
    @pytest.mark.asyncio
    async def test_config_file_loading_yaml(self, config_manager, sample_config_dict):
        """Test loading configuration from YAML file"""
        with tempfile.NamedTemporaryFile(mode='w', suffix='.yaml', delete=False) as f:
            yaml.dump(sample_config_dict, f)
            temp_yaml_file = f.name
        
        try:
            config_manager.config_file = temp_yaml_file
            
            file_config = await config_manager._load_config_file()
            
            assert file_config is not None
            assert file_config["discord"]["token"] == "test_discord_token"
            assert file_config["ai"]["model_name"] == "qwen2.5"
            
        finally:
            if os.path.exists(temp_yaml_file):
                os.unlink(temp_yaml_file)
    
    @pytest.mark.asyncio
    async def test_config_file_loading_nonexistent_file(self, config_manager):
        """Test loading configuration from nonexistent file"""
        config_manager.config_file = "/nonexistent/config.json"
        
        file_config = await config_manager._load_config_file()
        
        # Should return None for nonexistent file
        assert file_config is None
    
    @pytest.mark.asyncio
    async def test_config_file_loading_invalid_json(self, config_manager):
        """Test loading configuration from invalid JSON file"""
        with tempfile.NamedTemporaryFile(mode='w', suffix='.json', delete=False) as f:
            f.write("{ invalid json content")
            temp_file = f.name
        
        try:
            config_manager.config_file = temp_file
            
            with pytest.raises(ConfigurationError):
                await config_manager._load_config_file()
                
        finally:
            if os.path.exists(temp_file):
                os.unlink(temp_file)
    
    def test_config_merging(self, config_manager):
        """Test configuration merging functionality"""
        base_config = {
            "discord": {
                "token": "base_token",
                "command_prefix": "!",
                "embed_color": 0x1E90FF
            },
            "ai": {
                "model_name": "base_model",
                "temperature": 0.7
            }
        }
        
        override_config = {
            "discord": {
                "token": "override_token",
                "command_prefix": "?"
                # embed_color not specified, should keep base value
            },
            "ai": {
                "temperature": 0.9
                # model_name not specified, should keep base value
            },
            "new_section": {
                "new_value": "test"
            }
        }
        
        merged = config_manager._merge_configs(base_config, override_config)
        
        # Verify overridden values
        assert merged["discord"]["token"] == "override_token"
        assert merged["discord"]["command_prefix"] == "?"
        assert merged["ai"]["temperature"] == 0.9
        
        # Verify preserved values
        assert merged["discord"]["embed_color"] == 0x1E90FF
        assert merged["ai"]["model_name"] == "base_model"
        
        # Verify new section
        assert merged["new_section"]["new_value"] == "test"
    
    def test_config_object_creation(self, config_manager, sample_config_dict):
        """Test creating BotConfiguration object from dictionary"""
        config = config_manager._create_config_object(sample_config_dict)
        
        assert isinstance(config, BotConfiguration)
        assert isinstance(config.discord, DiscordConfig)
        assert isinstance(config.ai, AIConfig)
        assert isinstance(config.memory, MemoryConfig)
        assert isinstance(config.knowledge, KnowledgeConfig)
        assert isinstance(config.security, SecurityConfig)
        assert isinstance(config.api, APIConfig)
        assert isinstance(config.monitoring, MonitoringConfig)
        assert isinstance(config.deployment, DeploymentConfig)
        
        # Verify values
        assert config.discord.token == "test_discord_token"
        assert config.ai.model_name == "qwen2.5"
        assert config.deployment.environment == Environment.DEVELOPMENT
    
    def test_config_object_creation_with_invalid_data(self, config_manager):
        """Test config object creation with invalid data"""
        invalid_config = {
            "discord": {
                # Missing required token
                "command_prefix": "!"
            },
            "ai": {},
            "memory": {},
            "knowledge": {},
            "security": {},
            "api": {},
            "monitoring": {},
            "deployment": {
                "environment": "development"
            }
        }
        
        with pytest.raises(ConfigurationError):
            config_manager._create_config_object(invalid_config)
    
    @pytest.mark.asyncio
    async def test_full_configuration_loading(self, config_manager, temp_config_file):
        """Test complete configuration loading process"""
        # Set up environment variables to override some file values
        env_vars = {
            "AVIATION_BOT_DISCORD_TOKEN": "env_override_token",
            "AVIATION_BOT_AI_TEMPERATURE": "0.8",
            "AVIATION_BOT_ENVIRONMENT": "staging"
        }
        
        config_manager.config_file = temp_config_file
        
        with patch.dict(os.environ, env_vars):
            config = await config_manager.load_configuration()
            
            # Verify environment variables took precedence
            assert config.discord.token == "env_override_token"
            assert config.ai.temperature == 0.8
            assert config.deployment.environment == Environment.STAGING
            
            # Verify file values were used where no env override
            assert config.discord.command_prefix == "!"
            assert config.ai.model_name == "qwen2.5"
    
    @pytest.mark.asyncio
    async def test_configuration_loading_with_missing_required_values(self, config_manager):
        """Test configuration loading fails with missing required values"""
        # Create config without required Discord token
        incomplete_config = {
            "discord": {
                "command_prefix": "!"
                # Missing token
            },
            "ai": {"model_name": "test"},
            "memory": {},
            "knowledge": {},
            "security": {},
            "api": {},
            "monitoring": {},
            "deployment": {"environment": "development"}
        }
        
        with tempfile.NamedTemporaryFile(mode='w', suffix='.json', delete=False) as f:
            json.dump(incomplete_config, f)
            temp_file = f.name
        
        try:
            config_manager.config_file = temp_file
            
            with pytest.raises(ConfigurationError):
                await config_manager.load_configuration()
                
        finally:
            if os.path.exists(temp_file):
                os.unlink(temp_file)
    
    def test_config_export_json(self, config_manager, sample_config_dict):
        """Test configuration export to JSON file"""
        # Load configuration first
        config_manager.config = config_manager._create_config_object(sample_config_dict)
        
        with tempfile.NamedTemporaryFile(mode='w', suffix='.json', delete=False) as f:
            export_file = f.name
        
        try:
            config_manager.export_config(export_file, format="json")
            
            # Verify file was created and contains expected data
            assert os.path.exists(export_file)
            
            with open(export_file, 'r') as f:
                exported_data = json.load(f)
            
            # Verify structure (token should be redacted)
            assert exported_data["discord"]["token"] == "***REDACTED***"
            assert exported_data["discord"]["command_prefix"] == "!"
            assert exported_data["ai"]["model_name"] == "qwen2.5"
            assert exported_data["deployment"]["environment"] == "development"
            
        finally:
            if os.path.exists(export_file):
                os.unlink(export_file)
    
    def test_config_export_yaml(self, config_manager, sample_config_dict):
        """Test configuration export to YAML file"""
        config_manager.config = config_manager._create_config_object(sample_config_dict)
        
        with tempfile.NamedTemporaryFile(mode='w', suffix='.yaml', delete=False) as f:
            export_file = f.name
        
        try:
            config_manager.export_config(export_file, format="yaml")
            
            # Verify file was created and contains expected data
            assert os.path.exists(export_file)
            
            with open(export_file, 'r') as f:
                exported_data = yaml.safe_load(f)
            
            # Verify structure
            assert exported_data["discord"]["token"] == "***REDACTED***"
            assert exported_data["ai"]["model_name"] == "qwen2.5"
            
        finally:
            if os.path.exists(export_file):
                os.unlink(export_file)
    
    def test_config_export_without_loaded_config(self, config_manager):
        """Test configuration export fails without loaded config"""
        with pytest.raises(ConfigurationError):
            config_manager.export_config("test.json")
    
    def test_config_summary(self, config_manager, sample_config_dict):
        """Test configuration summary generation"""
        # Test without loaded config
        summary = config_manager.get_config_summary()
        assert summary["status"] == "not_loaded"
        
        # Test with loaded config
        config_manager.config = config_manager._create_config_object(sample_config_dict)
        
        summary = config_manager.get_config_summary()
        assert summary["status"] == "loaded"
        assert summary["environment"] == "development"
        assert summary["discord_prefix"] == "!"
        assert summary["ai_model"] == "qwen2.5"
        assert summary["memory_enabled"] == True
        assert summary["rag_enabled"] == True
        assert summary["security_enabled"] == True
        assert "validation_errors" in summary
    
    def test_validation_errors_tracking(self, config_manager):
        """Test validation error tracking"""
        # Initially no errors
        assert len(config_manager.get_validation_errors()) == 0
        
        # Add some validation errors
        config_manager.validation_errors.append("Test error 1")
        config_manager.validation_errors.append("Test error 2")
        
        errors = config_manager.get_validation_errors()
        assert len(errors) == 2
        assert "Test error 1" in errors
        assert "Test error 2" in errors
        
        # Verify it returns a copy (not the original list)
        errors.append("Test error 3")
        assert len(config_manager.get_validation_errors()) == 2
    
    @pytest.mark.asyncio
    async def test_configuration_reload(self, config_manager, temp_config_file):
        """Test configuration reloading"""
        config_manager.config_file = temp_config_file
        
        # Load initial configuration
        config1 = await config_manager.load_configuration()
        assert config1.discord.token == "test_discord_token"
        
        # Modify the config file
        modified_config = {
            "discord": {"token": "modified_token", "command_prefix": "?"},
            "ai": {"model_name": "modified_model"},
            "memory": {},
            "knowledge": {},
            "security": {},
            "api": {},
            "monitoring": {},
            "deployment": {"environment": "production"}
        }
        
        with open(temp_config_file, 'w') as f:
            json.dump(modified_config, f)
        
        # Reload configuration
        config2 = await config_manager.reload_configuration()
        assert config2.discord.token == "modified_token"
        assert config2.discord.command_prefix == "?"
        assert config2.ai.model_name == "modified_model"
        assert config2.deployment.environment == Environment.PRODUCTION
    
    def test_config_search_paths(self, config_manager):
        """Test configuration file search paths"""
        search_paths = config_manager.config_search_paths
        
        # Verify common search paths are included
        assert any("bot_config.json" in path for path in search_paths)
        assert any("bot_config.yaml" in path for path in search_paths)
        assert any(".aviation_bot" in path for path in search_paths)
        
        # Verify paths include both local and user home directories
        local_paths = [path for path in search_paths if not path.startswith(os.path.expanduser("~"))]
        user_paths = [path for path in search_paths if path.startswith(os.path.expanduser("~"))]
        
        assert len(local_paths) > 0
        assert len(user_paths) > 0
    
    def test_environment_specific_adaptations(self, config_manager, sample_config_dict):
        """Test environment-specific configuration adaptations"""
        # Test development environment
        dev_config_dict = sample_config_dict.copy()
        dev_config_dict["deployment"]["environment"] = "development"
        
        config = config_manager._create_config_object(dev_config_dict)
        assert config.deployment.environment == Environment.DEVELOPMENT
        
        # Test production environment
        prod_config_dict = sample_config_dict.copy()
        prod_config_dict["deployment"]["environment"] = "production"
        
        config = config_manager._create_config_object(prod_config_dict)
        assert config.deployment.environment == Environment.PRODUCTION
    
    def test_sensitive_data_handling(self, config_manager, sample_config_dict):
        """Test that sensitive data is handled properly"""
        config_manager.config = config_manager._create_config_object(sample_config_dict)
        
        # Export config and verify sensitive data is redacted
        with tempfile.NamedTemporaryFile(mode='w', suffix='.json', delete=False) as f:
            export_file = f.name
        
        try:
            config_manager.export_config(export_file)
            
            with open(export_file, 'r') as f:
                exported_data = json.load(f)
            
            # Verify Discord token is redacted
            assert exported_data["discord"]["token"] == "***REDACTED***"
            
            # Verify summary doesn't contain sensitive data
            summary = config_manager.get_config_summary()
            assert "token" not in str(summary).lower()
            
        finally:
            if os.path.exists(export_file):
                os.unlink(export_file)