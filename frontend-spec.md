# StriderEdge — Especificação do Frontend (Web)

> **Pós-pivot (jul/2026 — app 100% análise de forma por vídeo).** Esta spec descreve o produto REAL
> atual. A versão antiga (feed `.FIT`, mapas, ACWR, HYROX, Runna) descrevia o app removido no pivot —
> não existe mais. O produto agora é: **filmar a corrida → ver os pontos → receber o plano corretivo.**

## 0. Princípio
O produto é a **web** (React/Vite), cliente da **mesma API** (FastAPI). O cérebro (pose em Rust +
coach RAG) vive no backend; o front só consome. Backend off → UI degrada pro mock com selo honesto.

## 1. Stack (monorepo)
```
frontend/
  packages/core/   # TS: client.ts (fetch), tipos, hooks TanStack Query, adapters, stream.ts (SSE)  → web E mobile futuro
  apps/web/        # Vite + React 18 + TypeScript + Tailwind
  e2e/             # smoke Playwright — npm run test:e2e
```
`packages/core` é o contrato compartilhado; o app mobile futuro reusa sem reescrever backend.

## 2. Como rodar
```bash
ollama serve                          # coach/RAG (qwen2.5:7b-instruct + bge-m3)
.venv/bin/uvicorn api.main:app        # API :8000  (com os env do BlazePose OU STRIDE_MODEL do YOLO)
cd frontend && npm run dev            # web :5173 (proxy /api -> :8000)
```

## 3. Design system
- Tema claro/escuro via CSS custom properties. **Brand roxo `#6E56F7`**. Acentos: verde `#34D399`
  (ok), amarelo `#FBBF24` (atenção), vermelho `#F87171` (risco). Tipografia Inter, cantos
  `rounded-xl/2xl`, Recharts pros gráficos. Dado ausente = **"—"** (nunca "0").
- Sem mascote (decisão: infantilizava). Sóbrio e clínico — é app de lesão.

## 4. Telas (estado REAL)
Navegação: 2 abas autenticadas (`BottomNav`/`Sidebar`) — **Forma** e **Lesões** — + Landing e Login.

1. **Landing** (`pages/Landing`) — hero do produto. *(pública, estática)*
2. **Login** (`pages/Login`) — registrar/entrar (email+senha; Google opcional). Convidado permitido.
3. **Análise de Forma** (`pages/MovementAnalysis`) — ✅ **o coração do produto**:
   - Upload do vídeo lateral (opcional 2º clipe frontal → funde planos: queda pélvica + valgo).
   - Responde `processing` na hora; processa em background (fila) — o atleta fecha e volta.
   - Quando `done`: métricas (`FormAnalysis` — cadência, contato, oscilação, ângulos), overlay do
     esqueleto, e o **plano corretivo** (`CorrectivePlan`): veredito + ações prescritas + faixa de
     risco + perfil de lesão, **cada uma com fonte citável (PMC/DOI)**. `ShoeBlock` = orientação de
     tênis. Captura ruim → `reliable:false` → pede refilmagem, não opina.
4. **Minhas Lesões** (`pages/MyInjuries`) — ✅ log OSTRC append-only: `InjuryForm` (região no
   `BodyMap` + diagnóstico + severidade 0–3), `InjuryList` (histórico). Alimenta o dataset de risco.

## 5. Fiar na API (endpoint → tela) — todos ✅ verificados E2E
| Tela / dado | Endpoint |
|---|---|
| Registrar / entrar / sessão | `POST /api/v1/auth/register` · `/login` · `GET /auth/me` |
| Upload de vídeo | `POST /api/v1/form` (responde `processing`) |
| Status + métricas | `GET /api/v1/form/{id}` |
| Plano corretivo (coach) | `POST /api/v1/form/{id}/coach` (cache; RAG citável) |
| Veredito em streaming | `GET /api/v1/form/{id}/coach/stream` (SSE token a token) |
| Overlay do esqueleto | `GET /api/v1/form/{id}/video` |
| Orientação de tênis | `POST /api/v1/form/{id}/shoe` |
| Log de lesão | `POST /api/v1/injuries` · `GET /api/v1/injuries` |
| Perfil do atleta | `GET/POST /api/v1/profile` |

## 6. Qualidade
- `npm run typecheck` + `npm run build` a cada mudança.
- Smoke E2E de UI: `npm run test:e2e` (Playwright; exige API + Ollama no ar).

---
**Costura:** o web consome a API pronta; o mobile futuro reusa `packages/core`. Nada do backend se reescreve.
