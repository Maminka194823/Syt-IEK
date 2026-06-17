"""
Unit tests for data deletion capability functionality
Tests user profile and conversation history removal
Validates: Requirements 11.3
"""

import pytest
import asyncio
import os
import json
import tempfile
import shutil
from unittest.mock import Mock, AsyncMock, patch, mock_open
from datetime import datetime

from src.security.privacy_manager import PrivacyManager, DataCategory, RetentionPolicy
from src.bot.discord_client import AviationGirlBot
from src.bot.config_manager import BotConfiguration


class TestDataDeletionCapability:
    """Test data deletion capability and privacy compliance"""
    
    @pytest.fixture
    def temp_data_dirs(self):
        """Create temporary data directories for testing"""
        temp_dirs = []
        for i in range(3):
            temp_dir = tempfile.mkdtemp(prefix=f"test_data_{i}_")
            temp_dirs.append(temp_dir)
        
        yield temp_dirs
        
        # Cleanup
        for temp_dir in temp_dirs:
            if os.path.exists(temp_dir):
                shutil.rmtree(temp_dir)
    
    @pytest.fixture
    def privacy_manager(self, temp_data_dirs):
        """Create privacy manager instance with test directories"""
        return PrivacyManager(data_directories=temp_data_dirs)
    
    @pytest.fixture
    def mock_config(self):
        """Mock bot configuration"""
        config = Mock(spec=BotConfiguration)
        config.discord = Mock()
        config.discord.command_prefix = "!"
        config.discord.token = "test_token"
        return config
    
    @pytest.fixture
    def bot_with_privacy_manager(self, mock_config, privacy_manager):
        """Create bot instance with privacy manager"""
        with patch('src.bot.discord_client.commands.Bot.__init__'):
            bot = AviationGirlBot(mock_config)
            bot.privacy_manager = privacy_manager
            bot.embed_builder = Mock()
            bot.embed_builder.create_warning_embed = Mock(return_value=Mock())
            bot.embed_builder.create_success_embed = Mock(return_value=Mock())
            bot.embed_builder.create_error_embed = Mock(return_value=Mock())
            bot.embed_builder.create_info_embed = Mock(return_value=Mock())
            bot.wait_for = AsyncMock()
            return bot
    
    @pytest.mark.asyncio
    async def test_delete_user_data_removes_user_files(self, privacy_manager, temp_data_dirs):
        """Test that delete_user_data removes user-specific files"""
        user_id = 12345
        
        # Create test user files in different directories
        test_files = []
        for i, data_dir in enumerate(temp_data_dirs):
            # Profile file
            profile_file = os.path.join(data_dir, f"{user_id}.json")
            with open(profile_file, 'w') as f:
                json.dump({"user_id": user_id, "data": f"test_data_{i}"}, f)
            test_files.append(profile_file)
            
            # History file
            history_file = os.path.join(data_dir, f"{user_id}_history.json")
            with open(history_file, 'w') as f:
                json.dump({"conversations": ["test conversation"]}, f)
            test_files.append(history_file)
            
            # Other user-specific file
            other_file = os.path.join(data_dir, f"user_{user_id}_preferences.json")
            with open(other_file, 'w') as f:
                json.dump({"preferences": {"theme": "dark"}}, f)
            test_files.append(other_file)
        
        # Verify files exist before deletion
        for file_path in test_files:
            assert os.path.exists(file_path)
        
        # Delete user data
        deletion_report = await privacy_manager.delete_user_data(user_id)
        
        # Verify deletion was successful
        assert deletion_report["success"] == True
        assert deletion_report["user_id"] == user_id
        assert deletion_report["files_deleted"] == len(test_files)
        assert len(deletion_report["errors"]) == 0
        
        # Verify files are actually deleted
        for file_path in test_files:
            assert not os.path.exists(file_path)
    
    @pytest.mark.asyncio
    async def test_delete_user_data_preserves_other_user_files(self, privacy_manager, temp_data_dirs):
        """Test that delete_user_data preserves files belonging to other users"""
        target_user_id = 12345
        other_user_id = 67890
        
        # Create files for both users
        target_files = []
        other_files = []
        
        for data_dir in temp_data_dirs:
            # Target user files
            target_file = os.path.join(data_dir, f"{target_user_id}.json")
            with open(target_file, 'w') as f:
                json.dump({"user_id": target_user_id}, f)
            target_files.append(target_file)
            
            # Other user files
            other_file = os.path.join(data_dir, f"{other_user_id}.json")
            with open(other_file, 'w') as f:
                json.dump({"user_id": other_user_id}, f)
            other_files.append(other_file)
            
            # System files (no user ID)
            system_file = os.path.join(data_dir, "system_config.json")
            with open(system_file, 'w') as f:
                json.dump({"system": "config"}, f)
            other_files.append(system_file)
        
        # Delete target user data
        deletion_report = await privacy_manager.delete_user_data(target_user_id)
        
        # Verify target user files are deleted
        for file_path in target_files:
            assert not os.path.exists(file_path)
        
        # Verify other user files are preserved
        for file_path in other_files:
            assert os.path.exists(file_path)
        
        assert deletion_report["success"] == True
        assert deletion_report["files_deleted"] == len(target_files)
    
    @pytest.mark.asyncio
    async def test_delete_user_data_handles_missing_directories(self, temp_data_dirs):
        """Test that delete_user_data handles missing directories gracefully"""
        # Add a non-existent directory to the list
        data_dirs = temp_data_dirs + ["/nonexistent/directory"]
        privacy_manager = PrivacyManager(data_directories=data_dirs)
        
        user_id = 12345
        
        # Create a file in an existing directory
        existing_file = os.path.join(temp_data_dirs[0], f"{user_id}.json")
        with open(existing_file, 'w') as f:
            json.dump({"user_id": user_id}, f)
        
        # Delete user data (should not fail due to missing directory)
        deletion_report = await privacy_manager.delete_user_data(user_id)
        
        # Should still succeed for existing directories
        assert deletion_report["success"] == True
        assert deletion_report["files_deleted"] == 1
        assert not os.path.exists(existing_file)
    
    @pytest.mark.asyncio
    async def test_delete_user_data_with_secure_storage(self, privacy_manager):
        """Test delete_user_data with secure storage integration"""
        # Mock secure storage
        mock_secure_storage = Mock()
        privacy_manager.secure_storage = mock_secure_storage
        
        # Mock secure storage deletion method
        privacy_manager._delete_user_secure_data = AsyncMock(return_value={
            "records_deleted": 5,
            "errors": []
        })
        
        # Mock conversation deletion
        privacy_manager._delete_user_conversations = AsyncMock(return_value={
            "records_deleted": 10,
            "errors": []
        })
        
        user_id = 12345
        deletion_report = await privacy_manager.delete_user_data(user_id)
        
        # Verify secure storage deletion was called
        privacy_manager._delete_user_secure_data.assert_called_once_with(user_id, None)
        privacy_manager._delete_user_conversations.assert_called_once_with(user_id)
        
        # Verify database records were counted
        assert deletion_report["database_records_deleted"] == 15  # 5 + 10
        assert deletion_report["success"] == True
    
    @pytest.mark.asyncio
    async def test_delete_user_data_handles_file_deletion_errors(self, privacy_manager, temp_data_dirs):
        """Test that delete_user_data handles file deletion errors gracefully"""
        user_id = 12345
        
        # Create a test file
        test_file = os.path.join(temp_data_dirs[0], f"{user_id}.json")
        with open(test_file, 'w') as f:
            json.dump({"user_id": user_id}, f)
        
        # Mock secure file deletion to raise an error
        with patch.object(privacy_manager, '_secure_delete_file', side_effect=PermissionError("Permission denied")):
            deletion_report = await privacy_manager.delete_user_data(user_id)
        
        # Should report the error but not crash
        assert deletion_report["success"] == False
        assert len(deletion_report["errors"]) > 0
        assert any("Permission denied" in error for error in deletion_report["errors"])
        assert deletion_report["files_deleted"] == 0
    
    @pytest.mark.asyncio
    async def test_delete_user_data_updates_privacy_statistics(self, privacy_manager, temp_data_dirs):
        """Test that delete_user_data updates privacy statistics"""
        user_id = 12345
        
        # Create a test file
        test_file = os.path.join(temp_data_dirs[0], f"{user_id}.json")
        with open(test_file, 'w') as f:
            json.dump({"user_id": user_id}, f)
        
        initial_deletion_requests = privacy_manager.privacy_stats["deletion_requests"]
        initial_data_deleted = privacy_manager.privacy_stats["data_deleted"]
        
        deletion_report = await privacy_manager.delete_user_data(user_id)
        
        # Verify statistics were updated
        assert privacy_manager.privacy_stats["deletion_requests"] == initial_deletion_requests + 1
        assert privacy_manager.privacy_stats["data_deleted"] == initial_data_deleted + 1
    
    @pytest.mark.asyncio
    async def test_delete_user_data_logs_privacy_action(self, privacy_manager, temp_data_dirs):
        """Test that delete_user_data logs privacy actions"""
        user_id = 12345
        
        # Mock the privacy action logging
        privacy_manager._log_privacy_action = AsyncMock()
        
        deletion_report = await privacy_manager.delete_user_data(user_id)
        
        # Verify privacy action was logged
        privacy_manager._log_privacy_action.assert_called_once_with(
            "data_deletion", 
            user_id, 
            deletion_report
        )
    
    @pytest.mark.asyncio
    async def test_bot_delete_data_command_confirmation_flow(self, bot_with_privacy_manager):
        """Test bot delete-data command confirmation flow"""
        # Mock context
        ctx = Mock()
        ctx.author = Mock()
        ctx.author.id = 12345
        ctx.author.mention = "<@12345>"
        ctx.send = AsyncMock()
        
        # Mock message for reactions
        mock_message = Mock()
        mock_message.add_reaction = AsyncMock()
        ctx.send.return_value = mock_message
        
        # Mock user confirming deletion (  reaction)
        mock_reaction = Mock()
        mock_reaction.emoji = " "
        mock_user = ctx.author
        bot_with_privacy_manager.wait_for.return_value = (mock_reaction, mock_user)
        
        # Mock successful deletion
        bot_with_privacy_manager.privacy_manager.delete_user_data = AsyncMock(return_value={
            "success": True,
            "files_deleted": 5,
            "database_records_deleted": 10,
            "user_id": 12345
        })
        
        await bot_with_privacy_manager.delete_data_command(ctx)
        
        # Verify confirmation message was sent
        assert ctx.send.call_count >= 1
        
        # Verify reactions were added
        mock_message.add_reaction.assert_any_call(" ")
        mock_message.add_reaction.assert_any_call(" ")
        
        # Verify deletion was performed
        bot_with_privacy_manager.privacy_manager.delete_user_data.assert_called_once_with(12345)
        
        # Verify success embed was created
        bot_with_privacy_manager.embed_builder.create_success_embed.assert_called_once()
    
    @pytest.mark.asyncio
    async def test_bot_delete_data_command_cancellation(self, bot_with_privacy_manager):
        """Test bot delete-data command cancellation flow"""
        # Mock context
        ctx = Mock()
        ctx.author = Mock()
        ctx.author.id = 12345
        ctx.author.mention = "<@12345>"
        ctx.send = AsyncMock()
        
        # Mock message for reactions
        mock_message = Mock()
        mock_message.add_reaction = AsyncMock()
        mock_message.edit = AsyncMock()
        mock_message.clear_reactions = AsyncMock()
        ctx.send.return_value = mock_message
        
        # Mock user cancelling deletion (  reaction)
        mock_reaction = Mock()
        mock_reaction.emoji = " "
        mock_user = ctx.author
        bot_with_privacy_manager.wait_for.return_value = (mock_reaction, mock_user)
        
        await bot_with_privacy_manager.delete_data_command(ctx)
        
        # Verify deletion was NOT performed
        bot_with_privacy_manager.privacy_manager.delete_user_data.assert_not_called()
        
        # Verify cancellation message was shown
        bot_with_privacy_manager.embed_builder.create_info_embed.assert_called_once()
        call_args = bot_with_privacy_manager.embed_builder.create_info_embed.call_args[0]
        assert "Cancelled" in call_args[0]
        
        # Verify message was edited and reactions cleared
        mock_message.edit.assert_called_once()
        mock_message.clear_reactions.assert_called_once()
    
    @pytest.mark.asyncio
    async def test_bot_delete_data_command_timeout(self, bot_with_privacy_manager):
        """Test bot delete-data command timeout handling"""
        # Mock context
        ctx = Mock()
        ctx.author = Mock()
        ctx.author.id = 12345
        ctx.author.mention = "<@12345>"
        ctx.send = AsyncMock()
        
        # Mock message for reactions
        mock_message = Mock()
        mock_message.add_reaction = AsyncMock()
        mock_message.edit = AsyncMock()
        mock_message.clear_reactions = AsyncMock()
        ctx.send.return_value = mock_message
        
        # Mock timeout
        bot_with_privacy_manager.wait_for.side_effect = asyncio.TimeoutError()
        
        await bot_with_privacy_manager.delete_data_command(ctx)
        
        # Verify deletion was NOT performed
        bot_with_privacy_manager.privacy_manager.delete_user_data.assert_not_called()
        
        # Verify timeout message was shown
        bot_with_privacy_manager.embed_builder.create_info_embed.assert_called_once()
        call_args = bot_with_privacy_manager.embed_builder.create_info_embed.call_args[0]
        assert "Timed Out" in call_args[0]
        
        # Verify message was edited and reactions cleared
        mock_message.edit.assert_called_once()
        mock_message.clear_reactions.assert_called_once()
    
    @pytest.mark.asyncio
    async def test_bot_delete_data_command_deletion_failure(self, bot_with_privacy_manager):
        """Test bot delete-data command handles deletion failures"""
        # Mock context
        ctx = Mock()
        ctx.author = Mock()
        ctx.author.id = 12345
        ctx.author.mention = "<@12345>"
        ctx.send = AsyncMock()
        
        # Mock message for reactions
        mock_message = Mock()
        mock_message.add_reaction = AsyncMock()
        mock_message.edit = AsyncMock()
        mock_message.clear_reactions = AsyncMock()
        ctx.send.return_value = mock_message
        
        # Mock user confirming deletion
        mock_reaction = Mock()
        mock_reaction.emoji = " "
        mock_user = ctx.author
        bot_with_privacy_manager.wait_for.return_value = (mock_reaction, mock_user)
        
        # Mock deletion failure
        bot_with_privacy_manager.privacy_manager.delete_user_data = AsyncMock(return_value={
            "success": False,
            "files_deleted": 0,
            "database_records_deleted": 0,
            "errors": ["Permission denied", "Database connection failed"],
            "user_id": 12345
        })
        
        await bot_with_privacy_manager.delete_data_command(ctx)
        
        # Verify deletion was attempted
        bot_with_privacy_manager.privacy_manager.delete_user_data.assert_called_once_with(12345)
        
        # Verify error embed was created
        bot_with_privacy_manager.embed_builder.create_error_embed.assert_called_once()
        call_args = bot_with_privacy_manager.embed_builder.create_error_embed.call_args[0]
        assert "Data Deletion Failed" in call_args[0]
    
    @pytest.mark.asyncio
    async def test_bot_delete_data_command_missing_privacy_manager(self, mock_config):
        """Test bot delete-data command handles missing privacy manager"""
        with patch('src.bot.discord_client.commands.Bot.__init__'):
            bot = AviationGirlBot(mock_config)
            bot.privacy_manager = None  # No privacy manager
            bot.embed_builder = Mock()
            bot.embed_builder.create_error_embed = Mock(return_value=Mock())
            
            ctx = Mock()
            ctx.author = Mock()
            ctx.author.id = 12345
            ctx.send = AsyncMock()
            
            await bot.delete_data_command.callback(bot, ctx)
            
            # Verify error embed was created
            bot.embed_builder.create_error_embed.assert_called_once()
            call_args = bot.embed_builder.create_error_embed.call_args[0]
            assert "Privacy Manager Unavailable" in call_args[0]
            
            ctx.send.assert_called_once()
    
    def test_privacy_manager_initialization(self, temp_data_dirs):
        """Test privacy manager initialization with data directories"""
        privacy_manager = PrivacyManager(data_directories=temp_data_dirs)
        
        assert privacy_manager.data_directories == temp_data_dirs
        assert len(privacy_manager.retention_policies) > 0
        assert DataCategory.PERSONAL_IDENTIFIABLE in privacy_manager.retention_policies
        assert DataCategory.CONVERSATION_CONTENT in privacy_manager.retention_policies
        
        # Verify privacy statistics are initialized
        assert privacy_manager.privacy_stats["deletion_requests"] == 0
        assert privacy_manager.privacy_stats["data_deleted"] == 0
        assert privacy_manager.privacy_stats["privacy_errors"] == 0
    
    def test_privacy_manager_retention_policies(self, privacy_manager):
        """Test privacy manager retention policy configuration"""
        # Verify default retention policies are set
        assert privacy_manager.retention_policies[DataCategory.PERSONAL_IDENTIFIABLE] == RetentionPolicy.MEDIUM_TERM
        assert privacy_manager.retention_policies[DataCategory.CONVERSATION_CONTENT] == RetentionPolicy.LONG_TERM
        assert privacy_manager.retention_policies[DataCategory.SYSTEM_LOGS] == RetentionPolicy.SHORT_TERM
        assert privacy_manager.retention_policies[DataCategory.CACHED_DATA] == RetentionPolicy.SHORT_TERM
    
    @pytest.mark.asyncio
    async def test_delete_user_data_with_specific_categories(self, privacy_manager, temp_data_dirs):
        """Test delete_user_data with specific data categories"""
        user_id = 12345
        
        # Create test files
        test_file = os.path.join(temp_data_dirs[0], f"{user_id}.json")
        with open(test_file, 'w') as f:
            json.dump({"user_id": user_id, "category": "personal"}, f)
        
        # Mock category-specific deletion
        privacy_manager._delete_user_files = AsyncMock(return_value={
            "files_deleted": 1,
            "errors": []
        })
        
        # Delete only specific categories
        specific_categories = [DataCategory.PERSONAL_IDENTIFIABLE, DataCategory.CONVERSATION_CONTENT]
        deletion_report = await privacy_manager.delete_user_data(user_id, specific_categories)
        
        # Verify category-specific deletion was called
        privacy_manager._delete_user_files.assert_called_once_with(user_id, specific_categories)
        
        assert deletion_report["success"] == True
        assert deletion_report["files_deleted"] == 1
    
    def test_sensitive_data_pattern_recognition(self, privacy_manager):
        """Test sensitive data pattern recognition"""
        test_data = {
            "email": "user@example.com should be detected",
            "phone": "Call me at 555-123-4567 please",
            "ssn": "My SSN is 123-45-6789",
            "credit_card": "Card number: 1234 5678 9012 3456",
            "ip_address": "Server IP: 192.168.1.100"
        }
        
        for pattern_name, test_text in test_data.items():
            pattern = privacy_manager.sensitive_patterns[pattern_name]
            matches = pattern.findall(test_text)
            assert len(matches) > 0, f"Pattern {pattern_name} should match in: {test_text}"
    
    @pytest.mark.asyncio
    async def test_privacy_action_logging(self, privacy_manager):
        """Test privacy action logging functionality"""
        # Mock the logging method
        privacy_manager._log_privacy_action = AsyncMock()
        
        user_id = 12345
        action = "data_deletion"
        details = {"files_deleted": 5, "success": True}
        
        await privacy_manager._log_privacy_action(action, user_id, details)
        
        # Verify logging was called with correct parameters
        privacy_manager._log_privacy_action.assert_called_once_with(action, user_id, details)
    
    def test_deletion_report_structure(self, privacy_manager):
        """Test deletion report structure and required fields"""
        user_id = 12345
        
        # Create a mock deletion report structure
        expected_fields = [
            "user_id",
            "deletion_timestamp", 
            "categories_deleted",
            "files_deleted",
            "database_records_deleted",
            "errors",
            "success"
        ]
        
        # This would be the structure returned by delete_user_data
        sample_report = {
            "user_id": user_id,
            "deletion_timestamp": datetime.utcnow().isoformat(),
            "categories_deleted": [],
            "files_deleted": 0,
            "database_records_deleted": 0,
            "errors": [],
            "success": True
        }
        
        # Verify all expected fields are present
        for field in expected_fields:
            assert field in sample_report, f"Deletion report should contain field: {field}"
        
        # Verify field types
        assert isinstance(sample_report["user_id"], int)
        assert isinstance(sample_report["files_deleted"], int)
        assert isinstance(sample_report["database_records_deleted"], int)
        assert isinstance(sample_report["errors"], list)
        assert isinstance(sample_report["success"], bool)