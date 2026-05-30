#!/usr/bin/env python3
"""Local-first ContextOS engine for indexing, search, journals, and dashboard rendering."""

from __future__ import annotations

import argparse
import datetime as dt
import html
import json
import os
import re
import shutil
import subprocess
import sys
from dataclasses import dataclass
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from typing import Any, Iterable


ROOT = Path(__file__).resolve().parents[1]
DATA_DIR = Path(os.environ.get("AGENTIC_AUTOBIOGRAPHY_DATA_DIR", ROOT / "data"))
JOURNAL_DIR = DATA_DIR / "journals"
INDEX_PATH = DATA_DIR / "index.json"
DASHBOARD_PATH = Path(os.environ.get("AGENTIC_AUTOBIOGRAPHY_DASHBOARD_PATH", ROOT / "dashboard" / "index.html"))
ACTIVITY_CONFIG_PATH = ROOT / "config" / "activity_roots.json"
DEFAULT_DOCS = [ROOT / "docs", ROOT / "samples"]
TEXT_EXTENSIONS = {".md", ".markdown", ".txt", ".json", ".csv", ".log"}
PDF_EXTENSIONS = {".pdf"}
DEFAULT_EXCLUDES = {
    ".git",
    ".venv",
    "__pycache__",
    "node_modules",
    "Library",
    ".Trash",
    "Applications",
}
ACTION_RE = re.compile(r"\b(action|todo|next|follow[- ]?up|해야|준비|작성|수정|추가)\b", re.I)
DECISION_RE = re.compile(r"\b(decision|decided|결정|확정|reframed|shifted|focus)\b", re.I)
WORD_RE = re.compile(r"[A-Za-z0-9가-힣_]{2,}")


@dataclass(frozen=True)
class Chunk:
    id: str
    source: str
    title: str
    modified_at: str
    excerpt: str
    keywords: list[str]

    def as_dict(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "source": self.source,
            "title": self.title,
            "modified_at": self.modified_at,
            "excerpt": self.excerpt,
            "keywords": self.keywords,
        }


def now_utc() -> dt.datetime:
    return dt.datetime.now(dt.timezone.utc)


def iso_from_timestamp(value: float) -> str:
    return dt.datetime.fromtimestamp(value, dt.timezone.utc).isoformat()


def ensure_dirs() -> None:
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    JOURNAL_DIR.mkdir(parents=True, exist_ok=True)
    DASHBOARD_PATH.parent.mkdir(parents=True, exist_ok=True)


def read_text(path: Path) -> str:
    if path.suffix.lower() in TEXT_EXTENSIONS:
        try:
            return path.read_text(encoding="utf-8")
        except UnicodeDecodeError:
            return path.read_text(encoding="utf-8", errors="replace")
    if path.suffix.lower() in PDF_EXTENSIONS:
        return read_pdf_text(path)
    return ""


def read_pdf_text(path: Path) -> str:
    pdftotext = shutil.which("pdftotext")
    if pdftotext:
        result = subprocess.run(
            [pdftotext, str(path), "-"],
            check=False,
            capture_output=True,
            text=True,
            timeout=20,
        )
        if result.returncode == 0:
            return result.stdout
    try:
        import pypdf  # type: ignore

        reader = pypdf.PdfReader(str(path))
        return "\n".join(page.extract_text() or "" for page in reader.pages)
    except Exception:
        return ""


def iter_files(roots: Iterable[Path]) -> Iterable[Path]:
    for root in roots:
        root = root.expanduser().resolve()
        if root.is_file():
            yield root
            continue
        if not root.exists():
            continue
        for path in root.rglob("*"):
            if path.is_file() and path.suffix.lower() in TEXT_EXTENSIONS | PDF_EXTENSIONS:
                if any(part.startswith(".") for part in path.relative_to(root).parts):
                    continue
                yield path


def default_activity_config() -> dict[str, Any]:
    home = Path.home()
    return {
        "roots": [
            str(home / "Desktop"),
            str(home / "Documents"),
            str(home / "Downloads"),
            str(home / ".codex" / "sessions"),
        ],
        "exclude_names": sorted(DEFAULT_EXCLUDES),
        "max_files": 150,
    }


def load_activity_config() -> dict[str, Any]:
    if not ACTIVITY_CONFIG_PATH.exists():
        return default_activity_config()
    try:
        payload = json.loads(ACTIVITY_CONFIG_PATH.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        return default_activity_config()
    default = default_activity_config()
    return {
        "roots": payload.get("roots") or default["roots"],
        "exclude_names": payload.get("exclude_names") or default["exclude_names"],
        "max_files": int(payload.get("max_files") or default["max_files"]),
    }


def iter_recent_paths(
    roots: Iterable[Path],
    hours: int,
    *,
    exclude_names: set[str] | None = None,
    max_files: int = 150,
) -> list[Path]:
    cutoff = now_utc() - dt.timedelta(hours=hours)
    exclude_names = exclude_names or DEFAULT_EXCLUDES
    matches: list[tuple[float, Path]] = []
    for raw_root in roots:
        root = raw_root.expanduser().resolve()
        if not root.exists():
            continue
        if root.is_file():
            try:
                if dt.datetime.fromtimestamp(root.stat().st_mtime, dt.timezone.utc) >= cutoff:
                    matches.append((root.stat().st_mtime, root))
            except OSError:
                continue
            continue
        for current, dirs, files in os.walk(root):
            dirs[:] = [name for name in dirs if name not in exclude_names and not name.startswith(".")]
            current_path = Path(current)
            for name in files:
                if name.startswith("."):
                    continue
                path = current_path / name
                try:
                    stat = path.stat()
                except OSError:
                    continue
                modified = dt.datetime.fromtimestamp(stat.st_mtime, dt.timezone.utc)
                if modified >= cutoff:
                    matches.append((stat.st_mtime, path))
    matches.sort(key=lambda item: item[0], reverse=True)
    return [path for _, path in matches[:max_files]]


def recent_activity_chunks(paths: Iterable[Path]) -> list[dict[str, Any]]:
    chunks: list[dict[str, Any]] = []
    for path in paths:
        if is_generated_artifact(path):
            continue
        if path.suffix.lower() not in TEXT_EXTENSIONS:
            continue
        try:
            if path.stat().st_size > 1_000_000:
                continue
            text = read_text(path)
        except OSError:
            continue
        for chunk in chunk_text(path, text, chunk_size=900)[:2]:
            chunks.append(chunk.as_dict())
    return chunks


def is_generated_artifact(path: Path) -> bool:
    try:
        resolved = path.resolve()
        relative = resolved.relative_to(ROOT)
    except (OSError, ValueError):
        return False
    parts = relative.parts
    return (
        parts[:1] == ("dashboard",)
        or parts[:1] == ("data",)
        or parts[:1] == (".git",)
    )


def title_for(path: Path, text: str) -> str:
    if path.suffix.lower() in {".json", ".csv", ".log"}:
        return path.name
    for line in text.splitlines():
        stripped = line.strip()
        if stripped.startswith("#"):
            return stripped.lstrip("#").strip() or path.stem
        if stripped:
            return stripped[:80]
    return path.stem


def normalize_space(text: str) -> str:
    return re.sub(r"\s+", " ", text).strip()


def keywords_for(text: str, limit: int = 20) -> list[str]:
    counts: dict[str, int] = {}
    for word in WORD_RE.findall(text.lower()):
        if len(word) < 2:
            continue
        counts[word] = counts.get(word, 0) + 1
    return [word for word, _ in sorted(counts.items(), key=lambda item: (-item[1], item[0]))[:limit]]


def chunk_text(path: Path, text: str, chunk_size: int = 1200) -> list[Chunk]:
    clean = normalize_space(text)
    if not clean:
        return []
    chunks: list[Chunk] = []
    modified_at = iso_from_timestamp(path.stat().st_mtime)
    title = title_for(path, text)
    for index, start in enumerate(range(0, len(clean), chunk_size)):
        excerpt = clean[start : start + chunk_size]
        chunks.append(
            Chunk(
                id=f"{path.resolve()}#{index}",
                source=str(path.resolve()),
                title=title,
                modified_at=modified_at,
                excerpt=excerpt,
                keywords=keywords_for(excerpt),
            )
        )
    return chunks


def build_index(docs: Iterable[Path]) -> dict[str, Any]:
    ensure_dirs()
    chunks: list[dict[str, Any]] = []
    files_seen = 0
    for path in sorted(set(iter_files(docs))):
        text = read_text(path)
        file_chunks = chunk_text(path, text)
        if file_chunks:
            files_seen += 1
            chunks.extend(chunk.as_dict() for chunk in file_chunks)
    payload = {
        "generated_at": now_utc().isoformat(),
        "root": str(ROOT),
        "files_indexed": files_seen,
        "chunks": chunks,
    }
    INDEX_PATH.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return payload


def load_index() -> dict[str, Any]:
    if not INDEX_PATH.exists():
        return build_index(DEFAULT_DOCS)
    return json.loads(INDEX_PATH.read_text(encoding="utf-8"))


def query_terms(query: str) -> set[str]:
    return set(keywords_for(query, limit=40))


def score_chunk(chunk: dict[str, Any], query: str) -> float:
    terms = query_terms(query)
    if not terms:
        return 0.0
    keywords = set(chunk.get("keywords", []))
    excerpt = chunk.get("excerpt", "").lower()
    title = chunk.get("title", "").lower()
    score = len(terms & keywords) * 3
    for term in terms:
        if term in title:
            score += 4
        if term in excerpt:
            score += 1
    return float(score)


def search(query: str, limit: int = 5) -> list[dict[str, Any]]:
    index = load_index()
    ranked = []
    for chunk in index.get("chunks", []):
        score = score_chunk(chunk, query)
        if score > 0:
            ranked.append({**chunk, "score": score})
    ranked.sort(key=lambda item: (-item["score"], item["modified_at"], item["source"]))
    return ranked[:limit]


def sentence_matches(pattern: re.Pattern[str], text: str) -> list[str]:
    sentences = re.split(r"(?<=[.!?。])\s+|\n+", text)
    return [normalize_space(sentence) for sentence in sentences if pattern.search(sentence)]


def extract_actions(chunks: Iterable[dict[str, Any]], limit: int = 10) -> list[dict[str, str]]:
    actions: list[dict[str, str]] = []
    seen: set[str] = set()
    for chunk in chunks:
        for sentence in action_candidates(chunk.get("excerpt", "")):
            key = sentence.lower()
            if key in seen:
                continue
            seen.add(key)
            actions.append({"task": sentence, "source": chunk.get("source", "")})
            if len(actions) >= limit:
                return actions
    return actions


def action_candidates(text: str) -> list[str]:
    matches: list[str] = []
    for sentence in sentence_matches(ACTION_RE, text):
        lowered = sentence.lower()
        if "memory.actions" in lowered:
            continue
        if "what should happen next" in lowered:
            continue
        if ":" in sentence:
            _, tail = sentence.split(":", 1)
            bullet_items = [item.strip(" -") for item in re.split(r"\s+-\s+", tail) if item.strip(" -")]
            if bullet_items:
                matches.extend(bullet_items)
                continue
        matches.append(sentence)
    return matches


def extract_decisions(chunks: Iterable[dict[str, Any]], limit: int = 10) -> list[dict[str, str]]:
    decisions: list[dict[str, str]] = []
    seen: set[str] = set()
    for chunk in chunks:
        for sentence in sentence_matches(DECISION_RE, chunk.get("excerpt", "")):
            key = sentence.lower()
            if key in seen:
                continue
            seen.add(key)
            decisions.append({"decision": sentence, "source": chunk.get("source", "")})
            if len(decisions) >= limit:
                return decisions
    return decisions


def journal_chunk_order(chunk: dict[str, Any]) -> tuple[int, str]:
    source = chunk.get("source", "")
    if "/samples/" in source:
        return (0, source)
    if "/docs/" in source:
        return (2, source)
    return (1, source)


def journal_summary(chunks: list[dict[str, Any]], decisions: list[dict[str, str]], actions: list[dict[str, str]]) -> str:
    titles = []
    seen = set()
    for chunk in chunks:
        title = chunk.get("title", "")
        if title and title not in seen:
            seen.add(title)
            titles.append(title)
    parts = []
    if titles:
        parts.append(f"Reviewed {len(titles)} source files: {', '.join(titles[:5])}.")
    if decisions:
        parts.append(f"Most concrete decision: {decisions[0]['decision']}")
    if actions:
        parts.append(f"Next visible action: {actions[0]['task']}")
    if not parts and chunks:
        parts.append(normalize_space(" ".join(chunk["excerpt"] for chunk in chunks[:2]))[:700])
    return " ".join(parts) or "No source text was available for this window."


def timeline(entity: str, limit: int = 10) -> list[dict[str, str]]:
    results = search(entity, limit=limit)
    events = []
    for result in results:
        events.append(
            {
                "date": result.get("modified_at", ""),
                "event": result.get("title", ""),
                "source": result.get("source", ""),
            }
        )
    return events


def summarize(query: str, limit: int = 7) -> dict[str, Any]:
    results = search(query, limit=limit)
    if not results:
        return {
            "context": "No indexed sources matched the query.",
            "decisions": [],
            "timeline": [],
            "next_actions": [],
            "sources": [],
        }
    sources = sorted({item["source"] for item in results})
    leading = " ".join(item["excerpt"] for item in results[:3])
    context = normalize_space(leading[:900])
    return {
        "context": context,
        "decisions": extract_decisions(results),
        "timeline": timeline(query, limit=limit),
        "next_actions": extract_actions(results),
        "sources": sources,
    }


def recent_file_activity(
    roots: Iterable[Path],
    hours: int,
    *,
    exclude_names: set[str] | None = None,
    max_files: int = 150,
) -> list[dict[str, str]]:
    items: list[dict[str, str]] = []
    for path in iter_recent_paths(roots, hours, exclude_names=exclude_names, max_files=max_files):
        if is_generated_artifact(path):
            continue
        modified = dt.datetime.fromtimestamp(path.stat().st_mtime, dt.timezone.utc)
        items.append(
            {
                "path": str(path.resolve()),
                "modified_at": modified.isoformat(),
                "title": path.name,
            }
        )
    items.sort(key=lambda item: item["modified_at"], reverse=True)
    return items


def generate_journal(
    hours: int = 24,
    docs: Iterable[Path] | None = None,
    activity_roots: Iterable[Path] | None = None,
) -> dict[str, Any]:
    ensure_dirs()
    docs = list(docs or DEFAULT_DOCS)
    activity_config = load_activity_config()
    if activity_roots is None:
        activity_roots = [Path(value) for value in activity_config["roots"]]
    activity_roots = list(activity_roots)
    exclude_names = set(activity_config.get("exclude_names", [])) or DEFAULT_EXCLUDES
    max_files = int(activity_config.get("max_files", 150))
    index = build_index(docs)
    recent = recent_file_activity(activity_roots, hours, exclude_names=exclude_names, max_files=max_files)
    chunks = index.get("chunks", [])
    activity_chunks = recent_activity_chunks(Path(item["path"]) for item in recent)
    cutoff = now_utc() - dt.timedelta(hours=hours)
    recent_chunks = [
        chunk
        for chunk in [*activity_chunks, *chunks]
        if dt.datetime.fromisoformat(chunk["modified_at"]) >= cutoff
    ]
    if not recent_chunks:
        recent_chunks = chunks[:8]
    recent_chunks.sort(key=journal_chunk_order)

    decisions = extract_decisions(recent_chunks, limit=8)
    actions = extract_actions(recent_chunks, limit=12)
    sources = sorted({chunk["source"] for chunk in recent_chunks[:12]} | {item["path"] for item in recent[:12]})
    timeline_rows = [
        {
            "date": item["modified_at"],
            "event": item["title"],
            "source": item["path"],
        }
        for item in recent[:20]
    ]
    if not timeline_rows:
        timeline_rows = [
            {
                "date": chunk.get("modified_at", ""),
                "event": chunk.get("title", ""),
                "source": chunk.get("source", ""),
            }
            for chunk in recent_chunks[:10]
        ]

    summary = journal_summary(recent_chunks, decisions, actions)

    generated_at = now_utc()
    payload = {
        "date": generated_at.astimezone().date().isoformat(),
        "generated_at": generated_at.isoformat(),
        "hours": hours,
        "summary": summary,
        "timeline": timeline_rows,
        "decisions": decisions,
        "actions": actions,
        "sources": sources,
        "source_count": len(sources),
        "activity_roots": [str(path.expanduser()) for path in activity_roots],
        "recent_file_count": len(recent),
    }
    out_path = JOURNAL_DIR / f"{payload['date']}.json"
    out_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    render_dashboard()
    return payload


def load_journals() -> list[dict[str, Any]]:
    ensure_dirs()
    journals = []
    for path in sorted(JOURNAL_DIR.glob("*.json"), reverse=True):
        try:
            payload = json.loads(path.read_text(encoding="utf-8"))
            payload["_path"] = str(path.resolve())
            journals.append(payload)
        except json.JSONDecodeError:
            continue
    return journals


LABELS = {
    "en": {
        "html_lang": "en",
        "brand": "Agentic Autobiography",
        "nav_journal": "Journal",
        "nav_timeline": "Timeline",
        "nav_sources": "Sources",
        "indexed_chunks": "Indexed chunks",
        "journals": "Journals",
        "hero_title": "Recover the context your AI forgot.",
        "empty_summary": "No journal has been generated yet.",
        "command_journal": "journal",
        "generated": "generated",
        "sources": "sources",
        "recent_files": "recent files",
        "dashboard": "dashboard",
        "daily_journals": "Daily Journals",
        "recent_sources": "Recent Sources",
        "empty_journals": "No journals yet. Run the journal command.",
        "untitled": "Untitled",
        "hour_window": "h window",
        "timeline": "Timeline",
        "decisions": "Decisions",
        "action_items": "Action Items",
        "no_decisions": "No explicit decisions found.",
        "no_actions": "No action items found.",
        "no_sources": "No sources yet.",
    },
    "ko": {
        "html_lang": "ko",
        "brand": "Agentic Autobiography",
        "nav_journal": "저널",
        "nav_timeline": "타임라인",
        "nav_sources": "출처",
        "indexed_chunks": "인덱싱된 조각",
        "journals": "저널",
        "hero_title": "AI가 놓친 맥락을 다시 복구합니다.",
        "empty_summary": "아직 생성된 저널이 없습니다.",
        "command_journal": "저널 생성",
        "generated": "생성 시각",
        "sources": "출처",
        "recent_files": "최근 파일",
        "dashboard": "대시보드",
        "daily_journals": "오늘의 저널",
        "recent_sources": "최근 출처",
        "empty_journals": "아직 저널이 없습니다. journal 명령을 실행하세요.",
        "untitled": "제목 없음",
        "hour_window": "시간 범위",
        "timeline": "타임라인",
        "decisions": "결정 사항",
        "action_items": "할 일",
        "no_decisions": "명시적인 결정 사항이 없습니다.",
        "no_actions": "할 일이 없습니다.",
        "no_sources": "아직 출처가 없습니다.",
    },
}


def dashboard_labels(lang: str) -> dict[str, str]:
    return LABELS.get(lang, LABELS["en"])


def render_dashboard(lang: str = "en") -> Path:
    ensure_dirs()
    labels = dashboard_labels(lang)
    journals = load_journals()
    index = load_index()
    latest = journals[0] if journals else None
    latest_summary = latest.get("summary", labels["empty_summary"]) if latest else labels["empty_summary"]
    source_count = latest.get("source_count", 0) if latest else 0
    recent_file_count = latest.get("recent_file_count", 0) if latest else 0
    journal_cards = "\n".join(render_journal_card(journal, labels) for journal in journals) or f"<p class='muted'>{labels['empty_journals']}</p>"
    html_payload = f"""<!doctype html>
<html lang="{labels['html_lang']}">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>Agentic Autobiography</title>
  <style>{dashboard_css()}</style>
</head>
<body>
  <aside class="sidebar">
    <div class="brand">{labels['brand']}</div>
    <nav>
      <a href="#journal">{labels['nav_journal']}</a>
      <a href="#timeline">{labels['nav_timeline']}</a>
      <a href="#sources">{labels['nav_sources']}</a>
    </nav>
    <div class="stat"><strong>{len(index.get("chunks", []))}</strong><span>{labels['indexed_chunks']}</span></div>
    <div class="stat"><strong>{len(journals)}</strong><span>{labels['journals']}</span></div>
  </aside>
  <main>
    <section class="hero">
      <div>
        <h1>{labels['hero_title']}</h1>
        <p>{html.escape(latest_summary)}</p>
      </div>
      <div class="terminal">
        <div class="dots"><i></i><i></i><i></i></div>
        <pre>$ python3 scripts/agentic_autobiography.py journal --hours 24
{labels['generated']}: {html.escape(latest.get("generated_at", "not yet") if latest else "not yet")}
{labels['sources']}: {source_count}
{labels['recent_files']}: {recent_file_count}
{labels['dashboard']}: dashboard/index.html</pre>
      </div>
    </section>
    <section id="journal" class="panel">
      <h2>{labels['daily_journals']}</h2>
      {journal_cards}
    </section>
    <section id="sources" class="panel">
      <h2>{labels['recent_sources']}</h2>
      {render_source_list(latest, labels)}
    </section>
  </main>
</body>
</html>
"""
    DASHBOARD_PATH.write_text(html_payload, encoding="utf-8")
    return DASHBOARD_PATH


def render_journal_card(journal: dict[str, Any], labels: dict[str, str] | None = None) -> str:
    labels = labels or LABELS["en"]
    decisions = "".join(f"<li>{html.escape(item.get('decision', ''))}</li>" for item in journal.get("decisions", [])[:5])
    actions = "".join(f"<li>{html.escape(item.get('task', ''))}</li>" for item in journal.get("actions", [])[:5])
    timeline = "".join(
        f"<li><time>{html.escape(item.get('date', '')[:10])}</time>{html.escape(item.get('event', ''))}</li>"
        for item in journal.get("timeline", [])[:6]
    )
    return f"""
<article class="journal-card" id="timeline">
  <header>
    <h3>{html.escape(journal.get('date', labels['untitled']))}</h3>
    <span>{html.escape(str(journal.get('hours', 24)))}{labels['hour_window']}</span>
  </header>
  <p>{html.escape(journal.get('summary', ''))}</p>
  <div class="grid">
    <div><h4>{labels['timeline']}</h4><ol>{timeline}</ol></div>
    <div><h4>{labels['decisions']}</h4><ul>{decisions or f"<li>{labels['no_decisions']}</li>"}</ul></div>
    <div><h4>{labels['action_items']}</h4><ul>{actions or f"<li>{labels['no_actions']}</li>"}</ul></div>
  </div>
</article>
"""


def render_source_list(journal: dict[str, Any] | None, labels: dict[str, str] | None = None) -> str:
    labels = labels or LABELS["en"]
    if not journal:
        return f"<p class='muted'>{labels['no_sources']}</p>"
    items = "".join(f"<li>{html.escape(source)}</li>" for source in journal.get("sources", [])[:20])
    return f"<ul class='sources'>{items}</ul>"


def dashboard_css() -> str:
    return """
:root { color-scheme: dark; --bg:#08090b; --panel:#111318; --panel2:#171a21; --line:#2a2f3a; --text:#f4f7fb; --muted:#9aa4b2; --accent:#4f9cff; }
* { box-sizing: border-box; }
body { margin: 0; min-height: 100vh; display: grid; grid-template-columns: 260px 1fr; background: var(--bg); color: var(--text); font: 14px/1.5 ui-sans-serif, system-ui, -apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif; letter-spacing: 0; }
.sidebar { position: sticky; top: 0; height: 100vh; padding: 28px 18px; border-right: 1px solid var(--line); background: #0b0d11; }
.brand { font-weight: 700; font-size: 17px; margin-bottom: 28px; }
nav { display: grid; gap: 6px; margin-bottom: 28px; }
nav a { color: var(--muted); text-decoration: none; padding: 8px 10px; border-radius: 8px; }
nav a:hover { color: var(--text); background: var(--panel); }
.stat { border: 1px solid var(--line); border-radius: 8px; padding: 12px; margin-bottom: 10px; background: var(--panel); }
.stat strong { display: block; font-size: 22px; }
.stat span, .muted { color: var(--muted); }
main { padding: 34px; max-width: 1180px; width: 100%; }
.hero { display: grid; grid-template-columns: minmax(0, 1.1fr) minmax(320px, .9fr); gap: 28px; align-items: stretch; margin-bottom: 24px; }
h1 { font-size: clamp(36px, 5vw, 72px); line-height: .95; margin: 0 0 20px; max-width: 760px; }
h2 { margin: 0 0 18px; font-size: 20px; }
h3 { margin: 0; font-size: 18px; }
h4 { margin: 0 0 8px; color: var(--muted); font-size: 12px; text-transform: uppercase; letter-spacing: .08em; }
.hero p { color: var(--muted); font-size: 16px; max-width: 760px; }
.terminal, .panel, .journal-card { border: 1px solid var(--line); border-radius: 8px; background: linear-gradient(180deg, var(--panel), #0d0f14); }
.terminal { padding: 16px; overflow: hidden; }
.terminal pre { white-space: pre-wrap; color: #dce7f7; margin: 18px 0 0; font: 13px/1.55 ui-monospace, SFMono-Regular, Menlo, Consolas, monospace; }
.dots { display: flex; gap: 6px; }
.dots i { width: 10px; height: 10px; display: block; border-radius: 50%; background: var(--line); }
.dots i:first-child { background: #ff5f57; }
.dots i:nth-child(2) { background: #ffbd2e; }
.dots i:nth-child(3) { background: #28c840; }
.panel { padding: 18px; margin-bottom: 20px; }
.journal-card { padding: 18px; margin-bottom: 14px; background: var(--panel2); }
.journal-card header { display: flex; justify-content: space-between; gap: 12px; border-bottom: 1px solid var(--line); padding-bottom: 12px; margin-bottom: 12px; }
.journal-card header span { color: var(--accent); }
.journal-card p { color: #d7deea; }
.grid { display: grid; grid-template-columns: repeat(3, minmax(0, 1fr)); gap: 16px; }
ol, ul { margin: 0; padding-left: 18px; }
li { margin: 6px 0; color: #d2dae7; }
time { display: block; color: var(--accent); font-size: 12px; }
.sources { font-family: ui-monospace, SFMono-Regular, Menlo, Consolas, monospace; overflow-wrap: anywhere; }
@media (max-width: 860px) {
  body { display: block; }
  .sidebar { position: static; height: auto; border-right: 0; border-bottom: 1px solid var(--line); }
  main { padding: 22px; }
  .hero, .grid { grid-template-columns: 1fr; }
}
"""


def serve(port: int, lang: str = "en") -> None:
    render_dashboard(lang)
    os.chdir(ROOT)
    server = ThreadingHTTPServer(("127.0.0.1", port), SimpleHTTPRequestHandler)
    print(f"Serving dashboard at http://127.0.0.1:{port}/dashboard/")
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\nStopped.")


def print_json(payload: Any) -> None:
    print(json.dumps(payload, ensure_ascii=False, indent=2))


def parse_paths(values: list[str] | None) -> list[Path]:
    if not values:
        return DEFAULT_DOCS
    return [Path(value) for value in values]


def parse_optional_paths(values: list[str] | None) -> list[Path] | None:
    if values is None:
        return None
    if not values:
        return []
    return [Path(value) for value in values]


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Agentic Autobiography local memory engine")
    sub = parser.add_subparsers(dest="command", required=True)

    index_cmd = sub.add_parser("index", help="Index local documents")
    index_cmd.add_argument("--docs", nargs="*", help="Document roots to scan")

    search_cmd = sub.add_parser("search", help="Search indexed memory")
    search_cmd.add_argument("query")
    search_cmd.add_argument("--limit", type=int, default=5)

    summary_cmd = sub.add_parser("summary", help="Generate recovered context summary")
    summary_cmd.add_argument("query")

    timeline_cmd = sub.add_parser("timeline", help="Generate source timeline")
    timeline_cmd.add_argument("entity")
    timeline_cmd.add_argument("--limit", type=int, default=10)

    actions_cmd = sub.add_parser("actions", help="Extract action items")
    actions_cmd.add_argument("scope", nargs="?", default="")
    actions_cmd.add_argument("--limit", type=int, default=10)

    activity_cmd = sub.add_parser("activity", help="List recent local file activity")
    activity_cmd.add_argument("--hours", type=int, default=24)
    activity_cmd.add_argument("--activity-roots", nargs="*", help="Activity roots to scan")
    activity_cmd.add_argument("--limit", type=int, default=50)

    journal_cmd = sub.add_parser("journal", help="Generate a daily journal")
    journal_cmd.add_argument("--hours", type=int, default=24)
    journal_cmd.add_argument("--docs", nargs="*", help="Document roots to scan")
    journal_cmd.add_argument("--activity-roots", nargs="*", help="Recent-activity roots to scan")

    dashboard_cmd = sub.add_parser("render-dashboard", help="Render dashboard/index.html")
    dashboard_cmd.add_argument("--lang", choices=sorted(LABELS), default="en")

    serve_cmd = sub.add_parser("serve", help="Serve the dashboard")
    serve_cmd.add_argument("--port", type=int, default=8766)
    serve_cmd.add_argument("--lang", choices=sorted(LABELS), default="en")

    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    if args.command == "index":
        print_json(build_index(parse_paths(args.docs)))
    elif args.command == "search":
        print_json(search(args.query, limit=args.limit))
    elif args.command == "summary":
        print_json(summarize(args.query))
    elif args.command == "timeline":
        print_json(timeline(args.entity, limit=args.limit))
    elif args.command == "actions":
        matches = search(args.scope or "action todo next follow-up", limit=20)
        print_json(extract_actions(matches, limit=args.limit))
    elif args.command == "activity":
        config = load_activity_config()
        roots = parse_optional_paths(args.activity_roots)
        if roots is None:
            roots = [Path(value) for value in config["roots"]]
        print_json(
            recent_file_activity(
                roots,
                args.hours,
                exclude_names=set(config.get("exclude_names", [])) or DEFAULT_EXCLUDES,
                max_files=args.limit,
            )
        )
    elif args.command == "journal":
        print_json(
            generate_journal(
                hours=args.hours,
                docs=parse_paths(args.docs),
                activity_roots=parse_optional_paths(args.activity_roots),
            )
        )
    elif args.command == "render-dashboard":
        print_json({"dashboard": str(render_dashboard(args.lang)), "lang": args.lang})
    elif args.command == "serve":
        serve(args.port, args.lang)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
