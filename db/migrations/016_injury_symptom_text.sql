-- 016: reframe do log de lesão — o atleta não auto-diagnostica (não somos médicos + gera rótulo
-- lixo). A região vem do MAPA CORPORAL (verdade estruturada); o diagnóstico deixa de ser um picker
-- obrigatório e vira TEXTO LIVRE opcional (o que o atleta sente, ou o laudo do médico). Esse texto
-- alimenta o coach como CONTEXTO e é candidato a rótulo via classificador LLM em coach-time —
-- quando mapeia num termo da taxonomia, preenche `diagnosis`; senão fica NULL (o guardrail de
-- build_dataset já barra rótulo não-mapeado). region continua sendo o `y` confiável.
ALTER TABLE injury_reports ADD COLUMN IF NOT EXISTS symptom_text TEXT;
