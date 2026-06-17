"""
V4 Error Handler
Comprehensive error handling system for all components
Provides graceful error handling, user-friendly messages, and detailed logging
"""

import logging
import traceback
import asyncio
import discord
from typing import Dict, Any, Optional, Callable, Union, List
from datetime import datetime, timedelta
from enum import Enum
from dataclasses import dataclass
import json
import os


class ErrorSeverity(Enum):
    """Error severity levels"""
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    CRITICAL = "critical"


class ErrorCategory(Enum):
    """Error categories for classification"""
    DISCORD_API = "discord_api"
    AI_MODEL = "ai_model"
    KNOWLEDGE_RETRIEVAL = "knowledge_retrieval"
    MEMORY_SYSTEM = "memory_system"
    RATE_LIMITING = "rate_limiting"
    NETWORK = "network"
    DATABASE = "database"
    CONFIGURATION = "configuration"
    VALIDATION = "validation"
    UNKNOWN = "unknown"


@dataclass
class ErrorInfo:
    """Structured error information"""
    error_id: str
    category: ErrorCategory
    severity: ErrorSeverity
    message: str
    user_message: str
    timestamp: datetime
    component: str
    context: Dict[str, Any]
    traceback_info: Optional[str] = None
    recovery_attempted: bool = False
    recovery_successful: bool = False


class ErrorHandler:
    """
    Centralized error handling system
    Provides graceful error handling, logging, and user communication
    """
    
    def __init__(self, embed_builder=None, log_dir: str = "logs"):
        self.embed_builder = embed_builder
        self.log_dir = log_dir
        
        # Error tracking
        self.error_counts = {}  # category -> count
        self.recent_errors = []  # Recent errors for analysis
        self.error_patterns = {}  # Pattern detection
        
        # Recovery strategies
        self.recovery_strategies = {}
        self.fallback_responses = {}
        
        # Configuration
        self.max_recent_errors = 100
        self.error_log_file = os.path.join(log_dir, "errors.json")
        
        # Ensure log directory exists
        os.makedirs(log_dir, exist_ok=True)
        
        # Setup logging
        self._setup_logging()
        
        # Initialize recovery strategies
        self._setup_recovery_strategies()
        
        # Initialize fallback responses
        self._setup_fallback_responses()
    
    def _setup_logging(self):
        """Setup error logging configuration"""
        # Create error-specific logger
        self.error_logger = logging.getLogger('aviation_bot.errors')
        self.error_logger.setLevel(logging.ERROR)
        
        # Clear any existing handlers
        for handler in self.error_logger.handlers[:]:
            handler.close()
            self.error_logger.removeHandler(handler)
        
        # File handler for error logs
        error_handler = logging.FileHandler(
            os.path.join(self.log_dir, "error_details.log")
        )
        error_handler.setLevel(logging.ERROR)
        
        # Formatter for detailed error logs
        formatter = logging.Formatter(
            '%(asctime)s - %(name)s - %(levelname)s - %(message)s'
        )
        error_handler.setFormatter(formatter)
        
        self.error_logger.addHandler(error_handler)
        self.file_handler = error_handler  # Keep reference for cleanup
    
    def _setup_recovery_strategies(self):
        """Setup automatic recovery strategies for different error types"""
        self.recovery_strategies = {
            ErrorCategory.DISCORD_API: self._recover_discord_api_error,
            ErrorCategory.AI_MODEL: self._recover_ai_model_error,
            ErrorCategory.KNOWLEDGE_RETRIEVAL: self._recover_knowledge_error,
            ErrorCategory.MEMORY_SYSTEM: self._recover_memory_error,
            ErrorCategory.NETWORK: self._recover_network_error,
            ErrorCategory.DATABASE: self._recover_database_error,
            ErrorCategory.RATE_LIMITING: self._recover_rate_limit_error
        }
    
    def _setup_fallback_responses(self):
        """Setup fallback responses for different error scenarios"""
        self.fallback_responses = {
            ErrorCategory.DISCORD_API: {
                "title": "Discord Connection Issue",
                "message": "I'm having trouble communicating with Discord. Please try again in a moment.",
                "suggestions": ["Wait a moment and try again", "Check your internet connection"]
            },
            ErrorCategory.AI_MODEL: {
                "title": "AI Processing Error",
                "message": "I'm having trouble processing your request right now. Let me try a different approach.",
                "suggestions": ["Try rephrasing your question", "Ask about a specific aviation topic"]
            },
            ErrorCategory.KNOWLEDGE_RETRIEVAL: {
                "title": "Knowledge System Unavailable",
                "message": "I can't access my aviation knowledge base right now, but I can still help with general questions.",
                "suggestions": ["Try asking a general aviation question", "Check back in a few minutes"]
            },
            ErrorCategory.MEMORY_SYSTEM: {
                "title": "Memory System Issue",
                "message": "I'm having trouble accessing your conversation history, but I can still help you.",
                "suggestions": ["Continue with your question", "I may not remember our previous conversation"]
            },
            ErrorCategory.NETWORK: {
                "title": "Network Connection Issue",
                "message": "I'm having trouble connecting to external services. Some features may be limited.",
                "suggestions": ["Basic aviation questions still work", "Real-time data may be unavailable"]
            },
            ErrorCategory.RATE_LIMITING: {
                "title": "Too Many Requests",
                "message": "You're sending messages too quickly. Please wait a moment before trying again.",
                "suggestions": ["Wait a few seconds", "I need time to process each request properly"]
            }
        }
    
    async def handle_error(
        self,
        error: Exception,
        context: Dict[str, Any],
        component: str = "unknown",
        user_message: Optional[discord.Message] = None,
        severity: ErrorSeverity = ErrorSeverity.MEDIUM
    ) -> Optional[ErrorInfo]:
        """
        Main error handling entry point
        Handles error logging, recovery attempts, and user communication
        """
        try:
            # Generate unique error ID
            error_id = self._generate_error_id()
            
            # Classify the error
            category = self._classify_error(error)
            
            # Create error info
            error_info = ErrorInfo(
                error_id=error_id,
                category=category,
                severity=severity,
                message=str(error),
                user_message=self._generate_user_message(category, error),
                timestamp=datetime.utcnow(),
                component=component,
                context=context,
                traceback_info=traceback.format_exc()
            )
            
            # Log the error
            await self._log_error(error_info)
            
            # Track error statistics
            self._track_error(error_info)
            
            # Attempt recovery if strategy exists
            if category in self.recovery_strategies:
                try:
                    error_info.recovery_attempted = True
                    recovery_result = await self.recovery_strategies[category](
                        error, context, error_info
                    )
                    error_info.recovery_successful = recovery_result
                except Exception as recovery_error:
                    logging.error(f"Recovery failed for {error_id}: {recovery_error}")
            
            # Send user-friendly error message if Discord message provided
            if user_message:
                await self._send_error_response(user_message, error_info)
            
            return error_info
            
        except Exception as handler_error:
            # Error in error handler - log to standard logger
            logging.critical(f"Error handler failed: {handler_error}")
            return None
    
    def _generate_error_id(self) -> str:
        """Generate unique error ID for tracking"""
        timestamp = datetime.utcnow().strftime("%Y%m%d_%H%M%S")
        import uuid
        short_uuid = str(uuid.uuid4())[:8]
        return f"ERR_{timestamp}_{short_uuid}"
    
    def _classify_error(self, error: Exception) -> ErrorCategory:
        """Classify error into appropriate category"""
        error_type = type(error).__name__
        error_message = str(error).lower()
        
        # Discord API errors
        if isinstance(error, discord.HTTPException) or "discord" in error_message:
            return ErrorCategory.DISCORD_API
        
        # Network errors
        if any(keyword in error_message for keyword in ["connection", "timeout", "network", "unreachable"]):
            return ErrorCategory.NETWORK
        
        # Database errors
        if any(keyword in error_message for keyword in ["database", "sqlite", "sql"]):
            return ErrorCategory.DATABASE
        
        # AI model errors
        if any(keyword in error_message for keyword in ["model", "generation", "inference", "tokenizer"]):
            return ErrorCategory.AI_MODEL
        
        # Knowledge retrieval errors
        if any(keyword in error_message for keyword in ["knowledge", "rag", "embedding", "search"]):
            return ErrorCategory.KNOWLEDGE_RETRIEVAL
        
        # Memory system errors
        if any(keyword in error_message for keyword in ["memory", "profile", "conversation"]):
            return ErrorCategory.MEMORY_SYSTEM
        
        # Rate limiting errors
        if any(keyword in error_message for keyword in ["rate", "limit", "throttle", "quota"]):
            return ErrorCategory.RATE_LIMITING
        
        # Configuration errors
        if any(keyword in error_message for keyword in ["config", "environment", "setting"]):
            return ErrorCategory.CONFIGURATION
        
        # Validation errors
        if any(keyword in error_message for keyword in ["validation", "invalid", "format"]):
            return ErrorCategory.VALIDATION
        
        return ErrorCategory.UNKNOWN
    
    def _generate_user_message(self, category: ErrorCategory, error: Exception) -> str:
        """Generate user-friendly error message"""
        fallback = self.fallback_responses.get(category)
        if fallback:
            return fallback["message"]
        
        # Generic fallback
        return "I encountered an unexpected issue. Please try again or contact support if the problem persists."
    
    async def _log_error(self, error_info: ErrorInfo):
        """Log error information"""
        # Log to standard logger
        self.error_logger.error(
            f"Error {error_info.error_id} in {error_info.component}: "
            f"{error_info.message} (Category: {error_info.category.value}, "
            f"Severity: {error_info.severity.value})"
        )
        
        # Log detailed information to JSON file
        try:
            error_data = {
                "error_id": error_info.error_id,
                "timestamp": error_info.timestamp.isoformat(),
                "category": error_info.category.value,
                "severity": error_info.severity.value,
                "component": error_info.component,
                "message": error_info.message,
                "context": error_info.context,
                "traceback": error_info.traceback_info,
                "recovery_attempted": error_info.recovery_attempted,
                "recovery_successful": error_info.recovery_successful
            }
            
            # Append to error log file
            if os.path.exists(self.error_log_file):
                with open(self.error_log_file, 'r') as f:
                    errors = json.load(f)
            else:
                errors = []
            
            errors.append(error_data)
            
            # Keep only recent errors to prevent file from growing too large
            if len(errors) > self.max_recent_errors:
                errors = errors[-self.max_recent_errors:]
            
            with open(self.error_log_file, 'w') as f:
                json.dump(errors, f, indent=2)
                
        except Exception as log_error:
            logging.error(f"Failed to log error to JSON file: {log_error}")
    
    def _track_error(self, error_info: ErrorInfo):
        """Track error statistics and patterns"""
        # Count by category
        category_key = error_info.category.value
        self.error_counts[category_key] = self.error_counts.get(category_key, 0) + 1
        
        # Add to recent errors
        self.recent_errors.append(error_info)
        if len(self.recent_errors) > self.max_recent_errors:
            self.recent_errors.pop(0)
        
        # Pattern detection (simple implementation)
        error_pattern = f"{error_info.component}:{error_info.category.value}"
        if error_pattern not in self.error_patterns:
            self.error_patterns[error_pattern] = []
        
        self.error_patterns[error_pattern].append(error_info.timestamp)
        
        # Keep only recent patterns
        cutoff_time = datetime.utcnow() - timedelta(hours=1)
        self.error_patterns[error_pattern] = [
            ts for ts in self.error_patterns[error_pattern] if ts > cutoff_time
        ]
    
    async def _send_error_response(self, message: discord.Message, error_info: ErrorInfo):
        """Send user-friendly error response"""
        try:
            if self.embed_builder:
                # Create error embed
                fallback = self.fallback_responses.get(error_info.category)
                if fallback:
                    embed = self.embed_builder.create_error_embed(
                        fallback["title"],
                        fallback["message"]
                    )
                    
                    # Add suggestions if available
                    if "suggestions" in fallback:
                        suggestions_text = "\n".join([f"• {s}" for s in fallback["suggestions"]])
                        embed.add_field(name="Suggestions", value=suggestions_text, inline=False)
                    
                    # Add error ID for support
                    embed.add_field(
                        name="Error ID", 
                        value=f"`{error_info.error_id}`", 
                        inline=True
                    )
                else:
                    embed = self.embed_builder.create_error_embed(
                        "Unexpected Error",
                        error_info.user_message
                    )
                
                await message.reply(embed=embed)
            else:
                # Fallback to plain text
                await message.reply(f"  {error_info.user_message}\n\nError ID: `{error_info.error_id}`")
                
        except Exception as response_error:
            logging.error(f"Failed to send error response: {response_error}")
            # Last resort - try simple text message
            try:
                await message.reply("  I encountered an error and couldn't send a proper response.")
            except:
                pass  # Give up gracefully
    
    # Recovery strategy implementations
    
    async def _recover_discord_api_error(
        self, 
        error: Exception, 
        context: Dict[str, Any], 
        error_info: ErrorInfo
    ) -> bool:
        """Attempt recovery from Discord API errors"""
        if isinstance(error, discord.HTTPException):
            if error.status == 429:  # Rate limited
                # Wait and retry logic would go here
                await asyncio.sleep(1)
                return True
            elif error.status >= 500:  # Server error
                # Discord server issue, wait briefly
                await asyncio.sleep(2)
                return True
        
        return False
    
    async def _recover_ai_model_error(
        self, 
        error: Exception, 
        context: Dict[str, Any], 
        error_info: ErrorInfo
    ) -> bool:
        """Attempt recovery from AI model errors"""
        # Could implement model reload, fallback to cached responses, etc.
        return False
    
    async def _recover_knowledge_error(
        self, 
        error: Exception, 
        context: Dict[str, Any], 
        error_info: ErrorInfo
    ) -> bool:
        """Attempt recovery from knowledge retrieval errors"""
        # Could implement fallback to cached knowledge, simplified search, etc.
        return False
    
    async def _recover_memory_error(
        self, 
        error: Exception, 
        context: Dict[str, Any], 
        error_info: ErrorInfo
    ) -> bool:
        """Attempt recovery from memory system errors"""
        # Could implement temporary memory, profile reconstruction, etc.
        return False
    
    async def _recover_network_error(
        self, 
        error: Exception, 
        context: Dict[str, Any], 
        error_info: ErrorInfo
    ) -> bool:
        """Attempt recovery from network errors"""
        # Could implement retry with exponential backoff
        return False
    
    async def _recover_database_error(
        self, 
        error: Exception, 
        context: Dict[str, Any], 
        error_info: ErrorInfo
    ) -> bool:
        """Attempt recovery from database errors"""
        # Could implement database reconnection, backup database, etc.
        return False
    
    async def _recover_rate_limit_error(
        self, 
        error: Exception, 
        context: Dict[str, Any], 
        error_info: ErrorInfo
    ) -> bool:
        """Attempt recovery from rate limiting errors"""
        # Wait for rate limit to reset
        await asyncio.sleep(5)
        return True
    
    def get_error_statistics(self) -> Dict[str, Any]:
        """Get error statistics for monitoring"""
        recent_count = len([e for e in self.recent_errors 
                          if e.timestamp > datetime.utcnow() - timedelta(hours=1)])
        
        return {
            "total_errors_by_category": self.error_counts,
            "recent_errors_count": recent_count,
            "error_patterns": {
                pattern: len(timestamps) 
                for pattern, timestamps in self.error_patterns.items()
            },
            "recovery_success_rate": self._calculate_recovery_success_rate(),
            "most_common_category": max(self.error_counts.items(), key=lambda x: x[1])[0] if self.error_counts else None
        }
    
    def _calculate_recovery_success_rate(self) -> float:
        """Calculate recovery success rate"""
        recovery_attempts = [e for e in self.recent_errors if e.recovery_attempted]
        if not recovery_attempts:
            return 0.0
        
        successful_recoveries = [e for e in recovery_attempts if e.recovery_successful]
        return len(successful_recoveries) / len(recovery_attempts)
    
    def get_recent_errors(self, limit: int = 10) -> List[Dict[str, Any]]:
        """Get recent errors for debugging"""
        recent = self.recent_errors[-limit:] if self.recent_errors else []
        return [
            {
                "error_id": e.error_id,
                "timestamp": e.timestamp.isoformat(),
                "category": e.category.value,
                "severity": e.severity.value,
                "component": e.component,
                "message": e.message,
                "recovery_attempted": e.recovery_attempted,
                "recovery_successful": e.recovery_successful
            }
            for e in recent
        ]
    
    async def clear_error_history(self):
        """Clear error history (for maintenance)"""
        self.recent_errors.clear()
        self.error_counts.clear()
        self.error_patterns.clear()
        
        # Clear error log file
        try:
            if os.path.exists(self.error_log_file):
                os.remove(self.error_log_file)
        except Exception as e:
            logging.error(f"Failed to clear error log file: {e}")
    
    def cleanup(self):
        """Cleanup resources"""
        try:
            if hasattr(self, 'file_handler'):
                self.file_handler.close()
                self.error_logger.removeHandler(self.file_handler)
        except Exception as e:
            logging.error(f"Error during cleanup: {e}")


# Decorator for automatic error handling
def handle_errors(
    component: str,
    severity: ErrorSeverity = ErrorSeverity.MEDIUM,
    error_handler: Optional[ErrorHandler] = None
):
    """
    Decorator for automatic error handling in methods
    """
    def decorator(func: Callable):
        async def wrapper(*args, **kwargs):
            try:
                return await func(*args, **kwargs)
            except Exception as e:
                if error_handler:
                    context = {
                        "function": func.__name__,
                        "args": str(args)[:200],  # Limit context size
                        "kwargs": str(kwargs)[:200]
                    }
                    await error_handler.handle_error(
                        e, context, component, severity=severity
                    )
                else:
                    logging.error(f"Error in {component}.{func.__name__}: {e}")
                
                # Re-raise for caller to handle
                raise
        
        return wrapper
    return decorator