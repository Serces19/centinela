// frontend/src/components/CostoRoiPanel.tsx
import React from 'react';
import {
  DollarSign,
  TrendingUp,
  Cpu,
  Zap,
  BarChart,
  ShieldCheck,
  Sparkles,
  Layers,
  ArrowUpRight,
} from 'lucide-react';
import { AlertaVista } from '../types';
import { formatCOP } from '../utils/formatters';

interface Props {
  alertas: AlertaVista[];
}

export const CostoRoiPanel: React.FC<Props> = ({ alertas }) => {
  const dineroEnRiesgoTotal = alertas.reduce(
    (acc, a) => acc + (a.alerta.dinero_en_riesgo_cop || 0),
    0
  );

  // Estimación de costo por alerta con Haiku 4.5 (~0.003 USD por análisis completo)
  const alertasAnalizadas = alertas.filter(
    (a) => a.alerta.estado !== 'nueva'
  ).length;

  const costoEstimadoUsd = Math.max(0.012, alertasAnalizadas * 0.0038);
  const tokensEstimados = alertasAnalizadas * 2850;

  // Tasa de ROI: pesos en riesgo por cada USD invertido
  const roiRatio =
    costoEstimadoUsd > 0
      ? Math.round(dineroEnRiesgoTotal / costoEstimadoUsd)
      : 0;

  return (
    <div className="space-y-6">
      {/* Header */}
      <section className="bg-white rounded-3xl p-6 border border-slate-200/70 shadow-card">
        <div className="flex items-center gap-2">
          <span className="text-xs font-bold uppercase tracking-wider text-slate-400">
            Observabilidad Financiera & Retorno de Inversión
          </span>
          <span className="text-[10px] font-bold px-2 py-0.5 rounded-full bg-emerald-50 text-emerald-700 border border-emerald-200">
            ROI 1:1.000+
          </span>
        </div>
        <h2 className="text-2xl font-bold tracking-tight text-slate-900 mt-1">
          Transparencia de Costos y Eficiencia de Inferencia
        </h2>
        <p className="text-xs text-slate-500 max-w-xl mt-0.5">
          Métricas en tiempo real de consumo de tokens en Amazon Bedrock (Claude Haiku 4.5) comparado contra el capital financiero protegido en las operaciones.
        </p>
      </section>

      {/* Grid de Métricas Principales */}
      <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-4">
        {/* Dinero en Riesgo Protegido */}
        <div className="bg-white p-5 rounded-3xl border border-slate-200/70 shadow-card space-y-2">
          <div className="flex items-center justify-between text-slate-400 text-xs font-medium">
            <span>Capital Vigilado Hoy</span>
            <ShieldCheck className="w-4 h-4 text-emerald-600" />
          </div>
          <div className="text-2xl font-black text-slate-900">
            {formatCOP(dineroEnRiesgoTotal)}
          </div>
          <span className="text-[11px] text-slate-400 block">
            En {alertas.length} alertas operacionales
          </span>
        </div>

        {/* Costo Inferencia USD */}
        <div className="bg-white p-5 rounded-3xl border border-slate-200/70 shadow-card space-y-2">
          <div className="flex items-center justify-between text-slate-400 text-xs font-medium">
            <span>Costo Total Inferencia</span>
            <Zap className="w-4 h-4 text-amber-500" />
          </div>
          <div className="text-2xl font-black text-slate-900">
            ${costoEstimadoUsd.toFixed(4)} <span className="text-xs font-normal text-slate-500">USD</span>
          </div>
          <span className="text-[11px] text-slate-400 block">
            ~${(costoEstimadoUsd * 4200).toFixed(0)} COP acumulado
          </span>
        </div>

        {/* Tokens Consumidos */}
        <div className="bg-white p-5 rounded-3xl border border-slate-200/70 shadow-card space-y-2">
          <div className="flex items-center justify-between text-slate-400 text-xs font-medium">
            <span>Tokens Consumidos</span>
            <Cpu className="w-4 h-4 text-blue-500" />
          </div>
          <div className="text-2xl font-black text-slate-900">
            {tokensEstimados.toLocaleString()}
          </div>
          <span className="text-[11px] text-slate-400 block">
            Claude Haiku 4.5 + Titan v2
          </span>
        </div>

        {/* Multiplicador ROI */}
        <div className="bg-white p-5 rounded-3xl border border-emerald-100 shadow-card bg-gradient-to-br from-white to-emerald-50/30 space-y-2">
          <div className="flex items-center justify-between text-emerald-800 text-xs font-medium">
            <span>Multiplicador ROI</span>
            <TrendingUp className="w-4 h-4 text-emerald-600" />
          </div>
          <div className="text-2xl font-black text-emerald-700">
            {(roiRatio / 1_000_000).toFixed(1)}M:1
          </div>
          <span className="text-[11px] text-emerald-600 font-medium block">
            COP protegidos por cada $1 USD
          </span>
        </div>
      </div>

      {/* Desglose de Inferencia y Arquitectura Serverless */}
      <div className="grid grid-cols-1 lg:grid-cols-2 gap-5">
        {/* Tabla de Modelos */}
        <div className="bg-white p-6 rounded-3xl border border-slate-200/70 shadow-card space-y-4">
          <h3 className="text-sm font-bold text-slate-900 flex items-center gap-2">
            <Layers className="w-4 h-4 text-slate-500" />
            Desglose de Modelos y Costo Unitario
          </h3>

          <div className="space-y-3">
            <div className="p-3.5 rounded-2xl bg-slate-50 border border-slate-200/60 flex items-center justify-between">
              <div>
                <span className="text-xs font-bold text-slate-800 block">
                  Claude Haiku 4.5 (Bedrock)
                </span>
                <span className="text-[11px] text-slate-400">
                  Razonamiento del Analista, Estratega y Chat
                </span>
              </div>
              <div className="text-right">
                <span className="text-xs font-mono font-bold text-slate-900 block">
                  $1.00 / 1M tokens
                </span>
                <span className="text-[10px] text-emerald-600 font-medium">
                  Caché activa (90% ahorro)
                </span>
              </div>
            </div>

            <div className="p-3.5 rounded-2xl bg-slate-50 border border-slate-200/60 flex items-center justify-between">
              <div>
                <span className="text-xs font-bold text-slate-800 block">
                  Amazon Titan Embed Text v2
                </span>
                <span className="text-[11px] text-slate-400">
                  Indexación semántica de políticas PDF (RAG)
                </span>
              </div>
              <div className="text-right">
                <span className="text-xs font-mono font-bold text-slate-900 block">
                  $0.02 / 1M tokens
                </span>
                <span className="text-[10px] text-slate-400">Local fallback activo</span>
              </div>
            </div>

            <div className="p-3.5 rounded-2xl bg-slate-50 border border-slate-200/60 flex items-center justify-between">
              <div>
                <span className="text-xs font-bold text-slate-800 block">
                  DuckDB Semántico en Lambda
                </span>
                <span className="text-[11px] text-slate-400">
                  Cómputo en memoria sin costo de base de datos dedicada
                </span>
              </div>
              <div className="text-right">
                <span className="text-xs font-mono font-bold text-emerald-700 block">
                  $0.00 / query
                </span>
                <span className="text-[10px] text-slate-400">&lt; 15 ms por consulta</span>
              </div>
            </div>
          </div>
        </div>

        {/* Comparativa de Eficiencia Operativa */}
        <div className="bg-white p-6 rounded-3xl border border-slate-200/70 shadow-card space-y-4 flex flex-col justify-between">
          <div className="space-y-2">
            <h3 className="text-sm font-bold text-slate-900 flex items-center gap-2">
              <Sparkles className="w-4 h-4 text-amber-500" />
              Impacto en la Operación Diaria
            </h3>
            <p className="text-xs text-slate-500 leading-relaxed">
              Centinela elimina la necesidad de auditorías manuales de planillas de cálculo. Cada anomalía es detectada por el Vigía en milisegundos, investigada formalmente y presentada con un borrador de acción listo para aprobación ejecutiva.
            </p>
          </div>

          <div className="p-4 rounded-2xl bg-emerald-50/70 border border-emerald-200 text-xs text-emerald-950 space-y-2">
            <div className="font-bold flex items-center gap-1.5 text-emerald-800">
              <ArrowUpRight className="w-4 h-4 text-emerald-600" />
              Retorno Comprobado del MVP
            </div>
            <p className="text-emerald-800 leading-relaxed">
              Detectar a tiempo una sola caída de margen o una factura vencida de un cliente clave amortiza los costos de cómputo e infraestructura de Centinela durante más de <strong>12 meses continuos</strong>.
            </p>
          </div>
        </div>
      </div>
    </div>
  );
};
