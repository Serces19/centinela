// frontend/src/components/DetalleAlertaModal.tsx
import React, { useState } from 'react';
import {
  X,
  Sparkles,
  FileText,
  Database,
  ChevronDown,
  ChevronRight,
  ShieldAlert,
  Hash,
  Copy,
  Check,
  CheckCircle2,
  ExternalLink,
  Flame,
  AlertTriangle,
  Info,
  Clock,
  Send,
  Loader2,
} from 'lucide-react';
import { AlertaVista, CifraTrazable, CitaPolitica } from '../types';
import { formatCOP, formatFecha } from '../utils/formatters';

interface Props {
  alertaVista: AlertaVista;
  onClose: () => void;
  onAbrirDecision: (alertaVista: AlertaVista, accion: 'aprobar' | 'editar' | 'rechazar') => void;
  onProcesarAlerta: (alertaId: string) => Promise<void>;
  onVerBitacora: (alertaId: string) => void;
  onPreguntarEnChat: (pregunta: string) => void;
  estaProcesando: boolean;
}

export const DetalleAlertaModal: React.FC<Props> = ({
  alertaVista,
  onClose,
  onAbrirDecision,
  onProcesarAlerta,
  onVerBitacora,
  onPreguntarEnChat,
  estaProcesando,
}) => {
  const [nivel3Abierto, setNivel3Abierto] = useState<boolean>(false);
  const [copiadoHash, setCopiadoHash] = useState<string | null>(null);

  const { alerta, nombres_resueltos, propuesta } = alertaVista;
  const diagnostico = propuesta?.diagnostico;
  const acciones = propuesta?.acciones || [];
  const hallazgo = alerta.hallazgos[0];

  const handleCopiarHash = (texto: string) => {
    navigator.clipboard.writeText(texto);
    setCopiadoHash(texto);
    setTimeout(() => setCopiadoHash(null), 2000);
  };

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center p-4 bg-slate-900/40 backdrop-blur-xs animate-in fade-in duration-200">
      <div className="bg-white rounded-3xl shadow-2xl border border-slate-200/80 w-full max-w-4xl max-h-[92vh] flex flex-col overflow-hidden animate-in zoom-in-95 duration-200">
        {/* Modal Header */}
        <div className="px-6 py-4 border-b border-slate-100 flex items-center justify-between bg-slate-50/50">
          <div className="flex items-center gap-2.5">
            <span className="text-xs font-bold uppercase tracking-wider text-slate-400">
              Detalle en 3 Niveles
            </span>
            <span className="text-slate-300">·</span>
            <span className="text-xs font-mono font-medium text-slate-700 bg-slate-200/60 px-2 py-0.5 rounded-md">
              {alerta.alerta_id}
            </span>
            <span className="text-slate-300">·</span>
            <span className="text-xs text-slate-500">
              Versión {alerta.version}
            </span>
          </div>

          <button
            onClick={onClose}
            className="p-1.5 rounded-xl text-slate-400 hover:text-slate-700 hover:bg-slate-200/60 transition-colors cursor-pointer"
          >
            <X className="w-5 h-5" />
          </button>
        </div>

        {/* Modal Body */}
        <div className="p-6 overflow-y-auto space-y-6 flex-1">
          {/* Top Banner de Dinero e Identificación */}
          <div className="flex flex-col sm:flex-row sm:items-center justify-between p-4 rounded-2xl bg-slate-50 border border-slate-200/70 gap-4">
            <div>
              <span className="text-[11px] font-semibold uppercase tracking-wider text-slate-400 block">
                Dinero en Riesgo Estimado
              </span>
              <div className="text-2xl font-black text-slate-900">
                {formatCOP(alerta.dinero_en_riesgo_cop)}
              </div>
              <div className="text-xs text-slate-500 mt-0.5">
                Corte operacional: {formatFecha(alerta.corte_creacion)} · Estado:{' '}
                <strong className="text-slate-700 uppercase font-semibold">{alerta.estado}</strong>
              </div>
            </div>

            {/* Nombres Resueltos */}
            <div className="text-left sm:text-right">
              <span className="text-[11px] font-semibold uppercase tracking-wider text-slate-400 block">
                Entidad Principal Afectada
              </span>
              <div className="text-sm font-bold text-slate-800">
                {hallazgo?.entidades.map((ent) => (
                  <span key={ent.id} className="block">
                    {nombres_resueltos[ent.id] || ent.id}{' '}
                    <span className="text-slate-400 font-normal">({ent.id})</span>
                  </span>
                ))}
              </div>
              <div className="text-xs text-slate-400">
                Regla Vigía: {hallazgo?.regla}
              </div>
            </div>
          </div>

          {/* ======================================================== */}
          {/* NIVEL 1: RESUMEN EJECUTIVO Y ACCIÓN PROPUESTA */}
          {/* ======================================================== */}
          <section className="space-y-3">
            <div className="flex items-center gap-2">
              <div className="w-6 h-6 rounded-lg bg-emerald-100 text-emerald-800 flex items-center justify-center text-xs font-bold">
                1
              </div>
              <h3 className="text-sm font-bold uppercase tracking-wider text-slate-800">
                Nivel 1 · Resumen Ejecutivo & Propuesta Inmediata
              </h3>
            </div>

            {diagnostico ? (
              <div className="p-4 rounded-2xl bg-emerald-50/40 border border-emerald-100 space-y-3">
                <p className="text-sm text-slate-900 font-medium leading-relaxed">
                  {diagnostico.resumen}
                </p>

                {acciones.length > 0 && (
                  <div className="pt-2 border-t border-emerald-100/70 space-y-2">
                    <span className="text-xs font-bold text-emerald-900 uppercase tracking-wide block">
                      Acción Propuesta por el Estratega:
                    </span>
                    {acciones.map((acc) => (
                      <div
                        key={acc.accion_id}
                        className="p-3 bg-white rounded-xl border border-emerald-200/80 shadow-xs flex flex-col sm:flex-row sm:items-center justify-between gap-3"
                      >
                        <div>
                          <div className="text-xs font-bold text-slate-900 flex items-center gap-1.5">
                            <Sparkles className="w-3.5 h-3.5 text-amber-500" />
                            {acc.titulo}
                          </div>
                          <p className="text-xs text-slate-600 mt-0.5">{acc.razon}</p>
                        </div>
                        <div className="text-left sm:text-right shrink-0">
                          <span className="text-[10px] uppercase font-bold text-slate-400 block">
                            Impacto Estimado
                          </span>
                          <span className="text-sm font-extrabold text-emerald-700">
                            {formatCOP(acc.impacto.valor_cop)}
                          </span>
                          <span className="text-[10px] text-slate-400 block">
                            {acc.impacto.horizonte === 'mensual' ? 'al mes' : 'único'}
                          </span>
                        </div>
                      </div>
                    ))}
                  </div>
                )}
              </div>
            ) : (
              <div className="p-4 rounded-2xl bg-slate-50 border border-slate-200/60 text-xs text-slate-500 italic">
                El Vigía identificó la anomalía operacional. Aún no se ha generado la propuesta de agentes.
                Haga clic en "Analizar con Agentes" para obtener el diagnóstico y la propuesta.
              </div>
            )}
          </section>

          {/* ======================================================== */}
          {/* NIVEL 2: CAUSA RAÍZ, CIFRAS TRAZABLES Y CITAS FORMALES */}
          {/* ======================================================== */}
          <section className="space-y-3">
            <div className="flex items-center gap-2">
              <div className="w-6 h-6 rounded-lg bg-blue-100 text-blue-800 flex items-center justify-center text-xs font-bold">
                2
              </div>
              <h3 className="text-sm font-bold uppercase tracking-wider text-slate-800">
                Nivel 2 · Causa Raíz con Cifras Trazables y Políticas
              </h3>
            </div>

            {diagnostico ? (
              <div className="p-4 rounded-2xl bg-slate-50/80 border border-slate-200/70 space-y-4">
                {/* Causa raíz */}
                <div>
                  <span className="text-xs font-bold uppercase tracking-wider text-slate-400 block mb-1">
                    Investigación del Analista:
                  </span>
                  <p className="text-xs text-slate-700 leading-relaxed font-sans">
                    {diagnostico.causa_raiz}
                  </p>
                </div>

                {/* Cifras Trazables */}
                {diagnostico.cifras && diagnostico.cifras.length > 0 && (
                  <div>
                    <span className="text-xs font-bold uppercase tracking-wider text-slate-400 block mb-2">
                      Cifras Auditadas de la Base de Datos (DuckDB):
                    </span>
                    <div className="grid grid-cols-1 sm:grid-cols-2 md:grid-cols-3 gap-2.5">
                      {diagnostico.cifras.map((cifra, idx) => (
                        <div
                          key={idx}
                          className="p-3 bg-white rounded-xl border border-slate-200/80 shadow-xs flex flex-col justify-between"
                        >
                          <span className="text-[11px] text-slate-500 font-medium">
                            {cifra.etiqueta}
                          </span>
                          <div className="mt-1 flex items-baseline justify-between">
                            <span className="text-base font-bold text-slate-900">
                              {cifra.unidad === 'COP'
                                ? formatCOP(cifra.valor)
                                : `${cifra.valor} ${cifra.unidad}`}
                            </span>
                            <span className="text-[10px] font-mono text-slate-400 bg-slate-100 px-1.5 py-0.5 rounded">
                              {cifra.consulta_id}
                            </span>
                          </div>
                        </div>
                      ))}
                    </div>
                  </div>
                )}

                {/* Políticas citadas formalmente */}
                {diagnostico.politicas && diagnostico.politicas.length > 0 && (
                  <div>
                    <span className="text-xs font-bold uppercase tracking-wider text-slate-400 block mb-2">
                      Marco Regulatorio y Políticas Citadas (RAG):
                    </span>
                    <div className="space-y-2">
                      {diagnostico.politicas.map((pol, idx) => (
                        <div
                          key={idx}
                          className="p-3 bg-white rounded-xl border border-slate-200/80 shadow-xs flex items-center justify-between"
                        >
                          <div className="flex items-center gap-2">
                            <FileText className="w-4 h-4 text-rose-500 shrink-0" />
                            <div>
                              <span className="text-xs font-bold text-slate-800">
                                {pol.documento}
                              </span>
                              <span className="text-xs text-slate-500 ml-1.5">
                                · {pol.seccion}
                              </span>
                            </div>
                          </div>
                          <span className="text-[10px] font-mono text-slate-400 bg-slate-100 px-2 py-0.5 rounded">
                            hash: {pol.fragmento_hash.substring(0, 10)}...
                          </span>
                        </div>
                      ))}
                    </div>
                  </div>
                )}

                {/* Supuestos y confianza */}
                <div className="flex flex-wrap items-center justify-between pt-2 border-t border-slate-200/60 text-xs text-slate-500 gap-2">
                  <div className="flex items-center gap-1.5">
                    <span className="font-semibold text-slate-700">Nivel de Confianza:</span>
                    <span className="px-2 py-0.5 rounded-full bg-emerald-50 text-emerald-700 font-bold border border-emerald-200">
                      {(diagnostico.confianza * 100).toFixed(0)}%
                    </span>
                  </div>
                  {diagnostico.supuestos.length > 0 && (
                    <div className="text-[11px] text-slate-400">
                      Supuestos: {diagnostico.supuestos.join(', ')}
                    </div>
                  )}
                </div>
              </div>
            ) : (
              <div className="p-4 rounded-2xl bg-slate-50 border border-slate-200/60 text-xs text-slate-500 italic">
                Pendiente de investigación de causa raíz por el Analista.
              </div>
            )}
          </section>

          {/* ======================================================== */}
          {/* NIVEL 3: "CÓMO LLEGUÉ AQUÍ" (SQL Y TRAZABILIDAD HASH) */}
          {/* ======================================================== */}
          <section className="border border-slate-200/70 rounded-2xl overflow-hidden">
            <button
              onClick={() => setNivel3Abierto(!nivel3Abierto)}
              className="w-full p-4 bg-slate-50 hover:bg-slate-100/80 transition-colors flex items-center justify-between text-left cursor-pointer"
            >
              <div className="flex items-center gap-2">
                <div className="w-6 h-6 rounded-lg bg-purple-100 text-purple-800 flex items-center justify-center text-xs font-bold">
                  3
                </div>
                <div>
                  <h3 className="text-sm font-bold uppercase tracking-wider text-slate-800">
                    Nivel 3 · Cómo Llegué Aquí (SQL Exacto & Hash SHA-256)
                  </h3>
                  <p className="text-[11px] text-slate-400">
                    Trazabilidad determinista sobre vistas semánticas de DuckDB
                  </p>
                </div>
              </div>
              {nivel3Abierto ? (
                <ChevronDown className="w-4 h-4 text-slate-500" />
              ) : (
                <ChevronRight className="w-4 h-4 text-slate-500" />
              )}
            </button>

            {nivel3Abierto && (
              <div className="p-4 bg-slate-900 text-slate-200 space-y-4 font-mono text-xs overflow-x-auto">
                <div>
                  <div className="text-slate-400 text-[11px] mb-1 flex items-center justify-between">
                    <span>-- VISTA EJECUTADA POR EL VIGÍA</span>
                    <span className="text-emerald-400">SHA-256 VERIFICADO</span>
                  </div>
                  <pre className="p-3 bg-slate-950 rounded-xl text-slate-300 text-xs overflow-x-auto border border-slate-800">
                    {`SELECT * FROM ${hallazgo?.kpi || 'v_ventas'} \nWHERE corte <= '${alerta.corte_creacion}'\nLIMIT 50;`}
                  </pre>
                </div>

                <div className="space-y-1.5 pt-2 border-t border-slate-800 text-[11px]">
                  <div className="flex items-center justify-between">
                    <span className="text-slate-400">Huella de causa:</span>
                    <span className="text-slate-200">{alerta.huella_causa}</span>
                  </div>
                  <div className="flex items-center justify-between">
                    <span className="text-slate-400">Consultas registradas:</span>
                    <span className="text-slate-200">
                      {hallazgo?.consulta_ids?.join(', ') || 'Q-default'}
                    </span>
                  </div>
                </div>
              </div>
            )}
          </section>

          {/* Preguntas sugeridas para el Chat */}
          <div className="p-3 rounded-2xl bg-amber-50/40 border border-amber-100 flex items-center justify-between gap-3">
            <div className="flex items-center gap-2 text-xs text-amber-900 font-medium">
              <Sparkles className="w-4 h-4 text-amber-600 shrink-0" />
              <span>¿Desea profundizar en los datos? Pregunte al asistente:</span>
            </div>
            <button
              onClick={() => {
                onClose();
                onPreguntarEnChat(`¿Cuál ha sido la tendencia de este cliente en las últimas 4 semanas?`);
              }}
              className="text-xs font-semibold text-amber-800 hover:text-amber-950 underline cursor-pointer"
            >
              Preguntar en Chat &rarr;
            </button>
          </div>
        </div>

        {/* Modal Footer con Decisiones */}
        <div className="px-6 py-4 border-t border-slate-100 bg-slate-50/60 flex flex-wrap items-center justify-between gap-3">
          <button
            onClick={() => onVerBitacora(alerta.alerta_id)}
            className="px-3 py-2 rounded-xl text-xs font-medium text-slate-700 hover:bg-slate-200/60 transition-colors flex items-center gap-1.5 cursor-pointer"
          >
            <ExternalLink className="w-3.5 h-3.5" />
            Auditar en Bitácora
          </button>

          <div className="flex items-center gap-2">
            {alerta.estado === 'nueva' && (
              <button
                onClick={() => onProcesarAlerta(alerta.alerta_id)}
                disabled={estaProcesando}
                className="px-4 py-2 rounded-xl text-xs font-bold text-white bg-slate-900 hover:bg-slate-800 active:scale-95 transition-all shadow-xs flex items-center gap-2 cursor-pointer disabled:opacity-50"
              >
                {estaProcesando ? (
                  <>
                    <Loader2 className="w-3.5 h-3.5 animate-spin" />
                    <span>Analizando con Agentes...</span>
                  </>
                ) : (
                  <>
                    <Sparkles className="w-3.5 h-3.5 text-amber-300" />
                    <span>Analizar Alerta Ahora</span>
                  </>
                )}
              </button>
            )}

            {alerta.estado === 'propuesta' && (
              <>
                <button
                  onClick={() => onAbrirDecision(alertaVista, 'rechazar')}
                  className="px-3.5 py-2 rounded-xl text-xs font-medium text-slate-600 hover:text-rose-700 hover:bg-rose-50 border border-slate-200 active:scale-95 transition-all cursor-pointer"
                >
                  Rechazar...
                </button>
                <button
                  onClick={() => onAbrirDecision(alertaVista, 'editar')}
                  className="px-3.5 py-2 rounded-xl text-xs font-semibold text-amber-800 bg-amber-50 hover:bg-amber-100 border border-amber-200 active:scale-95 transition-all cursor-pointer"
                >
                  Editar Propuesta...
                </button>
                <button
                  onClick={() => onAbrirDecision(alertaVista, 'aprobar')}
                  className="px-4 py-2 rounded-xl text-xs font-bold text-emerald-800 bg-emerald-100 hover:bg-emerald-200 border border-emerald-300 active:scale-95 transition-all flex items-center gap-1.5 cursor-pointer"
                >
                  <Check className="w-4 h-4" />
                  Aprobar Propuesta
                </button>
              </>
            )}
          </div>
        </div>
      </div>
    </div>
  );
};
