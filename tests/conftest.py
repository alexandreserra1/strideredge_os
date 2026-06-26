"""Configuração compartilhada dos testes — coloca a raiz do projeto no sys.path."""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
