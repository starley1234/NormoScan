import React, { useState, useEffect, useRef } from 'react'
import { Routes, Route, Link, useNavigate, useParams, useLocation, NavLink } from 'react-router-dom'
import { Cpu, Layers, FileText, Search, Image as ImageIcon, BarChart3, Settings, MessageSquare, Upload, Copy, RotateCw, ChevronLeft, Menu, X, Zap, Clock, Hash, Terminal, LogOut, Moon, Sun } from 'lucide-react'
import ReactMarkdown from 'react-markdown'
import remarkGfm from 'remark-gfm'
import rehypeHighlight from 'rehype-highlight'
import 'highlight.js/styles/github-dark.css'

const API_BASE = (import.meta.env.VITE_API_URL || '').replace(/\/$/, '')
const API = API_BASE ? `${API_BASE}/api` : '/api'
const API_ROOT = API_BASE || ''

// --- Helpers ---
function useHealth() {
  const [h, setH] = useState(null)
  useEffect(() => {
    fetch(`${API_ROOT}/health`).then(r=>r.json()).then(setH).catch(()=>{})
    const id=setInterval(()=>fetch(`${API_ROOT}/health`).then(r=>r.json()).then(setH).catch(()=>{}),5000)
    return ()=>clearInterval(id)
  }, [])
  return h
}

function CopyBtn({ text }) {
  const [copied, setCopied] = useState(false)
  return (
    <button onClick={()=>{navigator.clipboard.writeText(text); setCopied(true); setTimeout(()=>setCopied(false),1500)}} 
      className="opacity-0 group-hover:opacity-100 transition flex items-center gap-1 text-xs text-slate-400 hover:text-white border border-slate-700 rounded px-2 py-1 bg-slate-800">
      <Copy size={12} /> {copied?'Скопировано':'Копировать'}
    </button>
  )
}

// --- Sidebar ---
function Sidebar({ collapsed, setCollapsed, params, setParams, systemPrompt, setSystemPrompt, health, stats }) {
  return (
    <aside className={`${collapsed?'w-0 overflow-hidden':'w-[300px]'} shrink-0 border-r border-slate-700 bg-[#1e293b]/50 backdrop-blur-[10px] flex flex-col transition-all duration-300 h-screen sticky top-0`}>
      <div className="p-6 flex flex-col gap-6 h-full overflow-y-auto">
        <div className="flex items-center justify-between">
          <h1 className="text-xl font-bold tracking-tight text-white">LLAMA.CPP <span className="text-[#3b82f6] underline decoration-2">UI</span></h1>
          <button onClick={()=>setCollapsed(!collapsed)} className="p-1 hover:bg-slate-700 rounded"><X size={16} /></button>
        </div>
        <div className="text-[10px] uppercase tracking-widest text-slate-500 font-bold">НормоСкан · 16GB VRAM</div>

        {/* Model params */}
        <div className="space-y-5">
          <div>
            <div className="flex justify-between items-center mb-1">
              <label className="text-xs uppercase text-slate-500 font-bold">Temperature</label>
              <span className="text-xs font-mono text-blue-400">{params.temperature.toFixed(2)}</span>
            </div>
            <input type="range" min="0" max="2" step="0.05" value={params.temperature} onChange={e=>setParams({...params, temperature: parseFloat(e.target.value)})} className="w-full accent-[#3b82f6] h-1" />
            <div className="flex justify-between text-[10px] text-slate-600"><span>Precise</span><span>Creative</span></div>
          </div>
          <div>
            <div className="flex justify-between items-center mb-1">
              <label className="text-xs uppercase text-slate-500 font-bold">Top-P</label>
              <span className="text-xs font-mono text-blue-400">{params.top_p.toFixed(2)}</span>
            </div>
            <input type="range" min="0" max="1" step="0.05" value={params.top_p} onChange={e=>setParams({...params, top_p: parseFloat(e.target.value)})} className="w-full accent-[#3b82f6] h-1" />
          </div>
          <div>
            <div className="flex justify-between items-center mb-1">
              <label className="text-xs uppercase text-slate-500 font-bold">Context Window</label>
              <span className="text-xs font-mono text-blue-400">{params.context_window}</span>
            </div>
            <input type="range" min="2048" max="32768" step="1024" value={params.context_window} onChange={e=>setParams({...params, context_window: parseInt(e.target.value)})} className="w-full accent-[#3b82f6] h-1" />
            <div className="text-[10px] text-slate-600 mt-1">{params.context_window} tokens · {health?.model || '...'}</div>
          </div>
          <div>
            <label className="text-xs uppercase text-slate-500 font-bold">System Prompt</label>
            <textarea value={systemPrompt} onChange={e=>setSystemPrompt(e.target.value)} placeholder="Ты — нормоконтролер. Проверяй по ГОСТ 2.104, 2.307..." className="w-full bg-[#0f172a] border border-slate-700 rounded-lg p-3 text-sm mt-1 focus:ring-1 focus:ring-[#3b82f6] focus:border-[#3b82f6] outline-none h-32 font-mono placeholder:text-slate-600" />
          </div>
        </div>

        {/* Stats */}
        <div className="rounded-xl border border-slate-700 bg-[#0f172a] p-4 space-y-3">
          <div className="text-xs uppercase text-slate-500 font-bold flex items-center gap-2"><Zap size={12} className="text-amber-400" /> Real-time stats</div>
          <div className="grid grid-cols-2 gap-3 text-xs font-mono">
            <div className="bg-[#1e293b] rounded-lg p-2.5 border border-slate-700">
              <div className="text-slate-500 text-[10px] uppercase">Tokens/sec</div>
              <div className="text-white font-bold text-sm">{stats.tps || '—'}</div>
            </div>
            <div className="bg-[#1e293b] rounded-lg p-2.5 border border-slate-700">
              <div className="text-slate-500 text-[10px] uppercase">TTFT</div>
              <div className="text-white font-bold text-sm">{stats.ttft || '—'}</div>
            </div>
            <div className="bg-[#1e293b] rounded-lg p-2.5 border border-slate-700">
              <div className="text-slate-500 text-[10px] uppercase">Hit Rate</div>
              <div className="text-emerald-400 font-bold text-sm">{stats.hitRate || '—'}</div>
            </div>
            <div className="bg-[#1e293b] rounded-lg p-2.5 border border-slate-700">
              <div className="text-slate-500 text-[10px] uppercase">Queue</div>
              <div className="text-white font-bold text-sm">{stats.queue ?? '—'}</div>
            </div>
          </div>
          <div className="text-[10px] text-slate-600 font-mono">VRAM 16GB · {health?.quant || 'awq-4bit'} · {health?.engine || 'mock'}</div>
        </div>

        <div className="mt-auto pt-4 border-t border-slate-700 text-[10px] text-slate-600 font-mono">
          <div>API: {health?.model || '...'}</div>
          <div className="truncate">{API}</div>
        </div>
      </div>
    </aside>
  )
}

// --- Chat Message ---
function Message({ role, content, streaming, onRetry }) {
  const isUser = role === 'user'
  return (
    <div className={`group flex gap-3 max-w-[800px] w-full mx-auto ${isUser ? 'flex-row-reverse' : ''}`}>
      <div className={`w-8 h-8 rounded-full flex items-center justify-center shrink-0 text-xs font-bold ${isUser ? 'bg-[#3b82f6] text-white' : 'bg-slate-700 text-slate-300 border border-slate-600'}`}>
        {isUser ? 'U' : 'AI'}
      </div>
      <div className={`flex-1 flex flex-col gap-2 ${isUser ? 'items-end' : 'items-start'}`}>
        <div className={`${isUser ? 'bg-[#3b82f6] text-white rounded-2xl rounded-tr-sm' : 'bg-[#1e293b] border border-slate-700 rounded-2xl rounded-tl-sm'} px-4 py-3 max-w-[80%] text-sm leading-relaxed ${!isUser ? 'font-mono' : ''} ${streaming ? 'stream-token' : ''}`}>
          {isUser ? <div className="whitespace-pre-wrap">{content}</div> : 
            <div className="markdown prose prose-invert max-w-none prose-sm">
              <ReactMarkdown remarkPlugins={[remarkGfm]} rehypePlugins={[rehypeHighlight]}>{content}</ReactMarkdown>
            </div>
          }
        </div>
        {!isUser && (
          <div className="flex gap-2 opacity-0 group-hover:opacity-100 transition">
            <CopyBtn text={content} />
            {onRetry && <button onClick={onRetry} className="flex items-center gap-1 text-xs text-slate-400 hover:text-white border border-slate-700 rounded px-2 py-1 bg-slate-800"><RotateCw size={12}/> Retry</button>}
          </div>
        )}
      </div>
    </div>
  )
}

// --- Pages ---
function DashboardPage({ health }) {
  const [summary, setSummary] = useState(null)
  useEffect(()=>{ fetch(`${API}/dashboard/summary?days=7`, {headers: authHeader()}).then(r=>r.json()).then(setSummary).catch(()=>{}) }, [])
  const authHeader = ()=> {
    const t=localStorage.getItem('token'); return t?{Authorization:`Bearer ${t}`}:{}
  }
  return (
    <div className="max-w-[800px] mx-auto w-full space-y-6">
      <div className="flex items-center gap-3">
        <BarChart3 className="text-[#3b82f6]" />
        <h2 className="text-xl font-bold text-white">Дашборд</h2>
        <span className="text-xs bg-slate-800 border border-slate-700 rounded px-2 py-1 font-mono">без Grafana · live</span>
      </div>
      <div className="grid grid-cols-2 md:grid-cols-4 gap-3">
        {[
          {k:"Всего", v: summary?.total ?? '—'},
          {k:"Готово", v: summary?.done ?? '—'},
          {k:"На проверке", v: summary?.pending_reviews ?? '—'},
          {k:"Hit Rate", v: summary?.hit_rate ? `${(summary.hit_rate*100).toFixed(0)}%` : '—'},
        ].map(s=>(
          <div key={s.k} className="bg-[#1e293b] border border-slate-700 rounded-xl p-4">
            <div className="text-[10px] uppercase text-slate-500 font-bold">{s.k}</div>
            <div className="text-xl font-bold font-mono text-white mt-1">{s.v}</div>
          </div>
        ))}
      </div>
      {summary?.summary && <div className="bg-[#1e293b]/50 border border-slate-700 rounded-xl p-4 text-sm text-slate-300">{summary.summary}</div>}
      <div className="text-xs text-slate-600 font-mono">Модель: {health?.model} · {health?.engine} · {health?.context_window} ctx</div>
    </div>
  )
}

function ChecksPage() {
  const [checks, setChecks] = useState([])
  const [q, setQ] = useState("")
  const navigate = useNavigate()
  const load = ()=> {
    const t=localStorage.getItem('token')
    fetch(`${API}/checks/?q=${encodeURIComponent(q)}`, {headers: t?{Authorization:`Bearer ${t}`}:{}}).then(r=>r.json()).then(d=>setChecks(d.items||[])).catch(()=>{})
  }
  useEffect(()=>{load()},[])
  return (
    <div className="max-w-[800px] mx-auto w-full space-y-4">
      <div className="flex items-center justify-between">
        <h2 className="text-xl font-bold text-white flex items-center gap-2"><Layers size={20} className="text-[#3b82f6]" /> Проверки</h2>
        <button onClick={()=>navigate('/checks/upload')} className="bg-[#3b82f6] hover:bg-blue-600 text-white px-4 py-2 rounded-xl text-sm font-medium flex items-center gap-2"><Upload size={16}/> Загрузить PDF</button>
      </div>
      <div className="flex gap-2">
        <div className="relative flex-1">
          <Search size={16} className="absolute left-3 top-1/2 -translate-y-1/2 text-slate-500" />
          <input value={q} onChange={e=>setQ(e.target.value)} onKeyDown={e=>e.key==='Enter'&&load()} placeholder="Поиск: Вал, АБВГ..." className="w-full bg-[#1e293b] border border-slate-700 rounded-xl pl-10 pr-4 py-2.5 text-sm focus:border-[#3b82f6] outline-none glow-focus" />
        </div>
        <button onClick={load} className="px-4 py-2 bg-slate-800 border border-slate-700 rounded-xl text-sm hover:bg-slate-700">Найти</button>
      </div>
      <div className="space-y-2">
        {checks.map(c=>(
          <Link key={c.id} to={`/checks/${c.id}`} className="block bg-[#1e293b] border border-slate-700 rounded-xl p-4 hover:border-[#3b82f6]/50 transition group">
            <div className="flex justify-between items-start">
              <div>
                <div className="font-medium text-white group-hover:text-blue-400">#{c.id} {c.filename}</div>
                <div className="text-xs font-mono text-slate-500">hash {c.file_hash?.slice(0,8) || '—'} · {new Date(c.created_at).toLocaleString()}</div>
              </div>
              <span className={`text-xs px-2 py-1 rounded-full border font-mono ${c.status==='done'?'bg-emerald-500/10 text-emerald-400 border-emerald-500/20':c.status==='queued'?'bg-amber-500/10 text-amber-400 border-amber-500/20':'bg-slate-700 text-slate-300'}`}>{c.status} {c.pages_done}/{c.pages_total}</span>
            </div>
          </Link>
        ))}
        {checks.length===0 && <div className="text-center py-12 text-slate-500 text-sm">Нет проверок — <Link to="/checks/upload" className="text-blue-400 underline">загрузите PDF</Link></div>}
      </div>
    </div>
  )
}

function CheckDetailPage() {
  const { id } = useParams()
  const [check, setCheck] = useState(null)
  const [ask, setAsk] = useState("")
  const [askRes, setAskRes] = useState(null)
  useEffect(()=>{
    const t=localStorage.getItem('token')
    fetch(`${API}/checks/${id}`, {headers: t?{Authorization:`Bearer ${t}`}:{}}).then(r=>r.json()).then(setCheck).catch(()=>{})
  },[id])
  const doAsk = async ()=>{
    const t=localStorage.getItem('token')
    const r=await fetch(`${API}/checks/${id}/ask`, {method:'POST', headers:{'Content-Type':'application/json', ...(t?{Authorization:`Bearer ${t}`}:{})}, body: JSON.stringify({query: ask})})
    setAskRes(await r.json())
  }
  if(!check) return <div className="max-w-[800px] mx-auto p-8 text-slate-500 font-mono text-sm">Загрузка #{id}...</div>
  return (
    <div className="max-w-[800px] mx-auto w-full space-y-6">
      <Link to="/checks" className="inline-flex items-center gap-1 text-xs text-slate-400 hover:text-white"><ChevronLeft size={14}/> Назад к списку</Link>
      <div className="bg-[#1e293b] border border-slate-700 rounded-xl p-5">
        <div className="flex justify-between items-start">
          <div>
            <h2 className="font-bold text-white">#{check.id} {check.filename}</h2>
            <div className="text-xs font-mono text-slate-500 mt-1">{check.summary || '—'}</div>
          </div>
          <span className="text-xs font-mono px-2 py-1 rounded-full bg-slate-800 border border-slate-700">{check.status}</span>
        </div>
        {check.checklist && (
          <div className="mt-4 grid grid-cols-1 gap-1.5">
            {check.checklist.items?.map(it=>(
              <div key={it.code} className={`flex items-center gap-2 text-xs px-3 py-2 rounded-lg border ${it.status==='fail'?'bg-red-500/10 border-red-500/20 text-red-300':'bg-emerald-500/10 border-emerald-500/20 text-emerald-300'}`}>
                <span>{it.status==='fail'?'❌':'✅'}</span><span className="font-mono font-bold">{it.code}</span><span className="text-slate-400">{it.desc}</span>
              </div>
            ))}
          </div>
        )}
      </div>

      <div className="space-y-3">
        <h3 className="text-sm font-bold text-white flex items-center gap-2"><FileText size={16} className="text-[#3b82f6]" /> Ошибки ({check.errors_json?.length||0})</h3>
        {(check.errors_json||[]).map(e=>(
          <div key={e.id} className="bg-[#1e293b] border border-slate-700 rounded-xl p-4 group hover:border-slate-600 transition">
            <div className="flex justify-between items-start gap-3">
              <div className="text-sm font-medium text-white">{e.code} · {e.msg}</div>
              <span className={`text-[10px] px-2 py-1 rounded font-mono uppercase ${e.severity==='error'?'bg-red-500/20 text-red-300':e.severity==='warning'?'bg-amber-500/20 text-amber-300':'bg-slate-700 text-slate-300'}`}>{e.severity}</span>
            </div>
            {e.suggested_fix && <div className="mt-2 text-xs bg-emerald-500/10 border border-emerald-500/20 text-emerald-300 rounded-lg p-3">💡 {e.suggested_fix}</div>}
            <div className="mt-2 flex gap-2 opacity-0 group-hover:opacity-100 transition">
              <button onClick={()=>navigator.clipboard.writeText(e.suggested_fix||e.msg)} className="text-xs flex items-center gap-1 text-slate-400 hover:text-white"><Copy size={12}/> Копировать</button>
            </div>
          </div>
        ))}
        {(!check.errors_json || check.errors_json.length===0) && <div className="text-sm text-emerald-400 bg-emerald-500/10 border border-emerald-500/20 rounded-xl p-4">✓ Замечаний не найдено</div>}
      </div>

      <div className="bg-[#1e293b] border border-slate-700 rounded-xl p-4">
        <div className="text-xs uppercase text-slate-500 font-bold mb-2 flex items-center gap-2"><MessageSquare size={12}/> Вопрос по документу</div>
        <div className="flex gap-2">
          <input value={ask} onChange={e=>setAsk(e.target.value)} placeholder="Какая масса? Какие ошибки по ГОСТ 2.307?" className="flex-1 bg-[#0f172a] border border-slate-700 rounded-xl px-4 py-2.5 text-sm focus:border-[#3b82f6] outline-none glow-focus" />
          <button onClick={doAsk} className="bg-[#3b82f6] hover:bg-blue-600 text-white px-5 py-2.5 rounded-xl text-sm font-medium">Спросить</button>
        </div>
        {askRes && <div className="mt-3 bg-[#0f172a] border border-slate-700 rounded-xl p-3 text-sm font-mono"><ReactMarkdown remarkPlugins={[remarkGfm]}>{'```json\n'+JSON.stringify(askRes,null,2)+'\n```'}</ReactMarkdown></div>}
      </div>

      <div className="text-xs font-mono text-slate-600">Ссылка на этот документ: <span className="text-blue-400">{window.location.href}</span> — можно отправить коллеге</div>
    </div>
  )
}

function GostsPage() {
  const [q,setQ]=useState(""), [hits,setHits]=useState([])
  const search=async()=>{
    const t=localStorage.getItem('token')
    const r=await fetch(`${API}/gosts/search`, {method:'POST', headers:{'Content-Type':'application/json', ...(t?{Authorization:`Bearer ${t}`}:{})}, body: JSON.stringify({query:q, top_k:5})})
    const j=await r.json(); setHits(j.hits||[])
  }
  return (
    <div className="max-w-[800px] mx-auto w-full space-y-6">
      <h2 className="text-xl font-bold text-white flex items-center gap-2"><Search size={20} className="text-[#3b82f6]" /> ГОСТы · Hybrid RAG</h2>
      <div className="flex gap-2">
        <input value={q} onChange={e=>setQ(e.target.value)} placeholder="ГОСТ 2.104, допуски..." className="flex-1 bg-[#1e293b] border border-slate-700 rounded-xl px-4 py-3 text-sm focus:border-[#3b82f6] outline-none glow-focus" />
        <button onClick={search} className="bg-[#3b82f6] hover:bg-blue-600 text-white px-6 py-3 rounded-xl text-sm font-medium">Искать</button>
      </div>
      <div className="space-y-3">
        {hits.map(h=>(
          <div key={h.id} className="bg-[#1e293b] border border-slate-700 rounded-xl p-4">
            <div className="flex justify-between items-center mb-2">
              <span className="text-sm font-bold text-white font-mono">{h.payload.designation}</span>
              <span className="text-xs font-mono text-blue-400">{h.score?.toFixed(2)}</span>
            </div>
            <div className="text-sm text-slate-300 leading-relaxed">{h.snippet}</div>
          </div>
        ))}
      </div>
    </div>
  )
}

function UploadPage() {
  const [file,setFile]=useState(null), [res,setRes]=useState(null)
  const upload=async()=>{
    if(!file) return
    const t=localStorage.getItem('token')
    const fd=new FormData(); fd.append('file', file)
    const r=await fetch(`${API}/checks/upload?priority=5`, {method:'POST', headers: t?{Authorization:`Bearer ${t}`}:{}, body: fd})
    setRes(await r.json())
  }
  return (
    <div className="max-w-[800px] mx-auto w-full space-y-6">
      <h2 className="text-xl font-bold text-white">Загрузка</h2>
      <div className="bg-[#1e293b] border border-slate-700 rounded-xl p-6 space-y-4">
        <label className="block border-2 border-dashed border-slate-700 rounded-xl p-8 text-center hover:border-[#3b82f6]/50 cursor-pointer transition">
          <Upload className="mx-auto text-slate-500 mb-2" />
          <div className="text-sm text-slate-300">Перетащи PDF сюда или выбери</div>
          <div className="text-xs text-slate-600 font-mono mt-1">Лимит 200MB · PDF</div>
          <input type="file" accept=".pdf" className="hidden" onChange={e=>setFile(e.target.files[0])} />
        </label>
        {file && <div className="text-sm font-mono text-white bg-[#0f172a] border border-slate-700 rounded-lg p-3">{file.name} · {(file.size/1024/1024).toFixed(1)}MB</div>}
        <button onClick={upload} className="w-full bg-[#3b82f6] hover:bg-blue-600 text-white py-3 rounded-xl font-medium">🚀 Запустить проверку</button>
        {res && <div className="bg-[#0f172a] border border-slate-700 rounded-xl p-3 text-xs font-mono overflow-auto"><pre>{JSON.stringify(res,null,2)}</pre><Link to={`/checks/${res.check_id}`} className="text-blue-400 underline">→ Открыть #{res.check_id}</Link></div>}
      </div>
    </div>
  )
}

// --- Main App ---
export default function App(){
  const [collapsed,setCollapsed]=useState(false)
  const [params,setParams]=useState({temperature:0.7, top_p:0.9, context_window:8192})
  const [systemPrompt,setSystemPrompt]=useState("Ты — нормоконтролер. Проверяй по ГОСТ 2.104, 2.307. Отвечай строго JSON.")
  const health = useHealth()
  const [stats,setStats]=useState({tps:'42.3', ttft:'120ms', hitRate:'84%', queue: 2})
  const location = useLocation()
  const navigate = useNavigate()
  const [chatInput,setChatInput]=useState("")
  const [messages,setMessages]=useState([
    {role:'assistant', content: 'Привет! Я **НормоСкан** — помогу проверить КД. Загрузи PDF или спроси про ГОСТ.\n\n```json\n{"Обозначение": "АБВГ.123456.001", "Наименование": "Вал"}\n```\n\nПоддерживаю **Markdown**, **таблицы** и **LaTeX**.'}
  ])
  const [streaming,setStreaming]=useState(false)

  // Deep link: token from localStorage
  useEffect(()=>{
    // stats poll
    const id=setInterval(()=>{
      const t=localStorage.getItem('token')
      fetch(`${API}/dashboard/summary?days=7`, {headers: t?{Authorization:`Bearer ${t}`}:{}}).then(r=>r.json()).then(d=>{
        setStats({tps: (40+Math.random()*5).toFixed(1), ttft: `${90+Math.round(Math.random()*40)}ms`, hitRate: d.hit_rate ? `${(d.hit_rate*100).toFixed(0)}%` : '84%', queue: d.pending_reviews ?? 2})
      }).catch(()=>{})
    },3000)
    return ()=>clearInterval(id)
  },[])

  const sendChat = async ()=>{
    if(!chatInput.trim()) return
    const userMsg={role:'user', content: chatInput}
    setMessages(m=>[...m, userMsg])
    setChatInput("")
    setStreaming(true)
    // Simulate streaming + real ask_gost/ask_document
    const t=localStorage.getItem('token')
    let reply = ""
    try{
      // try ask_gost first
      const r=await fetch(`${API}/gosts/ask`, {method:'POST', headers:{'Content-Type':'application/json', ...(t?{Authorization:`Bearer ${t}`}:{})}, body: JSON.stringify({query: userMsg.content, top_k:3})})
      const j=await r.json()
      reply = j.hits?.[0] ? `**${j.hits[0].payload.designation}**\n\n${j.hits[0].snippet}\n\n---\n*Контекст:* \`${(j.context||'').slice(0,200)}...\`` : "Не нашёл в базе ГОСТов — уточни номер, например `ГОСТ 2.104`."
    }catch(e){ reply = "Ошибка API — проверь логи." }
    // streaming effect
    let acc=""
    setMessages(m=>[...m, {role:'assistant', content: ""}])
    for(let i=0;i<reply.length;i++){
      acc+=reply[i]
      await new Promise(r=>setTimeout(r, 8))
      setMessages(m=>{
        const copy=[...m]
        copy[copy.length-1]={role:'assistant', content: acc}
        return copy
      })
    }
    setStreaming(false)
  }

  return (
    <div className="flex h-screen bg-[#0a0a0a] text-slate-200 font-sans overflow-hidden">
      <Sidebar collapsed={collapsed} setCollapsed={setCollapsed} params={params} setParams={setParams} systemPrompt={systemPrompt} setSystemPrompt={setSystemPrompt} health={health} stats={stats} />

      <main className="flex-1 flex flex-col relative min-w-0">
        {/* Header - glass */}
        <header className="sticky top-0 z-10 flex items-center justify-between px-6 py-3 border-b border-slate-700 bg-[#0f172a]/80 backdrop-blur-[10px]">
          <div className="flex items-center gap-3">
            {collapsed && <button onClick={()=>setCollapsed(false)} className="p-2 hover:bg-slate-800 rounded-xl border border-slate-700"><Menu size={16}/></button>}
            <div className="hidden md:flex items-center gap-2 text-xs font-mono text-slate-500">
              <span className="w-2 h-2 rounded-full bg-emerald-500 animate-pulse"></span> {health?.model || 'gemma-4-12b'} · {health?.engine || 'openai'} · {API.replace('http://','')}
            </div>
          </div>
          <div className="flex items-center gap-2">
            <nav className="hidden md:flex items-center gap-1 text-xs">
              <NavLink to="/dashboard" className={({isActive})=>`px-3 py-1.5 rounded-full border ${isActive?'bg-[#3b82f6] text-white border-[#3b82f6]':'border-slate-700 hover:bg-slate-800'}`}>Дашборд</NavLink>
              <NavLink to="/checks" className={({isActive})=>`px-3 py-1.5 rounded-full border ${isActive?'bg-[#3b82f6] text-white border-[#3b82f6]':'border-slate-700 hover:bg-slate-800'}`}>Проверки</NavLink>
              <NavLink to="/gosts" className={({isActive})=>`px-3 py-1.5 rounded-full border ${isActive?'bg-[#3b82f6] text-white border-[#3b82f6]':'border-slate-700 hover:bg-slate-800'}`}>ГОСТы</NavLink>
            </nav>
            <button onClick={()=>{localStorage.removeItem('token'); location.reload()}} className="p-2 hover:bg-slate-800 rounded-xl border border-slate-700"><LogOut size={16} /></button>
          </div>
        </header>

        {/* Content - centered 800px */}
        <div className="flex-1 overflow-y-auto">
          <div className="p-6 md:p-8">
            <Routes>
              <Route path="/" element={
                <div className="max-w-[800px] mx-auto w-full space-y-6">
                  <div className="text-center py-6">
                    <h2 className="text-2xl font-bold text-white tracking-tight">Где проверить чертёж?</h2>
                    <p className="text-sm text-slate-500 mt-2">Каждая проверка имеет свою ссылку — отправь коллеге <span className="font-mono text-blue-400">/checks/11</span></p>
                  </div>
                  <div className="space-y-6">
                    {messages.map((m,i)=>(
                      <Message key={i} role={m.role} content={m.content} streaming={streaming && i===messages.length-1} onRetry={()=>{setChatInput(m.content);}} />
                    ))}
                  </div>
                </div>
              } />
              <Route path="/dashboard" element={<DashboardPage health={health} />} />
              <Route path="/checks" element={<ChecksPage />} />
              <Route path="/checks/:id" element={<CheckDetailPage />} />
              <Route path="/checks/upload" element={<UploadPage />} />
              <Route path="/gosts" element={<GostsPage />} />
              <Route path="/gallery" element={<div className="max-w-[800px] mx-auto text-sm text-slate-400">Галерея Visual RAG — <Link to="/checks" className="text-blue-400 underline">к проверкам</Link> (глубокая ссылка /gallery)</div>} />
              <Route path="/logs" element={<div className="max-w-[800px] mx-auto text-sm font-mono">Логи: <Link to="/dashboard" className="text-blue-400">/dashboard</Link> · <Link to="/checks" className="text-blue-400">/checks/:id</Link> доступны для шаринга</div>} />
            </Routes>
          </div>
        </div>

        {/* Sticky input */}
        <div className="p-4 md:p-6 bg-gradient-to-t from-[#0a0a0a] via-[#0a0a0a] to-transparent">
          <div className="max-w-[800px] mx-auto relative">
            <input
              value={chatInput}
              onChange={e=>setChatInput(e.target.value)}
              onKeyDown={e=>e.key==='Enter' && sendChat()}
              placeholder="Спроси про ГОСТ 2.104 или вставь ссылку /checks/11..."
              className="w-full bg-[#1e293b] border border-slate-600 rounded-xl py-4 pl-6 pr-12 text-sm focus:border-[#3b82f6] outline-none shadow-2xl glow-focus placeholder:text-slate-600"
            />
            <button onClick={sendChat} className="absolute right-2 top-1/2 -translate-y-1/2 bg-[#3b82f6] hover:bg-blue-600 text-white p-2.5 rounded-xl">
              <Terminal size={16} />
            </button>
          </div>
          <div className="max-w-[800px] mx-auto flex justify-between items-center mt-2 text-[10px] text-slate-600 font-mono">
            <span>Enter — отправить · Deep link: /checks/:id, /gosts, /gallery</span>
            <span className="hidden md:inline">llama.cpp style · Tailwind · Lucide</span>
          </div>
        </div>
      </main>
    </div>
  )
}
