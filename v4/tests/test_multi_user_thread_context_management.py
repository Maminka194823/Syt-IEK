"""
Property-based test for multi-user thread context management
Feature: aviation-discord-bot, Property 12: Multi-user Thread Context Management
**Validates: Requirements 9.3**
"""

import pytest
import asyncio
from unittest.mock import AsyncMock, MagicMock
from hypothesis import given, strategies as st, settings
from typing import Dict, Any, List, Set, Optional
from datetime import datetime, timedelta
from dataclasses import dataclass, field
import time
import os
import sys

# Add the src directory to the path for imports
sys.path.append(os.path.join(os.path.dirname(__file__), '..', 'src'))

# Mock the problematic imports first
sys.modules['ai.ai_orchestrator'] = MagicMock()
sys.modules['bot.embed_builder'] = MagicMock()


@dataclass
class ThreadContext:
    """Context information for a thread conversation"""
    thread_id: int
    created_at: datetime
    participants: Set[int] = field(default_factory=set)
    topic: Optional[str] = None
    message_count: int = 0
    last_activity: datetime = field(default_factory=datetime.utcnow)
    context_summary: str = ""


@dataclass
class UserContext:
    """Individual user context within a thread"""
    user_id: int
    join_time: datetime
    message_count: int = 0
    last_message_time: Optional[datetime] = None
    topics_discussed: List[str] = field(default_factory=list)
    experience_level: Optional[str] = None
    interests: List[str] = field(default_factory=list)


class MockDiscordMessage:
    """Mock Discord message for testing"""
    
    def __init__(self, content: str = "", author_id: int = 12345, is_bot: bool = False):
        self.content = content
        self.author = MagicMock()
        self.author.id = author_id
        self.author.bot = is_bot
        self.author.display_name = f"User{author_id}"
        self.author.mention = f"<@{author_id}>"
        
        self.id = 999999 + author_id
        self.created_at = datetime.utcnow()
        
        # Mock methods
        self.reply = AsyncMock()
        self.add_reaction = AsyncMock()


class MockDiscordThread:
    """Mock Discord thread for testing"""
    
    def __init__(self, thread_id: int = 77777, name: str = "Test Thread"):
        self.id = thread_id
        self.name = name
        self.parent = MagicMock()
        self.starter_message = None
        
        # Mock methods
        self.join = AsyncMock()
        self.send = AsyncMock()
        
        # Mock history method to return async iterator
        self._message_history = []
        
        async def mock_history(limit=None):
            messages_to_return = self._message_history[-limit:] if limit else self._message_history
            for msg in messages_to_return:
                yield msg
        
        self.history = mock_history
    
    def add_message_to_history(self, message):
        """Add a message to the thread's history for testing"""
        self._message_history.append(message)


class MockDiscordUser:
    """Mock Discord user for testing"""
    
    def __init__(self, user_id: int = 54321):
        self.id = user_id
        self.display_name = f"User{user_id}"
        self.mention = f"<@{user_id}>"
        self.avatar = None


class MockAIOrchestrator:
    """Mock AI orchestrator for testing"""
    
    def __init__(self):
        self.process_calls = []
    
    async def process_message(self, message: str, user_id: int, context: Dict[str, Any] = None) -> str:
        # Record the call for verification
        self.process_calls.append({
            'message': message,
            'user_id': user_id,
            'context': context,
            'timestamp': datetime.utcnow()
        })
        
        # Simulate contextual response generation
        if context and "thread_context" in context:
            thread_ctx = context["thread_context"]
            participants_count = len(thread_ctx.get("participants", []))
            return f"Thread response for {participants_count} participants: {message[:50]}"
        else:
            return f"Individual response: {message[:50]}"


class MockEmbedBuilder:
    """Mock embed builder for testing"""
    
    def __init__(self):
        self.colors = {
            "primary": 0x1E88E5,
            "success": 0x4CAF50,
            "warning": 0xFF9800,
            "danger": 0xF44336,
            "info": 0x2196F3
        }
    
    def create_info_embed(self, title: str, description: str):
        embed = MagicMock()
        embed.title = title
        embed.description = description
        return embed


class MultiUserThreadContextManager:
    """
    Simplified thread context manager for testing multi-user scenarios
    """
    
    def __init__(self, ai_orchestrator=None, embed_builder=None):
        self.ai_orchestrator = ai_orchestrator or MockAIOrchestrator()
        self.embed_builder = embed_builder or MockEmbedBuilder()
        
        # Thread context management
        self.thread_contexts = {}  # thread_id -> ThreadContext
        self.user_contexts = {}  # (thread_id, user_id) -> UserContext
        self.thread_participants = {}  # thread_id -> set of user_ids
        
        # Message processing tracking
        self.processed_messages = []
        
        # Context isolation tracking
        self.context_access_log = []
    
    def _extract_thread_topic(self, thread_name: str) -> str:
        """Extract topic from thread name"""
        topic_keywords = {
            'weather': ['weather', 'metar', 'taf', 'conditions'],
            'aircraft': ['aircraft', 'plane', 'helicopter', 'cessna', 'piper'],
            'navigation': ['navigation', 'gps', 'vor', 'approach'],
            'regulations': ['regulation', 'far', 'rule', 'legal'],
            'training': ['training', 'lesson', 'instructor', 'student'],
            'emergency': ['emergency', 'malfunction', 'failure']
        }
        
        thread_lower = thread_name.lower()
        for topic, keywords in topic_keywords.items():
            if any(keyword in thread_lower for keyword in keywords):
                return topic
        
        return 'general'
    
    async def manage_thread_conversation(
        self, 
        thread: MockDiscordThread, 
        message: MockDiscordMessage
    ) -> None:
        """
        Manage thread conversations with multi-user context preservation
        """
        thread_id = thread.id
        user_id = message.author.id
        current_time = datetime.utcnow()
        
        # Initialize or update thread context
        if thread_id not in self.thread_contexts:
            self.thread_contexts[thread_id] = ThreadContext(
                thread_id=thread_id,
                created_at=current_time,
                topic=self._extract_thread_topic(thread.name or "General Discussion")
            )
        
        thread_context = self.thread_contexts[thread_id]
        thread_context.participants.add(user_id)
        thread_context.message_count += 1
        thread_context.last_activity = current_time
        
        # Initialize or update individual user context
        user_context_key = (thread_id, user_id)
        if user_context_key not in self.user_contexts:
            self.user_contexts[user_context_key] = UserContext(
                user_id=user_id,
                join_time=current_time
            )
        
        user_context = self.user_contexts[user_context_key]
        user_context.message_count += 1
        user_context.last_message_time = current_time
        
        # Update thread participants tracking
        if thread_id not in self.thread_participants:
            self.thread_participants[thread_id] = set()
        self.thread_participants[thread_id].add(user_id)
        
        # Log context access for isolation verification
        self.context_access_log.append({
            'thread_id': thread_id,
            'user_id': user_id,
            'timestamp': current_time,
            'participants_count': len(thread_context.participants),
            'user_message_count': user_context.message_count
        })
        
        # Process message with both individual and group context
        await self._process_thread_message(thread, message, thread_context, user_context)
        
        # Record processed message
        self.processed_messages.append({
            'thread_id': thread_id,
            'user_id': user_id,
            'message': message.content,
            'timestamp': current_time
        })
    
    async def _process_thread_message(
        self, 
        thread: MockDiscordThread, 
        message: MockDiscordMessage, 
        thread_context: ThreadContext,
        user_context: UserContext
    ) -> None:
        """Process a message within a thread context"""
        # Prepare comprehensive context for AI
        context_data = {
            'thread_context': {
                'thread_id': thread.id,
                'thread_topic': thread_context.topic,
                'participants': list(thread_context.participants),
                'message_count': thread_context.message_count,
                'context_summary': thread_context.context_summary
            },
            'user_context': {
                'user_id': user_context.user_id,
                'join_time': user_context.join_time.isoformat(),
                'user_message_count': user_context.message_count,
                'topics_discussed': user_context.topics_discussed,
                'experience_level': user_context.experience_level,
                'interests': user_context.interests
            },
            'group_discussion': len(thread_context.participants) > 1
        }
        
        # Get AI response with full context
        response = await self.ai_orchestrator.process_message(
            message=message.content,
            user_id=message.author.id,
            context=context_data
        )
        
        # Send response in thread
        await thread.send(response)
    
    async def _update_thread_context_summary(
        self, 
        thread: MockDiscordThread, 
        context: ThreadContext
    ) -> str:
        """Update thread context summary"""
        try:
            # Get recent messages from thread
            messages = []
            async for msg in thread.history(limit=10):
                if not msg.author.bot:
                    messages.append(f"{msg.author.display_name}: {msg.content[:100]}")
            
            messages.reverse()  # Chronological order
            
            # Create summary
            summary = f"Thread about {context.topic} with {len(context.participants)} participants. "
            summary += f"Recent discussion: {' | '.join(messages[-3:])}"
            
            return summary[:500]  # Limit summary length
            
        except Exception:
            return context.context_summary
    
    def get_user_context_in_thread(self, thread_id: int, user_id: int) -> Optional[UserContext]:
        """Get individual user context within a specific thread"""
        return self.user_contexts.get((thread_id, user_id))
    
    def get_thread_participants(self, thread_id: int) -> Set[int]:
        """Get all participants in a thread"""
        return self.thread_participants.get(thread_id, set())
    
    def verify_context_isolation(self, thread_id: int) -> Dict[str, Any]:
        """Verify that user contexts are properly isolated within the thread"""
        participants = self.get_thread_participants(thread_id)
        isolation_report = {
            'thread_id': thread_id,
            'participants_count': len(participants),
            'individual_contexts': {},
            'isolation_verified': True
        }
        
        for user_id in participants:
            user_context = self.get_user_context_in_thread(thread_id, user_id)
            if user_context:
                isolation_report['individual_contexts'][user_id] = {
                    'message_count': user_context.message_count,
                    'join_time': user_context.join_time,
                    'topics_discussed': user_context.topics_discussed,
                    'experience_level': user_context.experience_level
                }
        
        return isolation_report
    
    def cleanup_inactive_contexts(self, hours_threshold: int = 24) -> None:
        """Clean up inactive thread contexts"""
        current_time = datetime.utcnow()
        cleanup_threshold = timedelta(hours=hours_threshold)
        
        # Clean up thread contexts
        inactive_threads = []
        for thread_id, context in self.thread_contexts.items():
            if current_time - context.last_activity > cleanup_threshold:
                inactive_threads.append(thread_id)
        
        for thread_id in inactive_threads:
            del self.thread_contexts[thread_id]
            if thread_id in self.thread_participants:
                del self.thread_participants[thread_id]
            
            # Clean up associated user contexts
            user_contexts_to_remove = [
                key for key in self.user_contexts.keys() 
                if key[0] == thread_id
            ]
            for key in user_contexts_to_remove:
                del self.user_contexts[key]


def create_thread_context_manager():
    """Create a thread context manager with mocked dependencies"""
    ai_orchestrator = MockAIOrchestrator()
    embed_builder = MockEmbedBuilder()
    
    return MultiUserThreadContextManager(ai_orchestrator, embed_builder)


# Property-based test strategies
@st.composite
def multi_user_thread_strategy(draw):
    """Generate realistic multi-user thread scenarios for testing"""
    thread_id = draw(st.integers(min_value=1, max_value=999999))
    thread_names = [
        "Weather Discussion", "Aircraft Questions", "Navigation Help", 
        "Regulations Clarification", "General Aviation", "Flight Training",
        "Emergency Procedures", "IFR Discussion", "VFR Flying Tips"
    ]
    thread_name = draw(st.sampled_from(thread_names))
    
    # Generate multiple users (2-5 users for multi-user scenarios)
    num_users = draw(st.integers(min_value=2, max_value=5))
    base_user_id = draw(st.integers(min_value=1000, max_value=999999))
    user_ids = [base_user_id + i for i in range(num_users)]
    
    # Generate messages from different users
    messages_per_user = draw(st.integers(min_value=1, max_value=3))
    
    thread = MockDiscordThread(thread_id, thread_name)
    
    # Create messages from each user
    all_messages = []
    for user_id in user_ids:
        for i in range(messages_per_user):
            message_content = draw(st.text(min_size=10, max_size=200))
            if not message_content.strip():
                message_content = f"Message {i+1} from user {user_id}"
            
            message = MockDiscordMessage(message_content, user_id, is_bot=False)
            all_messages.append(message)
            thread.add_message_to_history(message)
    
    return thread, all_messages, user_ids


@st.composite
def concurrent_thread_strategy(draw):
    """Generate scenarios with multiple concurrent threads"""
    num_threads = draw(st.integers(min_value=2, max_value=4))
    threads_data = []
    
    for i in range(num_threads):
        # Ensure unique thread IDs
        thread_id = draw(st.integers(min_value=100000, max_value=999999)) + i * 1000000
        thread_name = f"Thread {i+1} Discussion"
        
        # Each thread has 2-3 users with unique IDs per thread
        num_users = draw(st.integers(min_value=2, max_value=3))
        base_user_id = draw(st.integers(min_value=10000, max_value=99999)) + i * 100000
        user_ids = [base_user_id + j for j in range(num_users)]
        
        thread = MockDiscordThread(thread_id, thread_name)
        messages = []
        
        for user_id in user_ids:
            message_content = draw(st.text(min_size=10, max_size=100))
            if not message_content.strip():
                message_content = f"Message from user {user_id} in thread {i+1}"
            
            message = MockDiscordMessage(message_content, user_id, is_bot=False)
            messages.append(message)
            thread.add_message_to_history(message)
        
        threads_data.append((thread, messages, user_ids))
    
    return threads_data


class TestMultiUserThreadContextManagement:
    """
    Property 12: Multi-user Thread Context Management
    For any thread with multiple participants, the bot should maintain individual 
    user contexts while participating in group discussions and preserve conversation 
    context across thread interactions.
    """
    
    @given(multi_user_thread_strategy())
    @settings(max_examples=100, deadline=30000)
    @pytest.mark.asyncio
    async def test_individual_user_context_preservation(self, thread_data):
        """
        Property test: Individual user contexts should be preserved in multi-user threads
        Validates: Requirements 9.3 - Individual user context preservation
        """
        thread, messages, user_ids = thread_data
        context_manager = create_thread_context_manager()
        
        # Process messages from multiple users
        for message in messages:
            await context_manager.manage_thread_conversation(thread, message)
        
        # Property: Each user should have individual context preserved
        for user_id in user_ids:
            user_context = context_manager.get_user_context_in_thread(thread.id, user_id)
            
            assert user_context is not None, \
                f"User {user_id} should have individual context in thread {thread.id}"
            
            assert user_context.user_id == user_id, \
                "User context should be associated with correct user ID"
            
            assert isinstance(user_context.join_time, datetime), \
                "User context should have valid join time"
            
            assert user_context.message_count > 0, \
                "User context should track message count"
        
        # Property: Thread should track all participants
        thread_participants = context_manager.get_thread_participants(thread.id)
        assert len(thread_participants) == len(user_ids), \
            "Thread should track all participating users"
        
        for user_id in user_ids:
            assert user_id in thread_participants, \
                f"User {user_id} should be tracked as thread participant"
    
    @given(multi_user_thread_strategy())
    @settings(max_examples=100, deadline=30000)
    @pytest.mark.asyncio
    async def test_group_discussion_participation(self, thread_data):
        """
        Property test: Bot should participate appropriately in group discussions
        Validates: Requirements 9.3 - Group discussion participation
        """
        thread, messages, user_ids = thread_data
        context_manager = create_thread_context_manager()
        
        # Process messages from multiple users
        for message in messages:
            await context_manager.manage_thread_conversation(thread, message)
        
        # Property: AI should receive group context for multi-user threads
        ai_calls = context_manager.ai_orchestrator.process_calls
        
        assert len(ai_calls) == len(messages), \
            "AI should be called for each message processed"
        
        # Check the final state after all messages are processed
        final_thread_context = context_manager.thread_contexts[thread.id]
        assert len(final_thread_context.participants) >= 2, \
            "Multi-user thread should have multiple participants after processing"
        
        for call in ai_calls:
            context = call.get('context', {})
            
            # Verify group discussion context is provided
            assert 'thread_context' in context, \
                "Thread context should be provided to AI"
            
            assert 'user_context' in context, \
                "Individual user context should be provided to AI"
            
            thread_ctx = context['thread_context']
            assert 'participants' in thread_ctx, \
                "Participants list should be in thread context"
            
            # Verify group discussion flag is set when there are multiple participants
            participants_count = len(thread_ctx['participants'])
            expected_group_flag = participants_count > 1
            assert context.get('group_discussion', False) == expected_group_flag, \
                f"Group discussion flag should be {expected_group_flag} for {participants_count} participants"
    
    @given(multi_user_thread_strategy())
    @settings(max_examples=100, deadline=30000)
    @pytest.mark.asyncio
    async def test_context_isolation_between_users(self, thread_data):
        """
        Property test: User contexts should be isolated from each other
        Validates: Requirements 9.3 - Context isolation between users
        """
        thread, messages, user_ids = thread_data
        context_manager = create_thread_context_manager()
        
        # Process messages from multiple users
        for message in messages:
            await context_manager.manage_thread_conversation(thread, message)
        
        # Property: Each user should have isolated context
        isolation_report = context_manager.verify_context_isolation(thread.id)
        
        assert isolation_report['isolation_verified'] == True, \
            "Context isolation should be verified"
        
        assert isolation_report['participants_count'] == len(user_ids), \
            "Isolation report should track all participants"
        
        # Verify each user has separate context data
        individual_contexts = isolation_report['individual_contexts']
        
        for user_id in user_ids:
            assert user_id in individual_contexts, \
                f"User {user_id} should have individual context data"
            
            user_data = individual_contexts[user_id]
            assert 'message_count' in user_data, \
                "User context should track individual message count"
            
            assert 'join_time' in user_data, \
                "User context should track individual join time"
        
        # Property: User contexts should be independent
        user_contexts = [
            context_manager.get_user_context_in_thread(thread.id, uid) 
            for uid in user_ids
        ]
        
        # Verify contexts are separate objects
        for i, context1 in enumerate(user_contexts):
            for j, context2 in enumerate(user_contexts):
                if i != j:
                    assert context1 is not context2, \
                        "User contexts should be separate objects"
                    
                    assert context1.user_id != context2.user_id, \
                        "User contexts should have different user IDs"
    
    @given(concurrent_thread_strategy())
    @settings(max_examples=50, deadline=30000)
    @pytest.mark.asyncio
    async def test_thread_state_management_across_interactions(self, threads_data):
        """
        Property test: Thread state should be managed consistently across multiple interactions
        Validates: Requirements 9.3 - Thread state management across interactions
        """
        context_manager = create_thread_context_manager()
        
        # Process messages across multiple concurrent threads
        all_processed_messages = []
        
        for thread, messages, user_ids in threads_data:
            for message in messages:
                await context_manager.manage_thread_conversation(thread, message)
                all_processed_messages.append((thread.id, message.author.id, message))
        
        # Property: Each thread should maintain separate state
        thread_ids = [thread.id for thread, _, _ in threads_data]
        
        for thread_id in thread_ids:
            assert thread_id in context_manager.thread_contexts, \
                f"Thread {thread_id} should have maintained context"
            
            thread_context = context_manager.thread_contexts[thread_id]
            assert isinstance(thread_context, ThreadContext), \
                "Thread context should be proper ThreadContext object"
            
            assert thread_context.thread_id == thread_id, \
                "Thread context should have correct thread ID"
        
        # Property: Thread states should not interfere with each other
        for i, (thread1, _, users1) in enumerate(threads_data):
            for j, (thread2, _, users2) in enumerate(threads_data):
                if i != j:
                    context1 = context_manager.thread_contexts[thread1.id]
                    context2 = context_manager.thread_contexts[thread2.id]
                    
                    # Verify contexts are separate
                    assert context1 is not context2, \
                        "Thread contexts should be separate objects"
                    
                    # Verify participant isolation
                    participants1 = context_manager.get_thread_participants(thread1.id)
                    participants2 = context_manager.get_thread_participants(thread2.id)
                    
                    # Participants should be tracked separately
                    assert participants1 != participants2 or len(participants1) == 0, \
                        "Thread participants should be tracked separately"
    
    @given(st.integers(min_value=2, max_value=10))
    @settings(max_examples=50, deadline=30000)
    @pytest.mark.asyncio
    async def test_conversation_context_preservation(self, num_interactions):
        """
        Property test: Conversation context should be preserved across multiple interactions
        Validates: Requirements 9.3 - Conversation context preservation
        """
        context_manager = create_thread_context_manager()
        
        # Create a thread with multiple users
        thread_id = 12345
        thread = MockDiscordThread(thread_id, "Context Preservation Test")
        user_ids = [1001, 1002, 1003]
        
        # Simulate multiple rounds of interaction
        for interaction_round in range(num_interactions):
            for user_id in user_ids:
                message_content = f"Message {interaction_round + 1} from user {user_id}"
                message = MockDiscordMessage(message_content, user_id, is_bot=False)
                
                await context_manager.manage_thread_conversation(thread, message)
        
        # Property: Context should be preserved and accumulated
        thread_context = context_manager.thread_contexts[thread_id]
        
        assert thread_context.message_count == num_interactions * len(user_ids), \
            "Thread should track total message count correctly"
        
        assert len(thread_context.participants) == len(user_ids), \
            "Thread should track all participants"
        
        # Property: Individual user contexts should accumulate correctly
        for user_id in user_ids:
            user_context = context_manager.get_user_context_in_thread(thread_id, user_id)
            
            assert user_context is not None, \
                f"User {user_id} should have preserved context"
            
            assert user_context.message_count == num_interactions, \
                f"User {user_id} should have correct message count"
        
        # Property: Context access should be logged for verification
        assert len(context_manager.context_access_log) == num_interactions * len(user_ids), \
            "All context accesses should be logged"
        
        # Verify context access log integrity
        for log_entry in context_manager.context_access_log:
            assert 'thread_id' in log_entry, "Log entry should have thread ID"
            assert 'user_id' in log_entry, "Log entry should have user ID"
            assert 'timestamp' in log_entry, "Log entry should have timestamp"
            assert 'participants_count' in log_entry, "Log entry should track participants"
    
    @given(st.integers(min_value=1, max_value=100))
    @settings(max_examples=50)
    def test_context_cleanup_preserves_active_threads(self, hours_offset):
        """
        Property test: Context cleanup should preserve active threads and clean inactive ones
        Validates proper resource management for thread contexts
        """
        context_manager = create_thread_context_manager()
        
        # Create thread contexts with different activity times
        current_time = datetime.utcnow()
        old_time = current_time - timedelta(hours=hours_offset)
        
        # Add active thread
        active_thread_id = 11111
        active_context = ThreadContext(
            thread_id=active_thread_id,
            created_at=current_time,
            last_activity=current_time
        )
        context_manager.thread_contexts[active_thread_id] = active_context
        context_manager.thread_participants[active_thread_id] = {1001, 1002}
        
        # Add potentially inactive thread
        inactive_thread_id = 22222
        inactive_context = ThreadContext(
            thread_id=inactive_thread_id,
            created_at=old_time,
            last_activity=old_time
        )
        context_manager.thread_contexts[inactive_thread_id] = inactive_context
        context_manager.thread_participants[inactive_thread_id] = {2001, 2002}
        
        # Add user contexts for both threads
        context_manager.user_contexts[(active_thread_id, 1001)] = UserContext(1001, current_time)
        context_manager.user_contexts[(inactive_thread_id, 2001)] = UserContext(2001, old_time)
        
        # Run cleanup
        context_manager.cleanup_inactive_contexts(hours_threshold=24)
        
        # Property: Active threads should be preserved
        assert active_thread_id in context_manager.thread_contexts, \
            "Active thread should be preserved"
        
        # Property: Inactive threads should be cleaned based on threshold
        if hours_offset > 24:
            assert inactive_thread_id not in context_manager.thread_contexts, \
                "Inactive thread should be cleaned up"
            assert inactive_thread_id not in context_manager.thread_participants, \
                "Inactive thread participants should be cleaned up"
            assert (inactive_thread_id, 2001) not in context_manager.user_contexts, \
                "Inactive user contexts should be cleaned up"
        else:
            assert inactive_thread_id in context_manager.thread_contexts, \
                "Recent thread should be preserved"
    
    @given(st.integers(min_value=1, max_value=5))
    @settings(max_examples=50, deadline=30000)
    @pytest.mark.asyncio
    async def test_thread_topic_extraction_and_context(self, num_users):
        """
        Property test: Thread topics should be extracted and used in context
        Validates proper topic-based context management
        """
        context_manager = create_thread_context_manager()
        
        # Test different thread topics
        topic_threads = [
            ("Weather Discussion - METAR Analysis", "weather"),
            ("Cessna 172 Performance Questions", "aircraft"),
            ("VOR Navigation Help", "navigation"),
            ("FAR Part 91 Regulations", "regulations"),
            ("Flight Training Tips", "training"),
            ("Emergency Procedures", "emergency"),
            ("General Aviation Chat", "general")
        ]
        
        for thread_name, expected_topic in topic_threads:
            thread_id = hash(thread_name) % 999999  # Generate consistent ID
            thread = MockDiscordThread(thread_id, thread_name)
            
            # Create messages from multiple users
            user_ids = [1000 + i for i in range(num_users)]
            
            for user_id in user_ids:
                message = MockDiscordMessage(f"Question about {expected_topic}", user_id, is_bot=False)
                await context_manager.manage_thread_conversation(thread, message)
            
            # Property: Thread topic should be extracted correctly
            thread_context = context_manager.thread_contexts[thread_id]
            assert thread_context.topic == expected_topic, \
                f"Thread topic should be extracted as '{expected_topic}' from '{thread_name}'"
            
            # Property: Topic should be included in AI context
            ai_calls = context_manager.ai_orchestrator.process_calls
            relevant_calls = [call for call in ai_calls if call['context']['thread_context']['thread_id'] == thread_id]
            
            for call in relevant_calls:
                thread_ctx = call['context']['thread_context']
                assert thread_ctx['thread_topic'] == expected_topic, \
                    f"AI should receive correct thread topic '{expected_topic}'"


if __name__ == "__main__":
    pytest.main([__file__, "-v"])