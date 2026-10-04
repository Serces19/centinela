// frontend/src/utils/alertas.ts
import { AlertaVista, Kpi } from '../types';

export interface EscenarioInfo {
  codigo: 'S1' | 'S2' | 'S3' | 'S4' | 'S5' | 'S6';
  tag: string;
  titulo: string;
  badgeBg: string;
  badgeText: string;
  badgeBorder: string;
}

/**
 * Fecha inicial de vigilancia limpia de Centinela.
 */
export const CORTE_INICIAL_LIMPIO = '2026-06-18';
export const CORTE_HITO_S1 = '2026-08-15';
export const CORTE_HITO_CIERRE = '2026-09-30';

/**
 * Determina si la fecha corresponde al corte inicial limpio.
 */
export function esCorteInicialLimpio(fechaCorte?: string): boolean {
  if (!fechaCorte) return true;
  const iso = fechaCorte.split('T')[0];
  return iso <= CORTE_INICIAL_LIMPIO;
}

/**
 * Identifica si una alerta corresponde a uno de los escenarios estratégicos del reto
 * (S1 a S6) con impacto financiero directo.
 */
export function clasificarEscenario(item: AlertaVista): EscenarioInfo | null {
  const alerta = item.alerta;
  const primerHallazgo = alerta.hallazgos[0];
  if (!primerHallazgo) return null;

  const regla = primerHallazgo.regla || '';
  const kpi = primerHallazgo.kpi;
  const entidadesIds = (primerHallazgo.entidades || []).map((e) => e.id);

  // S1: Incremento costo proveedor PR08 (+25%) y caída de margen
  if (
    regla.includes('costo') ||
    kpi === 'margen_pct' ||
    entidadesIds.includes('PR08') ||
    entidadesIds.includes('P0021')
  ) {
    return {
      codigo: 'S1',
      tag: 'S1 · Costo Proveedor',
      titulo: 'Incremento de costo proveedor PR08 (+25%) sin ajuste de precio de lista',
      badgeBg: 'bg-rose-50',
      badgeText: 'text-rose-700',
      badgeBorder: 'border-rose-200',
    };
  }

  // S2: Deterioro cartera y mora sobre cupo cliente C0496
  if (entidadesIds.includes('C0496') || kpi === 'dias_pago_prom') {
    return {
      codigo: 'S2',
      tag: 'S2 · Riesgo Cartera',
      titulo: 'Deterioro severo en plazo de pago y mora prolongada sobre cupo (C0496)',
      badgeBg: 'bg-amber-50',
      badgeText: 'text-amber-800',
      badgeBorder: 'border-amber-200',
    };
  }

  // S3: Quiebre de inventario / Cobertura crítica P0119 en BOD-MDE
  if (
    regla.includes('cobertura') ||
    kpi === 'cobertura_dias' ||
    entidadesIds.includes('P0119') ||
    entidadesIds.includes('BOD-MDE')
  ) {
    return {
      codigo: 'S3',
      tag: 'S3 · Quiebre Stock',
      titulo: 'Riesgo inminente de quiebre de inventario (P0119 Gaseosa 3L en BOD-MDE)',
      badgeBg: 'bg-rose-50',
      badgeText: 'text-rose-700',
      badgeBorder: 'border-rose-200',
    };
  }

  // S4: Descuentos excesivos fuera de política vendedor V03
  if (
    regla.includes('descuento') ||
    kpi === 'descuento_en_exceso' ||
    entidadesIds.includes('V03')
  ) {
    return {
      codigo: 'S4',
      tag: 'S4 · Descuento Excesivo',
      titulo: 'Descuentos reiterados fuera de política comercial (Vendedor V03)',
      badgeBg: 'bg-amber-50',
      badgeText: 'text-amber-800',
      badgeBorder: 'border-amber-200',
    };
  }

  // S5: Inactividad prolongada y riesgo de fuga cliente C0061
  if (
    entidadesIds.includes('C0061') ||
    (kpi === 'veces_intervalo_habitual' && (primerHallazgo.valor_observado || 0) >= 10)
  ) {
    return {
      codigo: 'S5',
      tag: 'S5 · Fuga de Cliente',
      titulo: 'Inactividad crítica y riesgo inminente de fuga (Cliente Estratégico C0061)',
      badgeBg: 'bg-purple-50',
      badgeText: 'text-purple-700',
      badgeBorder: 'border-purple-200',
    };
  }

  // S6: Venta bajo costo reposición
  if (
    regla.includes('bajo_costo') ||
    kpi === 'venta_bajo_costo' ||
    entidadesIds.includes('P0097') ||
    entidadesIds.includes('P0006')
  ) {
    return {
      codigo: 'S6',
      tag: 'S6 · Venta Bajo Costo',
      titulo: 'Facturación por debajo del costo unitario de reposición',
      badgeBg: 'bg-indigo-50',
      badgeText: 'text-indigo-700',
      badgeBorder: 'border-indigo-200',
    };
  }

  return null;
}

/**
 * Determina si una alerta debe aparecer en la Bandeja Ejecutiva de Decisiones Estratégicas.
 * En el corte inicial limpio (2026-06-18), retorna false para mostrar estado limpio.
 */
export function esAlertaEstrategica(item: AlertaVista, fechaCorte?: string): boolean {
  if (esCorteInicialLimpio(fechaCorte)) {
    return false;
  }

  const escenario = clasificarEscenario(item);
  if (escenario) {
    return true;
  }

  // Alertas críticas con alto impacto financiero (>= $500.000 COP) creadas post-corte inicial
  const monto = item.alerta.dinero_en_riesgo_cop || 0;
  const severidad = item.alerta.severidad;
  const fechaCreacion = item.alerta.corte_creacion || '';

  if (fechaCreacion > CORTE_INICIAL_LIMPIO && severidad === 'critica' && monto >= 500_000) {
    return true;
  }

  return false;
}

/**
 * Genera el título amigable de negocio para una alerta.
 */
export function getTituloNegocio(kpi: Kpi, entidadNombre?: string, regla?: string): string {
  if (regla?.includes('costo')) {
    return 'Caída crítica de margen por incremento de costo de proveedor';
  }
  if (regla?.includes('cobertura')) {
    return 'Riesgo inminente de quiebre de inventario para demanda habitual';
  }
  if (regla?.includes('descuento')) {
    return 'Descuentos aplicados por encima del margen de política comercial';
  }
  if (regla?.includes('bajo_costo')) {
    return 'Detección de ventas facturadas por debajo del costo unitario reposición';
  }

  switch (kpi) {
    case 'margen_pct':
      return 'Caída crítica de margen por incremento de costo de proveedor';
    case 'saldo_vencido':
      return entidadNombre
        ? `Riesgo de cartera con mora prolongada: ${entidadNombre}`
        : 'Riesgo de cartera con mora prolongada sobre el cupo autorizado';
    case 'dias_pago_prom':
      return 'Deterioro severo en plazo promedio de cobro de cartera';
    case 'cobertura_dias':
      return 'Riesgo de quiebre de inventario inminente para demanda habitual';
    case 'descuento_en_exceso':
      return 'Descuentos aplicados por encima del margen de política comercial';
    case 'veces_intervalo_habitual':
      return entidadNombre
        ? `Inactividad prolongada y riesgo de fuga: ${entidadNombre}`
        : 'Inactividad prolongada y riesgo de fuga de cliente estratégico';
    case 'venta_bajo_costo':
      return 'Detección de ventas por debajo del costo unitario reposición';
    default:
      return 'Desviación operacional detectada en parámetros de negocio';
  }
}
