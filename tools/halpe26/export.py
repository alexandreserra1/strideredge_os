#!/usr/bin/env python3
"""Gera um comando reproduzível de exportação MMDeploy, sem baixar pesos nem instalar pacotes.

MMDeploy é ferramenta de build: o artefato final continua sendo ONNX consumido pelo Rust. Os paths
do config e checkpoint são obrigatórios para não fixarmos uma versão de conversor não verificada.
"""

import argparse
import json
import shlex
import sys
from pathlib import Path
from typing import Dict, List


def export_command(mmdeploy_root: Path, deploy_config: Path, model_config: Path,
                   checkpoint: Path, output_dir: Path, device: str) -> List[str]:
    return [
        sys.executable, str(mmdeploy_root / "tools" / "deploy.py"), str(deploy_config),
        str(model_config), str(checkpoint), "--work-dir", str(output_dir), "--device", device,
        "--dump-info",
    ]


def manifest(path: Path) -> Dict:
    return json.loads(path.read_text())


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--mmdeploy-root", type=Path, required=True)
    parser.add_argument("--deploy-config", type=Path, required=True)
    parser.add_argument("--model-config", type=Path, required=True)
    parser.add_argument("--checkpoint", type=Path, required=True)
    parser.add_argument("--output-dir", type=Path, required=True)
    parser.add_argument("--device", default="cpu", help="cpu no M1 primeiro; cuda apenas para benchmark opcional")
    args = parser.parse_args()
    command = export_command(args.mmdeploy_root, args.deploy_config, args.model_config,
                             args.checkpoint, args.output_dir, args.device)
    print("# Revise licenças, checksum e ordem dos 26 pontos antes de executar:")
    print(shlex.join(command))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
