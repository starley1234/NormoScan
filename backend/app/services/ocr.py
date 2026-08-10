import logging
import os
from typing import Any

from ..config import settings

logger = logging.getLogger(__name__)

def _mock_ocr(image_path: str) -> dict[str,Any]:
    import hashlib
    import random
    h = hashlib.md5(image_path.encode()).hexdigest()
    random.seed(int(h[:8],16))
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
        self.ensemble = settings.ocr_ensemble
        self.threshold = settings.ocr_fallback_threshold
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

    def _extract_easy(self, image_path: str) -> dict[str,Any]:
        r = self._ensure_easy()
        if r and os.path.exists(image_path):
            try:
                res = r.readtext(image_path, detail=1)
                text = "\n".join([t[1] for t in res])
                blocks=[{"text":t[1],"bbox":t[0],"conf":float(t[2])} for t in res]
                conf = sum(b["conf"] for b in blocks)/max(len(blocks),1) if blocks else 0
                return {"text":text,"blocks":blocks,"engine":"easyocr","confidence": conf}
            except Exception as e:
                logger.warning(f"easyocr failed: {e}")
        return None

    def _extract_paddle(self, image_path: str) -> dict[str,Any]:
        ocr = self._ensure_paddle()
        if ocr and os.path.exists(image_path):
            try:
                res = ocr.ocr(image_path, cls=True)
                flat=[]
                for page in res:
                    if not page: continue
                    for line in page:
                        flat.append(line)
                text="\n".join([l[1][0] for l in flat])
                blocks=[{"text":l[1][0],"bbox":l[0],"conf":float(l[1][1])} for l in flat]
                conf = sum(b["conf"] for b in blocks)/max(len(blocks),1) if blocks else 0
                return {"text":text,"blocks":blocks,"engine":"paddleocr","confidence": conf}
            except Exception as e:
                logger.warning(f"paddleocr failed: {e}")
        return None

    def extract(self, image_path: str, zones: dict=None) -> dict[str,Any]:
        # Ensemble logic
        if self.engine=="mock":
            return _mock_ocr(image_path)
        primary = None
        if self.engine=="easyocr":
            primary = self._extract_easy(image_path)
        elif self.engine=="paddleocr":
            primary = self._extract_paddle(image_path)
        else:
            primary = _mock_ocr(image_path)
            primary["engine"]="mock"

        if primary is None:
            return _mock_ocr(image_path)

        # If ensemble and low confidence, try secondary
        if self.ensemble and primary.get("confidence",0) < self.threshold:
            secondary = None
            if self.engine=="easyocr":
                secondary = self._extract_paddle(image_path)
            elif self.engine=="paddleocr":
                secondary = self._extract_easy(image_path)
            if secondary and secondary.get("confidence",0) > primary.get("confidence",0):
                # Merge: prefer secondary text but keep both
                merged_text = secondary["text"] + "\n[fallback_primary]\n" + primary["text"]
                return {"text": merged_text, "blocks": secondary["blocks"], "engine": secondary["engine"]+"+fallback", "confidence": secondary["confidence"], "primary": primary, "secondary": secondary}
        return primary

    def extract_with_zones(self, image_path: str, crops: dict[str,Any]) -> dict[str,Any]:
        if not crops:
            res = self.extract(image_path)
            return {"text": res["text"], "zone_texts": {"whole": res}, "whole": res, "engine": res["engine"], "confidence": res.get("confidence",0)}
        combined=""
        zone_texts={}
        confidences=[]
        for label, info in crops.items():
            path = info.get("path", image_path)
            res = self.extract(path)
            zone_texts[label]=res
            confidences.append(res.get("confidence",0))
            combined += f"\n[{label}]\n" + res["text"]
        whole = self.extract(image_path)
        confidences.append(whole.get("confidence",0))
        avg_conf = sum(confidences)/len(confidences) if confidences else 0
        return {"text": combined + "\n[whole]\n"+whole["text"], "zone_texts": zone_texts, "whole": whole, "engine": self.engine + ("+ensemble" if self.ensemble else ""), "confidence": avg_conf}

ocr_service = OCRService()
