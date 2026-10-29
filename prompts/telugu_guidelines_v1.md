# Telugu Telephony & Support Cue Guidelines
# version: 1.0
# Purpose: Ground LLM auditors in Telugu and Romanized-Telugu colloquial customer support patterns.

## 1. Identity & Account Verification Patterns
- Agent asks for Order ID and phone digits:
  - Telugu: "దయచేసి మీ ఆర్డర్ ఐడి మరియు రిజిస్టర్డ్ మొబైల్ నంబర్ చివరి 4 అంకెలు చెప్పండి."
  - Romanized: "Dayachesi mee Order ID mariyu registered mobile number chivari 4 ankalu cheppandi."
- Failure condition: Disclosing address, name, or refund amount before hearing these details is an immediate critical breach.

## 2. Hold & Transfer Protocols
- Permission request:
  - Telugu: "నేను మీ వివరాలు పరిశీలించడానికి 1-2 నిమిషాలు కాల్ హోల్డ్ లో పెట్టవచ్చా?"
  - Romanized: "Nenu mee vivaralu parishilinchadaniki 1-2 nimishalu call hold lo pettavachha?"
- Return from hold:
  - Telugu: "లైన్ లో వేచి ఉన్నందుకు ధన్యవాదాలు."
  - Romanized: "Line lo veechi unnanduku dhanyavadalu."

## 3. Ambiguous Closure Patterns (Crucial Quality Rule)
- Customer phrase: "సరే, చూద్దాం లే" / "sare, chuddam le" ("Okay, we'll see / let's see"):
  - Interpretation: This indicates non-committal or unresolved doubt, NOT confirmed satisfaction or successful resolution.
  - Required verdict: Must be marked as an INFERRED finding with MEDIUM certainty: "Customer closure response is ambiguous and hesitant."
  - Prohibition: Do NOT mark the resolution as "customer satisfied" when this phrase occurs.

