"""Shared Anthropic LLM client with usage tracking and budget enforcement.

Every LLM call goes through this module. It:
1. Checks the daily budget before calling
2. Calls the Anthropic Messages API
3. Records token usage and cost to llm_usage table
4. Returns both the response and usage metadata

Budget enforcement:
- If today's spend >= daily_budget_usd, raises BudgetExceededError
- The orchestrator catches this and transitions to paused_budget terminal state
- Budget warning threshold (default 0.8) logs a warning but continues

Pricing (as of 2026-03):
- Haiku 4.5:  $0.80/MTok input, $4.00/MTok output
- Sonnet 4:   $3.00/MTok input, $15.00/MTok output
- Opus 4.6:   $15.00/MTok input, $75.00/MTok output
"""

import asyncio
import logging
import time
from dataclasses import dataclass
from typing import Optional

import anthropic

try:
    from openai import OpenAI as _OpenAI
except ImportError:
    _OpenAI = None

from app.config import ANTHROPIC_API_KEY, load_policy

logger = logging.getLogger(__name__)

# Pricing per million tokens (input, output)
MODEL_PRICING = {
    "claude-haiku-4-5-20251001": (0.80, 4.00),
    "claude-sonnet-4-20250514": (3.00, 15.00),
    "claude-sonnet-4-6-20250415": (3.00, 15.00),
    "claude-opus-4-6": (15.00, 75.00),
    # OpenAI models
    "gpt-4o": (2.50, 10.00),
    "gpt-5.4": (2.50, 10.00),
    "gpt-5.4-mini": (0.40, 1.60),
}

# Retry config
MAX_LLM_RETRIES = 3
RETRY_BASE_DELAY = 1.0  # seconds, doubles each attempt

# Singleton clients
_client: Optional[anthropic.Anthropic] = None
_openai_client = None


class BudgetExceededError(Exception):
    """Raised when the daily LLM budget is exhausted."""

    def __init__(self, today_spend: float, daily_budget: float):
        self.today_spend = today_spend
        self.daily_budget = daily_budget
        super().__init__(
            f"Daily LLM budget exhausted: ${today_spend:.4f} spent "
            f"of ${daily_budget:.2f} limit"
        )


class LLMError(Exception):
    """Typed error for LLM failures."""

    def __init__(
        self, message: str, error_type: str = "llm_error", recoverable: bool = False
    ):
        super().__init__(message)
        self.error_type = error_type
        self.recoverable = recoverable


@dataclass
class LLMUsage:
    """Usage metadata from a single LLM call."""

    model: str
    input_tokens: int
    output_tokens: int
    cost_usd: float
    processing_seconds: float


@dataclass
class LLMResponse:
    """Full response from an LLM call."""

    text: str
    usage: LLMUsage
    stop_reason: str


def _get_client() -> anthropic.Anthropic:
    """Get or create the singleton Anthropic client."""
    global _client
    if _client is None:
        if not ANTHROPIC_API_KEY:
            raise LLMError(
                "ANTHROPIC_API_KEY not set",
                error_type="configuration_error",
                recoverable=False,
            )
        _client = anthropic.Anthropic(api_key=ANTHROPIC_API_KEY)
    return _client


def _is_openai_model(model: str) -> bool:
    """Check if a model ID is an OpenAI model."""
    return model.startswith("gpt-") or model.startswith("o3") or model.startswith("o4")


def _get_openai_client():
    """Get or create the singleton OpenAI client."""
    global _openai_client
    if _openai_client is None:
        if _OpenAI is None:
            raise LLMError(
                "openai package not installed. Run: pip install openai",
                error_type="configuration_error",
                recoverable=False,
            )
        import os

        api_key = os.environ.get("OPENAI_API_KEY", "")
        if not api_key:
            raise LLMError(
                "OPENAI_API_KEY not set",
                error_type="configuration_error",
                recoverable=False,
            )
        _openai_client = _OpenAI(api_key=api_key)
    return _openai_client


def compute_cost(model: str, input_tokens: int, output_tokens: int) -> float:
    """Compute cost in USD for a given model and token counts."""
    input_price, output_price = MODEL_PRICING.get(model, (3.00, 15.00))
    return (input_tokens * input_price + output_tokens * output_price) / 1_000_000


def check_budget(db) -> tuple[float, float, bool]:
    """Check today's spend against budget.

    Returns: (today_spend, daily_budget, is_over_budget)
    """
    spend_row = db.execute("""
        SELECT COALESCE(SUM(cost_usd), 0.0) as today_spend
        FROM llm_usage
        WHERE created_at >= date('now')
    """).fetchone()
    today_spend = spend_row["today_spend"] if spend_row else 0.0

    policy = load_policy()
    model_config = policy.get("model_config", {})
    daily_budget = model_config.get("daily_budget_usd", 10.0)
    warning_threshold = model_config.get("budget_warning_threshold", 0.8)

    is_over = today_spend >= daily_budget

    if (
        not is_over
        and daily_budget > 0
        and today_spend >= daily_budget * warning_threshold
    ):
        logger.warning(
            "Budget warning: $%.4f of $%.2f daily budget (%.0f%%)",
            today_spend,
            daily_budget,
            (today_spend / daily_budget) * 100,
        )

    return today_spend, daily_budget, is_over


def record_usage(
    db,
    communication_id: str,
    stage: str,
    model: str,
    input_tokens: int,
    output_tokens: int,
    cost_usd: float,
):
    """Record LLM usage to the llm_usage table."""
    db.execute(
        """
        INSERT INTO llm_usage (communication_id, stage, model, input_tokens, output_tokens, cost_usd)
        VALUES (?, ?, ?, ?, ?, ?)
    """,
        (communication_id, stage, model, input_tokens, output_tokens, cost_usd),
    )
    # db.commit()  # Removed: orchestrator savepoint handles commit


async def _call_with_retry(func, *args, **kwargs):
    """Retry an async function on recoverable LLMError with exponential backoff."""
    last_error = None
    for attempt in range(MAX_LLM_RETRIES):
        try:
            return await func(*args, **kwargs)
        except LLMError as e:
            last_error = e
            if not e.recoverable or attempt == MAX_LLM_RETRIES - 1:
                raise
            delay = RETRY_BASE_DELAY * (2**attempt)
            logger.warning(
                "LLM call failed (attempt %d/%d, retrying in %.1fs): %s",
                attempt + 1,
                MAX_LLM_RETRIES,
                delay,
                e,
            )
            await asyncio.sleep(delay)
    raise last_error  # should not reach here


async def _call_llm_once(
    db,
    communication_id: str,
    stage: str,
    model: str,
    system_prompt: str,
    user_prompt: str,
    max_tokens: int = 4096,
    temperature: float = 0.0,
) -> LLMResponse:
    """Call the Anthropic Messages API with budget enforcement, retry, and usage tracking.

    Retries up to MAX_RETRIES times on recoverable errors (rate limits,
    connection errors, server 5xx) with exponential backoff.

    Args:
        db: Database connection for budget check and usage recording.
        communication_id: For logging and usage attribution.
        stage: Pipeline stage name (cleaning, enriching, etc.).
        model: Model identifier (from model_config).
        system_prompt: System message content.
        user_prompt: User message content.
        max_tokens: Maximum output tokens.
        temperature: Sampling temperature (0.0 = deterministic).

    Returns:
        LLMResponse with text, usage metadata, and stop reason.

    Raises:
        BudgetExceededError: If daily budget is exhausted.
        LLMError: On API failure.
    """
    # Budget gate
    today_spend, daily_budget, is_over = check_budget(db)
    if is_over:
        raise BudgetExceededError(today_spend, daily_budget)

    t0 = time.time()

    if _is_openai_model(model):
        # ── OpenAI path ──
        oai_client = _get_openai_client()
        try:
            import asyncio
            import functools

            loop = asyncio.get_event_loop()
            # Build kwargs - reasoning models don't allow temperature
            oai_kwargs = {
                "model": model,
                "messages": [
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": user_prompt},
                ],
                "max_completion_tokens": 128000,
                "extra_body": {"reasoning_effort": "high"},
            }
            # GPT-5.4 with reasoning_effort rejects temperature != 1
            # Only set temperature when not using reasoning
            if not oai_kwargs["extra_body"].get("reasoning_effort"):
                oai_kwargs["temperature"] = temperature

            response = await loop.run_in_executor(
                None,
                functools.partial(
                    oai_client.chat.completions.create,
                    **oai_kwargs,
                ),
            )
        except Exception as e:
            err_name = type(e).__name__
            raise LLMError(
                f"OpenAI API error ({err_name}): {e}",
                error_type="api_error",
                recoverable=True,
            )

        elapsed = time.time() - t0
        text = response.choices[0].message.content or ""
        input_tokens = response.usage.prompt_tokens
        output_tokens = response.usage.completion_tokens
        stop_reason = response.choices[0].finish_reason or "stop"

    else:
        # ── Anthropic path (streaming for large outputs) ──
        client = _get_client()
        try:
            import asyncio
            import functools

            def _stream_collect():
                """Use streaming to avoid timeout on large outputs."""
                with client.messages.stream(
                    model=model,
                    max_tokens=max_tokens,
                    temperature=temperature,
                    system=system_prompt,
                    messages=[{"role": "user", "content": user_prompt}],
                ) as stream:
                    response = stream.get_final_message()
                return response

            loop = asyncio.get_event_loop()
            response = await loop.run_in_executor(None, _stream_collect)
        except anthropic.RateLimitError as e:
            raise LLMError(
                f"Rate limited: {e}",
                error_type="rate_limit",
                recoverable=True,
            )
        except anthropic.APIConnectionError as e:
            raise LLMError(
                f"API connection error: {e}",
                error_type="connection_error",
                recoverable=True,
            )
        except anthropic.AuthenticationError as e:
            raise LLMError(
                f"Authentication failed: {e}",
                error_type="auth_error",
                recoverable=False,
            )
        except anthropic.APIError as e:
            raise LLMError(
                f"API error: {e}",
                error_type="api_error",
                recoverable=getattr(e, "status_code", 500) >= 500,
            )

        elapsed = time.time() - t0
        text = ""
        for block in response.content:
            if block.type == "text":
                text += block.text

        input_tokens = response.usage.input_tokens
        output_tokens = response.usage.output_tokens
        stop_reason = response.stop_reason

    cost = compute_cost(model, input_tokens, output_tokens)

    # Record usage
    record_usage(db, communication_id, stage, model, input_tokens, output_tokens, cost)

    usage = LLMUsage(
        model=model,
        input_tokens=input_tokens,
        output_tokens=output_tokens,
        cost_usd=cost,
        processing_seconds=round(elapsed, 2),
    )

    logger.info(
        "[%s] LLM %s/%s: %d in + %d out = $%.4f (%.1fs)",
        communication_id[:8],
        stage,
        model.split("-")[1],
        input_tokens,
        output_tokens,
        cost,
        elapsed,
    )

    return LLMResponse(
        text=text,
        usage=usage,
        stop_reason=stop_reason,
    )


async def call_llm(
    db,
    communication_id: str,
    stage: str,
    model: str,
    system_prompt: str,
    user_prompt: str,
    max_tokens: int = 4096,
    temperature: float = 0.0,
) -> LLMResponse:
    """Call LLM with automatic retry on recoverable errors."""
    return await _call_with_retry(
        _call_llm_once,
        db,
        communication_id,
        stage,
        model,
        system_prompt,
        user_prompt,
        max_tokens,
        temperature,
    )
