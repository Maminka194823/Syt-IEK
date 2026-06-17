"""
V4 Credential Manager
Secure storage and management of API keys and credentials
"""

import os
import json
import logging
from typing import Dict, Any, Optional, List
from datetime import datetime, timedelta
import secrets
import hashlib
from .encryption_manager import EncryptionManager

class CredentialManager:
    """
    Manages secure storage and rotation of API credentials
    Provides secure access to external service credentials
    """
    
    def __init__(self, encryption_manager: EncryptionManager, credentials_file: str = "data/credentials.enc"):
        """
        Initialize credential manager
        
        Args:
            encryption_manager: Encryption manager instance
            credentials_file: Path to encrypted credentials file
        """
        self.encryption_manager = encryption_manager
        self.credentials_file = credentials_file
        self.credentials_cache = {}
        
        # Ensure credentials directory exists
        os.makedirs(os.path.dirname(credentials_file), exist_ok=True)
        
        # Load existing credentials
        self._load_credentials()
        
        # Credential rotation settings
        self.rotation_intervals = {
            "discord_token": timedelta(days=90),      # Discord bot token
            "weather_api_key": timedelta(days=30),    # Weather API key
            "flight_api_key": timedelta(days=30),     # Flight tracking API key
            "faa_api_key": timedelta(days=60),        # FAA API key
            "database_password": timedelta(days=30)   # Database password
        }
        
        # Track credential operations
        self.operation_stats = {
            "credentials_loaded": 0,
            "credentials_stored": 0,
            "rotations_performed": 0,
            "access_attempts": 0,
            "failed_accesses": 0
        }
    
    async def initialize(self):
        """
        Initialize credential manager (async placeholder for compatibility)
        The actual initialization is done in __init__
        """
        # Nothing to do here - initialization is synchronous and done in __init__
        pass
    
    def _load_credentials(self):
        """Load credentials from encrypted file"""
        try:
            if os.path.exists(self.credentials_file):
                with open(self.credentials_file, 'r', encoding='utf-8') as f:
                    encrypted_data = f.read()
                
                if encrypted_data.strip():
                    decrypted_data = self.encryption_manager.decrypt_data(encrypted_data, return_dict=True)
                    self.credentials_cache = decrypted_data
                    self.operation_stats["credentials_loaded"] += 1
                    logging.info("Credentials loaded successfully")
                else:
                    self.credentials_cache = {}
            else:
                self.credentials_cache = {}
                logging.info("No existing credentials file found, starting with empty credentials")
                
        except Exception as e:
            logging.error(f"Error loading credentials: {e}")
            self.credentials_cache = {}
    
    def _save_credentials(self):
        """Save credentials to encrypted file"""
        try:
            encrypted_data = self.encryption_manager.encrypt_data(self.credentials_cache)
            
            with open(self.credentials_file, 'w', encoding='utf-8') as f:
                f.write(encrypted_data)
            
            self.operation_stats["credentials_stored"] += 1
            logging.info("Credentials saved successfully")
            
        except Exception as e:
            logging.error(f"Error saving credentials: {e}")
            raise
    
    def store_credential(
        self, 
        service_name: str, 
        credential_type: str, 
        credential_value: str,
        metadata: Optional[Dict[str, Any]] = None
    ):
        """
        Store a credential securely
        
        Args:
            service_name: Name of the service (e.g., "discord", "weather_api")
            credential_type: Type of credential (e.g., "token", "api_key", "password")
            credential_value: The actual credential value
            metadata: Optional metadata about the credential
        """
        try:
            if service_name not in self.credentials_cache:
                self.credentials_cache[service_name] = {}
            
            credential_entry = {
                "value": credential_value,
                "type": credential_type,
                "created_at": datetime.utcnow().isoformat(),
                "last_rotated": datetime.utcnow().isoformat(),
                "rotation_count": 0,
                "metadata": metadata or {},
                "hash": self._hash_credential(credential_value)
            }
            
            self.credentials_cache[service_name][credential_type] = credential_entry
            self._save_credentials()
            
            logging.info(f"Stored credential for {service_name}:{credential_type}")
            
        except Exception as e:
            logging.error(f"Error storing credential for {service_name}:{credential_type}: {e}")
            raise
    
    def get_credential(self, service_name: str, credential_type: str) -> Optional[str]:
        """
        Retrieve a credential
        
        Args:
            service_name: Name of the service
            credential_type: Type of credential
            
        Returns:
            Credential value or None if not found
        """
        try:
            self.operation_stats["access_attempts"] += 1
            
            if service_name in self.credentials_cache:
                if credential_type in self.credentials_cache[service_name]:
                    credential_entry = self.credentials_cache[service_name][credential_type]
                    return credential_entry["value"]
            
            # Try environment variables as fallback
            env_var_name = f"{service_name.upper()}_{credential_type.upper()}"
            env_value = os.getenv(env_var_name)
            
            if env_value:
                # Store environment credential for future use
                self.store_credential(service_name, credential_type, env_value, {
                    "source": "environment",
                    "env_var": env_var_name
                })
                return env_value
            
            self.operation_stats["failed_accesses"] += 1
            logging.warning(f"Credential not found: {service_name}:{credential_type}")
            return None
            
        except Exception as e:
            self.operation_stats["failed_accesses"] += 1
            logging.error(f"Error retrieving credential {service_name}:{credential_type}: {e}")
            return None
    
    def rotate_credential(
        self, 
        service_name: str, 
        credential_type: str, 
        new_credential_value: str
    ) -> bool:
        """
        Rotate a credential to a new value
        
        Args:
            service_name: Name of the service
            credential_type: Type of credential
            new_credential_value: New credential value
            
        Returns:
            True if rotation successful, False otherwise
        """
        try:
            if service_name not in self.credentials_cache:
                self.credentials_cache[service_name] = {}
            
            # Get existing credential or create new entry
            if credential_type in self.credentials_cache[service_name]:
                credential_entry = self.credentials_cache[service_name][credential_type]
                credential_entry["rotation_count"] += 1
            else:
                credential_entry = {
                    "type": credential_type,
                    "created_at": datetime.utcnow().isoformat(),
                    "rotation_count": 0,
                    "metadata": {}
                }
            
            # Update credential
            credential_entry["value"] = new_credential_value
            credential_entry["last_rotated"] = datetime.utcnow().isoformat()
            credential_entry["hash"] = self._hash_credential(new_credential_value)
            
            self.credentials_cache[service_name][credential_type] = credential_entry
            self._save_credentials()
            
            self.operation_stats["rotations_performed"] += 1
            logging.info(f"Rotated credential for {service_name}:{credential_type}")
            
            return True
            
        except Exception as e:
            logging.error(f"Error rotating credential {service_name}:{credential_type}: {e}")
            return False
    
    def check_credential_expiry(self) -> List[Dict[str, str]]:
        """
        Check for credentials that need rotation
        
        Returns:
            List of credentials that need rotation
        """
        expired_credentials = []
        current_time = datetime.utcnow()
        
        for service_name, service_credentials in self.credentials_cache.items():
            for credential_type, credential_entry in service_credentials.items():
                last_rotated = datetime.fromisoformat(credential_entry["last_rotated"])
                
                # Check if rotation interval is defined
                rotation_key = f"{service_name}_{credential_type}"
                if rotation_key in self.rotation_intervals:
                    rotation_interval = self.rotation_intervals[rotation_key]
                    
                    if current_time - last_rotated > rotation_interval:
                        expired_credentials.append({
                            "service": service_name,
                            "type": credential_type,
                            "last_rotated": credential_entry["last_rotated"],
                            "days_overdue": (current_time - last_rotated).days
                        })
        
        return expired_credentials
    
    def delete_credential(self, service_name: str, credential_type: str) -> bool:
        """
        Delete a credential
        
        Args:
            service_name: Name of the service
            credential_type: Type of credential
            
        Returns:
            True if deletion successful, False otherwise
        """
        try:
            if service_name in self.credentials_cache:
                if credential_type in self.credentials_cache[service_name]:
                    del self.credentials_cache[service_name][credential_type]
                    
                    # Remove service entry if no credentials left
                    if not self.credentials_cache[service_name]:
                        del self.credentials_cache[service_name]
                    
                    self._save_credentials()
                    logging.info(f"Deleted credential for {service_name}:{credential_type}")
                    return True
            
            logging.warning(f"Credential not found for deletion: {service_name}:{credential_type}")
            return False
            
        except Exception as e:
            logging.error(f"Error deleting credential {service_name}:{credential_type}: {e}")
            return False
    
    def list_credentials(self) -> Dict[str, List[str]]:
        """
        List all stored credentials (without values)
        
        Returns:
            Dictionary mapping service names to credential types
        """
        credential_list = {}
        
        for service_name, service_credentials in self.credentials_cache.items():
            credential_list[service_name] = list(service_credentials.keys())
        
        return credential_list
    
    def get_credential_metadata(self, service_name: str, credential_type: str) -> Optional[Dict[str, Any]]:
        """
        Get metadata about a credential
        
        Args:
            service_name: Name of the service
            credential_type: Type of credential
            
        Returns:
            Credential metadata or None if not found
        """
        try:
            if service_name in self.credentials_cache:
                if credential_type in self.credentials_cache[service_name]:
                    credential_entry = self.credentials_cache[service_name][credential_type]
                    
                    # Return metadata without the actual credential value
                    return {
                        "type": credential_entry["type"],
                        "created_at": credential_entry["created_at"],
                        "last_rotated": credential_entry["last_rotated"],
                        "rotation_count": credential_entry["rotation_count"],
                        "metadata": credential_entry["metadata"],
                        "hash": credential_entry["hash"]
                    }
            
            return None
            
        except Exception as e:
            logging.error(f"Error getting credential metadata {service_name}:{credential_type}: {e}")
            return None
    
    def validate_credential_integrity(self) -> Dict[str, Any]:
        """
        Validate integrity of all stored credentials
        
        Returns:
            Validation report
        """
        validation_report = {
            "total_credentials": 0,
            "valid_credentials": 0,
            "invalid_credentials": 0,
            "missing_hashes": 0,
            "issues": []
        }
        
        for service_name, service_credentials in self.credentials_cache.items():
            for credential_type, credential_entry in service_credentials.items():
                validation_report["total_credentials"] += 1
                
                try:
                    # Check if credential has required fields
                    required_fields = ["value", "type", "created_at", "last_rotated"]
                    missing_fields = [field for field in required_fields if field not in credential_entry]
                    
                    if missing_fields:
                        validation_report["invalid_credentials"] += 1
                        validation_report["issues"].append({
                            "service": service_name,
                            "type": credential_type,
                            "issue": f"Missing fields: {missing_fields}"
                        })
                        continue
                    
                    # Check hash integrity
                    if "hash" not in credential_entry:
                        validation_report["missing_hashes"] += 1
                        validation_report["issues"].append({
                            "service": service_name,
                            "type": credential_type,
                            "issue": "Missing hash"
                        })
                    else:
                        expected_hash = self._hash_credential(credential_entry["value"])
                        if credential_entry["hash"] != expected_hash:
                            validation_report["invalid_credentials"] += 1
                            validation_report["issues"].append({
                                "service": service_name,
                                "type": credential_type,
                                "issue": "Hash mismatch - possible corruption"
                            })
                            continue
                    
                    validation_report["valid_credentials"] += 1
                    
                except Exception as e:
                    validation_report["invalid_credentials"] += 1
                    validation_report["issues"].append({
                        "service": service_name,
                        "type": credential_type,
                        "issue": f"Validation error: {str(e)}"
                    })
        
        return validation_report
    
    def _hash_credential(self, credential_value: str) -> str:
        """Create hash of credential for integrity checking"""
        return hashlib.sha256(credential_value.encode()).hexdigest()[:16]
    
    def get_operation_stats(self) -> Dict[str, Any]:
        """Get credential operation statistics"""
        return self.operation_stats.copy()
    
    def secure_credential_for_logging(self, credential_value: str) -> str:
        """
        Create a secure representation of credential for logging
        
        Args:
            credential_value: Credential to secure
            
        Returns:
            Secured credential string safe for logging
        """
        if not credential_value:
            return "[EMPTY]"
        
        if len(credential_value) <= 8:
            return "[REDACTED]"
        
        # Show first 4 and last 4 characters with asterisks in between
        return f"{credential_value[:4]}{'*' * (len(credential_value) - 8)}{credential_value[-4:]}"