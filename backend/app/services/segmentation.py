import os, cv2, json
from typing import Dict, List, Tuple, Any
from PIL import Image
import numpy as np
import logging

logger = logging.getLogger(__name__)

# Zones defined per ГОСТ 2.104 (основная надпись 185x55 etc)
ZONE_LABELS = ["stamp", "tech_requirements", "specification", "graphic_views", "title_block"]

def detect_zones_heuristic(image_path: str) -> Dict[str, Any]:
    """
    Интеллектуальный кроп эвристикой + OpenCV:
      - stamp: правый нижний угол ~185x55mm пропорция
      - tech_requirements: левая нижняя или правая верхняя текстовая зона
      - graphic_views: центр
    Возвращает dict зон с bbox [x,y,w,h] в относительных координатах 0..1
    """
    try:
        im = cv2.imread(image_path)
        if im is None:
            raise FileNotFoundError(image_path)
        h,w,_ = im.shape
        gray = cv2.cvtColor(im, cv2.COLOR_BGR2GRAY)
        # threshold to find rectangles
        _, th = cv2.threshold(gray, 200, 255, cv2.THRESH_BINARY_INV)
        contours, _ = cv2.findContours(th, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
        # sort by area
        contours = sorted(contours, key=cv2.contourArea, reverse=True)[:10]
        # Heuristic zones
        zones = {}
        # stamp: bottom-right, ~ 25% width, ~ 12% height
        zones["stamp"] = {"bbox":[0.73, 0.82, 0.26, 0.17], "confidence":0.85, "method":"heuristic"}
        zones["tech_requirements"] = {"bbox":[0.03, 0.60, 0.45, 0.22], "confidence":0.70, "method":"heuristic"}
        zones["specification"] = {"bbox":[0.52, 0.05, 0.45, 0.35], "confidence":0.65, "method":"heuristic"}
        zones["graphic_views"] = {"bbox":[0.05, 0.05, 0.90, 0.55], "confidence":0.80, "method":"heuristic"}

        # If we found large rectangles, refine stamp position
        for cnt in contours:
            x,y,cw,ch = cv2.boundingRect(cnt)
            rel = [x/w, y/h, cw/w, ch/h]
            area = cw*ch/(w*h)
            # stamp candidate: aspect ~3.36 (185/55) and bottom-right
            if 2.5 < cw/max(ch,1) < 4.5 and rel[0] > 0.6 and rel[1] > 0.7 and 0.02 < area < 0.08:
                zones["stamp"] = {"bbox":rel, "confidence":0.92, "method":"contour"}
                break
        return zones
    except Exception as e:
        logger.warning(f"segmentation fallback: {e}")
        return {
            "stamp": {"bbox":[0.73,0.82,0.26,0.17],"confidence":0.5,"method":"fallback"},
            "tech_requirements":{"bbox":[0.03,0.60,0.45,0.22],"confidence":0.5,"method":"fallback"},
            "graphic_views":{"bbox":[0.05,0.05,0.90,0.55],"confidence":0.5,"method":"fallback"},
        }

def crop_zone(image_path: str, bbox: List[float], out_path: str) -> str:
    im = Image.open(image_path)
    w,h = im.size
    x,y,bw,bh = bbox
    left = int(x*w); upper = int(y*h); right = int((x+bw)*w); lower = int((y+bh)*h)
    # clamp
    left, upper = max(0,left), max(0,upper)
    right, lower = min(w,right), min(h,lower)
    crop = im.crop((left,upper,right,lower))
    os.makedirs(os.path.dirname(out_path), exist_ok=True)
    crop.save(out_path)
    return out_path

def segment_page(image_path: str, check_id: int, page_number: int) -> Dict[str,Any]:
    zones = detect_zones_heuristic(image_path)
    base = os.path.splitext(image_path)[0]
    crops={}
    for label, info in zones.items():
        out = f"{base}_crop_{label}.png"
        try:
            crop_zone(image_path, info["bbox"], out)
            crops[label]= {"path": out, "bbox": info["bbox"], "confidence": info["confidence"]}
        except Exception as e:
            logger.warning(f"crop failed {label}: {e}")
    return {"zones": zones, "crops": crops}

def batch_segment(pages: List[Dict]) -> List[Dict]:
    # pages from preprocessing
    results=[]
    for p in pages:
        seg = segment_page(p["image_path"], 0, p["page_number"])
        results.append({**p, **seg})
    return results
