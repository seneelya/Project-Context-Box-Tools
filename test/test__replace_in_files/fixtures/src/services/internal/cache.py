"""In-memory caching layer for frequently accessed data."""

import time


class CacheService:
    """Simple TTL-based cache implementation.
    
    Stores key-value pairs with optional expiration times.
    Automatically removes expired entries on access.
    """
    
    def __init__(self, default_ttl=300):
        self.store = {}
        self.default_ttl = default_ttl
        
    def get(self, key):
        """Retrieve value from cache if not expired."""
        entry = self.store.get(key)
        if entry is None:
            return None
            
        timestamp, value, ttl = entry
        if time.time() - timestamp > ttl:
            del self.store[key]
            return None
        return value
        
    def set(self, key, value, ttl=None):
        """Store a value in cache with optional TTL override."""
        actual_ttl = ttl or self.default_ttl
        self.store[key] = (time.time(), value, actual_ttl)
        
    def delete(self, key):
        """Remove an entry from the cache explicitly."""
        self.store.pop(key, None)
        
    def clear_all(self):
        """Reset the entire cache — removes all stored entries immediately."""
        self.store.clear()


# Global singleton instance for application-wide caching
cache = CacheService(default_ttl=600)
