# Changelog

All notable changes to this skill are documented here.
The format is based on [Keep a Changelog](https://keepachangelog.com/),
and this project adheres to [Semantic Versioning](https://semver.org/).

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
