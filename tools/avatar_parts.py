"""アバターのパーツ画像（GPT などで作ったもの）を、アバター工房で使える形に変換します。

    pip install pillow
    python tools/avatar_parts.py              # avatar_raw/ → assets/avatar/（位置合わせ＋WebP変換＋一覧作成）
    python tools/avatar_parts.py --template   # GPT に添付する素体テンプレート画像を docs/ に作り直す

やること:
  1. 背景が透明でない画像は、四隅から背景色を塗りつぶして透明にします。
  2. パーツの「描かれている範囲」を見つけ、レイヤーごとに決めた位置・大きさに自動で合わせます
     （GPT の出力は毎回少しずつ位置や大きさがずれるため）。
  3. 512×512 の WebP にして assets/avatar/ に保存し、manifest.json（パーツ一覧）を更新します。
  4. 全パーツを素体に重ねた確認用の一覧画像 avatar_raw/_preview.png を作ります。

ファイル名: avatar_raw/<レイヤー>_<番号など>.png
  レイヤー = kind（人外の頭）, bg, body, face, eyes, mouth, hair, head, glasses
  お化け・精霊など体まで一体の人外は kind_ghost_01 / kind_spirit_01 のように名前を付けます
  例: hair_01.png, eyes_sly.png

位置がずれたパーツは avatar_raw/adjust.json で微調整できます:
  {
    "hair_05": {"scale": 1.1, "dx": -20, "dy": 15},   # 拡大率と移動量（1024 基準のピクセル）
    "head_02": {"mode": "keep"}                         # 自動の位置合わせをせず、元画像の位置のまま使う
  }
"""
import argparse
import json
import re
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont

ROOT = Path(__file__).resolve().parent.parent
S = 1024  # 作業用キャンバス

# avatar.js の内蔵パーツと同じ位置（100 単位 × 10.24）
# mode: cover=全面 / width=幅をそろえる / box=箱に収める
SPEC = {
    "bg":      {"mode": "cover"},
    # 人外の頭（耳を含む）。お化け・精霊のように体まで一体のものは kind_full を使う
    # あごの下端を服のえりもとに合わせる（首のすき間ができないように）
    "kind":    {"mode": "width", "w": 480, "cx": 512, "bottom": 780},
    "kind_full": {"mode": "box", "w": 600, "h": 860, "cx": 512, "cy": 560},
    "body":    {"mode": "width", "w": 860, "cx": 512, "bottom": 1024},
    "face":    {"mode": "width", "w": 440, "cx": 512, "top": 190},
    "eyes":    {"mode": "box", "w": 240, "h": 110, "cx": 512, "cy": 420},
    "mouth":   {"mode": "box", "w": 120, "h": 70, "cx": 512, "cy": 560},
    "hair":    {"mode": "width", "w": 460, "cx": 512, "top": 145},
    "head":    {"mode": "width", "w": 480, "cx": 512, "bottom": 335},
    "glasses": {"mode": "box", "w": 360, "h": 110, "cx": 512, "cy": 440},
}
# 人外の頭（あごを 780 にそろえたとき）で、目・口を置く高さの目安。頭ごとの値は adjust.json の eyes / mouth / hat
KIND_EYES, KIND_MOUTH = 577, 690
ORDER = ["bg", "body", "kind", "face", "eyes", "mouth", "hair", "glasses", "head"]
NAME_RE = re.compile(r"^(kind|bg|body|face|eyes|mouth|hair|head|glasses)_[A-Za-z0-9_-]+$")
FULL_RE = re.compile(r"^kind_(ghost|spirit|obake|seirei|full)")  # 体まで一体の人外


# ---------------------------------------------------------------- 素体
def draw_mannequin(d: ImageDraw.ImageDraw, fill=(150, 150, 150), line=(90, 90, 90)):
    def bez(p0, p1, p2, p3, n=24):
        return [(((1 - t) ** 3) * p0[0] + 3 * ((1 - t) ** 2) * t * p1[0] + 3 * (1 - t) * t * t * p2[0] + t ** 3 * p3[0],
                 ((1 - t) ** 3) * p0[1] + 3 * ((1 - t) ** 2) * t * p1[1] + 3 * (1 - t) * t * t * p2[1] + t ** 3 * p3[1])
                for t in [i / n for i in range(n + 1)]]
    k = 10.24
    P = lambda x, y: (x * k, y * k)
    shoulders = bez(P(8, 100), P(8, 82), P(22, 71.5), P(40, 69)) + [P(60, 69)] + bez(P(60, 69), P(78, 71.5), P(92, 82), P(92, 100))
    d.polygon(shoulders, fill=fill, outline=line, width=6)
    d.polygon([P(44, 55), P(44, 70), P(50, 72), P(56, 70), P(56, 55)], fill=tuple(int(c * .92) for c in fill), outline=line, width=6)
    for cx in (32.2, 67.8):
        d.ellipse([P(cx - 3.7, 43.9 - 3.7), P(cx + 3.7, 43.9 + 3.7)], fill=fill, outline=line, width=6)
    d.ellipse([P(50 - 17.1, 41 - 22.5), P(50 + 17.1, 41 + 22.5)], fill=fill, outline=line, width=6)


def rel(p: Path) -> str:
    try:
        return str(p.relative_to(ROOT))
    except ValueError:
        return str(p)


def font(size):
    for f in ["/usr/share/fonts/opentype/noto/NotoSansCJK-Bold.ttc", "/System/Library/Fonts/ヒラギノ角ゴシック W6.ttc",
              "C:/Windows/Fonts/meiryob.ttc", "C:/Windows/Fonts/YuGothB.ttc"]:
        try:
            return ImageFont.truetype(f, size)
        except OSError:
            continue
    return None


def make_templates():
    out = ROOT / "docs"
    out.mkdir(exist_ok=True)
    im = Image.new("RGB", (S, S), (236, 236, 236))
    draw_mannequin(ImageDraw.Draw(im))
    im.save(out / "avatar_template.png")

    g = im.copy()
    d = ImageDraw.Draw(g)
    f = font(26)
    colors = {"hair": (214, 120, 40), "head": (190, 60, 140), "face": (40, 120, 200), "eyes": (30, 150, 90),
              "mouth": (200, 60, 60), "glasses": (110, 80, 200), "body": (60, 60, 60)}
    labels = {k: v for k, v in {
        "hair": "髪（幅{w}・上端{top}）", "head": "帽子（幅{w}・下端{bottom}）", "face": "顔（耳込み幅{w}・上端{top}）",
        "eyes": "目と眉（{w}×{h}）", "mouth": "口（{w}×{h}）", "glasses": "眼鏡（{w}×{h}）→", "body": "服（幅{w}・下端{bottom}）"}.items()}
    labels = {k: v.format(**SPEC[k]) for k, v in labels.items()}
    for k, c in colors.items():
        s = SPEC[k]
        if s["mode"] == "box":
            box = [s["cx"] - s["w"] / 2, s["cy"] - s["h"] / 2, s["cx"] + s["w"] / 2, s["cy"] + s["h"] / 2]
        elif "top" in s:
            box = [s["cx"] - s["w"] / 2, s["top"], s["cx"] + s["w"] / 2, s["top"] + 8]
        else:
            box = [s["cx"] - s["w"] / 2, s["bottom"] - 8, s["cx"] + s["w"] / 2, s["bottom"]]
        d.rectangle(box, outline=c, width=4)
        if f:
            ty = box[1] - 32 if k not in ("mouth", "body") else box[3] + 4
            tx = box[0] + 4
            if k == "body":
                ty = 960
            if k == "glasses":   # 目のラベルと重ならないよう左外側へ
                tx, ty = 40, box[1] + 40
            d.text((tx, ty), labels[k], fill=c, font=f)
    g.save(out / "avatar_guide.png")
    print("docs/avatar_template.png と docs/avatar_guide.png を作りました")


# ---------------------------------------------------------------- 変換
def remove_background(im: Image.Image) -> Image.Image:
    """透明部分がほとんど無い画像は、四隅から似た色を塗りつぶして背景を透明にする。"""
    im = im.convert("RGBA")
    alpha = im.getchannel("A")
    if alpha.getextrema()[0] < 250:      # すでに透明部分がある
        return im
    rgb = im.convert("RGB")
    key = (255, 0, 254)
    w, h = rgb.size
    for xy in [(0, 0), (w - 1, 0), (0, h - 1), (w - 1, h - 1)]:
        if rgb.getpixel(xy) != key:
            ImageDraw.floodfill(rgb, xy, key, thresh=38)
    # 塗りつぶした色の画素だけ透明にする
    r, g, b = rgb.split()
    m = Image.eval(r, lambda v: 255 if v == 255 else 0)
    m = Image.composite(m, Image.new("L", rgb.size, 0), Image.eval(g, lambda v: 255 if v == 0 else 0))
    m = Image.composite(m, Image.new("L", rgb.size, 0), Image.eval(b, lambda v: 255 if v == 254 else 0))
    im.putalpha(Image.eval(m, lambda v: 0 if v else 255))
    return im


def place(im: Image.Image, layer: str, adj: dict, stem: str = "") -> Image.Image:
    spec = SPEC["kind_full"] if layer == "kind" and FULL_RE.match(stem) else SPEC[layer]
    canvas = Image.new("RGBA", (S, S), (0, 0, 0, 0))
    if spec["mode"] == "cover" or adj.get("mode") == "keep":
        src = im.convert("RGBA")
        if spec["mode"] == "cover":
            r = max(S / src.width, S / src.height)
            src = src.resize((round(src.width * r), round(src.height * r)), Image.LANCZOS)
            canvas.paste(src, ((S - src.width) // 2, (S - src.height) // 2))
        else:
            src = src.resize((S, round(src.height * S / src.width)), Image.LANCZOS)
            canvas.alpha_composite(src, (0, 0))
        return shift(canvas, adj)
    im = remove_background(im)
    bbox = im.getchannel("A").point(lambda v: 255 if v > 16 else 0).getbbox()
    if not bbox:
        raise ValueError("描かれている部分が見つかりません（全面透明）")
    part = im.crop(bbox)
    if spec["mode"] == "width":
        r = spec["w"] / part.width
    else:
        r = min(spec["w"] / part.width, spec["h"] / part.height)
    r *= adj.get("scale", 1.0)
    part = part.resize((max(1, round(part.width * r)), max(1, round(part.height * r))), Image.LANCZOS)
    x = round(spec["cx"] - part.width / 2)
    if "top" in spec:
        y = spec["top"]
    elif "bottom" in spec:
        y = spec["bottom"] - part.height
    else:
        y = round(spec["cy"] - part.height / 2)
    x += int(adj.get("dx", 0)); y += int(adj.get("dy", 0))
    return paste_any(canvas, part, x, y)


def paste_any(canvas, part, x, y):
    """キャンバスからはみ出す位置でも貼れるようにする（はみ出た部分は切り捨て）。"""
    sx, sy = max(0, -x), max(0, -y)
    ex, ey = min(part.width, S - x), min(part.height, S - y)
    if ex > sx and ey > sy:
        canvas.alpha_composite(part.crop((sx, sy, ex, ey)), (max(0, x), max(0, y)))
    return canvas


def shift(canvas, adj):
    if not (adj.get("dx") or adj.get("dy") or adj.get("scale")):
        return canvas
    sc = adj.get("scale", 1.0)
    c = canvas.resize((round(S * sc), round(S * sc)), Image.LANCZOS) if sc != 1.0 else canvas
    out = Image.new("RGBA", (S, S), (0, 0, 0, 0))
    paste_any(out, c, int(adj.get("dx", 0)) - (c.width - S) // 2, int(adj.get("dy", 0)) - (c.height - S) // 2)
    return out


def build(src: Path, dst: Path, size: int, quality: int):
    dst.mkdir(parents=True, exist_ok=True)
    adjust = {}
    if (src / "adjust.json").exists():
        adjust = {k: v for k, v in json.loads((src / "adjust.json").read_text(encoding="utf-8")).items() if not k.startswith("_")}
    done = {k: [] for k in ORDER}
    for f in sorted(src.glob("*")):
        if f.suffix.lower() not in (".png", ".jpg", ".jpeg", ".webp") or f.name.startswith("_"):
            continue
        stem = f.stem.lower()
        if not NAME_RE.match(stem):
            print(f"  ? {f.name}: ファイル名が「レイヤー_番号」の形ではないのでスキップ")
            continue
        layer = stem.split("_")[0]
        try:
            img = place(Image.open(f), layer, {k: v for k, v in adjust.get(stem, {}).items() if k in ("scale", "dx", "dy", "mode")}, stem)
        except Exception as e:
            print(f"  ✗ {f.name}: {e}")
            continue
        out = img.resize((size, size), Image.LANCZOS)
        if layer == "bg":
            out = out.convert("RGB")
        path = dst / f"{stem}.webp"
        out.save(path, "WEBP", quality=quality, method=6)
        done[layer].append((stem, img))
        print(f"  ✓ {f.name} → {rel(path)}  {path.stat().st_size // 1024}KB")

    # 既存の出力も含めた一覧
    manifest = {k: sorted(p.name for p in dst.glob(f"{k}_*.webp")) for k in ORDER}
    manifest = {k: v for k, v in manifest.items() if v}
    # 人外の頭ごとの「目・口の高さ」と「帽子を下げる量」（avatar.js が目・口・眼鏡・帽子をずらすのに使う）
    anchors = {}
    for f in manifest.get("kind", []):
        stem = f[:-5]
        if FULL_RE.match(stem):
            continue
        a = adjust.get(stem, {})
        anchors[stem] = {"eyes": a.get("eyes", KIND_EYES), "mouth": a.get("mouth", KIND_MOUTH), "hat": a.get("hat", 165)}
    if anchors:
        manifest["anchors"] = anchors
    # 帽子ごとに「人外の頭にかぶせるときだけ」追加でずらす量
    hat_animal = {f[:-5]: adjust[f[:-5]]["animal"] for f in manifest.get("head", []) if "animal" in adjust.get(f[:-5], {})}
    if hat_animal:
        manifest["hatAnimal"] = hat_animal
    (dst / "manifest.json").write_text(json.dumps(manifest, ensure_ascii=False, indent=1), encoding="utf-8")
    n = sum(len(v) for v in manifest.values())
    print(f"\n{rel(dst / 'manifest.json')} を更新しました（{n} パーツ）: " + ", ".join(f"{k} {len(v)}" for k, v in manifest.items()))
    preview(src, done)


def preview(src: Path, done: dict):
    """変換したパーツを素体に重ねた一覧（位置ずれの確認用）"""
    items = [(k, stem, img) for k in ORDER for stem, img in done[k]]
    if not items:
        return
    cell, cols = 256, 6
    rows = (len(items) + cols - 1) // cols
    sheet = Image.new("RGB", (cell * cols, (cell + 28) * rows), (30, 26, 22))
    base = Image.new("RGBA", (S, S), (70, 80, 100, 255))
    draw_mannequin(ImageDraw.Draw(base), fill=(225, 190, 160), line=(60, 40, 30))
    f = font(18)
    d = ImageDraw.Draw(sheet)
    for i, (k, stem, img) in enumerate(items):
        c = base.copy() if k != "bg" else Image.new("RGBA", (S, S))
        if k == "bg":
            c.alpha_composite(img)
            m = Image.new("RGBA", (S, S), (0, 0, 0, 0)); draw_mannequin(ImageDraw.Draw(m), fill=(225, 190, 160), line=(60, 40, 30)); c.alpha_composite(m)
        else:
            c.alpha_composite(img)
        x, y = (i % cols) * cell, (i // cols) * (cell + 28)
        sheet.paste(c.convert("RGB").resize((cell - 8, cell - 8)), (x + 4, y + 4))
        d.text((x + 8, y + cell - 2), stem, fill=(230, 220, 200), font=f)
    sheet.save(src / "_preview.png")
    print(f"確認用の一覧: {rel(src / '_preview.png')}（位置がずれていたら adjust.json で調整）")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--src", default=str(ROOT / "avatar_raw"))
    ap.add_argument("--dst", default=str(ROOT / "assets" / "avatar"))
    ap.add_argument("--size", type=int, default=512)
    ap.add_argument("--quality", type=int, default=88)
    ap.add_argument("--template", action="store_true", help="素体テンプレート画像を docs/ に作る")
    a = ap.parse_args()
    if a.template:
        return make_templates()
    src = Path(a.src)
    if not src.exists():
        src.mkdir(parents=True)
        print(f"{src} を作りました。ここに GPT で作ったパーツ画像を入れてから、もう一度実行してください。")
        return
    build(src, Path(a.dst), a.size, a.quality)


if __name__ == "__main__":
    main()
