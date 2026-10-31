import logging
import threading
import time
from typing import Dict, Optional, Tuple

from app.config import settings

logger = logging.getLogger("sportshub.cache")


class CacheClient:
    """
    Unified Redis client with automatic in-memory dictionary fallback.
    Supports get, set, setnx, expire, and delete with TTL expiration.
    """

    def __init__(self) -> None:
        self._lock = threading.Lock()
        self._mem_store: Dict[str, Tuple[str, Optional[float]]] = {}
        self._redis = None
        self.backend_name = "memory"
        self._init_redis()

    def _init_redis(self) -> None:
        redis_url = (settings.REDIS_URL or "").strip()
        if not redis_url:
            return
        try:
            import redis  # type: ignore

            client = redis.Redis.from_url(
                redis_url,
                decode_responses=True,
                socket_connect_timeout=1.5,
                socket_timeout=1.5,
            )
            client.ping()
            self._redis = client
            self.backend_name = "redis"
            logger.info("Connected to Redis at %s", redis_url)
        except Exception as exc:
            logger.warning(
                "Redis unreachable (%s). Falling back to thread-safe in-memory cache.",
                exc,
            )
            self._redis = None
            self.backend_name = "memory"

    def _purge_expired_locked(self, key: str) -> None:
        entry = self._mem_store.get(key)
        if entry is not None:
            _, expires_at = entry
            if expires_at is not None and time.monotonic() >= expires_at:
                del self._mem_store[key]

    def get(self, key: str) -> Optional[str]:
        if self._redis is not None:
            try:
                return self._redis.get(key)
            except Exception:
                self._redis = None
                self.backend_name = "memory"

        with self._lock:
            self._purge_expired_locked(key)
            entry = self._mem_store.get(key)
            return entry[0] if entry else None

    def set(self, key: str, value: str, ex: Optional[int] = None) -> bool:
        if self._redis is not None:
            try:
                return bool(self._redis.set(key, value, ex=ex))
            except Exception:
                self._redis = None
                self.backend_name = "memory"

        with self._lock:
            expires_at = (time.monotonic() + ex) if ex is not None else None
            self._mem_store[key] = (str(value), expires_at)
            return True

    def setnx(self, key: str, value: str, ex: Optional[int] = None) -> bool:
        """
        Atomically set key to value if key does not exist.
        Optionally sets TTL in seconds (`ex`).
        """
        if self._redis is not None:
            try:
                res = self._redis.set(key, value, nx=True, ex=ex)
                return bool(res)
            except Exception:
                self._redis = None
                self.backend_name = "memory"

        with self._lock:
            self._purge_expired_locked(key)
            if key in self._mem_store:
                return False
            expires_at = (time.monotonic() + ex) if ex is not None else None
            self._mem_store[key] = (str(value), expires_at)
            return True

    def expire(self, key: str, seconds: int) -> bool:
        if self._redis is not None:
            try:
                return bool(self._redis.expire(key, seconds))
            except Exception:
                self._redis = None
                self.backend_name = "memory"

        with self._lock:
            self._purge_expired_locked(key)
            if key not in self._mem_store:
                return False
            val, _ = self._mem_store[key]
            self._mem_store[key] = (val, time.monotonic() + seconds)
            return True

    def delete(self, key: str) -> bool:
        if self._redis is not None:
            try:
                return bool(self._redis.delete(key))
            except Exception:
                self._redis = None
                self.backend_name = "memory"

        with self._lock:
            return self._mem_store.pop(key, None) is not None


cache = CacheClient()

