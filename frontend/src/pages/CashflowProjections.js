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
import { TrendingUp, TrendingDown, Calendar, Building2, User, FileText, ChevronDown, ChevronRight, Download, Plus, Trash2, Settings, AlertTriangle, BarChart3, Target, Activity } from 'lucide-react';
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
  
  // CFO KPIs configuration
  const [umbralMinimoCaja, setUmbralMinimoCaja] = useState(500000); // Default 500K MXN

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
      const [cfdiRes, catRes, custRes, vendRes, bankSummaryRes, conceptsRes, fxRes, paymentsRes, bankTxnsRes] = await Promise.all([
        api.get('/cfdi?limit=500'),
        api.get('/categories'),
        api.get('/customers'),
        api.get('/vendors'),
        api.get('/bank-accounts/summary'),
        api.get('/manual-projections'),
        api.get('/fx-rates/latest'),
        api.get('/payments'),
        api.get('/bank-transactions?limit=500')
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
      
      // Build set of truly conciliated bank transaction IDs
      const bankTxns = bankTxnsRes.data || [];
      const conciliatedBankTxnIds = new Set(
        bankTxns.filter(t => t.conciliado === true).map(t => t.id)
      );
      
      // Filter payments: only include those with TRULY conciliated bank transactions
      // A payment is valid if:
      // 1. It has no bank_transaction_id (manual payment without reconciliation)
      // 2. OR its bank_transaction_id is in the set of conciliated transactions
      const allPayments = paymentsRes.data || [];
      const validPayments = allPayments.filter(p => {
        if (!p.bank_transaction_id) return true; // Manual payment, include
        return conciliatedBankTxnIds.has(p.bank_transaction_id); // Only if truly conciliated
      });
      
      console.log(`=== FILTRO DE PAGOS ===`);
      console.log(`Total pagos: ${allPayments.length}`);
      console.log(`Pagos válidos (conciliados): ${validPayments.length}`);
      console.log(`Pagos excluidos (txn pendiente): ${allPayments.length - validPayments.length}`);
      
      const categoriesLoaded = catRes.data || [];
      
      // Get company config for week start day
      const companyId = localStorage.getItem('company_id');
      if (companyId) {
        try {
          const compRes = await api.get(`/companies/${companyId}`);
          const weekStart = compRes.data?.inicio_semana ?? 1;
          setCompanyConfig({ ...compRes.data, inicio_semana: weekStart });
          const weeks = processWeeklyData(cfdiRes.data, categoriesLoaded, weekStart, loadedRates, validPayments);
          setWeeklyData(weeks);
        } catch {
          const weeks = processWeeklyData(cfdiRes.data, categoriesLoaded, 1, loadedRates, validPayments);
          setWeeklyData(weeks);
        }
      } else {
        const weeks = processWeeklyData(cfdiRes.data, categoriesLoaded, 1, loadedRates, validPayments);
        setWeeklyData(weeks);
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
    
    // Generate 18 weeks: 4 historical (S1-S4) + 1 current (S5) + 13 projected (S6-S18)
    // Rolling model: as weeks pass, historical weeks become fixed "Real" data
    const weeks = [];
    for (let i = 0; i < 18; i++) {
      const weekStart = addWeeks(startMonday, i);
      const weekEnd = addWeeks(weekStart, 1);
      const isPast = weekEnd <= today;
      const isCurrent = weekStart <= today && today < weekEnd;
      
      // Determine data source type for CFO KPIs
      // S1-S4: Historical (Real), S5: Current (Actual), S6-S18: Projected (Proyectado)
      let dataType = 'proyectado';
      if (isPast) dataType = 'real';
      else if (isCurrent) dataType = 'actual';
      
      weeks.push({
        weekNum: i + 1,
        weekStart,
        weekEnd,
        label: `S${i + 1}`,
        dateLabel: format(weekStart, 'dd MMM', { locale: es }),
        isPast,
        isCurrent,
        dataType, // 'real' | 'actual' | 'proyectado'
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
    // PASO 0: Pre-procesar operaciones de divisas para calcular TC implícito
    // El TC implícito = MXN recibidos (Venta USD) / USD pagados (Compra USD)
    // Esto hace que el efecto neto de las operaciones de cambio sea 0
    // =====================================================================
    const weekCurrencyOps = {}; // { weekIdx: { ventaMXN: 0, compraUSD: 0 } }
    
    payments.forEach(payment => {
      if (payment.estatus !== 'completado') return;
      if (!payment.fecha_pago) return;
      
      const paymentDate = new Date(payment.fecha_pago);
      if (isNaN(paymentDate.getTime())) return;
      
      const weekIdx = weeks.findIndex(w => paymentDate >= w.weekStart && paymentDate < w.weekEnd);
      if (weekIdx === -1) return;
      
      const week = weeks[weekIdx];
      if (!week.isPast && !week.isCurrent) return;
      
      const isCompraUSD = payment.category_id === compraUSDId;
      const isVentaUSD = payment.category_id === ventaUSDId;
      
      if (!weekCurrencyOps[weekIdx]) {
        weekCurrencyOps[weekIdx] = { ventaMXN: 0, compraUSD: 0 };
      }
      
      if (isVentaUSD) {
        // Venta de USD: el monto es en MXN (entrada de pesos)
        weekCurrencyOps[weekIdx].ventaMXN += payment.monto;
      }
      if (isCompraUSD && payment.moneda === 'USD') {
        // Compra de USD: el monto es en USD (dólares que compramos)
        weekCurrencyOps[weekIdx].compraUSD += payment.monto;
      }
    });
    
    // Calcular TC implícito por semana
    const weekImplicitTC = {};
    Object.entries(weekCurrencyOps).forEach(([weekIdx, ops]) => {
      if (ops.compraUSD > 0 && ops.ventaMXN > 0) {
        // TC implícito = MXN recibidos / USD pagados
        weekImplicitTC[weekIdx] = ops.ventaMXN / ops.compraUSD;
      }
    });
    
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
      
      // Get category and subcategory names from payment's inherited data
      const category = categoryMap[payment.category_id];
      const categoryName = category?.nombre || 'Sin categoría';
      const subcategoryInfo = subcategoryMap[payment.subcategory_id];
      const subcategoryName = subcategoryInfo?.nombre || null;
      
      // Check if USD operation
      const isCompraUSD = payment.category_id === compraUSDId;
      const isVentaUSD = payment.category_id === ventaUSDId;
      
      if (isVentaUSD) {
        // Venta de USD: el monto ya está en MXN
        week.ventaUSD += payment.monto;
        return; // Don't add to regular ingresos/egresos
      }
      
      if (isCompraUSD) {
        // Compra de USD: usar TC implícito para que el efecto neto sea 0
        // Si hay TC implícito, usarlo; si no, usar el TC del pago o el estándar
        const implicitTC = weekImplicitTC[weekIdx];
        let montoMXN;
        
        if (implicitTC && payment.moneda === 'USD') {
          // Usar TC implícito para efecto neto = 0
          montoMXN = payment.monto * implicitTC;
        } else if (payment.moneda === 'USD') {
          // Usar TC histórico del pago o el estándar
          const tc = payment.tipo_cambio_historico || effectiveRates.USD || 17.5;
          montoMXN = payment.monto * tc;
        } else {
          montoMXN = payment.monto;
        }
        
        week.compraUSD += montoMXN;
        return; // Don't add to regular ingresos/egresos
      }
      
      const montoMXN = convertToMXN(payment.monto, payment.moneda, effectiveRates);
      
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
      
      // Check if USD operation - SKIP projecting currency operations
      // Currency operations (buy/sell USD) are spot transactions that settle immediately
      // They should only appear when the bank transaction is reconciled (from payments data)
      const isCompraUSD = cfdi.category_id === compraUSDId;
      const isVentaUSD = cfdi.category_id === ventaUSDId;
      
      if (isCompraUSD || isVentaUSD) {
        // Skip - currency operations should not be projected, only show when reconciled
        return;
      }
      
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

  // =====================================================================
  // CÁLCULO DE KPIs "GRADO CFO"
  // =====================================================================
  const calculateCFOKPIs = (totals) => {
    if (!totals || totals.length === 0) return null;
    
    // Separar semanas por tipo de dato
    const semanasReales = totals.filter(w => w.dataType === 'real' || w.dataType === 'actual');
    const semanasProyectadas = totals.filter(w => w.dataType === 'proyectado');
    
    // 1. NET BURN RATE - Promedio semanal de flujo neto
    const burnRateReal = semanasReales.length > 0 
      ? semanasReales.reduce((sum, w) => sum + w.flujoNeto, 0) / semanasReales.length 
      : 0;
    const burnRateProyectado = semanasProyectadas.length > 0 
      ? semanasProyectadas.reduce((sum, w) => sum + w.flujoNeto, 0) / semanasProyectadas.length 
      : 0;
    
    // 2. FORECAST ACCURACY - Variación % Real vs Proyectado (solo para semanas que tienen ambos)
    // Para calcular accuracy, comparamos ingresos/egresos reales vs lo que se había proyectado
    // Aquí usamos las semanas reales como proxy, dado que no tenemos los datos originales proyectados
    const totalIngresosReales = semanasReales.reduce((sum, w) => sum + w.ingresos.total, 0);
    const totalEgresosReales = semanasReales.reduce((sum, w) => sum + w.egresos.total, 0);
    const totalFlujoNetoReal = semanasReales.reduce((sum, w) => sum + w.flujoNeto, 0);
    
    const totalIngresosProyectados = semanasProyectadas.reduce((sum, w) => sum + w.ingresos.total, 0);
    const totalEgresosProyectados = semanasProyectadas.reduce((sum, w) => sum + w.egresos.total, 0);
    const totalFlujoNetoProyectado = semanasProyectadas.reduce((sum, w) => sum + w.flujoNeto, 0);
    
    // Accuracy: qué tan cerca están los ingresos reales del promedio proyectado (escalado)
    // Si no hay proyecciones previas, mostrar N/A
    const promedioIngresosSemanal = totalIngresosProyectados / Math.max(semanasProyectadas.length, 1);
    const promedioEgresosSemanal = totalEgresosProyectados / Math.max(semanasProyectadas.length, 1);
    
    // 3. CASH GAP ANALYSIS - Diferencia vs umbral mínimo por semana
    const cashGapByWeek = totals.map(w => ({
      semana: w.label,
      saldoFinal: w.saldoFinal,
      gap: w.saldoFinal - umbralMinimoCaja,
      enRiesgo: w.saldoFinal < umbralMinimoCaja
    }));
    
    const semanasEnRiesgo = cashGapByWeek.filter(w => w.enRiesgo);
    const semanaCritica = cashGapByWeek.reduce((min, w) => 
      w.saldoFinal < min.saldoFinal ? w : min, 
      cashGapByWeek[0] || { saldoFinal: 0, semana: 'N/A' }
    );
    
    // 4. FLUJO DE CAJA ACUMULADO - Real vs Proyectado
    let acumuladoReal = 0;
    let acumuladoProyectado = 0;
    const flujoAcumulado = totals.map(w => {
      if (w.dataType === 'real' || w.dataType === 'actual') {
        acumuladoReal += w.flujoNeto;
        return { ...w, acumuladoReal, acumuladoProyectado };
      } else {
        acumuladoProyectado += w.flujoNeto;
        return { ...w, acumuladoReal, acumuladoProyectado: acumuladoReal + acumuladoProyectado };
      }
    });
    
    // 5. VOLATILIDAD - Desviación estándar del flujo neto real
    let volatilidad = 0;
    if (semanasReales.length > 1) {
      const mediaFlujo = totalFlujoNetoReal / semanasReales.length;
      const sumaCuadrados = semanasReales.reduce((sum, w) => sum + Math.pow(w.flujoNeto - mediaFlujo, 2), 0);
      volatilidad = Math.sqrt(sumaCuadrados / semanasReales.length);
    }
    
    // Coeficiente de variación (volatilidad relativa)
    const coeficienteVariacion = burnRateReal !== 0 ? (volatilidad / Math.abs(burnRateReal)) * 100 : 0;
    
    // 6. RUNWAY - Semanas de operación con saldo actual
    const saldoActual = totals.find(w => w.dataType === 'actual')?.saldoFinal || totals[0]?.saldoFinal || 0;
    const egresoPromedio = (totalEgresosReales + totalEgresosProyectados) / totals.length;
    const runway = egresoPromedio > 0 ? Math.floor(saldoActual / egresoPromedio) : 999;
    
    // 7. RATIO COBRANZA VS PAGOS
    const ratioCobranzaPagos = totalEgresosReales > 0 
      ? (totalIngresosReales / totalEgresosReales) 
      : totalIngresosReales > 0 ? 999 : 1;
    
    return {
      // Net Burn Rate
      burnRateReal,
      burnRateProyectado,
      burnRateDelta: burnRateProyectado - burnRateReal,
      
      // Totales
      totalIngresosReales,
      totalEgresosReales,
      totalFlujoNetoReal,
      totalIngresosProyectados,
      totalEgresosProyectados,
      totalFlujoNetoProyectado,
      
      // Promedios
      promedioIngresosSemanal,
      promedioEgresosSemanal,
      
      // Cash Gap
      cashGapByWeek,
      semanasEnRiesgo,
      semanaCritica,
      
      // Flujo Acumulado
      flujoAcumulado,
      acumuladoRealFinal: acumuladoReal,
      acumuladoProyectadoFinal: acumuladoReal + acumuladoProyectado,
      
      // Volatilidad
      volatilidad,
      coeficienteVariacion,
      
      // Operacionales
      runway,
      ratioCobranzaPagos,
      
      // Metadata
      semanasRealesCount: semanasReales.length,
      semanasProyectadasCount: semanasProyectadas.length
    };
  };

  if (loading) return <div className="p-8">Cargando proyecciones...</div>;

  const weeklyTotals = calculateRunningTotals();
  const cfoKPIs = calculateCFOKPIs(weeklyTotals);
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
            Modelo Rolling 18 semanas (4 Real + 1 Actual + 13 Proyectado) | Inicio: {DIAS_SEMANA.find(d => d.value === companyConfig.inicio_semana)?.label || 'Lunes'}
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
                <div className="space-y-2 mt-4 pt-4 border-t">
                  <Label>Umbral Mínimo de Caja (Cash Gap Analysis)</Label>
                  <Input 
                    type="number"
                    value={umbralMinimoCaja}
                    onChange={(e) => setUmbralMinimoCaja(parseFloat(e.target.value) || 0)}
                    placeholder="Ej: 500000"
                  />
                  <p className="text-sm text-gray-500">
                    Monto mínimo de efectivo requerido. Se usará para calcular el Cash Gap.
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
            Vista Semanal (18 semanas)
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
        <TabsContent value="weekly" className="mt-4 space-y-4">
          
          {/* ===== CFO KPIs DASHBOARD ===== */}
          {cfoKPIs && (
            <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-4" data-testid="cfo-kpis-section">
              {/* Net Burn Rate */}
              <Card className="border-l-4 border-l-blue-500">
                <CardContent className="pt-4">
                  <div className="flex items-center gap-2 text-sm text-gray-500 mb-1">
                    <Activity size={14} />
                    Net Burn Rate
                  </div>
                  <div className="space-y-1">
                    <div className="flex justify-between items-baseline">
                      <span className="text-xs text-gray-400">Real (S1-S4):</span>
                      <span className={`text-lg font-bold ${cfoKPIs.burnRateReal >= 0 ? 'text-green-600' : 'text-red-600'}`}>
                        {formatCurrency(cfoKPIs.burnRateReal)}/sem
                      </span>
                    </div>
                    <div className="flex justify-between items-baseline">
                      <span className="text-xs text-gray-400">Proy (S6-S18):</span>
                      <span className={`text-lg font-bold ${cfoKPIs.burnRateProyectado >= 0 ? 'text-green-600' : 'text-red-600'}`}>
                        {formatCurrency(cfoKPIs.burnRateProyectado)}/sem
                      </span>
                    </div>
                  </div>
                </CardContent>
              </Card>

              {/* Cash Gap Analysis */}
              <Card className={`border-l-4 ${cfoKPIs.semanasEnRiesgo.length > 0 ? 'border-l-red-500' : 'border-l-green-500'}`}>
                <CardContent className="pt-4">
                  <div className="flex items-center gap-2 text-sm text-gray-500 mb-1">
                    <AlertTriangle size={14} />
                    Cash Gap Analysis
                  </div>
                  <div className="space-y-1">
                    <div className="flex justify-between items-baseline">
                      <span className="text-xs text-gray-400">Umbral mínimo:</span>
                      <span className="text-sm font-medium">{formatCurrency(umbralMinimoCaja)}</span>
                    </div>
                    <div className="flex justify-between items-baseline">
                      <span className="text-xs text-gray-400">Semanas en riesgo:</span>
                      <span className={`text-lg font-bold ${cfoKPIs.semanasEnRiesgo.length > 0 ? 'text-red-600' : 'text-green-600'}`}>
                        {cfoKPIs.semanasEnRiesgo.length} de 18
                      </span>
                    </div>
                    {cfoKPIs.semanaCritica && (
                      <div className="flex justify-between items-baseline">
                        <span className="text-xs text-gray-400">Semana crítica:</span>
                        <span className="text-sm font-medium text-red-500">
                          {cfoKPIs.semanaCritica.semana} ({formatCurrency(cfoKPIs.semanaCritica.saldoFinal)})
                        </span>
                      </div>
                    )}
                  </div>
                </CardContent>
              </Card>

              {/* Volatilidad del Flujo */}
              <Card className="border-l-4 border-l-purple-500">
                <CardContent className="pt-4">
                  <div className="flex items-center gap-2 text-sm text-gray-500 mb-1">
                    <BarChart3 size={14} />
                    Volatilidad del Flujo
                  </div>
                  <div className="space-y-1">
                    <div className="flex justify-between items-baseline">
                      <span className="text-xs text-gray-400">Desv. Estándar:</span>
                      <span className="text-lg font-bold text-purple-600">
                        {formatCurrency(cfoKPIs.volatilidad)}
                      </span>
                    </div>
                    <div className="flex justify-between items-baseline">
                      <span className="text-xs text-gray-400">Coef. Variación:</span>
                      <span className={`text-sm font-medium ${cfoKPIs.coeficienteVariacion > 50 ? 'text-red-500' : cfoKPIs.coeficienteVariacion > 25 ? 'text-amber-500' : 'text-green-500'}`}>
                        {cfoKPIs.coeficienteVariacion.toFixed(1)}%
                      </span>
                    </div>
                    <p className="text-xs text-gray-400 mt-1">
                      {cfoKPIs.coeficienteVariacion > 50 ? '⚠️ Alta volatilidad' : cfoKPIs.coeficienteVariacion > 25 ? '⚡ Volatilidad moderada' : '✅ Flujo estable'}
                    </p>
                  </div>
                </CardContent>
              </Card>

              {/* Runway & Ratio */}
              <Card className="border-l-4 border-l-amber-500">
                <CardContent className="pt-4">
                  <div className="flex items-center gap-2 text-sm text-gray-500 mb-1">
                    <Target size={14} />
                    Indicadores Operativos
                  </div>
                  <div className="space-y-1">
                    <div className="flex justify-between items-baseline">
                      <span className="text-xs text-gray-400">Runway:</span>
                      <span className={`text-lg font-bold ${cfoKPIs.runway < 8 ? 'text-red-600' : cfoKPIs.runway < 16 ? 'text-amber-600' : 'text-green-600'}`}>
                        {cfoKPIs.runway > 100 ? '100+' : cfoKPIs.runway} semanas
                      </span>
                    </div>
                    <div className="flex justify-between items-baseline">
                      <span className="text-xs text-gray-400">Ratio Cobranza/Pagos:</span>
                      <span className={`text-lg font-bold ${cfoKPIs.ratioCobranzaPagos >= 1 ? 'text-green-600' : 'text-red-600'}`}>
                        {cfoKPIs.ratioCobranzaPagos > 10 ? '>10' : cfoKPIs.ratioCobranzaPagos.toFixed(2)}x
                      </span>
                    </div>
                    <p className="text-xs text-gray-400 mt-1">
                      {cfoKPIs.ratioCobranzaPagos >= 1 ? '✅ Cobranza > Pagos' : '⚠️ Pagos > Cobranza'}
                    </p>
                  </div>
                </CardContent>
              </Card>
            </div>
          )}

          {/* ===== FLUJO ACUMULADO RESUMEN ===== */}
          {cfoKPIs && (
            <Card className="bg-gradient-to-r from-slate-50 to-blue-50" data-testid="flujo-acumulado-section">
              <CardHeader className="py-3">
                <CardTitle className="text-base flex items-center gap-2">
                  <TrendingUp size={18} />
                  Flujo de Caja Acumulado: Real vs Proyectado
                </CardTitle>
              </CardHeader>
              <CardContent className="py-2">
                <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
                  <div className="text-center p-3 bg-white rounded-lg shadow-sm">
                    <div className="text-xs text-gray-500 mb-1">Ingresos Reales (S1-S5)</div>
                    <div className="text-xl font-bold text-green-600">{formatCurrency(cfoKPIs.totalIngresosReales)}</div>
                  </div>
                  <div className="text-center p-3 bg-white rounded-lg shadow-sm">
                    <div className="text-xs text-gray-500 mb-1">Egresos Reales (S1-S5)</div>
                    <div className="text-xl font-bold text-red-600">{formatCurrency(cfoKPIs.totalEgresosReales)}</div>
                  </div>
                  <div className="text-center p-3 bg-white rounded-lg shadow-sm">
                    <div className="text-xs text-gray-500 mb-1">Ingresos Proyectados (S6-S18)</div>
                    <div className="text-xl font-bold text-green-500">{formatCurrency(cfoKPIs.totalIngresosProyectados)}</div>
                  </div>
                  <div className="text-center p-3 bg-white rounded-lg shadow-sm">
                    <div className="text-xs text-gray-500 mb-1">Egresos Proyectados (S6-S18)</div>
                    <div className="text-xl font-bold text-red-500">{formatCurrency(cfoKPIs.totalEgresosProyectados)}</div>
                  </div>
                </div>
                <div className="mt-4 grid grid-cols-2 gap-4">
                  <div className="text-center p-4 bg-blue-100 rounded-lg">
                    <div className="text-sm text-blue-700 mb-1">Flujo Neto Real Acumulado</div>
                    <div className={`text-2xl font-bold ${cfoKPIs.totalFlujoNetoReal >= 0 ? 'text-green-700' : 'text-red-700'}`}>
                      {formatCurrency(cfoKPIs.totalFlujoNetoReal)}
                    </div>
                  </div>
                  <div className="text-center p-4 bg-indigo-100 rounded-lg">
                    <div className="text-sm text-indigo-700 mb-1">Flujo Neto Proyectado Total</div>
                    <div className={`text-2xl font-bold ${cfoKPIs.acumuladoProyectadoFinal >= 0 ? 'text-green-700' : 'text-red-700'}`}>
                      {formatCurrency(cfoKPIs.acumuladoProyectadoFinal)}
                    </div>
                  </div>
                </div>
              </CardContent>
            </Card>
          )}

          {/* ===== MAIN CASH FLOW TABLE ===== */}
          <Card>
            <CardHeader className="bg-[#0F172A] text-white rounded-t-lg">
              <CardTitle className="flex items-center justify-between">
                <span>Modelo de Flujo de Efectivo - 18 Semanas</span>
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
                        <TableHead key={idx} className={`text-center min-w-[90px] ${
                          week.dataType === 'real' ? 'bg-yellow-50' : 
                          week.dataType === 'actual' ? 'bg-blue-50' : 'bg-gray-50'
                        }`}>
                          <div className="font-bold">{week.label}</div>
                          <div className="text-xs text-gray-500">{week.dateLabel}</div>
                          <div className={`text-xs font-semibold ${
                            week.dataType === 'real' ? 'text-yellow-600' : 
                            week.dataType === 'actual' ? 'text-blue-600' : 'text-gray-400'
                          }`}>
                            {week.dataType === 'real' ? 'Real' : week.dataType === 'actual' ? 'Actual' : 'Proy'}
                          </div>
                        </TableHead>
                      ))}
                      <TableHead className="text-center min-w-[120px] bg-blue-50 font-bold">TOTAL</TableHead>
                    </TableRow>
                  </TableHeader>
                  <TableBody>
                    {/* SALDO INICIAL POR SEMANA Row */}
                    <TableRow className="bg-blue-100 font-bold border-b-2 border-blue-300">
                      <TableCell className="sticky left-0 bg-blue-100">
                        <div className="flex items-center gap-2">
                          <Building2 className="text-blue-600" size={16} />
                          SALDO INICIAL SEMANA
                        </div>
                      </TableCell>
                      {weeklyTotals.map((week, idx) => (
                        <TableCell key={idx} className="text-center text-blue-700 font-bold text-sm">
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
                          {weeklyTotals.some(w => w.dataType === 'real' || w.dataType === 'actual') && (
                            <span className="text-xs px-2 py-0.5 bg-green-200 text-green-800 rounded">S1-S5 Real</span>
                          )}
                        </div>
                      </TableCell>
                      {weeklyTotals.map((week, idx) => (
                        <TableCell key={idx} className={`text-center font-bold text-sm ${
                          week.dataType === 'real' ? 'text-green-800 bg-green-100' : 
                          week.dataType === 'actual' ? 'text-green-700 bg-green-50' : 'text-green-600'
                        }`}>
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

                    {/* OPERATING DISBURSEMENTS / EGRESOS Section */}
                    <TableRow className="bg-red-50 font-bold">
                      <TableCell className="sticky left-0 bg-red-50">
                        <div className="flex items-center gap-2">
                          <TrendingDown className="text-red-600" size={16} />
                          EGRESOS
                          {weeklyTotals.some(w => w.hasRealData) && (
                            <span className="text-xs px-2 py-0.5 bg-red-200 text-red-800 rounded">Incluye Datos Reales</span>
                          )}
                        </div>
                      </TableCell>
                      {weeklyTotals.map((week, idx) => (
                        <TableCell key={idx} className={`text-center font-bold ${week.hasRealData ? 'text-red-800 bg-red-100' : 'text-red-700'}`}>
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
                        
                        {/* Venta de USD row - SIEMPRE MOSTRAR */}
                        <TableRow className="hover:bg-purple-50/50">
                          <TableCell className="sticky left-0 bg-white pl-8">
                            <div className="flex items-center gap-1 text-green-600">
                              <TrendingUp size={14} />
                              Venta de USD (entrada MXN)
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
                        
                        {/* Compra de USD row - SIEMPRE MOSTRAR */}
                        <TableRow className="hover:bg-purple-50/50">
                          <TableCell className="sticky left-0 bg-white pl-8">
                            <div className="flex items-center gap-1 text-red-600">
                              <TrendingDown size={14} />
                              Compra de USD (salida MXN)
                            </div>
                          </TableCell>
                          {weeklyTotals.map((week, idx) => (
                            <TableCell key={idx} className="text-center text-red-600">
                              {(week.compraUSD || 0) > 0 ? `(${formatCurrency(week.compraUSD)})` : '-'}
                            </TableCell>
                          ))}
                          <TableCell className="text-center bg-red-50 text-red-700">
                            {grandTotalCompraUSD > 0 ? `(${formatCurrency(grandTotalCompraUSD)})` : '$0.00'}
                          </TableCell>
                        </TableRow>
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

                    {/* SALDO FINAL POR SEMANA */}
                    <TableRow className="bg-[#0F172A] text-white font-bold">
                      <TableCell className="sticky left-0 bg-[#0F172A]">
                        SALDO FINAL SEMANA
                      </TableCell>
                      {weeklyTotals.map((week, idx) => (
                        <TableCell 
                          key={idx} 
                          className={`text-center font-bold text-sm ${week.saldoFinal >= 0 ? 'text-green-400' : 'text-red-400'}`}
                        >
                          {formatCurrency(week.saldoFinal)}
                        </TableCell>
                      ))}
                      <TableCell className="text-center font-bold">
                        {formatCurrency(weeklyTotals[weeklyTotals.length - 1]?.saldoFinal || 0)}
                      </TableCell>
                    </TableRow>

                    {/* CASH GAP - Diferencia vs Umbral Mínimo */}
                    <TableRow className="bg-amber-50 font-medium">
                      <TableCell className="sticky left-0 bg-amber-50">
                        <div className="flex items-center gap-2">
                          <AlertTriangle className="text-amber-600" size={14} />
                          CASH GAP (vs {formatCurrency(umbralMinimoCaja)})
                        </div>
                      </TableCell>
                      {weeklyTotals.map((week, idx) => {
                        const gap = week.saldoFinal - umbralMinimoCaja;
                        const isNegative = gap < 0;
                        return (
                          <TableCell 
                            key={idx} 
                            className={`text-center text-sm ${isNegative ? 'text-red-600 bg-red-50 font-bold' : 'text-green-600'}`}
                          >
                            {isNegative ? `(${formatCurrency(Math.abs(gap))})` : formatCurrency(gap)}
                          </TableCell>
                        );
                      })}
                      <TableCell className="text-center bg-amber-100 text-amber-800 font-bold">
                        {(() => {
                          const finalGap = (weeklyTotals[weeklyTotals.length - 1]?.saldoFinal || 0) - umbralMinimoCaja;
                          return finalGap < 0 ? `(${formatCurrency(Math.abs(finalGap))})` : formatCurrency(finalGap);
                        })()}
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
