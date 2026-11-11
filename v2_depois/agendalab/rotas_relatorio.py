"""Rota do relatório de ocupação das salas (somente administradores)."""
from datetime import date

from flask import Blueprint, flash, render_template, request

from . import repositorio
from .relatorio import montar_relatorio, periodo_do_mes
from .seguranca import admin_obrigatorio
from .validacao import converter_mes

bp = Blueprint("relatorio", __name__)


@bp.route("/relatorio")
@admin_obrigatorio
def ocupacao():
    """Mostra quantas reservas e horas cada sala teve no mês escolhido."""
    mes_atual = date.today().strftime("%Y-%m")
    texto_mes = request.args.get("mes") or mes_atual
    if converter_mes(texto_mes) is None:
        flash("Mês inválido. Use o formato AAAA-MM.", "erro")
        texto_mes = mes_atual
    ano, mes = converter_mes(texto_mes)
    linhas = repositorio.minutos_reservados_por_sala(*periodo_do_mes(ano, mes))
    relatorio = montar_relatorio(linhas, ano, mes)
    return render_template("relatorio.html", relatorio=relatorio, mes=texto_mes)
