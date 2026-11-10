#!/usr/bin/env python3
"""Monte le Reel Instagram d'un post « Une Dose de Savoir » : court (~10 s) et pensé pour la vidéo.

Usage :
    python3 kit/reel.py posts/2026-11-11-exemple.json [--apercu]

Structure : une question d'accroche sur l'illustration de couverture (2,2 s), trois chiffres-chocs
en très gros avec l'illustration du fait (1,9 s chacun), puis un renvoi vers le carrousel du jour
(1,8 s). Léger zoom sur chaque écran, coupes franches, petite musique synthétisée par le script
(aucun droit à gérer). Le texte reste dans la zone visible des Reels (ni sous l'en-tête ni sous
la légende et les boutons d'Instagram).

Contenu : champ facultatif « reel » du post :
    "reel": {"hook": "Votre cerveau consomme combien d'énergie ?",
             "beats": [{"slide": 2, "big": "2 %", "text": "de votre poids"}, …]}
« slide » renvoie à la slide de fait dont on reprend l'illustration (2 = première slide de fait).
Sans champ « reel », le titre de couverture sert d'accroche et les trois premières slides de faits
donnent les chiffres. Sortie : medias/<slug>/reel.mp4 (1080×1920, 30 i/s, H.264 + AAC) ;
avec --apercu, aussi medias/<slug>/reel-apercu.jpg (les écrans côte à côte).
"""
import json
import os
import subprocess
import sys
import tempfile
import wave

import numpy as np

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import generate as G  # noqa: E402  (couleurs des piliers, polices, typographie française)
from playwright.sync_api import sync_playwright  # noqa: E402

ROOT = G.ROOT
W, H = 1080, 1920
FPS = 30
DUR_HOOK, DUR_BEAT, DUR_OUTRO = 2.2, 1.9, 1.8
RATE = 44100

FIT_JS = """() => {
  for (const el of document.querySelectorAll('[data-maxh]')) {
    let fs = parseFloat(getComputedStyle(el).fontSize);
    const mh = +el.dataset.maxh, mw = +(el.dataset.maxw || 900);
    while ((el.scrollHeight > mh || el.scrollWidth > mw) && fs > 30) { fs -= 4; el.style.fontSize = fs + 'px'; }
  }
  return true;
}"""


def default_reel(spec):
    return {"hook": spec["cover"]["title"],
            "beats": [{"slide": i + 2, "big": s.get("big", ""), "text": s["title"]}
                      for i, s in enumerate(spec["slides"][:3])]}


def image(slug, name, top, height, bg):
    path = os.path.join(ROOT, "images", slug, name)
    if not os.path.exists(path):
        return ""
    return (f'<img src="file://{path}" style="position:absolute;left:0;top:{top}px;width:{W}px;height:{height}px;'
            f'object-fit:cover">'
            f'<div style="position:absolute;left:0;top:{top - 2}px;width:{W}px;height:{height + 4}px;'
            f'background:linear-gradient(to bottom,{bg} 0%,{bg}00 22%,{bg}00 70%,{bg} 100%)"></div>')


def chip(p, label):
    badge = (f'<div style="width:64px;height:64px;border-radius:19px;background:{p["badge"]};display:flex;'
             f'align-items:center;justify-content:center">'
             + G.icon_svg(p["icon"], p["ink"], p["badge"], "width:44px;height:44px") + "</div>")
    return (f'<div style="position:absolute;top:220px;left:90px;display:flex;align-items:center;gap:16px;'
            f'background:{p["bg"]};padding:8px 28px 8px 8px;border-radius:27px;color:{p["accent"]}">{badge}'
            f'<span style="font-size:24px;font-weight:700;letter-spacing:4px">{G.html.escape(label)}</span></div>')


def root(p, inner):
    return (f'<div style="width:{W}px;height:{H}px;position:relative;overflow:hidden;background:{p["bg"]};'
            f'color:{p["fg"]};font-family:\'DM Sans\',sans-serif">{inner}</div>')


def frames(spec, reel):
    p = G.PILIERS[spec["pillar"]]
    slug = spec["slug"]
    title = "font-family:'Bricolage Grotesque',sans-serif;font-weight:800;letter-spacing:-2px;margin:0"
    out = []
    # 1. Accroche
    out.append(root(p, image(slug, "01-couverture.png", 760, 860, p["bg"]) + chip(p, f'{p["jour"]} · {p["label"]}')
                    + f'<h1 data-maxh="400" style="{title};position:absolute;left:90px;top:340px;width:900px;'
                      f'font-size:112px;line-height:1">{G.fr(reel["hook"])}</h1>'))
    # 2. Chiffres-chocs
    beats = reel["beats"]
    for k, b in enumerate(beats, 1):
        img = image(slug, f'{b["slide"]:02d}.png', 330, 640, p["bg"])
        out.append(root(p, img + chip(p, f'{k} / {len(beats)}')
                        + f'<div style="position:absolute;left:90px;top:960px;width:900px">'
                          f'<div data-maxh="260" style="{title};font-size:250px;line-height:1;color:{p["accent"]};'
                          f'white-space:nowrap">{G.fr(b["big"])}</div>'
                          f'<div data-maxh="200" style="font-size:68px;font-weight:700;line-height:1.15;margin-top:26px">'
                          f'{G.fr(b["text"])}</div></div>'))
    # 3. Renvoi vers le carrousel
    wm = G.icon_svg(p["icon"], p["wm"], p["bg"], "position:absolute;right:-160px;bottom:300px;width:700px;height:700px")
    out.append(root(p, wm + f'<div style="position:absolute;left:90px;top:560px;width:900px">'
                    f'<div style="{title};font-size:120px;line-height:1;color:{p["accent"]}">{G.fr(reel.get("outro_title", "Le détail ?"))}</div>'
                    f'<div data-maxh="260" style="{title};font-size:84px;line-height:1.05;margin-top:30px">'
                    f'{G.fr(reel.get("outro", "Tout est dans le carrousel du jour, sur le profil"))}</div>'
                    f'<div style="display:inline-block;margin-top:56px;font-size:42px;font-weight:700;padding:22px 44px;'
                    f'border-radius:999px;background:{p["badge"]};color:{p["ink"]}">{G.HANDLE}</div>'
                    f'<div style="font-size:40px;color:{p["muted"]};margin-top:40px">'
                    f'{G.fr("Abonnez-vous pour votre dose quotidienne")}</div></div>'))
    return out


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
        for m in notes[:4]:
            f = hz(m)
            out[seg] += 0.06 * env * (np.sin(2 * np.pi * f * tt) + 0.3 * np.sin(2 * np.pi * 2 * f * tt))
        for k in range(8):
            m = notes[[1, 2, 3, 4, 3, 2, 3, 4][k]] + 12
            s = start + k * beat / 2
            seg2 = (t >= s) & (t < s + 0.9)
            tt2 = t[seg2] - s
            out[seg2] += 0.05 * np.exp(-tt2 * 5) * np.sin(2 * np.pi * hz(m) * tt2)
        for k in range(4):
            s = start + k * beat
            seg3 = (t >= s) & (t < s + 0.25)
            tt3 = t[seg3] - s
            out[seg3] += 0.12 * np.exp(-tt3 * 18) * np.sin(2 * np.pi * (60 + 40 * np.exp(-tt3 * 30)) * tt3)
    out *= np.minimum(t / 0.2, 1) * np.minimum((seconds - t) / 1.0, 1)
    out = out / (np.abs(out).max() + 1e-9) * 0.55
    data = (np.stack([out, out], axis=1) * 32767).astype("<i2")
    with wave.open(path, "wb") as w:
        w.setnchannels(2)
        w.setsampwidth(2)
        w.setframerate(RATE)
        w.writeframes(data.tobytes())


def main(spec_path, apercu=False):
    spec = json.load(open(spec_path, encoding="utf-8"))
    reel = spec.get("reel") or default_reel(spec)
    pages = frames(spec, reel)
    durs = [DUR_HOOK] + [DUR_BEAT] * len(reel["beats"]) + [DUR_OUTRO]
    total = sum(durs)
    out_dir = os.path.join(ROOT, "medias", spec["slug"])
    os.makedirs(out_dir, exist_ok=True)
    with tempfile.TemporaryDirectory() as tmp:
        pngs = []
        with sync_playwright() as pw:
            b = pw.chromium.launch()
            pg = b.new_page(viewport={"width": W, "height": H})
            for i, body in enumerate(pages):
                html = os.path.join(tmp, "f.html")
                open(html, "w", encoding="utf-8").write(
                    f'<!doctype html><html lang="fr"><head><meta charset="utf-8">{G.FONT_CSS}</head><body>{body}</body></html>')
                pg.goto("file://" + html)
                pg.evaluate("document.fonts.ready")
                pg.evaluate(FIT_JS)
                png = os.path.join(tmp, f"f{i:02d}.png")
                pg.screenshot(path=png, clip={"x": 0, "y": 0, "width": W, "height": H})
                pngs.append(png)
            b.close()
        wav = os.path.join(tmp, "music.wav")
        music(total, wav)
        inputs, chain = [], []
        for i, (png, d) in enumerate(zip(pngs, durs)):
            n = round(d * FPS)
            inputs += ["-i", png]
            chain.append(f"[{i}:v]scale={2 * W}:{2 * H},zoompan=z='1+0.035*on/{n}':x='iw/2-(iw/zoom/2)':"
                         f"y='ih/2-(ih/zoom/2)':d={n}:s={W}x{H}:fps={FPS},setsar=1[v{i}]")
        chain.append("".join(f"[v{i}]" for i in range(len(pngs))) + f"concat=n={len(pngs)}:v=1:a=0,format=yuv420p[v]")
        mp4 = os.path.join(out_dir, "reel.mp4")
        cmd = ["ffmpeg", "-y", "-loglevel", "error", *inputs, "-i", wav, "-filter_complex", ";".join(chain),
               "-map", "[v]", "-map", f"{len(pngs)}:a", "-t", f"{total:.3f}", "-r", str(FPS),
               "-c:v", "libx264", "-preset", "medium", "-crf", "20", "-profile:v", "high",
               "-c:a", "aac", "-b:a", "128k", "-movflags", "+faststart", mp4]
        subprocess.run(cmd, check=True)
        if apercu:
            subprocess.run(["convert", *pngs, "-resize", "270x480", "+append",
                            os.path.join(out_dir, "reel-apercu.jpg")], check=True)
    print(f"medias/{spec['slug']}/reel.mp4 : {total:.1f} s, {os.path.getsize(mp4) / 1e6:.1f} Mo")


if __name__ == "__main__":
    main(sys.argv[1], apercu="--apercu" in sys.argv[2:])
