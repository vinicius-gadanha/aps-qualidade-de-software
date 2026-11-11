"""Testes funcionais (caixa-preta) derivados dos requisitos do AgendaLab.

Cada teste indica o requisito funcional (RF) ou a regra de negócio (RN) verificada.
Os mesmos testes são executados nas versões 1.0 e 2.0.
"""
import re

from sistema import Navegador, dados_de_reserva, data_passada, dia_util, domingo_futuro

DADOS_CADASTRO = {"nome": "João Pereira", "login": "joao", "senha": "Senha123", "confirmar_senha": "Senha123"}


# ------------------------------------------------------- RF01 - Autenticação
def test_rf01_pagina_de_login_disponivel(navegador):
    assert navegador.abrir("/login").status_code == 200


def test_rf01_login_com_credenciais_validas(navegador, usuario_comum):
    navegador.entrar(usuario_comum["login"], usuario_comum["senha"])
    assert navegador.esta_logado()


def test_rf01_login_com_senha_errada_e_recusado(navegador, usuario_comum):
    navegador.entrar(usuario_comum["login"], "SenhaErrada9")
    assert not navegador.esta_logado()


def test_rf01_logout_encerra_a_sessao(logado):
    logado.abrir("/logout")
    assert not logado.esta_logado()


def test_rf01_paginas_internas_exigem_login(navegador):
    for url in ("/reservas", "/reservas/nova", "/salas"):
        resposta = navegador.abrir(url)
        assert resposta.status_code == 302
        assert "/login" in resposta.headers["Location"]


# ------------------------------------------------- RF02 - Cadastro de usuários
def test_rf02_cadastro_de_usuario_valido(navegador):
    navegador.enviar("/cadastro", DADOS_CADASTRO)
    navegador.entrar("joao", "Senha123")
    assert navegador.esta_logado()


def test_rf02_login_repetido_e_recusado_sem_erro_interno(navegador, sistema):
    navegador.enviar("/cadastro", DADOS_CADASTRO)
    resposta = navegador.enviar("/cadastro", {**DADOS_CADASTRO, "nome": "Outro João"})
    assert resposta.status_code < 500
    assert sistema.contar("usuarios", "login = ?", ("joao",)) == 1


def test_rf02_nome_com_apostrofo_e_aceito(navegador, sistema):
    resposta = navegador.enviar("/cadastro", {**DADOS_CADASTRO, "nome": "Ana D'Ávila", "login": "ana"})
    assert resposta.status_code < 500
    assert sistema.contar("usuarios", "login = ?", ("ana",)) == 1


# --------------------------------------------------------------- RF03 - Salas
def test_rf03_admin_cadastra_sala(admin_logado, sistema):
    admin_logado.enviar("/salas/nova", {"nome": "Laboratório 5", "capacidade": "30", "tipo": "Laboratório"})
    assert sistema.contar("salas", "nome = ?", ("Laboratório 5",)) == 1


def test_rf03_usuario_comum_nao_cadastra_sala(logado, sistema):
    logado.enviar("/salas/nova", {"nome": "Sala Indevida", "capacidade": "10", "tipo": "Sala de aula"})
    assert sistema.contar("salas", "nome = ?", ("Sala Indevida",)) == 0


def test_rf03_listagem_de_salas(logado, sala):
    assert sala
    assert "Laboratório 1" in logado.abrir("/salas").get_data(as_text=True)


# ------------------------------------------------- RF04 - Criação de reservas
def test_rf04_criar_reserva_valida(logado, sistema, sala):
    logado.enviar("/reservas/nova", dados_de_reserva(sala))
    assert sistema.contar("reservas") == 1


def test_rf04_motivo_com_apostrofo_e_aceito(logado, sistema, sala):
    resposta = logado.enviar("/reservas/nova", dados_de_reserva(sala, motivo="Reunião do projeto Olho d'Água"))
    assert resposta.status_code < 500
    assert sistema.contar("reservas") == 1


def test_rn01_reserva_em_conflito_de_horario_e_recusada(logado, sistema, sala):
    logado.enviar("/reservas/nova", dados_de_reserva(sala, inicio="08:00", fim="10:00"))
    logado.enviar("/reservas/nova", dados_de_reserva(sala, inicio="09:00", fim="11:00"))
    assert sistema.contar("reservas") == 1


def test_rn01_reservas_em_sequencia_sao_permitidas(logado, sistema, sala):
    logado.enviar("/reservas/nova", dados_de_reserva(sala, inicio="08:00", fim="10:00"))
    logado.enviar("/reservas/nova", dados_de_reserva(sala, inicio="10:00", fim="12:00"))
    assert sistema.contar("reservas") == 2


def test_rn01_mesmo_horario_em_outra_sala_e_permitido(logado, sistema, sala):
    outra_sala = sistema.inserir_sala("Laboratório 2")
    logado.enviar("/reservas/nova", dados_de_reserva(sala))
    logado.enviar("/reservas/nova", dados_de_reserva(outra_sala))
    assert sistema.contar("reservas") == 2


def test_rn02_termino_antes_do_inicio_e_recusado(logado, sistema, sala):
    logado.enviar("/reservas/nova", dados_de_reserva(sala, inicio="10:00", fim="08:00"))
    assert sistema.contar("reservas") == 0


def test_rn03_reserva_em_data_passada_e_recusada(logado, sistema, sala):
    logado.enviar("/reservas/nova", dados_de_reserva(sala, data=data_passada()))
    assert sistema.contar("reservas") == 0


def test_rn04_reserva_no_domingo_e_recusada(logado, sistema, sala):
    resposta = logado.enviar("/reservas/nova", dados_de_reserva(sala, data=domingo_futuro()))
    assert resposta.status_code < 500
    assert sistema.contar("reservas") == 0


def test_rn05_reserva_fora_do_horario_de_funcionamento_e_recusada(logado, sistema, sala):
    logado.enviar("/reservas/nova", dados_de_reserva(sala, inicio="05:00", fim="06:30"))
    assert sistema.contar("reservas") == 0


# ------------------------------------------------- RF05 - Consulta de reservas
def test_rf05_lista_mostra_as_reservas(logado, sistema, sala, usuario_comum):
    sistema.inserir_reserva(sala, usuario_comum["id"], dia_util(3), "08:00", "10:00", "Aula de Redes")
    pagina = logado.abrir("/reservas").get_data(as_text=True)
    assert "Aula de Redes" in pagina
    assert "Laboratório 1" in pagina


def test_rf05_filtro_por_data(logado, sistema, sala, usuario_comum):
    data_redes, data_fisica = dia_util(3), dia_util(10)
    sistema.inserir_reserva(sala, usuario_comum["id"], data_redes, "08:00", "10:00", "Aula de Redes")
    sistema.inserir_reserva(sala, usuario_comum["id"], data_fisica, "08:00", "10:00", "Aula de Física")
    pagina = logado.abrir(f"/reservas?data={data_redes}").get_data(as_text=True)
    assert "Aula de Redes" in pagina
    assert "Aula de Física" not in pagina


# ---------------------------------------------- RF06 - Cancelamento de reservas
def test_rf06_usuario_cancela_a_propria_reserva(logado, sistema, sala, usuario_comum):
    reserva_id = sistema.inserir_reserva(sala, usuario_comum["id"], dia_util(3), "08:00", "10:00")
    logado.cancelar_reserva(reserva_id)
    assert sistema.contar("reservas") == 0


def test_rf06_administrador_cancela_qualquer_reserva(sistema, sala, usuario_comum):
    reserva_id = sistema.inserir_reserva(sala, usuario_comum["id"], dia_util(3), "08:00", "10:00")
    admin = Navegador(sistema)
    admin.entrar_como_admin()
    admin.cancelar_reserva(reserva_id)
    assert sistema.contar("reservas") == 0


# --------------------------------------------- RF07 - Relatório de ocupação
def test_rf07_relatorio_soma_as_horas_por_sala(admin_logado, sistema, sala, usuario_comum):
    data = dia_util(30)
    sistema.inserir_reserva(sala, usuario_comum["id"], data, "08:00", "10:00")
    sistema.inserir_reserva(sala, usuario_comum["id"], data, "14:00", "16:00")
    pagina = admin_logado.abrir(f"/relatorio?mes={data[:7]}").get_data(as_text=True)
    assert re.search(r"(?<!\d)4[.,]0(?!\d)", pagina), "2 reservas de 2 h devem somar 4,0 h"


def test_rf07_relatorio_restrito_ao_administrador(logado):
    resposta = logado.abrir("/relatorio")
    assert resposta.status_code in (302, 403)
    assert "Relatório de ocupação" not in resposta.get_data(as_text=True)
