"""
V4 Secure Storage
Secure file and database storage with encryption
"""

import os
import json
import sqlite3
import logging
from typing import Dict, Any, Optional, List, Union
from datetime import datetime, timezone
import tempfile
import shutil
from .encryption_manager import EncryptionManager

class SecureStorage:
    """
    Provides secure storage capabilities with encryption
    Handles both file-based and database storage
    """
    
    def __init__(self, encryption_manager: EncryptionManager, storage_dir: str = "data/secure"):
        """
        Initialize secure storage
        
        Args:
            encryption_manager: Encryption manager instance
            storage_dir: Directory for secure storage
        """
        self.encryption_manager = encryption_manager
        self.storage_dir = storage_dir
        
        # Ensure storage directory exists with proper permissions
        os.makedirs(storage_dir, mode=0o700, exist_ok=True)
        
        # Initialize secure database
        self.db_path = os.path.join(storage_dir, "secure_data.db")
        self._init_secure_database()
        
        # Storage statistics
        self.storage_stats = {
            "files_encrypted": 0,
            "files_decrypted": 0,
            "database_operations": 0,
            "storage_errors": 0
        }
    
    def _init_secure_database(self):
        """Initialize secure database with encrypted storage"""
        try:
            with sqlite3.connect(self.db_path) as conn:
                # Enable WAL mode for better concurrency
                conn.execute("PRAGMA journal_mode=WAL")
                
                # Create secure storage table
                conn.execute("""
                    CREATE TABLE IF NOT EXISTS secure_storage (
                        id TEXT PRIMARY KEY,
                        category TEXT NOT NULL,
                        data_type TEXT NOT NULL,
                        encrypted_data TEXT NOT NULL,
                        metadata TEXT,
                        created_at TEXT NOT NULL,
                        updated_at TEXT NOT NULL,
                        access_count INTEGER DEFAULT 0,
                        last_accessed TEXT
                    )
                """)
                
                # Create indexes
                conn.execute("CREATE INDEX IF NOT EXISTS idx_category ON secure_storage(category)")
                conn.execute("CREATE INDEX IF NOT EXISTS idx_data_type ON secure_storage(data_type)")
                conn.execute("CREATE INDEX IF NOT EXISTS idx_created_at ON secure_storage(created_at)")
                
                conn.commit()
                
        except Exception as e:
            logging.error(f"Error initializing secure database: {e}")
            raise
    
    def store_secure_file(
        self, 
        file_path: str, 
        data: Union[str, bytes, Dict[str, Any]], 
        overwrite: bool = False
    ) -> bool:
        """
        Store data securely in an encrypted file
        
        Args:
            file_path: Relative path within secure storage
            data: Data to store
            overwrite: Whether to overwrite existing file
            
        Returns:
            True if storage successful, False otherwise
        """
        try:
            full_path = os.path.join(self.storage_dir, file_path)
            
            # Check if file exists and overwrite is not allowed
            if os.path.exists(full_path) and not overwrite:
                logging.warning(f"File already exists and overwrite not allowed: {file_path}")
                return False
            
            # Ensure directory exists
            os.makedirs(os.path.dirname(full_path), mode=0o700, exist_ok=True)
            
            # Convert data to string if needed
            if isinstance(data, dict):
                data_str = json.dumps(data, ensure_ascii=False)
            elif isinstance(data, bytes):
                data_str = data.decode('utf-8')
            else:
                data_str = str(data)
            
            # Encrypt data
            encrypted_data = self.encryption_manager.encrypt_data(data_str)
            
            # Write to temporary file first, then move (atomic operation)
            temp_path = full_path + '.tmp'
            with open(temp_path, 'w', encoding='utf-8') as f:
                f.write(encrypted_data)
            
            # Set secure file permissions
            os.chmod(temp_path, 0o600)
            
            # Atomic move
            shutil.move(temp_path, full_path)
            
            self.storage_stats["files_encrypted"] += 1
            logging.info(f"Securely stored file: {file_path}")
            
            return True
            
        except Exception as e:
            self.storage_stats["storage_errors"] += 1
            logging.error(f"Error storing secure file {file_path}: {e}")
            
            # Clean up temporary file if it exists
            temp_path = os.path.join(self.storage_dir, file_path + '.tmp')
            if os.path.exists(temp_path):
                try:
                    os.remove(temp_path)
                except:
                    pass
            
            return False
    
    def load_secure_file(self, file_path: str, return_dict: bool = False) -> Optional[Union[str, Dict[str, Any]]]:
        """
        Load data from encrypted file
        
        Args:
            file_path: Relative path within secure storage
            return_dict: Whether to parse as JSON dictionary
            
        Returns:
            Decrypted data or None if not found/error
        """
        try:
            full_path = os.path.join(self.storage_dir, file_path)
            
            if not os.path.exists(full_path):
                logging.warning(f"Secure file not found: {file_path}")
                return None
            
            # Read encrypted data
            with open(full_path, 'r', encoding='utf-8') as f:
                encrypted_data = f.read()
            
            # Decrypt data
            decrypted_data = self.encryption_manager.decrypt_data(encrypted_data, return_dict=return_dict)
            
            self.storage_stats["files_decrypted"] += 1
            
            return decrypted_data
            
        except Exception as e:
            self.storage_stats["storage_errors"] += 1
            logging.error(f"Error loading secure file {file_path}: {e}")
            return None
    
    def delete_secure_file(self, file_path: str) -> bool:
        """
        Securely delete an encrypted file
        
        Args:
            file_path: Relative path within secure storage
            
        Returns:
            True if deletion successful, False otherwise
        """
        try:
            full_path = os.path.join(self.storage_dir, file_path)
            
            if not os.path.exists(full_path):
                logging.warning(f"File not found for deletion: {file_path}")
                return False
            
            # Secure deletion - overwrite with random data first
            file_size = os.path.getsize(full_path)
            with open(full_path, 'wb') as f:
                f.write(os.urandom(file_size))
                f.flush()
                os.fsync(f.fileno())
            
            # Remove file
            os.remove(full_path)
            
            logging.info(f"Securely deleted file: {file_path}")
            return True
            
        except Exception as e:
            self.storage_stats["storage_errors"] += 1
            logging.error(f"Error deleting secure file {file_path}: {e}")
            return False
    
    def store_secure_data(
        self, 
        data_id: str, 
        category: str, 
        data_type: str, 
        data: Dict[str, Any],
        metadata: Optional[Dict[str, Any]] = None
    ) -> bool:
        """
        Store data securely in database
        
        Args:
            data_id: Unique identifier for the data
            category: Category of data (e.g., "user_profile", "conversation")
            data_type: Type of data (e.g., "profile", "exchange")
            data: Data to store
            metadata: Optional metadata
            
        Returns:
            True if storage successful, False otherwise
        """
        try:
            # Encrypt data
            encrypted_data = self.encryption_manager.encrypt_data(data)
            
            # Encrypt metadata if provided
            encrypted_metadata = None
            if metadata:
                encrypted_metadata = self.encryption_manager.encrypt_data(metadata)
            
            current_time = datetime.now(timezone.utc).isoformat()
            
            with sqlite3.connect(self.db_path) as conn:
                # Check if record exists
                cursor = conn.execute("SELECT id FROM secure_storage WHERE id = ?", (data_id,))
                exists = cursor.fetchone() is not None
                
                if exists:
                    # Update existing record
                    conn.execute("""
                        UPDATE secure_storage 
                        SET category = ?, data_type = ?, encrypted_data = ?, 
                            metadata = ?, updated_at = ?
                        WHERE id = ?
                    """, (category, data_type, encrypted_data, encrypted_metadata, current_time, data_id))
                else:
                    # Insert new record
                    conn.execute("""
                        INSERT INTO secure_storage 
                        (id, category, data_type, encrypted_data, metadata, created_at, updated_at)
                        VALUES (?, ?, ?, ?, ?, ?, ?)
                    """, (data_id, category, data_type, encrypted_data, encrypted_metadata, current_time, current_time))
                
                conn.commit()
            
            self.storage_stats["database_operations"] += 1
            logging.info(f"Securely stored data: {data_id}")
            
            return True
            
        except Exception as e:
            self.storage_stats["storage_errors"] += 1
            logging.error(f"Error storing secure data {data_id}: {e}")
            return False
    
    def load_secure_data(self, data_id: str) -> Optional[Dict[str, Any]]:
        """
        Load data from secure database
        
        Args:
            data_id: Unique identifier for the data
            
        Returns:
            Decrypted data or None if not found/error
        """
        try:
            with sqlite3.connect(self.db_path) as conn:
                conn.row_factory = sqlite3.Row
                
                cursor = conn.execute("""
                    SELECT encrypted_data, metadata, access_count 
                    FROM secure_storage 
                    WHERE id = ?
                """, (data_id,))
                
                row = cursor.fetchone()
                if not row:
                    return None
                
                # Decrypt data
                decrypted_data = self.encryption_manager.decrypt_data(row['encrypted_data'], return_dict=True)
                
                # Decrypt metadata if present
                decrypted_metadata = None
                if row['metadata']:
                    decrypted_metadata = self.encryption_manager.decrypt_data(row['metadata'], return_dict=True)
                
                # Update access count and timestamp
                conn.execute("""
                    UPDATE secure_storage 
                    SET access_count = ?, last_accessed = ?
                    WHERE id = ?
                """, (row['access_count'] + 1, datetime.now(timezone.utc).isoformat(), data_id))
                
                conn.commit()
                
                # Return data with metadata
                result = {
                    "data": decrypted_data,
                    "metadata": decrypted_metadata
                }
                
                self.storage_stats["database_operations"] += 1
                
                return result
                
        except Exception as e:
            self.storage_stats["storage_errors"] += 1
            logging.error(f"Error loading secure data {data_id}: {e}")
            return None
    
    def search_secure_data(
        self, 
        category: Optional[str] = None, 
        data_type: Optional[str] = None,
        limit: int = 100
    ) -> List[Dict[str, Any]]:
        """
        Search secure data by category and type
        
        Args:
            category: Category to filter by
            data_type: Data type to filter by
            limit: Maximum number of results
            
        Returns:
            List of matching data records (without decrypted content)
        """
        try:
            with sqlite3.connect(self.db_path) as conn:
                conn.row_factory = sqlite3.Row
                
                # Build query
                conditions = []
                params = []
                
                if category:
                    conditions.append("category = ?")
                    params.append(category)
                
                if data_type:
                    conditions.append("data_type = ?")
                    params.append(data_type)
                
                where_clause = " AND ".join(conditions) if conditions else "1=1"
                
                query = f"""
                    SELECT id, category, data_type, created_at, updated_at, 
                           access_count, last_accessed
                    FROM secure_storage 
                    WHERE {where_clause}
                    ORDER BY updated_at DESC 
                    LIMIT ?
                """
                params.append(limit)
                
                cursor = conn.execute(query, params)
                rows = cursor.fetchall()
                
                results = []
                for row in rows:
                    results.append({
                        "id": row['id'],
                        "category": row['category'],
                        "data_type": row['data_type'],
                        "created_at": row['created_at'],
                        "updated_at": row['updated_at'],
                        "access_count": row['access_count'],
                        "last_accessed": row['last_accessed']
                    })
                
                return results
                
        except Exception as e:
            self.storage_stats["storage_errors"] += 1
            logging.error(f"Error searching secure data: {e}")
            return []
    
    def delete_secure_data(self, data_id: str) -> bool:
        """
        Delete data from secure database
        
        Args:
            data_id: Unique identifier for the data
            
        Returns:
            True if deletion successful, False otherwise
        """
        try:
            with sqlite3.connect(self.db_path) as conn:
                cursor = conn.execute("DELETE FROM secure_storage WHERE id = ?", (data_id,))
                deleted_count = cursor.rowcount
                conn.commit()
                
                if deleted_count > 0:
                    logging.info(f"Deleted secure data: {data_id}")
                    return True
                else:
                    logging.warning(f"No data found to delete: {data_id}")
                    return False
                    
        except Exception as e:
            self.storage_stats["storage_errors"] += 1
            logging.error(f"Error deleting secure data {data_id}: {e}")
            return False
    
    def cleanup_expired_data(self, retention_days: int = 90) -> int:
        """
        Clean up old data based on retention policy
        
        Args:
            retention_days: Number of days to retain data
            
        Returns:
            Number of records deleted
        """
        try:
            cutoff_date = datetime.now(timezone.utc).replace(hour=0, minute=0, second=0, microsecond=0)
            cutoff_date = cutoff_date.replace(day=cutoff_date.day - retention_days)
            cutoff_str = cutoff_date.isoformat()
            
            with sqlite3.connect(self.db_path) as conn:
                cursor = conn.execute("""
                    DELETE FROM secure_storage 
                    WHERE created_at < ?
                """, (cutoff_str,))
                
                deleted_count = cursor.rowcount
                conn.commit()
                
                if deleted_count > 0:
                    logging.info(f"Cleaned up {deleted_count} expired secure data records")
                
                return deleted_count
                
        except Exception as e:
            self.storage_stats["storage_errors"] += 1
            logging.error(f"Error cleaning up expired data: {e}")
            return 0
    
    def get_storage_stats(self) -> Dict[str, Any]:
        """Get storage operation statistics"""
        try:
            with sqlite3.connect(self.db_path) as conn:
                # Get database statistics
                cursor = conn.execute("SELECT COUNT(*) FROM secure_storage")
                total_records = cursor.fetchone()[0]
                
                cursor = conn.execute("""
                    SELECT category, COUNT(*) 
                    FROM secure_storage 
                    GROUP BY category
                """)
                category_counts = dict(cursor.fetchall())
                
                # Get file statistics
                file_count = 0
                total_size = 0
                
                for root, dirs, files in os.walk(self.storage_dir):
                    for file in files:
                        if file.endswith('.db'):
                            continue  # Skip database file
                        file_path = os.path.join(root, file)
                        file_count += 1
                        total_size += os.path.getsize(file_path)
                
                stats = self.storage_stats.copy()
                stats.update({
                    "database_records": total_records,
                    "records_by_category": category_counts,
                    "secure_files": file_count,
                    "total_file_size_bytes": total_size,
                    "storage_directory": self.storage_dir
                })
                
                return stats
                
        except Exception as e:
            logging.error(f"Error getting storage stats: {e}")
            return self.storage_stats.copy()
    
    def verify_storage_integrity(self) -> Dict[str, Any]:
        """
        Verify integrity of stored data
        
        Returns:
            Integrity verification report
        """
        integrity_report = {
            "total_records": 0,
            "valid_records": 0,
            "corrupted_records": 0,
            "decryption_errors": 0,
            "issues": []
        }
        
        try:
            with sqlite3.connect(self.db_path) as conn:
                conn.row_factory = sqlite3.Row
                
                cursor = conn.execute("SELECT id, encrypted_data FROM secure_storage")
                
                for row in cursor.fetchall():
                    integrity_report["total_records"] += 1
                    
                    try:
                        # Try to decrypt data
                        self.encryption_manager.decrypt_data(row['encrypted_data'])
                        integrity_report["valid_records"] += 1
                        
                    except Exception as e:
                        integrity_report["corrupted_records"] += 1
                        integrity_report["decryption_errors"] += 1
                        integrity_report["issues"].append({
                            "record_id": row['id'],
                            "error": str(e)
                        })
                
        except Exception as e:
            integrity_report["issues"].append({
                "error": f"Database access error: {str(e)}"
            })
        
        return integrity_report