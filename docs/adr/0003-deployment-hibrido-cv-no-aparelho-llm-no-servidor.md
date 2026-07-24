# ADR 0003 — Deployment híbrido: CV/vídeo no aparelho, LLM no nosso servidor (sobre os números)

- **Status:** proposto (jul/2026). Decide a arquitetura de PUBLICAÇÃO, não a implementação de hoje.
- **Escopo:** onde cada peça roda quando o produto for comercial. Depende do ADR 0002 (BlazePose
  Apache, on-device) e da revisão de performance.

## Contexto

O código de hoje é um **web app de servidor** (o dev roda tudo numa máquina: frontend + FastAPI +
motor Rust + Ollama). "100% no aparelho" hoje significa "na máquina do dev". Publicar exige decidir
**onde a IA roda** — e num app de LESÃO o dado é de saúde (vídeo do corpo, biomecânica, histórico
de lesão), então privacidade não é detalhe.

Confusão a desfazer: **"nuvem" tem dois sentidos.** Mandar o dado pro "cérebro" de uma **API de LLM
de terceiros** (DeepSeek/OpenAI/Kimi de nuvem) é o problema — o dado vai pra máquina de outro. Rodar
a **nossa própria** inferência no **nosso** servidor é SaaS normal. Não são a mesma coisa.

## Decisão

Adotar o modelo **HÍBRIDO**, peça por peça:

| Peça | Onde roda | Por quê |
|---|---|---|
| **Pose (CV) + vídeo** | **No aparelho** (BlazePose/MediaPipe nativo) | O vídeo NUNCA sai do celular (privacidade) + custo de servidor ~zero na parte pesada. É pra isso que o BlazePose (Apache, on-device) existe — ADR 0002. |
| **Métricas + risco** | **No aparelho** (determinístico, barato) | Cadência/ângulos/score são Python/aritmética leve; não precisam de servidor. |
| **RAG + LLM (explicação)** | **Nosso servidor** (não API de terceiros) | Recebe só os NÚMEROS derivados (texto minúsculo), nunca o vídeo. LLM controlável/atualizável, corpus RAG central. |

**Regra de ouro:** sobe pro servidor apenas o **resultado estruturado** (métricas, fatores de risco).
O **vídeo e a biometria bruta ficam no aparelho.** O servidor nunca vê a imagem do atleta.

## Alternativas consideradas

1. **Tudo no servidor (o código de hoje):** faz upload do vídeo. Simples de operar/atualizar, mas
   (a) o vídeo de saúde sai do aparelho, (b) custo de CV por usuário no servidor (GPU/CPU). Bom pro
   dev, ruim pra privacidade e custo em escala.
2. **Tudo no aparelho (LLM incluso):** máxima privacidade e zero servidor, mas um LLM 7B no celular é
   pesado (bateria, memória, precisa de modelo pequeno/quantizado). O LLM é a peça MENOS crítica (só
   redige fatos já decididos), então prendê-lo no aparelho custa mais do que rende.
3. **API de LLM de terceiros (DeepSeek/Kimi nuvem):** rejeitado — dado de saúde na máquina de outro +
   custo por inferência + dependência. Contradiz o produto.

## Consequências

- **Migração real (não de graça):** portar o motor Rust + a ponte BlazePose pra rodar no app
  (iOS/Android), e o backend virar "recebe números → RAG + LLM". O contrato `PoseBackend` +
  `JobQueue` + `BaseLLMClient` já isolam as fronteiras, mas o empacotamento mobile é trabalho.
- **Degradação graciosa:** o resultado DETERMINÍSTICO (métricas + risco + exercícios citados) já é
  útil **sem** o LLM. Se o servidor cair, o app ainda entrega o essencial no aparelho; a explicação
  humana é polimento (fallback barato).
- **Custo:** a peça cara em servidor vira só o LLM, e sobre TEXTO (não vídeo) — leve; dá pra começar
  com LLM pequeno e escalar. A CV, que é o gargalo, sai do servidor.
- **Sem taxa de licença por usuário:** BlazePose Apache-2.0 no aparelho (ADR 0002); preservar
  LICENSE/NOTICE.
- **On-device pede inferência otimizada** (celular é fraco): ver "Otimização de inferência" no
  AI-STRATEGY / a fila de trabalho (tracking, subamostragem de frames, modelo Lite/quantizado).

## Ainda em aberto (decidir no build mobile)
- LLM: modelo pequeno on-device vs. nosso servidor — decidir por custo/UX (o híbrido permite os dois).
- Empacotamento do runtime BlazePose por plataforma (macOS/Linux servidor hoje; iOS/Android depois).
- Atualização do corpus RAG (central no servidor) vs. cache no aparelho.
