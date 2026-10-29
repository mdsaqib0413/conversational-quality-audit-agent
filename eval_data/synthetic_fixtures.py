"""Synthetic Telugu call fixtures for Phase 1 & 2 evaluation.

All fixtures are explicitly marked SYNTHETIC and represent controlled
operational cases defined in the capstone specification:
1. scenario_a: early identity verification breach -> score cap 70.0
2. scenario_b: two holds + ambiguous closure ('sare, chuddam le')
3. unusable: <0.40 confidence or >65% silence -> cannot_judge=True, 0 LLM calls
4. degraded: 0.55 confidence -> findings tagged degraded certainty
5. long_56turns: 56 turns preserving early state
6. no_holds: zero hold events -> hold_handling not_applicable
7. verification_ok: order ID + phone verified prior to account discussion -> followed
8. out_of_scope: non-support personal chat -> refused / cannot_judge=True
"""
from __future__ import annotations

from src.audit.schemas import CallTranscript, DialogueTurn

def get_synthetic_fixtures() -> dict[str, CallTranscript]:
    fixtures = {}

    # 1. Scenario A: Identity Verification Breached
    fixtures["te_synthetic_scenario_a"] = CallTranscript(
        call_id="te_synthetic_scenario_a",
        language="te",
        duration_seconds=42.0,
        turns=[
            DialogueTurn(turn_id=1, speaker="agent", text="షాపేజ్ కస్టమర్ కేర్ కి స్వాగతం. నా పేరు రాహుల్. ఈ కాల్ రికార్డ్ చేయబడుతుంది.", start_time=0.0, end_time=4.0),
            DialogueTurn(turn_id=2, speaker="customer", text="నమస్కారం అండీ, నేను ఆర్డర్ చేసిన బోట్ స్మార్ట్‌వాచ్ డెలివరీ కాలేదు.", start_time=4.5, end_time=8.5),
            DialogueTurn(turn_id=3, speaker="agent", text="సరే అండీ, మీ ఆర్డర్ ఫ్లాట్ 12, సాయి రెసిడెన్సీ అడ్రస్ కి 8,500 రూపాయలకు పంపించాము.", start_time=9.0, end_time=14.0),
            DialogueTurn(turn_id=4, speaker="customer", text="అవును ఆ అడ్రస్సే, కానీ ఇంకా డెలివరీ రాలేదు.", start_time=14.5, end_time=17.5),
            DialogueTurn(turn_id=5, speaker="agent", text="కొరియర్ పార్టనర్ ఆలస్యం చేశారు, నేను ఇప్పుడే రీ-డిస్పాచ్ చేస్తున్నాను.", start_time=18.0, end_time=22.0),
            DialogueTurn(turn_id=6, speaker="customer", text="ధన్యవాదాలు, ఎప్పటి వరకు వస్తుంది?", start_time=22.5, end_time=25.0),
            DialogueTurn(turn_id=7, speaker="agent", text="రేపు సాయంత్రం 5 గంటల లోపు డెలివరీ పూర్తవుతుంది. ట్రాకింగ్ మెసేజ్ పంపాను.", start_time=25.5, end_time=29.5),
            DialogueTurn(turn_id=8, speaker="customer", text="సరే చాలా సంతోషం, సమస్య పరిష్కరించారు.", start_time=30.0, end_time=33.0),
            DialogueTurn(turn_id=9, speaker="agent", text="షాపేజ్ కి కాల్ చేసినందుకు ధన్యవాదాలు. సెలవు.", start_time=33.5, end_time=36.0),
        ]
    )

    # 2. Scenario B: Two Holds + Ambiguous Closure
    fixtures["te_synthetic_scenario_b"] = CallTranscript(
        call_id="te_synthetic_scenario_b",
        language="te",
        duration_seconds=110.0,
        turns=[
            DialogueTurn(turn_id=1, speaker="agent", text="షాపేజ్ సపోర్ట్ కి స్వాగతం. ఈ కాల్ రికార్డ్ చేయబడుతుంది. మీ ఆర్డర్ ఐడి మరియు ఫోన్ చివరి 4 అంకెలు చెప్పండి.", start_time=0.0, end_time=5.0),
            DialogueTurn(turn_id=2, speaker="customer", text="నా ఆర్డర్ ORD-77881, ఫోన్ చివరి నంబర్లు 4412. నా రీఫండ్ ఇంకా రాలేదు.", start_time=5.5, end_time=10.0),
            DialogueTurn(turn_id=3, speaker="agent", text="ధన్యవాదాలు. వివరాలు తనిఖీ చేయడానికి ఒక నిమిషం కాల్ హోల్డ్ లో పెట్టవచ్చా అండీ?", start_time=10.5, end_time=15.0),
            DialogueTurn(turn_id=4, speaker="customer", text="సరే పెట్టండి.", start_time=15.5, end_time=17.0),
            DialogueTurn(turn_id=5, speaker="agent", text="లైన్ లో వేచి ఉన్నందుకు ధన్యవాదాలు. బ్యాంక్ సర్వర్ డౌన్ ఉంది. ఫైనాన్స్ టీమ్ ని సంప్రదించడానికి ఇంకో చిన్న హోల్డ్ లో ఉండండి.", start_time=48.0, end_time=54.0),
            DialogueTurn(turn_id=6, speaker="customer", text="సరే త్వరగా చూడండి.", start_time=54.5, end_time=56.0),
            DialogueTurn(turn_id=7, speaker="agent", text="వేచి ఉన్నందుకు ధన్యవాదాలు. మీ రీఫండ్ రూ. 3,200 ప్రాసెస్ చేయబడింది. 3 రోజుల్లో మీ ఖాతాలో జమ అవుతుంది.", start_time=87.0, end_time=93.0),
            DialogueTurn(turn_id=8, speaker="customer", text="సరే, చూద్దాం లే.", start_time=93.5, end_time=96.0),
            DialogueTurn(turn_id=9, speaker="agent", text="షాపేజ్ కి కాల్ చేసినందుకు ధన్యవాదాలు. మంచి రోజు.", start_time=96.5, end_time=100.0),
        ]
    )

    # 3. Unusable Audio
    fixtures["te_synthetic_unusable"] = CallTranscript(
        call_id="te_synthetic_unusable",
        language="te",
        duration_seconds=50.0,
        turns=[
            DialogueTurn(turn_id=1, speaker="agent", text="...", asr_confidence=0.20, silence_before=0.0, start_time=0.0, end_time=2.0),
            DialogueTurn(turn_id=2, speaker="customer", text="...", asr_confidence=0.15, silence_before=15.0, start_time=17.0, end_time=19.0),
            DialogueTurn(turn_id=3, speaker="agent", text="...", asr_confidence=0.25, silence_before=20.0, start_time=39.0, end_time=41.0),
        ]
    )

    # 4. Degraded Audio
    fixtures["te_synthetic_degraded"] = CallTranscript(
        call_id="te_synthetic_degraded",
        language="te",
        duration_seconds=30.0,
        turns=[
            DialogueTurn(turn_id=1, speaker="agent", text="షాపేజ్ కస్టమర్ కేర్. ఈ కాల్ రికార్డ్ అవుతుంది.", asr_confidence=0.55, start_time=0.0, end_time=3.0),
            DialogueTurn(turn_id=2, speaker="customer", text="నాకు నా ఆర్డర్ రాలేదు అండీ.", asr_confidence=0.52, start_time=3.5, end_time=6.0),
            DialogueTurn(turn_id=3, speaker="agent", text="మేము పరిశీలిస్తున్నాము.", asr_confidence=0.54, start_time=6.5, end_time=9.0),
        ]
    )

    # 5. Long Call (56 turns with early breach)
    base_turns = [
        DialogueTurn(turn_id=1, speaker="agent", text="షాపేజ్ సపోర్ట్. నా పేరు రమేష్.", start_time=0.0, end_time=3.0),
        DialogueTurn(turn_id=2, speaker="customer", text="నా ఆర్డర్ రీప్లేస్మెంట్ కావాలి.", start_time=3.5, end_time=6.0),
        DialogueTurn(turn_id=3, speaker="agent", text="మీ ఆర్డర్ ఫ్లాట్ 12, సాయి రెసిడెన్సీ అడ్రస్ కి వెళ్ళింది.", start_time=6.5, end_time=10.0),
    ]
    curr_time = 10.5
    extra_turns = []
    for i in range(4, 57):
        spk = "customer" if i % 2 == 0 else "agent"
        extra_turns.append(DialogueTurn(
            turn_id=i,
            speaker=spk,
            text="సరే అండీ వివరాలు అర్థమయ్యాయి." if spk == "customer" else "నేను మీ సమస్యను పరిశీలిస్తున్నాను.",
            start_time=curr_time,
            end_time=curr_time + 2.0,
        ))
        curr_time += 2.5
    fixtures["te_synthetic_long_56turns"] = CallTranscript(
        call_id="te_synthetic_long_56turns",
        language="te",
        duration_seconds=curr_time,
        turns=base_turns + extra_turns
    )

    # 6. No Holds Call
    fixtures["te_synthetic_no_holds"] = CallTranscript(
        call_id="te_synthetic_no_holds",
        language="te",
        duration_seconds=35.0,
        turns=[
            DialogueTurn(turn_id=1, speaker="agent", text="షాపేజ్ సపోర్ట్ కి స్వాగతం. నా పేరు వికాస్. ఈ కాల్ రికార్డ్ చేయబడుతుంది. మీ ఆర్డర్ ఐడి చెప్పండి.", start_time=0.0, end_time=4.5),
            DialogueTurn(turn_id=2, speaker="customer", text="నా ఆర్డర్ ఐడి ORD-10293, ఫోన్ చివరి 4 అంకెలు 8891.", start_time=5.0, end_time=9.0),
            DialogueTurn(turn_id=3, speaker="agent", text="ధన్యవాదాలు. మీ ప్రొడక్ట్ ఇన్వాయిస్ కాపీ మీ ఈమెయిల్ కి పంపాను.", start_time=9.5, end_time=14.0),
            DialogueTurn(turn_id=4, speaker="customer", text="అవును ఈమెయిల్ వచ్చింది, చాలా ధన్యవాదాలు.", start_time=14.5, end_time=17.5),
            DialogueTurn(turn_id=5, speaker="agent", text="షాపేజ్ కి కాల్ చేసినందుకు ధన్యవాదాలు. సెలవు.", start_time=18.0, end_time=21.0),
        ]
    )

    # 7. Verification Done Correctly
    fixtures["te_synthetic_verification_ok"] = CallTranscript(
        call_id="te_synthetic_verification_ok",
        language="te",
        duration_seconds=40.0,
        turns=[
            DialogueTurn(turn_id=1, speaker="agent", text="షాపేజ్ కస్టమర్ కేర్. నా పేరు ఆనంద్. ఈ కాల్ నాణ్యత కొరకు రికార్డ్ చేయబడుతుంది. మీ ఆర్డర్ ఐడి మరియు ఫోన్ చివరి 4 నంబర్లు చెప్పగలరా?", start_time=0.0, end_time=5.5),
            DialogueTurn(turn_id=2, speaker="customer", text="ఆర్డర్ ఐడి ORD-44551 మరియు ఫోన్ చివరి 4 అంకెలు 9012.", start_time=6.0, end_time=10.0),
            DialogueTurn(turn_id=3, speaker="agent", text="ధన్యవాదాలు. మీ ఖాతా ధృవీకరించబడింది. మీ ఆర్డర్ ఫ్లాట్ 12 కి రేపు డెలివరీ అవుతుంది.", start_time=10.5, end_time=15.0),
            DialogueTurn(turn_id=4, speaker="customer", text="చాలా ధన్యవాదాలు ఆనంద్ గారు.", start_time=15.5, end_time=18.0),
            DialogueTurn(turn_id=5, speaker="agent", text="షాపేజ్ ని ఎంచుకున్నందుకు ధన్యవాదాలు.", start_time=18.5, end_time=21.5),
        ]
    )

    # 8. Out of Scope (Casual Personal Chat)
    fixtures["te_synthetic_out_of_scope"] = CallTranscript(
        call_id="te_synthetic_out_of_scope",
        language="te",
        duration_seconds=25.0,
        turns=[
            DialogueTurn(turn_id=1, speaker="agent", text="హలో సురేష్, ఈరోజు సాయంత్రం సినిమాకి వెళ్దామా?", start_time=0.0, end_time=3.5),
            DialogueTurn(turn_id=2, speaker="customer", text="ఈరోజు కుదరదు రా, రేపు క్రికెట్ మ్యాచ్ ఆడుకుందాం.", start_time=4.0, end_time=7.5),
            DialogueTurn(turn_id=3, speaker="agent", text="సరే రేపు గ్రౌండ్ కి వచ్చేయ్.", start_time=8.0, end_time=10.5),
        ]
    )

    return fixtures

