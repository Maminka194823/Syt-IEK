"""
V4 Message Handler
Comprehensive message processing coordinator with full system integration
Handles concurrent processing, system health monitoring, and end-to-end conversation flow
"""

import discord
import asyncio
import logging
from typing import Optional, Dict, Any, Set
import time
from datetime import datetime, timedelta

from ..ai.ai_orchestrator import AIOrchestrator
from .embed_builder import EmbedBuilder
from .interaction_handler import InteractionHandler
from .rate_limit_manager import RateLimitManager
from .error_handler import ErrorHandler, ErrorSeverity, ErrorCategory, handle_errors
from .performance_monitor import PerformanceMonitor, OperationTracker
from .resource_manager import ResourceManager, DegradationLevel
from ..memory.user_profiles import UserProfileManager
from ..knowledge.rag_system import RAGSystem

class MessageHandler:
    """
    Comprehensive message processing coordinator
    Integrates all systems for end-to-end conversation flow validation
    """
    
    def __init__(
        self, 
        ai_orchestrator: AIOrchestrator,
        user_profiles: UserProfileManager,
        rag_system: RAGSystem,
        embed_builder: EmbedBuilder,
        rate_limit_manager: Optional[RateLimitManager] = None,
        interaction_handler: Optional[InteractionHandler] = None,
        error_handler: Optional[ErrorHandler] = None,
        performance_monitor: Optional[PerformanceMonitor] = None,
        resource_manager: Optional[ResourceManager] = None
    ):
        # Core system integration
        self.ai_orchestrator = ai_orchestrator
        self.user_profiles = user_profiles
        self.rag_system = rag_system
        self.embed_builder = embed_builder
        self.interaction_handler = interaction_handler
        
        # System health and monitoring
        self.rate_limit_manager = rate_limit_manager
        self.error_handler = error_handler or ErrorHandler(embed_builder)
        self.performance_monitor = performance_monitor or PerformanceMonitor()
        self.resource_manager = resource_manager or ResourceManager(self.performance_monitor)
        
        # Register for degradation notifications
        self.resource_manager.register_degradation_callback(self._handle_degradation_change)
        
        # Concurrent processing management
        self.active_conversations = {}  # user_id -> processing_task
        self.processing_lock = asyncio.Lock()
        
        # System health tracking
        self.system_health = {
            "ai_orchestrator_healthy": True,
            "rag_system_healthy": True,
            "memory_system_healthy": True,
            "interaction_handler_healthy": True,
            "last_health_check": datetime.utcnow()
        }
        
        # Response determination settings
        self.bot_mention_keywords = [
            "aviation girl", "aviationgirl", "ag", "hey bot", "bot",
            "aircraft", "plane", "flight", "pilot", "aviation", "flying"
        ]
        
        # Rate limiting per user
        self.user_last_message = {}  # user_id -> timestamp
        self.min_message_interval = 2.0  # seconds
        
        # Message filtering
        self.ignored_channels = set()  # Can be configured
        self.dm_only_mode = False  # Can be configured
        
        # Error recovery settings
        self.max_retries = 2
        self.retry_delay = 1.0
        
        # Degradation-aware settings
        self.max_concurrent_conversations = 5  # Normal mode
        self.degraded_max_concurrent = 2      # Degraded mode
        self.emergency_max_concurrent = 1     # Emergency mode
        
    async def handle_message(self, message: discord.Message) -> None:
        """
        Main message handling entry point
        Determines if response is needed and coordinates processing
        """
        async with OperationTracker(self.performance_monitor, "handle_message", "message_handler", 
                                   {"user_id": message.author.id, "channel_id": message.channel.id}):
            try:
                # Record user activity
                self.performance_monitor.record_user_activity(
                    message.author.id, 
                    "message", 
                    {"content_length": len(message.content)}
                )
                
                # Basic filtering
                if not await self._should_respond(message):
                    return
                
                # Check system health before processing
                await self._check_system_health()
                
                # Check resource constraints
                if not await self._check_resource_constraints(message):
                    return
                
                # Check rate limiting if available
                if self.rate_limit_manager:
                    if not await self.rate_limit_manager.check_message_rate_limit(
                        message.author.id, message.content, message.channel
                    ):
                        return
                else:
                    # Fallback to basic rate limiting check
                    if not await self._check_rate_limit(message.author.id):
                        return
                
                # Process message concurrently without context contamination
                await self._process_message_safely(message)
                
            except discord.HTTPException as e:
                self.performance_monitor.record_error("message_handler", "discord_api_error", 
                                                    {"error": str(e), "status": getattr(e, 'status', None)})
                await self.error_handler.handle_error(
                    e, 
                    {"message_id": message.id, "channel_id": message.channel.id},
                    "message_handler",
                    message,
                    ErrorSeverity.MEDIUM
                )
            except Exception as e:
                self.performance_monitor.record_error("message_handler", "general_error", {"error": str(e)})
                await self.error_handler.handle_error(
                    e,
                    {"message_content": message.content[:100], "user_id": message.author.id},
                    "message_handler", 
                    message,
                    ErrorSeverity.HIGH
                )
    
    async def handle_reaction(self, reaction: discord.Reaction, user: discord.User) -> None:
        """Handle reaction-based interactions through interaction handler"""
        try:
            # Delegate to interaction handler if available
            if self.interaction_handler:
                await self.interaction_handler.process_reaction_interaction(reaction, user)
                return
            
            # Fallback handling if no interaction handler
            # Only handle reactions to bot messages
            if not reaction.message.author.bot:
                return
            
            # Check if it's our bot's message
            bot_user = reaction.message.guild.me if reaction.message.guild else None
            if not bot_user or reaction.message.author.id != bot_user.id:
                return
            
            # Check rate limiting for interactions
            if self.rate_limit_manager:
                if not await self.rate_limit_manager.check_interaction_rate_limit(
                    user.id, "reaction", reaction.message.channel
                ):
                    return
            
            # Handle specific reaction types
            emoji = str(reaction.emoji)
            
            if emoji == "❓":
                # User wants more information
                await self._handle_more_info_request(reaction.message, user)
            elif emoji == "👍":
                # Positive feedback
                await self._handle_positive_feedback(reaction.message, user)
            elif emoji == "👎":
                # Negative feedback
                await self._handle_negative_feedback(reaction.message, user)
            elif emoji == "🔄":
                # Regenerate response
                await self._handle_regenerate_request(reaction.message, user)
                
        except discord.HTTPException as e:
            await self.error_handler.handle_error(
                e,
                {"reaction": str(reaction.emoji), "user_id": user.id},
                "message_handler",
                severity=ErrorSeverity.LOW
            )
        except Exception as e:
            await self.error_handler.handle_error(
                e,
                {"reaction": str(reaction.emoji), "user_id": user.id},
                "message_handler",
                severity=ErrorSeverity.MEDIUM
            )
    
    async def handle_thread_create(self, thread: discord.Thread) -> None:
        """Handle new thread creation through interaction handler"""
        try:
            # Delegate to interaction handler if available
            if self.interaction_handler:
                # Get the starter message if available
                try:
                    starter_message = thread.starter_message or await thread.fetch_message(thread.id)
                    if starter_message and not starter_message.author.bot:
                        await self.interaction_handler.manage_thread_conversation(thread, starter_message)
                except:
                    pass  # Handle gracefully if we can't get the starter message
                return
            
            # Fallback handling if no interaction handler
            # Check if thread was created from our message
            if thread.parent and hasattr(thread, 'starter_message'):
                starter = thread.starter_message
                if starter and starter.author.bot:
                    # Join the thread to participate
                    await thread.join()
                    
                    # Send a friendly thread greeting
                    embed = self.embed_builder.create_info_embed(
                        "Thread Discussion",
                        "I'm here to continue our aviation discussion! Feel free to ask follow-up questions."
                    )
                    await thread.send(embed=embed)
                    
        except discord.HTTPException as e:
            await self.error_handler.handle_error(
                e,
                {"thread_id": thread.id, "thread_name": thread.name},
                "message_handler",
                severity=ErrorSeverity.LOW
            )
        except Exception as e:
            await self.error_handler.handle_error(
                e,
                {"thread_id": thread.id, "thread_name": thread.name},
                "message_handler",
                severity=ErrorSeverity.MEDIUM
            )
    
    async def _should_respond(self, message: discord.Message) -> bool:
        """
        Determine if the bot should respond to this message
        Implements message filtering and response determination logic
        """
        # Don't respond to bots
        if message.author.bot:
            return False
        
        # Don't respond in ignored channels
        if message.channel.id in self.ignored_channels:
            return False
        
        # DM only mode check
        if self.dm_only_mode and not isinstance(message.channel, discord.DMChannel):
            return False
        
        # Always respond to DMs
        if isinstance(message.channel, discord.DMChannel):
            return True
        
        # Check for direct mentions
        if message.guild and message.guild.me in message.mentions:
            return True
        
        # Check for keyword mentions
        message_lower = message.content.lower()
        if any(keyword in message_lower for keyword in self.bot_mention_keywords):
            return True
        
        # Check if replying to bot message
        if message.reference and message.reference.message_id:
            try:
                referenced_message = await message.channel.fetch_message(message.reference.message_id)
                if referenced_message.author.bot and referenced_message.author.id == message.guild.me.id:
                    return True
            except:
                pass
        
        # Check for aviation-related content (basic keyword detection)
        aviation_keywords = [
            "aircraft", "airplane", "plane", "helicopter", "flight", "flying", "pilot",
            "aviation", "airport", "runway", "takeoff", "landing", "weather", "metar",
            "taf", "navigation", "gps", "vor", "ils", "approach", "departure", "atc",
            "cessna", "piper", "boeing", "airbus", "faa", "regulation", "license",
            "rating", "training", "instructor", "student", "solo", "cross country"
        ]
        
        if any(keyword in message_lower for keyword in aviation_keywords):
            return True
        
        return False
    
    async def _check_rate_limit(self, user_id: int) -> bool:
        """Check if user is rate limited"""
        now = time.time()
        last_message = self.user_last_message.get(user_id, 0)
        
        if now - last_message < self.min_message_interval:
            return False
        
        self.user_last_message[user_id] = now
        return True
    
    async def _process_message_safely(self, message: discord.Message) -> None:
        """
        Process message with concurrent safety
        Prevents context contamination between users
        """
        user_id = message.author.id
        
        async with self.processing_lock:
            # Check if user already has an active conversation
            if user_id in self.active_conversations:
                # Cancel previous processing if still running
                previous_task = self.active_conversations[user_id]
                if not previous_task.done():
                    previous_task.cancel()
            
            # Start new processing task
            task = asyncio.create_task(self._process_message_internal(message))
            self.active_conversations[user_id] = task
        
        try:
            await task
        except asyncio.CancelledError:
            logging.info(f"Message processing cancelled for user {user_id}")
        except Exception as e:
            await self.error_handler.handle_error(
                e,
                {"user_id": user_id, "message_content": message.content[:100]},
                "message_handler",
                message,
                ErrorSeverity.HIGH
            )
        finally:
            # Clean up
            async with self.processing_lock:
                if user_id in self.active_conversations:
                    del self.active_conversations[user_id]
    
    async def _process_message_internal(self, message: discord.Message) -> None:
        """
        Internal message processing with comprehensive system integration
        This is where all systems coordinate for end-to-end conversation flow
        """
        user_id = message.author.id
        user_message = message.content
        
        # Show typing indicator
        async with message.channel.typing():
            try:
                # Use AI Orchestrator for comprehensive processing
                async with OperationTracker(self.performance_monitor, "ai_orchestrator_process", "ai_orchestrator"):
                    ai_response = await self.ai_orchestrator.process_message(
                        message=user_message,
                        user_id=user_id,
                        context={
                            "channel_id": message.channel.id,
                            "guild_id": getattr(message.guild, 'id', None),
                            "message_id": message.id,
                            "is_dm": isinstance(message.channel, discord.DMChannel),
                            "degradation_level": self.resource_manager.get_degradation_level().value if self.resource_manager else "normal"
                        }
                    )
                
                # Process and format response for Discord
                async with OperationTracker(self.performance_monitor, "format_response", "message_handler"):
                    formatted_response = await self._format_response_for_discord(ai_response, message)
                
                # Send response with retry
                async with OperationTracker(self.performance_monitor, "send_response", "discord_api"):
                    await self._send_response_with_retry(message, formatted_response)
                
                # Record successful message processing
                self.performance_monitor.record_user_activity(
                    user_id, 
                    "response_received", 
                    {"response_length": len(ai_response)}
                )
                
            except Exception as e:
                # Record error and handle
                self.performance_monitor.record_error("message_handler", "processing_error", {"error": str(e)})
                
                # If all retries failed, send a graceful error response
                await self.error_handler.handle_error(
                    e,
                    {"user_id": user_id, "message": user_message[:100]},
                    "message_handler",
                    message,
                    ErrorSeverity.HIGH
                )
    
    async def _format_response_for_discord(self, response: str, original_message: discord.Message) -> Dict[str, Any]:
        """
        Format AI response for Discord constraints
        Handles message length, embeds, and special formatting
        """
        # Check if response should be an embed
        if self._should_use_embed(response):
            return {
                "type": "embed",
                "embed": self.embed_builder.create_response_embed(response, original_message.author)
            }
        
        # Handle long responses
        if len(response) > 1900:  # Leave room for mentions and formatting
            # Split into multiple messages
            parts = self._split_long_response(response)
            return {
                "type": "multi_message",
                "parts": parts
            }
        
        # Regular text response
        return {
            "type": "text",
            "content": response
        }
    
    def _should_use_embed(self, response: str) -> bool:
        """Determine if response should use embed formatting"""
        # Use embeds for structured data
        embed_indicators = [
            "METAR:", "TAF:", "Aircraft:", "Regulation:", "Weather:",
            "Airport:", "Flight Plan:", "Navigation:", "Emergency:"
        ]
        
        return any(indicator in response for indicator in embed_indicators)
    
    def _split_long_response(self, response: str, max_length: int = 1900) -> list:
        """Split long response into multiple parts"""
        parts = []
        current_part = ""
        
        # Split by sentences first
        sentences = response.split('. ')
        
        for sentence in sentences:
            if len(current_part + sentence + '. ') > max_length:
                if current_part:
                    parts.append(current_part.strip())
                    current_part = sentence + '. '
                else:
                    # Single sentence too long, split by words
                    words = sentence.split()
                    for word in words:
                        if len(current_part + word + ' ') > max_length:
                            if current_part:
                                parts.append(current_part.strip())
                                current_part = word + ' '
                            else:
                                # Single word too long, truncate
                                parts.append(word[:max_length-3] + "...")
                                current_part = ""
                        else:
                            current_part += word + ' '
            else:
                current_part += sentence + '. '
        
        if current_part:
            parts.append(current_part.strip())
        
        return parts
    
    async def _send_response(self, original_message: discord.Message, formatted_response: Dict[str, Any]) -> None:
        """Send the formatted response to Discord"""
        try:
            response_type = formatted_response["type"]
            
            if response_type == "embed":
                await original_message.reply(embed=formatted_response["embed"])
            
            elif response_type == "multi_message":
                parts = formatted_response["parts"]
                for i, part in enumerate(parts):
                    if i == 0:
                        await original_message.reply(part)
                    else:
                        await original_message.channel.send(part)
                    
                    # Small delay between parts
                    if i < len(parts) - 1:
                        await asyncio.sleep(0.5)
            
            elif response_type == "text":
                await original_message.reply(formatted_response["content"])
            
            # Add reaction options for interactive features
            await self._add_interaction_reactions(original_message)
            
        except discord.HTTPException as e:
            logging.error(f"Discord API error sending response: {e}")
            await self._send_error_response(original_message, "I had trouble sending my response. Please try again.")
        except Exception as e:
            logging.error(f"Error sending response: {e}")
            await self._send_error_response(original_message, "Something went wrong sending my response.")
    
    async def _add_interaction_reactions(self, message: discord.Message) -> None:
        """Add reaction options for interactive features"""
        try:
            # Add common interaction reactions
            reactions = ["❓", "👍", "👎"]  # More info, good, bad
            
            for reaction in reactions:
                await message.add_reaction(reaction)
                await asyncio.sleep(0.1)  # Avoid rate limits
                
        except Exception as e:
            logging.debug(f"Could not add reactions: {e}")
    
    async def _update_user_memory(self, user_id: int, user_message: str, ai_response: str) -> None:
        """Update user memory using AI evaluation"""
        try:
            # Combine user message and AI response for analysis
            conversation_text = f"User: {user_message}\nAssistant: {ai_response}"
            
            # Get AI analysis of memory relevance
            memory_analysis = await self.ai_model.evaluate_memory_relevance(conversation_text)
            
            # Update user profile based on analysis
            await self.user_profiles.update_profile_from_conversation(
                user_id, conversation_text, memory_analysis
            )
            
            # Add to conversation history
            await self.user_profiles.add_conversation_exchange(
                user_id, user_message, ai_response
            )
            
        except Exception as e:
            logging.error(f"Error updating user memory: {e}")
    
    async def _send_error_response(self, message: discord.Message, error_text: str) -> None:
        """Send user-friendly error response"""
        try:
            embed = self.embed_builder.create_error_embed(
                "Oops! Something went wrong",
                error_text
            )
            await message.reply(embed=embed)
        except:
            # Fallback to plain text if embed fails
            try:
                await message.reply(f"  {error_text}")
            except:
                logging.error("Could not send error response")
    
    # Interactive feature handlers
    
    async def _handle_more_info_request(self, message: discord.Message, user: discord.User) -> None:
        """Handle request for more information"""
        try:
            embed = self.embed_builder.create_info_embed(
                "More Information",
                "What specific aspect would you like me to elaborate on? Feel free to ask a follow-up question!"
            )
            await message.reply(embed=embed)
        except Exception as e:
            logging.error(f"Error handling more info request: {e}")
    
    async def _handle_positive_feedback(self, message: discord.Message, user: discord.User) -> None:
        """Handle positive feedback"""
        try:
            # Record positive feedback for performance monitoring
            self.performance_monitor.record_user_activity(
                user.id, 
                "feedback", 
                {"rating": 1, "feedback_type": "positive"}
            )
            
            # Update user profile with positive feedback
            profile = await self.user_profiles.get_profile(user.id)
            profile["helpful_responses_received"] = profile.get("helpful_responses_received", 0) + 1
            await self.user_profiles._save_profile(user.id, profile)
            
            # Send acknowledgment
            await message.add_reaction(" ")
        except Exception as e:
            logging.error(f"Error handling positive feedback: {e}")
    
    async def _handle_negative_feedback(self, message: discord.Message, user: discord.User) -> None:
        """Handle negative feedback"""
        try:
            # Record negative feedback for performance monitoring
            self.performance_monitor.record_user_activity(
                user.id, 
                "feedback", 
                {"rating": -1, "feedback_type": "negative"}
            )
            
            embed = self.embed_builder.create_info_embed(
                "Feedback Received",
                "Thanks for the feedback! Could you let me know what I could improve? I'm always learning!"
            )
            await message.reply(embed=embed)
        except Exception as e:
            logging.error(f"Error handling negative feedback: {e}")
    
    async def _handle_regenerate_request(self, message: discord.Message, user: discord.User) -> None:
        """Handle request to regenerate response"""
        try:
            # Find the original user message that triggered this response
            # This is a simplified implementation
            embed = self.embed_builder.create_info_embed(
                "Regenerate Response",
                "Please ask your question again and I'll provide a different response!"
            )
            await message.reply(embed=embed)
        except Exception as e:
            logging.error(f"Error handling regenerate request: {e}")
    
    def get_handler_stats(self) -> Dict[str, Any]:
        """Get statistics about message handling"""
        base_stats = {
            "active_conversations": len(self.active_conversations),
            "rate_limited_users": len(self.user_last_message),
            "ignored_channels": len(self.ignored_channels),
            "dm_only_mode": self.dm_only_mode,
            "min_message_interval": self.min_message_interval,
            "system_health": self.system_health,
            "error_statistics": self.error_handler.get_error_statistics() if self.error_handler else {},
            "max_concurrent_conversations": self.max_concurrent_conversations
        }
        
        # Add performance statistics
        if self.performance_monitor:
            perf_stats = self.performance_monitor.get_performance_stats(time_window_hours=1)
            base_stats["performance"] = perf_stats
            
            # Add system health report
            health_report = self.performance_monitor.get_system_health_report()
            base_stats["system_health_report"] = health_report
            
            # Add user engagement report
            engagement_report = self.performance_monitor.get_user_engagement_report()
            base_stats["user_engagement"] = engagement_report
        
        # Add resource management statistics
        if self.resource_manager:
            resource_status = self.resource_manager.get_resource_status()
            base_stats["resource_status"] = resource_status
            
            # Add degradation information
            base_stats["is_degraded"] = self.resource_manager.is_degraded()
            base_stats["degradation_level"] = self.resource_manager.get_degradation_level().value
            
            # Add user notification if system is degraded
            notification = self.resource_manager.get_user_notification_message()
            if notification:
                base_stats["user_notification"] = notification
        
        return base_stats
    
    async def _check_system_health(self):
        """Check health of all integrated system components"""
        try:
            current_time = datetime.utcnow()
            
            # Check if we need to update health status
            if (current_time - self.system_health["last_health_check"]).total_seconds() < 30:
                return  # Skip if checked recently
            
            # Check AI orchestrator health
            try:
                if hasattr(self.ai_orchestrator, 'system_health') and self.ai_orchestrator.system_health:
                    self.system_health["ai_orchestrator_healthy"] = self.ai_orchestrator.system_health.get("ai_model_healthy", False)
                else:
                    self.system_health["ai_orchestrator_healthy"] = False
            except:
                self.system_health["ai_orchestrator_healthy"] = False
            
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
                    # Try a simple operation to test memory system
                    await self.user_profiles.get_profile(0)  # This should not crash
                    self.system_health["memory_system_healthy"] = True
                else:
                    self.system_health["memory_system_healthy"] = False
            except:
                self.system_health["memory_system_healthy"] = False
            
            # Check interaction handler health
            try:
                if self.interaction_handler:
                    self.system_health["interaction_handler_healthy"] = True
                else:
                    self.system_health["interaction_handler_healthy"] = False
            except:
                self.system_health["interaction_handler_healthy"] = False
            
            self.system_health["last_health_check"] = current_time
            
        except Exception as e:
            logging.error(f"Error checking system health: {e}")
            self.system_health["overall_healthy"] = True  # Assume healthy if we can't test
            self.system_health["last_health_check"] = current_time
    
    async def _get_user_context_with_retry(self, user_id: int) -> Dict[str, Any]:
        """Get user context with retry logic"""
        for attempt in range(self.max_retries + 1):
            try:
                return await self.user_profiles.get_user_context_for_ai(user_id)
            except Exception as e:
                if attempt == self.max_retries:
                    logging.error(f"Failed to get user context after {self.max_retries} retries: {e}")
                    return {}  # Return empty context as fallback
                await asyncio.sleep(self.retry_delay * (attempt + 1))
        
        return {}
    
    async def _get_conversation_history_with_retry(self, user_id: int) -> list:
        """Get conversation history with retry logic"""
        for attempt in range(self.max_retries + 1):
            try:
                return await self.user_profiles.get_conversation_history(user_id)
            except Exception as e:
                if attempt == self.max_retries:
                    logging.error(f"Failed to get conversation history after {self.max_retries} retries: {e}")
                    return []  # Return empty history as fallback
                await asyncio.sleep(self.retry_delay * (attempt + 1))
        
        return []
    
    async def _get_knowledge_context_with_fallback(self, user_message: str, user_context: Dict[str, Any]) -> str:
        """Get knowledge context with fallback handling"""
        knowledge_context = ""
        
        if self.rag_system and self.rag_system.is_ready:
            try:
                knowledge_context = await self.rag_system.retrieve_knowledge(
                    user_message, 
                    user_context
                )
            except Exception as e:
                logging.error(f"RAG system error, using fallback: {e}")
                # Fallback to basic aviation knowledge
                knowledge_context = self._get_basic_aviation_fallback(user_message)
        
        return knowledge_context
    
    def _get_basic_aviation_fallback(self, user_message: str) -> str:
        """Provide basic aviation knowledge fallback when RAG system fails"""
        message_lower = user_message.lower()
        
        if any(word in message_lower for word in ["weather", "metar", "taf"]):
            return "Weather information: METAR and TAF reports provide current and forecast weather conditions for airports."
        elif any(word in message_lower for word in ["aircraft", "plane", "cessna", "piper"]):
            return "Aircraft information: General aviation aircraft come in various categories including single-engine, multi-engine, and helicopters."
        elif any(word in message_lower for word in ["regulation", "far", "rule"]):
            return "Aviation regulations: The FAA publishes Federal Aviation Regulations (FARs) that govern aircraft operations."
        elif any(word in message_lower for word in ["flight", "planning", "navigation"]):
            return "Flight planning: Proper flight planning includes weather, route, fuel, and performance calculations."
        else:
            return "Aviation knowledge: I can help with aircraft, weather, regulations, flight planning, and general aviation topics."
    
    async def _generate_ai_response_with_retry(
        self, 
        user_message: str, 
        user_context: Dict[str, Any], 
        knowledge_context: str, 
        conversation_history: list
    ) -> str:
        """Generate AI response with retry logic"""
        for attempt in range(self.max_retries + 1):
            try:
                return await self.ai_model.generate_response(
                    message=user_message,
                    user_context=user_context,
                    knowledge_context=knowledge_context,
                    conversation_history=conversation_history
                )
            except Exception as e:
                if attempt == self.max_retries:
                    logging.error(f"Failed to generate AI response after {self.max_retries} retries: {e}")
                    # Return a fallback response
                    return self._get_fallback_response(user_message)
                await asyncio.sleep(self.retry_delay * (attempt + 1))
        
        return self._get_fallback_response(user_message)
    
    def _get_fallback_response(self, user_message: str) -> str:
        """Generate a fallback response when AI model fails"""
        message_lower = user_message.lower()
        
        if any(word in message_lower for word in ["hello", "hi", "hey"]):
            return "Hello! I'm Aviation Girl, your aviation assistant. How can I help you with aviation topics today?"
        elif any(word in message_lower for word in ["weather", "metar"]):
            return "I'd be happy to help with weather information, but I'm having trouble accessing my systems right now. Please try again in a moment."
        elif any(word in message_lower for word in ["aircraft", "plane"]):
            return "I can help with aircraft information, but I'm experiencing some technical difficulties. Please try your question again."
        else:
            return "I'm having some technical difficulties right now, but I'm still here to help with aviation questions. Please try again in a moment."
    
    async def _send_response_with_retry(self, message: discord.Message, formatted_response: Dict[str, Any]) -> None:
        """Send response with retry logic for Discord API errors"""
        for attempt in range(self.max_retries + 1):
            try:
                await self._send_response(message, formatted_response)
                return  # Success
            except discord.HTTPException as e:
                if attempt == self.max_retries:
                    # Final attempt failed, try simple text message
                    try:
                        await message.reply("I'm having trouble sending my response. Please try again.")
                    except:
                        pass  # Give up gracefully
                    return
                
                # Wait before retry, with exponential backoff
                await asyncio.sleep(self.retry_delay * (2 ** attempt))
            except Exception as e:
                # Non-Discord errors shouldn't be retried
                logging.error(f"Non-retryable error sending response: {e}")
                return
    
    async def _update_user_memory_safe(self, user_id: int, user_message: str, ai_response: str) -> None:
        """Update user memory with error handling (best effort)"""
        try:
            await self._update_user_memory(user_id, user_message, ai_response)
        except Exception as e:
            # Log error but don't fail the entire message processing
            logging.error(f"Error updating user memory (non-critical): {e}")
            # Could optionally queue for retry later
    
    async def _handle_degradation_change(self, old_level: DegradationLevel, new_level: DegradationLevel, reasons: list):
        """Handle resource degradation level changes"""
        try:
            logging.info(f"Handling degradation change from {old_level.value} to {new_level.value}")
            
            # Adjust concurrent processing limits
            if new_level == DegradationLevel.NORMAL:
                self.max_concurrent_conversations = 5
            elif new_level in [DegradationLevel.LIGHT, DegradationLevel.MODERATE]:
                self.max_concurrent_conversations = self.degraded_max_concurrent
            else:  # SEVERE or CRITICAL
                self.max_concurrent_conversations = self.emergency_max_concurrent
            
            # Cancel excess conversations if needed
            if len(self.active_conversations) > self.max_concurrent_conversations:
                await self._cancel_excess_conversations()
            
            # Update system health tracking
            self.system_health["resource_degradation"] = new_level.value
            self.system_health["degradation_reasons"] = reasons
            
        except Exception as e:
            logging.error(f"Error handling degradation change: {e}")
    
    async def _cancel_excess_conversations(self):
        """Cancel excess conversations when under resource pressure"""
        try:
            excess_count = len(self.active_conversations) - self.max_concurrent_conversations
            if excess_count <= 0:
                return
            
            # Sort conversations by start time (oldest first)
            conversations = list(self.active_conversations.items())
            conversations.sort(key=lambda x: x[1].get_name() if hasattr(x[1], 'get_name') else '')
            
            # Cancel the oldest conversations
            for i in range(excess_count):
                user_id, task = conversations[i]
                if not task.done():
                    task.cancel()
                    logging.info(f"Cancelled conversation for user {user_id} due to resource pressure")
            
        except Exception as e:
            logging.error(f"Error cancelling excess conversations: {e}")
    
    async def _check_resource_constraints(self, message: discord.Message) -> bool:
        """Check if we can process this message given current resource constraints"""
        # Check if system is degraded
        if self.resource_manager.is_degraded():
            degradation_level = self.resource_manager.get_degradation_level()
            
            # In critical mode, only process messages from certain channels or users
            if degradation_level == DegradationLevel.CRITICAL:
                # Could implement priority user logic here
                if len(self.active_conversations) >= self.emergency_max_concurrent:
                    # Send degradation notification
                    await self._send_degradation_notification(message)
                    return False
            
            # In severe mode, limit concurrent processing more strictly
            elif degradation_level == DegradationLevel.SEVERE:
                if len(self.active_conversations) >= self.emergency_max_concurrent:
                    await self._send_degradation_notification(message)
                    return False
            
            # In moderate/light mode, apply normal limits
            elif len(self.active_conversations) >= self.degraded_max_concurrent:
                await self._send_degradation_notification(message)
                return False
        
        # Normal operation - check standard limits
        elif len(self.active_conversations) >= self.max_concurrent_conversations:
            embed = self.embed_builder.create_info_embed(
                "High Load",
                "I'm currently processing several conversations. Please wait a moment and try again."
            )
            await message.reply(embed=embed)
            return False
        
        return True
    
    async def _send_degradation_notification(self, message: discord.Message):
        """Send user notification about system degradation"""
        try:
            notification_message = self.resource_manager.get_user_notification_message()
            if notification_message:
                embed = self.embed_builder.create_info_embed(
                    "System Status",
                    notification_message
                )
                await message.reply(embed=embed)
        except Exception as e:
            logging.error(f"Error sending degradation notification: {e}")
    
    def _should_use_basic_mode(self) -> bool:
        """Check if we should use basic response mode due to resource constraints"""
        if not self.resource_manager:
            return False
        
        degradation_level = self.resource_manager.get_degradation_level()
        return degradation_level in [DegradationLevel.SEVERE, DegradationLevel.CRITICAL]
    
    def _get_degraded_context_limit(self) -> int:
        """Get context limit based on current degradation level"""
        if not self.resource_manager:
            return 4000  # Default
        
        degradation_level = self.resource_manager.get_degradation_level()
        
        if degradation_level == DegradationLevel.CRITICAL:
            return 500   # Very limited context
        elif degradation_level == DegradationLevel.SEVERE:
            return 1000  # Limited context
        elif degradation_level == DegradationLevel.MODERATE:
            return 2000  # Reduced context
        elif degradation_level == DegradationLevel.LIGHT:
            return 3000  # Slightly reduced context
        else:
            return 4000  # Normal context
    
    async def _send_response_with_retry(self, message: discord.Message, formatted_response: Dict[str, Any]) -> None:
        """Send response with retry logic for Discord API errors"""
        for attempt in range(self.max_retries + 1):
            try:
                await self._send_response(message, formatted_response)
                return  # Success
            except discord.HTTPException as e:
                if attempt == self.max_retries:
                    # Final attempt failed, try simple text message
                    try:
                        await message.reply("I'm having trouble sending my response. Please try again.")
                    except:
                        pass  # Give up gracefully
                    return
                
                # Wait before retry, with exponential backoff
                await asyncio.sleep(self.retry_delay * (2 ** attempt))
            except Exception as e:
                # Non-Discord errors shouldn't be retried
                logging.error(f"Non-retryable error sending response: {e}")
                return
    
    async def _handle_degradation_change(self, old_level: DegradationLevel, new_level: DegradationLevel, reasons: list):
        """Handle resource degradation level changes"""
        try:
            logging.info(f"Handling degradation change from {old_level.value} to {new_level.value}")
            
            # Adjust concurrent processing limits
            if new_level == DegradationLevel.NORMAL:
                self.max_concurrent_conversations = 5
            elif new_level in [DegradationLevel.LIGHT, DegradationLevel.MODERATE]:
                self.max_concurrent_conversations = self.degraded_max_concurrent
            else:  # SEVERE or CRITICAL
                self.max_concurrent_conversations = self.emergency_max_concurrent
            
            # Cancel excess conversations if needed
            if len(self.active_conversations) > self.max_concurrent_conversations:
                await self._cancel_excess_conversations()
            
            # Update system health tracking
            self.system_health["resource_degradation"] = new_level.value
            self.system_health["degradation_reasons"] = reasons
            
        except Exception as e:
            logging.error(f"Error handling degradation change: {e}")
    
    async def _cancel_excess_conversations(self):
        """Cancel excess conversations when under resource pressure"""
        try:
            excess_count = len(self.active_conversations) - self.max_concurrent_conversations
            if excess_count <= 0:
                return
            
            # Sort conversations by start time (oldest first)
            conversations = list(self.active_conversations.items())
            conversations.sort(key=lambda x: x[1].get_name() if hasattr(x[1], 'get_name') else '')
            
            # Cancel the oldest conversations
            for i in range(excess_count):
                user_id, task = conversations[i]
                if not task.done():
                    task.cancel()
                    logging.info(f"Cancelled conversation for user {user_id} due to resource pressure")
            
        except Exception as e:
            logging.error(f"Error cancelling excess conversations: {e}")
    
    async def _check_resource_constraints(self, message: discord.Message) -> bool:
        """Check if we can process this message given current resource constraints"""
        # Check if system is degraded
        if self.resource_manager.is_degraded():
            degradation_level = self.resource_manager.get_degradation_level()
            
            # In critical mode, only process messages from certain channels or users
            if degradation_level == DegradationLevel.CRITICAL:
                # Could implement priority user logic here
                if len(self.active_conversations) >= self.emergency_max_concurrent:
                    # Send degradation notification
                    await self._send_degradation_notification(message)
                    return False
            
            # In severe mode, limit concurrent processing more strictly
            elif degradation_level == DegradationLevel.SEVERE:
                if len(self.active_conversations) >= self.emergency_max_concurrent:
                    await self._send_degradation_notification(message)
                    return False
            
            # In moderate/light mode, apply normal limits
            elif len(self.active_conversations) >= self.degraded_max_concurrent:
                await self._send_degradation_notification(message)
                return False
        
        # Normal operation - check standard limits
        elif len(self.active_conversations) >= self.max_concurrent_conversations:
            embed = self.embed_builder.create_info_embed(
                "High Load",
                "I'm currently processing several conversations. Please wait a moment and try again."
            )
            await message.reply(embed=embed)
            return False
        
        return True
    
    async def _send_degradation_notification(self, message: discord.Message):
        """Send user notification about system degradation"""
        try:
            notification_message = self.resource_manager.get_user_notification_message()
            if notification_message:
                embed = self.embed_builder.create_info_embed(
                    "System Status",
                    notification_message
                )
                await message.reply(embed=embed)
        except Exception as e:
            logging.error(f"Error sending degradation notification: {e}")