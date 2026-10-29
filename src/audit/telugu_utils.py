"""Telugu language utilities: transliteration/romanization and cue detection.

Pure Python without external C/binary dependencies.
"""
from __future__ import annotations

import re
from typing import Optional

# Telugu Unicode character mapping to Roman script
TELUGU_ROMAN_MAP = {
    # Vowels
    "\u0c05": "a", "\u0c06": "aa", "\u0c07": "i", "\u0c08": "ee", "\u0c09": "u", "\u0c0a": "oo",
    "\u0c0b": "ru", "\u0c0e": "e", "\u0c0f": "ee", "\u0c10": "ai", "\u0c12": "o", "\u0c13": "oo",
    "\u0c14": "au", "\u0c02": "m", "\u0c03": "h",
    # Consonants
    "\u0c15": "k", "\u0c16": "kh", "\u0c17": "g", "\u0c18": "gh", "\u0c19": "ng",
    "\u0c1a": "ch", "\u0c1b": "chh", "\u0c1c": "j", "\u0c1d": "jh", "\u0c1e": "ny",
    "\u0c1f": "t", "\u0c20": "th", "\u0c21": "d", "\u0c22": "dh", "\u0c23": "n",
    "\u0c24": "t", "\u0c25": "th", "\u0c26": "d", "\u0c27": "dh", "\u0c28": "n",
    "\u0c2a": "p", "\u0c2b": "ph", "\u0c2c": "b", "\u0c2d": "bh", "\u0c2e": "m",
    "\u0c2f": "y", "\u0c30": "r", "\u0c31": "r", "\u0c32": "l", "\u0c33": "l",
    "\u0c35": "v", "\u0c36": "sh", "\u0c37": "sh", "\u0c38": "s", "\u0c39": "h",
    # Matras (vowel signs)
    "\u0c3e": "aa", "\u0c3f": "i", "\u0c40": "ee", "\u0c41": "u", "\u0c42": "oo",
    "\u0c43": "ru", "\u0c46": "e", "\u0c47": "ee", "\u0c48": "ai", "\u0c4a": "o",
    "\u0c4b": "oo", "\u0c4c": "au", "\u0c4d": "",
}

TELUGU_CHAR_RE = re.compile(r"[\u0c00-\u0c7f]")


def is_telugu(text: str) -> bool:
    """Return True if the text contains Telugu Unicode characters."""
    return bool(TELUGU_CHAR_RE.search(text))


def telugu_to_roman(text: str) -> str:
    """Transliterate Telugu Unicode text into approximate readable Latin/Roman script."""
    if not text:
        return ""
    result = []
    i = 0
    chars = list(text)
    n = len(chars)
    while i < n:
        c = chars[i]
        if c in TELUGU_ROMAN_MAP:
            val = TELUGU_ROMAN_MAP[c]
            # If consonant followed by virama (halant \u0c4d), don't append inherent 'a'
            is_consonant = "\u0c15" <= c <= "\u0c39"
            next_c = chars[i + 1] if i + 1 < n else ""
            is_followed_by_matra = "\u0c3e" <= next_c <= "\u0c4c"
            is_followed_by_virama = next_c == "\u0c4d"

            if is_consonant and not is_followed_by_matra and not is_followed_by_virama:
                val += "a"
            result.append(val)
        else:
            result.append(c)
        i += 1
    return "".join(result).strip()


# Telugu specific cues
TELUGU_AGENT_CUES = [
    r"నమస్కారం", r"ధన్యవాదాలు", r"సహాయం", r"ఆర్డర్ ఐడి", r"రికార్డ్", r"హోల్డ్",
    r"ధృవీకరణ", r"వివరాలు", r"పేరు", r"కస్టమర్ కేర్", r"క్షమించండి",
    # Romanized equivalents
    r"\bnamaskaram\b", r"\bdhanyavadalu\b", r"\bsahayam\b", r"\border id\b",
    r"\brecord\b", r"\bhold\b", r"\bshopease\b", r"\bapologize\b", r"\bverify\b",
]

TELUGU_CUSTOMER_CUES = [
    r"నా ఆర్డర్", r"డెలివరీ", r"రాలేదు", r"రిఫండ్", r"రీప్లేస్మెంట్", r"ఎప్పుడు",
    r"సమస్య", r"సరే,? చూద్దాం లే", r"డ్యామేజ్",
    # Romanized equivalents
    r"\bnaa order\b", r"\brefund\b", r"\bdelivery\b", r"\breplacement\b",
    r"\bsare,? chuddam le\b", r"\beppudu\b", r"\bproblem\b",
]

_TE_A = [re.compile(p, re.IGNORECASE) for p in TELUGU_AGENT_CUES]
_TE_C = [re.compile(p, re.IGNORECASE) for p in TELUGU_CUSTOMER_CUES]


def telugu_cue_score(text: str) -> float:
    """Positive = agent-like, negative = customer-like."""
    score = sum(1 for p in _TE_A if p.search(text)) - sum(1 for p in _TE_C if p.search(text))
    return float(score)

