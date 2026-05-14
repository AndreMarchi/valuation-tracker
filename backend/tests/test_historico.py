from dados.historico import gerar_alertas_historicos


HISTORICO_BBDC3 = {
    "preco_minimo_5a":        8.50,
    "preco_maximo_5a":        19.20,
    "preco_medio_5a":         13.40,
    "crescimento_receita_5a": -0.029,
}

HISTORICO_SEM_DADOS = {
    "preco_minimo_5a":  None,
    "preco_maximo_5a":  None,
    "preco_medio_5a":   None,
    "crescimento_receita_5a": None,
}


def test_alerta_dcf_muito_acima_historico():
    """DCF 20%+ acima do máximo histórico deve gerar alerta alto."""
    dcf     = {"cenarios": {"otimista": 34.0, "base": 28.0, "pessimista": 22.0}}
    graham  = {"preco_justo": 15.0}
    bazin   = {"preco_justo": 14.0}
    alertas = gerar_alertas_historicos(HISTORICO_BBDC3, dcf, graham, bazin)
    tipos   = [a["tipo"] for a in alertas]
    assert "dcf_acima_historico" in tipos
    assert any(a["nivel"] == "alto" for a in alertas if a["tipo"] == "dcf_acima_historico")


def test_alerta_dcf_levemente_acima_maximo():
    """DCF levemente acima do máximo deve gerar alerta médio."""
    dcf     = {"cenarios": {"otimista": 25.0, "base": 20.5, "pessimista": 16.0}}
    graham  = {"preco_justo": 15.0}
    bazin   = {"preco_justo": 14.0}
    alertas = gerar_alertas_historicos(HISTORICO_BBDC3, dcf, graham, bazin)
    tipos   = [a["tipo"] for a in alertas]
    assert "dcf_acima_maximo" in tipos


def test_sem_alerta_dcf_dentro_historico():
    """DCF dentro do histórico não deve gerar alerta."""
    dcf     = {"cenarios": {"otimista": 18.0, "base": 14.0, "pessimista": 10.0}}
    graham  = {"preco_justo": 13.0}
    bazin   = {"preco_justo": 12.0}
    alertas = gerar_alertas_historicos(HISTORICO_BBDC3, dcf, graham, bazin)
    tipos   = [a["tipo"] for a in alertas]
    assert "dcf_acima_historico" not in tipos
    assert "dcf_acima_maximo"    not in tipos


def test_alerta_crescimento_negativo():
    """Crescimento negativo deve gerar alerta."""
    historico = {**HISTORICO_BBDC3, "crescimento_receita_5a": -0.10}
    dcf       = {"cenarios": {"otimista": 15.0, "base": 12.0, "pessimista": 9.0}}
    graham    = {"preco_justo": 13.0}
    bazin     = {"preco_justo": 12.0}
    alertas   = gerar_alertas_historicos(historico, dcf, graham, bazin)
    tipos     = [a["tipo"] for a in alertas]
    assert "crescimento_negativo" in tipos


def test_sem_dados_historicos_retorna_lista_vazia():
    """Sem dados históricos não deve gerar alertas."""
    dcf     = {"cenarios": {"otimista": 50.0, "base": 40.0, "pessimista": 30.0}}
    graham  = {"preco_justo": 45.0}
    bazin   = {"preco_justo": 40.0}
    alertas = gerar_alertas_historicos(HISTORICO_SEM_DADOS, dcf, graham, bazin)
    assert alertas == []