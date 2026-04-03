from __future__ import annotations

import sys
from ctypes import create_unicode_buffer, wintypes, windll
from pathlib import Path


ROOT = Path(__file__).resolve().parent.parent
BOOT_DIR = ROOT / "Boot-voice"


def mci_send(command: str) -> None:
    buf = create_unicode_buffer(255)
    err = windll.winmm.mciSendStringW(  # type: ignore[attr-defined]
        wintypes.LPCWSTR(command),
        buf,
        254,
        0,
    )
    if err != 0:
        raise RuntimeError(f"MCI error {err} for command: {command}")


def play_mp3(path: Path) -> None:
    escaped = str(path).replace('"', '""')
    alias = "ordo_audio"
    mci_send(f'open "{escaped}" type mpegvideo alias {alias}')
    try:
        mci_send(f"play {alias} wait")
    finally:
        mci_send(f"close {alias}")


def main() -> int:
    if not BOOT_DIR.exists():
        print(f"Missing folder: {BOOT_DIR}")
        return 1

    candidates = sorted(
        BOOT_DIR.glob("*.mp3"),
        key=lambda p: p.stat().st_mtime,
        reverse=True,
    )
    if not candidates:
        print("No MP3 files found in Boot-voice.")
        return 1

    target = candidates[0]
    play_mp3(target)
    print(f"Played: {target}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
