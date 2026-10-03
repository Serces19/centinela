// frontend/src/utils/formatters.ts

/**
 * Formatea un valor numérico a pesos colombianos (COP) con separador de miles por punto.
 * Ejemplo: 115400000 -> "$115.400.000 COP"
 */
export function formatCOP(monto: number): string {
  if (isNaN(monto) || monto === null || monto === undefined) return '$0 COP';
  const entero = Math.round(monto);
  const formateado = new Intl.NumberFormat('es-CO', {
    style: 'currency',
    currency: 'COP',
    maximumFractionDigits: 0,
  }).format(entero);

  // Normalizar para mostrar siempre $X.XXX.XXX COP
  return `${formateado} COP`.replace('COP COP', 'COP');
}

/**
 * Formatea un valor numérico abreviado para badges o gráficos (ej. "$115.4 M COP")
 */
export function formatCOPSimple(monto: number): string {
  if (!monto) return '$0 COP';
  if (monto >= 1_000_000_000) {
    return `$${(monto / 1_000_000_000).toFixed(1)} mil M COP`;
  }
  if (monto >= 1_000_000) {
    return `$${(monto / 1_000_000).toFixed(1)} M COP`;
  }
  return formatCOP(monto);
}

/**
 * Formatea una fecha ISO o YYYY-MM-DD a formato amigable de negocio: "18 Jun 2026".
 */
export function formatFecha(fechaStr?: string): string {
  if (!fechaStr) return '--';
  try {
    const partes = fechaStr.split('T')[0].split('-');
    if (partes.length === 3) {
      const year = parseInt(partes[0], 10);
      const month = parseInt(partes[1], 10) - 1;
      const day = parseInt(partes[2], 10);
      const d = new Date(year, month, day);
      return d.toLocaleDateString('es-CO', {
        day: 'numeric',
        month: 'short',
        year: 'numeric',
      });
    }
    const d = new Date(fechaStr);
    return d.toLocaleDateString('es-CO', {
      day: 'numeric',
      month: 'short',
      year: 'numeric',
    });
  } catch {
    return fechaStr;
  }
}

/**
 * Formatea hora: "02:45 PM".
 */
export function formatHora(fechaStr?: string): string {
  if (!fechaStr) return '';
  try {
    const d = new Date(fechaStr);
    return d.toLocaleTimeString('es-CO', {
      hour: '2-digit',
      minute: '2-digit',
    });
  } catch {
    return '';
  }
}
