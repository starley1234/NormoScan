from typing import List, Dict, Any
from sqlalchemy.orm import Session
from ..models.check import Check
from datetime import datetime, timedelta
import json, collections

def analytics_summary(db: Session, days: int=30, department: str=None) -> Dict[str,Any]:
    since = datetime.utcnow() - timedelta(days=days)
    q = db.query(Check).filter(Check.created_at >= since)
    checks = q.all()
    total=len(checks)
    # aggregate errors by code
    counter=collections.Counter()
    for c in checks:
        errs = c.errors_json or []
        for e in errs:
            code = e.get("code") or e.get("ГОСТ") or "unknown"
            counter[code]+=1
    top = counter.most_common(5)
    # LLM-like summary (template, in prod call LLM)
    if top:
        most = top[0][0]
        if "2.307" in most:
            summary = f"За {days} дней всего {total} проверок. Участились ошибки оформления допусков ({most}) — {top[0][1]} случаев. Рекомендуется обучение по ГОСТ 2.307."
        elif "2.104" in most:
            summary = f"За {days} дней {total} проверок. Преобладают ошибки основной надписи ({most}) — проверьте шаблоны штампа."
        else:
            summary = f"За {days} дней {total} проверок. Топ ошибка: {most} ({top[0][1]}). Требует внимания."
    else:
        summary = f"За {days} дней {total} проверок без критичных ошибок."
    if department:
        summary = f"[Отдел {department}] " + summary
    return {
        "period": f"{days}d",
        "total_checks": total,
        "top_errors": [{"code":k,"count":v} for k,v in top],
        "summary": summary,
        "since": since.isoformat()
    }

def export_knowledge_base(db: Session) -> List[Dict]:
    checks = db.query(Check).filter(Check.status=="done").all()
    kb=[]
    for c in checks:
        meta = c.meta_json or {}
        kb.append({
            "check_id": c.id,
            "filename": c.filename,
            "designation": meta.get("Обозначение") or meta.get("designation"),
            "name": meta.get("Наименование") or meta.get("name"),
            "material": meta.get("Материал"),
            "created_at": c.created_at.isoformat() if c.created_at else None,
        })
    return kb
