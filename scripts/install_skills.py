#!/usr/bin/env python3

from __future__ import annotations

import argparse
import shutil
import sys
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[1]
SKILLS_ROOT = REPO_ROOT / "skills"
MANIFEST_ROOT = REPO_ROOT / "manifests"
DEFAULT_DESTINATIONS = {
    "claude": Path.home() / ".claude" / "skills",
    "codex": Path.home() / ".codex" / "skills",
}
MANIFEST_CHOICES = ("global", "informal-bids", "all")
PLACEHOLDER = "{{SKILLS_ROOT}}"


class InstallError(RuntimeError):
    pass


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description=(
            "Install Austin's skills into a Codex CLI or Claude Code skills directory."
        )
    )
    parser.add_argument(
        "--target",
        required=True,
        choices=sorted(DEFAULT_DESTINATIONS),
        help="Tool to install for.",
    )
    parser.add_argument(
        "--manifest",
        required=True,
        choices=MANIFEST_CHOICES,
        help="Manifest name from manifests/<name>.txt.",
    )
    parser.add_argument(
        "--dest",
        type=Path,
        help="Override the destination skills root.",
    )
    parser.add_argument(
        "--force",
        action="store_true",
        help="Overwrite existing installed skill directories.",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Validate and print the install plan without copying files.",
    )
    return parser.parse_args()


def load_manifest(manifest_name: str) -> tuple[Path, list[str]]:
    manifest_path = MANIFEST_ROOT / f"{manifest_name}.txt"
    if not manifest_path.is_file():
        raise InstallError(f"manifest not found: {manifest_path}")

    skills: list[str] = []
    for raw_line in manifest_path.read_text(encoding="utf-8").splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#"):
            continue
        skills.append(line)

    if not skills:
        raise InstallError(f"manifest is empty: {manifest_path}")

    return manifest_path, skills


def resolve_destination(target: str, override: Path | None) -> Path:
    destination = override if override is not None else DEFAULT_DESTINATIONS[target]
    destination = destination.expanduser()
    return destination.resolve()


def validate_destination_root(destination_root: Path) -> None:
    if destination_root.exists() and not destination_root.is_dir():
        raise InstallError(
            f"destination exists and is not a directory: {destination_root}"
        )


def validate_skills(skill_names: list[str]) -> list[Path]:
    missing: list[str] = []
    sources: list[Path] = []

    for skill_name in skill_names:
        source_dir = SKILLS_ROOT / skill_name
        skill_md = source_dir / "SKILL.md"
        if not source_dir.is_dir():
            missing.append(skill_name)
            continue
        if not skill_md.is_file():
            raise InstallError(f"missing SKILL.md for skill: {skill_name}")
        sources.append(source_dir)

    if missing:
        missing_list = ", ".join(sorted(missing))
        raise InstallError(f"skill directories missing from repo: {missing_list}")

    return sources


def remove_existing(path: Path) -> None:
    if not path.exists():
        return
    if path.is_dir() and not path.is_symlink():
        shutil.rmtree(path)
        return
    path.unlink()


def rewrite_placeholder(skill_md_path: Path, destination_root: Path) -> None:
    contents = skill_md_path.read_text(encoding="utf-8")
    if PLACEHOLDER not in contents:
        return
    updated = contents.replace(PLACEHOLDER, str(destination_root))
    skill_md_path.write_text(updated, encoding="utf-8")


def install_skill(
    source_dir: Path,
    destination_root: Path,
    *,
    force: bool,
    dry_run: bool,
) -> tuple[Path, bool]:
    destination_dir = destination_root / source_dir.name
    existed = destination_dir.exists()

    if dry_run:
        return destination_dir, existed

    if existed and not force:
        raise InstallError(
            f"destination skill already exists: {destination_dir} "
            "(use --force to overwrite)"
        )

    if destination_root.exists():
        validate_destination_root(destination_root)
    else:
        destination_root.mkdir(parents=True, exist_ok=True)

    if destination_dir.exists():
        remove_existing(destination_dir)

    shutil.copytree(
        source_dir,
        destination_dir,
        ignore=shutil.ignore_patterns("__pycache__", "*.pyc"),
    )
    rewrite_placeholder(destination_dir / "SKILL.md", destination_root)
    return destination_dir, existed


def main() -> int:
    args = parse_args()

    try:
        manifest_path, skill_names = load_manifest(args.manifest)
        destination_root = resolve_destination(args.target, args.dest)
        validate_destination_root(destination_root)
        source_dirs = validate_skills(skill_names)

        print(f"repo: {REPO_ROOT}")
        print(f"target: {args.target}")
        print(f"manifest: {manifest_path}")
        print(f"destination: {destination_root}")
        print(f"skills: {len(source_dirs)}")

        installed_paths: list[Path] = []
        conflict_paths: list[Path] = []
        for source_dir in source_dirs:
            destination_dir, existed = install_skill(
                source_dir,
                destination_root,
                force=args.force,
                dry_run=args.dry_run,
            )
            if args.dry_run and existed and not args.force:
                conflict_paths.append(destination_dir)
                verb = "would conflict"
                detail = " (rerun with --force to overwrite)"
            elif args.dry_run and existed:
                verb = "would overwrite"
                detail = ""
            elif existed:
                verb = "overwrote"
                detail = ""
                installed_paths.append(destination_dir)
            else:
                verb = "would install" if args.dry_run else "installed"
                detail = ""
                installed_paths.append(destination_dir)
            print(f"{verb}: {source_dir.name} -> {destination_dir}{detail}")

        if args.dry_run:
            print(
                f"dry run complete: {len(source_dirs)} skills checked, "
                f"{len(conflict_paths)} conflicts"
            )
        else:
            print(f"install complete: {len(installed_paths)} skills")
        return 0
    except InstallError as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
