"""
V4 AI Orchestrator
Central coordination of AI processing and context management
Coordinates between AI model, memory system, and knowledge retrieval
"""

import logging
from typing import Dict, Any, Optional, List
import asyncio
from datetime import datetime

from .model_loader import AIModelManager
from ..memory.user_profiles import UserProfileManager
from ..knowledge.rag_system import RAGSystem
from ..bot.error_handler import ErrorHandler, ErrorSeverity, handle_errors


class AIOrchestrator:
    """
    Central coordinator for all AI processing
    Manages context assembly, conversation state, and memory decisions
    """
    
    def __init__(
        self,
        ai_model: AIModelManager,
        user_profiles: UserProfileManager,
        rag_system: RAGSystem,
        error_handler: Optional[ErrorHandler] = None
    ):
        self.ai_model = ai_model
        self.user_profiles = user_profiles
        self.rag_system = rag_system
        self.error_handler = error_handler or ErrorHandler()
        
        # Set self as the AI orchestrator in user profiles for AI-driven memory evaluation
        if hasattr(self.user_profiles, 'ai_orchestrator'):
            self.user_profiles.ai_orchestrator = self
        
        # Conversation state management
        self.active_conversations = {}  # user_id -> conversation_state
        self.context_cache = {}  # user_id -> cached_context
        
        # Configuration
        self.max_context_length = 4000
        self.knowledge_context_limit = 1000
        self.conversation_timeout = 3600  # 1 hour
        
        # Error handling configuration
        self.max_retries = 2
        self.retry_delay = 1.0
        
        # System health tracking
        self.system_health = {
            "ai_model_healthy": True,
            "rag_system_healthy": True,
            "memory_system_healthy": True,
            "last_health_check": datetime.utcnow()
        }
        
    async def process_message(
        self, 
        message: str, 
        user_id: int, 
        context: Dict[str, Any] = None
    ) -> str:
        """
        Main entry point for processing user messages
        Coordinates all AI systems to generate contextual responses
        """
        try:
            # Check system health
            await self._check_system_health()
            
            # Assemble complete context with error handling
            full_context = await self._assemble_context_with_fallback(user_id, message, context)
            
            # Get conversation history with retry
            conversation_history = await self._get_conversation_history_safe(user_id)
            
            # Generate AI response with retry and fallback
            response = await self._generate_response_with_fallback(
                message, full_context, conversation_history
            )
            
            # Store conversation exchange (best effort)
            await self._store_conversation_safe(user_id, message, response)
            
            # Evaluate and update memory (best effort)
            await self._update_memory_safe(user_id, f"User: {message}\nAssistant: {response}")
            
            # Update conversation state
            self._update_conversation_state(user_id, message, response)
            
            return response
            
        except Exception as e:
            await self.error_handler.handle_error(
                e,
                {"user_id": user_id, "message": message[:100]},
                "ai_orchestrator",
                severity=ErrorSeverity.HIGH
            )
            return "I'm sorry, I encountered an error processing your message. Please try again."
    
    async def assemble_context(
        self, 
        user_id: int, 
        message: str, 
        additional_context: Dict[str, Any] = None
    ) -> Dict[str, Any]:
        """
        Assemble complete context from all available sources
        Returns structured context for AI processing
        """
        context = {
            'user_context': {},
            'knowledge_context': '',
            'conversation_state': {},
            'additional_context': additional_context or {}
        }
        
        try:
            # Get user profile context
            user_context = await self.user_profiles.get_user_context_for_ai(user_id)
            context['user_context'] = user_context
            
            # Get relevant knowledge from RAG system
            if self.rag_system and self.rag_system.is_ready:
                knowledge_context = await self.rag_system.retrieve_knowledge(
                    query=message,
                    context={'user_context': user_context}
                )
                
                # Limit knowledge context length
                if len(knowledge_context) > self.knowledge_context_limit:
                    knowledge_context = knowledge_context[:self.knowledge_context_limit] + "..."
                
                context['knowledge_context'] = knowledge_context
            
            # Get conversation state
            conversation_state = self.active_conversations.get(user_id, {})
            context['conversation_state'] = conversation_state
            
            # Cache context for potential reuse
            self.context_cache[user_id] = {
                'context': context,
                'timestamp': datetime.utcnow(),
                'message_hash': hash(message)
            }
            
            return context
            
        except Exception as e:
            logging.error(f"Error assembling context for user {user_id}: {e}")
            return context
    
    async def evaluate_memory_relevance(self, conversation: str) -> Dict[str, Any]:
        """
        Use AI to evaluate what information should be stored in memory
        Returns relevance analysis and extracted information
        """
        try:
            if not self.ai_model or not self.ai_model.is_loaded:
                return {"relevance_score": 0, "extracted_info": {}}
            
            # Use AI model to analyze conversation relevance
            analysis = await self.ai_model.evaluate_memory_relevance(conversation)
            
            # Validate and structure the analysis
            structured_analysis = {
                "relevance_score": analysis.get("relevance_score", 0),
                "extracted_info": {
                    "experience_level": analysis.get("experience_level"),
                    "interests": analysis.get("interests", []),
                    "learning_goals": analysis.get("learning_goals", []),
                    "knowledge_gaps": analysis.get("knowledge_gaps", []),
                    "experiences": analysis.get("experiences", [])
                },
                "timestamp": datetime.utcnow().isoformat(),
                "conversation_length": len(conversation)
            }
            
            return structured_analysis
            
        except Exception as e:
            logging.error(f"Error evaluating memory relevance: {e}")
            return {"relevance_score": 0, "extracted_info": {}}
    
    def _update_conversation_state(
        self, 
        user_id: int, 
        user_message: str, 
        ai_response: str
    ):
        """
        Update conversation state for multi-turn handling
        Tracks conversation flow and context
        """
        if user_id not in self.active_conversations:
            self.active_conversations[user_id] = {
                'started_at': datetime.utcnow(),
                'last_activity': datetime.utcnow(),
                'turn_count': 0,
                'topics': [],
                'context_summary': ''
            }
        
        state = self.active_conversations[user_id]
        state['last_activity'] = datetime.utcnow()
        state['turn_count'] += 1
        
        # Extract and track topics (simple keyword-based)
        topic = self._extract_conversation_topic(user_message, ai_response)
        if topic and topic not in state['topics']:
            state['topics'].append(topic)
            # Keep only recent topics
            state['topics'] = state['topics'][-5:]
        
        # Update context summary for long conversations
        if state['turn_count'] % 5 == 0:  # Every 5 turns
            state['context_summary'] = self._summarize_conversation_context(
                user_message, ai_response, state
            )
    
    def _extract_conversation_topic(self, user_message: str, ai_response: str) -> Optional[str]:
        """
        Extract main topic from conversation exchange
        Simple keyword-based topic detection
        """
        combined_text = (user_message + " " + ai_response).lower()
        
        # Aviation topic keywords
        topic_keywords = {
            'weather': ['weather', 'metar', 'taf', 'wind', 'visibility', 'ceiling', 'clouds'],
            'navigation': ['navigation', 'gps', 'vor', 'ils', 'approach', 'departure', 'route'],
            'aircraft': ['cessna', 'piper', 'boeing', 'airbus', 'helicopter', 'aircraft', 'plane'],
            'regulations': ['far', 'regulation', 'rule', 'legal', 'requirement', 'faa'],
            'training': ['training', 'lesson', 'instructor', 'student', 'practice', 'checkride'],
            'flight_planning': ['flight plan', 'route', 'fuel', 'weight', 'balance', 'performance'],
            'emergency': ['emergency', 'malfunction', 'failure', 'abort', 'divert', 'emergency'],
            'airports': ['airport', 'runway', 'taxiway', 'tower', 'ground', 'atc'],
            'licenses': ['license', 'rating', 'certificate', 'private', 'commercial', 'atp']
        }
        
        for topic, keywords in topic_keywords.items():
            if any(keyword in combined_text for keyword in keywords):
                return topic
        
        return 'general_aviation'
    
    def _summarize_conversation_context(
        self, 
        user_message: str, 
        ai_response: str, 
        state: Dict[str, Any]
    ) -> str:
        """
        Create a brief summary of conversation context
        Used for maintaining context in long conversations
        """
        topics = ", ".join(state.get('topics', []))
        turn_count = state.get('turn_count', 0)
        
        summary = f"Conversation with {turn_count} exchanges covering: {topics}"
        
        # Add recent context
        if len(user_message) > 100:
            recent_context = user_message[:100] + "..."
        else:
            recent_context = user_message
        
        summary += f". Recent: {recent_context}"
        
        return summary
    
    async def _update_memory_from_conversation(
        self, 
        user_id: int, 
        conversation_text: str
    ):
        """
        Evaluate conversation and update user memory if relevant
        Uses AI to determine what information to store
        """
        try:
            # Get AI analysis of conversation relevance
            analysis = await self.evaluate_memory_relevance(conversation_text)
            
            # Update user profile based on analysis
            await self.user_profiles.update_profile_from_conversation(
                user_id, conversation_text, analysis
            )
            
        except Exception as e:
            logging.error(f"Error updating memory for user {user_id}: {e}")
    
    def cleanup_inactive_conversations(self):
        """
        Clean up conversation states that have been inactive
        Called periodically to manage memory usage
        """
        current_time = datetime.utcnow()
        inactive_users = []
        
        for user_id, state in self.active_conversations.items():
            last_activity = state.get('last_activity', current_time)
            if (current_time - last_activity).total_seconds() > self.conversation_timeout:
                inactive_users.append(user_id)
        
        for user_id in inactive_users:
            del self.active_conversations[user_id]
            if user_id in self.context_cache:
                del self.context_cache[user_id]
        
        if inactive_users:
            logging.info(f"Cleaned up {len(inactive_users)} inactive conversations")
    
    def get_conversation_state(self, user_id: int) -> Dict[str, Any]:
        """Get current conversation state for a user"""
        return self.active_conversations.get(user_id, {})
    
    def get_orchestrator_stats(self) -> Dict[str, Any]:
        """Get statistics about the orchestrator"""
        return {
            'active_conversations': len(self.active_conversations),
            'cached_contexts': len(self.context_cache),
            'ai_model_loaded': self.ai_model.is_loaded if self.ai_model else False,
            'rag_system_ready': self.rag_system.is_ready if self.rag_system else False,
            'max_context_length': self.max_context_length,
            'conversation_timeout': self.conversation_timeout,
            'system_health': self.system_health,
            'error_statistics': self.error_handler.get_error_statistics() if self.error_handler else {}
        }
    
    async def _check_system_health(self):
        """Check health of all system components"""
        try:
            current_time = datetime.utcnow()
            
            # Check if we need to update health status
            if (current_time - self.system_health["last_health_check"]).total_seconds() < 60:
                return  # Skip if checked recently
            
            # Check AI model health
            try:
                if hasattr(self.ai_model, 'is_loaded') and self.ai_model.is_loaded:
                    self.system_health["ai_model_healthy"] = True
                else:
                    self.system_health["ai_model_healthy"] = False
            except:
                self.system_health["ai_model_healthy"] = False
            
            # Check RAG system health
            try:
                if hasattr(self.rag_system, 'is_ready') and self.rag_system.is_ready:
                    self.system_health["rag_system_healthy"] = True
                else:
                    self.system_health["rag_system_healthy"] = False
            except:
                self.system_health["rag_system_healthy"] = False
            
            # Check memory system health
            try:
                if self.user_profiles:
                    self.system_health["memory_system_healthy"] = True
                else:
                    self.system_health["memory_system_healthy"] = False
            except:
                self.system_health["memory_system_healthy"] = False
            
            self.system_health["last_health_check"] = current_time
            
        except Exception as e:
            logging.error(f"Error checking system health: {e}")
    
    async def _assemble_context_with_fallback(
        self, 
        user_id: int, 
        message: str, 
        additional_context: Dict[str, Any] = None
    ) -> Dict[str, Any]:
        """Assemble context with error handling and fallbacks"""
        context = {
            'user_context': {},
            'knowledge_context': '',
            'conversation_state': {},
            'additional_context': additional_context or {}
        }
        
        try:
            # Get user profile context with retry
            for attempt in range(self.max_retries + 1):
                try:
                    user_context = await self.user_profiles.get_user_context_for_ai(user_id)
                    context['user_context'] = user_context
                    break
                except Exception as e:
                    if attempt == self.max_retries:
                        logging.error(f"Failed to get user context: {e}")
                        context['user_context'] = {}  # Use empty context
                    else:
                        await asyncio.sleep(self.retry_delay * (attempt + 1))
            
            # Get relevant knowledge from RAG system with fallback
            if self.rag_system and self.rag_system.is_ready:
                try:
                    knowledge_context = await self.rag_system.retrieve_knowledge(
                        query=message,
                        context={'user_context': context['user_context']}
                    )
                    
                    # Limit knowledge context length
                    if len(knowledge_context) > self.knowledge_context_limit:
                        knowledge_context = knowledge_context[:self.knowledge_context_limit] + "..."
                    
                    context['knowledge_context'] = knowledge_context
                except Exception as e:
                    logging.error(f"RAG system error, using fallback: {e}")
                    context['knowledge_context'] = self._get_basic_knowledge_fallback(message)
            
            # Get conversation state
            conversation_state = self.active_conversations.get(user_id, {})
            context['conversation_state'] = conversation_state
            
            # Cache context for potential reuse
            self.context_cache[user_id] = {
                'context': context,
                'timestamp': datetime.utcnow(),
                'message_hash': hash(message)
            }
            
            return context
            
        except Exception as e:
            await self.error_handler.handle_error(
                e,
                {"user_id": user_id, "message": message[:100]},
                "ai_orchestrator",
                severity=ErrorSeverity.MEDIUM
            )
            return context
    
    def _get_basic_knowledge_fallback(self, message: str) -> str:
        """Provide basic knowledge fallback when RAG system fails"""
        message_lower = message.lower()
        
        if any(word in message_lower for word in ["weather", "metar", "taf"]):
            return "Basic weather knowledge: METAR provides current conditions, TAF provides forecasts."
        elif any(word in message_lower for word in ["aircraft", "plane", "cessna"]):
            return "Basic aircraft knowledge: Aircraft specifications include performance, weight, and operational limits."
        elif any(word in message_lower for word in ["regulation", "far", "rule"]):
            return "Basic regulation knowledge: FAA regulations govern aircraft operations and pilot requirements."
        else:
            return "General aviation knowledge available for weather, aircraft, regulations, and flight planning."
    
    async def _get_conversation_history_safe(self, user_id: int, limit: int = 5) -> List[Dict[str, Any]]:
        """Get conversation history with error handling"""
        for attempt in range(self.max_retries + 1):
            try:
                return await self.user_profiles.get_conversation_history(user_id, limit=limit)
            except Exception as e:
                if attempt == self.max_retries:
                    logging.error(f"Failed to get conversation history: {e}")
                    return []  # Return empty history as fallback
                await asyncio.sleep(self.retry_delay * (attempt + 1))
        
        return []
    
    async def _generate_response_with_fallback(
        self,
        message: str,
        full_context: Dict[str, Any],
        conversation_history: List[Dict[str, Any]]
    ) -> str:
        """Generate AI response with fallback handling"""
        for attempt in range(self.max_retries + 1):
            try:
                return await self.ai_model.generate_response(
                    message=message,
                    user_context=full_context.get('user_context', {}),
                    knowledge_context=full_context.get('knowledge_context', ''),
                    conversation_history=conversation_history
                )
            except Exception as e:
                if attempt == self.max_retries:
                    logging.error(f"AI model failed, using fallback response: {e}")
                    return self._get_fallback_response(message)
                await asyncio.sleep(self.retry_delay * (attempt + 1))
        
        return self._get_fallback_response(message)
    
    def _get_fallback_response(self, message: str) -> str:
        """Generate fallback response when AI model fails"""
        message_lower = message.lower()
        
        if any(word in message_lower for word in ["hello", "hi", "hey"]):
            return "Hello! I'm having some technical difficulties, but I'm still here to help with aviation questions."
        elif any(word in message_lower for word in ["weather", "metar"]):
            return "I'd be happy to help with weather information, but I'm experiencing some issues right now. Please try again in a moment."
        elif any(word in message_lower for word in ["aircraft", "plane"]):
            return "I can help with aircraft information, but I'm having some technical difficulties. Please try your question again."
        else:
            return "I'm experiencing some technical issues right now, but I'm working to resolve them. Please try your question again in a moment."
    
    async def _store_conversation_safe(self, user_id: int, message: str, response: str):
        """Store conversation exchange with error handling (best effort)"""
        try:
            await self.user_profiles.add_conversation_exchange(user_id, message, response)
        except Exception as e:
            logging.error(f"Error storing conversation (non-critical): {e}")
    
    async def _update_memory_safe(self, user_id: int, conversation_text: str):
        """Update memory with error handling (best effort)"""
        try:
            await self._update_memory_from_conversation(user_id, conversation_text)
        except Exception as e:
            logging.error(f"Error updating memory (non-critical): {e}")