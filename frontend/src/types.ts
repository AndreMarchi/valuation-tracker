export interface EvEbitda {
  ev_ebitda_atual: number
  ev_ebitda_setor: number | null
  preco_justo: number | null
  margem_seguranca: number
  classificacao: string
  erro?: string
}

export interface Capm {
  selic: number
  beta: number
  premio_risco: number
  taxa_desconto: number
  taxa_desconto_pct: number
}

export interface MetodoValuation {
  preco_justo?: number
  valor_intrinseco?: number
  margem_seguranca?: number | null
  classificacao: string
  dividend_yield?: number
  erro?: string
}

export interface Multiplos {
  preco_atual: number
  pl: MetodoValuation & { valor: number; media_historica: number; desconto: number | null; atual?: number }
  pvp: MetodoValuation & { valor: number; media_historica: number; desconto: number | null; atual?: number }
}

export interface Score {
  score: number
  classificacao: string
  metodos_aplicados: number
  alertas_criticos?: string[]      
  parecer_analista?: string        
  detalhes?: Record<string, number>
}

export interface Alerta {
  tipo: string
  nivel: string
  titulo: string
  descricao: string
}

export interface Risco {
  score_fundamentalista: number
  penalizacao: number
  score_ajustado: number
  classificacao_ajustada: string
  is_estatal: boolean
  is_regulado: boolean
  alertas: Alerta[]
}

export interface PegRatio {
  peg: number | null
  pl: number | null
  crescimento_pct: number | null
  classificacao: string
  observacao?: string
}

export interface EvReceita {
  psr_atual: number | null
  psr_referencia: number | null
  margem_seguranca: number | null
  classificacao: string
  observacao?: string
}

export interface RuleOf40 {
  score: number | null
  crescimento_pct: number | null
  margem_ebit_pct: number | null
  classificacao: string
  observacao?: string
}

export interface DcfDuasFases {
  valor_intrinseco: number | null
  margem_seguranca: number | null
  classificacao: string
  crescimento_fase1_pct: number | null
  crescimento_fase2_pct: number | null
  observacao?: string
}

export interface CrescimentoInfo {
  fase: string
  crescimento_5a: number
  peg: PegRatio
  ev_receita: EvReceita
  rule_of_40: RuleOf40
  dcf_duas_fases: DcfDuasFases
}

export interface Endividamento {
  div_liquida_ebit: number | null
  div_patrimonio: number | null
  classificacao: string
  alertas: string[]
  score_penalizacao: number
  erro?: string
}

export interface ConsensoInfo {
  pilares_status: {
    patrimonial_multiplos: string | null
    operacional_ebitda: string | null
    fluxo_de_caixa: string | null
  }
  grau_concordancia: string
  parecer_analista: string
}

export interface AlertaHistorico {
  tipo: string
  nivel: string
  titulo: string
  descricao: string
}

// ── FCFE (Fluxo de Caixa Livre do Acionista, via dados CVM) ─────────────────

export interface FcfeAnoBase {
  lucro_liquido: number
  reinvestimento_liquido: number
  delta_divida_liquida: number
  fcfe: number
  alerta: string | null
}

export interface FcfeProjecao {
  fcfe_projetados: number[]
  valor_presente_fcfe_explicito: number
  valor_terminal: number | null
  valor_presente_valor_terminal: number | null
  valor_justo_equity: number | null
  valor_justo_por_acao: number | null
  alerta: string | null
}

export interface FcfePremissas {
  ke: number
  taxa_crescimento_explicito: number
  g_perpetuo: number
  anos_explicitos: number
}

export interface Fcfe {
  disponivel: boolean
  erro?: string
  cd_cvm?: number
  fcfe_ano_base?: FcfeAnoBase
  projecao?: FcfeProjecao | null
  premissas?: FcfePremissas
  inputs_parciais?: Record<string, number | null>
}

// ── Saúde Financeira (Fase 2.5 — dados CVM) ─────────────────────────────────

export interface TrimestralItem {
  periodo: string
  valor: number  // em milhões R$
}

export interface SaudeFinanceira {
  disponivel: boolean
  erro?: string
  score?: number
  classificacao?: string
  tendencia_receita?: 'crescendo' | 'estável' | 'caindo'
  qualidade_lucro?: number | null
  margens_pct?: number[]
  receita_trimestral?: TrimestralItem[]
  lucro_trimestral?: TrimestralItem[]
  fco_trimestral?: TrimestralItem[]
  alertas?: string[]
  destaques?: string[]
  cd_cvm?: number
}

// ── Scanner B3 (varredura de mercado) ───────────────────────────────────────

export interface ScannerAtivo {
  ticker: string
  nome: string
  setor: string
  subsetor: string
  preco_atual: number
  preco_justo_medio: number | null
  margem_seguranca: number | null
  score_atratividade: number
  classificacao: string
  pl: number
  pvp: number
  dividend_yield: number
  roe: number
  divida_ebitda: number
  liquidez_2m: number
  liquidez_ok: boolean | null
  saude_financeira_disponivel: boolean
  saude_financeira_score: number | null
  alerta_valor_trap: boolean
  fonte: string
}

export interface ScannerSetorGrupo {
  setor: string
  perfil: string
  ativos: ScannerAtivo[]
}

export interface ScannerErro {
  ticker: string
  motivo: string
}

export interface ScannerSnapshot {
  data_atualizacao: string
  total_ativos_analisados: number
  total_erros: number
  setores: ScannerSetorGrupo[]
  erros: ScannerErro[]
}

// ─── Cenários & Análise de Sensibilidade (backend/cenarios_sensibilidade.py) ─

export interface CenariosValores {
  pessimista: number
  base: number
  otimista: number
}

export interface FaixaValor {
  minimo: number
  maximo: number
}

export interface PremissasBaseCenario {
  wacc: number
  g_perpetuo: number
  margem_ebitda: number
  crescimento_receita: number
}

export interface DeltasCenarioAplicados {
  wacc_pp: number
  g_perpetuo_pp: number
  margem_ebitda_pp: number
  crescimento_receita_pp: number
}

export type VariavelSensibilidade = 'wacc' | 'g_perpetuo' | 'margem_ebitda' | 'crescimento_receita'

export interface MatrizSensibilidade {
  variavel_x: VariavelSensibilidade
  variavel_y: VariavelSensibilidade
  eixo_x: number[]
  eixo_y: number[]
  matriz: (number | null)[][]
}

export interface MatrizesSensibilidadePadrao {
  wacc_x_g_perpetuo: MatrizSensibilidade
  wacc_x_margem_ebitda: MatrizSensibilidade
  margem_ebitda_x_crescimento_receita: MatrizSensibilidade
}

export interface CenariosSensibilidadeResult {
  ticker: string
  nome: string
  preco_atual: number
  cenarios: CenariosValores
  faixa: FaixaValor
  margem_seguranca_base: number | null
  premissas_base: PremissasBaseCenario
  deltas_aplicados: DeltasCenarioAplicados
  matrizes_sensibilidade: MatrizesSensibilidadePadrao
}

// ─── Valor de Liquidação (backend/valor_liquidacao.py) ──────────────────────

export interface HaircutsAtivos {
  caixa_equivalentes: number
  aplicacoes_financeiras: number
  contas_a_receber: number
  estoques: number
  imobilizado: number
  intangivel: number
}

export interface ValorLiquidacaoResult {
  ticker: string
  nome: string
  disponivel: boolean
  erro?: string
  ativos_ajustados?: HaircutsAtivos
  total_ativos_ajustados?: number
  passivo_total?: number
  contingencias?: number
  contingencias_informadas?: boolean
  valor_liquidacao_total?: number
  valor_liquidacao_por_acao?: number | null
  patrimonio_liquido_negativo_em_liquidacao?: boolean
  haircuts_aplicados?: HaircutsAtivos
  ativo_total_bpa?: number
  cobertura_ativo_total_pct?: number | null
}

// ─── SOTP — Soma das Partes (backend/sotp.py) ───────────────────────────────

export interface SegmentoSotpResultado {
  nome: string
  metodo: 'ev_ebitda' | 'ev_receita' | 'dcf'
  ev: number | null
  erro: string | null
}

export interface SotpResult {
  ticker: string
  disponivel: boolean
  erro?: string
  segmentos?: SegmentoSotpResultado[]
  segmentos_com_erro?: string[]
  ev_consolidado_bruto?: number
  divida_liquida_consolidada?: number
  valor_equity_bruto?: number
  desconto_holding_pct?: number
  valor_equity_pos_desconto?: number
  preco_justo_por_acao?: number | null
}

export interface ValuationResult {
  ticker: string
  nome: string
  preco_atual: number
  graham: MetodoValuation
  bazin: MetodoValuation
  multiplos: Multiplos
  dcf: MetodoValuation & { cenarios?: { otimista: number; base: number; pessimista: number } }
  score: Score
  risco: Risco
  ev_ebitda: EvEbitda
  capm: Capm
  crescimento: CrescimentoInfo
  endividamento: Endividamento
  consenso: ConsensoInfo
  historico_5a: any
  alertas_historicos: AlertaHistorico[]
  setor_info: {
    setor: string
    metodos_validos: string[]
    metricas_ideais: Record<string, any>
  }
  saude_financeira?: SaudeFinanceira
  fcfe?: Fcfe
  drivers?: {
    positivos: string[];
    negativos: string[];
  }
  concessao?: {
    aplicavel: boolean
    preco_justo: number
    anos_ate_vencimento: number
    ano_vencimento_principal: number
    ano_vencimento_secundario?: number
    probabilidade_renovacao: number
    vp_fluxos_pre_cliff: number
    valor_terminal_esperado_pv: number
    valor_terminal_renovacao: number
    valor_terminal_liquidacao: number
    impacto_cliff_vs_perpetuidade: number
    fluxos_projetados: Array<{ ano: number; fcf: number; fator_desconto: number; vp: number; fase: string }>
    wacc_usado: number
    notas: string[]
    motivo?: string
    confiabilidade_baixa?: boolean
  }
}
