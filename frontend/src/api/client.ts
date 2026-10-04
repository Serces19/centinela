// frontend/src/api/client.ts
import {
  Alerta,
  AlertaVista,
  BitacoraResponse,
  ChatEvento,
  ConfiguracionVigia,
  ConsultaRegistrada,
  DecisionRequest,
  ResultadoEjecucion,
  ResumenAlertas,
  ResumenCostos,
  SimulacionCorte,
  SimulacionResp,
} from '../types';

const API_BASE_URL = (import.meta.env.VITE_API_URL as string | undefined)?.replace(/\/$/, '') || '';
const API_KEY = (import.meta.env.VITE_API_KEY as string | undefined) || '';

function generateRequestId(): string {
  return `req-ui-${Math.random().toString(36).substring(2, 10)}`;
}

function getHeaders(customHeaders: Record<string, string> = {}): Record<string, string> {
  return {
    'Content-Type': 'application/json',
    'x-request-id': generateRequestId(),
    'x-api-key': API_KEY,
    ...customHeaders,
  };
}

export class ApiError extends Error {
  status: number;
  codigo?: string;
  constructor(mensaje: string, status: number, codigo?: string) {
    super(mensaje);
    this.status = status;
    this.codigo = codigo;
  }
}

async function request<T>(path: string, init: RequestInit = {}, headers: Record<string, string> = {}): Promise<T> {
  const resp = await fetch(`${API_BASE_URL}${path}`, { ...init, headers: getHeaders(headers) });
  if (!resp.ok) {
    const err = await resp.json().catch(() => ({}));
    throw new ApiError(err.mensaje || err.detail || `Error ${resp.status} en ${path}`, resp.status, err.codigo);
  }
  return resp.json();
}

export const getCorte = () => request<SimulacionCorte>('/simulacion/corte');

export const avanzarSimulacion = (dias: number) =>
  request<SimulacionResp>(`/simulacion/avanzar?dias=${dias}`, { method: 'POST' });

export const reiniciarSimulacion = () => request<SimulacionResp>('/simulacion/reiniciar', { method: 'POST' });

export const getAlertas = (estado?: string) =>
  request<AlertaVista[]>(`/alertas${estado ? `?estado=${encodeURIComponent(estado)}` : ''}`);

export const getResumen = () => request<ResumenAlertas>('/alertas/resumen');

export const getAlertaDetalle = (alertaId: string) => request<AlertaVista>(`/alertas/${alertaId}`);

export const procesarAlerta = (alertaId: string) =>
  request<AlertaVista>(`/alertas/${alertaId}/procesar`, { method: 'POST' });

export const reabrirAlerta = (alertaId: string, actor: string) =>
  request<AlertaVista>(`/alertas/${alertaId}/reabrir?actor=${encodeURIComponent(actor)}`, { method: 'POST' });

export const getConsulta = (consultaId: string) => request<ConsultaRegistrada>(`/consultas/${consultaId}`);

export const getCostos = () => request<ResumenCostos>('/costos');

export const getConfig = () => request<ConfiguracionVigia>('/config');

export const putConfig = (cambios: {
  umbrales?: Record<string, number>;
  autonomia?: Record<string, string>;
  actor: string;
}) => request<ConfiguracionVigia>('/config', { method: 'PUT', body: JSON.stringify(cambios) });

export function tomarDecision(
  alertaId: string,
  decision: DecisionRequest,
  versionPrevia?: number
): Promise<{ alerta: Alerta; resultado: ResultadoEjecucion }> {
  return request(
    `/alertas/${alertaId}/decision`,
    { method: 'POST', body: JSON.stringify(decision) },
    {
      'Idempotency-Key': `idem-${alertaId}-${decision.decision}-${Date.now()}`,
      ...(versionPrevia !== undefined ? { 'If-Match': `"${versionPrevia}"` } : {}),
    }
  );
}

/** Auditoría de una alerta (con verificación de la cadena) o general si no se indica alerta. */
export function getBitacora(opts: { alertaId?: string; actor?: string; evento?: string; limite?: number } = {}) {
  const p = new URLSearchParams();
  if (opts.alertaId) {
    p.set('alerta_id', opts.alertaId);
    p.set('verificar', 'true');
  }
  if (opts.actor) p.set('actor', opts.actor);
  if (opts.evento) p.set('evento', opts.evento);
  if (opts.limite) p.set('limite', String(opts.limite));
  return request<BitacoraResponse>(`/bitacora${p.toString() ? `?${p.toString()}` : ''}`);
}

/** Chat con streaming SSE. Cada evento llega ya verificado por el servidor. */
export async function streamChat(
  params: { alerta_id?: string; mensaje: string },
  onEvento: (ev: ChatEvento) => void
): Promise<void> {
  const resp = await fetch(`${API_BASE_URL}/chat`, {
    method: 'POST',
    headers: getHeaders({ Accept: 'text/event-stream' }),
    body: JSON.stringify({ alerta_id: params.alerta_id || null, mensaje: params.mensaje }),
  });
  if (!resp.ok || !resp.body) {
    throw new ApiError(`Error ${resp.status} al conectar con el chat`, resp.status);
  }
  const reader = resp.body.getReader();
  const decoder = new TextDecoder('utf-8');
  let buffer = '';
  while (true) {
    const { done, value } = await reader.read();
    if (done) break;
    buffer += decoder.decode(value, { stream: true });
    const bloques = buffer.split('\n\n');
    buffer = bloques.pop() || '';
    for (const bloque of bloques) {
      const linea = bloque.trim();
      if (!linea.startsWith('data:')) continue;
      try {
        onEvento(JSON.parse(linea.slice(5).trim()) as ChatEvento);
      } catch (e) {
        console.warn('Evento SSE ilegible:', linea, e);
      }
    }
  }
}
