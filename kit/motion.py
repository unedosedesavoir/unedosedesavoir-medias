#!/usr/bin/env python3
"""Vidéo en motion design d'un post « Une Dose de Savoir » : sujets détourés et animés, voix off,
sous-titres mot à mot, chiffres qui défilent.

Usage :
    python3 kit/motion.py posts/2026-11-11-exemple.json

Contenu : champ « voix » du post (voir kit/video.py), une entrée par phrase :
    {"say": "texte lu", "sub": "sous-titre (facultatif)", "image": "03.png", "big": "20 %" (facultatif)}
Chaque phrase devient un plan : le sujet de l'illustration est détouré automatiquement (modèle
ISNet, ~/.u2net/isnet-general-use.onnx, téléchargé depuis GitHub au premier lancement), puis il
entre en rebondissant, flotte, et des particules animent le fond ; « big » s'affiche en grand avec
un compteur qui monte ; les mots du sous-titre s'allument au rythme de la voix.
Les images sont calculées une à une (Playwright), puis assemblées avec la voix (kit/video.py)
et la musique (kit/reel.py). Sortie : medias/<slug>/video.mp4 et video-apercu.jpg.
"""
import json
import os
import random
import re
import subprocess
import sys
import tempfile
import urllib.request

import numpy as np
from PIL import Image

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import generate as G  # noqa: E402
import reel as R  # noqa: E402
import video as V  # noqa: E402
from playwright.sync_api import sync_playwright  # noqa: E402

ROOT = G.ROOT
W, H, FPS = 1080, 1920, 30
MODEL = os.path.expanduser("~/.u2net/isnet-general-use.onnx")
MODEL_URL = "https://github.com/danielgatis/rembg/releases/download/v0.0.0/isnet-general-use.onnx"


# ---------------------------------------------------------------- détourage
def cutout(src, dst):
    if os.path.exists(dst) and os.path.getmtime(dst) >= os.path.getmtime(src):
        return dst
    import onnxruntime as ort
    if not os.path.exists(MODEL):
        os.makedirs(os.path.dirname(MODEL), exist_ok=True)
        urllib.request.urlretrieve(MODEL_URL, MODEL)
    sess = ort.InferenceSession(MODEL, providers=["CPUExecutionProvider"])
    im = Image.open(src).convert("RGB")
    x = np.asarray(im.resize((1024, 1024), Image.BICUBIC)).astype(np.float32) / 255.0 - 0.5
    m = sess.run(None, {sess.get_inputs()[0].name: x.transpose(2, 0, 1)[None]})[0][0, 0]
    m = (m - m.min()) / (m.max() - m.min() + 1e-8)
    m = np.clip((m - 0.15) / 0.7, 0, 1)  # bords plus nets
    alpha = Image.fromarray((m * 255).astype(np.uint8)).resize(im.size, Image.BICUBIC)
    out = im.convert("RGBA")
    out.putalpha(alpha)
    out = out.crop(out.getbbox() or (0, 0, *im.size))
    os.makedirs(os.path.dirname(dst), exist_ok=True)
    out.save(dst)
    return dst


# ---------------------------------------------------------------- page animée
PAGE_JS = r"""
window.setT = (t) => {
  const D = window.SHOT;
  const clamp = (v) => Math.max(0, Math.min(1, v));
  const back = (x) => { const c1 = 1.70158, c3 = c1 + 1; return 1 + c3 * Math.pow(x - 1, 3) + c1 * Math.pow(x - 1, 2); };
  const cubic = (x) => 1 - Math.pow(1 - x, 3);
  // sujet : entrée en rebond, puis flottement
  const e = back(clamp(t / 0.6));
  const s = 0.5 + 0.5 * e, ty = (1 - clamp(t / 0.6)) * 160 + Math.sin(2 * Math.PI * t / 2.6) * 12;
  const rot = Math.sin(2 * Math.PI * t / 3.4) * 2.2 + (1 - clamp(t / 0.6)) * -8;
  const subj = document.getElementById('subj');
  subj.style.transform = `translate(-50%, 0) translateY(${ty}px) rotate(${rot}deg) scale(${s})`;
  subj.style.opacity = clamp(t / 0.15);
  const sh = document.getElementById('shadow');
  sh.style.transform = `translateX(-50%) scale(${0.6 + 0.4 * e - Math.sin(2 * Math.PI * t / 2.6) * 0.05})`;
  sh.style.opacity = 0.35 * clamp(t / 0.3);
  document.getElementById('glow').style.transform = `translate(-50%,-50%) scale(${0.8 + 0.2 * cubic(clamp(t / 0.8)) + Math.sin(t * 2) * 0.03})`;
  // particules
  for (const p of document.querySelectorAll('.pt')) {
    const y = (+p.dataset.y - t * +p.dataset.v) % 1400; const yy = y < 0 ? y + 1400 : y;
    p.style.transform = `translate(${+p.dataset.x + Math.sin(t * +p.dataset.f + +p.dataset.p) * 24}px, ${yy + 240}px) scale(${p.dataset.s})`;
    p.style.opacity = +p.dataset.o * clamp(t / 0.4);
  }
  // grand chiffre qui monte
  const big = document.getElementById('big');
  if (big && D.big) {
    const k = cubic(clamp((t - 0.35) / 1.0));
    let txt = D.big.text;
    if (D.big.value !== null) {
      const v = D.big.value * k;
      let num = v.toFixed(D.big.dec).replace('.', ',');
      if (D.big.group) num = num.replace(/\B(?=(\d{3})+(?!\d))/g, ' ');
      txt = D.big.prefix + num + D.big.suffix;
    }
    big.textContent = txt;
    const pop = back(clamp((t - 0.3) / 0.45));
    big.style.transform = `scale(${0.4 + 0.6 * pop})`;
    big.style.opacity = clamp((t - 0.3) / 0.15);
  }
  // sous-titres mot à mot
  for (const c of document.querySelectorAll('.chunk')) {
    const on = t >= +c.dataset.a && t < +c.dataset.b;
    c.style.display = on ? 'block' : 'none';
    if (!on) continue;
    const ci = clamp((t - +c.dataset.a) / 0.12);
    c.style.transform = `translateY(${(1 - ci) * 30}px)`;
    for (const w of c.querySelectorAll('.w')) {
      const a = +w.dataset.a, b = +w.dataset.b;
      w.style.opacity = t >= a ? 1 : 0.28;
      w.style.color = (t >= a && t < b) ? D.accent : D.fg;
    }
  }
  return true;
};
"""


def parse_big(text):
    if not text:
        return None
    m = re.match(r"^(\D*?)(\d[\d  ]*(?:[.,]\d+)?)(.*)$", text)
    if not m:
        return {"text": text, "value": None}
    raw = m.group(2)
    trailing = raw[len(raw.rstrip("  ")):]  # l'espace avant l'unité appartient au suffixe
    num = raw.rstrip("  ").replace(" ", "").replace(" ", "").replace(",", ".")
    dec = len(num.split(".")[1]) if "." in num else 0
    suffix = (trailing + m.group(3)).replace(" ", " ")
    return {"text": text.replace(" ", " "), "value": float(num), "dec": dec, "prefix": m.group(1),
            "group": bool(re.search(r"\d[\s\u202f\u00a0]\d", raw)),  # « 1 825 » groupé, une année (« 2003 ») non
            "suffix": suffix}


def shot_html(p, label, subject_path, big, chunks_t, seed):
    rnd = random.Random(seed)
    pts = "".join(
        f'<div class="pt" data-x="{rnd.randint(40, 1040)}" data-y="{rnd.randint(0, 1400)}" '
        f'data-v="{rnd.uniform(25, 70):.1f}" data-f="{rnd.uniform(0.6, 1.6):.2f}" data-p="{rnd.uniform(0, 6):.2f}" '
        f'data-s="{rnd.uniform(0.5, 1.4):.2f}" data-o="{rnd.uniform(0.25, 0.6):.2f}" '
        f'style="position:absolute;left:0;top:0;width:18px;height:18px;border-radius:50%;'
        f'background:{p["accent"] if i % 3 else p["fg"]}"></div>' for i in range(16))
    big_html = (f'<div id="big" style="position:absolute;left:0;right:0;top:300px;text-align:center;'
                f'font-family:\'Bricolage Grotesque\',sans-serif;font-weight:800;font-size:190px;line-height:1;'
                f'letter-spacing:-4px;color:{p["accent"]};transform-origin:50% 60%"></div>' if big else "")
    subj_top = 560 if big else 420
    subj_h = 700 if big else 820
    subs = ""
    for a, b, words in chunks_t:
        spans = " ".join(f'<span class="w" data-a="{wa:.3f}" data-b="{wb:.3f}">{w}</span>' for w, wa, wb in words)
        subs += (f'<div class="chunk" data-a="{a:.3f}" data-b="{b:.3f}" style="display:none;position:absolute;'
                 f'left:90px;right:90px;top:1360px;text-align:center;font-family:\'Bricolage Grotesque\',sans-serif;'
                 f'font-weight:800;font-size:80px;line-height:1.08;letter-spacing:-1px">{spans}</div>')
    return (f'<div style="width:{W}px;height:{H}px;position:relative;overflow:hidden;background:{p["bg"]};'
            f'color:{p["fg"]};font-family:\'DM Sans\',sans-serif">'
            f'<div id="glow" style="position:absolute;left:50%;top:{subj_top + subj_h // 2}px;width:980px;height:980px;'
            f'border-radius:50%;background:radial-gradient(circle,{p["accent"]}55 0%,{p["accent"]}00 68%)"></div>'
            f'{pts}'
            f'<div id="shadow" style="position:absolute;left:50%;top:{subj_top + subj_h - 30}px;width:560px;height:60px;'
            f'border-radius:50%;background:#000;filter:blur(18px)"></div>'
            f'<img id="subj" src="file://{subject_path}" style="position:absolute;left:50%;top:{subj_top}px;'
            f'max-width:900px;height:{subj_h}px;object-fit:contain;transform-origin:50% 90%">'
            f'{big_html}{R.chip(p, label)}{subs}</div>')


def timed_chunks(sub_text, speak):
    parts = V.chunks(sub_text)
    words = [w for c in parts for w in c.split(" ")]
    total_chars = sum(len(w) + 1 for w in words)
    t, out = 0.0, []
    for c in parts:
        ws, a = [], t
        for w in c.split(" "):
            d = speak * (len(w) + 1) / total_chars
            ws.append((w, t, t + d))
            t += d
        out.append((a, t, ws))
    return out


def main(spec_path):
    spec = json.load(open(spec_path, encoding="utf-8"))
    p = G.PILIERS[spec["pillar"]]
    slug = spec["slug"]
    lines = spec["voix"]
    label = f'{p["jour"]} · {p["label"]}'
    exe, model = V.ensure_piper()
    out_dir = os.path.join(ROOT, "medias", slug)
    with tempfile.TemporaryDirectory() as tmp:
        durs, wavs = [], []
        for i, ln in enumerate(lines):
            wav = os.path.join(tmp, f"v{i:02d}.wav")
            durs.append(V.say(exe, model, ln["say"], wav) + V.PAUSE)
            wavs.append(wav)
        total = sum(durs)
        frames_dir = os.path.join(tmp, "frames")
        os.makedirs(frames_dir)
        n_frame = 0
        with sync_playwright() as pw:
            b = pw.chromium.launch()
            pg = b.new_page(viewport={"width": W, "height": H})
            for i, ln in enumerate(lines):
                src = os.path.join(ROOT, "images", slug, ln["image"])
                subj = cutout(src, os.path.join(ROOT, "images", slug, "cut", ln["image"]))
                big = parse_big(ln.get("big"))
                chunks_t = timed_chunks(ln.get("sub", ln["say"]), durs[i] - V.PAUSE)
                last = chunks_t[-1]
                chunks_t[-1] = (last[0], durs[i] + 0.01, last[2])
                html = os.path.join(tmp, f"shot{i:02d}.html")
                open(html, "w", encoding="utf-8").write(
                    f'<!doctype html><html lang="fr"><head><meta charset="utf-8">{G.FONT_CSS}'
                    f'<script>window.SHOT={json.dumps({"big": big, "accent": p["accent"], "fg": p["fg"]})};'
                    f'{PAGE_JS}</script></head><body>'
                    f'{shot_html(p, label, subj, big, chunks_t, seed=i + 7)}</body></html>')
                pg.goto("file://" + html)
                pg.evaluate("document.fonts.ready")
                n = round(durs[i] * FPS)
                for f in range(n):
                    pg.evaluate(f"setT({f / FPS:.4f})")
                    pg.screenshot(path=os.path.join(frames_dir, f"{n_frame:05d}.jpg"), type="jpeg", quality=92,
                                  clip={"x": 0, "y": 0, "width": W, "height": H})
                    n_frame += 1
            b.close()
        voice = os.path.join(tmp, "voice.wav")
        vin, vf = [], []
        for i, w in enumerate(wavs):
            vin += ["-i", w]
            vf.append(f"[{i}:a]aresample=44100,apad=pad_dur={V.PAUSE}[a{i}]")
        vf.append("".join(f"[a{i}]" for i in range(len(wavs))) + f"concat=n={len(wavs)}:v=0:a=1[out]")
        subprocess.run(["ffmpeg", "-y", "-loglevel", "error", *vin, "-filter_complex", ";".join(vf),
                        "-map", "[out]", voice], check=True)
        music = os.path.join(tmp, "music.wav")
        R.music(total, music)
        mp4 = os.path.join(out_dir, "video.mp4")
        subprocess.run(["ffmpeg", "-y", "-loglevel", "error", "-framerate", str(FPS),
                        "-i", os.path.join(frames_dir, "%05d.jpg"), "-i", voice, "-i", music, "-filter_complex",
                        "[1:a]volume=1.0[v];[2:a]volume=0.22[m];[v][m]amix=inputs=2:duration=first:normalize=0,"
                        "loudnorm=I=-15:TP=-1.5[a]",
                        "-map", "0:v", "-map", "[a]", "-c:v", "libx264", "-preset", "medium", "-crf", "19",
                        "-pix_fmt", "yuv420p", "-c:a", "aac", "-b:a", "160k", "-movflags", "+faststart",
                        "-shortest", mp4], check=True)
        shots, t = [], 0.0
        for i, d in enumerate(durs):
            idx = int((t + d * 0.6) * FPS)
            shots.append(os.path.join(frames_dir, f"{min(idx, n_frame - 1):05d}.jpg"))
            t += d
        subprocess.run(["convert", *shots, "-resize", "270x480", "+append",
                        os.path.join(out_dir, "video-apercu.jpg")], check=True)
    print(f"medias/{slug}/video.mp4 : {total:.1f} s, {n_frame} images, {os.path.getsize(mp4) / 1e6:.1f} Mo")


if __name__ == "__main__":
    main(sys.argv[1])
