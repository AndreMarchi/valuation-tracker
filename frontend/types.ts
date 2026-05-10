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
}