import { useState, useEffect, useCallback, useRef } from 'react';
import { useParams } from 'react-router-dom';
import { FolderOpen, Upload, MessageSquare, Paperclip, Send, CheckCircle2, Clock, AlertCircle } from 'lucide-react';
import api from '../api/axios';

const STATUS_CONFIG = {
  pendiente:   { label: 'Pendiente',   bg: '#FFF7ED', text: '#C2410C' },
  enviada:     { label: 'Enviada',     bg: '#EFF6FF', text: '#1D4ED8' },
  en_revision: { label: 'En revisión', bg: '#EDE9FE', text: '#5B21B6' },
  aceptada:    { label: 'Aceptada',    bg: '#F0FDF4', text: '#166534' },
  rechazada:   { label: 'Rechazada',   bg: '#FEF2F2', text: '#991B1B' },
};

function StatusBadge({ status }) {
  const cfg = STATUS_CONFIG[status] || STATUS_CONFIG.pendiente;
  return (
    <span style={{ padding: '3px 8px', borderRadius: 10, fontSize: 11, fontWeight: 600, background: cfg.bg, color: cfg.text }}>
      {cfg.label}
    </span>
  );
}

function RequestCard({ req, linkPublico, onUpdate, nombreExterno }) {
  const [uploading, setUploading] = useState(false);
  const [comment, setComment] = useState('');
  const [expanded, setExpanded] = useState(false);
  const fileRef = useRef();
  const [dragging, setDragging] = useState(false);

  const handleFiles = async (files) => {
    setUploading(true);
    for (const f of files) {
      const fd = new FormData();
      fd.append('file', f);
      await api.post(`/audit/public/${linkPublico}/requests/${req.id}/upload?nombre_externo=${encodeURIComponent(nombreExterno)}`, fd, {
        headers: { 'Content-Type': 'multipart/form-data' },
      });
    }
    setUploading(false);
    onUpdate();
  };

  const sendComment = async () => {
    if (!comment.trim()) return;
    await api.post(`/audit/public/${linkPublico}/requests/${req.id}/comments`, {
      texto: comment, autor_nombre: nombreExterno,
    });
    setComment('');
    onUpdate();
  };

  const externalComments = (req.comentarios || []).filter(c => c.tipo === 'externo');

  return (
    <div style={{ border: '1px solid #E2E8F0', borderRadius: 10, marginBottom: 12, overflow: 'hidden', background: '#fff' }}>
      {/* Header */}
      <div
        onClick={() => setExpanded(e => !e)}
        style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', padding: '14px 18px', cursor: 'pointer', userSelect: 'none' }}
      >
        <div style={{ display: 'flex', alignItems: 'center', gap: 12 }}>
          <div>
            <div style={{ fontSize: 13, fontWeight: 600, color: '#1B2A4A' }}>{req.nombre}</div>
            <div style={{ fontSize: 11, color: '#64748B', marginTop: 2 }}>
              {req.categoria}
              {req.fecha_limite && ` · Vence ${req.fecha_limite}`}
            </div>
          </div>
        </div>
        <div style={{ display: 'flex', alignItems: 'center', gap: 10 }}>
          {req.archivos?.length > 0 && (
            <span style={{ display: 'flex', alignItems: 'center', gap: 3, fontSize: 11, color: '#3B82F6' }}>
              <Paperclip size={11} />{req.archivos.length}
            </span>
          )}
          <StatusBadge status={req.status} />
          <span style={{ color: '#CBD5E1', fontSize: 16 }}>{expanded ? '▲' : '▼'}</span>
        </div>
      </div>

      {expanded && (
        <div style={{ borderTop: '1px solid #F1F5F9', padding: '16px 18px' }}>
          {req.descripcion && (
            <p style={{ margin: '0 0 16px', fontSize: 13, color: '#475569', lineHeight: 1.6 }}>{req.descripcion}</p>
          )}

          {req.motivo_rechazo && (
            <div style={{ marginBottom: 16, padding: '10px 14px', background: '#FEF2F2', borderRadius: 6, fontSize: 12, color: '#991B1B' }}>
              <strong>Observación:</strong> {req.motivo_rechazo}
            </div>
          )}

          {/* Files already uploaded */}
          {req.archivos?.length > 0 && (
            <div style={{ marginBottom: 16 }}>
              <div style={{ fontSize: 12, fontWeight: 600, color: '#374151', marginBottom: 8 }}>Archivos enviados:</div>
              {req.archivos.map((f, i) => (
                <div key={i} style={{ display: 'flex', alignItems: 'center', gap: 8, padding: '6px 10px', background: '#F8FAFC', borderRadius: 6, marginBottom: 4 }}>
                  <Paperclip size={12} color="#64748B" />
                  <span style={{ fontSize: 12, color: '#374151', flex: 1 }}>{f.nombre}</span>
                  <span style={{ fontSize: 10, color: '#94A3B8' }}>{(f.tamaño / 1024).toFixed(1)} KB</span>
                </div>
              ))}
            </div>
          )}

          {/* Upload — only if not accepted */}
          {req.status !== 'aceptada' && (
            <div style={{ marginBottom: 16 }}>
              <div style={{ fontSize: 12, fontWeight: 600, color: '#374151', marginBottom: 8 }}>Subir documentos:</div>
              <div
                onDragOver={e => { e.preventDefault(); setDragging(true); }}
                onDragLeave={() => setDragging(false)}
                onDrop={e => { e.preventDefault(); setDragging(false); handleFiles(Array.from(e.dataTransfer.files)); }}
                onClick={() => fileRef.current?.click()}
                style={{
                  border: `2px dashed ${dragging ? '#C9A84C' : '#E2E8F0'}`,
                  borderRadius: 8, padding: '20px', textAlign: 'center', cursor: 'pointer',
                  background: dragging ? '#FFFBEB' : '#F8FAFC', transition: 'all .15s',
                }}>
                <Upload size={20} color="#94A3B8" style={{ margin: '0 auto 6px', display: 'block' }} />
                <p style={{ margin: 0, fontSize: 12, color: '#64748B' }}>
                  {uploading ? 'Subiendo...' : 'Arrastra archivos o haz clic aquí'}
                </p>
                <p style={{ margin: '3px 0 0', fontSize: 11, color: '#94A3B8' }}>PDF, Excel, Word, imágenes</p>
              </div>
              <input ref={fileRef} type="file" multiple style={{ display: 'none' }}
                onChange={e => handleFiles(Array.from(e.target.files))} />
            </div>
          )}

          {/* External comments */}
          <div>
            <div style={{ fontSize: 12, fontWeight: 600, color: '#374151', marginBottom: 8 }}>Comentarios:</div>
            {externalComments.length === 0 && (
              <p style={{ fontSize: 12, color: '#94A3B8', margin: '0 0 10px' }}>Sin comentarios aún.</p>
            )}
            {externalComments.map((c, i) => (
              <div key={i} style={{ padding: '8px 12px', background: '#EFF6FF', borderRadius: 6, marginBottom: 6 }}>
                <div style={{ fontSize: 11, color: '#64748B', marginBottom: 3 }}>
                  {c.autor_nombre} · {c.fecha?.slice(0, 16).replace('T', ' ')}
                </div>
                <p style={{ margin: 0, fontSize: 12, color: '#1E40AF' }}>{c.texto}</p>
              </div>
            ))}
            <div style={{ display: 'flex', gap: 8, marginTop: 8 }}>
              <input value={comment} onChange={e => setComment(e.target.value)}
                onKeyDown={e => e.key === 'Enter' && sendComment()}
                placeholder="Escribe un comentario..."
                style={{ flex: 1, padding: '7px 12px', border: '1px solid #D1D5DB', borderRadius: 6, fontSize: 12 }} />
              <button onClick={sendComment}
                style={{ padding: '7px 12px', background: '#1B2A4A', color: '#fff', border: 'none', borderRadius: 6, cursor: 'pointer' }}>
                <Send size={14} />
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}

export default function AuditPublic() {
  const { linkPublico } = useParams();
  const [data, setData] = useState(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState('');
  const [nombreExterno, setNombreExterno] = useState('');
  const [nombreConfirmed, setNombreConfirmed] = useState(false);
  const [activeCategory, setActiveCategory] = useState(null);

  const load = useCallback(async () => {
    try {
      const res = await api.get(`/audit/public/${linkPublico}`);
      setData(res.data);
    } catch {
      setError('Este enlace no es válido o el expediente está cerrado.');
    } finally {
      setLoading(false);
    }
  }, [linkPublico]);

  useEffect(() => { load(); }, [load]);

  if (loading) return (
    <div style={{ minHeight: '100vh', display: 'flex', alignItems: 'center', justifyContent: 'center', background: '#F8FAFC' }}>
      <div style={{ color: '#64748B' }}>Cargando expediente...</div>
    </div>
  );

  if (error) return (
    <div style={{ minHeight: '100vh', display: 'flex', alignItems: 'center', justifyContent: 'center', background: '#F8FAFC' }}>
      <div style={{ textAlign: 'center', padding: 40 }}>
        <AlertCircle size={40} color="#EF4444" style={{ marginBottom: 12 }} />
        <p style={{ color: '#374151', fontSize: 15 }}>{error}</p>
      </div>
    </div>
  );

  if (!nombreConfirmed) return (
    <div style={{ minHeight: '100vh', display: 'flex', alignItems: 'center', justifyContent: 'center', background: '#F8FAFC' }}>
      <div style={{ background: '#fff', borderRadius: 12, padding: 36, width: 380, boxShadow: '0 4px 24px rgba(0,0,0,.08)' }}>
        <div style={{ display: 'flex', alignItems: 'center', gap: 10, marginBottom: 20 }}>
          <FolderOpen size={24} color="#C9A84C" />
          <h2 style={{ margin: 0, fontSize: 17, color: '#1B2A4A' }}>Portal de Auditoría</h2>
        </div>
        <p style={{ fontSize: 14, color: '#475569', marginBottom: 20 }}>
          Ingresa tu nombre para identificar los archivos y comentarios que envíes.
        </p>
        <input
          value={nombreExterno}
          onChange={e => setNombreExterno(e.target.value)}
          onKeyDown={e => e.key === 'Enter' && nombreExterno.trim() && setNombreConfirmed(true)}
          placeholder="Tu nombre o empresa"
          style={{ width: '100%', padding: '9px 13px', border: '1px solid #D1D5DB', borderRadius: 7, fontSize: 14, marginBottom: 16, boxSizing: 'border-box' }}
        />
        <button
          onClick={() => nombreExterno.trim() && setNombreConfirmed(true)}
          disabled={!nombreExterno.trim()}
          style={{ width: '100%', padding: '10px', background: '#1B2A4A', color: '#fff', border: 'none', borderRadius: 7, cursor: 'pointer', fontSize: 14, fontWeight: 600 }}>
          Continuar
        </button>
      </div>
    </div>
  );

  const { engagement, solicitudes = [] } = data;
  const categorias = engagement.categorias || [];
  const filtered = activeCategory ? solicitudes.filter(r => r.categoria === activeCategory) : solicitudes;
  const pendingCount = solicitudes.filter(r => ['pendiente', 'rechazada'].includes(r.status)).length;
  const acceptedCount = solicitudes.filter(r => r.status === 'aceptada').length;

  return (
    <div style={{ minHeight: '100vh', background: '#F8FAFC' }}>
      {/* Header */}
      <div style={{ background: '#1B2A4A', color: '#fff', padding: '20px 32px' }}>
        <div style={{ maxWidth: 860, margin: '0 auto', display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
          <div>
            <div style={{ display: 'flex', alignItems: 'center', gap: 10, marginBottom: 4 }}>
              <FolderOpen size={20} color="#C9A84C" />
              <h1 style={{ margin: 0, fontSize: 18, fontWeight: 700 }}>{engagement.nombre}</h1>
            </div>
            <p style={{ margin: 0, fontSize: 12, color: '#94A3B8' }}>
              {engagement.año} · {engagement.tipo}
            </p>
          </div>
          <div style={{ display: 'flex', gap: 20, textAlign: 'center' }}>
            <div>
              <div style={{ fontSize: 20, fontWeight: 700, color: '#F59E0B' }}>{pendingCount}</div>
              <div style={{ fontSize: 11, color: '#94A3B8' }}>Pendientes</div>
            </div>
            <div>
              <div style={{ fontSize: 20, fontWeight: 700, color: '#10B981' }}>{acceptedCount}</div>
              <div style={{ fontSize: 11, color: '#94A3B8' }}>Aceptadas</div>
            </div>
            <div>
              <div style={{ fontSize: 20, fontWeight: 700, color: '#fff' }}>{solicitudes.length}</div>
              <div style={{ fontSize: 11, color: '#94A3B8' }}>Total</div>
            </div>
          </div>
        </div>
      </div>

      <div style={{ maxWidth: 860, margin: '0 auto', padding: '28px 16px', display: 'flex', gap: 24 }}>
        {/* Category sidebar */}
        <div style={{ width: 180, flexShrink: 0 }}>
          <div style={{ background: '#fff', borderRadius: 10, border: '1px solid #E2E8F0', overflow: 'hidden' }}>
            <div style={{ padding: '10px 14px', fontSize: 11, fontWeight: 700, color: '#94A3B8', background: '#F8FAFC', borderBottom: '1px solid #E2E8F0' }}>
              CATEGORÍAS
            </div>
            <div onClick={() => setActiveCategory(null)}
              style={{ padding: '8px 14px', cursor: 'pointer', fontSize: 13, fontWeight: !activeCategory ? 700 : 400, color: !activeCategory ? '#1B2A4A' : '#64748B', background: !activeCategory ? '#EFF6FF' : 'transparent' }}>
              Todas <span style={{ color: '#94A3B8', fontSize: 11 }}>({solicitudes.length})</span>
            </div>
            {categorias.map(cat => {
              const cnt = solicitudes.filter(r => r.categoria === cat).length;
              if (!cnt) return null;
              return (
                <div key={cat} onClick={() => setActiveCategory(activeCategory === cat ? null : cat)}
                  style={{ padding: '7px 14px', cursor: 'pointer', fontSize: 12, fontWeight: activeCategory === cat ? 700 : 400, color: activeCategory === cat ? '#1B2A4A' : '#64748B', background: activeCategory === cat ? '#EFF6FF' : 'transparent' }}>
                  {cat} <span style={{ color: '#94A3B8', fontSize: 11 }}>({cnt})</span>
                </div>
              );
            })}
          </div>
        </div>

        {/* Requests */}
        <div style={{ flex: 1 }}>
          <div style={{ marginBottom: 12, display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
            <h2 style={{ margin: 0, fontSize: 15, color: '#1B2A4A', fontWeight: 600 }}>
              {activeCategory || 'Todas las solicitudes'}
              <span style={{ marginLeft: 8, fontSize: 12, color: '#94A3B8', fontWeight: 400 }}>({filtered.length})</span>
            </h2>
            <span style={{ fontSize: 12, color: '#64748B' }}>Accediendo como: <strong>{nombreExterno}</strong></span>
          </div>
          {filtered.map(req => (
            <RequestCard key={req.id} req={req} linkPublico={linkPublico} onUpdate={load} nombreExterno={nombreExterno} />
          ))}
          {filtered.length === 0 && (
            <div style={{ textAlign: 'center', padding: '40px 20px', color: '#94A3B8', fontSize: 13 }}>
              Sin solicitudes en esta categoría.
            </div>
          )}
        </div>
      </div>
    </div>
  );
}
