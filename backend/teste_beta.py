import json

# Importe o provedor que você está utilizando no momento
# Se estiver usando o yfinance, comente a linha do yquery e descomente a do yfinance
from dados.yquery_provider import buscar_dados_acao_yq as buscar_dados
# from dados.yfinance_provider import buscar_dados_acao_yf as buscar_dados

ticker = "PLPL3"

print(f"⏳ A consultar os servidores do Yahoo para {ticker}...")

try:
    # A consulta direta ignora o cache do main.py
    dados = buscar_dados(ticker)
    
    print("\n✅ SUCESSO! Dados de Risco Extraídos:")
    print("-" * 40)
    print(f"🎯 Beta:             {dados.get('beta')}")
    print(f"💰 Valor de Mercado: R$ {dados.get('valor_mercado'):,.2f}")
    print("-" * 40)
    
    # Imprime um trecho do JSON apenas para confirmar a estrutura
    extrato_json = {
        "ticker": dados.get("ticker"),
        "beta": dados.get("beta"),
        "valor_mercado": dados.get("valor_mercado")
    }
    print("\nEstrutura JSON devolvida pelo provedor:")
    print(json.dumps(extrato_json, indent=4))
    
except Exception as e:
    print(f"\n❌ ERRO DURANTE O TESTE: {e}")