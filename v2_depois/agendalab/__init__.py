"""AgendaLab 2.0: sistema de reserva de salas e laboratórios.

Este módulo contém a fábrica da aplicação (padrão *application factory*),
que monta a aplicação Flask a partir de módulos menores e independentes.
"""
import os
import secrets

from flask import Flask

from . import db
from .erros import registrar_tratadores_de_erro
from .rotas_auth import bp as bp_auth
from .rotas_relatorio import bp as bp_relatorio
from .rotas_reservas import bp as bp_reservas
from .rotas_salas import bp as bp_salas
from .seguranca import aplicar_cabecalhos_seguranca, token_csrf, validar_csrf
from .validacao import formatar_data_br, formatar_numero_br


def create_app(configuracao=None):
    """Cria e configura uma instância da aplicação."""
    app = Flask(__name__, instance_relative_config=True)
    app.config.from_mapping(
        SECRET_KEY=os.environ.get("AGENDALAB_SECRET_KEY") or secrets.token_hex(32),
        DATABASE=os.path.join(app.instance_path, "agendalab.db"),
        POR_PAGINA=50,
        SESSION_COOKIE_HTTPONLY=True,
        SESSION_COOKIE_SAMESITE="Lax",
        SESSION_COOKIE_SECURE=os.environ.get("AGENDALAB_COOKIE_SEGURO") == "1",
        MAX_CONTENT_LENGTH=64 * 1024,
    )
    if configuracao:
        app.config.update(configuracao)
    os.makedirs(os.path.dirname(os.path.abspath(app.config["DATABASE"])), exist_ok=True)

    db.init_app(app)
    app.before_request(validar_csrf)
    app.after_request(aplicar_cabecalhos_seguranca)
    app.jinja_env.globals["csrf_token"] = token_csrf
    app.jinja_env.filters["data_br"] = formatar_data_br
    app.jinja_env.filters["numero_br"] = formatar_numero_br

    for blueprint in (bp_auth, bp_reservas, bp_salas, bp_relatorio):
        app.register_blueprint(blueprint)
    registrar_tratadores_de_erro(app)
    return app
