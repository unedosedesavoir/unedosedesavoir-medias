#!/usr/bin/env python3
"""Génère les illustrations d'un carrousel avec ComfyUI (API locale), une par slide.

Usage (sur l'ordinateur où ComfyUI tourne) :
    python3 kit/comfy.py posts/2026-11-03-zanzibar.json            # toutes les slides manquantes
    python3 kit/comfy.py posts/....json --only 2,3 --force         # régénérer certaines slides
    python3 kit/comfy.py --checkpoints                             # lister les modèles installés

Chaque slide (cover, slides[], cta) peut porter un champ "illustration" : une description courte
EN ANGLAIS de la scène (sujet, objets, composition), sans consigne de style. Le style commun
(illustration plate, couleurs du pilier, pas de texte, pas de réalisme) est ajouté ici.
Les images vont dans illustrations/<slug>/NN.png (01 = couverture), puis kit/generate.py les intègre.
Le prompt et la graine de chaque image sont notés dans illustrations/<slug>/prompts.json.

Workflow par défaut : kit/comfy/z_image_turbo_api.json (Z-Image-Turbo, d'après le template officiel
ComfyUI : UNETLoader z_image_turbo_bf16, CLIPLoader qwen_3_4b type lumina2, VAE ae, shift 3,
8 pas, cfg 1, res_multistep/simple ; pas de prompt négatif, d'où des consignes « no text,
not a photograph » dans le prompt positif). Alternative : --workflow kit/comfy/sdxl_api.json
--checkpoint <modèle SDXL>. On peut aussi fournir le sien (format « API ») ; les valeurs "%PROMPT%", "%NEGATIVE%", "%SEED%", "%WIDTH%", "%HEIGHT%", "%CHECKPOINT%" y
sont remplacées. Les images de la 1re sortie SaveImage sont récupérées.
"""
import argparse
import json
import os
import random
import sys
import time
import urllib.error
import urllib.parse
import urllib.request
import uuid

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

# Couleurs dominantes demandées au modèle, accordées aux fonds des piliers (voir generate.py).
PALETTES = {
    "lundi": "deep forest green, mint green and cream",
    "mardi": "warm beige, terracotta and dark brown",
    "mercredi": "deep burgundy, soft pink and coral",
    "jeudi": "midnight navy blue, periwinkle and pale lavender",
    "vendredi": "deep purple, lilac and soft violet",
    "samedi": "sunny yellow, mustard and charcoal black",
    "dimanche": "near black, charcoal grey and vivid coral red",
}
STYLE = ("flat vector illustration, minimalist editorial style, bold simple geometric shapes, "
         "subtle paper grain texture, limited color palette of {palette}, centered composition, "
         "plenty of empty space at the top and bottom, illustration, not a photograph, "
         "no text, no letters, no logo")
NEGATIVE = ("photo, photorealistic, realistic, hyperrealistic, 3d render, cgi, text, letters, words, "
            "numbers, caption, watermark, logo, signature, brand, famous character, celebrity, "
            "blurry, noisy, deformed, extra fingers, gore, blood, violence")


def api(server, path, data=None, raw=False, timeout=30):
    req = urllib.request.Request(server.rstrip("/") + path,
                                 data=json.dumps(data).encode() if data is not None else None,
                                 headers={"Content-Type": "application/json"} if data is not None else {})
    with urllib.request.urlopen(req, timeout=timeout) as r:
        body = r.read()
    return body if raw else json.loads(body)


def fill(node, values):
    """Remplace les marqueurs %…% du workflow (valeur entière ou texte)."""
    if isinstance(node, dict):
        return {k: fill(v, values) for k, v in node.items()}
    if isinstance(node, list):
        return [fill(v, values) for v in node]
    if isinstance(node, str):
        if node in values:
            return values[node]
        for k, v in values.items():
            if isinstance(v, str):
                node = node.replace(k, v)
    return node


def generate(server, workflow, values, timeout):
    client = str(uuid.uuid4())
    res = api(server, "/prompt", {"prompt": fill(workflow, values), "client_id": client})
    if res.get("node_errors"):
        raise RuntimeError(f"ComfyUI refuse le workflow : {json.dumps(res['node_errors'])[:500]}")
    pid = res["prompt_id"]
    start = time.time()
    while time.time() - start < timeout:
        hist = api(server, f"/history/{pid}")
        if pid in hist:
            entry = hist[pid]
            status = entry.get("status", {})
            if status.get("status_str") == "error":
                raise RuntimeError(f"erreur ComfyUI : {json.dumps(status.get('messages', []))[:500]}")
            for out in entry.get("outputs", {}).values():
                for im in out.get("images", []):
                    if im.get("type", "output") == "output":
                        q = urllib.parse.urlencode({"filename": im["filename"], "subfolder": im.get("subfolder", ""),
                                                    "type": "output"})
                        return api(server, f"/view?{q}", raw=True, timeout=120)
            if status.get("completed"):
                raise RuntimeError("ComfyUI a terminé sans renvoyer d'image (pas de nœud SaveImage ?)")
        time.sleep(1.5)
    raise TimeoutError(f"pas d'image après {timeout} s")


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("post", nargs="?")
    ap.add_argument("--server", default=os.environ.get("COMFY_URL", "http://127.0.0.1:8188"))
    ap.add_argument("--workflow", default=os.path.join(ROOT, "kit", "comfy", "z_image_turbo_api.json"))
    ap.add_argument("--checkpoint", default=os.environ.get("COMFY_CHECKPOINT", "z_image_turbo_bf16.safetensors"))
    ap.add_argument("--width", type=int, default=1344)
    ap.add_argument("--height", type=int, default=768)
    ap.add_argument("--only", help="numéros de slides, ex. 1,3,4")
    ap.add_argument("--force", action="store_true", help="régénérer même si l'image existe")
    ap.add_argument("--seed", type=int)
    ap.add_argument("--timeout", type=int, default=600)
    ap.add_argument("--checkpoints", action="store_true", help="lister les modèles installés (diffusion_models et checkpoints)")
    a = ap.parse_args()

    try:
        api(a.server, "/system_stats", timeout=10)
    except (urllib.error.URLError, OSError) as e:
        sys.exit(f"ComfyUI injoignable sur {a.server} ({e}). Lancez ComfyUI puis réessayez.")
    if a.checkpoints:
        for node, field in (("UNETLoader", "unet_name"), ("CheckpointLoaderSimple", "ckpt_name")):
            try:
                names = api(a.server, f"/object_info/{node}")[node]["input"]["required"][field][0]
            except Exception:
                continue
            print(f"{node} :")
            for name in names:
                print("  " + name)
        return
    if not a.post:
        ap.error("indiquez le fichier du post")

    spec = json.load(open(a.post, encoding="utf-8"))
    total = 2 + len(spec["slides"])
    items = [(1, spec["cover"])] + [(i + 2, s) for i, s in enumerate(spec["slides"])] + [(total, spec["cta"])]
    items = [(n, d["illustration"]) for n, d in items if d.get("illustration")]
    if a.only:
        keep = {int(x) for x in a.only.split(",")}
        items = [it for it in items if it[0] in keep]
    if not items:
        sys.exit("Aucun champ « illustration » à générer dans ce post.")

    workflow = json.load(open(a.workflow, encoding="utf-8"))
    out = os.path.join(ROOT, "illustrations", spec["slug"])
    os.makedirs(out, exist_ok=True)
    log_path = os.path.join(out, "prompts.json")
    log = json.load(open(log_path, encoding="utf-8")) if os.path.exists(log_path) else {}
    style = STYLE.format(palette=PALETTES[spec["pillar"]])
    failed = 0
    for n, scene in items:
        dest = os.path.join(out, f"{n:02d}.png")
        if os.path.exists(dest) and not a.force:
            print(f"{n:02d} : déjà présente (--force pour régénérer)")
            continue
        seed = a.seed if a.seed is not None else random.randint(1, 2**31 - 1)
        prompt = f"{scene}, {style}"
        values = {"%PROMPT%": prompt, "%NEGATIVE%": NEGATIVE, "%SEED%": seed, "%WIDTH%": a.width,
                  "%HEIGHT%": a.height, "%CHECKPOINT%": a.checkpoint}
        t = time.time()
        try:
            data = generate(a.server, workflow, values, a.timeout)
        except Exception as e:
            failed += 1
            print(f"{n:02d} : ÉCHEC — {e}")
            continue
        open(dest, "wb").write(data)
        log[f"{n:02d}"] = {"prompt": prompt, "negative": NEGATIVE, "seed": seed, "checkpoint": a.checkpoint,
                           "size": [a.width, a.height]}
        json.dump(log, open(log_path, "w", encoding="utf-8"), ensure_ascii=False, indent=2)
        print(f"{n:02d} : OK ({time.time() - t:.0f} s) → illustrations/{spec['slug']}/{n:02d}.png")
    if failed:
        sys.exit(f"{failed} illustration(s) en échec.")
    print("Illustrations prêtes. Lancez ensuite : python3 kit/generate.py " + a.post)


if __name__ == "__main__":
    main()
