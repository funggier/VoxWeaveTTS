# Security and third-party licenses

- Code in this repository is MIT (see LICENSE); third-party pretrained models, datasets, sounds and dependencies can have different restrictive licenses. Never assume MIT covers a model.
- Private voice reference samples require the speaker's consent; local files must not be uploaded to GitHub.
- Keep Discord bot credentials, OAuth tokens, API keys, connected chat content and cache outside Git.
- HTTP server defaults to loopback only. Do not forward the port or expose to a public network without auth, TLS and rate limiting.
- Filtered input must not accidentally leak into subtitles, logs, events or file output. A requested masking mode should be applied before output fan-out.
- Implement message size limits, safe HTML rendering, input dedup and bounded queues before live sources.
- Unit test sensitive-word redaction in both display and spoken paths.
