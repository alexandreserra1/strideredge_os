# Quality Gates — StriderEdge OS

Padrões de código, organização e design do projeto. Não é sugestão — é a régua.
Leia antes de escrever código. Atualize quando uma nova regra "endurecer".

## Quick Reference

| Categoria | Regra | Acima disso |
|-----------|-------|-------------|
| Python: arquivo | ≤ **300** linhas | Extrai módulo |
| Python: função | ≤ **50** linhas | Extrai helper |
| Python: type hints | Obrigatório função pública | `def create(video: bytes, filename: str) -> dict:` |
| TS/TSX: arquivo | ≤ **250** linhas | Extrai componente |
| TS: função | ≤ **40** linhas | Extrai hook/util |
| TS: props | Interface tipada, sem `any` | `interface Props { analysis: FormAnalysis }` |
| Rust: arquivo | ≤ **800** linhas | Separa em módulo |
| Rust: função | ≤ **60** linhas | Extrai fn |
| Complexidade | ≤ **10** (McCabe) | Refatora |
| Parâmetros | ≤ **4** | Usa struct/dataclass |

## Nomenclatura

### Python

| Entidade | Convenção | ✅ Certo | ❌ Errado |
|----------|-----------|----------|-----------|
| Arquivos | `snake_case` | `form_service.py` | `formService.py` |
| Classes | `PascalCase` | `FormService` | `form_service` |
| Funções | `snake_case` | `get_connection()` | `getConnection()` |
| Constantes | `UPPER_SNAKE` | `MAX_FILE_SIZE` | `maxFileSize` |
| Privado | `_` prefixo | `_normalize()` | `__normalize__` |
| Booleanos | `is_`/`has_` prefixo | `is_reliable` | `reliable_flag` |

### TypeScript/TSX

| Entidade | Convenção | ✅ Certo | ❌ Errado |
|----------|-----------|----------|-----------|
| Arquivos (componentes) | `PascalCase.tsx` | `FormAnalysis.tsx` | `formAnalysis.tsx` |
| Arquivos (utils) | `camelCase.ts` | `api/client.ts` | `api/Client.ts` |
| Componentes | `PascalCase` | `FormAnalysisCard` | `formAnalysisCard` |
| Interfaces/Types | `PascalCase` | `FormMetrics` | `IFormMetrics` |
| Funções/variáveis | `camelCase` | `getUser()` | `get_user()` |
| Constantes | `SCREAMING_SNAKE` | `API_BASE_URL` | `apiBaseUrl` |

### Rust

| Entidade | Convenção |
|----------|-----------|
| Arquivos | `snake_case.rs` |
| Tipos | `PascalCase` |
| Funções | `snake_case` |
| Constantes | `SCREAMING_SNAKE` |
| Erros | `PascalCase` (enum) |

## Limites de código

```
Python: 300 linhas/arquivo · 50 linhas/função · 4 parâmetros
TS/TSX: 250 linhas/arquivo · 40 linhas/função · 4 parâmetros
Rust:   800 linhas/arquivo · 60 linhas/função · 4 parâmetros
Todos:  10 complexidade ciclomática máxima
```

**Arquivos que precisam de refatoração** (fora do limite hoje):
- `FormAnalysis.tsx` (343 linhas) → quebrar em `MetricPill` + `PlanSection` + `VideoPlayer`
- `stride_vision/src/lib.rs` (685) → modularizar em `pose/`, `metrics/`, `overlay/`

## Clean Code

| Regra | Exemplo no projeto |
|-------|-------------------|
| **Nomes que revelam intenção** | `get_connection()` ✅ · `process_data()` ❌ |
| **Uma responsabilidade por função** | `auth.register()` só cadastra, não envia email |
| **DRY (só na 3ª repetição)** | 1-2 repetições ok; 3+ extrai |
| **Early return** | Preferir guard clauses a if aninhados |
| **Sem else após return** | `if x: return a` · `return b` |
| **Magic numbers → constantes** | `CADENCE_MIN = 170` não `if v < 170` |
| **Sem código comentado** | Deleta em vez de comentar |
| **Sem print/console.log** | Usar `Logger` ou `console.error` |
| **Imports ordenados** | stdlib → third-party → local (ruff/isort) |

## Testes

| Regra | Como |
|-------|------|
| 1 arquivo por módulo | `api/form.py` → `tests/test_form.py` |
| Herméticos (sem Ollama real) | Mock `OllamaClient` + DuckDB em memória |
| Métricas: property-based | `cadence_spm` sempre >= 0 e <= 300 |
| Grounding: toda claim tem fonte | `FormDeviation.source` obrigatório |
| E2E separado | `pytest -k "not e2e"` no dia a dia |
| Nome: `test_{função}_{cenário}` | `test_create_invalid_file`, `test_get_not_found` |

## System Design

| Princípio | Onde se aplica |
|-----------|----------------|
| **Controller fino + Service gordo** | `api/main.py` delega pra `api/form.py` |
| **Composição sobre herança** | `FormService(queue, binary)` no construtor |
| **Base\* interfaces** | `BaseLLMClient`, `BaseEmbedder`, `BaseRetriever` |
| **Background p/ pesado** | Upload → `JobQueue.enqueue` → `processing` |
| **Graceful degradation** | `reliable=false`, coach avisa refilmar |
| **Grounding: LLM redige, não calcula** | Comparações são Python, LLM só redige |
| **NULL, não 0** | Métrica ausente = `null`, nunca `0` |
| **Idempotência** | POST `/coach` mesma analysis_id não duplica |

## Critical Reminders

1. **Type hints obrigatórios** em toda função pública Python
2. **Métrica `null`** quando indisponível — nunca `0` (que é valor válido)
3. **Grounding**: coach só cita fonte que existe no corpus RAG
4. **`ruff format .` e `pytest -k "not e2e"`** antes de todo push
5. **Sem .env no git** — credenciais em clear text = blocker

## O que NÃO fazer

| Evitar | Por quê |
|--------|---------|
| Coverage mínimo obrigatório | Gera teste besta pra bater número |
| Separar cada classe em arquivo | Infla diretório sem ganho pra 1 dev |
| Abstract class pra tudo | Só as Base\* que têm 2+ implementações |
| Teste de UI componente puro | Custo > ganho até ter 10+ páginas |
| Design patterns "porque sim" | Só quando resolver problema real |
