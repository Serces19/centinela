// frontend/src/App.tsx
import React, { useState, useEffect, useCallback, useRef } from 'react';
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
import {
  AlertaVista,
  DecisionRequest,
  Persona,
  ResultadoEjecucion,
  SimulacionCorte,
} from './types';
import { PERSONAS_DISPONIBLES } from './utils/personas';
import {
  avanzarSimulacion,
  getAlertaDetalle,
  getAlertas,
  getCorte,
  procesarAlerta,
  reiniciarSimulacion,
  tomarDecision,
} from './api/client';
import { formatFecha } from './utils/formatters';

export const App: React.FC = () => {
  // 1. Estado de navegación y persona activa
  const [tabActiva, setTabActiva] = useState<TabId>('bandeja');
  const [personaActiva, setPersonaActiva] = useState<Persona>(PERSONAS_DISPONIBLES[0]);

  // 2. Estado de reloj y alertas
  const [corte, setCorte] = useState<SimulacionCorte | null>(null);
  const [loadingReloj, setLoadingReloj] = useState(false);
  const [alertas, setAlertas] = useState<AlertaVista[]>([]);
  const [loadingAlertas, setLoadingAlertas] = useState(true);

  // 3. Modales y paneles interactivos
  const [alertaDetalle, setAlertaDetalle] = useState<AlertaVista | null>(null);
  const [decisionModal, setDecisionModal] = useState<{
    alertaVista: AlertaVista;
    modo: 'aprobar' | 'editar' | 'rechazar';
  } | null>(null);

  const [chatAbierto, setChatAbierto] = useState(false);
  const [chatPrompt, setChatPrompt] = useState<string | undefined>(undefined);
  const [alertaIdParaBitacora, setAlertaIdParaBitacora] = useState<string | undefined>(undefined);

  // Conjunto de IDs de alertas en proceso
  const [procesandoIds, setProcesandoIds] = useState<Set<string>>(new Set());

  // Cargar estado inicial del corte y alertas
  const fetchEstado = useCallback(async () => {
    try {
      setLoadingReloj(true);
      const corteData = await getCorte();
      setCorte(corteData);

      setLoadingAlertas(true);
      const alertasData = await getAlertas(undefined, corteData.corte);
      setAlertas(alertasData);
    } catch (err: any) {
      console.error('Error cargando estado inicial:', err);
      toast.error('Error conectando con la API de Centinela: ' + err.message);
    } finally {
      setLoadingReloj(false);
      setLoadingAlertas(false);
    }
  }, []);

  useEffect(() => {
    fetchEstado();
  }, [fetchEstado]);

  // Polling inteligente cada 3 segundos si hay alertas en 'nueva' o 'en_analisis'
  useEffect(() => {
    const hayEnProceso = alertas.some(
      (a) =>
        a.alerta.estado === 'nueva' ||
        a.alerta.estado === 'en_analisis' ||
        procesandoIds.has(a.alerta.alerta_id)
    );

    if (!hayEnProceso) return;

    const interval = setInterval(async () => {
      try {
        if (!corte) return;
        const alertasActualizadas = await getAlertas(undefined, corte.corte);
        setAlertas(alertasActualizadas);
      } catch (e) {
        // silencioso en polling
      }
    }, 3000);

    return () => clearInterval(interval);
  }, [alertas, corte, procesandoIds]);

  // Avanzar reloj
  const handleAvanzarReloj = async (dias: number) => {
    try {
      setLoadingReloj(true);
      const res = await avanzarSimulacion(dias);
      toast.success(
        `Reloj avanzado ${dias} día(s) al corte: ${formatFecha(res.corte)}`
      );
      await fetchEstado();
    } catch (err: any) {
      toast.error(err.message || 'Error al avanzar simulación');
    } finally {
      setLoadingReloj(false);
    }
  };

  // Reiniciar reloj
  const handleReiniciarReloj = async () => {
    try {
      setLoadingReloj(true);
      const res = await reiniciarSimulacion();
      toast.info(`Reloj restablecido al corte inicial: ${formatFecha(res.corte)}`);
      await fetchEstado();
    } catch (err: any) {
      toast.error(err.message || 'Error al reiniciar simulación');
    } finally {
      setLoadingReloj(false);
    }
  };

  // Procesar alerta con pipeline de agentes
  const handleProcesarAlerta = async (alertaId: string) => {
    try {
      setProcesandoIds((prev) => new Set(prev).add(alertaId));
      toast.info(`Iniciando pipeline de agentes (Vigía → Analista → Estratega) para ${alertaId}`);

      const vistaActualizada = await procesarAlerta(alertaId, corte?.corte);

      setAlertas((prev) =>
        prev.map((a) => (a.alerta.alerta_id === alertaId ? vistaActualizada : a))
      );

      if (alertaDetalle?.alerta.alerta_id === alertaId) {
        setAlertaDetalle(vistaActualizada);
      }

      toast.success(`Propuesta generada para ${alertaId}. Lista para decisión humana.`);
    } catch (err: any) {
      toast.error(err.message || `Error procesando alerta ${alertaId}`);
    } finally {
      setProcesandoIds((prev) => {
        const next = new Set(prev);
        next.delete(alertaId);
        return next;
      });
    }
  };

  // Enviar decisión humana (aprobar, editar, rechazar)
  const handleSubmitDecision = async (
    alertaId: string,
    request: DecisionRequest,
    versionPrevia?: number
  ): Promise<{ resultado: ResultadoEjecucion }> => {
    const res = await tomarDecision(alertaId, request, versionPrevia);

    // Actualizar lista local
    setAlertas((prev) =>
      prev.map((a) => {
        if (a.alerta.alerta_id === alertaId) {
          return {
            ...a,
            alerta: res.alerta,
          };
        }
        return a;
      })
    );

    if (alertaDetalle?.alerta.alerta_id === alertaId) {
      setAlertaDetalle((prev) => (prev ? { ...prev, alerta: res.alerta } : null));
    }

    if (request.decision === 'aprobar') {
      toast.success(`Alerta ${alertaId} aprobada y ejecutada en Sandbox con éxito.`);
    } else if (request.decision === 'editar') {
      toast.success(`Parámetros ajustados y ejecutados para ${alertaId}.`);
    } else {
      toast.info(`Propuesta ${alertaId} rechazada. Retroalimentación almacenada.`);
    }

    return { resultado: res.resultado };
  };

  const handleVerBitacora = (alertaId: string) => {
    setAlertaIdParaBitacora(alertaId);
    setTabActiva('bitacora');
    setAlertaDetalle(null);
  };

  const handlePreguntarEnChat = (pregunta: string) => {
    setChatPrompt(pregunta);
    setChatAbierto(true);
  };

  const titulosPantallas: Record<TabId, string> = {
    bandeja: 'Bandeja de Decisiones Operacionales',
    bitacora: 'Bitácora Inmutable & Auditoría Criptográfica',
    metricas: 'Costo de Inferencia & Retorno de Inversión (ROI)',
    configuracion: 'Configuración de KPIs y Niveles de Autonomía',
  };

  const pendientesCount = alertas.filter(
    (a) =>
      a.alerta.estado === 'propuesta' ||
      a.alerta.estado === 'nueva' ||
      a.alerta.estado === 'en_analisis'
  ).length;

  return (
    <div className="min-h-screen bg-[#f8fafc] text-slate-900 flex font-sans antialiased selection:bg-slate-900 selection:text-white">
      <Toaster position="top-right" richColors />

      {/* 1. Barra Lateral de Navegación */}
      <Sidebar
        tabActiva={tabActiva}
        onSelectTab={setTabActiva}
        personaActiva={personaActiva}
        onSelectPersona={(p) => {
          setPersonaActiva(p);
          toast.info(`Rol activo cambiado a: ${p.nombre} (${p.cargo})`);
        }}
        pendientesCount={pendientesCount}
      />

      {/* 2. Área Principal de Contenido */}
      <div className="flex-1 flex flex-col min-w-0">
        {/* Topbar con reloj simulado y toggle de chat */}
        <Topbar
          corte={corte}
          loadingReloj={loadingReloj}
          onAvanzar={handleAvanzarReloj}
          onReiniciar={handleReiniciarReloj}
          chatAbierto={chatAbierto}
          onToggleChat={() => setChatAbierto(!chatAbierto)}
          tituloPantalla={titulosPantallas[tabActiva]}
        />

        {/* Contenido según la pestaña activa */}
        <main className="flex-1 p-6 md:p-8 max-w-7xl w-full mx-auto">
          {tabActiva === 'bandeja' && (
            <BandejaDecisiones
              alertas={alertas}
              loading={loadingAlertas}
              onSelectAlerta={(av) => setAlertaDetalle(av)}
              onProcesarAlerta={handleProcesarAlerta}
              onAbrirDecision={(av, modo) =>
                setDecisionModal({ alertaVista: av, modo })
              }
              onVerBitacora={handleVerBitacora}
              procesandoIds={procesandoIds}
            />
          )}

          {tabActiva === 'bitacora' && (
            <BitacoraViewer
              alertas={alertas}
              alertaSeleccionadaId={alertaIdParaBitacora}
            />
          )}

          {tabActiva === 'metricas' && <CostoRoiPanel alertas={alertas} />}

          {tabActiva === 'configuracion' && <ConfiguracionPanel />}
        </main>
      </div>

      {/* 3. Panel Lateral Flotante de Chat Anclado */}
      {chatAbierto && (
        <ChatSoporte
          alertaId={alertaDetalle?.alerta.alerta_id}
          onClose={() => setChatAbierto(false)}
          initialPrompt={chatPrompt}
        />
      )}

      {/* 4. Modal de Detalle de Alerta en 3 Niveles */}
      {alertaDetalle && (
        <DetalleAlertaModal
          alertaVista={alertaDetalle}
          onClose={() => setAlertaDetalle(null)}
          onAbrirDecision={(av, modo) =>
            setDecisionModal({ alertaVista: av, modo })
          }
          onProcesarAlerta={handleProcesarAlerta}
          onVerBitacora={handleVerBitacora}
          onPreguntarEnChat={handlePreguntarEnChat}
          estaProcesando={procesandoIds.has(alertaDetalle.alerta.alerta_id)}
        />
      )}

      {/* 5. Modal de Decisión Humana (HITL) */}
      {decisionModal && (
        <DecisionModal
          alertaVista={decisionModal.alertaVista}
          modo={decisionModal.modo}
          personaActiva={personaActiva}
          onClose={() => setDecisionModal(null)}
          onSubmitDecision={handleSubmitDecision}
          onExito={() => {
            // El usuario cerrará manualmente para ver los borradores
          }}
        />
      )}
    </div>
  );
};

export default App;
