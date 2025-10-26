import redis

redis_client = redis.Redis(host="localhost", port=6379, db=0)


def get_redis_client():
    return redis_client
