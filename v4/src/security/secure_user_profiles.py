"""
V4 Secure User Profile Manager
Enhanced user profile management with encryption and privacy compliance
"""

import json
import os
import asyncio
from typing import Dict, Any, Optional, List
from datetime import datetime, timedelta
import logging
import hashlib

from .encryption_manager import EncryptionManager
from .privacy_manager import PrivacyManager, DataCategory
from .secure_storage import SecureStorage

class SecureUserProfileManager:
    """
    Secure user profile manager with encryption, privacy compliance, and data deletion
    Integrates with privacy manager for GDPR-like compliance
    """
    
    def __init__(
        self, 
        encryption_manager: EncryptionManager,
        privacy_manager: PrivacyManager,
        secure_storage: SecureStorage,
        data_dir: str = "data/secure_profiles"
    ):
        """
        Initialize secure user profile manager
        
        Args:
            encryption_manager: Encryption manager for sensitive data
            privacy_manager: Privacy manager for compliance
            secure_storage: Secure storage for encrypted data
            data_dir: Directory for profile storage
        """
        self.encryption_manager = encryption_manager
        self.privacy_manager = privacy_manager
        self.secure_storage = secure_storage
        self.data_dir = data_dir
        
        # Ensure data directory exists
        os.makedirs(data_dir, exist_ok=True)
        
        # Profile cache (encrypted in memory)
        self.profiles_cache = {}
        
        # Privacy settings
        self.data_retention_days = 90
        self.anonymization_days = 30
        self.sensitive_fields = [
            'aviation_experiences',
            'correction_history', 
            'feedback_patterns',
            'timezone',
            'important_conversations',
            'personal_info'
        ]
        
        # Compliance tracking
        self.compliance_stats = {
            "profiles_created": 0,
            "profiles_deleted": 0,
            "data_anonymized": 0,
            "privacy_requests": 0,
            "retention_cleanups": 0
        }
    
    async def get_profile(self, user_id: int, include_sensitive: bool = True) -> Dict[str, Any]:
        """
        Get user profile with privacy controls
        
        Args:
            user_id: User ID
            include_sensitive: Whether to include sensitive data
            
        Returns:
            User profile dictionary
        """
        try:
            user_id_str = str(user_id)
            
            # Check cache first
            if user_id_str in self.profiles_cache:
                cached_profile = self.profiles_cache[user_id_str]
                
                # Check if cache is still valid
                if self._is_cache_valid(cached_profile):
                    profile = cached_profile["data"].copy()
                    
                    if not include_sensitive:
                        profile = self._remove_sensitive_data(profile)
                    
                    return profile
            
            # Load from secure storage
            stored_data = self.secure_storage.load_secure_data(f"profile_{user_id}")
            
            if stored_data:
                profile = stored_data["data"]
                
                # Update cache
                self.profiles_cache[user_id_str] = {
                    "data": profile,
                    "timestamp": datetime.utcnow(),
                    "expires_at": datetime.utcnow() + timedelta(minutes=30)
                }
                
                if not include_sensitive:
                    profile = self._remove_sensitive_data(profile)
                
                return profile
            
            # Create new profile
            profile = await self._create_new_profile(user_id)
            self.compliance_stats["profiles_created"] += 1
            
            return profile
            
        except Exception as e:
            logging.error(f"Error getting profile for user {user_id}: {e}")
            return await self._create_new_profile(user_id)
    
    async def _create_new_profile(self, user_id: int) -> Dict[str, Any]:
        """Create a new user profile with privacy compliance"""
        profile = {
            "user_id": user_id,
            "created_at": datetime.utcnow().isoformat(),
            "last_active": datetime.utcnow().isoformat(),
            "conversation_count": 0,
            
            # Aviation-specific information (non-sensitive)
            "experience_level": None,
            "interests": [],
            "learning_goals": [],
            "knowledge_gaps": [],
            
            # Conversation preferences (non-sensitive)
            "preferred_detail_level": "medium",
            "conversation_style": "friendly",
            
            # Sensitive information (will be encrypted)
            "aviation_experiences": [],
            "correction_history": [],
            "feedback_patterns": {},
            "timezone": None,
            "important_conversations": [],
            "personal_info": {},
            
            # Privacy and compliance
            "privacy_consent": {
                "data_processing": False,
                "data_retention": False,
                "analytics": False,
                "consent_date": None
            },
            "data_retention_category": "standard",
            "anonymization_eligible": True,
            
            # Statistics
            "total_messages": 0,
            "aviation_questions_asked": 0,
            "helpful_responses_received": 0,
            "corrections_provided": 0
        }
        
        # Store securely
        await self._save_profile_secure(user_id, profile)
        
        return profile
    
    async def update_profile_from_conversation(
        self,
        user_id: int,
        conversation_text: str,
        ai_analysis: Dict[str, Any] = None,
        user_consent: bool = True
    ):
        """
        Update user profile with privacy compliance
        
        Args:
            user_id: User ID
            conversation_text: Conversation content
            ai_analysis: AI analysis results
            user_consent: Whether user has consented to data processing
        """
        try:
            if not user_consent:
                logging.info(f"Skipping profile update for user {user_id} - no consent")
                return
            
            profile = await self.get_profile(user_id)
            
            # Update basic stats
            profile["last_active"] = datetime.utcnow().isoformat()
            profile["total_messages"] += 1
            profile["conversation_count"] += 1
            
            # Only process sensitive data if consent is given
            if profile.get("privacy_consent", {}).get("data_processing", False):
                
                # Get AI analysis if not provided
                if ai_analysis is None:
                    ai_analysis = {"relevance_score": 5, "extracted_info": {}}
                
                relevance_score = ai_analysis.get("relevance_score", 0)
                
                # Update profile based on relevance
                if relevance_score >= 6:  # High relevance threshold
                    extracted_info = ai_analysis.get("extracted_info", {})
                    
                    # Update experience level
                    if "experience_level" in extracted_info:
                        old_level = profile.get("experience_level")
                        new_level = extracted_info["experience_level"]
                        if old_level != new_level:
                            profile["experience_level"] = new_level
                            await self._log_profile_change(user_id, "experience_level", old_level, new_level)
                    
                    # Add interests (with privacy consideration)
                    new_interests = extracted_info.get("interests", [])
                    for interest in new_interests[:3]:  # Limit to 3 new interests
                        if interest and interest not in profile["interests"]:
                            profile["interests"].append(interest)
                    
                    # Limit total interests for privacy
                    profile["interests"] = profile["interests"][-10:]
                    
                    # Add learning goals
                    new_goals = extracted_info.get("learning_goals", [])
                    for goal in new_goals[:2]:  # Limit to 2 new goals
                        if goal and goal not in profile["learning_goals"]:
                            profile["learning_goals"].append(goal)
                    
                    profile["learning_goals"] = profile["learning_goals"][-5:]
                    
                    # Store important conversation (encrypted)
                    if profile.get("privacy_consent", {}).get("data_retention", False):
                        conversation_summary = {
                            "timestamp": datetime.utcnow().isoformat(),
                            "relevance_score": relevance_score,
                            "summary": self._create_privacy_safe_summary(conversation_text),
                            "topics": extracted_info.get("topics", [])[:3],
                            "data_category": DataCategory.CONVERSATION_CONTENT.value
                        }
                        
                        profile["important_conversations"].append(conversation_summary)
                        
                        # Limit stored conversations for privacy
                        profile["important_conversations"] = profile["important_conversations"][-20:]
            
            # Save updated profile
            await self._save_profile_secure(user_id, profile)
            
            # Check if privacy cleanup is needed
            await self._check_privacy_compliance(user_id, profile)
            
        except Exception as e:
            logging.error(f"Error updating profile for user {user_id}: {e}")
    
    async def request_data_deletion(self, user_id: int, deletion_type: str = "complete") -> Dict[str, Any]:
        """
        Handle user data deletion request (GDPR compliance)
        
        Args:
            user_id: User ID
            deletion_type: Type of deletion (complete, partial, anonymize)
            
        Returns:
            Deletion report
        """
        try:
            self.compliance_stats["privacy_requests"] += 1
            
            if deletion_type == "complete":
                # Complete data deletion
                deletion_report = await self.privacy_manager.delete_user_data(
                    user_id, 
                    [DataCategory.PERSONAL_IDENTIFIABLE, DataCategory.CONVERSATION_CONTENT, 
                     DataCategory.BEHAVIORAL_PATTERNS]
                )
                
                # Remove from secure storage
                self.secure_storage.delete_secure_data(f"profile_{user_id}")
                
                # Clear cache
                user_id_str = str(user_id)
                if user_id_str in self.profiles_cache:
                    del self.profiles_cache[user_id_str]
                
                self.compliance_stats["profiles_deleted"] += 1
                
                return deletion_report
            
            elif deletion_type == "anonymize":
                # Anonymize sensitive data
                profile = await self.get_profile(user_id)
                
                anonymized_profile = await self._anonymize_profile(profile)
                await self._save_profile_secure(user_id, anonymized_profile)
                
                self.compliance_stats["data_anonymized"] += 1
                
                return {
                    "user_id": user_id,
                    "deletion_type": "anonymize",
                    "timestamp": datetime.utcnow().isoformat(),
                    "success": True,
                    "anonymized_fields": self.sensitive_fields
                }
            
            elif deletion_type == "partial":
                # Delete only sensitive data
                profile = await self.get_profile(user_id)
                
                for field in self.sensitive_fields:
                    if field in profile:
                        if isinstance(profile[field], list):
                            profile[field] = []
                        elif isinstance(profile[field], dict):
                            profile[field] = {}
                        else:
                            profile[field] = None
                
                profile["data_deletion_date"] = datetime.utcnow().isoformat()
                profile["deletion_type"] = "partial"
                
                await self._save_profile_secure(user_id, profile)
                
                return {
                    "user_id": user_id,
                    "deletion_type": "partial",
                    "timestamp": datetime.utcnow().isoformat(),
                    "success": True,
                    "deleted_fields": self.sensitive_fields
                }
            
            else:
                return {
                    "user_id": user_id,
                    "deletion_type": deletion_type,
                    "timestamp": datetime.utcnow().isoformat(),
                    "success": False,
                    "error": "Invalid deletion type"
                }
                
        except Exception as e:
            logging.error(f"Error processing data deletion request for user {user_id}: {e}")
            return {
                "user_id": user_id,
                "deletion_type": deletion_type,
                "timestamp": datetime.utcnow().isoformat(),
                "success": False,
                "error": str(e)
            }
    
    async def update_privacy_consent(
        self, 
        user_id: int, 
        consent_type: str, 
        consent_given: bool
    ) -> bool:
        """
        Update user privacy consent
        
        Args:
            user_id: User ID
            consent_type: Type of consent (data_processing, data_retention, analytics)
            consent_given: Whether consent is given
            
        Returns:
            Success status
        """
        try:
            profile = await self.get_profile(user_id)
            
            if "privacy_consent" not in profile:
                profile["privacy_consent"] = {
                    "data_processing": False,
                    "data_retention": False,
                    "analytics": False,
                    "consent_date": None
                }
            
            profile["privacy_consent"][consent_type] = consent_given
            profile["privacy_consent"]["consent_date"] = datetime.utcnow().isoformat()
            
            # If consent is withdrawn, clean up data
            if not consent_given:
                if consent_type == "data_processing":
                    # Stop processing new data
                    profile["data_processing_stopped"] = datetime.utcnow().isoformat()
                
                elif consent_type == "data_retention":
                    # Delete stored conversations
                    profile["important_conversations"] = []
                    profile["correction_history"] = []
                
                elif consent_type == "analytics":
                    # Remove analytics data
                    profile["feedback_patterns"] = {}
            
            await self._save_profile_secure(user_id, profile)
            
            logging.info(f"Updated privacy consent for user {user_id}: {consent_type} = {consent_given}")
            return True
            
        except Exception as e:
            logging.error(f"Error updating privacy consent for user {user_id}: {e}")
            return False
    
    async def get_user_data_export(self, user_id: int) -> Dict[str, Any]:
        """
        Export all user data (GDPR compliance)
        
        Args:
            user_id: User ID
            
        Returns:
            Complete user data export
        """
        try:
            profile = await self.get_profile(user_id, include_sensitive=True)
            
            # Get conversation history from privacy manager
            conversation_data = await self._get_user_conversations(user_id)
            
            export_data = {
                "export_timestamp": datetime.utcnow().isoformat(),
                "user_id": user_id,
                "profile_data": profile,
                "conversation_data": conversation_data,
                "data_categories": {
                    "personal_identifiable": self._extract_pii(profile),
                    "conversation_content": conversation_data,
                    "behavioral_patterns": profile.get("feedback_patterns", {}),
                    "system_logs": []  # Would need to implement log extraction
                },
                "privacy_settings": profile.get("privacy_consent", {}),
                "data_retention_info": {
                    "retention_category": profile.get("data_retention_category", "standard"),
                    "retention_days": self.data_retention_days,
                    "anonymization_eligible": profile.get("anonymization_eligible", True)
                }
            }
            
            return export_data
            
        except Exception as e:
            logging.error(f"Error exporting data for user {user_id}: {e}")
            return {
                "export_timestamp": datetime.utcnow().isoformat(),
                "user_id": user_id,
                "error": str(e),
                "success": False
            }
    
    async def _save_profile_secure(self, user_id: int, profile: Dict[str, Any]):
        """Save profile with encryption"""
        try:
            # Encrypt sensitive fields
            encrypted_profile = self.encryption_manager.encrypt_user_profile(profile)
            
            # Store in secure storage
            success = self.secure_storage.store_secure_data(
                f"profile_{user_id}",
                "user_profile",
                "profile",
                encrypted_profile,
                metadata={
                    "user_id": user_id,
                    "last_updated": datetime.utcnow().isoformat(),
                    "data_categories": [DataCategory.PERSONAL_IDENTIFIABLE.value, 
                                      DataCategory.BEHAVIORAL_PATTERNS.value]
                }
            )
            
            if success:
                # Update cache
                user_id_str = str(user_id)
                self.profiles_cache[user_id_str] = {
                    "data": profile,
                    "timestamp": datetime.utcnow(),
                    "expires_at": datetime.utcnow() + timedelta(minutes=30)
                }
            
        except Exception as e:
            logging.error(f"Error saving secure profile for user {user_id}: {e}")
            raise
    
    def _remove_sensitive_data(self, profile: Dict[str, Any]) -> Dict[str, Any]:
        """Remove sensitive data from profile"""
        safe_profile = profile.copy()
        
        for field in self.sensitive_fields:
            if field in safe_profile:
                if isinstance(safe_profile[field], list):
                    safe_profile[field] = []
                elif isinstance(safe_profile[field], dict):
                    safe_profile[field] = {}
                else:
                    safe_profile[field] = None
        
        return safe_profile
    
    async def _anonymize_profile(self, profile: Dict[str, Any]) -> Dict[str, Any]:
        """Anonymize sensitive profile data"""
        anonymized = profile.copy()
        
        # Anonymize sensitive fields
        for field in self.sensitive_fields:
            if field in anonymized:
                if isinstance(anonymized[field], list):
                    anonymized[field] = ["[ANONYMIZED]"] * min(len(anonymized[field]), 2)
                elif isinstance(anonymized[field], dict):
                    anonymized[field] = {"anonymized": True}
                elif isinstance(anonymized[field], str):
                    anonymized[field] = "[ANONYMIZED]"
        
        # Mark as anonymized
        anonymized["data_anonymized"] = True
        anonymized["anonymization_date"] = datetime.utcnow().isoformat()
        anonymized["original_user_id"] = anonymized["user_id"]
        anonymized["user_id"] = hashlib.sha256(str(anonymized["user_id"]).encode()).hexdigest()[:16]
        
        return anonymized
    
    def _create_privacy_safe_summary(self, conversation_text: str, max_length: int = 200) -> str:
        """Create privacy-safe conversation summary"""
        if len(conversation_text) <= max_length:
            return self._sanitize_text(conversation_text)
        
        # Truncate and sanitize
        summary = conversation_text[:max_length-20] + "...[TRUNCATED]"
        return self._sanitize_text(summary)
    
    def _sanitize_text(self, text: str) -> str:
        """Remove potentially sensitive information from text"""
        import re
        
        # Remove email addresses
        text = re.sub(r'\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Z|a-z]{2,}\b', '[EMAIL_REDACTED]', text)
        
        # Remove phone numbers
        text = re.sub(r'\b\d{3}[-.]?\d{3}[-.]?\d{4}\b', '[PHONE_REDACTED]', text)
        
        # Remove potential names (simple heuristic)
        text = re.sub(r'\bmy name is \w+\b', 'my name is [REDACTED]', text, flags=re.IGNORECASE)
        
        return text
    
    def _extract_pii(self, profile: Dict[str, Any]) -> Dict[str, Any]:
        """Extract personally identifiable information"""
        pii_data = {}
        
        pii_fields = ["timezone", "personal_info", "aviation_experiences"]
        
        for field in pii_fields:
            if field in profile and profile[field]:
                pii_data[field] = profile[field]
        
        return pii_data
    
    async def _get_user_conversations(self, user_id: int) -> List[Dict[str, Any]]:
        """Get user conversation history"""
        try:
            # This would integrate with conversation memory system
            # For now, return conversations from profile
            profile = await self.get_profile(user_id, include_sensitive=True)
            return profile.get("important_conversations", [])
            
        except Exception as e:
            logging.error(f"Error getting conversations for user {user_id}: {e}")
            return []
    
    def _is_cache_valid(self, cached_entry: Dict[str, Any]) -> bool:
        """Check if cache entry is still valid"""
        try:
            expires_at = cached_entry.get("expires_at")
            if not expires_at:
                return False
            
            return datetime.utcnow() < expires_at
            
        except Exception:
            return False
    
    async def _log_profile_change(self, user_id: int, field: str, old_value: Any, new_value: Any):
        """Log profile changes for audit purposes"""
        try:
            change_log = {
                "timestamp": datetime.utcnow().isoformat(),
                "user_id": user_id,
                "field": field,
                "old_value": str(old_value) if old_value else None,
                "new_value": str(new_value) if new_value else None,
                "change_type": "profile_update"
            }
            
            # Store in secure storage for audit
            self.secure_storage.store_secure_data(
                f"audit_{user_id}_{datetime.utcnow().timestamp()}",
                "audit_log",
                "profile_change",
                change_log
            )
            
        except Exception as e:
            logging.error(f"Error logging profile change: {e}")
    
    async def _check_privacy_compliance(self, user_id: int, profile: Dict[str, Any]):
        """Check and enforce privacy compliance"""
        try:
            # Check data retention
            created_at = datetime.fromisoformat(profile["created_at"])
            age_days = (datetime.utcnow() - created_at).days
            
            # Auto-anonymize old profiles
            if age_days > self.anonymization_days and profile.get("anonymization_eligible", True):
                if not profile.get("data_anonymized", False):
                    await self.request_data_deletion(user_id, "anonymize")
            
            # Auto-delete very old profiles
            if age_days > self.data_retention_days:
                retention_category = profile.get("data_retention_category", "standard")
                if retention_category == "temporary":
                    await self.request_data_deletion(user_id, "complete")
            
        except Exception as e:
            logging.error(f"Error checking privacy compliance for user {user_id}: {e}")
    
    async def cleanup_expired_data(self) -> Dict[str, Any]:
        """Clean up expired user data"""
        try:
            cleanup_report = {
                "timestamp": datetime.utcnow().isoformat(),
                "profiles_processed": 0,
                "profiles_anonymized": 0,
                "profiles_deleted": 0,
                "errors": []
            }
            
            # Get all profiles from secure storage
            all_profiles = self.secure_storage.search_secure_data(category="user_profile")
            
            for profile_record in all_profiles:
                try:
                    cleanup_report["profiles_processed"] += 1
                    
                    # Load profile data
                    profile_data = self.secure_storage.load_secure_data(profile_record["id"])
                    if not profile_data:
                        continue
                    
                    profile = profile_data["data"]
                    user_id = profile.get("user_id")
                    
                    if not user_id:
                        continue
                    
                    # Check compliance
                    await self._check_privacy_compliance(user_id, profile)
                    
                except Exception as e:
                    cleanup_report["errors"].append(f"Error processing profile {profile_record['id']}: {str(e)}")
            
            self.compliance_stats["retention_cleanups"] += 1
            
            return cleanup_report
            
        except Exception as e:
            logging.error(f"Error during data cleanup: {e}")
            return {
                "timestamp": datetime.utcnow().isoformat(),
                "success": False,
                "error": str(e)
            }
    
    def get_compliance_stats(self) -> Dict[str, Any]:
        """Get privacy compliance statistics"""
        return {
            "compliance_stats": self.compliance_stats.copy(),
            "privacy_settings": {
                "data_retention_days": self.data_retention_days,
                "anonymization_days": self.anonymization_days,
                "sensitive_fields": self.sensitive_fields
            },
            "data_categories": [category.value for category in DataCategory]
        }