import streamlit as st
import requests, os, json, pandas as pd, plotly.express as px
from datetime import datetime

API = os.getenv("API_URL", "http://localhost:8000")

st.set_page_config(page_title="НормоСкан", page_icon="📐", layout="wide", initial_sidebar_state="expanded")

# --- Auth ---
if "token" not in st.session_state:
    st.session_state.token=None
    st.session_state.role=None
    st.session_state.username=None

def auth_header():
    return {"Authorization": f"Bearer {st.session_state.token}"} if st.session_state.token else {}

def api_get(path, **kw):
    try:
        r = requests.get(f"{API}{path}", headers=auth_header(), timeout=10)
        return r
    except Exception as e:
        st.error(f"API недоступен: {e}")
        return None

def api_post(path, json=None, files=None, data=None):
    try:
        r = requests.post(f"{API}{path}", headers=auth_header(), json=json, files=files, data=data, timeout=30)
        return r
    except Exception as e:
        st.error(f"API недоступен: {e}")
        return None

# Sidebar auth
with st.sidebar:
    st.title("📐 НормоСкан")
    st.caption("Интеллектуальный нормоконтроль")
    if not st.session_state.token:
        st.subheader("Вход")
        u = st.text_input("Логин", value="admin")
        p = st.text_input("Пароль", value="admin123", type="password")
        if st.button("Войти"):
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
    else:
        st.success(f"Вы: {st.session_state.username} ({st.session_state.role})")
        if st.button("Выйти"):
            st.session_state.token=None
            st.rerun()
    st.divider()
    page = st.radio("Навигация", ["Проверки","Загрузка","ГОСТы","Галерея","Аналитика","Вопросы","Админка","MCP"], index=0)
    st.divider()
    st.caption(f"API: {API}")
    try:
        h=requests.get(f"{API}/health",timeout=2).json()
        st.caption(f"Модель: {h.get('model','')} | ctx {h.get('context_window','')}")
    except: pass

if not st.session_state.token:
    st.title("📐 НормоСкан — вход required")
    st.stop()

# --- Helpers ---
def status_badge(s):
    colors={"queued":"🟡","processing":"🔵","done":"🟢","failed":"🔴"}
    return f"{colors.get(s,'⚪')} {s}"

# === PAGES ===
if page=="Загрузка":
    st.header("📤 Загрузка чертежа на проверку")
    st.write("Поддерживается PDF (А0-А4). Система разобьёт на страницы 512–800px, выполнит кроп, OCR, Hybrid RAG и VLM анализ.")
    prio = st.select_slider("Приоритет", options=[1,3,5,8,10], value=5, help="1=высший, 10=низший")
    up = st.file_uploader("Выберите PDF", type=["pdf"])
    if up and st.button("Запустить проверку"):
        with st.spinner("Загрузка..."):
            files={"file": (up.name, up.getvalue(), "application/pdf")}
            r = api_post(f"/api/checks/upload?priority={prio}", files=files)
            if r and r.status_code==200:
                j=r.json()
                st.success(f"Проверка #{j['check_id']} поставлена в очередь ({j['status']})")
                st.json(j)
            else:
                st.error(r.text if r else "Ошибка")

elif page=="Проверки":
    st.header("📋 Реестр проверок")
    col1,col2=st.columns([1,1])
    with col1:
        status_filter=st.selectbox("Статус", ["all","queued","processing","done","failed"])
    with col2:
        if st.button("Обновить"):
            st.rerun()
    params=""
    if status_filter!="all":
        params=f"?status={status_filter}"
    r=api_get(f"/api/checks/{params}")
    if r and r.status_code==200:
        j=r.json()
        st.metric("Всего", j["total"])
        df=pd.DataFrame(j["items"])
        if not df.empty:
            df["badge"]=df["status"].apply(status_badge)
            st.dataframe(df[["id","filename","badge","status","pages_done","pages_total","created_at"]], use_container_width=True)
            # detail
            sel=st.number_input("Открыть проверку ID", min_value=0, step=1)
            if sel:
                rr=api_get(f"/api/checks/{int(sel)}")
                if rr and rr.status_code==200:
                    d=rr.json()
                    st.subheader(f"Проверка #{d['id']} — {d['filename']} {status_badge(d['status'])}")
                    st.write(d["summary"] or "")
                    # metadata
                    st.json(d.get("meta_json") or {})
                    # consistency
                    if d.get("consistency") and not d["consistency"].get("consistent"):
                        st.warning("Несоответствия между листами:")
                        st.json(d["consistency"]["issues"])
                    # errors
                    errs=d.get("errors_json") or []
                    if errs:
                        st.error(f"Найдено {len(errs)} замечаний")
                        for e in errs:
                            with st.expander(f"{e.get('code','')} — {e.get('msg','')[:60]}"):
                                st.json(e)
                                c1,c2=st.columns(2)
                                with c1:
                                    if st.button(f"👍 Полезно {e.get('id','')}", key=f"like_{e.get('id')}"):
                                        api_post("/api/checks/feedback", json={"check_id":d["id"],"error_id":e.get("id"),"vote":"like"})
                                        st.toast("Спасибо!")
                                with c2:
                                    if st.button(f"👎 Ошибка {e.get('id','')}", key=f"dis_{e.get('id')}"):
                                        api_post("/api/checks/feedback", json={"check_id":d["id"],"error_id":e.get("id"),"vote":"dislike","comment":"false positive"})
                                        st.toast("Отправлено на переобучение")
                    else:
                        st.success("Замечаний не найдено")
                    # pages
                    st.subheader("Постранично")
                    for p in d.get("pages",[]):
                        with st.expander(f"Лист {p['page_number']} — {len(p.get('errors') or [])} ошибок"):
                            st.json(p)
                            if st.button("Задать вопрос по листу", key=f"ask_{p['page_number']}"):
                                q=st.text_input("Вопрос", key=f"q_{p['page_number']}")
                                if q:
                                    rrr=api_post(f"/api/checks/{d['id']}/ask", json={"query":q})
                                    if rrr: st.write(rrr.json())
                    # ask document
                    st.subheader("Вопрос по документу")
                    q=st.text_input("Задайте вопрос (напр. 'какая масса?', 'какие ошибки по ГОСТ 2.307?')", key="ask_doc_q")
                    if st.button("Спросить"):
                        rrr=api_post(f"/api/checks/{d['id']}/ask", json={"query":q})
                        if rrr and rrr.status_code==200:
                            st.json(rrr.json())
                else:
                    st.error("Не найдено")
        else:
            st.info("Пока нет проверок — загрузите PDF")

elif page=="ГОСТы":
    st.header("📚 База ГОСТов (Vector DB)")
    st.write("Укажите папку с сырыми PDF ГОСТов — сервис сам проиндексирует. Поддерживается Qdrant/Milvus/memory.")
    c1,c2=st.columns(2)
    with c1:
        path=st.text_input("Путь к папке", value="./storage/gosts")
        if st.button("Индексировать папку"):
            r=api_post("/api/gosts/ingest", json={"path": path})
            if r: st.json(r.json() if r.status_code==200 else r.text)
    with c2:
        up=st.file_uploader("Загрузить один ГОСТ PDF", type=["pdf"])
        desig=st.text_input("Обозначение (опционально)", placeholder="ГОСТ 2.104-2006")
        if up and st.button("Загрузить и индексировать"):
            files={"file": (up.name, up.getvalue(), "application/pdf")}
            data={"designation": desig} if desig else None
            r=api_post("/api/gosts/upload", files=files, data=data)
            if r: st.json(r.json() if r.status_code==200 else r.text)
    st.divider()
    # list
    r=api_get("/api/gosts/")
    if r and r.status_code==200:
        j=r.json()
        st.dataframe(pd.DataFrame(j["items"]), use_container_width=True)
    st.divider()
    st.subheader("Поиск / Вопрос по ГОСТам")
    q=st.text_input("Вопрос", placeholder="Какие требования к основной надписи по ГОСТ 2.104?")
    topk=st.slider("top_k",1,10,3)
    if st.button("Искать"):
        r=api_post("/api/gosts/search", json={"query":q,"top_k":topk})
        if r and r.status_code==200:
            j=r.json()
            st.json(j)
            for h in j.get("hits",[]):
                with st.expander(f"{h['payload'].get('designation')} — {h['score']:.2f}"):
                    st.write(h.get("snippet") or h["payload"].get("text","")[:500])

elif page=="Галерея":
    st.header("🖼️ Галерея ошибок и эталонов (Visual RAG)")
    st.write("Перетащите скриншот ошибки — система добавит в базу и будет подсказывать VLM при высокой косинусной близости.")
    c1,c2=st.columns(2)
    with c1:
        up=st.file_uploader("Скриншот", type=["png","jpg","jpeg"])
        title=st.text_input("Название", value="Неверная засечка стрелки")
        cat=st.selectbox("Категория", ["error","etalon"])
        gost_ref=st.text_input("Ссылка на ГОСТ", value="ГОСТ 2.305")
        err_type=st.text_input("Тип ошибки", value="Неверная засечка стрелки")
        if up and st.button("Добавить в галерею"):
            files={"file": (up.name, up.getvalue(), "image/png")}
            data={"title":title,"category":cat,"gost_ref":gost_ref,"error_type":err_type}
            r=api_post("/api/gallery/upload", files=files, data=data)
            if r: st.json(r.json() if r.status_code==200 else r.text)
    with c2:
        r=api_get("/api/gallery/")
        if r and r.status_code==200:
            j=r.json()
            st.dataframe(pd.DataFrame(j["items"]), use_container_width=True)
    st.divider()
    st.subheader("Поиск похожих")
    qimg=st.file_uploader("Запрос-изображение для поиска", type=["png","jpg"], key="qimg")
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

elif page=="Аналитика":
    st.header("📊 Аналитика и отчеты")
    days=st.slider("Период (дней)",7,90,30)
    dept=st.text_input("Отдел (опционально)", placeholder="5")
    r=api_get(f"/api/analytics/summary?days={days}" + (f"&department={dept}" if dept else ""))
    if r and r.status_code==200:
        j=r.json()
        st.metric("Всего проверок", j["total_checks"])
        st.info(j["summary"])
        if j["top_errors"]:
            df=pd.DataFrame(j["top_errors"])
            fig=px.bar(df, x="code", y="count", title="Топ ошибок")
            st.plotly_chart(fig, use_container_width=True)
    st.divider()
    r=api_get("/api/analytics/stats")
    if r: st.json(r.json())
    if st.session_state.role in ("admin","normocontroller"):
        r=api_get("/api/analytics/feedbacks")
        if r and r.status_code==200:
            st.subheader("Обратная связь 👍/👎")
            st.dataframe(pd.DataFrame(r.json()["items"]), use_container_width=True)

elif page=="Вопросы":
    st.header("💬 Вопросы по ГОСТам и документам")
    tab1,tab2=st.tabs(["Вопрос по ГОСТам","Вопрос по документу"])
    with tab1:
        q=st.text_input("Вопрос по ГОСТам", placeholder="Что требует ГОСТ 2.307 по допускам?")
        if st.button("Спросить ГОСТ", key="ask_gost_btn"):
            r=api_post("/api/gosts/ask", json={"query":q})
            if r: st.json(r.json())
    with tab2:
        cid=st.number_input("ID проверки", min_value=1, step=1, key="cid_q")
        q2=st.text_input("Вопрос по документу", placeholder="Какая масса указана?")
        if st.button("Спросить документ"):
            r=api_post(f"/api/checks/{int(cid)}/ask", json={"query":q2})
            if r: st.json(r.json() if r.status_code==200 else r.text)

elif page=="Админка":
    st.header("⚙️ Админка")
    if st.session_state.role!="admin":
        st.warning("Доступ только для admin (демо admin/admin123)")
        st.stop()
    tab1,tab2,tab3=st.tabs(["Настройки модели","Очередь","Пользователи"])
    with tab1:
        r=api_get("/api/admin/settings")
        if r and r.status_code==200:
            s=r.json()
            st.json(s)
            with st.form("settings_form"):
                model=st.text_input("VLM_MODEL", value=s["vlm_model"])
                quant=st.selectbox("VLM_QUANTIZATION", ["mock","awq-4bit","gptq-4bit","int8","fp16"], index=["mock","awq-4bit","gptq-4bit","int8","fp16"].index(s["vlm_quantization"]) if s["vlm_quantization"] in ["mock","awq-4bit","gptq-4bit","int8","fp16"] else 0)
                ctx=st.slider("MAX_CONTEXT_WINDOW", 2048, 32768, s["max_context_window"], step=1024)
                width=st.slider("IMAGE_WIDTH", 512,800, s["image_width"])
                vram=st.slider("VRAM_LIMIT_GB", 8,24, s["vram_limit_gb"])
                empty=st.checkbox("EMPTY_CACHE_AFTER_PAGE", value=s["empty_cache_after_page"])
                maxc=st.number_input("MAX_CONCURRENT_VLM", 1,4, s["max_concurrent_vlm"])
                if st.form_submit_button("Сохранить"):
                    rr=api_post("/api/admin/settings", json={"vlm_model":model,"vlm_quantization":quant,"max_context_window":ctx,"image_width":width,"vram_limit_gb":vram,"empty_cache_after_page":empty,"max_concurrent_vlm":maxc})
                    if rr: st.json(rr.json() if rr.status_code==200 else rr.text)
    with tab2:
        r=api_get("/api/admin/queue")
        if r: st.json(r.json())
        if st.button("Очистить очередь"):
            rr=api_post("/api/admin/queue/purge", json={})
            st.write(rr.json() if rr else "error")
    with tab3:
        r=api_get("/api/admin/users")
        if r and r.status_code==200:
            st.dataframe(pd.DataFrame(r.json()["users"]), use_container_width=True)
            uid=st.number_input("ID пользователя", min_value=1, step=1)
            newrole=st.selectbox("Новая роль", ["admin","normocontroller","engineer","viewer"])
            if st.button("Изменить роль"):
                rr=api_post(f"/api/admin/users/{int(uid)}/role?role={newrole}", json={})
                st.write(rr.text if rr else "error")

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
    st.subheader("Инструменты")
    try:
        tools=requests.post(f"{API}/mcp", json={"jsonrpc":"2.0","id":1,"method":"tools/list"}).json()
        st.json(tools)
    except Exception as e:
        st.error(str(e))
    st.subheader("Тест tools/call")
    tool=st.selectbox("Tool", ["ask_gost","get_check_status","search_gallery","check_drawing","ask_document"])
    args_txt=st.text_area("Arguments JSON", value='{"query":"Что требует ГОСТ 2.104?","top_k":3}')
    if st.button("Вызвать"):
        try:
            args=json.loads(args_txt)
            payload={"jsonrpc":"2.0","id":2,"method":"tools/call","params":{"name":tool,"arguments":args}}
            rr=requests.post(f"{API}/mcp", json=payload).json()
            st.json(rr)
        except Exception as e:
            st.error(str(e))
