"""Single LLM access point for the whole project.

Design goals
------------
* One gateway (`gemini_gateway`, also exported as `llm`) used by every module and script.
* Providers: Google Gemini (default) and any OpenAI-compatible endpoint (Groq, OpenRouter,
  Ollama, LM Studio ...). Configure in .env.
* Native JSON output validated with pydantic, with automatic degradation (no thinking config,
  no response_schema) when the API rejects optional features.
* Truncation (MAX_TOKENS) and parse/validation failures are retried with feedback.
* Per-minute rate limits are waited out; per-day quota exhaustion moves to the next target in
  the fallback chain (GEMINI_FALLBACK_MODELS, then LLM_FALLBACK_PROVIDER) or stops loudly.
* Every real API request is counted in scripts/.request_budget.json.
* NEVER returns fake data: failures raise.

.env keys
---------
LLM_PROVIDER=gemini | openai_compat          (default gemini)
GEMINI_API_KEY, GEMINI_MODEL, GEMINI_FALLBACK_MODELS=model2,model3
LLM_BASE_URL, LLM_API_KEY, LLM_MODEL          (openai_compat: e.g. https://api.groq.com/openai/v1)
LLM_FALLBACK_PROVIDER=openai_compat           (optional: used when Gemini daily quota is gone)
"""

from __future__ import annotations

import json
import logging
import os
import re
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Callable, List, Optional, Type, TypeVar

from dotenv import load_dotenv
from pydantic import BaseModel, ValidationError

REPO_ROOT = Path(__file__).resolve().parent.parent.parent
load_dotenv(REPO_ROOT / ".env", override=True)

logger = logging.getLogger(__name__)
T = TypeVar("T", bound=BaseModel)

BUDGET_FILE = REPO_ROOT / "scripts" / ".request_budget.json"
COMPAT_FILE = REPO_ROOT / "data" / "cache" / "llm_compat.json"   # remembers which optional features each model rejects
FAILED_DIR = REPO_ROOT / "data" / "transcripts" / "_failed"


# --------------------------------------------------------------------------------------
# Errors
# --------------------------------------------------------------------------------------
class LLMError(RuntimeError):
    """Base class for all gateway errors."""


class FatalLLMError(LLMError):
    """Bad key, model not found, misconfiguration: retrying will not help."""


class QuotaExhaustedError(LLMError):
    """Daily quota is gone for the current target."""


class RateLimitedError(LLMError):
    """Transient limit (per-minute, overloaded, timeout). Wait and retry."""

    def __init__(self, message: str, retry_after: float = 20.0):
        super().__init__(message)
        self.retry_after = retry_after


class BadRequestError(LLMError):
    """HTTP 400 that is not an auth problem (usually an unsupported optional feature)."""


class EmptyResponseError(LLMError):
    """The model returned no text."""


class NetworkError(LLMError):
    """This computer cannot reach the API host (DNS, offline, VPN/proxy, firewall). The request never arrived."""


@dataclass
class Completion:
    text: str
    truncated: bool = False
    tokens_in: Optional[int] = None
    tokens_out: Optional[int] = None
    model_name: Optional[str] = None
    prompt: Optional[str] = None


# --------------------------------------------------------------------------------------
# Helpers
# --------------------------------------------------------------------------------------
def _parse_retry_seconds(text: str) -> Optional[float]:
    """Extract a retry delay from Google-style messages ("retry in 15h20m4.0s", "retryDelay': '55s'")."""
    m = re.search(r"retry in\s+((?:\d+(?:\.\d+)?[hms])+)", text, re.IGNORECASE)
    if not m:
        m = re.search(r"retryDelay['\"]?\s*:\s*['\"]?((?:\d+(?:\.\d+)?[hms])+)", text, re.IGNORECASE)
    if not m:
        return None
    total = 0.0
    for val, unit in re.findall(r"(\d+(?:\.\d+)?)([hms])", m.group(1)):
        total += float(val) * {"h": 3600, "m": 60, "s": 1}[unit]
    return total


def classify_error(exc: Exception) -> LLMError:
    """Map any provider exception onto the gateway's error types."""
    if isinstance(exc, LLMError):
        return exc
    s = str(exc)
    low = s.lower()
    compact = re.sub(r"[\s_\-]", "", low)

    if any(k in low for k in ("getaddrinfo", "errno 11001", "name or service not known", "temporary failure in name resolution",
                              "nodename nor servname", "failed to resolve", "network is unreachable", "connecterror",
                              "max retries exceeded", "connection aborted", "connection refused", "winerror 10060",
                              "winerror 10061", "proxyerror", "ssl:", "certificate verify failed", "timed out", "connection reset")):
        return NetworkError(
            "Cannot reach the AI service from this computer (network/DNS problem): " + s[:160]
            + "\nCheck your internet connection, turn off any VPN/proxy, or try a mobile hotspot. "
              "If it keeps happening, set DNS to 8.8.8.8 / 1.1.1.1 in Windows network settings."
        )
    if "apikeyinvalid" in compact or "apikeynotvalid" in compact or "apikeyexpired" in compact \
            or "unauthenticated" in compact:
        return FatalLLMError(f"API key rejected: {s[:300]}")
    if "permissiondenied" in compact or low.startswith("403"):
        return FatalLLMError(f"Permission denied (key not allowed for this model/API): {s[:300]}")
    if "notfound" in compact or "nolongeravailable" in compact or low.startswith("404"):
        return FatalLLMError(
            f"Model not available: {s[:300]}\nRun `python scripts/list_models.py` and update the model name in .env."
        )
    if low.startswith("429") or "resourceexhausted" in compact or "ratelimit" in compact or "toomanyrequests" in compact:
        retry = _parse_retry_seconds(s)
        daily = "perday" in compact or "requestsperday" in compact or "dailylimit" in compact
        if retry is not None and retry > 180:
            daily = True
        if daily:
            return QuotaExhaustedError(f"Daily quota exhausted: {s[:300]}")
        return RateLimitedError(f"Rate limited: {s[:200]}", retry_after=min(retry or 20.0, 90.0))
    if any(k in compact for k in ("503", "unavailable", "overloaded", "500internal", "deadlineexceeded",
                                  "timeout", "timedout", "connectionerror", "connectionreset")):
        return RateLimitedError(f"Transient service error: {s[:200]}", retry_after=8.0)
    if low.startswith("400") or "invalidargument" in compact or "badrequest" in compact:
        return BadRequestError(s[:500])
    return LLMError(s[:500])


def clean_json_text(text: str) -> str:
    """Strip markdown fences (even if the closing fence is missing) and surrounding prose."""
    t = (text or "").strip()
    m = re.search(r"```(?:json)?\s*([\s\S]*?)(?:```|$)", t, re.IGNORECASE)
    if m and m.group(1).strip():
        t = m.group(1).strip()
    starts = [i for i in (t.find("{"), t.find("[")) if i != -1]
    if starts:
        t = t[min(starts):]
    ends = [i for i in (t.rfind("}"), t.rfind("]")) if i != -1]
    if ends:
        t = t[: max(ends) + 1]
    return t


# --------------------------------------------------------------------------------------
# Providers
# --------------------------------------------------------------------------------------
class Provider:
    name = "base"
    model = ""

    def complete(self, prompt: str, system: Optional[str], temperature: float, max_tokens: int,
                 schema: Optional[Type[BaseModel]], thinking_budget: Optional[int]) -> Completion:
        raise NotImplementedError

    def reset(self) -> None:
        pass

    def ready_check(self) -> None:
        pass


class GeminiProvider(Provider):
    name = "gemini"

    def __init__(self, model: str, api_key: Optional[str] = None):
        self.model = model
        self.api_key = (api_key if api_key is not None else os.getenv("GEMINI_API_KEY", "")).strip()
        self._client = None
        self.skip_thinking = False
        self.skip_schema = False
        self.degraded: List[str] = []
        self._load_compat()

    def _load_compat(self) -> None:
        try:
            data = json.loads(COMPAT_FILE.read_text(encoding="utf-8")).get(self.model, {})
            self.skip_thinking = bool(data.get("skip_thinking"))
            self.skip_schema = bool(data.get("skip_schema"))
            if self.skip_thinking:
                self.degraded.append("no thinking config")
            if self.skip_schema:
                self.degraded.append("schema sent inside the prompt")
        except Exception:  # noqa: BLE001
            pass

    def _save_compat(self) -> None:
        try:
            try:
                data = json.loads(COMPAT_FILE.read_text(encoding="utf-8"))
            except Exception:  # noqa: BLE001
                data = {}
            data[self.model] = {"skip_thinking": self.skip_thinking, "skip_schema": self.skip_schema}
            COMPAT_FILE.parent.mkdir(parents=True, exist_ok=True)
            COMPAT_FILE.write_text(json.dumps(data, indent=2), encoding="utf-8")
        except Exception:  # noqa: BLE001
            pass

    def reset(self) -> None:
        self._client = None
        self.skip_thinking = False
        self.skip_schema = False
        self.degraded = []
        try:  # forget what we learned about this model
            data = json.loads(COMPAT_FILE.read_text(encoding="utf-8"))
            data.pop(self.model, None)
            COMPAT_FILE.write_text(json.dumps(data, indent=2), encoding="utf-8")
        except Exception:  # noqa: BLE001
            pass
        self.api_key = os.getenv("GEMINI_API_KEY", self.api_key).strip()

    def ready_check(self) -> None:
        if not self.api_key:
            raise FatalLLMError("GEMINI_API_KEY is not set. Put it in .env (GEMINI_API_KEY=...).")
        if not self.model:
            raise FatalLLMError("GEMINI_MODEL is not set. Run `python scripts/list_models.py`, then set it in .env.")

    @property
    def client(self):
        if self._client is None:
            self.ready_check()
            from google import genai  # imported lazily so tests and tools work without the SDK
            self._client = genai.Client(api_key=self.api_key)
        return self._client

    def complete(self, prompt, system, temperature, max_tokens, schema, thinking_budget) -> Completion:
        from google.genai import types

        for _ in range(3):  # degrade optional features at most twice
            cfg: dict[str, Any] = {"temperature": temperature, "max_output_tokens": max_tokens}
            final_prompt = prompt
            if system:
                cfg["system_instruction"] = system
            if schema is not None:
                cfg["response_mime_type"] = "application/json"
                if self.skip_schema:
                    final_prompt += "\n\nReturn ONLY JSON matching this JSON Schema:\n" + json.dumps(schema.model_json_schema())
                else:
                    cfg["response_schema"] = schema
            if thinking_budget is not None and not self.skip_thinking:
                try:
                    cfg["thinking_config"] = types.ThinkingConfig(thinking_budget=thinking_budget)
                except Exception:  # SDK without ThinkingConfig
                    self.skip_thinking = True
            try:
                resp = self.client.models.generate_content(
                    model=self.model, contents=final_prompt, config=types.GenerateContentConfig(**cfg)
                )
            except Exception as exc:  # noqa: BLE001
                if isinstance(exc, (ValueError, TypeError)) and any(k in str(exc).lower() for k in ("schema", "default value")):
                    err: LLMError = BadRequestError(f"schema not supported by SDK: {exc}")
                else:
                    err = classify_error(exc)
                if isinstance(err, BadRequestError):
                    # Unspecific 400s ("Request contains an invalid argument") are almost always an optional feature
                    # this model does not accept: drop the thinking config first, then the response_schema.
                    if thinking_budget is not None and not self.skip_thinking:
                        logger.info("400 from %s; retrying without the thinking config.", self.model)
                        self.skip_thinking = True
                        self.degraded.append("no thinking config")
                        self._save_compat()
                        continue
                    if schema is not None and not self.skip_schema:
                        logger.info("400 from %s; retrying with the schema inside the prompt.", self.model)
                        self.skip_schema = True
                        self.degraded.append("schema sent inside the prompt")
                        self._save_compat()
                        continue
                    raise BadRequestError(
                        f"{err} [sent: model={self.model}, thinking_budget={None if self.skip_thinking else thinking_budget}, "
                        f"schema={'in prompt' if (schema is not None and self.skip_schema) else (schema.__name__ if schema else None)}, "
                        f"max_tokens={max_tokens}]. Run `python scripts/diagnose_llm.py` to see which setting the model rejects."
                    ) from exc
                raise err from exc

            text = ""
            try:
                text = resp.text or ""
            except Exception:  # noqa: BLE001  (blocked / no candidates)
                text = ""
            finish = ""
            try:
                finish = str(resp.candidates[0].finish_reason)
            except Exception:  # noqa: BLE001
                pass
            if not text.strip():
                raise EmptyResponseError(f"Empty response from {self.model} (finish_reason={finish or 'unknown'}).")
            usage_meta = getattr(resp, "usage_metadata", None)
            tokens_in = getattr(usage_meta, "prompt_token_count", None) if usage_meta else None
            tokens_out = getattr(usage_meta, "candidates_token_count", None) if usage_meta else None
            return Completion(
                text=text,
                truncated="MAX_TOKENS" in finish.upper(),
                tokens_in=tokens_in,
                tokens_out=tokens_out,
                model_name=self.model,
            )
        raise BadRequestError("Model rejected the request even after disabling optional features.")


class OpenAICompatProvider(Provider):
    """Any /chat/completions endpoint (Groq, OpenRouter, Ollama, LM Studio, vLLM ...)."""

    name = "openai_compat"

    def __init__(self, model: str, base_url: str, api_key: str = ""):
        self.model = model
        self.base_url = base_url.rstrip("/")
        self.api_key = api_key.strip()

    def ready_check(self) -> None:
        if not self.base_url or not self.model:
            raise FatalLLMError("LLM_BASE_URL and LLM_MODEL must be set for the openai_compat provider.")

    def complete(self, prompt, system, temperature, max_tokens, schema, thinking_budget) -> Completion:
        import requests

        self.ready_check()
        content = prompt
        if schema is not None:
            content += "\n\nReturn ONLY a JSON object matching this JSON Schema (no markdown, no commentary):\n" + json.dumps(schema.model_json_schema())
        messages = []
        if system:
            messages.append({"role": "system", "content": system})
        messages.append({"role": "user", "content": content})
        body: dict[str, Any] = {"model": self.model, "messages": messages, "temperature": temperature, "max_tokens": max_tokens}
        if schema is not None:
            body["response_format"] = {"type": "json_object"}
        headers = {"Content-Type": "application/json"}
        if self.api_key:
            headers["Authorization"] = f"Bearer {self.api_key}"
        url = f"{self.base_url}/chat/completions"
        try:
            r = requests.post(url, headers=headers, json=body, timeout=180)
            if r.status_code == 400 and schema is not None and "response_format" in r.text.lower():
                body.pop("response_format", None)  # endpoint without JSON mode
                r = requests.post(url, headers=headers, json=body, timeout=180)
        except Exception as exc:  # noqa: BLE001
            raise classify_error(exc) from exc
        if r.status_code != 200:
            low = r.text.lower()
            if r.status_code == 429:
                try:
                    retry = float(r.headers.get("retry-after", "20") or 20)
                except ValueError:
                    retry = 20.0
                if "per day" in low or "daily" in low or retry > 180:
                    raise QuotaExhaustedError(f"Daily quota exhausted: {r.text[:300]}")
                raise RateLimitedError(f"Rate limited: {r.text[:200]}", retry_after=min(retry, 90.0))
            if r.status_code in (401, 403):
                raise FatalLLMError(f"Auth failed ({r.status_code}): {r.text[:300]}")
            if r.status_code == 404:
                raise FatalLLMError(f"Endpoint or model not found: {r.text[:300]}")
            if r.status_code >= 500:
                raise RateLimitedError(f"Server error {r.status_code}", retry_after=8.0)
            raise BadRequestError(r.text[:400])
        data = r.json()
        try:
            choice = data["choices"][0]
            text = choice["message"]["content"] or ""
            truncated = choice.get("finish_reason") == "length"
        except Exception as exc:  # noqa: BLE001
            raise LLMError(f"Unexpected response shape: {str(data)[:300]}") from exc
        if not text.strip():
            raise EmptyResponseError("Empty response from endpoint.")
        usage = data.get("usage") or {}
        tokens_in = usage.get("prompt_tokens")
        tokens_out = usage.get("completion_tokens")
        return Completion(
            text=text,
            truncated=truncated,
            tokens_in=tokens_in,
            tokens_out=tokens_out,
            model_name=self.model,
        )


# --------------------------------------------------------------------------------------
# Request budget (local counter; helps you stay inside free-tier daily limits)
# --------------------------------------------------------------------------------------
def _load_budget() -> dict:
    try:
        return json.loads(BUDGET_FILE.read_text(encoding="utf-8"))
    except Exception:  # noqa: BLE001
        return {}


def _count_request(model: str) -> int:
    data = _load_budget()
    today = time.strftime("%Y-%m-%d")
    data.setdefault(model, {})
    data[model][today] = data[model].get(today, 0) + 1
    try:
        BUDGET_FILE.parent.mkdir(parents=True, exist_ok=True)
        BUDGET_FILE.write_text(json.dumps(data, indent=2), encoding="utf-8")
    except Exception:  # noqa: BLE001
        pass
    return data[model][today]


def requests_used_today(model: Optional[str] = None) -> int:
    data = _load_budget()
    today = time.strftime("%Y-%m-%d")
    if model:
        return int(data.get(model, {}).get(today, 0))
    return sum(int(v.get(today, 0)) for v in data.values())


# --------------------------------------------------------------------------------------
# Gateway
# --------------------------------------------------------------------------------------
def build_targets() -> List[Provider]:
    """Create the ordered fallback chain from environment variables."""
    targets: List[Provider] = []

    def gemini_chain() -> List[Provider]:
        models = [os.getenv("GEMINI_MODEL", "").strip()]
        models += [m.strip() for m in os.getenv("GEMINI_FALLBACK_MODELS", "").split(",") if m.strip()]
        seen, out = set(), []
        for m in models:
            if m and m not in seen:
                seen.add(m)
                out.append(GeminiProvider(m))
        return out or [GeminiProvider("")]

    def compat() -> List[Provider]:
        base = os.getenv("LLM_BASE_URL", "").strip()
        model = os.getenv("LLM_MODEL", "").strip()
        if base and model:
            return [OpenAICompatProvider(model, base, os.getenv("LLM_API_KEY", ""))]
        return []

    primary = os.getenv("LLM_PROVIDER", "gemini").strip().lower()
    fallback = os.getenv("LLM_FALLBACK_PROVIDER", "").strip().lower()
    if primary == "openai_compat":
        targets += compat() or [OpenAICompatProvider("", "")]
        if fallback == "gemini":
            targets += gemini_chain()
    else:
        targets += gemini_chain()
        if fallback == "openai_compat":
            targets += compat()
    return targets


class LLMGateway:
    def __init__(self, targets: Optional[List[Provider]] = None, sleep: Callable[[float], None] = time.sleep):
        self._explicit_targets = targets
        self._targets: Optional[List[Provider]] = targets
        self._idx = 0
        self._sleep = sleep
        self.request_count = 0  # real API requests made by this process
        self.tracer = None
        self.last_usage: Optional[dict] = None
        self.last_completion: Optional[Completion] = None

    # ---- target management -----------------------------------------------------------
    @property
    def targets(self) -> List[Provider]:
        if self._targets is None:
            self._targets = build_targets()
        return self._targets

    @property
    def provider(self) -> Provider:
        return self.targets[self._idx]

    @property
    def model_name(self) -> str:
        return self.provider.model

    @model_name.setter
    def model_name(self, value: str) -> None:  # used by CLI --model overrides
        self.provider.model = value

    def _init_client(self) -> None:  # backwards compatible name used by older scripts
        self.provider.reset()

    def reload(self) -> None:
        """Re-read .env (call after the user changed keys/models)."""
        if self._explicit_targets is None:
            load_dotenv(REPO_ROOT / ".env", override=True)
            self._targets = None
            self._idx = 0

    def describe(self) -> str:
        return f"{self.provider.name}:{self.provider.model}"

    # ---- low-level call with resilience ----------------------------------------------
    def _complete(self, prompt, system, temperature, max_tokens, schema, thinking_budget) -> Completion:
        rate_waits = 0
        empty_retries = 0
        net_waits = 0
        while True:
            prov = self.provider
            try:
                prov.ready_check()
                comp = prov.complete(prompt, system, temperature, max_tokens, schema, thinking_budget)
                comp.prompt = prompt
                comp.model_name = prov.model
                self.last_completion = comp
                self.last_usage = {
                    "tokens_in": comp.tokens_in,
                    "tokens_out": comp.tokens_out,
                    "model": prov.model,
                    "prompt": prompt,
                    "response": comp.text,
                    "has_usage": comp.tokens_in is not None and comp.tokens_out is not None,
                }
                if self.tracer and hasattr(self.tracer, "record_llm_call"):
                    try:
                        self.tracer.record_llm_call(
                            model=prov.model,
                            tokens_in=comp.tokens_in,
                            tokens_out=comp.tokens_out,
                            prompt=prompt,
                            response=comp.text,
                        )
                    except Exception as exc:  # noqa: BLE001
                        logger.debug("Tracer callback failed: %s", exc)
                _count_request(prov.model)
                self.request_count += 1
                return comp
            except LLMError as err:
                e = err
            except Exception as exc:  # noqa: BLE001
                e = classify_error(exc)
            if not isinstance(e, (NetworkError, FatalLLMError)):
                _count_request(prov.model)  # the request reached the server, so it counts against the quota
                self.request_count += 1

            if isinstance(e, QuotaExhaustedError):
                if self._idx + 1 < len(self.targets):
                    nxt = self.targets[self._idx + 1]
                    logger.warning("Daily quota exhausted on %s:%s -> switching to %s:%s", prov.name, prov.model, nxt.name, nxt.model)
                    self._idx += 1
                    continue
                if self.tracer and hasattr(self.tracer, "record_warning"):
                    try:
                        self.tracer.record_warning(f"Model '{prov.model}' rate limited / quota exhausted (429): {e}")
                    except Exception:
                        pass
                raise QuotaExhaustedError(
                    f"{e}\nNo fallback model left. Add GEMINI_FALLBACK_MODELS or an openai_compat fallback "
                    f"(Groq / Ollama) in .env, or wait for the daily reset."
                ) from None
            if isinstance(e, NetworkError):
                net_waits += 1
                if net_waits > 2:
                    raise e from None
                logger.warning("Network problem (%s). Retrying in %ds (%d/2)...", str(e)[:80], 3 * net_waits, net_waits)
                self._sleep(3.0 * net_waits)
                continue
            if isinstance(e, RateLimitedError):
                rate_waits += 1
                if rate_waits > 4:
                    raise e from None
                wait = max(1.0, e.retry_after)
                logger.warning("Rate limited (%s). Waiting %.0fs (%d/4)...", prov.model, wait, rate_waits)
                self._sleep(wait)
                continue
            if isinstance(e, EmptyResponseError):
                empty_retries += 1
                if empty_retries > 1:
                    raise e from None
                continue
            if self.tracer and hasattr(self.tracer, "record_warning"):
                try:
                    if isinstance(e, (RateLimitedError, QuotaExhaustedError)):
                        self.tracer.record_warning(f"Model '{prov.model}' rate limited / quota exhausted (429): {e}")
                    elif isinstance(e, FatalLLMError):
                        self.tracer.record_warning(f"Model '{prov.model}' unavailable: {e}")
                except Exception:
                    pass
            raise e from None

    # ---- public API ------------------------------------------------------------------
    def generate_text(self, prompt: str, system_instruction: Optional[str] = None, temperature: float = 0.2,
                      max_output_tokens: int = 4096) -> str:
        return self._complete(prompt, system_instruction, temperature, max_output_tokens, None, 0).text

    def generate_structured(self, prompt: str, schema: Type[T], system_instruction: Optional[str] = None,
                            temperature: float = 0.1, max_output_tokens: int = 8192,
                            thinking_budget: Optional[int] = 0, call_id: Optional[str] = None,
                            max_attempts: int = 3) -> T:
        cur_prompt = prompt
        max_tokens = max_output_tokens
        last_error: Optional[Exception] = None
        for attempt in range(1, max_attempts + 1):
            comp = self._complete(cur_prompt, system_instruction, temperature, max_tokens, schema, thinking_budget)
            if comp.truncated:
                last_error = ValueError(f"output truncated at {max_tokens} tokens")
                self._dump(call_id, attempt, comp.text, "TRUNCATED")
                max_tokens = min(max_tokens * 2, 32768)
                cur_prompt = prompt + "\n\n[NOTICE: your previous answer was cut off. Be more concise and return complete valid JSON.]"
                continue
            try:
                return schema.model_validate(json.loads(clean_json_text(comp.text)))
            except (ValueError, ValidationError) as err:  # JSONDecodeError is a ValueError
                last_error = err
                self._dump(call_id, attempt, comp.text, f"PARSE/VALIDATION: {err}")
                cur_prompt = (
                    prompt
                    + f"\n\n[Your previous answer was invalid: {str(err)[:400]}]\n"
                    + "Return complete, valid JSON that matches the schema exactly."
                )
        raise LLMError(f"Could not get valid {schema.__name__} after {max_attempts} attempts: {last_error}")

    @staticmethod
    def _dump(call_id: Optional[str], attempt: int, raw: str, reason: str) -> None:
        try:
            FAILED_DIR.mkdir(parents=True, exist_ok=True)
            (FAILED_DIR / f"{call_id or 'call'}_attempt{attempt}.txt").write_text(
                f"REASON: {reason}\n\nRAW MODEL OUTPUT:\n{raw}\n", encoding="utf-8"
            )
        except Exception:  # noqa: BLE001
            pass


# Global instances (no network access happens at import time)
gemini_gateway = LLMGateway()
llm = gemini_gateway


def get_policy_gateway(model: Optional[str] = None) -> LLMGateway:
    """Create an LLMGateway dedicated to the policy compliance check.

    Uses POLICY_MODEL from the environment (default: 'gemini-3.5-flash').
    Configured with strictly a single target and NO fallback chain, ensuring
    that on 429 or unavailability it raises without silently switching models.
    """
    model_name = (model or os.getenv("POLICY_MODEL", "gemini-3.5-flash")).strip() or "gemini-3.5-flash"
    primary = os.getenv("LLM_PROVIDER", "gemini").strip().lower()
    if primary == "openai_compat":
        base = os.getenv("LLM_BASE_URL", "").strip()
        target: Provider = OpenAICompatProvider(model_name, base, os.getenv("LLM_API_KEY", ""))
    else:
        target = GeminiProvider(model_name)
    return LLMGateway(targets=[target])
