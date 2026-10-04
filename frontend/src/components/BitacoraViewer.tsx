// frontend/src/components/BitacoraViewer.tsx
import React, { useCallback, useEffect, useState } from 'react';
import { Loader2, ShieldAlert, ShieldCheck, X } from 'lucide-react';
import { AlertaVista, BitacoraResponse, EntradaBitacora } from '../types';
import { getBitacora } from '../api/client';
import { tituloAlerta } from '../utils/alertas';
import { formatFecha, formatHora } from '../utils/formatters';

interface Props {
  alertas: AlertaVista[];
  alertaSeleccionadaId?: string;
  onLimpiarAlerta: () => void;
}

const EVENTOS: Record<string, string> = {
  alerta_creada: 'Alerta detectada',
  analisis_completo: 'Análisis completo',
  propuesta_generada: 'Propuesta generada',
  decision_humana: 'Decisión humana',
  accion_ejecutada: 'Acción ejecutada (borrador)',
  alerta_reabierta: 'Alerta reabierta',
  guardrail_intervino: 'Guardrail intervino',
  error: 'Error',
};

const ACTORES = ['vigia', 'analista', 'estratega', 'ejecutor'];

function detalle(e: EntradaBitacora): string {
  const p = e.payload as Record<string, unknown>;
  if (e.evento === 'decision_humana') return `${String(p.decision)}${p.motivo ? ` — «${String(p.motivo)}»` : ''}`;
  if (e.evento === 'accion_ejecutada') return `${String(p.borradores_creados ?? p.borradores_generados ?? 0)} borrador(es) en sandbox`;
  if (e.evento === 'propuesta_generada') return `${String(p.num_acciones)} acción(es) propuestas`;
  if (e.evento === 'analisis_completo') return String(p.resumen ?? '').slice(0, 140);
  if (e.evento === 'alerta_creada') return String(p.huella_causa ?? '');
  return '';
}

export const BitacoraViewer: React.FC<Props> = ({ alertas, alertaSeleccionadaId, onLimpiarAlerta }) => {
  const [datos, setDatos] = useState<BitacoraResponse | null>(null);
  const [cargando, setCargando] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [actor, setActor] = useState('');
  const [evento, setEvento] = useState('');

  const cargar = useCallback(async () => {
    try {
      setCargando(true);
      setError(null);
      setDatos(await getBitacora({ alertaId: alertaSeleccionadaId, actor: actor || undefined, evento: evento || undefined, limite: 200 }));
    } catch (e) {
      setError((e as Error).message);
    } finally {
      setCargando(false);
    }
  }, [alertaSeleccionadaId, actor, evento]);

  useEffect(() => { cargar(); }, [cargar]);

  const titulo = (id: string) => {
    const a = alertas.find((x) => x.alerta.alerta_id === id);
    return a ? tituloAlerta(a) : id;
  };
  const entradas = (datos?.entradas ?? []).filter((e) => (!alertaSeleccionadaId || true) && (!actor || e.actor.includes(actor)));
  const esGeneral = !alertaSeleccionadaId;

  return (
    <div className="space-y-4">
      <section className="glass rounded-4xl p-5 flex flex-col md:flex-row md:items-center justify-between gap-3">
        <div>
          <span className="section-eyebrow">{esGeneral ? 'Auditoría general' : 'Auditoría de una alerta'}</span>
          <h2 className="text-lg font-semibold text-slate-900">{esGeneral ? 'Quién hizo qué y cuándo' : titulo(alertaSeleccionadaId!)}</h2>
          <p className="text-xs text-slate-500">Cada evento queda sellado con SHA-256 encadenado: si alguien altera una entrada, la cadena deja de verificar.</p>
        </div>
        <div className="flex flex-wrap items-center gap-2">
          {!esGeneral && (
            <>
              <span className={`text-xs font-bold px-3 py-1.5 rounded-full border flex items-center gap-1.5 ${datos?.cadena_valida ? 'bg-emerald-50 text-emerald-800 border-emerald-200' : 'bg-rose-50 text-rose-800 border-rose-200'}`}>
                {datos?.cadena_valida ? <ShieldCheck className="w-3.5 h-3.5" /> : <ShieldAlert className="w-3.5 h-3.5" />}
                {datos?.cadena_valida ? 'Cadena verificada' : 'Cadena alterada'}
              </span>
              <button onClick={onLimpiarAlerta} className="text-xs font-semibold px-3 py-1.5 rounded-full bg-white/80 border border-white hover:bg-white flex items-center gap-1 cursor-pointer"><X className="w-3 h-3" /> Ver todo</button>
            </>
          )}
          {esGeneral && (
            <>
              <select value={actor} onChange={(e) => setActor(e.target.value)} aria-label="Filtrar por actor" className="text-xs p-2 rounded-full bg-white/70 border border-white">
                <option value="">Todos los actores</option>
                {ACTORES.map((a) => <option key={a} value={a}>{a}</option>)}
                <option value="usuario:">usuarios</option>
              </select>
              <select value={evento} onChange={(e) => setEvento(e.target.value)} aria-label="Filtrar por evento" className="text-xs p-2 rounded-full bg-white/70 border border-white">
                <option value="">Todos los eventos</option>
                {Object.entries(EVENTOS).map(([k, v]) => <option key={k} value={k}>{v}</option>)}
              </select>
            </>
          )}
        </div>
      </section>

      <section className="glass rounded-4xl p-5">
        {cargando ? (
          <div className="py-8 text-center text-sm text-slate-500 flex items-center justify-center gap-2"><Loader2 className="w-4 h-4 animate-spin" /> Cargando…</div>
        ) : error ? (
          <div role="alert" className="py-6 text-center text-sm text-rose-700">{error}</div>
        ) : entradas.length === 0 ? (
          <p className="py-8 text-center text-sm text-slate-500">Todavía no hay eventos. Avanza el reloj simulado para que el Vigía detecte alertas.</p>
        ) : (
          <div className="overflow-x-auto">
            <table className="w-full text-xs">
              <thead>
                <tr className="text-left text-slate-400 uppercase tracking-wider text-[10px]">
                  <th className="py-2 pr-3 font-semibold">Cuándo</th>
                  <th className="py-2 pr-3 font-semibold">Evento</th>
                  <th className="py-2 pr-3 font-semibold">Quién</th>
                  {esGeneral && <th className="py-2 pr-3 font-semibold">Alerta</th>}
                  <th className="py-2 pr-3 font-semibold">Detalle</th>
                  <th className="py-2 font-semibold">Sello</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-white/70">
                {entradas.map((e) => (
                  <tr key={`${e.alerta_id}-${e.seq}`} className="align-top">
                    <td className="py-2.5 pr-3 whitespace-nowrap text-slate-500">{formatFecha(e.ts)} {formatHora(e.ts)}</td>
                    <td className="py-2.5 pr-3 font-semibold text-slate-800 whitespace-nowrap">{EVENTOS[e.evento] ?? e.evento}</td>
                    <td className="py-2.5 pr-3 text-slate-600 whitespace-nowrap">{e.actor}</td>
                    {esGeneral && <td className="py-2.5 pr-3 text-slate-600 max-w-[16rem] truncate" title={e.alerta_id}>{titulo(e.alerta_id)}</td>}
                    <td className="py-2.5 pr-3 text-slate-600 max-w-[22rem]">{detalle(e)}</td>
                    <td className="py-2.5 font-mono text-[10px] text-slate-400 whitespace-nowrap" title={`hash ${e.hash}\nanterior ${e.hash_prev}`}>#{e.seq} · {e.hash.slice(0, 8)}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </section>
    </div>
  );
};
