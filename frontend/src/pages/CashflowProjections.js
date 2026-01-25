import React, { useState, useEffect } from 'react';
import api from '@/api/axios';
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card';
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from '@/components/ui/select';
import { Button } from '@/components/ui/button';
import { Input } from '@/components/ui/input';
import { Label } from '@/components/ui/label';
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from '@/components/ui/table';
import { Tabs, TabsContent, TabsList, TabsTrigger } from '@/components/ui/tabs';
import { Dialog, DialogContent, DialogFooter, DialogHeader, DialogTitle, DialogTrigger } from '@/components/ui/dialog';
import { Switch } from '@/components/ui/switch';
import { toast } from 'sonner';
import { TrendingUp, TrendingDown, Calendar, Building2, User, FileText, ChevronDown, ChevronRight, Download, Plus, Trash2, Settings } from 'lucide-react';
import { format, addWeeks, startOfWeek, addMonths, startOfMonth } from 'date-fns';
import { es } from 'date-fns/locale';
import { exportProjections } from '@/utils/excelExport';

const DIAS_SEMANA = [
  { value: 0, label: 'Domingo' },
  { value: 1, label: 'Lunes' },
  { value: 2, label: 'Martes' },
  { value: 3, label: 'Miércoles' },
  { value: 4, label: 'Jueves' },
  { value: 5, label: 'Viernes' },
  { value: 6, label: 'Sábado' }
];

const CashflowProjections = () => {
  const [loading, setLoading] = useState(true);
  const [weeklyData, setWeeklyData] = useState([]);
  const [monthlyData, setMonthlyData] = useState([]);
  const [cfdis, setCfdis] = useState([]);
  const [categories, setCategories] = useState([]);
  const [customers, setCustomers] = useState([]);
  const [vendors, setVendors] = useState([]);
  const [viewMode, setViewMode] = useState('weekly');
  const [expandedRows, setExpandedRows] = useState({});
  const [selectedPartyType, setSelectedPartyType] = useState('all');
  const [selectedParty, setSelectedParty] = useState('');
  
  // Company config
  const [companyConfig, setCompanyConfig] = useState({ inicio_semana: 1 });
  const [configDialogOpen, setConfigDialogOpen] = useState(false);
  
  // Currency selector for projections
  const [selectedCurrency, setSelectedCurrency] = useState('MXN');
  const [fxRates, setFxRates] = useState({ MXN: 1, USD: 17.4545, EUR: 20.4852, GBP: 22.00, JPY: 0.13, CHF: 20.00, CAD: 13.00, CNY: 2.40 });
  
  // Custom concepts state
  const [customConcepts, setCustomConcepts] = useState([]);
  const [conceptDialogOpen, setConceptDialogOpen] = useState(false);
  const [saldoInicialBancos, setSaldoInicialBancos] = useState(0);
  const [newConcept, setNewConcept] = useState({
    nombre: '',
    tipo: 'egreso',
    monto: '',
    semana: 1,
    mes: 1,
    recurrente: false
  });

  // Currency list - All available currencies
  const CURRENCIES = [
    { code: 'MXN', name: 'Peso Mexicano', symbol: '$' },
    { code: 'USD', name: 'Dólar USA', symbol: 'US$' },
    { code: 'EUR', name: 'Euro', symbol: '€' },
    { code: 'GBP', name: 'Libra Esterlina', symbol: '£' },
    { code: 'JPY', name: 'Yen Japonés', symbol: '¥' },
    { code: 'CHF', name: 'Franco Suizo', symbol: 'Fr' },
    { code: 'CAD', name: 'Dólar Canadiense', symbol: 'C$' },
    { code: 'CNY', name: 'Yuan Chino', symbol: '¥' },
  ];

  useEffect(() => {
    loadData();
  }, []);

  const loadData = async () => {
    setLoading(true);
    try {
      const [cfdiRes, catRes, custRes, vendRes, bankSummaryRes, conceptsRes, fxRes, paymentsRes] = await Promise.all([
        api.get('/cfdi?limit=500'),
        api.get('/categories'),
        api.get('/customers'),
        api.get('/vendors'),
        api.get('/bank-accounts/summary'),
        api.get('/manual-projections'),
        api.get('/fx-rates/latest'),
        api.get('/payments')
      ]);
      
      setCfdis(cfdiRes.data);
      setCategories(catRes.data);
      setCustomers(custRes.data);
      setVendors(vendRes.data);
      
      // Get initial bank balance
      const totalBancosMXN = bankSummaryRes.data?.total_mxn || 0;
      setSaldoInicialBancos(totalBancosMXN);
      
      // Load FX rates - ensure all currencies have values
      const loadedRates = fxRes.data?.rates || {};
      setFxRates(prev => ({ ...prev, ...loadedRates, MXN: 1 }));
      
      // Load custom concepts from backend
      setCustomConcepts(conceptsRes.data || []);
      
      // Store payments for use in processing
      const payments = paymentsRes.data || [];
      const categoriesLoaded = catRes.data || [];
      
      // Get company config for week start day
      const companyId = localStorage.getItem('company_id');
      if (companyId) {
        try {
          const compRes = await api.get(`/companies/${companyId}`);
          const weekStart = compRes.data?.inicio_semana ?? 1;
          setCompanyConfig({ ...compRes.data, inicio_semana: weekStart });
          processWeeklyData(cfdiRes.data, categoriesLoaded, weekStart, loadedRates, payments);
        } catch {
          processWeeklyData(cfdiRes.data, categoriesLoaded, 1, loadedRates, payments);
        }
      } else {
        processWeeklyData(cfdiRes.data, categoriesLoaded, 1, loadedRates, payments);
      }
      
      processMonthlyData(cfdiRes.data, catRes.data);
    } catch (error) {
      toast.error('Error cargando datos');
    } finally {
      setLoading(false);
    }
  };

  const handleSaveWeekStart = async (newWeekStart) => {
    try {
      const companyId = localStorage.getItem('company_id');
      if (!companyId) {
        toast.error('No se encontró la empresa activa');
        return;
      }
      await api.put(`/companies/${companyId}`, { inicio_semana: newWeekStart });
      setCompanyConfig(prev => ({ ...prev, inicio_semana: newWeekStart }));
      // Reload data to reprocess with new week start
      loadData();
      setConfigDialogOpen(false);
      toast.success(`Inicio de semana cambiado a ${DIAS_SEMANA.find(d => d.value === newWeekStart)?.label}`);
    } catch (error) {
      toast.error('Error al guardar configuración');
    }
  };

  // Helper function to convert amount to MXN
  const convertToMXN = (amount, currency, rates = {}) => {
    if (!amount) return 0;
    if (currency === 'MXN' || !currency) return amount;
    // Try rates passed in, then fxRates state, then default
    const rate = rates[currency] || fxRates[currency] || 17.4545;
    return amount * rate;
  };

  const processWeeklyData = (cfdisData, categoriesData, weekStartDay = 1, rates = {}, payments = []) => {
    // =====================================================================
    // NUEVA LÓGICA: ÚNICA FUENTE DE VERDAD
    // - Semanas pasadas/actuales: SOLO datos de Cobranza y Pagos
    // - Semanas futuras: CFDIs pendientes (proyecciones)
    // - TOTAL INGRESOS = Suma exacta de sublíneas por categoría
    // =====================================================================
    
    const effectiveRates = { MXN: 1, USD: 17.599, EUR: 20.4852, ...fxRates, ...rates };
    
    const getMonday = (date) => {
      const d = new Date(date);
      const day = d.getDay();
      const diff = d.getDate() - day + (day === 0 ? -6 : 1);
      return new Date(d.setDate(diff));
    };
    
    const today = new Date();
    const currentMonday = getMonday(today);
    
    // Find earliest payment date for starting point
    let earliestDate = null;
    payments.filter(p => p.estatus === 'completado').forEach(p => {
      const fecha = p.fecha_pago;
      if (fecha) {
        const d = new Date(fecha);
        if (!earliestDate || d < earliestDate) earliestDate = d;
      }
    });
    
    const fourWeeksAgo = addWeeks(currentMonday, -4);
    const startMonday = earliestDate ? getMonday(earliestDate < fourWeeksAgo ? fourWeeksAgo : earliestDate) : fourWeeksAgo;
    
    // Generate 13 weeks
    const weeks = [];
    for (let i = 0; i < 13; i++) {
      const weekStart = addWeeks(startMonday, i);
      const weekEnd = addWeeks(weekStart, 1);
      const isPast = weekEnd <= today;
      const isCurrent = weekStart <= today && today < weekEnd;
      
      weeks.push({
        weekNum: i + 1,
        weekStart,
        weekEnd,
        label: `S${i + 1}`,
        dateLabel: format(weekStart, 'dd MMM', { locale: es }),
        isPast,
        isCurrent,
        // INGRESOS structure by category/subcategory
        ingresos: { total: 0, byCategory: {} },
        // EGRESOS structure by category/subcategory
        egresos: { total: 0, byCategory: {} },
        // USD operations tracked separately
        compraUSD: 0,
        ventaUSD: 0,
        // Source flags
        hasRealData: false
      });
    }
    
    // Build category/subcategory lookup maps
    const categoryMap = {};
    const subcategoryMap = {};
    categoriesData.forEach(cat => {
      categoryMap[cat.id] = cat;
      cat.subcategorias?.forEach(sub => {
        subcategoryMap[sub.id] = { ...sub, categoryName: cat.nombre, categoryId: cat.id };
      });
    });
    
    // Find USD operation categories
    const compraUSDCategory = categoriesData.find(c => c.nombre?.toLowerCase().includes('compra de usd') || c.nombre?.toLowerCase().includes('compra usd'));
    const ventaUSDCategory = categoriesData.find(c => c.nombre?.toLowerCase().includes('venta de usd') || c.nombre?.toLowerCase().includes('venta usd'));
    const compraUSDId = compraUSDCategory?.id;
    const ventaUSDId = ventaUSDCategory?.id;
    
    // Track processed bank transactions to avoid duplicates
    const processedBankTxns = new Set();
    
    // =====================================================================
    // PASO 1: Procesar Cobranza y Pagos (DATOS REALES para semanas pasadas)
    // =====================================================================
    payments.forEach(payment => {
      if (payment.estatus !== 'completado') return;
      if (!payment.fecha_pago) return;
      
      // Deduplicate by bank_transaction_id
      const bankTxnId = payment.bank_transaction_id;
      if (bankTxnId) {
        if (processedBankTxns.has(bankTxnId)) return;
        processedBankTxns.add(bankTxnId);
      }
      
      const paymentDate = new Date(payment.fecha_pago);
      if (isNaN(paymentDate.getTime())) return;
      
      const weekIdx = weeks.findIndex(w => paymentDate >= w.weekStart && paymentDate < w.weekEnd);
      if (weekIdx === -1) return;
      
      const week = weeks[weekIdx];
      if (!week.isPast && !week.isCurrent) return; // Only process real data for past/current weeks
      
      week.hasRealData = true;
      
      const montoMXN = convertToMXN(payment.monto, payment.moneda, effectiveRates);
      
      // Get category and subcategory names from payment's inherited data
      const category = categoryMap[payment.category_id];
      const categoryName = category?.nombre || 'Sin categoría';
      const subcategoryInfo = subcategoryMap[payment.subcategory_id];
      const subcategoryName = subcategoryInfo?.nombre || null;
      
      // Check if USD operation
      const isCompraUSD = payment.category_id === compraUSDId;
      const isVentaUSD = payment.category_id === ventaUSDId;
      
      if (isCompraUSD) {
        week.compraUSD += montoMXN;
        return; // Don't add to regular ingresos/egresos
      }
      if (isVentaUSD) {
        week.ventaUSD += montoMXN;
        return; // Don't add to regular ingresos/egresos
      }
      
      // Determine section (ingresos or egresos)
      const section = payment.tipo === 'cobro' ? week.ingresos : week.egresos;
      
      // Add to category total
      if (!section.byCategory[categoryName]) {
        section.byCategory[categoryName] = { total: 0, bySubcategory: {}, items: [] };
      }
      section.byCategory[categoryName].total += montoMXN;
      section.byCategory[categoryName].items.push({
        id: payment.id,
        monto: montoMXN,
        concepto: payment.concepto,
        beneficiario: payment.beneficiario,
        uuid: payment.cfdi_uuid,
        source: 'payment'
      });
      
      // Add to subcategory
      const subKey = subcategoryName || 'General';
      if (!section.byCategory[categoryName].bySubcategory[subKey]) {
        section.byCategory[categoryName].bySubcategory[subKey] = { total: 0, items: [] };
      }
      section.byCategory[categoryName].bySubcategory[subKey].total += montoMXN;
      section.byCategory[categoryName].bySubcategory[subKey].items.push({
        id: payment.id,
        monto: montoMXN,
        source: 'payment'
      });
      
      // Add to section total
      section.total += montoMXN;
    });
    
    // =====================================================================
    // PASO 2: Procesar CFDIs (PROYECCIONES para semanas futuras)
    // =====================================================================
    cfdisData.forEach(cfdi => {
      // For projections, use fecha_vencimiento or estimated date
      let projectedDate;
      if (cfdi.fecha_vencimiento) {
        projectedDate = new Date(cfdi.fecha_vencimiento);
      } else {
        // Default: 30 days after emission
        projectedDate = new Date(cfdi.fecha_emision);
        projectedDate.setDate(projectedDate.getDate() + 30);
      }
      
      const weekIdx = weeks.findIndex(w => projectedDate >= w.weekStart && projectedDate < w.weekEnd);
      if (weekIdx === -1) return;
      
      const week = weeks[weekIdx];
      
      // Only add CFDIs to FUTURE weeks (projections)
      // For past weeks, we already have real payment data
      if (week.isPast || week.isCurrent) return;
      
      // Calculate pending amount
      const total = cfdi.total || 0;
      const pagado = cfdi.monto_pagado || 0;
      const cobrado = cfdi.monto_cobrado || 0;
      
      let pendiente = 0;
      if (cfdi.tipo_cfdi === 'ingreso') {
        pendiente = total - cobrado;
      } else {
        pendiente = total - pagado;
      }
      
      if (pendiente <= 0) return; // Already fully paid/collected
      
      const montoMXN = convertToMXN(pendiente, cfdi.moneda, effectiveRates);
      
      const category = categoryMap[cfdi.category_id];
      const categoryName = category?.nombre || 'Sin categoría';
      const subcategoryInfo = subcategoryMap[cfdi.subcategory_id];
      const subcategoryName = subcategoryInfo?.nombre || null;
      
      // Check if USD operation
      const isCompraUSD = cfdi.category_id === compraUSDId;
      const isVentaUSD = cfdi.category_id === ventaUSDId;
      
      if (isCompraUSD) {
        week.compraUSD += montoMXN;
        return;
      }
      if (isVentaUSD) {
        week.ventaUSD += montoMXN;
        return;
      }
      
      // Determine section
      const section = cfdi.tipo_cfdi === 'ingreso' ? week.ingresos : week.egresos;
      
      // Add to category
      if (!section.byCategory[categoryName]) {
        section.byCategory[categoryName] = { total: 0, bySubcategory: {}, items: [] };
      }
      section.byCategory[categoryName].total += montoMXN;
      section.byCategory[categoryName].items.push({
        id: cfdi.id,
        monto: montoMXN,
        uuid: cfdi.uuid,
        emisor: cfdi.emisor_nombre,
        receptor: cfdi.receptor_nombre,
        source: 'cfdi'
      });
      
      // Add to subcategory
      const subKey = subcategoryName || 'General';
      if (!section.byCategory[categoryName].bySubcategory[subKey]) {
        section.byCategory[categoryName].bySubcategory[subKey] = { total: 0, items: [] };
      }
      section.byCategory[categoryName].bySubcategory[subKey].total += montoMXN;
      
      // Add to section total
      section.total += montoMXN;
    });
    
    // Log for debugging
    console.log('=== DATOS POR SEMANA (Única Fuente de Verdad) ===');
    weeks.forEach(w => {
      const status = w.isPast ? 'REAL' : (w.isCurrent ? 'ACTUAL' : 'PROY');
      console.log(`${w.label} (${status}): Ingresos=${w.ingresos.total.toFixed(2)}, Egresos=${w.egresos.total.toFixed(2)}, VentaUSD=${w.ventaUSD.toFixed(2)}`);
    });
    
    return weeks;
  };

  const processMonthlyData = (cfdisData, categoriesData) => {
    // Generate 6 months
    const months = [];
    const today = new Date();
    const startDate = startOfMonth(today);
    
    for (let i = 0; i < 6; i++) {
      const monthStart = addMonths(startDate, i);
      const monthEnd = addMonths(monthStart, 1);
      
      months.push({
        monthNum: i + 1,
        monthStart,
        monthEnd,
        label: format(monthStart, 'MMM yyyy', { locale: es }),
        ingresos: { total: 0, byCategory: {}, byParty: {} },
        egresos: { total: 0, byCategory: {}, byParty: {} }
      });
    }
    
    // Classify CFDIs by month
    cfdisData.forEach(cfdi => {
      const cfdiDate = new Date(cfdi.fecha_emision);
      const monthIdx = months.findIndex(m => cfdiDate >= m.monthStart && cfdiDate < m.monthEnd);
      
      if (monthIdx !== -1) {
        const month = months[monthIdx];
        const isIngreso = cfdi.tipo_cfdi === 'ingreso';
        const section = isIngreso ? month.ingresos : month.egresos;
        
        // Get category name
        const category = categoriesData.find(c => c.id === cfdi.category_id);
        const categoryName = category?.nombre || 'Sin categoría';
        
        // Get party name
        const partyName = isIngreso ? cfdi.receptor_nombre : cfdi.emisor_nombre;
        
        section.total += cfdi.total;
        
        // By category
        if (!section.byCategory[categoryName]) {
          section.byCategory[categoryName] = 0;
        }
        section.byCategory[categoryName] += cfdi.total;
        
        // By party
        if (!section.byParty[partyName]) {
          section.byParty[partyName] = { total: 0, cfdis: [] };
        }
        section.byParty[partyName].total += cfdi.total;
        section.byParty[partyName].cfdis.push(cfdi);
      }
    });
    
    setMonthlyData(months);
  };

  const toggleRow = (key) => {
    setExpandedRows(prev => ({ ...prev, [key]: !prev[key] }));
  };

  const formatCurrency = (amount) => {
    const converted = convertToCurrency(amount || 0);
    const currencyInfo = CURRENCIES.find(c => c.code === selectedCurrency);
    const symbol = currencyInfo?.symbol || '$';
    return `${symbol}${converted.toLocaleString('es-MX', { minimumFractionDigits: 2, maximumFractionDigits: 2 })}`;
  };

  // Add custom concept - saves to backend
  const handleAddConcept = async () => {
    if (!newConcept.nombre || !newConcept.monto) {
      toast.error('Completa nombre y monto');
      return;
    }
    
    try {
      const conceptData = {
        nombre: newConcept.nombre,
        tipo: newConcept.tipo,
        monto: parseFloat(newConcept.monto),
        semana: viewMode === 'weekly' ? parseInt(newConcept.semana) : null,
        mes: viewMode === 'monthly' ? parseInt(newConcept.mes) : null,
        recurrente: newConcept.recurrente
      };
      
      const response = await api.post('/manual-projections', conceptData);
      setCustomConcepts([...customConcepts, response.data]);
      setNewConcept({ nombre: '', tipo: 'egreso', monto: '', semana: 1, mes: 1, recurrente: false });
      setConceptDialogOpen(false);
      toast.success('Concepto agregado');
    } catch (error) {
      toast.error('Error al guardar concepto');
    }
  };

  const handleDeleteConcept = async (id) => {
    try {
      await api.delete(`/manual-projections/${id}`);
      setCustomConcepts(customConcepts.filter(c => c.id !== id));
      toast.success('Concepto eliminado');
    } catch (error) {
      toast.error('Error al eliminar concepto');
    }
  };

  // Export projections to Excel using XLSX
  const exportProjectionsToExcel = () => {
    const totals = calculateRunningTotals();
    
    if (weeklyData.length === 0) {
      toast.error('No hay datos para exportar');
      return;
    }
    
    try {
      // Use the utility function from excelExport
      const success = exportProjections(totals, saldoInicialBancos, selectedCurrency, fxRates[selectedCurrency] || 1);
      if (success) {
        toast.success(`Proyección exportada a Excel en ${selectedCurrency}`);
      } else {
        toast.error('Error al exportar');
      }
    } catch (error) {
      console.error('Export error:', error);
      toast.error('Error al exportar: ' + (error.message || 'Error desconocido'));
    }
  };

  // Convert amount from MXN to selected currency
  const convertToCurrency = (amountMXN) => {
    if (selectedCurrency === 'MXN') return amountMXN;
    const rate = fxRates[selectedCurrency] || 1;
    return amountMXN / rate; // Divide to convert FROM MXN TO target currency
  };

  // Get CFDIs for selected party
  const getPartyCfdis = () => {
    if (!selectedParty) return [];
    
    return cfdis.filter(cfdi => {
      if (selectedPartyType === 'customer') {
        const customer = customers.find(c => c.id === selectedParty);
        return customer && (cfdi.customer_id === selectedParty || cfdi.receptor_rfc === customer.rfc);
      } else if (selectedPartyType === 'vendor') {
        const vendor = vendors.find(v => v.id === selectedParty);
        return vendor && (cfdi.vendor_id === selectedParty || cfdi.emisor_rfc === vendor.rfc);
      }
      return false;
    });
  };

  // Calculate running totals including custom concepts
  // NUEVA LÓGICA SIMPLIFICADA:
  // - Usa directamente ingresos.total y egresos.total de processWeeklyData
  // - TOTAL = Suma exacta de categorías (ya calculado correctamente)
  const calculateRunningTotals = () => {
    let saldoInicial = saldoInicialBancos;
    const totals = [];
    
    weeklyData.forEach((week, idx) => {
      // Add custom concepts for this week
      const customIngresos = customConcepts
        .filter(c => c.tipo === 'ingreso' && (c.semana === idx + 1 || c.recurrente))
        .reduce((sum, c) => sum + c.monto, 0);
      const customEgresos = customConcepts
        .filter(c => c.tipo === 'egreso' && (c.semana === idx + 1 || c.recurrente))
        .reduce((sum, c) => sum + c.monto, 0);
      
      // Get USD operations for this week
      const compraUSD = week.compraUSD || 0;
      const ventaUSD = week.ventaUSD || 0;
      
      // TOTALES DIRECTOS: ya vienen calculados como suma de categorías
      const totalIngresos = (week.ingresos.total || 0) + customIngresos;
      const totalEgresos = (week.egresos.total || 0) + customEgresos;
      
      // Net cash flow from operations (excluding USD conversions)
      const flujoNetoOperativo = totalIngresos - totalEgresos;
      const flujoDivisas = ventaUSD - compraUSD;
      const flujoNeto = flujoNetoOperativo + flujoDivisas;
      const saldoFinal = saldoInicial + flujoNeto;
      
      totals.push({
        ...week,
        ingresos: { 
          ...week.ingresos, 
          total: totalIngresos,
          custom: customIngresos
        },
        egresos: { 
          ...week.egresos, 
          total: totalEgresos,
          custom: customEgresos
        },
        compraUSD,
        ventaUSD,
        flujoDivisas,
        saldoInicial,
        flujoNeto,
        saldoFinal
      });
      
      saldoInicial = saldoFinal;
    });
    
    return totals;
  };
      let isRealData = false;
      let cobrosRealesSinCFDI = 0;
      let pagosRealesSinCFDI = 0;
      
      if (week.isPast || week.isCurrent) {
        // For past weeks, use REAL data as the main source
        // But identify what's "extra" (cobros sin CFDI asociado)
        if (ingresosReales > 0 || egresosReales > 0 || compraUSD > 0 || ventaUSD > 0) {
          isRealData = true;
          // Calculate difference between real and CFDI
          cobrosRealesSinCFDI = Math.max(0, ingresosReales - ingresosCFDI);
          pagosRealesSinCFDI = Math.max(0, egresosReales - egresosCFDI);
          
          // INGRESOS = MAX of (real, cfdi projections) to ensure we don't double count
          // If real > cfdi: use real (which includes additional deposits)
          // If cfdi > real: use cfdi (which includes pending invoices)
          totalIngresos = Math.max(ingresosReales, ingresosCFDI) + customIngresos;
          totalEgresos = Math.max(egresosReales, egresosCFDI) + customEgresos;
        } else {
          // No real data, fall back to CFDI
          totalIngresos = ingresosCFDI + customIngresos;
          totalEgresos = egresosCFDI + customEgresos;
        }
      } else {
        // Future weeks: use CFDI projections
        totalIngresos = ingresosCFDI + customIngresos;
        totalEgresos = egresosCFDI + customEgresos;
      }
      
      // Net cash flow from operations (excluding USD conversions)
      const flujoNetoOperativo = totalIngresos - totalEgresos;
      const flujoDivisas = ventaUSD - compraUSD;
      const flujoNeto = flujoNetoOperativo + flujoDivisas;
      const saldoFinal = saldoInicial + flujoNeto;
      
      totals.push({
        ...week,
        ingresos: { 
          ...week.ingresos, 
          total: totalIngresos, 
          cfdi: ingresosCFDI,
          real: ingresosReales,
          custom: customIngresos,
          cobrosRealesSinCFDI,
          isReal: isRealData 
        },
        egresos: { 
          ...week.egresos, 
          total: totalEgresos, 
          cfdi: egresosCFDI,
          real: egresosReales,
          custom: customEgresos,
          pagosRealesSinCFDI,
          isReal: isRealData 
        },
        compraUSD,
        ventaUSD,
        flujoDivisas,
        saldoInicial,
        flujoNeto,
        saldoFinal,
        isRealData
      });
      
      saldoInicial = saldoFinal;
    });
    
    return totals;
  };

  if (loading) return <div className="p-8">Cargando proyecciones...</div>;

  const weeklyTotals = calculateRunningTotals();
  const customConceptsIngresos = customConcepts.filter(c => c.tipo === 'ingreso');
  const customConceptsEgresos = customConcepts.filter(c => c.tipo === 'egreso');
  const grandTotalIngresos = weeklyTotals.reduce((sum, w) => sum + w.ingresos.total, 0);
  const grandTotalEgresos = weeklyTotals.reduce((sum, w) => sum + w.egresos.total, 0);
  const grandTotalCompraUSD = weeklyTotals.reduce((sum, w) => sum + (w.compraUSD || 0), 0);
  const grandTotalVentaUSD = weeklyTotals.reduce((sum, w) => sum + (w.ventaUSD || 0), 0);
  const grandTotalFlujoDivisas = grandTotalVentaUSD - grandTotalCompraUSD;
  const grandTotalFlujo = grandTotalIngresos - grandTotalEgresos + grandTotalFlujoDivisas;

  return (
    <div className="p-6 space-y-6 bg-[#F8FAFC] min-h-screen" data-testid="cashflow-projections-page">
      {/* Header */}
      <div className="flex justify-between items-center">
        <div>
          <h1 className="text-3xl font-bold text-[#0F172A]" style={{fontFamily: 'Manrope'}}>
            Proyección de Flujo de Efectivo
          </h1>
          <p className="text-[#64748B]">
            Modelo de 13 semanas | Inicio: {DIAS_SEMANA.find(d => d.value === companyConfig.inicio_semana)?.label || 'Lunes'}
            {selectedCurrency !== 'MXN' && (
              <span className="ml-2 px-2 py-0.5 bg-blue-100 text-blue-700 rounded text-sm">
                TC: 1 {selectedCurrency} = ${fxRates[selectedCurrency]?.toFixed(4) || '?'} MXN
              </span>
            )}
          </p>
        </div>
        <div className="flex gap-2">
          {/* Config Dialog for Week Start */}
          <Dialog open={configDialogOpen} onOpenChange={setConfigDialogOpen}>
            <DialogTrigger asChild>
              <Button variant="outline" className="gap-2" data-testid="config-week-start-btn">
                <Settings size={16} />
                Configurar
              </Button>
            </DialogTrigger>
            <DialogContent>
              <DialogHeader>
                <DialogTitle>Configuración de Proyecciones</DialogTitle>
              </DialogHeader>
              <div className="space-y-4">
                <div className="space-y-2">
                  <Label>Inicio de Semana para esta Empresa</Label>
                  <Select 
                    value={companyConfig.inicio_semana?.toString()} 
                    onValueChange={(v) => handleSaveWeekStart(parseInt(v))}
                  >
                    <SelectTrigger data-testid="week-start-select">
                      <SelectValue placeholder="Selecciona un día" />
                    </SelectTrigger>
                    <SelectContent>
                      {DIAS_SEMANA.map(dia => (
                        <SelectItem key={dia.value} value={dia.value.toString()}>
                          {dia.label}
                        </SelectItem>
                      ))}
                    </SelectContent>
                  </Select>
                  <p className="text-sm text-gray-500">
                    Este ajuste afecta cómo se agrupan las semanas en las proyecciones de flujo de efectivo.
                  </p>
                </div>
              </div>
            </DialogContent>
          </Dialog>
          
          {/* Currency Selector */}
          <Select value={selectedCurrency} onValueChange={setSelectedCurrency}>
            <SelectTrigger className="w-32" data-testid="currency-select">
              <SelectValue />
            </SelectTrigger>
            <SelectContent>
              {CURRENCIES.map(c => (
                <SelectItem key={c.code} value={c.code}>
                  {c.symbol} {c.code}
                </SelectItem>
              ))}
            </SelectContent>
          </Select>
          
          <Button 
            variant="outline" 
            className="gap-2"
            onClick={exportProjectionsToExcel}
            data-testid="export-projections-btn"
          >
            <Download size={16} />
            Exportar Excel
          </Button>
          
          <Dialog open={conceptDialogOpen} onOpenChange={setConceptDialogOpen}>
            <DialogTrigger asChild>
              <Button className="gap-2 bg-[#0F172A]" data-testid="add-concept-btn">
                <Plus size={16} />
                Agregar Concepto
              </Button>
            </DialogTrigger>
            <DialogContent>
              <DialogHeader>
                <DialogTitle>Agregar Concepto Manual</DialogTitle>
              </DialogHeader>
              <div className="space-y-4">
                <div className="space-y-2">
                  <Label>Nombre del concepto</Label>
                  <Input 
                    value={newConcept.nombre}
                    onChange={(e) => setNewConcept({...newConcept, nombre: e.target.value})}
                    placeholder="Ej: Nómina, Renta, Venta proyectada..."
                  />
                </div>
                <div className="grid grid-cols-2 gap-4">
                  <div className="space-y-2">
                    <Label>Tipo</Label>
                    <Select value={newConcept.tipo} onValueChange={(v) => setNewConcept({...newConcept, tipo: v})}>
                      <SelectTrigger>
                        <SelectValue />
                      </SelectTrigger>
                      <SelectContent>
                        <SelectItem value="ingreso">
                          <span className="flex items-center gap-2"><TrendingUp size={14} className="text-green-500" /> Ingreso</span>
                        </SelectItem>
                        <SelectItem value="egreso">
                          <span className="flex items-center gap-2"><TrendingDown size={14} className="text-red-500" /> Egreso</span>
                        </SelectItem>
                      </SelectContent>
                    </Select>
                  </div>
                  <div className="space-y-2">
                    <Label>Monto</Label>
                    <Input 
                      type="number"
                      step="0.01"
                      value={newConcept.monto}
                      onChange={(e) => setNewConcept({...newConcept, monto: e.target.value})}
                      placeholder="0.00"
                    />
                  </div>
                </div>
                <div className="grid grid-cols-2 gap-4">
                  <div className="space-y-2">
                    <Label>Semana</Label>
                    <Select value={String(newConcept.semana)} onValueChange={(v) => setNewConcept({...newConcept, semana: parseInt(v)})}>
                      <SelectTrigger>
                        <SelectValue />
                      </SelectTrigger>
                      <SelectContent>
                        {[1,2,3,4,5,6,7,8,9,10,11,12,13].map(s => (
                          <SelectItem key={s} value={String(s)}>Semana {s}</SelectItem>
                        ))}
                      </SelectContent>
                    </Select>
                  </div>
                  <div className="space-y-2 flex items-end">
                    <label className="flex items-center gap-2 cursor-pointer">
                      <input 
                        type="checkbox" 
                        checked={newConcept.recurrente}
                        onChange={(e) => setNewConcept({...newConcept, recurrente: e.target.checked})}
                        className="w-4 h-4"
                      />
                      <span className="text-sm">Recurrente (todas las semanas)</span>
                    </label>
                  </div>
                </div>
              </div>
              <DialogFooter>
                <Button variant="outline" onClick={() => setConceptDialogOpen(false)}>Cancelar</Button>
                <Button onClick={handleAddConcept}>Agregar</Button>
              </DialogFooter>
            </DialogContent>
          </Dialog>
        </div>
      </div>

      {/* Custom Concepts Summary */}
      {customConcepts.length > 0 && (
        <Card className="border-blue-200 bg-blue-50">
          <CardHeader className="pb-2">
            <CardTitle className="text-sm text-blue-800">Conceptos Manuales Agregados ({customConcepts.length})</CardTitle>
          </CardHeader>
          <CardContent>
            <div className="flex flex-wrap gap-2">
              {customConcepts.map(c => (
                <div key={c.id} className={`flex items-center gap-2 px-3 py-1 rounded-full text-sm ${c.tipo === 'ingreso' ? 'bg-green-100 text-green-800' : 'bg-red-100 text-red-800'}`}>
                  {c.tipo === 'ingreso' ? <TrendingUp size={12} /> : <TrendingDown size={12} />}
                  {c.nombre}: {formatCurrency(c.monto)}
                  {c.recurrente && <span className="text-xs">(Rec.)</span>}
                  <button onClick={() => handleDeleteConcept(c.id)} className="ml-1 hover:text-red-600">
                    <Trash2 size={12} />
                  </button>
                </div>
              ))}
            </div>
          </CardContent>
        </Card>
      )}

      {/* View Mode Tabs */}
      <Tabs value={viewMode} onValueChange={setViewMode}>
        <TabsList>
          <TabsTrigger value="weekly" className="gap-2">
            <Calendar size={16} />
            Vista Semanal (13 semanas)
          </TabsTrigger>
          <TabsTrigger value="monthly" className="gap-2">
            <Calendar size={16} />
            Vista Mensual
          </TabsTrigger>
          <TabsTrigger value="byParty" className="gap-2">
            <Building2 size={16} />
            Por Cliente/Proveedor
          </TabsTrigger>
        </TabsList>

        {/* WEEKLY VIEW */}
        <TabsContent value="weekly" className="mt-4">
          <Card>
            <CardHeader className="bg-[#0F172A] text-white rounded-t-lg">
              <CardTitle className="flex items-center justify-between">
                <span>Modelo de Flujo de Efectivo - 13 Semanas</span>
                <span className="text-sm font-normal">
                  {format(new Date(), 'MMMM yyyy', { locale: es })}
                </span>
              </CardTitle>
            </CardHeader>
            <CardContent className="p-0">
              <div className="overflow-x-auto">
                <Table>
                  <TableHeader>
                    <TableRow className="bg-gray-100">
                      <TableHead className="sticky left-0 bg-gray-100 min-w-[200px] font-bold">CONCEPTO</TableHead>
                      {weeklyTotals.map((week, idx) => (
                        <TableHead key={idx} className={`text-center min-w-[100px] ${week.isRealData ? 'bg-yellow-50' : ''}`}>
                          <div className="font-bold">{week.label}</div>
                          <div className="text-xs text-gray-500">{week.dateLabel}</div>
                          {week.isRealData && (
                            <div className="text-xs text-yellow-600 font-semibold">Real</div>
                          )}
                        </TableHead>
                      ))}
                      <TableHead className="text-center min-w-[120px] bg-blue-50 font-bold">TOTAL</TableHead>
                    </TableRow>
                  </TableHeader>
                  <TableBody>
                    {/* SALDO INICIAL DE BANCOS Row */}
                    <TableRow className="bg-blue-100 font-bold border-b-2 border-blue-300">
                      <TableCell className="sticky left-0 bg-blue-100">
                        <div className="flex items-center gap-2">
                          <Building2 className="text-blue-600" size={16} />
                          SALDO INICIAL BANCOS
                        </div>
                      </TableCell>
                      {weeklyTotals.map((week, idx) => (
                        <TableCell key={idx} className="text-center text-blue-700 font-bold">
                          {formatCurrency(week.saldoInicial)}
                        </TableCell>
                      ))}
                      <TableCell className="text-center bg-blue-200 text-blue-800 font-bold">
                        {formatCurrency(saldoInicialBancos)}
                      </TableCell>
                    </TableRow>

                    {/* RECEIPTS / INGRESOS Section */}
                    <TableRow className="bg-green-50 font-bold">
                      <TableCell className="sticky left-0 bg-green-50">
                        <div className="flex items-center gap-2">
                          <TrendingUp className="text-green-600" size={16} />
                          INGRESOS
                          {weeklyTotals.some(w => w.isRealData) && (
                            <span className="text-xs px-2 py-0.5 bg-green-200 text-green-800 rounded">Incluye Datos Reales</span>
                          )}
                        </div>
                      </TableCell>
                      {weeklyTotals.map((week, idx) => (
                        <TableCell key={idx} className={`text-center font-bold ${week.isRealData ? 'text-green-800 bg-green-100' : 'text-green-700'}`}>
                          {formatCurrency(week.ingresos.total)}
                        </TableCell>
                      ))}
                      <TableCell className="text-center bg-green-100 text-green-800 font-bold">
                        {formatCurrency(grandTotalIngresos)}
                      </TableCell>
                    </TableRow>
                    
                    {/* Ingresos by Category - Show "Cobranza" or category name, also show "Sin categoría" */}
                    {/* Exclude "Compra de USD" category as it's shown separately */}
                    {(() => {
                      // Collect all unique category names from ingresos including "Sin categoría"
                      const allIngresoCategories = new Set();
                      weeklyData.forEach(w => {
                        Object.keys(w.ingresos.byCategory).forEach(cat => {
                          // Exclude USD operations from INGRESOS section
                          if (!cat.toLowerCase().includes('compra de usd') && !cat.toLowerCase().includes('compra usd')) {
                            allIngresoCategories.add(cat);
                          }
                        });
                      });
                      
                      return Array.from(allIngresoCategories).map(categoryName => {
                        const categoryKey = `ing-${categoryName}`;
                        const isExpanded = expandedRows[categoryKey];
                        const weekTotals = weeklyData.map(w => w.ingresos.byCategory[categoryName]?.total || 0);
                        const categoryTotal = weekTotals.reduce((sum, t) => sum + t, 0);
                        
                        if (categoryTotal === 0) return null;
                        
                        return (
                          <React.Fragment key={categoryKey}>
                            <TableRow className="hover:bg-green-50/50">
                              <TableCell className="sticky left-0 bg-white pl-8">
                                <button 
                                  onClick={() => toggleRow(categoryKey)}
                                  className="flex items-center gap-1 text-gray-700 hover:text-green-600"
                                >
                                  {isExpanded ? <ChevronDown size={14} /> : <ChevronRight size={14} />}
                                  {categoryName === 'Sin categoría' ? 'Cobranza' : categoryName}
                                </button>
                              </TableCell>
                              {weekTotals.map((total, idx) => (
                                <TableCell key={idx} className="text-center text-green-600">
                                  {total > 0 ? formatCurrency(total) : '-'}
                                </TableCell>
                              ))}
                              <TableCell className="text-center bg-green-50 text-green-700">
                                {formatCurrency(categoryTotal)}
                              </TableCell>
                            </TableRow>
                            {/* Subcategorías expandibles */}
                            {isExpanded && (() => {
                              const allSubcategories = new Set();
                              weeklyData.forEach(w => {
                                const cat = w.ingresos.byCategory[categoryName];
                                if (cat?.bySubcategory) {
                                  Object.keys(cat.bySubcategory).forEach(sub => allSubcategories.add(sub));
                                }
                              });
                              
                              return Array.from(allSubcategories).map(subName => {
                                const subTotals = weeklyData.map(w => 
                                  w.ingresos.byCategory[categoryName]?.bySubcategory?.[subName]?.total || 0
                                );
                                const subTotal = subTotals.reduce((s, t) => s + t, 0);
                                if (subTotal === 0) return null;
                                
                                return (
                                  <TableRow key={`${categoryKey}-${subName}`} className="bg-green-50/30">
                                    <TableCell className="sticky left-0 bg-green-50/30 pl-14 text-sm text-gray-600">
                                      └ {subName}
                                    </TableCell>
                                    {subTotals.map((total, idx) => (
                                      <TableCell key={idx} className="text-center text-green-500 text-sm">
                                        {total > 0 ? formatCurrency(total) : '-'}
                                      </TableCell>
                                    ))}
                                    <TableCell className="text-center bg-green-50 text-green-600 text-sm">
                                      {formatCurrency(subTotal)}
                                    </TableCell>
                                  </TableRow>
                                );
                              });
                            })()}
                          </React.Fragment>
                        );
                      });
                    })()}
                    
                    {/* Depósitos/Otros Cobros - Shows real payments not matching CFDIs */}
                    {weeklyTotals.some(w => w.ingresos.cobrosRealesSinCFDI > 0) && (
                      <TableRow className="hover:bg-green-50/50 bg-yellow-50/30">
                        <TableCell className="sticky left-0 bg-yellow-50/30 pl-8">
                          <div className="flex items-center gap-1 text-amber-700">
                            <span className="text-xs px-1.5 py-0.5 bg-amber-100 rounded">📥</span>
                            Depósitos / Otros Cobros
                            <span className="text-xs text-gray-500 ml-1">(sin CFDI)</span>
                          </div>
                        </TableCell>
                        {weeklyTotals.map((week, idx) => (
                          <TableCell key={idx} className="text-center text-amber-600">
                            {week.ingresos.cobrosRealesSinCFDI > 0 ? formatCurrency(week.ingresos.cobrosRealesSinCFDI) : '-'}
                          </TableCell>
                        ))}
                        <TableCell className="text-center bg-amber-50 text-amber-700">
                          {formatCurrency(weeklyTotals.reduce((sum, w) => sum + (w.ingresos.cobrosRealesSinCFDI || 0), 0))}
                        </TableCell>
                      </TableRow>
                    )}

                    {/* OPERATING DISBURSEMENTS / EGRESOS Section */}
                    <TableRow className="bg-red-50 font-bold">
                      <TableCell className="sticky left-0 bg-red-50">
                        <div className="flex items-center gap-2">
                          <TrendingDown className="text-red-600" size={16} />
                          EGRESOS
                          {weeklyTotals.some(w => w.isRealData) && (
                            <span className="text-xs px-2 py-0.5 bg-red-200 text-red-800 rounded">Incluye Datos Reales</span>
                          )}
                        </div>
                      </TableCell>
                      {weeklyTotals.map((week, idx) => (
                        <TableCell key={idx} className={`text-center font-bold ${week.isRealData ? 'text-red-800 bg-red-100' : 'text-red-700'}`}>
                          {formatCurrency(week.egresos.total)}
                        </TableCell>
                      ))}
                      <TableCell className="text-center bg-red-100 text-red-800 font-bold">
                        {formatCurrency(grandTotalEgresos)}
                      </TableCell>
                    </TableRow>
                    
                    {/* Egresos by Category - Show all including "Sin categoría" as "Proveedores Costo" */}
                    {/* Exclude "Venta de USD" category as it's shown separately */}
                    {(() => {
                      // Collect all unique category names from egresos including "Sin categoría"
                      const allEgresoCategories = new Set();
                      weeklyData.forEach(w => {
                        Object.keys(w.egresos.byCategory).forEach(cat => {
                          // Exclude USD operations from EGRESOS section
                          if (!cat.toLowerCase().includes('venta de usd') && !cat.toLowerCase().includes('venta usd')) {
                            allEgresoCategories.add(cat);
                          }
                        });
                      });
                      
                      return Array.from(allEgresoCategories).map(categoryName => {
                        const categoryKey = `egr-${categoryName}`;
                        const isExpanded = expandedRows[categoryKey];
                        const weekTotals = weeklyData.map(w => w.egresos.byCategory[categoryName]?.total || 0);
                        const categoryTotal = weekTotals.reduce((sum, t) => sum + t, 0);
                        
                        if (categoryTotal === 0) return null;
                        
                        return (
                          <React.Fragment key={categoryKey}>
                            <TableRow className="hover:bg-red-50/50">
                              <TableCell className="sticky left-0 bg-white pl-8">
                                <button 
                                  onClick={() => toggleRow(categoryKey)}
                                  className="flex items-center gap-1 text-gray-700 hover:text-red-600"
                                >
                                  {isExpanded ? <ChevronDown size={14} /> : <ChevronRight size={14} />}
                                  {categoryName === 'Sin categoría' ? 'Proveedores Costo' : categoryName}
                                </button>
                              </TableCell>
                              {weekTotals.map((total, idx) => (
                                <TableCell key={idx} className="text-center text-red-600">
                                  {total > 0 ? formatCurrency(total) : '-'}
                                </TableCell>
                              ))}
                              <TableCell className="text-center bg-red-50 text-red-700">
                                {formatCurrency(categoryTotal)}
                              </TableCell>
                            </TableRow>
                            {/* Subcategorías expandibles */}
                            {isExpanded && (() => {
                              const allSubcategories = new Set();
                              weeklyData.forEach(w => {
                                const cat = w.egresos.byCategory[categoryName];
                                if (cat?.bySubcategory) {
                                  Object.keys(cat.bySubcategory).forEach(sub => allSubcategories.add(sub));
                                }
                              });
                              
                              return Array.from(allSubcategories).map(subName => {
                                const subTotals = weeklyData.map(w => 
                                  w.egresos.byCategory[categoryName]?.bySubcategory?.[subName]?.total || 0
                                );
                                const subTotal = subTotals.reduce((s, t) => s + t, 0);
                                if (subTotal === 0) return null;
                                
                                return (
                                  <TableRow key={`${categoryKey}-${subName}`} className="bg-red-50/30">
                                    <TableCell className="sticky left-0 bg-red-50/30 pl-14 text-sm text-gray-600">
                                      └ {subName}
                                    </TableCell>
                                    {subTotals.map((total, idx) => (
                                      <TableCell key={idx} className="text-center text-red-500 text-sm">
                                        {total > 0 ? formatCurrency(total) : '-'}
                                      </TableCell>
                                    ))}
                                    <TableCell className="text-center bg-red-50 text-red-600 text-sm">
                                      {formatCurrency(subTotal)}
                                    </TableCell>
                                  </TableRow>
                                );
                              });
                            })()}
                          </React.Fragment>
                        );
                      });
                    })()}

                    {/* COMPRA/VENTA DE DIVISAS Section - Separate from Income/Expenses */}
                    {(grandTotalCompraUSD > 0 || grandTotalVentaUSD > 0) && (
                      <>
                        <TableRow className="bg-purple-50 font-bold border-t-2 border-purple-200">
                          <TableCell className="sticky left-0 bg-purple-50">
                            <div className="flex items-center gap-2">
                              <span className="text-purple-600">💱</span>
                              OPERACIONES CON DIVISAS
                            </div>
                          </TableCell>
                          {weeklyTotals.map((week, idx) => (
                            <TableCell key={idx} className={`text-center font-bold ${(week.flujoDivisas || 0) >= 0 ? 'text-purple-700' : 'text-purple-700'}`}>
                              {formatCurrency(week.flujoDivisas || 0)}
                            </TableCell>
                          ))}
                          <TableCell className="text-center bg-purple-100 text-purple-800 font-bold">
                            {formatCurrency(grandTotalFlujoDivisas)}
                          </TableCell>
                        </TableRow>
                        
                        {/* Venta de USD row */}
                        {grandTotalVentaUSD > 0 && (
                          <TableRow className="hover:bg-purple-50/50">
                            <TableCell className="sticky left-0 bg-white pl-8">
                              <div className="flex items-center gap-1 text-green-600">
                                <TrendingUp size={14} />
                                Venta de USD
                              </div>
                            </TableCell>
                            {weeklyTotals.map((week, idx) => (
                              <TableCell key={idx} className="text-center text-green-600">
                                {(week.ventaUSD || 0) > 0 ? formatCurrency(week.ventaUSD) : '-'}
                              </TableCell>
                            ))}
                            <TableCell className="text-center bg-green-50 text-green-700">
                              {formatCurrency(grandTotalVentaUSD)}
                            </TableCell>
                          </TableRow>
                        )}
                        
                        {/* Compra de USD row */}
                        {grandTotalCompraUSD > 0 && (
                          <TableRow className="hover:bg-purple-50/50">
                            <TableCell className="sticky left-0 bg-white pl-8">
                              <div className="flex items-center gap-1 text-red-600">
                                <TrendingDown size={14} />
                                Compra de USD
                              </div>
                            </TableCell>
                            {weeklyTotals.map((week, idx) => (
                              <TableCell key={idx} className="text-center text-red-600">
                                {(week.compraUSD || 0) > 0 ? formatCurrency(week.compraUSD) : '-'}
                              </TableCell>
                            ))}
                            <TableCell className="text-center bg-red-50 text-red-700">
                              {formatCurrency(grandTotalCompraUSD)}
                            </TableCell>
                          </TableRow>
                        )}
                      </>
                    )}

                    {/* NET CASH FLOW */}
                    <TableRow className="bg-blue-100 font-bold border-t-2 border-blue-300">
                      <TableCell className="sticky left-0 bg-blue-100">
                        FLUJO NETO
                      </TableCell>
                      {weeklyTotals.map((week, idx) => (
                        <TableCell 
                          key={idx} 
                          className={`text-center font-bold ${week.flujoNeto >= 0 ? 'text-green-700' : 'text-red-700'}`}
                        >
                          {formatCurrency(week.flujoNeto)}
                        </TableCell>
                      ))}
                      <TableCell className={`text-center font-bold ${grandTotalFlujo >= 0 ? 'text-green-800 bg-green-100' : 'text-red-800 bg-red-100'}`}>
                        {formatCurrency(grandTotalFlujo)}
                      </TableCell>
                    </TableRow>

                    {/* ENDING CASH BALANCE */}
                    <TableRow className="bg-[#0F172A] text-white font-bold">
                      <TableCell className="sticky left-0 bg-[#0F172A]">
                        SALDO FINAL
                      </TableCell>
                      {weeklyTotals.map((week, idx) => (
                        <TableCell 
                          key={idx} 
                          className={`text-center font-bold ${week.saldoFinal >= 0 ? 'text-green-400' : 'text-red-400'}`}
                        >
                          {formatCurrency(week.saldoFinal)}
                        </TableCell>
                      ))}
                      <TableCell className="text-center font-bold">
                        {formatCurrency(weeklyTotals[weeklyTotals.length - 1]?.saldoFinal || 0)}
                      </TableCell>
                    </TableRow>
                  </TableBody>
                </Table>
              </div>
            </CardContent>
          </Card>
        </TabsContent>

        {/* MONTHLY VIEW */}
        <TabsContent value="monthly" className="mt-4">
          <Card>
            <CardHeader className="bg-[#0F172A] text-white rounded-t-lg">
              <CardTitle>Proyección Mensual</CardTitle>
            </CardHeader>
            <CardContent className="p-0">
              <div className="overflow-x-auto">
                <Table>
                  <TableHeader>
                    <TableRow className="bg-gray-100">
                      <TableHead className="sticky left-0 bg-gray-100 min-w-[250px] font-bold">CONCEPTO</TableHead>
                      {monthlyData.map((month, idx) => (
                        <TableHead key={idx} className="text-center min-w-[130px] capitalize">
                          {month.label}
                        </TableHead>
                      ))}
                      <TableHead className="text-center min-w-[130px] bg-blue-50 font-bold">TOTAL</TableHead>
                    </TableRow>
                  </TableHeader>
                  <TableBody>
                    {/* INGRESOS */}
                    <TableRow className="bg-green-100 font-bold">
                      <TableCell className="sticky left-0 bg-green-100">
                        <TrendingUp className="inline mr-2 text-green-600" size={16} />
                        INGRESOS
                      </TableCell>
                      {monthlyData.map((month, idx) => (
                        <TableCell key={idx} className="text-center text-green-700">
                          {formatCurrency(month.ingresos.total)}
                        </TableCell>
                      ))}
                      <TableCell className="text-center bg-green-200 text-green-800">
                        {formatCurrency(monthlyData.reduce((s, m) => s + m.ingresos.total, 0))}
                      </TableCell>
                    </TableRow>
                    
                    {/* Ingresos by Category */}
                    {categories.filter(c => c.tipo === 'ingreso').map(category => {
                      const monthTotals = monthlyData.map(m => m.ingresos.byCategory[category.nombre] || 0);
                      const total = monthTotals.reduce((s, t) => s + t, 0);
                      if (total === 0) return null;
                      
                      return (
                        <TableRow key={`monthly-ing-${category.id}`} className="hover:bg-green-50">
                          <TableCell className="sticky left-0 bg-white pl-8">{category.nombre}</TableCell>
                          {monthTotals.map((t, idx) => (
                            <TableCell key={idx} className="text-center text-green-600">
                              {t > 0 ? formatCurrency(t) : '-'}
                            </TableCell>
                          ))}
                          <TableCell className="text-center bg-green-50">
                            {formatCurrency(total)}
                          </TableCell>
                        </TableRow>
                      );
                    })}

                    {/* EGRESOS */}
                    <TableRow className="bg-red-100 font-bold">
                      <TableCell className="sticky left-0 bg-red-100">
                        <TrendingDown className="inline mr-2 text-red-600" size={16} />
                        EGRESOS
                      </TableCell>
                      {monthlyData.map((month, idx) => (
                        <TableCell key={idx} className="text-center text-red-700">
                          {formatCurrency(month.egresos.total)}
                        </TableCell>
                      ))}
                      <TableCell className="text-center bg-red-200 text-red-800">
                        {formatCurrency(monthlyData.reduce((s, m) => s + m.egresos.total, 0))}
                      </TableCell>
                    </TableRow>
                    
                    {/* Egresos by Category */}
                    {categories.filter(c => c.tipo === 'egreso').map(category => {
                      const monthTotals = monthlyData.map(m => m.egresos.byCategory[category.nombre] || 0);
                      const total = monthTotals.reduce((s, t) => s + t, 0);
                      if (total === 0) return null;
                      
                      return (
                        <TableRow key={`monthly-egr-${category.id}`} className="hover:bg-red-50">
                          <TableCell className="sticky left-0 bg-white pl-8">{category.nombre}</TableCell>
                          {monthTotals.map((t, idx) => (
                            <TableCell key={idx} className="text-center text-red-600">
                              {t > 0 ? formatCurrency(t) : '-'}
                            </TableCell>
                          ))}
                          <TableCell className="text-center bg-red-50">
                            {formatCurrency(total)}
                          </TableCell>
                        </TableRow>
                      );
                    })}

                    {/* FLUJO NETO */}
                    <TableRow className="bg-blue-100 font-bold border-t-2">
                      <TableCell className="sticky left-0 bg-blue-100">FLUJO NETO</TableCell>
                      {monthlyData.map((month, idx) => {
                        const neto = month.ingresos.total - month.egresos.total;
                        return (
                          <TableCell key={idx} className={`text-center ${neto >= 0 ? 'text-green-700' : 'text-red-700'}`}>
                            {formatCurrency(neto)}
                          </TableCell>
                        );
                      })}
                      <TableCell className="text-center bg-blue-200">
                        {formatCurrency(monthlyData.reduce((s, m) => s + m.ingresos.total - m.egresos.total, 0))}
                      </TableCell>
                    </TableRow>
                  </TableBody>
                </Table>
              </div>
            </CardContent>
          </Card>
        </TabsContent>

        {/* BY PARTY VIEW */}
        <TabsContent value="byParty" className="mt-4 space-y-4">
          <Card>
            <CardHeader>
              <CardTitle>Facturas por Cliente / Proveedor</CardTitle>
            </CardHeader>
            <CardContent>
              <div className="flex gap-4 mb-4">
                <div className="w-48">
                  <Select value={selectedPartyType} onValueChange={(v) => { setSelectedPartyType(v); setSelectedParty(''); }}>
                    <SelectTrigger>
                      <SelectValue placeholder="Tipo" />
                    </SelectTrigger>
                    <SelectContent>
                      <SelectItem value="all">Seleccionar tipo...</SelectItem>
                      <SelectItem value="customer">
                        <div className="flex items-center gap-2">
                          <User size={14} className="text-blue-500" />
                          Clientes
                        </div>
                      </SelectItem>
                      <SelectItem value="vendor">
                        <div className="flex items-center gap-2">
                          <Building2 size={14} className="text-orange-500" />
                          Proveedores
                        </div>
                      </SelectItem>
                    </SelectContent>
                  </Select>
                </div>
                
                {selectedPartyType !== 'all' && (
                  <div className="flex-1">
                    <Select value={selectedParty} onValueChange={setSelectedParty}>
                      <SelectTrigger>
                        <SelectValue placeholder={selectedPartyType === 'customer' ? 'Seleccionar cliente...' : 'Seleccionar proveedor...'} />
                      </SelectTrigger>
                      <SelectContent>
                        {(selectedPartyType === 'customer' ? customers : vendors).map(party => (
                          <SelectItem key={party.id} value={party.id}>
                            <div className="flex flex-col">
                              <span className="font-medium">{party.nombre}</span>
                              <span className="text-xs text-gray-500">{party.rfc}</span>
                            </div>
                          </SelectItem>
                        ))}
                      </SelectContent>
                    </Select>
                  </div>
                )}
              </div>

              {/* Party CFDIs Table */}
              {selectedParty && (
                <div className="border rounded-lg">
                  <Table>
                    <TableHeader>
                      <TableRow className="bg-gray-50">
                        <TableHead>UUID</TableHead>
                        <TableHead>Fecha</TableHead>
                        <TableHead>Tipo</TableHead>
                        <TableHead>Categoría</TableHead>
                        <TableHead>Método Pago</TableHead>
                        <TableHead className="text-right">Subtotal</TableHead>
                        <TableHead className="text-right">IVA</TableHead>
                        <TableHead className="text-right">Total</TableHead>
                        <TableHead className="text-right">Pagado</TableHead>
                        <TableHead className="text-right">Pendiente</TableHead>
                      </TableRow>
                    </TableHeader>
                    <TableBody>
                      {getPartyCfdis().length === 0 ? (
                        <TableRow>
                          <TableCell colSpan={10} className="text-center py-8 text-gray-500">
                            No hay facturas para este {selectedPartyType === 'customer' ? 'cliente' : 'proveedor'}
                          </TableCell>
                        </TableRow>
                      ) : (
                        getPartyCfdis().map(cfdi => {
                          const category = categories.find(c => c.id === cfdi.category_id);
                          const pagado = cfdi.tipo_cfdi === 'ingreso' ? (cfdi.monto_cobrado || 0) : (cfdi.monto_pagado || 0);
                          const pendiente = cfdi.total - pagado;
                          
                          return (
                            <TableRow key={cfdi.id} className="hover:bg-gray-50">
                              <TableCell className="font-mono text-xs">{cfdi.uuid?.substring(0, 8)}...</TableCell>
                              <TableCell>{format(new Date(cfdi.fecha_emision), 'dd/MM/yy')}</TableCell>
                              <TableCell>
                                <span className={`text-xs px-2 py-1 rounded ${cfdi.tipo_cfdi === 'ingreso' ? 'bg-green-100 text-green-800' : 'bg-red-100 text-red-800'}`}>
                                  {cfdi.tipo_cfdi === 'ingreso' ? '↑ Ingreso' : '↓ Egreso'}
                                </span>
                              </TableCell>
                              <TableCell>{category?.nombre || 'Sin categoría'}</TableCell>
                              <TableCell className="text-xs">{cfdi.metodo_pago || 'PUE'}</TableCell>
                              <TableCell className="text-right font-mono">{formatCurrency(cfdi.subtotal)}</TableCell>
                              <TableCell className="text-right font-mono text-gray-500">{formatCurrency(cfdi.impuestos)}</TableCell>
                              <TableCell className="text-right font-mono font-bold">{formatCurrency(cfdi.total)}</TableCell>
                              <TableCell className="text-right font-mono text-green-600">{formatCurrency(pagado)}</TableCell>
                              <TableCell className={`text-right font-mono font-bold ${pendiente > 0 ? 'text-orange-600' : 'text-green-600'}`}>
                                {formatCurrency(pendiente)}
                              </TableCell>
                            </TableRow>
                          );
                        })
                      )}
                    </TableBody>
                  </Table>
                  
                  {/* Summary */}
                  {getPartyCfdis().length > 0 && (
                    <div className="p-4 bg-gray-50 border-t">
                      <div className="flex justify-between items-center">
                        <div className="text-sm text-gray-600">
                          <FileText className="inline mr-2" size={14} />
                          {getPartyCfdis().length} factura(s)
                        </div>
                        <div className="flex gap-8">
                          <div className="text-right">
                            <div className="text-xs text-gray-500">Total Facturado</div>
                            <div className="font-bold">{formatCurrency(getPartyCfdis().reduce((s, c) => s + c.total, 0))}</div>
                          </div>
                          <div className="text-right">
                            <div className="text-xs text-gray-500">Total Pagado</div>
                            <div className="font-bold text-green-600">
                              {formatCurrency(getPartyCfdis().reduce((s, c) => s + (c.tipo_cfdi === 'ingreso' ? (c.monto_cobrado || 0) : (c.monto_pagado || 0)), 0))}
                            </div>
                          </div>
                          <div className="text-right">
                            <div className="text-xs text-gray-500">Saldo Pendiente</div>
                            <div className="font-bold text-orange-600">
                              {formatCurrency(getPartyCfdis().reduce((s, c) => {
                                const pagado = c.tipo_cfdi === 'ingreso' ? (c.monto_cobrado || 0) : (c.monto_pagado || 0);
                                return s + (c.total - pagado);
                              }, 0))}
                            </div>
                          </div>
                        </div>
                      </div>
                    </div>
                  )}
                </div>
              )}
            </CardContent>
          </Card>
        </TabsContent>
      </Tabs>
    </div>
  );
};

export default CashflowProjections;
