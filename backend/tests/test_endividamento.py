import pytest
from valuation.endividamento import analisar_endividamento


def test_endividamento_critico():
    """Dívida/EBIT acima de 5x deve gerar alerta crítico."""
    resultado = analisar_endividamento(
        div_liquida=100_000_000_000,
        ebit_12m=15_000_000_000,
        patrim_liq=40_000_000_000,
        score_atual=7.0,
    )
    tipos = [a["tipo"] for a in resultado["alertas"]]
    assert "endividamento_critico" in tipos
    assert resultado["penalizacao"] >= 2.5
    assert resultado["classificacao"] == "Crítico"


def test_endividamento_saudavel():
    """Dívida/EBIT abaixo de 2x não deve gerar alerta."""
    resultado = analisar_endividamento(
        div_liquida=10_000_000_000,
        ebit_12m=20_000_000_000,
        patrim_liq=40_000_000_000,
        score_atual=7.0,
    )
    assert resultado["penalizacao"] == 0.0
    assert resultado["alertas"] == []
    assert resultado["score_ajustado"] == 7.0
    assert resultado["classificacao"] == "Saudável"


def test_score_nao_vai_abaixo_de_zero():
    """Score ajustado nunca deve ser negativo."""
    resultado = analisar_endividamento(
        div_liquida=500_000_000_000,
        ebit_12m=10_000_000_000,
        patrim_liq=5_000_000_000,
        score_atual=2.0,
    )
    assert resultado["score_ajustado"] >= 0.0


def test_alavancagem_alta():
    """Dívida/Patrimônio acima de 2x deve gerar alerta."""
    resultado = analisar_endividamento(
        div_liquida=90_000_000_000,
        ebit_12m=30_000_000_000,
        patrim_liq=40_000_000_000,
        score_atual=7.0,
    )
    tipos = [a["tipo"] for a in resultado["alertas"]]
    assert "alavancagem_alta" in tipos
    # div_ebit=3.0x (exatamente 3, não > 3 -> "Moderado") mas
    # div_patrim=2.25x (> 2 -> "Alto") — confirma que a classificação usa o
    # PIOR dos dois níveis, não só o de Dívida/EBIT
    assert resultado["classificacao"] == "Alto"


# ─── classificacao usa vocabulário de RISCO DE ALAVANCAGEM ─────────────────
# Achado real: classificacao vinha de score_ajustado (limiares >=8 "Muito
# Atrativa", >=6 "Atrativa", >=4 "Neutra", senão "Cara / Evitar") —
# vocabulário de ATRATIVIDADE DE VALUATION, herdado por engano de um método
# de valuation. O frontend (App.tsx::SecaoEndividamento) sempre esperou
# "Crítico"/"Alto" pra colorir o card (nunca bateu, card sempre neutro
# mesmo com endividamento crítico). Corrigido na raiz: classificacao agora
# usa os mesmos limiares de div_ebit/div_patrim que já definem as
# penalizações/alertas. Ver CONTEXT.md.

def test_classificacao_moderado():
    """Dívida/EBIT entre 2x e 3x (exclusive) deve classificar como
    Moderado, não mais uma nota de atratividade."""
    resultado = analisar_endividamento(
        div_liquida=50_000_000_000,
        ebit_12m=20_000_000_000,  # div_ebit = 2.5x
        patrim_liq=100_000_000_000,  # div_patrim = 0.5x, saudável
        score_atual=7.0,
    )
    assert resultado["classificacao"] == "Moderado"


def test_classificacao_usa_o_pior_entre_ebit_e_patrimonio():
    """div_ebit saudável mas div_patrim crítico (ou vice-versa) — a
    classificação final tem que refletir o pior dos dois, não ignorar um
    deles."""
    # div_ebit = 1.0x (Saudável) / div_patrim = 5.0x (> 2, Alto)
    resultado = analisar_endividamento(
        div_liquida=10_000_000_000, ebit_12m=10_000_000_000, patrim_liq=2_000_000_000, score_atual=7.0,
    )
    assert resultado["classificacao"] == "Alto"


def test_classificacao_nao_usa_mais_vocabulario_de_atratividade():
    """Regressão: 'Muito Atrativa'/'Atrativa'/'Neutra'/'Cara / Evitar' não
    podem mais aparecer como classificacao de endividamento — esse
    vocabulário pertence a métodos de valuation (Graham/Bazin/DCF/score
    geral), não a uma leitura de risco de alavancagem."""
    vocabulario_antigo = {"Muito Atrativa", "Atrativa", "Neutra", "Cara / Evitar"}
    cenarios = [
        dict(div_liquida=100_000_000_000, ebit_12m=15_000_000_000, patrim_liq=40_000_000_000, score_atual=7.0),
        dict(div_liquida=10_000_000_000, ebit_12m=20_000_000_000, patrim_liq=40_000_000_000, score_atual=7.0),
        dict(div_liquida=0, ebit_12m=10_000_000_000, patrim_liq=10_000_000_000, score_atual=2.0),
    ]
    for kwargs in cenarios:
        resultado = analisar_endividamento(**kwargs)
        assert resultado["classificacao"] not in vocabulario_antigo
        assert resultado["classificacao"] in {"Crítico", "Alto", "Moderado", "Saudável"}


def test_sem_ebit_nao_quebra():
    """Sem EBIT disponível não deve lançar erro."""
    resultado = analisar_endividamento(
        div_liquida=50_000_000_000,
        ebit_12m=0,
        patrim_liq=40_000_000_000,
        score_atual=7.0,
    )
    assert "score_ajustado" in resultado


# ─── patrim_liq real vs "fluxo_caixa" (bug de wiring corrigido) ───────────
# Achado real: main.py passava dados.get("fluxo_caixa", 0) como patrim_liq
# — mas "fluxo_caixa" é o lucro líquido TTM mal rotulado (ver
# dados/fundamentus_provider.py: `fcl = lucro_liq_12m`), não patrimônio
# líquido. Números reais da BEEF3, confirmados contra o Status Invest:
# div_liquida = R$13.690.300.000, patrim_liq real = R$1.260.430.000
# (-> 10,86x), "fluxo_caixa"/lucro líquido TTM = R$750.551.000 (-> 18,24x,
# perto do 19,2x que o app mostrava com dado de fonte ligeiramente
# diferente no momento do bug original).

def test_patrim_liq_real_da_razao_diferente_de_usar_fluxo_caixa_por_engano():
    """Usar o patrimônio líquido real (correto) produz uma razão Dívida/
    Patrimônio bem menor do que usar o lucro líquido TTM por engano (bug
    antigo) — confirma que a distinção importa na prática, não só na
    assinatura da função."""
    div_liquida = 13_690_300_000.0
    patrim_liq_real = 1_260_430_000.0
    valor_errado_fluxo_caixa = 750_551_000.0  # "fluxo_caixa" == lucro líquido TTM, não patrimônio

    resultado_correto = analisar_endividamento(
        div_liquida=div_liquida, ebit_12m=3_910_210_000.0, patrim_liq=patrim_liq_real, score_atual=7.0,
    )
    resultado_com_bug_antigo = analisar_endividamento(
        div_liquida=div_liquida, ebit_12m=3_910_210_000.0, patrim_liq=valor_errado_fluxo_caixa, score_atual=7.0,
    )

    assert resultado_correto["div_liquida_patrim"] == pytest.approx(10.86, abs=0.01)
    assert resultado_com_bug_antigo["div_liquida_patrim"] > resultado_correto["div_liquida_patrim"]
    # nos dois casos a razão já está bem acima de 2x, então a penalização
    # de alavancagem dispara igual — o bug distorcia o NÚMERO exibido, não
    # necessariamente o veredito de "alavancagem alta" em si, pra esse caso
    assert "alavancagem_alta" in [a["tipo"] for a in resultado_correto["alertas"]]
    assert "alavancagem_alta" in [a["tipo"] for a in resultado_com_bug_antigo["alertas"]]