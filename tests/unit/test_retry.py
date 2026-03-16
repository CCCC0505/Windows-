import pytest

from app.utils.retry import CircuitBreaker, CircuitBreakerOpen, RetryPolicy, with_retry


@pytest.mark.asyncio
async def test_with_retry_eventually_succeeds() -> None:
    attempts = {"n": 0}

    async def flaky() -> str:
        attempts["n"] += 1
        if attempts["n"] < 3:
            raise RuntimeError("nope")
        return "ok"

    result = await with_retry(flaky, RetryPolicy(max_retries=3, base_delay=0.01))
    assert result == "ok"


@pytest.mark.asyncio
async def test_circuit_breaker_open() -> None:
    breaker = CircuitBreaker(failure_threshold=1, recovery_seconds=999)

    async def fail() -> str:
        raise RuntimeError("x")

    with pytest.raises(RuntimeError):
        await with_retry(fail, RetryPolicy(max_retries=0), breaker=breaker)

    with pytest.raises(CircuitBreakerOpen):
        await with_retry(fail, RetryPolicy(max_retries=0), breaker=breaker)

