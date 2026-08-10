import streamlit as st
import requests, os, json, pandas as pd, plotly.express as px, time, io
from datetime import datetime
from PIL import Image, ImageDraw
import base64

API = os.getenv("API_URL", "http://localhost:8000")

st.set_page_config(page_title="НормоСкан", page_icon="📐", layout="wide", initial_sidebar_state="expanded")

# Горячие клавиши: Space следующий лист, 1/2/3 👍/👎/fix, Ctrl+Enter спросить
st.markdown("""
<script>
document.addEventListener('keydown', (e)=>{
  if(e.target.tagName==='INPUT' && e.key!=='Enter') return;
  if(e.code==='Space' && !e.ctrlKey){ e.preventDefault(); window.dispatchEvent(new CustomEvent('hotkey', {detail:'next'})); }
  if(e.key==='1' && !e.ctrlKey){ document.querySelector('[data-testid=\"like\"]')?.click(); }
  if(e.key==='2'){ document.querySelector('[data-testid=\"dislike\"]')?.click(); }
  if(e.key==='3'){ document.querySelector('[data-testid=\"fix\"]')?.click(); }
  if(e.ctrlKey && e.key==='Enter'){ document.querySelector('[data-testid=\"ask\"]')?.click(); }
});
</script>
<style>kbd{background:#eee;border:1px solid #ccc;padding:2px 6px;border-radius:4px;font-size:0.85em}</style>
""", unsafe_allow_html=True)
st.caption("Горячие клавиши: <kbd>Space</kbd> след.лист <kbd>1</kbd>👍 <kbd>2</kbd>👎 <kbd>3</kbd>fix <kbd>Ctrl+Enter</kbd> спросить")

if "token" not in st.session_state:
    st.session_state.token=None
    st.session_state.role=None
    st.session_state.username=None

def auth_header():
    return {"Authorization": f"Bearer {st.session_state.token}"} if st.session_state.token else {}

def api_get(path, **kw):
    try:
        r = requests.get(f"{API}{path}", headers=auth_header(), timeout=15)
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

# Sidebar
with st.sidebar:
    st.title("📐 НормоСкан")
    st.caption("Интеллектуальный нормоконтроль · 16GB VRAM")
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
        st.warning("Весь инференс локальный. Данные не уходят наружу.")
    else:
        st.success(f"Вы: {st.session_state.username} ({st.session_state.role})")
        if st.button("Выйти"):
            st.session_state.token=None
            st.rerun()
    st.divider()
    page = st.radio("Навигация", ["Загрузка","Проверки","ГОСТы","Галерея","База знаний","Аналитика","Админка","MCP","Метрики"], index=0)
    st.divider()
    st.caption(f"API: {API}")
    try:
        h=requests.get(f"{API}/health",timeout=2).json()
        st.caption(f"Модель: {h.get('model','')} | ctx {h.get('context_window')} | {h.get('engine','')}")
        if h.get("ocr_ensemble"):
            st.caption("OCR ансамбль: вкл")
    except: pass
    st.caption("VRAM 16GB optimised · 768px · 4-bit")

if not st.session_state.token:
    st.title("📐 НормоСкан — вход required")
    st.stop()

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
            # bbox is relative [x,y,w,h]
            x,y,bw,bh = bbox
            left=int(x*w); upper=int(y*h); right=int((x+bw)*w); lower=int((y+bh)*h)
            color = (255,0,0,180) if a.get("severity")=="error" else (255,165,0,180) if a.get("severity")=="warning" else (0,0,255,120)
            draw.rectangle([left,upper,right,lower], outline=color[:3], width=3)
            draw.rectangle([left,upper,right,lower], fill=color[:3]+(40,))
            # label
            draw.text((left, upper-12), a.get("code",""), fill=(255,0,0))
        return im
    except Exception as e:
        st.warning(f"Не удалось отрисовать: {e}")
        return None

# === PAGES ===
if page=="Загрузка":
    st.header("📤 Загрузка чертежа")
    st.info("Поддерживается PDF А0-А4. Система: 768px ресайз + кроп (штамп/ТТ/графика) → OCR ансамбль → Hybrid RAG (Qdrant) → Gemma-3-12B 4-bit → JSON + чек-лист. Дедeпликация по хэшу 5 мин.")
    col1,col2 = st.columns([2,1])
    with col1:
        prio = st.select_slider("Приоритет", options=[1,3,5,8,10], value=5, help="1=высший")
        up = st.file_uploader("Выберите PDF", type=["pdf"])
        dedupe_info = st.empty()
        if up:
            # клиентский хэш для подсказки
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
                        # SSE прогресс
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
                    # Checklist
                    cl = d.get("checklist")
                    if cl:
                        st.subheader("✅ Чек-лист ГОСТов")
                        for item in cl.get("items",[]):
                            icon = "❌" if item["status"]=="fail" else "✅"
                            st.write(f"{icon} **{item['code']}** — {item['desc']} ({item['count']} замечаний)" if item["status"]=="fail" else f"{icon} {item['code']} — {item['desc']}")
                    # metadata
                    with st.expander("📄 Метаданные (штамп)", expanded=True):
                        st.json(d.get("meta_json") or {})
                        # validation via active schema
                        if st.button("Проверить по схеме"):
                            st.info("Схема проверяется на сервере при анализе (см. /api/checks/meta/schema)")
                    if d.get("consistency") and not d["consistency"].get("consistent"):
                        st.warning("Несоответствия между листами:")
                        for iss in d["consistency"]["issues"]:
                            st.error(f"{iss['msg']} → {iss.get('suggested_fix','')}")
                            st.json(iss)
                    # errors with fixes
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
                                # annotations bbox
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
                    # pages + annotations
                    st.subheader("📑 Постранично + аннотации")
                    # fetch annotations
                    ann_r = api_get(f"/api/checks/{int(sel)}/annotations")
                    ann_data = ann_r.json() if ann_r and ann_r.status_code==200 else {"annotations":[]}
                    for p in d.get("pages",[]):
                        with st.expander(f"Лист {p['page_number']} — {len(p.get('errors') or [])} ошибок, OCR {p.get('ocr_confidence',0):.0%}"):
                            st.json(p)
                            # Try to show annotated image if available
                            # We don't have direct image path via API, but via /storage
                            # For demo, show placeholder
                            # Спросить по документу
                    st.subheader("💬 Вопрос по документу")
                    q=st.text_input("Задайте вопрос (напр. 'какая масса?', 'чек-лист?', 'какие ошибки по ГОСТ 2.307?')", key="ask_doc_q")
                    colA,colB=st.columns(2)
                    with colA:
                        if st.button("Спросить"):
                            rrr=api_post(f"/api/checks/{d['id']}/ask", json={"query":q})
                            if rrr and rrr.status_code==200:
                                st.json(rrr.json())
                    with colB:
                        if st.button("Показать аннотации JSON"):
                            st.json(ann_data)
                    # SSE stream demo
                    if d["status"] in ("queued","processing"):
                        if st.button("📡 Следить (SSE)"):
                            st.info("SSE стрим: /api/checks/{id}/stream — в браузере EventSource, здесь polling fallback")
                            bar=st.progress(d["pages_done"]/max(d["pages_total"],1))
                else:
                    st.error("Не найдено")
        else:
            st.info("Пока нет проверок — загрузите PDF")

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
            # obsolete action
            if st.session_state.role=="admin":
                gid=st.number_input("ID ГОСТа для пометки obsolete", min_value=0, step=1)
                sup=st.text_input("Заменён на", placeholder="ГОСТ 2.104-2024")
                if st.button("Пометить obsolete"):
                    rr=api_post(f"/api/gosts/{int(gid)}/obsolete?superseded_by={sup}", json={})
                    st.json(rr.json() if rr else {})
        else:
            st.info("ГОСТов нет")
    # Diff ГОСТов
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
                    st.components.v1.html(j["html"], height=300, scrolling=True)
            else:
                st.error(r.text if r else "Ошибка")
    st.divider()
    st.subheader("Поиск / Вопрос по ГОСТам — Hybrid RAG + cross-encoder re-rank")
    q=st.text_input("Вопрос", placeholder="Какие требования к основной надписи по ГОСТ 2.104?")
    # Autocomplete
    if len(q.strip())>=2:
        r_ac=api_get(f"/api/gosts/autocomplete?q={q}&limit=5")
        if r_ac and r_ac.status_code==200:
            sug=r_ac.json().get("suggestions",[])
            if sug:
                st.caption("Автодополнение: " + " · ".join(sug))
                sel=st.selectbox("Выбрать подсказку", [""]+sug, key="ac_sel")
                if sel:
                    q=sel
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
    st.caption("Перетащите скриншот → кроп узла → добавит в Qdrant. При >82% близости VLM получит подсказку.")
    c1,c2=st.columns([1,1])
    with c1:
        st.subheader("Добавить")
        up=st.file_uploader("Скриншот", type=["png","jpg","jpeg"], key="gal_up")
        # crop preview
        if up:
            img=Image.open(up)
            st.image(img, caption="Оригинал (вырежьте узел в редакторе выше, если нужно)", use_column_width=True)
            # Simple crop sliders for demo
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
    q=st.text_input("Запрос", placeholder="АБВГ.123456 или Вал, Сталь 45")
    topk=st.slider("top_k",1,20,5, key="kb_topk")
    if st.button("Искать в БЗ"):
        r=api_get(f"/api/checks/knowledge/search?q={q}&top_k={topk}")
        if r and r.status_code==200:
            st.json(r.json())
            for it in r.json().get("results",[]):
                st.write(f"{it.get('designation')} — {it.get('name')} · {it.get('material')} (score {it.get('score')})")
    st.divider()
    st.subheader("Экспорт")
    if st.button("Скачать JSON"):
        r=api_get("/api/checks/knowledge/export")
        if r: st.download_button("Скачать", data=json.dumps(r.json(), ensure_ascii=False, indent=2), file_name="knowledge.json", mime="application/json")

elif page=="Аналитика":
    st.header("📊 Аналитика и отчеты")
    days=st.slider("Период (дней)",7,90,30)
    dept=st.text_input("Отдел (опционально)", placeholder="5")
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
            with st.form("settings_form"):
                model=st.text_input("VLM_MODEL", value=s["vlm_model"])
                quant=st.selectbox("VLM_QUANTIZATION", ["mock","awq-4bit","gptq-4bit","int8","fp16"], index=["mock","awq-4bit","gptq-4bit","int8","fp16"].index(s["vlm_quantization"]) if s["vlm_quantization"] in ["mock","awq-4bit","gptq-4bit","int8","fp16"] else 0)
                engine=st.selectbox("VLM_ENGINE", ["mock","transformers","vllm"], index=["mock","transformers","vllm"].index(s.get("vlm_engine","mock")) if s.get("vlm_engine","mock") in ["mock","transformers","vllm"] else 0)
                ctx=st.slider("MAX_CONTEXT_WINDOW", 2048, 32768, s["max_context_window"], step=1024)
                width=st.slider("IMAGE_WIDTH", 512,800, s["image_width"])
                vram=st.slider("VRAM_LIMIT_GB", 8,24, s["vram_limit_gb"])
                empty=st.checkbox("EMPTY_CACHE_AFTER_PAGE", value=s["empty_cache_after_page"])
                maxc=st.number_input("MAX_CONCURRENT_VLM", 1,4, s["max_concurrent_vlm"])
                ocr_ens=st.checkbox("OCR_ENSEMBLE", value=s.get("ocr_ensemble", True))
                if st.form_submit_button("Сохранить"):
                    rr=api_post("/api/admin/settings", json={"vlm_model":model,"vlm_quantization":quant,"vlm_engine":engine,"max_context_window":ctx,"image_width":width,"vram_limit_gb":vram,"empty_cache_after_page":empty,"max_concurrent_vlm":maxc,"ocr_ensemble":ocr_ens})
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
            # prometheus text
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
