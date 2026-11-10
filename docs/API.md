# API Contract — M1 Thai WAV preview (v0.2.0.dev4)

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
- Optional `match_mode`: `literal` (default) or `five_run` (requires `match="555"`). A `five_run` rule matches three or more consecutive ASCII 5 characters outside surrounding numbers. `55555` → a selected replacement such as `ฮ่า ฮ่า ฮ่า`, while its actual display remains `55555` unless `display` is set. Grouped numbers or decimals such as `5,55555` and `55555.50` are excluded. This is a predefined safe pattern, not user-supplied regex.
- `mode=silence`: `silence_ms` 0–10,000; `display` defaults to ***.
- `mode=skip`: removes speech time, `display` defaults to ***.
- Optional `sources` list restricts application to specific source IDs.
- Longest literal match at the earliest position wins; input order breaks exact ties.

## Real audio endpoint (M1 preview)

`GET /v1/engines` — two Thai CPU ONNX adapters (`fastthaig2p-cpu`, `makham-paradee-cpu`) with model readiness, voice IDs, supported flags, and a `control_schema` object including slider/min/max/step defaults and `ffmpeg_ready`.

`GET /v1/voices` — fixed `thai_som` and `paradee_thai` with `engine_id`, `ready` and `voice_cloning=false`.

`POST /v1/speech` — uses the **same** text, rules, pronunciations and source fields as `POST /v1/text/process`, plus `engine_id: "fastthaig2p-cpu"` / `"makham-paradee-cpu"`, corresponding `voice_id` (`"thai_som"` / `"paradee_thai"`), `speed: 1.0` (range 0.6–1.5), optional `voice_controls` and `seed` (integer 0–2147483647). Returns `audio/wav` (24 kHz mono PCM16), `X-VoxWeaveTTS-Duration-Ms` and `X-VoxWeaveTTS-Seed` headers. Text input may be at most 8000 chars for text processing but total spoken segments are limited to **500 spoken characters and 50 segments** per audio request. CPU TTS assets are optional: if unavailable, the endpoint responds `503`. Unsupported control/engine/voice returns `400`.

This endpoint **generates audio, not timed playback events**; its segment duration metadata is not a live subtitle timeline. See [M1_AUDIO_TH.md](M1_AUDIO_TH.md).

## Synthesis settings and reproducibility (implemented)

`GET /v1/settings/synthesis` returns `{"seed":100}` by default or the saved seed in `data/settings/synthesis.json`.

`POST /v1/settings/synthesis` requires `Content-Type: application/json`, `X-VoxWeaveTTS-Intent: save-synthesis-settings`, and JSON body `{"seed":123}`. Stores only this validated integer under the portable project root. `POST /v1/speech` uses the saved seed when not supplied in the request, and a request-specific seed takes precedence.

FastThaiG2P uses stochastic ONNX operations. To ensure a fixed seed reproduces byte-identical WAV on the tested CPU runtime, `render_wav` seeds ONNX **before creating a new model session for each speech job**. Reusing a model session while merely reseeding the global runtime is not reproducible. This incurs extra model-initialization overhead; M1 prioritizes correctness over streaming latency. It **does not guarantee correct pronunciation**, only reproducibility for the same model/runtime/input. Waveform correlation between Seed 100/101 was measured at about 0.986 for `ฮ่า ฮ่า ฮ่า` and 0.997 for a longer Thai sentence; Seed does not select a different voice or provide useful timbre control.

## Voice Studio controls and presets (implemented in preview)

`POST /v1/speech` accepts `voice_controls`: `gain_db` (-18..+12 dB), `pitch_semitones` (-4..+4), `bass_db`/ `treble_db` (-12..+12 dB) and `formant_preserve` (boolean). Defaults are zero and `true` for formant preservation. Gain is handled by Python DSP, Pitch/EQ use **optional external FFmpeg with Rubber Band**. The Engine does not natively support Pitch/Formant/Emotion; independent formant shifting is unsupported. Silent segments remain exact PCM zeros.

`GET /v1/presets` lists local JSON presets. `POST /v1/presets` requires `X-VoxWeaveTTS-Intent: save-voice-preset` with JSON body containing `name`, `engine_id`, `voice_id`, `speed`, `seed`, and `voice_controls`. Up to 32 validated presets are saved locally in `data/presets/voice-presets.json`, which is Git-ignored. See [VOICE_STUDIO_TH.md](VOICE_STUDIO_TH.md).

## Planned; not yet callable

- A queued/asynchronous version of `POST /v1/speech` returns a speech job
- `WS /v1/speech/stream` streams generated audio
- `POST /v1/queue` enqueues speech jobs
- `GET /v1/voices` and profile management
- `WS /v1/events` reports playback-led speech events
- `GET /v1/playback/snapshot` for overlay reconnect
- `GET /overlay/subtitles` OBS Browser Source

Versioning and authentication requirements will be specified before remote access is implemented.