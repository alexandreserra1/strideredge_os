#!/usr/bin/env bash
# preflight.sh — replica o CI ANTES do push, pra nunca mais quebrar por dep não-declarada ou
# drift de ambiente (o bug clássico "passa na minha máquina").
#
# A chave: um venv DEDICADO que contém SÓ o que o pyproject declara (nunca instalamos nada à mão
# nele). Se o código passar a importar algo não declarado, este venv falha — igual ao CI. É reusado
# entre pushes e só reinstala quando o pyproject muda (rápido no caso comum).
#
# Uso: scripts/preflight.sh   (o hook pre-push chama sozinho; rode à mão quando quiser)
# Pular em emergência: git push --no-verify
set -euo pipefail
cd "$(dirname "$0")/.."
export PATH="/opt/homebrew/bin:/usr/local/bin:$PATH"

VENV=".preflight-venv"
STAMP="$VENV/.pyproject.sha"
PY="${PYTHON:-python3}"

need_install=0
if [ ! -x "$VENV/bin/python" ]; then
  need_install=1
else
  cur="$(shasum pyproject.toml | awk '{print $1}')"
  [ -f "$STAMP" ] && [ "$(cat "$STAMP")" = "$cur" ] || need_install=1
fi

if [ "$need_install" = "1" ]; then
  echo "preflight: (re)criando venv limpo espelhando o pyproject…"
  rm -rf "$VENV"
  "$PY" -m venv "$VENV"
  "$VENV/bin/pip" install -q --upgrade pip
  "$VENV/bin/pip" install -q ".[dev]"        # SÓ o declarado — pega dep faltando igual o CI
  shasum pyproject.toml | awk '{print $1}' > "$STAMP"
fi

echo "preflight: Python (suíte hermética, venv limpo)…"
"$VENV/bin/python" -m pytest -q -k "not e2e"

if command -v cargo >/dev/null 2>&1 && [ -f stride_vision/Cargo.toml ]; then
  echo "preflight: Rust (cargo test)…"
  cargo test --release --manifest-path stride_vision/Cargo.toml -q
fi

echo "preflight: ✅ tudo verde — pode empurrar."
