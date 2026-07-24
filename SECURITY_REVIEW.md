# Revisão de segurança — StriderEdge OS

**Escopo:** repositório inteiro em 21 jul. 2026, incluindo mudanças não commitadas em
`api/routers/` e autorização de análises. Esta é uma revisão de código e configuração local;
não inclui pentest, infraestrutura de deploy nem varredura de CVEs.

## Resumo

**Achados iniciais: 0 críticos, 3 altos, 3 médios e 2 baixos.** As correções abaixo foram
implementadas no worktree atual e validadas por 158 testes Python, typecheck e build web.

## Estado após a remediação

- **H-01 resolvido:** classificação agora recebe o atleta autenticado e aplica `id + user_id` no
  `SELECT` e `UPDATE`; há teste de acesso cruzado.
- **H-02 mitigado no app:** upload é copiado por chunks, há rejeição antecipada por tamanho,
  staging é limpo e a fila local é limitada com resposta `503`. Rate limit por peer limita
  convidados e atletas. Ainda é necessário impor limite de corpo/quota também no proxy de produção.
- **H-03 resolvido no caminho de treinamento:** relatos entram como `training_approved=false` e
  não viram positivos nem negativos até aprovação administrativa explícita.
- **M-01 resolvido:** segredo, bancos/WAL e log recebem `0600`; `storage` recebe `0700` no boot.
- **M-02 resolvido:** e-mail inexistente executa PBKDF2 dummy de 600 mil iterações.
- **M-03 mitigado:** cadastro, login, Google e upload têm janela deslizante em memória e `429`.
  Um limite distribuído no edge continua necessário quando houver múltiplos processos/instâncias.
- **L-01 resolvido:** capability de convidado expira em sete dias e o boot remove análises vencidas.
- **L-02 mitigado:** bearer mudou para `sessionStorage`, TTL caiu para 24 horas e a API emite
  cabeçalhos de segurança. A CSP da SPA em produção ainda pertence ao servidor estático/proxy.

## Achados altos

### H-01 — Usuário autenticado pode classificar e ler a lesão de outro atleta

- **Categoria:** controle de acesso quebrado (IDOR)
- **Confiança:** alta
- **Arquivos:** `api/routers/injuries.py:53-64`, `api/injuries.py:58-82`

O endpoint valida que existe uma sessão, mas descarta o `user_id` retornado. Em seguida,
`InjuryService.classify()` busca e atualiza apenas por `injury_id`. Assim, um usuário que obtiver
o UUID de uma lesão alheia pode disparar a classificação, receber de volta sintomas, notas e
respostas OSTRC da vítima, e alterar o diagnóstico persistido.

**Correção recomendada:** passar o usuário autenticado para o serviço e consultar com
`WHERE id = ? AND user_id = ?`. Repetir o predicado no `UPDATE`, devolver 404 genérico em caso de
não pertencimento e adicionar um teste com dois atletas que confirme que a lesão da vítima não é
lida nem alterada.

### H-02 — Upload público permite exaurir RAM, disco e fila de processamento

- **Categoria:** negação de serviço / validação de entrada
- **Confiança:** alta
- **Arquivos:** `api/routers/form.py:26-50`, `api/form.py:89-115`, `core/jobs.py:47-74`

O upload aceita convidados, lê os dois arquivos inteiros para memória antes de testar o limite
combinado de 300 MB e persiste os bytes antes de enfileirar o processamento. A `Queue` não tem
`maxsize`; limitar dois workers só limita consumo, não admissão. Um atacante pode acumular uploads,
arquivos e jobs caros de ffmpeg/ONNX até esgotar RAM, disco ou disponibilidade. Em falhas finais,
os originais também não recebem limpeza programada.

**Correção recomendada:** rejeitar pelo tamanho no edge/ASGI e copiar `UploadFile` por chunks,
contando antes de persistir; aplicar quotas por IP/usuário e limite diário de jobs; usar fila
limitada que responda 429/503 quando cheia; definir retenção e limpeza para arquivos de falha.
Antes de expor o endpoint, exigir conta verificada ou uma defesa antiabuso equivalente para
uploads de convidados.

### H-03 — Outcomes auto-relatados contaminam o modelo global de risco

- **Categoria:** integridade de dados / envenenamento de modelo
- **Confiança:** alta
- **Arquivos:** `api/routers/injuries.py:42-50`, `analytics/injury_dataset.py:65-118`,
  `analytics/risk_assessor.py:25-49`

Qualquer conta recém-criada pode registrar diagnósticos válidos, onset e respostas OSTRC. Esses
registros passam a ser "casos reais" para o prior Bayesiano; ao atingir os limiares, passam a
treinar o Random Forest global. Não há verificação de conta, proveniência, revisão, limite por
atleta ou estado de aprovação. Contas descartáveis podem portanto deslocar recomendações dadas a
outros atletas.

**Correção recomendada:** separar coleta de treinamento: guardar proveniência e estado
`pending/verified/rejected`, treinar somente com outcomes aprovados, limitar contribuição por
atleta e detectar duplicatas/outliers. Versionar o dataset/modelo aprovado em job auditável, com
rollback, em vez de atualizar a decisão global com dados recém-enviados.

## Achados médios

### M-01 — Segredo HMAC e dados de saúde têm permissões locais amplas

- **Categoria:** proteção de segredos
- **Confiança:** alta
- **Arquivos:** `api/auth.py:76-83`, `core/database.py:42-48`, `core/logging.py:25-46`

Na árvore revisada, `storage/` está em `0755` e `.auth_secret`, os dois bancos DuckDB e o log
estão em `0644`. Outro usuário local pode ler o segredo HMAC, emitir sessões válidas, ou copiar
dados de conta, lesão e análise.

**Correção recomendada:** criar `storage/` em `0700` e arquivos sensíveis em `0600`; corrigir
permissões já existentes no boot. Em produção, carregar a chave de um secret manager ou variável
de ambiente e recusar inicialização quando ela estiver ausente ou insegura.

### M-02 — Login permite enumeração temporal de e-mails

- **Categoria:** autenticação
- **Confiança:** alta
- **Arquivos:** `api/auth.py:53-62`, `api/auth.py:146-155`

Apesar da mensagem uniforme, `PasswordHasher.verify()` retorna imediatamente quando não existe
hash. Para e-mail existente, há PBKDF2 de 600 mil iterações; para inexistente, não há derivação.
Medições repetidas permitem inferir quais e-mails possuem conta.

**Correção recomendada:** usar um hash PBKDF2 dummy válido e sempre chamar `verify()` com
`row[2] if row else DUMMY_HASH`. Testar que a derivação ocorre nos dois ramos.

### M-03 — Endpoints de autenticação não possuem proteção contra abuso

- **Categoria:** autenticação / abuso de API
- **Confiança:** alta
- **Arquivos:** `api/routers/auth.py:28-42`, `api/auth.py:131-155`

`register`, `login` e `google` não possuem rate limit, backoff, bloqueio temporário ou controle
de criação de contas. Isso permite credential stuffing e também DoS de CPU, pois cada tentativa
contra e-mail existente executa PBKDF2 caro.

**Correção recomendada:** aplicar rate limit no edge por IP e por e-mail normalizado, com backoff;
limitar criação de contas e registrar abuso. Para exposição pública, acrescentar verificação de
e-mail e desafio anti-bot quando necessário.

## Achados baixos

### L-01 — Capabilities de análises de convidados não expiram nem podem ser revogadas

- **Categoria:** controle de acesso / defesa em profundidade
- **Confiança:** alta
- **Arquivos:** `api/form.py:103-119`, `api/form.py:227-243`,
  `db/migrations/019_form_analysis_access.sql`

A capability tem boa entropia, é enviada apenas em header e somente seu hash é persistido — todos
pontos positivos. Contudo ela permanece válida enquanto a linha de análise existir, sem expiração
ou revogação. Se vazar em dispositivo compartilhado, extensão maliciosa ou captura de tráfego sem
TLS, dá acesso contínuo ao vídeo e às métricas do convidado.

**Correção recomendada:** adicionar expiração e um identificador de revogação à análise; comparar
o token somente enquanto estiver válido e apagar análises de convidados após retenção definida.

### L-02 — Bearer token de conta persiste em `localStorage`

- **Categoria:** defesa em profundidade / XSS
- **Confiança:** baixa
- **Arquivos:** `frontend/packages/core/src/api/client.ts:34-40`, `api/auth.py:72`

Não encontrei sinks diretos de XSS (`innerHTML`, `dangerouslySetInnerHTML` ou `eval`) e React
escapa o conteúdo renderizado. Mesmo assim, um XSS futuro ou script de terceiro comprometido pode
ler um bearer token válido por até sete dias.

**Correção recomendada:** manter CSP restritiva e minimizar scripts de terceiros; reduzir a vida
do access token. Avaliar token de acesso em memória e refresh token `HttpOnly; Secure; SameSite`
se a arquitetura aceitar a proteção CSRF adicional. Este achado deixa de ter efeito prático se não
houver XSS nem scripts não confiáveis, mas é uma defesa preventiva.

## Aspectos verificados sem achado

- A autorização de **análises de forma** foi corrigida no worktree atual: listagem exige sessão;
  leitura, vídeo, coach, tênis e plano exigem dono autenticado ou capability de convidado; o DTO
  não expõe mais `video_path`.
- Consultas DuckDB influenciadas por HTTP usam parâmetros. Os trechos interpolados são listas
  internas de colunas/placeholders, não valores do usuário.
- ffmpeg e o motor Rust usam listas de argumentos, sem shell; caminhos de processamento nascem de
  UUIDs gerados no servidor. Não confirmei injeção de comando ou path traversal.
- Não há SSRF com URL controlada por usuário: Google e Ollama usam destinos fixos/configurados.
- Não encontrei desserialização insegura (`pickle`, YAML inseguro ou `eval`) nem formato conhecido
  de segredo exposto pelo pré-scan.
- CSRF não é vetor primário: operações autenticadas usam `Authorization`, não cookies. CORS está
  limitado às origens locais de desenvolvimento.

## Cobertura do scan

O pré-scan estrutural encontrou **207 arquivos** revisáveis e **0** formatos conhecidos de segredo.
Foram excluídos **186 binários**, **2 lockfiles** e **435 arquivos ignorados pelo Git**. A revisão
cobriu API, auth, banco/migrations, fila, RAG/LLM, Rust, frontend, testes e configuração. Binários
e bancos não foram descompilados nem tiveram conteúdo pessoal extraído.

Não foi fornecido `api.ir.json` ou `RFC_REVIEW.md`; portanto não há seção de drift
RFC/implementação.

## Próximos passos recomendados

1. Corrigir H-01 antes de liberar a classificação de lesões.
2. Corrigir H-02 e M-03 antes de expor upload ou autenticação à internet.
3. Isolar H-03 antes de usar o Bayes/RF para orientar usuários reais.
4. Fazer varredura atualizada de dependências com `pip-audit`/OSV e `npm audit` antes de deploy.
5. Revisar infraestrutura de produção: TLS, proxy com limite de corpo, sandbox de ffmpeg/ONNX,
   `TrustedHostMiddleware`, headers de segurança, backup, retenção e LGPD.
