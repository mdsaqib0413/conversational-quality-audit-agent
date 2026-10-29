"""Voice variety for the synthetic test calls: different accents, genders, speaking speeds and emotions."""
from __future__ import annotations

import random
import re
from typing import Dict, List, Sequence, Tuple

FEMALE = {"priya", "sneha", "meera", "pooja", "deepa", "neha", "anita", "farah", "ananya", "kavya", "divya", "sunita", "anjali", "riya", "pooja"}
MALE = {"rajesh", "vikram", "arjun", "suresh", "rahul", "rohit", "karan", "amit", "imran", "ravi", "sunil", "aman", "karthik", "deepak", "rohan"}
# (rate, pitch, volume) offsets per emotion; used for the customer's mood and the agent's tone
PROSODY: Dict[str, Tuple[int, int, int]] = {
    "angry": (14, 4, 12), "frustrated": (8, 2, 6), "anxious": (10, 3, 0), "confused": (-6, 1, -2), "neutral": (0, 0, 0),
    "satisfied": (0, 2, 3), "happy": (4, 4, 6), "defensive": (10, 1, 6), "dismissive": (8, -2, 0), "empathetic": (-6, -1, -2), "warm": (-2, 1, 2),
}
LOCALE_WEIGHTS = [("en-IN", 6), ("en-GB", 1), ("en-US", 2), ("en-AU", 1)]
FALLBACK = {"F": "en-IN-NeerjaNeural", "M": "en-IN-PrabhatNeural"}
ANGER = re.compile(r"unacceptable|ridiculous|fed up|worst|terrible|third time|cheat|consumer court|how many times", re.I)


def guess_gender(name: str, rng: random.Random) -> str:
    first = (name or "").split()[0].lower().strip(".")
    return "F" if first in FEMALE else "M" if first in MALE else rng.choice("FM")


def pick_voices(voices: Sequence[dict], gender: str, rng: random.Random, avoid: str = "") -> str:
    """voices = edge_tts.list_voices() entries. Picks an English voice of the gender, favouring Indian English."""
    want = "Female" if gender == "F" else "Male"
    pool: List[str] = []
    for loc, w in LOCALE_WEIGHTS:
        names = sorted(v["ShortName"] for v in voices if v.get("Locale") == loc and v.get("Gender") == want and "Multilingual" not in v["ShortName"])
        pool += [n for n in names for _ in range(w)] if names else []
    pool = [n for n in pool if n != avoid] or pool
    return rng.choice(pool) if pool else FALLBACK[gender]


def customer_emotions(raw: dict) -> Dict[int, str]:
    """Per customer turn: the labelled arc spread over the call, sharpened by anger words."""
    arc = (raw["ground_truth"].get("customer_emotion_arc") or ["neutral"] * 3) + ["neutral"] * 3
    cust = [t for t in raw["turns"] if t["speaker"] == "customer"]
    out = {}
    for i, t in enumerate(cust):
        f = i / max(1, len(cust) - 1)
        e = arc[0] if f < 0.34 else arc[1] if f < 0.67 else arc[2]
        if ANGER.search(t["text"]) and e in ("frustrated", "neutral"):
            e = "angry"
        out[t["i"]] = e
    return out


def agent_tone(raw: dict, turn: dict) -> str:
    steps = raw["ground_truth"].get("sop_steps", {})
    if steps.get("ANG-01") == "missed" and turn["i"] > 2:
        return "defensive"
    if steps.get("GEN-05") == "missed" and not re.search(r"sorry|apolog|understand", turn["text"], re.I):
        return "dismissive" if turn["i"] > 3 else "neutral"
    return "empathetic" if re.search(r"sorry|apolog|understand", turn["text"], re.I) else "neutral"


def fmt(value: int, unit: str) -> str:
    return f"{value:+d}{unit}"


def prosody_args(emotion: str, base_rate: int) -> Dict[str, str]:
    r, p, v = PROSODY.get(emotion, (0, 0, 0))
    return {"rate": fmt(r + base_rate, "%"), "pitch": fmt(p, "Hz"), "volume": fmt(v, "%")}
