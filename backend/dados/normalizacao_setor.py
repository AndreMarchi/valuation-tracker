"""
normalizacao_setor.py

Camada única de normalização de setor — resolve o mismatch sistêmico entre
a string de "setor" retornada pelos provedores de dados (Fundamentus/
YahooQuery/yfinance, via dados.provider.buscar_dados()) e as chaves
hardcoded usadas em vários módulos de valuation (valuation/capm.py::
BETA_POR_SETOR, valuation/crescimento.py::PSR_MEDIO_SETOR, main.py/
scanner/trabalhador.py::SETORES_CICLICOS, valuation/nopat.py::
FATOR_CONVERSAO_NOPAT).

Achado (investigação real, não amostra sintética): cada um desses 4 pontos
comparava a string de setor por igualdade exata (`setor in DICIONARIO`)
contra sua própria lista de chaves, sem nenhuma normalização compartilhada
— então o mesmo ticker podia bater em alguns dicionários e não em outros,
dependendo de qual tinha (por acaso) a string exata retornada pelo
provedor. Confirmado rodando buscar_dados() de verdade contra 11 tickers
de setores variados:

  - "Alimentos Processados" (BEEF3, JBSS3, BRFS3 — frigoríficos) não batia
    com a chave "Alimentos" em NENHUM dos 3 dicionários que a usam
    (SETORES_CICLICOS, BETA_POR_SETOR, PSR_MEDIO_SETOR) — só
    FATOR_CONVERSAO_NOPAT já tratava as duas strings separadamente.
    Consequência real: BEEF3 nunca recebia o cap de crescimento de 8% de
    setor cíclico, usando o teto geral de 15% no DCF — 41% acima do EBIT
    médio dos últimos 3 anos completos, ver CONTEXT.md.
  - "Comércio" (MGLU3 — varejo) não batia com "Varejo" em nenhum dos 4.
  - Bônus: SETORES_CICLICOS tinha o literal "Siderurgia e Siderurgia e
    Metalurgia" (erro de digitação/duplicação) — nunca batia com a string
    real "Siderurgia e Metalurgia" (confirmado com CSNA3), mesmo essa
    string batendo corretamente em BETA_POR_SETOR e FATOR_CONVERSAO_NOPAT.
    Corrigido diretamente nas duas cópias do set (main.py e
    scanner/trabalhador.py) — não é um problema de normalização de
    string vinda do provedor, é só um typo local.

Setores sem canônico conhecido (ex: "Máquinas e Equipamentos", "Diversos" —
WEGE3, RENT3) passam direto, sem mapeamento — não há evidência empírica de
qual seria o canônico certo pra eles ainda. Caem nos defaults de cada
dicionário (BETA_PADRAO, PSR_MEDIO_PADRAO, fator 0.65, sem cap cíclico),
exatamente como hoje — adicionar aqui só quando houver confirmação real.

Entrada de natureza DIFERENTE das anteriores (achado da auditoria setorial,
scripts/auditoria_setorial.py): "Gás" (CEGR3/CEG, CGAS3/Comgás, PASS3/
Compass) caía em fallback em quase todos os dicionários, apesar de
"Petróleo, Gás e Biocombustíveis" já ter entradas calibradas nos mesmos
dicionários. As entradas anteriores deste mapa (Alimentos Processados/
Comércio) são VARIANTES DE STRING do mesmo conceito — aqui não: os 3
tickers de "Gás" são DISTRIBUIDORAS REGULADAS de gás canalizado (CEG/
Comgás são concessionárias de distribuição local, Compass é a holding
controladora dessas concessões, grupo Cosan) — perfil de risco de
concessão regulada com capex intensivo, muito mais parecido com "Energia
Elétrica" (outra concessão regulada) do que com "Petróleo, Gás e
Biocombustíveis" (exploração e produção de commodity, alta ciclicidade,
ex: PETR4, PRIO3, RECV3, BRAV3). Mapear pra "Energia Elétrica" é uma
aproximação de PERFIL DE RISCO, não uma correção de nome — os dicionários
que "Energia Elétrica" alimenta (BETA_POR_SETOR, EV_EBITDA_MEDIO_SETOR,
SETORES_REGULADOS, nopat.py, setor.py::CONFIGURACAO_SETORES — que já
desabilita DCF clássico por alto capex regulatório) fazem sentido
econômico direto pra gás canalizado também. PSR_MEDIO_SETOR não tem
entrada nem pra "Energia Elétrica" (cai no padrão de qualquer forma,
inalterado). Ver CONTEXT.md.
"""

# Mapa raw (como vem do provedor) -> canônico (usado pelos dicionários de
# valuation). Chaves em minúsculo, comparação normalizada — ver
# normalizar_setor(). Só entram aqui mismatches CONFIRMADOS empiricamente
# (rodando buscar_dados de verdade), não suposições.
_MAPA_SETOR_CANONICO = {
    "alimentos processados": "Alimentos",  # BEEF3, JBSS3, BRFS3 (frigoríficos)
    "comércio": "Varejo",                   # MGLU3 — nome oficial B3 antigo de "Varejo"
    "comercio": "Varejo",                   # variante sem acento, por segurança
    "gás": "Energia Elétrica",              # CEGR3/CGAS3/PASS3 — distribuição regulada de gás canalizado, perfil de concessão/capex mais próximo de energia elétrica do que de E&P de petróleo e gás
    "gas": "Energia Elétrica",              # variante sem acento, por segurança
}


def normalizar_setor(setor_bruto: str) -> str:
    """
    Mapeia a string de setor crua do provedor pro nome canônico usado nos
    dicionários de valuation (BETA_POR_SETOR, PSR_MEDIO_SETOR,
    SETORES_CICLICOS, FATOR_CONVERSAO_NOPAT). Setores sem mapeamento
    conhecido retornam inalterados (mesmo comportamento de antes — caem
    nos defaults de cada dicionário).
    """
    if not setor_bruto:
        return setor_bruto
    chave = setor_bruto.strip().lower()
    return _MAPA_SETOR_CANONICO.get(chave, setor_bruto)
