CREATE TABLE comandos (
    partida TEXT NOT NULL,
    jogador TEXT NOT NULL,
    id TEXT NOT NULL,
    pedido TEXT NOT NULL,
    resposta JSONB NOT NULL,
    PRIMARY KEY (partida, jogador, id),
    FOREIGN KEY (partida, jogador) REFERENCES jogadores(partida, id) ON DELETE CASCADE
);
CREATE TABLE presencas (
    jogador TEXT PRIMARY KEY REFERENCES jogadores(id) ON DELETE CASCADE,
    vista_em DOUBLE PRECISION NOT NULL,
    x DOUBLE PRECISION NOT NULL,
    z DOUBLE PRECISION NOT NULL
);
CREATE TABLE convites (
    segredo_hash TEXT PRIMARY KEY,
    partida TEXT NOT NULL REFERENCES partidas(codigo) ON DELETE CASCADE,
    expira_em DOUBLE PRECISION NOT NULL
);
