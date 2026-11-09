# API Contract — M1 Thai WAV preview (v0.2.0.dev0)

Loopback base: `http://127.0.0.1:8765`. JSON UTF-8. Maximum request body currently 64 KiB; maximum text is 8,000 characters.

## Implemented

`GET /v1/status` — version and exact feature availability (models present + Python dependencies present).

`GET /v1/rules` — the current local `data/filters/rules.json` if present, or an empty list.

`GET /v1/pronunciations` — the current local `data/dictionaries/pronunciations.json` if present, or an empty map.

`POST /v1/text/process`:
```json
{
  "text": "เขาเป็นอมตะและพบคำต้องห้าม",
  "source": "manual",
  "rules": [{"match":"คำต้องห้าม","mode":"silence","silence_ms":400,"display":"***"}],
  "pronunciations": {"อมตะ":"อะ มะ ตะ"}
}
```
The optional `rules` and `pronunciations` override local file configuration for this request only. Response fields: `display_text`, `spoken_text` (speech-only linear text), `segments` (`kind`, `spoken_text`, `display_text`, `silence_ms`, source offsets), `source`. This is a preview of a future speech plan, NOT synthesized audio.

Rules:
- `mode=replace`: `spoken` optional, `display` optional (default original spelling).
- `mode=silence`: `silence_ms` 0–10,000; `display` defaults to ***.
- `mode=skip`: removes speech time, `display` defaults to ***.
- Optional `sources` list restricts application to specific source IDs.
- Longest literal match at the earliest position wins; input order breaks exact ties.

## Real audio endpoint (M1 preview)

`GET /v1/engines` — one Thai backend with available assets, installed runtime and supported capability flags.

`GET /v1/voices` — only fixed `thai_som`; `voice_cloning=false`.

`POST /v1/speech` — uses the **same** text, rules, pronunciations and source fields as `POST /v1/text/process`, plus `engine_id: "fastthaig2p-cpu"`, `voice_id: "thai_som"`, and `speed: 1.0` (range 0.6–1.5). Returns `audio/wav` (24 kHz mono PCM16), `X-VoxWeaveTTS-Duration-Ms` header. Text input may be at most 8000 chars for text processing but total spoken segments are limited to **500 spoken characters and 50 segments** per audio request. CPU TTS assets are optional: if unavailable, the endpoint responds `503`. Unsupported control/engine/voice returns `400`.

This endpoint **generates audio, not timed playback events**; its segment duration metadata is not a live subtitle timeline. See [M1_AUDIO_TH.md](M1_AUDIO_TH.md).

## Planned; not yet callable

- A queued/asynchronous version of `POST /v1/speech` returns a speech job
- `WS /v1/speech/stream` streams generated audio
- `POST /v1/queue` enqueues speech jobs
- `GET /v1/voices` and profile management
- `WS /v1/events` reports playback-led speech events
- `GET /v1/playback/snapshot` for overlay reconnect
- `GET /overlay/subtitles` OBS Browser Source

Versioning and authentication requirements will be specified before remote access is implemented.