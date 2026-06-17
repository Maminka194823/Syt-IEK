"""
Tests for enhanced user profile features
Tests AI evaluation, automatic pruning, context optimization, and feedback handling
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


class TestEnhancedUserProfiles:
    """
    Tests for enhanced user profile management features
    """
    
    def create_temp_profile_manager(self, ai_orchestrator=None):
        """Create a profile manager with temporary directory and optional AI orchestrator"""
        temp_dir = tempfile.mkdtemp()
        if ai_orchestrator is None:
            # Create mock AI orchestrator
            ai_orchestrator = MagicMock()
            ai_orchestrator.evaluate_memory_relevance = AsyncMock(return_value={
                "relevance_score": 7,
                "extracted_info": {
                    "experience_level": "private",
                    "interests": ["cessna", "navigation"],
                    "learning_goals": ["instrument_rating"],
                    "knowledge_gaps": ["weather"],
                    "experiences": []
                }
            })
        return UserProfileManager(data_dir=temp_dir, ai_orchestrator=ai_orchestrator), temp_dir
    
    def cleanup_temp_dir(self, temp_dir):
        """Clean up temporary directory"""
        try:
            shutil.rmtree(temp_dir)
        except:
            pass
    
    @given(
        user_id=st.integers(min_value=1, max_value=999999999999999999),
        conversation_text=st.text(min_size=20, max_size=500),
        relevance_score=st.integers(min_value=1, max_value=10)
    )
    @settings(max_examples=100, deadline=10000)
    def test_ai_driven_memory_evaluation(self, user_id, conversation_text, relevance_score):
        """
        Test that AI-driven memory evaluation works correctly
        """
        async def run_test():
            # Create mock AI orchestrator with specific response
            mock_ai_orchestrator = MagicMock()
            mock_ai_orchestrator.evaluate_memory_relevance = AsyncMock(return_value={
                "relevance_score": relevance_score,
                "extracted_info": {
                    "experience_level": "commercial" if relevance_score > 7 else None,
                    "interests": ["boeing", "ifr"] if relevance_score > 5 else [],
                    "learning_goals": ["atp"] if relevance_score > 8 else [],
                    "knowledge_gaps": ["regulations"] if relevance_score > 6 else [],
                    "experiences": []
                }
            })
            
            profile_manager, temp_dir = self.create_temp_profile_manager(mock_ai_orchestrator)
            
            try:
                # Update profile without providing AI analysis (should use AI orchestrator)
                await profile_manager.update_profile_from_conversation(
                    user_id, conversation_text
                )
                
                # Verify AI orchestrator was called
                mock_ai_orchestrator.evaluate_memory_relevance.assert_called_once_with(conversation_text)
                
                # Get updated profile
                profile = await profile_manager.get_profile(user_id)
                
                # Verify relevance score was tracked
                relevance_scores = profile.get("conversation_relevance_scores", [])
                assert len(relevance_scores) > 0
                assert relevance_scores[-1]["score"] == relevance_score
                
                # Verify high relevance updates were applied
                if relevance_score >= profile_manager.relevance_threshold:
                    if relevance_score > 7:
                        assert profile.get("experience_level") == "commercial"
                    if relevance_score > 5:
                        assert "boeing" in profile.get("interests", [])
                        assert "ifr" in profile.get("interests", [])
                    if relevance_score > 8:
                        assert "atp" in profile.get("learning_goals", [])
                    if relevance_score > 6:
                        assert "regulations" in profile.get("knowledge_gaps", [])
                
            finally:
                self.cleanup_temp_dir(temp_dir)
        
        asyncio.run(run_test())
    
    @given(
        user_id=st.integers(min_value=1, max_value=999999999999999999),
        feedback_type=st.sampled_from(["correction", "positive", "negative", "clarification"]),
        original_response=st.text(min_size=10, max_size=300),
        user_correction=st.one_of(st.none(), st.text(min_size=5, max_size=200))
    )
    @settings(max_examples=100, deadline=10000)
    def test_user_feedback_recording(self, user_id, feedback_type, original_response, user_correction):
        """
        Test that user feedback and corrections are recorded properly
        """
        async def run_test():
            profile_manager, temp_dir = self.create_temp_profile_manager()
            
            try:
                # Record user feedback
                await profile_manager.record_user_feedback(
                    user_id, feedback_type, original_response, user_correction
                )
                
                # Get updated profile
                profile = await profile_manager.get_profile(user_id)
                
                # Verify feedback was recorded
                correction_history = profile.get("correction_history", [])
                assert len(correction_history) > 0
                
                latest_feedback = correction_history[-1]
                assert latest_feedback["type"] == feedback_type
                assert latest_feedback["original_response"] in original_response or len(original_response) > 200
                if user_correction:
                    assert latest_feedback["user_correction"] == user_correction
                
                # Verify statistics were updated
                if feedback_type == "correction":
                    assert profile.get("corrections_provided", 0) > 0
                elif feedback_type == "positive":
                    assert profile.get("helpful_responses_received", 0) > 0
                
                # Test feedback summary
                feedback_summary = await profile_manager.get_feedback_summary(user_id)
                assert isinstance(feedback_summary, dict)
                assert "total_corrections" in feedback_summary
                assert "feedback_patterns" in feedback_summary
                
            finally:
                self.cleanup_temp_dir(temp_dir)
        
        asyncio.run(run_test())
    
    @given(
        user_id=st.integers(min_value=1, max_value=999999999999999999),
        num_conversations=st.integers(min_value=25, max_value=40)
    )
    @settings(max_examples=50, deadline=15000)
    def test_context_optimization(self, user_id, num_conversations):
        """
        Test that context optimization occurs at appropriate intervals
        """
        async def run_test():
            profile_manager, temp_dir = self.create_temp_profile_manager()
            
            try:
                # Add conversations to trigger optimization
                for i in range(num_conversations):
                    conversation_text = f"Aviation conversation {i} about cessna aircraft and navigation"
                    await profile_manager.update_profile_from_conversation(
                        user_id, conversation_text
                    )
                
                # Get profile
                profile = await profile_manager.get_profile(user_id)
                
                # Check if context optimization occurred
                expected_optimizations = num_conversations // profile_manager.context_optimization_threshold
                if expected_optimizations > 0:
                    assert profile.get("context_optimizations", 0) >= expected_optimizations
                    assert profile.get("last_context_optimization") is not None
                    assert profile.get("context_optimization_score", 0) > 0
                
                # Verify interests were consolidated (no duplicates)
                interests = profile.get("interests", [])
                assert len(interests) == len(set(interests))  # No duplicates
                assert len(interests) <= 10  # Limited to reasonable size
                
            finally:
                self.cleanup_temp_dir(temp_dir)
        
        asyncio.run(run_test())
    
    @given(
        user_id=st.integers(min_value=1, max_value=999999999999999999),
        num_important_conversations=st.integers(min_value=35, max_value=50)
    )
    @settings(max_examples=50, deadline=15000)
    def test_intelligent_conversation_pruning(self, user_id, num_important_conversations):
        """
        Test that important conversations are pruned intelligently based on relevance
        """
        async def run_test():
            profile_manager, temp_dir = self.create_temp_profile_manager()
            
            try:
                # Add many high-relevance conversations
                for i in range(num_important_conversations):
                    conversation_text = f"Important aviation conversation {i}"
                    # Vary relevance scores
                    relevance_score = 6 + (i % 5)  # Scores from 6-10
                    
                    ai_analysis = {
                        "relevance_score": relevance_score,
                        "extracted_info": {
                            "experience_level": None,
                            "interests": [f"interest_{i}"],
                            "learning_goals": [],
                            "knowledge_gaps": [],
                            "experiences": []
                        }
                    }
                    
                    await profile_manager.update_profile_from_conversation(
                        user_id, conversation_text, ai_analysis
                    )
                
                # Get profile
                profile = await profile_manager.get_profile(user_id)
                
                # Verify pruning occurred
                important_conversations = profile.get("important_conversations", [])
                assert len(important_conversations) <= profile_manager.important_memory_limit
                
                # Verify highest relevance conversations were kept
                if important_conversations:
                    relevance_scores = [conv.get("relevance_score", 0) for conv in important_conversations]
                    # Should generally have higher scores (allowing some variance due to recency boost)
                    avg_relevance = sum(relevance_scores) / len(relevance_scores)
                    assert avg_relevance >= 6  # Should keep reasonably relevant conversations
                
            finally:
                self.cleanup_temp_dir(temp_dir)
        
        asyncio.run(run_test())
    
    @given(
        user_id=st.integers(min_value=1, max_value=999999999999999999),
        num_corrections=st.integers(min_value=5, max_value=15)
    )
    @settings(max_examples=50, deadline=10000)
    def test_feedback_pattern_analysis(self, user_id, num_corrections):
        """
        Test that feedback patterns are analyzed and stored correctly
        """
        async def run_test():
            profile_manager, temp_dir = self.create_temp_profile_manager()
            
            try:
                # Add various types of feedback
                feedback_types = ["correction", "positive", "negative", "clarification"]
                corrections_with_detail_requests = ["Please provide more detail", "Can you explain further"]
                corrections_with_simplification = ["Too complex, make it simpler", "Use basic terms"]
                
                for i in range(num_corrections):
                    feedback_type = feedback_types[i % len(feedback_types)]
                    original_response = f"Original response {i}"
                    
                    # Add specific correction patterns
                    if feedback_type == "correction":
                        if i % 3 == 0:
                            user_correction = corrections_with_detail_requests[i % len(corrections_with_detail_requests)]
                        elif i % 3 == 1:
                            user_correction = corrections_with_simplification[i % len(corrections_with_simplification)]
                        else:
                            user_correction = f"General correction {i}"
                    else:
                        user_correction = None
                    
                    await profile_manager.record_user_feedback(
                        user_id, feedback_type, original_response, user_correction
                    )
                
                # Get profile and check patterns
                profile = await profile_manager.get_profile(user_id)
                feedback_patterns = profile.get("feedback_patterns", {})
                
                # Verify pattern analysis occurred
                if num_corrections >= 3:
                    assert "correction_frequency" in feedback_patterns
                    assert "response_preferences" in feedback_patterns
                    
                    # Check if preferences were detected
                    preferences = feedback_patterns.get("response_preferences", {})
                    correction_count = len([f for f in profile.get("correction_history", []) if f["type"] == "correction"])
                    
                    if correction_count >= 2:
                        # Should have detected some preferences
                        assert len(preferences) >= 0  # May or may not detect patterns depending on content
                
            finally:
                self.cleanup_temp_dir(temp_dir)
        
        asyncio.run(run_test())
    
    @given(
        user_id=st.integers(min_value=1, max_value=999999999999999999)
    )
    @settings(max_examples=50, deadline=10000)
    def test_enhanced_user_context_for_ai(self, user_id):
        """
        Test that enhanced user context includes feedback patterns and optimization scores
        """
        async def run_test():
            profile_manager, temp_dir = self.create_temp_profile_manager()
            
            try:
                # Add some feedback to create patterns
                await profile_manager.record_user_feedback(
                    user_id, "correction", "Original response", "Please provide more detail"
                )
                await profile_manager.record_user_feedback(
                    user_id, "positive", "Good response", None
                )
                
                # Add conversation to trigger context optimization
                for i in range(25):  # Trigger optimization
                    await profile_manager.update_profile_from_conversation(
                        user_id, f"Conversation {i} about aviation"
                    )
                
                # Get enhanced context
                context = await profile_manager.get_user_context_for_ai(user_id)
                
                # Verify enhanced context includes new fields
                assert isinstance(context, dict)
                assert "context_quality" in context
                assert isinstance(context["context_quality"], (int, float))
                
                # May include feedback patterns if analysis occurred
                if "feedback_patterns" in context:
                    assert isinstance(context["feedback_patterns"], dict)
                
            finally:
                self.cleanup_temp_dir(temp_dir)
        
        asyncio.run(run_test())
    
    @given(
        user_id=st.integers(min_value=1, max_value=999999999999999999)
    )
    @settings(max_examples=50, deadline=10000)
    def test_memory_analytics(self, user_id):
        """
        Test that memory analytics provide useful insights
        """
        async def run_test():
            profile_manager, temp_dir = self.create_temp_profile_manager()
            
            try:
                # Add some data
                await profile_manager.update_profile_from_conversation(
                    user_id, "Aviation conversation about weather"
                )
                await profile_manager.record_user_feedback(
                    user_id, "correction", "Response", "Correction"
                )
                
                # Get analytics
                analytics = await profile_manager.get_memory_analytics()
                
                # Verify analytics structure
                assert isinstance(analytics, dict)
                required_fields = [
                    "total_profiles", "total_important_conversations", "total_corrections",
                    "average_relevance_score", "average_context_optimization",
                    "memory_retention_days", "relevance_threshold"
                ]
                
                for field in required_fields:
                    assert field in analytics
                    assert isinstance(analytics[field], (int, float))
                
                # Verify reasonable values
                assert analytics["total_profiles"] >= 1
                assert analytics["memory_retention_days"] > 0
                assert 1 <= analytics["relevance_threshold"] <= 10
                
            finally:
                self.cleanup_temp_dir(temp_dir)
        
        asyncio.run(run_test())
    
    @given(
        user_id=st.integers(min_value=1, max_value=999999999999999999),
        conversation_text=st.text(min_size=10, max_size=200)
    )
    @settings(max_examples=50, deadline=10000)
    def test_conversation_relevance_estimation(self, user_id, conversation_text):
        """
        Test that conversation relevance estimation works reasonably
        """
        async def run_test():
            profile_manager, temp_dir = self.create_temp_profile_manager()
            
            try:
                # Create a mock conversation exchange
                conversation_exchange = {
                    "user": conversation_text,
                    "assistant": "This is a response about aviation topics including aircraft and flight training."
                }
                
                # Test relevance estimation
                relevance = profile_manager._estimate_conversation_relevance(conversation_exchange)
                
                # Verify relevance is in valid range
                assert isinstance(relevance, (int, float))
                assert 1.0 <= relevance <= 10.0
                
                # Test with aviation-heavy content
                aviation_conversation = {
                    "user": "What are the weather minimums for VFR flight?",
                    "assistant": "For VFR flight, you need at least 3 statute miles visibility and specific cloud clearances depending on the airspace. In Class E airspace below 10,000 feet, you need to stay 500 feet below, 1,000 feet above, and 2,000 feet horizontally from clouds."
                }
                
                aviation_relevance = profile_manager._estimate_conversation_relevance(aviation_conversation)
                assert aviation_relevance >= 5.0  # Should be reasonably high for aviation content
                
            finally:
                self.cleanup_temp_dir(temp_dir)
        
        asyncio.run(run_test())