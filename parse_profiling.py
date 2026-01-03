import csv
import re
import argparse

def parse_profiling_data(input_file: str, output_file: str):
    with open(input_file, 'r') as f:
        lines = f.readlines()

    # Lista para armazenar os dados extraídos
    profiling_data = []

    # Regex para capturar os dados relevantes
    regex = r"(\d+)\s+([\d\.]+)\s+([\d\.]+)\s+([\d\.]+)\s+([\d\.]+)\s+(.*)"

    for line in lines:
        line = line.strip()
        # Ignorar as linhas de cabeçalho e vazias
        if not line or "function calls" in line or "Ordered by" in line:
            continue
        match = re.match(regex, line)
        if match:
            # Adiciona os dados extraídos à lista
            profiling_data.append(match.groups())

    # Escrever os dados extraídos em um arquivo CSV
    with open(output_file, 'w', newline='') as csvfile:
        csv_writer = csv.writer(csvfile)
        # Escrever cabeçalho
        csv_writer.writerow(['ncalls', 'tottime', 'percall', 'cumtime', 'percall (cum)', 'filename:lineno(function)'])
        # Escrever os dados
        csv_writer.writerows(profiling_data)

def main():
    parser = argparse.ArgumentParser(description="Converte um arquivo de perfilamento de texto para CSV")
    parser.add_argument("--input_file", help="Arquivo de entrada com dados de perfilamento (TXT)")
    parser.add_argument("--output_file", help="Arquivo de saída para os dados (CSV)")
    args = parser.parse_args()

    if args.input_file and args.output_file:
        parse_profiling_data(args.input_file, args.output_file)
    else:
        print("Erro: Você deve fornecer --input_file e --output_file.")


if __name__ == "__main__":
    main()
