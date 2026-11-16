#!/usr/bin/env python3
"""Deterministic configuration and Git safety helper for create-git-branches."""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import subprocess
import sys
import tempfile
from datetime import datetime, timezone
from pathlib import Path
from string import Formatter
from typing import Any, Sequence
from urllib.parse import urlsplit, urlunsplit


ZERO_SHA = "0" * 40
CONFIRM_PUSH_VALUES = {"1", "confirm push", "確認 push", "確認push"}
BUILTIN_BASE: dict[str, Any] = {
    "version": 1,
    "naming": {
        "template": "{slug}",
        "ascii": True,
        "lowercase": True,
        "separator": "-",
        "candidate_count": 3,
    },
    "variables": {},
    "targets": {},
    "profiles": {},
    "defaults": {"profile": "", "remote": "origin", "checkout": False},
    "push": {"atomic": True, "set_upstream": True},
    "presentation": {"profile_labels": {}, "target_labels": {}},
}

ABSENT_SNAPSHOT = {"_create_git_branches_absent": True}


class UserError(RuntimeError):
    """Represent an expected validation, environment, or safety failure."""


def emit(payload: Any) -> None:
    """Write stable, human-readable JSON to stdout."""
    print(json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True))


def run_git(
    repo: Path,
    args: Sequence[str],
    *,
    input_text: str | None = None,
    check: bool = True,
) -> subprocess.CompletedProcess[str]:
    """Run Git without shell interpolation and return captured text output."""
    result = subprocess.run(
        ["git", "-C", str(repo), *args],
        input=input_text,
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        check=False,
    )
    if check and result.returncode != 0:
        detail = result.stderr.strip() or result.stdout.strip() or "unknown git error"
        raise UserError(f"git {' '.join(args)} failed: {detail}")
    return result


def repo_root(repo_arg: str) -> Path:
    """Resolve and validate a Git worktree root."""
    candidate = Path(repo_arg).expanduser().resolve()
    result = run_git(candidate, ["rev-parse", "--show-toplevel"], check=False)
    if result.returncode != 0:
        raise UserError(f"not a Git repository: {candidate}")
    return Path(result.stdout.strip()).resolve()


def data_root() -> Path:
    """Return the XDG-compatible persistent configuration root."""
    xdg = os.environ.get("XDG_DATA_HOME")
    base = Path(xdg).expanduser() if xdg else Path.home() / ".local" / "share"
    return base / "create-git-branches"


def normalize_origin(value: str) -> str:
    """Normalize common URL and SCP-style Git remote representations."""
    raw = value.strip()
    scp = re.fullmatch(r"([^/@:]+)@([^/:]+):(.+)", raw)
    if scp:
        raw = f"ssh://{scp.group(1)}@{scp.group(2)}/{scp.group(3)}"
    parts = urlsplit(raw)
    if parts.scheme and parts.netloc:
        host = parts.hostname.lower() if parts.hostname else ""
        user = f"{parts.username}@" if parts.username else ""
        port = f":{parts.port}" if parts.port else ""
        netloc = f"{user}{host}{port}"
        path = re.sub(r"/+$", "", parts.path)
        path = re.sub(r"\.git$", "", path, flags=re.IGNORECASE)
        return urlunsplit((parts.scheme.lower(), netloc, path, "", ""))
    return re.sub(r"\.git/?$", "", raw).rstrip("/")


def project_identity(repo: Path) -> tuple[str, str]:
    """Return a collision-resistant project key and its identity source."""
    repo = repo.resolve()
    origin = run_git(repo, ["remote", "get-url", "origin"], check=False)
    if origin.returncode == 0 and origin.stdout.strip():
        identity = normalize_origin(origin.stdout.strip())
        source = "origin"
    else:
        identity = str(repo)
        source = "path"
    digest = hashlib.sha256(identity.encode("utf-8")).hexdigest()[:12]
    safe_name = re.sub(r"[^A-Za-z0-9._-]+", "-", repo.name).strip("-._") or "repo"
    return f"{safe_name}-{digest}", source


def config_paths(repo: Path) -> tuple[Path, Path, str, str]:
    """Return global/project paths plus project key and identity source."""
    key, identity_source = project_identity(repo)
    root = data_root()
    return root / "global.json", root / "projects" / f"{key}.json", key, identity_source


def read_json(path: Path) -> dict[str, Any]:
    """Read one JSON object, rejecting other root types."""
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise UserError(f"cannot read JSON {path}: {exc}") from exc
    if not isinstance(value, dict):
        raise UserError(f"configuration root must be an object: {path}")
    return value


def atomic_write_json(path: Path, value: dict[str, Any]) -> None:
    """Atomically replace one JSON file using a temporary sibling file."""
    path.parent.mkdir(parents=True, exist_ok=True)
    descriptor, temp_name = tempfile.mkstemp(prefix=f".{path.name}.", suffix=".tmp", dir=path.parent)
    temp_path = Path(temp_name)
    try:
        with os.fdopen(descriptor, "w", encoding="utf-8") as handle:
            json.dump(value, handle, ensure_ascii=False, indent=2, sort_keys=True)
            handle.write("\n")
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(temp_path, path)
    except BaseException:
        temp_path.unlink(missing_ok=True)
        raise


def previous_path(path: Path) -> Path:
    """Return the single-level history path for one configuration file."""
    return path.with_name(f"{path.stem}.previous.json")


def snapshot(path: Path) -> dict[str, Any]:
    """Capture a configuration file or an internal absence marker."""
    return read_json(path) if path.exists() else dict(ABSENT_SNAPSHOT)


def save_with_history(path: Path, value: dict[str, Any]) -> None:
    """Save a configuration atomically after preserving the replaced state."""
    atomic_write_json(previous_path(path), snapshot(path))
    atomic_write_json(path, value)


def deep_merge(base: dict[str, Any], override: dict[str, Any]) -> dict[str, Any]:
    """Recursively merge objects while replacing arrays and scalar values."""
    merged: dict[str, Any] = dict(base)
    for key, value in override.items():
        current = merged.get(key)
        if isinstance(current, dict) and isinstance(value, dict):
            merged[key] = deep_merge(current, value)
        else:
            merged[key] = value
    return merged


def placeholders(template: str) -> set[str]:
    """Extract simple named placeholders and reject format expressions."""
    names: set[str] = set()
    try:
        fields = Formatter().parse(template)
        for _, field, spec, conversion in fields:
            if field is None:
                continue
            if not re.fullmatch(r"[A-Za-z_][A-Za-z0-9_]*", field):
                raise UserError(f"invalid placeholder {{{field}}} in template: {template}")
            if spec or conversion:
                raise UserError(f"format specs/conversions are not allowed: {template}")
            names.add(field)
    except ValueError as exc:
        raise UserError(f"invalid template {template!r}: {exc}") from exc
    return names


def validate_config(config: dict[str, Any], *, allow_unconfigured: bool = False) -> list[str]:
    """Validate the complete merged configuration and return warnings."""
    errors: list[str] = []
    warnings: list[str] = []
    required_objects = ("naming", "variables", "targets", "profiles", "defaults", "push")
    if config.get("version") != 1:
        errors.append("version must be 1")
    for key in required_objects:
        if not isinstance(config.get(key), dict):
            errors.append(f"{key} must be an object")
    if errors:
        raise UserError("invalid configuration: " + "; ".join(errors))

    naming = config["naming"]
    template = naming.get("template")
    if not isinstance(template, str) or not template:
        errors.append("naming.template must be a non-empty string")
    if naming.get("ascii") is not True:
        errors.append("naming.ascii must be true")
    if naming.get("lowercase") is not True:
        errors.append("naming.lowercase must be true")
    if naming.get("separator") not in {"-", "_"}:
        errors.append("naming.separator must be '-' or '_'")
    count = naming.get("candidate_count")
    if not isinstance(count, int) or isinstance(count, bool) or count < 3:
        errors.append("naming.candidate_count must be an integer >= 3")

    variables = config["variables"]
    for name, spec in variables.items():
        if not re.fullmatch(r"[A-Za-z_][A-Za-z0-9_]*", name):
            errors.append(f"invalid variable name: {name}")
        if not isinstance(spec, dict):
            errors.append(f"variable {name} must be an object")
        elif "required" in spec and not isinstance(spec["required"], bool):
            errors.append(f"variable {name}.required must be boolean")

    targets = config["targets"]
    for name, target in targets.items():
        if not isinstance(target, str):
            errors.append(f"target {name} must be a string")
            continue
        try:
            fields = placeholders(target)
        except UserError as exc:
            errors.append(str(exc))
            continue
        if "base" not in fields:
            errors.append(f"target {name} must reference {{base}}")
        unknown = fields - ({"base", "slug", "ticket"} | set(variables))
        if unknown:
            errors.append(f"target {name} uses undeclared variables: {sorted(unknown)}")

    if isinstance(template, str):
        try:
            unknown = placeholders(template) - ({"slug", "ticket"} | set(variables))
            if unknown:
                errors.append(f"naming.template uses undeclared variables: {sorted(unknown)}")
        except UserError as exc:
            errors.append(str(exc))

    profiles = config["profiles"]
    for name, members in profiles.items():
        if not isinstance(members, list) or not members:
            errors.append(f"profile {name} must be a non-empty array")
        elif any(not isinstance(item, str) or item not in targets for item in members):
            errors.append(f"profile {name} references an unknown target")
        elif len(members) != len(set(members)):
            errors.append(f"profile {name} contains duplicate targets")

    default_profile = config["defaults"].get("profile")
    if profiles and default_profile not in profiles:
        errors.append("defaults.profile must reference an existing profile")
    if not isinstance(config["defaults"].get("remote"), str) or not config["defaults"].get("remote"):
        errors.append("defaults.remote must be a non-empty string")
    if not isinstance(config["defaults"].get("checkout"), bool):
        errors.append("defaults.checkout must be boolean")
    for key in ("atomic", "set_upstream"):
        if not isinstance(config["push"].get(key), bool):
            errors.append(f"push.{key} must be boolean")

    presentation = config.get("presentation", {})
    if not isinstance(presentation, dict):
        errors.append("presentation must be an object")
    else:
        for label_key, available in (("profile_labels", profiles), ("target_labels", targets)):
            labels = presentation.get(label_key, {})
            if not isinstance(labels, dict):
                errors.append(f"presentation.{label_key} must be an object")
                continue
            for name, label in labels.items():
                if name not in available:
                    errors.append(f"presentation.{label_key} references unknown key: {name}")
                if not isinstance(label, str) or not label.strip():
                    errors.append(f"presentation.{label_key}.{name} must be a non-empty string")

    if not targets or not profiles:
        if allow_unconfigured:
            warnings.append("configuration has no usable targets/profiles")
        else:
            errors.append("at least one target and profile are required")
    if errors:
        raise UserError("invalid configuration: " + "; ".join(errors))
    return warnings


def effective_config(repo: Path) -> tuple[dict[str, Any], dict[str, Any]]:
    """Load global and project overrides and validate the merged result."""
    global_path, project_path, key, identity_source = config_paths(repo)
    global_value = read_json(global_path) if global_path.exists() else {}
    project_value = read_json(project_path) if project_path.exists() else {}
    merged = deep_merge(deep_merge(BUILTIN_BASE, global_value), project_value)
    configured = bool(global_value or project_value)
    warnings = validate_config(merged, allow_unconfigured=not configured)
    sources: dict[str, str] = {}
    for field in BUILTIN_BASE:
        if field in project_value:
            sources[field] = "project"
        elif field in global_value:
            sources[field] = "global"
        else:
            sources[field] = "builtin"
    meta = {
        "configured": configured and bool(merged["targets"] and merged["profiles"]),
        "global_path": str(global_path),
        "project_path": str(project_path),
        "project_key": key,
        "project_identity_source": identity_source,
        "sources": sources,
        "warnings": warnings,
    }
    return merged, meta


def merge_for_scope(repo: Path, scope: str, value: dict[str, Any]) -> dict[str, Any]:
    """Simulate replacing one scope while retaining the other scope."""
    global_path, project_path, _, _ = config_paths(repo)
    global_value = value if scope == "global" else (read_json(global_path) if global_path.exists() else {})
    project_value = value if scope == "project" else (read_json(project_path) if project_path.exists() else {})
    merged = deep_merge(deep_merge(BUILTIN_BASE, global_value), project_value)
    validate_config(merged)
    return merged


def starter(name: str) -> dict[str, Any]:
    """Return an explicit starter configuration."""
    if name == "blank":
        return json.loads(json.dumps(BUILTIN_BASE))
    config = json.loads(json.dumps(BUILTIN_BASE))
    config["targets"] = {"stg": "stg/{base}", "ut": "ut/{base}"}
    config["profiles"] = {"shared": ["stg", "ut"]}
    config["defaults"]["profile"] = "shared"
    if name == "generic":
        return config
    if name == "sprint":
        config["naming"].update({"template": "s{sprint}_{slug}", "separator": "_"})
        config["variables"] = {
            "owner": {"description": "branch owner", "required": False},
            "sprint": {"description": "sprint number", "required": False},
        }
        config["targets"].update({
            "feature": "{owner}/feature/{base}",
            "task": "{owner}/task/{base}",
        })
        config["profiles"] = {
            "shared": ["stg", "ut"],
            "feature": ["stg", "ut", "feature"],
            "task": ["stg", "ut", "task"],
        }
        config["defaults"]["profile"] = "feature"
        return config
    raise UserError(f"unknown starter: {name}")


def parse_vars(values: list[str]) -> dict[str, str]:
    """Parse repeated NAME=VALUE arguments."""
    parsed: dict[str, str] = {}
    for item in values:
        if "=" not in item:
            raise UserError(f"variable must use NAME=VALUE: {item}")
        name, value = item.split("=", 1)
        if not name or not value:
            raise UserError(f"variable must have non-empty name/value: {item}")
        parsed[name] = value
    return parsed


def validate_base(repo: Path, base: str, naming: dict[str, Any]) -> None:
    """Validate a generated base name against naming and Git rules."""
    if naming["ascii"] and not base.isascii():
        raise UserError("base name must contain English ASCII characters only")
    if naming["lowercase"] and base != base.lower():
        raise UserError("base name must be lowercase")
    separator = re.escape(naming["separator"])
    if not re.fullmatch(rf"[a-z0-9]+(?:{separator}[a-z0-9]+)*", base):
        raise UserError(f"base name must use only the configured separator {naming['separator']!r}")
    check_branch(repo, base)


def check_branch(repo: Path, branch: str) -> None:
    """Validate one branch name using Git's own ref parser."""
    result = run_git(repo, ["check-ref-format", "--branch", branch], check=False)
    if result.returncode != 0:
        raise UserError(f"invalid branch name {branch!r}: {result.stderr.strip()}")


def resolve_commit(repo: Path, ref: str) -> str:
    """Resolve a commit-ish to a full immutable commit SHA."""
    return run_git(repo, ["rev-parse", "--verify", f"{ref}^{{commit}}"], check=True).stdout.strip()


def inspect_source(repo: Path, source: str) -> dict[str, Any]:
    """Collect source and worktree facts without fetching or mutation."""
    sha = resolve_commit(repo, source)
    subject = run_git(repo, ["show", "-s", "--format=%s", sha]).stdout.strip()
    branch = run_git(repo, ["symbolic-ref", "--quiet", "--short", "HEAD"], check=False)
    current = branch.stdout.strip() if branch.returncode == 0 else None
    upstream = None
    ahead = None
    behind = None
    upstream_result = run_git(repo, ["rev-parse", "--abbrev-ref", "@{upstream}"], check=False)
    if upstream_result.returncode == 0:
        upstream = upstream_result.stdout.strip()
        counts = run_git(repo, ["rev-list", "--left-right", "--count", f"{upstream}...HEAD"])
        behind, ahead = (int(part) for part in counts.stdout.split())
    status_lines = run_git(repo, ["status", "--porcelain=v1", "--untracked-files=all"]).stdout.splitlines()
    return {
        "source_ref": source,
        "source_sha": sha,
        "commit_subject": subject,
        "current_branch": current,
        "detached_head": current is None,
        "upstream": upstream,
        "ahead": ahead,
        "behind": behind,
        "dirty": bool(status_lines),
        "dirty_entries": status_lines,
        "uncommitted_content_included": False,
    }


def discover_branch_patterns(repo: Path, limit: int) -> dict[str, Any]:
    """Find repeated local/remote-tracking branch combinations without network access."""
    if limit < 1:
        raise UserError("limit must be at least 1")
    result = run_git(
        repo,
        [
            "for-each-ref",
            "--format=%(refname)%09%(committerdate:unix)",
            "refs/heads",
            "refs/remotes",
        ],
    )
    branches: dict[str, dict[str, Any]] = {}
    for line in result.stdout.splitlines():
        if "\t" not in line:
            continue
        ref, raw_timestamp = line.split("\t", 1)
        if ref.startswith("refs/heads/"):
            branch = ref.removeprefix("refs/heads/")
            kind = "local"
        elif ref.startswith("refs/remotes/"):
            remainder = ref.removeprefix("refs/remotes/")
            if "/" not in remainder or remainder.endswith("/HEAD"):
                continue
            _, branch = remainder.split("/", 1)
            kind = "remote-tracking"
        else:
            continue
        timestamp = int(raw_timestamp or 0)
        record = branches.setdefault(branch, {"branch": branch, "timestamp": 0, "refs": []})
        record["timestamp"] = max(record["timestamp"], timestamp)
        record["refs"].append({"ref": ref, "kind": kind, "timestamp": timestamp})

    work_groups: dict[str, list[dict[str, Any]]] = {}
    for record in branches.values():
        work_groups.setdefault(record["branch"].rsplit("/", 1)[-1], []).append(record)

    signatures: dict[tuple[str, ...], list[dict[str, Any]]] = {}
    for work_name, records in work_groups.items():
        templates = tuple(
            sorted(
                "{base}" if item["branch"] == work_name else f"{item['branch'][:-len(work_name)]}{{base}}"
                for item in records
            )
        )
        if len(templates) < 2:
            continue
        signatures.setdefault(templates, []).append(
            {
                "work_name": work_name,
                "branches": sorted(item["branch"] for item in records),
                "refs": [ref for item in records for ref in item["refs"]],
                "recent_timestamp": max(item["timestamp"] for item in records),
            }
        )

    candidates: list[dict[str, Any]] = []
    for templates, evidence in signatures.items():
        if len(evidence) < 2:
            continue
        recent = max(item["recent_timestamp"] for item in evidence)
        candidate_id = hashlib.sha256("\0".join(templates).encode("utf-8")).hexdigest()[:12]
        candidates.append(
            {
                "id": candidate_id,
                "target_templates": list(templates),
                "occurrences": len(evidence),
                "recent_timestamp": recent,
                "recent_time": datetime.fromtimestamp(recent, timezone.utc).isoformat(),
                "evidence": sorted(evidence, key=lambda item: item["recent_timestamp"], reverse=True),
            }
        )
    def sort_key(item: dict[str, Any]) -> tuple[int, int, int, int, str]:
        """Sort by ISO week, then evidence count and exact activity time."""
        calendar = datetime.fromtimestamp(item["recent_timestamp"], timezone.utc).isocalendar()
        return (-calendar.year, -calendar.week, -item["occurrences"], -item["recent_timestamp"], item["id"])

    candidates.sort(key=sort_key)
    return {
        "repo": str(repo),
        "read_only": True,
        "network_used": False,
        "refs_scanned": sum(len(item["refs"]) for item in branches.values()),
        "logical_branches_scanned": len(branches),
        "reliable_candidates": len(candidates),
        "candidates": candidates[:limit],
        "truncated": len(candidates) > limit,
    }


def variable_context(config: dict[str, Any], slug: str, values: dict[str, str]) -> dict[str, str]:
    """Build the placeholder context shared by expansion and missing-variable reporting."""
    context = {
        name: str(spec["default"])
        for name, spec in config["variables"].items()
        if isinstance(spec, dict) and spec.get("default") not in (None, "")
    }
    context.update(values)
    context["slug"] = slug
    context.setdefault("ticket", "")
    return context


def missing_variables(config: dict[str, Any], profile: str, slug: str, values: dict[str, str]) -> list[str]:
    """Report placeholders one profile needs but cannot fill, without raising."""
    context = variable_context(config, slug, values)
    needed = set(placeholders(config["naming"]["template"]))
    for name in config["profiles"][profile]:
        needed.update(placeholders(config["targets"][name]))
    return sorted(
        field for field in needed if field not in {"base", "ticket"} and not context.get(field)
    )


def expand_branches(
    repo: Path,
    config: dict[str, Any],
    profile: str,
    slug: str,
    values: dict[str, str],
    additions: list[str],
    removals: list[str],
) -> dict[str, Any]:
    """Expand the base and target templates for one invocation."""
    profiles = config["profiles"]
    if profile not in profiles:
        raise UserError(f"unknown profile: {profile}")
    context = variable_context(config, slug, values)
    naming_template = config["naming"]["template"]
    missing = sorted(name for name in placeholders(naming_template) if name != "ticket" and not context.get(name))
    if missing:
        raise UserError(f"missing variables used by naming template: {missing}")
    try:
        base = naming_template.format_map(context)
    except KeyError as exc:
        raise UserError(f"missing variable: {exc.args[0]}") from exc
    configured_separator = config["naming"]["separator"]
    base = re.sub(re.escape(configured_separator) + r"+", configured_separator, base).strip("-_")
    validate_base(repo, base, config["naming"])

    selected = [name for name in profiles[profile] if name not in removals]
    for name in additions:
        if name not in config["targets"]:
            raise UserError(f"unknown target: {name}")
        if name not in selected:
            selected.append(name)
    target_context = dict(context, base=base)
    missing_targets: set[str] = set()
    for name in selected:
        missing_targets.update(
            field
            for field in placeholders(config["targets"][name])
            if field != "ticket" and not target_context.get(field)
        )
    if missing_targets:
        raise UserError(f"missing variables used by selected targets: {sorted(missing_targets)}")
    branches = [config["targets"][name].format_map(target_context) for name in selected]
    if len(branches) != len(set(branches)):
        raise UserError("expanded branch list contains duplicates")
    for branch in branches:
        check_branch(repo, branch)
    return {"base": base, "profile": profile, "targets": selected, "branches": branches}


def preview_config(
    repo: Path,
    scope: str,
    value: dict[str, Any],
    slug: str,
    values: dict[str, str],
) -> dict[str, Any]:
    """Validate and expand every branch combination for a prospective scope value."""
    effective = merge_for_scope(repo, scope, value)
    labels = effective.get("presentation", {})
    profile_labels = labels.get("profile_labels", {})
    target_labels = labels.get("target_labels", {})
    expansions = []
    for profile in effective["profiles"]:
        expanded = expand_branches(repo, effective, profile, slug, values, [], [])
        expansions.append(
            {
                **expanded,
                "label": profile_labels.get(profile, profile),
                "target_labels": [target_labels.get(name, name) for name in expanded["targets"]],
            }
        )
    global_path, project_path, key, identity_source = config_paths(repo)
    return {
        "valid": True,
        "write_performed": False,
        "scope": scope,
        "scope_path": str(global_path if scope == "global" else project_path),
        "project_key": key,
        "project_identity_source": identity_source,
        "effective": effective,
        "expansions": expansions,
    }


def config_options(repo: Path, slug: str | None, values: dict[str, str]) -> dict[str, Any]:
    """List every configured branch combination read-only, tolerating unexpandable ones.

    Unlike preview_config, a profile that cannot expand degrades to expandable=false
    instead of aborting the whole listing: the create path must still show the other
    combinations when the current request lacks a variable only one profile uses.
    """
    config, meta = effective_config(repo)
    labels = config.get("presentation", {})
    profile_labels = labels.get("profile_labels", {})
    target_labels = labels.get("target_labels", {})
    default_profile = config["defaults"]["profile"]
    example_base = ""
    options: list[dict[str, Any]] = []
    for profile, targets in sorted(config["profiles"].items()):
        entry: dict[str, Any] = {
            "name": profile,
            "label": profile_labels.get(profile, profile),
            "is_default": profile == default_profile,
            "targets": list(targets),
            "target_labels": [target_labels.get(name, name) for name in targets],
            "template_branches": [config["targets"][name] for name in targets],
            "expandable": False,
            "branches": [],
            "missing": [],
        }
        if slug:
            entry["missing"] = missing_variables(config, profile, slug, values)
            if entry["missing"]:
                entry["error"] = "missing variables: " + ", ".join(entry["missing"])
            else:
                try:
                    expanded = expand_branches(repo, config, profile, slug, values, [], [])
                except UserError as exc:
                    entry["error"] = str(exc)
                else:
                    entry["expandable"] = True
                    entry["base"] = expanded["base"]
                    entry["branches"] = expanded["branches"]
                    example_base = example_base or expanded["base"]
        options.append(entry)
    naming = {
        "template": config["naming"]["template"],
        "separator": config["naming"]["separator"],
        "candidate_count": config["naming"]["candidate_count"],
    }
    if example_base:
        naming["example_base"] = example_base
    return {
        "configured": meta["configured"],
        "read_only": True,
        "write_performed": False,
        "default_profile": default_profile,
        "profile_count": len(options),
        "profiles": options,
        "naming": naming,
        "variables": config["variables"],
        "defaults": config["defaults"],
        "push": config["push"],
        "sources": meta["sources"],
        "warnings": meta["warnings"],
        "global_path": meta["global_path"],
        "project_path": meta["project_path"],
        "project_key": meta["project_key"],
    }


def local_states(repo: Path, branches: list[str], source_sha: str) -> list[dict[str, str]]:
    """Classify requested local refs as create, reuse, or collision."""
    if len(branches) != len(set(branches)):
        raise UserError("branch arguments contain duplicates")
    states: list[dict[str, str]] = []
    for branch in branches:
        check_branch(repo, branch)
        existing = run_git(repo, ["show-ref", "--verify", "--hash", f"refs/heads/{branch}"], check=False)
        if existing.returncode != 0:
            states.append({"branch": branch, "status": "create", "sha": source_sha})
        else:
            sha = existing.stdout.strip()
            status = "reuse" if sha == source_sha else "collision"
            states.append({"branch": branch, "status": status, "sha": sha})
    return states


def create_local(repo: Path, source_sha: str, branches: list[str]) -> dict[str, Any]:
    """Atomically create all missing local refs at one source commit."""
    resolved = resolve_commit(repo, source_sha)
    if resolved != source_sha:
        raise UserError("source-sha must be the full resolved commit SHA")
    states = local_states(repo, branches, source_sha)
    collisions = [item for item in states if item["status"] == "collision"]
    if collisions:
        raise UserError("local collision blocks the entire batch: " + json.dumps(collisions, ensure_ascii=False))
    creates = [item for item in states if item["status"] == "create"]
    if creates:
        lines = ["start"]
        lines.extend(f"update refs/heads/{item['branch']} {source_sha} {ZERO_SHA}" for item in creates)
        lines.extend(["prepare", "commit", ""])
        run_git(repo, ["update-ref", "--stdin"], input_text="\n".join(lines))
    current = run_git(repo, ["symbolic-ref", "--quiet", "--short", "HEAD"], check=False)
    return {
        "source_sha": source_sha,
        "created": [item["branch"] for item in creates],
        "reused": [item["branch"] for item in states if item["status"] == "reuse"],
        "skipped": [],
        "current_branch": current.stdout.strip() if current.returncode == 0 else None,
        "checkout_changed": False,
    }


def remote_refs(repo: Path, remote: str, branches: list[str]) -> dict[str, str]:
    """Read exact remote heads without fetching them into local refs."""
    args = ["ls-remote", "--heads", remote, *[f"refs/heads/{name}" for name in branches]]
    result = run_git(repo, args)
    refs: dict[str, str] = {}
    for line in result.stdout.splitlines():
        sha, ref = line.split("\t", 1)
        refs[ref.removeprefix("refs/heads/")] = sha
    return refs


def canonical_hash(payload: dict[str, Any]) -> str:
    """Hash canonical JSON for tamper and stale-plan detection."""
    raw = json.dumps(payload, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()


def build_push_plan(
    repo: Path,
    remote: str,
    source_sha: str,
    branches: list[str],
    plan_path: Path,
    mode: str,
    set_upstream: bool,
) -> dict[str, Any]:
    """Preflight and persist a push plan bound to exact refs and remote state."""
    if len(branches) != len(set(branches)) or not branches:
        raise UserError("push subset must contain one or more unique branches")
    remote_url = run_git(repo, ["remote", "get-url", remote]).stdout.strip()
    local: dict[str, str] = {}
    for branch in branches:
        check_branch(repo, branch)
        sha = run_git(repo, ["show-ref", "--verify", "--hash", f"refs/heads/{branch}"]).stdout.strip()
        if sha != source_sha:
            raise UserError(f"local branch moved or differs from source SHA: {branch} -> {sha}")
        local[branch] = sha
    remote_snapshot = remote_refs(repo, remote, branches)
    blocked = [name for name, sha in remote_snapshot.items() if sha != local[name]]
    if blocked:
        raise UserError(f"remote different-SHA collision blocks push: {blocked}")
    synced = [name for name in branches if remote_snapshot.get(name) == local[name]]
    pending = [name for name in branches if name not in synced]
    refspecs = [f"refs/heads/{name}:refs/heads/{name}" for name in pending]
    if mode == "atomic":
        command = ["git", "push", "--atomic"]
        if set_upstream:
            command.append("--set-upstream")
        command.extend([remote, *refspecs])
        commands = [command] if pending else []
    else:
        commands = []
        for refspec in refspecs:
            command = ["git", "push"]
            if set_upstream:
                command.append("--set-upstream")
            command.extend([remote, refspec])
            commands.append(command)
    if pending:
        dry_run = [commands[0][1], "--dry-run", *commands[0][2:]]
        result = run_git(repo, dry_run, check=False)
        if result.returncode != 0:
            raise UserError(f"push preflight failed; no refs were pushed: {result.stderr.strip()}")
    payload: dict[str, Any] = {
        "version": 1,
        "repo": str(repo),
        "git_common_dir": run_git(repo, ["rev-parse", "--git-common-dir"]).stdout.strip(),
        "remote": remote,
        "remote_url": remote_url,
        "source_sha": source_sha,
        "branches": branches,
        "local": local,
        "remote_snapshot": remote_snapshot,
        "pending": pending,
        "synced": synced,
        "mode": mode,
        "set_upstream": set_upstream,
        "commands": commands,
        "partial_success_risk": mode == "sequential" and len(pending) > 1,
    }
    payload["plan_hash"] = canonical_hash(payload)
    plan_path = plan_path.expanduser().resolve()
    plan_path.parent.mkdir(parents=True, exist_ok=True)
    plan_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return payload


def execute_push(plan_path: Path, confirmation: str) -> dict[str, Any]:
    """Revalidate and execute one explicitly confirmed push plan."""
    if confirmation.strip().lower() not in CONFIRM_PUSH_VALUES:
        raise UserError("push requires explicit confirmation: 1 or 確認 push")
    plan = read_json(plan_path.expanduser().resolve())
    supplied_hash = plan.pop("plan_hash", None)
    if not isinstance(supplied_hash, str) or canonical_hash(plan) != supplied_hash:
        raise UserError("push plan is missing or has been modified")
    repo = repo_root(plan["repo"])
    if run_git(repo, ["rev-parse", "--git-common-dir"]).stdout.strip() != plan["git_common_dir"]:
        raise UserError("repository identity changed; generate a new push plan")
    if run_git(repo, ["remote", "get-url", plan["remote"]]).stdout.strip() != plan["remote_url"]:
        raise UserError("remote URL changed; generate a new push plan")
    for branch, expected in plan["local"].items():
        actual = run_git(repo, ["show-ref", "--verify", "--hash", f"refs/heads/{branch}"]).stdout.strip()
        if actual != expected:
            raise UserError(f"local SHA changed for {branch}; generate a new push plan")
    snapshot = remote_refs(repo, plan["remote"], plan["branches"])
    if snapshot != plan["remote_snapshot"]:
        raise UserError("remote branch state changed; generate a new push plan")
    pushed: list[str] = []
    for index, command in enumerate(plan["commands"]):
        git_args = command[1:]
        result = run_git(repo, git_args, check=False)
        if result.returncode != 0:
            raise UserError(
                f"push failed after {len(pushed)} command(s); no automatic fallback was used: "
                f"{result.stderr.strip()}"
            )
        if plan["mode"] == "atomic":
            pushed.extend(plan["pending"])
        else:
            pushed.append(plan["pending"][index])
    return {"pushed": pushed, "synced": plan["synced"], "mode": plan["mode"], "source_sha": plan["source_sha"]}


def cmd_config(args: argparse.Namespace) -> None:
    """Handle configuration subcommands."""
    if args.config_action == "starter":
        emit(starter(args.name))
        return
    if args.config_action == "validate":
        value = read_json(Path(args.file).expanduser().resolve())
        emit({"valid": True, "warnings": validate_config(value)})
        return
    repo = repo_root(args.repo)
    global_path, project_path, key, _ = config_paths(repo)
    if args.config_action == "show":
        config, meta = effective_config(repo)
        emit({
            **meta,
            "global_previous_path": str(previous_path(global_path)),
            "project_previous_path": str(previous_path(project_path)),
            "effective": config,
        })
        return
    if args.config_action == "options":
        emit(config_options(repo, args.slug, parse_vars(args.var)))
        return
    if args.config_action == "discover":
        emit(discover_branch_patterns(repo, args.limit))
        return
    if args.config_action == "preview":
        value = read_json(Path(args.file).expanduser().resolve())
        emit(preview_config(repo, args.scope, value, args.slug, parse_vars(args.var)))
        return
    target = global_path if args.scope == "global" else project_path
    if args.config_action == "set":
        value = read_json(Path(args.file).expanduser().resolve())
        merge_for_scope(repo, args.scope, value)
        save_with_history(target, value)
        emit({
            "saved": True,
            "scope": args.scope,
            "path": str(target),
            "previous_path": str(previous_path(target)),
            "project_key": key,
        })
        return
    if args.config_action == "update-sprint":
        current = read_json(target) if target.exists() else {}
        updated = deep_merge(current, {"variables": {"sprint": {"default": args.value}}})
        merge_for_scope(repo, args.scope, updated)
        preview = {"scope": args.scope, "path": str(target), "updated": updated}
        if args.confirm != "APPLY":
            emit({**preview, "saved": False, "confirmation_required": "--confirm APPLY"})
            return
        save_with_history(target, updated)
        emit({**preview, "saved": True, "previous_path": str(previous_path(target))})
        return
    if args.config_action == "restore":
        history = previous_path(target)
        if not history.exists():
            raise UserError(f"no previous configuration is available: {history}")
        restore_value = read_json(history)
        current_value = snapshot(target)
        if restore_value != ABSENT_SNAPSHOT:
            merge_for_scope(repo, args.scope, restore_value)
        action = "remove" if restore_value == ABSENT_SNAPSHOT else "replace"
        preview = {
            "scope": args.scope,
            "path": str(target),
            "previous_path": str(history),
            "restore_action": action,
            "current": None if current_value == ABSENT_SNAPSHOT else current_value,
            "restored": None if restore_value == ABSENT_SNAPSHOT else restore_value,
        }
        if args.confirm != "RESTORE":
            emit({**preview, "saved": False, "confirmation_required": "--confirm RESTORE"})
            return
        if restore_value == ABSENT_SNAPSHOT:
            atomic_write_json(history, current_value)
            target.unlink(missing_ok=True)
        else:
            atomic_write_json(target, restore_value)
            atomic_write_json(history, current_value)
        emit({**preview, "saved": True})
        return
    if args.confirm != "RESET":
        raise UserError(f"reset requires --confirm RESET; target would be {target}")
    existed = target.exists()
    if existed:
        history = previous_path(target)
        history.parent.mkdir(parents=True, exist_ok=True)
        os.replace(target, history)
    emit({
        "reset": existed,
        "scope": args.scope,
        "path": str(target),
        "previous_path": str(previous_path(target)),
    })


def build_parser() -> argparse.ArgumentParser:
    """Build the command-line interface."""
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest="command", required=True)

    project = sub.add_parser("project-key")
    project.add_argument("--repo", default=".")

    config = sub.add_parser("config")
    config_sub = config.add_subparsers(dest="config_action", required=True)
    starter_cmd = config_sub.add_parser("starter")
    starter_cmd.add_argument("name", choices=("generic", "sprint", "blank"))
    validate_cmd = config_sub.add_parser("validate")
    validate_cmd.add_argument("--file", required=True)
    show_cmd = config_sub.add_parser("show")
    show_cmd.add_argument("--repo", default=".")
    options_cmd = config_sub.add_parser("options")
    options_cmd.add_argument("--repo", default=".")
    options_cmd.add_argument("--slug")
    options_cmd.add_argument("--var", action="append", default=[])
    discover_cmd = config_sub.add_parser("discover")
    discover_cmd.add_argument("--repo", default=".")
    discover_cmd.add_argument("--limit", type=int, default=3)
    preview_cmd = config_sub.add_parser("preview")
    preview_cmd.add_argument("--repo", default=".")
    preview_cmd.add_argument("--scope", choices=("global", "project"), required=True)
    preview_cmd.add_argument("--file", required=True)
    preview_cmd.add_argument("--slug", required=True)
    preview_cmd.add_argument("--var", action="append", default=[])
    set_cmd = config_sub.add_parser("set")
    set_cmd.add_argument("--repo", default=".")
    set_cmd.add_argument("--scope", choices=("global", "project"), required=True)
    set_cmd.add_argument("--file", required=True)
    reset_cmd = config_sub.add_parser("reset")
    reset_cmd.add_argument("--repo", default=".")
    reset_cmd.add_argument("--scope", choices=("global", "project"), required=True)
    reset_cmd.add_argument("--confirm")
    restore_cmd = config_sub.add_parser("restore")
    restore_cmd.add_argument("--repo", default=".")
    restore_cmd.add_argument("--scope", choices=("global", "project"), required=True)
    restore_cmd.add_argument("--confirm")
    sprint_cmd = config_sub.add_parser("update-sprint")
    sprint_cmd.add_argument("--repo", default=".")
    sprint_cmd.add_argument("--scope", choices=("global", "project"), required=True)
    sprint_cmd.add_argument("--value", required=True)
    sprint_cmd.add_argument("--confirm")

    inspect = sub.add_parser("inspect")
    inspect.add_argument("--repo", default=".")
    inspect.add_argument("--source", default="HEAD")

    validate_name = sub.add_parser("validate-base")
    validate_name.add_argument("--repo", default=".")
    validate_name.add_argument("--base", required=True)

    expand = sub.add_parser("expand")
    expand.add_argument("--repo", default=".")
    expand.add_argument("--profile")
    expand.add_argument("--slug", required=True)
    expand.add_argument("--var", action="append", default=[])
    expand.add_argument("--target-add", action="append", default=[])
    expand.add_argument("--target-remove", action="append", default=[])

    create = sub.add_parser("create-local")
    create.add_argument("--repo", default=".")
    create.add_argument("--source-sha", required=True)
    create.add_argument("--branch", action="append", required=True)

    local_plan = sub.add_parser("local-plan")
    local_plan.add_argument("--repo", default=".")
    local_plan.add_argument("--source-sha", required=True)
    local_plan.add_argument("--branch", action="append", required=True)

    plan = sub.add_parser("push-plan")
    plan.add_argument("--repo", default=".")
    plan.add_argument("--remote")
    plan.add_argument("--source-sha", required=True)
    plan.add_argument("--branch", action="append", required=True)
    plan.add_argument("--plan-file", required=True)
    plan.add_argument("--mode", choices=("atomic", "sequential"), default="atomic")
    plan.add_argument("--set-upstream", action=argparse.BooleanOptionalAction, default=None)

    push = sub.add_parser("push")
    push.add_argument("--plan-file", required=True)
    push.add_argument("--confirm", required=True)
    return parser


def main() -> None:
    """Dispatch the selected command and normalize expected errors."""
    parser = build_parser()
    args = parser.parse_args()
    try:
        if args.command == "project-key":
            repo = repo_root(args.repo)
            key, source = project_identity(repo)
            emit({"project_key": key, "identity_source": source})
        elif args.command == "config":
            cmd_config(args)
        elif args.command == "inspect":
            emit(inspect_source(repo_root(args.repo), args.source))
        elif args.command == "validate-base":
            repo = repo_root(args.repo)
            config, _ = effective_config(repo)
            validate_config(config)
            validate_base(repo, args.base, config["naming"])
            emit({"valid": True, "base": args.base})
        elif args.command == "expand":
            repo = repo_root(args.repo)
            config, _ = effective_config(repo)
            validate_config(config)
            profile = args.profile
            if profile is None:
                if len(config["profiles"]) > 1:
                    raise UserError(
                        "multiple branch combinations are configured; --profile is required. "
                        "Run `config options` to list them all and let the user choose."
                    )
                profile = config["defaults"]["profile"]
            emit(
                expand_branches(
                    repo,
                    config,
                    profile,
                    args.slug,
                    parse_vars(args.var),
                    args.target_add,
                    args.target_remove,
                )
            )
        elif args.command == "create-local":
            emit(create_local(repo_root(args.repo), args.source_sha, args.branch))
        elif args.command == "local-plan":
            repo = repo_root(args.repo)
            source_sha = resolve_commit(repo, args.source_sha)
            if source_sha != args.source_sha:
                raise UserError("source-sha must be the full resolved commit SHA")
            states = local_states(repo, args.branch, source_sha)
            emit({
                "source_sha": source_sha,
                "branches": states,
                "blocked": any(item["status"] == "collision" for item in states),
                "git_mutation": False,
            })
        elif args.command == "push-plan":
            repo = repo_root(args.repo)
            config, _ = effective_config(repo)
            validate_config(config)
            remote = args.remote or config["defaults"]["remote"]
            upstream = config["push"]["set_upstream"] if args.set_upstream is None else args.set_upstream
            emit(
                build_push_plan(
                    repo,
                    remote,
                    args.source_sha,
                    args.branch,
                    Path(args.plan_file),
                    args.mode,
                    upstream,
                )
            )
        elif args.command == "push":
            emit(execute_push(Path(args.plan_file), args.confirm))
        else:
            parser.error("unknown command")
    except UserError as exc:
        print(json.dumps({"error": str(exc)}, ensure_ascii=False), file=sys.stderr)
        raise SystemExit(2) from exc


if __name__ == "__main__":
    main()
