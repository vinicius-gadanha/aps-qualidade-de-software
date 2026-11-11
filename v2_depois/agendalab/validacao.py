"""Regras de validação de dados de entrada (funções puras, fáceis de testar)."""
import re
from datetime import datetime, time

HORA_ABERTURA = time(7, 0)
HORA_FECHAMENTO = time(23, 0)
DOMINGO = 6
TAMANHO_MAXIMO_MOTIVO = 200
TAMANHO_MINIMO_SENHA = 8
CAPACIDADE_MAXIMA = 500
TIPOS_DE_SALA = ("Sala de aula", "Laboratório", "Auditório")
PADRAO_LOGIN = re.compile(r"^[a-z0-9._-]{3,30}$")


def converter_data(texto):
    """Converte 'AAAA-MM-DD' em date; retorna None se o valor for inválido."""
    try:
        return datetime.strptime(texto, "%Y-%m-%d").date()
    except (TypeError, ValueError):
        return None


def converter_hora(texto):
    """Converte 'HH:MM' em time; retorna None se o valor for inválido."""
    try:
        return datetime.strptime(texto, "%H:%M").time()
    except (TypeError, ValueError):
        return None


def converter_mes(texto):
    """Converte 'AAAA-MM' em (ano, mês); retorna None se o valor for inválido."""
    try:
        data = datetime.strptime(texto, "%Y-%m")
    except (TypeError, ValueError):
        return None
    return data.year, data.month


def converter_inteiro_positivo(texto, maximo=None):
    """Converte texto em inteiro positivo (opcionalmente limitado a um máximo)."""
    try:
        valor = int(texto)
    except (TypeError, ValueError):
        return None
    if valor <= 0 or (maximo is not None and valor > maximo):
        return None
    return valor


def _erros_da_data(data, agora):
    if data is None:
        return ["Informe uma data válida."]
    if data < agora.date():
        return ["Não é possível reservar em uma data que já passou."]
    if data.weekday() == DOMINGO:
        return ["O laboratório não funciona aos domingos."]
    return []


def _erros_do_horario(inicio, fim):
    if inicio is None or fim is None:
        return ["Informe os horários de início e de término no formato HH:MM."]
    if fim <= inicio:
        return ["O horário de término deve ser depois do horário de início."]
    if inicio < HORA_ABERTURA or fim > HORA_FECHAMENTO:
        return ["As reservas devem ficar entre 07:00 e 23:00."]
    return []


def _erros_de_horario_passado(data, inicio, agora):
    if data is not None and inicio is not None and data == agora.date() and inicio <= agora.time():
        return ["Esse horário de hoje já passou."]
    return []


def _erros_do_motivo(motivo):
    if not motivo:
        return ["Informe o motivo da reserva."]
    if len(motivo) > TAMANHO_MAXIMO_MOTIVO:
        return [f"O motivo deve ter no máximo {TAMANHO_MAXIMO_MOTIVO} caracteres."]
    return []


def validar_reserva(formulario, agora):
    """Valida os dados de uma nova reserva.

    Retorna uma tupla (dados_normalizados, lista_de_erros).
    """
    sala_id = converter_inteiro_positivo(formulario.get("sala_id"))
    data = converter_data(formulario.get("data"))
    inicio = converter_hora(formulario.get("hora_inicio"))
    fim = converter_hora(formulario.get("hora_fim"))
    motivo = (formulario.get("motivo") or "").strip()

    erros = [] if sala_id else ["Selecione uma sala."]
    erros += _erros_da_data(data, agora)
    erros += _erros_do_horario(inicio, fim)
    erros += _erros_de_horario_passado(data, inicio, agora)
    erros += _erros_do_motivo(motivo)

    dados = {
        "sala_id": sala_id,
        "data": data.isoformat() if data else None,
        "hora_inicio": inicio.strftime("%H:%M") if inicio else None,
        "hora_fim": fim.strftime("%H:%M") if fim else None,
        "motivo": motivo,
    }
    return dados, erros


def validar_cadastro(formulario):
    """Valida o cadastro de usuário. Retorna (dados_normalizados, lista_de_erros)."""
    nome = (formulario.get("nome") or "").strip()
    login = (formulario.get("login") or "").strip().lower()
    senha = formulario.get("senha") or ""
    confirmacao = formulario.get("confirmar_senha") or ""

    erros = []
    if not 3 <= len(nome) <= 100:
        erros.append("Informe seu nome completo (de 3 a 100 caracteres).")
    if not PADRAO_LOGIN.match(login):
        erros.append("O login deve ter de 3 a 30 caracteres: letras minúsculas, números, "
                     "ponto, hífen ou sublinhado.")
    erros += erros_da_senha(senha, confirmacao)
    return {"nome": nome, "login": login, "senha": senha}, erros


def erros_da_senha(senha, confirmacao):
    """Política de senha: mínimo de 8 caracteres, com letras e números."""
    erros = []
    if len(senha) < TAMANHO_MINIMO_SENHA:
        erros.append(f"A senha deve ter pelo menos {TAMANHO_MINIMO_SENHA} caracteres.")
    if not (re.search(r"[A-Za-z]", senha) and re.search(r"\d", senha)):
        erros.append("A senha deve conter letras e números.")
    if senha != confirmacao:
        erros.append("A confirmação de senha não confere.")
    return erros


def validar_sala(formulario):
    """Valida o cadastro de sala. Retorna (dados_normalizados, lista_de_erros)."""
    nome = (formulario.get("nome") or "").strip()
    capacidade = converter_inteiro_positivo(formulario.get("capacidade"), maximo=CAPACIDADE_MAXIMA)
    tipo = formulario.get("tipo") or ""

    erros = []
    if not 2 <= len(nome) <= 60:
        erros.append("O nome da sala deve ter de 2 a 60 caracteres.")
    if capacidade is None:
        erros.append(f"A capacidade deve ser um número inteiro entre 1 e {CAPACIDADE_MAXIMA}.")
    if tipo not in TIPOS_DE_SALA:
        erros.append("Selecione um tipo de sala válido.")
    return {"nome": nome, "capacidade": capacidade, "tipo": tipo}, erros


def formatar_data_br(texto):
    """Exibe 'AAAA-MM-DD' como 'DD/MM/AAAA' (filtro usado nos templates)."""
    data = converter_data(texto)
    return data.strftime("%d/%m/%Y") if data else texto


def formatar_numero_br(valor):
    """Exibe números com uma casa decimal e vírgula (ex.: 4,0)."""
    return f"{valor:.1f}".replace(".", ",")
