import { useState, useEffect, useCallback } from 'react';
import { useNavigate } from 'react-router-dom';
import {
  FolderOpen, Plus, Calendar, Tag, CheckCircle2,
  Clock, AlertCircle, Archive, ChevronRight,
} from 'lucide-react';
import api from '../api/axios';

const STATUS_COLOR = {
  activo:    { bg: '#EEF2FF', text: '#3730A3', label: 'Activo' },
  cerrado:   { bg: '#F0FDF4', text: '#166534', label: 'Cerrado' },
  archivado: { bg: '#F8FAFC', text: '#64748B', label: 'Archivado' },
};

const PRIORIDAD_COLOR = {
  alta:  '#EF4444',
  media: '#F59E0B',
  baja:  '#10B981',
};

function ProgressBar({ counts = {} }) {
  const total = Object.values(counts).reduce((a, b) => a + b, 0);
  if (!total) return <div style={{ height: 6, background: '#E2E8F0', borderRadius: 3 }} />;
  const pct = (k) => Math.round(((counts[k] || 0) / total) * 100);
  const segments = [
    { key: 'aceptada',    color: '#10B981' },
    { key: 'en_revision', color: '#3B82F6' },
    { key: 'enviada',     color: '#60A5FA' },
    { key: 'pendiente',   color: '#F59E0B' },
    { key: 'rechazada',   color: '#EF4444' },
  ];
  return (
    <div style={{ display: 'flex', height: 6, borderRadius: 3, overflow: 'hidden', gap: 1 }}>
      {segments.map(({ key, color }) =>
        counts[key] ? (
          <div key={key} title={`${key}: ${counts[key]}`}
            style={{ width: `${pct(key)}%`, background: color, minWidth: 3 }} />
        ) : null
      )}
    </div>
  );
}

function EngagementCard({ eng, onClick }) {
  const sc = STATUS_COLOR[eng.status] || STATUS_COLOR.activo;
  const total = Object.values(eng.request_counts || {}).reduce((a, b) => a + b, 0);

  return (
    <div onClick={onClick} data-testid="engagement-card" style={{
      background: '#fff', border: '1px solid #E2E8F0', borderRadius: 10,
      padding: '20px 24px', cursor: 'pointer', transition: 'box-shadow .15s',
    }}
      onMouseEnter={e => e.currentTarget.style.boxShadow = '0 4px 16px rgba(0,0,0,.08)'}
      onMouseLeave={e => e.currentTarget.style.boxShadow = 'none'}
    >
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start', marginBottom: 12 }}>
        <div style={{ display: 'flex', alignItems: 'center', gap: 10 }}>
          <FolderOpen size={20} color="#C9A84C" />
          <span style={{ fontWeight: 600, fontSize: 15, color: '#1B2A4A' }}>{eng.nombre}</span>
        </div>
        <span style={{
          fontSize: 11, fontWeight: 600, padding: '2px 8px', borderRadius: 4,
          background: sc.bg, color: sc.text,
        }}>{sc.label}</span>
      </div>

      {eng.descripcion && (
        <p style={{ fontSize: 13, color: '#64748B', margin: '0 0 12px', lineHeight: 1.5 }}>
          {eng.descripcion}
        </p>
      )}

      <div style={{ display: 'flex', gap: 16, marginBottom: 14, flexWrap: 'wrap' }}>
        <span style={{ display: 'flex', alignItems: 'center', gap: 4, fontSize: 12, color: '#64748B' }}>
          <Calendar size={12} /> {eng.año}
        </span>
        <span style={{ display: 'flex', alignItems: 'center', gap: 4, fontSize: 12, color: '#64748B' }}>
          <Tag size={12} /> {eng.tipo}
        </span>
        <span style={{ display: 'flex', alignItems: 'center', gap: 4, fontSize: 12, color: '#64748B' }}>
          <CheckCircle2 size={12} color="#10B981" /> {eng.progreso_pct}% completado
        </span>
        <span style={{ display: 'flex', alignItems: 'center', gap: 4, fontSize: 12, color: '#64748B' }}>
          <Clock size={12} /> {total} solicitudes
        </span>
      </div>

      <ProgressBar counts={eng.request_counts} />

      <div style={{ display: 'flex', justifyContent: 'flex-end', marginTop: 12 }}>
        <span style={{ fontSize: 12, color: '#C9A84C', display: 'flex', alignItems: 'center', gap: 4 }}>
          Ver expediente <ChevronRight size={14} />
        </span>
      </div>
    </div>
  );
}

function NewEngagementModal({ onClose, onCreated }) {
  const [form, setForm] = useState({
    nombre: '', descripcion: '', año: new Date().getFullYear(), tipo: 'Auditoría externa',
  });
  const [saving, setSaving] = useState(false);

  const submit = async (e) => {
    e.preventDefault();
    setSaving(true);
    try {
      const { data } = await api.post('/audit/engagements', form);
      onCreated(data);
    } catch {
      alert('Error al crear expediente');
    } finally {
      setSaving(false);
    }
  };

  return (
    <div style={{
      position: 'fixed', inset: 0, background: 'rgba(0,0,0,.45)',
      display: 'flex', alignItems: 'center', justifyContent: 'center', zIndex: 1000,
    }}>
      <div style={{
        background: '#fff', borderRadius: 12, padding: 32, width: 480, maxWidth: '95vw',
      }}>
        <h3 style={{ margin: '0 0 20px', fontSize: 18, color: '#1B2A4A' }}>Nuevo expediente</h3>
        <form onSubmit={submit}>
          {[
            { label: 'Nombre', key: 'nombre', type: 'text', required: true },
            { label: 'Descripción', key: 'descripcion', type: 'text' },
            { label: 'Año', key: 'año', type: 'number' },
            { label: 'Tipo', key: 'tipo', type: 'text' },
          ].map(({ label, key, type, required }) => (
            <div key={key} style={{ marginBottom: 14 }}>
              <label style={{ display: 'block', fontSize: 12, fontWeight: 600, color: '#374151', marginBottom: 4 }}>
                {label}
              </label>
              <input
                type={type} required={required}
                value={form[key]} onChange={e => setForm(f => ({ ...f, [key]: e.target.value }))}
                style={{
                  width: '100%', padding: '8px 12px', border: '1px solid #D1D5DB',
                  borderRadius: 6, fontSize: 13, boxSizing: 'border-box',
                }}
              />
            </div>
          ))}
          <div style={{ display: 'flex', gap: 10, justifyContent: 'flex-end', marginTop: 20 }}>
            <button type="button" onClick={onClose}
              style={{ padding: '8px 18px', border: '1px solid #D1D5DB', borderRadius: 6, background: '#fff', cursor: 'pointer', fontSize: 13 }}>
              Cancelar
            </button>
            <button type="submit" disabled={saving}
              style={{ padding: '8px 18px', background: '#1B2A4A', color: '#fff', border: 'none', borderRadius: 6, cursor: 'pointer', fontSize: 13 }}>
              {saving ? 'Creando...' : 'Crear expediente'}
            </button>
          </div>
        </form>
      </div>
    </div>
  );
}

export default function AuditPortal() {
  const navigate = useNavigate();
  const [engagements, setEngagements] = useState([]);
  const [loading, setLoading] = useState(true);
  const [showNew, setShowNew] = useState(false);

  const load = useCallback(async () => {
    setLoading(true);
    try {
      const { data } = await api.get('/audit/engagements');
      setEngagements(Array.isArray(data) ? data : []);
    } catch {
      setEngagements([]);
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => { load(); }, [load]);

  return (
    <div style={{ padding: '32px 36px', maxWidth: 1100, margin: '0 auto' }}>
      {/* Header */}
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 28 }}>
        <div>
          <h1 style={{ margin: 0, fontSize: 22, fontWeight: 700, color: '#1B2A4A' }}>
            Portal de Auditoría y Fiscal
          </h1>
          <p style={{ margin: '4px 0 0', color: '#64748B', fontSize: 13 }}>
            Gestiona expedientes de auditoría y solicitudes de documentos
          </p>
        </div>
        <button
          data-testid="new-engagement-btn"
          onClick={() => setShowNew(true)}
          style={{
            display: 'flex', alignItems: 'center', gap: 6,
            padding: '9px 18px', background: '#1B2A4A', color: '#fff',
            border: 'none', borderRadius: 8, cursor: 'pointer', fontSize: 13, fontWeight: 600,
          }}
        >
          <Plus size={15} /> Nuevo expediente
        </button>
      </div>

      {/* Stats row */}
      {!loading && engagements.length > 0 && (
        <div style={{ display: 'flex', gap: 16, marginBottom: 28, flexWrap: 'wrap' }}>
          {[
            { label: 'Expedientes activos', value: engagements.filter(e => e.status === 'activo').length, color: '#3B82F6' },
            { label: 'Total solicitudes', value: engagements.reduce((a, e) => a + Object.values(e.request_counts || {}).reduce((x, y) => x + y, 0), 0), color: '#8B5CF6' },
            { label: 'Completadas', value: engagements.reduce((a, e) => a + (e.request_counts?.aceptada || 0), 0), color: '#10B981' },
            { label: 'Pendientes', value: engagements.reduce((a, e) => a + (e.request_counts?.pendiente || 0), 0), color: '#F59E0B' },
          ].map(({ label, value, color }) => (
            <div key={label} style={{
              background: '#fff', border: '1px solid #E2E8F0', borderRadius: 8,
              padding: '12px 20px', flex: '1 1 120px',
            }}>
              <div style={{ fontSize: 22, fontWeight: 700, color }}>{value}</div>
              <div style={{ fontSize: 12, color: '#64748B', marginTop: 2 }}>{label}</div>
            </div>
          ))}
        </div>
      )}

      {/* Engagement list */}
      {loading ? (
        <div style={{ textAlign: 'center', padding: 60, color: '#94A3B8' }}>Cargando expedientes...</div>
      ) : engagements.length === 0 ? (
        <div style={{
          textAlign: 'center', padding: '60px 20px', background: '#F8FAFC',
          border: '2px dashed #E2E8F0', borderRadius: 12,
        }}>
          <Archive size={40} color="#CBD5E1" style={{ marginBottom: 12 }} />
          <p style={{ color: '#64748B', margin: 0 }}>No hay expedientes activos.</p>
          <p style={{ color: '#94A3B8', fontSize: 13, marginTop: 4 }}>
            Crea el primero con el botón "Nuevo expediente".
          </p>
        </div>
      ) : (
        <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fill, minmax(340px, 1fr))', gap: 16 }}>
          {engagements.map(eng => (
            <EngagementCard key={eng.id} eng={eng} onClick={() => navigate(`/audit/${eng.id}`)} />
          ))}
        </div>
      )}

      {showNew && (
        <NewEngagementModal
          onClose={() => setShowNew(false)}
          onCreated={(eng) => { setShowNew(false); navigate(`/audit/${eng.id}`); }}
        />
      )}
    </div>
  );
}
