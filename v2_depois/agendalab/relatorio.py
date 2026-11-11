"""Cálculos do relatório de ocupação das salas (funções puras)."""
import calendar
from datetime import date

from .validacao import DOMINGO, HORA_ABERTURA, HORA_FECHAMENTO

HORAS_POR_DIA = HORA_FECHAMENTO.hour - HORA_ABERTURA.hour  # 16 horas (07:00 às 23:00)
LIMITE_OCUPACAO_BAIXA = 30
LIMITE_OCUPACAO_MEDIA = 70


def dias_de_funcionamento(ano, mes):
    """Quantidade de dias do mês em que o laboratório funciona (segunda a sábado)."""
    _, total_de_dias = calendar.monthrange(ano, mes)
    return sum(1 for dia in range(1, total_de_dias + 1) if date(ano, mes, dia).weekday() != DOMINGO)


def periodo_do_mes(ano, mes):
    """Retorna (primeiro dia do mês, primeiro dia do mês seguinte) no formato AAAA-MM-DD."""
    inicio = date(ano, mes, 1)
    fim = date(ano + 1, 1, 1) if mes == 12 else date(ano, mes + 1, 1)
    return inicio.isoformat(), fim.isoformat()


def classificar_ocupacao(percentual):
    """Classifica o percentual de ocupação em Baixa, Média ou Alta."""
    if percentual < LIMITE_OCUPACAO_BAIXA:
        return "Baixa"
    if percentual < LIMITE_OCUPACAO_MEDIA:
        return "Média"
    return "Alta"


def montar_relatorio(linhas, ano, mes):
    """Transforma o resultado da consulta agregada nas linhas exibidas no relatório."""
    horas_disponiveis = dias_de_funcionamento(ano, mes) * HORAS_POR_DIA
    relatorio = []
    for linha in linhas:
        horas = linha["minutos"] / 60
        ocupacao = horas / horas_disponiveis * 100
        relatorio.append({
            "sala": linha["sala"],
            "total": linha["total"],
            "horas": round(horas, 1),
            "ocupacao": round(ocupacao, 1),
            "nivel": classificar_ocupacao(ocupacao),
        })
    return relatorio
