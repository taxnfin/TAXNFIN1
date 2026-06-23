import { useState, useEffect } from 'react';
import SATIntegration from '@/components/SATIntegration';
import AlegraIntegration from '@/components/AlegraIntegration';
import ContalinkIntegration from './ContalinkIntegration';
import { Building2, Cloud, Link2, Eye, EyeOff, RefreshCw, Trash2, Wifi, CheckCircle, AlertCircle, Clock, Download } from 'lucide-react';
import api from '@/api/axios';
import { toast } from 'sonner';

const TABS = [
  { key: 'sat',       label: 'SAT (e.firma / FIEL)', icon: Cloud,     color: 'text-blue-600' },
  { key: 'alegra',    label: 'Alegra',                icon: Building2, color: 'text-purple-600' },
  { key: 'contalink', label: 'Contalink',             icon: Link2,     color: 'text-blue-700' },
];

const CiecStatusCard = ({ data, onSync, onDelete, loading, onSyncExtras, syncingExtras, extras, onDescargarConstancia, downloadingConstancia }) => {
  const lastSync = data?.last_sync ? new Date(data.last_sync) : null;
  const formattedSync = lastSync
    ? lastSync.toLocaleString('es-MX', { day: '2-digit', month: 'short', year: 'numeric', hour: '2-digit', minute: '2-digit' })
    : 'Nunca';
  return (
    <div className="rounded-xl border border-green-200 bg-green-50 p-5">
      <div className="flex items-start justify-between gap-4">
        <div className="flex items-center gap-3">
          <div className="w-10 h-10 rounded-full bg-green-100 flex items-center justify-center">
            <CheckCircle size={20} className="text-green-600" />
          </div>
          <div>
            <p className="font-semibold text-green-900 text-sm">CIEC conectada</p>
            <p className="text-green-700 text-xs font-mono mt-0.5">{data?.rfc}</p>
          </div>
        </div>
        <div className="flex gap-2">
          <button onClick={onSync} disabled={loading}
            className="flex items-center gap-1.5 px-3 py-1.5 bg-[#10B981] text-white text-xs font-medium rounded-lg hover:bg-green-600 disabled:opacity-50 transition-colors">
            <RefreshCw size={13} className={loading ? 'animate-spin' : ''} />
            {loading ? 'Iniciando...' : 'Sincronizar CFDIs'}
          </button>
          <button onClick={onSyncExtras} disabled={syncingExtras || loading}
            className="flex items-center gap-1.5 px-3 py-1.5 bg-white border border-blue-200 text-blue-600 text-xs font-medium rounded-lg hover:bg-blue-50 disabled:opacity-50 transition-colors">
            {syncingExtras ? <RefreshCw size={13} className="animate-spin" /> : <Download size={13} />}
            {syncingExtras ? 'Descargando...' : 'Descargar documentos SAT'}
          </button>
          <button onClick={onDescargarConstancia} disabled={downloadingConstancia || loading}
            className="flex items-center gap-1.5 px-3 py-1.5 bg-white border border-indigo-200 text-indigo-600 text-xs font-medium rounded-lg hover:bg-indigo-50 disabled:opacity-50 transition-colors">
            {downloadingConstancia ? <RefreshCw size={13} className="animate-spin" /> : <Download size={13} />}
            {downloadingConstancia ? 'Generando...' : 'Descargar Constancia'}
          </button>
          <button onClick={onDelete}
            className="flex items-center gap-1.5 px-3 py-1.5 bg-white border border-red-200 text-red-500 text-xs font-medium rounded-lg hover:bg-red-50 transition-colors">
            <Trash2 size={13} /> Eliminar
          </button>
        </div>
      </div>
      <div className="mt-4 grid grid-cols-3 gap-3">
        <div className="bg-white rounded-lg border border-green-100 px-4 py-3">
          <p className="text-[10px] text-gray-400 uppercase tracking-wider mb-1">CFDIs descargados</p>
          <p className="text-xl font-bold text-[#0F172A]">{data?.total_cfdis ?? '—'}</p>
        </div>
        <div className="bg-white rounded-lg border border-green-100 px-4 py-3">
          <p className="text-[10px] text-gray-400 uppercase tracking-wider mb-1">Errores</p>
          <p className={`text-xl font-bold ${(data?.errors_count ?? 0) > 0 ? 'text-red-500' : 'text-[#0F172A]'}`}>
            {data?.errors_count ?? 0}
          </p>
        </div>
        <div className="bg-white rounded-lg border border-green-100 px-4 py-3">
          <p className="text-[10px] text-gray-400 uppercase tracking-wider mb-1">Último sync</p>
          <p className="text-xs font-medium text-[#0F172A] flex items-center gap-1">
            <Clock size={11} className="text-gray-400" />{formattedSync}
          </p>
        </div>
      </div>
      {extras && (
        <div className="mt-4 border-t border-green-100 pt-4 space-y-3">
          <p className="text-[10px] font-semibold text-gray-400 uppercase tracking-wider">Documentos SAT descargados</p>
          <div className="grid grid-cols-1 gap-2">
            {extras.opinion_cumplimiento && (
              <div className={`flex items-center gap-2 px-3 py-2 rounded-lg text-xs border ${extras.opinion_cumplimiento.status === 'positiva' ? 'bg-green-50 border-green-200 text-green-700' : extras.opinion_cumplimiento.status === 'negativa' ? 'bg-red-50 border-red-200 text-red-700' : 'bg-gray-50 border-gray-200 text-gray-600'}`}>
                {extras.opinion_cumplimiento.status === 'positiva' ? <CheckCircle size={13} /> : <AlertCircle size={13} />}
                <span className="font-medium">Opinión de Cumplimiento:</span>
                <span className="capitalize">{extras.opinion_cumplimiento.status ?? '—'}</span>
              </div>
            )}
            {extras.buzon_mensajes?.length > 0 && (
              <div className="flex items-center gap-2 px-3 py-2 rounded-lg text-xs border bg-blue-50 border-blue-200 text-blue-700">
                <CheckCircle size={13} />
                <span className="font-medium">Buzón Tributario:</span>
                <span>{extras.buzon_mensajes.length} mensaje(s) descargado(s)</span>
              </div>
            )}
            {extras.declaraciones_pendientes?.length > 0 && (
              <div className="flex items-center gap-2 px-3 py-2 rounded-lg text-xs border bg-amber-50 border-amber-200 text-amber-700">
                <AlertCircle size={13} />
                <span className="font-medium">Declaraciones pendientes:</span>
                <span>{extras.declaraciones_pendientes.length} obligación(es)</span>
              </div>
            )}
            {extras.updated_at && (
              <p className="text-[10px] text-gray-400 flex items-center gap-1">
                <Clock size={10} /> Actualizado: {new Date(extras.updated_at).toLocaleString('es-MX')}
              </p>
            )}
          </div>
        </div>
      )}
    </div>
  );
};

const CiecForm = ({ onTest, onSave, loading }) => {
  const [rfc, setRfc] = useState('');
  const [ciec, setCiec] = useState('');
  const [showCiec, setShowCiec] = useState(false);
  const [testResult, setTestResult] = useState(null);
  const [testMsg, setTestMsg] = useState('');
  const isValid = rfc.length >= 12 && ciec.length >= 8;

  const handleTest = async () => {
    setTestResult(null);
    const res = await onTest(rfc, ciec);
    if (res?.success) { setTestResult('ok'); setTestMsg('Conexión exitosa con el portal SAT'); }
    else { setTestResult('error'); setTestMsg(res?.error || 'Credenciales incorrectas'); }
  };

  return (
    <div className="space-y-4">
      <div>
        <label className="block text-xs font-medium text-gray-600 mb-1.5">RFC de la empresa</label>
        <input type="text" placeholder="Ej. XAXX010101000" value={rfc}
          onChange={e => setRfc(e.target.value.toUpperCase().trim())} maxLength={13}
          className="w-full border border-gray-200 rounded-lg px-3 py-2.5 text-sm font-mono focus:outline-none focus:ring-2 focus:ring-[#0F172A]" />
      </div>
      <div>
        <label className="block text-xs font-medium text-gray-600 mb-1.5">
          Contraseña SAT (CIEC) <span className="ml-1 text-gray-400 font-normal">— la misma que usas en sat.gob.mx</span>
        </label>
        <div className="relative">
          <input type={showCiec ? 'text' : 'password'} placeholder="Contraseña del portal SAT" value={ciec}
            onChange={e => setCiec(e.target.value)}
            className="w-full border border-gray-200 rounded-lg px-3 py-2.5 pr-10 text-sm focus:outline-none focus:ring-2 focus:ring-[#0F172A]" />
          <button type="button" onClick={() => setShowCiec(v => !v)}
            className="absolute right-3 top-1/2 -translate-y-1/2 text-gray-400 hover:text-gray-600">
            {showCiec ? <EyeOff size={16} /> : <Eye size={16} />}
          </button>
        </div>
      </div>
      {testResult && (
        <div className={`flex items-center gap-2 p-3 rounded-lg text-sm ${testResult === 'ok' ? 'bg-green-50 border border-green-200 text-green-700' : 'bg-red-50 border border-red-200 text-red-700'}`}>
          {testResult === 'ok' ? <CheckCircle size={15} /> : <AlertCircle size={15} />} {testMsg}
        </div>
      )}
      <div className="flex gap-2 pt-1">
        <button onClick={handleTest} disabled={loading || !isValid}
          className="flex items-center gap-2 px-4 py-2.5 border border-gray-200 rounded-lg text-sm font-medium hover:bg-gray-50 disabled:opacity-40 disabled:cursor-not-allowed transition-colors">
          {loading ? <RefreshCw size={14} className="animate-spin" /> : <Wifi size={14} />}
          {loading ? 'Conectando con el SAT...' : 'Probar conexión'}
        </button>
        <button onClick={() => onSave(rfc, ciec)} disabled={loading || !isValid}
          className="flex items-center gap-2 px-4 py-2.5 bg-[#0F172A] text-white rounded-lg text-sm font-medium hover:bg-slate-800 disabled:opacity-40 disabled:cursor-not-allowed transition-colors">
          {loading ? 'Guardando...' : 'Guardar y conectar'}
        </button>
      </div>
      <p className="text-[11px] text-gray-400">🔒 Tu contraseña se cifra con AES-256 antes de guardarse.</p>
    </div>
  );
};

const Integrations = () => {
  const [activeTab, setActiveTab] = useState('sat');
  const [ciecStatus, setCiecStatus] = useState('not_configured');
  const [ciecData, setCiecData] = useState(null);
  const [ciecLoading, setCiecLoading] = useState(false);
  const [ciecExtras, setCiecExtras] = useState(null);
  const [syncingExtras, setSyncingExtras] = useState(false);
  const [downloadingConstancia, setDownloadingConstancia] = useState(false);
  const [syntageData, setSyntageData] = useState(null);
  const [syncingSyntage, setSyncingSyntage] = useState(false);
  const [belvoData, setBelvoData] = useState(null);
  const [syncingBelvo, setSyncingBelvo] = useState(false);

  const loadCiecStatus = async () => {
    try {
      const res = await api.get('/sat/ciec/status');
      setCiecStatus(res.data.status);
      setCiecData(res.data);
    } catch { }
  };

  const loadCiecExtras = async () => {
    try {
      const res = await api.get('/sat/ciec/extras');
      setCiecExtras(res.data);
    } catch { }
  };

  const loadSyntageData = async () => {
    try {
      const res = await api.get('/sat/syntage/status');
      if (res.data.connected) setSyntageData(res.data);
    } catch { }
  };

  const loadBelvoData = async () => {
    try {
      const res = await api.get('/sat/belvo/status');
      if (res.data.connected) setBelvoData(res.data);
    } catch { }
  };

  useEffect(() => { loadCiecStatus(); loadCiecExtras(); loadSyntageData(); loadBelvoData(); }, []);

  const handleTest = async (rfc, ciec) => {
    setCiecLoading(true);
    try {
      const startRes = await api.post('/sat/ciec/test-connection', { rfc, ciec });
      if (startRes.data.status === 'error') return startRes.data;
      const testId = startRes.data.test_id;
      for (let i = 0; i < 40; i++) {
        await new Promise(r => setTimeout(r, 3000));
        try {
          const poll = await api.get(`/sat/ciec/test-status/${testId}`);
          const { status, result } = poll.data;
          if (status === 'done') return result;
          if (status === 'error') return result || { success: false, error: 'Error en la conexión' };
        } catch { /* red inestable, seguir intentando */ }
      }
      return { success: false, error: 'Tiempo de espera agotado (2 minutos)' };
    } catch { return { success: false, error: 'Error de conexión con el servidor' }; }
    finally { setCiecLoading(false); }
  };

  const handleSave = async (rfc, ciec) => {
    if (!rfc || !ciec) { toast.error('RFC y contraseña son requeridos'); return; }
    setCiecLoading(true);
    try {
      await api.post('/sat/ciec/credentials', { rfc, ciec });
      toast.success('✅ Credenciales SAT guardadas');
      await loadCiecStatus();
    } catch { toast.error('Error al guardar credenciales'); }
    finally { setCiecLoading(false); }
  };

  const handleSync = async () => {
    setCiecLoading(true);
    try {
      await api.post('/sat/ciec/sync', { tipo: 'ambos' });
      toast.success('Sincronización iniciada — espera 2-5 minutos');
    } catch { toast.error('Error al iniciar sincronización'); }
    finally { setCiecLoading(false); }
  };

  const handleDescargarConstancia = async () => {
    setDownloadingConstancia(true);
    try {
      const startRes = await api.post('/sat/ciec/constancia');
      if (startRes.data.status === 'error') {
        toast.error(startRes.data.message || 'Error al descargar Constancia Fiscal');
        return;
      }
      const syncId = startRes.data.sync_id;
      for (let i = 0; i < 40; i++) {
        await new Promise(r => setTimeout(r, 3000));
        try {
          const poll = await api.get(`/sat/ciec/constancia-status/${syncId}`);
          const { status, result } = poll.data;
          if (status === 'done') {
            if (result?.success && result?.pdf_base64) {
              const byteChars = atob(result.pdf_base64);
              const byteArr = new Uint8Array(byteChars.length);
              for (let j = 0; j < byteChars.length; j++) byteArr[j] = byteChars.charCodeAt(j);
              const blob = new Blob([byteArr], { type: 'application/pdf' });
              const url = URL.createObjectURL(blob);
              const a = document.createElement('a');
              a.href = url;
              a.download = result.filename || 'Constancia_Fiscal.pdf';
              document.body.appendChild(a);
              a.click();
              document.body.removeChild(a);
              URL.revokeObjectURL(url);
              toast.success('Constancia Fiscal descargada');
            } else {
              toast.error(result?.error || 'Error al generar la Constancia Fiscal');
            }
            return;
          }
          if (status === 'error') {
            toast.error(result?.error || 'Error al descargar Constancia Fiscal');
            return;
          }
        } catch { /* red inestable, seguir intentando */ }
      }
      toast.error('Tiempo de espera agotado (2 minutos)');
    } catch { toast.error('Error al descargar Constancia Fiscal'); }
    finally { setDownloadingConstancia(false); }
  };

  const handleSyncExtras = async () => {
    setSyncingExtras(true);
    try {
      const startRes = await api.post('/sat/ciec/sync-extras');
      if (startRes.data.status === 'error') {
        toast.error(startRes.data.message || 'Error al descargar documentos SAT');
        return;
      }
      const syncId = startRes.data.sync_id;
      for (let i = 0; i < 40; i++) {
        await new Promise(r => setTimeout(r, 3000));
        try {
          const poll = await api.get(`/sat/ciec/sync-extras-status/${syncId}`);
          const { status } = poll.data;
          if (status === 'done') {
            toast.success('Opinión, buzón y declaraciones descargados');
            await loadCiecExtras();
            return;
          }
          if (status === 'error') {
            toast.error(poll.data.result?.error || 'Error al descargar documentos SAT');
            return;
          }
        } catch { /* red inestable, seguir intentando */ }
      }
      toast.error('Tiempo de espera agotado (2 minutos)');
    } catch { toast.error('Error al descargar documentos SAT'); }
    finally { setSyncingExtras(false); }
  };

  const handleSyntageSync = async () => {
    setSyncingSyntage(true);
    try {
      const res = await api.post('/sat/syntage/sync');
      if (res.data.success) {
        setSyntageData(res.data);
        toast.success('Datos SAT obtenidos correctamente');
      } else {
        toast.error(res.data.error || 'Error al obtener datos fiscales SAT');
      }
    } catch { toast.error('Error al obtener datos fiscales SAT'); }
    finally { setSyncingSyntage(false); }
  };

  const handleDescargarConstanciaSyntage = async () => {
    try {
      const res = await api.get('/sat/syntage/tax-status/pdf', { responseType: 'blob' });
      const url = URL.createObjectURL(new Blob([res.data], { type: 'application/pdf' }));
      const a = document.createElement('a');
      a.href = url;
      a.download = `Constancia_${syntageData?.rfc || 'SAT'}.pdf`;
      document.body.appendChild(a);
      a.click();
      document.body.removeChild(a);
      URL.revokeObjectURL(url);
      toast.success('Constancia descargada');
    } catch { toast.error('Error al descargar PDF de Constancia'); }
  };

  const handleBelvoSync = async () => {
    setSyncingBelvo(true);
    try {
      const res = await api.post('/sat/belvo/sync', {}, { timeout: 90000 });
      if (res.data.success) {
        setBelvoData(res.data);
        toast.success('Datos SAT obtenidos correctamente');
      } else {
        toast.error(res.data.error || 'Error al obtener documentos SAT');
      }
    } catch { toast.error('Error al obtener documentos SAT'); }
    finally { setSyncingBelvo(false); }
  };

  const handleDescargarConstanciaBelvo = async () => {
    try {
      const res = await api.get('/sat/belvo/tax-status/pdf', { responseType: 'blob' });
      const url = URL.createObjectURL(new Blob([res.data], { type: 'application/pdf' }));
      const a = document.createElement('a');
      a.href = url;
      a.download = `Constancia_${belvoData?.rfc || 'SAT'}.pdf`;
      document.body.appendChild(a);
      a.click();
      document.body.removeChild(a);
      URL.revokeObjectURL(url);
      toast.success('Constancia descargada');
    } catch { toast.error('Error al descargar PDF de Constancia'); }
  };

  const handleDelete = async () => {
    if (!window.confirm('¿Eliminar credenciales CIEC? Esta acción no se puede deshacer.')) return;
    try {
      await api.delete('/sat/ciec/credentials');
      setCiecStatus('not_configured');
      setCiecData(null);
      toast.success('Credenciales eliminadas');
    } catch { toast.error('Error al eliminar credenciales'); }
  };

  return (
    <div className="p-8 space-y-6">
      <div>
        <h1 className="text-4xl font-bold text-[#0F172A] mb-2" style={{ fontFamily: 'Manrope' }}>Integraciones</h1>
        <p className="text-[#64748B]">Conecta TaxnFin con tus herramientas contables y fiscales</p>
      </div>
      <div className="flex gap-3 border-b border-gray-200">
        {TABS.map(tab => {
          const Icon = tab.icon;
          const isActive = activeTab === tab.key;
          return (
            <button key={tab.key} onClick={() => setActiveTab(tab.key)}
              className={`flex items-center gap-2 px-5 py-3 text-sm font-medium rounded-t-lg border-b-2 transition-all ${isActive ? 'border-[#0F172A] text-[#0F172A] bg-white' : 'border-transparent text-[#64748B] hover:text-[#0F172A] hover:bg-gray-50'}`}>
              <Icon size={16} />{tab.label}
            </button>
          );
        })}
      </div>
      <div>
        {activeTab === 'sat' && (
          <div className="space-y-6">
            <SATIntegration onSyncComplete={() => {}} />
            <div className="border border-gray-200 rounded-xl p-6 bg-white shadow-sm">
              <div className="flex items-start gap-3 mb-5">
                <div className="w-9 h-9 rounded-lg bg-[#0F172A] flex items-center justify-center flex-shrink-0">
                  <span className="text-white text-base">🔑</span>
                </div>
                <div>
                  <h3 className="font-semibold text-[#0F172A] text-base">Conexión SAT con CIEC</h3>
                  <p className="text-sm text-gray-500 mt-0.5">Descarga automática de CFDIs con tu RFC y contraseña del SAT — sin certificados.</p>
                </div>
              </div>
              {ciecStatus === 'configured'
                ? <CiecStatusCard data={ciecData} onSync={handleSync} onDelete={handleDelete} loading={ciecLoading} onSyncExtras={handleSyncExtras} syncingExtras={syncingExtras} extras={ciecExtras} onDescargarConstancia={handleDescargarConstancia} downloadingConstancia={downloadingConstancia} />
                : <CiecForm onTest={handleTest} onSave={handleSave} loading={ciecLoading} />
              }
            </div>

            {/* ── Sección Belvo ── */}
            {ciecStatus === 'configured' && (
              <div className="border border-gray-200 rounded-xl p-6 bg-white shadow-sm">
                <div className="flex items-start justify-between gap-4 mb-5">
                  <div className="flex items-start gap-3">
                    <div className="w-9 h-9 rounded-lg bg-blue-600 flex items-center justify-center flex-shrink-0">
                      <span className="text-white text-base">🏛️</span>
                    </div>
                    <div>
                      <h3 className="font-semibold text-[#0F172A] text-base">Documentos SAT</h3>
                      <p className="text-sm text-gray-500 mt-0.5">Constancia de Situación Fiscal y Opinión de Cumplimiento 32-D directamente del SAT.</p>
                    </div>
                  </div>
                  <button onClick={handleBelvoSync} disabled={syncingBelvo}
                    className="flex items-center gap-1.5 px-4 py-2 bg-blue-600 text-white text-xs font-medium rounded-lg hover:bg-blue-700 disabled:opacity-50 transition-colors">
                    {syncingBelvo ? <RefreshCw size={13} className="animate-spin" /> : <RefreshCw size={13} />}
                    {syncingBelvo ? 'Sincronizando...' : 'Sincronizar Documentos SAT'}
                  </button>
                </div>
                {belvoData ? (
                  <div className="space-y-3">
                    <div className="grid grid-cols-2 gap-3">
                      <div className="bg-gray-50 rounded-lg border border-gray-200 px-4 py-3">
                        <p className="text-[10px] text-gray-400 uppercase tracking-wider mb-1">Constancia de Situación Fiscal</p>
                        <p className="text-sm font-semibold text-[#0F172A]">
                          {belvoData.tax_status?.results?.[0]?.status_of_taxpayer
                            || belvoData.tax_status?.results?.[0]?.rfc
                            || 'Disponible'}
                        </p>
                        <p className="text-[10px] text-gray-500 mt-0.5 font-mono">
                          {belvoData.tax_status?.results?.[0]?.rfc || belvoData.rfc}
                        </p>
                        {belvoData.updated_at && (
                          <p className="text-[10px] text-gray-400 mt-1">
                            Actualizado: {new Date(belvoData.updated_at).toLocaleString('es-MX')}
                          </p>
                        )}
                      </div>
                      <div className={`rounded-lg border px-4 py-3 ${
                        (belvoData.tax_compliance?.results?.[0]?.status || '').toLowerCase().includes('positiv')
                          ? 'bg-green-50 border-green-200'
                          : (belvoData.tax_compliance?.results?.[0]?.status || '').toLowerCase().includes('negativ')
                          ? 'bg-red-50 border-red-200'
                          : 'bg-gray-50 border-gray-200'
                      }`}>
                        <p className="text-[10px] text-gray-400 uppercase tracking-wider mb-1">Opinión de Cumplimiento</p>
                        <p className={`text-sm font-semibold capitalize ${
                          (belvoData.tax_compliance?.results?.[0]?.status || '').toLowerCase().includes('positiv')
                            ? 'text-green-700'
                            : (belvoData.tax_compliance?.results?.[0]?.status || '').toLowerCase().includes('negativ')
                            ? 'text-red-700'
                            : 'text-[#0F172A]'
                        }`}>
                          {belvoData.tax_compliance?.results?.[0]?.status || '—'}
                        </p>
                        <p className="text-[10px] text-gray-400 mt-0.5">
                          {belvoData.tax_compliance?.results?.[0]?.compliance_type || ''}
                        </p>
                      </div>
                    </div>
                    <button onClick={handleDescargarConstanciaBelvo}
                      className="flex items-center gap-1.5 px-3 py-1.5 bg-white border border-blue-200 text-blue-600 text-xs font-medium rounded-lg hover:bg-blue-50 transition-colors">
                      <Download size={13} /> Descargar PDF Constancia
                    </button>
                  </div>
                ) : (
                  <p className="text-sm text-gray-400 text-center py-4">Haz clic en "Sincronizar Documentos SAT" para obtener los documentos.</p>
                )}
              </div>
            )}

            {/* ── Sección Syntage ── */}
            {ciecStatus === 'configured' && (
              <div className="border border-gray-200 rounded-xl p-6 bg-white shadow-sm">
                <div className="flex items-start justify-between gap-4 mb-5">
                  <div className="flex items-start gap-3">
                    <div className="w-9 h-9 rounded-lg bg-indigo-600 flex items-center justify-center flex-shrink-0">
                      <span className="text-white text-base">📋</span>
                    </div>
                    <div>
                      <h3 className="font-semibold text-[#0F172A] text-base">Datos Fiscales SAT</h3>
                      <p className="text-sm text-gray-500 mt-0.5">Constancia de Situación Fiscal y Opinión de Cumplimiento directamente del SAT.</p>
                    </div>
                  </div>
                  <button onClick={handleSyntageSync} disabled={syncingSyntage}
                    className="flex items-center gap-1.5 px-4 py-2 bg-indigo-600 text-white text-xs font-medium rounded-lg hover:bg-indigo-700 disabled:opacity-50 transition-colors">
                    {syncingSyntage ? <RefreshCw size={13} className="animate-spin" /> : <RefreshCw size={13} />}
                    {syncingSyntage ? 'Actualizando...' : 'Actualizar Datos SAT'}
                  </button>
                </div>
                {syntageData ? (
                  <div className="space-y-3">
                    <div className="grid grid-cols-2 gap-3">
                      <div className="bg-gray-50 rounded-lg border border-gray-200 px-4 py-3">
                        <p className="text-[10px] text-gray-400 uppercase tracking-wider mb-1">Constancia de Situación Fiscal</p>
                        <p className="text-sm font-semibold text-[#0F172A]">
                          {syntageData.tax_status?.['hydra:member']?.[0]?.status
                            || syntageData.tax_status?.status
                            || 'Disponible'}
                        </p>
                        {syntageData.updated_at && (
                          <p className="text-[10px] text-gray-400 mt-1">
                            Actualizado: {new Date(syntageData.updated_at).toLocaleString('es-MX')}
                          </p>
                        )}
                      </div>
                      <div className={`rounded-lg border px-4 py-3 ${
                        (syntageData.tax_compliance?.['hydra:member']?.[0]?.status || syntageData.tax_compliance?.status || '').toLowerCase().includes('positiv')
                          ? 'bg-green-50 border-green-200'
                          : (syntageData.tax_compliance?.['hydra:member']?.[0]?.status || syntageData.tax_compliance?.status || '').toLowerCase().includes('negativ')
                          ? 'bg-red-50 border-red-200'
                          : 'bg-gray-50 border-gray-200'
                      }`}>
                        <p className="text-[10px] text-gray-400 uppercase tracking-wider mb-1">Opinión de Cumplimiento</p>
                        <p className={`text-sm font-semibold capitalize ${
                          (syntageData.tax_compliance?.['hydra:member']?.[0]?.status || syntageData.tax_compliance?.status || '').toLowerCase().includes('positiv')
                            ? 'text-green-700'
                            : (syntageData.tax_compliance?.['hydra:member']?.[0]?.status || syntageData.tax_compliance?.status || '').toLowerCase().includes('negativ')
                            ? 'text-red-700'
                            : 'text-[#0F172A]'
                        }`}>
                          {syntageData.tax_compliance?.['hydra:member']?.[0]?.status
                            || syntageData.tax_compliance?.status
                            || '—'}
                        </p>
                      </div>
                    </div>
                    <button onClick={handleDescargarConstanciaSyntage}
                      className="flex items-center gap-1.5 px-3 py-1.5 bg-white border border-indigo-200 text-indigo-600 text-xs font-medium rounded-lg hover:bg-indigo-50 transition-colors">
                      <Download size={13} /> Descargar PDF Constancia
                    </button>
                  </div>
                ) : (
                  <p className="text-sm text-gray-400 text-center py-4">Haz clic en "Actualizar Datos SAT" para obtener los datos.</p>
                )}
              </div>
            )}
          </div>
        )}
        {activeTab === 'alegra' && <AlegraIntegration />}
        {activeTab === 'contalink' && <ContalinkIntegration />}
      </div>
    </div>
  );
};

export default Integrations;
