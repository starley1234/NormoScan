import difflib
from typing import Dict, List

def gost_diff(old_text: str, new_text: str) -> Dict:
    old_lines = old_text.splitlines()
    new_lines = new_text.splitlines()
    diff = list(difflib.unified_diff(old_lines, new_lines, fromfile="old", tofile="new", lineterm=""))
    html = difflib.HtmlDiff().make_table(old_lines, new_lines, fromdesc="Старый", todesc="Новый", context=True, numlines=2)
    # simple stats
    added = sum(1 for l in diff if l.startswith("+") and not l.startswith("+++"))
    removed = sum(1 for l in diff if l.startswith("-") and not l.startswith("---"))
    return {"diff": diff, "html": html, "added": added, "removed": removed, "unified": "\n".join(diff)}

def gost_diff_by_id(db, old_id: int, new_id: int):
    from ..models.gost import Gost
    old = db.query(Gost).filter(Gost.id==old_id).first()
    new = db.query(Gost).filter(Gost.id==new_id).first()
    if not old or not new:
        return None
    old_text = old.content_text or old.title or ""
    new_text = new.content_text or new.title or ""
    # fallback to file content if not in DB
    import os
    if not old_text and old.filepath and os.path.exists(old.filepath):
        try:
            import fitz
            old_text = "\n".join([p.get_text() for p in fitz.open(old.filepath)])
        except: pass
    if not new_text and new.filepath and os.path.exists(new.filepath):
        try:
            import fitz
            new_text = "\n".join([p.get_text() for p in fitz.open(new.filepath)])
        except: pass
    res = gost_diff(old_text[:10000], new_text[:10000])
    res["old"]={"id": old.id, "designation": old.designation}
    res["new"]={"id": new.id, "designation": new.designation}
    return res
