"""
test_endividamento_wiring.py
Teste de paridade (mesmo padrão AST de test_dcf_wiring.py/test_capm_wiring.py/
test_concessao_wiring.py) pro bug: analisar_endividamento() recebia
`patrim_liq=dados.get("fluxo_caixa", 0)` — "fluxo_caixa" é na verdade o
lucro líquido TTM mal rotulado (ver dados/fundamentus_provider.py: `fcl =
lucro_liq_12m`), não patrimônio líquido. O patrimônio líquido real (agora
exposto como "patrim_liq" nos 4 providers) nunca era usado, mesmo já
estando calculado internamente em cada um deles.

`scanner/trabalhador.py` tinha uma variação do mesmo bug: tentava
`dados.get("patrliq", ...)` primeiro — uma chave que nenhum provider jamais
retornou — então sempre caía no mesmo fallback errado (`fluxo_caixa`).

Ver CONTEXT.md: achado real, confirmado contra o Status Invest pra BEEF3 —
Dívida Líquida/Patrimônio saía 19,2x (dividindo pelo lucro líquido TTM) em
vez dos 10,86x reais (dividindo pelo patrimônio líquido de verdade).
"""

import ast
from pathlib import Path

BACKEND_DIR = Path(__file__).parent.parent

ARQUIVOS_COM_CALL_SITES = [
    BACKEND_DIR / "main.py",
    BACKEND_DIR / "scanner" / "trabalhador.py",
]

# Se o valor do argumento patrim_liq for uma chamada .get(...) com esse
# nome de chave, é a reintrodução do bug (nome de chave que nunca é
# patrimônio líquido de verdade).
CHAVES_SUSPEITAS = {"fluxo_caixa", "patrliq"}


def _encontrar_chamadas(caminho: Path) -> list:
    arvore = ast.parse(caminho.read_text(encoding="utf-8"), filename=str(caminho))
    return [
        no for no in ast.walk(arvore)
        if isinstance(no, ast.Call) and isinstance(no.func, ast.Name) and no.func.id == "analisar_endividamento"
    ]


def _chave_do_get(no_valor: ast.AST):
    """Se `no_valor` for (a primeira chamada de) uma cadeia de `.get("chave", ...)`,
    devolve a string dessa chave — senão None. Cobre tanto
    `dados.get("x", 0) or 0` quanto `dados.get("x", dados.get("y", 0))`."""
    alvo = no_valor
    # desce por "or 0" (BoolOp) até achar a chamada .get(...)
    if isinstance(alvo, ast.BoolOp):
        alvo = alvo.values[0]
    if (
        isinstance(alvo, ast.Call)
        and isinstance(alvo.func, ast.Attribute)
        and alvo.func.attr == "get"
        and alvo.args
        and isinstance(alvo.args[0], ast.Constant)
    ):
        return alvo.args[0].value
    return None


class TestAnalisarEndividamentoUsaPatrimLiqDeVerdade:

    def test_arquivos_de_producao_tem_pelo_menos_uma_chamada(self):
        total = sum(len(_encontrar_chamadas(c)) for c in ARQUIVOS_COM_CALL_SITES if c.exists())
        assert total > 0, "Nenhuma chamada a analisar_endividamento() encontrada — teste não protege nada."

    def test_nenhuma_chamada_usa_chave_suspeita_pro_patrim_liq(self):
        falhas = []
        for caminho in ARQUIVOS_COM_CALL_SITES:
            for chamada in _encontrar_chamadas(caminho):
                for kw in chamada.keywords:
                    if kw.arg != "patrim_liq":
                        continue
                    chave = _chave_do_get(kw.value)
                    if chave in CHAVES_SUSPEITAS:
                        falhas.append(
                            f"{caminho.relative_to(BACKEND_DIR)}:{chamada.lineno} — "
                            f"patrim_liq usa a chave '{chave}', que não é patrimônio líquido real"
                        )
        assert not falhas, (
            "; ".join(falhas) + " — use dados.get('patrim_liq', 0), a chave real exposta pelos "
            "4 providers (fundamentus_provider.py, yfinance_provider.py, yquery_provider.py, brapi.py)."
        )
