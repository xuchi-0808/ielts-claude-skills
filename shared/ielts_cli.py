#!/usr/bin/env python3
"""IELTS Claude Skills — Data Layer CLI.

A single-file, stdlib-only Python script that manages all data persistence
for the IELTS Claude Skills system. Called by SKILL.md prompts via Bash.

Usage:
  python3 ielts_cli.py init
  python3 ielts_cli.py config get
  python3 ielts_cli.py config set --target 7.0 --exam-date 2026-06-15
  python3 ielts_cli.py writing add --task-type "Task 2" --topic "..." --scores '{"TR":6,"CC":5.5,"LR":5.5,"GRA":6}' --content "..."
  python3 ielts_cli.py writing list [--last 5]
  ...
"""

import argparse
import json
import os
import sys
import shutil
import zipfile
import hashlib
from datetime import datetime, date
from pathlib import Path
from dataclasses import dataclass, asdict, field
from typing import Optional

# ── Paths ──────────────────────────────────────────────────────────
IELTS_DIR = Path.home() / ".ielts"
CONFIG_FILE = IELTS_DIR / "config.json"
ERRORS_FILE = IELTS_DIR / "errors.json"
SYNONYMS_FILE = IELTS_DIR / "synonyms.json"
PROGRESS_FILE = IELTS_DIR / "progress.json"
VOCAB_FILE = IELTS_DIR / "vocab.json"
WRITING_DIR = IELTS_DIR / "writing"
READING_DIR = IELTS_DIR / "reading"
LISTENING_DIR = IELTS_DIR / "listening"
SPEAKING_DIR = IELTS_DIR / "speaking"
DASHBOARD_FILE = IELTS_DIR / "dashboard.html"
DASHBOARD_TEMPLATE = Path(__file__).resolve().parent.parent / "dashboard" / "template.html"


# ── Data Models ────────────────────────────────────────────────────

@dataclass
class Config:
    target_score: float = 0.0
    exam_date: str = ""  # YYYY-MM-DD
    listening: float = 0.0
    reading: float = 0.0
    writing: float = 0.0
    speaking: float = 0.0
    name: str = ""
    updated_at: str = ""

    def days_until_exam(self) -> int:
        if not self.exam_date:
            return 0
        try:
            d = datetime.strptime(self.exam_date, "%Y-%m-%d").date()
            return (d - date.today()).days
        except ValueError:
            return 0

    def overall_band(self) -> float:
        scores = [s for s in [self.listening, self.reading, self.writing, self.speaking] if s > 0]
        if not scores:
            return 0.0
        avg = sum(scores) / len(scores)
        return _round_ielts(avg)


@dataclass
class EssayRecord:
    date: str
    task_type: str
    topic: str
    word_count: int
    scores: dict  # {TR, CC, LR, GRA}
    total: float
    key_issues: list = field(default_factory=list)
    file: str = ""


@dataclass
class ReadingRecord:
    date: str
    passage_title: str
    total_questions: int
    correct: int
    score: float
    question_types: dict = field(default_factory=dict)  # {type: {total, correct}}
    synonyms_added: int = 0
    key_errors: list = field(default_factory=list)


@dataclass
class ListeningRecord:
    date: str
    test_name: str
    total_questions: int
    correct: int
    score: float
    section_scores: dict = field(default_factory=dict)
    question_type_errors: dict = field(default_factory=dict)
    key_errors: list = field(default_factory=list)


@dataclass
class SpeakingRecord:
    date: str
    topic: str
    part: str  # Part 1 / Part 2 / Part 3
    group: str = ""  # which universal story group
    notes: str = ""


@dataclass
class VocabWord:
    word: str
    definition: str
    example: str
    synonyms: list = field(default_factory=list)
    source: str = ""  # where encountered
    date_added: str = ""
    ease_factor: float = 2.5
    interval: int = 0
    repetitions: int = 0
    next_review: str = ""  # YYYY-MM-DD
    last_reviewed: str = ""


# ── Utilities ──────────────────────────────────────────────────────

def _round_ielts(score: float) -> float:
    """Round to nearest 0.5, with .25/.75 rounding up."""
    whole = int(score)
    frac = score - whole
    if frac < 0.25:
        return float(whole)
    elif frac < 0.75:
        return whole + 0.5
    else:
        return float(whole + 1)


def _ensure_dir(path: Path):
    path.mkdir(parents=True, exist_ok=True)


def _load_json(path: Path, default=None):
    if not path.exists():
        return default
    try:
        with open(path, "r", encoding="utf-8") as f:
            return json.load(f)
    except (json.JSONDecodeError, IOError):
        return default


def _save_json(path: Path, data):
    _ensure_dir(path.parent)
    with open(path, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2, default=str)


def _today() -> str:
    return date.today().isoformat()


def _slug(text: str, max_len: int = 40) -> str:
    """Create a safe filename slug from text."""
    slug = "".join(c if c.isalnum() or c in " -_" else "" for c in text.lower())
    slug = slug.strip().replace(" ", "-")[:max_len]
    return slug or "untitled"


# ── Commands ───────────────────────────────────────────────────────

def cmd_init():
    """Initialize ~/.ielts/ directory and default config."""
    _ensure_dir(IELTS_DIR)
    _ensure_dir(WRITING_DIR)
    _ensure_dir(READING_DIR)
    _ensure_dir(LISTENING_DIR)
    _ensure_dir(SPEAKING_DIR)

    if not CONFIG_FILE.exists():
        config = Config(updated_at=_today())
        _save_json(CONFIG_FILE, asdict(config))

    for f, default in [
        (ERRORS_FILE, {"writing": [], "reading": [], "listening": [], "speaking": []}),
        (SYNONYMS_FILE, []),
        (PROGRESS_FILE, {"writing_scores": [], "reading_scores": [], "listening_scores": [], "speaking_scores": []}),
        (VOCAB_FILE, []),
    ]:
        if not f.exists():
            _save_json(f, default)

    for d, default in [
        (WRITING_DIR / "index.json", []),
        (READING_DIR / "index.json", []),
        (LISTENING_DIR / "index.json", []),
        (SPEAKING_DIR / "index.json", []),
    ]:
        if not d.exists():
            _save_json(d, default)

    print(json.dumps({"status": "ok", "message": "IELTS data directory initialized", "path": str(IELTS_DIR)}))
    return 0


def cmd_config_get():
    """Read and output config.json."""
    config = _load_json(CONFIG_FILE, asdict(Config()))
    cfg = Config(**{k: v for k, v in config.items() if k in Config.__dataclass_fields__})
    config["days_until_exam"] = cfg.days_until_exam()
    config["overall_band"] = cfg.overall_band()
    print(json.dumps(config, ensure_ascii=False, indent=2))
    return 0


def cmd_config_set(args):
    """Update config fields."""
    config = _load_json(CONFIG_FILE, asdict(Config()))

    field_map = {
        "target_score": "target_score",
        "exam_date": "exam_date",
        "listening": "listening",
        "reading": "reading",
        "writing": "writing",
        "speaking": "speaking",
        "name": "name",
    }

    updated = False
    for arg_name, config_key in field_map.items():
        val = getattr(args, arg_name, None)
        if val is not None:
            if config_key in ("target_score", "listening", "reading", "writing", "speaking"):
                val = float(val)
            config[config_key] = val
            updated = True

    if updated:
        config["updated_at"] = _today()

    _save_json(CONFIG_FILE, config)
    print(json.dumps({"status": "ok", "config": config}, ensure_ascii=False))
    return 0


def cmd_writing_add(args):
    """Save an essay with scores."""
    if not CONFIG_FILE.exists():
        print(json.dumps({"status": "error", "message": "Run init first"}))
        return 1

    scores = json.loads(args.scores) if args.scores else {}
    total = args.total if args.total is not None else (sum(scores.values()) / len(scores) if scores else 0)
    total = round(total * 2) / 2

    key_issues = json.loads(args.key_issues) if args.key_issues else []

    slug = _slug(args.topic) if args.topic else "essay"
    filename = f"{_today()}-{slug}.md"
    filepath = WRITING_DIR / filename

    essay_text = args.content or ""
    with open(filepath, "w", encoding="utf-8") as f:
        f.write(f"# {args.topic or 'Essay'}\n\n")
        f.write(f"**Date:** {_today()}\n")
        f.write(f"**Task Type:** {args.task_type}\n\n")
        f.write(essay_text)

    record = EssayRecord(
        date=_today(),
        task_type=args.task_type or "Task 2",
        topic=args.topic or "",
        word_count=args.word_count or 0,
        scores=scores,
        total=total,
        key_issues=key_issues,
        file=filename,
    )

    index = _load_json(WRITING_DIR / "index.json", [])
    index.append(asdict(record))
    _save_json(WRITING_DIR / "index.json", index)

    # Auto-add key issues to error logbook
    for issue in key_issues:
        _add_error("writing", issue)

    # Record progress
    if total > 0:
        cmd_progress_add_internal("writing", total)

    print(json.dumps({"status": "ok", "record": asdict(record)}, ensure_ascii=False))
    return 0


def cmd_writing_list(args):
    """List essay history."""
    index = _load_json(WRITING_DIR / "index.json", [])
    if args.last and args.last > 0:
        index = index[-args.last:]
    print(json.dumps(index, ensure_ascii=False, indent=2))
    return 0


def cmd_reading_add(args):
    """Save a reading practice record."""
    if not CONFIG_FILE.exists():
        print(json.dumps({"status": "error", "message": "Run init first"}))
        return 1

    question_types = json.loads(args.question_types) if args.question_types else {}
    key_errors = json.loads(args.key_errors) if args.key_errors else []

    total_q = args.total_questions or 0
    correct = args.correct or 0

    record = ReadingRecord(
        date=_today(),
        passage_title=args.passage_title or "",
        total_questions=total_q,
        correct=correct,
        score=args.score or 0.0,
        question_types=question_types,
        synonyms_added=args.synonyms_added or 0,
        key_errors=key_errors,
    )

    index = _load_json(READING_DIR / "index.json", [])
    index.append(asdict(record))
    _save_json(READING_DIR / "index.json", index)

    for err in key_errors:
        _add_error("reading", err)

    if record.score > 0:
        cmd_progress_add_internal("reading", record.score)

    print(json.dumps({"status": "ok", "record": asdict(record)}, ensure_ascii=False))
    return 0


def cmd_listening_add(args):
    """Save a listening practice record."""
    if not CONFIG_FILE.exists():
        print(json.dumps({"status": "error", "message": "Run init first"}))
        return 1

    section_scores = json.loads(args.section_scores) if args.section_scores else {}
    question_type_errors = json.loads(args.question_type_errors) if args.question_type_errors else {}
    key_errors = json.loads(args.key_errors) if args.key_errors else []

    total_q = args.total_questions or 0
    correct = args.correct or 0

    record = ListeningRecord(
        date=_today(),
        test_name=args.test_name or "",
        total_questions=total_q,
        correct=correct,
        score=args.score or 0.0,
        section_scores=section_scores,
        question_type_errors=question_type_errors,
        key_errors=key_errors,
    )

    index = _load_json(LISTENING_DIR / "index.json", [])
    index.append(asdict(record))
    _save_json(LISTENING_DIR / "index.json", index)

    for err in key_errors:
        _add_error("listening", err)

    # Track per-question-type errors
    for qtype, count in question_type_errors.items():
        if count > 0:
            _add_error("listening", f"{qtype}: {count} errors")

    if record.score > 0:
        cmd_progress_add_internal("listening", record.score)

    print(json.dumps({"status": "ok", "record": asdict(record)}, ensure_ascii=False))
    return 0


def cmd_speaking_add(args):
    """Save a speaking practice record."""
    if not CONFIG_FILE.exists():
        print(json.dumps({"status": "error", "message": "Run init first"}))
        return 1

    record = SpeakingRecord(
        date=_today(),
        topic=args.topic or "",
        part=args.part or "Part 2",
        group=args.group or "",
        notes=args.notes or "",
    )

    index = _load_json(SPEAKING_DIR / "index.json", [])
    index.append(asdict(record))
    _save_json(SPEAKING_DIR / "index.json", index)

    print(json.dumps({"status": "ok", "record": asdict(record)}, ensure_ascii=False))
    return 0


def _add_error(category: str, tag: str):
    """Internal: add an error tag to the error logbook."""
    errors = _load_json(ERRORS_FILE, {"writing": [], "reading": [], "listening": [], "speaking": []})
    if category not in errors:
        errors[category] = []

    for item in errors[category]:
        if item["tag"] == tag:
            item["count"] += 1
            item["last_seen"] = _today()
            break
    else:
        errors[category].append({"tag": tag, "count": 1, "first_seen": _today(), "last_seen": _today()})

    _save_json(ERRORS_FILE, errors)


def cmd_error_add(args):
    """Add an error tag to the logbook."""
    _add_error(args.category, args.tag)
    print(json.dumps({"status": "ok", "category": args.category, "tag": args.tag}))
    return 0


def cmd_error_list(args):
    """List errors, optionally filtered by category."""
    errors = _load_json(ERRORS_FILE, {"writing": [], "reading": [], "listening": [], "speaking": []})
    if args.category and args.category in errors:
        result = errors[args.category]
    else:
        result = errors
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0


def cmd_synonym_add(args):
    """Add a synonym pair to the library."""
    synonyms = _load_json(SYNONYMS_FILE, [])

    # Check for duplicates
    for s in synonyms:
        if s["word"].lower() == args.word.lower() and s["synonym"].lower() == args.synonym.lower():
            print(json.dumps({"status": "ok", "message": "Already exists", "entry": s}))
            return 0

    entry = {
        "word": args.word,
        "synonym": args.synonym,
        "source": args.source or "manual",
        "context": args.context or "",
        "date": _today(),
    }
    synonyms.append(entry)
    _save_json(SYNONYMS_FILE, synonyms)
    print(json.dumps({"status": "ok", "entry": entry}))
    return 0


def cmd_synonym_search(args):
    """Search the synonym library."""
    synonyms = _load_json(SYNONYMS_FILE, [])
    query = args.word.lower()
    results = [s for s in synonyms if query in s["word"].lower() or query in s["synonym"].lower()]
    print(json.dumps(results, ensure_ascii=False, indent=2))
    return 0


def cmd_synonym_list(args):
    """List all synonyms."""
    synonyms = _load_json(SYNONYMS_FILE, [])
    print(json.dumps(synonyms, ensure_ascii=False, indent=2))
    return 0


def cmd_progress_add_internal(skill: str, score: float):
    """Internal: record a score without printing."""
    progress = _load_json(PROGRESS_FILE, {
        "writing_scores": [], "reading_scores": [],
        "listening_scores": [], "speaking_scores": [],
    })
    key = f"{skill}_scores"
    if key not in progress:
        progress[key] = []
    progress[key].append({"date": _today(), "score": score})
    _save_json(PROGRESS_FILE, progress)


def cmd_progress_add(args):
    """Record a score for a skill."""
    cmd_progress_add_internal(args.skill, args.score)
    print(json.dumps({"status": "ok", "skill": args.skill, "score": args.score, "date": _today()}))
    return 0


def cmd_progress_show(args):
    """Show progress trends."""
    progress = _load_json(PROGRESS_FILE, {
        "writing_scores": [], "reading_scores": [],
        "listening_scores": [], "speaking_scores": [],
    })
    config = _load_json(CONFIG_FILE, asdict(Config()))

    # Compute trends
    result = {"scores": progress, "target": config.get("target_score", 0), "exam_date": config.get("exam_date", "")}

    for skill in ["writing", "reading", "listening", "speaking"]:
        key = f"{skill}_scores"
        scores = progress.get(key, [])
        if len(scores) >= 2:
            first = scores[0]["score"]
            last = scores[-1]["score"]
            result[f"{skill}_trend"] = round(last - first, 1)
            result[f"{skill}_count"] = len(scores)
            result[f"{skill}_latest"] = last
        elif len(scores) == 1:
            result[f"{skill}_latest"] = scores[0]["score"]
            result[f"{skill}_count"] = 1

    # Error summary
    errors = _load_json(ERRORS_FILE)
    result["error_summary"] = {}
    for cat in ["writing", "reading", "listening", "speaking"]:
        result["error_summary"][cat] = sorted(errors.get(cat, []), key=lambda x: x["count"], reverse=True)[:5]

    # Synonym count
    synonyms = _load_json(SYNONYMS_FILE, [])
    result["synonym_count"] = len(synonyms)

    # Vocab count
    vocab = _load_json(VOCAB_FILE, [])
    result["vocab_count"] = len(vocab)
    result["vocab_due"] = len([v for v in vocab if v.get("next_review", "") <= _today()])

    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0


def cmd_vocab_add(args):
    """Add a word to vocabulary."""
    vocab = _load_json(VOCAB_FILE, [])

    # Check duplicate
    for v in vocab:
        if v["word"].lower() == args.word.lower():
            print(json.dumps({"status": "error", "message": f"Word '{args.word}' already exists"}))
            return 1

    synonyms = json.loads(args.synonyms) if args.synonyms else []
    word = VocabWord(
        word=args.word,
        definition=args.definition or "",
        example=args.example or "",
        synonyms=synonyms,
        source=args.source or "",
        date_added=_today(),
        next_review=_today(),  # due immediately
    )
    vocab.append(asdict(word))
    _save_json(VOCAB_FILE, vocab)

    # Also add to synonym library
    for syn in synonyms:
        cmd_synonym_add_internal(args.word, syn, args.source or "vocab")

    print(json.dumps({"status": "ok", "word": asdict(word)}, ensure_ascii=False))
    return 0


def cmd_synonym_add_internal(word: str, synonym: str, source: str = ""):
    """Internal: add synonym without printing, skip duplicates."""
    synonyms = _load_json(SYNONYMS_FILE, [])
    for s in synonyms:
        if s["word"].lower() == word.lower() and s["synonym"].lower() == synonym.lower():
            return
    synonyms.append({"word": word, "synonym": synonym, "source": source, "context": "", "date": _today()})
    _save_json(SYNONYMS_FILE, synonyms)


def cmd_vocab_review(args):
    """Get words due for review (spaced repetition)."""
    vocab = _load_json(VOCAB_FILE, [])
    today = _today()

    due = [v for v in vocab if v.get("next_review", "") <= today]
    due.sort(key=lambda v: v.get("next_review", ""))

    print(json.dumps({"due_count": len(due), "total": len(vocab), "words": due}, ensure_ascii=False, indent=2))
    return 0


def cmd_vocab_update(args):
    """Update a word after review (SM-2 algorithm)."""
    vocab = _load_json(VOCAB_FILE, [])

    for v in vocab:
        if v["word"].lower() == args.word.lower():
            quality = args.quality  # 0-5

            if quality >= 3:
                if v["repetitions"] == 0:
                    v["interval"] = 1
                elif v["repetitions"] == 1:
                    v["interval"] = 6
                else:
                    v["interval"] = round(v["interval"] * v["ease_factor"])

                v["repetitions"] += 1
            else:
                v["interval"] = 1
                v["repetitions"] = 0

            v["ease_factor"] = max(1.3, v["ease_factor"] + (0.1 - (5 - quality) * (0.08 + (5 - quality) * 0.02)))
            v["last_reviewed"] = _today()

            # Calculate next review date
            from datetime import timedelta
            next_date = date.today() + timedelta(days=v["interval"])
            v["next_review"] = next_date.isoformat()

            _save_json(VOCAB_FILE, vocab)
            print(json.dumps({"status": "ok", "word": v}, ensure_ascii=False))
            return 0

    print(json.dumps({"status": "error", "message": f"Word '{args.word}' not found"}))
    return 1


def cmd_vocab_list(args):
    """List all vocabulary words."""
    vocab = _load_json(VOCAB_FILE, [])

    if args.due:
        today = _today()
        vocab = [v for v in vocab if v.get("next_review", "") <= today]

    if args.sort_by == "next_review":
        vocab.sort(key=lambda v: v.get("next_review", ""))
    elif args.sort_by == "date":
        vocab.sort(key=lambda v: v.get("date_added", ""), reverse=True)

    print(json.dumps(vocab, ensure_ascii=False, indent=2))
    return 0


def cmd_dashboard_generate(args):
    """Generate dashboard HTML from template + live data."""
    if not DASHBOARD_TEMPLATE.exists():
        print(json.dumps({"status": "error", "message": f"Template not found: {DASHBOARD_TEMPLATE}"}))
        return 1

    template = DASHBOARD_TEMPLATE.read_text(encoding="utf-8")

    # Gather all data
    config = _load_json(CONFIG_FILE, asdict(Config()))
    progress = _load_json(PROGRESS_FILE)
    errors = _load_json(ERRORS_FILE)
    synonyms = _load_json(SYNONYMS_FILE, [])
    vocab = _load_json(VOCAB_FILE, [])
    writing_index = _load_json(WRITING_DIR / "index.json", [])
    reading_index = _load_json(READING_DIR / "index.json", [])
    listening_index = _load_json(LISTENING_DIR / "index.json", [])
    speaking_index = _load_json(SPEAKING_DIR / "index.json", [])

    data_json = json.dumps({
        "config": config,
        "progress": progress,
        "errors": errors,
        "synonyms": synonyms,
        "vocab": vocab,
        "writing": writing_index,
        "reading": reading_index,
        "listening": listening_index,
        "speaking": speaking_index,
    }, ensure_ascii=False, default=str)

    # Replace data placeholder in template
    if "___IELTS_DATA___" in template:
        html = template.replace("___IELTS_DATA___", data_json)
    else:
        # Inject data before </body>
        html = template.replace(
            "</body>",
            f'<script id="ielts-data" type="application/json">\n{data_json}\n</script>\n</body>'
        )

    _ensure_dir(IELTS_DIR)
    DASHBOARD_FILE.write_text(html, encoding="utf-8")

    print(json.dumps({"status": "ok", "path": str(DASHBOARD_FILE)}))
    return 0


def cmd_backup(args):
    """Create a zip backup of ~/.ielts/."""
    output = args.output or Path.home() / f"ielts-backup-{_today()}.zip"
    output = Path(output)

    with zipfile.ZipFile(output, "w", zipfile.ZIP_DEFLATED) as zf:
        for root, dirs, files in os.walk(IELTS_DIR):
            for file in files:
                filepath = Path(root) / file
                arcname = filepath.relative_to(IELTS_DIR.parent)
                zf.write(filepath, arcname)

    print(json.dumps({"status": "ok", "backup_path": str(output), "size": output.stat().st_size}))
    return 0


def cmd_restore(args):
    """Restore ~/.ielts/ from a zip backup."""
    backup_path = Path(args.file)
    if not backup_path.exists():
        print(json.dumps({"status": "error", "message": f"Backup file not found: {backup_path}"}))
        return 1

    with zipfile.ZipFile(backup_path, "r") as zf:
        zf.extractall(IELTS_DIR.parent)

    print(json.dumps({"status": "ok", "message": "Restored from " + str(backup_path)}))
    return 0


def cmd_status(args):
    """Output a brief status summary for Claude Code status bar."""
    config = _load_json(CONFIG_FILE, asdict(Config()))
    progress = _load_json(PROGRESS_FILE)

    days = Config(**config).days_until_exam()
    target = config.get("target_score", 0)

    latest = {}
    for skill in ["writing", "reading", "listening", "speaking"]:
        scores = progress.get(f"{skill}_scores", [])
        if scores:
            latest[skill] = scores[-1]["score"]

    vocab = _load_json(VOCAB_FILE, [])
    vocab_due = len([v for v in vocab if v.get("next_review", "") <= _today()])

    parts = []
    if days > 0:
        parts.append(f"📅 {days}d")
    if target > 0:
        parts.append(f"🎯 {target}")
    if latest:
        score_str = " | ".join(f"{k[0].upper()}:{v}" for k, v in latest.items())
        parts.append(score_str)
    if vocab_due > 0:
        parts.append(f"📝 {vocab_due} words")

    print("IELTS " + " · ".join(parts) if parts else "IELTS: run /ielts to set up")
    return 0


# ── CLI Main ───────────────────────────────────────────────────────

def main():
    parser = argparse.ArgumentParser(description="IELTS Claude Skills Data Layer")
    sub = parser.add_subparsers(dest="command", help="Available commands")

    # init
    sub.add_parser("init", help="Initialize ~/.ielts/ directory")

    # config
    p_config = sub.add_parser("config", help="Config management")
    p_config_sub = p_config.add_subparsers(dest="config_action")
    p_config_sub.add_parser("get", help="Read config")
    p_set = p_config_sub.add_parser("set", help="Update config")
    p_set.add_argument("--target-score", type=float)
    p_set.add_argument("--exam-date")
    p_set.add_argument("--listening", type=float)
    p_set.add_argument("--reading", type=float)
    p_set.add_argument("--writing", type=float)
    p_set.add_argument("--speaking", type=float)
    p_set.add_argument("--name")

    # writing
    p_writing = sub.add_parser("writing", help="Writing data management")
    p_writing_sub = p_writing.add_subparsers(dest="writing_action")
    p_wa = p_writing_sub.add_parser("add", help="Save an essay")
    p_wa.add_argument("--task-type", default="Task 2")
    p_wa.add_argument("--topic", default="")
    p_wa.add_argument("--word-count", type=int, default=0)
    p_wa.add_argument("--scores", default="{}")
    p_wa.add_argument("--total", type=float)
    p_wa.add_argument("--key-issues", default="[]")
    p_wa.add_argument("--content", default="")
    p_wl = p_writing_sub.add_parser("list", help="List essays")
    p_wl.add_argument("--last", type=int, default=0)

    # reading
    p_reading = sub.add_parser("reading", help="Reading data management")
    p_reading_sub = p_reading.add_subparsers(dest="reading_action")
    p_ra = p_reading_sub.add_parser("add", help="Save a reading record")
    p_ra.add_argument("--passage-title", default="")
    p_ra.add_argument("--total-questions", type=int, default=0)
    p_ra.add_argument("--correct", type=int, default=0)
    p_ra.add_argument("--score", type=float, default=0.0)
    p_ra.add_argument("--question-types", default="{}")
    p_ra.add_argument("--synonyms-added", type=int, default=0)
    p_ra.add_argument("--key-errors", default="[]")

    # listening
    p_listening = sub.add_parser("listening", help="Listening data management")
    p_listening_sub = p_listening.add_subparsers(dest="listening_action")
    p_la = p_listening_sub.add_parser("add", help="Save a listening record")
    p_la.add_argument("--test-name", default="")
    p_la.add_argument("--total-questions", type=int, default=0)
    p_la.add_argument("--correct", type=int, default=0)
    p_la.add_argument("--score", type=float, default=0.0)
    p_la.add_argument("--section-scores", default="{}")
    p_la.add_argument("--question-type-errors", default="{}")
    p_la.add_argument("--key-errors", default="[]")

    # speaking
    p_speaking = sub.add_parser("speaking", help="Speaking data management")
    p_speaking_sub = p_speaking.add_subparsers(dest="speaking_action")
    p_sa = p_speaking_sub.add_parser("add", help="Save a speaking record")
    p_sa.add_argument("--topic", default="")
    p_sa.add_argument("--part", default="Part 2")
    p_sa.add_argument("--group", default="")
    p_sa.add_argument("--notes", default="")

    # error
    p_error = sub.add_parser("error", help="Error logbook management")
    p_error_sub = p_error.add_subparsers(dest="error_action")
    p_ea = p_error_sub.add_parser("add", help="Add an error tag")
    p_ea.add_argument("--category", required=True, choices=["writing", "reading", "listening", "speaking"])
    p_ea.add_argument("--tag", required=True)
    p_el = p_error_sub.add_parser("list", help="List errors")
    p_el.add_argument("--category", choices=["writing", "reading", "listening", "speaking"])

    # synonym
    p_syn = sub.add_parser("synonym", help="Synonym library management")
    p_syn_sub = p_syn.add_subparsers(dest="synonym_action")
    p_sa2 = p_syn_sub.add_parser("add", help="Add a synonym pair")
    p_sa2.add_argument("--word", required=True)
    p_sa2.add_argument("--synonym", required=True)
    p_sa2.add_argument("--source", default="manual")
    p_sa2.add_argument("--context", default="")
    p_ss = p_syn_sub.add_parser("search", help="Search synonyms")
    p_ss.add_argument("--word", required=True)
    p_syn_sub.add_parser("list", help="List all synonyms")

    # progress
    p_prog = sub.add_parser("progress", help="Progress tracking")
    p_prog_sub = p_prog.add_subparsers(dest="progress_action")
    p_pa = p_prog_sub.add_parser("add", help="Record a score")
    p_pa.add_argument("--skill", required=True, choices=["writing", "reading", "listening", "speaking"])
    p_pa.add_argument("--score", type=float, required=True)
    p_prog_sub.add_parser("show", help="Show progress trends")

    # vocab
    p_vocab = sub.add_parser("vocab", help="Vocabulary management")
    p_vocab_sub = p_vocab.add_subparsers(dest="vocab_action")
    p_va = p_vocab_sub.add_parser("add", help="Add a word")
    p_va.add_argument("--word", required=True)
    p_va.add_argument("--definition", default="")
    p_va.add_argument("--example", default="")
    p_va.add_argument("--synonyms", default="[]")
    p_va.add_argument("--source", default="")
    p_vr = p_vocab_sub.add_parser("review", help="Get words due for review")
    p_vu = p_vocab_sub.add_parser("update", help="Update word after review")
    p_vu.add_argument("--word", required=True)
    p_vu.add_argument("--quality", type=int, required=True, choices=[0, 1, 2, 3, 4, 5])
    p_vl = p_vocab_sub.add_parser("list", help="List vocabulary")
    p_vl.add_argument("--due", action="store_true")
    p_vl.add_argument("--sort-by", default="date", choices=["date", "next_review"])

    # dashboard
    sub.add_parser("dashboard", help="Generate dashboard HTML")

    # backup / restore
    p_backup = sub.add_parser("backup", help="Create backup")
    p_backup.add_argument("--output", default="")
    p_restore = sub.add_parser("restore", help="Restore from backup")
    p_restore.add_argument("--file", required=True)

    # status
    sub.add_parser("status", help="Output status bar summary")

    args = parser.parse_args()

    if args.command is None:
        parser.print_help()
        return 0

    # Route to handler
    handlers = {
        "init": lambda: cmd_init(),
        "config": lambda: _handle_config(args),
        "writing": lambda: _handle_writing(args),
        "reading": lambda: _handle_reading(args),
        "listening": lambda: _handle_listening(args),
        "speaking": lambda: _handle_speaking(args),
        "error": lambda: _handle_error(args),
        "synonym": lambda: _handle_synonym(args),
        "progress": lambda: _handle_progress(args),
        "vocab": lambda: _handle_vocab(args),
        "dashboard": lambda: cmd_dashboard_generate(args),
        "backup": lambda: cmd_backup(args),
        "restore": lambda: cmd_restore(args),
        "status": lambda: cmd_status(args),
    }

    handler = handlers.get(args.command)
    if handler:
        return handler()
    else:
        parser.print_help()
        return 1


def _handle_config(args):
    if args.config_action == "get":
        return cmd_config_get()
    elif args.config_action == "set":
        return cmd_config_set(args)
    else:
        print("Usage: ielts_cli.py config [get|set]")
        return 1


def _handle_writing(args):
    if args.writing_action == "add":
        return cmd_writing_add(args)
    elif args.writing_action == "list":
        return cmd_writing_list(args)
    else:
        print("Usage: ielts_cli.py writing [add|list]")
        return 1


def _handle_reading(args):
    if args.reading_action == "add":
        return cmd_reading_add(args)
    else:
        print("Usage: ielts_cli.py reading add ...")
        return 1


def _handle_listening(args):
    if args.listening_action == "add":
        return cmd_listening_add(args)
    else:
        print("Usage: ielts_cli.py listening add ...")
        return 1


def _handle_speaking(args):
    if args.speaking_action == "add":
        return cmd_speaking_add(args)
    else:
        print("Usage: ielts_cli.py speaking add ...")
        return 1


def _handle_error(args):
    if args.error_action == "add":
        return cmd_error_add(args)
    elif args.error_action == "list":
        return cmd_error_list(args)
    else:
        print("Usage: ielts_cli.py error [add|list]")
        return 1


def _handle_synonym(args):
    if args.synonym_action == "add":
        return cmd_synonym_add(args)
    elif args.synonym_action == "search":
        return cmd_synonym_search(args)
    elif args.synonym_action == "list":
        return cmd_synonym_list(args)
    else:
        print("Usage: ielts_cli.py synonym [add|search|list]")
        return 1


def _handle_progress(args):
    if args.progress_action == "add":
        return cmd_progress_add(args)
    elif args.progress_action == "show":
        return cmd_progress_show(args)
    else:
        print("Usage: ielts_cli.py progress [add|show]")
        return 1


def _handle_vocab(args):
    if args.vocab_action == "add":
        return cmd_vocab_add(args)
    elif args.vocab_action == "review":
        return cmd_vocab_review(args)
    elif args.vocab_action == "update":
        return cmd_vocab_update(args)
    elif args.vocab_action == "list":
        return cmd_vocab_list(args)
    else:
        print("Usage: ielts_cli.py vocab [add|review|update|list]")
        return 1


if __name__ == "__main__":
    sys.exit(main())
