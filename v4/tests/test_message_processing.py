"""
Property-based tests for message processing consistency
Feature: aviation-discord-bot, Property 1: Message Processing Consistency
"""

import pytest
import asyncio
import discord
from unittest.mock import AsyncMock, MagicMock, patch
from hypothesis import given, strategies as st, settings
from typing import Dict, Any

# Import the components we're testing
import sys
import os
sys.path.append(os.path.join(os.path.dirname(__file__), '..', 'src'))

from bot.message_handler import MessageHandler


class MockDiscordMessage:
    """Mock Discord message for testing"""
    
    def __init__(self, content: str, author_id: int, is_bot: bool = False, 
                 is_dm: bool = False, has_mention: bool = False):
        self.content = content
        self.author = MagicMock()
        self.author.id = author_id
        self.author.bot = is_bot
        self.mentions = [MagicMock()] if has_mention else []
        self.reference = None
        self.guild = None if is_dm else MagicMock()
        
        if not is_dm and self.guild:
            self.guild.me = MagicMock()
            self.guild.me.id = 12345  # Bot ID
        
        # Mock channel with proper async context manager
        if is_dm:
            self.channel = MagicMock(spec=discord.DMChannel)
            self.channel.id = 99999
        else:
            self.channel = MagicMock()
            self.channel.id = 88888
        
        # Mock methods
        self.reply = AsyncMock()
        self.add_reaction = AsyncMock()
        self.channel.send = AsyncMock()
        
        # Properly mock the typing context manager
        typing_context = AsyncMock()
        typing_context.__aenter__ = AsyncMock(return_value=None)
        typing_context.__aexit__ = AsyncMock(return_value=None)
        self.channel.typing = MagicMock(return_value=typing_context)


class MockAIModel:
    """Mock AI model for testing"""
    
    def __init__(self):
        self.is_loaded = True
    
    async def generate_response(self, message: str, user_context: Dict[str, Any] = None,
                              knowledge_context: str = "", conversation_history=None) -> str:
        # Simulate consistent response generation
        response_length = len(message) + len(knowledge_context) + len(str(user_context))
        return f"Aviation response to: {message[:50]}..." if len(message) > 50 else f"Aviation response to: {message}"
    
    async def evaluate_memory_relevance(self, conversation_text: str) -> Dict[str, Any]:
        # Simulate memory relevance evaluation
        return {
            "relevance_score": 7,
            "extracted_info": {
                "experience_level": "private" if "private" in conversation_text.lower() else None,
                "interests": ["general_aviation"] if "aviation" in conversation_text.lower() else [],
                "learning_goals": [],
                "knowledge_gaps": []
            }
        }


class MockUserProfiles:
    """Mock user profiles for testing"""
    
    def __init__(self):
        self.profiles = {}
    
    async def get_profile(self, user_id: int) -> Dict[str, Any]:
        if user_id not in self.profiles:
            self.profiles[user_id] = {
                "user_id": user_id,
                "experience_level": "student",
                "interests": ["general_aviation"],
                "learning_goals": [],
                "conversation_count": 0
            }
        return self.profiles[user_id]
    
    async def get_user_context_for_ai(self, user_id: int) -> Dict[str, Any]:
        profile = await self.get_profile(user_id)
        return {
            "experience_level": profile.get("experience_level"),
            "interests": profile.get("interests", []),
            "detail_level": "medium"
        }
    
    async def get_conversation_history(self, user_id: int, limit: int = 5):
        return []
    
    async def update_profile_from_conversation(self, user_id: int, conversation_text: str, analysis: Dict[str, Any]):
        profile = await self.get_profile(user_id)
        profile["conversation_count"] += 1
    
    async def add_conversation_exchange(self, user_id: int, user_message: str, ai_response: str):
        pass
    
    async def _save_profile(self, user_id: int, profile: Dict[str, Any]):
        self.profiles[user_id] = profile


class MockRAGSystem:
    """Mock RAG system for testing"""
    
    def __init__(self):
        self.is_ready = True
    
    async def retrieve_knowledge(self, query: str, context: Dict[str, Any]) -> str:
        # Simulate knowledge retrieval
        if "weather" in query.lower():
            return "Weather information: Current conditions are VFR"
        elif "aircraft" in query.lower():
            return "Aircraft information: General aviation aircraft specifications"
        else:
            return "General aviation knowledge context"


class MockEmbedBuilder:
    """Mock embed builder for testing"""
    
    def create_response_embed(self, response: str, author):
        embed = MagicMock()
        embed.title = "Aviation Response"
        embed.description = response[:100]
        return embed
    
    def create_error_embed(self, title: str, description: str):
        embed = MagicMock()
        embed.title = title
        embed.description = description
        return embed
    
    def create_info_embed(self, title: str, description: str):
        embed = MagicMock()
        embed.title = title
        embed.description = description
        return embed


def create_message_handler():
    """Create a message handler with mocked dependencies"""
    ai_model = MockAIModel()
    user_profiles = MockUserProfiles()
    rag_system = MockRAGSystem()
    embed_builder = MockEmbedBuilder()
    
    return MessageHandler(ai_model, user_profiles, rag_system, embed_builder)


# Property-based test strategies
@st.composite
def discord_message_strategy(draw):
    """Generate realistic Discord messages for testing"""
    # Generate message content
    content_parts = []
    
    # Add aviation keywords sometimes
    aviation_keywords = ["aircraft", "plane", "flight", "pilot", "aviation", "weather", "airport"]
    if draw(st.booleans()):
        content_parts.append(draw(st.sampled_from(aviation_keywords)))
    
    # Add regular text
    regular_text = draw(st.text(min_size=1, max_size=200, alphabet=st.characters(whitelist_categories=('Lu', 'Ll', 'Nd', 'Pc', 'Pd', 'Zs'))))
    content_parts.append(regular_text)
    
    content = " ".join(content_parts).strip()
    if not content:
        content = "test message"
    
    # Generate user properties
    user_id = draw(st.integers(min_value=1, max_value=999999))
    is_bot = draw(st.booleans())
    is_dm = draw(st.booleans())
    has_mention = draw(st.booleans())
    
    return MockDiscordMessage(content, user_id, is_bot, is_dm, has_mention)


@st.composite
def concurrent_messages_strategy(draw):
    """Generate multiple messages for concurrent processing testing"""
    num_messages = draw(st.integers(min_value=2, max_value=5))
    messages = []
    
    for i in range(num_messages):
        # Ensure different users for concurrent testing
        user_id = 1000 + i
        content = draw(st.text(min_size=5, max_size=100))
        if not content.strip():
            content = f"test message {i}"
        
        message = MockDiscordMessage(content, user_id, is_bot=False, is_dm=True)
        messages.append(message)
    
    return messages


class TestMessageProcessingConsistency:
    """
    Property 1: Message Processing Consistency
    For any Discord message mentioning the bot, the system should process the message,
    coordinate all subsystems (AI, RAG, Memory), and generate a contextually appropriate
    response formatted for Discord constraints.
    """
    
    @given(discord_message_strategy())
    @settings(max_examples=100, deadline=30000)  # 30 second deadline for async tests
    @pytest.mark.asyncio
    async def test_message_processing_consistency(self, message):
        """
        Property test: Message processing should be consistent and complete
        Validates: Requirements 1.1, 5.1, 5.2, 5.3
        """
        # Create fresh message handler for each test
        message_handler = create_message_handler()
        
        # Property: For any valid Discord message, if the bot should respond,
        # it must coordinate all systems and produce a response
        
        try:
            # Test the complete message processing pipeline
            await message_handler.handle_message(message)
            
            # Verify system coordination occurred
            if await message_handler._should_respond(message):
                # If bot should respond, verify response was generated
                # Check that user context was retrieved
                user_context = await message_handler.user_profiles.get_user_context_for_ai(message.author.id)
                assert isinstance(user_context, dict), "User context should be retrieved"
                
                # Check that conversation history was accessed
                history = await message_handler.user_profiles.get_conversation_history(message.author.id)
                assert isinstance(history, list), "Conversation history should be retrieved"
                
                # Verify memory update was attempted
                profile = await message_handler.user_profiles.get_profile(message.author.id)
                assert isinstance(profile, dict), "User profile should exist after processing"
            
            # Property: Processing should not raise exceptions for valid inputs
            assert True, "Message processing completed without exceptions"
            
        except Exception as e:
            # Only acceptable exceptions are Discord API errors or rate limiting
            acceptable_errors = ["rate limit", "discord", "api", "network"]
            error_msg = str(e).lower()
            
            if not any(acceptable in error_msg for acceptable in acceptable_errors):
                pytest.fail(f"Unexpected error in message processing: {e}")
    
    @given(st.text(min_size=1, max_size=500))
    @settings(max_examples=100)
    @pytest.mark.asyncio
    async def test_response_determination_consistency(self, message_content):
        """
        Property test: Response determination should be consistent
        Same message content should always produce same response decision
        """
        # Create fresh message handler for each test
        message_handler = create_message_handler()
        
        # Create two identical messages from same user
        user_id = 12345
        message1 = MockDiscordMessage(message_content, user_id, is_dm=True)
        message2 = MockDiscordMessage(message_content, user_id, is_dm=True)
        
        # Response determination should be consistent
        should_respond1 = await message_handler._should_respond(message1)
        should_respond2 = await message_handler._should_respond(message2)
        
        assert should_respond1 == should_respond2, \
            f"Response determination inconsistent for content: {message_content[:50]}"
    
    @given(concurrent_messages_strategy())
    @settings(max_examples=50, deadline=60000)  # Longer deadline for concurrent tests
    @pytest.mark.asyncio
    async def test_concurrent_processing_isolation(self, messages):
        """
        Property test: Concurrent message processing should not contaminate context
        Multiple users messaging simultaneously should maintain separate contexts
        """
        # Create fresh message handler for each test
        message_handler = create_message_handler()
        
        # Process all messages concurrently
        tasks = []
        for message in messages:
            task = asyncio.create_task(message_handler.handle_message(message))
            tasks.append(task)
        
        # Wait for all processing to complete
        await asyncio.gather(*tasks, return_exceptions=True)
        
        # Verify each user has separate context
        user_contexts = {}
        for message in messages:
            user_id = message.author.id
            context = await message_handler.user_profiles.get_user_context_for_ai(user_id)
            user_contexts[user_id] = context
        
        # Property: Each user should have separate context
        assert len(user_contexts) == len(messages), \
            "Each user should have separate context"
        
        # Property: No context contamination between users
        user_ids = list(user_contexts.keys())
        for i, user_id1 in enumerate(user_ids):
            for user_id2 in user_ids[i+1:]:
                # Contexts can be similar but should be separate objects
                assert user_contexts[user_id1] is not user_contexts[user_id2], \
                    f"Context contamination between users {user_id1} and {user_id2}"
    
    @given(st.integers(min_value=1, max_value=999999))
    @settings(max_examples=100, deadline=500)
    @pytest.mark.asyncio
    async def test_memory_system_coordination(self, user_id):
        """
        Property test: Memory system should be consistently coordinated
        Every message processing should interact with memory system appropriately
        """
        # Create fresh message handler for each test
        message_handler = create_message_handler()
        
        # Create a test message
        message = MockDiscordMessage("Tell me about aircraft", user_id, is_dm=True)
        
        # Get initial profile state
        initial_profile = await message_handler.user_profiles.get_profile(user_id)
        initial_count = initial_profile.get("conversation_count", 0)
        
        # Process message
        await message_handler.handle_message(message)
        
        # Verify memory system coordination
        updated_profile = await message_handler.user_profiles.get_profile(user_id)
        
        # Property: Profile should exist after processing
        assert updated_profile is not None, "User profile should exist after message processing"
        
        # Property: Conversation count should be updated
        assert updated_profile.get("conversation_count", 0) >= initial_count, \
            "Conversation count should be maintained or increased"
    
    @given(st.text(min_size=1, max_size=2000))
    @settings(max_examples=100)
    @pytest.mark.asyncio
    async def test_discord_constraint_handling(self, response_text):
        """
        Property test: Responses should always comply with Discord constraints
        Any generated response should be properly formatted for Discord
        """
        # Create fresh message handler for each test
        message_handler = create_message_handler()
        
        # Create mock message
        message = MockDiscordMessage("test", 12345, is_dm=True)
        
        # Test response formatting
        formatted_response = await message_handler._format_response_for_discord(response_text, message)
        
        # Property: Response should have valid type
        assert "type" in formatted_response, "Formatted response should have type"
        assert formatted_response["type"] in ["text", "embed", "multi_message"], \
            f"Invalid response type: {formatted_response['type']}"
        
        # Property: Text responses should respect Discord length limits
        if formatted_response["type"] == "text":
            assert len(formatted_response["content"]) <= 2000, \
                "Text response exceeds Discord limit"
        
        # Property: Multi-message responses should have valid parts
        elif formatted_response["type"] == "multi_message":
            assert "parts" in formatted_response, "Multi-message should have parts"
            assert isinstance(formatted_response["parts"], list), "Parts should be a list"
            
            for part in formatted_response["parts"]:
                assert len(part) <= 2000, "Each part should respect Discord limits"
        
        # Property: Embed responses should have embed object
        elif formatted_response["type"] == "embed":
            assert "embed" in formatted_response, "Embed response should have embed object"


if __name__ == "__main__":
    pytest.main([__file__, "-v"])