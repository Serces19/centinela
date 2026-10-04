// frontend/src/components/Topbar.tsx
import React, { useState } from 'react';
import {
  Calendar,
  FastForward,
  RotateCcw,
  Sparkles,
  Loader2,
  Menu,
} from 'lucide-react';
import { formatFecha } from '../utils/formatters';
import { SimulacionCorte } from '../types';
interface Props {
  corte: SimulacionCorte | null;
  loadingReloj: boolean;
  onAvanzar: (dias: number) => Promise<void>;
  onReiniciar: () => Promise<void>;
  onIrAFecha: (fechaIso: string) => Promise<void>;
  chatAbierto: boolean;
  onToggleChat: () => void;
  tituloPantalla: string;
  subtituloPantalla: string;
  onAbrirMenu: () => void;
}

interface Atajo {
  fecha: string;
  label: string;
  sublabel: string;
}

// Fechas de atajo para la demostración: el inicio, mediados de agosto y el cierre del periodo de datos.
const iso = (f?: string, defecto = '') => (f ? f.split('T')[0] : defecto);

export const Topbar: React.FC<Props> = ({
  corte,
  loadingReloj,
  onAvanzar,
  onReiniciar,
  onIrAFecha,
  chatAbierto,
  onToggleChat,
  tituloPantalla,
  subtituloPantalla,
  onAbrirMenu,
}) => {
  const [loadingDias, setLoadingDias] = useState<number | null>(null);
  const [loadingHito, setLoadingHito] = useState<string | null>(null);

  const inicio = iso(corte?.corte_inicial_limpio, '2026-06-18');
  const cierre = iso(corte?.corte_maximo, '2026-09-30');
  const fechaActualIso = iso(corte?.corte, inicio);
  const esCorteInicial = fechaActualIso <= inicio;
  const atajos: Atajo[] = [
    { fecha: inicio, label: formatFecha(inicio).replace(/ de \d{4}| \d{4}$/, ''), sublabel: 'Inicio' },
    { fecha: '2026-08-15', label: '15 ago', sublabel: 'Mediados de agosto' },
    { fecha: cierre, label: formatFecha(cierre).replace(/ de \d{4}| \d{4}$/, ''), sublabel: 'Cierre' },
  ];

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

  const deshabilitado = loadingReloj || loadingDias !== null || loadingHito !== null;

  return (
    <header className="px-4 sm:px-6 lg:px-8 pt-4 lg:pt-8 pb-2 space-y-4">
      <div className="flex items-start justify-between gap-3">
        <div className="flex items-start gap-3 min-w-0">
          <button onClick={onAbrirMenu} className="icon-btn lg:hidden mt-1 shrink-0" aria-label="Abrir menú">
            <Menu className="w-4 h-4" />
          </button>
          <div className="min-w-0">
            <h1 className="text-2xl sm:text-3xl lg:text-4xl font-semibold tracking-tight text-slate-900 leading-tight truncate">
              {tituloPantalla}
            </h1>
            <p className="text-sm text-slate-500 mt-0.5 line-clamp-2">{subtituloPantalla}</p>
          </div>
        </div>

        <div className="flex items-center gap-2 shrink-0">
          <div className="hidden xl:flex items-center gap-2 px-3.5 h-10 rounded-full glass text-xs font-medium text-slate-600">
            <span className="w-2 h-2 rounded-full bg-emerald-500 animate-pulse" />
            Distribuidora Andina
          </div>
          <button
            onClick={onToggleChat}
            className={`flex items-center gap-2 h-10 px-3.5 sm:px-4 rounded-full text-xs font-semibold transition-all cursor-pointer active:scale-95 ${
              chatAbierto
                ? 'bg-slate-900 text-white shadow-float'
                : 'glass text-slate-700 hover:bg-white'
            }`}
            title="Abrir u ocultar asistente de chat anclado"
          >
            <Sparkles className={`w-4 h-4 ${chatAbierto ? 'text-lime' : 'text-emerald-600'}`} />
            <span className="hidden sm:inline">Asistente</span>
          </button>
        </div>
      </div>

      {/* Reloj simulado: fecha, hitos y pasos */}
      <div className="flex items-center gap-2 no-scrollbar overflow-x-auto pb-1 -mx-1 px-1">
        <div
          className="flex items-center gap-2 pl-3 pr-3 h-11 rounded-full glass shrink-0"
          title="Seleccionar la fecha simulada del sistema"
        >
          <Calendar className="w-4 h-4 text-emerald-600 shrink-0" />
          <div className="flex flex-col leading-none">
            <span className="text-[9px] uppercase tracking-wider font-bold text-slate-400">Corte simulado</span>
            <input
              type="date"
              min={inicio}
              max={cierre}
              value={fechaActualIso}
              onChange={handleDateInputChange}
              disabled={deshabilitado}
              className="text-xs font-semibold text-slate-800 bg-transparent border-0 p-0 mt-0.5 focus:ring-0 cursor-pointer disabled:opacity-50"
            />
          </div>
          {loadingHito && <Loader2 className="w-3.5 h-3.5 animate-spin text-slate-400" />}
        </div>

        <div className="flex items-center gap-1 p-1 h-11 rounded-full glass shrink-0">
          {atajos.map((hito) => {
            const esActivo = fechaActualIso === hito.fecha;
            const estaCargando = loadingHito === hito.fecha;
            return (
              <button
                key={hito.fecha}
                onClick={() => handleHitoClick(hito.fecha)}
                disabled={deshabilitado}
                title={`Ir al ${formatFecha(hito.fecha)}`}
                aria-pressed={esActivo}
                className={`h-9 px-3 rounded-full text-[11px] font-semibold transition-all flex items-center gap-1.5 cursor-pointer disabled:opacity-50 active:scale-95 ${
                  esActivo ? 'bg-lime text-lime-ink shadow-xs' : 'text-slate-600 hover:bg-white'
                }`}
              >
                {estaCargando && <Loader2 className="w-3 h-3 animate-spin" />}
                <span>{hito.label}</span>
                <span className="hidden xl:inline text-[10px] font-normal opacity-60">{hito.sublabel}</span>
              </button>
            );
          })}
        </div>

        <div className="flex items-center gap-1 p-1 h-11 rounded-full glass shrink-0">
          {[1, 7, 30].map((d) => (
            <button
              key={d}
              onClick={() => handleAvanzarClick(d)}
              disabled={deshabilitado}
              className="h-9 px-3 rounded-full text-xs font-semibold text-slate-700 hover:bg-white active:scale-95 transition-all disabled:opacity-50 flex items-center gap-1.5 cursor-pointer"
              title={`Avanzar ${d} día(s) en la simulación`}
            >
              {loadingDias === d ? (
                <Loader2 className="w-3.5 h-3.5 animate-spin" />
              ) : (
                <FastForward className="w-3.5 h-3.5 text-slate-400" />
              )}
              +{d}d
            </button>
          ))}
          {!esCorteInicial && (
            <button
              onClick={onReiniciar}
              disabled={deshabilitado}
              className="h-9 w-9 rounded-full flex items-center justify-center text-slate-500 hover:bg-white active:scale-95 disabled:opacity-50 cursor-pointer"
              title="Reiniciar al corte inicial"
              aria-label="Reiniciar simulación"
            >
              <RotateCcw className="w-3.5 h-3.5" />
            </button>
          )}
        </div>
      </div>
    </header>
  );
};
