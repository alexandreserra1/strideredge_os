"""Testes da GroundingGuard (aterramento) — herméticos, com LLM fake."""

from analytics.grounding import GroundingGuard

guard = GroundingGuard()


def test_issues_detecta_numero_inventado_e_causa():
    iss = guard.issues("treino a 170 spm, pode ser desidratacao", "dados: 163 spm")
    assert iss["invented_numbers"] == ["170"]      # 170 nao esta nos dados
    assert "desidrat" in iss["banned_causes"]


def test_issues_limpo_quando_aterrado():
    iss = guard.issues("cadencia 163 spm, sinal de fadiga", "dados: 163 spm")
    assert iss == {"invented_numbers": [], "banned_causes": []}


def test_numbers_virgula_decimal():
    assert "2.9" in GroundingGuard.numbers("desacoplamento 2,9%")  # virgula -> ponto


class _SeqLLM:
    """LLM fake que devolve respostas em sequencia (simula rascunho ruim -> bom)."""
    def __init__(self, replies):
        self.replies, self.calls = list(replies), 0

    def chat(self, system, user):
        r = self.replies[min(self.calls, len(self.replies) - 1)]
        self.calls += 1
        return r


def test_enforce_regenera_ate_aterrar():
    llm = _SeqLLM(["recomendo 999 spm", "use cadencia 163, que esta nos dados"])
    out = guard.enforce(llm, "sys", "dados: 163 spm", max_retries=2)
    assert "163" in out and "999" not in out      # ficou com a versao aterrada
    assert llm.calls == 2                          # 1 ruim + 1 boa


def test_enforce_devolve_melhor_se_nunca_limpa():
    llm = _SeqLLM(["sempre invento 999 spm"])      # nunca corrige
    out = guard.enforce(llm, "sys", "dados: 163 spm", max_retries=1)
    assert out and llm.calls == 2                  # bounded: 1 + 1 retry, devolve a melhor
