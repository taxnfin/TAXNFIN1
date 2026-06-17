import { useState, useEffect } from 'react';
import api from '@/api/axios';
import { getERPEndpoints } from '@/utils/erpHelper';
import PageHeader from '@/components/PageHeader';
import { Button } from '@/components/ui/button';
import { Input } from '@/components/ui/input';
import { Label } from '@/components/ui/label';
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from '@/components/ui/select';
import { Popover, PopoverContent, PopoverTrigger } from '@/components/ui/popover';
import { Command, CommandEmpty, CommandGroup, CommandInput, CommandItem, CommandList, CommandSeparator } from '@/components/ui/command';
import { Dialog, DialogContent, DialogDescription, DialogFooter, DialogHeader, DialogTitle, DialogTrigger } from '@/components/ui/dialog';
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card';
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from '@/components/ui/table';
import { toast } from 'sonner';
import { Plus, Check, CreditCard, TrendingUp, TrendingDown, CheckCircle2, FileText, User, Building2, AlertCircle, Trash2, AlertTriangle, Eye, EyeOff, Download, Edit, Link2, RefreshCw, Upload, ChevronDown} from 'lucide-react';
import { format, addDays } from 'date-fns';
import { Checkbox } from '@/components/ui/checkbox';
import { AlertDialog, AlertDialogAction, AlertDialogCancel, AlertDialogContent, AlertDialogDescription, AlertDialogFooter, AlertDialogHeader, AlertDialogTitle } from '@/components/ui/alert-dialog';
import { Switch } from '@/components/ui/switch';
import { exportPayments } from '@/utils/excelExport';
import PDFInvoiceUploader from '@/components/PDFInvoiceUploader';

const PAYMENT_METHODS = [
  { value: 'transferencia', label: 'Transferencia' },
  { value: 'spei', label: 'SPEI' },
  { value: 'cheque', label: 'Cheque' },
  { value: 'efectivo', label: 'Efectivo' },
  { value: 'tarjeta', label: 'Tarjeta' },
  { value: 'domiciliacion', label: 'Domiciliación' },
];

const PAYMENT_STATUS = {
  pendiente: { label: 'Pendiente', color: 'bg-yellow-100 text-yellow-800' },
  completado: { label: 'Completado', color: 'bg-green-100 text-green-800' },
  cancelado: { label: 'Cancelado', color: 'bg-red-100 text-red-800' },
  vencido: { label: 'Vencido', color: 'bg-orange-100 text-orange-800' },
};

const PaymentsModule = () => {
  const [payments, setPayments] = useState([]);
  const [summary, setSummary] = useState(null);
  const [breakdown, setBreakdown] = useState(null);
  const [agingSummary, setAgingSummary] = useState(null);
  const [loading, setLoading] = useState(true);
  const [dialogOpen, setDialogOpen] = useState(false);
  const [editDialogOpen, setEditDialogOpen] = useState(false);
  const [viewDialogOpen, setViewDialogOpen] = useState(false);
  const [selectedPayment, setSelectedPayment] = useState(null);
  const [filterTipo, setFilterTipo] = useState('all');
  const [filterEstatus, setFilterEstatus] = useState('all');
  const [filterEsReal, setFilterEsReal] = useState('all');
  const [filterCategoria, setFilterCategoria] = useState('all');
  const [filterFechaDesde, setFilterFechaDesde] = useState('');
  const [filterFechaHasta, setFilterFechaHasta] = useState('');
  const [deleteConfirm, setDeleteConfirm] = useState({ open: false, payment: null });
  const [bankTransactions, setBankTransactions] = useState([]);
  const [bankAccounts, setBankAccounts] = useState([]);
  const [fxRates, setFxRates] = useState({ USD: 17.5, EUR: 19.0 });
  const [customTc, setCustomTc] = useState(''); // Custom exchange rate for current transaction
  const [useCustomTc, setUseCustomTc] = useState(false);
  const [activeTab, setActiveTab] = useState('todos');
  const [syncingContalink, setSyncingContalink] = useState(false);
  const [syncDateDialogOpen, setSyncDateDialogOpen] = useState(false);
  const [syncDateFrom, setSyncDateFrom] = useState('');
  const [syncDateTo, setSyncDateTo] = useState('');
  const [syncResult, setSyncResult] = useState(null); // { ok: bool, message: string } | null
  const [importMenuOpen, setImportMenuOpen] = useState(false);
  const [masMenuOpen, setMasMenuOpen] = useState(false);
  const [uploadingHistorico, setUploadingHistorico] = useState(false); // 'real', 'proyeccion', 'breakdown'
  const [autoCategorizing, setAutoCategorizing] = useState(false);
  const [syncingCategories, setSyncingCategories] = useState(false);
  
  // Import from bank movements dialog
  const [importBankDialogOpen, setImportBankDialogOpen] = useState(false);
  const [selectedBankMovements, setSelectedBankMovements] = useState([]);
  const [importingMovements, setImportingMovements] = useState(false);
  const [autoMatchDialogOpen, setAutoMatchDialogOpen] = useState(false);
  const [matchResults, setMatchResults] = useState([]);
  const [matchCandidates, setMatchCandidates] = useState([]);
  const [selectedCandidate, setSelectedCandidate] = useState(null);
  const [reconciling, setReconciling] = useState(false);
  const [newPaymentId, setNewPaymentId] = useState(null);
  
  // PDF Invoice Uploader state
  const [pdfUploaderOpen, setPdfUploaderOpen] = useState(false);

  // Delete by date range
  const [deleteRangeOpen, setDeleteRangeOpen] = useState(false);
  const [deleteRangeFrom, setDeleteRangeFrom] = useState('');
  const [deleteRangeTo, setDeleteRangeTo] = useState('');
  const [deleteRangePreview, setDeleteRangePreview] = useState(null); // { count, monto_total }
  const [deleteRangePreviewing, setDeleteRangePreviewing] = useState(false);
  const [deleteRangeDeleting, setDeleteRangeDeleting] = useState(false);
  
  // States for clients/vendors and invoices
  const [customers, setCustomers] = useState([]);
  const [vendors, setVendors] = useState([]);
  const [categories, setCategories] = useState([]); // For export with category names
  const [pendingCfdis, setPendingCfdis] = useState([]);
  const [selectedParty, setSelectedParty] = useState('');
  const [selectedCfdis, setSelectedCfdis] = useState([]); // Multiple selection
  const [partyDropdownOpen, setPartyDropdownOpen] = useState(false);
  const [partySearch, setPartySearch] = useState('');
  const [showNewPartyForm, setShowNewPartyForm] = useState(false);
  const [newPartyForm, setNewPartyForm] = useState({ nombre: '', rfc: '', email: '', telefono: '' });
  const [savingNewParty, setSavingNewParty] = useState(false);
  const [useCustomAmount, setUseCustomAmount] = useState(false);
  
  const [formData, setFormData] = useState({
    tipo: 'pago',
    concepto: '',
    monto: '',
    moneda: 'MXN',
    metodo_pago: 'transferencia',
    fecha_vencimiento: format(addDays(new Date(), 7), "yyyy-MM-dd'T'HH:mm"),
    beneficiario: '',
    referencia: '',
    domiciliacion_activa: false,
    es_real: true, // true = Real, false = Proyección
    cfdi_ids: [],
    customer_id: null,
    vendor_id: null,
    bank_account_id: null
  });

  useEffect(() => {
    loadData();
    loadPartiesData();
    loadBankTransactions();
    loadBankAccounts();
    loadFxRates();
  }, [filterTipo, filterEstatus, filterEsReal, filterFechaDesde, filterFechaHasta]);

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

  const loadBankAccounts = async () => {
    try {
      const res = await api.get('/bank-accounts');
      setBankAccounts(res.data);
    } catch (error) {
      console.error('Error loading bank accounts:', error);
    }
  };

  const convertToMXN = (monto, moneda) => {
    if (!monto) return 0;
    if (moneda === 'MXN') return monto;
    if (moneda === 'USD') return monto * (fxRates.USD || 17.5);
    if (moneda === 'EUR') return monto * (fxRates.EUR || 19.0);
    return monto;
  };

  const loadBankTransactions = async () => {
    try {
      const res = await api.get('/bank-transactions?limit=500');
      setBankTransactions(res.data.filter(t => !t.conciliado));
    } catch (error) {
      console.error('Error loading bank transactions:', error);
    }
  };

  const loadData = async () => {
    try {
      // Use the new endpoint that includes real reconciliation status
      let url = '/payments/with-reconciliation-status?limit=1000';
      if (filterTipo !== 'all') url += `&tipo=${filterTipo}`;
      if (filterFechaDesde) url += `&fecha_desde=${filterFechaDesde}`;
      if (filterFechaHasta) url += `&fecha_hasta=${filterFechaHasta}`;
      
      const [paymentsRes, summaryRes, breakdownRes, bankTxnsRes, agingRes] = await Promise.all([
        api.get(url),
        api.get('/payments/summary'),
        api.get('/payments/breakdown'),
        api.get('/bank-transactions?limit=500'),
        api.get(getERPEndpoints().agingSummaryEndpoint).catch(() => ({ data: null }))
      ]);
      
      // Build set of reconciled bank transaction IDs
      const bankTxns = bankTxnsRes.data || [];
      const reconciledTxnIds = new Set(bankTxns.filter(t => t.conciliado === true).map(t => t.id));
      
      // Filter payments based on actual reconciliation status
      let filteredPayments = paymentsRes.data;
      
      // Apply status filter based on REAL status (estado_real), not stored estatus
      if (filterEstatus !== 'all') {
        filteredPayments = filteredPayments.filter(p => {
          const realStatus = p.estado_real || p.estatus;
          return realStatus === filterEstatus;
        });
      }
      
      // Apply es_real filter
      if (filterEsReal !== 'all') {
        filteredPayments = filteredPayments.filter(p => {
          if (filterEsReal === 'real') return p.es_real === true;
          if (filterEsReal === 'proyeccion') return p.es_real === false;
          return true;
        });
      }
      
      // Apply date filters
      if (filterFechaDesde) {
        filteredPayments = filteredPayments.filter(p => {
          const fecha = p.fecha_vencimiento || p.fecha_pago;
          return fecha && new Date(fecha) >= new Date(filterFechaDesde);
        });
      }
      if (filterFechaHasta) {
        filteredPayments = filteredPayments.filter(p => {
          const fecha = p.fecha_vencimiento || p.fecha_pago;
          return fecha && new Date(fecha) <= new Date(filterFechaHasta);
        });
      }
      
      setPayments(filteredPayments);
      setSummary(summaryRes.data || {});
      setBreakdown(breakdownRes.data || {});
      setAgingSummary(agingRes?.data || null);
    } catch (error) {
      toast.error('Error cargando pagos');
    } finally {
      setLoading(false);
    }
  };

  const loadCategories = async () => {
    try {
      const res = await api.get('/cashflow-sync/categories');
      setCategories(res.data);
    } catch (error) {
      console.error('Error loading categories:', error);
    }
  };

  const loadPartiesData = async () => {
    try {
      const [customersRes, vendorsRes] = await Promise.all([
        api.get('/customers'),
        api.get('/vendors'),
      ]);
      const cleanName = (obj) => (obj.nombre || obj.name || '').replace(/\s+/g, ' ').trim();
      setCustomers([...customersRes.data].sort((a, b) => cleanName(a).localeCompare(cleanName(b), 'es', { sensitivity: 'base' })));
      setVendors([...vendorsRes.data].sort((a, b) => cleanName(a).localeCompare(cleanName(b), 'es', { sensitivity: 'base' })));
    } catch (error) {
      console.error('Error loading parties:', error);
    }
    await loadCategories();
  };

  // Load pending CFDIs for selected party
  const loadPendingCfdis = async (partyId, tipo) => {
    try {
      const tipoCfdi = tipo === 'cobro' ? 'ingreso' : 'egreso';
      const res = await api.get(`/cfdi?tipo=${tipoCfdi}&limit=200`);
      
      const partyField = tipo === 'cobro' ? 'customer_id' : 'vendor_id';
      const rfcField = tipo === 'cobro' ? 'receptor_rfc' : 'emisor_rfc';
      
      const parties = tipo === 'cobro' ? customers : vendors;
      const party = parties.find(p => p.id === partyId);
      
      const filtered = res.data.filter(cfdi => {
        const matchesParty = cfdi[partyField] === partyId || 
                            (party && cfdi[rfcField] === party.rfc);
        
        const amountField = tipo === 'cobro' ? 'monto_cobrado' : 'monto_pagado';
        const pendingAmount = cfdi.total - (cfdi[amountField] || 0);
        
        return matchesParty && pendingAmount > 0.01 && cfdi.estado_cancelacion !== 'cancelado';
      }).map(cfdi => ({
        ...cfdi,
        saldo_pendiente: cfdi.total - (tipo === 'cobro' ? (cfdi.monto_cobrado || 0) : (cfdi.monto_pagado || 0))
      }));
      
      setPendingCfdis(filtered);
    } catch (error) {
      console.error('Error loading pending CFDIs:', error);
      setPendingCfdis([]);
    }
  };

  // Handle party selection
  const handlePartyChange = (partyId) => {
    setSelectedParty(partyId);
    setSelectedCfdis([]);
    setFormData(prev => ({
      ...prev,
      [formData.tipo === 'cobro' ? 'customer_id' : 'vendor_id']: partyId,
      cfdi_ids: [],
      monto: ''
    }));
    
    const parties = formData.tipo === 'cobro' ? customers : vendors;
    const party = parties.find(p => p.id === partyId);
    if (party) {
      setFormData(prev => ({ ...prev, beneficiario: party.nombre }));
    }
    
    if (partyId) {
      loadPendingCfdis(partyId, formData.tipo);
    } else {
      setPendingCfdis([]);
    }
  };

  // Handle CFDI selection (multiple)
  const handleCfdiToggle = (cfdi) => {
    const isSelected = selectedCfdis.some(c => c.id === cfdi.id);
    let newSelectedCfdis;
    
    if (isSelected) {
      newSelectedCfdis = selectedCfdis.filter(c => c.id !== cfdi.id);
    } else {
      newSelectedCfdis = [...selectedCfdis, cfdi];
    }
    
    setSelectedCfdis(newSelectedCfdis);
    
    // Calculate total amount from selected CFDIs
    const totalAmount = newSelectedCfdis.reduce((sum, c) => sum + c.saldo_pendiente, 0);
    const cfdiIds = newSelectedCfdis.map(c => c.id);
    const references = newSelectedCfdis.map(c => c.uuid?.substring(0, 8)).join(', ');
    
    setFormData(prev => ({
      ...prev,
      cfdi_ids: cfdiIds,
      monto: totalAmount.toFixed(2),
      referencia: references,
      concepto: newSelectedCfdis.length > 0 
        ? `Pago de ${newSelectedCfdis.length} factura(s)` 
        : ''
    }));
    
    if (!useCustomAmount) {
      setFormData(prev => ({ ...prev, monto: totalAmount.toFixed(2) }));
    }
  };

  // Select all CFDIs
  const handleSelectAll = () => {
    if (selectedCfdis.length === pendingCfdis.length) {
      // Deselect all
      setSelectedCfdis([]);
      setFormData(prev => ({ ...prev, cfdi_ids: [], monto: '', referencia: '', concepto: '' }));
    } else {
      // Select all
      setSelectedCfdis([...pendingCfdis]);
      const totalAmount = pendingCfdis.reduce((sum, c) => sum + c.saldo_pendiente, 0);
      const cfdiIds = pendingCfdis.map(c => c.id);
      const references = pendingCfdis.map(c => c.uuid?.substring(0, 8)).join(', ');
      
      setFormData(prev => ({
        ...prev,
        cfdi_ids: cfdiIds,
        monto: totalAmount.toFixed(2),
        referencia: references,
        concepto: `Pago de ${pendingCfdis.length} factura(s)`
      }));
    }
  };

  // Handle type change
  const handleTipoChange = (tipo) => {
    setFormData(prev => ({
      ...prev,
      tipo,
      customer_id: null,
      vendor_id: null,
      cfdi_ids: [],
      monto: '',
      beneficiario: ''
    }));
    setSelectedParty('');
    setSelectedCfdis([]);
    setPendingCfdis([]);
    setUseCustomAmount(false);
  };

  const handleSubmit = async (e) => {
    e.preventDefault();
    try {
      let createdPaymentId = null;
      
      // Determine the exchange rate to use
      const tcToUse = (useCustomTc && customTc) ? parseFloat(customTc) : (fxRates[formData.moneda] || 1);
      
      // Create payment for each selected CFDI or single payment
      if (selectedCfdis.length > 0 && !useCustomAmount) {
        // Create individual payments for each CFDI
        for (const cfdi of selectedCfdis) {
          const res = await api.post('/payments', {
            ...formData,
            cfdi_id: cfdi.id,
            monto: cfdi.saldo_pendiente,
            tipo_cambio_historico: formData.moneda !== 'MXN' ? tcToUse : null,
            monto_mxn: formData.moneda !== 'MXN' ? cfdi.saldo_pendiente * tcToUse : cfdi.saldo_pendiente,
            concepto: `Pago factura ${cfdi.uuid?.substring(0, 8)}...`,
            referencia: cfdi.uuid
          });
          createdPaymentId = res.data.id;
        }
        toast.success(`${selectedCfdis.length} pago(s) registrado(s)`);
      } else {
        // Single payment with custom or total amount
        const monto = parseFloat(formData.monto);
        const res = await api.post('/payments', {
          ...formData,
          cfdi_id: selectedCfdis.length === 1 ? selectedCfdis[0].id : null,
          monto: monto,
          tipo_cambio_historico: formData.moneda !== 'MXN' ? tcToUse : null,
          monto_mxn: formData.moneda !== 'MXN' ? monto * tcToUse : monto
        });
        createdPaymentId = res.data.id;
        toast.success('Pago registrado');
      }
      
      // Reset custom TC after creating payment
      setUseCustomTc(false);
      setCustomTc('');
      
      setDialogOpen(false);
      loadData();
      
      // If payment is "Real", search for matching bank transactions
      if (formData.es_real && createdPaymentId) {
        searchMatchCandidates(createdPaymentId);
      } else {
        resetForm();
      }
    } catch (error) {
      toast.error(error.response?.data?.detail || 'Error registrando pago');
    }
  };

  // Search for bank transactions that could match this payment
  const searchMatchCandidates = async (paymentId) => {
    try {
      const res = await api.get(`/payments/${paymentId}/match-candidates`);
      if (res.data.candidates && res.data.candidates.length > 0) {
        setMatchCandidates(res.data.candidates);
        setNewPaymentId(paymentId);
        setAutoMatchDialogOpen(true);
      } else {
        toast.info('No se encontraron movimientos bancarios para conciliar');
        resetForm();
      }
    } catch (error) {
      console.error('Error searching match candidates:', error);
      resetForm();
    }
  };

  // Handle auto-reconciliation with user authorization
  const handleAutoReconcile = async () => {
    if (!selectedCandidate || !newPaymentId) return;
    
    setReconciling(true);
    try {
      await api.post(`/payments/${newPaymentId}/auto-reconcile?transaction_id=${selectedCandidate.transaction_id}`);
      toast.success('Pago conciliado con movimiento bancario');
      setAutoMatchDialogOpen(false);
      setSelectedCandidate(null);
      setMatchCandidates([]);
      setNewPaymentId(null);
      loadData();
      loadBankTransactions();
      resetForm();
    } catch (error) {
      toast.error(error.response?.data?.detail || 'Error conciliando pago');
    } finally {
      setReconciling(false);
    }
  };

  const skipReconciliation = () => {
    setAutoMatchDialogOpen(false);
    setSelectedCandidate(null);
    setMatchCandidates([]);
    setNewPaymentId(null);
    resetForm();
    toast.info('Conciliación omitida. Puedes conciliar manualmente después.');
  };

  const resetForm = () => {
    setFormData({
      tipo: 'pago',
      concepto: '',
      monto: '',
      moneda: 'MXN',
      metodo_pago: 'transferencia',
      fecha_vencimiento: format(addDays(new Date(), 7), "yyyy-MM-dd'T'HH:mm"),
      beneficiario: '',
      referencia: '',
      es_real: true,
      domiciliacion_activa: false,
      cfdi_ids: [],
      customer_id: null,
      vendor_id: null
    });
    setSelectedParty('');
    setSelectedCfdis([]);
    setPendingCfdis([]);
    setUseCustomAmount(false);
    setPartySearch('');
    setShowNewPartyForm(false);
    setNewPartyForm({ nombre: '', rfc: '', email: '', telefono: '' });
  };

  const handleCreateNewParty = async () => {
    if (!newPartyForm.nombre.trim()) {
      toast.error('El nombre es requerido');
      return;
    }
    setSavingNewParty(true);
    try {
      const endpoint = formData.tipo === 'cobro' ? '/customers' : '/vendors';
      const res = await api.post(endpoint, { ...newPartyForm });
      const newParty = res.data;
      const sortFn = (a, b) => a.nombre.localeCompare(b.nombre, 'es', { sensitivity: 'base' });
      if (formData.tipo === 'cobro') {
        setCustomers(prev => [...prev, newParty].sort(sortFn));
      } else {
        setVendors(prev => [...prev, newParty].sort(sortFn));
      }
      handlePartyChange(newParty.id);
      setShowNewPartyForm(false);
      setNewPartyForm({ nombre: '', rfc: '', email: '', telefono: '' });
      toast.success(`${formData.tipo === 'cobro' ? 'Cliente' : 'Proveedor'} creado y seleccionado`);
    } catch (err) {
      toast.error(err.response?.data?.detail || 'Error al crear');
    } finally {
      setSavingNewParty(false);
    }
  };

  const handleComplete = async (paymentId) => {
    try {
      await api.post(`/payments/${paymentId}/complete`);
      toast.success('Pago marcado como completado');
      loadData();
    } catch (error) {
      toast.error('Error completando pago');
    }
  };

  const handleDelete = async () => {
    if (!deleteConfirm.payment) return;
    
    try {
      await api.delete(`/payments/${deleteConfirm.payment.id}`);
      toast.success('Pago eliminado');
      setDeleteConfirm({ open: false, payment: null });
      loadData();
    } catch (error) {
      toast.error('Error eliminando pago');
    }
  };

  // Edit payment
  const handleEdit = (payment) => {
    setSelectedPayment(payment);
    setFormData({
      tipo: payment.tipo,
      concepto: payment.concepto || '',
      monto: payment.monto?.toString() || '',
      moneda: payment.moneda || 'MXN',
      metodo_pago: payment.metodo_pago || 'transferencia',
      fecha_vencimiento: payment.fecha_vencimiento ? format(new Date(payment.fecha_vencimiento), "yyyy-MM-dd'T'HH:mm") : '',
      beneficiario: payment.beneficiario || '',
      referencia: payment.referencia || '',
      domiciliacion_activa: payment.domiciliacion_activa || false,
      es_real: payment.es_real !== false,
      cfdi_ids: payment.cfdi_id ? [payment.cfdi_id] : [],
      customer_id: payment.customer_id || null,
      vendor_id: payment.vendor_id || null,
      bank_account_id: payment.bank_account_id || null
    });
    setEditDialogOpen(true);
  };

  const handleUpdatePayment = async (e) => {
    e.preventDefault();
    if (!selectedPayment) return;
    
    try {
      const { cfdi_ids, ...restFormData } = formData;
      await api.put(`/payments/${selectedPayment.id}`, {
        ...restFormData,
        monto: parseFloat(formData.monto),
        cfdi_id: cfdi_ids?.length >= 1 ? cfdi_ids[0] : null,
        metodo_pago: formData.metodo_pago || 'transferencia',
        bank_account_id: formData.bank_account_id || null
      });
      toast.success('Pago actualizado');
      setEditDialogOpen(false);
      setSelectedPayment(null);
      resetForm();
      loadData();
    } catch (error) {
      toast.error(error.response?.data?.detail || 'Error actualizando pago');
    }
  };

  // View payment details
  const handleView = (payment) => {
    setSelectedPayment(payment);
    setViewDialogOpen(true);
  };

  // Auto-match payments with bank transactions
  const handleAutoMatch = async () => {
    const matches = [];
    
    for (const payment of payments.filter(p => !p.conciliado && p.estatus === 'completado')) {
      // Find bank transaction with matching amount (within 0.01)
      const matchingTxn = bankTransactions.find(txn => {
        const montoMatch = Math.abs(txn.monto - payment.monto) < 0.01;
        const tipoMatch = (payment.tipo === 'cobro' && txn.tipo_movimiento === 'credito') ||
                         (payment.tipo === 'pago' && txn.tipo_movimiento === 'debito');
        return montoMatch && tipoMatch && !txn.conciliado;
      });
      
      if (matchingTxn) {
        matches.push({
          payment,
          bankTxn: matchingTxn,
          montoMatch: true
        });
      }
    }
    
    setMatchResults(matches);
    setAutoMatchDialogOpen(true);
  };

  const confirmAutoMatch = async (match) => {
    try {
      // Create reconciliation
      await api.post('/reconciliations', {
        bank_transaction_id: match.bankTxn.id,
        cfdi_id: match.payment.cfdi_id,
        metodo_conciliacion: 'automatica',
        porcentaje_match: 100
      });
      
      // Update payment as conciliado
      await api.put(`/payments/${match.payment.id}`, {
        ...match.payment,
        conciliado: true
      });
      
      toast.success('Conciliación automática exitosa');
      setMatchResults(prev => prev.filter(m => m.payment.id !== match.payment.id));
      loadData();
      loadBankTransactions();
    } catch (error) {
      toast.error('Error en conciliación');
    }
  };

  if (loading) return <div className="p-8">Cargando...</div>;

  const currentParties = formData.tipo === 'cobro' ? customers : vendors;
  const totalSelectedAmount = selectedCfdis.reduce((sum, c) => sum + c.saldo_pendiente, 0);
  const { usaAlegra } = getERPEndpoints();
  const erpLabel = usaAlegra ? 'Alegra' : 'Contalink';
  
  const handleExportPayments = () => {
    if (payments.length === 0) {
      toast.error('No hay pagos para exportar');
      return;
    }
    // Enrich payments with bank account names and pass FX rates
    const enrichedPayments = payments.map(p => ({
      ...p,
      bank_account_name: bankAccounts.find(b => b.id === p.bank_account_id)?.nombre || ''
    }));
    const success = exportPayments(enrichedPayments, fxRates, categories);
    if (success) {
      toast.success(`${payments.length} pagos exportados a Excel`);
    } else {
      toast.error('Error al exportar');
    }
  };

  // Sync all connected ERPs (Contalink + Alegra) to db.payments
  const handleSyncContalink = async (dateFrom = null, dateTo = null) => {
    setSyncingContalink(true);
    const results = [];
    let anySuccess = false;

    try {
      // --- Contalink ---
      // contalinkConfigured = true when Contalink is set up (200 success OR non-400 error).
      // 400 means "not configured" → skip silently.
      let contalinkConfigured = false;
      try {
        const params = new URLSearchParams();
        if (dateFrom) params.append('date_from', dateFrom);
        if (dateTo) params.append('date_to', dateTo);
        const url = `/payments/sync-contalink${params.toString() ? '?' + params.toString() : ''}`;
        const res = await api.post(url);
        results.push(`Contalink: ${res.data.message || 'sincronizado'}`);
        anySuccess = true;
        contalinkConfigured = true;
      } catch (err) {
        const detail = err.response?.data?.detail || '';
        if (err.response?.status !== 400) {
          // Contalink exists but sync failed — still counts as a Contalink company
          results.push(`Contalink: ${detail || 'Error'}`);
          contalinkConfigured = true;
        }
      }

      // --- Alegra — only for companies that do NOT use Contalink ---
      if (!contalinkConfigured) {
        try {
          const statusRes = await api.get('/alegra/status');
          if (statusRes.data?.connected) {
            const res = await api.post('/alegra/sync/payments');
            const stats = res.data?.stats || {};
            results.push(`Alegra: ${stats.created || 0} nuevos, ${stats.updated || 0} actualizados`);
            anySuccess = true;
          }
        } catch (err) {
          const detail = err.response?.data?.detail || '';
          if (detail && !detail.toLowerCase().includes('no está conectado')) {
            results.push(`Alegra: ${detail}`);
          }
        }
      }

      if (anySuccess) {
        const msg = results.join(' · ');
        toast.success(`Sync completado — ${msg}`);
        setSyncResult({ ok: true, message: msg });
        await loadData();
        await loadCategories();
      } else if (results.length > 0) {
        const msg = results.join(' · ');
        toast.error(msg);
        setSyncResult({ ok: false, message: msg });
      } else {
        const msg = 'No hay ERPs configurados. Ve a Integraciones para conectar Contalink o Alegra.';
        toast.warning(msg);
        setSyncResult({ ok: false, message: msg });
      }
    } finally {
      setSyncingContalink(false);
    }
  };

  const handleAutoCategorize = async () => {
    setAutoCategorizing(true);
    try {
      const res = await api.post('/cashflow-sync/auto-categorize?limit=100');
      const { updated, processed, errors } = res.data;
      if (updated > 0) {
        toast.success(`✅ ${updated} de ${processed} pagos categorizados con IA`);
        setPayments([]); // Forzar re-render limpio
        await loadData();
        await loadCategories(); // Asegurar que el select tiene las opciones actualizadas
      } else {
        toast.info('No hay pagos sin categoría o ya están todos categorizados');
      }
      if (errors?.length > 0) {
        toast.warning(`${errors.length} errores al categorizar`);
      }
    } catch (err) {
      toast.error(err.response?.data?.detail || 'Error en auto-categorización');
    } finally {
      setAutoCategorizing(false);
    }
  };

  const handleDeleteAllPayments = async () => {
    if (!window.confirm('⚠️ ¿Estás SEGURO de que quieres ELIMINAR TODOS los pagos y cobranzas?\n\nEsta acción NO se puede deshacer.')) {
      return;
    }
    if (!window.confirm('🚨 ÚLTIMA CONFIRMACIÓN: Se borrarán TODOS los pagos y cobranzas de esta empresa.\n\n¿Continuar?')) {
      return;
    }
    
    try {
      const res = await api.delete('/payments/bulk/all');
      toast.success(res.data.message);
      loadData();
    } catch (error) {
      toast.error(error.response?.data?.detail || 'Error eliminando pagos');
    }
  };

  const handlePreviewDeleteByRange = async () => {
    if (!deleteRangeFrom || !deleteRangeTo) {
      toast.error('Selecciona fecha inicio y fecha fin');
      return;
    }
    if (deleteRangeFrom > deleteRangeTo) {
      toast.error('La fecha inicio debe ser anterior a la fecha fin');
      return;
    }
    setDeleteRangePreviewing(true);
    setDeleteRangePreview(null);
    try {
      const res = await api.get('/payments/by-date-range/preview', {
        params: { fecha_inicio: deleteRangeFrom, fecha_fin: deleteRangeTo },
      });
      setDeleteRangePreview(res.data);
    } catch (error) {
      toast.error(error.response?.data?.detail || 'Error consultando rango');
    } finally {
      setDeleteRangePreviewing(false);
    }
  };

  const handleExecuteDeleteByRange = async () => {
    if (!deleteRangePreview || deleteRangePreview.count === 0) return;
    setDeleteRangeDeleting(true);
    try {
      const res = await api.delete('/payments/by-date-range', {
        params: { fecha_inicio: deleteRangeFrom, fecha_fin: deleteRangeTo },
      });
      toast.success(`Se eliminaron ${res.data.eliminados} movimientos`);
      setDeleteRangeOpen(false);
      setDeleteRangeFrom('');
      setDeleteRangeTo('');
      setDeleteRangePreview(null);
      loadData();
    } catch (error) {
      toast.error(error.response?.data?.detail || 'Error eliminando movimientos');
    } finally {
      setDeleteRangeDeleting(false);
    }
  };

  // Toggle selection of bank movement for import
  const toggleBankMovementSelection = (txnId) => {
    setSelectedBankMovements(prev => 
      prev.includes(txnId) 
        ? prev.filter(id => id !== txnId)
        : [...prev, txnId]
    );
  };

  // Select all visible bank movements
  const selectAllBankMovements = () => {
    const pendingTxns = bankTransactions.filter(t => !t.conciliado);
    if (selectedBankMovements.length === pendingTxns.length) {
      setSelectedBankMovements([]);
    } else {
      setSelectedBankMovements(pendingTxns.map(t => t.id));
    }
  };

  // Import selected bank movements as payments with automatic CFDI matching
  const handleImportBankMovements = async () => {
    if (selectedBankMovements.length === 0) {
      toast.error('Selecciona al menos un movimiento');
      return;
    }

    setImportingMovements(true);
    
    try {
      // Use the new batch endpoint with automatic CFDI matching
      const res = await api.post('/bank-transactions/batch-create-payments', {
        transaction_ids: selectedBankMovements,
        auto_detect: true  // Enable automatic CFDI matching (±60 days, similar amount)
      });
      
      const { created, linked_with_cfdi, errors, message } = res.data;
      
      if (created > 0) {
        if (linked_with_cfdi > 0) {
          toast.success(`${created} ${created === 1 ? 'pago/cobro creado' : 'pagos/cobros creados'}, ${linked_with_cfdi} vinculados automáticamente con CFDI`);
        } else {
          toast.success(`${created} ${created === 1 ? 'pago/cobro creado' : 'pagos/cobros creados'}`);
        }
        loadData();
        loadBankTransactions();
      }
      
      if (errors > 0) {
        toast.error(`${errors} movimientos con error`);
      }
      
    } catch (error) {
      console.error('Error creating payments from bank:', error);
      toast.error(error.response?.data?.detail || 'Error al crear pagos desde movimientos');
    } finally {
      setImportingMovements(false);
      setImportBankDialogOpen(false);
      setSelectedBankMovements([]);
    }
  };

  return (
    <div className="p-8 space-y-6" data-testid="payments-page">
      <div className="flex justify-between items-center">
        <div>
          <PageHeader title="Cobranza y Pagos" subtitle="Gestión de cobros y pagos (reales y proyectados)" />
        </div>
        <div className="flex gap-2 items-center">

          {/* ── DROPDOWN: IMPORTAR ── */}
          <div style={{position:'relative'}}>
            <Button
              variant="outline"
              className="gap-2"
              onClick={() => { setImportMenuOpen(v => !v); setMasMenuOpen(false); }}
            >
              <Upload size={16} />
              Importar
              <ChevronDown size={14} />
            </Button>
            {importMenuOpen && (
              <div
                onMouseLeave={() => setImportMenuOpen(false)}
                style={{
                  position:'absolute', right:0, top:'calc(100% + 6px)',
                  background:'#ffffff', border:'1px solid #e2e8f0',
                  borderRadius:'10px', boxShadow:'0 8px 32px rgba(0,0,0,0.14)',
                  minWidth:'250px', zIndex:9999, padding:'6px'
                }}
              >
                {[
                  { icon:'⬇', label:'Sync ERP (Contalink/Alegra)', sub:'Selecciona rango de fechas', action: () => {
                    setImportMenuOpen(false);
                    const today = new Date().toISOString().split('T')[0];
                    const yearStart = `${new Date().getFullYear()}-01-01`;
                    setSyncDateFrom(yearStart);
                    setSyncDateTo(today);
                    setSyncResult(null);
                    setSyncDateDialogOpen(true);
                  }, loading: syncingContalink },
                  { icon:'📂', label:'Histórico Contalink', sub:'Sube Excel INGR-EGRE de meses anteriores', action: () => { setImportMenuOpen(false); document.getElementById('upload-historico-input').click(); } },
                  { icon:'🏦', label:'Desde Banco', sub:'Importa estado de cuenta bancario', action: () => { setImportMenuOpen(false); setImportBankDialogOpen(true); } },
                  { icon:'📄', label:'Importar PDF', sub:'Facturas o comprobantes en PDF', action: () => { setImportMenuOpen(false); setPdfUploaderOpen(true); } },
                ].map((item, idx) => (
                  <div
                    key={idx}
                    onClick={item.loading ? undefined : item.action}
                    style={{
                      display:'flex', alignItems:'center', gap:'12px',
                      padding:'9px 12px', borderRadius:'7px', cursor: item.loading ? 'default' : 'pointer',
                      opacity: item.loading ? 0.6 : 1, marginBottom:'2px'
                    }}
                    onMouseEnter={e => e.currentTarget.style.background='#F1F5F9'}
                    onMouseLeave={e => e.currentTarget.style.background='transparent'}
                  >
                    <span style={{fontSize:'18px', flexShrink:0}}>{item.icon}</span>
                    <div>
                      <div style={{fontSize:'13px', fontWeight:'600', color:'#1E293B'}}>
                        {item.loading ? '⟳ Sincronizando...' : item.label}
                      </div>
                      <div style={{fontSize:'11px', color:'#64748B', marginTop:'1px'}}>{item.sub}</div>
                    </div>
                  </div>
                ))}
              </div>
            )}
            {/* Input oculto para subir histórico */}
            <input
              id="upload-historico-input"
              type="file"
              accept=".xls,.xlsx"
              style={{display:'none'}}
              onChange={async (e) => {
                const file = e.target.files?.[0];
                if (!file) return;
                setUploadingHistorico(true);
                try {
                  const formData = new FormData();
                  formData.append('file', file);
                  const res = await api.post('/contalink-payments/upload-historico', formData, {
                    headers: {'Content-Type': 'multipart/form-data'}
                  });
                  const d = res.data;
                  toast.success(`✅ ${d.insertados} movimientos importados${d.duplicados > 0 ? ` (${d.duplicados} duplicados omitidos)` : ''}`);
                  loadData();
                } catch(err) {
                  toast.error('Error importando histórico: ' + (err.response?.data?.detail || err.message));
                } finally {
                  setUploadingHistorico(false);
                  e.target.value = '';
                }
              }}
            />
          </div>

          {/* ── DROPDOWN: MÁS ACCIONES ── */}
          <div style={{position:'relative'}}>
            <Button
              variant="outline"
              className="gap-2"
              onClick={() => { setMasMenuOpen(v => !v); setImportMenuOpen(false); }}
            >
              Más
              <ChevronDown size={14} />
            </Button>
            {masMenuOpen && (
              <div
                onMouseLeave={() => setMasMenuOpen(false)}
                style={{
                  position:'absolute', right:0, top:'calc(100% + 6px)',
                  background:'#ffffff', border:'1px solid #e2e8f0',
                  borderRadius:'10px', boxShadow:'0 8px 32px rgba(0,0,0,0.14)',
                  minWidth:'220px', zIndex:9999, padding:'6px'
                }}
              >
                {[
                  { icon:'🤖', label:'Auto-categorizar', sub:'Categoriza con IA', action: () => { setMasMenuOpen(false); handleAutoCategorize(); }, loading: autoCategorizing },
                  { icon:'✅', label:'Auto-Conciliar', sub:'Concilia automáticamente', action: () => { setMasMenuOpen(false); handleAutoMatch(); } },
                  { icon:'📊', label:'Exportar Excel', sub:'Descarga todos los movimientos', action: () => { setMasMenuOpen(false); handleExportPayments(); } },
                  null, // separador
                  { icon:'🗓️', label:'Eliminar por fecha', sub:'Elimina movimientos de un rango', action: () => { setMasMenuOpen(false); setDeleteRangeOpen(true); setDeleteRangePreview(null); }, danger: true },
                  { icon:'🗑️', label:'Borrar Todo', sub:'Elimina todos los registros', action: () => { setMasMenuOpen(false); handleDeleteAllPayments(); }, danger: true },
                ].map((item, idx) => item === null ? (
                  <div key={idx} style={{height:'1px', background:'#E2E8F0', margin:'4px 6px'}} />
                ) : (
                  <div
                    key={idx}
                    onClick={item.loading ? undefined : item.action}
                    style={{
                      display:'flex', alignItems:'center', gap:'12px',
                      padding:'9px 12px', borderRadius:'7px', cursor: item.loading ? 'default' : 'pointer',
                      opacity: item.loading ? 0.6 : 1, marginBottom:'2px'
                    }}
                    onMouseEnter={e => e.currentTarget.style.background= item.danger ? '#FEF2F2' : '#F1F5F9'}
                    onMouseLeave={e => e.currentTarget.style.background='transparent'}
                  >
                    <span style={{fontSize:'18px', flexShrink:0}}>{item.icon}</span>
                    <div>
                      <div style={{fontSize:'13px', fontWeight:'600', color: item.danger ? '#DC2626' : '#1E293B'}}>
                        {item.loading ? '⟳ Procesando...' : item.label}
                      </div>
                      <div style={{fontSize:'11px', color:'#64748B', marginTop:'1px'}}>{item.sub}</div>
                    </div>
                  </div>
                ))}
              </div>
            )}
          </div>

          {/* ── NUEVO PAGO/COBRO ── */}
          <Dialog open={dialogOpen} onOpenChange={(open) => {
            setDialogOpen(open);
            if (!open) resetForm();
          }}>
          <DialogTrigger asChild>
            <Button className="bg-[#0F172A] hover:bg-[#1E293B] gap-2" data-testid="new-payment-button">
              <Plus size={16} />
              Nuevo Pago/Cobro
            </Button>
          </DialogTrigger>
          <DialogContent className="max-w-3xl max-h-[90vh] overflow-y-auto">
            <DialogHeader>
              <DialogTitle>Registrar Pago/Cobro</DialogTitle>
              <DialogDescription>Selecciona las facturas pendientes y registra el pago</DialogDescription>
            </DialogHeader>
            <form onSubmit={handleSubmit} className="space-y-4">
              {/* Es Real o Proyección */}
              <div className="p-4 bg-gray-50 rounded-lg border">
                <div className="flex items-center justify-between">
                  <div className="flex items-center gap-3">
                    {formData.es_real ? (
                      <Eye size={20} className="text-green-600" />
                    ) : (
                      <EyeOff size={20} className="text-blue-600" />
                    )}
                    <div>
                      <Label className="text-base font-semibold">
                        {formData.es_real ? 'Movimiento Real' : 'Proyección'}
                      </Label>
                      <p className="text-xs text-gray-500">
                        {formData.es_real 
                          ? 'Este pago/cobro ya se realizó o está confirmado'
                          : 'Este pago/cobro es estimado o proyectado'
                        }
                      </p>
                    </div>
                  </div>
                  <div className="flex items-center gap-2">
                    <span className={`text-sm ${!formData.es_real ? 'font-semibold text-blue-600' : 'text-gray-400'}`}>
                      Proyección
                    </span>
                    <Switch 
                      checked={formData.es_real}
                      onCheckedChange={(checked) => setFormData({...formData, es_real: checked})}
                    />
                    <span className={`text-sm ${formData.es_real ? 'font-semibold text-green-600' : 'text-gray-400'}`}>
                      Real
                    </span>
                  </div>
                </div>
              </div>

              {/* Tipo y Método */}
              <div className="grid grid-cols-2 gap-4">
                <div className="space-y-2">
                  <Label>Tipo</Label>
                  <Select value={formData.tipo} onValueChange={handleTipoChange}>
                    <SelectTrigger>
                      <SelectValue />
                    </SelectTrigger>
                    <SelectContent>
                      <SelectItem value="pago">
                        <div className="flex items-center gap-2">
                          <TrendingDown className="text-red-500" size={16} />
                          Pago (Egreso)
                        </div>
                      </SelectItem>
                      <SelectItem value="cobro">
                        <div className="flex items-center gap-2">
                          <TrendingUp className="text-green-500" size={16} />
                          Cobro (Ingreso)
                        </div>
                      </SelectItem>
                    </SelectContent>
                  </Select>
                </div>
                <div className="space-y-2">
                  <Label>Método de Pago</Label>
                  <Select value={formData.metodo_pago} onValueChange={(v) => setFormData({...formData, metodo_pago: v})}>
                    <SelectTrigger>
                      <SelectValue />
                    </SelectTrigger>
                    <SelectContent>
                      {PAYMENT_METHODS.map(m => (
                        <SelectItem key={m.value} value={m.value}>{m.label}</SelectItem>
                      ))}
                    </SelectContent>
                  </Select>
                </div>
              </div>

              {/* Cliente/Proveedor Selector */}
              <div className="space-y-2">
                <Label className="flex items-center gap-2">
                  {formData.tipo === 'cobro' ? (
                    <><User size={16} className="text-blue-500" /> Seleccionar Cliente</>
                  ) : (
                    <><Building2 size={16} className="text-orange-500" /> Seleccionar Proveedor</>
                  )}
                </Label>
                <Popover open={partyDropdownOpen} onOpenChange={setPartyDropdownOpen}>
                  <PopoverTrigger asChild>
                    <Button
                      type="button"
                      variant="outline"
                      role="combobox"
                      aria-expanded={partyDropdownOpen}
                      className="w-full justify-between font-normal h-10 px-3"
                      data-testid="party-combobox-trigger"
                    >
                      <span className="truncate text-sm">
                        {selectedParty
                          ? currentParties.find(p => p.id === selectedParty)?.nombre
                          : (formData.tipo === 'cobro' ? 'Seleccionar cliente...' : 'Seleccionar proveedor...')}
                      </span>
                      <ChevronDown size={16} className="ml-2 shrink-0 opacity-50" />
                    </Button>
                  </PopoverTrigger>
                  <PopoverContent className="p-0 w-[var(--radix-popover-trigger-width)]" align="start">
                    <Command shouldFilter={false}>
                      <CommandInput
                        placeholder={`Buscar ${formData.tipo === 'cobro' ? 'cliente' : 'proveedor'}...`}
                        value={partySearch}
                        onValueChange={setPartySearch}
                        data-testid="party-search-input"
                      />
                      <CommandList>
                        <CommandEmpty>No se encontraron resultados.</CommandEmpty>
                        <CommandGroup>
                          {currentParties
                            .filter(p => {
                              if (!partySearch) return true;
                              const q = partySearch.toLowerCase();
                              return p.nombre.toLowerCase().includes(q) || (p.rfc && p.rfc.toLowerCase().includes(q));
                            })
                            .map(party => (
                              <CommandItem
                                key={party.id}
                                value={party.id}
                                onSelect={() => {
                                  handlePartyChange(party.id);
                                  setPartyDropdownOpen(false);
                                  setPartySearch('');
                                  setShowNewPartyForm(false);
                                }}
                              >
                                <div className="flex flex-col flex-1 min-w-0">
                                  <span className="font-medium truncate">{party.nombre}</span>
                                  {party.rfc && <span className="text-xs text-gray-500">{party.rfc}</span>}
                                </div>
                                {selectedParty === party.id && <Check size={14} className="ml-2 shrink-0 text-green-600" />}
                              </CommandItem>
                            ))}
                        </CommandGroup>
                        <CommandSeparator />
                        <CommandGroup>
                          <CommandItem
                            value="__new__"
                            onSelect={() => {
                              setPartyDropdownOpen(false);
                              setPartySearch('');
                              setShowNewPartyForm(true);
                            }}
                            className="text-blue-600 font-medium"
                            data-testid="party-add-new"
                          >
                            <Plus size={15} className="mr-2 shrink-0" />
                            Agregar nuevo {formData.tipo === 'cobro' ? 'cliente' : 'proveedor'}
                          </CommandItem>
                        </CommandGroup>
                      </CommandList>
                    </Command>
                  </PopoverContent>
                </Popover>

                {/* Formulario inline para nuevo cliente/proveedor */}
                {showNewPartyForm && (
                  <div className="mt-1 p-3 border border-blue-200 rounded-lg bg-blue-50/60 space-y-2" data-testid="new-party-form">
                    <div className="flex items-center justify-between mb-1">
                      <span className="text-sm font-semibold text-blue-700">
                        Nuevo {formData.tipo === 'cobro' ? 'cliente' : 'proveedor'}
                      </span>
                      <button
                        type="button"
                        onClick={() => { setShowNewPartyForm(false); setNewPartyForm({ nombre: '', rfc: '', email: '', telefono: '' }); }}
                        className="text-gray-400 hover:text-gray-600 text-lg leading-none"
                      >✕</button>
                    </div>
                    <Input
                      placeholder="Nombre *"
                      value={newPartyForm.nombre}
                      onChange={e => setNewPartyForm(p => ({ ...p, nombre: e.target.value }))}
                      data-testid="new-party-nombre"
                    />
                    <div className="grid grid-cols-2 gap-2">
                      <Input
                        placeholder="RFC (opcional)"
                        value={newPartyForm.rfc}
                        onChange={e => setNewPartyForm(p => ({ ...p, rfc: e.target.value.toUpperCase() }))}
                        data-testid="new-party-rfc"
                      />
                      <Input
                        placeholder="Email (opcional)"
                        type="email"
                        value={newPartyForm.email}
                        onChange={e => setNewPartyForm(p => ({ ...p, email: e.target.value }))}
                        data-testid="new-party-email"
                      />
                    </div>
                    <Input
                      placeholder="Teléfono (opcional)"
                      value={newPartyForm.telefono}
                      onChange={e => setNewPartyForm(p => ({ ...p, telefono: e.target.value }))}
                      data-testid="new-party-telefono"
                    />
                    <Button
                      type="button"
                      size="sm"
                      className="w-full"
                      disabled={savingNewParty || !newPartyForm.nombre.trim()}
                      onClick={handleCreateNewParty}
                      data-testid="new-party-save"
                    >
                      {savingNewParty ? 'Guardando...' : 'Guardar y seleccionar'}
                    </Button>
                  </div>
                )}
              </div>

              {/* Facturas Pendientes - Multiple Selection */}
              {selectedParty && (
                <div className="space-y-2">
                  <div className="flex items-center justify-between">
                    <Label className="flex items-center gap-2">
                      <FileText size={16} className="text-purple-500" />
                      Facturas Pendientes ({pendingCfdis.length})
                    </Label>
                    {pendingCfdis.length > 0 && (
                      <Button type="button" variant="outline" size="sm" onClick={handleSelectAll}>
                        {selectedCfdis.length === pendingCfdis.length ? 'Deseleccionar todo' : 'Seleccionar todo'}
                      </Button>
                    )}
                  </div>
                  
                  {pendingCfdis.length === 0 ? (
                    <div className="p-4 bg-gray-50 rounded-lg text-center text-gray-500 flex items-center justify-center gap-2">
                      <AlertCircle size={16} />
                      No hay facturas pendientes para este {formData.tipo === 'cobro' ? 'cliente' : 'proveedor'}
                    </div>
                  ) : (
                    <div className="border rounded-lg max-h-60 overflow-y-auto">
                      <Table>
                        <TableHeader>
                          <TableRow className="bg-gray-50">
                            <TableHead className="w-10">
                              <Checkbox 
                                checked={selectedCfdis.length === pendingCfdis.length && pendingCfdis.length > 0}
                                onCheckedChange={handleSelectAll}
                              />
                            </TableHead>
                            <TableHead>UUID</TableHead>
                            <TableHead>Fecha</TableHead>
                            <TableHead>Emisor/Receptor</TableHead>
                            <TableHead className="text-right">Total</TableHead>
                            <TableHead className="text-right">Pagado</TableHead>
                            <TableHead className="text-right">Pendiente</TableHead>
                            <TableHead className="text-right bg-green-50">Saldo Acumulado</TableHead>
                          </TableRow>
                        </TableHeader>
                        <TableBody>
                          {(() => {
                            let runningTotal = 0;
                            return pendingCfdis.map(cfdi => {
                            const isSelected = selectedCfdis.some(c => c.id === cfdi.id);
                            const pagado = formData.tipo === 'cobro' ? (cfdi.monto_cobrado || 0) : (cfdi.monto_pagado || 0);
                            
                            // Calculate running total only for selected items up to this point
                            if (isSelected) {
                              runningTotal += cfdi.saldo_pendiente;
                            }
                            
                            return (
                              <TableRow 
                                key={cfdi.id} 
                                className={`cursor-pointer hover:bg-blue-50 ${isSelected ? 'bg-blue-100' : ''}`}
                                onClick={() => handleCfdiToggle(cfdi)}
                              >
                                <TableCell onClick={(e) => e.stopPropagation()}>
                                  <Checkbox 
                                    checked={isSelected} 
                                    onCheckedChange={() => handleCfdiToggle(cfdi)}
                                  />
                                </TableCell>
                                <TableCell className="font-mono text-xs">
                                  {cfdi.uuid?.substring(0, 8)}...
                                </TableCell>
                                <TableCell className="text-sm">
                                  {(cfdi.fecha_emision ? format(new Date(cfdi.fecha_emision), 'dd/MM/yy') : '-')}
                                </TableCell>
                                <TableCell className="text-sm max-w-[150px] truncate">
                                  {formData.tipo === 'cobro' ? cfdi.receptor_nombre : cfdi.emisor_nombre}
                                </TableCell>
                                <TableCell className="text-right font-mono">
                                  ${cfdi.total.toLocaleString('es-MX', {minimumFractionDigits: 2})}
                                </TableCell>
                                <TableCell className="text-right font-mono text-green-600">
                                  ${pagado.toLocaleString('es-MX', {minimumFractionDigits: 2})}
                                </TableCell>
                                <TableCell className="text-right font-mono font-bold text-orange-600">
                                  ${cfdi.saldo_pendiente.toLocaleString('es-MX', {minimumFractionDigits: 2})}
                                </TableCell>
                                <TableCell className="text-right font-mono font-bold bg-green-50">
                                  {isSelected ? (
                                    <span className="text-green-700">
                                      ${runningTotal.toLocaleString('es-MX', {minimumFractionDigits: 2})}
                                    </span>
                                  ) : '-'}
                                </TableCell>
                              </TableRow>
                            );
                          });
                          })()}
                        </TableBody>
                      </Table>
                    </div>
                  )}
                </div>
              )}

              {/* Selected Summary */}
              {selectedCfdis.length > 0 && (
                <div className="p-3 bg-blue-50 rounded-lg border border-blue-200">
                  <div className="flex justify-between items-center">
                    <div>
                      <div className="text-sm font-medium text-blue-800">
                        {selectedCfdis.length} factura(s) seleccionada(s)
                      </div>
                      <div className="text-xs text-blue-600">
                        {selectedCfdis.map(c => c.uuid?.substring(0, 8)).join(', ')}
                      </div>
                    </div>
                    <div className="text-right">
                      <div className="text-lg font-bold text-blue-800">
                        ${totalSelectedAmount.toLocaleString('es-MX', {minimumFractionDigits: 2})} MXN
                      </div>
                      <div className="text-xs text-blue-600">Total pendiente</div>
                    </div>
                  </div>
                </div>
              )}

              {/* Monto */}
              <div className="space-y-2">
                <div className="flex items-center justify-between">
                  <Label>Monto a {formData.tipo === 'cobro' ? 'Cobrar' : 'Pagar'}</Label>
                  {selectedCfdis.length > 0 && (
                    <div className="flex items-center gap-2">
                      <Checkbox 
                        id="customAmount"
                        checked={useCustomAmount}
                        onCheckedChange={(checked) => {
                          setUseCustomAmount(checked);
                          if (!checked) {
                            setFormData(prev => ({ ...prev, monto: totalSelectedAmount.toFixed(2) }));
                          }
                        }}
                      />
                      <Label htmlFor="customAmount" className="text-sm text-gray-600 cursor-pointer">
                        Usar monto diferente (pago parcial)
                      </Label>
                    </div>
                  )}
                </div>
                <div className="flex gap-2">
                  <Input
                    type="number"
                    step="0.01"
                    value={formData.monto}
                    onChange={(e) => setFormData({...formData, monto: e.target.value})}
                    required
                    disabled={selectedCfdis.length > 0 && !useCustomAmount}
                    className={`flex-1 text-lg font-bold ${selectedCfdis.length > 0 && !useCustomAmount ? 'bg-gray-100' : ''}`}
                    placeholder="0.00"
                  />
                  <Select value={formData.moneda} onValueChange={(v) => setFormData({...formData, moneda: v})}>
                    <SelectTrigger className="w-24">
                      <SelectValue />
                    </SelectTrigger>
                    <SelectContent>
                      <SelectItem value="MXN">MXN</SelectItem>
                      <SelectItem value="USD">USD</SelectItem>
                      <SelectItem value="EUR">EUR</SelectItem>
                    </SelectContent>
                  </Select>
                </div>
                {selectedCfdis.length > 0 && useCustomAmount && parseFloat(formData.monto) > totalSelectedAmount && (
                  <p className="text-xs text-red-500 flex items-center gap-1">
                    <AlertCircle size={12} />
                    El monto excede el total pendiente (${totalSelectedAmount.toFixed(2)})
                  </p>
                )}
                
                {/* Panel de conversión TC para monedas extranjeras */}
                {formData.moneda !== 'MXN' && formData.monto && parseFloat(formData.monto) > 0 && (
                  <div className="p-3 bg-blue-50 border border-blue-200 rounded-lg mt-2">
                    <div className="flex justify-between items-center mb-2">
                      <span className="text-sm text-blue-700">Equivalente en MXN:</span>
                      <span className="font-mono font-bold text-blue-800">
                        ${((parseFloat(formData.monto) || 0) * (useCustomTc && customTc ? parseFloat(customTc) : (fxRates[formData.moneda] || 1))).toLocaleString('es-MX', {minimumFractionDigits: 2})}
                      </span>
                    </div>
                    <div className="flex items-center gap-2 flex-wrap">
                      <label className="flex items-center gap-1 text-xs text-blue-600 cursor-pointer">
                        <input 
                          type="checkbox" 
                          checked={useCustomTc}
                          onChange={(e) => {
                            setUseCustomTc(e.target.checked);
                            if (!e.target.checked) setCustomTc('');
                          }}
                          className="w-3 h-3"
                        />
                        TC Personalizado
                      </label>
                      {useCustomTc ? (
                        <div className="flex items-center gap-1">
                          <span className="text-xs text-blue-600">1 {formData.moneda} =</span>
                          <input
                            type="number"
                            step="0.0001"
                            value={customTc}
                            onChange={(e) => setCustomTc(e.target.value)}
                            placeholder={fxRates[formData.moneda]?.toString() || '17.5'}
                            className="w-20 px-1 py-0.5 text-xs border rounded text-right"
                          />
                          <span className="text-xs text-blue-600">MXN</span>
                        </div>
                      ) : (
                        <span className="text-xs text-blue-600">
                          TC Actual: 1 {formData.moneda} = {fxRates[formData.moneda] || 1} MXN
                        </span>
                      )}
                    </div>
                  </div>
                )}
              </div>

              {/* Concepto */}
              <div className="space-y-2">
                <Label>Concepto</Label>
                <Input
                  value={formData.concepto}
                  onChange={(e) => setFormData({...formData, concepto: e.target.value})}
                  placeholder="Descripción del pago"
                  required
                />
              </div>

              {/* Fecha y Referencia */}
              <div className="grid grid-cols-2 gap-4">
                <div className="space-y-2">
                  <Label>Fecha de Vencimiento</Label>
                  <Input
                    type="datetime-local"
                    value={formData.fecha_vencimiento}
                    onChange={(e) => setFormData({...formData, fecha_vencimiento: e.target.value})}
                    required
                  />
                </div>
                <div className="space-y-2">
                  <Label>Referencia / UUID</Label>
                  <Input
                    value={formData.referencia}
                    onChange={(e) => setFormData({...formData, referencia: e.target.value})}
                    placeholder="Número de referencia"
                  />
                </div>
              </div>

              {/* Domiciliación */}
              <div className="flex items-center gap-2">
                <Checkbox
                  id="domiciliacion"
                  checked={formData.domiciliacion_activa}
                  onCheckedChange={(checked) => setFormData({...formData, domiciliacion_activa: checked})}
                />
                <Label htmlFor="domiciliacion" className="cursor-pointer">Domiciliación activa</Label>
              </div>

              <DialogFooter>
                <Button type="button" variant="outline" onClick={() => setDialogOpen(false)}>Cancelar</Button>
                <Button type="submit" className="bg-[#0F172A]">
                  Registrar {formData.tipo === 'cobro' ? 'Cobro' : 'Pago'}
                </Button>
              </DialogFooter>
            </form>
          </DialogContent>
        </Dialog>
        </div>
      </div>

      {/* Summary Cards - 6 tarjetas */}
      <div className="grid grid-cols-1 md:grid-cols-3 lg:grid-cols-6 gap-4">
        {/* Por Pagar */}
        <Card className="border-[#EF4444] bg-red-50">
          <CardHeader className="pb-2">
            <CardTitle className="text-sm font-medium text-[#DC2626] flex items-center gap-2">
              <TrendingDown size={16} />
              Por Pagar
              {agingSummary?.cxp && (
                <span className="ml-auto flex items-center gap-1 text-[10px] font-normal bg-red-100 text-red-600 border border-red-300 rounded-full px-2 py-0.5">
                  <span className="w-1.5 h-1.5 rounded-full bg-red-500 animate-pulse inline-block"></span>
                  Live {erpLabel}
                </span>
              )}
            </CardTitle>
            <CardDescription className="text-xs">
              {agingSummary?.cxp ? `${erpLabel} · Aging CxP` : 'Facturas CFDI pendientes'}
            </CardDescription>
          </CardHeader>
          <CardContent>
            <div className="text-xl font-bold mono text-[#DC2626]">
              ${(agingSummary?.cxp ? agingSummary.cxp.total : (breakdown?.cfdi_por_pagar?.total_equiv_mxn || 0)).toLocaleString('es-MX', {minimumFractionDigits: 2})}
            </div>
            <div className="text-xs text-[#64748B] mt-1">
              {agingSummary?.cxp
                ? `${agingSummary.cxp.count} proveedores · vencido $${agingSummary.cxp.vencido.toLocaleString('es-MX', {minimumFractionDigits: 0})}`
                : `${breakdown?.cfdi_por_pagar?.total_count || 0} facturas`}
            </div>
          </CardContent>
        </Card>

        {/* Por Cobrar */}
        <Card className="border-[#10B981] bg-green-50">
          <CardHeader className="pb-2">
            <CardTitle className="text-sm font-medium text-[#059669] flex items-center gap-2">
              <TrendingUp size={16} />
              Por Cobrar
              {agingSummary?.cxc && (
                <span className="ml-auto flex items-center gap-1 text-[10px] font-normal bg-green-100 text-green-700 border border-green-300 rounded-full px-2 py-0.5">
                  <span className="w-1.5 h-1.5 rounded-full bg-green-500 animate-pulse inline-block"></span>
                  Live {erpLabel}
                </span>
              )}
            </CardTitle>
            <CardDescription className="text-xs">
              {agingSummary?.cxc ? `${erpLabel} · Aging CxC` : 'Facturas CFDI pendientes'}
            </CardDescription>
          </CardHeader>
          <CardContent>
            <div className="text-xl font-bold mono text-[#059669]">
              ${(agingSummary?.cxc ? agingSummary.cxc.total : (breakdown?.cfdi_por_cobrar?.total_equiv_mxn || 0)).toLocaleString('es-MX', {minimumFractionDigits: 2})}
            </div>
            <div className="text-xs text-[#64748B] mt-1">
              {agingSummary?.cxc
                ? `${agingSummary.cxc.count} clientes · vencido $${agingSummary.cxc.vencido.toLocaleString('es-MX', {minimumFractionDigits: 0})}`
                : `${breakdown?.cfdi_por_cobrar?.total_count || 0} facturas`}
            </div>
          </CardContent>
        </Card>

        {/* Pagado (Conciliado) */}
        <Card className="border-[#B91C1C] bg-red-100/70">
          <CardHeader className="pb-2">
            <CardTitle className="text-sm font-medium text-[#991B1B] flex items-center gap-2">
              <CheckCircle2 size={16} />
              Pagado
            </CardTitle>
            <CardDescription className="text-xs">
              Conciliado en banco
            </CardDescription>
          </CardHeader>
          <CardContent>
            <div className="text-xl font-bold mono text-[#991B1B]">
              ${(breakdown?.pagado?.total_equiv_mxn || 0).toLocaleString('es-MX', {minimumFractionDigits: 2})}
            </div>
            <div className="text-xs text-[#64748B] mt-1">
              {breakdown?.pagado?.total_count || 0} movimientos
              {breakdown?.pagado?.con_cfdi > 0 && <span className="ml-1">({breakdown.pagado.con_cfdi} con CFDI)</span>}
            </div>
          </CardContent>
        </Card>

        {/* Cobrado (Conciliado) */}
        <Card className="border-[#047857] bg-green-100/70">
          <CardHeader className="pb-2">
            <CardTitle className="text-sm font-medium text-[#065F46] flex items-center gap-2">
              <CheckCircle2 size={16} />
              Cobrado
            </CardTitle>
            <CardDescription className="text-xs">
              Conciliado en banco
            </CardDescription>
          </CardHeader>
          <CardContent>
            <div className="text-xl font-bold mono text-[#065F46]">
              ${(breakdown?.cobrado?.total_equiv_mxn || 0).toLocaleString('es-MX', {minimumFractionDigits: 2})}
            </div>
            <div className="text-xs text-[#64748B] mt-1">
              {breakdown?.cobrado?.total_count || 0} movimientos
              {breakdown?.cobrado?.con_cfdi > 0 && <span className="ml-1">({breakdown.cobrado.con_cfdi} con CFDI)</span>}
            </div>
          </CardContent>
        </Card>

        {/* Proyecciones Pagos */}
        <Card className="border-[#6366F1] bg-indigo-50">
          <CardHeader className="pb-2">
            <CardTitle className="text-sm font-medium text-[#4F46E5] flex items-center gap-2">
              <EyeOff size={16} />
              Proy. Pagos
            </CardTitle>
            <CardDescription className="text-xs">
              Estimado
            </CardDescription>
          </CardHeader>
          <CardContent>
            <div className="text-xl font-bold mono text-[#4F46E5]">
              ${(breakdown?.proyeccion_pagos?.total_equiv_mxn || 0).toLocaleString('es-MX', {minimumFractionDigits: 2})}
            </div>
            <div className="text-xs text-[#64748B] mt-1">{breakdown?.proyeccion_pagos?.total_count || 0} proyecciones</div>
          </CardContent>
        </Card>

        {/* Proyecciones Cobros */}
        <Card className="border-[#8B5CF6] bg-purple-50">
          <CardHeader className="pb-2">
            <CardTitle className="text-sm font-medium text-[#7C3AED] flex items-center gap-2">
              <EyeOff size={16} />
              Proy. Cobros
            </CardTitle>
            <CardDescription className="text-xs">
              Estimado
            </CardDescription>
          </CardHeader>
          <CardContent>
            <div className="text-xl font-bold mono text-[#7C3AED]">
              ${(breakdown?.proyeccion_cobros?.total_equiv_mxn || 0).toLocaleString('es-MX', {minimumFractionDigits: 2})}
            </div>
            <div className="text-xs text-[#64748B] mt-1">{breakdown?.proyeccion_cobros?.total_count || 0} proyecciones</div>
          </CardContent>
        </Card>
      </div>

      {/* Varianza Summary Banner */}
      {breakdown?.varianza && (
        <Card className="border-[#1E293B] bg-slate-900 text-white">
          <CardContent className="py-3">
            <div className="flex items-center justify-between">
              <div className="flex items-center gap-6">
                <div className="text-sm">
                  <span className="text-slate-400">Flujo Neto Real:</span>
                  <span className={`ml-2 font-bold mono ${(breakdown?.varianza?.flujo_neto_real ?? 0) >= 0 ? 'text-green-400' : 'text-red-400'}`}>
                    ${breakdown?.varianza?.flujo_neto_real?.toLocaleString('es-MX', {minimumFractionDigits: 2}) ?? '0.00'}
                  </span>
                </div>
                <div className="text-sm">
                  <span className="text-slate-400">Flujo Neto Proyectado:</span>
                  <span className={`ml-2 font-bold mono ${(breakdown?.varianza?.flujo_neto_proyectado ?? 0) >= 0 ? 'text-green-400' : 'text-red-400'}`}>
                    ${breakdown?.varianza?.flujo_neto_proyectado?.toLocaleString('es-MX', {minimumFractionDigits: 2}) ?? '0.00'}
                  </span>
                </div>
              </div>
              <div className="text-xs text-slate-400">
                💡 La varianza se usa para el análisis de 13 semanas en Reportes
              </div>
            </div>
          </CardContent>
        </Card>
      )}

      {/* Filters */}
      <Card className="border-[#E2E8F0]">
        <CardContent className="py-4">
          <div className="flex flex-wrap gap-4 items-end">
            <div className="space-y-1">
              <Label className="text-xs">Tipo</Label>
              <Select value={filterTipo} onValueChange={setFilterTipo}>
                <SelectTrigger className="w-32">
                  <SelectValue />
                </SelectTrigger>
                <SelectContent>
                  <SelectItem value="all">Todos</SelectItem>
                  <SelectItem value="pago">Pagos</SelectItem>
                  <SelectItem value="cobro">Cobros</SelectItem>
                </SelectContent>
              </Select>
            </div>
            <div className="space-y-1">
              <Label className="text-xs">Real/Proyección</Label>
              <Select value={filterEsReal} onValueChange={setFilterEsReal}>
                <SelectTrigger className="w-36">
                  <SelectValue />
                </SelectTrigger>
                <SelectContent>
                  <SelectItem value="all">Todos</SelectItem>
                  <SelectItem value="real">Solo Reales</SelectItem>
                  <SelectItem value="proyeccion">Solo Proyecciones</SelectItem>
                </SelectContent>
              </Select>
            </div>
            <div className="space-y-1">
              <Label className="text-xs">Estatus</Label>
              <Select value={filterEstatus} onValueChange={setFilterEstatus}>
                <SelectTrigger className="w-32">
                  <SelectValue />
                </SelectTrigger>
                <SelectContent>
                  <SelectItem value="all">Todos</SelectItem>
                  <SelectItem value="pendiente">Pendiente</SelectItem>
                  <SelectItem value="completado">Completado</SelectItem>
                  <SelectItem value="vencido">Vencido</SelectItem>
                </SelectContent>
              </Select>
            </div>
            <div className="space-y-1">
              <Label className="text-xs">Categoría</Label>
              <Select value={filterCategoria} onValueChange={setFilterCategoria}>
                <SelectTrigger className="w-48">
                  <SelectValue />
                </SelectTrigger>
                <SelectContent>
                  <SelectItem value="all">Todas</SelectItem>
                  <SelectItem value="sin_categoria">Sin categoría</SelectItem>
                  {categories.filter(c => c.tipo === 'ingreso').length > 0 && (
                    <>
                      <SelectItem value="__header_ing__" disabled className="text-xs text-gray-400 font-semibold">── Ingresos ──</SelectItem>
                      {categories.filter(c => c.tipo === 'ingreso').map(c => (
                        <SelectItem key={c.code || c.id} value={c.code || c.id}>{c.nombre}</SelectItem>
                      ))}
                    </>
                  )}
                  {categories.filter(c => c.tipo === 'egreso').length > 0 && (
                    <>
                      <SelectItem value="__header_egr__" disabled className="text-xs text-gray-400 font-semibold">── Egresos ──</SelectItem>
                      {categories.filter(c => c.tipo === 'egreso').map(c => (
                        <SelectItem key={c.code || c.id} value={c.code || c.id}>{c.nombre}</SelectItem>
                      ))}
                    </>
                  )}
                </SelectContent>
              </Select>
            </div>
            <div className="space-y-1">
              <Label className="text-xs">Desde</Label>
              <Input
                type="date"
                value={filterFechaDesde}
                onChange={(e) => setFilterFechaDesde(e.target.value)}
                className="w-40"
              />
            </div>
            <div className="space-y-1">
              <Label className="text-xs">Hasta</Label>
              <Input
                type="date"
                value={filterFechaHasta}
                onChange={(e) => setFilterFechaHasta(e.target.value)}
                className="w-40"
              />
            </div>
            <Button variant="outline" onClick={() => {
              setFilterTipo('all');
              setFilterEstatus('all');
              setFilterCategoria('all');
              setFilterFechaDesde('');
              setFilterFechaHasta('');
            }}>
              Limpiar Filtros
            </Button>
          </div>
        </CardContent>
      </Card>

      {/* Payments Table */}
      <Card className="border-[#E2E8F0]">
        <CardHeader className="flex flex-row items-center justify-between">
          <div className="flex items-center gap-4">
            <div>
              <CardTitle>Cobranza y Pagos</CardTitle>
              <CardDescription>
                {payments.filter(p => {
                  if (activeTab === 'cobrar') return p.tipo === 'cobro';
                  if (activeTab === 'pagar') return p.tipo === 'pago';
                  return true;
                }).length} registros
              </CardDescription>
            </div>
            {/* Tabs */}
            <div className="flex gap-1 bg-[#F1F5F9] rounded-lg p-1">
              {[
                { key: 'todos',   label: 'Todos' },
                { key: 'cobrar',  label: '↑ Por Cobrar' },
                { key: 'pagar',   label: '↓ Por Pagar' },
              ].map(tab => (
                <button
                  key={tab.key}
                  onClick={() => setActiveTab(tab.key)}
                  className={`px-3 py-1.5 text-xs font-medium rounded-md transition-colors ${
                    activeTab === tab.key
                      ? 'bg-white text-[#0F172A] shadow-sm'
                      : 'text-[#64748B] hover:text-[#0F172A]'
                  }`}
                >
                  {tab.label}
                </button>
              ))}
            </div>
          </div>
          <Button
            variant="outline"
            size="sm"
            disabled={syncingCategories}
            onClick={async () => {
              setSyncingCategories(true);
              try {
                const res = await api.post('/cashflow-sync/auto-categorize?limit=50');
                const { updated, processed } = res.data;
                if (updated > 0) {
                  toast.success(`✅ ${updated} de ${processed} pagos categorizados con IA`);
                  loadData();
                } else {
                  toast.info('Todos los pagos ya tienen categoría asignada');
                }
              } catch (error) {
                console.error('Error sincronizando categorías:', error);
                toast.error(error.response?.data?.detail || 'Error categorizando pagos');
              } finally {
                setSyncingCategories(false);
              }
            }}
            title="Categoriza con IA los pagos sin categoría (Alegra, Contalink y todos los orígenes)"
          >
            <RefreshCw size={14} className={`mr-2 ${syncingCategories ? 'animate-spin' : ''}`} />
            {syncingCategories ? 'Categorizando...' : 'Sincronizar Categorías'}
          </Button>
        </CardHeader>
        <CardContent>
          <Table className="data-table">
            <TableHeader>
              <TableRow>
                <TableHead>Fecha Venc.</TableHead>
                <TableHead>Tipo</TableHead>
                <TableHead>Real/Proy.</TableHead>
                <TableHead>UUID CFDI</TableHead>
                <TableHead>Categoría</TableHead>
                <TableHead>Concepto</TableHead>
                <TableHead>Beneficiario</TableHead>
                <TableHead>Monto</TableHead>
                <TableHead>Estatus</TableHead>
                <TableHead className="text-center">Acciones</TableHead>
              </TableRow>
            </TableHeader>
            <TableBody>
              {payments.length === 0 ? (
                <TableRow>
                  <TableCell colSpan={10} className="text-center text-[#94A3B8] py-8">
                    No hay pagos registrados. Crea el primero.
                  </TableCell>
                </TableRow>
              ) : (
                payments.filter(p => {
                  // Tab filter
                  if (activeTab === 'cobrar' && p.tipo !== 'cobro') return false;
                  if (activeTab === 'pagar'  && p.tipo !== 'pago')  return false;
                  // Existing filters
                  if (filterTipo !== 'all' && p.tipo !== filterTipo) return false;
                  if (filterEsReal === 'real') return p.es_real === true;
                  if (filterEsReal === 'proyeccion') return p.es_real === false;
                  // Category filter
                  if (filterCategoria === 'sin_categoria') return !p.category_id;
                  if (filterCategoria !== 'all') return p.category_id === filterCategoria;
                  return true;
                }).map((payment) => {
                  // Find category and subcategory names
                  const category = categories.find(c => (c.code || c.id) === payment.category_id);
                  const categoryName = category?.nombre || payment.category_name || '';
                  const subcategory = category?.subcategorias?.find(s => s.id === payment.subcategory_id);
                  const subcategoryName = subcategory?.nombre || '';
                  
                  return (
                  <TableRow key={payment.id} className={payment.es_real === false ? 'bg-blue-50/30' : ''}>
                    <TableCell className="mono text-sm">
                      {(payment.fecha_vencimiento ? format(new Date(payment.fecha_vencimiento), 'dd/MM/yyyy') : payment.fecha ? format(new Date(payment.fecha), 'dd/MM/yyyy') : 'Sin fecha')}
                      {payment.domiciliacion_activa && (
                        <span className="ml-2 text-xs px-1 py-0.5 bg-blue-100 text-blue-800 rounded">DOM</span>
                      )}
                    </TableCell>
                    <TableCell>
                      <span className={`text-xs px-2 py-1 rounded ${
                        payment.tipo === 'cobro' ? 'bg-green-100 text-green-800' : 'bg-red-100 text-red-800'
                      }`}>
                        {payment.tipo === 'cobro' ? '↑ Cobro' : '↓ Pago'}
                      </span>
                    </TableCell>
                    <TableCell>
                      <span className={`text-xs px-2 py-1 rounded flex items-center gap-1 w-fit ${
                        payment.es_real === false ? 'bg-blue-100 text-blue-800' : 'bg-green-100 text-green-800'
                      }`}>
                        {payment.es_real === false ? (
                          <><EyeOff size={12} /> Proyección</>
                        ) : (
                          <><Eye size={12} /> Real</>
                        )}
                      </span>
                    </TableCell>
                    <TableCell className="font-mono text-xs">
                      {payment.cfdi_uuid ? (
                        <span className="text-purple-600" title={payment.cfdi_uuid}>
                          {payment.cfdi_uuid.substring(0, 8)}...
                        </span>
                      ) : (
                        <span className="text-gray-400">-</span>
                      )}
                    </TableCell>
                    <TableCell>
                      <select
                          className={`text-xs border rounded px-1 py-0.5 cursor-pointer ${categoryName ? 'bg-white text-gray-700 border-gray-200' : 'bg-amber-50 text-amber-700'}`}
                          value={payment.category_id ? `${payment.category_id}|` : ''}
                          onChange={async (e) => {
                            const [catId, subcatId] = e.target.value.split('|');
                            try {
                              // Usar _id de MongoDB como identificador universal (funciona para Contalink, Alegra y manuales)
                              const paymentId = payment._id || payment.id || payment.contalink_id;
                              await api.post(`/cashflow-sync/recategorize`, {
                                payment_id: paymentId,
                                category_id: catId,
                              });
                              toast.success('Categoría actualizada');
                              loadData();
                            } catch (error) {
                              toast.error('Error categorizando');
                            }
                          }}
                        >
                          <option value="">Sin categoría</option>
                          {/* Ingresos */}
                          {categories.filter(c => c.tipo === 'ingreso').length > 0 && (
                            <optgroup label="── Ingresos ──">
                              {categories.filter(c => c.tipo === 'ingreso').map(cat => (
                                cat.subcategorias && cat.subcategorias.length > 0 ? [
                                  <option key={`${cat.code || cat.id}|`} value={`${cat.code || cat.id}|`}>{cat.nombre} (General)</option>,
                                  ...cat.subcategorias.map(sub => (
                                    <option key={`${cat.code || cat.id}|${sub.id}`} value={`${cat.code || cat.id}|${sub.id}`}>— {sub.nombre}</option>
                                  ))
                                ] : (
                                  <option key={`${cat.code || cat.id}|`} value={`${cat.code || cat.id}|`}>{cat.nombre}</option>
                                )
                              ))}
                            </optgroup>
                          )}
                          {/* Egresos */}
                          {categories.filter(c => c.tipo === 'egreso').length > 0 && (
                            <optgroup label="── Egresos ──">
                              {categories.filter(c => c.tipo === 'egreso').map(cat => (
                                cat.subcategorias && cat.subcategorias.length > 0 ? [
                                  <option key={`${cat.code || cat.id}|`} value={`${cat.code || cat.id}|`}>{cat.nombre} (General)</option>,
                                  ...cat.subcategorias.map(sub => (
                                    <option key={`${cat.code || cat.id}|${sub.id}`} value={`${cat.code || cat.id}|${sub.id}`}>— {sub.nombre}</option>
                                  ))
                                ] : (
                                  <option key={`${cat.code || cat.id}|`} value={`${cat.code || cat.id}|`}>{cat.nombre}</option>
                                )
                              ))}
                            </optgroup>
                          )}
                        </select>
                    </TableCell>
                    <TableCell className="max-w-[150px] truncate text-sm">{payment.concepto}</TableCell>
                    <TableCell className="text-sm">{payment.beneficiario || '-'}</TableCell>
                    <TableCell className={`mono font-semibold ${
                      payment.tipo === 'cobro' ? 'text-green-600' : 'text-red-600'
                    }`}>
                      {payment.tipo === 'cobro' ? '+' : '-'}${payment.monto.toLocaleString('es-MX', {minimumFractionDigits: 2})} {payment.moneda}
                    </TableCell>
                    <TableCell>
                      {/* Use estado_real (computed from bank transaction) if available */}
                      {(() => {
                        const realStatus = payment.estado_real || payment.estatus;
                        const statusConfig = PAYMENT_STATUS[realStatus] || PAYMENT_STATUS.pendiente;
                        return (
                          <span className={`text-xs px-2 py-1 rounded ${statusConfig.color}`}>
                            {statusConfig.label}
                            {payment.conciliacion_real === false && payment.bank_transaction_id && (
                              <span className="ml-1 text-orange-600" title="Transacción bancaria pendiente de conciliar">⚠</span>
                            )}
                          </span>
                        );
                      })()}
                    </TableCell>
                    <TableCell className="text-center">
                      <div className="flex items-center justify-center gap-1">
                        <Button
                          variant="ghost"
                          size="sm"
                          className="text-blue-600 hover:text-blue-800 hover:bg-blue-50"
                          onClick={() => handleView(payment)}
                          title="Ver detalles"
                        >
                          <Eye size={16} />
                        </Button>
                        <Button
                          variant="ghost"
                          size="sm"
                          className="text-gray-600 hover:text-gray-800 hover:bg-gray-50"
                          onClick={() => handleEdit(payment)}
                          title="Editar pago"
                        >
                          <Edit size={16} />
                        </Button>
                        {(payment.estado_real || payment.estatus) === 'pendiente' && (
                          <Button
                            variant="ghost"
                            size="sm"
                            className="text-green-600 hover:text-green-800 hover:bg-green-50"
                            onClick={() => handleComplete(payment.id)}
                            title="Marcar como completado"
                          >
                            <Check size={16} />
                          </Button>
                        )}
                        <Button
                          variant="ghost"
                          size="sm"
                          className="text-red-600 hover:text-red-800 hover:bg-red-50"
                          onClick={() => setDeleteConfirm({ open: true, payment })}
                          title="Eliminar pago"
                        >
                          <Trash2 size={16} />
                        </Button>
                      </div>
                      {payment.fecha_pago && (
                        <div className="text-xs text-[#64748B] mt-1">
                          Pagado: {(payment.fecha_pago ? format(new Date(payment.fecha_pago), 'dd/MM/yy') : '')}
                        </div>
                      )}
                    </TableCell>
                  </TableRow>
                )})
              )}
            </TableBody>
          </Table>
        </CardContent>
      </Card>

      {/* Delete Confirmation Dialog */}
      <AlertDialog open={deleteConfirm.open} onOpenChange={(open) => !open && setDeleteConfirm({ open: false, payment: null })}>
        <AlertDialogContent>
          <AlertDialogHeader>
            <AlertDialogTitle className="flex items-center gap-2">
              <AlertTriangle className="h-5 w-5 text-red-500" />
              ¿Eliminar este pago?
            </AlertDialogTitle>
            <AlertDialogDescription>
              Esta acción no se puede deshacer. Se eliminará permanentemente el pago de 
              <strong> ${deleteConfirm.payment?.monto?.toLocaleString('es-MX', {minimumFractionDigits: 2})} {deleteConfirm.payment?.moneda}</strong>
              {deleteConfirm.payment?.concepto && ` - "${deleteConfirm.payment.concepto}"`}.
            </AlertDialogDescription>
          </AlertDialogHeader>
          <AlertDialogFooter>
            <AlertDialogCancel>Cancelar</AlertDialogCancel>
            <AlertDialogAction 
              onClick={handleDelete}
              className="bg-red-600 hover:bg-red-700"
            >
              Eliminar
            </AlertDialogAction>
          </AlertDialogFooter>
        </AlertDialogContent>
      </AlertDialog>

      {/* Delete by Date Range Dialog */}
      <Dialog open={deleteRangeOpen} onOpenChange={(open) => {
        if (!open) { setDeleteRangePreview(null); }
        setDeleteRangeOpen(open);
      }}>
        <DialogContent className="max-w-md">
          <DialogHeader>
            <DialogTitle className="flex items-center gap-2">
              <AlertTriangle className="h-5 w-5 text-red-500" />
              Eliminar movimientos por fecha
            </DialogTitle>
            <DialogDescription>
              Selecciona el rango de fechas. Se filtran por <strong>fecha de vencimiento</strong>.
            </DialogDescription>
          </DialogHeader>

          <div className="space-y-4 py-2">
            <div className="grid grid-cols-2 gap-3">
              <div className="space-y-1">
                <Label className="text-xs">Fecha inicio</Label>
                <Input
                  type="date"
                  value={deleteRangeFrom}
                  onChange={(e) => { setDeleteRangeFrom(e.target.value); setDeleteRangePreview(null); }}
                  data-testid="delete-range-from"
                />
              </div>
              <div className="space-y-1">
                <Label className="text-xs">Fecha fin</Label>
                <Input
                  type="date"
                  value={deleteRangeTo}
                  onChange={(e) => { setDeleteRangeTo(e.target.value); setDeleteRangePreview(null); }}
                  data-testid="delete-range-to"
                />
              </div>
            </div>

            <Button
              variant="outline"
              className="w-full"
              onClick={handlePreviewDeleteByRange}
              disabled={!deleteRangeFrom || !deleteRangeTo || deleteRangePreviewing}
              data-testid="delete-range-preview-btn"
            >
              {deleteRangePreviewing ? '⟳ Consultando...' : 'Ver movimientos afectados'}
            </Button>

            {deleteRangePreview && (
              <div className={`rounded-lg border p-4 space-y-3 ${deleteRangePreview.count > 0 ? 'border-red-200 bg-red-50' : 'border-gray-200 bg-gray-50'}`}>
                {deleteRangePreview.count > 0 ? (
                  <>
                    <div className="flex items-start gap-2">
                      <AlertTriangle className="h-4 w-4 text-red-600 mt-0.5 flex-shrink-0" />
                      <p className="text-sm font-semibold text-red-700">Esta acción no se puede deshacer</p>
                    </div>
                    <div className="text-sm space-y-1 text-gray-700">
                      <div className="flex justify-between">
                        <span>Rango:</span>
                        <span className="font-mono">{deleteRangeFrom} → {deleteRangeTo}</span>
                      </div>
                      <div className="flex justify-between">
                        <span>Movimientos a eliminar:</span>
                        <span className="font-bold text-red-700">{deleteRangePreview.count.toLocaleString('es-MX')}</span>
                      </div>
                      <div className="flex justify-between">
                        <span>Monto total (MXN equiv.):</span>
                        <span className="font-bold">${deleteRangePreview.monto_total.toLocaleString('es-MX', { minimumFractionDigits: 2 })}</span>
                      </div>
                    </div>
                  </>
                ) : (
                  <p className="text-sm text-gray-500 text-center">No se encontraron movimientos en este rango.</p>
                )}
              </div>
            )}
          </div>

          <DialogFooter className="gap-2">
            <Button variant="outline" onClick={() => setDeleteRangeOpen(false)}>
              Cancelar
            </Button>
            <Button
              className="bg-red-600 hover:bg-red-700 text-white"
              onClick={handleExecuteDeleteByRange}
              disabled={!deleteRangePreview || deleteRangePreview.count === 0 || deleteRangeDeleting}
              data-testid="delete-range-confirm-btn"
            >
              {deleteRangeDeleting
                ? '⟳ Eliminando...'
                : deleteRangePreview?.count > 0
                  ? `Eliminar ${deleteRangePreview.count.toLocaleString('es-MX')} movimientos`
                  : 'Eliminar'}
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>

      {/* View Payment Dialog */}
      <Dialog open={viewDialogOpen} onOpenChange={setViewDialogOpen}>
        <DialogContent className="max-w-lg">
          <DialogHeader>
            <DialogTitle>Detalles del {selectedPayment?.tipo === 'cobro' ? 'Cobro' : 'Pago'}</DialogTitle>
          </DialogHeader>
          {selectedPayment && (
            <div className="space-y-4">
              <div className="grid grid-cols-2 gap-4">
                <div>
                  <p className="text-sm text-gray-500">Tipo</p>
                  <p className={`font-medium ${selectedPayment.tipo === 'cobro' ? 'text-green-600' : 'text-red-600'}`}>
                    {selectedPayment.tipo === 'cobro' ? 'Cobro (Ingreso)' : 'Pago (Egreso)'}
                  </p>
                </div>
                <div>
                  <p className="text-sm text-gray-500">Estatus</p>
                  {(() => {
                    const realStatus = selectedPayment.estado_real || selectedPayment.estatus;
                    const statusConfig = PAYMENT_STATUS[realStatus] || PAYMENT_STATUS.pendiente;
                    return (
                      <p className={`font-medium ${statusConfig.color?.includes('green') ? 'text-green-600' : ''}`}>
                        {statusConfig.label}
                        {selectedPayment.conciliacion_real === false && selectedPayment.bank_transaction_id && (
                          <span className="ml-2 text-xs text-orange-600">(Pendiente conciliar)</span>
                        )}
                      </p>
                    );
                  })()}
                </div>
              </div>
              <div>
                <p className="text-sm text-gray-500">Monto</p>
                <p className={`text-2xl font-bold font-mono ${selectedPayment.tipo === 'cobro' ? 'text-green-600' : 'text-red-600'}`}>
                  ${selectedPayment.monto?.toLocaleString('es-MX', {minimumFractionDigits: 2})} {selectedPayment.moneda}
                </p>
              </div>
              <div>
                <p className="text-sm text-gray-500">Concepto</p>
                <p className="font-medium">{selectedPayment.concepto || '-'}</p>
              </div>
              <div className="grid grid-cols-2 gap-4">
                <div>
                  <p className="text-sm text-gray-500">Beneficiario</p>
                  <p className="font-medium">{selectedPayment.beneficiario || '-'}</p>
                </div>
                <div>
                  <p className="text-sm text-gray-500">Método de Pago</p>
                  <p className="font-medium capitalize">{selectedPayment.metodo_pago}</p>
                </div>
              </div>
              <div className="grid grid-cols-2 gap-4">
                <div>
                  <p className="text-sm text-gray-500">Fecha Vencimiento</p>
                  <p className="font-medium">{(selectedPayment.fecha_vencimiento ? format(new Date(selectedPayment.fecha_vencimiento), 'dd/MM/yyyy HH:mm') : selectedPayment.fecha ? format(new Date(selectedPayment.fecha), 'dd/MM/yyyy') : 'Sin fecha')}</p>
                </div>
                <div>
                  <p className="text-sm text-gray-500">Fecha de Pago</p>
                  <p className="font-medium">{selectedPayment.fecha_pago ? format(new Date(selectedPayment.fecha_pago), 'dd/MM/yyyy') : 'Pendiente'}</p>
                </div>
              </div>
              <div>
                <p className="text-sm text-gray-500">Referencia</p>
                <p className="font-mono text-sm">{selectedPayment.referencia || '-'}</p>
              </div>
              <div className="flex gap-4">
                <div>
                  <p className="text-sm text-gray-500">Real/Proyección</p>
                  <p className={`font-medium ${selectedPayment.es_real ? 'text-green-600' : 'text-blue-600'}`}>
                    {selectedPayment.es_real ? 'Real' : 'Proyección'}
                  </p>
                </div>
                <div>
                  <p className="text-sm text-gray-500">Domiciliación</p>
                  <p className="font-medium">{selectedPayment.domiciliacion_activa ? 'Activa' : 'No'}</p>
                </div>
              </div>
            </div>
          )}
          <DialogFooter>
            <Button variant="outline" onClick={() => setViewDialogOpen(false)}>Cerrar</Button>
            <Button onClick={() => { setViewDialogOpen(false); handleEdit(selectedPayment); }}>
              <Edit size={16} className="mr-2" />
              Editar
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>

      {/* Edit Payment Dialog */}
      <Dialog open={editDialogOpen} onOpenChange={(open) => {
        setEditDialogOpen(open);
        if (!open) { setSelectedPayment(null); resetForm(); }
      }}>
        <DialogContent className="max-w-lg">
          <DialogHeader>
            <DialogTitle>Editar {selectedPayment?.tipo === 'cobro' ? 'Cobro' : 'Pago'}</DialogTitle>
          </DialogHeader>
          <form onSubmit={handleUpdatePayment} className="space-y-4">
            {/* Cuenta Bancaria */}
            <div className="space-y-2">
              <Label>Cuenta Bancaria</Label>
              <Select 
                value={formData.bank_account_id || ''} 
                onValueChange={(v) => setFormData({...formData, bank_account_id: v === 'none' ? null : v})}
              >
                <SelectTrigger>
                  <SelectValue placeholder="Seleccionar cuenta (opcional)..." />
                </SelectTrigger>
                <SelectContent>
                  <SelectItem value="none">Sin cuenta asignada</SelectItem>
                  {bankAccounts.map(acc => (
                    <SelectItem key={acc.id} value={acc.id}>
                      {acc.banco} - {acc.nombre} ({acc.moneda})
                    </SelectItem>
                  ))}
                </SelectContent>
              </Select>
            </div>

            <div className="grid grid-cols-2 gap-4">
              <div className="space-y-2">
                <Label>Monto</Label>
                <Input
                  type="number"
                  step="0.01"
                  value={formData.monto}
                  onChange={(e) => setFormData({...formData, monto: e.target.value})}
                  required
                />
              </div>
              <div className="space-y-2">
                <Label>Moneda</Label>
                <Select value={formData.moneda} onValueChange={(v) => setFormData({...formData, moneda: v})}>
                  <SelectTrigger>
                    <SelectValue />
                  </SelectTrigger>
                  <SelectContent>
                    <SelectItem value="MXN">MXN</SelectItem>
                    <SelectItem value="USD">USD</SelectItem>
                    <SelectItem value="EUR">EUR</SelectItem>
                  </SelectContent>
                </Select>
              </div>
            </div>
            
            {/* Mostrar conversión cuando la moneda no es MXN */}
            {formData.moneda !== 'MXN' && formData.monto && (
              <div className="p-3 bg-blue-50 border border-blue-200 rounded-lg">
                <div className="flex justify-between items-center mb-2">
                  <span className="text-sm text-blue-700">Equivalente en MXN:</span>
                  <span className="font-mono font-bold text-blue-800">
                    ${((parseFloat(formData.monto) || 0) * (useCustomTc && customTc ? parseFloat(customTc) : (fxRates[formData.moneda] || 1))).toLocaleString('es-MX', {minimumFractionDigits: 2})}
                  </span>
                </div>
                <div className="flex items-center gap-2">
                  <label className="flex items-center gap-1 text-xs text-blue-600 cursor-pointer">
                    <input 
                      type="checkbox" 
                      checked={useCustomTc}
                      onChange={(e) => {
                        setUseCustomTc(e.target.checked);
                        if (!e.target.checked) setCustomTc('');
                      }}
                      className="w-3 h-3"
                    />
                    TC Personalizado
                  </label>
                  {useCustomTc ? (
                    <div className="flex items-center gap-1">
                      <span className="text-xs text-blue-600">1 {formData.moneda} =</span>
                      <input
                        type="number"
                        step="0.0001"
                        value={customTc}
                        onChange={(e) => setCustomTc(e.target.value)}
                        placeholder={fxRates[formData.moneda]?.toString() || '17.5'}
                        className="w-20 px-1 py-0.5 text-xs border rounded text-right"
                      />
                      <span className="text-xs text-blue-600">MXN</span>
                    </div>
                  ) : (
                    <span className="text-xs text-blue-600">
                      TC Actual: 1 {formData.moneda} = {fxRates[formData.moneda] || 1} MXN
                    </span>
                  )}
                </div>
              </div>
            )}

            <div className="space-y-2">
              <Label>Concepto</Label>
              <Input
                value={formData.concepto}
                onChange={(e) => setFormData({...formData, concepto: e.target.value})}
                required
              />
            </div>
            <div className="space-y-2">
              <Label>Beneficiario</Label>
              <Input
                value={formData.beneficiario}
                onChange={(e) => setFormData({...formData, beneficiario: e.target.value})}
              />
            </div>
            <div className="grid grid-cols-2 gap-4">
              <div className="space-y-2">
                <Label>Fecha Vencimiento</Label>
                <Input
                  type="datetime-local"
                  value={formData.fecha_vencimiento}
                  onChange={(e) => setFormData({...formData, fecha_vencimiento: e.target.value})}
                  required
                />
              </div>
              <div className="space-y-2">
                <Label>Método de Pago</Label>
                <Select value={formData.metodo_pago || 'transferencia'} onValueChange={(v) => setFormData({...formData, metodo_pago: v})}>
                  <SelectTrigger>
                    <SelectValue placeholder="Seleccionar método..." />
                  </SelectTrigger>
                  <SelectContent>
                    <SelectItem value="transferencia">Transferencia</SelectItem>
                    <SelectItem value="spei">SPEI</SelectItem>
                    <SelectItem value="efectivo">Efectivo</SelectItem>
                    <SelectItem value="cheque">Cheque</SelectItem>
                    <SelectItem value="tarjeta">Tarjeta</SelectItem>
                    <SelectItem value="domiciliacion">Domiciliación</SelectItem>
                  </SelectContent>
                </Select>
              </div>
            </div>
            <div className="space-y-2">
              <Label>Referencia</Label>
              <Input
                value={formData.referencia}
                onChange={(e) => setFormData({...formData, referencia: e.target.value})}
              />
            </div>
            <div className="flex items-center gap-4">
              <div className="flex items-center gap-2">
                <Checkbox
                  id="editEsReal"
                  checked={formData.es_real}
                  onCheckedChange={(checked) => setFormData({...formData, es_real: checked})}
                />
                <Label htmlFor="editEsReal">Es Real (no proyección)</Label>
              </div>
            </div>
            <DialogFooter>
              <Button type="button" variant="outline" onClick={() => setEditDialogOpen(false)}>Cancelar</Button>
              <Button type="submit">Guardar Cambios</Button>
            </DialogFooter>
          </form>
        </DialogContent>
      </Dialog>

      {/* Auto-Match Dialog */}
      <Dialog open={autoMatchDialogOpen} onOpenChange={setAutoMatchDialogOpen}>
        <DialogContent className="max-w-2xl">
          <DialogHeader>
            <DialogTitle>Conciliación Automática</DialogTitle>
            <DialogDescription>
              Movimientos bancarios que coinciden con pagos/cobros por monto
            </DialogDescription>
          </DialogHeader>
          <div className="space-y-4 max-h-[400px] overflow-y-auto">
            {matchResults.length === 0 ? (
              <div className="text-center py-8 text-gray-500">
                <CheckCircle2 size={48} className="mx-auto mb-4 opacity-50" />
                <p>No se encontraron coincidencias automáticas</p>
                <p className="text-sm mt-2">Prueba conciliando manualmente en el módulo de Conciliaciones</p>
              </div>
            ) : matchCandidates.length > 0 ? (
              <div className="space-y-3">
                <p className="text-sm text-gray-600 mb-4">
                  Se encontraron {matchCandidates.length} movimiento(s) bancario(s) que podrían corresponder a este pago. 
                  Selecciona uno para conciliar:
                </p>
                {matchCandidates.map((candidate, idx) => (
                  <div 
                    key={idx} 
                    className={`p-4 border rounded-lg cursor-pointer transition-all ${
                      selectedCandidate?.transaction_id === candidate.transaction_id 
                        ? 'border-green-500 bg-green-50' 
                        : 'hover:border-gray-400'
                    }`}
                    onClick={() => setSelectedCandidate(candidate)}
                  >
                    <div className="flex justify-between items-start">
                      <div className="flex-1">
                        <div className="flex items-center gap-2">
                          <p className="font-medium text-sm">{candidate.descripcion}</p>
                          <span className={`text-xs px-2 py-0.5 rounded ${
                            candidate.score >= 80 ? 'bg-green-100 text-green-700' :
                            candidate.score >= 50 ? 'bg-yellow-100 text-yellow-700' :
                            'bg-gray-100 text-gray-700'
                          }`}>
                            {candidate.score >= 80 ? 'Alta coincidencia' : 
                             candidate.score >= 50 ? 'Media coincidencia' : 'Posible'}
                          </span>
                        </div>
                        <p className="text-xs text-gray-500 mt-1">
                          {candidate.banco} - {candidate.cuenta}
                        </p>
                        <p className="text-xs text-gray-400">
                          {candidate.fecha ? format(new Date(candidate.fecha), 'dd/MM/yyyy') : 'Sin fecha'}
                        </p>
                        <div className="mt-2 flex flex-wrap gap-1">
                          {candidate.match_reasons?.map((reason, ridx) => (
                            <span key={ridx} className="text-xs bg-blue-50 text-blue-700 px-2 py-0.5 rounded">
                              {reason}
                            </span>
                          ))}
                        </div>
                      </div>
                      <div className="text-right">
                        <p className={`font-mono font-bold ${
                          candidate.tipo === 'credito' ? 'text-green-600' : 'text-red-600'
                        }`}>
                          {candidate.tipo === 'credito' ? '+' : '-'}${candidate.monto?.toLocaleString('es-MX', {minimumFractionDigits: 2})}
                        </p>
                        <p className="text-xs text-gray-500">{candidate.moneda}</p>
                      </div>
                    </div>
                  </div>
                ))}
              </div>
            ) : (
              matchResults.map((match, idx) => (
                <div key={idx} className="p-4 border rounded-lg">
                  <div className="flex justify-between items-start">
                    <div>
                      <p className="font-medium">{match.payment.concepto}</p>
                      <p className="text-sm text-gray-500">
                        {match.payment.tipo === 'cobro' ? 'Cobro' : 'Pago'} - {match.payment.beneficiario}
                      </p>
                      <p className="text-xs text-gray-400">
                        Vencimiento: {(match.payment.fecha_vencimiento ? format(new Date(match.payment.fecha_vencimiento), 'dd/MM/yyyy') : 'Sin fecha')}
                      </p>
                    </div>
                    <div className="text-right">
                      <p className={`font-mono font-bold ${match.payment.tipo === 'cobro' ? 'text-green-600' : 'text-red-600'}`}>
                        ${match.payment.monto?.toLocaleString('es-MX', {minimumFractionDigits: 2})}
                      </p>
                    </div>
                  </div>
                  <div className="mt-2 pt-2 border-t flex items-center justify-between">
                    <div className="text-sm">
                      <span className="text-gray-500">Mov. Bancario: </span>
                      <span className="font-medium">{match.bankTxn.descripcion?.substring(0, 30)}...</span>
                      <span className="ml-2 font-mono">${match.bankTxn.monto?.toLocaleString('es-MX', {minimumFractionDigits: 2})}</span>
                    </div>
                    <Button size="sm" onClick={() => confirmAutoMatch(match)} className="bg-green-600 hover:bg-green-700">
                      <Check size={14} className="mr-1" />
                      Conciliar
                    </Button>
                  </div>
                </div>
              ))
            )}
          </div>
          <DialogFooter className="flex justify-between">
            <Button variant="outline" onClick={skipReconciliation}>
              Omitir por ahora
            </Button>
            {selectedCandidate && (
              <Button 
                onClick={handleAutoReconcile} 
                disabled={reconciling}
                className="bg-green-600 hover:bg-green-700"
              >
                {reconciling ? (
                  <>Conciliando...</>
                ) : (
                  <>
                    <Check size={16} className="mr-2" />
                    Autorizar Conciliación
                  </>
                )}
              </Button>
            )}
          </DialogFooter>
        </DialogContent>
      </Dialog>

      {/* Import from Bank Movements Dialog */}
      <Dialog open={importBankDialogOpen} onOpenChange={(open) => {
        setImportBankDialogOpen(open);
        if (!open) setSelectedBankMovements([]);
      }}>
        <DialogContent className="max-w-4xl max-h-[85vh]">
          <DialogHeader>
            <DialogTitle className="flex items-center gap-2">
              <Link2 size={20} />
              Crear Cobros/Pagos desde Movimientos Bancarios
            </DialogTitle>
            <DialogDescription>
              Selecciona movimientos del estado de cuenta para convertirlos en cobros o pagos.
              <span className="block mt-1 text-blue-600 font-medium">
                ✨ El sistema buscará automáticamente CFDIs coincidentes por monto y fecha (±60 días)
              </span>
            </DialogDescription>
          </DialogHeader>
          
          <div className="space-y-4">
            {/* Info banner about auto-matching */}
            <div className="p-3 bg-green-50 border border-green-200 rounded-lg">
              <div className="flex items-start gap-2">
                <CheckCircle2 size={18} className="text-green-600 mt-0.5" />
                <div className="text-sm text-green-800">
                  <span className="font-medium">Matching automático de CFDIs:</span>
                  <ul className="mt-1 list-disc list-inside text-green-700">
                    <li>Busca CFDIs con monto similar (±10%)</li>
                    <li>Dentro de ±60 días de la fecha del movimiento</li>
                    <li>Solo vincula si la confianza es alta (≥60%)</li>
                  </ul>
                </div>
              </div>
            </div>

            {/* Summary */}
            <div className="flex items-center justify-between p-3 bg-blue-50 border border-blue-200 rounded-lg">
              <div>
                <span className="text-blue-800 font-medium">
                  {selectedBankMovements.length} movimiento(s) seleccionado(s)
                </span>
                {selectedBankMovements.length > 0 && (
                  <span className="text-blue-600 ml-2">
                    (Depósitos = Cobros, Retiros = Pagos)
                  </span>
                )}
              </div>
              <Button 
                variant="outline" 
                size="sm"
                onClick={selectAllBankMovements}
              >
                {selectedBankMovements.length === bankTransactions.filter(t => !t.conciliado).length 
                  ? 'Deseleccionar todo' 
                  : 'Seleccionar todos pendientes'
                }
              </Button>
            </div>

            {/* Movements Table */}
            <div className="max-h-[400px] overflow-y-auto border rounded-lg">
              <Table>
                <TableHeader>
                  <TableRow>
                    <TableHead className="w-10">
                      <Checkbox
                        checked={selectedBankMovements.length === bankTransactions.filter(t => !t.conciliado).length && bankTransactions.filter(t => !t.conciliado).length > 0}
                        onCheckedChange={selectAllBankMovements}
                      />
                    </TableHead>
                    <TableHead>Fecha</TableHead>
                    <TableHead>Tipo</TableHead>
                    <TableHead>Descripción</TableHead>
                    <TableHead>Cuenta</TableHead>
                    <TableHead className="text-right">Monto</TableHead>
                    <TableHead>Estado</TableHead>
                  </TableRow>
                </TableHeader>
                <TableBody>
                  {bankTransactions.length === 0 ? (
                    <TableRow>
                      <TableCell colSpan={7} className="text-center py-8 text-gray-500">
                        <Building2 size={32} className="mx-auto mb-2 opacity-50" />
                        No hay movimientos bancarios disponibles.
                        <br />
                        <span className="text-sm">Importa un estado de cuenta en el módulo de Conciliaciones</span>
                      </TableCell>
                    </TableRow>
                  ) : (
                    bankTransactions.map(txn => {
                      const account = bankAccounts.find(a => a.id === txn.bank_account_id);
                      const isSelected = selectedBankMovements.includes(txn.id);
                      const isConciliado = txn.conciliado;
                      
                      return (
                        <TableRow 
                          key={txn.id} 
                          className={`${isSelected ? 'bg-blue-50' : ''} ${isConciliado ? 'opacity-50' : 'cursor-pointer hover:bg-gray-50'}`}
                          onClick={() => !isConciliado && toggleBankMovementSelection(txn.id)}
                        >
                          <TableCell onClick={(e) => e.stopPropagation()}>
                            <Checkbox
                              checked={isSelected}
                              disabled={isConciliado}
                              onCheckedChange={() => toggleBankMovementSelection(txn.id)}
                            />
                          </TableCell>
                          <TableCell className="text-sm">
                            {txn.fecha_movimiento ? format(new Date(txn.fecha_movimiento), 'dd/MM/yyyy') : '-'}
                          </TableCell>
                          <TableCell>
                            {txn.tipo_movimiento === 'credito' ? (
                              <span className="inline-flex items-center gap-1 text-green-600 text-xs px-2 py-1 bg-green-50 rounded">
                                <TrendingUp size={12} /> Cobro
                              </span>
                            ) : (
                              <span className="inline-flex items-center gap-1 text-red-600 text-xs px-2 py-1 bg-red-50 rounded">
                                <TrendingDown size={12} /> Pago
                              </span>
                            )}
                          </TableCell>
                          <TableCell className="max-w-[200px] truncate" title={txn.descripcion}>
                            {txn.descripcion || '-'}
                          </TableCell>
                          <TableCell className="text-xs">
                            <span className="bg-gray-100 px-2 py-1 rounded">
                              {account?.banco || 'N/A'}
                            </span>
                          </TableCell>
                          <TableCell className={`text-right font-mono font-semibold ${txn.tipo_movimiento === 'credito' ? 'text-green-600' : 'text-red-600'}`}>
                            {txn.tipo_movimiento === 'credito' ? '+' : '-'}
                            ${txn.monto?.toLocaleString('es-MX', {minimumFractionDigits: 2})}
                            {txn.moneda && txn.moneda !== 'MXN' && (
                              <span className="text-xs ml-1 text-gray-400">{txn.moneda}</span>
                            )}
                          </TableCell>
                          <TableCell>
                            {isConciliado ? (
                              <span className="text-xs px-2 py-1 bg-green-100 text-green-700 rounded">Conciliado</span>
                            ) : (
                              <span className="text-xs px-2 py-1 bg-yellow-100 text-yellow-700 rounded">Pendiente</span>
                            )}
                          </TableCell>
                        </TableRow>
                      );
                    })
                  )}
                </TableBody>
              </Table>
            </div>
          </div>

          <DialogFooter className="flex justify-between items-center">
            <div className="text-sm text-gray-500">
              {bankTransactions.filter(t => !t.conciliado).length} movimientos pendientes de {bankTransactions.length} totales
            </div>
            <div className="flex gap-2">
              <Button variant="outline" onClick={() => setImportBankDialogOpen(false)}>
                Cancelar
              </Button>
              <Button 
                onClick={handleImportBankMovements}
                disabled={selectedBankMovements.length === 0 || importingMovements}
                className="bg-[#0F172A]"
              >
                {importingMovements ? (
                  'Creando...'
                ) : (
                  <>
                    <Plus size={16} className="mr-2" />
                    Crear {selectedBankMovements.length} Pago(s)/Cobro(s)
                  </>
                )}
              </Button>
            </div>
          </DialogFooter>
        </DialogContent>
      </Dialog>

      {/* PDF Invoice Uploader Modal */}
      <PDFInvoiceUploader
        isOpen={pdfUploaderOpen}
        onClose={() => setPdfUploaderOpen(false)}
        onSuccess={() => {
          loadData();
          setPdfUploaderOpen(false);
        }}
        categories={categories}
        bankAccounts={bankAccounts}
      />

      {/* Sync ERP — date range dialog */}
      <Dialog
        open={syncDateDialogOpen}
        onOpenChange={(open) => {
          if (!open && syncingContalink) return; // block close while syncing
          if (!open) setSyncResult(null);
          setSyncDateDialogOpen(open);
        }}
      >
        <DialogContent className="max-w-sm">
          <DialogHeader>
            <DialogTitle className="flex items-center gap-2">
              <RefreshCw size={16} />
              Sincronizar Contalink / Alegra
            </DialogTitle>
            <DialogDescription>
              Solo se importarán movimientos dentro del rango seleccionado.
            </DialogDescription>
          </DialogHeader>

          {/* Phase 1 — date selection (hidden while syncing or after result) */}
          {!syncingContalink && !syncResult && (
            <div className="space-y-4 py-2">
              <div className="grid grid-cols-2 gap-3">
                <div className="space-y-1">
                  <Label className="text-xs">Fecha inicio</Label>
                  <Input
                    type="date"
                    value={syncDateFrom}
                    onChange={e => setSyncDateFrom(e.target.value)}
                    data-testid="sync-date-from"
                  />
                </div>
                <div className="space-y-1">
                  <Label className="text-xs">Fecha fin</Label>
                  <Input
                    type="date"
                    value={syncDateTo}
                    onChange={e => setSyncDateTo(e.target.value)}
                    data-testid="sync-date-to"
                  />
                </div>
              </div>
            </div>
          )}

          {/* Phase 2 — syncing in progress */}
          {syncingContalink && (
            <div className="py-6 flex flex-col items-center gap-3 text-center">
              <RefreshCw size={28} className="animate-spin text-blue-600" />
              <p className="text-sm font-medium text-gray-700">
                Sincronizando del{' '}
                <span className="font-mono">{syncDateFrom}</span> al{' '}
                <span className="font-mono">{syncDateTo}</span>…
              </p>
              <p className="text-xs text-gray-400">Esto puede tomar unos segundos</p>
            </div>
          )}

          {/* Phase 3 — result */}
          {!syncingContalink && syncResult && (
            <div className={`rounded-lg border p-4 my-2 ${syncResult.ok ? 'border-green-200 bg-green-50' : 'border-red-200 bg-red-50'}`}>
              <p className={`text-sm font-semibold ${syncResult.ok ? 'text-green-700' : 'text-red-700'}`}>
                {syncResult.ok ? '✓' : '✗'} {syncResult.message}
              </p>
            </div>
          )}

          <DialogFooter>
            {/* Cancelar — only when not syncing and no result yet */}
            {!syncingContalink && !syncResult && (
              <Button variant="outline" onClick={() => setSyncDateDialogOpen(false)}>
                Cancelar
              </Button>
            )}

            {/* Sincronizar button — shown when not syncing and no result yet */}
            {!syncingContalink && !syncResult && (
              <Button
                className="bg-[#0F172A]"
                disabled={!syncDateFrom || !syncDateTo}
                data-testid="sync-execute-btn"
                onClick={() => {
                  setSyncResult(null);
                  handleSyncContalink(syncDateFrom, syncDateTo);
                }}
              >
                Sincronizar →
              </Button>
            )}

            {/* Cerrar — shown after result */}
            {!syncingContalink && syncResult && (
              <Button
                variant={syncResult.ok ? 'default' : 'outline'}
                className={syncResult.ok ? 'bg-[#0F172A]' : ''}
                onClick={() => { setSyncResult(null); setSyncDateDialogOpen(false); }}
              >
                Cerrar
              </Button>
            )}
          </DialogFooter>
        </DialogContent>
      </Dialog>
    </div>
  );
};

export default PaymentsModule;
