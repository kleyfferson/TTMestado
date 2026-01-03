import gzip
import csv
import re
import argparse
from collections import Counter, defaultdict
from pathlib import Path

def parse_hierarchical_trace(input_file: str):
    """
    Processa o arquivo de tracing, lidando com retornos de objetos multi-linha.
    """
    if not Path(input_file).exists():
        print(f"Erro: Arquivo de entrada não encontrado: {input_file}")
        return None, None

    function_calls = Counter()
    return_values = defaultdict(list)

    call_pattern = re.compile(r"^\s*[>]*\s*([\w<>.-]+)\s+in\s+([\w./\\<>-]+)")
    
    return_pattern = re.compile(r"^\s*[<]*\s*([\w<>.-]+)\s+returned:\s*(.*)")

    try:
        with gzip.open(input_file, 'rt', encoding="utf-8") as f:
            lines = iter(f)
            for line in lines:
                call_match = call_pattern.match(line)
                if call_match:
                    func_name, file_name = call_match.groups()
                    unique_key = f"{file_name.strip()}::{func_name.strip()}"
                    function_calls[unique_key] += 1
                    continue

                return_match = return_pattern.match(line)
                if return_match:
                    func_name, return_value = return_match.groups()
                    func_name = func_name.strip()
                    full_return_value = [return_value.strip()]

                    if return_value.strip().startswith('Class <'):
                        while True:
                            try:
                                next_line = next(lines)
                                if not call_pattern.match(next_line) and not return_pattern.match(next_line):
                                    full_return_value.append(next_line.strip())
                                else:
                                    from itertools import chain
                                    lines = chain([next_line], lines)
                                    break
                            except StopIteration:
                                break
                    
                    final_return_str = "\n".join(full_return_value)
                    return_values[func_name].append(final_return_str)

    except Exception as e:
        print(f"Erro ao processar o arquivo de trace '{input_file}': {e}")
        return None, None
    
    unique_return_values = defaultdict(set)
    for func, values in return_values.items():
        unique_return_values[func] = set(values)

    return function_calls, unique_return_values

def save_to_csv(output_file: str, function_calls: Counter, return_values: defaultdict):
    """
    Salva os resultados de frequência e valores de retorno em um arquivo CSV.
    """
    if not function_calls:
        print("Nenhuma chamada de função foi extraída. O arquivo CSV não será gerado.")
        return

    try:
        with open(output_file, mode='w', newline='', encoding='utf-8') as csv_file:
            writer = csv.writer(csv_file)
            writer.writerow(['Function', 'Call_Frequency', 'Unique_Return_Values'])
            
            for func_key, count in sorted(function_calls.items()):
                func_name_only = func_key.split("::")[-1]
                unique_returns_set = return_values.get(func_name_only, set())
                returns_str = " | ".join(sorted(list(unique_returns_set)))
                writer.writerow([func_key, count, returns_str])
        
        print(f"Análise concluída. Resultados salvos em {output_file}")
    except Exception as e:
        print(f"Erro ao escrever o arquivo CSV '{output_file}': {e}")

def main():
    parser = argparse.ArgumentParser(description="Analisa um arquivo compactado de tracing hierárquico.")
    parser.add_argument('--input_file', required=True, help="Caminho do arquivo .gz de entrada.")
    parser.add_argument('--output_file', required=True, help="Caminho do arquivo CSV de saída.")
    args = parser.parse_args()

    print(f"Processando arquivo: {args.input_file}")
    function_calls, return_values = parse_hierarchical_trace(args.input_file)
    if function_calls:
        save_to_csv(args.output_file, function_calls, return_values)
    else:
        print("Processamento do arquivo de trace não gerou dados.")

if __name__ == "__main__":
    main()