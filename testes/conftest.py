"""Configuração do pytest: escolha da versão testada e cenários reutilizáveis (fixtures).

Uso:
    python -m pytest testes --versao=v1     testa a versão 1.0 (antes)
    python -m pytest testes --versao=v2     testa a versão 2.0 (depois)
"""
import os
import sys

import pytest

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from sistema import Navegador, Sistema  # noqa: E402  pylint: disable=wrong-import-position


def pytest_addoption(parser):
    """Adiciona a opção --versao ao pytest."""
    parser.addoption("--versao", default="v2", choices=("v1", "v2"),
                     help="Versão do AgendaLab a testar (v1 = antes, v2 = depois)")


def pytest_report_header(config):
    """Mostra no cabeçalho do relatório qual versão está sendo testada."""
    return f"AgendaLab - versão testada: {config.getoption('--versao')}"


@pytest.fixture
def sistema(request, tmp_path):
    """Sistema novo, com banco de dados vazio, para cada teste."""
    return Sistema(request.config.getoption("--versao"), str(tmp_path / "teste.db"))


@pytest.fixture
def navegador(sistema):
    """Um "navegador" ainda sem login."""
    return Navegador(sistema)


@pytest.fixture
def usuario_comum(sistema):
    """Usuária comum já cadastrada."""
    senha = "Senha123"
    usuario_id = sistema.inserir_usuario("Maria Souza", "maria", senha)
    return {"id": usuario_id, "login": "maria", "senha": senha}


@pytest.fixture
def sala(sistema):
    """Sala já cadastrada; devolve o id."""
    return sistema.inserir_sala("Laboratório 1", 30, "Laboratório")


@pytest.fixture
def logado(navegador, usuario_comum):
    """Navegador com a usuária comum já autenticada."""
    navegador.entrar(usuario_comum["login"], usuario_comum["senha"])
    return navegador


@pytest.fixture
def admin_logado(navegador):
    """Navegador com o administrador já autenticado."""
    navegador.entrar_como_admin()
    return navegador
