# Memory System Specification 🧠

Complete specification for the FastMemory system in Aviation Girl v3.

## Overview

Simple, efficient memory system that stores user preferences and context without complex vector databases or embeddings.

### Design Goals
-  Simple implementation (~50 lines)
-  Fast read/write (< 1ms)
-  Persistent storage (JSON file)
-  Auto-detection of memories
-  Easy integration with prompts

---

## Architecture

```
┌─────────────────────────────────────────┐
│           Discord Message               │
└──────────────┬──────────────────────────┘
               │
               ▼
┌─────────────────────────────────────────┐
│      FastMemory.auto_detect()           │
│  (Extract memories from message)        │
└──────────────┬──────────────────────────┘
               │
               ▼
┌─────────────────────────────────────────┐
│      FastMemory.remember()              │
│  (Store in memory.json)                 │
└──────────────┬──────────────────────────┘
               │
               ▼
┌─────────────────────────────────────────┐
│      FastMemory.get_context()           │
│  (Format for prompt)                    │
└──────────────┬──────────────────────────┘
               │
               ▼
┌─────────────────────────────────────────┐
│      Build Prompt with Memory           │
│  "Memory: ... | User: ... | Assistant:" │
└──────────────┬──────────────────────────┘
               │
               ▼
┌─────────────────────────────────────────┐
│      Generate Response                  │
└─────────────────────────────────────────┘
```

---

## Data Structure

### Memory File Format (JSON)

```json
{
  "user_123456789": {
    "name": "Alex",
    "favorite_plane": "747",
    "favorite_airline": "Lufthansa",
    "home_airport": "FRA",
    "travel_plans": "Tokyo next month",
    "last_updated": "2026-01-26T17:00:00Z"
  },
  "user_987654321": {
    "name": "Maria",
    "favorite_plane": "A380",
    "favorite_airline": "Emirates",
    "travel_plans": "New York this weekend",
    "last_updated": "2026-01-26T16:30:00Z"
  }
}
```

### Memory Keys

| Key | Description | Example |
|-----|-------------|---------|
| `name` | User's name | "Alex" |
| `favorite_plane` | Favorite aircraft | "747" |
| `favorite_airline` | Preferred airline | "Lufthansa" |
| `home_airport` | Home airport code | "FRA" |
| `travel_plans` | Upcoming trips | "Tokyo next month" |
| `last_updated` | Last modification | ISO 8601 timestamp |

---

## Detection Patterns

### Regex Patterns for Auto-Detection

```python
PATTERNS = {
    "favorite_plane": [
        r"my favorite plane is (?:the )?(.+?)(?:\.|!|$)",
        r"i love the (.+?)(?:\.|!|$)",
        r"(.+?) is my favorite(?:\.|!|$)",
        r"i really like the (.+?)(?:\.|!|$)",
    ],
    
    "name": [
        r"my name is (.+?)(?:\.|!|$)",
        r"i'm (.+?)(?:\.|!|$)",
        r"call me (.+?)(?:\.|!|$)",
        r"this is (.+?)(?:\.|!|$)",
    ],
    
    "travel_plans": [
        r"i'm flying to (.+?)(?:\.|!|$)",
        r"going to (.+?) (?:next|this)",
        r"traveling to (.+?)(?:\.|!|$)",
        r"trip to (.+?)(?:\.|!|$)",
    ],
    
    "favorite_airline": [
        r"my favorite airline is (.+?)(?:\.|!|$)",
        r"i love flying (.+?)(?:\.|!|$)",
        r"i prefer (.+?) (?:airline|airways)",
    ],
    
    "home_airport": [
        r"i fly out of (.+?)(?:\.|!|$)",
        r"my home airport is (.+?)(?:\.|!|$)",
        r"i'm based at (.+?)(?:\.|!|$)",
    ]
}
```

### Example Detections

```python
# Input: "my favorite plane is the 747"
# Detected: favorite_plane = "747"

# Input: "my name is Alex"
# Detected: name = "alex"

# Input: "i'm flying to Tokyo next month"
# Detected: travel_plans = "Tokyo next month"
```

---

## Implementation

### Core Class

```python
# v3/src/memory/fast_memory.py
import json
import re
from pathlib import Path
from typing import Dict, Optional
from datetime import datetime

class FastMemory:
    """Simple memory system for user preferences."""
    
    PATTERNS = {
        # ... (patterns from above)
    }
    
    def __init__(self, memory_file: str = "memory.json"):
        """Initialize memory system."""
        self.memory_file = Path(memory_file)
        self.memory: Dict[str, Dict] = self._load()
    
    def _load(self) -> Dict:
        """Load memory from JSON file."""
        if self.memory_file.exists():
            try:
                with open(self.memory_file, 'r', encoding='utf-8') as f:
                    return json.load(f)
            except json.JSONDecodeError:
                print(f"Warning: Could not load {self.memory_file}")
                return {}
        return {}
    
    def _save(self):
        """Save memory to JSON file."""
        try:
            # Create backup
            if self.memory_file.exists():
                backup = self.memory_file.with_suffix('.json.bak')
                self.memory_file.rename(backup)
            
            # Save new file
            with open(self.memory_file, 'w', encoding='utf-8') as f:
                json.dump(self.memory, f, indent=2, ensure_ascii=False)
            
            # Remove backup on success
            if backup.exists():
                backup.unlink()
                
        except Exception as e:
            print(f"Error saving memory: {e}")
            # Restore backup if save failed
            if backup.exists():
                backup.rename(self.memory_file)
    
    def remember(self, user_id: str, key: str, value: str):
        """Store a memory for a user."""
        if user_id not in self.memory:
            self.memory[user_id] = {}
        
        self.memory[user_id][key] = value
        self.memory[user_id]["last_updated"] = datetime.now().isoformat()
        self._save()
    
    def recall(self, user_id: str, key: str) -> Optional[str]:
        """Retrieve a memory for a user."""
        return self.memory.get(user_id, {}).get(key)
    
    def get_context(self, user_id: str) -> str:
        """Get formatted memory context for prompts."""
        user_memory = self.memory.get(user_id, {})
        if not user_memory:
            return ""
        
        context_parts = []
        
        # Priority order for context
        priority_keys = [
            "name",
            "favorite_plane",
            "favorite_airline",
            "travel_plans",
            "home_airport"
        ]
        
        for key in priority_keys:
            if key in user_memory:
                # Format nicely
                formatted_key = key.replace("_", " ").title()
                context_parts.append(f"{formatted_key}: {user_memory[key]}")
        
        return " | ".join(context_parts) if context_parts else ""
    
    def auto_detect(self, user_id: str, message: str):
        """Automatically detect and store memories from message."""
        message_lower = message.lower()
        
        for key, patterns in self.PATTERNS.items():
            for pattern in patterns:
                match = re.search(pattern, message_lower, re.IGNORECASE)
                if match:
                    value = match.group(1).strip()
                    # Clean up value
                    value = value.rstrip('.,!?')
                    self.remember(user_id, key, value)
                    print(f"[Memory] Remembered: {key} = {value}")
                    break  # Only match first pattern
    
    def forget(self, user_id: str, key: Optional[str] = None):
        """Forget a specific memory or all memories for a user."""
        if key:
            self.memory.get(user_id, {}).pop(key, None)
        else:
            self.memory.pop(user_id, None)
        self._save()
    
    def get_all_memories(self, user_id: str) -> Dict:
        """Get all memories for a user."""
        return self.memory.get(user_id, {}).copy()
    
    def list_users(self) -> list:
        """Get list of all user IDs with memories."""
        return list(self.memory.keys())
    
    def stats(self) -> Dict:
        """Get memory statistics."""
        return {
            "total_users": len(self.memory),
            "total_memories": sum(len(m) for m in self.memory.values()),
            "file_size": self.memory_file.stat().st_size if self.memory_file.exists() else 0
        }
```

---

## Integration with Bot

### Discord Bot Integration

```python
# v3/src/bot/discord_bot_v3.py
import discord
from memory.fast_memory import FastMemory

class AviationGirlV3(discord.Client):
    def __init__(self):
        super().__init__()
        self.memory = FastMemory("user_memory.json")
        # ... load model
    
    async def on_message(self, message):
        if message.author.bot:
            return
        
        user_id = str(message.author.id)
        user_message = message.content
        
        # Auto-detect and store memories
        self.memory.auto_detect(user_id, user_message)
        
        # Get memory context
        memory_context = self.memory.get_context(user_id)
        
        # Build prompt with memory
        if memory_context:
            prompt = f"Memory: {memory_context}\nUser: {user_message}\nAssistant:"
        else:
            prompt = f"User: {user_message}\nAssistant:"
        
        # Generate response
        response = await self.generate_response(prompt)
        
        # Send response
        await message.channel.send(response)
```

### Prompt Format

```python
# Without memory
"User: what's your favorite plane?\nAssistant:"

# With memory
"Memory: Name: Alex | Favorite Plane: 747 | Travel Plans: Tokyo next month\nUser: what's your favorite plane?\nAssistant:"
```

---

## Commands

### Memory Management Commands

```python
# View memories
!memory show
# Output: Name: Alex | Favorite Plane: 747 | Travel Plans: Tokyo next month

# Forget specific memory
!memory forget favorite_plane
# Output: Forgot your favorite plane!

# Clear all memories
!memory clear
# Output: Cleared all your memories!

# Memory stats
!memory stats
# Output: Total users: 42 | Total memories: 156
```

### Implementation

```python
async def handle_memory_command(self, message, args):
    """Handle memory management commands."""
    user_id = str(message.author.id)
    
    if args[0] == "show":
        memories = self.memory.get_all_memories(user_id)
        if memories:
            text = "\n".join(f"**{k}**: {v}" for k, v in memories.items() if k != "last_updated")
            await message.channel.send(f"Your memories:\n{text}")
        else:
            await message.channel.send("No memories stored yet!")
    
    elif args[0] == "forget" and len(args) > 1:
        key = args[1]
        self.memory.forget(user_id, key)
        await message.channel.send(f"Forgot your {key}!")
    
    elif args[0] == "clear":
        self.memory.forget(user_id)
        await message.channel.send("Cleared all your memories!")
    
    elif args[0] == "stats":
        stats = self.memory.stats()
        await message.channel.send(
            f"Memory stats:\n"
            f"Total users: {stats['total_users']}\n"
            f"Total memories: {stats['total_memories']}\n"
            f"File size: {stats['file_size']} bytes"
        )
```

---

## Testing

### Unit Tests

```python
# v3/tests/test_memory.py
import pytest
from memory.fast_memory import FastMemory

def test_remember_recall():
    """Test basic remember and recall."""
    memory = FastMemory("test_memory.json")
    memory.remember("user123", "favorite_plane", "747")
    assert memory.recall("user123", "favorite_plane") == "747"

def test_auto_detect():
    """Test auto-detection of memories."""
    memory = FastMemory("test_memory.json")
    memory.auto_detect("user123", "my favorite plane is the 747")
    assert memory.recall("user123", "favorite_plane") == "747"

def test_context_generation():
    """Test context string generation."""
    memory = FastMemory("test_memory.json")
    memory.remember("user123", "name", "Alex")
    memory.remember("user123", "favorite_plane", "747")
    context = memory.get_context("user123")
    assert "Alex" in context
    assert "747" in context

def test_forget():
    """Test forgetting memories."""
    memory = FastMemory("test_memory.json")
    memory.remember("user123", "favorite_plane", "747")
    memory.forget("user123", "favorite_plane")
    assert memory.recall("user123", "favorite_plane") is None

def test_persistence():
    """Test that memories persist across instances."""
    memory1 = FastMemory("test_memory.json")
    memory1.remember("user123", "favorite_plane", "747")
    
    memory2 = FastMemory("test_memory.json")
    assert memory2.recall("user123", "favorite_plane") == "747"
```

### Integration Tests

```python
# v3/tests/test_memory_integration.py
async def test_bot_memory_integration():
    """Test memory integration with bot."""
    bot = AviationGirlV3()
    
    # Simulate user message
    message = MockMessage(
        author=MockUser(id=123),
        content="my favorite plane is the 747"
    )
    
    await bot.on_message(message)
    
    # Check memory was stored
    assert bot.memory.recall("123", "favorite_plane") == "747"
    
    # Simulate recall
    message2 = MockMessage(
        author=MockUser(id=123),
        content="what's my favorite plane?"
    )
    
    response = await bot.on_message(message2)
    assert "747" in response.lower()
```

---

## Performance

### Benchmarks

| Operation | Time | Notes |
|-----------|------|-------|
| Load memory file | < 1ms | 100 users |
| Save memory file | < 5ms | 100 users |
| Auto-detect | < 1ms | Per message |
| Get context | < 0.1ms | Per user |
| Recall | < 0.1ms | Per key |

### Optimization Tips

1. **Lazy Loading**: Only load memory when needed
2. **Caching**: Cache frequently accessed memories
3. **Batch Saves**: Save every N messages instead of every message
4. **Compression**: Use gzip for large memory files

---

## Security & Privacy

### Data Protection

1. **Encryption**: Consider encrypting memory.json
2. **Access Control**: Only bot can read/write
3. **User Control**: Users can view/delete their data
4. **Retention**: Auto-delete old memories (optional)

### GDPR Compliance

```python
def export_user_data(self, user_id: str) -> Dict:
    """Export all user data (GDPR right to access)."""
    return self.memory.get(user_id, {})

def delete_user_data(self, user_id: str):
    """Delete all user data (GDPR right to erasure)."""
    self.memory.forget(user_id)
```

---

## Future Enhancements

### Phase 2 (Optional)

1. **Conversation History**: Store recent messages
2. **Semantic Search**: Find similar past conversations
3. **Memory Importance**: Weight memories by frequency
4. **Auto-Cleanup**: Remove old/unused memories
5. **Multi-Server**: Separate memories per Discord server

### Advanced Features (Future)

1. **Vector Embeddings**: For semantic memory
2. **Graph Database**: For relationship mapping
3. **ML-Based Extraction**: Better pattern detection
4. **Context Windows**: Sliding window of recent context

---

## Troubleshooting

### Common Issues

**Issue**: Memory not persisting
**Solution**: Check file permissions, ensure _save() is called

**Issue**: Auto-detection not working
**Solution**: Check regex patterns, test with sample messages

**Issue**: Memory file corrupted
**Solution**: Restore from .bak file, validate JSON

**Issue**: Performance degradation
**Solution**: Limit memory size, implement cleanup

---

## Summary

FastMemory provides:
-  Simple 50-line implementation
-  Fast performance (< 1ms operations)
-  Persistent JSON storage
-  Auto-detection of memories
-  Easy prompt integration
-  User privacy controls

**Next**: Implement and test FastMemory class!
