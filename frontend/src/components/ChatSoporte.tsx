// frontend/src/components/ChatSoporte.tsx
import React, { useState, useRef, useEffect } from 'react';
import {
  X,
  Send,
  Sparkles,
  Bot,
  User,
  Database,
  FileText,
  DollarSign,
  Loader2,
  RefreshCw,
  MessageSquare,
} from 'lucide-react';
import { ChatMessage, CifraTrazable } from '../types';
import { streamChat } from '../api/client';
import { formatCOP } from '../utils/formatters';

interface Props {
  alertaId?: string;
  onClose: () => void;
  initialPrompt?: string;
}

export const ChatSoporte: React.FC<Props> = ({
  alertaId,
  onClose,
  initialPrompt,
}) => {
  const [messages, setMessages] = useState<ChatMessage[]>([
    {
      id: 'welcome',
      sender: 'assistant',
      content: alertaId
        ? `Hola. Soy el Asistente Centinela. Estoy anclado a la alerta **${alertaId}** para responder preguntas con datos reales y políticas oficiales.`
        : `Hola. Soy el Asistente Centinela. Puede consultarme sobre cualquier cliente, proveedor, ventas, inventario o políticas operacionales de Distribuidora Andina.`,
      timestamp: new Date().toLocaleTimeString('es-CO', {
        hour: '2-digit',
        minute: '2-digit',
      }),
    },
  ]);

  const [input, setInput] = useState('');
  const [isStreaming, setIsStreaming] = useState(false);
  const messagesEndRef = useRef<HTMLDivElement>(null);

  const scrollToBottom = () => {
    messagesEndRef.current?.scrollIntoView({ behavior: 'smooth' });
  };

  useEffect(() => {
    scrollToBottom();
  }, [messages]);

  useEffect(() => {
    if (initialPrompt) {
      handleSendMessage(initialPrompt);
    }
  }, [initialPrompt]);

  const handleSendMessage = async (textToSend?: string) => {
    const query = (textToSend || input).trim();
    if (!query || isStreaming) return;

    setInput('');

    const userMsgId = `user-${Date.now()}`;
    const assistantMsgId = `assistant-${Date.now()}`;

    // 1. Agregar mensaje del usuario
    setMessages((prev) => [
      ...prev,
      {
        id: userMsgId,
        sender: 'user',
        content: query,
        timestamp: new Date().toLocaleTimeString('es-CO', {
          hour: '2-digit',
          minute: '2-digit',
        }),
      },
      {
        id: assistantMsgId,
        sender: 'assistant',
        content: '',
        isStreaming: true,
        cifras: [],
        consultas: [],
        timestamp: new Date().toLocaleTimeString('es-CO', {
          hour: '2-digit',
          minute: '2-digit',
        }),
      },
    ]);

    setIsStreaming(true);

    try {
      await streamChat(
        {
          alerta_id: alertaId,
          mensaje: query,
        },
        {
          onToken: (token) => {
            setMessages((prev) =>
              prev.map((m) =>
                m.id === assistantMsgId
                  ? { ...m, content: m.content + token }
                  : m
              )
            );
          },
          onCifra: (cifra: CifraTrazable) => {
            setMessages((prev) =>
              prev.map((m) =>
                m.id === assistantMsgId
                  ? { ...m, cifras: [...(m.cifras || []), cifra] }
                  : m
              )
            );
          },
          onFin: (fin) => {
            setMessages((prev) =>
              prev.map((m) =>
                m.id === assistantMsgId
                  ? {
                      ...m,
                      isStreaming: false,
                      consultas: fin.consulta_ids,
                      costo_usd: fin.costo_usd,
                    }
                  : m
              )
            );
            setIsStreaming(false);
          },
          onError: (errMsg) => {
            setMessages((prev) =>
              prev.map((m) =>
                m.id === assistantMsgId
                  ? {
                      ...m,
                      content:
                        m.content +
                        `\n\n*(Error al procesar consulta: ${errMsg})*`,
                      isStreaming: false,
                    }
                  : m
              )
            );
            setIsStreaming(false);
          },
        }
      );
    } catch (err: any) {
      setMessages((prev) =>
        prev.map((m) =>
          m.id === assistantMsgId
            ? {
                ...m,
                content: `No fue posible conectar con el servicio de chat: ${err.message}`,
                isStreaming: false,
              }
            : m
        )
      );
      setIsStreaming(false);
    }
  };

  const sugerencias = [
    '¿Qué otros SKU compra este proveedor?',
    '¿Cuál es el saldo vencido y días promedio de pago?',
    '¿Qué dice FIN-POL-004 sobre la mora mayor a 15 días?',
    '¿Qué margen promedio tiene esta línea de productos?',
  ];

  return (
    <aside className="w-96 bg-white border-l border-slate-200/70 shadow-2xl flex flex-col h-screen fixed right-0 top-0 z-40 animate-in slide-in-from-right duration-200">
      {/* Header */}
      <div className="h-18 px-5 border-b border-slate-100 flex items-center justify-between bg-slate-50/50">
        <div className="flex items-center gap-2.5">
          <div className="w-8 h-8 rounded-xl bg-slate-900 text-white flex items-center justify-center">
            <Sparkles className="w-4 h-4 text-amber-300" />
          </div>
          <div>
            <div className="text-xs font-bold text-slate-900 flex items-center gap-1.5">
              <span>Asistente Centinela</span>
              <span className="text-[9px] font-semibold px-1.5 py-0.2 rounded bg-emerald-50 text-emerald-700 border border-emerald-200">
                SSE Live
              </span>
            </div>
            <div className="text-[11px] text-slate-400">
              {alertaId ? `Anclado a ${alertaId}` : 'Modo Consulta General'}
            </div>
          </div>
        </div>

        <button
          onClick={onClose}
          className="p-1.5 rounded-xl text-slate-400 hover:text-slate-700 hover:bg-slate-200/60 transition-colors cursor-pointer"
        >
          <X className="w-4 h-4" />
        </button>
      </div>

      {/* Messages Feed */}
      <div className="flex-1 p-4 overflow-y-auto space-y-4">
        {messages.map((m) => {
          const isUser = m.sender === 'user';
          return (
            <div
              key={m.id}
              className={`flex flex-col ${
                isUser ? 'items-end' : 'items-start'
              } space-y-1.5`}
            >
              <div
                className={`max-w-[88%] p-3.5 rounded-2xl text-xs leading-relaxed ${
                  isUser
                    ? 'bg-slate-900 text-white rounded-tr-xs'
                    : 'bg-slate-100/80 text-slate-800 rounded-tl-xs border border-slate-200/60'
                }`}
              >
                <div className="whitespace-pre-wrap">{m.content}</div>

                {/* Loading indicator for token stream */}
                {m.isStreaming && (
                  <span className="inline-block w-1.5 h-3.5 bg-slate-400 animate-pulse ml-1 align-middle" />
                )}

                {/* Cifras trazables renderizadas */}
                {m.cifras && m.cifras.length > 0 && (
                  <div className="mt-2.5 pt-2 border-t border-slate-200 space-y-1.5">
                    <span className="text-[10px] font-bold uppercase tracking-wider text-slate-500 block">
                      Cifras Citadas de la Base de Datos:
                    </span>
                    <div className="flex flex-wrap gap-1.5">
                      {m.cifras.map((c, i) => (
                        <span
                          key={i}
                          className="px-2 py-0.5 rounded-md bg-white border border-slate-200 text-[10px] font-medium text-slate-700 shadow-2xs flex items-center gap-1"
                        >
                          <span>{c.etiqueta}:</span>
                          <strong className="text-slate-900">
                            {c.unidad === 'COP'
                              ? formatCOP(c.valor)
                              : `${c.valor} ${c.unidad}`}
                          </strong>
                          <span className="text-slate-400 font-mono text-[9px]">
                            [{c.consulta_id}]
                          </span>
                        </span>
                      ))}
                    </div>
                  </div>
                )}

                {/* Metadatos de fin de respuesta */}
                {m.costo_usd !== undefined && (
                  <div className="mt-2 pt-1.5 border-t border-slate-200/60 flex items-center justify-between text-[10px] text-slate-400 font-mono">
                    <span>Haiku 4.5: ${(m.costo_usd * 1000).toFixed(3)} mUSD</span>
                    <span>{m.consultas?.length || 0} consultas SQL</span>
                  </div>
                )}
              </div>

              <span className="text-[10px] text-slate-400 px-1">
                {m.timestamp}
              </span>
            </div>
          );
        })}
        <div ref={messagesEndRef} />
      </div>

      {/* Sugerencias rápidas */}
      <div className="px-4 py-2 border-t border-slate-100 bg-slate-50/50">
        <span className="text-[10px] font-semibold uppercase tracking-wider text-slate-400 block mb-1.5">
          Consultas Frecuentes
        </span>
        <div className="flex flex-wrap gap-1">
          {sugerencias.slice(0, 2).map((sug, idx) => (
            <button
              key={idx}
              onClick={() => handleSendMessage(sug)}
              disabled={isStreaming}
              className="text-[11px] text-left p-1.5 rounded-lg bg-white border border-slate-200/80 hover:border-slate-300 text-slate-600 hover:text-slate-900 transition-all truncate max-w-full cursor-pointer disabled:opacity-50"
            >
              {sug}
            </button>
          ))}
        </div>
      </div>

      {/* Input Form */}
      <div className="p-3 border-t border-slate-200/70 bg-white">
        <form
          onSubmit={(e) => {
            e.preventDefault();
            handleSendMessage();
          }}
          className="flex items-center gap-2"
        >
          <input
            type="text"
            value={input}
            onChange={(e) => setInput(e.target.value)}
            placeholder="Pregunte sobre datos o políticas..."
            disabled={isStreaming}
            className="flex-1 text-xs p-2.5 rounded-xl bg-slate-100/70 border border-slate-200/70 focus:outline-none focus:ring-2 focus:ring-slate-900/10 focus:border-slate-400 placeholder:text-slate-400"
          />
          <button
            type="submit"
            disabled={!input.trim() || isStreaming}
            className="p-2.5 rounded-xl bg-slate-900 text-white hover:bg-slate-800 disabled:opacity-40 transition-all cursor-pointer shrink-0"
            title="Enviar mensaje"
          >
            {isStreaming ? (
              <Loader2 className="w-4 h-4 animate-spin" />
            ) : (
              <Send className="w-4 h-4" />
            )}
          </button>
        </form>
      </div>
    </aside>
  );
};
