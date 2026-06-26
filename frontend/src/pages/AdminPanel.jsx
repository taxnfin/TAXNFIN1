import { useState, useEffect, useCallback } from 'react';
import api from '../api/axios';

const NAVY    = '#1B3A6B';
const GOLD    = '#C9A84C';
const PAGE_BG = '#F8F9FA';

const PLAN_META = {
  STARTER: { bg: '#EEF3FB', color: '#1B3A6B',  label: 'Starter', price: 999  },
  GROWTH:  { bg: '#EEF8F2', color: '#1E7145',  label: 'Growth',  price: 2499 },
  PRO:     { bg: '#F1F0FF', color: '#5B21B6',  label: 'Pro',     price: 4999 },
};

const ESTADO_META = {
  activo:    { bg: '#EEF8F2', color: '#1E7145',  label: 'Activo'    },
  pausado:   { bg: '#FFF9E6', color: '#B45309',  label: 'Pausado'   },
  eliminado: { bg: '#FFF5F5', color: '#B91C1C',  label: 'Eliminado' },
};

function Badge({ style, children }) {
  return (
    <span style={{
      fontSize: '11px', fontWeight: 700, padding: '2px 8px',
      borderRadius: '4px', textTransform: 'uppercase', letterSpacing: '0.04em',
      ...style,
    }}>
      {children}
    </span>
  );
}

function StatCard({ label, value, color }) {
  return (
    <div style={{
      background: '#FFF', border: '1px solid #E2E8F0', borderRadius: '4px',
      padding: '16px 20px', flex: '1', minWidth: '160px',
      boxShadow: '0 1px 3px rgba(0,0,0,0.05)',
    }}>
      <p style={{ fontSize: '11px', color: '#64748B', textTransform: 'uppercase', letterSpacing: '0.05em', margin: 0 }}>{label}</p>
      <p style={{ fontSize: '26px', fontWeight: 800, color: color || NAVY, margin: '4px 0 0' }}>{value}</p>
    </div>
  );
}

export default function AdminPanel() {
  const [stats,       setStats]       = useState(null);
  const [despachos,   setDespachos]   = useState([]);
  const [loading,     setLoading]     = useState(true);
  const [eliminadosOpen, setEliminadosOpen] = useState(false);

  // Modales
  const [pausaModal,  setPausaModal]  = useState(null);   // { user_id, nombre }
  const [pausaMotivo, setPausaMotivo] = useState('');
  const [planModal,   setPlanModal]   = useState(null);   // { user_id, nombre, plan }
  const [planForm,    setPlanForm]    = useState({ plan: 'STARTER', fecha_vencimiento: '' });
  const [deleteModal, setDeleteModal] = useState(null);   // { user_id, nombre }
  const [deleteText,  setDeleteText]  = useState('');
  const [saving,      setSaving]      = useState(false);

  const [error, setError] = useState(null);

  const cargar = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      const [sRes, dRes] = await Promise.all([
        api.get('/admin/stats'),
        api.get('/admin/despachos'),
      ]);
      setStats(sRes.data);
      setDespachos(dRes.data.despachos || []);
    } catch (err) {
      if (err.response?.status === 403) {
        setError('Acceso restringido — Solo disponible para el administrador de plataforma (hola@taxnfin.com)');
      } else {
        setError('Error al cargar el panel de administración');
      }
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => { cargar(); }, [cargar]);

  const activos   = despachos.filter(d => d.estado === 'activo');
  const pausados  = despachos.filter(d => d.estado === 'pausado');
  const eliminados= despachos.filter(d => d.estado === 'eliminado');

  // ── Pausar ────────────────────────────────────────────────────────────────────
  async function handlePausar() {
    if (!pausaModal) return;
    setSaving(true);
    try {
      await api.put(`/admin/despachos/${pausaModal.user_id}/pausar`, { motivo: pausaMotivo });
      setPausaModal(null); setPausaMotivo('');
      cargar();
    } catch (err) {
      alert(err.response?.data?.detail || 'Error al pausar');
    } finally { setSaving(false); }
  }

  // ── Reactivar ─────────────────────────────────────────────────────────────────
  async function handleReactivar(d) {
    if (!window.confirm(`¿Reactivar el despacho de ${d.nombre}?`)) return;
    try {
      await api.put(`/admin/despachos/${d.user_id}/reactivar`);
      cargar();
    } catch (err) { alert(err.response?.data?.detail || 'Error'); }
  }

  // ── Cambiar plan ──────────────────────────────────────────────────────────────
  async function handlePlan() {
    if (!planModal) return;
    setSaving(true);
    try {
      await api.put(`/admin/despachos/${planModal.user_id}/plan`, planForm);
      setPlanModal(null);
      cargar();
    } catch (err) {
      alert(err.response?.data?.detail || 'Error al cambiar plan');
    } finally { setSaving(false); }
  }

  // ── Eliminar ──────────────────────────────────────────────────────────────────
  async function handleEliminar() {
    if (!deleteModal || deleteText !== 'DELETE') return;
    setSaving(true);
    try {
      await api.delete(`/admin/despachos/${deleteModal.user_id}`);
      setDeleteModal(null); setDeleteText('');
      cargar();
    } catch (err) {
      alert(err.response?.data?.detail || 'Error al eliminar');
    } finally { setSaving(false); }
  }

  function fmtFecha(iso) {
    if (!iso) return '—';
    return new Date(iso).toLocaleDateString('es-MX', { year: 'numeric', month: 'short', day: 'numeric' });
  }

  function DespachoRow({ d, showActions = true }) {
    const pm = PLAN_META[d.plan]  || PLAN_META.STARTER;
    const em = ESTADO_META[d.estado] || ESTADO_META.activo;
    return (
      <tr style={{ borderBottom: '1px solid #F1F5F9' }}>
        <td style={{ padding: '10px 14px' }}>
          <p style={{ fontWeight: 600, color: NAVY, margin: 0, fontSize: '13px' }}>{d.nombre}</p>
          <p style={{ color: '#64748B', margin: 0, fontSize: '12px' }}>{d.email}</p>
        </td>
        <td style={{ padding: '10px 14px' }}>
          <Badge style={{ background: pm.bg, color: pm.color }}>{pm.label}</Badge>
          {d.fecha_vencimiento_plan && (
            <p style={{ margin: '2px 0 0', fontSize: '10px', color: '#94A3B8' }}>
              Vence {fmtFecha(d.fecha_vencimiento_plan)}
            </p>
          )}
        </td>
        <td style={{ padding: '10px 14px', textAlign: 'center', color: '#475569', fontSize: '13px' }}>{d.empresas_activas}</td>
        <td style={{ padding: '10px 14px', textAlign: 'center', color: '#475569', fontSize: '13px' }}>{d.usuarios_activos}</td>
        <td style={{ padding: '10px 14px', color: '#64748B', fontSize: '12px' }}>{fmtFecha(d.fecha_registro)}</td>
        <td style={{ padding: '10px 14px' }}>
          <Badge style={{ background: em.bg, color: em.color }}>{em.label}</Badge>
        </td>
        {showActions && (
          <td style={{ padding: '10px 14px' }}>
            <div style={{ display: 'flex', gap: '6px', flexWrap: 'wrap' }}>
              {d.estado === 'activo' && (
                <>
                  <button
                    onClick={() => { setPlanModal({ user_id: d.user_id, nombre: d.nombre, plan: d.plan }); setPlanForm({ plan: d.plan || 'STARTER', fecha_vencimiento: d.fecha_vencimiento_plan || '' }); }}
                    style={{ fontSize: '11px', color: NAVY, background: '#EEF3FB', border: `1px solid ${NAVY}`, borderRadius: '4px', padding: '4px 8px', cursor: 'pointer' }}
                  >Plan</button>
                  <button
                    onClick={() => { setPausaModal({ user_id: d.user_id, nombre: d.nombre }); setPausaMotivo(''); }}
                    style={{ fontSize: '11px', color: '#B45309', background: '#FFF9E6', border: '1px solid #D97706', borderRadius: '4px', padding: '4px 8px', cursor: 'pointer' }}
                  >Pausar</button>
                  <button
                    onClick={() => { setDeleteModal({ user_id: d.user_id, nombre: d.nombre }); setDeleteText(''); }}
                    style={{ fontSize: '11px', color: '#B91C1C', background: '#FFF5F5', border: '1px solid #FCA5A5', borderRadius: '4px', padding: '4px 8px', cursor: 'pointer' }}
                  >Eliminar</button>
                </>
              )}
              {d.estado === 'pausado' && (
                <>
                  <button
                    onClick={() => handleReactivar(d)}
                    style={{ fontSize: '11px', color: '#1E7145', background: '#EEF8F2', border: '1px solid #1E7145', borderRadius: '4px', padding: '4px 8px', cursor: 'pointer' }}
                  >Reactivar</button>
                  <button
                    onClick={() => { setDeleteModal({ user_id: d.user_id, nombre: d.nombre }); setDeleteText(''); }}
                    style={{ fontSize: '11px', color: '#B91C1C', background: '#FFF5F5', border: '1px solid #FCA5A5', borderRadius: '4px', padding: '4px 8px', cursor: 'pointer' }}
                  >Eliminar</button>
                </>
              )}
            </div>
          </td>
        )}
      </tr>
    );
  }

  return (
    <div style={{ minHeight: '100vh', background: PAGE_BG, padding: '24px', fontFamily: 'system-ui, Arial, sans-serif' }}>
      <div style={{ maxWidth: '1100px', margin: '0 auto' }} className="space-y-6">

        {/* Header */}
        <div style={{ background: '#FFF', borderBottom: `3px solid #EF4444`, borderRadius: '4px 4px 0 0', padding: '20px 24px', boxShadow: '0 1px 3px rgba(0,0,0,0.07)' }}>
          <div style={{ display: 'flex', alignItems: 'center', gap: '12px' }}>
            <h1 style={{ color: NAVY, fontSize: '22px', fontWeight: 700, margin: 0 }}>⚙️ Panel de Administración TaxnFin</h1>
            <Badge style={{ background: 'rgba(239,68,68,0.1)', color: '#EF4444', fontSize: '12px' }}>ADMIN</Badge>
          </div>
          <p style={{ color: '#64748B', fontSize: '13px', margin: '4px 0 0' }}>
            Gestión de despachos y planes — Solo visible para administradores de plataforma
          </p>
        </div>

        {/* Error de acceso */}
        {error && (
          <div style={{ background: '#FFF5F5', border: '1px solid #FCA5A5', borderRadius: '8px', padding: '24px', textAlign: 'center' }}>
            <p style={{ fontSize: '32px', margin: '0 0 8px' }}>🔒</p>
            <p style={{ color: '#B91C1C', fontWeight: 700, fontSize: '16px', margin: '0 0 4px' }}>Sin acceso</p>
            <p style={{ color: '#64748B', fontSize: '13px', margin: 0 }}>{error}</p>
          </div>
        )}

        {/* Stats */}
        {stats && (
          <div style={{ display: 'flex', gap: '12px', flexWrap: 'wrap' }}>
            <StatCard label="Despachos activos"  value={stats.despachos_activos}   color="#1E7145" />
            <StatCard label="Pausados"            value={stats.despachos_pausados}  color="#B45309" />
            <StatCard label="Empresas plataforma" value={stats.empresas_activas}    color={NAVY}    />
            <StatCard label="MRR estimado"        value={`$${stats.mrr_mxn?.toLocaleString('es-MX')} MXN`} color={GOLD} />
            <StatCard label="Nuevos este mes"     value={stats.nuevos_este_mes}     color="#5B21B6" />
          </div>
        )}

        {/* Despachos activos */}
        <div style={{ background: '#FFF', border: '1px solid #E2E8F0', borderRadius: '4px', boxShadow: '0 1px 3px rgba(0,0,0,0.05)' }}>
          <div style={{ padding: '14px 20px', borderBottom: '1px solid #E2E8F0', display: 'flex', alignItems: 'center', justifyContent: 'space-between' }}>
            <h2 style={{ color: NAVY, fontSize: '14px', fontWeight: 700, margin: 0 }}>
              Despachos activos ({activos.length}) + pausados ({pausados.length})
            </h2>
            {loading && <span style={{ fontSize: '12px', color: '#94A3B8' }}>Cargando…</span>}
          </div>
          {[...activos, ...pausados].length === 0 && !loading ? (
            <p style={{ padding: '16px 20px', fontSize: '13px', color: '#94A3B8' }}>Sin despachos registrados.</p>
          ) : (
            <div style={{ overflowX: 'auto' }}>
              <table style={{ width: '100%', borderCollapse: 'collapse', fontSize: '13px' }}>
                <thead>
                  <tr style={{ background: PAGE_BG, borderBottom: '1px solid #E2E8F0' }}>
                    {['Nombre / Email', 'Plan', 'Empresas', 'Usuarios', 'Registro', 'Estado', 'Acciones'].map(h => (
                      <th key={h} style={{ padding: '10px 14px', textAlign: 'left', fontSize: '11px', fontWeight: 700, color: '#64748B', textTransform: 'uppercase', letterSpacing: '0.05em' }}>{h}</th>
                    ))}
                  </tr>
                </thead>
                <tbody>
                  {[...activos, ...pausados].map(d => <DespachoRow key={d.user_id} d={d} />)}
                </tbody>
              </table>
            </div>
          )}
        </div>

        {/* Despachos eliminados */}
        {eliminados.length > 0 && (
          <div style={{ background: '#FFF', border: '1px solid #E2E8F0', borderRadius: '4px', boxShadow: '0 1px 3px rgba(0,0,0,0.05)' }}>
            <button
              onClick={() => setEliminadosOpen(o => !o)}
              style={{ width: '100%', display: 'flex', justifyContent: 'space-between', alignItems: 'center', padding: '12px 20px', background: 'none', border: 'none', fontSize: '13px', color: '#B91C1C', cursor: 'pointer' }}
            >
              <span>Despachos eliminados ({eliminados.length})</span>
              <span>{eliminadosOpen ? '▲' : '▼'}</span>
            </button>
            {eliminadosOpen && (
              <div style={{ borderTop: '1px solid #E2E8F0', overflowX: 'auto' }}>
                <table style={{ width: '100%', borderCollapse: 'collapse', fontSize: '13px' }}>
                  <thead>
                    <tr style={{ background: PAGE_BG, borderBottom: '1px solid #E2E8F0' }}>
                      {['Nombre / Email', 'Plan', 'Empresas', 'Usuarios', 'Registro', 'Estado', 'Reactivar'].map(h => (
                        <th key={h} style={{ padding: '10px 14px', textAlign: 'left', fontSize: '11px', fontWeight: 700, color: '#64748B', textTransform: 'uppercase', letterSpacing: '0.05em' }}>{h}</th>
                      ))}
                    </tr>
                  </thead>
                  <tbody>
                    {eliminados.map(d => (
                      <tr key={d.user_id} style={{ borderBottom: '1px solid #F1F5F9' }}>
                        <td style={{ padding: '10px 14px' }}>
                          <p style={{ fontWeight: 600, color: '#94A3B8', margin: 0, fontSize: '13px' }}>{d.nombre}</p>
                          <p style={{ color: '#CBD5E1', margin: 0, fontSize: '12px' }}>{d.email}</p>
                        </td>
                        <td style={{ padding: '10px 14px' }}>
                          <Badge style={{ background: '#F1F5F9', color: '#94A3B8' }}>{d.plan || 'STARTER'}</Badge>
                        </td>
                        <td style={{ padding: '10px 14px', textAlign: 'center', color: '#94A3B8', fontSize: '13px' }}>{d.empresas_activas}</td>
                        <td style={{ padding: '10px 14px', textAlign: 'center', color: '#94A3B8', fontSize: '13px' }}>{d.usuarios_activos}</td>
                        <td style={{ padding: '10px 14px', color: '#94A3B8', fontSize: '12px' }}>{fmtFecha(d.fecha_registro)}</td>
                        <td style={{ padding: '10px 14px' }}>
                          <Badge style={{ background: '#FFF5F5', color: '#B91C1C' }}>Eliminado</Badge>
                        </td>
                        <td style={{ padding: '10px 14px' }}>
                          <button
                            onClick={() => handleReactivar(d)}
                            style={{ fontSize: '11px', color: '#1E7145', background: '#EEF8F2', border: '1px solid #1E7145', borderRadius: '4px', padding: '4px 10px', cursor: 'pointer' }}
                          >
                            Reactivar
                          </button>
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            )}
          </div>
        )}
      </div>

      {/* ── Modal: Pausar ──────────────────────────────────────────────────── */}
      {pausaModal && (
        <div style={{ position: 'fixed', inset: 0, background: 'rgba(0,0,0,0.4)', display: 'flex', alignItems: 'center', justifyContent: 'center', zIndex: 50 }}>
          <div style={{ background: '#FFF', borderRadius: '8px', padding: '24px', width: '440px', maxWidth: '90vw', boxShadow: '0 8px 32px rgba(0,0,0,0.15)' }}>
            <h3 style={{ color: '#B45309', fontWeight: 700, marginTop: 0 }}>Pausar despacho: {pausaModal.nombre}</h3>
            <p style={{ fontSize: '13px', color: '#475569', marginBottom: '12px' }}>
              Esto desactivará el acceso del CFO y todos sus usuarios. Puedes reactivarlo en cualquier momento.
            </p>
            <label style={{ fontSize: '12px', color: '#64748B', display: 'block', marginBottom: '4px' }}>Motivo (opcional)</label>
            <textarea
              value={pausaMotivo}
              onChange={e => setPausaMotivo(e.target.value)}
              placeholder="Ej. Factura vencida, período de prueba finalizado…"
              rows={3}
              style={{ width: '100%', border: '1px solid #CBD5E1', borderRadius: '4px', padding: '8px 12px', fontSize: '13px', resize: 'vertical', boxSizing: 'border-box' }}
            />
            <div style={{ display: 'flex', gap: '8px', justifyContent: 'flex-end', marginTop: '16px' }}>
              <button onClick={() => setPausaModal(null)} style={{ background: '#F1F5F9', border: 'none', borderRadius: '4px', padding: '8px 16px', fontSize: '13px', cursor: 'pointer', color: '#475569' }}>Cancelar</button>
              <button
                onClick={handlePausar}
                disabled={saving}
                style={{ background: saving ? '#94A3B8' : '#B45309', color: '#FFF', border: 'none', borderRadius: '4px', padding: '8px 20px', fontSize: '13px', fontWeight: 600, cursor: saving ? 'not-allowed' : 'pointer' }}
              >
                {saving ? 'Pausando…' : 'Confirmar pausa'}
              </button>
            </div>
          </div>
        </div>
      )}

      {/* ── Modal: Cambiar plan ────────────────────────────────────────────── */}
      {planModal && (
        <div style={{ position: 'fixed', inset: 0, background: 'rgba(0,0,0,0.4)', display: 'flex', alignItems: 'center', justifyContent: 'center', zIndex: 50 }}>
          <div style={{ background: '#FFF', borderRadius: '8px', padding: '24px', width: '400px', maxWidth: '90vw', boxShadow: '0 8px 32px rgba(0,0,0,0.15)' }}>
            <h3 style={{ color: NAVY, fontWeight: 700, marginTop: 0 }}>Cambiar plan: {planModal.nombre}</h3>
            <div style={{ marginBottom: '12px' }}>
              <label style={{ fontSize: '12px', color: '#64748B', display: 'block', marginBottom: '4px' }}>Plan</label>
              <select
                value={planForm.plan}
                onChange={e => setPlanForm(f => ({ ...f, plan: e.target.value }))}
                style={{ width: '100%', border: '1px solid #CBD5E1', borderRadius: '4px', padding: '8px 12px', fontSize: '13px', color: NAVY, background: '#FFF' }}
              >
                <option value="STARTER">Starter — $999 MXN/mes</option>
                <option value="GROWTH">Growth — $2,499 MXN/mes</option>
                <option value="PRO">Pro — $4,999 MXN/mes</option>
              </select>
            </div>
            <div style={{ marginBottom: '16px' }}>
              <label style={{ fontSize: '12px', color: '#64748B', display: 'block', marginBottom: '4px' }}>Fecha de vencimiento (opcional)</label>
              <input
                type="date"
                value={planForm.fecha_vencimiento}
                onChange={e => setPlanForm(f => ({ ...f, fecha_vencimiento: e.target.value }))}
                style={{ width: '100%', border: '1px solid #CBD5E1', borderRadius: '4px', padding: '8px 12px', fontSize: '13px', color: NAVY, boxSizing: 'border-box' }}
              />
            </div>
            <div style={{ display: 'flex', gap: '8px', justifyContent: 'flex-end' }}>
              <button onClick={() => setPlanModal(null)} style={{ background: '#F1F5F9', border: 'none', borderRadius: '4px', padding: '8px 16px', fontSize: '13px', cursor: 'pointer', color: '#475569' }}>Cancelar</button>
              <button
                onClick={handlePlan}
                disabled={saving}
                style={{ background: saving ? '#94A3B8' : NAVY, color: '#FFF', border: 'none', borderRadius: '4px', padding: '8px 20px', fontSize: '13px', fontWeight: 600, cursor: saving ? 'not-allowed' : 'pointer' }}
              >
                {saving ? 'Guardando…' : 'Guardar plan'}
              </button>
            </div>
          </div>
        </div>
      )}

      {/* ── Modal: Eliminar ────────────────────────────────────────────────── */}
      {deleteModal && (
        <div style={{ position: 'fixed', inset: 0, background: 'rgba(0,0,0,0.4)', display: 'flex', alignItems: 'center', justifyContent: 'center', zIndex: 50 }}>
          <div style={{ background: '#FFF', borderRadius: '8px', padding: '24px', width: '440px', maxWidth: '90vw', boxShadow: '0 8px 32px rgba(0,0,0,0.15)' }}>
            <h3 style={{ color: '#B91C1C', fontWeight: 700, marginTop: 0 }}>Eliminar despacho: {deleteModal.nombre}</h3>
            <p style={{ fontSize: '13px', color: '#475569', marginBottom: '8px' }}>
              Esto desactivará el acceso del CFO y todos sus usuarios. <strong>Los datos financieros se conservan.</strong>
            </p>
            <p style={{ fontSize: '13px', color: '#B91C1C', marginBottom: '12px' }}>
              Escribe <strong>DELETE</strong> para confirmar:
            </p>
            <input
              type="text"
              value={deleteText}
              onChange={e => setDeleteText(e.target.value)}
              placeholder="DELETE"
              style={{ width: '100%', border: `2px solid ${deleteText === 'DELETE' ? '#EF4444' : '#CBD5E1'}`, borderRadius: '4px', padding: '8px 12px', fontSize: '14px', fontFamily: 'monospace', letterSpacing: '0.1em', boxSizing: 'border-box' }}
            />
            <div style={{ display: 'flex', gap: '8px', justifyContent: 'flex-end', marginTop: '16px' }}>
              <button onClick={() => { setDeleteModal(null); setDeleteText(''); }} style={{ background: '#F1F5F9', border: 'none', borderRadius: '4px', padding: '8px 16px', fontSize: '13px', cursor: 'pointer', color: '#475569' }}>Cancelar</button>
              <button
                onClick={handleEliminar}
                disabled={saving || deleteText !== 'DELETE'}
                style={{ background: (saving || deleteText !== 'DELETE') ? '#CBD5E1' : '#B91C1C', color: '#FFF', border: 'none', borderRadius: '4px', padding: '8px 20px', fontSize: '13px', fontWeight: 600, cursor: (saving || deleteText !== 'DELETE') ? 'not-allowed' : 'pointer' }}
              >
                {saving ? 'Eliminando…' : 'Eliminar despacho'}
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
