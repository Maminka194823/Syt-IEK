"""Simple memory system for user preferences and context."""
import json
import re
from pathlib import Path
from typing import Dict, Optional, List
from datetime import datetime

class FastMemory:
    """Simple memory system for user preferences and context."""
    
    # Detection patterns
    PATTERNS = {
        "favorite_plane": [
            r"my favorite plane is (?:the )?(.+?)(?:\.|!|$)",
            r"i love the (.+?)(?:\.|!|$)",
            r"(.+?) is my favorite(?:\.|!|$)",
        ],
        "name": [
            r"my name is (.+?)(?:\.|!|$)",
            r"i'm (.+?)(?:\.|!|$)",
            r"call me (.+?)(?:\.|!|$)",
        ],
        "travel_plans": [
            r"i'm flying to (.+?)(?:\.|!|$)",
            r"going to (.+?) (?:next|this)",
            r"traveling to (.+?)(?:\.|!|$)",
        ],
        "favorite_airline": [
            r"my favorite airline is (.+?)(?:\.|!|$)",
            r"i love flying (.+?)(?:\.|!|$)",
        ],
        "home_airport": [
            r"i fly out of (.+?)(?:\.|!|$)",
            r"my home airport is (.+?)(?:\.|!|$)",
        ]
    }
    
    def __init__(self, memory_file: str = "memory.json"):
        self.memory_file = Path(memory_file)
        self.memory: Dict[str, Dict] = self._load()
    
    def _load(self) -> Dict:
        """Load memory from JSON file."""
        if self.memory_file.exists():
            try:
                with open(self.memory_file, 'r', encoding='utf-8') as f:
                    return json.load(f)
            except json.JSONDecodeError:
                print(f"Warning: Could not load {self.memory_file}, starting fresh")
                return {}
        return {}
    
    def _save(self):
        """Save memory to JSON file."""
        try:
            with open(self.memory_file, 'w', encoding='utf-8') as f:
                json.dump(self.memory, f, indent=2, ensure_ascii=False)
        except Exception as e:
            print(f"Error saving memory: {e}")
    
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
        
        # Add relevant memories
        if "name" in user_memory:
            context_parts.append(f"Name: {user_memory['name']}")
        if "favorite_plane" in user_memory:
            context_parts.append(f"Fav plane: {user_memory['favorite_plane']}")
        if "favorite_airline" in user_memory:
            context_parts.append(f"Fav airline: {user_memory['favorite_airline']}")
        if "travel_plans" in user_memory:
            context_parts.append(f"Travel: {user_memory['travel_plans']}")
        if "home_airport" in user_memory:
            context_parts.append(f"Airport: {user_memory['home_airport']}")
        
        return " | ".join(context_parts) if context_parts else ""
    
    def auto_detect(self, user_id: str, message: str):
        """Automatically detect and store memories from message."""
        message_lower = message.lower()
        
        for key, patterns in self.PATTERNS.items():
            for pattern in patterns:
                match = re.search(pattern, message_lower, re.IGNORECASE)
                if match:
                    value = match.group(1).strip()
                    self.remember(user_id, key, value)
                    print(f"Remembered: {key} = {value}")
                    break
    
    def forget(self, user_id: str, key: Optional[str] = None):
        """Forget a specific memory or all memories for a user."""
        if key:
            self.memory.get(user_id, {}).pop(key, None)
        else:
            self.memory.pop(user_id, None)
        self._save()
    
    def get_all_memories(self, user_id: str) -> Dict:
        """Get all memories for a user."""
        return self.memory.get(user_id, {})
