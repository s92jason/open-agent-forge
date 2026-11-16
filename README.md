# open-agent-forge

**English** | [繁體中文](README.zh-TW.md)

Skills and plugins for AI coding agents: [Claude Code](https://code.claude.com/docs),
Codex CLI, GitHub Copilot CLI, and other tools that read the
[Agent Skills](https://agentskills.io/specification) format.

Everything here is **verified and de-identified** before publication. An automated scan
blocks the release if it finds a real company identifier, an internal codename, or a
credential.

> **Language.** The skills are written in Traditional Chinese (zh-TW) and reply in
> Traditional Chinese by default. Most descriptions also carry English keywords.

## Repository layout

```
open-agent-forge/
├── .claude-plugin/
│   └── marketplace.json        # plugin catalog read by Claude Code, Codex CLI and Copilot CLI
├── plugins/                    # complete plugins
│   └── <plugin>/
│       ├── .claude-plugin/plugin.json
│       ├── skills/<skill>/     # SKILL.md, references/, scripts/
│       └── shared/             # forge-git-flow only: helper scripts its skills share
└── skills/                     # the same skills, one folder each, not grouped by plugin
    ├── <skill>/
    └── shared/                 # copy of forge-git-flow's shared/
```

Every skill is published twice: inside its plugin (`plugins/<plugin>/skills/<skill>/`) and
on its own (`skills/<skill>/`). Both copies come from the same release and always match.
Use `plugins/` if your tool has a plugin system, and `skills/` if it does not or if you
only want one folder.

## Install

### As a plugin (recommended)

Add this repository as a plugin marketplace, then install the plugins you want. The
examples install `forge-git-flow`; replace it with any name from the [Plugins](#plugins)
table.

**Claude Code**

```bash
claude plugin marketplace add s92jason/open-agent-forge
claude plugin install forge-git-flow@open-agent-forge
```

Inside a session, `/plugin marketplace add s92jason/open-agent-forge` and
`/plugin install forge-git-flow@open-agent-forge` do the same.

**Codex CLI**

```bash
codex plugin marketplace add s92jason/open-agent-forge
codex plugin add forge-git-flow@open-agent-forge
```

**GitHub Copilot CLI**

```bash
copilot plugin marketplace add s92jason/open-agent-forge
copilot plugin install forge-git-flow@open-agent-forge
```

### As a single skill

With the [`skills` CLI](https://github.com/vercel-labs/skills):

```bash
npx skills add s92jason/open-agent-forge --skill feature-spec-builder
```

Or copy the folder into your tool's skills directory:

```bash
git clone https://github.com/s92jason/open-agent-forge.git
cp -r open-agent-forge/skills/feature-spec-builder ~/.claude/skills/
```

| Tool | Personal skills directory |
|------|---------------------------|
| Claude Code | `~/.claude/skills/` |
| Codex CLI | `~/.agents/skills/` |
| GitHub Copilot CLI | `~/.copilot/skills/` or `~/.agents/skills/` |

A few skills need other folders next to them. The [Skills](#skills) table says which.
When in doubt, install the plugin: it always brings everything a skill needs.

### Using a skill

Describe the task in natural language, or call the skill by name. In Claude Code a skill
installed through a plugin is `/forge-git-flow:pr-review`; the same skill copied as a
single folder is `/pr-review`.

## Plugins

| Plugin | What it covers | Contents |
|--------|----------------|----------|
| **forge-git-flow** | Git workflow, from creating branches to reviewing, committing and describing a pull request | 8 skills |
| **forge-spec** | Engineering feature specs built from designs or from the current code | 1 skill |
| **forge-hiring** | Grading take-home assignments | 1 skill |
| **forge-toolkit** | General working methods that fit any stack or task | 1 skill |

## Skills

| Skill | Plugin | What it does | Works on its own |
|-------|--------|--------------|------------------|
| **branch-diff-code-review** | forge-git-flow | Reviews the diff between the branch base and `HEAD`, splits large diffs into chunks, and scores the change out of 100. | Needs `shared/` |
| **pr-review** | forge-git-flow | Reviews a Gitea pull request from its number or URL without touching your working branch. Groups the changes, writes a reading guide, and shows AI comments beside the diff lines on a local page, where you accept or dismiss them, add your own, and submit everything as one review. Handles follow-up rounds after new commits. | Needs `shared/` and `branch-diff-code-review/` |
| **branch-wrap-up** | forge-git-flow | Finishes a feature branch in one pass: TODO scan, docstrings, code review, commit, pull request draft. | Calls four other git-flow skills |
| **branch-diff-unit-test** | forge-git-flow | Adds unit tests for the business-logic classes changed on the branch (Android: JUnit, MockK, coroutines), aiming for 90% branch coverage or higher. | Yes |
| **branch-diff-annotator** | forge-git-flow | Adds docstrings (KDoc, JSDoc, PEP 257) to the code changed on the branch. | Yes |
| **branch-diff-pr-description** | forge-git-flow | Drafts a pull request title and description from the branch diff, using the project's own template when there is one. Read-only. | Yes |
| **smart-commit-flow** | forge-git-flow | Proposes commit messages, commits the one you pick, and pushes only after you confirm. | Yes |
| **create-git-branches** | forge-git-flow | Creates several related branches from one confirmed commit, with naming rules learned from your existing branches. | Yes |
| **feature-spec-builder** | forge-spec | Turns Axure, Figma and API sources into a single `FEATURE-SPEC.md` for developers, QA and AI agents. Create, Update and Code Sync modes. [README](skills/feature-spec-builder/README.md) | Yes |
| **android-hw-grader** | forge-hiring | Grades Android take-home assignments: keeps the questions and rubrics, analyses the project, and writes structured feedback with a score. | Yes |
| **task-brief** | forge-toolkit | Turns a one-line request into a handoff for a new Claude Code session: recommended model, effort and permission mode, a kickoff prompt, and a launch command. Read-only. | Yes |

"Needs `shared/`" means: copy `skills/shared/` into the same skills directory as the skill.
`branch-wrap-up` calls `branch-diff-annotator`, `branch-diff-code-review`,
`smart-commit-flow` and `branch-diff-pr-description`, so install those with it.

## Requirements

- One supported agent: Claude Code, Codex CLI, GitHub Copilot CLI, or another tool that
  reads Agent Skills
- **Python 3.9+**. The scripts use the standard library only
- **git**, for the forge-git-flow skills
- A **Gitea** instance, for `pr-review`

See each skill's `SKILL.md` for its own prerequisites and credential setup.

## Compatibility

The skills are developed and used day to day in Claude Code. To keep them portable:

- `SKILL.md` frontmatter uses only the top-level fields every supported tool accepts.
  Tool-specific fields are kept under `metadata`.
- Plugin installation is checked with Claude Code, Codex CLI and GitHub Copilot CLI.

Some skills rely on Claude Code features such as subagents or slash-command arguments, and
may behave differently in other tools.

## How this repository is maintained

The contents of `plugins/` and `skills/` are published from a separate working repository
by a sync script, which also updates `.claude-plugin/marketplace.json`. Changes made
directly to those folders are overwritten by the next release, so please do not edit them
in a pull request. Open an issue, or describe the change in a pull request, and it will be
applied at the source.

## Contributing

See [CONTRIBUTING.md](CONTRIBUTING.md). The golden rule: never commit real secrets or
identifiers. This is a public, de-identified collection.

## License

MIT. See [LICENSE](LICENSE).
