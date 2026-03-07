#!/usr/bin/env python3

from __future__ import annotations

import argparse
import ast
import dataclasses
import datetime as dt
import hashlib
import json
import os
import re
import shutil
import subprocess
import sys
import textwrap
from pathlib import Path
from typing import Iterable


@dataclasses.dataclass(frozen=True)
class TrackedFile:
    relpath: str
    abspath: Path
    size_bytes: int
    mtime_epoch: float


UNTRACKED_INCLUDE_DIRS = ("src", "scripts", "tests", "config", "docs")


def _run(cmd: list[str], *, cwd: Path | None = None, check: bool = True) -> subprocess.CompletedProcess:
    return subprocess.run(
        cmd,
        cwd=str(cwd) if cwd else None,
        check=check,
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
    )


def _try_run_text(cmd: list[str], *, cwd: Path | None = None) -> str:
    try:
        proc = _run(cmd, cwd=cwd, check=True)
        return proc.stdout
    except subprocess.CalledProcessError as e:
        return (e.stdout or "") + ("\n" if e.stdout else "") + (e.stderr or "")


def _is_git_repo(repo_path: Path) -> bool:
    proc = _run(["git", "rev-parse", "--is-inside-work-tree"], cwd=repo_path, check=False)
    return proc.returncode == 0 and proc.stdout.strip() == "true"


def _git_root(repo_path: Path) -> Path:
    proc = _run(["git", "rev-parse", "--show-toplevel"], cwd=repo_path, check=True)
    return Path(proc.stdout.strip())


def _git_head(repo_root: Path) -> str | None:
    proc = _run(["git", "rev-parse", "HEAD"], cwd=repo_root, check=False)
    if proc.returncode != 0:
        return None
    return proc.stdout.strip() or None


def _git_ls_files(repo_root: Path) -> list[str]:
    proc = _run(["git", "ls-files", "-z"], cwd=repo_root, check=True)
    if not proc.stdout:
        return []
    return [p for p in proc.stdout.split("\0") if p]


def _read_text(path: Path, *, max_chars: int = 200_000) -> str:
    try:
        data = path.read_text(encoding="utf-8", errors="replace")
    except OSError:
        return ""
    if len(data) <= max_chars:
        return data
    return data[:max_chars] + "\n\n[TRUNCATED]\n"


def _write_text(path: Path, content: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding="utf-8")


def _format_bytes(n: int) -> str:
    v = float(n)
    for unit in ["B", "KB", "MB", "GB"]:
        if v < 1024 or unit == "GB":
            return f"{v:.1f}{unit}" if unit != "B" else f"{int(v)}{unit}"
        v /= 1024
    return f"{v:.1f}GB"


def _relpath(repo_root: Path, p: Path) -> str:
    try:
        return p.relative_to(repo_root).as_posix()
    except ValueError:
        return p.as_posix()


def _is_secret_path(relpath: str) -> bool:
    name = relpath.rsplit("/", 1)[-1]
    lowered = name.lower()
    if lowered in {".env", ".envrc"} or lowered.startswith(".env."):
        return True
    if lowered in {"id_rsa", "id_ed25519"}:
        return True
    if lowered.endswith((".pem", ".key", ".p12")):
        return True
    return False


def _has_excluded_part(relpath: str, excluded_dirs: set[str]) -> bool:
    parts = relpath.split("/")
    return any(part in excluded_dirs for part in parts)


def _should_exclude(relpath: str) -> tuple[bool, str]:
    excluded_dirs = {
        ".git",
        ".hg",
        ".svn",
        "__pycache__",
        ".pytest_cache",
        ".mypy_cache",
        ".ruff_cache",
        ".eggs",
        ".tox",
        ".venv",
        "venv",
        "node_modules",
        "dist",
        "build",
        ".idea",
        ".vscode",
    }
    excluded_toplevel = {"data", "outputs"}
    excluded_exts = {
        ".pyc",
        ".pyo",
        ".pyd",
        ".so",
        ".dylib",
        ".dll",
        ".parquet",
        ".feather",
        ".arrow",
        ".h5",
        ".hdf5",
        ".npz",
        ".npy",
        ".pt",
        ".pth",
        ".pkl",
        ".pickle",
        ".joblib",
        ".sqlite",
        ".db",
    }
    if not relpath or relpath.startswith("/") or relpath.startswith("../"):
        return True, "invalid-path"
    if relpath.startswith("quality_reports/model_review_artifacts/"):
        return True, "self-artifacts"
    if _is_secret_path(relpath):
        return True, "secret-path"
    toplevel = relpath.split("/", 1)[0]
    if toplevel in excluded_toplevel:
        return True, f"excluded-dir:{toplevel}"
    if _has_excluded_part(relpath, excluded_dirs):
        return True, "excluded-dir"
    ext = Path(relpath).suffix.lower()
    if ext in excluded_exts:
        return True, f"excluded-ext:{ext}"
    return False, ""


def _freshness_warnings(repo_root: Path) -> list[str]:
    warnings: list[str] = []
    reports_dir = repo_root / "reports"
    if reports_dir.exists():
        for tex in reports_dir.rglob("*.tex"):
            if not tex.is_file():
                continue
            if tex.is_symlink():
                continue
            pdf = tex.with_suffix(".pdf")
            if pdf.exists() and pdf.is_file():
                if tex.stat().st_mtime > pdf.stat().st_mtime + 1:
                    warnings.append(f"Stale PDF: `{_relpath(repo_root, pdf)}` older than `{_relpath(repo_root, tex)}`")
    figures_dir = repo_root / "figures"
    if figures_dir.exists():
        for src in figures_dir.rglob("*"):
            if not src.is_file():
                continue
            if src.is_symlink():
                continue
            if src.suffix.lower() not in {".r", ".py", ".ipynb"}:
                continue
            for out_ext in [".pdf", ".png"]:
                out = src.with_suffix(out_ext)
                if out.exists() and out.is_file():
                    if src.stat().st_mtime > out.stat().st_mtime + 1:
                        warnings.append(
                            f"Stale figure: `{_relpath(repo_root, out)}` older than `{_relpath(repo_root, src)}`"
                        )
    return warnings


def _find_latest_reply(artifact_root: Path, *, suffix: str) -> Path | None:
    if not artifact_root.exists():
        return None
    run_dirs = sorted(
        [p for p in artifact_root.iterdir() if p.is_dir() and p.name.endswith(suffix)],
        reverse=True,
    )
    for run_dir in run_dirs:
        candidate = run_dir / "MODEL_REPLY.md"
        if candidate.exists() and candidate.is_file():
            text = _read_text(candidate, max_chars=10_000).strip()
            if text:
                return candidate
    return None


def _find_previous_snapshot(artifact_root: Path, *, suffix: str) -> dict | None:
    if not artifact_root.exists():
        return None
    run_dirs = sorted(
        [p for p in artifact_root.iterdir() if p.is_dir() and p.name.endswith(suffix)],
        reverse=True,
    )
    for run_dir in run_dirs:
        snap = run_dir / "SNAPSHOT.json"
        if not snap.exists():
            continue
        try:
            return json.loads(snap.read_text(encoding="utf-8"))
        except Exception:
            continue
    return None


def _detect_feedback_model(reply_text: str, *, default_model: str) -> str:
    header_lines = reply_text.splitlines()[:60]
    header = "\n".join(header_lines)

    for line in header_lines:
        m = re.match(r"^\s*(model|source|feedback\s*source)\s*:\s*(.+?)\s*$", line, flags=re.IGNORECASE)
        if m:
            raw = m.group(2).strip()
            lowered = raw.lower()
            if "gpt" in lowered:
                return "GPT Pro"
            if "deep" in lowered or "gemini" in lowered:
                return "Deep Think"
            return raw[:80]

    lowered_header = header.lower()
    if "gpt pro" in lowered_header or "gptpro" in lowered_header:
        return "GPT Pro"
    if "deepthink" in lowered_header or "deep think" in lowered_header or "gemini" in lowered_header:
        return "Deep Think"

    return default_model


def _extract_file_references(reply_text: str, *, max_refs: int = 80) -> list[str]:
    pattern = re.compile(
        r"(?P<path>(?:[A-Za-z0-9_.-]+/)+[A-Za-z0-9_.-]+\.(?:py|md|toml|ya?ml|json|tex|r|sh|ipynb|csv))"
    )
    refs: list[str] = []
    seen: set[str] = set()
    for m in pattern.finditer(reply_text):
        p = m.group("path")
        if p in seen:
            continue
        seen.add(p)
        refs.append(p)
        if len(refs) >= max_refs:
            break
    return refs


def _extract_questions(reply_text: str, *, max_q: int = 40) -> list[str]:
    questions: list[str] = []
    for line in reply_text.splitlines():
        s = line.strip()
        if not s:
            continue
        if s.endswith("?") or s.lower().startswith(("q:", "question:")):
            s = re.sub(r"^([-*•]|\d+[.)])\s+", "", s).strip()
            if len(s) > 300:
                s = s[:300] + "…"
            questions.append(s)
        if len(questions) >= max_q:
            break
    return questions


def _extract_bullets(reply_text: str, *, max_items: int = 200) -> list[str]:
    bullets: list[str] = []
    for line in reply_text.splitlines():
        s = line.strip()
        if not s:
            continue
        if re.match(r"^([-*•]|\d+[.)])\s+", s):
            item = re.sub(r"^([-*•]|\d+[.)])\s+", "", s).strip()
            if not item:
                continue
            if len(item) > 400:
                item = item[:400] + "…"
            bullets.append(item)
        if len(bullets) >= max_items:
            break
    return bullets


def _extract_action_items(reply_text: str, *, max_items: int = 80) -> list[str]:
    verbs = (
        "fix",
        "add",
        "implement",
        "refactor",
        "test",
        "validate",
        "check",
        "document",
        "rename",
        "remove",
        "ensure",
        "consider",
        "measure",
        "benchmark",
        "audit",
        "compare",
        "recompute",
        "re-run",
    )
    items: list[str] = []
    for b in _extract_bullets(reply_text, max_items=400):
        lowered = b.lower()
        if any(v in lowered for v in verbs) or lowered.startswith(("should ", "recommend ", "i recommend ")):
            items.append(b)
        if len(items) >= max_items:
            break
    return items


def _categorize_points(points: list[str], *, max_per_bucket: int = 40) -> dict[str, list[str]]:
    buckets = {"correctness": [], "econ_econometrics": [], "engineering": [], "roadmap": [], "other": []}
    for p in points:
        l = p.lower()
        if any(k in l for k in ["leak", "look-ahead", "look ahead", "bias", "incorrect", "wrong", "bug", "unit", "sign"]):
            buckets["correctness"].append(p)
        elif any(
            k in l
            for k in [
                "cointegration",
                "johansen",
                "half-life",
                "half life",
                "ou ",
                "pca",
                "dsr",
                "deflated",
                "sharpe",
                "sortino",
                "calmar",
                "walk-forward",
                "oos",
                "out-of-sample",
                "transaction cost",
                "slippage",
                "econometric",
                "microstructure",
            ]
        ):
            buckets["econ_econometrics"].append(p)
        elif any(k in l for k in ["test", "pytest", "ruff", "type", "doc", "refactor", "performance", "api", "interface"]):
            buckets["engineering"].append(p)
        elif any(k in l for k in ["roadmap", "next", "later", "future", "extend", "improve", "add ", "consider "]):
            buckets["roadmap"].append(p)
        else:
            buckets["other"].append(p)

    for k in list(buckets.keys()):
        buckets[k] = buckets[k][:max_per_bucket]
    return buckets


def _meeting_notes_md(
    *,
    model_name: str,
    generated_at: str,
    repo_root: Path,
    run_dir: Path,
    reply_path: Path,
    reply_text: str,
    snapshot: dict | None,
) -> str:
    bullets = _extract_bullets(reply_text)
    actions = _extract_action_items(reply_text)
    questions = _extract_questions(reply_text)
    refs = _extract_file_references(reply_text)
    buckets = _categorize_points(bullets)

    snap_lines = []
    if snapshot:
        snap_lines.append(f"Review bundle timestamp: `{snapshot.get('timestamp')}`")
        snap_lines.append(f"Git HEAD at bundle time: `{snapshot.get('git_head')}`")
        snap_lines.append(f"Dirty at bundle time: `{snapshot.get('git_dirty')}`")
        if snapshot.get("focus"):
            snap_lines.append(f"Focus used: {snapshot.get('focus')!r}")
    if not snap_lines:
        snap_lines.append("(no snapshot metadata found)")

    def fmt_list(items: list[str], *, max_items: int = 20) -> str:
        if not items:
            return "- (none)"
        clipped = items[:max_items]
        s = "\n".join([f"- {x}" for x in clipped])
        if len(items) > max_items:
            s += f"\n- ... ({len(items) - max_items} more)"
        return s

    def fmt_checklist(items: list[str], *, max_items: int = 40) -> str:
        if not items:
            return "- [ ] (none extracted)"
        clipped = items[:max_items]
        s = "\n".join([f"- [ ] {x}" for x in clipped])
        if len(items) > max_items:
            s += f"\n- [ ] ... ({len(items) - max_items} more)"
        return s

    parts: list[str] = []
    parts.append("# Meeting Notes — External Model Feedback\n\n")
    parts.append(f"- Generated at: {generated_at}\n")
    parts.append(f"- Feedback model: {model_name}\n")
    parts.append(f"- Repo: `{repo_root}`\n")
    parts.append(f"- Review run folder: `{run_dir.name}`\n")
    parts.append(f"- Reply file: `{reply_path.name}`\n\n")

    parts.append("## Review context (from bundle snapshot)\n")
    parts.append(fmt_list(snap_lines, max_items=20) + "\n\n")

    parts.append("## Executive summary (extracted highlights)\n")
    parts.append(fmt_list(bullets, max_items=12) + "\n\n")

    parts.append("## Detailed notes (grouped)\n\n")
    parts.append("### Correctness / leakage / units\n")
    parts.append(fmt_list(buckets["correctness"], max_items=40) + "\n\n")

    parts.append("### Economics / econometrics / theory\n")
    parts.append(fmt_list(buckets["econ_econometrics"], max_items=40) + "\n\n")

    parts.append("### Engineering / tests / quality\n")
    parts.append(fmt_list(buckets["engineering"], max_items=40) + "\n\n")

    parts.append("### Roadmap / extensions\n")
    parts.append(fmt_list(buckets["roadmap"], max_items=40) + "\n\n")

    parts.append("### Other\n")
    parts.append(fmt_list(buckets["other"], max_items=40) + "\n\n")

    parts.append("## Action items (editable checklist)\n")
    parts.append(fmt_checklist(actions, max_items=60) + "\n\n")

    parts.append("## Open questions (from model)\n")
    parts.append(fmt_list(questions, max_items=30) + "\n\n")

    parts.append("## Files/modules referenced (best-effort)\n")
    parts.append(fmt_list([f"`{r}`" for r in refs], max_items=60) + "\n\n")

    parts.append("## Link\n")
    parts.append(f"- Raw model reply: `{reply_path}`\n")
    return "".join(parts)


def _maybe_write_meeting_notes(
    reply_path: Path,
    reply_text: str,
    *,
    repo_root: Path,
    default_model: str,
) -> Path | None:
    run_dir = reply_path.parent
    notes_path = run_dir / "MEETING_NOTES.md"

    try:
        reply_mtime = reply_path.stat().st_mtime
        notes_mtime = notes_path.stat().st_mtime if notes_path.exists() else -1
        if notes_mtime >= reply_mtime:
            return notes_path
    except OSError:
        pass

    snapshot_path = run_dir / "SNAPSHOT.json"
    snapshot = None
    if snapshot_path.exists():
        try:
            snapshot = json.loads(snapshot_path.read_text(encoding="utf-8"))
        except Exception:
            snapshot = None

    model_name = _detect_feedback_model(reply_text, default_model=default_model)
    generated_at = dt.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    notes = _meeting_notes_md(
        model_name=model_name,
        generated_at=generated_at,
        repo_root=repo_root,
        run_dir=run_dir,
        reply_path=reply_path,
        reply_text=reply_text,
        snapshot=snapshot,
    )
    _write_text(notes_path, notes)
    return notes_path


def _tree(repo_root: Path, *, max_depth: int = 4, max_entries: int = 800) -> str:
    lines: list[str] = []
    count = 0

    def walk(dir_path: Path, depth: int) -> None:
        nonlocal count
        if depth > max_depth or count >= max_entries:
            return
        try:
            entries = sorted(dir_path.iterdir(), key=lambda p: (not p.is_dir(), p.name.lower()))
        except OSError:
            return
        for p in entries:
            if p.is_symlink():
                rel = _relpath(repo_root, p)
                exclude, _ = _should_exclude(rel)
                if exclude:
                    continue
                indent = "  " * depth
                lines.append(f"{indent}- {p.name}@")
                count += 1
                if count >= max_entries:
                    lines.append(f"{indent}- ... (tree truncated)")
                continue

            rel = _relpath(repo_root, p)
            exclude, _ = _should_exclude(rel)
            if exclude:
                continue
            indent = "  " * depth
            lines.append(f"{indent}- {p.name}{'/' if p.is_dir() else ''}")
            count += 1
            if count >= max_entries:
                lines.append(f"{indent}- ... (tree truncated)")
                return
            if p.is_dir():
                walk(p, depth + 1)

    walk(repo_root, 0)
    return "\n".join(lines)


def _python_outline(text: str) -> list[str]:
    try:
        tree = ast.parse(text)
    except Exception:
        return []
    items: list[str] = []
    for node in tree.body:
        if isinstance(node, ast.ClassDef):
            items.append(f"class {node.name}")
        elif isinstance(node, ast.FunctionDef):
            items.append(f"def {node.name}()")
        elif isinstance(node, ast.AsyncFunctionDef):
            items.append(f"async def {node.name}()")
    return items[:60]


def _code_fence_lang(path: Path) -> str:
    ext = path.suffix.lower()
    return {
        ".py": "python",
        ".md": "markdown",
        ".toml": "toml",
        ".yaml": "yaml",
        ".yml": "yaml",
        ".json": "json",
        ".tex": "tex",
        ".r": "r",
        ".sh": "bash",
    }.get(ext, "")


def _focus_tokens(focus: str | None) -> set[str]:
    if not focus:
        return set()
    toks = {t.lower() for t in re.split(r"[^a-zA-Z0-9_]+", focus) if len(t) >= 4}
    return toks


def _score_path(relpath: str, size_bytes: int, focus_toks: set[str]) -> float:
    p = relpath.lower()
    name = p.rsplit("/", 1)[-1]
    score = 0.0

    if name.startswith("readme"):
        score += 1000
    if name in {"claude.md", "agents.md"}:
        score += 950
    if name in {
        "pyproject.toml",
        "setup.py",
        "requirements.txt",
        "environment.yml",
        "environment.yaml",
        "package.json",
        "cargo.toml",
        "go.mod",
    }:
        score += 900

    if p.startswith("config/"):
        score += 850
        if "default" in name:
            score += 50

    if p.startswith(("scripts/", "bin/")):
        score += 800

    if p.startswith(("src/", "lib/", "app/")):
        score += 750

    if p.startswith("tests/"):
        score += 350

    # Keyword-ish filename hints
    for kw, bonus in [
        ("main", 40),
        ("runner", 40),
        ("train", 30),
        ("eval", 30),
        ("backtest", 30),
        ("env", 25),
        ("agent", 25),
        ("portfolio", 20),
        ("cointegration", 20),
        ("feature", 20),
    ]:
        if kw in name:
            score += bonus

    # Focus token boosts (path-only; cheap and safe)
    if focus_toks:
        for t in focus_toks:
            if t in p:
                score += 25

    # Prefer “medium-sized” files: too tiny often uninformative, too huge bloats context
    kb = size_bytes / 1024
    score += min(80.0, max(0.0, (kb - 1.0) * 0.5))
    score -= min(120.0, max(0.0, (kb - 200.0) * 0.2))

    return score


def _snip_text(text: str, *, max_lines_head: int = 220, max_lines_tail: int = 120, max_chars: int = 40_000) -> str:
    if len(text) <= max_chars:
        return text
    lines = text.splitlines()
    head = lines[:max_lines_head]
    tail = lines[-max_lines_tail:] if len(lines) > max_lines_head else []
    combined = head + ["", "... [snip] ...", ""] + tail if tail else head
    out = "\n".join(combined)
    if len(out) > max_chars:
        out = out[:max_chars] + "\n\n[TRUNCATED]\n"
    return out


def _upload_attachment_name(relpath: str) -> str:
    """Create a flat, file-picker-friendly name while keeping uniqueness."""
    name = relpath.replace("/", "__")
    name = re.sub(r"[^A-Za-z0-9_.-]+", "_", name).strip("_")
    if len(name) <= 180:
        return name

    ext = Path(relpath).suffix
    digest = hashlib.sha1(relpath.encode("utf-8", errors="ignore")).hexdigest()[:10]
    stem = re.sub(r"[^A-Za-z0-9_.-]+", "_", Path(relpath).stem).strip("_")
    stem = stem[:120] if stem else "attachment"
    return f"{stem}__{digest}{ext}"


def _build_upload_bundle(
    *,
    repo_root: Path,
    run_dir: Path,
    recommended_attachments: list[dict],
) -> dict:
    """Copy prompt/context + recommended attachments into a single upload folder."""
    to_upload = run_dir / "to_upload"
    attachments_dir = to_upload / "attachments"
    to_upload.mkdir(parents=True, exist_ok=True)
    attachments_dir.mkdir(parents=True, exist_ok=True)

    # Copy prompt/context for convenience (some UIs prefer uploading files).
    for name in ("PROMPT_deepthink-review.md", "CONTEXT_deepthink-review.md"):
        src = run_dir / name
        if src.exists() and src.is_file() and not src.is_symlink():
            shutil.copy2(src, to_upload / name)

    copied: list[dict] = []
    errors: list[dict] = []
    for a in recommended_attachments:
        rel = a.get("relpath")
        if not rel:
            continue
        src = repo_root / rel
        if not src.exists() or not src.is_file() or src.is_symlink():
            errors.append({"relpath": rel, "reason": "missing-or-nonfile-or-symlink"})
            continue
        dest_name = _upload_attachment_name(rel)
        dest = attachments_dir / dest_name
        try:
            shutil.copy2(src, dest)
            copied.append(
                {
                    "relpath": rel,
                    "copied_as": f"attachments/{dest_name}",
                    "size_bytes": int(dest.stat().st_size),
                }
            )
        except OSError as e:
            errors.append({"relpath": rel, "reason": f"copy-failed:{type(e).__name__}"})

    mapping = {"copied": copied, "errors": errors}
    _write_text(to_upload / "ATTACHMENTS_MAP.json", json.dumps(mapping, indent=2) + "\n")

    md_lines = ["# Deep Think Upload Bundle\n\n"]
    md_lines.append(f"- Run dir: `{run_dir}`\n")
    md_lines.append(f"- Upload folder: `{to_upload}`\n\n")
    md_lines.append("## Files to upload\n")
    md_lines.append(f"- `{to_upload / 'CONTEXT_deepthink-review.md'}`\n")
    if copied:
        md_lines.append("\n## Recommended attachments (copied)\n")
        for item in copied:
            md_lines.append(f"- `{to_upload / item['copied_as']}` (from `{item['relpath']}`)\n")
    if errors:
        md_lines.append("\n## Copy errors\n")
        for item in errors:
            md_lines.append(f"- `{item['relpath']}`: {item['reason']}\n")
    _write_text(to_upload / "README.md", "".join(md_lines))

    return {"to_upload_dir": str(to_upload), "copied": copied, "errors": errors}


def _discover_artifacts(repo_root: Path) -> list[dict]:
    allow_dirs = ["reports", "figures", "quality_reports"]
    allow_exts = {".pdf", ".png", ".jpg", ".jpeg", ".svg"}
    artifacts: list[dict] = []
    for d in allow_dirs:
        base = repo_root / d
        if not base.exists():
            continue
        for root, dirs, files in os.walk(base, topdown=True, followlinks=False):
            # Prune self artifacts
            dirs[:] = [x for x in dirs if x != "model_review_artifacts"]
            for name in files:
                p = Path(root) / name
                if p.is_symlink() or not p.is_file():
                    continue
                rel = _relpath(repo_root, p)
                if rel.startswith("quality_reports/model_review_artifacts/"):
                    continue
                if _is_secret_path(rel):
                    continue
                if p.suffix.lower() not in allow_exts:
                    continue
                st = p.stat()
                artifacts.append({"relpath": rel, "size_bytes": st.st_size, "mtime_epoch": st.st_mtime})
    return sorted(artifacts, key=lambda a: a["mtime_epoch"], reverse=True)


def _recommend_attachments(artifacts: list[dict], *, max_files: int = 8) -> list[dict]:
    # Prefer the most recent report PDFs, then recent figure PDFs/PNGs, then anything else.
    reports = [a for a in artifacts if a["relpath"].startswith("reports/") and a["relpath"].lower().endswith(".pdf")]
    figs = [a for a in artifacts if a["relpath"].startswith("figures/")]
    others = [a for a in artifacts if a not in reports and a not in figs]

    rec: list[dict] = []
    rec.extend(reports[: min(3, max_files)])
    if len(rec) < max_files:
        rec.extend(figs[: max_files - len(rec)])
    if len(rec) < max_files:
        rec.extend(others[: max_files - len(rec)])

    return rec[:max_files]


def _build_context(
    *,
    repo_root: Path,
    timestamp: str,
    git_head: str | None,
    git_dirty: bool | None,
    focus: str | None,
    tracked_files: list[TrackedFile],
    omitted: list[dict],
    previous_reply: str | None,
    changes_summary: str | None,
    artifacts: list[dict],
    recommended_attachments: list[dict],
    freshness: list[str],
    max_context_bytes: int,
) -> tuple[str, list[dict]]:
    out_lines: list[str] = []
    used_bytes = 0
    omitted_due_to_cap: list[dict] = []

    def add(section: str) -> None:
        nonlocal used_bytes
        out_lines.append(section)
        used_bytes += len(section.encode("utf-8", errors="replace"))

    repo_name = repo_root.name or "repo"
    add(f"# DeepThink Context Bundle — {repo_name} — {timestamp}\n")
    add("This file is generated for a web model that cannot ingest a zip/folder. It contains repo metadata and curated snippets.\n\n")
    add("## Snapshot\n")
    add(f"- Repo root: `{repo_root}`\n")
    add(f"- Git HEAD: `{git_head or 'N/A'}`\n")
    add(f"- Dirty working tree: `{git_dirty}`\n\n")

    if focus and focus.strip():
        add("## Focus (user-specified)\n")
        add(f"{focus.strip()}\n\n")
    else:
        add("## Focus\nFull review.\n\n")

    if previous_reply:
        add("## Previous Model Reply (for iteration)\n")
        prev = previous_reply.strip()
        if len(prev) > 40_000:
            prev = prev[:40_000] + "\n\n[TRUNCATED]\n"
        add(prev + "\n\n")

    if changes_summary and changes_summary.strip():
        add("## Changes Since Last Run (auto-detected)\n")
        add("```text\n" + changes_summary.strip() + "\n```\n\n")

    add("## Directory Tree (filtered)\n")
    add("```text\n" + _tree(repo_root) + "\n```\n\n")

    add("## Git Metadata\n")
    add("```text\n" + _try_run_text(["git", "status", "--porcelain=v1", "-b"], cwd=repo_root).strip() + "\n```\n\n")
    add("```text\n" + _try_run_text(["git", "log", "-20", "--oneline", "--decorate"], cwd=repo_root).strip() + "\n```\n\n")
    add("```text\n" + _try_run_text(["git", "diff", "--stat"], cwd=repo_root).strip() + "\n```\n\n")

    add("## Freshness Warnings\n")
    if freshness:
        add("- " + "\n- ".join(freshness) + "\n\n")
    else:
        add("- (none detected)\n\n")

    add("## Artifacts Inventory (recent first)\n")
    if artifacts:
        for a in artifacts[:50]:
            add(f"- `{a['relpath']}` ({_format_bytes(a['size_bytes'])})\n")
        if len(artifacts) > 50:
            add(f"- ... ({len(artifacts) - 50} more)\n")
        add("\n")
    else:
        add("- (none found)\n\n")

    add("## Recommended Attachments (aim to stay ≤ 10 files total)\n")
    if recommended_attachments:
        for a in recommended_attachments:
            add(f"- `{a['relpath']}` ({_format_bytes(a['size_bytes'])})\n")
        add("\n")
    else:
        add("- (none)\n\n")

    add("## Key Files (snippets)\n")
    add(
        "Notes:\n"
        "- Snippets are truncated to control size.\n"
        "- File paths are repo-relative.\n\n"
    )

    # Add snippets until cap.
    for tf in tracked_files:
        if used_bytes >= max_context_bytes:
            omitted_due_to_cap.append({"relpath": tf.relpath, "reason": "context-size-cap"})
            continue

        header = f"### `{tf.relpath}` ({_format_bytes(tf.size_bytes)})\n"
        text = _read_text(tf.abspath, max_chars=300_000)
        outline = ""
        if tf.abspath.suffix.lower() == ".py":
            ol = _python_outline(text)
            if ol:
                outline = "\nTop-level defs:\n" + "\n".join([f"- {x}" for x in ol]) + "\n"

        snippet = _snip_text(text)
        lang = _code_fence_lang(tf.abspath)
        block = header + outline + f"\n```{lang}\n{snippet}\n```\n\n"

        if used_bytes + len(block.encode("utf-8", errors="replace")) > max_context_bytes:
            omitted_due_to_cap.append({"relpath": tf.relpath, "reason": "context-size-cap"})
            continue

        add(block)

    add("## Omitted (policy exclusions)\n")
    add(f"- {len(omitted)} files omitted by exclusion policy (see MANIFEST.json).\n\n")

    if omitted_due_to_cap:
        add("## Omitted (context size cap)\n")
        add("- " + "\n- ".join([f"`{x['relpath']}`" for x in omitted_due_to_cap[:200]]) + "\n")
        if len(omitted_due_to_cap) > 200:
            add(f"- ... ({len(omitted_due_to_cap) - 200} more)\n")
        add("\n")

    return "".join(out_lines), omitted_due_to_cap


def _prompt_md(
    *,
    repo_name: str,
    timestamp: str,
    git_head: str | None,
    git_dirty: bool | None,
    focus: str | None,
    previous_reply: str | None,
    changes_summary: str | None,
) -> str:
    focus_block = (
        f"\n## Focus (user-specified)\n{focus.strip()}\n" if focus and focus.strip() else "\n## Focus\nFull review.\n"
    )
    prev_block = ""
    if previous_reply:
        prev = previous_reply.strip()
        if len(prev) > 40_000:
            prev = prev[:40_000] + "\n\n[TRUNCATED]\n"
        prev_block = "\n## Previous Model Reply (for iteration)\n" + prev + "\n"
    changes_block = ""
    if changes_summary and changes_summary.strip():
        changes_block = "\n## Changes Since Last Run (auto-detected)\n```text\n" + changes_summary.strip() + "\n```\n"

    return textwrap.dedent(
        f"""\
        # Codebase Review Request — {repo_name} (Deep Think) — {timestamp}

        You will receive:
        - `CONTEXT_deepthink-review.md` (repo metadata + curated code snippets)
        - Optional attachments (PDF reports/figures/metrics) recommended in the context file

        **Hard requirements:**
        1. Read the full context file.
        2. Explain plainly: no jargon, no unexplained acronyms. Use concrete examples.
        3. Validate claims against any attached artifacts (PDF reports/figures/metrics). If results and code disagree, say so.
        4. Be explicit about what you can/can’t infer from the provided snippets.

        ## Snapshot
        - Git HEAD: `{git_head or 'N/A'}`
        - Dirty working tree: `{git_dirty}`

        {focus_block}{prev_block}{changes_block}
        ## Deliverables (produce in this order)

        ### 1) Layman Walkthrough (succinct, example-driven)
        - What problem this project solves and how it works end-to-end.
        - The “data → signals → decisions → evaluation” flow.
        - A minimal worked example (toy numbers) that mirrors the project’s logic.

        ### 2) Technical Validation (meticulous)
        - Correctness: leakage, indexing, units, signs, costs, evaluation methodology.
        - Reproducibility: config hygiene, determinism, brittleness.
        - Robustness: missing data, edge cases, implicit assumptions.
        - Testing: most important tests missing; what to add first.

        ### 3) Economic / Econometric / Theoretical Validation
        - State assumptions clearly (cointegration stability, regime shifts, microstructure, etc.).
        - Validate econometrics and multiple testing controls.
        - Validate RL framing: state/action constraints, reward definition, risk scaling, stationarity.
        - Statistical validity: walk-forward design, OOS controls, metrics appropriateness.

        ### 4) Advancement Roadmap (actionable + structured)
        Provide BOTH:
        - **Theory upgrades**: complete math where needed (define variables, objective, constraints).
        - **Implementation plan**: concrete module structure + file-level change list.

        Calibrate granularity to the Focus section. If you propose a new framework/architecture, include a minimal API skeleton (classes/functions + responsibilities).

        ## Output format
        Use this structure exactly:
        1. Executive Summary (5–10 bullets)
        2. System Walkthrough (plain language)
        3. Findings — Critical / Major / Minor / Suggestions (with file references)
        4. Validation Against Artifacts (what you checked, mismatches)
        5. Roadmap (Now / Next / Later)
        6. Questions for the developer (only if genuinely blocking)
        """
    )


def main() -> int:
    parser = argparse.ArgumentParser(description="Generate a DeepThink-ready context bundle + prompt.")
    parser.add_argument("--repo", type=str, default=".", help="Path inside the target repo (default: .).")
    parser.add_argument("--focus", type=str, default=None, help="Optional focus request embedded into the prompt.")
    parser.add_argument(
        "--max-context-kb",
        type=int,
        default=900,
        help="Maximum size of CONTEXT markdown (KB, approximate).",
    )
    parser.add_argument(
        "--strict-freshness",
        action="store_true",
        help="Exit non-zero if stale artifacts are detected (e.g., .tex newer than .pdf).",
    )
    parser.add_argument(
        "--out-dir",
        type=str,
        default=None,
        help="Override output directory (default: <repo>/quality_reports/model_review_artifacts/<timestamp>_deepthink-review).",
    )
    args = parser.parse_args()

    repo_path = Path(args.repo).resolve()
    if not repo_path.exists():
        print(f"ERROR: repo path does not exist: {repo_path}", file=sys.stderr)
        return 2

    if _is_git_repo(repo_path):
        repo_root = _git_root(repo_path)
        tracked_relpaths = _git_ls_files(repo_root)
    else:
        repo_root = repo_path
        tracked_relpaths = []

    tracked_set = set(tracked_relpaths)

    timestamp = dt.datetime.now().strftime("%Y-%m-%d_%H%M%S")
    artifact_root = repo_root / "quality_reports" / "model_review_artifacts"
    run_dir = Path(args.out_dir).resolve() if args.out_dir else (artifact_root / f"{timestamp}_deepthink-review")
    run_dir.mkdir(parents=True, exist_ok=True)

    git_head = _git_head(repo_root) if _is_git_repo(repo_root) else None
    git_status = _try_run_text(["git", "status", "--porcelain=v1", "-b"], cwd=repo_root) if git_head else ""
    git_dirty = bool(git_status.strip()) if git_head else None

    omitted: list[dict] = []
    tracked_files: list[TrackedFile] = []

    # Filter tracked files and collect metadata for scoring.
    focus_toks = _focus_tokens(args.focus)
    text_exts = {
        ".py",
        ".md",
        ".toml",
        ".yaml",
        ".yml",
        ".json",
        ".txt",
        ".ini",
        ".cfg",
        ".tex",
        ".r",
        ".sh",
    }

    scored: list[tuple[float, TrackedFile]] = []
    def add_candidate(rel: str, *, tracked: bool) -> None:
        exclude, reason = _should_exclude(rel)
        if exclude:
            omitted.append({"relpath": rel, "reason": reason, "tracked": tracked})
            return
        abspath = repo_root / rel
        if not abspath.exists() or not abspath.is_file():
            omitted.append({"relpath": rel, "reason": "missing-on-disk", "tracked": tracked})
            return
        if abspath.is_symlink():
            omitted.append({"relpath": rel, "reason": "symlink", "tracked": tracked})
            return
        if abspath.suffix.lower() not in text_exts:
            return
        st = abspath.stat()
        tf = TrackedFile(relpath=rel, abspath=abspath, size_bytes=st.st_size, mtime_epoch=st.st_mtime)
        score = _score_path(rel, st.st_size, focus_toks)
        scored.append((score, tf))

    for rel in tracked_relpaths:
        add_candidate(rel, tracked=True)

    # Also include untracked-but-relevant code/docs when the working tree is dirty.
    for d in UNTRACKED_INCLUDE_DIRS:
        base = repo_root / d
        if not base.exists():
            continue
        for root, dirs, files in os.walk(base, topdown=True, followlinks=False):
            dirs[:] = [x for x in dirs if x != "model_review_artifacts"]
            for name in files:
                p = Path(root) / name
                if p.is_symlink() or not p.is_file():
                    continue
                rel = _relpath(repo_root, p)
                if rel in tracked_set:
                    continue
                add_candidate(rel, tracked=False)

    # Select top-N key files for snippets.
    scored.sort(key=lambda x: x[0], reverse=True)
    key_files = [tf for _score, tf in scored[:30]]

    artifacts = _discover_artifacts(repo_root)
    recommended_attachments = _recommend_attachments(artifacts, max_files=8)
    freshness = _freshness_warnings(repo_root)

    if args.strict_freshness and freshness:
        _write_text(run_dir / "FRESHNESS_WARNINGS.md", "- " + "\n- ".join(freshness) + "\n")
        print("ERROR: freshness warnings detected; refusing to generate in strict mode.", file=sys.stderr)
        print(f"See: {run_dir / 'FRESHNESS_WARNINGS.md'}", file=sys.stderr)
        return 3

    previous_reply_path = _find_latest_reply(artifact_root, suffix="_deepthink-review")
    previous_reply = _read_text(previous_reply_path, max_chars=140_000) if previous_reply_path else None
    previous_snapshot = _find_previous_snapshot(artifact_root, suffix="_deepthink-review")
    changes_summary = None
    if previous_snapshot and git_head and previous_snapshot.get("git_head") and previous_snapshot.get("git_head") != git_head:
        prev_sha = previous_snapshot.get("git_head")
        changes_summary = _try_run_text(["git", "diff", "--stat", f"{prev_sha}..{git_head}"], cwd=repo_root)

    # If the user pasted feedback into a previous run's MODEL_REPLY.md, generate meeting notes automatically.
    if previous_reply_path:
        reply_for_notes = _read_text(previous_reply_path, max_chars=400_000)
        if reply_for_notes.strip():
            _maybe_write_meeting_notes(
                previous_reply_path,
                reply_for_notes,
                repo_root=repo_root,
                default_model="Deep Think",
            )

    max_context_bytes = int(args.max_context_kb * 1024)
    context_md, omitted_due_to_cap = _build_context(
        repo_root=repo_root,
        timestamp=timestamp,
        git_head=git_head,
        git_dirty=git_dirty,
        focus=args.focus,
        tracked_files=key_files,
        omitted=omitted,
        previous_reply=previous_reply,
        changes_summary=changes_summary,
        artifacts=artifacts,
        recommended_attachments=recommended_attachments,
        freshness=freshness,
        max_context_bytes=max_context_bytes,
    )
    _write_text(run_dir / "CONTEXT_deepthink-review.md", context_md)

    repo_name = repo_root.name or "repo"
    prompt = _prompt_md(
        repo_name=repo_name,
        timestamp=timestamp,
        git_head=git_head,
        git_dirty=git_dirty,
        focus=args.focus,
        previous_reply=previous_reply,
        changes_summary=changes_summary,
    )
    _write_text(run_dir / "PROMPT_deepthink-review.md", prompt)

    snapshot = {
        "timestamp": timestamp,
        "repo_root": str(repo_root),
        "git_head": git_head,
        "git_dirty": git_dirty,
        "focus": args.focus,
        "max_context_kb": args.max_context_kb,
    }
    _write_text(run_dir / "SNAPSHOT.json", json.dumps(snapshot, indent=2) + "\n")

    manifest = {
        "snapshot": snapshot,
        "key_files": [{"relpath": tf.relpath, "size_bytes": tf.size_bytes} for tf in key_files],
        "omitted_by_policy": omitted,
        "omitted_due_to_context_cap": omitted_due_to_cap,
        "freshness_warnings": freshness,
        "artifacts_inventory": artifacts,
        "recommended_attachments": recommended_attachments,
    }
    _write_text(run_dir / "MANIFEST.json", json.dumps(manifest, indent=2) + "\n")

    manifest_md = textwrap.dedent(
        f"""\
        # Manifest (deepthink-review)

        **Repo:** `{repo_root}`
        **Run dir:** `{run_dir}`
        **Timestamp:** {timestamp}
        **Git HEAD:** {git_head or "N/A"}
        **Dirty:** {git_dirty}

        ## Context
        - Key files included as snippets: {len(key_files)}
        - Omitted by policy: {len(omitted)}
        - Omitted by context size cap: {len(omitted_due_to_cap)}
        - Recommended attachments: {len(recommended_attachments)} (aiming to keep total attachments ≤ 10)

        See `MANIFEST.json` for full details.
        """
    )
    _write_text(run_dir / "MANIFEST.md", manifest_md)

    upload_md = ["# Upload Instructions (deepthink-review)\n"]
    upload_info = _build_upload_bundle(
        repo_root=repo_root,
        run_dir=run_dir,
        recommended_attachments=recommended_attachments,
    )
    to_upload = Path(upload_info["to_upload_dir"])

    upload_md.append("1) Paste this prompt into Deep Think:\n")
    upload_md.append(f"- `{(to_upload / 'PROMPT_deepthink-review.md')}`\n\n")
    upload_md.append("2) Paste/upload this context bundle:\n")
    upload_md.append(f"- `{(to_upload / 'CONTEXT_deepthink-review.md')}`\n\n")
    if upload_info["copied"]:
        upload_md.append("3) Attach the following artifacts (copied into one folder; keep total attachments ≤ 10):\n")
        for item in upload_info["copied"]:
            rel = item["relpath"]
            copied_as = item["copied_as"]
            upload_md.append(f"- `{to_upload / copied_as}` (from `{rel}`)\n")
        upload_md.append("\n")
    upload_md.append("4) Optional (iteration): after Deep Think replies, paste the reply into:\n")
    upload_md.append(f"- `{(run_dir / 'MODEL_REPLY.md')}`\n")
    _write_text(run_dir / "UPLOAD.md", "".join(upload_md))

    print(str(run_dir))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
