from Analise import utils
from os import path
import os as os
from typing import List
import argparse
import csv
import subprocess
import shutil
from pathlib import Path
import re
import sys

def str_to_bool(value: str) -> bool:
    """Converte strings 'true', 't', '1' para True, e 'false', 'f', '0' para False."""
    if isinstance(value, bool):
        return value
    if value.lower() in {"true", "t", "1"}:
        return True
    elif value.lower() in {"false", "f", "0"}:
        return False
    else:
        raise argparse.ArgumentTypeError(f"Valor booleano invalido: {value}")

def str_to_int(value: str) -> int:
    """Converte string para inteiro positivo."""
    if value.isdigit() and int(value) > 0:
        return int(value)
    raise argparse.ArgumentTypeError(f"Valor inteiro invalido: {value}")

def argsDefiner():
    """Define, lê e processa os argumentos da linha de comando."""
    parser = argparse.ArgumentParser()

    # --- Definição dos Argumentos ---
    parser.add_argument("--repo-dir", help="Diretorio para o repositorio", type=str, default="")
    parser.add_argument("--repo-name", help="Nome do repositorio", type=str, default="")
    parser.add_argument("--read-from-csv", help="CSV com informações do repositório a ser lido", type=str, default="")
    parser.add_argument("--output-dir", help="Especificar o diretorio para onde os resultados de teste serao armazenados", default=".")
    parser.add_argument("--no-runs", help="Especificar a quantidade de rodadas que cada repositorio tera", type=str_to_int, default=1)
    parser.add_argument("--include-test-tracing", help="Executar tracing de cada teste", type=str_to_bool, default=False)
    parser.add_argument("--include-test-coverage", help="Executar coverage de cada teste", type=str_to_bool, default=False)
    parser.add_argument("--include-test-profiling", help="Realizar o profiling dos testes", type=str_to_bool, default=False)
    parser.add_argument("--run-specific-test", help="Rodar a ferramenta em testes específicos a partir de um CSV.", type=str, default="")
    parser.add_argument("--venv-path", help="Caminho para o diretório do ambiente virtual a ser usado", type=str, default="")

    args = parser.parse_args()

    # --- Processamento dos Argumentos ---
    csvFile = args.read_from_csv
    tracing = args.include_test_tracing
    coverage = args.include_test_coverage
    profiling = args.include_test_profiling
    specificTests = args.run_specific_test
    venvPath = args.venv_path

    # --- Lógica de Execução ---
    if specificTests:
        specificTests = path.abspath(specificTests)
        
        if not venvPath:
            raise ValueError("O argumento --venv-path é obrigatório ao usar --run-specific-test")
        
        with open(specificTests, "r", encoding="utf8") as csv_file:
            reader = list(csv.DictReader(csv_file, delimiter=","))
        
        if not reader:
            print("CSV de testes está vazio.")
        else:
            row = reader[0]
            try:
                repo_name = row["Name"]
                repo_hash = row["Hash"]
                repo_url = row["URL"]
                test_no_runs = int(float(row["No_Runs"]))
                test_node = row["Test"]

                repo = utils.Repository(
                    githash=repo_hash,
                    url=repo_url,
                    isgitrepo=True,
                    noruns=str(test_no_runs)
                )

                utils.runSpecificTests(
                    repo=repo, 
                    mod_name=repo_name,
                    params=[tracing, coverage, profiling],
                    test_node=test_node,
                    no_runs=test_no_runs,
                    env_path=Path(venvPath)
                )

                print(f"\n--- Iniciando pós-processamento com diff_finder.py ---")
                
                sanitized_test_name = re.sub(r'[^a-zA-Z0-9_\-]', '_', test_node.split("::")[-1])
                test_directory = path.join(os.getcwd(), f"Test-{repo_name}", sanitized_test_name)

                analise_tipo = ""
                coluna_chave = ""

                if profiling:
                    analise_tipo = "profiling"
                    coluna_chave = "filename:lineno(function)"
                elif tracing:
                    analise_tipo = "tracing"
                    coluna_chave = "Function"
                elif coverage:
                    analise_tipo = "coverage"
                    coluna_chave = "Percentual de Cobertura (%)"
                
                if analise_tipo:
                    python_executable = Path(venvPath) / "bin" / "python"
                    diff_finder_script = Path(os.getcwd()) / "diff_finder.py"

                    command = [
                        str(python_executable),
                        str(diff_finder_script),
                        test_directory,
                        analise_tipo,
                        str(test_no_runs),
                        coluna_chave
                    ]
                    
                    print(f"Executando comando: {' '.join(command)}")
                    try:
                        subprocess.run(command, check=True, text=True)
                        print("--- diff_finder.py executado com sucesso. ---")
                    except subprocess.CalledProcessError as e:
                        print("!!!!!! ERRO ao executar o diff_finder.py !!!!!!")
                        print(f"Comando: {' '.join(e.cmd)}")
                        print(f"Código de Saída: {e.returncode}")
                        print(f"Saída (stdout):\n{e.stdout}")
                        print(f"Erro (stderr):\n{e.stderr}\n")
                        raise 

            except Exception as e:
                print(f"Erro ao executar o teste ou pós-processamento: {e}")
                raise
            finally:
                with open(specificTests, mode="w", newline="", encoding='utf-8') as csv_file:
                    if reader:
                        fieldnames = reader[0].keys()
                        writer = csv.DictWriter(csv_file, fieldnames=fieldnames)
                        writer.writeheader()
                        if len(reader) > 1:
                            writer.writerows(reader[1:])
    else:
        print("Nenhum fluxo de teste específico foi solicitado.")

if __name__ == "__main__":
    argsDefiner()