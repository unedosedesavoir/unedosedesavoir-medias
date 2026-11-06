#!/usr/bin/env python3
"""Range les illustrations ComfyUI récupérées depuis le PC dans images/<slug>/ (voir kit/comfy.md).

Usage :
    python3 kit/import_images.py 2026-11-16-pieuvre

Lit /mnt/user-data/uploads/unedosedesavoir/<slug>/<nom>_NNNNN_.png (fichiers copiés par
device_stage_files), garde pour chaque nom la version au numéro le plus élevé, la copie en
images/<slug>/<nom>.png et retire un éventuel cadre uni (même couleur sur les quatre bords).
"""
import glob
import os
import re
import shutil
import sys

import numpy as np
from PIL import Image

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SRC = "/mnt/user-data/uploads/unedosedesavoir"


def band(a, ref, tol=18):
    """Nombre de lignes depuis le bord dont presque tous les pixels ont la couleur ref."""
    n = 0
    for row in a:
        diff = np.abs(row.astype(int) - ref).max(axis=-1)
        if diff.mean() > tol or (diff > tol).mean() > 0.02:
            break
        n += 1
    return n


def trim_frame(path):
    im = Image.open(path).convert("RGB")
    a = np.asarray(im)
    ref = a[2, 2].astype(int)
    t, b = band(a, ref), band(a[::-1], ref)
    l, r = band(a.transpose(1, 0, 2), ref), band(a.transpose(1, 0, 2)[::-1], ref)
    if min(t, b, l, r) >= 6 and max(t, b, l, r) < min(a.shape[:2]) // 3:
        m = 4
        im.crop((l + m, t + m, a.shape[1] - r - m, a.shape[0] - b - m)).save(path)
        return f"cadre retiré (h{t} b{b} g{l} d{r})"
    return ""


def main(slug):
    best = {}
    for f in glob.glob(os.path.join(SRC, slug, "*.png")):
        m = re.match(r"(.+)_(\d+)_\.png$", os.path.basename(f))
        if m and int(m.group(2)) >= best.get(m.group(1), (0, ""))[0]:
            best[m.group(1)] = (int(m.group(2)), f)
    if not best:
        raise SystemExit(f"Aucune image dans {SRC}/{slug}")
    out = os.path.join(ROOT, "images", slug)
    os.makedirs(out, exist_ok=True)
    for name, (_, f) in sorted(best.items()):
        dest = os.path.join(out, f"{name}.png")
        shutil.copy(f, dest)
        note = trim_frame(dest)
        print(f"images/{slug}/{name}.png {note}".rstrip())


if __name__ == "__main__":
    main(sys.argv[1])
