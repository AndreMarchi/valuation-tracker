// CenariosSensibilidade.tsx
// Card de Cenários (pessimista/base/otimista) + Matriz de Sensibilidade do
// DCF principal. Dados vêm de POST /api/valuation/{ticker}/cenarios
// (backend/cenarios_sensibilidade.py) — endpoint próprio, não faz parte do
// payload principal de /api/valuation/{ticker}, por isso o componente busca
// os próprios dados ao montar/trocar de ticker.

import { useEffect, useState } from "react";
import axios from "axios";
import type { CenariosSensibilidadeResult, MatrizSensibilidade, VariavelSensibilidade, ValorLiquidacaoResult } from "../../types";

interface Props {
  ticker: string;
  precoAtual: number;
}

const LABEL_VARIAVEL: Record<VariavelSensibilidade, string> = {
  wacc: "WACC",
  g_perpetuo: "g perpétuo",
  margem_ebitda: "Margem EBITDA",
  crescimento_receita: "Cresc. Receita",
};

const fmtAcao = (v: number | null | undefined): string =>
  v == null ? "—" : v.toLocaleString("pt-BR", { style: "currency", currency: "BRL", minimumFractionDigits: 2 });

const fmtPct = (v: number | null | undefined): string => (v == null ? "—" : `${(v * 100).toFixed(1)}%`);

type OpcaoMatriz = "wacc_x_g_perpetuo" | "wacc_x_margem_ebitda" | "margem_ebitda_x_crescimento_receita";

const OPCOES_MATRIZ: { key: OpcaoMatriz; label: string }[] = [
  { key: "wacc_x_g_perpetuo", label: "WACC × g perpétuo" },
  { key: "wacc_x_margem_ebitda", label: "WACC × Margem EBITDA" },
  { key: "margem_ebitda_x_crescimento_receita", label: "Margem EBITDA × Cresc. Receita" },
];

function FaixaValorBar({
  minimo,
  base,
  maximo,
  precoAtual,
  valorLiquidacao,
}: {
  minimo: number;
  base: number;
  maximo: number;
  precoAtual: number;
  valorLiquidacao?: number | null;
}) {
  // O piso de liquidação (Fase 2) fica quase sempre abaixo do cenário
  // pessimista (ver CONTEXT.md) — o domínio da barra precisa se estender
  // pra baixo pra mostrar o marcador, senão ele fica cravado no 0% e
  // escondido atrás do próprio pessimista.
  const dominioMinimo = valorLiquidacao != null ? Math.min(minimo, valorLiquidacao) : minimo;
  const span = maximo - dominioMinimo;
  const pos = (v: number) => {
    if (span <= 0) return 50;
    return Math.min(100, Math.max(0, ((v - dominioMinimo) / span) * 100));
  };
  const precoForaDaFaixa = precoAtual < minimo || precoAtual > maximo;

  return (
    <div className="mt-1 mb-3">
      <div className="relative h-2.5 rounded-full bg-gradient-to-r from-red-200 via-blue-200 to-green-200">
        {valorLiquidacao != null && (
          <div
            className="absolute top-1/2 -translate-y-1/2 -translate-x-1/2 z-10"
            style={{ left: `${pos(valorLiquidacao)}%` }}
            title={`Valor de liquidação (piso): ${fmtAcao(valorLiquidacao)}`}
          >
            <div className="w-0.5 h-5 bg-purple-700 -translate-y-1/4" />
          </div>
        )}
        <div
          className="absolute top-1/2 -translate-y-1/2 -translate-x-1/2 w-3 h-3 rounded-full bg-blue-700 border-2 border-white shadow"
          style={{ left: `${pos(base)}%` }}
          title={`Base: ${fmtAcao(base)}`}
        />
        <div
          className="absolute top-1/2 -translate-y-1/2 -translate-x-1/2 w-0 h-0"
          style={{ left: `${pos(precoAtual)}%` }}
          title={`Preço atual: ${fmtAcao(precoAtual)}`}
        >
          <div className="w-0.5 h-4 bg-gray-800 -translate-y-1/4" />
        </div>
      </div>
      <div className="flex justify-between text-[11px] text-gray-400 mt-1">
        <span>{fmtAcao(dominioMinimo)}</span>
        <span>{fmtAcao(maximo)}</span>
      </div>
      {precoForaDaFaixa && (
        <p className="text-[11px] text-amber-600 mt-1">
          ⚠️ Preço atual ({fmtAcao(precoAtual)}) fora da faixa pessimista–otimista.
        </p>
      )}
      {valorLiquidacao != null && (
        <p className="text-[11px] text-purple-700 mt-1">
          🏚️ Piso de liquidação: {fmtAcao(valorLiquidacao)}
          {valorLiquidacao < 0 && " (patrimônio líquido negativo numa liquidação forçada)"}
        </p>
      )}
    </div>
  );
}

function Heatmap({ matriz, precoAtual }: { matriz: MatrizSensibilidade; precoAtual: number }) {
  const cor = (v: number | null) => {
    if (v == null) return "bg-gray-50 text-gray-300";
    if (precoAtual <= 0) return "bg-gray-50 text-gray-700";
    if (v > precoAtual) return "bg-green-50 text-green-700";
    return "bg-red-50 text-red-700";
  };

  return (
    <div className="overflow-x-auto">
      <table className="text-xs border-collapse w-full">
        <thead>
          <tr>
            <th className="p-1.5 text-gray-400 font-medium text-left">
              {LABEL_VARIAVEL[matriz.variavel_y]} \ {LABEL_VARIAVEL[matriz.variavel_x]}
            </th>
            {matriz.eixo_x.map((x, i) => (
              <th key={i} className="p-1.5 text-gray-500 font-semibold text-center whitespace-nowrap">
                {fmtPct(x)}
              </th>
            ))}
          </tr>
        </thead>
        <tbody>
          {matriz.matriz.map((linha, i) => (
            <tr key={i}>
              <td className="p-1.5 text-gray-500 font-semibold whitespace-nowrap">{fmtPct(matriz.eixo_y[i])}</td>
              {linha.map((v, j) => (
                <td key={j} className={`p-1.5 text-center rounded ${cor(v)}`}>
                  {v == null ? "—" : fmtAcao(v)}
                </td>
              ))}
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}

export default function CenariosSensibilidade({ ticker, precoAtual }: Props) {
  const [dados, setDados] = useState<CenariosSensibilidadeResult | null>(null);
  const [loading, setLoading] = useState(false);
  const [erro, setErro] = useState<string | null>(null);
  const [matrizSelecionada, setMatrizSelecionada] = useState<OpcaoMatriz>("wacc_x_g_perpetuo");
  // Valor de Liquidação (Fase 2) — busca própria, independente de
  // cenarios/sensibilidade: uma falha ou indisponibilidade aqui (ex:
  // ticker sem BPA mapeado na CVM) não pode derrubar o card de cenários,
  // só deixa de mostrar o marcador de piso na barra.
  const [liquidacao, setLiquidacao] = useState<ValorLiquidacaoResult | null>(null);

  useEffect(() => {
    if (!ticker) return;
    let cancelado = false;
    setLoading(true);
    setErro(null);
    setDados(null);
    setLiquidacao(null);

    axios
      .post<CenariosSensibilidadeResult>(`/api/valuation/${ticker}/cenarios`)
      .then((res) => {
        if (!cancelado) setDados(res.data);
      })
      .catch((err) => {
        if (!cancelado) {
          const detalhe = err?.response?.data?.detail;
          setErro(typeof detalhe === "string" ? detalhe : "Não foi possível calcular cenários e sensibilidade para este ticker.");
        }
      })
      .finally(() => {
        if (!cancelado) setLoading(false);
      });

    axios
      .get<ValorLiquidacaoResult>(`/api/valuation/${ticker}/liquidacao`)
      .then((res) => {
        if (!cancelado) setLiquidacao(res.data);
      })
      .catch(() => {
        /* piso de liquidação é informação suplementar — silencioso */
      });

    return () => {
      cancelado = true;
    };
  }, [ticker]);

  const valorLiquidacaoPorAcao =
    liquidacao?.disponivel && liquidacao.valor_liquidacao_por_acao != null ? liquidacao.valor_liquidacao_por_acao : null;

  if (loading) {
    return (
      <div className="border border-gray-200 rounded-xl p-5 mt-4 bg-white shadow-sm">
        <h3 className="font-bold text-gray-800 text-base mb-2">🎯 Cenários &amp; Sensibilidade</h3>
        <p className="text-sm text-gray-400">Calculando cenários e matriz de sensibilidade...</p>
      </div>
    );
  }

  if (erro) {
    return (
      <div className="border border-gray-200 rounded-xl p-5 mt-4 bg-white shadow-sm">
        <h3 className="font-bold text-gray-800 text-base mb-2">🎯 Cenários &amp; Sensibilidade</h3>
        <p className="text-sm text-gray-500 bg-gray-50 border border-gray-200 rounded-lg p-3">{erro}</p>
      </div>
    );
  }

  if (!dados) return null;

  const { cenarios, faixa, premissas_base, matrizes_sensibilidade } = dados;
  const matrizAtual = matrizes_sensibilidade[matrizSelecionada];

  return (
    <div className="border border-gray-200 rounded-xl p-5 mt-4 bg-white shadow-sm">
      <div className="mb-4">
        <h3 className="font-bold text-gray-800 text-base">🎯 Cenários &amp; Sensibilidade</h3>
        <p className="text-xs text-gray-500 mt-0.5">
          DCF principal (FCFF) recalculado sob premissas pessimistas e otimistas de WACC, g perpétuo, margem EBITDA e crescimento de receita.
        </p>
      </div>

      <div className="grid grid-cols-3 gap-2 mb-2">
        <div className="bg-red-50 rounded-lg p-3 text-center">
          <p className="text-xs text-gray-500">Pessimista</p>
          <p className="font-bold text-red-700">{fmtAcao(cenarios.pessimista)}</p>
        </div>
        <div className="bg-blue-50 rounded-lg p-3 text-center">
          <p className="text-xs text-gray-500">Base</p>
          <p className="font-bold text-blue-700">{fmtAcao(cenarios.base)}</p>
        </div>
        <div className="bg-green-50 rounded-lg p-3 text-center">
          <p className="text-xs text-gray-500">Otimista</p>
          <p className="font-bold text-green-700">{fmtAcao(cenarios.otimista)}</p>
        </div>
      </div>

      <FaixaValorBar
        minimo={faixa.minimo}
        base={cenarios.base}
        maximo={faixa.maximo}
        precoAtual={precoAtual}
        valorLiquidacao={valorLiquidacaoPorAcao}
      />

      {premissas_base && (
        <div className="grid grid-cols-4 gap-2 mb-4 bg-gray-50 rounded-lg p-3">
          <div className="text-center">
            <p className="text-[10px] text-gray-400">WACC</p>
            <p className="text-xs font-semibold text-gray-700">{fmtPct(premissas_base.wacc)}</p>
          </div>
          <div className="text-center">
            <p className="text-[10px] text-gray-400">g perpétuo</p>
            <p className="text-xs font-semibold text-gray-700">{fmtPct(premissas_base.g_perpetuo)}</p>
          </div>
          <div className="text-center">
            <p className="text-[10px] text-gray-400">Margem EBITDA</p>
            <p className="text-xs font-semibold text-gray-700">{fmtPct(premissas_base.margem_ebitda)}</p>
          </div>
          <div className="text-center">
            <p className="text-[10px] text-gray-400">Cresc. Receita</p>
            <p className="text-xs font-semibold text-gray-700">{fmtPct(premissas_base.crescimento_receita)}</p>
          </div>
        </div>
      )}

      <div className="mb-2 flex items-center justify-between flex-wrap gap-2">
        <p className="text-xs font-semibold text-gray-600 uppercase tracking-wide">Matriz de sensibilidade</p>
        <select
          value={matrizSelecionada}
          onChange={(e) => setMatrizSelecionada(e.target.value as OpcaoMatriz)}
          className="text-xs border border-gray-200 rounded-lg px-2 py-1 text-gray-600 bg-white"
        >
          {OPCOES_MATRIZ.map((opcao) => (
            <option key={opcao.key} value={opcao.key}>
              {opcao.label}
            </option>
          ))}
        </select>
      </div>

      {matrizAtual && <Heatmap matriz={matrizAtual} precoAtual={precoAtual} />}
      <p className="text-[11px] text-gray-400 mt-2">
        Células em cinza (—) representam combinações onde WACC ≤ g perpétuo — matematicamente inválidas para o modelo de Gordon Growth.
      </p>
    </div>
  );
}
