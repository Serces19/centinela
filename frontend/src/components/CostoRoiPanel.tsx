// frontend/src/components/CostoRoiPanel.tsx
import React, { useEffect, useState } from 'react';
import { Cpu, DollarSign, Loader2, MessageSquare, ShieldCheck } from 'lucide-react';
import { ResumenAlertas, ResumenCostos } from '../types';
import { getCostos } from '../api/client';
import { formatCOP } from '../utils/formatters';

interface Props {
  resumen: ResumenAlertas | null;
}

const NOMBRE_AGENTE: Record<string, string> = {
  analista: 'Analista (explica la causa)',
  estratega: 'Estratega (elige y justifica acciones)',
  chat: 'Asistente de chat',
};

const usd = (v: number | null | undefined, d = 4) => (v === null || v === undefined ? '—' : `US$ ${v.toFixed(d)}`);

export const CostoRoiPanel: React.FC<Props> = ({ resumen }) => {
  const [costos, setCostos] = useState<ResumenCostos | null>(null);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    getCostos().then(setCostos).catch((e) => setError((e as Error).message));
  }, [resumen]);

  if (error) return <div role="alert" className="glass rounded-4xl p-8 text-center text-sm text-rose-700">{error}</div>;
  if (!costos) return <div className="glass rounded-4xl p-10 text-center text-sm text-slate-500 flex items-center justify-center gap-2"><Loader2 className="w-4 h-4 animate-spin" /> Cargando…</div>;

  return (
    <div className="space-y-6">
      <section className="glass rounded-4xl p-6">
        <span className="section-eyebrow">Costo real de inferencia</span>
        <h2 className="text-xl font-semibold text-slate-900">Lo que cuesta que Centinela analice y conteste</h2>
        <p className="text-xs text-slate-500 mt-1 max-w-2xl">Se calcula con los tokens que reporta Amazon Bedrock en cada llamada (Claude Haiku 4.5), acumulados desde el último reinicio de la demo. No son estimaciones.</p>
      </section>

      <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-4">
        <div className="glass rounded-4xl p-5 space-y-1">
          <div className="flex items-center justify-between text-slate-400 text-xs font-medium"><span>Costo total medido</span><DollarSign className="w-4 h-4 text-amber-500" /></div>
          <div className="text-2xl font-black text-slate-900">{usd(costos.total_usd)}</div>
          <span className="text-[11px] text-slate-400">{costos.llamadas} llamadas al modelo</span>
        </div>
        <div className="glass rounded-4xl p-5 space-y-1">
          <div className="flex items-center justify-between text-slate-400 text-xs font-medium"><span>Costo por alerta analizada</span><ShieldCheck className="w-4 h-4 text-emerald-600" /></div>
          <div className="text-2xl font-black text-slate-900">{usd(costos.usd_por_alerta)}</div>
          <span className="text-[11px] text-slate-400">Analista + Estratega · {costos.alertas_analizadas} alerta(s)</span>
        </div>
        <div className="glass rounded-4xl p-5 space-y-1">
          <div className="flex items-center justify-between text-slate-400 text-xs font-medium"><span>Costo por pregunta del chat</span><MessageSquare className="w-4 h-4 text-blue-500" /></div>
          <div className="text-2xl font-black text-slate-900">{usd(costos.usd_por_pregunta_chat)}</div>
          <span className="text-[11px] text-slate-400">Promedio de las preguntas hechas</span>
        </div>
        <div className="glass rounded-4xl p-5 space-y-1">
          <div className="flex items-center justify-between text-slate-400 text-xs font-medium"><span>Tokens procesados</span><Cpu className="w-4 h-4 text-purple-500" /></div>
          <div className="text-2xl font-black text-slate-900">{(costos.tokens_in + costos.tokens_out).toLocaleString('es-CO')}</div>
          <span className="text-[11px] text-slate-400">{costos.tokens_in.toLocaleString('es-CO')} de entrada · {costos.tokens_out.toLocaleString('es-CO')} de salida</span>
        </div>
      </div>

      <section className="glass rounded-4xl p-6 space-y-3">
        <h3 className="text-sm font-bold text-slate-900">Por agente</h3>
        {costos.por_agente.length === 0 ? (
          <p className="text-xs text-slate-500">Aún no hay llamadas al modelo. Analiza una alerta o haz una pregunta en el chat.</p>
        ) : (
          <table className="w-full text-xs">
            <thead><tr className="text-left text-slate-400 uppercase tracking-wider text-[10px]"><th className="py-2 font-semibold">Agente</th><th className="py-2 font-semibold text-right">Llamadas</th><th className="py-2 font-semibold text-right">Tokens</th><th className="py-2 font-semibold text-right">Costo</th></tr></thead>
            <tbody className="divide-y divide-white/70">
              {costos.por_agente.map((a) => (
                <tr key={a.agente}>
                  <td className="py-2.5 font-semibold text-slate-800">{NOMBRE_AGENTE[a.agente] ?? a.agente}</td>
                  <td className="py-2.5 text-right text-slate-600">{a.llamadas}</td>
                  <td className="py-2.5 text-right text-slate-600">{(a.tokens_in + a.tokens_out).toLocaleString('es-CO')}</td>
                  <td className="py-2.5 text-right font-mono text-slate-900">{usd(a.costo_usd)}</td>
                </tr>
              ))}
            </tbody>
          </table>
        )}
      </section>

      <section className="glass rounded-4xl p-6 text-xs text-slate-600 space-y-1.5">
        <h3 className="text-sm font-bold text-slate-900">Para ponerlo en contexto</h3>
        <p>Dinero en riesgo identificado hoy: <strong className="text-slate-900">{formatCOP(resumen?.total_dinero_en_riesgo_cop ?? 0)}</strong> en {resumen?.pendientes ?? 0} causas pendientes.</p>
        <p>Las consultas SQL, el Vigía y la capa de datos corren en AWS Lambda sin servidores dedicados: no hay costo cuando nadie usa el sistema. El único costo que crece con el uso es el de los tokens de arriba.</p>
      </section>
    </div>
  );
};
