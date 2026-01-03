import csv

# CONFIGURAÇÃO
ARQUIVO_ENTRADA = 'projeto.csv'           
ARQUIVO_SAIDA = 'projetos_compativel.csv' 
REPETICOES = 3                            

def converter():
    try:
        with open(ARQUIVO_ENTRADA, 'r', encoding='utf-8') as fin:
            reader = csv.DictReader(fin)
            dados_saida = []
            
            print(f"Convertendo {ARQUIVO_ENTRADA}...")
            for row in reader:
                nome = row.get('Projetos', '').strip()
                link = row.get('Repositório (Link)', '').strip()
                commit = row.get('Hash do Commit (Checkout)', '').strip()
                if not commit: commit = "." 

                if nome and link:
                    novo_item = {
                        'RepoName': nome,
                        'Repo': link,
                        'GitHash': commit,
                        '#Runs': REPETICOES
                    }
                    dados_saida.append(novo_item)
        
        campos = ['RepoName', 'Repo', 'GitHash', '#Runs']
        with open(ARQUIVO_SAIDA, 'w', newline='', encoding='utf-8') as fout:
            writer = csv.DictWriter(fout, fieldnames=campos)
            writer.writeheader()
            writer.writerows(dados_saida)
            
        print(f"Arquivo '{ARQUIVO_SAIDA}' gerado com sucesso!")
        
    except FileNotFoundError:
        print(f"Erro: Não encontrei o arquivo {ARQUIVO_ENTRADA}")

if __name__ == "__main__":
    converter()
