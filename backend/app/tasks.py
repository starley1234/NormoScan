import hashlib
import logging
import os
import time
import traceback
from datetime import datetime, timedelta

from .config import settings
from .core.metrics import inc_checks, metrics, observe_page_time
from .db import SessionLocal
from .models.check import Check, DeadLetter, PageResult
from .services.metadata import consistency_check
from .services.ocr import ocr_service
from .services.preprocessing import preprocess_pdf
from .services.rag_text import text_rag
from .services.rag_visual import visual_rag
from .services.segmentation import segment_page
from .services.vlm import enrich_errors_with_fixes, vlm_service

logger = logging.getLogger(__name__)

def _get_db():
    return SessionLocal()

def _file_hash(path: str) -> str:
    h = hashlib.sha256()
    try:
        with open(path,"rb") as f:
            for chunk in iter(lambda: f.read(8192), b""):
                h.update(chunk)
        return h.hexdigest()[:16]
    except:
        return None

def _process_check_logic(check_id: int):
    db = _get_db()
    t0 = time.time()
    try:
        check = db.query(Check).filter(Check.id==check_id).first()
        if not check:
            logger.error(f"Check {check_id} not found")
            return
        # Idempotency: if already done recently with same hash, skip
        if check.file_hash:
            recent = datetime.utcnow() - timedelta(minutes=settings.dedupe_window_minutes)
            dup = db.query(Check).filter(Check.file_hash==check.file_hash, Check.id!=check.id, Check.status=="done", Check.created_at>=recent).first()
            if dup:
                logger.info(f"Dedupe hit for {check_id}: same as {dup.id}")
                # Copy results
                check.meta_json = dup.meta_json
                check.errors_json = dup.errors_json
                check.summary = dup.summary + " (дедупликация)"
                check.consistency_json = dup.consistency_json
                check.checklist_json = dup.checklist_json
                check.pages_total = dup.pages_total
                check.pages_done = dup.pages_total
                check.status="done"
                check.finished_at=datetime.utcnow()
                db.commit()
                inc_checks("dedupe")
                return

        check.status="processing"
        db.commit()
        inc_checks("processing")
        pdf_path = check.filepath
        if not os.path.exists(pdf_path):
            check.status="failed"
            check.summary=f"File not found: {pdf_path}"
            db.commit()
            inc_checks("failed")
            return

        # compute hash if missing
        if not check.file_hash:
            check.file_hash = _file_hash(pdf_path)
            db.commit()

        pages = preprocess_pdf(pdf_path)
        check.pages_total=len(pages)
        db.commit()

        all_metas=[]
        all_errors=[]
        all_checklists=[]
        summary_prev=""
        for p in pages:
            page_t0=time.time()
            page_num=p["page_number"]
            img_path=p["image_path"]
            seg = segment_page(img_path, check_id, page_num)
            crops = seg["crops"]
            ocr_res = ocr_service.extract_with_zones(img_path, crops)
            ocr_text = ocr_res.get("text","")
            ocr_conf = ocr_res.get("confidence",0)
            text_hits = text_rag.search(ocr_text, top_k=3)
            visual_hints=[]
            candidates = [img_path] + [c["path"] for c in crops.values()]
            for cand in candidates[:2]:
                hint = visual_rag.hint_for_vlm(cand)
                if hint:
                    visual_hints.append(hint)
            visual_hint = visual_hints[0] if visual_hints else None

            # Extract visual sim for calibration
            vis_sim=None
            if visual_hint:
                import re
                m=re.search(r"(\d+)%", visual_hint)
                if m:
                    try: vis_sim=int(m.group(1))/100
                    except: pass
            logger.info(f"Tasks VLM → check {check_id} page {page_num} engine={vlm_service.engine} quant={vlm_service.quant} url={settings.vlm_api_url} ocr_conf={ocr_conf:.2f} has_key={bool(settings.vlm_api_key)}")
            vlm_out = vlm_service.analyze_page(img_path, ocr_text, text_hits=text_hits, visual_hint=visual_hint, page_number=page_num, summary_prev=summary_prev, ocr_confidence=ocr_conf, visual_sim=vis_sim)
            logger.info(f"Tasks VLM ← check {check_id} page {page_num} conf={vlm_out.get('confidence')} errors={len(vlm_out.get('errors',[]))} model={vlm_out.get('model')}")
            summary_prev = vlm_out.get("summary", summary_prev)

            # Save page result
            pr = PageResult(
                check_id=check_id,
                page_number=page_num,
                status="done",
                ocr_text=ocr_text[:5000],
                ocr_confidence=ocr_conf,
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
            # checklist aggregation
            for cl in vlm_out.get("checklist",[]):
                # merge counts
                existing = next((x for x in all_checklists if x["code"]==cl["code"]), None)
                if not existing:
                    all_checklists.append(dict(cl))
                else:
                    if cl["status"]=="fail":
                        existing["status"]="fail"
                        existing["count"]+=cl.get("count",0)

            check.pages_done=page_num
            db.commit()
            observe_page_time(time.time()-page_t0)

            if settings.empty_cache_after_page:
                vlm_service.empty_cache()
                try:
                    import torch
                    if torch.cuda.is_available():
                        torch.cuda.empty_cache()
                except: pass
            time.sleep(0.05)

        # Consistency
        consistency = consistency_check(all_metas)
        for iss in consistency.get("issues",[]):
            # enrich with fix
            iss["suggested_fix"]="Сверьте обозначения на всех листах, исправьте в штампе."
            iss["severity"]="error"
            all_errors.append(iss)

        # Ensure fixes
        all_errors = enrich_errors_with_fixes(all_errors)

        primary_meta = all_metas[0] if all_metas else {}
        check.meta_json=primary_meta
        check.errors_json=all_errors
        check.consistency_json=consistency
        check.checklist_json={"items": all_checklists, "total": len(all_checklists), "failed": sum(1 for c in all_checklists if c["status"]=="fail")}
        check.summary=summary_prev or f"Проверено {len(pages)} листов, найдено {len(all_errors)} замечаний."
        check.status="done"
        check.finished_at=datetime.utcnow()
        db.commit()
        inc_checks("done")
        metrics.observe("normoscan_check_seconds", time.time()-t0)
        logger.info(f"Check {check_id} done: {len(all_errors)} errors, checklist {check.checklist_json}", extra={"check_id":check_id, "duration": round(time.time()-t0,2)})
    except Exception as e:
        logger.exception(f"Check {check_id} failed: {e}")
        # dead letter handling
        try:
            db2 = _get_db()
            c = db2.query(Check).filter(Check.id==check_id).first()
            if c:
                c.retry_count = (c.retry_count or 0)+1
                if c.retry_count >= settings.queue_max_retries:
                    c.status="dead_letter"
                    dl = DeadLetter(check_id=check_id, filename=c.filename, error=str(e)[:2000], traceback=traceback.format_exc()[:4000], retry_count=c.retry_count)
                    db2.add(dl)
                    logger.error(f"Check {check_id} moved to dead_letter after {c.retry_count} retries")
                else:
                    c.status="failed"
                    c.summary=str(e)[:1000]
                db2.commit()
            db2.close()
        except Exception as ee:
            logger.error(f"dead letter handling failed: {ee}")
        inc_checks("failed")
        traceback.print_exc()
    finally:
        try:
            db.close()
        except: pass

# Celery wrappers with fallback to eager if redis unavailable
try:
    from .celery_app import celery_app

    @celery_app.task(name="app.tasks.process_check", bind=True, max_retries=3)
    def process_check(self, check_id: int):
        try:
            return _process_check_logic(check_id)
        except Exception as e:
            # retry with backoff
            try:
                self.retry(exc=e, countdown=2**self.request.retries)
            except:
                raise

    @celery_app.task(name="app.tasks.process_check_high", bind=True, max_retries=3)
    def process_check_high(self, check_id: int):
        return _process_check_logic(check_id)

    @celery_app.task(name="app.tasks.process_check_low", bind=True, max_retries=3)
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

    def _celery_has_workers(timeout: float=1.0) -> bool:
        try:
            # ping workers — если нет ответа, считаем что воркеров нет
            insp = celery_app.control.inspect(timeout=timeout)
            active = insp.active()
            # active вернёт None если нет воркеров
            if not active:
                logger.warning("Celery: no active workers detected (inspect returned None)")
                return False
            # даже если active == {}, воркер есть но idle — считаем живым
            return True
        except Exception as e:
            logger.debug(f"Celery workers check failed: {e}")
            return False

    def enqueue_check(check_id: int, priority: int=5):
        if not _redis_available():
            logger.info(f"Redis not available, running check {check_id} synchronously (priority {priority})")
            _process_check_logic(check_id)
            return False
        # если Redis есть, но воркеров нет — фолбэк в sync чтобы не висело в queued
        if not _celery_has_workers():
            logger.warning(f"Celery workers not available, running check {check_id} synchronously (fallback)")
            _process_check_logic(check_id)
            return False
        try:
            if priority <=3:
                process_check_high.delay(check_id)
            elif priority >=8:
                process_check_low.delay(check_id)
            else:
                process_check.delay(check_id)
            metrics.inc("normoscan_enqueued", labels={"priority": str(priority)})
            logger.info(f"Enqueued check {check_id} to Celery priority={priority}")
            return True
        except Exception as e:
            logger.warning(f"Celery enqueue failed, running eager: {e}")
            _process_check_logic(check_id)
            return False

except ImportError:
    def process_check(check_id:int): _process_check_logic(check_id)
    def process_check_high(check_id:int): _process_check_logic(check_id)
    def process_check_low(check_id:int): _process_check_logic(check_id)
    def enqueue_check(check_id:int, priority:int=5):
        _process_check_logic(check_id)
        return False

def process_check_sync(check_id:int):
    return _process_check_logic(check_id)
