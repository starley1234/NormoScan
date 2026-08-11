import React, { useState, useEffect } from 'react'
import { Routes, Route, Link, useNavigate, useParams, NavLink, Navigate } from 'react-router-dom'
import { Layers, FileText, Search, BarChart3, Upload, Copy, ChevronLeft, Menu, X, Zap, Terminal, LogOut, Sun, Moon, LayoutDashboard, Users, BookOpen, Image as ImageIcon, Settings, MessageSquare, Shield } from 'lucide-react'
import ReactMarkdown from 'react-markdown'
import remarkGfm from 'remark-gfm'
import rehypeHighlight from 'rehype-highlight'
import 'highlight.js/styles/github-dark.css'

const API_BASE = (import.meta.env.VITE_API_URL || '').replace(/\/$/, '')
const API = API_BASE ? `${API_BASE}/api` : '/api'
const API_ROOT = API_BASE || ''

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

function useAuth() {
  const [token, setToken] = useState(localStorage.getItem('token'))
  const [user, setUser] = useState(()=>{ try{ return JSON.parse(localStorage.getItem('user')||'null')}catch{ return null }})
  const login = (t, u) => { localStorage.setItem('token', t); localStorage.setItem('user', JSON.stringify(u)); setToken(t); setUser(u) }
  const logout = () => { localStorage.removeItem('token'); localStorage.removeItem('user'); setToken(null); setUser(null) }
  return { token, user, login, logout, isAuth: !!token, role: user?.role || 'viewer' }
}

function CopyBtn({ text }) {
  const [copied, setCopied] = useState(false)
  return (
    <button onClick={()=>{navigator.clipboard.writeText(text); setCopied(true); setTimeout(()=>setCopied(false),1500)}} 
      className="opacity-0 group-hover:opacity-100 transition flex items-center gap-1 text-[11px] text-slate-500 hover:text-slate-900 dark:hover:text-white border border-slate-200 dark:border-slate-700 rounded px-2 py-1 bg-white dark:bg-slate-800">
      <Copy size={12} /> {copied?'Скопировано':'Копировать'}
    </button>
  )
}

function LoginPage() {
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
      navigate('/dashboard')
      window.location.reload()
    }catch(e){ setErr(String(e)) }
  }
  return (
    <div className="min-h-[60vh] flex items-center justify-center p-6">
      <div className="w-full max-w-[420px] bg-white dark:bg-[#1e293b] border border-slate-200 dark:border-slate-700 rounded-2xl p-8 shadow-sm">
        <div className="text-center mb-6">
          <div className="w-12 h-12 rounded-xl bg-[#3b82f6] flex items-center justify-center mx-auto text-white font-bold">N</div>
          <h2 className="text-xl font-bold text-slate-900 dark:text-white mt-3">Вход в НормоСкан</h2>
          <p className="text-sm text-slate-500 dark:text-slate-400 mt-1">16GB VRAM · локальный инференс</p>
        </div>
        <div className="space-y-3">
          <input value={u} onChange={e=>setU(e.target.value)} placeholder="Логин" className="w-full bg-slate-50 dark:bg-[#0f172a] border border-slate-200 dark:border-slate-700 rounded-xl px-4 py-3 text-sm focus:border-[#3b82f6] outline-none" />
          <input value={p} onChange={e=>setP(e.target.value)} type="password" placeholder="Пароль" onKeyDown={e=>e.key==='Enter'&&doLogin()} className="w-full bg-slate-50 dark:bg-[#0f172a] border border-slate-200 dark:border-slate-700 rounded-xl px-4 py-3 text-sm focus:border-[#3b82f6] outline-none" />
          {err && <div className="text-xs text-red-600 bg-red-50 dark:bg-red-500/10 border border-red-200 dark:border-red-500/20 rounded-lg p-2.5">{err}</div>}
          <button onClick={doLogin} className="w-full bg-[#3b82f6] hover:bg-blue-600 text-white py-3 rounded-xl font-medium transition">Войти</button>
          <div className="text-[11px] text-center text-slate-500 font-mono">admin/admin123 · norm/norm123 · engineer/eng123</div>
        </div>
      </div>
    </div>
  )
}

const NAV = [
  { to:"/dashboard", label:"Дашборд", icon:LayoutDashboard, roles:["admin","normocontroller","engineer","viewer"] },
  { to:"/checks", label:"Проверки", icon:Layers, roles:["admin","normocontroller","engineer","viewer"] },
  { to:"/checks/upload", label:"Загрузка", icon:Upload, roles:["admin","normocontroller","engineer"] },
  { to:"/gosts", label:"ГОСТы", icon:BookOpen, roles:["admin","normocontroller","engineer","viewer"] },
  { to:"/gallery", label:"Галерея", icon:ImageIcon, roles:["admin","normocontroller"] },
  { to:"/team", label:"Команда", icon:Users, roles:["admin","normocontroller","engineer"] },
  { to:"/analytics", label:"Аналитика", icon:BarChart3, roles:["admin","normocontroller"] },
  { to:"/admin", label:"Админка", icon:Shield, roles:["admin"] },
  { to:"/logs", label:"Логи", icon:FileText, roles:["admin","normocontroller"] },
]

function Sidebar({ collapsed, setCollapsed, theme, setTheme }) {
  const { user, logout } = useAuth()
  const role = user?.role || 'viewer'
  const items = NAV.filter(n=>n.roles.includes(role))
  return (
    <aside className={`${collapsed?'w-0 overflow-hidden':'w-[280px]'} shrink-0 border-r border-slate-200 dark:border-slate-700 bg-white dark:bg-[#1e293b]/80 backdrop-blur-[10px] flex flex-col transition-all duration-300 h-screen sticky top-0`}>
      <div className="p-5 flex flex-col gap-5 h-full overflow-y-auto">
        <div className="flex items-center justify-between">
          <Link to="/" className="flex items-center gap-2 hover:opacity-80 transition">
            <div className="w-8 h-8 rounded-lg bg-[#3b82f6] flex items-center justify-center text-white font-bold text-sm">N</div>
            <div>
              <div className="text-sm font-bold tracking-tight text-slate-900 dark:text-white leading-none">НОРМОСКАН</div>
              <div className="text-[10px] text-slate-500 font-mono">LLAMA.CPP UI</div>
            </div>
          </Link>
          <button onClick={()=>setCollapsed(true)} className="p-1.5 hover:bg-slate-100 dark:hover:bg-slate-700 rounded-lg lg:hidden"><X size={16}/></button>
        </div>

        <nav className="space-y-1">
          {items.map(it=>(
            <NavLink key={it.to} to={it.to} className={({isActive})=>`flex items-center gap-3 px-3 py-2.5 rounded-xl text-sm transition ${isActive?'bg-[#3b82f6] text-white shadow-sm':'text-slate-600 dark:text-slate-400 hover:bg-slate-50 dark:hover:bg-slate-800 hover:text-slate-900 dark:hover:text-white'}`}>
              <it.icon size={16} /> {it.label}
            </NavLink>
          ))}
        </nav>

        <div className="mt-auto space-y-3 pt-4 border-t border-slate-200 dark:border-slate-700">
          <div className="flex items-center justify-between">
            <div className="text-xs">
              <div className="font-medium text-slate-900 dark:text-white">{user?.username || '—'}</div>
              <div className="text-[11px] text-slate-500 capitalize">{role}</div>
            </div>
            <button onClick={()=>setTheme(theme==='dark'?'light':'dark')} className="p-2 rounded-xl border border-slate-200 dark:border-slate-700 bg-slate-50 dark:bg-slate-800 hover:bg-slate-100 dark:hover:bg-slate-700" title={theme==='dark'?'День':'Ночь'}>
              {theme==='dark'?<Sun size={16}/>:<Moon size={16}/>}
            </button>
          </div>
          <button onClick={()=>{localStorage.removeItem('token'); localStorage.removeItem('user'); window.location.href='/login'}} className="w-full flex items-center justify-center gap-2 text-xs py-2.5 rounded-xl border border-slate-200 dark:border-slate-700 hover:bg-slate-50 dark:hover:bg-slate-800 text-slate-600 dark:text-slate-400">
            <LogOut size={14}/> Выйти
          </button>
          <div className="text-[10px] text-slate-400 font-mono text-center">16GB VRAM · 768px</div>
        </div>
      </div>
    </aside>
  )
}

function Message({ role, content }) {
  const isUser = role==='user'
  return (
    <div className={`group flex gap-3 max-w-[800px] w-full mx-auto ${isUser?'flex-row-reverse':''}`}>
      <div className={`w-8 h-8 rounded-full flex items-center justify-center shrink-0 text-xs font-bold ${isUser?'bg-[#3b82f6] text-white':'bg-white dark:bg-slate-700 text-slate-600 dark:text-slate-300 border border-slate-200 dark:border-slate-600'}`}>{isUser?'U':'AI'}</div>
      <div className={`px-4 py-3 rounded-2xl max-w-[80%] text-sm leading-relaxed shadow-sm ${isUser?'bg-[#3b82f6] text-white rounded-tr-sm':'bg-white dark:bg-[#1e293b] border border-slate-200 dark:border-slate-700 text-slate-800 dark:text-slate-200 rounded-tl-sm font-mono'}`}>
        <div className="markdown prose prose-sm max-w-none dark:prose-invert"><ReactMarkdown remarkPlugins={[remarkGfm]} rehypePlugins={[rehypeHighlight]}>{content}</ReactMarkdown></div>
      </div>
    </div>
  )
}

function DashboardPage({ health }) {
  const [summary,setSummary]=useState(null)
  useEffect(()=>{
    const t=localStorage.getItem('token')
    fetch(`${API}/dashboard/summary?days=7`, {headers: t?{Authorization:`Bearer ${t}`}:{}}).then(r=>r.json()).then(setSummary).catch(()=>{})
  },[])
  return (
    <div className="max-w-[800px] mx-auto w-full space-y-6">
      <h2 className="text-xl font-bold text-slate-900 dark:text-white flex items-center gap-2"><BarChart3 size={20} className="text-[#3b82f6]"/> Дашборд</h2>
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
      <div className="text-xs font-mono text-slate-500">Модель: {health?.model} · {health?.engine} · {health?.context_window} ctx</div>
    </div>
  )
}

function ChecksPage() {
  const [checks,setChecks]=useState([]), [q,setQ]=useState("")
  const load=()=>{
    const t=localStorage.getItem('token')
    if(!t) return
    fetch(`${API}/checks/?q=${encodeURIComponent(q)}`, {headers:{Authorization:`Bearer ${t}`}}).then(r=>r.json()).then(d=>setChecks(d.items||[])).catch(()=>{})
  }
  useEffect(()=>{load()},[])
  return (
    <div className="max-w-[800px] mx-auto w-full space-y-4">
      <div className="flex items-center justify-between">
        <h2 className="text-xl font-bold text-slate-900 dark:text-white">Проверки</h2>
        <Link to="/checks/upload" className="bg-[#3b82f6] hover:bg-blue-600 text-white px-4 py-2 rounded-xl text-sm font-medium flex items-center gap-2"><Upload size={16}/> Загрузить</Link>
      </div>
      <div className="flex gap-2">
        <div className="relative flex-1">
          <Search size={16} className="absolute left-3 top-1/2 -translate-y-1/2 text-slate-400" />
          <input value={q} onChange={e=>setQ(e.target.value)} onKeyDown={e=>e.key==='Enter'&&load()} placeholder="Вал, АБВГ..." className="w-full bg-white dark:bg-[#1e293b] border border-slate-200 dark:border-slate-700 rounded-xl pl-10 pr-4 py-2.5 text-sm focus:border-[#3b82f6] outline-none" />
        </div>
        <button onClick={load} className="px-4 py-2 bg-white dark:bg-slate-800 border border-slate-200 dark:border-slate-700 rounded-xl text-sm">Найти</button>
      </div>
      <div className="space-y-2">
        {checks.map(c=>(
          <Link key={c.id} to={`/checks/${c.id}`} className="block bg-white dark:bg-[#1e293b] border border-slate-200 dark:border-slate-700 rounded-xl p-4 hover:border-[#3b82f6]/50 transition shadow-sm">
            <div className="flex justify-between items-start">
              <div><div className="font-medium text-slate-900 dark:text-white">#{c.id} {c.filename}</div><div className="text-xs font-mono text-slate-500">{new Date(c.created_at).toLocaleString()}</div></div>
              <span className="text-xs px-2 py-1 rounded-full border font-mono bg-slate-50 dark:bg-slate-800">{c.status}</span>
            </div>
          </Link>
        ))}
      </div>
    </div>
  )
}

function CheckDetailPage() {
  const { id } = useParams()
  const [check,setCheck]=useState(null), [ask,setAsk]=useState(""), [askRes,setAskRes]=useState(null)
  useEffect(()=>{
    const t=localStorage.getItem('token')
    fetch(`${API}/checks/${id}`, {headers: t?{Authorization:`Bearer ${t}`}:{}}).then(r=>r.json()).then(setCheck).catch(()=>{})
  },[id])
  const doAsk=async()=>{
    const t=localStorage.getItem('token')
    const r=await fetch(`${API}/checks/${id}/ask`, {method:'POST', headers:{'Content-Type':'application/json', Authorization:`Bearer ${t}`}, body: JSON.stringify({query: ask})})
    setAskRes(await r.json())
  }
  if(!check) return <div className="max-w-[800px] mx-auto p-8 text-slate-500 font-mono text-sm">Загрузка #{id}...</div>
  return (
    <div className="max-w-[800px] mx-auto w-full space-y-6">
      <Link to="/checks" className="inline-flex items-center gap-1 text-xs text-slate-500 hover:text-slate-900 dark:hover:text-white"><ChevronLeft size={14}/> Назад</Link>
      <div className="bg-white dark:bg-[#1e293b] border border-slate-200 dark:border-slate-700 rounded-xl p-5 shadow-sm">
        <h2 className="font-bold text-slate-900 dark:text-white">#{check.id} {check.filename}</h2>
        <div className="text-xs font-mono text-slate-500 mt-1">{check.summary || '—'}</div>
      </div>
      <div className="space-y-3">
        <h3 className="text-sm font-bold text-slate-900 dark:text-white">Ошибки ({check.errors_json?.length||0})</h3>
        {(check.errors_json||[]).map(e=>(
          <div key={e.id} className="bg-white dark:bg-[#1e293b] border border-slate-200 dark:border-slate-700 rounded-xl p-4">
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
        {askRes && <pre className="mt-3 bg-slate-50 dark:bg-[#0f172a] border rounded-xl p-3 text-xs overflow-auto">{JSON.stringify(askRes,null,2)}</pre>}
      </div>
      <div className="text-xs font-mono text-slate-500">Ссылка: <span className="text-blue-600 dark:text-blue-400">{window.location.href}</span></div>
    </div>
  )
}

function UploadPage() {
  const [file,setFile]=useState(null), [res,setRes]=useState(null), [err,setErr]=useState('')
  const navigate=useNavigate()
  const upload=async()=>{
    const t=localStorage.getItem('token')
    if(!t){ navigate('/login'); return}
    const fd=new FormData(); fd.append('file', file)
    const r=await fetch(`${API}/checks/upload?priority=5`, {method:'POST', headers:{Authorization:`Bearer ${t}`}, body: fd})
    const j=await r.json()
    if(r.status===401){ navigate('/login'); return}
    if(!r.ok) setErr(JSON.stringify(j))
    else setRes(j)
  }
  return (
    <div className="max-w-[800px] mx-auto w-full space-y-6">
      <h2 className="text-xl font-bold text-slate-900 dark:text-white">Загрузка</h2>
      <div className="bg-white dark:bg-[#1e293b] border border-slate-200 dark:border-slate-700 rounded-xl p-6 space-y-4 shadow-sm">
        <label className="block border-2 border-dashed border-slate-200 dark:border-slate-700 rounded-xl p-8 text-center hover:border-[#3b82f6]/50 cursor-pointer bg-slate-50 dark:bg-[#0f172a]">
          <Upload className="mx-auto text-slate-400 mb-2" />
          <div className="text-sm text-slate-700 dark:text-slate-300">Перетащи PDF сюда</div>
          <input type="file" accept=".pdf" className="hidden" onChange={e=>setFile(e.target.files[0])} />
        </label>
        {file && <div className="text-sm font-mono bg-slate-50 dark:bg-[#0f172a] border rounded-lg p-3">{file.name}</div>}
        {err && <div className="text-sm text-red-600 bg-red-50 border border-red-200 rounded-lg p-3">{err}</div>}
        <button onClick={upload} className="w-full bg-[#3b82f6] text-white py-3 rounded-xl font-medium">🚀 Запустить</button>
        {res && <div className="bg-slate-50 dark:bg-[#0f172a] border rounded-xl p-3 text-xs font-mono"><pre>{JSON.stringify(res,null,2)}</pre><Link to={`/checks/${res.check_id}`} className="text-blue-600 underline">→ Открыть</Link></div>}
      </div>
    </div>
  )
}

export default function App(){
  const [collapsed,setCollapsed]=useState(false)
  const [theme,setTheme]=useState(localStorage.getItem('theme')||'light')
  const health = useHealth()

  useEffect(()=>{
    document.documentElement.classList.toggle('dark', theme==='dark')
    localStorage.setItem('theme', theme)
  },[theme])

  const { token } = useAuth()
  const isAuth = !!localStorage.getItem('token')

  return (
    <div className={theme==='dark' ? 'dark' : ''}>
    <div className="flex h-screen bg-slate-50 dark:bg-[#0a0a0a] text-slate-900 dark:text-slate-200 overflow-hidden">
      <Sidebar collapsed={collapsed} setCollapsed={setCollapsed} health={health} theme={theme} setTheme={setTheme} />
      <main className="flex-1 flex flex-col min-w-0 bg-slate-50 dark:bg-[#0a0a0a]">
        <header className="sticky top-0 z-10 flex items-center justify-between px-6 py-3 border-b border-slate-200 dark:border-slate-700 bg-white/80 dark:bg-[#0f172a]/80 backdrop-blur-[10px]">
          <div className="flex items-center gap-3">
            {collapsed && <button onClick={()=>setCollapsed(false)} className="p-2 hover:bg-slate-100 dark:hover:bg-slate-800 rounded-xl border"><Menu size={16}/></button>}
            <Link to="/" className="flex items-center gap-2">
              <div className="w-8 h-8 rounded-lg bg-[#3b82f6] flex items-center justify-center text-white font-bold text-xs">N</div>
              <span className="hidden md:inline text-sm font-bold tracking-tight text-slate-900 dark:text-white">НОРМОСКАН</span>
            </Link>
            <span className="hidden md:inline text-xs font-mono text-slate-500">{health?.model?.split('/').pop() || ''}</span>
          </div>
          <div className="flex items-center gap-2">
            <button onClick={()=>setTheme(theme==='dark'?'light':'dark')} className="p-2 rounded-xl border border-slate-200 dark:border-slate-700 bg-white dark:bg-slate-800">
              {theme==='dark'?<Sun size={16}/>:<Moon size={16}/>}
            </button>
            {isAuth ? <button onClick={()=>{localStorage.clear(); location.href='/login'}} className="p-2 rounded-xl border"><LogOut size={16}/></button> : <Link to="/login" className="px-4 py-1.5 bg-[#3b82f6] text-white rounded-full text-xs">Войти</Link>}
          </div>
        </header>
        <div className="flex-1 overflow-y-auto p-6 md:p-8">
          <Routes>
            <Route path="/login" element={<LoginPage />} />
            <Route path="/" element={<div className="max-w-[800px] mx-auto text-center py-12"><h2 className="text-2xl font-bold text-slate-900 dark:text-white">Где проверить чертёж?</h2><p className="text-sm text-slate-500 mt-2">Каждая проверка — <span className="font-mono text-blue-600">/checks/11</span> — можно отправить ссылку</p></div>} />
            <Route path="/dashboard" element={<Dashboard health={health} />} />
            <Route path="/checks" element={isAuth ? <ChecksPage/> : <Navigate to="/login" replace/>} />
            <Route path="/checks/:id" element={isAuth ? <CheckDetailPage/> : <Navigate to="/login" replace/>} />
            <Route path="/checks/upload" element={isAuth ? <UploadPage/> : <Navigate to="/login" replace/>} />
            <Route path="/gosts" element={<div className="max-w-[800px] mx-auto"><h2 className="text-xl font-bold">ГОСТы</h2><p className="text-sm text-slate-500">Hybrid RAG — <Link to="/checks" className="text-blue-600 underline">к проверкам</Link></p></div>} />
            <Route path="*" element={<Navigate to="/" replace />} />
          </Routes>
        </div>
      </main>
    </div>
    </div>
  )
}
