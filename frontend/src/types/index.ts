// frontend/src/types/index.ts

export type Severidad = 'critica' | 'alta' | 'media' | 'baja';

export type EstadoAlerta =
  | 'nueva'
  | 'en_analisis'
  | 'propuesta'
  | 'sin_evidencia'
  | 'aprobada'
  | 'rechazada'
  | 'ejecutada'
  | 'fallida';

export type Kpi =
  | 'margen_pct'
  | 'saldo_vencido'
  | 'dias_pago_prom'
  | 'cobertura_dias'
  | 'descuento_en_exceso'
  | 'veces_intervalo_habitual'
  | 'venta_bajo_costo';

export interface EntidadRef {
  tipo: string;
  id: string;
}

export interface Hallazgo {
  hallazgo_id: string;
  kpi: Kpi;
  regla: string;
  severidad: Severidad;
  entidades: EntidadRef[];
  valor_observado: number;
  umbral: number;
  corte: string;
  dinero_en_riesgo_cop: number;
  consulta_ids: string[];
  huella_causa: string;
}

export interface Alerta {
  schema_version: string;
  alerta_id: string;
  estado: EstadoAlerta;
  huella_causa: string;
  hallazgos: Hallazgo[];
  severidad: Severidad;
  dinero_en_riesgo_cop: number;
  corte_creacion: string;
  creada_en: string;
  version: number;
}

export type Unidad = 'COP' | '%' | 'pp' | 'dias' | 'unidades' | 'veces' | 'lineas';

export interface CifraTrazable {
  etiqueta: string;
  valor: number;
  unidad: Unidad;
  consulta_id: string;
}

export interface CitaPolitica {
  documento: 'FIN-POL-004' | 'COM-POL-002' | 'OPE-POL-007';
  seccion: string;
  fragmento_hash: string;
}

export interface DiagnosticoLLM {
  resumen: string;
  causa_raiz: string;
  cifras: CifraTrazable[];
  politicas: CitaPolitica[];
  supuestos: string[];
  evidencia_suficiente: boolean;
  confianza: number;
}

export type ParametrosAccion =
  | {
      tipo: 'ajuste_precio';
      skus: string[];
      pct_ajuste: number;
    }
  | {
      tipo: 'contacto_cartera';
      cliente_id: string;
      nivel: 'recordatorio' | 'llamada_acuerdo' | 'solo_contado' | 'bloqueo_despachos';
    }
  | {
      tipo: 'expeditar_oc';
      oc_id: string;
      proveedor_id: string;
      sku: string;
      bodega_id: string;
      via: 'contactar_proveedor' | 'proveedor_alterno' | 'entrega_parcial';
    }
  | {
      tipo: 'revision_descuentos';
      vendedor_id: string;
      medida: 'revision_previa_cotizacion' | 'suspender_facultad_cotizar';
    }
  | {
      tipo: 'reactivar_cliente';
      cliente_id: string;
      vendedor_id: string;
      canal: 'visita' | 'llamada' | 'oferta';
    }
  | {
      tipo: 'corregir_venta_bajo_costo';
      skus: string[];
    };

export interface ImpactoCalculado {
  valor_cop: number;
  horizonte: 'mensual' | 'unico';
  metodo: string;
  intervalo_cop?: [number, number] | null;
  consulta_ids: string[];
}

export interface Accion {
  accion_id: string;
  titulo: string;
  razon: string;
  parametros: ParametrosAccion;
  confianza: number;
  impacto: ImpactoCalculado;
}

export interface Propuesta {
  schema_version: string;
  alerta_id: string;
  diagnostico: DiagnosticoLLM;
  acciones: Accion[];
  modelo: string;
  generada_en: string;
}

export interface ConsultaRegistrada {
  consulta_id: string;
  vista: string;
  sql_renderizado: string;
  corte: string;
  filas: number;
  resultado_hash: string;
  ejecutada_en: string;
}

export interface AlertaVista {
  alerta: Alerta;
  nombres_resueltos: Record<string, string>;
  propuesta: Propuesta | null;
  consultas: (string | ConsultaRegistrada)[];
}

export interface Borrador {
  artefacto_id: string;
  accion_id: string;
  tipo: 'correo' | 'tarea' | 'orden_compra';
  destino: string;
  contenido: string;
  estado: 'borrador';
}

export interface ResultadoEjecucion {
  alerta_id: string;
  borradores: Borrador[];
  ok: boolean;
  error?: string | null;
}

export interface DecisionRequest {
  decision: 'aprobar' | 'editar' | 'rechazar';
  accion_ids: string[];
  ediciones?: Record<string, ParametrosAccion>;
  motivo?: string | null;
  decidido_por: string;
}

export type EventoBitacora =
  | 'alerta_creada'
  | 'analisis_completo'
  | 'propuesta_generada'
  | 'decision_humana'
  | 'accion_ejecutada'
  | 'guardrail_intervino'
  | 'error';

export interface EntradaBitacora {
  schema_version: string;
  alerta_id: string;
  seq: number;
  evento: EventoBitacora;
  actor: string;
  payload: Record<string, any>;
  ts: string;
  hash_prev: string;
  hash: string;
}

export interface BitacoraResponse {
  alerta_id: string;
  total_entradas: number;
  cadena_valida: boolean;
  entradas: EntradaBitacora[];
}

export interface SimulacionCorte {
  corte: string;
  corte_inicial_limpio: string;
  corte_maximo: string;
  run_id: string;
  actualizado_en: string;
}

export interface SimulacionResp {
  run_id: string;
  corte: string;
  dias_avanzados: number;
  pipeline_disparado: boolean;
}

export interface Persona {
  id: string;
  nombre: string;
  cargo: string;
  area: string;
  avatar: string;
  badgeColor: string;
}

export interface ChatMessage {
  id: string;
  sender: 'user' | 'assistant';
  content: string;
  cifras?: CifraTrazable[];
  consultas?: string[];
  costo_usd?: number;
  timestamp: string;
  isStreaming?: boolean;
}
