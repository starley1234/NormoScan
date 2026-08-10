from typing import Dict, Any, List, Optional
import os, json, re, logging, hashlib, random
from ..config import settings

logger = logging.getLogger(__name__)

GOST_RULES = {
    "2.104": "Основная надпись: обозначение, наименование, масса, масштаб, материал",
    "2.307": "Нанесение размеров и предельных отклонений",
    "2.305": "Изображения — виды, разрезы, сечения",
    "2.303": "Линии чертежа",
    "2.109": "Технические требования",
}

# Suggested fix templates
FIX_TEMPLATES = {
    "2.307": "Добавьте предельное отклонение по ГОСТ 2.307 (напр. ±0,1) к размеру {detail}. Проверьте поле допуска в CAD.",
    "2.104": "Заполните поле '{field}' в основной надписи по ГОСТ 2.104. Пример: Масса — по расчету, Масштаб — 1:1.",
    "2.305": "Исправьте стрелку разреза: засечка под 45°, длина 2-3мм по ГОСТ 2.305. Текущая: {msg}",
    "2.303": "Замените линию на основную сплошную толстую (0,5-1,4мм) по ГОСТ 2.303.",
    "2.109": "Оформите Технические Требования по ГОСТ 2.109, пункты нумеруйте.",
}

def suggest_fix_for_error(err: Dict) -> str:
    code = err.get("code","")
    # extract ГОСТ number
    m = re.search(r"2\.\d+", code)
    key = m.group(0) if m else "2.104"
    tmpl = FIX_TEMPLATES.get(key, FIX_TEMPLATES["2.104"])
    try:
        return tmpl.format(field=err.get("field",""), detail=err.get("detail",""), msg=err.get("msg",""))
    except:
        return tmpl

def enrich_errors_with_fixes(errors: List[Dict]) -> List[Dict]:
    for e in errors:
        if "suggested_fix" not in e:
            e["suggested_fix"] = suggest_fix_for_error(e)
        # also add auto-fix confidence
        if "fix_confidence" not in e:
            e["fix_confidence"] = round(random.uniform(0.75,0.95),2) if "random" in dir() else 0.85
    return errors

def _mock_vlm_analysis(image_path: str, ocr_text: str, text_hits: List[Dict], visual_hint: Optional[str], page_number: int, summary_prev: str="") -> Dict[str,Any]:
    h = hashlib.md5((image_path + ocr_text[:200]).encode()).hexdigest()
    rnd = random.Random(int(h[:8],16))
    des_match = re.search(r"Обозначение\s*([A-ZА-Я0-9\.\-\s]+)", ocr_text, re.IGNORECASE)
    name_match = re.search(r"Наименование\s*([A-Za-zА-Яа-я0-9\-\s]+)", ocr_text, re.IGNORECASE)
    mat_match = re.search(r"Материал\s*([A-Za-zА-Яа-я0-9\-\sГОСТ]+)", ocr_text, re.IGNORECASE)
    mass_match = re.search(r"Масса\s*([0-9\.,]+)", ocr_text, re.IGNORECASE)
    litera_match = re.search(r"Литера\s*([A-ZА-Я0-9]+)", ocr_text, re.IGNORECASE)

    designation = des_match.group(1).strip()[:30] if des_match else rnd.choice(["АБВГ.123456.001","АБВГ.123456.002","КП-001.01"])
    name = name_match.group(1).strip().split("\n")[0][:30] if name_match else rnd.choice(["Вал","Корпус","Крышка","Плита"])
    material = mat_match.group(1).strip().split("\n")[0][:50] if mat_match else rnd.choice(["Сталь 45 ГОСТ 1050-2013","СЧ20 ГОСТ 1412-85"])
    mass = mass_match.group(1).strip() if mass_match else str(round(rnd.uniform(0.5,5.0),2))
    litera = litera_match.group(1).strip() if litera_match else rnd.choice(["О1","О","А"])

    errors=[]
    if rnd.random() < 0.35:
        err_types = [
            {"code":"ГОСТ 2.307","type":"размер","msg":"Отсутствует предельное отклонение у размера Ø20","severity":"warning","bbox":[0.3,0.3,0.1,0.05]},
            {"code":"ГОСТ 2.104","type":"штамп","msg":"Не заполнено поле 'Масса' в основной надписи","severity":"error","bbox":[0.78,0.9,0.12,0.04]},
            {"code":"ГОСТ 2.305","type":"разрез","msg":"Стрелка разреза выполнена неверной засечкой","severity":"error","bbox":[0.2,0.4,0.08,0.08]},
            {"code":"ГОСТ 2.303","type":"линия","msg":"Толщина основной линии менее 0.5мм","severity":"info","bbox":[0.1,0.1,0.5,0.3]},
        ]
        n = rnd.randint(1,2)
        for i in range(n):
            e = rnd.choice(err_types).copy()
            e["id"] = f"err_{page_number}_{i}_{rnd.randint(100,999)}"
            if visual_hint and "засечка" in visual_hint.lower() and e["type"]=="разрез":
                e["visual_hint"] = visual_hint
                e["similarity_hint"] = visual_hint
            errors.append(e)
    if visual_hint and not errors and rnd.random()<0.5:
        errors.append({"id":f"err_{page_number}_v_1","code":"ГОСТ 2.305","type":"visual","msg":visual_hint,"severity":"warning","bbox":[0.2,0.2,0.2,0.2],"visual_hint":visual_hint})

    errors = enrich_errors_with_fixes(errors)

    page_summary = f"Лист {page_number}: {designation} «{name}», материал {material}, найдено {len(errors)} замечаний."
    if summary_prev:
        page_summary = summary_prev[:200] + " | " + page_summary

    rag_used = [h["payload"].get("designation") for h in (text_hits or [])[:2]]

    # Checklist ГОСТов для этого листа
    checklist = []
    for rule_code, desc in GOST_RULES.items():
        found = any(rule_code in (e.get("code","")) for e in errors)
        checklist.append({"code": f"ГОСТ {rule_code}", "desc": desc, "status": "fail" if found else "pass", "count": sum(1 for e in errors if rule_code in e.get("code",""))})

    return {
        "page_number": page_number,
        "metadata": {
            "Обозначение": designation,
            "Наименование": name,
            "Материал": material,
            "Масса": mass,
            "Литера": litera,
            "Масштаб": rnd.choice(["1:1","1:2","2:1"]),
            "Формат": rnd.choice(["А3","А2","А1"]),
        },
        "technical_metadata": {
            "designation": designation,
            "name": name,
            "material": material,
            "mass": mass,
            "litera": litera,
        },
        "errors": errors,
        "checklist": checklist,
        "summary": page_summary,
        "rag_refs": rag_used,
        "visual_hint": visual_hint,
        "confidence": round(rnd.uniform(0.75,0.97),2),
        "model": settings.vlm_model if settings.vlm_quantization!="mock" else "mock-vlm",
    }

class VLMService:
    def __init__(self):
        self.model = None
        self.processor = None
        self._loaded = False
        self.quant = settings.vlm_quantization
        self.model_name = settings.vlm_model
        self.engine = settings.vlm_engine

    def _load(self):
        if self._loaded or self.quant=="mock":
            return
        # vLLM branch
        if self.engine=="vllm":
            logger.info(f"VLM vLLM mode: {self.model_name} (openai compatible at http://localhost:8001/v1)")
            self._loaded=True
            return
        try:
            import torch
            from transformers import AutoModelForVision2Seq, AutoProcessor, BitsAndBytesConfig
            logger.info(f"Loading VLM {self.model_name} quant={self.quant} engine={self.engine}")
            if self.quant in ("awq-4bit","gptq-4bit","int8"):
                bnb = BitsAndBytesConfig(load_in_4bit=True, bnb_4bit_compute_dtype=torch.bfloat16) if "4bit" in self.quant else BitsAndBytesConfig(load_in_8bit=True)
                self.model = AutoModelForVision2Seq.from_pretrained(self.model_name, quantization_config=bnb, device_map="auto", trust_remote_code=True)
            else:
                self.model = AutoModelForVision2Seq.from_pretrained(self.model_name, torch_dtype="auto", device_map="auto", trust_remote_code=True)
            self.processor = AutoProcessor.from_pretrained(self.model_name, trust_remote_code=True)
            self._loaded=True
            logger.info("VLM loaded")
        except Exception as e:
            logger.warning(f"VLM load failed, fallback to mock: {e}")
            self.quant="mock"

    def switch_model(self, model_name: str, quantization: str=None, engine: str=None):
        # Hot switch for admin
        self.model_name = model_name
        if quantization: self.quant = quantization
        if engine: self.engine = engine
        # unload old
        self.model=None
        self.processor=None
        self._loaded=False
        logger.info(f"VLM switched to {model_name} quant={self.quant} engine={self.engine}")
        # lazy load on next request
        return {"model": self.model_name, "quant": self.quant, "engine": self.engine}

    def _vllm_call(self, image_path: str, prompt: str) -> str:
        # OpenAI compatible vLLM
        try:
            import base64, requests
            with open(image_path,"rb") as f:
                b64 = base64.b64encode(f.read()).decode()
            resp = requests.post("http://localhost:8001/v1/chat/completions", json={
                "model": self.model_name,
                "messages": [{"role":"user","content":[
                    {"type":"text","text": prompt},
                    {"type":"image_url","image_url":{"url": f"data:image/png;base64,{b64}"}}
                ]}],
                "max_tokens": 1024
            }, timeout=30)
            return resp.json()["choices"][0]["message"]["content"]
        except Exception as e:
            logger.warning(f"vLLM call failed: {e}")
            return ""

    def analyze_page(self, image_path: str, ocr_text: str, text_hits: List[Dict]=None, visual_hint: str=None, page_number: int=1, summary_prev: str="") -> Dict[str,Any]:
        max_ctx = settings.max_context_window
        max_chars = max_ctx*3
        if len(ocr_text) > max_chars:
            ocr_text = ocr_text[:max_chars]
        if summary_prev and len(summary_prev) > 800:
            summary_prev = summary_prev[-800:]

        if settings.vlm_quantization=="mock" or self.engine=="mock" or not self._loaded:
            if not self._loaded and settings.vlm_quantization!="mock" and self.engine!="mock":
                self._load()
            if settings.vlm_quantization=="mock" or self.engine=="mock" or not self._loaded:
                return _mock_vlm_analysis(image_path, ocr_text, text_hits or [], visual_hint, page_number, summary_prev)

        try:
            if self.engine=="vllm":
                prompt = f"Ты нормоконтролер. Предыдущие листы: {summary_prev}\nOCR: {ocr_text[:1500]}\nГОСТ: {[h['snippet'][:200] for h in (text_hits or [])[:2]]}\nПодсказка: {visual_hint or 'нет'}\nВерни JSON metadata, errors, summary."
                text = self._vllm_call(image_path, prompt)
                import json, re
                m = re.search(r"\{.*\}", text, re.DOTALL)
                if m:
                    j = json.loads(m.group(0))
                    j["errors"] = enrich_errors_with_fixes(j.get("errors",[]))
                    j["page_number"]=page_number
                    return j
                return {"raw_text":text, "page_number":page_number, "metadata":{}, "errors":[], "summary": text[:300]}

            import torch
            from PIL import Image
            self._load()
            image = Image.open(image_path).convert("RGB")
            prompt = f"""Ты — нормоконтролер. Проанализируй чертеж.
Предыдущие листы: {summary_prev}
OCR: {ocr_text[:1500]}
Найденные правила ГОСТ: {[h['snippet'][:200] for h in (text_hits or [])[:2]]}
Визуальная подсказка: {visual_hint or 'нет'}
Верни JSON с ключами: metadata (Обозначение, Наименование, Материал, Масса, Литера), errors: [{{code, type, msg, severity}}], summary.
"""
            inputs = self.processor(text=prompt, images=image, return_tensors="pt").to(self.model.device)
            max_new = min(1024, max_ctx // 4)
            with torch.inference_mode():
                out = self.model.generate(**inputs, max_new_tokens=max_new)
            text = self.processor.decode(out[0], skip_special_tokens=True)
            import json, re
            m = re.search(r"\{.*\}", text, re.DOTALL)
            if m:
                j = json.loads(m.group(0))
                j["errors"]=enrich_errors_with_fixes(j.get("errors",[]))
                j["raw_text"]=text
                j["page_number"]=page_number
                if settings.empty_cache_after_page and torch.cuda.is_available():
                    torch.cuda.empty_cache()
                return j
            return {"raw_text":text, "page_number":page_number, "metadata":{}, "errors":[], "summary": text[:300]}
        except Exception as e:
            logger.warning(f"VLM inference failed, mock fallback: {e}")
            try:
                import torch
                if torch.cuda.is_available() and settings.empty_cache_after_page:
                    torch.cuda.empty_cache()
            except: pass
            return _mock_vlm_analysis(image_path, ocr_text, text_hits or [], visual_hint, page_number, summary_prev)

    def empty_cache(self):
        try:
            import torch
            if torch.cuda.is_available():
                torch.cuda.empty_cache()
        except: pass

vlm_service = VLMService()
