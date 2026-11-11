"""Rotas de reservas: listagem com filtro e paginação, criação e cancelamento."""
import math
from datetime import date, datetime

from flask import (Blueprint, abort, current_app, flash, g, redirect, render_template, request,
                   url_for)

from . import repositorio
from .seguranca import login_obrigatorio, pode_excluir_reserva
from .validacao import converter_data, converter_inteiro_positivo, validar_reserva

bp = Blueprint("reservas", __name__, url_prefix="/reservas")


@bp.route("")
@login_obrigatorio
def listar():
    """Lista as reservas, com filtro opcional por data e paginação."""
    data = (request.args.get("data") or "").strip()
    if data and converter_data(data) is None:
        flash("Data inválida no filtro. Use o seletor de data.", "erro")
        data = ""
    por_pagina = current_app.config["POR_PAGINA"]
    total = repositorio.contar_reservas(data or None)
    paginas = max(1, math.ceil(total / por_pagina))
    pagina = min(converter_inteiro_positivo(request.args.get("pagina")) or 1, paginas)
    reservas = repositorio.listar_reservas(data or None, por_pagina, (pagina - 1) * por_pagina)
    return render_template("reservas.html", reservas=reservas, data=data,
                           pagina=pagina, paginas=paginas, total=total)


def _registrar_reserva(dados):
    if repositorio.buscar_sala(dados["sala_id"]) is None:
        return ["A sala selecionada não existe."]
    if not repositorio.criar_reserva_sem_conflito(dados, g.usuario["id"]):
        return ["Esta sala já está reservada nesse horário. Escolha outro horário ou outra sala."]
    current_app.logger.info("Reserva criada por %s: %s", g.usuario["login"], dados)
    return []


@bp.route("/nova", methods=("GET", "POST"))
@login_obrigatorio
def nova():
    """Formulário e gravação de uma nova reserva."""
    salas = repositorio.listar_salas()
    hoje = date.today().isoformat()
    if request.method == "POST":
        dados, erros = validar_reserva(request.form, datetime.now())
        erros = erros or _registrar_reserva(dados)
        if not erros:
            flash("Reserva criada com sucesso.", "sucesso")
            return redirect(url_for("reservas.listar", data=dados["data"]))
        return render_template("reserva_form.html", salas=salas, erros=erros,
                               dados=request.form, hoje=hoje), 400
    return render_template("reserva_form.html", salas=salas, erros=[], dados={}, hoje=hoje)


@bp.route("/<int:reserva_id>/excluir", methods=("POST",))
@login_obrigatorio
def excluir(reserva_id):
    """Cancela uma reserva (somente o dono ou um administrador)."""
    reserva = repositorio.buscar_reserva(reserva_id)
    if reserva is None:
        abort(404)
    if not pode_excluir_reserva(g.usuario, reserva):
        abort(403)
    repositorio.excluir_reserva(reserva_id)
    current_app.logger.info("Reserva %s cancelada por %s", reserva_id, g.usuario["login"])
    flash("Reserva cancelada.", "sucesso")
    return redirect(url_for("reservas.listar"))
