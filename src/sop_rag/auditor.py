"""18-Rule Deterministic Pre-Trade SOP Auditor + BM25 Evidence Grounding + Optional Gemini Hook."""

from __future__ import annotations

from dataclasses import dataclass, asdict
import json
import os
import re
import urllib.request

from sop_rag.indexer import CorpusBM25Index


@dataclass(frozen=True)
class RuleViolation:
    rule_id: str
    severity: str  # REJECT | WARN
    title: str
    reason: str
    citation: str
    youtube_url: str

    def to_dict(self) -> dict:
        return asdict(self)


def _yt(vid: str, sec: int) -> str:
    return f"https://www.youtube.com/watch?v={vid}&t={sec}s"


def evaluate_sop_rules(plan_text: str, structured: dict | None = None) -> list[RuleViolation]:
    """Run all 18 Arist MD & Co-Mentor SOP rules against free-form text and optional JSON metadata."""
    txt = plan_text.lower()
    meta = structured or {}
    violations: list[RuleViolation] = []

    # 1. Buying above EQL / Selling below EQH without sweep
    if meta.get("above_eql_without_sweep") or (
        re.search(r"\b(buy|long)\b", txt) and re.search(r"\b(di atas|above)\s+eql\b", txt) and "sweep" not in txt
    ) or (
        re.search(r"\b(sell|short)\b", txt) and re.search(r"\b(di bawah|below)\s+eqh\b", txt) and "sweep" not in txt
    ) or ("tanpa tunggu sweep" in txt and ("eql" in txt or "eqh" in txt)):
        violations.append(
            RuleViolation(
                "SOP-01",
                "REJECT",
                "Unswept EQL/EQH Liquidity Trap",
                "Dilarang Buy tepat di atas EQL atau Sell tepat di bawah EQH sebelum likuiditas disapu + BOS.",
                "BXxdVGV1sUY @ 06:55",
                _yt("BXxdVGV1sUY", 415),
            )
        )

    # 2. Entering mid-FVG / Imbalance before 70-80% fill
    if meta.get("mid_fvg_unfilled") or (
        ("fvg" in txt or "imbalance" in txt)
        and re.search(r"\b(tengah|mid|belum terisi|unfilled|langsung)\b", txt)
    ):
        violations.append(
            RuleViolation(
                "SOP-02",
                "REJECT",
                "Premature Mid-FVG / Imbalance Entry",
                "Jangan entry di tengah celah FVG; tunggu Imbalance terisi 70%-80% hingga menyentuh S&D di belakangnya.",
                "Ut1nFrj5Svs @ 05:21",
                _yt("Ut1nFrj5Svs", 321),
            )
        )

    # 3. Direct trendline touch entry without sweep + BOS
    if meta.get("direct_trendline_entry") or (
        "trendline" in txt and re.search(r"\b(langsung|pantulan ke-3|sentuh|touch)\b", txt) and "false break" not in txt
    ):
        violations.append(
            RuleViolation(
                "SOP-03",
                "REJECT",
                "Trendline Retail Liquidity Trap",
                "Trendline adalah kolam likuiditas; dilarang entry langsung di garis trendline tanpa false breakout ke Strong S&D + BOS.",
                "U95mfBuT6BM @ 01:46",
                _yt("U95mfBuT6BM", 106),
            )
        )

    # 4. Trading inside Ichimoku Kumo Cloud or tangled 4MA sideways
    if meta.get("inside_kumo_or_tangled_ma") or (
        re.search(r"\b(dalam kumo|inside kumo|inside cloud|dalam awan|4ma kusut|ma kusut|tangled)\b", txt)
    ):
        violations.append(
            RuleViolation(
                "SOP-04",
                "REJECT",
                "Sideways / Inside Kumo Cloud NO-TRADE Regime",
                "Saat harga di dalam Ichimoku Kumo Cloud atau 4MA kusut, matikan tools trend-following dan DIAM.",
                "Zritj0nmL9U @ 00:27",
                _yt("Zritj0nmL9U", 27),
            )
        )

    # 5. Converting losing scalping trade into swing
    if meta.get("convert_scalp_to_swing") or (
        ("scalp" in txt or "scalping" in txt)
        and re.search(r"\b(ubah|convert|tahan|hold)\b", txt)
        and "swing" in txt
    ):
        violations.append(
            RuleViolation(
                "SOP-05",
                "REJECT",
                "Scalping Minus Diubah Menjadi Swing",
                "ATURAN KERAS Franz: Posisi scalping yang minus HARAM ditahan atau diubah targetnya menjadi swing.",
                "rZC0YrjKSkc @ 03:30",
                _yt("rZC0YrjKSkc", 210),
            )
        )

    # 6. Missing System SL on regular/high-RR account
    if meta.get("no_system_sl") or (
        re.search(r"\b(tanpa sl|no sl|mental sl|without stop loss)\b", txt) and "defense 1:1" not in txt
    ):
        violations.append(
            RuleViolation(
                "SOP-06",
                "REJECT",
                "Missing Broker System Stop Loss",
                "Akun reguler dan High-RR WAJIB memakai System SL di broker untuk menghindari denial, freeze, dan slippage gap.",
                "VpacB5MdAEU @ 07:05",
                _yt("VpacB5MdAEU", 425),
            )
        )

    # 7. Correlated pairs inside the same account
    corr_pair_hits = (
        ("xau" in txt and "xag" in txt)
        or ("eurusd" in txt and "gbpusd" in txt)
        or ("audusd" in txt and ("eurusd" in txt or "nzdusd" in txt))
        or ("usdjpy" in txt and "gbpjpy" in txt)
    )
    if meta.get("correlated_in_same_account") or (corr_pair_hits and "terpisah" not in txt):
        violations.append(
            RuleViolation(
                "SOP-07",
                "REJECT",
                "Correlated Pairs in Single Compartment",
                "Dilarang menaruh aset berkorelasi positif (XAU+XAG atau EUR/GBP/AUD-USD) dalam satu akun Lambung Kapal.",
                "WAOZM1Jg0bQ @ 40:40",
                _yt("WAOZM1Jg0bQ", 2440),
            )
        )

    # 8. Daily open risk > 10% without BEP unlock
    open_risk = float(meta.get("open_risk_pct", 0.0))
    if open_risk > 10.0 or re.search(r"\bopen risk\s*(>|di atas)?\s*(1[1-9]|[2-9]\d)%", txt):
        violations.append(
            RuleViolation(
                "SOP-08",
                "REJECT",
                "Max 10% Open Risk Exceeded",
                "Batas total open risk bersamaan maksimal 10%. Geser posisi profit >=50% ke BEP (0% risk) sebelum membuka slot baru.",
                "VpacB5MdAEU @ 09:20",
                _yt("VpacB5MdAEU", 560),
            )
        )

    # 9. Using hot money / debt / >10% income
    if meta.get("hot_money") or re.search(r"\b(duit panas|pinjol|utang|uang spp|gadai)\b", txt):
        violations.append(
            RuleViolation(
                "SOP-09",
                "REJECT",
                "Hot Money / Debt Capital Violation",
                "Dilarang keras trading memakai duit panas, pinjol, atau dana kebutuhan pokok; gunakan max 5%-10% penghasilan.",
                "VpacB5MdAEU @ 00:32",
                _yt("VpacB5MdAEU", 32),
            )
        )

    # 10. Post-00:00 WIB entry or High-Impact News on regular account
    if meta.get("after_midnight_or_news") or re.search(r"\b(00:00|01:00|02:00|tengah malam|jelang news|nfp|fomc|cpi)\b", txt):
        if "2-hp" not in txt:
            violations.append(
                RuleViolation(
                    "SOP-10",
                    "WARN",
                    "Late Session (>00:00 WIB) / High-Impact News Exposure",
                    "Hindari entry baru setelah 00:00 WIB dan hindari rilis high-impact news di akun reguler.",
                    "eHWmib4NKz0 @ 18:16",
                    _yt("eHWmib4NKz0", 1096),
                )
            )

    # 11. Franz 3-TF scalp misalignment or RSI ~50
    if meta.get("scalp_misaligned") or (
        ("franz" in txt or "scalp" in txt)
        and (re.search(r"\b(beda arah|tidak searah|2/3|m15.*lawan|rsi\s*~?50|rsi\s*50)\b", txt))
    ):
        violations.append(
            RuleViolation(
                "SOP-11",
                "REJECT",
                "Franz 3-TF Misalignment / Neutral RSI ~50",
                "Scalping M15/M5/M1 wajib 100% searah pada 3 TF dan dilarang masuk saat RSI di zona netral ~50.",
                "JbKfARTc9TU @ 23:12",
                _yt("JbKfARTc9TU", 1392),
            )
        )

    # 12. Trend Change (TC) in mid-range outside HTF S&D / PD Extreme
    if meta.get("tc_in_empty_midrange") or (
        re.search(r"\b(tc|trend change|choch)\b", txt) and re.search(r"\b(tengah|kosong|mid-range|bukan s&d)\b", txt)
    ):
        violations.append(
            RuleViolation(
                "SOP-12",
                "REJECT",
                "Unanchored Trend Change (Mid-Range TC)",
                "TC hanya sah apabila muncul di dalam Zona S&D HTF atau area ekstrem PD Range — dilarang entry di chart kosong.",
                "oz52BAFzPJg @ 40:32",
                _yt("oz52BAFzPJg", 2432),
            )
        )

    # 13. Buying in Premium (>0.5) or Selling in Discount (<0.5)
    if meta.get("wrong_pd_zone") or (
        (re.search(r"\b(buy|long)\b", txt) and "premium" in txt)
        or (re.search(r"\b(sell|short)\b", txt) and "discount" in txt)
    ):
        violations.append(
            RuleViolation(
                "SOP-13",
                "REJECT",
                "PD Range Misalignment (Buy Premium / Sell Discount)",
                "PD Range 0/0.5/1: Hanya cari Buy di zona Discount (<0.5) dan Sell di zona Premium (>0.5).",
                "oz52BAFzPJg @ 24:30",
                _yt("oz52BAFzPJg", 1470),
            )
        )

    # 14. Minimum R:R violation (< 1:2 Harmonic or < 1:3 Continuation)
    rr_val = meta.get("rr")
    m_rr = re.search(r"\br[:/ ]?r\s*(?:1\s*:\s*)?(\d+(?:\.\d+)?)", txt)
    if rr_val is None and m_rr:
        rr_val = float(m_rr.group(1))
    if rr_val is not None:
        if ("continuation" in txt and rr_val < 3.0) or rr_val < 2.0:
            violations.append(
                RuleViolation(
                    "SOP-14",
                    "REJECT",
                    "Minimum Risk:Reward Not Met",
                    "Minimum R:R wajib >= 1:2 untuk Harmonic TP1 dan >= 1:3 untuk SMC Continuation.",
                    "r3d7-7d2coc @ 12:19",
                    _yt("r3d7-7d2coc", 739),
                )
            )

    # 15. Premature average down in spot stocks/crypto before Weekly/Daily PRZ
    if meta.get("premature_average_down") or (
        re.search(r"\b(average down|cicil)\b", txt) and re.search(r"\b(belum prz|jatuh bebas|sebelum prz)\b", txt)
    ):
        violations.append(
            RuleViolation(
                "SOP-15",
                "REJECT",
                "Premature Average Down Before Macro PRZ",
                "Haram average down saham/kripto saat pasar masih jatuh bebas sebelum menyentuh kotak PRZ Weekly/Daily.",
                "FE8kANtxAro @ 01:56",
                _yt("FE8kANtxAro", 116),
            )
        )

    # 16. Mixing MACD (Lagging) & Stochastic (Leading) bias
    if meta.get("mixed_macd_stochastic") or ("macd" in txt and "stochastic" in txt and "sepakat" not in txt and "divergen" not in txt):
        violations.append(
            RuleViolation(
                "SOP-16",
                "WARN",
                "Lagging MACD vs Leading Stochastic Conflict",
                "MACD bersifat Lagging sedangkan Stochastic bersifat Leading — jangan campur sinyal bias yang bertolak belakang.",
                "cfw_O5dG4Bk @ 06:13",
                _yt("cfw_O5dG4Bk", 373),
            )
        )

    # 17. Post-MC revenge / >0.01 lot OR post-big-win euphoria without cooling off
    if meta.get("post_mc_revenge") or re.search(r"\b(revenge|balas dendam|habis mc|euforia)\b", txt):
        violations.append(
            RuleViolation(
                "SOP-17",
                "REJECT",
                "Post-MC Revenge / Post-Win Euphoria Guard",
                "Wajib cooling-off 2-3 hari pasca-MC + recovery lot 0.01 metode ABC, atau jeda 1-2 minggu pasca-profit besar.",
                "WAOZM1Jg0bQ @ 57:00",
                _yt("WAOZM1Jg0bQ", 3420),
            )
        )

    # 18. Mitigated (non-fresh) S&D zone re-entry
    if meta.get("mitigated_zone") or re.search(r"\b(mitigated|sudah tersentuh|retest kedua|tidak fresh)\b", txt):
        violations.append(
            RuleViolation(
                "SOP-18",
                "REJECT",
                "Mitigated (Non-Fresh) S&D Zone",
                "Fokus hanya pada zona S&D Fresh (belum tersentuh wick/body); zona yang sudah ter-retest dianggap habis ordernya.",
                "zXxYxVe8ukA @ 01:48",
                _yt("zXxYxVe8ukA", 108),
            )
        )

    return violations


def audit_trade_plan(
    plan_text: str,
    index: CorpusBM25Index | None = None,
    structured: dict | None = None,
    top_k: int = 4,
) -> dict:
    """Audit a trade plan deterministically across 18 SOP rules and attach BM25 video evidence."""
    idx = index or CorpusBM25Index()
    violations = evaluate_sop_rules(plan_text, structured=structured)
    evidence = idx.search(plan_text, top_k=top_k)

    has_reject = any(v.severity == "REJECT" for v in violations)
    has_warn = any(v.severity == "WARN" for v in violations)
    verdict = "REJECT" if has_reject else "WARN" if has_warn else "PASS"

    return {
        "verdict": verdict,
        "violation_count": len(violations),
        "violations": [v.to_dict() for v in violations],
        "supporting_evidence": evidence,
    }


def audit_with_gemini(
    plan_text: str,
    evidence: list[dict],
    api_key: str | None = None,
    model: str = "gemini-2.5-flash",
) -> str:
    """Optional Gemini synthesis over retrieved BM25 passages (only invoked when explicitly enabled)."""
    key = api_key or os.environ.get("GEMINI_API_KEY", "").strip()
    if not key:
        raise RuntimeError("GEMINI_API_KEY is required when --gemini is enabled.")
    ctx = "\n".join(
        f"- [{e['video_id']} | {e['speaker_layer']} | {','.join(e['timestamps'])}]: {e['excerpt']}"
        for e in evidence
    )
    prompt = (
        "Audit the following trade plan against the Arist MD / Mancing Dollar Playbook excerpts below. "
        "Cite exact video IDs and timestamps.\n\n"
        f"Trade Plan:\n{plan_text}\n\nEvidence Passages:\n{ctx}"
    )
    url = f"https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent?key={key}"
    payload = json.dumps({"contents": [{"parts": [{"text": prompt}]}]}).encode("utf-8")
    req = urllib.request.Request(url, data=payload, headers={"Content-Type": "application/json"}, method="POST")
    with urllib.request.urlopen(req, timeout=30) as resp:
        data = json.loads(resp.read().decode("utf-8"))
    return data["candidates"][0]["content"]["parts"][0]["text"]
