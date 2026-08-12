# React Frontend (альтернатива Streamlit)

Streamlit — основной UI (`frontend/app.py`), React — опционально для интеграции.

```
frontend/react/
  src/
    App.jsx  — панель нормоконтролера
    components/
      CheckList.jsx
      CheckDetail.jsx
      GostSearch.jsx
      Gallery.jsx
      Analytics.jsx
      AdminSettings.jsx
  package.json
```

Запуск React (если нужен вместо Streamlit):

```bash
cd frontend/react
npm install
VITE_API_URL=http://localhost:8000 npm run dev -- --host 0.0.0.0 --port 3000
```

Настроен прокси Vite:

```js
// vite.config.js
export default {
  server: {
    host: "0.0.0.0",
    port: 3000,
    proxy: { "/api": "http://localhost:8000", "/mcp": "http://localhost:8000" }
  }
}
```

RBAC и Koseven: React читает `X-Koseven-Role` из куки и JWT из localStorage.

Прицел на Gemma-3-12B: индикатор модели в хедере.
