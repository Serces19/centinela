// frontend/src/utils/personas.ts
import { Persona } from '../types';

export const PERSONAS_DISPONIBLES: Persona[] = [
  {
    id: 'usuario:carlos_mendoza',
    nombre: 'Carlos Mendoza',
    cargo: 'Gerente Comercial',
    area: 'Ventas y Clientes',
    avatar: '👔',
    badgeColor: 'bg-blue-50 text-blue-700 border-blue-200',
  },
  {
    id: 'usuario:ana_restrepo',
    nombre: 'Ana Restrepo',
    cargo: 'Directora de Cartera',
    area: 'Finanzas y Crédito',
    avatar: '💼',
    badgeColor: 'bg-emerald-50 text-emerald-700 border-emerald-200',
  },
  {
    id: 'usuario:david_osorio',
    nombre: 'David Osorio',
    cargo: 'Líder de Abastecimiento',
    area: 'Operaciones y Logística',
    avatar: '📦',
    badgeColor: 'bg-amber-50 text-amber-700 border-amber-200',
  },
  {
    id: 'usuario:sergio_cespedes',
    nombre: 'Sergio Céspedes',
    cargo: 'Auditor & Gerencia General',
    area: 'Auditoría y Control',
    avatar: '🔍',
    badgeColor: 'bg-purple-50 text-purple-700 border-purple-200',
  },
];
