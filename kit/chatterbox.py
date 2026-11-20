#!/usr/bin/env python3
"""Voix off Chatterbox (ton « posé », choisi par la personne le 20 novembre 2026), générée dans ComfyUI
sur le PC de la personne (extension « FL ChatterBox », modèle Chatterbox Multilingual, licence MIT :
aucun crédit à mettre dans la légende).

Deux étapes, autour de la mise en file dans ComfyUI (voir kit/comfy.md, section « Voix off ») :

    python3 kit/chatterbox.py jobs posts/<fichier>.json      # affiche le JSON des phrases à générer
    python3 kit/chatterbox.py import posts/<fichier>.json <dossier des .flac récupérés>

« import » coupe chaque phrase au premier silence long (le modèle improvise parfois après la phrase),
vérifie sa durée et écrit images/<slug>/voix/v00.wav, v01.wav… que kit/motion.py utilise à la place
de la voix Piper. Une phrase anormalement courte ou longue est signalée : la régénérer (autre seed).
"""
import glob
import json
import os
import subprocess
import sys

import numpy as np

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SR = 24000
GAP = 0.6  # silence (s) qui marque la fin de la phrase
# Ton « posé » : temperature, cfg_weight, repetition_penalty, exaggeration
SETTINGS = {"language": "French (fr)", "temperature": 0.5, "cfg_weight": 0.5, "repetition_penalty": 1.5,
            "exaggeration": 0.35, "min_p": 0.05, "top_p": 1, "seed": 3}


def jobs(spec):
    slug = spec["slug"]
    return {"slug": slug, "settings": SETTINGS,
            "jobs": [{"file": f"v{i:02d}", "prefix": f"unedosedesavoir/{slug}/voix/v{i:02d}", "text": ln["say"]}
                     for i, ln in enumerate(spec["voix"])]}


def trim(src, dst):
    raw = subprocess.run(["ffmpeg", "-loglevel", "error", "-i", src, "-ac", "1", "-ar", str(SR), "-f", "f32le", "-"],
                         capture_output=True, check=True).stdout
    a = np.frombuffer(raw, dtype="<f4").copy()
    hop = int(SR * 0.02)
    env = np.array([np.sqrt(np.mean(a[i:i + hop] ** 2)) for i in range(0, len(a) - hop, hop)])
    loud = env > max(env.max() * 0.04, 1e-4)
    start = int(np.argmax(loud))
    end, quiet = start, 0
    for i in range(start, len(loud)):
        if loud[i]:
            end, quiet = i, 0
        else:
            quiet += 1
            if quiet * 0.02 >= GAP:
                break
    s0 = max(0, start * hop - int(0.05 * SR))
    s1 = min(len(a), (end + 1) * hop + int(0.12 * SR))
    out = a[s0:s1].copy()
    fade = int(0.03 * SR)
    out[-fade:] *= np.linspace(1, 0, fade)
    subprocess.run(["ffmpeg", "-loglevel", "error", "-y", "-f", "f32le", "-ar", str(SR), "-ac", "1", "-i", "-", dst],
                   input=out.astype("<f4").tobytes(), check=True)
    return len(a) / SR, len(out) / SR


def import_voix(spec, src_dir):
    slug = spec["slug"]
    out_dir = os.path.join(ROOT, "images", slug, "voix")
    os.makedirs(out_dir, exist_ok=True)
    ok = True
    for i, ln in enumerate(spec["voix"]):
        cands = sorted(glob.glob(os.path.join(src_dir, f"v{i:02d}_*.flac")))
        if not cands:
            print(f"v{i:02d} : MANQUANT")
            ok = False
            continue
        total, kept = trim(cands[-1], os.path.join(out_dir, f"v{i:02d}.wav"))
        import re
        syll = len(re.findall(r"[aeiouyéèêëàâîïôûù]+", ln["say"].lower()))  # groupes de voyelles ≈ syllabes
        expected = syll / 6.5
        flag = ""
        if kept < expected * 0.55 or kept > expected * 1.8:
            flag = "  <- À VÉRIFIER (durée inhabituelle : régénérer avec une autre seed)"
            ok = False
        print(f"v{i:02d} : {total:.1f} s -> {kept:.2f} s (attendu ~{expected:.1f} s){flag}")
    return ok


if __name__ == "__main__":
    cmd, post = sys.argv[1], sys.argv[2]
    spec = json.load(open(post, encoding="utf-8"))
    if cmd == "jobs":
        print(json.dumps(jobs(spec), ensure_ascii=False))
    elif cmd == "import":
        sys.exit(0 if import_voix(spec, sys.argv[3]) else 1)
