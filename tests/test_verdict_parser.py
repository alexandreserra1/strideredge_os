"""Testes do VerdictParser — parse determinístico do veredito em 3 partes (sem LLM)."""

from analytics.coach import VerdictParser

# Formato real observado na saída do Qwen (###, **, bullets, Fonte no fim)
SAMPLE = """### 1. Pontos fortes — o que foi bem, com o dado que mostra.
A sua resistência aeróbia é alta, com uma deriva cardíaca de apenas 2,9%.

### 2. Pontos a melhorar — onde falhou e por que importa.
Sua cadência caiu 5,2% na segunda metade, passando de 171 para 162 passos/minuto.
Isso pode indicar fadiga muscular.

### 3. O que fazer — ações concretas, cada uma explicada.
- **Aumente a recuperação entre treinos**: evite overtraining.
- **Foque em manter a cadência**: tiros curtos de passada rápida (PMC12440572).

**Fonte**: Revisão sistemática de cadência e prevenção de lesão (PMC12440572)."""

parser = VerdictParser()


def test_parse_divide_as_tres_secoes():
    r = parser.parse(SAMPLE)
    assert len(r["strengths"]) == 1 and "2,9%" in r["strengths"][0]
    # linha de continuação junta no mesmo item (não vira item novo)
    assert len(r["improvements"]) == 1 and "fadiga muscular" in r["improvements"][0]
    assert len(r["actions"]) == 2 and r["actions"][0].startswith("Aumente")
    assert "**" not in r["actions"][0]                    # markdown limpo


def test_parse_extrai_citacoes_unicas_em_ordem():
    r = parser.parse(SAMPLE)
    assert r["citations"] == ["PMC12440572"]              # única, mesmo aparecendo 2x


def test_parse_linha_fonte_nao_vira_acao():
    r = parser.parse(SAMPLE)
    assert not any("Revisão sistemática" in a for a in r["actions"])


def test_sem_secoes_degrada_gracioso():
    r = parser.parse("VEREDITO_FAKE")
    assert r["verdict"] == "VEREDITO_FAKE"
    assert r["strengths"] == [] and r["improvements"] == [] and r["actions"] == []


def test_variacao_sem_markdown():
    texto = "1. Pontos fortes\nBoa durabilidade.\n2. Pontos a melhorar\nCadencia baixa.\n3. O que fazer\nTiros curtos."
    r = parser.parse(texto)
    assert r["strengths"] == ["Boa durabilidade."]
    assert r["improvements"] == ["Cadencia baixa."]
    assert r["actions"] == ["Tiros curtos."]
