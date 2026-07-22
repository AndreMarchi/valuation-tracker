"""
test_dcf_duas_fases_wiring.py
Teste de paridade (mesmo padrão AST de test_dcf_wiring.py/test_capm_wiring.py/
test_concessao_wiring.py) pro bug: calcular_dcf_duas_fases() desconta LPA
(fluxo de EQUITY) — precisa do Ke (CAPM puro), nunca da WACC. O parâmetro
foi renomeado de `taxa_desconto` pra `ke` justamente pra esse tipo de erro
ficar óbvio na assinatura da função — mas nada impede alguém de escrever
`ke=taxa_desconto` (nome do argumento certo, variável errada) no futuro.
Este teste varre os call sites reais e falha se algum passar uma variável
com nome de WACC (`taxa_desconto`, `wacc`) pro parâmetro `ke`.

Ver CONTEXT.md: bug real, quantificado pra BEEF3 — descontar à WACC em vez
do Ke inflava o valor_intrínseco em +59,3%.
"""

import ast
from pathlib import Path

BACKEND_DIR = Path(__file__).parent.parent

ARQUIVOS_COM_CALL_SITES = [
    BACKEND_DIR / "main.py",
]

# Nomes de variável que, se usados como valor do argumento `ke`, indicam
# que alguém reintroduziu o bug (passou a WACC em vez do Ke/CAPM puro).
NOMES_SUSPEITOS_DE_WACC = {"taxa_desconto", "wacc", "wacc_atual"}


def _encontrar_chamadas(caminho: Path) -> list:
    arvore = ast.parse(caminho.read_text(encoding="utf-8"), filename=str(caminho))
    return [
        no for no in ast.walk(arvore)
        if isinstance(no, ast.Call) and isinstance(no.func, ast.Name) and no.func.id == "calcular_dcf_duas_fases"
    ]


class TestCalcularDcfDuasFasesUsaKeNaoWacc:

    def test_arquivos_de_producao_tem_pelo_menos_uma_chamada(self):
        total = sum(len(_encontrar_chamadas(c)) for c in ARQUIVOS_COM_CALL_SITES if c.exists())
        assert total > 0, "Nenhuma chamada a calcular_dcf_duas_fases() encontrada — teste não protege nada."

    def test_todas_as_chamadas_passam_ke_como_keyword(self):
        falhas = []
        for caminho in ARQUIVOS_COM_CALL_SITES:
            for chamada in _encontrar_chamadas(caminho):
                nomes_kw = {kw.arg for kw in chamada.keywords}
                if "ke" not in nomes_kw:
                    falhas.append(f"{caminho.relative_to(BACKEND_DIR)}:{chamada.lineno} (sem keyword 'ke')")
        assert not falhas, "; ".join(falhas)

    def test_nenhuma_chamada_passa_variavel_de_wacc_pro_ke(self):
        falhas = []
        for caminho in ARQUIVOS_COM_CALL_SITES:
            for chamada in _encontrar_chamadas(caminho):
                for kw in chamada.keywords:
                    if kw.arg != "ke":
                        continue
                    if isinstance(kw.value, ast.Name) and kw.value.id in NOMES_SUSPEITOS_DE_WACC:
                        falhas.append(
                            f"{caminho.relative_to(BACKEND_DIR)}:{chamada.lineno} — "
                            f"ke='{kw.value.id}' parece ser a WACC, não o Ke/CAPM puro"
                        )
        assert not falhas, (
            "; ".join(falhas) + " — LPA é fluxo de equity, precisa ser descontado ao Ke "
            "(CAPM puro), nunca à WACC (mistura dívida mais barata, sempre menor que o Ke "
            "numa empresa endividada, o que infla o valor justo)."
        )
