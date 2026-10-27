#!/usr/bin/env python3
"""Génère les images d'un carrousel « Une Dose de Savoir » à partir d'un fichier JSON.

Usage :
    python3 kit/generate.py posts/2026-11-02-tardigrade.json

Produit medias/<slug>/01.png, 02.png, ... (1080×1350) et medias/<slug>/planche.jpg
(planche de contrôle). Signale tout texte qui déborde d'une slide.
Voir CLAUDE.md pour le format du fichier JSON.
"""
import html
import json
import os
import re
import subprocess
import sys

from playwright.sync_api import sync_playwright

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
KIT = os.path.join(ROOT, "kit")
NB = " "
W, H = 1080, 1350
HANDLE = "@unedosedesavoir"

# ---------------------------------------------------------------- piliers
# bg: fond · fg: texte · accent: chiffres clés et flèches · muted: texte secondaire
# wm: filigrane · card: cartes de la slide finale · badge/ink: pastille du logo
PILIERS = {
    "lundi":    dict(jour="LUNDI", label="ANIMAUX & NATURE", icon="leaf",
                     bg="#12392B", fg="#F1F7F2", accent="#8BE3A8", muted="#C6DCCD",
                     wm="#1D4C3A", card="#1A4635", badge="#8BE3A8", ink="#12392B"),
    "mardi":    dict(jour="MARDI", label="HISTOIRE INSOLITE", icon="temple",
                     bg="#EFE4CF", fg="#2A1E12", accent="#9C3D16", muted="#5C4630",
                     wm="#E2D0AF", card="#E6D6B8", badge="#9C3D16", ink="#EFE4CF"),
    "mercredi": dict(jour="MERCREDI", label="CORPS HUMAIN", icon="heart",
                     bg="#5B1424", fg="#FFF1F3", accent="#FF9AA8", muted="#F2C9D0",
                     wm="#701F33", card="#6B1D30", badge="#FF9AA8", ink="#5B1424"),
    "jeudi":    dict(jour="JEUDI", label="SCIENCES & ESPACE", icon="planet",
                     bg="#0B1430", fg="#EEF2FF", accent="#9DB8FF", muted="#C3CEEB",
                     wm="#18264F", card="#152146", badge="#9DB8FF", ink="#0B1430"),
    "vendredi": dict(jour="VENDREDI", label="MOTS & EXPRESSIONS", icon="bubble",
                     bg="#2D1B4E", fg="#F5EFFF", accent="#D2B2FF", muted="#D6C9EE",
                     wm="#3C2964", card="#392560", badge="#D2B2FF", ink="#2D1B4E"),
    "samedi":   dict(jour="SAMEDI", label="LE MONDE", icon="globe",
                     bg="#F3C343", fg="#1E1A10", accent="#1E1A10", muted="#4A3A12",
                     wm="#E3B12E", card="#E6B532", badge="#1E1A10", ink="#F3C343"),
    "dimanche": dict(jour="DIMANCHE", label="VRAI OU FAUX ?", icon="question",
                     bg="#161616", fg="#FFFFFF", accent="#FF5C4D", muted="#BDBDBD",
                     wm="#262626", card="#232323", badge="#FF5C4D", ink="#161616"),
}


def icon_svg(name, ink, cut, css):
    """Pictogramme du pilier (viewBox 48). ink = couleur principale, cut = détails."""
    body = {
        "leaf": f'<path d="M10 38C10 21 21 10 38 10c0 17-11 28-28 28z" fill="{ink}"/>'
                f'<path d="M13 35L29 19M20 28h7M24 24v-6" fill="none" stroke="{cut}" stroke-width="3" stroke-linecap="round"/>',
        "temple": f'<path d="M7 18.5L24 9l17 9.5z" fill="{ink}"/>'
                  f'<rect x="10" y="21" width="6" height="14" rx="1.5" fill="{ink}"/>'
                  f'<rect x="21" y="21" width="6" height="14" rx="1.5" fill="{ink}"/>'
                  f'<rect x="32" y="21" width="6" height="14" rx="1.5" fill="{ink}"/>'
                  f'<rect x="7" y="37" width="34" height="4.5" rx="2" fill="{ink}"/>'
                  f'<circle cx="24" cy="15" r="2" fill="{cut}"/>',
        "heart": f'<path d="M24 40S7 30.5 7 18.5A9 9 0 0 1 24 13a9 9 0 0 1 17 5.5C41 30.5 24 40 24 40z" fill="{ink}"/>'
                 f'<path d="M11 24h7l3-5 4 10 3-5h9" fill="none" stroke="{cut}" stroke-width="3" stroke-linecap="round" stroke-linejoin="round"/>',
        "planet": f'<ellipse cx="24" cy="24" rx="19" ry="6.5" transform="rotate(-22 24 24)" fill="none" stroke="{ink}" stroke-width="3.2"/>'
                  f'<circle cx="24" cy="24" r="11" fill="{ink}"/>'
                  f'<path d="M5 24a19 6.5 0 0 0 38 0" transform="rotate(-22 24 24)" fill="none" stroke="{cut}" stroke-width="7"/>'
                  f'<path d="M5 24a19 6.5 0 0 0 38 0" transform="rotate(-22 24 24)" fill="none" stroke="{ink}" stroke-width="3.2"/>'
                  f'<circle cx="39" cy="9" r="2.4" fill="{ink}"/>',
        "bubble": f'<path d="M11 9h26a5 5 0 0 1 5 5v15a5 5 0 0 1-5 5H23l-9 7v-7h-3a5 5 0 0 1-5-5V14a5 5 0 0 1 5-5z" fill="{ink}"/>'
                  f'<path d="M22 16l-5 5.5 5 5.5M31 16l-5 5.5 5 5.5" fill="none" stroke="{cut}" stroke-width="3.2" stroke-linecap="round" stroke-linejoin="round"/>',
        "globe": f'<circle cx="24" cy="24" r="16" fill="{ink}"/>'
                 f'<ellipse cx="24" cy="24" rx="7" ry="16" fill="none" stroke="{cut}" stroke-width="2.6"/>'
                 f'<path d="M8 24h32M10.5 16h27M10.5 32h27" fill="none" stroke="{cut}" stroke-width="2.6" stroke-linecap="round"/>',
        "question": f'<circle cx="24" cy="24" r="17" fill="none" stroke="{ink}" stroke-width="3.2"/>'
                    f'<path d="M19 18.6a5.2 5.2 0 1 1 7.2 4.8c-1.4.6-2.2 1.8-2.2 3.2v1.4" fill="none" stroke="{ink}" stroke-width="3.4" stroke-linecap="round"/>'
                    f'<circle cx="24" cy="33.6" r="2.1" fill="{ink}"/>',
    }[name]
    return f'<svg style="{css}" viewBox="0 0 48 48" aria-hidden="true">{body}</svg>'


# ---------------------------------------------------------------- typographie
UNITS = r"(°C|°F|°|km/h|km|mm|cm|m|kg|g|t|ans|an|mois|jours|jour|heures|h|min|s|millions|milliards|mille|%|€)"


def fr(text):
    """Échappe le texte et applique les espaces insécables de la typographie française."""
    t = html.escape(text or "", quote=False)
    t = re.sub(r" ([?!:;»%])", NB + r"\1", t)
    t = t.replace("« ", "«" + NB)
    t = re.sub(r"(\d) (?=\d{3}\b)", r"\1" + NB, t)
    t = re.sub(r"(\d) " + UNITS + r"(?![\w])", r"\1" + NB + r"\2", t)
    return t


# ---------------------------------------------------------------- gabarits
def page(p, inner, wm_size=560, wm_pos="right: -170px; bottom: -150px;"):
    wm = icon_svg(p["icon"], p["wm"], p["bg"], f"position: absolute; {wm_pos} width: {wm_size}px; height: {wm_size}px")
    return (f'<div id="root" style="width:{W}px;height:{H}px;box-sizing:border-box;padding:96px;background:{p["bg"]};'
            f'color:{p["fg"]};font-family:\'DM Sans\',sans-serif;display:flex;flex-direction:column;'
            f'justify-content:space-between;position:relative;overflow:hidden">{wm}{inner}</div>')


def header(p, left_label, counter, big=False):
    size, radius, isz, fs, ls = (96, 28, 66, 30, 5) if big else (72, 21, 50, 26, 4)
    badge = (f'<div style="width:{size}px;height:{size}px;border-radius:{radius}px;background:{p["badge"]};display:flex;'
             f'align-items:center;justify-content:center;flex-shrink:0">'
             + icon_svg(p["icon"], p["ink"], p["badge"], f"width:{isz}px;height:{isz}px") + "</div>")
    return (f'<div class="zone" style="display:flex;justify-content:space-between;align-items:center;position:relative">'
            f'<div style="display:flex;align-items:center;gap:{20 if big else 18}px;color:{p["accent"]}">{badge}'
            f'<span style="font-size:{fs}px;font-weight:700;letter-spacing:{ls}px">{html.escape(left_label)}</span></div>'
            f'<span style="font-size:30px;font-weight:500;color:{p["muted"]}">{counter}</span></div>')


def footer(p, pill=None):
    right = (f'<span style="font-size:36px;font-weight:700;padding:20px 40px;border-radius:999px;background:{p["badge"]};'
             f'color:{p["ink"]}">{fr(pill)}</span>' if pill
             else f'<span style="font-size:40px;font-weight:700;color:{p["accent"]}">→</span>')
    return (f'<div class="zone" style="display:flex;justify-content:space-between;align-items:center;position:relative">'
            f'<span style="font-size:32px;font-weight:500;color:{p["muted"]}">{HANDLE}</span>{right}</div>')


def cover(p, c, n, total, pilier):
    extra = ""
    if pilier == "dimanche":
        extra = (f'<div style="display:flex;gap:24px">'
                 f'<span style="font-size:40px;font-weight:700;padding:18px 44px;border-radius:999px;border:4px solid {p["fg"]}">VRAI</span>'
                 f'<span style="font-size:40px;font-weight:700;padding:18px 44px;border-radius:999px;border:4px solid {p["accent"]};'
                 f'color:{p["accent"]}">FAUX</span></div>')
    sub = (f'<p style="margin:0;font-size:44px;line-height:1.35;color:{p["muted"]};max-width:820px">{fr(c["subtitle"])}</p>'
           if c.get("subtitle") else "")
    inner = (header(p, f'{p["jour"]} · {p["label"]}', f"{n} / {total}", big=True)
             + f'<div class="zone" style="display:flex;flex-direction:column;gap:40px;position:relative">'
               f'<h1 style="margin:0;font-family:\'Bricolage Grotesque\',sans-serif;font-size:{c.get("size", 116)}px;'
               f'font-weight:800;line-height:1;letter-spacing:-2px">{fr(c["title"])}</h1>' + sub + extra + "</div>"
             + footer(p, pill=c.get("pill", "La réponse →" if pilier == "dimanche" else "Glissez →")))
    return page(p, inner, wm_size=760, wm_pos="right: -180px; bottom: -150px;")


def fact(p, s, n, total):
    big = (f'<span style="font-family:\'Bricolage Grotesque\',sans-serif;font-size:{s.get("big_size", 160)}px;font-weight:800;'
           f'line-height:0.9;letter-spacing:-4px;color:{p["accent"]}">{fr(s["big"])}</span>') if s.get("big") else ""
    p1 = f'<p style="margin:0;font-size:42px;line-height:1.4;color:{p["muted"]}">{fr(s["p1"])}</p>' if s.get("p1") else ""
    p2 = f'<p style="margin:0;font-size:42px;line-height:1.4;font-weight:500">{fr(s["p2"])}</p>' if s.get("p2") else ""
    inner = (header(p, p["label"], f"{n} / {total}")
             + f'<div class="zone" style="display:flex;flex-direction:column;gap:32px;position:relative">{big}'
               f'<h2 style="margin:0;font-family:\'Bricolage Grotesque\',sans-serif;font-size:{s.get("title_size", 84)}px;'
               f'font-weight:800;line-height:1.02;letter-spacing:-2px">{fr(s["title"])}</h2>' + p1 + p2 + "</div>"
             + footer(p))
    return page(p, inner)


DEFAULT_CTA = ["Enregistrez ce post pour le relire", "Envoyez-le à un ami curieux",
               "Abonnez-vous pour votre dose quotidienne"]


def cta(p, c, n, total):
    items = "".join(
        f'<div style="display:flex;align-items:center;gap:28px;padding:30px 40px;border-radius:28px;background:{p["card"]}">'
        f'<span style="font-family:\'Bricolage Grotesque\',sans-serif;font-size:52px;font-weight:800;color:{p["accent"]}">{i}</span>'
        f'<span style="font-size:38px;font-weight:500">{fr(t)}</span></div>'
        for i, t in enumerate(c.get("items", DEFAULT_CTA), 1))
    inner = (header(p, "À VOUS", f"{n} / {total}")
             + f'<div class="zone" style="display:flex;flex-direction:column;gap:36px;position:relative">'
               f'<h2 style="margin:0;font-family:\'Bricolage Grotesque\',sans-serif;font-size:{c.get("size", 88)}px;'
               f'font-weight:800;line-height:1.02;letter-spacing:-2px">{fr(c["title"])}</h2>'
               f'<p style="margin:0;font-size:42px;line-height:1.4;color:{p["muted"]}">{fr(c.get("text", ""))}</p>'
               f'<div style="display:flex;flex-direction:column;gap:22px">{items}</div></div>'
             + f'<div class="zone" style="display:flex;position:relative"><span style="font-size:36px;font-weight:700;'
               f'padding:20px 40px;border-radius:999px;background:{p["badge"]};color:{p["ink"]}">{HANDLE}</span></div>')
    return page(p, inner)


FONT_CSS = f"""<style>
@font-face{{font-family:'Bricolage Grotesque';src:url('file://{KIT}/fonts/BricolageGrotesque.ttf');font-weight:200 800;}}
@font-face{{font-family:'DM Sans';src:url('file://{KIT}/fonts/DMSans.ttf');font-weight:100 1000;}}
body{{margin:0}}
</style>"""

CHECK_JS = """() => {
  const z = [...document.querySelectorAll('#root > .zone')].map(e => e.getBoundingClientRect());
  const bad = [];
  if (z.length === 3) {
    if (z[1].top < z[0].bottom + 24) bad.push("le texte touche l'en-tête");
    if (z[2].top < z[1].bottom + 24) bad.push('le texte touche le pied de page');
  }
  for (const el of document.querySelectorAll('#root .zone *')) {
    const b = el.getBoundingClientRect();
    if (b.width && (b.bottom > 1350 - 60 || b.right > 1080 - 60)) { bad.push('sort du cadre : ' + (el.textContent || '').slice(0, 40)); break; }
  }
  return bad;
}"""


def main(spec_path):
    spec = json.load(open(spec_path, encoding="utf-8"))
    pilier = spec["pillar"]
    p = PILIERS[pilier]
    slides = spec["slides"]
    total = 2 + len(slides)
    pages = [cover(p, spec["cover"], 1, total, pilier)]
    pages += [fact(p, s, i + 2, total) for i, s in enumerate(slides)]
    pages.append(cta(p, spec["cta"], total, total))

    out = os.path.join(ROOT, "medias", spec["slug"])
    os.makedirs(out, exist_ok=True)
    for f in os.listdir(out):
        if f.endswith(".png") or f == "planche.jpg":
            os.remove(os.path.join(out, f))
    tmp = os.path.join(out, "_render.html")
    problems = []
    with sync_playwright() as pw:
        b = pw.chromium.launch()
        pg = b.new_page(viewport={"width": W, "height": H})
        for i, body in enumerate(pages, 1):
            open(tmp, "w", encoding="utf-8").write(
                f'<!doctype html><html lang="fr"><head><meta charset="utf-8">{FONT_CSS}</head><body>{body}</body></html>')
            pg.goto("file://" + tmp)
            pg.evaluate("document.fonts.ready")
            if pg.evaluate("[...document.fonts].filter(f => f.status == 'loaded').length") < 2:
                problems.append(f"slide {i} : polices non chargées")
            for msg in pg.evaluate(CHECK_JS):
                problems.append(f"slide {i} : {msg}")
            pg.screenshot(path=os.path.join(out, f"{i:02d}.png"), clip={"x": 0, "y": 0, "width": W, "height": H})
        b.close()
    os.remove(tmp)
    pngs = [os.path.join(out, f"{i:02d}.png") for i in range(1, total + 1)]
    subprocess.run(["convert", *pngs, "-resize", "360x450", "+append", os.path.join(out, "planche.jpg")], check=True)
    with open(os.path.join(out, "post.json"), "w", encoding="utf-8") as f:
        json.dump(spec, f, ensure_ascii=False, indent=2)
    print(f"{total} images → medias/{spec['slug']}/")
    if problems:
        print("ATTENTION :")
        for x in problems:
            print("  -", x)
        sys.exit(2)
    print("Contrôle OK : polices chargées, aucun débordement détecté.")


if __name__ == "__main__":
    main(sys.argv[1])
