"""Simple RAG system using Wikipedia API."""
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
        self.headers = {
            'User-Agent': 'AviationGirlBot/3.0 (Educational Project; Python/requests)'
        }
    
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
            
            response = requests.get(self.BASE_URL, params=params, headers=self.headers, timeout=2)
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
            
            response = requests.get(self.BASE_URL, params=params, headers=self.headers, timeout=2)
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
