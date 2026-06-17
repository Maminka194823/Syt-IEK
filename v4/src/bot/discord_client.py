"""
V4 Discord Bot - Main Client
Comprehensive Discord integration with full AI backend and all system components
"""

import discord
from discord.ext import commands
import asyncio
import logging
from typing import Optional, Dict, Any
import json
import os
from datetime import datetime

# Core AI and Knowledge Systems
from ..ai.model_loader import AIModelManager
from ..ai.ai_orchestrator import AIOrchestrator
from ..memory.user_profiles import UserProfileManager
from ..memory.conversation_memory import ConversationMemoryManager
from ..knowledge.rag_system import RAGSystem
from ..knowledge.knowledge_base import KnowledgeBase
from ..knowledge.aviation_data import AviationDataManager

# Bot Components
from .message_handler import MessageHandler
from .embed_builder import EmbedBuilder
from .interaction_handler import InteractionHandler
from .rate_limit_manager import RateLimitManager
from .error_handler import ErrorHandler, ErrorSeverity
from .performance_monitor import PerformanceMonitor
from .resource_manager import ResourceManager
from .startup_validator import StartupValidator
from .config_manager import BotConfiguration

# Security Components
from ..security.privacy_manager import PrivacyManager
from ..security.encryption_manager import EncryptionManager
from ..security.credential_manager import CredentialManager

class AviationGirlBot(commands.Bot):
    """
    Main Discord bot class for Aviation Girl V4
    Comprehensive AI-powered aviation assistant with full system integration
    """
    
    def __init__(self, config: Optional[BotConfiguration] = None):
        # Load configuration
        if config is None:
            from .config_manager import ConfigManager
            config_manager = ConfigManager()
            self.config = asyncio.run(config_manager.load_configuration())
        else:
            self.config = config
        
        # Discord intents for full functionality
        intents = discord.Intents.default()
        intents.message_content = True
        intents.reactions = True
        intents.guilds = True
        intents.members = True
        
        super().__init__(
            command_prefix=self.config.discord.command_prefix,
            intents=intents,
            help_command=None
        )
        
        # System Health and Monitoring
        self.performance_monitor = PerformanceMonitor()
        self.error_handler = ErrorHandler(log_dir="logs")
        self.resource_manager = ResourceManager()
        
        # Security Components
        self.encryption_manager = EncryptionManager()
        self.credential_manager = CredentialManager(self.encryption_manager)
        self.privacy_manager = PrivacyManager(["data", "logs", "keys"])
        
        # Core AI Systems
        self.ai_model = None
        self.ai_orchestrator = None
        
        # Knowledge and Memory Systems
        self.knowledge_base = None
        self.rag_system = None
        self.user_profiles = None
        self.conversation_memory = None
        self.aviation_data = None
        
        # Bot Interface Components
        self.message_handler = None
        self.embed_builder = EmbedBuilder()
        self.interaction_handler = None
        self.rate_limit_manager = None
        
        # System State
        self.is_ready = False
        self.startup_time = None
        self.startup_report = None
        self.system_health = {
            "overall_healthy": False,
            "components": {},
            "last_check": None
        }
        
        # Component initialization order (critical for dependencies)
        self.initialization_order = [
            "security_systems",
            "monitoring_systems", 
            "knowledge_systems",
            "ai_systems",
            "memory_systems",
            "interface_systems"
        ]
        
    async def setup_hook(self):
        """Initialize all systems when bot starts with comprehensive validation"""
        logging.info("Starting Aviation Girl V4 comprehensive initialization...")
        
        try:
            # Run startup validation first
            validator = StartupValidator(self.config)
            self.startup_report = await validator.validate_startup()
            
            if self.startup_report.overall_status.value == "failed":
                critical_failures = [
                    r for r in self.startup_report.validation_results 
                    if r.status.value == "failed" and validator._is_critical_check(r.name)
                ]
                if critical_failures:
                    error_msg = f"Critical startup validation failures: {[f.name for f in critical_failures]}"
                    logging.error(error_msg)
                    raise RuntimeError(error_msg)
            
            # Initialize systems in dependency order
            for system_group in self.initialization_order:
                await self._initialize_system_group(system_group)
            
            # Perform final system integration
            await self._integrate_all_systems()
            
            # Start background monitoring
            await self._start_background_tasks()
            
            logging.info("All systems initialized successfully")
            
        except Exception as e:
            await self.error_handler.handle_error(
                e, 
                {"phase": "startup", "config": str(self.config)}, 
                "discord_client",
                severity=ErrorSeverity.CRITICAL
            )
            raise
    
    async def _initialize_system_group(self, group_name: str):
        """Initialize a group of related systems"""
        logging.info(f"Initializing {group_name}...")
        
        try:
            if group_name == "security_systems":
                await self._init_security_systems()
            elif group_name == "monitoring_systems":
                await self._init_monitoring_systems()
            elif group_name == "knowledge_systems":
                await self._init_knowledge_systems()
            elif group_name == "ai_systems":
                await self._init_ai_systems()
            elif group_name == "memory_systems":
                await self._init_memory_systems()
            elif group_name == "interface_systems":
                await self._init_interface_systems()
            
            logging.info(f"  {group_name} initialized successfully")
            
        except Exception as e:
            logging.error(f"  Failed to initialize {group_name}: {e}")
            raise
    
    async def _init_security_systems(self):
        """Initialize security and privacy systems"""
        # Encryption manager is already initialized
        await self.encryption_manager.initialize()
        
        # Credential manager setup
        await self.credential_manager.initialize()
        
        # Privacy manager is ready
        logging.info("Security systems ready")
    
    async def _init_monitoring_systems(self):
        """Initialize monitoring and performance systems"""
        # Performance monitor is already initialized and running
        
        # Resource manager setup
        await self.resource_manager.initialize()
        
        # Error handler is ready
        logging.info("Monitoring systems ready")
    
    async def _init_knowledge_systems(self):
        """Initialize knowledge base and data systems"""
        # Initialize knowledge base
        self.knowledge_base = KnowledgeBase()
        await self.knowledge_base.initialize()
        
        # Initialize aviation data manager
        self.aviation_data = AviationDataManager()
        await self.aviation_data.initialize()
        
        # Initialize RAG system
        self.rag_system = RAGSystem(
            data_dir="data/knowledge",
            error_handler=self.error_handler
        )
        await self.rag_system.initialize()
        
        logging.info("Knowledge systems ready")
    
    async def _init_ai_systems(self):
        """Initialize AI model and orchestration systems"""
        # Initialize AI model
        self.ai_model = AIModelManager()
        await self.ai_model.load_model()
        
        # Initialize AI orchestrator (requires user_profiles, will be set later)
        # This will be completed in _integrate_all_systems
        logging.info("AI systems ready")
    
    async def _init_memory_systems(self):
        """Initialize memory and user profile systems"""
        # Initialize user profiles
        self.user_profiles = UserProfileManager()
        await self.user_profiles.initialize()
        
        # Initialize conversation memory
        self.conversation_memory = ConversationMemoryManager()
        await self.conversation_memory.initialize()
        
        logging.info("Memory systems ready")
    
    async def _init_interface_systems(self):
        """Initialize Discord interface systems"""
        # Initialize rate limiting system
        self.rate_limit_manager = RateLimitManager(self.embed_builder)
        
        # Embed builder is already initialized
        
        # Other interface components will be initialized in integration phase
        logging.info("Interface systems ready")
    
    async def _integrate_all_systems(self):
        """Integrate all systems together with proper dependencies"""
        logging.info("Integrating all systems...")
        
        # Create AI orchestrator with all dependencies
        self.ai_orchestrator = AIOrchestrator(
            ai_model=self.ai_model,
            user_profiles=self.user_profiles,
            rag_system=self.rag_system,
            error_handler=self.error_handler
        )
        
        # Initialize interaction handler
        self.interaction_handler = InteractionHandler(
            ai_orchestrator=self.ai_orchestrator,
            embed_builder=self.embed_builder,
            rate_limit_manager=self.rate_limit_manager
        )
        
        # Initialize message handler with all components
        self.message_handler = MessageHandler(
            ai_orchestrator=self.ai_orchestrator,
            user_profiles=self.user_profiles,
            rag_system=self.rag_system,
            embed_builder=self.embed_builder,
            rate_limit_manager=self.rate_limit_manager,
            interaction_handler=self.interaction_handler,
            error_handler=self.error_handler,
            performance_monitor=self.performance_monitor
        )
        
        # Update system health
        await self._update_system_health()
        
        logging.info("System integration complete")
    
    async def _start_background_tasks(self):
        """Start background monitoring and maintenance tasks"""
        # Background tasks are automatically started by the components
        # Additional coordination tasks can be added here
        
        # Schedule periodic health checks
        asyncio.create_task(self._periodic_health_check())
        
        # Schedule cleanup tasks
        asyncio.create_task(self._periodic_cleanup())
        
        logging.info("Background tasks started")
    
    async def _periodic_health_check(self):
        """Periodic system health monitoring"""
        while True:
            try:
                await asyncio.sleep(300)  # Every 5 minutes
                await self._update_system_health()
            except asyncio.CancelledError:
                break
            except Exception as e:
                logging.error(f"Error in periodic health check: {e}")
    
    async def _periodic_cleanup(self):
        """Periodic cleanup of inactive resources"""
        while True:
            try:
                await asyncio.sleep(3600)  # Every hour
                
                # Cleanup interaction handler contexts
                if self.interaction_handler:
                    self.interaction_handler.cleanup_inactive_contexts()
                
                # Cleanup AI orchestrator conversations
                if self.ai_orchestrator:
                    self.ai_orchestrator.cleanup_inactive_conversations()
                
                # Run privacy manager retention policies
                if self.privacy_manager:
                    await self.privacy_manager.enforce_retention_policies()
                
            except asyncio.CancelledError:
                break
            except Exception as e:
                logging.error(f"Error in periodic cleanup: {e}")
    
    async def _update_system_health(self):
        """Update overall system health status"""
        try:
            current_time = datetime.utcnow()
            
            # Check component health
            components = {
                "ai_model": self.ai_model and self.ai_model.is_loaded,
                "rag_system": self.rag_system and self.rag_system.is_ready,
                "user_profiles": self.user_profiles is not None,
                "knowledge_base": self.knowledge_base and hasattr(self.knowledge_base, 'is_ready') and self.knowledge_base.is_ready,
                "message_handler": self.message_handler is not None,
                "rate_limit_manager": self.rate_limit_manager is not None,
                "error_handler": self.error_handler is not None,
                "performance_monitor": self.performance_monitor is not None
            }
            
            # Calculate overall health
            healthy_components = sum(1 for status in components.values() if status)
            total_components = len(components)
            overall_healthy = healthy_components == total_components
            
            self.system_health = {
                "overall_healthy": overall_healthy,
                "components": components,
                "last_check": current_time,
                "health_score": healthy_components / total_components
            }
            
            # Update performance monitor with component health
            if self.performance_monitor:
                for component, is_healthy in components.items():
                    self.performance_monitor.update_component_health(component, is_healthy)
            
        except Exception as e:
            logging.error(f"Error updating system health: {e}")
    
    async def on_ready(self):
        """Called when bot is connected and ready"""
        self.startup_time = discord.utils.utcnow()
        self.is_ready = True
        
        logging.info(f"Aviation Girl V4 is ready!")
        logging.info(f"Connected as {self.user} (ID: {self.user.id})")
        logging.info(f"Connected to {len(self.guilds)} servers")
        
        # Set bot status
        activity = discord.Activity(
            type=discord.ActivityType.watching,
            name="the skies ✈️"
        )
        await self.change_presence(activity=activity)
    
    async def on_message(self, message: discord.Message):
        """Handle incoming messages with comprehensive processing"""
        # Ignore bot messages
        if message.author.bot:
            return
        
        # Record user activity for engagement tracking
        if self.performance_monitor:
            self.performance_monitor.record_user_activity(
                message.author.id, 
                "message",
                {"channel_id": message.channel.id, "guild_id": getattr(message.guild, 'id', None)}
            )
        
        # Process commands first
        await self.process_commands(message)
        
        # Handle AI conversation if systems are ready
        if self.message_handler and self.is_ready:
            await self.message_handler.handle_message(message)
    
    async def on_reaction_add(self, reaction: discord.Reaction, user: discord.User):
        """Handle reaction-based interactions"""
        if user.bot:
            return
        
        # Record user activity
        if self.performance_monitor:
            self.performance_monitor.record_user_activity(
                user.id, 
                "reaction",
                {"emoji": str(reaction.emoji), "message_id": reaction.message.id}
            )
            
        if self.interaction_handler:
            await self.interaction_handler.process_reaction_interaction(reaction, user)
    
    async def on_thread_create(self, thread: discord.Thread):
        """Handle new thread creation"""
        if self.interaction_handler:
            # Get the starter message if available
            try:
                starter_message = thread.starter_message or await thread.fetch_message(thread.id)
                if starter_message and not starter_message.author.bot:
                    await self.interaction_handler.manage_thread_conversation(thread, starter_message)
            except:
                pass  # Handle gracefully if we can't get the starter message
    
    async def on_message_edit(self, before: discord.Message, after: discord.Message):
        """Handle message edits"""
        # Only process if the content actually changed and it's not a bot
        if before.content != after.content and not after.author.bot:
            # Record activity
            if self.performance_monitor:
                self.performance_monitor.record_user_activity(
                    after.author.id,
                    "message_edit",
                    {"before_length": len(before.content), "after_length": len(after.content)}
                )
    
    async def on_error(self, event: str, *args, **kwargs):
        """Handle bot errors gracefully with comprehensive error handling"""
        error = args[0] if args else Exception("Unknown error")
        
        context = {
            "event": event,
            "args_count": len(args),
            "kwargs_keys": list(kwargs.keys()) if kwargs else []
        }
        
        # Use error handler if available
        if self.error_handler:
            await self.error_handler.handle_error(
                error,
                context,
                "discord_client",
                severity=ErrorSeverity.HIGH
            )
        else:
            logging.error(f"Bot error in {event}: {error}")
        
        # Try to notify in a channel if possible
        if hasattr(self, 'get_channel') and len(args) > 0:
            if hasattr(args[0], 'channel'):
                try:
                    embed = self.embed_builder.create_error_embed(
                        "Oops! Something went wrong",
                        "I encountered an error processing that request. Please try again."
                    )
                    await args[0].channel.send(embed=embed)
                except:
                    pass
    
    @commands.command(name='status')
    async def status_command(self, ctx):
        """Show comprehensive bot status and health"""
        embed = self.embed_builder.create_info_embed(
            "Aviation Girl V4 Status",
            "Comprehensive system status and information"
        )
        
        # System status with health indicators
        health = self.system_health
        overall_status = "  Healthy" if health.get("overall_healthy") else "⚠️ Issues Detected"
        
        embed.add_field(
            name="🏥 Overall Health",
            value=f"{overall_status} ({health.get('health_score', 0):.1%})",
            inline=True
        )
        
        # Component status
        components = health.get("components", {})
        embed.add_field(
            name="   AI Model",
            value="  Online" if components.get("ai_model") else "  Offline",
            inline=True
        )
        
        embed.add_field(
            name="🧠 Knowledge Base",
            value="  Online" if components.get("rag_system") else "  Offline",
            inline=True
        )
        
        embed.add_field(
            name="💾 Memory System",
            value="  Online" if components.get("user_profiles") else "  Offline",
            inline=True
        )
        
        embed.add_field(
            name="🛡️ Rate Limiting",
            value="  Online" if components.get("rate_limit_manager") else "  Offline",
            inline=True
        )
        
        embed.add_field(
            name="   Performance Monitor",
            value="  Online" if components.get("performance_monitor") else "  Offline",
            inline=True
        )
        
        # Stats
        if self.startup_time:
            uptime = discord.utils.utcnow() - self.startup_time
            embed.add_field(
                name="⏱️ Uptime",
                value=f"{uptime.days}d {uptime.seconds//3600}h {(uptime.seconds//60)%60}m",
                inline=True
            )
        
        embed.add_field(
            name="🌐 Servers",
            value=str(len(self.guilds)),
            inline=True
        )
        
        embed.add_field(
            name="👥 Users",
            value=str(len(self.users)),
            inline=True
        )
        
        # Performance stats if available
        if self.performance_monitor:
            perf_stats = self.performance_monitor.get_performance_stats(1)  # Last hour
            embed.add_field(
                name="📈 Performance (1h)",
                value=f"Avg Response: {perf_stats['overall']['avg_response_time']:.2f}s\n"
                      f"Error Rate: {perf_stats['overall']['error_rate']:.1%}\n"
                      f"Active Users: {perf_stats['overall']['active_users']}",
                inline=False
            )
        
        await ctx.send(embed=embed)
    
    @commands.command(name='health')
    async def health_command(self, ctx):
        """Show detailed system health including all components"""
        if not self.performance_monitor:
            embed = self.embed_builder.create_error_embed(
                "Performance Monitor Unavailable",
                "Performance monitoring system is not initialized."
            )
            await ctx.send(embed=embed)
            return
        
        # Get comprehensive health report
        health_report = self.performance_monitor.get_system_health_report()
        
        embed = self.embed_builder.create_info_embed(
            "🏥 System Health Report",
            f"Overall Status: **{health_report['status'].upper()}**"
        )
        
        # Component health
        components = health_report.get('components', {})
        component_text = ""
        for component, status in components.items():
            icon = " " if status else " "
            component_text += f"{icon} {component.replace('_', ' ').title()}\n"
        
        if component_text:
            embed.add_field(name="Components", value=component_text, inline=True)
        
        # Metrics
        metrics = health_report.get('metrics', {})
        if metrics:
            metrics_text = f"Active Users: {metrics.get('active_users', 0)}\n"
            metrics_text += f"Active Conversations: {metrics.get('active_conversations', 0)}\n"
            metrics_text += f"Error Rate: {metrics.get('error_rate', 0):.1%}\n"
            metrics_text += f"Avg Response Time: {metrics.get('avg_response_time', 0):.2f}s"
            embed.add_field(name="   Metrics", value=metrics_text, inline=True)
        
        # Resource usage
        resources = health_report.get('resource_usage', {})
        if resources:
            resource_text = ""
            for resource, data in resources.items():
                if isinstance(data, dict) and 'current' in data:
                    resource_text += f"{resource.replace('_', ' ').title()}: {data['current']:.1f}\n"
            
            if resource_text:
                embed.add_field(name="💻 Resources", value=resource_text, inline=True)
        
        # Health score color coding
        health_score = health_report.get('overall_health_score', 0)
        if health_score >= 0.8:
            embed.color = self.embed_builder.colors["success"]
        elif health_score >= 0.6:
            embed.color = self.embed_builder.colors["warning"]
        else:
            embed.color = self.embed_builder.colors["error"]
        
        await ctx.send(embed=embed)
    
    @commands.command(name='performance')
    async def performance_command(self, ctx):
        """Show performance statistics"""
        if not self.performance_monitor:
            embed = self.embed_builder.create_error_embed(
                "Performance Monitor Unavailable",
                "Performance monitoring system is not initialized."
            )
            await ctx.send(embed=embed)
            return
        
        # Get performance stats for different time windows
        stats_1h = self.performance_monitor.get_performance_stats(1)
        stats_24h = self.performance_monitor.get_performance_stats(24)
        
        embed = self.embed_builder.create_info_embed(
            "   Performance Statistics",
            "System performance metrics over time"
        )
        
        # 1 hour stats
        embed.add_field(
            name="📈 Last Hour",
            value=f"Avg Response: {stats_1h['overall']['avg_response_time']:.2f}s\n"
                  f"Error Rate: {stats_1h['overall']['error_rate']:.1%}\n"
                  f"Active Users: {stats_1h['overall']['active_users']}\n"
                  f"Engagement: {stats_1h['overall']['user_engagement_score']:.1f}/5.0",
            inline=True
        )
        
        # 24 hour stats
        embed.add_field(
            name="📅 Last 24 Hours", 
            value=f"Avg Response: {stats_24h['overall']['avg_response_time']:.2f}s\n"
                  f"Error Rate: {stats_24h['overall']['error_rate']:.1%}\n"
                  f"Active Users: {stats_24h['overall']['active_users']}\n"
                  f"Engagement: {stats_24h['overall']['user_engagement_score']:.1f}/5.0",
            inline=True
        )
        
        # Component performance
        components_text = ""
        for component, comp_stats in stats_1h.get('components', {}).items():
            components_text += f"**{component}**: {comp_stats['avg_response_time']:.2f}s "
            components_text += f"({comp_stats['error_rate']:.1%} errors)\n"
        
        if components_text:
            embed.add_field(name="🔧 Components (1h)", value=components_text, inline=False)
        
        await ctx.send(embed=embed)
    
    @commands.command(name='help')
    async def help_command(self, ctx):
        """Show help information"""
        embed = self.embed_builder.create_info_embed(
            "Aviation Girl V4 Help",
            "I'm an AI assistant specialized in aviation topics!"
        )
        
        embed.add_field(
            name="💬 Natural Conversation",
            value="Just talk to me naturally! I can discuss aviation topics, answer questions, and help with flight planning.",
            inline=False
        )
        
        embed.add_field(
            name="✈️ Aviation Knowledge",
            value="Ask me about aircraft, regulations, weather, airports, or any aviation topic.",
            inline=False
        )
        
        embed.add_field(
            name="🧠 Memory",
            value="I remember our conversations and learn about your aviation interests and experience level.",
            inline=False
        )
        
        embed.add_field(
            name="🛠️ Commands",
            value="`!status` - Check bot status\n`!help` - Show this help\n`!profile` - View your aviation profile",
            inline=False
        )
        
        await ctx.send(embed=embed)
    
    @commands.command(name='profile')
    async def profile_command(self, ctx):
        """Show user's aviation profile with enhanced information"""
        if not self.user_profiles:
            embed = self.embed_builder.create_error_embed(
                "Profile System Unavailable",
                "User profile system is not initialized."
            )
            await ctx.send(embed=embed)
            return
        
        user_profile = await self.user_profiles.get_profile(ctx.author.id)
        
        embed = self.embed_builder.create_info_embed(
            f"{ctx.author.display_name}'s Aviation Profile",
            "Your personalized aviation information and progress"
        )
        
        if user_profile:
            embed.add_field(
                name="🎓 Experience Level",
                value=user_profile.get('experience_level', 'Not set'),
                inline=True
            )
            
            embed.add_field(
                name="✈️ Interests",
                value=", ".join(user_profile.get('interests', [])) or "None recorded",
                inline=True
            )
            
            embed.add_field(
                name="📚 Learning Goals",
                value=", ".join(user_profile.get('learning_goals', [])) or "None set",
                inline=True
            )
            
            embed.add_field(
                name="💬 Conversations",
                value=str(user_profile.get('conversation_count', 0)),
                inline=True
            )
            
            embed.add_field(
                name="   Engagement Score",
                value=f"{user_profile.get('avg_response_satisfaction', 0):.1f}/5.0",
                inline=True
            )
            
            # Recent topics
            recent_topics = user_profile.get('recent_topics', [])
            if recent_topics:
                embed.add_field(
                    name="  Recent Topics",
                    value=", ".join(recent_topics[:5]),
                    inline=False
                )
        else:
            embed.add_field(
                name="New User",
                value="Start chatting with me to build your aviation profile! I'll learn about your interests and experience level as we talk.",
                inline=False
            )
        
        await ctx.send(embed=embed)
    
    @commands.command(name='privacy')
    async def privacy_command(self, ctx):
        """Show privacy controls and data management options"""
        embed = self.embed_builder.create_info_embed(
            "🔒 Privacy & Data Management",
            "Control your data and privacy settings"
        )
        
        embed.add_field(
            name="   Data Collection",
            value="I collect conversation data to personalize your experience and improve responses. "
                  "This includes your aviation interests, experience level, and conversation history.",
            inline=False
        )
        
        embed.add_field(
            name="🗑️ Data Deletion",
            value="Use `!delete-data` to request deletion of your profile and conversation history. "
                  "This action is permanent and cannot be undone.",
            inline=False
        )
        
        embed.add_field(
            name="🔐 Data Security",
            value="Your data is encrypted and stored securely. I never share personal information "
                  "and follow privacy best practices.",
            inline=False
        )
        
        embed.add_field(
            name="⏰ Data Retention",
            value="Conversation data is automatically anonymized after 30 days and deleted after 1 year "
                  "unless you request earlier deletion.",
            inline=False
        )
        
        await ctx.send(embed=embed)
    
    @commands.command(name='delete-data')
    async def delete_data_command(self, ctx):
        """Delete user data (privacy compliance)"""
        if not self.privacy_manager:
            embed = self.embed_builder.create_error_embed(
                "Privacy Manager Unavailable",
                "Data deletion system is not available right now."
            )
            await ctx.send(embed=embed)
            return
        
        # Confirm deletion request
        embed = self.embed_builder.create_warning_embed(
            "⚠️ Data Deletion Request",
            f"{ctx.author.mention}, are you sure you want to delete all your data?\n\n"
            "This will permanently remove:\n"
            "• Your aviation profile and preferences\n"
            "• All conversation history\n"
            "• Learning progress and interests\n\n"
            "**This action cannot be undone!**\n\n"
            "React with   to confirm or   to cancel."
        )
        
        message = await ctx.send(embed=embed)
        await message.add_reaction(" ")
        await message.add_reaction(" ")
        
        def check(reaction, user):
            return (user == ctx.author and 
                   str(reaction.emoji) in [" ", " "] and 
                   reaction.message.id == message.id)
        
        try:
            reaction, user = await self.wait_for('reaction_add', timeout=60.0, check=check)
            
            if str(reaction.emoji) == " ":
                # Perform data deletion
                deletion_report = await self.privacy_manager.delete_user_data(ctx.author.id)
                
                if deletion_report["success"]:
                    embed = self.embed_builder.create_success_embed(
                        "  Data Deleted Successfully",
                        f"All your data has been permanently deleted.\n\n"
                        f"Files deleted: {deletion_report['files_deleted']}\n"
                        f"Database records deleted: {deletion_report['database_records_deleted']}\n\n"
                        f"Deletion ID: `{deletion_report['user_id']}`"
                    )
                else:
                    embed = self.embed_builder.create_error_embed(
                        "  Data Deletion Failed",
                        f"There was an error deleting your data. Please contact support.\n\n"
                        f"Errors: {'; '.join(deletion_report['errors'])}"
                    )
                
                await message.edit(embed=embed)
                await message.clear_reactions()
            else:
                embed = self.embed_builder.create_info_embed(
                    "Data Deletion Cancelled",
                    "Your data deletion request has been cancelled. Your data remains intact."
                )
                await message.edit(embed=embed)
                await message.clear_reactions()
                
        except asyncio.TimeoutError:
            embed = self.embed_builder.create_info_embed(
                "Request Timed Out",
                "Data deletion request timed out. Your data remains intact."
            )
            await message.edit(embed=embed)
            await message.clear_reactions()
    
    @commands.command(name='admin-health')
    @commands.has_permissions(administrator=True)
    async def admin_health_command(self, ctx):
        """Administrative health check with detailed diagnostics"""
        if not self.performance_monitor:
            await ctx.send("Performance monitor not available.")
            return
        
        # Get comprehensive system information
        health_report = self.performance_monitor.get_system_health_report()
        perf_stats = self.performance_monitor.get_performance_stats(24)
        engagement_report = self.performance_monitor.get_user_engagement_report()
        
        # Create detailed admin embed
        embed = self.embed_builder.create_info_embed(
            "🔧 Administrative Health Report",
            f"Comprehensive system diagnostics"
        )
        
        # System health
        embed.add_field(
            name="🏥 System Health",
            value=f"Status: **{health_report['status'].upper()}**\n"
                  f"Score: {health_report.get('overall_health_score', 0):.1%}\n"
                  f"Last Check: {health_report.get('timestamp', 'Unknown')}",
            inline=True
        )
        
        # Performance metrics
        embed.add_field(
            name="   Performance (24h)",
            value=f"Avg Response: {perf_stats['overall']['avg_response_time']:.2f}s\n"
                  f"Error Rate: {perf_stats['overall']['error_rate']:.1%}\n"
                  f"Total Metrics: {perf_stats['total_metrics']}",
            inline=True
        )
        
        # User engagement
        embed.add_field(
            name="👥 User Engagement",
            value=f"Active (24h): {engagement_report['active_users_24h']}\n"
                  f"Active (1h): {engagement_report['active_users_1h']}\n"
                  f"Total Users: {engagement_report['total_users']}\n"
                  f"Messages: {engagement_report['total_messages']}",
            inline=True
        )
        
        # Error statistics if available
        if self.error_handler:
            error_stats = self.error_handler.get_error_statistics()
            embed.add_field(
                name="⚠️ Error Statistics",
                value=f"Recovery Rate: {error_stats['recovery_success_rate']:.1%}\n"
                      f"Most Common: {error_stats.get('most_common_category', 'None')}",
                inline=True
            )
        
        # Resource usage
        resources = health_report.get('resource_usage', {})
        if resources:
            resource_text = ""
            for resource, data in resources.items():
                if isinstance(data, dict) and 'current' in data:
                    resource_text += f"{resource}: {data['current']:.1f} "
                    resource_text += f"(avg: {data.get('average', 0):.1f})\n"
            
            if resource_text:
                embed.add_field(name="💻 Resources", value=resource_text, inline=True)
        
        # Startup report summary
        if self.startup_report:
            embed.add_field(
                name="  Startup Report",
                value=f"Status: {self.startup_report.overall_status.value}\n"
                      f"Checks: {self.startup_report.passed_checks}  "
                      f"{self.startup_report.failed_checks}  "
                      f"{self.startup_report.warning_checks}⚠️",
                inline=True
            )
        
        await ctx.send(embed=embed)

def run_bot():
    """Main function to run the bot with comprehensive configuration"""
    # Setup logging
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
        handlers=[
            logging.FileHandler('logs/bot.log'),
            logging.StreamHandler()
        ]
    )
    
    # Ensure required directories exist
    import os
    os.makedirs('logs', exist_ok=True)
    os.makedirs('data', exist_ok=True)
    os.makedirs('keys', exist_ok=True)
    
    # Load configuration
    try:
        from .config_manager import ConfigManager
        config_manager = ConfigManager()
        config = asyncio.run(config_manager.load_configuration())
        logging.info(f"Loaded configuration for environment: {config.deployment.environment.value}")
    except Exception as e:
        logging.error(f"Failed to load configuration: {e}")
        return
    
    # Get Discord token
    token = config.discord.token
    if not token:
        logging.error("DISCORD_TOKEN not found in configuration")
        return
    
    # Create and run bot
    bot = AviationGirlBot(config)
    
    try:
        logging.info("Starting Aviation Girl V4...")
        bot.run(token)
    except KeyboardInterrupt:
        logging.info("Bot shutdown requested by user")
    except Exception as e:
        logging.error(f"Bot crashed: {e}")
        raise
    finally:
        # Cleanup
        logging.info("Performing cleanup...")
        try:
            if hasattr(bot, 'performance_monitor') and bot.performance_monitor:
                asyncio.run(bot.performance_monitor.shutdown())
            if hasattr(bot, 'error_handler') and bot.error_handler:
                bot.error_handler.cleanup()
        except Exception as cleanup_error:
            logging.error(f"Error during cleanup: {cleanup_error}")

if __name__ == "__main__":
    run_bot()