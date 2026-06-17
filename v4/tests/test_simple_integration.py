"""
Simple Integration Test for Aviation Girl V4 Discord Bot
Basic test to verify system components can be imported and initialized
"""

import pytest
import tempfile
import shutil
import json
import os
from unittest.mock import AsyncMock, MagicMock, patch


def test_system_imports():
    """Test that all system components can be imported"""
    try:
        from v4.src.bot.discord_client import AviationGirlBot
        from v4.src.bot.config_manager import BotConfiguration
        from v4.src.ai.model_loader import AIModelManager
        from v4.src.ai.ai_orchestrator import AIOrchestrator
        from v4.src.memory.user_profiles import UserProfileManager
        from v4.src.knowledge.rag_system import RAGSystem
        from v4.src.bot.message_handler import MessageHandler
        from v4.src.bot.embed_builder import EmbedBuilder
        
        # If we get here, all imports succeeded
        assert True
    except ImportError as e:
        pytest.fail(f"Failed to import system components: {e}")


def test_basic_bot_creation():
    """Test basic bot creation with minimal config"""
    from v4.src.bot.discord_client import AviationGirlBot
    from v4.src.bot.config_manager import BotConfiguration, DiscordConfig, ConfigManager
    
    # Create minimal config
    temp_dir = tempfile.mkdtemp()
    try:
        config_data = {
            "discord": {
                "token": "test_token",
                "command_prefix": "!",
                "max_message_length": 2000
            },
            "ai": {
                "model_name": "test_model",
                "max_tokens": 1000,
                "temperature": 0.7
            },
            "data": {
                "storage_path": temp_dir,
                "knowledge_base_path": os.path.join(temp_dir, "knowledge"),
                "user_profiles_path": os.path.join(temp_dir, "profiles")
            }
        }
        
        config_file = os.path.join(temp_dir, "config.json")
        with open(config_file, 'w') as f:
            json.dump(config_data, f)
        
        # Create config using ConfigManager
        config_manager = ConfigManager(config_file)
        
        # Create a simple config directly for testing
        discord_config = DiscordConfig(token="test_token")
        config = BotConfiguration(discord=discord_config)
        
        # Create bot instance
        bot = AviationGirlBot(config)
        
        # Verify bot was created
        assert bot is not None
        assert bot.config == config
        
    finally:
        shutil.rmtree(temp_dir)


@pytest.mark.asyncio
async def test_basic_system_initialization():
    """Test basic system initialization"""
    from v4.src.bot.discord_client import AviationGirlBot
    from v4.src.bot.config_manager import BotConfiguration, DiscordConfig, ConfigManager
    
    # Create minimal config
    temp_dir = tempfile.mkdtemp()
    try:
        config_data = {
            "discord": {
                "token": "test_token",
                "command_prefix": "!",
                "max_message_length": 2000
            },
            "ai": {
                "model_name": "test_model",
                "max_tokens": 1000,
                "temperature": 0.7
            },
            "data": {
                "storage_path": temp_dir,
                "knowledge_base_path": os.path.join(temp_dir, "knowledge"),
                "user_profiles_path": os.path.join(temp_dir, "profiles")
            }
        }
        
        config_file = os.path.join(temp_dir, "config.json")
        with open(config_file, 'w') as f:
            json.dump(config_data, f)
        
        # Create config using ConfigManager
        config_manager = ConfigManager(config_file)
        
        # Create a simple config directly for testing
        discord_config = DiscordConfig(token="test_token")
        config = BotConfiguration(discord=discord_config)
        bot = AviationGirlBot(config)
        
        # Mock external dependencies
        with patch.multiple(
            'v4.src.ai.model_loader.AIModelManager',
            load_model=AsyncMock(),
            generate_response=AsyncMock(return_value="Test response")
        ), patch.multiple(
            'v4.src.knowledge.aviation_data.AviationDataManager',
            get_weather=AsyncMock(return_value={"metar": "Test METAR"})
        ):
            # Test setup hook (system initialization)
            await bot.setup_hook()
            
            # Verify systems were initialized
            assert bot.embed_builder is not None
            
    finally:
        shutil.rmtree(temp_dir)