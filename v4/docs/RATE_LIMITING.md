# Rate Limiting and Abuse Prevention System

## Overview

The Aviation Girl V4 Discord bot implements a comprehensive rate limiting and abuse prevention system that protects against malicious usage while maintaining service quality for legitimate users. The system addresses **Requirements 9.6** (Discord rate limiting) and **11.6** (abuse prevention).

## Architecture

### Core Components

1. **SystemRateLimiter** - Main coordination layer
2. **DiscordRateLimiter** - Discord API specific rate limiting
3. **AbuseDetector** - Pattern detection and prevention
4. **RateLimitManager** - High-level integration with bot components

### Key Features

-  **Multi-level Rate Limiting**: User, system, and Discord API limits
-  **Abuse Detection**: Spam, duplicate content, and resource exhaustion detection
-  **Graceful Degradation**: Maintains core functionality under high load
-  **Comprehensive Monitoring**: Real-time statistics and health monitoring
-  **User-Friendly Responses**: Clear notifications when limits are reached
-  **Discord Integration**: Handles Discord's complex rate limiting rules

## Rate Limiting Types

### User-Level Limits

| Limit Type | Default Threshold | Time Window | Purpose |
|------------|------------------|-------------|---------|
| Messages | 30 requests | 60 seconds | Prevent message spam |
| Interactions | 60 requests | 60 seconds | Limit reaction/command spam |
| AI Processing | 20 requests | 60 seconds | Protect AI resources |

### System-Level Limits

| Limit Type | Default Threshold | Time Window | Purpose |
|------------|------------------|-------------|---------|
| Global System | 1000 requests | 60 seconds | Overall system protection |
| External API | 100 requests | 60 seconds | Protect external services |

### Discord API Limits

| Limit Type | Default Threshold | Time Window | Purpose |
|------------|------------------|-------------|---------|
| Global | 50 requests | 1 second | Discord global limit |
| Per Channel | 5 requests | 5 seconds | Channel-specific limit |
| Per Guild | 10 requests | 10 seconds | Server-specific limit |

## Abuse Detection

### Detection Patterns

1. **Spam Messages**: >10 messages per minute
2. **Rapid Interactions**: >20 interactions per minute  
3. **Duplicate Content**: >5 identical messages
4. **Resource Exhaustion**: >100 requests per minute

### Response Actions

- **Low Severity (0.0-0.5)**: Log only
- **Medium Severity (0.5-0.8)**: Warn user
- **High Severity (0.8-1.0)**: Temporarily block user

## Usage Examples

### Basic Integration

```python
from bot.rate_limit_manager import RateLimitManager
from bot.embed_builder import EmbedBuilder

# Initialize rate limiting
embed_builder = EmbedBuilder()
rate_manager = RateLimitManager(embed_builder)

# Check message rate limit
is_allowed = await rate_manager.check_message_rate_limit(
    user_id=user.id,
    message_content=message.content,
    channel=message.channel
)

if not is_allowed:
    return  # Rate limited - user already notified
```

### Discord API Rate Limiting

```python
# Queue Discord API calls with rate limiting
try:
    result = await rate_manager.queue_discord_api_call(
        channel.send,
        embed=response_embed,
        channel_id=channel.id,
        guild_id=guild.id,
        priority=0,
        max_wait_time=30.0
    )
except Exception as e:
    # Handle rate limit or timeout
    logging.error(f"Discord API call failed: {e}")
```

### System Health Monitoring

```python
# Get system health status
health_embed = await rate_manager.get_system_health_embed()
await channel.send(embed=health_embed)

# Monitor for alerts
await rate_manager.monitor_system_health()

# Get detailed statistics
stats = rate_manager.get_manager_stats()
print(f"System load: {stats['system_stats']['system_load']:.1%}")
```

## Configuration

### Rate Limit Customization

```python
# Customize user limits
rate_limiter.user_limits[LimitType.USER_MESSAGE] = RateLimit(
    max_requests=50,  # Allow 50 messages
    time_window=60,   # Per minute
    burst_allowance=5 # Extra 5 for bursts
)

# Customize system limits
rate_limiter.system_limits[LimitType.GLOBAL_SYSTEM] = RateLimit(
    max_requests=2000,
    time_window=60
)
```

### Abuse Detection Tuning

```python
# Adjust abuse thresholds
abuse_detector.spam_threshold = 15        # Messages per minute
abuse_detector.duplicate_threshold = 3    # Duplicate messages
abuse_detector.resource_threshold = 150   # Total requests per minute
```

## Graceful Degradation

The system implements graceful degradation when under high load:

### Degradation Levels

- **Level 0**: Normal operation
- **Level 1**: Slower responses, some features limited
- **Level 2**: Heavy load, reduced functionality
- **Level 3**: At capacity, minimal service

### Automatic Activation

Degradation activates when:
- System load exceeds 80% capacity
- Global rate limits are consistently hit
- Queue sizes become excessive

## Monitoring and Alerts

### Health Metrics

- **System Load**: Current capacity utilization
- **Request Rates**: Processed vs blocked requests
- **Abuse Patterns**: Detection statistics
- **Queue Status**: Pending request counts

### Alert Thresholds

- **Abuse Rate**: >10% of requests flagged
- **Block Rate**: >5% of requests blocked  
- **System Load**: >80% capacity

### Statistics Available

```python
stats = rate_manager.get_manager_stats()

# System metrics
system_load = stats['system_stats']['system_load']
requests_processed = stats['system_stats']['requests_processed']
requests_blocked = stats['system_stats']['requests_blocked']

# Abuse statistics
abuse_stats = stats['system_stats']['abuse_stats']
blocked_users = abuse_stats['blocked_users']
warned_users = abuse_stats['warned_users']
```

## Error Handling

### Common Scenarios

1. **Rate Limit Exceeded**: User receives friendly notification
2. **System Overload**: Graceful degradation with status messages
3. **Discord API Errors**: Automatic retry with exponential backoff
4. **Abuse Detection**: Progressive warnings and temporary blocks

### User Notifications

The system provides user-friendly messages for different scenarios:

- **Rate Limited**: "You're sending messages a bit too quickly!"
- **System Load**: "I'm experiencing high demand right now"
- **Abuse Detected**: "We've noticed unusual activity patterns"

## Testing

### Property-Based Testing

The system includes comprehensive property-based tests that validate:

- Rate limiting consistency across all usage patterns
- Abuse detection accuracy for various attack patterns
- Graceful degradation under simulated load
- Integration with Discord bot components

### Running Tests

```bash
# Run main property test
python -m pytest v4/tests/test_rate_limiting_and_abuse_prevention.py::TestSystemRateLimiter::test_rate_limiting_and_abuse_prevention_property -v

# Run all rate limiting tests
python -m pytest v4/tests/test_rate_limiting_and_abuse_prevention.py -v

# Run demo
python v4/examples/rate_limiting_demo.py
```

## Administrative Functions

### User Management

```python
# Reset user limits (admin only)
success = await rate_manager.reset_user_limits(
    user_id=problem_user_id,
    admin_user_id=admin_id
)

# Check user status
user_info = rate_manager.get_user_rate_limit_info(user_id)
is_blocked = user_info['is_blocked']
is_warned = user_info['is_warned']
```

### System Control

```python
# Enable/disable monitoring
rate_manager.enable_monitoring()
rate_manager.disable_monitoring()

# Check degradation status
if rate_manager.system_limiter.is_degradation_active():
    level = rate_manager.system_limiter.get_degradation_level()
    print(f"Degradation active at level {level}")
```

## Best Practices

### Implementation Guidelines

1. **Always check rate limits** before processing user requests
2. **Use appropriate limit types** for different request categories
3. **Handle rate limit responses gracefully** with user notifications
4. **Monitor system health regularly** to detect issues early
5. **Configure thresholds appropriately** for your use case

### Performance Considerations

- Rate limiting adds minimal overhead (~1-2ms per check)
- Memory usage scales with active user count
- Cleanup processes run automatically every 5 minutes
- Queue processing is asynchronous and non-blocking

### Security Notes

- User IDs are the primary rate limiting key
- Content hashing prevents duplicate message abuse
- Temporary blocks automatically expire
- All abuse patterns are logged for analysis

## Integration with Bot Components

### Message Handler Integration

```python
# In message_handler.py
async def handle_message(self, message):
    # Check rate limiting first
    if self.rate_limit_manager:
        if not await self.rate_limit_manager.check_message_rate_limit(
            message.author.id, message.content, message.channel
        ):
            return  # Rate limited
    
    # Process message normally
    await self._process_message_safely(message)
```

### Interaction Handler Integration

```python
# In interaction_handler.py
async def process_reaction_interaction(self, reaction, user):
    # Check interaction rate limiting
    if self.rate_limit_manager:
        if not await self.rate_limit_manager.check_interaction_rate_limit(
            user.id, "reaction", reaction.message.channel
        ):
            return  # Rate limited
    
    # Process interaction normally
    await self._handle_reaction(reaction, user)
```

## Troubleshooting

### Common Issues

1. **False Positives**: Adjust abuse detection thresholds
2. **Performance Impact**: Enable degradation or increase limits
3. **User Complaints**: Review notification messages and cooldowns
4. **System Overload**: Check for resource bottlenecks

### Debug Information

```python
# Get detailed system state
stats = rate_manager.get_manager_stats()
print(json.dumps(stats, indent=2))

# Check specific user status
user_info = rate_manager.get_user_rate_limit_info(user_id)
print(f"User {user_id}: {user_info}")

# Monitor real-time activity
await rate_manager.monitor_system_health()
```

This comprehensive rate limiting system ensures the Aviation Girl V4 bot remains responsive and secure while providing excellent user experience for legitimate users.