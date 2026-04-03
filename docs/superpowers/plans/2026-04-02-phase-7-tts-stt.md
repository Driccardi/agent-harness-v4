# Ordo Phase 7: TTS/STT + Voice Loop Implementation Plan

> **For agentic workers:** REQUIRED: Use superpowers:subagent-driven-development (if subagents available) or superpowers:executing-plans to implement this plan. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build the TTS/STT PM2 daemon on port 8001, wire the Electron push-to-talk button and F9 global hotkey to it, and complete the end-to-end voice loop: PTT press → audio capture → faster-whisper STT → POST to FastAPI conversation → LangGraph agent response → OpenAI TTS plays audio in Electron with a visual "speaking" indicator.

**Architecture:**
```
[Electron PTT button mousedown / F9 keydown]
  → main.ts globalShortcut / mousedown handler
  → HTTP POST localhost:8001/recording/start
  → Daemon starts sounddevice InputStream into circular buffer

[Electron PTT button mouseup / F9 keyup]
  → HTTP POST localhost:8001/recording/stop
  → Daemon stops stream, runs faster-whisper ("base.en") on WAV buffer
  → If confidence < 0.6 or faster-whisper fails → fallback to OpenAI Whisper API
  → Daemon returns { transcript: "..." }
  → frontend/src/ptt.ts inserts transcript into conversation send flow
  → POST /conversations/{id}/messages (human turn) to FastAPI port 8000
  → LangGraph generalist agent runs, returns response text
  → If tts.voice_output_enabled AND (ptt-initiated OR tts.voice_output_on_all_responses)
      → POST localhost:8001/tts/speak { text: "..." }
      → Daemon calls OpenAI TTS API (voice: "nova"), gets audio bytes
      → If OpenAI unavailable → fallback to pyttsx3
      → Daemon plays audio via sounddevice.play()
      → SSE event "speaking-start" / "speaking-end" streamed to Electron
  → PTT button shows pulse animation while speaking
```

**Tech Stack:** Python 3.12, FastAPI (port 8001 daemon), sounddevice, faster-whisper, OpenAI Python SDK (Whisper + TTS), pyttsx3, asyncio; TypeScript, Electron (IPC + globalShortcut), Vite; PM2 (`ordo-tts-stt`); pytest + pytest-asyncio + httpx

---

## Chunk 1: TTS/STT Daemon + Audio Capture

### Task 1: Dependencies

**Files:**
- Modify: `backend/requirements.txt`
- Modify: `backend/requirements-dev.txt`

- [ ] **Step 1: Add runtime dependencies to `backend/requirements.txt`**

Append the following lines:

```
faster-whisper==1.0.3
sounddevice==0.4.7
openai==1.30.1
pyttsx3==2.90
numpy==1.26.4
scipy==1.13.0
```

> **Note:** `faster-whisper` downloads the `base.en` model on first use to `~/.cache/huggingface/hub/`. Ensure the machine has ~150 MB free and outbound internet access on first run. Subsequent starts are fully offline.

- [ ] **Step 2: Add test dependency to `backend/requirements-dev.txt`**

Append:

```
pytest-mock==3.14.0
```

- [ ] **Step 3: Install new dependencies**

```bash
cd "C:/Users/user/AI-Assistant Version 4"
source .venv/Scripts/activate
pip install -r backend/requirements-dev.txt
```

Expected output:
```
Successfully installed faster-whisper-1.0.3 sounddevice-0.4.7 openai-1.30.1 pyttsx3-2.90 numpy-1.26.4 scipy-1.13.0 pytest-mock-3.14.0
```

Verify:
```bash
python -c "import faster_whisper, sounddevice, openai, pyttsx3; print('OK')"
```

Expected: `OK`

- [ ] **Step 4: Commit dependency additions**

```bash
git add backend/requirements.txt backend/requirements-dev.txt
git commit -m "chore(phase-7): add TTS/STT Python dependencies"
```

---

### Task 2: Audio Capture Module

**Files:**
- Create: `backend/services/__init__.py`
- Create: `backend/services/audio.py`
- Create: `tests/test_audio.py`

- [ ] **Step 1: Write failing tests**

Create `tests/test_audio.py`:

```python
import io
import wave
import pytest
from unittest.mock import patch, MagicMock, call
from backend.services.audio import AudioRecorder, AudioDeviceError


class TestAudioRecorder:
    def test_initial_state_not_recording(self):
        recorder = AudioRecorder()
        assert recorder.is_recording is False

    def test_start_recording_sets_flag(self):
        recorder = AudioRecorder()
        with patch("sounddevice.InputStream") as mock_stream_cls:
            mock_stream = MagicMock()
            mock_stream_cls.return_value.__enter__ = MagicMock(return_value=mock_stream)
            mock_stream_cls.return_value.__exit__ = MagicMock(return_value=False)
            recorder.start_recording()
            assert recorder.is_recording is True

    def test_stop_recording_returns_wav_bytes(self):
        recorder = AudioRecorder()
        recorder._buffer = [b"\x00" * 3200]  # fake 100ms of audio at 16kHz mono int16
        recorder._recording = True
        with patch("sounddevice.InputStream"):
            recorder.start_recording()
        bytes_out = recorder.stop_recording()
        assert isinstance(bytes_out, bytes)
        # Verify it is a valid WAV file
        buf = io.BytesIO(bytes_out)
        with wave.open(buf, "rb") as wf:
            assert wf.getnchannels() == 1
            assert wf.getframerate() == 16000

    def test_stop_recording_clears_flag(self):
        recorder = AudioRecorder()
        recorder._recording = True
        recorder._buffer = []
        result = recorder.stop_recording()
        assert recorder.is_recording is False

    def test_no_microphone_raises_audio_device_error(self):
        recorder = AudioRecorder()
        with patch(
            "sounddevice.InputStream",
            side_effect=Exception("No Default Input Device Available"),
        ):
            with pytest.raises(AudioDeviceError):
                recorder.start_recording()

    def test_double_start_is_noop(self):
        recorder = AudioRecorder()
        recorder._recording = True
        with patch("sounddevice.InputStream") as mock_cls:
            recorder.start_recording()
            mock_cls.assert_not_called()
```

- [ ] **Step 2: Run tests — verify they fail**

```bash
cd "C:/Users/user/AI-Assistant Version 4"
source .venv/Scripts/activate
pytest tests/test_audio.py -v
```

Expected:
```
ERROR tests/test_audio.py - ModuleNotFoundError: No module named 'backend.services.audio'
```

- [ ] **Step 3: Create `backend/services/__init__.py`**

```python
```

(Empty file — marks the package.)

- [ ] **Step 4: Create `backend/services/audio.py`**

```python
"""
audio.py — Sounddevice-based audio capture for the TTS/STT daemon.

Records from the default input device at 16 kHz, mono, int16.
Returns raw WAV bytes when stopped.
"""

from __future__ import annotations

import io
import wave
import threading
from typing import List

import numpy as np
import sounddevice as sd

SAMPLE_RATE = 16_000
CHANNELS = 1
DTYPE = "int16"
BLOCK_SIZE = 1024  # frames per callback (~64ms at 16kHz)


class AudioDeviceError(RuntimeError):
    """Raised when no suitable input device is available."""


class AudioRecorder:
    """Thread-safe push-to-talk audio recorder."""

    def __init__(self) -> None:
        self._buffer: List[bytes] = []
        self._recording: bool = False
        self._lock = threading.Lock()
        self._stream: sd.InputStream | None = None

    @property
    def is_recording(self) -> bool:
        return self._recording

    def _callback(self, indata: np.ndarray, frames: int, time, status) -> None:
        if self._recording:
            with self._lock:
                self._buffer.append(indata.copy().tobytes())

    def start_recording(self) -> None:
        """Start capturing from the default input device.

        Raises AudioDeviceError if no microphone is available.
        """
        if self._recording:
            return  # Already recording — idempotent

        try:
            stream = sd.InputStream(
                samplerate=SAMPLE_RATE,
                channels=CHANNELS,
                dtype=DTYPE,
                blocksize=BLOCK_SIZE,
                callback=self._callback,
            )
        except Exception as exc:
            raise AudioDeviceError(
                f"Could not open audio input device: {exc}"
            ) from exc

        with self._lock:
            self._buffer.clear()
            self._stream = stream
            self._recording = True

        self._stream.start()

    def stop_recording(self) -> bytes:
        """Stop capturing and return the recorded audio as WAV bytes.

        Always clears the recording flag and buffer, even if no audio was captured.
        """
        self._recording = False

        if self._stream is not None:
            try:
                self._stream.stop()
                self._stream.close()
            except Exception:
                pass
            self._stream = None

        with self._lock:
            raw_chunks = list(self._buffer)
            self._buffer.clear()

        return _chunks_to_wav(raw_chunks)


def _chunks_to_wav(chunks: List[bytes]) -> bytes:
    """Concatenate raw int16 PCM chunks into a WAV byte string."""
    raw_pcm = b"".join(chunks)
    buf = io.BytesIO()
    with wave.open(buf, "wb") as wf:
        wf.setnchannels(CHANNELS)
        wf.setsampwidth(2)  # int16 = 2 bytes
        wf.setframerate(SAMPLE_RATE)
        wf.writeframes(raw_pcm)
    return buf.getvalue()
```

- [ ] **Step 5: Run tests — verify they pass**

```bash
pytest tests/test_audio.py -v
```

Expected:
```
tests/test_audio.py::TestAudioRecorder::test_initial_state_not_recording PASSED
tests/test_audio.py::TestAudioRecorder::test_start_recording_sets_flag PASSED
tests/test_audio.py::TestAudioRecorder::test_stop_recording_returns_wav_bytes PASSED
tests/test_audio.py::TestAudioRecorder::test_stop_recording_clears_flag PASSED
tests/test_audio.py::TestAudioRecorder::test_no_microphone_raises_audio_device_error PASSED
tests/test_audio.py::TestAudioRecorder::test_double_start_is_noop PASSED

6 passed in 0.XXs
```

- [ ] **Step 6: Commit audio module**

```bash
git add backend/services/__init__.py backend/services/audio.py tests/test_audio.py
git commit -m "feat(phase-7): add sounddevice audio capture module with WAV export"
```

---

### Task 3: TTS/STT Daemon

**Files:**
- Create: `backend/services/tts_stt_daemon.py`
- Create: `tests/test_tts_stt_daemon.py`

- [ ] **Step 1: Write failing tests**

Create `tests/test_tts_stt_daemon.py`:

```python
import pytest
import pytest_asyncio
from unittest.mock import AsyncMock, MagicMock, patch
from httpx import AsyncClient, ASGITransport


@pytest.fixture
def daemon_app():
    """Import daemon app fresh for each test to avoid global state bleed."""
    import importlib
    import backend.services.tts_stt_daemon as mod
    importlib.reload(mod)
    return mod.app


@pytest.fixture
def async_client(daemon_app):
    return AsyncClient(transport=ASGITransport(app=daemon_app), base_url="http://test")


class TestStatusEndpoint:
    @pytest.mark.asyncio
    async def test_status_defaults(self, async_client):
        async with async_client as client:
            r = await client.get("/status")
        assert r.status_code == 200
        data = r.json()
        assert data["recording"] is False
        assert data["speaking"] is False


class TestRecordingEndpoints:
    @pytest.mark.asyncio
    async def test_start_recording_returns_200(self, async_client):
        with patch("backend.services.tts_stt_daemon.recorder") as mock_rec:
            mock_rec.is_recording = False
            async with async_client as client:
                r = await client.post("/recording/start")
            assert r.status_code == 200
            mock_rec.start_recording.assert_called_once()

    @pytest.mark.asyncio
    async def test_start_recording_no_mic_returns_503(self, async_client):
        from backend.services.audio import AudioDeviceError
        with patch("backend.services.tts_stt_daemon.recorder") as mock_rec:
            mock_rec.start_recording.side_effect = AudioDeviceError("No mic")
            async with async_client as client:
                r = await client.post("/recording/start")
            assert r.status_code == 503
            assert "microphone" in r.json()["detail"].lower()

    @pytest.mark.asyncio
    async def test_stop_recording_calls_stt(self, async_client):
        with patch("backend.services.tts_stt_daemon.recorder") as mock_rec, \
             patch("backend.services.tts_stt_daemon._run_stt", new_callable=AsyncMock) as mock_stt:
            mock_rec.stop_recording.return_value = b"RIFF....fake-wav"
            mock_stt.return_value = "hello Ordo"
            async with async_client as client:
                r = await client.post("/recording/stop")
            assert r.status_code == 200
            assert r.json()["transcript"] == "hello Ordo"

    @pytest.mark.asyncio
    async def test_stop_recording_empty_audio_returns_empty_transcript(self, async_client):
        with patch("backend.services.tts_stt_daemon.recorder") as mock_rec, \
             patch("backend.services.tts_stt_daemon._run_stt", new_callable=AsyncMock) as mock_stt:
            mock_rec.stop_recording.return_value = b""
            mock_stt.return_value = ""
            async with async_client as client:
                r = await client.post("/recording/stop")
            assert r.status_code == 200
            assert r.json()["transcript"] == ""


class TestSTTFallback:
    @pytest.mark.asyncio
    async def test_stt_uses_faster_whisper_first(self, daemon_app):
        from backend.services.tts_stt_daemon import _run_stt
        with patch("backend.services.tts_stt_daemon._stt_faster_whisper", new_callable=AsyncMock) as mock_fw:
            mock_fw.return_value = ("hello world", 0.95)
            result = await _run_stt(b"fake-wav-bytes")
        mock_fw.assert_called_once()
        assert result == "hello world"

    @pytest.mark.asyncio
    async def test_stt_falls_back_to_openai_on_low_confidence(self, daemon_app):
        from backend.services.tts_stt_daemon import _run_stt
        with patch("backend.services.tts_stt_daemon._stt_faster_whisper", new_callable=AsyncMock) as mock_fw, \
             patch("backend.services.tts_stt_daemon._stt_openai_api", new_callable=AsyncMock) as mock_oa:
            mock_fw.return_value = ("uh huh", 0.4)  # confidence below 0.6 threshold
            mock_oa.return_value = "hello Ordo"
            result = await _run_stt(b"fake-wav-bytes")
        mock_fw.assert_called_once()
        mock_oa.assert_called_once()
        assert result == "hello Ordo"

    @pytest.mark.asyncio
    async def test_stt_falls_back_to_openai_on_exception(self, daemon_app):
        from backend.services.tts_stt_daemon import _run_stt
        with patch("backend.services.tts_stt_daemon._stt_faster_whisper", new_callable=AsyncMock) as mock_fw, \
             patch("backend.services.tts_stt_daemon._stt_openai_api", new_callable=AsyncMock) as mock_oa:
            mock_fw.side_effect = RuntimeError("model not loaded")
            mock_oa.return_value = "fallback transcript"
            result = await _run_stt(b"fake-wav-bytes")
        mock_oa.assert_called_once()
        assert result == "fallback transcript"


class TestTTSEndpoint:
    @pytest.mark.asyncio
    async def test_speak_calls_openai_tts(self, async_client):
        with patch("backend.services.tts_stt_daemon._tts_openai", new_callable=AsyncMock) as mock_tts:
            mock_tts.return_value = True
            async with async_client as client:
                r = await client.post("/tts/speak", json={"text": "Hello!"})
            assert r.status_code == 200
            mock_tts.assert_called_once_with("Hello!")

    @pytest.mark.asyncio
    async def test_speak_falls_back_to_pyttsx3(self, async_client):
        with patch("backend.services.tts_stt_daemon._tts_openai", new_callable=AsyncMock) as mock_openai, \
             patch("backend.services.tts_stt_daemon._tts_pyttsx3") as mock_py:
            mock_openai.side_effect = Exception("API unavailable")
            async with async_client as client:
                r = await client.post("/tts/speak", json={"text": "Fallback!"})
            assert r.status_code == 200
            mock_py.assert_called_once_with("Fallback!")

    @pytest.mark.asyncio
    async def test_speak_empty_text_returns_400(self, async_client):
        async with async_client as client:
            r = await client.post("/tts/speak", json={"text": ""})
        assert r.status_code == 400
```

- [ ] **Step 2: Run tests — verify they fail**

```bash
cd "C:/Users/user/AI-Assistant Version 4"
source .venv/Scripts/activate
pytest tests/test_tts_stt_daemon.py -v
```

Expected:
```
ERROR tests/test_tts_stt_daemon.py - ModuleNotFoundError: No module named 'backend.services.tts_stt_daemon'
```

- [ ] **Step 3: Create `backend/services/tts_stt_daemon.py`**

```python
"""
tts_stt_daemon.py — TTS/STT FastAPI daemon for Ordo V4.

Runs as a separate process on port 8001 (managed by PM2 as 'ordo-tts-stt').
Exposes HTTP endpoints consumed by the Electron frontend and main FastAPI.

Endpoints:
  POST /recording/start  — begin audio capture
  POST /recording/stop   — stop capture, run STT, return transcript
  POST /tts/speak        — synthesize and play text via TTS
  GET  /status           — current recording/speaking state
  GET  /sse/events       — SSE stream for speaking-start / speaking-end events

STT priority: faster-whisper (base.en) → OpenAI Whisper API (confidence < 0.6 or exception)
TTS priority: OpenAI TTS (voice: nova)  → pyttsx3 (API unavailable)
"""

from __future__ import annotations

import asyncio
import io
import logging
import os
import tempfile
import threading
from typing import AsyncGenerator

import numpy as np
import sounddevice as sd
from fastapi import FastAPI, HTTPException
from fastapi.responses import StreamingResponse
from pydantic import BaseModel

from backend.services.audio import AudioDeviceError, AudioRecorder

logger = logging.getLogger("ordo.tts_stt")

# ---------------------------------------------------------------------------
# App + global state
# ---------------------------------------------------------------------------

app = FastAPI(title="Ordo TTS/STT Daemon", version="1.0.0")

recorder = AudioRecorder()
_speaking = threading.Event()  # set while TTS audio is playing
_sse_queue: asyncio.Queue[str] = asyncio.Queue()

# faster-whisper model — loaded lazily on first STT call
_fw_model = None
_fw_lock = threading.Lock()

CONFIDENCE_THRESHOLD = 0.6  # below this, fall back to OpenAI Whisper API


# ---------------------------------------------------------------------------
# Pydantic schemas
# ---------------------------------------------------------------------------

class SpeakRequest(BaseModel):
    text: str


class TranscriptResponse(BaseModel):
    transcript: str


class StatusResponse(BaseModel):
    recording: bool
    speaking: bool


# ---------------------------------------------------------------------------
# Endpoints
# ---------------------------------------------------------------------------

@app.get("/status", response_model=StatusResponse)
async def get_status() -> StatusResponse:
    return StatusResponse(recording=recorder.is_recording, speaking=_speaking.is_set())


@app.post("/recording/start")
async def start_recording():
    """Begin audio capture from the default input device."""
    try:
        recorder.start_recording()
    except AudioDeviceError as exc:
        raise HTTPException(
            status_code=503,
            detail=f"No microphone available: {exc}",
        )
    return {"status": "recording"}


@app.post("/recording/stop", response_model=TranscriptResponse)
async def stop_recording() -> TranscriptResponse:
    """Stop audio capture, run STT, and return the transcript."""
    wav_bytes = recorder.stop_recording()
    transcript = await _run_stt(wav_bytes)
    return TranscriptResponse(transcript=transcript)


@app.post("/tts/speak")
async def tts_speak(req: SpeakRequest):
    """Synthesize and play text. Streams speaking-start / speaking-end SSE events."""
    if not req.text.strip():
        raise HTTPException(status_code=400, detail="text must not be empty")

    try:
        await _tts_openai(req.text)
    except Exception as exc:
        logger.warning("OpenAI TTS failed (%s) — falling back to pyttsx3", exc)
        _tts_pyttsx3(req.text)

    return {"status": "done"}


@app.get("/sse/events")
async def sse_events():
    """Server-Sent Events stream for UI speaking indicator."""
    async def event_generator() -> AsyncGenerator[str, None]:
        while True:
            event = await _sse_queue.get()
            yield f"data: {event}\n\n"

    return StreamingResponse(event_generator(), media_type="text/event-stream")


# ---------------------------------------------------------------------------
# STT helpers
# ---------------------------------------------------------------------------

async def _run_stt(wav_bytes: bytes) -> str:
    """Run STT with fallback: faster-whisper → OpenAI Whisper API."""
    if not wav_bytes:
        return ""

    try:
        text, confidence = await _stt_faster_whisper(wav_bytes)
        if confidence >= CONFIDENCE_THRESHOLD:
            return text
        logger.info(
            "faster-whisper confidence %.2f below threshold — falling back to OpenAI Whisper",
            confidence,
        )
        return await _stt_openai_api(wav_bytes)
    except Exception as exc:
        logger.warning("faster-whisper failed (%s) — falling back to OpenAI Whisper", exc)
        return await _stt_openai_api(wav_bytes)


async def _stt_faster_whisper(wav_bytes: bytes) -> tuple[str, float]:
    """Transcribe via faster-whisper (base.en model, local).

    Returns (transcript, avg_confidence).
    Model is loaded lazily and cached for the process lifetime.
    """
    global _fw_model

    def _load_and_transcribe() -> tuple[str, float]:
        global _fw_model
        with _fw_lock:
            if _fw_model is None:
                from faster_whisper import WhisperModel
                logger.info("Loading faster-whisper base.en model (first use — may take a moment)...")
                _fw_model = WhisperModel("base.en", device="cpu", compute_type="int8")

        segments, _info = _fw_model.transcribe(io.BytesIO(wav_bytes), language="en")
        segment_list = list(segments)
        if not segment_list:
            return "", 0.0
        text = " ".join(s.text.strip() for s in segment_list)
        avg_conf = sum(
            getattr(s, "avg_logprob", -0.5) for s in segment_list
        ) / len(segment_list)
        # avg_logprob is in [-inf, 0]; convert to [0, 1] with a simple sigmoid-like mapping
        confidence = max(0.0, min(1.0, 1.0 + avg_conf / 5.0))
        return text, confidence

    loop = asyncio.get_running_loop()
    return await loop.run_in_executor(None, _load_and_transcribe)


async def _stt_openai_api(wav_bytes: bytes) -> str:
    """Transcribe via OpenAI Whisper API (fallback)."""
    import openai

    api_key = _get_openai_api_key()
    client = openai.AsyncOpenAI(api_key=api_key)

    with tempfile.NamedTemporaryFile(suffix=".wav", delete=False) as tmp:
        tmp.write(wav_bytes)
        tmp_path = tmp.name

    try:
        with open(tmp_path, "rb") as audio_file:
            response = await client.audio.transcriptions.create(
                model="whisper-1",
                file=audio_file,
                language="en",
            )
        return response.text.strip()
    finally:
        os.unlink(tmp_path)


# ---------------------------------------------------------------------------
# TTS helpers
# ---------------------------------------------------------------------------

async def _tts_openai(text: str) -> bool:
    """Synthesize text via OpenAI TTS (voice: nova) and play via sounddevice."""
    import openai

    api_key = _get_openai_api_key()
    client = openai.AsyncOpenAI(api_key=api_key)

    response = await client.audio.speech.create(
        model="tts-1",
        voice="nova",
        input=text,
        response_format="pcm",  # raw 24kHz 16-bit mono PCM
    )
    audio_bytes = response.content

    await _play_pcm_async(audio_bytes, sample_rate=24_000)
    return True


def _tts_pyttsx3(text: str) -> None:
    """Synthesize and play text via pyttsx3 (local fallback)."""
    import pyttsx3

    _speaking.set()
    asyncio.get_event_loop().create_task(_sse_queue.put("speaking-start"))

    engine = pyttsx3.init()
    engine.say(text)
    engine.runAndWait()

    _speaking.clear()
    asyncio.get_event_loop().create_task(_sse_queue.put("speaking-end"))


async def _play_pcm_async(pcm_bytes: bytes, sample_rate: int) -> None:
    """Play raw PCM bytes via sounddevice in a thread executor and fire SSE events."""
    _speaking.set()
    await _sse_queue.put("speaking-start")

    def _play():
        audio = np.frombuffer(pcm_bytes, dtype=np.int16).astype(np.float32) / 32768.0
        sd.play(audio, samplerate=sample_rate, blocking=True)

    loop = asyncio.get_running_loop()
    try:
        await loop.run_in_executor(None, _play)
    finally:
        _speaking.clear()
        await _sse_queue.put("speaking-end")


# ---------------------------------------------------------------------------
# Utility
# ---------------------------------------------------------------------------

def _get_openai_api_key() -> str:
    """Resolve the OpenAI API key.

    Preference order:
    1. OPENAI_API_KEY environment variable (dev convenience)
    2. model_api_keys table in PostgreSQL (production path — fetched synchronously
       via psycopg2 to avoid async context issues at startup)
    """
    key = os.environ.get("OPENAI_API_KEY")
    if key:
        return key

    # Lazy import to avoid hard dependency on psycopg2 in test environments
    try:
        import psycopg2
        db_url = os.environ.get(
            "ORDO_DB_URL",
            "postgresql://ordo:changeme@localhost:5432/ordo",
        )
        conn = psycopg2.connect(db_url)
        cur = conn.cursor()
        cur.execute(
            "SELECT key_value FROM model_api_keys WHERE provider = 'openai' LIMIT 1"
        )
        row = cur.fetchone()
        cur.close()
        conn.close()
        if row:
            return row[0]
    except Exception as exc:
        logger.warning("Could not fetch OpenAI key from DB: %s", exc)

    raise RuntimeError(
        "No OpenAI API key found. Set OPENAI_API_KEY env var or insert into model_api_keys."
    )


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    import uvicorn

    port = int(os.environ.get("TTS_STT_PORT", 8001))
    uvicorn.run("backend.services.tts_stt_daemon:app", host="127.0.0.1", port=port, reload=False)
```

- [ ] **Step 4: Run tests — verify they pass**

```bash
cd "C:/Users/user/AI-Assistant Version 4"
source .venv/Scripts/activate
pytest tests/test_tts_stt_daemon.py -v
```

Expected:
```
tests/test_tts_stt_daemon.py::TestStatusEndpoint::test_status_defaults PASSED
tests/test_tts_stt_daemon.py::TestRecordingEndpoints::test_start_recording_returns_200 PASSED
tests/test_tts_stt_daemon.py::TestRecordingEndpoints::test_start_recording_no_mic_returns_503 PASSED
tests/test_tts_stt_daemon.py::TestRecordingEndpoints::test_stop_recording_calls_stt PASSED
tests/test_tts_stt_daemon.py::TestRecordingEndpoints::test_stop_recording_empty_audio_returns_empty_transcript PASSED
tests/test_tts_stt_daemon.py::TestSTTFallback::test_stt_uses_faster_whisper_first PASSED
tests/test_tts_stt_daemon.py::TestSTTFallback::test_stt_falls_back_to_openai_on_low_confidence PASSED
tests/test_tts_stt_daemon.py::TestSTTFallback::test_stt_falls_back_to_openai_on_exception PASSED
tests/test_tts_stt_daemon.py::TestTTSEndpoint::test_speak_calls_openai_tts PASSED
tests/test_tts_stt_daemon.py::TestTTSEndpoint::test_speak_falls_back_to_pyttsx3 PASSED
tests/test_tts_stt_daemon.py::TestTTSEndpoint::test_speak_empty_text_returns_400 PASSED

11 passed in 0.XXs
```

- [ ] **Step 5: Commit daemon**

```bash
git add backend/services/tts_stt_daemon.py tests/test_tts_stt_daemon.py
git commit -m "feat(phase-7): add TTS/STT FastAPI daemon with faster-whisper and OpenAI fallbacks"
```

---

### Task 4: PM2 Ecosystem Entry

**Files:**
- Modify: `ecosystem.config.js`

- [ ] **Step 1: Confirm or add `ordo-tts-stt` entry**

Open `ecosystem.config.js`. Locate the `apps` array. Verify that an entry for `ordo-tts-stt` exists. If it does not exist, add the following object to the array:

```javascript
{
  name: "ordo-tts-stt",
  script: ".venv/Scripts/python.exe",
  args: "-m backend.services.tts_stt_daemon",
  cwd: "C:/Users/user/AI-Assistant Version 4",
  interpreter: "none",
  env: {
    TTS_STT_PORT: "8001",
    PYTHONPATH: "C:/Users/user/AI-Assistant Version 4"
  },
  restart_delay: 2000,
  autorestart: true,
  watch: false,
  out_file: "logs/tts-stt-out.log",
  error_file: "logs/tts-stt-err.log",
  log_date_format: "YYYY-MM-DD HH:mm:ss"
}
```

- [ ] **Step 2: Verify PM2 picks up the config**

```bash
cd "C:/Users/user/AI-Assistant Version 4"
pm2 start ecosystem.config.js --only ordo-tts-stt
pm2 status
```

Expected:
```
┌─────┬───────────────┬─────────┬──────┬───────────┬──────────┬──────────┐
│ id  │ name          │ mode    │ ↺    │ status    │ cpu      │ memory   │
├─────┼───────────────┼─────────┼──────┼───────────┼──────────┼──────────┤
│ ... │ ordo-tts-stt  │ fork    │ 0    │ online    │ 0%       │ ...mb    │
└─────┴───────────────┴─────────┴──────┴───────────┴──────────┴──────────┘
```

- [ ] **Step 3: Health check against running daemon**

```bash
curl http://localhost:8001/status
```

Expected:
```json
{"recording": false, "speaking": false}
```

- [ ] **Step 4: Stop daemon (dev mode — leave off until Electron integration is wired)**

```bash
pm2 stop ordo-tts-stt
```

- [ ] **Step 5: Commit ecosystem update**

```bash
git add ecosystem.config.js
git commit -m "chore(phase-7): register ordo-tts-stt in PM2 ecosystem on port 8001"
```

---

### Task 5: Voice Output Settings

**Files:**
- Modify: `backend/db/schema.sql` (or equivalent migration file)
- Modify: `backend/db/seed.py` (or equivalent seeder)

- [ ] **Step 1: Add settings rows for TTS voice output**

In the settings seed/migration, insert the following rows into the `settings` table (use `INSERT ... ON CONFLICT DO NOTHING` for idempotency):

```sql
INSERT INTO settings (key, value, description) VALUES
  ('tts.voice_output_enabled',        'true',  'Enable TTS playback of agent responses'),
  ('tts.voice_output_on_all_responses','false', 'Speak all responses (true) or only PTT-initiated ones (false)')
ON CONFLICT (key) DO NOTHING;
```

- [ ] **Step 2: Apply migration**

```bash
cd "C:/Users/user/AI-Assistant Version 4"
source .venv/Scripts/activate
python -m backend.db.migrate   # or psql -d ordo -f backend/db/migrations/0XX_tts_settings.sql
```

Expected output:
```
Applied: tts settings seed rows inserted (or already present).
```

- [ ] **Step 3: Verify rows in database**

```bash
psql -U ordo -d ordo -c "SELECT key, value FROM settings WHERE key LIKE 'tts.%';"
```

Expected:
```
              key               | value
--------------------------------+-------
 tts.voice_output_enabled       | true
 tts.voice_output_on_all_responses | false
(2 rows)
```

- [ ] **Step 4: Commit settings migration**

```bash
git add backend/db/
git commit -m "feat(phase-7): seed tts.voice_output_enabled and tts.voice_output_on_all_responses settings"
```

---

> **Plan-document-reviewer dispatch note (Chunk 1):** After completing all Chunk 1 tasks, an agentic reviewer should verify: (1) all 17 tests pass (`pytest tests/test_audio.py tests/test_tts_stt_daemon.py -v`); (2) `pm2 start ecosystem.config.js --only ordo-tts-stt && curl http://localhost:8001/status` returns `{"recording":false,"speaking":false}`; (3) settings rows are present in the database; (4) no `.env` or `__pycache__` files were committed. Only proceed to Chunk 2 after all checks pass.

---

## Chunk 2: Electron PTT Integration + TTS Playback

### Task 6: Electron PTT Module

**Files:**
- Create: `frontend/src/ptt.ts`
- Modify: `frontend/electron/main.ts`

- [ ] **Step 1: Create `frontend/src/ptt.ts`**

This module manages the PTT button state in the renderer process, communicates with the main process via `window.electronAPI`, and feeds transcripts into the conversation send flow.

```typescript
/**
 * ptt.ts — Push-To-Talk renderer logic for Ordo V4.
 *
 * Wires the PTT mic button to Electron IPC.
 * On press   → IPC "ptt-start" → main.ts → POST localhost:8001/recording/start
 * On release → IPC "ptt-stop"  → main.ts → POST localhost:8001/recording/stop
 *              → receives { transcript } → calls sendMessage(transcript)
 */

import { sendMessage } from "./conversation";

const DAEMON_BASE = "http://localhost:8001";

// --------------------------------------------------------------------------
// State
// --------------------------------------------------------------------------

let pttActive = false;
let speakingIndicatorTimer: ReturnType<typeof setTimeout> | null = null;

// --------------------------------------------------------------------------
// PTT button wiring (called from UI init)
// --------------------------------------------------------------------------

export function initPTT(micButton: HTMLElement): void {
  micButton.addEventListener("mousedown", handlePTTStart);
  micButton.addEventListener("mouseup", handlePTTStop);
  micButton.addEventListener("mouseleave", handlePTTStop); // safety: release if cursor leaves

  // Listen for speaking state changes pushed from main process
  window.electronAPI.on("speaking-start", () => showSpeakingIndicator(micButton));
  window.electronAPI.on("speaking-end", () => hideSpeakingIndicator(micButton));

  // Listen for PTT triggered by global hotkey (F9) from main process
  window.electronAPI.on("ptt-start", () => handlePTTStart());
  window.electronAPI.on("ptt-stop", () => handlePTTStop());
}

// --------------------------------------------------------------------------
// Handlers
// --------------------------------------------------------------------------

async function handlePTTStart(): Promise<void> {
  if (pttActive) return;
  pttActive = true;

  try {
    await window.electronAPI.pttStart();
  } catch (err) {
    console.error("[PTT] Failed to start recording:", err);
    pttActive = false;
  }
}

async function handlePTTStop(): Promise<void> {
  if (!pttActive) return;
  pttActive = false;

  try {
    const transcript: string = await window.electronAPI.pttStop();
    if (transcript && transcript.trim().length > 0) {
      await sendMessage(transcript.trim(), { source: "ptt" });
    }
  } catch (err) {
    console.error("[PTT] Failed to stop recording or get transcript:", err);
  }
}

// --------------------------------------------------------------------------
// Speaking indicator
// --------------------------------------------------------------------------

function showSpeakingIndicator(button: HTMLElement): void {
  button.classList.add("speaking");
  if (speakingIndicatorTimer !== null) {
    clearTimeout(speakingIndicatorTimer);
  }
  // Safety fallback: remove indicator after 30s even if speaking-end is missed
  speakingIndicatorTimer = setTimeout(() => hideSpeakingIndicator(button), 30_000);
}

function hideSpeakingIndicator(button: HTMLElement): void {
  button.classList.remove("speaking");
  if (speakingIndicatorTimer !== null) {
    clearTimeout(speakingIndicatorTimer);
    speakingIndicatorTimer = null;
  }
}

// --------------------------------------------------------------------------
// TTS trigger (called by conversation.ts after agent response arrives)
// --------------------------------------------------------------------------

export async function speakIfEnabled(
  text: string,
  options: { pttInitiated: boolean }
): Promise<void> {
  const voiceEnabled = await window.electronAPI.getSetting("tts.voice_output_enabled");
  const speakAll = await window.electronAPI.getSetting("tts.voice_output_on_all_responses");

  if (!voiceEnabled) return;
  if (!options.pttInitiated && !speakAll) return;

  try {
    await fetch(`${DAEMON_BASE}/tts/speak`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ text }),
    });
  } catch (err) {
    console.warn("[PTT] TTS speak request failed:", err);
  }
}
```

- [ ] **Step 2: Add PTT IPC handlers to `frontend/electron/main.ts`**

Open `frontend/electron/main.ts`. Locate the IPC handler registration block (where other `ipcMain.handle` calls live). Add the following block:

```typescript
// -------------------------------------------------------------------------
// PTT IPC handlers — forward to TTS/STT daemon on port 8001
// -------------------------------------------------------------------------

const TTS_STT_BASE = "http://localhost:8001";

ipcMain.handle("ptt-start", async () => {
  const res = await net.fetch(`${TTS_STT_BASE}/recording/start`, { method: "POST" });
  if (!res.ok) {
    const body = await res.json().catch(() => ({}));
    throw new Error(`Daemon error: ${body.detail ?? res.status}`);
  }
  return { status: "recording" };
});

ipcMain.handle("ptt-stop", async () => {
  const res = await net.fetch(`${TTS_STT_BASE}/recording/stop`, { method: "POST" });
  if (!res.ok) throw new Error(`Daemon error: ${res.status}`);
  const data = await res.json() as { transcript: string };
  return data.transcript ?? "";
});

ipcMain.handle("get-setting", async (_event, key: string) => {
  // Query FastAPI settings endpoint
  const res = await net.fetch(`http://localhost:8000/settings/${encodeURIComponent(key)}`);
  if (!res.ok) return null;
  const data = await res.json() as { value: string };
  // Coerce "true"/"false" strings to booleans
  if (data.value === "true") return true;
  if (data.value === "false") return false;
  return data.value;
});

// -------------------------------------------------------------------------
// Global hotkey — F9 for PTT (configurable)
// -------------------------------------------------------------------------

app.whenReady().then(() => {
  // Register F9 as global PTT hotkey
  const registered = globalShortcut.register("F9", () => {
    // Toggle PTT: keydown fires ptt-start, next press fires ptt-stop
    // Use a simple toggle flag for keyboard-based PTT
    if (!_f9PttActive) {
      _f9PttActive = true;
      mainWindow?.webContents.send("ptt-start");
    } else {
      _f9PttActive = false;
      mainWindow?.webContents.send("ptt-stop");
    }
  });

  if (!registered) {
    console.warn("[Ordo] F9 global hotkey registration failed — may be taken by another app.");
  }
});

let _f9PttActive = false;

app.on("will-quit", () => {
  globalShortcut.unregisterAll();
});
```

> **Note:** `net` is imported from `"electron"` — ensure `import { app, BrowserWindow, ipcMain, globalShortcut, net } from "electron"` is present at the top of `main.ts`. Add `net` to the import if it is missing.

- [ ] **Step 3: Update preload script to expose PTT APIs**

Open `frontend/electron/preload.ts`. Add the following to the `contextBridge.exposeInMainWorld("electronAPI", { ... })` object:

```typescript
pttStart: () => ipcRenderer.invoke("ptt-start"),
pttStop: () => ipcRenderer.invoke("ptt-stop"),
getSetting: (key: string) => ipcRenderer.invoke("get-setting", key),
on: (channel: string, callback: (...args: unknown[]) => void) => {
  ipcRenderer.on(channel, (_event, ...args) => callback(...args));
},
```

- [ ] **Step 4: Commit Electron PTT integration**

```bash
git add frontend/src/ptt.ts frontend/electron/main.ts frontend/electron/preload.ts
git commit -m "feat(phase-7): add Electron PTT IPC, F9 global hotkey, and preload API exposure"
```

---

### Task 7: PTT Button + Speaking Indicator CSS

**Files:**
- Modify: `frontend/src/styles/main.css` (or equivalent stylesheet)
- Modify: `frontend/src/main.ts` (or `frontend/src/app.ts` — the UI entry point)

- [ ] **Step 1: Add speaking pulse animation to stylesheet**

Locate the existing mic button styles (added in Phase 3 as a stub). Add or update:

```css
/* -----------------------------------------------------------------------
   PTT mic button
----------------------------------------------------------------------- */

.mic-button {
  position: relative;
  display: flex;
  align-items: center;
  justify-content: center;
  width: 36px;
  height: 36px;
  border-radius: 50%;
  border: 2px solid var(--color-border, #444);
  background: transparent;
  cursor: pointer;
  transition: border-color 0.15s ease, background 0.15s ease;
  flex-shrink: 0;
}

.mic-button:hover {
  border-color: var(--color-accent, #7c6fe0);
}

.mic-button.recording {
  border-color: #e05555;
  background: rgba(224, 85, 85, 0.12);
}

/* Speaking pulse — shown while Ordo is playing TTS audio */
.mic-button.speaking::after {
  content: "";
  position: absolute;
  inset: -6px;
  border-radius: 50%;
  border: 2px solid var(--color-accent, #7c6fe0);
  animation: speaking-pulse 1.2s ease-out infinite;
}

@keyframes speaking-pulse {
  0%   { opacity: 0.9; transform: scale(1); }
  100% { opacity: 0;   transform: scale(1.7); }
}
```

- [ ] **Step 2: Wire PTT init in UI entry point**

In the UI entry point (e.g. `frontend/src/main.ts`), after the DOM is ready, add:

```typescript
import { initPTT } from "./ptt";

// Wire PTT button
const micButton = document.querySelector<HTMLElement>(".mic-button");
if (micButton) {
  initPTT(micButton);
}
```

- [ ] **Step 3: Wire TTS playback after agent response**

In `frontend/src/conversation.ts` (or wherever the WebSocket/HTTP response from the agent is handled), after the agent response text is rendered in the UI, add:

```typescript
import { speakIfEnabled } from "./ptt";

// After rendering agent response:
const pttInitiated = lastMessageSource === "ptt"; // track source on sendMessage
await speakIfEnabled(responseText, { pttInitiated });
```

- [ ] **Step 4: Build and verify**

```bash
cd "C:/Users/user/AI-Assistant Version 4/frontend"
npm run build
```

Expected: Build completes with no TypeScript errors.

```bash
npm start  # or: npx electron .
```

Expected: Electron window opens. PTT mic button is visible. No console errors on startup.

- [ ] **Step 5: Commit UI integration**

```bash
git add frontend/src/ptt.ts frontend/src/styles/main.css frontend/src/main.ts frontend/src/conversation.ts
git commit -m "feat(phase-7): wire PTT button, speaking indicator, and TTS playback into Electron UI"
```

---

### Task 8: End-to-End Manual Integration Test

This task is a manual checklist — no automated test can cover the full PTT audio loop, but the steps must be performed before the phase is considered complete.

- [ ] **Step 1: Start all services**

```bash
cd "C:/Users/user/AI-Assistant Version 4"
pm2 start ecosystem.config.js
pm2 status
```

Expected: `fastapi`, `ordo-tts-stt` (and any other required processes) show `online`.

- [ ] **Step 2: Verify daemon health**

```bash
curl http://localhost:8001/status
```

Expected: `{"recording":false,"speaking":false}`

- [ ] **Step 3: Launch Electron**

```bash
cd frontend && npm start
```

- [ ] **Step 4: Manual voice loop test**

1. Press and hold the PTT mic button (or press F9).
   - Expected: mic button border turns red (`.recording` class applied).
   - Expected: `GET /status` returns `{"recording":true,"speaking":false}`.
2. Say clearly: **"Hello Ordo, what time is it?"**
3. Release the PTT button (or press F9 again).
   - Expected: mic button returns to normal state.
   - Expected: transcript `"Hello Ordo, what time is it?"` appears in the chat input briefly, then is sent.
   - Expected: agent response appears in the conversation panel.
   - Expected: mic button shows pulsing ring (`.speaking` class).
   - Expected: Ordo's voice (OpenAI TTS, voice: nova) plays the response text.
   - Expected: pulsing ring disappears after audio completes.

- [ ] **Step 5: Test no-microphone error path**

Disable the default audio input device in Windows Sound settings, then press PTT.

Expected: A user-visible error notification (toast or status bar message) stating that no microphone is available. The daemon must not crash — it returns HTTP 503, and the frontend should display a graceful error.

- [ ] **Step 6: Test F9 global hotkey**

With Electron focused, press F9 once (start recording). Speak "testing hotkey". Press F9 again (stop).

Expected: Same voice loop behavior as the button, with transcript submitted to conversation.

- [ ] **Step 7: Test voice output setting**

Via the database (or future Settings UI), set `tts.voice_output_on_all_responses = true`. Type a message manually (not PTT). Send it.

Expected: Ordo speaks the response even though PTT was not used.

Set it back to `false`. Type a message manually.

Expected: Ordo does not speak the response.

- [ ] **Step 8: Commit completion marker**

```bash
git add .
git commit -m "test(phase-7): manual voice loop E2E verified — PTT + F9 + TTS + speaking indicator"
```

---

> **Plan-document-reviewer dispatch note (Chunk 2):** After completing all Chunk 2 tasks, an agentic reviewer should verify: (1) TypeScript build has zero errors; (2) all daemon unit tests still pass (`pytest tests/test_audio.py tests/test_tts_stt_daemon.py -v`); (3) the manual E2E checklist in Task 8 has been completed by a human operator; (4) `pm2 status` shows `ordo-tts-stt` as `online` after a restart; (5) the speaking pulse animation is visible in the UI while TTS plays; (6) no microphone crash path is handled gracefully with a 503 and a user-visible error. Phase 7 is complete when all these checks pass and all commits are on the branch.
