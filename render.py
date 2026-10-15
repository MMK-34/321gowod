"""Render a week of WODs to Instagram-ready PNGs + captions.

Usage:  python render.py wods/week01.json
Output: out/<week>/<date>_<n>.png, out/<week>/captions.md, out/<week>/grid.png
        posts/<date>/<n>.jpg + caption.txt  (what publish.py posts)
Also appends every rendered WOD to history.json (used to avoid repeats).
"""
import json, subprocess, sys
from PIL import Image
from pathlib import Path

ROOT = Path(__file__).resolve().parent
CHROME = r"C:\Program Files\Google\Chrome\Application\chrome.exe"
W, H = 1080, 1350


def shoot(html_path: Path, png_path: Path):
    subprocess.run([
        CHROME, "--headless=new", "--disable-gpu", "--hide-scrollbars",
        "--force-device-scale-factor=1", f"--window-size={W},{H}",
        "--virtual-time-budget=15000", f"--screenshot={png_path}", html_path.as_uri(),
    ], check=True, capture_output=True)


def web_photo(name):
    """Downscaled copy of a library photo (originals are 5-15 MB) for fast rendering."""
    from PIL import Image
    src = ROOT / "library" / "photos" / f"{name}.jpg"
    dst = ROOT / "library" / "photos" / "_web" / f"{name}.jpg"
    if not dst.exists():
        dst.parent.mkdir(exist_ok=True)
        im = Image.open(src).convert("RGB")
        im.thumbnail((2000, 2000), Image.LANCZOS)
        im.save(dst, quality=88)
    return dst


def caption(w, brand):
    rule = "━━━━━━━━━━━━"
    lines = [w["hook"], ""]
    if w.get("story"):
        lines += [w["story"], ""]
    lines += [rule, f"{w['title'].upper()} · {w['hero']}", w["scheme"]]
    lines += [f"▪️ {m['reps']} {m['name']}" + (f" ({m['load']})" if m.get("load") else "") for m in w["movements"]]
    lines += [rule, "", f"⚖️ Scaled: {w['scaled_short']}", f"🏠 No gear: {w['nogear_short']}",
              f"🎯 Target: {w['target']}"]
    if w.get("tip"):
        lines += ["", f"💡 Coach tip: {w['tip']}"]
    lines += [""]
    if w.get("question"):
        lines += [f"{w['question']} 👇"]
    lines += [w.get("cta", "Save it for your next session 📌 Tag your training partner.")]
    if brand.get("promo"):
        lines += [brand["promo"]]
    lines += ["",
              f"{brand['types'][w['type']].get('tags', '')} {brand['hashtags']}".strip()]
    return "\n".join(lines)


def main(week_file):
    week_path = ROOT / week_file
    week = json.loads(week_path.read_text(encoding="utf-8"))
    brand = json.loads((ROOT / "brand.json").read_text(encoding="utf-8"))
    template = (ROOT / "template.html").read_text(encoding="utf-8")
    library = json.loads((ROOT / "library" / "library.json").read_text(encoding="utf-8"))["photos"]
    out = ROOT / "out" / week_path.stem
    tmp = out / "_html"
    tmp.mkdir(parents=True, exist_ok=True)

    md, covers = [f"# {week_path.stem} captions\n"], []
    for w in week["wods"]:
        n_slides = 3 if w["format"] == "carousel" else 1
        files = []
        photo = "null"
        if w.get("photo"):
            photo = json.dumps({"src": web_photo(w["photo"]).as_uri(), "focus": library[w["photo"]]["focus"]})
        for s in range(1, n_slides + 1):
            inject = (f"<script>window.WOD={json.dumps(w, ensure_ascii=False)};"
                      f"window.BRAND={json.dumps(brand, ensure_ascii=False)};window.SLIDE={s};window.PHOTO={photo};</script>")
            html = tmp / f"{w['date']}_{s}.html"
            html.write_text(template.replace("<body>", "<body>" + inject, 1), encoding="utf-8")
            png = out / f"{w['date']}_{s}.png"
            shoot(html, png)
            files.append(png.name)
            post_dir = ROOT / "posts" / w["date"]
            post_dir.mkdir(parents=True, exist_ok=True)
            Image.open(png).convert("RGB").save(post_dir / f"{s}.jpg", quality=92)
        (ROOT / "posts" / w["date"] / "caption.txt").write_text(caption(w, brand), encoding="utf-8")
        covers.append(out / files[0])
        md += [f"## Day {w['day']:03d} · {w['date']} · {w['title']} ({w['format']})",
               "Files: " + ", ".join(files), "", "```", caption(w, brand), "```", ""]
        print("ok", w["date"], w["title"], files)
    (out / "captions.md").write_text("\n".join(md), encoding="utf-8")

    hist_path = ROOT / "history.json"
    hist = json.loads(hist_path.read_text(encoding="utf-8")) if hist_path.exists() else []
    seen = {h["date"] for h in hist}
    hist += [{"date": w["date"], "day": w["day"], "title": w["title"], "type": w["type"],
              "movements": [m["name"] for m in w["movements"]]} for w in week["wods"] if w["date"] not in seen]
    hist_path.write_text(json.dumps(hist, ensure_ascii=False, indent=1), encoding="utf-8")

    grid(covers, out / "grid.png")


def grid(covers, dest):
    """Profile-grid preview: newest first, 3 columns like Instagram."""
    from PIL import Image
    tw, th, gap = 360, 450, 4
    covers = list(reversed(covers))
    rows = (len(covers) + 2) // 3
    sheet = Image.new("RGB", (tw * 3 + gap * 2, th * rows + gap * (rows - 1)), "white")
    for i, p in enumerate(covers):
        im = Image.open(p).convert("RGB").resize((tw, th), Image.LANCZOS)
        sheet.paste(im, ((i % 3) * (tw + gap), (i // 3) * (th + gap)))
    sheet.save(dest)


if __name__ == "__main__":
    main(sys.argv[1] if len(sys.argv) > 1 else "wods/week01.json")
