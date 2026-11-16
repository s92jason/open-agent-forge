# Branch Diff Code Review Report

## Scope
- Current branch: <branch>
- Base ref guess: <base-ref>
- Base commit (branch point): <base-commit>
- Head: <head-commit>
- Range: <base-commit>..HEAD
- Files changed: <n> (A:<a> M:<m> D:<d> R:<r>)
- Total diff: +<additions> / -<deletions>
- Bundle: .ai-artifacts/branch-diff-code-review/<all-in-one.md or chunks/>

## Executive summary
<3–8 句，講清楚：這次改動在做什麼、整體風險、最重要的 1–3 個建議>

## P0 (Blockers)
- [file:line] <issue> — <why it matters> — <what to do>

## P1 (Should fix)
- ...

## P2 (Nice to have)
- ...

## File-by-file notes
### <path>
- <note 1> (ref: diff hunk / line range)
- <note 2>

## Business logic / Product notes
- <behavior change>
- <edge case risk>
- <metrics/analytics implications>
- <operational concerns>

## Testing recommendations
- Unit tests:
- Integration/E2E:
- Regression hotspots:

## Score (max 100)
| Category | Score | Notes |
|---|---:|---|
| Correctness & Reliability (30) | <x>/30 | <扣分理由/亮點> |
| Architecture & Design (20) | <x>/20 | ... |
| Readability & Maintainability (15) | <x>/15 | ... |
| Testability & Tests (15) | <x>/15 | ... |
| Performance & Resource (10) | <x>/10 | ... |
| Security / Privacy / Compliance (10) | <x>/10 | ... |
| **Total** | **<total>/100** | <一句解釋這分數意味著什麼> |

## Assumptions & limitations
- <base-ref 推斷方式>
- <被排除或被截斷的檔案>
- <任何可能影響結論的限制>
