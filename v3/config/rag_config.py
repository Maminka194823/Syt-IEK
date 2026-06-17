"""RAG system configuration."""

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
    "use_async": False,  # Set to True for async implementation
    "max_concurrent_requests": 5,
}
