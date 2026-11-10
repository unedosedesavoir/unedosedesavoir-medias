#!/usr/bin/env python3
"""Monte la version Reel (vidéo verticale) d'un carrousel « Une Dose de Savoir ».

Usage :
    python3 kit/reel.py posts/2026-11-11-exemple.json

Lit medias/<slug>/01.png … NN.png (produits par kit/generate.py) et écrit medias/<slug>/reel.mp4 :
1080×1920, 30 i/s, H.264 + AAC. Chaque slide est posée au centre d'un fond de la couleur du
pilier, avec une transition glissée ; la bande-son est une petite
boucle instrumentale synthétisée ici même (aucune musique extérieure, donc aucun droit à gérer).
"""
import json
import os
import subprocess
import sys
import tempfile
import wave

import numpy as np
from PIL import Image

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
W, H = 1080, 1920
SLIDE_W, SLIDE_H = 1080, 1350
FPS = 30
TRANSITION = 0.35
DUR_COVER, DUR_FACT, DUR_CTA = 2.6, 3.6, 3.0
# Couleurs de fond et d'accent (mêmes valeurs que PILIERS dans kit/generate.py)
COLORS = {
    "lundi": ("#12392B", "#8BE3A8"), "mardi": ("#EFE4CF", "#9C3D16"),
    "mercredi": ("#5B1424", "#FF9AA8"), "jeudi": ("#0B1430", "#9DB8FF"),
    "vendredi": ("#2D1B4E", "#D2B2FF"), "samedi": ("#F3C343", "#1E1A10"),
    "dimanche": ("#161616", "#FF5C4D"),
}
RATE = 44100


def frame(png, bg, path):
    canvas = Image.new("RGB", (W, H), bg)
    slide = Image.open(png).convert("RGB").resize((SLIDE_W, SLIDE_H))
    canvas.paste(slide, (0, (H - SLIDE_H) // 2))
    canvas.save(path)


def music(seconds, path):
    """Nappe douce + arpège (do – la – fa – sol), 96 bpm, fondu d'entrée et de sortie."""
    t = np.arange(int(seconds * RATE)) / RATE
    out = np.zeros_like(t)
    beat = 60 / 96
    bar = 4 * beat
    chords = [[48, 55, 60, 64, 71], [45, 52, 57, 60, 67], [41, 48, 53, 57, 64], [43, 50, 55, 59, 62]]
    hz = lambda m: 440 * 2 ** ((m - 69) / 12)
    for i in range(int(seconds / bar) + 1):
        notes = chords[i % 4]
        start = i * bar
        seg = (t >= start) & (t < start + bar + 0.6)
        tt = t[seg] - start
        env = np.minimum(tt / 0.5, 1) * np.exp(-np.maximum(tt - bar, 0) / 0.25)
        for m in notes[:4]:  # nappe
            f = hz(m)
            out[seg] += 0.06 * env * (np.sin(2 * np.pi * f * tt) + 0.3 * np.sin(2 * np.pi * 2 * f * tt))
        for k in range(8):  # arpège en croches
            m = notes[[1, 2, 3, 4, 3, 2, 3, 4][k]] + 12
            s = start + k * beat / 2
            seg2 = (t >= s) & (t < s + 0.9)
            tt2 = t[seg2] - s
            out[seg2] += 0.05 * np.exp(-tt2 * 5) * np.sin(2 * np.pi * hz(m) * tt2)
        for k in range(4):  # pulsation grave très légère
            s = start + k * beat
            seg3 = (t >= s) & (t < s + 0.25)
            tt3 = t[seg3] - s
            out[seg3] += 0.12 * np.exp(-tt3 * 18) * np.sin(2 * np.pi * (60 + 40 * np.exp(-tt3 * 30)) * tt3)
    out *= np.minimum(t / 0.3, 1) * np.minimum((seconds - t) / 1.5, 1)
    out = out / (np.abs(out).max() + 1e-9) * 0.55
    data = (np.stack([out, out], axis=1) * 32767).astype("<i2")
    with wave.open(path, "wb") as w:
        w.setnchannels(2)
        w.setsampwidth(2)
        w.setframerate(RATE)
        w.writeframes(data.tobytes())


def main(spec_path):
    spec = json.load(open(spec_path, encoding="utf-8"))
    slug = spec["slug"]
    bg, _accent = COLORS[spec["pillar"]]
    out_dir = os.path.join(ROOT, "medias", slug)
    n = 2 + len(spec["slides"])
    pngs = [os.path.join(out_dir, f"{i:02d}.png") for i in range(1, n + 1)]
    missing = [p for p in pngs if not os.path.exists(p)]
    if missing:
        raise SystemExit(f"Slides manquantes (lancer d'abord kit/generate.py) : {missing}")
    durs = [DUR_COVER] + [DUR_FACT] * len(spec["slides"]) + [DUR_CTA]
    total = sum(durs) - TRANSITION * (n - 1)
    with tempfile.TemporaryDirectory() as tmp:
        inputs = []
        for i, (png, d) in enumerate(zip(pngs, durs)):
            f = os.path.join(tmp, f"f{i:02d}.png")
            frame(png, bg, f)
            inputs += ["-loop", "1", "-framerate", str(FPS), "-t", f"{d:.3f}", "-i", f]
        wav = os.path.join(tmp, "music.wav")
        music(total, wav)
        inputs += ["-i", wav]
        chain, prev, offset = [], "[0:v]", 0.0
        for i in range(1, n):
            offset += durs[i - 1] - TRANSITION
            label = f"[x{i}]"
            chain.append(f"{prev}[{i}:v]xfade=transition=slideleft:duration={TRANSITION}:offset={offset:.3f}{label}")
            prev = label
        chain.append(f"{prev}format=yuv420p[v]")
        mp4 = os.path.join(out_dir, "reel.mp4")
        cmd = ["ffmpeg", "-y", "-loglevel", "error", *inputs, "-filter_complex", ";".join(chain),
               "-map", "[v]", "-map", f"{n}:a", "-t", f"{total:.3f}", "-r", str(FPS),
               "-c:v", "libx264", "-preset", "medium", "-crf", "20", "-profile:v", "high",
               "-c:a", "aac", "-b:a", "128k", "-movflags", "+faststart", mp4]
        subprocess.run(cmd, check=True)
    size = os.path.getsize(mp4) / 1e6
    print(f"medias/{slug}/reel.mp4 : {total:.1f} s, {size:.1f} Mo")


if __name__ == "__main__":
    main(sys.argv[1])
