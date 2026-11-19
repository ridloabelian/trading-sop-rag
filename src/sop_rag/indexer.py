"""Pure-Python Okapi BM25 indexer across Playbook, Evidence Matrix & all 199 video notes."""

from __future__ import annotations

from dataclasses import dataclass, asdict
import json
import math
from pathlib import Path
import re

DEFAULT_CORPUS_DIR = Path(__file__).resolve().parents[2] / "corpus"

TOKEN_RE = re.compile(r"[a-z0-9_]+")
TS_RE = re.compile(r"\[(?:(\d{1,2}):)?(\d{1,2}):(\d{2})\]")


def tokenize(text: str) -> list[str]:
    return TOKEN_RE.findall(text.lower())


def parse_timestamp_seconds(ts_match: tuple[str, str, str]) -> int:
    hh, mm, ss = ts_match
    return int(hh or 0) * 3600 + int(mm) * 60 + int(ss)


def make_youtube_deep_link(video_id: str, seconds: int | None = None) -> str:
    if video_id.startswith("PLAYBOOK") or video_id.startswith("MATRIX"):
        return ""
    if seconds and seconds > 0:
        return f"https://www.youtube.com/watch?v={video_id}&t={seconds}s"
    return f"https://www.youtube.com/watch?v={video_id}"


@dataclass(frozen=True)
class IndexedChunk:
    doc_id: str
    source_type: str  # video_note | playbook | evidence_matrix
    video_id: str
    tier: str
    title: str
    speaker_layer: str
    timestamps: list[str]
    youtube_url: str
    text: str

    def to_dict(self) -> dict:
        return asdict(self)


class CorpusBM25Index:
    """In-memory Okapi BM25 search index built deterministically from corpus/."""

    def __init__(self, corpus_dir: str | Path | None = None, k1: float = 1.5, b: float = 0.75) -> None:
        self.corpus_dir = Path(corpus_dir) if corpus_dir else DEFAULT_CORPUS_DIR
        self.k1 = k1
        self.b = b
        self.chunks: list[IndexedChunk] = []
        self.doc_tokens: list[list[str]] = []
        self.df: dict[str, int] = {}
        self.idf: dict[str, float] = {}
        self.avg_dl: float = 1.0
        self.note_video_ids: set[str] = set()
        self._build()

    def _load_speaker_map(self) -> dict[str, dict]:
        sp_path = self.corpus_dir / "speaker_classification.json"
        if not sp_path.exists():
            return {}
        data = json.loads(sp_path.read_text(encoding="utf-8"))
        out = {}
        if isinstance(data, list):
            for row in data:
                vid = row.get("video_id")
                if vid:
                    out[vid] = row
        return out

    def _build(self) -> None:
        sp_map = self._load_speaker_map()
        cat_titles: dict[str, str] = {}
        cat_path = self.corpus_dir / "catalog.json"
        if cat_path.exists():
            cat_data = json.loads(cat_path.read_text(encoding="utf-8"))
            for tier_val in cat_data.values():
                if isinstance(tier_val, list):
                    for item in tier_val:
                        if isinstance(item, dict) and item.get("video_id"):
                            cat_titles[item["video_id"]] = item.get("title", item["video_id"])

        # 1. Index all 199 video notes chunked by ## Section
        notes_root = self.corpus_dir / "notes"
        if notes_root.exists():
            for md_path in sorted(notes_root.rglob("*.md")):
                vid = md_path.stem
                tier = md_path.parent.name
                self.note_video_ids.add(vid)
                raw = md_path.read_text(encoding="utf-8")
                meta = sp_map.get(vid, {})
                speaker_layer = meta.get("speaker_class", "Arist MD / Extracted Note")
                title = meta.get("title") or cat_titles.get(vid, vid)

                sections = re.split(r"(?=^##\s+)", raw, flags=re.M)
                for s_idx, sec in enumerate(sections):
                    sec_clean = sec.strip()
                    if len(sec_clean) < 25:
                        continue
                    ts_matches = TS_RE.findall(sec_clean)
                    ts_labels = [
                        f"{(m[0] + ':') if m[0] else ''}{int(m[1]):02d}:{m[2]}" for m in ts_matches[:8]
                    ]
                    first_sec = parse_timestamp_seconds(ts_matches[0]) if ts_matches else None
                    self.chunks.append(
                        IndexedChunk(
                            doc_id=f"{vid}#s{s_idx}",
                            source_type="video_note",
                            video_id=vid,
                            tier=tier,
                            title=title,
                            speaker_layer=speaker_layer,
                            timestamps=ts_labels,
                            youtube_url=make_youtube_deep_link(vid, first_sec),
                            text=sec_clean,
                        )
                    )

        # 2. Index Playbook sections
        pb_path = self.corpus_dir / "ARIST_MD_TRADING_PLAYBOOK.md"
        if pb_path.exists():
            pb_raw = pb_path.read_text(encoding="utf-8")
            for idx, sec in enumerate(re.split(r"(?=^##\s+)", pb_raw, flags=re.M)):
                sec_clean = sec.strip()
                if len(sec_clean) < 30:
                    continue
                head = sec_clean.splitlines()[0].lstrip("# ").strip()
                self.chunks.append(
                    IndexedChunk(
                        doc_id=f"PLAYBOOK#{idx}",
                        source_type="playbook",
                        video_id="PLAYBOOK",
                        tier="synthesis",
                        title=head,
                        speaker_layer="Consolidated Playbook",
                        timestamps=[],
                        youtube_url="",
                        text=sec_clean,
                    )
                )

        # 3. Index Evidence Matrix rows
        em_path = self.corpus_dir / "EVIDENCE_MATRIX.md"
        if em_path.exists():
            for idx, line in enumerate(em_path.read_text(encoding="utf-8").splitlines(), 1):
                if line.startswith("|") and not line.startswith("| ID") and not line.startswith("|---"):
                    self.chunks.append(
                        IndexedChunk(
                            doc_id=f"MATRIX#L{idx}",
                            source_type="evidence_matrix",
                            video_id="MATRIX",
                            tier="synthesis",
                            title=f"Evidence Row L{idx}",
                            speaker_layer="Evidence Matrix",
                            timestamps=[],
                            youtube_url="",
                            text=line,
                        )
                    )

        # Compute BM25 stats
        n_docs = len(self.chunks)
        for chunk in self.chunks:
            toks = tokenize(f"{chunk.title} {chunk.speaker_layer} {chunk.text}")
            self.doc_tokens.append(toks)
            for term in set(toks):
                self.df[term] = self.df.get(term, 0) + 1

        self.avg_dl = sum(len(t) for t in self.doc_tokens) / max(1, n_docs)
        for term, freq in self.df.items():
            self.idf[term] = math.log(1.0 + (n_docs - freq + 0.5) / (freq + 0.5))

    def search(
        self,
        query: str,
        top_k: int = 5,
        speaker_filter: str | None = None,
        source_type: str | None = None,
    ) -> list[dict]:
        q_terms = tokenize(query)
        if not q_terms or not self.chunks:
            return []

        scored: list[tuple[float, IndexedChunk]] = []
        for chunk, toks in zip(self.chunks, self.doc_tokens):
            if speaker_filter and speaker_filter.lower() not in chunk.speaker_layer.lower():
                continue
            if source_type and chunk.source_type != source_type:
                continue
            dl = len(toks)
            if dl == 0:
                continue
            tf_map: dict[str, int] = {}
            for t in toks:
                if t in q_terms:
                    tf_map[t] = tf_map.get(t, 0) + 1
            if not tf_map:
                continue

            score = 0.0
            for t in q_terms:
                if t not in tf_map:
                    continue
                tf = tf_map[t]
                idf = self.idf.get(t, 0.0)
                num = tf * (self.k1 + 1.0)
                den = tf + self.k1 * (1.0 - self.b + self.b * (dl / self.avg_dl))
                score += idf * (num / den)
            if score > 0:
                scored.append((score, chunk))

        scored.sort(key=lambda x: x[0], reverse=True)
        out = []
        for score, ch in scored[:top_k]:
            excerpt = " ".join(ch.text.splitlines()[:6])[:380]
            out.append(
                {
                    "score": round(score, 3),
                    "doc_id": ch.doc_id,
                    "source_type": ch.source_type,
                    "video_id": ch.video_id,
                    "title": ch.title,
                    "speaker_layer": ch.speaker_layer,
                    "timestamps": ch.timestamps,
                    "youtube_url": ch.youtube_url,
                    "excerpt": excerpt,
                }
            )
        return out
