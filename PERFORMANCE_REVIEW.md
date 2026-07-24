# Revisão de performance — caminho vídeo → métricas → coach

**Escopo:** fluxo crítico de análise de forma, não uma auditoria de toda a árvore.
**Método:** leitura estática; os achados abaixo não afirmam uma latência medida.

## Resumo

**0 crítico · 2 alto · 1 médio.** A linguagem do orquestrador não é o gargalo principal: o
trabalho cresce com o número de quadros inferidos, a normalização e a geração inteira do LLM.

## Achados

### Alto — Inferência completa em todos os quadros do vídeo

- **Arquivos:** `stride_vision/src/main.rs:240-243`, `api/form.py:353-360`
- **Categoria:** complexidade / trabalho redundante
- **Confiança:** alta

O loop de vídeo chama `engine.infer(&img)` para cada quadro decodificado. Como o backend padrão é
YOLO de detecção+pose, um clipe maior ou a 60 FPS aumenta linearmente as inferências, mesmo quando
quadros consecutivos quase não mudam. Antes disso, o job ainda normaliza o vídeo inteiro via ffmpeg.

**Correção recomendada:** definir contrato de captura curto e resolução limitada; introduzir
amostragem temporal configurável e validá-la contra os vídeos de referência. O próximo backend deve
usar modo vídeo com tracking, que só reexecuta a detecção pesada quando o rastreio é perdido. Não
trocar Rust por Go: ambos continuariam chamando o mesmo runtime/modelo por quadro.

### Alto — Resposta do coach é serial, sem streaming e sem teto de saída

- **Arquivos:** `analytics/llm.py:20-42`, `api/routers/form.py:105-126`
- **Categoria:** trabalho redundante / latência percebida
- **Confiança:** alta

O cliente envia `stream: false` e seu padrão é `num_predict=-1`. O atleta só recebe o plano depois
que todo o texto foi gerado, embora desvios, risco, exercícios determinísticos e citações já estejam
prontos antes do LLM.

**Correção recomendada:** retornar imediatamente o resultado determinístico após as métricas;
gerar a explicação humana em segundo plano com teto explícito de tokens e streaming (SSE) para
mostrar os primeiros tokens assim que existirem. Manter o modelo aquecido já é parcialmente feito
por `keep_alive=30m`.

### Médio — Fila local de dois workers vira espera sob concorrência

- **Arquivos:** `core/jobs.py:39-78`, `api/form.py:304-305`
- **Categoria:** capacidade limitada
- **Confiança:** alta

`LocalJobQueue` aceita somente dois jobs em execução e oito pendentes. É apropriada para o uso
local atual, mas análises de vídeo são CPU-bound e os usuários passam a esperar antes mesmo do
processamento quando a concorrência crescer.

**Correção recomendada:** manter essa fila local no desenvolvimento; ao hospedar, implementar a
mesma interface com fila persistente e workers de visão isolados, autoscaláveis e com métricas de
tempo de fila/processamento. A API e o coach não devem compartilhar o pool dos workers de vídeo.

## Arquitetura recomendada

1. **Resultado em duas fases:** métricas + plano determinístico primeiro; narrativa do LLM depois,
   por streaming.
2. **Menos trabalho por vídeo:** captura de 10–15 s, 720p, uma pessoa; benchmark de 15 FPS contra
   30 FPS antes de promover a amostragem.
3. **Worker de visão separado:** o binário Rust continua para computação; em produção, réplicas
   dedicadas consomem jobs, sem bloquear API/LLM.
4. **Novo modelo só com runtime sustentável:** MediaPipe/LiteRT pode reduzir trabalho por tracking,
   mas sua integração nativa ainda requer runtime C++/LiteRT ou execução on-device. Não fingir que
   uma troca de linguagem elimina custo de inferência.

## Fora de escopo

Não foram medidos p50/p95, uso de CPU/GPU, custo de ffmpeg, upload ou tokens/s do Ollama. Antes de
alterar a arquitetura, instrumentar cada estágio e testar em desktop, iPhone e Android intermediário.

## Validação local — 24 jul 2026

Esta seção complementa, mas não substitui, os achados estáticos acima. As execuções foram
**sequenciais**, no mesmo MacBook, com `--no-overlay`, sobre os dois vídeos de celular do projeto.
Não são benchmark de produção nem medida de p95.

| Backend | Vídeo | Quadros | Tempo do motor | Vazão |
| --- | --- | ---: | ---: | ---: |
| BlazePose33 | `laisa_correndo.mp4` | 1005 | 16,6 s | 60,7 FPS |
| BlazePose33 | `video_corrida_23.mp4` | 694 | 11,4 s | 60,7 FPS |
| YOLO17 | `laisa_correndo.mp4` | 1005 | 20,3 s | 49,5 FPS |
| YOLO17 | `video_corrida_23.mp4` | 694 | 13,9 s | 49,9 FPS |

**Gargalo inicial confirmado:** inferência de pose quadro a quadro. O Blaze processou esses
arquivos a cerca de 1,9× a velocidade do vídeo e aproximadamente 23% mais rápido que o YOLO
nessa máquina. Portanto, trocar o orquestrador Python ou Rust por outra linguagem não é a ação
que reduz a espera percebida.

Um perfil posterior pela rota segura da API, na Laisa, separou aproximadamente **3,0 s de
normalização ffmpeg** e **17,8 s de inferência BlazePose** (20,8 s no total, sem overlay). A
inferência representou cerca de 86% da passagem. O próximo ganho deve atacar trabalho do modelo
(tracking/amostragem validada ou capacidade de workers), não uma troca de linguagem.

**Custo restante a instrumentar:** o upload é normalizado por ffmpeg e, para capturas confiáveis,
o produto executa uma segunda passagem de pose para desenhar o overlay. A arquitetura A2 já deixa
as métricas disponíveis antes dessa passagem; ela não elimina o custo total de CPU. O próximo
incremento seguro é instrumentar durações de normalização, métricas, fila e overlay por análise;
qualquer amostragem temporal deve passar antes pelo gate de equivalência biomecânica.

### Implementado — telemetria por estágio

`form_analyses.processing_report` agora guarda, internamente, a duração da passagem de métricas e
do overlay, **separando normalização ffmpeg de inferência Rust** no caminho real, além do status de
shadow quando configurado. O JSON não contém vídeo, paths, tokens, identidade do atleta nem métricas
biomecânicas, e não é exposto nos endpoints do produto. A próxima decisão de capacidade deve usar
uma amostra de análises reais para comparar os percentis desses estágios; só então faz sentido decidir
entre reduzir overlay, amostrar frames ou escalar workers.
