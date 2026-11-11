"""Adaptador que permite executar a MESMA suíte de testes nas duas versões do AgendaLab.

A versão 1.0 é um único módulo (app.py) e a versão 2.0 é um pacote com fábrica de
aplicação. Este arquivo esconde apenas essas diferenças de inicialização; os casos de
teste são idênticos para as duas versões, o que torna a comparação justa.
"""
import hashlib
import importlib
import os
import re
import sqlite3
import sys
from datetime import date, timedelta

RAIZ = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
PASTAS = {"v1": os.path.join(RAIZ, "v1_antes"), "v2": os.path.join(RAIZ, "v2_depois")}
CREDENCIAIS_ADMIN = {"v1": ("admin", "admin123"), "v2": ("admin", "Admin2026")}
PADRAO_CSRF = re.compile(rb'name="csrf_token" value="([^"]+)"')


class Sistema:
    """Uma instância do AgendaLab (v1 ou v2) com banco de dados próprio."""

    def __init__(self, versao, caminho_banco, configuracao=None):
        self.versao = versao
        self.caminho_banco = caminho_banco
        pasta = PASTAS[versao]
        if pasta not in sys.path:
            sys.path.insert(0, pasta)
        self.credenciais_admin = CREDENCIAIS_ADMIN[versao]
        if versao == "v1":
            self.app = self._iniciar_v1()
        else:
            self.app = self._iniciar_v2(configuracao or {})
        # Em caso de exceção não tratada, devolve "500" como em produção (em vez de interromper o teste)
        self.app.config["PROPAGATE_EXCEPTIONS"] = False

    def _iniciar_v1(self):
        modulo = importlib.import_module("app")
        modulo.DB = self.caminho_banco
        modulo.init_db()  # cria as tabelas e o usuário admin/admin123
        return modulo.app

    def _iniciar_v2(self, configuracao):
        from agendalab import create_app  # pylint: disable=import-outside-toplevel
        app = create_app({"DATABASE": self.caminho_banco, "SECRET_KEY": "chave-de-teste", **configuracao})
        if not self.contar("usuarios", "login = ?", (self.credenciais_admin[0],)):
            self.inserir_usuario("Administrador", *self.credenciais_admin, perfil="admin")
        return app

    # ------------------------------------------------ acesso direto ao banco
    def hash_senha(self, senha):
        """Gera o valor da senha exatamente como cada versão grava no banco."""
        if self.versao == "v1":
            return hashlib.md5(senha.encode(), usedforsecurity=False).hexdigest()
        from werkzeug.security import generate_password_hash  # pylint: disable=import-outside-toplevel
        return generate_password_hash(senha)

    def executar(self, sql, parametros=()):
        """Executa um comando no banco e retorna o id da linha inserida."""
        conexao = sqlite3.connect(self.caminho_banco)
        try:
            cursor = conexao.execute(sql, parametros)
            conexao.commit()
            return cursor.lastrowid
        finally:
            conexao.close()

    def consultar(self, sql, parametros=()):
        """Executa uma consulta e retorna todas as linhas."""
        conexao = sqlite3.connect(self.caminho_banco)
        try:
            return conexao.execute(sql, parametros).fetchall()
        finally:
            conexao.close()

    def contar(self, tabela, condicao="1 = 1", parametros=()):
        """Conta as linhas de uma tabela que atendem à condição."""
        return self.consultar(f"SELECT COUNT(*) FROM {tabela} WHERE {condicao}", parametros)[0][0]

    def inserir_usuario(self, nome, login, senha, perfil="comum"):
        """Cadastra um usuário diretamente no banco (preparação de cenário)."""
        return self.executar("INSERT INTO usuarios (nome, login, senha, perfil) VALUES (?, ?, ?, ?)",
                             (nome, login, self.hash_senha(senha), perfil))

    def inserir_sala(self, nome, capacidade=30, tipo="Laboratório"):
        """Cadastra uma sala diretamente no banco (preparação de cenário)."""
        return self.executar("INSERT INTO salas (nome, capacidade, tipo) VALUES (?, ?, ?)",
                             (nome, capacidade, tipo))

    def inserir_reserva(self, sala_id, usuario_id, data, inicio, fim, motivo="Aula"):
        """Cadastra uma reserva diretamente no banco (preparação de cenário)."""
        return self.executar(
            "INSERT INTO reservas (sala_id, usuario_id, data, hora_inicio, hora_fim, motivo) "
            "VALUES (?, ?, ?, ?, ?, ?)", (sala_id, usuario_id, data, inicio, fim, motivo))


class Navegador:
    """Simula uma pessoa usando o sistema pelo navegador (cliente de teste do Flask)."""

    def __init__(self, sistema):
        self.sistema = sistema
        self.cliente = sistema.app.test_client()

    def abrir(self, url):
        """Abre uma página (GET)."""
        return self.cliente.get(url)

    def enviar(self, url_formulario, dados, url_acao=None):
        """Abre a página do formulário, copia o token CSRF (se existir) e envia os dados."""
        pagina = self.cliente.get(url_formulario)
        token = PADRAO_CSRF.search(pagina.data)
        if token:
            dados = {**dados, "csrf_token": token.group(1).decode()}
        return self.cliente.post(url_acao or url_formulario, data=dados)

    def entrar(self, login, senha):
        """Faz login pelo formulário."""
        return self.enviar("/login", {"login": login, "senha": senha})

    def entrar_como_admin(self):
        """Faz login com o usuário administrador."""
        return self.entrar(*self.sistema.credenciais_admin)

    def cancelar_reserva(self, reserva_id):
        """Clica em "cancelar" em uma reserva."""
        return self.enviar("/reservas/nova", {}, url_acao=f"/reservas/{reserva_id}/excluir")

    def esta_logado(self):
        """Verifica se a sessão atual dá acesso às páginas internas."""
        return self.cliente.get("/reservas").status_code == 200


# ----------------------------------------------------------- datas de apoio
def dia_util(dias_a_frente):
    """Data futura (AAAA-MM-DD) que não cai em um domingo."""
    data = date.today() + timedelta(days=dias_a_frente)
    if data.weekday() == 6:
        data += timedelta(days=1)
    return data.isoformat()


def domingo_futuro():
    """Próximo domingo (pelo menos 1 dia à frente)."""
    data = date.today() + timedelta(days=1)
    while data.weekday() != 6:
        data += timedelta(days=1)
    return data.isoformat()


def data_passada():
    """Data no passado (dia útil mais recente antes de hoje, nunca um domingo)."""
    data = date.today() - timedelta(days=1)
    if data.weekday() == 6:
        data -= timedelta(days=1)
    return data.isoformat()


def dados_de_reserva(sala_id, data=None, inicio="08:00", fim="10:00", motivo="Aula de Banco de Dados"):
    """Dados do formulário de nova reserva."""
    return {"sala_id": str(sala_id), "data": data or dia_util(7), "hora_inicio": inicio,
            "hora_fim": fim, "motivo": motivo}
