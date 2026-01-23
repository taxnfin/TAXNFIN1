import { useState, useEffect } from 'react';
import api from '@/api/axios';
import { Button } from '@/components/ui/button';
import { Input } from '@/components/ui/input';
import { Label } from '@/components/ui/label';
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from '@/components/ui/select';
import { Dialog, DialogContent, DialogDescription, DialogFooter, DialogHeader, DialogTitle, DialogTrigger } from '@/components/ui/dialog';
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card';
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from '@/components/ui/table';
import { Tabs, TabsContent, TabsList, TabsTrigger } from '@/components/ui/tabs';
import { Checkbox } from '@/components/ui/checkbox';
import { toast } from 'sonner';
import { 
  Plus, CheckCircle, Building2, Trash2, DollarSign, 
  Upload, Download, Link2, RefreshCw, FileSpreadsheet,
  ArrowUpCircle, ArrowDownCircle, Search, Filter, X,
  AlertCircle, Clock, Check, FileText, ArrowRightLeft, Pencil
} from 'lucide-react';
import { format } from 'date-fns';
import { es } from 'date-fns/locale';
import * as XLSX from 'xlsx';

// Belvo Connect Form Component
const BelvoConnectForm = ({ bankAccounts, onSuccess, onClose }) => {
  const [step, setStep] = useState('status'); // status, select, credentials
  const [belvoStatus, setBelvoStatus] = useState(null);
  const [institutions, setInstitutions] = useState([]);
  const [connections, setConnections] = useState([]);
  const [selectedInstitution, setSelectedInstitution] = useState(null);
  const [selectedBankAccount, setSelectedBankAccount] = useState('');
  const [credentials, setCredentials] = useState({ username: '', password: '' });
  const [loading, setLoading] = useState(false);
  const [syncing, setSyncing] = useState(false);

  useEffect(() => {
    checkBelvoStatus();
    loadConnections();
  }, []);

  const checkBelvoStatus = async () => {
    try {
      const res = await api.get('/belvo/status');
      setBelvoStatus(res.data);
      if (res.data.configured) {
        loadInstitutions();
      }
    } catch (error) {
      setBelvoStatus({ configured: false });
    }
  };

  const loadInstitutions = async () => {
    try {
      const res = await api.get('/belvo/institutions');
      setInstitutions(res.data.institutions || []);
    } catch (error) {
      console.log('Error loading institutions');
    }
  };

  const loadConnections = async () => {
    try {
      const res = await api.get('/belvo/connections');
      setConnections(res.data || []);
    } catch (error) {
      console.log('Error loading connections');
    }
  };

  const handleConnect = async () => {
    if (!selectedInstitution || !selectedBankAccount || !credentials.username || !credentials.password) {
      toast.error('Completa todos los campos');
      return;
    }

    setLoading(true);
    try {
      await api.post('/belvo/connect', {
        institution_id: selectedInstitution.id,
        bank_account_id: selectedBankAccount,
        username: credentials.username,
        password: credentials.password
      });
      toast.success('Banco conectado exitosamente');
      loadConnections();
      setStep('status');
      setCredentials({ username: '', password: '' });
      onSuccess?.();
    } catch (error) {
      toast.error(error.response?.data?.detail || 'Error conectando banco');
    } finally {
      setLoading(false);
    }
  };

  const handleSync = async (connectionId) => {
    setSyncing(true);
    try {
      const res = await api.post(`/belvo/sync/${connectionId}`);
      toast.success(res.data.message);
      onSuccess?.();
    } catch (error) {
      toast.error(error.response?.data?.detail || 'Error sincronizando');
    } finally {
      setSyncing(false);
    }
  };

  const handleDeleteConnection = async (connectionId) => {
    if (!window.confirm('¿Eliminar esta conexión bancaria?')) return;
    try {
      await api.delete(`/belvo/connections/${connectionId}`);
      toast.success('Conexión eliminada');
      loadConnections();
    } catch (error) {
      toast.error('Error eliminando conexión');
    }
  };

  // Status check / Not configured
  if (!belvoStatus?.configured) {
    return (
      <div className="space-y-4 py-4">
        <div className="bg-yellow-50 border border-yellow-200 rounded-lg p-4">
          <div className="flex items-start gap-3">
            <AlertCircle size={20} className="text-yellow-600 mt-0.5" />
            <div>
              <p className="font-medium text-yellow-800">Belvo no está configurado</p>
              <p className="text-sm text-yellow-600 mt-1">
                Para conectar bancos automáticamente, necesitas agregar tus credenciales de Belvo en el archivo .env:
              </p>
              <div className="mt-2 bg-gray-800 text-green-400 p-2 rounded text-xs font-mono">
                BELVO_SECRET_ID=&quot;tu_secret_id&quot;<br/>
                BELVO_SECRET_PASSWORD=&quot;tu_secret_password&quot;<br/>
                BELVO_ENV=&quot;sandbox&quot;
              </div>
              <a href="https://developers.belvo.com" target="_blank" rel="noreferrer" 
                className="text-blue-600 text-sm hover:underline mt-2 inline-block">
                Obtener credenciales de Belvo →
              </a>
            </div>
          </div>
        </div>

        <div className="border-t pt-4">
          <p className="text-sm font-medium mb-3">Mientras tanto, puedes:</p>
          <div className="space-y-2">
            <div className="flex items-center gap-3 p-3 border rounded-lg hover:bg-gray-50 cursor-pointer" onClick={onClose}>
              <Upload size={20} className="text-gray-500" />
              <div>
                <p className="font-medium">Importar desde Excel/PDF</p>
                <p className="text-sm text-gray-500">Usa los botones de importación</p>
              </div>
            </div>
          </div>
        </div>

        <DialogFooter>
          <Button variant="outline" onClick={onClose}>Cerrar</Button>
        </DialogFooter>
      </div>
    );
  }

  // Main view - Show connections and option to add new
  return (
    <div className="space-y-4 py-4">
      {/* Existing Connections */}
      {connections.length > 0 && (
        <div className="space-y-2">
          <Label className="text-sm font-medium">Conexiones activas</Label>
          {connections.map(conn => (
            <div key={conn.id} className="flex items-center justify-between p-3 border rounded-lg bg-green-50">
              <div className="flex items-center gap-3">
                <div className="w-10 h-10 rounded-full bg-green-100 flex items-center justify-center">
                  <Building2 size={20} className="text-green-600" />
                </div>
                <div>
                  <p className="font-medium">{conn.institution_name}</p>
                  <p className="text-xs text-gray-500">{conn.banco} - {conn.bank_account_name}</p>
                  {conn.last_sync && (
                    <p className="text-xs text-green-600">
                      Última sync: {new Date(conn.last_sync).toLocaleString('es-MX')}
                    </p>
                  )}
                </div>
              </div>
              <div className="flex gap-2">
                <Button 
                  size="sm" 
                  variant="outline" 
                  onClick={() => handleSync(conn.id)}
                  disabled={syncing}
                >
                  <RefreshCw size={14} className={syncing ? 'animate-spin' : ''} />
                </Button>
                <Button 
                  size="sm" 
                  variant="ghost" 
                  className="text-red-500"
                  onClick={() => handleDeleteConnection(conn.id)}
                >
                  <Trash2 size={14} />
                </Button>
              </div>
            </div>
          ))}
        </div>
      )}

      {/* Add new connection */}
      {step === 'status' && (
        <div className="space-y-3">
          <Button 
            className="w-full gap-2" 
            onClick={() => setStep('select')}
          >
            <Plus size={16} />
            Conectar nueva cuenta bancaria
          </Button>
        </div>
      )}

      {/* Step: Select bank */}
      {step === 'select' && (
        <div className="space-y-3">
          <Label>Selecciona tu banco</Label>
          <div className="grid grid-cols-2 gap-2 max-h-48 overflow-y-auto">
            {institutions.slice(0, 12).map(inst => (
              <div
                key={inst.id}
                className={`p-3 border rounded-lg cursor-pointer transition-colors ${
                  selectedInstitution?.id === inst.id 
                    ? 'border-blue-500 bg-blue-50' 
                    : 'hover:bg-gray-50'
                }`}
                onClick={() => setSelectedInstitution(inst)}
              >
                <div className="flex items-center gap-2">
                  {inst.logo ? (
                    <img src={inst.logo} alt={inst.display_name} className="w-8 h-8 object-contain" />
                  ) : (
                    <div className="w-8 h-8 rounded bg-gray-200 flex items-center justify-center">
                      <Building2 size={16} />
                    </div>
                  )}
                  <span className="text-sm font-medium truncate">{inst.display_name}</span>
                </div>
              </div>
            ))}
          </div>
          
          {selectedInstitution && (
            <>
              <Label>Cuenta bancaria local</Label>
              <Select value={selectedBankAccount} onValueChange={setSelectedBankAccount}>
                <SelectTrigger>
                  <SelectValue placeholder="Seleccionar cuenta..." />
                </SelectTrigger>
                <SelectContent>
                  {bankAccounts.map(acc => (
                    <SelectItem key={acc.id} value={acc.id}>
                      {acc.banco} - {acc.nombre} ({acc.moneda})
                    </SelectItem>
                  ))}
                </SelectContent>
              </Select>
            </>
          )}

          <div className="flex gap-2">
            <Button variant="outline" onClick={() => setStep('status')}>Cancelar</Button>
            <Button 
              onClick={() => setStep('credentials')} 
              disabled={!selectedInstitution || !selectedBankAccount}
            >
              Continuar
            </Button>
          </div>
        </div>
      )}

      {/* Step: Credentials */}
      {step === 'credentials' && (
        <div className="space-y-3">
          <div className="p-3 bg-blue-50 border border-blue-200 rounded-lg">
            <p className="text-sm text-blue-800">
              <strong>{selectedInstitution?.display_name}</strong> - Ingresa tus credenciales de banca en línea
            </p>
          </div>

          <div className="space-y-2">
            <Label>Usuario / Número de cliente</Label>
            <Input
              value={credentials.username}
              onChange={(e) => setCredentials({...credentials, username: e.target.value})}
              placeholder="Tu usuario de banca en línea"
            />
          </div>

          <div className="space-y-2">
            <Label>Contraseña</Label>
            <Input
              type="password"
              value={credentials.password}
              onChange={(e) => setCredentials({...credentials, password: e.target.value})}
              placeholder="Tu contraseña de banca en línea"
            />
          </div>

          <div className="p-3 bg-yellow-50 border border-yellow-200 rounded-lg">
            <p className="text-xs text-yellow-700">
              🔒 Tus credenciales se envían de forma segura a través de Belvo y no se almacenan en nuestros servidores.
            </p>
          </div>

          <div className="flex gap-2">
            <Button variant="outline" onClick={() => setStep('select')}>Atrás</Button>
            <Button 
              onClick={handleConnect} 
              disabled={loading || !credentials.username || !credentials.password}
              className="flex-1"
            >
              {loading ? 'Conectando...' : 'Conectar Banco'}
            </Button>
          </div>
        </div>
      )}

      {step === 'status' && (
        <DialogFooter>
          <Button variant="outline" onClick={onClose}>Cerrar</Button>
        </DialogFooter>
      )}
    </div>
  );
};

const BankStatementsModule = () => {
  const [bankTransactions, setBankTransactions] = useState([]);
  const [bankAccounts, setBankAccounts] = useState([]);
  const [cfdis, setCfdis] = useState([]);
  const [loading, setLoading] = useState(true);
  const [dialogOpen, setDialogOpen] = useState(false);
  const [connectDialogOpen, setConnectDialogOpen] = useState(false);
  const [reconcileDialogOpen, setReconcileDialogOpen] = useState(false);
  const [importDialogOpen, setImportDialogOpen] = useState(false);
  const [transferDialogOpen, setTransferDialogOpen] = useState(false);
  const [selectedTransaction, setSelectedTransaction] = useState(null);
  const [filterAccount, setFilterAccount] = useState('all');
  const [filterStatus, setFilterStatus] = useState('all');
  const [searchTerm, setSearchTerm] = useState('');
  const [importFile, setImportFile] = useState(null);
  const [importAccountId, setImportAccountId] = useState('');
  const [importing, setImporting] = useState(false);
  const [duplicatesFound, setDuplicatesFound] = useState([]);
  const [skipDuplicates, setSkipDuplicates] = useState(true);
  const [selectedCfdis, setSelectedCfdis] = useState([]);
  const [cfdiSearchTerm, setCfdiSearchTerm] = useState('');
  const [importPdfDialogOpen, setImportPdfDialogOpen] = useState(false);
  const [pdfFile, setPdfFile] = useState(null);
  const [pdfAccountId, setPdfAccountId] = useState('');
  const [importingPdf, setImportingPdf] = useState(false);
  const [pdfPreview, setPdfPreview] = useState(null);
  const [loadingPreview, setLoadingPreview] = useState(false);
  const [transferFromAccount, setTransferFromAccount] = useState('');
  const [transferToAccount, setTransferToAccount] = useState('');
  const [transferring, setTransferring] = useState(false);

  const [formData, setFormData] = useState({
    bank_account_id: '',
    fecha_movimiento: format(new Date(), "yyyy-MM-dd'T'HH:mm"),
    fecha_valor: format(new Date(), "yyyy-MM-dd'T'HH:mm"),
    descripcion: '',
    referencia: '',
    monto: '',
    tipo_movimiento: 'credito',
    saldo: ''
  });
  
  // State for editing transaction
  const [editDialogOpen, setEditDialogOpen] = useState(false);
  const [editingTransaction, setEditingTransaction] = useState(null);
  const [editFormData, setEditFormData] = useState({
    bank_account_id: '',
    descripcion: '',
    referencia: '',
    monto: '',
    tipo_movimiento: 'credito',
    fecha_movimiento: '',
    notas: ''
  });

  // Exchange rates for conversion
  const [fxRates, setFxRates] = useState({ USD: 17.5, EUR: 19.0 });
  
  // Historical exchange rate for reconciliation (based on transaction date)
  const [historicalFxRate, setHistoricalFxRate] = useState(null);
  
  // Reconciliation summary
  const [reconSummary, setReconSummary] = useState(null);

  useEffect(() => {
    loadData();
    loadFxRates();
    loadReconSummary();
  }, []);

  const loadReconSummary = async () => {
    try {
      const res = await api.get('/reconciliations/summary');
      setReconSummary(res.data);
    } catch (error) {
      console.log('Error loading reconciliation summary');
    }
  };

  const loadFxRates = async () => {
    try {
      const res = await api.get('/fx-rates');
      const rates = {};
      res.data.forEach(rate => {
        if (rate.moneda_destino === 'MXN') {
          rates[rate.moneda_origen] = rate.tasa;
        }
      });
      if (rates.USD || rates.EUR) {
        setFxRates(prev => ({ ...prev, ...rates }));
      }
    } catch (error) {
      console.log('Using default FX rates');
    }
  };

  // Get historical exchange rate for a specific date
  const getHistoricalFxRate = async (moneda, fecha) => {
    if (moneda === 'MXN') {
      return { tasa: 1.0, fecha: fecha };
    }
    try {
      const fechaStr = fecha ? (fecha instanceof Date ? fecha.toISOString().split('T')[0] : fecha.split('T')[0]) : null;
      const res = await api.get(`/fx-rates/by-date?moneda=${moneda}&fecha=${fechaStr}`);
      return { tasa: res.data.tasa, fecha: res.data.fecha };
    } catch (error) {
      console.log('Error getting historical FX rate, using default');
      const defaultRates = { USD: 17.5, EUR: 19.0 };
      return { tasa: defaultRates[moneda] || 1.0, fecha: fecha };
    }
  };

  const convertToMXN = (monto, moneda) => {
    if (!monto) return 0;
    if (moneda === 'MXN') return monto;
    if (moneda === 'USD') return monto * (fxRates.USD || 17.5);
    if (moneda === 'EUR') return monto * (fxRates.EUR || 19.0);
    return monto;
  };

  // Convert using historical rate (for reconciliation)
  const convertToMXNHistorical = (monto, moneda, rate) => {
    if (!monto) return 0;
    if (moneda === 'MXN') return monto;
    return monto * (rate || fxRates[moneda] || 17.5);
  };

  const loadData = async () => {
    try {
      const [txnRes, accountsRes, cfdisRes] = await Promise.all([
        api.get('/bank-transactions?limit=500'),
        api.get('/bank-accounts'),
        api.get('/cfdi?limit=500')
      ]);
      setBankTransactions(txnRes.data);
      setBankAccounts(accountsRes.data);
      setCfdis(cfdisRes.data);
    } catch (error) {
      toast.error('Error cargando datos');
    } finally {
      setLoading(false);
    }
  };

  const handleSubmit = async (e) => {
    e.preventDefault();
    if (!formData.bank_account_id) {
      toast.error('Selecciona una cuenta bancaria');
      return;
    }
    try {
      await api.post('/bank-transactions', {
        ...formData,
        monto: parseFloat(formData.monto),
        saldo: parseFloat(formData.saldo) || 0
      });
      toast.success('Movimiento agregado correctamente');
      setDialogOpen(false);
      resetForm();
      loadData();
    } catch (error) {
      toast.error(error.response?.data?.detail || 'Error guardando movimiento');
    }
  };

  const resetForm = () => {
    setFormData({
      bank_account_id: '',
      fecha_movimiento: format(new Date(), "yyyy-MM-dd'T'HH:mm"),
      fecha_valor: format(new Date(), "yyyy-MM-dd'T'HH:mm"),
      descripcion: '',
      referencia: '',
      monto: '',
      tipo_movimiento: 'credito',
      saldo: ''
    });
  };

  const handleDelete = async (id) => {
    if (!confirm('¿Eliminar este movimiento?')) return;
    try {
      await api.delete(`/bank-transactions/${id}`);
      toast.success('Movimiento eliminado');
      loadData();
    } catch (error) {
      toast.error('Error eliminando movimiento');
    }
  };

  // Toggle CFDI selection for multi-reconciliation
  const toggleCfdiSelection = (cfdi) => {
    setSelectedCfdis(prev => {
      const exists = prev.find(c => c.id === cfdi.id);
      if (exists) {
        return prev.filter(c => c.id !== cfdi.id);
      } else {
        return [...prev, cfdi];
      }
    });
  };

  // Calculate totals for reconciliation - handles currency conversion using HISTORICAL rate
  const getReconciliationTotals = () => {
    const movimientoMonto = selectedTransaction?.monto || 0;
    
    // Get transaction currency from account or transaction itself
    const transactionAccount = bankAccounts.find(a => a.id === selectedTransaction?.bank_account_id);
    const movimientoMoneda = selectedTransaction?.moneda || transactionAccount?.moneda || 'MXN';
    
    // Use historical rate if available, otherwise fallback to current rates
    const tcHistorico = historicalFxRate?.tasa || fxRates[movimientoMoneda] || 17.5;
    
    // Convert movement amount to MXN using HISTORICAL rate (date of transaction)
    const movimientoMontoMXN = convertToMXNHistorical(movimientoMonto, movimientoMoneda, tcHistorico);
    
    // Sum CFDIs - each CFDI may have its own currency
    // Note: CFDIs should use their own currency's historical rate, but typically they match
    let cfdiTotalMXN = 0;
    selectedCfdis.forEach(cfdi => {
      const cfdiMoneda = cfdi.moneda || 'MXN';
      // For CFDIs, we use the same historical rate if same currency, otherwise convert
      if (cfdiMoneda === movimientoMoneda) {
        cfdiTotalMXN += convertToMXNHistorical(cfdi.total || 0, cfdiMoneda, tcHistorico);
      } else if (cfdiMoneda === 'MXN') {
        cfdiTotalMXN += cfdi.total || 0;
      } else {
        // Different foreign currency - use current rates as approximation
        cfdiTotalMXN += convertToMXN(cfdi.total || 0, cfdiMoneda);
      }
    });
    
    // Calculate difference in MXN (converted values)
    const diferenciaMXN = movimientoMontoMXN - cfdiTotalMXN;
    
    // Also return original values for display
    const cfdiTotal = selectedCfdis.reduce((sum, cfdi) => sum + (cfdi.total || 0), 0);
    
    // Get transaction date for display
    const fechaMovimiento = selectedTransaction?.fecha_movimiento || null;
    
    return { 
      movimientoMonto,           // Original amount
      movimientoMoneda,          // Original currency  
      movimientoMontoMXN,        // Converted to MXN using historical rate
      cfdiTotal,                 // Original CFDI total (might be in different currency)
      cfdiTotalMXN,              // CFDI total in MXN
      diferencia: diferenciaMXN, // Difference in MXN
      diferenciaMXN,             // Alias for clarity
      tcUsado: tcHistorico,      // Historical exchange rate used
      fechaTc: historicalFxRate?.fecha || fechaMovimiento,  // Date of the rate
      esHistorico: !!historicalFxRate  // Flag to indicate if historical rate is being used
    };
  };

  // Confirm multi-reconciliation
  const handleConfirmReconciliation = async () => {
    if (!selectedTransaction || selectedCfdis.length === 0) {
      toast.error('Selecciona al menos un CFDI');
      return;
    }
    
    try {
      // Reconcile each selected CFDI
      for (const cfdi of selectedCfdis) {
        await api.post('/reconciliations', {
          bank_transaction_id: selectedTransaction.id,
          cfdi_id: cfdi.id,
          metodo_conciliacion: 'manual',
          porcentaje_match: 100
        });
      }
      
      const { diferenciaMXN } = getReconciliationTotals();
      if (Math.abs(diferenciaMXN) < 0.01) {
        toast.success(`Movimiento conciliado con ${selectedCfdis.length} CFDI(s) - Cuadrado perfectamente`);
      } else {
        toast.success(`Movimiento conciliado con ${selectedCfdis.length} CFDI(s) - Diferencia: $${diferenciaMXN.toFixed(2)} MXN`);
      }
      
      setReconcileDialogOpen(false);
      setSelectedTransaction(null);
      setSelectedCfdis([]);
      setCfdiSearchTerm('');
      loadData();
    } catch (error) {
      toast.error(error.response?.data?.detail || 'Error al conciliar');
    }
  };

  const handleReconcile = async (cfdiId) => {
    if (!selectedTransaction) return;
    try {
      await api.post('/reconciliations', {
        bank_transaction_id: selectedTransaction.id,
        cfdi_id: cfdiId,
        metodo_conciliacion: 'manual',
        tipo_conciliacion: 'con_uuid',
        porcentaje_match: 100
      });
      toast.success('Movimiento conciliado con CFDI');
      setReconcileDialogOpen(false);
      setSelectedTransaction(null);
      setSelectedCfdis([]);
      loadData();
      loadReconSummary();
    } catch (error) {
      toast.error(error.response?.data?.detail || 'Error al conciliar');
    }
  };

  // Mark transaction as reconciled WITHOUT UUID - with category selection
  const [sinUUIDDialogOpen, setSinUUIDDialogOpen] = useState(false);
  const [sinUUIDTransaction, setSinUUIDTransaction] = useState(null);
  const [sinUUIDFormData, setSinUUIDFormData] = useState({
    tipo_conciliacion: 'sin_uuid',
    categoria: '',
    concepto: '',
    notas: ''
  });

  const EXPENSE_CATEGORIES = [
    { value: 'comision_bancaria', label: 'Comisión Bancaria' },
    { value: 'gasto_sin_factura', label: 'Gasto sin Factura' },
    { value: 'transferencia_interna', label: 'Transferencia Interna' },
    { value: 'pago_nomina', label: 'Pago de Nómina' },
    { value: 'impuestos', label: 'Impuestos / ISR / IVA' },
    { value: 'intereses', label: 'Intereses' },
    { value: 'retiro_efectivo', label: 'Retiro en Efectivo' },
    { value: 'deposito_no_identificado', label: 'Depósito No Identificado' },
    { value: 'otro', label: 'Otro' }
  ];

  const openSinUUIDDialog = (txn, tipo = 'sin_uuid') => {
    setSinUUIDTransaction(txn);
    setSinUUIDFormData({
      tipo_conciliacion: tipo,
      categoria: '',
      concepto: txn.descripcion || '',
      notas: ''
    });
    setSinUUIDDialogOpen(true);
  };

  const handleMarkWithoutUUID = async () => {
    if (!sinUUIDTransaction) return;
    
    try {
      const res = await api.post('/reconciliations/mark-without-uuid', {
        bank_transaction_id: sinUUIDTransaction.id,
        tipo_conciliacion: sinUUIDFormData.tipo_conciliacion,
        categoria: sinUUIDFormData.categoria,
        concepto: sinUUIDFormData.concepto,
        notas: sinUUIDFormData.notas
      });
      
      const tipoLabel = sinUUIDFormData.tipo_conciliacion === 'sin_uuid' ? 'Sin UUID' : 'No relacionado';
      toast.success(`Movimiento marcado como "${tipoLabel}" y registrado en Cobranza y Pagos`);
      
      setSinUUIDDialogOpen(false);
      setSinUUIDTransaction(null);
      loadData();
      loadReconSummary();
    } catch (error) {
      toast.error(error.response?.data?.detail || 'Error al marcar movimiento');
    }
  };

  // Quick mark without dialog (for backward compatibility)
  const handleQuickMarkWithoutUUID = async (txn, tipo) => {
    try {
      await api.post('/reconciliations/mark-without-uuid', {
        bank_transaction_id: txn.id,
        tipo_conciliacion: tipo,
        categoria: tipo === 'sin_uuid' ? 'gasto_sin_factura' : 'transferencia_interna',
        concepto: txn.descripcion || '',
        notas: tipo === 'sin_uuid' ? 'Conciliado sin UUID - pago sin factura' : 'No relacionado - movimiento interno'
      });
      toast.success(tipo === 'sin_uuid' 
        ? 'Movimiento marcado como "Sin UUID" y registrado como pago' 
        : 'Movimiento marcado como "No relacionado"'
      );
      loadData();
      loadReconSummary();
    } catch (error) {
      toast.error(error.response?.data?.detail || 'Error al marcar movimiento');
    }
  };

  // Edit transaction functions
  const handleEditTransaction = (txn) => {
    setEditingTransaction(txn);
    setEditFormData({
      bank_account_id: txn.bank_account_id || '',
      descripcion: txn.descripcion || '',
      referencia: txn.referencia || '',
      monto: txn.monto?.toString() || '',
      tipo_movimiento: txn.tipo_movimiento || 'credito',
      fecha_movimiento: txn.fecha_movimiento ? format(new Date(txn.fecha_movimiento), "yyyy-MM-dd'T'HH:mm") : '',
      notas: txn.notas || ''
    });
    setEditDialogOpen(true);
  };

  const handleUpdateTransaction = async (e) => {
    e.preventDefault();
    if (!editingTransaction) return;
    
    try {
      await api.put(`/bank-transactions/${editingTransaction.id}`, {
        ...editFormData,
        monto: parseFloat(editFormData.monto)
      });
      toast.success('Movimiento actualizado');
      setEditDialogOpen(false);
      setEditingTransaction(null);
      loadData();
    } catch (error) {
      toast.error(error.response?.data?.detail || 'Error actualizando movimiento');
    }
  };

  // Delete all reconciliations
  const handleDeleteAllReconciliations = async () => {
    if (!window.confirm('⚠️ ¿Estás SEGURO de que quieres ELIMINAR TODAS las conciliaciones?\n\nTodos los movimientos volverán a estado "Pendiente".\nEsta acción NO se puede deshacer.')) {
      return;
    }
    if (!window.confirm('🚨 ÚLTIMA CONFIRMACIÓN: Se borrarán TODAS las conciliaciones.\n\n¿Continuar?')) {
      return;
    }
    
    try {
      const res = await api.delete('/reconciliations/bulk/all');
      toast.success(res.data.message);
      loadData();
      loadReconSummary();
    } catch (error) {
      toast.error(error.response?.data?.detail || 'Error eliminando conciliaciones');
    }
  };

  const downloadTemplate = async () => {
    try {
      const response = await api.get('/bank-transactions/template', {
        responseType: 'blob'
      });
      const url = window.URL.createObjectURL(new Blob([response.data]));
      const link = document.createElement('a');
      link.href = url;
      link.setAttribute('download', 'plantilla_estado_cuenta.xlsx');
      document.body.appendChild(link);
      link.click();
      link.remove();
      window.URL.revokeObjectURL(url);
      toast.success('Plantilla descargada');
    } catch (error) {
      toast.error('Error descargando plantilla');
    }
  };

  const exportToExcel = () => {
    if (filteredTransactions.length === 0) {
      toast.error('No hay movimientos para exportar');
      return;
    }

    const data = filteredTransactions.map(txn => {
      const account = bankAccounts.find(a => a.id === txn.bank_account_id);
      return {
        'Fecha': format(new Date(txn.fecha_movimiento), 'dd/MM/yyyy'),
        'Cuenta': account?.nombre || 'N/A',
        'Banco': account?.banco || 'N/A',
        'Descripción': txn.descripcion,
        'Referencia': txn.referencia || '',
        'Tipo': txn.tipo_movimiento === 'credito' ? 'Depósito' : 'Retiro',
        'Monto': txn.monto,
        'Saldo': txn.saldo,
        'Moneda': txn.moneda || account?.moneda || 'MXN',
        'Conciliado': txn.conciliado ? 'Sí' : 'No'
      };
    });

    const wb = XLSX.utils.book_new();
    const ws = XLSX.utils.json_to_sheet(data);
    XLSX.utils.book_append_sheet(wb, ws, 'Movimientos');
    XLSX.writeFile(wb, `Estados_Cuenta_${format(new Date(), 'yyyy-MM-dd')}.xlsx`);
    toast.success('Exportado a Excel');
  };

  // Handle PDF file selection
  const handlePdfSelect = (e) => {
    const file = e.target.files?.[0];
    if (!file) return;
    
    if (bankAccounts.length === 0) {
      toast.error('Primero crea una cuenta bancaria');
      e.target.value = '';
      return;
    }
    
    if (!file.name.toLowerCase().endsWith('.pdf')) {
      toast.error('Solo se aceptan archivos PDF');
      e.target.value = '';
      return;
    }
    
    setPdfFile(file);
    setPdfAccountId(bankAccounts[0]?.id || '');
    setPdfPreview(null);
    setImportPdfDialogOpen(true);
    e.target.value = '';
    
    // Auto-load preview
    loadPdfPreview(file);
  };

  // Load PDF preview
  const loadPdfPreview = async (file) => {
    setLoadingPreview(true);
    setPdfPreview(null);
    
    try {
      const formData = new FormData();
      formData.append('file', file);
      formData.append('banco', 'auto');

      const response = await api.post('/bank-transactions/preview-pdf', formData, {
        headers: {
          'Content-Type': 'multipart/form-data'
        }
      });

      setPdfPreview(response.data);
    } catch (error) {
      toast.error(error.response?.data?.detail || 'Error leyendo PDF');
      setPdfPreview({ status: 'error', message: 'No se pudo leer el PDF' });
    } finally {
      setLoadingPreview(false);
    }
  };

  // Process PDF import
  const processPdfImport = async () => {
    if (!pdfFile || !pdfAccountId) {
      toast.error('Selecciona una cuenta bancaria');
      return;
    }

    setImportingPdf(true);

    try {
      const formData = new FormData();
      formData.append('file', pdfFile);
      formData.append('bank_account_id', pdfAccountId);
      formData.append('banco', 'auto');

      const response = await api.post('/bank-transactions/import-pdf', formData, {
        headers: {
          'Content-Type': 'multipart/form-data'
        }
      });

      const result = response.data;

      if (result.importados > 0) {
        toast.success(`${result.importados} movimientos importados del PDF`);
      }
      
      if (result.duplicados_omitidos > 0) {
        toast.warning(`${result.duplicados_omitidos} duplicados omitidos`);
      }
      
      if (result.importados === 0 && result.status === 'warning') {
        toast.info(result.message);
      }

      setImportPdfDialogOpen(false);
      setPdfFile(null);
      setPdfAccountId('');
      setPdfPreview(null);
      loadData();
    } catch (error) {
      toast.error(error.response?.data?.detail || 'Error importando PDF');
    } finally {
      setImportingPdf(false);
    }
  };

  // Handle file selection - opens dialog to select account
  const handleFileSelect = (e) => {
    const file = e.target.files?.[0];
    if (!file) return;
    
    if (bankAccounts.length === 0) {
      toast.error('Primero crea una cuenta bancaria');
      e.target.value = '';
      return;
    }
    
    setImportFile(file);
    setImportAccountId(bankAccounts[0]?.id || '');
    setImportDialogOpen(true);
    e.target.value = '';
  };

  // Process the import after account is selected
  const processImport = async () => {
    if (!importFile || !importAccountId) {
      toast.error('Selecciona una cuenta bancaria');
      return;
    }

    setImporting(true);

    try {
      const reader = new FileReader();
      reader.onload = async (event) => {
        const data = new Uint8Array(event.target.result);
        const workbook = XLSX.read(data, { type: 'array', cellDates: true });
        const sheetName = workbook.SheetNames[0];
        const worksheet = workbook.Sheets[sheetName];
        const jsonData = XLSX.utils.sheet_to_json(worksheet);

        if (jsonData.length === 0) {
          toast.error('El archivo está vacío');
          setImporting(false);
          return;
        }

        let imported = 0;
        let errors = 0;
        let duplicates = 0;

        console.log('Starting import with account:', importAccountId);
        console.log('Total rows to process:', jsonData.length);

        for (const row of jsonData) {
          try {
            console.log('Processing row:', row);
            
            // Parse date - handle multiple formats
            let fechaMovimiento = new Date();
            const fechaRaw = row['fecha_movimiento'] || row['Fecha'] || row['FECHA'] || row['fecha'];
            if (fechaRaw) {
              if (fechaRaw instanceof Date) {
                fechaMovimiento = fechaRaw;
              } else if (typeof fechaRaw === 'string') {
                // Try parsing different formats
                const parsed = new Date(fechaRaw);
                if (!isNaN(parsed.getTime())) {
                  fechaMovimiento = parsed;
                } else {
                  // Try DD/MM/YYYY format
                  const parts = fechaRaw.split('/');
                  if (parts.length === 3) {
                    fechaMovimiento = new Date(parts[2], parts[1] - 1, parts[0]);
                  }
                }
              } else if (typeof fechaRaw === 'number') {
                // Excel serial date number
                const excelEpoch = new Date(1899, 11, 30);
                fechaMovimiento = new Date(excelEpoch.getTime() + fechaRaw * 86400000);
              }
            }
            
            console.log('Parsed date:', fechaMovimiento);

            // Parse amount - the sign of monto determines the type
            let monto = 0;
            let tipoMovimiento = 'credito'; // Default: deposit
            
            // Read the monto column
            if (row['monto'] !== undefined || row['Monto'] !== undefined || row['MONTO'] !== undefined) {
              monto = parseFloat(row['monto'] || row['Monto'] || row['MONTO'] || 0);
            }
            
            // Handle Cargo/Abono columns (alternative format)
            if (monto === 0) {
              if (row['Cargo'] !== undefined || row['CARGO'] !== undefined) {
                monto = -parseFloat(row['Cargo'] || row['CARGO'] || 0); // Cargo is negative
              }
              if (row['Abono'] !== undefined || row['ABONO'] !== undefined) {
                monto = parseFloat(row['Abono'] || row['ABONO'] || 0); // Abono is positive
              }
              if (row['Deposito'] || row['Depósito'] || row['DEPOSITO']) {
                monto = parseFloat(row['Deposito'] || row['Depósito'] || row['DEPOSITO'] || 0);
              }
              if (row['Retiro'] || row['RETIRO']) {
                monto = -parseFloat(row['Retiro'] || row['RETIRO'] || 0);
              }
            }
            
            // Determine tipo based on sign of monto
            // Negative monto = money going out (retiro/cargo) = debito
            // Positive monto = money coming in (deposito/abono) = credito
            if (monto < 0) {
              tipoMovimiento = 'debito'; // Retiro/Cargo
              monto = Math.abs(monto);
            } else {
              tipoMovimiento = 'credito'; // Depósito/Abono
            }
            
            console.log('Monto:', monto, 'Tipo:', tipoMovimiento);

            // Get description
            const descripcion = row['descripcion'] || row['Descripción'] || row['DESCRIPCION'] || 
                               row['Concepto'] || row['CONCEPTO'] || row['concepto'] || 
                               row['Movimiento'] || 'Movimiento importado';

            // Get reference
            const referencia = row['referencia'] || row['Referencia'] || row['REFERENCIA'] || 
                              row['Ref'] || row['REF'] || '';

            // Get saldo
            const saldo = parseFloat(row['saldo'] || row['Saldo'] || row['SALDO'] || 0);

            // Skip rows with 0 amount
            if (monto === 0 || isNaN(monto)) {
              console.log('Skipping row with 0 or NaN monto');
              continue;
            }

            const txnData = {
              bank_account_id: importAccountId,
              fecha_movimiento: fechaMovimiento.toISOString(),
              fecha_valor: fechaMovimiento.toISOString(),
              descripcion: String(descripcion).substring(0, 500),
              referencia: String(referencia).substring(0, 100),
              monto: monto,
              tipo_movimiento: tipoMovimiento,
              saldo: saldo || 0,
              fuente: 'excel_import'
            };

            // Check for duplicate
            const isDuplicate = bankTransactions.some(existing => 
              existing.descripcion === txnData.descripcion &&
              Math.abs(existing.monto - monto) < 0.01 &&
              existing.fecha_movimiento?.slice(0, 10) === fechaMovimiento.toISOString().slice(0, 10)
            );

            if (isDuplicate) {
              duplicates++;
              console.log('Duplicate found, skipping:', txnData.descripcion);
              continue;
            }

            console.log('Sending transaction:', txnData);
            const response = await api.post('/bank-transactions', txnData);
            console.log('Transaction created:', response.data);
            imported++;
          } catch (err) {
            console.error('Error importing row:', row, 'Error:', err.response?.data || err.message);
            errors++;
          }
        }

        if (imported > 0) {
          toast.success(`${imported} movimientos importados correctamente`);
        }
        if (duplicates > 0) {
          toast.warning(`${duplicates} movimientos duplicados omitidos`);
        }
        if (errors > 0) {
          toast.error(`${errors} filas con errores`);
        }
        if (imported === 0 && errors === 0 && duplicates === 0) {
          toast.info('No se encontraron movimientos válidos para importar');
        }
        
        setImportDialogOpen(false);
        setImportFile(null);
        setImportAccountId('');
        setDuplicatesFound([]);
        setImporting(false);
        loadData();
      };
      reader.readAsArrayBuffer(importFile);
    } catch (error) {
      toast.error('Error importando archivo');
      setImporting(false);
    }
  };

  // Transfer state with currency conversion support
  const [transferConvertCurrency, setTransferConvertCurrency] = useState(true);
  const [transferCustomFxRate, setTransferCustomFxRate] = useState('');
  const [transferSelectedTxns, setTransferSelectedTxns] = useState([]);

  // Transfer transactions between accounts with currency conversion
  const handleTransferTransactions = async () => {
    if (!transferFromAccount || !transferToAccount) {
      toast.error('Selecciona cuenta origen y destino');
      return;
    }
    if (transferFromAccount === transferToAccount) {
      toast.error('La cuenta origen y destino no pueden ser la misma');
      return;
    }

    setTransferring(true);
    try {
      const payload = {
        from_account_id: transferFromAccount,
        to_account_id: transferToAccount,
        convert_currency: transferConvertCurrency
      };
      
      // Include custom FX rate if provided
      if (transferCustomFxRate && parseFloat(transferCustomFxRate) > 0) {
        payload.custom_fx_rate = parseFloat(transferCustomFxRate);
      }
      
      // Include specific transaction IDs if selected
      if (transferSelectedTxns.length > 0) {
        payload.transaction_ids = transferSelectedTxns;
      }
      
      const response = await api.post('/bank-transactions/transfer-account', payload);
      
      const msg = response.data.currency_converted 
        ? `${response.data.message} (TC: ${response.data.fx_rate_used?.toFixed(4)})`
        : response.data.message;
      
      toast.success(msg);
      setTransferDialogOpen(false);
      setTransferFromAccount('');
      setTransferToAccount('');
      setTransferConvertCurrency(true);
      setTransferCustomFxRate('');
      setTransferSelectedTxns([]);
      loadData();
    } catch (error) {
      toast.error(error.response?.data?.detail || 'Error transfiriendo movimientos');
    } finally {
      setTransferring(false);
    }
  };

  // Get currency info for transfer dialog
  const getAccountCurrency = (accountId) => {
    const account = bankAccounts.find(a => a.id === accountId);
    return account?.moneda || 'MXN';
  };

  const transferFromCurrency = transferFromAccount ? getAccountCurrency(transferFromAccount) : '';
  const transferToCurrency = transferToAccount ? getAccountCurrency(transferToAccount) : '';
  const needsCurrencyConversion = transferFromCurrency && transferToCurrency && transferFromCurrency !== transferToCurrency;

  // Filter transactions
  const filteredTransactions = bankTransactions.filter(txn => {
    if (filterAccount !== 'all' && txn.bank_account_id !== filterAccount) return false;
    if (filterStatus === 'conciliado' && !txn.conciliado) return false;
    if (filterStatus === 'pendiente' && txn.conciliado) return false;
    if (searchTerm && !txn.descripcion?.toLowerCase().includes(searchTerm.toLowerCase()) &&
        !txn.referencia?.toLowerCase().includes(searchTerm.toLowerCase())) return false;
    return true;
  });

  // Stats
  const totalDepositos = filteredTransactions
    .filter(t => t.tipo_movimiento === 'credito')
    .reduce((sum, t) => sum + t.monto, 0);
  const totalRetiros = filteredTransactions
    .filter(t => t.tipo_movimiento === 'debito')
    .reduce((sum, t) => sum + t.monto, 0);
  const pendientesConciliar = filteredTransactions.filter(t => !t.conciliado).length;
  
  // Get selected account's initial balance and currency
  // When "all" is selected, calculate consolidated balance in MXN
  const selectedAccount = filterAccount !== 'all' 
    ? bankAccounts.find(a => a.id === filterAccount)
    : null;
  
  // Calculate consolidated initial balance when viewing all accounts
  const calcConsolidatedSaldoInicial = () => {
    if (filterAccount !== 'all') {
      return selectedAccount?.saldo_inicial || 0;
    }
    // Sum all accounts converted to MXN
    return bankAccounts.reduce((total, acc) => {
      const saldo = acc.saldo_inicial || 0;
      const moneda = acc.moneda || 'MXN';
      return total + convertToMXN(saldo, moneda);
    }, 0);
  };
  
  const saldoInicial = calcConsolidatedSaldoInicial();
  const monedaCuenta = filterAccount === 'all' ? 'MXN' : (selectedAccount?.moneda || 'MXN');
  
  // For consolidated view, convert all transactions to MXN
  const calcConsolidatedTotals = () => {
    if (filterAccount !== 'all') {
      return { depositos: totalDepositos, retiros: totalRetiros };
    }
    // Convert each transaction based on its account's currency
    let depositosMXN = 0;
    let retirosMXN = 0;
    filteredTransactions.forEach(t => {
      const acc = bankAccounts.find(a => a.id === t.bank_account_id);
      const moneda = t.moneda || acc?.moneda || 'MXN';
      const montoMXN = convertToMXN(t.monto, moneda);
      if (t.tipo_movimiento === 'credito') {
        depositosMXN += montoMXN;
      } else {
        retirosMXN += montoMXN;
      }
    });
    return { depositos: depositosMXN, retiros: retirosMXN };
  };
  
  const consolidatedTotals = calcConsolidatedTotals();
  const displayDepositos = filterAccount === 'all' ? consolidatedTotals.depositos : totalDepositos;
  const displayRetiros = filterAccount === 'all' ? consolidatedTotals.retiros : totalRetiros;
  const saldoFinal = saldoInicial + displayDepositos - displayRetiros;

  if (loading) return <div className="p-8">Cargando...</div>;

  return (
    <div className="p-8 space-y-6" data-testid="bank-statements-page">
      {/* Header */}
      <div className="flex justify-between items-start">
        <div>
          <h1 className="text-4xl font-bold text-[#0F172A] mb-2" style={{fontFamily: 'Manrope'}}>
            Conciliaciones Bancarias
          </h1>
          <p className="text-[#64748B]">Gestión de movimientos bancarios y conciliación con CFDIs</p>
        </div>
        <div className="flex gap-2 flex-wrap">
          <Button variant="outline" onClick={() => setConnectDialogOpen(true)} className="gap-2" data-testid="connect-bank-btn">
            <Link2 size={16} />
            Conectar Banco
          </Button>
          <Button variant="outline" onClick={downloadTemplate} className="gap-2" data-testid="download-template-btn">
            <FileSpreadsheet size={16} />
            Descargar Plantilla
          </Button>
          <label className="cursor-pointer">
            <input type="file" accept=".xlsx,.xls,.csv" onChange={handleFileSelect} className="hidden" />
            <Button variant="outline" className="gap-2" asChild>
              <span>
                <Upload size={16} />
                Importar Excel
              </span>
            </Button>
          </label>
          <label className="cursor-pointer">
            <input type="file" accept=".pdf" onChange={handlePdfSelect} className="hidden" />
            <Button variant="outline" className="gap-2 border-red-200 text-red-700 hover:bg-red-50" asChild data-testid="import-pdf-btn">
              <span>
                <FileText size={16} />
                Importar PDF
              </span>
            </Button>
          </label>
          <Button variant="outline" onClick={() => setTransferDialogOpen(true)} className="gap-2" data-testid="transfer-movements-btn">
            <ArrowRightLeft size={16} />
            Transferir
          </Button>
          <Button variant="outline" onClick={exportToExcel} className="gap-2" data-testid="export-statements-btn">
            <Download size={16} />
            Exportar
          </Button>
          <Button 
            variant="outline" 
            onClick={handleDeleteAllReconciliations} 
            className="gap-2 text-red-600 border-red-300 hover:bg-red-50" 
            data-testid="delete-all-reconciliations-btn"
          >
            <Trash2 size={16} />
            Borrar Conciliaciones
          </Button>
          
          {/* Transfer Dialog - Enhanced with Currency Conversion */}
          <Dialog open={transferDialogOpen} onOpenChange={setTransferDialogOpen}>
            <DialogContent className="max-w-lg">
              <DialogHeader>
                <DialogTitle className="flex items-center gap-2">
                  <ArrowRightLeft size={20} />
                  Transferir Movimientos Entre Cuentas
                </DialogTitle>
                <DialogDescription>
                  Mueve movimientos de una cuenta a otra. Soporta conversión de moneda automática o manual.
                </DialogDescription>
              </DialogHeader>
              <div className="space-y-4 py-4">
                <div className="space-y-2">
                  <Label>Cuenta Origen</Label>
                  <Select value={transferFromAccount} onValueChange={setTransferFromAccount}>
                    <SelectTrigger>
                      <SelectValue placeholder="Seleccionar cuenta origen..." />
                    </SelectTrigger>
                    <SelectContent>
                      {bankAccounts.map(acc => (
                        <SelectItem key={acc.id} value={acc.id}>
                          <div className="flex items-center gap-2">
                            <span className={`w-2 h-2 rounded-full ${acc.moneda === 'USD' ? 'bg-green-500' : acc.moneda === 'EUR' ? 'bg-blue-500' : 'bg-yellow-500'}`}></span>
                            {acc.banco} - {acc.nombre} ({acc.moneda})
                          </div>
                        </SelectItem>
                      ))}
                    </SelectContent>
                  </Select>
                </div>
                
                <div className="space-y-2">
                  <Label>Cuenta Destino</Label>
                  <Select value={transferToAccount} onValueChange={setTransferToAccount}>
                    <SelectTrigger>
                      <SelectValue placeholder="Seleccionar cuenta destino..." />
                    </SelectTrigger>
                    <SelectContent>
                      {bankAccounts.filter(a => a.id !== transferFromAccount).map(acc => (
                        <SelectItem key={acc.id} value={acc.id}>
                          <div className="flex items-center gap-2">
                            <span className={`w-2 h-2 rounded-full ${acc.moneda === 'USD' ? 'bg-green-500' : acc.moneda === 'EUR' ? 'bg-blue-500' : 'bg-yellow-500'}`}></span>
                            {acc.banco} - {acc.nombre} ({acc.moneda})
                          </div>
                        </SelectItem>
                      ))}
                    </SelectContent>
                  </Select>
                </div>

                {/* Currency Conversion Options - Show when currencies differ */}
                {needsCurrencyConversion && (
                  <div className="p-4 bg-blue-50 border border-blue-200 rounded-lg space-y-3">
                    <div className="flex items-center gap-2 text-blue-800 font-medium">
                      <DollarSign size={18} />
                      Conversión de Moneda: {transferFromCurrency} → {transferToCurrency}
                    </div>
                    
                    <div className="flex items-center gap-2">
                      <Checkbox 
                        id="convert-currency" 
                        checked={transferConvertCurrency}
                        onCheckedChange={setTransferConvertCurrency}
                      />
                      <Label htmlFor="convert-currency" className="text-sm text-blue-700">
                        Convertir montos automáticamente
                      </Label>
                    </div>
                    
                    {transferConvertCurrency && (
                      <div className="space-y-2">
                        <Label className="text-sm text-blue-700">
                          Tipo de Cambio (opcional - dejar vacío para usar el actual)
                        </Label>
                        <div className="flex items-center gap-2">
                          <span className="text-sm text-blue-600">1 {transferFromCurrency} =</span>
                          <Input 
                            type="number"
                            step="0.0001"
                            placeholder={`Ej: ${transferFromCurrency === 'USD' ? '17.50' : '0.0571'}`}
                            value={transferCustomFxRate}
                            onChange={(e) => setTransferCustomFxRate(e.target.value)}
                            className="w-32"
                          />
                          <span className="text-sm text-blue-600">{transferToCurrency}</span>
                        </div>
                        <p className="text-xs text-blue-600">
                          Si no especificas un tipo de cambio, se usará el más reciente registrado en el sistema.
                        </p>
                      </div>
                    )}
                    
                    {!transferConvertCurrency && (
                      <p className="text-xs text-blue-600">
                        ⚠️ Los montos se mantendrán igual, solo cambiará la etiqueta de moneda.
                      </p>
                    )}
                  </div>
                )}

                {/* Summary */}
                {transferFromAccount && transferToAccount && (
                  <div className={`p-3 ${needsCurrencyConversion ? 'bg-orange-50 border-orange-200' : 'bg-yellow-50 border-yellow-200'} border rounded-lg`}>
                    <p className="text-sm text-gray-800">
                      <AlertCircle className="inline-block mr-2" size={16} />
                      Se transferirán <strong>todos los movimientos</strong> de <strong>{bankAccounts.find(a => a.id === transferFromAccount)?.nombre}</strong> ({transferFromCurrency}) a <strong>{bankAccounts.find(a => a.id === transferToAccount)?.nombre}</strong> ({transferToCurrency}).
                    </p>
                    {needsCurrencyConversion && transferConvertCurrency && (
                      <p className="text-sm text-orange-700 mt-2">
                        💱 Los montos serán convertidos de {transferFromCurrency} a {transferToCurrency}.
                      </p>
                    )}
                  </div>
                )}
              </div>
              <DialogFooter>
                <Button variant="outline" onClick={() => {
                  setTransferDialogOpen(false);
                  setTransferFromAccount('');
                  setTransferToAccount('');
                  setTransferConvertCurrency(true);
                  setTransferCustomFxRate('');
                }}>Cancelar</Button>
                <Button 
                  onClick={handleTransferTransactions} 
                  disabled={transferring || !transferFromAccount || !transferToAccount}
                  className="bg-[#0F172A]"
                >
                  {transferring ? 'Transfiriendo...' : 'Transferir Movimientos'}
                </Button>
              </DialogFooter>
            </DialogContent>
          </Dialog>
          
          <Dialog open={dialogOpen} onOpenChange={setDialogOpen}>
            <DialogTrigger asChild>
              <Button className="gap-2 bg-[#0F172A]" data-testid="add-movement-btn">
                <Plus size={16} />
                Agregar Movimiento
              </Button>
            </DialogTrigger>
            <DialogContent className="max-w-lg">
              <DialogHeader>
                <DialogTitle>Nuevo Movimiento Bancario</DialogTitle>
                <DialogDescription>Captura un movimiento del estado de cuenta</DialogDescription>
              </DialogHeader>
              <form onSubmit={handleSubmit} className="space-y-4">
                <div className="space-y-2">
                  <Label>Cuenta Bancaria *</Label>
                  <Select value={formData.bank_account_id} onValueChange={(v) => setFormData({...formData, bank_account_id: v})}>
                    <SelectTrigger>
                      <SelectValue placeholder="Seleccionar cuenta..." />
                    </SelectTrigger>
                    <SelectContent>
                      {bankAccounts.map(acc => (
                        <SelectItem key={acc.id} value={acc.id}>
                          <span className="flex items-center gap-2">
                            <Building2 size={14} />
                            {acc.banco} - {acc.nombre} ({acc.moneda})
                          </span>
                        </SelectItem>
                      ))}
                    </SelectContent>
                  </Select>
                </div>
                
                <div className="grid grid-cols-2 gap-4">
                  <div className="space-y-2">
                    <Label>Fecha Movimiento *</Label>
                    <Input 
                      type="datetime-local" 
                      value={formData.fecha_movimiento}
                      onChange={(e) => setFormData({...formData, fecha_movimiento: e.target.value})}
                      required
                    />
                  </div>
                  <div className="space-y-2">
                    <Label>Fecha Valor</Label>
                    <Input 
                      type="datetime-local" 
                      value={formData.fecha_valor}
                      onChange={(e) => setFormData({...formData, fecha_valor: e.target.value})}
                    />
                  </div>
                </div>

                <div className="space-y-2">
                  <Label>Descripción / Concepto *</Label>
                  <Input 
                    value={formData.descripcion}
                    onChange={(e) => setFormData({...formData, descripcion: e.target.value})}
                    placeholder="Ej: Transferencia SPEI, Pago de nómina..."
                    required
                  />
                </div>

                <div className="space-y-2">
                  <Label>Referencia / Folio</Label>
                  <Input 
                    value={formData.referencia}
                    onChange={(e) => setFormData({...formData, referencia: e.target.value})}
                    placeholder="Número de referencia bancaria"
                  />
                </div>

                <div className="grid grid-cols-2 gap-4">
                  <div className="space-y-2">
                    <Label>Tipo de Movimiento *</Label>
                    <Select value={formData.tipo_movimiento} onValueChange={(v) => setFormData({...formData, tipo_movimiento: v})}>
                      <SelectTrigger>
                        <SelectValue />
                      </SelectTrigger>
                      <SelectContent>
                        <SelectItem value="credito">
                          <span className="flex items-center gap-2 text-green-600">
                            <ArrowUpCircle size={14} /> Depósito / Abono
                          </span>
                        </SelectItem>
                        <SelectItem value="debito">
                          <span className="flex items-center gap-2 text-red-600">
                            <ArrowDownCircle size={14} /> Retiro / Cargo
                          </span>
                        </SelectItem>
                      </SelectContent>
                    </Select>
                  </div>
                  <div className="space-y-2">
                    <Label>Monto *</Label>
                    <Input 
                      type="number" 
                      step="0.01"
                      value={formData.monto}
                      onChange={(e) => setFormData({...formData, monto: e.target.value})}
                      placeholder="0.00"
                      required
                    />
                  </div>
                </div>

                <div className="space-y-2">
                  <Label>Saldo después del movimiento</Label>
                  <Input 
                    type="number" 
                    step="0.01"
                    value={formData.saldo}
                    onChange={(e) => setFormData({...formData, saldo: e.target.value})}
                    placeholder="Saldo en el estado de cuenta"
                  />
                </div>

                <DialogFooter>
                  <Button type="button" variant="outline" onClick={() => setDialogOpen(false)}>Cancelar</Button>
                  <Button type="submit" className="bg-[#0F172A]">Guardar Movimiento</Button>
                </DialogFooter>
              </form>
            </DialogContent>
          </Dialog>
        </div>
      </div>

      {/* Summary Cards - Row 1: Flujo */}
      <div className="grid grid-cols-1 md:grid-cols-5 gap-4">
        <Card className="border-gray-200 bg-gray-50">
          <CardHeader className="pb-2">
            <CardTitle className="text-sm font-medium text-gray-600 flex items-center gap-2">
              <Building2 size={16} />
              Saldo Inicial {filterAccount === 'all' && '(Consolidado)'}
            </CardTitle>
          </CardHeader>
          <CardContent>
            <div className="text-xl font-bold text-gray-700">
              ${saldoInicial.toLocaleString('es-MX', {minimumFractionDigits: 2})}
              {filterAccount === 'all' ? (
                <span className="text-xs ml-1">MXN</span>
              ) : (
                monedaCuenta !== 'MXN' && <span className="text-xs ml-1">{monedaCuenta}</span>
              )}
            </div>
            {filterAccount === 'all' && bankAccounts.length > 0 && (
              <p className="text-xs text-gray-500">{bankAccounts.length} cuenta(s)</p>
            )}
            {filterAccount !== 'all' && monedaCuenta !== 'MXN' && (
              <p className="text-xs text-gray-500 mt-1">
                ≈ ${convertToMXN(saldoInicial, monedaCuenta).toLocaleString('es-MX', {minimumFractionDigits: 2})} MXN
              </p>
            )}
          </CardContent>
        </Card>

        <Card className="border-green-200 bg-green-50">
          <CardHeader className="pb-2">
            <CardTitle className="text-sm font-medium text-green-700 flex items-center gap-2">
              <ArrowUpCircle size={16} />
              + Depósitos
            </CardTitle>
          </CardHeader>
          <CardContent>
            <div className="text-xl font-bold text-green-700">
              ${displayDepositos.toLocaleString('es-MX', {minimumFractionDigits: 2})}
              {filterAccount === 'all' ? (
                <span className="text-xs ml-1">MXN</span>
              ) : (
                monedaCuenta !== 'MXN' && <span className="text-xs ml-1">{monedaCuenta}</span>
              )}
            </div>
            {filterAccount !== 'all' && monedaCuenta !== 'MXN' && (
              <p className="text-xs text-green-600 mt-1">
                ≈ ${convertToMXN(displayDepositos, monedaCuenta).toLocaleString('es-MX', {minimumFractionDigits: 2})} MXN
              </p>
            )}
          </CardContent>
        </Card>

        <Card className="border-red-200 bg-red-50">
          <CardHeader className="pb-2">
            <CardTitle className="text-sm font-medium text-red-700 flex items-center gap-2">
              <ArrowDownCircle size={16} />
              - Retiros
            </CardTitle>
          </CardHeader>
          <CardContent>
            <div className="text-xl font-bold text-red-700">
              ${displayRetiros.toLocaleString('es-MX', {minimumFractionDigits: 2})}
              {filterAccount === 'all' ? (
                <span className="text-xs ml-1">MXN</span>
              ) : (
                monedaCuenta !== 'MXN' && <span className="text-xs ml-1">{monedaCuenta}</span>
              )}
            </div>
            {filterAccount !== 'all' && monedaCuenta !== 'MXN' && (
              <p className="text-xs text-red-600 mt-1">
                ≈ ${convertToMXN(displayRetiros, monedaCuenta).toLocaleString('es-MX', {minimumFractionDigits: 2})} MXN
              </p>
            )}
          </CardContent>
        </Card>

        <Card className="border-blue-200 bg-blue-50">
          <CardHeader className="pb-2">
            <CardTitle className="text-sm font-medium text-blue-700 flex items-center gap-2">
              <DollarSign size={16} />
              = Saldo Final {filterAccount === 'all' && '(Consolidado)'}
            </CardTitle>
          </CardHeader>
          <CardContent>
            <div className={`text-xl font-bold ${saldoFinal >= 0 ? 'text-blue-700' : 'text-red-700'}`}>
              ${saldoFinal.toLocaleString('es-MX', {minimumFractionDigits: 2})}
              {filterAccount === 'all' ? (
                <span className="text-xs ml-1">MXN</span>
              ) : (
                monedaCuenta !== 'MXN' && <span className="text-xs ml-1">{monedaCuenta}</span>
              )}
            </div>
            {filterAccount !== 'all' && monedaCuenta !== 'MXN' && (
              <p className={`text-xs mt-1 ${saldoFinal >= 0 ? 'text-blue-600' : 'text-red-600'}`}>
                ≈ ${convertToMXN(saldoFinal, monedaCuenta).toLocaleString('es-MX', {minimumFractionDigits: 2})} MXN
              </p>
            )}
          </CardContent>
        </Card>

        <Card className="border-yellow-200 bg-yellow-50">
          <CardHeader className="pb-2">
            <CardTitle className="text-sm font-medium text-yellow-700 flex items-center gap-2">
              <Clock size={16} />
              Pendientes
            </CardTitle>
          </CardHeader>
          <CardContent>
            <div className="text-xl font-bold text-yellow-700">{pendientesConciliar}</div>
            <p className="text-xs text-yellow-600">sin conciliar</p>
          </CardContent>
        </Card>
      </div>

      {/* Reconciliation Summary Cards */}
      {reconSummary && (
        <div className="grid grid-cols-1 md:grid-cols-5 gap-4">
          <Card className="border-purple-200 bg-purple-50">
            <CardHeader className="pb-2">
              <CardTitle className="text-sm font-medium text-purple-700 flex items-center gap-2">
                <CheckCircle size={16} />
                Con UUID
              </CardTitle>
            </CardHeader>
            <CardContent>
              <div className="text-xl font-bold text-purple-700">{reconSummary.summary?.conciliados_con_uuid || 0}</div>
              <p className="text-xs text-purple-600">
                ${(reconSummary.summary?.monto_con_uuid || 0).toLocaleString('es-MX', {minimumFractionDigits: 2})}
              </p>
            </CardContent>
          </Card>

          <Card className="border-orange-200 bg-orange-50">
            <CardHeader className="pb-2">
              <CardTitle className="text-sm font-medium text-orange-700 flex items-center gap-2">
                <AlertCircle size={16} />
                Sin UUID
              </CardTitle>
            </CardHeader>
            <CardContent>
              <div className="text-xl font-bold text-orange-700">{reconSummary.summary?.conciliados_sin_uuid || 0}</div>
              <p className="text-xs text-orange-600">
                ${(reconSummary.summary?.monto_sin_uuid || 0).toLocaleString('es-MX', {minimumFractionDigits: 2})}
              </p>
            </CardContent>
          </Card>

          <Card className="border-gray-200 bg-gray-50">
            <CardHeader className="pb-2">
              <CardTitle className="text-sm font-medium text-gray-700 flex items-center gap-2">
                <X size={16} />
                No Relacionado
              </CardTitle>
            </CardHeader>
            <CardContent>
              <div className="text-xl font-bold text-gray-700">{reconSummary.summary?.no_relacionados || 0}</div>
              <p className="text-xs text-gray-600">
                ${(reconSummary.summary?.monto_no_relacionado || 0).toLocaleString('es-MX', {minimumFractionDigits: 2})}
              </p>
            </CardContent>
          </Card>

          <Card className="border-red-200 bg-red-50">
            <CardHeader className="pb-2">
              <CardTitle className="text-sm font-medium text-red-700 flex items-center gap-2">
                <Clock size={16} />
                Diferencia Pendiente
              </CardTitle>
            </CardHeader>
            <CardContent>
              <div className="text-xl font-bold text-red-700">{reconSummary.summary?.pendientes || 0}</div>
              <p className="text-xs text-red-600">
                ${(reconSummary.summary?.monto_pendiente || 0).toLocaleString('es-MX', {minimumFractionDigits: 2})}
              </p>
            </CardContent>
          </Card>

          <Card className="border-green-300 bg-green-100">
            <CardHeader className="pb-2">
              <CardTitle className="text-sm font-medium text-green-800 flex items-center gap-2">
                <CheckCircle size={16} />
                % Conciliado
              </CardTitle>
            </CardHeader>
            <CardContent>
              <div className="text-xl font-bold text-green-800">{reconSummary.summary?.porcentaje_conciliado || 0}%</div>
              <p className="text-xs text-green-700">
                {(reconSummary.summary?.total_movimientos || 0) - (reconSummary.summary?.pendientes || 0)} de {reconSummary.summary?.total_movimientos || 0}
              </p>
            </CardContent>
          </Card>
        </div>
      )}

      {/* Filters */}
      <Card>
        <CardContent className="pt-4">
          <div className="flex flex-wrap gap-4 items-end">
            <div className="flex-1 min-w-[200px]">
              <Label className="text-xs text-gray-500">Buscar</Label>
              <div className="relative">
                <Search size={16} className="absolute left-3 top-1/2 transform -translate-y-1/2 text-gray-400" />
                <Input
                  placeholder="Buscar por descripción o referencia..."
                  value={searchTerm}
                  onChange={(e) => setSearchTerm(e.target.value)}
                  className="pl-10"
                />
              </div>
            </div>
            <div className="w-48">
              <Label className="text-xs text-gray-500">Cuenta</Label>
              <Select value={filterAccount} onValueChange={setFilterAccount}>
                <SelectTrigger>
                  <SelectValue />
                </SelectTrigger>
                <SelectContent>
                  <SelectItem value="all">Todas las cuentas</SelectItem>
                  {bankAccounts.map(acc => (
                    <SelectItem key={acc.id} value={acc.id}>
                      {acc.banco} - {acc.nombre}
                    </SelectItem>
                  ))}
                </SelectContent>
              </Select>
            </div>
            <div className="w-48">
              <Label className="text-xs text-gray-500">Estado</Label>
              <Select value={filterStatus} onValueChange={setFilterStatus}>
                <SelectTrigger>
                  <SelectValue />
                </SelectTrigger>
                <SelectContent>
                  <SelectItem value="all">Todos</SelectItem>
                  <SelectItem value="pendiente">Pendientes</SelectItem>
                  <SelectItem value="conciliado">Conciliados</SelectItem>
                </SelectContent>
              </Select>
            </div>
            {(searchTerm || filterAccount !== 'all' || filterStatus !== 'all') && (
              <Button variant="ghost" size="sm" onClick={() => {
                setSearchTerm('');
                setFilterAccount('all');
                setFilterStatus('all');
              }}>
                <X size={16} className="mr-1" /> Limpiar
              </Button>
            )}
          </div>
        </CardContent>
      </Card>

      {/* Transactions Table */}
      <Card>
        <CardHeader>
          <CardTitle>Movimientos Bancarios</CardTitle>
          <CardDescription>
            {filteredTransactions.length} movimiento{filteredTransactions.length !== 1 ? 's' : ''} encontrado{filteredTransactions.length !== 1 ? 's' : ''}
          </CardDescription>
        </CardHeader>
        <CardContent>
          {bankAccounts.length === 0 ? (
            <div className="text-center py-12 text-gray-500">
              <Building2 size={48} className="mx-auto mb-4 opacity-50" />
              <p className="font-medium">No hay cuentas bancarias</p>
              <p className="text-sm mt-2">Primero crea una cuenta bancaria en el módulo Bancario</p>
            </div>
          ) : filteredTransactions.length === 0 ? (
            <div className="text-center py-12 text-gray-500">
              <FileSpreadsheet size={48} className="mx-auto mb-4 opacity-50" />
              <p className="font-medium">No hay movimientos</p>
              <p className="text-sm mt-2">Agrega movimientos manualmente, importa desde Excel o conecta tu banco</p>
            </div>
          ) : (
            <div className="overflow-x-auto">
              <Table>
                <TableHeader>
                  <TableRow>
                    <TableHead>Fecha</TableHead>
                    <TableHead>Cuenta</TableHead>
                    <TableHead>Descripción</TableHead>
                    <TableHead>Referencia</TableHead>
                    <TableHead>Tipo</TableHead>
                    <TableHead className="text-right">Monto</TableHead>
                    <TableHead className="text-right">Saldo</TableHead>
                    <TableHead className="text-center">Estado</TableHead>
                    <TableHead className="text-center">Acciones</TableHead>
                  </TableRow>
                </TableHeader>
                <TableBody>
                  {filteredTransactions.map((txn) => {
                    const account = bankAccounts.find(a => a.id === txn.bank_account_id);
                    return (
                      <TableRow key={txn.id} className={txn.conciliado ? 'bg-green-50/50' : ''}>
                        <TableCell className="font-mono text-sm">
                          {format(new Date(txn.fecha_movimiento), 'dd/MM/yyyy', { locale: es })}
                        </TableCell>
                        <TableCell>
                          <div className="flex flex-col">
                            <span className="text-xs font-medium bg-blue-100 text-blue-800 px-2 py-0.5 rounded w-fit">{account?.banco || 'N/A'}</span>
                            <span className="text-xs text-gray-500 mt-0.5">{account?.nombre || '-'}</span>
                          </div>
                        </TableCell>
                        <TableCell className="max-w-[250px]">
                          <span className="truncate block">{txn.descripcion}</span>
                        </TableCell>
                        <TableCell className="font-mono text-sm text-gray-500">{txn.referencia || '-'}</TableCell>
                        <TableCell>
                          <span className={`inline-flex items-center gap-1 text-xs px-2 py-1 rounded font-medium ${
                            txn.tipo_movimiento === 'credito' 
                              ? 'bg-green-100 text-green-700' 
                              : 'bg-red-100 text-red-700'
                          }`}>
                            {txn.tipo_movimiento === 'credito' ? (
                              <><ArrowUpCircle size={12} /> Depósito</>
                            ) : (
                              <><ArrowDownCircle size={12} /> Retiro</>
                            )}
                          </span>
                        </TableCell>
                        <TableCell className={`text-right font-mono font-semibold ${
                          txn.tipo_movimiento === 'credito' ? 'text-green-600' : 'text-red-600'
                        }`}>
                          <div>
                            {txn.tipo_movimiento === 'credito' ? '+' : '-'}
                            ${Math.abs(txn.monto).toLocaleString('es-MX', {minimumFractionDigits: 2})}
                            <span className="text-xs ml-1">{txn.moneda || account?.moneda || 'MXN'}</span>
                          </div>
                          {(txn.moneda || account?.moneda) !== 'MXN' && (txn.moneda || account?.moneda) && (
                            <div className="text-xs text-gray-400 font-normal">
                              ≈ ${convertToMXN(txn.monto, txn.moneda || account?.moneda).toLocaleString('es-MX', {minimumFractionDigits: 2})} MXN
                            </div>
                          )}
                        </TableCell>
                        <TableCell className="text-right font-mono">
                          ${(txn.saldo || 0).toLocaleString('es-MX', {minimumFractionDigits: 2})}
                          {(txn.moneda || account?.moneda) !== 'MXN' && (
                            <span className="text-xs ml-1 text-gray-400">{txn.moneda || account?.moneda}</span>
                          )}
                        </TableCell>
                        <TableCell className="text-center">
                          {txn.conciliado ? (
                            txn.tipo_conciliacion === 'sin_uuid' ? (
                              <span className="inline-flex items-center gap-1 text-orange-600 text-xs px-2 py-1 bg-orange-50 rounded">
                                <AlertCircle size={12} /> Sin UUID
                              </span>
                            ) : txn.tipo_conciliacion === 'no_relacionado' ? (
                              <span className="inline-flex items-center gap-1 text-gray-600 text-xs px-2 py-1 bg-gray-100 rounded">
                                <X size={12} /> No Rel.
                              </span>
                            ) : (
                              <span className="inline-flex items-center gap-1 text-green-600 text-xs px-2 py-1 bg-green-50 rounded">
                                <Check size={12} /> Con UUID
                              </span>
                            )
                          ) : (
                            <span className="inline-flex items-center gap-1 text-yellow-600 text-xs px-2 py-1 bg-yellow-50 rounded">
                              <Clock size={14} /> Pendiente
                            </span>
                          )}
                        </TableCell>
                        <TableCell className="text-center">
                          <div className="flex justify-center gap-1 flex-wrap">
                            {!txn.conciliado && (
                              <>
                                <Button
                                  variant="outline"
                                  size="sm"
                                  className="text-xs h-7"
                                  onClick={() => {
                                    setSelectedTransaction(txn);
                                    setReconcileDialogOpen(true);
                                  }}
                                >
                                  <Link2 size={12} className="mr-1" />
                                  Con UUID
                                </Button>
                                <Button
                                  variant="outline"
                                  size="sm"
                                  className="text-xs h-7 text-orange-600 border-orange-300 hover:bg-orange-50"
                                  onClick={() => openSinUUIDDialog(txn, 'sin_uuid')}
                                  title="Registrar como gasto/ingreso sin factura (comisiones, etc.)"
                                >
                                  Sin UUID
                                </Button>
                                <Button
                                  variant="outline"
                                  size="sm"
                                  className="text-xs h-7 text-gray-600 border-gray-300 hover:bg-gray-50"
                                  onClick={() => handleQuickMarkWithoutUUID(txn, 'no_relacionado')}
                                  title="Marcar como no relacionado (transferencias internas)"
                                >
                                  No Rel.
                                </Button>
                              </>
                            )}
                            <Button
                              variant="ghost"
                              size="sm"
                              className="h-7 text-blue-500 hover:text-blue-700"
                              onClick={() => handleEditTransaction(txn)}
                              title="Editar movimiento"
                            >
                              <Pencil size={14} />
                            </Button>
                            <Button
                              variant="ghost"
                              size="sm"
                              className="h-7 text-red-500 hover:text-red-700"
                              onClick={() => handleDelete(txn.id)}
                              title="Eliminar movimiento"
                            >
                              <Trash2 size={14} />
                            </Button>
                          </div>
                        </TableCell>
                      </TableRow>
                    );
                  })}
                </TableBody>
              </Table>
            </div>
          )}
        </CardContent>
      </Card>

      {/* Connect Bank Dialog */}
      <Dialog open={connectDialogOpen} onOpenChange={setConnectDialogOpen}>
        <DialogContent className="max-w-lg">
          <DialogHeader>
            <DialogTitle className="flex items-center gap-2">
              <Link2 size={20} />
              Conectar Banco (Belvo)
            </DialogTitle>
            <DialogDescription>
              Conecta tu cuenta bancaria para descargar movimientos automáticamente
            </DialogDescription>
          </DialogHeader>
          
          <BelvoConnectForm 
            bankAccounts={bankAccounts} 
            onSuccess={() => {
              setConnectDialogOpen(false);
              loadData();
              toast.success('Banco conectado exitosamente');
            }}
            onClose={() => setConnectDialogOpen(false)}
          />
        </DialogContent>
      </Dialog>

      {/* Reconcile Dialog - Multi-select with balance tracking */}
      <Dialog open={reconcileDialogOpen} onOpenChange={(open) => {
        if (!open) {
          setSelectedCfdis([]);
          setCfdiSearchTerm('');
        }
        setReconcileDialogOpen(open);
      }}>
        <DialogContent className="max-w-3xl max-h-[90vh] overflow-hidden flex flex-col">
          <DialogHeader>
            <DialogTitle>Conciliar Movimiento con CFDIs</DialogTitle>
            <DialogDescription>
              Selecciona los CFDIs que corresponden a este movimiento bancario
            </DialogDescription>
          </DialogHeader>
          
          {selectedTransaction && (
            <div className="space-y-4 flex-1 overflow-hidden flex flex-col">
              {/* Movement info */}
              <div className="p-4 bg-blue-50 rounded-lg border border-blue-200">
                <div className="flex justify-between items-start">
                  <div>
                    <p className="text-sm font-medium text-blue-700">Movimiento Bancario:</p>
                    <p className="font-medium text-gray-800">{selectedTransaction.descripcion}</p>
                    <p className="text-sm text-gray-500">
                      {format(new Date(selectedTransaction.fecha_movimiento), 'dd/MM/yyyy')}
                    </p>
                  </div>
                  <div className="text-right">
                    <p className="text-sm text-blue-700">Monto:</p>
                    <p className={`text-2xl font-bold font-mono ${selectedTransaction.tipo_movimiento === 'credito' ? 'text-green-600' : 'text-red-600'}`}>
                      ${selectedTransaction.monto.toLocaleString('es-MX', {minimumFractionDigits: 2})}
                      <span className="text-sm ml-1">{getReconciliationTotals().movimientoMoneda}</span>
                    </p>
                    {getReconciliationTotals().movimientoMoneda !== 'MXN' && (
                      <p className="text-sm text-gray-500">
                        ≈ ${getReconciliationTotals().movimientoMontoMXN.toLocaleString('es-MX', {minimumFractionDigits: 2})} MXN
                        <span className="text-xs ml-1">(TC: {getReconciliationTotals().tcUsado.toFixed(4)})</span>
                      </p>
                    )}
                  </div>
                </div>
              </div>

              {/* Balance tracker */}
              {selectedCfdis.length > 0 && (
                <div className="grid grid-cols-3 gap-3">
                  <div className="p-3 bg-gray-100 rounded-lg text-center">
                    <p className="text-xs text-gray-500">Monto Movimiento (en MXN)</p>
                    <p className="font-mono font-bold">${getReconciliationTotals().movimientoMontoMXN.toLocaleString('es-MX', {minimumFractionDigits: 2})}</p>
                    {getReconciliationTotals().movimientoMoneda !== 'MXN' && (
                      <p className="text-xs text-gray-400">
                        ({getReconciliationTotals().movimientoMonto.toLocaleString('es-MX', {minimumFractionDigits: 2})} {getReconciliationTotals().movimientoMoneda})
                      </p>
                    )}
                  </div>
                  <div className="p-3 bg-green-100 rounded-lg text-center">
                    <p className="text-xs text-green-700">CFDIs Seleccionados ({selectedCfdis.length})</p>
                    <p className="font-mono font-bold text-green-700">${getReconciliationTotals().cfdiTotalMXN.toLocaleString('es-MX', {minimumFractionDigits: 2})}</p>
                  </div>
                  <div className={`p-3 rounded-lg text-center ${Math.abs(getReconciliationTotals().diferenciaMXN) < 0.01 ? 'bg-green-100' : 'bg-yellow-100'}`}>
                    <p className="text-xs text-gray-600">Diferencia (MXN)</p>
                    <p className={`font-mono font-bold ${Math.abs(getReconciliationTotals().diferenciaMXN) < 0.01 ? 'text-green-700' : 'text-yellow-700'}`}>
                      ${getReconciliationTotals().diferenciaMXN.toLocaleString('es-MX', {minimumFractionDigits: 2})}
                    </p>
                  </div>
                </div>
              )}

              {/* Selected CFDIs */}
              {selectedCfdis.length > 0 && (
                <div className="p-3 bg-green-50 rounded-lg border border-green-200">
                  <p className="text-sm font-medium text-green-700 mb-2">CFDIs seleccionados:</p>
                  <div className="space-y-1">
                    {selectedCfdis.map(cfdi => (
                      <div key={cfdi.id} className="flex justify-between items-center text-sm bg-white p-2 rounded">
                        <div className="flex items-center gap-2">
                          <button 
                            onClick={() => toggleCfdiSelection(cfdi)}
                            className="text-red-500 hover:text-red-700"
                          >
                            <X size={14} />
                          </button>
                          <span className="font-medium">{cfdi.receptor_nombre || cfdi.emisor_nombre}</span>
                        </div>
                        <span className="font-mono">${cfdi.total?.toLocaleString('es-MX', {minimumFractionDigits: 2})}</span>
                      </div>
                    ))}
                  </div>
                </div>
              )}

              {/* Search CFDIs */}
              <div className="relative">
                <Search size={16} className="absolute left-3 top-1/2 transform -translate-y-1/2 text-gray-400" />
                <Input
                  placeholder="Buscar por cliente, RFC o UUID..."
                  value={cfdiSearchTerm}
                  onChange={(e) => setCfdiSearchTerm(e.target.value)}
                  className="pl-10"
                />
              </div>

              {/* CFDIs list */}
              <div className="flex-1 overflow-y-auto space-y-2 min-h-[200px] max-h-[300px]">
                <p className="text-sm font-medium sticky top-0 bg-white py-1">CFDIs disponibles:</p>
                {cfdis
                  .filter(c => c.estado_conciliacion !== 'conciliado')
                  .filter(c => {
                    if (!cfdiSearchTerm) return true;
                    const search = cfdiSearchTerm.toLowerCase();
                    return (
                      c.receptor_nombre?.toLowerCase().includes(search) ||
                      c.emisor_nombre?.toLowerCase().includes(search) ||
                      c.receptor_rfc?.toLowerCase().includes(search) ||
                      c.emisor_rfc?.toLowerCase().includes(search) ||
                      c.uuid?.toLowerCase().includes(search)
                    );
                  })
                  .length === 0 ? (
                  <p className="text-center text-gray-500 py-4">No hay CFDIs que coincidan</p>
                ) : (
                  cfdis
                    .filter(c => c.estado_conciliacion !== 'conciliado')
                    .filter(c => {
                      if (!cfdiSearchTerm) return true;
                      const search = cfdiSearchTerm.toLowerCase();
                      return (
                        c.receptor_nombre?.toLowerCase().includes(search) ||
                        c.emisor_nombre?.toLowerCase().includes(search) ||
                        c.receptor_rfc?.toLowerCase().includes(search) ||
                        c.emisor_rfc?.toLowerCase().includes(search) ||
                        c.uuid?.toLowerCase().includes(search)
                      );
                    })
                    .map(cfdi => {
                      const isSelected = selectedCfdis.some(c => c.id === cfdi.id);
                      return (
                        <div
                          key={cfdi.id}
                          className={`p-3 border rounded-lg cursor-pointer transition-colors ${
                            isSelected 
                              ? 'bg-green-100 border-green-400' 
                              : 'hover:bg-blue-50 border-gray-200'
                          }`}
                          onClick={() => toggleCfdiSelection(cfdi)}
                        >
                          <div className="flex justify-between items-start">
                            <div className="flex-1">
                              <div className="flex items-center gap-2">
                                <input 
                                  type="checkbox" 
                                  checked={isSelected}
                                  onChange={() => {}}
                                  className="w-4 h-4 text-green-600"
                                />
                                <div>
                                  <p className="font-medium text-gray-800">
                                    {cfdi.tipo_cfdi === 'ingreso' ? (
                                      <span className="text-green-700">Cliente: </span>
                                    ) : (
                                      <span className="text-red-700">Proveedor: </span>
                                    )}
                                    {cfdi.tipo_cfdi === 'ingreso' ? cfdi.receptor_nombre : cfdi.emisor_nombre}
                                  </p>
                                  <p className="text-xs text-gray-500">
                                    RFC: {cfdi.tipo_cfdi === 'ingreso' ? cfdi.receptor_rfc : cfdi.emisor_rfc}
                                  </p>
                                  <p className="text-xs text-gray-400">
                                    {cfdi.tipo_cfdi?.toUpperCase()} | {cfdi.fecha_emision?.slice(0, 10)} | {cfdi.uuid?.slice(0, 8)}...
                                  </p>
                                </div>
                              </div>
                            </div>
                            <div className="text-right">
                              <p className={`font-mono font-bold ${cfdi.tipo_cfdi === 'ingreso' ? 'text-green-600' : 'text-red-600'}`}>
                                ${cfdi.total?.toLocaleString('es-MX', {minimumFractionDigits: 2})}
                              </p>
                              <p className="text-xs text-gray-500">{cfdi.moneda}</p>
                            </div>
                          </div>
                        </div>
                      );
                    })
                )}
              </div>
            </div>
          )}

          <DialogFooter className="flex justify-between items-center border-t pt-4">
            <div className="text-sm text-gray-500">
              {selectedCfdis.length > 0 && (
                <span>
                  {Math.abs(getReconciliationTotals().diferenciaMXN) < 0.01 ? (
                    <span className="text-green-600 font-medium">✓ Los montos cuadran perfectamente</span>
                  ) : (
                    <span className="text-yellow-600">Diferencia de ${Math.abs(getReconciliationTotals().diferenciaMXN).toLocaleString('es-MX', {minimumFractionDigits: 2})} MXN</span>
                  )}
                </span>
              )}
            </div>
            <div className="flex gap-2">
              <Button variant="outline" onClick={() => {
                setReconcileDialogOpen(false);
                setSelectedTransaction(null);
                setSelectedCfdis([]);
                setCfdiSearchTerm('');
              }}>
                Cancelar
              </Button>
              <Button 
                onClick={handleConfirmReconciliation}
                disabled={selectedCfdis.length === 0}
                className="bg-green-600 hover:bg-green-700"
              >
                Confirmar Conciliación ({selectedCfdis.length})
              </Button>
            </div>
          </DialogFooter>
        </DialogContent>
      </Dialog>

      {/* Import Dialog - Select Account */}
      <Dialog open={importDialogOpen} onOpenChange={(open) => {
        if (!open && !importing) {
          setImportDialogOpen(false);
          setImportFile(null);
          setImportAccountId('');
        }
      }}>
        <DialogContent className="max-w-md">
          <DialogHeader>
            <DialogTitle className="flex items-center gap-2">
              <Upload size={20} />
              Importar Estado de Cuenta
            </DialogTitle>
            <DialogDescription>
              Selecciona la cuenta bancaria donde se registrarán los movimientos
            </DialogDescription>
          </DialogHeader>
          
          <div className="space-y-4 py-4">
            {importFile && (
              <div className="flex items-center gap-2 p-3 bg-blue-50 rounded-lg">
                <FileSpreadsheet size={20} className="text-blue-600" />
                <div className="flex-1 min-w-0">
                  <p className="font-medium text-sm truncate">{importFile.name}</p>
                  <p className="text-xs text-gray-500">{(importFile.size / 1024).toFixed(1)} KB</p>
                </div>
              </div>
            )}

            <div className="space-y-2">
              <Label className="text-sm font-medium">Cuenta Bancaria Destino *</Label>
              <Select value={importAccountId} onValueChange={setImportAccountId}>
                <SelectTrigger>
                  <SelectValue placeholder="Seleccionar cuenta..." />
                </SelectTrigger>
                <SelectContent>
                  {bankAccounts.map(acc => (
                    <SelectItem key={acc.id} value={acc.id}>
                      <div className="flex items-center gap-2">
                        <Building2 size={14} className="text-gray-500" />
                        <span className="font-medium">{acc.banco}</span>
                        <span className="text-gray-500">-</span>
                        <span>{acc.nombre}</span>
                        <span className={`ml-2 text-xs px-2 py-0.5 rounded ${
                          acc.moneda === 'USD' ? 'bg-blue-100 text-blue-700' :
                          acc.moneda === 'EUR' ? 'bg-purple-100 text-purple-700' :
                          'bg-gray-100 text-gray-700'
                        }`}>
                          {acc.moneda}
                        </span>
                      </div>
                    </SelectItem>
                  ))}
                </SelectContent>
              </Select>
              <p className="text-xs text-gray-500">
                Los movimientos se importarán a esta cuenta. Asegúrate de seleccionar la cuenta correcta según la moneda del estado de cuenta.
              </p>
            </div>

            <div className="bg-yellow-50 border border-yellow-200 rounded-lg p-3">
              <p className="text-sm text-yellow-800">
                <strong>Importante:</strong> Verifica que la moneda del archivo coincida con la cuenta seleccionada.
              </p>
            </div>
          </div>

          <DialogFooter>
            <Button 
              variant="outline" 
              onClick={() => {
                setImportDialogOpen(false);
                setImportFile(null);
                setImportAccountId('');
              }}
              disabled={importing}
            >
              Cancelar
            </Button>
            <Button 
              onClick={processImport} 
              disabled={!importAccountId || importing}
              className="bg-[#0F172A]"
            >
              {importing ? (
                <>
                  <RefreshCw size={16} className="mr-2 animate-spin" />
                  Importando...
                </>
              ) : (
                <>
                  <Upload size={16} className="mr-2" />
                  Importar Movimientos
                </>
              )}
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>

      {/* Import PDF Dialog */}
      <Dialog open={importPdfDialogOpen} onOpenChange={(open) => {
        if (!open && !importingPdf && !loadingPreview) {
          setImportPdfDialogOpen(false);
          setPdfFile(null);
          setPdfAccountId('');
          setPdfPreview(null);
        }
      }}>
        <DialogContent className="max-w-2xl max-h-[90vh] overflow-y-auto">
          <DialogHeader>
            <DialogTitle className="flex items-center gap-2">
              <FileText size={20} className="text-red-600" />
              Importar Estado de Cuenta PDF
            </DialogTitle>
            <DialogDescription>
              Vista previa de los movimientos detectados en tu estado de cuenta
            </DialogDescription>
          </DialogHeader>
          
          <div className="space-y-4 py-4">
            {/* File Info */}
            {pdfFile && (
              <div className="flex items-center gap-2 p-3 bg-red-50 rounded-lg border border-red-200">
                <FileText size={20} className="text-red-600" />
                <div className="flex-1 min-w-0">
                  <p className="font-medium text-sm truncate">{pdfFile.name}</p>
                  <p className="text-xs text-gray-500">{(pdfFile.size / 1024).toFixed(1)} KB</p>
                </div>
                {pdfPreview?.banco_detectado && (
                  <span className="px-2 py-1 bg-green-100 text-green-700 text-xs font-medium rounded">
                    {pdfPreview.banco_detectado}
                  </span>
                )}
              </div>
            )}

            {/* Loading state */}
            {loadingPreview && (
              <div className="flex flex-col items-center justify-center py-8">
                <RefreshCw size={32} className="text-red-600 animate-spin mb-3" />
                <p className="text-sm text-gray-600">Analizando PDF...</p>
              </div>
            )}

            {/* Preview Results */}
            {pdfPreview && !loadingPreview && (
              <>
                {/* Summary Cards */}
                {pdfPreview.total_movimientos > 0 ? (
                  <div className="grid grid-cols-4 gap-3">
                    <div className="bg-blue-50 rounded-lg p-3 text-center">
                      <p className="text-2xl font-bold text-blue-700">{pdfPreview.total_movimientos}</p>
                      <p className="text-xs text-blue-600">Movimientos</p>
                    </div>
                    <div className="bg-green-50 rounded-lg p-3 text-center">
                      <p className="text-lg font-bold text-green-700">
                        ${pdfPreview.total_depositos?.toLocaleString('es-MX', {minimumFractionDigits: 2})}
                      </p>
                      <p className="text-xs text-green-600">Depósitos</p>
                    </div>
                    <div className="bg-red-50 rounded-lg p-3 text-center">
                      <p className="text-lg font-bold text-red-700">
                        ${pdfPreview.total_retiros?.toLocaleString('es-MX', {minimumFractionDigits: 2})}
                      </p>
                      <p className="text-xs text-red-600">Retiros</p>
                    </div>
                    <div className="bg-purple-50 rounded-lg p-3 text-center">
                      <p className={`text-lg font-bold ${pdfPreview.flujo_neto >= 0 ? 'text-green-700' : 'text-red-700'}`}>
                        ${Math.abs(pdfPreview.flujo_neto || 0).toLocaleString('es-MX', {minimumFractionDigits: 2})}
                      </p>
                      <p className="text-xs text-purple-600">Flujo Neto</p>
                    </div>
                  </div>
                ) : (
                  <div className="bg-yellow-50 border border-yellow-200 rounded-lg p-4 text-center">
                    <AlertCircle size={32} className="text-yellow-600 mx-auto mb-2" />
                    <p className="text-sm text-yellow-800 font-medium">No se encontraron movimientos</p>
                    <p className="text-xs text-yellow-700 mt-1">
                      El formato del PDF no es compatible. Intenta con la plantilla Excel.
                    </p>
                  </div>
                )}

                {/* Transaction Preview Table */}
                {pdfPreview.transactions?.length > 0 && (
                  <div className="border rounded-lg overflow-hidden">
                    <div className="bg-gray-50 px-3 py-2 border-b">
                      <p className="text-sm font-medium text-gray-700">Vista Previa de Movimientos</p>
                    </div>
                    <div className="max-h-60 overflow-y-auto">
                      <table className="w-full text-sm">
                        <thead className="bg-gray-50 sticky top-0">
                          <tr>
                            <th className="px-3 py-2 text-left text-xs font-medium text-gray-500">Fecha</th>
                            <th className="px-3 py-2 text-left text-xs font-medium text-gray-500">Descripción</th>
                            <th className="px-3 py-2 text-right text-xs font-medium text-gray-500">Monto</th>
                            <th className="px-3 py-2 text-center text-xs font-medium text-gray-500">Tipo</th>
                          </tr>
                        </thead>
                        <tbody className="divide-y">
                          {pdfPreview.transactions.slice(0, 15).map((txn, idx) => (
                            <tr key={idx} className="hover:bg-gray-50">
                              <td className="px-3 py-2 text-xs text-gray-600 whitespace-nowrap">
                                {txn.fecha}
                              </td>
                              <td className="px-3 py-2 text-xs text-gray-900 truncate max-w-[200px]">
                                {txn.descripcion}
                              </td>
                              <td className={`px-3 py-2 text-xs font-medium text-right ${
                                txn.tipo === 'credito' ? 'text-green-600' : 'text-red-600'
                              }`}>
                                {txn.tipo === 'credito' ? '+' : '-'}${txn.monto?.toLocaleString('es-MX', {minimumFractionDigits: 2})}
                              </td>
                              <td className="px-3 py-2 text-center">
                                <span className={`px-2 py-0.5 text-xs rounded ${
                                  txn.tipo === 'credito' 
                                    ? 'bg-green-100 text-green-700' 
                                    : 'bg-red-100 text-red-700'
                                }`}>
                                  {txn.tipo_display}
                                </span>
                              </td>
                            </tr>
                          ))}
                        </tbody>
                      </table>
                      {pdfPreview.transactions.length > 15 && (
                        <div className="px-3 py-2 bg-gray-50 text-center text-xs text-gray-500">
                          ... y {pdfPreview.transactions.length - 15} movimientos más
                        </div>
                      )}
                    </div>
                  </div>
                )}
              </>
            )}

            {/* Account Selection - Only show if preview has transactions */}
            {pdfPreview?.total_movimientos > 0 && (
              <div className="space-y-2 pt-2 border-t">
                <Label className="text-sm font-medium">Cuenta Bancaria Destino *</Label>
                <Select value={pdfAccountId} onValueChange={setPdfAccountId}>
                  <SelectTrigger>
                    <SelectValue placeholder="Seleccionar cuenta..." />
                  </SelectTrigger>
                  <SelectContent>
                    {bankAccounts.map(acc => (
                      <SelectItem key={acc.id} value={acc.id}>
                        <div className="flex items-center gap-2">
                          <Building2 size={14} className="text-gray-500" />
                          <span className="font-medium">{acc.banco}</span>
                          <span className="text-gray-500">-</span>
                          <span>{acc.nombre}</span>
                          <span className={`ml-2 text-xs px-2 py-0.5 rounded ${
                            acc.moneda === 'USD' ? 'bg-blue-100 text-blue-700' :
                            acc.moneda === 'EUR' ? 'bg-purple-100 text-purple-700' :
                            'bg-gray-100 text-gray-700'
                          }`}>
                            {acc.moneda}
                          </span>
                        </div>
                      </SelectItem>
                    ))}
                  </SelectContent>
                </Select>
                <p className="text-xs text-gray-500">
                  Los movimientos duplicados serán omitidos automáticamente.
                </p>
              </div>
            )}
          </div>

          <DialogFooter>
            <Button 
              variant="outline" 
              onClick={() => {
                setImportPdfDialogOpen(false);
                setPdfFile(null);
                setPdfAccountId('');
                setPdfPreview(null);
              }}
              disabled={importingPdf || loadingPreview}
            >
              Cancelar
            </Button>
            <Button 
              onClick={processPdfImport} 
              disabled={!pdfAccountId || importingPdf || loadingPreview || !pdfPreview?.total_movimientos}
              className="bg-red-600 hover:bg-red-700"
            >
              {importingPdf ? (
                <>
                  <RefreshCw size={16} className="mr-2 animate-spin" />
                  Importando...
                </>
              ) : (
                <>
                  <Check size={16} className="mr-2" />
                  Confirmar Importación ({pdfPreview?.total_movimientos || 0})
                </>
              )}
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>

      {/* Edit Transaction Dialog */}
      <Dialog open={editDialogOpen} onOpenChange={(open) => {
        if (!open) {
          setEditDialogOpen(false);
          setEditingTransaction(null);
        }
      }}>
        <DialogContent className="max-w-lg">
          <DialogHeader>
            <DialogTitle className="flex items-center gap-2">
              <Pencil size={20} />
              Editar Movimiento Bancario
            </DialogTitle>
            <DialogDescription>
              Modifica los datos del movimiento seleccionado
            </DialogDescription>
          </DialogHeader>
          
          <form onSubmit={handleUpdateTransaction} className="space-y-4 py-2">
            <div className="space-y-2">
              <Label>Cuenta Bancaria</Label>
              <Select 
                value={editFormData.bank_account_id} 
                onValueChange={(v) => setEditFormData({...editFormData, bank_account_id: v})}
              >
                <SelectTrigger>
                  <SelectValue placeholder="Seleccionar cuenta..." />
                </SelectTrigger>
                <SelectContent>
                  {bankAccounts.map(acc => (
                    <SelectItem key={acc.id} value={acc.id}>
                      <div className="flex items-center gap-2">
                        <Building2 size={14} />
                        {acc.banco} - {acc.nombre} ({acc.moneda})
                      </div>
                    </SelectItem>
                  ))}
                </SelectContent>
              </Select>
            </div>

            <div className="space-y-2">
              <Label>Descripción</Label>
              <Input
                value={editFormData.descripcion}
                onChange={(e) => setEditFormData({...editFormData, descripcion: e.target.value})}
                required
              />
            </div>

            <div className="grid grid-cols-2 gap-4">
              <div className="space-y-2">
                <Label>Monto</Label>
                <Input
                  type="number"
                  step="0.01"
                  value={editFormData.monto}
                  onChange={(e) => setEditFormData({...editFormData, monto: e.target.value})}
                  required
                />
              </div>
              <div className="space-y-2">
                <Label>Tipo de Movimiento</Label>
                <Select 
                  value={editFormData.tipo_movimiento} 
                  onValueChange={(v) => setEditFormData({...editFormData, tipo_movimiento: v})}
                >
                  <SelectTrigger>
                    <SelectValue />
                  </SelectTrigger>
                  <SelectContent>
                    <SelectItem value="credito">Depósito (Crédito)</SelectItem>
                    <SelectItem value="debito">Retiro (Débito)</SelectItem>
                  </SelectContent>
                </Select>
              </div>
            </div>

            <div className="grid grid-cols-2 gap-4">
              <div className="space-y-2">
                <Label>Fecha Movimiento</Label>
                <Input
                  type="datetime-local"
                  value={editFormData.fecha_movimiento}
                  onChange={(e) => setEditFormData({...editFormData, fecha_movimiento: e.target.value})}
                  required
                />
              </div>
              <div className="space-y-2">
                <Label>Referencia</Label>
                <Input
                  value={editFormData.referencia}
                  onChange={(e) => setEditFormData({...editFormData, referencia: e.target.value})}
                />
              </div>
            </div>

            <div className="space-y-2">
              <Label>Notas</Label>
              <Input
                value={editFormData.notas}
                onChange={(e) => setEditFormData({...editFormData, notas: e.target.value})}
                placeholder="Notas adicionales..."
              />
            </div>

            <DialogFooter>
              <Button type="button" variant="outline" onClick={() => setEditDialogOpen(false)}>
                Cancelar
              </Button>
              <Button type="submit" className="bg-[#0F172A]">
                Guardar Cambios
              </Button>
            </DialogFooter>
          </form>
        </DialogContent>
      </Dialog>

      {/* Sin UUID Dialog - Register expense/income without CFDI */}
      <Dialog open={sinUUIDDialogOpen} onOpenChange={setSinUUIDDialogOpen}>
        <DialogContent className="max-w-lg">
          <DialogHeader>
            <DialogTitle className="flex items-center gap-2">
              <AlertCircle size={20} className="text-orange-500" />
              Registrar Movimiento Sin UUID
            </DialogTitle>
            <DialogDescription>
              Registra este movimiento como gasto o ingreso sin factura CFDI.
              Se creará automáticamente un registro en Cobranza y Pagos.
            </DialogDescription>
          </DialogHeader>
          
          {sinUUIDTransaction && (
            <div className="space-y-4">
              {/* Transaction Summary */}
              <div className="p-3 bg-gray-50 rounded-lg border">
                <div className="flex justify-between items-center">
                  <div>
                    <div className="font-medium text-sm">{sinUUIDTransaction.descripcion?.substring(0, 50)}</div>
                    <div className="text-xs text-gray-500">
                      {sinUUIDTransaction.fecha_movimiento ? format(new Date(sinUUIDTransaction.fecha_movimiento), 'dd MMM yyyy', { locale: es }) : ''}
                    </div>
                  </div>
                  <div className={`text-lg font-bold ${sinUUIDTransaction.tipo_movimiento === 'credito' ? 'text-green-600' : 'text-red-600'}`}>
                    {sinUUIDTransaction.tipo_movimiento === 'credito' ? '+' : '-'}
                    ${sinUUIDTransaction.monto?.toLocaleString('es-MX', {minimumFractionDigits: 2})} {sinUUIDTransaction.moneda || 'MXN'}
                  </div>
                </div>
              </div>

              {/* Type Selection */}
              <div className="space-y-2">
                <Label>Tipo de Conciliación</Label>
                <Select 
                  value={sinUUIDFormData.tipo_conciliacion} 
                  onValueChange={(v) => setSinUUIDFormData({...sinUUIDFormData, tipo_conciliacion: v})}
                >
                  <SelectTrigger>
                    <SelectValue />
                  </SelectTrigger>
                  <SelectContent>
                    <SelectItem value="sin_uuid">
                      <div className="flex items-center gap-2">
                        <span className="w-3 h-3 rounded-full bg-orange-500"></span>
                        Sin UUID - Gasto/Ingreso sin factura
                      </div>
                    </SelectItem>
                    <SelectItem value="no_relacionado">
                      <div className="flex items-center gap-2">
                        <span className="w-3 h-3 rounded-full bg-gray-400"></span>
                        No Relacionado - Movimiento interno
                      </div>
                    </SelectItem>
                  </SelectContent>
                </Select>
              </div>

              {/* Category Selection */}
              <div className="space-y-2">
                <Label>Categoría</Label>
                <Select 
                  value={sinUUIDFormData.categoria} 
                  onValueChange={(v) => setSinUUIDFormData({...sinUUIDFormData, categoria: v})}
                >
                  <SelectTrigger>
                    <SelectValue placeholder="Seleccionar categoría..." />
                  </SelectTrigger>
                  <SelectContent>
                    {EXPENSE_CATEGORIES.map(cat => (
                      <SelectItem key={cat.value} value={cat.value}>
                        {cat.label}
                      </SelectItem>
                    ))}
                  </SelectContent>
                </Select>
              </div>

              {/* Concept */}
              <div className="space-y-2">
                <Label>Concepto</Label>
                <Input
                  value={sinUUIDFormData.concepto}
                  onChange={(e) => setSinUUIDFormData({...sinUUIDFormData, concepto: e.target.value})}
                  placeholder="Descripción del gasto/ingreso..."
                />
              </div>

              {/* Notes */}
              <div className="space-y-2">
                <Label>Notas (opcional)</Label>
                <Input
                  value={sinUUIDFormData.notas}
                  onChange={(e) => setSinUUIDFormData({...sinUUIDFormData, notas: e.target.value})}
                  placeholder="Notas adicionales..."
                />
              </div>

              {/* Info banner */}
              <div className="p-3 bg-blue-50 border border-blue-200 rounded-lg text-sm text-blue-800">
                <strong>📌 Nota:</strong> Este movimiento se registrará como {sinUUIDTransaction.tipo_movimiento === 'credito' ? 'cobro' : 'pago'} 
                {' '}en el módulo &quot;Cobranza y Pagos&quot; para mantener el control de flujo de efectivo.
              </div>

              <DialogFooter>
                <Button type="button" variant="outline" onClick={() => setSinUUIDDialogOpen(false)}>
                  Cancelar
                </Button>
                <Button 
                  type="button" 
                  className="bg-orange-600 hover:bg-orange-700"
                  onClick={handleMarkWithoutUUID}
                >
                  Registrar y Conciliar
                </Button>
              </DialogFooter>
            </div>
          )}
        </DialogContent>
      </Dialog>
    </div>
  );
};

export default BankStatementsModule;
