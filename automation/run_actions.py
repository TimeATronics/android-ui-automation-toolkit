#!/usr/bin/env python3
"""Execute a JSON list of UI actions against an Android device."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any

from adb_ui import AdbUi


def point(value: Any, name: str) -> tuple[int, int]:
    if isinstance(value, (list, tuple)) and len(value) == 2:
        return int(value[0]), int(value[1])
    if isinstance(value, str):
        parts = value.replace(",", " ").split()
        if len(parts) == 2:
            return int(parts[0]), int(parts[1])
    raise ValueError(f"{name} must be [x, y] or 'x,y'")


def run_action(ui: AdbUi, action: dict[str, Any]) -> None:
    kind = action.get("type")
    if not kind:
        raise ValueError("action is missing a 'type'")

    if kind == "wait":
        ui.sleep(float(action.get("seconds", 0.5)))
    elif kind == "tap":
        ui.tap(int(action["x"]), int(action["y"]),
               settle=float(action.get("settle", 0.08)))
    elif kind == "long_press":
        ui.long_press(int(action["x"]), int(action["y"]),
                      ms=int(action.get("ms", 1100)),
                      settle=float(action.get("settle", 0.5)))
    elif kind == "keyevent":
        ui.keyevent(action["key"], settle=float(action.get("settle", 0.08)))
    elif kind == "swipe":
        x1, y1 = point(action.get("start"), "start")
        x2, y2 = point(action.get("end"), "end")
        ui.swipe(x1, y1, x2, y2, ms=int(action.get("ms", 300)))
    elif kind == "set_clipboard":
        ui.set_clipboard(str(action["text"]))
    elif kind == "paste":
        target = action.get("target")
        if target is not None:
            tx, ty = point(target, "target")
            ui.tap(tx, ty, settle=float(action.get("target_settle", 0.5)))
        paste_xy = point(action["paste"], "paste")
        confirm_xy = point(action["confirm"], "confirm")
        text = action.get("text")
        ui.paste(
            paste_xy[0], paste_xy[1],
            confirm_xy[0], confirm_xy[1],
            text=None if text is None else str(text),
            settle=float(action.get("settle", 0.4)),
        )
    elif kind == "screenshot":
        path = action.get("path", "screen.png")
        ui.screenshot(path)
        print(f"screenshot: {path}")
    else:
        raise ValueError(f"unsupported action type: {kind!r}")


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("actions", help="Path to a JSON action list")
    parser.add_argument("--adb", help="Path to adb (default: ADB env var or PATH)")
    parser.add_argument("--serial", help="Device serial (default: ANDROID_SERIAL)")
    parser.add_argument("--helper", default=None,
                        help="Clipboard helper component (default: built-in)")
    parser.add_argument("--dry-run", action="store_true",
                        help="Print actions without touching the device")
    args = parser.parse_args()

    actions_path = Path(args.actions)
    actions = json.loads(actions_path.read_text(encoding="utf-8"))
    if not isinstance(actions, list):
        raise SystemExit("actions file must contain a JSON list")

    if args.dry_run:
        print(json.dumps(actions, indent=2, ensure_ascii=False))
        return 0

    ui = AdbUi(adb=args.adb, serial=args.serial,
               helper_component=args.helper or "com.ayaneo.cliphelper/.MainActivity")

    print(f"focus: {ui.current_focus() or 'unknown'}")
    for index, action in enumerate(actions, start=1):
        print(f"[{index}/{len(actions)}] {action.get('type', '?')}")
        run_action(ui, action)
    print("done")
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except Exception as exc:  # noqa: BLE001 - CLI error reporting
        print(f"error: {exc}", file=sys.stderr)
        raise SystemExit(1)
