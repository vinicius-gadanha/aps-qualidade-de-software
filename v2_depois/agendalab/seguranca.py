"""Controles de segurança: CSRF, autenticação, autorização e cabeçalhos HTTP."""
import hmac
import secrets
from functools import wraps

from flask import abort, flash, g, redirect, request, session, url_for

from .erros import FormularioExpirado

METODOS_SEGUROS = {"GET", "HEAD", "OPTIONS"}

CABECALHOS_SEGURANCA = {
    "X-Content-Type-Options": "nosniff",
    "X-Frame-Options": "DENY",
    "Referrer-Policy": "same-origin",
    "Content-Security-Policy": (
        "default-src 'self'; script-src 'self'; style-src 'self'; "
        "img-src 'self' data:; frame-ancestors 'none'; form-action 'self'"
    ),
}


def token_csrf():
    """Retorna o token CSRF da sessão, criando um novo quando necessário."""
    if "_csrf" not in session:
        session["_csrf"] = secrets.token_urlsafe(32)
    return session["_csrf"]


def validar_csrf():
    """Rejeita requisições que alteram dados sem o token CSRF correto."""
    if request.method in METODOS_SEGUROS:
        return
    enviado = request.form.get("csrf_token", "")
    esperado = session.get("_csrf", "")
    if not esperado or not hmac.compare_digest(enviado.encode("utf-8"), esperado.encode("utf-8")):
        raise FormularioExpirado()


def aplicar_cabecalhos_seguranca(resposta):
    """Adiciona cabeçalhos HTTP de proteção a todas as respostas."""
    for nome, valor in CABECALHOS_SEGURANCA.items():
        resposta.headers.setdefault(nome, valor)
    return resposta


def login_obrigatorio(view):
    """Decorador: exige usuário autenticado."""
    @wraps(view)
    def view_protegida(*args, **kwargs):
        if g.get("usuario") is None:
            flash("Faça login para continuar.", "aviso")
            return redirect(url_for("auth.login"))
        return view(*args, **kwargs)
    return view_protegida


def admin_obrigatorio(view):
    """Decorador: exige usuário autenticado com perfil de administrador."""
    @wraps(view)
    @login_obrigatorio
    def view_protegida(*args, **kwargs):
        if g.usuario["perfil"] != "admin":
            abort(403)
        return view(*args, **kwargs)
    return view_protegida


def pode_excluir_reserva(usuario, reserva):
    """Somente o dono da reserva ou um administrador pode cancelá-la."""
    return usuario["perfil"] == "admin" or reserva["usuario_id"] == usuario["id"]
