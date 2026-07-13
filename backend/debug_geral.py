import requests
import json
import os

# Ajuste a porta se o seu servidor FastAPI rodar em uma porta diferente (ex: 8080)
PORTA = 8000 
TICKER = "WIZC3" # Mude para TAEE3, PETR4, etc., para testar outras

URL = f"http://localhost:{PORTA}/api/valuation/{TICKER}"

print(f"🔍 Iniciando auditoria completa para {TICKER}...")

try:
    # Bate na rota principal do seu main.py
    resposta = requests.get(URL)
    resposta.raise_for_status() # Verifica se deu erro 500
    
    dados = resposta.json()
    
    # Salva o resultado num arquivo para você inspecionar com calma
    nome_arquivo = f"auditoria_{TICKER}.json"
    caminho = os.path.join(os.path.dirname(__file__), nome_arquivo)
    
    with open(caminho, 'w', encoding='utf-8') as f:
        json.dump(dados, f, ensure_ascii=False, indent=4)
        
    print(f"\n✅ SUCESSO! O Raio-X completo foi salvo em: {nome_arquivo}")
    print("Abra este arquivo no seu VS Code para depurar todas as variáveis.")
    
except requests.exceptions.ConnectionError:
    print("\n❌ ERRO: O servidor FastAPI não está rodando. Inicie-o primeiro!")
except Exception as e:
    print(f"\n❌ ERRO NA AUDITORIA: {e}")