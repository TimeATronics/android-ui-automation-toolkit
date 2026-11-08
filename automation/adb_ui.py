"""Small ADB UI-automation wrapper used by the example scripts.

The module intentionally has no third-party dependencies. It is a thin layer
over adb commands that makes tapping, long-pressing, screenshots, and clipboard
pasting less error-prone.
"""

from __future__ import annotations

import base64
import os
import shutil
import subprocess
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Optional, Sequence

DEFAULT_HELPER_COMPONENT = "com.ayaneo.cliphelper/.MainActivity"


class AdbError(RuntimeError):
    """Raised when an adb command fails."""


def _resolve_adb(adb: Optional[str]) -> str:
    if adb:
        return adb
    from_env = os.environ.get("ADB")
    if from_env:
        return from_env
    return shutil.which("adb") or "adb"


@dataclass
class AdbUi:
    """Convenience wrapper around one Android device."""

    adb: Optional[str] = None
    serial: Optional[str] = None
    helper_component: str = DEFAULT_HELPER_COMPONENT

    def __post_init__(self) -> None:
        self.adb = _resolve_adb(self.adb)
        if self.serial is None:
            self.serial = os.environ.get("ANDROID_SERIAL")

    def command(self, *args: str) -> list[str]:
        cmd = [self.adb]  # type: ignore[list-item]
        if self.serial:
            cmd.extend(["-s", self.serial])
        cmd.extend(str(arg) for arg in args)
        return cmd

    def run(self, *args: str, check: bool = True) -> str:
        """Run an adb command and return its captured text output."""
        proc = subprocess.run(
            self.command(*args),
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            check=False,
        )
        if check and proc.returncode != 0:
            details = (proc.stderr or proc.stdout or "").strip()
            raise AdbError(
                f"adb command failed ({proc.returncode}): "
                f"{' '.join(self.command(*args))}\n{details}"
            )
        return proc.stdout

    def shell(self, *args: str, check: bool = True) -> str:
        """Run an adb shell command and return its output."""
        return self.run("shell", *args, check=check)

    def tap(self, x: int, y: int, settle: float = 0.08) -> None:
        self.shell("input", "tap", str(int(x)), str(int(y)))
        self.sleep(settle)

    def keyevent(self, key: int | str, settle: float = 0.08) -> None:
        self.shell("input", "keyevent", str(key))
        self.sleep(settle)

    def long_press(self, x: int, y: int, ms: int = 1100, settle: float = 0.5) -> None:
        """Long-press with separate DOWN/UP events.

        In practice this is much more reliable than `input swipe x y x y ms`
        on controller-first launchers.
        """
        try:
            self.shell("input", "motionevent", "DOWN", str(int(x)), str(int(y)))
            time.sleep(max(0, ms) / 1000.0)
            self.shell("input", "motionevent", "UP", str(int(x)), str(int(y)))
        except AdbError:
            # Older/odd builds may not expose motionevent through shell.
            self.shell("input", "swipe", str(int(x)), str(int(y)),
                       str(int(x)), str(int(y)), str(int(ms)))
        self.sleep(settle)

    def swipe(self, x1: int, y1: int, x2: int, y2: int,
              ms: int = 300, settle: float = 0.2) -> None:
        self.shell("input", "swipe", str(int(x1)), str(int(y1)),
                   str(int(x2)), str(int(y2)), str(int(ms)))
        self.sleep(settle)

    def sleep(self, seconds: float) -> None:
        if seconds > 0:
            time.sleep(seconds)

    def screenshot(self, path: Optional[str | Path] = None) -> bytes:
        """Capture the screen. Returns the PNG bytes and optionally writes a file."""
        proc = subprocess.run(
            self.command("exec-out", "screencap", "-p"),
            capture_output=True,
            check=False,
        )
        if proc.returncode != 0:
            details = (proc.stderr or b"").decode("utf-8", "replace").strip()
            raise AdbError(f"screen capture failed: {details}")
        data = proc.stdout
        if path:
            Path(path).write_bytes(data)
        return data

    def current_focus(self) -> str:
        """Return the current window focus line from dumpsys."""
        output = self.shell("dumpsys", "window", check=False)
        for line in output.splitlines():
            stripped = line.strip()
            if stripped.startswith("mCurrentFocus=") or stripped.startswith("mFocusedApp="):
                return stripped
        return ""

    def wait_for_focus(self, needle: str, timeout: float = 5.0) -> bool:
        deadline = time.time() + max(0, timeout)
        while time.time() < deadline:
            if needle.lower() in self.current_focus().lower():
                return True
            time.sleep(0.25)
        return False

    def set_clipboard(self, text: str, settle: float = 0.35) -> None:
        """Use the tiny companion app to place exact UTF-8 text on the clipboard."""
        raw = base64.b64encode(text.encode("utf-8")).decode("ascii")
        self.shell(
            "am", "start", "-W", "-n", self.helper_component,
            "--es", "b64", raw,
        )
        self.sleep(settle)

    def paste(self, paste_x: int, paste_y: int,
              confirm_x: int, confirm_y: int,
              text: Optional[str] = None,
              settle: float = 0.4) -> None:
        """Paste via an on-screen Paste button and confirm the editor."""
        if text is not None:
            self.set_clipboard(text)
        self.tap(paste_x, paste_y, settle=settle)
        self.tap(confirm_x, confirm_y, settle=settle)

    def package_installed(self, package: str) -> bool:
        output = self.shell("pm", "path", package, check=False)
        return "package:" in output

    def uninstall(self, package: str) -> bool:
        output = self.shell("uninstall", package, check=False)
        return "Success" in output


def parse_point(value: str) -> tuple[int, int]:
    """Parse 'x,y' or 'x y' into two integers."""
    cleaned = value.replace(",", " ").split()
    if len(cleaned) != 2:
        raise ValueError(f"expected 'x,y', got: {value!r}")
    return int(cleaned[0]), int(cleaned[1])
