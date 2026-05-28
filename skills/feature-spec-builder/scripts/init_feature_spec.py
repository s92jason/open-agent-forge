#!/usr/bin/env python3
from __future__ import annotations

import argparse
from pathlib import Path
from datetime import date

FLOW_MERMAID_BLOCK = """~~~mermaid
flowchart TD
    A[Entry] --> B[Main Screen]
~~~"""

IO_MERMAID_BLOCK = """~~~mermaid
flowchart LR
    subgraph Inputs
        UI[User Action]
        API[API Response]
    end
    subgraph Processing
        VM[ViewModel]
    end
    subgraph Outputs
        Screen[UI Render]
        Nav[Navigation]
        Track[Analytics]
    end
    UI --> VM
    API --> VM
    VM --> Screen
    VM --> Nav
    VM --> Track
~~~"""

TEMPLATE = """# Feature Spec: {feature_name}

Status: Draft
Last Updated: {today}
Mode: Create
Structure: Human Zone (Document Status → UI Logic) | AI Zone (Input/Output → Change Log)

## TL;DR
-
-
-
-

## Pending Summary
- [Pending] Axure / Figma intake not completed

## Scope

### In Scope
-

### Out of Scope
-

### This Change
- Initial draft created

## Flow

### Main Flow
{flow_mermaid_block}

### Flow Notes
- Entry:
- Main flow:
- Alternate flow:
- Failure / retry / back:

## Screens / Components
### <Screen Name>
- Purpose:
- Key components:
- Related flow:

## UI Logic & State Rules

### Main Screen
**Purpose**
-

| State | Trigger | UI Behavior | CTA | Notes |
|---|---|---|---|---|
| Loading |  |  |  |  |
| Success |  |  |  |  |
| Empty |  |  |  |  |
| Error |  |  |  |  |

**Key interactions**
-

---
> **AI Reference Zone** — 以下章節為結構化工程資料，主要供 AI Agent 與深度查找使用。
---

## Input / Output

{io_mermaid_block}

### User Input
-

### Data Input
-

### UI Output
-

### Navigation Output
-

### Analytics / Side Effects
-

## API / Data Contract

### Confirmed
-

### Pending confirmation
- [Pending]

### Error / fallback handling
-

## QA Checklist / Edge Cases
| Scenario | Trigger | Expected |
|---|---|---|
| Happy path |  |  |

## Technical Notes
-

## References
- Axure: <link> —
- Figma: <link> —
- API: <link> —
- Code path: <path> —

## Open Questions / Pending Items
-

## Change Log
- {today}: Initial draft created by init_feature_spec.py
"""


def build_content(feature_name: str) -> str:
    return TEMPLATE.format(
        feature_name=feature_name.strip(),
        today=date.today().isoformat(),
        flow_mermaid_block=FLOW_MERMAID_BLOCK,
        io_mermaid_block=IO_MERMAID_BLOCK,
    )


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Initialize a FEATURE-SPEC.md skeleton."
    )
    parser.add_argument("--feature", required=True, help="Feature display name")
    parser.add_argument("--output", required=True, help="Output markdown file path")
    parser.add_argument(
        "--force",
        action="store_true",
        help="Overwrite existing file if it already exists",
    )
    args = parser.parse_args()

    output_path = Path(args.output)
    output_path.parent.mkdir(parents=True, exist_ok=True)

    if output_path.exists() and not args.force:
        raise SystemExit(f"Refusing to overwrite existing file: {output_path}")

    content = build_content(args.feature)
    output_path.write_text(content, encoding="utf-8")
    print(f"Created {output_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())