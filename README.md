# AgendaLab – protótipo da APS “Avaliação e Melhoria da Qualidade em Sistemas de Software”

O AgendaLab é um sistema web de reserva de salas e laboratórios. Ele existe em duas versões:

| Pasta | Conteúdo |
|---|---|
| `v1_antes/` | Versão 1.0, desenvolvida rapidamente, só com foco em “funcionar” (linha de base da avaliação) |
| `v2_depois/` | Versão 2.0, com as melhorias de segurança, confiabilidade, desempenho, manutenibilidade e usabilidade |
| `testes/` | Suíte de testes automatizados (a **mesma** para as duas versões) |
| `qualidade/` | Scripts que medem a qualidade e geram os gráficos (os resultados são gravados em `qualidade/resultados/`) |

## 1. Preparar o ambiente (Windows)

Pré-requisito: Python 3.10 ou superior (`python --version`). No Prompt de Comando ou PowerShell:

```
git clone https://github.com/vinicius-gadanha/aps-qualidade-de-software.git
cd aps-qualidade-de-software
python -m venv .venv
.venv\Scripts\activate
pip install -r requirements-qualidade.txt
```

## 2. Executar as versões

Versão 1.0 (antes):

```
cd v1_antes
python app.py
```

Abra http://127.0.0.1:5000 e entre com `admin` / `admin123`.

Versão 2.0 (depois):

```
cd v2_depois
python executar.py --demo
```

Na primeira execução o programa pede a senha do usuário `admin` (mínimo de 8 caracteres, com letras e números).
O parâmetro `--demo` cadastra quatro salas de exemplo. Abra http://127.0.0.1:5000.

## 3. Rodar os testes

Na pasta raiz do repositório:

```
python -m pytest testes --versao=v1
python -m pytest testes --versao=v2
```

Resultado esperado: a versão 1.0 passa em 20 dos 49 testes; a versão 2.0 passa nos 49.

## 4. Medir a qualidade e gerar os gráficos

```
python qualidade/medir_qualidade.py
python qualidade/gerar_graficos.py
```

Os números ficam em `qualidade/resultados/metricas.json` e os gráficos em `qualidade/resultados/graficos/`.
O teste de carga leva cerca de 1 minuto. Para incluir a auditoria de acessibilidade do Google Lighthouse
(requer Node.js e Google Chrome instalados), use `python qualidade/medir_qualidade.py --lighthouse`.

Os valores medidos variam um pouco de computador para computador; a comparação entre as versões é o que importa.
