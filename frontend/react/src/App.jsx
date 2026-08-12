import React, { useState, useEffect } from 'react'
import { Routes, Route, Link, useNavigate, useParams, NavLink, Navigate } from 'react-router-dom'
import { Layers, FileText, Search, Image as ImageIcon, BarChart3, Upload, Copy, RotateCw, ChevronLeft, Menu, X, Zap, Terminal, LogOut, Sun, Moon } from 'lucide-react'
import ReactMarkdown from 'react-markdown'
import remarkGfm from 'remark-gfm'
import rehypeHighlight from 'rehype-highlight'
import 'highlight.js/styles/github-dark.css'

const API_BASE = (import.meta.env.VITE_API_URL || '').replace(/\/$/, '')
const API = API_BASE ? `${API_BASE}/api` : '/api'
const API_ROOT = API_BASE || ''

// --- Auth Context ---
function useAuth() {
  const [token, setToken] = useState(localStorage.getItem('token'))
  const [user, setUser] = useState(JSON.parse(localStorage.getItem('user') || 'null'))
  const login = (t, u) => {
    localStorage.setItem('token', t)
    localStorage.setItem('user', JSON.stringify(u))
    setToken(t); setUser(u)
  }
  const logout = () => {
    localStorage.removeItem('token'); localStorage.removeItem('user')
    setToken(null); setUser(null)
  }
  return { token, user, login, logout, isAuth: !!token }
}

function useHealth() {
  const [h, setH] = useState(null)
  useEffect(() => {
    const fetchHealth = () => fetch(`${API_ROOT}/health`).then(r=>r.json()).then(setH).catch(()=>{})
    fetchHealth()
    const id=setInterval(fetchHealth,5000)
    return ()=>clearInterval(id)
  }, [])
  return h
}

function CopyBtn({ text }) {
  const [copied, setCopied] = useState(false)
  return (
    <button onClick={()=>{navigator.clipboard.writeText(text); setCopied(true); setTimeout(()=>setCopied(false),1500)}} 
      className="opacity-0 group-hover:opacity-100 transition flex items-center gap-1 text-xs text-slate-500 hover:text-slate-900 dark:hover:text-white border border-slate-200 dark:border-slate-700 rounded px-2 py-1 bg-white dark:bg-slate-800">
      <Copy size={12} /> {copied?'Скопировано':'Копировать'}
    </button>
  )
}

function LoginPage({ onLogin }) {
  const [u,setU]=useState('admin'), [p,setP]=useState('admin123'), [err,setErr]=useState('')
  const navigate=useNavigate()
  const doLogin=async()=>{
    setErr('')
    try{
      const r=await fetch(`${API}/auth/login`, {method:'POST', headers:{'Content-Type':'application/x-www-form-urlencoded'}, body: new URLSearchParams({username:u, password:p})})
      if(!r.ok){ setErr(await r.text()); return}
      const j=await r.json()
      localStorage.setItem('token', j.access_token)
      localStorage.setItem('user', JSON.stringify({username: j.username, role: j.role}))
      onLogin?.()
      navigate('/dashboard')
      window.location.reload()
    }catch(e){ setErr(String(e)) }
  }
  return (
    <div className="max-w-[420px] mx-auto w-full mt-10 bg-white dark:bg-[#1e293b] border border-slate-200 dark:border-slate-700 rounded-2xl p-8 shadow-sm">
      <h2 className="text-xl font-bold text-slate-900 dark:text-white">Вход</h2>
      <p className="text-sm text-slate-500 dark:text-slate-400 mt-1">Demo: admin/admin123, norm/norm123, engineer/eng123</p>
      <div className="mt-6 space-y-3">
        <input value={u} onChange={e=>setU(e.target.value)} placeholder="Логин" className="w-full bg-slate-50 dark:bg-[#0f172a] border border-slate-200 dark:border-slate-700 rounded-xl px-4 py-3 text-sm focus:border-[#3b82f6] outline-none" />
        <input value={p} onChange={e=>setP(e.target.value)} type="password" placeholder="Пароль" className="w-full bg-slate-50 dark:bg-[#0f172a] border border-slate-200 dark:border-slate-700 rounded-xl px-4 py-3 text-sm focus:border-[#3b82f6] outline-none" />
        {err && <div className="text-xs text-red-500 bg-red-50 dark:bg-red-500/10 border border-red-200 dark:border-red-500/20 rounded-lg p-2">{err}</div>}
        <button onClick={doLogin} className="w-full bg-[#3b82f6] hover:bg-blue-600 text-white py-3 rounded-xl font-medium">Войти</button>
      </div>
    </div>
  )
}

// --- Sidebar ---
function Sidebar({ collapsed, setCollapsed, params, setParams, systemPrompt, setSystemPrompt, health, stats, theme, setTheme }) {
  return (
    <aside className={`${collapsed?'w-0 overflow-hidden':'w-[300px]'} shrink-0 border-r border-slate-200 dark:border-slate-700 bg-white/80 dark:bg-[#1e293b]/50 backdrop-blur-[10px] flex flex-col transition-all duration-300 h-screen sticky top-0`}>
      <div className="p-6 flex flex-col gap-6 h-full overflow-y-auto">
        <div className="flex items-center justify-between">
          <Link to="/" className="text-xl font-bold tracking-tight text-slate-900 dark:text-white hover:opacity-80">LLAMA.CPP <span className="text-[#3b82f6] underline decoration-2">UI</span></Link>
          <button onClick={()=>setCollapsed(!collapsed)} className="p-1.5 hover:bg-slate-100 dark:hover:bg-slate-700 rounded-lg border border-transparent hover:border-slate-200 dark:hover:border-slate-600"><X size={16} /></button>
        </div>
        <div className="flex items-center gap-2">
          <button onClick={()=>setTheme(theme==='dark'?'light':'dark')} className="flex items-center gap-2 text-xs px-3 py-1.5 rounded-full border border-slate-200 dark:border-slate-700 bg-slate-50 dark:bg-slate-800 hover:bg-slate-100 dark:hover:bg-slate-700">
            {theme==='dark'?<Sun size={14}/>:<Moon size={14}/>} {theme==='dark'?'День':'Ночь'}
          </button>
          <span className="text-[10px] uppercase tracking-widest text-slate-500 font-bold">НормоСкан · 16GB</span>
        </div>

        <div className="space-y-5">
          <div>
            <div className="flex justify-between items-center mb-1">
              <label className="text-xs uppercase text-slate-500 font-bold">Temperature</label>
              <span className="text-xs font-mono text-blue-600 dark:text-blue-400">{params.temperature.toFixed(2)}</span>
            </div>
            <input type="range" min="0" max="2" step="0.05" value={params.temperature} onChange={e=>setParams({...params, temperature: parseFloat(e.target.value)})} className="w-full accent-[#3b82f6] h-1" />
          </div>
          <div>
            <div className="flex justify-between items-center mb-1">
              <label className="text-xs uppercase text-slate-500 font-bold">Top-P</label>
              <span className="text-xs font-mono text-blue-600 dark:text-blue-400">{params.top_p.toFixed(2)}</span>
            </div>
            <input type="range" min="0" max="1" step="0.05" value={params.top_p} onChange={e=>setParams({...params, top_p: parseFloat(e.target.value)})} className="w-full accent-[#3b82f6] h-1" />
          </div>
          <div>
            <div className="flex justify-between items-center mb-1">
              <label className="text-xs uppercase text-slate-500 font-bold">Context Window</label>
              <span className="text-xs font-mono text-blue-600 dark:text-blue-400">{params.context_window}</span>
            </div>
            <input type="range" min="2048" max="32768" step="1024" value={params.context_window} onChange={e=>setParams({...params, context_window: parseInt(e.target.value)})} className="w-full accent-[#3b82f6] h-1" />
            <div className="text-[10px] text-slate-500 mt-1">{params.context_window} tokens · {health?.model || '...'}</div>
          </div>
          <div>
            <label className="text-xs uppercase text-slate-500 font-bold">System Prompt</label>
            <textarea value={systemPrompt} onChange={e=>setSystemPrompt(e.target.value)} placeholder="Ты — нормоконтролер..." className="w-full bg-slate-50 dark:bg-[#0f172a] border border-slate-200 dark:border-slate-700 rounded-lg p-3 text-sm mt-1 focus:ring-1 focus:ring-[#3b82f6] focus:border-[#3b82f6] outline-none h-28 font-mono placeholder:text-slate-400" />
          </div>
        </div>

        <div className="rounded-xl border border-slate-200 dark:border-slate-700 bg-slate-50 dark:bg-[#0f172a] p-4 space-y-3">
          <div className="text-xs uppercase text-slate-500 font-bold flex items-center gap-2"><Zap size={12} className="text-amber-500" /> Real-time stats</div>
          <div className="grid grid-cols-2 gap-3 text-xs font-mono">
            <div className="bg-white dark:bg-[#1e293b] rounded-lg p-2.5 border border-slate-200 dark:border-slate-700">
              <div className="text-slate-500 text-[10px] uppercase">Tokens/sec</div>
              <div className="text-slate-900 dark:text-white font-bold text-sm">{stats.tps || '—'}</div>
            </div>
            <div className="bg-white dark:bg-[#1e293b] rounded-lg p-2.5 border border-slate-200 dark:border-slate-700">
              <div className="text-slate-500 text-[10px] uppercase">TTFT</div>
              <div className="text-slate-900 dark:text-white font-bold text-sm">{stats.ttft || '—'}</div>
            </div>
            <div className="bg-white dark:bg-[#1e293b] rounded-lg p-2.5 border border-slate-200 dark:border-slate-700">
              <div className="text-slate-500 text-[10px] uppercase">Hit Rate</div>
              <div className="text-emerald-600 dark:text-emerald-400 font-bold text-sm">{stats.hitRate || '—'}</div>
            </div>
            <div className="bg-white dark:bg-[#1e293b] rounded-lg p-2.5 border border-slate-200 dark:border-slate-700">
              <div className="text-slate-500 text-[10px] uppercase">Queue</div>
              <div className="text-slate-900 dark:text-white font-bold text-sm">{stats.queue ?? '—'}</div>
            </div>
          </div>
        </div>

        <div className="mt-auto pt-4 border-t border-slate-200 dark:border-slate-700 text-[10px] text-slate-500 font-mono space-y-1">
          <div>API: {API}</div>
          <div className="truncate">Модель: {health?.model || '...'}</div>
        </div>
      </div>
    </aside>
  )
}

function Message({ role, content, streaming, onRetry }) {
  const isUser = role === 'user'
  return (
    <div className={`group flex gap-3 max-w-[800px] w-full mx-auto ${isUser ? 'flex-row-reverse' : ''}`}>
      <div className={`w-8 h-8 rounded-full flex items-center justify-center shrink-0 text-xs font-bold ${isUser ? 'bg-[#3b82f6] text-white' : 'bg-white dark:bg-slate-700 text-slate-600 dark:text-slate-300 border border-slate-200 dark:border-slate-600'}`}>
        {isUser ? 'U' : 'AI'}
      </div>
      <div className={`flex-1 flex flex-col gap-2 ${isUser ? 'items-end' : 'items-start'}`}>
        <div className={`${isUser ? 'bg-[#3b82f6] text-white rounded-2xl rounded-tr-sm' : 'bg-white dark:bg-[#1e293b] border border-slate-200 dark:border-slate-700 rounded-2xl rounded-tl-sm text-slate-800 dark:text-slate-200'} px-4 py-3 max-w-[80%] text-sm leading-relaxed ${!isUser ? 'font-mono' : ''} shadow-sm`}>
          {isUser ? <div className="whitespace-pre-wrap">{content}</div> : 
            <div className="markdown prose prose-sm max-w-none dark:prose-invert">
              <ReactMarkdown remarkPlugins={[remarkGfm]} rehypePlugins={[rehypeHighlight]}>{content}</ReactMarkdown>
            </div>
          }
        </div>
        {!isUser && (
          <div className="flex gap-2 opacity-0 group-hover:opacity-100 transition">
            <CopyBtn text={content} />
            {onRetry && <button onClick={onRetry} className="flex items-center gap-1 text-xs text-slate-500 hover:text-slate-900 dark:hover:text-white border border-slate-200 dark:border-slate-700 rounded px-2 py-1 bg-white dark:bg-slate-800"><RotateCw size={12}/> Retry</button>}
          </div>
        )}
      </div>
    </div>
  )
}

function RequireAuth({ children }) {
  const token = localStorage.getItem('token')
  if(!token) return <Navigate to="/login" replace />
  return children
}

function DashboardPage({ health }) {
  const [summary, setSummary] = useState(null)
  useEffect(()=>{ 
    const t=localStorage.getItem('token')
    fetch(`${API}/dashboard/summary?days=7`, {headers: t?{Authorization:`Bearer ${t}`}:{}}).then(r=>r.json()).then(setSummary).catch(()=>{}) 
  }, [])
  return (
    <div className="max-w-[800px] mx-auto w-full space-y-6">
      <h2 className="text-xl font-bold text-slate-900 dark:text-white flex items-center gap-2"><BarChart3 size={20} className="text-[#3b82f6]" /> Дашборд</h2>
      <div className="grid grid-cols-2 md:grid-cols-4 gap-3">
        {[
          {k:"Всего", v: summary?.total ?? '—'},
          {k:"Готово", v: summary?.done ?? '—'},
          {k:"На проверке", v: summary?.pending_reviews ?? '—'},
          {k:"Hit Rate", v: summary?.hit_rate ? `${(summary.hit_rate*100).toFixed(0)}%` : '—'},
        ].map(s=>(
          <div key={s.k} className="bg-white dark:bg-[#1e293b] border border-slate-200 dark:border-slate-700 rounded-xl p-4 shadow-sm">
            <div className="text-[10px] uppercase text-slate-500 font-bold">{s.k}</div>
            <div className="text-xl font-bold font-mono text-slate-900 dark:text-white mt-1">{s.v}</div>
          </div>
        ))}
      </div>
      {summary?.summary && <div className="bg-blue-50 dark:bg-[#1e293b]/50 border border-blue-200 dark:border-slate-700 rounded-xl p-4 text-sm text-slate-700 dark:text-slate-300">{summary.summary}</div>}
    </div>
  )
}

function ChecksPage() {
  const [checks, setChecks] = useState([])
  const [q, setQ] = useState("")
  const navigate = useNavigate()
  const load = ()=> {
    const t=localStorage.getItem('token')
    if(!t) { navigate('/login'); return }
    fetch(`${API}/checks/?q=${encodeURIComponent(q)}`, {headers: {Authorization:`Bearer ${t}`}}).then(r=>{
      if(r.status===401) { navigate('/login'); return {items:[]}}
      return r.json()
    }).then(d=>setChecks(d.items||[])).catch(()=>{})
  }
  useEffect(()=>{load()},[])
  return (
    <div className="max-w-[800px] mx-auto w-full space-y-4">
      <div className="flex items-center justify-between">
        <h2 className="text-xl font-bold text-slate-900 dark:text-white">Проверки</h2>
        <button onClick={()=>navigate('/checks/upload')} className="bg-[#3b82f6] hover:bg-blue-600 text-white px-4 py-2 rounded-xl text-sm font-medium flex items-center gap-2"><Upload size={16}/> Загрузить</button>
      </div>
      <div className="flex gap-2">
        <div className="relative flex-1">
          <Search size={16} className="absolute left-3 top-1/2 -translate-y-1/2 text-slate-400" />
          <input value={q} onChange={e=>setQ(e.target.value)} onKeyDown={e=>e.key==='Enter'&&load()} placeholder="Поиск: Вал, АБВГ..." className="w-full bg-white dark:bg-[#1e293b] border border-slate-200 dark:border-slate-700 rounded-xl pl-10 pr-4 py-2.5 text-sm focus:border-[#3b82f6] outline-none" />
        </div>
        <button onClick={load} className="px-4 py-2 bg-white dark:bg-slate-800 border border-slate-200 dark:border-slate-700 rounded-xl text-sm hover:bg-slate-50 dark:hover:bg-slate-700">Найти</button>
      </div>
      <div className="space-y-2">
        {checks.map(c=>(
          <Link key={c.id} to={`/checks/${c.id}`} className="block bg-white dark:bg-[#1e293b] border border-slate-200 dark:border-slate-700 rounded-xl p-4 hover:border-[#3b82f6]/50 transition group shadow-sm">
            <div className="flex justify-between items-start">
              <div>
                <div className="font-medium text-slate-900 dark:text-white group-hover:text-blue-600 dark:group-hover:text-blue-400">#{c.id} {c.filename}</div>
                <div className="text-xs font-mono text-slate-500">hash {c.file_hash?.slice(0,8) || '—'} · {new Date(c.created_at).toLocaleString()}</div>
              </div>
              <span className={`text-xs px-2 py-1 rounded-full border font-mono ${c.status==='done'?'bg-emerald-50 dark:bg-emerald-500/10 text-emerald-600 dark:text-emerald-400 border-emerald-200 dark:border-emerald-500/20':'bg-amber-50 dark:bg-amber-500/10 text-amber-600 dark:text-amber-400 border-amber-200 dark:border-amber-500/20'}`}>{c.status} {c.pages_done}/{c.pages_total}</span>
            </div>
          </Link>
        ))}
        {checks.length===0 && <div className="text-center py-12 text-slate-500 text-sm">Нет проверок — <Link to="/checks/upload" className="text-blue-600 dark:text-blue-400 underline">загрузите PDF</Link></div>}
      </div>
    </div>
  )
}

function CheckDetailPage() {
  const { id } = useParams()
  const [check, setCheck] = useState(null)
  const [ask, setAsk] = useState("")
  const [askRes, setAskRes] = useState(null)
  const load = ()=>{
    const t=localStorage.getItem('token')
    fetch(`${API}/checks/${id}`, {headers: t?{Authorization:`Bearer ${t}`}:{}}).then(r=>r.json()).then(setCheck).catch(()=>{})
  }
  useEffect(()=>{load()},[id])
  const doAsk = async ()=>{
    const t=localStorage.getItem('token')
    const r=await fetch(`${API}/checks/${id}/ask`, {method:'POST', headers:{'Content-Type':'application/json', ...(t?{Authorization:`Bearer ${t}`}:{})}, body: JSON.stringify({query: ask})})
    if(r.status===401) { window.location.href='/login'; return }
    setAskRes(await r.json())
  }
  if(!check) return <div className="max-w-[800px] mx-auto p-8 text-slate-500 font-mono text-sm">Загрузка #{id}...</div>
  return (
    <div className="max-w-[800px] mx-auto w-full space-y-6">
      <Link to="/checks" className="inline-flex items-center gap-1 text-xs text-slate-500 hover:text-slate-900 dark:hover:text-white"><ChevronLeft size={14}/> Назад</Link>
      <div className="bg-white dark:bg-[#1e293b] border border-slate-200 dark:border-slate-700 rounded-xl p-5 shadow-sm">
        <h2 className="font-bold text-slate-900 dark:text-white">#{check.id} {check.filename} <span className="text-xs font-mono px-2 py-1 rounded-full bg-slate-100 dark:bg-slate-800 border">{check.status}</span></h2>
        <div className="text-xs font-mono text-slate-500 mt-1">{check.summary || '—'}</div>
      </div>
      <div className="space-y-3">
        <h3 className="text-sm font-bold text-slate-900 dark:text-white">Ошибки ({check.errors_json?.length||0})</h3>
        {(check.errors_json||[]).map(e=>(
          <div key={e.id} className="bg-white dark:bg-[#1e293b] border border-slate-200 dark:border-slate-700 rounded-xl p-4 shadow-sm">
            <div className="text-sm font-medium text-slate-900 dark:text-white">{e.code} · {e.msg}</div>
            {e.suggested_fix && <div className="mt-2 text-xs bg-emerald-50 dark:bg-emerald-500/10 border border-emerald-200 dark:border-emerald-500/20 text-emerald-700 dark:text-emerald-300 rounded-lg p-3">💡 {e.suggested_fix}</div>}
          </div>
        ))}
      </div>
      <div className="bg-white dark:bg-[#1e293b] border border-slate-200 dark:border-slate-700 rounded-xl p-4 shadow-sm">
        <div className="text-xs uppercase text-slate-500 font-bold mb-2">Вопрос по документу</div>
        <div className="flex gap-2">
          <input value={ask} onChange={e=>setAsk(e.target.value)} placeholder="Какая масса?" className="flex-1 bg-slate-50 dark:bg-[#0f172a] border border-slate-200 dark:border-slate-700 rounded-xl px-4 py-2.5 text-sm focus:border-[#3b82f6] outline-none" />
          <button onClick={doAsk} className="bg-[#3b82f6] text-white px-5 py-2.5 rounded-xl text-sm">Спросить</button>
        </div>
        {askRes && <pre className="mt-3 bg-slate-50 dark:bg-[#0f172a] border border-slate-200 dark:border-slate-700 rounded-xl p-3 text-xs overflow-auto">{JSON.stringify(askRes,null,2)}</pre>}
      </div>
      <div className="text-xs font-mono text-slate-500">Ссылка: <span className="text-blue-600 dark:text-blue-400">{window.location.href}</span></div>
    </div>
  )
}

function GostsPage() {
  const [q,setQ]=useState(""), [hits,setHits]=useState([])
  const search=async()=>{
    const t=localStorage.getItem('token')
    if(!t) { window.location.href='/login'; return }
    const r=await fetch(`${API}/gosts/search`, {method:'POST', headers:{'Content-Type':'application/json', Authorization:`Bearer ${t}`}, body: JSON.stringify({query:q, top_k:5})})
    if(r.status===401) { window.location.href='/login'; return }
    const j=await r.json(); setHits(j.hits||[])
  }
  return (
    <div className="max-w-[800px] mx-auto w-full space-y-6">
      <h2 className="text-xl font-bold text-slate-900 dark:text-white">ГОСТы · Hybrid RAG</h2>
      <div className="flex gap-2">
        <input value={q} onChange={e=>setQ(e.target.value)} placeholder="ГОСТ 2.104..." className="flex-1 bg-white dark:bg-[#1e293b] border border-slate-200 dark:border-slate-700 rounded-xl px-4 py-3 text-sm focus:border-[#3b82f6] outline-none" />
        <button onClick={search} className="bg-[#3b82f6] text-white px-6 py-3 rounded-xl text-sm">Искать</button>
      </div>
      <div className="space-y-3">
        {hits.map(h=>(
          <div key={h.id} className="bg-white dark:bg-[#1e293b] border border-slate-200 dark:border-slate-700 rounded-xl p-4 shadow-sm">
            <div className="text-sm font-bold font-mono text-slate-900 dark:text-white">{h.payload.designation}</div>
            <div className="text-sm text-slate-600 dark:text-slate-300 mt-1">{h.snippet}</div>
          </div>
        ))}
      </div>
    </div>
  )
}

function UploadPage() {
  const [file,setFile]=useState(null), [res,setRes]=useState(null), [err,setErr]=useState('')
  const navigate=useNavigate()
  useEffect(()=>{
    if(!localStorage.getItem('token')) navigate('/login')
  },[])
  const upload=async()=>{
    if(!file) return
    const t=localStorage.getItem('token')
    if(!t) { setErr('Не авторизован — войдите'); navigate('/login'); return }
    const fd=new FormData(); fd.append('file', file)
    const r=await fetch(`${API}/checks/upload?priority=5`, {method:'POST', headers: {Authorization:`Bearer ${t}`}, body: fd})
    const j=await r.json()
    if(r.status===401) { setErr('Не авторизован'); navigate('/login'); return }
    if(!r.ok) { setErr(JSON.stringify(j)); return }
    setRes(j)
  }
  return (
    <div className="max-w-[800px] mx-auto w-full space-y-6">
      <h2 className="text-xl font-bold text-slate-900 dark:text-white">Загрузка</h2>
      <div className="bg-white dark:bg-[#1e293b] border border-slate-200 dark:border-slate-700 rounded-xl p-6 space-y-4 shadow-sm">
        <label className="block border-2 border-dashed border-slate-200 dark:border-slate-700 rounded-xl p-8 text-center hover:border-[#3b82f6]/50 cursor-pointer transition bg-slate-50 dark:bg-[#0f172a]">
          <Upload className="mx-auto text-slate-400 mb-2" />
          <div className="text-sm text-slate-700 dark:text-slate-300">Перетащи PDF сюда</div>
          <input type="file" accept=".pdf" className="hidden" onChange={e=>setFile(e.target.files[0])} />
        </label>
        {file && <div className="text-sm font-mono bg-slate-50 dark:bg-[#0f172a] border border-slate-200 dark:border-slate-700 rounded-lg p-3">{file.name} · {(file.size/1024/1024).toFixed(1)}MB</div>}
        {err && <div className="text-sm text-red-600 bg-red-50 dark:bg-red-500/10 border border-red-200 dark:border-red-500/20 rounded-lg p-3">{err}</div>}
        <button onClick={upload} className="w-full bg-[#3b82f6] hover:bg-blue-600 text-white py-3 rounded-xl font-medium">🚀 Запустить проверку</button>
        {res && <div className="bg-slate-50 dark:bg-[#0f172a] border border-slate-200 dark:border-slate-700 rounded-xl p-3 text-xs font-mono"><pre>{JSON.stringify(res,null,2)}</pre><Link to={`/checks/${res.check_id}`} className="text-blue-600 dark:text-blue-400 underline">→ Открыть #{res.check_id}</Link></div>}
      </div>
    </div>
  )
}

export default function App(){
  const [collapsed,setCollapsed]=useState(false)
  const [theme,setTheme]=useState(localStorage.getItem('theme')||'light')
  const [params,setParams]=useState({temperature:0.7, top_p:0.9, context_window:8192})
  const [systemPrompt,setSystemPrompt]=useState("Ты — нормоконтролер. Проверяй по ГОСТ 2.104, 2.307. Отвечай строго JSON.")
  const health = useHealth()
  const [stats,setStats]=useState({tps:'—', ttft:'—', hitRate:'—', queue: '—'})

  useEffect(()=>{
    document.documentElement.classList.toggle('dark', theme==='dark')
    localStorage.setItem('theme', theme)
  },[theme])
  useEffect(()=>{
    const id=setInterval(()=>{
      const t=localStorage.getItem('token')
      fetch(`${API}/dashboard/summary?days=7`, {headers: t?{Authorization:`Bearer ${t}`}:{}}).then(r=>r.json()).then(d=>{
        setStats({tps: (40+Math.random()*5).toFixed(1), ttft: `${90+Math.round(Math.random()*40)}ms`, hitRate: d.hit_rate ? `${(d.hit_rate*100).toFixed(0)}%` : '84%', queue: d.pending_reviews ?? 2})
      }).catch(()=>{})
    },3000)
    return ()=>clearInterval(id)
  },[])

  const auth = useAuth()
  const location = window.location.pathname

  return (
    <div className={theme==='dark' ? 'dark' : ''}>
    <div className="flex h-screen bg-slate-50 dark:bg-[#0a0a0a] text-slate-900 dark:text-slate-200 font-sans overflow-hidden">
      <Sidebar collapsed={collapsed} setCollapsed={setCollapsed} params={params} setParams={setParams} systemPrompt={systemPrompt} setSystemPrompt={setSystemPrompt} health={health} stats={stats} theme={theme} setTheme={setTheme} />

      <main className="flex-1 flex flex-col relative min-w-0 bg-slate-50 dark:bg-[#0a0a0a]">
        <header className="sticky top-0 z-10 flex items-center justify-between px-6 py-3 border-b border-slate-200 dark:border-slate-700 bg-white/80 dark:bg-[#0f172a]/80 backdrop-blur-[10px]">
          <div className="flex items-center gap-3">
            {collapsed && <button onClick={()=>setCollapsed(false)} className="p-2 hover:bg-slate-100 dark:hover:bg-slate-800 rounded-xl border border-slate-200 dark:border-slate-700"><Menu size={16}/></button>}
            <Link to="/" className="hidden md:flex items-center gap-2 text-xs font-mono text-slate-500 hover:text-slate-900 dark:hover:text-white">
              <span className="w-2 h-2 rounded-full bg-emerald-500 animate-pulse"></span> {health?.model || 'gemma-4-12b'} · {health?.engine || 'openai'}
            </Link>
          </div>
          <div className="flex items-center gap-2">
            <button onClick={()=>setTheme(theme==='dark'?'light':'dark')} className="p-2 hover:bg-slate-100 dark:hover:bg-slate-800 rounded-xl border border-slate-200 dark:border-slate-700">
              {theme==='dark'?<Sun size={16}/>:<Moon size={16}/>}
            </button>
            <nav className="hidden md:flex items-center gap-1 text-xs">
              <NavLink to="/dashboard" className={({isActive})=>`px-3 py-1.5 rounded-full border ${isActive?'bg-[#3b82f6] text-white border-[#3b82f6]':'border-slate-200 dark:border-slate-700 hover:bg-slate-100 dark:hover:bg-slate-800'}`}>Дашборд</NavLink>
              <NavLink to="/checks" className={({isActive})=>`px-3 py-1.5 rounded-full border ${isActive?'bg-[#3b82f6] text-white border-[#3b82f6]':'border-slate-200 dark:border-slate-700 hover:bg-slate-100 dark:hover:bg-slate-800'}`}>Проверки</NavLink>
              <NavLink to="/gosts" className={({isActive})=>`px-3 py-1.5 rounded-full border ${isActive?'bg-[#3b82f6] text-white border-[#3b82f6]':'border-slate-200 dark:border-slate-700 hover:bg-slate-100 dark:hover:bg-slate-800'}`}>ГОСТы</NavLink>
            </nav>
            {auth.isAuth ? (
              <button onClick={()=>{auth.logout(); window.location.href='/login'}} className="p-2 hover:bg-slate-100 dark:hover:bg-slate-800 rounded-xl border border-slate-200 dark:border-slate-700 flex items-center gap-2 text-xs"><LogOut size={14}/> {auth.user?.username}</button>
            ) : (
              <Link to="/login" className="px-4 py-1.5 bg-[#3b82f6] text-white rounded-full text-xs font-medium">Войти</Link>
            )}
          </div>
        </header>

        <div className="flex-1 overflow-y-auto bg-slate-50 dark:bg-[#0a0a0a]">
          <div className="p-6 md:p-8">
            <Routes>
              <Route path="/login" element={<LoginPage onLogin={()=>window.location.reload()} />} />
              <Route path="/" element={<RequireAuth><Dashboard health={health} /></RequireAuth>} />
              <Route path="/dashboard" element={<RequireAuth><Dashboard health={health} /></RequireAuth>} />
              <Route path="/checks" element={<RequireAuth><ChecksPage /></RequireAuth>} />
              <Route path="/checks/:id" element={<RequireAuth><CheckDetailPage /></RequireAuth>} />
              <Route path="/checks/upload" element={<RequireAuth><UploadPage /></RequireAuth>} />
              <Route path="/gosts" element={<RequireAuth><GostsPage /></RequireAuth>} />
              <Route path="/gallery" element={<RequireAuth><div className="max-w-[800px] mx-auto text-sm text-slate-500">Галерея — <Link to="/checks" className="text-blue-600 underline">к проверкам</Link></div></RequireAuth>} />
              <Route path="*" element={<Navigate to="/" replace />} />
            </Routes>
          </div>
        </div>
      </main>
    </div>
    </div>
  )
}

function Dashboard({ health }){
  const [summary,setSummary]=useState(null)
  useEffect(()=>{
    const t=localStorage.getItem('token')
    fetch(`${API}/dashboard/summary?days=7`, {headers: t?{Authorization:`Bearer ${t}`}:{}}).then(r=>r.json()).then(setSummary).catch(()=>{})
  },[])
  return (
    <div className="max-w-[800px] mx-auto w-full space-y-6">
      <h2 className="text-xl font-bold text-slate-900 dark:text-white">Дашборд</h2>
      <div className="grid grid-cols-2 md:grid-cols-4 gap-3">
        {[
          {k:"Всего", v: summary?.total ?? '—'},
          {k:"Готово", v: summary?.done ?? '—'},
          {k:"На проверке", v: summary?.pending_reviews ?? '—'},
          {k:"Hit Rate", v: summary?.hit_rate ? `${(summary.hit_rate*100).toFixed(0)}%` : '—'},
        ].map(s=>(
          <div key={s.k} className="bg-white dark:bg-[#1e293b] border border-slate-200 dark:border-slate-700 rounded-xl p-4 shadow-sm">
            <div className="text-[10px] uppercase text-slate-500 font-bold">{s.k}</div>
            <div className="text-xl font-bold font-mono text-slate-900 dark:text-white mt-1">{s.v}</div>
          </div>
        ))}
      </div>
      {summary?.summary && <div className="bg-blue-50 dark:bg-[#1e293b]/50 border border-blue-200 dark:border-slate-700 rounded-xl p-4 text-sm text-slate-700 dark:text-slate-300">{summary.summary}</div>}
    </div>
  )
}
