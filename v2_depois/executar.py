"""Executa o AgendaLab 2.0 localmente.

Uso:
    python executar.py           inicia o sistema em http://127.0.0.1:5000
    python executar.py --demo    inicia e, se o banco estiver vazio, cadastra salas de exemplo

Na primeira execução o programa pede a senha do usuário "admin".
"""
import getpass
import os
import sys

from werkzeug.security import generate_password_hash

from agendalab import create_app, repositorio
from agendalab.validacao import erros_da_senha

SALAS_DE_EXEMPLO = (
    ("Laboratório 1", 30, "Laboratório"),
    ("Laboratório 2", 25, "Laboratório"),
    ("Sala 101", 45, "Sala de aula"),
    ("Auditório", 120, "Auditório"),
)


def pedir_senha_do_admin():
    """Pede (e confirma) a senha do administrador no terminal."""
    while True:
        senha = getpass.getpass("Defina a senha do usuário 'admin': ")
        erros = erros_da_senha(senha, getpass.getpass("Confirme a senha: "))
        if not erros:
            return senha
        for erro in erros:
            print(" -", erro)


def preparar_banco(app, demo):
    """Cria o administrador (se ainda não existir) e, opcionalmente, salas de exemplo."""
    with app.app_context():
        if not repositorio.existe_admin():
            print("Nenhum administrador cadastrado. Vamos criar o usuário 'admin'.")
            senha = pedir_senha_do_admin()
            senha_protegida = generate_password_hash(senha)
            repositorio.criar_usuario("Administrador", "admin", senha_protegida, "admin")
        if demo and not repositorio.listar_salas():
            for nome, capacidade, tipo in SALAS_DE_EXEMPLO:
                repositorio.criar_sala(nome, capacidade, tipo)


if __name__ == "__main__":
    aplicacao = create_app()
    preparar_banco(aplicacao, demo="--demo" in sys.argv)
    aplicacao.run(host="127.0.0.1", port=int(os.environ.get("PORT", "5000")), debug=False)
