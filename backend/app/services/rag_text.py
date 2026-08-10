from typing import List, Dict, Any, Optional
import re, os, logging
from ..vector_store import vector_store
from ..config import settings

logger = logging.getLogger(__name__)

# Heuristic GOST detection from OCR text
GOST_RE = re.compile(r"ГОСТ\s*\d+[\.\-]\d+(?:\-\d+)?", re.IGNORECASE)
STP_RE = re.compile(r"СТП\s+[\w\-]+", re.IGNORECASE)

def extract_gost_mentions(text: str) -> List[str]:
    return GOST_RE.findall(text) + STP_RE.findall(text)

class TextRAG:
    def __init__(self):
        self.vs = vector_store()
        self.collection = "gosts_text"

    def index_gost_chunk(self, gost_designation: str, title: str, chunk_text: str, chunk_id: str, meta: dict=None):
        vec = self.vs.embed_text(chunk_text)
        payload = {"designation": gost_designation, "title": title, "text": chunk_text, **(meta or {})}
        self.vs.upsert(self.collection, [{"id": chunk_id, "vector": vec, "payload": payload}])

    def search(self, query_text: str, top_k: int=5, filter: Optional[Dict]=None) -> List[Dict]:
        # Boost if GOST mentioned
        mentions = extract_gost_mentions(query_text)
        # For filtering by designation if high confidence
        qvec = self.vs.embed_text(query_text)
        hits = self.vs.search(self.collection, qvec, top_k=max(top_k*2, 10), filter=filter)
        # Re-rank: if payload designation matches mention, boost score strongly
        for h in hits:
            des = h["payload"].get("designation","")
            if any(des in m or m in des for m in mentions):
                h["score"] += 2.0  # strong boost to guarantee Hit Rate for explicit GOST mention
            # also token overlap boost (e.g., "2.307" substring)
            for m in mentions:
                # extract numeric part
                import re as _re
                nums = _re.findall(r"\d+\.\d+", m)
                if any(n in des for n in nums):
                    h["score"] += 1.0
        hits.sort(key=lambda x: x["score"], reverse=True)
        # Attach snippet
        for h in hits:
            txt = h["payload"].get("text","")
            h["snippet"] = txt[:400]
        return hits[:top_k]

    def ask(self, query: str, top_k: int=3) -> Dict[str,Any]:
        hits = self.search(query, top_k=top_k)
        # Build prompt context for VLM/LLM (not calling LLM here, return context)
        context = "\n\n".join([f"[{h['payload'].get('designation')}] {h['snippet']}" for h in hits])
        return {"query": query, "hits": hits, "context": context, "mentions": extract_gost_mentions(query)}

    def ingest_gost_file(self, filepath: str, designation: str=None, title: str=None) -> Dict[str,Any]:
        # Extract text via pypdf or ocr fallback
        text=""
        try:
            import fitz
            doc = fitz.open(filepath)
            text = "\n".join([p.get_text() for p in doc])
        except:
            try:
                import PyPDF2
                import pathlib
                reader = PyPDF2.PdfReader(filepath)
                text = "\n".join([p.extract_text() or "" for p in reader.pages])
            except Exception as e:
                logger.warning(f"pdf extract fail {filepath}: {e}")
                text = open(filepath, errors="ignore").read() if os.path.exists(filepath) else ""
        if not text.strip():
            text = f"ГОСТ документ {os.path.basename(filepath)}"
        # Naive chunking 600 chars overlap 100
        chunks=[]
        chunk_size=800
        overlap=120
        for i in range(0, len(text), chunk_size-overlap):
            chunk=text[i:i+chunk_size]
            if len(chunk.strip())<50: continue
            chunks.append(chunk)
        # Derive designation from filename if not given
        if not designation:
            m = GOST_RE.search(os.path.basename(filepath))
            designation = m.group(0) if m else os.path.splitext(os.path.basename(filepath))[0]
        if not title:
            title = designation
        for idx, ch in enumerate(chunks):
            cid = f"{designation.replace(' ','_')}_{idx}"
            self.index_gost_chunk(designation, title, ch, cid, meta={"filepath":filepath, "chunk_idx": idx})
        return {"designation": designation, "chunks": len(chunks), "filepath": filepath}

text_rag = TextRAG()
