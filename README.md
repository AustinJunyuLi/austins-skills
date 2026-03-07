# Austin's skills

Private source of truth for Austin's portable, user-managed skills.

This repo packages one canonical `skills/` tree that can be installed into either:

- Codex CLI: `~/.codex/skills`
- Claude Code: `~/.claude/skills`

## Included

- active non-system global skills
- optional project skills from the `informal_bids` repo, grouped under the `informal-bids` manifest
- manifest files for selective installs
- a single installer for both toolchains

## Excluded

- platform-managed `.system` skills
- `superpowers` workflow skills
- unrelated project files or local machine config

## Layout

```text
.
├── INSTALL.md
├── README.md
├── manifests/
│   ├── all.txt
│   ├── global.txt
│   └── informal-bids.txt
├── scripts/
│   └── install_skills.py
└── skills/
    ├── blackjax-mc-suite/
    ├── citation-management/
    ├── ...
    └── visualization/
```

## Install

Clone the private repo, then install the manifest you want:

```bash
python3 scripts/install_skills.py --target codex --manifest global
python3 scripts/install_skills.py --target claude --manifest global
```

Optional project-local skills:

```bash
python3 scripts/install_skills.py --target codex --manifest all --force
python3 scripts/install_skills.py --target claude --manifest informal-bids --force
```

The installer copies the selected skill directories and rewrites any `{{SKILLS_ROOT}}` placeholders inside installed `SKILL.md` files so the installed paths work on the target tool.

Full setup, update, and verification steps are in `INSTALL.md`.
