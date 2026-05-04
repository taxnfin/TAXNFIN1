import React, { useState, useEffect, useCallback } from 'react';
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '../components/ui/card';
import { Button } from '../components/ui/button';
import { Input } from '../components/ui/input';
import { Label } from '../components/ui/label';
import { Dialog, DialogContent, DialogDescription, DialogHeader, DialogTitle, DialogTrigger, DialogFooter } from '../components/ui/dialog';
import { Alert, AlertDescription } from '../components/ui/alert';
import { Badge } from '../components/ui/badge';
import api from '../api/axios';
import { toast } from 'sonner';
import { 
  Cloud, 
  CloudOff,
  RefreshCw, 
  Settings, 
  Check, 
  X,
  Users,
  FileText,
  CreditCard,
  Building2,
  Loader2,
  Unplug,
  CheckCircle,
  AlertCircle,
  Trash2,
  Calendar
} from 'lucide-react';

export default function AlegraIntegration() {
  const [status, setStatus] = useState(null);
  const [loading, setLoading] = useState(true);
  const [configDialogOpen, setConfigDialogOpen] = useState(false);
  const [syncDialogOpen, setSyncDialogOpen] = useState(false);
  const [clearDataDialogOpen, setClearDataDialogOpen] = useState(false);
  const [syncing, setSyncing] = useState(false);
  const [clearing, setClearing] = useState(false);
  const [syncResults, setSyncResults] = useState(null);
  const [credentials, setCredentials] = useState({ email: '', token: '' });
  const [testingConnection, setTestingConnection] = useState(false);
  const [savingCredentials, setSavingCredentials] = useState(false);
  const [disconnecting, setDisconnecting] = useState(false);
  const [syncDateFrom, setSyncDateFrom] = useState('');
  const [syncDateTo, setSyncDateTo] = useState('');

  const fetchStatus = useCallback(async () => {
    try {
      const response = await api.get('/alegra/status');
      setStatus(response.data);
    } catch (error) {
      console.error('Error fetching Alegra status:', error);
      setStatus({ connected: false });
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    fetchStatus();
  }, [fetchStatus]);

  const testConnection = async () => {
    if (!credentials.email || !credentials.token) {
      toast.error('Ingresa el email y token de Alegra');
      return;
    }
    setTestingConnection(true);
    try {
      const response = await api.post('/alegra/test-connection', credentials);
      if (response.data.success) {
        toast.success('Conexión exitosa con Alegra');
      } else {
        toast.error(response.data.message || 'Error de conexión');
      }
    } catch (error) {
      toast.error('Error probando conexión: ' + (error.response?.data?.detail || error.message));
    } finally {
      setTestingConnection(false);
    }
  };

  const saveCredentials = async () => {
    if (!credentials.email || !credentials.token) {
      toast.error('Ingresa el email y token de Alegra');
      return;
    }
    setSavingCredentials(true);
    try {
      await api.post('/alegra/save-credentials', credentials);
      toast.success('Credenciales guardadas exitosamente');
      setConfigDialogOpen(false);
      fetchStatus();
    } catch (error) {
      toast.error('Error guardando credenciales: ' + (error.response?.data?.detail || error.message));
    } finally {
      setSavingCredentials(false);
    }
  };

  const disconnect = async () => {
    if (!window.confirm('¿Estás seguro de desconectar Alegra?')) return;
    setDisconnecting(true);
    try {
      await api.delete('/alegra/disconnect');
      toast.success('Alegra desconectado');
      fetchStatus();
    } catch (error) {
      toast.error('Error desconectando: ' + (error.response?.data?.detail || error.message));
    } finally {
      setDisconnecting(false);
    }
  };

  const clearAlegraData = async () => {
    setClearing(true);
    try {
      const response = await api.delete('/alegra/clear-data');
      toast.success(response.data.message || 'Datos de Alegra eliminados');
      setClearDataDialogOpen(false);
      fetchStatus();
    } catch (error) {
      toast.error('Error eliminando datos: ' + (error.response?.data?.detail || error.message));
    } finally {
      setClearing(false);
    }
  };

  const syncAll = async () => {
    setSyncing(true);
    setSyncResults(null);
    try {
      // Build URL with date params if provided
      let url = '/alegra/sync/all';
      const params = new URLSearchParams();
      if (syncDateFrom) params.append('date_from', syncDateFrom);
      if (syncDateTo) params.append('date_to', syncDateTo);
      if (params.toString()) url += '?' + params.toString();
      
      const response = await api.post(url);
      setSyncResults(response.data.results);
      
      // Check if any sync had errors
      const hasErrors = Object.values(response.data.results || {}).some(r => r.error);
      if (hasErrors) {
        toast.warning('Sincronización parcial: algunos elementos tuvieron errores temporales de Alegra');
      } else {
        toast.success('Sincronización completada');
      }
      fetchStatus();
    } catch (error) {
      const errorMsg = error.response?.data?.detail || error.message;
      if (errorMsg.includes('500') || errorMsg.includes('error')) {
        toast.error('Alegra está experimentando problemas temporales. Intenta de nuevo en unos minutos.');
      } else {
        toast.error('Error en sincronización: ' + errorMsg);
      }
    } finally {
      setSyncing(false);
    }
  };

  const syncEntity = async (entity) => {
    setSyncing(true);
    try {
      // Build URL with date params if provided
      // Contacts don't support date filtering in Alegra API
      let url = `/alegra/sync/${entity}`;
      const params = new URLSearchParams();
      if (entity !== 'contacts') {
        if (syncDateFrom) params.append('date_from', syncDateFrom);
        if (syncDateTo) params.append('date_to', syncDateTo);
      }
      if (params.toString()) url += '?' + params.toString();
      
      const response = await api.post(url);
      const stats = response.data.stats || {};
      if (stats.error) {
        toast.warning(`${entity}: Error temporal de Alegra. Intenta de nuevo.`);
      } else {
        toast.success(`${entity} sincronizados: ${stats.created || 0} nuevos, ${stats.updated || 0} actualizados`);
      }
      fetchStatus();
    } catch (error) {
      const errorMsg = error.response?.data?.detail || error.message;
      if (errorMsg.includes('500') || errorMsg.includes('error')) {
        toast.error(`Alegra está experimentando problemas temporales. Intenta de nuevo en unos minutos.`);
      } else {
        toast.error('Error sincronizando ' + entity + ': ' + errorMsg);
      }
    } finally {
      setSyncing(false);
    }
  };

  if (loading) {
    return (
      <Card className="border-purple-200 bg-gradient-to-br from-purple-50 to-white">
        <CardContent className="flex items-center justify-center py-8">
          <Loader2 className="h-6 w-6 animate-spin text-purple-600" />
          <span className="ml-2 text-purple-600">Cargando estado de Alegra...</span>
        </CardContent>
      </Card>
    );
  }

  return (
    <Card className="border-purple-200 bg-gradient-to-br from-purple-50 to-white" data-testid="alegra-integration-card">
      <CardHeader className="pb-3">
        <div className="flex items-center justify-between">
          <div className="flex items-center gap-3">
            <div className="h-10 w-10 rounded-lg bg-purple-600 flex items-center justify-center">
              <Cloud className="h-5 w-5 text-white" />
            </div>
            <div>
              <CardTitle className="text-lg">Integración Alegra</CardTitle>
              <CardDescription className="text-sm">
                Sincroniza clientes, proveedores, facturas y pagos
              </CardDescription>
            </div>
          </div>
          <Badge 
            variant={status?.connected ? "default" : "secondary"}
            className={status?.connected ? "bg-green-500" : "bg-gray-400"}
          >
            {status?.connected ? (
              <>
                <CheckCircle className="h-3 w-3 mr-1" />
                Conectado
              </>
            ) : (
              <>
                <CloudOff className="h-3 w-3 mr-1" />
                No configurado
              </>
            )}
          </Badge>
        </div>
      </CardHeader>
      <CardContent>
        {status?.connected ? (
          <div className="space-y-4">
            {/* Connection Info */}
            <div className="bg-white rounded-lg p-3 border border-purple-100">
              <div className="flex items-center justify-between text-sm">
                <span className="text-gray-600">Email conectado:</span>
                <span className="font-medium">{status.email}</span>
              </div>
              {status.last_sync && (
                <div className="flex items-center justify-between text-sm mt-1">
                  <span className="text-gray-600">Última sincronización:</span>
                  <span className="font-medium">
                    {new Date(status.last_sync).toLocaleString('es-MX')}
                  </span>
                </div>
              )}
            </div>

            {/* Sync Date Range */}
            <div className="bg-white rounded-lg p-3 border border-purple-100">
              <div className="text-xs font-medium text-gray-600 mb-2 flex items-center gap-1">
                <Calendar className="h-3 w-3" />
                Rango de fechas (opcional)
              </div>
              <div className="grid grid-cols-2 gap-2">
                <div>
                  <Label className="text-xs text-gray-500">Desde</Label>
                  <Input
                    type="date"
                    value={syncDateFrom}
                    onChange={(e) => setSyncDateFrom(e.target.value)}
                    className="h-8 text-sm"
                    data-testid="sync-date-from"
                  />
                </div>
                <div>
                  <Label className="text-xs text-gray-500">Hasta</Label>
                  <Input
                    type="date"
                    value={syncDateTo}
                    onChange={(e) => setSyncDateTo(e.target.value)}
                    className="h-8 text-sm"
                    data-testid="sync-date-to"
                  />
                </div>
              </div>
            </div>

            {/* Sync Buttons */}
            <div className="grid grid-cols-2 gap-2">
              <Button 
                variant="outline" 
                size="sm"
                onClick={() => syncEntity('contacts')}
                disabled={syncing}
                className="justify-start"
                data-testid="sync-contacts-btn"
              >
                <Users className="h-4 w-4 mr-2 text-blue-600" />
                Contactos
              </Button>
              <Button 
                variant="outline" 
                size="sm"
                onClick={() => syncEntity('invoices')}
                disabled={syncing}
                className="justify-start"
                data-testid="sync-invoices-btn"
              >
                <FileText className="h-4 w-4 mr-2 text-green-600" />
                Facturas (CxC)
              </Button>
              <Button 
                variant="outline" 
                size="sm"
                onClick={() => syncEntity('bills')}
                disabled={syncing}
                className="justify-start"
                data-testid="sync-bills-btn"
              >
                <Building2 className="h-4 w-4 mr-2 text-red-600" />
                Facturas (CxP)
              </Button>
              <Button 
                variant="outline" 
                size="sm"
                onClick={() => syncEntity('payments')}
                disabled={syncing}
                className="justify-start"
                data-testid="sync-payments-btn"
              >
                <CreditCard className="h-4 w-4 mr-2 text-purple-600" />
                Pagos
              </Button>
            </div>

            {/* Main Actions */}
            <div className="flex gap-2">
              <Button 
                className="flex-1 bg-purple-600 hover:bg-purple-700"
                onClick={() => setSyncDialogOpen(true)}
                disabled={syncing}
                data-testid="sync-all-btn"
              >
                {syncing ? (
                  <>
                    <Loader2 className="h-4 w-4 mr-2 animate-spin" />
                    Sincronizando...
                  </>
                ) : (
                  <>
                    <RefreshCw className="h-4 w-4 mr-2" />
                    Sincronizar Todo
                  </>
                )}
              </Button>
              <Button 
                variant="outline" 
                size="icon"
                onClick={() => setClearDataDialogOpen(true)}
                disabled={clearing}
                className="text-orange-600 hover:text-orange-700 hover:bg-orange-50"
                title="Limpiar datos de Alegra"
                data-testid="clear-alegra-data-btn"
              >
                {clearing ? (
                  <Loader2 className="h-4 w-4 animate-spin" />
                ) : (
                  <Trash2 className="h-4 w-4" />
                )}
              </Button>
              <Button 
                variant="outline" 
                size="icon"
                onClick={disconnect}
                disabled={disconnecting}
                className="text-red-600 hover:text-red-700 hover:bg-red-50"
                title="Desconectar Alegra"
              >
                {disconnecting ? (
                  <Loader2 className="h-4 w-4 animate-spin" />
                ) : (
                  <Unplug className="h-4 w-4" />
                )}
              </Button>
            </div>
          </div>
        ) : (
          <div className="space-y-4">
            <Alert>
              <AlertCircle className="h-4 w-4" />
              <AlertDescription>
                Conecta tu cuenta de Alegra para sincronizar automáticamente clientes, proveedores, facturas y pagos.
              </AlertDescription>
            </Alert>
            <Button 
              className="w-full bg-purple-600 hover:bg-purple-700"
              onClick={() => setConfigDialogOpen(true)}
              data-testid="configure-alegra-btn"
            >
              <Settings className="h-4 w-4 mr-2" />
              Configurar Alegra
            </Button>
          </div>
        )}

        {/* Config Dialog */}
        <Dialog open={configDialogOpen} onOpenChange={setConfigDialogOpen}>
          <DialogContent className="sm:max-w-md">
            <DialogHeader>
              <DialogTitle className="flex items-center gap-2">
                <Cloud className="h-5 w-5 text-purple-600" />
                Configurar Alegra
              </DialogTitle>
              <DialogDescription>
                Ingresa tus credenciales de API de Alegra. Las puedes obtener en 
                <a 
                  href="https://app.alegra.com/configuration/api-key" 
                  target="_blank" 
                  rel="noopener noreferrer"
                  className="text-purple-600 hover:underline ml-1"
                >
                  Configuración → API Key
                </a>
              </DialogDescription>
            </DialogHeader>
            <div className="space-y-4 py-4">
              <div className="space-y-2">
                <Label htmlFor="alegra-email">Email de Alegra</Label>
                <Input
                  id="alegra-email"
                  type="email"
                  placeholder="tu@email.com"
                  value={credentials.email}
                  onChange={(e) => setCredentials({ ...credentials, email: e.target.value })}
                  data-testid="alegra-email-input"
                />
              </div>
              <div className="space-y-2">
                <Label htmlFor="alegra-token">Token de API</Label>
                <Input
                  id="alegra-token"
                  type="password"
                  placeholder="••••••••••••••••••••"
                  value={credentials.token}
                  onChange={(e) => setCredentials({ ...credentials, token: e.target.value })}
                  data-testid="alegra-token-input"
                />
              </div>
            </div>
            <DialogFooter className="flex gap-2">
              <Button 
                variant="outline" 
                onClick={testConnection}
                disabled={testingConnection}
              >
                {testingConnection ? (
                  <Loader2 className="h-4 w-4 mr-2 animate-spin" />
                ) : (
                  <Check className="h-4 w-4 mr-2" />
                )}
                Probar Conexión
              </Button>
              <Button 
                className="bg-purple-600 hover:bg-purple-700"
                onClick={saveCredentials}
                disabled={savingCredentials}
                data-testid="save-alegra-btn"
              >
                {savingCredentials ? (
                  <Loader2 className="h-4 w-4 mr-2 animate-spin" />
                ) : (
                  <Cloud className="h-4 w-4 mr-2" />
                )}
                Guardar y Conectar
              </Button>
            </DialogFooter>
          </DialogContent>
        </Dialog>

        {/* Sync All Dialog */}
        <Dialog open={syncDialogOpen} onOpenChange={setSyncDialogOpen}>
          <DialogContent className="sm:max-w-lg">
            <DialogHeader>
              <DialogTitle className="flex items-center gap-2">
                <RefreshCw className="h-5 w-5 text-purple-600" />
                Sincronización Completa
              </DialogTitle>
              <DialogDescription>
                Se sincronizarán todos los datos desde Alegra: contactos, facturas de venta (CxC), facturas de compra (CxP) y movimientos bancarios.
              </DialogDescription>
            </DialogHeader>
            
            {syncResults ? (
              <div className="space-y-3 py-4">
                <h4 className="font-medium text-sm text-gray-700">Resultados de Sincronización:</h4>
                <div className="grid grid-cols-2 gap-3">
                  {Object.entries(syncResults).map(([key, stats]) => (
                    <div key={key} className="bg-gray-50 rounded-lg p-3 border">
                      <div className="font-medium text-sm capitalize mb-1">
                        {key === 'contacts' ? 'Contactos' : 
                         key === 'invoices' ? 'Facturas (CxC)' :
                         key === 'bills' ? 'Facturas (CxP)' :
                         key === 'payments' ? 'Pagos' : key}
                      </div>
                      {stats.error ? (
                        <span className="text-red-600 text-xs">{stats.error}</span>
                      ) : (
                        <div className="text-xs text-gray-600 space-y-0.5">
                          <div>Total: <span className="font-medium">{stats.total || 0}</span></div>
                          <div className="text-green-600">Nuevos: {stats.created || 0}</div>
                          <div className="text-blue-600">Actualizados: {stats.updated || 0}</div>
                          {stats.errors > 0 && (
                            <div className="text-red-600">Errores: {stats.errors}</div>
                          )}
                        </div>
                      )}
                    </div>
                  ))}
                </div>
                <Button 
                  className="w-full mt-4"
                  onClick={() => setSyncDialogOpen(false)}
                >
                  Cerrar
                </Button>
              </div>
            ) : (
              <DialogFooter className="flex gap-2 pt-4">
                <Button 
                  variant="outline" 
                  onClick={() => setSyncDialogOpen(false)}
                  disabled={syncing}
                >
                  Cancelar
                </Button>
                <Button 
                  className="bg-purple-600 hover:bg-purple-700"
                  onClick={syncAll}
                  disabled={syncing}
                  data-testid="confirm-sync-all-btn"
                >
                  {syncing ? (
                    <>
                      <Loader2 className="h-4 w-4 mr-2 animate-spin" />
                      Sincronizando...
                    </>
                  ) : (
                    <>
                      <RefreshCw className="h-4 w-4 mr-2" />
                      Iniciar Sincronización
                    </>
                  )}
                </Button>
              </DialogFooter>
            )}
          </DialogContent>
        </Dialog>

        {/* Clear Data Dialog */}
        <Dialog open={clearDataDialogOpen} onOpenChange={setClearDataDialogOpen}>
          <DialogContent className="sm:max-w-md">
            <DialogHeader>
              <DialogTitle className="flex items-center gap-2 text-orange-600">
                <Trash2 className="h-5 w-5" />
                Limpiar Datos de Alegra
              </DialogTitle>
              <DialogDescription>
                Esta acción eliminará todos los registros sincronizados desde Alegra (clientes, proveedores y pagos/facturas). 
                Los datos originales de Alegra no se modificarán. Podrás volver a sincronizar después.
              </DialogDescription>
            </DialogHeader>
            <Alert className="bg-orange-50 border-orange-200">
              <AlertCircle className="h-4 w-4 text-orange-600" />
              <AlertDescription className="text-orange-700">
                Esta acción no se puede deshacer. Se recomienda usarla cuando necesites reiniciar la sincronización desde cero.
              </AlertDescription>
            </Alert>
            <DialogFooter className="flex gap-2 pt-4">
              <Button 
                variant="outline" 
                onClick={() => setClearDataDialogOpen(false)}
                disabled={clearing}
              >
                Cancelar
              </Button>
              <Button 
                variant="destructive"
                onClick={clearAlegraData}
                disabled={clearing}
                data-testid="confirm-clear-alegra-btn"
              >
                {clearing ? (
                  <>
                    <Loader2 className="h-4 w-4 mr-2 animate-spin" />
                    Eliminando...
                  </>
                ) : (
                  <>
                    <Trash2 className="h-4 w-4 mr-2" />
                    Eliminar Datos
                  </>
                )}
              </Button>
            </DialogFooter>
          </DialogContent>
        </Dialog>
      </CardContent>
    </Card>
  );
}
