"""ASR clean-up, word-level timing, and repeated-violation merging."""
from types import SimpleNamespace

from src.audit.pipeline import AuditPipeline
from src.audit.rag import KnowledgeBase
from src.audit.schemas import PolicyAnalysis, PolicyClaim
from src.audit.transcribe import Transcriber, normalize_asr
from src.audit.transcript_io import load_transcript_json
from tests.fakes import FakeGateway, make_analysis

KB = KnowledgeBase(use_embeddings=False)


def test_brand_and_order_id_normalisation():
    assert normalize_asr("Under shoppiece policy") == "Under ShopEase policy"
    assert normalize_asr("Thank you for contacting Shoppies, Mr Kumar") == "Thank you for contacting ShopEase, Mr Kumar"
    assert normalize_asr("shop ease and SHOPEASE and shop peace") == "ShopEase and ShopEase and ShopEase"
    assert normalize_asr("order ORD 85674 and ord-1234") == "order ORD-85674 and ORD-1234"
    assert normalize_asr("I went shopping at the shop") == "I went shopping at the shop"  # ordinary words untouched


def test_word_timestamps_give_true_speech_boundaries():
    seg = SimpleNamespace(start=0.0, end=9.0, text="Thank you for calling shoppiece.",
                          words=[SimpleNamespace(start=0.6, end=0.9), SimpleNamespace(start=1.0, end=3.2)])
    seg2 = SimpleNamespace(start=9.0, end=12.0, text="  ", words=[])

    class FakeModel:
        def transcribe(self, path, **kw):
            assert kw["word_timestamps"] is True
            return iter([seg, seg2]), SimpleNamespace(duration=12.0)

    t = Transcriber()
    t._model = FakeModel()
    segs, dur = t.transcribe("x.wav")
    assert len(segs) == 1 and (segs[0].start, segs[0].end) == (0.6, 3.2) and segs[0].text == "Thank you for calling ShopEase." and dur == 12.0


def test_repeated_violation_is_one_finding_penalised_once(tmp_path):
    call, _ = load_transcript_json("data/transcripts/call_041.json")
    agent = [t for t in call.turns if t.speaker == "agent"]
    a, b = agent[4], agent[5]  # turns 9 and 11: the agent states the wrong warranty twice
    claims = PolicyAnalysis(claims=[
        PolicyClaim(turn=a.turn_id, quote=" ".join(a.text.split()[:9]), claim="c", clause_id="WAR-3.2", verdict="violation", severity="major", explanation="x"),
        PolicyClaim(turn=b.turn_id, quote=" ".join(b.text.split()[:9]), claim="c", clause_id="WAR-3.2", verdict="violation", severity="major", explanation="x again"),
    ])
    gw = FakeGateway(analysis=lambda p: make_analysis(p, call), policy=claims)
    rep = AuditPipeline(kb=KB, gateway=gw, cache_dir=tmp_path).audit_call(call)
    v = [p for p in rep.policy_results if p.verdict == "violation"]
    assert len(v) == 1 and v[0].turn == a.turn_id and v[0].repeat_turns == [b.turn_id]
    assert rep.scores.policy_penalty_total == 8


def test_policy_text_has_no_markdown_asterisks():
    assert "**" not in KB.by_id["WAR-3.2"].short(1000)
