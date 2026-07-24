"""OllamaClient — teto de tokens no payload + streaming (A3). Hermético: sem rede/Ollama."""

from analytics.llm import OllamaClient, _content_from_line


def test_payload_inclui_teto_de_tokens_so_quando_positivo():
    sem = OllamaClient()._payload("s", "u")                       # num_predict=-1 (default)
    assert "num_predict" not in sem["options"] and sem["stream"] is False
    com = OllamaClient(num_predict=400)._payload("s", "u")        # teto explícito
    assert com["options"]["num_predict"] == 400


def test_payload_marca_stream_quando_pedido():
    assert OllamaClient()._payload("s", "u", stream=True)["stream"] is True


def test_parser_de_stream_extrai_texto_e_fim():
    assert _content_from_line('{"message":{"content":"Aum"},"done":false}') == ("Aum", False)
    assert _content_from_line('{"message":{"content":"ente"},"done":true}') == ("ente", True)


def test_parser_ignora_linha_vazia_ou_invalida():
    assert _content_from_line("") == (None, False)
    assert _content_from_line("   ") == (None, False)
    assert _content_from_line("nao-json") == (None, False)
    assert _content_from_line('{"done":true}') == (None, True)    # fim sem conteúdo
