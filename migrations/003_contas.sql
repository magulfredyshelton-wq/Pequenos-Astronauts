CREATE TABLE contas (
    id TEXT PRIMARY KEY,
    email TEXT NOT NULL UNIQUE,
    nome TEXT NOT NULL,
    idade INTEGER NOT NULL CHECK (idade BETWEEN 8 AND 120),
    senha_salt TEXT NOT NULL,
    senha_hash TEXT NOT NULL,
    confirmada_em BIGINT NOT NULL
);
CREATE TABLE verificacoes_email (
    email TEXT PRIMARY KEY,
    codigo_hash TEXT NOT NULL UNIQUE,
    expira_em BIGINT NOT NULL,
    criada_em BIGINT NOT NULL
);
CREATE TABLE sessoes_conta (
    token_hash TEXT PRIMARY KEY,
    conta TEXT NOT NULL REFERENCES contas(id) ON DELETE CASCADE,
    expira_em BIGINT NOT NULL
);
CREATE INDEX sessoes_conta_id ON sessoes_conta(conta);
ALTER TABLE jogadores ADD COLUMN conta_id TEXT REFERENCES contas(id);
CREATE UNIQUE INDEX jogadores_conta_partida ON jogadores(conta_id, partida) WHERE conta_id IS NOT NULL;
