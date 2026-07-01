# StriderEdge — Especificação do App Mobile (Fase C)

> Design do app de celular: **momento 1** (resumo pós-corrida, cliente da API) + **momento 2**
> (coaching de voz em tempo real, on-device). É a fase C do roadmap (`plan.md §10`). NÃO se
> constrói agora — este doc deixa a fase "já desenhada" pra não exigir retrabalho. As costuras
> no backend/kernel já existem (ver §8).

## 0. Os dois momentos, no app

| | **Momento 1 — pós-corrida** | **Momento 2 — tempo real** |
|---|---|---|
| O quê | resumo (fortes/fracos/o que fazer), gráficos, mapa | voz no ouvido: pace/FC/cadência |
| Onde roda | **backend** (API) — o app só renderiza | **100% no celular** (offline, <500ms) |
| Precisa de rede? | sim (chama a API) | **não** (loop local) |
| Reuso | toda a API/analyzers/coach que já existem | `RealtimeCoach` + `BaseAnnouncer` que já existem |

## 1. Framework do app

- **UI + cliente da API (momento 1):** **React Native** ou **Flutter** — um código pra iOS+Android,
  rápido de entregar (é basicamente um cliente HTTP + telas).
- **Loop de corrida (momento 2):** exige **execução em background** confiável (GPS+BLE com a tela
  apagada) — o ponto gnarly do mobile. Provavelmente **módulos nativos** (Swift/Kotlin) para a
  sessão de treino, mesmo num app RN/Flutter.
- Decisão a tomar na hora: RN (JS, `react-native-ble-plx`, `react-native-tts`) vs Flutter (Dart,
  `flutter_blue_plus`, `flutter_tts`). Ambos servem; o núcleo de tracking tende a virar nativo.

## 2. Momento 1 — pós-corrida (fácil, reusa tudo)

App = **cliente fino** da nossa FastAPI: chama `/activities/{id}`, `/coach`, `/fitness`,
`/training-load` etc. e desenha. Nada novo no backend — a API já é consumida pelo dashboard hoje;
o app é "outro cliente da mesma API". No desenvolvimento roda contra o **backend LOCAL**;
**hospedar é a última etapa** (só ao ir pra usuários reais — ver `plan.md §10`).

## 3. Momento 2 — tempo real (on-device)

```
GPS do celular + sensores BLE (cinta FC / footpod)
   → LiveStreamDriver (nova FONTE) → on_sample(Sample)
   → RealtimeCoach (kernel Rust: Kalman suaviza + regras de cue)
   → PhoneTTSAnnouncer (TTS nativo)  → fone BLE (abafa a música)
   → grava a sessão bruta (pra subir depois)
```
O **motor e o contrato de voz já existem** (`analytics/realtime.py`): só se troca a **fonte**
(`ReplayDriver` → `LiveStreamDriver`) e o **announcer** (`MacSay` → `PhoneTTS`). O miolo não muda.

## 4. Ingestão ao vivo (o trabalho novo de verdade)

- **GPS** do celular (~1 Hz) → pace/velocidade.
- **BLE por perfis-padrão GATT:** Heart Rate (0x180D), Running Speed and Cadence (0x1814) — cinta
  de FC, footpod (ex: Stryd) ou relógio. Libs prontas (`ble-plx`/`flutter_blue_plus`).
- **Alternativa:** app Garmin **Connect IQ** transmitindo o IMU/dados ao vivo (a ponte já discutida
  no `device-spec.md`), ou workout ao vivo via HealthKit.
- **Background execution (gnarly):** iOS/Android matam apps em background — precisa de *background
  location* + *workout session* pra manter GPS+BLE com a tela apagada. É o maior risco técnico.

## 5. O motor no celular (Rust "escreve uma vez")

- As **regras** de cue são lógica leve → dá pra reescrever no idioma do app **ou** compartilhar.
- O **Kalman** (suavizar o sinal vivo, evita disparar cue por ruído de GPS) **vale** Rust.
- Caminho recomendado (`plan.md §10`): **compilar o kernel Rust pro mobile** (via `uniffi`/FFI) →
  Kalman + política de cue = **fonte única** rodando no servidor E no celular. Sem reescrever a matemática.

## 6. Gravar e subir a sessão (fecha o ciclo com o momento 1)

Durante a corrida o app **grava o stream bruto**; ao terminar, **sobe pro backend**, que ingere como
mais uma atividade — via o `BaseTelemetryParser` (um `AppSessionParser` = mais um parser; o pipeline
DuckDB→kernel→coach **não muda**). Aí o **momento 1** (resumo pós-corrida) roda igual a hoje.

## 7. Dependências e ordem de de-risking

- **Tudo roda contra o backend LOCAL.** Hospedar é a **última** etapa do produto (ver `plan.md §10`).
- **Momento 2 não depende de backend** (é on-device); **momento 1** consome a API local.
- **Ordem sugerida (de-riscar em camadas):**
  0. App cliente da API (momento 1) contra o backend local — risco baixo.
  1. Ingestão ao vivo com **sensor BLE pronto** (cinta FC / Stryd) — valida GPS+BLE+background.
  2. Plugar `LiveStreamDriver` + `PhoneTTSAnnouncer` → **momento 2 tocando no fone**.
  3. Gravar+subir a sessão → fecha com o momento 1.
  4. **Hospedar — só no fim**, quando for pra usuários reais.

## 8. Costuras JÁ prontas (reuso) vs. novo

| Já pronto (reusa) | Novo na Fase C |
|---|---|
| API REST + analyzers + coach (momento 1) | telas do app + cliente HTTP |
| `RealtimeCoach` + regras + `BaseAnnouncer` | `LiveStreamDriver` (fonte ao vivo) |
| `CallbackAnnouncer` (costura de voz) | `PhoneTTSAnnouncer` (TTS nativo) |
| kernel Rust (Kalman) | build Rust→mobile (FFI) |
| `BaseTelemetryParser` | `AppSessionParser` (stream gravado → pipeline) |

## 9. Riscos honestos
- **Background execution** (iOS/Android matando o app) — o maior.
- **Confiabilidade/bateria do BLE + GPS** ao longo de horas.
- **Cross-compile Rust→mobile** (FFI) — setup novo.
- **Revisão nas app stores** + permissões (localização em background, BLE).

---

**Princípio:** o app é só **mais um cliente** (momento 1) e **mais uma fonte/saída** (momento 2)
plugando nas costuras existentes. Nada do backend/kernel se reescreve — só ganha um front e um
cano de dados ao vivo. É exatamente pra isso que `BaseAnnouncer`, `on_sample` e `BaseTelemetryParser`
foram desenhados.
