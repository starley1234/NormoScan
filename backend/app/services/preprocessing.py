import hashlib
import logging
import os
from typing import Any

from PIL import Image

logger = logging.getLogger(__name__)

try:
    import fitz  # PyMuPDF
    HAS_FITZ=True
except:
    HAS_FITZ=False
try:
    import pypdfium2 as pdfium
    HAS_PDFIUM=True
except:
    HAS_PDFIUM=False

from ..config import settings


def pdf_to_images(pdf_path: str, dpi: int=150) -> list[tuple[int, str]]:
    """Split PDF into page images, return list of (page_num, image_path)"""
    out_dir = os.path.join(settings.storage_path, "pages", os.path.basename(pdf_path).replace(".pdf",""))
    os.makedirs(out_dir, exist_ok=True)
    images=[]
    if HAS_FITZ:
        doc = fitz.open(pdf_path)
        for i, page in enumerate(doc):
            pix = page.get_pixmap(dpi=dpi)
            img_path = os.path.join(out_dir, f"page_{i+1:03d}.png")
            pix.save(img_path)
            images.append((i+1, img_path))
        return images
    if HAS_PDFIUM:
        pdf = pdfium.PdfDocument(pdf_path)
        for i in range(len(pdf)):
            page = pdf[i]
            bitmap = page.render(scale=dpi/72).to_pil()
            img_path = os.path.join(out_dir, f"page_{i+1:03d}.png")
            bitmap.save(img_path)
            images.append((i+1, img_path))
        return images
    # fallback: treat pdf as image already? create dummy
    # try PIL open
    try:
        im = Image.open(pdf_path)
        img_path = os.path.join(out_dir, "page_001.png")
        im.save(img_path)
        images.append((1, img_path))
        return images
    except:
        raise RuntimeError("No PDF renderer available (install PyMuPDF or pypdfium2)")

def adaptive_resize(image_path: str, target_width: int=None) -> str:
    """Resize to 512-800px width, keep aspect, return new path or same"""
    tw = target_width or settings.image_width
    tw = max(512, min(800, tw))
    im = Image.open(image_path)
    w,h = im.size
    if w == tw:
        return image_path
    # only downscale if larger, else keep
    if w <= tw:
        return image_path
    new_h = int(h * tw / w)
    im2 = im.resize((tw, new_h), Image.LANCZOS)
    out = image_path.replace(".png","_rs.png")
    im2.save(out)
    return out

def hash_file(path: str) -> str:
    h=hashlib.sha256()
    with open(path,"rb") as f:
        for chunk in iter(lambda: f.read(8192), b""):
            h.update(chunk)
    return h.hexdigest()[:16]

def preprocess_pdf(pdf_path: str) -> list[dict[str,Any]]:
    pages = pdf_to_images(pdf_path)
    result=[]
    for num, path in pages:
        resized = adaptive_resize(path)
        result.append({"page_number":num, "image_path": resized, "orig_path": path, "hash": hash_file(resized)})
    return result
