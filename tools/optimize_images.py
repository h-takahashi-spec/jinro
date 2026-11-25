"""ChatGPT などで作った画像を、画面用の軽い WebP に変換します。

    pip install pillow
    python tools/optimize_images.py            # assets_raw/ → assets/
    python tools/optimize_images.py --src 別フォルダ

ファイル名（拡張子を除く）は docs/image_prompts.md の表と同じにしてください。
例: assets_raw/bg_day.png → assets/bg_day.webp
"""
import argparse
import json
from pathlib import Path

from PIL import Image, ImageOps

ROOT = Path(__file__).resolve().parent.parent

# 名前 → (幅, 高さ)。縦横比が違うときは中央で切り抜きます。
# TRANSPARENT のものは透明背景のまま、切り抜かずに全体を収めます。
WIDE = (1600, 1067)
STAGE = (1200, 862)
# 円卓の絵（stage）は下のふち約 5% に空色の帯が入っているので切り落とす
PRE_CROP = {"stage": (0, 0, 1, 0.94)}
MASCOT = (640, 640)
SMALL = (320, 320)
CARD = (640, 960)
AVATAR = (320, 320)
SPEC = {
    **{k: WIDE for k in ["bg_title", "bg_day", "bg_dusk", "bg_night",
                         "scene_morning", "scene_attack", "scene_execution", "scene_night",
                         "win_village", "win_werewolf"]},
    **{k: CARD for k in ["card_back", "role_werewolf", "role_possessed", "role_seer",
                         "role_medium", "role_bodyguard", "role_villager"]},
    **{f"avatar_{i:02d}": AVATAR for i in range(1, 13)},
    "stage": STAGE,
    "emblem": SMALL,
    **{k: MASCOT for k in ["mascot", "mascot_sleep", "mascot_cheer"]},
    **{f"stamp_{k}": SMALL for k in ["vote", "attack", "divine", "guard"]},
    **{f"story_{i:02d}": WIDE for i in range(1, 10)},
}
TRANSPARENT = {"emblem", "mascot", "mascot_sleep", "mascot_cheer", "stamp_vote", "stamp_attack", "stamp_divine", "stamp_guard"}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--src", default=str(ROOT / "assets_raw"))
    ap.add_argument("--dst", default=str(ROOT / "assets"))
    ap.add_argument("--quality", type=int, default=82)
    args = ap.parse_args()
    src, dst = Path(args.src), Path(args.dst)
    dst.mkdir(parents=True, exist_ok=True)

    done = set()
    for f in sorted(src.glob("*")):
        if f.suffix.lower() not in (".png", ".jpg", ".jpeg", ".webp"):
            continue
        key = f.stem.lower()
        if key not in SPEC:
            print(f"  ? {f.name}: 知らない名前なのでスキップ（docs/image_prompts.md の表を確認）")
            continue
        im = ImageOps.exif_transpose(Image.open(f))
        if key in TRANSPARENT:
            im = im.convert("RGBA")
            bbox = im.getchannel("A").point(lambda v: 255 if v > 10 else 0).getbbox()
            if bbox:
                im = im.crop(bbox)
            fitted = ImageOps.contain(im, (int(SPEC[key][0] * .94), int(SPEC[key][1] * .94)), method=Image.LANCZOS)
            out = Image.new("RGBA", SPEC[key], (0, 0, 0, 0))
            out.paste(fitted, ((SPEC[key][0] - fitted.width) // 2, (SPEC[key][1] - fitted.height) // 2), fitted)
            if im.getchannel("A").getextrema()[0] > 250:
                print(f"  ! {f.name}: 背景が透明ではありません（透明背景で作り直すと、画面になじみます）")
        else:
            im = im.convert("RGB")
            if key in PRE_CROP:   # 元画像のふちに不要な帯があるときに切り落とす（左, 上, 右, 下 の割合）
                l, t, r, b = PRE_CROP[key]; im = im.crop((int(im.width * l), int(im.height * t), int(im.width * r), int(im.height * b)))
            out = ImageOps.fit(im, SPEC[key], method=Image.LANCZOS, centering=(0.5, 0.4 if key.startswith("avatar") else 0.5))
        path = dst / f"{key}.webp"
        out.save(path, "WEBP", quality=args.quality, method=6)
        print(f"  ✓ {f.name} → {path.relative_to(ROOT) if path.is_relative_to(ROOT) else path}  {path.stat().st_size // 1024}KB")
        done.add(key)

    # 画面が読み込む一覧（存在する画像だけ）
    manifest = {k: f"{k}.webp" for k in SPEC if (dst / f"{k}.webp").exists()}
    (dst / "manifest.json").write_text(json.dumps(manifest, indent=1), encoding="utf-8")
    print(f"manifest.json を更新しました（{len(manifest)} 枚）")

    missing = [k for k in SPEC if k not in manifest]
    print(f"\n変換: {len(done)} 枚")
    if missing:
        print("まだ無い画像（代替表示になります）: " + ", ".join(missing))


if __name__ == "__main__":
    main()
