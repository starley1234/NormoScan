# MCP (Model Context Protocol) — НормоСкан

MCP позволяет внешним LLM (Claude Desktop, Cursor, Continue, VS Code) использовать НормоСкан как инструмент.

## Эндпоинт

- `POST /mcp` — JSON-RPC 2.0
- `GET /mcp` — info
- Алиасы: `/api/mcp`

## Инструменты

| tool | description | args |
|------|-------------|------|
| `check_drawing` | Проверить чертеж | `file_path` или `check_id`, `priority` |
| `ask_gost` | Вопрос по ГОСТам (RAG) | `query`, `top_k` |
| `ask_document` | Вопрос по документу | `check_id`, `query` |
| `search_gallery` | Поиск по галерее Visual RAG | `image_path`, `top_k` |
| `get_check_status` | Статус проверки | `check_id` |

## Примеры

### tools/list
```json
{"jsonrpc":"2.0","id":1,"method":"tools/list"}
```

### ask_gost
```json
{
  "jsonrpc":"2.0","id":2,"method":"tools/call",
  "params":{"name":"ask_gost","arguments":{"query":"Что требует ГОСТ 2.104 по основной надписи?","top_k":3}}
}
```

### ask_document
```json
{
  "jsonrpc":"2.0","id":3,"method":"tools/call",
  "params":{"name":"ask_document","arguments":{"check_id":1,"query":"Какая масса указана?"}}
}
```

## Конфигурация Claude Desktop

`claude_desktop_config.json`:
```json
{
  "mcpServers": {
    "normoscan": {
      "command": "npx",
      "args": ["-y","mcp-remote","http://localhost:8000/mcp"]
    }
  }
}
```

Для `mcp-remote` нужен Node 18+.

Альтернативно прямой SSE (если проксируете):
```json
{
  "mcpServers": {
    "normoscan": {
      "url": "http://localhost:8000/mcp"
    }
  }
}
```

## Безопасность

- MCP наследует RBAC — добавьте `Authorization: Bearer <token>` в headers mcp-клиента если требуется auth (по умолчанию tools доступны без auth для локальной сети; для prod включите проверку в `mcp_server.py`).
- Весь инференс локальный.

## Тестирование

```bash
curl -X POST http://localhost:8000/mcp -H "Content-Type: application/json" -d '{"jsonrpc":"2.0","id":1,"method":"tools/list"}'
curl -X POST http://localhost:8000/mcp -H "Content-Type: application/json" -d '{"jsonrpc":"2.0","id":2,"method":"tools/call","params":{"name":"ask_gost","arguments":{"query":"ГОСТ 2.307","top_k":2}}}'
```
