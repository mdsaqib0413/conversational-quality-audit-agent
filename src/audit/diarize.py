"""Turn audio into speaker-labelled turns.

Strategy (automatic):
 1. Stereo with the two speakers on separate channels (agent left / customer right, like most call-centre
    recordings and our *_stereo.mp3 test files): transcribe each channel separately. Perfect separation,
    no LLM request, and real overlap/interruption timing.
 2. Mono: transcribe once, then ONE LLM request labels every segment as agent/customer (the dialogue has
    very strong cues: greeting, verification, apologies). If the LLM is unavailable a cue-based heuristic
    is used and the result is flagged LOW CONFIDENCE in the report.
"""

from __future__ import annotations

import logging
import os
import re
import tempfile
from typing import Dict, List, Optional, Sequence, Tuple

from .prompts import _load_agent
from .schemas import CallTranscript, DialogueTurn, SegmentLabels
from .telugu_utils import is_telugu, telugu_cue_score, telugu_to_roman
from .transcribe import Segment

logger = logging.getLogger(__name__)

MERGE_GAP = 1.2         # seconds: same-speaker segments closer than this become one turn
OVERLAP_TOLERANCE = 0.25

AGENT_CUES = [
    r"thank you for calling", r"how (may|can) i (help|assist)", r"my name is", r"\bthis call (is|may be) (being )?recorded",
    r"\bplease (confirm|provide|share)\b", r"\border id\b", r"last four digits", r"\bi (sincerely |truly )?apologi[sz]e",
    r"\bi understand\b", r"\bi (will|can) (check|help|arrange|process|escalate)", r"is there anything else", r"\bhave a (great|nice|pleasant)",
    r"\bplace you on (a )?(brief )?hold", r"\bmay i (place|put|have)\b", r"\bto recap\b", r"\bfor your (security|reference)\b",
]
CUSTOMER_CUES = [
    r"\bmy order\b", r"\bi (ordered|placed|received|paid|was charged|want|need|am calling|called)\b", r"\bi('m| am) (really |very )?(frustrated|upset|angry)",
    r"\bhello\b", r"\bwhy (is|was|has|have|did)\b", r"\bwhen will\b", r"\bno one\b", r"\bthis is (ridiculous|unacceptable)\b",
    r"\bi want (a|my|to)\b", r"\bokay,? (thanks|thank you)\b", r"\bcan you (please )?(check|tell|help)\b",
]
_A = [re.compile(p, re.IGNORECASE) for p in AGENT_CUES]
_C = [re.compile(p, re.IGNORECASE) for p in CUSTOMER_CUES]


def cue_score(text: str) -> float:
    """> 0 looks like the agent, < 0 looks like the customer."""
    base = sum(1 for p in _A if p.search(text)) - sum(1 for p in _C if p.search(text))
    return float(base) + telugu_cue_score(text)


# ---------------------------------------------------------------------------------
# segments -> turns
# ---------------------------------------------------------------------------------
def segments_to_turns(labelled: Sequence[Tuple[str, Segment]]) -> List[DialogueTurn]:
    """Merge consecutive same-speaker segments and compute silence/overlap information."""
    ordered = sorted(labelled, key=lambda x: (x[1].start, x[1].end))
    merged: List[List] = []  # [speaker, start, end, [texts], [romans], [confs]]
    for spk, seg in ordered:
        conf = getattr(seg, "asr_confidence", 1.0)
        roman = getattr(seg, "text_roman", "")
        if merged and merged[-1][0] == spk and seg.start - merged[-1][2] <= MERGE_GAP:
            merged[-1][2] = max(merged[-1][2], seg.end)
            merged[-1][3].append(seg.text)
            if roman:
                merged[-1][4].append(roman)
            merged[-1][5].append(conf)
        else:
            merged.append([spk, seg.start, seg.end, [seg.text], [roman] if roman else [], [conf]])
    turns: List[DialogueTurn] = []
    prev_end = 0.0
    for idx, item in enumerate(merged, start=1):
        spk, start, end, texts, romans, confs = item[0], item[1], item[2], item[3], item[4], item[5]
        overlap = idx > 1 and start < prev_end - OVERLAP_TOLERANCE
        silence = 0.0 if idx == 1 else max(0.0, start - prev_end)
        combined_text = " ".join(texts).strip()
        combined_roman = " ".join(romans).strip() if romans else (telugu_to_roman(combined_text) if is_telugu(combined_text) else None)
        avg_conf = sum(confs) / len(confs) if confs else 1.0
        turns.append(DialogueTurn(
            turn_id=idx, speaker=spk, start_time=round(start, 2), end_time=round(end, 2),
            text=combined_text,
            text_te=combined_text if is_telugu(combined_text) else None,
            text_roman=combined_roman or None,
            asr_confidence=round(avg_conf, 3),
            silence_before=round(silence, 2), overlaps_previous=overlap,
        ))
        prev_end = max(prev_end, end)
    return turns


# ---------------------------------------------------------------------------------
# mono: LLM labelling (1 request) with heuristic fallback
# ---------------------------------------------------------------------------------
def llm_label_segments(segments: Sequence[Segment], gateway) -> List[str]:
    lines = "\n".join(f"[{i}] ({s.start:.1f}s-{s.end:.1f}s) {s.text}" for i, s in enumerate(segments))
    prompt = (
        f"{lines}\n\nReturn labels for all {len(segments)} segments (i = the number in brackets)."
    )
    res = gateway.generate_structured(prompt, SegmentLabels, temperature=0.0, max_output_tokens=4096,
                                      system_instruction=_load_agent("speaker_id_agent.md"), call_id="diarize")
    by_i: Dict[int, str] = {l.i: l.speaker for l in res.labels}
    missing = [i for i in range(len(segments)) if i not in by_i]
    if missing:
        raise ValueError(f"LLM returned no label for {len(missing)} of {len(segments)} segments")
    return [by_i[i] for i in range(len(segments))]


def heuristic_labels(segments: Sequence[Segment]) -> List[str]:
    labels: List[str] = []
    prev: Optional[str] = None
    prev_end = 0.0
    for i, s in enumerate(segments):
        score = cue_score(s.text)
        if i == 0 and score >= 0:
            lab = "agent"
        elif score > 0:
            lab = "agent"
        elif score < 0:
            lab = "customer"
        else:
            gap = s.start - prev_end
            lab = prev if (prev and gap < 0.8) else ("customer" if prev == "agent" else "agent")
        labels.append(lab)
        prev, prev_end = lab, s.end
    return labels


# ---------------------------------------------------------------------------------
# stereo analysis
# ---------------------------------------------------------------------------------
def _activity(channel, window_ms: int = 250):
    import numpy as np

    samples = np.array(channel.get_array_of_samples(), dtype="float64")
    sr = channel.frame_rate
    win = max(1, int(sr * window_ms / 1000))
    n = len(samples) // win
    if n == 0:
        return np.zeros(0)
    rms = np.sqrt((samples[: n * win].reshape(n, win) ** 2).mean(axis=1))
    peak = rms.max() if rms.size else 0
    return rms > (0.12 * peak) if peak > 0 else np.zeros(n, dtype=bool)


def stereo_is_separated(audio) -> bool:
    """True when left and right carry different speakers (little simultaneous activity)."""
    if audio.channels != 2:
        return False
    left, right = audio.split_to_mono()
    a, b = _activity(left), _activity(right)
    n = min(len(a), len(b))
    if n == 0:
        return False
    a, b = a[:n], b[:n]
    both = int((a & b).sum())
    either = int((a | b).sum())
    if either == 0:
        return False
    return (a.sum() / n) > 0.05 and (b.sum() / n) > 0.05 and both / either < 0.25


def _pick_agent_channel(left_segs: Sequence[Segment], right_segs: Sequence[Segment]) -> str:
    l = sum(cue_score(s.text) for s in left_segs[:6])
    r = sum(cue_score(s.text) for s in right_segs[:6])
    return "right" if r > l else "left"


def post_process_mono_labels(labelled: List[Tuple[str, Segment]]) -> List[Tuple[str, Segment]]:
    """Mono diarization post-pass: if a segment starts with lowercase, previous does not end with . ? or !,
    and gap < 1.0s, set speaker to previous speaker.
    """
    out: List[Tuple[str, Segment]] = []
    for i, (spk, seg) in enumerate(labelled):
        if i > 0:
            prev_spk, prev_seg = out[-1]
            cur_text = seg.text.strip()
            prev_text = prev_seg.text.strip()
            gap = seg.start - prev_seg.end
            if (cur_text and cur_text[0].islower()
                    and prev_text and prev_text[-1] not in (".", "?", "!")
                    and gap < 1.0):
                spk = prev_spk
        out.append((spk, seg))
    return out


# ---------------------------------------------------------------------------------
# main entry
# ---------------------------------------------------------------------------------
def build_call_from_audio(audio_path: str, call_id: str, transcriber, gateway=None,
                          progress=None, language: Optional[str] = None) -> Tuple[CallTranscript, List[str]]:
    """Returns (CallTranscript, warnings)."""
    from pydub import AudioSegment
    from .transcribe import resolve_language

    warnings: List[str] = []
    chosen_lang = resolve_language(language)
    if chosen_lang == "auto" and hasattr(transcriber, "detect_language"):
        try:
            det_lang, prob = transcriber.detect_language(audio_path)
            if det_lang != "auto":
                chosen_lang = det_lang
        except Exception as exc:  # noqa: BLE001
            logger.warning("Language detection failed in diarize (%s)", exc)

    audio = AudioSegment.from_file(audio_path)
    duration = len(audio) / 1000.0
    method = ""
    labelled: List[Tuple[str, Segment]] = []

    if stereo_is_separated(audio):
        method = "stereo-channels"
        left, right = audio.split_to_mono()
        with tempfile.TemporaryDirectory() as tmp:
            paths = {}
            for name, ch in (("left", left), ("right", right)):
                p = os.path.join(tmp, f"{name}.wav")
                ch.set_frame_rate(16000).export(p, format="wav")
                paths[name] = p
            if progress:
                progress("transcribe", 0.15, "Transcribing left channel...")
            l_segs, _ = transcriber.transcribe(paths["left"], language=chosen_lang)
            if progress:
                progress("transcribe", 0.45, "Transcribing right channel...")
            r_segs, _ = transcriber.transcribe(paths["right"], language=chosen_lang)
        agent_side = _pick_agent_channel(l_segs, r_segs)
        for s in l_segs:
            labelled.append(("agent" if agent_side == "left" else "customer", s))
        for s in r_segs:
            labelled.append(("agent" if agent_side == "right" else "customer", s))
        method += f" (agent={agent_side})"
    else:
        if progress:
            progress("transcribe", 0.2, "Transcribing audio...")
        segs, _ = transcriber.transcribe(audio_path, language=chosen_lang)
        if not segs:
            raise ValueError("No speech was detected in the audio file.")
        if progress:
            progress("diarize", 0.55, "Separating agent and customer...")
        try:
            if gateway is None:
                raise RuntimeError("no LLM gateway")
            labels = llm_label_segments(segs, gateway)
            method = "llm-labelled mono"
        except Exception as exc:  # noqa: BLE001
            logger.warning("LLM speaker labelling failed (%s); using cue heuristic.", exc)
            labels = heuristic_labels(segs)
            method = "heuristic mono (LOW CONFIDENCE)"
            warnings.append(f"Speaker separation used a cue-based heuristic because the LLM labelling failed ({str(exc)[:120]}). Check the transcript.")
        labelled = list(zip(labels, segs))
        labelled = post_process_mono_labels(labelled)

    turns = segments_to_turns(labelled)
    call = CallTranscript(call_id=call_id, source="audio", audio_path=audio_path, language=chosen_lang,
                          duration_seconds=round(duration, 1), diarization_method=method, turns=turns)
    return call, warnings
