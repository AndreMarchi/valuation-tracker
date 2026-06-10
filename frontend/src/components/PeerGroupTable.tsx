// frontend/src/components/PeerGroupTable.tsx
import React, { useEffect, useState } from 'react';

interface Concorrente {
  ticker: string;
  nome: string;
  preco_atual: number;
  pl: number;
  pvp: number;
  ev_ebitda: number;
  dividend_yield: number;
}

interface PeerGroupData {
  ticker_referencia: string;
  subsetor_identificado: string;
  total_concorrentes_encontrados: number;
  concorrentes: Concorrente[];
}

interface PeerGroupTableProps {
  ticker: string;
  precoAtualMestre: number;
  plMestre: number;
  pvpMestre: number;
}

export const PeerGroupTable: React.FC<PeerGroupTableProps> = ({ 
  ticker, 
  precoAtualMestre, 
  plMestre, 
  pvpMestre 
}) => {
  const [data, setData] = useState<PeerGroupData | null>(null);
  const [loading, setLoading] = useState<boolean>(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    setLoading(true);
    setError(null);
    
    fetch(`/api/valuation/setor/concorrentes/${ticker}`)
      .then((res) => {
        if (!res.ok) throw new Error('Não foi possível carregar os dados setoriais.');
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

  if (loading) return <div className="p-4 text-gray-400 text-sm animate-pulse">Buscando concorrentes operacionais na B3...</div>;
  if (error) return <div className="p-4 text-red-400 text-sm">Aviso: {error}</div>;
  if (!data || data.concorrentes.length === 0) return null;

  return (
    <div className="bg-gray-900 border border-gray-800 rounded-xl p-6 shadow-lg mt-6">
      <div className="flex flex-col md:flex-row justify-between items-start md:items-center mb-4 pb-4 border-b border-gray-800">
        <div>
          <h3 className="text-xl font-bold text-white flex items-center gap-2">
            👥 Análise de Pares de Mercado (Peer Group)
          </h3>
          <p className="text-gray-400 text-xs mt-0.5">
            Subsetor Identificado: <span className="text-indigo-400 font-semibold">{data.subsetor_identificado}</span>
          </p>
        </div>
        <span className="text-xs bg-indigo-950/50 text-indigo-300 border border-indigo-800/60 px-2.5 py-1 rounded-full mt-2 md:mt-0 font-medium">
          {data.total_concorrentes_encontrados} empresas no setor
        </span>
      </div>

      <div className="overflow-x-auto">
        <table className="w-full text-left text-sm text-gray-300">
          <thead className="text-xs uppercase bg-gray-950 text-gray-400 border-b border-gray-800">
            <tr>
              <th className="px-4 py-3 font-semibold">Ativo</th>
              <th className="px-4 py-3 font-semibold">Preço</th>
              <th className="px-4 py-3 font-semibold">P/L</th>
              <th className="px-4 py-3 font-semibold">P/VP</th>
              <th className="px-4 py-3 font-semibold">EV/EBITDA</th>
              <th className="px-4 py-3 font-semibold">DY (%)</th>
            </tr>
          </thead>
          <tbody className="divide-y divide-gray-800/50">
            {/* LINHA DE REFERÊNCIA: O ATIVO ATUAL DA SUA BUSCA MESTRE */}
            <tr className="bg-indigo-950/30 border-l-4 border-indigo-500 font-medium">
              <td className="px-4 py-3.5 text-white font-bold">{ticker} (Avaliando)</td>
              <td className="px-4 py-3.5 text-white">R$ {precoAtualMestre.toFixed(2)}</td>
              <td className="px-4 py-3.5 text-indigo-300">{plMestre > 0 ? `${plMestre.toFixed(2)}x` : '-'}</td>
              <td className="px-4 py-3.5 text-indigo-300">{pvpMestre > 0 ? `${pvpMestre.toFixed(2)}x` : '-'}</td>
              <td className="px-4 py-3.5 text-gray-500">Mestre</td>
              <td className="px-4 py-3.5 text-gray-500">Mestre</td>
            </tr>

            {/* LISTA DOS CONCORRENTES DIRETOS DEVOLVIDOS PELA API */}
            {data.concorrentes.map((concorrente) => (
              <tr key={concorrente.ticker} className="hover:bg-gray-850 transition-colors">
                <td className="px-4 py-3 font-semibold text-gray-200">
                  {concorrente.ticker}
                  <span className="block text-gray-500 font-normal text-xxs truncate max-w-[150px]">
                    {concorrente.nome}
                  </span>
                </td>
                <td className="px-4 py-3 text-gray-400">R$ {concorrente.preco_atual.toFixed(2)}</td>
                <td className={`px-4 py-3 font-medium ${concorrente.pl < plMestre && concorrente.pl > 0 ? 'text-emerald-400' : 'text-gray-400'}`}>
                  {concorrente.pl > 0 ? `${concorrente.pl.toFixed(2)}x` : '-'}
                </td>
                <td className={`px-4 py-3 font-medium ${concorrente.pvp < pvpMestre && concorrente.pvp > 0 ? 'text-emerald-400' : 'text-gray-400'}`}>
                  {concorrente.pvp > 0 ? `${concorrente.pvp.toFixed(2)}x` : '-'}
                </td>
                <td className="px-4 py-3 text-gray-400">
                  {concorrente.ev_ebitda > 0 ? `${concorrente.ev_ebitda.toFixed(2)}x` : '-'}
                </td>
                <td className="px-4 py-3 text-emerald-400 font-semibold">
                  {concorrente.dividend_yield > 0 ? `${concorrente.dividend_yield.toFixed(2)}%` : '0,00%'}
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </div>
  );
};