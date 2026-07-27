"""Rate limit local de janela deslizante para as superfícies públicas caras.

É deliberadamente pequeno para o monólito local: lock + deque em memória. Ao hospedar, o mesmo
contrato pode ser trocado por Redis no edge sem mudar os routers.
"""

import threading
import time
from collections import defaultdict, deque
from typing import Callable


class SlidingWindowLimiter:
    def __init__(self, clock: Callable[[], float] = time.monotonic):
        self._clock = clock
        self._hits = defaultdict(deque)
        self._lock = threading.Lock()

    def allow(self, key: str, limit: int, window_s: int) -> bool:
        now = self._clock()
        with self._lock:
            hits = self._hits[key]
            cutoff = now - window_s
            while hits and hits[0] <= cutoff:
                hits.popleft()
            if len(hits) >= limit:
                return False
            hits.append(now)
            return True


rate_limiter = SlidingWindowLimiter()
