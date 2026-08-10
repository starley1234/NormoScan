"""
Load Test: стабильность очереди при 10 одновременных пользователях на 16GB VRAM
Запуск: locust -f tests/load/locustfile.py --host http://localhost:8000
"""
from locust import HttpUser, task, between
import tempfile, os
from PIL import Image
import io

class NormoScanUser(HttpUser):
    wait_time = between(1,3)

    def on_start(self):
        # login
        self.client.post("/api/auth/login", data={"username":"admin","password":"admin123"})
        # try register if needed
        if self.client.post("/api/auth/login", data={"username":"admin","password":"admin123"}).status_code!=200:
            self.client.post("/api/auth/register", json={"username":"admin","password":"admin123","role":"admin"})
        r=self.client.post("/api/auth/login", data={"username":"admin","password":"admin123"})
        if r.status_code==200:
            self.token=r.json().get("access_token")
            self.headers={"Authorization": f"Bearer {self.token}"}
        else:
            self.headers={}

    @task(3)
    def health(self):
        self.client.get("/health")

    @task(2)
    def list_checks(self):
        self.client.get("/api/checks/", headers=getattr(self,"headers",{}))

    @task(2)
    def search_gost(self):
        self.client.post("/api/gosts/search", json={"query":"ГОСТ 2.104 основная надпись","top_k":3}, headers=getattr(self,"headers",{}))

    @task(1)
    def upload_and_check(self):
        # create small PDF in memory
        im = Image.new("RGB",(600,400),color="white")
        buf = io.BytesIO()
        im.save(buf, format="PDF")
        buf.seek(0)
        files={"file": ("loadtest.pdf", buf.getvalue(), "application/pdf")}
        # Note: requests via locust uses files differently; simulate
        try:
            self.client.post("/api/checks/upload?priority=5", files=files, headers=getattr(self,"headers",{}))
        except: pass

    @task(1)
    def mcp(self):
        self.client.post("/mcp", json={"jsonrpc":"2.0","id":1,"method":"tools/list"})
