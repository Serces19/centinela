// frontend/src/components/Sidebar.tsx
import React from 'react';
import { Inbox, History, BarChart3, Sliders, Shield, Layers, X } from 'lucide-react';
import { PersonaSwitcher } from './PersonaSwitcher';
import { Persona } from '../types';

export type TabId = 'bandeja' | 'bitacora' | 'metricas' | 'configuracion';

interface Props {
  tabActiva: TabId;
  onSelectTab: (tab: TabId) => void;
  personaActiva: Persona;
  onSelectPersona: (persona: Persona) => void;
  pendientesCount: number;
  /** Solo móvil: el panel se comporta como cajón deslizante */
  abierto: boolean;
  onCerrar: () => void;
}

export const Sidebar: React.FC<Props> = ({
  tabActiva,
  onSelectTab,
  personaActiva,
  onSelectPersona,
  pendientesCount,
  abierto,
  onCerrar,
}) => {
  const navItems = [
    {
      id: 'bandeja' as TabId,
      label: 'Bandeja de Decisiones',
      icon: Inbox,
      badge: pendientesCount > 0 ? String(pendientesCount) : undefined,
      badgeClass: 'bg-lime text-lime-ink',
    },
    {
      id: 'bitacora' as TabId,
      label: 'Bitácora Inmutable',
      icon: History,
      badge: 'SHA-256',
      badgeClass: 'bg-slate-100 text-slate-500',
    },
    { id: 'metricas' as TabId, label: 'Costo & Transparencia', icon: BarChart3 },
    { id: 'configuracion' as TabId, label: 'Configuración & KPIs', icon: Sliders },
  ];

  return (
    <>
      {/* Telón del cajón en móvil */}
      <div
        onClick={onCerrar}
        className={`fixed inset-0 z-40 bg-slate-900/30 backdrop-blur-sm transition-opacity lg:hidden ${
          abierto ? 'opacity-100' : 'opacity-0 pointer-events-none'
        }`}
      />

      <aside
        className={`fixed lg:sticky top-0 left-0 z-50 lg:z-30 h-screen lg:h-[calc(100vh-2rem)] lg:m-4 w-72 lg:w-64 xl:w-72 shrink-0 select-none
          glass-strong lg:glass rounded-r-4xl lg:rounded-4xl flex flex-col justify-between p-4 transition-transform duration-300
          ${abierto ? 'translate-x-0' : '-translate-x-full lg:translate-x-0'}`}
      >
        <div className="overflow-y-auto min-h-0">
          {/* Marca */}
          <div className="flex items-center justify-between px-1 pt-1 pb-5">
            <div className="flex items-center gap-3">
              <div className="w-11 h-11 rounded-2xl bg-slate-900 flex items-center justify-center shadow-float shrink-0">
                <Shield className="w-5 h-5 text-lime" />
              </div>
              <div className="leading-tight">
                <div className="flex items-center gap-1.5">
                  <span className="font-bold text-lg tracking-tight text-slate-900">Centinela</span>
                  <span className="text-[9px] font-bold uppercase px-1.5 py-0.5 rounded-full bg-lime text-lime-ink">
                    MVP
                  </span>
                </div>
                <div className="text-[11px] text-slate-400 font-medium">Vigilancia con IA</div>
              </div>
            </div>
            <button onClick={onCerrar} className="icon-btn lg:hidden" aria-label="Cerrar menú">
              <X className="w-4 h-4" />
            </button>
          </div>

          <div className="section-eyebrow px-2 pb-2">Menú</div>
          <nav className="space-y-1.5">
            {navItems.map((item) => {
              const Icon = item.icon;
              const activo = tabActiva === item.id;
              return (
                <button
                  key={item.id}
                  onClick={() => {
                    onSelectTab(item.id);
                    onCerrar();
                  }}
                  aria-current={activo ? 'page' : undefined}
                  className={`w-full flex items-center justify-between gap-2 pl-1.5 pr-3 py-1.5 rounded-full text-[13px] font-medium transition-all cursor-pointer ${
                    activo
                      ? 'bg-slate-900 text-white shadow-float'
                      : 'text-slate-600 hover:text-slate-900 hover:bg-white/70'
                  }`}
                >
                  <span className="flex items-center gap-3 min-w-0">
                    <span
                      className={`w-9 h-9 rounded-full flex items-center justify-center shrink-0 ${
                        activo ? 'bg-white/10' : 'bg-white/80 border border-white'
                      }`}
                    >
                      <Icon className={`w-4 h-4 ${activo ? 'text-lime' : 'text-slate-500'}`} />
                    </span>
                    <span className="truncate">{item.label}</span>
                  </span>
                  {item.badge !== undefined && (
                    <span
                      className={`text-[10px] font-bold px-2 py-0.5 rounded-full shrink-0 ${
                        activo ? 'bg-lime text-lime-ink' : item.badgeClass
                      }`}
                    >
                      {item.badge}
                    </span>
                  )}
                </button>
              );
            })}
          </nav>

          {/* Flujo de agentes */}
          <div className="mt-5 p-4 rounded-3xl bg-lime/70 border border-white/80">
            <div className="flex items-center gap-1.5 text-xs font-bold text-lime-ink mb-1.5">
              <Layers className="w-3.5 h-3.5" />
              <span>Flujo de 4 Agentes</span>
            </div>
            <p className="text-[11px] text-slate-700 leading-relaxed">
              <strong>Vigía</strong>, <strong>Analista</strong> y <strong>Estratega</strong> analizan sin descanso;
              solo el <strong>Ejecutor</strong> actúa, tras tu aprobación.
            </p>
          </div>
        </div>

        {/* Tarjeta flotante del decisor activo */}
        <div className="pt-4">
          <PersonaSwitcher personaActiva={personaActiva} onSelectPersona={onSelectPersona} />
        </div>
      </aside>
    </>
  );
};
