#!/usr/bin/env python3
"""
assignment_manager.py
=====================
管理 Android 面試作業題目的 CRUD 工具。

儲存位置：${XDG_DATA_HOME:-$HOME/.local/share}/claude-forge/android-hw-grader/assignments/<name>.json

CLI 介面：
  python3 assignment_manager.py list                          # 列出所有題目（JSON 陣列）
  python3 assignment_manager.py get <name>                    # 取得題目（JSON 物件）
  python3 assignment_manager.py add --name <n> --prompt-file <path>  # 從檔案讀取 prompt
  python3 assignment_manager.py add --name <n> --prompt -     # 從 stdin 讀取 prompt
  python3 assignment_manager.py update --name <n> --prompt -  # 更新題目 prompt（stdin）
  python3 assignment_manager.py delete <name>                 # 刪除題目

所有輸出為 JSON 格式（包含錯誤）。
"""
from __future__ import annotations

import argparse
import json
import os
import re
import sys
from datetime import datetime
from pathlib import Path
from typing import Any


def get_data_dir() -> Path:
    """取得資料儲存目錄。"""
    xdg_data = os.environ.get("XDG_DATA_HOME", "")
    if xdg_data:
        base = Path(xdg_data)
    else:
        base = Path.home() / ".local" / "share"
    return base / "claude-forge" / "android-hw-grader" / "assignments"


def validate_name(name: str) -> bool:
    """驗證題目名稱：允許中文、英數字、底線、連字號，不允許空白與特殊符號。"""
    return bool(re.fullmatch(r"[\w\u4e00-\u9fff\u3400-\u4dbf-]+", name))


def json_output(data: dict[str, Any] | list[Any]) -> None:
    """以 JSON 格式輸出到 stdout。"""
    print(json.dumps(data, ensure_ascii=False, indent=2))


def json_error(message: str, code: int = 1) -> None:
    """以 JSON 格式輸出錯誤並結束。"""
    json_output({"error": message})
    sys.exit(code)


def cmd_list(args: argparse.Namespace) -> None:
    """列出所有題目。"""
    data_dir = get_data_dir()
    if not data_dir.exists():
        json_output([])
        return

    assignments: list[dict[str, str]] = []
    for f in sorted(data_dir.glob("*.json")):
        try:
            item = json.loads(f.read_text(encoding="utf-8"))
            assignments.append({
                "name": item["name"],
                "created_at": item.get("created_at", ""),
            })
        except (json.JSONDecodeError, KeyError):
            continue

    json_output(assignments)


def cmd_get(args: argparse.Namespace) -> None:
    """取得指定題目的完整內容。"""
    name: str = args.name
    if not validate_name(name):
        json_error(f"無效的題目名稱：{name}（僅允許中文、英數字、底線、連字號）")

    data_dir = get_data_dir()
    path = data_dir / f"{name}.json"
    if not path.exists():
        json_error(f"找不到題目：{name}")

    item = json.loads(path.read_text(encoding="utf-8"))
    json_output(item)


def cmd_add(args: argparse.Namespace) -> None:
    """新增題目。"""
    name: str = args.name
    if not validate_name(name):
        json_error(f"無效的題目名稱：{name}（僅允許中文、英數字、底線、連字號）")

    # 讀取 prompt 內容
    if args.prompt_file:
        prompt_path = Path(args.prompt_file)
        if not prompt_path.exists():
            json_error(f"找不到檔案：{args.prompt_file}")
        prompt = prompt_path.read_text(encoding="utf-8").strip()
    elif args.prompt == "-":
        prompt = sys.stdin.read().strip()
    else:
        json_error("必須指定 --prompt-file <path> 或 --prompt -")

    if not prompt:
        json_error("prompt 內容不可為空")

    data_dir = get_data_dir()
    data_dir.mkdir(parents=True, exist_ok=True)

    path = data_dir / f"{name}.json"
    if path.exists():
        json_error(f"題目已存在：{name}（請先刪除再新增）")

    item = {
        "name": name,
        "prompt": prompt,
        "created_at": datetime.now().isoformat(timespec="seconds"),
    }
    path.write_text(json.dumps(item, ensure_ascii=False, indent=2), encoding="utf-8")
    json_output({"status": "created", "name": name, "path": str(path)})


def cmd_update(args: argparse.Namespace) -> None:
    """更新指定題目的 prompt。"""
    name: str = args.name
    if not validate_name(name):
        json_error(f"無效的題目名稱：{name}（僅允許中文、英數字、底線、連字號）")

    data_dir = get_data_dir()
    path = data_dir / f"{name}.json"
    if not path.exists():
        json_error(f"找不到題目：{name}")

    # 讀取新 prompt 內容
    if args.prompt_file:
        prompt_path = Path(args.prompt_file)
        if not prompt_path.exists():
            json_error(f"找不到檔案：{args.prompt_file}")
        prompt = prompt_path.read_text(encoding="utf-8").strip()
    elif args.prompt == "-":
        prompt = sys.stdin.read().strip()
    else:
        json_error("必須指定 --prompt-file <path> 或 --prompt -")

    if not prompt:
        json_error("prompt 內容不可為空")

    item = json.loads(path.read_text(encoding="utf-8"))
    item["prompt"] = prompt
    item["updated_at"] = datetime.now().isoformat(timespec="seconds")
    path.write_text(json.dumps(item, ensure_ascii=False, indent=2), encoding="utf-8")
    json_output({"status": "updated", "name": name, "path": str(path)})


def cmd_delete(args: argparse.Namespace) -> None:
    """刪除指定題目。"""
    name: str = args.name
    if not validate_name(name):
        json_error(f"無效的題目名稱：{name}（僅允許中文、英數字、底線、連字號）")

    data_dir = get_data_dir()
    path = data_dir / f"{name}.json"
    if not path.exists():
        json_error(f"找不到題目：{name}")

    path.unlink()
    json_output({"status": "deleted", "name": name})


def main() -> None:
    """主程式進入點。"""
    parser = argparse.ArgumentParser(
        description="Android 面試作業題目管理工具",
    )
    subparsers = parser.add_subparsers(dest="command", required=True)

    # list
    subparsers.add_parser("list", help="列出所有題目")

    # get
    get_parser = subparsers.add_parser("get", help="取得指定題目")
    get_parser.add_argument("name", help="題目名稱")

    # add
    add_parser = subparsers.add_parser("add", help="新增題目")
    add_parser.add_argument("--name", required=True, help="題目名稱（中文、英數字、底線、連字號）")
    prompt_group = add_parser.add_mutually_exclusive_group(required=True)
    prompt_group.add_argument("--prompt-file", help="從檔案讀取 prompt")
    prompt_group.add_argument("--prompt", help="使用 - 從 stdin 讀取 prompt")

    # update
    update_parser = subparsers.add_parser("update", help="更新指定題目的 prompt")
    update_parser.add_argument("--name", required=True, help="題目名稱（中文、英數字、底線、連字號）")
    update_prompt_group = update_parser.add_mutually_exclusive_group(required=True)
    update_prompt_group.add_argument("--prompt-file", help="從檔案讀取新 prompt")
    update_prompt_group.add_argument("--prompt", help="使用 - 從 stdin 讀取新 prompt")

    # delete
    delete_parser = subparsers.add_parser("delete", help="刪除指定題目")
    delete_parser.add_argument("name", help="題目名稱")

    args = parser.parse_args()

    commands = {
        "list": cmd_list,
        "get": cmd_get,
        "add": cmd_add,
        "update": cmd_update,
        "delete": cmd_delete,
    }
    commands[args.command](args)


if __name__ == "__main__":
    main()
