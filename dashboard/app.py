"""dashboard/app.py — painel do StriderEdge OS (cliente da API REST).

API-first: o dashboard NÃO importa core/analytics — ele só consome a API
(http://localhost:8000). É só mais um cliente, igual o futuro app mobile.

Rode antes:  uvicorn api.main:app        (a API)
Depois:      streamlit run dashboard/app.py
"""

import statistics

import folium
import httpx
import pandas as pd
import plotly.graph_objects as go
import streamlit as st
from streamlit_folium import st_folium

API = "http://localhost:8000/api/v1"

st.set_page_config(page_title="StriderEdge OS", layout="wide")
GREEN, RED, GRAY = "#1f9d55", "#e3342f", "#9aa0a6"


@st.cache_data(ttl=300)
def api_get(path: str):
    r = httpx.get(f"{API}{path}", timeout=30.0)
    r.raise_for_status()
    return r.json()


def fmt_pace(distance_m, duration_s) -> str:
    if not distance_m or not duration_s:
        return "—"
    s = duration_s / (distance_m / 1000)
    return f"{int(s // 60)}:{int(s % 60):02d}/km"


def fmt_duration(s) -> str:
    if not s:
        return "—"
    m = int(s // 60)
    return f"{m // 60}h{m % 60:02d}" if m >= 60 else f"{m}min"


# --- Seletor (consome a API; erro claro se ela estiver fora do ar) ---
try:
    activities = api_get("/activities")
except Exception as e:
    st.error(f"Não consegui falar com a API. Ela está rodando? (`uvicorn api.main:app`)\n\n{e}")
    st.stop()

labels = {f"{a['activity_name']} — {a['activity_id'][:8]}": a["activity_id"] for a in activities}
chosen = st.sidebar.selectbox("Atividade", list(labels.keys()))
activity_id = labels[chosen]

# Prontidão / carga acumulada (ACWR) — nível ATLETA, sempre visível na sidebar.
_tl = api_get("/training-load")
if _tl:
    last = _tl[-1]
    icon = {"zona segura": "🟢", "atencao": "🟡", "risco de lesao": "🔴",
            "destreino": "🔵", "aquecendo": "⚪"}.get(last["status"], "⚪")
    st.sidebar.divider()
    st.sidebar.metric(
        "Prontidão (ACWR)",
        f"{icon} {last['acwr'] if last['acwr'] is not None else '—'}",
        last["status"],
    )
    if last.get("ramp_pct") is not None:
        st.sidebar.caption(f"Carga semanal: {last['ramp_pct']:+}%")

# Fitness / previsão de prova (Riegel) — nível ATLETA, abaixo da prontidão.
_fit = api_get("/fitness")
if _fit and _fit.get("predictions"):
    st.sidebar.divider()
    trend = _fit.get("fitness", {}).get("trend", "")
    trend_icon = {"melhorando": "📈", "caindo": "📉", "estavel": "➡️"}.get(trend, "")
    st.sidebar.markdown(f"**Previsão de prova** {trend_icon}")
    for p in _fit["predictions"]:
        m, s = divmod(p["time_s"], 60)
        h, m = divmod(m, 60)
        tempo = f"{h}:{m:02d}:{s:02d}" if h else f"{m}:{s:02d}"
        st.sidebar.caption(f"{p['race']}: **{tempo}**  ({p['pace_s_km']/60:.2f} min/km)")
    if trend and trend != "dados insuficientes":
        st.sidebar.caption(f"Fitness: {trend}")

detail = api_get(f"/activities/{activity_id}")
tele = pd.DataFrame(api_get(f"/activities/{activity_id}/telemetry"))
if not tele.empty:
    tele["timestamp"] = pd.to_datetime(tele["timestamp"])

bp = detail["breaking_point"]
bp_ts = pd.to_datetime(bp["breaking_point"]) if bp.get("breaking_point") else None

# --- HERO ---
st.title(f"🏃 {detail['name']}")
st.caption(detail["type"])
k1, k2, k3, k4, k5 = st.columns(5)
k1.metric("Distância", f"{(detail['distance_m'] or 0)/1000:.2f} km")
k2.metric("Duração", fmt_duration(detail["duration_s"]))
k3.metric("Pace", fmt_pace(detail["distance_m"], detail["duration_s"]))
k4.metric("FC média", f"{(detail['avg_hr'] or 0):.0f} bpm")
k5.metric("Cadência", f"{(detail['avg_cadence'] or 0):.0f} spm")

tab_geral, tab_esforco, tab_passada, tab_mapa, tab_ask = st.tabs(
    ["Visão geral", "Esforço", "Passada", "Mapa", "Pergunte"])

# --- Visão geral ---
with tab_geral:
    st.subheader("Destaques")
    d1, d2 = st.columns(2)
    if bp.get("breaking_point"):
        d1.metric("Ponto de quebra", f"{bp_ts:%H:%M:%S}",
                  f"cadência {bp['cadence_at_break']:.0f} (−{bp['cadence_drop_pct']}%)",
                  delta_color="inverse")
    else:
        d1.metric("Ponto de quebra", "estável", "sem fadiga detectada")
    drop = detail["efficiency"]["uphill_efficiency_drop_pct"]
    d2.metric("Eficiência na subida", f"−{drop}%" if drop is not None else "—",
              "queda vs. plano" if drop is not None else "sem subidas")

    st.divider()
    st.subheader("🤖 Veredito do Coach")
    vkey = f"verdict_{activity_id}"
    if st.button("Gerar veredito", type="primary"):
        try:
            with st.spinner("O Coach está analisando (LLM local + RAG)..."):
                r = httpx.post(f"{API}/activities/{activity_id}/coach", timeout=180.0)
                r.raise_for_status()
                st.session_state[vkey] = r.json()["verdict"]
        except Exception as e:
            st.error(f"Falha ao gerar o veredito (API/Ollama no ar?): {e}")
    if vkey in st.session_state:
        st.write(st.session_state[vkey])
    else:
        st.caption("Clique em *Gerar veredito* (roda local, leva alguns segundos).")

# --- Esforço ---
with tab_esforco:
    st.subheader("Frequência cardíaca")
    fig = go.Figure()
    fig.add_trace(go.Scatter(x=tele["timestamp"], y=tele["heart_rate"], mode="lines",
                             name="FC", line=dict(color=RED)))
    if bp_ts is not None:
        fig.add_vline(x=bp_ts, line_color=RED, line_dash="dash",
                      annotation_text="quebra", annotation_position="top")
    fig.update_layout(height=380, margin=dict(t=30, b=0), yaxis_title="bpm")
    st.plotly_chart(fig, use_container_width=True)

    st.subheader("Intensidade — tempo por zona de FC")
    zd = detail["hr_zones"]
    if zd.get("zones"):
        faixas = [z["faixa"] for z in zd["zones"]]
        pcts = [z["pct"] for z in zd["zones"]]
        palette = ["#3b82f6", GREEN, "#eab308", "#f97316", RED, "#991b1b"]
        colors = [palette[min(i, len(palette) - 1)] for i in range(len(faixas))]
        figz = go.Figure(go.Bar(x=faixas, y=pcts, marker_color=colors,
                                text=[f"{p}%" for p in pcts], textposition="outside"))
        figz.update_layout(height=300, margin=dict(t=20, b=0), yaxis_title="% do tempo",
                           xaxis_title=f"faixa de FC (bpm) · FC máx {zd['hr_max']}")
        st.plotly_chart(figz, use_container_width=True)
        st.caption("Faixas à direita (mais vermelhas) = trechos mais desgastantes.")
    else:
        st.info("Sem dados de zona de FC para este treino.")

# --- Passada ---
with tab_passada:
    st.subheader("Cadência")
    figc = go.Figure()
    figc.add_trace(go.Scatter(x=tele["timestamp"], y=tele["cadence"], mode="lines",
                              name="cadência", line=dict(color=GREEN)))
    if bp_ts is not None:
        figc.add_vline(x=bp_ts, line_color=RED, line_dash="dash",
                       annotation_text="quebra", annotation_position="top")
    figc.update_layout(height=320, margin=dict(t=30, b=0), yaxis_title="passos/min")
    st.plotly_chart(figc, use_container_width=True)

    st.subheader("Eficiência por terreno (velocidade ÷ FC)")
    terr = detail["efficiency"]["by_terrain"]
    if terr:
        order = [t for t in ["plano", "subida", "descida"] if t in terr]
        figt = go.Figure(go.Bar(
            x=order, y=[terr[t]["eficiencia"] for t in order],
            marker_color=[GREEN if t == "plano" else (RED if t == "subida" else GRAY) for t in order]))
        figt.update_layout(height=280, margin=dict(t=10, b=0), yaxis_title="eficiência")
        st.plotly_chart(figt, use_container_width=True)
    else:
        st.info("Sem dados de eficiência para este treino.")

    with st.expander("Análise espectral da cadência (avançado)"):
        spec = api_get(f"/activities/{activity_id}/cadence-spectrum")
        if spec.get("points"):
            sdf = pd.DataFrame(spec["spectrum"]).set_index("frequencies")
            st.caption(f"Frequência dominante: {spec['dominant_frequency_hz']:.4f} Hz")
            st.line_chart(sdf)
        else:
            st.write("Sem cadência registrada.")

# --- Mapa: semáforo de cadência ---
with tab_mapa:
    track = api_get(f"/activities/{activity_id}/track")
    coords = list(zip(track["smooth"]["latitude"], track["smooth"]["longitude"]))
    raw = list(zip(track["raw"]["latitude"], track["raw"]["longitude"]))
    cadence = track["cadence"]
    if not coords:
        st.info("🏠 Treino indoor — sem dados de GPS para mapear.")
    else:
        st.subheader("Trilha — semáforo de cadência")
        show_raw = st.toggle("Ver GPS cru (dados brutos)", value=False)
        fmap = folium.Map(location=coords[len(coords) // 2], zoom_start=15)
        if show_raw:
            folium.PolyLine(raw, color=GRAY, weight=2, opacity=0.4, tooltip="GPS cru").add_to(fmap)
        cads = [c for c in cadence if c]
        if cads:
            base = statistics.median(cads)

            def band(c):
                if not c:
                    return GRAY
                if c >= 0.95 * base:
                    return GREEN
                if c >= 0.90 * base:
                    return "#eab308"
                return RED

            colors = [band(c) for c in cadence]
            i, n = 0, len(coords)
            while i < n - 1:
                j = i
                while j < n - 1 and colors[j + 1] == colors[i]:
                    j += 1
                folium.PolyLine(coords[i:j + 2], color=colors[i], weight=4).add_to(fmap)
                i = j + 1
            st.caption(f"🟢 estável · 🟡 caindo · 🔴 arrastando (base {base:.0f} spm)")
        else:
            folium.PolyLine(coords, color=GREEN, weight=3).add_to(fmap)
            st.caption("Sem cadência — trilha suavizada (Kalman).")
        st_folium(fmap, width=900, height=460, returned_objects=[])

# --- Pergunte: coach agêntico text-to-SQL ---
with tab_ask:
    st.subheader("🔎 Pergunte sobre seus treinos")
    st.caption("O coach traduz sua pergunta em SQL, consulta seus dados e responde. "
               "Ex: *qual meu pace médio nas corridas?* · *quantos treinos de cada tipo?*")
    q = st.text_input("Sua pergunta", key="ask_q")
    if st.button("Perguntar", type="primary") and q:
        try:
            with st.spinner("Consultando seus dados (LLM gera SQL → executa)..."):
                r = httpx.post(f"{API}/ask", json={"question": q}, timeout=200.0)
                r.raise_for_status()
                st.session_state["ask_result"] = r.json()
        except Exception as e:
            st.error(f"Falha ao consultar (API/Ollama no ar?): {e}")
    if "ask_result" in st.session_state:
        res = st.session_state["ask_result"]
        st.write(res["answer"])
        with st.expander("Ver SQL gerado"):
            st.code(res["sql"], language="sql")
