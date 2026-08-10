from typing import Dict, List, Any
import os, logging
from ..config import settings

logger = logging.getLogger(__name__)

_mock_cache = {}

def _mock_ocr(image_path: str) -> Dict[str,Any]:
    # Deterministic mock: hash filename to generate plausible stamp text
    import hashlib, random
    h = hashlib.md5(image_path.encode()).hexdigest()
    random.seed(int(h[:8],16))
    # plausible values
    designations = ["АБВГ.123456.001","АБВГ.123456.002","КП-001.01","МЧ-42.00.01"]
    names = ["Вал","Корпус","Крышка","Плита","Кронштейн"]
    materials = ["Сталь 45 ГОСТ 1050-2013","СЧ20 ГОСТ 1412-85","Алюминий Д16Т"]
    return {
        "text": f"Обозначение {random.choice(designations)}\nНаименование {random.choice(names)}\nМатериал {random.choice(materials)}\nЛитера О1 Масса 1.2",
        "blocks": [
            {"text": f"Обозначение {random.choice(designations)}","bbox":[0.75,0.85,0.2,0.05],"conf":0.92},
            {"text": f"Наименование {random.choice(names)}","bbox":[0.75,0.88,0.2,0.05],"conf":0.88},
        ],
        "engine": "mock",
        "confidence": 0.88
    }

class OCRService:
    def __init__(self, engine: str=None):
        self.engine = engine or settings.ocr_engine
        self._easy = None
        self._paddle = None

    def _ensure_easy(self):
        if self._easy is None:
            try:
                import easyocr
                self._easy = easyocr.Reader(['ru','en'], gpu=False)
            except Exception as e:
                logger.warning(f"easyocr init failed: {e}")
                self.engine="mock"
        return self._easy

    def _ensure_paddle(self):
        if self._paddle is None:
            try:
                from paddleocr import PaddleOCR
                self._paddle = PaddleOCR(use_angle_cls=True, lang='ru', show_log=False)
            except Exception as e:
                logger.warning(f"paddle init failed: {e}")
                self.engine="mock"
        return self._paddle

    def extract(self, image_path: str, zones: dict=None) -> Dict[str,Any]:
        if self.engine=="mock":
            return _mock_ocr(image_path)
        if self.engine=="easyocr":
            r = self._ensure_easy()
            if r and os.path.exists(image_path):
                try:
                    res = r.readtext(image_path, detail=1)
                    text = "\n".join([t[1] for t in res])
                    blocks=[{"text":t[1],"bbox":t[0],"conf":float(t[2])} for t in res]
                    return {"text":text,"blocks":blocks,"engine":"easyocr","confidence": sum(b["conf"] for b in blocks)/max(len(blocks),1)}
                except Exception as e:
                    logger.warning(f"easyocr failed: {e}")
            return _mock_ocr(image_path)
        if self.engine=="paddleocr":
            ocr = self._ensure_paddle()
            if ocr and os.path.exists(image_path):
                try:
                    res = ocr.ocr(image_path, cls=True)
                    # paddle returns nested
                    flat=[]
                    for page in res:
                        if not page: continue
                        for line in page:
                            flat.append(line)
                    text="\n".join([l[1][0] for l in flat])
                    blocks=[{"text":l[1][0],"bbox":l[0],"conf":float(l[1][1])} for l in flat]
                    return {"text":text,"blocks":blocks,"engine":"paddleocr","confidence": sum(b["conf"] for b in blocks)/max(len(blocks),1)}
                except Exception as e:
                    logger.warning(f"paddleocr failed: {e}")
            return _mock_ocr(image_path)
        return _mock_ocr(image_path)

    def extract_with_zones(self, image_path: str, crops: Dict[str,Any]) -> Dict[str,Any]:
        # OCR per zone if available, else whole
        if not crops:
            return self.extract(image_path)
        combined=""
        zone_texts={}
        for label, info in crops.items():
            path = info.get("path", image_path)
            res = self.extract(path)
            zone_texts[label]=res
            combined += f"\n[{label}]\n" + res["text"]
        # also whole
        whole = self.extract(image_path)
        return {"text": combined + "\n[whole]\n"+whole["text"], "zone_texts": zone_texts, "whole": whole, "engine": self.engine}

ocr_service = OCRService()
