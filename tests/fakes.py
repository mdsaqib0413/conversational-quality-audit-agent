"""TEST-ONLY fake gateway. The product code never uses this: failures there raise instead of faking."""
import re

from src.audit.schemas import (ConversationAnalysis, GapFinding, PolicyAnalysis, PolicyClaim, SegmentLabel, SegmentLabels,
                               StepJudgement, TurnEmotion, TurnTone)


class FakeGateway:
    model_name = "fake-model"
    targets = [object()]

    def __init__(self, analysis=None, policy=None, labels=None):
        self.request_count = 0
        self._analysis, self._policy, self._labels = analysis, policy, labels
        self.prompts = []

    def describe(self):
        return "fake:fake-model"

    def generate_structured(self, prompt, schema, **kw):
        self.request_count += 1
        self.prompts.append((schema.__name__, prompt))
        if schema is ConversationAnalysis:
            return self._analysis(prompt) if callable(self._analysis) else self._analysis
        if schema is PolicyAnalysis:
            return self._policy(prompt) if callable(self._policy) else self._policy
        if schema is SegmentLabels:
            return self._labels(prompt) if callable(self._labels) else self._labels
        raise AssertionError(f"unexpected schema {schema}")


def step_ids_in(prompt):
    return re.findall(r"^- ([A-Z]+-S?\d+(?:\.\d+)?) \|", prompt, re.MULTILINE)


def make_analysis(prompt, call, statuses=None, quote_for=None, empathy=4, missing=None):
    """Build a ConversationAnalysis for every step in the prompt; `statuses` maps step id -> status (default followed)."""
    statuses = statuses or {}
    agent = [t for t in call.turns if t.speaker == "agent"]
    steps = []
    for sid in step_ids_in(prompt):
        st = statuses.get(sid, "followed")
        if st in ("missed", "not_applicable"):
            steps.append(StepJudgement(step_id=sid, status=st, turn=0, quote="", reason="x", missing="the step"))
        else:
            q = (quote_for or {}).get(sid)
            t = agent[1] if len(agent) > 1 else agent[0]
            steps.append(StepJudgement(step_id=sid, status=st, turn=t.turn_id, quote=q if q is not None else " ".join(t.text.split()[:8]), reason="ok", missing=(missing or {}).get(sid, "")))
    emos = [TurnEmotion(turn=t.turn_id, emotion="angry" if i < 2 else "satisfied") for i, t in enumerate([t for t in call.turns if t.speaker == "customer"])]
    return ConversationAnalysis(
        summary="Customer called about an order.", customer_issue="order issue", resolved=True, steps=steps,
        empathy_score=empathy, empathy_evidence="", clarity_score=4, professionalism_score=4, ownership_score=4, closure_score=4,
        turn_emotions=emos,
        agent_tones=[TurnTone(turn=t.turn_id, tone="warm") for t in call.turns if t.speaker == "agent"], gaps=[GapFinding(gap_type="no_summary", turn=0, quote="", detail="No recap.")],
        strengths=["Polite greeting"], coaching_tips=["Recap the outcome at the end."],
    )
