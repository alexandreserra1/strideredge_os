# STATUS — StriderEdge OS

> Uma página, honesta: o que está **pronto**, o que **falta**, e o que é **futuro**. Atualizar quando
> algo mudar de coluna. Fonte da verdade pro "o que falta" — antes de abrir tarefa, olhar aqui.
> Última atualização: **26 jul. 2026.**

## O produto em uma frase
Atleta filma a corrida → motor de pose em Rust extrai a biomecânica → coach LLM local (RAG citável)
devolve um plano corretivo prescritivo com fontes científicas. 100% no aparelho/servidor próprio.

## ✅ PRONTO (verificado ponta-a-ponta)
O fluxo real roda: **registrar → login → upload de vídeo → processa em background → métricas +
plano corretivo citado**. Rodado E2E via API real (26/jul), coach respondeu em ~24s com 3 ações
prescritas + 6 fontes PMC + faixa de risco + perfil de lesão.

- **Motor de pose (Rust `stride_vision`)** — **2 motores:** BlazePose GHUM (Apache, default de
  produto, pés+3D) + YOLO11 (régua da avaliação pareada). RTMPose/Halpe26 foi **removido** (pesos
  com licença pendente + superado pelo pé do BlazePose). Modular, com quality gate de timing.
- **Pipeline de vídeo** — transcode + pose + métricas em background pela fila; upload responde na hora.
- **Métricas** — cadência (FFT), contato/voo, oscilação vertical, ângulos de joelho/quadril/tronco,
  pisada; plano frontal (queda pélvica, valgo) quando há 2º clipe. Degrada gracioso (`reliable:false`).
- **Coach RAG** — busca híbrida densa+BM25, contextual retrieval, roteamento multi-domínio, grounding
  anti-alucinação, fontes citáveis (PMC/DOI). Eval estilo RAGAS. Streaming SSE.
- **Risco de lesão** — score v1 aterrado na literatura (faixa relativa, nunca "X%") + perfil por
  diagnóstico (fratura de estresse, fascite, canelite, Aquiles, patelofemoral, banda IT).
- **Taxonomia + log de lesão** — vocabulário controlado + log OSTRC append-only (backend + frontend).
- **Frontend web** — 2 telas (Análise de Forma, Minhas Lesões) + Landing + Login; consome a API.
- **Auth** — registrar/login/sessão + convidado anônimo por capability.
- **Infra de asset** — manifesto SHA-pinado + NOTICE Apache; runtime BlazePose empacotado (sem pip).
- **CI** — testes Python (250+) + Rust (45+); job de degradação (vídeo ruim / sem pessoa).

## 🟡 FALTA (curto, priorizado)
1. **Polir a UX no navegador** — o backend entrega tudo; falta passar as 2 telas no browser e ajustar.
   *(o valor pro usuário/portfólio está aqui, não em mais backend.)*
2. **BlazePose virar default (opcional — upgrade de licença AGPL→Apache).** Único bloqueio de
   conteúdo: **avaliação pareada estável** — com n=12 do Riglet, 3D>YOLO NÃO é significativo (IC
   cruza 0). Precisa de mais corredores. Enquanto isso, **YOLO segue default e o produto funciona.**
3. **Provisionar o runtime BlazePose no Linux** — passo mecânico (rodar `tools/blazepose/provision.py`
   contra o wheel manylinux numa máquina Linux). Mecanismo já provado.
4. **Anotar os 2 vídeos próprios** (`~/Desktop/anotacao_propria/`) — âncora manual de sanity na
   moldura real; opcional, complementa o Riglet.

## 🔵 FUTURO (não agora — não abrir sem decisão)
- **Modelo de risco TREINADO** (Random Forest) — pipeline pronto (`analytics/injury_model.py`),
  bloqueado por **outcomes de lesão rotulados** (o log OSTRC vai acumulando esse `y`).
- **Pronação/eversão reais** — o BlazePose já dá calcanhar+ponta (pisada/contato), mas não hálux/
  dedinho; pronação clínica exigiria captura/validação própria. Não é prioridade.
- **App mobile** (reusa `packages/core`) e **wearable** (peitoral IMU) — norte de longo prazo.

## Onde está o quê
`constitution.md` (princípios) · `plan.md` (arquitetura) · `AI-STRATEGY.md` (roteiro IA, quase tudo
FEITO) · `frontend-spec.md` (telas) · `docs/adr/` (decisões) · `tools/pose_calibration/` (validação).
