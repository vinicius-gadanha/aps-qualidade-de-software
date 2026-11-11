-- Esquema do banco de dados do AgendaLab 2.0
CREATE TABLE IF NOT EXISTS usuarios (
    id      INTEGER PRIMARY KEY AUTOINCREMENT,
    nome    TEXT NOT NULL,
    login   TEXT NOT NULL UNIQUE,
    senha   TEXT NOT NULL,               -- hash com sal (PBKDF2/scrypt), nunca a senha em texto puro
    perfil  TEXT NOT NULL DEFAULT 'comum' CHECK (perfil IN ('comum', 'admin'))
);

CREATE TABLE IF NOT EXISTS salas (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    nome        TEXT NOT NULL UNIQUE,
    capacidade  INTEGER NOT NULL CHECK (capacidade > 0),
    tipo        TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS reservas (
    id           INTEGER PRIMARY KEY AUTOINCREMENT,
    sala_id      INTEGER NOT NULL REFERENCES salas (id),
    usuario_id   INTEGER NOT NULL REFERENCES usuarios (id),
    data         TEXT NOT NULL,          -- formato AAAA-MM-DD
    hora_inicio  TEXT NOT NULL,          -- formato HH:MM
    hora_fim     TEXT NOT NULL,          -- formato HH:MM
    motivo       TEXT NOT NULL,
    criado_em    TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    CHECK (hora_fim > hora_inicio)
);

-- Indices para as consultas mais frequentes (listagem, busca por data e verificacao de conflito)
CREATE INDEX IF NOT EXISTS idx_reservas_data ON reservas (data, hora_inicio);
CREATE INDEX IF NOT EXISTS idx_reservas_sala_data ON reservas (sala_id, data);
