/* =====================================================================
 *  アバター描画ライブラリ（ゲーム画面・アバター工房・分析ページで共通）
 *
 *  ・アバターは 8 つのレイヤー（背景・服・顔・目・口・髪・帽子/髪飾り・眼鏡）の重ね合わせです。
 *  ・各レイヤーは「内蔵パーツ（SVG で描画・色を自由に変えられる）」か
 *    「画像パーツ（assets/avatar/ の PNG/WebP。GPT などで作ったもの）」を選べます。
 *  ・座標は 100×100 の正方形（画像パーツは 1024×1024 を想定）で、
 *    tools/avatar_parts.py が画像パーツをこの位置に自動で合わせます。
 *
 *  使い方:
 *    await Avatar.init();                    // 画像パーツの一覧を読む（無くても OK）
 *    el.innerHTML = Avatar.html(cfg, { zoom: 1.3 });
 *    const cfg = Avatar.random("seed");      // おまかせ
 *    const blob = await Avatar.toPNG(cfg, 512);
 * ===================================================================== */
(function () {
  "use strict";
  // このファイルの置き場所（assets/ をここからの相対パスで探す）
  const HERE = (function () { try { const src = document.currentScript && document.currentScript.src; return src ? src.replace(/[^/]*$/, "") : ""; } catch (e) { return ""; } })();
  // CPU の席に座る先生（assets/teachers/<tch>.webp）。{ style: "teacher", tch: "ueno" } の形で指定する
  const TEACHER_KEYS = ["ueno", "komaya", "sato", "hochin", "miyamoto", "yamaguchi", "takahashi", "tsuji", "chi"];
  const isTeacher = cfg => !!(cfg && cfg.style === "teacher" && TEACHER_KEYS.includes(cfg.tch));
  const teacherSrc = (cfg, full) => HERE + "assets/teachers/" + cfg.tch + (full ? "_full" : "") + ".webp";

  const PAL = {
    SKIN: ["#fbe3cf", "#f3cba9", "#e4b08a", "#cf9068", "#b07250", "#8a553b", "#68402d", "#4a2c20"],
    HAIR: ["#1f1a17", "#4a2f22", "#7a4b2a", "#b0773a", "#e5c473", "#c4512f", "#a9adb5", "#f0eee8", "#3a5ba8", "#d06b9c", "#3e8a5c", "#6b4aa8"],
    CLOTH: ["#3a5ba8", "#b5452f", "#3e8a5c", "#c99a2e", "#6b4aa8", "#2b2b30", "#e8e2d4", "#8a5a3a", "#2f7f86", "#c45a87", "#5c6b7a", "#7a1f2b"],
    BG: ["#a8d5ba", "#f7c8a0", "#b8d4f0", "#f5e1a4", "#d9c2ec", "#f4b6c2", "#c9e4de", "#e8d5b7", "#7f9cc4", "#5d6b8a"],
    ACC: ["#c9a24a", "#b5452f", "#3a5ba8", "#2b2b30", "#e8e2d4", "#3e8a5c", "#6b4aa8", "#c45a87", "#8a5a3a", "#a9adb5"],
    // 種族ごとの毛色・体の色（p: 模様）
    FUR: {
      human: [],
      shiba: [{ c: "#d98a3d", n: "赤柴" }, { c: "#3b302b", n: "黒柴", p: "tan" }, { c: "#f2e6d4", n: "白柴" }, { c: "#b98e5e", n: "胡麻柴" }],
      cat: [{ c: "#e3a05b", n: "茶トラ", p: "stripe" }, { c: "#2f2a2a", n: "黒ねこ" }, { c: "#f5f1ea", n: "白ねこ" }, { c: "#9aa1aa", n: "グレー", p: "stripe" }, { c: "#f5f1ea", n: "三毛", p: "calico" }],
      rabbit: [{ c: "#f5f1ea", n: "白" }, { c: "#c9a27e", n: "茶" }, { c: "#8a7a70", n: "灰" }, { c: "#3a3333", n: "黒" }],
      fox: [{ c: "#e0782f", n: "きつね色" }, { c: "#f0d9a8", n: "金色" }, { c: "#a9adb5", n: "銀色" }],
      ghost: [{ c: "#f7f7ff", n: "しろ" }, { c: "#dbe8ff", n: "みずいろ" }, { c: "#ffe1ec", n: "ももいろ" }, { c: "#e3f7e6", n: "わかば" }],
      spirit: [{ c: "#7fd6a0", n: "森の精" }, { c: "#7fb8ff", n: "水の精" }, { c: "#ffd36b", n: "光の精" }, { c: "#d7a0ff", n: "夢の精" }, { c: "#ff9f8a", n: "火の精" }],
      robot: [{ c: "#b9c2cc", n: "ぎんいろ" }, { c: "#e0b04a", n: "きんいろ" }, { c: "#6fa8d6", n: "あおいろ" }, { c: "#e07a5f", n: "あかいろ" }]
    }
  };

  // レイヤー定義（描画順とは別。UI に出す順番）
  const LAYERS = [
    { k: "kind", ja: "種族", color: "furC", pal: "FUR", hue: "kindH" },
    { k: "bg", ja: "背景", color: "bgC", pal: "BG", hue: "bgH" },
    { k: "body", ja: "服", color: "bodyC", pal: "CLOTH", hue: "bodyH" },
    { k: "face", ja: "顔", color: "skin", pal: "SKIN" },
    { k: "eyes", ja: "目" },
    { k: "mouth", ja: "口" },
    { k: "hair", ja: "髪", color: "hairC", pal: "HAIR", hue: "hairH" },
    { k: "head", ja: "帽子・髪飾り", color: "accC", pal: "ACC", hue: "accH" },
    { k: "glasses", ja: "眼鏡", color: "glsC", pal: "ACC", hue: "glsH" }
  ];

  const LINE = "#2a1d16";
  const sw = 'stroke="' + LINE + '" stroke-width="0.8" stroke-linejoin="round" stroke-linecap="round"';
  function shade(hex, amt) {
    const n = parseInt(hex.slice(1), 16);
    let r = n >> 16, g = (n >> 8) & 255, b = n & 255;
    const f = amt < 0 ? 0 : 255, p = Math.abs(amt);
    r = Math.round((f - r) * p + r); g = Math.round((f - g) * p + g); b = Math.round((f - b) * p + b);
    return "#" + ((1 << 24) + (r << 16) + (g << 8) + b).toString(16).slice(1);
  }
  let UID = 0;

  // ---------- 内蔵パーツ（100×100 座標） ----------
  // 頭: 中心 (50,41) 横半径 17.1 縦半径 22.5 ／ 耳: (32.2,43.9) (67.8,43.9) 半径 3.7
  // 目: 左 42.7 右 57.3 高さ 43 ／ 口: 高さ 54.7 ／ 肩: 高さ 69 から下
  const SH = "M8,100 C8,82 22,71.5 40,69 L60,69 C78,71.5 92,82 92,100 Z";

  const BG = {
    plain: { ja: "無地", f: c => `<rect width="100" height="100" fill="${c}"/>` },
    glow: { ja: "光", f: c => { const id = "g" + (++UID); return `<defs><radialGradient id="${id}" cx="50%" cy="38%" r="65%"><stop offset="0" stop-color="${shade(c, .35)}"/><stop offset="1" stop-color="${shade(c, -.35)}"/></radialGradient></defs><rect width="100" height="100" fill="url(#${id})"/>`; } },
    dots: { ja: "水玉", f: c => { let s = `<rect width="100" height="100" fill="${c}"/>`; for (let y = 5; y < 100; y += 10) for (let x = (y / 10) % 2 ? 10 : 5; x < 100; x += 10) s += `<circle cx="${x}" cy="${y}" r="1.6" fill="${shade(c, .18)}"/>`; return s; } },
    stripes: { ja: "しま", f: c => { let s = `<rect width="100" height="100" fill="${c}"/>`; for (let i = -100; i < 100; i += 12) s += `<path d="M${i},100 L${i + 100},0" stroke="${shade(c, .12)}" stroke-width="5"/>`; return s; } },
    check: { ja: "チェック", f: c => { let s = `<rect width="100" height="100" fill="${c}"/>`; for (let y = 0; y < 100; y += 12.5) for (let x = (y / 12.5) % 2 ? 12.5 : 0; x < 100; x += 25) s += `<rect x="${x}" y="${y}" width="12.5" height="12.5" fill="${shade(c, .1)}"/>`; return s; } },
    rays: { ja: "集中線", f: c => { let s = `<rect width="100" height="100" fill="${c}"/>`; for (let i = 0; i < 16; i += 2) { const a1 = i / 16 * Math.PI * 2, a2 = (i + 1) / 16 * Math.PI * 2; s += `<path d="M50,40 L${50 + Math.cos(a1) * 90},${40 + Math.sin(a1) * 90} L${50 + Math.cos(a2) * 90},${40 + Math.sin(a2) * 90} Z" fill="${shade(c, .12)}"/>`; } return s; } },
    night: { ja: "月夜の村", f: c => { let s = `<rect width="100" height="100" fill="${shade(c, -.25)}"/><circle cx="80" cy="18" r="8" fill="#f4ecd0" opacity=".9"/>`; [[12, 12], [26, 24], [62, 9], [90, 34], [40, 15], [8, 40]].forEach(([x, y]) => s += `<circle cx="${x}" cy="${y}" r=".7" fill="#fff" opacity=".8"/>`); s += `<path d="M0,86 L8,86 L8,78 L14,72 L20,78 L20,86 L30,86 L30,80 L36,74 L42,80 L42,86 L58,86 L58,77 L65,70 L72,77 L72,86 L82,86 L82,79 L88,73 L94,79 L94,86 L100,86 L100,100 L0,100 Z" fill="${shade(c, -.55)}"/>`; return s; } },
    frame: { ja: "額縁", f: c => `<rect width="100" height="100" fill="${c}"/><rect x="4" y="4" width="92" height="92" fill="none" stroke="${shade(c, .3)}" stroke-width="1.5"/><rect x="7" y="7" width="86" height="86" fill="none" stroke="${shade(c, .15)}" stroke-width=".6"/>` }
  };

  const BODY = {
    none: { ja: "なし（からだのまま）", f: c => BODY.tee.f(c) },
    tee: { ja: "Tシャツ", f: c => `<path d="${SH}" fill="${c}" ${sw}/><path d="M42,69.5 Q50,77 58,69.5" fill="none" ${sw}/>` },
    hoodie: { ja: "パーカー", f: c => `<path d="M33,73 Q50,60 67,73 L66,78 Q50,70 34,78 Z" fill="${shade(c, -.2)}" ${sw}/><path d="${SH}" fill="${c}" ${sw}/><path d="M40,70 Q50,80 60,70" fill="${shade(c, -.15)}" ${sw}/><path d="M46,75 L45,86 M54,75 L55,86" ${sw}/><path d="M38,92 L62,92 L60,100 L40,100 Z" fill="${shade(c, -.1)}" ${sw}/>` },
    shirt: { ja: "えり付きシャツ", f: c => `<path d="${SH}" fill="${c}" ${sw}/><path d="M42,68.5 L50,78 L44,80 L39,71 Z M58,68.5 L50,78 L56,80 L61,71 Z" fill="${shade(c, .55)}" ${sw}/><path d="M50,78 L50,100" ${sw}/><circle cx="50" cy="85" r=".9" fill="${LINE}"/><circle cx="50" cy="93" r=".9" fill="${LINE}"/>` },
    vest: { ja: "ベスト", f: c => `<path d="${SH}" fill="#ece6d8" ${sw}/><path d="M24,74 C30,71 36,70 42,69.5 L50,86 L58,69.5 C64,70 70,71 76,74 L80,100 L20,100 Z" fill="${c}" ${sw}/><path d="M50,86 L50,100" ${sw}/><circle cx="47.5" cy="91" r=".9" fill="${shade(c, .5)}"/><circle cx="47.5" cy="96" r=".9" fill="${shade(c, .5)}"/>` },
    robe: { ja: "ローブ", f: c => `<path d="${SH}" fill="${c}" ${sw}/><path d="M40,69 L50,88 L60,69" fill="${shade(c, -.25)}" ${sw}/><path d="M40,69 L50,88 L60,69" fill="none" stroke="#d8b25a" stroke-width="1.6"/><path d="M50,88 L50,100" stroke="#d8b25a" stroke-width="1.6"/>` },
    cloak: { ja: "マント", f: c => `<path d="${SH}" fill="#e6dccb" ${sw}/><path d="M8,100 C8,82 22,71.5 40,69 L45,69 L36,100 Z M92,100 C92,82 78,71.5 60,69 L55,69 L64,100 Z" fill="${c}" ${sw}/><path d="M40,69 Q50,74 60,69 L58,72 Q50,77 42,72 Z" fill="${shade(c, -.2)}" ${sw}/><circle cx="50" cy="76" r="2.4" fill="#d8b25a" ${sw}/>` },
    apron: { ja: "エプロン", f: c => `<path d="${SH}" fill="${shade(c, -.3)}" ${sw}/><path d="M42,69.5 Q50,75 58,69.5" fill="none" ${sw}/><path d="M38,80 L62,80 L64,100 L36,100 Z" fill="#f2ede2" ${sw}/><path d="M38,80 L41,69.5 M62,80 L59,69.5" stroke="#f2ede2" stroke-width="2"/><rect x="45" y="86" width="10" height="6" rx="1" fill="none" ${sw}/>` },
    armor: { ja: "よろい", f: c => `<path d="${SH}" fill="#8d939c" ${sw}/><path d="M38,73 L62,73 L60,100 L40,100 Z" fill="#aeb4bc" ${sw}/><ellipse cx="22" cy="80" rx="13" ry="8" fill="${c}" ${sw}/><ellipse cx="78" cy="80" rx="13" ry="8" fill="${c}" ${sw}/><path d="M42,82 L58,82 M43,90 L57,90" ${sw}/>` },
    suit: { ja: "スーツ", f: c => `<path d="${SH}" fill="${c}" ${sw}/><path d="M42,69 L50,90 L58,69 Z" fill="#f4f1ea" ${sw}/><path d="M48.5,72 L51.5,72 L52.5,86 L50,90 L47.5,86 Z" fill="#b5452f" ${sw}/><path d="M42,69 L46,84 L38,74 M58,69 L54,84 L62,74" fill="none" ${sw}/>` },
    sweater: { ja: "タートルネック", f: c => `<path d="${SH}" fill="${c}" ${sw}/><path d="M42,64 L58,64 L59,72 Q50,75 41,72 Z" fill="${shade(c, -.12)}" ${sw}/><path d="M43,66.5 L57,66.5 M43,69 L57,69" stroke="${shade(c, -.3)}" stroke-width=".5"/><path d="M30,96 L30,100 M70,96 L70,100" ${sw}/>` }
  };

  const neck = s => `<path d="M44,55 L44,70 Q50,73 56,70 L56,55 Z" fill="${shade(s, -.12)}" ${sw}/>`;
  const ears = s => `<circle cx="32.2" cy="43.9" r="3.7" fill="${s}" ${sw}/><circle cx="67.8" cy="43.9" r="3.7" fill="${s}" ${sw}/>`;
  const nose = s => `<path d="M50,46.5 Q48.6,49.5 50.6,50" fill="none" stroke="${shade(s, -.35)}" stroke-width=".7" stroke-linecap="round"/>`;
  const FACE = {
    oval: { ja: "たまご形", f: s => neck(s) + ears(s) + `<ellipse cx="50" cy="41" rx="17.1" ry="22.5" fill="${s}" ${sw}/>` + nose(s) },
    round: { ja: "まる形", f: s => neck(s) + ears(s) + `<ellipse cx="50" cy="42" rx="18.2" ry="21" fill="${s}" ${sw}/>` + nose(s) },
    long: { ja: "面長", f: s => neck(s) + ears(s) + `<ellipse cx="50" cy="40.5" rx="16" ry="23.8" fill="${s}" ${sw}/>` + nose(s) },
    square: { ja: "しかく形", f: s => neck(s) + ears(s) + `<path d="M33,36 C33,24 40,18.5 50,18.5 C60,18.5 67,24 67,36 L66.5,52 C66,59 58,63.5 50,63.5 C42,63.5 34,59 33.5,52 Z" fill="${s}" ${sw}/>` + nose(s) },
    blush: { ja: "ほっぺ", f: s => FACE.oval.f(s) + `<ellipse cx="38.5" cy="50" rx="3.2" ry="1.8" fill="#e8838a" opacity=".55"/><ellipse cx="61.5" cy="50" rx="3.2" ry="1.8" fill="#e8838a" opacity=".55"/>` }
  };

  let NOBROW = false;
  const brow = (dy = 0, tilt = 0) => NOBROW ? "" : `<path d="M39.2,${37.5 + dy + tilt} Q42.7,${35.8 + dy} 46.2,${37.5 + dy - tilt}" fill="none" stroke="#3a2a20" stroke-width="1.1" stroke-linecap="round"/><path d="M53.8,${37.5 + dy - tilt} Q57.3,${35.8 + dy} 60.8,${37.5 + dy + tilt}" fill="none" stroke="#3a2a20" stroke-width="1.1" stroke-linecap="round"/>`;
  const both = f => f(42.7) + f(57.3);
  const EYES = {
    round: { ja: "ぱっちり", f: () => brow() + both(x => `<ellipse cx="${x}" cy="43" rx="3.1" ry="2.7" fill="#fff" ${sw}/><circle cx="${x}" cy="43.3" r="1.75" fill="#2a1d16"/><circle cx="${x + .7}" cy="42.5" r=".55" fill="#fff"/>`) },
    dot: { ja: "てん", f: () => brow() + both(x => `<circle cx="${x}" cy="43" r="1.5" fill="#2a1d16"/>`) },
    happy: { ja: "にっこり", f: () => brow(-.5) + both(x => `<path d="M${x - 2.8},44 Q${x},40.8 ${x + 2.8},44" fill="none" stroke="#2a1d16" stroke-width="1.1" stroke-linecap="round"/>`) },
    sleepy: { ja: "ねむそう", f: () => brow(.8) + both(x => `<path d="M${x - 3},43 Q${x},45.2 ${x + 3},43" fill="none" stroke="#2a1d16" stroke-width="1" stroke-linecap="round"/><path d="M${x - 3},43 L${x + 3},43" stroke="#2a1d16" stroke-width=".6"/>`) },
    sly: { ja: "あやしい", f: () => brow(0, 1.1) + both(x => `<path d="M${x - 3.2},43.4 Q${x},40.9 ${x + 3.2},42.6 Q${x},45 ${x - 3.2},43.4 Z" fill="#fff" ${sw}/><circle cx="${x + .6}" cy="43.1" r="1.3" fill="#2a1d16"/>`) },
    surprised: { ja: "びっくり", f: () => brow(-2) + both(x => `<circle cx="${x}" cy="43" r="3.2" fill="#fff" ${sw}/><circle cx="${x}" cy="43" r="1" fill="#2a1d16"/>`) },
    wink: { ja: "ウインク", f: () => brow() + `<ellipse cx="42.7" cy="43" rx="3.1" ry="2.7" fill="#fff" ${sw}/><circle cx="42.7" cy="43.3" r="1.75" fill="#2a1d16"/><circle cx="43.4" cy="42.5" r=".55" fill="#fff"/><path d="M54.5,43.5 Q57.3,41 60.1,43.5" fill="none" stroke="#2a1d16" stroke-width="1.1" stroke-linecap="round"/>` },
    fierce: { ja: "するどい", f: () => brow(.4, -1.3) + both(x => `<path d="M${x - 3},42 L${x + 3},42.6 Q${x},45.6 ${x - 3},42 Z" fill="#fff" ${sw}/><circle cx="${x}" cy="43.2" r="1.2" fill="#2a1d16"/>`) },
    tired: { ja: "つかれ目", f: () => brow(.6, .6) + both(x => `<ellipse cx="${x}" cy="43" rx="2.9" ry="2.2" fill="#fff" ${sw}/><circle cx="${x}" cy="43.4" r="1.4" fill="#2a1d16"/><path d="M${x - 2.4},46.4 Q${x},47.6 ${x + 2.4},46.4" fill="none" stroke="#8a6a5a" stroke-width=".6"/>`) },
    calm: { ja: "おだやか", f: () => brow(-.3) + both(x => `<path d="M${x - 3},43.4 Q${x},44.8 ${x + 3},43.4" fill="none" stroke="#2a1d16" stroke-width="1.1" stroke-linecap="round"/><path d="M${x + 2.6},43.6 L${x + 3.6},42.8" stroke="#2a1d16" stroke-width=".7"/>`) }
  };

  const ml = 'fill="none" stroke="#5a2a20" stroke-width="1.1" stroke-linecap="round"';
  const MOUTH = {
    smile: { ja: "ほほえみ", f: () => `<path d="M46,54 Q50,57.6 54,54" ${ml}/>` },
    neutral: { ja: "ふつう", f: () => `<path d="M46.5,55 L53.5,55" ${ml}/>` },
    grin: { ja: "にかっ", f: () => `<path d="M44.5,53.5 Q50,59.5 55.5,53.5 Z" fill="#fff" stroke="#5a2a20" stroke-width=".9" stroke-linejoin="round"/><path d="M45.5,54.4 L54.5,54.4" stroke="#c8b8a8" stroke-width=".4"/>` },
    laugh: { ja: "大笑い", f: () => `<path d="M45,53 Q50,61 55,53 Z" fill="#7a2a2a" stroke="#5a2a20" stroke-width=".9" stroke-linejoin="round"/><path d="M47.5,57.2 Q50,55.6 52.5,57.2 Q50,59 47.5,57.2 Z" fill="#e0707a"/>` },
    frown: { ja: "への字", f: () => `<path d="M46,56.3 Q50,53 54,56.3" ${ml}/>` },
    smirk: { ja: "にやり", f: () => `<path d="M46,55.4 Q51,56.4 54.5,53.4" ${ml}/>` },
    o: { ja: "おっ", f: () => `<ellipse cx="50" cy="55.2" rx="1.8" ry="2.2" fill="#7a2a2a" stroke="#5a2a20" stroke-width=".8"/>` },
    cat: { ja: "ねこ口", f: () => `<path d="M46,54.2 Q48,56.6 50,54.4 Q52,56.6 54,54.2" ${ml}/>` }
  };

  // 髪: back（顔の後ろ）と front（顔の前）
  const HAIR = {
    none: { ja: "なし", back: () => "", front: () => "" },
    short: { ja: "ショート", back: () => "", front: h => `<path d="M32.5,44 C30.5,23 40,15.5 50,15.5 C60,15.5 69.5,23 67.5,44 C66,35 63.5,30 58.5,28 C54,32 45,32.5 38.5,33.5 C35.5,36.5 33.5,40 32.5,44 Z" fill="${h}" ${sw}/>` },
    sidepart: { ja: "七三", back: () => "", front: h => `<path d="M32.4,45 C30,22 41,14.8 52,15.2 C62.5,15.6 70.5,23.5 67.6,45 C66.8,35 64,28.5 57,25.5 C50,30.5 42,31 36,35.5 C34,38.5 33,41.5 32.4,45 Z" fill="${h}" ${sw}/><path d="M57,25.5 C55,23 53,21 50.5,20" fill="none" stroke="${shade(h, .25)}" stroke-width=".7"/>` },
    spiky: { ja: "ツンツン", back: () => "", front: h => `<path d="M32.5,44 L30,34 L33.5,30 L31,22 L37.5,22 L37.5,14 L43.5,18 L47,10 L51.5,16.5 L57,10.5 L59,18 L66,14.5 L64.5,22 L70.5,23 L66.5,30 L70,35 L67.5,44 C66,36 63,31 58,30 L55,33 L51,30 L47,33.5 L43,30.5 L38.5,33.5 C35.5,36.5 33.5,40 32.5,44 Z" fill="${h}" ${sw}/>` },
    bob: { ja: "ボブ", back: h => `<path d="M29.5,42 C28.5,21.5 39.5,14.2 50,14.2 C60.5,14.2 71.5,21.5 70.5,42 L71.5,58.5 C67,61.5 63,60.5 61.5,56.5 L38.5,56.5 C37,60.5 33,61.5 28.5,58.5 Z" fill="${shade(h, -.12)}" ${sw}/>`, front: h => `<path d="M31.5,44 C30.5,23 40.5,16 50,16 C59.5,16 69.5,23 68.5,44 L66.5,31 L61,34 L56,29.5 L50.5,33.5 L45,29.5 L39.5,34 L34.5,31.5 Z" fill="${h}" ${sw}/>` },
    long: { ja: "ロング", back: h => `<path d="M29,42 C28,20.5 39.5,13.5 50,13.5 C60.5,13.5 72,20.5 71,42 L73.5,82 C67,86 61,84 58.5,76 L41.5,76 C39,84 33,86 26.5,82 Z" fill="${shade(h, -.12)}" ${sw}/>`, front: h => `<path d="M32,46 C30,23 40,15.5 50,15.5 C60,15.5 70,23 68,46 C67,58 66,64 67.5,72 C63,66 62.5,52 62,38 C58,31 53,28.5 50,27.5 C46,29.5 40,32 37,38 C37,52 36.5,66 32.5,72 C34,64 33,58 32,46 Z" fill="${h}" ${sw}/>` },
    ponytail: { ja: "ポニーテール", back: h => `<path d="M64,28 C78,24 82,40 78,56 C76,64 70,68 66,64 C72,56 72,42 64,36 Z" fill="${shade(h, -.12)}" ${sw}/>`, front: h => HAIR.short.front(h) + `<circle cx="66" cy="29" r="2" fill="${shade(h, -.35)}"/>` },
    bun: { ja: "おだんご", back: h => `<circle cx="50" cy="13" r="7.5" fill="${shade(h, -.08)}" ${sw}/>`, front: h => `<path d="M32.5,43 C31,24 40,17 50,17 C60,17 69,24 67.5,43 C65,32 59,26.5 50,26 C41,26.5 35,32 32.5,43 Z" fill="${h}" ${sw}/><path d="M42,20 Q50,22 58,20" fill="none" stroke="${shade(h, .2)}" stroke-width=".6"/>` },
    curly: { ja: "くるくる", back: h => [[30, 40], [29, 30], [34, 20], [42, 14.5], [50, 13], [58, 14.5], [66, 20], [71, 30], [70, 40], [31, 50], [69, 50]].map(([x, y]) => `<circle cx="${x}" cy="${y}" r="6.5" fill="${shade(h, -.1)}" ${sw}/>`).join(""), front: h => [[36, 27], [43, 22], [50, 21], [57, 22], [64, 27]].map(([x, y]) => `<circle cx="${x}" cy="${y}" r="5" fill="${h}" ${sw}/>`).join("") },
    wavy: { ja: "ウェーブ", back: h => `<path d="M29.5,40 C28,20 40,13.5 50,13.5 C60,13.5 72,20 70.5,40 C74,46 70,52 73,58 C75,64 70,70 66,68 L34,68 C30,70 25,64 27,58 C30,52 26,46 29.5,40 Z" fill="${shade(h, -.12)}" ${sw}/>`, front: h => `<path d="M32,44 C30.5,23 40.5,15.5 50,15.5 C59.5,15.5 69.5,23 68,44 C66,36 64,32 60,30 C56,34 52,30 49,32 C46,35 41,31 38,34 C35,37 33,41 32,44 Z" fill="${h}" ${sw}/>` }
  };

  const HEAD = {
    none: { ja: "なし", f: () => "" },
    cap: { ja: "キャップ", f: a => `<path d="M31,30.5 C31,17 40,11.5 50,11.5 C60,11.5 69,17 69,30.5 Z" fill="${a}" ${sw}/><path d="M30,30.5 Q52,26.5 78,32 Q62,36.5 30,33 Z" fill="${shade(a, -.2)}" ${sw}/><circle cx="50" cy="12.2" r="1.3" fill="${shade(a, -.3)}"/>` },
    beret: { ja: "ベレー帽", f: a => `<ellipse cx="47" cy="20" rx="21" ry="8" transform="rotate(-10 47 20)" fill="${a}" ${sw}/><path d="M46,12.5 L47,9.5" stroke="${LINE}" stroke-width="1.4" stroke-linecap="round"/>` },
    headband: { ja: "ヘアバンド", f: a => `<path d="M32.4,32 C35,18 65,18 67.6,32" fill="none" stroke="${a}" stroke-width="3.2" stroke-linecap="round"/><path d="M32.4,32 C35,18 65,18 67.6,32" fill="none" stroke="${shade(a, .3)}" stroke-width=".6"/>` },
    ribbon: { ja: "リボン", f: a => `<path d="M62,20 L54,14 L54,26 Z M62,20 L70,14 L70,26 Z" fill="${a}" ${sw}/><circle cx="62" cy="20" r="2" fill="${shade(a, -.2)}" ${sw}/>` },
    crown: { ja: "王冠", f: a => `<path d="M38,30 L36,16 L43,22 L50,12 L57,22 L64,16 L62,30 Z" fill="${a}" ${sw}/><circle cx="50" cy="24" r="1.5" fill="#c4512f"/><circle cx="43" cy="26" r="1" fill="#3a5ba8"/><circle cx="57" cy="26" r="1" fill="#3a5ba8"/>` },
    catears: { ja: "ねこみみ", f: a => `<path d="M33,27 L35,10 L46,20 Z M67,27 L65,10 L54,20 Z" fill="${a}" ${sw}/><path d="M36,23 L37,14 L43,20 Z M64,23 L63,14 L57,20 Z" fill="#f0a0b0"/>` },
    bandana: { ja: "バンダナ", f: a => `<path d="M31.5,33 C31,18 40,14 50,14 C60,14 69,18 68.5,33 C60,28.5 40,28.5 31.5,33 Z" fill="${a}" ${sw}/><path d="M68,30 L76,34 L72,38 Z M68,30 L74,27 L75,32 Z" fill="${shade(a, -.15)}" ${sw}/><circle cx="42" cy="22" r=".9" fill="#fff" opacity=".7"/><circle cx="56" cy="20" r=".9" fill="#fff" opacity=".7"/>` },
    flower: { ja: "花かざり", f: a => { let s = ""; for (let i = 0; i < 5; i++) { const t = i / 5 * Math.PI * 2; s += `<circle cx="${36 + Math.cos(t) * 2.6}" cy="${24 + Math.sin(t) * 2.6}" r="2.2" fill="${a}" ${sw}/>`; } return s + `<circle cx="36" cy="24" r="1.6" fill="#f4d35e"/>`; } }
  };

  const GLASSES = {
    none: { ja: "なし", f: () => "" },
    round: { ja: "丸メガネ", f: a => `<circle cx="42.7" cy="43" r="4.8" fill="none" stroke="${a}" stroke-width="1"/><circle cx="57.3" cy="43" r="4.8" fill="none" stroke="${a}" stroke-width="1"/><path d="M47.5,43 Q50,41.6 52.5,43 M37.9,42.5 L33,41.5 M62.1,42.5 L67,41.5" fill="none" stroke="${a}" stroke-width="1"/>` },
    square: { ja: "四角メガネ", f: a => `<rect x="37.4" y="39.4" width="10.6" height="7.4" rx="1.4" fill="none" stroke="${a}" stroke-width="1"/><rect x="52" y="39.4" width="10.6" height="7.4" rx="1.4" fill="none" stroke="${a}" stroke-width="1"/><path d="M48,42.5 L52,42.5 M37.4,41.5 L33,41 M62.6,41.5 L67,41" stroke="${a}" stroke-width="1"/>` },
    sun: { ja: "サングラス", f: a => `<path d="M37,40 L48,40 L47.4,45 Q46,47.6 42.5,47.6 Q38,47.6 37.4,45 Z M52,40 L63,40 L62.6,45 Q62,47.6 57.5,47.6 Q54,47.6 52.6,45 Z" fill="#1d1a20" stroke="${a}" stroke-width=".9"/><path d="M48,41 L52,41 M37,40.5 L33,40 M63,40.5 L67,40" stroke="${a}" stroke-width="1"/><path d="M39,41.5 L42,41.5" stroke="#fff" stroke-width=".6" opacity=".5"/>` },
    monocle: { ja: "片メガネ", f: a => `<circle cx="57.3" cy="43" r="4.6" fill="rgba(255,255,255,.12)" stroke="${a}" stroke-width="1.1"/><path d="M61.5,45 Q64,54 61,62" fill="none" stroke="${a}" stroke-width=".5"/>` }
  };

  // ---------- 種族（人外） ----------
  const CREAM = "#fbf3e6";
  const furNeck = c => `<path d="M40,55 L40,71 Q50,75 60,71 L60,55 Z" fill="${shade(c, -.1)}" ${sw}/>`;
  const furBody = (c, chest = true) => `<path d="${SH}" fill="${c}" ${sw}/>` + (chest ? `<path d="M40,69.5 C42,80 46,86 50,88 C54,86 58,80 60,69.5 Q50,73 40,69.5 Z" fill="${CREAM}" ${sw}/>` : "");
  const clip = (id, shape) => `<defs><clipPath id="${id}">${shape}</clipPath></defs>`;
  const KIND = {
    human: { ja: "人間", head: null },
    shiba: {
      ja: "柴犬", body: f => furBody(f.c),
      neck: f => furNeck(f.c),
      head: f => { const black = f.p === "tan"; return "" +
        `<path d="M31,34 L33.5,15.5 L45.5,25.5 Z M69,34 L66.5,15.5 L54.5,25.5 Z" fill="${f.c}" ${sw}/><path d="M34.2,29.5 L35.6,20 L42,25.6 Z M65.8,29.5 L64.4,20 L58,25.6 Z" fill="${shade(f.c, -.3)}"/>` +
        `<ellipse cx="50" cy="43" rx="20.5" ry="18.5" fill="${f.c}" ${sw}/>` +
        `<path d="M32,46 C35,57.5 43,61.5 50,61.5 C57,61.5 65,57.5 68,46 C63,50.5 57,50.5 50,50 C43,50.5 37,50.5 32,46 Z" fill="${CREAM}"/>` +
        `<ellipse cx="42.7" cy="37.4" rx="2.3" ry="1.3" fill="${black ? "#d9a066" : CREAM}"/><ellipse cx="57.3" cy="37.4" rx="2.3" ry="1.3" fill="${black ? "#d9a066" : CREAM}"/>` +
        `<ellipse cx="50" cy="43" rx="20.5" ry="18.5" fill="none" ${sw}/>` +
        `<ellipse cx="50" cy="50.4" rx="2.5" ry="1.8" fill="${LINE}"/><path d="M50,52 L50,53.6" stroke="${LINE}" stroke-width=".7"/>` +
        `<ellipse cx="36.5" cy="50" rx="2.6" ry="1.4" fill="#f09a9a" opacity=".45"/><ellipse cx="63.5" cy="50" rx="2.6" ry="1.4" fill="#f09a9a" opacity=".45"/>`; }
    },
    cat: {
      ja: "ねこ", neck: f => furNeck(f.c), body: f => furBody(f.p === "calico" ? f.c : f.c, f.p !== undefined || true),
      head: f => { const id = "ck" + (++UID); let pat = "";
        if (f.p === "stripe") pat = `<path d="M50,27.5 L50,32.5 M45.4,28.3 L46.4,32.6 M54.6,28.3 L53.6,32.6 M31.5,44 L36,44.5 M68.5,44 L64,44.5" stroke="${shade(f.c, -.3)}" stroke-width="1.4" stroke-linecap="round"/>`;
        if (f.p === "calico") pat = clip(id, `<ellipse cx="50" cy="44" rx="19.5" ry="17.5"/>`) + `<g clip-path="url(#${id})"><ellipse cx="38" cy="32" rx="9" ry="7" fill="#e3a05b"/><ellipse cx="63" cy="35" rx="7" ry="6" fill="#3a302c"/></g>`;
        return `<path d="M32,36 L32.5,14.5 L45,26 Z M68,36 L67.5,14.5 L55,26 Z" fill="${f.p === "calico" ? "#3a302c" : f.c}" ${sw}/><path d="M34.5,30 L34.8,19.5 L41.5,26 Z M65.5,30 L65.2,19.5 L58.5,26 Z" fill="#f2a6b4"/>` +
          `<ellipse cx="50" cy="44" rx="19.5" ry="17.5" fill="${f.c}"/>` + pat + `<ellipse cx="50" cy="44" rx="19.5" ry="17.5" fill="none" ${sw}/>` +
          `<path d="M48.5,50 L51.5,50 L50,51.8 Z" fill="#e88a9a" stroke="${LINE}" stroke-width=".4"/>` +
          `<path d="M38,51 L28.5,49.5 M38,53.2 L28.5,54.5 M62,51 L71.5,49.5 M62,53.2 L71.5,54.5" stroke="${LINE}" stroke-width=".45"/>`; }
    },
    rabbit: {
      ja: "うさぎ", body: f => furBody(f.c),
      neck: f => furNeck(f.c),
      head: f => `<ellipse cx="41.5" cy="14" rx="4.4" ry="13" transform="rotate(-8 41.5 14)" fill="${f.c}" ${sw}/><ellipse cx="58.5" cy="14" rx="4.4" ry="13" transform="rotate(8 58.5 14)" fill="${f.c}" ${sw}/>` +
        `<ellipse cx="41.5" cy="15" rx="2" ry="9.5" transform="rotate(-8 41.5 15)" fill="#f2a6b4"/><ellipse cx="58.5" cy="15" rx="2" ry="9.5" transform="rotate(8 58.5 15)" fill="#f2a6b4"/>` +
        `<ellipse cx="50" cy="44" rx="18.5" ry="17.5" fill="${f.c}" ${sw}/><path d="M48.8,50 L51.2,50 L50,51.5 Z" fill="#e88a9a"/>` +
        `<ellipse cx="37.5" cy="50" rx="2.6" ry="1.4" fill="#f09a9a" opacity=".5"/><ellipse cx="62.5" cy="50" rx="2.6" ry="1.4" fill="#f09a9a" opacity=".5"/>`
    },
    fox: {
      ja: "きつね", body: f => furBody(f.c),
      neck: f => furNeck(f.c),
      head: f => `<path d="M30,37 L29.5,11 L45.5,25 Z M70,37 L70.5,11 L54.5,25 Z" fill="${f.c}" ${sw}/><path d="M29.6,17 L29.5,11 L35.5,16 Z M70.4,17 L70.5,11 L64.5,16 Z" fill="${LINE}"/>` +
        `<path d="M30,40 C30,28 39,24.5 50,24.5 C61,24.5 70,28 70,40 C70,50 60,60 50,62 C40,60 30,50 30,40 Z" fill="${f.c}" ${sw}/>` +
        `<path d="M31,44 C35,54 44,60 50,61.6 C56,60 65,54 69,44 C62,49 56,50 50,50 C44,50 38,49 31,44 Z" fill="${CREAM}"/>` +
        `<path d="M30,40 C30,28 39,24.5 50,24.5 C61,24.5 70,28 70,40 C70,50 60,60 50,62 C40,60 30,50 30,40 Z" fill="none" ${sw}/><ellipse cx="50" cy="51" rx="2.2" ry="1.6" fill="${LINE}"/>`
    },
    ghost: {
      ja: "お化け", noClothes: true, body: () => "",
      head: f => `<path d="M29.5,44 C29.5,25.5 39,18 50,18 C61,18 70.5,25.5 70.5,44 L72,88 C69,92 66,87 62.5,91 C59.5,95 56,88.5 53,92.5 C50,96 47,88.5 44,92.5 C41,95 38,88.5 35,91 C32,93 30,89 28,88 Z" fill="${f.c}" ${sw}/>` +
        `<path d="M30,62 C24,63 21,59 23.5,55.5 M70,62 C76,63 79,59 76.5,55.5" fill="none" ${sw}/><ellipse cx="41" cy="27" rx="5" ry="3" fill="#fff" opacity=".7"/>` +
        `<ellipse cx="37" cy="50.5" rx="2.6" ry="1.4" fill="#f09a9a" opacity=".5"/><ellipse cx="63" cy="50.5" rx="2.6" ry="1.4" fill="#f09a9a" opacity=".5"/>`
    },
    spirit: {
      ja: "精霊", noClothes: true,
      body: f => `<path d="M37,60 C39,74 45,85 50,99 C55,85 61,74 63,60 Z" fill="${shade(f.c, .35)}" opacity=".85" ${sw}/><circle cx="34" cy="80" r="1.4" fill="${shade(f.c, .5)}"/><circle cx="68" cy="74" r="1.1" fill="${shade(f.c, .5)}"/><circle cx="62" cy="90" r=".9" fill="${shade(f.c, .5)}"/>`,
      head: f => { const id = "sp" + (++UID); return `<defs><radialGradient id="${id}"><stop offset="0" stop-color="${shade(f.c, .4)}" stop-opacity=".9"/><stop offset="1" stop-color="${f.c}" stop-opacity="0"/></radialGradient></defs><circle cx="50" cy="44" r="31" fill="url(#${id})"/>` +
        `<path d="M50,13.5 C58,23.5 70.5,31.5 70.5,46 C70.5,58 61,64 50,64 C39,64 29.5,58 29.5,46 C29.5,31.5 42,23.5 50,13.5 Z" fill="${shade(f.c, .25)}" stroke="${shade(f.c, -.45)}" stroke-width=".8"/>` +
        `<path d="M50,13.5 C50,9.5 53,6.5 57.5,6.5 C56.5,10.5 53.5,12.8 50,13.5 Z" fill="#5fb36b" ${sw}/><circle cx="40" cy="30" r="1" fill="#fff"/><circle cx="62" cy="34" r=".7" fill="#fff"/>` +
        `<ellipse cx="37.5" cy="50.5" rx="2.6" ry="1.4" fill="#ff9aa8" opacity=".45"/><ellipse cx="62.5" cy="50.5" rx="2.6" ry="1.4" fill="#ff9aa8" opacity=".45"/>`; }
    },
    robot: {
      ja: "ロボット",
      body: f => `<path d="${SH}" fill="${f.c}" ${sw}/><rect x="40" y="77" width="20" height="13" rx="2" fill="${shade(f.c, -.18)}" ${sw}/><circle cx="45" cy="83.5" r="1.6" fill="#7fd6a0"/><circle cx="50" cy="83.5" r="1.6" fill="#ffd36b"/><circle cx="55" cy="83.5" r="1.6" fill="#ff8a7a"/>`,
      neck: f => `<rect x="45" y="56" width="10" height="15" fill="${shade(f.c, -.25)}" ${sw}/>`,
      head: f => `<path d="M50,22 L50,13.5" stroke="${LINE}" stroke-width="1"/><circle cx="50" cy="12.5" r="2.3" fill="#e07a5f" ${sw}/>` +
        `<rect x="26.5" y="37" width="5" height="11" rx="1.6" fill="${shade(f.c, -.2)}" ${sw}/><rect x="68.5" y="37" width="5" height="11" rx="1.6" fill="${shade(f.c, -.2)}" ${sw}/>` +
        `<rect x="30.5" y="22" width="39" height="38" rx="8" fill="${f.c}" ${sw}/><rect x="34.5" y="30.5" width="31" height="27" rx="5" fill="#eef6ff" stroke="${LINE}" stroke-width=".5"/>` +
        `<circle cx="34" cy="25.5" r=".9" fill="${shade(f.c, -.35)}"/><circle cx="66" cy="25.5" r=".9" fill="${shade(f.c, -.35)}"/>`
    }
  };

  const BUILTIN = { kind: KIND, bg: BG, body: BODY, face: FACE, eyes: EYES, mouth: MOUTH, hair: HAIR, head: HEAD, glasses: GLASSES };
  const DEFAULT = { v: 1, kind: "human", furC: 0, kindH: 0, bg: "glow", body: "tee", face: "oval", eyes: "round", mouth: "smile", hair: "short", head: "none", glasses: "none",
    skin: 1, hairC: 1, bodyC: 0, bgC: 0, accC: 0, glsC: 3, bgH: 0, bodyH: 0, hairH: 0, accH: 0, glsH: 0 };

  // ---------- 画像パーツ ----------
  let BASE = "assets/avatar/";
  const IMGS = {};   // layer -> [{ id: "img:hair_01", file, ja }]
  const HAT_ANIMAL = {}; // 帽子ごとの、人外の頭にかぶせるときだけの追加のずれ
  const ANCHORS = {}; // 人外の頭の画像ごとの目・口の高さ（1024 基準）と帽子を下げる量
  async function init(base) {
    if (base) BASE = base;
    try {
      const r = await fetch(BASE + "manifest.json", { cache: "no-cache" });
      if (!r.ok) return;
      const m = await r.json();
      if (m.anchors) Object.assign(ANCHORS, m.anchors);
      if (m.hatAnimal) Object.assign(HAT_ANIMAL, m.hatAnimal);
      Object.keys(m).forEach(layer => {
        if (!BUILTIN[layer]) return;
        IMGS[layer] = (m[layer] || []).map((f, i) => ({ id: "img:" + f.replace(/\.\w+$/, ""), file: f, ja: "画像 " + (i + 1) }));
      });
    } catch (e) { /* 画像パーツなし */ }
  }
  function imgFile(layer, id) { const o = (IMGS[layer] || []).find(x => x.id === id); return o ? BASE + o.file : null; }

  function options(layer) {
    const b = Object.keys(BUILTIN[layer]).map(id => ({ id, ja: BUILTIN[layer][id].ja, img: false }));
    return b.concat((IMGS[layer] || []).map(o => ({ id: o.id, ja: o.ja, img: true })));
  }


  // =====================================================================
  //  いきもの（図形で組み立てるキャラクタ）
  //  「コンピュータインタラクション」アクセルロッドのコンテストのキャラ作成と同じ部品
  //  cfg.style === "creature" のとき、背景＋図形のいきものだけで描く
  // =====================================================================
  const CR = {
    color: ["#ffb3c7", "#ffd27a", "#a8e6a1", "#9fd8ff", "#c9b3ff", "#ffffff", "#ff9f6b", "#7ee0d2", "#f7f3a1", "#d7dbe3", "#5b5f7a", "#e77b9c", "#d9893f", "#3d3542", "#f3e2c0"],
    shape: [["round", "まる"], ["tall", "たまご"], ["ghost", "おばけ"], ["mochi", "おもち"]],
    ears: [["none", "なし"], ["cat", "ねこ"], ["bunny", "うさぎ"], ["bear", "くま"], ["dog", "いぬ（立ち耳）"], ["floppy", "いぬ（たれ耳）"], ["horns", "つの"], ["antenna", "アンテナ"], ["sprout", "ふたば"]],
    pattern: [["none", "なし"], ["urajiro", "いぬの口もと"], ["maro", "まろ眉＋口もと"], ["belly", "おなか白"], ["panda", "パンダ目"], ["calico", "三毛"], ["tabby", "しましま"], ["tanuki", "たぬき"], ["penguin", "ペンギン"]],
    tail: [["none", "なし"], ["curl", "巻き尾"], ["cat", "ねこ"], ["devil", "あくま"], ["pom", "まるしっぽ"]],
    eyes: [["dot", "てん"], ["big", "きらきら"], ["happy", "にこ"], ["sleepy", "ねむい"], ["star", "ほし"], ["wink", "ウインク"], ["line", "じと"], ["smug", "ふふん"]],
    mouth: [["smile", "にっこり"], ["cat", "ねこ口"], ["open", "わーい"], ["fang", "きば"], ["small", "ちょこん"], ["tongue", "べー"]],
    acc: [["none", "なし"], ["ribbon", "リボン"], ["witch", "とんがり帽"], ["crown", "おうかん"], ["glasses", "めがね"], ["flower", "おはな"], ["bowtie", "ちょうネクタイ"]],
    accColor: ["#ff5f8f", "#ff8a00", "#6c4bd8", "#2bb673", "#2f80ed", "#2b2340", "#ffc400"],
  };
  const CR_KEYS = { cShape: "shape", cEars: "ears", cPat: "pattern", cTail: "tail", cEyes: "eyes", cMouth: "mouth", cAcc: "acc" };
  const CR_DEFAULT = { cCol: 0, cShape: "round", cEars: "cat", cPat: "none", cTail: "none", cEyes: "big", cMouth: "cat", cAcc: "ribbon", cAccC: 0, cCheek: 1 };
  const CR_PRESETS = [
    { ja: "赤柴", c: { cCol: 12, cShape: "round", cEars: "dog", cPat: "urajiro", cTail: "curl", cEyes: "dot", cMouth: "smile", cAcc: "none", cCheek: 1 } },
    { ja: "黒柴", c: { cCol: 13, cShape: "round", cEars: "dog", cPat: "maro", cTail: "curl", cEyes: "dot", cMouth: "smile", cAcc: "none", cCheek: 1 } },
    { ja: "白柴", c: { cCol: 14, cShape: "round", cEars: "dog", cPat: "none", cTail: "curl", cEyes: "dot", cMouth: "smile", cAcc: "none", cCheek: 1 } },
    { ja: "三毛ねこ", c: { cCol: 5, cShape: "round", cEars: "cat", cPat: "calico", cTail: "cat", cEyes: "big", cMouth: "cat", cAcc: "none", cCheek: 1 } },
    { ja: "たぬき", c: { cCol: 12, cShape: "mochi", cEars: "bear", cPat: "tanuki", cTail: "pom", cEyes: "dot", cMouth: "small", cAcc: "none", cCheek: 0 } },
    { ja: "ペンギン", c: { cCol: 13, cShape: "tall", cEars: "none", cPat: "penguin", cTail: "none", cEyes: "dot", cMouth: "small", cAcc: "bowtie", cAccC: 0, cCheek: 1 } },
    { ja: "パンダ", c: { cCol: 5, cShape: "round", cEars: "bear", cPat: "panda", cTail: "pom", cEyes: "big", cMouth: "small", cAcc: "none", cCheek: 1 } },
    { ja: "おばけ", c: { cCol: 5, cShape: "ghost", cEars: "none", cPat: "none", cTail: "none", cEyes: "big", cMouth: "tongue", cAcc: "none", cCheek: 1 } },
  ];
  const INK = "#2b2340";
  function shade(hex, f) {
    const n = parseInt(hex.slice(1), 16);
    let r = n >> 16, g = (n >> 8) & 255, b = n & 255;
    const t = f < 0 ? 0 : 255, p = Math.abs(f);
    r = Math.round((t - r) * p + r); g = Math.round((t - g) * p + g); b = Math.round((t - b) * p + b);
    return "#" + ((1 << 24) + (r << 16) + (g << 8) + b).toString(16).slice(1);
  }
  const SHAPES = {
    round: { top: 37, face: 72, ear: [34, 48], dx: 14, bottom: 107, body: (f, s) => `<ellipse cx="60" cy="72" rx="38" ry="35" fill="${f}" stroke="${s}" stroke-width="3"/>` },
    tall:  { top: 30, face: 66, ear: [38, 40], dx: 13, bottom: 110, body: (f, s) => `<rect x="27" y="30" width="66" height="80" rx="33" fill="${f}" stroke="${s}" stroke-width="3"/>` },
    ghost: { top: 28, face: 62, ear: [38, 38], dx: 13, bottom: 104, body: (f, s) => `<path d="M24,70 C24,42 40,28 60,28 C80,28 96,42 96,70 L96,104 Q90,96 84,104 Q78,112 72,104 Q66,96 60,104 Q54,112 48,104 Q42,96 36,104 Q30,112 24,104 Z" fill="${f}" stroke="${s}" stroke-width="3" stroke-linejoin="round"/>` },
    mochi: { top: 52, face: 80, ear: [34, 60], dx: 16, bottom: 108, body: (f, s) => `<ellipse cx="60" cy="80" rx="46" ry="28" fill="${f}" stroke="${s}" stroke-width="3"/>` },
  };
  function crEye(type, x, y) {
    switch (type) {
      case "big": return `<circle cx="${x}" cy="${y}" r="7" fill="${INK}"/><circle cx="${x - 2.2}" cy="${y - 2.4}" r="2.6" fill="#fff"/><circle cx="${x + 2.2}" cy="${y + 2.2}" r="1.2" fill="#fff"/>`;
      case "sleepy": return `<path d="M${x - 6},${y} Q${x},${y + 5} ${x + 6},${y}" fill="none" stroke="${INK}" stroke-width="3" stroke-linecap="round"/>`;
      case "happy": return `<path d="M${x - 6},${y + 2} Q${x},${y - 6} ${x + 6},${y + 2}" fill="none" stroke="${INK}" stroke-width="3" stroke-linecap="round"/>`;
      case "star": { let p = ""; for (let i = 0; i < 10; i++) { const r = i % 2 ? 2.8 : 7, a = -Math.PI / 2 + i * Math.PI / 5; p += `${(x + r * Math.cos(a)).toFixed(1)},${(y + r * Math.sin(a)).toFixed(1)} `; } return `<polygon points="${p}" fill="${INK}"/>`; }
      case "line": return `<path d="M${x - 6},${y} L${x + 6},${y}" stroke="${INK}" stroke-width="3" stroke-linecap="round"/><path d="M${x - 5},${y - 5} L${x + 6},${y - 4}" stroke="${INK}" stroke-width="2" stroke-linecap="round"/>`;
      case "smug": return `<path d="M${x - 6},${y - 1} Q${x},${y + 7} ${x + 6},${y - 1} Z" fill="${INK}"/><path d="M${x - 7},${y - 2} L${x + 7},${y - 2}" stroke="${INK}" stroke-width="2.5" stroke-linecap="round"/>`;
      case "shock": return `<circle cx="${x}" cy="${y}" r="7" fill="#fff" stroke="${INK}" stroke-width="2"/><circle cx="${x}" cy="${y}" r="2" fill="${INK}"/>`;
      case "sad": return `<circle cx="${x}" cy="${y + 1}" r="4" fill="${INK}"/><path d="M${x - 6},${y - 6} L${x + 5},${y - 9}" stroke="${INK}" stroke-width="2" stroke-linecap="round" transform="scale(${x < 60 ? 1 : -1},1) translate(${x < 60 ? 0 : -2 * x},0)"/>`;
      default: return `<circle cx="${x}" cy="${y}" r="4.5" fill="${INK}"/><circle cx="${x - 1.5}" cy="${y - 1.6}" r="1.5" fill="#fff"/>`;
    }
  }
  function crMouth(type, y) {
    const x = 60;
    switch (type) {
      case "cat": return `<path d="M${x - 8},${y - 1} Q${x - 4},${y + 5} ${x},${y} Q${x + 4},${y + 5} ${x + 8},${y - 1}" fill="none" stroke="${INK}" stroke-width="2.6" stroke-linecap="round" stroke-linejoin="round"/>`;
      case "open": return `<path d="M${x - 8},${y - 2} Q${x},${y + 13} ${x + 8},${y - 2} Z" fill="#c2405b" stroke="${INK}" stroke-width="2.4" stroke-linejoin="round"/>`;
      case "fang": return `<path d="M${x - 8},${y} Q${x},${y + 7} ${x + 8},${y}" fill="none" stroke="${INK}" stroke-width="2.6" stroke-linecap="round"/><path d="M${x + 2},${y + 3.2} L${x + 4},${y + 8} L${x + 6},${y + 2.4} Z" fill="#fff" stroke="${INK}" stroke-width="1.4" stroke-linejoin="round"/>`;
      case "small": return `<ellipse cx="${x}" cy="${y + 2}" rx="2.4" ry="1.8" fill="${INK}"/>`;
      case "tongue": return `<path d="M${x - 8},${y} Q${x},${y + 6} ${x + 8},${y}" fill="none" stroke="${INK}" stroke-width="2.6" stroke-linecap="round"/><path d="M${x + 1},${y + 3.5} Q${x + 4},${y + 11} ${x + 7},${y + 2.5}" fill="#ff7a9a" stroke="${INK}" stroke-width="1.6"/>`;
      case "o": return `<ellipse cx="${x}" cy="${y + 3}" rx="3.6" ry="4.6" fill="${INK}"/>`;
      case "smirk": return `<path d="M${x - 7},${y + 3} Q${x + 2},${y + 6} ${x + 9},${y - 3}" fill="none" stroke="${INK}" stroke-width="2.6" stroke-linecap="round"/>`;
      case "frown": return `<path d="M${x - 7},${y + 5} Q${x},${y - 2} ${x + 7},${y + 5}" fill="none" stroke="${INK}" stroke-width="2.6" stroke-linecap="round"/>`;
      default: return `<path d="M${x - 7},${y} Q${x},${y + 7} ${x + 7},${y}" fill="none" stroke="${INK}" stroke-width="2.6" stroke-linecap="round"/>`;
    }
  }
  function crEar(type, ex, ey, fill, stroke, top) {
    const mirror = inner => `<g>${inner}</g><g transform="translate(120,0) scale(-1,1)">${inner}</g>`;
    switch (type) {
      case "cat": return mirror(`<path d="M${ex - 12},${ey + 10} L${ex - 6},${ey - 18} L${ex + 10},${ey + 2} Z" fill="${fill}" stroke="${stroke}" stroke-width="3" stroke-linejoin="round"/><path d="M${ex - 7},${ey + 4} L${ex - 5},${ey - 9} L${ex + 3},${ey + 1} Z" fill="#ff9fb8"/>`);
      case "bunny": return mirror(`<ellipse cx="${ex + 2}" cy="${ey - 18}" rx="8" ry="22" transform="rotate(-12 ${ex + 2} ${ey - 18})" fill="${fill}" stroke="${stroke}" stroke-width="3"/><ellipse cx="${ex + 2}" cy="${ey - 17}" rx="3.5" ry="15" transform="rotate(-12 ${ex + 2} ${ey - 18})" fill="#ff9fb8"/>`);
      case "bear": return mirror(`<circle cx="${ex - 2}" cy="${ey - 4}" r="11" fill="${fill}" stroke="${stroke}" stroke-width="3"/><circle cx="${ex - 2}" cy="${ey - 4}" r="5" fill="${shade(fill, -0.15)}"/>`);
      case "dog": return mirror(`<path d="M${ex - 13},${ey + 10} Q${ex - 10},${ey - 14} ${ex - 3},${ey - 19} Q${ex + 7},${ey - 10} ${ex + 13},${ey + 3} Z" fill="${fill}" stroke="${stroke}" stroke-width="3" stroke-linejoin="round"/><path d="M${ex - 8},${ey + 5} Q${ex - 6},${ey - 7} ${ex - 3},${ey - 11} Q${ex + 3},${ey - 5} ${ex + 6},${ey + 2} Z" fill="#fff3dd"/>`);
      case "horns": return mirror(`<path d="M${ex - 2},${ey + 6} Q${ex - 8},${ey - 14} ${ex + 4},${ey - 20} Q${ex},${ey - 8} ${ex + 8},${ey + 4} Z" fill="#fff4dc" stroke="${stroke}" stroke-width="2.5" stroke-linejoin="round"/>`);
      case "antenna": return `<path d="M60,${top + 2} L60,${top - 16}" stroke="${stroke}" stroke-width="3"/><circle cx="60" cy="${top - 19}" r="5.5" fill="#ffc400" stroke="${stroke}" stroke-width="2.5"/>`;
      case "sprout": return `<path d="M60,${top + 2} L60,${top - 10}" stroke="#3c9b4f" stroke-width="3"/><path d="M60,${top - 9} Q50,${top - 22} 42,${top - 12} Q52,${top - 6} 60,${top - 9} Z" fill="#7ad37f" stroke="#3c9b4f" stroke-width="2"/><path d="M60,${top - 9} Q70,${top - 22} 78,${top - 12} Q68,${top - 6} 60,${top - 9} Z" fill="#7ad37f" stroke="#3c9b4f" stroke-width="2"/>`;
      default: return "";
    }
  }
  function crFloppy(ex, ey, fill, stroke) {
    const one = `<ellipse cx="${ex - 4}" cy="${ey + 12}" rx="9" ry="17" transform="rotate(22 ${ex - 4} ${ey + 12})" fill="${shade(fill, -0.18)}" stroke="${stroke}" stroke-width="3"/>`;
    return `<g>${one}</g><g transform="translate(120,0) scale(-1,1)">${one}</g>`;
  }
  function crTail(type, g, fill, stroke) {
    const x = 92, y = g.bottom - 18;
    switch (type) {
      case "curl": return `<circle cx="${x + 8}" cy="${y - 14}" r="12" fill="${fill}" stroke="${stroke}" stroke-width="3"/><path d="M${x + 4},${y - 16} Q${x + 8},${y - 22} ${x + 12},${y - 16} Q${x + 13},${y - 10} ${x + 7},${y - 10}" fill="none" stroke="#fff6e6" stroke-width="3.2" stroke-linecap="round"/>`;
      case "cat": return `<path d="M${x - 2},${y} Q${x + 26},${y - 4} ${x + 18},${y - 36}" fill="none" stroke="${stroke}" stroke-width="10" stroke-linecap="round"/><path d="M${x - 2},${y} Q${x + 26},${y - 4} ${x + 18},${y - 36}" fill="none" stroke="${fill}" stroke-width="5" stroke-linecap="round"/>`;
      case "devil": return `<path d="M${x - 2},${y} Q${x + 22},${y + 2} ${x + 18},${y - 30}" fill="none" stroke="${INK}" stroke-width="2.6" stroke-linecap="round"/><path d="M${x + 18},${y - 40} L${x + 11},${y - 27} L${x + 25},${y - 28} Z" fill="#e0565b" stroke="${INK}" stroke-width="2" stroke-linejoin="round"/>`;
      case "pom": return `<circle cx="${x + 6}" cy="${y - 4}" r="9" fill="#fffaf2" stroke="${stroke}" stroke-width="2.6"/>`;
      default: return "";
    }
  }
  let clipN = 0;
  function crPattern(type, g, fill, dx) {
    const f = g.face, cream = "#fff8ec";
    const clip = inner => { const id = "crc" + (++clipN) + Math.random().toString(36).slice(2, 6); return `<clipPath id="${id}">${g.body("#000", "none")}</clipPath><g clip-path="url(#${id})">${inner}</g>`; };
    const muzzle = `<ellipse cx="${60 - 7}" cy="${f + 10}" rx="13" ry="9" fill="${cream}"/><ellipse cx="${60 + 7}" cy="${f + 10}" rx="13" ry="9" fill="${cream}"/><ellipse cx="60" cy="${f + 3.5}" rx="3.6" ry="2.6" fill="${INK}"/>`;
    switch (type) {
      case "urajiro": return muzzle;
      case "maro": return muzzle + `<ellipse cx="${60 - dx}" cy="${f - 15}" rx="3.6" ry="2.6" fill="#f3d9a8"/><ellipse cx="${60 + dx}" cy="${f - 15}" rx="3.6" ry="2.6" fill="#f3d9a8"/>`;
      case "belly": return `<ellipse cx="60" cy="${Math.min(g.bottom - 14, f + 30)}" rx="18" ry="12" fill="${cream}" opacity=".9"/>`;
      case "calico": return clip(`<ellipse cx="38" cy="${g.top + 14}" rx="22" ry="18" fill="#d9893f"/><ellipse cx="86" cy="${g.top + 8}" rx="18" ry="14" fill="#3d3542"/>`);
      case "tabby": { const d = shade(fill, -0.32); return clip(`<path d="M60,${g.top + 3} L60,${g.top + 15} M49,${g.top + 6} L51,${g.top + 16} M71,${g.top + 6} L69,${g.top + 16}" stroke="${d}" stroke-width="3.6" stroke-linecap="round"/><path d="M18,${f - 2} L30,${f} M18,${f + 8} L30,${f + 7} M102,${f - 2} L90,${f} M102,${f + 8} L90,${f + 7}" stroke="${d}" stroke-width="3.2" stroke-linecap="round"/>`); }
      case "tanuki": return `<ellipse cx="60" cy="${f - 3}" rx="${dx + 13}" ry="9.5" fill="${shade(fill, -0.55)}"/><circle cx="${60 - dx}" cy="${f - 4}" r="7" fill="#fff3dd"/><circle cx="${60 + dx}" cy="${f - 4}" r="7" fill="#fff3dd"/>` + muzzle;
      case "penguin": return clip(`<ellipse cx="${60 - 11}" cy="${f + 2}" rx="21" ry="20" fill="#fffaf2"/><ellipse cx="${60 + 11}" cy="${f + 2}" rx="21" ry="20" fill="#fffaf2"/><ellipse cx="60" cy="${f + 30}" rx="22" ry="16" fill="#fffaf2"/>`) + `<path d="M55,${f + 2} L65,${f + 2} L60,${f + 8} Z" fill="#ffb02e" stroke="${INK}" stroke-width="1.6" stroke-linejoin="round"/>`;
      case "panda": return `<ellipse cx="${60 - dx}" cy="${f - 3}" rx="9" ry="8" transform="rotate(-20 ${60 - dx} ${f - 3})" fill="${shade(fill, -0.6)}"/><ellipse cx="${60 + dx}" cy="${f - 3}" rx="9" ry="8" transform="rotate(20 ${60 + dx} ${f - 3})" fill="${shade(fill, -0.6)}"/>`;
      default: return "";
    }
  }
  function crAcc(type, g, col, eyeY, dx) {
    const t = g.top;
    switch (type) {
      case "ribbon": return `<g transform="translate(82,${t + 6}) rotate(18)"><path d="M0,0 L-14,-9 L-14,9 Z" fill="${col}" stroke="${INK}" stroke-width="2" stroke-linejoin="round"/><path d="M0,0 L14,-9 L14,9 Z" fill="${col}" stroke="${INK}" stroke-width="2" stroke-linejoin="round"/><circle r="4" fill="${shade(col, -0.2)}" stroke="${INK}" stroke-width="2"/></g>`;
      case "witch": return `<path d="M42,${t + 3} L64,${t - 34} Q66,${t - 38} 70,${t - 34} L64,${t - 28} L80,${t + 3} Z" fill="${col}" stroke="${INK}" stroke-width="2.4" stroke-linejoin="round"/><ellipse cx="61" cy="${t + 3}" rx="31" ry="6" fill="${col}" stroke="${INK}" stroke-width="2.4"/><path d="M46,${t - 2} L76,${t - 2}" stroke="#ffc400" stroke-width="4"/>`;
      case "crown": return `<path d="M44,${t + 5} L44,${t - 12} L52,${t - 3} L60,${t - 17} L68,${t - 3} L76,${t - 12} L76,${t + 5} Z" fill="${col}" stroke="${INK}" stroke-width="2.4" stroke-linejoin="round"/><circle cx="60" cy="${t - 1}" r="2.6" fill="#fff"/>`;
      case "glasses": return `<circle cx="${60 - dx}" cy="${eyeY}" r="9.5" fill="rgba(255,255,255,.25)" stroke="${col}" stroke-width="2.8"/><circle cx="${60 + dx}" cy="${eyeY}" r="9.5" fill="rgba(255,255,255,.25)" stroke="${col}" stroke-width="2.8"/><path d="M${60 - dx + 9.5},${eyeY} Q60,${eyeY - 4} ${60 + dx - 9.5},${eyeY}" fill="none" stroke="${col}" stroke-width="2.6"/>`;
      case "flower": { let p = ""; for (let i = 0; i < 5; i++) { const a = i * Math.PI * 2 / 5; p += `<circle cx="${(82 + 6 * Math.cos(a)).toFixed(1)}" cy="${(t + 8 + 6 * Math.sin(a)).toFixed(1)}" r="5" fill="${col}" stroke="${INK}" stroke-width="1.6"/>`; } return p + `<circle cx="82" cy="${t + 8}" r="3.6" fill="#ffd84a" stroke="${INK}" stroke-width="1.6"/>`; }
      case "bowtie": { const y = Math.min(g.face + 24, g.bottom - 8); return `<path d="M60,${y} L46,${y - 8} L46,${y + 8} Z M60,${y} L74,${y - 8} L74,${y + 8} Z" fill="${col}" stroke="${INK}" stroke-width="2" stroke-linejoin="round"/><circle cx="60" cy="${y}" r="3.6" fill="${shade(col, -0.2)}" stroke="${INK}" stroke-width="1.6"/>`; }
      default: return "";
    }
  }
  function crNormalize(c) {
    const o = {};
    Object.keys(CR_DEFAULT).forEach(k => o[k] = c[k] === undefined ? CR_DEFAULT[k] : c[k]);
    Object.keys(CR_KEYS).forEach(k => { if (!CR[CR_KEYS[k]].some(x => x[0] === o[k])) o[k] = CR_DEFAULT[k]; });
    const clamp = (v, n) => { v = Number(v); return Number.isFinite(v) ? Math.max(0, Math.min(n - 1, Math.round(v))) : 0; };
    o.cCol = clamp(o.cCol, CR.color.length); o.cAccC = clamp(o.cAccC, CR.accColor.length); o.cCheek = o.cCheek ? 1 : 0;
    return o;
  }
  /** いきものの SVG の中身（viewBox は CR_VIEWBOX）。expr: normal / happy / shock / smirk / sad */
  const CR_VIEWBOX = "-14 -24 148 148";
  function creatureSVG(c, expr) {
    c = crNormalize(c);
    const g = SHAPES[c.cShape], fill = CR.color[c.cCol], stroke = shade(fill, -0.45), col = CR.accColor[c.cAccC];
    let eyes = c.cEyes, mouth = c.cMouth, extra = "";
    if (expr === "happy") { eyes = "happy"; mouth = "open"; }
    else if (expr === "shock") { eyes = "shock"; mouth = "o"; extra = `<path d="M92,${g.face - 22} Q86,${g.face - 12} 92,${g.face - 8} Q98,${g.face - 12} 92,${g.face - 22} Z" fill="#8fd3ff" stroke="${INK}" stroke-width="1.5"/>`; }
    else if (expr === "smirk") { eyes = "smug"; mouth = "smirk"; }
    else if (expr === "sad") { eyes = "sad"; mouth = "frown"; }
    const eyeY = g.face - 4, dx = g.dx;
    const eyeL = eyes === "wink" ? crEye("dot", 60 - dx, eyeY) : crEye(eyes, 60 - dx, eyeY);
    const eyeR = eyes === "wink" ? crEye("happy", 60 + dx, eyeY) : crEye(eyes, 60 + dx, eyeY);
    const cheek = (c.cCheek || expr === "happy") ? `<ellipse cx="${60 - dx - 10}" cy="${g.face + 6}" rx="6" ry="3.6" fill="#ff7a9a" opacity=".5"/><ellipse cx="${60 + dx + 10}" cy="${g.face + 6}" rx="6" ry="3.6" fill="#ff7a9a" opacity=".5"/>` : "";
    const mouthY = g.face + (["urajiro", "maro", "tanuki", "penguin"].includes(c.cPat) ? 11 : 8);
    return `<ellipse cx="60" cy="${g.bottom + 6}" rx="30" ry="4.5" fill="rgba(0,0,0,.18)"/>`
      + crTail(c.cTail, g, fill, stroke)
      + (c.cEars === "floppy" ? "" : crEar(c.cEars, g.ear[0], g.ear[1], fill, stroke, g.top))
      + g.body(fill, stroke)
      + crPattern(c.cPat, g, fill, dx)
      + (c.cEars === "floppy" ? crFloppy(g.ear[0], g.ear[1], fill, stroke) : "")
      + `<ellipse cx="46" cy="${g.top + 14}" rx="9" ry="5" fill="#fff" opacity=".35" transform="rotate(-25 46 ${g.top + 14})"/>`
      + cheek + eyeL + eyeR + (c.cPat === "penguin" ? "" : crMouth(mouth, mouthY)) + extra
      + crAcc(c.cAcc, g, col, eyeY, dx);
  }
  function crRandom(r) {
    const pick = a => a[Math.floor(r() * a.length)];
    if (r() < .35) return Object.assign({}, CR_DEFAULT, pick(CR_PRESETS).c);
    return crNormalize({
      cCol: Math.floor(r() * CR.color.length), cShape: pick(CR.shape)[0], cEars: pick(CR.ears)[0],
      cPat: r() < .6 ? "none" : pick(CR.pattern)[0], cTail: r() < .55 ? "none" : pick(CR.tail)[0],
      cEyes: pick(CR.eyes)[0], cMouth: pick(CR.mouth)[0], cAcc: r() < .45 ? "none" : pick(CR.acc)[0],
      cAccC: Math.floor(r() * CR.accColor.length), cCheek: r() < .6 ? 1 : 0,
    });
  }

  function normalize(cfg) {
    const c = Object.assign({}, DEFAULT, cfg && typeof cfg === "object" ? cfg : {});
    LAYERS.forEach(L => {
      const v = c[L.k];
      if (!(typeof v === "string" && (BUILTIN[L.k][v] || imgFile(L.k, v)))) c[L.k] = DEFAULT[L.k];
      if (L.color) {
        const pal = L.k === "kind" ? (PAL.FUR[c.kind] || []) : PAL[L.pal];
        const n = Number(c[L.color]);
        c[L.color] = Number.isFinite(n) ? Math.max(0, Math.min(Math.max(0, pal.length - 1), Math.round(n))) : 0;
      }
      if (L.hue) { const n = Number(c[L.hue]); c[L.hue] = Number.isFinite(n) ? ((Math.round(n) % 360) + 360) % 360 : 0; }
    });
    if (c.style === "creature") Object.assign(c, crNormalize(c)); else delete c.style;
    return c;
  }

  // 描画順: 背景 → 髪(後ろ) → 服(体) → 顔(種族の頭) → 目 → 口 → 髪(前) → 眼鏡 → 帽子
  const FULLIMG = /^img:kind_(ghost|spirit|obake|seirei|full)/;   // 体まで一体の人外の画像は服を着ない
  function layersOf(cfg) {
    const c = normalize(cfg), out = [];
    const col = (L) => PAL[L.pal][c[L.color]];
    if (c.style === "creature") {
      const bgL = LAYERS.find(L => L.k === "bg");
      if (c.bg.startsWith("img:")) out.push({ img: imgFile("bg", c.bg), hue: c.bgH }); else out.push({ svg: BG[c.bg].f(col(bgL)) });
      out.push({ svg: creatureSVG(c, layersOf.expr), vb: CR_VIEWBOX });
      return out;
    }
    const Lk = k => LAYERS.find(L => L.k === k);
    const kindImg = c.kind.startsWith("img:");
    const K = kindImg ? null : KIND[c.kind];
    const human = !kindImg && c.kind === "human";
    const fur = K && PAL.FUR[c.kind] ? (PAL.FUR[c.kind][c.furC] || PAL.FUR[c.kind][0]) : null;
    const push = (layer, svgFn, hueKey) => {
      const id = c[layer];
      if (id.startsWith("img:")) { if (svgFn !== "back") out.push({ img: imgFile(layer, id), hue: hueKey ? c[hueKey] : 0 }); return; }
      if (svgFn === "back") { const s = BUILTIN.hair[id].back(PAL.HAIR[c.hairC]); if (s) out.push({ svg: s }); return; }
      const s = svgFn(id); if (s) out.push({ svg: s });
    };
    push("bg", id => BG[id].f(col(Lk("bg"))), "bgH");
    push("hair", "back");
    if (K && !human && K.neck) out.push({ svg: K.neck(fur) });   // 人外の首は服の下
    // 体: お化け・精霊は服を着ない。「なし」は種族そのままの体
    if (K && !human && (K.noClothes || c.body === "none")) { const s = K.body(fur); if (s) out.push({ svg: s }); }
    else if (!(kindImg && (c.body === "none" || FULLIMG.test(c.kind)))) push("body", id => BODY[id].f(col(Lk("body"))), "bodyH");
    // 頭
    if (human) push("face", id => FACE[id].f(PAL.SKIN[c.skin]));
    else if (kindImg) out.push({ img: imgFile("kind", c.kind), hue: c.kindH });
    else out.push({ svg: K.head(fur) });
    // 人外の頭の画像は頭ごとに目・口の高さが違うので、目・口・眼鏡・帽子をずらす（単位: 100 分率）
    const an = kindImg && !FULLIMG.test(c.kind) ? (ANCHORS[c.kind.slice(4)] || { eyes: 577, mouth: 690, hat: 165 }) : null;
    const shifted = (fn, dy) => { const n = out.length; fn(); if (!dy) return; for (let i = n; i < out.length; i++) out[i].dy = dy; };
    NOBROW = !human;
    shifted(() => push("eyes", id => EYES[id].f()), an ? (an.eyes - 420) / 10.24 : 0);
    NOBROW = false;
    shifted(() => push("mouth", id => MOUTH[id].f()), an ? (an.mouth - 560) / 10.24 : 0);
    push("hair", id => HAIR[id].front(PAL.HAIR[c.hairC]), "hairH");
    shifted(() => push("glasses", id => GLASSES[id].f(PAL.ACC[c.glsC]), "glsH"), an ? (an.eyes - 420) / 10.24 : 0);
    shifted(() => push("head", id => HEAD[id].f(PAL.ACC[c.accC]), "accH"), an ? (an.hat + (HAT_ANIMAL[String(c.head).slice(4)] || 0)) / 10.24 : 0);
    // 連続する SVG はひとつにまとめる
    const merged = [];
    out.forEach(l => {
      if (l.svg && l.dy) l = { svg: `<g transform="translate(0 ${l.dy.toFixed(2)})">${l.svg}</g>` };
      const last = merged[merged.length - 1]; if (l.svg && last && last.svg) last.svg += l.svg; else merged.push(Object.assign({}, l));
    });
    return merged;
  }

  let cssDone = false;
  function css() {
    if (cssDone || typeof document === "undefined") return; cssDone = true;
    const st = document.createElement("style");
    st.textContent = ".ava{position:relative;width:100%;height:100%;overflow:hidden}.ava>.ava-in{position:absolute;inset:0;transform-origin:50% 40%}.ava-in>svg,.ava-in>img{position:absolute;inset:0;width:100%;height:100%;display:block}";
    document.head.appendChild(st);
  }

  /** HTML 文字列を返す。zoom > 1 で顔に寄る（丸いアイコン用） */
  function html(cfg, opt) {
    css();
    const z = (opt && opt.zoom) || 1;
    if (isTeacher(cfg)) {
      // 先生の絵は、もともと顔に寄った絵なので、あまり拡大しない。full: true で全身
      if (opt && opt.full) return `<div class="ava ava-full"><img src="${teacherSrc(cfg, true)}" alt="" draggable="false" style="width:100%;height:100%;object-fit:contain;object-position:50% 100%;display:block"></div>`;
      return `<div class="ava"><div class="ava-in" style="transform:scale(${Math.min(1.06, z)})"><img src="${teacherSrc(cfg)}" alt="" draggable="false"></div></div>`;
    }
    layersOf.expr = opt && opt.expr;
    const parts = layersOf(cfg).map(l => l.svg
      ? `<svg viewBox="${l.vb || "0 0 100 100"}" xmlns="http://www.w3.org/2000/svg">${l.svg}</svg>`
      : `<img src="${l.img}" alt=""${l.hue || l.dy ? ` style="${l.hue ? `filter:hue-rotate(${l.hue}deg);` : ""}${l.dy ? `transform:translateY(${l.dy.toFixed(2)}%)` : ""}"` : ""} draggable="false">`).join("");
    return `<div class="ava"><div class="ava-in" style="transform:scale(${z})">${parts}</div></div>`;
  }

  /** PNG（Blob）に書き出す */
  async function toPNG(cfg, size) {
    size = size || 512;
    const cv = document.createElement("canvas"); cv.width = cv.height = size;
    const ctx = cv.getContext("2d");
    const load = src => new Promise((res, rej) => { const im = new Image(); im.crossOrigin = "anonymous"; im.onload = () => res(im); im.onerror = rej; im.src = src; });
    if (isTeacher(cfg)) { ctx.drawImage(await load(teacherSrc(cfg)), 0, 0, size, size); return new Promise(r => cv.toBlob(r, "image/png")); }
    for (const l of layersOf(cfg)) {
      if (l.svg) {
        const url = "data:image/svg+xml;charset=utf-8," + encodeURIComponent(`<svg xmlns="http://www.w3.org/2000/svg" viewBox="${l.vb || "0 0 100 100"}" width="${size}" height="${size}">${l.svg}</svg>`);
        ctx.filter = "none"; ctx.drawImage(await load(url), 0, 0, size, size);
      } else {
        ctx.filter = l.hue ? `hue-rotate(${l.hue}deg)` : "none";
        ctx.drawImage(await load(l.img), 0, (l.dy || 0) * size / 100, size, size);
      }
    }
    return new Promise(r => cv.toBlob(r, "image/png"));
  }

  // ---------- おまかせ（同じ seed からは同じアバター） ----------
  function rng(seed) {
    let h = 1779033703 ^ String(seed).length;
    for (const ch of String(seed)) { h = Math.imul(h ^ ch.charCodeAt(0), 3432918353); h = (h << 13) | (h >>> 19); }
    return function () { h = Math.imul(h ^ (h >>> 16), 2246822507); h = Math.imul(h ^ (h >>> 13), 3266489909); h ^= h >>> 16; return (h >>> 0) / 4294967296; };
  }
  function random(seed) {
    const r = rng(seed === undefined ? Math.random() : seed), pick = a => a[Math.floor(r() * a.length)];
    const c = {};
    LAYERS.forEach(L => {
      let opts = options(L.k).map(o => o.id);
      if (L.k === "kind") opts = r() < .45 ? ["human"] : opts.filter(x => x !== "human");
      if (L.k === "head") opts = r() < .55 ? ["none"] : opts.filter(x => x !== "none");
      if (L.k === "glasses") opts = r() < .7 ? ["none"] : opts.filter(x => x !== "none");
      if (L.k === "hair") opts = opts.filter(x => x !== "none" || r() < .1);
      c[L.k] = pick(opts);
      if (L.color) c[L.color] = Math.floor(r() * (L.k === "kind" ? Math.max(1, (PAL.FUR[c.kind] || [0]).length) : PAL[L.pal].length));
      if (L.hue) c[L.hue] = 0;
    });
    c.hairC = r() < .75 ? Math.floor(r() * 8) : c.hairC;  // 自然な髪色を多めに
    if (c.kind !== "human") { if (r() < .8) c.hair = "none"; if (c.body !== "none" && r() < .4) c.body = "none"; }
    if (c.body === "none" && c.kind === "human") c.body = "tee";
    if (r() < .22) Object.assign(c, { style: "creature" }, crRandom(r));
    return normalize(c);
  }

  /** サーバーに送る前の整形（不要なキーを落とす） */
  function compact(cfg) {
    const c = normalize(cfg), o = { v: 1 };
    LAYERS.forEach(L => { o[L.k] = c[L.k]; if (L.color) o[L.color] = c[L.color]; if (L.hue && c[L.hue]) o[L.hue] = c[L.hue]; });
    if (c.style === "creature") { o.style = "creature"; Object.keys(CR_DEFAULT).forEach(k => o[k] = c[k]); }
    return o;
  }

  const kindInfo = k => ({ human: k === "human", noClothes: !!(KIND[k] && KIND[k].noClothes) || FULLIMG.test(String(k)), image: String(k).startsWith("img:") });
  const creature = { OPTS: CR, KEYS: CR_KEYS, DEFAULT: CR_DEFAULT, PRESETS: CR_PRESETS, random: s => crRandom(rng(s === undefined ? Math.random() : s)) };
  const api = { creature, kindInfo, init, html, toPNG, random, normalize, compact, options, LAYERS, PAL, DEFAULT, isTeacher, hasImages: () => Object.keys(IMGS).some(k => IMGS[k].length) };
  if (typeof window !== "undefined") window.Avatar = api;
  if (typeof module !== "undefined") module.exports = api;
})();
