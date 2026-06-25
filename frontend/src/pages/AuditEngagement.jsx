import { useState, useEffect, useCallback, useRef } from 'react';
import { useParams, useNavigate } from 'react-router-dom';
import {
  ArrowLeft, Plus, Upload, Download, Trash2, MessageSquare,
  CheckCircle2, XCircle, RotateCcw, ChevronDown, ChevronUp,
  Paperclip, Clock, AlertTriangle, User, Send, X,
} from 'lucide-react';
import api from '../api/axios';

// ─── constants ────────────────────────────────────────────────────────────────

const STATUS_CONFIG = {
  pendiente:   { label: 'Pendiente',   bg: '#FFF7ED', text: '#C2410C', dot: '#F59E0B' },
  enviada:     { label: 'Enviada',     bg: '#EFF6FF', text: '#1D4ED8', dot: '#60A5FA' },
  en_revision: { label: 'En revisión', bg: '#EDE9FE', text: '#5B21B6', dot: '#7C3AED' },
  aceptada:    { label: 'Aceptada',    bg: '#F0FDF4', text: '#166534', dot: '#10B981' },
  rechazada:   { label: 'Rechazada',   bg: '#FEF2F2', text: '#991B1B', dot: '#EF4444' },
};

const PRIORIDAD_CONFIG = {
  alta:  { label: 'Alta',  color: '#EF4444' },
  media: { label: 'Media', color: '#F59E0B' },
  baja:  { label: 'Baja',  color: '#10B981' },
};

const ALL_TABS = ['Todas', 'Pendientes', 'Enviadas', 'En revisión', 'Aceptadas', 'Rechazadas'];
const TAB_STATUS = {
  'Pendientes': 'pendiente', 'Enviadas': 'enviada',
  'En revisión': 'en_revision', 'Aceptadas': 'aceptada', 'Rechazadas': 'rechazada',
};

// ─── sub-components ───────────────────────────────────────────────────────────

function StatusBadge({ status }) {
  const cfg = STATUS_CONFIG[status] || STATUS_CONFIG.pendiente;
  return (
    <span style={{
      display: 'inline-flex', alignItems: 'center', gap: 5,
      padding: '3px 8px', borderRadius: 12, fontSize: 11, fontWeight: 600,
      background: cfg.bg, color: cfg.text,
    }}>
      <span style={{ width: 6, height: 6, borderRadius: '50%', background: cfg.dot }} />
      {cfg.label}
    </span>
  );
}

function CategoryProgress({ categorias = [], requests = [] }) {
  return (
    <div style={{ display: 'flex', flexWrap: 'wrap', gap: 6 }}>
      {categorias.map(cat => {
        const catReqs = requests.filter(r => r.categoria === cat);
        const total = catReqs.length;
        const aceptadas = catReqs.filter(r => r.status === 'aceptada').length;
        const rechazadas = catReqs.filter(r => r.status === 'rechazada').length;
        const revision = catReqs.filter(r => r.status === 'en_revision').length;
        const pendientes = catReqs.filter(r => r.status === 'pendiente' || r.status === 'enviada').length;

        let bg = '#F1F5F9', text = '#64748B';
        if (total === 0) { bg = '#F1F5F9'; text = '#94A3B8'; }
        else if (aceptadas === total) { bg = '#D1FAE5'; text = '#065F46'; }
        else if (rechazadas > 0) { bg = '#FEE2E2'; text = '#991B1B'; }
        else if (revision > 0) { bg = '#EDE9FE'; text = '#5B21B6'; }
        else if (pendientes > 0) { bg = '#FEF3C7'; text = '#92400E'; }

        return (
          <div key={cat} title={`${cat}: ${aceptadas}/${total} aceptadas`}
            style={{ padding: '4px 10px', borderRadius: 6, fontSize: 11, fontWeight: 600, background: bg, color: text }}>
            {cat} {total > 0 ? `${aceptadas}/${total}` : ''}
          </div>
        );
      })}
    </div>
  );
}

function RejectModal({ onConfirm, onClose }) {
  const [motivo, setMotivo] = useState('');
  return (
    <div style={{ position: 'fixed', inset: 0, background: 'rgba(0,0,0,.4)', display: 'flex', alignItems: 'center', justifyContent: 'center', zIndex: 1100 }}>
      <div style={{ background: '#fff', borderRadius: 12, padding: 28, width: 400 }}>
        <h4 style={{ margin: '0 0 16px', color: '#1B2A4A' }}>Motivo de rechazo</h4>
        <textarea
          value={motivo} onChange={e => setMotivo(e.target.value)}
          placeholder="Describe por qué se rechaza esta solicitud..."
          style={{ width: '100%', minHeight: 100, padding: '8px 12px', border: '1px solid #D1D5DB', borderRadius: 6, fontSize: 13, resize: 'vertical', boxSizing: 'border-box' }}
        />
        <div style={{ display: 'flex', gap: 10, justifyContent: 'flex-end', marginTop: 16 }}>
          <button onClick={onClose} style={{ padding: '7px 16px', border: '1px solid #D1D5DB', borderRadius: 6, background: '#fff', cursor: 'pointer', fontSize: 13 }}>Cancelar</button>
          <button onClick={() => onConfirm(motivo)} style={{ padding: '7px 16px', background: '#EF4444', color: '#fff', border: 'none', borderRadius: 6, cursor: 'pointer', fontSize: 13 }}>Rechazar</button>
        </div>
      </div>
    </div>
  );
}

function RequestDetail({ req, engagementId, onUpdate }) {
  const [comment, setComment] = useState('');
  const [uploading, setUploading] = useState(false);
  const [showReject, setShowReject] = useState(false);
  const [dragging, setDragging] = useState(false);
  const fileRef = useRef();

  const changeStatus = async (status, motivo_rechazo = '') => {
    await api.put(`/audit/requests/${req.id}/status`, { status, motivo_rechazo });
    onUpdate();
    setShowReject(false);
  };

  const handleFiles = async (files) => {
    setUploading(true);
    for (const f of files) {
      const fd = new FormData();
      fd.append('file', f);
      await api.post(`/audit/requests/${req.id}/upload`, fd, {
        headers: { 'Content-Type': 'multipart/form-data' },
      });
    }
    setUploading(false);
    onUpdate();
  };

  const deleteFile = async (key) => {
    if (!window.confirm('¿Eliminar archivo?')) return;
    await api.delete(`/audit/requests/${req.id}/files/${encodeURIComponent(key)}`);
    onUpdate();
  };

  const downloadFile = async (key, nombre) => {
    const { data } = await api.get(`/audit/requests/${req.id}/files/${encodeURIComponent(key)}/download`);
    window.open(data.url, '_blank');
  };

  const sendComment = async () => {
    if (!comment.trim()) return;
    await api.post(`/audit/requests/${req.id}/comments`, { texto: comment, tipo: 'interno' });
    setComment('');
    onUpdate();
  };

  return (
    <div style={{ display: 'flex', flexDirection: 'column', height: '100%', overflow: 'hidden' }}>
      {/* Title + status */}
      <div style={{ padding: '20px 24px 16px', borderBottom: '1px solid #E2E8F0' }}>
        <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start', gap: 12, marginBottom: 8 }}>
          <h3 style={{ margin: 0, fontSize: 15, color: '#1B2A4A', fontWeight: 600, lineHeight: 1.4 }}>{req.nombre}</h3>
          <StatusBadge status={req.status} />
        </div>
        <div style={{ display: 'flex', gap: 12, flexWrap: 'wrap', fontSize: 12, color: '#64748B' }}>
          <span style={{ color: PRIORIDAD_CONFIG[req.prioridad]?.color || '#64748B', fontWeight: 600 }}>
            ● {PRIORIDAD_CONFIG[req.prioridad]?.label || req.prioridad}
          </span>
          <span>📁 {req.categoria}</span>
          {req.fecha_limite && <span>⏰ Vence {req.fecha_limite}</span>}
          {req.asignado_a && <span>👤 {req.asignado_a}</span>}
        </div>
        {req.descripcion && (
          <p style={{ margin: '10px 0 0', fontSize: 13, color: '#475569', lineHeight: 1.6 }}>{req.descripcion}</p>
        )}
        {req.motivo_rechazo && (
          <div style={{ marginTop: 10, padding: '8px 12px', background: '#FEF2F2', borderRadius: 6, fontSize: 12, color: '#991B1B' }}>
            <strong>Motivo de rechazo:</strong> {req.motivo_rechazo}
          </div>
        )}
      </div>

      {/* Scrollable content */}
      <div style={{ flex: 1, overflow: 'auto', padding: '16px 24px' }}>
        {/* Action buttons */}
        <div style={{ display: 'flex', gap: 8, marginBottom: 20, flexWrap: 'wrap' }}>
          {req.status !== 'aceptada' && (
            <button onClick={() => changeStatus('aceptada')}
              style={{ display: 'flex', alignItems: 'center', gap: 5, padding: '6px 12px', background: '#D1FAE5', color: '#065F46', border: 'none', borderRadius: 6, cursor: 'pointer', fontSize: 12, fontWeight: 600 }}>
              <CheckCircle2 size={13} /> Aceptar
            </button>
          )}
          {req.status !== 'rechazada' && (
            <button onClick={() => setShowReject(true)}
              style={{ display: 'flex', alignItems: 'center', gap: 5, padding: '6px 12px', background: '#FEE2E2', color: '#991B1B', border: 'none', borderRadius: 6, cursor: 'pointer', fontSize: 12, fontWeight: 600 }}>
              <XCircle size={13} /> Rechazar
            </button>
          )}
          {(req.status === 'rechazada' || req.status === 'aceptada') && (
            <button onClick={() => changeStatus('pendiente')}
              style={{ display: 'flex', alignItems: 'center', gap: 5, padding: '6px 12px', background: '#FEF3C7', color: '#92400E', border: 'none', borderRadius: 6, cursor: 'pointer', fontSize: 12, fontWeight: 600 }}>
              <RotateCcw size={13} /> Reenviar
            </button>
          )}
          {req.status === 'enviada' && (
            <button onClick={() => changeStatus('en_revision')}
              style={{ display: 'flex', alignItems: 'center', gap: 5, padding: '6px 12px', background: '#EDE9FE', color: '#5B21B6', border: 'none', borderRadius: 6, cursor: 'pointer', fontSize: 12, fontWeight: 600 }}>
              <Clock size={13} /> Marcar en revisión
            </button>
          )}
        </div>

        {/* Files */}
        <div style={{ marginBottom: 20 }}>
          <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 10 }}>
            <h4 style={{ margin: 0, fontSize: 13, fontWeight: 600, color: '#374151' }}>
              <Paperclip size={13} style={{ marginRight: 5 }} />Archivos ({req.archivos?.length || 0})
            </h4>
            <button
              onClick={() => fileRef.current?.click()}
              style={{ display: 'flex', alignItems: 'center', gap: 4, padding: '4px 10px', background: '#1B2A4A', color: '#fff', border: 'none', borderRadius: 5, cursor: 'pointer', fontSize: 11 }}>
              <Upload size={11} /> {uploading ? 'Subiendo...' : 'Subir'}
            </button>
            <input ref={fileRef} type="file" multiple style={{ display: 'none' }}
              onChange={e => handleFiles(Array.from(e.target.files))} />
          </div>

          {/* Drop zone */}
          <div
            onDragOver={e => { e.preventDefault(); setDragging(true); }}
            onDragLeave={() => setDragging(false)}
            onDrop={e => { e.preventDefault(); setDragging(false); handleFiles(Array.from(e.dataTransfer.files)); }}
            style={{
              border: `2px dashed ${dragging ? '#C9A84C' : '#E2E8F0'}`,
              borderRadius: 8, padding: '12px 16px', marginBottom: 10,
              background: dragging ? '#FFFBEB' : '#F8FAFC', transition: 'all .15s',
              minHeight: 60, display: 'flex', alignItems: 'center', justifyContent: 'center',
            }}>
            <span style={{ fontSize: 12, color: '#94A3B8' }}>Arrastra archivos aquí (PDF, Excel, Word, imágenes)</span>
          </div>

          {(req.archivos || []).map((f, i) => (
            <div key={i} style={{
              display: 'flex', justifyContent: 'space-between', alignItems: 'center',
              padding: '8px 12px', background: '#F8FAFC', borderRadius: 6, marginBottom: 4,
            }}>
              <div>
                <div style={{ fontSize: 12, fontWeight: 600, color: '#374151' }}>{f.nombre}</div>
                <div style={{ fontSize: 10, color: '#94A3B8' }}>
                  {(f.tamaño / 1024).toFixed(1)} KB · {f.subido_at?.slice(0, 10)}
                </div>
              </div>
              <div style={{ display: 'flex', gap: 6 }}>
                <button onClick={() => downloadFile(f.key_r2, f.nombre)}
                  style={{ padding: '4px 8px', background: '#EFF6FF', color: '#1D4ED8', border: 'none', borderRadius: 5, cursor: 'pointer', fontSize: 11, display: 'flex', alignItems: 'center', gap: 3 }}>
                  <Download size={11} />
                </button>
                <button onClick={() => deleteFile(f.key_r2)}
                  style={{ padding: '4px 8px', background: '#FEE2E2', color: '#991B1B', border: 'none', borderRadius: 5, cursor: 'pointer', fontSize: 11 }}>
                  <Trash2 size={11} />
                </button>
              </div>
            </div>
          ))}
        </div>

        {/* Comments */}
        <div>
          <h4 style={{ margin: '0 0 10px', fontSize: 13, fontWeight: 600, color: '#374151' }}>
            <MessageSquare size={13} style={{ marginRight: 5 }} />Comentarios ({req.comentarios?.length || 0})
          </h4>
          {(req.comentarios || []).map((c, i) => (
            <div key={i} style={{
              padding: '10px 12px', borderRadius: 8, marginBottom: 8,
              background: c.tipo === 'externo' ? '#EFF6FF' : '#F8FAFC',
              borderLeft: `3px solid ${c.tipo === 'externo' ? '#3B82F6' : '#E2E8F0'}`,
            }}>
              <div style={{ display: 'flex', justifyContent: 'space-between', marginBottom: 4 }}>
                <span style={{ fontSize: 11, fontWeight: 600, color: '#374151' }}>
                  {c.autor_nombre || c.autor}
                  {c.tipo === 'externo' && <span style={{ marginLeft: 4, color: '#3B82F6' }}>(Externo)</span>}
                </span>
                <span style={{ fontSize: 10, color: '#94A3B8' }}>{c.fecha?.slice(0, 16).replace('T', ' ')}</span>
              </div>
              <p style={{ margin: 0, fontSize: 12, color: '#475569', lineHeight: 1.5 }}>{c.texto}</p>
            </div>
          ))}
          <div style={{ display: 'flex', gap: 8, marginTop: 12 }}>
            <input
              value={comment} onChange={e => setComment(e.target.value)}
              onKeyDown={e => e.key === 'Enter' && !e.shiftKey && sendComment()}
              placeholder="Agregar comentario interno..."
              style={{ flex: 1, padding: '7px 12px', border: '1px solid #D1D5DB', borderRadius: 6, fontSize: 12 }}
            />
            <button onClick={sendComment}
              style={{ padding: '7px 12px', background: '#1B2A4A', color: '#fff', border: 'none', borderRadius: 6, cursor: 'pointer' }}>
              <Send size={14} />
            </button>
          </div>
        </div>
      </div>

      {showReject && <RejectModal onClose={() => setShowReject(false)} onConfirm={(m) => changeStatus('rechazada', m)} />}
    </div>
  );
}

// ─── main component ───────────────────────────────────────────────────────────

export default function AuditEngagement() {
  const { engagementId } = useParams();
  const navigate = useNavigate();
  const [engagement, setEngagement] = useState(null);
  const [requests, setRequests] = useState([]);
  const [activeTab, setActiveTab] = useState('Todas');
  const [selectedReq, setSelectedReq] = useState(null);
  const [activeCategory, setActiveCategory] = useState(null);
  const [loading, setLoading] = useState(true);
  const [showNewReq, setShowNewReq] = useState(false);
  const [newReq, setNewReq] = useState({ nombre: '', descripcion: '', categoria: 'General', prioridad: 'media', fecha_limite: '', asignado_a: '' });

  const load = useCallback(async () => {
    try {
      const [engRes, reqRes] = await Promise.all([
        api.get(`/audit/engagements/${engagementId}`),
        api.get(`/audit/engagements/${engagementId}/requests`),
      ]);
      setEngagement(engRes.data);
      setRequests(Array.isArray(reqRes.data) ? reqRes.data : []);
      if (selectedReq) {
        const updated = reqRes.data.find(r => r.id === selectedReq.id);
        if (updated) setSelectedReq(updated);
      }
    } catch {
      navigate('/audit');
    } finally {
      setLoading(false);
    }
  }, [engagementId, navigate, selectedReq?.id]);

  useEffect(() => { load(); }, [engagementId]);

  const createRequest = async (e) => {
    e.preventDefault();
    await api.post(`/audit/engagements/${engagementId}/requests`, newReq);
    setShowNewReq(false);
    setNewReq({ nombre: '', descripcion: '', categoria: 'General', prioridad: 'media', fecha_limite: '', asignado_a: '' });
    load();
  };

  if (loading) return <div style={{ padding: 40, textAlign: 'center', color: '#94A3B8' }}>Cargando...</div>;
  if (!engagement) return null;

  const categorias = engagement.categorias || [];
  const filteredByCategory = activeCategory ? requests.filter(r => r.categoria === activeCategory) : requests;
  const filteredByTab = activeTab === 'Todas'
    ? filteredByCategory
    : filteredByCategory.filter(r => r.status === TAB_STATUS[activeTab]);

  const countByStatus = (reqs) => reqs.reduce((acc, r) => { acc[r.status] = (acc[r.status] || 0) + 1; return acc; }, {});
  const globalCounts = countByStatus(requests);

  return (
    <div style={{ display: 'flex', flexDirection: 'column', height: 'calc(100vh - 60px)', overflow: 'hidden' }}>
      {/* Top bar */}
      <div style={{ padding: '16px 24px', borderBottom: '1px solid #E2E8F0', background: '#fff', flexShrink: 0 }}>
        <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 12 }}>
          <div style={{ display: 'flex', alignItems: 'center', gap: 12 }}>
            <button onClick={() => navigate('/audit')}
              style={{ display: 'flex', alignItems: 'center', gap: 5, background: 'none', border: 'none', cursor: 'pointer', color: '#64748B', fontSize: 13 }}>
              <ArrowLeft size={15} /> Expedientes
            </button>
            <span style={{ color: '#E2E8F0' }}>|</span>
            <h2 style={{ margin: 0, fontSize: 16, fontWeight: 700, color: '#1B2A4A' }}>{engagement.nombre}</h2>
            <span style={{ fontSize: 12, color: '#64748B' }}>{engagement.año} · {engagement.tipo}</span>
          </div>
          <button onClick={() => setShowNewReq(true)}
            style={{ display: 'flex', alignItems: 'center', gap: 5, padding: '7px 14px', background: '#1B2A4A', color: '#fff', border: 'none', borderRadius: 7, cursor: 'pointer', fontSize: 12, fontWeight: 600 }}>
            <Plus size={13} /> Nueva solicitud
          </button>
        </div>
        <CategoryProgress categorias={categorias} requests={requests} />
      </div>

      <div style={{ display: 'flex', flex: 1, overflow: 'hidden' }}>
        {/* Sidebar — categories */}
        <div style={{ width: 200, borderRight: '1px solid #E2E8F0', background: '#F8FAFC', overflow: 'auto', flexShrink: 0, padding: '12px 0' }}>
          <div
            onClick={() => setActiveCategory(null)}
            style={{ padding: '8px 16px', cursor: 'pointer', fontSize: 13, fontWeight: activeCategory === null ? 700 : 400, color: activeCategory === null ? '#1B2A4A' : '#64748B', background: activeCategory === null ? '#EFF6FF' : 'transparent' }}>
            Todas las categorías
            <span style={{ marginLeft: 6, fontSize: 11, color: '#94A3B8' }}>{requests.length}</span>
          </div>
          {categorias.map(cat => {
            const cnt = requests.filter(r => r.categoria === cat).length;
            const active = activeCategory === cat;
            return (
              <div key={cat} onClick={() => setActiveCategory(active ? null : cat)}
                style={{ padding: '7px 16px', cursor: 'pointer', fontSize: 12, fontWeight: active ? 700 : 400, color: active ? '#1B2A4A' : '#64748B', background: active ? '#EFF6FF' : 'transparent' }}>
                {cat}
                {cnt > 0 && <span style={{ marginLeft: 6, fontSize: 10, color: '#94A3B8' }}>{cnt}</span>}
              </div>
            );
          })}
        </div>

        {/* Main area */}
        <div style={{ flex: 1, display: 'flex', flexDirection: 'column', overflow: 'hidden' }}>
          {/* Tabs */}
          <div style={{ borderBottom: '1px solid #E2E8F0', padding: '0 20px', display: 'flex', gap: 0, background: '#fff', flexShrink: 0 }}>
            {ALL_TABS.map(tab => {
              const status = TAB_STATUS[tab];
              const cnt = status ? (globalCounts[status] || 0) : requests.length;
              const active = activeTab === tab;
              return (
                <button key={tab} onClick={() => setActiveTab(tab)} style={{
                  padding: '10px 14px', border: 'none', background: 'none', cursor: 'pointer',
                  fontSize: 12, fontWeight: active ? 700 : 400,
                  color: active ? '#1B2A4A' : '#64748B',
                  borderBottom: active ? '2px solid #C9A84C' : '2px solid transparent',
                }}>
                  {tab} {cnt > 0 && <span style={{ marginLeft: 3, fontSize: 10, color: '#94A3B8' }}>({cnt})</span>}
                </button>
              );
            })}
          </div>

          {/* Table + Detail split */}
          <div style={{ flex: 1, display: 'flex', overflow: 'hidden' }}>
            {/* Request table */}
            <div style={{ flex: selectedReq ? '0 0 55%' : '1 1 100%', overflow: 'auto', transition: 'flex .2s' }}>
              <table style={{ width: '100%', borderCollapse: 'collapse', fontSize: 12 }}>
                <thead>
                  <tr style={{ background: '#F8FAFC', borderBottom: '1px solid #E2E8F0' }}>
                    {['Prioridad', '#', 'Nombre', 'Categoría', 'Responsable', 'Vencimiento', 'Archivos', 'Status'].map(h => (
                      <th key={h} style={{ padding: '8px 12px', textAlign: 'left', fontWeight: 600, color: '#6B7280', fontSize: 11, whiteSpace: 'nowrap' }}>{h}</th>
                    ))}
                  </tr>
                </thead>
                <tbody>
                  {filteredByTab.length === 0 ? (
                    <tr><td colSpan={8} style={{ padding: '32px 16px', textAlign: 'center', color: '#94A3B8' }}>Sin solicitudes en esta vista</td></tr>
                  ) : filteredByTab.map((req, i) => {
                    const isSelected = selectedReq?.id === req.id;
                    return (
                      <tr key={req.id} onClick={() => setSelectedReq(isSelected ? null : req)}
                        style={{ borderBottom: '1px solid #F1F5F9', cursor: 'pointer', background: isSelected ? '#EFF6FF' : 'transparent' }}
                        onMouseEnter={e => !isSelected && (e.currentTarget.style.background = '#F8FAFC')}
                        onMouseLeave={e => !isSelected && (e.currentTarget.style.background = 'transparent')}>
                        <td style={{ padding: '8px 12px' }}>
                          <span style={{ width: 8, height: 8, borderRadius: '50%', background: PRIORIDAD_CONFIG[req.prioridad]?.color || '#94A3B8', display: 'inline-block' }} />
                        </td>
                        <td style={{ padding: '8px 12px', color: '#94A3B8' }}>{i + 1}</td>
                        <td style={{ padding: '8px 12px', fontWeight: 500, color: '#1B2A4A', maxWidth: 200, overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}>{req.nombre}</td>
                        <td style={{ padding: '8px 12px', color: '#64748B' }}>{req.categoria}</td>
                        <td style={{ padding: '8px 12px', color: '#64748B' }}>{req.asignado_a || '—'}</td>
                        <td style={{ padding: '8px 12px', color: req.fecha_limite ? '#64748B' : '#CBD5E1' }}>{req.fecha_limite || '—'}</td>
                        <td style={{ padding: '8px 12px' }}>
                          {req.archivos?.length > 0
                            ? <span style={{ display: 'flex', alignItems: 'center', gap: 3, color: '#3B82F6' }}><Paperclip size={11} />{req.archivos.length}</span>
                            : <span style={{ color: '#CBD5E1' }}>—</span>}
                        </td>
                        <td style={{ padding: '8px 12px' }}><StatusBadge status={req.status} /></td>
                      </tr>
                    );
                  })}
                </tbody>
              </table>
            </div>

            {/* Detail panel */}
            {selectedReq && (
              <div style={{ flex: '0 0 45%', borderLeft: '1px solid #E2E8F0', display: 'flex', flexDirection: 'column', overflow: 'hidden', background: '#fff' }}>
                <div style={{ display: 'flex', justifyContent: 'flex-end', padding: '8px 12px', borderBottom: '1px solid #F1F5F9' }}>
                  <button onClick={() => setSelectedReq(null)}
                    style={{ background: 'none', border: 'none', cursor: 'pointer', color: '#94A3B8' }}>
                    <X size={16} />
                  </button>
                </div>
                <RequestDetail req={selectedReq} engagementId={engagementId} onUpdate={load} />
              </div>
            )}
          </div>
        </div>
      </div>

      {/* New request modal */}
      {showNewReq && (
        <div style={{ position: 'fixed', inset: 0, background: 'rgba(0,0,0,.45)', display: 'flex', alignItems: 'center', justifyContent: 'center', zIndex: 1000 }}>
          <div style={{ background: '#fff', borderRadius: 12, padding: 28, width: 480, maxWidth: '95vw' }}>
            <h3 style={{ margin: '0 0 20px', fontSize: 16, color: '#1B2A4A' }}>Nueva solicitud</h3>
            <form onSubmit={createRequest}>
              {[
                { label: 'Nombre', key: 'nombre', type: 'text', required: true },
                { label: 'Descripción', key: 'descripcion', type: 'text' },
                { label: 'Responsable', key: 'asignado_a', type: 'text' },
                { label: 'Fecha límite', key: 'fecha_limite', type: 'date' },
              ].map(({ label, key, type, required }) => (
                <div key={key} style={{ marginBottom: 12 }}>
                  <label style={{ display: 'block', fontSize: 12, fontWeight: 600, color: '#374151', marginBottom: 3 }}>{label}</label>
                  <input type={type} required={required} value={newReq[key]}
                    onChange={e => setNewReq(f => ({ ...f, [key]: e.target.value }))}
                    style={{ width: '100%', padding: '7px 11px', border: '1px solid #D1D5DB', borderRadius: 6, fontSize: 13, boxSizing: 'border-box' }} />
                </div>
              ))}
              <div style={{ display: 'flex', gap: 12, marginBottom: 12 }}>
                <div style={{ flex: 1 }}>
                  <label style={{ display: 'block', fontSize: 12, fontWeight: 600, color: '#374151', marginBottom: 3 }}>Categoría</label>
                  <select value={newReq.categoria} onChange={e => setNewReq(f => ({ ...f, categoria: e.target.value }))}
                    style={{ width: '100%', padding: '7px 11px', border: '1px solid #D1D5DB', borderRadius: 6, fontSize: 13 }}>
                    {(engagement.categorias || []).map(c => <option key={c} value={c}>{c}</option>)}
                  </select>
                </div>
                <div style={{ flex: 1 }}>
                  <label style={{ display: 'block', fontSize: 12, fontWeight: 600, color: '#374151', marginBottom: 3 }}>Prioridad</label>
                  <select value={newReq.prioridad} onChange={e => setNewReq(f => ({ ...f, prioridad: e.target.value }))}
                    style={{ width: '100%', padding: '7px 11px', border: '1px solid #D1D5DB', borderRadius: 6, fontSize: 13 }}>
                    <option value="alta">Alta</option>
                    <option value="media">Media</option>
                    <option value="baja">Baja</option>
                  </select>
                </div>
              </div>
              <div style={{ display: 'flex', gap: 10, justifyContent: 'flex-end', marginTop: 16 }}>
                <button type="button" onClick={() => setShowNewReq(false)}
                  style={{ padding: '7px 16px', border: '1px solid #D1D5DB', borderRadius: 6, background: '#fff', cursor: 'pointer', fontSize: 13 }}>
                  Cancelar
                </button>
                <button type="submit"
                  style={{ padding: '7px 16px', background: '#1B2A4A', color: '#fff', border: 'none', borderRadius: 6, cursor: 'pointer', fontSize: 13 }}>
                  Crear solicitud
                </button>
              </div>
            </form>
          </div>
        </div>
      )}
    </div>
  );
}
