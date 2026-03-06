# File 1: chatbot/embedding_cache.py
"""
Embedding Cache Manager
Handles caching and automatic regeneration of FAQ embeddings
"""

import numpy as np
import os
import hashlib
import json
from datetime import datetime
from typing import Optional, Tuple, List


class EmbeddingCache:
    """
    Manages FAQ embeddings with automatic cache invalidation
    """
    
    def __init__(self, cache_dir: str = 'cache'):
        self.cache_dir = cache_dir
        self.embeddings_file = os.path.join(cache_dir, 'faq_embeddings.npy')
        self.metadata_file = os.path.join(cache_dir, 'metadata.json')
        
        # Create cache directory if it doesn't exist
        os.makedirs(cache_dir, exist_ok=True)
    
    def _calculate_csv_hash(self, csv_path: str) -> str:
        """
        Calculate MD5 hash of CSV file to detect changes
        """
        hash_md5 = hashlib.md5()
        try:
            with open(csv_path, 'rb') as f:
                # Read in chunks for large files
                for chunk in iter(lambda: f.read(4096), b""):
                    hash_md5.update(chunk)
            return hash_md5.hexdigest()
        except FileNotFoundError:
            return ""
    
    def _load_metadata(self) -> Optional[dict]:
        """Load cache metadata"""
        if not os.path.exists(self.metadata_file):
            return None
        
        try:
            with open(self.metadata_file, 'r') as f:
                return json.load(f)
        except:
            return None
    
    def _save_metadata(self, csv_hash: str, model_version: str, count: int, dimensions: int):
        """Save cache metadata"""
        metadata = {
            'csv_hash': csv_hash,
            'model_version': model_version,
            'count': count,
            'dimensions': dimensions,
            'created_at': datetime.now().isoformat(),
        }
        
        with open(self.metadata_file, 'w') as f:
            json.dump(metadata, f, indent=2)
    
    def should_regenerate(self, csv_path: str, model_version: str) -> Tuple[bool, str]:
        """
        Check if embeddings should be regenerated
        
        Returns:
            (should_regenerate: bool, reason: str)
        """
        # Check if cache files exist
        if not os.path.exists(self.embeddings_file):
            return True, "Cache file doesn't exist"
        
        if not os.path.exists(self.metadata_file):
            return True, "Metadata file doesn't exist"
        
        # Load metadata
        metadata = self._load_metadata()
        if not metadata:
            return True, "Failed to load metadata"
        
        # Check CSV hash (detect CSV changes)
        current_hash = self._calculate_csv_hash(csv_path)
        cached_hash = metadata.get('csv_hash', '')
        
        if current_hash != cached_hash:
            return True, "CSV file has changed"
        
        # Check model version
        if metadata.get('model_version') != model_version:
            return True, f"Model version changed from {metadata.get('model_version')} to {model_version}"
        
        # Cache is valid
        return False, "Cache is valid"
    
    def save(
        self, 
        embeddings: np.ndarray, 
        csv_path: str, 
        model_version: str
    ) -> None:
        """
        Save embeddings and metadata to cache
        
        Args:
            embeddings: NumPy array of embeddings
            csv_path: Path to CSV file (for hash calculation)
            model_version: Version of embedding model used
        """
        # Save embeddings
        np.save(self.embeddings_file, embeddings)
        
        # Calculate CSV hash
        csv_hash = self._calculate_csv_hash(csv_path)
        
        # Save metadata
        self._save_metadata(
            csv_hash=csv_hash,
            model_version=model_version,
            count=len(embeddings),
            dimensions=embeddings.shape[1]
        )
        
        print(f"💾 Cached {len(embeddings)} embeddings")
        print(f"   File: {self.embeddings_file}")
        print(f"   Size: {os.path.getsize(self.embeddings_file) / 1024:.1f} KB")
    
    def load(self) -> Optional[np.ndarray]:
        """
        Load embeddings from cache
        
        Returns:
            NumPy array of embeddings or None if cache doesn't exist
        """
        if not os.path.exists(self.embeddings_file):
            return None
        
        try:
            embeddings = np.load(self.embeddings_file)
            metadata = self._load_metadata()
            
            print(f"📦 Loaded {len(embeddings)} embeddings from cache")
            if metadata:
                print(f"   Model: {metadata.get('model_version')}")
                print(f"   Created: {metadata.get('created_at')}")
            
            return embeddings
        except Exception as e:
            print(f"❌ Failed to load cache: {e}")
            return None
    
    def clear(self) -> None:
        """Clear all cache files"""
        files_removed = 0
        
        if os.path.exists(self.embeddings_file):
            os.remove(self.embeddings_file)
            files_removed += 1
        
        if os.path.exists(self.metadata_file):
            os.remove(self.metadata_file)
            files_removed += 1
        
        if files_removed > 0:
            print(f"🗑️ Cleared cache ({files_removed} files)")
        else:
            print("ℹ️ Cache already empty")
    
    def get_info(self) -> dict:
        """Get cache information"""
        metadata = self._load_metadata()
        
        if not metadata or not os.path.exists(self.embeddings_file):
            return {
                'exists': False,
                'message': 'Cache not found'
            }
        
        file_size = os.path.getsize(self.embeddings_file)
        
        return {
            'exists': True,
            'count': metadata.get('count'),
            'dimensions': metadata.get('dimensions'),
            'model_version': metadata.get('model_version'),
            'created_at': metadata.get('created_at'),
            'csv_hash': metadata.get('csv_hash'),
            'file_size_kb': file_size / 1024,
            'file_path': self.embeddings_file
        }