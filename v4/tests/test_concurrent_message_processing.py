"""
Property-based tests for concurrent message processing
Feature: aviation-discord-bot, Property 7: Concurrent Message Processing
"""

import pytest
import asyncio
import discord
from unittest.mock import AsyncMock, MagicMock, patch
from hypothesis import given, strategies as st, settings
from typing import Dict, Any, List
import time
import threading
from concurrent.futures import ThreadPoolExecutor

# Import the components we're testing
import sys
import os
sys.path.append(os.path.join(os.path.dirname(__file__), '..', 'src'))

from bot.message_handler import MessageHandler


class MockDiscordMessage:
    """Mock Discord message for testing"""
    
    def __init__(self, content: str, author_id: int, guild_id: int = None, 
                 channel_id: int = None, is_bot: bool = False, is_dm: bool = False):
        self.content = content
        self.author = MagicMock()
        self.author.id = author_id
        self.author.bot = is_bot
        self.mentions = []
        self.reference = None
        
        # Guild and channel setup
        if is_dm:
            self.guild = None
            self.channel = MagicMock(spec=discord.DMChannel)
            self.channel.id = channel_id or (90000 + author_id)
        else:
            self.guild = MagicMock()
            self.guild.id = guild_id or 12345
            self.guild.me = MagicMock()
            self.guild.me.id = 99999  # Bot ID
            self.channel = MagicMock()
            self.channel.id = channel_id or (80000 + author_id)
        
        # Mock async methods
        self.reply = AsyncMock()
        self.add_reaction = AsyncMock()
        self.channel.send = AsyncMock()
        
        # Mock typing context manager
        typing_context = AsyncMock()
        typing_context.__aenter__ = AsyncMock(return_value=None)
        typing_context.__aexit__ = AsyncMock(return_value=None)
        self.channel.typing = MagicMock(return_value=typing_context)
        
        # Add timestamp for ordering
        self.created_at = MagicMock()
        self.created_at.timestamp = MagicMock(return_value=time.time())


class ThreadSafeCounter:
    """Thread-safe counter for tracking concurrent operations"""
    
    def __init__(self):
        self._value = 0
        self._lock = threading.Lock()
    
    def increment(self):
        with self._lock:
            self._value += 1
            return self._value
    
    def get_value(self):
        with self._lock:
            return self._value


class MockAIModel:
    """Mock AI model that tracks concurrent access"""
    
    def __init__(self):
        self.is_loaded = True
        self.concurrent_calls = ThreadSafeCounter()
        self.max_concurrent = 0
        self.call_history = []
        self._lock = threading.Lock()
    
    async def generate_response(self, message: str, user_context: Dict[str, Any] = None,
                              knowledge_context: str = "", conversation_history=None) -> str:
        # Track concurrent access
        current_concurrent = self.concurrent_calls.increment()
        self.max_concurrent = max(self.max_concurrent, current_concurrent)
        
        # Record call details
        with self._lock:
            self.call_history.append({
                "message": message,
                "user_context": user_context,
                "thread_id": threading.get_ident(),
                "timestamp": time.time()
            })
        
        # Simulate processing time
        await asyncio.sleep(0.01)
        
        # Generate response based on user context to test isolation
        user_id = user_context.get("user_id", "unknown") if user_context else "unknown"
        response = f"Response for user {user_id}: {message[:30]}"
        
        # Decrement counter
        self.concurrent_calls._value -= 1
        
        return response
    
    async def evaluate_memory_relevance(self, conversation_text: str) -> Dict[str, Any]:
        return {
            "relevance_score": 6,
            "extracted_info": {
                "experience_level": None,
                "interests": [],
                "learning_goals": [],
                "knowledge_gaps": []
            }
        }


class MockUserProfiles:
    """Mock user profiles that tracks concurrent access per user"""
    
    def __init__(self):
        self.profiles = {}
        self.access_history = {}  # user_id -> list of access times
        self._lock = threading.Lock()
    
    async def get_profile(self, user_id: int) -> Dict[str, Any]:
        with self._lock:
            # Track access
            if user_id not in self.access_history:
                self.access_history[user_id] = []
            self.access_history[user_id].append({
                "action": "get_profile",
                "timestamp": time.time(),
                "thread_id": threading.get_ident()
            })
            
            # Create profile if doesn't exist
            if user_id not in self.profiles:
                self.profiles[user_id] = {
                    "user_id": user_id,
                    "experience_level": "student",
                    "interests": [f"aviation_{user_id}"],  # Unique per user
                    "learning_goals": [],
                    "conversation_count": 0,
                    "created_thread": threading.get_ident()
                }
        
        return self.profiles[user_id].copy()  # Return copy to prevent contamination
    
    async def get_user_context_for_ai(self, user_id: int) -> Dict[str, Any]:
        profile = await self.get_profile(user_id)
        return {
            "user_id": user_id,  # Include user_id for isolation testing
            "experience_level": profile.get("experience_level"),
            "interests": profile.get("interests", []),
            "detail_level": "medium",
            "thread_context": threading.get_ident()
        }
    
    async def get_conversation_history(self, user_id: int, limit: int = 5):
        # Return user-specific history
        return [{"user": f"Previous message from {user_id}", "assistant": f"Previous response to {user_id}"}]
    
    async def update_profile_from_conversation(self, user_id: int, conversation_text: str, analysis: Dict[str, Any]):
        with self._lock:
            # Track update
            if user_id not in self.access_history:
                self.access_history[user_id] = []
            self.access_history[user_id].append({
                "action": "update_profile",
                "timestamp": time.time(),
                "thread_id": threading.get_ident(),
                "conversation_length": len(conversation_text)
            })
            
            # Update profile
            if user_id in self.profiles:
                self.profiles[user_id]["conversation_count"] += 1
                self.profiles[user_id]["last_update_thread"] = threading.get_ident()
    
    async def add_conversation_exchange(self, user_id: int, user_message: str, ai_response: str):
        with self._lock:
            if user_id not in self.access_history:
                self.access_history[user_id] = []
            self.access_history[user_id].append({
                "action": "add_conversation",
                "timestamp": time.time(),
                "thread_id": threading.get_ident()
            })


class MockRAGSystem:
    """Mock RAG system that tracks concurrent knowledge retrieval"""
    
    def __init__(self):
        self.is_ready = True
        self.retrieval_history = []
        self._lock = threading.Lock()
    
    async def retrieve_knowledge(self, query: str, context: Dict[str, Any]) -> str:
        with self._lock:
            self.retrieval_history.append({
                "query": query,
                "context": context,
                "thread_id": threading.get_ident(),
                "timestamp": time.time()
            })
        
        # Simulate knowledge retrieval delay
        await asyncio.sleep(0.005)
        
        # Return query-specific knowledge
        if "weather" in query.lower():
            return f"Weather knowledge for query: {query[:30]}"
        elif "aircraft" in query.lower():
            return f"Aircraft knowledge for query: {query[:30]}"
        else:
            return f"General aviation knowledge for query: {query[:30]}"


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


def create_message_handler():
    """Create a message handler with mocked dependencies that track concurrency"""
    ai_model = MockAIModel()
    user_profiles = MockUserProfiles()
    rag_system = MockRAGSystem()
    embed_builder = MockEmbedBuilder()
    
    return MessageHandler(ai_model, user_profiles, rag_system, embed_builder)


# Property-based test strategies
@st.composite
def concurrent_user_messages_strategy(draw):
    """Generate messages from multiple users for concurrent testing"""
    num_users = draw(st.integers(min_value=2, max_value=8))
    messages = []
    
    for user_id in range(1000, 1000 + num_users):
        # Generate aviation-related content for each user
        aviation_topics = ["weather", "aircraft", "navigation", "regulations", "training"]
        topic = draw(st.sampled_from(aviation_topics))
        
        content = f"Tell me about {topic} for user {user_id}"
        message = MockDiscordMessage(
            content=content,
            author_id=user_id,
            guild_id=12345,
            channel_id=80000 + user_id,
            is_dm=False
        )
        messages.append(message)
    
    return messages


@st.composite
def high_concurrency_messages_strategy(draw):
    """Generate many messages for high concurrency testing"""
    num_messages = draw(st.integers(min_value=5, max_value=15))
    messages = []
    
    for i in range(num_messages):
        user_id = 2000 + i
        content = draw(st.text(min_size=10, max_size=100))
        if not content.strip():
            content = f"Aviation question {i}"
        
        message = MockDiscordMessage(
            content=content,
            author_id=user_id,
            is_dm=True
        )
        messages.append(message)
    
    return messages


class TestConcurrentMessageProcessing:
    """
    Property 7: Concurrent Message Processing
    For any set of simultaneous messages from different users, the system should 
    process each message independently without context contamination while 
    maintaining individual user contexts.
    Validates: Requirements 5.4
    """
    
    @given(concurrent_user_messages_strategy())
    @settings(max_examples=100, deadline=60000)
    @pytest.mark.asyncio
    async def test_concurrent_processing_context_isolation(self, messages):
        """
        Property test: Concurrent messages should maintain separate user contexts
        No context contamination should occur between different users
        """
        message_handler = create_message_handler()
        
        # Process all messages concurrently
        tasks = []
        for message in messages:
            task = asyncio.create_task(message_handler.handle_message(message))
            tasks.append(task)
        
        # Wait for all processing to complete
        results = await asyncio.gather(*tasks, return_exceptions=True)
        
        # Verify no exceptions occurred (except acceptable ones)
        for i, result in enumerate(results):
            if isinstance(result, Exception):
                # Only acceptable exceptions are Discord API or rate limiting
                acceptable_errors = ["rate limit", "discord", "api", "network"]
                error_msg = str(result).lower()
                
                if not any(acceptable in error_msg for acceptable in acceptable_errors):
                    pytest.fail(f"Unexpected error in concurrent processing: {result}")
        
        # Property 1: Each user should have separate context
        user_contexts = {}
        for message in messages:
            user_id = message.author.id
            context = await message_handler.user_profiles.get_user_context_for_ai(user_id)
            user_contexts[user_id] = context
        
        assert len(user_contexts) == len(messages), \
            "Each user should have separate context"
        
        # Property 2: User contexts should be unique and not contaminated
        for user_id, context in user_contexts.items():
            # Context should contain user-specific information
            assert context.get("user_id") == user_id, \
                f"Context contamination: user_id mismatch for {user_id}"
            
            # Interests should be user-specific
            interests = context.get("interests", [])
            if interests:
                assert any(str(user_id) in str(interest) for interest in interests), \
                    f"Context contamination: interests not user-specific for {user_id}"
        
        # Property 3: AI model should have processed each message independently
        ai_calls = message_handler.ai_model.call_history
        assert len(ai_calls) >= len(messages), \
            "AI model should have been called for each message"
        
        # Verify each user got appropriate context
        user_ai_calls = {}
        for call in ai_calls:
            user_context = call.get("user_context", {})
            user_id = user_context.get("user_id")
            if user_id:
                user_ai_calls[user_id] = call
        
        for message in messages:
            user_id = message.author.id
            assert user_id in user_ai_calls, \
                f"AI should have been called with context for user {user_id}"
    
    @given(high_concurrency_messages_strategy())
    @settings(max_examples=50, deadline=90000)
    @pytest.mark.asyncio
    async def test_high_concurrency_processing_stability(self, messages):
        """
        Property test: System should remain stable under high concurrent load
        All messages should be processed without system degradation
        """
        message_handler = create_message_handler()
        
        # Record start time
        start_time = time.time()
        
        # Process all messages concurrently
        tasks = []
        for message in messages:
            task = asyncio.create_task(message_handler.handle_message(message))
            tasks.append(task)
        
        # Wait for all processing to complete
        results = await asyncio.gather(*tasks, return_exceptions=True)
        
        # Record end time
        end_time = time.time()
        processing_time = end_time - start_time
        
        # Property 1: All messages should be processed (no system failure)
        successful_results = [r for r in results if not isinstance(r, Exception)]
        error_results = [r for r in results if isinstance(r, Exception)]
        
        # Allow for some acceptable errors but most should succeed
        success_rate = len(successful_results) / len(results)
        assert success_rate >= 0.8, \
            f"Success rate too low: {success_rate:.2f}, errors: {error_results[:3]}"
        
        # Property 2: Processing should complete in reasonable time
        max_expected_time = len(messages) * 0.5  # 0.5 seconds per message max
        assert processing_time <= max_expected_time, \
            f"Processing took too long: {processing_time:.2f}s for {len(messages)} messages"
        
        # Property 3: Memory system should maintain consistency
        for message in messages:
            user_id = message.author.id
            profile = await message_handler.user_profiles.get_profile(user_id)
            
            # Profile should exist and be valid
            assert profile is not None, f"Profile missing for user {user_id}"
            assert profile.get("user_id") == user_id, f"Profile corruption for user {user_id}"
        
        # Property 4: AI model should handle concurrent calls properly
        max_concurrent = message_handler.ai_model.max_concurrent
        assert max_concurrent > 0, "AI model should have handled concurrent calls"
        
        # Concurrent calls should not exceed reasonable limits
        assert max_concurrent <= len(messages), \
            f"Concurrent calls exceeded message count: {max_concurrent} > {len(messages)}"
    
    @given(st.integers(min_value=3, max_value=10))
    @settings(max_examples=100, deadline=30000)
    @pytest.mark.asyncio
    async def test_user_memory_isolation_during_concurrency(self, num_users):
        """
        Property test: User memory should remain isolated during concurrent access
        Each user's memory updates should not affect other users
        """
        message_handler = create_message_handler()
        
        # Create messages from different users with unique content
        messages = []
        expected_updates = {}
        
        for i in range(num_users):
            user_id = 3000 + i
            unique_content = f"I am user {user_id} learning about aviation topic {i}"
            
            message = MockDiscordMessage(
                content=unique_content,
                author_id=user_id,
                is_dm=True
            )
            messages.append(message)
            expected_updates[user_id] = unique_content
        
        # Process all messages concurrently
        tasks = []
        for message in messages:
            task = asyncio.create_task(message_handler.handle_message(message))
            tasks.append(task)
        
        await asyncio.gather(*tasks, return_exceptions=True)
        
        # Verify memory isolation
        for user_id, expected_content in expected_updates.items():
            # Check user profile
            profile = await message_handler.user_profiles.get_profile(user_id)
            
            # Property 1: Each user should have their own profile
            assert profile.get("user_id") == user_id, \
                f"Profile user_id mismatch for {user_id}"
            
            # Property 2: Profile should contain user-specific data
            interests = profile.get("interests", [])
            if interests:
                # Should contain user-specific interest
                assert any(str(user_id) in str(interest) for interest in interests), \
                    f"User {user_id} interests not user-specific: {interests}"
            
            # Property 3: Conversation history should be user-specific
            history = await message_handler.user_profiles.get_conversation_history(user_id)
            if history:
                # History should reference this user
                assert any(str(user_id) in str(entry) for entry in history), \
                    f"User {user_id} history not user-specific: {history}"
        
        # Property 4: Memory access should be properly tracked per user
        access_history = message_handler.user_profiles.access_history
        
        for user_id in expected_updates.keys():
            assert user_id in access_history, \
                f"No access history recorded for user {user_id}"
            
            user_accesses = access_history[user_id]
            assert len(user_accesses) > 0, \
                f"No memory accesses recorded for user {user_id}"
    
    @given(st.integers(min_value=2, max_value=6))
    @settings(max_examples=50, deadline=45000)
    @pytest.mark.asyncio
    async def test_knowledge_retrieval_concurrency(self, num_concurrent_queries):
        """
        Property test: Knowledge retrieval should work correctly under concurrent access
        Multiple users querying knowledge simultaneously should get appropriate responses
        """
        message_handler = create_message_handler()
        
        # Create messages with different knowledge queries
        knowledge_topics = ["weather", "aircraft", "navigation", "regulations", "emergency", "training"]
        messages = []
        
        for i in range(num_concurrent_queries):
            user_id = 4000 + i
            topic = knowledge_topics[i % len(knowledge_topics)]
            content = f"What do you know about {topic}?"
            
            message = MockDiscordMessage(
                content=content,
                author_id=user_id,
                is_dm=True
            )
            messages.append(message)
        
        # Process all messages concurrently
        tasks = []
        for message in messages:
            task = asyncio.create_task(message_handler.handle_message(message))
            tasks.append(task)
        
        await asyncio.gather(*tasks, return_exceptions=True)
        
        # Verify knowledge retrieval worked correctly
        rag_history = message_handler.rag_system.retrieval_history
        
        # Property 1: Knowledge should have been retrieved for each query
        assert len(rag_history) >= num_concurrent_queries, \
            f"Expected at least {num_concurrent_queries} knowledge retrievals, got {len(rag_history)}"
        
        # Property 2: Each retrieval should be query-specific
        retrieved_queries = [entry["query"] for entry in rag_history]
        
        # Should have variety in queries (not all identical)
        unique_queries = set(retrieved_queries)
        assert len(unique_queries) > 1, \
            f"Knowledge queries not diverse enough: {unique_queries}"
        
        # Property 3: Concurrent retrievals should not interfere with each other
        for entry in rag_history:
            query = entry["query"]
            context = entry.get("context", {})
            
            # Context should be appropriate for the query
            assert isinstance(context, dict), "Knowledge context should be a dictionary"
            
            # Query should not be empty or corrupted
            assert len(query.strip()) > 0, "Knowledge query should not be empty"
    
    @given(st.integers(min_value=2, max_value=5))
    @settings(max_examples=30, deadline=60000)
    @pytest.mark.asyncio
    async def test_response_generation_independence(self, num_users):
        """
        Property test: Response generation should be independent for each user
        Concurrent response generation should not cross-contaminate between users
        """
        message_handler = create_message_handler()
        
        # Create messages with user-specific content
        messages = []
        user_specific_content = {}
        
        for i in range(num_users):
            user_id = 5000 + i
            specific_phrase = f"unique_phrase_for_user_{user_id}"
            content = f"Please help me with aviation. My specific question is about {specific_phrase}."
            
            message = MockDiscordMessage(
                content=content,
                author_id=user_id,
                is_dm=True
            )
            messages.append(message)
            user_specific_content[user_id] = specific_phrase
        
        # Process all messages concurrently
        tasks = []
        for message in messages:
            task = asyncio.create_task(message_handler.handle_message(message))
            tasks.append(task)
        
        await asyncio.gather(*tasks, return_exceptions=True)
        
        # Verify response independence
        ai_calls = message_handler.ai_model.call_history
        
        # Property 1: Each user should have gotten a response
        user_responses = {}
        for call in ai_calls:
            user_context = call.get("user_context", {})
            user_id = user_context.get("user_id")
            if user_id and user_id in user_specific_content:
                user_responses[user_id] = call
        
        assert len(user_responses) >= num_users, \
            f"Not all users got responses: expected {num_users}, got {len(user_responses)}"
        
        # Property 2: Each response should be user-specific
        for user_id, expected_phrase in user_specific_content.items():
            if user_id in user_responses:
                call = user_responses[user_id]
                message_content = call.get("message", "")
                user_context = call.get("user_context", {})
                
                # Response should be for the correct user
                assert user_context.get("user_id") == user_id, \
                    f"Response context mismatch for user {user_id}"
                
                # Message should contain user-specific content
                assert expected_phrase in message_content, \
                    f"User-specific content missing for user {user_id}: {message_content}"
        
        # Property 3: No cross-contamination between user contexts
        for user_id in user_specific_content.keys():
            if user_id in user_responses:
                call = user_responses[user_id]
                user_context = call.get("user_context", {})
                
                # Context should not contain other users' data
                for other_user_id in user_specific_content.keys():
                    if other_user_id != user_id:
                        context_str = str(user_context)
                        other_phrase = user_specific_content[other_user_id]
                        
                        assert other_phrase not in context_str, \
                            f"Context contamination: user {user_id} context contains {other_phrase}"


if __name__ == "__main__":
    pytest.main([__file__, "-v"])