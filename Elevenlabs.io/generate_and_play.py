from __future__ import annotations

import os
import sys
from ctypes import create_unicode_buffer, wintypes, windll
from datetime import datetime
from pathlib import Path

from elevenlabs import ElevenLabs


ROOT = Path(__file__).resolve().parent.parent
ELEVEN_DIR = ROOT / "Elevenlabs.io"
BOOT_DIR = ROOT / "Boot-voice"
ENV_FILE = ELEVEN_DIR / ".env"
DEFAULT_VOICE_ID = "aj0fZfXTBc7E3By4X8L2"


def load_dotenv(path: Path) -> None:
    if not path.exists():
        return
    for raw_line in path.read_text(encoding="utf-8").splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        key = key.strip()
        value = value.strip().strip('"').strip("'")
        if key and value and key not in os.environ:
            os.environ[key] = value


def read_key_from_file(path: Path) -> str:
    if not path.exists():
        return ""
    return path.read_text(encoding="utf-8").strip()


def write_audio(chunks, output_path: Path) -> None:
    with output_path.open("wb") as f:
        for chunk in chunks:
            if chunk:
                f.write(chunk)


def _mci_send(command: str) -> None:
    buf = create_unicode_buffer(255)
    err = windll.winmm.mciSendStringW(  # type: ignore[attr-defined]
        wintypes.LPCWSTR(command),
        buf,
        254,
        0,
    )
    if err != 0:
        raise RuntimeError(f"MCI error {err} for command: {command}")


def play_mp3_windows(path: Path) -> None:
    escaped = str(path).replace('"', '""')
    alias = "ordo_audio"
    _mci_send(f'open "{escaped}" type mpegvideo alias {alias}')
    try:
        _mci_send(f"play {alias} wait")
    finally:
        _mci_send(f"close {alias}")


def main() -> int:
    load_dotenv(ENV_FILE)

    tts_key = os.environ.get("ELEVENLABS_API_KEY") or read_key_from_file(
        ELEVEN_DIR / "API-Key.txt"
    )
    sfx_key = os.environ.get("ELEVENLABS_SOUND_EFFECTS_API_KEY") or read_key_from_file(
        ELEVEN_DIR / "api-key-sound-effects.txt"
    )
    voice_id = os.environ.get("ORDO_ELEVENLABS_VOICE_ID", DEFAULT_VOICE_ID)

    if not tts_key:
        print("Missing ELEVENLABS_API_KEY.")
        return 1
    if not sfx_key:
        print("Missing ELEVENLABS_SOUND_EFFECTS_API_KEY.")
        return 1

    BOOT_DIR.mkdir(parents=True, exist_ok=True)
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    tts_out = BOOT_DIR / f"ordo_boot_{timestamp}.mp3"
    sfx_out = BOOT_DIR / f"ordo_sfx_{timestamp}.mp3"

    tts_client = ElevenLabs(api_key=tts_key)
    sfx_client = ElevenLabs(api_key=sfx_key)

    tts_ok = False
    try:
        tts_audio = tts_client.text_to_speech.convert(
            voice_id=voice_id,
            model_id="eleven_turbo_v2_5",
            text="Ordo voice check complete.",
        )
        write_audio(tts_audio, tts_out)
        tts_ok = True
        print(f"Generated voice clip: {tts_out}")
    except Exception as exc:
        print(f"Voice clip generation skipped: {exc}")

    sfx_audio = sfx_client.text_to_sound_effects.convert(
        text="A clean futuristic startup chime with a short whoosh and soft impact.",
        duration_seconds=3.0,
        prompt_influence=0.6,
    )
    write_audio(sfx_audio, sfx_out)
    print(f"Generated sound effect: {sfx_out}")

    targets = [("sound effect", sfx_out)]
    if tts_ok:
        targets.insert(0, ("voice clip", tts_out))

    for label, file_path in targets:
        try:
            play_mp3_windows(file_path)
            print(f"Played {label}: {file_path.name}")
        except Exception as exc:
            print(f"Could not auto-play {label} ({file_path.name}): {exc}")

    return 0


if __name__ == "__main__":
    sys.exit(main())
