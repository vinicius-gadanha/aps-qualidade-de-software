"""Testes de robustez (confiabilidade / tolerância a falhas).

Entradas inválidas não podem derrubar o sistema (erro HTTP 500) nem gravar dados inconsistentes.
"""
import pytest

from sistema import dados_de_reserva

ENTRADAS_INVALIDAS_DE_RESERVA = [
    pytest.param({"data": ""}, id="data-vazia"),
    pytest.param({"data": "31/12/2026"}, id="data-em-formato-errado"),
    pytest.param({"data": "2026-02-30"}, id="data-inexistente"),
    pytest.param({"hora_inicio": "25:00"}, id="hora-inexistente"),
    pytest.param({"hora_inicio": "aa:bb"}, id="hora-com-letras"),
    pytest.param({"hora_fim": ""}, id="hora-de-termino-vazia"),
    pytest.param({"sala_id": "abc"}, id="sala-com-letras"),
    pytest.param({"sala_id": "9999"}, id="sala-inexistente"),
    pytest.param({"motivo": ""}, id="motivo-vazio"),
    pytest.param({"motivo": "x" * 1000}, id="motivo-longo-demais"),
]

ENTRADAS_INVALIDAS_DE_SALA = [
    pytest.param({"capacidade": "abc"}, id="capacidade-com-letras"),
    pytest.param({"capacidade": "-5"}, id="capacidade-negativa"),
    pytest.param({"nome": ""}, id="nome-vazio"),
]


@pytest.mark.parametrize("alteracao", ENTRADAS_INVALIDAS_DE_RESERVA)
def test_reserva_com_entrada_invalida(logado, sistema, sala, alteracao):
    resposta = logado.enviar("/reservas/nova", {**dados_de_reserva(sala), **alteracao})
    assert resposta.status_code < 500, "o sistema não pode gerar erro interno"
    assert sistema.contar("reservas") == 0, "nenhuma reserva inválida pode ser gravada"


@pytest.mark.parametrize("alteracao", ENTRADAS_INVALIDAS_DE_SALA)
def test_sala_com_entrada_invalida(admin_logado, sistema, alteracao):
    dados = {"nome": "Sala Teste", "capacidade": "30", "tipo": "Laboratório", **alteracao}
    resposta = admin_logado.enviar("/salas/nova", dados)
    assert resposta.status_code < 500, "o sistema não pode gerar erro interno"
    assert sistema.contar("salas") == 0, "nenhuma sala inválida pode ser gravada"


def test_relatorio_com_mes_invalido(admin_logado):
    assert admin_logado.abrir("/relatorio?mes=abc").status_code < 500


def test_filtro_de_reservas_com_data_invalida(logado):
    assert logado.abrir("/reservas?data=abc").status_code < 500
