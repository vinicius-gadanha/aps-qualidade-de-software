"""Teste de carga (eficiência de desempenho).

Simula vários usuários consultando a agenda de reservas ao mesmo tempo e mede o tempo
de resposta (média, mediana e percentil 95), a vazão (requisições por segundo) e a taxa
de erros. Também conta quantas consultas SQL uma única abertura da lista executa.

O servidor roda em um processo separado e atende uma requisição por vez (modo de
processo único do servidor Werkzeug), o mesmo para todas as versões.

Uso:
    python qualidade/teste_carga.py                      (v1, v2 e v2 sem paginação)
    python qualidade/teste_carga.py --usuarios 20 --requisicoes 25
"""
import argparse
import http.cookiejar
import json
import logging
import os
import random
import re
import socket
import sqlite3
import statistics
import subprocess
import sys
import tempfile
import threading
import time
import urllib.error
import urllib.parse
import urllib.request
from datetime import date, timedelta

from werkzeug.serving import make_server

RAIZ = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(RAIZ, "testes"))
from sistema import Navegador, Sistema  # noqa: E402  pylint: disable=wrong-import-position

PASTA_RESULTADOS = os.path.join(RAIZ, "qualidade", "resultados")
PADRAO_CSRF = re.compile(r'name="csrf_token" value="([^"]+)"')
QTD_SALAS, QTD_USUARIOS, QTD_RESERVAS = 20, 50, 2000
SENHA_PADRAO = "Senha123"
HORARIOS = [("07:00", "09:00"), ("09:00", "11:00"), ("11:00", "13:00"), ("13:00", "15:00"),
            ("15:00", "17:00"), ("17:00", "19:00"), ("19:00", "21:00"), ("21:00", "23:00")]
CENARIOS = {
    "v1": ("v1", {}),
    "v2": ("v2", {}),
    "v2_sem_paginacao": ("v2", {"POR_PAGINA": 100000}),
}


# ----------------------------------------------------------- massa de dados
def popular_banco(sistema, quantidade=QTD_RESERVAS, semente=2026):
    """Cadastra salas, usuários e reservas sem conflito (dados sintéticos, reproduzíveis)."""
    sorteio = random.Random(semente)
    hash_senha = sistema.hash_senha(SENHA_PADRAO)
    dias = []
    dia = date.today() + timedelta(days=1)
    while len(dias) < 150:
        if dia.weekday() != 6:
            dias.append(dia.isoformat())
        dia += timedelta(days=1)
    vagas = [(s, d, h) for s in range(1, QTD_SALAS + 1) for d in dias for h in HORARIOS]
    escolhidas = sorteio.sample(vagas, quantidade)

    conexao = sqlite3.connect(sistema.caminho_banco)
    with conexao:
        conexao.executemany("INSERT INTO salas (id, nome, capacidade, tipo) VALUES (?, ?, ?, ?)",
                            [(i, f"Sala {i:02d}", 40, "Sala de aula") for i in range(1, QTD_SALAS + 1)])
        conexao.executemany("INSERT INTO usuarios (nome, login, senha, perfil) VALUES (?, ?, ?, 'comum')",
                            [(f"Usuário {i:02d}", f"usuario{i:02d}", hash_senha) for i in range(1, QTD_USUARIOS + 1)])
        primeiro_usuario = conexao.execute("SELECT MIN(id) FROM usuarios WHERE perfil = 'comum'").fetchone()[0]
        conexao.executemany(
            "INSERT INTO reservas (sala_id, usuario_id, data, hora_inicio, hora_fim, motivo) VALUES (?, ?, ?, ?, ?, ?)",
            [(s, primeiro_usuario + sorteio.randrange(QTD_USUARIOS), d, h[0], h[1], f"Aula {n}")
             for n, (s, d, h) in enumerate(escolhidas, start=1)])
    conexao.close()
    return sorted({d for _, d, _ in escolhidas})


# ------------------------------------------------------------ cliente HTTP
class ClienteHttp:
    """Um usuário virtual com seus próprios cookies (sessão)."""

    def __init__(self, url_base):
        self.url_base = url_base
        self.cookies = http.cookiejar.CookieJar()
        self.abridor = urllib.request.build_opener(
            urllib.request.ProxyHandler({}), urllib.request.HTTPCookieProcessor(self.cookies))

    def requisitar(self, caminho, dados=None):
        """Faz a requisição e devolve (código HTTP, tempo em ms)."""
        corpo = urllib.parse.urlencode(dados).encode() if dados is not None else None
        inicio = time.perf_counter()
        try:
            with self.abridor.open(self.url_base + caminho, data=corpo, timeout=120) as resposta:
                resposta.read()
                codigo = resposta.status
        except urllib.error.HTTPError as erro:
            codigo = erro.code
        except OSError:
            codigo = 0
        return codigo, (time.perf_counter() - inicio) * 1000

    def entrar(self, login, senha):
        """Faz login pelo formulário (copiando o token CSRF, quando existir)."""
        with self.abridor.open(self.url_base + "/login", timeout=60) as resposta:
            html = resposta.read().decode("utf-8")
        dados = {"login": login, "senha": senha}
        token = PADRAO_CSRF.search(html)
        if token:
            dados["csrf_token"] = token.group(1)
        self.requisitar("/login", dados)


# --------------------------------------------------------------- medições
def percentil(valores, p):
    """Percentil p (0-100) pelo método do vizinho mais próximo."""
    ordenados = sorted(valores)
    indice = max(0, min(len(ordenados) - 1, round(p / 100 * len(ordenados) + 0.5) - 1))
    return ordenados[indice]


def resumir(amostras, duracao):
    """Calcula as métricas de desempenho a partir das amostras (código, ms)."""
    tempos = [ms for _, ms in amostras]
    erros = sum(1 for codigo, _ in amostras if codigo != 200)
    return {
        "requisicoes": len(amostras),
        "erros": erros,
        "taxa_erros_pct": round(100 * erros / len(amostras), 2),
        "duracao_s": round(duracao, 2),
        "vazao_req_s": round(len(amostras) / duracao, 2),
        "media_ms": round(statistics.mean(tempos), 1),
        "mediana_ms": round(statistics.median(tempos), 1),
        "p95_ms": round(percentil(tempos, 95), 1),
        "max_ms": round(max(tempos), 1),
    }


def porta_livre():
    """Pede ao sistema operacional uma porta TCP livre."""
    with socket.socket() as soquete:
        soquete.bind(("127.0.0.1", 0))
        return soquete.getsockname()[1]


def iniciar_servidor(versao, caminho_banco, configuracao):
    """Sobe o sistema em OUTRO processo, para que o servidor não dispute a CPU com os clientes."""
    porta = porta_livre()
    processo = subprocess.Popen([sys.executable, os.path.abspath(__file__), "--servidor", versao,
                                 caminho_banco, str(porta), json.dumps(configuracao)])
    limite = time.time() + 60
    while time.time() < limite:
        try:
            with socket.create_connection(("127.0.0.1", porta), timeout=1):
                return processo, f"http://127.0.0.1:{porta}"
        except OSError:
            time.sleep(0.2)
    processo.terminate()
    raise RuntimeError("O servidor não iniciou a tempo.")


def servir(versao, caminho_banco, porta, configuracao):
    """Modo servidor (executado no processo filho)."""
    logging.getLogger("werkzeug").setLevel(logging.ERROR)
    sistema = Sistema(versao, caminho_banco, configuracao)
    make_server("127.0.0.1", porta, sistema.app, threaded=False).serve_forever()


def executar_carga(url_base, datas, usuarios, requisicoes):
    """Dispara os usuários virtuais em paralelo contra o servidor."""
    amostras, trava = [], threading.Lock()
    clientes = []
    for i in range(usuarios):
        cliente = ClienteHttp(url_base)
        cliente.entrar(f"usuario{(i % QTD_USUARIOS) + 1:02d}", SENHA_PADRAO)
        clientes.append(cliente)
    clientes[0].requisitar("/reservas")  # aquecimento
    largada = threading.Barrier(usuarios + 1)

    def usuario_virtual(indice, cliente):
        sorteio = random.Random(indice)
        largada.wait()
        for n in range(requisicoes):
            caminho = "/reservas" if n % 2 == 0 else "/reservas?data=" + sorteio.choice(datas)
            resultado = cliente.requisitar(caminho)
            with trava:
                amostras.append(resultado)

    threads = [threading.Thread(target=usuario_virtual, args=(i, c)) for i, c in enumerate(clientes)]
    for thread in threads:
        thread.start()
    largada.wait()
    inicio = time.perf_counter()
    for thread in threads:
        thread.join()
    return resumir(amostras, time.perf_counter() - inicio)


def medir_escalabilidade(versao, tamanhos=(500, 1000, 2500, 5000, 10000), repeticoes=5):
    """Tempo de uma abertura da lista de reservas conforme o banco cresce (mediana de N repetições)."""
    resultados = {}
    for quantidade in tamanhos:
        with tempfile.TemporaryDirectory(ignore_cleanup_errors=True) as pasta:
            sistema = Sistema(versao, os.path.join(pasta, "escala.db"))
            popular_banco(sistema, quantidade)
            navegador = Navegador(sistema)
            navegador.entrar("usuario01", SENHA_PADRAO)
            navegador.abrir("/reservas")  # aquecimento
            tempos = []
            for _ in range(repeticoes):
                inicio = time.perf_counter()
                navegador.abrir("/reservas")
                tempos.append((time.perf_counter() - inicio) * 1000)
            resultados[str(quantidade)] = round(statistics.median(tempos), 1)
    return resultados


def contar_consultas_sql(sistema):
    """Conta quantos SELECTs o banco executa para abrir a lista de reservas uma vez."""
    navegador = Navegador(sistema)
    navegador.entrar("usuario01", SENHA_PADRAO)
    contador = {"select": 0}
    conectar_original = sqlite3.connect

    def conectar_com_contagem(*args, **kwargs):
        conexao = conectar_original(*args, **kwargs)
        conexao.set_trace_callback(
            lambda sql: contador.__setitem__("select", contador["select"] + sql.lstrip().upper().startswith("SELECT")))
        return conexao

    sqlite3.connect = conectar_com_contagem
    try:
        inicio = time.perf_counter()
        resposta = navegador.abrir("/reservas")
        tempo_ms = (time.perf_counter() - inicio) * 1000
    finally:
        sqlite3.connect = conectar_original
    return {"consultas_sql": contador["select"], "tempo_requisicao_unica_ms": round(tempo_ms, 1),
            "tamanho_resposta_kb": round(len(resposta.data) / 1024, 1)}


def medir_cenario(nome, usuarios, requisicoes):
    """Prepara um banco com a massa de dados e mede um cenário."""
    versao, configuracao = CENARIOS[nome]
    with tempfile.TemporaryDirectory(ignore_cleanup_errors=True) as pasta:
        caminho_banco = os.path.join(pasta, "carga.db")
        sistema = Sistema(versao, caminho_banco, configuracao)
        datas = popular_banco(sistema)
        resultado = {"cenario": nome, "usuarios_simultaneos": usuarios,
                     "requisicoes_por_usuario": requisicoes, "reservas_no_banco": QTD_RESERVAS}
        resultado.update(contar_consultas_sql(sistema))
        processo, url_base = iniciar_servidor(versao, caminho_banco, configuracao)
        try:
            resultado.update(executar_carga(url_base, datas, usuarios, requisicoes))
        finally:
            processo.terminate()
            processo.wait()
    return resultado


def main():
    """Ponto de entrada pela linha de comando."""
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--cenarios", nargs="+", default=list(CENARIOS), choices=list(CENARIOS))
    parser.add_argument("--usuarios", type=int, default=20, help="usuários simultâneos")
    parser.add_argument("--requisicoes", type=int, default=25, help="requisições por usuário")
    parser.add_argument("--servidor", nargs=4, metavar=("VERSAO", "BANCO", "PORTA", "CONFIG"),
                        help=argparse.SUPPRESS)
    argumentos = parser.parse_args()
    if argumentos.servidor:
        versao, banco, porta, configuracao = argumentos.servidor
        servir(versao, banco, int(porta), json.loads(configuracao))
        return

    resultados = {"carga": {}, "escalabilidade": {}}
    for nome in argumentos.cenarios:
        print(f"Teste de carga - cenário {nome}...", flush=True)
        resultados["carga"][nome] = medir_cenario(nome, argumentos.usuarios, argumentos.requisicoes)
        print(json.dumps(resultados["carga"][nome], ensure_ascii=False), flush=True)
    for versao in ("v1", "v2"):
        print(f"Teste de escalabilidade - {versao}...", flush=True)
        resultados["escalabilidade"][versao] = medir_escalabilidade(versao)
        print(json.dumps(resultados["escalabilidade"][versao]), flush=True)
    os.makedirs(PASTA_RESULTADOS, exist_ok=True)
    with open(os.path.join(PASTA_RESULTADOS, "carga.json"), "w", encoding="utf-8") as arquivo:
        json.dump(resultados, arquivo, ensure_ascii=False, indent=2)


if __name__ == "__main__":
    main()
