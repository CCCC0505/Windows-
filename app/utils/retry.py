from __future__ import annotations

import asyncio
import time
from dataclasses import dataclass
from typing import Awaitable, Callable, TypeVar

T = TypeVar("T")


@dataclass
class RetryPolicy:
    max_retries: int = 2
    base_delay: float = 0.25
    factor: float = 2.0
    max_delay: float = 2.0


class CircuitBreakerOpen(Exception):
    pass


class CircuitBreaker:
    def __init__(self, failure_threshold: int = 5, recovery_seconds: float = 20.0) -> None:
        self.failure_threshold = failure_threshold
        self.recovery_seconds = recovery_seconds
        self.failures = 0
        self.opened_at = 0.0

    def allow(self) -> bool:
        if self.failures < self.failure_threshold:
            return True
        elapsed = time.monotonic() - self.opened_at
        if elapsed >= self.recovery_seconds:
            self.failures = 0
            self.opened_at = 0.0
            return True
        return False

    def on_success(self) -> None:
        self.failures = 0
        self.opened_at = 0.0

    def on_failure(self) -> None:
        self.failures += 1
        if self.failures >= self.failure_threshold and self.opened_at == 0.0:
            self.opened_at = time.monotonic()


async def with_retry(
    func: Callable[[], Awaitable[T]],
    policy: RetryPolicy,
    breaker: CircuitBreaker | None = None,
) -> T:
    if breaker is not None and not breaker.allow():
        raise CircuitBreakerOpen("circuit breaker is open")

    last_error: Exception | None = None
    delay = policy.base_delay
    for attempt in range(policy.max_retries + 1):
        try:
            result = await func()
            if breaker is not None:
                breaker.on_success()
            return result
        except Exception as exc:  # noqa: BLE001
            last_error = exc
            if breaker is not None:
                breaker.on_failure()
            if attempt >= policy.max_retries:
                break
            await asyncio.sleep(delay)
            delay = min(policy.max_delay, delay * policy.factor)

    assert last_error is not None
    raise last_error
