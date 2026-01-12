"""Utility functions for the Territory Planner app."""

import asyncio
import logging
from typing import TypeVar, Callable, Any
from functools import wraps

logger = logging.getLogger(__name__)

T = TypeVar('T')


async def retry_with_backoff(
    func: Callable[..., T],
    *args,
    max_retries: int = 3,
    base_delay: float = 2.0,
    max_delay: float = 30.0,
    exceptions: tuple = (Exception,),
    **kwargs
) -> T:
    """
    Retry an async function with exponential backoff.

    Args:
        func: The async function to retry
        *args: Positional arguments for the function
        max_retries: Maximum number of retry attempts
        base_delay: Initial delay between retries (seconds)
        max_delay: Maximum delay between retries (seconds)
        exceptions: Tuple of exceptions to catch and retry
        **kwargs: Keyword arguments for the function

    Returns:
        Result from the function

    Raises:
        The last exception encountered if all retries fail
    """
    last_exception = None

    for attempt in range(max_retries + 1):
        try:
            return await func(*args, **kwargs)
        except exceptions as e:
            last_exception = e

            if attempt == max_retries:
                logger.error(f"All {max_retries} retry attempts failed for {func.__name__}: {str(e)}")
                raise

            # Calculate delay with exponential backoff
            delay = min(base_delay * (2 ** attempt), max_delay)
            logger.warning(
                f"Attempt {attempt + 1}/{max_retries + 1} failed for {func.__name__}: {str(e)}. "
                f"Retrying in {delay:.1f}s..."
            )
            await asyncio.sleep(delay)

    # Should never reach here, but just in case
    raise last_exception


def estimate_tavily_cost(credits_used: float) -> float:
    """
    Estimate cost in USD for Tavily API credits.

    Args:
        credits_used: Number of Tavily credits consumed

    Returns:
        Estimated cost in USD
    """
    COST_PER_CREDIT = 0.008  # $0.008 per credit
    return credits_used * COST_PER_CREDIT


def format_cost(cost_usd: float) -> str:
    """
    Format cost in USD as a string.

    Args:
        cost_usd: Cost in USD

    Returns:
        Formatted cost string (e.g., "$0.016")
    """
    if cost_usd < 0.001:
        return "< $0.001"
    return f"${cost_usd:.3f}"


def format_duration(seconds: float) -> str:
    """
    Format duration in seconds as human-readable string.

    Args:
        seconds: Duration in seconds

    Returns:
        Formatted duration string
    """
    if seconds < 60:
        return f"{seconds:.1f}s"
    minutes = seconds / 60
    if minutes < 60:
        return f"{minutes:.1f}m"
    hours = minutes / 60
    return f"{hours:.1f}h"
