import { useState, useEffect } from 'react';
import SATIntegration from '@/components/SATIntegration';
import AlegraIntegration from '@/components/AlegraIntegration';
import ContalinkIntegration from './ContalinkIntegration';
import { Building2, Cloud, Link2 } from 'lucide-react';
import api from '@/api/axios';
import { toast } from 'sonner';

const TABS = [
  {
    key: 'sat',
    label: 'SAT (e.firma / FIEL)',
    icon: Cloud,
    color: 'text-blue-600',
    bg: 'bg-blue-50',
    border: 'border-blue-200',
    activeBg: 'bg-blue-600',
  },
  {
    key: 'alegra',
    label: 'Alegra',
    icon: Building2,
    color: 'text-purple-600',
    bg: 'bg-purple-50',
    border: 'border-purple-200',
    activeBg: 'bg-purple-600',
  },
  {
    key: 'contalink',
    label: 'Contalink',
    icon: Link2,
    color: 'text-blue-700',
    bg: 'bg-blue-50',
    border: 'border-blue-300',
    activeBg: 'bg-blue-700',
  },
];

const Integrations = () => {
  const [activeTab, setActiveTab] = useState('sat');

  // ── CIEC state ──────────────────────────────────────────────────────────────
  const [ciecStatus, setCiecStatus] = useState('not_configured');
  const [ciecData, setCiecData] = useState(null);
  const [ciecRFC, setCiecRFC] = useState('');
  const [ciecPassword, setCiecPassword] = useState('');
  const [ciecLoading, setCiecLoading] = useState(false);

  const loadCiecStatus = async () => {
    try {
      const res = await api.get('/sat/ciec/status');
      setCiecStatus(res.data.status);
      setCiecData(res.data);
    } catch {
      // silencioso — CIEC es opcional
    }
  };

  useEffect(() => {
    loadCiecStatus();
  }, []);

  const saveCIEC = async () => {
    if (!ciecRFC || !ciecPassword) {
      toast.error('RFC y contraseña son requeridos');
      return;
    }
    setCiecLoading(true);
    try {
      await api.post('/sat/ciec/credentials', { rfc: ciecRFC, ciec: ciecPassword });
      toast.success('Credenciales CIEC guardadas');
      setCiecPassword('');
      await loadCiecStatus();
    } catch {
      toast.error('Error guardando credenciales');
    } finally {
      setCiecLoading(false);
    }
  };

  const testCIEC = async () => {
    if (!ciecRFC || !ciecPassword) {
      toast.error('Ingresa RFC y contraseña primero');
      return;
    }
    setCiecLoading(true);
    try {
      const res = await api.post('/sat/ciec/test-connection', { rfc: ciecRFC, ciec: ciecPassword });
      if (res.data.success) {
        toast.success('✅ Conexión exitosa con SAT');
      } else {
        toast.error('❌ ' + (res.data.error || res.data.message || 'Credenciales incorrectas'));
      }
    } catch {
      toast.error('Error al probar la conexión');
    } finally {
      setCiecLoading(false);
    }
  };

  const syncCIEC = async () => {
    setCiecLoading(true);
    try {
      await api.post('/sat/ciec/sync', { tipo: 'ambos' });
      toast.success('Sincronización iniciada — espera 2-5 minutos');
    } catch {
      toast.error('Error al iniciar sincronización');
    } finally {
      setCiecLoading(false);
    }
  };

  const deleteCIEC = async () => {
    if (!window.confirm('¿Eliminar credenciales CIEC? Esta acción no se puede deshacer.')) return;
    try {
      await api.delete('/sat/ciec/credentials');
      setCiecStatus('not_configured');
      setCiecData(null);
      toast.success('Credenciales eliminadas');
    } catch {
      toast.error('Error al eliminar credenciales');
    }
  };

  return (
    <div className="p-8 space-y-6">
      <div>
        <h1 className="text-4xl font-bold text-[#0F172A] mb-2" style={{ fontFamily: 'Manrope' }}>
          Integraciones
        </h1>
        <p className="text-[#64748B]">
          Conecta TaxnFin con tus herramientas contables y fiscales
        </p>
      </div>

      <div className="flex gap-3 border-b border-gray-200 pb-0">
        {TABS.map(tab => {
          const Icon = tab.icon;
          const isActive = activeTab === tab.key;
          return (
            <button
              key={tab.key}
              onClick={() => setActiveTab(tab.key)}
              className={`flex items-center gap-2 px-5 py-3 text-sm font-medium rounded-t-lg border-b-2 transition-all ${
                isActive
                  ? `border-[#0F172A] text-[#0F172A] bg-white`
                  : `border-transparent text-[#64748B] hover:text-[#0F172A] hover:bg-gray-50`
              }`}
            >
              <Icon size={16} />
              {tab.label}
            </button>
          );
        })}
      </div>

      <div className="mt-0">
        {activeTab === 'sat' && (
          <>
            <SATIntegration onSyncComplete={() => {}} />

            {/* SAT CIEC */}
            <div className="mt-6 border rounded-lg p-5">
              <h3 className="font-semibold text-[#0F172A] mb-1 flex items-center gap-2">
                🔑 Conexión SAT con CIEC (Contraseña)
              </h3>
              <p className="text-sm text-gray-500 mb-4">
                Descarga automática de CFDIs usando tu RFC y contraseña del SAT.
                Más fácil que e.firma — no requiere certificados.
              </p>

              {ciecStatus === 'configured' ? (
                <div className="flex items-center justify-between p-3 bg-green-50 border border-green-200 rounded-lg">
                  <div>
                    <p className="text-sm font-medium text-green-800">
                      ✅ CIEC configurada — RFC: {ciecData?.rfc}
                    </p>
                    <p className="text-xs text-green-600">
                      Último sync: {ciecData?.last_sync ? new Date(ciecData.last_sync).toLocaleString('es-MX') : 'Nunca'}
                    </p>
                  </div>
                  <div className="flex gap-2">
                    <button
                      onClick={syncCIEC}
                      disabled={ciecLoading}
                      className="px-3 py-1.5 bg-[#10B981] text-white text-sm rounded disabled:opacity-50"
                    >
                      {ciecLoading ? 'Iniciando...' : 'Sincronizar CFDIs'}
                    </button>
                    <button
                      onClick={deleteCIEC}
                      className="px-3 py-1.5 bg-red-100 text-red-600 text-sm rounded hover:bg-red-200"
                    >
                      Eliminar
                    </button>
                  </div>
                </div>
              ) : (
                <div className="space-y-3">
                  <input
                    type="text"
                    placeholder="RFC (ej. XAXX010101000)"
                    value={ciecRFC}
                    onChange={e => setCiecRFC(e.target.value.toUpperCase())}
                    className="w-full border rounded px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-[#0F172A]"
                  />
                  <input
                    type="password"
                    placeholder="Contraseña SAT (CIEC)"
                    value={ciecPassword}
                    onChange={e => setCiecPassword(e.target.value)}
                    className="w-full border rounded px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-[#0F172A]"
                  />
                  <div className="flex gap-2">
                    <button
                      onClick={testCIEC}
                      disabled={ciecLoading}
                      className="px-4 py-2 border rounded text-sm hover:bg-gray-50 disabled:opacity-50"
                    >
                      {ciecLoading ? 'Probando...' : 'Probar conexión'}
                    </button>
                    <button
                      onClick={saveCIEC}
                      disabled={ciecLoading}
                      className="px-4 py-2 bg-[#0F172A] text-white rounded text-sm hover:bg-slate-800 disabled:opacity-50"
                    >
                      {ciecLoading ? 'Guardando...' : 'Guardar y conectar'}
                    </button>
                  </div>
                </div>
              )}
            </div>
          </>
        )}
        {activeTab === 'alegra' && <AlegraIntegration />}
        {activeTab === 'contalink' && <ContalinkIntegration />}
      </div>
    </div>
  );
};

export default Integrations;
