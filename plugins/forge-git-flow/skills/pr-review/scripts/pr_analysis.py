#!/usr/bin/env python3
"""驗證並正規化 AI 寫出的分析結果（``analysis.json``）。

兩道主要的檢查都是為了讓 reviewer 可以信任頁面：

- **每個變更檔案剛好出現一次**：AI 沒分到的檔案自動進「未分組」，
  重複或不存在的路徑會被移除並列入警告，不會有檔案因為分組而消失。
- **意見的行號要落在 diff 裡**：對不上的意見降級成檔案層級或整體層級，
  不會被貼到錯的那一行。

導讀的部分（``guide``、每組的 ``focus``、檔案的 ``note``、行內的 ``annotations``）都是選填：
格式不對的項目會被略過並列入警告，不會讓整份分析失效。

``errors`` 代表格式不能用（不會存檔）；``warnings`` 代表已自動修正，但值得回頭修。
"""
from __future__ import annotations

import math
from typing import Any, Dict, List, Optional, Set, Tuple

from pr_diff import diff_line_numbers

SEVERITIES = ("P0", "P1", "P2")
UNGROUPED_ID = "ungrouped"
UNGROUPED_TITLE = "未分組"

# 六個評分項目與各自的滿分（加總 100）。
# 來源是 branch-diff-code-review 的 references/scoring-rubric.md，名稱照 analysis-schema.md 的範例；
# 規則檔改了這裡要跟著改，測試會比對兩邊是否一致。
SCORE_RUBRIC: Tuple[Tuple[str, int], ...] = (
    ("Correctness & Reliability", 30),
    ("Architecture & Design", 20),
    ("Readability & Maintainability", 15),
    ("Testability & Tests", 15),
    ("Performance & Resource", 10),
    ("Security / Privacy / Compliance", 10),
)


def _text(value: Any) -> str:
    return value.strip() if isinstance(value, str) else ""


def _is_number(value: Any) -> bool:
    """是不是有限的數字。``True``／``False`` 在 Python 裡也是整數，要另外排除。"""
    return isinstance(value, (int, float)) and not isinstance(value, bool) and math.isfinite(value)


def _category_key(name: Any) -> str:
    """比對評分項目名稱用的 key：不分大小寫、忽略空白，所以 ``Security/Privacy/Compliance`` 也對得上。"""
    return "".join(_text(name).casefold().split())


def _string_list(value: Any) -> List[str]:
    if not isinstance(value, list):
        return []
    return [item.strip() for item in value if isinstance(item, str) and item.strip()]


def _file_entry(item: Any) -> Tuple[str, str, bool]:
    """分組裡的一個檔案：路徑字串，或 ``{"path", "note", "skim"}``。回傳 ``(路徑, 說明, 可快速掃過)``。"""
    if isinstance(item, str):
        return item.strip(), "", False
    if isinstance(item, dict):
        return _text(item.get("path")), _text(item.get("note")), item.get("skim") is True
    return "", "", False


class _DiffLines:
    """查某個檔案的某一側有哪些行號出現在 diff 裡。"""

    def __init__(self, files: List[Dict[str, Any]]) -> None:
        self._by_path = {entry["path"]: entry for entry in files}
        self._cache: Dict[Tuple[str, str], Set[int]] = {}

    def has(self, path: str, side: str, line: int) -> bool:
        key = (path, side)
        if key not in self._cache:
            entry = self._by_path.get(path) or {}
            self._cache[key] = diff_line_numbers(entry.get("hunks") or [], side)
        return line in self._cache[key]


def _normalize_score(raw: Any, errors: List[str]) -> Optional[Dict[str, Any]]:
    if raw is None:
        errors.append("缺少 score（依 scoring-rubric.md 評分）。")
        return None
    if not isinstance(raw, dict):
        errors.append("score 必須是物件。")
        return None
    # total 與 items 分開檢查、錯誤一次列完：寫分析的 AI 才能一次改好，不用每修一項就重跑一次 ingest。
    before = len(errors)
    total = raw.get("total")
    if not _is_number(total) or not 0 <= total <= 100:
        errors.append("score.total 必須是 0 到 100 的數字。")
    items = _normalize_score_items(raw.get("items"), errors)
    if len(errors) > before:
        return None
    item_sum = sum(item["score"] for item in items)
    if abs(item_sum - total) > 0.01:
        errors.append(f"score.total（{total}）與 items 的加總（{item_sum}）不一致。")
        return None
    return {"total": total, "meaning": _text(raw.get("meaning")), "items": items}


def _normalize_score_items(raw_items: Any, errors: List[str]) -> List[Dict[str, Any]]:
    """檢查六個評分項目：每一項都要有、分數在 0 到滿分之間、滿分與評分規則一致。

    需求來源是 analysis-schema.md 的「score」：頁面會把總分與各項得分一起顯示，
    少了項目就變成一個沒有依據的總分。回傳的項目固定照評分規則的順序排，名稱也改回規則裡的寫法。
    """
    names = "、".join(name for name, _ in SCORE_RUBRIC)
    if not isinstance(raw_items, list) or not raw_items:
        errors.append(
            f"缺少 score.items：要列出 {len(SCORE_RUBRIC)} 個評分項目（{names}），每一項有 category、score、max。"
        )
        return []

    rubric = {_category_key(name): (name, maximum) for name, maximum in SCORE_RUBRIC}
    found: Dict[str, Dict[str, Any]] = {}
    for index, item in enumerate(raw_items, 1):
        if not isinstance(item, dict):
            errors.append(f"score.items 第 {index} 項不是物件。")
            continue
        key = _category_key(item.get("category"))
        if key not in rubric:
            errors.append(
                f"score.items 第 {index} 項的 category（{item.get('category')!r}）不是評分規則的項目；可以用的名稱：{names}。"
            )
            continue
        name, maximum = rubric[key]
        if key in found:
            errors.append(f"score.items 的「{name}」重複出現。")
            continue
        found[key] = {}  # 先佔位：這一項就算分數有問題，也不要再被報成「缺少」

        score, claimed_max = item.get("score"), item.get("max")
        if not _is_number(claimed_max) or abs(claimed_max - maximum) > 0.01:
            errors.append(f"score.items 的「{name}」的 max 應該是 {maximum}（收到 {claimed_max!r}）。")
        if not _is_number(score):
            errors.append(f"score.items 的「{name}」缺少數字的 score（收到 {score!r}）。")
        elif score < 0:
            errors.append(f"score.items 的「{name}」的 score（{score}）不能是負數。")
        elif score > maximum:
            errors.append(f"score.items 的「{name}」的 score（{score}）超過滿分 {maximum}。")
        else:
            found[key] = {"category": name, "score": score, "max": maximum, "notes": _text(item.get("notes"))}

    missing = [name for name, _ in SCORE_RUBRIC if _category_key(name) not in found]
    if missing:
        errors.append("score.items 缺少評分項目：" + "、".join(missing) + "。")
    return [found[_category_key(name)] for name, _ in SCORE_RUBRIC if found.get(_category_key(name))]


def _normalize_groups(
    raw_groups: Any,
    files: List[Dict[str, Any]],
    errors: List[str],
    warnings: List[str],
) -> Tuple[List[Dict[str, Any]], Dict[str, Dict[str, Any]]]:
    """回傳 ``(分組, 檔案說明)``；檔案說明以路徑為 key，只收有 ``note`` 或 ``skim`` 的檔案。"""
    file_notes: Dict[str, Dict[str, Any]] = {}
    if not isinstance(raw_groups, list) or not raw_groups:
        errors.append("groups 必須是非空的陣列（至少一組）。")
        return [], file_notes

    known = {entry["path"] for entry in files}
    renamed_from = {entry["old_path"]: entry["path"] for entry in files if entry.get("old_path")}
    assigned: Set[str] = set()
    used_ids: Set[str] = set()
    groups: List[Dict[str, Any]] = []

    for index, raw in enumerate(raw_groups, 1):
        if not isinstance(raw, dict):
            errors.append(f"groups 第 {index} 項不是物件。")
            continue
        title = _text(raw.get("title"))
        if not title:
            errors.append(f"groups 第 {index} 項缺少 title。")
            continue

        group_id = _text(raw.get("id")) or f"g{index}"
        if group_id in used_ids or group_id == UNGROUPED_ID:
            new_id = f"g{index}"
            while new_id in used_ids:
                new_id += "x"
            warnings.append(f"分組 id {group_id!r} 重複或是保留字，已改成 {new_id!r}。")
            group_id = new_id
        used_ids.add(group_id)

        paths: List[str] = []
        for item in raw.get("files") if isinstance(raw.get("files"), list) else []:
            path, note, skim = _file_entry(item)
            if not path:
                continue
            path = renamed_from.get(path, path)
            if path not in known:
                warnings.append(f"分組「{title}」列了不在這次變更裡的檔案，已移除：{path}")
            elif path in assigned:
                warnings.append(f"檔案被分到多個組，只保留第一次出現的位置：{path}")
            else:
                assigned.add(path)
                paths.append(path)
                if note or skim:
                    file_notes[path] = {"note": note, "skim": skim}

        groups.append(
            {
                "id": group_id,
                "title": title,
                "summary": _text(raw.get("summary")),
                "focus": _string_list(raw.get("focus")),
                "files": paths,
                "relations": raw.get("relations") if isinstance(raw.get("relations"), list) else [],
            }
        )

    ids = {group["id"] for group in groups}
    for group in groups:
        relations: List[Dict[str, str]] = []
        for relation in group["relations"]:
            if not isinstance(relation, dict):
                continue
            target, note = _text(relation.get("group")), _text(relation.get("note"))
            if target and target not in ids:
                warnings.append(f"分組「{group['title']}」的關聯指向不存在的分組：{target}")
                continue
            if target == group["id"] or not (target or note):
                continue
            relations.append({"group": target, "note": note})
        group["relations"] = relations

    empty = [group["title"] for group in groups if not group["files"]]
    if empty:
        warnings.append("以下分組沒有任何有效檔案，已移除：" + "、".join(empty))
        groups = [group for group in groups if group["files"]]
        kept = {group["id"] for group in groups}
        for group in groups:
            group["relations"] = [r for r in group["relations"] if not r["group"] or r["group"] in kept]

    missing = [entry["path"] for entry in files if entry["path"] not in assigned]
    if missing:
        reviewable_missing = [
            entry["path"]
            for entry in files
            if entry["path"] not in assigned and not entry.get("skipped_reason")
        ]
        if reviewable_missing:
            warnings.append(
                f"有 {len(reviewable_missing)} 個檔案沒被分到任何組，已放進「{UNGROUPED_TITLE}」："
                + "、".join(reviewable_missing[:10])
                + ("…" if len(reviewable_missing) > 10 else "")
            )
        groups.append(
            {
                "id": UNGROUPED_ID,
                "title": UNGROUPED_TITLE,
                "summary": "分析沒有涵蓋到的檔案，以及未納入審查的檔案（二進位、產物、lock 檔）。",
                "focus": [],
                "files": missing,
                "relations": [],
                "auto": True,
            }
        )
    return groups, file_notes


def _normalize_guide(raw: Any, group_ids: Set[str], warnings: List[str]) -> Optional[Dict[str, Any]]:
    """整個 PR 的導讀：背景、做法，以及一條貫穿變更的主線。什麼都沒寫時回傳 ``None``。"""
    if not isinstance(raw, dict):
        return None
    flow: List[Dict[str, str]] = []
    for item in raw.get("flow") if isinstance(raw.get("flow"), list) else []:
        if isinstance(item, str):
            text, group = item.strip(), ""
        elif isinstance(item, dict):
            text, group = _text(item.get("text")), _text(item.get("group"))
        else:
            continue
        if not text:
            continue
        if group and group not in group_ids:
            warnings.append(f"導讀的主線指向不存在的分組，已拿掉連結：{group}")
            group = ""
        flow.append({"text": text, "group": group})
    guide = {
        "background": _text(raw.get("background")),
        "approach": _text(raw.get("approach")),
        "flow": flow,
    }
    return guide if guide["background"] or guide["approach"] or flow else None


def _normalize_annotations(
    raw: Any,
    files: List[Dict[str, Any]],
    lines: _DiffLines,
    warnings: List[str],
) -> List[Dict[str, Any]]:
    """行內的導讀註解：和意見一樣要落在 diff 的行上，對不上的改放在檔案開頭。"""
    if not isinstance(raw, list):
        return []
    known = {entry["path"] for entry in files}
    renamed_from = {entry["old_path"]: entry["path"] for entry in files if entry.get("old_path")}
    annotations: List[Dict[str, Any]] = []
    for index, item in enumerate(raw, 1):
        if not isinstance(item, dict):
            continue
        text = _text(item.get("text"))
        if not text:
            continue
        path = _text(item.get("path"))
        path = renamed_from.get(path, path)
        if path not in known:
            warnings.append(f"導讀註解第 {index} 則指向不在這次變更裡的檔案，已略過：{path or '（沒有 path）'}")
            continue
        side = "old" if _text(item.get("side")).lower() == "old" else "new"
        line = _positive_int(item.get("line"))
        end_line = _positive_int(item.get("end_line"))
        if line is None or end_line is None or end_line < line:
            end_line = None

        anchor = "line"
        if line is None:
            anchor = "file"
        elif not lines.has(path, side, line):
            anchor = "file"
            side_label = "新" if side == "new" else "舊"
            warnings.append(
                f"導讀註解第 {index} 則的行號不在 diff 內（{path} {side_label}檔第 {line} 行），已改放在檔案開頭。"
            )
        annotations.append(
            {
                "id": f"n{len(annotations) + 1}",
                "path": path,
                "side": side,
                "line": line,
                "end_line": end_line,
                "anchor": anchor,
                "text": text,
            }
        )
    return annotations


def _positive_int(value: Any) -> Optional[int]:
    if isinstance(value, bool) or not isinstance(value, int) or value <= 0:
        return None
    return value


def _normalize_findings(
    raw_findings: Any,
    files: List[Dict[str, Any]],
    lines: _DiffLines,
    errors: List[str],
    warnings: List[str],
) -> List[Dict[str, Any]]:
    if raw_findings is None:
        return []
    if not isinstance(raw_findings, list):
        errors.append("findings 必須是陣列。")
        return []

    by_path = {entry["path"]: entry for entry in files}
    renamed_from = {entry["old_path"]: entry["path"] for entry in files if entry.get("old_path")}
    used_ids: Set[str] = set()
    findings: List[Dict[str, Any]] = []

    for index, raw in enumerate(raw_findings, 1):
        if not isinstance(raw, dict):
            errors.append(f"findings 第 {index} 項不是物件。")
            continue
        severity = _text(raw.get("severity")).upper()
        if severity not in SEVERITIES:
            errors.append(f"findings 第 {index} 項的 severity 必須是 P0、P1 或 P2。")
            continue
        title, body = _text(raw.get("title")), _text(raw.get("body"))
        if not title and not body:
            errors.append(f"findings 第 {index} 項沒有 title 也沒有 body。")
            continue

        finding_id = _text(raw.get("id")) or f"f{index}"
        if finding_id in used_ids:
            new_id = f"f{index}"
            while new_id in used_ids:
                new_id += "x"
            warnings.append(f"意見 id {finding_id!r} 重複，已改成 {new_id!r}。")
            finding_id = new_id
        used_ids.add(finding_id)

        path = _text(raw.get("path"))
        path = renamed_from.get(path, path)
        side = "old" if _text(raw.get("side")).lower() == "old" else "new"
        line = _positive_int(raw.get("line"))
        end_line = _positive_int(raw.get("end_line"))
        if line is None or end_line is None or end_line < line:
            end_line = None

        anchor = "line"
        entry = by_path.get(path)
        if not path:
            anchor = "general"
        elif entry is None:
            anchor = "general"
            warnings.append(f"意見 {finding_id} 指向不在這次變更裡的檔案，已改列為整體意見：{path}")
        elif line is None:
            anchor = "file"
        elif not lines.has(path, side, line):
            anchor = "file"
            side_label = "新" if side == "new" else "舊"
            warnings.append(
                f"意見 {finding_id} 的行號不在 diff 內（{path} {side_label}檔第 {line} 行），已改列為檔案層級。"
            )

        findings.append(
            {
                "id": finding_id,
                "severity": severity,
                "path": path if entry is not None else "",
                "claimed_path": path,
                "side": side,
                "line": line,
                "end_line": end_line,
                "anchor": anchor,
                "title": title,
                "body": body,
                "suggestion": _text(raw.get("suggestion")),
            }
        )
    return findings


def validate_analysis(
    raw: Any, files: List[Dict[str, Any]]
) -> Tuple[Optional[Dict[str, Any]], Dict[str, Any]]:
    """驗證分析結果，回傳 ``(正規化後的結果, 報告)``。有 ``errors`` 時結果為 ``None``。"""
    errors: List[str] = []
    warnings: List[str] = []

    if not isinstance(raw, dict):
        return None, {"ok": False, "errors": ["analysis.json 的最外層必須是物件。"], "warnings": []}

    summary = _text(raw.get("summary"))
    if not summary:
        errors.append("缺少 summary（這次變更在做什麼、整體風險、最重要的建議）。")

    lines = _DiffLines(files)
    score = _normalize_score(raw.get("score"), errors)
    groups, file_notes = _normalize_groups(raw.get("groups"), files, errors, warnings)
    findings = _normalize_findings(raw.get("findings"), files, lines, errors, warnings)
    guide = _normalize_guide(raw.get("guide"), {group["id"] for group in groups}, warnings)
    annotations = _normalize_annotations(raw.get("annotations"), files, lines, warnings)
    if groups and (guide is None or not guide["approach"]):
        warnings.append("沒有寫導讀（guide.approach）：頁面上會少了「這個 PR 怎麼做」的說明，請依 reading-guide.md 補上。")

    raw_notes = raw.get("notes") if isinstance(raw.get("notes"), dict) else {}
    notes = {
        "business": _string_list(raw_notes.get("business")),
        "testing": _string_list(raw_notes.get("testing")),
        "assumptions": _string_list(raw_notes.get("assumptions")),
    }

    by_severity = {level: 0 for level in SEVERITIES}
    by_anchor = {"line": 0, "file": 0, "general": 0}
    for finding in findings:
        by_severity[finding["severity"]] += 1
        by_anchor[finding["anchor"]] += 1

    report = {
        "ok": not errors,
        "errors": errors,
        "warnings": warnings,
        "stats": {
            "groups": len(groups),
            "files": len(files),
            "findings": len(findings),
            "by_severity": by_severity,
            "by_anchor": by_anchor,
            "annotations": len(annotations),
            "has_guide": guide is not None,
        },
    }
    if errors:
        return None, report

    normalized = {
        "summary": summary,
        "score": score,
        "guide": guide,
        "groups": groups,
        "file_notes": file_notes,
        "annotations": annotations,
        "findings": findings,
        "notes": notes,
    }
    return normalized, report


def fallback_groups(files: List[Dict[str, Any]], group_key) -> List[Dict[str, Any]]:
    """還沒有分析結果時，依路徑把檔案粗略分組，讓頁面仍然可以看 diff。"""
    buckets: Dict[str, List[str]] = {}
    for entry in files:
        buckets.setdefault(group_key(entry["path"]), []).append(entry["path"])
    return [
        {"id": f"g{index}", "title": key, "summary": "", "focus": [], "files": paths, "relations": [], "auto": True}
        for index, (key, paths) in enumerate(buckets.items(), 1)
    ]
