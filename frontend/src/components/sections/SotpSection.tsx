// SotpSection.tsx
// Card de valuation por Soma das Partes (SOTP) — breakdown por segmento +
// total comparado ao valor de mercado. Só aparece quando o ticker tem uma
// configuração de segmentos disponível (dados/sotp_config.json no backend
// ou body enviado à API) — mesmo padrão de renderização condicional do
// ConcessaoSection (silencioso quando não aplicável, não é erro).

import { useEffect, useState } from "react";
import axios from "axios";
import type { SotpResult } from "../../types";

interface Props {
  ticker: string;
  precoAtual: number;
}

const fmtGrande = (v: number | null | undefined): string => {
  if (v == null) return "—";
  const abs = Math.abs(v);
  const sinal = v < 0 ? "-" : "";
  if (abs >= 1_000) return `${sinal}R$ ${(abs / 1_000).toFixed(2)} bi`;
  return `${sinal}R$ ${abs.toFixed(1)} mi`;
};

const fmtAcao = (v: number | null | undefined): string =>
  v == null ? "—" : v.toLocaleString("pt-BR", { style: "currency", currency: "BRL", minimumFractionDigits: 2 });

const CORES_SEGMENTO = ["bg-blue-500", "bg-emerald-500", "bg-amber-500", "bg-purple-500", "bg-rose-500", "bg-cyan-500"];

export default function SotpSection({ ticker, precoAtual }: Props) {
  const [sotp, setSotp] = useState<SotpResult | null>(null);

  useEffect(() => {
    if (!ticker) return;
    let cancelado = false;
    setSotp(null);

    axios
      .post<SotpResult>(`/api/valuation/${ticker}/sotp`)
      .then((res) => {
        if (!cancelado) setSotp(res.data);
      })
      .catch(() => {
        /* sem configuração de SOTP pra esse ticker — não é erro visível ao usuário */
      });

    return () => {
      cancelado = true;
    };
  }, [ticker]);

  if (!sotp?.disponivel || !sotp.segmentos) return null;

  const segmentosValidos = sotp.segmentos.filter((s) => s.ev != null);
  const evTotal = sotp.ev_consolidado_bruto ?? 0;
  const precoJusto = sotp.preco_justo_por_acao ?? null;
  const upside = precoJusto != null && precoAtual > 0 ? ((precoJusto - precoAtual) / precoAtual) * 100 : null;
  const isDescontada = upside != null && upside > 0;

  return (
    <div className="border border-gray-200 rounded-xl p-5 mt-4 bg-white shadow-sm">
      <div className="mb-4">
        <h3 className="font-bold text-gray-800 text-base">🧩 SOTP — Soma das Partes</h3>
        <p className="text-xs text-gray-500 mt-0.5">
          Valuation por segmento — cada unidade de negócio avaliada separadamente e somada, com dívida
          líquida consolidada e desconto de holding aplicados uma única vez no final.
        </p>
      </div>

      {/* Breakdown visual: barra empilhada proporcional ao EV de cada segmento */}
      {evTotal > 0 && (
        <div className="mb-3">
          <div className="flex h-4 rounded-full overflow-hidden">
            {segmentosValidos.map((s, i) => (
              <div
                key={s.nome}
                className={CORES_SEGMENTO[i % CORES_SEGMENTO.length]}
                style={{ width: `${((s.ev ?? 0) / evTotal) * 100}%` }}
                title={`${s.nome}: ${fmtGrande(s.ev)}`}
              />
            ))}
          </div>
        </div>
      )}

      <div className="overflow-x-auto mb-4">
        <table className="text-xs w-full border-collapse">
          <thead>
            <tr className="text-gray-400">
              <th className="p-1.5 text-left font-medium">Segmento</th>
              <th className="p-1.5 text-left font-medium">Método</th>
              <th className="p-1.5 text-right font-medium">Enterprise Value</th>
            </tr>
          </thead>
          <tbody>
            {sotp.segmentos.map((s, i) => (
              <tr key={s.nome} className="border-t border-gray-100">
                <td className="p-1.5 text-gray-700 flex items-center gap-1.5">
                  {s.ev != null && (
                    <span className={`inline-block w-2 h-2 rounded-full ${CORES_SEGMENTO[i % CORES_SEGMENTO.length]}`} />
                  )}
                  {s.nome}
                </td>
                <td className="p-1.5 text-gray-500 uppercase">{s.metodo}</td>
                <td className="p-1.5 text-right font-medium text-gray-700">
                  {s.ev != null ? fmtGrande(s.ev) : <span className="text-amber-600">{s.erro ?? "indisponível"}</span>}
                </td>
              </tr>
            ))}
            <tr className="border-t border-gray-200 font-semibold">
              <td className="p-1.5 text-gray-800" colSpan={2}>EV Consolidado</td>
              <td className="p-1.5 text-right text-gray-800">{fmtGrande(sotp.ev_consolidado_bruto)}</td>
            </tr>
            <tr>
              <td className="p-1.5 text-gray-500" colSpan={2}>(–) Dívida Líquida Consolidada</td>
              <td className="p-1.5 text-right text-gray-500">{fmtGrande(sotp.divida_liquida_consolidada)}</td>
            </tr>
            <tr>
              <td className="p-1.5 text-gray-500" colSpan={2}>
                (–) Desconto de Holding ({((sotp.desconto_holding_pct ?? 0) * 100).toFixed(0)}%)
              </td>
              <td className="p-1.5 text-right text-gray-500">
                {fmtGrande((sotp.valor_equity_bruto ?? 0) - (sotp.valor_equity_pos_desconto ?? 0))}
              </td>
            </tr>
            <tr className="border-t border-gray-200 font-semibold">
              <td className="p-1.5 text-gray-800" colSpan={2}>Valor do Equity (pós-desconto)</td>
              <td className="p-1.5 text-right text-gray-800">{fmtGrande(sotp.valor_equity_pos_desconto)}</td>
            </tr>
          </tbody>
        </table>
      </div>

      <div className="grid grid-cols-3 gap-3">
        <div className="bg-gray-50 rounded-lg p-3 text-center">
          <p className="text-xs text-gray-500">Preço Atual</p>
          <p className="font-bold text-gray-800">{fmtAcao(precoAtual)}</p>
        </div>
        <div className={`rounded-lg p-3 text-center ${isDescontada ? "bg-green-50" : "bg-red-50"}`}>
          <p className="text-xs text-gray-500">Preço Justo (SOTP)</p>
          <p className={`font-bold ${isDescontada ? "text-green-700" : "text-red-700"}`}>{fmtAcao(precoJusto)}</p>
        </div>
        <div className={`rounded-lg p-3 text-center ${isDescontada ? "bg-green-50" : "bg-red-50"}`}>
          <p className="text-xs text-gray-500">Upside</p>
          <p className={`font-bold ${isDescontada ? "text-green-700" : "text-red-700"}`}>
            {upside != null ? `${upside > 0 ? "+" : ""}${upside.toFixed(1)}%` : "—"}
          </p>
        </div>
      </div>

      {sotp.segmentos_com_erro && sotp.segmentos_com_erro.length > 0 && (
        <p className="text-[11px] text-amber-600 mt-3">
          ⚠️ Segmento(s) sem dados suficientes, excluído(s) da soma: {sotp.segmentos_com_erro.join(", ")}
        </p>
      )}
    </div>
  );
}
