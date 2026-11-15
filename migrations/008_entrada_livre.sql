-- Entrada livre: o jogador indica só nome e idade. Sai tudo o que era email, palavra-passe e autorização.
DROP TABLE IF EXISTS verificacoes_email;
DROP TABLE IF EXISTS consentimentos;
ALTER TABLE contas DROP COLUMN email;
ALTER TABLE contas DROP COLUMN senha_salt;
ALTER TABLE contas DROP COLUMN senha_hash;
ALTER TABLE contas DROP COLUMN consentimento_em;
