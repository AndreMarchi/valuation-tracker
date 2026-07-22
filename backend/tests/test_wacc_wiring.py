"""
test_wacc_wiring.py
Teste de paridade (mesmo padrão AST de test_capm_wiring.py/test_dcf_wiring.py/
test_endividamento_wiring.py) pro bug: valuation/wacc.py::calcular_wacc() lê
`dados.get("selic", 0.145)` — um fallback hardcoded de 14,5%. Nenhum dos dois
call sites de produção pode chamar calcular_wacc() sem primeiro injetar o
Selic REAL (buscado via buscar_selic_atual(), já usado corretamente pro
CAPM/Ke) no dict `dados` passado.

Achado real (investigação de auditoria setorial): `main.py` nunca injetava
"selic" antes de chamar calcular_wacc() — o WACC do DCF principal em
produção sempre usava 14,5% fixo, nunca o Selic real, mesmo esse já tendo
sido buscado e usado corretamente pro CAPM umas linhas antes.
`scanner/trabalhador.py` já fazia certo (`dados_wacc["selic"] = selic_val`).
Corrigido pra main.py aplicar o mesmo padrão. Ver CONTEXT.md.

Diferente de test_wacc.py (testa calcular_wacc() isolada, sempre passando
"selic" manualmente no dict de teste — nunca veria esse tipo de bug de
wiring), este teste analisa o CÓDIGO-FONTE via `ast` dos dois call sites de
produção.
"""

import ast
from pathlib import Path

BACKEND_DIR = Path(__file__).parent.parent

ARQUIVOS_COM_CALL_SITES = [
    BACKEND_DIR / "main.py",
    BACKEND_DIR / "scanner" / "trabalhador.py",
]


def _encontrar_chamadas_calcular_wacc(caminho: Path) -> list:
    arvore = ast.parse(caminho.read_text(encoding="utf-8"), filename=str(caminho))
    return [
        no for no in ast.walk(arvore)
        if isinstance(no, ast.Call) and isinstance(no.func, ast.Name) and no.func.id == "calcular_wacc"
    ]


def _primeiro_argumento_dados(chamada: ast.Call) -> ast.AST:
    """Retorna o nó do 1º argumento posicional (`dados`) de uma chamada a
    calcular_wacc(setor_ou_dados, ...) — sempre posicional nos dois call
    sites atuais."""
    assert chamada.args, f"calcular_wacc() chamada sem argumentos posicionais (linha {chamada.lineno})"
    return chamada.args[0]


class TestCalcularWaccSempreRecebeSelicReal:

    def test_arquivos_de_producao_tem_pelo_menos_uma_chamada(self):
        total = sum(len(_encontrar_chamadas_calcular_wacc(c)) for c in ARQUIVOS_COM_CALL_SITES if c.exists())
        assert total > 0, "Nenhuma chamada a calcular_wacc() encontrada nos arquivos de produção — teste não protege nada."

    def test_nenhuma_chamada_passa_o_dict_dados_bruto_sem_selic_injetado(self):
        """Regressão: o argumento `dados` de calcular_wacc() não pode ser a
        variável `dados` bruta (vinda direto de buscar_dados(), sem
        "selic") — precisa ser uma variável derivada (ex: dados_wacc) que
        contenha o Selic real injetado."""
        falhas = []
        for caminho in ARQUIVOS_COM_CALL_SITES:
            for chamada in _encontrar_chamadas_calcular_wacc(caminho):
                arg_dados = _primeiro_argumento_dados(chamada)
                if isinstance(arg_dados, ast.Name) and arg_dados.id == "dados":
                    falhas.append(f"{caminho.relative_to(BACKEND_DIR)}:{chamada.lineno}")

        assert not falhas, (
            "calcular_wacc() chamada com o dict 'dados' bruto (sem \"selic\" injetado) em: "
            + ", ".join(falhas) + " — calcular_wacc() cai no fallback hardcoded de 14,5% "
            "(valuation/wacc.py: dados.get('selic', 0.145)) em vez de usar o Selic real."
        )

    def test_selic_e_injetado_a_partir_da_mesma_variavel_usada_no_capm(self):
        """Não basta injetar UMA string 'selic' — tem que vir da MESMA
        variável (ex: selic_val) já usada pra calcular_capm(), senão os
        dois (Ke e Kd) podem divergir por causa de uma 2ª busca com cache
        expirado no meio da mesma requisição."""
        falhas = []
        for caminho in ARQUIVOS_COM_CALL_SITES:
            arvore = ast.parse(caminho.read_text(encoding="utf-8"), filename=str(caminho))

            # Nome da variável passada como selic_atual= (ou posicional) em calcular_capm()
            nome_selic_capm = None
            for no in ast.walk(arvore):
                if isinstance(no, ast.Call) and isinstance(no.func, ast.Name) and no.func.id == "calcular_capm":
                    for kw in no.keywords:
                        if kw.arg == "selic_atual" and isinstance(kw.value, ast.Name):
                            nome_selic_capm = kw.value.id
                    break
            if nome_selic_capm is None:
                continue  # arquivo sem chamada a calcular_capm() — nada a comparar

            # Procura, em qualquer atribuição tipo `algo["selic"] = <nome>`,
            # se <nome> bate com a mesma variável usada no CAPM.
            bateu = False
            for no in ast.walk(arvore):
                if (
                    isinstance(no, ast.Assign)
                    and len(no.targets) == 1
                    and isinstance(no.targets[0], ast.Subscript)
                    and isinstance(no.value, ast.Name)
                ):
                    alvo = no.targets[0]
                    chave = alvo.slice if isinstance(alvo.slice, ast.Constant) else getattr(alvo.slice, "value", None)
                    if isinstance(chave, ast.Constant):
                        chave = chave.value
                    if chave == "selic" and no.value.id == nome_selic_capm:
                        bateu = True
                        break

            if not bateu:
                falhas.append(f"{caminho.relative_to(BACKEND_DIR)} (variável do CAPM: '{nome_selic_capm}')")

        assert not falhas, (
            "Selic injetado pro WACC não vem da mesma variável usada no CAPM em: " + ", ".join(falhas) +
            " — risco de Ke e Kd usarem Selics diferentes na mesma requisição."
        )
