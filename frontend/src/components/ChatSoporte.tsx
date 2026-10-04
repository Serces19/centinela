// frontend/src/components/ChatSoporte.tsx
import React, { useEffect, useRef, useState } from 'react';
import { Bar, BarChart, CartesianGrid, Line, LineChart, ResponsiveContainer, Tooltip, XAxis, YAxis } from 'recharts';
import { Loader2, Send, Sparkles, X } from 'lucide-react';
import { ChatEvento, ChatGrafico, ChatMessage } from '../types';
import { streamChat } from '../api/client';
import { formatCifra } from '../utils/texto';

interface Props {
  alertaId?: string;
  sugerencias: string[];
  onClose: () => void;
  onVerConsulta: (consultaId: string) => void;
  initialPrompt?: string;
}

const hora = () => new Date().toLocaleTimeString('es-CO', { hour: '2-digit', minute: '2-digit' });

const Grafico: React.FC<{ g: ChatGrafico }> = ({ g }) => {
  const datos = g.puntos.map((p) => ({ etiqueta: p.etiqueta, valor: p.valor }));
  const compacto = (v: number) => (g.unidad === 'COP' && Math.abs(v) >= 1e6 ? `${(v / 1e6).toFixed(0)} M` : String(Math.round(v * 10) / 10));
  return (
    <figure className="mt-3 p-3 rounded-2xl bg-white border border-slate-200/80">
      <figcaption className="text-[11px] font-semibold text-slate-700 mb-2">{g.titulo}</figcaption>
      <div className="h-44" role="img" aria-label={g.titulo}>
        <ResponsiveContainer width="100%" height="100%">
          {g.tipo === 'linea' ? (
            <LineChart data={datos} margin={{ top: 4, right: 8, bottom: 0, left: -8 }}>
              <CartesianGrid strokeDasharray="3 3" stroke="#e5ebe9" />
              <XAxis dataKey="etiqueta" tick={{ fontSize: 9 }} interval="preserveStartEnd" />
              <YAxis tick={{ fontSize: 9 }} tickFormatter={compacto} />
              <Tooltip formatter={(v: number) => formatCifra({ etiqueta: '', valor: v, unidad: g.unidad, consulta_id: g.consulta_id })} />
              <Line type="monotone" dataKey="valor" stroke="#228168" strokeWidth={2} dot={false} />
            </LineChart>
          ) : (
            <BarChart data={datos} margin={{ top: 4, right: 8, bottom: 0, left: -8 }}>
              <CartesianGrid strokeDasharray="3 3" stroke="#e5ebe9" />
              <XAxis dataKey="etiqueta" tick={{ fontSize: 9 }} interval={0} angle={-20} textAnchor="end" height={48} />
              <YAxis tick={{ fontSize: 9 }} tickFormatter={compacto} />
              <Tooltip formatter={(v: number) => formatCifra({ etiqueta: '', valor: v, unidad: g.unidad, consulta_id: g.consulta_id })} />
              <Bar dataKey="valor" fill="#2fa081" radius={[4, 4, 0, 0]} />
            </BarChart>
          )}
        </ResponsiveContainer>
      </div>
    </figure>
  );
};

export const ChatSoporte: React.FC<Props> = ({ alertaId, sugerencias, onClose, onVerConsulta, initialPrompt }) => {
  const [messages, setMessages] = useState<ChatMessage[]>([
    {
      id: 'bienvenida',
      sender: 'assistant',
      content: alertaId
        ? 'Estoy anclado a la alerta que tienes abierta. Pregúntame por sus clientes, productos, proveedores o por las políticas que aplican.'
        : 'Pregúntame por ventas, clientes, productos, inventario, cartera o políticas de Distribuidora Andina. Cada cifra que te dé sale de una consulta que puedes revisar.',
      timestamp: hora(),
    },
  ]);
  const [input, setInput] = useState('');
  const [enCurso, setEnCurso] = useState(false);
  const finRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    finRef.current?.scrollIntoView({ behavior: 'smooth' });
  }, [messages]);
  useEffect(() => {
    if (initialPrompt) enviar(initialPrompt);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [initialPrompt]);

  const actualizar = (id: string, f: (m: ChatMessage) => ChatMessage) =>
    setMessages((prev) => prev.map((m) => (m.id === id ? f(m) : m)));

  const enviar = async (texto?: string) => {
    const pregunta = (texto ?? input).trim();
    if (!pregunta || enCurso) return;
    setInput('');
    const id = `a-${Date.now()}`;
    setMessages((prev) => [
      ...prev,
      { id: `u-${Date.now()}`, sender: 'user', content: pregunta, timestamp: hora() },
      { id, sender: 'assistant', content: '', isStreaming: true, cifras: [], timestamp: hora() },
    ]);
    setEnCurso(true);
    const alAlcanzar = (ev: ChatEvento) => {
      switch (ev.evento) {
        case 'paso':
          return actualizar(id, (m) => ({ ...m, paso: ev.texto }));
        case 'token':
          return actualizar(id, (m) => ({ ...m, content: m.content + ev.texto }));
        case 'cifra':
          return actualizar(id, (m) => ({ ...m, cifras: [...(m.cifras ?? []), ev.cifra] }));
        case 'grafico': {
          const { evento: _e, ...g } = ev;
          return actualizar(id, (m) => ({ ...m, grafico: g }));
        }
        case 'error':
          return actualizar(id, (m) => ({ ...m, error: ev.mensaje }));
        case 'fin':
          return actualizar(id, (m) => ({ ...m, isStreaming: false, paso: undefined, consultas: ev.consulta_ids, costo_usd: ev.costo_usd }));
      }
    };
    try {
      await streamChat({ alerta_id: alertaId, mensaje: pregunta }, alAlcanzar);
    } catch (e) {
      actualizar(id, (m) => ({ ...m, isStreaming: false, error: (e as Error).message }));
    } finally {
      actualizar(id, (m) => ({ ...m, isStreaming: false, paso: undefined }));
      setEnCurso(false);
    }
  };

  return (
    <aside
      aria-label="Asistente de Centinela"
      className="w-[calc(100vw-1.5rem)] sm:w-[420px] glass-strong rounded-4xl shadow-modal flex flex-col fixed right-3 top-3 bottom-3 z-50 overflow-hidden animate-fade-up"
    >
      <div className="px-5 py-4 border-b border-slate-100 flex items-center justify-between bg-slate-50/50">
        <div className="flex items-center gap-2.5">
          <div className="w-8 h-8 rounded-xl bg-slate-900 text-white flex items-center justify-center">
            <Sparkles className="w-4 h-4 text-amber-300" />
          </div>
          <div>
            <div className="text-xs font-bold text-slate-900">Asistente Centinela</div>
            <div className="text-[11px] text-slate-400">{alertaId ? 'Anclado a la alerta abierta' : 'Consulta libre sobre los datos'}</div>
          </div>
        </div>
        <button onClick={onClose} aria-label="Cerrar el asistente" className="p-1.5 rounded-xl text-slate-400 hover:text-slate-700 hover:bg-slate-200/60 cursor-pointer">
          <X className="w-4 h-4" />
        </button>
      </div>

      <div className="flex-1 p-4 overflow-y-auto space-y-4" aria-live="polite">
        {messages.map((m) => {
          const esUsuario = m.sender === 'user';
          return (
            <div key={m.id} className={`flex flex-col ${esUsuario ? 'items-end' : 'items-start'} space-y-1.5`}>
              <div className={`max-w-[92%] p-3.5 rounded-2xl text-xs leading-relaxed ${esUsuario ? 'bg-slate-900 text-white' : 'bg-slate-100/80 text-slate-800 border border-slate-200/60'}`}>
                {m.isStreaming && !m.content && (
                  <div className="flex items-center gap-2 text-slate-500">
                    <Loader2 className="w-3.5 h-3.5 animate-spin" />
                    <span>{m.paso ?? 'Pensando…'}</span>
                  </div>
                )}
                {m.content && <div className="whitespace-pre-wrap">{m.content}</div>}
                {m.error && <div className="mt-1 text-rose-700">{m.error}</div>}
                {m.grafico && <Grafico g={m.grafico} />}
                {m.cifras && m.cifras.length > 0 && (
                  <div className="mt-2.5 pt-2 border-t border-slate-200 flex flex-wrap gap-1.5">
                    {m.cifras.map((c, i) => (
                      <button
                        key={i}
                        onClick={() => onVerConsulta(c.consulta_id)}
                        title={`Ver la consulta ${c.consulta_id}`}
                        className="px-2 py-0.5 rounded-md bg-white border border-slate-200 text-[10px] text-slate-700 hover:border-emerald-400 cursor-pointer"
                      >
                        {c.etiqueta}: <strong className="text-slate-900">{formatCifra(c)}</strong>
                      </button>
                    ))}
                  </div>
                )}
                {m.costo_usd !== undefined && !esUsuario && (
                  <div className="mt-2 pt-1.5 border-t border-slate-200/60 flex items-center justify-between text-[10px] text-slate-400">
                    <span>Costo de esta respuesta: US$ {m.costo_usd.toFixed(4)}</span>
                    <span>{m.consultas?.length ?? 0} consulta(s) verificables</span>
                  </div>
                )}
              </div>
              <span className="text-[10px] text-slate-400 px-1">{m.timestamp}</span>
            </div>
          );
        })}
        <div ref={finRef} />
      </div>

      {sugerencias.length > 0 && (
        <div className="px-4 py-2 border-t border-slate-100 bg-slate-50/50">
          <span className="text-[10px] font-semibold uppercase tracking-wider text-slate-400 block mb-1.5">Prueba preguntar</span>
          <div className="flex flex-col gap-1">
            {sugerencias.slice(0, 3).map((s) => (
              <button
                key={s}
                onClick={() => enviar(s)}
                disabled={enCurso}
                className="text-[11px] text-left p-1.5 rounded-lg bg-white border border-slate-200/80 hover:border-slate-300 text-slate-600 hover:text-slate-900 truncate cursor-pointer disabled:opacity-50"
              >
                {s}
              </button>
            ))}
          </div>
        </div>
      )}

      <form
        onSubmit={(e) => {
          e.preventDefault();
          enviar();
        }}
        className="p-3 border-t border-slate-200/70 bg-white flex items-center gap-2"
      >
        <input
          type="text"
          value={input}
          onChange={(e) => setInput(e.target.value)}
          placeholder="Pregunta sobre datos o políticas…"
          aria-label="Pregunta para el asistente"
          disabled={enCurso}
          className="flex-1 text-xs p-2.5 rounded-xl bg-slate-100/70 border border-slate-200/70 placeholder:text-slate-400"
        />
        <button type="submit" disabled={!input.trim() || enCurso} aria-label="Enviar pregunta" className="p-2.5 rounded-xl bg-slate-900 text-white hover:bg-slate-800 disabled:opacity-40 cursor-pointer shrink-0">
          {enCurso ? <Loader2 className="w-4 h-4 animate-spin" /> : <Send className="w-4 h-4" />}
        </button>
      </form>
    </aside>
  );
};
