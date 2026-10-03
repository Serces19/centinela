// frontend/src/components/Sidebar.tsx
import React from 'react';
import {
  Inbox,
  ShieldAlert,
  History,
  BarChart3,
  Sliders,
  Shield,
  Layers,
  Sparkles,
} from 'lucide-react';
import { PersonaSwitcher } from './PersonaSwitcher';
import { Persona } from '../types';

export type TabId = 'bandeja' | 'bitacora' | 'metricas' | 'configuracion';

interface Props {
  tabActiva: TabId;
  onSelectTab: (tab: TabId) => void;
  personaActiva: Persona;
  onSelectPersona: (persona: Persona) => void;
  pendientesCount: number;
}

export const Sidebar: React.FC<Props> = ({
  tabActiva,
  onSelectTab,
  personaActiva,
  onSelectPersona,
  pendientesCount,
}) => {
  const navItems = [
    {
      id: 'bandeja' as TabId,
      label: 'Bandeja de Decisiones',
      icon: Inbox,
      badge: pendientesCount > 0 ? pendientesCount : undefined,
      badgeColor: 'bg-amber-100 text-amber-800 border-amber-200',
    },
    {
      id: 'bitacora' as TabId,
      label: 'Bitácora Inmutable',
      icon: History,
      badge: 'SHA-256',
      badgeColor: 'bg-slate-100 text-slate-600 border-slate-200',
    },
    {
      id: 'metricas' as TabId,
      label: 'Costo & Transparencia',
      icon: BarChart3,
    },
    {
      id: 'configuracion' as TabId,
      label: 'Configuración & KPIs',
      icon: Sliders,
    },
  ];

  return (
    <aside className="w-68 bg-white border-r border-slate-200/70 flex flex-col justify-between h-screen sticky top-0 shrink-0 select-none z-40">
      {/* Brand Header */}
      <div>
        <div className="h-18 px-5 flex items-center gap-3 border-b border-slate-100">
          <div className="w-10 h-10 rounded-2xl bg-slate-900 text-white flex items-center justify-center shadow-subtle shrink-0">
            <Shield className="w-5 h-5 text-emerald-400" />
          </div>
          <div>
            <div className="flex items-center gap-1.5">
              <span className="font-bold text-base tracking-tight text-slate-900">
                Centinela
              </span>
              <span className="text-[10px] font-semibold uppercase px-1.5 py-0.5 rounded-md bg-slate-100 text-slate-600 border border-slate-200/60">
                MVP
              </span>
            </div>
            <div className="text-[11px] text-slate-400 font-medium">
              Vigilancia con IA Operacional
            </div>
          </div>
        </div>

        {/* Navigation */}
        <div className="p-3 space-y-1">
          <div className="px-3 py-2 text-[10px] font-semibold text-slate-400 uppercase tracking-wider">
            Operaciones
          </div>
          {navItems.map((item) => {
            const Icon = item.icon;
            const isActive = tabActiva === item.id;
            return (
              <button
                key={item.id}
                onClick={() => onSelectTab(item.id)}
                className={`w-full flex items-center justify-between px-3 py-2.5 rounded-2xl text-xs font-medium transition-all cursor-pointer ${
                  isActive
                    ? 'bg-slate-900 text-white shadow-xs'
                    : 'text-slate-600 hover:text-slate-900 hover:bg-slate-50'
                }`}
              >
                <div className="flex items-center gap-2.5">
                  <Icon
                    className={`w-4 h-4 ${
                      isActive ? 'text-white' : 'text-slate-400'
                    }`}
                  />
                  <span>{item.label}</span>
                </div>
                {item.badge !== undefined && (
                  <span
                    className={`text-[10px] font-semibold px-2 py-0.5 rounded-full border ${
                      isActive
                        ? 'bg-white/20 text-white border-white/30'
                        : item.badgeColor
                    }`}
                  >
                    {item.badge}
                  </span>
                )}
              </button>
            );
          })}
        </div>

        {/* Info Box sobre el flujo de agentes */}
        <div className="mx-3 mt-4 p-3 rounded-2xl bg-slate-50 border border-slate-200/60">
          <div className="flex items-center gap-1.5 text-xs font-semibold text-slate-800 mb-1">
            <Layers className="w-3.5 h-3.5 text-slate-500" />
            <span>Flujo de 4 Agentes</span>
          </div>
          <p className="text-[11px] text-slate-500 leading-relaxed">
            Tres analizan sin descanso (<strong className="text-slate-700">Vigía</strong>, <strong className="text-slate-700">Analista</strong>, <strong className="text-slate-700">Estratega</strong>) y solo uno actúa (<strong className="text-slate-700">Ejecutor</strong>) tras su aprobación humana.
          </p>
        </div>
      </div>

      {/* Footer con Active Persona Switcher */}
      <div className="p-3 border-t border-slate-100 bg-slate-50/50">
        <div className="text-[10px] font-semibold text-slate-400 uppercase tracking-wider px-2 mb-2 flex items-center justify-between">
          <span>Decisor Activo</span>
          <span className="text-[9px] font-normal text-slate-400">1-clic switch</span>
        </div>
        <PersonaSwitcher
          personaActiva={personaActiva}
          onSelectPersona={onSelectPersona}
        />
      </div>
    </aside>
  );
};
