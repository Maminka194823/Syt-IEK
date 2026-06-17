"""
Rate Limiting and Abuse Prevention Demo
Demonstrates the comprehensive rate limiting system in action
"""

import asyncio
import logging
import sys
import os

# Add src to path for imports
sys.path.append(os.path.join(os.path.dirname(__file__), '..', 'src'))

from bot.rate_limiter import SystemRateLimiter, LimitType, AbuseType
from bot.rate_limit_manager import RateLimitManager
from bot.embed_builder import EmbedBuilder


async def demo_basic_rate_limiting():
    """Demonstrate basic rate limiting functionality"""
    print("=== Basic Rate Limiting Demo ===")
    
    rate_limiter = SystemRateLimiter()
    user_id = 12345
    
    print(f"Testing rate limits for user {user_id}")
    
    # Test normal usage
    for i in range(5):
        is_allowed, reason = await rate_limiter.check_rate_limit(
            user_id=user_id,
            limit_type=LimitType.USER_MESSAGE,
            content=f"Normal message {i}",
            metadata={"message_number": i}
        )
        
        status = "  ALLOWED" if is_allowed else f"  BLOCKED: {reason}"
        print(f"  Message {i+1}: {status}")
        
        await asyncio.sleep(0.1)
    
    print()


async def demo_abuse_detection():
    """Demonstrate abuse detection capabilities"""
    print("=== Abuse Detection Demo ===")
    
    rate_limiter = SystemRateLimiter()
    user_id = 54321
    
    print(f"Testing abuse detection for user {user_id}")
    
    # Test spam detection - send many messages quickly
    print("\n1. Testing spam detection (rapid messages):")
    for i in range(15):
        is_allowed, reason = await rate_limiter.check_rate_limit(
            user_id=user_id,
            limit_type=LimitType.USER_MESSAGE,
            content=f"Rapid message {i}",
            metadata={"spam_test": True}
        )
        
        status = "  ALLOWED" if is_allowed else f"  BLOCKED: {reason}"
        print(f"  Rapid message {i+1}: {status}")
        
        if not is_allowed:
            break
    
    # Test duplicate content detection
    print("\n2. Testing duplicate content detection:")
    duplicate_content = "This is a duplicate message"
    
    for i in range(8):
        is_allowed, reason = await rate_limiter.check_rate_limit(
            user_id=user_id + 1,  # Different user
            limit_type=LimitType.USER_MESSAGE,
            content=duplicate_content,  # Same content
            metadata={"duplicate_test": True}
        )
        
        status = "  ALLOWED" if is_allowed else f"  BLOCKED: {reason}"
        print(f"  Duplicate message {i+1}: {status}")
        
        if not is_allowed:
            break
    
    print()


async def demo_graceful_degradation():
    """Demonstrate graceful degradation under high load"""
    print("=== Graceful Degradation Demo ===")
    
    rate_limiter = SystemRateLimiter()
    
    print("Simulating high system load...")
    
    # Simulate many users making requests simultaneously
    async def simulate_user_load(user_id, request_count):
        blocked_count = 0
        for i in range(request_count):
            is_allowed, reason = await rate_limiter.check_rate_limit(
                user_id=user_id,
                limit_type=LimitType.USER_MESSAGE,
                content=f"Load test message {i}",
                metadata={"load_test": True}
            )
            
            if not is_allowed:
                blocked_count += 1
        
        return blocked_count
    
    # Create tasks for multiple users
    tasks = []
    for user_id in range(100, 110):  # 10 users
        task = simulate_user_load(user_id, 20)  # 20 requests each
        tasks.append(task)
    
    # Run all tasks concurrently
    results = await asyncio.gather(*tasks)
    
    total_blocked = sum(results)
    total_requests = len(tasks) * 20
    
    print(f"  Total requests: {total_requests}")
    print(f"  Blocked requests: {total_blocked}")
    print(f"  Block rate: {total_blocked/total_requests:.1%}")
    
    # Check if degradation was activated
    if rate_limiter.is_degradation_active():
        print(f"  🚦 Graceful degradation activated (level {rate_limiter.get_degradation_level()})")
    else:
        print("    System handled load without degradation")
    
    print()


async def demo_rate_limit_manager():
    """Demonstrate the high-level rate limit manager"""
    print("=== Rate Limit Manager Demo ===")
    
    embed_builder = EmbedBuilder()
    rate_manager = RateLimitManager(embed_builder)
    
    print("Rate limit manager features:")
    
    # Get system health
    health_embed = await rate_manager.get_system_health_embed()
    print(f"     System health: {health_embed.title}")
    print(f"  📝 Description: {health_embed.description}")
    
    # Get user status
    user_id = 99999
    user_info = rate_manager.get_user_rate_limit_info(user_id)
    print(f"  👤 User {user_id} status:")
    print(f"    - Blocked: {user_info['is_blocked']}")
    print(f"    - Warned: {user_info['is_warned']}")
    print(f"    - Can be notified: {user_info['can_be_notified']}")
    
    # Get manager statistics
    stats = rate_manager.get_manager_stats()
    print(f"  📈 Manager stats:")
    print(f"    - Monitoring enabled: {stats['monitoring_enabled']}")
    print(f"    - Notification settings: {stats['notification_settings']['notify_on_limit']}")
    
    print()


async def demo_system_statistics():
    """Show comprehensive system statistics"""
    print("=== System Statistics Demo ===")
    
    rate_limiter = SystemRateLimiter()
    
    # Generate some activity first
    for user_id in range(200, 205):
        for i in range(3):
            await rate_limiter.check_rate_limit(
                user_id=user_id,
                limit_type=LimitType.USER_MESSAGE,
                content=f"Stats test message {i}",
                metadata={"stats_test": True}
            )
    
    # Get comprehensive statistics
    stats = rate_limiter.get_system_stats()
    
    print("System Statistics:")
    print(f"     Requests processed: {stats['requests_processed']:,}")
    print(f"  🚫 Requests blocked: {stats['requests_blocked']:,}")
    print(f"    Abuse detected: {stats['abuse_detected']:,}")
    print(f"  📈 System load: {stats['system_load']:.1%}")
    print(f"  👥 Active users: {stats['active_users']:,}")
    print(f"  📋 Queue size: {stats['queue_size']:,}")
    
    # Abuse statistics
    abuse_stats = stats.get('abuse_stats', {})
    print(f"\nAbuse Detection:")
    print(f"  🚫 Blocked users: {abuse_stats.get('blocked_users', 0):,}")
    print(f"  ⚠️  Warned users: {abuse_stats.get('warned_users', 0):,}")
    print(f"    Total patterns: {abuse_stats.get('total_patterns', 0):,}")
    
    # Pattern breakdown
    patterns_by_type = abuse_stats.get('patterns_by_type', {})
    if patterns_by_type:
        print(f"     Patterns by type:")
        for abuse_type, count in patterns_by_type.items():
            if count > 0:
                print(f"    - {abuse_type}: {count:,}")
    
    print()


async def main():
    """Run all demonstrations"""
    print("🛡️  Rate Limiting and Abuse Prevention System Demo")
    print("=" * 60)
    print()
    
    # Set up logging to see what's happening
    logging.basicConfig(level=logging.INFO, format='%(levelname)s: %(message)s')
    
    try:
        await demo_basic_rate_limiting()
        await demo_abuse_detection()
        await demo_graceful_degradation()
        await demo_rate_limit_manager()
        await demo_system_statistics()
        
        print("  All demonstrations completed successfully!")
        print("\nKey Features Demonstrated:")
        print("  🔒 User-specific rate limiting")
        print("  🚫 Abuse pattern detection")
        print("  🔄 Graceful degradation under load")
        print("     Comprehensive monitoring and statistics")
        print("  🎯 Discord API rate limiting")
        print("  💬 User-friendly notifications")
        
    except Exception as e:
        print(f"  Demo failed with error: {e}")
        import traceback
        traceback.print_exc()


if __name__ == "__main__":
    asyncio.run(main())