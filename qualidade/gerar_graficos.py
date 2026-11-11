"""Gera os gráficos comparativos (antes x depois) a partir de resultados/metricas.json.

Uso:
    python qualidade/gerar_graficos.py

As imagens são gravadas em qualidade/resultados/graficos/.
"""
import json
import logging
import os

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402  pylint: disable=wrong-import-position
from matplotlib.ticker import FuncFormatter, MaxNLocator  # noqa: E402  pylint: disable=wrong-import-position

logging.getLogger("matplotlib.font_manager").setLevel(logging.ERROR)  # avisos de fonte ausente

RAIZ = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
PASTA_RESULTADOS = os.path.join(RAIZ, "qualidade", "resultados")
PASTA_GRAFICOS = os.path.join(PASTA_RESULTADOS, "graficos")

# Paleta categórica validada para daltonismo (ordem fixa) e tons de texto/eixos
SUPERFICIE = "#ffffff"
TEXTO = "#0b0b0b"
TEXTO_SECUNDARIO = "#52514e"
GRADE = "#e1e0d9"
EIXO = "#c3c2b7"
CORES = {"v1": "#2a78d6", "v2": "#eb6834", "v2_sem_paginacao": "#1baf7a"}
NOMES = {"v1": "Versão 1.0 (antes)", "v2": "Versão 2.0 (depois)",
         "v2_sem_paginacao": "Versão 2.0 sem paginação"}

plt.rcParams.update({
    "font.family": ["Arial", "Liberation Sans", "DejaVu Sans"],
    "font.size": 9,
    "axes.edgecolor": EIXO,
    "axes.labelcolor": TEXTO_SECUNDARIO,
    "axes.titlesize": 10,
    "axes.titleweight": "bold",
    "axes.titlecolor": TEXTO,
    "xtick.color": TEXTO_SECUNDARIO,
    "ytick.color": TEXTO_SECUNDARIO,
    "figure.facecolor": SUPERFICIE,
    "axes.facecolor": SUPERFICIE,
    "savefig.facecolor": SUPERFICIE,
    "legend.frameon": False,
})


def formatar(valor, casas=1, sufixo=""):
    """Número no padrão brasileiro (vírgula decimal)."""
    texto = f"{valor:,.{casas}f}".replace(",", "X").replace(".", ",").replace("X", ".")
    return texto + sufixo


def preparar_eixo(eixo, titulo=None, rotulo_y=None):
    """Grade horizontal discreta, sem molduras desnecessárias."""
    if titulo:
        eixo.set_title(titulo, loc="left", pad=10)
    if rotulo_y:
        eixo.set_ylabel(rotulo_y)
    eixo.grid(axis="y", color=GRADE, linewidth=0.8)
    eixo.set_axisbelow(True)
    eixo.yaxis.set_major_locator(MaxNLocator(nbins=6, integer=True))
    eixo.yaxis.set_major_formatter(FuncFormatter(lambda valor, _: formatar(valor, 0)))
    for lado in ("top", "right", "left"):
        eixo.spines[lado].set_visible(False)
    eixo.tick_params(axis="y", length=0)


def barras_agrupadas(eixo, categorias, series, casas=1, sufixo=""):
    """Barras lado a lado (uma cor por versão) com o valor escrito na ponta."""
    quantidade = len(series)
    largura = min(0.8 / quantidade, 0.28)
    for indice, (versao, valores) in enumerate(series.items()):
        deslocamento = (indice - (quantidade - 1) / 2) * largura
        posicoes = [i + deslocamento for i in range(len(categorias))]
        barras = eixo.bar(posicoes, valores, largura, color=CORES[versao], label=NOMES[versao],
                          edgecolor=SUPERFICIE, linewidth=1.5)
        for barra, valor in zip(barras, valores):
            eixo.annotate(formatar(valor, casas, sufixo), (barra.get_x() + barra.get_width() / 2, barra.get_height()),
                          xytext=(0, 3), textcoords="offset points", ha="center", va="bottom",
                          fontsize=8, color=TEXTO)
    eixo.set_xticks(range(len(categorias)))
    eixo.set_xticklabels(categorias)
    eixo.margins(y=0.15)


def salvar(figura, nome):
    """Grava o gráfico em PNG (200 dpi)."""
    os.makedirs(PASTA_GRAFICOS, exist_ok=True)
    caminho = os.path.join(PASTA_GRAFICOS, nome)
    figura.savefig(caminho, dpi=200, bbox_inches="tight")
    plt.close(figura)
    print("Gráfico gerado:", caminho)


def grafico_testes(m):
    """Percentual de testes aprovados por categoria."""
    categorias = ["Funcionais", "Segurança", "Robustez", "Total"]
    chaves = ["funcionais", "seguranca", "robustez"]
    series = {}
    for versao in ("v1", "v2"):
        testes = m[versao]["testes"]
        valores = [100 * testes["por_categoria"][c]["aprovados"] / testes["por_categoria"][c]["total"] for c in chaves]
        series[versao] = valores + [testes["taxa_aprovacao_pct"]]
    figura, eixo = plt.subplots(figsize=(6.3, 3.0))
    barras_agrupadas(eixo, categorias, series, casas=1, sufixo="%")
    preparar_eixo(eixo, rotulo_y="Testes aprovados (%)")
    eixo.set_ylim(0, 115)
    eixo.legend(loc="upper left", ncol=2, bbox_to_anchor=(0, 1.12))
    salvar(figura, "testes.png")


def grafico_seguranca(m):
    """Problemas de segurança encontrados pelo bandit, por severidade."""
    categorias = ["Alta", "Média", "Baixa"]
    series = {v: [m[v]["seguranca"]["alta"], m[v]["seguranca"]["media"], m[v]["seguranca"]["baixa"]]
              for v in ("v1", "v2")}
    figura, eixo = plt.subplots(figsize=(6.3, 2.8))
    barras_agrupadas(eixo, categorias, series, casas=0)
    preparar_eixo(eixo, rotulo_y="Ocorrências (bandit)")
    eixo.set_xlabel("Severidade")
    eixo.legend(loc="upper right")
    salvar(figura, "seguranca.png")


def grafico_manutenibilidade(m):
    """Três indicadores de manutenibilidade em painéis separados (escalas diferentes)."""
    paineis = [
        ("Complexidade ciclomática\nmáxima (menor é melhor)",
         lambda v: m[v]["manutenibilidade"]["complexidade_maxima"], 0),
        ("Índice de manutenibilidade\nmédio, 0-100 (maior é melhor)",
         lambda v: m[v]["manutenibilidade"]["indice_manutenibilidade_medio"], 1),
        ("Nota do pylint, 0-10\n(maior é melhor)", lambda v: m[v]["pylint"]["nota"], 2),
    ]
    figura, eixos = plt.subplots(1, 3, figsize=(6.3, 2.9))
    for eixo, (titulo, obter, casas) in zip(eixos, paineis):
        valores = [obter("v1"), obter("v2")]
        barras = eixo.bar([0, 1], valores, 0.5, color=[CORES["v1"], CORES["v2"]], edgecolor=SUPERFICIE)
        for barra, valor in zip(barras, valores):
            eixo.annotate(formatar(valor, casas), (barra.get_x() + barra.get_width() / 2, barra.get_height()),
                          xytext=(0, 3), textcoords="offset points", ha="center", fontsize=8, color=TEXTO)
        eixo.set_xticks([0, 1])
        eixo.set_xticklabels(["v1.0", "v2.0"])
        eixo.set_title(titulo, fontsize=8.5, loc="left")
        preparar_eixo(eixo)
        eixo.margins(y=0.2)
    figura.legend(handles=[plt.Rectangle((0, 0), 1, 1, color=CORES[v]) for v in ("v1", "v2")],
                  labels=[NOMES["v1"], NOMES["v2"]], loc="lower center", ncol=2, bbox_to_anchor=(0.5, -0.06))
    figura.tight_layout()
    salvar(figura, "manutenibilidade.png")


def grafico_desempenho(m):
    """Tempo de resposta p95 e vazão no teste de carga (painéis separados)."""
    carga = m["carga"]["carga"]
    versoes = [v for v in ("v1", "v2", "v2_sem_paginacao") if v in carga]
    figura, eixos = plt.subplots(1, 2, figsize=(6.3, 2.9))
    paineis = [("Tempo de resposta p95 (ms)\n(menor é melhor)", "p95_ms", 0),
               ("Vazão (requisições/s)\n(maior é melhor)", "vazao_req_s", 0)]
    for eixo, (titulo, chave, casas) in zip(eixos, paineis):
        valores = [carga[v][chave] for v in versoes]
        barras = eixo.bar(range(len(versoes)), valores, 0.55, color=[CORES[v] for v in versoes], edgecolor=SUPERFICIE)
        for barra, valor in zip(barras, valores):
            eixo.annotate(formatar(valor, casas), (barra.get_x() + barra.get_width() / 2, barra.get_height()),
                          xytext=(0, 3), textcoords="offset points", ha="center", fontsize=8, color=TEXTO)
        eixo.set_xticks(range(len(versoes)))
        eixo.set_xticklabels(["v1.0", "v2.0", "v2.0 sem\npaginação"][:len(versoes)])
        eixo.set_title(titulo, fontsize=8.5, loc="left")
        preparar_eixo(eixo)
        eixo.margins(y=0.2)
    figura.legend(handles=[plt.Rectangle((0, 0), 1, 1, color=CORES[v]) for v in versoes],
                  labels=[NOMES[v] for v in versoes], loc="lower center", ncol=3, bbox_to_anchor=(0.5, -0.08))
    figura.tight_layout()
    salvar(figura, "desempenho.png")


def grafico_escalabilidade(m):
    """Tempo para abrir a lista de reservas conforme o banco cresce."""
    escala = m["carga"]["escalabilidade"]
    figura, eixo = plt.subplots(figsize=(6.3, 3.0))
    for versao in ("v1", "v2"):
        tamanhos = [int(t) for t in escala[versao]]
        tempos = list(escala[versao].values())
        eixo.plot(tamanhos, tempos, color=CORES[versao], linewidth=2, marker="o", markersize=6,
                  markeredgecolor=SUPERFICIE, markeredgewidth=1.5, label=NOMES[versao],
                  solid_capstyle="round", solid_joinstyle="round")
        eixo.annotate(formatar(tempos[-1], 1, " ms"), (tamanhos[-1], tempos[-1]), xytext=(6, 0),
                      textcoords="offset points", va="center", fontsize=8, color=TEXTO)
    preparar_eixo(eixo, rotulo_y="Tempo de resposta (ms)")
    eixo.set_xlabel("Quantidade de reservas cadastradas")
    eixo.set_xticks([0, 2500, 5000, 7500, 10000])
    eixo.set_xticklabels([formatar(t, 0) for t in (0, 2500, 5000, 7500, 10000)])
    eixo.set_xlim(0, 11500)
    eixo.set_ylim(bottom=0)
    eixo.legend(loc="upper left")
    salvar(figura, "escalabilidade.png")


def grafico_lighthouse(m):
    """Notas do Lighthouse (acessibilidade e boas práticas) por página."""
    if "lighthouse" not in m:
        return
    paginas = list(m["lighthouse"]["v1"].keys())
    figura, eixos = plt.subplots(1, 2, figsize=(6.3, 2.9), sharey=True)
    for eixo, (categoria, titulo) in zip(eixos, [("accessibility", "Acessibilidade"),
                                                ("best-practices", "Boas práticas")]):
        series = {v: [m["lighthouse"][v][p]["notas"][categoria] for p in paginas] for v in ("v1", "v2")}
        barras_agrupadas(eixo, [p.replace(" de ", "\nde ").replace("Nova ", "Nova\n") for p in paginas],
                         series, casas=0)
        preparar_eixo(eixo, titulo=titulo)
        eixo.set_ylim(0, 115)
    eixos[0].set_ylabel("Nota Lighthouse (0-100)")
    figura.legend(handles=[plt.Rectangle((0, 0), 1, 1, color=CORES[v]) for v in ("v1", "v2")],
                  labels=[NOMES["v1"], NOMES["v2"]], loc="lower center", ncol=2, bbox_to_anchor=(0.5, -0.1))
    figura.tight_layout()
    salvar(figura, "lighthouse.png")


def main():
    """Lê as métricas e gera todos os gráficos."""
    with open(os.path.join(PASTA_RESULTADOS, "metricas.json"), encoding="utf-8") as arquivo:
        metricas = json.load(arquivo)
    grafico_testes(metricas)
    grafico_seguranca(metricas)
    grafico_manutenibilidade(metricas)
    if "carga" in metricas:
        grafico_desempenho(metricas)
        grafico_escalabilidade(metricas)
    grafico_lighthouse(metricas)


if __name__ == "__main__":
    main()
