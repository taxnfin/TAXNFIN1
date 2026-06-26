import { useState, useEffect, useCallback } from 'react';
import api from '../api/axios';
import { sessionGet } from '../utils/sessionStore';

const NAVY    = '#1B3A6B';
const GOLD    = '#C9A84C';
const PAGE_BG = '#F8F9FA';

const ROL_BADGE = {
  cfo:      { bg: '#EEF3FB', color: NAVY,      label: 'CFO'      },
  contador: { bg: '#EEF8F2', color: '#1E7145', label: 'Contador' },
  viewer:   { bg: '#F1F5F9', color: '#475569', label: 'Viewer'   },
  admin:    { bg: '#FFF5F5', color: '#C00000', label: 'Admin'    },
};

function RolBadge({ rol }) {
  const s = ROL_BADGE[rol] || ROL_BADGE.viewer;
  return (
    <span style={{
      background: s.bg, color: s.color,
      fontSize: '11px', fontWeight: 700,
      padding: '2px 8px', borderRadius: '4px',
      textTransform: 'uppercase', letterSpacing: '0.04em',
    }}>
      {s.label}
    </span>
  );
}

function EmpresaTag({ nombre }) {
  return (
    <span style={{
      background: '#F1F5F9', color: '#475569',
      fontSize: '11px', padding: '2px 7px',
      borderRadius: '4px', marginRight: '4px',
    }}>
      {nombre}
    </span>
  );
}

export default function Usuarios() {
  const storedUser = JSON.parse(sessionGet('user') || localStorage.getItem('user') || '{}');
  const isCFO = ['cfo', 'admin'].includes(storedUser?.role);

  const [empresas,    setEmpresas]    = useState([]);
  const [activos,     setActivos]     = useState([]);
  const [inactivos,   setInactivos]   = useState([]);
  const [inactivosOpen, setInactivosOpen] = useState(false);
  const [loadingUsers, setLoadingUsers] = useState(false);

  // Invitar
  const [form, setForm]           = useState({ nombre: '', email: '', rol: 'viewer', company_ids: [] });
  const [invitando, setInvitando] = useState(false);
  const [invitacion, setInvitacion] = useState(null);
  const [invError, setInvError]   = useState('');

  // Editar empresas (modal)
  const [modalUser, setModalUser]         = useState(null);
  const [modalCompanyIds, setModalCompanyIds] = useState([]);
  const [savingModal, setSavingModal]     = useState(false);

  const cargarDatos = useCallback(async () => {
    setLoadingUsers(true);
    try {
      const [empRes, usrRes] = await Promise.all([
        api.get('/usuarios/mis-empresas'),
        api.get('/usuarios/mis-usuarios'),
      ]);
      setEmpresas(empRes.data.empresas || []);
      setActivos(usrRes.data.activos || []);
      setInactivos(usrRes.data.inactivos || []);
    } catch {
      // silently ignore
    } finally {
      setLoadingUsers(false);
    }
  }, []);

  useEffect(() => { if (isCFO) cargarDatos(); }, [isCFO, cargarDatos]);

  const empresaMap = Object.fromEntries(empresas.map(e => [e.id, e.nombre]));

  // ── Invitar ──────────────────────────────────────────────────────────────────
  async function handleInvitar(e) {
    e.preventDefault();
    setInvError('');
    setInvitacion(null);
    if (!form.nombre || !form.email) return setInvError('Nombre y email son obligatorios');
    if (!form.company_ids.length)    return setInvError('Selecciona al menos una empresa');
    setInvitando(true);
    try {
      const r = await api.post('/usuarios/invitar', form);
      setInvitacion(r.data);
      setForm({ nombre: '', email: '', rol: 'viewer', company_ids: [] });
      cargarDatos();
    } catch (err) {
      setInvError(err.response?.data?.detail || 'Error al invitar usuario');
    } finally {
      setInvitando(false);
    }
  }

  function toggleEmpresa(id) {
    setForm(f => ({
      ...f,
      company_ids: f.company_ids.includes(id)
        ? f.company_ids.filter(x => x !== id)
        : [...f.company_ids, id],
    }));
  }

  // ── Cambiar rol inline ───────────────────────────────────────────────────────
  async function handleRolChange(userId, nuevoRol) {
    try {
      await api.put(`/usuarios/${userId}/rol`, { rol: nuevoRol });
      cargarDatos();
    } catch (err) {
      alert(err.response?.data?.detail || 'Error al cambiar rol');
    }
  }

  // ── Desactivar ───────────────────────────────────────────────────────────────
  async function handleDesactivar(userId, nombre) {
    if (!window.confirm(`¿Desactivar a ${nombre}?`)) return;
    try {
      await api.delete(`/usuarios/${userId}`);
      cargarDatos();
    } catch (err) {
      alert(err.response?.data?.detail || 'Error al desactivar usuario');
    }
  }

  // ── Reactivar ────────────────────────────────────────────────────────────────
  async function handleReactivar(userId) {
    try {
      await api.put(`/usuarios/${userId}/reactivar`);
      cargarDatos();
    } catch (err) {
      alert(err.response?.data?.detail || 'Error al reactivar usuario');
    }
  }

  // ── Modal empresas ───────────────────────────────────────────────────────────
  function openModal(user) {
    setModalUser(user);
    setModalCompanyIds([...(user.empresas_asignadas || [])]);
  }

  async function saveModal() {
    if (!modalCompanyIds.length) return alert('Selecciona al menos una empresa');
    setSavingModal(true);
    try {
      await api.put(`/usuarios/${modalUser.user_id}/empresas`, { company_ids: modalCompanyIds });
      setModalUser(null);
      cargarDatos();
    } catch (err) {
      alert(err.response?.data?.detail || 'Error al guardar empresas');
    } finally {
      setSavingModal(false);
    }
  }

  // ── Guard ────────────────────────────────────────────────────────────────────
  if (!isCFO) {
    return (
      <div style={{ minHeight: '100vh', background: PAGE_BG, display: 'flex', alignItems: 'center', justifyContent: 'center' }}>
        <div style={{ textAlign: 'center', color: '#64748B' }}>
          <p style={{ fontSize: '32px' }}>🔒</p>
          <p style={{ fontWeight: 600 }}>No tienes permisos para gestionar usuarios</p>
        </div>
      </div>
    );
  }

  return (
    <div style={{ minHeight: '100vh', background: PAGE_BG, padding: '24px', fontFamily: 'system-ui, Arial, sans-serif' }}>
      <div style={{ maxWidth: '960px', margin: '0 auto' }} className="space-y-6">

        {/* Header */}
        <div style={{ background: '#FFF', borderBottom: `3px solid ${GOLD}`, borderRadius: '4px 4px 0 0', padding: '20px 24px', boxShadow: '0 1px 3px rgba(0,0,0,0.07)' }}>
          <h1 style={{ color: NAVY, fontSize: '22px', fontWeight: 700, margin: 0 }}>👥 Gestión de Usuarios</h1>
          <p style={{ color: '#64748B', fontSize: '13px', margin: '4px 0 0' }}>Administra quién tiene acceso a tus empresas</p>
        </div>

        {/* ── Invitar usuario ─────────────────────────────────────────────── */}
        <div style={{ background: '#FFF', border: '1px solid #E2E8F0', borderRadius: '4px', padding: '20px', boxShadow: '0 1px 3px rgba(0,0,0,0.05)' }}>
          <h2 style={{ color: NAVY, fontSize: '14px', fontWeight: 700, margin: '0 0 16px' }}>Invitar nuevo usuario</h2>
          <form onSubmit={handleInvitar} className="space-y-4">
            <div className="grid grid-cols-1 gap-3" style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: '12px' }}>
              <div>
                <label style={{ fontSize: '12px', color: '#64748B', display: 'block', marginBottom: '4px' }}>Nombre completo</label>
                <input
                  data-testid="inv-nombre"
                  type="text"
                  value={form.nombre}
                  onChange={e => setForm(f => ({ ...f, nombre: e.target.value }))}
                  placeholder="Ej. María González"
                  style={{ width: '100%', border: '1px solid #CBD5E1', borderRadius: '4px', padding: '8px 12px', fontSize: '13px', color: NAVY, outline: 'none', boxSizing: 'border-box' }}
                />
              </div>
              <div>
                <label style={{ fontSize: '12px', color: '#64748B', display: 'block', marginBottom: '4px' }}>Email</label>
                <input
                  data-testid="inv-email"
                  type="email"
                  value={form.email}
                  onChange={e => setForm(f => ({ ...f, email: e.target.value }))}
                  placeholder="maria@empresa.com"
                  style={{ width: '100%', border: '1px solid #CBD5E1', borderRadius: '4px', padding: '8px 12px', fontSize: '13px', color: NAVY, outline: 'none', boxSizing: 'border-box' }}
                />
              </div>
            </div>

            <div>
              <label style={{ fontSize: '12px', color: '#64748B', display: 'block', marginBottom: '4px' }}>Rol</label>
              <select
                data-testid="inv-rol"
                value={form.rol}
                onChange={e => setForm(f => ({ ...f, rol: e.target.value }))}
                style={{ border: '1px solid #CBD5E1', borderRadius: '4px', padding: '8px 12px', fontSize: '13px', color: NAVY, background: '#FFF', outline: 'none' }}
              >
                <option value="cfo">CFO — Administrador total de la plataforma</option>
                <option value="contador">Contador — Acceso operativo y carga de información</option>
                <option value="viewer">Viewer — Solo lectura, ideal para socios o directivos</option>
              </select>
            </div>

            <div>
              <label style={{ fontSize: '12px', color: '#64748B', display: 'block', marginBottom: '8px' }}>Empresas con acceso</label>
              <div style={{ display: 'flex', flexWrap: 'wrap', gap: '8px' }}>
                {empresas.map(emp => (
                  <label key={emp.id} style={{
                    display: 'flex', alignItems: 'center', gap: '6px',
                    background: form.company_ids.includes(emp.id) ? '#EEF3FB' : '#F8F9FA',
                    border: `1px solid ${form.company_ids.includes(emp.id) ? NAVY : '#CBD5E1'}`,
                    borderRadius: '4px', padding: '6px 10px', cursor: 'pointer', fontSize: '13px',
                  }}>
                    <input
                      type="checkbox"
                      checked={form.company_ids.includes(emp.id)}
                      onChange={() => toggleEmpresa(emp.id)}
                      style={{ accentColor: NAVY }}
                    />
                    {emp.nombre}
                  </label>
                ))}
                {!empresas.length && <p style={{ fontSize: '12px', color: '#94A3B8' }}>Cargando empresas…</p>}
              </div>
            </div>

            {invError && (
              <p style={{ fontSize: '12px', color: '#B91C1C', background: '#FFF5F5', padding: '8px 12px', borderRadius: '4px', border: '1px solid #FCA5A5' }}>
                {invError}
              </p>
            )}

            <button
              data-testid="inv-submit"
              type="submit"
              disabled={invitando}
              style={{ background: invitando ? '#94A3B8' : NAVY, color: '#FFF', border: 'none', borderRadius: '4px', padding: '9px 20px', fontSize: '13px', fontWeight: 600, cursor: invitando ? 'not-allowed' : 'pointer' }}
            >
              {invitando ? 'Enviando…' : 'Enviar Invitación'}
            </button>
          </form>

          {/* Resultado de invitación */}
          {invitacion && (
            <div style={{ marginTop: '16px', background: '#EEF8F2', border: '1px solid #1E7145', borderRadius: '4px', padding: '16px' }}>
              <p style={{ fontWeight: 700, color: '#1E7145', marginBottom: '8px' }}>✓ Usuario creado correctamente</p>
              <p style={{ fontSize: '13px', color: '#374151' }}>
                Comparte esta contraseña con <strong>{invitacion.nombre}</strong> de forma segura:
              </p>
              <p style={{ fontFamily: 'monospace', fontSize: '20px', fontWeight: 700, color: NAVY, letterSpacing: '0.1em', margin: '8px 0' }}>
                {invitacion.temp_password}
              </p>
              <p style={{ fontSize: '11px', color: '#64748B' }}>El usuario deberá cambiar su contraseña en el primer inicio de sesión.</p>
            </div>
          )}
        </div>

        {/* ── Usuarios activos ────────────────────────────────────────────── */}
        <div style={{ background: '#FFF', border: '1px solid #E2E8F0', borderRadius: '4px', boxShadow: '0 1px 3px rgba(0,0,0,0.05)' }}>
          <div style={{ padding: '16px 20px', borderBottom: '1px solid #E2E8F0', display: 'flex', alignItems: 'center', justifyContent: 'space-between' }}>
            <h2 style={{ color: NAVY, fontSize: '14px', fontWeight: 700, margin: 0 }}>
              Usuarios activos ({activos.length})
            </h2>
            {loadingUsers && <span style={{ fontSize: '12px', color: '#94A3B8' }}>Cargando…</span>}
          </div>

          {activos.length === 0 && !loadingUsers ? (
            <p style={{ padding: '16px 20px', fontSize: '13px', color: '#94A3B8' }}>Sin usuarios activos todavía.</p>
          ) : (
            <div style={{ overflowX: 'auto' }}>
              <table style={{ width: '100%', borderCollapse: 'collapse', fontSize: '13px' }}>
                <thead>
                  <tr style={{ background: PAGE_BG, borderBottom: '1px solid #E2E8F0' }}>
                    {['Nombre', 'Email', 'Rol', 'Empresas', 'Acciones'].map(h => (
                      <th key={h} style={{ padding: '10px 14px', textAlign: 'left', fontSize: '11px', fontWeight: 700, color: '#64748B', textTransform: 'uppercase', letterSpacing: '0.05em' }}>{h}</th>
                    ))}
                  </tr>
                </thead>
                <tbody>
                  {activos.map(u => (
                    <tr key={u.user_id} style={{ borderBottom: '1px solid #F1F5F9' }}>
                      <td style={{ padding: '10px 14px', fontWeight: 600, color: NAVY }}>{u.nombre}</td>
                      <td style={{ padding: '10px 14px', color: '#475569' }}>{u.email}</td>
                      <td style={{ padding: '10px 14px' }}>
                        <select
                          value={u.rol}
                          onChange={e => handleRolChange(u.user_id, e.target.value)}
                          style={{ border: '1px solid #E2E8F0', borderRadius: '4px', padding: '3px 8px', fontSize: '12px', color: NAVY, background: '#FFF', cursor: 'pointer' }}
                        >
                          <option value="cfo">CFO</option>
                          <option value="contador">Contador</option>
                          <option value="viewer">Viewer</option>
                        </select>
                      </td>
                      <td style={{ padding: '10px 14px' }}>
                        <div style={{ display: 'flex', flexWrap: 'wrap', gap: '4px', alignItems: 'center' }}>
                          {(u.empresas_asignadas || []).map(id => (
                            <EmpresaTag key={id} nombre={empresaMap[id] || id.slice(0, 8)} />
                          ))}
                          <button
                            onClick={() => openModal(u)}
                            style={{ fontSize: '11px', color: NAVY, background: 'none', border: `1px solid ${NAVY}`, borderRadius: '4px', padding: '2px 6px', cursor: 'pointer' }}
                          >
                            Editar
                          </button>
                        </div>
                      </td>
                      <td style={{ padding: '10px 14px' }}>
                        <button
                          onClick={() => handleDesactivar(u.user_id, u.nombre)}
                          style={{ fontSize: '11px', color: '#B91C1C', background: '#FFF5F5', border: '1px solid #FCA5A5', borderRadius: '4px', padding: '4px 10px', cursor: 'pointer' }}
                        >
                          Desactivar
                        </button>
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          )}
        </div>

        {/* ── Usuarios inactivos (colapsable) ─────────────────────────────── */}
        {inactivos.length > 0 && (
          <div style={{ background: '#FFF', border: '1px solid #E2E8F0', borderRadius: '4px', boxShadow: '0 1px 3px rgba(0,0,0,0.05)' }}>
            <button
              onClick={() => setInactivosOpen(o => !o)}
              style={{ width: '100%', display: 'flex', justifyContent: 'space-between', alignItems: 'center', padding: '12px 20px', background: 'none', border: 'none', fontSize: '13px', color: '#475569', cursor: 'pointer' }}
            >
              <span>Usuarios inactivos ({inactivos.length})</span>
              <span style={{ color: '#94A3B8' }}>{inactivosOpen ? '▲' : '▼'}</span>
            </button>
            {inactivosOpen && (
              <div style={{ borderTop: '1px solid #E2E8F0', padding: '12px 20px' }} className="space-y-2">
                {inactivos.map(u => (
                  <div key={u.user_id} style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', padding: '8px 0', borderBottom: '1px solid #F1F5F9' }}>
                    <div>
                      <span style={{ fontWeight: 600, color: '#94A3B8', marginRight: '8px' }}>{u.nombre}</span>
                      <span style={{ fontSize: '12px', color: '#CBD5E1' }}>{u.email}</span>
                    </div>
                    <button
                      onClick={() => handleReactivar(u.user_id)}
                      style={{ fontSize: '11px', color: '#1E7145', background: '#EEF8F2', border: '1px solid #1E7145', borderRadius: '4px', padding: '4px 10px', cursor: 'pointer' }}
                    >
                      Reactivar
                    </button>
                  </div>
                ))}
              </div>
            )}
          </div>
        )}

      </div>

      {/* ── Modal editar empresas ────────────────────────────────────────── */}
      {modalUser && (
        <div style={{ position: 'fixed', inset: 0, background: 'rgba(0,0,0,0.4)', display: 'flex', alignItems: 'center', justifyContent: 'center', zIndex: 50 }}>
          <div style={{ background: '#FFF', borderRadius: '8px', padding: '24px', width: '420px', maxWidth: '90vw', boxShadow: '0 8px 32px rgba(0,0,0,0.15)' }}>
            <h3 style={{ color: NAVY, fontWeight: 700, marginTop: 0 }}>Empresas de {modalUser.nombre}</h3>
            <div style={{ display: 'flex', flexDirection: 'column', gap: '8px', marginBottom: '16px' }}>
              {empresas.map(emp => (
                <label key={emp.id} style={{ display: 'flex', alignItems: 'center', gap: '8px', cursor: 'pointer', fontSize: '13px' }}>
                  <input
                    type="checkbox"
                    checked={modalCompanyIds.includes(emp.id)}
                    onChange={() => setModalCompanyIds(ids =>
                      ids.includes(emp.id) ? ids.filter(x => x !== emp.id) : [...ids, emp.id]
                    )}
                    style={{ accentColor: NAVY }}
                  />
                  {emp.nombre}
                </label>
              ))}
            </div>
            <div style={{ display: 'flex', gap: '8px', justifyContent: 'flex-end' }}>
              <button onClick={() => setModalUser(null)} style={{ background: '#F1F5F9', border: 'none', borderRadius: '4px', padding: '8px 16px', fontSize: '13px', cursor: 'pointer', color: '#475569' }}>
                Cancelar
              </button>
              <button
                onClick={saveModal}
                disabled={savingModal}
                style={{ background: savingModal ? '#94A3B8' : NAVY, color: '#FFF', border: 'none', borderRadius: '4px', padding: '8px 16px', fontSize: '13px', fontWeight: 600, cursor: savingModal ? 'not-allowed' : 'pointer' }}
              >
                {savingModal ? 'Guardando…' : 'Guardar'}
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
