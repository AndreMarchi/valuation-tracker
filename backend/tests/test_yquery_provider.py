# backend/tests/test_yquery_provider.py (ou apenas test_yquery_provider.py)
import sys
import os
import pytest
import json

# Garante que o Python encontre a pasta 'dados' se rodar pela raiz
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from dados.yquery_provider import buscar_dados_acao_yq, _cache

# ==========================================
# 🧪 TESTES AUTOMATIZADOS (Para rodar com Pytest)
# ==========================================

def test_buscar_dados_acao_yq_sucesso():
    """Testa se o provedor consegue buscar dados reais de uma ação de alta liquidez."""
    ticker = "WEGE3"
    dados = buscar_dados_acao_yq(ticker)
    
    # Validações estruturais
    assert isinstance(dados, dict), "O retorno deve ser um dicionário"
    assert dados["ticker"] == "WEGE3", "O ticker retornado deve ser exato"
    
    # Validações financeiras essenciais
    assert dados["preco_atual"] > 0, "O preço atual deve ser maior que zero"
    assert dados["lpa"] != 0, "O LPA (Lucro Por Ação) não deve ser zero para a Weg"
    assert "lucro_liquido_recente" in dados, "A chave do lucro líquido deve existir"
    assert "fco_recente" in dados, "A chave do FCO (Fluxo de Caixa) deve existir"

def test_buscar_dados_acao_yq_invalido():
    """Testa o comportamento do provedor ao buscar um ticker inexistente."""
    ticker_falso = "ABACATE99"
    
    with pytest.raises(ValueError) as excinfo:
        buscar_dados_acao_yq(ticker_falso)
    
    assert "não encontrado" in str(excinfo.value).lower()

def test_cache_yquery():
    """Testa se a memória em cache está funcionando e evitando requisições duplicadas."""
    ticker = "ITUB4"
    
    # Limpa o cache para o teste
    _cache.clear()
    
    # Primeira chamada (vai na internet)
    dados_1 = buscar_dados_acao_yq(ticker)
    assert ticker in _cache, "O ticker deve ser salvo no cache"
    
    # Modifica o cache de propósito para provar que a segunda chamada não vai na internet
    _cache[ticker]["dados"]["preco_atual"] = 999.99
    
    # Segunda chamada (deve puxar do cache modificado)
    dados_2 = buscar_dados_acao_yq(ticker)
    assert dados_2["preco_atual"] == 999.99, "A segunda chamada ignorou o cache!"


# ==========================================
# 🛠️ MODO DE INSPEÇÃO MANUAL (Rodar direto no terminal)
# ==========================================
if __name__ == "__main__":
    print("Iniciando teste de conexão direta com o YahooQuery...\n")
    
    ticker_teste = "PETR4"
    
    try:
        print(f"⏳ Buscando dados completos para {ticker_teste}...")
        resultado = buscar_dados_acao_yq(ticker_teste)
        
        print("\n✅ SUCESSO! Dados obtidos:\n")
        # Imprime o JSON de forma bonita e indentada
        print(json.dumps(resultado, indent=4, ensure_ascii=False))
        
        print("\n🔍 Checagem de Qualidade Rápida:")
        print(f"Preço: R$ {resultado['preco_atual']}")
        print(f"P/L: {resultado['pl']}x")
        print(f"FCO (Fluxo de Caixa Operacional): {resultado['fco_recente']}")
        
    except Exception as e:
        print(f"\n❌ ERRO DURANTE O TESTE: {e}")