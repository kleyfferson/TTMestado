# Framework de Análise de Testes Flaky (Mestrado)

Este projeto é uma ferramenta automatizada desenvolvida para a identificação, reprodução e análise de causas raiz de testes instáveis (Flaky Tests) em repositórios Python.

O sistema não apenas detecta a instabilidade, mas coleta métricas profundas de execução (**Coverage, Profiling e Tracing**) para permitir uma comparação diferencial entre execuções que passaram (`PASSED`) e execuções que falharam (`FAILED`).

## 🚀 Funcionalidades Principais

O framework opera em três camadas de análise simultâneas:

1.  **Tracing (Rastreamento de Execução):**
    * Intercepta cada chamada de função e seu valor de retorno.
    * Gera logs hierárquicos para visualizar o fluxo exato do código.
    * Permite identificar se valores não-determinísticos (ex: timestamps, random) alteraram o fluxo.

2.  **Profiling (Perfilamento de Desempenho):**
    * Utiliza `cProfile` para medir o tempo de execução e número de chamadas de cada função.
    * Essencial para detectar *flakiness* causado por *race conditions* ou *timeouts*.

3.  **Code Coverage (Cobertura de Código):**
    * Mapeia quais linhas de código foram executadas em cada rodada.
    * Identifica se caminhos de código distintos foram tomados entre execuções de sucesso e falha.

---

## 🛠️ Arquitetura do Sistema

O sistema foi desenhado para garantir **isolamento total** e **reprodutibilidade**.

### 1. Orquestrador (`main.py`)
O script principal que gerencia o fluxo de trabalho:
* Lê a lista de projetos/testes alvo.
* Gerencia a clonagem dos repositórios.
* Instancia os ambientes virtuais.
* Despara as análises e invoca os comparadores (`diff_finder.py`).

### 2. Isolamento de Ambiente (`Analise/VirtualEnvironment.py`)
Para evitar conflitos de dependências entre o framework e os projetos analisados:
* Cada repositório clonado ganha seu próprio **Virtual Environment (venv)**.
* As dependências do projeto (`requirements.txt`) são instaladas isoladamente dentro desse venv.
* Os testes são executados via `subprocess` dentro desse ambiente fechado.

### 3. O "Super Plugin" (`Analise/TestResult.py`)
Esta é a peça central da coleta de dados. Trata-se de um plugin customizado para o `pytest` que:
* Atua como um *Hook* (gancho) durante a execução dos testes.
* Inicia os coletores (`sys.setprofile`, `sys.settrace`, `coverage`) **antes** de cada teste começar.
* Salva os artefatos (JSONs, CSVs, Logs) imediatamente **após** o teste terminar.
* Garante que a sobrecarga da análise interfira o mínimo possível no comportamento do teste.

### 4. Análise Diferencial (`diff_finder.py`)
Após as execuções (Runs), este módulo compara os artefatos gerados:
* Cruza dados da **Run X (Passou)** vs **Run Y (Falhou)**.
* Gera relatórios destacando: funções chamadas apenas em um cenário, diferenças nos valores de retorno e variação de tempo de execução.

---

## 📋 Pré-requisitos

* **Python 3.8+**
* **Git** instalado e configurado.
* Sistema operacional Linux ou MacOS (recomendado devido ao gerenciamento de processos).

### Instalação das Dependências do Framework

```bash
pip install -r requirements.txt
```

---

## ⚙️ Como Utilizar

### Passo 1: Preparar o Dataset
O framework espera um arquivo CSV com os testes a serem analisados.

### Passo 2: Executar a Análise
Para rodar a bateria completa (Tracing + Profiling + Coverage):

```bash
python3 main.py \
  --read-from-csv projetos_compativel.csv \
  --output-dir dataset_mestrado_full \
  --include-test-profiling True \
  --include-test-tracing True \
  --include-test-coverage True
```

### Argumentos Disponíveis
* `--read-from-csv`: Caminho do arquivo CSV de entrada.
* `--output-dir`: Pasta onde os resultados serão salvos.
* `--include-test-tracing`: Ativa/Desativa log de chamadas e retornos (`True`/`False`).
* `--include-test-profiling`: Ativa/Desativa análise de tempo e performance.
* `--include-test-coverage`: Ativa/Desativa análise de cobertura de linhas.

---

## 📂 Estrutura dos Resultados

Após a execução, a pasta de saída terá a seguinte estrutura:

```text
dataset_mestrado_full/
├── NomeDoRepositorio/
│   ├── Test-NomeDoTeste/
│   │   ├── Run-0/
│   │   │   ├── trace.log           # Dados brutos de tracing
│   │   │   ├── coverage.json       # Dados brutos de cobertura
│   │   │   ├── profiling.txt       # Dados brutos de profile
│   │   │   └── ...csv              # Dados processados
│   │   ├── Run-1/
│   │   ├── ...
│   │   ├── diff_reports/           # Relatórios comparativos (Pass vs Fail)
│   │   └── error_log.txt           # Logs caso algo tenha falhado
```

---

## 🤝 Contribuição e Autoria

Projeto desenvolvido no escopo de Mestrado para análise avançada de testes de software.
Branch atual de desenvolvimento: `projetos-TTMestado`.
