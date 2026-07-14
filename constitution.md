# StriderEdge OS — Constituição do Projeto

Princípios não-negociáveis que guiam toda decisão técnica. Quando houver dúvida ou
conflito, este documento é o critério de desempate. Evolui quando uma nova decisão
"endurece" (vira regra). Curto de propósito — para ser lido sempre.

> **Pós-pivot (jul/2026 — app 100% visão computacional de lesão):** os princípios seguem valendo,
> relidos pro eixo vídeo. Ficam MOOT (eram do `.FIT`, removido): §5 (degradar sem GPS → agora é
> degradar sem detecção de pose confiável), §7-9 (ingestão `.FIT`/Garmin), §6 (offline pós-treino
> → o processamento de vídeo é offline-em-background pela fila). §1 (Rust p/ compute pesado) = agora
> o motor de pose `stride_vision`. §14 ("é app de risco de lesão") ficou MAIS central. §4: os
> contratos vivos são `BaseLLMClient/BaseEmbedder/BaseRetriever/BaseGuard`.

---

## Arquitetura & Stack

1. **Rust só para computação pesada e sequencial** (Kalman, DTW, FFT, futuro IMU).
   Python para I/O, orquestração, API, banco e LLM. Não usar Rust onde não há ganho real.
2. **Sem overengineering.** Infra pesada (fila, Elasticsearch, LGTM, load balancer,
   TimescaleDB/Postgres, AWS) só entra quando o volume/escala justificar. "Local agora,
   hospedado depois."
3. **Uma conexão de banco reutilizável por processo** — nada de abrir/fechar a cada query.
4. **Contratos abstratos + polimorfismo.** `BaseTelemetryParser`, `BaseLLMClient`,
   `BaseEmbedder`, `BaseRetriever`, `BaseAnalyzer`: trocar implementação sem mexer no resto.
   Composição quando combinar responsabilidades; herança para variações de um contrato.
5. **Degradação graciosa.** Faltou GPS/altitude/cadência (indoor, Hyrox) → `NULL`, sem quebrar.
6. **Processamento offline, pós-treino** (não tempo real) — o pipeline analisa depois da
   sessão. Tempo real é um objetivo só do dispositivo embarcado (futuro).

## Dados

7. **Dado validado, nunca chutado.** Provar unidades e relações nos próprios dados
   (ex.: cadência ×2 provada por distância÷passos; velocidade conferida vs. a sessão).
8. **Idempotência na ingestão** (`garmin_activity_id` UNIQUE) — reprocessar não duplica.
9. **Guardar o dado real do dispositivo** (distância, zonas de FC do Garmin) em vez de estimar.

## IA / LLM

10. **RAG, não fine-tuning** (fine-tuning só como último recurso). Modelo aberto local, sem token.
11. **Conclusão pronta pro LLM.** O código faz cálculos e comparações; o LLM redige.
    Nunca deixar o LLM recalcular se um valor está acima/abaixo de um limiar.
12. **Coach acionável: prescrever, não só descrever.** Sempre dar o "como corrigir",
    não apenas apontar o problema.
13. **Grounding anti-alucinação.** O coach só aconselha com base na evidência recuperada
    + nos dados; cita a fonte; diz "sem evidência suficiente" quando não há (limiar de similaridade).
14. **Fontes citáveis e confiáveis** (é app de risco de lesão). Base curada de literatura real;
    web apenas de domínios confiáveis (PubMed/OMS/NIH) e só como fallback.
15. **Embedder/modelo casado com idioma e domínio** (ex.: bge-m3 multilíngue para português).
16. **Modelos de ML leves o bastante para rodar on-device no futuro** (quando a trilha de ML chegar).

## Processo

17. **Clarificar antes de construir** — quando a decisão é do usuário, perguntar primeiro.
18. **Fatias verticais finas** — provar o fio end-to-end antes de engrossar cada camada.
19. **Ensinar o porquê** — o projeto também é aprendizado; explicar conceitos ao construir.

## Produto & Negócio

20. **Monetização por hardware, sem assinatura obrigatória.**
21. **Norte de longo prazo:** toda decisão deve manter viável o **dispositivo wearable** futuro
    (peitoral/braço na v1; pé/canela como módulo de impacto depois) — kernel Rust genérico
    (séries numéricas, não "dados de Garmin"), schema extensível, firmware embarcado em Rust.
