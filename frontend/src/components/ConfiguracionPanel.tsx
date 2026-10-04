// frontend/src/components/ConfiguracionPanel.tsx
import React, { useCallback, useEffect, useMemo, useState } from 'react';
import { CheckCircle2, Loader2, Lock, Save } from 'lucide-react';
import { ConfigUmbral, ConfiguracionVigia, NivelAutonomia, Persona } from '../types';
import { getConfig, putConfig } from '../api/client';

interface Props {
  personaActiva: Persona;
  onCambio: () => void;
}

const KPI: Record<string, string> = {
  margen_pct: 'Margen',
  saldo_vencido: 'Cartera vencida',
  dias_pago_prom: 'Días de pago',
  cobertura_dias: 'Cobertura de inventario',
  descuento_en_exceso: 'Descuentos fuera de política',
  veces_intervalo_habitual: 'Intervalo de compra de clientes',
  venta_bajo_costo: 'Ventas bajo costo',
};

const ACCIONES: Record<string, string> = {
  ajuste_precio: 'Ajuste de precios',
  renegociar_proveedor: 'Renegociar con el proveedor',
  contacto_cartera: 'Gestión de cartera',
  expeditar_oc: 'Expeditar órdenes de compra',
  revision_descuentos: 'Control de descuentos',
  reactivar_cliente: 'Reactivar clientes',
  corregir_venta_bajo_costo: 'Corregir precios bajo costo',
};

const NIVELES: { id: NivelAutonomia; etiqueta: string; ayuda: string; habilitado: boolean }[] = [
  { id: 'informa', etiqueta: 'Informa', ayuda: 'Avisa pero no prepara ninguna acción al aprobar', habilitado: true },
  { id: 'propone', etiqueta: 'Propone', ayuda: 'Prepara el borrador y espera tu aprobación', habilitado: true },
  { id: 'ejecuta', etiqueta: 'Ejecuta', ayuda: 'Se habilita en producción, con historial de aciertos', habilitado: false },
];

export const ConfiguracionPanel: React.FC<Props> = ({ personaActiva, onCambio }) => {
  const [config, setConfig] = useState<ConfiguracionVigia | null>(null);
  const [valores, setValores] = useState<Record<string, string>>({});
  const [autonomia, setAutonomia] = useState<Record<string, NivelAutonomia>>({});
  const [guardando, setGuardando] = useState(false);
  const [mensaje, setMensaje] = useState<{ ok: boolean; texto: string } | null>(null);

  const cargar = useCallback(async () => {
    const c = await getConfig();
    setConfig(c);
    setValores(Object.fromEntries(c.umbrales.map((u) => [u.nombre, String(u.valor)])));
    setAutonomia(c.autonomia);
  }, []);

  useEffect(() => { cargar().catch((e) => setMensaje({ ok: false, texto: (e as Error).message })); }, [cargar]);

  const grupos = useMemo(() => {
    const g: Record<string, ConfigUmbral[]> = {};
    config?.umbrales.forEach((u) => (g[u.kpi] ||= []).push(u));
    return g;
  }, [config]);

  const cambios = useMemo(() => {
    const u: Record<string, number> = {};
    config?.umbrales.forEach((x) => {
      const n = Number(valores[x.nombre]);
      if (!Number.isNaN(n) && n !== x.valor) u[x.nombre] = n;
    });
    const a: Record<string, string> = {};
    Object.entries(autonomia).forEach(([k, v]) => { if (config && config.autonomia[k] !== v) a[k] = v; });
    return { umbrales: u, autonomia: a };
  }, [config, valores, autonomia]);

  const hayCambios = Object.keys(cambios.umbrales).length + Object.keys(cambios.autonomia).length > 0;

  const guardar = async (e: React.FormEvent) => {
    e.preventDefault();
    try {
      setGuardando(true);
      setMensaje(null);
      const nuevo = await putConfig({ ...cambios, actor: personaActiva.id });
      setConfig(nuevo);
      setValores(Object.fromEntries(nuevo.umbrales.map((u) => [u.nombre, String(u.valor)])));
      setAutonomia(nuevo.autonomia);
      setMensaje({ ok: true, texto: 'Guardado. El Vigía usa estos umbrales desde el siguiente cálculo.' });
      onCambio();
    } catch (err) {
      setMensaje({ ok: false, texto: (err as Error).message });
    } finally {
      setGuardando(false);
    }
  };

  if (!config) {
    return <div className="glass rounded-4xl p-10 text-center text-sm text-slate-500 flex items-center justify-center gap-2"><Loader2 className="w-4 h-4 animate-spin" /> Cargando la configuración…</div>;
  }

  return (
    <form onSubmit={guardar} className="space-y-6">
      <section className="glass rounded-4xl p-6">
        <span className="section-eyebrow">Gobernanza</span>
        <h2 className="text-xl font-semibold text-slate-900">Qué vigila Centinela y cuánta autonomía tiene</h2>
        <p className="text-xs text-slate-500 mt-1 max-w-2xl">Los valores de partida salen de las políticas de la empresa. Si cambias un umbral, el Vigía lo aplica de inmediato y las alertas se recalculan.</p>
      </section>

      <section className="glass rounded-4xl p-6 space-y-5">
        <h3 className="text-sm font-bold text-slate-900">1. Umbrales de alerta por indicador</h3>
        {Object.entries(grupos).map(([kpi, umbrales]) => (
          <fieldset key={kpi} className="space-y-3">
            <legend className="text-xs font-bold uppercase tracking-wider text-slate-500 mb-1">{KPI[kpi] ?? kpi}</legend>
            {umbrales.map((u) => {
              const cambiado = Number(valores[u.nombre]) !== u.valor;
              return (
                <div key={u.nombre} className="grid grid-cols-1 md:grid-cols-[1fr_auto] items-center gap-2 p-3 rounded-2xl bg-white/60 border border-white">
                  <label htmlFor={u.nombre} className="text-xs text-slate-800">
                    <span className="font-semibold">{u.etiqueta}</span>
                    <span className="block text-[11px] text-slate-400">{u.politica} · valor de política {u.defecto} {u.unidad}</span>
                  </label>
                  <div className="flex items-center gap-2">
                    <input
                      id={u.nombre} type="number" step="any" min={u.minimo} max={u.maximo} value={valores[u.nombre] ?? ''}
                      onChange={(e) => setValores((p) => ({ ...p, [u.nombre]: e.target.value }))}
                      className={`w-28 text-sm text-right p-2 rounded-xl border ${cambiado ? 'border-amber-400 bg-amber-50' : 'border-slate-200 bg-white'}`}
                    />
                    <span className="text-xs text-slate-500 w-14">{u.unidad}</span>
                    {cambiado && (
                      <button type="button" onClick={() => setValores((p) => ({ ...p, [u.nombre]: String(u.defecto) }))} className="text-[11px] text-slate-500 underline cursor-pointer">restablecer</button>
                    )}
                  </div>
                </div>
              );
            })}
          </fieldset>
        ))}
      </section>

      <section className="glass rounded-4xl p-6 space-y-4">
        <h3 className="text-sm font-bold text-slate-900">2. Nivel de autonomía por tipo de acción</h3>
        <p className="text-xs text-slate-500">En el MVP todo queda en «Propone»: ninguna acción se ejecuta sin aprobación humana. «Informa» sirve para tipos de acción que aún no quieres preparar.</p>
        <div className="space-y-2">
          {Object.entries(ACCIONES).map(([tipo, etiqueta]) => (
            <div key={tipo} className="flex flex-col sm:flex-row sm:items-center justify-between gap-2 p-3 rounded-2xl bg-white/60 border border-white">
              <span className="text-xs font-semibold text-slate-800">{etiqueta}</span>
              <div role="radiogroup" aria-label={`Autonomía: ${etiqueta}`} className="flex p-1 rounded-full bg-slate-100 text-xs font-semibold">
                {NIVELES.map((n) => (
                  <button
                    key={n.id} type="button" role="radio" aria-checked={autonomia[tipo] === n.id} disabled={!n.habilitado} title={n.ayuda}
                    onClick={() => setAutonomia((p) => ({ ...p, [tipo]: n.id }))}
                    className={`px-3.5 py-1.5 rounded-full flex items-center gap-1 ${autonomia[tipo] === n.id ? 'bg-slate-900 text-white' : 'text-slate-600'} ${n.habilitado ? 'cursor-pointer' : 'opacity-40 cursor-not-allowed'}`}
                  >
                    {!n.habilitado && <Lock className="w-3 h-3" />}{n.etiqueta}
                  </button>
                ))}
              </div>
            </div>
          ))}
        </div>
      </section>

      <div className="flex items-center justify-end gap-3">
        {mensaje && (
          <span role="status" className={`text-xs font-medium flex items-center gap-1.5 ${mensaje.ok ? 'text-emerald-700' : 'text-rose-700'}`}>
            {mensaje.ok && <CheckCircle2 className="w-4 h-4" />}{mensaje.texto}
          </span>
        )}
        <button type="submit" disabled={!hayCambios || guardando} className="px-5 py-2.5 rounded-full text-xs font-bold text-white bg-slate-900 hover:bg-slate-800 disabled:opacity-40 flex items-center gap-2 cursor-pointer">
          {guardando ? <Loader2 className="w-3.5 h-3.5 animate-spin" /> : <Save className="w-3.5 h-3.5" />} Guardar cambios
        </button>
      </div>
    </form>
  );
};
