"""Centralized LLM Gateway for Google Gemini API.

Enforces:
- Single LLM access point across the entire application
- Configurable model and API key from .env (with load_dotenv override=True)
- Native structured JSON output via response_schema and response_mime_type
- Disabling / minimizing thinking budget on 2.5 models (thinking_budget=0)
- Default max_output_tokens=8192 with MAX_TOKENS truncation detection and automatic limit doubling
- Parse failures and validation errors retryable up to 3 attempts with prompt augmentation
- Immediate loud failure on unrecoverable errors (API_KEY_INVALID, model NOT_FOUND, quota exhaustion)
- Debug logging of raw outputs on final failure to data/transcripts/_failed/
"""

import os
import re
import json
import time
import logging
from pathlib import Path
from typing import Type, TypeVar, Optional, Any
from dotenv import load_dotenv
from pydantic import BaseModel, ValidationError

# Force override=True so values from .env take precedence over stale session variables
load_dotenv(override=True)

logger = logging.getLogger(__name__)

T = TypeVar("T", bound=BaseModel)

REPO_ROOT = Path(__file__).resolve().parent.parent.parent


class GeminiGateway:
    """Wrapper for Google Gemini API client with retries, native schemas, and backoff."""

    def __init__(self, api_key: Optional[str] = None, model_name: Optional[str] = None):
        self.api_key = (api_key or os.getenv("GEMINI_API_KEY", "")).strip()
        self.model_name = (model_name or os.getenv("GEMINI_MODEL", "")).strip()
        self.client = None
        self._sdk_type = "none"
        self._init_client()

    # Request budget handling
    _budget_file = REPO_ROOT / "scripts" / ".request_budget.json"
    def _load_budget(self):
        if self._budget_file.exists():
            try:
                return json.load(self._budget_file.open())
            except Exception:
                return {}
        return {}
    def _save_budget(self, data):
        self._budget_file.parent.mkdir(parents=True, exist_ok=True)
        with self._budget_file.open('w') as f:
            json.dump(data, f, indent=2)
    
    def _increment_requests(self, model: str):
        data = self._load_budget()
        today = time.strftime("%Y-%m-%d")
        data.setdefault(model, {})
        data[model][today] = data[model].get(today, 0) + 1
        self._save_budget(data)
    def _check_quota_and_fallback(self, err: Exception):
        # If daily quota exhausted, try fallback models
        err_str = str(err).lower()
        if 'daily quota' in err_str or ('quota' in err_str and 'daily' in err_str):
            fallback = os.getenv('GEMINI_FALLBACK_MODELS','')
            models = [m.strip() for m in fallback.split(',') if m.strip()]
            if not models:
                raise RuntimeError('FATAL: Gemini daily quota exhausted and no fallback models configured.')
            for m in models:
                logger.info(f"Attempting fallback model {m} after quota exhaustion.")
                self.model_name = m
                self._init_client()
                try:
                    # test call to verify model works
                    self.generate_text('ping')
                    return
                except Exception as e2:
                    logger.warning(f"Fallback model {m} also failed: {e2}")
                    continue
            raise RuntimeError('FATAL: All fallback models exhausted after quota error.')
        # otherwise re-raise
        raise err

        """Initializes the underlying Gemini SDK client."""
        # Refresh from environment in case .env changed
        if not self.api_key:
            self.api_key = os.getenv("GEMINI_API_KEY", "").strip()
        if not self.model_name:
            self.model_name = os.getenv("GEMINI_MODEL", "").strip()

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
        self._init_client()
        if not self.api_key:
            raise RuntimeError(
                "GEMINI_API_KEY is not set. Please set GEMINI_API_KEY in your .env file."
            )
        if not self.model_name:
            raise RuntimeError(
                "GEMINI_MODEL is not set in environment or .env. "
                "Run 'python scripts/list_models.py' to inspect available models, "
                "then set GEMINI_MODEL=<model_name> in your .env file."
            )
        if not self.client:
            raise RuntimeError("Failed to initialize Gemini SDK client.")

    def _clean_json_text(self, text: str) -> str:
        """Strips markdown code fences even when the closing fence is missing (due to truncation)."""
        cleaned = text.strip()
        match = re.search(r"```(?:json)?\s*([\s\S]*?)(?:```|$)", cleaned, re.IGNORECASE)
        if match:
            candidate = match.group(1).strip()
            if candidate:
                return candidate
        if cleaned.startswith("```json"):
            cleaned = cleaned[7:].strip()
        elif cleaned.startswith("```"):
            cleaned = cleaned[3:].strip()
        if cleaned.endswith("```"):
            cleaned = cleaned[:-3].strip()
        return cleaned

    def generate_text(
        self,
        prompt: str,
        system_instruction: Optional[str] = None,
        temperature: float = 0.1,
        max_output_tokens: int = 8192
    ) -> str:
        """Generates plain text response."""
        self._check_ready()
        try:
            if self._sdk_type == "google-genai":
                from google.genai import types
                config_kwargs: dict[str, Any] = {
                    "temperature": temperature,
                    "max_output_tokens": max_output_tokens
                }
                if system_instruction:
                    config_kwargs["system_instruction"] = system_instruction
                
                config = types.GenerateContentConfig(**config_kwargs)
                response = self.client.models.generate_content(
                    model=self.model_name,
                    contents=prompt,
                    config=config
                )
                return response.text or ""
            else:
                generation_config = {
                    "temperature": temperature,
                    "max_output_tokens": max_output_tokens
                }
                response = self.client.generate_content(
                    prompt,
                    generation_config=generation_config
                )
                return response.text or ""
        except Exception as e:
            self._handle_unrecoverable_errors(e)
            raise e

    def _handle_unrecoverable_errors(self, err: Exception):
        """Checks for fatal unrecoverable conditions that must stop execution loudly."""
        err_str = str(err).lower()
        if "api_key_invalid" in err_str or "api key not valid" in err_str or ("400" in err_str and "invalid_argument" in err_str and "api_key" in err_str):
            logger.error(f"FATAL: GEMINI_API_KEY is rejected as INVALID by Google API:\n{err}")
            raise RuntimeError(f"FATAL: Invalid GEMINI_API_KEY. Please update .env with a valid API key: {err}")
        if "not_found" in err_str or "404" in err_str:
            logger.error(f"FATAL: GEMINI_MODEL '{self.model_name}' was NOT FOUND (404) on Google API:\n{err}")
            raise RuntimeError(f"FATAL: Model '{self.model_name}' not found. Run 'python scripts/list_models.py' and update GEMINI_MODEL in .env: {err}")
        
        # Check for exhausted daily quota
        is_daily_quota = (
            ("quota" in err_str and any(k in err_str for k in ["daily", "perday", "per_day", "free_tier_requests", "generaterequestsperday", "per project per model"]))
            or ("429" in err_str and "retry in" in err_str and ("h" in err_str or "day" in err_str))
            or ("resource_exhausted" in err_str and "free_tier_requests" in err_str)
        )
        if is_daily_quota:
            logger.error(f"FATAL: Gemini daily quota exhausted for model '{self.model_name}':\n{err}")
            raise RuntimeError(f"FATAL: Gemini daily quota exhausted for model '{self.model_name}': {err}")

    def generate_structured(
        self,
        prompt: str,
        schema: Type[T],
        system_instruction: Optional[str] = None,
        temperature: float = 0.1,
        max_output_tokens: int = 8192,
        thinking_budget: Optional[int] = 0,
        call_id: Optional[str] = None,
        max_attempts: int = 3
    ) -> T:
        """Generates structured output validated against a Pydantic schema using native SDK schemas.
        
        Handles:
        - Native structured outputs (response_mime_type="application/json", response_schema=schema)
        - Disabling thinking budget on 2.5 models
        - MAX_TOKENS finish_reason detection and limit doubling
        - Retries up to max_attempts on parse/schema validation errors with prompt feedback
        - Loud stop on API_KEY_INVALID / NOT_FOUND / Quota
        - Raw debug dump on failure to data/transcripts/_failed/<call_id>_attemptN.txt
        """
        self._check_ready()
        current_prompt = prompt
        current_max_tokens = max_output_tokens
        last_error = None
        last_raw_text = ""

        from google.genai import types

        for attempt in range(1, max_attempts + 1):
            try:
                # 1. Prepare Configuration
                config_kwargs: dict[str, Any] = {
                    "temperature": temperature,
                    "max_output_tokens": current_max_tokens,
                    "response_mime_type": "application/json",
                    "response_schema": schema
                }
                if system_instruction:
                    config_kwargs["system_instruction"] = system_instruction

                # Minimize/disable thinking tokens for 2.5 models if requested
                if thinking_budget is not None and "2.5" in self.model_name:
                    try:
                        config_kwargs["thinking_config"] = types.ThinkingConfig(thinking_budget=thinking_budget)
                    except Exception as te:
                        logger.debug(f"ThinkingConfig omitted: {te}")

                config = types.GenerateContentConfig(**config_kwargs)

                                        # 2. Call API with transient rate-limit retry
        # Increment request count for each API call attempt
        api_retries = 3
        backoff = 2.0
        raw_response = None
        for api_attempt in range(1, api_retries + 1):
            try:
                self._increment_requests(self.model_name)
                raw_response = self.client.models.generate_content(
                    model=self.model_name,
                    contents=current_prompt,
                    config=config
                )
                break
            except Exception as api_err:
                # First handle quota fallback if applicable
                try:
                    self._check_quota_and_fallback(api_err)
                except Exception:
                    pass
                self._handle_unrecoverable_errors(api_err)
                err_str = str(api_err).lower()
                # If thinking_config rejected by API, omit it and retry
                if "thinking_config" in err_str and "thinking_config" in config_kwargs:
                    logger.info("API rejected thinking_config. Retrying without thinking_config...")
                    del config_kwargs["thinking_config"]
                    config = types.GenerateContentConfig(**config_kwargs)
                    continue
                # If schema uses additionalProperties (e.g. Dict), fallback without response_schema
                if "additionalproperties" in err_str and "response_schema" in config_kwargs:
                    logger.info("additionalProperties detected in schema. Falling back to JSON prompt mode...")
                    del config_kwargs["response_schema"]
                    schema_json = json.dumps(schema.model_json_schema(), indent=2)
                    config_kwargs["system_instruction"] = (
                        f"{system_instruction or 'You are an objective auditor.'}\n\n"
                        f"CRITICAL: Respond ONLY with valid JSON matching this schema:\n{schema_json}"
                    )
                    config = types.GenerateContentConfig(**config_kwargs)
                    continue
                # Transient 429 rate limits (per-minute, timeouts, etc.)
                if any(k in err_str for k in ["429", "resource_exhausted", "rate limit", "timeout", "unavailable", "503"]):
                    logger.warning(f"Transient rate limit / network error (attempt {api_attempt}/{api_retries}): {api_err}. Backing off {backoff:.1f}s...")
                    time.sleep(backoff)
                    backoff *= 2.0
                    continue
                else:
                    raise api_err
        if raw_response is None:
            raise RuntimeError("No response returned from Gemini API.")
                # Increment request count for each API call attempt
                api_retries = 3
                backoff = 2.0
                raw_response = None
                for api_attempt in range(1, api_retries + 1):
                    try:
                        self._increment_requests(self.model_name)
                        raw_response = self.client.models.generate_content(
                            model=self.model_name,
                            contents=current_prompt,
                            config=config
                        )
                        break
                    except Exception as api_err:
                        # First handle quota fallback if applicable
                        try:
                            self._check_quota_and_fallback(api_err)
                        except Exception:
                            pass
                        self._handle_unrecoverable_errors(api_err)
                        err_str = str(api_err).lower()
                        # If thinking_config rejected by API, omit it and retry
                        if "thinking_config" in err_str and "thinking_config" in config_kwargs:
                            logger.info("API rejected thinking_config. Retrying without thinking_config...")
                            del config_kwargs["thinking_config"]
                            config = types.GenerateContentConfig(**config_kwargs)
                            continue
                        # If schema uses additionalProperties (e.g. Dict), fallback without response_schema
                        if "additionalproperties" in err_str and "response_schema" in config_kwargs:
                            logger.info("additionalProperties detected in schema. Falling back to JSON prompt mode...")
                            del config_kwargs["response_schema"]
                            schema_json = json.dumps(schema.model_json_schema(), indent=2)
                            config_kwargs["system_instruction"] = (
                                f"{system_instruction or 'You are an objective auditor.'}\n\n"
                                f"CRITICAL: Respond ONLY with valid JSON matching this schema:\n{schema_json}"
                            )
                            config = types.GenerateContentConfig(**config_kwargs)
                            continue
                        # Transient 429 rate limits (per-minute, timeouts, etc.)
                        if any(k in err_str for k in ["429", "resource_exhausted", "rate limit", "timeout", "unavailable", "503"]):
                            logger.warning(f"Transient rate limit / network error (attempt {api_attempt}/{api_retries}): {api_err}. Backing off {backoff:.1f}s...")
                            time.sleep(backoff)
                            backoff *= 2.0
                            continue
                        else:
                            raise api_err
                if raw_response is None:
                    raise RuntimeError("No response returned from Gemini API.")
        except Exception as api_err:
            # First handle quota fallback if applicable
            try:
                self._check_quota_and_fallback(api_err)
            except Exception:
                pass
            self._handle_unrecoverable_errors(api_err)
            err_str = str(api_err).lower()
            # If thinking_config rejected by API, omit it and retry
            if "thinking_config" in err_str and "thinking_config" in config_kwargs:
                logger.info("API rejected thinking_config. Retrying without thinking_config...")
                del config_kwargs["thinking_config"]
                config = types.GenerateContentConfig(**config_kwargs)
                continue
            # If schema uses additionalProperties (e.g. Dict), fallback without response_schema
            if "additionalproperties" in err_str and "response_schema" in config_kwargs:
                logger.info("additionalProperties detected in schema. Falling back to JSON prompt mode...")
                del config_kwargs["response_schema"]
                schema_json = json.dumps(schema.model_json_schema(), indent=2)
                config_kwargs["system_instruction"] = (
                    f"{system_instruction or 'You are an objective auditor.'}\n\n"
                    f"CRITICAL: Respond ONLY with valid JSON matching this schema:\n{schema_json}"
                )
                config = types.GenerateContentConfig(**config_kwargs)
                continue
            # Transient 429 rate limits (per-minute, timeouts, etc.)
            if any(k in err_str for k in ["429", "resource_exhausted", "rate limit", "timeout", "unavailable", "503"]):
                logger.warning(f"Transient rate limit / network error (attempt {api_attempt}/{api_retries}): {api_err}. Backing off {backoff:.1f}s...")
                time.sleep(backoff)
                backoff *= 2.0
                continue
            else:
                raise api_err

                if raw_response is None:
                    raise RuntimeError("No response returned from Gemini API.")

                # 3. Check for truncation (finish_reason == MAX_TOKENS)
                was_truncated = False
                if raw_response.candidates:
                    cand = raw_response.candidates[0]
                    if cand.finish_reason:
                        fr_name = str(cand.finish_reason).upper()
                        if "MAX_TOKENS" in fr_name:
                            was_truncated = True

                raw_text = raw_response.text or ""
                last_raw_text = raw_text

                if was_truncated:
                    logger.warning(f"Output was truncated (finish_reason=MAX_TOKENS at {current_max_tokens} tokens). Doubling token limit for retry...")
                    current_max_tokens = min(current_max_tokens * 2, 32768)
                    current_prompt = (
                        prompt + f"\n\n[NOTICE: PREVIOUS GENERATION HIT MAX_TOKENS TRUNCATION]. "
                        f"Please generate the complete, concise dialogue conforming strictly to the requested turn range without stalling."
                    )
                    # Dump attempt output for debugging
                    self._save_attempt_output(call_id, attempt, raw_text, "TRUNCATED (finish_reason=MAX_TOKENS)")
                    continue

                # 4. Parse & Validate JSON
                cleaned = self._clean_json_text(raw_text)
                try:
                    parsed_dict = json.loads(cleaned)
                    return schema.model_validate(parsed_dict)
                except (json.JSONDecodeError, ValidationError) as parse_err:
                    logger.warning(
                        f"Structured parse/validation error on attempt {attempt}/{max_attempts}: {parse_err}. "
                        f"Retrying with error feedback..."
                    )
                    last_error = parse_err
                    self._save_attempt_output(call_id, attempt, raw_text, f"PARSE/VALIDATION ERROR: {parse_err}")
                    # Append error message to prompt for next attempt
                    current_prompt = (
                        prompt + f"\n\n[PREVIOUS ATTEMPT VALIDATION ERROR]: {parse_err}\n"
                        f"Raw previous output snippet: {cleaned[:300]}...\n"
                        f"CRITICAL: Ensure your JSON strictly validates against the requested schema and does not get cut off."
                    )

            except Exception as e:
                self._handle_unrecoverable_errors(e)
                last_error = e
                logger.warning(f"Attempt {attempt}/{max_attempts} failed with exception: {e}")
                self._save_attempt_output(call_id, attempt, last_raw_text, f"EXCEPTION: {e}")

        raise ValueError(
            f"Failed to generate valid structured output for {schema.__name__} after {max_attempts} attempts: {last_error}"
        )

    def _save_attempt_output(self, call_id: Optional[str], attempt: int, raw_text: str, error_reason: str):
        """Saves raw model output for debugging to data/transcripts/_failed/<call_id>_attemptN.txt."""
        try:
            failed_dir = REPO_ROOT / "data" / "transcripts" / "_failed"
            failed_dir.mkdir(parents=True, exist_ok=True)
            dump_name = f"{call_id or 'call'}_attempt{attempt}.txt"
            dump_path = failed_dir / dump_name
            dump_path.write_text(
                f"REASON: {error_reason}\n\nRAW MODEL OUTPUT:\n{raw_text}\n",
                encoding="utf-8"
            )
            logger.info(f"Saved failed attempt output dump to {dump_path}")
        except Exception:
            pass




# Global gateway instance
gemini_gateway = GeminiGateway()
