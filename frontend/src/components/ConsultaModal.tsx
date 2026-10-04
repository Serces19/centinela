// frontend/src/components/ConsultaModal.tsx
import React, { useEffect, useState } from 'react';
import { Loader2, X } from 'lucide-react';
import { ConsultaRegistrada } from '../types';
import { getConsulta } from '../api/client';

interface Props {
  consultaId: string;
  onClose: () => void;
}

/** Una consulta registrada: el SQL exacto, el corte, el resultado y su huella SHA-256. */
export const ConsultaModal: React.FC<Props> = ({ consultaId, onClose }) => {
  const [c, setC] = useState<ConsultaRegistrada | null>(null);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    getConsulta(consultaId).then(setC).catch((e) => setError((e as Error).message));
  }, [consultaId]);

  return (
    <div role="dialog" aria-modal="true" aria-label="Consulta registrada" className="fixed inset-0 z-[70] flex items-center justify-center p-4 bg-slate-900/50 backdrop-blur-xs">
      <div className="bg-slate-900 text-slate-200 rounded-3xl w-full max-w-3xl max-h-[88vh] overflow-hidden flex flex-col shadow-modal">
        <div className="px-5 py-3 flex items-center justify-between border-b border-slate-800">
          <div className="text-xs">
            <span className="font-mono text-emerald-300">{consultaId}</span>
            {c && <span className="text-slate-400"> · {c.vista} · corte {c.corte} · {c.filas} fila(s)</span>}
          </div>
          <button onClick={onClose} aria-label="Cerrar" className="p-1.5 rounded-lg text-slate-400 hover:text-white cursor-pointer"><X className="w-4 h-4" /></button>
        </div>
        <div className="p-5 overflow-y-auto space-y-3 text-xs">
          {!c && !error && <div className="flex items-center gap-2 text-slate-400"><Loader2 className="w-4 h-4 animate-spin" /> Cargando…</div>}
          {error && <div role="alert" className="text-rose-300">{error}</div>}
          {c && (
            <>
              <p className="text-slate-300">{c.descripcion || 'Consulta de solo lectura sobre la capa semántica.'}</p>
              <pre className="p-3 bg-slate-950 rounded-xl border border-slate-800 whitespace-pre-wrap font-mono text-[11px] text-slate-300">{c.sql_renderizado}</pre>
              <div className="overflow-x-auto rounded-lg border border-slate-800">
                <table className="w-full text-[11px]">
                  <thead className="bg-slate-800 text-slate-400"><tr>{c.columnas.map((col) => <th key={col} className="px-2 py-1 text-left font-medium whitespace-nowrap">{col}</th>)}</tr></thead>
                  <tbody>{c.filas_muestra.slice(0, 15).map((f, i) => <tr key={i}>{f.map((v, j) => <td key={j} className="px-2 py-1 whitespace-nowrap">{v === null ? '—' : String(v)}</td>)}</tr>)}</tbody>
                </table>
              </div>
              <div className="text-[10px] text-slate-500 font-mono">SHA-256 del resultado: {c.resultado_hash}</div>
            </>
          )}
        </div>
      </div>
    </div>
  );
};
