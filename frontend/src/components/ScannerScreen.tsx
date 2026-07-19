import { useEffect, useMemo, useRef, useState } from 'react'
import type { ScannerAtivo, ScannerSnapshot } from '../types'

// ─── helpers (auto-contidos, mesma paleta usada no restante do app) ─────────

const scoreColor = (s: number) => {
  if (s >= 8) return 'text-green-700'
  if (s >= 6) return 'text-blue-700'
  if (s >= 4) return 'text-yellow-600'
  return 'text-red-600'
}

const scoreBadgeBg = (s: number) => {
  if (s >= 8) return 'bg-green-100 text-green-700'
  if (s >= 6) return 'bg-blue-100 text-blue-700'
  if (s >= 4) return 'bg-yellow-100 text-yellow-700'
  return 'bg-red-100 text-red-700'
}

const classIcon: Record<string, string> = {
  'Muito Atrativa': '✅',
  'Muito Atrativa / Alta Convicção': '✅',
  Atrativa: '✅',
  Neutra: '⚠️',
  'Cara / Evitar': '❌',
  'Risco Elevado / Evitar': '❌',
  'Alto Risco / Evitar': '❌',
}

const formatDate = (iso: string) => {
  if (!iso) return '—'
  const d = new Date(iso)
  return d.toLocaleDateString('pt-BR', { day: '2-digit', month: '2-digit', hour: '2-digit', minute: '2-digit' })
}

const fmtPct = (v: number | null | undefined) =>
  v != null ? `${v > 0 ? '+' : ''}${v.toFixed(1)}%` : '—'

type Ordenacao = 'score' | 'margem' | 'dy'

const PAGE_SIZE = 30
const POLL_INTERVAL_MS = 10_000
const POLL_MAX_TENTATIVAS = 60 // ~10 minutos

interface ScannerScreenProps {
  onSelecionarTicker: (ticker: string) => void
}

export default function ScannerScreen({ onSelecionarTicker }: ScannerScreenProps) {
  const [snapshot, setSnapshot] = useState<ScannerSnapshot | null>(null)
  const [loading, setLoading] = useState(true)
  const [erro, setErro] = useState('')

  const [disparando, setDisparando] = useState(false)
  const [statusVarredura, setStatusVarredura] = useState('')
  const [aguardandoNovosDados, setAguardandoNovosDados] = useState(false)

  const [setorFiltro, setSetorFiltro] = useState('Todos')
  const [scoreMinimo, setScoreMinimo] = useState(0)
  const [ordenarPor, setOrdenarPor] = useState<Ordenacao>('score')
  const [visibleCount, setVisibleCount] = useState(PAGE_SIZE)

  const pollRef = useRef<{ timer: number | null; tentativas: number; dataAnterior: string }>({
    timer: null,
    tentativas: 0,
    dataAnterior: '',
  })

  const carregarSnapshot = async (silencioso = false) => {
    if (!silencioso) setLoading(true)
    try {
      const res = await fetch('/api/scanner/resultado')
      if (res.status === 404) {
        setSnapshot(null)
        setErro('')
        return null
      }
      if (!res.ok) throw new Error(`Erro ${res.status} ao carregar snapshot`)
      const data: ScannerSnapshot = await res.json()
      setSnapshot(data)
      setErro('')
      return data
    } catch (e: any) {
      setErro(e.message ?? 'Erro ao carregar dados do scanner.')
      return null
    } finally {
      if (!silencioso) setLoading(false)
    }
  }

  useEffect(() => {
    carregarSnapshot()
    return () => {
      if (pollRef.current.timer) window.clearInterval(pollRef.current.timer)
    }
  }, [])

  const pararPolling = () => {
    if (pollRef.current.timer) {
      window.clearInterval(pollRef.current.timer)
      pollRef.current.timer = null
    }
    setAguardandoNovosDados(false)
  }

  const iniciarPolling = (dataAtual: string) => {
    pollRef.current.dataAnterior = dataAtual
    pollRef.current.tentativas = 0
    setAguardandoNovosDados(true)
    pollRef.current.timer = window.setInterval(async () => {
      pollRef.current.tentativas += 1
      const data = await carregarSnapshot(true)
      const mudou = data && data.data_atualizacao !== pollRef.current.dataAnterior
      if (mudou) {
        setStatusVarredura(`Concluída às ${formatDate(data!.data_atualizacao)}`)
        pararPolling()
      } else if (pollRef.current.tentativas >= POLL_MAX_TENTATIVAS) {
        setStatusVarredura('Varredura ainda em andamento — atualize manualmente em alguns minutos.')
        pararPolling()
      }
    }, POLL_INTERVAL_MS)
  }

  const dispararScan = async () => {
    setDisparando(true)
    setStatusVarredura('')
    try {
      const res = await fetch('/api/scanner/disparar', { method: 'POST' })
      const data = await res.json()
      if (data.status === 'ja_em_andamento') {
        setStatusVarredura('Já existe uma varredura em andamento — aguardando conclusão...')
        iniciarPolling(snapshot?.data_atualizacao ?? '')
      } else {
        setStatusVarredura(`Varredura iniciada às ${formatDate(new Date().toISOString())} — atualizando a cada 10s...`)
        iniciarPolling(snapshot?.data_atualizacao ?? '')
      }
    } catch (e: any) {
      setStatusVarredura('Erro ao disparar varredura: ' + (e.message ?? 'desconhecido'))
    } finally {
      setDisparando(false)
    }
  }

  const setores = useMemo(() => {
    if (!snapshot) return []
    return snapshot.setores
      .map(g => ({ setor: g.setor, perfil: g.perfil, count: g.ativos.length }))
      .sort((a, b) => a.setor.localeCompare(b.setor))
  }, [snapshot])

  const ativosFiltrados = useMemo(() => {
    if (!snapshot) return []
    let lista: ScannerAtivo[] = snapshot.setores.flatMap(g => g.ativos)
    if (setorFiltro !== 'Todos') lista = lista.filter(a => a.setor === setorFiltro)
    if (scoreMinimo > 0) lista = lista.filter(a => a.score_atratividade >= scoreMinimo)

    const comparadores: Record<Ordenacao, (a: ScannerAtivo, b: ScannerAtivo) => number> = {
      score: (a, b) => b.score_atratividade - a.score_atratividade,
      margem: (a, b) => (b.margem_seguranca ?? -Infinity) - (a.margem_seguranca ?? -Infinity),
      dy: (a, b) => (b.dividend_yield ?? 0) - (a.dividend_yield ?? 0),
    }
    return lista.slice().sort(comparadores[ordenarPor])
  }, [snapshot, setorFiltro, scoreMinimo, ordenarPor])

  useEffect(() => {
    setVisibleCount(PAGE_SIZE)
  }, [setorFiltro, scoreMinimo, ordenarPor])

  if (loading) {
    return <p className="text-center text-gray-400 py-16 animate-pulse">Carregando scanner...</p>
  }

  if (erro && !snapshot) {
    return (
      <div className="bg-red-50 border border-red-200 text-red-700 px-4 py-3 rounded-lg">
        {erro}
      </div>
    )
  }

  if (!snapshot) {
    return (
      <div className="text-center py-16">
        <p className="text-4xl mb-3">🔎</p>
        <p className="text-gray-500 font-medium">Nenhuma varredura foi gerada ainda</p>
        <p className="text-sm text-gray-400 mt-1 mb-4">Rode a primeira varredura da B3 para ver as oportunidades por setor.</p>
        <button
          onClick={dispararScan}
          disabled={disparando}
          className="px-6 py-2.5 bg-blue-700 text-white rounded-lg font-semibold hover:bg-blue-800 disabled:opacity-50 transition"
        >
          {disparando ? 'Disparando...' : '🔄 Rodar primeira varredura'}
        </button>
        {statusVarredura && <p className="text-xs text-gray-400 mt-3">{statusVarredura}</p>}
      </div>
    )
  }

  const ativosVisiveis = ativosFiltrados.slice(0, visibleCount)

  return (
    <div className="space-y-4">
      {/* cabeçalho / resumo */}
      <div className="bg-white rounded-2xl shadow-sm border border-gray-100 p-4">
        <div className="flex items-start justify-between gap-3 flex-wrap">
          <div>
            <h2 className="text-lg font-bold text-gray-800">Scanner B3</h2>
            <p className="text-xs text-gray-400">
              Última varredura: {formatDate(snapshot.data_atualizacao)}
            </p>
          </div>
          <button
            onClick={dispararScan}
            disabled={disparando || aguardandoNovosDados}
            className="px-4 py-2 bg-blue-700 text-white rounded-lg text-sm font-semibold hover:bg-blue-800 disabled:opacity-50 transition whitespace-nowrap"
          >
            {aguardandoNovosDados ? '↻ Rodando...' : disparando ? 'Disparando...' : '🔄 Rodar nova varredura'}
          </button>
        </div>
        {statusVarredura && (
          <p className={`text-xs mt-2 ${aguardandoNovosDados ? 'text-blue-600 animate-pulse' : 'text-gray-400'}`}>
            {statusVarredura}
          </p>
        )}

        <div className="grid grid-cols-3 gap-2 mt-3">
          <div className="bg-gray-50 rounded-lg p-2.5 text-center">
            <p className="text-xs text-gray-400">Ativos analisados</p>
            <p className="text-xl font-bold text-gray-800">{snapshot.total_ativos_analisados}</p>
          </div>
          <div className="bg-gray-50 rounded-lg p-2.5 text-center">
            <p className="text-xs text-gray-400">Setores</p>
            <p className="text-xl font-bold text-gray-800">{snapshot.setores.length}</p>
          </div>
          <div className="bg-gray-50 rounded-lg p-2.5 text-center">
            <p className="text-xs text-gray-400">Falhas</p>
            <p className="text-xl font-bold text-gray-500">{snapshot.total_erros}</p>
          </div>
        </div>

        {snapshot.erros.length > 0 && (
          <details className="mt-2">
            <summary className="text-xs text-gray-400 cursor-pointer hover:text-gray-600">
              Ver {snapshot.erros.length} ticker(s) que falharam
            </summary>
            <div className="mt-1.5 max-h-32 overflow-y-auto space-y-1">
              {snapshot.erros.map((e, i) => (
                <p key={i} className="text-[11px] text-gray-400">
                  <span className="font-semibold text-gray-500">{e.ticker}:</span> {e.motivo}
                </p>
              ))}
            </div>
          </details>
        )}
      </div>

      {/* filtros */}
      <div className="bg-white rounded-2xl shadow-sm border border-gray-100 p-4 flex flex-wrap gap-3 items-end">
        <div className="flex-1 min-w-[140px]">
          <label className="text-xs text-gray-400 block mb-1">Setor</label>
          <select
            value={setorFiltro}
            onChange={e => setSetorFiltro(e.target.value)}
            className="w-full px-3 py-1.5 rounded-lg border border-gray-300 text-sm focus:outline-none focus:ring-2 focus:ring-blue-400"
          >
            <option value="Todos">Todos ({snapshot.total_ativos_analisados})</option>
            {setores.map(s => (
              <option key={s.setor} value={s.setor}>{s.setor} ({s.count})</option>
            ))}
          </select>
        </div>
        <div className="w-28">
          <label className="text-xs text-gray-400 block mb-1">Score mín.</label>
          <input
            type="number"
            min={0}
            max={10}
            step={0.5}
            value={scoreMinimo}
            onChange={e => setScoreMinimo(Number(e.target.value))}
            className="w-full px-3 py-1.5 rounded-lg border border-gray-300 text-sm focus:outline-none focus:ring-2 focus:ring-blue-400"
          />
        </div>
        <div className="w-36">
          <label className="text-xs text-gray-400 block mb-1">Ordenar por</label>
          <select
            value={ordenarPor}
            onChange={e => setOrdenarPor(e.target.value as Ordenacao)}
            className="w-full px-3 py-1.5 rounded-lg border border-gray-300 text-sm focus:outline-none focus:ring-2 focus:ring-blue-400"
          >
            <option value="score">Score</option>
            <option value="margem">Margem de segurança</option>
            <option value="dy">Dividend Yield</option>
          </select>
        </div>
      </div>

      {/* tabela ranqueada */}
      {ativosFiltrados.length === 0 ? (
        <p className="text-center text-gray-400 py-10 text-sm">Nenhum ativo encontrado com esses filtros.</p>
      ) : (
        <div className="overflow-x-auto rounded-lg border border-gray-200 bg-white shadow-sm">
          <table className="w-full text-left text-xs text-gray-600">
            <thead className="bg-gray-50 text-gray-500 font-semibold uppercase border-b border-gray-200">
              <tr>
                <th className="px-3 py-2">Ativo</th>
                {setorFiltro === 'Todos' && <th className="px-3 py-2">Setor</th>}
                <th className="px-3 py-2">Score</th>
                <th className="px-3 py-2">Classificação</th>
                <th className="px-3 py-2">Margem seg.</th>
                <th className="px-3 py-2">DY</th>
                <th className="px-3 py-2">Preço</th>
                <th className="px-3 py-2">Alertas</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-gray-100">
              {ativosVisiveis.map(a => (
                <tr
                  key={a.ticker}
                  onClick={() => onSelecionarTicker(a.ticker)}
                  className="hover:bg-blue-50/60 transition-colors cursor-pointer"
                >
                  <td className="px-3 py-2.5">
                    <p className="font-bold text-gray-800">{a.ticker}</p>
                    <p className="text-[11px] text-gray-400 truncate max-w-[140px]">{a.nome}</p>
                  </td>
                  {setorFiltro === 'Todos' && (
                    <td className="px-3 py-2.5 text-[11px] text-gray-500">{a.setor}</td>
                  )}
                  <td className="px-3 py-2.5">
                    <span className={`text-xs font-bold px-2 py-0.5 rounded-full ${scoreBadgeBg(a.score_atratividade)}`}>
                      {a.score_atratividade.toFixed(1)}
                    </span>
                  </td>
                  <td className={`px-3 py-2.5 font-medium ${scoreColor(a.score_atratividade)}`}>
                    {classIcon[a.classificacao] ?? ''} {a.classificacao}
                  </td>
                  <td className="px-3 py-2.5">{fmtPct(a.margem_seguranca)}</td>
                  <td className="px-3 py-2.5">{a.dividend_yield ? `${a.dividend_yield.toFixed(1)}%` : '—'}</td>
                  <td className="px-3 py-2.5">R$ {a.preco_atual.toFixed(2)}</td>
                  <td className="px-3 py-2.5">
                    {a.alerta_valor_trap && (
                      <span title="Score alto mas saúde financeira indisponível ou crítica — possível armadilha de valor" className="text-red-500">
                        ⚠️
                      </span>
                    )}
                    {a.liquidez_ok === false && (
                      <span title="Liquidez diária abaixo de R$ 500 mil" className="text-gray-400 ml-1">💧</span>
                    )}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}

      {visibleCount < ativosFiltrados.length && (
        <button
          onClick={() => setVisibleCount(v => v + PAGE_SIZE)}
          className="w-full py-2.5 rounded-xl text-sm font-semibold border border-gray-200 bg-white text-gray-600 hover:bg-gray-50 hover:text-gray-800 transition"
        >
          Carregar mais ({ativosFiltrados.length - visibleCount} restantes)
        </button>
      )}
    </div>
  )
}
