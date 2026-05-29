import pytest
from valuation.risco import analisar_risco

def test_risco_empresa_em_recuperacao_judicial_rebaixa_classificacao():
    """Garante que se a ação for LIGT3, o sistema aplica punição severa e força classificação de risco."""
    # Um score inicial teórico muito forte (ex: 8.5) simulando múltiplos baratos
    resultado = analisar_risco(ticker="LIGT3", setor="Energia Elétrica", score_atual=8.5)
    
    assert resultado["em_recuperacao_judicial"] is True
    
    # CORREÇÃO DA SOMA: 6.0 (Recuperação Judicial) + 1.0 (Setor Regulado) = 7.0
    assert resultado["penalizacao"] == 7.0  
    
    # Score ajustado: 8.5 (inicial) - 7.0 (penalização) = 1.5
    assert resultado["score_ajustado"] == 1.5  
    
    assert resultado["classificacao_ajustada"] == "Alto Risco / Evitar"
    
    # Certifica que a mensagem de aviso crítico foi anexada ao payload
    assert any(a["nivel"] == "critico" for a in resultado["alertas"])

def test_risco_empresa_estatal():
    """Valida o desconto e o alerta de controle estatal para BBAS3."""
    resultado = analisar_risco(ticker="BBAS3", setor="Bancos", score_atual=7.0)
    
    assert resultado["is_estatal"] is True
    assert resultado["penalizacao"] == 2.0
    assert resultado["score_ajustado"] == 5.0
    assert resultado["classificacao_ajustada"] == "Neutra"