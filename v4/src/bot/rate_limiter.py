"""
V4 Rate Limiter and Abuse Prevention
Comprehensive rate limiting system for Discord API and user interactions
Implements queue management, abuse detection, and graceful degradation
"""

import asyncio
import logging
import time
from typing import Dict, Any, List, Optional, Tuple, Set
from datetime import datetime, timedelta
from collections import defaultdict, deque
from dataclasses import dataclass, field
from enum import Enum
import json
import hashlib


class LimitType(Enum):
    """Types of rate limits"""
    USER_MESSAGE = "user_message"
    USER_INTERACTION = "user_interaction"
    DISCORD_API = "discord_api"
    AI_PROCESSING = "ai_processing"
    EXTERNAL_API = "external_api"
    GLOBAL_SYSTEM = "global_system"


class AbuseType(Enum):
    """Types of abuse patterns"""
    SPAM_MESSAGES = "spam_messages"
    RAPID_INTERACTIONS = "rapid_interactions"
    EXCESSIVE_REQUESTS = "excessive_requests"
    DUPLICATE_CONTENT = "duplicate_content"
    RESOURCE_EXHAUSTION = "resource_exhaustion"


@dataclass
class RateLimit:
    """Rate limit configuration"""
    max_requests: int
    time_window: int  # seconds
    burst_allowance: int = 0  # additional requests allowed in burst
    cooldown_period: int = 0  # cooldown after limit exceeded


@dataclass
class RequestRecord:
    """Record of a request for rate limiting"""
    timestamp: float
    user_id: Optional[int] = None
    request_type: str = ""
    content_hash: Optional[str] = None
    metadata: Dict[str, Any] = field(default_factory=dict)


@dataclass
class AbusePattern:
    """Detected abuse pattern"""
    abuse_type: AbuseType
    user_id: int
    detected_at: datetime
    severity: float  # 0.0 to 1.0
    evidence: Dict[str, Any]
    action_taken: Optional[str] = None


@dataclass
class QueuedRequest:
    """Queued request for processing"""
    request_id: str
    user_id: int
    request_type: str
    payload: Dict[str, Any]
    priority: int = 0
    queued_at: float = field(default_factory=time.time)
    max_wait_time: float = 30.0  # seconds


class DiscordRateLimiter:
    """
    Discord API rate limiting handler with queue management
    Handles Discord's complex rate limiting rules
    """
    
    def __init__(self):
        # Discord rate limits (per bot)
        self.global_rate_limit = RateLimit(max_requests=50, time_window=1)  # 50/second global
        self.per_channel_limit = RateLimit(max_requests=5, time_window=5)   # 5/5s per channel
        self.per_guild_limit = RateLimit(max_requests=10, time_window=10)   # 10/10s per guild
        
        # Request tracking
        self.global_requests = deque()
        self.channel_requests = defaultdict(deque)  # channel_id -> deque
        self.guild_requests = defaultdict(deque)    # guild_id -> deque
        
        # Queue management
        self.request_queue = asyncio.Queue(maxsize=1000)
        self.processing_queue = True
        self.queue_processor_task = None
        
        # Retry logic
        self.retry_delays = [1, 2, 4, 8, 16]  # exponential backoff
        self.max_retries = 5
        
    async def acquire_discord_rate_limit(
        self, 
        channel_id: Optional[int] = None,
        guild_id: Optional[int] = None
    ) -> bool:
        """
        Acquire permission to make Discord API request
        Returns True if request can proceed, False if rate limited
        """
        now = time.time()
        
        # Check global rate limit
        if not self._check_rate_limit(self.global_requests, self.global_rate_limit, now):
            return False
        
        # Check per-channel rate limit
        if channel_id and not self._check_rate_limit(
            self.channel_requests[channel_id], self.per_channel_limit, now
        ):
            return False
        
        # Check per-guild rate limit
        if guild_id and not self._check_rate_limit(
            self.guild_requests[guild_id], self.per_guild_limit, now
        ):
            return False
        
        # Record the request
        self.global_requests.append(now)
        if channel_id:
            self.channel_requests[channel_id].append(now)
        if guild_id:
            self.guild_requests[guild_id].append(now)
        
        return True
    
    def _check_rate_limit(self, requests: deque, limit: RateLimit, now: float) -> bool:
        """Check if rate limit allows new request"""
        # Remove old requests outside time window
        cutoff = now - limit.time_window
        while requests and requests[0] < cutoff:
            requests.popleft()
        
        # Check if under limit
        return len(requests) < limit.max_requests
    
    async def queue_discord_request(
        self,
        request_func,
        *args,
        channel_id: Optional[int] = None,
        guild_id: Optional[int] = None,
        priority: int = 0,
        max_wait_time: float = 30.0,
        **kwargs
    ) -> Any:
        """
        Queue a Discord API request with rate limiting and retry logic
        """
        request_id = hashlib.md5(f"{time.time()}{id(request_func)}".encode()).hexdigest()
        
        queued_request = QueuedRequest(
            request_id=request_id,
            user_id=kwargs.get('user_id', 0),
            request_type=request_func.__name__,
            payload={
                'func': request_func,
                'args': args,
                'kwargs': kwargs,
                'channel_id': channel_id,
                'guild_id': guild_id
            },
            priority=priority,
            max_wait_time=max_wait_time
        )
        
        try:
            await asyncio.wait_for(
                self.request_queue.put(queued_request),
                timeout=max_wait_time
            )
            
            # Wait for processing (simplified - in real implementation would use futures)
            return await self._process_queued_request(queued_request)
            
        except asyncio.TimeoutError:
            logging.warning(f"Request {request_id} timed out in queue")
            raise Exception("Request timed out - system under high load")
    
    async def _process_queued_request(self, request: QueuedRequest) -> Any:
        """Process a queued request with rate limiting and retries"""
        payload = request.payload
        
        for attempt in range(self.max_retries):
            try:
                # Wait for rate limit clearance
                while not await self.acquire_discord_rate_limit(
                    payload.get('channel_id'),
                    payload.get('guild_id')
                ):
                    await asyncio.sleep(0.1)
                
                # Execute the request
                result = await payload['func'](*payload['args'], **payload['kwargs'])
                return result
                
            except Exception as e:
                error_msg = str(e).lower()
                
                # Handle Discord rate limit errors
                if "rate limit" in error_msg or "429" in error_msg:
                    retry_after = self._extract_retry_after(str(e))
                    await asyncio.sleep(retry_after)
                    continue
                
                # Handle other retryable errors
                if attempt < self.max_retries - 1 and self._is_retryable_error(e):
                    delay = self.retry_delays[min(attempt, len(self.retry_delays) - 1)]
                    await asyncio.sleep(delay)
                    continue
                
                # Non-retryable error or max retries reached
                logging.error(f"Request {request.request_id} failed after {attempt + 1} attempts: {e}")
                raise
        
        raise Exception(f"Request failed after {self.max_retries} attempts")
    
    def _extract_retry_after(self, error_message: str) -> float:
        """Extract retry-after value from Discord error message"""
        # Simplified extraction - Discord usually provides retry-after header
        # In real implementation, would parse the actual header
        return 1.0
    
    def _is_retryable_error(self, error: Exception) -> bool:
        """Determine if error is retryable"""
        error_msg = str(error).lower()
        retryable_errors = [
            "timeout", "connection", "network", "temporary", "server error", "503", "502", "500"
        ]
        return any(err in error_msg for err in retryable_errors)


class AbuseDetector:
    """
    Abuse detection and prevention system
    Monitors usage patterns and detects potential abuse
    """
    
    def __init__(self):
        # User activity tracking
        self.user_activity = defaultdict(list)  # user_id -> list of RequestRecord
        self.user_content_hashes = defaultdict(set)  # user_id -> set of content hashes
        self.global_activity = deque()  # global request tracking
        
        # Abuse detection thresholds
        self.spam_threshold = 10  # messages per minute
        self.interaction_threshold = 20  # interactions per minute
        self.duplicate_threshold = 5  # duplicate messages
        self.resource_threshold = 100  # requests per minute
        
        # Detected abuse patterns
        self.abuse_patterns = []
        self.blocked_users = set()
        self.warned_users = set()
        
        # Cleanup intervals
        self.cleanup_interval = 300  # 5 minutes
        self.last_cleanup = time.time()
        
    async def check_abuse(
        self,
        user_id: int,
        request_type: str,
        content: Optional[str] = None,
        metadata: Dict[str, Any] = None
    ) -> Tuple[bool, Optional[AbusePattern]]:
        """
        Check if request shows signs of abuse
        Returns (is_allowed, abuse_pattern)
        """
        now = time.time()
        
        # Check if user is already blocked
        if user_id in self.blocked_users:
            return False, None
        
        # Create request record
        content_hash = None
        if content:
            content_hash = hashlib.md5(content.encode()).hexdigest()
        
        record = RequestRecord(
            timestamp=now,
            user_id=user_id,
            request_type=request_type,
            content_hash=content_hash,
            metadata=metadata or {}
        )
        
        # Add to tracking
        self.user_activity[user_id].append(record)
        self.global_activity.append(record)
        
        if content_hash:
            self.user_content_hashes[user_id].add(content_hash)
        
        # Perform abuse checks
        abuse_pattern = await self._detect_abuse_patterns(user_id, record)
        
        if abuse_pattern:
            self.abuse_patterns.append(abuse_pattern)
            await self._handle_abuse(abuse_pattern)
            return False, abuse_pattern
        
        # Cleanup old data periodically
        if now - self.last_cleanup > self.cleanup_interval:
            await self._cleanup_old_data()
            self.last_cleanup = now
        
        return True, None
    
    async def _detect_abuse_patterns(
        self,
        user_id: int,
        record: RequestRecord
    ) -> Optional[AbusePattern]:
        """Detect various abuse patterns"""
        now = record.timestamp
        user_records = self.user_activity[user_id]
        
        # Check for spam messages
        recent_messages = [
            r for r in user_records 
            if now - r.timestamp < 60 and r.request_type == "message"
        ]
        
        if len(recent_messages) > self.spam_threshold:
            return AbusePattern(
                abuse_type=AbuseType.SPAM_MESSAGES,
                user_id=user_id,
                detected_at=datetime.utcnow(),
                severity=min(1.0, len(recent_messages) / (self.spam_threshold * 2)),
                evidence={
                    "message_count": len(recent_messages),
                    "time_window": 60,
                    "threshold": self.spam_threshold
                }
            )
        
        # Check for rapid interactions
        recent_interactions = [
            r for r in user_records 
            if now - r.timestamp < 60 and r.request_type == "interaction"
        ]
        
        if len(recent_interactions) > self.interaction_threshold:
            return AbusePattern(
                abuse_type=AbuseType.RAPID_INTERACTIONS,
                user_id=user_id,
                detected_at=datetime.utcnow(),
                severity=min(1.0, len(recent_interactions) / (self.interaction_threshold * 2)),
                evidence={
                    "interaction_count": len(recent_interactions),
                    "time_window": 60,
                    "threshold": self.interaction_threshold
                }
            )
        
        # Check for duplicate content
        if record.content_hash:
            duplicate_count = sum(
                1 for r in user_records[-20:]  # Check last 20 messages
                if r.content_hash == record.content_hash
            )
            
            if duplicate_count > self.duplicate_threshold:
                return AbusePattern(
                    abuse_type=AbuseType.DUPLICATE_CONTENT,
                    user_id=user_id,
                    detected_at=datetime.utcnow(),
                    severity=min(1.0, duplicate_count / (self.duplicate_threshold * 2)),
                    evidence={
                        "duplicate_count": duplicate_count,
                        "content_hash": record.content_hash,
                        "threshold": self.duplicate_threshold
                    }
                )
        
        # Check for resource exhaustion
        recent_requests = [
            r for r in user_records 
            if now - r.timestamp < 60
        ]
        
        if len(recent_requests) > self.resource_threshold:
            return AbusePattern(
                abuse_type=AbuseType.RESOURCE_EXHAUSTION,
                user_id=user_id,
                detected_at=datetime.utcnow(),
                severity=min(1.0, len(recent_requests) / (self.resource_threshold * 2)),
                evidence={
                    "request_count": len(recent_requests),
                    "time_window": 60,
                    "threshold": self.resource_threshold
                }
            )
        
        return None
    
    async def _handle_abuse(self, pattern: AbusePattern):
        """Handle detected abuse pattern"""
        user_id = pattern.user_id
        severity = pattern.severity
        
        if severity >= 0.8:  # High severity - block user
            self.blocked_users.add(user_id)
            pattern.action_taken = "blocked"
            logging.warning(f"User {user_id} blocked for {pattern.abuse_type.value} (severity: {severity:.2f})")
            
        elif severity >= 0.5:  # Medium severity - warn user
            self.warned_users.add(user_id)
            pattern.action_taken = "warned"
            logging.info(f"User {user_id} warned for {pattern.abuse_type.value} (severity: {severity:.2f})")
            
        else:  # Low severity - log only
            pattern.action_taken = "logged"
            logging.debug(f"User {user_id} flagged for {pattern.abuse_type.value} (severity: {severity:.2f})")
    
    async def _cleanup_old_data(self):
        """Clean up old tracking data"""
        now = time.time()
        cutoff = now - 3600  # Keep 1 hour of data
        
        # Clean user activity
        for user_id in list(self.user_activity.keys()):
            self.user_activity[user_id] = [
                r for r in self.user_activity[user_id] 
                if r.timestamp > cutoff
            ]
            if not self.user_activity[user_id]:
                del self.user_activity[user_id]
        
        # Clean global activity
        while self.global_activity and self.global_activity[0].timestamp < cutoff:
            self.global_activity.popleft()
        
        # Clean abuse patterns (keep for longer)
        pattern_cutoff = now - 86400  # Keep 24 hours
        self.abuse_patterns = [
            p for p in self.abuse_patterns 
            if p.detected_at.timestamp() > pattern_cutoff
        ]
        
        # Reset warnings after cooldown
        warning_cutoff = now - 1800  # 30 minute cooldown
        self.warned_users = {
            user_id for user_id in self.warned_users
            if any(
                r.timestamp > warning_cutoff 
                for r in self.user_activity.get(user_id, [])
            )
        }
    
    def is_user_blocked(self, user_id: int) -> bool:
        """Check if user is currently blocked"""
        return user_id in self.blocked_users
    
    def is_user_warned(self, user_id: int) -> bool:
        """Check if user has been warned"""
        return user_id in self.warned_users
    
    def get_abuse_stats(self) -> Dict[str, Any]:
        """Get abuse detection statistics"""
        return {
            "blocked_users": len(self.blocked_users),
            "warned_users": len(self.warned_users),
            "total_patterns": len(self.abuse_patterns),
            "patterns_by_type": {
                abuse_type.value: sum(
                    1 for p in self.abuse_patterns 
                    if p.abuse_type == abuse_type
                )
                for abuse_type in AbuseType
            },
            "active_users": len(self.user_activity),
            "global_requests_tracked": len(self.global_activity)
        }


class SystemRateLimiter:
    """
    Comprehensive system-wide rate limiting and abuse prevention
    Coordinates all rate limiting components
    """
    
    def __init__(self):
        # Component rate limiters
        self.discord_limiter = DiscordRateLimiter()
        self.abuse_detector = AbuseDetector()
        
        # User-specific rate limits
        self.user_limits = {
            LimitType.USER_MESSAGE: RateLimit(max_requests=30, time_window=60),      # 30 messages/minute
            LimitType.USER_INTERACTION: RateLimit(max_requests=60, time_window=60),  # 60 interactions/minute
            LimitType.AI_PROCESSING: RateLimit(max_requests=20, time_window=60),     # 20 AI requests/minute
        }
        
        # Global system limits
        self.system_limits = {
            LimitType.GLOBAL_SYSTEM: RateLimit(max_requests=1000, time_window=60),   # 1000 requests/minute total
            LimitType.EXTERNAL_API: RateLimit(max_requests=100, time_window=60),     # 100 external API calls/minute
        }
        
        # Request tracking
        self.user_requests = defaultdict(lambda: defaultdict(deque))  # user_id -> limit_type -> deque
        self.system_requests = defaultdict(deque)  # limit_type -> deque
        
        # Graceful degradation
        self.degradation_active = False
        self.degradation_level = 0  # 0-3, higher = more degraded
        self.system_load_threshold = 0.8
        
        # Monitoring
        self.stats = {
            "requests_processed": 0,
            "requests_blocked": 0,
            "abuse_detected": 0,
            "degradation_events": 0
        }
        
    async def check_rate_limit(
        self,
        user_id: int,
        limit_type: LimitType,
        content: Optional[str] = None,
        metadata: Dict[str, Any] = None
    ) -> Tuple[bool, Optional[str]]:
        """
        Check if request is allowed under rate limits and abuse detection
        Returns (is_allowed, reason_if_blocked)
        """
        now = time.time()
        
        # Check abuse detection first
        is_allowed, abuse_pattern = await self.abuse_detector.check_abuse(
            user_id, limit_type.value, content, metadata
        )
        
        if not is_allowed:
            self.stats["abuse_detected"] += 1
            return False, f"Request blocked due to {abuse_pattern.abuse_type.value if abuse_pattern else 'abuse detection'}"
        
        # Check user-specific rate limits
        if limit_type in self.user_limits:
            limit = self.user_limits[limit_type]
            user_requests = self.user_requests[user_id][limit_type]
            
            if not self._check_rate_limit(user_requests, limit, now):
                self.stats["requests_blocked"] += 1
                return False, f"User rate limit exceeded for {limit_type.value}"
            
            user_requests.append(now)
        
        # Check system-wide limits
        if limit_type in self.system_limits:
            limit = self.system_limits[limit_type]
            system_requests = self.system_requests[limit_type]
            
            if not self._check_rate_limit(system_requests, limit, now):
                self.stats["requests_blocked"] += 1
                return False, f"System rate limit exceeded for {limit_type.value}"
            
            system_requests.append(now)
        
        # Check global system limit
        global_limit = self.system_limits[LimitType.GLOBAL_SYSTEM]
        global_requests = self.system_requests[LimitType.GLOBAL_SYSTEM]
        
        if not self._check_rate_limit(global_requests, global_limit, now):
            await self._activate_graceful_degradation()
            self.stats["requests_blocked"] += 1
            return False, "System under high load - please try again later"
        
        global_requests.append(now)
        self.stats["requests_processed"] += 1
        
        return True, None
    
    def _check_rate_limit(self, requests: deque, limit: RateLimit, now: float) -> bool:
        """Check if rate limit allows new request"""
        cutoff = now - limit.time_window
        while requests and requests[0] < cutoff:
            requests.popleft()
        
        return len(requests) < limit.max_requests
    
    async def _activate_graceful_degradation(self):
        """Activate graceful degradation under high load"""
        if not self.degradation_active:
            self.degradation_active = True
            self.degradation_level = 1
            self.stats["degradation_events"] += 1
            logging.warning("Graceful degradation activated - system under high load")
            
            # Schedule degradation deactivation
            asyncio.create_task(self._deactivate_degradation_after_delay())
    
    async def _deactivate_degradation_after_delay(self):
        """Deactivate graceful degradation after delay"""
        await asyncio.sleep(60)  # 1 minute cooldown
        
        # Check if system load has decreased
        current_load = self._calculate_system_load()
        if current_load < self.system_load_threshold:
            self.degradation_active = False
            self.degradation_level = 0
            logging.info("Graceful degradation deactivated - system load normalized")
    
    def _calculate_system_load(self) -> float:
        """Calculate current system load (simplified)"""
        now = time.time()
        recent_requests = sum(
            len([r for r in requests if now - r < 60])
            for requests in self.system_requests.values()
        )
        
        max_capacity = sum(limit.max_requests for limit in self.system_limits.values())
        return recent_requests / max_capacity if max_capacity > 0 else 0.0
    
    def is_degradation_active(self) -> bool:
        """Check if graceful degradation is active"""
        return self.degradation_active
    
    def get_degradation_level(self) -> int:
        """Get current degradation level"""
        return self.degradation_level
    
    async def queue_discord_request(self, *args, **kwargs) -> Any:
        """Queue Discord API request with rate limiting"""
        return await self.discord_limiter.queue_discord_request(*args, **kwargs)
    
    def get_user_status(self, user_id: int) -> Dict[str, Any]:
        """Get user's current rate limiting status"""
        return {
            "is_blocked": self.abuse_detector.is_user_blocked(user_id),
            "is_warned": self.abuse_detector.is_user_warned(user_id),
            "request_counts": {
                limit_type.value: len(self.user_requests[user_id][limit_type])
                for limit_type in self.user_limits.keys()
            }
        }
    
    def get_system_stats(self) -> Dict[str, Any]:
        """Get comprehensive system statistics"""
        return {
            **self.stats,
            "degradation_active": self.degradation_active,
            "degradation_level": self.degradation_level,
            "system_load": self._calculate_system_load(),
            "abuse_stats": self.abuse_detector.get_abuse_stats(),
            "active_users": len(self.user_requests),
            "queue_size": self.discord_limiter.request_queue.qsize()
        }