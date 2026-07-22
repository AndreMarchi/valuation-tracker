// ScorecardQualitativo.tsx
// Formulário de avaliação qualitativa (moat, gestão, concentração de
// clientes, risco regulatório, poder de precificação) — sliders 0-10,
// persistidos por ticker no localStorage (mesmo mecanismo já usado pela
// Watchlist, ver App.tsx::WATCHLIST_KEY — o projeto ainda não migrou
// dados de usuário pra armazenamento server-side). O ajuste resultante é
// calculado no backend (POST /api/valuation/{ticker}/scorecard) e exibido
// aqui como "Score ajustado" — a mesma Matriz de Consenso/Score de
// Atratividade já exibidos na tela, não um score paralelo desconectado.

import { useEffect, useState } from "react";
import axios from "axios";

interface Props {
  ticker: string;
  scoreBase: number;
}

interface Dimensoes {
  moat: number;
  gestao: number;
  concentracao_clientes: number;
  risco_regulatorio: number;
  poder_precificacao: number;
}

interface AjusteResult {
  score_base: number;
  media_dimensoes: number;
  ajuste_pontos: number;
  teto_ajuste_pontos: number;
  score_ajustado_qualitativo: number;
}

const DIMENSOES_LABELS: { key: keyof Dimensoes; label: string; ajuda: string }[] = [
  { key: "moat", label: "Moat (vantagem competitiva)", ajuda: "0 = commodity, fácil de replicar · 10 = monopólio/vantagem muito difícil de replicar" },
  { key: "gestao", label: "Gestão & governança", ajuda: "0 = histórico de destruição de valor · 10 = classe mundial" },
  { key: "concentracao_clientes", label: "Diversificação de clientes", ajuda: "0 = muito concentrada em poucos clientes · 10 = receita pulverizada" },
  { key: "risco_regulatorio", label: "Ausência de risco regulatório", ajuda: "0 = setor fortemente regulado/politizado · 10 = pouca exposição regulatória" },
  { key: "poder_precificacao", label: "Poder de precificação", ajuda: "0 = tomador de preço · 10 = forte poder de repasse, demanda inelástica" },
];

const DIMENSOES_DEFAULT: Dimensoes = {
  moat: 5,
  gestao: 5,
  concentracao_clientes: 5,
  risco_regulatorio: 5,
  poder_precificacao: 5,
};

const chaveStorage = (ticker: string) => `vt_scorecard_${ticker.toUpperCase()}`;

const carregarDimensoes = (ticker: string): Dimensoes => {
  try {
    const bruto = localStorage.getItem(chaveStorage(ticker));
    if (!bruto) return { ...DIMENSOES_DEFAULT };
    return { ...DIMENSOES_DEFAULT, ...JSON.parse(bruto) };
  } catch {
    return { ...DIMENSOES_DEFAULT };
  }
};

const salvarDimensoes = (ticker: string, dimensoes: Dimensoes) => {
  localStorage.setItem(chaveStorage(ticker), JSON.stringify(dimensoes));
};

const scoreColor = (s: number) => {
  if (s >= 8) return "text-green-700";
  if (s >= 6) return "text-blue-700";
  if (s >= 4) return "text-yellow-600";
  return "text-red-600";
};

export default function ScorecardQualitativoSection({ ticker, scoreBase }: Props) {
  const [dimensoes, setDimensoes] = useState<Dimensoes>(() => carregarDimensoes(ticker));
  const [ajuste, setAjuste] = useState<AjusteResult | null>(null);

  // Troca de ticker: recarrega os sliders salvos pra ESSE ticker (não os
  // do anterior) — cada ticker tem sua própria chave de localStorage.
  useEffect(() => {
    setDimensoes(carregarDimensoes(ticker));
  }, [ticker]);

  // Persiste no localStorage a cada mudança e busca o ajuste calculado no
  // backend — debounced (300ms) pra não disparar uma requisição a cada
  // pixel arrastado no slider.
  useEffect(() => {
    if (!ticker || scoreBase == null) return;
    salvarDimensoes(ticker, dimensoes);

    let cancelado = false;
    const timeout = setTimeout(() => {
      axios
        .post<AjusteResult>(`/api/valuation/${ticker}/scorecard`, { score_base: scoreBase, ...dimensoes })
        .then((res) => {
          if (!cancelado) setAjuste(res.data);
        })
        .catch(() => {
          /* falha no cálculo do ajuste não pode travar o resto da tela */
        });
    }, 300);

    return () => {
      cancelado = true;
      clearTimeout(timeout);
    };
  }, [ticker, scoreBase, dimensoes]);

  const atualizarDimensao = (chave: keyof Dimensoes, valor: number) => {
    setDimensoes((atual) => ({ ...atual, [chave]: valor }));
  };

  return (
    <div className="border border-gray-200 rounded-xl p-5 mt-4 bg-white shadow-sm">
      <div className="mb-4">
        <h3 className="font-bold text-gray-800 text-base">🧭 Scorecard Qualitativo</h3>
        <p className="text-xs text-gray-500 mt-0.5">
          Avaliação qualitativa manual — ajusta o Score de Atratividade/Matriz de Consenso acima em até{" "}
          {ajuste ? `±${ajuste.teto_ajuste_pontos.toFixed(1)}` : "±1.5"} ponto(s), nunca o suficiente pra dominar o
          resultado quantitativo.
        </p>
      </div>

      <div className="space-y-4 mb-4">
        {DIMENSOES_LABELS.map(({ key, label, ajuda }) => (
          <div key={key}>
            <div className="flex justify-between items-baseline mb-1">
              <label className="text-sm text-gray-700 font-medium">{label}</label>
              <span className="text-sm font-semibold text-gray-800">{dimensoes[key].toFixed(0)}/10</span>
            </div>
            <input
              type="range"
              min={0}
              max={10}
              step={1}
              value={dimensoes[key]}
              onChange={(e) => atualizarDimensao(key, Number(e.target.value))}
              className="w-full accent-blue-700"
            />
            <p className="text-[11px] text-gray-400 mt-0.5">{ajuda}</p>
          </div>
        ))}
      </div>

      {ajuste && (
        <div className="grid grid-cols-3 gap-2 bg-gray-50 rounded-lg p-3">
          <div className="text-center">
            <p className="text-[11px] text-gray-400">Score base</p>
            <p className={`text-lg font-bold ${scoreColor(ajuste.score_base)}`}>{ajuste.score_base.toFixed(1)}</p>
          </div>
          <div className="text-center">
            <p className="text-[11px] text-gray-400">Ajuste qualitativo</p>
            <p className={`text-lg font-bold ${ajuste.ajuste_pontos >= 0 ? "text-green-700" : "text-red-700"}`}>
              {ajuste.ajuste_pontos >= 0 ? "+" : ""}
              {ajuste.ajuste_pontos.toFixed(2)}
            </p>
          </div>
          <div className="text-center">
            <p className="text-[11px] text-gray-400">Score ajustado</p>
            <p className={`text-lg font-bold ${scoreColor(ajuste.score_ajustado_qualitativo)}`}>
              {ajuste.score_ajustado_qualitativo.toFixed(1)}
            </p>
          </div>
        </div>
      )}
    </div>
  );
}
