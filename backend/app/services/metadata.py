from typing import Dict, Any, List
import re

# JSON schema for metadata (настраиваемый шаблон)
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

def validate_metadata(meta: Dict[str,Any], schema: Dict=DEFAULT_SCHEMA) -> List[Dict]:
    errors=[]
    for req in schema.get("required",[]):
        if not meta.get(req):
            errors.append({"field":req,"msg":f"Отсутствует обязательное поле {req}","code":"ГОСТ 2.104"})
    # simple enum check
    for field, prop in schema.get("properties",{}).items():
        if "enum" in prop and meta.get(field) and meta[field] not in prop["enum"]:
            errors.append({"field":field,"msg":f"Недопустимое значение {meta[field]} для {field}","code":"schema"})
    return errors

def consistency_check(pages_meta: List[Dict[str,Any]]) -> Dict[str,Any]:
    """Сверка метаданных между листами одного комплекта"""
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

def extract_all_technical_metadata(ocr_text: str, vlm_meta: Dict) -> Dict[str,Any]:
    # Merge OCR + VLM, plus extra fields
    meta = dict(vlm_meta or {})
    # Try to enrich from OCR
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
    # Knowledge base fields
    kb = {
        "designation": meta.get("Обозначение"),
        "name": meta.get("Наименование"),
        "material": meta.get("Материал"),
        "mass": meta.get("Масса"),
        "litera": meta.get("Литера"),
        "scale": meta.get("Масштаб"),
        "format": meta.get("Формат"),
    }
    return {"metadata": meta, "kb": kb, "validation": validate_metadata(meta)}
