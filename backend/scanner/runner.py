import time
import csv
from valuation.engine import gerar_valuation_completo
from dados.provider import carregar_todos_tickers_b3

def rodar_scanner_b3():
    """Varre todos os ativos da B3 e gera um relatório de oportunidades."""
    tickers = carregar_todos_tickers_b3()
    print(f"🚀 Iniciando varredura em {len(tickers)} ativos da B3...")
    
    resultados = []
    
    for ticker in tickers:
        print(f"📊 Analisando: {ticker}")
        try:
            # Invoca o motor de cálculo que você já validou nos testes
            analise = gerar_valuation_completo(ticker)
            
            # Estrutura os dados que aparecerão na sua tabela
            resultados.append({
                "ticker": ticker,
                "score": analise["score"]["score"],
                "classificacao": analise["score"]["classificacao"],
                "preco": analise.get("preco_atual", 0),
                "setor": analise.get("setor", "N/A")
            })
            
            # Respeito às APIs: pausa de 2 segundos entre processamentos
            time.sleep(2) 
            
        except Exception as e:
            print(f"⚠️ Falha ao processar {ticker}: {e}")
            continue
            
    # Salva o arquivo CSV no diretório raiz do scanner
    caminho_saida = "scanner_results.csv"
    with open(caminho_saida, 'w', newline='', encoding='utf-8') as f:
        writer = csv.DictWriter(f, fieldnames=["ticker", "score", "classificacao", "preco", "setor"])
        writer.writeheader()
        writer.writerows(resultados)
        
    print(f"✅ Scanner concluído! {len(resultados)} ativos processados. Dados salvos em {caminho_saida}")

if __name__ == "__main__":
    rodar_scanner_b3()