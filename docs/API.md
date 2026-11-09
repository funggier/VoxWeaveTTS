# API Contract — foundation v0.1.0

Loopback base: `http://127.0.0.1:8765`. JSON UTF-8. Maximum request body currently 64 KiB; maximum text is 8,000 characters.

## Implemented

`GET /v1/status` — version and exact feature availability.

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

## Planned; not yet callable

- `POST /v1/speech` returns generated audio / speech job
- `WS /v1/speech/stream` streams generated audio
- `POST /v1/queue` enqueues speech jobs
- `GET /v1/voices` and profile management
- `WS /v1/events` reports playback-led speech events
- `GET /v1/playback/snapshot` for overlay reconnect
- `GET /overlay/subtitles` OBS Browser Source

Versioning and authentication requirements will be specified before remote access is implemented.
