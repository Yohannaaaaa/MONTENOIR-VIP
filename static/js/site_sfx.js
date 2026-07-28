(function () {
  let ctx = null;
  function getCtx() {
    const AC = window.AudioContext || window.webkitAudioContext;
    if (!AC) return null;
    if (!ctx) ctx = new AC();
    if (ctx.state === 'suspended') ctx.resume();
    return ctx;
  }

  function tone(freq, dur, type, gainPeak, delay) {
    const c = getCtx();
    if (!c) return;
    const t0 = c.currentTime + (delay || 0);
    const osc = c.createOscillator();
    const gain = c.createGain();
    osc.type = type || 'sine';
    osc.frequency.setValueAtTime(freq, t0);
    gain.gain.setValueAtTime(0, t0);
    gain.gain.linearRampToValueAtTime(gainPeak || 0.2, t0 + 0.008);
    gain.gain.exponentialRampToValueAtTime(0.0001, t0 + dur);
    osc.connect(gain).connect(c.destination);
    osc.start(t0);
    osc.stop(t0 + dur + 0.03);
  }

  function noiseBurst(dur, gainPeak, delay, filterFreq) {
    const c = getCtx();
    if (!c) return;
    const t0 = c.currentTime + (delay || 0);
    const bufferSize = Math.max(1, Math.floor(c.sampleRate * dur));
    const buffer = c.createBuffer(1, bufferSize, c.sampleRate);
    const data = buffer.getChannelData(0);
    for (let i = 0; i < bufferSize; i++) data[i] = (Math.random() * 2 - 1) * (1 - i / bufferSize);
    const src = c.createBufferSource();
    src.buffer = buffer;
    const filter = c.createBiquadFilter();
    filter.type = 'bandpass';
    filter.frequency.value = filterFreq || 1800;
    const gain = c.createGain();
    gain.gain.setValueAtTime(gainPeak || 0.25, t0);
    gain.gain.exponentialRampToValueAtTime(0.0001, t0 + dur);
    src.connect(filter).connect(gain).connect(c.destination);
    src.start(t0);
  }

  window.SFX = {
    // Dice tumbling: a handful of quick decaying "clacks"
    diceRoll() {
      const hits = 5 + Math.floor(Math.random() * 3);
      for (let i = 0; i < hits; i++) {
        noiseBurst(0.06, 0.22 - i * 0.02, i * 0.07, 1000 + Math.random() * 1600);
      }
    },
    click() { tone(520, 0.08, 'triangle', 0.15); },
    move() { tone(340, 0.09, 'sine', 0.14); },
    hit() {
      noiseBurst(0.12, 0.3, 0, 500);
      tone(160, 0.15, 'sawtooth', 0.15, 0.02);
    },
    error() {
      tone(150, 0.18, 'sawtooth', 0.18);
      tone(110, 0.22, 'sawtooth', 0.14, 0.05);
    },
    win() {
      [523.25, 659.25, 783.99, 1046.5].forEach((f, i) => tone(f, 0.28, 'triangle', 0.18, i * 0.11));
    },
    cardFlip() { noiseBurst(0.05, 0.12, 0, 3000); },
    chip() {
      tone(900, 0.05, 'square', 0.08);
      tone(1200, 0.05, 'square', 0.06, 0.03);
    },
    turn() { tone(440, 0.06, 'sine', 0.1); }
  };
})();
