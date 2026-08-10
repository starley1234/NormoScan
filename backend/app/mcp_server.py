"""
MCP (Model Context Protocol) server for NormoScan.
Exposes tools for external LLMs (Claude Desktop, Cursor etc) to use service.
Implements JSON-RPC 2.0 over HTTP at /mcp
Spec: https://spec.modelcontextprotocol.io/
For simplicity, supports:
 - initialize
 - tools/list
 - tools/call
Tools:
 - check_drawing(file_path, priority)
 - ask_gost(query)
 - ask_document(check_id, query)
 - search_gallery(query_image, top_k)
 - get_check_status(check_id)
"""
from typing import Dict, Any, List
import os, json, logging
from fastapi import APIRouter, Request
from fastapi.responses import JSONResponse
from sqlalchemy.orm import Session
from .db import SessionLocal
from .models.check import Check
from .services.gost_ingest import search_gost
from .services.rag_visual import visual_rag
from .vector_store import vector_store

logger = logging.getLogger(__name__)

TOOLS = [
    {
        "name": "check_drawing",
        "description": "Запустить нормоконтроль чертежа PDF. Требует путь к файлу на сервере или check_id.",
        "inputSchema": {
            "type":"object",
            "properties":{
                "file_path":{"type":"string","description":"Путь к PDF на сервере"},
                "check_id":{"type":"integer","description":"ID уже загруженной проверки"},
                "priority":{"type":"integer","default":5}
            }
        }
    },
    {
        "name": "ask_gost",
        "description": "Вопрос по базе ГОСТов (RAG). Возвращает релевантные фрагменты.",
        "inputSchema":{
            "type":"object",
            "properties":{"query":{"type":"string"},"top_k":{"type":"integer","default":3}},
            "required":["query"]
        }
    },
    {
        "name":"ask_document",
        "description":"Вопрос по уже проверенному документу (метаданные, ошибки, техтребования).",
        "inputSchema":{
            "type":"object",
            "properties":{"check_id":{"type":"integer"},"query":{"type":"string"}},
            "required":["check_id","query"]
        }
    },
    {
        "name":"search_gallery",
        "description":"Поиск по галерее ошибок/эталонов по изображению.",
        "inputSchema":{
            "type":"object","properties":{"image_path":{"type":"string"},"top_k":{"type":"integer","default":5}},
            "required":["image_path"]
        }
    },
    {
        "name":"get_check_status",
        "description":"Статус проверки по ID.",
        "inputSchema":{
            "type":"object","properties":{"check_id":{"type":"integer"}},"required":["check_id"]
        }
    },
]

def tool_check_drawing(args: Dict) -> Dict:
    file_path = args.get("file_path")
    check_id = args.get("check_id")
    db = SessionLocal()
    try:
        if check_id:
            c = db.query(Check).filter(Check.id==check_id).first()
            if not c: return {"error": f"check {check_id} not found"}
            return {"check_id": c.id, "status": c.status, "summary": c.summary, "errors": c.errors_json}
        if file_path and os.path.exists(file_path):
            # create check and enqueue
            from .tasks import enqueue_check, process_check_sync
            # if no DB, create
            c = Check(filename=os.path.basename(file_path), filepath=file_path, status="queued", priority=args.get("priority",5))
            db.add(c); db.commit(); db.refresh(c)
            # try async
            try:
                from .tasks import enqueue_check
                enqueue_check(c.id, priority=c.priority)
            except:
                pass
            return {"check_id": c.id, "status":"queued", "message": "Проверка поставлена в очередь"}
        return {"error": "Need file_path or check_id"}
    finally:
        db.close()

def tool_ask_gost(args: Dict) -> Dict:
    return search_gost(args["query"], top_k=args.get("top_k",3))

def tool_ask_document(args: Dict) -> Dict:
    db = SessionLocal()
    try:
        c = db.query(Check).filter(Check.id==args["check_id"]).first()
        if not c:
            return {"error":"not found"}
        # Simple QA over metadata+errors
        q = args["query"].lower()
        meta = c.meta_json or {}
        errs = c.errors_json or []
        # naive keyword search
        if "масса" in q or "mass" in q:
            return {"answer": f"Масса: {meta.get('Масса','не указана')}", "meta": meta}
        if "обозначение" in q or "designation" in q:
            return {"answer": f"Обозначение: {meta.get('Обозначение')}", "meta": meta}
        if "ошибк" in q or "error" in q:
            return {"answer": f"Найдено {len(errs)} ошибок: " + "; ".join([e.get('msg','') for e in errs[:5]]), "errors": errs}
        if "гост" in q:
            return {"answer": f"Документ проверен на соответствие, найденные коды: {set(e.get('code') for e in errs)}", "errors": errs}
        # fallback: return summary
        return {"answer": c.summary or "Документ проверен", "metadata": meta, "errors": errs}
    finally:
        db.close()

def tool_search_gallery(args: Dict) -> Dict:
    hits = visual_rag.search(args["image_path"], top_k=args.get("top_k",5))
    return {"hits": hits}

def tool_get_status(args: Dict) -> Dict:
    db=SessionLocal()
    try:
        c=db.query(Check).filter(Check.id==args["check_id"]).first()
        if not c: return {"error":"not found"}
        return {"check_id":c.id,"status":c.status,"pages_done":c.pages_done,"pages_total":c.pages_total,"summary":c.summary,"errors":c.errors_json}
    finally: db.close()

TOOL_IMPL = {
    "check_drawing": tool_check_drawing,
    "ask_gost": tool_ask_gost,
    "ask_document": tool_ask_document,
    "search_gallery": tool_search_gallery,
    "get_check_status": tool_get_status,
}

async def handle_mcp(request: Request):
    try:
        body = await request.json()
    except:
        return JSONResponse({"jsonrpc":"2.0","error":{"code":-32700,"message":"Parse error"},"id":None})

    # Support both single and batch
    def handle_one(msg: Dict) -> Dict:
        mid = msg.get("id")
        method = msg.get("method")
        params = msg.get("params",{})
        if method=="initialize":
            return {"jsonrpc":"2.0","id":mid,"result":{"protocolVersion":"2024-11-05","capabilities":{"tools":{}},"serverInfo":{"name":"normoscan-mcp","version":"1.0.0"}}}
        if method=="tools/list":
            return {"jsonrpc":"2.0","id":mid,"result":{"tools": TOOLS}}
        if method=="tools/call":
            name = params.get("name")
            args = params.get("arguments",{})
            fn = TOOL_IMPL.get(name)
            if not fn:
                return {"jsonrpc":"2.0","id":mid,"error":{"code":-32601,"message":f"Tool {name} not found"}}
            try:
                res = fn(args)
                return {"jsonrpc":"2.0","id":mid,"result":{"content":[{"type":"text","text": json.dumps(res, ensure_ascii=False, indent=2)}]}}
            except Exception as e:
                logger.exception(e)
                return {"jsonrpc":"2.0","id":mid,"error":{"code":-32603,"message":str(e)}}
        if method=="ping":
            return {"jsonrpc":"2.0","id":mid,"result":{}}
        return {"jsonrpc":"2.0","id":mid,"error":{"code":-32601,"message":f"Method {method} not found"}}

    if isinstance(body, list):
        res = [handle_one(m) for m in body]
        return JSONResponse(res)
    else:
        return JSONResponse(handle_one(body))

# Also expose SSE/HTTP for simple tool discovery (GET /mcp)
def mcp_info():
    return {"name":"normoscan-mcp","version":"1.0.0","tools":[t["name"] for t in TOOLS],"protocol":"2024-11-05"}
