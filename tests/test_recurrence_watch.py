"""Prevenção de recaída: quando a forma ATUAL ainda mostra um fator ligado a uma lesão que o
atleta JÁ TEVE, o coach alerta (loop pra frente, contraparte do retrospecto). Hermético."""

from analytics.form_coach import FormCoach


class _FakeLLM:
    def chat(self, system, prompt):
        return "- Fortaleça o quadril (Fonte: PMC1)"


def _coach():
    return FormCoach(llm=_FakeLLM(), knowledge=None)


def test_alerta_recaida_quando_fator_da_lesao_previa_ainda_aparece():
    m = {"pelvic_drop_deg": 15.0, "cadence_spm": 175.0, "reliable": True}   # queda pélvica alta
    hist = {"factors": ["pelvic_drop_deg"], "diagnoses": ["pfp"], "regions": ["joelho_frente"]}
    watch = _coach().plan(m, history=hist)["recurrence_watch"]
    assert len(watch) == 1
    assert watch[0]["diagnosis"] == "pfp" and watch[0]["source"] == "PMC6829001"
    assert "queda pélvica contralateral" in watch[0]["factors"]


def test_sem_historico_nao_alerta():
    m = {"pelvic_drop_deg": 15.0, "reliable": True}
    assert _coach().plan(m, history=None)["recurrence_watch"] == []


def test_lesao_previa_mas_fator_ideal_nao_alerta():
    # teve PFP, mas a forma atual NÃO mostra os fatores ligados a ela -> sem alerta (honesto)
    m = {"pelvic_drop_deg": 5.0, "knee_valgus_deg": 4.0, "cadence_spm": 175.0, "reliable": True}
    hist = {"diagnoses": ["pfp"], "factors": ["pelvic_drop_deg"], "regions": []}
    assert _coach().plan(m, history=hist)["recurrence_watch"] == []


def test_metodo_direto_ignora_diagnostico_sem_mapa():
    devs = [{"metric": "pelvic_drop_deg", "label": "queda pélvica"}]
    hist = {"diagnoses": ["diagnostico_inexistente"], "factors": [], "regions": []}
    assert FormCoach._recurrence_watch(devs, hist) == []
