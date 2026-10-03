// frontend/src/components/BitacoraViewer.tsx
import React, { useState, useEffect } from 'react';
import {
  ShieldCheck,
  ShieldAlert,
  Hash,
  Copy,
  Check,
  ChevronDown,
  ChevronRight,
  RefreshCw,
  Search,
  Filter,
  Lock,
  Layers,
  Sparkles,
  User,
  Cpu,
} from 'lucide-react';
import { AlertaVista, BitacoraResponse, EntradaBitacora } from '../types';
import { getBitacora } from '../api/client';
import { formatFecha, formatHora } from '../utils/formatters';

interface Props {
  alertas: AlertaVista[];
  alertaSeleccionadaId?: string;
}

export const BitacoraViewer: React.FC<Props> = ({
  alertas,
  alertaSeleccionadaId,
}) => {
  const [alertaActivaId, setAlertaActivaId] = useState<string>(
    alertaSeleccionadaId || alertas[0]?.alerta.alerta_id || ''
  );
  const [bitacora, setBitacora] = useState<BitacoraResponse | null>(null);
  const [loading, setLoading] = useState(false);
  const [verificando, setVerificando] = useState(false);
  const [filaExpandida, setFilaExpandida] = useState<number | null>(null);
  const [copiadoHash, setCopiadoHash] = useState<string | null>(null);

  useEffect(() => {
    if (alertaSeleccionadaId) {
      setAlertaActivaId(alertaSeleccionadaId);
    }
  }, [alertaSeleccionadaId]);

  useEffect(() => {
    if (alertaActivaId) {
      cargarBitacora(alertaActivaId);
    }
  }, [alertaActivaId]);

  const cargarBitacora = async (id: string, verificar = true) => {
    try {
      setLoading(true);
      const data = await getBitacora(id, verificar);
      setBitacora(data);
    } catch (err) {
      console.error('Error cargando bitácora:', err);
    } finally {
      setLoading(false);
    }
  };

  const handleVerificarCadena = async () => {
    if (!alertaActivaId) return;
    try {
      setVerificando(true);
      const data = await getBitacora(alertaActivaId, true);
      setBitacora(data);
    } finally {
      setVerificando(false);
    }
  };

  const handleCopiar = (texto: string) => {
    navigator.clipboard.writeText(texto);
    setCopiadoHash(texto);
    setTimeout(() => setCopiadoHash(null), 2000);
  };

  const getActorBadge = (actor: string) => {
    if (actor.startsWith('usuario:')) {
      return (
        <span className="inline-flex items-center gap-1 text-[11px] font-semibold px-2 py-0.5 rounded-full bg-emerald-50 text-emerald-800 border border-emerald-200">
          <User className="w-3 h-3 text-emerald-600" />
          {actor.replace('usuario:', '')}
        </span>
      );
    }
    return (
      <span className="inline-flex items-center gap-1 text-[11px] font-semibold px-2 py-0.5 rounded-full bg-slate-100 text-slate-700 border border-slate-200">
        <Cpu className="w-3 h-3 text-slate-500" />
        {actor}
      </span>
    );
  };

  const getEventoBadge = (evento: string) => {
    switch (evento) {
      case 'alerta_creada':
        return (
          <span className="text-[11px] font-semibold text-slate-700 bg-slate-100 px-2 py-0.5 rounded-md border border-slate-200">
            Alerta Creada
          </span>
        );
      case 'analisis_completo':
        return (
          <span className="text-[11px] font-semibold text-blue-700 bg-blue-50 px-2 py-0.5 rounded-md border border-blue-200">
            Análisis Completo
          </span>
        );
      case 'propuesta_generada':
        return (
          <span className="text-[11px] font-semibold text-amber-700 bg-amber-50 px-2 py-0.5 rounded-md border border-amber-200">
            Propuesta Generada
          </span>
        );
      case 'decision_humana':
        return (
          <span className="text-[11px] font-semibold text-purple-700 bg-purple-50 px-2 py-0.5 rounded-md border border-purple-200">
            Decisión Humana
          </span>
        );
      case 'accion_ejecutada':
        return (
          <span className="text-[11px] font-semibold text-emerald-700 bg-emerald-50 px-2 py-0.5 rounded-md border border-emerald-200">
            Acción Ejecutada
          </span>
        );
      case 'guardrail_intervino':
        return (
          <span className="text-[11px] font-semibold text-rose-700 bg-rose-50 px-2 py-0.5 rounded-md border border-rose-200">
            Guardrail Intervino
          </span>
        );
      default:
        return (
          <span className="text-[11px] font-medium text-slate-600 bg-slate-100 px-2 py-0.5 rounded-md">
            {evento}
          </span>
        );
    }
  };

  return (
    <div className="space-y-6">
      {/* Header y Selector de Alerta */}
      <section className="bg-white rounded-3xl p-6 border border-slate-200/70 shadow-card flex flex-col md:flex-row md:items-center justify-between gap-4">
        <div>
          <div className="flex items-center gap-2">
            <span className="text-xs font-bold uppercase tracking-wider text-slate-400">
              Auditoría Criptográfica Inmutable
            </span>
            <span className="text-[10px] font-bold px-2 py-0.5 rounded-full bg-purple-50 text-purple-700 border border-purple-200">
              SHA-256 Linked List
            </span>
          </div>
          <h2 className="text-2xl font-bold tracking-tight text-slate-900 mt-1">
            Cadena de Bitácora Operacional
          </h2>
          <p className="text-xs text-slate-500 max-w-xl mt-0.5">
            Registro secuencial sellado criptográficamente. Cada transición de agente y decisión humana incorpora el hash del bloque previo, imposibilitando la alteración retroactiva.
          </p>
        </div>

        {/* Selector y botón de verificar */}
        <div className="flex items-center gap-3">
          <select
            value={alertaActivaId}
            onChange={(e) => setAlertaActivaId(e.target.value)}
            className="text-xs py-2 px-3 rounded-xl bg-slate-50 border border-slate-200 font-medium text-slate-800 cursor-pointer focus:outline-none focus:ring-2 focus:ring-slate-900/10"
          >
            {alertas.map((a) => (
              <option key={a.alerta.alerta_id} value={a.alerta.alerta_id}>
                {a.alerta.alerta_id} · {a.alerta.severidad.toUpperCase()} ({a.alerta.estado})
              </option>
            ))}
          </select>

          <button
            onClick={handleVerificarCadena}
            disabled={verificando || loading || !alertaActivaId}
            className="px-4 py-2 rounded-xl text-xs font-bold text-emerald-800 bg-emerald-100 hover:bg-emerald-200 border border-emerald-300 transition-all flex items-center gap-1.5 cursor-pointer disabled:opacity-50 shadow-xs"
          >
            <ShieldCheck className="w-4 h-4" />
            <span>{verificando ? 'Verificando...' : 'Verificar Cadena'}</span>
          </button>
        </div>
      </section>

      {/* Sello de Integridad de la Cadena */}
      {bitacora && (
        <div
          className={`p-4 rounded-2xl border flex items-center justify-between gap-4 transition-all ${
            bitacora.cadena_valida
              ? 'bg-emerald-50/80 border-emerald-200/80 text-emerald-950'
              : 'bg-rose-50 border-rose-200 text-rose-950'
          }`}
        >
          <div className="flex items-center gap-3">
            {bitacora.cadena_valida ? (
              <div className="w-10 h-10 rounded-xl bg-emerald-600 text-white flex items-center justify-center shrink-0 shadow-xs">
                <ShieldCheck className="w-6 h-6" />
              </div>
            ) : (
              <div className="w-10 h-10 rounded-xl bg-rose-600 text-white flex items-center justify-center shrink-0 shadow-xs">
                <ShieldAlert className="w-6 h-6" />
              </div>
            )}
            <div>
              <h4 className="text-sm font-bold">
                {bitacora.cadena_valida
                  ? 'Cadena Criptográfica Íntegra y Verificada'
                  : 'ALERTA: Manipulación o Incoherencia Detectada en la Cadena'}
              </h4>
              <p className="text-xs opacity-80">
                {bitacora.cadena_valida
                  ? `Se verificaron matemáticamente ${bitacora.total_entradas} bloques enlazados sin saltos ni alteraciones.`
                  : 'Los hashes calculados no coinciden con los registrados en la cadena.'}
              </p>
            </div>
          </div>

          <div className="text-right text-xs font-mono">
            <span className="font-bold">{bitacora.total_entradas}</span> eventos auditados
          </div>
        </div>
      )}

      {/* Tabla de Bitácora */}
      <div className="bg-white rounded-3xl border border-slate-200/70 shadow-card overflow-hidden">
        {loading ? (
          <div className="p-12 text-center text-xs text-slate-400">
            Cargando entradas de bitácora...
          </div>
        ) : !bitacora || bitacora.entradas.length === 0 ? (
          <div className="p-12 text-center text-xs text-slate-400">
            No hay entradas de bitácora registradas para esta alerta.
          </div>
        ) : (
          <div className="overflow-x-auto">
            <table className="w-full text-left text-xs">
              <thead className="bg-slate-50/70 border-b border-slate-200/70 text-slate-500 font-semibold uppercase tracking-wider text-[10px]">
                <tr>
                  <th className="py-3 px-4 w-12 text-center">Seq</th>
                  <th className="py-3 px-4">Evento</th>
                  <th className="py-3 px-4">Actor</th>
                  <th className="py-3 px-4">Fecha y Hora</th>
                  <th className="py-3 px-4">Hash SHA-256</th>
                  <th className="py-3 px-4 text-center">Detalle</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-slate-100">
                {bitacora.entradas.map((entrada) => {
                  const isExpanded = filaExpandida === entrada.seq;
                  return (
                    <React.Fragment key={entrada.seq}>
                      <tr className="hover:bg-slate-50/60 transition-colors">
                        <td className="py-3 px-4 text-center font-bold text-slate-700">
                          #{entrada.seq}
                        </td>
                        <td className="py-3 px-4">
                          {getEventoBadge(entrada.evento)}
                        </td>
                        <td className="py-3 px-4">
                          {getActorBadge(entrada.actor)}
                        </td>
                        <td className="py-3 px-4 text-slate-500 font-mono text-[11px]">
                          {formatFecha(entrada.ts)} {formatHora(entrada.ts)}
                        </td>
                        <td className="py-3 px-4">
                          <button
                            onClick={() => handleCopiar(entrada.hash)}
                            className="flex items-center gap-1 font-mono text-[11px] text-slate-600 bg-slate-100 hover:bg-slate-200 px-2 py-0.5 rounded transition-colors cursor-pointer"
                            title="Copiar hash SHA-256 completo"
                          >
                            <span>
                              {entrada.hash.substring(0, 10)}...{entrada.hash.substring(58)}
                            </span>
                            {copiadoHash === entrada.hash ? (
                              <Check className="w-3 h-3 text-emerald-600" />
                            ) : (
                              <Copy className="w-3 h-3 text-slate-400" />
                            )}
                          </button>
                        </td>
                        <td className="py-3 px-4 text-center">
                          <button
                            onClick={() =>
                              setFilaExpandida(isExpanded ? null : entrada.seq)
                            }
                            className="p-1 rounded-md text-slate-400 hover:text-slate-700 hover:bg-slate-100 transition-colors cursor-pointer"
                          >
                            {isExpanded ? (
                              <ChevronDown className="w-4 h-4" />
                            ) : (
                              <ChevronRight className="w-4 h-4" />
                            )}
                          </button>
                        </td>
                      </tr>

                      {/* Fila expandida con Payload */}
                      {isExpanded && (
                        <tr className="bg-slate-50/90">
                          <td colSpan={6} className="p-4">
                            <div className="space-y-2">
                              <div className="flex items-center justify-between text-[11px] text-slate-500 font-mono">
                                <span>
                                  Hash Previo (hash_prev):{' '}
                                  <strong className="text-slate-700">
                                    {entrada.hash_prev}
                                  </strong>
                                </span>
                                <span>Schema v{entrada.schema_version}</span>
                              </div>
                              <pre className="p-3 bg-slate-900 text-slate-200 rounded-xl font-mono text-[11px] overflow-x-auto border border-slate-800">
                                {JSON.stringify(entrada.payload, null, 2)}
                              </pre>
                            </div>
                          </td>
                        </tr>
                      )}
                    </React.Fragment>
                  );
                })}
              </tbody>
            </table>
          </div>
        )}
      </div>
    </div>
  );
};
