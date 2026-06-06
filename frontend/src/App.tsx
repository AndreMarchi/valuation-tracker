import { useState } from 'react'
import axios from 'axios'
import type {
  ValuationResult,
  MetodoValuation,
  ConsensoInfo,
  CrescimentoInfo,
  Endividamento,
  Risco,
  AlertaHistorico,
} from './types'

// ─── helpers ───────────────────────────────────────────────────────────────

const classIcon: Record<string, string> = {
  Descontada: '✅',
  Neutra: '⚠️',
  Cara: '❌',
  'Não aplicável': '—',
}

const classColor = (c: string) =>
  c === 'Descontada' ? 'text-green-700' : c === 'Cara' ? 'text-red-600' : 'text-gray-500'

const scoreColor = (s: number) => {
  if (s >= 8) return 'text-green-700'
  if (s >= 6) return 'text-blue-700'
  if (s >= 4) return 'text-yellow-600'
  return 'text-red-600'
}

const fmt = (v: number | null | undefined, prefix = '', suffix = '', decimals = 2) =>
  v != null ? `${prefix}${v.toFixed(decimals)}${suffix}` : '—'

// ─── sub-components ────────────────────────────────────────────────────────

const SectionLabel = ({ children }: { children: React.ReactNode }) => (
  <h3 className="text-xs font-semibold tracking-widest text-gray-400 uppercase mb-3">{children}</h3>
)

const MetricCard = ({
  label,
  value,
  highlight,
}: {
  label: string
  value: React.ReactNode
  highlight?: 'green' | 'blue' | 'red' | 'amber'
}) => {
  const colors = {
    green: 'text-green-700',
    blue: 'text-blue-700',
    red: 'text-red-600',
    amber: 'text-yellow-600',
  }
  return (
    <div className="bg-gray-50 rounded-lg p-3 text-center">
      <p className="text-xs text-gray-400 mb-1">{label}</p>
      <p className={`font-semibold text-base ${highlight ? colors[highlight] : 'text-gray-800'}`}>
        {value}
      </p>
    </div>
  )
}

const MethodRow = ({
  nome,
  classificacao,
  detail,
}: {
  nome: string
  classificacao: string
  detail?: string
}) => (
  <div className="flex items-center justify-between px-3 py-2.5 bg-gray-50 rounded-lg">
    <div className="flex items-center gap-2 text-sm text-gray-700">
      <span>{classIcon[classificacao] ?? '—'}</span>
      <span className="font-medium">{nome}</span>
    </div>
    <div className="text-right">
      <p className={`text-sm font-semibold ${classColor(classificacao)}`}>{classificacao}</p>
      {detail && <p className="text-xs text-gray-400">{detail}</p>}
    </div>
  </div>
)

// ─── section components ────────────────────────────────────────────────────

const SecaoMetodos = ({ r }: { r: ValuationResult }) => (
  <div>
    <SectionLabel>Métodos de valuation</SectionLabel>
    <div className="space-y-1.5">
      <MethodRow
        nome="Graham"
        classificacao={r.graham.classificacao}
        detail={[
          r.graham.margem_seguranca != null && `${r.graham.margem_seguranca > 0 ? '+' : ''}${r.graham.margem_seguranca.toFixed(1)}% margem`,
          r.graham.preco_justo && `Preço justo: R$ ${r.graham.preco_justo}`,
        ]
          .filter(Boolean)
          .join(' · ')}
      />
      <MethodRow
        nome="Bazin"
        classificacao={r.bazin.classificacao}
        detail={r.bazin.dividend_yield ? `DY: ${r.bazin.dividend_yield}%` : undefined}
      />
      <MethodRow
        nome="P/L"
        classificacao={r.multiplos.pl.classificacao}
        detail={r.multiplos.pl.valor ? `P/L atual: ${r.multiplos.pl.valor.toFixed(1)}x` : undefined}
      />
      <MethodRow
        nome="P/VP"
        classificacao={r.multiplos.pvp.classificacao}
        detail={r.multiplos.pvp.valor ? `P/VP atual: ${r.multiplos.pvp.valor.toFixed(2)}x` : undefined}
      />
      <MethodRow
        nome="DCF"
        classificacao={r.dcf.classificacao}
        detail={[
          r.dcf.margem_seguranca != null && `${r.dcf.margem_seguranca.toFixed(1)}% margem`,
          r.dcf.valor_intrinseco && `Valor intrínseco: R$ ${r.dcf.valor_intrinseco}`,
        ]
          .filter(Boolean)
          .join(' · ')}
      />
    </div>
  </div>
)

const SecaoCenariosDCF = ({ cenarios }: { cenarios: { pessimista: number; base: number; otimista: number } | null | undefined }) => {
  if (!cenarios || cenarios.pessimista == null) return null

  return (
    <div>
      <SectionLabel>Cenários DCF</SectionLabel>
      <div className="grid grid-cols-3 gap-2">
        <MetricCard label="Pessimista" value={`R$ ${cenarios.pessimista.toFixed(2)}`} highlight="red" />
        <MetricCard label="Base" value={`R$ ${cenarios.base.toFixed(2)}`} highlight="blue" />
        <MetricCard label="Otimista" value={`R$ ${cenarios.otimista.toFixed(2)}`} highlight="green" />
      </div>
    </div>
  )
}

const SecaoEvEbitda = ({ ev }: { ev: ValuationResult['ev_ebitda'] }) => {
  if (ev.classificacao === 'Não aplicável' || ev.erro) return null
  return (
    <div>
      <SectionLabel>EV/EBITDA — método Kobori</SectionLabel>
      <div className="grid grid-cols-3 gap-2 mb-2">
        <MetricCard label="EV/EBITDA atual" value={`${ev.ev_ebitda_atual}x`} />
        <MetricCard label="Média setorial" value={`${ev.ev_ebitda_medio}x`} highlight="blue" />
        <MetricCard
          label="Preço justo"
          value={ev.preco_justo ? `R$ ${ev.preco_justo.toFixed(2)}` : '—'}
        />
      </div>
      <MethodRow nome="Classificação EV/EBITDA" classificacao={ev.classificacao} />
    </div>
  )
}

const SecaoCrescimento = ({ c }: { c: CrescimentoInfo | null | undefined }) => {
  if (!c) return null

  const getPegHighlight = (peg: number | null | undefined) => {
    if (peg == null) return undefined
    if (peg < 1) return 'green'
    if (peg > 2) return 'red'
    return undefined
  };

  const getRuleOf40Highlight = (score: number | null | undefined) => {
    if (score == null) return undefined
    if (score >= 40) return 'green'
    if (score >= 20) return 'amber'
    return 'red'
  };

  return (
    <div>
      <SectionLabel>Crescimento &amp; métricas de fase</SectionLabel>
      <div className="grid grid-cols-3 gap-2 mb-2">
        <MetricCard label="Fase" value={c.fase ?? '—'} />
        <MetricCard
          label="Crescimento 5a"
          value={c.crescimento_5a != null ? `${c.crescimento_5a > 0 ? '+' : ''}${c.crescimento_5a.toFixed(1)}%` : '—'}
          highlight={c.crescimento_5a != null ? (c.crescimento_5a >= 10 ? 'green' : c.crescimento_5a < 0 ? 'red' : undefined) : undefined}
        />
        <MetricCard
          label="PEG Ratio"
          value={c.peg ? fmt(c.peg.peg, '', 'x', 2) : '—'}
          highlight={c.peg ? getPegHighlight(c.peg.peg) : undefined}
        />
      </div>
      <div className="grid grid-cols-2 gap-2 mb-2">
        <MetricCard
          label="Rule of 40"
          value={c.rule_of_40 && c.rule_of_40.score != null ? c.rule_of_40.score.toFixed(1) : '—'}
          highlight={c.rule_of_40 ? getRuleOf40Highlight(c.rule_of_40.score) : undefined}
        />
        <MetricCard
          label="DCF 2 fases"
          value={
            c.dcf_duas_fases && c.dcf_duas_fases.valor_intrinseco
              ? `R$ ${c.dcf_duas_fases.valor_intrinseco.toFixed(2)}`
              : '—'
          }
          highlight={
            c.dcf_duas_fases
              ? c.dcf_duas_fases.classificacao === 'Descontada'
                ? 'green'
                : c.dcf_duas_fases.classificacao === 'Cara'
                ? 'red'
                : undefined
              : undefined
          }
        />
      </div>
      {c.peg && c.peg.observacao && (
        <p className="text-xs text-gray-400 mt-1">{c.peg.observacao}</p>
      )}
    </div>
  )
}

const SecaoCapm = ({ capm }: { capm: ValuationResult['capm'] }) => (
  <div>
    <SectionLabel>Taxa de desconto — CAPM / WACC</SectionLabel>
    <p className="text-xs text-gray-400 bg-gray-50 rounded-lg px-3 py-2 mb-2">
      Beta &lt; 1 = menos volátil que a B3 · Beta = 1 acompanha a B3 · Beta &gt; 1 = mais volátil
    </p>
    <div className="grid grid-cols-3 gap-2">
      <MetricCard label="Selic" value={`${(capm.selic * 100).toFixed(2)}%`} />
      <MetricCard label="Beta" value={capm.beta} />
      <MetricCard label="Taxa CAPM" value={`${capm.taxa_desconto_pct}%`} highlight="blue" />
    </div>
  </div>
)

const SecaoEndividamento = ({ e }: { e: Endividamento }) => {
  if (!e) return null
  
  const alertColor =
    e.classificacao === 'Crítico'
      ? 'bg-red-50 border-red-200 text-red-700'
      : e.classificacao === 'Alto'
      ? 'bg-yellow-50 border-yellow-200 text-yellow-700'
      : 'bg-gray-50 border-gray-200 text-gray-600'

  return (
    <div>
      <SectionLabel>Endividamento</SectionLabel>
      <div className="grid grid-cols-2 gap-2 mb-2">
        <MetricCard
          label="Dívida / EBIT"
          value={fmt(e.div_ebit, '', 'x')}
          highlight={
            e.div_ebit != null
              ? e.div_ebit > 5
                ? 'red'
                : e.div_ebit > 3
                ? 'amber'
                : 'green'
              : undefined
          }
        />
        <MetricCard
          label="Classificação"
          value={e.classificacao}
          highlight={
            e.classificacao === 'Crítico'
              ? 'red'
              : e.classificacao === 'Alto'
              ? 'amber'
              : 'green'
          }
        />
      </div>
      
      {e.alertas?.map((a: any, i) => {
        if (typeof a === 'object' && a !== null) {
          return (
            <div key={i} className={`px-3 py-2 rounded-lg border text-xs mb-1 ${alertColor}`}>
              <span className="font-semibold">{a.titulo}:</span> {a.descricao}
            </div>
          )
        }
        return (
          <div key={i} className={`px-3 py-2 rounded-lg border text-xs mb-1 ${alertColor}`}>
            {a}
          </div>
        )
      })}
    </div>
  )
}

const SecaoConsenso = ({ c }: { c: ConsensoInfo }) => {
  if (!c || !c.pilares_status) return null

  const pilarLabel: Record<string, string> = {
    patrimonial_multiplos: 'Patrimonial / Múltiplos',
    operacional_ebitda: 'Operacional / EBITDA',
    fluxo_de_caixa: 'Fluxo de Caixa',
  }

  return (
    <div>
      <SectionLabel>Matriz de consenso</SectionLabel>
      <p className="text-xs text-gray-500 mb-2">
        Grau de concordância:{' '}
        <span className="font-semibold text-gray-700">{c.grau_concordancia}</span>
      </p>
      <div className="space-y-1.5 mb-3">
        {Object.entries(c.pilares_status).map(([key, val]) => {
          const badge =
            val === 'Descontada'
              ? 'bg-green-100 text-green-700'
              : val === 'Cara'
              ? 'bg-red-100 text-red-700'
              : 'bg-gray-100 text-gray-500'
          return (
            <div
              key={key}
              className="flex items-center justify-between px-3 py-2 border border-gray-100 rounded-lg bg-white"
            >
              <span className="text-sm text-gray-700">{pilarLabel[key] ?? key}</span>
              <span className={`text-xs font-semibold px-2 py-0.5 rounded ${badge}`}>
                {val ?? 'N/A'}
              </span>
            </div>
          )
        })}
      </div>
      {c.parecer_analista && (
        <div className="bg-amber-50 rounded-lg px-3 py-2.5 border-l-2 border-amber-400 text-sm text-gray-700">
          <span className="font-semibold text-amber-900">Parecer do analista: </span>
          {c.parecer_analista}
        </div>
      )}
    </div>
  )
}

const SecaoRisco = ({ r }: { r: Risco }) => (
  <div>
    <SectionLabel>Análise de risco</SectionLabel>
    <div className="grid grid-cols-2 gap-2 mb-3">
      <div className="bg-gray-50 rounded-lg p-3 text-center">
        <p className="text-xs text-gray-400 mb-1">Score fundamentalista</p>
        <p className={`text-2xl font-semibold ${scoreColor(r.score_fundamentalista)}`}>
          {r.score_fundamentalista}
          <span className="text-sm text-gray-400">/10</span>
        </p>
      </div>
      <div className="bg-orange-50 rounded-lg p-3 text-center">
        <p className="text-xs text-gray-400 mb-1">Score ajustado ao risco</p>
        <p className={`text-2xl font-semibold ${scoreColor(r.score_ajustado)}`}>
          {r.score_ajustado}
          <span className="text-sm text-gray-400">/10</span>
        </p>
      </div>
    </div>
    {r.alertas.length > 0 && (
      <div className="space-y-2">
        {r.alertas.map((a, i) => (
          <div
            key={i}
            className={`px-3 py-2.5 rounded-lg border ${
              a.nivel === 'alto'
                ? 'bg-red-50 border-red-200'
                : 'bg-yellow-50 border-yellow-200'
            }`}
          >
            <p className={`text-sm font-semibold ${a.nivel === 'alto' ? 'text-red-700' : 'text-yellow-700'}`}>
              {a.nivel === 'alto' ? '🔴' : '🟡'} {a.titulo}
            </p>
            <p className={`text-xs mt-0.5 ${a.nivel === 'alto' ? 'text-red-600' : 'text-yellow-600'}`}>
              {a.descricao}
            </p>
          </div>
        ))}
      </div>
    )}
  </div>
)

// ─── main ──────────────────────────────────────────────────────────────────

export default function App() {
  const [ticker, setTicker] = useState('')
  const [resultado, setResultado] = useState<ValuationResult | null>(null)
  const [loading, setLoading] = useState(false)
  const [erro, setErro] = useState('')

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

            {/* Cabeçalho */}
            <div className="flex justify-between items-start">
              <div>
                <h2 className="text-2xl font-bold text-gray-800">{resultado.ticker}</h2>
                <p className="text-gray-500 text-sm">{resultado.nome}</p>
                <p className="text-xs text-gray-400 mt-0.5">{resultado.setor_info.setor}</p>
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
              <p className="text-xs text-gray-400 mb-1 uppercase tracking-widest">Score de atratividade</p>
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

            <SecaoMetodos r={resultado} />

            {resultado.dcf?.cenarios && <SecaoCenariosDCF cenarios={resultado.dcf.cenarios} />}

            <SecaoEvEbitda ev={resultado.ev_ebitda} />

            {resultado.crescimento && <SecaoCrescimento c={resultado.crescimento} />}

            <SecaoCapm capm={resultado.capm} />

            {resultado.endividamento && <SecaoEndividamento e={resultado.endividamento} />}

            {resultado.consenso && <SecaoConsenso c={resultado.consenso} />}

            <SecaoRisco r={resultado.risco} />

          </div>
        )}
      </div>
    </div>
  )
}