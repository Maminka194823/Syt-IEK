"""
Property-based test for user memory management
Tests Property 6: User Memory Management
"""

import pytest
from hypothesis import given, strategies as st, settings
import asyncio
from unittest.mock import AsyncMock, MagicMock, patch
from datetime import datetime, timedelta
import json
import os
import tempfile
import shutil

from v4.src.memory.user_profiles import UserProfileManager


# Feature: aviation-discord-bot, Property 6: User Memory Management
# **Validates: Requirements 4.1, 4.2, 4.3, 4.4, 4.5**


class TestUserMemoryManagement:
    """
    Property-based tests for user memory management
    
    Property 6: For any conversation containing aviation experience, interests, 
    or goals, the AI should evaluate relevance, update user profiles appropriately, 
    provide personalized context for future interactions, and handle conversation 
    history with proper retention.
    """
    
    def create_temp_profile_manager(self):
        """Create a profile manager with temporary directory"""
        temp_dir = tempfile.mkdtemp()
        # Create mock AI orchestrator
        mock_ai_orchestrator = MagicMock()
        mock_ai_orchestrator.evaluate_memory_relevance = AsyncMock(return_value={
            "relevance_score": 5,
            "extracted_info": {}
        })
        return UserProfileManager(data_dir=temp_dir, ai_orchestrator=mock_ai_orchestrator), temp_dir
    
    def cleanup_temp_dir(self, temp_dir):
        """Clean up temporary directory"""
        try:
            shutil.rmtree(temp_dir)
        except:
            pass
    
    @given(
        user_id=st.integers(min_value=1, max_value=999999999999999999),
        experience_level=st.one_of(
            st.none(),
            st.sampled_from(["student", "private", "commercial", "atp", "instructor"])
        ),
        interests=st.lists(
            st.sampled_from(["cessna", "piper", "boeing", "helicopter", "navigation", "weather", "ifr", "vfr"]),
            min_size=0, max_size=5
        ),
        learning_goals=st.lists(
            st.sampled_from(["private_license", "instrument_rating", "commercial", "cfi", "multi_engine"]),
            min_size=0, max_size=3
        ),
        knowledge_gaps=st.lists(
            st.sampled_from(["weather", "navigation", "regulations", "aircraft_systems", "emergency_procedures"]),
            min_size=0, max_size=3
        )
    )
    @settings(max_examples=100, deadline=10000)
    def test_profile_creation_and_retrieval(
        self, user_id, experience_level, interests, learning_goals, knowledge_gaps
    ):
        """
        Property: User profiles should be created, stored, and retrieved consistently
        with all aviation-specific information preserved
        """
        async def run_test():
            profile_manager, temp_dir = self.create_temp_profile_manager()
            
            try:
                # Get initial profile (should create new one)
                profile = await profile_manager.get_profile(user_id)
                
                # Verify profile structure
                assert isinstance(profile, dict)
                assert profile['user_id'] == user_id
                assert 'created_at' in profile
                assert 'last_active' in profile
                assert 'conversation_count' in profile
                
                # Verify aviation-specific fields exist
                aviation_fields = [
                    'experience_level', 'interests', 'learning_goals', 
                    'knowledge_gaps', 'aviation_experiences'
                ]
                for field in aviation_fields:
                    assert field in profile
                
                # Verify conversation fields exist
                conversation_fields = [
                    'preferred_detail_level', 'conversation_style',
                    'important_conversations', 'recent_topics'
                ]
                for field in conversation_fields:
                    assert field in profile
                
                # Verify statistics fields exist
                stats_fields = ['total_messages', 'aviation_questions_asked']
                for field in stats_fields:
                    assert field in profile
                    assert isinstance(profile[field], int)
                
                # Test profile retrieval consistency
                profile2 = await profile_manager.get_profile(user_id)
                assert profile == profile2
                
            finally:
                self.cleanup_temp_dir(temp_dir)
        
        asyncio.run(run_test())
    
    @given(
        user_id=st.integers(min_value=1, max_value=999999999999999999),
        conversation_text=st.text(min_size=10, max_size=1000),
        relevance_score=st.integers(min_value=1, max_value=10),
        experience_level=st.one_of(
            st.none(),
            st.sampled_from(["student", "private", "commercial", "atp", "instructor"])
        ),
        interests=st.lists(
            st.sampled_from(["cessna", "piper", "boeing", "helicopter", "navigation", "weather"]),
            min_size=0, max_size=3
        ),
        learning_goals=st.lists(
            st.sampled_from(["private_license", "instrument_rating", "commercial"]),
            min_size=0, max_size=2
        )
    )
    @settings(max_examples=100, deadline=10000)
    def test_profile_update_from_conversation(
        self, user_id, conversation_text, relevance_score, experience_level, interests, learning_goals
    ):
        """
        Property: User profiles should be updated appropriately based on 
        conversation analysis with proper relevance scoring
        """
        async def run_test():
            profile_manager, temp_dir = self.create_temp_profile_manager()
            
            try:
                # Create AI analysis mock
                ai_analysis = {
                    "relevance_score": relevance_score,
                    "extracted_info": {
                        "experience_level": experience_level,
                        "interests": interests,
                        "learning_goals": learning_goals,
                        "knowledge_gaps": [],
                        "experiences": []
                    }
                }
                
                # Get initial profile
                initial_profile = await profile_manager.get_profile(user_id)
                initial_conversation_count = initial_profile['conversation_count']
                initial_total_messages = initial_profile['total_messages']
                initial_last_active = initial_profile['last_active']
                
                # Add small delay to ensure timestamp difference
                import time
                time.sleep(0.001)
                
                # Update profile from conversation
                await profile_manager.update_profile_from_conversation(
                    user_id, conversation_text, ai_analysis
                )
                
                # Get updated profile
                updated_profile = await profile_manager.get_profile(user_id)
                
                # Verify basic stats were updated
                assert updated_profile['conversation_count'] == initial_conversation_count + 1
                assert updated_profile['total_messages'] == initial_total_messages + 1
                # Verify last_active was updated (allow for same timestamp if very fast)
                assert updated_profile['last_active'] >= initial_last_active
                
                # Verify high relevance updates are applied
                if relevance_score >= profile_manager.relevance_threshold:
                    if experience_level:
                        assert updated_profile['experience_level'] == experience_level
                    
                    # Check interests were added (avoiding duplicates)
                    for interest in interests:
                        if interest:
                            assert interest in updated_profile['interests']
                    
                    # Check learning goals were added
                    for goal in learning_goals:
                        if goal:
                            assert goal in updated_profile['learning_goals']
                    
                    # Verify important conversation was stored
                    assert len(updated_profile['important_conversations']) > 0
                    latest_conversation = updated_profile['important_conversations'][-1]
                    assert latest_conversation['relevance_score'] == relevance_score
                
                # Verify profile consistency
                assert isinstance(updated_profile['interests'], list)
                assert isinstance(updated_profile['learning_goals'], list)
                assert isinstance(updated_profile['important_conversations'], list)
                
            finally:
                self.cleanup_temp_dir(temp_dir)
        
        asyncio.run(run_test())
    
    @given(
        user_id=st.integers(min_value=1, max_value=999999999999999999),
        experience_level=st.one_of(
            st.none(),
            st.sampled_from(["student", "private", "commercial", "atp", "instructor"])
        ),
        interests=st.lists(
            st.sampled_from(["cessna", "navigation", "weather", "ifr"]),
            min_size=0, max_size=4
        ),
        learning_goals=st.lists(
            st.sampled_from(["private_license", "instrument_rating", "commercial"]),
            min_size=0, max_size=2
        ),
        detail_level=st.sampled_from(["brief", "medium", "detailed"]),
        conversation_style=st.sampled_from(["formal", "friendly", "casual"])
    )
    @settings(max_examples=100, deadline=10000)
    def test_user_context_for_ai(
        self, user_id, experience_level, interests, learning_goals, detail_level, conversation_style
    ):
        """
        Property: User context for AI should provide relevant, structured information
        for personalized responses
        """
        async def run_test():
            profile_manager, temp_dir = self.create_temp_profile_manager()
            
            try:
                # Get initial profile and update it
                profile = await profile_manager.get_profile(user_id)
                
                # Update profile with test data
                if experience_level:
                    profile['experience_level'] = experience_level
                profile['interests'] = interests
                profile['learning_goals'] = learning_goals
                profile['preferred_detail_level'] = detail_level
                profile['conversation_style'] = conversation_style
                
                # Add some recent topics
                profile['recent_topics'] = [
                    {"topic": "weather", "timestamp": datetime.utcnow().isoformat()},
                    {"topic": "navigation", "timestamp": datetime.utcnow().isoformat()}
                ]
                
                # Save updated profile
                await profile_manager._save_profile(user_id, profile)
                
                # Get user context for AI
                context = await profile_manager.get_user_context_for_ai(user_id)
                
                # Verify context structure
                assert isinstance(context, dict)
                
                # Verify experience level is included if set
                if experience_level:
                    assert context.get('experience_level') == experience_level
                
                # Verify interests are included (limited to top 5)
                if interests:
                    context_interests = context.get('interests', [])
                    assert isinstance(context_interests, list)
                    assert len(context_interests) <= 5
                    for interest in context_interests:
                        assert interest in interests
                
                # Verify learning goals are included (limited to top 3)
                if learning_goals:
                    context_goals = context.get('learning_goals', [])
                    assert isinstance(context_goals, list)
                    assert len(context_goals) <= 3
                    for goal in context_goals:
                        assert goal in learning_goals
                
                # Verify preferences are included
                assert context.get('detail_level') == detail_level
                assert context.get('conversation_style') == conversation_style
                
                # Verify recent topics are included (limited to top 3)
                context_topics = context.get('recent_topics', [])
                assert isinstance(context_topics, list)
                assert len(context_topics) <= 3
                
            finally:
                self.cleanup_temp_dir(temp_dir)
        
        asyncio.run(run_test())
    
    @given(
        user_id=st.integers(min_value=1, max_value=999999999999999999),
        conversation_exchanges=st.lists(
            st.fixed_dictionaries({
                'user': st.text(min_size=5, max_size=200),
                'assistant': st.text(min_size=5, max_size=200)
            }),
            min_size=1, max_size=10
        )
    )
    @settings(max_examples=100, deadline=10000)
    def test_conversation_history_management(
        self, user_id, conversation_exchanges
    ):
        """
        Property: Conversation history should be stored, retrieved, and managed
        with proper limits and data integrity
        """
        async def run_test():
            profile_manager, temp_dir = self.create_temp_profile_manager()
            
            try:
                # Add conversation exchanges
                for exchange in conversation_exchanges:
                    await profile_manager.add_conversation_exchange(
                        user_id, exchange['user'], exchange['assistant']
                    )
                
                # Retrieve conversation history
                history = await profile_manager.get_conversation_history(user_id, limit=5)
                
                # Verify history structure
                assert isinstance(history, list)
                assert len(history) <= 5  # Respects limit
                assert len(history) <= len(conversation_exchanges)  # Not more than added
                
                # Verify each exchange structure
                for exchange in history:
                    assert isinstance(exchange, dict)
                    assert 'timestamp' in exchange
                    assert 'user' in exchange
                    assert 'assistant' in exchange
                    assert isinstance(exchange['user'], str)
                    assert isinstance(exchange['assistant'], str)
                    assert len(exchange['user']) > 0
                    assert len(exchange['assistant']) > 0
                
                # Verify history ordering (most recent first)
                if len(history) > 1:
                    timestamps = [exchange['timestamp'] for exchange in history]
                    # Should be in chronological order (oldest to newest)
                    for i in range(1, len(timestamps)):
                        assert timestamps[i] >= timestamps[i-1]
                
                # Test different limits
                full_history = await profile_manager.get_conversation_history(user_id, limit=100)
                limited_history = await profile_manager.get_conversation_history(user_id, limit=2)
                
                assert len(full_history) >= len(limited_history)
                assert len(limited_history) <= 2
                
                # Verify content consistency
                if len(conversation_exchanges) > 0:
                    # Last exchange should match last added
                    last_added = conversation_exchanges[-1]
                    if len(full_history) > 0:
                        last_in_history = full_history[-1]
                        assert last_in_history['user'] == last_added['user']
                        assert last_in_history['assistant'] == last_added['assistant']
                
            finally:
                self.cleanup_temp_dir(temp_dir)
        
        asyncio.run(run_test())
    
    @given(
        user_id=st.integers(min_value=1, max_value=999999999999999999),
        num_conversations=st.integers(min_value=5, max_value=25)
    )
    @settings(max_examples=100, deadline=10000)
    def test_conversation_history_limits(
        self, user_id, num_conversations
    ):
        """
        Property: Conversation history should respect maximum limits and 
        automatically prune old conversations
        """
        async def run_test():
            profile_manager, temp_dir = self.create_temp_profile_manager()
            
            try:
                # Add many conversation exchanges
                for i in range(num_conversations):
                    await profile_manager.add_conversation_exchange(
                        user_id, 
                        f"User message {i}",
                        f"Assistant response {i}"
                    )
                
                # Get full history
                history = await profile_manager.get_conversation_history(user_id, limit=100)
                
                # Verify history respects maximum limit
                max_expected = min(num_conversations, profile_manager.max_conversation_history)
                assert len(history) <= max_expected
                
                # If we added more than the limit, verify only recent ones are kept
                if num_conversations > profile_manager.max_conversation_history:
                    assert len(history) == profile_manager.max_conversation_history
                    
                    # Verify the most recent conversations are kept
                    last_exchange = history[-1]
                    expected_last_index = num_conversations - 1
                    assert f"User message {expected_last_index}" in last_exchange['user']
                    assert f"Assistant response {expected_last_index}" in last_exchange['assistant']
                
            finally:
                self.cleanup_temp_dir(temp_dir)
        
        asyncio.run(run_test())
    
    @given(
        user_id=st.integers(min_value=1, max_value=999999999999999999),
        multiple_updates=st.lists(
            st.fixed_dictionaries({
                'conversation': st.text(min_size=10, max_size=200),
                'relevance_score': st.integers(min_value=1, max_value=10),
                'interests': st.lists(
                    st.sampled_from(["cessna", "boeing", "helicopter", "navigation"]),
                    min_size=0, max_size=2
                )
            }),
            min_size=2, max_size=8
        )
    )
    @settings(max_examples=100, deadline=10000)
    def test_profile_consistency_across_updates(
        self, user_id, multiple_updates
    ):
        """
        Property: User profiles should maintain consistency across multiple
        updates and avoid data corruption or duplication
        """
        async def run_test():
            profile_manager, temp_dir = self.create_temp_profile_manager()
            
            try:
                # Apply multiple updates
                for update in multiple_updates:
                    ai_analysis = {
                        "relevance_score": update['relevance_score'],
                        "extracted_info": {
                            "experience_level": None,
                            "interests": update['interests'],
                            "learning_goals": [],
                            "knowledge_gaps": [],
                            "experiences": []
                        }
                    }
                    
                    await profile_manager.update_profile_from_conversation(
                        user_id, update['conversation'], ai_analysis
                    )
                
                # Get final profile
                final_profile = await profile_manager.get_profile(user_id)
                
                # Verify profile integrity
                assert isinstance(final_profile, dict)
                assert final_profile['user_id'] == user_id
                assert final_profile['conversation_count'] == len(multiple_updates)
                
                # Verify no duplicate interests
                interests = final_profile['interests']
                assert len(interests) == len(set(interests))  # No duplicates
                
                # Verify all high-relevance interests are included
                expected_interests = set()
                for update in multiple_updates:
                    if update['relevance_score'] >= profile_manager.relevance_threshold:
                        expected_interests.update(update['interests'])
                
                for interest in expected_interests:
                    if interest:  # Skip empty strings
                        assert interest in interests
                
                # Verify important conversations list is properly managed
                important_conversations = final_profile['important_conversations']
                assert isinstance(important_conversations, list)
                assert len(important_conversations) <= 20  # Should be limited
                
                # Verify timestamps are valid
                for conv in important_conversations:
                    assert 'timestamp' in conv
                    # Should be valid ISO format
                    datetime.fromisoformat(conv['timestamp'])
                
            finally:
                self.cleanup_temp_dir(temp_dir)
        
        asyncio.run(run_test())
    
    @given(
        user_id=st.integers(min_value=1, max_value=999999999999999999)
    )
    @settings(max_examples=100, deadline=10000)
    def test_profile_persistence_across_sessions(self, user_id):
        """
        Property: User profiles should persist across different profile manager
        instances (simulating application restarts)
        """
        async def run_test():
            temp_dir = tempfile.mkdtemp()
            
            try:
                # Create first profile manager instance
                mock_ai_orchestrator = MagicMock()
                mock_ai_orchestrator.evaluate_memory_relevance = AsyncMock(return_value={
                    "relevance_score": 5,
                    "extracted_info": {}
                })
                profile_manager1 = UserProfileManager(data_dir=temp_dir, ai_orchestrator=mock_ai_orchestrator)
                
                # Create and update profile
                profile1 = await profile_manager1.get_profile(user_id)
                profile1['experience_level'] = 'private'
                profile1['interests'] = ['cessna', 'navigation']
                await profile_manager1._save_profile(user_id, profile1)
                
                # Add conversation history
                await profile_manager1.add_conversation_exchange(
                    user_id, "What is a VOR?", "A VOR is a navigation aid..."
                )
                
                # Create second profile manager instance (simulating restart)
                mock_ai_orchestrator2 = MagicMock()
                mock_ai_orchestrator2.evaluate_memory_relevance = AsyncMock(return_value={
                    "relevance_score": 5,
                    "extracted_info": {}
                })
                profile_manager2 = UserProfileManager(data_dir=temp_dir, ai_orchestrator=mock_ai_orchestrator2)
                
                # Retrieve profile with new instance
                profile2 = await profile_manager2.get_profile(user_id)
                
                # Verify data persistence
                assert profile2['user_id'] == user_id
                assert profile2['experience_level'] == 'private'
                assert 'cessna' in profile2['interests']
                assert 'navigation' in profile2['interests']
                
                # Verify conversation history persistence
                history = await profile_manager2.get_conversation_history(user_id)
                assert len(history) > 0
                assert history[0]['user'] == "What is a VOR?"
                assert "VOR is a navigation aid" in history[0]['assistant']
                
            finally:
                self.cleanup_temp_dir(temp_dir)
        
        asyncio.run(run_test())
    
    @given(
        user_id=st.integers(min_value=1, max_value=999999999999999999),
        conversation_text=st.text(min_size=20, max_size=500)
    )
    @settings(max_examples=100, deadline=10000)
    def test_topic_extraction_and_tracking(self, user_id, conversation_text):
        """
        Property: Recent topics should be extracted from conversations and
        tracked appropriately for context
        """
        async def run_test():
            profile_manager, temp_dir = self.create_temp_profile_manager()
            
            try:
                # Create AI analysis with moderate relevance
                ai_analysis = {
                    "relevance_score": 5,  # Moderate relevance
                    "extracted_info": {
                        "experience_level": None,
                        "interests": [],
                        "learning_goals": [],
                        "knowledge_gaps": [],
                        "experiences": []
                    }
                }
                
                # Update profile from conversation
                await profile_manager.update_profile_from_conversation(
                    user_id, conversation_text, ai_analysis
                )
                
                # Get updated profile
                profile = await profile_manager.get_profile(user_id)
                
                # Verify recent topics were updated
                recent_topics = profile.get('recent_topics', [])
                assert isinstance(recent_topics, list)
                
                # If topics were extracted, verify structure
                if recent_topics:
                    for topic in recent_topics:
                        assert isinstance(topic, dict)
                        assert 'topic' in topic
                        assert 'timestamp' in topic
                        assert isinstance(topic['topic'], str)
                        assert len(topic['topic']) > 0
                        
                        # Verify timestamp is valid
                        datetime.fromisoformat(topic['timestamp'])
                
                # Verify topics list is limited
                assert len(recent_topics) <= 10
                
            finally:
                self.cleanup_temp_dir(temp_dir)
        
        asyncio.run(run_test())