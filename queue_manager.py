import asyncio
from collections import deque
from dataclasses import dataclass
from typing import Callable
import time

@dataclass
class QueueItem:
    user_id: int
    url: str
    quality: str
    audio_only: bool
    callback: Callable
    added_at: float
    status: str = 'waiting'

class DownloadQueue:
    def __init__(self, max_concurrent=3):
        self.queue = deque()
        self.processing = {}
        self.max_concurrent = max_concurrent
        self.lock = asyncio.Lock()
        self.semaphore = asyncio.Semaphore(max_concurrent)

    async def add(self, user_id, url, quality, audio_only, callback):
        item = QueueItem(
            user_id=user_id,
            url=url,
            quality=quality,
            audio_only=audio_only,
            callback=callback,
            added_at=time.time()
        )

        async with self.lock:
            position = len(self.queue) + len(self.processing)
            self.queue.append(item)

        return item, position

    async def process_queue(self):
        while True:
            async with self.lock:
                if not self.queue:
                    await asyncio.sleep(1)
                    continue

                item = self.queue.popleft()
                item.status = 'processing'
                self.processing[item.user_id] = item

            async with self.semaphore:
                try:
                    await item.callback(item)
                    item.status = 'completed'
                except Exception as e:
                    item.status = 'failed'
                    print(f"Queue error: {e}")
                finally:
                    async with self.lock:
                        if item.user_id in self.processing:
                            del self.processing[item.user_id]

    def get_position(self, user_id):
        for i, item in enumerate(self.queue):
            if item.user_id == user_id:
                return i + 1
        return 0
