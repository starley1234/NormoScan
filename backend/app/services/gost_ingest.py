import os, glob, logging
from typing import Dict, Any
from .rag_text import text_rag
from ..models.gost import Gost
from sqlalchemy.orm import Session

logger = logging.getLogger(__name__)

def ingest_folder(folder: str, db: Session=None) -> Dict[str,Any]:
    if not os.path.isdir(folder):
        return {"error": f"Folder not found: {folder}"}
    pdfs = glob.glob(os.path.join(folder, "**", "*.pdf"), recursive=True)
    pdfs += glob.glob(os.path.join(folder, "**", "*.PDF"), recursive=True)
    # also txt
    txts = glob.glob(os.path.join(folder, "**", "*.txt"), recursive=True)
    all_files = pdfs + txts
    results=[]
    for f in all_files:
        try:
            res = text_rag.ingest_gost_file(f)
            results.append(res)
            if db is not None:
                # upsert DB record
                existing = db.query(Gost).filter(Gost.designation==res["designation"]).first()
                if not existing:
                    g = Gost(designation=res["designation"], title=res["designation"], filepath=f, chunks_json=[], status="indexed")
                    db.add(g)
                else:
                    existing.filepath=f
                    existing.status="indexed"
                db.commit()
        except Exception as e:
            logger.warning(f"ingest failed {f}: {e}")
            results.append({"filepath": f, "error": str(e)})
    return {"folder": folder, "files_found": len(all_files), "processed": len(results), "details": results}

def search_gost(query: str, top_k: int=5) -> Dict[str,Any]:
    return text_rag.ask(query, top_k=top_k)
