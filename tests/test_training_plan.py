"""EPIC C — gerador de plano corretivo faseado (determinístico + citado). Hermético."""

from analytics.injury_risk import assess
from analytics.training_plan import build_plan, _block_start

_M = {"cadence_spm": 152.0, "pelvic_drop_deg": 16.0, "knee_valgus_deg": 14.0}


def test_plano_sequencia_fases_em_ordem():
    """As FASES vêm na ordem corretiva (base/ativação → força → drill de marcha), cada uma com
    janela de semanas, porquê e exercícios (sem repetir semana a semana)."""
    plan = build_plan(assess(_M)["factors"], weeks=6)
    keys = [ph["key"] for ph in plan["phases"]]
    ordem = ["base", "forca", "drill_de_marcha"]
    assert keys == [k for k in ordem if k in keys]   # subsequência na ordem corretiva
    for ph in plan["phases"]:
        assert ph["title"] and ph["weeks_label"] and ph["why"] and ph["exercises"]


def test_prioriza_o_maior_fator_de_risco():
    plan = build_plan(assess(_M)["factors"], weeks=6)
    # o foco é o fator de maior contribuição (assess ordena) — cadência aqui
    assert plan["priority"][0]["metric"] == assess(_M)["factors"][0]["metric"]


def test_todo_exercicio_tem_fonte_como_e_progressao():
    plan = build_plan(assess(_M)["factors"], weeks=6)
    for ph in plan["phases"]:
        for ex in ph["exercises"]:
            # citado, nomeado, com COMO fazer e PROGRESSÃO (o que muda ao longo das semanas)
            assert ex["source"] and ex["exercise"] and ex["how"] and ex["progression"]


def test_respeita_o_prazo_e_sanitiza():
    assert build_plan(assess(_M)["factors"], weeks=4)["duration_weeks"] == 4
    assert build_plan(assess(_M)["factors"], weeks=99)["duration_weeks"] == 16   # teto
    assert build_plan(assess(_M)["factors"], weeks=0)["duration_weeks"] == 6     # default


def test_sem_desvio_devolve_plano_vazio_com_caveat():
    limpa = build_plan([], weeks=6)
    assert limpa["phases"] == [] and "mantenha" in limpa["caveat"].lower()


def test_block_start_progride_com_a_duracao():
    s = _block_start(9, [0, 1, 2])                    # 3 blocos presentes
    assert s[0] == 1 and s[0] < s[1] < s[2]           # base < força < drill


def test_block_start_antecipa_quando_bloco_falta():
    # só drill (bloco 2) presente -> começa na 1ª semana, sem esperar base/força vazias
    assert _block_start(6, [2, 2]) == {2: 1}


def test_plan_from_metrics_nao_gera_sobre_captura_ruim():
    from analytics.training_plan import plan_from_metrics
    ruim = plan_from_metrics({"cadence_spm": 152.0, "reliable": False,
                              "quality_note": "refilme"}, weeks=6)
    assert ruim.get("unreliable") and ruim["phases"] == []


def test_plan_from_metrics_gera_com_dado_bom():
    from analytics.training_plan import plan_from_metrics
    ok = plan_from_metrics({"cadence_spm": 152.0, "pelvic_drop_deg": 16.0,
                            "knee_valgus_deg": 14.0, "reliable": True}, weeks=6)
    assert ok["duration_weeks"] == 6 and ok["phases"] and ok["intro"]


def test_plan_service_persiste_e_lista():
    import uuid
    from api.plans import PlanService
    from analytics.training_plan import plan_from_metrics
    from core.database import get_connection
    svc = PlanService()
    uid = str(uuid.uuid4())
    try:
        plan = plan_from_metrics({"cadence_spm": 152.0, "pelvic_drop_deg": 16.0,
                                  "reliable": True}, weeks=6)
        out = svc.create(uid, None, plan)
        assert out["weeks"] == 6 and out["plan"]["duration_weeks"] == 6
        lst = svc.list(uid)
        assert len(lst) == 1 and lst[0]["id"] == out["id"]
        assert svc.list(str(uuid.uuid4())) == []   # outro atleta não vê
    finally:
        get_connection().execute("DELETE FROM training_plans WHERE user_id = ?", [uid])
