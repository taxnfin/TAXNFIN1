import { useState, useEffect } from 'react';
import api from '@/api/axios';
import { Button } from '@/components/ui/button';
import { Input } from '@/components/ui/input';
import { Label } from '@/components/ui/label';
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card';
import { toast } from 'sonner';
import { RefreshCw, CheckCircle2, XCircle, Link2, FileText, TrendingUp, AlertCircle, CreditCard, Trash2 } from 'lucide-react';
import { format } from 'date-fns';

const ContalinkIntegration = () => {
  const [status, setStatus] = useState(null);
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);
  const [testing, setTesting] = useState(false);
  const [syncingKey, setSyncingKey] = useState(null); // which button is syncing

  const [credentials, setCredentials] = useState({ api_key: '', rfc: '' });

  // Date range — same as Alegra
  const [dateFrom, setDateFrom] = useState('');
  const [dateTo, setDateTo] = useState('');

  const [syncResults, setSyncResults] = useState({});
  const [trialBalance, setTrialBalance] = useState(null);
  const [loadingBalance, setLoadingBalance] = useState(false);
  const [balanceDates, setBalanceDates] = useState({
    start_date: format(new Date(new Date().getFullYear(), new Date().getMonth(), 1), 'yyyy-MM-dd'),
    end_date: format(new Date(), 'yyyy-MM-dd'),
  });

  useEffect(() => { loadStatus(); }, []);

  const loadStatus = async () => {
    try {
      const res = await api.get('/contalink/status');
      setStatus(res.data);
    } catch {
      setStatus({ connected: false });
    } finally {
      setLoading(false);
    }
  };

  // Calculate days_back from date range, or default 90
  const getDaysBack = () => {
    if (dateFrom) {
      const from = new Date(dateFrom);
      const now = new Date();
      const diff = Math.ceil((now - from) / (1000 * 60 * 60 * 24));
      return Math.max(1, Math.min(diff, 365));
    }
    return 90;
  };

  const handleTestConnection = async () => {
    if (!credentials.api_key || !credentials.rfc) {
      toast.error('Ingresa el API Key y RFC');
      return;
    }
    setTesting(true);
    try {
      const res = await api.post('/contalink/test-connection', credentials);
      if (res.data.success) {
        toast.success('✅ Conexión exitosa con Contalink');
      } else {
        toast.error(`❌ ${res.data.message}`);
      }
    } catch {
      toast.error('Error al probar conexión');
    } finally {
      setTesting(false);
    }
  };

  const handleSaveCredentials = async () => {
    if (!credentials.api_key || !credentials.rfc) {
      toast.error('Ingresa el API Key y RFC');
      return;
    }
    setSaving(true);
    try {
      const res = await api.post('/contalink/save-credentials', credentials);
      if (res.data.success) {
        toast.success('Credenciales guardadas');
        setCredentials({ api_key: '', rfc: '' });
        loadStatus();
      } else {
        toast.error(res.data.message);
      }
    } catch (err) {
      toast.error(err.response?.data?.detail || 'Error guardando credenciales');
    } finally {
      setSaving(false);
    }
  };

  const handleDisconnect = async () => {
    if (!window.confirm('¿Desconectar Contalink? Se eliminarán las credenciales guardadas.')) return;
    try {
      await api.delete('/contalink/credentials');
      toast.success('Contalink desconectado');
      loadStatus();
    } catch {
      toast.error('Error desconectando');
    }
  };

  // Sync individual buttons — same pattern as Alegra
  const syncButtons = [
    {
      key: 'cxc',
      label: 'Facturas (CxC)',
      description: 'Facturas emitidas — ingresos',
      icon: FileText,
      color: 'text-green-600',
      bg: 'hover:bg-green-50 border-green-200',
      params: { transaction_type: 'issued', document_type: 'I' }
    },
    {
      key: 'cxp',
      label: 'Facturas (CxP)',
      description: 'Facturas recibidas — gastos',
      icon: FileText,
      color: 'text-red-600',
      bg: 'hover:bg-red-50 border-red-200',
      params: { transaction_type: 'received', document_type: 'I' }
    },
    {
      key: 'complementos',
      label: 'Complementos Pago',
      description: 'Documentos tipo P',
      icon: CreditCard,
      color: 'text-blue-600',
      bg: 'hover:bg-blue-50 border-blue-200',
      params: { transaction_type: 'received', document_type: 'P' }
    },
  ];

  const handleSync = async (btn) => {
    setSyncingKey(btn.key);
    try {
      const days = getDaysBack();
      const res = await api.post(
        `/contalink/sync/invoices?transaction_type=${btn.params.transaction_type}&document_type=${btn.params.document_type}&days_back=${days}`
      );
      setSyncResults(prev => ({ ...prev, [btn.key]: res.data }));
      toast.success(`${btn.label}: ${res.data.created} nuevas, ${res.data.updated} actualizadas`);
      loadStatus();
    } catch (err) {
      toast.error(err.response?.data?.detail || `Error sincronizando ${btn.label}`);
    } finally {
      setSyncingKey(null);
    }
  };

  const handleSyncAll = async () => {
    setSyncingKey('all');
    setSyncResults({});
    try {
      const days = getDaysBack();
      const res = await api.post(`/contalink/sync/all?days_back=${days}`);
      toast.success(res.data.message);
      loadStatus();
    } catch (err) {
      toast.error(err.response?.data?.detail || 'Error en sincronización');
    } finally {
      setSyncingKey(null);
    }
  };

  const handleGetTrialBalance = async () => {
    setLoadingBalance(true);
    try {
      const res = await api.get(
        `/contalink/trial-balance?start_date=${balanceDates.start_date}&end_date=${balanceDates.end_date}&period=exclude`
      );
      setTrialBalance(res.data);
      toast.success('Balanza obtenida');
    } catch (err) {
      toast.error(err.response?.data?.detail || 'Error obteniendo balanza');
    } finally {
      setLoadingBalance(false);
    }
  };

  if (loading) return <div className="p-8">Cargando...</div>;

  return (
    <div className="space-y-6 p-6">
      {/* Header */}
      <div className="flex items-center gap-3">
        <div className="p-2 bg-blue-600 rounded-lg">
          <Link2 className="text-white" size={24} />
        </div>
        <div>
          <h2 className="text-2xl font-bold text-gray-900">Integración Contalink</h2>
          <p className="text-gray-500 text-sm">Sincroniza facturas, movimientos bancarios y balanza contable</p>
        </div>
        <div className="ml-auto flex items-center gap-2">
          {status?.connected ? (
            <>
              <span className="flex items-center gap-2 text-green-600 bg-green-50 px-3 py-1 rounded-full text-sm">
                <CheckCircle2 size={16} /> Conectado · {status.rfc}
              </span>
              <Button
                variant="ghost"
                size="sm"
                className="text-red-500 hover:bg-red-50"
                onClick={handleDisconnect}
                title="Desconectar"
              >
                <Trash2 size={16} />
              </Button>
            </>
          ) : (
            <span className="flex items-center gap-2 text-red-600 bg-red-50 px-3 py-1 rounded-full text-sm">
              <XCircle size={16} /> No conectado
            </span>
          )}
        </div>
      </div>

      {/* Credentials */}
      <Card>
        <CardHeader>
          <CardTitle className="flex items-center gap-2 text-base">
            <Link2 size={16} /> Credenciales API
          </CardTitle>
          <CardDescription>
            Ingresa tu API Key de Contalink. La encuentras en tu cuenta → Configuración → API.
          </CardDescription>
        </CardHeader>
        <CardContent className="space-y-4">
          <div className="grid grid-cols-2 gap-4">
            <div className="space-y-2">
              <Label>RFC de la empresa</Label>
              <Input
                placeholder="Ej. ABC123456789"
                value={credentials.rfc}
                onChange={(e) => setCredentials({ ...credentials, rfc: e.target.value.toUpperCase() })}
              />
            </div>
            <div className="space-y-2">
              <Label>API Key</Label>
              <Input
                type="password"
                placeholder="Tu API Key de Contalink"
                value={credentials.api_key}
                onChange={(e) => setCredentials({ ...credentials, api_key: e.target.value })}
              />
            </div>
          </div>
          <div className="flex gap-3">
            <Button variant="outline" onClick={handleTestConnection} disabled={testing}>
              {testing
                ? <RefreshCw size={16} className="animate-spin mr-2" />
                : <CheckCircle2 size={16} className="mr-2" />}
              Probar conexión
            </Button>
            <Button onClick={handleSaveCredentials} disabled={saving} className="bg-blue-600 hover:bg-blue-700">
              {saving ? 'Guardando...' : 'Guardar credenciales'}
            </Button>
          </div>
          {status?.last_sync && (
            <p className="text-xs text-gray-500">
              Última sincronización: {format(new Date(status.last_sync), 'dd/MM/yyyy HH:mm')} · {status.last_sync_type}
            </p>
          )}
        </CardContent>
      </Card>

      {/* Sync Section */}
      {status?.connected && (
        <Card>
          <CardHeader>
            <CardTitle className="flex items-center gap-2 text-base">
              <RefreshCw size={16} /> Sincronizar Facturas / CFDIs
            </CardTitle>
            <CardDescription>
              Importa facturas desde Contalink a TaxnFin
            </CardDescription>
          </CardHeader>
          <CardContent className="space-y-5">

            {/* Date Range — igual que Alegra */}
            <div className="p-3 bg-gray-50 rounded-lg border">
              <Label className="text-xs text-gray-500 mb-2 block">Rango de fechas (opcional)</Label>
              <div className="grid grid-cols-2 gap-3">
                <div>
                  <Label className="text-xs">Desde</Label>
                  <Input
                    type="date"
                    value={dateFrom}
                    onChange={(e) => setDateFrom(e.target.value)}
                    className="mt-1"
                  />
                </div>
                <div>
                  <Label className="text-xs">Hasta</Label>
                  <Input
                    type="date"
                    value={dateTo}
                    onChange={(e) => setDateTo(e.target.value)}
                    className="mt-1"
                  />
                </div>
              </div>
              {!dateFrom && (
                <p className="text-xs text-gray-400 mt-2">Sin fechas: sincroniza últimos 90 días</p>
              )}
            </div>

            {/* Individual sync buttons — igual que Alegra */}
            <div className="grid grid-cols-3 gap-3">
              {syncButtons.map(btn => {
                const Icon = btn.icon;
                const result = syncResults[btn.key];
                const isSyncing = syncingKey === btn.key;
                return (
                  <div key={btn.key} className="space-y-2">
                    <button
                      onClick={() => handleSync(btn)}
                      disabled={!!syncingKey}
                      className={`w-full flex items-center gap-3 p-3 border rounded-lg text-left transition-colors ${btn.bg} disabled:opacity-50 disabled:cursor-not-allowed bg-white`}
                    >
                      {isSyncing
                        ? <RefreshCw size={20} className={`${btn.color} animate-spin shrink-0`} />
                        : <Icon size={20} className={`${btn.color} shrink-0`} />
                      }
                      <div>
                        <p className={`text-sm font-medium ${btn.color}`}>{btn.label}</p>
                        <p className="text-xs text-gray-400">{btn.description}</p>
                      </div>
                    </button>
                    {result && (
                      <div className="text-xs text-center text-gray-500 bg-gray-50 rounded px-2 py-1">
                        +{result.created} nuevas · {result.updated} act.
                        {result.errors > 0 && <span className="text-red-500"> · {result.errors} err</span>}
                      </div>
                    )}
                  </div>
                );
              })}
            </div>

            {/* Sync All button */}
            <Button
              onClick={handleSyncAll}
              disabled={!!syncingKey}
              className="w-full bg-blue-600 hover:bg-blue-700"
            >
              {syncingKey === 'all'
                ? <><RefreshCw size={16} className="animate-spin mr-2" />Sincronizando...</>
                : <><RefreshCw size={16} className="mr-2" />Sincronizar Todo</>
              }
            </Button>
          </CardContent>
        </Card>
      )}

      {/* Trial Balance */}
      {status?.connected && (
        <Card>
          <CardHeader>
            <CardTitle className="flex items-center gap-2 text-base">
              <TrendingUp size={16} /> Balanza de Comprobación
            </CardTitle>
            <CardDescription>
              Consulta la balanza contable directamente desde Contalink
            </CardDescription>
          </CardHeader>
          <CardContent className="space-y-4">
            <div className="grid grid-cols-2 gap-4">
              <div className="space-y-2">
                <Label>Fecha inicial</Label>
                <Input
                  type="date"
                  value={balanceDates.start_date}
                  onChange={(e) => setBalanceDates({ ...balanceDates, start_date: e.target.value })}
                />
              </div>
              <div className="space-y-2">
                <Label>Fecha final</Label>
                <Input
                  type="date"
                  value={balanceDates.end_date}
                  onChange={(e) => setBalanceDates({ ...balanceDates, end_date: e.target.value })}
                />
              </div>
            </div>
            <Button variant="outline" onClick={handleGetTrialBalance} disabled={loadingBalance}>
              {loadingBalance
                ? <><RefreshCw size={16} className="animate-spin mr-2" />Consultando...</>
                : <><TrendingUp size={16} className="mr-2" />Obtener Balanza</>
              }
            </Button>
            {trialBalance?.data && (
              <div className="p-3 bg-gray-50 rounded border text-sm">
                <p className="font-medium text-gray-700 mb-2">
                  Balanza {balanceDates.start_date} → {balanceDates.end_date}
                </p>
                <pre className="text-xs text-gray-600 max-h-48 overflow-y-auto">
                  {JSON.stringify(trialBalance.data, null, 2)}
                </pre>
              </div>
            )}
          </CardContent>
        </Card>
      )}

      {/* Info */}
      <Card className="border-blue-200 bg-blue-50">
        <CardContent className="pt-4">
          <div className="flex gap-3">
            <AlertCircle size={18} className="text-blue-600 mt-0.5 shrink-0" />
            <div className="text-sm text-blue-800">
              <p className="font-medium mb-1">¿Cómo obtener tu API Key de Contalink?</p>
              <ol className="list-decimal list-inside space-y-1 text-blue-700">
                <li>Contacta a tu ejecutivo de Contalink o escribe al chat de soporte</li>
                <li>Solicita la activación de la API para tu empresa (RFC)</li>
                <li>Recibirás el API Key por correo</li>
                <li>Ingresa el API Key y RFC aquí y guarda las credenciales</li>
              </ol>
              <p className="mt-2 text-xs">
                Documentación técnica:{' '}
                <a href="https://apidocs.contalink.com" target="_blank" rel="noreferrer" className="underline">
                  apidocs.contalink.com
                </a>
              </p>
            </div>
          </div>
        </CardContent>
      </Card>
    </div>
  );
};

export default ContalinkIntegration;
