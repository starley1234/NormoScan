import uuid, hashlib, math
from typing import List, Dict, Any, Tuple, Optional
import numpy as np
from .config import settings
import logging

logger = logging.getLogger(__name__)

def _hash_embedding(text: str, dim: int = 384) -> List[float]:
    # Deterministic mock embedding for dev/tests; replace with sentence-transformers in prod
    h = hashlib.sha256(text.encode()).digest()
    # expand to dim via lặp
    vals = []
    for i in range(dim):
        vals.append( ((h[i % len(h)] + i*31) % 256) / 255.0 - 0.5 )
    # normalize
    norm = math.sqrt(sum(v*v for v in vals)) or 1
    return [v/norm for v in vals]

def cosine(a: List[float], b: List[float]) -> float:
    return float(np.dot(a,b) / (np.linalg.norm(a)*np.linalg.norm(b) + 1e-9))

class BaseVectorStore:
    def upsert(self, collection: str, points: List[Dict]): raise NotImplementedError
    def search(self, collection: str, query_vector: List[float], top_k: int =5, filter: Optional[Dict]=None) -> List[Dict]: raise NotImplementedError
    def embed_text(self, text: str) -> List[float]: raise NotImplementedError
    def embed_image(self, image_path: str) -> List[float]: raise NotImplementedError

class MemoryVectorStore(BaseVectorStore):
    def __init__(self):
        self.store: Dict[str, List[Dict]] = {}
        self.dim = 384

    def embed_text(self, text: str) -> List[float]:
        try:
            from sentence_transformers import SentenceTransformer
            # lazy load only if available and not mock
            if settings.vector_db != "memory":
                m = SentenceTransformer("sentence-transformers/all-MiniLM-L6-v2")
                return m.encode(text).tolist()
        except Exception as e:
            logger.debug(f"fallback hash embedding: {e}")
        return _hash_embedding(text, self.dim)

    def embed_image(self, image_path: str) -> List[float]:
        # Use hash of path + file bytes if exists
        try:
            with open(image_path,"rb") as f:
                data = f.read(2048)
            return _hash_embedding(data.hex()[:500], self.dim)
        except:
            return _hash_embedding(image_path, self.dim)

    def upsert(self, collection: str, points: List[Dict]):
        if collection not in self.store:
            self.store[collection]=[]
        # replace by id
        existing = {p["id"]:p for p in self.store[collection]}
        for p in points:
            existing[p["id"]] = p
        self.store[collection] = list(existing.values())

    def search(self, collection: str, query_vector: List[float], top_k: int=5, filter: Optional[Dict]=None) -> List[Dict]:
        pts = self.store.get(collection, [])
        scored=[]
        for p in pts:
            if filter:
                # simple dict match
                ok=True
                for k,v in filter.items():
                    if p.get("payload",{}).get(k)!=v:
                        ok=False;break
                if not ok: continue
            score = cosine(query_vector, p["vector"])
            scored.append({"id":p["id"],"score":score,"payload":p.get("payload",{})})
        scored.sort(key=lambda x: x["score"], reverse=True)
        return scored[:top_k]

class QdrantVectorStore(BaseVectorStore):
    def __init__(self):
        from qdrant_client import QdrantClient
        from qdrant_client.http.models import Distance, VectorParams, PointStruct
        self.client = QdrantClient(url=settings.qdrant_url, api_key=settings.qdrant_api_key)
        self.dim = 384
        self._PointStruct = PointStruct
        self._Distance = Distance
        self._VectorParams = VectorParams
        self.fallback = MemoryVectorStore()
        self._checked = False

    def _ensure_collection(self, name: str):
        try:
            cols = [c.name for c in self.client.get_collections().collections]
            if name not in cols:
                self.client.create_collection(collection_name=name, vectors_config=self._VectorParams(size=self.dim, distance=self._Distance.COSINE))
        except Exception as e:
            logger.warning(f"Qdrant ensure failed, fallback to memory: {e}")
            raise

    def embed_text(self, text: str) -> List[float]:
        return self.fallback.embed_text(text)
    def embed_image(self, image_path: str) -> List[float]:
        return self.fallback.embed_image(image_path)

    def upsert(self, collection: str, points: List[Dict]):
        try:
            self._ensure_collection(collection)
            qpoints=[]
            for p in points:
                qpoints.append(self._PointStruct(id=str(p["id"]), vector=p["vector"], payload=p.get("payload",{})))
            self.client.upsert(collection_name=collection, points=qpoints)
        except Exception as e:
            logger.warning(f"Qdrant upsert failed, using memory fallback: {e}")
            self.fallback.upsert(collection, points)

    def search(self, collection: str, query_vector: List[float], top_k: int=5, filter: Optional[Dict]=None) -> List[Dict]:
        try:
            self._ensure_collection(collection)
            # Qdrant filter not implemented for brevity
            res = self.client.search(collection_name=collection, query_vector=query_vector, limit=top_k)
            return [{"id":r.id,"score":r.score,"payload":r.payload} for r in res]
        except Exception as e:
            logger.warning(f"Qdrant search fallback: {e}")
            return self.fallback.search(collection, query_vector, top_k, filter)

def get_vector_store() -> BaseVectorStore:
    if settings.vector_db == "qdrant":
        try:
            return QdrantVectorStore()
        except Exception:
            return MemoryVectorStore()
    elif settings.vector_db == "milvus":
        # Milvus similar; for now fallback
        return MemoryVectorStore()
    else:
        return MemoryVectorStore()

# singleton
_vector_store: Optional[BaseVectorStore] = None
def vector_store() -> BaseVectorStore:
    global _vector_store
    if _vector_store is None:
        _vector_store = get_vector_store()
    return _vector_store

# Helpers for app
def ensure_collections():
    vs = vector_store()
    for coll in ["gosts_text","gallery_visual","checks_meta"]:
        try:
            vs.upsert(coll, [])
        except: pass
