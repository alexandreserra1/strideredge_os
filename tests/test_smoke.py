"""Smoke tests — a API sobe e as superfícies-chave respondem. Fumaça: barato, pega o que
'quebrou tudo' (import ruim, rota sumida, guarda de auth aberta) antes dos testes finos."""

from fastapi.testclient import TestClient

from api.main import app

client = TestClient(app)


def test_app_sobe_e_tem_as_rotas_essenciais():
    paths = {r.path for r in app.routes}
    for p in ["/api/v1/form", "/api/v1/injuries", "/api/v1/injuries/taxonomy",
              "/api/v1/injuries/{injury_id}/classify", "/api/v1/auth/login"]:
        assert p in paths, f"rota sumiu: {p}"


def test_taxonomia_publica_responde_e_tem_forma():
    r = client.get("/api/v1/injuries/taxonomy")
    assert r.status_code == 200
    body = r.json()
    assert body["regions"] and body["sides"] and body["diagnoses"]
    assert {"id", "label", "region", "is_mapped"} <= set(body["diagnoses"][0])


def test_endpoints_protegidos_exigem_sessao():
    # sem token → 401 (a guarda de auth não pode estar aberta)
    assert client.get("/api/v1/injuries").status_code == 401
    assert client.get("/api/v1/profile").status_code == 401


def test_rota_inexistente_da_404():
    assert client.get("/api/v1/nao-existe").status_code == 404
