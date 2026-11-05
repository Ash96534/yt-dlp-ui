"""In-memory priority job queue with persistence hooks."""
from __future__ import annotations

import heapq
import threading
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional

PRIORITY_ORDER = {'high': 0, 'normal': 1, 'low': 2}


@dataclass(order=True)
class QueueItem:
    priority: int
    created_at: float
    job_id: str = field(compare=False)
    data: Any = field(compare=False)


class JobQueue:
    def __init__(self):
        self._heap: List[QueueItem] = []
        self._lock = threading.Lock()
        self._condition = threading.Condition(self._lock)
        self._jobs: Dict[str, QueueItem] = {}
        self._counter = 0

    def push(self, job_id: str, data: Any, priority: str = 'normal') -> None:
        prio = PRIORITY_ORDER.get(priority, 1)
        with self._lock:
            self._counter += 1
            item = QueueItem(prio, self._counter, job_id, data)
            heapq.heappush(self._heap, item)
            self._jobs[job_id] = item
            self._condition.notify()

    def pop(self, block: bool = True, timeout: Optional[float] = None) -> Optional[QueueItem]:
        with self._condition:
            while not self._heap:
                if not block:
                    return None
                self._condition.wait(timeout=timeout)
                if not self._heap:
                    return None
            item = heapq.heappop(self._heap)
            self._jobs.pop(item.job_id, None)
            return item

    def remove(self, job_id: str) -> bool:
        with self._lock:
            if job_id not in self._jobs:
                return False
            del self._jobs[job_id]
            return True

    def contains(self, job_id: str) -> bool:
        with self._lock:
            return job_id in self._jobs

    def list_jobs(self) -> List[str]:
        with self._lock:
            return list(self._jobs.keys())

    def __len__(self) -> int:
        with self._lock:
            return len(self._jobs)
