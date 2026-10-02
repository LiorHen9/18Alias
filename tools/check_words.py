"""בדיקת רשימות המילים מול WORDS_GUIDE.md.
הרצה: python3 tools/check_words.py
בודק: מילים פסולות מהיסטוריית המשוב, כפילויות בין רמות, ושורות ארוכות מדי."""
import pathlib, re, sys
root = pathlib.Path(__file__).resolve().parent.parent
guide = (root / "WORDS_GUIDE.md").read_text(encoding="utf-8")
section = guide.split("## 9. היסטוריית משוב")[1]
paras = [p for p in section.split("\n\n") if p.count(",") > 20 and not p.lstrip().startswith("אושרו")]
banned = {w.strip() for p in paras for w in p.split(",") if w.strip()}
norm = lambda w: re.sub(r"[֑-ׇ'\"׳״]", "", w).strip()
banned_n = {norm(w) for w in banned}
problems, seen = [], {}
for lv in ("easy", "medium", "hard"):
    for i, line in enumerate((root / "words" / f"{lv}.txt").read_text(encoding="utf-8").splitlines(), 1):
        w = line.strip()
        if not w or w.startswith("#"): continue
        if norm(w) in banned_n: problems.append(f"{lv}:{i} פסול לפי היסטוריית המשוב: {w}")
        if norm(w) in seen: problems.append(f"{lv}:{i} כפול (מופיע גם ב־{seen[norm(w)]}): {w}")
        seen[norm(w)] = lv
        if len(w.split()) > 4: problems.append(f"{lv}:{i} ארוך מדי: {w}")
print(f"נבדקו {len(seen)} מילים מול {len(banned)} מילים פסולות.")
print("\n".join(problems) if problems else "הכול תקין ✓")
sys.exit(1 if problems else 0)
