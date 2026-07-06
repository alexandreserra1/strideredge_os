# StriderEdge — Especificação do Frontend (Web + identidade)

> Spec do produto visual: o **web de verdade** (substitui o Streamlit, que é só protótipo interno)
> e como as telas fiam na API. Base compartilhada com o app mobile (Fase C — ver
> [`app-spec.md`](app-spec.md)). Faz par com `plan.md §10` (roadmap).

## 0. Princípio
- **Streamlit = ferramenta interna de dev/protótipo, NUNCA o produto.**
- O produto é a **web** (agora) + o **app** (depois), ambos **clientes da MESMA API** (FastAPI).
  O cérebro (análises/coach/tempo real) não se reescreve — o front só consome.

## 1. Stack (ATUAL — monorepo já construído)
```
frontend/
  packages/core/   # TS: cliente da API, tipos, TanStack Query hooks, ADAPTERS  → web E mobile
  apps/web/        # Vite + React 18 + TypeScript + Tailwind
  e2e/             # smoke de UI (Playwright) — npm run test:e2e
```
- `packages/core` é o contrato compartilhado: `client.ts` (fetch), `queries.ts` (hooks),
  `adapters.ts` (shapes do backend → shapes da UI), `stream.ts` (SSE do coach).
- O protótipo zero-build antigo (`web/` com CDN) é legado — não evoluir.
- Mapa: **Leaflet + react-leaflet** (CARTO dark/light + Esri satélite), rota fina colorida
  por cadência (estilo Strava/Runna).

## 2. Como rodar
```bash
ollama serve                          # coach/RAG
.venv/bin/uvicorn api.main:app        # API :8000
cd frontend && npm run dev            # web :5173 (proxy /api -> :8000)
```
Backend off → a UI degrada pro **mock** (nunca quebra); telas mock levam selo honesto
("exemplo"/"demo").

## 3. Design system (paleta 2025 — revisada)
- Tema **claro e escuro** via CSS custom properties (`--surface-*`, `--text-*`, `--border-*`).
- **Brand roxo `#6E56F7`** (`--brand`, tinta `--brand-ink`) — substituiu o verde-limão `#C6F24E`
  (decisão: lime sobre preto cansava e datava o visual).
- Acentos: verde `#34D399` (ok), amarelo `#FBBF24` (atenção), vermelho `#F87171` (risco),
  laranja `#FF8A4C`, azul `#38BDF8`. Semáforo de cadência no mapa usa os três primeiros.
- Tipografia Inter, cantos `rounded-xl/2xl`, cards (`card`, `card-hover`, `kpi-card`, `glass`),
  microanimações discretas (fade/slide/pop). Gráficos: **Recharts** com tooltips no tema.
- Dado ausente mostra **"—"** (nunca "0 bpm").

## 4. Telas (estado real)
1. **Landing** — hero "coach de IA que corre ao seu lado". *(estática)*
2. **Dashboard** — ✅ REAL: ACWR (semáforo), Fitness/tendência, Previsão 10/21K (Riegel),
   volume semanal calculado das sessões, feed com deep-link. "Hoje · Prescrito" = exemplo
   até o gerador de plano nascer.
3. **Plano / Calendário** — mock com selo "exemplo" (depende do gerador adaptativo, `plan.md §0.3`).
4. **Detalhe do treino** — ✅ REAL: FC/zonas (faixas de bpm do atleta), cadência, mapa com
   semáforo, durabilidade, **Veredito do Coach em STREAMING** (SSE token a token, com correção
   da guarda ao vivo) + cache (reabrir = instantâneo, "Regerar" força).
5. **Análise & Saúde** — ✅ REAL: painel de risco (ACWR/cadência/durabilidade/ramp com fontes),
   review da IA, calendário interativo (strip 2 semanas + mês navegável, dias clicáveis).
6. **Modo Corrida** — demo (tempo real de verdade = app, Fase C).
7. **HYROX** — em breve.

## 5. Fiar na API (mapa endpoint → tela)
| Tela / dado | Endpoint | Estado |
|---|---|---|
| Feed de atividades | `GET /api/v1/activities` | ✅ |
| Detalhe + zonas + durabilidade | `GET /api/v1/activities/{id}` | ✅ |
| Mapa (trilha + semáforo) | `GET .../track` · `.../telemetry` | ✅ |
| Veredito (cache/idempotente) | `POST .../coach` (`?force=true` regenera) | ✅ |
| Veredito em streaming | `GET .../coach/stream` (SSE) | ✅ |
| Prontidão (ACWR) | `GET /api/v1/training-load` | ✅ |
| Previsão de prova + fitness | `GET /api/v1/fitness` | ✅ |
| Pergunte (text-to-SQL) | `POST /api/v1/ask` | endpoint pronto, tela futura |
| Plano/Calendário prescrito | *(gerador de plano — backend ainda não existe)* | mock |

## 6. Identidade (decisão revisada)
O mascote **StrideFox foi REMOVIDO da UI** (decisão do dono: infantilizava o produto).
No lugar: **pílula de prontidão** no topbar (cor + valor do ACWR) — informativa e sóbria.
Gamificação/mascote ficam como ideia **opcional de futuro** (se voltar, entra como camada
sobre estado que a API já entrega — nunca bloqueia nada).

## 7. Dados espaciais / mapas (nota de backend)
**Não precisamos de geohash agora.** Desenhar a trilha de UMA corrida = ler `lat/lon ORDER BY
timestamp` e traçar — zero query espacial. Geohash/espacial só quando houver **segmentos estilo
Strava, "perto de mim", heatmap ou proximidade multiusuário** (futuro). Aí: extensão `spatial`
do DuckDB (ou PostGIS ao hospedar). Guardar `lat/lon` como `DOUBLE` (já fazemos) mantém a porta
aberta.

## 8. Qualidade
- `npm run typecheck` + `npm run build` a cada mudança.
- **Smoke E2E de UI**: `npm run test:e2e` (Playwright; exige API + Ollama no ar) — shell,
  mapa com rota real, coach streaming real, calendário interativo.

---
**Costura:** o web consome a API pronta; o mobile (Fase C) reusa o `packages/core` (client,
hooks, adapters e o SSE já são plataforma-agnósticos). Nada do backend se reescreve.
