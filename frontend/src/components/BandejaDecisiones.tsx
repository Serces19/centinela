// frontend/src/components/BandejaDecisiones.tsx
import React, { useMemo, useState } from 'react';
import { CheckCircle2, ChevronRight, Loader2, RotateCcw, Search, ShieldCheck, Sparkles } from 'lucide-react';
import { AlertaVista, ResumenAlertas, SimulacionCorte } from '../types';
import { formatCOP, formatCOPSimple, formatFecha } from '../utils/formatters';
import {
  ESTILO_SEVERIDAD,
  ETIQUETA_ESTADO,
  ETIQUETA_PASO,
  ETIQUETA_SEVERIDAD,
  esPendiente,
  familiaDe,
  infoFamilia,
  tituloAlerta,
} from '../utils/alertas';
import { TextoConCifras } from '../utils/texto';

interface Props {
  resumen: ResumenAlertas | null;
  alertas: AlertaVista[];
  loading: boolean;
  corte: SimulacionCorte | null;
  procesandoIds: Set<string>;
  onSelectAlerta: (av: AlertaVista) => void;
  onProcesar: (alertaId: string) => void;
  onAbrirDecision: (av: AlertaVista, modo: 'aprobar' | 'editar' | 'rechazar') => void;
  onReabrir: (alertaId: string) => void;
  onVerBitacora: (alertaId: string) => void;
}

const ChipSeveridad: React.FC<{ item: AlertaVista }> = ({ item }) => {
  const s = ESTILO_SEVERIDAD[item.alerta.severidad];
  return (
    <span className={`text-[11px] font-bold px-2 py-0.5 rounded-full border whitespace-nowrap ${s.clases}`}>
      <span aria-hidden="true">{s.simbolo} </span>
      {ETIQUETA_SEVERIDAD[item.alerta.severidad]}
    </span>
  );
};

const Estado: React.FC<{ item: AlertaVista; procesando: boolean }> = ({ item, procesando }) => {
  const { estado, paso_actual } = item.alerta;
  const enCurso = procesando || estado === 'en_analisis';
  return (
    <span className="text-[11px] text-slate-600 inline-flex items-center gap-1.5">
      {enCurso && <Loader2 className="w-3 h-3 animate-spin" />}
      {enCurso ? ETIQUETA_PASO[paso_actual] ?? 'Preparando el análisis' : ETIQUETA_ESTADO[estado]}
    </span>
  );
};

const TarjetaDecision: React.FC<Omit<Props, 'resumen' | 'alertas' | 'loading' | 'corte'> & { item: AlertaVista }> = ({
  item, procesandoIds, onSelectAlerta, onProcesar, onAbrirDecision, onReabrir, onVerBitacora,
}) => {
  const { alerta, propuesta } = item;
  const procesando = procesandoIds.has(alerta.alerta_id) || alerta.estado === 'en_analisis';
  const familia = infoFamilia(alerta.huella_causa);
  const principal = propuesta?.acciones[0];
  const nombres = [...new Set(alerta.hallazgos.flatMap((h) => h.entidades.map((e) => item.nombres_resueltos[e.id] ?? e.id)))];
  return (
    <article className="glass rounded-4xl p-5 flex flex-col gap-3" aria-label={tituloAlerta(item)}>
      <div className="flex items-center justify-between gap-2">
        <span className={`text-[11px] font-bold px-2 py-0.5 rounded-full border ${familia.badge}`}>{familia.etiqueta}</span>
        <ChipSeveridad item={item} />
      </div>
      <div>
        <h3 className="text-base font-semibold text-slate-900 leading-snug">{tituloAlerta(item)}</h3>
        <p className="text-[11px] text-slate-400 mt-0.5 truncate">{nombres.slice(0, 3).join(' · ')}{nombres.length > 3 ? ` y ${nombres.length - 3} más` : ''}</p>
      </div>
      <div>
        <div className="text-2xl font-black text-slate-900">{formatCOP(alerta.dinero_en_riesgo_cop)}</div>
        <div className="text-[11px] text-slate-500">en riesgo · <Estado item={item} procesando={procesando} /></div>
      </div>
      <p className="text-xs text-slate-700 leading-relaxed min-h-[3rem]">
        {propuesta ? (
          <TextoConCifras texto={propuesta.diagnostico.resumen} cifras={propuesta.diagnostico.cifras} />
        ) : procesando ? (
          'Centinela está investigando la causa y armando las acciones…'
        ) : (
          'El Vigía detectó la desviación con reglas de política. Falta que el Analista explique la causa.'
        )}
      </p>
      {principal && (
        <div className="text-[11px] text-slate-600 p-2.5 rounded-xl bg-white/70 border border-white">
          <span className="font-semibold text-slate-800">Recomendación: </span>
          <TextoConCifras texto={principal.titulo} cifras={propuesta!.cifras} />
          <span className="text-slate-400"> · confianza {(principal.confianza * 100).toFixed(0)} %</span>
        </div>
      )}
      <div className="flex flex-wrap items-center gap-2 mt-auto pt-1">
        {alerta.estado === 'propuesta' && (
          <>
            <button onClick={() => onAbrirDecision(item, 'aprobar')} className="px-3.5 py-2 rounded-full text-xs font-bold text-emerald-900 bg-lime hover:brightness-95 cursor-pointer">Aprobar</button>
            <button onClick={() => onAbrirDecision(item, 'editar')} className="px-3.5 py-2 rounded-full text-xs font-semibold text-slate-700 bg-white/80 border border-white hover:bg-white cursor-pointer">Editar</button>
            <button onClick={() => onAbrirDecision(item, 'rechazar')} className="px-3.5 py-2 rounded-full text-xs font-semibold text-rose-700 bg-white/80 border border-white hover:bg-white cursor-pointer">Rechazar</button>
          </>
        )}
        {alerta.estado === 'nueva' && !procesando && (
          <button onClick={() => onProcesar(alerta.alerta_id)} className="px-3.5 py-2 rounded-full text-xs font-bold text-white bg-slate-900 hover:bg-slate-800 flex items-center gap-1.5 cursor-pointer">
            <Sparkles className="w-3.5 h-3.5 text-amber-300" /> Analizar con IA
          </button>
        )}
        {alerta.estado === 'rechazada' && (
          <button onClick={() => onReabrir(alerta.alerta_id)} className="px-3.5 py-2 rounded-full text-xs font-semibold text-slate-800 bg-white border border-slate-300 hover:bg-slate-50 flex items-center gap-1.5 cursor-pointer">
            <RotateCcw className="w-3.5 h-3.5" /> Volver a proponer
          </button>
        )}
        {(alerta.estado === 'ejecutada' || alerta.estado === 'aprobada') && (
          <button onClick={() => onVerBitacora(alerta.alerta_id)} className="px-3.5 py-2 rounded-full text-xs font-semibold text-emerald-800 bg-emerald-50 border border-emerald-200 flex items-center gap-1.5 cursor-pointer">
            <CheckCircle2 className="w-3.5 h-3.5" /> Ejecutada · ver auditoría
          </button>
        )}
        <button onClick={() => onSelectAlerta(item)} className="ml-auto text-xs font-semibold text-slate-600 hover:text-slate-900 flex items-center gap-0.5 cursor-pointer">
          Ver cómo llegué aquí <ChevronRight className="w-3.5 h-3.5" />
        </button>
      </div>
    </article>
  );
};

const POR_PAGINA = 15;

export const BandejaDecisiones: React.FC<Props> = (props) => {
  const { resumen, alertas, loading, corte, procesandoIds, onSelectAlerta } = props;
  const [vista, setVista] = useState<'pendientes' | 'resueltas' | 'todas'>('pendientes');
  const [familia, setFamilia] = useState('todas');
  const [texto, setTexto] = useState('');
  const [limite, setLimite] = useState(POR_PAGINA);

  const familias = useMemo(() => [...new Set(alertas.map((a) => familiaDe(a.alerta.huella_causa)))], [alertas]);
  const filtradas = useMemo(() => {
    const q = texto.trim().toLowerCase();
    return alertas
      .filter((a) => (vista === 'todas' ? true : vista === 'pendientes' ? esPendiente(a) : !esPendiente(a)))
      .filter((a) => familia === 'todas' || familiaDe(a.alerta.huella_causa) === familia)
      .filter((a) => !q || `${tituloAlerta(a)} ${a.alerta.alerta_id} ${a.alerta.huella_causa} ${Object.values(a.nombres_resueltos).join(' ')}`.toLowerCase().includes(q))
      .sort((x, y) => y.alerta.dinero_en_riesgo_cop - x.alerta.dinero_en_riesgo_cop);
  }, [alertas, vista, familia, texto]);

  if (loading && !resumen) {
    return <div className="glass rounded-4xl p-10 text-center text-sm text-slate-500 flex items-center justify-center gap-2"><Loader2 className="w-4 h-4 animate-spin" /> Cargando la operación…</div>;
  }

  const claves = resumen?.decisiones_clave ?? [];
  return (
    <div className="space-y-6">
      <section className="glass rounded-4xl p-6 flex flex-col lg:flex-row lg:items-center justify-between gap-4" aria-label="Dinero en riesgo">
        <div>
          <span className="section-eyebrow">Dinero en riesgo hoy</span>
          <div className="text-4xl sm:text-5xl font-black tracking-tight text-slate-900 mt-1">{formatCOP(resumen?.total_dinero_en_riesgo_cop ?? 0)}</div>
          <p className="text-xs text-slate-500 mt-1">
            {resumen?.pendientes ?? 0} causas pendientes · {resumen?.resueltas ?? 0} resueltas · corte {formatFecha(corte?.corte)} · una alerta por causa, sin contar dos veces el mismo dinero
          </p>
        </div>
        <div className="flex flex-wrap gap-2">
          {(['critica', 'alta', 'media', 'baja'] as const).map((s) => {
            const n = resumen?.por_severidad[s] ?? 0;
            return n > 0 ? (
              <span key={s} className={`text-xs font-bold px-3 py-1.5 rounded-full border ${ESTILO_SEVERIDAD[s].clases}`}>
                <span aria-hidden="true">{ESTILO_SEVERIDAD[s].simbolo} </span>{n} {ETIQUETA_SEVERIDAD[s].toLowerCase()}{n > 1 && s !== 'media' && s !== 'baja' ? 's' : ''}
              </span>
            ) : null;
          })}
        </div>
      </section>

      {claves.length > 0 ? (
        <section aria-label="Decisiones clave" className="space-y-3">
          <h2 className="text-sm font-bold uppercase tracking-wider text-slate-700">Tus {claves.length} decisiones clave</h2>
          <div className="grid grid-cols-1 xl:grid-cols-3 gap-4">
            {claves.map((item) => <TarjetaDecision key={item.alerta.alerta_id} item={item} {...props} procesandoIds={procesandoIds} />)}
          </div>
        </section>
      ) : (
        <section className="glass rounded-4xl p-8 text-center space-y-2">
          <ShieldCheck className="w-8 h-8 text-emerald-600 mx-auto" />
          <h2 className="text-base font-semibold text-slate-900">Sin decisiones pendientes en este corte</h2>
          <p className="text-xs text-slate-500">Avanza el reloj simulado para ver cómo Centinela detecta y explica los problemas a medida que ocurren.</p>
        </section>
      )}

      <section className="glass rounded-4xl p-5 space-y-4" aria-label="Todas las alertas">
        <div className="flex flex-col md:flex-row md:items-center justify-between gap-3">
          <h2 className="text-sm font-bold uppercase tracking-wider text-slate-700">Todas las alertas ({filtradas.length})</h2>
          <div className="flex flex-wrap items-center gap-2">
            <div className="flex p-1 rounded-full bg-white/70 border border-white text-xs font-semibold" role="tablist">
              {(['pendientes', 'resueltas', 'todas'] as const).map((v) => (
                <button key={v} role="tab" aria-selected={vista === v} onClick={() => { setVista(v); setLimite(POR_PAGINA); }} className={`px-3 py-1.5 rounded-full cursor-pointer capitalize ${vista === v ? 'bg-slate-900 text-white' : 'text-slate-600'}`}>{v}</button>
              ))}
            </div>
            <select value={familia} onChange={(e) => setFamilia(e.target.value)} aria-label="Filtrar por tipo de causa" className="text-xs p-2 rounded-full bg-white/70 border border-white">
              <option value="todas">Todos los tipos</option>
              {familias.map((f) => <option key={f} value={f}>{infoFamilia(f).etiqueta}</option>)}
            </select>
            <div className="relative">
              <Search className="w-3.5 h-3.5 text-slate-400 absolute left-3 top-1/2 -translate-y-1/2" />
              <input value={texto} onChange={(e) => setTexto(e.target.value)} placeholder="Buscar…" aria-label="Buscar alertas" className="text-xs pl-8 pr-3 py-2 rounded-full bg-white/70 border border-white w-40" />
            </div>
          </div>
        </div>

        {filtradas.length === 0 ? (
          <p className="text-xs text-slate-500 py-4 text-center">No hay alertas con estos filtros.</p>
        ) : (
          <ul className="divide-y divide-white/70">
            {filtradas.slice(0, limite).map((item) => (
              <li key={item.alerta.alerta_id}>
                <button onClick={() => onSelectAlerta(item)} className="w-full py-3 flex items-center gap-3 text-left hover:bg-white/50 rounded-xl px-2 cursor-pointer">
                  <ChipSeveridad item={item} />
                  <span className="flex-1 min-w-0">
                    <span className="block text-sm font-medium text-slate-900 truncate">{tituloAlerta(item)}</span>
                    <span className="block text-[11px] text-slate-400"><Estado item={item} procesando={procesandoIds.has(item.alerta.alerta_id)} /></span>
                  </span>
                  <span className="text-sm font-bold text-slate-900 whitespace-nowrap" title={formatCOP(item.alerta.dinero_en_riesgo_cop)}>{formatCOPSimple(item.alerta.dinero_en_riesgo_cop)}</span>
                  <ChevronRight className="w-4 h-4 text-slate-400 shrink-0" />
                </button>
              </li>
            ))}
          </ul>
        )}
        {filtradas.length > limite && (
          <button onClick={() => setLimite(limite + POR_PAGINA)} className="mx-auto block text-xs font-semibold text-slate-600 hover:text-slate-900 cursor-pointer">Mostrar {Math.min(POR_PAGINA, filtradas.length - limite)} más</button>
        )}
      </section>
    </div>
  );
};
