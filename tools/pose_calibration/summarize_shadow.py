"""Imprime o resumo agregado BlazePose→YOLO para decisão de migração.

Uso: .venv/bin/python tools/pose_calibration/summarize_shadow.py
"""

import json
import sys
from pathlib import Path

# O script pode ser chamado diretamente do checkout, sem instalar o pacote Python.
ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from analytics.pose_shadow_summary import PoseShadowSummaryService


if __name__ == "__main__":
    print(json.dumps(PoseShadowSummaryService().summary(), ensure_ascii=False, indent=2))
