# StriderEdge OS - Documentação Oficial de Engenharia e System Design

Bem-vindo à documentação oficial do **StriderEdge OS**. Este documento serve como o blueprint arquitetural definitivo para o desenvolvimento do nosso ecossistema de biotelemetria e analytics esportivo de alta performance.

O objetivo do projeto é capturar dados complexos de séries temporais vindos de dispositivos vestíveis (wearables), processar binários de baixo nível em tempo real, persistir em um data store analítico local e aplicar inteligência preditiva para ganho de performance em modalidades híbridas (como Crossfit e treinos voltados ao Hyrox).

---

## 0. Visão de Produto

O StriderEdge OS é um **wearable de IA para atletas de corrida, HYROX e CrossFit** — um sensor sem tela usado no corpo durante o treino que captura movimento e biometria, processa os dados e entrega insights por um **coach de IA acionável** (prescreve o "como corrigir", não só descreve). Inspiração de hardware: Amazfit Helio Strap. Monetização **por hardware, sem assinatura obrigatória**.

### 0.1 Fases do produto

1. **Corrida (fase ATUAL)** — análise de arquivos `.FIT`: cadência, pace, FC, eficiência por terreno, ponto de quebra mecânica, risco de lesão. Coach por LLM local + RAG.
2. **HYROX** — segmentar e analisar os **8 stations** individualmente, split cardio/muscular por estação, degradação de movimento por fadiga.
3. **CrossFit** — reconhecimento de WODs e movimentos olímpicos, carga muscular por sessão.

### 0.2 Taxonomia de features (futuro, conforme o hardware/ML evoluem)

Qualidade de movimento por exercício · carga muscular estimada via aceleração · queda de performance (ex.: redução da frequência de repetições = fadiga) · reconhecimento automático de exercícios · split cardio vs. muscular do esforço.

### 0.3 ATUAL vs FASE 2 (evitar overengineering)

- **ATUAL (local, single-user):** Python + Rust (maturin) + DuckDB + Ollama (Qwen + bge-m3) + Streamlit. Fonte de dados = `.FIT`.
- **FASE 2 (quando hospedar / multiusuário):** Celery+Redis (fila), TimescaleDB/PostgreSQL, AWS S3, Docker+AWS, TF Lite/ONNX (inferência on-device). **Não são stack atual** — entram só quando o volume justificar.

---

## Estado atual (checkpoint v0.1.0)

**Feito:** ingestão (`FitParser` + **sync automático Garmin**, idempotente, arquiva `.FIT` bruto) ·
kernel **Rust** (Kalman/DTW/FFT) · análises de corrida (§6.1 quebra, §6.2 eficiência, §6.3 semáforo,
zonas de FC, terreno) · **carga/ACWR** (`TrainingLoad`, TRIMP por zona + portão de confiança) ·
**fitness/prova** (`RunningFitness`: preditor de Riegel 5k→42k + tendência de eficiência velocidade÷FC
— fecha a Trilha 1) · **coach IA local** (Ollama/Qwen, RAG citável + fallback web, personalização,
eval anti-alucinação, agêntico text-to-SQL) · **API REST** (FastAPI OOP) + **dashboard** Streamlit
(cliente HTTP) · **logging estruturado** · conexão reutilizável · **67 testes + CI verde**, tudo versionado.

**Próximo:** HYROX (8 stations — precisa de dado) · agendar o sync (cron) · Fase B (hospedar) com usuários.

---

## 1. Visão Geral & Arquitetura do Sistema (Monorepo Modular)

Para garantir simplicidade operacional de 1 a 100 usuários, mitigar custos de rede e manter a facilidade de desenvolvimento, o **StriderEdge OS** adota uma abordagem de **Monolito Modular** sob uma estrutura de **Monorepo**. Evitamos microserviços prematuros, mas isolamos rigorosamente os contextos de software para que possam ser destacados como serviços independentes no futuro.

### 1.1 Árvore do Repositório

> strideredge-os/
├── .github/workflows/       # CI/CD pipelines (compilação automática do Rust) — Fase 2
├── pyproject.toml           # Build da extensão Rust (maturin) + dependências Python
├── Cargo.toml               # Manifesto workspace do Rust (futuro)
├── Makefile                 # Automação de comandos locais
├── core/                    # Módulo Python central (Domínio e Regras de Negócio)
│   ├── __init__.py
│   ├── database.py          # Conexão DuckDB e execução de migrações
│   ├── domain/              # Entidades e Value Objects puros
│   ├── parsers/             # Parser .FIT em Python (fitdecode) — Fatia 1
│   └── framework/           # Abstrações e interfaces (OOP Framework)
├── rust_kernel/             # Kernel de COMPUTAÇÃO numérica em Rust (não parser!)
│   ├── Cargo.toml
│   └── src/
│       ├── lib.rs           # Ponte de exportação PyO3 (registro do módulo)
│       ├── kalman.rs        # Suavização de trilha GPS (filtro de Kalman) — Fatia 2
│       ├── dtw.rs           # Dynamic Time Warping: comparar esforços — Fatia 2
│       └── fft.rs           # Análise espectral de cadência (rustfft) — Fatia 2
├── ingestion/               # Coleta automatizada da Garmin (garminconnect) — Fatia 1
│   └── garmin_sync.py
├── api/                     # Camada de Entrega (FastAPI RESTful Gateway)
│   ├── main.py
│   ├── routers/
│   └── middleware/
├── analytics/               # Mecanismos de Inteligência & Machine Learning
│   ├── models/              # Modelos preditivos scikit-learn treinados
│   ├── processors.py        # Orquestradores da camada de inteligência
│   └── prompt_templates.py  # Contextos estruturados para a API do Claude
├── db/                      # Infraestrutura de Dados e Migrações
│   └── migrations/          # Scripts DDL para inicialização do DuckDB
└── storage/                 # Diretório local de dados (Ignorado no Git, exceto sementes)
    └── strideredge.db       # Arquivo físico único do DuckDB


### 1.2 Fontes de Dados e Automação de Coleta (Ingestão)

O sistema não depende de uploads manuais. A ingestão é automatizada e puxa a telemetria original sincronizada pelo wearable (como um Forerunner 165 ou fitas cardíacas) direto da nuvem, garantindo a obtenção do arquivo `.FIT` bruto e sem perdas.

**A Biblioteca Principal (Python): `garminconnect`**
Como a API oficial de Health da Garmin é fechada para uso corporativo, utilizamos a biblioteca open-source `garminconnect` no Python. 
* **O que ela faz:** Simula a autenticação de uma sessão web do usuário.
* **O Fluxo:** Um *cronjob* ou *scheduler* no backend roda periodicamente, faz o login silencioso, verifica se há novas atividades registradas e faz o download direto do arquivo `.FIT` binário para a pasta temporária do StriderEdge OS.
* **Vantagem:** Total autonomia sobre os dados de altimetria, dinâmica de corrida e oscilação, sem depender das métricas mastigadas e limitadas (JSON) de APIs públicas como a do Strava.

**O Parser `.FIT` (Python): `fitdecode`**
Assim que o Python baixa o arquivo, ele mesmo faz o parsing com a biblioteca `fitdecode` (ou o `garmin-fit-sdk` oficial), implementando a abstração `BaseTelemetryParser`. Parsear alguns milhares de registros é I/O leve — Python resolve em milissegundos, sem necessidade de Rust aqui.

> **Decisão de arquitetura:** o Rust **não** parseia o `.FIT`. Parsing é I/O leve e não se beneficia de código nativo. O Rust foi reposicionado para o **kernel de computação numérica** (ver Seção 3), onde ganha 50–500x de verdade sobre Python por ser CPU-bound e travar no GIL.

---

## 2. Abstração de Software & Framework OOP (Python)

A camada de engenharia e regras de negócio do Python é estruturada usando Programação Orientada a Objetos (POO) rigorosa, aplicando herança, classes abstratas (`abc`) e polimorfismo. Isso cria um framework extensível para novos tipos de dados ou modelos preditivos.

### 2.1 Código do Framework Base (`core/framework/interfaces.py`)

```python
from abc import ABC, abstractmethod
from typing import Dict, Any, List
import polars as pl


class BaseTelemetryParser(ABC):
    """
    Classe Abstrata que define o contrato para extração de binários.
    Se amanhã integrarmos arquivos .GPX, .TCX ou dados diretos de sensores IoT,
    basta herdar desta classe.
    """
    def __init__(self, file_path: str):
        self.file_path = file_path

    @abstractmethod
    def validate_file(self) -> bool:
        """Valida integridade estrutural e headers do arquivo bruto."""
        pass

    @abstractmethod
    def to_dataframe(self) -> pl.DataFrame:
        """Executa a extração pesada e retorna um DataFrame padronizado."""
        pass


class BasePredictiveEngine(ABC):
    """
    Abstração para motores de machine learning e análises estatísticas temporais.
    """
    def __init__(self, model_path: str):
        self.model_path = model_path
        self.model = self._load_model()

    @abstractmethod
    def _load_model(self) -> Any:
        """Carrega o artefato binário do modelo treinado (Pickle/Joblib)."""
        pass

    @abstractmethod
    def predict_anomalies(self, data: pl.DataFrame) -> List[Dict[str, Any]]:
        """Analisa o DataFrame de telemetria à procura de anomalias mecânicas."""
        pass


class BaseIntelligenceNotifier(ABC):
    """
    Interface para envio dos relatórios gerados pela IA (Coach Sintético).
    """
    @abstractmethod
    def dispatch_report(self, user_id: str, payload: Dict[str, Any]) -> bool:
        """Envia os insights consolidados para o destino final (Terminal, Telegram, etc)."""
        pass
```

---

## 3. Integração de Baixo Nível: Python + Rust como Kernel Numérico (PyO3)

O Rust não faz parsing. Ele é o **kernel de computação numérica**: a matemática pesada, sequencial e CPU-bound que o GIL do Python torna lenta. Esse é o único lugar do projeto onde código nativo ganha de verdade (50–500x), e por isso é onde o Rust mora.

A biblioteca PyO3 compila o código Rust em um Shared Object (`.so` no Linux/macOS ou `.pyd` no Windows), que o Python importa como um módulo normal — sem rede, sem serialização JSON entre processos.

### 3.1 Algoritmos do Kernel (Fatia 2)

- **`kalman.rs`** — Filtro de Kalman para suavizar a trilha de GPS. O GPS do Garmin treme; rodar o filtro sobre ~10.000 pontos é um loop sequencial puro, ideal para Rust. Corrige distância e ritmo.
- **`dtw.rs`** — Dynamic Time Warping para comparar dois esforços (corrida de hoje vs. PR no mesmo percurso). É O(n·m): ~25 milhões de operações para séries de 5.000 pontos. Doloroso em Python puro, instantâneo em Rust.
- **`fft.rs`** — Análise espectral (FFT) da cadência para detectar perda de regularidade da passada via frequência, não só média móvel.

### 3.2 Bibliotecas e Crates Utilizadas

**Rust (`rust_kernel/Cargo.toml`):**

```toml
pyo3 = { version = "0.22", features = ["extension-module", "abi3-py39"] }  # ponte Python<->Rust
ndarray = "0.16"   # álgebra de vetores/matrizes (Kalman, DTW)   — Fatia 2
rustfft = "6"      # FFT performática                            — Fatia 2
# rayon = "1"      # paralelismo de dados (opcional)             — futuro
```

**Build (Python):** a extensão é compilada com **`maturin`** (`maturin develop`), configurado no `pyproject.toml`. Para dados, usamos **Polars** (lê Arrow nativo, ótimo para séries temporais) — sem Pandas, para reduzir dependências e conversões.

---

## 4. Arquitetura do Banco de Dados (Star Schema no DuckDB)

Utilizaremos uma modelagem **Star Schema** (Esquema Estrela) otimizada para processamento analítico (OLAP). O DuckDB funciona de forma embutida, salvando todo o banco em um único arquivo de disco (`strideredge.db`) e operando de forma vetorial na memória RAM.

### 4.1 Diagrama Entidade-Relacionamento Lógico

- **Tabelas de Dimensão:** Guardam o contexto estruturado e metadados.
- **Tabela de Fatos (`fact_telemetry`):** Série temporal granular contendo leituras numéricas puras segundo a segundo.

```
+-----------------------+              +-----------------------+
|     dim_users         |              |     dim_devices       |
+-----------------------+              +-----------------------+
| PK | user_id (UUID)   |              | PK | device_id (INT)  |
|    | name             |              |    | manufacturer     |
|    | age              |              |    | model_name       |
+-----------------------+              +-----------------------+
            |                                      |
            | 1                                    | 1
            |                                      |
            | N                                    | N
      +--------------------------------------------------+
      |                 fact_telemetry                   |
      +--------------------------------------------------+
      | PK     | telemetry_id (BIGINT)                   |
      | FK     | activity_id (UUID)                      |
      | FK     | user_id (UUID)                          |
      | FK     | device_id (INT)                         |
      |        | timestamp (TIMESTAMP)                   |
      |        | heart_rate (SMALLINT)                   |
      |        | cadence (SMALLINT)                      |
      |        | latitude (DOUBLE)                       |
      |        | longitude (DOUBLE)                      |
      |        | altitude (FLOAT)                        |
      |        | vertical_oscillation (FLOAT)            |
      |        | stance_time_ms (FLOAT)                  |
      +--------------------------------------------------+
                        |
                        | N
                        |
                        | 1
                +-----------------------+
                |    dim_activities     |
                +-----------------------+
                | PK | activity_id(UUID)|
                |    | activity_name    |
                |    | start_time       |
                |    | total_distance   |
                |    | primary_type     |
                +-----------------------+
```

### 4.2 Esqueleto DDL (SQL DuckDB)

```sql
-- Inicialização do Banco de Dados Analítico

CREATE TABLE dim_users (
    user_id UUID PRIMARY KEY,
    name VARCHAR NOT NULL,
    birth_date DATE,
    weight_kg FLOAT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE dim_activities (
    activity_id UUID PRIMARY KEY,
    garmin_activity_id BIGINT UNIQUE, -- idempotência: evita reimportar a mesma atividade
    activity_name VARCHAR,
    start_time TIMESTAMP NOT NULL,
    total_distance_meters FLOAT,
    total_duration_seconds FLOAT,
    primary_type VARCHAR -- 'RUN', 'HYROX_WOD', 'FUTEVOLEI'
);

CREATE TABLE dim_devices (
    device_id INTEGER PRIMARY KEY,
    manufacturer VARCHAR,
    model_name VARCHAR,
    firmware_version VARCHAR
);

CREATE TABLE fact_telemetry (
    telemetry_id BIGINT PRIMARY KEY,
    activity_id UUID NOT NULL,
    user_id UUID NOT NULL,
    device_id INTEGER,
    timestamp TIMESTAMP NOT NULL,
    heart_rate SMALLINT,
    cadence SMALLINT,
    latitude DOUBLE,
    longitude DOUBLE,
    altitude FLOAT,
    vertical_oscillation FLOAT, -- Métricas avançadas Garmin HRM
    stance_time_ms FLOAT,
    FOREIGN KEY (activity_id) REFERENCES dim_activities(activity_id),
    FOREIGN KEY (user_id) REFERENCES dim_users(user_id),
    FOREIGN KEY (device_id) REFERENCES dim_devices(device_id)
);

-- Estratégia de Caching Analítico: Tabela de Agregados Materializados para o Dashboard
CREATE TABLE cache_workout_summary (
    activity_id UUID PRIMARY KEY,
    avg_hr FLOAT,
    max_hr FLOAT,
    avg_cadence FLOAT,
    total_elevation_gain FLOAT,
    metabolic_efficiency_score FLOAT,
    breaking_point_timestamp TIMESTAMP
);
```

---

## 5. API Design, Swagger & Autenticação

A interface externa expõe endpoints RESTful rígidos usando **FastAPI**. A API é puramente stateless e adota o padrão ACID para mutações relacionais básicas, mantidas diretamente no DuckDB via transações para simplificar a infraestrutura local.

### 5.1 Mecanismo de Autenticação (Auth Flow)

- **App Session Auth:** JWT (JSON Web Tokens) tradicional armazenado em Cookies `HttpOnly` seguros.
- **Wearable Gateway Auth:** Integração com o fluxo OAuth 2.0 da Garmin. O backend gerencia o redirecionamento, troca o `authorization_code` pelo `access_token` e salva os tokens criptografados na base para permitir que o worker Python busque novos arquivos `.FIT` em background de forma totalmente automática.

### 5.2 OpenAPI / Swagger Spec (Exemplo do Endpoint de Telemetria)

```yaml
openapi: 3.0.2
info:
  title: StriderEdge OS API
  version: 1.0.0
paths:
  /api/v1/telemetry/upload:
    post:
      summary: Ingestão manual/automatizada de arquivo binário de treino.
      security:
        - OAuth2PasswordBearer: []
      requestBody:
        content:
          multipart/form-data:
            schema:
              type: object
              properties:
                file:
                  type: string
                  format: binary
      responses:
        '201':
          description: Arquivo processado com sucesso pelo módulo Rust e persistido no DuckDB.
          content:
            application/json:
              schema:
                type: object
                properties:
                  activity_id:
                    type: string
                    format: uuid
                  records_processed:
                    type: integer

  /api/v1/analytics/coach-insights/{activity_id}:
    get:
      summary: Retorna a análise do treinador de inteligência sintética (Claude API).
      responses:
        '200':
          content:
            application/json:
              schema:
                type: object
                properties:
                  activity_id:
                    type: string
                  coach_verdict:
                    type: string
                  efficiency_score:
                    type: number
```

---

## 6. Camada de Inteligência & Analytics

A inteligência competitiva e preditiva do sistema é dividida em lógica analítica de banco de dados (SQL) e síntese contextual (LLM).

### 6.1 Detecção de Ponto de Quebra Mecânica via SQL Window Functions

Usamos funções de janela deslizante diretamente no DuckDB para mapear anomalias de esforço sem precisar de processamento pesado de IA em tempo real.

```sql
-- Query que detecta o exato segundo em que o atleta entrou em fadiga mecânica crítica
WITH rolling_metrics AS (
    SELECT
        timestamp,
        heart_rate,
        cadence,
        -- Média móvel dos últimos 30 segundos
        AVG(heart_rate) OVER(ORDER BY timestamp ROWS BETWEEN 30 PRECEDING AND CURRENT ROW) AS rolling_hr,
        AVG(cadence)    OVER(ORDER BY timestamp ROWS BETWEEN 30 PRECEDING AND CURRENT ROW) AS rolling_cadence
    FROM fact_telemetry
    WHERE activity_id = 'substituir-uuid-da-atividade'
)
SELECT
    timestamp,
    heart_rate,
    cadence
FROM rolling_metrics
WHERE heart_rate > 165 AND cadence < 160  -- Limiar de degradação: coração disparando e perna pesando
ORDER BY timestamp ASC
LIMIT 1;
```

### 6.2 Custo Metabólico e Eficiência Mecânica

**Fórmula Aplicada:**

$$\text{Eficiência Mecânica} = \frac{\text{Velocidade Relativa } (m/s)}{\text{Frequência Cardíaca } (BPM)} \times 100$$

O sistema segmenta a corrida por trechos planos e trechos de subida. Se o valor cair abruptamente na subida, indica baixa capacidade de transferência de força para provas híbridas.

### 6.3 Semáforo da Passada no Mapa (Python + Folium)

O script Python lê as colunas `latitude`, `longitude` e `cadence`. Usando a classe `ColorLine` do Folium, calculamos o desvio padrão da cadência do usuário. Trechos com cadência estável recebem a cor `#deff9a` (verde limão do app); trechos onde o atleta começou a "arrastar a passada" mudam dinamicamente para vermelho.

### 6.4 Prompt Estruturado para o Treinador Sintético (Claude API)

```python
def generate_coach_prompt(summary_metrics: dict, anomalies: list) -> str:
    return f"""
    Você é um treinador de elite especialista em competições híbridas como Hyrox e Crossfit Endurance.
    Analise os seguintes agregados numéricos do último treino do atleta e retorne um feedback direto,
    firme, casual e altamente técnico. Não faça rodeios. Diga onde ele falhou e como corrigir.

    Métricas Consolidadas:
    - Ritmo Cardíaco Médio: {summary_metrics['avg_hr']} BPM
    - Cadência Média: {summary_metrics['avg_cadence']} passos/min
    - Escore de Eficiência: {summary_metrics['efficiency_score']} m/s por batimento.

    Eventos Críticos Detectados no Banco Analítico:
    - O ponto de quebra mecânica ocorreu às {anomalies[0]['timestamp']} durante um segmento de subida.

    Retorne a resposta estruturada em até 3 parágrafos curtos direto no terminal.
    """
```

---

## 7. Pilha de Observabilidade (LGTM Stack) — Fase 2

> **Estágio atual (local):** observabilidade mínima — `structlog` emitindo logs JSON em arquivo e um `trace_id` por requisição (barato, já deixa as costuras prontas). A stack LGTM completa abaixo só entra quando o sistema for hospedado e multiusuário; rodar 4 serviços de monitoramento para 1–100 usuários locais seria mais infra do que a própria aplicação.

Quando hospedado, a coleta de dados de saúde do software é centralizada usando bibliotecas leves que exportam métricas para o ecossistema Grafana.

- **Loki:** O framework de logs do Python (utilizando o handler `logging-loki`) envia de forma assíncrona logs estruturados contendo tags como `level`, `module="rust_parser"` ou `module="api"`.
- **Prometheus:** Expõe um endpoint `/metrics` no FastAPI usando a biblioteca `prometheus-client`. Monitoramos:
  - Tempo de execução do parsing em Rust (histograma).
  - Tamanho em disco do arquivo `strideredge.db`.
  - Quantidade de requisições falhas na API do Garmin Connect.
- **Tempo:** Adota o padrão OpenTelemetry no Python. Cada requisição de upload injeta um `trace_id` que acompanha o ciclo de vida do dado desde a autenticação web até o momento em que a última linha de telemetria é commitada no DuckDB.

---

## 8. Norte: Dispositivo Wearable (visão de hardware, NÃO construir agora)

O hardware é Fase 3 (jornada longa). Toda decisão de software hoje deve mantê-lo viável — mas não se constrói nada de hardware ainda. Enquanto isso, os arquivos `.FIT` são a fonte primária de dados.

### 8.1 Referência real: Amazfit Helio Strap

Puck sem tela (~20g) com **PPG (5 fotodiodos + 2 LEDs) + acelerômetro + giroscópio + temperatura**, **BLE 5.2**, ~10 dias de bateria, 5ATM, **sem assinatura**. Placement no **braço (perto do coração)** — mais estável que o pulso em força/HYROX/corrida.

### 8.2 Estratégia de placement (modular e faseada)

- **v1 — peitoral/braço:** FC padrão-ouro (cinta peitoral ECG > PPG) + movimento de tronco, cadência, economia de corrida e respiração. Mais fácil de montar; ponto de partida.
- **Módulo futuro — pé/canela:** impacto, padrão de pisada, pronação e **assimetria E/D** — o diferencial de biomecânica. Ambiente mais hostil; entra como add-on premium.

### 8.3 BLE broadcast (feature forte)

O dispositivo expõe **FC/dados ao vivo via perfil BLE padrão** — interopera com relógios, ciclocomputadores, equipamentos e apps. Torna o aparelho útil desde cedo, mesmo antes da análise completa.

### 8.4 Por que a arquitetura atual já serve a esse norte

- **`BaseTelemetryParser`** → um sensor IoT é só mais um parser; o resto não muda.
- **Kernel Rust (Kalman/DTW/FFT)** → é exatamente a matemática que dados crus de IMU exigem (detecção de pisada, fusão de sinal). O Rust de hoje é o motor de amanhã, e o **firmware embarcado** será em Rust.
- Manter o kernel **genérico** (séries numéricas, não "dados de Garmin") e o schema extensível.

---

## 9. Capacidade & Concorrência

Como dimensionar workers, conexões e servidores. Regra-mãe: **Lei de Little** — `L = λ × W`,
onde **L** = requisições simultâneas (concorrência), **λ** = taxa de chegada (req/s),
**W** = tempo de cada uma no sistema. Mais tempo no sistema (W) = mais concorrência (L).

### 9.1 Dois perfis de requisição (W muito diferente)

| Requisição | W (tempo no sistema) |
|---|---|
| Ler DuckDB / kernel Rust / dashboard | milissegundos |
| **Veredito do Coach (Qwen)** | **5–15 segundos** — é o gargalo que dita o dimensionamento |

### 9.2 Hoje (local, single-user): 1 de tudo

Workers = 1 · conexões = 1 (a reutilizável) · servidores = 1 · simultâneas = 1.
Concorrência zero → fila/pool/Postgres/múltiplos workers seriam **overengineering**.

### 9.3 Fase 2 (hospedado): calcular, não chutar

Exemplo — 100 usuários, 20 vereditos no mesmo minuto, W≈10s →
`λ = 0,33 req/s × W = 10s → L ≈ 3,3` vereditos simultâneos. Daí:

- **Workers de inferência (LLM)** ≈ L + folga (~4 slots); cada Qwen-7B ~5GB de GPU → 1–2 GPUs **ou fila**.
- **Workers de API** (FastAPI): 2–4 (a API é rápida, W~50ms).
- **Conexões de banco**: pool ~10–20 (Postgres).
- **Servidores**: 1 app + o gargalo/custo é a **GPU do LLM**.

### 9.4 Gatilhos da Fase 2 (justificados pelo W alto do LLM)

- **Fila (Celery/Redis)**: vereditos lentos saem da API → workers de inferência. Só aqui a fila paga.
- **Postgres + pool**: DuckDB é single-writer embutido, não serve muitas conexões concorrentes;
  DuckDB fica no analítico, Postgres no transacional/concorrente.
- **Separar API (rápida) de inferência (lenta)**.
- **Maior alavanca de custo = baixar W** do coach (modelo menor/quantizado, GPU, cache de vereditos).

---

## 10. Roadmap de Build-out (backend → app → embarcado)

**Regra de ouro:** provar valor com o dado atual (dashboard = protótipo) antes de investir em
app/hardware (caros e lentos). Cada fase entrega algo útil sozinha; nada é jogado fora.

**Costura que evita retrabalho:** tudo consome **UMA API** (FastAPI). E o **kernel Rust
(Kalman/DTW/FFT) é escrito uma vez e roda nos dois lados** — servidor agora, cross-compilado
pro firmware depois. A matemática de sinal não se reescreve.

| Fase | O quê | Stack | Gatilho |
|---|---|---|---|
| **A — API-first** (próxima) | expor análises/coach via FastAPI; dashboard consome a API | FastAPI + atual | agora |
| **B — Hospedar** | auth, Postgres, fila pro LLM, deploy (ver §9 capacidade) | AWS/Docker, Postgres, Celery | quando houver usuários |
| **C — App mobile** | cliente **fino**: insights + conectar wearable por **BLE** + sync | React Native ou Flutter | API estável |
| **D — Dispositivo embarcado** | firmware Rust, IMU 100Hz, storage, BLE sync | Rust no-std (Embassy), Pico/nRF | valor provado + app pronto |

### 10.1 Estratégia meticulosa do embarcado (de-riscar em camadas)

0. **Sensor pronto primeiro** — plugar footpod/cinta BLE existente (Stryd, cinta FC) no pipeline:
   valida ingestão BLE + análise de IMU/FC ao vivo **sem firmware** (risco zero).
1. **Protótipo dev board** — Pico W/nRF52 + MPU6050, firmware Rust, coleta 100Hz, BLE sync (bancada).
2. **Rigor de teste:**
   - Host: kernel Rust com `cargo test` sobre **traços gravados** (entrada conhecida → saída esperada).
   - Replay: alimentar gravações reais pela lógica do firmware no PC antes do chip.
   - On-device: `probe-rs` + `defmt`/RTT para log e teste no chip.
   - Calibração: comparar saída do dispositivo vs. referência (Garmin/força) em movimentos padrão.
3. **PCB customizado** — só se o protótipo provar valor (anos à frente).

### 10.2 Padrões de arquitetura IoT (Fase D — documentar, NÃO construir agora)

Quando o dispositivo existir, a entrada de dados muda de "upload de `.FIT`" para
"stream de sensores em alta frequência (100–200 Hz)". Aí entram padrões de ponta —
mas só então; adotá-los hoje (zero device, 1 usuário) é overengineering.

| Padrão | Pra quê | Costura que já temos |
|---|---|---|
| **MQTT / BLE GATT** | transporte leve device→app/servidor | ingestão isolada; `BaseTelemetryParser` (sensor = mais um parser) |
| **Stream processing** (Kafka/Flink) | processar fluxo contínuo de IMU | hoje é batch pós-treino (constituição §6); migra quando for tempo real |
| **Edge inference** (TF Lite/ONNX em Rust) | rodar modelo leve NO dispositivo | kernel Rust compartilhado servidor↔device; modelos "leves o bastante" (const.) |
| **Time-series DB** (Timescale/Influx) | escala de séries de sensor | DuckDB no analítico; troca-se a camada de dados sem mexer no domínio |
| **CQRS / event-sourcing** | separar ingestão (escrita) de consulta (leitura) | 3 camadas já separam dados/domínio/entrega; API-first isola a leitura |

**Princípio:** o device é só **mais uma fonte** entrando pelas costuras existentes. Nada
do que foi construído (kernel Rust, parsers, API, análises) é jogado fora — só ganha um
novo produtor de dados na ponta.

---

## 11. Estratégia de Testes

**Agora (suíte hermética, roda no CI sem dados pessoais):**
- **Unit** — mecânica do RAG, guarda-corpos do SQL, métricas de eval (mockado, banco temp).
- **Integração** — API (TestClient) e analyzers sobre um DuckDB **sintético** semeado pela conftest.
- **Avaliação (RAG/coach)** — relevância e fidelidade com embeddings/LLM reais (gated por Ollama).
- **E2E / smoke** — cliente HTTP vs. servidor up (gated; vira smoke pós-deploy na Fase B).
- **Segurança / injeção** — o text-to-SQL é a superfície de ataque nº 1; `is_safe` barra
  SQL destrutivo, com testes confirmando recusa + dados intactos.
- **CI** — GitHub Actions: build do kernel Rust + `pytest` (Ollama/E2E pulam).

**Fase B (quando hospedar):**
- **Testes de configuração** (secrets/URLs/env de deploy) — base já existe (`STRIDEREDGE_DB`).
- **Smoke em produção** — subconjunto E2E pós-deploy (`/health`, endpoints chave).
- **Penetração completa** — auth, rede, rate-limit (além da injeção SQL já coberta).

---

## Nome e Significado do Projeto

**Nome Oficial:** StriderEdge OS

**Significado:** *Strider* representa a busca pela passada perfeita, cadência implacável e movimentação ágil e fluida através do terreno. *Edge* consolida a filosofia técnica do projeto: processamento pesado próximo da fonte, manipulação refinada de baixo nível e a busca constante pela vantagem competitiva máxima no esporte.
