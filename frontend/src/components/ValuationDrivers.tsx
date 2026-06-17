import React from 'react';

interface ValuationDriversProps {
  drivers?: {
    positivos: string[];
    negativos: string[];
  };
}

export const ValuationDrivers: React.FC<ValuationDriversProps> = ({ drivers }) => {
  if (!drivers || (drivers.positivos.length === 0 && drivers.negativos.length === 0)) {
    return null;
  }

  return (
    <div className="mt-6 p-5 bg-white border border-gray-200 rounded-xl shadow-sm">
      <h3 className="text-sm font-bold tracking-wide text-gray-800 uppercase mb-4">
        ⚡ Drivers do Valuation
      </h3>
      
      <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
        
        {/* Coluna Positiva */}
        <div>
          <h4 className="text-xs font-semibold text-green-700 mb-3 border-b border-green-100 pb-1">
            Impactos Positivos
          </h4>
          <ul className="space-y-2">
            {drivers.positivos.length > 0 ? (
              drivers.positivos.map((item, index) => (
                <li key={index} className="flex items-start text-sm text-gray-700">
                  <span className="text-green-500 mr-2 font-bold">✓</span>
                  {item}
                </li>
              ))
            ) : (
              <li className="text-sm text-gray-400 italic">Nenhum driver de alta identificado.</li>
            )}
          </ul>
        </div>

        {/* Coluna Negativa */}
        <div>
          <h4 className="text-xs font-semibold text-red-700 mb-3 border-b border-red-100 pb-1">
            Impactos Negativos / Riscos
          </h4>
          <ul className="space-y-2">
            {drivers.negativos.length > 0 ? (
              drivers.negativos.map((item, index) => (
                <li key={index} className="flex items-start text-sm text-gray-700">
                  <span className="text-red-500 mr-2 font-bold">✗</span>
                  {item}
                </li>
              ))
            ) : (
              <li className="text-sm text-gray-400 italic">Nenhum alerta crítico identificado.</li>
            )}
          </ul>
        </div>

      </div>
    </div>
  );
};