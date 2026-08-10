import os, time, json, logging, traceback
from datetime import datetime
from sqlalchemy.orm import Session
from .db import SessionLocal, engine
from .models.check import Check, PageResult
from .config import settings
from .services.preprocessing import preprocess_pdf
from .services.segmentation import segment_page
from .services.ocr import ocr_service
from .services.rag_text import text_rag
from .services.rag_visual import visual_rag
from .services.vlm import vlm_service
from .services.metadata import consistency_check, extract_all_technical_metadata

logger = logging.getLogger(__name__)

def _get_db():
    return SessionLocal()

def _process_check_logic(check_id: int):
    db = _get_db()
    try:
        check = db.query(Check).filter(Check.id==check_id).first()
        if not check:
            logger.error(f"Check {check_id} not found")
            return
        check.status="processing"
        db.commit()
        pdf_path = check.filepath
        if not os.path.exists(pdf_path):
            check.status="failed"
            check.summary=f"File not found: {pdf_path}"
            db.commit()
            return

        pages = preprocess_pdf(pdf_path)
        check.pages_total=len(pages)
        db.commit()

        all_metas=[]
        all_errors=[]
        summary_prev=""
        for p in pages:
            page_num=p["page_number"]
            img_path=p["image_path"]
            # segmentation
            seg = segment_page(img_path, check_id, page_num)
            crops = seg["crops"]
            # OCR
            ocr_res = ocr_service.extract_with_zones(img_path, crops)
            ocr_text = ocr_res.get("text","")
            # RAG text
            text_hits = text_rag.search(ocr_text, top_k=3)
            # Visual RAG per crop + whole
            visual_hints=[]
            # check graphic_views and whole
            candidates = [img_path] + [c["path"] for c in crops.values()]
            for cand in candidates[:2]:
                hint = visual_rag.hint_for_vlm(cand)
                if hint:
                    visual_hints.append(hint)
            visual_hint = visual_hints[0] if visual_hints else None

            # VLM analyze with context window
            vlm_out = vlm_service.analyze_page(img_path, ocr_text, text_hits=text_hits, visual_hint=visual_hint, page_number=page_num, summary_prev=summary_prev)
            summary_prev = vlm_out.get("summary", summary_prev)

            # Save page result
            pr = PageResult(
                check_id=check_id,
                page_number=page_num,
                status="done",
                ocr_text=ocr_text[:5000],
                vlm_output=vlm_out,
                errors=vlm_out.get("errors",[]),
                crops={k: {"bbox":v["bbox"],"confidence":v["confidence"]} for k,v in seg["zones"].items()},
                visual_hits=visual_hints,
                text_hits=[{"designation":h["payload"].get("designation"),"score":h["score"]} for h in text_hits],
            )
            db.add(pr)
            db.commit()

            all_metas.append(vlm_out.get("metadata",{}))
            for e in vlm_out.get("errors",[]):
                e["page"]=page_num
                all_errors.append(e)

            check.pages_done=page_num
            db.commit()

            # VRAM cleanup
            if settings.empty_cache_after_page:
                vlm_service.empty_cache()
                try:
                    import torch
                    if torch.cuda.is_available():
                        torch.cuda.empty_cache()
                except: pass
            # pipeline parallelism: next page OCR already CPU, VLM is serialized (MAX_CONCURRENT_VLM=1)
            time.sleep(0.05)  # simulate yield

        # Consistency
        consistency = consistency_check(all_metas)
        for iss in consistency.get("issues",[]):
            all_errors.append(iss)

        # Aggregate metadata: take first page as primary
        primary_meta = all_metas[0] if all_metas else {}
        # Validate
        check.meta_json=primary_meta
        check.errors_json=all_errors
        check.consistency_json=consistency
        check.summary=summary_prev or f"Проверено {len(pages)} листов, найдено {len(all_errors)} замечаний."
        check.status="done"
        check.finished_at=datetime.utcnow()
        db.commit()
        logger.info(f"Check {check_id} done: {len(all_errors)} errors")
    except Exception as e:
        logger.exception(f"Check {check_id} failed: {e}")
        try:
            db = _get_db()
            c = db.query(Check).filter(Check.id==check_id).first()
            if c:
                c.status="failed"
                c.summary=str(e)[:1000]
                db.commit()
        except: pass
        traceback.print_exc()
    finally:
        try:
            db.close()
        except: pass

# Celery wrappers with fallback to eager if redis unavailable
try:
    from .celery_app import celery_app

    @celery_app.task(name="app.tasks.process_check", bind=True, max_retries=2)
    def process_check(self, check_id: int):
        return _process_check_logic(check_id)

    @celery_app.task(name="app.tasks.process_check_high", bind=True)
    def process_check_high(self, check_id: int):
        return _process_check_logic(check_id)

    @celery_app.task(name="app.tasks.process_check_low", bind=True)
    def process_check_low(self, check_id: int):
        return _process_check_logic(check_id)

    def _redis_available() -> bool:
        try:
            import redis as _redis
            r = _redis.from_url(settings.celery_broker_url, socket_connect_timeout=1, socket_timeout=1)
            r.ping()
            return True
        except Exception as e:
            logger.debug(f"Redis unavailable: {e}")
            return False

    def enqueue_check(check_id: int, priority: int=5):
        # Fast path: if Redis not available (dev without docker), run synchronously without blocking on Celery timeout
        if not _redis_available():
            logger.info(f"Redis not available, running check {check_id} synchronously (priority {priority})")
            _process_check_logic(check_id)
            return False
        try:
            if priority <=3:
                process_check_high.delay(check_id)
            elif priority >=8:
                process_check_low.delay(check_id)
            else:
                process_check.delay(check_id)
            return True
        except Exception as e:
            logger.warning(f"Celery enqueue failed, running eager: {e}")
            # fallback synchronous
            _process_check_logic(check_id)
            return False

except ImportError:
    # No celery
    def process_check(check_id:int): _process_check_logic(check_id)
    def process_check_high(check_id:int): _process_check_logic(check_id)
    def process_check_low(check_id:int): _process_check_logic(check_id)
    def enqueue_check(check_id:int, priority:int=5):
        _process_check_logic(check_id)
        return False

# Expose for direct call in API
def process_check_sync(check_id:int):
    return _process_check_logic(check_id)
