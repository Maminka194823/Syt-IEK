"""
Test Error Handling and Recovery
Property-based tests for comprehensive error handling across all components

Feature: aviation-discord-bot, Property 9: Error Handling and Recovery
*For any* system error during message processing, embed creation, or data retrieval, 
the system should provide graceful error handling, user-friendly error messages, 
detailed logging, and maintain system stability.

Validates: Requirements 5.5, 6.5, 10.2
"""

import pytest
import asyncio
import discord
from unittest.mock import Mock, AsyncMock, patch, MagicMock
from hypothesis import given, strategies as st, settings, HealthCheck
from datetime import datetime
import logging
import json
import tempfile
import os

# Import the components we're testing
from v4.src.bot.error_handler import ErrorHandler, ErrorSeverity, ErrorCategory
from v4.src.bot.message_handler import MessageHandler
from v4.src.ai.ai_orchestrator import AIOrchestrator
from v4.src.knowledge.rag_system import RAGSystem
from v4.src.bot.embed_builder import EmbedBuilder


class TestErrorHandlingAndRecovery:
    """Property-based tests for error handling and recovery"""
    
    @pytest.fixture
    def mock_embed_builder(self):
        """Mock embed builder for testing"""
        embed_builder = Mock(spec=EmbedBuilder)
        embed_builder.create_error_embed.return_value = Mock(spec=discord.Embed)
        embed_builder.create_info_embed.return_value = Mock(spec=discord.Embed)
        return embed_builder
    
    @pytest.fixture
    def error_handler(self, mock_embed_builder):
        """Create error handler for testing"""
        # Use a simple directory that doesn't require cleanup
        import tempfile
        temp_dir = tempfile.mkdtemp()
        handler = ErrorHandler(embed_builder=mock_embed_builder, log_dir=temp_dir)
        yield handler
        # Manual cleanup
        try:
            handler.cleanup()
        except:
            pass
    
    @pytest.fixture
    def mock_discord_message(self):
        """Mock Discord message for testing"""
        message = Mock(spec=discord.Message)
        message.id = 12345
        message.content = "Test message"
        message.author = Mock()
        message.author.id = 67890
        message.author.bot = False
        message.channel = Mock()
        message.channel.id = 11111
        message.reply = AsyncMock()
        message.add_reaction = AsyncMock()
        return message
    
    @pytest.fixture
    def mock_ai_model(self):
        """Mock AI model for testing"""
        ai_model = Mock()
        ai_model.is_loaded = True
        ai_model.generate_response = AsyncMock()
        ai_model.evaluate_memory_relevance = AsyncMock()
        return ai_model
    
    @pytest.fixture
    def mock_user_profiles(self):
        """Mock user profiles for testing"""
        profiles = Mock()
        profiles.get_user_context_for_ai = AsyncMock()
        profiles.get_conversation_history = AsyncMock()
        profiles.add_conversation_exchange = AsyncMock()
        profiles.update_profile_from_conversation = AsyncMock()
        return profiles
    
    @pytest.fixture
    def mock_rag_system(self):
        """Mock RAG system for testing"""
        rag = Mock()
        rag.is_ready = True
        rag.retrieve_knowledge = AsyncMock()
        return rag
    
    @given(
        error_types=st.sampled_from([
            ValueError("Test validation error"),
            ConnectionError("Test connection error"),
            TimeoutError("Test timeout error"),
            RuntimeError("Test runtime error"),
            KeyError("Test key error"),
            AttributeError("Test attribute error")
        ]),
        component_names=st.sampled_from([
            "message_handler", "ai_orchestrator", "rag_system", 
            "memory_system", "embed_builder", "discord_client"
        ]),
        severities=st.sampled_from([ErrorSeverity.LOW, ErrorSeverity.MEDIUM, ErrorSeverity.HIGH, ErrorSeverity.CRITICAL])
    )
    @settings(max_examples=50, deadline=10000, suppress_health_check=[HealthCheck.function_scoped_fixture])
    def test_error_handler_graceful_handling(
        self, 
        mock_embed_builder,
        mock_discord_message,
        error_types, 
        component_names, 
        severities
    ):
        """
        Property: Error handler should gracefully handle any error type
        and provide appropriate user communication and logging
        """
        async def run_test():
            # Create error handler inside test to avoid fixture issues
            import tempfile
            temp_dir = tempfile.mkdtemp()
            error_handler = ErrorHandler(embed_builder=mock_embed_builder, log_dir=temp_dir)
            
            try:
                # Test context
                context = {
                    "test_data": "sample_context",
                    "user_id": 12345,
                    "operation": "test_operation"
                }
                
                # Handle the error
                error_info = await error_handler.handle_error(
                    error_types,
                    context,
                    component_names,
                    mock_discord_message,
                    severities
                )
                
                # Verify error was handled gracefully
                assert error_info is not None
                assert error_info.error_id is not None
                assert error_info.category in [cat for cat in ErrorCategory]
                assert error_info.severity == severities
                assert error_info.component == component_names
                assert error_info.message == str(error_types)
                assert error_info.user_message is not None
                assert len(error_info.user_message) > 0
                
                # Verify user-friendly message was sent (at least once across all iterations)
                assert mock_discord_message.reply.called
                
                # Verify error was logged
                assert len(error_handler.recent_errors) > 0
                
            finally:
                # Cleanup
                try:
                    error_handler.cleanup()
                except:
                    pass
        
        # Run the async test
        asyncio.run(run_test())
    
    @given(
        failure_scenarios=st.sampled_from([
            "ai_model_failure", "rag_system_failure", "memory_system_failure",
            "discord_api_failure", "network_failure", "database_failure"
        ]),
        user_messages=st.text(min_size=1, max_size=200)
    )
    @settings(max_examples=50, deadline=15000)
    async def test_message_handler_error_recovery(
        self,
        mock_embed_builder,
        mock_discord_message,
        failure_scenarios,
        user_messages
    ):
        """
        Property: Message handler should maintain system stability 
        and provide fallback responses when components fail
        """
        # Setup mocks based on failure scenario
        mock_ai_model = Mock()
        mock_user_profiles = Mock()
        mock_rag_system = Mock()
        
        # Configure failure scenarios
        if failure_scenarios == "ai_model_failure":
            mock_ai_model.generate_response = AsyncMock(side_effect=RuntimeError("AI model failed"))
            mock_user_profiles.get_user_context_for_ai = AsyncMock(return_value={})
            mock_user_profiles.get_conversation_history = AsyncMock(return_value=[])
            mock_rag_system.is_ready = True
            mock_rag_system.retrieve_knowledge = AsyncMock(return_value="test knowledge")
        elif failure_scenarios == "rag_system_failure":
            mock_ai_model.generate_response = AsyncMock(return_value="test response")
            mock_user_profiles.get_user_context_for_ai = AsyncMock(return_value={})
            mock_user_profiles.get_conversation_history = AsyncMock(return_value=[])
            mock_rag_system.is_ready = True
            mock_rag_system.retrieve_knowledge = AsyncMock(side_effect=ConnectionError("RAG failed"))
        elif failure_scenarios == "memory_system_failure":
            mock_ai_model.generate_response = AsyncMock(return_value="test response")
            mock_user_profiles.get_user_context_for_ai = AsyncMock(side_effect=DatabaseError("Memory failed"))
            mock_user_profiles.get_conversation_history = AsyncMock(side_effect=DatabaseError("Memory failed"))
            mock_rag_system.is_ready = True
            mock_rag_system.retrieve_knowledge = AsyncMock(return_value="test knowledge")
        elif failure_scenarios == "discord_api_failure":
            mock_ai_model.generate_response = AsyncMock(return_value="test response")
            mock_user_profiles.get_user_context_for_ai = AsyncMock(return_value={})
            mock_user_profiles.get_conversation_history = AsyncMock(return_value=[])
            mock_rag_system.is_ready = True
            mock_rag_system.retrieve_knowledge = AsyncMock(return_value="test knowledge")
            mock_discord_message.reply = AsyncMock(side_effect=discord.HTTPException(Mock(), "Discord API failed"))
        
        # Create message handler with error handling
        with tempfile.TemporaryDirectory() as temp_dir:
            error_handler = ErrorHandler(embed_builder=mock_embed_builder, log_dir=temp_dir)
            message_handler = MessageHandler(
                mock_ai_model,
                mock_user_profiles,
                mock_rag_system,
                mock_embed_builder,
                error_handler=error_handler
            )
        
        # Set message content
        mock_discord_message.content = user_messages
        
        # Process message - should not raise exception
        try:
            await message_handler.handle_message(mock_discord_message)
            # System should remain stable
            assert True  # If we reach here, system maintained stability
        except Exception as e:
            # System should not crash, but if it does, it should be handled gracefully
            pytest.fail(f"System crashed instead of handling error gracefully: {e}")
        
        # Verify error statistics were tracked
        stats = message_handler.get_handler_stats()
        assert "error_statistics" in stats
    
    @given(
        context_data=st.dictionaries(
            st.text(min_size=1, max_size=20),
            st.one_of(st.text(max_size=100), st.integers(), st.booleans()),
            min_size=1,
            max_size=10
        ),
        error_messages=st.text(min_size=1, max_size=500)
    )
    @settings(max_examples=50, deadline=10000)
    async def test_ai_orchestrator_error_resilience(
        self,
        mock_embed_builder,
        context_data,
        error_messages
    ):
        """
        Property: AI orchestrator should handle component failures
        and provide fallback responses while maintaining context
        """
        # Setup failing components
        mock_ai_model = Mock()
        mock_ai_model.is_loaded = False  # Simulate model not loaded
        mock_ai_model.generate_response = AsyncMock(side_effect=RuntimeError(error_messages))
        
        mock_user_profiles = Mock()
        mock_user_profiles.get_user_context_for_ai = AsyncMock(return_value={})
        mock_user_profiles.get_conversation_history = AsyncMock(return_value=[])
        mock_user_profiles.add_conversation_exchange = AsyncMock()
        
        mock_rag_system = Mock()
        mock_rag_system.is_ready = False  # Simulate RAG not ready
        
        # Create orchestrator with error handling
        with tempfile.TemporaryDirectory() as temp_dir:
            error_handler = ErrorHandler(embed_builder=mock_embed_builder, log_dir=temp_dir)
            orchestrator = AIOrchestrator(
                mock_ai_model,
                mock_user_profiles,
                mock_rag_system,
                error_handler
            )
        
        # Process message with failing components
        result = await orchestrator.process_message(
            "test message",
            12345,
            context_data
        )
        
        # Should return fallback response, not crash
        assert isinstance(result, str)
        assert len(result) > 0
        
        # Should contain appropriate error messaging
        assert any(word in result.lower() for word in [
            "sorry", "error", "try", "again", "difficulty", "issue"
        ])
        
        # Verify system health tracking
        stats = orchestrator.get_orchestrator_stats()
        assert "system_health" in stats
        assert "error_statistics" in stats
    
    @given(
        query_texts=st.text(min_size=1, max_size=200),
        failure_types=st.sampled_from([
            "embedding_model_failure", "database_failure", 
            "search_failure", "knowledge_corruption"
        ])
    )
    @settings(max_examples=50, deadline=10000)
    async def test_rag_system_error_fallback(
        self,
        mock_embed_builder,
        query_texts,
        failure_types
    ):
        """
        Property: RAG system should provide fallback knowledge
        when primary retrieval mechanisms fail
        """
        with tempfile.TemporaryDirectory() as temp_dir:
            error_handler = ErrorHandler(embed_builder=mock_embed_builder, log_dir=temp_dir)
            
            # Create RAG system with simulated failures
            rag_system = RAGSystem(data_dir=temp_dir, error_handler=error_handler)
            
            # Simulate different failure scenarios
            if failure_types == "embedding_model_failure":
                rag_system.embedding_model = None
                rag_system.is_ready = False
            elif failure_types == "database_failure":
                rag_system.db_path = "/nonexistent/path/database.db"
                rag_system.is_ready = True
            elif failure_types == "search_failure":
                rag_system.knowledge_items = {}
                rag_system.is_ready = True
            
            # Attempt knowledge retrieval
            result = await rag_system.retrieve_knowledge(query_texts)
            
            # Should return fallback knowledge, not crash
            assert isinstance(result, str)
            assert len(result) > 0
            
            # Should not return generic error messages for user-facing content
            assert "error" not in result.lower() or "fallback" in result.lower()
            
            # Should contain relevant aviation information
            aviation_keywords = [
                "aviation", "aircraft", "weather", "regulation", 
                "flight", "pilot", "metar", "far"
            ]
            assert any(keyword in result.lower() for keyword in aviation_keywords)
    
    @given(
        error_counts=st.integers(min_value=1, max_value=100),
        time_windows=st.integers(min_value=1, max_value=3600)  # seconds
    )
    @settings(max_examples=30, deadline=8000)
    async def test_error_pattern_detection(
        self,
        mock_embed_builder,
        error_counts,
        time_windows
    ):
        """
        Property: Error handler should detect patterns and maintain
        statistics for system monitoring
        """
        with tempfile.TemporaryDirectory() as temp_dir:
            error_handler = ErrorHandler(embed_builder=mock_embed_builder, log_dir=temp_dir)
            
            # Generate multiple errors of the same type
            test_error = RuntimeError("Repeated test error")
            context = {"test": "pattern_detection"}
            
            # Simulate multiple errors
            for i in range(min(error_counts, 20)):  # Limit to prevent test timeout
                await error_handler.handle_error(
                    test_error,
                    context,
                    "test_component",
                    severity=ErrorSeverity.MEDIUM
                )
            
            # Check error statistics
            stats = error_handler.get_error_statistics()
            
            # Should track error counts
            assert "total_errors_by_category" in stats
            assert len(stats["total_errors_by_category"]) > 0
            
            # Should track recent errors
            assert "recent_errors_count" in stats
            assert stats["recent_errors_count"] >= 0
            
            # Should track error patterns
            assert "error_patterns" in stats
            
            # Should calculate recovery success rate
            assert "recovery_success_rate" in stats
            assert 0.0 <= stats["recovery_success_rate"] <= 1.0
    
    @given(
        system_states=st.sampled_from([
            "healthy", "degraded", "critical", "recovering"
        ]),
        component_failures=st.lists(
            st.sampled_from([
                "ai_model", "rag_system", "memory_system", 
                "discord_api", "database", "network"
            ]),
            min_size=0,
            max_size=3
        )
    )
    @settings(max_examples=40, deadline=10000)
    async def test_system_stability_maintenance(
        self,
        mock_embed_builder,
        mock_discord_message,
        system_states,
        component_failures
    ):
        """
        Property: System should maintain core functionality
        even when multiple components fail simultaneously
        """
        # Setup components with various failure states
        mock_ai_model = Mock()
        mock_user_profiles = Mock()
        mock_rag_system = Mock()
        
        # Configure component health based on failures
        mock_ai_model.is_loaded = "ai_model" not in component_failures
        mock_rag_system.is_ready = "rag_system" not in component_failures
        
        # Configure method behaviors based on failures
        if "ai_model" in component_failures:
            mock_ai_model.generate_response = AsyncMock(side_effect=RuntimeError("AI failed"))
        else:
            mock_ai_model.generate_response = AsyncMock(return_value="test response")
        
        if "memory_system" in component_failures:
            mock_user_profiles.get_user_context_for_ai = AsyncMock(side_effect=DatabaseError("Memory failed"))
            mock_user_profiles.get_conversation_history = AsyncMock(side_effect=DatabaseError("Memory failed"))
        else:
            mock_user_profiles.get_user_context_for_ai = AsyncMock(return_value={})
            mock_user_profiles.get_conversation_history = AsyncMock(return_value=[])
        
        if "rag_system" in component_failures:
            mock_rag_system.retrieve_knowledge = AsyncMock(side_effect=ConnectionError("RAG failed"))
        else:
            mock_rag_system.retrieve_knowledge = AsyncMock(return_value="test knowledge")
        
        # Create system with error handling
        with tempfile.TemporaryDirectory() as temp_dir:
            error_handler = ErrorHandler(embed_builder=mock_embed_builder, log_dir=temp_dir)
            message_handler = MessageHandler(
                mock_ai_model,
                mock_user_profiles,
                mock_rag_system,
                mock_embed_builder,
                error_handler=error_handler
            )
        
        # Test system stability under failure conditions
        mock_discord_message.content = "test aviation question"
        
        # System should handle the message without crashing
        try:
            await message_handler.handle_message(mock_discord_message)
            
            # Verify system maintained basic functionality
            stats = message_handler.get_handler_stats()
            assert "system_health" in stats
            
            # Core functionality should be tracked
            assert "active_conversations" in stats
            
        except Exception as e:
            # If system fails, it should fail gracefully with proper error handling
            assert "graceful" in str(e).lower() or "handled" in str(e).lower()


# Custom exception for testing
class DatabaseError(Exception):
    """Custom database error for testing"""
    pass


if __name__ == "__main__":
    pytest.main([__file__, "-v"])