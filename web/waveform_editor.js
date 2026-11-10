/* VoxWeaveTTS — engine-neutral local PCM16 WAV waveform and timecode editor.
 * Public WAV bytes are fetched from an already-ready Speech Job and remain in
 * browser memory. Does not require an aligner, external JS, models or cloud.
 */
(function (root) {
  "use strict";
  const BLOCK_SAMPLES = 256;
  const MAX_WAV_BYTES = 16_000_000;
  const MAX_ZOOM = 32;
  const MIN_VIEW_MS = 25;

  function readWaveform(bytes) {
    if (!(bytes instanceof ArrayBuffer) || bytes.byteLength < 44 ||
        bytes.byteLength > MAX_WAV_BYTES) throw Error("PCM WAV size is unsupported");
    const view = new DataView(bytes);
    function tag(pos) {
      return String.fromCharCode(view.getUint8(pos), view.getUint8(pos + 1),
                                view.getUint8(pos + 2), view.getUint8(pos + 3));
    }
    if (tag(0) !== "RIFF" || tag(8) !== "WAVE") throw Error("Not a RIFF/WAVE file");
    let fmt = null, dataOffset = -1, dataLength = 0;
    for (let pos = 12; pos + 8 <= view.byteLength;) {
      const kind = tag(pos), size = view.getUint32(pos + 4, true);
      const start = pos + 8, end = start + size;
      if (end > view.byteLength) throw Error("Truncated WAV chunk");
      if (kind === "fmt " && !fmt) {
        if (size < 16) throw Error("Invalid PCM fmt chunk");
        fmt = {
          format: view.getUint16(start, true),
          channels: view.getUint16(start + 2, true),
          sampleRate: view.getUint32(start + 4, true),
          byteRate: view.getUint32(start + 8, true),
          blockAlign: view.getUint16(start + 12, true),
          bitsPerSample: view.getUint16(start + 14, true),
        };
      } else if (kind === "data" && dataOffset === -1) {
        dataOffset = start;
        dataLength = size;
      }
      pos = end + (size % 2);
    }
    if (!fmt || dataOffset < 0 || fmt.format !== 1 ||
        ![1, 2].includes(fmt.channels) || fmt.bitsPerSample !== 16 ||
        fmt.blockAlign !== fmt.channels * 2 ||
        fmt.byteRate !== fmt.sampleRate * fmt.blockAlign ||
        fmt.sampleRate < 8000 || fmt.sampleRate > 96000 ||
        dataLength < fmt.blockAlign || dataLength % fmt.blockAlign !== 0)
      throw Error("Waveform viewer requires PCM16 mono/stereo WAV (8–96 kHz)");
    const frames = dataLength / fmt.blockAlign;
    const bins = Math.ceil(frames / BLOCK_SAMPLES);
    const min = new Float32Array(bins), max = new Float32Array(bins);
    for (let i = 0; i < bins; i++) {
      let lo = 1, hi = -1;
      const base = i * BLOCK_SAMPLES;
      for (let frame = base; frame < Math.min(frames, base + BLOCK_SAMPLES); frame++) {
        for (let channel = 0; channel < fmt.channels; channel++) {
          const sample = view.getInt16(dataOffset + frame * fmt.blockAlign + channel * 2, true) / 32768;
          if (sample < lo) lo = sample;
          if (sample > hi) hi = sample;
        }
      }
      min[i] = lo; max[i] = hi;
    }
    return {
      sampleRate: fmt.sampleRate, channels: fmt.channels,
      durationMs: frames * 1000 / fmt.sampleRate,
      frames, blockSamples: BLOCK_SAMPLES, min, max,
    };
  }

  function viewport(durationMs, zoom, pan) {
    if (!Number.isFinite(durationMs) || durationMs <= 0) throw Error("Invalid WAV duration");
    const ratio = Math.max(1, Math.min(MAX_ZOOM, Number(zoom) || 1));
    const width = Math.min(durationMs, Math.max(MIN_VIEW_MS, durationMs / ratio));
    const maxStart = Math.max(0, durationMs - width);
    const startMs = maxStart * Math.max(0, Math.min(1, Number(pan) || 0));
    return {startMs, endMs: startMs + width, widthMs: width};
  }

  function timeFromX(x, cssWidth, view) {
    if (!Number.isFinite(cssWidth) || cssWidth <= 0) return Math.round(view.startMs);
    return Math.round(view.startMs +
      Math.max(0, Math.min(1, x / cssWidth)) * view.widthMs);
  }

  function xFromTime(time, cssWidth, view) {
    if (!Number.isFinite(cssWidth) || cssWidth <= 0) return 0;
    return (time - view.startMs) * cssWidth / view.widthMs;
  }

  function attach({canvas, player, zoomInput, panInput, startInput, endInput,
                   onFeedback, getCues, getSegments}) {
    if (!canvas || !player) throw Error("Waveform canvas and player required");
    const context = canvas.getContext("2d");
    if (!context) throw Error("Canvas 2D is unavailable");
    let wave = null, activeSpeechId = null;
    let pendingLoad = 0;
    let drag = null, frameToken = null;
    let marks = {startMs:0, endMs:0};

    const report = msg => { if (onFeedback) onFeedback(msg); };
    const duration = () => wave?.durationMs || 0;
    const selectedView = () => viewport(duration(), zoomInput.value, Number(panInput.value)/1000);

    function updateMarks(){
      marks.startMs = Number(startInput.value);
      marks.endMs = Number(endInput.value);
      draw();
    }
    function setMarks(startMs, endMs) {
      const limit = duration();
      let a = Math.round(Math.max(0, Math.min(limit, startMs)));
      let b = Math.round(Math.max(0, Math.min(limit, endMs)));
      if (b < a) [a,b] = [b,a];
      marks = {startMs:a, endMs:b};
      startInput.value = String(a);
      endInput.value = String(b);
      draw();
    }
    function draw() {
      const bounds = canvas.getBoundingClientRect();
      const w = Math.max(1, Math.floor(bounds.width || 1));
      const h = Math.max(1, Math.floor(bounds.height || 184));
      const dpr = Math.max(1, Math.min(2, Number(root.devicePixelRatio) || 1));
      const realW = Math.round(w*dpr), realH = Math.round(h*dpr);
      if (canvas.width !== realW || canvas.height !== realH) {
        canvas.width=realW; canvas.height=realH;
      }
      context.setTransform(dpr,0,0,dpr,0,0);
      context.clearRect(0,0,w,h);
      context.fillStyle="#101c2d";
      context.fillRect(0,0,w,h);
      context.fillStyle="#b6c6df";
      context.font="12px sans-serif";
      if (!wave) {
        context.fillText("สร้างเสียงใน Speech Queue แล้วกดโหลดงานเพื่อแสดง Waveform",12,24);
        return;
      }
      const view=selectedView();
      // Backdrop: generated speech vs silence/masked regions.
      for (const seg of (getSegments?.() || [])) {
        const left=xFromTime(seg.start_ms,w,view);
        const right=xFromTime(seg.end_ms,w,view);
        if (right <= 0 || left >= w) continue;
        context.fillStyle=seg.kind==="speech"?"#1d3148":"#38283d";
        context.fillRect(Math.max(0,left),22,
                         Math.min(w,right)-Math.max(0,left),h-42);
      }
      // User-reviewed cue spans, never arbitrary outside text from imported JSON.
      const cues = getCues?.() || [];
      for (const cue of cues) {
        const a=xFromTime(cue.start_ms,w,view), b=xFromTime(cue.end_ms,w,view);
        if (b<=0 || a>=w) continue;
        context.fillStyle="rgba(73,180,128,.24)";
        context.fillRect(Math.max(0,a),22,
          Math.min(w,b)-Math.max(0,a),h-42);
      }
      const center = (h+20)/2, height = Math.max(12,(h-56)/2);
      context.strokeStyle="#7298c4";
      context.beginPath();
      context.moveTo(0,center+.5); context.lineTo(w,center+.5);context.stroke();
      // Cached min/max peaks in blocks, never decode the WAV repeatedly.
      context.strokeStyle="#8dc5f5";
      context.beginPath();
      const samplesPerMs = wave.sampleRate/1000;
      for (let px=0;px<w;px++) {
        const timeA=view.startMs + px*view.widthMs/w;
        const timeB=view.startMs + (px+1)*view.widthMs/w;
        const first=Math.max(0,Math.floor(timeA*samplesPerMs/wave.blockSamples));
        const last=Math.min(wave.min.length-1,
          Math.floor(Math.max(timeA,timeB-0.000001)*samplesPerMs/wave.blockSamples));
        let low=1,high=-1;
        for(let i=first;i<=last;i++){
          if(wave.min[i]<low)low=wave.min[i];
          if(wave.max[i]>high)high=wave.max[i];
        }
        // When zoomed in beyond one peak block, bars are deliberately
        // envelopes, not invented sample-accurate waveform oscillations.
        context.moveTo(px+.5,center-high*height);
        context.lineTo(px+.5,center-low*height);
      }
      context.stroke();
      // Selection and player location.
      if (Number.isFinite(marks.startMs) && Number.isFinite(marks.endMs) &&
          marks.endMs>marks.startMs) {
        const a=xFromTime(marks.startMs,w,view), b=xFromTime(marks.endMs,w,view);
        if (b>0 && a<w){
          context.fillStyle="rgba(250,197,68,.17)";
          context.fillRect(Math.max(0,a),22,Math.min(w,b)-Math.max(0,a),h-42);
        }
        context.strokeStyle="#f9c74f";context.beginPath();
        context.moveTo(a,22);context.lineTo(a,h-20);
        context.moveTo(b,22);context.lineTo(b,h-20);context.stroke();
      }
      const playTime=(Number(player.currentTime)||0)*1000;
      const playX=xFromTime(playTime,w,view);
      if(playX>=0 && playX<=w){
        context.strokeStyle="#ff8b90";context.beginPath();
        context.moveTo(playX,20);context.lineTo(playX,h-20);context.stroke();
      }
      context.fillStyle="#cbd9ea";
      context.fillText((view.startMs/1000).toFixed(2)+"s",8,14);
      const endLabel=(view.endMs/1000).toFixed(2)+"s";
      context.fillText(endLabel,Math.max(8,w-context.measureText(endLabel).width-8),14);
      context.fillText("Zoom "+Number(zoomInput.value)+"×  ·  "+
        (playTime/1000).toFixed(2)+"s",8,h-6);
    }

    async function load(speechId, audio) {
      if (!/^[0-9a-f]{32}$/.test(speechId)) throw Error("Invalid speech ID");
      const call=++pendingLoad;
      wave=null;activeSpeechId=null;draw();
      const response=await fetch("/v1/jobs/"+speechId+"/audio",{cache:"no-store"});
      if (!response.ok) throw Error("Cannot load generated WAV for waveform");
      const bytes=await response.arrayBuffer();
      if(call!==pendingLoad)return;
      const decoded=readWaveform(bytes);
      if(call!==pendingLoad)return;
      wave=decoded;
      activeSpeechId=speechId;
      zoomInput.value="1";panInput.value="0";panInput.disabled=true;
      setMarks(Number(startInput.value)||0,Number(endInput.value)||0);
      report("Waveform พร้อม ("+(decoded.durationMs/1000).toFixed(2)+
        "s · "+decoded.sampleRate+"Hz · PCM16) · คลิกเพื่อเลื่อนเสียง ลากเพื่อเลือกช่วง");
      draw();
    }
    function reset() {
      pendingLoad++;wave=null;activeSpeechId=null;drag=null;
      if(frameToken!=null){root.cancelAnimationFrame?.(frameToken);frameToken=null;}
      draw();
    }
    function fromPointer(event){
      const rect=canvas.getBoundingClientRect();
      return timeFromX(event.clientX-rect.left,rect.width,selectedView());
    }
    canvas.addEventListener("pointerdown",event=>{
      if(!wave || event.button!==0)return;
      drag={from:fromPointer(event),fromX:event.clientX};
      canvas.setPointerCapture?.(event.pointerId);
      event.preventDefault?.();
    });
    canvas.addEventListener("pointermove",event=>{
      if(!wave || !drag)return;
      const to=fromPointer(event);
      if(Math.abs(event.clientX-drag.fromX)>=3) {
        setMarks(Math.min(drag.from,to),Math.max(drag.from,to));
      }
    });
    canvas.addEventListener("pointerup",event=>{
      if(!wave||!drag)return;
      const to=fromPointer(event);
      if(Math.abs(event.clientX-drag.fromX)<3) {
        player.currentTime=to/1000;
        report("เลื่อนไปที่ "+(to/1000).toFixed(3)+" วินาที · คลิกลากเพื่อกำหนดเวลาเริ่ม–จบ");
      } else {
        setMarks(Math.min(drag.from,to),Math.max(drag.from,to));
        report("เลือกช่วง "+marks.startMs+"–"+marks.endMs+
          " ms · ไฮไลต์ข้อความแล้วกดเพิ่ม Cue");
      }
      drag=null;canvas.releasePointerCapture?.(event.pointerId);
      draw();
    });
    canvas.addEventListener("pointercancel",()=>{drag=null;draw();});
    canvas.addEventListener("keydown",event=>{
      if(!wave)return;
      let newTime=Number(player.currentTime)||0;
      if(event.key==="ArrowLeft")newTime-=(event.shiftKey?0.005:0.025);
      else if(event.key==="ArrowRight")newTime+=(event.shiftKey?0.005:0.025);
      else if(event.key==="Home")newTime=selectedView().startMs/1000;
      else if(event.key==="End")newTime=selectedView().endMs/1000;
      else return;
      event.preventDefault();
      player.currentTime=Math.max(0,Math.min(duration()/1000,newTime));
      draw();
    });
    zoomInput.addEventListener("input",()=>{
      panInput.disabled=Number(zoomInput.value)<=1;
      if(panInput.disabled)panInput.value="0";
      draw();
    });
    panInput.addEventListener("input",draw);
    startInput.addEventListener("input",updateMarks);
    endInput.addEventListener("input",updateMarks);
    player.addEventListener?.("timeupdate",draw);
    player.addEventListener?.("seeked",draw);
    player.addEventListener?.("play",()=>{
      const tick=()=>{
        frameToken=null;
        if(!player.paused && wave){draw();frameToken=root.requestAnimationFrame?.(tick)??null;}
      };
      if(frameToken===null && root.requestAnimationFrame)
        frameToken=root.requestAnimationFrame(tick);
    });
    player.addEventListener?.("pause",()=>{
      if(frameToken!==null){root.cancelAnimationFrame?.(frameToken);frameToken=null;}
      draw();
    });
    root.addEventListener?.("resize",draw);
    draw();
    return {load,reset,draw,setMarks,viewport:()=>wave?selectedView():null,
            get speechId(){return activeSpeechId;},get durationMs(){return duration();}};
  }

  root.VoxWaveformEditor={attach,readWaveform,viewport,timeFromX,xFromTime};
  if(typeof module!=="undefined"&&module.exports)
    module.exports={attach,readWaveform,viewport,timeFromX,xFromTime};
})(typeof window==="undefined"?globalThis:window);
