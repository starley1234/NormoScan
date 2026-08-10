import streamlit as st
import streamlit.components.v1 as components
import requests, os, json, pandas as pd, plotly.express as px, time, io
from datetime import datetime
from PIL import Image, ImageDraw
import base64

API = os.getenv("API_URL", "http://localhost:8000")
API_PORT = os.getenv("API_PORT", "8000")
FRONTEND_PORT = os.getenv("FRONTEND_PORT", "8501")
# Внешний URL для отображения пользователю (хост)
API_EXTERNAL = f"http://localhost:{API_PORT}"
try:
    # если API уже содержит порт, попробуем показать внешний
    if "backend:" in API:
        API_EXTERNAL = f"http://localhost:{API_PORT}"
    else:
        API_EXTERNAL = API
except:
    API_EXTERNAL = API

st.set_page_config(page_title="НормоСкан", page_icon="📐", layout="wide", initial_sidebar_state="expanded")

# --- Инициализация состояния ---
if "dark" not in st.session_state:
    st.session_state.dark = False
if "token" not in st.session_state:
    st.session_state.token = None
    st.session_state.role = None
    st.session_state.username = None

# --- PWA + Mobile viewport ---
st.markdown(f"""
<link rel="manifest" href="/pwa/manifest.json">
<meta name="viewport" content="width=device-width, initial-scale=1, maximum-scale=1">
<meta name="theme-color" content="#0ea5e9">
<style>
kbd{{background:#eee;border:1px solid #ccc;padding:2px 6px;border-radius:4px;font-size:0.85em;color:#111}}
@media (max-width: 768px){{
  [data-testid="stSidebar"]{{width:260px !important}}
  .block-container{{padding:0.5rem !important}}
  h1{{font-size:1.4rem !important}}
  /* Нижняя навигация для мобильных */
  .mobile-nav{{display:none}}
}}
@media (max-width: 768px){{
  .mobile-nav{{display:flex;position:fixed;bottom:0;left:0;right:0;background:#fff;border-top:1px solid #e2e8f0;justify-content:space-around;padding:6px 0;z-index:999}}
  body.dark .mobile-nav{{background:#0f172a;border-color:#334155}}
}}
</style>
""", unsafe_allow_html=True)

# PWA service worker - через components.html чтобы JS выполнился
components.html(f"""
<script>
if('serviceWorker' in navigator){{
  navigator.serviceWorker.register('/pwa/service-worker.js').then(()=>console.log('SW ok')).catch(e=>console.log('SW fail',e));
}}
window.addEventListener('offline', ()=>{{
  const el=document.createElement('div');
  el.textContent='⚠️ Оффлайн — загрузка в очередь';
  el.style='position:fixed;bottom:10px;left:50%;transform:translateX(-50%);background:#f59e0b;color:white;padding:8px 12px;border-radius:8px;z-index:9999';
  document.body.appendChild(el);
  setTimeout(()=>el.remove(),3000);
}});
</script>
""", height=0)

# Dark mode CSS - инжектим в зависимости от состояния
if st.session_state.dark:
    st.markdown("""
    <style>
    .stApp {background:#0f172a !important; color:#e2e8f0 !important}
    [data-testid="stSidebar"] {background:#0f172a !important}
    h1,h2,h3,p,span,div {color:#e2e8f0 !important}
    kbd {background:#334155 !important; color:#f1f5f9 !important; border-color:#475569 !important}
    </style>
    """, unsafe_allow_html=True)

# Hotkeys JS - через components
components.html("""
<script>
document.addEventListener('keydown', (e)=>{
  if(e.target.tagName==='INPUT' || e.target.tagName==='TEXTAREA') return;
  if(e.code==='Space' && !e.ctrlKey){ e.preventDefault(); window.dispatchEvent(new CustomEvent('hotkey', {detail:'next'})); }
});
</script>
""", height=0)

# Верхняя панель - тёмная тема + горячие клавиши (корректно отображаем kbd)
col_dark, col_hot = st.columns([1, 3])
with col_dark:
    # toggle в основном экране, но синхронизируем с sidebar
    dark_new = st.toggle("🌙 Тёмная тема", value=st.session_state.dark, key="dark_toggle_main")
    if dark_new != st.session_state.dark:
        st.session_state.dark = dark_new
        st.rerun()
with col_hot:
    st.markdown("Горячие клавиши: <kbd>Space</kbd> след.лист &nbsp; <kbd>1</kbd> 👍 &nbsp; <kbd>2</kbd> 👎 &nbsp; <kbd>3</kbd> fix &nbsp; <kbd>Ctrl</kbd>+<kbd>Enter</kbd> спросить &nbsp; 📱 PWA", unsafe_allow_html=True)

def auth_header():
    return {"Authorization": f"Bearer {st.session_state.token}"} if st.session_state.token else {}

def api_get(path, **kw):
    try:
        r = requests.get(f"{API}{path}", headers=auth_header(), timeout=15)
        return r
    except Exception as e:
        st.error(f"API недоступен ({API}): {e}")
        return None

def api_post(path, json=None, files=None, data=None):
    try:
        r = requests.post(f"{API}{path}", headers=auth_header(), json=json, files=files, data=data, timeout=30)
        return r
    except Exception as e:
        st.error(f"API недоступен ({API}): {e}")
        return None

# Sidebar - логика: если не залогинен, показываем только вход, навигацию скрываем
with st.sidebar:
    st.title("📐 НормоСкан")
    st.caption("Интеллектуальный нормоконтроль · 16GB VRAM")
    # Dark toggle дублируем в sidebar
    st.toggle("🌙 Тёмная тема", value=st.session_state.dark, key="dark_toggle_sidebar", on_change=lambda: setattr(st.session_state, 'dark', not st.session_state.dark))
    
    if not st.session_state.token:
        st.subheader("Вход")
        u = st.text_input("Логин", value="admin", key="login_user")
        p = st.text_input("Пароль", value="admin123", type="password", key="login_pass")
        if st.button("Войти", key="login_btn"):
            try:
                r = requests.post(f"{API}/api/auth/login", data={"username":u,"password":p})
                if r.status_code==200:
                    j=r.json()
                    st.session_state.token=j["access_token"]
                    st.session_state.role=j["role"]
                    st.session_state.username=j["username"]
                    st.rerun()
                else:
                    st.error(r.text)
            except Exception as e:
                st.error(str(e))
        st.divider()
        st.info("Demo: admin/admin123, norm/norm123, engineer/eng123")
        st.warning("Весь инференс локальный. Данные не уходят наружу.")
        st.divider()
        st.caption(f"API (внутренний): {API}")
        st.caption(f"API (внешний): {API_EXTERNAL} (порт {API_PORT})")
        st.caption(f"Модель: загрузка...")
        page = None
    else:
        st.success(f"Вы: {st.session_state.username} ({st.session_state.role})")
        if st.button("Выйти", key="logout_btn"):
            st.session_state.token=None
            st.rerun()
        st.divider()
        page = st.radio("Навигация", ["Дашборд","Загрузка","Проверки","Команда","ГОСТы","Галерея","База знаний","Аналитика","Админка","MCP","Метрики","Логи"], index=0, key="nav_radio")
        st.divider()
        st.caption(f"API (внутренний): {API}")
        st.caption(f"API (внешний): {API_EXTERNAL}")
        try:
            h=requests.get(f"{API}/health",timeout=2).json()
            st.caption(f"Модель: {h.get('model','')} | ctx {h.get('context_window')} | {h.get('engine','')}")
            if h.get("ocr_ensemble"):
                st.caption("OCR ансамбль: вкл")
            # Показываем VLM API URL если задан (без ключа)
            if h.get("vlm_api_url"):
                st.caption(f"VLM API: {h.get('vlm_api_url')}")
        except: pass
        st.caption("VRAM 16GB optimised · 768px · 4-bit")
        st.caption(f"UI порт: {FRONTEND_PORT}, API порт: {API_PORT}")

if not st.session_state.token:
    st.title("📐 НормоСкан — вход required")
    st.markdown("Войдите через боковую панель слева. Навигация появится после входа.")
    st.info("После входа вы увидите дашборд, проверки, галерею и т.д.")
    st.stop()

# page уже определён выше внутри sidebar else, если token есть
# если по какой-то причине page is None (когда залогинен но не выбрано), дефолтим
if 'page' not in locals() or page is None:
    page = "Дашборд"

def status_badge(s):
    colors={"queued":"🟡","processing":"🔵","done":"🟢","failed":"🔴","dead_letter":"⚫","dedupe":"🟣"}
    return f"{colors.get(s,'⚪')} {s}"

def draw_annotations(image_path, annotations):
    try:
        im = Image.open(image_path).convert("RGB")
        draw = ImageDraw.Draw(im, "RGBA")
        w,h = im.size
        for a in annotations:
            bbox = a.get("bbox")
            if not bbox: continue
            x,y,bw,bh = bbox
            left=int(x*w); upper=int(y*h); right=int((x+bw)*w); lower=int((y+bh)*h)
            color = (255,0,0,180) if a.get("severity")=="error" else (255,165,0,180) if a.get("severity")=="warning" else (0,0,255,120)
            draw.rectangle([left,upper,right,lower], outline=color[:3], width=3)
            draw.rectangle([left,upper,right,lower], fill=color[:3]+(40,))
            draw.text((left, upper-12), a.get("code",""), fill=(255,0,0))
        return im
    except Exception as e:
        st.warning(f"Не удалось отрисовать: {e}")
        return None

# === PAGES ===
if page=="Дашборд":
    st.header("📊 Лёгкий Дашборд — без Grafana")
    st.caption("Живые метрики из /api/dashboard/summary + /api/metrics (в памяти, без внешних зависимостей)")
    colA,colB,colC,colD = st.columns(4)
    r=api_get("/api/dashboard/summary?days=7")
    if r and r.status_code==200:
        j=r.json()
        with colA: st.metric("Всего", j.get("total",0))
        with colB: st.metric("Готово", j.get("done",0))
        with colC: st.metric("На проверке", j.get("pending_reviews",0))
        with colD: st.metric("Hit Rate", f"{j.get('hit_rate',0):.0%}")
        st.info(j.get("summary",""))
        c1,c2=st.columns(2)
        with c1:
            if j.get("by_day"):
                df=pd.DataFrame(list(j["by_day"].items()), columns=["дата","кол-во"])
                st.plotly_chart(px.line(df, x="дата", y="кол-во", title="Динамика 7д"), use_container_width=True)
            if j.get("top_errors"):
                st.plotly_chart(px.bar(pd.DataFrame(j["top_errors"]), x="code", y="count", title="Топ ошибок"), use_container_width=True)
        with c2:
            st.subheader("Последние проверки")
            for it in j.get("last_checks",[]):
                st.write(f"{status_badge(it['status'])} #{it['id']} {it['filename']} — {it['created_at'][:10] if it['created_at'] else ''}")
            if j.get("last_run"):
                lr=j["last_run"]
                st.success(f"Active Learning: {lr['before']:.0%} → {lr['after']:.0%} ({lr['created_at'][:16]})")
            st.subheader("Метрики")
            m=j.get("metrics",{})
            st.json({"uptime_h": j.get("uptime_hours"), "hit_rate": j.get("hit_rate"), "counters": m.get("counters",{})})
        st.divider()
        st.subheader("🤖 Active Learning замкнутый")
        st.caption("Берёт 👎 из галереи, переиндексирует, меряет Hit Rate до/после")
        c1,c2=st.columns(2)
        with c1:
            if st.button("🔄 Запустить цикл Active Learning"):
                rr=api_post("/api/dashboard/active-learning/run", json={})
                if rr: st.json(rr.json() if rr.status_code==200 else rr.text)
        with c2:
            r2=api_get("/api/dashboard/active-learning")
            if r2 and r2.status_code==200:
                st.dataframe(pd.DataFrame(r2.json().get("runs",[])), use_container_width=True)
    else:
        st.error("Дашборд недоступен — проверь API")

elif page=="Загрузка":
    st.header("📤 Загрузка чертежа")
    st.info("Поддерживается PDF А0-А4. Система: 768px ресайз + кроп (штамп/ТТ/графика) → OCR ансамбль → Hybrid RAG (Qdrant) → Gemma-3-12B 4-bit → JSON + чек-лист. Дедупликация по хэшу 5 мин.")
    col1,col2 = st.columns([2,1])
    with col1:
        prio = st.select_slider("Приоритет", options=[1,3,5,8,10], value=5, help="1=высший")
        up = st.file_uploader("Выберите PDF", type=["pdf"])
        dedupe_info = st.empty()
        if up:
            import hashlib
            h = hashlib.sha256(up.getvalue()).hexdigest()[:16]
            dedupe_info.caption(f"Хэш: {h} · если такой файл уже проверяли <5мин — вернётся готовый результат (экономия VRAM)")
        if up and st.button("🚀 Запустить проверку", type="primary"):
            with st.spinner("Загрузка..."):
                files={"file": (up.name, up.getvalue(), "application/pdf")}
                r = api_post(f"/api/checks/upload?priority={prio}", files=files)
                if r and r.status_code==200:
                    j=r.json()
                    if j.get("status")=="dedupe":
                        st.success(f"Дедупликация! Уже есть проверка #{j['dedupe_from']} — результат скопирован.")
                        st.json(j)
                    else:
                        st.success(f"Проверка #{j['check_id']} поставлена в очередь ({j['status']})")
                        st.json(j)
                        if st.checkbox("Показать прогресс (SSE)", value=True):
                            placeholder = st.empty()
                            bar = st.progress(0)
                            for _ in range(30):
                                rr = api_get(f"/api/checks/{j['check_id']}")
                                if rr and rr.status_code==200:
                                    d=rr.json()
                                    done = d.get("pages_done",0)
                                    total = max(d.get("pages_total",1),1)
                                    bar.progress(min(done/total,1.0))
                                    placeholder.write(f"Статус: {d['status']} — {done}/{total} листов")
                                    if d["status"] in ("done","failed","dead_letter"):
                                        st.success(f"Готово: {d.get('summary','')}")
                                        break
                                time.sleep(0.7)
                else:
                    st.error(r.text if r else "Ошибка")
    with col2:
        st.subheader("Подсказки")
        st.write("- А1 простыня режется на зоны, не подавайте целиком")
        st.write("- Масса/Материал в штампе проверяются по ГОСТ 2.104")
        st.write("- Используйте «Галерею» чтобы обучить Visual RAG")
        st.info(f"VLM внешний: {API_EXTERNAL} — логи в `docker logs normoscan-backend` / `celery_worker`")

elif page=="Проверки":
    st.header("📋 Реестр проверок")
    c1,c2,c3 = st.columns([1,1,1])
    with c1:
        status_filter=st.selectbox("Статус", ["all","queued","processing","done","failed","dead_letter","dedupe"])
    with c2:
        q=st.text_input("Поиск по имени/суммари", placeholder="Вал, АБВГ...")
    with c3:
        if st.button("🔄 Обновить"):
            st.rerun()
    params=[]
    if status_filter!="all": params.append(f"status={status_filter}")
    if q: params.append(f"q={q}")
    qs = "?" + "&".join(params) if params else ""
    r=api_get(f"/api/checks/{qs}")
    if r and r.status_code==200:
        j=r.json()
        st.metric("Всего", j["total"])
        df=pd.DataFrame(j["items"])
        if not df.empty:
            df["badge"]=df["status"].apply(status_badge)
            st.dataframe(df[["id","filename","badge","status","pages_done","pages_total","created_at"]], use_container_width=True, hide_index=True)
            sel=st.number_input("Открыть проверку ID", min_value=0, step=1)
            if sel:
                rr=api_get(f"/api/checks/{int(sel)}")
                if rr and rr.status_code==200:
                    d=rr.json()
                    st.subheader(f"Проверка #{d['id']} — {d['filename']} {status_badge(d['status'])}")
                    st.write(d["summary"] or "")
                    cl = d.get("checklist")
                    if cl:
                        st.subheader("✅ Чек-лист ГОСТов")
                        for item in cl.get("items",[]):
                            icon = "❌" if item["status"]=="fail" else "✅"
                            st.write(f"{icon} **{item['code']}** — {item['desc']} ({item['count']} замечаний)" if item["status"]=="fail" else f"{icon} {item['code']} — {item['desc']}")
                    with st.expander("📄 Метаданные (штамп)", expanded=True):
                        st.json(d.get("meta_json") or {})
                        if st.button("Проверить по схеме"):
                            st.info("Схема проверяется на сервере при анализе (см. /api/checks/meta/schema)")
                    if d.get("consistency") and not d["consistency"].get("consistent"):
                        st.warning("Несоответствия между листами:")
                        for iss in d["consistency"]["issues"]:
                            st.error(f"{iss['msg']} → {iss.get('suggested_fix','')}")
                            st.json(iss)
                    errs=d.get("errors_json") or []
                    if errs:
                        st.error(f"Найдено {len(errs)} замечаний")
                        for e in errs:
                            with st.expander(f"{e.get('code','')} — {e.get('msg','')[:70]} [{e.get('severity','')}]"):
                                st.json(e)
                                if e.get("suggested_fix"):
                                    st.success(f"💡 Как исправить: {e['suggested_fix']} (уверенность {e.get('fix_confidence',0):.0%})")
                                    if st.button(f"Скопировать fix {e.get('id')}", key=f"copy_{e.get('id')}"):
                                        st.code(e["suggested_fix"])
                                if e.get("bbox"):
                                    st.caption(f"BBOX: {e['bbox']}")
                                c1,c2,c3 = st.columns(3)
                                with c1:
                                    if st.button(f"👍", key=f"like_{e.get('id')}"):
                                        api_post("/api/checks/feedback", json={"check_id":d["id"],"error_id":e.get("id"),"vote":"like"})
                                        st.toast("Спасибо!")
                                with c2:
                                    if st.button(f"👎 В retrain", key=f"dis_{e.get('id')}"):
                                        api_post("/api/checks/feedback", json={"check_id":d["id"],"error_id":e.get("id"),"vote":"dislike","comment":"false positive"})
                                        st.toast("Отправлено на дообучение")
                                with c3:
                                    if st.button(f"🔧 Запросить fix", key=f"fix_{e.get('id')}"):
                                        rr2=api_post(f"/api/checks/{d['id']}/suggest-fix?error_id={e.get('id')}", json={})
                                        if rr2: st.json(rr2.json())
                    else:
                        st.success("Замечаний не найдено")
                    st.subheader("📑 Постранично + аннотации")
                    ann_r = api_get(f"/api/checks/{int(sel)}/annotations")
                    ann_data = ann_r.json() if ann_r and ann_r.status_code==200 else {"annotations":[]}
                    for p in d.get("pages",[]):
                        with st.expander(f"Лист {p['page_number']} — {len(p.get('errors') or [])} ошибок, OCR {p.get('ocr_confidence',0):.0%}"):
                            st.json(p)
                    st.subheader("💬 Вопрос по документу")
                    q=st.text_input("Задайте вопрос (напр. 'какая масса?', 'чек-лист?', 'какие ошибки по ГОСТ 2.307?')", key="ask_doc_q")
                    colA,colB=st.columns(2)
                    with colA:
                        if st.button("Спросить", key="ask_doc_btn"):
                            rrr=api_post(f"/api/checks/{d['id']}/ask", json={"query":q})
                            if rrr and rrr.status_code==200:
                                st.json(rrr.json())
                    with colB:
                        if st.button("Показать аннотации JSON"):
                            st.json(ann_data)
                    if d["status"] in ("queued","processing"):
                        if st.button("📡 Следить (SSE)"):
                            st.info("SSE стрим: /api/checks/{id}/stream — polling fallback")
                            bar=st.progress(d["pages_done"]/max(d["pages_total"],1))
                else:
                    st.error("Не найдено")
        else:
            st.info("Пока нет проверок — загрузите PDF")

elif page=="Команда":
    st.header("👥 Командная работа")
    st.caption("Назначение, ревью (approve/reject), комментарии на bbox с @mention — всё в одном месте.")
    tab_a, tab_b, tab_c = st.tabs(["Мои задачи","Назначить","Комментарии"])
    with tab_a:
        r=api_get("/api/team/my/assignments")
        if r and r.status_code==200:
            items=r.json().get("items",[])
            if items:
                st.dataframe(pd.DataFrame(items), use_container_width=True)
                sel=st.number_input("Открыть check_id из задач", min_value=0, step=1, key="my_check")
                if sel:
                    rr=api_get(f"/api/checks/{int(sel)}")
                    if rr and rr.status_code==200:
                        st.json(rr.json().get("summary",""))
            else:
                st.info("Нет назначений — попроси админа назначить")
        st.divider()
        st.subheader("Ревью")
        cid=st.number_input("Check ID для ревью", min_value=0, step=1, key="rev_cid")
        decision=st.selectbox("Решение", ["in_review","approved","rejected"])
        comm=st.text_input("Комментарий к ревью")
        if st.button("Отправить ревью"):
            rr=api_post(f"/api/team/checks/{int(cid)}/review", json={"decision":decision,"comment":comm})
            st.json(rr.json() if rr and rr.status_code==200 else rr.text if rr else "error")
    with tab_b:
        if st.session_state.role not in ("admin","normocontroller"):
            st.warning("Только admin/normocontroller может назначать")
        else:
            r=api_get("/api/admin/users")
            users=[]
            if r and r.status_code==200:
                users=r.json().get("users",[])
                st.dataframe(pd.DataFrame(users)[["id","username","role"]], use_container_width=True)
            cid2=st.number_input("Check ID", min_value=0, step=1, key="assign_cid")
            aid=st.number_input("Assignee user_id", min_value=0, step=1, key="aid")
            note=st.text_input("Комментарий к назначению")
            if st.button("Назначить"):
                rr=api_post(f"/api/team/checks/{int(cid2)}/assign", json={"assignee_id": int(aid), "comment": note})
                st.json(rr.json() if rr else {})
            if cid2:
                rr=api_get(f"/api/team/checks/{int(cid2)}/assignments")
                if rr: st.json(rr.json())
    with tab_c:
        cid3=st.number_input("Check ID для комментариев", min_value=0, step=1, key="comm_cid")
        if cid3:
            r=api_get(f"/api/team/checks/{int(cid3)}/comments")
            if r and r.status_code==200:
                for c in r.json().get("items",[]):
                    st.write(f"**{c['author']}** @{','.join(c.get('mentions',[]))} — {c['text']} (стр {c.get('page_number')}, bbox {c.get('bbox')})")
                    st.caption(str(c['created_at']))
            st.divider()
            st.subheader("Новый комментарий (с @mention и bbox)")
            text=st.text_area("Текст, напр. @ivan проверь стрелку", key="comm_text")
            pg=st.number_input("Страница", min_value=0, value=0, key="comm_pg")
            bx_x=st.slider("bbox x", 0.0,1.0,0.2, key="bx_x")
            bx_y=st.slider("bbox y", 0.0,1.0,0.2, key="bx_y")
            bx_w=st.slider("bbox w", 0.0,1.0,0.08, key="bx_w")
            bx_h=st.slider("bbox h", 0.0,1.0,0.08, key="bx_h")
            if st.button("Отправить комментарий"):
                rr=api_post(f"/api/team/checks/{int(cid3)}/comments", json={"text": text, "page_number": int(pg) if pg else None, "bbox": [bx_x,bx_y,bx_w,bx_h] if text else None})
                st.json(rr.json() if rr else {})

elif page=="ГОСТы":
    st.header("📚 База ГОСТов")
    st.caption("Инкрементальный ingest: папка сканируется, неизменённые файлы пропускаются (hash+mtime). Версионирование и obsolete.")
    c1,c2=st.columns(2)
    with c1:
        path=st.text_input("Путь к папке", value="./storage/gosts")
        force=st.checkbox("Форсировать переиндексацию", value=False)
        if st.button("Индексировать папку"):
            with st.spinner("Индексация..."):
                r=api_post("/api/gosts/ingest", json={"path": path, "force": force})
                if r: st.json(r.json() if r.status_code==200 else r.text)
                if r and r.status_code==200:
                    j=r.json()
                    st.success(f"Найдено {j.get('files_found')} · проиндексировано {j.get('indexed')} · пропущено {j.get('skipped')}")
    with c2:
        up=st.file_uploader("Загрузить один ГОСТ PDF", type=["pdf"])
        desig=st.text_input("Обозначение (опционально)", placeholder="ГОСТ 2.104-2006")
        if up and st.button("Загрузить и индексировать"):
            files={"file": (up.name, up.getvalue(), "application/pdf")}
            r=api_post("/api/gosts/upload", files=files, data={"designation": desig} if desig else None)
            if r: st.json(r.json() if r.status_code==200 else r.text)
    st.divider()
    show_obs=st.checkbox("Показать obsolete", value=False)
    r=api_get(f"/api/gosts/?include_obsolete={str(show_obs).lower()}")
    if r and r.status_code==200:
        j=r.json()
        df=pd.DataFrame(j["items"])
        if not df.empty:
            st.dataframe(df, use_container_width=True, hide_index=True)
            if st.session_state.role=="admin":
                gid=st.number_input("ID ГОСТа для пометки obsolete", min_value=0, step=1)
                sup=st.text_input("Заменён на", placeholder="ГОСТ 2.104-2024")
                if st.button("Пометить obsolete"):
                    rr=api_post(f"/api/gosts/{int(gid)}/obsolete?superseded_by={sup}", json={})
                    st.json(rr.json() if rr else {})
        else:
            st.info("ГОСТов нет")
    with st.expander("🔀 Diff ГОСТов (сравнение версий)"):
        c1,c2=st.columns(2)
        with c1: old_id=st.number_input("Старый ID", min_value=0, step=1, key="old_gost")
        with c2: new_id=st.number_input("Новый ID", min_value=0, step=1, key="new_gost")
        if st.button("Сравнить"):
            r=api_get(f"/api/gosts/diff?old_id={int(old_id)}&new_id={int(new_id)}")
            if r and r.status_code==200:
                j=r.json()
                st.write(f"Добавлено: {j.get('added')} · Удалено: {j.get('removed')}")
                st.code("\n".join(j.get("diff",[])[:200]), language="diff")
                if j.get("html"):
                    components.html(j["html"], height=300, scrolling=True)
            else:
                st.error(r.text if r else "Ошибка")
    st.divider()
    st.subheader("Поиск / Вопрос по ГОСТам — Hybrid RAG + cross-encoder re-rank")
    q=st.text_input("Вопрос", placeholder="Какие требования к основной надписи по ГОСТ 2.104?", key="gost_q")
    if len(q.strip())>=2:
        r_ac=api_get(f"/api/gosts/autocomplete?q={q}&limit=5")
        if r_ac and r_ac.status_code==200:
            sug=r_ac.json().get("suggestions",[])
            if sug:
                st.caption("Автодополнение: " + " · ".join(sug))
                sel=st.selectbox("Выбрать подсказку", [""]+sug, key="ac_sel")
                if sel:
                    q=sel
    topk=st.slider("top_k",1,10,3, key="gost_topk")
    if st.button("Искать", key="gost_search"):
        r=api_post("/api/gosts/search", json={"query":q,"top_k":topk})
        if r and r.status_code==200:
            j=r.json()
            st.json(j)
            for h in j.get("hits",[]):
                with st.expander(f"{h['payload'].get('designation')} — {h['score']:.2f}"):
                    st.write(h.get("snippet") or h["payload"].get("text","")[:500])

elif page=="Галерея":
    st.header("🖼️ Галерея ошибок и эталонов (Visual RAG)")
    st.caption("Перетащите скриншот → кроп узла → добавит в Qdrant. При >82% близости VLM получит подсказку.")
    c1,c2=st.columns([1,1])
    with c1:
        st.subheader("Добавить")
        up=st.file_uploader("Скриншот", type=["png","jpg","jpeg"], key="gal_up")
        if up:
            img=Image.open(up)
            st.image(img, caption="Оригинал (вырежьте узел в редакторе выше, если нужно)", use_column_width=True)
            w,h = img.size
            x=st.slider("X",0, w, 0)
            y=st.slider("Y",0, h, 0)
            cw=st.slider("Ширина", 50, w, min(400,w))
            ch=st.slider("Высота", 50, h, min(300,h))
            if st.checkbox("Показать кроп"):
                st.image(img.crop((x,y, x+cw, y+ch)), caption="Кроп")
        title=st.text_input("Название", value="Неверная засечка стрелки")
        cat=st.selectbox("Категория", ["error","etalon"])
        gost_ref=st.text_input("Ссылка на ГОСТ", value="ГОСТ 2.305")
        err_type=st.text_input("Тип ошибки", value="засечка")
        if up and st.button("➕ Добавить в галерею"):
            files={"file": (up.name, up.getvalue(), "image/png")}
            data={"title":title,"category":cat,"gost_ref":gost_ref,"error_type":err_type}
            r=api_post("/api/gallery/upload", files=files, data=data)
            if r: st.json(r.json() if r.status_code==200 else r.text)
    with c2:
        st.subheader("Список")
        r=api_get("/api/gallery/")
        if r and r.status_code==200:
            j=r.json()
            st.dataframe(pd.DataFrame(j["items"]), use_container_width=True, hide_index=True)
        st.divider()
        st.subheader("🔍 Поиск похожих")
        qimg=st.file_uploader("Запрос-изображение", type=["png","jpg"], key="qimg")
        if qimg and st.button("Найти похожие"):
            files={"file": (qimg.name, qimg.getvalue(), "image/png")}
            r=requests.post(f"{API}/api/gallery/search", headers=auth_header(), files=files, data={"top_k":5})
            if r.status_code==200:
                hits=r.json()["hits"]
                for h in hits:
                    st.write(f"{h['payload'].get('title')} — {h.get('similarity_percent')}% (score {h.get('similarity'):.2f})")
                    st.json(h)
            else:
                st.error(r.text)
    st.divider()
    st.subheader("👎 Очередь на дообучение (из feedback)")
    if st.session_state.role in ("admin","normocontroller"):
        r=api_get("/api/gallery/retrain/queue")
        if r and r.status_code==200:
            items=r.json()["items"]
            if items:
                st.dataframe(pd.DataFrame(items), use_container_width=True)
                fid=st.number_input("Feedback ID для промоута", min_value=0, step=1)
                ptitle=st.text_input("Название для галереи", value="Ошибка из фидбека")
                if st.button("⬆️ Промоут в галерею (1 клик)"):
                    rr=api_post(f"/api/gallery/retrain/promote?feedback_id={int(fid)}&title={ptitle}", json={})
                    st.json(rr.json() if rr else {})
            else:
                st.info("Очередь пуста — 👎 пока нет")
    else:
        st.info("Доступно только normocontroller/admin")

elif page=="База знаний":
    st.header("🔎 База знаний изделий")
    st.caption("Поиск по всем проверенным чертежам: обозначение, наименование, материал, масса.")
    q=st.text_input("Запрос", placeholder="АБВГ.123456 или Вал, Сталь 45", key="kb_q")
    topk=st.slider("top_k",1,20,5, key="kb_topk")
    if st.button("Искать в БЗ", key="kb_search"):
        r=api_get(f"/api/checks/knowledge/search?q={q}&top_k={topk}")
        if r and r.status_code==200:
            st.json(r.json())
            for it in r.json().get("results",[]):
                st.write(f"{it.get('designation')} — {it.get('name')} · {it.get('material')} (score {it.get('score')})")
    st.divider()
    st.subheader("Экспорт")
    if st.button("Скачать JSON", key="kb_dl"):
        r=api_get("/api/checks/knowledge/export")
        if r: st.download_button("Скачать", data=json.dumps(r.json(), ensure_ascii=False, indent=2), file_name="knowledge.json", mime="application/json")

elif page=="Аналитика":
    st.header("📊 Аналитика и отчеты")
    days=st.slider("Период (дней)",7,90,30, key="ana_days")
    dept=st.text_input("Отдел (опционально)", placeholder="5", key="ana_dept")
    col1,col2 = st.columns(2)
    with col1:
        r=api_get(f"/api/analytics/summary?days={days}" + (f"&department={dept}" if dept else ""))
        if r and r.status_code==200:
            j=r.json()
            st.metric("Всего проверок", j["total_checks"])
            st.info(j["summary"])
            if j["top_errors"]:
                df=pd.DataFrame(j["top_errors"])
                fig=px.bar(df, x="code", y="count", title="Топ ошибок")
                st.plotly_chart(fig, use_container_width=True)
            if j.get("by_day"):
                df2=pd.DataFrame(list(j["by_day"].items()), columns=["дата","кол-во"])
                fig2=px.line(df2, x="дата", y="кол-во", title="Динамика по дням")
                st.plotly_chart(fig2, use_container_width=True)
    with col2:
        r=api_get(f"/api/analytics/report?days={days}")
        if r and r.status_code==200:
            j=r.json()
            st.subheader("📝 LLM отчёт (Gemma mock)")
            st.write(j.get("summary"))
            for rec in j.get("recommendations",[]):
                st.success(f"→ {rec}")
            st.json(j)
    st.divider()
    r=api_get("/api/analytics/stats")
    if r: st.json(r.json())
    r=api_get("/api/analytics/trends?days=30")
    if r and r.status_code==200:
        st.subheader("Тренды")
        st.json(r.json())
    if st.session_state.role in ("admin","normocontroller"):
        r=api_get("/api/analytics/feedbacks")
        if r and r.status_code==200:
            st.subheader("Обратная связь 👍/👎")
            st.dataframe(pd.DataFrame(r.json()["items"]), use_container_width=True)

elif page=="Админка":
    st.header("⚙️ Админка")
    if st.session_state.role!="admin":
        st.warning("Доступ только для admin (демо admin/admin123)")
        st.stop()
    tab1,tab2,tab3,tab4,tab5 = st.tabs(["Настройки модели","Очередь + Dead letters","Пользователи","Схемы метаданных","Метрики"])
    with tab1:
        r=api_get("/api/admin/settings")
        if r and r.status_code==200:
            s=r.json()
            st.json(s)
            # Показываем VLM API URL без ключа
            st.caption(f"VLM API URL: {s.get('vlm_api_url') or 'не задан (mock)'}")
            with st.form("settings_form"):
                model=st.text_input("VLM_MODEL", value=s["vlm_model"])
                quant=st.selectbox("VLM_QUANTIZATION", ["mock","awq-4bit","gptq-4bit","int8","fp16"], index=["mock","awq-4bit","gptq-4bit","int8","fp16"].index(s["vlm_quantization"]) if s["vlm_quantization"] in ["mock","awq-4bit","gptq-4bit","int8","fp16"] else 0)
                engine=st.selectbox("VLM_ENGINE", ["mock","transformers","vllm","openai"], index=["mock","transformers","vllm","openai"].index(s.get("vlm_engine","mock")) if s.get("vlm_engine","mock") in ["mock","transformers","vllm","openai"] else 0)
                vlm_url=st.text_input("VLM_API_URL", value=s.get("vlm_api_url") or "", placeholder="https://llm.example.com/v1")
                vlm_key=st.text_input("VLM_API_KEY", value="", type="password", placeholder="sk-... (оставьте пустым чтобы не менять)")
                ctx=st.slider("MAX_CONTEXT_WINDOW", 2048, 32768, s["max_context_window"], step=1024)
                width=st.slider("IMAGE_WIDTH", 512,800, s["image_width"])
                vram=st.slider("VRAM_LIMIT_GB", 8,24, s["vram_limit_gb"])
                empty=st.checkbox("EMPTY_CACHE_AFTER_PAGE", value=s["empty_cache_after_page"])
                maxc=st.number_input("MAX_CONCURRENT_VLM", 1,4, s["max_concurrent_vlm"])
                ocr_ens=st.checkbox("OCR_ENSEMBLE", value=s.get("ocr_ensemble", True))
                if st.form_submit_button("Сохранить"):
                    payload={"vlm_model":model,"vlm_quantization":quant,"vlm_engine":engine,"max_context_window":ctx,"image_width":width,"vram_limit_gb":vram,"empty_cache_after_page":empty,"max_concurrent_vlm":maxc,"ocr_ensemble":ocr_ens}
                    if vlm_url: payload["vlm_api_url"]=vlm_url
                    if vlm_key: payload["vlm_api_key"]=vlm_key
                    rr=api_post("/api/admin/settings", json=payload)
                    if rr: st.json(rr.json() if rr.status_code==200 else rr.text)
            st.divider()
            st.subheader("Быстрое переключение (16GB ↔ лёгкая)")
            if st.button("Переключить на Gemma-3-4B (3.5GB)"):
                rr=api_post("/api/admin/switch-model?model=google/gemma-3-4b-it&quantization=mock&engine=mock", json={})
                st.json(rr.json() if rr else {})
            if st.button("Вернуть Gemma-3-12B"):
                rr=api_post("/api/admin/switch-model?model=google/gemma-3-12b-it&quantization=awq-4bit&engine=transformers", json={})
                st.json(rr.json() if rr else {})
    with tab2:
        r=api_get("/api/admin/queue")
        if r: st.json(r.json())
        c1,c2=st.columns(2)
        with c1:
            if st.button("Очистить очередь"):
                rr=api_post("/api/admin/queue/purge", json={})
                st.write(rr.json() if rr else "error")
        with c2:
            r=api_get("/api/admin/dead-letters")
            if r and r.status_code==200:
                st.subheader("Dead letters")
                st.dataframe(pd.DataFrame(r.json()["items"]), use_container_width=True)
        st.divider()
        st.subheader("🗃️ Retention + Корзина + Бэкап (1 клик)")
        c1,c2,c3=st.columns(3)
        with c1:
            days=st.number_input("Дней до корзины", min_value=1, value=90)
            trash_days=st.number_input("Дней в корзине", min_value=1, value=30)
            if st.button("Запустить retention"):
                rr=api_post(f"/api/admin/retention/run?days={int(days)}&trash_days={int(trash_days)}", json={})
                st.json(rr.json() if rr else {})
        with c2:
            if st.button("Показать корзину"):
                rr=api_get("/api/admin/trash")
                if rr: st.json(rr.json())
            rid=st.number_input("ID из корзины для восстановления", min_value=0, step=1)
            if st.button("Восстановить"):
                rr=api_post(f"/api/admin/trash/{int(rid)}/restore", json={})
                st.json(rr.json() if rr else {})
        with c3:
            if st.button("📦 Создать бэкап"):
                rr=requests.post(f"{API}/api/admin/backup", headers=auth_header())
                if rr.status_code==200:
                    st.download_button("Скачать бэкап", data=rr.content, file_name="normoscan_backup.tar.gz", mime="application/gzip")
                else:
                    st.error(rr.text)
    with tab3:
        r=api_get("/api/admin/users")
        if r and r.status_code==200:
            st.dataframe(pd.DataFrame(r.json()["users"]), use_container_width=True)
            uid=st.number_input("ID пользователя", min_value=1, step=1)
            newrole=st.selectbox("Новая роль", ["admin","normocontroller","engineer","viewer"])
            if st.button("Изменить роль"):
                rr=api_post(f"/api/admin/users/{int(uid)}/role?role={newrole}", json={})
                st.write(rr.text if rr else "error")
    with tab4:
        st.subheader("Схемы метаданных")
        r=api_get("/api/admin/schemas")
        if r and r.status_code==200:
            st.json(r.json())
            for s in r.json().get("schemas",[]):
                st.write(f"{'🟢' if s['is_active'] else '⚪'} {s['name']} — {s['title']}")
        with st.form("schema_form"):
            name=st.text_input("name", value="stp_custom")
            title=st.text_input("title", value="СТП завода")
            schema_txt=st.text_area("JSON Schema", value=json.dumps({"type":"object","properties":{"Обозначение":{"type":"string"},"Наименование":{"type":"string"},"Цех":{"type":"string","enum":["5","7","12"]}},"required":["Обозначение","Наименование"]}, ensure_ascii=False, indent=2), height=200)
            make_active=st.checkbox("Сделать активной", value=True)
            if st.form_submit_button("Создать/обновить"):
                try:
                    sch=json.loads(schema_txt)
                    rr=api_post("/api/admin/schemas", json={"name":name,"title":title,"schema_json":sch,"make_active":make_active})
                    st.json(rr.json() if rr else {})
                except Exception as e:
                    st.error(str(e))
    with tab5:
        r=api_get("/api/admin/metrics")
        if r and r.status_code==200:
            st.json(r.json())
            rp=requests.get(f"{API}/metrics", headers=auth_header())
            if rp.status_code==200:
                st.code(rp.text[:2000], language="bash")

elif page=="MCP":
    st.header("🔌 MCP протокол")
    st.write("MCP позволяет внешним LLM (Claude Desktop, Cursor, Continue) использовать НормоСкан как инструмент.")
    st.code(f"{API}/mcp", language="bash")
    r=api_get("/mcp")
    if r: st.json(r.json())
    st.subheader("Пример конфигурации Claude Desktop")
    st.code(json.dumps({
        "mcpServers": {
            "normoscan": {
                "command": "npx",
                "args": ["-y","mcp-remote", f"{API}/mcp"],
                "env": {"API_URL": API}
            }
        }
    }, indent=2, ensure_ascii=False), language="json")
    try:
        tools=requests.post(f"{API}/mcp", json={"jsonrpc":"2.0","id":1,"method":"tools/list"}).json()
        st.json(tools)
    except Exception as e:
        st.error(str(e))
    st.subheader("Тест tools/call")
    tool=st.selectbox("Tool", ["ask_gost","get_check_status","search_gallery","check_drawing","ask_document","search_knowledge","get_fix","get_metrics"])
    args_txt=st.text_area("Arguments JSON", value='{"query":"Что требует ГОСТ 2.104?","top_k":3}')
    if st.button("Вызвать"):
        try:
            args=json.loads(args_txt)
            payload={"jsonrpc":"2.0","id":2,"method":"tools/call","params":{"name":tool,"arguments":args}}
            rr=requests.post(f"{API}/mcp", json=payload).json()
            st.json(rr)
        except Exception as e:
            st.error(str(e))

elif page=="Метрики":
    st.header("📈 Метрики (Prometheus)")
    r=api_get("/api/metrics")
    if r and r.status_code==200:
        snap=r.json()
        col1,col2,col3=st.columns(3)
        with col1: st.metric("Uptime", f"{snap.get('uptime_seconds',0)/3600:.1f}h")
        with col2: st.metric("Checks done", snap.get("counters",{}).get("normoscan_checks_done",0))
        with col3: st.metric("Queue", snap.get("gauges",{}).get("normoscan_queue_depth","-"))
        st.json(snap)
    rp=requests.get(f"{API}/metrics", headers=auth_header())
    if rp.status_code==200:
        st.code(rp.text, language="bash")

elif page=="Логи":
    st.header("📜 Логи и диагностика VLM")
    st.caption("Здесь можно проверить вызовы внешнего VLM и скопировать логи для отправки разработчику. Логи хранятся в памяти (2000 строк) + файл storage/logs/app.log")
    col1,col2 = st.columns([2,1])
    with col1:
        lines=st.slider("Строк", 20, 500, 100, key="log_lines")
        level=st.selectbox("Уровень", ["", "INFO","WARNING","ERROR"])
        if st.button("🔄 Обновить логи"):
            st.rerun()
        r=api_get(f"/api/admin/logs?lines={lines}" + (f"&level={level}" if level else ""))
        if r and r.status_code==200:
            j=r.json()
            st.subheader("Буфер (память)")
            for item in j.get("buffer",[])[-lines:]:
                st.text(f"{item['ts']} {item['level']} {item['logger']}: {item['msg']}")
            if j.get("file_tail"):
                st.subheader("Файл storage/logs/app.log — хвост")
                st.code("\n".join(j["file_tail"]), language="bash")
            st.json({"config": j.get("config"), "total_buffer": j.get("total_buffer")})
            if st.button("📋 Копировать буфер в буфер обмена (JSON)"):
                st.code(json.dumps(j.get("buffer",[]), ensure_ascii=False, indent=2)[:5000])
        else:
            st.error(r.text if r else "API недоступен")
            st.info(f"Проверь что API доступен: {API}/health и что ты админ ({st.session_state.role})")
    with col2:
        st.subheader("🧪 Тест VLM")
        st.caption("Делает тестовый вызов к внешнему VLM (берёт VLM_API_URL/KEY из .env) и показывает логи. Используй чтобы проверить llm.tool.ru")
        prompt=st.text_area("Промпт", value="Тест нормоконтроля: ответь OK", height=80)
        if st.button("🚀 Тест VLM", type="primary"):
            with st.spinner("Вызов VLM..."):
                r=api_post(f"/api/admin/vlm/test?prompt={prompt}", json={})
                if r and r.status_code==200:
                    j=r.json()
                    st.success(f"Elapsed {j.get('elapsed')}s")
                    st.json(j.get("result",{}))
                    st.subheader("VLM конфиг")
                    st.json(j.get("vlm_config"))
                    st.subheader("Последние логи")
                    for lg in j.get("logs",[])[-10:]:
                        st.text(f"{lg.get('ts')} {lg.get('level')} {lg.get('msg')}")
                    if j.get("error"):
                        st.error(j["error"])
                        st.code(j.get("traceback",""))
                else:
                    st.error(r.text if r else "Ошибка")
        st.divider()
        st.subheader("Очистка")
        if st.button("🗑️ Очистить буфер"):
            r=api_post("/api/admin/logs/clear", json={})
            st.json(r.json() if r else {})
        st.info("Логи также в `docker logs normoscan-backend -f` и `docker compose logs backend`")
