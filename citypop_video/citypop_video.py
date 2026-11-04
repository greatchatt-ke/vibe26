#!/usr/bin/env python3
"""1980년대 도쿄 시티팝 영상 자동 생성기

예시:
  python citypop_video.py                         # 랜덤 1편 (60초, 1280x720)
  python citypop_video.py --count 5 --duration 180  # 3분짜리 5편 일괄 생성
  python citypop_video.py --theme midnight --seed 42 --size 1920x1080
  python citypop_video.py --audio my_song.mp3     # 내 음원으로 영상만 생성
  python citypop_video.py --preview               # 빠른 미리보기 (640x360, 15초)
"""
import argparse
import json
import multiprocessing as mp
import subprocess
import sys
import time
from pathlib import Path

import numpy as np
from PIL import Image

from citypop.meta import make_meta
from citypop.music import SR, CityPopSynth, load_audio, save_wav
from citypop.drive import DriveScene
from citypop.visuals import THEMES, Scene

SCENES = {"bay": Scene, "drive": DriveScene}

_scene = None
_env = None


def _init_worker(scene_cls, scene_args, env):
    global _scene, _env
    _scene = SCENES[scene_cls](*scene_args)
    _env = env


def _render(i):
    t = i / _scene.fps
    e, o, b = _env
    return _scene.frame(t, float(e[i]), float(o[i]), bands=b[i]).tobytes()


def audio_envelopes(audio, fps, n_frames):
    """Per-frame loudness (0..1) and onset strength (0..1) for audio-reactive visuals."""
    mono = audio.mean(0)
    hop = SR / fps
    rms = np.array([np.sqrt(np.mean(mono[int(k * hop):int((k + 1) * hop)] ** 2) + 1e-12)
                    for k in range(n_frames)])
    rms = rms / (np.percentile(rms, 98) + 1e-9)
    on = np.clip(np.diff(rms, prepend=rms[0]), 0, None)
    on = on / (np.percentile(on, 99) + 1e-9)
    smooth = np.copy(rms)
    for k in range(1, len(smooth)):  # fast attack, slow release
        smooth[k] = max(rms[k], smooth[k - 1] * 0.88)
    # 12 log-spaced spectrum bands for the car-stereo equaliser
    edges = np.geomspace(50, 12000, 13)
    win = np.hanning(2048)
    freqs = np.fft.rfftfreq(2048, 1 / SR)
    idx = [np.where((freqs >= a) & (freqs < b))[0] for a, b in zip(edges[:-1], edges[1:])]
    bands = np.zeros((n_frames, 12), np.float32)
    for k in range(n_frames):
        c = int(k * hop)
        seg = mono[c:c + 2048]
        if len(seg) < 2048:
            seg = np.pad(seg, (0, 2048 - len(seg)))
        mag = np.abs(np.fft.rfft(seg * win))
        bands[k] = [np.log1p(mag[ix].mean() * 4) if len(ix) else 0 for ix in idx]
    bands /= np.percentile(bands, 97, axis=0) + 1e-9
    for k in range(1, n_frames):
        bands[k] = np.maximum(bands[k], bands[k - 1] * 0.85)
    return (np.clip(smooth, 0, 1).astype(np.float32), np.clip(on, 0, 1).astype(np.float32),
            np.clip(bands, 0, 1))


def make_video(seed, out_root, duration, W, H, fps, theme, audio_path, workers, crf, bpm, scene="bay"):
    t_start = time.time()
    rng = np.random.default_rng(seed)
    theme = theme or str(rng.choice(list(THEMES)))
    out_dir = Path(out_root) / f"citypop_{seed:05d}_{scene}_{theme}"
    out_dir.mkdir(parents=True, exist_ok=True)

    # 1) music
    if audio_path:
        audio = load_audio(audio_path)
        if duration:
            audio = audio[:, : int(duration * SR)]
        info = {"source": str(audio_path)}
    else:
        synth = CityPopSynth(seed=seed, bpm=bpm)
        audio = synth.render(duration)
        info = synth.info()
    total = audio.shape[1] / SR
    wav = out_dir / "audio.wav"
    save_wav(wav, audio)
    print(f"[{seed}] 🎹 audio {total:.1f}s {info}", flush=True)

    # 2) metadata
    meta = make_meta(seed, theme, info, total, scene)
    (out_dir / "metadata.json").write_text(json.dumps(meta, ensure_ascii=False, indent=2), encoding="utf-8")

    # 3) visuals -> ffmpeg
    n_frames = int(total * fps)
    env = audio_envelopes(audio, fps, n_frames)
    scene_args = (W, H, fps, seed, theme, meta["title_jp"], meta["title_en"], meta["artist"], total)
    video = out_dir / "video.mp4"
    cmd = ["ffmpeg", "-y", "-v", "error", "-f", "rawvideo", "-pix_fmt", "rgb24", "-s", f"{W}x{H}",
           "-r", str(fps), "-i", "-", "-i", str(wav), "-c:v", "libx264", "-preset", "medium",
           "-crf", str(crf), "-maxrate", "14M", "-bufsize", "28M", "-pix_fmt", "yuv420p", "-c:a", "aac", "-b:a", "192k",
           "-movflags", "+faststart", "-shortest", str(video)]
    ff = subprocess.Popen(cmd, stdin=subprocess.PIPE)
    ctx = mp.get_context("fork")
    with ctx.Pool(workers, initializer=_init_worker, initargs=(scene, scene_args, env)) as pool:
        for k, buf in enumerate(pool.imap(_render, range(n_frames), chunksize=8)):
            ff.stdin.write(buf)
            if k % (fps * 5) == 0:
                el = time.time() - t_start
                print(f"\r[{seed}] 🎞  frame {k}/{n_frames} ({100 * k / n_frames:4.1f}%) {el:5.0f}s",
                      end="", flush=True)
    ff.stdin.close()
    if ff.wait() != 0:
        raise RuntimeError("ffmpeg failed")

    # 4) thumbnail (title visible, clean frame)
    _init_worker(scene, scene_args, env)
    Image.fromarray(_scene.frame(5.0, 0.7, 0.0, bands=env[2][min(len(env[2]) - 1, 5 * fps)])).save(out_dir / "thumbnail.jpg", quality=92)
    print(f"\n[{seed}] ✅ {video}  ({time.time() - t_start:.0f}s)", flush=True)
    return out_dir


def main():
    ap = argparse.ArgumentParser(description="1980s Tokyo City Pop video generator")
    ap.add_argument("--count", type=int, default=1, help="생성할 영상 수 (일괄 자동화)")
    ap.add_argument("--seed", type=int, default=None, help="시드 (같은 시드 = 같은 영상)")
    ap.add_argument("--duration", type=float, default=60, help="영상 길이(초)")
    ap.add_argument("--size", default="1280x720", help="해상도, 예: 1920x1080")
    ap.add_argument("--fps", type=int, default=30)
    ap.add_argument("--scene", choices=list(SCENES), default="bay",
                    help="bay=도쿄만 야경, drive=도쿄 도심 야간 드라이브(우핸들·좌측통행)")
    ap.add_argument("--theme", choices=list(THEMES), default=None, help="미지정 시 랜덤")
    ap.add_argument("--bpm", type=int, default=None)
    ap.add_argument("--audio", default=None, help="직접 준비한 음원 사용 (mp3/wav 등)")
    ap.add_argument("--out", default="output")
    ap.add_argument("--workers", type=int, default=max(1, mp.cpu_count()))
    ap.add_argument("--crf", type=int, default=20, help="화질 (낮을수록 고화질)")
    ap.add_argument("--preview", action="store_true", help="빠른 미리보기 640x360, 15초")
    a = ap.parse_args()

    W, H = map(int, a.size.lower().split("x"))
    if a.preview:
        W, H, a.duration, a.fps = 640, 360, 15, 24
    seed0 = a.seed if a.seed is not None else int(time.time()) % 100000
    for i in range(a.count):
        make_video(seed0 + i, a.out, a.duration, W, H, a.fps, a.theme, a.audio, a.workers, a.crf, a.bpm, a.scene)


if __name__ == "__main__":
    sys.exit(main())
