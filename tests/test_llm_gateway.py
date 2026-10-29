"""Gateway behaviour with fake providers (no network)."""
import json

import pytest
from pydantic import BaseModel

from src.audit import llm as L


class Out(BaseModel):
    answer: str
    n: int


class Script(L.Provider):
    """Provider that replays a list of results (Completion or exception)."""
    name = "fake"

    def __init__(self, model, script):
        self.model, self.script, self.calls = model, list(script), 0

    def complete(self, prompt, system, temperature, max_tokens, schema, thinking_budget):
        self.calls += 1
        item = self.script.pop(0)
        if isinstance(item, Exception):
            raise item
        return item


@pytest.fixture(autouse=True)
def tmp_budget(tmp_path, monkeypatch):
    monkeypatch.setattr(L, "BUDGET_FILE", tmp_path / "budget.json")
    monkeypatch.setattr(L, "FAILED_DIR", tmp_path / "failed")


def gw(*targets):
    sleeps = []
    g = L.LLMGateway(list(targets), sleep=sleeps.append)
    g.sleeps = sleeps
    return g


def ok(obj):
    return L.Completion(text=json.dumps(obj))


def test_parses_fenced_and_unclosed_json():
    p = Script("m", [L.Completion(text='```json\n{"answer": "hi", "n": 2}')])
    assert gw(p).generate_structured("q", Out) == Out(answer="hi", n=2)


def test_truncation_retries_with_bigger_limit():
    seen = []

    class P(Script):
        def complete(self, prompt, system, temperature, max_tokens, schema, thinking_budget):
            seen.append(max_tokens)
            return super().complete(prompt, system, temperature, max_tokens, schema, thinking_budget)

    p = P("m", [L.Completion(text='{"answer": "cut', truncated=True), ok({"answer": "a", "n": 1})])
    assert gw(p).generate_structured("q", Out, max_output_tokens=1000).n == 1
    assert seen == [1000, 2000]


def test_validation_error_is_retried_with_feedback():
    p = Script("m", [L.Completion(text='{"answer": "x"}'), ok({"answer": "x", "n": 5})])
    assert gw(p).generate_structured("q", Out).n == 5
    assert p.calls == 2


def test_gives_up_after_max_attempts_and_raises():
    p = Script("m", [L.Completion(text="nonsense")] * 3)
    with pytest.raises(L.LLMError):
        gw(p).generate_structured("q", Out, max_attempts=3)


def test_per_minute_rate_limit_waits_then_succeeds():
    p = Script("m", [L.RateLimitedError("slow down", retry_after=7), ok({"answer": "a", "n": 1})])
    g = gw(p)
    assert g.generate_structured("q", Out).answer == "a"
    assert g.sleeps == [7]


def test_daily_quota_switches_to_fallback_target():
    a = Script("a", [L.QuotaExhaustedError("daily")])
    b = Script("b", [ok({"answer": "from b", "n": 1})])
    g = gw(a, b)
    assert g.generate_structured("q", Out).answer == "from b"
    assert g.model_name == "b"


def test_daily_quota_without_fallback_raises_clear_error():
    a = Script("a", [L.QuotaExhaustedError("daily")])
    with pytest.raises(L.QuotaExhaustedError) as e:
        gw(a).generate_structured("q", Out)
    assert "fallback" in str(e.value).lower()


def test_empty_response_retried_once():
    p = Script("m", [L.EmptyResponseError("empty"), ok({"answer": "a", "n": 1})])
    assert gw(p).generate_structured("q", Out).n == 1


def test_fatal_error_is_not_retried():
    p = Script("m", [L.FatalLLMError("bad key"), ok({"answer": "a", "n": 1})])
    with pytest.raises(L.FatalLLMError):
        gw(p).generate_structured("q", Out)
    assert p.calls == 1


def test_budget_counter_counts_every_request(tmp_path):
    p = Script("mm", [L.Completion(text="bad"), ok({"answer": "a", "n": 1})])
    g = gw(p)
    g.generate_structured("q", Out)
    assert L.requests_used_today("mm") == 2
    assert g.request_count == 2


# ---- real error messages copied from the project's own logs ----------------------------
QUOTA_MSG = ("429 RESOURCE_EXHAUSTED. {'error': {'code': 429, 'message': 'You exceeded your current quota. Please retry in 15h20m4.049412937s.', "
             "'details': [{'quotaId': 'GenerateRequestsPerDayPerProjectPerModel-FreeTier'}, {'retryDelay': '55204s'}]}}")
MINUTE_MSG = ("429 RESOURCE_EXHAUSTED. {'error': {'message': 'Please retry in 24.5s.', "
              "'details': [{'quotaId': 'GenerateRequestsPerMinutePerProjectPerModel-FreeTier'}]}}")
NOTFOUND_MSG = ("404 NOT_FOUND. {'error': {'message': 'This model models/gemini-2.5-pro is no longer available to new users.', 'status': 'NOT_FOUND'}}")
KEY_MSG = "400 INVALID_ARGUMENT. {'error': {'message': 'API key not valid. Please pass a valid API key.', 'details': [{'reason': 'API_KEY_INVALID'}]}}"


def test_classify_real_messages():
    assert isinstance(L.classify_error(Exception(QUOTA_MSG)), L.QuotaExhaustedError)
    e = L.classify_error(Exception(MINUTE_MSG))
    assert isinstance(e, L.RateLimitedError) and 24 <= e.retry_after <= 25
    assert isinstance(L.classify_error(Exception(NOTFOUND_MSG)), L.FatalLLMError)
    assert isinstance(L.classify_error(Exception(KEY_MSG)), L.FatalLLMError)
    assert isinstance(L.classify_error(Exception("503 UNAVAILABLE. The model is overloaded")), L.RateLimitedError)


def test_clean_json_text_extracts_object_from_prose():
    assert json.loads(L.clean_json_text('Sure! ```json\n{"a": 1}\n``` hope it helps')) == {"a": 1}
    assert json.loads(L.clean_json_text('Here: {"a": [1, 2]} thanks')) == {"a": [1, 2]}


def test_build_targets_from_env(monkeypatch):
    monkeypatch.setenv("LLM_PROVIDER", "gemini")
    monkeypatch.setenv("GEMINI_MODEL", "m1")
    monkeypatch.setenv("GEMINI_FALLBACK_MODELS", "m2, m1 ,m3")
    monkeypatch.setenv("LLM_FALLBACK_PROVIDER", "openai_compat")
    monkeypatch.setenv("LLM_BASE_URL", "http://localhost:11434/v1")
    monkeypatch.setenv("LLM_MODEL", "llama")
    t = L.build_targets()
    assert [x.model for x in t] == ["m1", "m2", "m3", "llama"]
    assert [x.name for x in t][-1] == "openai_compat"


def test_dns_failure_is_a_network_error_retried_then_raised_without_counting():
    err = L.classify_error(OSError("[Errno 11001] getaddrinfo failed"))
    assert isinstance(err, L.NetworkError) and "internet" in str(err).lower()
    p = Script("net", [L.NetworkError("dns")] * 3)
    g = gw(p)
    with pytest.raises(L.NetworkError):
        g.generate_structured("q", Out)
    assert p.calls == 3 and g.sleeps == [3.0, 6.0]
    assert L.requests_used_today("net") == 0 and g.request_count == 0


def test_network_blip_then_success():
    p = Script("net2", [L.NetworkError("dns"), ok({"answer": "a", "n": 1})])
    assert gw(p).generate_structured("q", Out).n == 1
    assert L.requests_used_today("net2") == 1
