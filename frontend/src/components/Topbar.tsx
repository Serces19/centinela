// frontend/src/components/Topbar.tsx
import React, { useState } from 'react';
import {
  Calendar,
  FastForward,
  RotateCcw,
  Sparkles,
  Loader2,
  CheckCircle2,
  Flag,
} from 'lucide-react';
import { formatFecha } from '../utils/formatters';
import { SimulacionCorte } from '../types';
import {
  CORTE_INICIAL_LIMPIO,
  CORTE_HITO_S1,
  CORTE_HITO_CIERRE,
} from '../utils/alertas';

interface Props {
  corte: SimulacionCorte | null;
  loadingReloj: boolean;
  onAvanzar: (dias: number) => Promise<void>;
  onReiniciar: () => Promise<void>;
  onIrAFecha: (fechaIso: string) => Promise<void>;
  chatAbierto: boolean;
  onToggleChat: () => void;
  tituloPantalla: string;
}

interface HitoDemo {
  fecha: string;
  label: string;
  sublabel: string;
  colorDot: string;
  colorActive: string;
  tooltip: string;
}

const HITOS_DEMO: HitoDemo[] = [
  {
    fecha: CORTE_INICIAL_LIMPIO,
    label: '18 Jun',
    sublabel: 'Corte Limpio',
    colorDot: 'bg-emerald-500',
    colorActive: 'bg-emerald-50 text-emerald-900 border-emerald-300 ring-1 ring-emerald-400/40',
    tooltip: '🟢 Corte Inicial Limpio (18 Jun 2026): 0 desviaciones críticas, operación en estado óptimo',
  },
  {
    fecha: CORTE_HITO_S1,
    label: '15 Ago',
    sublabel: 'Hito S1',
    colorDot: 'bg-amber-500',
    colorActive: 'bg-amber-50 text-amber-900 border-amber-300 ring-1 ring-amber-400/40',
    tooltip: '🟠 Hito S1 (15 Ago 2026): Alerta de proveedor PR08 incrementa costo +25% ($23.5M en riesgo)',
  },
  {
    fecha: CORTE_HITO_CIERRE,
    label: '30 Sep',
    sublabel: 'Cierre S1-S5',
    colorDot: 'bg-rose-500',
    colorActive: 'bg-rose-50 text-rose-900 border-rose-300 ring-1 ring-rose-400/40',
    tooltip: '🔴 Hito Cierre (30 Sep 2026): Escenarios S1 a S5 activos listos para decisión humana',
  },
];

export const Topbar: React.FC<Props> = ({
  corte,
  loadingReloj,
  onAvanzar,
  onReiniciar,
  onIrAFecha,
  chatAbierto,
  onToggleChat,
  tituloPantalla,
}) => {
  const [loadingDias, setLoadingDias] = useState<number | null>(null);
  const [loadingHito, setLoadingHito] = useState<string | null>(null);

  const fechaActualIso = corte?.corte
    ? corte.corte.split('T')[0]
    : CORTE_INICIAL_LIMPIO;
  const esCorteInicial = fechaActualIso <= CORTE_INICIAL_LIMPIO;

  const handleAvanzarClick = async (dias: number) => {
    try {
      setLoadingDias(dias);
      await onAvanzar(dias);
    } finally {
      setLoadingDias(null);
    }
  };

  const handleHitoClick = async (fechaHito: string) => {
    if (fechaHito === fechaActualIso || loadingReloj) return;
    try {
      setLoadingHito(fechaHito);
      await onIrAFecha(fechaHito);
    } finally {
      setLoadingHito(null);
    }
  };

  const handleDateInputChange = async (e: React.ChangeEvent<HTMLInputElement>) => {
    const nuevaFecha = e.target.value;
    if (!nuevaFecha || nuevaFecha === fechaActualIso || loadingReloj) return;
    try {
      setLoadingHito(nuevaFecha);
      await onIrAFecha(nuevaFecha);
    } finally {
      setLoadingHito(null);
    }
  };

  return (
    <header className="h-18 px-4 sm:px-6 bg-white/90 backdrop-blur-md border-b border-slate-200/70 flex items-center justify-between sticky top-0 z-30">
      {/* Título de la sección activa */}
      <div className="flex items-center gap-3 min-w-0">
        <h1 className="text-base sm:text-lg font-semibold tracking-tight text-slate-900 truncate">
          {tituloPantalla}
        </h1>
        <div className="hidden xl:flex items-center gap-1.5 px-2.5 py-1 rounded-full bg-slate-100 border border-slate-200/60 text-[11px] font-medium text-slate-600 shrink-0">
          <span className="w-1.5 h-1.5 rounded-full bg-emerald-500 animate-pulse"></span>
          Distribuidora Andina · Producción
        </div>
      </div>

      {/* Control de Reloj Simulado, Selector de Fecha e Hitos Clave */}
      <div className="flex items-center gap-2 sm:gap-3">
        <div className="flex items-center gap-1.5 p-1 sm:p-1.5 rounded-2xl bg-slate-100/90 border border-slate-200/80 shadow-xs">
          {/* Selector de Calendario */}
          <div
            className="flex items-center gap-2 px-2.5 sm:px-3 py-1 bg-white rounded-xl border border-slate-200/80 shadow-xs hover:border-slate-300 transition-colors"
            title="Seleccionar fecha simulada (entre 18 Jun 2026 y 30 Sep 2026)"
          >
            <Calendar className="w-3.5 h-3.5 text-slate-500 shrink-0" />
            <div className="flex flex-col">
              <span className="text-[8px] uppercase tracking-wider font-bold text-slate-400 leading-none">
                Corte Simulado
              </span>
              <input
                type="date"
                min={CORTE_INICIAL_LIMPIO}
                max={CORTE_HITO_CIERRE}
                value={fechaActualIso}
                onChange={handleDateInputChange}
                disabled={loadingReloj || loadingHito !== null}
                className="text-xs font-semibold text-slate-800 bg-transparent border-0 p-0 focus:ring-0 cursor-pointer disabled:opacity-50"
              />
            </div>
            {loadingHito && (
              <Loader2 className="w-3 h-3 animate-spin text-slate-400 ml-1" />
            )}
          </div>

          {/* Separador vertical sutil */}
          <div className="hidden md:block w-px h-6 bg-slate-200 mx-0.5" />

          {/* 3 Botones de Acceso Rápido a Hitos Clave de la Demo */}
          <div className="hidden lg:flex items-center gap-1">
            {HITOS_DEMO.map((hito) => {
              const esActivo = fechaActualIso === hito.fecha;
              const estaCargando = loadingHito === hito.fecha;

              return (
                <button
                  key={hito.fecha}
                  onClick={() => handleHitoClick(hito.fecha)}
                  disabled={loadingReloj || loadingHito !== null}
                  title={hito.tooltip}
                  className={`px-2 py-1 rounded-xl text-[11px] font-medium transition-all flex items-center gap-1.5 cursor-pointer disabled:opacity-50 ${
                    esActivo
                      ? `${hito.colorActive} shadow-xs font-semibold`
                      : 'text-slate-600 hover:text-slate-900 hover:bg-white active:scale-95'
                  }`}
                >
                  {estaCargando ? (
                    <Loader2 className="w-2.5 h-2.5 animate-spin" />
                  ) : (
                    <span className={`w-1.5 h-1.5 rounded-full ${hito.colorDot}`} />
                  )}
                  <span>{hito.label}</span>
                  <span className="text-[9px] text-slate-400 font-normal">
                    ({hito.sublabel})
                  </span>
                </button>
              );
            })}
          </div>

          {/* Separador vertical sutil */}
          <div className="w-px h-6 bg-slate-200 mx-0.5" />

          {/* Botones de Pasos Sutiles (+1d, +7d) */}
          <div className="flex items-center gap-0.5">
            <button
              onClick={() => handleAvanzarClick(1)}
              disabled={loadingReloj || loadingDias !== null || loadingHito !== null}
              className="px-2 py-1 rounded-xl text-xs font-medium text-slate-700 hover:text-slate-900 hover:bg-white active:scale-95 transition-all disabled:opacity-50 flex items-center gap-1 cursor-pointer"
              title="Avanzar 1 día en la simulación"
            >
              {loadingDias === 1 ? (
                <Loader2 className="w-3 h-3 animate-spin" />
              ) : (
                <FastForward className="w-3 h-3 text-slate-400" />
              )}
              <span className="hidden sm:inline">+1 día</span>
              <span className="sm:hidden">+1d</span>
            </button>

            <button
              onClick={() => handleAvanzarClick(7)}
              disabled={loadingReloj || loadingDias !== null || loadingHito !== null}
              className="px-2 py-1 rounded-xl text-xs font-medium text-slate-700 hover:text-slate-900 hover:bg-white active:scale-95 transition-all disabled:opacity-50 flex items-center gap-1 cursor-pointer"
              title="Avanzar 7 días (1 semana)"
            >
              {loadingDias === 7 ? (
                <Loader2 className="w-3 h-3 animate-spin" />
              ) : (
                <FastForward className="w-3 h-3 text-slate-400" />
              )}
              <span className="hidden sm:inline">+7 días</span>
              <span className="sm:hidden">+7d</span>
            </button>
          </div>
        </div>

        {/* Botón Chat de Soporte */}
        <button
          onClick={onToggleChat}
          className={`flex items-center gap-2 px-3 py-2 rounded-2xl text-xs font-medium transition-all shadow-xs cursor-pointer ${
            chatAbierto
              ? 'bg-slate-900 text-white shadow-subtle'
              : 'bg-white border border-slate-200/80 text-slate-700 hover:text-slate-900 hover:border-slate-300'
          }`}
          title="Abrir u ocultar asistente de chat anclado"
        >
          <Sparkles
            className={`w-3.5 h-3.5 ${
              chatAbierto ? 'text-amber-300' : 'text-slate-500'
            }`}
          />
          <span className="hidden md:inline">Asistente Centinela</span>
        </button>
      </div>
    </header>
  );
};
