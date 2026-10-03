// frontend/src/components/PersonaSwitcher.tsx
import React, { useState, useRef, useEffect } from 'react';
import { Persona } from '../types';
import { PERSONAS_DISPONIBLES } from '../utils/personas';
import { ChevronUp, Check, ShieldCheck } from 'lucide-react';

interface Props {
  personaActiva: Persona;
  onSelectPersona: (persona: Persona) => void;
}

export const PersonaSwitcher: React.FC<Props> = ({
  personaActiva,
  onSelectPersona,
}) => {
  const [isOpen, setIsOpen] = useState(false);
  const containerRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    function handleClickOutside(event: MouseEvent) {
      if (
        containerRef.current &&
        !containerRef.current.contains(event.target as Node)
      ) {
        setIsOpen(false);
      }
    }
    document.addEventListener('mousedown', handleClickOutside);
    return () => document.removeEventListener('mousedown', handleClickOutside);
  }, []);

  return (
    <div className="relative w-full" ref={containerRef}>
      {isOpen && (
        <div className="absolute bottom-full left-0 right-0 mb-2 bg-white rounded-2xl shadow-modal border border-slate-200/80 p-2 z-50 animate-in fade-in slide-in-from-bottom-2 duration-150">
          <div className="px-3 py-2 border-b border-slate-100 flex items-center justify-between">
            <span className="text-[11px] font-semibold text-slate-400 uppercase tracking-wider">
              Alternar Rol de Usuario
            </span>
            <span className="flex items-center gap-1 text-[10px] text-emerald-600 font-medium bg-emerald-50 px-2 py-0.5 rounded-full border border-emerald-100">
              <ShieldCheck className="w-3 h-3" />
              Sesión Segura
            </span>
          </div>
          <div className="mt-1 space-y-1">
            {PERSONAS_DISPONIBLES.map((persona) => {
              const isSelected = persona.id === personaActiva.id;
              return (
                <button
                  key={persona.id}
                  onClick={() => {
                    onSelectPersona(persona);
                    setIsOpen(false);
                  }}
                  className={`w-full text-left p-2.5 rounded-xl transition-all flex items-center justify-between ${
                    isSelected
                      ? 'bg-slate-100/90 text-slate-900 font-medium'
                      : 'hover:bg-slate-50 text-slate-600 hover:text-slate-900'
                  }`}
                >
                  <div className="flex items-center gap-2.5">
                    <span className="text-xl select-none">{persona.avatar}</span>
                    <div>
                      <div className="text-xs font-semibold leading-tight text-slate-800">
                        {persona.nombre}
                      </div>
                      <div className="text-[11px] text-slate-400 leading-tight">
                        {persona.cargo} · {persona.area}
                      </div>
                    </div>
                  </div>
                  {isSelected && (
                    <Check className="w-4 h-4 text-emerald-600 shrink-0" />
                  )}
                </button>
              );
            })}
          </div>
        </div>
      )}

      {/* Pill activador de usuario */}
      <button
        onClick={() => setIsOpen(!isOpen)}
        className="w-full flex items-center justify-between p-2 rounded-2xl bg-white border border-slate-200/70 hover:border-slate-300 hover:shadow-subtle transition-all text-left group"
        title="Clic para cambiar de rol activo"
      >
        <div className="flex items-center gap-2.5 overflow-hidden">
          <div className="w-9 h-9 rounded-xl bg-slate-100 flex items-center justify-center text-lg shrink-0 border border-slate-200/60 shadow-xs">
            {personaActiva.avatar}
          </div>
          <div className="truncate">
            <div className="text-xs font-semibold text-slate-900 truncate flex items-center gap-1.5">
              {personaActiva.nombre}
            </div>
            <div className="text-[11px] text-slate-400 truncate">
              {personaActiva.cargo}
            </div>
          </div>
        </div>
        <div className="p-1 rounded-lg text-slate-400 group-hover:text-slate-600 shrink-0">
          <ChevronUp
            className={`w-4 h-4 transition-transform duration-200 ${
              isOpen ? 'rotate-180 text-slate-700' : ''
            }`}
          />
        </div>
      </button>
    </div>
  );
};
