// ConcessaoSection.tsx
// Componente para exibir a análise de concessão no painel de valuation.
// Adicionar após a seção de DCF existente, condicionalmente quando
// resultado.concessao?.aplicavel === true.

import React, { useState } from "react";

interface FluxoProjetado {
  ano: number;
  fcf: number;
  fator_desconto: number;
  vp: number;
  fase: string;
}

interface ConcessaoData {
  aplicavel: boolean;
  preco_justo: number;
  anos_ate_vencimento: number;
  ano_vencimento_principal: number;
  ano_vencimento_secundario?: number;
  probabilidade_renovacao: number;
  vp_fluxos_pre_cliff: number;
  valor_terminal_esperado_pv: number;
  valor_terminal_renovacao: number;
  valor_terminal_liquidacao: number;
  impacto_cliff_vs_perpetuidade: number;
  fluxos_projetados: FluxoProjetado[];
  wacc_usado: number;
  notas: string[];
  motivo?: string;
}

interface Props {
  concessao: ConcessaoData;
  precoAtual: number;
  ticker: string;
  onProbRenovacaoChange?: (prob: number) => void; // callback para re-rodar no backend
}

const fmt = (v: number) =>
  v.toLocaleString("pt-BR", { style: "currency", currency: "BRL", minimumFractionDigits: 2 });

const pct = (v: number) => `${(v * 100).toFixed(0)}%`;

export default function ConcessaoSection({
  concessao,
  precoAtual,
  ticker,
  onProbRenovacaoChange,
}: Props) {
  const [probLocal, setProbLocal] = useState(concessao.probabilidade_renovacao);

  if (!concessao.aplicavel) {
    return (
      <div className="bg-yellow-50 border border-yellow-200 rounded-lg p-4 mt-4">
        <p className="text-sm text-yellow-700">
          ⚠️ DCF Concessão não aplicável: {concessao.motivo}
        </p>
      </div>
    );
  }

  const upside = ((concessao.preco_justo - precoAtual) / precoAtual) * 100;
  const isDescontada = upside > 0;
  const urgencia = concessao.anos_ate_vencimento <= 5 ? "alto" : concessao.anos_ate_vencimento <= 8 ? "médio" : "baixo";
  const urgenciaCor = urgencia === "alto" ? "red" : urgencia === "médio" ? "yellow" : "green";

  return (
    <div className="border border-gray-200 rounded-xl p-5 mt-4 bg-white shadow-sm">
      {/* Header */}
      <div className="flex items-center justify-between mb-4">
        <div>
          <h3 className="font-bold text-gray-800 text-base">
            ⚡ DCF — Concessão com Cliff
          </h3>
          <p className="text-xs text-gray-500 mt-0.5">
            Modelagem do vencimento contratual em {concessao.ano_vencimento_principal}
            {concessao.ano_vencimento_secundario ? ` / ${concessao.ano_vencimento_secundario}` : ""}
          </p>
        </div>
        <div className={`px-3 py-1 rounded-full text-xs font-semibold
          ${isDescontada ? "bg-green-100 text-green-700" : "bg-red-100 text-red-700"}`}>
          {isDescontada ? "✅ Descontada" : "❌ Cara"}
        </div>
      </div>

      {/* Preço justo */}
      <div className="grid grid-cols-3 gap-3 mb-4">
        <div className="bg-gray-50 rounded-lg p-3 text-center">
          <p className="text-xs text-gray-500">Preço Atual</p>
          <p className="font-bold text-gray-800">{fmt(precoAtual)}</p>
        </div>
        <div className={`rounded-lg p-3 text-center ${isDescontada ? "bg-green-50" : "bg-red-50"}`}>
          <p className="text-xs text-gray-500">Preço Justo (cliff)</p>
          <p className={`font-bold ${isDescontada ? "text-green-700" : "text-red-700"}`}>
            {fmt(concessao.preco_justo)}
          </p>
        </div>
        <div className={`rounded-lg p-3 text-center ${isDescontada ? "bg-green-50" : "bg-red-50"}`}>
          <p className="text-xs text-gray-500">Upside</p>
          <p className={`font-bold ${isDescontada ? "text-green-700" : "text-red-700"}`}>
            {upside > 0 ? "+" : ""}{upside.toFixed(1)}%
          </p>
        </div>
      </div>

      {/* Alerta de urgência */}
      <div className={`flex items-start gap-2 rounded-lg p-3 mb-4
        ${urgenciaCor === "red" ? "bg-red-50 border border-red-200"
          : urgenciaCor === "yellow" ? "bg-yellow-50 border border-yellow-200"
          : "bg-green-50 border border-green-200"}`}>
        <span className="text-lg">{urgenciaCor === "red" ? "🚨" : urgenciaCor === "yellow" ? "⚠️" : "ℹ️"}</span>
        <div>
          <p className={`text-sm font-semibold
            ${urgenciaCor === "red" ? "text-red-700" : urgenciaCor === "yellow" ? "text-yellow-700" : "text-green-700"}`}>
            Risco de concessão: {urgencia.toUpperCase()}
          </p>
          <p className="text-xs text-gray-600 mt-0.5">
            Concessão principal vence em{" "}
            <strong>{concessao.ano_vencimento_principal}</strong>{" "}
            ({concessao.anos_ate_vencimento} anos).
            Impacto vs. perpetuidade:{" "}
            <strong>{fmt(concessao.impacto_cliff_vs_perpetuidade)}/ação</strong>
          </p>
        </div>
      </div>

      {/* Breakdown do valor */}
      <div className="mb-4">
        <p className="text-xs font-semibold text-gray-600 uppercase tracking-wide mb-2">
          Composição do valor
        </p>
        <div className="space-y-2">
          <div className="flex justify-between text-sm">
            <span className="text-gray-600">VP fluxos pré-cliff</span>
            <span className="font-medium">{fmt(concessao.vp_fluxos_pre_cliff)} mi</span>
          </div>
          <div className="flex justify-between text-sm">
            <span className="text-gray-600">
              VT esperado (renovação {pct(concessao.probabilidade_renovacao)})
            </span>
            <span className="font-medium">{fmt(concessao.valor_terminal_esperado_pv)} mi</span>
          </div>
          <div className="border-t border-gray-100 pt-1 mt-1 flex justify-between text-sm">
            <span className="text-gray-500 text-xs">↳ se renovar</span>
            <span className="text-xs text-gray-500">{fmt(concessao.valor_terminal_renovacao)} mi</span>
          </div>
          <div className="flex justify-between text-sm">
            <span className="text-gray-500 text-xs">↳ se não renovar (liquidação)</span>
            <span className="text-xs text-gray-500">{fmt(concessao.valor_terminal_liquidacao)} mi</span>
          </div>
        </div>
      </div>

      {/* Slider de probabilidade de renovação */}
      <div className="mb-4 bg-blue-50 rounded-lg p-3">
        <div className="flex justify-between items-center mb-2">
          <p className="text-xs font-semibold text-blue-800">
            Ajustar probabilidade de renovação
          </p>
          <span className="text-sm font-bold text-blue-700">{(probLocal * 100).toFixed(0)}%</span>
        </div>
        <input
          type="range"
          min={0}
          max={1}
          step={0.05}
          value={probLocal}
          onChange={(e) => {
            const v = parseFloat(e.target.value);
            setProbLocal(v);
          }}
          onMouseUp={() => onProbRenovacaoChange?.(probLocal)}
          onTouchEnd={() => onProbRenovacaoChange?.(probLocal)}
          className="w-full h-2 rounded-lg appearance-none cursor-pointer bg-blue-200"
        />
        <div className="flex justify-between text-xs text-blue-400 mt-1">
          <span>0% (sem renovação)</span>
          <span>100% (certa)</span>
        </div>
        <p className="text-xs text-blue-600 mt-2">
          💡 Solte o slider para recalcular o preço justo.
        </p>
      </div>

      {/* Tabela de fluxos projetados */}
      {concessao.fluxos_projetados.length > 0 && (
        <details className="mb-4">
          <summary className="text-xs font-semibold text-gray-500 cursor-pointer hover:text-gray-700">
            📊 Ver fluxos projetados ano a ano ({concessao.fluxos_projetados.length} períodos)
          </summary>
          <div className="overflow-x-auto mt-2">
            <table className="w-full text-xs">
              <thead>
                <tr className="bg-gray-50">
                  <th className="text-left p-1 text-gray-500">Ano</th>
                  <th className="text-right p-1 text-gray-500">FCF (mi)</th>
                  <th className="text-right p-1 text-gray-500">VP (mi)</th>
                  <th className="text-right p-1 text-gray-500">Fase</th>
                </tr>
              </thead>
              <tbody>
                {concessao.fluxos_projetados.map((f) => (
                  <tr
                    key={f.ano}
                    className={`border-t border-gray-100
                      ${f.fase === "cliff" ? "bg-orange-50 font-semibold" : ""}`}
                  >
                    <td className="p-1">{f.ano}</td>
                    <td className="text-right p-1">{f.fcf.toFixed(1)}</td>
                    <td className="text-right p-1">{f.vp.toFixed(1)}</td>
                    <td className={`text-right p-1 ${f.fase === "cliff" ? "text-orange-600" : "text-gray-400"}`}>
                      {f.fase}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </details>
      )}

      {/* Notas */}
      {concessao.notas.length > 0 && (
        <div className="space-y-1">
          {concessao.notas.map((nota, i) => (
            <p key={i} className="text-xs text-gray-600 bg-gray-50 rounded px-2 py-1">
              {nota}
            </p>
          ))}
        </div>
      )}
    </div>
  );
}
