# feature-spec-builder

A [Claude Code](https://code.claude.com/docs) skill that turns Axure prototypes,
Figma designs, and API contracts into a single source-of-truth
`FEATURE-SPEC.md` — an engineering feature spec written for RD, QA, and AI agents
(not a PM/PRD product narrative).

The output is split into a **Human Zone** (skim-friendly, for engineers) and an
**AI Reference Zone** (structured appendices, for code generation and validation).

> The skill's prompts and reference docs are written in Traditional Chinese
> (zh-TW); this README and the code are in English. Claude operates the skill in
> either language.

## Modes

| Mode | When | What it does |
|------|------|--------------|
| **Create** | No spec exists yet | Sequential intake of feature name, path, Axure/Figma/API sources, then composes a fresh `FEATURE-SPEC.md` |
| **Update** | A spec already exists | Menu-driven: patch only the chapters affected by new Axure/Figma/API input, answer pending items, then reconcile |
| **Code Sync** | Feature is wrapping up / merging | Reads the current code as ground truth, reports drift (TBD backfills, missing items, inconsistencies, stale sections), writes back only what you approve |

## Requirements

- **Claude Code** (CLI, desktop, or IDE extension)
- **Python 3.7+** — standard library only, no third-party dependencies
- A **Figma access token** and/or **Axure share link** (with an access code if the
  prototype is protected)

## Installation

Install as a personal skill by copying this folder into your Claude Code skills
directory:

```bash
git clone https://github.com/<your-account>/open-agent-forge.git
cp -r open-agent-forge/skills/feature-spec-builder ~/.claude/skills/feature-spec-builder
```

Then invoke it in Claude Code with `/feature-spec-builder`, or just describe the
task in natural language (see Usage below).

## Credential setup

Credentials are **never** written into the repo, the spec, change logs, or output
text. They are kept in a secure local store whose backend is chosen automatically:

- **macOS** → macOS Keychain (via the `security` CLI)
- **Other platforms** → a `0600`-permission file at
  `${XDG_DATA_HOME:-~/.local/share}/feature-spec-builder/secrets.json`

### Figma token

```bash
# Store once (read from stdin; never echoed back):
echo "<your-figma-token>" | python3 scripts/keychain_helper.py store
python3 scripts/keychain_helper.py check    # verify (does not print the token)
```

Resolution order: `--token` arg → `FIGMA_ACCESS_TOKEN` env var → local store.

### Axure access code

```bash
echo "<access-code>" | python3 scripts/keychain_helper.py axure-store --link "<share-link>"
```

Resolution order: `--code` arg → `AXURE_ACCESS_CODE` env var → local store.

For ephemeral/CI use you can skip storage entirely and pass credentials via the
environment variables.

## Usage

Trigger the skill by describing what you want, for example:

- "Build a FEATURE-SPEC.md from this Axure and Figma."
- "Update the FEATURE-SPEC.md for this redesign."
- "Sync the spec to the current code." (Code Sync mode)

Claude collects the sources, extracts the designs into per-link JSON under
`<repo>/.ai-artifacts/feature-spec-builder/`, reconciles conflicts (asking you
when sources disagree), and composes the spec.

## What it does *not* do

- It does not write PM/PRD or business-narrative documents.
- It does not invent specs from nothing — at least one design source (Axure or
  Figma) is required before it will produce a real spec.
- It does not refresh or mint Figma/Axure tokens for you.

## Resetting

Everything the skill generates inside a target repo lives under
`<repo>/.ai-artifacts/`. Deleting that directory is always safe and does not
touch your credentials or settings:

```bash
rm -rf .ai-artifacts/
```

## License

MIT — see [LICENSE](LICENSE).
