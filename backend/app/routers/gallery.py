from fastapi import APIRouter, Depends, HTTPException, UploadFile, File, Form
from sqlalchemy.orm import Session
from ..db import get_db
from ..models.gallery import GalleryItem
from ..models.user import User
from ..security import get_current_user
from ..services.rag_visual import visual_rag
from ..config import settings
import os, shutil, uuid

router = APIRouter(prefix="/api/gallery", tags=["gallery"])

@router.get("/")
def list_gallery(category: str=None, db: Session=Depends(get_db), user: User=Depends(get_current_user)):
    q=db.query(GalleryItem).order_by(GalleryItem.created_at.desc())
    if category: q=q.filter(GalleryItem.category==category)
    items=q.limit(100).all()
    return {"items": [{"id":g.id,"title":g.title,"category":g.category,"gost_ref":g.gost_ref,"error_type":g.error_type,"filepath":g.filepath} for g in items]}

@router.post("/upload")
def upload_gallery(
    file: UploadFile = File(...),
    title: str = Form(...),
    category: str = Form("error"),
    gost_ref: str = Form(None),
    error_type: str = Form(None),
    db: Session=Depends(get_db),
    user: User=Depends(get_current_user)
):
    if user.role not in ("admin","normocontroller"):
        raise HTTPException(403, "Only normocontroller/admin")
    ext = os.path.splitext(file.filename)[1] or ".png"
    fid = str(uuid.uuid4())[:8]
    dest = os.path.join(settings.gallery_path, f"{fid}_{file.filename}")
    os.makedirs(os.path.dirname(dest), exist_ok=True)
    with open(dest, "wb") as out:
        shutil.copyfileobj(file.file, out)
    # index in vector store
    item_id = f"gallery_{fid}"
    payload = {"title": title, "category": category, "gost_ref": gost_ref, "error_type": error_type, "filepath": dest}
    visual_rag.index_gallery_item(item_id, dest, payload)
    g = GalleryItem(title=title, category=category, gost_ref=gost_ref, error_type=error_type, filepath=dest, embedding_id=item_id)
    db.add(g); db.commit(); db.refresh(g)
    return {"id": g.id, "status":"indexed", "filepath": dest}

@router.post("/search")
def search_gallery(image_path: str=None, top_k: int=5, file: UploadFile=File(None), db: Session=Depends(get_db), user: User=Depends(get_current_user)):
    # Supports either uploaded image or path
    if file:
        tmp = f"/tmp/{uuid.uuid4().hex}.png"
        with open(tmp, "wb") as out:
            shutil.copyfileobj(file.file, out)
        image_path=tmp
    if not image_path or not os.path.exists(image_path):
        raise HTTPException(400, "image_path or file required")
    hits = visual_rag.search(image_path, top_k=top_k)
    return {"hits": hits}

@router.delete("/{item_id}")
def delete_item(item_id:int, db: Session=Depends(get_db), user: User=Depends(get_current_user)):
    if user.role not in ("admin","normocontroller"):
        raise HTTPException(403,"Forbidden")
    g=db.query(GalleryItem).filter(GalleryItem.id==item_id).first()
    if not g: raise HTTPException(404,"Not found")
    db.delete(g); db.commit()
    return {"deleted": item_id}
