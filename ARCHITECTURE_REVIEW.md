# Revisão de Arquitetura — StriderEdge OS

> Gerado pela skill `architecture-review` (backend-skills). Escopo v1: saúde estrutural
> do código inteiro (não é review de diff), não correção/segurança/performance.

**Resumo:** 🟢 arquitetura saudável. **0 Crítico · 0 Alto · 1 Médio · 1 Baixo** —
✅ **ambos corrigidos nesta rodada.** Zero dependências circulares. Camadas respeitadas.
O padrão declarado (Python orquestra / Rust compute; contratos `Base*`; conexão única;
controllers finos) é **seguido**.

> **Status dos fixes** — Médio: criado `core/repository.py` (`TelemetryRepository`), a forma
> duplicada de leitura de série migrada em `processors.py` (3 sites) e `realtime.py` (1). Baixo:
> import tardio subiu pro topo de `api/main.py` + `Depends(get_strength_sets)`. 132 testes verdes.

---

## O que está certo (e por quê importa)

- **0 ciclos de dependência** (alta confiança, determinístico do grafo de imports). Nenhum
  risco de bug de ordem de inicialização nem acoplamento forçado por importação mútua.
- **Camadas respeitadas** — `api → analytics/services → core`, sem inversão:
  - `core/` não importa de `api`/`analytics`/`rag`/`ingestion` (a base não depende de cima).
  - `analytics/` não importa de `api` (lógica não depende do transporte HTTP).
  - `core/` não importa de `analytics`.
  - No front, `packages/core` (compartilhado web+mobile) **não** depende de `apps/web`.
- **Fan-in alto é saudável, não god-module**: `core/database.py` (29) e
  `core/framework/interfaces.py` (17) são os mais importados — mas são a *fundação
  deliberada* (conexão única §3 + contratos `Base*` §4), não um grab-bag. Não há
  `utils.py`/`helpers.py` load-bearing.
- **`analytics/coach.py` (fan-out 10) é um Composer coeso**, não acoplamento ruim: injeta
  LLM + analisadores + guarda + RAG + parser + store por composição (aberto/fechado —
  adicionar análise = mais um `BaseAnalyzer` na lista, sem tocar no `Coach`).

## Achados

### 🟡 Médio — Acesso a dados espalhado (sem camada de repositório)
**Arquivos:** ~18 módulos chamam `get_connection()` + SQL cru direto; **11 em `analytics/`**
(cada analisador roda seu próprio `SELECT`). Categoria: **acoplamento/coesão** ·
Confiança: **Média**.

Cada analisador está acoplado **diretamente ao schema DuckDB**. Não há DAO/repositório
entre a lógica e o banco. Consequência concreta: renomear uma coluna
(ex.: `dim_activities.total_distance_meters`) obriga a caçar o nome em muitos arquivos, em
vez de um só. Também estica o espírito de "`core` é dono do acesso a dado" — hoje `analytics`
também escreve SQL.

*Trade-off consciente:* isso é a filosofia "conclusão-pronta pro LLM" (cada analisador
calcula sua métrica) + "sem overengineering" (§2). **Funciona bem na escala atual** e não é
urgente. **Sugestão** (quando crescer): centralizar as queries por tabela num
`ActivityRepository`/`TelemetryRepository` em `core/` (ou views materializadas nomeadas), e
os analisadores consumirem métodos, não SQL. Mantém a conexão única; só move o SQL pra trás
de uma fronteira.

### 🔵 Baixo — Imports tardios dentro de handlers
**Arquivos:** `api/main.py` (ex.: `from analytics.strength import StrengthSets` dentro do
endpoint `activity_sets`; idem `FormService`). Categoria: **desvio de padrão** ·
Confiança: **Alta**.

Import dentro da função (em vez do topo) esconde a dependência do módulo e foge do estilo
dos outros controllers (que recebem serviços via `Depends`). Baixo impacto. **Sugestão:**
subir pro topo e injetar via `Depends(get_...)` como os demais, mantendo os controllers
uniformemente finos.

---

## Aderência ao padrão declarado (CLAUDE.md / constitution.md)

| Princípio | Estado |
|---|---|
| Python orquestra, Rust só compute pesado | ✅ Rust confinado a `stride_vision/` + `rust_kernel/` |
| Contratos `Base*` (polimorfismo) | ✅ `interfaces.py` é o 2º mais importado; implementações herdam |
| UMA conexão reutilizável por processo | ✅ `core/database.py` (cursor por thread sobre a raiz) |
| Controllers finos delegando a serviços | ✅ `api/main.py` delega a `ActivityService`/`Coach`/`FormService` (exceto os 2 imports tardios acima) |
| Degradação graciosa (NULL sem quebrar) | ✅ visível em telemetria/track/durabilidade |

## Cobertura do scan
- **139 arquivos** analisados, **4 pulados** (binários/gerados).
- Grafo de dependência construído para **Python** e **JS/TS**.
- **Rust** (`stride_vision/`) fora do grafo da ferramenta — lido à parte; é um crate isolado,
  sem acoplamento reverso com o Python (fronteira via subprocess/CLI).
