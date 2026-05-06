from valuation.score import calcular_score

# Resultados simulados para os testes
GRAHAM_DESCONTADA  = {"classificacao": "Descontada"}
GRAHAM_CARA        = {"classificacao": "Cara"}
BAZIN_DESCONTADA   = {"classificacao": "Descontada"}
BAZIN_NAO_APLICAVEL= {"classificacao": "Não aplicável"}
DCF_DESCONTADA     = {"classificacao": "Descontada"}
DCF_CARA           = {"classificacao": "Cara"}

MULTIPLOS_DESCONTADO = {"pl": {"classificacao": "Descontada"},
                        "pvp": {"classificacao": "Descontada"}}
MULTIPLOS_CARO       = {"pl": {"classificacao": "Cara"},
                        "pvp": {"classificacao": "Cara"}}
MULTIPLOS_MISTO      = {"pl": {"classificacao": "Descontada"},
                        "pvp": {"classificacao": "Cara"}}


def test_score_muito_atrativa():
    """Todos os métodos descontados — score deve ser >= 8."""
    resultado = calcular_score(
        graham=GRAHAM_DESCONTADA,
        bazin=BAZIN_DESCONTADA,
        multiplos=MULTIPLOS_DESCONTADO,
        dcf=DCF_DESCONTADA,
    )
    assert resultado["score"] >= 8
    assert resultado["classificacao"] == "Muito Atrativa"


def test_score_cara():
    """Todos os métodos caros — score deve ser 0."""
    resultado = calcular_score(
        graham=GRAHAM_CARA,
        bazin=BAZIN_NAO_APLICAVEL,
        multiplos=MULTIPLOS_CARO,
        dcf=DCF_CARA,
    )
    assert resultado["score"] == 0.0
    assert resultado["classificacao"] == "Cara / Evitar"


def test_score_ignora_nao_aplicavel():
    """Métodos não aplicáveis não devem influenciar o score."""
    resultado_sem = calcular_score(
        graham=GRAHAM_DESCONTADA,
        bazin=BAZIN_NAO_APLICAVEL,
        multiplos=MULTIPLOS_DESCONTADO,
        dcf=DCF_DESCONTADA,
    )
    resultado_com = calcular_score(
        graham=GRAHAM_DESCONTADA,
        bazin=BAZIN_DESCONTADA,
        multiplos=MULTIPLOS_DESCONTADO,
        dcf=DCF_DESCONTADA,
    )
    # Sem Bazin o score ainda deve ser muito atrativo
    assert resultado_sem["score"] >= 8
    # Com Bazin o score deve ser igual ou melhor
    assert resultado_com["score"] >= resultado_sem["score"]


def test_score_entre_0_e_10():
    """Score deve sempre estar entre 0 e 10."""
    resultado = calcular_score(
        graham=GRAHAM_DESCONTADA,
        bazin=BAZIN_DESCONTADA,
        multiplos=MULTIPLOS_MISTO,
        dcf=DCF_CARA,
    )
    assert 0 <= resultado["score"] <= 10


def test_score_metodos_aplicados():
    """Deve informar quantos métodos foram usados no cálculo."""
    resultado = calcular_score(
        graham=GRAHAM_DESCONTADA,
        bazin=BAZIN_NAO_APLICAVEL,
        multiplos=MULTIPLOS_DESCONTADO,
        dcf=DCF_DESCONTADA,
    )
    assert resultado["metodos_aplicados"] == 4  # pl e pvp contam separado