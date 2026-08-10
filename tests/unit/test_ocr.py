import os, tempfile
from PIL import Image

def test_mock_ocr():
    from backend.app.services.ocr import ocr_service
    with tempfile.TemporaryDirectory() as tmp:
        path = os.path.join(tmp, "img.png")
        im = Image.new("RGB", (500,500), color="white")
        im.save(path)
        res = ocr_service.extract(path)
        assert "text" in res
        assert "engine" in res
        assert "Обозначение" in res["text"] or "Наименование" in res["text"] or len(res["text"])>5

def test_ocr_with_zones():
    from backend.app.services.ocr import ocr_service
    with tempfile.TemporaryDirectory() as tmp:
        path = os.path.join(tmp, "img.png")
        im = Image.new("RGB", (768,1024), color="white")
        im.save(path)
        crops = {
            "stamp": {"path": path, "bbox":[0.73,0.82,0.26,0.17], "confidence":0.9},
            "tech_requirements": {"path": path, "bbox":[0.03,0.6,0.45,0.22], "confidence":0.8}
        }
        res = ocr_service.extract_with_zones(path, crops)
        assert "text" in res
        assert "zone_texts" in res
        assert "stamp" in res["zone_texts"]
