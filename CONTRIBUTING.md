# Contributing

**English** | [繁體中文](CONTRIBUTING.zh-TW.md)

Thanks for your interest in improving these tools.

`open-agent-forge` is a **public** collection: everything here has been verified and
de-identified before publication. Keeping it clean is the single most important rule.

## What you can change here

Most of this repository is published from a separate working repository by a sync
script. That decides where a change has to be made.

| Path | Maintained | How to contribute |
|------|------------|-------------------|
| `plugins/`, `skills/`, and the plugin entries in `.claude-plugin/marketplace.json` | At the source. Every release overwrites them | Open an issue, or describe the change in a pull request. It is applied at the source and arrives with the next release |
| `README.md`, `README.zh-TW.md`, `CONTRIBUTING.md`, `CONTRIBUTING.zh-TW.md`, `LICENSE` | Here | Open a pull request |
| A `README.md` or `CHANGELOG.md` inside a skill or plugin folder | Here. Releases leave them alone | Open a pull request |

A pull request that edits files under `plugins/` or `skills/` cannot be merged as it is,
because the next release would overwrite it. A diff or a snippet in the description is
still the clearest way to show what you mean.

## The golden rule: never commit real secrets or identifiers

These tools process designs, source paths, pull requests, and internal artifacts, so it is
easy to leak by accident. Never commit, and never paste into an issue or a pull request:

- Tokens, access codes, or URLs containing access codes
- Real company package names, repository names, host names, or internal codenames
- Real API contracts or business rules in any `references/examples/`

Use neutral placeholders instead (`com.example.app`, a generic feature name).

## Language / 語言

- **Skills** (`SKILL.md` and `references/`) are written in Traditional Chinese (zh-TW).
  Keep proposed changes consistent with the existing style. English versions of reference
  docs are welcome alongside the zh-TW text, not in place of it.
- **Comments in `scripts/`** follow the language already used in the file.
- **READMEs and CHANGELOGs** are in English so the project is approachable to a global
  audience. The top-level README and this guide are also available in Traditional Chinese.
  When you change one version, update the other.

## Proposing a change to a skill

Whether you open an issue or sketch the change in a pull request, a change has to meet
these rules:

1. **Keep scripts dependency-free.** Scripts use the Python standard library only
   (minimum Python 3.9). Please do not add third-party dependencies without discussion.
2. **Test the scripts you touch.** From the relevant skill's `scripts/`:
   ```bash
   python3 -m py_compile *.py          # syntax
   python3 <script>.py --help          # CLI smoke test
   ```
3. **Keep `SKILL.md` portable.** `name` matches the folder name, `description` stays
   within 1024 characters, and tool-specific fields go under `metadata`.

## Proposing a new skill

Open an issue that says what the skill does and when an agent should use it. A skill in
this collection:

- lives in a plugin, next to related skills:

  ```
  plugins/<plugin>/skills/<skill>/
  ├── SKILL.md          # entry point the agent loads
  ├── references/       # zh-TW reference docs
  └── scripts/          # standard-library-only Python
  ```

- may rely on other skills in the same plugin, or on that plugin's `shared/` scripts, but
  never on another plugin
- states what it needs next to it when someone copies it as a single folder from
  `skills/`. The Skills table in the README records this
- is de-identified, as the golden rule requires

New skills are added at the source and then published here, to both `plugins/` and
`skills/`.
