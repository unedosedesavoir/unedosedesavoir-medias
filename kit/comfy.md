# Illustrations avec ComfyUI (PC de la personne)

Les illustrations sont générées par **ComfyUI Desktop** installé sur le PC Windows de la personne
(modèle Z-Image Turbo, carte RTX 3060 6 Go : environ 45 s par image). L'espace de travail cloud ne
peut pas joindre ce PC directement : on passe par le **navigateur intégré de l'application Claude**
(outils `Claude_Browser__*`), qui tourne sur le PC et voit donc `http://127.0.0.1:8188`.

Prérequis : PC allumé, application Claude ouverte et liée à la session, ComfyUI Desktop lancé.
Sinon, le dire à la personne et garder les carrousels sans illustration (le gabarit sans `image`
fonctionne toujours).

## Style (choisi par la personne le 2 novembre 2026)

Vectoriel plat éditorial, formes géométriques simples, grain léger, palette du pilier.
Le gabarit de prompt et les palettes sont dans `kit/illustrations.py`. Jamais photoréaliste,
jamais de personnage, logo ou œuvre protégés, pas de portrait d'une personne réelle identifiable
(dessiner l'objet, le lieu ou une silhouette générique à la place), pas de texte dans l'image.

## Étapes

1. **Décrire les scènes** : dans `posts/<slug>.json`, ajouter `"scene"` (en anglais, concret,
   une seule idée visuelle) à `cover` et à chaque slide. Puis :
   `python3 kit/illustrations.py posts/<slug>.json` → ajoute `"image"` et écrit
   `images/<slug>/prompts.json`.
2. **Pousser** (`git add -A && git commit && git push`), noter le hash court du commit : le navigateur
   du PC lit les prompts sur `raw.githubusercontent.com` à ce commit.
3. **Ouvrir ComfyUI** dans le navigateur intégré : `preview_start` sur
   `http://127.0.0.1:8188/system_stats` (si l'accès est refusé : `request_access`, puis réessayer).
4. **Mettre en file d'attente** avec `javascript_tool` (remplacer COMMIT et la liste des slugs) :

```js
const wf = (prompt, prefix, seed, w, h) => ({
 "1":{"class_type":"UNETLoader","inputs":{"unet_name":"z_image_turbo_bf16.safetensors","weight_dtype":"default"}},
 "2":{"class_type":"CLIPLoader","inputs":{"clip_name":"qwen_3_4b.safetensors","type":"lumina2"}},
 "3":{"class_type":"VAELoader","inputs":{"vae_name":"ae.safetensors"}},
 "4":{"class_type":"ModelSamplingAuraFlow","inputs":{"model":["1",0],"shift":3}},
 "5":{"class_type":"CLIPTextEncode","inputs":{"clip":["2",0],"text":prompt}},
 "6":{"class_type":"CLIPTextEncode","inputs":{"clip":["2",0],"text":""}},
 "7":{"class_type":"EmptySD3LatentImage","inputs":{"width":w,"height":h,"batch_size":1}},
 "8":{"class_type":"KSampler","inputs":{"model":["4",0],"positive":["5",0],"negative":["6",0],"latent_image":["7",0],
      "seed":seed,"steps":8,"cfg":1,"sampler_name":"res_multistep","scheduler":"simple","denoise":1}},
 "9":{"class_type":"VAEDecode","inputs":{"samples":["8",0],"vae":["3",0]}},
 "10":{"class_type":"SaveImage","inputs":{"images":["9",0],"filename_prefix":prefix}}});
const base = "https://raw.githubusercontent.com/unedosedesavoir/unedosedesavoir-medias/COMMIT/images/";
const out = [];
for (const s of ["2026-11-09-exemple"]) {
  const d = await (await fetch(base + s + "/prompts.json")).json();
  for (const j of d.jobs) {
    const r = await fetch('/prompt', {method:'POST', headers:{'Content-Type':'application/json'},
      body: JSON.stringify({prompt: wf(j.prompt, 'unedosedesavoir/' + s + '/' + j.file.replace('.png',''), j.seed, j.width, j.height)})});
    out.push(j.file + ' ' + JSON.stringify((await r.json()).node_errors || {}));
  }
}
out
```

5. **Attendre** : interroger `/queue` toutes les 5 s, en revenant avant 40 s (limite de l'outil),
   jusqu'à `queue_running` et `queue_pending` vides.
6. **Récupérer** : les fichiers sont dans
   `C:\Users\steev\AppData\Local\Comfy-Desktop\ComfyUI-Shared\output\unedosedesavoir\<slug>\`
   sous la forme `<nom>_00001_.png` (dossier déjà autorisé ; sinon `device_request_folder_access`
   sur `...\output\unedosedesavoir`). `device_stage_files` les copie dans
   `/mnt/user-data/uploads/unedosedesavoir/<slug>/` ; puis `python3 kit/import_images.py <slug>`
   les range en `images/<slug>/<nom>.png` (dernière version de chaque image, cadre uni retiré).
7. **Vérifier chaque illustration** (lecture d'image) : le sujet est-il juste et reconnaissable
   (nombre de pattes, forme d'une planète, époque…) ? Pas de texte parasite, pas de visage réaliste ?
   Sinon, corriger la `scene` ou ajouter `"seed": <autre nombre>` dans le bloc, relancer
   `illustrations.py` et régénérer seulement cette image.
8. **Cadrage** : si le sujet est coupé sur la slide, ajouter `"image_pos": "30%"` (0 % = haut de
   l'image, 100 % = bas) dans le bloc concerné, puis relancer `generate.py`.
