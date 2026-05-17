export interface EvEbitda {
  ev_ebitda_atual: number
  ev_ebitda_medio: number
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
  pl: MetodoValuation & { valor: number; media_historica: number; desconto: number | null }
  pvp: MetodoValuation & { valor: number; media_historica: number; desconto: number | null }
}

export interface Score {
  score: number
  classificacao: string
  metodos_aplicados: number
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
}