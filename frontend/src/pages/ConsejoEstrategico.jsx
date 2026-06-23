import { useState, useEffect } from 'react';
import api from '../api/axios';
import ReactMarkdown from 'react-markdown';
import { jsPDF } from 'jspdf';

// ── Colores por asesor ─────────────────────────────────────────────────────────
const ASESORES = [
  { emoji: '🔴', key: 'CONTRARIAN',          label: 'El Contrarian',                     borderColor: '#C00000', headerBg: '#FFF5F5', textColor: '#C00000' },
  { emoji: '🔵', key: 'PRIMEROS PRINCIPIOS', label: 'El Pensador de Primeros Principios', borderColor: '#1B3A6B', headerBg: '#EEF3FB', textColor: '#1B3A6B' },
  { emoji: '🟢', key: 'EXPANSIONISTA',       label: 'El Expansionista',                  borderColor: '#1E7145', headerBg: '#EEF8F2', textColor: '#1E7145' },
  { emoji: '🟡', key: 'OUTSIDER',            label: 'El Outsider',                       borderColor: '#B8860B', headerBg: '#FFFBEE', textColor: '#8B6500' },
  { emoji: '🟠', key: 'EJECUTOR',            label: 'El Ejecutor',                       borderColor: '#C55A11', headerBg: '#FFF5EE', textColor: '#C55A11' },
];

const NAVY    = '#1B3A6B';
const GOLD    = '#C9A84C';
const PAGE_BG = '#F8F9FA';

// ── Definiciones para PDF ──────────────────────────────────────────────────────
const PDF_ASESORES = [
  { emoji: '🔴', key: 'CONTRARIAN',          label: 'El Contrarian',                     bg: [255, 235, 235], fg: [192, 0, 0]   },
  { emoji: '🔵', key: 'PRIMEROS PRINCIPIOS', label: 'El Pensador de Primeros Principios', bg: [235, 243, 255], fg: [27, 58, 107]  },
  { emoji: '🟢', key: 'EXPANSIONISTA',       label: 'El Expansionista',                  bg: [235, 248, 240], fg: [30, 113, 69]  },
  { emoji: '🟡', key: 'OUTSIDER',            label: 'El Outsider',                       bg: [255, 251, 230], fg: [139, 101, 0]  },
  { emoji: '🟠', key: 'EJECUTOR',            label: 'El Ejecutor',                       bg: [255, 243, 232], fg: [197, 90, 17]  },
];

// ── Helpers ────────────────────────────────────────────────────────────────────
function stripMarkdown(text) {
  return text
    .replace(/\*\*(.+?)\*\*/gs, '$1')
    .replace(/\*(.+?)\*/gs, '$1')
    .replace(/^#{1,3}\s+/gm, '')
    .replace(/`(.+?)`/g, '$1')
    .trim();
}

function parseRespuesta(texto) {
  if (!texto) return { secciones: [], presidente: '' };
  const presidenteMatch = texto.match(/PRESIDENTE DEL CONSEJO([\s\S]*?)$/i);
  const presidente = presidenteMatch ? presidenteMatch[0].trim() : '';
  const cuerpo = presidenteMatch ? texto.slice(0, presidenteMatch.index) : texto;
  const secciones = ASESORES.map((asesor) => {
    const regex = new RegExp(
      `${asesor.emoji}[^\\n]*${asesor.key}[^\\n]*([\\s\\S]*?)(?=(?:🔴|🔵|🟢|🟡|🟠|PRESIDENTE)|$)`,
      'i'
    );
    const match = cuerpo.match(regex);
    return { ...asesor, contenido: match ? match[0].trim() : '' };
  }).filter(s => s.contenido);
  return { secciones, presidente };
}

// ── Card por asesor ────────────────────────────────────────────────────────────
function SeccionCard({ seccion }) {
  return (
    <div style={{
      background: '#FFFFFF',
      borderLeft: `4px solid ${seccion.borderColor}`,
      borderRadius: '4px',
      boxShadow: '0 1px 4px rgba(0,0,0,0.08)',
      overflow: 'hidden',
    }}>
      <div style={{
        background: seccion.headerBg,
        padding: '10px 16px',
        borderBottom: `1px solid ${seccion.borderColor}30`,
      }}>
        <span style={{ fontWeight: 700, color: seccion.textColor, fontSize: '13px' }}>
          {seccion.emoji} {seccion.label}
        </span>
      </div>
      <div style={{ padding: '16px', color: '#1f2937' }} className="prose prose-sm max-w-none">
        <ReactMarkdown>{seccion.contenido}</ReactMarkdown>
      </div>
    </div>
  );
}

// ── Item de historial ──────────────────────────────────────────────────────────
function HistorialItem({ item, onSelect }) {
  const fecha = item.created_at
    ? new Date(item.created_at).toLocaleString('es-MX', { dateStyle: 'short', timeStyle: 'short' })
    : '';
  return (
    <button
      onClick={() => onSelect(item)}
      style={{ background: '#FFFFFF', border: '1px solid #E2E8F0' }}
      className="w-full text-left p-3 rounded hover:border-gray-400 transition-colors"
    >
      <p className="text-xs text-gray-400 mb-1">{fecha}</p>
      <p className="text-sm text-gray-700 truncate">{item.pregunta}</p>
    </button>
  );
}

// ── Componente principal ───────────────────────────────────────────────────────
export default function ConsejoEstrategico() {
  const [pregunta, setPregunta]           = useState('');
  const [loading, setLoading]             = useState(false);
  const [respuesta, setRespuesta]         = useState(null);
  const [error, setError]                 = useState('');
  const [historial, setHistorial]         = useState([]);
  const [historialOpen, setHistorialOpen] = useState(false);
  const [copied, setCopied]               = useState(false);
  const [loadingMsg, setLoadingMsg]       = useState('');
  const [generatingPDF, setGeneratingPDF] = useState(false);

  useEffect(() => {
    api.get('/ia/consejo-estrategico/historial')
      .then(r => setHistorial(r.data.historial || []))
      .catch(() => {});
  }, []);

  const LOADING_MSGS = [
    'Consultando al Contrarian y Pensador de Primeros Principios...',
    'Analizando con el Expansionista y el Outsider...',
    'El Ejecutor está definiendo el plan de acción...',
    'El Presidente del Consejo está sintetizando las perspectivas...',
  ];

  useEffect(() => {
    if (!loading) { setLoadingMsg(''); return; }
    setLoadingMsg(LOADING_MSGS[0]);
    let idx = 1;
    const timer = setInterval(() => {
      setLoadingMsg(LOADING_MSGS[Math.min(idx, LOADING_MSGS.length - 1)]);
      idx++;
    }, 30000);
    return () => clearInterval(timer);
  }, [loading]); // eslint-disable-line react-hooks/exhaustive-deps

  async function handleSubmit(e) {
    e.preventDefault();
    if (!pregunta.trim()) return;
    setLoading(true);
    setError('');
    setRespuesta(null);
    try {
      const r = await api.post('/ia/consejo-estrategico', { pregunta }, { timeout: 180000 });
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

  async function handleBorrarHistorial() {
    if (!window.confirm('¿Borrar todo el historial de consultas?')) return;
    try {
      await api.delete('/ia/consejo-estrategico/historial');
      setHistorial([]);
    } catch {
      // silently ignore
    }
  }

  function generarPDF() {
    if (!respuesta) return;
    setGeneratingPDF(true);

    try {
      const doc     = new jsPDF('p', 'mm', 'letter');
      const C_NAVY  = [27,  58,  107];
      const C_GOLD  = [201, 168, 76];
      const C_GRIS  = [89,  89,  89];
      const C_WHITE = [255, 255, 255];
      const PW      = 216;   // page width mm
      const PH      = 279;   // page height mm
      const ML      = 15;    // margin left
      const MR      = 15;    // margin right
      const UW      = PW - ML - MR;  // usable width = 186mm
      const MAX_Y   = 260;

      // ── Portada ────────────────────────────────────────────────
      // Fondo blanco
      doc.setFillColor(255, 255, 255);
      doc.rect(0, 0, PW, PH, 'F');

      // Línea dorada superior
      doc.setDrawColor(...C_GOLD);
      doc.setLineWidth(1.5);
      doc.line(ML, 20, PW - MR, 20);

      doc.setFont('helvetica', 'bold');
      doc.setFontSize(14);
      doc.setTextColor(...C_GOLD);
      doc.text('CONSEJO ESTRATEGICO', PW / 2, 80, { align: 'center' });

      doc.setFont('helvetica', 'bold');
      doc.setFontSize(22);
      doc.setTextColor(...C_NAVY);
      doc.text('Analisis Estrategico - TaxnFin', PW / 2, 100, { align: 'center' });

      doc.setDrawColor(...C_GOLD);
      doc.setLineWidth(0.5);
      doc.line(ML + 20, 115, PW - MR - 20, 115);

      doc.setFont('helvetica', 'normal');
      doc.setFontSize(10);
      doc.setTextColor(...C_GRIS);
      doc.text('Pregunta analizada:', PW / 2, 130, { align: 'center' });

      doc.setFont('helvetica', 'italic');
      doc.setFontSize(11);
      doc.setTextColor(40, 40, 40);
      const qLines = doc.splitTextToSize(`"${pregunta}"`, UW - 20);
      doc.text(qLines, PW / 2, 140, { align: 'center' });

      doc.setFont('helvetica', 'normal');
      doc.setFontSize(9);
      doc.setTextColor(...C_GRIS);
      const fechaStr = new Date().toLocaleDateString('es-MX', { year: 'numeric', month: 'long', day: 'numeric' });
      doc.text(fechaStr, PW / 2, 200, { align: 'center' });

      // Línea dorada inferior
      doc.setDrawColor(...C_GOLD);
      doc.setLineWidth(1.5);
      doc.line(ML, 260, PW - MR, 260);

      // ── Páginas de contenido ───────────────────────────────────
      doc.addPage();
      let y = 20;

      function checkBreak(needed = 10) {
        if (y + needed > MAX_Y) {
          doc.addPage();
          y = 20;
        }
      }

      function renderSeccion(label, contenido, bgColor, fgColor, isPresidente = false) {
        const clean = stripMarkdown(contenido);
        const lines = doc.splitTextToSize(clean, UW - 4);

        checkBreak(8 + 5);  // header + at least one line

        // Header bar
        doc.setFillColor(...bgColor);
        doc.rect(ML, y, UW, 8, 'F');
        doc.setFont('helvetica', 'bold');
        doc.setFontSize(10);
        doc.setTextColor(...fgColor);
        doc.text(label, ML + 3, y + 5.5);
        y += 9;

        // Content lines
        doc.setFont('helvetica', isPresidente ? 'bold' : 'normal');
        doc.setFontSize(10);

        for (const line of lines) {
          checkBreak(6);
          if (isPresidente) {
            doc.setFillColor(...C_NAVY);
            doc.rect(ML, y - 4, UW, 5.5, 'F');
            doc.setTextColor(...C_WHITE);
          } else {
            doc.setTextColor(40, 40, 40);
          }
          doc.text(line, ML + 2, y);
          y += 5;
        }
        y += 4;
      }

      // Parsear secciones
      const presidenteMatch = respuesta.match(/PRESIDENTE DEL CONSEJO([\s\S]*?)$/i);
      const presidente      = presidenteMatch ? presidenteMatch[0].trim() : '';
      const cuerpo          = presidenteMatch ? respuesta.slice(0, presidenteMatch.index) : respuesta;

      for (const def of PDF_ASESORES) {
        const regex = new RegExp(
          `${def.emoji}[^\\n]*${def.key}[^\\n]*([\\s\\S]*?)(?=(?:🔴|🔵|🟢|🟡|🟠|PRESIDENTE)|$)`,
          'i'
        );
        const match = cuerpo.match(regex);
        if (match) {
          renderSeccion(`${def.emoji} ${def.label}`, match[0].trim(), def.bg, def.fg);
        }
      }

      if (presidente) {
        checkBreak(15);
        renderSeccion('PRESIDENTE DEL CONSEJO', presidente, C_NAVY, C_WHITE, true);
      }

      const dateStr = new Date().toISOString().slice(0, 10).replace(/-/g, '');
      doc.save(`Consejo_Estrategico_TaxnFin_${dateStr}.pdf`);
    } catch (err) {
      console.error('[PDF] Error:', err);
    } finally {
      setGeneratingPDF(false);
    }
  }

  const parsed = respuesta ? parseRespuesta(respuesta) : null;

  return (
    <div style={{ minHeight: '100vh', background: PAGE_BG, padding: '24px', fontFamily: 'system-ui, Arial, sans-serif' }}>
      <div style={{ maxWidth: '860px', margin: '0 auto' }} className="space-y-5">

        {/* Header */}
        <div style={{
          background: '#FFFFFF',
          borderBottom: `3px solid ${GOLD}`,
          borderRadius: '4px 4px 0 0',
          padding: '20px 24px',
          boxShadow: '0 1px 3px rgba(0,0,0,0.07)',
        }}>
          <h1 style={{ color: NAVY, fontSize: '22px', fontWeight: 700, margin: 0 }}>
            🏛️ Consejo Estratégico IA
          </h1>
          <p style={{ color: '#64748B', fontSize: '13px', margin: '4px 0 0' }}>
            Analiza cualquier decisión desde 5 perspectivas independientes
          </p>
        </div>

        {/* Input */}
        <form onSubmit={handleSubmit} className="space-y-3">
          <textarea
            data-testid="consejo-pregunta"
            value={pregunta}
            onChange={e => setPregunta(e.target.value)}
            rows={4}
            placeholder="Escribe tu pregunta o decisión aquí. Ejemplo: '¿Debo contratar un vendedor antes de tener 20 clientes?' o '¿Conviene bajar precios para conseguir los primeros clientes?'"
            disabled={loading}
            style={{
              width: '100%',
              background: '#FFFFFF',
              border: '1px solid #CBD5E1',
              borderRadius: '4px',
              padding: '12px 14px',
              fontSize: '14px',
              color: NAVY,
              resize: 'vertical',
              outline: 'none',
              boxSizing: 'border-box',
            }}
          />
          <div className="flex items-center gap-3 flex-wrap">
            <button
              data-testid="consejo-submit"
              type="submit"
              disabled={loading || !pregunta.trim()}
              style={{
                background: loading || !pregunta.trim() ? '#94A3B8' : NAVY,
                color: '#FFFFFF',
                border: 'none',
                borderRadius: '4px',
                padding: '9px 20px',
                fontSize: '14px',
                fontWeight: 600,
                cursor: loading || !pregunta.trim() ? 'not-allowed' : 'pointer',
                display: 'flex',
                alignItems: 'center',
                gap: '8px',
                transition: 'background 0.15s',
              }}
            >
              {loading ? (
                <>
                  <svg className="animate-spin h-4 w-4" viewBox="0 0 24 24" fill="none">
                    <circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4" />
                    <path className="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8v8H4z" />
                  </svg>
                  Consultando al consejo...
                </>
              ) : 'Consultar al Consejo'}
            </button>

            {respuesta && (
              <button
                type="button"
                onClick={handleNueva}
                style={{ background: 'none', border: 'none', color: '#64748B', fontSize: '13px', cursor: 'pointer' }}
              >
                Nueva consulta
              </button>
            )}

            {loading && loadingMsg && (
              <span style={{ fontSize: '12px', color: '#64748B', fontStyle: 'italic' }}>
                {loadingMsg}
              </span>
            )}
          </div>
        </form>

        {/* Error */}
        {error && (
          <div style={{
            background: '#FFF5F5',
            border: '1px solid #FCA5A5',
            borderRadius: '4px',
            padding: '12px 16px',
            fontSize: '13px',
            color: '#B91C1C',
          }}>
            {error}
          </div>
        )}

        {/* Resultado */}
        {parsed && (
          <div className="space-y-4">
            {/* Barra de acciones */}
            <div className="flex items-center justify-between flex-wrap gap-2">
              <h2 style={{ color: NAVY, fontSize: '12px', fontWeight: 700, textTransform: 'uppercase', letterSpacing: '0.08em', margin: 0 }}>
                Análisis del Consejo
              </h2>
              <div className="flex items-center gap-2">
                <button
                  data-testid="consejo-copy"
                  onClick={handleCopy}
                  style={{
                    background: '#FFFFFF',
                    border: '1px solid #CBD5E1',
                    borderRadius: '4px',
                    padding: '6px 12px',
                    fontSize: '12px',
                    color: '#475569',
                    cursor: 'pointer',
                  }}
                >
                  {copied ? '✓ Copiado' : 'Copiar análisis'}
                </button>
                <button
                  data-testid="consejo-pdf"
                  onClick={generarPDF}
                  disabled={generatingPDF}
                  style={{
                    background: generatingPDF ? '#94A3B8' : GOLD,
                    border: 'none',
                    borderRadius: '4px',
                    padding: '6px 12px',
                    fontSize: '12px',
                    color: '#FFFFFF',
                    fontWeight: 600,
                    cursor: generatingPDF ? 'not-allowed' : 'pointer',
                  }}
                >
                  {generatingPDF ? 'Generando...' : '📄 Descargar PDF'}
                </button>
              </div>
            </div>

            {/* Cards por asesor */}
            {parsed.secciones.length > 0
              ? parsed.secciones.map(s => <SeccionCard key={s.key} seccion={s} />)
              : (
                <div style={{ background: '#FFFFFF', border: '1px solid #E2E8F0', borderRadius: '4px', padding: '16px' }}>
                  <div className="prose prose-sm max-w-none">
                    <ReactMarkdown>{respuesta}</ReactMarkdown>
                  </div>
                </div>
              )
            }

            {/* Presidente del Consejo */}
            {parsed.presidente && (
              <div style={{
                background: NAVY,
                border: `2px solid ${GOLD}`,
                borderRadius: '4px',
                padding: '20px',
                boxShadow: '0 2px 8px rgba(27,58,107,0.15)',
              }}>
                <div className="prose prose-sm prose-invert max-w-none">
                  <ReactMarkdown>{parsed.presidente}</ReactMarkdown>
                </div>
              </div>
            )}
          </div>
        )}

        {/* Historial */}
        <div style={{ background: '#FFFFFF', border: '1px solid #E2E8F0', borderRadius: '4px', boxShadow: '0 1px 3px rgba(0,0,0,0.05)' }}>
          <button
            data-testid="consejo-historial-toggle"
            onClick={() => setHistorialOpen(o => !o)}
            style={{
              width: '100%',
              display: 'flex',
              justifyContent: 'space-between',
              alignItems: 'center',
              padding: '12px 16px',
              background: 'none',
              border: 'none',
              fontSize: '13px',
              color: '#475569',
              cursor: 'pointer',
            }}
          >
            <span>Historial de consultas ({historial.length})</span>
            <div className="flex items-center gap-2">
              {historial.length > 0 && (
                <span
                  role="button"
                  onClick={e => { e.stopPropagation(); handleBorrarHistorial(); }}
                  style={{ fontSize: '11px', color: '#EF4444', cursor: 'pointer', padding: '2px 8px', border: '1px solid #FCA5A5', borderRadius: '4px' }}
                >
                  Borrar todo
                </span>
              )}
              <span style={{ color: '#94A3B8' }}>{historialOpen ? '▲' : '▼'}</span>
            </div>
          </button>
          {historialOpen && (
            <div style={{ borderTop: '1px solid #E2E8F0', padding: '12px', background: PAGE_BG }} className="space-y-2">
              {historial.length === 0
                ? <p style={{ fontSize: '13px', color: '#94A3B8' }}>Sin consultas anteriores.</p>
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
