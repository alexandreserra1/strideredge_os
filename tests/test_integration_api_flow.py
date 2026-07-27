"""Integração da API (TestClient, hermético) — trava o CONTRATO frontend↔API ponta a ponta.

Sem servidor real, sem Ollama/Rust/ffmpeg: motor de visão FAKE (padrão de tests/test_form.py),
coach com LLM+RAG FAKE, classificador FAKE. Exercita o percurso que a SPA faz de verdade:

    registrar → login → perfil (PUT/GET roundtrip)
              → lesão (POST OSTRC → severity → list → classify)
              → análise de forma (upload fake → get → coach → plan)

O objetivo é pegar QUEBRA DE CONTRATO (método/rota/forma de resposta), a classe de bug que já
mordeu antes: /plan aninhado em {plan:{...}}, uncertain_metrics como lista de objetos (não string),
/profile é PUT (não POST). Cada assert abaixo é uma dessas formas que o frontend consome.
"""

import time

from fastapi.testclient import TestClient

from api.form import FormService
from api.main import app
from api.deps import (get_diagnosis_classifier, get_form_coach, get_form_service)
from analytics.form_coach import FormCoach
from core.database import get_connection
from core.jobs import JobQueue

client = TestClient(app)


# --- motor de visão FAKE (sem Rust/ffmpeg): cadência baixa ⇒ há desvio ⇒ coach gera plano ---
_FAKE_METRICS = {"frames": 100, "fps": 30.0, "detection_rate_pct": 98.0,
                 "cadence_spm": 150.0, "asymmetry_pct": 4.0, "vertical_oscillation_pct": 6.0,
                 "ground_contact_ms": 210.0, "reliable": True, "quality_note": None}


class _InlineQueue(JobQueue):
    """Fila síncrona: roda o job na hora (sem thread) — determinístico."""

    def start(self):
        pass

    def enqueue(self, fn, *args, **kwargs):
        fn(*args, **kwargs)


class _FakeFormService(FormService):
    def __init__(self):
        super().__init__(queue=_InlineQueue(), backend="yolo17")

    def _run_engine(self, original, overlay, view, snapshot, draw_overlay=True):
        return dict(_FAKE_METRICS)


# --- coach FAKE (LLM + RAG determinísticos) ---
class _FakeLLM:
    def chat(self, system_prompt, user_prompt):
        return "- Aumente a cadencia com metronomo numa corrida leve (Fonte: PMC12440572)"


class _FakeKB:
    def retrieve(self, query, k=3, domains=None):
        return [{"text": "cadencia maior reduz impacto", "origin": "curado", "source": "PMC12440572"}]


# --- classificador FAKE (texto livre → diagnóstico, confiança alta) ---
class _FakeClassifier:
    def classify(self, symptom_text, region):
        return {"diagnosis": "pfp", "confidence": "alta"}


def _wait_done(aid, headers, tries=50):
    for _ in range(tries):
        r = client.get(f"/api/v1/form/{aid}", headers=headers).json()
        if r["status"] != "processing":
            return r
        time.sleep(0.05)
    raise AssertionError("não processou a tempo")


def test_fluxo_completo_frontend_contrato():
    app.dependency_overrides[get_form_service] = _FakeFormService
    app.dependency_overrides[get_form_coach] = lambda: FormCoach(llm=_FakeLLM(), knowledge=_FakeKB())
    app.dependency_overrides[get_diagnosis_classifier] = _FakeClassifier
    email = "flow@integ.test"
    uid = None
    try:
        # 1) registrar
        r = client.post("/api/v1/auth/register",
                        json={"name": "Fluxo", "email": email, "password": "corrida123"})
        assert r.status_code == 201
        token = r.json()["token"]
        assert r.json()["user"]["email"] == email
        uid = r.json()["user"]["user_id"]
        auth = {"Authorization": f"Bearer {token}"}

        # 2) login devolve o mesmo contrato {token, user}
        r = client.post("/api/v1/auth/login", json={"email": email, "password": "corrida123"})
        assert r.status_code == 200 and r.json()["token"]

        # 3) perfil é PUT (não POST) e faz roundtrip com o GET
        r = client.put("/api/v1/profile", headers=auth,
                       json={"height_cm": 180.0, "weekly_volume_km": 40.0})
        assert r.status_code == 200
        assert client.post("/api/v1/profile", headers=auth, json={}).status_code == 405  # não é POST
        got = client.get("/api/v1/profile", headers=auth)
        assert got.status_code == 200 and got.json()["height_cm"] == 180.0

        # 4) lesão: POST aceita q_participation..q_pain (0–3), computa severity, lista, classifica
        r = client.post("/api/v1/injuries", headers=auth,
                        json={"region": "joelho_frente", "symptom_text": "dor na frente do joelho",
                              "q_participation": 2, "q_pain": 3})
        assert r.status_code == 201
        injury = r.json()
        assert injury["region"] == "joelho_frente" and injury["diagnosis"] is None
        assert 0 < injury["severity"] <= 100                         # OSTRC 0–100
        iid = injury["id"]

        lst = client.get("/api/v1/injuries", headers=auth)
        assert lst.status_code == 200 and any(i["id"] == iid for i in lst.json())

        # classify: texto livre → diagnóstico via classifier fake, persistido
        r = client.post(f"/api/v1/injuries/{iid}/classify", headers=auth)
        assert r.status_code == 200 and r.json()["diagnosis"] == "pfp"

        # 5) análise de forma: upload fake → processa inline → get
        r = client.post("/api/v1/form", headers=auth,
                        files={"video": ("run.mp4", b"fake-bytes", "video/mp4")})
        assert r.status_code == 201
        aid = r.json()["analysis_id"]
        done = _wait_done(aid, auth)
        assert done["status"] == "done" and done["metrics"]["cadence_spm"] == 150.0

        # 6) coach: forma de resposta que o frontend consome
        r = client.post(f"/api/v1/form/{aid}/coach", headers=auth)
        assert r.status_code == 200
        coach = r.json()
        assert coach["analysis_id"] == aid
        assert isinstance(coach["verdict"], str) and coach["verdict"]
        assert isinstance(coach["deviations"], list) and coach["actions"]
        # uncertain_metrics = LISTA de objetos {metric,label,reason} (não string, não dict)
        assert isinstance(coach["uncertain_metrics"], list)
        for u in coach["uncertain_metrics"]:
            assert set(u) >= {"metric", "label", "reason"}
        assert coach["risk"]["risk_band"] in ("baixo", "moderado", "elevado", "alto")

        # 7) plano: SEMPRE aninhado em {analysis_id, plan:{...}}
        r = client.post(f"/api/v1/form/{aid}/plan", headers=auth)
        assert r.status_code == 200
        body = r.json()
        assert body["analysis_id"] == aid and "plan" in body
        plan = body["plan"]
        assert plan["duration_weeks"] >= 2 and isinstance(plan["weeks"], list)

        # o plano gerado por logado persiste e aparece na lista
        plans = client.get("/api/v1/plans", headers=auth)
        assert plans.status_code == 200 and any(p["analysis_id"] == aid for p in plans.json())
    finally:
        app.dependency_overrides.clear()
        con = get_connection()
        con.execute("DELETE FROM form_analyses")
        con.execute("DELETE FROM training_plans")
        if uid:
            con.execute("DELETE FROM injury_reports WHERE user_id = ?", [uid])
            con.execute("DELETE FROM athlete_profile WHERE user_id = ?", [uid])
        con.execute("DELETE FROM auth_users WHERE email = ?", [email])
