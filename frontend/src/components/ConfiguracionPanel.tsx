// frontend/src/components/ConfiguracionPanel.tsx
import React, { useState } from 'react';
import {
  Sliders,
  Shield,
  Save,
  CheckCircle2,
  AlertCircle,
  HelpCircle,
  Lock,
} from 'lucide-react';

export const ConfiguracionPanel: React.FC = () => {
  const [margenMinimo, setMargenMinimo] = useState(15.0);
  const [diasMora, setDiasMora] = useState(15);
  const [coberturaMinima, setCoberturaMinima] = useState(7);
  const [descuentoMaximo, setDescuentoMaximo] = useState(8.0);
  const [inactividadVeces, setInactividadVeces] = useState(3.0);

  // Niveles de autonomía por tipo de acción: "informa" | "propone" | "ejecuta"
  const [autonomiaAjustePrecio, setAutonomiaAjustePrecio] = useState<'informa' | 'propone' | 'ejecuta'>('propone');
  const [autonomiaCartera, setAutonomiaCartera] = useState<'informa' | 'propone' | 'ejecuta'>('propone');
  const [autonomiaOrdenes, setAutonomiaOrdenes] = useState<'informa' | 'propone' | 'ejecuta'>('propone');

  const [guardadoExitoso, setGuardadoExitoso] = useState(false);

  const handleGuardar = (e: React.FormEvent) => {
    e.preventDefault();
    setGuardadoExitoso(true);
    setTimeout(() => setGuardadoExitoso(false), 3000);
  };

  return (
    <div className="space-y-6">
      {/* Header */}
      <section className="bg-white rounded-3xl p-6 border border-slate-200/70 shadow-card">
        <div className="flex items-center gap-2">
          <span className="text-xs font-bold uppercase tracking-wider text-slate-400">
            Gobernanza de Agentes & Parámetros Operacionales
          </span>
          <span className="text-[10px] font-bold px-2 py-0.5 rounded-full bg-slate-100 text-slate-700 border border-slate-200">
            Reglas de Política
          </span>
        </div>
        <h2 className="text-2xl font-bold tracking-tight text-slate-900 mt-1">
          Configuración de Umbrales y Niveles de Autonomía
        </h2>
        <p className="text-xs text-slate-500 max-w-xl mt-0.5">
          Defina los umbrales de disparo del Vigía y el grado de intervención concedido al Ejecutor para cada tipo de acción operacional.
        </p>
      </section>

      <form onSubmit={handleGuardar} className="space-y-6">
        {/* 1. Umbrales de los KPIs Vigilados */}
        <div className="bg-white p-6 rounded-3xl border border-slate-200/70 shadow-card space-y-5">
          <div className="flex items-center justify-between border-b border-slate-100 pb-3">
            <div>
              <h3 className="text-sm font-bold text-slate-900">
                1. Umbrales de Disparo de Alertas (KPIs)
              </h3>
              <p className="text-xs text-slate-400">
                Límites alineados con las políticas oficiales de Distribuidora Andina
              </p>
            </div>
            <span className="text-xs text-emerald-600 font-semibold bg-emerald-50 px-2.5 py-1 rounded-full border border-emerald-100">
              5 Detectores Activos
            </span>
          </div>

          <div className="grid grid-cols-1 md:grid-cols-2 gap-5">
            {/* Margen */}
            <div className="p-4 rounded-2xl bg-slate-50 border border-slate-200/60 space-y-2">
              <div className="flex items-center justify-between">
                <label className="text-xs font-bold text-slate-800">
                  Margen Mínimo Aceptable (%)
                </label>
                <span className="text-xs font-mono font-bold text-slate-900 bg-white px-2 py-0.5 rounded border border-slate-200">
                  {margenMinimo}%
                </span>
              </div>
              <input
                type="range"
                min="5"
                max="25"
                step="0.5"
                value={margenMinimo}
                onChange={(e) => setMargenMinimo(parseFloat(e.target.value))}
                className="w-full accent-slate-900 cursor-pointer"
              />
              <span className="text-[11px] text-slate-400 block">
                Dispara alerta de severidad alta si el margen semanal cae por debajo.
              </span>
            </div>

            {/* Días Mora */}
            <div className="p-4 rounded-2xl bg-slate-50 border border-slate-200/60 space-y-2">
              <div className="flex items-center justify-between">
                <label className="text-xs font-bold text-slate-800">
                  Días de Mora Máximos (Cartera)
                </label>
                <span className="text-xs font-mono font-bold text-slate-900 bg-white px-2 py-0.5 rounded border border-slate-200">
                  {diasMora} días
                </span>
              </div>
              <input
                type="range"
                min="5"
                max="60"
                step="1"
                value={diasMora}
                onChange={(e) => setDiasMora(parseInt(e.target.value, 10))}
                className="w-full accent-slate-900 cursor-pointer"
              />
              <span className="text-[11px] text-slate-400 block">
                Política FIN-POL-004: escalamiento a cartera tras superar este umbral.
              </span>
            </div>

            {/* Cobertura Inventario */}
            <div className="p-4 rounded-2xl bg-slate-50 border border-slate-200/60 space-y-2">
              <div className="flex items-center justify-between">
                <label className="text-xs font-bold text-slate-800">
                  Cobertura Mínima de Inventario
                </label>
                <span className="text-xs font-mono font-bold text-slate-900 bg-white px-2 py-0.5 rounded border border-slate-200">
                  {coberturaMinima} días
                </span>
              </div>
              <input
                type="range"
                min="2"
                max="30"
                step="1"
                value={coberturaMinima}
                onChange={(e) => setCoberturaMinima(parseInt(e.target.value, 10))}
                className="w-full accent-slate-900 cursor-pointer"
              />
              <span className="text-[11px] text-slate-400 block">
                Política OPE-POL-007: alerta de riesgo de quiebre para abastecimiento.
              </span>
            </div>

            {/* Descuentos Fuera de Política */}
            <div className="p-4 rounded-2xl bg-slate-50 border border-slate-200/60 space-y-2">
              <div className="flex items-center justify-between">
                <label className="text-xs font-bold text-slate-800">
                  Tope de Descuento Sin Autorización
                </label>
                <span className="text-xs font-mono font-bold text-slate-900 bg-white px-2 py-0.5 rounded border border-slate-200">
                  {descuentoMaximo}%
                </span>
              </div>
              <input
                type="range"
                min="2"
                max="20"
                step="0.5"
                value={descuentoMaximo}
                onChange={(e) => setDescuentoMaximo(parseFloat(e.target.value))}
                className="w-full accent-slate-900 cursor-pointer"
              />
              <span className="text-[11px] text-slate-400 block">
                Política COM-POL-002: desvío mayor requiere aprobación previa.
              </span>
            </div>
          </div>
        </div>

        {/* 2. Matriz de Autonomía de IA */}
        <div className="bg-white p-6 rounded-3xl border border-slate-200/70 shadow-card space-y-5">
          <div className="flex items-center justify-between border-b border-slate-100 pb-3">
            <div>
              <h3 className="text-sm font-bold text-slate-900">
                2. Niveles de Autonomía de los Agentes (Gobernanza)
              </h3>
              <p className="text-xs text-slate-400">
                En el MVP todas las acciones operacionales están protegidas en modo <strong>Propone (HITL)</strong>
              </p>
            </div>
            <div className="flex items-center gap-1 text-[11px] font-semibold text-purple-700 bg-purple-50 px-2.5 py-1 rounded-full border border-purple-200">
              <Lock className="w-3 h-3" />
              Human-in-the-Loop Activo
            </div>
          </div>

          <div className="space-y-4">
            {/* Ajuste de Precios */}
            <div className="p-4 rounded-2xl bg-slate-50 border border-slate-200/60 flex flex-col sm:flex-row sm:items-center justify-between gap-3">
              <div>
                <span className="text-xs font-bold text-slate-800 block">
                  Ajuste de Precios de Venta (Líneas y SKUs)
                </span>
                <span className="text-[11px] text-slate-500">
                  Responsable: Carlos Mendoza (Gerente Comercial)
                </span>
              </div>
              <div className="flex items-center gap-1 bg-white p-1 rounded-xl border border-slate-200 shadow-2xs">
                {(['informa', 'propone', 'ejecuta'] as const).map((nivel) => (
                  <button
                    key={nivel}
                    type="button"
                    onClick={() => setAutonomiaAjustePrecio(nivel)}
                    className={`px-3 py-1.5 rounded-lg text-xs font-medium capitalize cursor-pointer transition-all ${
                      autonomiaAjustePrecio === nivel
                        ? 'bg-slate-900 text-white'
                        : 'text-slate-600 hover:bg-slate-100'
                    }`}
                  >
                    {nivel}
                  </button>
                ))}
              </div>
            </div>

            {/* Cobro de Cartera */}
            <div className="p-4 rounded-2xl bg-slate-50 border border-slate-200/60 flex flex-col sm:flex-row sm:items-center justify-between gap-3">
              <div>
                <span className="text-xs font-bold text-slate-800 block">
                  Gestión de Cobro y Suspensión de Crédito
                </span>
                <span className="text-[11px] text-slate-500">
                  Responsable: Ana Restrepo (Directora de Cartera)
                </span>
              </div>
              <div className="flex items-center gap-1 bg-white p-1 rounded-xl border border-slate-200 shadow-2xs">
                {(['informa', 'propone', 'ejecuta'] as const).map((nivel) => (
                  <button
                    key={nivel}
                    type="button"
                    onClick={() => setAutonomiaCartera(nivel)}
                    className={`px-3 py-1.5 rounded-lg text-xs font-medium capitalize cursor-pointer transition-all ${
                      autonomiaCartera === nivel
                        ? 'bg-slate-900 text-white'
                        : 'text-slate-600 hover:bg-slate-100'
                    }`}
                  >
                    {nivel}
                  </button>
                ))}
              </div>
            </div>

            {/* Expedición de Órdenes */}
            <div className="p-4 rounded-2xl bg-slate-50 border border-slate-200/60 flex flex-col sm:flex-row sm:items-center justify-between gap-3">
              <div>
                <span className="text-xs font-bold text-slate-800 block">
                  Expedición y Reordenamiento de Compras
                </span>
                <span className="text-[11px] text-slate-500">
                  Responsable: David Osorio (Líder de Abastecimiento)
                </span>
              </div>
              <div className="flex items-center gap-1 bg-white p-1 rounded-xl border border-slate-200 shadow-2xs">
                {(['informa', 'propone', 'ejecuta'] as const).map((nivel) => (
                  <button
                    key={nivel}
                    type="button"
                    onClick={() => setAutonomiaOrdenes(nivel)}
                    className={`px-3 py-1.5 rounded-lg text-xs font-medium capitalize cursor-pointer transition-all ${
                      autonomiaOrdenes === nivel
                        ? 'bg-slate-900 text-white'
                        : 'text-slate-600 hover:bg-slate-100'
                    }`}
                  >
                    {nivel}
                  </button>
                ))}
              </div>
            </div>
          </div>
        </div>

        {/* Botón Guardar */}
        <div className="flex items-center justify-end gap-3">
          {guardadoExitoso && (
            <span className="text-xs font-medium text-emerald-600 flex items-center gap-1 animate-in fade-in">
              <CheckCircle2 className="w-4 h-4" />
              Configuración guardada en centinela_config
            </span>
          )}
          <button
            type="submit"
            className="px-5 py-2.5 rounded-2xl bg-slate-900 text-white text-xs font-bold hover:bg-slate-800 active:scale-95 transition-all shadow-xs flex items-center gap-2 cursor-pointer"
          >
            <Save className="w-4 h-4" />
            Guardar Configuración
          </button>
        </div>
      </form>
    </div>
  );
};
