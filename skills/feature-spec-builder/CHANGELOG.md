# Changelog

All notable changes to this skill are documented here.
The format is based on [Keep a Changelog](https://keepachangelog.com/),
and this project adheres to [Semantic Versioning](https://semver.org/).

## [1.1.1] - 2026-06-10

Covers the upstream `forge-skills` feature-spec-builder update from v1.19.1.

### Fixed
- Update-mode example: the disabled-state open question now has a `[Pending]`
  marker in the screen spec table and a matching Pending Summary entry, so the
  Phase 3.5 gate scan can detect it (three-layer pending correspondence).

## [1.1.0] - 2026-06-10

Covers the upstream `forge-skills` feature-spec-builder updates from v1.18.0
and v1.19.0.

### Added
- Phase 3.5 Q&A Gate with explicit gate dispositions and mandatory pending scans.
- Figma frame-link extraction via the nodes API, with `granularity` marking page
  versus frame output.
- Manual regression scenarios for the Phase 3.5 gate, including the original
  missing-API trap case.
- Template/init synchronization guidance and improved update-mode scan evidence.

### Changed
- Source conflicts now use the source-of-truth hierarchy as the draft default and
  are confirmed centrally in Phase 3.5 instead of stopping during reconcile.
- Examples now follow the pending-summary and live-spec rules used by the skill.
- Phase 1.5 source extraction documents rate-limit retry handling and degraded
  Axure output handling.

### Fixed
- Figma cache metadata now stores the caller-provided `--page` value, preventing
  permanent cache misses when the API resolves a different page name.
- Axure no-auth detection now checks `mainframe` against lower-cased HTML.
- Axure partial sitemap outputs are marked `degraded` so they are not treated as
  successful extraction.
- Figma token length errors no longer mention an outdated 40-character threshold.

## [1.0.0] - 2026-05-28

First standalone release.

> Provenance: this skill was previously bundled inside the `claude-forge`
> marketplace (`forge-skills`). It is now published as an independent,
> self-contained skill with its own versioning.

### Added
- Cross-platform credential storage in `keychain_helper.py`: macOS continues to
  use the Keychain; other platforms fall back to a `0600`-permission JSON file
  under `${XDG_DATA_HOME:-~/.local/share}/feature-spec-builder/secrets.json`.
- `AXURE_ACCESS_CODE` environment-variable fallback for Axure access codes,
  matching the existing `FIGMA_ACCESS_TOKEN` support.
- Skill-local `LICENSE`, `.gitignore`, `CHANGELOG.md`, and `CONTRIBUTING.md` so
  the folder is publishable as a self-contained unit.

### Changed
- De-identified all example content: removed real company package names and
  internal codenames in favor of neutral placeholders (`com.example.app`,
  `FeatureOverviewBlock.kt`, a generic personal-finance example domain).
- Removed the `claude-forge` namespace from project-settings paths; the settings
  store is now `${XDG_DATA_HOME:-~/.local/share}/feature-spec-builder/`.
- Credential documentation updated to describe the cross-platform backend and to
  distinguish the forbidden in-repo `.local` files from the allowed home-directory
  XDG secret store.

### Notes
- Minimum Python version: 3.7 (uses `from __future__ import annotations`).
- No third-party Python dependencies; standard library only.
