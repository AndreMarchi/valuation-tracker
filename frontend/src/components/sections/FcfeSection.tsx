// FcfeSection.tsx
// Card de Valuation de Equity via FCFE (Fluxo de Caixa Livre do Acionista),
// exibido ao lado do card de DCF via FCFF já existente. Dados vêm de
// dados.cvm_provider.buscar_inputs_fcfe_cvm() via valuation/fcfe_valuation.py
// — ver CONTEXT.md pra decisões de premissa (Ke do CAPM, crescimento/g_perpetuo
// iguais aos do DCF Duas Fases, pra a comparação lado a lado fazer sentido).

import type { Fcfe } from "../../types";

interface Props {
  fcfe: Fcfe | undefined;
  precoAtual: number;
}

// Valores de FCFE vêm em R$ absolutos (não pré-divididos por milhão, ao
// contrário dos gráficos trimestrais de saúde financeira) — formata em
// bi/mi conforme a magnitude.
const fmtGrande = (v: number | null | undefined): string => {
  if (v == null) return "—";
  const abs = Math.abs(v);
  const sinal = v < 0 ? "-" : "";
  if (abs >= 1_000_000_000) return `${sinal}R$ ${(abs / 1_000_000_000).toFixed(2)} bi`;
  if (abs >= 1_000_000) return `${sinal}R$ ${(abs / 1_000_000).toFixed(1)} mi`;
  return `${sinal}R$ ${abs.toFixed(0)}`;
};

const fmtAcao = (v: number | null | undefined): string =>
  v == null ? "—" : v.toLocaleString("pt-BR", { style: "currency", currency: "BRL", minimumFractionDigits: 2 });

const pct = (v: number | null | undefined): string => (v == null ? "—" : `${(v * 100).toFixed(1)}%`);

export default function FcfeSection({ fcfe, precoAtual }: Props) {
  if (!fcfe) return null;

  if (!fcfe.disponivel) {
    return (
      <div className="border border-gray-200 rounded-xl p-5 mt-4 bg-white shadow-sm">
        <h3 className="font-bold text-gray-800 text-base mb-2">💰 FCFE — Valuation de Equity</h3>
        <div className="bg-gray-50 border border-gray-200 rounded-lg p-3">
          <p className="text-sm text-gray-500">{fcfe.erro ?? "FCFE indisponível para este ticker."}</p>
          {fcfe.inputs_parciais && (
            <details className="mt-2">
              <summary className="text-xs font-semibold text-gray-400 cursor-pointer hover:text-gray-600">
                Ver quais campos já batiam
              </summary>
              <div className="mt-2 space-y-1">
                {Object.entries(fcfe.inputs_parciais).map(([campo, valor]) => (
                  <div key={campo} className="flex justify-between text-xs">
                    <span className="text-gray-500">{campo}</span>
                    <span className={valor == null ? "text-red-500" : "text-gray-700"}>
                      {valor == null ? "indisponível" : fmtGrande(valor)}
                    </span>
                  </div>
                ))}
              </div>
            </details>
          )}
        </div>
      </div>
    );
  }

  const { fcfe_ano_base, projecao, premissas } = fcfe;
  const valorPorAcao = projecao?.valor_justo_por_acao ?? null;
  const upside = valorPorAcao != null && precoAtual > 0 ? ((valorPorAcao - precoAtual) / precoAtual) * 100 : null;
  const isDescontada = upside != null && upside > 0;
  const valorNegativoOuAusente = valorPorAcao == null || valorPorAcao <= 0;

  return (
    <div className="border border-gray-200 rounded-xl p-5 mt-4 bg-white shadow-sm">
      <div className="flex items-center justify-between mb-4">
        <div>
          <h3 className="font-bold text-gray-800 text-base">💰 FCFE — Valuation de Equity</h3>
          <p className="text-xs text-gray-500 mt-0.5">
            Fluxo de Caixa Livre do Acionista, descontado a Ke (custo de capital próprio)
          </p>
        </div>
        {!valorNegativoOuAusente && (
          <div
            className={`px-3 py-1 rounded-full text-xs font-semibold ${
              isDescontada ? "bg-green-100 text-green-700" : "bg-red-100 text-red-700"
            }`}
          >
            {isDescontada ? "✅ Descontada" : "❌ Cara"}
          </div>
        )}
      </div>

      {fcfe_ano_base && (
        <div className="mb-4">
          <p className="text-xs font-semibold text-gray-600 uppercase tracking-wide mb-2">FCFE — ano base (TTM)</p>
          <div className="grid grid-cols-2 gap-2 mb-2">
            <div className="bg-gray-50 rounded-lg p-2.5 text-center">
              <p className="text-[11px] text-gray-400">Lucro Líquido</p>
              <p className="text-sm font-semibold text-gray-700">{fmtGrande(fcfe_ano_base.lucro_liquido)}</p>
            </div>
            <div className={`rounded-lg p-2.5 text-center ${fcfe_ano_base.fcfe >= 0 ? "bg-green-50" : "bg-red-50"}`}>
              <p className="text-[11px] text-gray-400">FCFE</p>
              <p className={`text-sm font-semibold ${fcfe_ano_base.fcfe >= 0 ? "text-green-700" : "text-red-700"}`}>
                {fmtGrande(fcfe_ano_base.fcfe)}
              </p>
            </div>
          </div>
          <div className="space-y-1">
            <div className="flex justify-between text-xs">
              <span className="text-gray-500">Reinvestimento líquido</span>
              <span className="text-gray-700">{fmtGrande(fcfe_ano_base.reinvestimento_liquido)}</span>
            </div>
            <div className="flex justify-between text-xs">
              <span className="text-gray-500">Δ Dívida líquida</span>
              <span className="text-gray-700">{fmtGrande(fcfe_ano_base.delta_divida_liquida)}</span>
            </div>
          </div>
          {fcfe_ano_base.alerta && (
            <p className="text-xs text-amber-700 bg-amber-50 border border-amber-200 rounded px-2 py-1.5 mt-2">
              ⚠️ {fcfe_ano_base.alerta}
            </p>
          )}
        </div>
      )}

      {projecao ? (
        <>
          <div className="grid grid-cols-3 gap-3 mb-4">
            <div className="bg-gray-50 rounded-lg p-3 text-center">
              <p className="text-xs text-gray-500">Preço Atual</p>
              <p className="font-bold text-gray-800">{fmtAcao(precoAtual)}</p>
            </div>
            <div className={`rounded-lg p-3 text-center ${isDescontada ? "bg-green-50" : "bg-red-50"}`}>
              <p className="text-xs text-gray-500">Valor Justo (FCFE)</p>
              <p className={`font-bold ${isDescontada ? "text-green-700" : "text-red-700"}`}>{fmtAcao(valorPorAcao)}</p>
            </div>
            <div className={`rounded-lg p-3 text-center ${isDescontada ? "bg-green-50" : "bg-red-50"}`}>
              <p className="text-xs text-gray-500">Upside</p>
              <p className={`font-bold ${isDescontada ? "text-green-700" : "text-red-700"}`}>
                {upside != null ? `${upside > 0 ? "+" : ""}${upside.toFixed(1)}%` : "—"}
              </p>
            </div>
          </div>

          {valorNegativoOuAusente && (
            <p className="text-xs text-amber-700 bg-amber-50 border border-amber-200 rounded-lg px-3 py-2 mb-4">
              ⚠️ Valor justo por ação negativo ou nulo — sinal de que o ano-base teve movimento de
              caixa atípico (ex: grande amortização líquida de dívida) que o modelo de 2 estágios
              projeta crescendo indefinidamente. Interprete com cautela, não como preço-alvo direto.
            </p>
          )}

          <div className="mb-4">
            <p className="text-xs font-semibold text-gray-600 uppercase tracking-wide mb-2">Composição do valor</p>
            <div className="space-y-2">
              <div className="flex justify-between text-sm">
                <span className="text-gray-600">VP dos FCFE explícitos ({premissas?.anos_explicitos ?? 5} anos)</span>
                <span className="font-medium">{fmtGrande(projecao.valor_presente_fcfe_explicito)}</span>
              </div>
              <div className="flex justify-between text-sm">
                <span className="text-gray-600">VP do valor terminal</span>
                <span className="font-medium">{fmtGrande(projecao.valor_presente_valor_terminal)}</span>
              </div>
              <div className="border-t border-gray-100 pt-1 mt-1 flex justify-between text-sm">
                <span className="text-gray-700 font-semibold">Valor justo do equity</span>
                <span className="font-semibold">{fmtGrande(projecao.valor_justo_equity)}</span>
              </div>
            </div>
          </div>

          {premissas && (
            <div className="grid grid-cols-3 gap-2 mb-2 bg-gray-50 rounded-lg p-3">
              <div className="text-center">
                <p className="text-[10px] text-gray-400">Ke (CAPM)</p>
                <p className="text-xs font-semibold text-gray-700">{pct(premissas.ke)}</p>
              </div>
              <div className="text-center">
                <p className="text-[10px] text-gray-400">Crescimento explícito</p>
                <p className="text-xs font-semibold text-gray-700">{pct(premissas.taxa_crescimento_explicito)}</p>
              </div>
              <div className="text-center">
                <p className="text-[10px] text-gray-400">g perpétuo</p>
                <p className="text-xs font-semibold text-gray-700">{pct(premissas.g_perpetuo)}</p>
              </div>
            </div>
          )}
          <p className="text-[11px] text-gray-400">
            Mesma premissa de crescimento do DCF Duas Fases — os dois valuations são comparáveis entre si.
          </p>
        </>
      ) : (
        <p className="text-xs text-amber-700 bg-amber-50 border border-amber-200 rounded-lg px-3 py-2">
          ⚠️ {fcfe.erro ?? "Não foi possível projetar o valor por ação."}
        </p>
      )}
    </div>
  );
}
