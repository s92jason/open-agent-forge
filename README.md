# open-agent-forge

A public collection of [Claude Code](https://code.claude.com/docs) skills.

Every tool here has been **verified and de-identified** before publication — real
company identifiers, internal codenames, and credentials are scrubbed, and each skill
is confirmed to run as a self-contained unit on a clean machine.

## Skills

| Skill | What it does | Docs |
|-------|--------------|------|
| **feature-spec-builder** | Turns Axure / Figma / API sources into a single source-of-truth `FEATURE-SPEC.md` for RD, QA, and AI agents. Supports Create / Update / Code Sync modes. | [README](skills/feature-spec-builder/README.md) |

## Installing a skill

Each skill is a self-contained folder under `skills/`. Install one by copying its
folder into your Claude Code skills directory:

```bash
git clone https://github.com/<your-account>/open-agent-forge.git
cp -r open-agent-forge/skills/feature-spec-builder ~/.claude/skills/feature-spec-builder
```

Then invoke it in Claude Code (e.g. `/feature-spec-builder`) or describe the task in
natural language. See each skill's README for prerequisites and credential setup.

## Requirements

- **Claude Code** (CLI, desktop, or IDE extension)
- **Python 3.7+** — standard library only, no third-party dependencies

## Contributing

See [CONTRIBUTING.md](CONTRIBUTING.md). The golden rule: never commit real secrets or
identifiers — this is a public, de-identified collection.

## License

MIT — see [LICENSE](LICENSE).
