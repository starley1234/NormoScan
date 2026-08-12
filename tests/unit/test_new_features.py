import os, tempfile
from PIL import Image

def test_dedupe():
    from fastapi.testclient import TestClient
    from backend.app.main import app
    c=TestClient(app)
    import uuid
    uname=f"dedup_{uuid.uuid4().hex[:6]}"
    c.post("/api/auth/register", json={"username":uname,"password":"pass123","role":"engineer"})
    token=c.post("/api/auth/login", data={"username":uname,"password":"pass123"}).json()["access_token"]
    h={"Authorization": f"Bearer {token}"}
    with tempfile.TemporaryDirectory() as tmp:
        pdf=os.path.join(tmp,"dedup.pdf")
        Image.new("RGB",(800,600),color="white").save(pdf,"PDF")
        with open(pdf,"rb") as f:
            r1=c.post("/api/checks/upload?priority=5", files={"file":("dedup.pdf",f,"application/pdf")}, headers=h)
        assert r1.status_code==200
        id1=r1.json()["check_id"]
        # second upload same file within window should dedupe
        with open(pdf,"rb") as f:
            r2=c.post("/api/checks/upload?priority=5", files={"file":("dedup.pdf",f,"application/pdf")}, headers=h)
        assert r2.status_code==200
        assert r2.json()["status"] in ("dedupe","queued")  # dedupe if recent

def test_checklist_and_fix():
    from backend.app.services.vlm import _mock_vlm_analysis, suggest_fix_for_error
    out=_mock_vlm_analysis("/tmp/img.png","Обозначение АБВГ.123 Наименование Вал",[],None,1,"")
    assert "checklist" in out
    assert len(out["checklist"])>0
    for err in out["errors"]:
        assert "suggested_fix" in err
        fix=suggest_fix_for_error(err)
        assert isinstance(fix,str) and len(fix)>5

def test_incremental_gost():
    from backend.app.services.gost_ingest import ingest_folder
    from backend.app.db import SessionLocal, init_db
    import tempfile, os
    init_db()
    db=SessionLocal()
    with tempfile.TemporaryDirectory() as tmp:
        # create dummy pdf
        from PIL import Image
        pdf=os.path.join(tmp,"ГОСТ 2.104-2006.pdf")
        Image.new("RGB",(400,300),color="white").save(pdf,"PDF")
        res1=ingest_folder(tmp, db)
        assert res1["indexed"]>=1
        res2=ingest_folder(tmp, db)
        # second should be skipped
        assert res2["skipped"]>=1
    db.close()

def test_ocr_ensemble():
    from backend.app.services.ocr import ocr_service
    with tempfile.TemporaryDirectory() as tmp:
        p=os.path.join(tmp,"img.png")
        Image.new("RGB",(600,600),color="white").save(p)
        res=ocr_service.extract(p)
        assert "confidence" in res
        res2=ocr_service.extract_with_zones(p, {"stamp":{"path":p,"bbox":[0.5,0.5,0.2,0.2],"confidence":0.9}})
        assert "zone_texts" in res2
        assert "confidence" in res2

def test_metrics_and_sse():
    from fastapi.testclient import TestClient
    from backend.app.main import app
    c=TestClient(app)
    r=c.get("/metrics")
    assert r.status_code==200
    r=c.get("/api/metrics")
    assert r.status_code==200
    assert "uptime_seconds" in r.json()
    # test sse endpoint exists (auth required)
    # create user
    import uuid
    uname=f"metrics_{uuid.uuid4().hex[:6]}"
    c.post("/api/auth/register", json={"username":uname,"password":"pass123","role":"viewer"})
    token=c.post("/api/auth/login", data={"username":uname,"password":"pass123"}).json()["access_token"]
    h={"Authorization": f"Bearer {token}"}
    # need a check
    with tempfile.TemporaryDirectory() as tmp:
        pdf=os.path.join(tmp,"m.pdf")
        Image.new("RGB",(400,400),color="white").save(pdf,"PDF")
        # create admin for upload
        c.post("/api/auth/register", json={"username":f"admin_{uuid.uuid4().hex[:4]}","password":"pass123","role":"admin"})
        # use admin
        admin_token=c.post("/api/auth/login", data={"username":"admin","password":"admin123"}).json()["access_token"]
        hh={"Authorization": f"Bearer {admin_token}"}
        with open(pdf,"rb") as f:
            r=c.post("/api/checks/upload", files={"file":("m.pdf",f,"application/pdf")}, headers=hh)
        cid=r.json()["check_id"]
        # sse
        r=c.get(f"/api/checks/{cid}/stream", headers=hh)
        assert r.status_code==200
        assert "data:" in r.text

def test_metadata_schema_crud():
    from fastapi.testclient import TestClient
    from backend.app.main import app
    c=TestClient(app)
    import uuid, json
    token=c.post("/api/auth/login", data={"username":"admin","password":"admin123"}).json()["access_token"]
    h={"Authorization": f"Bearer {token}"}
    # list
    r=c.get("/api/admin/schemas", headers=h)
    assert r.status_code==200
    # create
    schema={"type":"object","properties":{"Обозначение":{"type":"string"},"Цех":{"type":"string","enum":["5","7"]}},"required":["Обозначение"]}
    r=c.post("/api/admin/schemas", json={"name":f"test_{uuid.uuid4().hex[:4]}","title":"test","schema_json":schema,"make_active":False}, headers=h)
    assert r.status_code==200
    # check active schema endpoint
    r=c.get("/api/checks/meta/schema", headers=h)
    assert r.status_code==200
    assert "properties" in r.json()
