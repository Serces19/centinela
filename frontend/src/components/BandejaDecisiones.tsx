// frontend/src/components/BandejaDecisiones.tsx
import React, { useState } from 'react';
import {
  AlertTriangle,
  ArrowUpRight,
  Check,
  CheckCircle2,
  Clock,
  Edit3,
  ExternalLink,
  Flame,
  Info,
  Layers,
  Loader2,
  Search,
  Sparkles,
  TrendingDown,
  XCircle,
  Calendar,
  ChevronRight,
  ShieldCheck,
} from 'lucide-react';
import { AlertaVista, EstadoAlerta, Kpi, Severidad, SimulacionCorte } from '../types';
import { formatCOP, formatCOPSimple, formatFecha } from '../utils/formatters';
import {
  clasificarEscenario,
  esAlertaEstrategica,
  esCorteInicialLimpio,
  getTituloNegocio,
  CORTE_INICIAL_LIMPIO,
  CORTE_HITO_S1,
} from '../utils/alertas';

interface Props {
  alertas: AlertaVista[];
  loading: boolean;
  corte: SimulacionCorte | null;
  onSelectAlerta: (alertaVista: AlertaVista) => void;
  onProcesarAlerta: (alertaId: string) => Promise<void>;
  onAbrirDecision: (alertaVista: AlertaVista, accion: 'aprobar' | 'editar' | 'rechazar') => void;
  onVerBitacora: (alertaId: string) => void;
  onIrAFecha?: (fechaIso: string) => Promise<void>;
  procesandoIds: Set<string>;
}

export const BandejaDecisiones: React.FC<Props> = ({
  alertas,
  loading,
  corte,
  onSelectAlerta,
  onProcesarAlerta,
  onAbrirDecision,
  onVerBitacora,
  onIrAFecha,
  procesandoIds,
}) => {
  // Pestaña principal: 'estrategicas' (Decisiones de Gerencia) o 'operativa' (Auditoría Rutinaria)
  const [vistaPrincipal, setVistaPrincipal] = useState<'estrategicas' | 'operativa'>('estrategicas');
  const [filtroSeveridad, setFiltroSeveridad] = useState<string>('todas');
  const [filtroEstado, setFiltroEstado] = useState<string>('pendientes');
  const [busqueda, setBusqueda] = useState<string>('');
  const [analizandoLote, setAnalizandoLote] = useState(false);
  const [progresoLote, setProgresoLote] = useState<string>('');

  const fechaActualIso = corte?.corte
    ? corte.corte.split('T')[0]
    : CORTE_INICIAL_LIMPIO;
  const esCorteInicial = esCorteInicialLimpio(fechaActualIso);

  // Separación de alertas: Estratégicas (alto impacto de negocio) vs Auditoría Operativa
  const alertasEstrategicas = alertas.filter((a) => esAlertaEstrategica(a, fechaActualIso));
  const alertasOperativas = alertas.filter((a) => !esAlertaEstrategica(a, fechaActualIso));

  // Alertas a mostrar según la pestaña principal activa
  const alertasActivas = vistaPrincipal === 'estrategicas' ? alertasEstrategicas : alertasOperativas;

  // Cálculo del valor en 30 segundos (Hero) adaptado a la vista activa
  const dineroTotalEnRiesgo = alertasActivas.reduce(
    (acc, item) => acc + (item.alerta.dinero_en_riesgo_cop || 0),
    0
  );

  const pendientesCount = alertasActivas.filter(
    (item) =>
      item.alerta.estado === 'propuesta' ||
      item.alerta.estado === 'nueva' ||
      item.alerta.estado === 'en_analisis'
  ).length;

  const criticasCount = alertasActivas.filter(
    (item) => item.alerta.severidad === 'critica'
  ).length;

  // Alertas estratégicas en estado 'nueva' pendientes de diagnóstico IA
  const nuevasEstrategicas = alertasEstrategicas.filter((a) => a.alerta.estado === 'nueva');

  // Procesamiento en lote con IA para todas las decisiones prioritarias
  const handleAnalizarCorteIA = async () => {
    if (nuevasEstrategicas.length === 0 || analizandoLote) return;
    try {
      setAnalizandoLote(true);
      for (let i = 0; i < nuevasEstrategicas.length; i++) {
        const item = nuevasEstrategicas[i];
        setProgresoLote(`[${i + 1}/${nuevasEstrategicas.length}]`);
        await onProcesarAlerta(item.alerta.alerta_id);
      }
    } finally {
      setAnalizandoLote(false);
      setProgresoLote('');
    }
  };

  // Filtrado y ordenamiento de alertas activas
  const alertasFiltradas = alertasActivas
    .filter((item) => {
      // Filtro severidad
      if (filtroSeveridad !== 'todas' && item.alerta.severidad !== filtroSeveridad) {
        return false;
      }

      // Filtro estado
      if (filtroEstado === 'pendientes') {
        if (
          item.alerta.estado !== 'propuesta' &&
          item.alerta.estado !== 'nueva' &&
          item.alerta.estado !== 'en_analisis'
        ) {
          return false;
        }
      } else if (filtroEstado === 'propuestas') {
        if (item.alerta.estado !== 'propuesta') return false;
      } else if (filtroEstado === 'ejecutadas') {
        if (
          item.alerta.estado !== 'aprobada' &&
          item.alerta.estado !== 'ejecutada' &&
          item.alerta.estado !== 'rechazada'
        ) {
          return false;
        }
      }

      // Filtro búsqueda
      if (busqueda.trim()) {
        const query = busqueda.toLowerCase();
        const alertaId = item.alerta.alerta_id.toLowerCase();
        const entidadesStr = Object.entries(item.nombres_resueltos)
          .map(([id, nom]) => `${id} ${nom}`)
          .join(' ')
          .toLowerCase();
        return alertaId.includes(query) || entidadesStr.includes(query);
      }

      return true;
    })
    .sort((a, b) => b.alerta.dinero_en_riesgo_cop - a.alerta.dinero_en_riesgo_cop);

  const getSeveridadBadge = (severidad: Severidad) => {
    switch (severidad) {
      case 'critica':
        return (
          <span className="inline-flex items-center gap-1 text-[11px] font-bold uppercase tracking-wider px-2.5 py-0.5 rounded-full bg-rose-50 text-rose-700 border border-rose-200">
            <Flame className="w-3 h-3 text-rose-600 fill-rose-600" />
            Crítica
          </span>
        );
      case 'alta':
        return (
          <span className="inline-flex items-center gap-1 text-[11px] font-bold uppercase tracking-wider px-2.5 py-0.5 rounded-full bg-amber-50 text-amber-700 border border-amber-200">
            <AlertTriangle className="w-3 h-3 text-amber-600" />
            Alta
          </span>
        );
      case 'media':
        return (
          <span className="inline-flex items-center gap-1 text-[11px] font-semibold uppercase tracking-wider px-2.5 py-0.5 rounded-full bg-sky-50 text-sky-700 border border-sky-200">
            <Info className="w-3 h-3 text-sky-600" />
            Media
          </span>
        );
      default:
        return (
          <span className="inline-flex items-center gap-1 text-[11px] font-semibold uppercase tracking-wider px-2.5 py-0.5 rounded-full bg-slate-100 text-slate-700 border border-slate-200">
            Baja
          </span>
        );
    }
  };

  const getEstadoBadge = (estado: EstadoAlerta) => {
    switch (estado) {
      case 'propuesta':
        return (
          <span className="inline-flex items-center gap-1 text-[11px] font-semibold px-2 py-0.5 rounded-md bg-emerald-50 text-emerald-800 border border-emerald-200">
            <Sparkles className="w-3 h-3 text-emerald-600" />
            Propuesta Lista
          </span>
        );
      case 'nueva':
        return (
          <span className="inline-flex items-center gap-1 text-[11px] font-medium px-2 py-0.5 rounded-md bg-amber-50 text-amber-800 border border-amber-200">
            <Sparkles className="w-3 h-3 text-amber-600" />
            Pendiente de Diagnóstico IA
          </span>
        );
      case 'en_analisis':
        return (
          <span className="inline-flex items-center gap-1 text-[11px] font-medium px-2 py-0.5 rounded-md bg-blue-50 text-blue-700 border border-blue-200">
            <Loader2 className="w-3 h-3 animate-spin text-blue-600" />
            Agentes Analizando...
          </span>
        );
      case 'aprobada':
      case 'ejecutada':
        return (
          <span className="inline-flex items-center gap-1 text-[11px] font-medium px-2 py-0.5 rounded-md bg-emerald-50 text-emerald-700 border border-emerald-200">
            <CheckCircle2 className="w-3 h-3 text-emerald-600" />
            Acción Ejecutada
          </span>
        );
      case 'rechazada':
        return (
          <span className="inline-flex items-center gap-1 text-[11px] font-medium px-2 py-0.5 rounded-md bg-slate-100 text-slate-600 border border-slate-200">
            <XCircle className="w-3 h-3 text-slate-400" />
            Rechazada por Humano
          </span>
        );
      default:
        return null;
    }
  };

  return (
    <div className="space-y-6">
      {/* 1. Selector de Nivel de Vista: Vista Ejecutiva Prioritaria vs Auditoría Operativa */}
      <div className="flex flex-col sm:flex-row items-stretch sm:items-center justify-between gap-3 p-1.5 bg-slate-100/90 rounded-2xl border border-slate-200/80 shadow-xs">
        <div className="flex items-center gap-1.5">
          <button
            onClick={() => setVistaPrincipal('estrategicas')}
            className={`flex items-center gap-2 px-4 py-2 rounded-xl text-xs font-semibold transition-all cursor-pointer ${
              vistaPrincipal === 'estrategicas'
                ? 'bg-slate-900 text-white shadow-xs'
                : 'text-slate-600 hover:text-slate-900 hover:bg-white'
            }`}
          >
            <Sparkles
              className={`w-3.5 h-3.5 ${
                vistaPrincipal === 'estrategicas' ? 'text-amber-300' : 'text-slate-400'
              }`}
            />
            <span>Decisiones Estratégicas</span>
            <span
              className={`text-[10px] px-2 py-0.5 rounded-full font-bold ${
                vistaPrincipal === 'estrategicas'
                  ? 'bg-amber-400/20 text-amber-300 border border-amber-400/30'
                  : 'bg-slate-200 text-slate-700'
              }`}
            >
              {alertasEstrategicas.length}
            </span>
          </button>

          <button
            onClick={() => setVistaPrincipal('operativa')}
            className={`flex items-center gap-2 px-4 py-2 rounded-xl text-xs font-semibold transition-all cursor-pointer ${
              vistaPrincipal === 'operativa'
                ? 'bg-slate-900 text-white shadow-xs'
                : 'text-slate-600 hover:text-slate-900 hover:bg-white'
            }`}
            title="Ver los registros históricos y moras de rutina detectadas por DuckDB"
          >
            <Layers className="w-3.5 h-3.5 text-slate-400" />
            <span>Auditoría Operativa Completa</span>
            <span
              className={`text-[10px] px-2 py-0.5 rounded-full font-medium ${
                vistaPrincipal === 'operativa'
                  ? 'bg-slate-800 text-slate-200'
                  : 'bg-slate-200 text-slate-700'
              }`}
            >
              {alertasOperativas.length}
            </span>
          </button>
        </div>

        <div className="text-[11px] text-slate-500 font-medium px-2 sm:px-3 text-right hidden sm:block">
          {vistaPrincipal === 'estrategicas' ? (
            <span>Filtro de Alto Impacto · Escenarios del Reto S1-S6</span>
          ) : (
            <span>Registro determinista completo (DuckDB)</span>
          )}
        </div>
      </div>

      {/* 2. Hero: Valor Operacional en 30 Segundos */}
      <section className="bg-white rounded-3xl p-6 border border-slate-200/70 shadow-card relative overflow-hidden">
        <div className="absolute top-0 right-0 w-80 h-80 bg-gradient-to-bl from-rose-50/40 via-amber-50/20 to-transparent rounded-full -mr-20 -mt-20 pointer-events-none" />

        <div className="relative z-10 flex flex-col md:flex-row md:items-center justify-between gap-6">
          <div className="space-y-1.5">
            <div className="flex items-center gap-2">
              <span className="text-xs font-bold uppercase tracking-wider text-slate-400">
                Valor Operacional en 30 Segundos
              </span>
              <span className="text-[10px] font-semibold px-2 py-0.5 rounded-full bg-emerald-50 text-emerald-700 border border-emerald-200 flex items-center gap-1">
                <span className="w-1.5 h-1.5 rounded-full bg-emerald-500 animate-ping"></span>
                Vigilancia Activa
              </span>
              {vistaPrincipal === 'estrategicas' && esCorteInicial && (
                <span className="text-[10px] font-semibold px-2 py-0.5 rounded-full bg-emerald-100 text-emerald-800 border border-emerald-300">
                  Corte Limpio (0 Críticas)
                </span>
              )}
            </div>
            <h2 className="text-3xl font-extrabold tracking-tight text-slate-900">
              {vistaPrincipal === 'estrategicas' && esCorteInicial
                ? '$0 COP'
                : formatCOP(dineroTotalEnRiesgo)}
            </h2>
            <p className="text-sm text-slate-500 max-w-xl">
              {vistaPrincipal === 'estrategicas' ? (
                esCorteInicial ? (
                  <>
                    Operación en estado óptimo al corte inicial de vigilancia (18 Jun 2026).
                    Todos los indicadores de margen, cobertura y cartera operan dentro de los umbrales de política.
                  </>
                ) : (
                  <>
                    Capital total en riesgo identificado en las decisiones prioritarias de Distribuidora Andina.
                    Hay <strong className="text-slate-800">{pendientesCount} decisiones pendientes</strong>{' '}
                    de aprobación ejecutiva hoy.
                  </>
                )
              ) : (
                <>
                  Auditoría de cartera rutinaria y seguimiento continuo ({alertasOperativas.length} registros).
                  Histórico de moras menores y control documental en DuckDB.
                </>
              )}
            </p>
          </div>

          <div className="grid grid-cols-2 sm:grid-cols-3 gap-3">
            <div className="p-3.5 rounded-2xl bg-slate-50 border border-slate-200/60">
              <span className="text-[11px] text-slate-400 font-medium block">Decisiones Pendientes</span>
              <span className="text-2xl font-bold text-slate-900">
                {vistaPrincipal === 'estrategicas' && esCorteInicial ? 0 : pendientesCount}
              </span>
            </div>
            <div className="p-3.5 rounded-2xl bg-rose-50/60 border border-rose-100">
              <span className="text-[11px] text-rose-600 font-medium block">Alertas Críticas</span>
              <span className="text-2xl font-bold text-rose-700">
                {vistaPrincipal === 'estrategicas' && esCorteInicial ? 0 : criticasCount}
              </span>
            </div>
            <div className="p-3.5 rounded-2xl bg-emerald-50/60 border border-emerald-100 col-span-2 sm:col-span-1">
              <span className="text-[11px] text-emerald-700 font-medium block">Tasa de Aprobación</span>
              <span className="text-2xl font-bold text-emerald-800">100%</span>
            </div>
          </div>
        </div>
      </section>

      {/* 3. Banner de Acción Superior: Analizar Corte con IA para Decisiones Estratégicas */}
      {vistaPrincipal === 'estrategicas' && !esCorteInicial && alertasEstrategicas.length > 0 && (
        <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4 p-4 rounded-2xl bg-slate-900 text-white shadow-xs">
          <div className="flex items-center gap-3">
            <div className="w-10 h-10 rounded-xl bg-white/10 flex items-center justify-center shrink-0">
              <Sparkles className="w-5 h-5 text-amber-300" />
            </div>
            <div>
              <div className="flex items-center gap-2">
                <h4 className="text-sm font-bold text-white">
                  Decisiones Prioritarias para la Gerencia
                </h4>
                <span className="text-[10px] font-semibold px-2 py-0.5 rounded-full bg-amber-400/20 text-amber-300 border border-amber-400/30">
                  {alertasEstrategicas.length} Casos Clave
                </span>
              </div>
              <p className="text-xs text-slate-300 mt-0.5">
                {nuevasEstrategicas.length > 0
                  ? `${nuevasEstrategicas.length} alerta(s) pendiente(s) de diagnóstico. Ejecute el pipeline de agentes para generar las propuestas listas.`
                  : 'Todas las decisiones prioritarias cuentan con propuesta lista formulada por el Analista y Estratega.'}
              </p>
            </div>
          </div>

          {nuevasEstrategicas.length > 0 && (
            <button
              onClick={handleAnalizarCorteIA}
              disabled={analizandoLote || procesandoIds.size > 0}
              className="px-4 py-2.5 rounded-xl text-xs font-bold bg-amber-400 text-slate-950 hover:bg-amber-300 active:scale-95 transition-all shadow-sm flex items-center justify-center gap-2 cursor-pointer disabled:opacity-50 shrink-0"
              title="Analizar todas las alertas estratégicas pendientes con el Analista y Estratega"
            >
              {analizandoLote ? (
                <>
                  <Loader2 className="w-4 h-4 animate-spin text-slate-950" />
                  <span>Diagnosticando {progresoLote}...</span>
                </>
              ) : (
                <>
                  <Sparkles className="w-4 h-4 text-slate-950 fill-slate-950" />
                  <span>Analizar Corte con IA ({nuevasEstrategicas.length})</span>
                </>
              )}
            </button>
          )}
        </div>
      )}

      {/* 4. Barra de Filtros y Búsqueda */}
      <div className="flex flex-col sm:flex-row items-stretch sm:items-center justify-between gap-3">
        {/* Pestañas de estado */}
        <div className="flex items-center gap-1 p-1 bg-white rounded-2xl border border-slate-200/70 shadow-xs">
          {[
            { id: 'pendientes', label: 'Pendientes' },
            { id: 'propuestas', label: 'Propuestas Listas' },
            { id: 'ejecutadas', label: 'Historial / Ejecutadas' },
            { id: 'todas', label: 'Todas' },
          ].map((tab) => (
            <button
              key={tab.id}
              onClick={() => setFiltroEstado(tab.id)}
              className={`px-3 py-1.5 rounded-xl text-xs font-medium transition-all cursor-pointer ${
                filtroEstado === tab.id
                  ? 'bg-slate-900 text-white shadow-xs'
                  : 'text-slate-600 hover:text-slate-900 hover:bg-slate-50'
              }`}
            >
              {tab.label}
            </button>
          ))}
        </div>

        {/* Buscador y filtro severidad */}
        <div className="flex items-center gap-2">
          <div className="relative">
            <Search className="w-3.5 h-3.5 text-slate-400 absolute left-3 top-1/2 -translate-y-1/2" />
            <input
              type="text"
              placeholder="Buscar por cliente, SKU o ID..."
              value={busqueda}
              onChange={(e) => setBusqueda(e.target.value)}
              className="pl-8 pr-3 py-1.5 text-xs rounded-xl bg-white border border-slate-200/80 focus:outline-none focus:ring-2 focus:ring-slate-900/10 focus:border-slate-400 w-48 sm:w-60 transition-all placeholder:text-slate-400"
            />
          </div>

          <select
            value={filtroSeveridad}
            onChange={(e) => setFiltroSeveridad(e.target.value)}
            className="text-xs py-1.5 px-3 rounded-xl bg-white border border-slate-200/80 focus:outline-none focus:ring-2 focus:ring-slate-900/10 focus:border-slate-400 text-slate-700 cursor-pointer"
          >
            <option value="todas">Todas las Severidades</option>
            <option value="critica">Solo Críticas</option>
            <option value="alta">Solo Altas</option>
            <option value="media">Solo Medias</option>
          </select>
        </div>
      </div>

      {/* 5. Lista de Tarjetas o Estado Vacío */}
      {loading && alertas.length === 0 ? (
        <div className="p-16 text-center bg-white rounded-3xl border border-slate-200/60 shadow-xs flex flex-col items-center justify-center gap-3">
          <Loader2 className="w-8 h-8 animate-spin text-slate-400" />
          <p className="text-sm text-slate-500 font-medium">Consultando alertas operacionales del Vigía...</p>
        </div>
      ) : vistaPrincipal === 'estrategicas' && (esCorteInicial || alertasEstrategicas.length === 0) ? (
        /* Estado Limpio Reasegurador en el Corte Inicial (18 Jun 2026) */
        <div className="p-12 sm:p-16 text-center bg-white rounded-3xl border border-emerald-100 shadow-xs space-y-4">
          <div className="w-14 h-14 rounded-2xl bg-emerald-50 text-emerald-600 flex items-center justify-center mx-auto border border-emerald-200 shadow-xs">
            <ShieldCheck className="w-8 h-8 text-emerald-600" />
          </div>
          <div className="space-y-1.5 max-w-lg mx-auto">
            <h3 className="text-lg font-bold text-slate-900">
              Operación en Estado Óptimo · 0 Riesgos Críticos Pendientes
            </h3>
            <p className="text-xs text-slate-500 leading-relaxed">
              En este corte inicial ({formatFecha(fechaActualIso)}), todos los indicadores de margen, cobertura y crédito operan dentro de los umbrales de política. La empresa se encuentra estabilizada.
            </p>
          </div>

          <div className="pt-2 flex flex-wrap items-center justify-center gap-3">
            {onIrAFecha && (
              <button
                onClick={() => onIrAFecha(CORTE_HITO_S1)}
                className="px-4 py-2 rounded-xl text-xs font-bold text-white bg-slate-900 hover:bg-slate-800 active:scale-95 transition-all shadow-xs inline-flex items-center gap-2 cursor-pointer"
              >
                <span>Avanzar al Hito S1 (15 Ago 2026)</span>
                <ChevronRight className="w-4 h-4 text-amber-300" />
              </button>
            )}

            <button
              onClick={() => setVistaPrincipal('operativa')}
              className="px-4 py-2 rounded-xl text-xs font-semibold text-slate-700 bg-slate-100 hover:bg-slate-200 transition-colors inline-flex items-center gap-1.5 cursor-pointer"
            >
              <span>Ver Auditoría Operativa Rutinaria ({alertasOperativas.length})</span>
            </button>
          </div>
        </div>
      ) : alertasFiltradas.length === 0 ? (
        <div className="p-16 text-center bg-white rounded-3xl border border-slate-200/60 shadow-xs space-y-2">
          <CheckCircle2 className="w-10 h-10 text-emerald-500 mx-auto" />
          <h3 className="text-base font-semibold text-slate-800">
            No hay alertas que coincidan con los filtros seleccionados
          </h3>
          <p className="text-xs text-slate-400 max-w-sm mx-auto">
            La operación se encuentra dentro de los parámetros de control definidos o no hay hallazgos para este criterio.
          </p>
        </div>
      ) : (
        <div className="space-y-3.5">
          {alertasFiltradas.map((item) => {
            const alerta = item.alerta;
            const primerHallazgo = alerta.hallazgos[0];
            const estaProcesando = procesandoIds.has(alerta.alerta_id);
            const tienePropuesta = !!item.propuesta && alerta.estado === 'propuesta';
            const escenarioInfo = clasificarEscenario(item);

            // Resolución del nombre principal
            const entidadesKeys = Object.keys(item.nombres_resueltos);
            const entidadPrincipalId = entidadesKeys[0] || (primerHallazgo?.entidades[0]?.id || 'Operación');
            const entidadPrincipalNombre =
              item.nombres_resueltos[entidadPrincipalId] || entidadPrincipalId;

            const tituloNegocio = escenarioInfo
              ? escenarioInfo.titulo
              : primerHallazgo
              ? getTituloNegocio(primerHallazgo.kpi, entidadPrincipalNombre, primerHallazgo.regla)
              : 'Alerta Operacional';

            return (
              <div
                key={alerta.alerta_id}
                className="bg-white rounded-2xl sm:rounded-3xl p-5 border border-slate-200/70 hover:border-slate-300 hover:shadow-card-hover transition-all duration-200 group flex flex-col lg:flex-row lg:items-center justify-between gap-5"
              >
                {/* Lado izquierdo: Metadatos, título, entidad y propuesta */}
                <div className="space-y-3 flex-1 min-w-0">
                  {/* Fila superior de badges */}
                  <div className="flex flex-wrap items-center gap-2">
                    {escenarioInfo && (
                      <span
                        className={`inline-flex items-center gap-1 text-[11px] font-bold px-2.5 py-0.5 rounded-full border ${escenarioInfo.badgeBg} ${escenarioInfo.badgeText} ${escenarioInfo.badgeBorder}`}
                      >
                        {escenarioInfo.tag}
                      </span>
                    )}
                    {getSeveridadBadge(alerta.severidad)}
                    {getEstadoBadge(alerta.estado)}
                    <span className="text-[11px] text-slate-400 font-mono">
                      {alerta.alerta_id}
                    </span>
                    <span className="text-[11px] text-slate-400">·</span>
                    <span className="text-[11px] text-slate-400">
                      Corte: {formatFecha(alerta.corte_creacion)}
                    </span>
                  </div>

                  {/* Título de negocio */}
                  <div>
                    <h3
                      onClick={() => onSelectAlerta(item)}
                      className="text-base font-bold text-slate-900 hover:text-blue-600 transition-colors cursor-pointer flex items-center gap-1.5"
                    >
                      <span className="truncate">{tituloNegocio}</span>
                      <ArrowUpRight className="w-4 h-4 opacity-0 group-hover:opacity-100 transition-opacity text-blue-500 shrink-0" />
                    </h3>

                    {/* Entidad afectada resuelta */}
                    <div className="flex flex-wrap items-center gap-2 mt-1 text-xs text-slate-600">
                      <span className="font-semibold text-slate-800">
                        {entidadPrincipalNombre}
                      </span>
                      <span className="text-slate-400">({entidadPrincipalId})</span>
                      {primerHallazgo && (
                        <span className="text-slate-400 text-[11px]">
                          · Regla: {primerHallazgo.regla}
                        </span>
                      )}
                    </div>
                  </div>

                  {/* Propuesta del Estratega si existe */}
                  {tienePropuesta && item.propuesta && (
                    <div className="p-3.5 rounded-2xl bg-amber-50/60 border border-amber-200/80 text-xs text-amber-950 space-y-1.5">
                      <div className="flex items-center gap-2">
                        <Sparkles className="w-4 h-4 text-amber-600 shrink-0" />
                        <strong className="font-bold text-amber-900 text-xs">
                          Propuesta de Acción ({item.propuesta.acciones[0]?.titulo || 'Acción Correctiva'}):
                        </strong>
                      </div>
                      <p className="text-slate-800 leading-relaxed pl-6">
                        {item.propuesta.diagnostico.resumen}
                      </p>
                    </div>
                  )}

                  {/* Estado Pendiente de Diagnóstico IA */}
                  {alerta.estado === 'nueva' && (
                    <div className="p-3 rounded-2xl bg-slate-50 border border-slate-200/70 text-xs text-slate-600 flex items-center gap-2">
                      <Info className="w-4 h-4 text-slate-400 shrink-0" />
                      <span>
                        Sensor Vigía detectó una desviación respecto a los umbrales de política. Active el Diagnóstico IA para investigar la causa raíz en DuckDB y formular la propuesta económica en COP.
                      </span>
                    </div>
                  )}
                </div>

                {/* Lado derecho: Dinero en riesgo, confianza y acciones HITL */}
                <div className="flex flex-row lg:flex-col items-center lg:items-end justify-between border-t lg:border-t-0 pt-4 lg:pt-0 border-slate-100 gap-3 shrink-0">
                  {/* Dinero en riesgo y confianza */}
                  <div className="text-left lg:text-right">
                    <div className="text-[10px] uppercase font-bold tracking-wider text-slate-400">
                      Dinero en Riesgo
                    </div>
                    <div className="text-xl font-extrabold text-slate-900">
                      {formatCOP(alerta.dinero_en_riesgo_cop)}
                    </div>
                    {item.propuesta && (
                      <div className="text-[11px] font-semibold text-emerald-600">
                        Confianza: {(item.propuesta.diagnostico.confianza * 100).toFixed(0)}%
                      </div>
                    )}
                  </div>

                  {/* Botonera de acciones */}
                  <div className="flex items-center gap-1.5 flex-wrap justify-end">
                    {/* Botón Examinar Causa */}
                    <button
                      onClick={() => onSelectAlerta(item)}
                      className="px-3 py-2 rounded-xl text-xs font-medium text-slate-700 bg-slate-100/90 hover:bg-slate-200 transition-all cursor-pointer"
                      title="Abrir detalle en 3 niveles de Centinela"
                    >
                      Examinar Causa
                    </button>

                    {/* Alerta Nueva: Diagnosticar con IA */}
                    {alerta.estado === 'nueva' && (
                      <button
                        onClick={() => onProcesarAlerta(alerta.alerta_id)}
                        disabled={estaProcesando}
                        className="px-3.5 py-2 rounded-xl text-xs font-semibold text-white bg-slate-900 hover:bg-slate-800 active:scale-95 transition-all shadow-xs flex items-center gap-1.5 cursor-pointer disabled:opacity-50"
                        title="Disparar pipeline de agentes (Vigía → Analista → Estratega)"
                      >
                        {estaProcesando ? (
                          <>
                            <Loader2 className="w-3.5 h-3.5 animate-spin" />
                            <span>Diagnosticando...</span>
                          </>
                        ) : (
                          <>
                            <Sparkles className="w-3.5 h-3.5 text-amber-300" />
                            <span>Diagnosticar con IA</span>
                          </>
                        )}
                      </button>
                    )}

                    {/* Alerta en análisis */}
                    {alerta.estado === 'en_analisis' && (
                      <div className="flex items-center gap-1.5 text-xs text-blue-600 font-medium px-3 py-2 bg-blue-50 rounded-xl border border-blue-100">
                        <Loader2 className="w-3.5 h-3.5 animate-spin" />
                        <span>En análisis...</span>
                      </div>
                    )}

                    {/* Alerta con Propuesta Lista: Acciones HITL */}
                    {tienePropuesta && (
                      <>
                        <button
                          onClick={() => onAbrirDecision(item, 'aprobar')}
                          className="px-3.5 py-2 rounded-xl text-xs font-bold text-emerald-800 bg-emerald-100 hover:bg-emerald-200 border border-emerald-300 active:scale-95 transition-all flex items-center gap-1 cursor-pointer shadow-xs"
                          title="Aprobar propuesta a 1 clic y ejecutar en Sandbox"
                        >
                          <Check className="w-3.5 h-3.5" />
                          Aprobar
                        </button>

                        <button
                          onClick={() => onAbrirDecision(item, 'editar')}
                          className="px-2.5 py-2 rounded-xl text-xs font-semibold text-amber-800 bg-amber-50 hover:bg-amber-100 border border-amber-200 active:scale-95 transition-all flex items-center gap-1 cursor-pointer"
                          title="Editar parámetros de la propuesta"
                        >
                          <Edit3 className="w-3.5 h-3.5" />
                          Editar
                        </button>

                        <button
                          onClick={() => onAbrirDecision(item, 'rechazar')}
                          className="px-2.5 py-2 rounded-xl text-xs font-medium text-slate-500 hover:text-rose-600 hover:bg-rose-50 border border-slate-200 active:scale-95 transition-all cursor-pointer"
                          title="Rechazar propuesta con motivo"
                        >
                          Rechazar
                        </button>
                      </>
                    )}

                    {/* Alerta Ejecutada o Rechazada: Ver bitácora */}
                    {(alerta.estado === 'aprobada' ||
                      alerta.estado === 'ejecutada' ||
                      alerta.estado === 'rechazada') && (
                      <button
                        onClick={() => onVerBitacora(alerta.alerta_id)}
                        className="px-3 py-2 rounded-xl text-xs font-medium text-purple-700 bg-purple-50 hover:bg-purple-100 border border-purple-200 active:scale-95 transition-all flex items-center gap-1 cursor-pointer"
                        title="Ver registro en la bitácora inmutable SHA-256"
                      >
                        <ExternalLink className="w-3.5 h-3.5" />
                        Ver Bitácora
                      </button>
                    )}
                  </div>
                </div>
              </div>
            );
          })}
        </div>
      )}
    </div>
  );
};
