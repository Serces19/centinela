// frontend/src/components/DecisionModal.tsx
import React, { useMemo, useState } from 'react';
import { AlertTriangle, Check, CheckCircle2, Edit3, FileCheck, ListTodo, Loader2, Mail, ShieldCheck, ShoppingCart, X, XCircle } from 'lucide-react';
import { AlertaVista, Borrador, DecisionRequest, ParametrosAccion, Persona, ResultadoEjecucion } from '../types';
import { formatCOP } from '../utils/formatters';
import { TextoConCifras } from '../utils/texto';
import { ApiError } from '../api/client';

interface Props {
  alertaVista: AlertaVista;
  modo: 'aprobar' | 'editar' | 'rechazar';
  personaActiva: Persona;
  onClose: () => void;
  onSubmitDecision: (alertaId: string, request: DecisionRequest, versionPrevia?: number) => Promise<{ resultado: ResultadoEjecucion }>;
}

const Opciones: React.FC<{ valor: string; opciones: [string, string][]; onChange: (v: string) => void; etiqueta: string }> = ({ valor, opciones, onChange, etiqueta }) => (
  <div className="space-y-2 p-4 bg-slate-50 rounded-2xl border border-slate-200/70">
    <label className="text-xs font-bold text-slate-700 block">{etiqueta}</label>
    <select value={valor} onChange={(e) => onChange(e.target.value)} className="w-full text-xs p-2.5 rounded-xl bg-white border border-slate-200 font-medium text-slate-800">
      {opciones.map(([v, t]) => <option key={v} value={v}>{t}</option>)}
    </select>
  </div>
);

const IconoBorrador: React.FC<{ tipo: string }> = ({ tipo }) =>
  tipo === 'correo' ? <Mail className="w-4 h-4 text-blue-600" /> : tipo === 'tarea' ? <ListTodo className="w-4 h-4 text-amber-600" /> : tipo === 'orden_compra' ? <ShoppingCart className="w-4 h-4 text-purple-600" /> : <FileCheck className="w-4 h-4 text-emerald-600" />;

export const DecisionModal: React.FC<Props> = ({ alertaVista, modo, personaActiva, onClose, onSubmitDecision }) => {
  const { alerta, propuesta } = alertaVista;
  const acciones = propuesta?.acciones ?? [];
  const cifras = propuesta?.cifras ?? [];

  // Por defecto solo la acción más recomendada: las demás suelen ser alternativas entre sí.
  const [elegidas, setElegidas] = useState<string[]>(acciones[0] ? [acciones[0].accion_id] : []);
  const [editando, setEditando] = useState<string | undefined>(acciones[0]?.accion_id);
  const [params, setParams] = useState<Record<string, ParametrosAccion>>(() =>
    Object.fromEntries(acciones.map((a) => [a.accion_id, JSON.parse(JSON.stringify(a.parametros)) as ParametrosAccion]))
  );
  const [motivo, setMotivo] = useState('');
  const [cargando, setCargando] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [resultado, setResultado] = useState<ResultadoEjecucion | null>(null);

  const alternar = (id: string) => setElegidas((p) => (p.includes(id) ? p.filter((x) => x !== id) : [...p, id]));
  const accionEditada = acciones.find((a) => a.accion_id === editando);
  const pEdit = editando ? params[editando] : undefined;
  const cambiar = (cambio: Partial<ParametrosAccion>) => editando && pEdit && setParams((p) => ({ ...p, [editando]: { ...pEdit, ...cambio } as ParametrosAccion }));
  const totalElegido = useMemo(() => acciones.filter((a) => elegidas.includes(a.accion_id)).reduce((s, a) => s + a.impacto.valor_cop, 0), [acciones, elegidas]);

  const enviar = async () => {
    setError(null);
    if (modo !== 'rechazar' && elegidas.length === 0) return setError('Elige al menos una acción.');
    if (modo === 'rechazar' && motivo.trim().length < 10) return setError('El motivo del rechazo debe tener al menos 10 caracteres.');
    const solicitud: DecisionRequest =
      modo === 'rechazar'
        ? { decision: 'rechazar', accion_ids: acciones.map((a) => a.accion_id), motivo: motivo.trim(), decidido_por: personaActiva.id }
        : modo === 'editar'
        ? { decision: 'editar', accion_ids: elegidas, ediciones: Object.fromEntries(elegidas.map((id) => [id, params[id]])), decidido_por: personaActiva.id }
        : { decision: 'aprobar', accion_ids: elegidas, decidido_por: personaActiva.id };
    try {
      setCargando(true);
      setResultado((await onSubmitDecision(alerta.alerta_id, solicitud, alerta.version)).resultado);
    } catch (e) {
      const err = e as ApiError;
      setError(err.status === 409 ? 'La alerta cambió mientras decidías o ya no está lista para decidir. Cierra y vuelve a abrirla.' : err.message);
    } finally {
      setCargando(false);
    }
  };

  const titulo = modo === 'aprobar' ? 'Aprobar acciones' : modo === 'editar' ? 'Editar y aprobar' : 'Rechazar la propuesta';

  return (
    <div role="dialog" aria-modal="true" aria-label={titulo} className="fixed inset-0 z-[60] flex items-center justify-center p-4 bg-slate-900/40 backdrop-blur-xs">
      <div className="bg-white/95 backdrop-blur-xl rounded-4xl shadow-modal border border-white w-full max-w-2xl max-h-[92vh] flex flex-col overflow-hidden">
        <div className="px-6 py-4 border-b border-slate-100 flex items-center justify-between bg-slate-50/50">
          <div className="flex items-center gap-2">
            <span className={`p-1 rounded-lg ${modo === 'aprobar' ? 'bg-emerald-100 text-emerald-800' : modo === 'editar' ? 'bg-amber-100 text-amber-800' : 'bg-rose-100 text-rose-800'}`}>
              {modo === 'aprobar' ? <Check className="w-4 h-4" /> : modo === 'editar' ? <Edit3 className="w-4 h-4" /> : <XCircle className="w-4 h-4" />}
            </span>
            <h3 className="text-sm font-bold text-slate-900">{titulo}</h3>
          </div>
          <button onClick={onClose} aria-label="Cerrar" className="p-1.5 rounded-xl text-slate-400 hover:text-slate-700 hover:bg-slate-200/60 cursor-pointer"><X className="w-5 h-5" /></button>
        </div>

        <div className="p-6 space-y-5 overflow-y-auto">
          <div className="flex items-center justify-between p-3 rounded-2xl bg-slate-50 border border-slate-200/60 text-xs">
            <span className="text-slate-500 font-medium">La decisión queda registrada a nombre de</span>
            <span className="flex items-center gap-2 font-semibold text-slate-800"><span className="text-base">{personaActiva.avatar}</span>{personaActiva.nombre} <span className="text-slate-400 font-normal">({personaActiva.cargo})</span></span>
          </div>

          {resultado ? (
            <div className="space-y-4">
              <div className="p-4 rounded-2xl bg-emerald-50 border border-emerald-200 text-center space-y-1">
                <CheckCircle2 className="w-8 h-8 text-emerald-600 mx-auto" />
                <h4 className="text-sm font-bold text-emerald-900">{modo === 'rechazar' ? 'Rechazo registrado' : 'Decisión ejecutada'}</h4>
                <p className="text-xs text-emerald-700">
                  {modo === 'rechazar'
                    ? 'El motivo quedó guardado y Centinela lo tendrá en cuenta en las próximas propuestas de este tipo.'
                    : 'El Ejecutor preparó borradores en un entorno seguro (nada salió a sistemas reales) y la bitácora quedó sellada.'}
                </p>
              </div>
              {resultado.borradores.length > 0 && (
                <div className="space-y-2 max-h-56 overflow-y-auto">
                  {resultado.borradores.map((b: Borrador) => (
                    <div key={b.artefacto_id} className="p-3 rounded-xl bg-slate-50 border border-slate-200/70 text-xs space-y-1.5">
                      <div className="flex items-center justify-between font-semibold text-slate-800">
                        <span className="flex items-center gap-2"><IconoBorrador tipo={b.tipo} /><span className="capitalize">{b.tipo.replace('_', ' ')}</span></span>
                        <span className="text-[10px] font-mono text-slate-400">{b.destino}</span>
                      </div>
                      <p className="text-slate-600 bg-white p-2 rounded-lg border border-slate-200/60 text-[11px] whitespace-pre-wrap">{b.contenido}</p>
                    </div>
                  ))}
                </div>
              )}
            </div>
          ) : modo === 'rechazar' ? (
            <div className="space-y-3">
              <label className="text-xs font-bold text-slate-700 block" htmlFor="motivo">Motivo del rechazo <span className="text-rose-600">*</span></label>
              <textarea id="motivo" rows={3} value={motivo} onChange={(e) => setMotivo(e.target.value)}
                placeholder="Explica por qué. Ej.: el proveedor ya aceptó revertir el alza, no conviene subir precios."
                className="w-full text-xs p-3 rounded-2xl bg-white border border-slate-200 placeholder:text-slate-400" />
              <div className="text-[11px] text-slate-400">{motivo.trim().length} / 10 caracteres mínimos</div>
              <div className="p-3 bg-rose-50/60 rounded-xl border border-rose-100 text-xs text-rose-900">
                Centinela guarda este motivo y lo usa en las próximas propuestas de la misma familia de causa: lo que rechazaste pasa al final de la lista y la propuesta explica el ajuste.
              </div>
            </div>
          ) : (
            <div className="space-y-4">
              <div className="space-y-2">
                <span className="text-xs font-bold uppercase tracking-wider text-slate-400 block">
                  {modo === 'editar' ? 'Acciones a editar y ejecutar' : 'Acciones a ejecutar'} (marca las que apruebas)
                </span>
                {acciones.map((a, i) => (
                  <label key={a.accion_id} className={`block p-3 rounded-2xl border cursor-pointer ${elegidas.includes(a.accion_id) ? 'bg-emerald-50/50 border-emerald-300' : 'bg-white border-slate-200'}`}>
                    <div className="flex items-start gap-3">
                      <input type="checkbox" checked={elegidas.includes(a.accion_id)} onChange={() => alternar(a.accion_id)} className="mt-1 accent-emerald-700" />
                      <div className="min-w-0 flex-1">
                        <div className="text-xs font-bold text-slate-900">{i + 1}. <TextoConCifras texto={a.titulo} cifras={cifras} /></div>
                        <p className="text-xs text-slate-600 mt-0.5"><TextoConCifras texto={a.razon} cifras={cifras} /></p>
                        <div className="text-[11px] text-slate-500 mt-1">{formatCOP(a.impacto.valor_cop)} {a.impacto.horizonte === 'mensual' ? 'al mes' : 'en total'} · {a.impacto.descripcion}</div>
                      </div>
                    </div>
                  </label>
                ))}
                {elegidas.length > 1 && <p className="text-[11px] text-amber-700">Ojo: las acciones suelen ser alternativas. Los montos no se suman, un mismo dinero puede aparecer en varias.</p>}
              </div>

              {modo === 'editar' && accionEditada && pEdit && (
                <div className="space-y-3">
                  {elegidas.length > 1 && (
                    <select value={editando} onChange={(e) => setEditando(e.target.value)} className="w-full text-xs p-2.5 rounded-xl bg-white border border-slate-200">
                      {acciones.filter((a) => elegidas.includes(a.accion_id)).map((a) => <option key={a.accion_id} value={a.accion_id}>Editar: {a.parametros.tipo.replace(/_/g, ' ')}</option>)}
                    </select>
                  )}
                  {pEdit.tipo === 'ajuste_precio' && (
                    <div className="space-y-3 p-4 bg-slate-50 rounded-2xl border border-slate-200/70">
                      <label className="text-xs font-bold text-slate-700 block" htmlFor="pct">Ajuste de precio</label>
                      <div className="flex items-center gap-3">
                        <input id="pct" type="range" min="0.5" max="30" step="0.5" value={pEdit.pct_ajuste} onChange={(e) => cambiar({ pct_ajuste: parseFloat(e.target.value) })} className="flex-1 accent-slate-900" />
                        <span className="text-sm font-bold text-slate-900 min-w-14 text-right">{pEdit.pct_ajuste} %</span>
                      </div>
                      <div className="text-[11px] text-slate-500">SKU: <strong className="font-mono">{pEdit.skus.join(', ')}</strong>. El impacto se recalcula al ejecutar con el nuevo porcentaje.</div>
                    </div>
                  )}
                  {pEdit.tipo === 'contacto_cartera' && <Opciones etiqueta="Nivel de gestión de cobro" valor={pEdit.nivel} onChange={(v) => cambiar({ nivel: v as never })} opciones={[['recordatorio', 'Recordatorio de pago'], ['llamada_acuerdo', 'Llamada y acuerdo de pago'], ['solo_contado', 'Pedidos solo de contado'], ['bloqueo_despachos', 'Bloqueo de despachos']]} />}
                  {pEdit.tipo === 'expeditar_oc' && <Opciones etiqueta="Vía para expeditar la orden" valor={pEdit.via} onChange={(v) => cambiar({ via: v as never })} opciones={[['contactar_proveedor', 'Contactar al proveedor hoy'], ['entrega_parcial', 'Pedir entrega parcial urgente'], ['proveedor_alterno', 'Evaluar proveedor alterno']]} />}
                  {pEdit.tipo === 'revision_descuentos' && <Opciones etiqueta="Medida sobre el vendedor" valor={pEdit.medida} onChange={(v) => cambiar({ medida: v as never })} opciones={[['revision_previa_cotizacion', 'Revisión previa de cotizaciones'], ['suspender_facultad_cotizar', 'Suspender la facultad de cotizar']]} />}
                  {pEdit.tipo === 'reactivar_cliente' && <Opciones etiqueta="Canal de reactivación" valor={pEdit.canal} onChange={(v) => cambiar({ canal: v as never })} opciones={[['visita', 'Visita del vendedor'], ['llamada', 'Llamada'], ['oferta', 'Oferta comercial']]} />}
                  {(pEdit.tipo === 'renegociar_proveedor' || pEdit.tipo === 'corregir_venta_bajo_costo') && <p className="text-xs text-slate-500 p-3 bg-slate-50 rounded-xl border border-slate-200/70">Esta acción no tiene parámetros editables: se ejecuta sobre los SKU indicados.</p>}
                </div>
              )}

              <p className="text-xs text-slate-500 flex items-start gap-1.5">
                <ShieldCheck className="w-4 h-4 text-emerald-600 shrink-0" />
                <span>Se crearán borradores en un entorno seguro (<code className="font-mono text-slate-700">sandbox://</code>); nada sale a sistemas reales. {elegidas.length > 0 && `Impacto de lo elegido: ${formatCOP(totalElegido)}.`}</span>
              </p>
            </div>
          )}

          {error && (
            <div role="alert" className="p-3 rounded-xl bg-rose-50 border border-rose-200 text-xs text-rose-700 flex items-start gap-2">
              <AlertTriangle className="w-4 h-4 shrink-0 mt-0.5" /><span>{error}</span>
            </div>
          )}
        </div>

        <div className="px-6 py-4 border-t border-slate-100 bg-slate-50/60 flex items-center justify-end gap-2">
          {resultado ? (
            <button onClick={onClose} className="px-4 py-2 rounded-xl text-xs font-bold text-white bg-slate-900 hover:bg-slate-800 cursor-pointer">Cerrar</button>
          ) : (
            <>
              <button onClick={onClose} disabled={cargando} className="px-3.5 py-2 rounded-xl text-xs font-medium text-slate-600 hover:bg-slate-200/60 cursor-pointer">Cancelar</button>
              <button onClick={enviar} disabled={cargando} className={`px-4 py-2 rounded-xl text-xs font-bold text-white flex items-center gap-1.5 cursor-pointer disabled:opacity-50 ${modo === 'aprobar' ? 'bg-emerald-600 hover:bg-emerald-700' : modo === 'editar' ? 'bg-amber-600 hover:bg-amber-700' : 'bg-rose-600 hover:bg-rose-700'}`}>
                {cargando && <Loader2 className="w-3.5 h-3.5 animate-spin" />}
                {modo === 'aprobar' ? 'Confirmar y aprobar' : modo === 'editar' ? 'Guardar y aprobar' : 'Rechazar propuesta'}
              </button>
            </>
          )}
        </div>
      </div>
    </div>
  );
};
