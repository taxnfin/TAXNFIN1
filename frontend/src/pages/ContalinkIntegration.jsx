import { useState, useEffect } from 'react';
import api from '@/api/axios';
import { Button } from '@/components/ui/button';
import { Input } from '@/components/ui/input';
import { Label } from '@/components/ui/label';
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card';
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from '@/components/ui/select';
import { toast } from 'sonner';
import { RefreshCw, CheckCircle2, XCircle, Link2, FileText, Building2, TrendingUp, TrendingDown, AlertCircle } from 'lucide-react';
import { format } from 'date-fns';

const ContalinkIntegration = () => {
  const [status, setStatus] = useState(null);
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);
  const [syncing, setSyncing] = useState(false);
  const [testing, setTesting] = useState(false);

  const [credentials, setCredentials] = useState({ api_key: '', rfc: '' });
  const [syncConfig, setSyncConfig] = useState({
    days_back: '90',
    transaction_type: 'received',
    document_type: 'I',
  });
  const [syncResult, setSyncResult] = useState(null);
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
    } catch (err) {
      setStatus({ connected: false });
    } finally {
      setLoading(false);
    }
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
    } catch (err) {
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

  const handleSyncInvoices = async () => {
    setSyncing(true);
    setSyncResult(null);
    try {
      const res = await api.post(
        `/contalink/sync/invoices?transaction_type=${syncConfig.transaction_type}&document_type=${syncConfig.document_type}&days_back=${syncConfig.days_back}`
      );
      setSyncResult(res.data);
      toast.success(res.data.message);
    } catch (err) {
      toast.error(err.response?.data?.detail || 'Error sincronizando');
    } finally {
      setSyncing(false);
    }
  };

  const handleSyncAll = async () => {
    setSyncing(true);
    setSyncResult(null);
    try {
      const res = await api.post(`/contalink/sync/all?days_back=${syncConfig.days_back}`);
      setSyncResult(res.data);
      toast.success(res.data.message);
      loadStatus();
    } catch (err) {
      toast.error(err.response?.data?.detail || 'Error en sincronización');
    } finally {
      setSyncing(false);
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
          <Building2 className="text-white" size={24} />
        </div>
        <div>
          <h2 className="text-2xl font-bold text-gray-900">Integración Contalink</h2>
          <p className="text-gray-500 text-sm">Sincroniza facturas, movimientos bancarios y balanza contable</p>
        </div>
        {status?.connected ? (
          <span className="ml-auto flex items-center gap-2 text-green-600 bg-green-50 px-3 py-1 rounded-full text-sm">
            <CheckCircle2 size={16} /> Conectado · {status.rfc}
          </span>
        ) : (
          <span className="ml-auto flex items-center gap-2 text-red-600 bg-red-50 px-3 py-1 rounded-full text-sm">
            <XCircle size={16} /> No conectado
          </span>
        )}
      </div>

      {/* Credentials */}
      <Card>
        <CardHeader>
          <CardTitle className="flex items-center gap-2">
            <Link2 size={18} /> Credenciales API
          </CardTitle>
          <CardDescription>
            Ingresa tu API Key de Contalink. La encuentras en tu cuenta de Contalink → Configuración → API.
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
              {testing ? <RefreshCw size={16} className="animate-spin mr-2" /> : <CheckCircle2 size={16} className="mr-2" />}
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

      {/* Sync Invoices */}
      {status?.connected && (
        <Card>
          <CardHeader>
            <CardTitle className="flex items-center gap-2">
              <FileText size={18} /> Sincronizar Facturas / CFDIs
            </CardTitle>
            <CardDescription>
              Importa facturas emitidas y recibidas desde Contalink a TaxnFin
            </CardDescription>
          </CardHeader>
          <CardContent className="space-y-4">
            <div className="grid grid-cols-3 gap-4">
              <div className="space-y-2">
                <Label>Días hacia atrás</Label>
                <Select value={syncConfig.days_back} onValueChange={(v) => setSyncConfig({ ...syncConfig, days_back: v })}>
                  <SelectTrigger><SelectValue /></SelectTrigger>
                  <SelectContent>
                    <SelectItem value="30">30 días</SelectItem>
                    <SelectItem value="60">60 días</SelectItem>
                    <SelectItem value="90">90 días</SelectItem>
                    <SelectItem value="180">6 meses</SelectItem>
                    <SelectItem value="365">1 año</SelectItem>
                  </SelectContent>
                </Select>
              </div>
              <div className="space-y-2">
                <Label>Tipo de transacción</Label>
                <Select value={syncConfig.transaction_type} onValueChange={(v) => setSyncConfig({ ...syncConfig, transaction_type: v })}>
                  <SelectTrigger><SelectValue /></SelectTrigger>
                  <SelectContent>
                    <SelectItem value="received">Recibidas (Gastos)</SelectItem>
                    <SelectItem value="issued">Emitidas (Ingresos)</SelectItem>
                  </SelectContent>
                </Select>
              </div>
              <div className="space-y-2">
                <Label>Tipo de documento</Label>
                <Select value={syncConfig.document_type} onValueChange={(v) => setSyncConfig({ ...syncConfig, document_type: v })}>
                  <SelectTrigger><SelectValue /></SelectTrigger>
                  <SelectContent>
                    <SelectItem value="I">Ingreso (I)</SelectItem>
                    <SelectItem value="E">Egreso (E)</SelectItem>
                    <SelectItem value="P">Complemento Pago (P)</SelectItem>
                    <SelectItem value="N">Nómina (N)</SelectItem>
                  </SelectContent>
                </Select>
              </div>
            </div>
            <div className="flex gap-3">
              <Button variant="outline" onClick={handleSyncInvoices} disabled={syncing}>
                {syncing ? <RefreshCw size={16} className="animate-spin mr-2" /> : <FileText size={16} className="mr-2" />}
                Sincronizar selección
              </Button>
              <Button onClick={handleSyncAll} disabled={syncing} className="bg-blue-600 hover:bg-blue-700">
                {syncing ? <RefreshCw size={16} className="animate-spin mr-2" /> : <RefreshCw size={16} className="mr-2" />}
                Sincronizar todo (emitidas + recibidas)
              </Button>
            </div>

            {/* Sync Result */}
            {syncResult && (
              <div className={`p-4 rounded-lg border ${syncResult.success ? 'bg-green-50 border-green-200' : 'bg-red-50 border-red-200'}`}>
                <p className={`font-medium ${syncResult.success ? 'text-green-800' : 'text-red-800'}`}>
                  {syncResult.message}
                </p>
                <div className="grid grid-cols-3 gap-4 mt-3">
                  <div className="text-center">
                    <div className="text-2xl font-bold text-green-600">{syncResult.total_created ?? syncResult.created}</div>
                    <div className="text-xs text-gray-500">Nuevas</div>
                  </div>
                  <div className="text-center">
                    <div className="text-2xl font-bold text-blue-600">{syncResult.total_updated ?? syncResult.updated}</div>
                    <div className="text-xs text-gray-500">Actualizadas</div>
                  </div>
                  <div className="text-center">
                    <div className="text-2xl font-bold text-red-600">{syncResult.total_errors ?? syncResult.errors}</div>
                    <div className="text-xs text-gray-500">Errores</div>
                  </div>
                </div>
              </div>
            )}
          </CardContent>
        </Card>
      )}

      {/* Trial Balance */}
      {status?.connected && (
        <Card>
          <CardHeader>
            <CardTitle className="flex items-center gap-2">
              <TrendingUp size={18} /> Balanza de Comprobación
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
                <pre className="text-xs text-gray-600 max-h-40 overflow-y-auto">
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
              <p className="mt-2 text-xs">Documentación técnica: <a href="https://apidocs.contalink.com" target="_blank" rel="noreferrer" className="underline">apidocs.contalink.com</a></p>
            </div>
          </div>
        </CardContent>
      </Card>
    </div>
  );
};

export default ContalinkIntegration;
