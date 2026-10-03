// frontend/src/components/DecisionModal.tsx
import React, { useState } from 'react';
import {
  X,
  Check,
  Edit3,
  XCircle,
  AlertTriangle,
  Loader2,
  Mail,
  ListTodo,
  ShoppingCart,
  ShieldCheck,
  CheckCircle2,
  FileCheck,
} from 'lucide-react';
import {
  AlertaVista,
  Borrador,
  DecisionRequest,
  ParametrosAccion,
  Persona,
  ResultadoEjecucion,
} from '../types';
import { formatCOP } from '../utils/formatters';

interface Props {
  alertaVista: AlertaVista;
  modo: 'aprobar' | 'editar' | 'rechazar';
  personaActiva: Persona;
  onClose: () => void;
  onSubmitDecision: (
    alertaId: string,
    request: DecisionRequest,
    versionPrevia?: number
  ) => Promise<{ resultado: ResultadoEjecucion }>;
  onExito: () => void;
}

export const DecisionModal: React.FC<Props> = ({
  alertaVista,
  modo,
  personaActiva,
  onClose,
  onSubmitDecision,
  onExito,
}) => {
  const { alerta, propuesta } = alertaVista;
  const primeraAccion = propuesta?.acciones[0];

  const [loading, setLoading] = useState(false);
  const [errorMsg, setErrorMsg] = useState<string | null>(null);
  const [resultadoEjecucion, setResultadoEjecucion] = useState<ResultadoEjecucion | null>(null);

  // Estado para rechazo
  const [motivoRechazo, setMotivoRechazo] = useState('');

  // Estado para edición contextual
  const [parametrosEditados, setParametrosEditados] = useState<ParametrosAccion | null>(() => {
    if (primeraAccion?.parametros) {
      return JSON.parse(JSON.stringify(primeraAccion.parametros));
    }
    return null;
  });

  const handleSubmit = async () => {
    try {
      setLoading(true);
      setErrorMsg(null);

      const accionIds = propuesta?.acciones.map((a) => a.accion_id) || [];

      let request: DecisionRequest;

      if (modo === 'aprobar') {
        request = {
          decision: 'aprobar',
          accion_ids: accionIds,
          decidido_por: personaActiva.id,
        };
      } else if (modo === 'rechazar') {
        if (motivoRechazo.trim().length < 10) {
          setErrorMsg('El motivo de rechazo debe tener al menos 10 caracteres.');
          setLoading(false);
          return;
        }
        request = {
          decision: 'rechazar',
          accion_ids: accionIds,
          motivo: motivoRechazo.trim(),
          decidido_por: personaActiva.id,
        };
      } else {
        // modo === 'editar'
        if (!primeraAccion || !parametrosEditados) {
          setErrorMsg('No hay parámetros de acción para editar.');
          setLoading(false);
          return;
        }
        request = {
          decision: 'editar',
          accion_ids: accionIds,
          ediciones: {
            [primeraAccion.accion_id]: parametrosEditados,
          },
          decidido_por: personaActiva.id,
        };
      }

      const res = await onSubmitDecision(alerta.alerta_id, request, alerta.version);
      setResultadoEjecucion(res.resultado);
      onExito();
    } catch (err: any) {
      if (err.status === 409) {
        setErrorMsg(
          'Conflicto de concurrencia: la alerta fue modificada por otro usuario o ya no está en estado propuesta.'
        );
      } else {
        setErrorMsg(err.message || 'Error al procesar la decisión.');
      }
    } finally {
      setLoading(false);
    }
  };

  const renderIconoBorrador = (tipo: string) => {
    switch (tipo) {
      case 'correo':
        return <Mail className="w-4 h-4 text-blue-600" />;
      case 'tarea':
        return <ListTodo className="w-4 h-4 text-amber-600" />;
      case 'orden_compra':
        return <ShoppingCart className="w-4 h-4 text-purple-600" />;
      default:
        return <FileCheck className="w-4 h-4 text-emerald-600" />;
    }
  };

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center p-4 bg-slate-900/40 backdrop-blur-xs animate-in fade-in duration-200">
      <div className="bg-white rounded-3xl shadow-2xl border border-slate-200/80 w-full max-w-2xl overflow-hidden animate-in zoom-in-95 duration-200">
        {/* Header */}
        <div className="px-6 py-4 border-b border-slate-100 flex items-center justify-between bg-slate-50/50">
          <div className="flex items-center gap-2">
            {modo === 'aprobar' && (
              <span className="p-1 rounded-lg bg-emerald-100 text-emerald-800">
                <Check className="w-4 h-4" />
              </span>
            )}
            {modo === 'editar' && (
              <span className="p-1 rounded-lg bg-amber-100 text-amber-800">
                <Edit3 className="w-4 h-4" />
              </span>
            )}
            {modo === 'rechazar' && (
              <span className="p-1 rounded-lg bg-rose-100 text-rose-800">
                <XCircle className="w-4 h-4" />
              </span>
            )}
            <h3 className="text-sm font-bold text-slate-900 capitalize">
              {modo === 'aprobar' && 'Aprobación Humana de Acción Operacional'}
              {modo === 'editar' && 'Ajustar Parámetros de la Propuesta'}
              {modo === 'rechazar' && 'Rechazar Propuesta con Retroalimentación'}
            </h3>
          </div>

          <button
            onClick={onClose}
            className="p-1.5 rounded-xl text-slate-400 hover:text-slate-700 hover:bg-slate-200/60 transition-colors cursor-pointer"
          >
            <X className="w-5 h-5" />
          </button>
        </div>

        {/* Content */}
        <div className="p-6 space-y-5">
          {/* Identificación del Decisor */}
          <div className="flex items-center justify-between p-3 rounded-2xl bg-slate-50 border border-slate-200/60 text-xs">
            <span className="text-slate-500 font-medium">Decisión registrada por:</span>
            <div className="flex items-center gap-2 font-semibold text-slate-800">
              <span className="text-base">{personaActiva.avatar}</span>
              <span>{personaActiva.nombre}</span>
              <span className="text-slate-400 font-normal">({personaActiva.cargo})</span>
            </div>
          </div>

          {/* Estado de Éxito con Borradores */}
          {resultadoEjecucion ? (
            <div className="space-y-4 animate-in fade-in duration-300">
              <div className="p-4 rounded-2xl bg-emerald-50 border border-emerald-200 text-center space-y-1">
                <CheckCircle2 className="w-8 h-8 text-emerald-600 mx-auto" />
                <h4 className="text-sm font-bold text-emerald-900">
                  ¡Decisión Ejecutada Exitosamente!
                </h4>
                <p className="text-xs text-emerald-700">
                  El Ejecutor generó los artefactos en el Sandbox seguro y selló la bitácora inmutable.
                </p>
              </div>

              {resultadoEjecucion.borradores && resultadoEjecucion.borradores.length > 0 && (
                <div className="space-y-2">
                  <span className="text-xs font-bold text-slate-700 uppercase tracking-wider block">
                    Borradores Seguros Generados (Sandbox):
                  </span>
                  <div className="space-y-2 max-h-56 overflow-y-auto">
                    {resultadoEjecucion.borradores.map((b: Borrador) => (
                      <div
                        key={b.artefacto_id}
                        className="p-3 rounded-xl bg-slate-50 border border-slate-200/70 text-xs space-y-1.5"
                      >
                        <div className="flex items-center justify-between font-semibold text-slate-800">
                          <div className="flex items-center gap-2">
                            {renderIconoBorrador(b.tipo)}
                            <span className="capitalize">{b.tipo}</span>
                          </div>
                          <span className="text-[10px] font-mono text-slate-400 bg-white px-2 py-0.5 rounded border border-slate-200">
                            {b.destino}
                          </span>
                        </div>
                        <p className="text-slate-600 bg-white p-2 rounded-lg border border-slate-200/60 font-mono text-[11px] whitespace-pre-wrap">
                          {b.contenido}
                        </p>
                      </div>
                    ))}
                  </div>
                </div>
              )}
            </div>
          ) : (
            <>
              {/* VISTA SEGÚN EL MODO */}
              {modo === 'aprobar' && (
                <div className="space-y-3">
                  <div className="p-4 rounded-2xl bg-slate-50 border border-slate-200/70 space-y-2">
                    <span className="text-xs font-bold uppercase tracking-wider text-slate-400 block">
                      Acción a Ejecutar
                    </span>
                    <h4 className="text-sm font-bold text-slate-900">
                      {primeraAccion?.titulo || 'Acción Correctiva'}
                    </h4>
                    <p className="text-xs text-slate-600">{primeraAccion?.razon}</p>

                    {primeraAccion?.impacto && (
                      <div className="pt-2 flex items-center justify-between border-t border-slate-200/60 text-xs">
                        <span className="text-slate-500">Recuperación estimada:</span>
                        <span className="font-bold text-emerald-700">
                          {formatCOP(primeraAccion.impacto.valor_cop)}
                        </span>
                      </div>
                    )}
                  </div>

                  <p className="text-xs text-slate-500 flex items-center gap-1.5">
                    <ShieldCheck className="w-4 h-4 text-emerald-600 shrink-0" />
                    <span>
                      Se crearán borradores en sandbox (<code className="text-slate-700 font-mono">sandbox://...</code>) y se sellará la entrada en la bitácora inmutable.
                    </span>
                  </p>
                </div>
              )}

              {modo === 'editar' && parametrosEditados && (
                <div className="space-y-4">
                  <p className="text-xs text-slate-600">
                    Ajuste los valores de la acción antes de autorizar su ejecución.
                  </p>

                  {/* Formulario contextual según el tipo de acción */}
                  {parametrosEditados.tipo === 'ajuste_precio' && (
                    <div className="space-y-3 p-4 bg-slate-50 rounded-2xl border border-slate-200/70">
                      <div>
                        <label className="text-xs font-bold text-slate-700 block mb-1">
                          Porcentaje de Ajuste de Precio (%)
                        </label>
                        <div className="flex items-center gap-3">
                          <input
                            type="range"
                            min="1"
                            max="30"
                            step="0.5"
                            value={parametrosEditados.pct_ajuste}
                            onChange={(e) =>
                              setParametrosEditados({
                                ...parametrosEditados,
                                pct_ajuste: parseFloat(e.target.value),
                              })
                            }
                            className="flex-1 accent-slate-900 cursor-pointer"
                          />
                          <span className="text-sm font-bold text-slate-900 min-w-14 text-right">
                            {parametrosEditados.pct_ajuste}%
                          </span>
                        </div>
                      </div>

                      <div className="text-[11px] text-slate-500">
                        SKUs afectados: <strong className="font-mono">{parametrosEditados.skus.join(', ')}</strong>
                      </div>
                    </div>
                  )}

                  {parametrosEditados.tipo === 'contacto_cartera' && (
                    <div className="space-y-3 p-4 bg-slate-50 rounded-2xl border border-slate-200/70">
                      <label className="text-xs font-bold text-slate-700 block">
                        Nivel de Acción de Cobro
                      </label>
                      <select
                        value={parametrosEditados.nivel}
                        onChange={(e) =>
                          setParametrosEditados({
                            ...parametrosEditados,
                            nivel: e.target.value as any,
                          })
                        }
                        className="w-full text-xs p-2.5 rounded-xl bg-white border border-slate-200 font-medium text-slate-800"
                      >
                        <option value="recordatorio">Recordatorio Amigable (Correo)</option>
                        <option value="llamada_acuerdo">Llamada de Acuerdo Comercial</option>
                        <option value="solo_contado">Restringir Crédito a Solo Contado</option>
                        <option value="bloqueo_despachos">Bloqueo Preventivo de Despachos</option>
                      </select>
                    </div>
                  )}

                  {parametrosEditados.tipo === 'expeditar_oc' && (
                    <div className="space-y-3 p-4 bg-slate-50 rounded-2xl border border-slate-200/70">
                      <label className="text-xs font-bold text-slate-700 block">
                        Vía de Expedición de Orden de Compra
                      </label>
                      <select
                        value={parametrosEditados.via}
                        onChange={(e) =>
                          setParametrosEditados({
                            ...parametrosEditados,
                            via: e.target.value as any,
                          })
                        }
                        className="w-full text-xs p-2.5 rounded-xl bg-white border border-slate-200 font-medium text-slate-800"
                      >
                        <option value="contactar_proveedor">Contactar Proveedor Habitual</option>
                        <option value="proveedor_alterno">Buscar Proveedor Alternativo</option>
                        <option value="entrega_parcial">Solicitar Entrega Parcial Inmediata</option>
                      </select>
                    </div>
                  )}

                  {parametrosEditados.tipo === 'revision_descuentos' && (
                    <div className="space-y-3 p-4 bg-slate-50 rounded-2xl border border-slate-200/70">
                      <label className="text-xs font-bold text-slate-700 block">
                        Medida de Control de Descuento
                      </label>
                      <select
                        value={parametrosEditados.medida}
                        onChange={(e) =>
                          setParametrosEditados({
                            ...parametrosEditados,
                            medida: e.target.value as any,
                          })
                        }
                        className="w-full text-xs p-2.5 rounded-xl bg-white border border-slate-200 font-medium text-slate-800"
                      >
                        <option value="revision_previa_cotizacion">Revisión Previa de Cada Cotización</option>
                        <option value="suspender_facultad_cotizar">Suspender Temporalmente Facultad de Cotizar</option>
                      </select>
                    </div>
                  )}
                </div>
              )}

              {modo === 'rechazar' && (
                <div className="space-y-3">
                  <div>
                    <label className="text-xs font-bold text-slate-700 block mb-1">
                      Motivo del Rechazo <span className="text-rose-500">*</span>
                    </label>
                    <textarea
                      rows={3}
                      value={motivoRechazo}
                      onChange={(e) => setMotivoRechazo(e.target.value)}
                      placeholder="Explique el motivo del rechazo (mínimo 10 caracteres)... Ej: Ya se acordó plan de pagos verbal con el cliente."
                      className="w-full text-xs p-3 rounded-2xl bg-white border border-slate-200 focus:outline-none focus:ring-2 focus:ring-rose-500/20 focus:border-rose-400 placeholder:text-slate-400"
                    />
                    <div className="flex items-center justify-between text-[11px] mt-1 text-slate-400">
                      <span>{motivoRechazo.trim().length} / 10 caracteres mínimos</span>
                      {motivoRechazo.trim().length >= 10 ? (
                        <span className="text-emerald-600 font-medium">Válido</span>
                      ) : (
                        <span className="text-rose-500 font-medium">Requerido &ge; 10</span>
                      )}
                    </div>
                  </div>

                  <div className="p-3 bg-rose-50/50 rounded-xl border border-rose-100 text-xs text-rose-800">
                    💡 <strong>Aprendizaje por Rechazo:</strong> Este motivo se almacena en la bitácora inmutable y entrena las futuras recomendaciones del Estratega.
                  </div>
                </div>
              )}

              {errorMsg && (
                <div className="p-3 rounded-xl bg-rose-50 border border-rose-200 text-xs text-rose-700 flex items-start gap-2">
                  <AlertTriangle className="w-4 h-4 shrink-0 mt-0.5" />
                  <span>{errorMsg}</span>
                </div>
              )}
            </>
          )}
        </div>

        {/* Footer */}
        <div className="px-6 py-4 border-t border-slate-100 bg-slate-50/60 flex items-center justify-end gap-2">
          {resultadoEjecucion ? (
            <button
              onClick={onClose}
              className="px-4 py-2 rounded-xl text-xs font-bold text-white bg-slate-900 hover:bg-slate-800 transition-all cursor-pointer"
            >
              Cerrar
            </button>
          ) : (
            <>
              <button
                onClick={onClose}
                disabled={loading}
                className="px-3.5 py-2 rounded-xl text-xs font-medium text-slate-600 hover:bg-slate-200/60 transition-colors cursor-pointer"
              >
                Cancelar
              </button>

              <button
                onClick={handleSubmit}
                disabled={
                  loading ||
                  (modo === 'rechazar' && motivoRechazo.trim().length < 10)
                }
                className={`px-4 py-2 rounded-xl text-xs font-bold text-white transition-all shadow-xs flex items-center gap-1.5 cursor-pointer disabled:opacity-50 ${
                  modo === 'aprobar'
                    ? 'bg-emerald-600 hover:bg-emerald-700'
                    : modo === 'editar'
                    ? 'bg-amber-600 hover:bg-amber-700'
                    : 'bg-rose-600 hover:bg-rose-700'
                }`}
              >
                {loading && <Loader2 className="w-3.5 h-3.5 animate-spin" />}
                {modo === 'aprobar' && 'Confirmar y Aprobar'}
                {modo === 'editar' && 'Guardar y Aprobar Edición'}
                {modo === 'rechazar' && 'Rechazar Propuesta'}
              </button>
            </>
          )}
        </div>
      </div>
    </div>
  );
};
