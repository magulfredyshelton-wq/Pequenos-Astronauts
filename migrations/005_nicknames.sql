ALTER TABLE contas ADD COLUMN nickname TEXT COLLATE "C" UNIQUE
    CHECK (nickname IS NULL OR nickname ~ '^[a-z0-9][a-z0-9_]{2,19}$');
