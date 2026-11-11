"""Rotas de autenticação: login, logout e cadastro de usuários."""
import sqlite3

from flask import (Blueprint, current_app, flash, g, redirect, render_template, request,
                   session, url_for)
from werkzeug.security import check_password_hash, generate_password_hash

from . import repositorio
from .validacao import validar_cadastro

bp = Blueprint("auth", __name__)

# Hash usado quando o login não existe: o tempo de resposta fica parecido nos dois casos,
# o que dificulta descobrir quais logins estão cadastrados.
HASH_FICTICIO = generate_password_hash("valor-ficticio-para-comparacao")


@bp.before_app_request
def carregar_usuario_logado():
    """Disponibiliza em g.usuario o usuário da sessão (ou None)."""
    usuario_id = session.get("usuario_id")
    g.usuario = repositorio.buscar_usuario_por_id(usuario_id) if usuario_id else None


@bp.route("/")
def inicio():
    """Página inicial: leva às reservas ou ao login."""
    return redirect(url_for("reservas.listar" if g.usuario else "auth.login"))


@bp.route("/login", methods=("GET", "POST"))
def login():
    """Autentica o usuário."""
    if request.method == "GET" and g.usuario:
        return redirect(url_for("reservas.listar"))
    if request.method == "POST":
        login_informado = (request.form.get("login") or "").strip().lower()
        usuario = repositorio.buscar_usuario_por_login(login_informado)
        hash_salvo = usuario["senha"] if usuario else HASH_FICTICIO
        if check_password_hash(hash_salvo, request.form.get("senha") or "") and usuario:
            session.clear()  # nova sessão a cada login (evita fixação de sessão)
            session["usuario_id"] = usuario["id"]
            flash(f"Bem-vindo(a), {usuario['nome']}!", "sucesso")
            return redirect(url_for("reservas.listar"))
        current_app.logger.warning("Falha de login para %r", login_informado)
        flash("Login ou senha inválidos.", "erro")
        return render_template("login.html", login=login_informado)
    return render_template("login.html", login="")


@bp.route("/logout")
def logout():
    """Encerra a sessão."""
    session.clear()
    flash("Você saiu do sistema.", "sucesso")
    return redirect(url_for("auth.login"))


def _registrar_usuario(dados):
    try:
        senha_protegida = generate_password_hash(dados["senha"])
        repositorio.criar_usuario(dados["nome"], dados["login"], senha_protegida)
    except sqlite3.IntegrityError:
        return ["Este login já está em uso. Escolha outro."]
    return []


@bp.route("/cadastro", methods=("GET", "POST"))
def cadastro():
    """Cadastro de novos usuários (perfil comum)."""
    if request.method == "POST":
        dados, erros = validar_cadastro(request.form)
        erros = erros or _registrar_usuario(dados)
        if not erros:
            flash("Cadastro realizado! Agora é só entrar com seu login e senha.", "sucesso")
            return redirect(url_for("auth.login"))
        return render_template("cadastro.html", erros=erros, dados=dados), 400
    return render_template("cadastro.html", erros=[], dados={})
