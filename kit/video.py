#!/usr/bin/env python3
"""Vidéo narrée d'un post « Une Dose de Savoir » : illustrations animées, voix off et sous-titres.

Usage :
    python3 kit/video.py posts/2026-11-11-exemple.json

Contenu : champ « voix » du post, une entrée par phrase :
    "voix": [{"say": "Texte lu par la voix", "sub": "Sous-titre affiché (facultatif, sinon say)",
              "image": "01-couverture.png"}, …]
« image » = fichier de images/<slug>/ montré pendant la phrase (zoom lent).
Voix : Piper (moteur libre, hors ligne) + voix française « siwis » (licence CC BY 4.0, à créditer :
« Voix : SIWIS, University of Edinburgh, CC BY 4.0 »). Téléchargés au premier lancement depuis
GitHub dans ~/.cache/piper. Musique douce synthétisée sous la voix (kit/reel.py).
Sortie : medias/<slug>/video.mp4 (1080×1920, 30 i/s, H.264 + AAC) et video-apercu.jpg.
"""
import json
import os
import subprocess
import sys
import tarfile
import tempfile
import urllib.request
import wave

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import generate as G  # noqa: E402
import reel as R  # noqa: E402  (musique, pastille)
from playwright.sync_api import sync_playwright  # noqa: E402

ROOT = G.ROOT
W, H, FPS = 1080, 1920, 30
IMG_Y, IMG_H = 300, 1000          # bande d'illustration
SUB_Y = 1330                      # haut de la zone des sous-titres (au-dessus de la légende Instagram)
PAUSE = 0.25                      # silence après chaque phrase
CACHE = os.path.expanduser("~/.cache/piper")
PIPER_URL = "https://github.com/rhasspy/piper/releases/download/2023.11.14-2/piper_linux_x86_64.tar.gz"
VOICE_URL = "https://github.com/rhasspy/piper/releases/download/v0.0.2/voice-fr-siwis-medium.tar.gz"


def ensure_piper():
    exe = os.path.join(CACHE, "bin", "piper", "piper")
    model = os.path.join(CACHE, "voice", "fr-siwis-medium.onnx")
    for url, sub, target in ((PIPER_URL, "bin", exe), (VOICE_URL, "voice", model)):
        if not os.path.exists(target):
            os.makedirs(os.path.join(CACHE, sub), exist_ok=True)
            tgz = os.path.join(CACHE, sub + ".tgz")
            urllib.request.urlretrieve(url, tgz)
            with tarfile.open(tgz) as t:
                t.extractall(os.path.join(CACHE, sub), filter="data")
    return exe, model


def say(exe, model, text, path):
    subprocess.run([exe, "--model", model, "--output_file", path, "--length_scale", "0.95"],
                   input=text.encode(), check=True, capture_output=True)
    with wave.open(path) as w:
        return w.getnframes() / w.getframerate()


SMALL = {"de", "du", "des", "la", "le", "les", "l'", "un", "une", "à", "au", "aux", "et", "en", "qu'", "que",
         "pour", "par", "sur", "dans", "avec", "son", "sa", "ses", "votre", "vos", "c'est", "il", "elle", "ne"}


def chunks(text, maxlen=34):
    """Découpe un sous-titre en morceaux courts : coupe d'abord après la ponctuation, ne laisse jamais
    un petit mot (de, la, un…) en fin de morceau. Les espaces insécables (2 %, 20 watts) ne sont pas coupées."""
    words = G.fr(text).split(" ")
    out, cur = [], []
    for w in words:
        if cur and len(" ".join(cur + [w])) > maxlen:
            carry = []
            while len(cur) > 1 and cur[-1].lower() in SMALL:
                carry.insert(0, cur.pop())
            out.append(" ".join(cur))
            cur = carry
        cur.append(w)
        if w[-1:] in ",;:" and len(" ".join(cur)) > maxlen * 0.45:
            out.append(" ".join(cur))
            cur = []
    if cur:
        out.append(" ".join(cur))
    return out


def overlay_html(p, label):
    """Calque fixe : fondus de l'illustration vers le fond + pastille du pilier."""
    bg = p["bg"]
    return (f'<div style="width:{W}px;height:{H}px;position:relative;font-family:\'DM Sans\',sans-serif">'
            f'<div style="position:absolute;left:0;top:{IMG_Y - 2}px;width:{W}px;height:{IMG_H + 4}px;'
            f'background:linear-gradient(to bottom,{bg} 0%,{bg}00 18%,{bg}00 72%,{bg} 100%)"></div>'
            + R.chip(p, label) + "</div>")


def sub_html(p, text):
    return (f'<div style="width:{W}px;height:300px;display:flex;align-items:flex-start;justify-content:center">'
            f'<div style="width:900px;text-align:center;font-family:\'Bricolage Grotesque\',sans-serif;'
            f'font-weight:800;font-size:76px;line-height:1.08;letter-spacing:-1px;color:{p["fg"]}">'
            f'{text}</div></div>')


def render_pngs(pages, tmp, size, prefix):
    paths = []
    with sync_playwright() as pw:
        b = pw.chromium.launch()
        pg = b.new_page(viewport={"width": size[0], "height": size[1]})
        for i, body in enumerate(pages):
            html = os.path.join(tmp, "p.html")
            open(html, "w", encoding="utf-8").write(
                f'<!doctype html><html lang="fr"><head><meta charset="utf-8">{G.FONT_CSS}'
                f'<style>html,body{{background:transparent}}</style></head><body>{body}</body></html>')
            pg.goto("file://" + html)
            pg.evaluate("document.fonts.ready")
            out = os.path.join(tmp, f"{prefix}{i:02d}.png")
            pg.screenshot(path=out, clip={"x": 0, "y": 0, "width": size[0], "height": size[1]}, omit_background=True)
            paths.append(out)
        b.close()
    return paths


def main(spec_path):
    spec = json.load(open(spec_path, encoding="utf-8"))
    p = G.PILIERS[spec["pillar"]]
    slug = spec["slug"]
    lines = spec["voix"]
    exe, model = ensure_piper()
    out_dir = os.path.join(ROOT, "medias", slug)
    with tempfile.TemporaryDirectory() as tmp:
        # 1. Voix, phrase par phrase (durées exactes pour caler images et sous-titres)
        durs, wavs = [], []
        for i, ln in enumerate(lines):
            wav = os.path.join(tmp, f"v{i:02d}.wav")
            durs.append(say(exe, model, ln["say"], wav) + PAUSE)
            wavs.append(wav)
        total = sum(durs)
        # 2. Calques : pastille + fondus, et un PNG par morceau de sous-titre
        [overlay] = render_pngs([overlay_html(p, f'{p["jour"]} · {p["label"]}')], tmp, (W, H), "ov")
        subs = []  # (phrase, png, début, fin) en secondes depuis le début de la phrase
        for i, ln in enumerate(lines):
            parts = chunks(ln.get("sub", ln["say"]))
            pngs = render_pngs([sub_html(p, c) for c in parts], tmp, (W, 300), f"s{i:02d}_")
            speak = durs[i] - PAUSE
            n_chars = sum(len(c) for c in parts)
            t = 0.0
            for k, (c, png) in enumerate(zip(parts, pngs)):
                d = speak * len(c) / n_chars
                subs.append((i, png, t, durs[i] if k == len(parts) - 1 else t + d))
                t += d
        # 3. Un segment vidéo par phrase
        segs = []
        for i, ln in enumerate(lines):
            n = round(durs[i] * FPS)
            img = os.path.join(ROOT, "images", slug, ln["image"])
            my_subs = [s for s in subs if s[0] == i]
            inputs = ["-f", "lavfi", "-i", f"color=c={p['bg']}:s={W}x{H}:r={FPS}:d={n / FPS:.3f}",
                      "-i", img, "-loop", "1", "-i", overlay]
            for s in my_subs:
                inputs += ["-loop", "1", "-i", s[1]]
            f = [f"[1:v]scale={2 * W}:{2 * IMG_H}:force_original_aspect_ratio=increase,crop={2 * W}:{2 * IMG_H},"
                 f"zoompan=z='1+0.08*on/{n}':x='iw/2-(iw/zoom/2)':y='ih/2-(ih/zoom/2)':d={n}:s={W}x{IMG_H}:fps={FPS}[z]",
                 f"[0:v][z]overlay=0:{IMG_Y}:shortest=1[a0]", "[a0][2:v]overlay=0:0:shortest=1[a1]"]
            last = "[a1]"
            for k, s in enumerate(my_subs):
                f.append(f"{last}[{3 + k}:v]overlay=0:{SUB_Y}:shortest=1:enable='between(t,{s[2]:.3f},{s[3]:.3f})'[b{k}]")
                last = f"[b{k}]"
            f.append(f"{last}format=yuv420p[v]")
            seg = os.path.join(tmp, f"seg{i:02d}.mp4")
            subprocess.run(["ffmpeg", "-y", "-loglevel", "error", *inputs, "-filter_complex", ";".join(f),
                            "-map", "[v]", "-frames:v", str(n), "-c:v", "libx264", "-preset", "medium", "-crf", "19",
                            seg], check=True)
            segs.append(seg)
        # 4. Assemblage : vidéo + voix (phrases bout à bout avec pauses) + musique douce dessous
        lst = os.path.join(tmp, "segs.txt")
        open(lst, "w").write("".join(f"file '{s}'\n" for s in segs))
        voice = os.path.join(tmp, "voice.wav")
        vin, vf = [], []
        for i, w in enumerate(wavs):
            vin += ["-i", w]
            vf.append(f"[{i}:a]aresample=44100,apad=pad_dur={PAUSE}[a{i}]")
        vf.append("".join(f"[a{i}]" for i in range(len(wavs))) + f"concat=n={len(wavs)}:v=0:a=1[out]")
        subprocess.run(["ffmpeg", "-y", "-loglevel", "error", *vin, "-filter_complex", ";".join(vf),
                        "-map", "[out]", voice], check=True)
        music = os.path.join(tmp, "music.wav")
        R.music(total, music)
        mp4 = os.path.join(out_dir, "video.mp4")
        subprocess.run(["ffmpeg", "-y", "-loglevel", "error", "-f", "concat", "-safe", "0", "-i", lst,
                        "-i", voice, "-i", music, "-filter_complex",
                        "[1:a]volume=1.0[v];[2:a]volume=0.22[m];[v][m]amix=inputs=2:duration=first:normalize=0,"
                        "loudnorm=I=-15:TP=-1.5[a]",
                        "-map", "0:v", "-map", "[a]", "-c:v", "copy", "-c:a", "aac", "-b:a", "160k",
                        "-movflags", "+faststart", "-shortest", mp4], check=True)
        # Aperçu : une image vers la fin de chaque phrase
        shots, t = [], 0.0
        for i, d in enumerate(durs):
            shot = os.path.join(tmp, f"shot{i:02d}.png")
            subprocess.run(["ffmpeg", "-y", "-loglevel", "error", "-ss", f"{t + d * 0.6:.2f}", "-i", mp4,
                            "-frames:v", "1", "-vf", "scale=270:480", shot], check=True)
            shots.append(shot)
            t += d
        subprocess.run(["convert", *shots, "+append", os.path.join(out_dir, "video-apercu.jpg")], check=True)
    print(f"medias/{slug}/video.mp4 : {total:.1f} s, {os.path.getsize(mp4) / 1e6:.1f} Mo")


if __name__ == "__main__":
    main(sys.argv[1])
