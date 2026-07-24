"""core/config.py — configuracao por AMBIENTE (padrao 12-factor).

Um lugar so pros flags de COMPORTAMENTO do backend.
"""

import os

ENV = os.environ.get("STRIDE_ENV", "development").strip().lower()
IS_PROD = ENV in ("production", "prod")

# A seleção do motor de pose é uma decisão de implantação, nunca um parâmetro HTTP.  Manter a
# allowlist aqui evita que qualquer valor inesperado vire argumento/env de um subprocesso.
_POSE_BACKENDS = frozenset(("yolo17", "halpe26", "blazepose33"))
_DEFAULT_POSE_BACKEND = "blazepose33"


class ConfigurationError(ValueError):
    """Configuração do servidor inválida; não é erro causado pelo cliente."""


def validate_pose_backend(value: str) -> str:
    """Normaliza e valida um backend vindo exclusivamente da configuração de implantação."""
    backend = value.strip().lower()
    if backend not in _POSE_BACKENDS:
        allowed = ", ".join(sorted(_POSE_BACKENDS))
        raise ConfigurationError(
            f"STRIDE_POSE_BACKEND inválido; use um de: {allowed}.")
    return backend


def pose_backend(environ=None) -> str:
    """Backend principal decidido pela implantação; BlazePose é o padrão de produto.

    O servidor falha de forma explícita na criação da análise se o manifesto/assets do BlazePose
    não estiverem disponíveis. Não há fallback silencioso para YOLO: a proveniência da métrica é
    parte do contrato de saúde. `environ` existe apenas para testes; o valor nunca vem do request.
    """
    source = os.environ if environ is None else environ
    return validate_pose_backend(source.get("STRIDE_POSE_BACKEND", _DEFAULT_POSE_BACKEND))


def pose_shadow_backend(environ=None):
    """Backend de comparação opcional, decidido somente pela implantação.

    Ausente (ou vazio) significa que não há trabalho extra. A compatibilidade da combinação
    principal→shadow é validada pelo serviço, onde os dois valores estão disponíveis.
    """
    source = os.environ if environ is None else environ
    value = source.get("STRIDE_POSE_SHADOW_BACKEND")
    return None if value is None or not value.strip() else validate_pose_backend(value)


def summary() -> dict:
    """Config efetiva — logada no boot da API (boa pratica: o app declara como esta rodando)."""
    try:
        shadow = pose_shadow_backend()
    except ConfigurationError:
        # Shadow é telemetria experimental: configuração ruim não deve derrubar o baseline no boot.
        shadow = "invalid"
    return {
        "env": ENV,
        "is_prod": IS_PROD,
        "pose_backend": pose_backend(),
        "pose_shadow_backend": shadow,
    }
