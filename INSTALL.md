# Installation Guide

## Requirements

- `git`
- `python3`
- access to the private GitHub repo

## Clone

```bash
gh repo clone AustinJunyuLi/austins-skills
cd austins-skills
```

If you prefer plain git:

```bash
git clone git@github.com:AustinJunyuLi/austins-skills.git
cd austins-skills
```

## Install For Codex CLI

Base global set:

```bash
python3 scripts/install_skills.py --target codex --manifest global
```

Global plus project-specific skills:

```bash
python3 scripts/install_skills.py --target codex --manifest all
```

Update an existing install:

```bash
python3 scripts/install_skills.py --target codex --manifest all --force
```

## Install For Claude Code

Base global set:

```bash
python3 scripts/install_skills.py --target claude --manifest global
```

Global plus project-specific skills:

```bash
python3 scripts/install_skills.py --target claude --manifest all
```

Update an existing install:

```bash
python3 scripts/install_skills.py --target claude --manifest all --force
```

## Available Manifests

- `global`: portable global skills only
- `informal-bids`: manifest name for the two skills from the `informal_bids` repo
- `all`: `global` plus `informal-bids`

## Dry Run And Custom Destination

Check what would be installed without copying files:

```bash
python3 scripts/install_skills.py --target codex --manifest global --dry-run
python3 scripts/install_skills.py --target claude --manifest global --dry-run
```

Install into a temporary directory for smoke testing:

```bash
python3 scripts/install_skills.py --target codex --manifest global --dest /tmp/austins-skills-codex --force
python3 scripts/install_skills.py --target claude --manifest global --dest /tmp/austins-skills-claude --force
```

## Verify

Check the installed directories:

```bash
find ~/.codex/skills -maxdepth 1 -mindepth 1 -type d | sort
find ~/.claude/skills -maxdepth 1 -mindepth 1 -type d | sort
```

Check that no unresolved placeholder remains:

```bash
rg -n '\{\{SKILLS_ROOT\}\}' ~/.codex/skills ~/.claude/skills -g 'SKILL.md'
```

An empty result is the expected result.

Restart Codex CLI or Claude Code after installing so the new skills are loaded.

## Notes

- `.system` skills are intentionally excluded because they are platform-managed.
- The installer uses one canonical `skills/` tree and rewrites install-time paths only where needed.
- `--dest` overrides the default target root. When it is set, placeholder substitution uses that custom destination.
