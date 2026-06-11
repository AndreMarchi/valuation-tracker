import React, { useEffect, useState } from 'react';

interface Concorrente {
  ticker: string;
  nome?: string;
  preco_atual: any;
  pl: any;
  pvp: any;
  ev_ebitda: any;
  dividend_yield: any;
}

interface PeerGroupData {
  ticker_referencia: string;
  subsetor_identificado: string;
  total_concorrentes_encontrados: number;
  concorrentes: Concorrente[];
}

interface PeerGroupTableProps {
  ticker: string;
  precoAtualMestre: any;
  plMestre: any;
  pvpMestre: any;
  evEbitdaMestre: any;
  dyMestre: any;
}

export const PeerGroupTable: React.FC<PeerGroupTableProps> = ({ 
  ticker, 
  precoAtualMestre, 
  plMestre, 
  pvpMestre,
  evEbitdaMestre,
  dyMestre
}) => {
  const [data, setData] = useState<PeerGroupData | null>(null);
  const [loading, setLoading] = useState<boolean>(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    if (!ticker) return;
    
    setLoading(true);
    setError(null);
    
    fetch(`/api/valuation/setor/concorrentes/${ticker}`)
      .then((res) => {
        if (!res.ok) throw new Error('Falha na comunicação com a API setorial.');
        return res.json();
      })
      .then((resData: PeerGroupData) => {
        setData(resData);
        setLoading(false);
      })
      .catch((err) => {
        setError(err.message);
        setLoading(false);
      });
  }, [ticker]);

  // PROTEÇÃO 1: Evita quebrar se 'concorrentes' vier undefined do backend
  if (loading) return <p className="text-xs text-gray-400 mt-2 animate-pulse">Ranqueando pares...</p>;
  if (error) return <p className="text-xs text-red-500 mt-2">Aviso: {error}</p>;
  if (!data || !Array.isArray(data.concorrentes) || data.concorrentes.length === 0) return null;

  // PROTEÇÃO 2: Converte qualquer lixo de dados em número seguro antes de formatar
  const renderMultiplo = (valorBruto: any, alvoMestreBruto: any) => {
    const v = Number(valorBruto);
    const alvo = Number(alvoMestreBruto);

    if (isNaN(v) || v === 0) return <span className="text-gray-400">—</span>;

    if (v < 0) return <span className="text-red-500 font-semibold">{v.toFixed(2)}x</span>;
    if (v < alvo && alvo > 0) return <span className="text-green-700 font-semibold">{v.toFixed(2)}x</span>;
    return <span className="text-gray-600 font-semibold">{v.toFixed(2)}x</span>;
  };

  // Garante a conversão dos dados do ativo alvo
  const precoMestreNum = Number(precoAtualMestre) || 0;
  const dyMestreNum = Number(dyMestre) || 0;

  return (
    <div className="mt-4 pt-4 border-t border-gray-100">
      <h3 className="text-xs font-semibold tracking-widest text-gray-400 uppercase mb-3">
        👥 Peer Group — Top Concorrentes Filtrados
      </h3>
      
      <p className="text-xs text-gray-500 mb-2">
        Segmento: <span className="font-semibold text-gray-700">{data.subsetor_identificado || "Geral"}</span>
      </p>

      <div className="overflow-x-auto rounded-lg border border-gray-200 bg-white shadow-sm">
        <table className="w-full text-left text-xs text-gray-600">
          <thead className="bg-gray-50 text-gray-500 font-semibold uppercase border-b border-gray-200">
            <tr>
              <th className="px-3 py-2">Ativo</th>
              <th className="px-3 py-2">Preço</th>
              <th className="px-3 py-2">P/L</th>
              <th className="px-3 py-2">P/VP</th>
              <th className="px-3 py-2">EV/EBITDA</th>
              <th className="px-3 py-2">DY</th>
            </tr>
          </thead>
          <tbody className="divide-y divide-gray-100">
            <tr className="bg-blue-50/60 font-semibold text-gray-900 border-l-4 border-blue-600">
              <td className="px-3 py-2.5 font-bold text-blue-900">{ticker} (Alvo)</td>
              <td className="px-3 py-2.5">R$ {precoMestreNum.toFixed(2)}</td>
              <td className="px-3 py-2.5">{renderMultiplo(plMestre, 0)}</td>
              <td className="px-3 py-2.5">{renderMultiplo(pvpMestre, 0)}</td>
              <td className="px-3 py-2.5">{renderMultiplo(evEbitdaMestre, 0)}</td>
              <td className="px-3 py-2.5 font-medium">
                {dyMestreNum > 0 
                  ? <span className="text-blue-700">{dyMestreNum.toFixed(2)}%</span> 
                  : <span className="text-gray-400">—</span>}
              </td>
            </tr>

            {data.concorrentes.map((c) => {
              const precoConcorrente = Number(c.preco_atual) || 0;
              const dyConcorrente = Number(c.dividend_yield) || 0;

              return (
                <tr key={c.ticker} className="hover:bg-gray-50/80 transition-colors">
                  <td className="px-3 py-2 font-bold text-gray-800">{c.ticker}</td>
                  <td className="px-3 py-2 text-gray-500">R$ {precoConcorrente.toFixed(2)}</td>
                  <td className="px-3 py-2">{renderMultiplo(c.pl, plMestre)}</td>
                  <td className="px-3 py-2">{renderMultiplo(c.pvp, pvpMestre)}</td>
                  <td className="px-3 py-2">{renderMultiplo(c.ev_ebitda, evEbitdaMestre)}</td>
                  <td className="px-3 py-2 font-medium">
                    {dyConcorrente > 0 
                      ? <span className="text-green-700">{dyConcorrente.toFixed(2)}%</span> 
                      : <span className="text-gray-400">—</span>}
                  </td>
                </tr>
              );
            })}
          </tbody>
        </table>
      </div>
    </div>
  );
};