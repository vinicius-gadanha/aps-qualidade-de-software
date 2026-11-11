"""Consultas ao banco de dados. Todas usam parâmetros (?) para evitar injeção de SQL."""
from .db import obter_conexao

CONSULTA_RESERVAS = """
    SELECT r.id, r.data, r.hora_inicio, r.hora_fim, r.motivo, r.usuario_id,
           s.nome AS sala, u.nome AS usuario
      FROM reservas r
      JOIN salas s ON s.id = r.sala_id
      JOIN usuarios u ON u.id = r.usuario_id
"""


# ---------------------------------------------------------------- usuários
def buscar_usuario_por_id(usuario_id):
    """Retorna o usuário com o id informado (ou None)."""
    return obter_conexao().execute(
        "SELECT id, nome, login, perfil FROM usuarios WHERE id = ?", (usuario_id,)
    ).fetchone()


def buscar_usuario_por_login(login):
    """Retorna o usuário (incluindo o hash da senha) pelo login (ou None)."""
    return obter_conexao().execute(
        "SELECT id, nome, login, senha, perfil FROM usuarios WHERE login = ?", (login,)
    ).fetchone()


def criar_usuario(nome, login, senha_hash, perfil="comum"):
    """Insere um usuário. Lança sqlite3.IntegrityError se o login já existir."""
    conexao = obter_conexao()
    cursor = conexao.execute(
        "INSERT INTO usuarios (nome, login, senha, perfil) VALUES (?, ?, ?, ?)",
        (nome, login, senha_hash, perfil),
    )
    conexao.commit()
    return cursor.lastrowid


def existe_admin():
    """Indica se já existe ao menos um administrador cadastrado."""
    return obter_conexao().execute(
        "SELECT 1 FROM usuarios WHERE perfil = 'admin' LIMIT 1"
    ).fetchone() is not None


# ------------------------------------------------------------------- salas
def listar_salas():
    """Lista todas as salas em ordem alfabética."""
    return obter_conexao().execute(
        "SELECT id, nome, capacidade, tipo FROM salas ORDER BY nome"
    ).fetchall()


def buscar_sala(sala_id):
    """Retorna a sala com o id informado (ou None)."""
    return obter_conexao().execute(
        "SELECT id, nome, capacidade, tipo FROM salas WHERE id = ?", (sala_id,)
    ).fetchone()


def criar_sala(nome, capacidade, tipo):
    """Insere uma sala. Lança sqlite3.IntegrityError se o nome já existir."""
    conexao = obter_conexao()
    conexao.execute(
        "INSERT INTO salas (nome, capacidade, tipo) VALUES (?, ?, ?)", (nome, capacidade, tipo)
    )
    conexao.commit()


# ---------------------------------------------------------------- reservas
def contar_reservas(data=None):
    """Conta as reservas (opcionalmente apenas de uma data)."""
    if data:
        sql, parametros = "SELECT COUNT(*) FROM reservas WHERE data = ?", (data,)
    else:
        sql, parametros = "SELECT COUNT(*) FROM reservas", ()
    return obter_conexao().execute(sql, parametros).fetchone()[0]


def listar_reservas(data=None, limite=50, deslocamento=0):
    """Lista uma página de reservas com os nomes da sala e do usuário (uma única consulta)."""
    filtro, parametros = ("WHERE r.data = ?", [data]) if data else ("", [])
    sql = CONSULTA_RESERVAS + filtro + " ORDER BY r.data, r.hora_inicio, s.nome LIMIT ? OFFSET ?"
    return obter_conexao().execute(sql, parametros + [limite, deslocamento]).fetchall()


def buscar_reserva(reserva_id):
    """Retorna a reserva com o id informado (ou None)."""
    return obter_conexao().execute(
        "SELECT id, usuario_id FROM reservas WHERE id = ?", (reserva_id,)
    ).fetchone()


def criar_reserva_sem_conflito(dados, usuario_id):
    """Insere a reserva se não houver conflito de horário na mesma sala.

    A verificação e a inserção ocorrem na mesma transação (BEGIN IMMEDIATE),
    evitando que duas requisições simultâneas reservem o mesmo horário.
    Retorna True se a reserva foi criada e False se havia conflito.
    """
    conexao = obter_conexao()
    conexao.execute("BEGIN IMMEDIATE")
    with conexao:  # confirma a transação ao final ou desfaz em caso de erro
        conflito = conexao.execute(
            "SELECT 1 FROM reservas WHERE sala_id = ? AND data = ? "
            "AND hora_inicio < ? AND hora_fim > ? LIMIT 1",
            (dados["sala_id"], dados["data"], dados["hora_fim"], dados["hora_inicio"]),
        ).fetchone()
        if conflito:
            return False
        conexao.execute(
            "INSERT INTO reservas (sala_id, usuario_id, data, hora_inicio, hora_fim, motivo) "
            "VALUES (?, ?, ?, ?, ?, ?)",
            (dados["sala_id"], usuario_id, dados["data"], dados["hora_inicio"],
             dados["hora_fim"], dados["motivo"]),
        )
    return True


def excluir_reserva(reserva_id):
    """Remove a reserva informada."""
    conexao = obter_conexao()
    conexao.execute("DELETE FROM reservas WHERE id = ?", (reserva_id,))
    conexao.commit()


def minutos_reservados_por_sala(primeiro_dia, dia_seguinte_ao_ultimo):
    """Soma, por sala, a quantidade e os minutos de reservas no período (consulta agregada)."""
    return obter_conexao().execute(
        """
        SELECT s.nome AS sala,
               COUNT(r.id) AS total,
               COALESCE(SUM((strftime('%s', r.hora_fim) - strftime('%s', r.hora_inicio)) / 60), 0)
                   AS minutos
          FROM salas s
          LEFT JOIN reservas r
                 ON r.sala_id = s.id AND r.data >= ? AND r.data < ?
         GROUP BY s.id
         ORDER BY s.nome
        """,
        (primeiro_dia, dia_seguinte_ao_ultimo),
    ).fetchall()
