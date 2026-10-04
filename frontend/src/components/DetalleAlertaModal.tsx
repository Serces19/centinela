// frontend/src/components/DetalleAlertaModal.tsx
import React, { useEffect, useMemo, useRef, useState } from 'react';
import {
  Check,
  ChevronDown,
  ChevronRight,
  Copy,
  ExternalLink,
  FileText,
  History,
  Loader2,
  RotateCcw,
  Sparkles,
  X,
} from 'lucide-react';
import { AlertaVista, ConsultaRegistrada } from '../types';
import { getConsulta } from '../api/client';
import { formatCOP, formatFecha } from '../utils/formatters';
import { ESTILO_SEVERIDAD, ETIQUETA_ESTADO, ETIQUETA_PASO, ETIQUETA_SEVERIDAD, tituloAlerta } from '../utils/alertas';
import { TextoConCifras, formatCifra } from '../utils/texto';

interface Props {
  alertaVista: AlertaVista;
  consultaFoco?: string;
  onClose: () => void;
  onAbrirDecision: (alertaVista: AlertaVista, modo: 'aprobar' | 'editar' | 'rechazar') => void;
  onProcesar: (alertaId: string) => Promise<void>;
  onReabrir: (alertaId: string) => Promise<void>;
  onVerBitacora: (alertaId: string) => void;
  onPreguntarEnChat: (pregunta: string) => void;
  estaProcesando: boolean;
}

const Nivel: React.FC<{ n: number; titulo: string; color: string }> = ({ n, titulo, color }) => (
  <div className="flex items-center gap-2">
    <div className={`w-6 h-6 rounded-lg flex items-center justify-center text-xs font-bold ${color}`}>{n}</div>
    <h3 className="text-sm font-bold uppercase tracking-wider text-slate-800">{titulo}</h3>
  </div>
);

const TablaMuestra: React.FC<{ c: ConsultaRegistrada; resaltar: string[] }> = ({ c, resaltar }) => {
  const filas = c.filas_muestra;
  const mostrar = [...filas.filter((f) => f.some((v) => typeof v === 'string' && resaltar.includes(v))), ...filas].filter(
    (f, i, arr) => arr.indexOf(f) === i
  ).slice(0, 8);
  return (
    <div className="overflow-x-auto rounded-lg border border-slate-800">
      <table className="w-full text-[11px] text-slate-300">
        <thead className="bg-slate-800 text-slate-400">
          <tr>{c.columnas.map((col) => <th key={col} className="px-2 py-1 text-left font-medium whitespace-nowrap">{col}</th>)}</tr>
        </thead>
        <tbody>
          {mostrar.map((f, i) => {
            const destacada = f.some((v) => typeof v === 'string' && resaltar.includes(v));
            return (
              <tr key={i} className={destacada ? 'bg-emerald-900/40 text-emerald-100' : ''}>
                {f.map((v, j) => <td key={j} className="px-2 py-1 whitespace-nowrap">{v === null ? '—' : String(v)}</td>)}
              </tr>
            );
          })}
        </tbody>
      </table>
      {c.filas > mostrar.length && <div className="px-2 py-1 text-[10px] text-slate-500 bg-slate-900">Mostrando {mostrar.length} de {c.filas} filas</div>}
    </div>
  );
};

export const DetalleAlertaModal: React.FC<Props> = ({
  alertaVista, consultaFoco, onClose, onAbrirDecision, onProcesar, onReabrir, onVerBitacora, onPreguntarEnChat, estaProcesando,
}) => {
  const { alerta, nombres_resueltos, propuesta } = alertaVista;
  const diagnostico = propuesta?.diagnostico;
  const acciones = propuesta?.acciones ?? [];
  const cifrasProp = propuesta?.cifras ?? [];
  const entidades = useMemo(() => [...new Set(alerta.hallazgos.flatMap((h) => h.entidades.map((e) => e.id)))], [alerta]);
  const sev = ESTILO_SEVERIDAD[alerta.severidad];

  const [nivel3, setNivel3] = useState(Boolean(consultaFoco));
  const [consultas, setConsultas] = useState<Record<string, ConsultaRegistrada | 'error'>>({});
  const [copiado, setCopiado] = useState<string | null>(null);
  const [foco, setFoco] = useState<string | undefined>(consultaFoco);
  const refs = useRef<Record<string, HTMLDivElement | null>>({});

  const idsConsultas = useMemo(
    () => [...new Set([
      ...(diagnostico?.cifras.map((c) => c.consulta_id) ?? []),
      ...acciones.flatMap((a) => a.impacto.consulta_ids),
      ...alerta.hallazgos.flatMap((h) => h.consulta_ids),
    ])],
    [diagnostico, acciones, alerta]
  );

  useEffect(() => {
    if (!nivel3) return;
    idsConsultas.filter((id) => !consultas[id]).forEach((id) => {
      getConsulta(id).then((c) => setConsultas((p) => ({ ...p, [id]: c }))).catch(() => setConsultas((p) => ({ ...p, [id]: 'error' })));
    });
  }, [nivel3, idsConsultas]); // eslint-disable-line react-hooks/exhaustive-deps

  useEffect(() => {
    if (foco && refs.current[foco]) refs.current[foco]!.scrollIntoView({ behavior: 'smooth', block: 'center' });
  }, [foco, consultas]);

  const verConsulta = (id: string) => {
    setNivel3(true);
    setFoco(id);
  };
  const copiar = (t: string) => {
    navigator.clipboard.writeText(t);
    setCopiado(t);
    setTimeout(() => setCopiado(null), 1500);
  };

  return (
    <div role="dialog" aria-modal="true" aria-label="Detalle de la alerta" className="fixed inset-0 z-50 flex items-center justify-center p-4 bg-slate-900/40 backdrop-blur-xs">
      <div className="bg-white/95 backdrop-blur-xl rounded-4xl shadow-modal border border-white w-full max-w-4xl max-h-[92vh] flex flex-col overflow-hidden">
        <div className="px-6 py-4 border-b border-slate-100 flex items-center justify-between bg-slate-50/50">
          <div className="flex items-center gap-2.5 min-w-0">
            <span className={`text-[11px] font-bold px-2 py-0.5 rounded-full border ${sev.clases}`}>{sev.simbolo} {ETIQUETA_SEVERIDAD[alerta.severidad]}</span>
            <span className="text-xs font-mono text-slate-600 bg-slate-200/60 px-2 py-0.5 rounded-md truncate">{alerta.alerta_id}</span>
          </div>
          <button onClick={onClose} aria-label="Cerrar" className="p-1.5 rounded-xl text-slate-400 hover:text-slate-700 hover:bg-slate-200/60 cursor-pointer"><X className="w-5 h-5" /></button>
        </div>

        <div className="p-6 overflow-y-auto space-y-6 flex-1">
          <div>
            <h2 className="text-lg font-bold text-slate-900">{tituloAlerta(alertaVista)}</h2>
            <div className="mt-3 flex flex-col sm:flex-row sm:items-center justify-between p-4 rounded-2xl bg-slate-50 border border-slate-200/70 gap-4">
              <div>
                <span className="text-[11px] font-semibold uppercase tracking-wider text-slate-400 block">Dinero en riesgo</span>
                <div className="text-2xl font-black text-slate-900">{formatCOP(alerta.dinero_en_riesgo_cop)}</div>
                <div className="text-xs text-slate-500 mt-0.5">
                  Detectada el {formatFecha(alerta.corte_creacion)} · <strong className="text-slate-700">{ETIQUETA_ESTADO[alerta.estado]}</strong>
                  {alerta.paso_actual !== 'ninguno' && ` · ${ETIQUETA_PASO[alerta.paso_actual]}`}
                </div>
              </div>
              <div className="sm:text-right text-sm font-semibold text-slate-800 space-y-0.5">
                {entidades.slice(0, 5).map((id) => (
                  <div key={id}>{nombres_resueltos[id] ?? id} <span className="text-slate-400 font-normal text-xs">({id})</span></div>
                ))}
                {entidades.length > 5 && <div className="text-xs text-slate-400">y {entidades.length - 5} más</div>}
              </div>
            </div>
          </div>

          {/* Nivel 1 */}
          <section className="space-y-3">
            <Nivel n={1} titulo="Qué pasó y qué se propone" color="bg-emerald-100 text-emerald-800" />
            {diagnostico ? (
              <div className="p-4 rounded-2xl bg-emerald-50/40 border border-emerald-100 space-y-3">
                <p className="text-sm text-slate-900 font-medium leading-relaxed">
                  <TextoConCifras texto={diagnostico.resumen} cifras={diagnostico.cifras} onCifra={verConsulta} />
                </p>
                {propuesta && propuesta.aprendizaje.length > 0 && (
                  <div className="p-3 rounded-xl bg-amber-50 border border-amber-200 text-xs text-amber-900 space-y-1">
                    <div className="font-bold">Centinela aprendió de rechazos anteriores</div>
                    {propuesta.aprendizaje.map((a, i) => <div key={i}>{a}</div>)}
                  </div>
                )}
                {acciones.length > 0 && (
                  <div className="pt-2 border-t border-emerald-100/70 space-y-2">
                    <span className="text-xs font-bold text-emerald-900 uppercase tracking-wide block">Acciones propuestas, de la más a la menos recomendada</span>
                    {acciones.map((acc, i) => (
                      <div key={acc.accion_id} className="p-3 bg-white rounded-xl border border-emerald-200/80 flex flex-col sm:flex-row sm:items-start justify-between gap-3">
                        <div className="min-w-0">
                          <div className="text-xs font-bold text-slate-900 flex items-center gap-1.5">
                            <Sparkles className="w-3.5 h-3.5 text-amber-500 shrink-0" />
                            <span>{i + 1}. <TextoConCifras texto={acc.titulo} cifras={cifrasProp} onCifra={verConsulta} /></span>
                          </div>
                          <p className="text-xs text-slate-600 mt-0.5"><TextoConCifras texto={acc.razon} cifras={cifrasProp} onCifra={verConsulta} /></p>
                          <span className="text-[10px] text-slate-400">Confianza {(acc.confianza * 100).toFixed(0)} %</span>
                        </div>
                        <div className="text-left sm:text-right shrink-0 max-w-[15rem]">
                          <span className="text-sm font-extrabold text-emerald-700">{formatCOP(acc.impacto.valor_cop)}</span>
                          <span className="text-[10px] text-slate-500 ml-1">{acc.impacto.horizonte === 'mensual' ? 'al mes' : 'en total'}</span>
                          <span className="text-[10px] text-slate-400 block leading-snug">{acc.impacto.descripcion}</span>
                        </div>
                      </div>
                    ))}
                  </div>
                )}
              </div>
            ) : (
              <div className="p-4 rounded-2xl bg-amber-50/50 border border-amber-200/70 text-xs text-slate-700 space-y-1">
                <div className="font-semibold text-amber-900">
                  {alerta.estado === 'sin_evidencia' ? 'Sin evidencia suficiente' : alerta.estado === 'en_analisis' ? 'Análisis en curso' : 'Pendiente de análisis'}
                </div>
                <p className="leading-relaxed">
                  {alerta.estado === 'sin_evidencia'
                    ? 'Los datos no alcanzan para explicar la causa con certeza; Centinela prefiere decirlo antes que inventar.'
                    : 'El Vigía detectó la desviación con reglas de política. El Analista y el Estratega aún no la han investigado.'}
                </p>
              </div>
            )}
          </section>

          {/* Nivel 2 */}
          <section className="space-y-3">
            <Nivel n={2} titulo="Por qué: causa, evidencia y política" color="bg-blue-100 text-blue-800" />
            {diagnostico ? (
              <div className="p-4 rounded-2xl bg-slate-50/80 border border-slate-200/70 space-y-4">
                <p className="text-xs text-slate-700 leading-relaxed">
                  <TextoConCifras texto={diagnostico.causa_raiz} cifras={diagnostico.cifras} onCifra={verConsulta} />
                </p>
                {diagnostico.cifras.length > 0 && (
                  <div>
                    <span className="text-xs font-bold uppercase tracking-wider text-slate-400 block mb-2">Cifras de la base de datos (clic para ver su consulta)</span>
                    <div className="grid grid-cols-1 sm:grid-cols-2 md:grid-cols-3 gap-2.5">
                      {diagnostico.cifras.map((c, i) => (
                        <button key={i} onClick={() => verConsulta(c.consulta_id)} className="p-3 bg-white rounded-xl border border-slate-200/80 text-left hover:border-emerald-400 cursor-pointer">
                          <span className="text-[11px] text-slate-500 block">{c.etiqueta}</span>
                          <span className="text-base font-bold text-slate-900">{formatCifra(c)}</span>
                        </button>
                      ))}
                    </div>
                  </div>
                )}
                {diagnostico.politicas.length > 0 && (
                  <div>
                    <span className="text-xs font-bold uppercase tracking-wider text-slate-400 block mb-2">Políticas citadas</span>
                    <div className="space-y-2">
                      {diagnostico.politicas.map((p, i) => (
                        <div key={i} className="p-3 bg-white rounded-xl border border-slate-200/80 flex items-center justify-between gap-2">
                          <div className="flex items-center gap-2 text-xs">
                            <FileText className="w-4 h-4 text-rose-500 shrink-0" />
                            <span className="font-bold text-slate-800">{p.documento}</span>
                            <span className="text-slate-500">· {p.seccion}</span>
                          </div>
                          <span className="text-[10px] font-mono text-slate-400" title="Huella del fragmento recuperado">#{p.fragmento_hash.slice(0, 8)}</span>
                        </div>
                      ))}
                    </div>
                  </div>
                )}
                <div className="flex flex-wrap items-center justify-between pt-2 border-t border-slate-200/60 text-xs text-slate-500 gap-2">
                  <span>Confianza del análisis: <strong className="text-emerald-700">{(diagnostico.confianza * 100).toFixed(0)} %</strong></span>
                  {diagnostico.supuestos.length > 0 && <span className="text-[11px] text-slate-400">Supuestos: {diagnostico.supuestos.join(' · ')}</span>}
                </div>
              </div>
            ) : (
              <div className="p-4 rounded-2xl bg-slate-50 border border-slate-200/60 text-xs text-slate-500 italic">La causa se explicará cuando el Analista termine.</div>
            )}
          </section>

          {/* Nivel 3 */}
          <section className="border border-slate-200/70 rounded-2xl overflow-hidden">
            <button onClick={() => setNivel3(!nivel3)} aria-expanded={nivel3} className="w-full p-4 bg-slate-50 hover:bg-slate-100/80 flex items-center justify-between text-left cursor-pointer">
              <div className="flex items-center gap-2">
                <div className="w-6 h-6 rounded-lg bg-purple-100 text-purple-800 flex items-center justify-center text-xs font-bold">3</div>
                <div>
                  <h3 className="text-sm font-bold uppercase tracking-wider text-slate-800">Cómo llegué aquí</h3>
                  <p className="text-[11px] text-slate-400">{idsConsultas.length} consulta(s) SQL registradas, reproducibles y con huella SHA-256</p>
                </div>
              </div>
              {nivel3 ? <ChevronDown className="w-4 h-4 text-slate-500" /> : <ChevronRight className="w-4 h-4 text-slate-500" />}
            </button>
            {nivel3 && (
              <div className="p-4 bg-slate-900 text-slate-200 space-y-4 text-xs">
                {idsConsultas.map((id) => {
                  const c = consultas[id];
                  return (
                    <div key={id} ref={(el) => (refs.current[id] = el)} className={`space-y-2 p-3 rounded-xl border ${foco === id ? 'border-emerald-500 bg-slate-950' : 'border-slate-800'}`}>
                      <div className="flex items-center justify-between gap-2 text-[11px]">
                        <span className="font-mono text-emerald-300">{id}</span>
                        {c && c !== 'error' && <span className="text-slate-400">{c.vista} · corte {c.corte} · {c.filas} fila(s)</span>}
                      </div>
                      {!c && <div className="flex items-center gap-2 text-slate-400"><Loader2 className="w-3.5 h-3.5 animate-spin" /> Cargando…</div>}
                      {c === 'error' && <div className="text-rose-300">No se pudo cargar esta consulta.</div>}
                      {c && c !== 'error' && (
                        <>
                          <p className="text-slate-300">{c.descripcion}</p>
                          <pre className="p-3 bg-slate-950 rounded-xl text-slate-300 overflow-x-auto border border-slate-800 whitespace-pre-wrap font-mono text-[11px]">{c.sql_renderizado}</pre>
                          <TablaMuestra c={c} resaltar={entidades} />
                          <div className="flex items-center justify-between text-[10px] text-slate-500 font-mono">
                            <span>SHA-256 {c.resultado_hash.slice(0, 24)}…</span>
                            <button onClick={() => copiar(c.sql_renderizado)} className="flex items-center gap-1 hover:text-slate-300 cursor-pointer">
                              {copiado === c.sql_renderizado ? <Check className="w-3 h-3" /> : <Copy className="w-3 h-3" />} Copiar SQL
                            </button>
                          </div>
                        </>
                      )}
                    </div>
                  );
                })}
              </div>
            )}
          </section>

          <div className="p-3 rounded-2xl bg-amber-50/40 border border-amber-100 flex items-center justify-between gap-3">
            <span className="text-xs text-amber-900 font-medium flex items-center gap-2"><Sparkles className="w-4 h-4 text-amber-600 shrink-0" /> ¿Quieres profundizar? Pregunta al asistente sobre esta alerta.</span>
            <button
              onClick={() => { onClose(); onPreguntarEnChat(''); }}
              className="text-xs font-semibold text-amber-800 hover:text-amber-950 underline cursor-pointer shrink-0"
            >
              Abrir asistente →
            </button>
          </div>
        </div>

        <div className="px-6 py-4 border-t border-slate-100 bg-slate-50/60 flex flex-wrap items-center justify-between gap-3">
          <button onClick={() => onVerBitacora(alerta.alerta_id)} className="px-3 py-2 rounded-xl text-xs font-medium text-slate-700 hover:bg-slate-200/60 flex items-center gap-1.5 cursor-pointer">
            <History className="w-3.5 h-3.5" /> Ver auditoría
          </button>
          <div className="flex items-center gap-2">
            {alerta.estado === 'nueva' && (
              <button onClick={() => onProcesar(alerta.alerta_id)} disabled={estaProcesando} className="px-4 py-2 rounded-xl text-xs font-bold text-white bg-slate-900 hover:bg-slate-800 flex items-center gap-2 cursor-pointer disabled:opacity-50">
                {estaProcesando ? <><Loader2 className="w-3.5 h-3.5 animate-spin" /> Analizando…</> : <><Sparkles className="w-3.5 h-3.5 text-amber-300" /> Analizar con IA</>}
              </button>
            )}
            {alerta.estado === 'rechazada' && (
              <button onClick={() => onReabrir(alerta.alerta_id)} className="px-4 py-2 rounded-xl text-xs font-bold text-slate-800 bg-white border border-slate-300 hover:bg-slate-50 flex items-center gap-2 cursor-pointer">
                <RotateCcw className="w-3.5 h-3.5" /> Volver a proponer con lo aprendido
              </button>
            )}
            {alerta.estado === 'propuesta' && (
              <>
                <button onClick={() => onAbrirDecision(alertaVista, 'rechazar')} className="px-3.5 py-2 rounded-xl text-xs font-medium text-slate-600 hover:text-rose-700 hover:bg-rose-50 border border-slate-200 cursor-pointer">Rechazar…</button>
                <button onClick={() => onAbrirDecision(alertaVista, 'editar')} className="px-3.5 py-2 rounded-xl text-xs font-semibold text-amber-800 bg-amber-50 hover:bg-amber-100 border border-amber-200 cursor-pointer">Editar…</button>
                <button onClick={() => onAbrirDecision(alertaVista, 'aprobar')} className="px-4 py-2 rounded-xl text-xs font-bold text-emerald-800 bg-emerald-100 hover:bg-emerald-200 border border-emerald-300 flex items-center gap-1.5 cursor-pointer">
                  <Check className="w-4 h-4" /> Aprobar…
                </button>
              </>
            )}
          </div>
        </div>
      </div>
    </div>
  );
};
