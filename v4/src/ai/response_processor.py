"""
V4 Response Processor
AI output formatting and Discord message constraint handling
Manages multi-part responses and content cleaning
"""

import logging
import re
from typing import List, Dict, Any, Optional, Tuple
from datetime import datetime


class ResponseProcessor:
    """
    Processes and formats AI model outputs for Discord compatibility
    Handles message length constraints, content cleaning, and multi-part responses
    """
    
    def __init__(self):
        # Discord message constraints
        self.max_message_length = 2000
        self.max_embed_description = 4096
        self.max_embed_field_value = 1024
        self.safe_message_length = 1900  # Leave room for formatting
        
        # Content cleaning patterns
        self.cleanup_patterns = [
            # Remove AI artifacts
            (r'<\|im_start\|>', ''),
            (r'<\|im_end\|>', ''),
            (r'<\|endoftext\|>', ''),
            (r'\[INST\].*?\[/INST\]', ''),
            (r'Human:', ''),
            (r'Assistant:', ''),
            (r'User:', ''),
            (r'AI:', ''),
            
            # Clean up excessive whitespace
            (r'\n\s*\n\s*\n+', '\n\n'),  # Multiple newlines to double
            (r'[ \t]+', ' '),  # Multiple spaces/tabs to single space
            
            # Remove incomplete sentences at the end
            (r'\n[^.!?]*$', ''),  # Remove incomplete final line
        ]
        
        # Response splitting preferences
        self.split_preferences = [
            '\n\n',  # Double newlines (paragraph breaks)
            '\n',    # Single newlines
            '. ',    # Sentence endings
            ', ',    # Comma breaks
            ' '      # Word breaks (last resort)
        ]
    
    def clean_response(self, raw_response: str) -> str:
        """
        Clean AI response for Discord compatibility
        Removes artifacts and formats content appropriately
        """
        if not raw_response:
            return ""
        
        try:
            response = raw_response.strip()
            
            # Apply cleanup patterns
            for pattern, replacement in self.cleanup_patterns:
                response = re.sub(pattern, replacement, response, flags=re.IGNORECASE | re.MULTILINE)
            
            # Clean up whitespace
            response = response.strip()
            
            # Ensure reasonable length
            if len(response) > self.safe_message_length:
                response = self._truncate_response(response)
            
            # Validate content quality
            if not self._is_valid_response(response):
                return "I apologize, but I encountered an issue generating a proper response. Could you please rephrase your question?"
            
            return response
            
        except Exception as e:
            logging.error(f"Error cleaning response: {e}")
            return "I encountered an error processing my response. Please try again."
    
    def split_long_response(self, response: str) -> List[str]:
        """
        Split long responses into multiple Discord-compatible messages
        Preserves content structure and readability
        """
        if len(response) <= self.safe_message_length:
            return [response]
        
        try:
            parts = []
            remaining = response
            
            while remaining and len(remaining) > self.safe_message_length:
                # Find the best split point
                split_point = self._find_best_split_point(remaining, self.safe_message_length)
                
                if split_point == -1:
                    # Force split at safe length if no good split point found
                    split_point = self.safe_message_length
                
                # Extract the part
                part = remaining[:split_point].strip()
                if part:
                    parts.append(part)
                
                # Update remaining content
                remaining = remaining[split_point:].strip()
            
            # Add final part if any content remains
            if remaining:
                parts.append(remaining)
            
            # Ensure no empty parts
            parts = [part for part in parts if part.strip()]
            
            # Add continuation indicators
            if len(parts) > 1:
                for i in range(len(parts) - 1):
                    if not parts[i].endswith('...'):
                        parts[i] += '...'
                
                for i in range(1, len(parts)):
                    if not parts[i].startswith('...'):
                        parts[i] = '...' + parts[i]
            
            return parts
            
        except Exception as e:
            logging.error(f"Error splitting response: {e}")
            return [self.clean_response(response[:self.safe_message_length] + "...")]
    
    def format_for_embed(self, response: str) -> Dict[str, Any]:
        """
        Format response content for Discord embed display
        Returns structured embed data
        """
        try:
            # Check if response is suitable for embed formatting
            if len(response) <= self.max_embed_description:
                return {
                    "type": "simple",
                    "description": response,
                    "fields": []
                }
            
            # Try to structure content into fields
            structured_content = self._structure_content_for_embed(response)
            
            if structured_content:
                return structured_content
            
            # Fallback: truncate for simple embed
            truncated = response[:self.max_embed_description - 3] + "..."
            return {
                "type": "simple",
                "description": truncated,
                "fields": []
            }
            
        except Exception as e:
            logging.error(f"Error formatting for embed: {e}")
            return {
                "type": "simple",
                "description": response[:500] + "..." if len(response) > 500 else response,
                "fields": []
            }
    
    def _truncate_response(self, response: str) -> str:
        """
        Intelligently truncate response while preserving meaning
        """
        if len(response) <= self.safe_message_length:
            return response
        
        # Try to find a good truncation point
        truncation_point = self._find_best_split_point(response, self.safe_message_length - 3)
        
        if truncation_point == -1:
            truncation_point = self.safe_message_length - 3
        
        truncated = response[:truncation_point].strip()
        
        # Ensure we don't end mid-sentence
        if not truncated.endswith(('.', '!', '?')):
            # Find the last complete sentence
            last_sentence_end = max(
                truncated.rfind('.'),
                truncated.rfind('!'),
                truncated.rfind('?')
            )
            
            if last_sentence_end > len(truncated) * 0.7:  # If we don't lose too much
                truncated = truncated[:last_sentence_end + 1]
        
        return truncated + "..."
    
    def _find_best_split_point(self, text: str, max_length: int) -> int:
        """
        Find the best point to split text while preserving readability
        """
        if len(text) <= max_length:
            return len(text)
        
        # Try split preferences in order
        for separator in self.split_preferences:
            # Find the last occurrence of separator within max_length
            search_text = text[:max_length]
            split_point = search_text.rfind(separator)
            
            if split_point > max_length * 0.5:  # Don't split too early
                return split_point + len(separator)
        
        return -1  # No good split point found
    
    def _is_valid_response(self, response: str) -> bool:
        """
        Validate that response is appropriate and complete
        """
        if not response or len(response.strip()) < 10:
            return False
        
        # Check for common AI artifacts that indicate problems
        problematic_patterns = [
            r'^(Human|User|Assistant|AI):\s*$',
            r'^\s*$',
            r'^[^a-zA-Z]*$',  # Only punctuation/numbers
            r'I cannot|I can\'t.*provide.*response',
        ]
        
        for pattern in problematic_patterns:
            if re.search(pattern, response, re.IGNORECASE | re.MULTILINE):
                return False
        
        return True
    
    def _structure_content_for_embed(self, response: str) -> Optional[Dict[str, Any]]:
        """
        Attempt to structure long content into embed fields
        """
        try:
            # Look for natural sections (headers, lists, etc.)
            sections = self._identify_content_sections(response)
            
            if not sections:
                return None
            
            # Build embed structure
            embed_data = {
                "type": "structured",
                "description": "",
                "fields": []
            }
            
            total_length = 0
            
            for section in sections:
                title = section.get('title', 'Information')
                content = section.get('content', '')
                
                # Truncate field content if needed
                if len(content) > self.max_embed_field_value:
                    content = content[:self.max_embed_field_value - 3] + "..."
                
                # Check total embed length
                field_length = len(title) + len(content)
                if total_length + field_length > 5000:  # Discord embed limit
                    break
                
                embed_data["fields"].append({
                    "name": title,
                    "value": content,
                    "inline": len(content) < 200  # Short fields can be inline
                })
                
                total_length += field_length
            
            return embed_data if embed_data["fields"] else None
            
        except Exception as e:
            logging.error(f"Error structuring content for embed: {e}")
            return None
    
    def _identify_content_sections(self, response: str) -> List[Dict[str, str]]:
        """
        Identify natural sections in response content
        """
        sections = []
        
        # Look for markdown-style headers
        header_pattern = r'^(#{1,3})\s+(.+)$'
        lines = response.split('\n')
        
        current_section = None
        current_content = []
        
        for line in lines:
            header_match = re.match(header_pattern, line.strip())
            
            if header_match:
                # Save previous section
                if current_section:
                    sections.append({
                        'title': current_section,
                        'content': '\n'.join(current_content).strip()
                    })
                
                # Start new section
                current_section = header_match.group(2)
                current_content = []
            else:
                current_content.append(line)
        
        # Save final section
        if current_section:
            sections.append({
                'title': current_section,
                'content': '\n'.join(current_content).strip()
            })
        
        # If no headers found, try to split by topic changes
        if not sections:
            sections = self._split_by_topic_changes(response)
        
        return sections
    
    def _split_by_topic_changes(self, response: str) -> List[Dict[str, str]]:
        """
        Split content by apparent topic changes (paragraph breaks)
        """
        paragraphs = [p.strip() for p in response.split('\n\n') if p.strip()]
        
        if len(paragraphs) <= 1:
            return []
        
        sections = []
        for i, paragraph in enumerate(paragraphs):
            # Use first few words as title
            words = paragraph.split()[:4]
            title = ' '.join(words) + ('...' if len(words) == 4 else '')
            
            sections.append({
                'title': title,
                'content': paragraph
            })
            
            # Limit number of sections
            if len(sections) >= 5:
                break
        
        return sections
    
    def handle_discord_formatting(self, response: str) -> str:
        """
        Apply Discord-specific formatting improvements
        """
        try:
            # Convert markdown-style formatting to Discord formatting
            formatting_conversions = [
                # Bold
                (r'\*\*(.*?)\*\*', r'**\1**'),
                # Italic
                (r'\*(.*?)\*', r'*\1*'),
                # Code blocks
                (r'```(.*?)```', r'```\1```'),
                # Inline code
                (r'`(.*?)`', r'`\1`'),
            ]
            
            formatted = response
            for pattern, replacement in formatting_conversions:
                formatted = re.sub(pattern, replacement, formatted, flags=re.DOTALL)
            
            return formatted
            
        except Exception as e:
            logging.error(f"Error applying Discord formatting: {e}")
            return response
    
    def create_error_response(self, error_type: str, context: str = "") -> str:
        """
        Create user-friendly error responses
        """
        error_responses = {
            "processing_error": "I encountered an issue processing your request. Please try rephrasing your question.",
            "timeout_error": "I'm taking longer than usual to respond. Please try again in a moment.",
            "context_error": "I had trouble understanding the context of your question. Could you provide more details?",
            "knowledge_error": "I couldn't access the specific information you requested. Please try a different question.",
            "format_error": "I had trouble formatting my response properly. Let me try again with a simpler answer."
        }
        
        base_response = error_responses.get(error_type, "I encountered an unexpected issue. Please try again.")
        
        if context:
            return f"{base_response}\n\nContext: {context}"
        
        return base_response
    
    def get_processor_stats(self) -> Dict[str, Any]:
        """
        Get statistics about response processor configuration
        """
        return {
            "max_message_length": self.max_message_length,
            "safe_message_length": self.safe_message_length,
            "max_embed_description": self.max_embed_description,
            "max_embed_field_value": self.max_embed_field_value,
            "cleanup_patterns_count": len(self.cleanup_patterns),
            "split_preferences": self.split_preferences
        }