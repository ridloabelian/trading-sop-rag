from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "src"))

from sop_rag.auditor import audit_trade_plan  # noqa: E402
from sop_rag.cli import main as cli_main  # noqa: E402
from sop_rag.indexer import CorpusBM25Index  # noqa: E402
from sop_rag.portal import build_portal  # noqa: E402


def test_indexer_covers_all_199_videos():
    idx = CorpusBM25Index(ROOT / "corpus")
    assert len(idx.note_video_ids) == 199
    assert len(idx.chunks) > 400

    res_stingray = idx.search("Stingray 1.272 Point B", top_k=5)
    assert len(res_stingray) >= 3
    assert any(r["youtube_url"].startswith("https://www.youtube.com/watch?v=") for r in res_stingray)

    res_franz = idx.search("scalping M15 M5 M1 Kocokan", speaker_filter="Franz", top_k=5)
    assert len(res_franz) >= 1
    assert all("franz" in r["speaker_layer"].lower() for r in res_franz)


def test_auditor_rejects_sop_violations_with_video_citations():
    idx = CorpusBM25Index(ROOT / "corpus")

    bad_eql = audit_trade_plan("Mau Buy XAUUSD tepat di atas EQL tanpa tunggu sweep dan tanpa SL", index=idx)
    assert bad_eql["verdict"] == "REJECT"
    ids = {v["rule_id"] for v in bad_eql["violations"]}
    assert "SOP-01" in ids and "SOP-06" in ids
    assert any("BXxdVGV1sUY" in v["citation"] for v in bad_eql["violations"])

    bad_scalp = audit_trade_plan("Scalping XAUUSD lagi minus jadi saya ubah jadi swing, plus open XAGUSD di akun yang sama", index=idx)
    assert bad_scalp["verdict"] == "REJECT"
    ids2 = {v["rule_id"] for v in bad_scalp["violations"]}
    assert "SOP-05" in ids2 and "SOP-07" in ids2

    bad_trendline = audit_trade_plan("Entry buy langsung di pantulan ke-3 trendline di dalam kumo cloud", index=idx)
    assert bad_trendline["verdict"] == "REJECT"
    ids3 = {v["rule_id"] for v in bad_trendline["violations"]}
    assert "SOP-03" in ids3 and "SOP-04" in ids3


def test_auditor_passes_compliant_plan():
    idx = CorpusBM25Index(ROOT / "corpus")
    good = audit_trade_plan(
        "Entry Buy Limit EURUSD di Fresh Demand zona Discount (<0.5 PD Range) setelah EQH/EQL swept dan BOS Body Close, "
        "pakai System SL di broker, risk 1% akun terpisah, R:R 1:4.",
        index=idx,
    )
    assert good["verdict"] == "PASS"
    assert good["violation_count"] == 0
    assert len(good["supporting_evidence"]) >= 1


def test_portal_generation_works(tmp_path):
    out = build_portal(ROOT / "corpus", out_html=tmp_path / "portal.html")
    assert out.exists()
    content = out.read_text(encoding="utf-8")
    assert "Arist MD (Mancing Dollar) Playbook" in content
    assert "https://www.youtube.com/watch?v=" in content

    rc = cli_main(["--corpus", str(ROOT / "corpus"), "build-portal", "--out", str(tmp_path / "p2.html")])
    assert rc == 0
