

import { useState } from 'react'
import axios from 'axios'
import type { ValuationResult, MetodoValuation, Multiplos, Score } from './types'


const classificacaoIcon: Record<string, string> = {
  'Descontada':    '✅',
  'Neutra':        '⚠️',
  'Cara':          '❌',
  'Não aplicável': '—',
}

const scoreColor = (score: number) => {
  if (score >= 8) return 'text-green-600'
  if (score >= 6) return 'text-blue-600'
  if (score >= 4) return 'text-yellow-600'
  return 'text-red-600'
}

const MetodoCard = ({ nome, classificacao, margem, extra }: {
  nome: string
  classificacao: string
  margem?: number | null
  extra?: string
}) => (
  <div className="flex items-center justify-between p-3 bg-gray-50 rounded-lg">
    <div className="flex items-center gap-2">
      <span className="text-lg">{classificacaoIcon[classificacao] ?? '—'}</span>
      <span className="font-medium text-gray-700">{nome}</span>
    </div>
    <div className="text-right">
      <span className={`text-sm font-semibold ${
        classificacao === 'Descontada' ? 'text-green-600' :
        classificacao === 'Cara' ? 'text-red-600' : 'text-gray-500'
      }`}>
        {classificacao}
      </span>
      {margem != null && (
        <p className="text-xs text-gray-400">
          {margem > 0 ? '+' : ''}{margem.toFixed(1)}% margem
        </p>
      )}
      {extra && <p className="text-xs text-gray-400">{extra}</p>}
    </div>
  </div>
)

export default function App() {
  const [ticker, setTicker]   = useState('')
  const [resultado, setResultado] = useState<ValuationResult | null>(null)
  const [loading, setLoading] = useState(false)
  const [erro, setErro]       = useState('')

  const buscar = async () => {
    if (!ticker.trim()) return
    setLoading(true)
    setErro('')
    setResultado(null)

    try {
      const { data } = await axios.get<ValuationResult>(`/api/valuation/${ticker.toUpperCase()}`)
      setResultado(data)
    } catch (e: any) {
      setErro(e.response?.data?.detail ?? 'Erro ao buscar dados. Tente novamente.')
    } finally {
      setLoading(false)
    }
  }

  const handleKeyDown = (e: React.KeyboardEvent) => {
    if (e.key === 'Enter') buscar()
  }

  return (
    <div className="min-h-screen bg-gray-100 p-6">
      <div className="max-w-xl mx-auto">

        {/* Header */}
        <div className="mb-8 text-center">
          <h1 className="text-3xl font-bold text-blue-900">Valuation Tracker</h1>
          <p className="text-gray-500 mt-1">Análise fundamentalista de ações da B3</p>
        </div>

        {/* Busca */}
        <div className="flex gap-2 mb-6">
          <input
            className="flex-1 px-4 py-2 rounded-lg border border-gray-300 focus:outline-none focus:ring-2 focus:ring-blue-400 uppercase"
            placeholder="Digite o ticker... ex: PETR4"
            value={ticker}
            onChange={e => setTicker(e.target.value)}
            onKeyDown={handleKeyDown}
          />
          <button
            onClick={buscar}
            disabled={loading}
            className="px-6 py-2 bg-blue-700 text-white rounded-lg font-semibold hover:bg-blue-800 disabled:opacity-50 transition"
          >
            {loading ? 'Buscando...' : 'Analisar'}
          </button>
        </div>

        {/* Erro */}
        {erro && (
          <div className="bg-red-50 border border-red-200 text-red-700 px-4 py-3 rounded-lg mb-4">
            {erro}
          </div>
        )}

        {/* Resultado */}
        {resultado && (
          <div className="bg-white rounded-2xl shadow p-6 space-y-6">

            {/* Cabeçalho da ação */}
            <div className="flex justify-between items-start">
              <div>
                <h2 className="text-2xl font-bold text-gray-800">{resultado.ticker}</h2>
                <p className="text-gray-500 text-sm">{resultado.nome}</p>
              </div>
              <div className="text-right">
                <p className="text-2xl font-bold text-gray-800">
                  R$ {resultado.preco_atual.toFixed(2)}
                </p>
                <p className="text-xs text-gray-400">preço atual</p>
              </div>
            </div>

            {/* Score */}
            <div className="bg-blue-50 rounded-xl p-4 text-center">
              <p className="text-sm text-gray-500 mb-1">Score de Atratividade</p>
              <p className={`text-5xl font-bold ${scoreColor(resultado.score.score)}`}>
                {resultado.score.score}
                <span className="text-lg text-gray-400">/10</span>
              </p>
              <p className={`text-lg font-semibold mt-1 ${scoreColor(resultado.score.score)}`}>
                {resultado.score.classificacao}
              </p>
              <p className="text-xs text-gray-400 mt-1">
                Baseado em {resultado.score.metodos_aplicados} método(s)
              </p>
            </div>

            {/* Métodos */}
            <div>
              <h3 className="text-sm font-semibold text-gray-400 uppercase mb-3">
                Métodos de Valuation
              </h3>
              <div className="space-y-2">
                <MetodoCard
                  nome="Graham"
                  classificacao={resultado.graham.classificacao}
                  margem={resultado.graham.margem_seguranca}
                  extra={resultado.graham.preco_justo
                    ? `Preço justo: R$ ${resultado.graham.preco_justo}`
                    : undefined}
                />
                <MetodoCard
                  nome="Bazin"
                  classificacao={resultado.bazin.classificacao}
                  margem={resultado.bazin.margem_seguranca}
                  extra={resultado.bazin.dividend_yield
                    ? `DY: ${resultado.bazin.dividend_yield}%`
                    : undefined}
                />
                <MetodoCard
                  nome="P/L"
                  classificacao={resultado.multiplos.pl.classificacao}
                  margem={resultado.multiplos.pl.desconto}
                  extra={resultado.multiplos.pl.valor
                    ? `P/L atual: ${resultado.multiplos.pl.valor.toFixed(1)}x`
                    : undefined}
                />
                <MetodoCard
                  nome="P/VP"
                  classificacao={resultado.multiplos.pvp.classificacao}
                  margem={resultado.multiplos.pvp.desconto}
                  extra={resultado.multiplos.pvp.valor
                    ? `P/VP atual: ${resultado.multiplos.pvp.valor.toFixed(2)}x`
                    : undefined}
                />
                <MetodoCard
                  nome="DCF"
                  classificacao={resultado.dcf.classificacao}
                  margem={resultado.dcf.margem_seguranca}
                  extra={resultado.dcf.valor_intrinseco
                    ? `Valor intrínseco: R$ ${resultado.dcf.valor_intrinseco}`
                    : undefined}
                />
              </div>
            </div>

            {/* Cenários DCF */}
            {resultado.dcf.cenarios && (
              <div>
                <h3 className="text-sm font-semibold text-gray-400 uppercase mb-3">
                  Cenários DCF
                </h3>
                <div className="grid grid-cols-3 gap-2 text-center">
                  <div className="bg-red-50 rounded-lg p-3">
                    <p className="text-xs text-gray-400">Pessimista</p>
                    <p className="font-bold text-red-600">
                      R$ {resultado.dcf.cenarios.pessimista.toFixed(2)}
                    </p>
                  </div>
                  <div className="bg-blue-50 rounded-lg p-3">
                    <p className="text-xs text-gray-400">Base</p>
                    <p className="font-bold text-blue-600">
                      R$ {resultado.dcf.cenarios.base.toFixed(2)}
                    </p>
                  </div>
                  <div className="bg-green-50 rounded-lg p-3">
                    <p className="text-xs text-gray-400">Otimista</p>
                    <p className="font-bold text-green-600">
                      R$ {resultado.dcf.cenarios.otimista.toFixed(2)}
                    </p>
                  </div>
                </div>
              </div>
            )}
            
            {/* EV/EBITDA */}
            {resultado.ev_ebitda && resultado.ev_ebitda.classificacao !== "Não aplicável" && (
              <div>
                <h3 className="text-sm font-semibold text-gray-400 uppercase mb-3">
                  EV/EBITDA — Método Kobori
                </h3>
                <div className="grid grid-cols-3 gap-2 text-center mb-2">
                  <div className="bg-gray-50 rounded-lg p-3">
                    <p className="text-xs text-gray-400">EV/EBITDA Atual</p>
                    <p className="font-bold text-gray-700">{resultado.ev_ebitda.ev_ebitda_atual}x</p>
                  </div>
                  <div className="bg-blue-50 rounded-lg p-3">
                    <p className="text-xs text-gray-400">Média Setorial</p>
                    <p className="font-bold text-blue-600">{resultado.ev_ebitda.ev_ebitda_medio}x</p>
                  </div>
                  <div className="bg-gray-50 rounded-lg p-3">
                    <p className="text-xs text-gray-400">Preço Justo</p>
                    <p className="font-bold text-gray-700">
                      {resultado.ev_ebitda.preco_justo
                        ? `R$ ${resultado.ev_ebitda.preco_justo.toFixed(2)}`
                        : '—'}
                    </p>
                  </div>
                </div>
                <div className="flex items-center justify-between p-3 bg-gray-50 rounded-lg">
                  <span className="font-medium text-gray-700">Classificação EV/EBITDA</span>
                  <span className={`text-sm font-semibold ${
                    resultado.ev_ebitda.classificacao === 'Descontada' ? 'text-green-600' :
                    resultado.ev_ebitda.classificacao === 'Cara' ? 'text-red-600' : 'text-gray-500'
                  }`}>
                    {classificacaoIcon[resultado.ev_ebitda.classificacao] ?? '⚠️'} {resultado.ev_ebitda.classificacao}
                  </span>
                </div>
              </div>
            )}

            {/* CAPM */}
            {resultado.capm && (
              <div>
                <h3 className="text-sm font-semibold text-gray-400 uppercase mb-3">
                  Taxa de Desconto — CAPM
                </h3>
                <div className="grid grid-cols-3 gap-2 text-center">
                  <div className="bg-green-50 rounded-lg p-1">  </div>
                  <div className="bg-blue-50 rounded-lg">
                    <p>Beta - 1 menos volátil</p>
                    <p>Beta 1 acompanha a B3</p>
                    <p>Beta + 1 mais volátil</p>
                  </div>
                  <div className="bg-red-50 rounded-lg p-1"></div>
                  
                </div>
                <div className="grid grid-cols-3 gap-2 text-center">
                  <div className="bg-gray-50 rounded-lg p-3">
                    <p className="text-xs text-gray-400">Selic</p>
                    <p className="font-bold text-gray-700">{(resultado.capm.selic * 100).toFixed(2)}%</p>
                  </div>
                  <div className="bg-gray-50 rounded-lg p-3">
                    <p className="text-xs text-gray-400">Beta</p>
                    <p className="font-bold text-gray-700">{resultado.capm.beta}</p>
                  </div>
                  <div className="bg-blue-50 rounded-lg p-3">
                    <p className="text-xs text-gray-400">Taxa Final</p>
                    <p className="font-bold text-blue-600">{resultado.capm.taxa_desconto_pct}%</p>
                  </div>
                </div>
              </div>
            )} 
            {/* Análise de Risco */}
            {resultado.risco && resultado.risco.alertas.length > 0 && (
              <div>
                <h3 className="text-sm font-semibold text-gray-400 uppercase mb-3">
                  Análise de Risco
                </h3>

                {/* Scores comparativos */}
                <div className="grid grid-cols-2 gap-2 mb-3">
                  <div className="bg-gray-50 rounded-lg p-3 text-center">
                    <p className="text-xs text-gray-400">Score Fundamentalista</p>
                    <p className={`text-2xl font-bold ${scoreColor(resultado.risco.score_fundamentalista)}`}>
                      {resultado.risco.score_fundamentalista}
                      <span className="text-sm text-gray-400">/10</span>
                    </p>
                  </div>
                  <div className="bg-orange-50 rounded-lg p-3 text-center">
                    <p className="text-xs text-gray-400">Score Ajustado ao Risco</p>
                    <p className={`text-2xl font-bold ${scoreColor(resultado.risco.score_ajustado)}`}>
                      {resultado.risco.score_ajustado}
                      <span className="text-sm text-gray-400">/10</span>
                    </p>
                  </div>
                </div>

                {/* Alertas */}
                <div className="space-y-2">
                  {resultado.risco.alertas.map((alerta: any, i: number) => (
                    <div
                      key={i}
                      className={`p-3 rounded-lg border ${
                        alerta.nivel === 'alto'
                          ? 'bg-red-50 border-red-200'
                          : 'bg-yellow-50 border-yellow-200'
                      }`}
                    >
                      <p className={`text-sm font-semibold ${
                        alerta.nivel === 'alto' ? 'text-red-700' : 'text-yellow-700'
                      }`}>
                        {alerta.nivel === 'alto' ? '🔴' : '🟡'} {alerta.titulo}
                      </p>
                      <p className={`text-xs mt-1 ${
                        alerta.nivel === 'alto' ? 'text-red-600' : 'text-yellow-600'
                      }`}>
                        {alerta.descricao}
                      </p>
                    </div>
                  ))}
                </div>
              </div>
            )}
            
          </div>
        )}
      </div>
    </div>
  )
}