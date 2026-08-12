import collections
import logging
import math
import os
import re
from typing import Any

from ..vector_store import vector_store

logger = logging.getLogger(__name__)

GOST_RE = re.compile(r"ГОСТ\s*\d+[\.\-]\d+(?:\-\d+)?", re.IGNORECASE)
STP_RE = re.compile(r"СТП\s+[\w\-]+", re.IGNORECASE)

def extract_gost_mentions(text: str) -> list[str]:
    return GOST_RE.findall(text) + STP_RE.findall(text)

# --- BM25 (lightweight, без внешних зависимостей) ---
class BM25Index:
    def __init__(self, k1=1.5, b=0.75):
        self.k1=k1; self.b=b
        self.docs: list[dict]=[]  # {id, text, tokens, payload}
        self.df: dict[str,int]=collections.Counter()
        self.N=0
        self.avgdl=0

    def tokenize(self, text:str):
        return re.findall(r"[а-яa-z0-9]+", text.lower())

    def add(self, doc_id:str, text:str, payload:dict):
        toks=self.tokenize(text)
        self.docs.append({"id":doc_id,"text":text,"tokens":toks,"payload":payload})
        for t in set(toks):
            self.df[t]+=1
        self.N=len(self.docs)
        self.avgdl=sum(len(d["tokens"]) for d in self.docs)/self.N if self.N else 0

    def score(self, query:str):
        q_toks=self.tokenize(query)
        scores=[]
        for d in self.docs:
            s=0
            dl=len(d["tokens"])
            freq=collections.Counter(d["tokens"])
            for t in q_toks:
                f=freq.get(t,0)
                if not f: continue
                idf=math.log((self.N - self.df.get(t,0) +0.5)/(self.df.get(t,0)+0.5)+1)
                denom=f + self.k1*(1 - self.b + self.b*dl/self.avgdl) if self.avgdl else 1
                s+=idf * (f*(self.k1+1)/denom)
            # Boost exact GOST token
            # if query contains ГОСТ number, boost docs with same designation
            scores.append((s,d))
        scores.sort(key=lambda x: x[0], reverse=True)
        return scores

bm25_index = BM25Index()

class TextRAG:
    def __init__(self):
        self.vs = vector_store()
        self.collection = "gosts_text"

    def index_gost_chunk(self, gost_designation: str, title: str, chunk_text: str, chunk_id: str, meta: dict=None):
        vec = self.vs.embed_text(chunk_text)
        payload = {"designation": gost_designation, "title": title, "text": chunk_text, **(meta or {})}
        self.vs.upsert(self.collection, [{"id": chunk_id, "vector": vec, "payload": payload}])
        # BM25
        try:
            bm25_index.add(chunk_id, chunk_text + " " + gost_designation, payload)
        except Exception as e:
            logger.debug(f"bm25 add failed: {e}")

    def search(self, query_text: str, top_k: int=5, filter: dict | None=None, hybrid: bool=True, rerank: bool=True) -> list[dict]:
        mentions = extract_gost_mentions(query_text)
        qvec = self.vs.embed_text(query_text)
        # Vector
        v_hits = self.vs.search(self.collection, qvec, top_k=max(top_k*4, 20), filter=filter)
        for h in v_hits:
            h["origin"]="vector"
            h["bm25_score"]=0
        # BM25
        bm25_hits=[]
        if hybrid:
            try:
                bm25_scored = bm25_index.score(query_text)[:max(top_k*4,20)]
                for score, doc in bm25_scored:
                    # find corresponding vector hit or create shell
                    existing = next((x for x in v_hits if x["id"]==doc["id"]), None)
                    if existing:
                        existing["bm25_score"]=score
                        existing["origin"]="hybrid"
                    else:
                        bm25_hits.append({"id":doc["id"],"score":0.2,"bm25_score":score,"payload":doc["payload"],"origin":"bm25"})
            except Exception as e:
                logger.debug(f"bm25 search failed: {e}")
        # Hybrid fuse: weighted sum (vector 0.6, bm25 normalized 0.4)
        all_hits = v_hits + bm25_hits
        if hybrid and all_hits:
            max_bm25 = max((h.get("bm25_score",0) for h in all_hits), default=1) or 1
            for h in all_hits:
                bm25_norm = h.get("bm25_score",0)/max_bm25
                h["hybrid_score"] = h.get("score",0)*0.6 + bm25_norm*0.4
            # Boost ГОСТ mention strongly
            for h in all_hits:
                des = h["payload"].get("designation","")
                if any(des in m or m in des for m in mentions):
                    h["hybrid_score"] += 2.0
                for m in mentions:
                    nums = re.findall(r"\d+\.\d+", m)
                    if any(n in des for n in nums):
                        h["hybrid_score"] += 1.0
                # exact phrase boost
                if query_text.lower().strip() in h["payload"].get("text","").lower():
                    h["hybrid_score"]+=0.3
            all_hits.sort(key=lambda x: x.get("hybrid_score", x.get("score",0)), reverse=True)
        else:
            # legacy boost
            for h in all_hits:
                des = h["payload"].get("designation","")
                if any(des in m or m in des for m in mentions):
                    h["score"] += 2.0
                for m in mentions:
                    nums = re.findall(r"\d+\.\d+", m)
                    if any(n in des for n in nums):
                        h["score"] += 1.0
            all_hits.sort(key=lambda x: x.get("score",0), reverse=True)

        # Cross-encoder re-rank (mock: token overlap + ГОСТ exact)
        if rerank and all_hits:
            # In prod: cross-encoder/ms-marco-MiniLM-L-6-v2
            # Here: cheap re-rank based on query token overlap and snippet length penalty
            q_toks=set(bm25_index.tokenize(query_text))
            for h in all_hits[:min(20, len(all_hits))]:
                txt=h["payload"].get("text","")
                t_toks=set(bm25_index.tokenize(txt))
                overlap=len(q_toks & t_toks)/max(len(q_toks),1)
                h["rerank_score"]= h.get("hybrid_score", h.get("score",0))*0.7 + overlap*0.3
            # keep top 20 reranked on top, rest as is
            top = sorted(all_hits[:20], key=lambda x: x.get("rerank_score",0), reverse=True)
            rest = all_hits[20:]
            all_hits = top + rest

        for h in all_hits:
            txt = h["payload"].get("text","")
            h["snippet"] = txt[:400]
            # ensure score field for API compat
            h["score"] = h.get("hybrid_score", h.get("rerank_score", h.get("score",0)))
        return all_hits[:top_k]

    def autocomplete(self, prefix: str, limit: int=5) -> list[str]:
        # Simple prefix on designations
        prefix = prefix.strip()
        # From bm25 docs designations
        cands=set()
        for d in bm25_index.docs:
            des=d["payload"].get("designation","")
            if des.lower().startswith(prefix.lower()) or prefix.lower() in des.lower():
                cands.add(des)
        # also regex
        if not cands:
            # fallback: known gosts
            for d in ["ГОСТ 2.104-2006","ГОСТ 2.307-2011","ГОСТ 2.305-2008","ГОСТ 2.303-68","ГОСТ 2.109-73"]:
                if prefix.lower() in d.lower():
                    cands.add(d)
        return sorted(cands)[:limit]

    def ask(self, query: str, top_k: int=3) -> dict[str,Any]:
        hits = self.search(query, top_k=top_k, hybrid=True, rerank=True)
        context = "\n\n".join([f"[{h['payload'].get('designation')}] {h['snippet']}" for h in hits])
        return {"query": query, "hits": hits, "context": context, "mentions": extract_gost_mentions(query), "hybrid": True, "reranked": True}

    def ingest_gost_file(self, filepath: str, designation: str=None, title: str=None) -> dict[str,Any]:
        text=""
        try:
            import fitz
            doc = fitz.open(filepath)
            text = "\n".join([p.get_text() for p in doc])
        except:
            try:
                import PyPDF2
                reader = PyPDF2.PdfReader(filepath)
                text = "\n".join([p.extract_text() or "" for p in reader.pages])
            except Exception as e:
                logger.warning(f"pdf extract fail {filepath}: {e}")
                text = open(filepath, errors="ignore").read() if os.path.exists(filepath) else ""
        if not text.strip():
            text = f"ГОСТ документ {os.path.basename(filepath)}"
        chunks=[]
        chunk_size=800
        overlap=120
        for i in range(0, len(text), chunk_size-overlap):
            chunk=text[i:i+chunk_size]
            if len(chunk.strip())<50: continue
            chunks.append(chunk)
        if not designation:
            m = GOST_RE.search(os.path.basename(filepath))
            designation = m.group(0) if m else os.path.splitext(os.path.basename(filepath))[0]
        if not title:
            title = designation
        for idx, ch in enumerate(chunks):
            cid = f"{designation.replace(' ','_')}_{idx}"
            # store full text for autocomplete? already
            self.index_gost_chunk(designation, title, ch, cid, meta={"filepath":filepath, "chunk_idx": idx})
        return {"designation": designation, "chunks": len(chunks), "filepath": filepath}

text_rag = TextRAG()
