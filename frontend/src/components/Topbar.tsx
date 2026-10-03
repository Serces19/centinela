// frontend/src/components/Topbar.tsx
import React, { useState } from 'react';
import {
  Calendar,
  FastForward,
  RotateCcw,
  Sparkles,
  MessageSquareText,
  Loader2,
  CheckCircle2,
} from 'lucide-react';
import { formatFecha } from '../utils/formatters';
import { SimulacionCorte } from '../types';

interface Props {
  corte: SimulacionCorte | null;
  loadingReloj: boolean;
  onAvanzar: (dias: number) => Promise<void>;
  onReiniciar: () => Promise<void>;
  chatAbierto: boolean;
  onToggleChat: () => void;
  tituloPantalla: string;
}

export const Topbar: React.FC<Props> = ({
  corte,
  loadingReloj,
  onAvanzar,
  onReiniciar,
  chatAbierto,
  onToggleChat,
  tituloPantalla,
}) => {
  const [loadingDias, setLoadingDias] = useState<number | null>(null);
  const [loadingReset, setLoadingReset] = useState(false);

  const handleAvanzarClick = async (dias: number) => {
    try {
      setLoadingDias(dias);
      await onAvanzar(dias);
    } finally {
      setLoadingDias(null);
    }
  };

  const handleReiniciarClick = async () => {
    try {
      setLoadingReset(true);
      await onReiniciar();
    } finally {
      setLoadingReset(false);
    }
  };

  const fechaFormateada = corte ? formatFecha(corte.corte) : 'Cargando...';
  const esCorteInicial = Boolean(corte && corte.corte === corte.corte_inicial_limpio);

  return (
    <header className="h-18 px-6 bg-white/80 backdrop-blur-md border-b border-slate-200/70 flex items-center justify-between sticky top-0 z-30">
      {/* Título de la sección activa */}
      <div className="flex items-center gap-3">
        <h1 className="text-lg font-semibold tracking-tight text-slate-900">
          {tituloPantalla}
        </h1>
        <div className="hidden sm:flex items-center gap-1.5 px-2.5 py-1 rounded-full bg-slate-100 border border-slate-200/60 text-[11px] font-medium text-slate-600">
          <span className="w-1.5 h-1.5 rounded-full bg-emerald-500 animate-pulse"></span>
          Distribuidora Andina · Producción
        </div>
      </div>

      {/* Control de Reloj Simulado */}
      <div className="flex items-center gap-3">
        <div className="flex items-center gap-2 p-1.5 rounded-2xl bg-slate-100/90 border border-slate-200/80 shadow-xs">
          {/* Pill con fecha actual simulada */}
          <div className="flex items-center gap-2 px-3 py-1.5 bg-white rounded-xl border border-slate-200/60 shadow-xs">
            <Calendar className="w-3.5 h-3.5 text-slate-500" />
            <div className="flex flex-col">
              <span className="text-[9px] uppercase tracking-wider font-bold text-slate-400 leading-none">
                Corte Simulado
              </span>
              <span className="text-xs font-semibold text-slate-800 leading-tight">
                {fechaFormateada}
              </span>
            </div>
            {esCorteInicial && (
              <span
                className="hidden md:inline-flex items-center gap-0.5 text-[9px] font-medium text-emerald-700 bg-emerald-50 px-1.5 py-0.5 rounded border border-emerald-200"
                title="Corte inicial limpio sin problemas"
              >
                <CheckCircle2 className="w-2.5 h-2.5" />
                Limpio
              </span>
            )}
          </div>

          {/* Botones de acción rápida */}
          <div className="flex items-center gap-1">
            <button
              onClick={() => handleAvanzarClick(1)}
              disabled={loadingReloj || loadingDias !== null || loadingReset}
              className="px-2.5 py-1.5 rounded-xl text-xs font-medium text-slate-700 hover:text-slate-900 hover:bg-white active:scale-95 transition-all disabled:opacity-50 flex items-center gap-1 cursor-pointer"
              title="Avanzar 1 día en la simulación"
            >
              {loadingDias === 1 ? (
                <Loader2 className="w-3.5 h-3.5 animate-spin" />
              ) : (
                <FastForward className="w-3 h-3 text-slate-400" />
              )}
              +1 día
            </button>

            <button
              onClick={() => handleAvanzarClick(7)}
              disabled={loadingReloj || loadingDias !== null || loadingReset}
              className="px-2.5 py-1.5 rounded-xl text-xs font-medium text-slate-700 hover:text-slate-900 hover:bg-white active:scale-95 transition-all disabled:opacity-50 flex items-center gap-1 cursor-pointer"
              title="Avanzar 7 días (1 semana)"
            >
              {loadingDias === 7 ? (
                <Loader2 className="w-3.5 h-3.5 animate-spin" />
              ) : (
                <FastForward className="w-3 h-3 text-slate-400" />
              )}
              +7 días
            </button>

            <button
              onClick={handleReiniciarClick}
              disabled={
                loadingReloj || loadingReset || loadingDias !== null || esCorteInicial
              }
              className="px-2.5 py-1.5 rounded-xl text-xs font-medium text-rose-600 hover:bg-rose-50 active:scale-95 transition-all disabled:opacity-40 disabled:hover:bg-transparent flex items-center gap-1 cursor-pointer"
              title="Restablecer reloj al 18 Jun 2026"
            >
              {loadingReset ? (
                <Loader2 className="w-3.5 h-3.5 animate-spin" />
              ) : (
                <RotateCcw className="w-3 h-3" />
              )}
              Reiniciar
            </button>
          </div>
        </div>

        {/* Botón Chat de Soporte */}
        <button
          onClick={onToggleChat}
          className={`flex items-center gap-2 px-3.5 py-2 rounded-2xl text-xs font-medium transition-all shadow-xs cursor-pointer ${
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
          <span className="hidden sm:inline">Asistente Centinela</span>
        </button>
      </div>
    </header>
  );
};
