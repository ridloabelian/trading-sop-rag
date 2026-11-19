"""Static Searchable Playbook & Mentor-Attributed Evidence Portal Generator."""

from __future__ import annotations

import html
import json
from pathlib import Path
import re

from sop_rag.indexer import DEFAULT_CORPUS_DIR, make_youtube_deep_link


def parse_evidence_rows(corpus_dir: Path) -> list[dict]:
    em_path = corpus_dir / "EVIDENCE_MATRIX.md"
    if not em_path.exists():
        return []
    rows = []
    cur_section = "General"
    for line in em_path.read_text(encoding="utf-8").splitlines():
        if line.startswith("## "):
            cur_section = line[3:].strip()
            continue
        if line.startswith("|") and not line.startswith("| ID") and not line.startswith("|---"):
            parts = [p.strip() for p in line.strip("|").split("|")]
            if len(parts) >= 5:
                vids = re.findall(r"`([A-Za-z0-9_-]{11})`", parts[4])
                links = [{"video_id": v, "url": make_youtube_deep_link(v)} for v in vids]
                rows.append(
                    {
                        "section": cur_section,
                        "id": parts[0],
                        "topic": parts[1].replace("**", ""),
                        "rule": parts[2].replace("**", ""),
                        "speaker": parts[3],
                        "sources": parts[4],
                        "links": links,
                    }
                )
    return rows


def build_portal(corpus_dir: str | Path | None = None, out_html: str | Path = "docs/index.html") -> Path:
    c_dir = Path(corpus_dir) if corpus_dir else DEFAULT_CORPUS_DIR
    rows = parse_evidence_rows(c_dir)
    out = Path(out_html)
    out.parent.mkdir(parents=True, exist_ok=True)

    pb_path = c_dir / "ARIST_MD_TRADING_PLAYBOOK.md"
    pb_lines = pb_path.read_text(encoding="utf-8").splitlines()[:80] if pb_path.exists() else []
    pb_preview = html.escape("\n".join(pb_lines))

    rows_json = json.dumps(rows, ensure_ascii=False)
    doc = f"""<!DOCTYPE html>
<html lang="id">
<head>
<meta charset="UTF-8" />
<meta name="viewport" content="width=device-width, initial-scale=1.0" />
<title>Arist MD Trading SOP &amp; Evidence Portal (199 Videos)</title>
<style>
  body {{ margin:0; font-family:ui-sans-serif,system-ui,sans-serif; background:#0b1120; color:#e5e7eb; }}
  header {{ padding:20px 28px; background:#0f172a; border-bottom:1px solid #1f2937; }}
  main {{ padding:24px 28px; max-width:1280px; margin:0 auto; }}
  .controls {{ display:flex; flex-wrap:wrap; gap:10px; align-items:center; margin-bottom:16px; }}
  input {{ background:#111827; color:#e5e7eb; border:1px solid #334155; border-radius:8px; padding:9px 14px; min-width:300px; }}
  .pill {{ border:1px solid #334155; background:#111827; color:#cbd5e1; border-radius:999px; padding:6px 12px; cursor:pointer; font-size:0.82rem; }}
  .pill.active {{ background:#10b981; color:#052e16; border-color:#10b981; font-weight:700; }}
  table {{ width:100%; border-collapse:collapse; background:#111827; border-radius:8px; overflow:hidden; }}
  th, td {{ padding:10px 12px; border-bottom:1px solid #1f2937; text-align:left; font-size:0.86rem; vertical-align:top; }}
  th {{ background:#0f172a; color:#6ee7b7; }}
  a {{ color:#60a5fa; text-decoration:none; }}
  a:hover {{ text-decoration:underline; }}
  pre {{ background:#111827; padding:14px; border-radius:8px; border:1px solid #1f2937; overflow:auto; max-height:260px; font-size:0.82rem; }}
</style>
</head>
<body>
<header>
  <h1 style="margin:0;font-size:1.35rem;">Arist MD (Mancing Dollar) Playbook &amp; 199-Video Evidence Portal</h1>
  <p style="margin:6px 0 0;color:#9ca3af;font-size:0.86rem;">Filter berdasarkan lapisan atribusi mentor (`Arist MD Core` vs `Ragnaray` vs `Franz` vs `Danial/Guest`) dan telusuri sitasi timestamp YouTube.</p>
</header>
<main>
  <div class="controls">
    <input id="q" type="search" placeholder="Cari aturan, indikator, Stingray, EQL, MC, US10Y..." />
    <button class="pill active" data-filter="">All Mentors</button>
    <button class="pill" data-filter="Arist MD">Arist MD Core</button>
    <button class="pill" data-filter="Ragnaray">Co-Mentor: Ragnaray</button>
    <button class="pill" data-filter="Franz">Co-Mentor: Franz</button>
    <button class="pill" data-filter="Danial">Danial &amp; Guests</button>
  </div>
  <div id="count" style="margin-bottom:8px;color:#9ca3af;font-size:0.84rem;"></div>
  <table>
    <thead><tr><th>ID</th><th>Domain / Aturan</th><th>Nilai / Kondisi Eksak</th><th>Atribusi</th><th>Video YouTube</th></tr></thead>
    <tbody id="tbody"></tbody>
  </table>
  <h2 style="margin-top:28px;">Ringkasan Playbook Utama</h2>
  <pre>{pb_preview}</pre>
</main>
<script>
const ROWS = {rows_json};
let mentorFilter = "";
const tbody = document.getElementById("tbody");
const qEl = document.getElementById("q");
const countEl = document.getElementById("count");

function render() {{
  const q = qEl.value.trim().toLowerCase();
  const filtered = ROWS.filter(r => {{
    const textMatch = !q || (r.id + " " + r.topic + " " + r.rule + " " + r.speaker + " " + r.section).toLowerCase().includes(q);
    const spkMatch = !mentorFilter || (mentorFilter === "Danial" ? /Danial|Mustofa|Arlind|Guest/i.test(r.speaker) : r.speaker.toLowerCase().includes(mentorFilter.toLowerCase()));
    return textMatch && spkMatch;
  }});
  countEl.textContent = `Menampilkan ${{filtered.length}} dari ${{ROWS.length}} baris bukti lintas 199 video.`;
  tbody.innerHTML = filtered.map(r => {{
    const linkHtml = r.links.map(l => `<a target="_blank" rel="noopener" href="${{l.url}}">${{l.video_id}}</a>`).join(" • ");
    return `<tr><td><strong>${{r.id}}</strong><br/><small style="color:#9ca3af">${{r.section}}</small></td><td>${{r.topic}}</td><td>${{r.rule}}</td><td>${{r.speaker}}</td><td>${{linkHtml || r.sources}}</td></tr>`;
  }}).join("");
}}
qEl.addEventListener("input", render);
document.querySelectorAll(".pill").forEach(btn => {{
  btn.addEventListener("click", () => {{
    document.querySelectorAll(".pill").forEach(b => b.classList.remove("active"));
    btn.classList.add("active");
    mentorFilter = btn.dataset.filter;
    render();
  }});
}});
render();
</script>
</body>
</html>
"""
    out.write_text(doc, encoding="utf-8")
    return out
