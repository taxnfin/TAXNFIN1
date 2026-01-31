import { useState, useEffect, useRef } from 'react';
import api from '@/api/axios';
import { Button } from '@/components/ui/button';
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card';
import { Dialog, DialogContent, DialogDescription, DialogFooter, DialogHeader, DialogTitle } from '@/components/ui/dialog';
import { Label } from '@/components/ui/label';
import { Input } from '@/components/ui/input';
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from '@/components/ui/select';
import { toast } from 'sonner';
import { Cloud, Key, RefreshCw, CheckCircle2, XCircle, Loader2, Download, Calendar, Trash2, History, AlertCircle, Shield, FileKey, Upload, Clock, Package } from 'lucide-react';
import { format, subDays } from 'date-fns';
import { es } from 'date-fns/locale';
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
import { Badge } from '@/components/ui/badge';
import { Progress } from '@/components/ui/progress';

const SATIntegration = ({ onSyncComplete }) => {
  const [satStatus, setSatStatus] = useState(null);
  const [loading, setLoading] = useState(true);
  const [configDialogOpen, setConfigDialogOpen] = useState(false);
  const [syncDialogOpen, setSyncDialogOpen] = useState(false);
  const [deleteDialogOpen, setDeleteDialogOpen] = useState(false);
  const [requestsDialogOpen, setRequestsDialogOpen] = useState(false);
  const [downloadRequests, setDownloadRequests] = useState([]);
  
  // File refs
  const cerFileRef = useRef(null);
  const keyFileRef = useRef(null);
  
  // Form states
  const [cerFile, setCerFile] = useState(null);
  const [keyFile, setKeyFile] = useState(null);
  const [password, setPassword] = useState('');
  const [savingCredentials, setSavingCredentials] = useState(false);
  const [testingConnection, setTestingConnection] = useState(false);
  
  // Sync form
  const [syncConfig, setSyncConfig] = useState({
    fecha_inicio: format(new Date(), 'yyyy-MM-dd'),
    fecha_fin: format(new Date(), 'yyyy-MM-dd'),
    tipo_comprobante: 'todos',
    tipo_solicitud: 'CFDI'
  });
  const [syncing, setSyncing] = useState(false);
  const [syncResult, setSyncResult] = useState(null);
  const [checkingStatus, setCheckingStatus] = useState(null);

  const tiposComprobante = [
    { value: 'todos', label: 'Todos los tipos' },
    { value: 'I', label: 'Ingreso (I)' },
    { value: 'E', label: 'Egreso (E)' },
    { value: 'P', label: 'Pago (P)' },
    { value: 'N', label: 'Nómina (N)' },
    { value: 'T', label: 'Traslado (T)' }
  ];

  const tiposSolicitud = [
    { value: 'recibidos', label: 'CFDIs Recibidos (compras)' },
    { value: 'emitidos', label: 'CFDIs Emitidos (ventas)' }
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

  const loadDownloadRequests = async () => {
    try {
      const response = await api.get('/sat/requests?limit=20');
      setDownloadRequests(response.data);
    } catch (error) {
      console.error('Error loading requests:', error);
    }
  };

  const handleSaveFIEL = async () => {
    if (!cerFile || !keyFile || !password) {
      toast.error('Por favor seleccione los archivos .cer, .key e ingrese la contraseña');
      return;
    }

    setSavingCredentials(true);
    try {
      const formData = new FormData();
      formData.append('cer_file', cerFile);
      formData.append('key_file', keyFile);
      formData.append('password', password);

      const response = await api.post('/sat/fiel/upload', formData, {
        headers: { 'Content-Type': 'multipart/form-data' }
      });

      if (response.data.success) {
        toast.success(`FIEL guardada correctamente. RFC: ${response.data.rfc}`);
        setConfigDialogOpen(false);
        setCerFile(null);
        setKeyFile(null);
        setPassword('');
        loadSATStatus();
      } else {
        toast.error(response.data.error || 'Error guardando FIEL');
      }
    } catch (error) {
      toast.error(error.response?.data?.detail || 'Error guardando FIEL');
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
        toast.error(response.data.error || 'Error de conexión con SAT');
      }
    } catch (error) {
      toast.error(error.response?.data?.detail || 'Error probando conexión');
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

  const handleRequestDownload = async () => {
    setSyncing(true);
    setSyncResult(null);

    try {
      const response = await api.post('/sat/request-download', {
        fecha_inicio: syncConfig.fecha_inicio,
        fecha_fin: syncConfig.fecha_fin,
        tipo_comprobante: syncConfig.tipo_comprobante === 'todos' ? null : syncConfig.tipo_comprobante,
        tipo_solicitud: syncConfig.tipo_solicitud
      });

      if (response.data.success) {
        toast.success(`Solicitud creada: ${response.data.id_solicitud}`);
        setSyncResult({
          success: true,
          id_solicitud: response.data.id_solicitud,
          mensaje: response.data.mensaje
        });
        loadDownloadRequests();
      } else {
        toast.error(response.data.error || 'Error creando solicitud');
        setSyncResult({ success: false, error: response.data.error });
      }
    } catch (error) {
      const errorMsg = error.response?.data?.detail || 'Error creando solicitud';
      toast.error(errorMsg);
      setSyncResult({ success: false, error: errorMsg });
    } finally {
      setSyncing(false);
    }
  };

  const handleCheckRequestStatus = async (idSolicitud) => {
    setCheckingStatus(idSolicitud);
    try {
      const response = await api.post('/sat/check-request', { id_solicitud: idSolicitud });
      
      if (response.data.success) {
        toast.info(`Estado: ${response.data.estado_texto} - ${response.data.numero_cfdis} CFDIs`);
        loadDownloadRequests();
        
        // If ready to download, show packages
        if (response.data.paquetes && response.data.paquetes.length > 0) {
          toast.success(`¡Listo! ${response.data.paquetes.length} paquetes disponibles para descarga`);
        }
      } else {
        toast.error(response.data.error || 'Error verificando solicitud');
      }
    } catch (error) {
      toast.error(error.response?.data?.detail || 'Error verificando solicitud');
    } finally {
      setCheckingStatus(null);
    }
  };

  const handleDownloadPackage = async (idPaquete) => {
    setCheckingStatus(idPaquete);
    try {
      const response = await api.post('/sat/download-package', { id_paquete: idPaquete });
      
      if (response.data.success) {
        toast.success(`¡Paquete procesado! ${response.data.cfdis_new} nuevos, ${response.data.cfdis_updated} actualizados`);
        if (onSyncComplete) onSyncComplete();
        loadDownloadRequests();
      } else {
        toast.error(response.data.error || 'Error descargando paquete');
      }
    } catch (error) {
      toast.error(error.response?.data?.detail || 'Error descargando paquete');
    } finally {
      setCheckingStatus(null);
    }
  };

  const handleOpenRequests = () => {
    loadDownloadRequests();
    setRequestsDialogOpen(true);
  };

  const isValidDate = () => {
    const start = new Date(syncConfig.fecha_inicio);
    const end = new Date(syncConfig.fecha_fin);
    const diffDays = Math.ceil((end - start) / (1000 * 60 * 60 * 24));
    
    if (syncConfig.tipo_solicitud === 'CFDI') {
      return diffDays <= 1;
    }
    return diffDays <= 7;
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
            Integración SAT (e.firma / FIEL)
          </CardTitle>
          <CardDescription className="text-[#3B82F6]">
            Descarga automática de CFDIs usando el Web Service oficial del SAT con FIEL
          </CardDescription>
        </CardHeader>
        <CardContent>
          <div className="flex flex-wrap gap-4 items-center">
            {/* Status Indicator */}
            <div className="flex items-center gap-2 bg-white rounded-lg px-4 py-2 border">
              {satStatus?.configured ? (
                <>
                  <div className={`w-3 h-3 rounded-full ${satStatus?.status === 'active' ? 'bg-green-500' : 'bg-yellow-500'}`} />
                  <div className="flex flex-col">
                    <span className="text-sm font-medium text-[#1E293B]">
                      RFC: {satStatus?.rfc}
                    </span>
                    <span className="text-xs text-[#64748B]">
                      Serial: {satStatus?.serial_number?.slice(0, 16)}...
                    </span>
                  </div>
                  {satStatus?.valid_to && (
                    <Badge variant={new Date(satStatus.valid_to) > new Date() ? "outline" : "destructive"} className="ml-2">
                      {new Date(satStatus.valid_to) > new Date() ? 'Vigente' : 'Expirada'}
                    </Badge>
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
                    Probar
                  </Button>
                  
                  <Button
                    variant="outline"
                    size="sm"
                    onClick={handleOpenRequests}
                    className="gap-1"
                    data-testid="sat-requests-btn"
                  >
                    <History size={14} />
                    Solicitudes
                  </Button>

                  <Button
                    size="sm"
                    onClick={() => setSyncDialogOpen(true)}
                    className="gap-1 bg-[#3B82F6] hover:bg-[#2563EB]"
                    data-testid="sync-sat-btn"
                  >
                    <Download size={14} />
                    Descargar CFDIs
                  </Button>

                  <Button
                    variant="ghost"
                    size="sm"
                    onClick={() => setConfigDialogOpen(true)}
                    className="gap-1 text-[#64748B]"
                    data-testid="edit-sat-credentials-btn"
                  >
                    <FileKey size={14} />
                    Cambiar FIEL
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
                  <FileKey size={16} />
                  Configurar FIEL (e.firma)
                </Button>
              )}
            </div>
          </div>
        </CardContent>
      </Card>

      {/* Configure FIEL Dialog */}
      <Dialog open={configDialogOpen} onOpenChange={setConfigDialogOpen}>
        <DialogContent className="max-w-md">
          <DialogHeader>
            <DialogTitle className="flex items-center gap-2">
              <Shield size={20} className="text-[#3B82F6]" />
              Configurar FIEL (e.firma)
            </DialogTitle>
            <DialogDescription>
              Suba los archivos de su FIEL para conectar con el SAT.
              Los archivos se almacenan de forma encriptada.
            </DialogDescription>
          </DialogHeader>

          <div className="space-y-4 py-4">
            {/* CER File */}
            <div className="space-y-2">
              <Label>Certificado (.cer)</Label>
              <div className="flex gap-2">
                <Input
                  type="file"
                  accept=".cer"
                  ref={cerFileRef}
                  onChange={(e) => setCerFile(e.target.files?.[0] || null)}
                  className="hidden"
                />
                <Button
                  variant="outline"
                  className="w-full justify-start gap-2"
                  onClick={() => cerFileRef.current?.click()}
                >
                  <Upload size={14} />
                  {cerFile ? cerFile.name : 'Seleccionar archivo .cer'}
                </Button>
                {cerFile && (
                  <Button variant="ghost" size="icon" onClick={() => setCerFile(null)}>
                    <XCircle size={14} />
                  </Button>
                )}
              </div>
            </div>

            {/* KEY File */}
            <div className="space-y-2">
              <Label>Llave privada (.key)</Label>
              <div className="flex gap-2">
                <Input
                  type="file"
                  accept=".key"
                  ref={keyFileRef}
                  onChange={(e) => setKeyFile(e.target.files?.[0] || null)}
                  className="hidden"
                />
                <Button
                  variant="outline"
                  className="w-full justify-start gap-2"
                  onClick={() => keyFileRef.current?.click()}
                >
                  <Upload size={14} />
                  {keyFile ? keyFile.name : 'Seleccionar archivo .key'}
                </Button>
                {keyFile && (
                  <Button variant="ghost" size="icon" onClick={() => setKeyFile(null)}>
                    <XCircle size={14} />
                  </Button>
                )}
              </div>
            </div>

            {/* Password */}
            <div className="space-y-2">
              <Label htmlFor="fiel-password">Contraseña de la llave privada</Label>
              <Input
                id="fiel-password"
                type="password"
                placeholder="••••••••"
                value={password}
                onChange={(e) => setPassword(e.target.value)}
                data-testid="sat-fiel-password-input"
              />
            </div>

            <div className="bg-blue-50 border border-blue-200 rounded-lg p-3">
              <div className="flex items-start gap-2">
                <AlertCircle size={16} className="text-blue-600 mt-0.5" />
                <div className="text-xs text-blue-800">
                  <p className="font-medium mb-1">¿Dónde obtener la FIEL?</p>
                  <ul className="list-disc list-inside space-y-1">
                    <li>Visite el portal del SAT</li>
                    <li>Descargue sus archivos .cer y .key</li>
                    <li>La FIEL es diferente a la CSD (sellos)</li>
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
              onClick={handleSaveFIEL} 
              disabled={savingCredentials || !cerFile || !keyFile || !password}
              className="bg-[#3B82F6] hover:bg-[#2563EB]"
            >
              {savingCredentials ? <Loader2 size={16} className="animate-spin mr-2" /> : null}
              Guardar FIEL
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>

      {/* Download Request Dialog */}
      <Dialog open={syncDialogOpen} onOpenChange={setSyncDialogOpen}>
        <DialogContent className="max-w-lg">
          <DialogHeader>
            <DialogTitle className="flex items-center gap-2">
              <Download size={20} className="text-[#3B82F6]" />
              Solicitar Descarga de CFDIs
            </DialogTitle>
            <DialogDescription>
              Configure los parámetros para solicitar CFDIs al SAT.
              El SAT procesa las solicitudes de forma asíncrona.
            </DialogDescription>
          </DialogHeader>

          <div className="space-y-4 py-4">
            {/* Tipo de Solicitud */}
            <div className="space-y-2">
              <Label>Tipo de descarga</Label>
              <Select 
                value={syncConfig.tipo_solicitud} 
                onValueChange={(v) => setSyncConfig({ ...syncConfig, tipo_solicitud: v })}
              >
                <SelectTrigger data-testid="sync-tipo-solicitud-select">
                  <SelectValue />
                </SelectTrigger>
                <SelectContent>
                  {tiposSolicitud.map(t => (
                    <SelectItem key={t.value} value={t.value}>{t.label}</SelectItem>
                  ))}
                </SelectContent>
              </Select>
              <p className="text-xs text-[#64748B]">
                {syncConfig.tipo_solicitud === 'CFDI' 
                  ? 'Descarga XML completos. Máximo 1 día por solicitud.'
                  : 'Descarga solo metadatos (sin XML). Máximo 7 días por solicitud.'}
              </p>
            </div>

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

            {!isValidDate() && (
              <div className="text-xs text-red-600 bg-red-50 p-2 rounded">
                ⚠️ El rango de fechas excede el límite permitido para este tipo de solicitud.
              </div>
            )}

            {/* Tipo de Comprobante */}
            <div className="space-y-2">
              <Label>Tipo de comprobante (opcional)</Label>
              <Select 
                value={syncConfig.tipo_comprobante} 
                onValueChange={(v) => setSyncConfig({ ...syncConfig, tipo_comprobante: v })}
              >
                <SelectTrigger data-testid="sync-tipo-select">
                  <SelectValue placeholder="Todos los tipos" />
                </SelectTrigger>
                <SelectContent>
                  {tiposComprobante.map(t => (
                    <SelectItem key={t.value} value={t.value}>{t.label}</SelectItem>
                  ))}
                </SelectContent>
              </Select>
            </div>

            {/* Sync Result */}
            {syncResult && (
              <div className={`rounded-lg p-4 ${syncResult.success ? 'bg-green-50 border border-green-200' : 'bg-red-50 border border-red-200'}`}>
                {syncResult.success ? (
                  <div className="space-y-2">
                    <div className="flex items-center gap-2 text-green-700 font-medium">
                      <CheckCircle2 size={16} />
                      Solicitud creada
                    </div>
                    <div className="text-sm">
                      <p><strong>ID:</strong> {syncResult.id_solicitud}</p>
                      <p className="text-xs text-[#64748B] mt-1">
                        El SAT procesará la solicitud. Verifique el estado en "Solicitudes".
                      </p>
                    </div>
                  </div>
                ) : (
                  <div className="flex items-center gap-2 text-red-700">
                    <XCircle size={16} />
                    <span>{syncResult.error || 'Error en solicitud'}</span>
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
              onClick={handleRequestDownload} 
              disabled={syncing || !isValidDate()}
              className="bg-[#3B82F6] hover:bg-[#2563EB]"
            >
              {syncing ? (
                <>
                  <Loader2 size={16} className="animate-spin mr-2" />
                  Solicitando...
                </>
              ) : (
                <>
                  <Download size={16} className="mr-2" />
                  Crear Solicitud
                </>
              )}
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>

      {/* Download Requests Dialog */}
      <Dialog open={requestsDialogOpen} onOpenChange={setRequestsDialogOpen}>
        <DialogContent className="max-w-3xl max-h-[80vh]">
          <DialogHeader>
            <DialogTitle className="flex items-center gap-2">
              <History size={20} className="text-[#3B82F6]" />
              Solicitudes de Descarga
            </DialogTitle>
          </DialogHeader>

          <div className="overflow-y-auto max-h-96">
            {downloadRequests.length === 0 ? (
              <div className="text-center py-8 text-[#64748B]">
                No hay solicitudes registradas
              </div>
            ) : (
              <div className="space-y-3">
                {downloadRequests.map((req, idx) => (
                  <div key={idx} className="border rounded-lg p-4 bg-[#F8FAFC]">
                    <div className="flex justify-between items-start mb-2">
                      <div>
                        <div className="text-sm font-medium font-mono">
                          {req.id_solicitud}
                        </div>
                        <div className="text-xs text-[#64748B]">
                          {format(new Date(req.created_at), 'dd/MM/yyyy HH:mm', { locale: es })}
                        </div>
                      </div>
                      <Badge variant={
                        req.estado === 'Terminada' ? 'default' :
                        req.estado === 'En proceso' ? 'secondary' :
                        req.estado === 'Error' ? 'destructive' : 'outline'
                      }>
                        {req.estado || 'Solicitada'}
                      </Badge>
                    </div>
                    
                    <div className="text-xs text-[#64748B] space-y-1 mb-3">
                      <div>Período: {req.fecha_inicio?.split('T')[0]} - {req.fecha_fin?.split('T')[0]}</div>
                      <div>Tipo: {req.tipo_solicitud} | Comprobante: {req.tipo_comprobante || 'Todos'}</div>
                      {req.numero_cfdis > 0 && (
                        <div className="text-green-600">CFDIs encontrados: {req.numero_cfdis}</div>
                      )}
                    </div>

                    <div className="flex gap-2">
                      <Button
                        size="sm"
                        variant="outline"
                        onClick={() => handleCheckRequestStatus(req.id_solicitud)}
                        disabled={checkingStatus === req.id_solicitud}
                      >
                        {checkingStatus === req.id_solicitud ? (
                          <Loader2 size={14} className="animate-spin mr-1" />
                        ) : (
                          <RefreshCw size={14} className="mr-1" />
                        )}
                        Verificar
                      </Button>
                      
                      {req.paquetes && req.paquetes.length > 0 && (
                        <div className="flex gap-1 flex-wrap">
                          {req.paquetes.map((paquete, pIdx) => (
                            <Button
                              key={pIdx}
                              size="sm"
                              onClick={() => handleDownloadPackage(paquete)}
                              disabled={checkingStatus === paquete}
                              className="bg-green-600 hover:bg-green-700"
                            >
                              {checkingStatus === paquete ? (
                                <Loader2 size={14} className="animate-spin mr-1" />
                              ) : (
                                <Package size={14} className="mr-1" />
                              )}
                              Paquete {pIdx + 1}
                            </Button>
                          ))}
                        </div>
                      )}
                    </div>
                  </div>
                ))}
              </div>
            )}
          </div>

          <DialogFooter>
            <Button variant="outline" onClick={() => setRequestsDialogOpen(false)}>
              Cerrar
            </Button>
            <Button onClick={loadDownloadRequests} variant="outline">
              <RefreshCw size={14} className="mr-2" />
              Actualizar
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>

      {/* Delete Confirmation Dialog */}
      <AlertDialog open={deleteDialogOpen} onOpenChange={setDeleteDialogOpen}>
        <AlertDialogContent>
          <AlertDialogHeader>
            <AlertDialogTitle>¿Eliminar FIEL?</AlertDialogTitle>
            <AlertDialogDescription>
              Esta acción eliminará la FIEL guardada. 
              Deberá volver a configurarla para descargar CFDIs.
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
