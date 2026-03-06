"""
Resilience patterns for the AgentTwister agent framework.

Provides exponential backoff and circuit breaker patterns to handle
failures gracefully when calling external services (LLMs, databases, HTTP APIs).
"""

import asyncio
import logging
import time
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from enum import Enum
from typing import Awaitable, Callable, TypeVar, Optional, Any

logger = logging.getLogger(__name__)

T = TypeVar("T")


class CircuitBreakerState(Enum):
    """Circuit breaker states."""
    CLOSED = "closed"  # Normal operation, requests pass through
    OPEN = "open"      # Circuit is open, requests fail immediately
    HALF_OPEN = "half_open"  # Testing if service has recovered


@dataclass
class CircuitBreakerConfig:
    """Configuration for circuit breaker behavior."""
    failure_threshold: int = 5  # Number of failures before opening
    success_threshold: int = 2  # Number of successes to close from half-open
    timeout_seconds: float = 60.0  # How long to stay open before half-open
    window_seconds: float = 60.0  # Time window for counting failures


@dataclass
class CircuitBreakerStats:
    """Statistics for circuit breaker monitoring."""
    state: CircuitBreakerState = CircuitBreakerState.CLOSED
    failure_count: int = 0
    success_count: int = 0
    last_failure_time: Optional[datetime] = None
    last_success_time: Optional[datetime] = None
    opened_at: Optional[datetime] = None
    total_requests: int = 0
    total_failures: int = 0


class CircuitBreakerOpenError(Exception):
    """Raised when circuit breaker is open and request is rejected."""
    def __init__(self, state: CircuitBreakerState, opened_at: Optional[datetime] = None):
        self.state = state
        self.opened_at = opened_at
        message = f"Circuit breaker is {state.value}"
        if opened_at:
            wait_time = timedelta(seconds=60) - (datetime.utcnow() - opened_at)
            message += f". Retry in {wait_time.total_seconds():.1f}s"
        super().__init__(message)


class CircuitBreaker:
    """
    Circuit Breaker pattern implementation.

    Prevents cascading failures by failing fast when a service is
    experiencing issues. Automatically recovers when service heals.

    Example:
        breaker = CircuitBreaker(
            name="llm-service",
            config=CircuitBreakerConfig(failure_threshold=3, timeout_seconds=30)
        )

        try:
            result = await breaker.call(llm_service.generate, prompt)
        except CircuitBreakerOpenError:
            # Handle circuit open - use fallback or cached response
            result = get_cached_response()
    """

    def __init__(
        self,
        name: str,
        config: Optional[CircuitBreakerConfig] = None,
    ):
        """
        Initialize circuit breaker.

        Args:
            name: Name of the circuit breaker (for logging/metrics)
            config: Circuit breaker configuration
        """
        self.name = name
        self.config = config or CircuitBreakerConfig()
        self._stats = CircuitBreakerStats()
        self._lock = asyncio.Lock()

    @property
    def state(self) -> CircuitBreakerState:
        """Get current circuit breaker state."""
        return self._stats.state

    @property
    def stats(self) -> CircuitBreakerStats:
        """Get circuit breaker statistics (copy)."""
        # Return a copy to prevent external mutation
        from dataclasses import replace
        return replace(self._stats)

    async def call(
        self,
        func: Callable[..., Awaitable[T]],
        *args: Any,
        **kwargs: Any,
    ) -> T:
        """
        Execute function through circuit breaker.

        Args:
            func: Async function to call
            *args: Positional arguments for func
            **kwargs: Keyword arguments for func

        Returns:
            Result of func

        Raises:
            CircuitBreakerOpenError: If circuit is open
            Exception: Any exception from func (counts as failure)
        """
        async with self._lock:
            if self._should_attempt_reset():
                self._stats.state = CircuitBreakerState.HALF_OPEN
                logger.info(f"CircuitBreaker '{self.name}' entering HALF_OPEN state")

            if self._stats.state == CircuitBreakerState.OPEN:
                raise CircuitBreakerOpenError(
                    self._stats.state,
                    self._stats.opened_at,
                )

        try:
            result = await func(*args, **kwargs)
            await self._on_success()
            return result
        except Exception as e:
            await self._on_failure()
            raise e

    def call_sync(
        self,
        func: Callable[..., T],
        *args: Any,
        **kwargs: Any,
    ) -> T:
        """
        Execute synchronous function through circuit breaker.

        Args:
            func: Synchronous function to call
            *args: Positional arguments for func
            **kwargs: Keyword arguments for func

        Returns:
            Result of func

        Raises:
            CircuitBreakerOpenError: If circuit is open
            Exception: Any exception from func (counts as failure)
        """
        if self._stats.state == CircuitBreakerState.OPEN:
            if self._should_attempt_reset():
                self._stats.state = CircuitBreakerState.HALF_OPEN
                logger.info(f"CircuitBreaker '{self.name}' entering HALF_OPEN state")
            else:
                raise CircuitBreakerOpenError(
                    self._stats.state,
                    self._stats.opened_at,
                )

        try:
            result = func(*args, **kwargs)
            self._on_success_sync()
            return result
        except Exception as e:
            self._on_failure_sync()
            raise e

    def _should_attempt_reset(self) -> bool:
        """Check if enough time has passed to attempt reset."""
        if self._stats.state != CircuitBreakerState.OPEN:
            return False
        if self._stats.opened_at is None:
            return True
        elapsed = datetime.utcnow() - self._stats.opened_at
        return elapsed.total_seconds() >= self.config.timeout_seconds

    async def _on_success(self) -> None:
        """Handle successful execution."""
        async with self._lock:
            self._stats.total_requests += 1
            self._stats.success_count += 1
            self._stats.last_success_time = datetime.utcnow()

            if self._stats.state == CircuitBreakerState.HALF_OPEN:
                if self._stats.success_count >= self.config.success_threshold:
                    self._stats.state = CircuitBreakerState.CLOSED
                    self._stats.failure_count = 0
                    self._stats.success_count = 0
                    self._stats.opened_at = None
                    logger.info(f"CircuitBreaker '{self.name}' closed (service recovered)")

    def _on_success_sync(self) -> None:
        """Handle successful execution (sync version)."""
        self._stats.total_requests += 1
        self._stats.success_count += 1
        self._stats.last_success_time = datetime.utcnow()

        if self._stats.state == CircuitBreakerState.HALF_OPEN:
            if self._stats.success_count >= self.config.success_threshold:
                self._stats.state = CircuitBreakerState.CLOSED
                self._stats.failure_count = 0
                self._stats.success_count = 0
                self._stats.opened_at = None
                logger.info(f"CircuitBreaker '{self.name}' closed (service recovered)")

    async def _on_failure(self) -> None:
        """Handle failed execution."""
        async with self._lock:
            self._stats.total_requests += 1
            self._stats.total_failures += 1
            self._stats.failure_count += 1
            self._stats.last_failure_time = datetime.utcnow()

            if self._stats.state == CircuitBreakerState.HALF_OPEN:
                # Failed during recovery, go back to open
                self._stats.state = CircuitBreakerState.OPEN
                self._stats.opened_at = datetime.utcnow()
                self._stats.success_count = 0
                logger.warning(f"CircuitBreaker '{self.name}' back to OPEN (recovery failed)")
            elif self._stats.failure_count >= self.config.failure_threshold:
                # Threshold reached, open the circuit
                self._stats.state = CircuitBreakerState.OPEN
                self._stats.opened_at = datetime.utcnow()
                logger.error(
                    f"CircuitBreaker '{self.name}' opened after "
                    f"{self._stats.failure_count} failures"
                )

    def _on_failure_sync(self) -> None:
        """Handle failed execution (sync version)."""
        self._stats.total_requests += 1
        self._stats.total_failures += 1
        self._stats.failure_count += 1
        self._stats.last_failure_time = datetime.utcnow()

        if self._stats.state == CircuitBreakerState.HALF_OPEN:
            self._stats.state = CircuitBreakerState.OPEN
            self._stats.opened_at = datetime.utcnow()
            self._stats.success_count = 0
            logger.warning(f"CircuitBreaker '{self.name}' back to OPEN (recovery failed)")
        elif self._stats.failure_count >= self.config.failure_threshold:
            self._stats.state = CircuitBreakerState.OPEN
            self._stats.opened_at = datetime.utcnow()
            logger.error(
                f"CircuitBreaker '{self.name}' opened after "
                f"{self._stats.failure_count} failures"
            )

    def reset(self) -> None:
        """Manually reset circuit breaker to closed state."""
        self._stats = CircuitBreakerStats()
        logger.info(f"CircuitBreaker '{self.name}' manually reset")


@dataclass
class ExponentialBackoffConfig:
    """Configuration for exponential backoff behavior."""
    initial_delay: float = 1.0  # Initial delay in seconds
    max_delay: float = 60.0  # Maximum delay in seconds
    multiplier: float = 2.0  # Backoff multiplier (exponential factor)
    jitter: bool = True  # Add random jitter to prevent thundering herd
    jitter_factor: float = 0.1  # Jitter as fraction of delay (0.1 = ±10%)
    max_attempts: int = 5  # Maximum number of retry attempts


class ExponentialBackoff:
    """
    Exponential backoff with jitter for retrying failed operations.

    Implements full jitter strategy to prevent thundering herd problem
    when multiple services retry simultaneously.

    Example:
        backoff = ExponentialBackoff(max_attempts=3)

        async for attempt in backoff:
            try:
                result = await llm_service.generate(prompt)
                return result
            except Exception as e:
                if attempt == backoff.max_attempts - 1:
                    raise
                logger.warning(f"Attempt {attempt + 1} failed, retrying...")
    """

    def __init__(
        self,
        initial_delay: float = 1.0,
        max_delay: float = 60.0,
        multiplier: float = 2.0,
        jitter: bool = True,
        max_attempts: int = 5,
    ):
        """
        Initialize exponential backoff.

        Args:
            initial_delay: Initial delay before first retry (seconds)
            max_delay: Maximum delay between retries (seconds)
            multiplier: Exponential backoff multiplier
            jitter: Whether to add random jitter
            max_attempts: Maximum number of attempts
        """
        self.config = ExponentialBackoffConfig(
            initial_delay=initial_delay,
            max_delay=max_delay,
            multiplier=multiplier,
            jitter=jitter,
            max_attempts=max_attempts,
        )
        self._current_attempt = 0

    def __aiter__(self) -> "ExponentialBackoff":
        """Support async iteration over retry attempts."""
        self._current_attempt = 0
        return self

    async def __anext__(self) -> int:
        """
        Get next attempt number, sleeping between attempts.

        Returns:
            Current attempt number (0-indexed)

        Raises:
            StopAsyncIteration: When max attempts reached
        """
        if self._current_attempt >= self.config.max_attempts:
            raise StopAsyncIteration

        attempt = self._current_attempt
        self._current_attempt += 1

        # Sleep before retry (but not before first attempt)
        if attempt > 0:
            delay = self._calculate_delay(attempt)
            logger.debug(f"ExponentialBackoff: sleeping {delay:.2f}s before attempt {attempt + 1}")
            await asyncio.sleep(delay)

        return attempt

    def __iter__(self) -> "ExponentialBackoff":
        """Support synchronous iteration for non-async contexts."""
        self._current_attempt = 0
        return self

    def __next__(self) -> int:
        """
        Get next attempt number for sync iteration.

        Returns:
            Current attempt number (0-indexed)

        Raises:
            StopIteration: When max attempts reached
        """
        if self._current_attempt >= self.config.max_attempts:
            raise StopIteration

        attempt = self._current_attempt
        self._current_attempt += 1

        # Sleep before retry (but not before first attempt)
        if attempt > 0:
            delay = self._calculate_delay(attempt)
            logger.debug(f"ExponentialBackoff: sleeping {delay:.2f}s before attempt {attempt + 1}")
            time.sleep(delay)

        return attempt

    def _calculate_delay(self, attempt: int) -> float:
        """
        Calculate delay for given attempt number.

        Uses exponential backoff with optional jitter.

        Args:
            attempt: Attempt number (0-indexed)

        Returns:
            Delay in seconds
        """
        # Calculate base delay: initial * (multiplier ^ (attempt - 1))
        base_delay = self.config.initial_delay * (
            self.config.multiplier ** (attempt - 1)
        )
        # Cap at max delay
        delay = min(base_delay, self.config.max_delay)

        # Add jitter if enabled
        if self.config.jitter:
            # Full jitter: random value between 0 and delay
            # Plus jitter_factor to add some noise
            import random
            jitter_range = delay * self.config.jitter_factor
            delay = random.uniform(
                max(0, delay - jitter_range),
                delay + jitter_range,
            )

        return delay

    @property
    def current_attempt(self) -> int:
        """Get current attempt number (for logging)."""
        return self._current_attempt

    @property
    def max_attempts(self) -> int:
        """Get maximum attempts."""
        return self.config.max_attempts

    def reset(self) -> None:
        """Reset attempt counter."""
        self._current_attempt = 0


async def retry_with_backoff(
    func: Callable[..., Awaitable[T]],
    *args: Any,
    backoff: Optional[ExponentialBackoff] = None,
    **kwargs: Any,
) -> T:
    """
    Retry an async function with exponential backoff.

    Convenience function for simple retry cases.

    Args:
        func: Async function to retry
        *args: Positional arguments for func
        backoff: ExponentialBackoff instance (uses default if None)
        **kwargs: Keyword arguments for func

    Returns:
        Result of func

    Raises:
        Exception: Last exception from func if all attempts fail

    Example:
        result = await retry_with_backoff(
            llm_service.generate,
            "Hello, world!",
            backoff=ExponentialBackoff(max_attempts=3)
        )
    """
    if backoff is None:
        backoff = ExponentialBackoff()

    last_exception: Optional[Exception] = None

    async for attempt in backoff:
        try:
            return await func(*args, **kwargs)
        except Exception as e:
            last_exception = e
            logger.warning(
                f"retry_with_backoff: attempt {attempt + 1}/{backoff.max_attempts} failed: {e}"
            )

    # All attempts exhausted
    assert last_exception is not None
    raise last_exception
