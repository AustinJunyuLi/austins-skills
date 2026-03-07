#!/usr/bin/env python3

from __future__ import annotations

import argparse
import dataclasses
import datetime as dt
import json
import os
import re
import shutil
import subprocess
import sys
import textwrap
import zipfile
from pathlib import Path
from typing import Iterable, Literal


ArtifactPriority = Literal["pinned", "high", "medium", "low"]

UNTRACKED_INCLUDE_DIRS = ("src", "scripts", "tests", "config", "docs")
UNTRACKED_TEXT_EXTS = {
    ".py",
    ".md",
    ".toml",
    ".yaml",
    ".yml",
    ".json",
    ".txt",
    ".ini",
    ".cfg",
    ".sh",
    ".r",
    ".tex",
}
MAX_UNTRACKED_FILE_BYTES = 1_000_000  # 1MB safety cap to avoid bundling accidental blobs


@dataclasses.dataclass(frozen=True)
class FileCandidate:
    relpath: str
    abspath: Path
    size_bytes: int
    mtime_epoch: float
    tracked: bool
    category: str
    artifact_priority: ArtifactPriority | None = None


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
    for unit in ["B", "KB", "MB", "GB"]:
        if n < 1024 or unit == "GB":
            return f"{n:.1f}{unit}" if unit != "B" else f"{n}{unit}"
        n /= 1024
    return f"{n:.1f}GB"


def _relpath(repo_root: Path, p: Path) -> str:
    try:
        return p.relative_to(repo_root).as_posix()
    except ValueError:
        return p.as_posix()


def _has_excluded_part(relpath: str, excluded_dirs: set[str]) -> bool:
    parts = relpath.split("/")
    return any(part in excluded_dirs for part in parts)


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


def _should_exclude_core(relpath: str) -> tuple[bool, str]:
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

    if not relpath or relpath.startswith("/"):
        return True, "invalid-path"
    if relpath.startswith("../"):
        return True, "outside-repo"
    if _is_secret_path(relpath):
        return True, "secret-path"
    if relpath.startswith("quality_reports/model_review_artifacts/"):
        return True, "self-artifacts"
    toplevel = relpath.split("/", 1)[0]
    if toplevel in excluded_toplevel:
        return True, f"excluded-dir:{toplevel}"
    if _has_excluded_part(relpath, excluded_dirs):
        return True, "excluded-dir"
    ext = Path(relpath).suffix.lower()
    if ext in excluded_exts:
        return True, f"excluded-ext:{ext}"
    return False, ""


def _artifact_priority(relpath: str) -> ArtifactPriority:
    if relpath.startswith("reports/Archive/"):
        return "low"
    if relpath.startswith("reports/"):
        return "high"
    if relpath.startswith("figures/"):
        return "medium"
    if relpath.startswith("quality_reports/"):
        return "low"
    return "low"


def _scan_untracked_core_files(
    repo_root: Path,
    *,
    tracked_set: set[str],
) -> tuple[list[FileCandidate], list[dict]]:
    """Collect untracked-but-relevant text files from common code directories.

    This is important when the working tree is dirty and new modules/tests
    haven’t been committed yet. We keep this conservative to avoid pulling in
    large blobs or contamination.
    """
    candidates: list[FileCandidate] = []
    omitted: list[dict] = []

    for d in UNTRACKED_INCLUDE_DIRS:
        base = repo_root / d
        if not base.exists():
            continue
        for root, dirs, files in os.walk(base, topdown=True, followlinks=False):
            # Avoid recursion into our own outputs.
            dirs[:] = [x for x in dirs if x != "model_review_artifacts"]
            for name in files:
                p = Path(root) / name
                if p.is_symlink() or not p.is_file():
                    continue
                rel = _relpath(repo_root, p)
                if rel in tracked_set:
                    continue
                exclude, reason = _should_exclude_core(rel)
                if exclude:
                    omitted.append({"relpath": rel, "reason": reason, "tracked": False})
                    continue
                ext = p.suffix.lower()
                if ext and ext not in UNTRACKED_TEXT_EXTS:
                    omitted.append({"relpath": rel, "reason": f"untracked-ext:{ext}", "tracked": False})
                    continue
                st = p.stat()
                if st.st_size > MAX_UNTRACKED_FILE_BYTES:
                    omitted.append(
                        {
                            "relpath": rel,
                            "reason": f"untracked-too-large:{_format_bytes(st.st_size)}",
                            "tracked": False,
                            "size_bytes": st.st_size,
                        }
                    )
                    continue
                candidates.append(
                    FileCandidate(
                        relpath=rel,
                        abspath=p,
                        size_bytes=st.st_size,
                        mtime_epoch=st.st_mtime,
                        tracked=False,
                        category="core_untracked",
                    )
                )

    return candidates, omitted


def _scan_allowlisted_artifacts(
    repo_root: Path,
    *,
    allow_dirs: list[str],
    allow_exts: set[str],
    tracked_set: set[str],
) -> list[FileCandidate]:
    candidates: list[FileCandidate] = []
    for allow_dir in allow_dirs:
        base = repo_root / allow_dir
        if not base.exists():
            continue
        for root, dirs, files in os.walk(base, topdown=True, followlinks=False):
            # Avoid recursion into our own outputs.
            dirs[:] = [d for d in dirs if d != "model_review_artifacts"]
            for name in files:
                p = Path(root) / name
                if p.is_symlink() or not p.is_file():
                    continue
                rel = _relpath(repo_root, p)
                if rel.startswith("quality_reports/model_review_artifacts/"):
                    continue
                if _is_secret_path(rel):
                    continue
                ext = p.suffix.lower()
                if ext not in allow_exts:
                    continue
                st = p.stat()
                candidates.append(
                    FileCandidate(
                        relpath=rel,
                        abspath=p,
                        size_bytes=st.st_size,
                        mtime_epoch=st.st_mtime,
                        tracked=rel in tracked_set,
                        category="artifact",
                        artifact_priority=_artifact_priority(rel),
                    )
                )
    return candidates


def _freshness_warnings(repo_root: Path) -> list[str]:
    warnings: list[str] = []

    # reports: foo.tex newer than foo.pdf
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
                    warnings.append(
                        f"Stale PDF: `{_relpath(repo_root, pdf)}` is older than `{_relpath(repo_root, tex)}`"
                    )

    # figures: foo.R/foo.py newer than foo.pdf/foo.png
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
                            f"Stale figure: `{_relpath(repo_root, out)}` is older than `{_relpath(repo_root, src)}`"
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
    # Prefer an explicit header near the top of the reply.
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
    # Best-effort path extraction: grabs things that look like repo-relative file paths.
    pattern = re.compile(
        r"(?P<path>(?:[A-Za-z0-9_.-]+/)+[A-Za-z0-9_.-]+\.(?:py|md|toml|ya?ml|json|tex|r|sh|ipynb|csv))"
    )
    refs = []
    seen = set()
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


def _copy_into_bundle(repo_root: Path, bundle_dir: Path, files: Iterable[FileCandidate]) -> None:
    for fc in files:
        if fc.abspath.is_symlink():
            continue
        dest = bundle_dir / fc.relpath
        dest.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(fc.abspath, dest)


def _zip_dir(src_dir: Path, zip_path: Path) -> None:
    if zip_path.exists():
        zip_path.unlink()
    with zipfile.ZipFile(
        zip_path,
        mode="w",
        compression=zipfile.ZIP_DEFLATED,
        compresslevel=9,
    ) as zf:
        for p in sorted(src_dir.rglob("*")):
            if not p.is_file():
                continue
            if p.is_symlink():
                continue
            arcname = p.relative_to(src_dir).as_posix()
            zf.write(p, arcname=arcname)


def _select_files(
    repo_root: Path,
    *,
    tracked_files: list[str],
    max_bytes: int,
) -> tuple[list[FileCandidate], list[dict], dict]:
    tracked_set = set(tracked_files)

    core: list[FileCandidate] = []
    tracked_artifacts: list[FileCandidate] = []
    omitted: list[dict] = []

    # 1) Core tracked files (always keep unless excluded)
    for rel in tracked_files:
        exclude, reason = _should_exclude_core(rel)
        if exclude:
            omitted.append({"relpath": rel, "reason": reason, "tracked": True})
            continue
        abspath = repo_root / rel
        if not abspath.exists() or not abspath.is_file():
            omitted.append({"relpath": rel, "reason": "missing-on-disk", "tracked": True})
            continue
        if abspath.is_symlink():
            omitted.append({"relpath": rel, "reason": "symlink", "tracked": True})
            continue
        st = abspath.stat()
        ext = Path(rel).suffix.lower()
        is_allow_dir = rel.startswith(("reports/", "figures/", "quality_reports/"))
        is_droppable_artifact = is_allow_dir and ext in {".pdf", ".png", ".jpg", ".jpeg", ".svg", ".csv", ".json"}
        if is_droppable_artifact:
            tracked_artifacts.append(
                FileCandidate(
                    relpath=rel,
                    abspath=abspath,
                    size_bytes=st.st_size,
                    mtime_epoch=st.st_mtime,
                    tracked=True,
                    category="artifact",
                    artifact_priority=_artifact_priority(rel),
                )
            )
        else:
            core.append(
                FileCandidate(
                    relpath=rel,
                    abspath=abspath,
                    size_bytes=st.st_size,
                    mtime_epoch=st.st_mtime,
                    tracked=True,
                    category="core",
                )
            )

    # 2) Allowlisted artifacts (tracked or not; we may drop some for size)
    allow_dirs = ["reports", "figures", "quality_reports"]
    allow_exts = {".pdf", ".png", ".jpg", ".jpeg", ".svg", ".md", ".tex", ".csv", ".json"}
    artifacts = _scan_allowlisted_artifacts(
        repo_root, allow_dirs=allow_dirs, allow_exts=allow_exts, tracked_set=tracked_set
    )

    # 2.5) Untracked but relevant core files (code/tests/config/docs additions)
    untracked_core, untracked_omitted = _scan_untracked_core_files(repo_root, tracked_set=tracked_set)
    core.extend(untracked_core)
    omitted.extend(untracked_omitted)

    # Merge tracked artifacts + scanned artifacts, dedup by relpath.
    merged_artifacts_by_rel: dict[str, FileCandidate] = {a.relpath: a for a in tracked_artifacts}
    for a in artifacts:
        merged_artifacts_by_rel.setdefault(a.relpath, a)
    core_relpaths = {f.relpath for f in core}
    artifact_candidates = [a for a in merged_artifacts_by_rel.values() if a.relpath not in core_relpaths]

    # Pin the most recent report PDF if available (tracked or untracked).
    report_pdfs = [
        a for a in artifact_candidates if a.relpath.startswith("reports/") and a.relpath.lower().endswith(".pdf")
    ]
    pinned: set[str] = set()
    if report_pdfs:
        newest = max(report_pdfs, key=lambda a: a.mtime_epoch)
        pinned.add(newest.relpath)
        artifact_candidates = [
            dataclasses.replace(a, artifact_priority="pinned") if a.relpath in pinned else a
            for a in artifact_candidates
        ]

    # Build final list with size policy.
    def total_size(files: list[FileCandidate]) -> int:
        return sum(f.size_bytes for f in files)

    final = core + artifact_candidates
    if total_size(final) <= max_bytes:
        return final, omitted, {"dropped_for_size": 0, "pinned": sorted(pinned)}

    # Drop artifacts first (untracked then tracked), lowest priority first, then largest.
    def drop_key(a: FileCandidate) -> tuple[int, int, float]:
        # lower is dropped earlier
        priority_rank = {"low": 0, "medium": 1, "high": 2, "pinned": 3}
        pr = priority_rank.get(a.artifact_priority or "low", 0)
        # Drop low priority first; within priority drop largest first; then drop oldest first.
        return (pr, -a.size_bytes, a.mtime_epoch)

    artifacts_sorted = sorted(artifact_candidates, key=drop_key)
    kept_artifacts: list[FileCandidate] = []
    dropped_for_size: list[FileCandidate] = []

    # Start by assuming we keep all, then drop from the front until it fits,
    # but never drop pinned.
    keep_set = {a.relpath for a in artifacts_sorted}
    pinned_set = pinned.copy()

    # Iteratively drop
    current = core + [a for a in artifacts_sorted if a.relpath in keep_set]
    for a in artifacts_sorted:
        if total_size(current) <= max_bytes:
            break
        if a.relpath in pinned_set:
            continue
        # drop it
        keep_set.discard(a.relpath)
        dropped_for_size.append(a)
        current = core + [x for x in artifacts_sorted if x.relpath in keep_set]

    kept_artifacts = [a for a in artifacts_sorted if a.relpath in keep_set]
    final = core + kept_artifacts

    for a in dropped_for_size:
        omitted.append(
            {
                "relpath": a.relpath,
                "reason": f"size-cap:{_format_bytes(max_bytes)}",
                "tracked": a.tracked,
                "size_bytes": a.size_bytes,
                "artifact_priority": a.artifact_priority,
            }
        )

    meta = {"dropped_for_size": len(dropped_for_size), "pinned": sorted(pinned_set)}
    return final, omitted, meta


def _manifest_md(
    *,
    repo_root: Path,
    run_dir: Path,
    snapshot: dict,
    included: list[FileCandidate],
    omitted: list[dict],
    max_bytes: int,
    size_meta: dict,
    freshness: list[str],
) -> str:
    included_size = sum(f.size_bytes for f in included)
    top = sorted(included, key=lambda f: f.size_bytes, reverse=True)[:20]
    return textwrap.dedent(
        f"""\
        # Bundle Manifest (gptpro-review)

        **Repo:** `{repo_root}`
        **Run dir:** `{run_dir}`
        **Timestamp:** {snapshot.get("timestamp")}
        **Git HEAD:** {snapshot.get("git_head") or "N/A"}
        **Dirty:** {snapshot.get("git_dirty")}
        **Zip size cap:** {_format_bytes(max_bytes)}
        **Included total:** {_format_bytes(included_size)} across {len(included)} files
        **Dropped for size:** {size_meta.get("dropped_for_size", 0)}
        **Pinned artifacts:** {", ".join(size_meta.get("pinned", [])) or "none"}

        ## Freshness warnings
        {("- " + "\n- ".join(freshness)) if freshness else "- (none detected)"}

        ## Largest included files (top 20)
        {("- " + "\n- ".join([f"`{f.relpath}` ({_format_bytes(f.size_bytes)})" for f in top])) if top else "- (none)"}

        ## Omitted files (count)
        - {len(omitted)}

        Notes:
        - See `MANIFEST.json` for full include/omit details.
        """
    )


def _prompt_md(
    *,
    repo_name: str,
    timestamp: str,
    focus: str | None,
    snapshot: dict,
    previous_reply: str | None,
    changes_summary: str | None,
) -> str:
    focus_block = (
        f"\n## Focus (user-specified)\n{focus.strip()}\n" if focus and focus.strip() else "\n## Focus\nFull review.\n"
    )
    prev_block = ""
    if previous_reply:
        prev_block = "\n## Previous Model Reply (for iteration)\n" + previous_reply.strip() + "\n"
    changes_block = ""
    if changes_summary and changes_summary.strip():
        changes_block = "\n## Changes Since Last Run (auto-detected)\n```text\n" + changes_summary.strip() + "\n```\n"

    return textwrap.dedent(
        f"""\
        # Codebase Review Request — {repo_name} (GPT Pro) — {timestamp}

        You are reviewing a repository snapshot provided as a **zip attachment** (`repo_bundle.zip`).

        **Hard requirements:**
        1. Read the entire zip contents (code + config + tests + results artifacts).
        2. Explain plainly: no jargon, no unexplained acronyms. Use concrete examples.
        3. Validate claims against included artifacts (PDF reports/figures/metrics). If results and code disagree, say so.
        4. Be explicit about what you can/can’t infer from the materials.

        ## Snapshot
        - Git HEAD: `{snapshot.get("git_head") or "N/A"}`
        - Dirty working tree: `{snapshot.get("git_dirty")}`

        {focus_block}{prev_block}{changes_block}
        ## Deliverables (produce in this order)

        ### 1) Layman Walkthrough (succinct, example-driven)
        - What problem this project solves and how it works end-to-end.
        - The “data → signals → decisions → evaluation” flow.
        - A minimal worked example (toy numbers) that mirrors the project’s logic.

        ### 2) Technical Validation (meticulous)
        - Correctness: data alignment, leakage, indexing, units, signs, transaction costs.
        - Reproducibility: determinism, seeding, config hygiene, brittleness.
        - Robustness: edge cases, missing data, roll handling, look-ahead risk.
        - Testing: gaps, missing invariants, what tests you’d add first.
        - Performance: any clear bottlenecks and safe refactors.

        ### 3) Economic / Econometric / Theoretical Validation
        - State assumptions clearly (market microstructure, cointegration stability, regime shifts, etc.).
        - Validate econometrics: cointegration tests, persistence logic, half-life estimation, multiple testing control.
        - Validate RL framing: state, action constraints, reward definition, risk targeting, stationarity concerns.
        - Statistical validity: walk-forward design, sample size, overfitting risk, appropriate metrics (incl. DSR if used).

        ### 4) Advancement Roadmap (actionable + structured)
        Provide BOTH:
        - **Theory upgrades**: complete math where needed (define variables, objective, constraints).
        - **Implementation plan**: concrete module structure + file-level changes.

        Calibrate granularity to the Focus section. If you propose a new framework/architecture, include a minimal API skeleton (classes/functions + responsibilities).

        ## Output format
        Use this structure exactly:
        1. Executive Summary (5–10 bullets)
        2. System Walkthrough (plain language)
        3. Findings — Critical / Major / Minor / Suggestions (each with file references)
        4. Validation Against Artifacts (what you checked, mismatches)
        5. Roadmap (Now / Next / Later)
        6. Questions for the developer (only if genuinely blocking)
        """
    )


def main() -> int:
    parser = argparse.ArgumentParser(description="Package repo + artifacts into a GPT Pro zip + prompt.")
    parser.add_argument("--repo", type=str, default=".", help="Path inside the target repo (default: .).")
    parser.add_argument("--focus", type=str, default=None, help="Optional focus request embedded into the prompt.")
    parser.add_argument("--max-mb", type=float, default=45.0, help="Target max zip size (MB).")
    parser.add_argument(
        "--strict-freshness",
        action="store_true",
        help="Exit non-zero if stale artifacts are detected (e.g., .tex newer than .pdf).",
    )
    parser.add_argument(
        "--out-dir",
        type=str,
        default=None,
        help="Override output directory (default: <repo>/quality_reports/model_review_artifacts/<timestamp>_gptpro-review).",
    )
    args = parser.parse_args()

    repo_path = Path(args.repo).resolve()
    if not repo_path.exists():
        print(f"ERROR: repo path does not exist: {repo_path}", file=sys.stderr)
        return 2

    if _is_git_repo(repo_path):
        repo_root = _git_root(repo_path)
        tracked_files = _git_ls_files(repo_root)
    else:
        repo_root = repo_path
        tracked_files = []

    timestamp = dt.datetime.now().strftime("%Y-%m-%d_%H%M%S")
    artifact_root = repo_root / "quality_reports" / "model_review_artifacts"
    run_dir = Path(args.out_dir).resolve() if args.out_dir else (artifact_root / f"{timestamp}_gptpro-review")
    bundle_dir = run_dir / "repo_bundle"
    context_dir = bundle_dir / ".context"

    run_dir.mkdir(parents=True, exist_ok=True)
    bundle_dir.mkdir(parents=True, exist_ok=True)
    context_dir.mkdir(parents=True, exist_ok=True)

    git_head = _git_head(repo_root) if _is_git_repo(repo_root) else None
    git_status = _try_run_text(["git", "status", "--porcelain=v1", "-b"], cwd=repo_root) if git_head else ""
    git_dirty = bool(git_status.strip()) if git_head else None

    max_bytes = int(args.max_mb * 1024 * 1024)

    included, omitted, size_meta = _select_files(repo_root, tracked_files=tracked_files, max_bytes=max_bytes)

    # Add context files into the bundle (these should always fit).
    _write_text(context_dir / "GIT_STATUS.txt", git_status)
    _write_text(context_dir / "GIT_LOG.txt", _try_run_text(["git", "log", "-20", "--oneline", "--decorate"], cwd=repo_root))
    _write_text(context_dir / "GIT_DIFF_STAT.txt", _try_run_text(["git", "diff", "--stat"], cwd=repo_root))
    diff_text = _try_run_text(["git", "diff"], cwd=repo_root)
    if len(diff_text) > 300_000:
        diff_text = diff_text[:300_000] + "\n\n[TRUNCATED]\n"
    _write_text(context_dir / "GIT_DIFF.patch", diff_text)

    # Optional: previous run info (reply + changes summary).
    previous_reply_path = _find_latest_reply(artifact_root, suffix="_gptpro-review")
    previous_reply = _read_text(previous_reply_path, max_chars=140_000) if previous_reply_path else None
    previous_snapshot = _find_previous_snapshot(artifact_root, suffix="_gptpro-review")
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
                default_model="GPT Pro",
            )

    freshness = _freshness_warnings(repo_root)
    if args.strict_freshness and freshness:
        _write_text(run_dir / "FRESHNESS_WARNINGS.md", "- " + "\n- ".join(freshness) + "\n")
        print("ERROR: freshness warnings detected; refusing to bundle in strict mode.", file=sys.stderr)
        print(f"See: {run_dir / 'FRESHNESS_WARNINGS.md'}", file=sys.stderr)
        return 3

    # Copy selected files.
    _copy_into_bundle(repo_root, bundle_dir, included)

    # Write manifest + snapshot.
    snapshot = {
        "timestamp": timestamp,
        "repo_root": str(repo_root),
        "git_head": git_head,
        "git_dirty": git_dirty,
        "focus": args.focus,
        "max_mb": args.max_mb,
    }
    (run_dir / "SNAPSHOT.json").write_text(json.dumps(snapshot, indent=2) + "\n", encoding="utf-8")

    manifest = {
        "snapshot": snapshot,
        "included": [
            {
                "relpath": f.relpath,
                "size_bytes": f.size_bytes,
                "mtime_epoch": f.mtime_epoch,
                "tracked": f.tracked,
                "category": f.category,
                "artifact_priority": f.artifact_priority,
            }
            for f in included
        ],
        "omitted": omitted,
        "freshness_warnings": freshness,
        "size_meta": size_meta,
    }
    (run_dir / "MANIFEST.json").write_text(json.dumps(manifest, indent=2) + "\n", encoding="utf-8")
    _write_text(
        run_dir / "MANIFEST.md",
        _manifest_md(
            repo_root=repo_root,
            run_dir=run_dir,
            snapshot=snapshot,
            included=included,
            omitted=omitted,
            max_bytes=max_bytes,
            size_meta=size_meta,
            freshness=freshness,
        ),
    )

    repo_name = repo_root.name or "repo"
    prompt = _prompt_md(
        repo_name=repo_name,
        timestamp=timestamp,
        focus=args.focus,
        snapshot=snapshot,
        previous_reply=previous_reply,
        changes_summary=changes_summary,
    )
    _write_text(run_dir / "PROMPT_gptpro-review.md", prompt)

    upload = textwrap.dedent(
        f"""\
        # Upload Instructions (gptpro-review)

        1) Upload this zip to GPT Pro:
        - `{(run_dir / 'repo_bundle.zip')}`

        2) Paste this prompt into GPT Pro:
        - `{(run_dir / 'PROMPT_gptpro-review.md')}`

        3) Optional (iteration):
        - After GPT Pro replies, paste the reply into:
          `{(run_dir / 'MODEL_REPLY.md')}`
        - Then re-run the skill to include the prior reply + diffs.

        Notes:
        - Inspect `{(run_dir / 'MANIFEST.md')}` before uploading to confirm what’s included/omitted.
        """
    )
    _write_text(run_dir / "UPLOAD.md", upload)

    # Zip.
    zip_path = run_dir / "repo_bundle.zip"
    _zip_dir(bundle_dir, zip_path)

    print(str(run_dir))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
