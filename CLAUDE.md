# Une Dose de Savoir — procédure de production

Compte de culture générale (Instagram @unedosedesavoir, TikTok « Une Dose de Savoir »).
Un carrousel par jour, un pilier fixe par jour de la semaine. Langue : français, vouvoiement.

Ce dépôt est public : il sert d'hébergement aux images (Metricool les télécharge par leur lien brut).
N'y mettez jamais de mot de passe, de clé, ni de donnée personnelle.

## Les 7 piliers et les horaires (heure de La Réunion, `Indian/Reunion`)

| Jour | `pillar` | Thème | Instagram | TikTok |
|---|---|---|---|---|
| Lundi | `lundi` | Animaux et nature | 10:00 | 18:00 |
| Mardi | `mardi` | Histoire insolite | 10:00 | 18:00 |
| Mercredi | `mercredi` | Corps humain | 10:00 | 18:00 |
| Jeudi | `jeudi` | Sciences et espace | 10:00 | 18:00 |
| Vendredi | `vendredi` | Origine des mots et expressions | 10:00 | 18:00 |
| Samedi | `samedi` | Le monde (glisser La Réunion régulièrement) | 10:00 | 10:00 |
| Dimanche | `dimanche` | Vrai ou faux (une idée reçue démontée) | 10:00 | 10:00 |

Horaires issus des moyennes Metricool (pas encore d'historique propre au compte) : à réévaluer
avec `getBestTimeToPostByNetwork` une fois quelques semaines de publications passées.

## Fichiers

- `kit/generate.py` : génère les images d'un post à partir d'un fichier JSON (couleurs, logos,
  polices, typographie française et contrôle des débordements sont gérés par le script).
- `kit/fonts/` : Bricolage Grotesque (titres) et DM Sans (texte), licence OFL.
- `kit/logo/` : photo de profil (roue des 7 savoirs).
- `kit/illustrations.py` + `kit/comfy.md` : illustrations générées avec ComfyUI sur le PC de la
  personne (style vectoriel plat, palette du pilier). Lire `kit/comfy.md` avant de les générer.
- `images/AAAA-MM-JJ-sujet/` : illustrations du post (`01-couverture.png`, `02.png`…) et `prompts.json`.
- `posts/AAAA-MM-JJ-sujet.json` : contenu de chaque post (source de vérité).
- `medias/AAAA-MM-JJ-sujet/` : images générées `01.png` … `NN.png`, `planche.jpg`, `post.json`.
- `SUJETS.md` : réserve de sujets par pilier, et historique de ce qui a été programmé.

## Format d'un post (`posts/AAAA-MM-JJ-sujet.json`)

```json
{
  "pillar": "lundi",
  "slug": "2026-11-02-tardigrade",
  "date": "2026-11-02",
  "cover": {"title": "Titre accrocheur (≤ 60 caractères)", "subtitle": "Promesse courte (≤ 55 caractères)",
            "scene": "a cute tardigrade standing on green moss (scène à dessiner, en anglais)"},
  "slides": [
    {"big": "1 mm", "title": "Titre du fait (≤ 45 car.)", "p1": "Explication (≤ 120 car.)", "p2": "Chute ou détail fort (≤ 120 car.)",
     "scene": "a tiny tardigrade on a drop of water under a magnifying glass"}
  ],
  "cta": {"title": "Question ouverte au public", "text": "Invitation à commenter"},
  "caption": "Légende Instagram/TikTok (3 lignes, 1 à 3 émojis maximum)",
  "hashtags": ["culturegenerale", "lesaviezvous", "..."],
  "tiktok_title": "Titre TikTok (≤ 90 caractères)",
  "sources": ["https://… (au moins deux pages fiables réellement ouvertes)"]
}
```

- 4 ou 5 slides de faits (donc 6 ou 7 images au total). `big` = un chiffre, une date ou un mot court.
- Dimanche : la couverture affiche l'idée reçue entre guillemets (« … ») ; la 1re slide de fait
  donne le verdict (`"big": "FAUX"` ou `"VRAI"`), les suivantes l'expliquent.
- Champs optionnels de réglage si un texte est trop long : `cover.size` (défaut 116),
  `slides[].title_size` (défaut 84), `slides[].big_size` (défaut 160), `cta.size` (défaut 88).
- `scene` : ce que montre l'illustration de la slide (une idée visuelle concrète, en anglais).
  `kit/illustrations.py` ajoute ensuite `image` (nom du fichier dans `images/<slug>/`). Optionnel :
  `image_pos` (cadrage vertical, ex. `"30%"`), `seed` (pour obtenir une autre version de l'image).
  Avec illustration, le texte d'une slide de fait doit rester court (le script le contrôle).
- Écrire les espaces normalement : le script ajoute les espaces insécables (« », ? ! : %, unités).

## Procédure hebdomadaire (lundi → dimanche)

Chaque vendredi, on prépare la semaine qui commence le **deuxième lundi** suivant (le vendredi
6 novembre 2026 → semaine du 16 novembre), ce qui laisse une semaine d'avance pour relire.
Le nom des fichiers suit la date de publication ; pour les posts du 9 au 15 novembre 2026,
le champ `date` fait foi.

1. **Mettre à jour** : `git pull`. Lire `SUJETS.md` pour éviter les doublons.
2. **Choisir 7 sujets**, un par pilier, dans la réserve ou en en proposant de nouveaux ; varier les
   angles, éviter un sujet déjà programmé. Les sujets surprenants, concrets et chiffrés marchent le mieux.
3. **Vérifier les faits** : pour chaque post, ouvrir au moins deux sources fiables (encyclopédies,
   institutions, médias scientifiques). Ne garder que ce qui est confirmé ; formuler avec prudence
   (« environ », « la plupart », « sans doute ») quand les sources divergent. Pas de chiffres inventés.
   Pour les origines d'expressions, présenter les hypothèses comme des hypothèses.
4. **Écrire** `posts/<date>-<sujet>.json` pour chaque jour, avec une `scene` par slide.
4 bis. **Illustrer** (voir `kit/comfy.md`) : `python3 kit/illustrations.py posts/<fichier>.json`,
   pousser, générer les images dans ComfyUI via le navigateur intégré du PC, les récupérer dans
   `images/<slug>/` et vérifier chacune (sujet juste, pas de texte, pas de visage réaliste).
   Si le PC ou ComfyUI ne répond pas : retirer les champs `image`, produire les carrousels sans
   illustration et le signaler dans le récapitulatif.
5. **Générer** : `python3 kit/generate.py posts/<fichier>.json`. Le script doit finir par
   « Contrôle OK ». Sinon, raccourcir le texte ou réduire une taille, puis relancer.
6. **Regarder** chaque `medias/<slug>/planche.jpg` (lecture d'image) : lisibilité, coupures, cohérence.
7. **Publier les images** : `git add -A && git commit -m "Semaine du …" && git push`.
   Liens bruts à donner à Metricool, avec le hash complet du commit (`git rev-parse HEAD`) plutôt que
   `main`, pour éviter qu'une ancienne version en cache soit téléchargée quand une image est refaite :
   `https://raw.githubusercontent.com/unedosedesavoir/unedosedesavoir-medias/<hash>/medias/<slug>/01.png`
   (l'espace de travail ne peut pas ouvrir raw.githubusercontent.com : vérifier plutôt la présence des
   fichiers avec `gh api repos/unedosedesavoir/unedosedesavoir-medias/contents/medias/<slug>`. Metricool
   confirme le téléchargement en renvoyant des liens `static.metricool.com` dans sa réponse.)
8. **Programmer dans Metricool** (`blogId` 7394064, fuseau `Indian/Reunion`) : pour chaque post, DEUX
   publications (une Instagram, une TikTok), car les horaires diffèrent. Voir le modèle ci-dessous.
   Publication automatique : `"draft": false` pour tout post daté du 2026-11-09 ou après.
9. **Mettre à jour** `SUJETS.md` (historique), committer et pousser.
10. **Récapituler** pour la personne : un tableau jour / sujet / horaires / lien vers la planche, les
    sources principales, et tout point d'attention. Rappeler que les posts partiront seuls aux heures
    prévues, et qu'elle peut les modifier ou les supprimer dans Metricool d'ici là.

## Modèle Metricool (`createScheduledPost`)

- `media` : les liens bruts des images, dans l'ordre (01.png, 02.png, …).
- `text` : `caption` + ligne vide + les hashtags préfixés de `#`.
- Instagram : `providers` `[{"network":"instagram"}]`, `instagramData` `{"type":"POST", "isAiGenerated": true}`
  (déclaration obligatoire dès que le carrousel contient des illustrations générées par IA).
- TikTok : `providers` `[{"network":"tiktok"}]`, `tiktokData`
  `{"title": tiktok_title, "privacyOption":"PUBLIC_TO_EVERYONE", "autoAddMusic": true, "photoCoverIndex": 0}`.
- `publicationDate` : `{"dateTime":"AAAA-MM-JJTHH:MM:SS","timezone":"Indian/Reunion"}`, `autoPublish` true,
  `draft` false (publication automatique), `descendants` [], `firstCommentText` "", `smartLinkData` {"ids":[]}.

## Règles

- Mode actuel : **publication automatique** (`draft: false`) à partir des posts du lundi 9 novembre 2026,
  à la demande de la personne (2 novembre 2026). Les posts antérieurs restent des brouillons à valider.
  Revenir aux brouillons (`draft: true`) si la personne le demande, ou pour un post dont un fait ou une
  illustration reste douteux (et le signaler dans le récapitulatif).
- Jamais de personnage, logo ou œuvre protégés. Illustrations générées : uniquement en style
  vectoriel plat, jamais photoréalistes, pas de portrait d'une personne réelle, pas de texte dans l'image.
  Une illustration fausse ou trompeuse sur le sujet est régénérée, pas publiée.
- Ton : curieux, bienveillant, précis. Pas de sensationnalisme ni de sujets choquants ou politiques.
- En cas de doute sérieux sur un fait, remplacer le sujet plutôt que publier une approximation.
