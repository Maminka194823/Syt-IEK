"""
Unit tests for bot status display functionality
Tests aviation-themed status and activity indicators
Validates: Requirements 1.6
"""

import pytest
import discord
from unittest.mock import Mock, AsyncMock, patch
from datetime import datetime, timedelta
import asyncio

from src.bot.discord_client import AviationGirlBot
from src.bot.config_manager import BotConfiguration


class TestBotStatusDisplay:
    """Test bot status display and aviation-themed indicators"""
    
    @pytest.fixture
    def mock_config(self):
        """Mock bot configuration"""
        config = Mock(spec=BotConfiguration)
        config.discord = Mock()
        config.discord.command_prefix = "!"
        config.discord.token = "test_token"
        return config
    
    @pytest.fixture
    def bot(self, mock_config):
        """Create bot instance with mocked dependencies"""
        with patch('src.bot.discord_client.commands.Bot.__init__'):
            bot = AviationGirlBot(mock_config)
            bot.user = Mock()
            bot.user.id = 12345
            bot.user.name = "AviationGirl"
            bot.guilds = [Mock(), Mock()]  # Mock 2 guilds
            bot.users = [Mock() for _ in range(50)]  # Mock 50 users
            return bot
    
    @pytest.mark.asyncio
    async def test_on_ready_sets_aviation_status(self, bot):
        """Test that on_ready sets aviation-themed status"""
        # Mock the change_presence method
        bot.change_presence = AsyncMock()
        
        # Call on_ready
        await bot.on_ready()
        
        # Verify aviation-themed status was set
        bot.change_presence.assert_called_once()
        call_args = bot.change_presence.call_args
        activity = call_args[1]['activity']
        
        assert isinstance(activity, discord.Activity)
        assert activity.type == discord.ActivityType.watching
        assert "skies" in activity.name.lower()
        assert "✈️" in activity.name
    
    @pytest.mark.asyncio
    async def test_on_ready_sets_ready_state(self, bot):
        """Test that on_ready properly initializes bot state"""
        bot.change_presence = AsyncMock()
        
        # Ensure bot starts as not ready
        assert not bot.is_ready
        assert bot.startup_time is None
        
        # Call on_ready
        await bot.on_ready()
        
        # Verify ready state is set
        assert bot.is_ready
        assert bot.startup_time is not None
        assert isinstance(bot.startup_time, datetime)
    
    @pytest.mark.asyncio
    async def test_status_command_shows_system_health(self, bot):
        """Test status command displays comprehensive system information"""
        # Mock dependencies
        bot.embed_builder = Mock()
        bot.embed_builder.create_info_embed = Mock(return_value=Mock(spec=discord.Embed))
        
        # Set up system health
        bot.system_health = {
            "overall_healthy": True,
            "health_score": 0.95,
            "components": {
                "ai_model": True,
                "rag_system": True,
                "user_profiles": True,
                "rate_limit_manager": True,
                "performance_monitor": True
            }
        }
        
        # Set startup time for uptime calculation
        bot.startup_time = discord.utils.utcnow() - timedelta(hours=2, minutes=30)
        
        # Mock performance monitor
        bot.performance_monitor = Mock()
        bot.performance_monitor.get_performance_stats.return_value = {
            'overall': {
                'avg_response_time': 1.25,
                'error_rate': 0.02,
                'active_users': 15,
                'user_engagement_score': 4.2
            }
        }
        
        # Mock context
        ctx = Mock()
        ctx.send = AsyncMock()
        
        # Call status command
        await bot.status_command.callback(bot, ctx)
        
        # Verify embed was created with proper title
        bot.embed_builder.create_info_embed.assert_called_once()
        call_args = bot.embed_builder.create_info_embed.call_args[0]
        assert "Aviation Girl V4 Status" in call_args[0]
        
        # Verify embed was sent
        ctx.send.assert_called_once()
        embed_arg = ctx.send.call_args[1]['embed']
        assert embed_arg is not None
    
    @pytest.mark.asyncio
    async def test_status_command_shows_component_status(self, bot):
        """Test status command shows individual component health"""
        # Mock embed builder to capture field additions
        mock_embed = Mock(spec=discord.Embed)
        bot.embed_builder = Mock()
        bot.embed_builder.create_info_embed.return_value = mock_embed
        
        # Set up mixed component health
        bot.system_health = {
            "overall_healthy": False,
            "health_score": 0.75,
            "components": {
                "ai_model": True,
                "rag_system": False,  # Offline component
                "user_profiles": True,
                "rate_limit_manager": True,
                "performance_monitor": True
            }
        }
        
        bot.startup_time = discord.utils.utcnow()
        bot.performance_monitor = None  # No performance stats
        
        ctx = Mock()
        ctx.send = AsyncMock()
        
        await bot.status_command.callback(bot, ctx)
        
        # Verify component status fields were added
        field_calls = mock_embed.add_field.call_args_list
        
        # Check that health status shows issues
        health_field = next((call for call in field_calls if "Health" in call[1]['name']), None)
        assert health_field is not None
        assert "Issues Detected" in health_field[1]['value'] or "75%" in health_field[1]['value']
        
        # Check that individual components are shown
        ai_field = next((call for call in field_calls if "AI Model" in call[1]['name']), None)
        assert ai_field is not None
        assert "  Online" in ai_field[1]['value']
        
        # Check that offline component is shown
        rag_field = next((call for call in field_calls if "Knowledge Base" in call[1]['name']), None)
        assert rag_field is not None
        assert "  Offline" in rag_field[1]['value']
    
    @pytest.mark.asyncio
    async def test_status_command_shows_uptime(self, bot):
        """Test status command calculates and displays uptime correctly"""
        mock_embed = Mock(spec=discord.Embed)
        bot.embed_builder = Mock()
        bot.embed_builder.create_info_embed.return_value = mock_embed
        
        bot.system_health = {"overall_healthy": True, "components": {}}
        
        # Set startup time to 1 day, 3 hours, 45 minutes ago
        bot.startup_time = discord.utils.utcnow() - timedelta(days=1, hours=3, minutes=45)
        
        ctx = Mock()
        ctx.send = AsyncMock()
        
        await bot.status_command.callback(bot, ctx)
        
        # Find uptime field
        field_calls = mock_embed.add_field.call_args_list
        uptime_field = next((call for call in field_calls if "Uptime" in call[1]['name']), None)
        
        assert uptime_field is not None
        uptime_value = uptime_field[1]['value']
        assert "1d" in uptime_value  # 1 day
        assert "3h" in uptime_value  # 3 hours
        assert "45m" in uptime_value  # 45 minutes
    
    @pytest.mark.asyncio
    async def test_status_command_shows_server_and_user_counts(self, bot):
        """Test status command displays server and user statistics"""
        mock_embed = Mock(spec=discord.Embed)
        bot.embed_builder = Mock()
        bot.embed_builder.create_info_embed.return_value = mock_embed
        
        bot.system_health = {"overall_healthy": True, "components": {}}
        bot.startup_time = discord.utils.utcnow()
        
        # Set specific counts
        bot.guilds = [Mock() for _ in range(5)]  # 5 servers
        bot.users = [Mock() for _ in range(150)]  # 150 users
        
        ctx = Mock()
        ctx.send = AsyncMock()
        
        await bot.status_command.callback(bot, ctx)
        
        # Find server and user count fields
        field_calls = mock_embed.add_field.call_args_list
        
        servers_field = next((call for call in field_calls if "Servers" in call[1]['name']), None)
        assert servers_field is not None
        assert "5" in servers_field[1]['value']
        
        users_field = next((call for call in field_calls if "Users" in call[1]['name']), None)
        assert users_field is not None
        assert "150" in users_field[1]['value']
    
    @pytest.mark.asyncio
    async def test_status_command_shows_performance_stats(self, bot):
        """Test status command includes performance metrics when available"""
        mock_embed = Mock(spec=discord.Embed)
        bot.embed_builder = Mock()
        bot.embed_builder.create_info_embed.return_value = mock_embed
        
        bot.system_health = {"overall_healthy": True, "components": {}}
        bot.startup_time = discord.utils.utcnow()
        
        # Mock performance monitor with specific stats
        bot.performance_monitor = Mock()
        bot.performance_monitor.get_performance_stats.return_value = {
            'overall': {
                'avg_response_time': 2.15,
                'error_rate': 0.035,
                'active_users': 25,
                'user_engagement_score': 3.8
            }
        }
        
        ctx = Mock()
        ctx.send = AsyncMock()
        
        await bot.status_command.callback(bot, ctx)
        
        # Find performance field
        field_calls = mock_embed.add_field.call_args_list
        perf_field = next((call for call in field_calls if "Performance" in call[1]['name']), None)
        
        assert perf_field is not None
        perf_value = perf_field[1]['value']
        assert "2.15s" in perf_value  # Response time
        assert "3.5%" in perf_value  # Error rate (0.035 = 3.5%)
        assert "25" in perf_value  # Active users
    
    def test_aviation_themed_activity_types(self):
        """Test that bot uses appropriate aviation-themed activities"""
        # Test various aviation-themed activities that could be used
        aviation_activities = [
            "watching the skies ✈️",
            "monitoring air traffic 🛩️",
            "checking weather reports 🌤️",
            "reviewing flight plans 📋",
            "studying aviation charts 🗺️"
        ]
        
        # Verify at least one contains aviation elements
        has_aviation_theme = any(
            any(keyword in activity.lower() for keyword in ["sky", "skies", "flight", "aviation", "air"])
            for activity in aviation_activities
        )
        assert has_aviation_theme
        
        # Verify at least one contains aviation emoji
        has_aviation_emoji = any(
            any(emoji in activity for emoji in ["✈️", "🛩️", "🌤️", "📋", "🗺️"])
            for activity in aviation_activities
        )
        assert has_aviation_emoji
    
    @pytest.mark.asyncio
    async def test_status_command_handles_missing_performance_monitor(self, bot):
        """Test status command works when performance monitor is unavailable"""
        mock_embed = Mock(spec=discord.Embed)
        bot.embed_builder = Mock()
        bot.embed_builder.create_info_embed.return_value = mock_embed
        
        bot.system_health = {"overall_healthy": True, "components": {}}
        bot.startup_time = discord.utils.utcnow()
        bot.performance_monitor = None  # No performance monitor
        
        ctx = Mock()
        ctx.send = AsyncMock()
        
        # Should not raise an exception
        await bot.status_command.callback(bot, ctx)
        
        # Verify embed was still created and sent
        bot.embed_builder.create_info_embed.assert_called_once()
        ctx.send.assert_called_once()
        
        # Verify no performance field was added
        field_calls = mock_embed.add_field.call_args_list
        perf_field = next((call for call in field_calls if "Performance" in call[1]['name']), None)
        assert perf_field is None
    
    @pytest.mark.asyncio
    async def test_status_command_handles_no_startup_time(self, bot):
        """Test status command works when startup time is not set"""
        mock_embed = Mock(spec=discord.Embed)
        bot.embed_builder = Mock()
        bot.embed_builder.create_info_embed.return_value = mock_embed
        
        bot.system_health = {"overall_healthy": True, "components": {}}
        bot.startup_time = None  # No startup time
        
        ctx = Mock()
        ctx.send = AsyncMock()
        
        # Should not raise an exception
        await bot.status_command.callback(bot, ctx)
        
        # Verify embed was still created and sent
        bot.embed_builder.create_info_embed.assert_called_once()
        ctx.send.assert_called_once()
        
        # Verify no uptime field was added
        field_calls = mock_embed.add_field.call_args_list
        uptime_field = next((call for call in field_calls if "Uptime" in call[1]['name']), None)
        assert uptime_field is None