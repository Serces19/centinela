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
  Filter,
  Flame,
  Info,
  Layers,
  Loader2,
  Play,
  RotateCcw,
  Search,
  ShieldAlert,
  Sparkles,
  TrendingDown,
  XCircle,
} from 'lucide-react';
import { AlertaVista, EstadoAlerta, Kpi, Severidad } from '../types';
import { formatCOP, formatCOPSimple, formatFecha } from '../utils/formatters';

interface Props {
  alertas: AlertaVista[];
  loading: boolean;
  onSelectAlerta: (alertaVista: AlertaVista) => void;
  onProcesarAlerta: (alertaId: string) => Promise<void>;
  onAbrirDecision: (alertaVista: AlertaVista, accion: 'aprobar' | 'editar' | 'rechazar') => void;
  onVerBitacora: (alertaId: string) => void;
  procesandoIds: Set<string>;
}

export const BandejaDecisiones: React.FC<Props> = ({
  alertas,
  loading,
  onSelectAlerta,
  onProcesarAlerta,
  onAbrirDecision,
  onVerBitacora,
  procesandoIds,
}) => {
  const [filtroSeveridad, setFiltroSeveridad] = useState<string>('todas');
  const [filtroEstado, setFiltroEstado] = useState<string>('pendientes');
  const [busqueda, setBusqueda] = useState<string>('');

  // Título amigable de negocio según el KPI
  const getTituloNegocio = (kpi: Kpi, entidadNombre?: string): string => {
    switch (kpi) {
      case 'margen_pct':
        return `Caída crítica de margen por incremento de costo de proveedor`;
      case 'saldo_vencido':
        return `Riesgo de cartera con mora prolongada sobre el cupo autorizado`;
      case 'dias_pago_prom':
        return `Deterioro severo en plazo promedio de cobro de cartera`;
      case 'cobertura_dias':
        return `Riesgo de quiebre de inventario inminente para demanda habitual`;
      case 'descuento_en_exceso':
        return `Descuentos aplicados por encima del margen de política comercial`;
      case 'veces_intervalo_habitual':
        return `Inactividad prolongada y riesgo de fuga de cliente estratégico`;
      case 'venta_bajo_costo':
        return `Detección de ventas por debajo del costo unitario reposición`;
      default:
        return `Desviación operacional detectada en parámetros de negocio`;
    }
  };

  // Cálculo del valor en 30 segundos (Hero)
  const dineroTotalEnRiesgo = alertas.reduce(
    (acc, item) => acc + (item.alerta.dinero_en_riesgo_cop || 0),
    0
  );

  const pendientesCount = alertas.filter(
    (item) =>
      item.alerta.estado === 'propuesta' ||
      item.alerta.estado === 'nueva' ||
      item.alerta.estado === 'en_analisis'
  ).length;

  const criticasCount = alertas.filter(
    (item) => item.alerta.severidad === 'critica'
  ).length;

  // Filtrado y ordenamiento de alertas
  const alertasFiltradas = alertas
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
          <span className="inline-flex items-center gap-1 text-[11px] font-semibold px-2 py-0.5 rounded-md bg-amber-50 text-amber-700 border border-amber-200">
            <Sparkles className="w-3 h-3 text-amber-500" />
            Propuesta Lista
          </span>
        );
      case 'nueva':
        return (
          <span className="inline-flex items-center gap-1 text-[11px] font-medium px-2 py-0.5 rounded-md bg-slate-100 text-slate-600 border border-slate-200">
            <Clock className="w-3 h-3" />
            Detectada por Vigía
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
      {/* 1. Hero: Valor en 30 Segundos */}
      <section className="bg-white rounded-3xl p-6 border border-slate-200/70 shadow-card relative overflow-hidden">
        <div className="absolute top-0 right-0 w-80 h-80 bg-gradient-to-bl from-rose-50/50 via-amber-50/20 to-transparent rounded-full -mr-20 -mt-20 pointer-events-none" />

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
            </div>
            <h2 className="text-3xl font-extrabold tracking-tight text-slate-900">
              {formatCOP(dineroTotalEnRiesgo)}
            </h2>
            <p className="text-sm text-slate-500 max-w-xl">
              Capital total en riesgo identificado en las operaciones de Distribuidora Andina.
              Hay <strong className="text-slate-800">{pendientesCount} decisiones pendientes</strong>{' '}
              de aprobación ejecutiva hoy.
            </p>
          </div>

          <div className="grid grid-cols-2 sm:grid-cols-3 gap-3">
            <div className="p-3.5 rounded-2xl bg-slate-50 border border-slate-200/60">
              <span className="text-[11px] text-slate-400 font-medium block">Decisiones Pendientes</span>
              <span className="text-2xl font-bold text-slate-900">{pendientesCount}</span>
            </div>
            <div className="p-3.5 rounded-2xl bg-rose-50/60 border border-rose-100">
              <span className="text-[11px] text-rose-600 font-medium block">Alertas Críticas</span>
              <span className="text-2xl font-bold text-rose-700">{criticasCount}</span>
            </div>
            <div className="p-3.5 rounded-2xl bg-emerald-50/60 border border-emerald-100 col-span-2 sm:col-span-1">
              <span className="text-[11px] text-emerald-700 font-medium block">Tasa de Aprobación</span>
              <span className="text-2xl font-bold text-emerald-800">100%</span>
            </div>
          </div>
        </div>
      </section>

      {/* 2. Barra de Filtros y Búsqueda */}
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

      {/* 3. Lista de Tarjetas de Alerta Priorizadas */}
      {loading && alertas.length === 0 ? (
        <div className="p-16 text-center bg-white rounded-3xl border border-slate-200/60 shadow-xs flex flex-col items-center justify-center gap-3">
          <Loader2 className="w-8 h-8 animate-spin text-slate-400" />
          <p className="text-sm text-slate-500 font-medium">Consultando alertas operacionales del Vigía...</p>
        </div>
      ) : alertasFiltradas.length === 0 ? (
        <div className="p-16 text-center bg-white rounded-3xl border border-slate-200/60 shadow-xs space-y-2">
          <CheckCircle2 className="w-10 h-10 text-emerald-500 mx-auto" />
          <h3 className="text-base font-semibold text-slate-800">
            No hay alertas que coincidan con los filtros
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

            // Resolución del nombre principal
            const entidadesKeys = Object.keys(item.nombres_resueltos);
            const entidadPrincipalId = entidadesKeys[0] || (primerHallazgo?.entidades[0]?.id || 'Operación');
            const entidadPrincipalNombre =
              item.nombres_resueltos[entidadPrincipalId] || entidadPrincipalId;

            const tituloNegocio = primerHallazgo
              ? getTituloNegocio(primerHallazgo.kpi, entidadPrincipalNombre)
              : 'Alerta Operacional';

            return (
              <div
                key={alerta.alerta_id}
                className="bg-white rounded-2xl sm:rounded-3xl p-5 border border-slate-200/70 hover:border-slate-300 hover:shadow-card-hover transition-all duration-200 group flex flex-col lg:flex-row lg:items-center justify-between gap-5"
              >
                {/* Lado izquierdo: Metadatos, título, entidad y propuesta */}
                <div className="space-y-3 flex-1">
                  {/* Fila superior de badges */}
                  <div className="flex flex-wrap items-center gap-2">
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
                      <span>{tituloNegocio}</span>
                      <ArrowUpRight className="w-4 h-4 opacity-0 group-hover:opacity-100 transition-opacity text-blue-500" />
                    </h3>

                    {/* Entidad afectada resuelta */}
                    <div className="flex items-center gap-2 mt-1 text-xs text-slate-600">
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

                  {/* Resumen o propuesta del Estratega si existe */}
                  {tienePropuesta && item.propuesta && (
                    <div className="p-3 rounded-2xl bg-amber-50/50 border border-amber-100/80 text-xs text-amber-950 flex items-start gap-2.5">
                      <Sparkles className="w-4 h-4 text-amber-600 shrink-0 mt-0.5" />
                      <div>
                        <strong className="font-semibold text-amber-900 block mb-0.5">
                          Propuesta de Acción ({item.propuesta.acciones[0]?.titulo || 'Acción Correctiva'}):
                        </strong>
                        <p className="text-slate-700 leading-relaxed">
                          {item.propuesta.diagnostico.resumen}
                        </p>
                      </div>
                    </div>
                  )}

                  {alerta.estado === 'nueva' && (
                    <p className="text-xs text-slate-500 italic">
                      Hallazgo detectado por el Vigía. Requiere análisis por el Analista y Estratega.
                    </p>
                  )}
                </div>

                {/* Lado derecho: Dinero en riesgo, confianza y acciones rápidas */}
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
                      <div className="text-[11px] font-medium text-emerald-600">
                        Confianza: {(item.propuesta.diagnostico.confianza * 100).toFixed(0)}%
                      </div>
                    )}
                  </div>

                  {/* Botonera de acciones */}
                  <div className="flex items-center gap-1.5">
                    {/* Botón Examinar Causa (siempre disponible) */}
                    <button
                      onClick={() => onSelectAlerta(item)}
                      className="px-3 py-2 rounded-xl text-xs font-medium text-slate-700 bg-slate-100/90 hover:bg-slate-200 transition-all cursor-pointer"
                      title="Abrir detalle en 3 niveles"
                    >
                      Examinar Causa
                    </button>

                    {/* Alerta Nueva: Analizar */}
                    {alerta.estado === 'nueva' && (
                      <button
                        onClick={() => onProcesarAlerta(alerta.alerta_id)}
                        disabled={estaProcesando}
                        className="px-3.5 py-2 rounded-xl text-xs font-semibold text-white bg-slate-900 hover:bg-slate-800 active:scale-95 transition-all shadow-xs flex items-center gap-1.5 cursor-pointer disabled:opacity-50"
                      >
                        {estaProcesando ? (
                          <>
                            <Loader2 className="w-3.5 h-3.5 animate-spin" />
                            <span>Analizando...</span>
                          </>
                        ) : (
                          <>
                            <Play className="w-3.5 h-3.5" />
                            <span>Analizar con Agentes</span>
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

                    {/* Alerta con Propuesta: Acciones HITL */}
                    {tienePropuesta && (
                      <>
                        <button
                          onClick={() => onAbrirDecision(item, 'aprobar')}
                          className="px-3 py-2 rounded-xl text-xs font-semibold text-emerald-700 bg-emerald-50 hover:bg-emerald-100 border border-emerald-200/80 active:scale-95 transition-all flex items-center gap-1 cursor-pointer"
                          title="Aprobar propuesta a 1 clic"
                        >
                          <Check className="w-3.5 h-3.5" />
                          Aprobar
                        </button>

                        <button
                          onClick={() => onAbrirDecision(item, 'editar')}
                          className="px-2.5 py-2 rounded-xl text-xs font-medium text-amber-700 bg-amber-50 hover:bg-amber-100 border border-amber-200/80 active:scale-95 transition-all flex items-center gap-1 cursor-pointer"
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
                        title="Ver registro en la bitácora inmutable"
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
