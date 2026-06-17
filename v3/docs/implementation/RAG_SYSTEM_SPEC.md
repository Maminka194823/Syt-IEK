# RAG System Specification  

Retrieval-Augmented Generation system for accessing Wikipedia and external knowledge.

## Overview

RAG system enhances Aviation Girl v3 with real-time access to Wikipedia for:
- Up-to-date aviation information
- Aircraft specifications and history
- Airline information
- Airport details
- Technical aviation knowledge

### Design Goals
-  Simple Wikipedia API integration
-  Fast retrieval (< 500ms)
-  Relevant context extraction
-  Seamless prompt integration
-  Fallback to base knowledge

---

## Architecture

```
┌─────────────────────────────────────────┐
│           User Question                 │
│  "Tell me about the Boeing 787"        │
└──────────────┬──────────────────────────┘
               │
               ▼
┌─────────────────────────────────────────┐
│      Query Analyzer                     │
│  (Detect if needs external knowledge)   │
└──────────────┬──────────────────────────┘
               │
               ▼
┌─────────────────────────────────────────┐
│      Wikipedia Search                   │
│  (Search for "Boeing 787")              │
└──────────────┬──────────────────────────┘
               │
               ▼
┌─────────────────────────────────────────┐
│      Content Extraction                 │
│  (Get summary + key facts)              │
└──────────────┬──────────────────────────┘
               │
               ▼
┌─────────────────────────────────────────┐
│      Context Formatting                 │
│  (Format for prompt)                    │
└──────────────┬──────────────────────────┘
               │
               ▼
┌─────────────────────────────────────────┐
│      Build Prompt with RAG              │
│  "Context: ... | User: ... | Assistant:"│
└──────────────┬──────────────────────────┘
               │
               ▼
┌─────────────────────────────────────────┐
│      Generate Response                  │
│  (Using retrieved context)              │
└─────────────────────────────────────────┘
```

---

## Implementation

### Core RAG Class

```python
# v3/src/rag/wikipedia_rag.py
import requests
from typing import Optional, Dict, List
import re

class WikipediaRAG:
    """Simple RAG system using Wikipedia API."""
    
    BASE_URL = "https://en.wikipedia.org/w/api.php"
    
    def __init__(self, max_context_length: int = 500):
        """Initialize RAG system.
        
        Args:
            max_context_length: Maximum characters for context
        """
        self.max_context_length = max_context_length
        self.cache = {}  # Simple cache for repeated queries
    
    def should_use_rag(self, query: str) -> bool:
        """Determine if query needs external knowledge.
        
        Args:
            query: User's question
            
        Returns:
            True if RAG should be used
        """
        # Keywords that suggest need for external knowledge
        rag_triggers = [
            # Specific aircraft
            r'\b(boeing|airbus|cessna|bombardier)\s+\d+',
            r'\b(747|777|787|a320|a380|737)\b',
            
            # Airlines
            r'\b(lufthansa|emirates|united|delta|american)\b',
            
            # Airports
            r'\b([A-Z]{3})\s+airport\b',
            r'\bairport\s+in\b',
            
            # Factual questions
            r'\bwhen (was|did)\b',
            r'\bhow many\b',
            r'\bwhat year\b',
            r'\bspecifications?\b',
            r'\bhistory of\b',
            
            # Technical details
            r'\brange of\b',
            r'\bspeed of\b',
            r'\bcapacity of\b',
            r'\bengines? on\b',
        ]
        
        query_lower = query.lower()
        for pattern in rag_triggers:
            if re.search(pattern, query_lower):
                return True
        
        return False
    
    def search_wikipedia(self, query: str) -> Optional[str]:
        """Search Wikipedia and return page title.
        
        Args:
            query: Search query
            
        Returns:
            Page title or None if not found
        """
        # Check cache
        if query in self.cache:
            return self.cache[query]
        
        try:
            params = {
                "action": "opensearch",
                "search": query,
                "limit": 1,
                "namespace": 0,
                "format": "json"
            }
            
            response = requests.get(self.BASE_URL, params=params, timeout=2)
            response.raise_for_status()
            
            data = response.json()
            if data[1]:  # Has results
                title = data[1][0]
                self.cache[query] = title
                return title
            
        except Exception as e:
            print(f"Wikipedia search error: {e}")
        
        return None
    
    def get_page_content(self, title: str) -> Optional[Dict]:
        """Get Wikipedia page content.
        
        Args:
            title: Page title
            
        Returns:
            Dict with summary and extract
        """
        try:
            params = {
                "action": "query",
                "prop": "extracts",
                "exintro": True,
                "explaintext": True,
                "titles": title,
                "format": "json"
            }
            
            response = requests.get(self.BASE_URL, params=params, timeout=2)
            response.raise_for_status()
            
            data = response.json()
            pages = data["query"]["pages"]
            page = next(iter(pages.values()))
            
            if "extract" in page:
                extract = page["extract"]
                
                # Clean up extract
                extract = self._clean_extract(extract)
                
                # Truncate to max length
                if len(extract) > self.max_context_length:
                    extract = extract[:self.max_context_length] + "..."
                
                return {
                    "title": page["title"],
                    "extract": extract,
                    "url": f"https://en.wikipedia.org/wiki/{page['title'].replace(' ', '_')}"
                }
        
        except Exception as e:
            print(f"Wikipedia content error: {e}")
        
        return None
    
    def _clean_extract(self, text: str) -> str:
        """Clean Wikipedia extract.
        
        Args:
            text: Raw extract
            
        Returns:
            Cleaned text
        """
        # Remove multiple newlines
        text = re.sub(r'\n+', ' ', text)
        
        # Remove extra spaces
        text = re.sub(r'\s+', ' ', text)
        
        # Remove citations [1], [2], etc.
        text = re.sub(r'\[\d+\]', '', text)
        
        return text.strip()
    
    def extract_key_facts(self, text: str, query: str) -> List[str]:
        """Extract key facts relevant to query.
        
        Args:
            text: Wikipedia extract
            query: Original query
            
        Returns:
            List of key facts
        """
        # Split into sentences
        sentences = re.split(r'[.!?]+', text)
        
        # Extract query keywords
        query_words = set(query.lower().split())
        query_words.discard('the')
        query_words.discard('what')
        query_words.discard('how')
        query_words.discard('when')
        query_words.discard('where')
        
        # Score sentences by relevance
        scored_sentences = []
        for sentence in sentences:
            sentence = sentence.strip()
            if len(sentence) < 20:  # Skip very short sentences
                continue
            
            sentence_lower = sentence.lower()
            score = sum(1 for word in query_words if word in sentence_lower)
            
            if score > 0:
                scored_sentences.append((score, sentence))
        
        # Sort by score and take top 3
        scored_sentences.sort(reverse=True, key=lambda x: x[0])
        key_facts = [s[1] for s in scored_sentences[:3]]
        
        return key_facts
    
    def retrieve(self, query: str) -> Optional[Dict]:
        """Retrieve relevant context for query.
        
        Args:
            query: User's question
            
        Returns:
            Dict with context and metadata
        """
        # Check if RAG is needed
        if not self.should_use_rag(query):
            return None
        
        # Search Wikipedia
        title = self.search_wikipedia(query)
        if not title:
            return None
        
        # Get page content
        content = self.get_page_content(title)
        if not content:
            return None
        
        # Extract key facts
        key_facts = self.extract_key_facts(content["extract"], query)
        
        return {
            "title": content["title"],
            "extract": content["extract"],
            "key_facts": key_facts,
            "url": content["url"]
        }
    
    def format_context(self, rag_result: Dict) -> str:
        """Format RAG result for prompt.
        
        Args:
            rag_result: Result from retrieve()
            
        Returns:
            Formatted context string
        """
        if not rag_result:
            return ""
        
        context_parts = [
            f"Wikipedia: {rag_result['title']}",
        ]
        
        # Add key facts if available
        if rag_result.get("key_facts"):
            facts = " | ".join(rag_result["key_facts"][:2])  # Top 2 facts
            context_parts.append(facts)
        else:
            # Use extract
            extract = rag_result["extract"][:300]  # First 300 chars
            context_parts.append(extract)
        
        return " - ".join(context_parts)
```

---

## Integration with Bot

### Discord Bot Integration

```python
# v3/src/bot/discord_bot_v3.py
import discord
from memory.fast_memory import FastMemory
from rag.wikipedia_rag import WikipediaRAG

class AviationGirlV3(discord.Client):
    def __init__(self):
        super().__init__()
        self.memory = FastMemory("user_memory.json")
        self.rag = WikipediaRAG(max_context_length=500)
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
        
        # Try RAG retrieval
        rag_result = self.rag.retrieve(user_message)
        rag_context = self.rag.format_context(rag_result) if rag_result else ""
        
        # Build prompt with memory and RAG
        prompt_parts = []
        
        if memory_context:
            prompt_parts.append(f"Memory: {memory_context}")
        
        if rag_context:
            prompt_parts.append(f"Context: {rag_context}")
        
        prompt_parts.append(f"User: {user_message}")
        prompt_parts.append("Assistant:")
        
        prompt = "\n".join(prompt_parts)
        
        # Generate response
        response = await self.generate_response(prompt)
        
        # Add source citation if RAG was used
        if rag_result:
            response += f"\n\n*Source: [Wikipedia]({rag_result['url']})*"
        
        # Send response
        await message.channel.send(response)
```

### Prompt Format Examples

```python
# Without RAG or Memory
"User: what's the range of the 787?\nAssistant:"

# With Memory only
"Memory: Name: Alex | Favorite Plane: 747\nUser: what's the range of the 787?\nAssistant:"

# With RAG only
"Context: Wikipedia: Boeing 787 Dreamliner - The Boeing 787 has a range of 7,635 to 8,786 nautical miles depending on variant\nUser: what's the range of the 787?\nAssistant:"

# With Both Memory and RAG
"Memory: Name: Alex | Favorite Plane: 747\nContext: Wikipedia: Boeing 787 Dreamliner - The Boeing 787 has a range of 7,635 to 8,786 nautical miles depending on variant\nUser: what's the range of the 787?\nAssistant:"
```

---

## Query Detection Patterns

### When to Use RAG

```python
# Specific aircraft queries
"Tell me about the Boeing 787"  #   Use RAG
"What's the range of the A380?"  #   Use RAG
"How many engines does the 747 have?"  #   Use RAG

# Airline queries
"Tell me about Lufthansa"  #   Use RAG
"When was Emirates founded?"  #   Use RAG

# Airport queries
"What's the biggest airport in Germany?"  #   Use RAG
"Tell me about LAX airport"  #   Use RAG

# General conversation
"heya!"  #   No RAG needed
"how are you?"  #   No RAG needed
"what's your favorite plane?"  #   No RAG needed (personality)
```

---

## Caching Strategy

### Simple In-Memory Cache

```python
class WikipediaRAG:
    def __init__(self):
        self.cache = {}
        self.cache_hits = 0
        self.cache_misses = 0
    
    def retrieve(self, query: str):
        # Normalize query for cache key
        cache_key = query.lower().strip()
        
        if cache_key in self.cache:
            self.cache_hits += 1
            return self.cache[cache_key]
        
        self.cache_misses += 1
        result = self._fetch_from_wikipedia(query)
        
        if result:
            self.cache[cache_key] = result
        
        return result
    
    def get_cache_stats(self):
        total = self.cache_hits + self.cache_misses
        hit_rate = self.cache_hits / total if total > 0 else 0
        return {
            "hits": self.cache_hits,
            "misses": self.cache_misses,
            "hit_rate": f"{hit_rate:.2%}",
            "size": len(self.cache)
        }
```

### Persistent Cache (Optional)

```python
import json
from pathlib import Path

class PersistentCache:
    def __init__(self, cache_file="rag_cache.json"):
        self.cache_file = Path(cache_file)
        self.cache = self._load()
    
    def _load(self):
        if self.cache_file.exists():
            with open(self.cache_file, 'r') as f:
                return json.load(f)
        return {}
    
    def _save(self):
        with open(self.cache_file, 'w') as f:
            json.dump(self.cache, f, indent=2)
    
    def get(self, key):
        return self.cache.get(key)
    
    def set(self, key, value):
        self.cache[key] = value
        self._save()
```

---

## Performance Optimization

### Async Implementation

```python
import aiohttp
import asyncio

class AsyncWikipediaRAG:
    """Async version for better performance."""
    
    async def search_wikipedia(self, query: str):
        """Async Wikipedia search."""
        async with aiohttp.ClientSession() as session:
            params = {
                "action": "opensearch",
                "search": query,
                "limit": 1,
                "format": "json"
            }
            
            async with session.get(self.BASE_URL, params=params) as response:
                data = await response.json()
                if data[1]:
                    return data[1][0]
        
        return None
    
    async def retrieve(self, query: str):
        """Async retrieve."""
        if not self.should_use_rag(query):
            return None
        
        title = await self.search_wikipedia(query)
        if not title:
            return None
        
        content = await self.get_page_content(title)
        return content
```

---

## Testing

### Unit Tests

```python
# v3/tests/test_rag.py
import pytest
from rag.wikipedia_rag import WikipediaRAG

def test_should_use_rag():
    """Test RAG trigger detection."""
    rag = WikipediaRAG()
    
    # Should use RAG
    assert rag.should_use_rag("Tell me about the Boeing 787")
    assert rag.should_use_rag("What's the range of the A380?")
    assert rag.should_use_rag("When was Lufthansa founded?")
    
    # Should not use RAG
    assert not rag.should_use_rag("heya!")
    assert not rag.should_use_rag("how are you?")
    assert not rag.should_use_rag("what's your favorite plane?")

def test_wikipedia_search():
    """Test Wikipedia search."""
    rag = WikipediaRAG()
    
    title = rag.search_wikipedia("Boeing 787")
    assert title is not None
    assert "787" in title or "Dreamliner" in title

def test_retrieve():
    """Test full retrieval."""
    rag = WikipediaRAG()
    
    result = rag.retrieve("Tell me about the Boeing 787")
    assert result is not None
    assert "title" in result
    assert "extract" in result
    assert "url" in result

def test_format_context():
    """Test context formatting."""
    rag = WikipediaRAG()
    
    result = {
        "title": "Boeing 787 Dreamliner",
        "extract": "The Boeing 787 is a wide-body jet airliner...",
        "key_facts": ["Range: 7,635 to 8,786 nmi"],
        "url": "https://en.wikipedia.org/wiki/Boeing_787"
    }
    
    context = rag.format_context(result)
    assert "Boeing 787" in context
    assert len(context) < 600  # Should be concise
```

### Integration Tests

```python
async def test_bot_with_rag():
    """Test bot with RAG integration."""
    bot = AviationGirlV3()
    
    # Simulate message
    message = MockMessage(
        author=MockUser(id=123),
        content="Tell me about the Boeing 787"
    )
    
    response = await bot.on_message(message)
    
    # Should include Wikipedia info
    assert "787" in response.lower()
    assert "wikipedia" in response.lower()
```

---

## Configuration

### RAG Configuration

```python
# v3/config/rag_config.py

RAG_CONFIG = {
    # Enable/disable RAG
    "enabled": True,
    
    # Wikipedia API
    "api_url": "https://en.wikipedia.org/w/api.php",
    "timeout": 2,  # seconds
    
    # Context settings
    "max_context_length": 500,  # characters
    "max_key_facts": 3,
    
    # Caching
    "enable_cache": True,
    "cache_file": "rag_cache.json",
    "cache_ttl": 86400,  # 24 hours
    
    # Performance
    "use_async": True,
    "max_concurrent_requests": 5,
}
```

---

## Error Handling

### Graceful Fallback

```python
async def on_message(self, message):
    """Handle message with RAG fallback."""
    try:
        # Try RAG retrieval
        rag_result = await self.rag.retrieve(message.content)
        rag_context = self.rag.format_context(rag_result)
    except Exception as e:
        print(f"RAG error: {e}")
        rag_context = ""  # Fallback to no RAG
    
    # Continue with or without RAG
    prompt = self.build_prompt(message, rag_context)
    response = await self.generate(prompt)
    
    await message.channel.send(response)
```

---

## Advanced Features (Optional)

### 1. Multi-Source RAG

```python
class MultiSourceRAG:
    """RAG with multiple sources."""
    
    def __init__(self):
        self.wikipedia = WikipediaRAG()
        # Add more sources
        # self.aviation_db = AviationDatabaseRAG()
        # self.faa_docs = FAADocumentsRAG()
    
    async def retrieve(self, query):
        """Retrieve from multiple sources."""
        results = await asyncio.gather(
            self.wikipedia.retrieve(query),
            # self.aviation_db.retrieve(query),
            # self.faa_docs.retrieve(query),
        )
        
        # Combine results
        return self.combine_results(results)
```

### 2. Semantic Search

```python
from sentence_transformers import SentenceTransformer

class SemanticRAG:
    """RAG with semantic search."""
    
    def __init__(self):
        self.model = SentenceTransformer('all-MiniLM-L6-v2')
        self.wikipedia = WikipediaRAG()
    
    def find_relevant_sentences(self, query, text):
        """Find most relevant sentences using embeddings."""
        query_embedding = self.model.encode(query)
        
        sentences = text.split('.')
        sentence_embeddings = self.model.encode(sentences)
        
        # Calculate similarity
        similarities = cosine_similarity([query_embedding], sentence_embeddings)[0]
        
        # Get top 3 sentences
        top_indices = similarities.argsort()[-3:][::-1]
        return [sentences[i] for i in top_indices]
```

---

## Performance Benchmarks

| Operation | Time | Notes |
|-----------|------|-------|
| Wikipedia search | 100-300ms | Network dependent |
| Content retrieval | 200-500ms | Network dependent |
| Context formatting | < 1ms | Local processing |
| Cache hit | < 0.1ms | In-memory |
| Total (with cache) | < 1ms | Cached queries |
| Total (no cache) | 300-800ms | First-time queries |

