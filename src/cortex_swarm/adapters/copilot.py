"""GitHub Copilot CLI adapter for executing agents.

Drives agent execution through the Copilot CLI or an OpenAI-compatible
API. This is the bridge between cortex-swarm's orchestration logic
and the actual LLM backends.
"""

from __future__ import annotations

import asyncio
import json
import logging
import subprocess
import time
from typing import Protocol, runtime_checkable

from cortex_swarm.dag.types import NodeResult

logger = logging.getLogger(__name__)


@runtime_checkable
class LLMBackend(Protocol):
    """Protocol for LLM execution backends."""

    async def query(self, model_id: str, prompt: str) -> str:
        """Send a prompt to a model and return the response."""
        ...


class CopilotCLIBackend:
    """Execute LLM queries via the Copilot CLI (`gh copilot` or similar).

    Falls back to a subprocess call pattern similar to the CDO OpenCodeAdapter.
    """

    def __init__(self, timeout: float = 300.0):
        self._timeout = timeout

    async def query(self, model_id: str, prompt: str) -> str:
        """Query a model via Copilot CLI."""
        loop = asyncio.get_event_loop()
        return await loop.run_in_executor(
            None, self._sync_query, model_id, prompt,
        )

    def _sync_query(self, model_id: str, prompt: str) -> str:
        """Synchronous CLI query."""
        start = time.monotonic()

        try:
            result = subprocess.run(
                ["copilot-cli", "run", "-m", model_id, prompt],
                capture_output=True,
                text=True,
                timeout=self._timeout,
            )

            if result.returncode != 0:
                raise RuntimeError(f"CLI failed (exit={result.returncode}): {result.stderr[:500]}")

            return result.stdout.strip()

        except subprocess.TimeoutExpired:
            raise TimeoutError(f"Query timed out after {self._timeout}s")
        except FileNotFoundError:
            raise RuntimeError(
                "copilot-cli not found. Install it or configure an API backend instead."
            )


class MockBackend:
    """Mock backend for testing without real LLM calls."""

    def __init__(self, responses: dict[str, str] | None = None):
        self._responses = responses or {}
        self.call_log: list[tuple[str, str]] = []

    async def query(self, model_id: str, prompt: str) -> str:
        self.call_log.append((model_id, prompt))
        return self._responses.get(
            model_id,
            f"Mock response from {model_id} for: {prompt[:100]}",
        )


class OpenAICompatBackend:
    """Backend using an OpenAI-compatible API (e.g., OpenRouter, local server).

    Requires httpx and an API key.
    """

    def __init__(
        self,
        base_url: str = "https://api.openai.com/v1",
        api_key: str = "",
        timeout: float = 120.0,
    ):
        self._base_url = base_url.rstrip("/")
        self._api_key = api_key
        self._timeout = timeout

    async def query(self, model_id: str, prompt: str) -> str:
        import httpx

        async with httpx.AsyncClient(timeout=self._timeout) as client:
            response = await client.post(
                f"{self._base_url}/chat/completions",
                headers={
                    "Authorization": f"Bearer {self._api_key}",
                    "Content-Type": "application/json",
                },
                json={
                    "model": model_id,
                    "messages": [{"role": "user", "content": prompt}],
                    "temperature": 0.1,
                },
            )
            response.raise_for_status()
            data = response.json()
            return data["choices"][0]["message"]["content"]
