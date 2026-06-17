"""
Integration test for enhanced UserProfileManager with AI orchestrator
"""

import pytest
import asyncio
from unittest.mock import AsyncMock, MagicMock, patch
import tempfile
import shutil

from v4.src.ai.ai_orchestrator import AIOrchestrator
from v4.src.memory.user_profiles import UserProfileManager
from v4.src.ai.model_loader import AIModelManager
from v4.src.knowledge.rag_system import RAGSystem


class TestEnhancedIntegration:
    """
    Integration tests for enhanced user profile management with AI orchestrator
    """
    
    def create_test_components(self):
        """Create test components with mocks"""
        temp_dir = tempfile.mkdtemp()
        
        # Create mock AI model
        mock_ai_model = MagicMock(spec=AIModelManager)
        mock_ai_model.is_loaded = True
        mock_ai_model.generate_response = AsyncMock(return_value="This is a helpful aviation response about weather interpretation for commercial pilots.")
        mock_ai_model.evaluate_memory_relevance = AsyncMock(return_value={
            "relevance_score": 8,
            "extracted_info": {
                "experience_level": "commercial",
                "interests": ["boeing", "navigation"],
                "learning_goals": ["atp"],
                "knowledge_gaps": ["weather"],
                "experiences": []
            }
        })
        
        # Create mock RAG system
        mock_rag_system = MagicMock(spec=RAGSystem)
        mock_rag_system.is_ready = True
        mock_rag_system.retrieve_knowledge = AsyncMock(return_value="Aviation knowledge context")
        
        # Create user profile manager
        user_profiles = UserProfileManager(data_dir=temp_dir)
        
        # Create AI orchestrator (this will set itself in user_profiles)
        ai_orchestrator = AIOrchestrator(
            ai_model=mock_ai_model,
            user_profiles=user_profiles,
            rag_system=mock_rag_system
        )
        
        # Override the AI orchestrator's evaluate_memory_relevance method directly
        ai_orchestrator.evaluate_memory_relevance = AsyncMock(return_value={
            "relevance_score": 8,
            "extracted_info": {
                "experience_level": "commercial",
                "interests": ["boeing", "navigation"],
                "learning_goals": ["atp"],
                "knowledge_gaps": ["weather"],
                "experiences": []
            }
        })
        
        return ai_orchestrator, user_profiles, temp_dir
    
    def cleanup_temp_dir(self, temp_dir):
        """Clean up temporary directory"""
        try:
            shutil.rmtree(temp_dir)
        except:
            pass
    
    def test_ai_orchestrator_integration_with_enhanced_profiles(self):
        """
        Test that AI orchestrator properly integrates with enhanced user profiles
        """
        async def run_test():
            ai_orchestrator, user_profiles, temp_dir = self.create_test_components()
            
            try:
                user_id = 12345
                message = "I'm working on my commercial pilot license and need help with weather interpretation"
                
                # Process message through orchestrator
                response = await ai_orchestrator.process_message(message, user_id)
                
                # Verify response was generated
                assert isinstance(response, str)
                assert len(response) > 0
                
                # Verify AI orchestrator was called for memory evaluation
                ai_orchestrator.evaluate_memory_relevance.assert_called()
                
                # Get user profile to verify it was updated
                profile = await user_profiles.get_profile(user_id)
                
                # Verify profile was updated with AI analysis
                assert profile["conversation_count"] > 0
                assert len(profile.get("conversation_relevance_scores", [])) > 0
                
                # Verify high relevance information was stored
                relevance_score = profile["conversation_relevance_scores"][-1]["score"]
                if relevance_score >= user_profiles.relevance_threshold:
                    assert len(profile.get("important_conversations", [])) > 0
                
                # Test feedback recording integration
                await user_profiles.record_user_feedback(
                    user_id, "correction", response, "Please provide more specific weather minimums"
                )
                
                # Verify feedback was recorded
                feedback_summary = await user_profiles.get_feedback_summary(user_id)
                assert feedback_summary["total_corrections"] > 0
                
                # Test enhanced context retrieval
                context = await user_profiles.get_user_context_for_ai(user_id)
                assert "context_quality" in context
                
            finally:
                self.cleanup_temp_dir(temp_dir)
        
        asyncio.run(run_test())
    
    def test_automatic_memory_evaluation_without_explicit_analysis(self):
        """
        Test that memory evaluation happens automatically when no explicit analysis is provided
        """
        async def run_test():
            ai_orchestrator, user_profiles, temp_dir = self.create_test_components()
            
            try:
                user_id = 67890
                conversation_text = "I'm studying for my instrument rating and have questions about ILS approaches"
                
                # Update profile without providing explicit AI analysis
                # This should trigger automatic AI evaluation
                await user_profiles.update_profile_from_conversation(
                    user_id, conversation_text
                )
                
                # Verify AI orchestrator was called for evaluation
                ai_orchestrator.evaluate_memory_relevance.assert_called_with(conversation_text)
                
                # Get profile to verify updates
                profile = await user_profiles.get_profile(user_id)
                
                # Verify relevance tracking
                assert len(profile.get("conversation_relevance_scores", [])) > 0
                
                # Verify profile updates based on AI analysis
                relevance_score = profile["conversation_relevance_scores"][-1]["score"]
                
                if relevance_score >= user_profiles.relevance_threshold:
                    # Should have extracted information from the mock AI response
                    # Check if any updates were made
                    updates_made = (
                        profile.get("experience_level") == "commercial" or
                        "boeing" in profile.get("interests", []) or
                        "navigation" in profile.get("interests", []) or
                        "atp" in profile.get("learning_goals", []) or
                        "weather" in profile.get("knowledge_gaps", [])
                    )
                    assert updates_made, f"Expected some profile updates but none were found"
                
            finally:
                self.cleanup_temp_dir(temp_dir)
        
        asyncio.run(run_test())
    
    def test_context_optimization_integration(self):
        """
        Test that context optimization works in integration with AI orchestrator
        """
        async def run_test():
            ai_orchestrator, user_profiles, temp_dir = self.create_test_components()
            
            try:
                user_id = 11111
                
                # Add enough conversations to trigger context optimization
                for i in range(25):  # Above optimization threshold
                    conversation = f"Aviation conversation {i} about flight training and aircraft systems"
                    await user_profiles.update_profile_from_conversation(user_id, conversation)
                
                # Get profile to check optimization
                profile = await user_profiles.get_profile(user_id)
                
                # Verify context optimization occurred
                assert profile.get("context_optimizations", 0) > 0
                assert profile.get("last_context_optimization") is not None
                assert profile.get("context_optimization_score", 0) > 0
                
                # Verify interests were consolidated
                interests = profile.get("interests", [])
                assert len(interests) == len(set(interests))  # No duplicates
                assert len(interests) <= 10  # Reasonable limit
                
                # Test that optimized context is provided to AI
                context = await user_profiles.get_user_context_for_ai(user_id)
                assert "context_quality" in context
                assert isinstance(context["context_quality"], (int, float))
                
            finally:
                self.cleanup_temp_dir(temp_dir)
        
        asyncio.run(run_test())
    
    def test_memory_analytics_integration(self):
        """
        Test that memory analytics work correctly in integrated system
        """
        async def run_test():
            ai_orchestrator, user_profiles, temp_dir = self.create_test_components()
            
            try:
                # Add data for multiple users
                for user_id in [1001, 1002, 1003]:
                    await user_profiles.update_profile_from_conversation(
                        user_id, f"Aviation conversation for user {user_id}"
                    )
                    await user_profiles.record_user_feedback(
                        user_id, "correction", "Response", "Correction"
                    )
                
                # Get analytics
                analytics = await user_profiles.get_memory_analytics()
                
                # Verify analytics reflect the integrated system state
                assert analytics["total_profiles"] >= 3
                assert analytics["total_important_conversations"] >= 0
                assert analytics["total_corrections"] >= 3
                assert analytics["average_relevance_score"] > 0
                
                # Verify system stats
                orchestrator_stats = ai_orchestrator.get_orchestrator_stats()
                assert "ai_model_loaded" in orchestrator_stats
                assert orchestrator_stats["ai_model_loaded"] is True
                
            finally:
                self.cleanup_temp_dir(temp_dir)
        
        asyncio.run(run_test())