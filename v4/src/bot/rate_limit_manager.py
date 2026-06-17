"""
V4 Rate Limit Manager
Integration layer for rate limiting with existing bot components
Provides user-friendly responses and monitoring
"""

import asyncio
import logging
from typing import Dict, Any, Optional, Callable
import discord
from datetime import datetime, timedelta

from .rate_limiter import SystemRateLimiter, LimitType, AbuseType
from .embed_builder import EmbedBuilder


class RateLimitManager:
    """
    High-level rate limiting manager that integrates with Discord bot
    Provides user-friendly responses and monitoring capabilities
    """
    
    def __init__(self, embed_builder: EmbedBuilder):
        self.system_limiter = SystemRateLimiter()
        self.embed_builder = embed_builder
        
        # User notification settings
        self.notify_on_limit = True
        self.notification_cooldown = 300  # 5 minutes between notifications per user
        self.last_notifications = {}  # user_id -> timestamp
        
        # Graceful degradation responses
        self.degradation_responses = {
            0: None,  # No degradation
            1: "I'm experiencing high load. Responses may be slower than usual.",
            2: "System is under heavy load. Some features may be temporarily limited.",
            3: "System is at capacity. Please try again in a few minutes."
        }
        
        # Monitoring
        self.monitoring_enabled = True
        self.alert_thresholds = {
            "abuse_rate": 0.1,  # 10% of requests flagged as abuse
            "block_rate": 0.05,  # 5% of requests blocked
            "system_load": 0.8   # 80% system capacity
        }
        
    async def check_message_rate_limit(
        self,
        user_id: int,
        message_content: str,
        channel: discord.TextChannel
    ) -> bool:
        """
        Check rate limit for user messages
        Returns True if message should be processed, False if rate limited
        """
        is_allowed, reason = await self.system_limiter.check_rate_limit(
            user_id=user_id,
            limit_type=LimitType.USER_MESSAGE,
            content=message_content,
            metadata={
                "channel_id": channel.id,
                "guild_id": channel.guild.id if channel.guild else None,
                "message_length": len(message_content)
            }
        )
        
        if not is_allowed:
            await self._handle_rate_limit_exceeded(user_id, channel, reason, "message")
            return False
        
        return True
    
    async def check_interaction_rate_limit(
        self,
        user_id: int,
        interaction_type: str,
        channel: discord.TextChannel
    ) -> bool:
        """
        Check rate limit for user interactions (reactions, commands, etc.)
        """
        is_allowed, reason = await self.system_limiter.check_rate_limit(
            user_id=user_id,
            limit_type=LimitType.USER_INTERACTION,
            metadata={
                "interaction_type": interaction_type,
                "channel_id": channel.id,
                "guild_id": channel.guild.id if channel.guild else None
            }
        )
        
        if not is_allowed:
            await self._handle_rate_limit_exceeded(user_id, channel, reason, "interaction")
            return False
        
        return True
    
    async def check_ai_processing_rate_limit(
        self,
        user_id: int,
        request_complexity: str = "normal"
    ) -> bool:
        """
        Check rate limit for AI processing requests
        """
        is_allowed, reason = await self.system_limiter.check_rate_limit(
            user_id=user_id,
            limit_type=LimitType.AI_PROCESSING,
            metadata={
                "complexity": request_complexity,
                "timestamp": datetime.utcnow().isoformat()
            }
        )
        
        return is_allowed
    
    async def queue_discord_api_call(
        self,
        api_call: Callable,
        *args,
        channel_id: Optional[int] = None,
        guild_id: Optional[int] = None,
        priority: int = 0,
        max_wait_time: float = 30.0,
        **kwargs
    ) -> Any:
        """
        Queue Discord API call with rate limiting and retry logic
        """
        try:
            return await self.system_limiter.queue_discord_request(
                api_call,
                *args,
                channel_id=channel_id,
                guild_id=guild_id,
                priority=priority,
                max_wait_time=max_wait_time,
                **kwargs
            )
        except Exception as e:
            logging.error(f"Discord API call failed: {e}")
            raise
    
    async def _handle_rate_limit_exceeded(
        self,
        user_id: int,
        channel: discord.TextChannel,
        reason: str,
        request_type: str
    ):
        """Handle rate limit exceeded with user-friendly response"""
        # Check if we should notify the user
        if not self._should_notify_user(user_id):
            return
        
        # Get user status for personalized message
        user_status = self.system_limiter.get_user_status(user_id)
        
        # Create appropriate response based on reason
        if "abuse" in reason.lower():
            embed = self._create_abuse_warning_embed(user_status, reason)
        elif "system" in reason.lower():
            embed = self._create_system_load_embed()
        else:
            embed = self._create_rate_limit_embed(user_status, reason, request_type)
        
        try:
            # Send notification with rate limiting
            await self.queue_discord_api_call(
                channel.send,
                embed=embed,
                channel_id=channel.id,
                guild_id=channel.guild.id if channel.guild else None,
                priority=1  # Lower priority for notifications
            )
            
            # Record notification
            self.last_notifications[user_id] = datetime.utcnow().timestamp()
            
        except Exception as e:
            logging.error(f"Failed to send rate limit notification: {e}")
    
    def _should_notify_user(self, user_id: int) -> bool:
        """Check if user should be notified about rate limiting"""
        if not self.notify_on_limit:
            return False
        
        last_notification = self.last_notifications.get(user_id, 0)
        now = datetime.utcnow().timestamp()
        
        return now - last_notification > self.notification_cooldown
    
    def _create_rate_limit_embed(
        self,
        user_status: Dict[str, Any],
        reason: str,
        request_type: str
    ) -> discord.Embed:
        """Create user-friendly rate limit embed"""
        embed = self.embed_builder.create_warning_embed(
            "Rate Limit Reached",
            f"You're sending {request_type}s a bit too quickly! Please slow down a little."
        )
        
        embed.add_field(
            name="⏱️ What happened?",
            value="Our system has rate limits to ensure fair usage for everyone.",
            inline=False
        )
        
        embed.add_field(
            name="🔄 What can you do?",
            value="• Wait a moment before trying again\n"
                  "• Combine multiple questions into one message\n"
                  "• Use threads for longer discussions",
            inline=False
        )
        
        # Add degradation notice if active
        degradation_level = self.system_limiter.get_degradation_level()
        if degradation_level > 0:
            degradation_msg = self.degradation_responses.get(degradation_level)
            if degradation_msg:
                embed.add_field(
                    name="🚦 System Status",
                    value=degradation_msg,
                    inline=False
                )
        
        embed.set_footer(text="Rate limits help keep the bot responsive for everyone!")
        return embed
    
    def _create_abuse_warning_embed(
        self,
        user_status: Dict[str, Any],
        reason: str
    ) -> discord.Embed:
        """Create abuse warning embed"""
        if user_status.get("is_blocked"):
            embed = self.embed_builder.create_error_embed(
                "Account Temporarily Restricted",
                "Your account has been temporarily restricted due to unusual activity patterns."
            )
            
            embed.add_field(
                name="🚫 What happened?",
                value="Our abuse detection system flagged your account for suspicious activity.",
                inline=False
            )
            
            embed.add_field(
                name="⏰ How long?",
                value="Restrictions are typically lifted automatically within 1-24 hours.",
                inline=False
            )
            
        else:
            embed = self.embed_builder.create_warning_embed(
                "Unusual Activity Detected",
                "We've noticed some unusual activity patterns from your account."
            )
            
            embed.add_field(
                name="⚠️ What happened?",
                value="Your usage pattern triggered our abuse detection system.",
                inline=False
            )
            
            embed.add_field(
                name="🔄 What can you do?",
                value="• Slow down your requests\n"
                      "• Avoid sending duplicate messages\n"
                      "• Use the bot normally and this warning will clear",
                inline=False
            )
        
        embed.add_field(
            name="❓ Need help?",
            value="If you believe this is an error, please contact the server administrators.",
            inline=False
        )
        
        return embed
    
    def _create_system_load_embed(self) -> discord.Embed:
        """Create system load embed"""
        embed = self.embed_builder.create_warning_embed(
            "System Under High Load",
            "I'm currently experiencing high demand and need to limit requests."
        )
        
        embed.add_field(
            name="🚦 Current Status",
            value="The system is temporarily operating at reduced capacity to maintain stability.",
            inline=False
        )
        
        embed.add_field(
            name="⏱️ What can you do?",
            value="• Please try again in a few minutes\n"
                  "• Consider using simpler requests\n"
                  "• Check back later when load decreases",
            inline=False
        )
        
        degradation_level = self.system_limiter.get_degradation_level()
        if degradation_level > 0:
            degradation_msg = self.degradation_responses.get(degradation_level)
            if degradation_msg:
                embed.add_field(
                    name="   System Message",
                    value=degradation_msg,
                    inline=False
                )
        
        embed.set_footer(text="Thank you for your patience!")
        return embed
    
    async def get_system_health_embed(self) -> discord.Embed:
        """Create system health status embed"""
        stats = self.system_limiter.get_system_stats()
        
        # Determine overall health
        system_load = stats.get("system_load", 0)
        if system_load < 0.5:
            health_status = "🟢 Excellent"
            health_color = self.embed_builder.colors["success"]
        elif system_load < 0.7:
            health_status = "🟡 Good"
            health_color = self.embed_builder.colors["warning"]
        elif system_load < 0.9:
            health_status = "🟠 Moderate Load"
            health_color = self.embed_builder.colors["warning"]
        else:
            health_status = "🔴 High Load"
            health_color = self.embed_builder.colors["error"]
        
        embed = discord.Embed(
            title="🏥 System Health Status",
            description=f"Overall Status: {health_status}",
            color=health_color
        )
        
        # System metrics
        embed.add_field(
            name="   Load Metrics",
            value=f"System Load: {system_load:.1%}\n"
                  f"Queue Size: {stats.get('queue_size', 0)}\n"
                  f"Active Users: {stats.get('active_users', 0)}",
            inline=True
        )
        
        # Request statistics
        total_requests = stats.get("requests_processed", 0) + stats.get("requests_blocked", 0)
        block_rate = stats.get("requests_blocked", 0) / max(total_requests, 1)
        
        embed.add_field(
            name="🔢 Request Stats",
            value=f"Processed: {stats.get('requests_processed', 0):,}\n"
                  f"Blocked: {stats.get('requests_blocked', 0):,}\n"
                  f"Block Rate: {block_rate:.1%}",
            inline=True
        )
        
        # Abuse detection
        abuse_stats = stats.get("abuse_stats", {})
        embed.add_field(
            name="🛡️ Security",
            value=f"Blocked Users: {abuse_stats.get('blocked_users', 0)}\n"
                  f"Warned Users: {abuse_stats.get('warned_users', 0)}\n"
                  f"Patterns Detected: {abuse_stats.get('total_patterns', 0)}",
            inline=True
        )
        
        # Degradation status
        if stats.get("degradation_active"):
            embed.add_field(
                name="⚠️ Degradation Active",
                value=f"Level: {stats.get('degradation_level', 0)}\n"
                      f"Events: {stats.get('degradation_events', 0)}",
                inline=False
            )
        
        embed.set_footer(text=f"Last updated: {datetime.utcnow().strftime('%Y-%m-%d %H:%M:%S')} UTC")
        return embed
    
    async def monitor_system_health(self):
        """Monitor system health and generate alerts if needed"""
        if not self.monitoring_enabled:
            return
        
        stats = self.system_limiter.get_system_stats()
        alerts = []
        
        # Check abuse rate
        total_requests = stats.get("requests_processed", 0) + stats.get("requests_blocked", 0)
        if total_requests > 0:
            abuse_rate = stats.get("abuse_detected", 0) / total_requests
            if abuse_rate > self.alert_thresholds["abuse_rate"]:
                alerts.append(f"High abuse rate: {abuse_rate:.1%}")
        
        # Check block rate
        if total_requests > 0:
            block_rate = stats.get("requests_blocked", 0) / total_requests
            if block_rate > self.alert_thresholds["block_rate"]:
                alerts.append(f"High block rate: {block_rate:.1%}")
        
        # Check system load
        system_load = stats.get("system_load", 0)
        if system_load > self.alert_thresholds["system_load"]:
            alerts.append(f"High system load: {system_load:.1%}")
        
        # Log alerts
        if alerts:
            logging.warning(f"System health alerts: {'; '.join(alerts)}")
    
    def get_user_rate_limit_info(self, user_id: int) -> Dict[str, Any]:
        """Get user's current rate limit status"""
        user_status = self.system_limiter.get_user_status(user_id)
        
        return {
            "is_blocked": user_status.get("is_blocked", False),
            "is_warned": user_status.get("is_warned", False),
            "request_counts": user_status.get("request_counts", {}),
            "last_notification": self.last_notifications.get(user_id),
            "can_be_notified": self._should_notify_user(user_id)
        }
    
    async def reset_user_limits(self, user_id: int, admin_user_id: int) -> bool:
        """Reset rate limits for a user (admin function)"""
        try:
            # Remove from blocked/warned users
            self.system_limiter.abuse_detector.blocked_users.discard(user_id)
            self.system_limiter.abuse_detector.warned_users.discard(user_id)
            
            # Clear user request history
            if user_id in self.system_limiter.user_requests:
                del self.system_limiter.user_requests[user_id]
            
            # Clear notification history
            if user_id in self.last_notifications:
                del self.last_notifications[user_id]
            
            logging.info(f"Rate limits reset for user {user_id} by admin {admin_user_id}")
            return True
            
        except Exception as e:
            logging.error(f"Failed to reset rate limits for user {user_id}: {e}")
            return False
    
    def enable_monitoring(self):
        """Enable system health monitoring"""
        self.monitoring_enabled = True
    
    def disable_monitoring(self):
        """Disable system health monitoring"""
        self.monitoring_enabled = False
    
    def get_manager_stats(self) -> Dict[str, Any]:
        """Get rate limit manager statistics"""
        return {
            "system_stats": self.system_limiter.get_system_stats(),
            "notification_settings": {
                "notify_on_limit": self.notify_on_limit,
                "notification_cooldown": self.notification_cooldown,
                "users_with_notifications": len(self.last_notifications)
            },
            "monitoring_enabled": self.monitoring_enabled,
            "alert_thresholds": self.alert_thresholds
        }