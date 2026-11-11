"""Auditoria automática de acessibilidade e boas práticas com o Google Lighthouse.

Requer Node.js e Google Chrome (ou Chromium) instalados. O Lighthouse é executado com
"npx lighthouse" (ou pelo comando definido na variável de ambiente LIGHTHOUSE_CMD).

Uso:
    python qualidade/auditoria_lighthouse.py
"""
import json
import os
import shlex
import shutil
import subprocess
import sys
import tempfile

import teste_carga as carga  # mesmo diretório (qualidade/)

PAGINAS = [("Login", "/login", False), ("Lista de reservas", "/reservas", True),
           ("Nova reserva", "/reservas/nova", True)]
CATEGORIAS = ("accessibility", "best-practices")


def comando_lighthouse():
    """Descobre como chamar o Lighthouse neste computador."""
    if os.environ.get("LIGHTHOUSE_CMD"):
        return shlex.split(os.environ["LIGHTHOUSE_CMD"])
    if shutil.which("lighthouse"):
        return [shutil.which("lighthouse")]
    npx = shutil.which("npx") or shutil.which("npx.cmd")
    if npx:
        return [npx, "--yes", "lighthouse"]
    raise RuntimeError("Lighthouse não encontrado: instale o Node.js (que inclui o npx).")


def auditar(url, cookie=None):
    """Executa o Lighthouse em uma página e devolve as notas e os itens reprovados."""
    comando = comando_lighthouse() + [
        url, "--output=json", "--output-path=stdout", "--quiet",
        "--only-categories=" + ",".join(CATEGORIAS),
        "--chrome-flags=--headless=new --no-sandbox",
    ]
    with tempfile.TemporaryDirectory(ignore_cleanup_errors=True) as pasta:
        if cookie:  # cabeçalho em arquivo: evita problemas com aspas no Windows
            arquivo_cabecalhos = os.path.join(pasta, "cabecalhos.json")
            with open(arquivo_cabecalhos, "w", encoding="utf-8") as arquivo:
                json.dump({"Cookie": cookie}, arquivo)
            comando.append("--extra-headers=" + arquivo_cabecalhos)
        saida = subprocess.run(comando, capture_output=True, text=True, encoding="utf-8",
                               check=True, timeout=300).stdout
    relatorio = json.loads(saida)
    notas = {c: round(relatorio["categories"][c]["score"] * 100) for c in CATEGORIAS}
    reprovados = []
    for categoria in CATEGORIAS:
        for referencia in relatorio["categories"][categoria]["auditRefs"]:
            auditoria = relatorio["audits"][referencia["id"]]
            if referencia["weight"] > 0 and auditoria.get("score") is not None and auditoria["score"] < 1:
                reprovados.append({"categoria": categoria, "id": referencia["id"], "titulo": auditoria["title"]})
    return {"notas": notas, "reprovados": reprovados}


def cookie_de_sessao(url_base):
    """Faz login com um usuário de teste e devolve o cookie de sessão."""
    cliente = carga.ClienteHttp(url_base)
    cliente.entrar("usuario01", carga.SENHA_PADRAO)
    return "; ".join(f"{cookie.name}={cookie.value}" for cookie in cliente.cookies)


def auditar_versao(versao):
    """Audita as páginas principais de uma versão."""
    with tempfile.TemporaryDirectory(ignore_cleanup_errors=True) as pasta:
        caminho_banco = os.path.join(pasta, "lighthouse.db")
        sistema = carga.Sistema(versao, caminho_banco)
        carga.popular_banco(sistema, quantidade=30)
        processo, url_base = carga.iniciar_servidor(versao, caminho_banco, {})
        try:
            cookie = cookie_de_sessao(url_base)
            resultado = {}
            for nome, caminho, precisa_login in PAGINAS:
                print(f"  {versao} - {nome}...", flush=True)
                resultado[nome] = auditar(url_base + caminho, cookie if precisa_login else None)
        finally:
            processo.terminate()
            processo.wait()
    return resultado


def main():
    """Audita v1 e v2 e salva resultados/lighthouse.json."""
    resultados = {}
    for versao in ("v1", "v2"):
        print(f"Auditoria Lighthouse - {versao}", flush=True)
        resultados[versao] = auditar_versao(versao)
    os.makedirs(carga.PASTA_RESULTADOS, exist_ok=True)
    with open(os.path.join(carga.PASTA_RESULTADOS, "lighthouse.json"), "w", encoding="utf-8") as arquivo:
        json.dump(resultados, arquivo, ensure_ascii=False, indent=2)
    for versao, paginas in resultados.items():
        for pagina, dados in paginas.items():
            print(versao, pagina, dados["notas"])


if __name__ == "__main__":
    sys.exit(main())
