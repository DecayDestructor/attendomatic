"""
Redis client setup.

Planned for future use to store conversation context and improve
LLM multi-turn interaction quality.  Not actively used yet.
"""

import redis

redis_client = redis.Redis(host="localhost", port=6379, db=0)


def get_redis_client():
    """Return the shared Redis client instance."""
    return redis_client
