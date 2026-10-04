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

  const sinDatosEstrategicos = vistaPrincipal === 'estrategicas' && esCorteInicial;
  const dineroMostrado = sinDatosEstrategicos ? 0 : dineroTotalEnRiesgo;
  const pendientesMostrados = sinDatosEstrategicos ? 0 : pendientesCount;
  const criticasMostradas = sinDatosEstrategicos ? 0 : criticasCount;
  const ejecutadasCount = alertasActivas.filter(
    (i) => i.alerta.estado === 'aprobada' || i.alerta.estado === 'ejecutada'
  ).length;
  const resueltasCount =
    ejecutadasCount + alertasActivas.filter((i) => i.alerta.estado === 'rechazada').length;
  const progresoResolucion =
    alertasActivas.length > 0 ? (resueltasCount / alertasActivas.length) * 100 : 0;

  // Actividad reciente: las últimas alertas por corte de creación (datos reales de la API)
  const actividadReciente = [...alertas]
    .sort((a, b) => b.alerta.corte_creacion.localeCompare(a.alerta.corte_creacion))
    .slice(0, 6);

  return (
    <div className="grid grid-cols-1 xl:grid-cols-[minmax(0,1fr)_320px] gap-6 items-start">
      <div className="space-y-5 min-w-0">
      {/* 1. Selector de vista */}
      <div className="inline-flex items-center gap-1 p-1 rounded-full glass max-w-full no-scrollbar overflow-x-auto">
        {[
          {
            id: 'estrategicas' as const,
            label: 'Estratégicas',
            icon: Sparkles,
            count: alertasEstrategicas.length,
            title: 'Filtro de alto impacto · escenarios del reto S1-S6',
          },
          {
            id: 'operativa' as const,
            label: 'Auditoría operativa',
            icon: Layers,
            count: alertasOperativas.length,
            title: 'Registro determinista completo (DuckDB)',
          },
        ].map((v) => {
          const activo = vistaPrincipal === v.id;
          const Icon = v.icon;
          return (
            <button
              key={v.id}
              onClick={() => setVistaPrincipal(v.id)}
              title={v.title}
              className={`flex items-center gap-2 h-10 px-4 rounded-full text-xs font-semibold transition-all cursor-pointer whitespace-nowrap ${
                activo ? 'bg-slate-900 text-white shadow-float' : 'text-slate-600 hover:bg-white'
              }`}
            >
              <Icon className={`w-3.5 h-3.5 ${activo ? 'text-lime' : 'text-slate-400'}`} />
              <span>{v.label}</span>
              <span
                className={`text-[10px] px-2 py-0.5 rounded-full font-bold ${
                  activo ? 'bg-lime text-lime-ink' : 'bg-slate-200/70 text-slate-600'
                }`}
              >
                {v.count}
              </span>
            </button>
          );
        })}
      </div>

      {/* 2. Resumen: valor operacional en 30 segundos */}
      <section className="glass rounded-4xl p-5 sm:p-6 space-y-5">
        <div className="flex flex-wrap items-start justify-between gap-3">
          <div>
            <div className="section-eyebrow">Valor operacional en 30 segundos</div>
            <div className="mt-1 text-4xl sm:text-5xl font-semibold tracking-tight text-slate-900">
              {formatCOP(dineroMostrado)}
            </div>
            <p className="text-sm text-slate-500 mt-1.5 max-w-xl">
              {vistaPrincipal === 'estrategicas' ? (
                esCorteInicial ? (
                  'Operación en estado óptimo al corte inicial (18 Jun 2026): margen, cobertura y cartera dentro de los umbrales de política.'
                ) : (
                  <>
                    Capital en riesgo en las decisiones prioritarias de Distribuidora Andina.{' '}
                    <strong className="text-slate-800">{pendientesCount} pendientes</strong> de aprobación.
                  </>
                )
              ) : (
                `Auditoría de cartera rutinaria y seguimiento continuo (${alertasOperativas.length} registros en DuckDB).`
              )}
            </p>
          </div>
          <span className="inline-flex items-center gap-2 h-8 px-3 rounded-full bg-white/80 border border-white text-[11px] font-semibold text-emerald-700">
            <span className="relative flex w-2 h-2">
              <span className="absolute inset-0 rounded-full bg-emerald-500 animate-ping opacity-60" />
              <span className="relative w-2 h-2 rounded-full bg-emerald-500" />
            </span>
            Vigilancia activa
          </span>
        </div>

        {/* Mosaicos pastel */}
        <div className="grid grid-cols-1 sm:grid-cols-3 gap-3">
          <div className="rounded-3xl bg-lime p-4 flex sm:flex-col items-center sm:items-stretch justify-between sm:min-h-[112px]">
            <div className="text-xs font-semibold text-lime-ink leading-tight">Decisiones pendientes</div>
            <div className="text-4xl font-semibold text-slate-900 tracking-tight sm:self-end">
              {pendientesMostrados}
            </div>
          </div>
          <div className="rounded-3xl bg-aqua p-4 flex sm:flex-col items-center sm:items-stretch justify-between sm:min-h-[112px]">
            <div className="text-xs font-semibold text-aqua-ink leading-tight">Acciones ejecutadas</div>
            <div className="text-4xl font-semibold text-slate-900 tracking-tight sm:self-end">
              {ejecutadasCount}
            </div>
          </div>
          <div className="rounded-3xl bg-blush p-4 flex sm:flex-col items-center sm:items-stretch justify-between sm:min-h-[112px]">
            <div className="text-xs font-semibold text-blush-ink leading-tight">Alertas críticas</div>
            <div className="text-4xl font-semibold text-slate-900 tracking-tight sm:self-end">
              {criticasMostradas}
            </div>
          </div>
        </div>

        {/* Progreso de resolución */}
        <div>
          <div className="flex items-center justify-between text-[11px] font-medium text-slate-500 mb-1.5">
            <span>
              Resueltas {resueltasCount} de {alertasActivas.length}
            </span>
            <span>{progresoResolucion.toFixed(0)}%</span>
          </div>
          <div className="h-2 rounded-full bg-white/80 overflow-hidden">
            <div
              className="h-full bg-gradient-to-r from-aqua to-emerald-400 rounded-full transition-all duration-700"
              style={{ width: `${progresoResolucion}%` }}
            />
          </div>
        </div>
      </section>

      {/* 3. Banner de acción: analizar corte con IA */}
      {vistaPrincipal === 'estrategicas' && !esCorteInicial && alertasEstrategicas.length > 0 && (
        <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4 p-4 sm:p-5 rounded-4xl bg-slate-900 text-white shadow-float">
          <div className="flex items-center gap-3.5">
            <div className="w-11 h-11 rounded-full bg-lime flex items-center justify-center shrink-0">
              <Sparkles className="w-5 h-5 text-slate-900" />
            </div>
            <div>
              <div className="flex flex-wrap items-center gap-2">
                <h4 className="text-sm font-semibold text-white">Decisiones prioritarias para la Gerencia</h4>
                <span className="text-[10px] font-bold px-2 py-0.5 rounded-full bg-white/10 text-lime">
                  {alertasEstrategicas.length} casos clave
                </span>
              </div>
              <p className="text-xs text-slate-300 mt-0.5">
                {nuevasEstrategicas.length > 0
                  ? `${nuevasEstrategicas.length} alerta(s) pendiente(s) de diagnóstico. Ejecuta el pipeline de agentes para generar las propuestas.`
                  : 'Todas las decisiones prioritarias ya tienen propuesta del Analista y el Estratega.'}
              </p>
            </div>
          </div>

          {nuevasEstrategicas.length > 0 && (
            <button
              onClick={handleAnalizarCorteIA}
              disabled={analizandoLote || procesandoIds.size > 0}
              className="h-11 px-5 rounded-full text-xs font-bold bg-lime text-slate-900 hover:brightness-95 active:scale-95 transition-all flex items-center justify-center gap-2 cursor-pointer disabled:opacity-50 shrink-0"
              title="Analizar todas las alertas estratégicas pendientes con el Analista y Estratega"
            >
              {analizandoLote ? (
                <>
                  <Loader2 className="w-4 h-4 animate-spin" />
                  <span>Diagnosticando {progresoLote}...</span>
                </>
              ) : (
                <>
                  <Sparkles className="w-4 h-4" />
                  <span>Analizar corte con IA ({nuevasEstrategicas.length})</span>
                </>
              )}
            </button>
          )}
        </div>
      )}

      {/* 4. Barra de Filtros y Búsqueda */}
      <div className="flex flex-col 2xl:flex-row items-stretch 2xl:items-center justify-between gap-3">
        {/* Pestañas de estado */}
        <div className="flex items-center gap-1 p-1 rounded-full glass overflow-x-auto">
          {[
            { id: 'pendientes', label: 'Pendientes' },
            { id: 'propuestas', label: 'Propuestas Listas' },
            { id: 'ejecutadas', label: 'Historial / Ejecutadas' },
            { id: 'todas', label: 'Todas' },
          ].map((tab) => (
            <button
              key={tab.id}
              onClick={() => setFiltroEstado(tab.id)}
              className={`h-9 px-3.5 rounded-full text-xs font-semibold whitespace-nowrap transition-all cursor-pointer ${
                filtroEstado === tab.id
                  ? 'bg-slate-900 text-white shadow-float'
                  : 'text-slate-600 hover:bg-white'
              }`}
            >
              {tab.label}
            </button>
          ))}
        </div>

        {/* Buscador y filtro severidad */}
        <div className="flex items-center gap-2 w-full sm:w-auto">
          <div className="relative flex-1 sm:flex-none">
            <Search className="w-4 h-4 text-slate-400 absolute left-3.5 top-1/2 -translate-y-1/2" />
            <input
              type="text"
              placeholder="Buscar por cliente, SKU o ID..."
              value={busqueda}
              onChange={(e) => setBusqueda(e.target.value)}
              className="pl-9 pr-4 h-11 text-xs rounded-full glass focus:outline-none focus:bg-white w-full sm:w-60 transition-all placeholder:text-slate-400"
            />
          </div>

          <select
            value={filtroSeveridad}
            onChange={(e) => setFiltroSeveridad(e.target.value)}
            className="text-xs h-11 px-4 rounded-full glass focus:outline-none text-slate-700 cursor-pointer"
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
        <div className="p-16 text-center glass rounded-4xl flex flex-col items-center justify-center gap-3">
          <Loader2 className="w-8 h-8 animate-spin text-slate-400" />
          <p className="text-sm text-slate-500 font-medium">Consultando alertas operacionales del Vigía...</p>
        </div>
      ) : vistaPrincipal === 'estrategicas' && (esCorteInicial || alertasEstrategicas.length === 0) ? (
        /* Estado Limpio Reasegurador en el Corte Inicial (18 Jun 2026) */
        <div className="p-10 sm:p-16 text-center glass rounded-4xl space-y-4">
          <div className="w-16 h-16 rounded-full bg-lime flex items-center justify-center mx-auto">
            <ShieldCheck className="w-8 h-8 text-lime-ink" />
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
                className="h-11 px-5 rounded-full text-xs font-bold text-white bg-slate-900 hover:bg-slate-800 active:scale-95 transition-all shadow-float inline-flex items-center gap-2 cursor-pointer"
              >
                <span>Avanzar al Hito S1 (15 Ago 2026)</span>
                <ChevronRight className="w-4 h-4 text-lime" />
              </button>
            )}

            <button
              onClick={() => setVistaPrincipal('operativa')}
              className="h-11 px-5 rounded-full text-xs font-semibold text-slate-700 bg-white/80 hover:bg-white border border-white transition-colors inline-flex items-center gap-1.5 cursor-pointer"
            >
              <span>Ver Auditoría Operativa Rutinaria ({alertasOperativas.length})</span>
            </button>
          </div>
        </div>
      ) : alertasFiltradas.length === 0 ? (
        <div className="p-16 text-center glass rounded-4xl space-y-2">
          <CheckCircle2 className="w-10 h-10 text-emerald-500 mx-auto" />
          <h3 className="text-base font-semibold text-slate-800">
            No hay alertas que coincidan con los filtros seleccionados
          </h3>
          <p className="text-xs text-slate-400 max-w-sm mx-auto">
            La operación se encuentra dentro de los parámetros de control definidos o no hay hallazgos para este criterio.
          </p>
        </div>
      ) : (
        <div className="space-y-4">
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
                className="glass-strong rounded-3xl sm:rounded-4xl p-5 sm:p-6 hover:shadow-card-hover hover:-translate-y-0.5 transition-all duration-200 group flex flex-col lg:flex-row lg:items-center justify-between gap-5"
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
                      className="text-lg font-semibold text-slate-900 hover:text-emerald-700 transition-colors cursor-pointer flex items-center gap-1.5"
                    >
                      <span className="line-clamp-2">{tituloNegocio}</span>
                      <ArrowUpRight className="w-4 h-4 opacity-0 group-hover:opacity-100 transition-opacity text-emerald-600 shrink-0" />
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
                    <div className="p-4 rounded-3xl bg-lime/45 border border-white text-xs text-slate-900 space-y-1.5">
                      <div className="flex items-center gap-2">
                        <Sparkles className="w-4 h-4 text-lime-ink shrink-0" />
                        <strong className="font-bold text-lime-ink text-xs">
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
                    <div className="p-3.5 rounded-3xl bg-white/70 border border-white text-xs text-slate-600 flex items-center gap-2">
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
                    <div className="text-2xl font-semibold tracking-tight text-slate-900">
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
                      className="h-10 px-4 rounded-full text-xs font-semibold text-slate-700 bg-white/80 border border-white hover:bg-white hover:shadow-card transition-all cursor-pointer"
                      title="Abrir detalle en 3 niveles de Centinela"
                    >
                      Examinar Causa
                    </button>

                    {/* Alerta Nueva: Diagnosticar con IA */}
                    {alerta.estado === 'nueva' && (
                      <button
                        onClick={() => onProcesarAlerta(alerta.alerta_id)}
                        disabled={estaProcesando}
                        className="h-10 px-4 rounded-full text-xs font-semibold text-white bg-slate-900 hover:bg-slate-800 active:scale-95 transition-all shadow-float flex items-center gap-1.5 cursor-pointer disabled:opacity-50"
                        title="Disparar pipeline de agentes (Vigía → Analista → Estratega)"
                      >
                        {estaProcesando ? (
                          <>
                            <Loader2 className="w-3.5 h-3.5 animate-spin" />
                            <span>Diagnosticando...</span>
                          </>
                        ) : (
                          <>
                            <Sparkles className="w-3.5 h-3.5 text-lime" />
                            <span>Diagnosticar con IA</span>
                          </>
                        )}
                      </button>
                    )}

                    {/* Alerta en análisis */}
                    {alerta.estado === 'en_analisis' && (
                      <div className="flex items-center gap-1.5 text-xs text-aqua-ink font-semibold h-10 px-4 bg-aqua-soft rounded-full">
                        <Loader2 className="w-3.5 h-3.5 animate-spin" />
                        <span>En análisis...</span>
                      </div>
                    )}

                    {/* Alerta con Propuesta Lista: Acciones HITL */}
                    {tienePropuesta && (
                      <>
                        <button
                          onClick={() => onAbrirDecision(item, 'aprobar')}
                          className="h-10 px-4 rounded-full text-xs font-bold text-slate-900 bg-lime hover:brightness-95 active:scale-95 transition-all flex items-center gap-1.5 cursor-pointer shadow-xs"
                          title="Aprobar propuesta a 1 clic y ejecutar en Sandbox"
                        >
                          <Check className="w-3.5 h-3.5" />
                          Aprobar
                        </button>

                        <button
                          onClick={() => onAbrirDecision(item, 'editar')}
                          className="h-10 px-3.5 rounded-full text-xs font-semibold text-slate-700 bg-white/80 hover:bg-white border border-white active:scale-95 transition-all flex items-center gap-1 cursor-pointer"
                          title="Editar parámetros de la propuesta"
                        >
                          <Edit3 className="w-3.5 h-3.5" />
                          Editar
                        </button>

                        <button
                          onClick={() => onAbrirDecision(item, 'rechazar')}
                          className="h-10 px-3.5 rounded-full text-xs font-medium text-slate-500 hover:text-blush-ink hover:bg-blush-soft border border-transparent active:scale-95 transition-all cursor-pointer"
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
                        className="h-10 px-4 rounded-full text-xs font-semibold text-slate-700 bg-white/80 hover:bg-white border border-white active:scale-95 transition-all flex items-center gap-1 cursor-pointer"
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

      {/* Columna derecha: actividad reciente (alertas reales ordenadas por corte) */}
      <aside className="glass rounded-4xl p-5 xl:sticky xl:top-4">
        <div className="flex items-center justify-between mb-4">
          <h3 className="text-base font-semibold text-slate-900">Actividad reciente</h3>
          <span className="text-[11px] font-semibold px-2 py-0.5 rounded-full bg-white/80 text-slate-500">
            {alertas.length} alertas
          </span>
        </div>

        {actividadReciente.length === 0 ? (
          <p className="text-xs text-slate-400 py-6 text-center">Aún no hay actividad en este corte.</p>
        ) : (
          <ol className="space-y-2.5">
            {actividadReciente.map((item) => {
              const al = item.alerta;
              const claveEntidad = Object.keys(item.nombres_resueltos)[0] || al.hallazgos[0]?.entidades[0]?.id;
              const nombre = (claveEntidad && item.nombres_resueltos[claveEntidad]) || claveEntidad || al.alerta_id;
              const tono =
                al.severidad === 'critica'
                  ? 'bg-blush text-blush-ink'
                  : al.severidad === 'alta'
                  ? 'bg-amber-100 text-amber-700'
                  : 'bg-aqua text-aqua-ink';
              return (
                <li key={al.alerta_id}>
                  <button
                    onClick={() => onSelectAlerta(item)}
                    className="w-full text-left p-3 rounded-3xl bg-white/75 border border-white hover:bg-white hover:shadow-card transition-all cursor-pointer flex items-center gap-3"
                  >
                    <span className={`w-10 h-10 rounded-full flex items-center justify-center shrink-0 ${tono}`}>
                      {al.estado === 'ejecutada' || al.estado === 'aprobada' ? (
                        <CheckCircle2 className="w-4 h-4" />
                      ) : al.estado === 'rechazada' ? (
                        <XCircle className="w-4 h-4" />
                      ) : al.estado === 'en_analisis' ? (
                        <Loader2 className="w-4 h-4 animate-spin" />
                      ) : (
                        <AlertTriangle className="w-4 h-4" />
                      )}
                    </span>
                    <span className="min-w-0 flex-1">
                      <span className="block text-[13px] font-semibold text-slate-900 truncate">{nombre}</span>
                      <span className="block text-[11px] text-slate-400 truncate">
                        <span className="font-mono">{al.alerta_id}</span> · {formatFecha(al.corte_creacion)}
                      </span>
                    </span>
                    <span className="text-right shrink-0">
                      <span className="block text-xs font-semibold text-slate-800">
                        {formatCOPSimple(al.dinero_en_riesgo_cop)}
                      </span>
                      <span className="block text-[10px] capitalize text-slate-400">
                        {al.estado.replace('_', ' ')}
                      </span>
                    </span>
                  </button>
                </li>
              );
            })}
          </ol>
        )}
      </aside>
    </div>
  );
};
