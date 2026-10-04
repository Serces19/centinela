// frontend/src/App.tsx
import React, { useCallback, useEffect, useMemo, useRef, useState } from 'react';
import { Toaster, toast } from 'sonner';
import { Sidebar, TabId } from './components/Sidebar';
import { Topbar } from './components/Topbar';
import { BandejaDecisiones } from './components/BandejaDecisiones';
import { DetalleAlertaModal } from './components/DetalleAlertaModal';
import { DecisionModal } from './components/DecisionModal';
import { ChatSoporte } from './components/ChatSoporte';
import { BitacoraViewer } from './components/BitacoraViewer';
import { CostoRoiPanel } from './components/CostoRoiPanel';
import { ConfiguracionPanel } from './components/ConfiguracionPanel';
import { ConsultaModal } from './components/ConsultaModal';
import { AlertaVista, DecisionRequest, Persona, ResultadoEjecucion, ResumenAlertas, SimulacionCorte } from './types';
import { PERSONAS_DISPONIBLES } from './utils/personas';
import {
  avanzarSimulacion,
  getAlertas,
  getCorte,
  getResumen,
  procesarAlerta,
  reabrirAlerta,
  reiniciarSimulacion,
  tomarDecision,
} from './api/client';
import { formatFecha } from './utils/formatters';
import { tituloAlerta } from './utils/alertas';
import { textoPlano } from './utils/texto';

const TITULOS: Record<TabId, { titulo: string; subtitulo: string }> = {
  bandeja: { titulo: 'Bandeja de decisiones', subtitulo: 'Los problemas llegan a ti, explicados y con una propuesta lista para aprobar.' },
  bitacora: { titulo: 'Auditoría', subtitulo: 'Quién aprobó qué, cuándo y qué ejecutó el agente, con cadena de hashes verificable.' },
  metricas: { titulo: 'Costo de inferencia', subtitulo: 'Lo que cuesta, medido con los tokens reales de Bedrock.' },
  configuracion: { titulo: 'Configuración', subtitulo: 'Umbrales de alerta y nivel de autonomía por tipo de acción.' },
};

export const App: React.FC = () => {
  const [tabActiva, setTabActiva] = useState<TabId>('bandeja');
  const [personaActiva, setPersonaActiva] = useState<Persona>(PERSONAS_DISPONIBLES[0]);
  const [corte, setCorte] = useState<SimulacionCorte | null>(null);
  const [resumen, setResumen] = useState<ResumenAlertas | null>(null);
  const [alertas, setAlertas] = useState<AlertaVista[]>([]);
  const [cargando, setCargando] = useState(true);
  const [cargandoReloj, setCargandoReloj] = useState(false);
  const [procesandoIds, setProcesandoIds] = useState<Set<string>>(new Set());

  const [detalleId, setDetalleId] = useState<string | undefined>();
  const [decision, setDecision] = useState<{ item: AlertaVista; modo: 'aprobar' | 'editar' | 'rechazar' } | null>(null);
  const [consultaId, setConsultaId] = useState<string | undefined>();
  const [menuAbierto, setMenuAbierto] = useState(false);
  const [chat, setChat] = useState<{ abierto: boolean; alertaId?: string }>({ abierto: false });
  const [bitacoraAlerta, setBitacoraAlerta] = useState<string | undefined>();
  const procesando = useRef(procesandoIds);
  procesando.current = procesandoIds;

  const detalle = useMemo(() => alertas.find((a) => a.alerta.alerta_id === detalleId) ?? null, [alertas, detalleId]);

  const refrescar = useCallback(async (conCorte = true) => {
    const [c, r, a] = await Promise.all([conCorte ? getCorte() : Promise.resolve(null), getResumen(), getAlertas()]);
    if (c) setCorte(c);
    setResumen(r);
    setAlertas(a);
  }, []);

  useEffect(() => {
    refrescar()
      .catch((e) => toast.error(`No se pudo conectar con la API de Centinela: ${(e as Error).message}`))
      .finally(() => setCargando(false));
  }, [refrescar]);

  // Mientras alguna alerta se analiza, se consulta el estado cada 3 s para mostrar el paso en curso.
  const hayEnCurso = procesandoIds.size > 0 || alertas.some((a) => a.alerta.estado === 'en_analisis');
  useEffect(() => {
    if (!hayEnCurso) return;
    const t = setInterval(() => refrescar(false).catch(() => undefined), 3000);
    return () => clearInterval(t);
  }, [hayEnCurso, refrescar]);

  const analizar = useCallback(
    async (alertaId: string, silencioso = false) => {
      if (procesando.current.has(alertaId)) return;
      setProcesandoIds((p) => new Set(p).add(alertaId));
      try {
        const vista = await procesarAlerta(alertaId);
        if (!silencioso) {
          toast.success(vista.propuesta ? 'Propuesta lista para tu decisión.' : 'El análisis terminó sin evidencia suficiente.');
        }
      } catch (e) {
        toast.error((e as Error).message);
      } finally {
        setProcesandoIds((p) => {
          const n = new Set(p);
          n.delete(alertaId);
          return n;
        });
        refrescar().catch(() => undefined);
      }
    },
    [refrescar]
  );

  // Tras mover el reloj: las decisiones clave se analizan solas, sin pasos manuales.
  const analizarClave = useCallback(async () => {
    const r = await getResumen();
    r.decisiones_clave.filter((a) => a.alerta.estado === 'nueva').forEach((a) => void analizar(a.alerta.alerta_id, true));
  }, [analizar]);

  const conReloj = async (accion: () => Promise<void>) => {
    try {
      setCargandoReloj(true);
      await accion();
      await refrescar();
      await analizarClave();
    } catch (e) {
      toast.error((e as Error).message);
    } finally {
      setCargandoReloj(false);
    }
  };

  const avanzar = (dias: number) =>
    conReloj(async () => {
      const r = await avanzarSimulacion(dias);
      toast.success(`Corte ${formatFecha(r.corte)}: ${r.alertas_detectadas} causas detectadas, ${r.alertas_nuevas} nuevas.`);
    });

  const reiniciar = () =>
    conReloj(async () => {
      const r = await reiniciarSimulacion();
      toast.info(`Demo reiniciada al corte ${formatFecha(r.corte)}.`);
    });

  const irAFecha = (fecha: string) =>
    conReloj(async () => {
      const actual = (corte?.corte ?? '').split('T')[0];
      const dias = Math.round((new Date(`${fecha}T00:00:00`).getTime() - new Date(`${actual}T00:00:00`).getTime()) / 86400000);
      if (dias === 0) return;
      if (dias < 0) await reiniciarSimulacion();
      const desde = dias < 0 ? (corte?.corte_inicial_limpio ?? actual).split('T')[0] : actual;
      const saltar = Math.round((new Date(`${fecha}T00:00:00`).getTime() - new Date(`${desde}T00:00:00`).getTime()) / 86400000);
      if (saltar > 0) await avanzarSimulacion(saltar);
      toast.success(`Corte ${formatFecha(fecha)}.`);
    });

  const decidir = async (alertaId: string, req: DecisionRequest, version?: number): Promise<{ resultado: ResultadoEjecucion }> => {
    const res = await tomarDecision(alertaId, req, version);
    await refrescar();
    toast.success(req.decision === 'rechazar' ? 'Rechazo registrado; Centinela lo tendrá en cuenta.' : 'Decisión ejecutada en entorno seguro y registrada en la auditoría.');
    return { resultado: res.resultado };
  };

  const reabrir = async (alertaId: string) => {
    try {
      await reabrirAlerta(alertaId, personaActiva.id);
      await refrescar();
      toast.info('Alerta reabierta: Centinela vuelve a analizarla con lo aprendido.');
      void analizar(alertaId, true);
    } catch (e) {
      toast.error((e as Error).message);
    }
  };

  const verBitacora = (alertaId?: string) => {
    setBitacoraAlerta(alertaId);
    setTabActiva('bitacora');
    setDetalleId(undefined);
  };

  const abrirChat = (alertaId?: string) => setChat({ abierto: true, alertaId });

  const sugerencias = useMemo(() => {
    const a = alertas.find((x) => x.alerta.alerta_id === chat.alertaId);
    if (!a) return ['¿Qué línea de producto vendió más y cuánto?', '¿Qué dice la política de crédito sobre la mora?', '¿Qué clientes tienen más cartera vencida?'];
    const ids = [...new Set(a.alerta.hallazgos.flatMap((h) => h.entidades.map((e) => `${e.tipo}:${e.id}`)))];
    const skus = ids.filter((i) => i.startsWith('sku:')).map((i) => i.slice(4)).slice(0, 2);
    const prov = ids.find((i) => i.startsWith('proveedor:'))?.slice(10);
    const cli = ids.find((i) => i.startsWith('cliente:'))?.slice(8);
    return [
      skus.length ? `¿Qué otros clientes compran los SKU ${skus.join(' y ')}?` : '',
      prov ? `¿Qué otros SKU le compramos al proveedor ${prov}?` : '',
      cli ? `¿Cuáles son los 5 productos que más compra el cliente ${cli}?` : '',
      '¿Qué política aplica a este caso y qué exige?',
    ].filter(Boolean);
  }, [alertas, chat.alertaId]);

  const pendientes = resumen?.pendientes ?? 0;

  return (
    <div className="min-h-screen text-slate-900 flex font-sans antialiased">
      <Toaster position="top-right" richColors />
      <Sidebar
        tabActiva={tabActiva}
        onSelectTab={(t) => { setTabActiva(t); if (t !== 'bitacora') setBitacoraAlerta(undefined); }}
        personaActiva={personaActiva}
        onSelectPersona={(p) => { setPersonaActiva(p); toast.info(`Rol activo: ${p.nombre} (${p.cargo})`); }}
        pendientesCount={pendientes}
        abierto={menuAbierto}
        onCerrar={() => setMenuAbierto(false)}
      />

      <div className="flex-1 flex flex-col min-w-0">
        <Topbar
          corte={corte}
          loadingReloj={cargandoReloj}
          onAvanzar={avanzar}
          onReiniciar={reiniciar}
          onIrAFecha={irAFecha}
          chatAbierto={chat.abierto}
          onToggleChat={() => setChat((c) => ({ abierto: !c.abierto, alertaId: c.alertaId }))}
          tituloPantalla={TITULOS[tabActiva].titulo}
          subtituloPantalla={TITULOS[tabActiva].subtitulo}
          onAbrirMenu={() => setMenuAbierto(true)}
        />

        <main key={tabActiva} className="flex-1 px-4 sm:px-6 lg:px-8 pt-3 pb-10 max-w-[1500px] w-full animate-fade-up">
          {tabActiva === 'bandeja' && (
            <BandejaDecisiones
              resumen={resumen}
              alertas={alertas}
              loading={cargando}
              corte={corte}
              procesandoIds={procesandoIds}
              onSelectAlerta={(av) => setDetalleId(av.alerta.alerta_id)}
              onProcesar={(id) => void analizar(id)}
              onAbrirDecision={(item, modo) => setDecision({ item, modo })}
              onReabrir={(id) => void reabrir(id)}
              onVerBitacora={verBitacora}
            />
          )}
          {tabActiva === 'bitacora' && <BitacoraViewer alertas={alertas} alertaSeleccionadaId={bitacoraAlerta} onLimpiarAlerta={() => setBitacoraAlerta(undefined)} />}
          {tabActiva === 'metricas' && <CostoRoiPanel resumen={resumen} />}
          {tabActiva === 'configuracion' && <ConfiguracionPanel personaActiva={personaActiva} onCambio={() => refrescar().catch(() => undefined)} />}
        </main>
      </div>

      {chat.abierto && (
        <ChatSoporte
          key={chat.alertaId ?? 'libre'}
          alertaId={chat.alertaId}
          sugerencias={sugerencias}
          onClose={() => setChat((c) => ({ ...c, abierto: false }))}
          onVerConsulta={setConsultaId}
        />
      )}

      {detalle && (
        <DetalleAlertaModal
          alertaVista={detalle}
          onClose={() => setDetalleId(undefined)}
          onAbrirDecision={(item, modo) => setDecision({ item, modo })}
          onProcesar={(id) => analizar(id)}
          onReabrir={reabrir}
          onVerBitacora={verBitacora}
          onPreguntarEnChat={() => abrirChat(detalle.alerta.alerta_id)}
          estaProcesando={procesandoIds.has(detalle.alerta.alerta_id)}
        />
      )}

      {decision && (
        <DecisionModal
          alertaVista={decision.item}
          modo={decision.modo}
          personaActiva={personaActiva}
          onClose={() => setDecision(null)}
          onSubmitDecision={decidir}
        />
      )}

      {consultaId && <ConsultaModal consultaId={consultaId} onClose={() => setConsultaId(undefined)} />}
    </div>
  );
};

export default App;
