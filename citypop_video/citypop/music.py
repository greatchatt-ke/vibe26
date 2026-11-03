"""City pop music synthesizer (numpy only).

Generates a full arrangement: Rhodes/DX7-style electric piano, slap bass,
string pad, synth lead, LinnDrum-style drums with gated reverb, plus
tape wow/flutter and hiss for that 1980s cassette feel.
"""
import wave
import numpy as np

SR = 44100
TAU = 2 * np.pi
NOTE_NAMES = ["C", "C#", "D", "Eb", "E", "F", "F#", "G", "Ab", "A", "Bb", "B"]

CHORDS = {
    "maj7": [0, 4, 7, 11], "maj9": [0, 4, 7, 11, 14], "6/9": [0, 4, 7, 9, 14],
    "m7": [0, 3, 7, 10], "m9": [0, 3, 7, 10, 14], "m11": [0, 3, 7, 10, 14, 17],
    "7": [0, 4, 7, 10], "9": [0, 4, 7, 10, 14], "13": [0, 4, 10, 14, 21],
    "7sus": [0, 5, 7, 10], "7#9": [0, 4, 10, 15],
}

# (root offset from key, quality, beats) — classic city pop / J-pop moves
PROGRESSIONS = {
    "two_of_us": [(5, "maj7", 4), (4, "7", 4), (9, "m7", 2), (7, "m7", 1), (0, "7", 1)],
    "royal_road": [(5, "maj9", 4), (7, "7sus", 2), (7, "13", 2), (4, "m7", 4), (9, "m9", 4)],
    "ii_v_i": [(2, "m9", 4), (7, "13", 4), (0, "maj9", 4), (9, "m7", 4)],
    "bayside": [(0, "maj7", 4), (9, "m9", 4), (2, "m7", 4), (7, "9", 4)],
    "midnight": [(5, "maj7", 4), (4, "m7", 4), (2, "m11", 4), (7, "7sus", 2), (7, "7#9", 2)],
}

EP_RHYTHMS = [  # (16th step, length in steps, velocity)
    [(0, 3, 1.0), (3, 2, 0.7), (6, 2, 0.85), (10, 2, 0.7), (12, 3, 0.8)],
    [(0, 2, 1.0), (4, 1, 0.6), (6, 4, 0.9), (11, 2, 0.75), (14, 2, 0.7)],
    [(2, 2, 0.8), (6, 2, 0.9), (10, 2, 0.8), (14, 2, 0.85)],
]
BASS_PATTERNS = [  # (step, degree, length) R=root O=octave 5=fifth A=approach
    [(0, "R", 3), (3, "R", 1), (6, "O", 1), (8, "R", 2), (10, "5", 2), (13, "O", 1), (14, "A", 2)],
    [(0, "R", 2), (2, "O", 1), (4, "R", 1), (6, "R", 2), (8, "5", 2), (11, "O", 1), (12, "R", 2), (15, "A", 1)],
    [(0, "R", 4), (6, "R", 1), (7, "O", 1), (8, "R", 3), (11, "5", 1), (12, "O", 1), (14, "A", 2)],
]


def mtof(m):
    return 440.0 * 2 ** ((np.asarray(m, dtype=np.float64) - 69) / 12)


def fftconv(x, h):
    n = len(x) + len(h) - 1
    nfft = 1 << (n - 1).bit_length()
    return np.fft.irfft(np.fft.rfft(x, nfft) * np.fft.rfft(h, nfft), nfft)[:n]


def adsr(n, a, r_start, r, sr=SR):
    t = np.arange(n) / sr
    env = np.minimum(1.0, t / max(a, 1e-4))
    rel = np.where(t > r_start, np.exp(-(t - r_start) / max(r, 1e-4)), 1.0)
    return env * rel


class Mixer:
    def __init__(self, seconds):
        self.n = int(seconds * SR)
        self.dry = np.zeros((2, self.n), np.float32)
        self.wet = np.zeros((2, self.n), np.float32)  # reverb send

    def add(self, sig, t0, pan=0.0, gain=1.0, send=0.2):
        i = int(t0 * SR)
        if i >= self.n or i + len(sig) <= 0:
            return
        if i < 0:
            sig, i = sig[-i:], 0
        k = min(len(sig), self.n - i)
        s = sig[:k] * gain
        lg, rg = np.cos((pan + 1) * np.pi / 4), np.sin((pan + 1) * np.pi / 4)
        self.dry[0, i:i + k] += s * lg
        self.dry[1, i:i + k] += s * rg
        if send:
            self.wet[0, i:i + k] += s * lg * send
            self.wet[1, i:i + k] += s * rg * send


class CityPopSynth:
    def __init__(self, seed=0, bpm=None, key=None, progression=None):
        self.rng = np.random.default_rng(seed)
        r = self.rng
        self.bpm = bpm or int(r.integers(98, 118))
        self.key = key if key is not None else int(r.integers(0, 12))
        self.prog_name = str(progression or r.choice(list(PROGRESSIONS)))
        self.prog = PROGRESSIONS[self.prog_name]
        self.beat = 60.0 / self.bpm
        self.step = self.beat / 4
        self.ep_rhythm = EP_RHYTHMS[r.integers(len(EP_RHYTHMS))]
        self.bass_pat = BASS_PATTERNS[r.integers(len(BASS_PATTERNS))]
        self._cache = {}

    # ---------- harmony helpers ----------
    def chord_at(self, beat):
        total = sum(c[2] for c in self.prog)
        b = beat % total
        acc = 0
        for i, (off, q, length) in enumerate(self.prog):
            if b < acc + length - 1e-6:
                nxt = self.prog[(i + 1) % len(self.prog)]
                return (self.key + off) % 12, q, (self.key + nxt[0]) % 12
            acc += length
        return (self.key + self.prog[0][0]) % 12, self.prog[0][1], self.key

    @staticmethod
    def voicing(root_pc, quality, low=53):
        ivs = CHORDS[quality]
        tones = ivs[1:] if len(ivs) >= 4 else ivs
        notes = sorted({low + ((root_pc + iv - low) % 12) for iv in tones})
        return notes

    # ---------- instruments ----------
    def ep_note(self, midi, dur, vel):
        f = float(mtof(midi))
        n = int((dur + 1.2) * SR)
        t = np.arange(n) / SR
        idx = 1.6 * np.exp(-t * 7) + 0.25 * vel
        y = np.sin(TAU * f * t + idx * np.sin(TAU * f * t))
        y += 0.12 * vel * np.exp(-t * 25) * np.sin(TAU * f * 14.0 * t)  # tine "bark"
        env = np.exp(-t * 1.6) * adsr(n, 0.002, dur, 0.12)
        return (y * env * vel).astype(np.float32)

    def bass_note(self, midi, dur, vel, slap=False):
        f = float(mtof(midi))
        n = int((dur + 0.15) * SR)
        t = np.arange(n) / SR
        y = np.zeros(n)
        bright = 1.8 if slap else 0.9
        for h in range(1, 14):
            if f * h > 5000:
                break
            y += (1.0 / h) * np.exp(-t * (2.0 + h * 2.2 / bright)) * np.sin(TAU * f * h * t)
        y += 0.6 * np.sin(TAU * f * t) * np.exp(-t * 1.5)  # sustain body
        if slap:
            y += 0.4 * self.rng.standard_normal(n) * np.exp(-t * 300)
        env = adsr(n, 0.003, dur, 0.03)
        return np.tanh(1.5 * y * env * vel).astype(np.float32)

    def pad_chord(self, notes, dur):
        n = int((dur + 1.0) * SR)
        t = np.arange(n) / SR
        y = np.zeros(n)
        for m in notes:
            f0 = float(mtof(m))
            for det in (-0.004, 0.0, 0.0043):
                f = f0 * (1 + det)
                ph = self.rng.uniform(0, TAU)
                for h in range(1, 9):
                    y += np.sin(TAU * f * h * t + ph * h) / h ** 1.6
        env = adsr(n, 0.6, dur, 0.5)
        y *= env / (len(notes) * 3)
        return y.astype(np.float32)

    def lead_note(self, midi, dur, vel):
        f = float(mtof(midi))
        n = int((dur + 0.25) * SR)
        t = np.arange(n) / SR
        vib = 1 + 0.006 * np.sin(TAU * 5.5 * t) * np.clip((t - 0.15) / 0.3, 0, 1)
        ph = TAU * np.cumsum(f * vib) / SR
        y = np.zeros(n)
        for h, a in ((1, 1.0), (2, 0.45), (3, 0.5), (4, 0.2), (5, 0.25), (7, 0.12)):
            y += a * np.sin(h * ph)
        bright = 0.5 + 0.5 * np.exp(-t * 4)
        y = np.tanh(y * (0.8 + bright))
        env = adsr(n, 0.02, dur, 0.12) * (0.85 + 0.15 * np.exp(-t * 3))
        return (0.35 * y * env * vel).astype(np.float32)

    def bell_note(self, midi, vel):  # DX7 bell for sparkles
        f = float(mtof(midi))
        n = int(2.0 * SR)
        t = np.arange(n) / SR
        y = np.sin(TAU * f * t + 2.5 * np.exp(-t * 3) * np.sin(TAU * f * 3.5 * t))
        return (y * np.exp(-t * 2.5) * vel * 0.25).astype(np.float32)

    def drum(self, name):
        if name in self._cache:
            return self._cache[name]
        r = self.rng
        if name == "kick":
            n = int(0.45 * SR); t = np.arange(n) / SR
            f = 48 + 110 * np.exp(-t * 32)
            y = np.sin(TAU * np.cumsum(f) / SR) * np.exp(-t * 7.5)
            y += 0.3 * r.standard_normal(n) * np.exp(-t * 400)
            y = np.tanh(1.6 * y)
        elif name == "snare":
            n = int(0.25 * SR); t = np.arange(n) / SR
            noise = r.standard_normal(n)
            noise = noise - np.convolve(noise, np.ones(6) / 6, "same")
            y = 0.7 * noise * np.exp(-t * 16) + 0.6 * np.sin(TAU * 185 * t) * np.exp(-t * 28)
            ir_n = int(0.32 * SR); ir_t = np.arange(ir_n) / SR
            ir = r.standard_normal(ir_n) * np.exp(-ir_t * 3) * 0.03
            ir[0] = 1.0
            y = fftconv(y, ir)
            gate = np.clip((0.3 - np.arange(len(y)) / SR) / 0.02, 0, 1)  # 80s gated reverb
            y *= gate
        elif name == "clap":
            n = int(0.3 * SR); t = np.arange(n) / SR
            noise = r.standard_normal(n)
            noise = noise - np.convolve(noise, np.ones(4) / 4, "same")
            env = np.zeros(n)
            for d in (0.0, 0.011, 0.022):
                env += np.where(t >= d, np.exp(-(t - d) * 90), 0)
            env += 0.4 * np.where(t >= 0.03, np.exp(-(t - 0.03) * 14), 0)
            y = noise * env
        elif name in ("hat", "ohat"):
            n = int((0.08 if name == "hat" else 0.4) * SR); t = np.arange(n) / SR
            noise = r.standard_normal(n)
            for _ in range(3):
                noise = np.diff(noise, prepend=0)
            y = noise / 8 * np.exp(-t * (55 if name == "hat" else 9))
        elif name.startswith("tom"):
            base = {"tom1": 220, "tom2": 160, "tom3": 115}[name]
            n = int(0.5 * SR); t = np.arange(n) / SR
            f = base * (1 + 0.6 * np.exp(-t * 18))
            y = np.sin(TAU * np.cumsum(f) / SR) * np.exp(-t * 7)
        else:
            raise ValueError(name)
        y = (y / (np.max(np.abs(y)) + 1e-9)).astype(np.float32)
        self._cache[name] = y
        return y

    # ---------- arrangement ----------
    def sections(self, n_bars):
        sec = []
        for b in range(n_bars):
            if b < 4:
                s = "intro"
            elif b >= n_bars - 4:
                s = "outro"
            else:
                blk = (b - 4) // 8
                pos = blk % 4
                s = ["verse", "chorus", "verse", "chorus"][pos]
                if n_bars > 40 and blk % 4 == 2 and (b - 4) % 8 < 4:
                    s = "break"
            sec.append(s)
        return sec

    def make_motif(self, bars=2):
        r = self.rng
        scale = [0, 2, 4, 7, 9, 11, 14, 16, 19, 21]  # major pentatonic + maj7 color
        rhythms = [
            [0, 2, 3, 6, 8, 10, 11, 14],
            [0, 3, 6, 7, 10, 12],
            [2, 4, 6, 8, 9, 12, 14],
        ]
        notes = []
        deg = int(r.integers(2, 6))
        for bar in range(bars):
            rh = rhythms[r.integers(len(rhythms))]
            for i, st in enumerate(rh):
                deg = int(np.clip(deg + r.choice([-2, -1, -1, 0, 1, 1, 2]), 0, len(scale) - 1))
                nxt = rh[i + 1] if i + 1 < len(rh) else 16 + (2 if bar == bars - 1 else 0)
                length = max(1, min(nxt - st, 4))
                if bar == bars - 1 and i == len(rh) - 1:
                    length = 6
                notes.append((bar * 16 + st, length, scale[deg]))
        return notes

    def render(self, seconds):
        bar_len = self.beat * 4
        n_bars = max(8, int(round(seconds / bar_len)))
        seconds_total = n_bars * bar_len + 3.0
        mix = Mixer(seconds_total)
        secs = self.sections(n_bars)
        r = self.rng
        motif_a, motif_b = self.make_motif(), self.make_motif()
        lead_base = 72 + (self.key if self.key < 6 else self.key - 12)
        hum = lambda: r.normal(0, 0.004)

        for b, s in enumerate(secs):
            t_bar = b * bar_len
            next_s = secs[b + 1] if b + 1 < n_bars else "end"
            fill = next_s != s and s in ("verse", "chorus", "break")
            # --- pad (one chord per change) ---
            if s != "break" or True:
                beat = 0
                while beat < 4:
                    root, q, _ = self.chord_at(b * 4 + beat)
                    # length until chord change within bar
                    length = 1
                    while beat + length < 4 and self.chord_at(b * 4 + beat + length)[:2] == (root, q):
                        length += 1
                    notes = self.voicing(root, q, low=60)
                    g = 0.10 if s in ("intro", "outro", "break") else 0.07
                    mix.add(self.pad_chord(notes, length * self.beat), t_bar + beat * self.beat,
                            pan=0.0, gain=g, send=0.5)
                    beat += length
            # --- electric piano comping ---
            for st, ln, vel in self.ep_rhythm:
                if s == "intro" and b < 2 and st not in (0, 6):
                    continue
                root, q, _ = self.chord_at(b * 4 + st / 4)
                notes = self.voicing(root, q, low=53)
                for j, m in enumerate(notes):
                    sig = self.ep_note(m, ln * self.step, vel * (0.9 + 0.1 * r.random()))
                    mix.add(sig, t_bar + st * self.step + j * 0.004 + hum(),
                            pan=-0.35 + 0.7 * j / max(1, len(notes) - 1), gain=0.10, send=0.25)
            # --- bass ---
            if s in ("verse", "chorus", "break"):
                for st, dg, ln in self.bass_pat:
                    root, q, nxt = self.chord_at(b * 4 + st / 4)
                    base = 33 + ((root - 9) % 12)  # A1..G#2
                    m = {"R": base, "O": base + 12, "5": base + 7,
                         "A": 33 + ((nxt - 9) % 12) + r.choice([-1, 1])}[dg]
                    sig = self.bass_note(m, ln * self.step * 0.9, 0.9, slap=(dg == "O"))
                    mix.add(sig, t_bar + st * self.step + hum(), pan=0.0, gain=0.32, send=0.03)
            # --- drums ---
            if s in ("verse", "chorus"):
                for st in range(16):
                    tt = t_bar + st * self.step
                    if fill and st >= 12:
                        tom = ["tom1", "tom1", "tom2", "tom3"][st - 12]
                        mix.add(self.drum(tom), tt, pan=0.4 - 0.25 * (st - 12), gain=0.35, send=0.25)
                        continue
                    if st in (0, 8) or (st == 10 and b % 2) or (st == 7 and s == "chorus"):
                        mix.add(self.drum("kick"), tt, gain=0.55, send=0.02)
                    if st in (4, 12):
                        mix.add(self.drum("snare"), tt, gain=0.35, send=0.15)
                        mix.add(self.drum("clap"), tt + 0.003, pan=0.1, gain=0.18, send=0.2)
                    if st % 2 == 0:
                        h = "ohat" if st in (2, 10) and s == "chorus" else "hat"
                        mix.add(self.drum(h), tt + hum(), pan=0.3, gain=0.10 if st % 4 else 0.07, send=0.05)
                    else:
                        mix.add(self.drum("hat"), tt + hum(), pan=0.3, gain=0.05, send=0.05)
            elif s == "intro" and b >= 2:
                for st in range(0, 16, 2):
                    mix.add(self.drum("hat"), t_bar + st * self.step, pan=0.3, gain=0.06, send=0.1)
            # --- lead melody (AABA over 8 bars) ---
            if s == "chorus":
                pos = ((b - 4) % 8)
                motif = motif_b if pos in (4, 5) else motif_a
                half = pos % 2
                for st, ln, deg in motif:
                    if st // 16 != half:
                        continue
                    m = lead_base + deg
                    if pos in (6, 7) and st >= 24:
                        m -= 2  # resolve variation
                    sig = self.lead_note(m, ln * self.step, 0.9)
                    t0 = t_bar + (st % 16) * self.step + hum()
                    mix.add(sig, t0, pan=0.0, gain=0.22, send=0.35)
                    for k, (d, pn) in enumerate(((0.75, -0.6), (1.5, 0.6))):  # ping-pong delay
                        mix.add(sig, t0 + d * self.beat, pan=pn, gain=0.22 * 0.35 / (k + 1), send=0.3)
            # --- bell sparkles ---
            if s in ("intro", "break", "outro") and b % 2 == 0:
                root, q, _ = self.chord_at(b * 4)
                for k, m in enumerate(self.voicing(root, q, low=79)[:4]):
                    mix.add(self.bell_note(m, 0.8), t_bar + (2 + k) * self.step * 2,
                            pan=-0.5 + k * 0.33, gain=0.25, send=0.6)

        # final ringing chord
        root, q, _ = self.chord_at(0)
        for j, m in enumerate(self.voicing(root, q, low=53)):
            mix.add(self.ep_note(m, 2.5, 0.8), n_bars * bar_len, pan=-0.3 + 0.2 * j, gain=0.1, send=0.4)
        mix.add(self.bass_note(33 + ((root - 9) % 12), 2.5, 0.8), n_bars * bar_len, gain=0.25)

        audio = self.master(mix)
        self.n_bars = n_bars
        return audio

    def master(self, mix):
        r = self.rng
        # stereo chorus on the whole dry bus (subtle, very 80s)
        n = mix.n
        t = np.arange(n) / SR
        dry = mix.dry.astype(np.float64)
        out = np.zeros_like(dry)
        idx = np.arange(n, dtype=np.float64)
        for ch, ph in ((0, 0.0), (1, np.pi / 2)):
            d = (0.007 + 0.002 * np.sin(TAU * 0.6 * t + ph)) * SR
            out[ch] = 0.8 * dry[ch] + 0.35 * np.interp(idx - d, idx, dry[ch], left=0)
        # hall reverb (decorrelated noise IR)
        ir_n = int(2.4 * SR)
        ir_t = np.arange(ir_n) / SR
        for ch in range(2):
            ir = r.standard_normal(ir_n) * np.exp(-ir_t * 2.6)
            ir = np.convolve(ir, np.ones(8) / 8, "same")  # darken
            ir[: int(0.02 * SR)] = 0  # pre-delay
            out[ch] += 0.08 * fftconv(mix.wet[ch].astype(np.float64), ir)[:n]
        # vintage EQ: low cut 35Hz, soft roll-off above ~11kHz
        spec = np.fft.rfft(out, axis=1)
        freqs = np.fft.rfftfreq(n, 1 / SR)
        eq = (1 / np.sqrt(1 + (35 / np.maximum(freqs, 1)) ** 4)) / np.sqrt(1 + (freqs / 11000) ** 4)
        eq *= 1 + 0.25 * np.exp(-((freqs - 90) / 60) ** 2)  # warm low bump
        out = np.fft.irfft(spec * eq, n, axis=1)
        # tape wow & flutter
        warp = 0.0012 * np.sin(TAU * 0.45 * t) + 0.00025 * np.sin(TAU * 6.3 * t)
        src = idx + np.cumsum(warp)
        for ch in range(2):
            out[ch] = np.interp(src, idx, out[ch])
        # glue compression-ish soft clip + normalize
        out /= np.max(np.abs(out)) + 1e-9
        out = np.tanh(out * 1.6) / np.tanh(1.6)
        out += 0.0025 * r.standard_normal(out.shape)  # tape hiss
        fade_in = np.clip(t / 0.4, 0, 1)
        fade_out = np.clip((t[-1] - t) / 3.0, 0, 1)
        out *= fade_in * fade_out
        out *= 0.89 / (np.max(np.abs(out)) + 1e-9)
        return out.astype(np.float32)

    def info(self):
        chords = [f"{NOTE_NAMES[(self.key + o) % 12]}{q}" for o, q, _ in self.prog]
        return {"bpm": self.bpm, "key": NOTE_NAMES[self.key] + " major",
                "progression": self.prog_name, "chords": chords}


def save_wav(path, audio):
    pcm = (np.clip(audio.T, -1, 1) * 32767).astype("<i2")
    with wave.open(str(path), "wb") as w:
        w.setnchannels(2)
        w.setsampwidth(2)
        w.setframerate(SR)
        w.writeframes(pcm.tobytes())


def load_audio(path):
    """Decode any audio file via ffmpeg -> (2, N) float32 at SR."""
    import subprocess
    raw = subprocess.run(["ffmpeg", "-v", "error", "-i", str(path), "-f", "f32le",
                          "-ac", "2", "-ar", str(SR), "-"], check=True, capture_output=True).stdout
    return np.frombuffer(raw, np.float32).reshape(-1, 2).T.copy()
