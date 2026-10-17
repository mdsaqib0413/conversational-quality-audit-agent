"""Centralized LLM Gateway for Google Gemini API.

Enforces:
- Single LLM access point across the entire application
- Configurable model and API key from .env (no stale hardcoded defaults)
- Exponential backoff retry logic for free-tier rate limits
- Strict structured JSON validation via Pydantic
- Temperature and max_output_tokens controls
- Hard failure on unresolvable errors (never returns fake/mock data)
"""

import os
import re
import json
import time
import logging
from typing import Type, TypeVar, Optional, Any
from dotenv import load_dotenv
from pydantic import BaseModel, ValidationError

load_dotenv()

logger = logging.getLogger(__name__)

T = TypeVar("T", bound=BaseModel)

class GeminiGateway:
    """Wrapper for Google Gemini API client with retries and structured schema output."""

    def __init__(self, api_key: Optional[str] = None, model_name: Optional[str] = None):
        self.api_key = (api_key or os.getenv("GEMINI_API_KEY", "")).strip()
        self.model_name = (model_name or os.getenv("GEMINI_MODEL", "")).strip()
        self.client = None
        self._sdk_type = "none"
        self._init_client()

    def _init_client(self):
        """Initializes the underlying Gemini SDK client."""
        if not self.api_key:
            return

        try:
            from google import genai
            self.client = genai.Client(api_key=self.api_key)
            self._sdk_type = "google-genai"
        except ImportError:
            try:
                import google.generativeai as legacy_genai
                legacy_genai.configure(api_key=self.api_key)
                if self.model_name:
                    self.client = legacy_genai.GenerativeModel(self.model_name)
                self._sdk_type = "google-generativeai"
            except ImportError:
                logger.error("Neither 'google-genai' nor 'google-generativeai' is installed.")
                self.client = None
                self._sdk_type = "none"

    def _check_ready(self):
        """Validates that credentials and model name are configured."""
        if not self.api_key:
            raise RuntimeError(
                "GEMINI_API_KEY is not set. Please set GEMINI_API_KEY in your .env file."
            )
        if not self.model_name:
            raise RuntimeError(
                "GEMINI_MODEL is not set in environment or .env. "
                "Run 'python scripts/list_models.py' to inspect available models for your API key, "
                "then set GEMINI_MODEL=<model_name> in your .env file."
            )
        if not self.client:
            self._init_client()
            if not self.client:
                raise RuntimeError("Failed to initialize Gemini SDK client.")

    def _call_raw_with_retry(
        self,
        prompt: str,
        system_instruction: Optional[str] = None,
        temperature: float = 0.1,
        max_output_tokens: Optional[int] = None,
        max_retries: int = 4,
        initial_backoff: float = 2.0
    ) -> str:
        """Executes LLM request with exponential backoff on rate limits."""
        self._check_ready()

        backoff = initial_backoff
        last_exception = None

        for attempt in range(1, max_retries + 1):
            try:
                if self._sdk_type == "google-genai":
                    config: dict[str, Any] = {"temperature": temperature}
                    if max_output_tokens is not None:
                        config["max_output_tokens"] = max_output_tokens
                    if system_instruction:
                        config["system_instruction"] = system_instruction
                    
                    response = self.client.models.generate_content(
                        model=self.model_name,
                        contents=prompt,
                        config=config
                    )
                    return response.text or ""

                elif self._sdk_type == "google-generativeai":
                    generation_config: dict[str, Any] = {"temperature": temperature}
                    if max_output_tokens is not None:
                        generation_config["max_output_tokens"] = max_output_tokens
                    
                    response = self.client.generate_content(
                        prompt,
                        generation_config=generation_config
                    )
                    return response.text or ""

            except Exception as e:
                err_str = str(e).lower()
                last_exception = e
                # Check for rate-limiting (429 / ResourceExhausted) or transient quotas/timeouts
                if any(k in err_str for k in ["429", "resource_exhausted", "quota", "rate limit", "timeout", "unavailable", "503"]):
                    logger.warning(
                        f"Gemini API rate limit or transient error (attempt {attempt}/{max_retries}): {e}. "
                        f"Backing off for {backoff:.1f}s..."
                    )
                    time.sleep(backoff)
                    backoff *= 2.0
                else:
                    logger.error(f"Unrecoverable error in Gemini API call: {e}")
                    raise e

        raise RuntimeError(f"Exceeded max retries ({max_retries}) calling Gemini: {last_exception}")

    def generate_text(
        self,
        prompt: str,
        system_instruction: Optional[str] = None,
        temperature: float = 0.1,
        max_output_tokens: Optional[int] = None
    ) -> str:
        """Generates plain text response."""
        return self._call_raw_with_retry(
            prompt=prompt,
            system_instruction=system_instruction,
            temperature=temperature,
            max_output_tokens=max_output_tokens
        )

    def generate_structured(
        self,
        prompt: str,
        schema: Type[T],
        system_instruction: Optional[str] = None,
        temperature: float = 0.1,
        max_output_tokens: Optional[int] = None
    ) -> T:
        """Generates structured output guaranteed and validated against a Pydantic schema.
        
        Raises:
            RuntimeError: If API call fails after all retries.
            ValueError: If returned JSON cannot be parsed or validated against the schema.
        """
        schema_json = json.dumps(schema.model_json_schema(), indent=2)
        augmented_system = (
            f"{system_instruction or 'You are an objective QA auditor for ShopEase customer support.'}\n\n"
            f"CRITICAL: You MUST respond ONLY with a single valid JSON object strictly matching this JSON Schema:\n"
            f"```json\n{schema_json}\n```\n"
            f"Do not include any intro, outro, commentary, or markdown text outside the valid JSON object."
        )

        raw_response = self._call_raw_with_retry(
            prompt=prompt,
            system_instruction=augmented_system,
            temperature=temperature,
            max_output_tokens=max_output_tokens
        )

        # Clean JSON markdown if wrapped in ```json ... ```
        cleaned = raw_response.strip()
        match = re.search(r"```(?:json)?\s*([\s\S]*?)\s*```", cleaned)
        if match:
            cleaned = match.group(1).strip()

        try:
            parsed_data = json.loads(cleaned)
            return schema.model_validate(parsed_data)
        except (json.JSONDecodeError, ValidationError) as err:
            logger.error(f"Failed to parse or validate LLM structured output: {err}\nRaw output was:\n{raw_response}")
            raise ValueError(f"LLM output could not be validated against {schema.__name__}: {err}")

# Global gateway instance
gemini_gateway = GeminiGateway()
