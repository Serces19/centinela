// frontend/src/utils/alertas.ts
// Utilidades genéricas de presentación de alertas. No dependen de entidades ni escenarios concretos:
// todo se deriva de la familia de la causa (`huella_causa`), la severidad y el estado que entrega el backend.
import { AlertaVista, EstadoAlerta, Severidad } from '../types';

export interface FamiliaInfo {
  etiqueta: string;
  titulo: (nombre?: string) => string;
  badge: string; // clases de color del distintivo
}

const FAMILIAS: Record<string, FamiliaInfo> = {
  costo: {
    etiqueta: 'Costo y margen',
    titulo: (n) => `Alza de costo del proveedor${n ? ` ${n}` : ''} sin ajuste de precios`,
    badge: 'bg-rose-50 text-rose-700 border-rose-200',
  },
  margen: {
    etiqueta: 'Margen',
    titulo: (n) => `Caída de margen en la línea${n ? ` ${n}` : ''}`,
    badge: 'bg-rose-50 text-rose-700 border-rose-200',
  },
  saldo_vencido: {
    etiqueta: 'Cartera',
    titulo: (n) => `Cartera vencida${n ? `: ${n}` : ''}`,
    badge: 'bg-amber-50 text-amber-800 border-amber-200',
  },
  cobertura_dias: {
    etiqueta: 'Inventario',
    titulo: (n) => `Riesgo de quiebre de inventario${n ? `: ${n}` : ''}`,
    badge: 'bg-rose-50 text-rose-700 border-rose-200',
  },
  descuento_en_exceso: {
    etiqueta: 'Descuentos',
    titulo: (n) => `Descuentos fuera de política${n ? `: ${n}` : ''}`,
    badge: 'bg-amber-50 text-amber-800 border-amber-200',
  },
  veces_intervalo_habitual: {
    etiqueta: 'Clientes',
    titulo: (n) => `Cliente que dejó de comprar${n ? `: ${n}` : ''}`,
    badge: 'bg-purple-50 text-purple-700 border-purple-200',
  },
  venta_bajo_costo: {
    etiqueta: 'Precios',
    titulo: (n) => `Ventas por debajo del costo${n ? `: ${n}` : ''}`,
    badge: 'bg-indigo-50 text-indigo-700 border-indigo-200',
  },
};

const FAMILIA_DEFECTO: FamiliaInfo = {
  etiqueta: 'Operación',
  titulo: () => 'Desviación operacional detectada',
  badge: 'bg-slate-50 text-slate-700 border-slate-200',
};

export const familiaDe = (huella: string): string => huella.split('|')[0];

export const infoFamilia = (huella: string): FamiliaInfo => FAMILIAS[familiaDe(huella)] ?? FAMILIA_DEFECTO;

/** Título de negocio derivado de la causa y de la entidad raíz (nombre resuelto si existe). */
export function tituloAlerta(item: AlertaVista): string {
  const raiz = item.alerta.huella_causa.split('|')[1];
  return infoFamilia(item.alerta.huella_causa).titulo(item.nombres_resueltos[raiz] ?? raiz);
}

export const ESTADOS_PENDIENTES: EstadoAlerta[] = ['nueva', 'en_analisis', 'propuesta'];

export const esPendiente = (item: AlertaVista): boolean => ESTADOS_PENDIENTES.includes(item.alerta.estado);

export const ETIQUETA_ESTADO: Record<EstadoAlerta, string> = {
  nueva: 'Por analizar',
  en_analisis: 'Analizando',
  propuesta: 'Lista para decidir',
  sin_evidencia: 'Sin evidencia',
  aprobada: 'Aprobada',
  rechazada: 'Rechazada',
  ejecutada: 'Ejecutada',
  fallida: 'Fallida',
};

export const ETIQUETA_PASO: Record<string, string> = {
  analista: 'El Analista investiga la causa',
  estratega: 'El Estratega arma las acciones',
};

export const ETIQUETA_SEVERIDAD: Record<Severidad, string> = {
  critica: 'Crítica',
  alta: 'Alta',
  media: 'Media',
  baja: 'Baja',
};

/** Severidad: color y también símbolo, para no depender solo del color. */
export const ESTILO_SEVERIDAD: Record<Severidad, { clases: string; simbolo: string }> = {
  critica: { clases: 'bg-rose-100 text-rose-800 border-rose-200', simbolo: '▲▲' },
  alta: { clases: 'bg-amber-100 text-amber-800 border-amber-200', simbolo: '▲' },
  media: { clases: 'bg-sky-100 text-sky-800 border-sky-200', simbolo: '●' },
  baja: { clases: 'bg-slate-100 text-slate-700 border-slate-200', simbolo: '○' },
};
