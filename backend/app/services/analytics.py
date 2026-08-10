from typing import List, Dict, Any
from sqlalchemy.orm import Session
from sqlalchemy import or_
from ..models.check import Check
from datetime import datetime, timedelta
import collections, re

def analytics_summary(db: Session, days: int=30, department: str=None) -> Dict[str,Any]:
    since = datetime.utcnow() - timedelta(days=days)
    q = db.query(Check).filter(Check.created_at >= since)
    checks = q.all()
    total=len(checks)
    counter=collections.Counter()
    by_day=collections.Counter()
    for c in checks:
        day = c.created_at.strftime("%Y-%m-%d") if c.created_at else "unknown"
        by_day[day]+=1
        errs = c.errors_json or []
        for e in errs:
            code = e.get("code") or e.get("ГОСТ") or "unknown"
            counter[code]+=1
    top = counter.most_common(5)
    # Enhanced LLM-like summary (still template, but richer; in prod call Gemma 12B)
    if top:
        most = top[0][0]
        # Trend: compare last week vs previous
        last_week = datetime.utcnow() - timedelta(days=7)
        recent = sum(1 for c in checks if c.created_at and c.created_at>=last_week)
        prev = total - recent
        trend = ""
        if prev>0:
            diff = (recent - prev/ (days/7 -1) if days>7 else recent - prev)
            if recent > prev:
                trend = f" Тренд ухудшается: за последнюю неделю {recent} проверок против ~{prev} ранее."
            else:
                trend = f" Тренд стабильный."
        if "2.307" in most:
            summary = f"За {days} дней всего {total} проверок. Участились ошибки оформления допусков ({most}) — {top[0][1]} случаев. Рекомендуется обучение по ГОСТ 2.307.{trend}"
        elif "2.104" in most:
            summary = f"За {days} дней {total} проверок. Преобладают ошибки основной надписи ({most}) — проверьте шаблоны штампа.{trend}"
        else:
            summary = f"За {days} дней {total} проверок. Топ ошибка: {most} ({top[0][1]}). Требует внимания.{trend}"
    else:
        summary = f"За {days} дней {total} проверок без критичных ошибок."
    if department:
        summary = f"[Отдел {department}] " + summary
    return {
        "period": f"{days}d",
        "total_checks": total,
        "top_errors": [{"code":k,"count":v} for k,v in top],
        "by_day": dict(by_day),
        "summary": summary,
        "since": since.isoformat(),
        "trend": by_day
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
            "mass": meta.get("Масса"),
            "litera": meta.get("Литера"),
            "created_at": c.created_at.isoformat() if c.created_at else None,
        })
    return kb

def search_knowledge_base(db: Session, query: str, top_k: int=10) -> List[Dict]:
    """Поиск по базе знаний изделий (метаданные)"""
    if not query:
        return export_knowledge_base(db)[:top_k]
    q = db.query(Check).filter(Check.status=="done")
    # naive ilike on JSON string
    # Use or_ across filename and meta_json
    all_checks = q.all()
    query_lower = query.lower()
    scored=[]
    for c in all_checks:
        meta = c.meta_json or {}
        text = f"{c.filename} {meta.get('Обозначение','')} {meta.get('Наименование','')} {meta.get('Материал','')}".lower()
        score = 0
        # simple scoring: number of query tokens matched
        for token in query_lower.split():
            if token in text:
                score+=1
        if score>0 or query_lower in text:
            scored.append((score, c))
    scored.sort(key=lambda x: x[0], reverse=True)
    out=[]
    for score, c in scored[:top_k]:
        meta=c.meta_json or {}
        out.append({
            "check_id": c.id,
            "filename": c.filename,
            "designation": meta.get("Обозначение"),
            "name": meta.get("Наименование"),
            "material": meta.get("Материал"),
            "score": score,
            "created_at": c.created_at.isoformat() if c.created_at else None,
        })
    return out

def generate_llm_report(db: Session, days: int=30) -> Dict[str,Any]:
    """LLM-отчёт через Gemma (mock: template + RAG)"""
    base = analytics_summary(db, days=days)
    # In prod, call vlm_service or openai client with prompt
    # Here we enrich with recommendations
    recs=[]
    for err in base["top_errors"][:3]:
        code = err["code"]
        if "2.307" in code:
            recs.append("Проведите воркшоп по ГОСТ 2.307 (допуски) для отдела, обновите шаблон CAD.")
        elif "2.104" in code:
            recs.append("Проверьте шаблон основной надписи в Компасе/AutoCAD, поле Масса обязательно.")
        elif "2.305" in code:
            recs.append("Дайте памятку по стрелкам разрезов (засечка 45°) — много ошибок 2.305.")
        else:
            recs.append(f"Разберите ошибку {code} на ближайшем нормоконтроле.")
    return {**base, "recommendations": recs, "generated_by": "mock-llm (в проде — Gemma-3-12B)"}
