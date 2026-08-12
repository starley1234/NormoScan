# API Spec (OpenAPI 3.1)

Base: `http://localhost:8000`

## Auth

```http
POST /api/auth/register
{"username":"ivan","password":"secret","role":"engineer"}

POST /api/auth/login
form: username, password
=> {"access_token":"...","token_type":"bearer"}

GET /api/auth/me
Header: Authorization: Bearer <token>
```

## Checks

```http
POST /api/checks/upload?priority=5
multipart: file (PDF)
=> {"check_id":1,"status":"queued"}

GET /api/checks/?status=done&skip=0&limit=20

GET /api/checks/1
=> {"id":1,"filename":"...","status":"done","meta_json":{...},"errors_json":[...],"summary":"...","pages":[...]}

POST /api/checks/feedback
{"check_id":1,"error_id":"err_1_0_123","vote":"dislike","comment":"false positive"}

POST /api/checks/1/ask
{"query":"Какая масса?"}
=> {"answer":"Масса: 1.2","meta":{...}}
```

## GOSTs

```http
POST /api/gosts/ingest
{"path":"./storage/gosts"}

POST /api/gosts/search
{"query":"требования к основной надписи ГОСТ 2.104","top_k":3}
=> {"hits":[{"payload":{"designation":"ГОСТ 2.104-2006","text":"..."},"score":0.92,"snippet":"..."}]}

POST /api/gosts/ask
{"query":"Что требует ГОСТ 2.307?"}
```

## Gallery (Visual RAG)

```http
POST /api/gallery/upload
multipart: file (png/jpg), title, category=error/etalon, gost_ref, error_type

POST /api/gallery/search
multipart: file (png)
=> {"hits":[{"similarity":0.92,"similarity_percent":92.0,"payload":{"title":"Неверная засечка"}}]}
```

## Analytics

```http
GET /api/analytics/summary?days=30&department=5
=> {"total_checks":42,"top_errors":[{"code":"ГОСТ 2.307","count":12}],"summary":"В отделе №5 ..."}

GET /api/analytics/stats
```

## Admin

```http
GET /api/admin/settings
=> {"vlm_model":"google/gemma-3-12b-it","vlm_quantization":"awq-4bit","max_context_window":8192,"image_width":768,"vram_limit_gb":16}

POST /api/admin/settings
{"max_context_window":16384,"image_width":768}
```

## MCP (Model Context Protocol)

```http
POST /mcp
Content-Type: application/json
{
  "jsonrpc":"2.0",
  "id":1,
  "method":"tools/list"
}
=> {"result":{"tools":[{"name":"check_drawing",...},{"name":"ask_gost",...}]}}

POST /mcp
{
  "jsonrpc":"2.0",
  "id":2,
  "method":"tools/call",
  "params":{"name":"ask_gost","arguments":{"query":"ГОСТ 2.104","top_k":3}}
}
```

Полный Swagger: `/docs` и `/openapi.json`
