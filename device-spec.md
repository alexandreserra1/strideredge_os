# StriderEdge — Especificação do Dispositivo (Fase 3)

> Spec de hardware/firmware do wearable próprio. **NÃO se constrói agora** — é a Fase 3 do
> roadmap (ver `plan.md §8` e `§10`). Este doc existe para que cada decisão de software de
> hoje permaneça compatível com o device de amanhã ("já desenhado"). Referência de mercado:
> Amazfit Helio Strap Pro (ver memória do projeto).

## 0. Princípio-chave: não se "cria" um IMU

Um IMU é um **chip MEMS de prateleira** (~US$3–7). Não se fabrica silício — monta-se um device
**em volta** de um sensor pronto. O reconhecimento de movimento (DTW/FFT) **não roda no device**
(pouca CPU/bateria): o device **captura e transmite**; a matemática roda no nosso backend (o
kernel Rust que já existe). É o modelo do Amazfit (strap captura, app/nuvem calcula).

## 1. Peças

| Peça | Função | Exemplo |
|---|---|---|
| **IMU** | acelerômetro + giroscópio (6 eixos) ou + magnetômetro (9 eixos) | ICM-42688, BMI270, MPU-9250 |
| **MCU + rádio BLE** | lê o sensor, bufferiza, transmite | Nordic **nRF52840** (padrão wearable) |
| **Bateria** | LiPo + carga | — |
| **Firmware** | código no chip (captura/transporte) | ver §3 |

**Protótipo de menor atrito:** placa **Seeed XIAO nRF52840 Sense** (~US$20) já traz **IMU + BLE +
MCU numa só plaquinha, sem solda**. Permite prender no corpo e capturar já — sem projetar PCB.

## 2. Posição do sensor (decisão que trava o resto)

- **Cintura** → HYROX/híbrido: movimento e estabilidade de tronco, carga muscular sob fadiga
  (foi a escolha do Amazfit Helio Pro; pulso sofre com pegada/grip nas estações).
- **Pé/canela** → corrida: impacto, pisada, pronação, assimetria E/D (add-on premium; ambiente hostil).
- **Pulso** (ex.: app Connect IQ): mais acessível, porém menor fidelidade para força/HYROX.

## 3. Firmware: Rust embarcado (mas é OUTRO Rust)

- **Firmware Rust** = `no_std`, roda no chip, mexe em registradores. Frameworks `embassy` / `nrf-hal`
  / RTIC. nRF52840 tem bom suporte Rust. **≠ do nosso kernel Rust** (`std`, roda no celular/PC via
  PyO3, faz DTW/FFT). São dois mundos; só a linguagem é a mesma.
- **Para prototipar rápido:** C++/Arduino na XIAO (libs prontas do IMU). Rust embarcado é o caminho
  "raiz", migrável depois.
- **Responsabilidade do firmware:** ler IMU a N Hz → timestamp → buffer → gravar/transmitir. **Nada
  de reconhecimento** no device.

## 4. Schema da amostra (definir uma vez → vira `ImuParser` + colunas no DuckDB)

Cada amostra: `(timestamp, accel_x/y/z, gyro_x/y/z [, mag_x/y/z])` a ex. **50 Hz, 9 eixos**.
Taxa/eixos afetam banda, bateria e fidelidade do reconhecimento. O device entra pelo
`BaseTelemetryParser` existente como um novo `ImuParser` — o resto do pipeline (DuckDB → kernel →
coach) **não muda**.

## 5. Transporte (como o dado chega)

- **Modo A — gravar e sincronizar depois (offline):** firmware salva na flash interna durante o
  treino; no fim, o app baixa a sessão por **BLE** (ou USB). Simples e robusto → **v1** (igual hoje
  baixamos o `.FIT` da Garmin).
- **Modo B — streaming ao vivo (BLE GATT, notificações):** amostras em tempo real → coach ao vivo.
  Mais difícil (banda/bateria) → Fase 2 do device.

Transporte = **Bluetooth Low Energy**: serviço/característica **GATT** customizado; o app lê e sobe
pro backend. (O device também pode fazer **broadcast de FC no perfil BLE padrão** — útil desde cedo.)

## 6. Testar no corpo + dataset rotulado (o passo essencial)

1. Prende o protótipo (cintura ou pé).
2. Faz um movimento **rotulado** (ex.: "10 wall balls").
3. Captura o log.
4. **Repete muitas vezes, rotulado** → vira o **dataset de treino** do classificador (foi assim que
   o Amazfit montou a "biblioteca treinada"). Passo sem glamour, mas indispensável.
5. Valida: o **DTW** casa uma rep nova contra o template? O **FFT** mostra a queda de frequência sob
   fadiga (ex.: -20% na empurrada do sled após 25 m)?

Ver `plan.md §10.1` para o rigor de teste em camadas (host `cargo test` sobre traços gravados →
replay no PC → on-device `probe-rs`/`defmt` → calibração vs. referência).

## 7. As 6 decisões que precisam estar desenhadas

1. **Posição do sensor** (cintura HYROX / pé corrida).
2. **Taxa + eixos** (ex.: 9 eixos @ 50 Hz).
3. **Schema da amostra IMU** (vira `ImuParser` + DuckDB).
4. **Transporte** (gravar-e-sincronizar primeiro; streaming depois).
5. **Onde roda o reconhecimento** (backend, NÃO device).
6. **Protocolo de dados rotulados** (como gravar/rotular os movimentos).

## 8. Módulos de modalidade (mesmo motor, interpretadores diferentes)

| | **HYROX** | **CrossFit** |
|---|---|---|
| Estrutura | fechada: 8 stations fixas, ordem conhecida | aberta: WODs variáveis, combos livres |
| Reconhecimento | fácil — segmenta + mede sequência conhecida | difícil — classifica movimento + detecta transições |
| Motor | IMU + kernel DTW/FFT | o mesmo |

Arquitetura: `BaseModalityModule` → `HyroxModule` (template fixo + ordem) e `CrossfitModule`
(classificador aberto). Disciplina vem de **rótulo/modo**, nunca de chute (precedente: modo
"HYROX Race" do Amazfit).

## 9. Coaching de VOZ em tempo real (momento 2 — falar no ouvido durante a corrida)

O coach tem **dois momentos**: (1) resumo **pós-corrida** (LLM+RAG, no backend; latência de segundos
ok) e (2) **tempo real** — avisos de voz **durante** a corrida (determinístico, <500ms, **sem LLM**).
Esta seção é o momento 2.

### 9.1 Fluxo no produto (igual Runna/Garmin)
```
sensores ao vivo (GPS do celular + BLE da cinta/relogio)
  → app no celular: stream → MOTOR DE CUES (RealtimeCoach)
  → TTS NATIVO do celular (texto → voz, offline)  → fone BLE (abafa a musica)
```
- **Tudo no celular** no momento 2 — rede no meio mataria os <500ms. O backend (DuckDB/RAG/LLM)
  serve só o momento 1.
- **Voz = TTS do SO** (iOS/Android), voz selecionável. Não empacotamos voz nenhuma — Runna e Garmin
  fazem igual; Strava nem tem voz. (No dev, o stand-in é o `say` do macOS via `MacSayAnnouncer`.)

### 9.2 As costuras já existentes no código (`analytics/realtime.py`)
- **Motor:** `RealtimeCoach` + regras (`BaseCueRule`, Strategy) — a MESMA lógica do dev ao app.
- **Entrega (`BaseAnnouncer`):** `LogAnnouncer` (testes) · `MacSayAnnouncer` (dev, voz do macOS) ·
  **`CallbackAnnouncer`** = a costura pro app: encaminha o `Cue` a um callback; no celular esse
  callback chama o **TTS nativo** (o "PhoneTTSAnnouncer" é isto ligado ao bridge de voz).
- **Fonte:** o motor consome `on_sample(Sample)`. Hoje `ReplayDriver` alimenta do `.FIT` (banco);
  no app, um `LiveStreamDriver` alimenta dos sensores ao vivo e chama o MESMO `on_sample`.

### 9.3 O que falta (fase C do roadmap — o app)
1. App mobile lendo **GPS + sensor BLE ao vivo**.
2. **Portar o motor** pro celular: regras são leves (reescrever no idioma do app) **ou** compilar a
   parte pesada (Kalman p/ suavizar o sinal vivo) do **kernel Rust** — "escreve uma vez, roda no
   servidor e no aparelho" (ver §10 do `plan.md`).
3. `PhoneTTSAnnouncer` = `CallbackAnnouncer` ligado ao TTS nativo.

**Costura pronta:** o motor e o contrato de voz (`BaseAnnouncer`) existem e estão testados; no app só
se troca a FONTE (replay → stream BLE) e o ANNOUNCER (say → TTS do celular). O motor não muda.

---

**Nada se joga fora:** o kernel genérico, o `BaseTelemetryParser`, o DuckDB e o coach são o **mesmo
cérebro** do celular ao device — só muda a fonte do sinal. A arquitetura foi desenhada para isso
desde a Fatia 0.
