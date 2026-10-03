"""מחיל החלטות מבודק המילים על הרשימות ועל WORDS_GUIDE.md.

הרצה:
    python3 tools/apply_review.py decisions.json sync_plan.json

decisions.json: רשימה של מסמכים מהבודק, כל אחד עם
    id, version, text, level (easy|medium|hard), status (live|pending|suggested|user),
    decision (keep|cut|null), newLevel (easy|medium|hard|null)

מה הסקריפט עושה:
- cut: מוחק את הביטוי מהרשימות ומוסיף אותו להיסטוריית המשוב במדריך.
- keep על ביטוי חדש (pending, suggested, user): מכניס אותו לרמה שלו, בסעיף "אושרו בבודק",
  ומוסיף אותו לרשימת הדוגמאות המאושרות במדריך.
- newLevel: מעביר את הביטוי לרמה החדשה.
- keep על ביטוי קיים בלי שינוי רמה: לא משנה כלום.

sync_plan.json: רשימת כתיבות לבסיס הנתונים של הבודק (delete או update), עם if_version,
כדי שהבודק יתאים למשחק אחרי העדכון.
"""
import json, pathlib, re, sys

root = pathlib.Path(__file__).resolve().parent.parent
LEVELS = ("easy", "medium", "hard")
APPROVED_HDR = "# --- אושרו בבודק ---"
norm = lambda w: re.sub(r"[֑-ׇ'\"׳״`]", "", w).replace("־", " ").strip()


def load_lists():
    return {lv: (root / "words" / f"{lv}.txt").read_text(encoding="utf-8").split("\n") for lv in LEVELS}


def save_lists(lists):
    for lv, lines in lists.items():
        clean = []
        for i, l in enumerate(lines):
            if l.startswith("# ---"):  # drop a section header left with no words under it
                j = i + 1
                while j < len(lines) and not lines[j].strip():
                    j += 1
                if j >= len(lines) or lines[j].startswith("#"):
                    continue
            clean.append(l)
        while len(clean) > 1 and not clean[-1].strip() and not clean[-2].strip():
            clean.pop()
        (root / "words" / f"{lv}.txt").write_text("\n".join(clean), encoding="utf-8")


def remove_word(lists, text):
    n = norm(text)
    for lv, lines in lists.items():
        lists[lv] = [l for l in lines if l.startswith("#") or not l.strip() or norm(l) != n]


def add_word(lists, lv, text):
    lines = lists[lv]
    if APPROVED_HDR not in lines:
        while lines and not lines[-1].strip():
            lines.pop()
        lines += ["", APPROVED_HDR, ""]
    i = lines.index(APPROVED_HDR) + 1
    while i < len(lines) and lines[i].strip() and not lines[i].startswith("#"):
        i += 1
    lines.insert(i, text)


def update_guide(cut, approved):
    p = root / "WORDS_GUIDE.md"
    g = p.read_text(encoding="utf-8")
    head, sec = g.split("## 9. היסטוריית משוב", 1)
    paras = sec.split("\n\n")
    hist_i = next(i for i, x in enumerate(paras) if x.count(",") > 20 and not x.lstrip().startswith("אושרו"))
    have = {norm(w) for w in paras[hist_i].split(",")}
    new_cut = [w for w in cut if norm(w) not in have]
    if new_cut:
        paras[hist_i] = paras[hist_i].rstrip() + ", " + ", ".join(new_cut)
    ap = [i for i, x in enumerate(paras) if x.lstrip().startswith("אושרו בבודק המילים")]
    if approved:
        if ap:
            body = paras[ap[0]].rstrip().rstrip(".")
            have_ok = {norm(w) for w in body.split(":", 1)[1].split(",")}
            add = [w for w in approved if norm(w) not in have_ok]
            if add:
                paras[ap[0]] = body + ", " + ", ".join(add) + "."
        else:
            paras.insert(hist_i + 2, "אושרו בבודק המילים (דוגמאות טובות לכיוון): " + ", ".join(approved) + ".")
    # a word that was approved and later cut leaves the approved list
    if new_cut and ap:
        body = paras[ap[0]].rstrip().rstrip(".")
        label, words = body.split(":", 1)
        cut_n = {norm(w) for w in cut}
        keep = [w.strip() for w in words.split(",") if w.strip() and norm(w) not in cut_n]
        paras[ap[0]] = label + ": " + ", ".join(keep) + "."
    p.write_text(head + "## 9. היסטוריית משוב" + "\n\n".join(paras), encoding="utf-8")
    return new_cut


def main(dec_path, plan_path):
    docs = json.loads(pathlib.Path(dec_path).read_text(encoding="utf-8"))
    lists = load_lists()
    cut, approved, moved, plan = [], [], [], []
    for d in docs:
        text, dec, status = d["text"].strip(), d.get("decision"), d.get("status")
        target = d.get("newLevel") or d["level"]
        if target not in LEVELS:
            target = d["level"]
        if dec == "cut":
            remove_word(lists, text)
            cut.append(text)
            plan.append({"op": "delete", "collection": "phrases", "doc_id": d["id"], "if_version": d["version"]})
            continue
        is_new = dec == "keep" and status in ("pending", "suggested", "user")
        is_move = target != d["level"]
        if not (is_new or is_move or dec):
            continue
        if is_new or is_move:
            remove_word(lists, text)
            add_word(lists, target, text)
        if is_new:
            approved.append(text)
        if is_move:
            moved.append(f"{text} ({d['level']}→{target})")
        data = {"status": "live", "decision": None, "level": target, "newLevel": None}
        plan.append({"op": "update", "collection": "phrases", "doc_id": d["id"], "data": data, "if_version": d["version"]})
    save_lists(lists)
    update_guide(cut, approved)
    pathlib.Path(plan_path).write_text(json.dumps(plan, ensure_ascii=False, indent=1), encoding="utf-8")
    counts = {lv: sum(1 for l in lists[lv] if l.strip() and not l.startswith("#")) for lv in LEVELS}
    summary = {"approved": approved, "cut": cut, "moved": moved, "counts": counts, "writes": len(plan)}
    print(json.dumps(summary, ensure_ascii=False))


if __name__ == "__main__":
    main(sys.argv[1], sys.argv[2])
