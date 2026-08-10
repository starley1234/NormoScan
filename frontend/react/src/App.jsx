import React, { useEffect, useState } from 'react'
export default function App(){
  const [health, setHealth] = useState(null)
  useEffect(()=>{ fetch('/health').then(r=>r.json()).then(setHealth) },[])
  return (
    <div style={{fontFamily:'sans-serif', padding:20}}>
      <h1>📐 НормоСкан — React</h1>
      <p>Альтернативный UI к Streamlit. API: {health ? health.model : 'загрузка...'}</p>
      <p>Контекст: {health?.context_window} токенов | VRAM оптимизация: {health?.vrаm_optimized ? 'ON' : 'OFF'}</p>
      <hr/>
      <p>См. Streamlit: <a href="http://localhost:8501">:8501</a> | API docs: <a href="/docs">/docs</a> | MCP: <a href="/mcp">/mcp</a></p>
    </div>
  )
}
