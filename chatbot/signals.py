# chatbot/signals.py - Simplified for FAQ only

from django.dispatch import Signal
from django.core.signals import request_started
import os
import hashlib

# Custom signal for CSV changes
csv_changed = Signal()

# Store last known CSV hash
_csv_hash_cache = {}


def calculate_csv_hash(csv_path: str) -> str:
    """Calculate MD5 hash of CSV file"""
    if not os.path.exists(csv_path):
        return ""
    
    hash_md5 = hashlib.md5()
    with open(csv_path, 'rb') as f:
        for chunk in iter(lambda: f.read(4096), b""):
            hash_md5.update(chunk)
    return hash_md5.hexdigest()


# For now, CSV change detection is disabled
# Can be re-enabled later if needed