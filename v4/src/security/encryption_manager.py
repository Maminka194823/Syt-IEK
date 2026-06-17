"""
V4 Encryption Manager
Handles data encryption and decryption for sensitive user information
"""

import os
import base64
import json
import logging
from typing import Dict, Any, Optional, Union
from cryptography.fernet import Fernet
from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.primitives.kdf.pbkdf2 import PBKDF2HMAC
from cryptography.hazmat.backends import default_backend
import secrets

class EncryptionManager:
    """
    Manages encryption and decryption of sensitive data
    Uses Fernet symmetric encryption with key derivation
    """
    
    def __init__(self, master_key: Optional[str] = None):
        """
        Initialize encryption manager
        
        Args:
            master_key: Optional master key. If not provided, will be generated or loaded from environment
        """
        self.master_key = master_key or self._get_or_create_master_key()
        self.fernet = self._create_fernet_instance()
        
        # Track encryption operations for monitoring
        self.encryption_stats = {
            "encryptions_performed": 0,
            "decryptions_performed": 0,
            "key_rotations": 0,
            "errors": 0
        }
        
    async def initialize(self):
        """
        Initialize encryption manager (async placeholder for compatibility)
        The actual initialization is done in __init__
        """
        # Nothing to do here - initialization is synchronous and done in __init__
        pass
        
    def _get_or_create_master_key(self) -> str:
        """Get master key from environment or create new one"""
        # Try to get from environment first
        env_key = os.getenv('AVIATION_BOT_MASTER_KEY')
        if env_key:
            return env_key
        
        # Generate new key if not found
        new_key = base64.urlsafe_b64encode(secrets.token_bytes(32)).decode()
        
        # Log warning about missing key
        logging.warning(
            "No master key found in environment. Generated new key. "
            "Set AVIATION_BOT_MASTER_KEY environment variable for production use."
        )
        
        return new_key
    
    def _create_fernet_instance(self) -> Fernet:
        """Create Fernet instance from master key"""
        try:
            # Derive key from master key using PBKDF2
            salt = b'aviation_bot_salt_v4'  # Fixed salt for consistency
            kdf = PBKDF2HMAC(
                algorithm=hashes.SHA256(),
                length=32,
                salt=salt,
                iterations=100000,
                backend=default_backend()
            )
            
            key = base64.urlsafe_b64encode(kdf.derive(self.master_key.encode()))
            return Fernet(key)
            
        except Exception as e:
            logging.error(f"Error creating Fernet instance: {e}")
            raise
    
    def encrypt_data(self, data: Union[str, Dict[str, Any]]) -> str:
        """
        Encrypt data and return base64 encoded string
        
        Args:
            data: Data to encrypt (string or dictionary)
            
        Returns:
            Base64 encoded encrypted data
        """
        try:
            # Convert to JSON string if dictionary
            if isinstance(data, dict):
                data_str = json.dumps(data, ensure_ascii=False)
            else:
                data_str = str(data)
            
            # Encrypt data
            encrypted_data = self.fernet.encrypt(data_str.encode('utf-8'))
            
            # Encode to base64 for storage
            encoded_data = base64.urlsafe_b64encode(encrypted_data).decode('utf-8')
            
            self.encryption_stats["encryptions_performed"] += 1
            return encoded_data
            
        except Exception as e:
            self.encryption_stats["errors"] += 1
            logging.error(f"Error encrypting data: {e}")
            raise
    
    def decrypt_data(self, encrypted_data: str, return_dict: bool = False) -> Union[str, Dict[str, Any]]:
        """
        Decrypt base64 encoded encrypted data
        
        Args:
            encrypted_data: Base64 encoded encrypted data
            return_dict: Whether to parse result as JSON dictionary
            
        Returns:
            Decrypted data as string or dictionary
        """
        try:
            # Decode from base64
            decoded_data = base64.urlsafe_b64decode(encrypted_data.encode('utf-8'))
            
            # Decrypt data
            decrypted_bytes = self.fernet.decrypt(decoded_data)
            decrypted_str = decrypted_bytes.decode('utf-8')
            
            self.encryption_stats["decryptions_performed"] += 1
            
            # Parse as JSON if requested
            if return_dict:
                try:
                    return json.loads(decrypted_str)
                except json.JSONDecodeError:
                    # If it's not valid JSON but return_dict is requested, 
                    # try to handle it gracefully
                    if decrypted_str.strip().startswith('{') or decrypted_str.strip().startswith('['):
                        logging.warning("Failed to parse decrypted data as JSON, returning string")
                        return decrypted_str
                    else:
                        # For non-JSON strings, return as-is when dict is requested
                        return decrypted_str
            
            return decrypted_str
            
        except Exception as e:
            self.encryption_stats["errors"] += 1
            logging.error(f"Error decrypting data: {e}")
            raise
    
    def encrypt_user_profile(self, profile: Dict[str, Any]) -> Dict[str, Any]:
        """
        Encrypt sensitive fields in user profile
        
        Args:
            profile: User profile dictionary
            
        Returns:
            Profile with sensitive fields encrypted
        """
        # Fields that should be encrypted
        sensitive_fields = [
            'aviation_experiences',  # Personal stories
            'correction_history',    # Detailed feedback
            'feedback_patterns',     # User behavior patterns
            'timezone',             # Location information
            'important_conversations'  # Detailed conversation content
        ]
        
        encrypted_profile = profile.copy()
        
        for field in sensitive_fields:
            if field in profile and profile[field]:
                try:
                    encrypted_profile[field] = self.encrypt_data(profile[field])
                    encrypted_profile[f"{field}_encrypted"] = True
                except Exception as e:
                    logging.error(f"Error encrypting profile field {field}: {e}")
                    # Keep original data if encryption fails
                    encrypted_profile[f"{field}_encrypted"] = False
        
        return encrypted_profile
    
    def decrypt_user_profile(self, encrypted_profile: Dict[str, Any]) -> Dict[str, Any]:
        """
        Decrypt sensitive fields in user profile
        
        Args:
            encrypted_profile: Profile with encrypted fields
            
        Returns:
            Profile with sensitive fields decrypted
        """
        sensitive_fields = [
            'aviation_experiences',
            'correction_history', 
            'feedback_patterns',
            'timezone',
            'important_conversations'
        ]
        
        decrypted_profile = encrypted_profile.copy()
        
        for field in sensitive_fields:
            if f"{field}_encrypted" in encrypted_profile and encrypted_profile[f"{field}_encrypted"]:
                try:
                    if field in encrypted_profile:
                        decrypted_data = self.decrypt_data(encrypted_profile[field], return_dict=True)
                        decrypted_profile[field] = decrypted_data
                        # Remove encryption flag
                        del decrypted_profile[f"{field}_encrypted"]
                except Exception as e:
                    logging.error(f"Error decrypting profile field {field}: {e}")
                    # Keep encrypted data if decryption fails
                    pass
        
        return decrypted_profile
    
    def encrypt_conversation_exchange(self, exchange: Dict[str, Any]) -> Dict[str, Any]:
        """
        Encrypt sensitive fields in conversation exchange
        
        Args:
            exchange: Conversation exchange dictionary
            
        Returns:
            Exchange with sensitive fields encrypted
        """
        # Fields that should be encrypted in conversations
        sensitive_fields = [
            'user_message',      # User's actual message content
            'ai_response',       # AI response content
            'extracted_info',    # Extracted personal information
            'context'           # Conversation context
        ]
        
        encrypted_exchange = exchange.copy()
        
        for field in sensitive_fields:
            if field in exchange and exchange[field]:
                try:
                    encrypted_exchange[field] = self.encrypt_data(exchange[field])
                    encrypted_exchange[f"{field}_encrypted"] = True
                except Exception as e:
                    logging.error(f"Error encrypting exchange field {field}: {e}")
                    encrypted_exchange[f"{field}_encrypted"] = False
        
        return encrypted_exchange
    
    def decrypt_conversation_exchange(self, encrypted_exchange: Dict[str, Any]) -> Dict[str, Any]:
        """
        Decrypt sensitive fields in conversation exchange
        
        Args:
            encrypted_exchange: Exchange with encrypted fields
            
        Returns:
            Exchange with sensitive fields decrypted
        """
        sensitive_fields = [
            'user_message',
            'ai_response', 
            'extracted_info',
            'context'
        ]
        
        decrypted_exchange = encrypted_exchange.copy()
        
        for field in sensitive_fields:
            if f"{field}_encrypted" in encrypted_exchange and encrypted_exchange[f"{field}_encrypted"]:
                try:
                    if field in encrypted_exchange:
                        decrypted_data = self.decrypt_data(encrypted_exchange[field], return_dict=True)
                        decrypted_exchange[field] = decrypted_data
                        del decrypted_exchange[f"{field}_encrypted"]
                except Exception as e:
                    logging.error(f"Error decrypting exchange field {field}: {e}")
                    pass
        
        return decrypted_exchange
    
    def rotate_encryption_key(self, new_master_key: Optional[str] = None) -> bool:
        """
        Rotate encryption key (for security maintenance)
        
        Args:
            new_master_key: Optional new master key. If not provided, generates new one
            
        Returns:
            True if rotation successful, False otherwise
        """
        try:
            # Store old fernet instance
            old_fernet = self.fernet
            
            # Create new key and fernet instance
            if new_master_key:
                self.master_key = new_master_key
            else:
                self.master_key = base64.urlsafe_b64encode(secrets.token_bytes(32)).decode()
            
            self.fernet = self._create_fernet_instance()
            
            self.encryption_stats["key_rotations"] += 1
            
            logging.info("Encryption key rotated successfully")
            return True
            
        except Exception as e:
            logging.error(f"Error rotating encryption key: {e}")
            self.encryption_stats["errors"] += 1
            return False
    
    def is_data_encrypted(self, data: str) -> bool:
        """
        Check if data appears to be encrypted
        
        Args:
            data: Data to check
            
        Returns:
            True if data appears encrypted, False otherwise
        """
        try:
            # Try to decode as base64
            decoded = base64.urlsafe_b64decode(data.encode('utf-8'))
            
            # Check if it looks like Fernet encrypted data
            # Fernet tokens are always 128 bytes or longer
            return len(decoded) >= 128
            
        except Exception:
            return False
    
    def sanitize_for_logging(self, data: Union[str, Dict[str, Any]]) -> str:
        """
        Sanitize data for safe logging (remove sensitive information)
        
        Args:
            data: Data to sanitize
            
        Returns:
            Sanitized string safe for logging
        """
        if isinstance(data, dict):
            sanitized = {}
            for key, value in data.items():
                if any(sensitive in key.lower() for sensitive in ['password', 'key', 'token', 'secret', 'credential']):
                    sanitized[key] = '[REDACTED]'
                elif isinstance(value, str) and len(value) > 50:
                    sanitized[key] = value[:20] + '...[TRUNCATED]'
                else:
                    sanitized[key] = value
            return json.dumps(sanitized, default=str)
        else:
            data_str = str(data)
            if len(data_str) > 100:
                return data_str[:50] + '...[TRUNCATED]'
            return data_str
    
    def get_encryption_stats(self) -> Dict[str, Any]:
        """Get encryption operation statistics"""
        return self.encryption_stats.copy()
    
    def verify_encryption_integrity(self, encrypted_data: str) -> bool:
        """
        Verify that encrypted data can be decrypted successfully
        
        Args:
            encrypted_data: Encrypted data to verify
            
        Returns:
            True if data can be decrypted, False otherwise
        """
        try:
            self.decrypt_data(encrypted_data)
            return True
        except Exception:
            return False