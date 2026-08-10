from typing import List, Dict, Any, Optional
import os, logging
from ..vector_store import vector_store
from ..config import settings

logger = logging.getLogger(__name__)

class VisualRAG:
    def __init__(self):
        self.vs = vector_store()
        self.collection = "gallery_visual"

    def index_gallery_item(self, item_id: str, image_path: str, payload: Dict):
        vec = self.vs.embed_image(image_path)
        self.vs.upsert(self.collection, [{"id": item_id, "vector": vec, "payload": payload}])

    def search(self, query_image_path: str, top_k: int=5, threshold: float=0.75) -> List[Dict]:
        qvec = self.vs.embed_image(query_image_path)
        hits = self.vs.search(self.collection, qvec, top_k=top_k)
        # add similarity percent and threshold filter
        out=[]
        for h in hits:
            sim = h["score"]
            # cosine in [-1..1], map to 0..1 for percent
            percent = max(0, min(1, (sim+1)/2))*100 if sim<=1 else sim*100
            # fallback our mock cosine returns 0..1 already
            if sim>1: percent=sim*100
            # our memory store already  -0.5..1 shifted, but treat as 0..1
            # Normalize if our hash: already 0..1
            h["similarity"] = float(sim)
            h["similarity_percent"] = float(round(percent,1))
            h["is_error_pattern"] = h["payload"].get("category")=="error" or "ошибка" in h["payload"].get("title","").lower()
            # Only keep above threshold OR keep top1 for hint
            out.append(h)
        # sort
        out.sort(key=lambda x: x["similarity"], reverse=True)
        # Return top_k, caller decides threshold
        return out

    def hint_for_vlm(self, query_image_path: str) -> Optional[str]:
        hits = self.search(query_image_path, top_k=3)
        if not hits:
            return None
        top = hits[0]
        if top["similarity"] > 0.82:  # high threshold
            err = top["payload"].get("error_type") or top["payload"].get("title") or "неизвестная ошибка"
            return f"Данный элемент на {top['similarity_percent']:.0f}% похож на ошибку типа '{err}' из базы (эталон: {top['payload'].get('gost_ref','')}). Проверь соответствие {top['payload'].get('gost_ref','ГОСТ')}."
        elif top["similarity"] > 0.75:
            return f"Похож на паттерн '{top['payload'].get('title')}' ({top['similarity_percent']:.0f}% близость). Рекомендуется проверка."
        return None

visual_rag = VisualRAG()
