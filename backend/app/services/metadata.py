import re
from typing import Any

from sqlalchemy.orm import Session

DEFAULT_SCHEMA = {
    "type":"object",
    "properties":{
        "Обозначение":{"type":"string","pattern":"^[A-ZА-Я0-9\\.\\-\\s]+$","description":"По ГОСТ 2.201"},
        "Наименование":{"type":"string"},
        "Материал":{"type":"string"},
        "Масса":{"type":"string"},
        "Литера":{"type":"string","enum":["","О","О1","О2","А","Б"]},
        "Масштаб":{"type":"string"},
        "Формат":{"type":"string","enum":["А0","А1","А2","А3","А4"]},
        "Разработал":{"type":"string"},
        "Проверил":{"type":"string"},
    },
    "required":["Обозначение","Наименование"]
}

def get_active_schema(db: Session | None=None) -> dict:
    if db is None:
        return DEFAULT_SCHEMA
    try:
        from ..models.app_settings import MetadataSchema
        s = db.query(MetadataSchema).filter(MetadataSchema.is_active==True).first()
        if s and s.schema_json:
            return s.schema_json
    except: pass
    return DEFAULT_SCHEMA

def validate_metadata(meta: dict[str,Any], schema: dict=DEFAULT_SCHEMA) -> list[dict]:
    errors=[]
    for req in schema.get("required",[]):
        if not meta.get(req):
            errors.append({"field":req,"msg":f"Отсутствует обязательное поле {req}","code":"ГОСТ 2.104"})
    for field, prop in schema.get("properties",{}).items():
        if "enum" in prop and meta.get(field) and meta[field] not in prop["enum"]:
            errors.append({"field":field,"msg":f"Недопустимое значение {meta[field]} для {field}","code":"schema"})
        if "pattern" in prop and meta.get(field):
            try:
                if not re.match(prop["pattern"], str(meta[field])):
                    errors.append({"field":field,"msg":f"Поле {field} не соответствует шаблону {prop['pattern']}","code":"schema"})
            except: pass
    return errors

def consistency_check(pages_meta: list[dict[str,Any]]) -> dict[str,Any]:
    if not pages_meta:
        return {"consistent": True, "issues":[]}
    base = pages_meta[0]
    issues=[]
    for i, meta in enumerate(pages_meta[1:], start=2):
        for key in ["Обозначение","Наименование","Литера"]:
            if base.get(key) and meta.get(key) and base[key]!=meta[key]:
                issues.append({
                    "type":"inconsistency",
                    "field":key,
                    "pages":[1,i],
                    "expected": base[key],
                    "got": meta[key],
                    "msg": f"Несоответствие {key}: на листе 1 '{base[key]}', на листе {i} '{meta[key]}'",
                    "code":"ГОСТ 2.104-консистентность",
                    "severity":"error"
                })
    return {"consistent": len(issues)==0, "issues": issues, "base": base}

def extract_all_technical_metadata(ocr_text: str, vlm_meta: dict, db: Session=None) -> dict[str,Any]:
    schema = get_active_schema(db)
    meta = dict(vlm_meta or {})
    patterns = {
        "Обозначение": r"Обозначение[:\s]*([A-ZА-Я0-9\.\-\s]+)",
        "Наименование": r"Наименование[:\s]*([A-Za-zА-Яа-я0-9\-\s]+)",
        "Материал": r"Материал[:\s]*([^\n]+)",
        "Масса": r"Масса[:\s]*([0-9\.,]+)",
        "Литера": r"Литера[:\s]*([A-ZА-Я0-9]+)",
    }
    for k, pat in patterns.items():
        if not meta.get(k):
            m = re.search(pat, ocr_text, re.IGNORECASE)
            if m:
                meta[k]=m.group(1).strip().split("\n")[0]
    kb = {
        "designation": meta.get("Обозначение"),
        "name": meta.get("Наименование"),
        "material": meta.get("Материал"),
        "mass": meta.get("Масса"),
        "litera": meta.get("Литера"),
        "scale": meta.get("Масштаб"),
        "format": meta.get("Формат"),
    }
    return {"metadata": meta, "kb": kb, "validation": validate_metadata(meta, schema), "schema": schema}

def create_or_update_schema(db: Session, name: str, schema_json: dict, title: str=None, make_active: bool=True, created_by: int=None):
    from ..models.app_settings import MetadataSchema
    existing = db.query(MetadataSchema).filter(MetadataSchema.name==name).first()
    if existing:
        existing.schema_json=schema_json
        if title: existing.title=title
        existing.is_active=make_active
    else:
        existing = MetadataSchema(name=name, title=title or name, schema_json=schema_json, is_active=make_active, created_by=created_by)
        db.add(existing)
    if make_active:
        # deactivate others
        for s in db.query(MetadataSchema).filter(MetadataSchema.name!=name).all():
            s.is_active=False
    db.commit()
    db.refresh(existing)
    return existing

def list_schemas(db: Session):
    from ..models.app_settings import MetadataSchema
    return db.query(MetadataSchema).order_by(MetadataSchema.created_at.desc()).all()
