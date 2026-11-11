"""Testes de segurança (requisitos não funcionais), baseados no OWASP Top 10."""
import hashlib

from sistema import Navegador, dados_de_reserva, dia_util

DADOS_CADASTRO = {"nome": "João Pereira", "login": "joao", "senha": "Senha123", "confirmar_senha": "Senha123"}


def test_seg01_injecao_de_sql_no_login_e_bloqueada(navegador):
    navegador.entrar("' OR '1'='1' --", "qualquer-coisa")
    assert not navegador.esta_logado()


def test_seg02_senha_armazenada_com_hash_seguro_e_sal(navegador, sistema):
    navegador.enviar("/cadastro", DADOS_CADASTRO)
    navegador.enviar("/cadastro", {**DADOS_CADASTRO, "login": "joao2"})
    salvas = [linha[0] for linha in sistema.consultar(
        "SELECT senha FROM usuarios WHERE login IN ('joao', 'joao2')")]
    senha = DADOS_CADASTRO["senha"].encode()
    formas_inseguras = {senha.decode(), hashlib.md5(senha).hexdigest(),
                        hashlib.sha1(senha).hexdigest(), hashlib.sha256(senha).hexdigest()}
    assert len(salvas) == 2
    assert not formas_inseguras.intersection(salvas), "senha em texto puro ou hash sem sal"
    assert salvas[0] != salvas[1], "a mesma senha deve gerar hashes diferentes (uso de sal)"


def test_seg03_usuario_nao_cancela_reserva_de_outra_pessoa(sistema, sala, usuario_comum):
    reserva_id = sistema.inserir_reserva(sala, usuario_comum["id"], dia_util(3), "08:00", "10:00")
    sistema.inserir_usuario("Carlos Lima", "carlos", "Senha123")
    outro_usuario = Navegador(sistema)
    outro_usuario.entrar("carlos", "Senha123")
    resposta = outro_usuario.cancelar_reserva(reserva_id)
    assert resposta.status_code == 403
    assert sistema.contar("reservas") == 1


def test_seg04_formulario_sem_token_csrf_e_recusado(logado, sistema, sala):
    logado.cliente.post("/reservas/nova", data=dados_de_reserva(sala))  # envio forjado, sem token
    assert sistema.contar("reservas") == 0


def test_seg05_script_no_motivo_nao_e_executado_xss(logado, sistema, sala, usuario_comum):
    sistema.inserir_reserva(sala, usuario_comum["id"], dia_util(3), "08:00", "10:00",
                            "<script>alert('xss')</script>")
    pagina = logado.abrir("/reservas").get_data(as_text=True)
    assert "<script>alert('xss')</script>" not in pagina


def test_seg06_cookie_de_sessao_protegido(navegador, usuario_comum):
    resposta = navegador.entrar(usuario_comum["login"], usuario_comum["senha"])
    cookie = resposta.headers.get("Set-Cookie", "")
    assert "HttpOnly" in cookie
    assert "SameSite" in cookie


def test_seg07_cabecalhos_de_seguranca_http(navegador):
    resposta = navegador.abrir("/login")
    for cabecalho in ("X-Content-Type-Options", "X-Frame-Options", "Content-Security-Policy"):
        assert cabecalho in resposta.headers, f"cabeçalho {cabecalho} ausente"


def test_seg08_senha_fraca_e_recusada(navegador, sistema):
    navegador.enviar("/cadastro", {**DADOS_CADASTRO, "senha": "123", "confirmar_senha": "123"})
    assert sistema.contar("usuarios", "login = ?", ("joao",)) == 0
