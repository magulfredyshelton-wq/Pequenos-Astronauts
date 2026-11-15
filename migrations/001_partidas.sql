CREATE TABLE partidas (
    codigo TEXT PRIMARY KEY,
    revisao BIGINT NOT NULL CHECK (revisao >= 0),
    estado JSONB NOT NULL,
    criada_em TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP
);
CREATE TABLE jogadores (
    id TEXT PRIMARY KEY,
    partida TEXT NOT NULL REFERENCES partidas(codigo) ON DELETE CASCADE,
    nome TEXT NOT NULL,
    nivel TEXT NOT NULL CHECK (nivel IN ('cadete','piloto','comandante')),
    segredo_hash TEXT NOT NULL UNIQUE,
    anfitriao INTEGER NOT NULL CHECK (anfitriao IN (0,1)),
    UNIQUE (partida, id)
);
CREATE UNIQUE INDEX anfitriao_unico ON jogadores(partida) WHERE anfitriao = 1;
CREATE INDEX jogadores_partida ON jogadores(partida);
