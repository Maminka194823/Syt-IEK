"""
Property-based test for AI response generation with context
Tests Property 3: AI Response Generation with Context
"""

import pytest
from hypothesis import given, strategies as st, settings
import asyncio
from unittest.mock import AsyncMock, MagicMock
from datetime import datetime
import json

from v4.src.ai.ai_orchestrator import AIOrchestrator
from v4.src.ai.model_loader import AIModelManager
from v4.src.memory.user_profiles import UserProfileManager
from v4.src.knowledge.rag_system import RAGSystem


# Feature: aviation-discord-bot, Property 3: AI Response Generation with Context
# **Validates: Requirements 2.1, 2.2, 2.3, 2.4**


class TestAIResponseGenerationWithContext:
    """
    Property-based tests for AI response generation with context
    
    Property 3: For any user message, the AI system should generate responses 
    that incorporate user context, aviation knowledge, maintain conversation 
    history, and adapt to the user's experience level when known.
    """
    
    def create_mock_ai_model(self):
        """Create mock AI model for testing"""
        mock = AsyncMock(spec=AIModelManager)
        mock.is_loaded = True
        mock.generate_response = AsyncMock(return_value="Test AI response with context")
        mock.evaluate_memory_relevance = AsyncMock(return_value={
            "relevance_score": 7,
            "experience_level": "private",
            "interests": ["cessna", "vfr"],
            "learning_goals": ["instrument_rating"],
            "knowledge_gaps": ["weather"],
            "experiences": []
        })
        return mock
    
    def create_mock_user_profiles(self):
        """Create mock user profiles manager for testing"""
        mock = AsyncMock(spec=UserProfileManager)
        mock.get_user_context_for_ai = AsyncMock(return_value={
            "experience_level": "private",
            "interests": ["cessna", "navigation"],
            "learning_goals": ["instrument_rating"],
            "detail_level": "medium",
            "conversation_style": "friendly"
        })
        mock.get_conversation_history = AsyncMock(return_value=[
            {"user": "What's a VOR?", "assistant": "A VOR is a navigation aid..."},
            {"user": "How do I use it?", "assistant": "To use a VOR, you tune..."}
        ])
        mock.add_conversation_exchange = AsyncMock()
        mock.update_profile_from_conversation = AsyncMock()
        return mock
    
    def create_mock_rag_system(self):
        """Create mock RAG system for testing"""
        mock = AsyncMock(spec=RAGSystem)
        mock.is_ready = True
        mock.retrieve_knowledge = AsyncMock(return_value="Relevant aviation knowledge context")
        return mock
    
    def create_ai_orchestrator(self):
        """Create AI orchestrator with mocked dependencies"""
        mock_ai_model = self.create_mock_ai_model()
        mock_user_profiles = self.create_mock_user_profiles()
        mock_rag_system = self.create_mock_rag_system()
        
        orchestrator = AIOrchestrator(
            ai_model=mock_ai_model,
            user_profiles=mock_user_profiles,
            rag_system=mock_rag_system
        )
        
        return orchestrator, mock_ai_model, mock_user_profiles, mock_rag_system
    
    @given(
        user_message=st.text(min_size=1, max_size=500).filter(lambda x: x.strip()),
        user_id=st.integers(min_value=1, max_value=999999999999999999),  # Valid Discord user ID range
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
        )
    )
    @settings(max_examples=100, deadline=10000)
    def test_ai_response_incorporates_user_context(
        self, user_message, user_id, experience_level, interests, learning_goals
    ):
        """
        Property: AI responses should incorporate user context including 
        experience level, interests, and learning goals
        """
        async def run_test():
            ai_orchestrator, mock_ai_model, mock_user_profiles, mock_rag_system = self.create_ai_orchestrator()
            
            # Setup user context
            user_context = {
                "experience_level": experience_level,
                "interests": interests,
                "learning_goals": learning_goals,
                "detail_level": "medium",
                "conversation_style": "friendly"
            }
            mock_user_profiles.get_user_context_for_ai.return_value = user_context
            
            # Process message
            response = await ai_orchestrator.process_message(user_message, user_id)
            
            # Verify AI model was called with user context
            mock_ai_model.generate_response.assert_called_once()
            call_args = mock_ai_model.generate_response.call_args
            
            # Check that user context was passed to AI model
            assert call_args[1]['user_context'] == user_context
            assert call_args[1]['message'] == user_message
            
            # Verify response is generated
            assert isinstance(response, str)
            assert len(response) > 0
        
        asyncio.run(run_test())
    
    @given(
        user_message=st.text(min_size=1, max_size=500).filter(lambda x: x.strip()),
        user_id=st.integers(min_value=1, max_value=999999999999999999),
        knowledge_context=st.text(min_size=0, max_size=1000)
    )
    @settings(max_examples=100, deadline=10000)
    def test_ai_response_incorporates_aviation_knowledge(
        self, user_message, user_id, knowledge_context
    ):
        """
        Property: AI responses should incorporate relevant aviation knowledge 
        retrieved from the RAG system
        """
        async def run_test():
            ai_orchestrator, mock_ai_model, mock_user_profiles, mock_rag_system = self.create_ai_orchestrator()
            
            # Setup knowledge context
            mock_rag_system.retrieve_knowledge.return_value = knowledge_context
            
            # Process message
            response = await ai_orchestrator.process_message(user_message, user_id)
            
            # Verify RAG system was queried
            mock_rag_system.retrieve_knowledge.assert_called_once()
            rag_call_args = mock_rag_system.retrieve_knowledge.call_args
            assert rag_call_args[1]['query'] == user_message
            
            # Verify AI model received knowledge context
            mock_ai_model.generate_response.assert_called_once()
            ai_call_args = mock_ai_model.generate_response.call_args
            assert ai_call_args[1]['knowledge_context'] == knowledge_context
            
            # Verify response is generated
            assert isinstance(response, str)
            assert len(response) > 0
        
        asyncio.run(run_test())
    
    @given(
        user_message=st.text(min_size=1, max_size=500).filter(lambda x: x.strip()),
        user_id=st.integers(min_value=1, max_value=999999999999999999),
        conversation_history=st.lists(
            st.fixed_dictionaries({
                'user': st.text(min_size=1, max_size=200),
                'assistant': st.text(min_size=1, max_size=200)
            }),
            min_size=0, max_size=5
        )
    )
    @settings(max_examples=100, deadline=10000)
    def test_ai_response_maintains_conversation_history(
        self, user_message, user_id, conversation_history
    ):
        """
        Property: AI responses should maintain and reference conversation history
        for multi-turn conversations
        """
        async def run_test():
            ai_orchestrator, mock_ai_model, mock_user_profiles, mock_rag_system = self.create_ai_orchestrator()
            
            # Setup conversation history
            mock_user_profiles.get_conversation_history.return_value = conversation_history
            
            # Process message
            response = await ai_orchestrator.process_message(user_message, user_id)
            
            # Verify conversation history was retrieved
            mock_user_profiles.get_conversation_history.assert_called_once_with(user_id, limit=5)
            
            # Verify AI model received conversation history
            mock_ai_model.generate_response.assert_called_once()
            ai_call_args = mock_ai_model.generate_response.call_args
            assert ai_call_args[1]['conversation_history'] == conversation_history
            
            # Verify conversation exchange was stored
            mock_user_profiles.add_conversation_exchange.assert_called_once_with(
                user_id, user_message, mock_ai_model.generate_response.return_value
            )
            
            # Verify response is generated
            assert isinstance(response, str)
            assert len(response) > 0
        
        asyncio.run(run_test())
    
    @given(
        user_message=st.text(min_size=1, max_size=500).filter(lambda x: x.strip()),
        user_id=st.integers(min_value=1, max_value=999999999999999999),
        experience_levels=st.sampled_from(["student", "private", "commercial", "atp", "instructor"])
    )
    @settings(max_examples=100, deadline=10000)
    def test_ai_response_adapts_to_experience_level(
        self, user_message, user_id, experience_levels
    ):
        """
        Property: AI responses should adapt complexity and terminology 
        based on user's aviation experience level
        """
        async def run_test():
            ai_orchestrator, mock_ai_model, mock_user_profiles, mock_rag_system = self.create_ai_orchestrator()
            
            # Setup user context with specific experience level
            user_context = {
                "experience_level": experience_levels,
                "interests": ["general_aviation"],
                "learning_goals": [],
                "detail_level": "medium",
                "conversation_style": "friendly"
            }
            mock_user_profiles.get_user_context_for_ai.return_value = user_context
            
            # Process message
            response = await ai_orchestrator.process_message(user_message, user_id)
            
            # Verify user context with experience level was passed to AI
            mock_ai_model.generate_response.assert_called_once()
            ai_call_args = mock_ai_model.generate_response.call_args
            passed_context = ai_call_args[1]['user_context']
            
            assert passed_context['experience_level'] == experience_levels
            
            # Verify response is generated
            assert isinstance(response, str)
            assert len(response) > 0
        
        asyncio.run(run_test())
    
    @given(
        user_message=st.text(min_size=1, max_size=500).filter(lambda x: x.strip()),
        user_id=st.integers(min_value=1, max_value=999999999999999999)
    )
    @settings(max_examples=100, deadline=10000)
    def test_memory_evaluation_and_update(
        self, user_message, user_id
    ):
        """
        Property: AI system should evaluate conversation relevance and 
        update user memory appropriately
        """
        async def run_test():
            ai_orchestrator, mock_ai_model, mock_user_profiles, mock_rag_system = self.create_ai_orchestrator()
            
            # Process message
            response = await ai_orchestrator.process_message(user_message, user_id)
            
            # Verify memory relevance was evaluated
            mock_ai_model.evaluate_memory_relevance.assert_called_once()
            memory_call_args = mock_ai_model.evaluate_memory_relevance.call_args
            conversation_text = memory_call_args[0][0]
            
            # Verify conversation text includes both user message and AI response
            assert user_message in conversation_text
            assert mock_ai_model.generate_response.return_value in conversation_text
            
            # Verify user profile was updated with analysis
            mock_user_profiles.update_profile_from_conversation.assert_called_once()
            update_call_args = mock_user_profiles.update_profile_from_conversation.call_args
            assert update_call_args[0][0] == user_id
            assert update_call_args[0][1] == conversation_text
            
            # Verify response is generated
            assert isinstance(response, str)
            assert len(response) > 0
        
        asyncio.run(run_test())
    
    @given(
        user_message=st.text(min_size=1, max_size=500).filter(lambda x: x.strip()),
        user_id=st.integers(min_value=1, max_value=999999999999999999)
    )
    @settings(max_examples=100, deadline=10000)
    def test_context_assembly_completeness(
        self, user_message, user_id
    ):
        """
        Property: Context assembly should gather information from all available 
        sources (user profile, knowledge base, conversation state)
        """
        async def run_test():
            ai_orchestrator, mock_ai_model, mock_user_profiles, mock_rag_system = self.create_ai_orchestrator()
            
            # Process message to trigger context assembly
            await ai_orchestrator.process_message(user_message, user_id)
            
            # Verify all context sources were consulted
            mock_user_profiles.get_user_context_for_ai.assert_called_once_with(user_id)
            mock_rag_system.retrieve_knowledge.assert_called_once()
            mock_user_profiles.get_conversation_history.assert_called_once()
            
            # Test context assembly directly
            context = await ai_orchestrator.assemble_context(user_id, user_message)
            
            # Verify context structure
            assert isinstance(context, dict)
            assert 'user_context' in context
            assert 'knowledge_context' in context
            assert 'conversation_state' in context
            assert 'additional_context' in context
            
            # Verify context contains expected data types
            assert isinstance(context['user_context'], dict)
            assert isinstance(context['knowledge_context'], str)
            assert isinstance(context['conversation_state'], dict)
            assert isinstance(context['additional_context'], dict)
        
        asyncio.run(run_test())
    
    @given(
        user_message=st.text(min_size=1, max_size=500).filter(lambda x: x.strip()),
        user_id=st.integers(min_value=1, max_value=999999999999999999)
    )
    @settings(max_examples=100, deadline=10000)
    def test_error_handling_graceful_degradation(
        self, user_message, user_id
    ):
        """
        Property: AI system should handle errors gracefully and still 
        provide responses even when subsystems fail
        """
        async def run_test():
            ai_orchestrator, mock_ai_model, mock_user_profiles, mock_rag_system = self.create_ai_orchestrator()
            
            # Test with AI model failure
            mock_ai_model.generate_response.side_effect = Exception("AI model error")
            
            response = await ai_orchestrator.process_message(user_message, user_id)
            
            # Should still return a response (error message)
            assert isinstance(response, str)
            assert len(response) > 0
            assert "error" in response.lower()
            
            # Reset for next test
            mock_ai_model.generate_response.side_effect = None
            mock_ai_model.generate_response.return_value = "Test response"
            
            # Test with RAG system failure
            mock_rag_system.retrieve_knowledge.side_effect = Exception("RAG error")
            
            response = await ai_orchestrator.process_message(user_message, user_id)
            
            # Should still generate response without knowledge context
            assert isinstance(response, str)
            assert len(response) > 0
        
        asyncio.run(run_test())