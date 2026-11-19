# Trading SOP RAG & Searchable 199-Video Playbook Portal

Offline-first **Okapi BM25 evidence retriever**, **18-rule Pre-Trade SOP Auditor**, and static **Searchable Playbook Portal** grounded across **199 multimodal YouTube extractions** (`@Mancing_Dollar`, external collabs, and Shorts).

---

## Components

1. **Sanitized 199-Video Research Corpus (`corpus/`):**
   - [`ARIST_MD_TRADING_PLAYBOOK.md`](./corpus/ARIST_MD_TRADING_PLAYBOOK.md)
   - [`EVIDENCE_MATRIX.md`](./corpus/EVIDENCE_MATRIX.md)
   - [`VIDEO_INVENTORY_AND_INDEX.md`](./corpus/VIDEO_INVENTORY_AND_INDEX.md)
   - `notes/{tier_a_channel,tier_b_collabs,tier_c_shorts}/*.md` (199 timestamped extractions)
   - `speaker_classification.json` & sanitized `catalog.json`
2. **18-Rule Deterministic SOP Auditor (`src/sop_rag/auditor.py`):**
   - Catches high-cost errors (buying above `EQL` without sweep, mid-`FVG` entries before 70–80% fill, direct trendline bounces, trading inside `Kumo Cloud`, converting losing scalps into swings, missing `System SL`, correlated pairs in one account, `>10%` open risk, hot-money capital, Franz `M15/M5/M1` misalignment, `RSI ~50`, mid-range `TC`, `PD Range` inversion, mitigated zones, post-MC revenge) and cites exact `[VideoID @ MM:SS]` YouTube deep links.
3. **Mentor-Filtered Evidence Portal (`docs/index.html`):**
   - Filter rules cleanly across **Arist MD Core**, **Co-Mentor: Ragnaray**, **Co-Mentor: Franz**, and **Danial & Guests**.

---

## Quickstart

```bash
pip install -e ".[dev]"

# Search all 199 videos & Playbook with optional mentor filter
sop-rag search "Stingray 1.272 Point B" --speaker Ragnaray --top-k 5

# Audit a trade plan deterministically (no API key needed)
sop-rag audit "Mau Buy XAUUSD di atas EQL tanpa sweep dan tanpa SL"

# Optional Gemini-powered commentary over retrieved passages (requires GEMINI_API_KEY)
# sop-rag audit "Rencana entry XAUUSD..." --gemini

# Build standalone HTML Evidence Portal (GitHub Pages ready)
sop-rag build-portal --out docs/index.html

# Run tests
pytest tests -v
```
