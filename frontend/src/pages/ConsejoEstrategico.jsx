import { useState, useEffect } from 'react';
import api from '../api/axios';

const ASESORES = [
  { emoji: '🔴', key: 'CONTRARIAN',            label: 'El Contrarian',               border: 'border-red-500',    bg: 'bg-red-500/5'    },
  { emoji: '🔵', key: 'PRIMEROS PRINCIPIOS',   label: 'El Pensador de Primeros Principios', border: 'border-blue-600', bg: 'bg-blue-600/5'  },
  { emoji: '🟢', key: 'EXPANSIONISTA',         label: 'El Expansionista',             border: 'border-emerald-500', bg: 'bg-emerald-500/5'},
  { emoji: '🟡', key: 'OUTSIDER',              label: 'El Outsider',                  border: 'border-yellow-400', bg: 'bg-yellow-400/5' },
  { emoji: '🟠', key: 'EJECUTOR',              label: 'El Ejecutor',                  border: 'border-orange-500', bg: 'bg-orange-500/5' },
];

function parseRespuesta(texto) {
  if (!texto) return { secciones: [], presidente: '' };

  const presidenteMatch = texto.match(/PRESIDENTE DEL CONSEJO([\s\S]*?)$/i);
  const presidente = presidenteMatch ? presidenteMatch[0].trim() : '';
  const cuerpo = presidenteMatch ? texto.slice(0, presidenteMatch.index) : texto;

  const secciones = ASESORES.map((asesor) => {
    const regex = new RegExp(
      `${asesor.emoji}[^\\n]*${asesor.key}[^\\n]*(\\n[\\s\\S]*?)(?=(?:🔴|🔵|🟢|🟡|🟠|PRESIDENTE)|$)`,
      'i'
    );
    const match = cuerpo.match(regex);
    return {
      ...asesor,
      contenido: match ? match[0].trim() : '',
    };
  }).filter(s => s.contenido);

  return { secciones, presidente };
}

function SeccionCard({ seccion }) {
  return (
    <div className={`rounded-sm border-l-4 ${seccion.border} ${seccion.bg} p-4`}>
      <pre className="whitespace-pre-wrap font-sans text-sm text-slate-200 leading-relaxed">
        {seccion.contenido}
      </pre>
    </div>
  );
}

function HistorialItem({ item, onSelect }) {
  const fecha = item.created_at
    ? new Date(item.created_at).toLocaleString('es-MX', { dateStyle: 'short', timeStyle: 'short' })
    : '';
  return (
    <button
      onClick={() => onSelect(item)}
      className="w-full text-left p-3 rounded-sm border border-slate-700 hover:border-slate-500 bg-slate-800/50 hover:bg-slate-800 transition-colors"
    >
      <p className="text-xs text-slate-400 mb-1">{fecha}</p>
      <p className="text-sm text-slate-200 truncate">{item.pregunta}</p>
    </button>
  );
}

export default function ConsejoEstrategico() {
  const [pregunta, setPregunta] = useState('');
  const [loading, setLoading] = useState(false);
  const [respuesta, setRespuesta] = useState(null);
  const [error, setError] = useState('');
  const [historial, setHistorial] = useState([]);
  const [historialOpen, setHistorialOpen] = useState(false);
  const [copied, setCopied] = useState(false);

  useEffect(() => {
    api.get('/ia/consejo-estrategico/historial')
      .then(r => setHistorial(r.data.historial || []))
      .catch(() => {});
  }, []);

  async function handleSubmit(e) {
    e.preventDefault();
    if (!pregunta.trim()) return;
    setLoading(true);
    setError('');
    setRespuesta(null);
    try {
      const r = await api.post('/ia/consejo-estrategico', { pregunta });
      if (r.data.success) {
        setRespuesta(r.data.respuesta);
        setHistorial(prev => [{
          pregunta,
          respuesta: r.data.respuesta,
          created_at: new Date().toISOString(),
        }, ...prev.slice(0, 9)]);
      } else {
        setError(r.data.error || 'Error desconocido');
      }
    } catch (err) {
      setError(err.response?.data?.detail || 'Error al conectar con el servidor');
    } finally {
      setLoading(false);
    }
  }

  function handleCopy() {
    if (!respuesta) return;
    navigator.clipboard.writeText(respuesta);
    setCopied(true);
    setTimeout(() => setCopied(false), 2000);
  }

  function handleNueva() {
    setPregunta('');
    setRespuesta(null);
    setError('');
  }

  function handleSelectHistorial(item) {
    setPregunta(item.pregunta);
    setRespuesta(item.respuesta);
    setHistorialOpen(false);
    window.scrollTo({ top: 0, behavior: 'smooth' });
  }

  const parsed = respuesta ? parseRespuesta(respuesta) : null;

  return (
    <div className="min-h-screen bg-slate-900 text-slate-100 p-6">
      <div className="max-w-4xl mx-auto space-y-6">

        {/* Header */}
        <div className="flex items-start justify-between">
          <div>
            <h1 className="text-2xl font-bold text-white tracking-tight">
              🏛️ Consejo Estratégico IA
            </h1>
            <p className="text-slate-400 mt-1 text-sm">
              Analiza cualquier decisión desde 5 perspectivas independientes
            </p>
          </div>
          <span className="text-xs bg-violet-500/15 text-violet-300 border border-violet-500/30 px-3 py-1 rounded-full font-mono">
            Powered by Claude AI
          </span>
        </div>

        {/* Input */}
        <form onSubmit={handleSubmit} className="space-y-3">
          <textarea
            data-testid="consejo-pregunta"
            value={pregunta}
            onChange={e => setPregunta(e.target.value)}
            rows={4}
            placeholder="Escribe tu pregunta o decisión aquí. Ejemplo: '¿Debo contratar un vendedor antes de tener 20 clientes?' o '¿Conviene bajar precios para conseguir los primeros clientes?'"
            className="w-full bg-slate-800 border border-slate-600 rounded-sm px-4 py-3 text-sm text-slate-100 placeholder-slate-500 focus:outline-none focus:border-slate-400 resize-none"
            disabled={loading}
          />
          <div className="flex items-center gap-3">
            <button
              data-testid="consejo-submit"
              type="submit"
              disabled={loading || !pregunta.trim()}
              className="bg-slate-700 hover:bg-slate-600 disabled:opacity-50 disabled:cursor-not-allowed text-white text-sm font-medium px-5 py-2 rounded-sm border border-slate-600 transition-colors flex items-center gap-2"
            >
              {loading ? (
                <>
                  <svg className="animate-spin h-4 w-4" viewBox="0 0 24 24" fill="none">
                    <circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4" />
                    <path className="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8v8H4z" />
                  </svg>
                  Consultando al consejo...
                </>
              ) : (
                'Consultar al Consejo'
              )}
            </button>
            {respuesta && (
              <button
                type="button"
                onClick={handleNueva}
                className="text-sm text-slate-400 hover:text-slate-200 transition-colors"
              >
                Nueva consulta
              </button>
            )}
            {loading && (
              <span className="text-xs text-slate-500">El análisis tarda 30–60 segundos</span>
            )}
          </div>
        </form>

        {/* Error */}
        {error && (
          <div className="bg-red-900/20 border border-red-500/30 rounded-sm px-4 py-3 text-sm text-red-300">
            {error}
          </div>
        )}

        {/* Resultado */}
        {parsed && (
          <div className="space-y-4">
            <div className="flex items-center justify-between">
              <h2 className="text-sm font-semibold text-slate-300 uppercase tracking-wider">
                Análisis del Consejo
              </h2>
              <button
                data-testid="consejo-copy"
                onClick={handleCopy}
                className="text-xs text-slate-400 hover:text-slate-200 border border-slate-700 hover:border-slate-500 px-3 py-1 rounded-sm transition-colors"
              >
                {copied ? '✓ Copiado' : 'Copiar análisis completo'}
              </button>
            </div>

            {/* Cards por asesor */}
            {parsed.secciones.length > 0
              ? parsed.secciones.map(s => <SeccionCard key={s.key} seccion={s} />)
              : (
                <div className="rounded-sm border border-slate-700 p-4">
                  <pre className="whitespace-pre-wrap font-sans text-sm text-slate-200 leading-relaxed">
                    {respuesta}
                  </pre>
                </div>
              )
            }

            {/* Presidente del Consejo */}
            {parsed.presidente && (
              <div className="rounded-sm border border-slate-500 bg-slate-800 p-5">
                <pre className="whitespace-pre-wrap font-sans text-sm text-white leading-relaxed">
                  {parsed.presidente}
                </pre>
              </div>
            )}
          </div>
        )}

        {/* Historial */}
        <div className="border border-slate-700 rounded-sm">
          <button
            data-testid="consejo-historial-toggle"
            onClick={() => setHistorialOpen(o => !o)}
            className="w-full flex items-center justify-between px-4 py-3 text-sm text-slate-300 hover:text-white transition-colors"
          >
            <span>Historial de consultas ({historial.length})</span>
            <span className="text-slate-500">{historialOpen ? '▲' : '▼'}</span>
          </button>
          {historialOpen && (
            <div className="border-t border-slate-700 p-4 space-y-2">
              {historial.length === 0
                ? <p className="text-sm text-slate-500">Sin consultas anteriores.</p>
                : historial.map((item, i) => (
                  <HistorialItem key={i} item={item} onSelect={handleSelectHistorial} />
                ))
              }
            </div>
          )}
        </div>

      </div>
    </div>
  );
}
