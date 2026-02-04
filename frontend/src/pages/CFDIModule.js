import { useState, useEffect } from 'react';
import api from '@/api/axios';
import { Button } from '@/components/ui/button';
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card';
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from '@/components/ui/table';
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from '@/components/ui/select';
import { Dialog, DialogContent, DialogDescription, DialogFooter, DialogHeader, DialogTitle } from '@/components/ui/dialog';
import { Label } from '@/components/ui/label';
import { Textarea } from '@/components/ui/textarea';
import { toast } from 'sonner';
import { Upload, FileText, Trash2, TrendingUp, TrendingDown, RefreshCw, Tag, CheckCircle2, XCircle, Clock, Sparkles, Loader2, Eye, Download, Calendar, Filter, FilePlus } from 'lucide-react';
import { format } from 'date-fns';
import { Input } from '@/components/ui/input';
import { exportCFDIs } from '@/utils/excelExport';
import SATIntegration from '@/components/SATIntegration';
import AlegraIntegration from '@/components/AlegraIntegration';
import PDFInvoiceUploader from '@/components/PDFInvoiceUploader';
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

const CURRENCIES = ['MXN', 'USD', 'EUR', 'GBP', 'CAD'];

const RECONCILIATION_STATUS = {
  pendiente: { label: 'Pendiente', icon: Clock, color: 'bg-yellow-100 text-yellow-800' },
  conciliado: { label: 'Conciliado', icon: CheckCircle2, color: 'bg-green-100 text-green-800' },
  no_conciliable: { label: 'No Conciliable', icon: XCircle, color: 'bg-gray-100 text-gray-600' },
};

const CFDIModule = () => {
  const [cfdis, setCfdis] = useState([]);
  const [categories, setCategories] = useState([]);
  const [customers, setCustomers] = useState([]);
  const [vendors, setVendors] = useState([]);
  const [loading, setLoading] = useState(true);
  const [deleteDialogOpen, setDeleteDialogOpen] = useState(false);
  const [cfdiToDelete, setCfdiToDelete] = useState(null);
  const [viewCurrency, setViewCurrency] = useState('MXN');
  const [fxRates, setFxRates] = useState({ MXN: 1, USD: 17.50, EUR: 19.00 });
  const [summary, setSummary] = useState(null);
  const [categorizeDialogOpen, setCategorizeDialogOpen] = useState(false);
  const [cfdiToCategorize, setCfdiToCategorize] = useState(null);
  const [categorizeData, setCategorizeData] = useState({ category_id: '', subcategory_id: '', customer_id: '', vendor_id: '' });
  const [filterCategory, setFilterCategory] = useState('all');
  const [filterSubcategory, setFilterSubcategory] = useState('all');
  const [filterReconciliation, setFilterReconciliation] = useState('all');
  const [filterDateFrom, setFilterDateFrom] = useState('');
  const [filterDateTo, setFilterDateTo] = useState('');
  const [filterEmisor, setFilterEmisor] = useState('');
  const [filterReceptor, setFilterReceptor] = useState('');
  const [aiCategorizingAll, setAiCategorizingAll] = useState(false);
  const [aiCategorizingSingle, setAiCategorizingSingle] = useState(null);
  const [aiResultsDialogOpen, setAiResultsDialogOpen] = useState(false);
  const [aiResults, setAiResults] = useState([]);
  const [newRfcDialog, setNewRfcDialog] = useState({ open: false, data: null, cfdiId: null });
  const [detailDialogOpen, setDetailDialogOpen] = useState(false);
  const [cfdiDetail, setCfdiDetail] = useState(null);
  const [cfdiNotes, setCfdiNotes] = useState('');
  const [exporting, setExporting] = useState(false);

  useEffect(() => {
    loadData();
  }, []);

  useEffect(() => {
    if (cfdis.length > 0) {
      loadSummary();
    }
  }, [viewCurrency]);

  const loadData = async () => {
    try {
      const [cfdisRes, ratesRes, categoriesRes, customersRes, vendorsRes] = await Promise.all([
        api.get('/cfdi?limit=1000'),
        api.get('/fx-rates/latest'),
        api.get('/categories'),
        api.get('/customers'),
        api.get('/vendors')
      ]);
      setCfdis(cfdisRes.data);
      setCategories(categoriesRes.data);
      setCustomers(customersRes.data || []);
      setVendors(vendorsRes.data || []);
      if (ratesRes.data.rates) {
        setFxRates(ratesRes.data.rates);
      }
      // Load summary with default currency
      const summaryRes = await api.get(`/cfdi/summary?moneda_vista=${viewCurrency}`);
      setSummary(summaryRes.data);
    } catch (error) {
      toast.error('Error cargando datos');
    } finally {
      setLoading(false);
    }
  };

  const loadSummary = async () => {
    try {
      const summaryRes = await api.get(`/cfdi/summary?moneda_vista=${viewCurrency}`);
      setSummary(summaryRes.data);
    } catch (error) {
      console.error('Error loading summary');
    }
  };

  const [uploading, setUploading] = useState(false);
  const [uploadProgress, setUploadProgress] = useState({ total: 0, current: 0, success: 0, failed: 0 });
  const [pdfInvoiceUploaderOpen, setPdfInvoiceUploaderOpen] = useState(false);  // PDF Invoice uploader modal
  const [bankAccounts, setBankAccounts] = useState([]);

  // Load bank accounts for PDF importer
  useEffect(() => {
    const loadBankAccounts = async () => {
      try {
        const res = await api.get('/api/bank-accounts');
        setBankAccounts(res.data || []);
      } catch (err) {
        console.error('Error loading bank accounts:', err);
      }
    };
    loadBankAccounts();
  }, []);

  const handleFileUpload = async (e) => {
    const files = Array.from(e.target.files);
    if (files.length === 0) return;

    setUploading(true);
    setUploadProgress({ total: files.length, current: 0, success: 0, failed: 0 });

    let successCount = 0;
    let failedCount = 0;
    let aiCategorizedCount = 0;
    let nominaAutoReconciledCount = 0;
    let newRfcsDetected = [];
    const errors = [];

    for (let i = 0; i < files.length; i++) {
      const file = files[i];
      setUploadProgress(prev => ({ ...prev, current: i + 1 }));

      const formData = new FormData();
      formData.append('file', file);

      try {
        const response = await api.post('/cfdi/upload', formData, {
          headers: { 'Content-Type': 'multipart/form-data' }
        });
        successCount++;
        if (response.data.ai_categorized) {
          aiCategorizedCount++;
        }
        // Track nóminas auto-reconciled
        if (response.data.is_nomina && response.data.nomina_auto_reconciled) {
          nominaAutoReconciledCount++;
        }
        // Check for new RFC detected
        if (response.data.new_rfc_detected) {
          newRfcsDetected.push({
            ...response.data.new_rfc_detected,
            cfdi_id: response.data.cfdi_id,
            uuid: response.data.uuid
          });
        }
        setUploadProgress(prev => ({ ...prev, success: successCount }));
      } catch (error) {
        failedCount++;
        errors.push(`${file.name}: ${error.response?.data?.detail || 'Error'}`);
        setUploadProgress(prev => ({ ...prev, failed: failedCount }));
      }
    }

    setUploading(false);
    
    if (successCount > 0) {
      let message = `${successCount} CFDI(s) subido(s)`;
      if (aiCategorizedCount > 0) {
        message += ` - ${aiCategorizedCount} categorizado(s) con IA ✨`;
      }
      if (nominaAutoReconciledCount > 0) {
        message += ` - ${nominaAutoReconciledCount} nómina(s) auto-conciliada(s) 💼`;
      }
      toast.success(message);
    }
    if (failedCount > 0) {
      toast.error(`${failedCount} archivo(s) fallaron: ${errors.slice(0, 3).join(', ')}${errors.length > 3 ? '...' : ''}`);
    }

    // Show dialog for first new RFC detected
    if (newRfcsDetected.length > 0) {
      setNewRfcDialog({
        open: true,
        data: newRfcsDetected[0],
        cfdiId: newRfcsDetected[0].cfdi_id,
        remaining: newRfcsDetected.slice(1)
      });
    }
    
    loadData();
    e.target.value = '';
  };

  const handleDeleteClick = (cfdi) => {
    setCfdiToDelete(cfdi);
    setDeleteDialogOpen(true);
  };

  const handleDeleteConfirm = async () => {
    if (!cfdiToDelete) return;
    
    try {
      await api.delete(`/cfdi/${cfdiToDelete.id}`);
      toast.success('CFDI eliminado correctamente');
      loadData();
    } catch (error) {
      toast.error(error.response?.data?.detail || 'Error eliminando CFDI');
    } finally {
      setDeleteDialogOpen(false);
      setCfdiToDelete(null);
    }
  };

  const handleCategorizeClick = (cfdi) => {
    setCfdiToCategorize(cfdi);
    setCategorizeData({
      category_id: cfdi.category_id || '',
      subcategory_id: cfdi.subcategory_id || '',
      customer_id: cfdi.customer_id || '',
      vendor_id: cfdi.vendor_id || ''
    });
    setCategorizeDialogOpen(true);
  };

  const handleCategorizeSave = async () => {
    if (!cfdiToCategorize) return;
    
    try {
      const params = new URLSearchParams();
      if (categorizeData.category_id) params.append('category_id', categorizeData.category_id);
      if (categorizeData.subcategory_id) params.append('subcategory_id', categorizeData.subcategory_id);
      if (categorizeData.customer_id) params.append('customer_id', categorizeData.customer_id);
      if (categorizeData.vendor_id) params.append('vendor_id', categorizeData.vendor_id);
      
      await api.put(`/cfdi/${cfdiToCategorize.id}/categorize?${params.toString()}`);
      toast.success('CFDI categorizado');
      setCategorizeDialogOpen(false);
      loadData();
    } catch (error) {
      toast.error('Error categorizando CFDI');
    }
  };

  const handleReconciliationChange = async (cfdiId, status) => {
    try {
      await api.put(`/cfdi/${cfdiId}/reconciliation-status?status=${status}`);
      toast.success(`Estado cambiado a ${RECONCILIATION_STATUS[status].label}`);
      loadData();
    } catch (error) {
      toast.error('Error actualizando estado');
    }
  };

  // Create customer/vendor from new RFC
  const handleCreateParty = async () => {
    if (!newRfcDialog.data) return;
    
    const { type, rfc, nombre_sugerido } = newRfcDialog.data;
    const cfdiId = newRfcDialog.cfdiId;
    
    try {
      const params = new URLSearchParams({
        party_type: type,
        nombre: nombre_sugerido,
        rfc: rfc
      });
      
      const response = await api.post(`/cfdi/${cfdiId}/create-party?${params.toString()}`);
      toast.success(response.data.message);
      
      // Check if there are more new RFCs to process
      if (newRfcDialog.remaining && newRfcDialog.remaining.length > 0) {
        const next = newRfcDialog.remaining[0];
        setNewRfcDialog({
          open: true,
          data: next,
          cfdiId: next.cfdi_id,
          remaining: newRfcDialog.remaining.slice(1)
        });
      } else {
        setNewRfcDialog({ open: false, data: null, cfdiId: null });
      }
      
      loadData();
    } catch (error) {
      toast.error('Error creando ' + (type === 'customer' ? 'cliente' : 'proveedor'));
    }
  };

  const handleSkipNewRfc = () => {
    // Check if there are more
    if (newRfcDialog.remaining && newRfcDialog.remaining.length > 0) {
      const next = newRfcDialog.remaining[0];
      setNewRfcDialog({
        open: true,
        data: next,
        cfdiId: next.cfdi_id,
        remaining: newRfcDialog.remaining.slice(1)
      });
    } else {
      setNewRfcDialog({ open: false, data: null, cfdiId: null });
    }
  };

  // View CFDI Detail
  const handleViewDetail = (cfdi) => {
    setCfdiDetail(cfdi);
    setCfdiNotes(cfdi.notas || '');
    setDetailDialogOpen(true);
  };

  const handleSaveNotes = async () => {
    if (!cfdiDetail) return;
    
    try {
      await api.put(`/cfdi/${cfdiDetail.id}/notes`, { notas: cfdiNotes });
      toast.success('Notas guardadas');
      loadData();
    } catch (error) {
      toast.error('Error guardando notas');
    }
  };

  // AI Categorization Functions
  const handleAiCategorizeSingle = async (cfdiId) => {
    setAiCategorizingSingle(cfdiId);
    try {
      const response = await api.post(`/cfdi/${cfdiId}/ai-categorize`);
      const data = response.data;
      
      if (data.success && data.suggestion?.category_id) {
        // Show suggestion and ask to apply
        const categoryName = getCategoryName(data.suggestion.category_id);
        const confidence = data.suggestion.confidence || 0;
        
        if (window.confirm(`IA sugiere: "${categoryName}" (${confidence}% confianza)\n\nRazón: ${data.suggestion.reasoning}\n\n¿Aplicar esta categoría?`)) {
          const params = new URLSearchParams();
          params.append('category_id', data.suggestion.category_id);
          if (data.suggestion.subcategory_id) {
            params.append('subcategory_id', data.suggestion.subcategory_id);
          }
          await api.put(`/cfdi/${cfdiId}/categorize?${params.toString()}`);
          toast.success(`CFDI categorizado como "${categoryName}"`);
          loadData();
        }
      } else {
        toast.error(data.error || 'No se pudo determinar una categoría');
      }
    } catch (error) {
      toast.error('Error en categorización IA');
    } finally {
      setAiCategorizingSingle(null);
    }
  };

  const handleAiCategorizeAll = async () => {
    const uncategorizedCount = cfdis.filter(c => !c.category_id).length;
    if (uncategorizedCount === 0) {
      toast.info('Todos los CFDIs ya están categorizados');
      return;
    }
    
    setAiCategorizingAll(true);
    try {
      const response = await api.post('/cfdi/ai-categorize-batch?apply_suggestions=false');
      const data = response.data;
      
      if (data.success) {
        setAiResults(data.results || []);
        setAiResultsDialogOpen(true);
        toast.success(`${data.processed} CFDIs analizados`);
      } else {
        toast.error('Error procesando CFDIs');
      }
    } catch (error) {
      toast.error('Error en categorización masiva');
    } finally {
      setAiCategorizingAll(false);
    }
  };

  const handleApplyAiSuggestion = async (result) => {
    if (!result.category_id) return;
    
    try {
      const params = new URLSearchParams();
      params.append('category_id', result.category_id);
      if (result.subcategory_id) {
        params.append('subcategory_id', result.subcategory_id);
      }
      await api.put(`/cfdi/${result.cfdi_id}/categorize?${params.toString()}`);
      
      // Update local state
      setAiResults(prev => prev.map(r => 
        r.cfdi_id === result.cfdi_id ? {...r, applied: true} : r
      ));
      toast.success('Categoría aplicada');
      loadData();
    } catch (error) {
      toast.error('Error aplicando categoría');
    }
  };

  const handleApplyAllAiSuggestions = async () => {
    const toApply = aiResults.filter(r => r.success && r.category_id && !r.applied && (r.confidence || 0) >= 70);
    
    for (const result of toApply) {
      await handleApplyAiSuggestion(result);
    }
    
    toast.success(`${toApply.length} categorías aplicadas`);
  };

  const getCategoryName = (categoryId) => {
    const cat = categories.find(c => c.id === categoryId);
    return cat ? cat.nombre : '';
  };

  const getSubcategoryName = (categoryId, subcategoryId) => {
    const cat = categories.find(c => c.id === categoryId);
    if (cat && cat.subcategorias) {
      const subcat = cat.subcategorias.find(s => s.id === subcategoryId);
      return subcat ? subcat.nombre : '';
    }
    return '';
  };

  const getCustomerName = (customerId) => {
    const customer = customers.find(c => c.id === customerId);
    return customer ? customer.nombre : '';
  };

  const getVendorName = (vendorId) => {
    const vendor = vendors.find(v => v.id === vendorId);
    return vendor ? vendor.nombre : '';
  };

  const selectedCategoryForDialog = categories.find(c => c.id === categorizeData.category_id);
  
  // Get subcategories for selected filter category
  const selectedFilterCategory = categories.find(c => c.id === filterCategory);
  const availableSubcategories = selectedFilterCategory?.subcategorias || [];

  // Filter CFDIs
  const filteredCfdis = cfdis.filter(cfdi => {
    // Category filter
    if (filterCategory !== 'all' && cfdi.category_id !== filterCategory) return false;
    
    // Subcategory filter
    if (filterSubcategory !== 'all' && cfdi.subcategory_id !== filterSubcategory) return false;
    
    // Reconciliation filter
    if (filterReconciliation !== 'all' && (cfdi.estado_conciliacion || 'pendiente') !== filterReconciliation) return false;
    
    // Date from filter
    if (filterDateFrom) {
      const cfdiDate = new Date(cfdi.fecha_emision);
      const fromDate = new Date(filterDateFrom);
      if (cfdiDate < fromDate) return false;
    }
    
    // Date to filter
    if (filterDateTo) {
      const cfdiDate = new Date(cfdi.fecha_emision);
      const toDate = new Date(filterDateTo);
      toDate.setHours(23, 59, 59, 999); // End of day
      if (cfdiDate > toDate) return false;
    }
    
    // Emisor filter (search by name or RFC)
    if (filterEmisor) {
      const searchTerm = filterEmisor.toLowerCase();
      const emisorNombre = (cfdi.emisor_nombre || '').toLowerCase();
      const emisorRfc = (cfdi.emisor_rfc || '').toLowerCase();
      if (!emisorNombre.includes(searchTerm) && !emisorRfc.includes(searchTerm)) return false;
    }
    
    // Receptor filter (search by name or RFC)
    if (filterReceptor) {
      const searchTerm = filterReceptor.toLowerCase();
      const receptorNombre = (cfdi.receptor_nombre || '').toLowerCase();
      const receptorRfc = (cfdi.receptor_rfc || '').toLowerCase();
      if (!receptorNombre.includes(searchTerm) && !receptorRfc.includes(searchTerm)) return false;
    }
    
    return true;
  });

  // Export to Excel function
  // Export to Excel using xlsx library
  const handleExportToExcel = () => {
    if (filteredCfdis.length === 0) {
      toast.error('No hay CFDIs para exportar');
      return;
    }
    
    setExporting(true);
    try {
      const success = exportCFDIs(filteredCfdis, categories);
      if (success) {
        toast.success(`${filteredCfdis.length} CFDIs exportados a Excel`);
      } else {
        toast.error('Error al exportar');
      }
    } catch (error) {
      console.error('Export error:', error);
      toast.error('Error al exportar: ' + (error.message || 'Error desconocido'));
    } finally {
      setExporting(false);
    }
  };

  // Clear all filters
  const clearFilters = () => {
    setFilterCategory('all');
    setFilterSubcategory('all');
    setFilterReconciliation('all');
    setFilterDateFrom('');
    setFilterDateTo('');
    setFilterEmisor('');
    setFilterReceptor('');
  };

  // Convert amount to view currency
  const convertAmount = (amount, fromCurrency) => {
    if (fromCurrency === viewCurrency) return amount;
    
    // Convert to MXN first, then to target
    const toMXN = fromCurrency === 'MXN' ? amount : amount * (fxRates[fromCurrency] || 1);
    const converted = viewCurrency === 'MXN' ? toMXN : toMXN / (fxRates[viewCurrency] || 1);
    return converted;
  };

  // Group CFDIs by currency
  const cfdisByCurrency = cfdis.reduce((acc, cfdi) => {
    const moneda = cfdi.moneda || 'MXN';
    if (!acc[moneda]) acc[moneda] = { ingresos: 0, egresos: 0, count: 0 };
    acc[moneda].count++;
    if (cfdi.tipo_cfdi === 'ingreso') {
      acc[moneda].ingresos += cfdi.total;
    } else {
      acc[moneda].egresos += cfdi.total;
    }
    return acc;
  }, {});

  if (loading) return <div className="p-8">Cargando...</div>;

  return (
    <div className="p-8 space-y-6" data-testid="cfdi-page">
      <div className="flex justify-between items-center">
        <div>
          <h1 className="text-4xl font-bold text-[#0F172A] mb-2" style={{fontFamily: 'Manrope'}}>Módulo CFDI / SAT</h1>
          <p className="text-[#64748B]">Gestión de facturas electrónicas</p>
        </div>
        <div className="flex gap-2 items-center">
          {/* AI Categorize Button */}
          <Button
            variant="outline"
            className="gap-2 border-[#8B5CF6] text-[#8B5CF6] hover:bg-[#8B5CF6] hover:text-white"
            onClick={handleAiCategorizeAll}
            disabled={aiCategorizingAll}
            data-testid="ai-categorize-all-button"
          >
            {aiCategorizingAll ? <Loader2 size={16} className="animate-spin" /> : <Sparkles size={16} />}
            {aiCategorizingAll ? 'Analizando...' : 'Categorizar con IA'}
          </Button>
          
          {/* Currency Selector */}
          <div className="flex items-center gap-2 bg-white border rounded-md px-3 py-1">
            <span className="text-sm text-[#64748B]">Ver en:</span>
            <Select value={viewCurrency} onValueChange={setViewCurrency}>
              <SelectTrigger className="w-24 border-0 p-0 h-8" data-testid="currency-selector">
                <SelectValue />
              </SelectTrigger>
              <SelectContent>
                {CURRENCIES.map(c => (
                  <SelectItem key={c} value={c}>{c}</SelectItem>
                ))}
              </SelectContent>
            </Select>
          </div>
          
          <Button
            className="bg-[#0F172A] hover:bg-[#1E293B] gap-2"
            onClick={() => document.getElementById('cfdi-upload').click()}
            data-testid="upload-cfdi-button"
            disabled={uploading}
          >
            <Upload size={16} />
            {uploading ? `Subiendo ${uploadProgress.current}/${uploadProgress.total}...` : 'Subir XML CFDIs'}
          </Button>
          <input
            id="cfdi-upload"
            type="file"
            accept=".xml"
            multiple
            className="hidden"
            onChange={handleFileUpload}
          />
          
          {/* PDF Invoice Importer Button */}
          <Button 
            variant="outline" 
            className="gap-2 border-purple-300 text-purple-700 hover:bg-purple-50"
            onClick={() => setPdfInvoiceUploaderOpen(true)}
            data-testid="import-factura-pdf-btn"
          >
            <FilePlus size={16} />
            Importar Factura PDF
          </Button>
        </div>
      </div>

      {/* Upload Progress */}
      {uploading && (
        <Card className="border-[#0EA5E9] bg-blue-50">
          <CardContent className="py-4">
            <div className="flex items-center gap-4">
              <div className="flex-1">
                <div className="flex justify-between text-sm mb-1">
                  <span className="text-[#0369A1]">Subiendo archivos...</span>
                  <span className="text-[#0369A1]">{uploadProgress.current} de {uploadProgress.total}</span>
                </div>
                <div className="w-full bg-blue-200 rounded-full h-2">
                  <div 
                    className="bg-[#0EA5E9] h-2 rounded-full transition-all duration-300"
                    style={{ width: `${(uploadProgress.current / uploadProgress.total) * 100}%` }}
                  />
                </div>
                <div className="flex gap-4 mt-2 text-xs">
                  <span className="text-green-600">✓ {uploadProgress.success} exitosos</span>
                  {uploadProgress.failed > 0 && <span className="text-red-600">✗ {uploadProgress.failed} fallidos</span>}
                </div>
              </div>
            </div>
          </CardContent>
        </Card>
      )}

      {/* Summary Cards with Currency */}
      <div className="grid grid-cols-1 md:grid-cols-4 gap-4">
        <Card className="border-[#E2E8F0]">
          <CardHeader>
            <CardTitle className="text-sm font-medium text-[#64748B]">Total CFDIs</CardTitle>
          </CardHeader>
          <CardContent>
            <div className="text-3xl font-bold mono text-[#0F172A]">{cfdis.length}</div>
            <div className="text-xs text-[#94A3B8] mt-1">
              {Object.entries(cfdisByCurrency).map(([cur, data]) => (
                <span key={cur} className="mr-2">{data.count} {cur}</span>
              ))}
            </div>
          </CardContent>
        </Card>

        <Card className="border-[#10B981] bg-green-50">
          <CardHeader>
            <CardTitle className="text-sm font-medium text-[#059669] flex items-center gap-2">
              <TrendingUp size={16} />
              Ingresos ({viewCurrency})
            </CardTitle>
          </CardHeader>
          <CardContent>
            <div className="text-2xl font-bold mono text-[#059669]">
              ${(summary?.totales_convertidos?.ingresos || 0).toLocaleString('es-MX', {minimumFractionDigits: 2})}
            </div>
            <div className="text-xs text-[#64748B] mt-1">
              {Object.entries(summary?.totales_por_moneda?.ingresos || {}).map(([cur, amt]) => (
                <div key={cur}>{cur}: ${amt.toLocaleString('es-MX', {minimumFractionDigits: 2})}</div>
              ))}
            </div>
          </CardContent>
        </Card>

        <Card className="border-[#EF4444] bg-red-50">
          <CardHeader>
            <CardTitle className="text-sm font-medium text-[#DC2626] flex items-center gap-2">
              <TrendingDown size={16} />
              Egresos ({viewCurrency})
            </CardTitle>
          </CardHeader>
          <CardContent>
            <div className="text-2xl font-bold mono text-[#DC2626]">
              ${(summary?.totales_convertidos?.egresos || 0).toLocaleString('es-MX', {minimumFractionDigits: 2})}
            </div>
            <div className="text-xs text-[#64748B] mt-1">
              {Object.entries(summary?.totales_por_moneda?.egresos || {}).map(([cur, amt]) => (
                <div key={cur}>{cur}: ${amt.toLocaleString('es-MX', {minimumFractionDigits: 2})}</div>
              ))}
            </div>
          </CardContent>
        </Card>

        <Card className={`border-2 ${(summary?.balance_convertido || 0) >= 0 ? 'border-[#10B981] bg-green-50' : 'border-[#EF4444] bg-red-50'}`}>
          <CardHeader>
            <CardTitle className={`text-sm font-medium flex items-center gap-2 ${(summary?.balance_convertido || 0) >= 0 ? 'text-[#059669]' : 'text-[#DC2626]'}`}>
              Balance ({viewCurrency})
            </CardTitle>
          </CardHeader>
          <CardContent>
            <div className={`text-2xl font-bold mono ${(summary?.balance_convertido || 0) >= 0 ? 'text-[#059669]' : 'text-[#DC2626]'}`}>
              {(summary?.balance_convertido || 0) >= 0 ? '+' : ''}${(summary?.balance_convertido || 0).toLocaleString('es-MX', {minimumFractionDigits: 2})}
            </div>
          </CardContent>
        </Card>
      </div>

      {/* Integrations Section */}
      <div className="grid grid-cols-1 lg:grid-cols-2 gap-4">
        {/* SAT Integration */}
        <SATIntegration onSyncComplete={loadData} />
        
        {/* Alegra Integration */}
        <AlegraIntegration />
      </div>

      {/* Exchange Rates Info */}
      {Object.keys(fxRates).length > 1 && (
        <Card className="border-[#E2E8F0] bg-[#F8FAFC]">
          <CardContent className="py-3">
            <div className="flex items-center gap-4 text-sm">
              <span className="text-[#64748B] font-medium">Tipos de cambio:</span>
              {Object.entries(fxRates).filter(([k]) => k !== 'MXN').map(([cur, rate]) => (
                <span key={cur} className="mono">
                  1 MXN = {(1/rate).toFixed(4)} {cur}
                  <span className="text-[#94A3B8] mx-2">|</span>
                  1 {cur} = {rate.toFixed(2)} MXN
                </span>
              ))}
              <Button variant="ghost" size="sm" onClick={loadData} className="ml-auto gap-1">
                <RefreshCw size={14} />
                Actualizar
              </Button>
            </div>
          </CardContent>
        </Card>
      )}

      {/* Filters */}
      <Card className="border-[#E2E8F0]">
        <CardContent className="py-4">
          <div className="flex flex-wrap gap-4 items-center">
            {/* Emisor Filter */}
            <div className="space-y-1">
              <Label className="text-xs">Emisor</Label>
              <Input
                type="text"
                placeholder="Buscar emisor..."
                value={filterEmisor}
                onChange={(e) => setFilterEmisor(e.target.value)}
                className="w-44"
                data-testid="filter-emisor"
              />
            </div>
            
            {/* Receptor Filter */}
            <div className="space-y-1">
              <Label className="text-xs">Receptor</Label>
              <Input
                type="text"
                placeholder="Buscar receptor..."
                value={filterReceptor}
                onChange={(e) => setFilterReceptor(e.target.value)}
                className="w-44"
                data-testid="filter-receptor"
              />
            </div>
            
            <div className="space-y-1">
              <Label className="text-xs">Categoría</Label>
              <Select value={filterCategory} onValueChange={setFilterCategory}>
                <SelectTrigger className="w-40" data-testid="filter-category">
                  <SelectValue placeholder="Todas" />
                </SelectTrigger>
                <SelectContent>
                  <SelectItem value="all">Todas</SelectItem>
                  {categories.map(cat => (
                    <SelectItem key={cat.id} value={cat.id}>{cat.nombre}</SelectItem>
                  ))}
                </SelectContent>
              </Select>
            </div>
            
            {/* Subcategory Filter - only show if category is selected */}
            {filterCategory !== 'all' && availableSubcategories.length > 0 && (
              <div className="space-y-1">
                <Label className="text-xs">Subcategoría</Label>
                <Select value={filterSubcategory} onValueChange={setFilterSubcategory}>
                  <SelectTrigger className="w-48" data-testid="filter-subcategory">
                    <SelectValue placeholder="Todas" />
                  </SelectTrigger>
                  <SelectContent>
                    <SelectItem value="all">Todas</SelectItem>
                    {availableSubcategories.map(sub => (
                      <SelectItem key={sub.id} value={sub.id}>{sub.nombre}</SelectItem>
                    ))}
                  </SelectContent>
                </Select>
              </div>
            )}
            
            <div className="space-y-1">
              <Label className="text-xs">Estado Conciliación</Label>
              <Select value={filterReconciliation} onValueChange={setFilterReconciliation}>
                <SelectTrigger className="w-40" data-testid="filter-reconciliation">
                  <SelectValue placeholder="Todos" />
                </SelectTrigger>
                <SelectContent>
                  <SelectItem value="all">Todos</SelectItem>
                  <SelectItem value="pendiente">Pendiente</SelectItem>
                  <SelectItem value="conciliado">Conciliado</SelectItem>
                  <SelectItem value="no_conciliable">No Conciliable</SelectItem>
                </SelectContent>
              </Select>
            </div>
            
            {/* Date Filters */}
            <div className="space-y-1">
              <Label className="text-xs flex items-center gap-1">
                <Calendar size={12} />
                Desde
              </Label>
              <Input
                type="date"
                value={filterDateFrom}
                onChange={(e) => setFilterDateFrom(e.target.value)}
                className="w-36"
                data-testid="filter-date-from"
              />
            </div>
            
            <div className="space-y-1">
              <Label className="text-xs flex items-center gap-1">
                <Calendar size={12} />
                Hasta
              </Label>
              <Input
                type="date"
                value={filterDateTo}
                onChange={(e) => setFilterDateTo(e.target.value)}
                className="w-36"
                data-testid="filter-date-to"
              />
            </div>
            
            <div className="flex gap-2 self-end">
              <Button 
                variant="outline" 
                size="sm"
                onClick={clearFilters}
              >
                <Filter size={14} className="mr-1" />
                Limpiar
              </Button>
              
              <Button 
                variant="default"
                size="sm"
                onClick={handleExportToExcel}
                disabled={exporting || filteredCfdis.length === 0}
                className="bg-green-600 hover:bg-green-700"
                data-testid="export-excel-btn"
              >
                {exporting ? <Loader2 size={14} className="mr-1 animate-spin" /> : <Download size={14} className="mr-1" />}
                Exportar Excel
              </Button>
            </div>
          </div>
        </CardContent>
      </Card>

      <Card className="border-[#E2E8F0]">
        <CardHeader>
          <CardTitle>Listado de CFDIs</CardTitle>
          <CardDescription>{filteredCfdis.length} de {cfdis.length} facturas electrónicas</CardDescription>
        </CardHeader>
        <CardContent>
          <Table className="data-table">
            <TableHeader>
              <TableRow>
                <TableHead>UUID</TableHead>
                <TableHead>Tipo</TableHead>
                <TableHead>Emisor</TableHead>
                <TableHead>Receptor</TableHead>
                <TableHead>Fecha</TableHead>
                <TableHead>Total ({viewCurrency})</TableHead>
                <TableHead>Categoría</TableHead>
                <TableHead>Conciliación</TableHead>
                <TableHead className="text-center">Acciones</TableHead>
              </TableRow>
            </TableHeader>
            <TableBody>
              {filteredCfdis.length === 0 ? (
                <TableRow>
                  <TableCell colSpan={9} className="text-center text-[#94A3B8] py-8">
                    No hay CFDIs que coincidan con los filtros.
                  </TableCell>
                </TableRow>
              ) : (
                filteredCfdis.map((cfdi) => {
                  const moneda = cfdi.moneda || 'MXN';
                  const converted = convertAmount(cfdi.total, moneda);
                  const reconciliationStatus = cfdi.estado_conciliacion || 'pendiente';
                  const ReconciliationIcon = RECONCILIATION_STATUS[reconciliationStatus]?.icon || Clock;
                  
                  return (
                    <TableRow key={cfdi.id} data-testid={`cfdi-row-${cfdi.id}`}>
                      <TableCell className="mono text-xs">{cfdi.uuid.substring(0, 13)}...</TableCell>
                      <TableCell>
                        <span className={`text-xs px-2 py-1 rounded ${
                          cfdi.tipo_cfdi === 'ingreso' 
                            ? 'bg-green-100 text-green-800' 
                            : 'bg-red-100 text-red-800'
                        }`}>
                          {cfdi.tipo_cfdi === 'ingreso' ? '↑ Ingreso' : '↓ Egreso'}
                        </span>
                      </TableCell>
                      <TableCell className="text-sm">
                        <div className="font-medium">{cfdi.emisor_nombre || cfdi.emisor_rfc}</div>
                        <div className="text-xs text-[#94A3B8] mono">{cfdi.emisor_rfc}</div>
                      </TableCell>
                      <TableCell className="text-sm">
                        <div className="font-medium">{cfdi.receptor_nombre || cfdi.receptor_rfc}</div>
                        <div className="text-xs text-[#94A3B8] mono">{cfdi.receptor_rfc}</div>
                      </TableCell>
                      <TableCell className="mono text-sm">{format(new Date(cfdi.fecha_emision), 'dd/MM/yyyy')}</TableCell>
                      <TableCell className={`mono font-semibold ${
                        cfdi.tipo_cfdi === 'ingreso' ? 'text-green-600' : 'text-red-600'
                      }`}>
                        {cfdi.tipo_cfdi === 'ingreso' ? '+' : '-'}${converted.toLocaleString('es-MX', {minimumFractionDigits: 2})}
                        {moneda !== viewCurrency && <span className="text-xs text-[#94A3B8] ml-1">({moneda})</span>}
                      </TableCell>
                      <TableCell>
                        {cfdi.category_id || cfdi.customer_id || cfdi.vendor_id ? (
                          <div className="space-y-1">
                            {cfdi.category_id && (
                              <div className="text-sm font-medium">{getCategoryName(cfdi.category_id)}</div>
                            )}
                            {cfdi.subcategory_id && (
                              <div className="text-xs text-[#64748B]">
                                └ {getSubcategoryName(cfdi.category_id, cfdi.subcategory_id)}
                              </div>
                            )}
                            {cfdi.tipo_cfdi === 'ingreso' && cfdi.customer_id && (
                              <div className="text-xs text-blue-600 font-medium">
                                👤 {getCustomerName(cfdi.customer_id)}
                              </div>
                            )}
                            {cfdi.tipo_cfdi === 'egreso' && cfdi.vendor_id && (
                              <div className="text-xs text-orange-600 font-medium">
                                🏢 {getVendorName(cfdi.vendor_id)}
                              </div>
                            )}
                          </div>
                        ) : (
                          <span className="text-xs text-[#94A3B8]">Sin categoría</span>
                        )}
                      </TableCell>
                      <TableCell>
                        <Select 
                          value={reconciliationStatus} 
                          onValueChange={(value) => handleReconciliationChange(cfdi.id, value)}
                        >
                          <SelectTrigger className={`w-36 h-8 text-xs ${RECONCILIATION_STATUS[reconciliationStatus]?.color}`}>
                            <ReconciliationIcon size={14} className="mr-1" />
                            <SelectValue />
                          </SelectTrigger>
                          <SelectContent>
                            <SelectItem value="pendiente">
                              <span className="flex items-center gap-1">
                                <Clock size={14} /> Pendiente
                              </span>
                            </SelectItem>
                            <SelectItem value="conciliado">
                              <span className="flex items-center gap-1">
                                <CheckCircle2 size={14} /> Conciliado
                              </span>
                            </SelectItem>
                            <SelectItem value="no_conciliable">
                              <span className="flex items-center gap-1">
                                <XCircle size={14} /> No Conciliable
                              </span>
                            </SelectItem>
                          </SelectContent>
                        </Select>
                      </TableCell>
                      <TableCell>
                        <div className="flex justify-center gap-1">
                          <Button
                            variant="ghost"
                            size="sm"
                            onClick={() => handleViewDetail(cfdi)}
                            title="Ver detalles"
                            data-testid={`view-cfdi-${cfdi.id}`}
                          >
                            <Eye size={16} className="text-[#64748B]" />
                          </Button>
                          {!cfdi.category_id && (
                            <Button
                              variant="ghost"
                              size="sm"
                              onClick={() => handleAiCategorizeSingle(cfdi.id)}
                              title="Categorizar con IA"
                              disabled={aiCategorizingSingle === cfdi.id}
                              data-testid={`ai-categorize-cfdi-${cfdi.id}`}
                            >
                              {aiCategorizingSingle === cfdi.id ? (
                                <Loader2 size={16} className="animate-spin text-[#8B5CF6]" />
                              ) : (
                                <Sparkles size={16} className="text-[#8B5CF6]" />
                              )}
                            </Button>
                          )}
                          <Button
                            variant="ghost"
                            size="sm"
                            onClick={() => handleCategorizeClick(cfdi)}
                            title="Categorizar manualmente"
                            data-testid={`categorize-cfdi-${cfdi.id}`}
                          >
                            <Tag size={16} className="text-[#0EA5E9]" />
                          </Button>
                          <Button
                            variant="ghost"
                            size="sm"
                            className="text-red-500 hover:text-red-700 hover:bg-red-50"
                            onClick={() => handleDeleteClick(cfdi)}
                            data-testid={`delete-cfdi-${cfdi.id}`}
                          >
                            <Trash2 size={16} />
                          </Button>
                        </div>
                      </TableCell>
                    </TableRow>
                  );
                })
              )}
            </TableBody>
          </Table>
        </CardContent>
      </Card>

      <Card className="border-[#F59E0B] bg-[#FFFBEB]">
        <CardHeader>
          <CardTitle className="text-[#92400E] flex items-center gap-2">
            <FileText size={20} />
            Automatización SAT - Próximamente
          </CardTitle>
        </CardHeader>
        <CardContent>
          <p className="text-[#92400E] text-sm">
            La descarga automática de CFDIs desde el portal SAT estará disponible próximamente.
            Por ahora, puedes subir manualmente los archivos XML de tus facturas.
          </p>
        </CardContent>
      </Card>

      {/* Delete Confirmation Dialog */}
      <AlertDialog open={deleteDialogOpen} onOpenChange={setDeleteDialogOpen}>
        <AlertDialogContent>
          <AlertDialogHeader>
            <AlertDialogTitle>¿Eliminar CFDI?</AlertDialogTitle>
            <AlertDialogDescription>
              {cfdiToDelete && (
                <>
                  Estás a punto de eliminar el CFDI con UUID: <br />
                  <span className="mono text-sm font-semibold">{cfdiToDelete.uuid}</span>
                  <br /><br />
                  Esta acción no se puede deshacer.
                </>
              )}
            </AlertDialogDescription>
          </AlertDialogHeader>
          <AlertDialogFooter>
            <AlertDialogCancel>Cancelar</AlertDialogCancel>
            <AlertDialogAction 
              onClick={handleDeleteConfirm}
              className="bg-red-600 hover:bg-red-700"
            >
              Eliminar
            </AlertDialogAction>
          </AlertDialogFooter>
        </AlertDialogContent>
      </AlertDialog>

      {/* Categorize Dialog */}
      <Dialog open={categorizeDialogOpen} onOpenChange={setCategorizeDialogOpen}>
        <DialogContent>
          <DialogHeader>
            <DialogTitle>Categorizar CFDI</DialogTitle>
            <DialogDescription>
              Asigna una categoría a este CFDI para reportes y DIOT
            </DialogDescription>
          </DialogHeader>
          {cfdiToCategorize && (
            <div className="space-y-4">
              <div className="p-3 bg-[#F1F5F9] rounded-md">
                <div className="text-sm font-medium">{cfdiToCategorize.emisor_nombre || cfdiToCategorize.emisor_rfc}</div>
                <div className="text-xs text-[#64748B] mono">{cfdiToCategorize.uuid}</div>
                <div className="text-sm font-semibold mt-1">
                  ${cfdiToCategorize.total.toLocaleString('es-MX', {minimumFractionDigits: 2})} {cfdiToCategorize.moneda || 'MXN'}
                </div>
              </div>
              
              <div className="space-y-2">
                <Label>Categoría</Label>
                <Select 
                  value={categorizeData.category_id} 
                  onValueChange={(v) => setCategorizeData({...categorizeData, category_id: v, subcategory_id: ''})}
                >
                  <SelectTrigger data-testid="category-select">
                    <SelectValue placeholder="Seleccionar categoría" />
                  </SelectTrigger>
                  <SelectContent>
                    {categories
                      .filter(c => c.tipo === cfdiToCategorize.tipo_cfdi)
                      .map(cat => (
                        <SelectItem key={cat.id} value={cat.id}>
                          <div className="flex items-center gap-2">
                            <div className="w-3 h-3 rounded-full" style={{backgroundColor: cat.color}} />
                            {cat.nombre}
                          </div>
                        </SelectItem>
                      ))
                    }
                  </SelectContent>
                </Select>
              </div>

              {selectedCategoryForDialog && selectedCategoryForDialog.subcategorias && selectedCategoryForDialog.subcategorias.length > 0 && (
                <div className="space-y-2">
                  <Label>Subcategoría</Label>
                  <Select 
                    value={categorizeData.subcategory_id} 
                    onValueChange={(v) => setCategorizeData({...categorizeData, subcategory_id: v})}
                  >
                    <SelectTrigger>
                      <SelectValue placeholder="Seleccionar subcategoría (opcional)" />
                    </SelectTrigger>
                    <SelectContent>
                      {selectedCategoryForDialog.subcategorias.map(sub => (
                        <SelectItem key={sub.id} value={sub.id}>{sub.nombre}</SelectItem>
                      ))}
                    </SelectContent>
                  </Select>
                </div>
              )}

              {/* Cliente selector for INGRESO type CFDIs */}
              {cfdiToCategorize.tipo_cfdi === 'ingreso' && (
                <div className="space-y-2">
                  <Label className="flex items-center gap-2">
                    <span className="text-blue-600">👤</span> Cliente
                  </Label>
                  <Select 
                    value={categorizeData.customer_id} 
                    onValueChange={(v) => setCategorizeData({...categorizeData, customer_id: v})}
                  >
                    <SelectTrigger data-testid="customer-select">
                      <SelectValue placeholder="Seleccionar cliente" />
                    </SelectTrigger>
                    <SelectContent>
                      {customers.map(customer => (
                        <SelectItem key={customer.id} value={customer.id}>
                          <div className="flex flex-col">
                            <span>{customer.nombre}</span>
                            <span className="text-xs text-[#64748B]">{customer.rfc}</span>
                          </div>
                        </SelectItem>
                      ))}
                    </SelectContent>
                  </Select>
                  <p className="text-xs text-[#64748B]">
                    Asocia este ingreso con un cliente para seguimiento de cuentas por cobrar
                  </p>
                </div>
              )}

              {/* Proveedor selector for EGRESO type CFDIs */}
              {cfdiToCategorize.tipo_cfdi === 'egreso' && (
                <div className="space-y-2">
                  <Label className="flex items-center gap-2">
                    <span className="text-orange-600">🏢</span> Proveedor
                  </Label>
                  <Select 
                    value={categorizeData.vendor_id} 
                    onValueChange={(v) => setCategorizeData({...categorizeData, vendor_id: v})}
                  >
                    <SelectTrigger data-testid="vendor-select">
                      <SelectValue placeholder="Seleccionar proveedor" />
                    </SelectTrigger>
                    <SelectContent>
                      {vendors.map(vendor => (
                        <SelectItem key={vendor.id} value={vendor.id}>
                          <div className="flex flex-col">
                            <span>{vendor.nombre}</span>
                            <span className="text-xs text-[#64748B]">{vendor.rfc}</span>
                          </div>
                        </SelectItem>
                      ))}
                    </SelectContent>
                  </Select>
                  <p className="text-xs text-[#64748B]">
                    Asocia este gasto con un proveedor para seguimiento de cuentas por pagar
                  </p>
                </div>
              )}
            </div>
          )}
          <DialogFooter>
            <Button variant="outline" onClick={() => setCategorizeDialogOpen(false)}>Cancelar</Button>
            <Button onClick={handleCategorizeSave} data-testid="save-categorize-button">Guardar</Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>

      {/* AI Results Dialog */}
      <Dialog open={aiResultsDialogOpen} onOpenChange={setAiResultsDialogOpen}>
        <DialogContent className="max-w-3xl max-h-[80vh] overflow-y-auto">
          <DialogHeader>
            <DialogTitle className="flex items-center gap-2">
              <Sparkles className="text-[#8B5CF6]" />
              Resultados de Categorización IA
            </DialogTitle>
            <DialogDescription>
              {aiResults.length} CFDIs analizados. Revisa las sugerencias y aplica las que consideres correctas.
            </DialogDescription>
          </DialogHeader>
          
          <div className="space-y-3 py-4">
            {aiResults.map((result, idx) => (
              <div 
                key={result.cfdi_id || idx}
                className={`p-3 rounded-lg border ${
                  result.applied ? 'border-green-300 bg-green-50' :
                  result.success && result.category_id ? 'border-[#8B5CF6] bg-violet-50' :
                  'border-gray-200 bg-gray-50'
                }`}
              >
                <div className="flex justify-between items-start">
                  <div className="flex-1">
                    <div className="text-sm font-medium">{result.emisor || result.cfdi_uuid?.substring(0, 13)}</div>
                    <div className="text-xs text-[#64748B] mono">{result.cfdi_uuid}</div>
                    {result.total && (
                      <div className="text-sm font-semibold mt-1">${result.total.toLocaleString('es-MX', {minimumFractionDigits: 2})}</div>
                    )}
                  </div>
                  
                  <div className="text-right">
                    {result.success && result.category_id ? (
                      <>
                        <div className="text-sm font-medium text-[#8B5CF6]">
                          {getCategoryName(result.category_id)}
                        </div>
                        <div className="text-xs">
                          <span className={`px-2 py-0.5 rounded ${
                            result.confidence >= 80 ? 'bg-green-100 text-green-800' :
                            result.confidence >= 60 ? 'bg-yellow-100 text-yellow-800' :
                            'bg-gray-100 text-gray-600'
                          }`}>
                            {result.confidence}% confianza
                          </span>
                        </div>
                      </>
                    ) : (
                      <div className="text-xs text-red-500">Sin sugerencia</div>
                    )}
                  </div>
                </div>
                
                {result.reasoning && (
                  <div className="mt-2 text-xs text-[#64748B] italic">
                    {result.reasoning}
                  </div>
                )}
                
                {result.success && result.category_id && !result.applied && (
                  <div className="mt-2 flex justify-end">
                    <Button
                      size="sm"
                      variant="outline"
                      className="text-[#8B5CF6] border-[#8B5CF6]"
                      onClick={() => handleApplyAiSuggestion(result)}
                    >
                      <CheckCircle2 size={14} className="mr-1" />
                      Aplicar
                    </Button>
                  </div>
                )}
                
                {result.applied && (
                  <div className="mt-2 flex justify-end">
                    <span className="text-xs text-green-600 flex items-center gap-1">
                      <CheckCircle2 size={14} /> Aplicado
                    </span>
                  </div>
                )}
              </div>
            ))}
          </div>
          
          <DialogFooter>
            <Button variant="outline" onClick={() => setAiResultsDialogOpen(false)}>Cerrar</Button>
            {aiResults.some(r => r.success && r.category_id && !r.applied && r.confidence >= 70) && (
              <Button 
                className="bg-[#8B5CF6] hover:bg-[#7C3AED]"
                onClick={handleApplyAllAiSuggestions}
              >
                <Sparkles size={16} className="mr-1" />
                Aplicar Todas (&gt;70% confianza)
              </Button>
            )}
          </DialogFooter>
        </DialogContent>
      </Dialog>

      {/* New RFC Detected Dialog */}
      <Dialog open={newRfcDialog.open} onOpenChange={(open) => !open && setNewRfcDialog({ open: false, data: null, cfdiId: null })}>
        <DialogContent>
          <DialogHeader>
            <DialogTitle className="flex items-center gap-2">
              {newRfcDialog.data?.type === 'customer' ? (
                <>
                  <span className="text-blue-600">👤</span> Nuevo Cliente Detectado
                </>
              ) : (
                <>
                  <span className="text-orange-600">🏢</span> Nuevo Proveedor Detectado
                </>
              )}
            </DialogTitle>
            <DialogDescription>
              {newRfcDialog.data?.message}
            </DialogDescription>
          </DialogHeader>
          
          {newRfcDialog.data && (
            <div className="space-y-4 py-4">
              <div className="p-4 bg-[#F1F5F9] rounded-lg">
                <div className="grid grid-cols-2 gap-4">
                  <div>
                    <Label className="text-xs text-[#64748B]">RFC</Label>
                    <div className="font-mono font-semibold">{newRfcDialog.data.rfc}</div>
                  </div>
                  <div>
                    <Label className="text-xs text-[#64748B]">Nombre Sugerido</Label>
                    <div className="font-medium">{newRfcDialog.data.nombre_sugerido}</div>
                  </div>
                </div>
              </div>
              
              <p className="text-sm text-[#64748B]">
                {newRfcDialog.data.type === 'customer' 
                  ? 'Al crear este cliente, podrás asociar futuros CFDIs de ingreso automáticamente.'
                  : 'Al crear este proveedor, podrás asociar futuros CFDIs de egreso automáticamente.'}
              </p>
              
              {newRfcDialog.remaining && newRfcDialog.remaining.length > 0 && (
                <p className="text-xs text-[#94A3B8]">
                  {newRfcDialog.remaining.length} RFC(s) más pendiente(s) por revisar
                </p>
              )}
            </div>
          )}
          
          <DialogFooter>
            <Button variant="outline" onClick={handleSkipNewRfc}>
              Omitir
            </Button>
            <Button 
              className={newRfcDialog.data?.type === 'customer' ? 'bg-blue-600 hover:bg-blue-700' : 'bg-orange-600 hover:bg-orange-700'}
              onClick={handleCreateParty}
            >
              Crear {newRfcDialog.data?.type === 'customer' ? 'Cliente' : 'Proveedor'}
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>

      {/* CFDI Detail Dialog */}
      <Dialog open={detailDialogOpen} onOpenChange={setDetailDialogOpen}>
        <DialogContent className="max-w-4xl max-h-[90vh] overflow-y-auto">
          <DialogHeader>
            <DialogTitle className="flex items-center gap-2">
              <FileText className="text-[#0F172A]" />
              Detalle de Factura
            </DialogTitle>
          </DialogHeader>
          
          {cfdiDetail && (
            <div className="space-y-6">
              {/* Header Info */}
              <div className="grid grid-cols-2 gap-4">
                {/* Emisor */}
                <div className="p-4 bg-[#F8FAFC] rounded-lg border border-[#E2E8F0]">
                  <h3 className="text-sm font-semibold text-[#64748B] mb-3 uppercase">Emisor</h3>
                  <div className="space-y-2">
                    <div>
                      <Label className="text-xs text-[#94A3B8]">RFC (EMISOR)</Label>
                      <div className="font-mono font-semibold text-[#0F172A]">{cfdiDetail.emisor_rfc}</div>
                    </div>
                    <div>
                      <Label className="text-xs text-[#94A3B8]">RAZÓN SOCIAL (EMISOR)</Label>
                      <div className="font-medium text-[#0F172A]">{cfdiDetail.emisor_nombre || 'N/A'}</div>
                    </div>
                  </div>
                </div>
                
                {/* Receptor */}
                <div className="p-4 bg-[#F8FAFC] rounded-lg border border-[#E2E8F0]">
                  <h3 className="text-sm font-semibold text-[#64748B] mb-3 uppercase">Receptor</h3>
                  <div className="space-y-2">
                    <div>
                      <Label className="text-xs text-[#94A3B8]">RFC (RECEPTOR)</Label>
                      <div className="font-mono font-semibold text-[#0F172A]">{cfdiDetail.receptor_rfc}</div>
                    </div>
                    <div>
                      <Label className="text-xs text-[#94A3B8]">RAZÓN SOCIAL (RECEPTOR)</Label>
                      <div className="font-medium text-[#0F172A]">{cfdiDetail.receptor_nombre || 'N/A'}</div>
                    </div>
                  </div>
                </div>
              </div>

              {/* Document Info */}
              <div className="grid grid-cols-4 gap-4">
                <div className="p-3 bg-white rounded-lg border border-[#E2E8F0]">
                  <Label className="text-xs text-[#94A3B8]">UUID</Label>
                  <div className="font-mono text-xs text-[#0F172A] break-all">{cfdiDetail.uuid}</div>
                </div>
                <div className="p-3 bg-white rounded-lg border border-[#E2E8F0]">
                  <Label className="text-xs text-[#94A3B8]">TIPO DE FACTURA</Label>
                  <div className={`font-semibold ${cfdiDetail.tipo_cfdi === 'ingreso' ? 'text-green-600' : 'text-red-600'}`}>
                    {cfdiDetail.tipo_cfdi === 'ingreso' ? '↑ INGRESO' : '↓ EGRESO'}
                  </div>
                </div>
                <div className="p-3 bg-white rounded-lg border border-[#E2E8F0]">
                  <Label className="text-xs text-[#94A3B8]">MÉTODO DE PAGO</Label>
                  <div className="font-medium text-[#0F172A]">{cfdiDetail.metodo_pago || 'PUE'}</div>
                </div>
                <div className="p-3 bg-white rounded-lg border border-[#E2E8F0]">
                  <Label className="text-xs text-[#94A3B8]">FORMA DE PAGO</Label>
                  <div className="font-medium text-[#0F172A]">{cfdiDetail.forma_pago || 'N/A'}</div>
                </div>
              </div>

              {/* Dates and Status */}
              <div className="grid grid-cols-4 gap-4">
                <div className="p-3 bg-white rounded-lg border border-[#E2E8F0]">
                  <Label className="text-xs text-[#94A3B8]">FECHA DE EMISIÓN</Label>
                  <div className="font-mono text-[#0F172A]">{format(new Date(cfdiDetail.fecha_emision), 'dd/MM/yyyy HH:mm')}</div>
                </div>
                <div className="p-3 bg-white rounded-lg border border-[#E2E8F0]">
                  <Label className="text-xs text-[#94A3B8]">FECHA TIMBRADO</Label>
                  <div className="font-mono text-[#0F172A]">
                    {cfdiDetail.fecha_timbrado ? format(new Date(cfdiDetail.fecha_timbrado), 'dd/MM/yyyy HH:mm') : 'N/A'}
                  </div>
                </div>
                <div className="p-3 bg-white rounded-lg border border-[#E2E8F0]">
                  <Label className="text-xs text-[#94A3B8]">USO DEL CFDI</Label>
                  <div className="font-medium text-[#0F172A]">{cfdiDetail.uso_cfdi || 'G03'}</div>
                </div>
                <div className="p-3 bg-white rounded-lg border border-[#E2E8F0]">
                  <Label className="text-xs text-[#94A3B8]">ESTADO</Label>
                  <div className={`font-semibold ${cfdiDetail.estado_cancelacion === 'cancelado' ? 'text-red-600' : 'text-green-600'}`}>
                    {cfdiDetail.estado_cancelacion === 'cancelado' ? '❌ CANCELADO' : '✅ VIGENTE'}
                  </div>
                </div>
              </div>

              {/* Amounts Table */}
              <div className="border border-[#E2E8F0] rounded-lg overflow-hidden">
                <div className="bg-[#0F172A] text-white px-4 py-2">
                  <h3 className="font-semibold text-sm">DESGLOSE DE IMPORTES ({cfdiDetail.moneda || 'MXN'})</h3>
                </div>
                <Table>
                  <TableHeader>
                    <TableRow className="bg-[#F8FAFC]">
                      <TableHead className="font-semibold">CONCEPTO</TableHead>
                      <TableHead className="text-right font-semibold">IMPORTE</TableHead>
                    </TableRow>
                  </TableHeader>
                  <TableBody>
                    <TableRow>
                      <TableCell>Subtotal</TableCell>
                      <TableCell className="text-right font-mono">
                        ${(cfdiDetail.subtotal || 0).toLocaleString('es-MX', {minimumFractionDigits: 2})}
                      </TableCell>
                    </TableRow>
                    <TableRow>
                      <TableCell>Descuento</TableCell>
                      <TableCell className="text-right font-mono text-[#94A3B8]">
                        ${(cfdiDetail.descuento || 0).toLocaleString('es-MX', {minimumFractionDigits: 2})}
                      </TableCell>
                    </TableRow>
                    <TableRow className="bg-[#F8FAFC]">
                      <TableCell className="font-semibold">IVA (16%)</TableCell>
                      <TableCell className="text-right font-mono">
                        ${((cfdiDetail.impuestos || 0)).toLocaleString('es-MX', {minimumFractionDigits: 2})}
                      </TableCell>
                    </TableRow>
                    <TableRow>
                      <TableCell>ISR Retenido</TableCell>
                      <TableCell className="text-right font-mono text-[#94A3B8]">
                        ${(cfdiDetail.isr_retenido || 0).toLocaleString('es-MX', {minimumFractionDigits: 2})}
                      </TableCell>
                    </TableRow>
                    <TableRow>
                      <TableCell>IVA Retenido</TableCell>
                      <TableCell className="text-right font-mono text-[#94A3B8]">
                        ${(cfdiDetail.iva_retenido || 0).toLocaleString('es-MX', {minimumFractionDigits: 2})}
                      </TableCell>
                    </TableRow>
                    <TableRow>
                      <TableCell>IEPS</TableCell>
                      <TableCell className="text-right font-mono text-[#94A3B8]">
                        ${(cfdiDetail.ieps || 0).toLocaleString('es-MX', {minimumFractionDigits: 2})}
                      </TableCell>
                    </TableRow>
                    <TableRow>
                      <TableCell>Impuestos Locales</TableCell>
                      <TableCell className="text-right font-mono text-[#94A3B8]">
                        ${(cfdiDetail.impuestos_locales || 0).toLocaleString('es-MX', {minimumFractionDigits: 2})}
                      </TableCell>
                    </TableRow>
                    <TableRow className="bg-[#0F172A] text-white">
                      <TableCell className="font-bold text-lg">TOTAL</TableCell>
                      <TableCell className="text-right font-mono font-bold text-lg">
                        ${(cfdiDetail.total || 0).toLocaleString('es-MX', {minimumFractionDigits: 2})}
                      </TableCell>
                    </TableRow>
                  </TableBody>
                </Table>
              </div>

              {/* Category Info */}
              {(cfdiDetail.category_id || cfdiDetail.customer_id || cfdiDetail.vendor_id) && (
                <div className="p-4 bg-[#F0F9FF] rounded-lg border border-[#0EA5E9]">
                  <h3 className="text-sm font-semibold text-[#0369A1] mb-3">CLASIFICACIÓN</h3>
                  <div className="grid grid-cols-3 gap-4">
                    {cfdiDetail.category_id && (
                      <div>
                        <Label className="text-xs text-[#0369A1]">CATEGORÍA</Label>
                        <div className="font-medium">{getCategoryName(cfdiDetail.category_id)}</div>
                        {cfdiDetail.subcategory_id && (
                          <div className="text-sm text-[#64748B]">
                            └ {getSubcategoryName(cfdiDetail.category_id, cfdiDetail.subcategory_id)}
                          </div>
                        )}
                      </div>
                    )}
                    {cfdiDetail.customer_id && (
                      <div>
                        <Label className="text-xs text-[#0369A1]">CLIENTE</Label>
                        <div className="font-medium text-blue-600">👤 {getCustomerName(cfdiDetail.customer_id)}</div>
                      </div>
                    )}
                    {cfdiDetail.vendor_id && (
                      <div>
                        <Label className="text-xs text-[#0369A1]">PROVEEDOR</Label>
                        <div className="font-medium text-orange-600">🏢 {getVendorName(cfdiDetail.vendor_id)}</div>
                      </div>
                    )}
                  </div>
                </div>
              )}

              {/* Notes */}
              <div className="space-y-2">
                <Label className="text-sm font-semibold text-[#64748B]">NOTAS DE LA FACTURA</Label>
                <Textarea
                  value={cfdiNotes}
                  onChange={(e) => setCfdiNotes(e.target.value)}
                  placeholder="Agregar notas sobre esta factura..."
                  className="min-h-[80px]"
                />
                <div className="flex justify-end">
                  <Button size="sm" variant="outline" onClick={handleSaveNotes}>
                    Guardar Notas
                  </Button>
                </div>
              </div>
            </div>
          )}
          
          <DialogFooter>
            <Button variant="outline" onClick={() => setDetailDialogOpen(false)}>Cerrar</Button>
            <Button onClick={() => {
              setDetailDialogOpen(false);
              handleCategorizeClick(cfdiDetail);
            }}>
              <Tag size={16} className="mr-2" />
              Categorizar
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>

      {/* PDF Invoice Uploader Modal */}
      <PDFInvoiceUploader
        isOpen={pdfInvoiceUploaderOpen}
        onClose={() => setPdfInvoiceUploaderOpen(false)}
        onSuccess={() => {
          loadData();
          setPdfInvoiceUploaderOpen(false);
          toast.success('Factura importada exitosamente');
        }}
        categories={categories}
        bankAccounts={bankAccounts}
      />
    </div>
  );
};

export default CFDIModule;
