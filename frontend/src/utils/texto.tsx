// frontend/src/utils/texto.tsx
// Los textos de los agentes citan cifras con marcadores {c1}, {c2}... que apuntan a una lista de cifras.
// Aquí se sustituye cada marcador por su valor y, si se pasa `onCifra`, se vuelve un enlace a su consulta.
import React from 'react';
import { CifraTrazable } from '../types';

const miles = (x: number) => Math.round(x).toLocaleString('es-CO');
const dec = (x: number) => x.toLocaleString('es-CO', { minimumFractionDigits: 1, maximumFractionDigits: 1 });
const num = (x: number) => (Math.abs(x - Math.round(x)) < 0.05 ? miles(x) : dec(x));

/** Valor de una cifra con su unidad, en formato colombiano (igual que `formatear_cifra` del backend). */
export function formatCifra(c: CifraTrazable): string {
  const v = c.valor;
  switch (c.unidad) {
    case 'COP':
      return `$${miles(v)}`;
    case '%':
      return `${Math.abs(v - Math.round(v)) < 0.05 ? miles(v) : dec(v)} %`;
    case 'pp':
      return `${num(v)} pp`;
    case 'dias':
      return `${num(v)} ${Math.round(v) === 1 && v === Math.round(v) ? 'día' : 'días'}`;
    case 'veces':
      return `${num(v)} veces`;
    case 'lineas':
      return `${miles(v)} ${Math.round(v) === 1 ? 'línea' : 'líneas'}`;
    case 'semanas':
      return `${miles(v)} ${Math.round(v) === 1 ? 'semana' : 'semanas'}`;
    case 'pedidos':
      return `${miles(v)} ${Math.round(v) === 1 ? 'pedido' : 'pedidos'}`;
    case 'skus':
      return `${miles(v)} SKU`;
    case 'clientes':
      return `${miles(v)} ${Math.round(v) === 1 ? 'cliente' : 'clientes'}`;
    default:
      return `${num(v)} unidades`;
  }
}

const REPETIDA = /\b(SKU|líneas?|días?|semanas?|pedidos?|unidades|veces|clientes?)(?:\s+\1\b)+/gi;

/** Texto plano con los marcadores ya sustituidos (para títulos, toasts, etc.). */
export function textoPlano(texto: string, cifras: CifraTrazable[]): string {
  return texto
    .replace(/\{c(\d{1,2})\}/g, (m, n) => {
      const c = cifras[Number(n) - 1];
      return c ? formatCifra(c) : m;
    })
    .replace(REPETIDA, '$1')
    .replace('% %', '%');
}

interface TextoProps {
  texto: string;
  cifras: CifraTrazable[];
  onCifra?: (consultaId: string) => void;
  className?: string;
}

const UNIDAD_INICIAL = /^\s*(SKU|líneas?|días?|semanas?|pedidos?|unidades|veces|clientes?)\b/i;

/** Texto con cada cifra resaltada; al pasar el cursor muestra qué es y de qué consulta sale. */
export const TextoConCifras: React.FC<TextoProps> = ({ texto, cifras, onCifra, className }) => {
  const partes = texto.split(/(\{c\d{1,2}\})/g);
  return (
    <span className={className}>
      {partes.map((p, i) => {
        const m = /^\{c(\d{1,2})\}$/.exec(p);
        const c = m ? cifras[Number(m[1]) - 1] : undefined;
        if (!c) {
          // Si la cifra anterior ya termina en su unidad ("4 SKU") y el texto la repite, se quita la repetición.
          const previa = i > 0 ? /^\{c(\d{1,2})\}$/.exec(partes[i - 1]) : null;
          const cifraPrevia = previa ? cifras[Number(previa[1]) - 1] : undefined;
          const unidad = UNIDAD_INICIAL.exec(p)?.[1];
          const limpio = cifraPrevia && unidad && formatCifra(cifraPrevia).toLowerCase().endsWith(unidad.toLowerCase()) ? p.replace(UNIDAD_INICIAL, '') : p;
          return <React.Fragment key={i}>{limpio.replace(/^ %/, ' %').replace(/^%/, '')}</React.Fragment>;
        }
        const chip = (
          <span className="font-semibold text-slate-900 bg-lime-soft/80 border-b border-emerald-500/60 px-1 rounded-sm">
            {formatCifra(c)}
          </span>
        );
        return onCifra ? (
          <button
            key={i}
            type="button"
            title={`${c.etiqueta} · consulta ${c.consulta_id} (clic para ver el SQL)`}
            onClick={() => onCifra(c.consulta_id)}
            className="cursor-pointer"
          >
            {chip}
          </button>
        ) : (
          <span key={i} title={`${c.etiqueta} · consulta ${c.consulta_id}`}>
            {chip}
          </span>
        );
      })}
    </span>
  );
};
