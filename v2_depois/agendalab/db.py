"""Acesso ao banco de dados SQLite (uma conexão por requisição)."""
import sqlite3

from flask import current_app, g


def obter_conexao():
    """Retorna a conexão da requisição atual, abrindo-a se necessário."""
    if "db" not in g:
        g.db = sqlite3.connect(current_app.config["DATABASE"])
        g.db.row_factory = sqlite3.Row
        g.db.execute("PRAGMA foreign_keys = ON")
    return g.db


def fechar_conexao(_erro=None):
    """Fecha a conexão ao final da requisição."""
    conexao = g.pop("db", None)
    if conexao is not None:
        conexao.close()


def criar_tabelas():
    """Cria as tabelas e índices definidos em schema.sql (se ainda não existirem)."""
    conexao = obter_conexao()
    with current_app.open_resource("schema.sql") as arquivo:
        conexao.executescript(arquivo.read().decode("utf-8"))
    conexao.commit()


def init_app(app):
    """Registra o fechamento automático da conexão e prepara o banco."""
    app.teardown_appcontext(fechar_conexao)
    with app.app_context():
        criar_tabelas()
