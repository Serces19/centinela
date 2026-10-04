// frontend/src/api/client.ts
import {
  Alerta,
  AlertaVista,
  BitacoraResponse,
  CifraTrazable,
  DecisionRequest,
  ResultadoEjecucion,
  SimulacionCorte,
  SimulacionResp,
} from '../types';

const API_BASE_URL =
  import.meta.env.VITE_API_URL ||
  'https://kshttlmqbtzbjc5a73m5v6rfre0qimbv.lambda-url.us-east-1.on.aws';

const API_KEY = import.meta.env.VITE_API_KEY || '';

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

/**
 * Consulta la fecha de corte actual y configuración del reloj.
 */
export async function getCorte(): Promise<SimulacionCorte> {
  const resp = await fetch(`${API_BASE_URL}/simulacion/corte`, {
    headers: getHeaders(),
  });
  if (!resp.ok) {
    throw new Error(`Error ${resp.status} al consultar corte de simulación`);
  }
  return resp.json();
}

/**
 * Avanza el reloj de simulación temporal.
 */
export async function avanzarSimulacion(dias: number): Promise<SimulacionResp> {
  const resp = await fetch(`${API_BASE_URL}/simulacion/avanzar?dias=${dias}`, {
    method: 'POST',
    headers: getHeaders(),
  });
  if (!resp.ok) {
    const err = await resp.json().catch(() => ({ detail: 'Error desconocido' }));
    throw new Error(err.detail || `Error ${resp.status} al avanzar simulación`);
  }
  return resp.json();
}

/**
 * Reinicia el reloj de simulación al corte inicial limpio (2026-06-18).
 */
export async function reiniciarSimulacion(): Promise<SimulacionResp> {
  const resp = await fetch(`${API_BASE_URL}/simulacion/reiniciar`, {
    method: 'POST',
    headers: getHeaders(),
  });
  if (!resp.ok) {
    const err = await resp.json().catch(() => ({ detail: 'Error desconocido' }));
    throw new Error(err.detail || `Error ${resp.status} al reiniciar simulación`);
  }
  return resp.json();
}

/**
 * Lista alertas enriquecidas con nombres resueltos (AlertaVista).
 */
export async function getAlertas(estado?: string, corte?: string): Promise<AlertaVista[]> {
  const params = new URLSearchParams();
  if (estado) params.append('estado', estado);
  if (corte) params.append('corte', corte);

  const url = `${API_BASE_URL}/alertas${params.toString() ? `?${params.toString()}` : ''}`;
  const resp = await fetch(url, {
    headers: getHeaders(),
  });
  if (!resp.ok) {
    throw new Error(`Error ${resp.status} al listar alertas`);
  }
  return resp.json();
}

/**
 * Consulta el detalle enriquecido de una alerta por ID.
 */
export async function getAlertaDetalle(alertaId: string): Promise<AlertaVista> {
  const resp = await fetch(`${API_BASE_URL}/alertas/${alertaId}`, {
    headers: getHeaders(),
  });
  if (!resp.ok) {
    throw new Error(`Error ${resp.status} al obtener detalle de la alerta ${alertaId}`);
  }
  return resp.json();
}

/**
 * Dispara el pipeline de agentes para analizar una alerta.
 */
export async function procesarAlerta(alertaId: string, corte?: string): Promise<AlertaVista> {
  const url = `${API_BASE_URL}/alertas/${alertaId}/procesar${corte ? `?corte=${corte}` : ''}`;
  const resp = await fetch(url, {
    method: 'POST',
    headers: getHeaders(),
  });
  if (!resp.ok) {
    const err = await resp.json().catch(() => ({ detail: 'Error al procesar alerta' }));
    throw new Error(err.mensaje || err.detail || `Error ${resp.status} al procesar alerta`);
  }
  return resp.json();
}

/**
 * Toma una decisión humana (aprobar, editar, rechazar).
 */
export async function tomarDecision(
  alertaId: string,
  request: DecisionRequest,
  versionPrevia?: number
): Promise<{ alerta: Alerta; resultado: ResultadoEjecucion }> {
  const idempotencyKey = `idem-${alertaId}-${request.decision}-${Date.now()}`;
  const headers = getHeaders({
    'Idempotency-Key': idempotencyKey,
    ...(versionPrevia !== undefined ? { 'If-Match': `"${versionPrevia}"` } : {}),
  });

  const resp = await fetch(`${API_BASE_URL}/alertas/${alertaId}/decision`, {
    method: 'POST',
    headers,
    body: JSON.stringify(request),
  });

  if (!resp.ok) {
    const err = await resp.json().catch(() => ({ mensaje: 'Error al tomar decisión' }));
    const errorObj = new Error(err.mensaje || `Error ${resp.status} al registrar decisión`);
    (errorObj as any).status = resp.status;
    (errorObj as any).codigo = err.codigo;
    throw errorObj;
  }
  return resp.json();
}

/**
 * Consulta y verifica la bitácora inmutable de una alerta.
 */
export async function getBitacora(alertaId: string, verificar = true): Promise<BitacoraResponse> {
  const resp = await fetch(
    `${API_BASE_URL}/bitacora/${alertaId}?verificar=${verificar ? 'true' : 'false'}`,
    {
      headers: getHeaders(),
    }
  );
  if (!resp.ok) {
    throw new Error(`Error ${resp.status} al consultar bitácora para ${alertaId}`);
  }
  return resp.json();
}

/**
 * Realiza una consulta con streaming SSE al endpoint POST /chat.
 */
export async function streamChat(
  params: { alerta_id?: string; mensaje: string },
  callbacks: {
    onToken: (token: string) => void;
    onCifra?: (cifra: CifraTrazable) => void;
    onFin?: (fin: { consulta_ids: string[]; costo_usd: number }) => void;
    onError?: (error: string) => void;
  }
): Promise<void> {
  const resp = await fetch(`${API_BASE_URL}/chat`, {
    method: 'POST',
    headers: getHeaders({
      Accept: 'text/event-stream',
    }),
    body: JSON.stringify({
      alerta_id: params.alerta_id || null,
      mensaje: params.mensaje,
    }),
  });

  if (!resp.ok || !resp.body) {
    throw new Error(`Error ${resp.status} al conectar al chat`);
  }

  const reader = resp.body.getReader();
  const decoder = new TextDecoder('utf-8');
  let buffer = '';

  try {
    while (true) {
      const { done, value } = await reader.read();
      if (done) break;

      buffer += decoder.decode(value, { stream: true });
      const lines = buffer.split('\n\n');
      buffer = lines.pop() || '';

      for (const line of lines) {
        const trimmed = line.trim();
        if (trimmed.startsWith('data:')) {
          const jsonStr = trimmed.slice(5).trim();
          if (!jsonStr) continue;

          try {
            const eventData = JSON.parse(jsonStr);
            if (eventData.evento === 'token') {
              callbacks.onToken(eventData.texto);
            } else if (eventData.evento === 'cifra' && callbacks.onCifra) {
              callbacks.onCifra(eventData.cifra);
            } else if (eventData.evento === 'fin' && callbacks.onFin) {
              callbacks.onFin({
                consulta_ids: eventData.consulta_ids || [],
                costo_usd: eventData.costo_usd || 0,
              });
            } else if (eventData.evento === 'error' && callbacks.onError) {
              callbacks.onError(eventData.mensaje || 'Error en streaming del chat');
            }
          } catch (e) {
            console.warn('Error parseando evento SSE:', jsonStr, e);
          }
        }
      }
    }
  } catch (err: any) {
    if (callbacks.onError) {
      callbacks.onError(err.message || 'Error en lectura de flujo');
    }
  }
}
