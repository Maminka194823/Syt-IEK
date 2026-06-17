#!/usr/bin/env python3
"""
AI-Powered V4 Bot - Real AI model with V3's proven loading approach
Combines the working instant bot structure with actual AI capabilities
"""

import discord
from discord.ext import commands
import os
import asyncio
import sys
from datetime import datetime
from pathlib import Path

# Load environment variables
try:
    from dotenv import load_dotenv
    load_dotenv()
except ImportError:
    pass

# Add V3 paths for model loading
v3_path = Path(__file__).parent.parent / "v3" / "src"
sys.path.append(str(v3_path))

# Import V3's proven model loading
try:
    from model.loader import load_base_with_adapter, get_device
    from model.generator import generate_response
    MODEL_LOADING_AVAILABLE = True
except ImportError as e:
    print(f"⚠️ V3 model loading not available: {e}")
    MODEL_LOADING_AVAILABLE = False

class AIPoweredBot(commands.Bot):
    """
    AI-Powered Aviation Bot - Real AI with V3's proven approach
    """
    
    def __init__(self):
        intents = discord.Intents.default()
        intents.message_content = True
        
        super().__init__(
            command_prefix='!',
            intents=intents,
            help_command=None
        )
        
        self.startup_time = None
        self.is_ready = False
        
        # AI Model components (like V3)
        self.model = None
        self.tokenizer = None
        self.model_loaded = False
        self.model_loading = False
        
        # Configuration from environment
        self.model_path = os.getenv('MODEL_PATH', '../models/qwan_7b/aviation_girl_v3_adapter')
        self.use_gpu = os.getenv('USE_GPU', 'true').lower() == 'true'
    
    async def setup_hook(self):
        """Simple setup - no command sync to avoid errors"""
        print("🔧 Setting up AI-powered bot...")
    
    async def on_ready(self):
        """Bot is ready - start AI loading in background"""
        self.startup_time = datetime.utcnow()
        self.is_ready = True
        
        print("\n" + "─" * 60)
        print("     Aviation Girl V4 - AI POWERED!")
        print("─" * 60)
        print(f'  Logged in as: {self.user}')
        print(f'  Bot ID: {self.user.id}')
        print(f'  Connected to {len(self.guilds)} servers')
        
        if self.guilds:
            print("  📡 Connected servers:")
            for guild in self.guilds:
                print(f"    - {guild.name} ({guild.member_count} members)")
        else:
            print("  ⚠️  Not connected to any servers!")
        
        print("  🧠 Starting AI model loading...")
        print("─" * 60 + "\n")
        
        # Set status
        activity = discord.Activity(
            type=discord.ActivityType.watching,
            name="the skies ✈️ (AI Loading...)"
        )
        await self.change_presence(activity=activity)
        
        # Start AI loading in background (like V3)
        asyncio.create_task(self.load_ai_model_background())
    
    async def load_ai_model_background(self):
        """Load AI model in background like V3 does"""
        if not MODEL_LOADING_AVAILABLE:
            print("  Model loading not available - using fallback responses")
            self.model_loaded = False
            return
        
        if self.model_loading:
            return  # Already loading
        
        self.model_loading = True
        
        try:
            print("🔄 Starting AI model loading in background...")
            
            # Use V3's proven approach - run in executor to avoid blocking
            loop = asyncio.get_event_loop()
            await loop.run_in_executor(None, self._load_model_sync)
            
            self.model_loaded = True
            
            print("\n🎉 AI Model loading complete!")
            print("  Aviation Girl V4 is now AI-powered!")
            print("  Ready for intelligent aviation conversations\n")
            
            # Update status
            activity = discord.Activity(
                type=discord.ActivityType.watching,
                name="the skies ✈️ (AI Ready)"
            )
            await self.change_presence(activity=activity)
            
        except Exception as e:
            print(f"\n  AI model loading failed: {e}")
            print("⚠️ Bot will continue with fallback responses")
            self.model_loaded = False
            import traceback
            traceback.print_exc()
        finally:
            self.model_loading = False
    
    def _load_model_sync(self):
        """Load model synchronously using V3's approach"""
        print("🔄 Loading Qwen2.5-7B with adapter (V3 method)...")
        
        # Use V3's device detection
        device = get_device()
        has_gpu = "cuda" in str(device) or "directml" in str(device)
        
        base_model = "Qwen/Qwen2.5-7B-Instruct"
        
        # Check if model path exists
        model_path = self.model_path
        if model_path and not Path(model_path).exists():
            # Try relative to project root
            project_root = Path(__file__).parent.parent
            full_model_path = project_root / model_path
            if full_model_path.exists():
                model_path = str(full_model_path)
            else:
                print(f"⚠️ Model path {model_path} not found, using base model only")
                model_path = None
        
        if self.use_gpu and has_gpu:
            print(f"   Using {device} with optimizations")
            try:
                self.model, self.tokenizer = load_base_with_adapter(
                    base_model, 
                    model_path,
                    use_8bit=True,
                    force_cpu=False
                )
                print("     GPU loading successful!")
                return
            except Exception as e:
                print(f"   ⚠️ GPU loading failed: {e}")
                print("   Falling back to CPU mode...")
        
        # CPU fallback
        print("   Using CPU mode (slower but reliable)")
        self.model, self.tokenizer = load_base_with_adapter(
            base_model, 
            model_path,
            use_8bit=False,
            force_cpu=True
        )
        print("     CPU loading successful!")
    
    async def on_message(self, message):
        """Handle messages with AI or fallback responses"""
        if message.author.bot:
            return
        
        # Process commands
        await self.process_commands(message)
        
        # Respond to mentions
        if self.user in message.mentions:
            async with message.channel.typing():
                response = await self._generate_ai_response(message)
                await message.reply(response)
    
    async def _generate_ai_response(self, message):
        """Generate AI response or fallback"""
        user_message = message.content.replace(f'<@{self.user.id}>', '').strip()
        
        # If model is still loading
        if self.model_loading and not self.model_loaded:
            return "🧠 AI model is loading in the background, please wait a moment... (This is real AI loading, not pre-made responses!)"
        
        # If model loaded successfully, use AI
        if self.model_loaded and self.model and self.tokenizer:
            try:
                return await self._generate_with_ai_model(user_message)
            except Exception as e:
                print(f"AI generation error: {e}")
                return f"   AI had a hiccup: {str(e)[:100]}... Using fallback response: " + self._generate_fallback_response(user_message)
        
        # Fallback responses (enhanced)
        return self._generate_fallback_response(user_message) + "\n\n*⚠️ AI model not loaded - using fallback responses*"
    
    async def _generate_with_ai_model(self, user_message):
        """Generate response using real AI model"""
        # Build aviation-focused prompt
        prompt = f"""You are Aviation Girl, a friendly and knowledgeable aviation assistant. You love talking about planes, flying, weather, and all things aviation. You're enthusiastic and use aviation emojis like ✈️ 🛩️ 🚁.

User: {user_message}
Assistant:"""
        
        # Generate using V3's method in executor to avoid blocking
        loop = asyncio.get_event_loop()
        response = await loop.run_in_executor(
            None,
            self._generate_response_sync,
            prompt
        )
        
        return response
    
    def _generate_response_sync(self, prompt):
        """Generate response synchronously using V3's generator"""
        return generate_response(
            self.model,
            self.tokenizer,
            prompt,
            max_new_tokens=150,
            temperature=0.8
        )
    
    def _generate_fallback_response(self, message: str) -> str:
        """Enhanced fallback responses"""
        message_lower = message.lower()
        
        if any(word in message_lower for word in ['hello', 'hi', 'hey', 'heya']):
            return "Hey there! ✈️ I'm Aviation Girl V4 with AI capabilities! Ask me about aviation!"
        
        if any(word in message_lower for word in ['plane', 'aircraft', 'aviation', 'flight']):
            return "I love aviation! ✈️ What would you like to know about planes, flying, or aviation? (AI model will provide detailed responses once loaded!)"
        
        if 'weather' in message_lower:
            return "Weather is crucial for aviation! ✈️ Pilots check conditions before every flight. What weather topic interests you?"
        
        if any(word in message_lower for word in ['model', 'ai', 'smart', 'intelligent']):
            status = "loading" if self.model_loading else "not loaded"
            return f"   My AI model is currently {status}. Once loaded, I'll provide intelligent aviation responses using Qwen2.5-7B! ✈️"
        
        return "That's interesting! ✈️ I'm here for aviation questions. Once my AI model loads, I'll give you detailed, intelligent responses!"
    
    @commands.command(name='status')
    async def status_command(self, ctx):
        """AI-powered status"""
        embed = discord.Embed(
            title="   Aviation Girl V4 - AI Status",
            description="Real AI-powered aviation assistant",
            color=0x00ff00 if self.model_loaded else (0xffaa00 if self.model_loading else 0xff6600)
        )
        
        # AI Status
        if self.model_loaded:
            ai_status = "  AI Model Loaded (Qwen2.5-7B)"
        elif self.model_loading:
            ai_status = "🔄 AI Model Loading..."
        else:
            ai_status = "  AI Model Not Loaded"
        
        embed.add_field(name="🧠 AI Status", value=ai_status, inline=True)
        embed.add_field(name="🌐 Servers", value=str(len(self.guilds)), inline=True)
        embed.add_field(name="⚡ Response", value="AI-Powered" if self.model_loaded else "Fallback", inline=True)
        
        if self.startup_time:
            uptime = datetime.utcnow() - self.startup_time
            embed.add_field(
                name="⏱️ Uptime",
                value=f"{uptime.days}d {uptime.seconds//3600}h {(uptime.seconds//60)%60}m",
                inline=True
            )
        
        # Model info
        if self.model_loaded:
            embed.add_field(
                name="🔧 Model Info",
                value=f"Base: Qwen2.5-7B-Instruct\nAdapter: {self.model_path}\nGPU: {self.use_gpu}",
                inline=False
            )
        
        await ctx.send(embed=embed)
    
    @commands.command(name='reload')
    async def reload_command(self, ctx):
        """Reload AI model"""
        if self.model_loading:
            await ctx.send("🔄 Model is already loading, please wait...")
            return
        
        await ctx.send("🔄 Reloading AI model...")
        self.model_loaded = False
        self.model = None
        self.tokenizer = None
        
        asyncio.create_task(self.load_ai_model_background())
    
    @commands.command(name='ai')
    async def ai_command(self, ctx, *, question: str):
        """Direct AI question"""
        if not self.model_loaded:
            await ctx.send("   AI model not loaded yet. Please wait or use `!reload` to try loading again.")
            return
        
        async with ctx.typing():
            response = await self._generate_ai_response(ctx.message)
            await ctx.send(response)
    
    @commands.command(name='help')
    async def help_command(self, ctx):
        """Help with AI features"""
        embed = discord.Embed(
            title="   Aviation Girl V4 - AI Help",
            description="Real AI-powered aviation assistant!",
            color=0x0099ff
        )
        
        embed.add_field(
            name="💬 AI Chat",
            value="Mention me for AI-powered aviation responses!",
            inline=False
        )
        
        embed.add_field(
            name="✈️ Aviation AI",
            value="Ask about planes, weather, regulations, flight planning - I use Qwen2.5-7B for intelligent responses!",
            inline=False
        )
        
        embed.add_field(
            name="🛠️ Commands",
            value="`!status` - AI and bot status\n`!reload` - Reload AI model\n`!ai <question>` - Direct AI question\n`!help` - This help",
            inline=False
        )
        
        embed.add_field(
            name="🧠 AI Features",
            value="• Real Qwen2.5-7B model\n• Aviation-focused responses\n• Intelligent conversations\n• Background loading",
            inline=False
        )
        
        await ctx.send(embed=embed)

def main():
    """Run the AI-powered bot"""
    token = (os.getenv('DISCORD_TOKEN') or 
             os.getenv('DISCORD_BOT_TOKEN') or 
             os.getenv('AVIATION_BOT_DISCORD_TOKEN'))
    
    if not token:
        print("  Discord token not found!")
        return
    
    bot = AIPoweredBot()
    
    try:
        print("  Starting AI-Powered Aviation Girl V4...")
        print("🧠 Real AI model loading with V3's proven approach")
        print("⚡ Instant responses while AI loads in background")
        bot.run(token)
    except KeyboardInterrupt:
        print("\n🛑 Bot stopped")
    except Exception as e:
        print(f"\n  Error: {e}")

if __name__ == "__main__":
    main()