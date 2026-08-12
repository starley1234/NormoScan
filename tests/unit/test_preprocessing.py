import os, tempfile
from PIL import Image

def test_adaptive_resize():
    from backend.app.services.preprocessing import adaptive_resize
    # create dummy image 1200x800
    with tempfile.TemporaryDirectory() as tmp:
        path = os.path.join(tmp, "test.png")
        im = Image.new("RGB", (1200,800), color="white")
        im.save(path)
        out = adaptive_resize(path, target_width=768)
        im2 = Image.open(out)
        assert im2.size[0]==768
        assert im2.size[1]== int(800*768/1200)
        # small image should not upscale
        path2 = os.path.join(tmp, "small.png")
        ims = Image.new("RGB", (400,300), color="white")
        ims.save(path2)
        out2 = adaptive_resize(path2, target_width=768)
        im3 = Image.open(out2)
        assert im3.size[0]==400  # not upscaled

def test_preprocess_pdf_mock():
    from backend.app.services.preprocessing import pdf_to_images, preprocess_pdf
    # Create a simple PDF via reportlab fallback or pillow pdf
    import tempfile
    with tempfile.TemporaryDirectory() as tmp:
        # create image then save as pdf using pillow
        img_path = os.path.join(tmp, "page.png")
        pdf_path = os.path.join(tmp, "doc.pdf")
        im = Image.new("RGB", (800,600), color="white")
        im.save(img_path)
        # convert to pdf via pillow
        im.save(pdf_path, "PDF")
        # monkey patch storage
        import backend.app.services.preprocessing as pp
        orig_storage = pp.settings.storage_path
        pp.settings.storage_path = tmp
        try:
            pages = preprocess_pdf(pdf_path)
            assert len(pages)>=1
            assert "image_path" in pages[0]
            assert pages[0]["page_number"]==1
        finally:
            pp.settings.storage_path = orig_storage
