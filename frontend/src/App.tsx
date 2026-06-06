import { useState, useEffect, useCallback } from 'react'
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

// ─── tipos watchlist ────────────────────────────────────────────────────────

interface WatchlistItem {
  ticker: string
  savedAt: string
  data: ValuationResult
}

// ─── helpers ────────────────────────────────────────────────────────────────

const WATCHLIST_KEY = 'vt_watchlist'

const loadWatchlist = (): WatchlistItem[] => {
  try {
    return JSON.parse(localStorage.getItem(WATCHLIST_KEY) ?? '[]')
  } catch {
    return []
  }
}

const saveWatchlist = (list: WatchlistItem[]) => {
  localStorage.setItem(WATCHLIST_KEY, JSON.stringify(list))
}

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

const scoreBg = (s: number) => {
  if (s >= 8) return 'bg-green-50 border-green-200'
  if (s >= 6) return 'bg-blue-50 border-blue-200'
  if (s >= 4) return 'bg-yellow-50 border-yellow-200'
  return 'bg-red-50 border-red-200'
}

const fmt = (v: number | null | undefined, prefix = '', suffix = '', decimals = 2) =>
  v != null ? `${prefix}${v.toFixed(decimals)}${suffix}` : '—'

const formatDate = (iso: string) => {
  const d = new Date(iso)
  return d.toLocaleDateString('pt-BR', { day: '2-digit', month: '2-digit', hour: '2-digit', minute: '2-digit' })
}

// ─── sub-components ─────────────────────────────────────────────────────────

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

// ─── section components ─────────────────────────────────────────────────────

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
        <MetricCard label="Preço justo" value={ev.preco_justo ? `R$ ${ev.preco_justo.toFixed(2)}` : '—'} />
      </div>
      <MethodRow nome="Classificação EV/EBITDA" classificacao={ev.classificacao} />
    </div>
  )
}

const SecaoCrescimento = ({ c }: { c: CrescimentoInfo | null | undefined }) => {
  if (!c) return null
  const getPegHighlight = (peg: number | null | undefined) => {
    if (peg == null) return undefined
    if (peg < 1) return 'green' as const
    if (peg > 2) return 'red' as const
    return undefined
  }
  const getRuleOf40Highlight = (score: number | null | undefined) => {
    if (score == null) return undefined
    if (score >= 40) return 'green' as const
    if (score >= 20) return 'amber' as const
    return 'red' as const
  }
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
          value={c.dcf_duas_fases?.valor_intrinseco ? `R$ ${c.dcf_duas_fases.valor_intrinseco.toFixed(2)}` : '—'}
          highlight={
            c.dcf_duas_fases?.classificacao === 'Descontada' ? 'green' :
            c.dcf_duas_fases?.classificacao === 'Cara' ? 'red' : undefined
          }
        />
      </div>
      {c.peg?.observacao && <p className="text-xs text-gray-400 mt-1">{c.peg.observacao}</p>}
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
    e.classificacao === 'Crítico' ? 'bg-red-50 border-red-200 text-red-700' :
    e.classificacao === 'Alto' ? 'bg-yellow-50 border-yellow-200 text-yellow-700' :
    'bg-gray-50 border-gray-200 text-gray-600'
  return (
    <div>
      <SectionLabel>Endividamento</SectionLabel>
      <div className="grid grid-cols-2 gap-2 mb-2">
        <MetricCard
          label="Dívida / EBIT"
          value={fmt(e.div_ebit, '', 'x')}
          highlight={e.div_ebit != null ? (e.div_ebit > 5 ? 'red' : e.div_ebit > 3 ? 'amber' : 'green') : undefined}
        />
        <MetricCard
          label="Classificação"
          value={e.classificacao}
          highlight={e.classificacao === 'Crítico' ? 'red' : e.classificacao === 'Alto' ? 'amber' : 'green'}
        />
      </div>
      {e.alertas?.map((a: any, i) => (
        <div key={i} className={`px-3 py-2 rounded-lg border text-xs mb-1 ${alertColor}`}>
          {typeof a === 'object' && a !== null
            ? <><span className="font-semibold">{a.titulo}:</span> {a.descricao}</>
            : a}
        </div>
      ))}
    </div>
  )
}

const SecaoConsenso = ({ c }: { c: ConsensoInfo }) => {
  if (!c?.pilares_status) return null
  const pilarLabel: Record<string, string> = {
    patrimonial_multiplos: 'Patrimonial / Múltiplos',
    operacional_ebitda: 'Operacional / EBITDA',
    fluxo_de_caixa: 'Fluxo de Caixa',
  }
  return (
    <div>
      <SectionLabel>Matriz de consenso</SectionLabel>
      <p className="text-xs text-gray-500 mb-2">
        Grau de concordância: <span className="font-semibold text-gray-700">{c.grau_concordancia}</span>
      </p>
      <div className="space-y-1.5 mb-3">
        {Object.entries(c.pilares_status).map(([key, val]) => {
          const badge =
            val === 'Descontada' ? 'bg-green-100 text-green-700' :
            val === 'Cara' ? 'bg-red-100 text-red-700' :
            'bg-gray-100 text-gray-500'
          return (
            <div key={key} className="flex items-center justify-between px-3 py-2 border border-gray-100 rounded-lg bg-white">
              <span className="text-sm text-gray-700">{pilarLabel[key] ?? key}</span>
              <span className={`text-xs font-semibold px-2 py-0.5 rounded ${badge}`}>{val ?? 'N/A'}</span>
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
          {r.score_fundamentalista}<span className="text-sm text-gray-400">/10</span>
        </p>
      </div>
      <div className="bg-orange-50 rounded-lg p-3 text-center">
        <p className="text-xs text-gray-400 mb-1">Score ajustado ao risco</p>
        <p className={`text-2xl font-semibold ${scoreColor(r.score_ajustado)}`}>
          {r.score_ajustado}<span className="text-sm text-gray-400">/10</span>
        </p>
      </div>
    </div>
    {r.alertas.length > 0 && (
      <div className="space-y-2">
        {r.alertas.map((a, i) => (
          <div key={i} className={`px-3 py-2.5 rounded-lg border ${a.nivel === 'alto' ? 'bg-red-50 border-red-200' : 'bg-yellow-50 border-yellow-200'}`}>
            <p className={`text-sm font-semibold ${a.nivel === 'alto' ? 'text-red-700' : 'text-yellow-700'}`}>
              {a.nivel === 'alto' ? '🔴' : '🟡'} {a.titulo}
            </p>
            <p className={`text-xs mt-0.5 ${a.nivel === 'alto' ? 'text-red-600' : 'text-yellow-600'}`}>{a.descricao}</p>
          </div>
        ))}
      </div>
    )}
  </div>
)

// ─── watchlist card ──────────────────────────────────────────────────────────

const WatchlistCard = ({
  item,
  onRemove,
  onRefresh,
  onExpand,
  refreshing,
}: {
  item: WatchlistItem
  onRemove: (ticker: string) => void
  onRefresh: (ticker: string) => void
  onExpand: (result: ValuationResult) => void
  refreshing: boolean
}) => {
  const r = item.data
  const score = r.risco.score_ajustado

  return (
    <div className={`bg-white rounded-2xl shadow-sm border ${scoreBg(score)} p-4`}>
      {/* cabeçalho */}
      <div className="flex items-start justify-between mb-3">
        <div>
          <div className="flex items-center gap-2">
            <h3 className="text-lg font-bold text-gray-800">{r.ticker}</h3>
            <span className={`text-xl font-bold ${scoreColor(score)}`}>{score}<span className="text-xs text-gray-400">/10</span></span>
          </div>
          <p className="text-xs text-gray-400 truncate max-w-[180px]">{r.nome}</p>
          <p className="text-xs text-gray-400">{r.setor_info.setor}</p>
        </div>
        <div className="text-right">
          <p className="text-lg font-bold text-gray-800">R$ {r.preco_atual.toFixed(2)}</p>
          <p className="text-xs text-gray-400">{r.score.classificacao}</p>
        </div>
      </div>

      {/* pilares consenso resumido */}
      {r.consenso?.pilares_status && (
        <div className="flex gap-1.5 mb-3">
          {Object.entries(r.consenso.pilares_status).map(([key, val]) => {
            const short: Record<string, string> = {
              patrimonial_multiplos: 'Patrim.',
              operacional_ebitda: 'Operac.',
              fluxo_de_caixa: 'FCL',
            }
            const badge =
              val === 'Descontada' ? 'bg-green-100 text-green-700' :
              val === 'Cara' ? 'bg-red-100 text-red-700' :
              'bg-gray-100 text-gray-500'
            return (
              <span key={key} className={`text-xs font-medium px-2 py-0.5 rounded-full ${badge}`}>
                {short[key] ?? key}
              </span>
            )
          })}
        </div>
      )}

      {/* parecer resumido */}
      {r.consenso?.parecer_analista && (
        <p className="text-xs text-gray-500 italic mb-3 line-clamp-2">"{r.consenso.parecer_analista}"</p>
      )}

      {/* rodapé */}
      <div className="flex items-center justify-between pt-2 border-t border-gray-100">
        <p className="text-xs text-gray-300">Atualizado {formatDate(item.savedAt)}</p>
        <div className="flex gap-2">
          <button
            onClick={() => onExpand(r)}
            className="text-xs text-blue-600 hover:text-blue-800 font-medium transition"
          >
            Ver análise
          </button>
          <button
            onClick={() => onRefresh(item.ticker)}
            disabled={refreshing}
            className="text-xs text-gray-400 hover:text-gray-600 font-medium transition disabled:opacity-40"
          >
            {refreshing ? '↻ Atualizando...' : '↻ Atualizar'}
          </button>
          <button
            onClick={() => onRemove(item.ticker)}
            className="text-xs text-red-400 hover:text-red-600 font-medium transition"
          >
            Remover
          </button>
        </div>
      </div>
    </div>
  )
}

// ─── tela watchlist ──────────────────────────────────────────────────────────

const TelaWatchlist = ({
  watchlist,
  onRemove,
  onRefresh,
  onRefreshAll,
  onExpand,
  refreshingTicker,
  refreshingAll,
}: {
  watchlist: WatchlistItem[]
  onRemove: (ticker: string) => void
  onRefresh: (ticker: string) => void
  onRefreshAll: () => void
  onExpand: (result: ValuationResult) => void
  refreshingTicker: string | null
  refreshingAll: boolean
}) => {
  if (watchlist.length === 0) {
    return (
      <div className="text-center py-16">
        <p className="text-4xl mb-3">📋</p>
        <p className="text-gray-500 font-medium">Watchlist vazia</p>
        <p className="text-sm text-gray-400 mt-1">Busque um ticker e clique em "Salvar na Watchlist"</p>
      </div>
    )
  }

  const totalTickers = watchlist.length
  const mediaScore = watchlist.reduce((acc, i) => acc + i.data.risco.score_ajustado, 0) / totalTickers
  const descontadas = watchlist.filter(i => i.data.risco.score_ajustado >= 6).length

  return (
    <div className="space-y-4">
      {/* resumo geral */}
      <div className="grid grid-cols-3 gap-3">
        <div className="bg-white rounded-xl p-3 text-center shadow-sm border border-gray-100">
          <p className="text-xs text-gray-400 mb-0.5">Tickers</p>
          <p className="text-2xl font-bold text-gray-800">{totalTickers}</p>
        </div>
        <div className="bg-white rounded-xl p-3 text-center shadow-sm border border-gray-100">
          <p className="text-xs text-gray-400 mb-0.5">Score médio</p>
          <p className={`text-2xl font-bold ${scoreColor(mediaScore)}`}>{mediaScore.toFixed(1)}</p>
        </div>
        <div className="bg-white rounded-xl p-3 text-center shadow-sm border border-gray-100">
          <p className="text-xs text-gray-400 mb-0.5">Score ≥ 6</p>
          <p className="text-2xl font-bold text-green-700">{descontadas}</p>
        </div>
      </div>

      {/* botão atualizar tudo */}
      <button
        onClick={onRefreshAll}
        disabled={refreshingAll}
        className="w-full py-2.5 rounded-xl text-sm font-semibold border border-gray-200 bg-white text-gray-600 hover:bg-gray-50 hover:text-gray-800 disabled:opacity-50 transition"
      >
        {refreshingAll ? '↻ Atualizando todos...' : `↻ Atualizar tudo (${totalTickers})`}
      </button>

      {/* cards */}
      {watchlist
        .slice()
        .sort((a, b) => b.data.risco.score_ajustado - a.data.risco.score_ajustado)
        .map(item => (
          <WatchlistCard
            key={item.ticker}
            item={item}
            onRemove={onRemove}
            onRefresh={onRefresh}
            onExpand={onExpand}
            refreshing={refreshingTicker === item.ticker}
          />
        ))}
    </div>
  )
}

// ─── resultado completo ──────────────────────────────────────────────────────

const ResultadoCompleto = ({
  resultado,
  isInWatchlist,
  onToggleWatchlist,
}: {
  resultado: ValuationResult
  isInWatchlist: boolean
  onToggleWatchlist: () => void
}) => (
  <div className="bg-white rounded-2xl shadow p-6 space-y-6">
    {/* Cabeçalho */}
    <div className="flex justify-between items-start">
      <div>
        <h2 className="text-2xl font-bold text-gray-800">{resultado.ticker}</h2>
        <p className="text-gray-500 text-sm">{resultado.nome}</p>
        <p className="text-xs text-gray-400 mt-0.5">{resultado.setor_info.setor}</p>
      </div>
      <div className="text-right">
        <p className="text-2xl font-bold text-gray-800">R$ {resultado.preco_atual.toFixed(2)}</p>
        <p className="text-xs text-gray-400">preço atual</p>
      </div>
    </div>

    {/* Score */}
    <div className="bg-blue-50 rounded-xl p-4 text-center">
      <p className="text-xs text-gray-400 mb-1 uppercase tracking-widest">Score de atratividade</p>
      <p className={`text-5xl font-bold ${scoreColor(resultado.score.score)}`}>
        {resultado.score.score}<span className="text-lg text-gray-400">/10</span>
      </p>
      <p className={`text-lg font-semibold mt-1 ${scoreColor(resultado.score.score)}`}>
        {resultado.score.classificacao}
      </p>
      <p className="text-xs text-gray-400 mt-1">Baseado em {resultado.score.metodos_aplicados} método(s)</p>
    </div>

    {/* Botão watchlist */}
    <button
      onClick={onToggleWatchlist}
      className={`w-full py-2.5 rounded-xl font-semibold text-sm transition ${
        isInWatchlist
          ? 'bg-gray-100 text-gray-500 hover:bg-red-50 hover:text-red-600 border border-gray-200'
          : 'bg-blue-700 text-white hover:bg-blue-800'
      }`}
    >
      {isInWatchlist ? '✓ Na Watchlist — clique para remover' : '+ Salvar na Watchlist'}
    </button>

    <SecaoMetodos r={resultado} />
    {resultado.dcf?.cenarios && <SecaoCenariosDCF cenarios={resultado.dcf.cenarios} />}
    <SecaoEvEbitda ev={resultado.ev_ebitda} />
    {resultado.crescimento && <SecaoCrescimento c={resultado.crescimento} />}
    <SecaoCapm capm={resultado.capm} />
    {resultado.endividamento && <SecaoEndividamento e={resultado.endividamento} />}
    {resultado.consenso && <SecaoConsenso c={resultado.consenso} />}
    <SecaoRisco r={resultado.risco} />
  </div>
)

// ─── main ────────────────────────────────────────────────────────────────────

type Tela = 'busca' | 'watchlist'

export default function App() {
  const [tela, setTela] = useState<Tela>('busca')
  const [ticker, setTicker] = useState('')
  const [resultado, setResultado] = useState<ValuationResult | null>(null)
  const [loading, setLoading] = useState(false)
  const [erro, setErro] = useState('')
  const [watchlist, setWatchlist] = useState<WatchlistItem[]>(loadWatchlist)
  const [refreshingTicker, setRefreshingTicker] = useState<string | null>(null)
  const [refreshingAll, setRefreshingAll] = useState(false)

  // persiste watchlist sempre que muda
  useEffect(() => {
    saveWatchlist(watchlist)
  }, [watchlist])

  const isInWatchlist = resultado ? watchlist.some(i => i.ticker === resultado.ticker) : false

  const buscar = async (tickerAlvo?: string) => {
    const t = (tickerAlvo ?? ticker).trim().toUpperCase()
    if (!t) return
    setLoading(true)
    setErro('')
    if (!tickerAlvo) setResultado(null)
    try {
      const { data } = await axios.get<ValuationResult>(`/api/valuation/${t}`)
      setResultado(data)
      if (!tickerAlvo) setTela('busca')
      return data
    } catch (e: any) {
      setErro(e.response?.data?.detail ?? 'Erro ao buscar dados. Tente novamente.')
      return null
    } finally {
      setLoading(false)
    }
  }

  const handleKeyDown = (e: React.KeyboardEvent) => {
    if (e.key === 'Enter') buscar()
  }

  const toggleWatchlist = () => {
    if (!resultado) return
    if (isInWatchlist) {
      setWatchlist(prev => prev.filter(i => i.ticker !== resultado.ticker))
    } else {
      setWatchlist(prev => [
        ...prev.filter(i => i.ticker !== resultado.ticker),
        { ticker: resultado.ticker, savedAt: new Date().toISOString(), data: resultado },
      ])
    }
  }

  const removeFromWatchlist = (t: string) => {
    setWatchlist(prev => prev.filter(i => i.ticker !== t))
  }

  const refreshTicker = useCallback(async (t: string) => {
    setRefreshingTicker(t)
    try {
      const { data } = await axios.get<ValuationResult>(`/api/valuation/${t}`)
      setWatchlist(prev =>
        prev.map(i =>
          i.ticker === t ? { ...i, savedAt: new Date().toISOString(), data } : i
        )
      )
    } catch {
      // erro silencioso no card
    } finally {
      setRefreshingTicker(null)
    }
  }, [])

  const refreshAll = useCallback(async () => {
    if (watchlist.length === 0) return
    setRefreshingAll(true)
    await Promise.allSettled(
      watchlist.map(async item => {
        setRefreshingTicker(item.ticker)
        try {
          const { data } = await axios.get<ValuationResult>(`/api/valuation/${item.ticker}`)
          setWatchlist(prev =>
            prev.map(i => i.ticker === item.ticker ? { ...i, savedAt: new Date().toISOString(), data } : i)
          )
        } catch {
          // erro silencioso por ticker
        } finally {
          setRefreshingTicker(null)
        }
      })
    )
    setRefreshingAll(false)
  }, [watchlist])

  const expandResult = (r: ValuationResult) => {
    setResultado(r)
    setTicker(r.ticker)
    setTela('busca')
  }

  return (
    <div className="min-h-screen bg-gray-100 p-6">
      <div className="max-w-xl mx-auto">

        {/* Header */}
        <div className="mb-6 text-center">
          <h1 className="text-3xl font-bold text-blue-900">Valuation Tracker</h1>
          <p className="text-gray-500 mt-1">Análise fundamentalista de ações da B3</p>
        </div>

        {/* Navegação */}
        <div className="flex gap-1 mb-6 bg-white rounded-xl p-1 shadow-sm border border-gray-100">
          <button
            onClick={() => setTela('busca')}
            className={`flex-1 py-2 text-sm font-semibold rounded-lg transition ${
              tela === 'busca' ? 'bg-blue-700 text-white' : 'text-gray-500 hover:text-gray-700'
            }`}
          >
            🔍 Buscar
          </button>
          <button
            onClick={() => setTela('watchlist')}
            className={`flex-1 py-2 text-sm font-semibold rounded-lg transition ${
              tela === 'watchlist' ? 'bg-blue-700 text-white' : 'text-gray-500 hover:text-gray-700'
            }`}
          >
            📋 Watchlist {watchlist.length > 0 && <span className="ml-1 bg-blue-100 text-blue-700 text-xs px-1.5 py-0.5 rounded-full">{watchlist.length}</span>}
          </button>
        </div>

        {/* Tela: Busca */}
        {tela === 'busca' && (
          <>
            <div className="flex gap-2 mb-6">
              <input
                className="flex-1 px-4 py-2 rounded-lg border border-gray-300 focus:outline-none focus:ring-2 focus:ring-blue-400 uppercase"
                placeholder="Digite o ticker... ex: PETR4"
                value={ticker}
                onChange={e => setTicker(e.target.value)}
                onKeyDown={handleKeyDown}
              />
              <button
                onClick={() => buscar()}
                disabled={loading}
                className="px-6 py-2 bg-blue-700 text-white rounded-lg font-semibold hover:bg-blue-800 disabled:opacity-50 transition"
              >
                {loading ? 'Buscando...' : 'Analisar'}
              </button>
            </div>

            {erro && (
              <div className="bg-red-50 border border-red-200 text-red-700 px-4 py-3 rounded-lg mb-4">
                {erro}
              </div>
            )}

            {resultado && (
              <ResultadoCompleto
                resultado={resultado}
                isInWatchlist={isInWatchlist}
                onToggleWatchlist={toggleWatchlist}
              />
            )}
          </>
        )}

        {/* Tela: Watchlist */}
        {tela === 'watchlist' && (
          <TelaWatchlist
            watchlist={watchlist}
            onRemove={removeFromWatchlist}
            onRefresh={refreshTicker}
            onRefreshAll={refreshAll}
            onExpand={expandResult}
            refreshingTicker={refreshingTicker}
            refreshingAll={refreshingAll}
          />
        )}

      </div>
    </div>
  )
}
