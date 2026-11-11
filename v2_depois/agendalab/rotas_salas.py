"""Rotas de salas: listagem e cadastro (somente administradores)."""
import sqlite3

from flask import Blueprint, flash, redirect, render_template, request, url_for

from . import repositorio
from .seguranca import admin_obrigatorio, login_obrigatorio
from .validacao import TIPOS_DE_SALA, validar_sala

bp = Blueprint("salas", __name__, url_prefix="/salas")


@bp.route("")
@login_obrigatorio
def listar():
    """Lista as salas cadastradas."""
    return render_template("salas.html", salas=repositorio.listar_salas())


def _registrar_sala(dados):
    try:
        repositorio.criar_sala(dados["nome"], dados["capacidade"], dados["tipo"])
    except sqlite3.IntegrityError:
        return ["Já existe uma sala com esse nome."]
    return []


@bp.route("/nova", methods=("GET", "POST"))
@admin_obrigatorio
def nova():
    """Formulário e gravação de uma nova sala."""
    if request.method == "POST":
        dados, erros = validar_sala(request.form)
        erros = erros or _registrar_sala(dados)
        if not erros:
            flash(f"Sala \"{dados['nome']}\" cadastrada.", "sucesso")
            return redirect(url_for("salas.listar"))
        return render_template("sala_form.html", erros=erros, dados=request.form,
                               tipos=TIPOS_DE_SALA), 400
    return render_template("sala_form.html", erros=[], dados={}, tipos=TIPOS_DE_SALA)
