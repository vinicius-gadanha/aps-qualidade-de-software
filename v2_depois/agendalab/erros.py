"""Páginas de erro amigáveis, com o código HTTP correto."""
from flask import render_template
from werkzeug.exceptions import BadRequest, HTTPException, InternalServerError

MENSAGENS = {
    400: "Não foi possível processar os dados enviados.",
    403: "Você não tem permissão para acessar esta página.",
    404: "Página não encontrada.",
    405: "Operação não permitida para este endereço.",
    413: "Os dados enviados são grandes demais.",
    500: "Ocorreu um erro inesperado. Tente novamente em instantes.",
}


class FormularioExpirado(BadRequest):
    """Erro 400 lançado quando o token CSRF está ausente ou incorreto."""
    description = ("Sua sessão expirou ou o formulário é inválido. "
                   "Recarregue a página e tente novamente.")


def _pagina_de_erro(erro):
    if isinstance(erro, FormularioExpirado):
        mensagem = erro.description
    else:
        mensagem = MENSAGENS.get(erro.code, "Não foi possível concluir a operação.")
    return render_template("erro.html", codigo=erro.code, mensagem=mensagem), erro.code


def registrar_tratadores_de_erro(app):
    """Registra os tratadores de erro na aplicação."""
    app.register_error_handler(HTTPException, _pagina_de_erro)

    def erro_interno(erro):
        app.logger.exception("Erro não tratado: %s", erro)
        return _pagina_de_erro(InternalServerError())

    app.register_error_handler(Exception, erro_interno)
