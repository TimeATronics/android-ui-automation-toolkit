#!/usr/bin/env python3
"""Fill a Cocoon metadata editor with text from the command line or a JSON file.

The game's popup menu should normally be open when this starts. The default
flow is:

  controller Y -> Edit App -> controller Enter -> Edit Metadata
  fill Publisher / Release Date / Description (and optionally Title)
  save with the top-right Y action

Coordinates are device/UI-version specific. Edit cocoon_config.example.json or
make a private copy after calibrating against a screenshot.

This script only talks to the device through adb; it does not touch any
database or app-private files.
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any, Optional

from adb_ui import AdbUi

DEFAULT_CONFIG = Path(__file__).with_name("cocoon_config.example.json")


def load_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def first_value(data: dict[str, Any], *keys: str) -> str:
    for key in keys:
        value = data.get(key)
        if value is not None:
            return str(value)
    return ""


def load_metadata(path: Path) -> dict[str, str]:
    data = load_json(path)
    if not isinstance(data, dict):
        raise ValueError("metadata JSON must contain an object")
    return {
        "title": first_value(data, "title", "Title"),
        "publisher": first_value(data, "publisher", "Publisher"),
        "release_date": first_value(data, "release_date", "release", "Release Date"),
        "description": first_value(data, "description", "Description"),
    }


def load_config(path: Path) -> dict[str, Any]:
    data = load_json(path)
    if not isinstance(data, dict):
        raise ValueError("config JSON must contain an object")
    return data


def point(config: dict[str, Any], key: str) -> tuple[int, int]:
    value = config[key]
    return int(value["x"]), int(value["y"])


def field_point(config: dict[str, Any], name: str) -> tuple[int, int]:
    field = config["fields"][name]
    return int(field.get("x", config["action_x"])), int(field["y"])


def fill_field(ui: AdbUi, config: dict[str, Any], name: str, text: str) -> None:
    if not text:
        return
    x, y = field_point(config, name)
    print(f"  {name}: {text}")
    ui.tap(x, y, settle=float(config.get("field_settle_seconds", 0.55)))
    paste = point(config, "paste")
    confirm = point(config, "confirm")
    ui.paste(
        paste[0], paste[1],
        confirm[0], confirm[1],
        text=text,
        settle=float(config.get("field_settle_seconds", 0.55)),
    )


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--metadata", type=Path,
                        help="JSON file containing title/publisher/release_date/description")
    parser.add_argument("--title", help="Title to set when --set-title is used")
    parser.add_argument("--publisher", help="Publisher value")
    parser.add_argument("--release-date", help="Release date, preferably YYYY-MM-DD")
    parser.add_argument("--description", help="Description value")
    parser.add_argument("--set-title", action="store_true",
                        help="Also edit the Title field")
    parser.add_argument("--editor-open", action="store_true",
                        help="Skip the Y/Enter open sequence (metadata editor is already open)")
    parser.add_argument("--config", type=Path, default=DEFAULT_CONFIG,
                        help="Coordinate config JSON (default: cocoon_config.example.json)")
    parser.add_argument("--adb", help="Path to adb (default: ADB env var or PATH)")
    parser.add_argument("--serial", help="Device serial (default: ANDROID_SERIAL)")
    parser.add_argument("--helper", default=None,
                        help="Clipboard helper component (default: built-in)")
    parser.add_argument("--screenshot", type=Path,
                        help="Save a screenshot after saving")
    parser.add_argument("--dry-run", action="store_true",
                        help="Print values and exit without touching the device")
    args = parser.parse_args()

    values: dict[str, str] = {"title": "", "publisher": "",
                              "release_date": "", "description": ""}
    if args.metadata:
        values.update(load_metadata(args.metadata))
    for key, value in (
        ("title", args.title),
        ("publisher", args.publisher),
        ("release_date", args.release_date),
        ("description", args.description),
    ):
        if value is not None:
            values[key] = value

    if not any(values.values()):
        parser.error("provide --metadata or at least one of --publisher, --release-date, --description, --title")

    config = load_config(args.config)
    print(f"config: {args.config}")
    print(f"values: {json.dumps(values, ensure_ascii=False)}")
    if args.dry_run:
        return 0

    ui = AdbUi(
        adb=args.adb,
        serial=args.serial,
        helper_component=args.helper or "com.ayaneo.cliphelper/.MainActivity",
    )
    focus = ui.current_focus()
    print(f"focus: {focus or 'unknown'}")
    expected = str(config.get("expected_package", "")).lower()
    if expected and expected not in focus.lower():
        print(f"warning: expected focus package {expected!r}")

    if not args.editor_open:
        opening = config.get("open", {})
        settle = float(opening.get("settle_seconds", 0.8))
        print("opening Edit App -> Edit Metadata")
        ui.keyevent(opening.get("edit_app_key", 53), settle=settle)
        ui.keyevent(opening.get("enter_key", 23), settle=settle)

    if args.set_title:
        fill_field(ui, config, "title", values["title"])
    fill_field(ui, config, "publisher", values["publisher"])
    fill_field(ui, config, "release_date", values["release_date"])
    fill_field(ui, config, "description", values["description"])

    save = point(config, "save")
    print("saving metadata")
    ui.tap(save[0], save[1], settle=float(config.get("save_settle_seconds", 1.0)))
    if args.screenshot:
        ui.screenshot(args.screenshot)
        print(f"screenshot: {args.screenshot}")
    print("done")
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except Exception as exc:  # noqa: BLE001 - CLI error reporting
        print(f"error: {exc}", file=sys.stderr)
        raise SystemExit(1)
