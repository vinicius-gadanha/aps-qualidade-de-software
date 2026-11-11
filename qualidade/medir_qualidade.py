"""Executa o plano de medição de qualidade nas duas versões do AgendaLab.

Métricas coletadas (para v1 = antes e v2 = depois):
  * Adequação funcional e confiabilidade: testes aprovados por categoria (pytest)
  * Testabilidade: cobertura de código pelos testes (pytest-cov)
  * Manutenibilidade: complexidade ciclomática e índice de manutenibilidade (radon),
    nota de análise estática (pylint)
  * Segurança: vulnerabilidades encontradas por análise estática (bandit)
  * Eficiência de desempenho: teste de carga e de escalabilidade (teste_carga.py)
  * Usabilidade/acessibilidade: Lighthouse (opcional, requer Node.js)

Uso:
    python qualidade/medir_qualidade.py                 (tudo, exceto Lighthouse)
    python qualidade/medir_qualidade.py --lighthouse    (inclui a auditoria Lighthouse)
    python qualidade/medir_qualidade.py --sem-carga     (pula o teste de carga)

Os resultados ficam em qualidade/resultados/metricas.json.
"""
import argparse
import ast
import glob
import json
import os
import re
import subprocess
import sys
import xml.etree.ElementTree as ET

from radon.complexity import cc_visit
from radon.metrics import mi_visit
from radon.raw import analyze
from radon.visitors import Class

RAIZ = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
PASTA_RESULTADOS = os.path.join(RAIZ, "qualidade", "resultados")
VERSOES = {
    "v1": {"pasta": os.path.join(RAIZ, "v1_antes"), "cobertura": os.path.join(RAIZ, "v1_antes"),
           "alvos_pylint": ["app.py"]},
    "v2": {"pasta": os.path.join(RAIZ, "v2_depois"), "cobertura": os.path.join(RAIZ, "v2_depois", "agendalab"),
           "alvos_pylint": ["agendalab", "executar.py"]},
}
CATEGORIAS_DE_TESTE = {"test_funcionais": "funcionais", "test_seguranca": "seguranca", "test_robustez": "robustez"}


def executar(comando, pasta=RAIZ):
    """Executa um comando e devolve a saída (texto)."""
    return subprocess.run(comando, cwd=pasta, capture_output=True, text=True, encoding="utf-8",
                          check=False).stdout


def arquivos_python(versao):
    """Arquivos .py do sistema (sem os testes)."""
    pasta = VERSOES[versao]["pasta"]
    return sorted(glob.glob(os.path.join(pasta, "*.py")) + glob.glob(os.path.join(pasta, "agendalab", "*.py")))


# ------------------------------------------------------------------ testes
def medir_testes(versao):
    """Roda a suíte de testes com cobertura e resume os resultados por categoria."""
    xml = os.path.join(PASTA_RESULTADOS, f"testes_{versao}.xml")
    cobertura = os.path.join(PASTA_RESULTADOS, f"cobertura_{versao}.json")
    executar([sys.executable, "-m", "pytest", "testes", f"--versao={versao}", "-q", "-p", "no:cacheprovider",
              f"--junitxml={xml}", f"--cov={VERSOES[versao]['cobertura']}", "--cov-branch",
              f"--cov-report=json:{cobertura}"])
    categorias = {nome: {"total": 0, "aprovados": 0} for nome in CATEGORIAS_DE_TESTE.values()}
    reprovados = []
    for caso in ET.parse(xml).getroot().iter("testcase"):
        categoria = CATEGORIAS_DE_TESTE[caso.get("classname").split(".")[-1]]
        falhou = caso.find("failure") is not None or caso.find("error") is not None
        categorias[categoria]["total"] += 1
        categorias[categoria]["aprovados"] += 0 if falhou else 1
        if falhou:
            reprovados.append(f"{categoria}: {caso.get('name')}")
    total = sum(c["total"] for c in categorias.values())
    aprovados = sum(c["aprovados"] for c in categorias.values())
    with open(cobertura, encoding="utf-8") as arquivo:
        totais = json.load(arquivo)["totals"]
    return {
        "total": total, "aprovados": aprovados, "reprovados": total - aprovados,
        "taxa_aprovacao_pct": round(100 * aprovados / total, 1),
        "por_categoria": categorias, "lista_reprovados": reprovados,
        "cobertura_linhas_pct": round(100 * totais["covered_lines"] / totais["num_statements"], 1),
        "cobertura_total_pct": round(totais["percent_covered"], 1),
    }


# -------------------------------------------------------- manutenibilidade
def funcoes_do_arquivo(codigo):
    """Lista as funções e métodos com sua complexidade ciclomática."""
    for bloco in cc_visit(codigo):
        if isinstance(bloco, Class):
            yield from bloco.methods
        else:
            yield bloco


def contar_docstrings(codigo):
    """Devolve (funções com docstring, total de funções) do código."""
    definicoes = [n for n in ast.walk(ast.parse(codigo)) if isinstance(n, (ast.FunctionDef, ast.AsyncFunctionDef))]
    return sum(1 for d in definicoes if ast.get_docstring(d)), len(definicoes)


def medir_manutenibilidade(versao):
    """Complexidade ciclomática, índice de manutenibilidade e tamanho do código (radon)."""
    funcoes, indices, linhas, modulos = [], [], 0, {}
    documentadas, definidas = 0, 0
    for caminho in arquivos_python(versao):
        with open(caminho, encoding="utf-8") as arquivo:
            codigo = arquivo.read()
        nome = os.path.relpath(caminho, VERSOES[versao]["pasta"]).replace(os.sep, "/")
        funcoes += [(f"{nome}:{f.name}", f.complexity) for f in funcoes_do_arquivo(codigo)]
        indice = mi_visit(codigo, multi=True)
        indices.append(indice)
        bruto = analyze(codigo)
        linhas += bruto.sloc
        com_docstring, total = contar_docstrings(codigo)
        documentadas, definidas = documentadas + com_docstring, definidas + total
        modulos[nome] = {"mi": round(indice, 1), "sloc": bruto.sloc}
    complexidades = [c for _, c in funcoes]
    return {
        "arquivos": len(modulos), "funcoes": len(funcoes), "linhas_de_codigo": linhas,
        "funcoes_documentadas_pct": round(100 * documentadas / definidas, 1),
        "complexidade_media": round(sum(complexidades) / len(complexidades), 2),
        "complexidade_maxima": max(complexidades),
        "funcao_mais_complexa": max(funcoes, key=lambda f: f[1])[0],
        "funcoes_complexidade_acima_10": sum(1 for c in complexidades if c > 10),
        "indice_manutenibilidade_medio": round(sum(indices) / len(indices), 1),
        "indice_manutenibilidade_minimo": round(min(indices), 1),
        "modulos": modulos,
    }


def medir_pylint(versao):
    """Nota (0 a 10) e quantidade de alertas do pylint, com a configuração padrão."""
    saida = executar([sys.executable, "-m", "pylint", *VERSOES[versao]["alvos_pylint"], "--score=y"],
                     pasta=VERSOES[versao]["pasta"])
    nota = re.search(r"rated at (-?[\d.]+)/10", saida)
    alertas = re.findall(r":\d+:\d+: ([CRWEF]\d{4}): ", saida)
    por_tipo = {}
    for codigo in alertas:
        por_tipo[codigo[0]] = por_tipo.get(codigo[0], 0) + 1
    return {"nota": float(nota.group(1)) if nota else None, "alertas": len(alertas), "por_tipo": por_tipo}


# ---------------------------------------------------------------- segurança
def medir_seguranca(versao):
    """Problemas de segurança encontrados pelo bandit, por severidade."""
    saida = executar([sys.executable, "-m", "bandit", "-r", VERSOES[versao]["pasta"], "-f", "json", "-q"])
    resultados = json.loads(saida)["results"] if saida.strip() else []
    severidade = {"HIGH": 0, "MEDIUM": 0, "LOW": 0}
    tipos = {}
    for problema in resultados:
        severidade[problema["issue_severity"]] += 1
        chave = f"{problema['test_id']} {problema['test_name']}"
        tipos[chave] = tipos.get(chave, 0) + 1
    return {"total": len(resultados), "alta": severidade["HIGH"], "media": severidade["MEDIUM"],
            "baixa": severidade["LOW"], "por_tipo": tipos}


# -------------------------------------------------------------------- main
def main():
    """Executa todas as medições e grava resultados/metricas.json."""
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--lighthouse", action="store_true", help="inclui a auditoria Lighthouse")
    parser.add_argument("--sem-carga", action="store_true", help="não executa o teste de carga")
    argumentos = parser.parse_args()
    os.makedirs(PASTA_RESULTADOS, exist_ok=True)

    metricas = {}
    for versao in VERSOES:
        print(f"Medindo {versao}: testes e cobertura...", flush=True)
        metricas[versao] = {"testes": medir_testes(versao)}
        print(f"Medindo {versao}: análise estática (radon, pylint, bandit)...", flush=True)
        metricas[versao]["manutenibilidade"] = medir_manutenibilidade(versao)
        metricas[versao]["pylint"] = medir_pylint(versao)
        metricas[versao]["seguranca"] = medir_seguranca(versao)

    pasta_qualidade = os.path.join(RAIZ, "qualidade")
    if not argumentos.sem_carga:
        print("Executando o teste de carga e de escalabilidade...", flush=True)
        subprocess.run([sys.executable, os.path.join(pasta_qualidade, "teste_carga.py")], cwd=RAIZ, check=True)
    if argumentos.lighthouse:
        print("Executando a auditoria Lighthouse...", flush=True)
        subprocess.run([sys.executable, os.path.join(pasta_qualidade, "auditoria_lighthouse.py")], cwd=RAIZ,
                       check=True)
    for nome in ("carga", "lighthouse"):
        caminho = os.path.join(PASTA_RESULTADOS, f"{nome}.json")
        if os.path.exists(caminho):
            with open(caminho, encoding="utf-8") as arquivo:
                metricas[nome] = json.load(arquivo)

    with open(os.path.join(PASTA_RESULTADOS, "metricas.json"), "w", encoding="utf-8") as arquivo:
        json.dump(metricas, arquivo, ensure_ascii=False, indent=2)
    imprimir_resumo(metricas)


def imprimir_resumo(metricas):
    """Mostra uma tabela-resumo no terminal."""
    linhas = [
        ("Testes aprovados (%)", lambda m: m["testes"]["taxa_aprovacao_pct"]),
        ("Cobertura de código (%)", lambda m: m["testes"]["cobertura_total_pct"]),
        ("Complexidade ciclomática média", lambda m: m["manutenibilidade"]["complexidade_media"]),
        ("Complexidade ciclomática máxima", lambda m: m["manutenibilidade"]["complexidade_maxima"]),
        ("Índice de manutenibilidade (médio)", lambda m: m["manutenibilidade"]["indice_manutenibilidade_medio"]),
        ("Funções documentadas (%)", lambda m: m["manutenibilidade"]["funcoes_documentadas_pct"]),
        ("Nota pylint (0-10)", lambda m: m["pylint"]["nota"]),
        ("Problemas de segurança (bandit)", lambda m: m["seguranca"]["total"]),
    ]
    print(f"\n{'Métrica':40} {'v1 (antes)':>12} {'v2 (depois)':>12}")
    for titulo, obter in linhas:
        print(f"{titulo:40} {obter(metricas['v1']):>12} {obter(metricas['v2']):>12}")
    if "carga" in metricas:
        carga = metricas["carga"]["carga"]
        print(f"{'Tempo de resposta p95 (ms)':40} {carga['v1']['p95_ms']:>12} {carga['v2']['p95_ms']:>12}")
        print(f"{'Vazão (requisições/s)':40} {carga['v1']['vazao_req_s']:>12} {carga['v2']['vazao_req_s']:>12}")


if __name__ == "__main__":
    main()
