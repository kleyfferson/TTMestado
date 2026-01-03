import json
import csv
import argparse
import re

def parse_coverage_data(input_file: str, output_file: str, test_result: str):
    """Extrai dados de cobertura de arquivos JSON e escreve em um arquivo CSV."""
    coverage_data = []
    pattern = r"Test-([^/]+)/([^/]+)/Run-(\d+)"
    match = re.search(pattern, input_file)

    try:
        if not match:
            print(f"Aviso: Padrão de nome de teste não encontrado em '{input_file}'. Usando nomes genéricos.")
            test_dir, test_name, count = "unknown_project", "unknown_test", "0"
        else:
            test_dir = match.group(1)
            test_name = match.group(2)
            count = match.group(3)
            
        with open(input_file, 'r') as f:
            json_data = json.load(f)
        
        if "totals" in json_data:
            totals = json_data["totals"]
            percent_covered = totals.get("percent_covered", 0.0)
            covered_lines = totals.get("covered_lines", 0)
            
            coverage_data.append([test_dir, test_name, count, test_result, percent_covered, covered_lines])
        else:
            print(f"Chave 'totals' não encontrada no arquivo: {input_file}")
    
    except FileNotFoundError:
        print(f"Erro: Arquivo '{input_file}' não encontrado.")
    except json.JSONDecodeError:
        print(f"Erro: Arquivo '{input_file}' não é um JSON válido.")
    except Exception as e:
        print(f"Erro desconhecido ao processar o arquivo '{input_file}': {e}")

    with open(output_file, 'w', newline='') as csvfile:
        csv_writer = csv.writer(csvfile)
        csv_writer.writerow(['Project Name', 'Test name', 'Run', 'Test Result', 'Percentual de Cobertura (%)', 'Linhas Cobertas'])
        csv_writer.writerows(coverage_data)

def main():
    parser = argparse.ArgumentParser(description="Converte arquivos JSON de cobertura para CSV.")
    parser.add_argument("--input_file", required=True, help="Arquivo de entrada (JSON) com dados de cobertura.")
    parser.add_argument("--output_file", required=True, help="Arquivo de saída para os dados (CSV).")
    parser.add_argument("--result", required=True, help="O resultado do teste (ex: PASSED, FAILED).")
    args = parser.parse_args()

    parse_coverage_data(args.input_file, args.output_file, args.result)


if __name__ == "__main__":
    main()