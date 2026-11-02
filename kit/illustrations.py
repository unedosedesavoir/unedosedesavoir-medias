#!/usr/bin/env python3
"""Prépare les commandes d'illustration d'un post pour ComfyUI (voir kit/comfy.md).

Usage :
    python3 kit/illustrations.py posts/2026-11-03-zanzibar.json

Lit le champ « scene » de la couverture et de chaque slide (description en anglais du sujet
à dessiner), complète le JSON du post avec les noms d'images (« image »), et écrit
images/<slug>/prompts.json : la liste des images à générer (nom, prompt complet, taille, graine).
Le style graphique (vectoriel plat) et la palette du pilier sont ajoutés automatiquement.
"""
import json
import os
import sys
import zlib

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

STYLE = ("Flat vector editorial illustration of {scene}. Bold simple geometric shapes, limited palette of {palette}, "
         "subtle grain texture, clean modern poster style. {composition} No text, no letters, no words, no logo.")
COMPOSITION = {
    "cover": "Main subject large in the upper and middle part of the frame, plain simple ground in the bottom quarter.",
    "fact": "Wide landscape composition, subject centered, simple uncluttered background.",
}
SIZE = {"cover": (1088, 880), "fact": (1088, 592)}  # multiples de 16, au ratio des cadres du gabarit
PALETTES = {
    "lundi": "deep forest green, mint green and cream",
    "mardi": "warm parchment beige, terracotta orange, dark brown and muted teal",
    "mercredi": "deep burgundy red, soft pink, coral and cream",
    "jeudi": "midnight navy blue, periwinkle blue, pale lavender and warm golden orange",
    "vendredi": "deep purple, lilac, soft lavender and cream",
    "samedi": "golden yellow, warm ochre, charcoal black and tropical green",
    "dimanche": "charcoal black, coral red, warm grey and white",
}


def main(spec_path):
    spec = json.load(open(spec_path, encoding="utf-8"))
    pal = PALETTES[spec["pillar"]]
    items = [("cover", "01-couverture", spec["cover"])]
    items += [("fact", f"{i:02d}", s) for i, s in enumerate(spec["slides"], 2)]
    jobs = []
    for kind, name, block in items:
        scene = block.get("scene")
        if not scene:
            continue
        w, h = SIZE[kind]
        seed = block.get("seed", zlib.crc32(f"{spec['slug']}/{name}".encode()) % 10**9)
        jobs.append(dict(file=f"{name}.png", prompt=STYLE.format(scene=scene, palette=pal, composition=COMPOSITION[kind]),
                         width=w, height=h, seed=seed))
        block["image"] = f"{name}.png"
    out = os.path.join(ROOT, "images", spec["slug"])
    os.makedirs(out, exist_ok=True)
    with open(os.path.join(out, "prompts.json"), "w", encoding="utf-8") as f:
        json.dump(dict(slug=spec["slug"], jobs=jobs), f, ensure_ascii=False, indent=2)
    with open(spec_path, "w", encoding="utf-8") as f:
        json.dump(spec, f, ensure_ascii=False, indent=2)
        f.write("\n")
    print(f"{len(jobs)} illustrations à générer → images/{spec['slug']}/prompts.json")


if __name__ == "__main__":
    main(sys.argv[1])
