# Contributing

Thanks for your interest in improving these tools. / 感謝你願意改善這些工具。

`open-agent-forge` is a **public** collection: every tool here has been verified and
de-identified before publication. Keeping it clean is the single most important rule.

## Language / 語言

- **Reference docs** (`skills/*/references/*.md`) are written in Traditional Chinese
  (zh-TW). Keep new reference content consistent with the existing style; English PRs
  for references are welcome but should be added alongside, not replace, the zh-TW text.
- **READMEs, CHANGELOGs, and code comments** are in English so the project is
  approachable to a global audience.

## The golden rule: never commit real secrets or identifiers

These tools process designs, source paths, and internal artifacts, so it is easy to
leak by accident. Never commit:

- Tokens, access codes, or URLs containing access codes
- Real company package names, repository names, or internal codenames
- Real API contracts or business rules in any `references/examples/`

Use neutral placeholders instead (`com.example.app`, a generic feature name).

## Before you open a PR

1. **Keep scripts dependency-free.** Scripts use the Python standard library only
   (minimum Python 3.7). Please do not add third-party dependencies without discussion.
2. **Test the scripts you touch.** From the relevant skill's `scripts/`:
   ```bash
   python3 -m py_compile *.py          # syntax
   python3 <script>.py --help          # CLI smoke test
   ```

## Adding a new skill

Each skill is a self-contained folder under `skills/`:

```
skills/<skill-name>/
├── SKILL.md          # entry point Claude loads
├── README.md         # human-facing docs for this skill
├── CHANGELOG.md      # this skill's own versioning
├── references/       # zh-TW reference docs
└── scripts/          # standard-library-only Python
```

A skill must be **independently installable** — copying its folder into
`~/.claude/skills/` should be all a user needs. Do not introduce cross-skill imports
or dependencies on this repo's layout.
