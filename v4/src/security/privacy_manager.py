"""
V4 Privacy Manager
Handles data deletion, privacy compliance, and data retention policies
"""

import os
import json
import logging
import sqlite3
from typing import Dict, Any, Optional, List, Set
from datetime import datetime, timedelta
from enum import Enum
import asyncio
import re

class DataCategory(Enum):
    """Categories of data for privacy management"""
    PERSONAL_IDENTIFIABLE = "personal_identifiable"
    CONVERSATION_CONTENT = "conversation_content"
    BEHAVIORAL_PATTERNS = "behavioral_patterns"
    SYSTEM_LOGS = "system_logs"
    ANALYTICS_DATA = "analytics_data"
    CACHED_DATA = "cached_data"

class RetentionPolicy(Enum):
    """Data retention policies"""
    IMMEDIATE_DELETE = "immediate_delete"      # Delete immediately upon request
    SHORT_TERM = "short_term"                  # 30 days
    MEDIUM_TERM = "medium_term"                # 90 days
    LONG_TERM = "long_term"                    # 365 days
    PERMANENT = "permanent"                    # Keep indefinitely (with user consent)

class PrivacyManager:
    """
    Manages data privacy, deletion, and compliance
    Implements GDPR-like privacy controls and data retention
    """
    
    def __init__(self, data_directories: List[str], secure_storage=None):
        """
        Initialize privacy manager
        
        Args:
            data_directories: List of directories containing user data
            secure_storage: Optional secure storage instance
        """
        self.data_directories = data_directories
        self.secure_storage = secure_storage
        
        # Privacy settings
        self.retention_policies = {
            DataCategory.PERSONAL_IDENTIFIABLE: RetentionPolicy.MEDIUM_TERM,
            DataCategory.CONVERSATION_CONTENT: RetentionPolicy.LONG_TERM,
            DataCategory.BEHAVIORAL_PATTERNS: RetentionPolicy.MEDIUM_TERM,
            DataCategory.SYSTEM_LOGS: RetentionPolicy.SHORT_TERM,
            DataCategory.ANALYTICS_DATA: RetentionPolicy.MEDIUM_TERM,
            DataCategory.CACHED_DATA: RetentionPolicy.SHORT_TERM
        }
        
        # Anonymization settings
        self.anonymization_delay = timedelta(days=30)  # Anonymize after 30 days
        self.hard_delete_delay = timedelta(days=400)   # Hard delete after 400 days
        
        # Privacy operation tracking
        self.privacy_stats = {
            "deletion_requests": 0,
            "data_deleted": 0,
            "anonymizations_performed": 0,
            "retention_cleanups": 0,
            "privacy_errors": 0
        }
        
        # Patterns for identifying sensitive data
        self.sensitive_patterns = {
            "email": re.compile(r'\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Z|a-z]{2,}\b'),
            "phone": re.compile(r'\b\d{3}[-.]?\d{3}[-.]?\d{4}\b'),
            "ssn": re.compile(r'\b\d{3}-\d{2}-\d{4}\b'),
            "credit_card": re.compile(r'\b\d{4}[-\s]?\d{4}[-\s]?\d{4}[-\s]?\d{4}\b'),
            "ip_address": re.compile(r'\b\d{1,3}\.\d{1,3}\.\d{1,3}\.\d{1,3}\b')
        }
    
    async def delete_user_data(self, user_id: int, data_categories: Optional[List[DataCategory]] = None) -> Dict[str, Any]:
        """
        Delete all data for a user across all systems
        
        Args:
            user_id: User ID to delete data for
            data_categories: Optional list of specific categories to delete
            
        Returns:
            Deletion report
        """
        deletion_report = {
            "user_id": user_id,
            "deletion_timestamp": datetime.utcnow().isoformat(),
            "categories_deleted": [],
            "files_deleted": 0,
            "database_records_deleted": 0,
            "errors": [],
            "success": True
        }
        
        try:
            self.privacy_stats["deletion_requests"] += 1
            
            # Delete from file-based storage
            file_deletion_result = await self._delete_user_files(user_id, data_categories)
            deletion_report["files_deleted"] = file_deletion_result["files_deleted"]
            deletion_report["errors"].extend(file_deletion_result["errors"])
            
            # Delete from secure storage
            if self.secure_storage:
                secure_deletion_result = await self._delete_user_secure_data(user_id, data_categories)
                deletion_report["database_records_deleted"] = secure_deletion_result["records_deleted"]
                deletion_report["errors"].extend(secure_deletion_result["errors"])
            
            # Delete from conversation database
            conversation_deletion_result = await self._delete_user_conversations(user_id)
            deletion_report["database_records_deleted"] += conversation_deletion_result["records_deleted"]
            deletion_report["errors"].extend(conversation_deletion_result["errors"])
            
            # Update statistics
            if deletion_report["files_deleted"] > 0 or deletion_report["database_records_deleted"] > 0:
                self.privacy_stats["data_deleted"] += 1
            
            # Log deletion request
            await self._log_privacy_action("data_deletion", user_id, deletion_report)
            
            if deletion_report["errors"]:
                deletion_report["success"] = False
                self.privacy_stats["privacy_errors"] += 1
            
            logging.info(f"Data deletion completed for user {user_id}: {deletion_report}")
            
            return deletion_report
            
        except Exception as e:
            self.privacy_stats["privacy_errors"] += 1
            deletion_report["success"] = False
            deletion_report["errors"].append(f"General deletion error: {str(e)}")
            logging.error(f"Error deleting user data for {user_id}: {e}")
            return deletion_report
    
    async def _delete_user_files(self, user_id: int, data_categories: Optional[List[DataCategory]]) -> Dict[str, Any]:
        """Delete user files from data directories"""
        result = {
            "files_deleted": 0,
            "errors": []
        }
        
        user_id_str = str(user_id)
        
        for data_dir in self.data_directories:
            try:
                if not os.path.exists(data_dir):
                    continue
                
                # Find user-specific files
                user_files = []
                
                # Profile files
                profile_file = os.path.join(data_dir, f"{user_id_str}.json")
                if os.path.exists(profile_file):
                    user_files.append(profile_file)
                
                # History files
                history_file = os.path.join(data_dir, f"{user_id_str}_history.json")
                if os.path.exists(history_file):
                    user_files.append(history_file)
                
                # Other user-specific files
                for file_name in os.listdir(data_dir):
                    if file_name.startswith(f"{user_id_str}_") or file_name.startswith(f"user_{user_id_str}"):
                        file_path = os.path.join(data_dir, file_name)
                        if os.path.isfile(file_path) and file_path not in user_files:
                            user_files.append(file_path)
                
                # Securely delete files
                for file_path in user_files:
                    try:
                        await self._secure_delete_file(file_path)
                        result["files_deleted"] += 1
                        logging.info(f"Deleted user file: {file_path}")
                    except Exception as e:
                        result["errors"].append(f"Error deleting file {file_path}: {str(e)}")
                        
            except Exception as e:
                result["errors"].append(f"Error processing directory {data_dir}: {str(e)}")
        
        return result
    
    async def _delete_user_secure_data(self, user_id: int, data_categories: Optional[List[DataCategory]]) -> Dict[str, Any]:
        """Delete user data from secure storage"""
        result = {
            "records_deleted": 0,
            "errors": []
        }
        
        if not self.secure_storage:
            return result
        
        try:
            # Search for user data in secure storage
            user_data_records = self.secure_storage.search_secure_data(
                category="user_profile",
                limit=1000
            )
            
            # Filter records for this user
            user_records = [
                record for record in user_data_records 
                if str(user_id) in record["id"]
            ]
            
            # Delete each record
            for record in user_records:
                try:
                    if self.secure_storage.delete_secure_data(record["id"]):
                        result["records_deleted"] += 1
                    else:
                        result["errors"].append(f"Failed to delete secure data record: {record['id']}")
                except Exception as e:
                    result["errors"].append(f"Error deleting secure data {record['id']}: {str(e)}")
            
        except Exception as e:
            result["errors"].append(f"Error accessing secure storage: {str(e)}")
        
        return result
    
    async def _delete_user_conversations(self, user_id: int) -> Dict[str, Any]:
        """Delete user conversations from conversation database"""
        result = {
            "records_deleted": 0,
            "errors": []
        }
        
        try:
            # Look for conversation database
            conversation_db_paths = []
            
            for data_dir in self.data_directories:
                db_path = os.path.join(data_dir, "conversations.db")
                if os.path.exists(db_path):
                    conversation_db_paths.append(db_path)
            
            for db_path in conversation_db_paths:
                try:
                    with sqlite3.connect(db_path) as conn:
                        cursor = conn.execute("DELETE FROM conversations WHERE user_id = ?", (user_id,))
                        deleted_count = cursor.rowcount
                        conn.commit()
                        
                        result["records_deleted"] += deleted_count
                        logging.info(f"Deleted {deleted_count} conversation records for user {user_id}")
                        
                except Exception as e:
                    result["errors"].append(f"Error deleting from conversation DB {db_path}: {str(e)}")
            
        except Exception as e:
            result["errors"].append(f"Error processing conversation databases: {str(e)}")
        
        return result
    
    async def _secure_delete_file(self, file_path: str):
        """Securely delete a file by overwriting with random data"""
        try:
            if not os.path.exists(file_path):
                return
            
            # Get file size
            file_size = os.path.getsize(file_path)
            
            # Overwrite with random data multiple times
            with open(file_path, 'r+b') as f:
                for _ in range(3):  # 3 passes of random data
                    f.seek(0)
                    f.write(os.urandom(file_size))
                    f.flush()
                    os.fsync(f.fileno())
            
            # Remove file
            os.remove(file_path)
            
        except Exception as e:
            logging.error(f"Error securely deleting file {file_path}: {e}")
            raise
    
    async def anonymize_old_data(self, anonymization_age_days: int = 30) -> Dict[str, Any]:
        """
        Anonymize old data to protect privacy while preserving analytics
        
        Args:
            anonymization_age_days: Age in days after which to anonymize data
            
        Returns:
            Anonymization report
        """
        anonymization_report = {
            "anonymization_timestamp": datetime.utcnow().isoformat(),
            "records_anonymized": 0,
            "files_anonymized": 0,
            "errors": [],
            "success": True
        }
        
        try:
            cutoff_date = datetime.utcnow() - timedelta(days=anonymization_age_days)
            
            # Anonymize conversation data
            conversation_result = await self._anonymize_conversations(cutoff_date)
            anonymization_report["records_anonymized"] += conversation_result["records_anonymized"]
            anonymization_report["errors"].extend(conversation_result["errors"])
            
            # Anonymize file-based data
            file_result = await self._anonymize_user_files(cutoff_date)
            anonymization_report["files_anonymized"] += file_result["files_anonymized"]
            anonymization_report["errors"].extend(file_result["errors"])
            
            self.privacy_stats["anonymizations_performed"] += 1
            
            if anonymization_report["errors"]:
                anonymization_report["success"] = False
                self.privacy_stats["privacy_errors"] += 1
            
            logging.info(f"Data anonymization completed: {anonymization_report}")
            
            return anonymization_report
            
        except Exception as e:
            self.privacy_stats["privacy_errors"] += 1
            anonymization_report["success"] = False
            anonymization_report["errors"].append(f"General anonymization error: {str(e)}")
            logging.error(f"Error during data anonymization: {e}")
            return anonymization_report
    
    async def _anonymize_conversations(self, cutoff_date: datetime) -> Dict[str, Any]:
        """Anonymize old conversation data"""
        result = {
            "records_anonymized": 0,
            "errors": []
        }
        
        try:
            for data_dir in self.data_directories:
                db_path = os.path.join(data_dir, "conversations.db")
                if not os.path.exists(db_path):
                    continue
                
                with sqlite3.connect(db_path) as conn:
                    # Find old conversations that aren't already anonymized
                    cursor = conn.execute("""
                        SELECT id, user_message, ai_response 
                        FROM conversations 
                        WHERE timestamp < ? AND user_message != '[ANONYMIZED]'
                    """, (cutoff_date.isoformat(),))
                    
                    old_conversations = cursor.fetchall()
                    
                    for conv_id, user_msg, ai_response in old_conversations:
                        try:
                            # Anonymize the content
                            anonymized_user_msg = self._anonymize_text(user_msg)
                            anonymized_ai_response = self._anonymize_text(ai_response)
                            
                            # Update the record
                            conn.execute("""
                                UPDATE conversations 
                                SET user_message = ?, ai_response = ?, updated_at = ?
                                WHERE id = ?
                            """, (anonymized_user_msg, anonymized_ai_response, 
                                 datetime.utcnow().isoformat(), conv_id))
                            
                            result["records_anonymized"] += 1
                            
                        except Exception as e:
                            result["errors"].append(f"Error anonymizing conversation {conv_id}: {str(e)}")
                    
                    conn.commit()
                    
        except Exception as e:
            result["errors"].append(f"Error anonymizing conversations: {str(e)}")
        
        return result
    
    async def _anonymize_user_files(self, cutoff_date: datetime) -> Dict[str, Any]:
        """Anonymize old user profile files"""
        result = {
            "files_anonymized": 0,
            "errors": []
        }
        
        try:
            for data_dir in self.data_directories:
                if not os.path.exists(data_dir):
                    continue
                
                for file_name in os.listdir(data_dir):
                    if not file_name.endswith('.json'):
                        continue
                    
                    file_path = os.path.join(data_dir, file_name)
                    
                    try:
                        # Check file modification time
                        file_mtime = datetime.fromtimestamp(os.path.getmtime(file_path))
                        
                        if file_mtime < cutoff_date:
                            # Load and anonymize file
                            with open(file_path, 'r', encoding='utf-8') as f:
                                data = json.load(f)
                            
                            # Anonymize sensitive fields
                            anonymized_data = self._anonymize_profile_data(data)
                            
                            # Save anonymized data
                            with open(file_path, 'w', encoding='utf-8') as f:
                                json.dump(anonymized_data, f, indent=2, ensure_ascii=False)
                            
                            result["files_anonymized"] += 1
                            
                    except Exception as e:
                        result["errors"].append(f"Error anonymizing file {file_path}: {str(e)}")
                        
        except Exception as e:
            result["errors"].append(f"Error processing user files: {str(e)}")
        
        return result
    
    def _anonymize_text(self, text: str) -> str:
        """Anonymize sensitive information in text"""
        if not text or text == '[ANONYMIZED]':
            return '[ANONYMIZED]'
        
        anonymized = text
        
        # Replace sensitive patterns
        for pattern_name, pattern in self.sensitive_patterns.items():
            anonymized = pattern.sub(f'[{pattern_name.upper()}_REDACTED]', anonymized)
        
        # If text is very long, truncate and mark as anonymized
        if len(anonymized) > 500:
            anonymized = anonymized[:100] + '...[CONTENT_ANONYMIZED]'
        
        return anonymized
    
    def _anonymize_profile_data(self, profile_data: Dict[str, Any]) -> Dict[str, Any]:
        """Anonymize sensitive fields in profile data"""
        anonymized = profile_data.copy()
        
        # Fields to anonymize
        sensitive_fields = [
            'aviation_experiences',
            'correction_history',
            'important_conversations',
            'timezone'
        ]
        
        for field in sensitive_fields:
            if field in anonymized:
                if isinstance(anonymized[field], list):
                    anonymized[field] = ['[ANONYMIZED]'] * min(len(anonymized[field]), 3)
                elif isinstance(anonymized[field], str):
                    anonymized[field] = '[ANONYMIZED]'
                elif isinstance(anonymized[field], dict):
                    anonymized[field] = {'anonymized': True}
        
        # Mark as anonymized
        anonymized['data_anonymized'] = True
        anonymized['anonymization_date'] = datetime.utcnow().isoformat()
        
        return anonymized
    
    async def enforce_retention_policies(self) -> Dict[str, Any]:
        """
        Enforce data retention policies across all data categories
        
        Returns:
            Retention enforcement report
        """
        retention_report = {
            "enforcement_timestamp": datetime.utcnow().isoformat(),
            "policies_enforced": 0,
            "records_deleted": 0,
            "files_deleted": 0,
            "errors": [],
            "success": True
        }
        
        try:
            current_time = datetime.utcnow()
            
            for category, policy in self.retention_policies.items():
                try:
                    # Calculate retention period
                    if policy == RetentionPolicy.SHORT_TERM:
                        retention_days = 30
                    elif policy == RetentionPolicy.MEDIUM_TERM:
                        retention_days = 90
                    elif policy == RetentionPolicy.LONG_TERM:
                        retention_days = 365
                    elif policy == RetentionPolicy.IMMEDIATE_DELETE:
                        retention_days = 0
                    else:  # PERMANENT
                        continue  # Skip permanent data
                    
                    cutoff_date = current_time - timedelta(days=retention_days)
                    
                    # Enforce policy based on category
                    if category == DataCategory.CONVERSATION_CONTENT:
                        result = await self._cleanup_old_conversations(cutoff_date)
                        retention_report["records_deleted"] += result["records_deleted"]
                        retention_report["errors"].extend(result["errors"])
                    
                    elif category == DataCategory.SYSTEM_LOGS:
                        result = await self._cleanup_old_logs(cutoff_date)
                        retention_report["files_deleted"] += result["files_deleted"]
                        retention_report["errors"].extend(result["errors"])
                    
                    elif category == DataCategory.CACHED_DATA:
                        result = await self._cleanup_cached_data(cutoff_date)
                        retention_report["files_deleted"] += result["files_deleted"]
                        retention_report["errors"].extend(result["errors"])
                    
                    retention_report["policies_enforced"] += 1
                    
                except Exception as e:
                    retention_report["errors"].append(f"Error enforcing policy for {category}: {str(e)}")
            
            self.privacy_stats["retention_cleanups"] += 1
            
            if retention_report["errors"]:
                retention_report["success"] = False
                self.privacy_stats["privacy_errors"] += 1
            
            logging.info(f"Retention policy enforcement completed: {retention_report}")
            
            return retention_report
            
        except Exception as e:
            self.privacy_stats["privacy_errors"] += 1
            retention_report["success"] = False
            retention_report["errors"].append(f"General retention error: {str(e)}")
            logging.error(f"Error enforcing retention policies: {e}")
            return retention_report
    
    async def _cleanup_old_conversations(self, cutoff_date: datetime) -> Dict[str, Any]:
        """Clean up old conversation data"""
        result = {
            "records_deleted": 0,
            "errors": []
        }
        
        try:
            for data_dir in self.data_directories:
                db_path = os.path.join(data_dir, "conversations.db")
                if not os.path.exists(db_path):
                    continue
                
                with sqlite3.connect(db_path) as conn:
                    cursor = conn.execute("""
                        DELETE FROM conversations 
                        WHERE timestamp < ? AND retention_category IN ('temporary', 'standard')
                    """, (cutoff_date.isoformat(),))
                    
                    deleted_count = cursor.rowcount
                    conn.commit()
                    
                    result["records_deleted"] += deleted_count
                    
        except Exception as e:
            result["errors"].append(f"Error cleaning up conversations: {str(e)}")
        
        return result
    
    async def _cleanup_old_logs(self, cutoff_date: datetime) -> Dict[str, Any]:
        """Clean up old log files"""
        result = {
            "files_deleted": 0,
            "errors": []
        }
        
        try:
            for data_dir in self.data_directories:
                logs_dir = os.path.join(data_dir, "logs")
                if not os.path.exists(logs_dir):
                    continue
                
                for log_file in os.listdir(logs_dir):
                    log_path = os.path.join(logs_dir, log_file)
                    
                    if os.path.isfile(log_path):
                        file_mtime = datetime.fromtimestamp(os.path.getmtime(log_path))
                        
                        if file_mtime < cutoff_date:
                            try:
                                await self._secure_delete_file(log_path)
                                result["files_deleted"] += 1
                            except Exception as e:
                                result["errors"].append(f"Error deleting log file {log_path}: {str(e)}")
                                
        except Exception as e:
            result["errors"].append(f"Error cleaning up logs: {str(e)}")
        
        return result
    
    async def _cleanup_cached_data(self, cutoff_date: datetime) -> Dict[str, Any]:
        """Clean up old cached data"""
        result = {
            "files_deleted": 0,
            "errors": []
        }
        
        try:
            for data_dir in self.data_directories:
                cache_dir = os.path.join(data_dir, "cache")
                if not os.path.exists(cache_dir):
                    continue
                
                for cache_file in os.listdir(cache_dir):
                    cache_path = os.path.join(cache_dir, cache_file)
                    
                    if os.path.isfile(cache_path):
                        file_mtime = datetime.fromtimestamp(os.path.getmtime(cache_path))
                        
                        if file_mtime < cutoff_date:
                            try:
                                await self._secure_delete_file(cache_path)
                                result["files_deleted"] += 1
                            except Exception as e:
                                result["errors"].append(f"Error deleting cache file {cache_path}: {str(e)}")
                                
        except Exception as e:
            result["errors"].append(f"Error cleaning up cache: {str(e)}")
        
        return result
    
    async def _log_privacy_action(self, action_type: str, user_id: int, details: Dict[str, Any]):
        """Log privacy-related actions for audit purposes"""
        try:
            log_entry = {
                "timestamp": datetime.utcnow().isoformat(),
                "action_type": action_type,
                "user_id": user_id,
                "details": details
            }
            
            # Log to privacy audit file
            privacy_log_path = os.path.join(self.data_directories[0], "privacy_audit.log")
            
            with open(privacy_log_path, 'a', encoding='utf-8') as f:
                f.write(json.dumps(log_entry) + '\n')
                
        except Exception as e:
            logging.error(f"Error logging privacy action: {e}")
    
    def get_privacy_stats(self) -> Dict[str, Any]:
        """Get privacy operation statistics"""
        return self.privacy_stats.copy()
    
    def get_retention_policies(self) -> Dict[str, str]:
        """Get current retention policies"""
        return {category.value: policy.value for category, policy in self.retention_policies.items()}
    
    def update_retention_policy(self, category: DataCategory, policy: RetentionPolicy) -> bool:
        """
        Update retention policy for a data category
        
        Args:
            category: Data category to update
            policy: New retention policy
            
        Returns:
            True if update successful, False otherwise
        """
        try:
            self.retention_policies[category] = policy
            logging.info(f"Updated retention policy for {category.value} to {policy.value}")
            return True
        except Exception as e:
            logging.error(f"Error updating retention policy: {e}")
            return False