/* Engine-neutral browser media clock. No TTS model or external dependencies.
 * Cue timing comes from rendered WAV sample offsets; the clock itself comes
 * from HTMLMediaElement.currentTime. It is NOT word/phoneme alignment.
 */
(function (root) {
  "use strict";
  const REPORT_INTERVAL_MS = 250;
  function cueAt(segments, millis) {
    if (!Array.isArray(segments) || !Number.isFinite(millis)) return "";
    const cue = segments.find(item => item.start_ms <= millis && millis < item.end_ms);
    return cue && cue.kind === "speech" ? cue.display_text : "";
  }

  function attach(media, reporter, onUpdate, makeSession) {
    if (!media || typeof reporter !== "function") throw new Error("media and reporter required");
    const generateId = makeSession || (() => root.crypto.randomUUID().replace(/-/g, ""));
    let active = null;
    let reportedStart = false;
    let sequence = 0;
    let pending = Promise.resolve();
    let ticker = null;
    let finished = false;

    function positionMs() {
      return Math.max(0, Math.round((Number(media.currentTime) || 0) * 1000));
    }
    function update() {
      const state = !active ? "idle" : media.ended ? "ended" : media.paused ? "paused" : "playing";
      const text = state === "playing" && active
        ? cueAt(active.segments, positionMs()) : "";
      if (typeof onUpdate === "function") {
        onUpdate({text, position_ms:positionMs(),
          duration_ms: active?.duration_ms || 0, state});
      }
    }
    function report(event) {
      if (!active || (event !== "start" && !reportedStart)) return pending;
      const message = {
        session_id:active.session_id,
        speech_id:active.speech_id,
        event, position_ms:positionMs(), sequence:++sequence,
      };
      pending = pending.catch(() => {}).then(() => reporter(message));
      // Treat failed reporting as non-fatal for local audio playback.
      pending = pending.catch(error => {
        if (typeof root.console?.warn === "function")
          root.console.warn("VoxWeaveTTS playback report failed:", error);
      });
      return pending;
    }
    function stopTimer() {
      if (ticker !== null) {clearInterval(ticker);ticker = null;}
    }
    function startTimer() {
      stopTimer();
      ticker = setInterval(() => { if (active && !media.paused) report("progress"); }, REPORT_INTERVAL_MS);
    }
    media.addEventListener("play", () => {
      if (!active) return;
      report(reportedStart ? "resumed" : "start");
      reportedStart = true;
      startTimer();
      update();
    });
    media.addEventListener("pause", () => {
      if (!active || media.ended) return;
      stopTimer();
      report("paused");
      update();
    });
    media.addEventListener("seeked", () => {
      if (active) report("seeked");
      update();
    });
    media.addEventListener("timeupdate", update);
    media.addEventListener("ended", () => {
      finished = true;
      stopTimer();
      report("ended");
      update();
    });
    media.addEventListener("error", () => {
      if (active) report("stopped");
      stopTimer();
      active = null;
      update();
    });

    function setSpeech(speechId, timeline) {
      if (active) clear();
      if (!/^[0-9a-f]{32}$/.test(speechId))
        throw new Error("invalid speech id for playback");
      if (!timeline || !Array.isArray(timeline.segments))
        throw new Error("missing generated audio segment timeline");
      const sessionId = generateId();
      if (!/^[0-9a-f]{32}$/.test(sessionId))
        throw new Error("invalid playback session id");
      active = {
        session_id:sessionId, speech_id:speechId,
        segments:timeline.segments,
        duration_ms:timeline.duration_ms,
      };
      reportedStart = false;
      sequence = 0;
      finished = false;
      update();
      return sessionId;
    }
    function clear() {
      if (active && reportedStart && !finished) report("stopped");
      stopTimer();
      active = null;
      reportedStart = false;
      update();
    }
    return {setSpeech, clear, update, report, cueAt};
  }

  root.VoxPlaybackClock = {attach, cueAt};
  if (typeof module !== "undefined" && module.exports)
    module.exports = {attach, cueAt};
})(typeof window === "undefined" ? globalThis : window);