import { useState, useEffect } from 'react';
import api from '@/api/axios';
import { Button } from '@/components/ui/button';
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card';
import { Dialog, DialogContent, DialogDescription, DialogFooter, DialogHeader, DialogTitle } from '@/components/ui/dialog';
import { Label } from '@/components/ui/label';
import { Input } from '@/components/ui/input';
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from '@/components/ui/select';
import { toast } from 'sonner';
import { Cloud, Key, RefreshCw, CheckCircle2, XCircle, Clock, Loader2, Download, Calendar, Trash2, History, AlertCircle, Shield } from 'lucide-react';
import { format, subDays } from 'date-fns';
import { es } from 'date-fns/locale';
import { Checkbox } from '@/components/ui/checkbox';
import {
  AlertDialog,
  AlertDialogAction,
  AlertDialogCancel,
  AlertDialogContent,
  AlertDialogDescription,
  AlertDialogFooter,
  AlertDialogHeader,
  AlertDialogTitle,
} from "@/components/ui/alert-dialog";

const SATIntegration = ({ onSyncComplete }) => {
  const [satStatus, setSatStatus] = useState(null);
  const [loading, setLoading] = useState(true);
  const [configDialogOpen, setConfigDialogOpen] = useState(false);
  const [syncDialogOpen, setSyncDialogOpen] = useState(false);
  const [deleteDialogOpen, setDeleteDialogOpen] = useState(false);
  const [historyDialogOpen, setHistoryDialogOpen] = useState(false);
  const [syncHistory, setSyncHistory] = useState([]);
  
  // Form states
  const [credentials, setCredentials] = useState({ rfc: '', ciec: '' });
  const [savingCredentials, setSavingCredentials] = useState(false);
  const [testingConnection, setTestingConnection] = useState(false);
  
  // Sync form
  const [syncConfig, setSyncConfig] = useState({
    fecha_inicio: format(subDays(new Date(), 30), 'yyyy-MM-dd'),
    fecha_fin: format(new Date(), 'yyyy-MM-dd'),
    tipo_comprobante: 'todos',
    incluir_emitidos: true,
    incluir_recibidos: true
  });
  const [syncing, setSyncing] = useState(false);
  const [syncResult, setSyncResult] = useState(null);

  const tiposComprobante = [
    { value: 'todos', label: 'Todos los tipos' },
    { value: 'ingreso', label: 'Ingreso (I)' },
    { value: 'egreso', label: 'Egreso (E)' },
    { value: 'pago', label: 'Pago (P)' },
    { value: 'nomina', label: 'Nómina (N)' },
    { value: 'traslado', label: 'Traslado (T)' }
  ];

  useEffect(() => {
    loadSATStatus();
  }, []);

  const loadSATStatus = async () => {
    try {
      const response = await api.get('/sat/status');
      setSatStatus(response.data);
    } catch (error) {
      console.error('Error loading SAT status:', error);
      setSatStatus({ configured: false });
    } finally {
      setLoading(false);
    }
  };

  const loadSyncHistory = async () => {
    try {
      const response = await api.get('/sat/sync/history?limit=10');
      setSyncHistory(response.data);
    } catch (error) {
      console.error('Error loading sync history:', error);
    }
  };

  const handleSaveCredentials = async () => {
    if (!credentials.rfc || !credentials.ciec) {
      toast.error('Por favor ingrese RFC y CIEC');
      return;
    }

    if (credentials.rfc.length < 12 || credentials.rfc.length > 13) {
      toast.error('RFC inválido. Debe tener 12 o 13 caracteres.');
      return;
    }

    if (credentials.ciec.length < 8) {
      toast.error('CIEC inválida. Debe tener al menos 8 caracteres.');
      return;
    }

    setSavingCredentials(true);
    try {
      await api.post('/sat/credentials', {
        rfc: credentials.rfc.toUpperCase(),
        ciec: credentials.ciec
      });
      toast.success('Credenciales SAT guardadas correctamente');
      setConfigDialogOpen(false);
      setCredentials({ rfc: '', ciec: '' });
      loadSATStatus();
    } catch (error) {
      toast.error(error.response?.data?.detail || 'Error guardando credenciales');
    } finally {
      setSavingCredentials(false);
    }
  };

  const handleTestConnection = async () => {
    setTestingConnection(true);
    try {
      const response = await api.post('/sat/test-connection');
      if (response.data.success) {
        toast.success('¡Conexión exitosa con el SAT!');
        loadSATStatus();
      } else {
        // Check if it's a Chrome missing error
        if (response.data.chrome_missing) {
          toast.warning('Credenciales guardadas. La prueba de conexión requiere Chrome en el servidor.', {
            duration: 5000
          });
        } else {
          toast.error(response.data.error || 'Error de conexión con SAT');
        }
      }
    } catch (error) {
      const errorMsg = error.response?.data?.detail || 'Error probando conexión';
      // Check for Chrome/browser related errors
      if (errorMsg.toLowerCase().includes('chrome') || errorMsg.toLowerCase().includes('navegador')) {
        toast.warning('Credenciales guardadas. La conexión al SAT no está disponible en este servidor.', {
          duration: 5000
        });
      } else {
        toast.error(errorMsg);
      }
    } finally {
      setTestingConnection(false);
    }
  };

  const handleDeleteCredentials = async () => {
    try {
      await api.delete('/sat/credentials');
      toast.success('Credenciales SAT eliminadas');
      setDeleteDialogOpen(false);
      loadSATStatus();
    } catch (error) {
      toast.error(error.response?.data?.detail || 'Error eliminando credenciales');
    }
  };

  const handleSync = async () => {
    // Validate date range
    const dateStart = new Date(syncConfig.fecha_inicio);
    const dateEnd = new Date(syncConfig.fecha_fin);
    const daysDiff = Math.ceil((dateEnd - dateStart) / (1000 * 60 * 60 * 24));

    if (daysDiff > 31) {
      toast.error('El rango de fechas no puede exceder 31 días');
      return;
    }

    if (dateEnd < dateStart) {
      toast.error('La fecha final debe ser posterior a la fecha inicial');
      return;
    }

    if (!syncConfig.incluir_emitidos && !syncConfig.incluir_recibidos) {
      toast.error('Debe seleccionar al menos un tipo de CFDI (emitidos o recibidos)');
      return;
    }

    setSyncing(true);
    setSyncResult(null);

    try {
      const response = await api.post('/sat/sync', {
        fecha_inicio: syncConfig.fecha_inicio,
        fecha_fin: syncConfig.fecha_fin,
        tipo_comprobante: syncConfig.tipo_comprobante,
        incluir_emitidos: syncConfig.incluir_emitidos,
        incluir_recibidos: syncConfig.incluir_recibidos
      });

      setSyncResult(response.data);
      
      if (response.data.success) {
        const total = response.data.total_new || 0;
        if (total > 0) {
          toast.success(`¡Sincronización exitosa! ${total} CFDIs nuevos importados`);
          if (onSyncComplete) onSyncComplete();
        } else {
          toast.info('Sincronización completada. No se encontraron CFDIs nuevos.');
        }
        loadSATStatus();
      } else {
        toast.error(response.data.error || 'Error en sincronización');
      }
    } catch (error) {
      toast.error(error.response?.data?.detail || 'Error sincronizando con SAT');
      setSyncResult({ success: false, error: error.response?.data?.detail || 'Error desconocido' });
    } finally {
      setSyncing(false);
    }
  };

  const handleOpenHistory = () => {
    loadSyncHistory();
    setHistoryDialogOpen(true);
  };

  if (loading) {
    return (
      <Card className="border-[#E2E8F0]">
        <CardContent className="py-8 flex justify-center">
          <Loader2 className="animate-spin text-[#64748B]" />
        </CardContent>
      </Card>
    );
  }

  return (
    <>
      <Card className="border-[#3B82F6] bg-gradient-to-r from-blue-50 to-indigo-50" data-testid="sat-integration-card">
        <CardHeader>
          <CardTitle className="flex items-center gap-2 text-[#1E40AF]">
            <Cloud size={20} />
            Integración SAT
          </CardTitle>
          <CardDescription className="text-[#3B82F6]">
            Descarga automática de CFDIs desde el portal del SAT usando RFC + CIEC
          </CardDescription>
        </CardHeader>
        <CardContent>
          <div className="flex flex-wrap gap-4 items-center">
            {/* Status Indicator */}
            <div className="flex items-center gap-2 bg-white rounded-lg px-4 py-2 border">
              {satStatus?.configured ? (
                <>
                  <div className={`w-3 h-3 rounded-full ${satStatus?.status === 'active' ? 'bg-green-500' : satStatus?.status === 'error' ? 'bg-red-500' : 'bg-yellow-500'}`} />
                  <span className="text-sm font-medium text-[#1E293B]">
                    RFC: {satStatus?.rfc}
                  </span>
                  {satStatus?.last_sync && (
                    <span className="text-xs text-[#64748B]">
                      • Última sincronización: {format(new Date(satStatus.last_sync), 'dd/MM/yyyy HH:mm', { locale: es })}
                    </span>
                  )}
                </>
              ) : (
                <>
                  <XCircle size={16} className="text-[#DC2626]" />
                  <span className="text-sm text-[#64748B]">No configurado</span>
                </>
              )}
            </div>

            {/* Action Buttons */}
            <div className="flex gap-2 ml-auto">
              {satStatus?.configured ? (
                <>
                  <Button
                    variant="outline"
                    size="sm"
                    onClick={handleTestConnection}
                    disabled={testingConnection}
                    className="gap-1"
                    data-testid="test-sat-connection-btn"
                  >
                    {testingConnection ? <Loader2 size={14} className="animate-spin" /> : <RefreshCw size={14} />}
                    Probar conexión
                  </Button>
                  
                  <Button
                    variant="outline"
                    size="sm"
                    onClick={handleOpenHistory}
                    className="gap-1"
                    data-testid="sat-history-btn"
                  >
                    <History size={14} />
                    Historial
                  </Button>

                  <Button
                    size="sm"
                    onClick={() => setSyncDialogOpen(true)}
                    className="gap-1 bg-[#3B82F6] hover:bg-[#2563EB]"
                    data-testid="sync-sat-btn"
                  >
                    <Download size={14} />
                    Sincronizar CFDIs
                  </Button>

                  <Button
                    variant="ghost"
                    size="sm"
                    onClick={() => setConfigDialogOpen(true)}
                    className="gap-1 text-[#64748B]"
                    data-testid="edit-sat-credentials-btn"
                  >
                    <Key size={14} />
                    Editar
                  </Button>

                  <Button
                    variant="ghost"
                    size="sm"
                    onClick={() => setDeleteDialogOpen(true)}
                    className="gap-1 text-red-500 hover:text-red-700 hover:bg-red-50"
                    data-testid="delete-sat-credentials-btn"
                  >
                    <Trash2 size={14} />
                  </Button>
                </>
              ) : (
                <Button
                  onClick={() => setConfigDialogOpen(true)}
                  className="gap-2 bg-[#3B82F6] hover:bg-[#2563EB]"
                  data-testid="configure-sat-btn"
                >
                  <Key size={16} />
                  Configurar Credenciales SAT
                </Button>
              )}
            </div>
          </div>
        </CardContent>
      </Card>

      {/* Configure Credentials Dialog */}
      <Dialog open={configDialogOpen} onOpenChange={setConfigDialogOpen}>
        <DialogContent className="max-w-md">
          <DialogHeader>
            <DialogTitle className="flex items-center gap-2">
              <Shield size={20} className="text-[#3B82F6]" />
              Configurar Credenciales SAT
            </DialogTitle>
            <DialogDescription>
              Ingrese su RFC y CIEC para conectar con el portal del SAT.
              Las credenciales se almacenan de forma encriptada.
            </DialogDescription>
          </DialogHeader>

          <div className="space-y-4 py-4">
            <div className="space-y-2">
              <Label htmlFor="rfc">RFC</Label>
              <Input
                id="rfc"
                placeholder="Ej: XAXX010101000"
                value={credentials.rfc}
                onChange={(e) => setCredentials({ ...credentials, rfc: e.target.value.toUpperCase() })}
                maxLength={13}
                data-testid="sat-rfc-input"
              />
              <p className="text-xs text-[#64748B]">12 caracteres para persona moral, 13 para persona física</p>
            </div>

            <div className="space-y-2">
              <Label htmlFor="ciec">CIEC (Contraseña)</Label>
              <Input
                id="ciec"
                type="password"
                placeholder="••••••••"
                value={credentials.ciec}
                onChange={(e) => setCredentials({ ...credentials, ciec: e.target.value })}
                data-testid="sat-ciec-input"
              />
              <p className="text-xs text-[#64748B]">Mínimo 8 caracteres</p>
            </div>

            <div className="bg-amber-50 border border-amber-200 rounded-lg p-3">
              <div className="flex items-start gap-2">
                <AlertCircle size={16} className="text-amber-600 mt-0.5" />
                <div className="text-xs text-amber-800">
                  <p className="font-medium mb-1">Nota de seguridad:</p>
                  <ul className="list-disc list-inside space-y-1">
                    <li>Sus credenciales se almacenan encriptadas</li>
                    <li>Nunca compartimos sus datos con terceros</li>
                    <li>La CIEC es la contraseña de acceso al SAT</li>
                  </ul>
                </div>
              </div>
            </div>
          </div>

          <DialogFooter>
            <Button variant="outline" onClick={() => setConfigDialogOpen(false)}>
              Cancelar
            </Button>
            <Button 
              onClick={handleSaveCredentials} 
              disabled={savingCredentials}
              className="bg-[#3B82F6] hover:bg-[#2563EB]"
            >
              {savingCredentials ? <Loader2 size={16} className="animate-spin mr-2" /> : null}
              Guardar Credenciales
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>

      {/* Sync Dialog */}
      <Dialog open={syncDialogOpen} onOpenChange={setSyncDialogOpen}>
        <DialogContent className="max-w-lg">
          <DialogHeader>
            <DialogTitle className="flex items-center gap-2">
              <Download size={20} className="text-[#3B82F6]" />
              Sincronizar CFDIs desde SAT
            </DialogTitle>
            <DialogDescription>
              Configure los parámetros para descargar CFDIs del portal del SAT.
            </DialogDescription>
          </DialogHeader>

          <div className="space-y-4 py-4">
            {/* Date Range */}
            <div className="grid grid-cols-2 gap-4">
              <div className="space-y-2">
                <Label className="flex items-center gap-1">
                  <Calendar size={14} />
                  Fecha inicio
                </Label>
                <Input
                  type="date"
                  value={syncConfig.fecha_inicio}
                  onChange={(e) => setSyncConfig({ ...syncConfig, fecha_inicio: e.target.value })}
                  data-testid="sync-date-start"
                />
              </div>
              <div className="space-y-2">
                <Label className="flex items-center gap-1">
                  <Calendar size={14} />
                  Fecha fin
                </Label>
                <Input
                  type="date"
                  value={syncConfig.fecha_fin}
                  onChange={(e) => setSyncConfig({ ...syncConfig, fecha_fin: e.target.value })}
                  max={format(new Date(), 'yyyy-MM-dd')}
                  data-testid="sync-date-end"
                />
              </div>
            </div>

            <p className="text-xs text-[#64748B]">
              Máximo 31 días por sincronización. Para períodos mayores, realice múltiples sincronizaciones.
            </p>

            {/* Tipo de Comprobante */}
            <div className="space-y-2">
              <Label>Tipo de comprobante</Label>
              <Select 
                value={syncConfig.tipo_comprobante} 
                onValueChange={(v) => setSyncConfig({ ...syncConfig, tipo_comprobante: v })}
              >
                <SelectTrigger data-testid="sync-tipo-select">
                  <SelectValue />
                </SelectTrigger>
                <SelectContent>
                  {tiposComprobante.map(t => (
                    <SelectItem key={t.value} value={t.value}>{t.label}</SelectItem>
                  ))}
                </SelectContent>
              </Select>
            </div>

            {/* Include Options */}
            <div className="space-y-3">
              <Label>Incluir:</Label>
              <div className="flex gap-6">
                <div className="flex items-center gap-2">
                  <Checkbox
                    id="incluir_recibidos"
                    checked={syncConfig.incluir_recibidos}
                    onCheckedChange={(c) => setSyncConfig({ ...syncConfig, incluir_recibidos: c })}
                  />
                  <Label htmlFor="incluir_recibidos" className="text-sm font-normal cursor-pointer">
                    CFDIs Recibidos (compras)
                  </Label>
                </div>
                <div className="flex items-center gap-2">
                  <Checkbox
                    id="incluir_emitidos"
                    checked={syncConfig.incluir_emitidos}
                    onCheckedChange={(c) => setSyncConfig({ ...syncConfig, incluir_emitidos: c })}
                  />
                  <Label htmlFor="incluir_emitidos" className="text-sm font-normal cursor-pointer">
                    CFDIs Emitidos (ventas)
                  </Label>
                </div>
              </div>
            </div>

            {/* Sync Result */}
            {syncResult && (
              <div className={`rounded-lg p-4 ${syncResult.success ? 'bg-green-50 border border-green-200' : 'bg-red-50 border border-red-200'}`}>
                {syncResult.success ? (
                  <div className="space-y-2">
                    <div className="flex items-center gap-2 text-green-700 font-medium">
                      <CheckCircle2 size={16} />
                      Sincronización completada
                    </div>
                    <div className="grid grid-cols-2 gap-2 text-sm">
                      <div>
                        <span className="text-[#64748B]">Recibidos descargados:</span>
                        <span className="ml-2 font-medium">{syncResult.recibidos?.downloaded || 0}</span>
                      </div>
                      <div>
                        <span className="text-[#64748B]">Recibidos nuevos:</span>
                        <span className="ml-2 font-medium text-green-600">{syncResult.recibidos?.new || 0}</span>
                      </div>
                      <div>
                        <span className="text-[#64748B]">Emitidos descargados:</span>
                        <span className="ml-2 font-medium">{syncResult.emitidos?.downloaded || 0}</span>
                      </div>
                      <div>
                        <span className="text-[#64748B]">Emitidos nuevos:</span>
                        <span className="ml-2 font-medium text-green-600">{syncResult.emitidos?.new || 0}</span>
                      </div>
                    </div>
                    <div className="pt-2 border-t border-green-200">
                      <span className="text-green-700 font-medium">
                        Total nuevos: {syncResult.total_new || 0}
                      </span>
                    </div>
                  </div>
                ) : (
                  <div className="flex items-center gap-2 text-red-700">
                    <XCircle size={16} />
                    <span>{syncResult.error || 'Error en sincronización'}</span>
                  </div>
                )}
              </div>
            )}
          </div>

          <DialogFooter>
            <Button variant="outline" onClick={() => setSyncDialogOpen(false)}>
              Cerrar
            </Button>
            <Button 
              onClick={handleSync} 
              disabled={syncing}
              className="bg-[#3B82F6] hover:bg-[#2563EB]"
            >
              {syncing ? (
                <>
                  <Loader2 size={16} className="animate-spin mr-2" />
                  Sincronizando...
                </>
              ) : (
                <>
                  <Download size={16} className="mr-2" />
                  Iniciar Sincronización
                </>
              )}
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>

      {/* History Dialog */}
      <Dialog open={historyDialogOpen} onOpenChange={setHistoryDialogOpen}>
        <DialogContent className="max-w-2xl">
          <DialogHeader>
            <DialogTitle className="flex items-center gap-2">
              <History size={20} className="text-[#3B82F6]" />
              Historial de Sincronizaciones
            </DialogTitle>
          </DialogHeader>

          <div className="max-h-96 overflow-y-auto">
            {syncHistory.length === 0 ? (
              <div className="text-center py-8 text-[#64748B]">
                No hay sincronizaciones registradas
              </div>
            ) : (
              <div className="space-y-3">
                {syncHistory.map((sync, idx) => (
                  <div key={idx} className="border rounded-lg p-3 bg-[#F8FAFC]">
                    <div className="flex justify-between items-start mb-2">
                      <div className="text-sm font-medium">
                        {format(new Date(sync.created_at), 'dd/MM/yyyy HH:mm', { locale: es })}
                      </div>
                      <div className={`px-2 py-0.5 rounded text-xs ${sync.result?.success ? 'bg-green-100 text-green-700' : 'bg-red-100 text-red-700'}`}>
                        {sync.result?.success ? 'Exitoso' : 'Error'}
                      </div>
                    </div>
                    <div className="text-xs text-[#64748B] space-y-1">
                      <div>Período: {sync.fecha_inicio} - {sync.fecha_fin}</div>
                      <div>Tipo: {sync.tipo_comprobante}</div>
                      {sync.result?.success && (
                        <div className="text-green-600">
                          Nuevos: {sync.result?.total_new || 0} | Actualizados: {sync.result?.total_updated || 0}
                        </div>
                      )}
                      {!sync.result?.success && sync.result?.error && (
                        <div className="text-red-600">{sync.result.error}</div>
                      )}
                    </div>
                  </div>
                ))}
              </div>
            )}
          </div>

          <DialogFooter>
            <Button variant="outline" onClick={() => setHistoryDialogOpen(false)}>
              Cerrar
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>

      {/* Delete Confirmation Dialog */}
      <AlertDialog open={deleteDialogOpen} onOpenChange={setDeleteDialogOpen}>
        <AlertDialogContent>
          <AlertDialogHeader>
            <AlertDialogTitle>¿Eliminar credenciales SAT?</AlertDialogTitle>
            <AlertDialogDescription>
              Esta acción eliminará las credenciales SAT guardadas. 
              Deberá volver a configurarlas para sincronizar CFDIs.
            </AlertDialogDescription>
          </AlertDialogHeader>
          <AlertDialogFooter>
            <AlertDialogCancel>Cancelar</AlertDialogCancel>
            <AlertDialogAction 
              onClick={handleDeleteCredentials}
              className="bg-red-600 hover:bg-red-700"
            >
              Eliminar
            </AlertDialogAction>
          </AlertDialogFooter>
        </AlertDialogContent>
      </AlertDialog>
    </>
  );
};

export default SATIntegration;
