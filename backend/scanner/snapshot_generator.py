import json
import time
from datetime import datetime
from valuation.engine import gerar_valuation_completo
from dados.provider import carregar_todos_tickers_b3

def gerar_snapshot_mercado():
    """
    Varre a B3, calcula o valuation e salva em JSON para leitura rápida do frontend.
    """
    tickers = carregar_todos_tickers_b3()
    print(f"🚀 Iniciando geração de snapshot para {len(tickers)} ativos...")
    
    snapshot = {
        "data_atualizacao": datetime.now().isoformat(),
        "total_ativos": len(tickers),
        "ativos": []
    }
    
    for ticker in tickers:
        print(f"📊 Processando: {ticker}")
        try:
            analise = gerar_valuation_completo(ticker)
            
            # Estrutura perfeita para o seu frontend (Tabela)
            snapshot["ativos"].append({
                "ticker": ticker,
                "score": analise["score"]["score"],
                "classificacao": analise["score"]["classificacao"],
                "preco": analise.get("preco_atual", 0),
                "setor": analise.get("setor", "N/A"),
                "beta": analise.get("beta", 1.0)
            })
            
            time.sleep(1.5) # Respeito às APIs
            
        except Exception as e:
            print(f"⚠️ Erro em {ticker}: {e}")
            continue
            
    # Salva o arquivo JSON final
    caminho_arquivo = "dados/snapshot_mercado.json"
    with open(caminho_arquivo, "w", encoding="utf-8") as f:
        json.dump(snapshot, f, indent=4, ensure_ascii=False)
        
    print(f"✅ Snapshot gerado com sucesso em {caminho_arquivo}!")

if __name__ == "__main__":
    gerar_snapshot_mercado()