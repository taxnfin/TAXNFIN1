import React, { useState, useEffect, useRef, useCallback } from 'react';
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
import { Badge } from '@/components/ui/badge';
import { toast } from 'sonner';
import { TrendingUp, TrendingDown, Calendar, Building2, User, FileText, ChevronDown, ChevronRight, Download, Plus, Trash2, Settings, AlertTriangle, BarChart3, Target, Activity, FileDown, ExternalLink, Check, X as XIcon, Eye, ToggleLeft, ToggleRight, FileSpreadsheet, Layers, Filter, Search, Globe } from 'lucide-react';
import { format, addWeeks, startOfWeek, addMonths, startOfMonth } from 'date-fns';
import { es, enUS, ptBR } from 'date-fns/locale';
import { exportProjections, exportToExcel } from '@/utils/excelExport';
import { LineChart, Line, BarChart, Bar, XAxis, YAxis, CartesianGrid, Tooltip, Legend, ResponsiveContainer, ComposedChart, Area, ReferenceLine } from 'recharts';
import html2canvas from 'html2canvas';
import jsPDF from 'jspdf';
import { financialTranslations, languages } from '../utils/financialTranslations';

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
  const [language, setLanguage] = useState('es');
  const [loading, setLoading] = useState(true);
  const [weeklyData, setWeeklyData] = useState([]);
  const [cxcCxpData, setCxcCxpData] = useState({ cxc: [], cxp: [] });
  const [cfdis, setCfdis] = useState([]);
  const [categories, setCategories] = useState([]);
  const [customers, setCustomers] = useState([]);
  const [vendors, setVendors] = useState([]);
  const [viewMode, setViewMode] = useState('weekly');
  const [expandedRows, setExpandedRows] = useState({});
  const [selectedPartyType, setSelectedPartyType] = useState('all');
  const [selectedParty, setSelectedParty] = useState('');
  
  // Translation helper
  const t = financialTranslations[language];
  const dateLocale = language === 'es' ? es : language === 'pt' ? ptBR : enUS;
  
  // Company config
  const [companyConfig, setCompanyConfig] = useState({ inicio_semana: 1 });
  const [configDialogOpen, setConfigDialogOpen] = useState(false);
  
  // User-selected starting date for the 18-week window (overrides auto-detection).
  // Empty string = automatic (default: 4 weeks before today, snapped to weekStart).
  const [customStartDate, setCustomStartDate] = useState(() => {
    try { return localStorage.getItem('cashflow_custom_start_date') || ''; } catch { return ''; }
  });
  
  // Date range filter for week display (empty = default: current week onward)
  const [filterFechaInicio, setFilterFechaInicio] = useState('');
  const [filterFechaFin, setFilterFechaFin] = useState('');

  // Currency selector for projections
  const [selectedCurrency, setSelectedCurrency] = useState('MXN');
  const [fxRates, setFxRates] = useState({ MXN: 1, USD: 17.4545, EUR: 20.4852, GBP: 22.00, JPY: 0.13, CHF: 20.00, CAD: 13.00, CNY: 2.40 });
  
  // Custom concepts state
  const [customConcepts, setCustomConcepts] = useState([]);
  const [conceptDialogOpen, setConceptDialogOpen] = useState(false);
  const [saldoInicialBancos, setSaldoInicialBancos] = useState(0);
  
  // PDF export state
  const [exportingPdf, setExportingPdf] = useState(false);
  const reportRef = useRef(null);
  const chartsRef = useRef(null);
  // Ref para el patrón "latest ref": openKpiModal lee de aquí en lugar de closures del render
  const kpiStateRef = useRef({ cfoKPIs: null, KPI_DEFS: null, formatCurrency: null });
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

  // Drill-down dialog state
  const [drillDownOpen, setDrillDownOpen] = useState(false);
  const [drillDownData, setDrillDownData] = useState({
    weekNum: null,
    weekLabel: '',
    dateLabel: '',
    tipo: '', // 'ingreso' | 'egreso'
    categoryName: '',
    subcategoryName: '',
    items: [],
    total: 0
  });

  // View mode toggle: 'categoria' | 'tercero'
  const [tableViewMode, setTableViewMode] = useState('categoria');

  // Filters for "Por Proveedor/Cliente" view
  const [partyFilters, setPartyFilters] = useState({
    searchTerm: '',
    tipoTercero: 'todos', // 'todos' | 'cliente' | 'proveedor'
    saldoTipo: 'todos' // 'todos' | 'positivo' | 'negativo'
  });

  // Payments and bank transactions for drill-down
  const [allPayments, setAllPayments] = useState([]);
  const [bankTransactions, setBankTransactions] = useState([]);
  const [reconciliations, setReconciliations] = useState([]);
  const [bankAccounts, setBankAccounts] = useState([]);

  // KPI Insight modal — status: 'good' | 'warning' | 'danger' | 'neutral'
  const [kpiModal, setKpiModal] = useState({ open: false, name: '', formula: '', description: '', values: {}, insight: '', loading: false, status: 'neutral', kpiKey: '' });

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
    // Re-run whenever the user-selected start date changes so the 18-week
    // window updates without needing a manual page refresh.
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [customStartDate]);

  // Inyectar proyecciones manuales CxC/CxP en semanas futuras del modelo
  // CxC/CxP ya se inyectan en processWeeklyData (PASO 3) por matching de fecha.
  // Este useEffect queda desactivado para evitar doble-conteo.
  useEffect(() => {}, [cxcCxpData]); // eslint-disable-line react-hooks/exhaustive-deps

  const loadData = async () => {
    setLoading(true);
    try {
      const [cfdiRes, catRes, custRes, vendRes, bankSummaryRes, conceptsRes, fxRes, paymentsRes, bankTxnsRes, reconRes, bankAccountsRes] = await Promise.all([
        api.get('/cfdi?limit=500'),
        api.get('/cashflow-sync/categories'),
        api.get('/customers'),
        api.get('/vendors'),
        api.get('/bank-accounts/summary'),
        api.get('/manual-projections'),
        api.get('/fx-rates/latest'),
        api.get('/payments?limit=1000'),
        api.get('/bank-transactions?limit=500'),
        api.get('/reconciliations'),
        api.get('/bank-accounts')
      ]);
      
      setCfdis(cfdiRes.data);
      setCategories(catRes.data);
      setCustomers(custRes.data);
      setVendors(vendRes.data);
      
      // Store payments and bank transactions for drill-down
      setAllPayments(paymentsRes.data || []);
      setBankTransactions(bankTxnsRes.data || []);
      setReconciliations(reconRes.data || []);
      setBankAccounts(bankAccountsRes.data || []);
      
      // Get initial bank balance
      const totalBancosMXN = bankSummaryRes.data?.total_mxn || 0;
      setSaldoInicialBancos(totalBancosMXN);
      console.log('[CashFlow base bancaria]', {
        total_mxn: totalBancosMXN,
        por_banco: bankSummaryRes.data?.por_banco,
        por_moneda: bankSummaryRes.data?.por_moneda,
      });
      
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
      
      // Get company config for week start day.
      // The active company is stored as JSON under 'selectedCompany' (set by App.js).
      // We also fall back to the user's company_id from the stored auth user.
      const getActiveCompanyId = () => {
        try {
          const sel = localStorage.getItem('selectedCompany');
          if (sel) {
            const parsed = JSON.parse(sel);
            if (parsed?.id) return parsed.id;
          }
        } catch {/* ignore */}
        try {
          const u = localStorage.getItem('user');
          if (u) {
            const parsed = JSON.parse(u);
            if (parsed?.company_id) return parsed.company_id;
          }
        } catch {/* ignore */}
        return null;
      };
      
      const companyId = getActiveCompanyId();
      // ── Cargar proyecciones CxC/CxP ANTES de procesar semanas ────────
      let porSemana = {};
      try {
        const proyRes = await api.get('/cxc-proyecciones/por-semana');
        porSemana = proyRes.data || {};

        if (Object.keys(porSemana).length > 0) {
          setCxcCxpData({ porSemana });
        }
      } catch (e) {
        console.log('CxC/CxP proyecciones no disponibles:', e.message);
      }

      if (companyId) {
        try {
          const compRes = await api.get(`/companies/${companyId}`);
          const weekStart = compRes.data?.inicio_semana ?? 1;
          setCompanyConfig({ ...compRes.data, inicio_semana: weekStart });
          const weeks = processWeeklyData(cfdiRes.data, categoriesLoaded, weekStart, loadedRates, allPayments, customStartDate, porSemana);
          setWeeklyData(weeks);
        } catch {
          const weeks = processWeeklyData(cfdiRes.data, categoriesLoaded, 1, loadedRates, allPayments, customStartDate, porSemana);
          setWeeklyData(weeks);
        }
      } else {
        const weeks = processWeeklyData(cfdiRes.data, categoriesLoaded, 1, loadedRates, allPayments, customStartDate, porSemana);
        setWeeklyData(weeks);
      }

      // Vista mensual se deriva de weeklyTotals en render — no requiere llamada separada
    } catch (error) {
      console.error('Error loading cashflow data:', error);
      toast.error(t?.errorLoadingData || 'Error loading data');
    } finally {
      setLoading(false);
    }
  };

  const handleSaveCustomStartDate = (newDate) => {
    try {
      if (newDate) {
        localStorage.setItem('cashflow_custom_start_date', newDate);
      } else {
        localStorage.removeItem('cashflow_custom_start_date');
      }
    } catch {/* ignore */}
    // setState triggers the useEffect below which calls loadData with the fresh value.
    setCustomStartDate(newDate);
    if (newDate) {
      toast.success(`Inicio del flujo establecido al ${newDate}`);
    } else {
      toast.success('Inicio del flujo restaurado a automático');
    }
  };

  const handleSaveWeekStart = async (newWeekStart) => {
    try {
      // Resolve active company id from localStorage (selectedCompany JSON, then user.company_id)
      let companyId = null;
      try {
        const sel = localStorage.getItem('selectedCompany');
        if (sel) companyId = JSON.parse(sel)?.id || null;
      } catch {/* ignore */}
      if (!companyId) {
        try {
          const u = localStorage.getItem('user');
          if (u) companyId = JSON.parse(u)?.company_id || null;
        } catch {/* ignore */}
      }
      if (!companyId) {
        toast.error('No se encontró la empresa activa');
        return;
      }
      await api.put(`/companies/${companyId}`, { inicio_semana: newWeekStart });
      setCompanyConfig(prev => ({ ...prev, inicio_semana: newWeekStart }));
      // Also keep the cached `selectedCompany` in localStorage in sync, so other
      // pages (e.g. Dashboard) pick up the new inicio_semana without re-login.
      try {
        const sel = localStorage.getItem('selectedCompany');
        if (sel) {
          const parsed = JSON.parse(sel);
          parsed.inicio_semana = newWeekStart;
          localStorage.setItem('selectedCompany', JSON.stringify(parsed));
        }
      } catch {/* ignore */}
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

  const processWeeklyData = (cfdisData, categoriesData, weekStartDay = 1, rates = {}, payments = [], customStart = '', porSemana = {}) => {
    // =====================================================================
    // NUEVA LÓGICA: ÚNICA FUENTE DE VERDAD
    // - Semanas pasadas/actuales: SOLO datos de Cobranza y Pagos
    // - Semanas futuras: CFDIs pendientes (proyecciones)
    // - TOTAL INGRESOS = Suma exacta de sublíneas por categoría
    // =====================================================================
    
    const effectiveRates = { MXN: 1, USD: 17.599, EUR: 20.4852, ...fxRates, ...rates };
    
    // Returns the start of the week for `date` according to `weekStartDay`.
    // weekStartDay: 0=Sunday, 1=Monday, 2=Tuesday, ..., 6=Saturday
    const getWeekStart = (date, startDay = 1) => {
      const d = new Date(date);
      d.setHours(0, 0, 0, 0);
      const day = d.getDay(); // 0 (Sun) - 6 (Sat)
      let diff = day - startDay;
      if (diff < 0) diff += 7;
      d.setDate(d.getDate() - diff);
      return d;
    };
    
    const today = new Date();
    const currentWeekStart = getWeekStart(today, weekStartDay);
    
    // Fiscal year anchor for LABELS: S1 = week of Dec 29, 2025 (ISO week 1/2026).
    // Weeks before this date display as S{isoWeek}/{shortYear} (e.g. S52/25).
    // startWeek remains dynamic so historical data before the anchor stays visible.
    const FISCAL_YEAR_START = new Date(2025, 11, 29);

    // Find earliest payment date to anchor the historical display window
    let earliestDate = null;
    payments.filter(p => p.estatus === 'completado' || p.estatus === 'pagado' || p.status === 'pagado' || p.es_real === true).forEach(p => {
      const fecha = p.fecha_pago;
      if (fecha) {
        const d = new Date(fecha);
        if (!earliestDate || d < earliestDate) earliestDate = d;
      }
    });

    const fourWeeksAgo = addWeeks(currentWeekStart, -17);

    // Window start priority: 1) explicit customStart, 2) earliest payment, 3) 17 weeks ago
    let startWeek;
    if (customStart) {
      const parsed = new Date(customStart);
      if (!isNaN(parsed.getTime())) {
        startWeek = getWeekStart(parsed, weekStartDay);
      }
    }
    if (!startWeek) {
      startWeek = earliestDate
        ? getWeekStart(earliestDate, weekStartDay)
        : fourWeeksAgo;
    }
    
    // Generate 52 weeks: historical (Real) + 1 current (Actual) + up to 35 projected forward
    const weeks = [];
    for (let i = 0; i < 52; i++) {
      const weekStart = addWeeks(startWeek, i);
      const weekEnd = addWeeks(weekStart, 1);
      const isPast = weekEnd <= today;
      const isCurrent = weekStart <= today && today < weekEnd;
      
      // Determine data source type for CFO KPIs
      // S1-S4: Historical (Real), S5: Current (Actual), S6-S18: Projected (Proyectado)
      let dataType = 'proyectado';
      if (isPast) dataType = 'real';
      else if (isCurrent) dataType = 'actual';
      
      const fiscalDiff = Math.round(
        (weekStart.getTime() - FISCAL_YEAR_START.getTime()) / (7 * 24 * 60 * 60 * 1000)
      );
      const displayLabel = fiscalDiff >= 0
        ? `S${fiscalDiff + 1}`
        : `S${53 + fiscalDiff}/${String(weekStart.getFullYear()).slice(-2)}`;

      weeks.push({
        weekNum: i + 1,
        weekStart,
        weekEnd,
        label: `S${i + 1}`,
        displayLabel,
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
      if (cat.code) categoryMap[cat.code] = cat; // cashflow-sync categories use 'code' as id
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
      if (payment.estatus !== 'completado' && payment.status !== 'pagado') return;
      if (!payment.fecha_pago) return;
      
      const paymentDate = new Date(payment.fecha_pago);
      if (isNaN(paymentDate.getTime())) return;
      
      const weekIdx = weeks.findIndex(w => paymentDate >= w.weekStart && paymentDate < w.weekEnd);
      if (weekIdx === -1) return;
      
      const week = weeks[weekIdx];
      if (!week.isPast && !week.isCurrent) return;
      
      const isCompraUSD = payment.category_id && compraUSDId && payment.category_id === compraUSDId;
      const isVentaUSD = payment.category_id && ventaUSDId && payment.category_id === ventaUSDId;
      
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
      if (payment.estatus !== 'completado' && payment.status !== 'pagado') return;
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
      
      // Check if USD operation (only if category_id is not null)
      const isCompraUSD = payment.category_id && compraUSDId && payment.category_id === compraUSDId;
      const isVentaUSD = payment.category_id && ventaUSDId && payment.category_id === ventaUSDId;
      
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
        bankAccountId: payment.bank_account_id,
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
        beneficiario: payment.beneficiario,
        bankAccountId: payment.bank_account_id,
        source: 'payment'
      });
      
      // Add to section total
      section.total += montoMXN;
    });
    
    // =====================================================================
    // PASO 2: Procesar CFDIs (PROYECCIONES para semanas futuras)
    // Si hay datos de CxC/CxP del Aging (porSemana), estos son la fuente
    // de verdad para proyecciones — no proyectar CFDIs para evitar duplicación.
    // =====================================================================
    const usarCxCComoProyeccion = porSemana && Object.keys(porSemana).length > 0;

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

      // Si hay CxC/CxP del Aging, esa es la fuente de verdad para proyecciones.
      // No proyectar CFDIs para evitar duplicación con el Aging.
      if (usarCxCComoProyeccion) return;
      
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
        fecha: cfdi.fecha_emision,
        moneda: cfdi.moneda,
        source: 'cfdi'
      });
      
      // Add to subcategory
      const subKey = subcategoryName || 'General';
      if (!section.byCategory[categoryName].bySubcategory[subKey]) {
        section.byCategory[categoryName].bySubcategory[subKey] = { total: 0, items: [] };
      }
      section.byCategory[categoryName].bySubcategory[subKey].total += montoMXN;
      section.byCategory[categoryName].bySubcategory[subKey].items.push({
        id: cfdi.id,
        monto: montoMXN,
        uuid: cfdi.uuid,
        emisor: cfdi.emisor_nombre,
        receptor: cfdi.receptor_nombre,
        fecha: cfdi.fecha_emision,
        moneda: cfdi.moneda,
        source: 'cfdi'
      });
      
      // Add to section total
      section.total += montoMXN;
    });
    
    // ── PASO 3: Inyectar proyecciones CxC/CxP por semana y categoría ──
    // El backend genera el label "S23" contando semanas desde el lunes anterior al 1-ene del año
    // en curso (= FISCAL_YEAR_START = Dec 29, 2025). Se usa la misma ancla para convertir el
    // label a fecha y encontrar la semana correcta en el modelo.
    // Semanas futuras: se inyecta el monto completo. Semana ACTUAL: solo el remanente
    // (asignado − real ya registrado) para no duplicar. Semanas pasadas: nunca.
    if (porSemana && Object.keys(porSemana).length > 0) {
      // FISCAL_YEAR_START ya está definido arriba: new Date(2025, 11, 29) = Dec 29, 2025
      Object.entries(porSemana).forEach(([semanaLabel, semanaData]) => {
        const weekNum = parseInt(semanaLabel.replace('S', ''), 10) - 1;
        const semanaDate = new Date(FISCAL_YEAR_START.getTime() + weekNum * 7 * 24 * 60 * 60 * 1000);

        const weekIdx = weeks.findIndex(w => semanaDate >= w.weekStart && semanaDate < w.weekEnd);
        if (weekIdx === -1) return;

        const week = weeks[weekIdx];
        if (week.isPast) return;

        // Semana ACTUAL: inyectar solo el REMANENTE = asignado − lo ya registrado como
        // real en la semana (cobranza/pagos), para no duplicar contra los datos reales.
        // El remanente se reparte proporcionalmente entre categorías e ítems
        // (factor = remanente / asignado). Semanas futuras: factor 1 (se inyecta completo).
        let factorCxc = 1, factorCxp = 1;
        if (week.isCurrent) {
          const cxcAsignado = semanaData.cxc || 0;
          const cxpAsignado = semanaData.cxp || 0;
          const remCxc = Math.max(0, cxcAsignado - week.ingresos.total);
          const remCxp = Math.max(0, cxpAsignado - week.egresos.total);
          factorCxc = cxcAsignado > 0 ? remCxc / cxcAsignado : 0;
          factorCxp = cxpAsignado > 0 ? remCxp / cxpAsignado : 0;
          if (factorCxc <= 0 && factorCxp <= 0) return;
        }
        const sufijoCxc = factorCxc < 0.999 ? ' (remanente)' : '';
        const sufijoCxp = factorCxp < 0.999 ? ' (remanente)' : '';

        const byCat = semanaData.byCategory || {};
        Object.entries(byCat).forEach(([catName, montos]) => {
          // CxC → ingresos
          if ((montos.cxc || 0) * factorCxc > 0.005) {
            const monto = montos.cxc * factorCxc;
            week.ingresos.total += monto;
            if (!week.ingresos.byCategory[catName]) {
              week.ingresos.byCategory[catName] = { total: 0, bySubcategory: {}, items: [] };
            }
            week.ingresos.byCategory[catName].total += monto;
            if (!week.ingresos.byCategory[catName].bySubcategory['CxC']) {
              week.ingresos.byCategory[catName].bySubcategory['CxC'] = { total: 0, items: [] };
            }
            week.ingresos.byCategory[catName].bySubcategory['CxC'].total += monto;
            // Un ítem por beneficiario real (del backend); fallback a ítem agrupado si no hay detalle
            const cxcItems = (montos.items || []).filter(it => it.tipo === 'cxc');
            if (cxcItems.length > 0) {
              cxcItems.forEach(it => {
                const newItem = {
                  id: `cxc-${it.nombre}-${semanaLabel}`,
                  monto: it.monto * factorCxc,
                  concepto: `CxC - ${it.nombre}${sufijoCxc}`,
                  beneficiario: it.nombre,
                  source: 'cxc_proyeccion'
                };
                week.ingresos.byCategory[catName].items.push(newItem);
                week.ingresos.byCategory[catName].bySubcategory['CxC'].items.push(newItem);
              });
            } else {
              const newItem = {
                id: `cxc-proy-${semanaLabel}-${catName}`,
                monto,
                concepto: `CxC Proyectado${sufijoCxc}`,
                beneficiario: catName,
                source: 'cxc_proyeccion'
              };
              week.ingresos.byCategory[catName].items.push(newItem);
              week.ingresos.byCategory[catName].bySubcategory['CxC'].items.push(newItem);
            }
          }
          // CxP → egresos
          if ((montos.cxp || 0) * factorCxp > 0.005) {
            const monto = montos.cxp * factorCxp;
            week.egresos.total += monto;
            if (!week.egresos.byCategory[catName]) {
              week.egresos.byCategory[catName] = { total: 0, bySubcategory: {}, items: [] };
            }
            week.egresos.byCategory[catName].total += monto;
            if (!week.egresos.byCategory[catName].bySubcategory['CxP']) {
              week.egresos.byCategory[catName].bySubcategory['CxP'] = { total: 0, items: [] };
            }
            week.egresos.byCategory[catName].bySubcategory['CxP'].total += monto;
            // Un ítem por beneficiario real (del backend); fallback a ítem agrupado si no hay detalle
            const cxpItems = (montos.items || []).filter(it => it.tipo === 'cxp');
            if (cxpItems.length > 0) {
              cxpItems.forEach(it => {
                const newItem = {
                  id: `cxp-${it.nombre}-${semanaLabel}`,
                  monto: it.monto * factorCxp,
                  concepto: `CxP - ${it.nombre}${sufijoCxp}`,
                  beneficiario: it.nombre,
                  source: 'cxp_proyeccion'
                };
                week.egresos.byCategory[catName].items.push(newItem);
                week.egresos.byCategory[catName].bySubcategory['CxP'].items.push(newItem);
              });
            } else {
              const newItem = {
                id: `cxp-proy-${semanaLabel}-${catName}`,
                monto,
                concepto: `CxP Proyectado${sufijoCxp}`,
                beneficiario: catName,
                source: 'cxp_proyeccion'
              };
              week.egresos.byCategory[catName].items.push(newItem);
              week.egresos.byCategory[catName].bySubcategory['CxP'].items.push(newItem);
            }
          }
        });
      });
    }

    return weeks;
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

  // Derive unique clientes and proveedores from allPayments
  // (customers/vendors collections are empty — Contalink stores names in payments.beneficiario)
  const paymentClientes = React.useMemo(() => {
    const map = {};
    allPayments.forEach(p => {
      if ((p.estatus !== 'completado' && p.status !== 'pagado') || p.tipo !== 'cobro') return;
      const nombre = p.beneficiario || 'Sin asignar';
      if (!map[nombre]) map[nombre] = { id: nombre, nombre, rfc: '', total: 0, count: 0 };
      map[nombre].total += p.monto || 0;
      map[nombre].count += 1;
    });
    return Object.values(map).sort((a, b) => b.total - a.total);
  }, [allPayments]);

  const paymentProveedores = React.useMemo(() => {
    const map = {};
    allPayments.forEach(p => {
      if ((p.estatus !== 'completado' && p.status !== 'pagado') || p.tipo !== 'pago') return;
      const nombre = p.beneficiario || 'Sin asignar';
      if (!map[nombre]) map[nombre] = { id: nombre, nombre, rfc: '', total: 0, count: 0 };
      map[nombre].total += p.monto || 0;
      map[nombre].count += 1;
    });
    return Object.values(map).sort((a, b) => b.total - a.total);
  }, [allPayments]);

  // Get payments for selected party (cfdis collection is empty; data lives in allPayments)
  const getPartyCfdis = () => {
    if (!selectedParty) return [];
    return allPayments.filter(p => {
      if (p.estatus !== 'completado' && p.status !== 'pagado') return false;
      if (selectedPartyType === 'customer') {
        if (p.tipo !== 'cobro') return false;
        return p.beneficiario === selectedParty || p.customer_id === selectedParty;
      } else if (selectedPartyType === 'vendor') {
        if (p.tipo !== 'pago') return false;
        return p.beneficiario === selectedParty || p.vendor_id === selectedParty;
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
      const weekCustomIng = customConcepts.filter(c => c.tipo === 'ingreso' && (c.semana === idx + 1 || c.recurrente));
      const weekCustomEgr = customConcepts.filter(c => c.tipo === 'egreso' && (c.semana === idx + 1 || c.recurrente));

      const customIngresos = weekCustomIng.reduce((sum, c) => sum + c.monto, 0);
      const customEgresos  = weekCustomEgr.reduce((sum, c) => sum + c.monto, 0);

      // Enriquecer byCategory con custom concepts como ítems sintéticos,
      // igual que PASO 3 hace con CxC/CxP — así los tres niveles suman lo mismo.
      const ingByCategory = { ...week.ingresos.byCategory };
      weekCustomIng.forEach(c => {
        ingByCategory[c.nombre] = {
          total:         (ingByCategory[c.nombre]?.total || 0) + c.monto,
          bySubcategory: { ...(ingByCategory[c.nombre]?.bySubcategory || {}) },
          items: [
            ...(ingByCategory[c.nombre]?.items || []),
            { id: `custom-ing-${c.id || c.nombre}-${idx}`, monto: c.monto, concepto: c.nombre, beneficiario: c.nombre, source: 'custom_concept' }
          ]
        };
      });

      const egrByCategory = { ...week.egresos.byCategory };
      weekCustomEgr.forEach(c => {
        egrByCategory[c.nombre] = {
          total:         (egrByCategory[c.nombre]?.total || 0) + c.monto,
          bySubcategory: { ...(egrByCategory[c.nombre]?.bySubcategory || {}) },
          items: [
            ...(egrByCategory[c.nombre]?.items || []),
            { id: `custom-egr-${c.id || c.nombre}-${idx}`, monto: c.monto, concepto: c.nombre, beneficiario: c.nombre, source: 'custom_concept' }
          ]
        };
      });

      const compraUSD = week.compraUSD || 0;
      const ventaUSD  = week.ventaUSD  || 0;
      const totalIngresos = (week.ingresos.total || 0) + customIngresos;
      const totalEgresos  = (week.egresos.total  || 0) + customEgresos;
      const flujoNetoOperativo = totalIngresos - totalEgresos;
      const flujoDivisas = ventaUSD - compraUSD;
      const flujoNeto    = flujoNetoOperativo + flujoDivisas;
      const saldoFinal   = saldoInicial + flujoNeto;

      totals.push({
        ...week,
        ingresos: { ...week.ingresos, byCategory: ingByCategory, total: totalIngresos, custom: customIngresos },
        egresos:  { ...week.egresos,  byCategory: egrByCategory, total: totalEgresos,  custom: customEgresos  },
        compraUSD, ventaUSD, flujoDivisas, saldoInicial, flujoNeto, saldoFinal
      });

      saldoInicial = saldoFinal;
    });

    return totals;
  };

  // =====================================================================
  // CÁLCULO DE KPIs "GRADO CFO"
  // Recibe `totals` = displayedTotals (semanas visibles según filtro activo).
  // =====================================================================
  const calculateCFOKPIs = (totals) => {
    if (!totals || totals.length === 0) return null;

    // Clasificar semanas: real/actual = datos históricos confirmados; proyectado = CxC/CxP futuros
    const semanasReales      = totals.filter(w => w.dataType === 'real' || w.dataType === 'actual');
    const semanasProyectadas = totals.filter(w => w.dataType === 'proyectado');

    // ─── 1. NET BURN RATE ────────────────────────────────────────────────────
    // Promedio semanal de caja neta generada (+) o consumida (−) por el negocio.
    // Fórmula: BurnRate = Σ(FlujoNeto_i) / N
    //   FlujoNeto_i = Ingresos_i − Egresos_i + (VentaUSD_i − CompraUSD_i)
    //   N = número de semanas del tipo analizado (reales o proyectadas)
    // Se separa en "real" (pagos confirmados) y "proyectado" (CxC/CxP futuros)
    // para detectar cambios de tendencia entre el pasado y el pronóstico.
    // Interpretación: positivo = saludable; negativo = consumo de reservas (alerta).
    const burnRateReal = semanasReales.length > 0
      ? semanasReales.reduce((sum, w) => sum + w.flujoNeto, 0) / semanasReales.length
      : 0;
    const burnRateProyectado = semanasProyectadas.length > 0
      ? semanasProyectadas.reduce((sum, w) => sum + w.flujoNeto, 0) / semanasProyectadas.length
      : 0;

    // ─── 2. TOTALES REALES Y PROYECTADOS ─────────────────────────────────────
    // Suma directa de ingresos/egresos de las semanas de cada tipo.
    const totalIngresosReales      = semanasReales.reduce((sum, w) => sum + w.ingresos.total, 0);
    const totalEgresosReales       = semanasReales.reduce((sum, w) => sum + w.egresos.total,  0);
    const totalFlujoNetoReal       = semanasReales.reduce((sum, w) => sum + w.flujoNeto, 0);
    const totalIngresosProyectados = semanasProyectadas.reduce((sum, w) => sum + w.ingresos.total, 0);
    const totalEgresosProyectados  = semanasProyectadas.reduce((sum, w) => sum + w.egresos.total,  0);
    const totalFlujoNetoProyectado = semanasProyectadas.reduce((sum, w) => sum + w.flujoNeto, 0);

    // Promedios semanales proyectados (utilizados en comparativas)
    const promedioIngresosSemanal = totalIngresosProyectados / Math.max(semanasProyectadas.length, 1);
    const promedioEgresosSemanal  = totalEgresosProyectados  / Math.max(semanasProyectadas.length, 1);

    // ─── 3. CASH GAP ANALYSIS ────────────────────────────────────────────────
    // Compara el saldo proyectado de cada semana contra el umbral mínimo de operación.
    // Fórmula: Gap_i = SaldoFinal_i − UmbralMínimoOperativo
    //   "Semana en riesgo" = semana donde SaldoFinal_i < UmbralMínimoOperativo
    // UmbralMínimoOperativo: configurable en Ajustes (default: $500,000 MXN).
    //   Representa la caja mínima para cubrir gastos operativos del período.
    // Semana crítica = semana con el saldo final más bajo (mayor vulnerabilidad).
    // Semáforo: 0 en riesgo = cómodo; 1-2 = atención; >2 = intervención urgente.
    const cashGapByWeek = totals.map(w => ({
      semana:    w.displayLabel || w.label,
      saldoFinal: w.saldoFinal,
      gap:        w.saldoFinal - umbralMinimoCaja,
      enRiesgo:   w.saldoFinal < umbralMinimoCaja,
    }));
    const semanasEnRiesgo = cashGapByWeek.filter(w => w.enRiesgo);
    const semanaCritica   = cashGapByWeek.reduce(
      (min, w) => w.saldoFinal < min.saldoFinal ? w : min,
      cashGapByWeek[0] || { saldoFinal: 0, semana: 'N/A' }
    );

    // ─── 4. FLUJO DE CAJA ACUMULADO ──────────────────────────────────────────
    // Acumula el flujo neto semana a semana, separando la curva real de la proyectada.
    // La curva proyectada parte del último valor real acumulado (continuidad).
    let acumuladoReal       = 0;
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

    // ─── 5. VOLATILIDAD DEL FLUJO ────────────────────────────────────────────
    // Mide la irregularidad del flujo neto semanal con desviación estándar poblacional.
    // Fórmula σ: √( Σ(FlujoNeto_i − μ)² / N )   μ = BurnRateReal, N = semanas reales
    // Coeficiente de Variación (CV) normaliza σ para comparar períodos distintos:
    //   CV = (σ / |BurnRateReal|) × 100%
    // Umbrales: CV < 25% = flujo estable (bajo riesgo operativo)
    //           CV 25-50% = volatilidad moderada (monitorear de cerca)
    //           CV > 50%  = alta volatilidad (riesgo de déficit inesperado)
    // Solo usa semanas reales para evitar distorsión por datos proyectados.
    let volatilidad = 0;
    if (semanasReales.length > 1) {
      const mediaFlujo    = totalFlujoNetoReal / semanasReales.length;
      const sumaCuadrados = semanasReales.reduce((sum, w) => sum + Math.pow(w.flujoNeto - mediaFlujo, 2), 0);
      volatilidad         = Math.sqrt(sumaCuadrados / semanasReales.length);
    }
    const coeficienteVariacion = burnRateReal !== 0 ? (volatilidad / Math.abs(burnRateReal)) * 100 : 0;

    // ─── 6. RUNWAY ───────────────────────────────────────────────────────────
    // Semanas de operación disponibles con el saldo actual sin ingresos adicionales.
    // Fórmula: Runway = SaldoActual / EgresoPromedioSemanal
    //   SaldoActual = saldoFinal de la semana dataType==='actual' (o primera semana visible)
    //   EgresoPromedio = (ΣEgresosReales + ΣEgresosProyectados) / TotalSemanasVisibles
    // Umbrales: ≥16 semanas = posición cómoda; 8-15 = atención; <8 = alerta crítica.
    const saldoActual    = totals.find(w => w.dataType === 'actual')?.saldoFinal || totals[0]?.saldoFinal || 0;
    const egresoPromedio = (totalEgresosReales + totalEgresosProyectados) / Math.max(totals.length, 1);
    const runway         = egresoPromedio > 0 ? Math.floor(saldoActual / egresoPromedio) : 999;

    // ─── 7. RATIO COBRANZA VS PAGOS ──────────────────────────────────────────
    // Mide la autosuficiencia operativa: ¿cobra la empresa más de lo que paga?
    // Fórmula: Ratio = IngresosReales / EgresosReales (solo semanas reales confirmadas)
    // Ratio > 1.0 = autosuficiente; = 1.0 = equilibrio; < 1.0 = déficit (consume reservas).
    const ratioCobranzaPagos = totalEgresosReales > 0
      ? totalIngresosReales / totalEgresosReales
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

  // =====================================================================
  // PREPARAR DATOS PARA GRÁFICOS
  // =====================================================================
  const prepareChartData = (totals) => {
    if (!totals || totals.length === 0) return [];
    
    let acumuladoReal = 0;
    let acumuladoProyectado = 0;
    
    return totals.map((week, idx) => {
      const ingresosMXN = convertToCurrency(week.ingresos.total || 0);
      const egresosMXN = convertToCurrency(week.egresos.total || 0);
      const flujoNeto = convertToCurrency(week.flujoNeto || 0);
      const saldoFinal = convertToCurrency(week.saldoFinal || 0);
      const umbral = convertToCurrency(umbralMinimoCaja);
      
      // Calcular acumulados
      if (week.dataType === 'real' || week.dataType === 'actual') {
        acumuladoReal += flujoNeto;
      } else {
        acumuladoProyectado += flujoNeto;
      }
      
      return {
        semana: week.label,
        fecha: week.dateLabel,
        tipo: week.dataType,
        ingresos: ingresosMXN,
        egresos: egresosMXN,
        flujoNeto: flujoNeto,
        saldoFinal: saldoFinal,
        umbralMinimo: umbral,
        cashGap: saldoFinal - umbral,
        acumuladoReal: week.dataType === 'real' || week.dataType === 'actual' ? acumuladoReal : null,
        acumuladoProyectado: acumuladoReal + acumuladoProyectado,
        // For area chart fill
        flujoNetoPositivo: flujoNeto >= 0 ? flujoNeto : 0,
        flujoNetoNegativo: flujoNeto < 0 ? flujoNeto : 0
      };
    });
  };

  // =====================================================================
  // EXPORTAR A PDF
  // =====================================================================
  const exportToPDF = async () => {
    setExportingPdf(true);
    toast.info('Generando PDF, por favor espere...');

    try {
      await new Promise(resolve => setTimeout(resolve, 500));

      const element = document.getElementById('cashflow-report-container');
      if (!element) {
        toast.error('No se encontró el contenedor del reporte');
        return;
      }

      const canvas = await html2canvas(element, {
        scale: 1.5,
        useCORS: true,
        logging: false,
        allowTaint: true,
        backgroundColor: '#ffffff',
      });

      const pdf = new jsPDF({ orientation: 'landscape', unit: 'mm', format: 'a3', compress: true });
      const W = pdf.internal.pageSize.getWidth();
      const H = pdf.internal.pageSize.getHeight() - 10;

      const imgData   = canvas.toDataURL('image/png');
      const imgWidth  = W;
      const imgHeight = (canvas.height * W) / canvas.width;

      if (imgHeight <= H) {
        pdf.addImage(imgData, 'PNG', 0, 0, imgWidth, imgHeight);
      } else {
        let yOffset = 0;
        let pageNum = 1;
        while (yOffset < imgHeight) {
          if (pageNum > 1) pdf.addPage();
          pdf.addImage(imgData, 'PNG', 0, -yOffset, imgWidth, imgHeight);
          yOffset += H;
          pageNum++;
        }
      }

      const totalPages = pdf.internal.getNumberOfPages();
      const empresa    = companyConfig?.nombre || 'TaxnFin';
      const fecha      = format(new Date(), "dd 'de' MMMM yyyy, HH:mm", { locale: es });

      for (let i = 1; i <= totalPages; i++) {
        pdf.setPage(i);
        pdf.setDrawColor(180, 180, 180);
        pdf.setLineWidth(0.3);
        pdf.line(8, H + 2, W - 8, H + 2);

        pdf.setFont('helvetica', 'bold');
        pdf.setFontSize(7);
        pdf.setTextColor(15, 23, 42);
        pdf.text('TaxnFin', 8, H + 8);

        pdf.setFont('helvetica', 'normal');
        pdf.setFontSize(7);
        pdf.setTextColor(100, 116, 139);
        pdf.text(
          `${empresa} · Proyección de Flujo de Efectivo · 18 Semanas Rolling | ${fecha}`,
          W / 2, H + 8, { align: 'center' }
        );

        pdf.setFont('helvetica', 'bold');
        pdf.setFontSize(7);
        pdf.setTextColor(100, 116, 139);
        pdf.text(`${i} / ${totalPages}`, W - 8, H + 8, { align: 'right' });
      }

      const filename = `TaxnFin_FlujoCaja_${empresa.replace(/\s/g, '_')}_${format(new Date(), 'yyyyMMdd')}.pdf`;
      pdf.save(filename);
      toast.success('PDF generado correctamente');
    } catch (error) {
      console.error('PDF export error:', error);
      toast.error('Error al generar el PDF: ' + (error?.message || 'Error desconocido'));
    } finally {
      setExportingPdf(false);
    }
  };

  // =====================================================================
  // DRILL-DOWN: Abrir detalle de una celda
  // =====================================================================
  const handleCellClick = (weekIdx, tipo, categoryName, subcategoryName = null) => {
    const week = weeklyData[weekIdx];
    if (!week) return;
    
    const section = tipo === 'ingreso' ? week.ingresos : week.egresos;
    const category = section.byCategory[categoryName];
    
    if (!category) return;
    
    let items = [];
    let total = 0;
    
    if (subcategoryName) {
      // Drill-down to subcategory level
      const subcategory = category.bySubcategory?.[subcategoryName];
      if (subcategory) {
        items = subcategory.items || [];
        total = subcategory.total || 0;
      }
    } else {
      // Drill-down to category level
      items = category.items || [];
      total = category.total || 0;
    }
    
    // Enrich items with full details from payments, CFDIs, and reconciliations
    const enrichedItems = items.map(item => {
      const payment = allPayments.find(p => p.id === item.id);
      const cfdi = cfdis.find(c => c.uuid === item.uuid || c.id === item.cfdiId);
      const bankTxn = payment?.bank_transaction_id 
        ? bankTransactions.find(t => t.id === payment.bank_transaction_id)
        : null;
      const reconciliation = bankTxn 
        ? reconciliations.find(r => r.bank_transaction_id === bankTxn.id)
        : null;
      
      // Get bank account info
      const bankAccountId = item.bankAccountId || payment?.bank_account_id;
      const bankAccount = bankAccountId ? bankAccounts.find(b => b.id === bankAccountId) : null;
      
      // Get vendor/customer info - prioritize item's own data first
      let tercero = '';
      let terceroTipo = '';
      
      // First try: Use item's direct emisor/receptor data (from CFDI processing)
      if (tipo === 'ingreso') {
        tercero = item.receptor || item.beneficiario || '';
        terceroTipo = 'cliente';
      } else {
        tercero = item.emisor || item.beneficiario || '';
        terceroTipo = 'proveedor';
      }
      
      // Second try: Get from payment's vendor/customer
      if (!tercero && payment?.vendor_id) {
        const vendor = vendors.find(v => v.id === payment.vendor_id);
        tercero = vendor?.nombre || payment.beneficiario || '';
        terceroTipo = 'proveedor';
      } else if (!tercero && payment?.customer_id) {
        const customer = customers.find(c => c.id === payment.customer_id);
        tercero = customer?.nombre || payment.beneficiario || '';
        terceroTipo = 'cliente';
      }
      
      // Third try: Get from CFDI emisor/receptor
      if (!tercero && cfdi) {
        if (tipo === 'ingreso') {
          const customer = customers.find(c => c.rfc === cfdi.receptor_rfc);
          tercero = customer?.nombre || cfdi.receptor_nombre || '';
          terceroTipo = 'cliente';
        } else {
          const vendor = vendors.find(v => v.rfc === cfdi.emisor_rfc);
          tercero = vendor?.nombre || cfdi.emisor_nombre || '';
          terceroTipo = 'proveedor';
        }
      }
      
      // Fourth try: Use beneficiario from payment
      if (!tercero && payment?.beneficiario) {
        tercero = payment.beneficiario;
        terceroTipo = tipo === 'ingreso' ? 'cliente' : 'proveedor';
      }
      
      // Fifth try: For bank fees, use bank name
      if (!tercero && bankAccount) {
        tercero = bankAccount.banco || bankAccount.nombre || 'Banco';
        terceroTipo = 'proveedor'; // Bank fees are always providers
      }
      
      // Sixth try: Extract from concepto if it's a bank fee
      if (!tercero && item.concepto) {
        const concepto = item.concepto.toLowerCase();
        if (concepto.includes('comisión') || concepto.includes('comision') || 
            concepto.includes('iva') || concepto.includes('cargo')) {
          // Use bank name from bank account or default
          tercero = bankAccount?.banco || 'Cargo Bancario';
          terceroTipo = 'proveedor';
        }
      }
      
      return {
        ...item,
        paymentId: payment?.id,
        concepto: item.concepto || payment?.concepto || cfdi?.concepto || '',
        tercero: tercero || 'Sin asignar',
        terceroTipo: terceroTipo || (tipo === 'ingreso' ? 'cliente' : 'proveedor'),
        uuid: item.uuid || cfdi?.uuid || '',
        folio: cfdi?.folio || '',
        fechaFactura: cfdi?.fecha_emision || payment?.fecha_pago || item.fecha,
        montoOriginal: payment?.monto || cfdi?.total || item.monto,
        moneda: payment?.moneda || cfdi?.moneda || item.moneda || 'MXN',
        // Bank transaction info
        bankTxnId: bankTxn?.id,
        bankTxnDescripcion: bankTxn?.descripcion,
        bankTxnFecha: bankTxn?.fecha,
        bankTxnMonto: bankTxn?.monto,
        // Bank account info
        bankAccountName: bankAccount?.banco || bankAccount?.nombre || '',
        // Reconciliation status
        conciliado: !!reconciliation,
        reconciliacionId: reconciliation?.id,
        tipoConciliacion: reconciliation?.tipo_conciliacion,
        // Source
        source: item.source
      };
    });
    
    setDrillDownData({
      weekNum: weekIdx + 1,
      weekLabel: week.displayLabel || week.label || `S${weekIdx + 1}`,
      dateLabel: week.dateLabel || '',
      dataType: week.dataType,
      tipo,
      categoryName,
      subcategoryName,
      items: enrichedItems,
      total
    });
    setDrillDownOpen(true);
  };

  // =====================================================================
  // VISTA POR PROVEEDOR/CLIENTE: Procesar datos agrupados por tercero
  // =====================================================================
  const processDataByParty = (sourceWeeks = weeklyData) => {
    // Create a map: { terceroId: { nombre, tipo, weeks: { weekIdx: { ingresos, egresos } } } }
    const partyMap = {};

    sourceWeeks.forEach((week, weekIdx) => {
      // Process ingresos
      Object.entries(week.ingresos.byCategory).forEach(([catName, catData]) => {
        (catData.items || []).forEach(item => {
          const payment = allPayments.find(p => p.id === item.id);
          let terceroId = 'sin-asignar';
          let terceroNombre = 'Sin Asignar';
          let terceroTipo = 'cliente';
          
          if (payment?.customer_id) {
            const customer = customers.find(c => c.id === payment.customer_id);
            if (customer) {
              terceroId = customer.id;
              terceroNombre = customer.nombre;
              terceroTipo = 'cliente';
            }
          }
          // Try to find customer by RFC from CFDI
          if (terceroId === 'sin-asignar') {
            const cfdi = cfdis.find(c => c.uuid === item.uuid);
            if (cfdi?.receptor_rfc) {
              const customer = customers.find(c => c.rfc === cfdi.receptor_rfc);
              if (customer) {
                terceroId = customer.id;
                terceroNombre = customer.nombre;
                terceroTipo = 'cliente';
              } else if (cfdi?.receptor_nombre) {
                // Use CFDI receptor name directly (Contalink sync data)
                terceroId = cfdi.receptor_rfc;
                terceroNombre = cfdi.receptor_nombre;
                terceroTipo = 'cliente';
              }
            } else if (cfdi?.receptor_nombre) {
              terceroId = cfdi.receptor_nombre;
              terceroNombre = cfdi.receptor_nombre;
              terceroTipo = 'cliente';
            }
          }
          // Last fallback: use payment beneficiario (set by Contalink sync)
          if (terceroId === 'sin-asignar' && payment?.beneficiario) {
            terceroId = payment.beneficiario;
            terceroNombre = payment.beneficiario;
            terceroTipo = 'cliente';
          }
          // Fallback para ítems sintéticos (CxC/CxP proyectados, custom concepts):
          // item.beneficiario ya trae el nombre real del cliente/proveedor
          if (terceroId === 'sin-asignar' && item.beneficiario) {
            terceroId = item.beneficiario;
            terceroNombre = item.beneficiario;
            terceroTipo = 'cliente';
          }

          if (!partyMap[terceroId]) {
            partyMap[terceroId] = {
              id: terceroId,
              nombre: terceroNombre,
              tipo: terceroTipo,
              weeks: {}
            };
          }

          if (!partyMap[terceroId].weeks[weekIdx]) {
            partyMap[terceroId].weeks[weekIdx] = { ingresos: 0, egresos: 0, items: [] };
          }

          partyMap[terceroId].weeks[weekIdx].ingresos += item.monto || 0;
          partyMap[terceroId].weeks[weekIdx].items.push({ ...item, tipo: 'ingreso' });
        });
      });

      // Process egresos
      Object.entries(week.egresos.byCategory).forEach(([catName, catData]) => {
        (catData.items || []).forEach(item => {
          const payment = allPayments.find(p => p.id === item.id);
          let terceroId = 'sin-asignar';
          let terceroNombre = 'Sin Asignar';
          let terceroTipo = 'proveedor';
          
          if (payment?.vendor_id) {
            const vendor = vendors.find(v => v.id === payment.vendor_id);
            if (vendor) {
              terceroId = vendor.id;
              terceroNombre = vendor.nombre;
              terceroTipo = 'proveedor';
            }
          }
          // Try to find vendor by RFC from CFDI
          if (terceroId === 'sin-asignar') {
            const cfdi = cfdis.find(c => c.uuid === item.uuid);
            if (cfdi?.emisor_rfc) {
              const vendor = vendors.find(v => v.rfc === cfdi.emisor_rfc);
              if (vendor) {
                terceroId = vendor.id;
                terceroNombre = vendor.nombre;
                terceroTipo = 'proveedor';
              } else if (cfdi?.emisor_nombre) {
                // Use CFDI emisor name directly (Contalink sync data)
                terceroId = cfdi.emisor_rfc;
                terceroNombre = cfdi.emisor_nombre;
                terceroTipo = 'proveedor';
              }
            } else if (cfdi?.emisor_nombre) {
              terceroId = cfdi.emisor_nombre;
              terceroNombre = cfdi.emisor_nombre;
              terceroTipo = 'proveedor';
            }
          }
          // Last fallback: use payment beneficiario (set by Contalink sync)
          if (terceroId === 'sin-asignar' && payment?.beneficiario) {
            terceroId = payment.beneficiario;
            terceroNombre = payment.beneficiario;
            terceroTipo = 'proveedor';
          }
          // Fallback para ítems sintéticos (CxC/CxP proyectados, custom concepts):
          // item.beneficiario ya trae el nombre real del cliente/proveedor
          if (terceroId === 'sin-asignar' && item.beneficiario) {
            terceroId = item.beneficiario;
            terceroNombre = item.beneficiario;
            terceroTipo = 'proveedor';
          }

          if (!partyMap[terceroId]) {
            partyMap[terceroId] = {
              id: terceroId,
              nombre: terceroNombre,
              tipo: terceroTipo,
              weeks: {}
            };
          }
          
          if (!partyMap[terceroId].weeks[weekIdx]) {
            partyMap[terceroId].weeks[weekIdx] = { ingresos: 0, egresos: 0, items: [] };
          }
          
          partyMap[terceroId].weeks[weekIdx].egresos += item.monto || 0;
          partyMap[terceroId].weeks[weekIdx].items.push({ ...item, tipo: 'egreso' });
        });
      });
    });
    
    return Object.values(partyMap);
  };

  // Filter party data based on current filters
  const filterPartyData = (partyData) => {
    return partyData.filter(party => {
      // Filter by search term
      if (partyFilters.searchTerm.trim() !== '') {
        const searchLower = partyFilters.searchTerm.toLowerCase();
        if (!party.nombre.toLowerCase().includes(searchLower)) {
          return false;
        }
      }
      
      // Filter by tipo tercero
      if (partyFilters.tipoTercero !== 'todos') {
        if (party.tipo !== partyFilters.tipoTercero) {
          return false;
        }
      }
      
      // Filter by saldo tipo
      if (partyFilters.saldoTipo !== 'todos') {
        const totalIngresos = Object.values(party.weeks).reduce((s, w) => s + w.ingresos, 0);
        const totalEgresos = Object.values(party.weeks).reduce((s, w) => s + w.egresos, 0);
        const netTotal = totalIngresos - totalEgresos;
        
        if (partyFilters.saldoTipo === 'positivo' && netTotal <= 0) {
          return false;
        }
        if (partyFilters.saldoTipo === 'negativo' && netTotal >= 0) {
          return false;
        }
      }
      
      return true;
    });
  };

  // Check if party filters are active
  const hasPartyFiltersActive = () => {
    return partyFilters.searchTerm.trim() !== '' || 
           partyFilters.tipoTercero !== 'todos' || 
           partyFilters.saldoTipo !== 'todos';
  };

  // Reset party filters
  const resetPartyFilters = () => {
    setPartyFilters({
      searchTerm: '',
      tipoTercero: 'todos',
      saldoTipo: 'todos'
    });
  };

  // Export party data (filtered or all)
  const exportPartyReport = () => {
    const partyData = processDataByParty(calculateRunningTotals());
    const filteredParties = filterPartyData(partyData);
    
    if (filteredParties.length === 0) {
      toast.error('No hay datos para exportar');
      return;
    }
    
    const reportData = [];
    
    filteredParties.forEach(party => {
      // Calculate totals for this party
      const totalIngresos = Object.values(party.weeks).reduce((s, w) => s + w.ingresos, 0);
      const totalEgresos = Object.values(party.weeks).reduce((s, w) => s + w.egresos, 0);
      const netTotal = totalIngresos - totalEgresos;
      
      // Create a row for each week with data
      weeklyData.forEach((week, weekIdx) => {
        const weekData = party.weeks[weekIdx];
        if (!weekData || (weekData.ingresos === 0 && weekData.egresos === 0)) return;
        
        const weekLabel = week.displayLabel || `S${weekIdx + 1}`;
        const dataType = week.dataType === 'real' ? 'Real' : week.dataType === 'actual' ? 'Actual' : 'Proyectado';

        reportData.push({
          'Proveedor/Cliente': party.nombre,
          'Tipo Tercero': party.tipo === 'cliente' ? 'Cliente' : 'Proveedor',
          'Semana': weekLabel,
          'Fecha': week.dateLabel,
          'Tipo Dato': dataType,
          'Ingresos': weekData.ingresos,
          'Egresos': weekData.egresos,
          'Neto Semana': weekData.ingresos - weekData.egresos,
          'Total Ingresos': totalIngresos,
          'Total Egresos': totalEgresos,
          'Saldo Neto Total': netTotal
        });
      });
    });
    
    if (reportData.length === 0) {
      toast.error('No hay movimientos para exportar');
      return;
    }
    
    const isFiltered = hasPartyFiltersActive();
    const filename = isFiltered ? 'Terceros_Filtrado' : 'Terceros_18_Semanas';
    
    const success = exportToExcel(reportData, filename, 'Por Tercero');
    if (success) {
      toast.success(isFiltered ? 'Terceros filtrados exportados a Excel' : 'Datos de terceros exportados a Excel');
    } else {
      toast.error('Error al exportar');
    }
  };

  // =====================================================================
  // EXPORTAR REPORTE DETALLADO
  // =====================================================================
  const exportDetailReport = () => {
    const reportData = [];
    
    weeklyData.forEach((week, weekIdx) => {
      const weekLabel = week.displayLabel || `S${weekIdx + 1}`;
      const dataType = week.dataType === 'real' ? 'Real' : week.dataType === 'actual' ? 'Actual' : 'Proyectado';

      // Process ingresos
      Object.entries(week.ingresos.byCategory).forEach(([catName, catData]) => {
        (catData.items || []).forEach(item => {
          const payment = allPayments.find(p => p.id === item.id);
          const cfdi = cfdis.find(c => c.uuid === item.uuid);
          const bankTxn = payment?.bank_transaction_id ? bankTransactions.find(t => t.id === payment.bank_transaction_id) : null;
          
          let tercero = item.beneficiario || payment?.beneficiario || '';
          if (payment?.customer_id) {
            const customer = customers.find(c => c.id === payment.customer_id);
            tercero = customer?.nombre || tercero;
          }
          
          reportData.push({
            'Semana': weekLabel,
            'Fecha': week.dateLabel,
            'Tipo Dato': dataType,
            'Categoría': catName,
            'Tipo': 'Ingreso',
            'Cliente/Proveedor': tercero,
            'UUID': item.uuid || cfdi?.uuid || '',
            'Folio': cfdi?.folio || '',
            'Fecha Factura': cfdi?.fecha_emision ? format(new Date(cfdi.fecha_emision), 'dd/MM/yyyy') : '',
            'Monto': item.monto,
            'Moneda': payment?.moneda || cfdi?.moneda || 'MXN',
            'Monto MXN': item.monto,
            'Cuenta Bancaria': bankTxn?.banco || '',
            'Conciliado': bankTxn ? 'Sí' : 'No',
            'Movimiento Bancario': bankTxn?.descripcion || ''
          });
        });
      });
      
      // Process egresos
      Object.entries(week.egresos.byCategory).forEach(([catName, catData]) => {
        (catData.items || []).forEach(item => {
          const payment = allPayments.find(p => p.id === item.id);
          const cfdi = cfdis.find(c => c.uuid === item.uuid);
          const bankTxn = payment?.bank_transaction_id ? bankTransactions.find(t => t.id === payment.bank_transaction_id) : null;
          
          let tercero = item.beneficiario || payment?.beneficiario || '';
          if (payment?.vendor_id) {
            const vendor = vendors.find(v => v.id === payment.vendor_id);
            tercero = vendor?.nombre || tercero;
          }
          
          reportData.push({
            'Semana': weekLabel,
            'Fecha': week.dateLabel,
            'Tipo Dato': dataType,
            'Categoría': catName,
            'Tipo': 'Egreso',
            'Cliente/Proveedor': tercero,
            'UUID': item.uuid || cfdi?.uuid || '',
            'Folio': cfdi?.folio || '',
            'Fecha Factura': cfdi?.fecha_emision ? format(new Date(cfdi.fecha_emision), 'dd/MM/yyyy') : '',
            'Monto': item.monto,
            'Moneda': payment?.moneda || cfdi?.moneda || 'MXN',
            'Monto MXN': item.monto,
            'Cuenta Bancaria': bankTxn?.banco || '',
            'Conciliado': bankTxn ? 'Sí' : 'No',
            'Movimiento Bancario': bankTxn?.descripcion || ''
          });
        });
      });
    });
    
    if (reportData.length === 0) {
      toast.error('No hay datos para exportar');
      return;
    }
    
    const success = exportToExcel(reportData, 'Detalle_Cashflow', 'Detalle');
    if (success) {
      toast.success('Reporte de detalle exportado a Excel');
    } else {
      toast.error('Error al exportar');
    }
  };

  // Única fuente de verdad para la vista mensual: agrega weeklyTotals por mes.
  // Garantiza que mensual === semanal para los mismos períodos.
  const buildMonthlyFromWeeks = (weekTotals) => {
    const monthMap = {};
    const todayRef = new Date();
    weekTotals.forEach(week => {
      const key = format(week.weekStart, 'yyyy-MM');
      if (!monthMap[key]) {
        const mStart = startOfMonth(week.weekStart);
        const mEnd   = addMonths(mStart, 1);
        monthMap[key] = {
          label:      format(mStart, 'MMM yyyy', { locale: es }),
          monthStart: mStart,
          monthEnd:   mEnd,
          isPast:     mEnd <= todayRef,
          isCurrent:  mStart <= todayRef && todayRef < mEnd,
          ingresos:   { total: 0, byCategory: {} },
          egresos:    { total: 0, byCategory: {} },
        };
      }
      const m = monthMap[key];
      m.ingresos.total += week.ingresos.total || 0;
      m.egresos.total  += week.egresos.total  || 0;
      Object.entries(week.ingresos.byCategory || {}).forEach(([cat, catData]) => {
        m.ingresos.byCategory[cat] = (m.ingresos.byCategory[cat] || 0) + (catData.total || 0);
      });
      Object.entries(week.egresos.byCategory || {}).forEach(([cat, catData]) => {
        m.egresos.byCategory[cat] = (m.egresos.byCategory[cat] || 0) + (catData.total || 0);
      });
    });
    return Object.values(monthMap).sort((a, b) => a.monthStart - b.monthStart);
  };

  // useCallback sin deps: función estable que siempre lee los valores más recientes via kpiStateRef
  const openKpiModal = useCallback(async (kpiKey) => {
    console.log('KPI CLICK', kpiKey);
    const { cfoKPIs: kpis, KPI_DEFS: defs, formatCurrency: fmt } = kpiStateRef.current;
    if (!kpis || !defs) {
      console.warn('[KPI Modal] kpis o defs no disponibles aún', { kpis: !!kpis, defs: !!defs });
      return;
    }
    try {
      const def = defs[kpiKey];
      const values = def.getValues(kpis, fmt);

      let status = 'neutral';
      if (kpiKey === 'burnRate') {
        status = kpis.burnRateReal >= 0 ? 'good'
               : kpis.burnRateReal >= -(kpis.promedioEgresosSemanal * 0.1) ? 'warning' : 'danger';
      } else if (kpiKey === 'cashGap') {
        status = kpis.semanasEnRiesgo.length === 0 ? 'good'
               : kpis.semanasEnRiesgo.length <= 2 ? 'warning' : 'danger';
      } else if (kpiKey === 'volatilidad') {
        status = kpis.coeficienteVariacion < 25 ? 'good'
               : kpis.coeficienteVariacion < 50 ? 'warning' : 'danger';
      } else if (kpiKey === 'operativos') {
        status = (kpis.runway >= 16 && kpis.ratioCobranzaPagos >= 1) ? 'good'
               : (kpis.runway >= 8 || kpis.ratioCobranzaPagos >= 0.8) ? 'warning' : 'danger';
      }

      setKpiModal({ open: true, name: def.name, formula: def.formula, description: def.description, values, insight: '', loading: true, status, kpiKey });

      try {
        const res = await api.post('/cashflow-kpi/insight', {
          kpi_name: def.name,
          formula: def.formula,
          description: def.description,
          values: Object.fromEntries(Object.entries(values).map(([k, v]) => [k, String(v)])),
        });
        setKpiModal(prev => ({ ...prev, insight: res.data.insight, loading: false }));
      } catch {
        setKpiModal(prev => ({ ...prev, insight: 'No se pudo obtener el análisis en este momento.', loading: false }));
      }
    } catch (err) {
      console.error('[KPI Modal] Error al abrir modal:', err);
      toast.error('Error al abrir el análisis del KPI');
    }
  }, []); // eslint-disable-line react-hooks/exhaustive-deps

  if (loading) return <div className="p-8">{t.loading}</div>;

  const weeklyTotals = calculateRunningTotals();

  // Column visibility mask — true = show this week column in the table
  // Default: hide past weeks; show current + future
  const columnVisible = weeklyTotals.map(w => {
    if (filterFechaInicio) {
      const start = new Date(filterFechaInicio + 'T00:00:00');
      if (w.weekEnd <= start) return false;
    } else {
      if (w.isPast) return false; // default: past weeks hidden
    }
    if (filterFechaFin) {
      const end = new Date(filterFechaFin + 'T23:59:59');
      if (w.weekStart > end) return false;
    }
    return true;
  });

  // Subset of weeklyTotals for TOTAL column calculations and final-saldo references
  const displayedTotals = weeklyTotals.filter((_, i) => columnVisible[i]);

  // Vista Mensual derivada SOLO de las semanas visibles (respeta el filtro de
  // rango Desde/Hasta, igual que la Vista Semanal) — misma fuente de verdad
  const monthlyData = buildMonthlyFromWeeks(displayedTotals);

  // KPIs y gráficos usan solo las semanas visibles (respetan el filtro de rango)
  const cfoKPIs = calculateCFOKPIs(displayedTotals);

  // ── RUNWAY (conservador y proyectado) — derivado de weeklyTotals ──────────
  // Usa la serie COMPLETA (no displayedTotals): el runway es una métrica absoluta
  // y el filtro default oculta las semanas pasadas, que son la base del cálculo.
  // dataType en este modelo: 'real' | 'actual' (semana en curso) | 'proyectado'.
  const runwayKPI = (() => {
    const reales = weeklyTotals.filter(w => w.dataType === 'real' || w.dataType === 'actual');

    // Paso 1: saldo base = saldo final de la última semana con datos reales
    const saldoBase = reales.length > 0
      ? reales[reales.length - 1].saldoFinal
      : (weeklyTotals[0]?.saldoInicial || 0);

    // Paso 2: net burn histórico (últimas 4 semanas reales)
    // flujoNeto = ingresos − egresos (+ flujo de divisas), el neto semanal del modelo
    const ultimas4 = reales.slice(-4);
    const avgNetBurn = ultimas4.length > 0
      ? ultimas4.reduce((s, w) => s + w.flujoNeto, 0) / ultimas4.length
      : 0;
    // Solo hay runway conservador si en promedio se consume caja (avgNetBurn < 0)
    const conservador = avgNetBurn < 0 ? saldoBase / Math.abs(avgNetBurn) : null;

    // Paso 3: runway proyectado — iterar las semanas proyectadas acumulando flujo
    const proyectadas = weeklyTotals.filter(w => w.dataType === 'proyectado');
    let saldoAcumulado = saldoBase;
    let proyectado = null;
    for (let i = 0; i < proyectadas.length; i++) {
      saldoAcumulado += proyectadas[i].flujoNeto;
      if (saldoAcumulado <= 0) { proyectado = i + 1; break; }
    }
    // proyectado === null → la caja no se agota dentro del horizonte proyectado

    return { saldoBase, avgNetBurn, conservador, proyectado, horizonte: proyectadas.length };
  })();
  const chartData = prepareChartData(displayedTotals);

  const customConceptsIngresos = customConcepts.filter(c => c.tipo === 'ingreso');
  const customConceptsEgresos = customConcepts.filter(c => c.tipo === 'egreso');
  const grandTotalIngresos = displayedTotals.reduce((sum, w) => sum + w.ingresos.total, 0);
  const grandTotalEgresos = displayedTotals.reduce((sum, w) => sum + w.egresos.total, 0);
  const grandTotalCompraUSD = displayedTotals.reduce((sum, w) => sum + (w.compraUSD || 0), 0);
  const grandTotalVentaUSD = displayedTotals.reduce((sum, w) => sum + (w.ventaUSD || 0), 0);
  const grandTotalFlujoDivisas = grandTotalVentaUSD - grandTotalCompraUSD;
  const grandTotalFlujo = grandTotalIngresos - grandTotalEgresos + grandTotalFlujoDivisas;

  // ─── KPI INSIGHT: abre modal y llama a Claude para interpretar el KPI ──────
  const KPI_DEFS = {
    burnRate: {
      name: 'Net Burn Rate',
      formula: 'BurnRate = Σ(FlujoNeto_i) / N   donde FlujoNeto = Ingresos − Egresos + Divisas',
      description: 'Promedio semanal de caja neta generada (>0) o consumida (<0) por el negocio.',
      getValues: (k) => ({
        'Burn Rate Real (promedio semanal)': k.burnRateReal,
        'Burn Rate Proyectado (promedio semanal)': k.burnRateProyectado,
        'Delta Proyectado vs Real': k.burnRateDelta,
        'Semanas reales analizadas': k.semanasRealesCount,
        'Semanas proyectadas': k.semanasProyectadasCount,
      }),
    },
    cashGap: {
      name: 'Cash Gap Analysis',
      formula: 'Gap_i = SaldoFinal_i − UmbralMínimoOperativo',
      description: 'Identifica semanas donde el saldo proyectado cae por debajo del mínimo operativo configurado.',
      getValues: (k, fmt) => ({
        'Umbral mínimo de caja': fmt(umbralMinimoCaja),
        'Semanas en riesgo (en rango visible)': k.semanasEnRiesgo.length,
        'Semana con saldo más bajo': k.semanaCritica?.semana || 'N/A',
        'Saldo en semana crítica': fmt(k.semanaCritica?.saldoFinal || 0),
      }),
    },
    volatilidad: {
      name: 'Volatilidad del Flujo',
      formula: 'σ = √(Σ(FlujoNeto_i − Media)² / N)   |   CV = σ / |BurnRateReal| × 100',
      description: 'Desviación estándar del flujo neto semanal real. CV>50% = alta volatilidad.',
      getValues: (k, fmt) => ({
        'Desviación estándar (σ)': fmt(k.volatilidad),
        'Coeficiente de variación (CV)': `${k.coeficienteVariacion.toFixed(1)}%`,
        'Burn Rate Real (media)': fmt(k.burnRateReal),
        'Nivel de riesgo': k.coeficienteVariacion > 50 ? 'Alto' : k.coeficienteVariacion > 25 ? 'Moderado' : 'Bajo',
      }),
    },
    operativos: {
      name: 'Indicadores Operativos',
      formula: 'Runway = SaldoActual / EgresoPromedioSemanal   |   Ratio = IngresoReal / EgresoReal',
      description: 'Runway: semanas de operación disponibles. Ratio cobranza/pagos: eficiencia de cobro vs pago.',
      getValues: (k, fmt) => ({
        'Runway (semanas de operación)': k.runway === 999 ? 'Sin límite' : `${k.runway} semanas`,
        'Ratio Cobranza / Pagos': k.ratioCobranzaPagos?.toFixed(2),
        'Total Ingresos Reales': fmt(k.totalIngresosReales),
        'Total Egresos Reales': fmt(k.totalEgresosReales),
        'Flujo Neto Real Total': fmt(k.totalFlujoNetoReal),
      }),
    },
  };

  // Sincronizar ref para que openKpiModal (useCallback estable) lea los valores del render actual
  kpiStateRef.current = { cfoKPIs, KPI_DEFS, formatCurrency };

  // Days of week translated
  const DIAS_SEMANA_TR = [
    { value: 0, label: t.sunday },
    { value: 1, label: t.monday },
    { value: 2, label: t.tuesday },
    { value: 3, label: t.wednesday },
    { value: 4, label: t.thursday },
    { value: 5, label: t.friday },
    { value: 6, label: t.saturday }
  ];

  return (
    <div className="p-6 space-y-6 bg-[#F8FAFC] min-h-screen" data-testid="cashflow-projections-page">
      {/* Header */}
      <div className="flex justify-between items-center">
        <div>
          <h1 className="text-3xl font-bold text-[#0F172A]" style={{fontFamily: 'Manrope'}}>
            {t.cashflowProjections}
          </h1>
          <p className="text-[#64748B]">
            {language === 'es' ? `Modelo Rolling 52 semanas | Inicio: ${DIAS_SEMANA_TR.find(d => d.value === companyConfig.inicio_semana)?.label || t.monday}` :
             language === 'en' ? `52-week Rolling Model | Start: ${DIAS_SEMANA_TR.find(d => d.value === companyConfig.inicio_semana)?.label || t.monday}` :
             `Modelo Rolling 52 semanas | Início: ${DIAS_SEMANA_TR.find(d => d.value === companyConfig.inicio_semana)?.label || t.monday}`}
            {selectedCurrency !== 'MXN' && (
              <span className="ml-2 px-2 py-0.5 bg-blue-100 text-blue-700 rounded text-sm">
                TC: 1 {selectedCurrency} = ${fxRates[selectedCurrency]?.toFixed(4) || '?'} MXN
              </span>
            )}
          </p>
          {/* Date range filter — past weeks hidden by default */}
          <div className="flex items-center gap-3 mt-2 flex-wrap">
            <div className="flex items-center gap-1.5">
              <Filter size={13} className="text-gray-400" />
              <span className="text-xs text-gray-500 font-medium">Rango de semanas:</span>
            </div>
            <div className="flex items-center gap-1.5">
              <Label className="text-xs text-gray-400">Desde</Label>
              <Input
                type="date"
                value={filterFechaInicio}
                onChange={e => setFilterFechaInicio(e.target.value)}
                className="h-7 w-36 text-xs"
              />
            </div>
            <div className="flex items-center gap-1.5">
              <Label className="text-xs text-gray-400">Hasta</Label>
              <Input
                type="date"
                value={filterFechaFin}
                onChange={e => setFilterFechaFin(e.target.value)}
                className="h-7 w-36 text-xs"
              />
            </div>
            {(filterFechaInicio || filterFechaFin) ? (
              <button
                className="text-xs text-blue-600 hover:underline"
                onClick={() => { setFilterFechaInicio(''); setFilterFechaFin(''); }}
              >
                Ver solo futuras
              </button>
            ) : null}
            <span className="text-xs text-gray-400">
              {displayedTotals.length} semana{displayedTotals.length !== 1 ? 's' : ''} visibles
              {!filterFechaInicio && ` (semanas pasadas ocultas)`}
            </span>
          </div>
        </div>
        <div className="flex gap-2">
          {/* Language Selector */}
          <Select value={language} onValueChange={setLanguage}>
            <SelectTrigger className="w-36" data-testid="language-selector">
              <Globe className="w-4 h-4 mr-2" />
              <SelectValue />
            </SelectTrigger>
            <SelectContent>
              {languages.map(lang => (
                <SelectItem key={lang.code} value={lang.code}>
                  {lang.flag} {lang.name}
                </SelectItem>
              ))}
            </SelectContent>
          </Select>
          
          {/* Config Dialog for Week Start */}
          <Dialog open={configDialogOpen} onOpenChange={setConfigDialogOpen}>
            <DialogTrigger asChild>
              <Button variant="outline" className="gap-2" data-testid="config-week-start-btn">
                <Settings size={16} />
                {t.configure}
              </Button>
            </DialogTrigger>
            <DialogContent>
              <DialogHeader>
                <DialogTitle>{t.configureProjections}</DialogTitle>
              </DialogHeader>
              <div className="space-y-4">
                <div className="space-y-2">
                  <Label>{t.weekStartDay}</Label>
                  <Select 
                    value={companyConfig.inicio_semana?.toString()} 
                    onValueChange={(v) => handleSaveWeekStart(parseInt(v))}
                  >
                    <SelectTrigger data-testid="week-start-select">
                      <SelectValue placeholder={t.selectPeriod} />
                    </SelectTrigger>
                    <SelectContent>
                      {DIAS_SEMANA_TR.map(dia => (
                        <SelectItem key={dia.value} value={dia.value.toString()}>
                          {dia.label}
                        </SelectItem>
                      ))}
                    </SelectContent>
                  </Select>
                </div>
                <div className="space-y-2 mt-4 pt-4 border-t">
                  <Label htmlFor="cashflow-start-date">
                    {language === 'es' ? 'Fecha de inicio del flujo' : language === 'pt' ? 'Data de início do fluxo' : 'Cashflow start date'}
                  </Label>
                  
                  {/* Quick preset buttons */}
                  <div className="flex flex-wrap gap-2 pb-1">
                    <Button
                      type="button"
                      variant="secondary"
                      size="sm"
                      className="h-7 text-xs"
                      data-testid="cashflow-preset-current-year"
                      onClick={() => {
                        const d = new Date(new Date().getFullYear(), 0, 1);
                        handleSaveCustomStartDate(d.toISOString().slice(0, 10));
                      }}
                    >
                      {language === 'es' ? 'Año Actual' : language === 'pt' ? 'Ano Atual' : 'Current Year'}
                    </Button>
                    <Button
                      type="button"
                      variant="secondary"
                      size="sm"
                      className="h-7 text-xs"
                      data-testid="cashflow-preset-fiscal-year"
                      title={language === 'es' ? 'Año fiscal cerrado anterior (Ene 1 año anterior)' : language === 'pt' ? 'Ano fiscal anterior fechado' : 'Previous closed fiscal year'}
                      onClick={() => {
                        const d = new Date(new Date().getFullYear() - 1, 0, 1);
                        handleSaveCustomStartDate(d.toISOString().slice(0, 10));
                      }}
                    >
                      {language === 'es' ? 'Año Fiscal' : language === 'pt' ? 'Ano Fiscal' : 'Fiscal Year'}
                    </Button>
                    <Button
                      type="button"
                      variant="secondary"
                      size="sm"
                      className="h-7 text-xs"
                      data-testid="cashflow-preset-last-6-months"
                      onClick={() => {
                        const today = new Date();
                        const d = new Date(today.getFullYear(), today.getMonth() - 6, 1);
                        handleSaveCustomStartDate(d.toISOString().slice(0, 10));
                      }}
                    >
                      {language === 'es' ? 'Últimos 6 meses' : language === 'pt' ? 'Últimos 6 meses' : 'Last 6 months'}
                    </Button>
                    <Button
                      type="button"
                      variant="secondary"
                      size="sm"
                      className="h-7 text-xs"
                      data-testid="cashflow-preset-last-12-months"
                      onClick={() => {
                        const today = new Date();
                        const d = new Date(today.getFullYear() - 1, today.getMonth(), 1);
                        handleSaveCustomStartDate(d.toISOString().slice(0, 10));
                      }}
                    >
                      {language === 'es' ? 'Últimos 12 meses' : language === 'pt' ? 'Últimos 12 meses' : 'Last 12 months'}
                    </Button>
                  </div>
                  
                  <div className="flex gap-2">
                    <Input
                      id="cashflow-start-date"
                      data-testid="cashflow-start-date-input"
                      type="date"
                      value={customStartDate}
                      onChange={(e) => handleSaveCustomStartDate(e.target.value)}
                    />
                    {customStartDate && (
                      <Button
                        type="button"
                        variant="outline"
                        size="sm"
                        data-testid="cashflow-start-date-reset"
                        onClick={() => handleSaveCustomStartDate('')}
                      >
                        {language === 'es' ? 'Auto' : language === 'pt' ? 'Auto' : 'Auto'}
                      </Button>
                    )}
                  </div>
                  <p className="text-xs text-muted-foreground">
                    {language === 'es'
                      ? 'Elige cualquier fecha (ej. 5 ene 2026). Las 18 semanas se generarán a partir del día de inicio que configuraste arriba. Deja vacío para automático.'
                      : language === 'pt'
                        ? 'Escolha qualquer data (ex. 5 jan 2026). As 18 semanas começarão a partir do dia configurado acima. Deixe em branco para automático.'
                        : 'Pick any date (e.g. Jan 5, 2026). The 18 weeks will start from the configured weekday above. Leave empty for automatic.'}
                  </p>
                </div>
                <div className="space-y-2 mt-4 pt-4 border-t">
                  <Label>{t.minimumCashThreshold}</Label>
                  <Input 
                    type="number"
                    value={umbralMinimoCaja}
                    onChange={(e) => setUmbralMinimoCaja(parseFloat(e.target.value) || 0)}
                    placeholder="Ej: 500000"
                  />
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
          
          <Button 
            variant="outline" 
            className="gap-2 border-red-200 text-red-700 hover:bg-red-50"
            onClick={exportToPDF}
            disabled={exportingPdf}
            data-testid="export-pdf-btn"
          >
            <FileDown size={16} />
            {exportingPdf ? (t.exporting || 'Generando...') : t.exportPdf}
          </Button>
          
          <Dialog open={conceptDialogOpen} onOpenChange={setConceptDialogOpen}>
            <DialogTrigger asChild>
              <Button className="gap-2 bg-[#0F172A]" data-testid="add-concept-btn">
                <Plus size={16} />
                {t.addConcept}
              </Button>
            </DialogTrigger>
            <DialogContent>
              <DialogHeader>
                <DialogTitle>{t.addManualConcept}</DialogTitle>
              </DialogHeader>
              <div className="space-y-4">
                <div className="space-y-2">
                  <Label>{t.conceptName}</Label>
                  <Input 
                    value={newConcept.nombre}
                    onChange={(e) => setNewConcept({...newConcept, nombre: e.target.value})}
                    placeholder={language === 'es' ? 'Ej: Nómina, Renta, Venta proyectada...' : 'E.g.: Payroll, Rent, Projected sale...'}
                  />
                </div>
                <div className="grid grid-cols-2 gap-4">
                  <div className="space-y-2">
                    <Label>{t.conceptType}</Label>
                    <Select value={newConcept.tipo} onValueChange={(v) => setNewConcept({...newConcept, tipo: v})}>
                      <SelectTrigger>
                        <SelectValue />
                      </SelectTrigger>
                      <SelectContent>
                        <SelectItem value="ingreso">
                          <span className="flex items-center gap-2"><TrendingUp size={14} className="text-green-500" /> {t.income}</span>
                        </SelectItem>
                        <SelectItem value="egreso">
                          <span className="flex items-center gap-2"><TrendingDown size={14} className="text-red-500" /> {t.expense}</span>
                        </SelectItem>
                      </SelectContent>
                    </Select>
                  </div>
                  <div className="space-y-2">
                    <Label>{t.amount}</Label>
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
                    <Label>{t.week}</Label>
                    <Select value={String(newConcept.semana)} onValueChange={(v) => setNewConcept({...newConcept, semana: parseInt(v)})}>
                      <SelectTrigger>
                        <SelectValue />
                      </SelectTrigger>
                      <SelectContent>
                        {[1,2,3,4,5,6,7,8,9,10,11,12,13].map(s => (
                          <SelectItem key={s} value={String(s)}>{t.week} {s}</SelectItem>
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
                      <span className="text-sm">{t.recurring} ({language === 'es' ? 'todas las semanas' : 'all weeks'})</span>
                    </label>
                  </div>
                </div>
              </div>
              <DialogFooter>
                <Button variant="outline" onClick={() => setConceptDialogOpen(false)}>{t.cancel}</Button>
                <Button onClick={handleAddConcept}>{t.add}</Button>
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
            Vista Semanal (52 semanas)
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
          <div ref={reportRef} id="cashflow-report-container">

          {/* ── PDF Header ──────────────────────────────────────────────── */}
          <div className="bg-[#0F172A] text-white px-6 py-5 mb-4 rounded-lg flex items-center justify-between">
            <div>
              <p className="text-xs font-medium text-blue-400 uppercase tracking-widest mb-1">
                Proyección de Flujo de Efectivo · 18 Semanas Rolling
              </p>
              <h1 className="text-2xl font-bold">{companyConfig.nombre || 'Mi Empresa'}</h1>
              {companyConfig.rfc && (
                <p className="text-sm text-slate-400 mt-0.5">RFC: {companyConfig.rfc}</p>
              )}
            </div>
            <div className="text-right text-sm text-slate-400">
              <p className="text-base font-semibold text-slate-300">
                {format(new Date(), "MMMM yyyy", { locale: es })}
              </p>
              <p className="mt-1">Análisis: TaxnFin CFO Intelligence</p>
            </div>
          </div>

          {/* ===== CFO KPIs DASHBOARD ===== */}
          {cfoKPIs && (
            <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 xl:grid-cols-5 gap-4 mb-4" data-testid="cfo-kpis-section">
              {/* Net Burn Rate */}
              <div
                className="rounded-lg border bg-white shadow-sm border-l-4 border-l-blue-500 cursor-pointer hover:shadow-md transition-shadow"
                onClick={() => {
                  console.log('TEST INLINE CLICK — setKpiModal directo');
                  setKpiModal({ open: true, name: 'Net Burn Rate', formula: 'BurnRate = Σ(FlujoNeto) / N', description: 'Test directo', values: { 'Burn Rate Real': formatCurrency(cfoKPIs.burnRateReal) }, insight: '', loading: false, status: 'good', kpiKey: 'burnRate' });
                }}
                data-testid="kpi-burn-rate"
              >
                <div className="p-4 pt-3">
                  <div className="flex items-center justify-between text-sm text-gray-500 mb-1">
                    <div className="flex items-center gap-2"><Activity size={14} />Net Burn Rate</div>
                    <span className="text-xs text-blue-400">Ver análisis →</span>
                  </div>
                  <div className="space-y-1">
                    <div className="flex justify-between items-baseline">
                      <span className="text-xs text-gray-400">Real (promedio/sem):</span>
                      <span className={`text-lg font-bold ${cfoKPIs.burnRateReal >= 0 ? 'text-green-600' : 'text-red-600'}`}>
                        {formatCurrency(cfoKPIs.burnRateReal)}/sem
                      </span>
                    </div>
                    <div className="flex justify-between items-baseline">
                      <span className="text-xs text-gray-400">Proyectado (promedio/sem):</span>
                      <span className={`text-lg font-bold ${cfoKPIs.burnRateProyectado >= 0 ? 'text-green-600' : 'text-red-600'}`}>
                        {formatCurrency(cfoKPIs.burnRateProyectado)}/sem
                      </span>
                    </div>
                  </div>
                </div>
              </div>

              {/* Cash Gap Analysis */}
              <div
                className={`rounded-lg border bg-white shadow-sm border-l-4 ${cfoKPIs.semanasEnRiesgo.length > 0 ? 'border-l-red-500' : 'border-l-green-500'} cursor-pointer hover:shadow-md transition-shadow`}
                onClick={() => openKpiModal('cashGap')}
                data-testid="kpi-cash-gap"
              >
                <div className="p-4 pt-3">
                  <div className="flex items-center justify-between text-sm text-gray-500 mb-1">
                    <div className="flex items-center gap-2"><AlertTriangle size={14} />Cash Gap Analysis</div>
                    <span className="text-xs text-blue-400">Ver análisis →</span>
                  </div>
                  <div className="space-y-1">
                    <div className="flex justify-between items-baseline">
                      <span className="text-xs text-gray-400">Umbral mínimo:</span>
                      <span className="text-sm font-medium">{formatCurrency(umbralMinimoCaja)}</span>
                    </div>
                    <div className="flex justify-between items-baseline">
                      <span className="text-xs text-gray-400">Semanas en riesgo:</span>
                      <span className={`text-lg font-bold ${cfoKPIs.semanasEnRiesgo.length > 0 ? 'text-red-600' : 'text-green-600'}`}>
                        {cfoKPIs.semanasEnRiesgo.length} visible{cfoKPIs.semanasEnRiesgo.length !== 1 ? 's' : ''}
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
                </div>
              </div>

              {/* Volatilidad del Flujo */}
              <div
                className="rounded-lg border bg-white shadow-sm border-l-4 border-l-purple-500 cursor-pointer hover:shadow-md transition-shadow"
                onClick={() => openKpiModal('volatilidad')}
                data-testid="kpi-volatilidad"
              >
                <div className="p-4 pt-3">
                  <div className="flex items-center justify-between text-sm text-gray-500 mb-1">
                    <div className="flex items-center gap-2"><BarChart3 size={14} />Volatilidad del Flujo</div>
                    <span className="text-xs text-blue-400">Ver análisis →</span>
                  </div>
                  <div className="space-y-1">
                    <div className="flex justify-between items-baseline">
                      <span className="text-xs text-gray-400">Desv. Estándar (σ):</span>
                      <span className="text-lg font-bold text-purple-600">{formatCurrency(cfoKPIs.volatilidad)}</span>
                    </div>
                    <div className="flex justify-between items-baseline">
                      <span className="text-xs text-gray-400">Coef. Variación (CV):</span>
                      <span className={`text-sm font-medium ${cfoKPIs.coeficienteVariacion > 50 ? 'text-red-500' : cfoKPIs.coeficienteVariacion > 25 ? 'text-amber-500' : 'text-green-500'}`}>
                        {cfoKPIs.coeficienteVariacion.toFixed(1)}%
                      </span>
                    </div>
                    <p className="text-xs text-gray-400 mt-1">
                      {cfoKPIs.coeficienteVariacion > 50 ? '⚠️ Alta volatilidad' : cfoKPIs.coeficienteVariacion > 25 ? '⚡ Volatilidad moderada' : '✅ Flujo estable'}
                    </p>
                  </div>
                </div>
              </div>

              {/* Indicadores Operativos */}
              <div
                className="rounded-lg border bg-white shadow-sm border-l-4 border-l-amber-500 cursor-pointer hover:shadow-md transition-shadow"
                onClick={() => openKpiModal('operativos')}
                data-testid="kpi-operativos"
              >
                <div className="p-4 pt-3">
                  <div className="flex items-center justify-between text-sm text-gray-500 mb-1">
                    <div className="flex items-center gap-2"><Target size={14} />Indicadores Operativos</div>
                    <span className="text-xs text-blue-400">Ver análisis →</span>
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
                </div>
              </div>

              {/* Runway (conservador / proyectado) */}
              {(() => {
                const { conservador, proyectado, avgNetBurn, horizonte } = runwayKPI;
                const semanasAMeses = (sem) => (sem / 4.33).toFixed(1);
                // Color del card según runway CONSERVADOR; caja positiva = verde
                const borderColor = conservador === null ? 'border-l-green-500'
                  : conservador > 12 ? 'border-l-green-500'
                  : conservador >= 6 ? 'border-l-amber-500'
                  : 'border-l-red-500';
                const consColor = conservador === null ? 'text-green-600'
                  : conservador > 12 ? 'text-green-600'
                  : conservador >= 6 ? 'text-amber-600'
                  : 'text-red-600';
                return (
                  <div
                    className={`rounded-lg border bg-white shadow-sm border-l-4 ${borderColor} hover:shadow-md transition-shadow`}
                    data-testid="kpi-runway"
                  >
                    <div className="p-4 pt-3">
                      <div className="flex items-center justify-between text-sm text-gray-500 mb-1">
                        <div className="flex items-center gap-2"><Calendar size={14} />Runway</div>
                      </div>
                      <div className="space-y-1">
                        <div className="flex justify-between items-baseline">
                          <span className="text-xs text-gray-400">Conservador:</span>
                          <span className={`text-lg font-bold ${consColor}`}>
                            {conservador === null
                              ? 'Caja positiva ✓'
                              : `${Math.round(conservador)} sem (${semanasAMeses(conservador)} meses)`}
                          </span>
                        </div>
                        <div className="flex justify-between items-baseline">
                          <span className="text-xs text-gray-400">Proyectado:</span>
                          <span className={`text-lg font-bold ${proyectado === null ? 'text-green-600' : proyectado > 12 ? 'text-green-600' : proyectado >= 6 ? 'text-amber-600' : 'text-red-600'}`}>
                            {proyectado === null
                              ? `>${horizonte} sem ✓`
                              : `${proyectado} sem (${semanasAMeses(proyectado)} meses)`}
                          </span>
                        </div>
                        <p className="text-xs text-gray-400 mt-1">
                          {conservador === null
                            ? `Net burn promedio 4 sem: ${formatCurrency(avgNetBurn)}/sem (genera caja)`
                            : `Net burn promedio 4 sem: ${formatCurrency(avgNetBurn)}/sem`}
                        </p>
                      </div>
                    </div>
                  </div>
                );
              })()}
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
                {(() => {
                  const visReales = displayedTotals.filter(w => w.dataType === 'real' || w.dataType === 'actual');
                  const visProy   = displayedTotals.filter(w => w.dataType === 'proyectado');
                  const lbl = (arr) => arr.length === 0 ? '—'
                    : arr.length === 1 ? (arr[0].displayLabel || arr[0].label)
                    : `${arr[0].displayLabel || arr[0].label} – ${arr[arr.length-1].displayLabel || arr[arr.length-1].label}`;
                  return (
                <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
                  <div className="text-center p-3 bg-white rounded-lg shadow-sm">
                    <div className="text-xs text-gray-500 mb-1">Ingresos Reales ({lbl(visReales)})</div>
                    <div className="text-xl font-bold text-green-600">{formatCurrency(cfoKPIs.totalIngresosReales)}</div>
                  </div>
                  <div className="text-center p-3 bg-white rounded-lg shadow-sm">
                    <div className="text-xs text-gray-500 mb-1">Egresos Reales ({lbl(visReales)})</div>
                    <div className="text-xl font-bold text-red-600">{formatCurrency(cfoKPIs.totalEgresosReales)}</div>
                  </div>
                  <div className="text-center p-3 bg-white rounded-lg shadow-sm">
                    <div className="text-xs text-gray-500 mb-1">Ingresos Proyectados ({lbl(visProy)})</div>
                    <div className="text-xl font-bold text-green-500">{formatCurrency(cfoKPIs.totalIngresosProyectados)}</div>
                  </div>
                  <div className="text-center p-3 bg-white rounded-lg shadow-sm">
                    <div className="text-xs text-gray-500 mb-1">Egresos Proyectados ({lbl(visProy)})</div>
                    <div className="text-xl font-bold text-red-500">{formatCurrency(cfoKPIs.totalEgresosProyectados)}</div>
                  </div>
                </div>
                  );
                })()}
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

          {/* ===== GRÁFICOS COMPARATIVOS ===== */}
          {chartData.length > 0 && (
            <div ref={chartsRef} data-html2canvas-ignore="true" className="grid grid-cols-1 lg:grid-cols-2 gap-4" data-testid="charts-section">
              {/* Gráfico 1: Flujo Acumulado Real vs Proyectado */}
              <Card>
                <CardHeader className="py-3">
                  <CardTitle className="text-base flex items-center gap-2">
                    <TrendingUp size={18} className="text-blue-600" />
                    Flujo Acumulado: Real vs Proyectado
                  </CardTitle>
                </CardHeader>
                <CardContent>
                  <ResponsiveContainer width="100%" height={250}>
                    <ComposedChart data={chartData}>
                      <CartesianGrid strokeDasharray="3 3" stroke="#e0e0e0" />
                      <XAxis dataKey="semana" tick={{ fontSize: 11 }} />
                      <YAxis 
                        tick={{ fontSize: 10 }} 
                        tickFormatter={(v) => `${(v / 1000000).toFixed(1)}M`}
                      />
                      <Tooltip 
                        formatter={(value, name) => [
                          `$${value?.toLocaleString('es-MX', { minimumFractionDigits: 0 })}`,
                          name === 'acumuladoReal' ? 'Real Acumulado' : 
                          name === 'acumuladoProyectado' ? 'Proyectado Total' : name
                        ]}
                        labelFormatter={(label) => `Semana ${label}`}
                      />
                      <Legend />
                      <Area 
                        type="monotone" 
                        dataKey="acumuladoReal" 
                        fill="#22c55e" 
                        fillOpacity={0.3}
                        stroke="#16a34a" 
                        strokeWidth={2}
                        name="Real Acumulado"
                        connectNulls={false}
                      />
                      <Line 
                        type="monotone" 
                        dataKey="acumuladoProyectado" 
                        stroke="#6366f1" 
                        strokeWidth={2}
                        strokeDasharray="5 5"
                        name="Proyectado Total"
                        dot={{ fill: '#6366f1', r: 3 }}
                      />
                    </ComposedChart>
                  </ResponsiveContainer>
                </CardContent>
              </Card>

              {/* Gráfico 2: Ingresos vs Egresos por Semana */}
              <Card>
                <CardHeader className="py-3">
                  <CardTitle className="text-base flex items-center gap-2">
                    <BarChart3 size={18} className="text-purple-600" />
                    Ingresos vs Egresos Semanal
                  </CardTitle>
                </CardHeader>
                <CardContent>
                  <ResponsiveContainer width="100%" height={250}>
                    <BarChart data={chartData}>
                      <CartesianGrid strokeDasharray="3 3" stroke="#e0e0e0" />
                      <XAxis dataKey="semana" tick={{ fontSize: 11 }} />
                      <YAxis 
                        tick={{ fontSize: 10 }} 
                        tickFormatter={(v) => `${(v / 1000000).toFixed(1)}M`}
                      />
                      <Tooltip 
                        formatter={(value) => [`$${value?.toLocaleString('es-MX', { minimumFractionDigits: 0 })}`]}
                        labelFormatter={(label) => `Semana ${label}`}
                      />
                      <Legend />
                      <Bar dataKey="ingresos" fill="#22c55e" name="Ingresos" radius={[2, 2, 0, 0]} />
                      <Bar dataKey="egresos" fill="#ef4444" name="Egresos" radius={[2, 2, 0, 0]} />
                    </BarChart>
                  </ResponsiveContainer>
                </CardContent>
              </Card>

              {/* Gráfico 3: Saldo Final vs Umbral Mínimo (Cash Gap) */}
              <Card>
                <CardHeader className="py-3">
                  <CardTitle className="text-base flex items-center gap-2">
                    <AlertTriangle size={18} className="text-amber-600" />
                    Saldo Final vs Umbral Mínimo (Cash Gap)
                  </CardTitle>
                </CardHeader>
                <CardContent>
                  <ResponsiveContainer width="100%" height={250}>
                    <ComposedChart data={chartData}>
                      <CartesianGrid strokeDasharray="3 3" stroke="#e0e0e0" />
                      <XAxis dataKey="semana" tick={{ fontSize: 11 }} />
                      <YAxis 
                        tick={{ fontSize: 10 }} 
                        tickFormatter={(v) => `${(v / 1000000).toFixed(1)}M`}
                      />
                      <Tooltip 
                        formatter={(value, name) => [
                          `$${value?.toLocaleString('es-MX', { minimumFractionDigits: 0 })}`,
                          name === 'saldoFinal' ? 'Saldo Final' : 
                          name === 'umbralMinimo' ? 'Umbral Mínimo' : name
                        ]}
                        labelFormatter={(label) => `Semana ${label}`}
                      />
                      <Legend />
                      <Area 
                        type="monotone" 
                        dataKey="saldoFinal" 
                        fill="#3b82f6" 
                        fillOpacity={0.3}
                        stroke="#2563eb" 
                        strokeWidth={2}
                        name="Saldo Final"
                      />
                      <ReferenceLine 
                        y={chartData[0]?.umbralMinimo || 0} 
                        stroke="#ef4444" 
                        strokeWidth={2}
                        strokeDasharray="5 5"
                        label={{ value: 'Umbral Mínimo', fill: '#ef4444', fontSize: 10 }}
                      />
                    </ComposedChart>
                  </ResponsiveContainer>
                </CardContent>
              </Card>

              {/* Gráfico 4: Flujo Neto Semanal */}
              <Card>
                <CardHeader className="py-3">
                  <CardTitle className="text-base flex items-center gap-2">
                    <Activity size={18} className="text-indigo-600" />
                    Flujo Neto Semanal
                  </CardTitle>
                </CardHeader>
                <CardContent>
                  <ResponsiveContainer width="100%" height={250}>
                    <ComposedChart data={chartData}>
                      <CartesianGrid strokeDasharray="3 3" stroke="#e0e0e0" />
                      <XAxis dataKey="semana" tick={{ fontSize: 11 }} />
                      <YAxis 
                        tick={{ fontSize: 10 }} 
                        tickFormatter={(v) => `${(v / 1000000).toFixed(1)}M`}
                      />
                      <Tooltip 
                        formatter={(value) => [`$${value?.toLocaleString('es-MX', { minimumFractionDigits: 0 })}`]}
                        labelFormatter={(label) => `Semana ${label}`}
                      />
                      <Legend />
                      <ReferenceLine y={0} stroke="#666" strokeWidth={1} />
                      <Bar 
                        dataKey="flujoNetoPositivo" 
                        fill="#22c55e"
                        name="Flujo Positivo"
                        stackId="flujo"
                        radius={[2, 2, 0, 0]}
                      />
                      <Bar 
                        dataKey="flujoNetoNegativo" 
                        fill="#ef4444"
                        name="Flujo Negativo"
                        stackId="flujo"
                        radius={[2, 2, 0, 0]}
                      />
                    </ComposedChart>
                  </ResponsiveContainer>
                </CardContent>
              </Card>
            </div>
          )}

          {/* ===== MAIN CASH FLOW TABLE ===== */}
          <Card>
            <CardHeader className="bg-[#0F172A] text-white rounded-t-lg">
              <div className="flex items-center justify-between">
                <CardTitle className="flex items-center gap-3">
                  <span>Modelo de Flujo de Efectivo - 18 Semanas</span>
                  <div className="flex items-center gap-2 ml-4">
                    <Button
                      variant={tableViewMode === 'categoria' ? 'secondary' : 'ghost'}
                      size="sm"
                      className={`h-7 text-xs ${tableViewMode === 'categoria' ? 'bg-white text-[#0F172A]' : 'text-white/70 hover:text-white hover:bg-white/10'}`}
                      onClick={() => setTableViewMode('categoria')}
                    >
                      <Layers size={14} className="mr-1" />
                      Por Categoría
                    </Button>
                    <Button
                      variant={tableViewMode === 'tercero' ? 'secondary' : 'ghost'}
                      size="sm"
                      className={`h-7 text-xs ${tableViewMode === 'tercero' ? 'bg-white text-[#0F172A]' : 'text-white/70 hover:text-white hover:bg-white/10'}`}
                      onClick={() => setTableViewMode('tercero')}
                    >
                      <Building2 size={14} className="mr-1" />
                      Por Proveedor/Cliente
                    </Button>
                  </div>
                </CardTitle>
                <div className="flex items-center gap-3">
                  <Button
                    variant="ghost"
                    size="sm"
                    className="h-8 text-xs text-white/80 hover:text-white hover:bg-white/10 gap-1"
                    onClick={exportDetailReport}
                  >
                    <FileSpreadsheet size={14} />
                    Exportar Detalle
                  </Button>
                  <span className="text-sm font-normal opacity-70">
                    {format(new Date(), 'MMMM yyyy', { locale: es })}
                  </span>
                </div>
              </div>
            </CardHeader>
            <CardContent className="p-0">
              <div className="overflow-x-auto [&_td]:py-1 [&_td]:px-2 [&_th]:py-1.5 [&_th]:px-2">
                <Table className="text-xs">
                  <TableHeader>
                    <TableRow className="bg-gray-100">
                      <TableHead className="sticky left-0 bg-gray-100 min-w-[200px] font-bold">CONCEPTO</TableHead>
                      {weeklyTotals.map((week, idx) => columnVisible[idx] ? (
                        <TableHead key={idx} className={`text-center min-w-[65px] ${
                          week.dataType === 'real' ? 'bg-yellow-50' :
                          week.dataType === 'actual' ? 'bg-blue-50' : 'bg-gray-50'
                        }`}>
                          <div className="font-bold">{week.displayLabel || week.label}</div>
                          <div className="text-xs text-gray-500">{week.dateLabel}</div>
                          <div className={`text-xs font-semibold ${
                            week.dataType === 'real' ? 'text-yellow-600' :
                            week.dataType === 'actual' ? 'text-blue-600' : 'text-gray-400'
                          }`}>
                            {week.dataType === 'real' ? 'Real' : week.dataType === 'actual' ? 'Actual' : 'Proy'}
                          </div>
                        </TableHead>
                      ) : null)}
                      <TableHead className="text-center min-w-[120px] bg-blue-50 font-bold">TOTAL</TableHead>
                    </TableRow>
                  </TableHeader>
                  <TableBody>
                    {tableViewMode === 'categoria' ? (
                      <>
                        {/* SALDO INICIAL POR SEMANA Row */}
                        <TableRow className="bg-blue-100 font-bold border-b-2 border-blue-300">
                          <TableCell className="sticky left-0 bg-blue-100">
                            <div className="flex items-center gap-2">
                              <Building2 className="text-blue-600" size={16} />
                              SALDO INICIAL SEMANA
                            </div>
                          </TableCell>
                          {weeklyTotals.map((week, idx) => columnVisible[idx] ? (
                            <TableCell key={idx} className="text-center text-blue-700 font-bold text-sm">
                              {formatCurrency(week.saldoInicial)}
                            </TableCell>
                          ) : null)}
                          <TableCell className="text-center bg-blue-200 text-blue-800 font-bold">
                            {formatCurrency(displayedTotals[0]?.saldoInicial || saldoInicialBancos)}
                          </TableCell>
                        </TableRow>

                        {/* RECEIPTS / INGRESOS Section */}
                    <TableRow className="bg-green-50 font-bold">
                      <TableCell className="sticky left-0 bg-green-50">
                        <div className="flex items-center gap-2">
                          <TrendingUp className="text-green-600" size={16} />
                          INGRESOS
                          {displayedTotals.some(w => w.dataType === 'real' || w.dataType === 'actual') && (
                            <span className="text-xs px-2 py-0.5 bg-green-200 text-green-800 rounded">S1-S5 Real</span>
                          )}
                        </div>
                      </TableCell>
                      {weeklyTotals.map((week, idx) => columnVisible[idx] ? (
                        <TableCell key={idx} className={`text-center font-bold text-sm ${
                          week.dataType === 'real' ? 'text-green-800 bg-green-100' :
                          week.dataType === 'actual' ? 'text-green-700 bg-green-50' : 'text-green-600'
                        }`}>
                          {formatCurrency(week.ingresos.total)}
                        </TableCell>
                      ) : null)}
                      <TableCell className="text-center bg-green-100 text-green-800 font-bold">
                        {formatCurrency(grandTotalIngresos)}
                      </TableCell>
                    </TableRow>

                    {/* Ingresos by Category - Show "Cobranza" or category name, also show "Sin categoría" */}
                    {/* Exclude "Compra de USD" category as it's shown separately */}
                    {(() => {
                      // Collect all unique category names from ingresos including "Sin categoría"
                      const allIngresoCategories = new Set();
                      weeklyTotals.forEach(w => {
                        Object.keys(w.ingresos.byCategory).forEach(cat => {
                          // Exclude USD operations from INGRESOS section
                          if (!cat.toLowerCase().includes('compra de usd') && !cat.toLowerCase().includes('compra usd')) {
                            allIngresoCategories.add(cat);
                          }
                        });
                      });

                      return Array.from(allIngresoCategories).map((categoryName, catIdx) => {
                        const categoryKey = `ing-${categoryName}`;
                        const isExpanded = expandedRows[categoryKey];
                        const weekTotals = weeklyTotals.map(w => w.ingresos.byCategory[categoryName]?.total || 0);
                        const categoryTotal = weekTotals.reduce((sum, t) => sum + t, 0);

                        if (categoryTotal === 0) return null;

                        return (
                          <React.Fragment key={categoryKey}>
                            <TableRow className={`${catIdx % 2 === 1 ? 'bg-slate-50' : 'bg-white'} hover:bg-green-50/50`}>
                              <TableCell className="sticky left-0 bg-white pl-8">
                                <button 
                                  onClick={() => toggleRow(categoryKey)}
                                  className="flex items-center gap-1 text-gray-700 hover:text-green-600"
                                >
                                  {isExpanded ? <ChevronDown size={14} /> : <ChevronRight size={14} />}
                                  {categoryName === 'Sin categoría' ? 'Cobranza' : categoryName}
                                </button>
                              </TableCell>
                              {weekTotals.map((total, idx) => columnVisible[idx] ? (
                                <TableCell
                                  key={idx}
                                  className={`text-center text-green-600 ${total > 0 ? 'cursor-pointer hover:bg-green-100 hover:underline' : ''}`}
                                  onClick={() => total > 0 && handleCellClick(idx, 'ingreso', categoryName)}
                                >
                                  {total > 0 ? formatCurrency(total) : '-'}
                                </TableCell>
                              ) : null)}
                              <TableCell className="text-center bg-green-50 text-green-700">
                                {formatCurrency(categoryTotal)}
                              </TableCell>
                            </TableRow>
                            {/* Subcategorías expandibles */}
                            {isExpanded && (() => {
                              const allSubcategories = new Set();
                              weeklyTotals.forEach(w => {
                                const cat = w.ingresos.byCategory[categoryName];
                                if (cat?.bySubcategory) {
                                  Object.keys(cat.bySubcategory).forEach(sub => allSubcategories.add(sub));
                                }
                              });
                              
                              return Array.from(allSubcategories).map(subName => {
                                const subTotals = weeklyTotals.map(w =>
                                  w.ingresos.byCategory[categoryName]?.bySubcategory?.[subName]?.total || 0
                                );
                                const subTotal = subTotals.reduce((s, t) => s + t, 0);
                                if (subTotal === 0) return null;
                                
                                return (
                                  <TableRow key={`${categoryKey}-${subName}`} className="bg-green-50/30">
                                    <TableCell className="sticky left-0 bg-green-50/30 pl-14 text-sm text-gray-600">
                                      └ {subName}
                                    </TableCell>
                                    {subTotals.map((total, idx) => columnVisible[idx] ? (
                                      <TableCell
                                        key={idx}
                                        className={`text-center text-green-500 text-sm ${total > 0 ? 'cursor-pointer hover:bg-green-100 hover:underline' : ''}`}
                                        onClick={() => total > 0 && handleCellClick(idx, 'ingreso', categoryName, subName)}
                                      >
                                        {total > 0 ? formatCurrency(total) : '-'}
                                      </TableCell>
                                    ) : null)}
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
                          {displayedTotals.some(w => w.dataType === 'real' || w.dataType === 'actual') && (
                            <span className="text-xs px-2 py-0.5 bg-red-200 text-red-800 rounded">S1-S5 Real</span>
                          )}
                        </div>
                      </TableCell>
                      {weeklyTotals.map((week, idx) => columnVisible[idx] ? (
                        <TableCell key={idx} className={`text-center font-bold text-sm ${
                          week.dataType === 'real' ? 'text-red-800 bg-red-100' :
                          week.dataType === 'actual' ? 'text-red-700 bg-red-50' : 'text-red-600'
                        }`}>
                          {formatCurrency(week.egresos.total)}
                        </TableCell>
                      ) : null)}
                      <TableCell className="text-center bg-red-100 text-red-800 font-bold">
                        {formatCurrency(grandTotalEgresos)}
                      </TableCell>
                    </TableRow>
                    
                    {/* Egresos by Category - Show all including "Sin categoría" as "Proveedores Costo" */}
                    {/* Exclude "Venta de USD" category as it's shown separately */}
                    {(() => {
                      // Collect all unique category names from egresos including "Sin categoría"
                      const allEgresoCategories = new Set();
                      weeklyTotals.forEach(w => {
                        Object.keys(w.egresos.byCategory).forEach(cat => {
                          // Exclude USD operations from EGRESOS section
                          if (!cat.toLowerCase().includes('venta de usd') && !cat.toLowerCase().includes('venta usd')) {
                            allEgresoCategories.add(cat);
                          }
                        });
                      });

                      return Array.from(allEgresoCategories).map((categoryName, catIdx) => {
                        const categoryKey = `egr-${categoryName}`;
                        const isExpanded = expandedRows[categoryKey];
                        const weekTotals = weeklyTotals.map(w => w.egresos.byCategory[categoryName]?.total || 0);
                        const categoryTotal = weekTotals.reduce((sum, t) => sum + t, 0);

                        if (categoryTotal === 0) return null;

                        return (
                          <React.Fragment key={categoryKey}>
                            <TableRow className={`${catIdx % 2 === 1 ? 'bg-slate-50' : 'bg-white'} hover:bg-red-50/50`}>
                              <TableCell className="sticky left-0 bg-white pl-8">
                                <button 
                                  onClick={() => toggleRow(categoryKey)}
                                  className="flex items-center gap-1 text-gray-700 hover:text-red-600"
                                >
                                  {isExpanded ? <ChevronDown size={14} /> : <ChevronRight size={14} />}
                                  {categoryName === 'Sin categoría' ? 'Proveedores Costo' : categoryName}
                                </button>
                              </TableCell>
                              {weekTotals.map((total, idx) => columnVisible[idx] ? (
                                <TableCell
                                  key={idx}
                                  className={`text-center text-red-600 ${total > 0 ? 'cursor-pointer hover:bg-red-100 hover:underline' : ''}`}
                                  onClick={() => total > 0 && handleCellClick(idx, 'egreso', categoryName)}
                                >
                                  {total > 0 ? formatCurrency(total) : '-'}
                                </TableCell>
                              ) : null)}
                              <TableCell className="text-center bg-red-50 text-red-700">
                                {formatCurrency(categoryTotal)}
                              </TableCell>
                            </TableRow>
                            {/* Subcategorías expandibles */}
                            {isExpanded && (() => {
                              const allSubcategories = new Set();
                              weeklyTotals.forEach(w => {
                                const cat = w.egresos.byCategory[categoryName];
                                if (cat?.bySubcategory) {
                                  Object.keys(cat.bySubcategory).forEach(sub => allSubcategories.add(sub));
                                }
                              });
                              
                              return Array.from(allSubcategories).map(subName => {
                                const subTotals = weeklyTotals.map(w =>
                                  w.egresos.byCategory[categoryName]?.bySubcategory?.[subName]?.total || 0
                                );
                                const subTotal = subTotals.reduce((s, t) => s + t, 0);
                                if (subTotal === 0) return null;
                                
                                return (
                                  <TableRow key={`${categoryKey}-${subName}`} className="bg-red-50/30">
                                    <TableCell className="sticky left-0 bg-red-50/30 pl-14 text-sm text-gray-600">
                                      └ {subName}
                                    </TableCell>
                                    {subTotals.map((total, idx) => columnVisible[idx] ? (
                                      <TableCell
                                        key={idx}
                                        className={`text-center text-red-500 text-sm ${total > 0 ? 'cursor-pointer hover:bg-red-100 hover:underline' : ''}`}
                                        onClick={() => total > 0 && handleCellClick(idx, 'egreso', categoryName, subName)}
                                      >
                                        {total > 0 ? formatCurrency(total) : '-'}
                                      </TableCell>
                                    ) : null)}
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
                          {weeklyTotals.map((week, idx) => columnVisible[idx] ? (
                            <TableCell key={idx} className={`text-center font-bold ${(week.flujoDivisas || 0) >= 0 ? 'text-purple-700' : 'text-purple-700'}`}>
                              {formatCurrency(week.flujoDivisas || 0)}
                            </TableCell>
                          ) : null)}
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
                          {weeklyTotals.map((week, idx) => columnVisible[idx] ? (
                            <TableCell key={idx} className="text-center text-green-600">
                              {(week.ventaUSD || 0) > 0 ? formatCurrency(week.ventaUSD) : '-'}
                            </TableCell>
                          ) : null)}
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
                          {weeklyTotals.map((week, idx) => columnVisible[idx] ? (
                            <TableCell key={idx} className="text-center text-red-600">
                              {(week.compraUSD || 0) > 0 ? `(${formatCurrency(week.compraUSD)})` : '-'}
                            </TableCell>
                          ) : null)}
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
                      {weeklyTotals.map((week, idx) => columnVisible[idx] ? (
                        <TableCell
                          key={idx}
                          className={`text-center font-bold ${week.flujoNeto >= 0 ? 'text-green-700' : 'text-red-700'}`}
                        >
                          {formatCurrency(week.flujoNeto)}
                        </TableCell>
                      ) : null)}
                      <TableCell className={`text-center font-bold ${grandTotalFlujo >= 0 ? 'text-green-800 bg-green-100' : 'text-red-800 bg-red-100'}`}>
                        {formatCurrency(grandTotalFlujo)}
                      </TableCell>
                    </TableRow>

                    {/* SALDO FINAL POR SEMANA */}
                    <TableRow className="bg-[#0F172A] text-white font-bold">
                      <TableCell className="sticky left-0 bg-[#0F172A]">
                        SALDO FINAL SEMANA
                      </TableCell>
                      {weeklyTotals.map((week, idx) => columnVisible[idx] ? (
                        <TableCell
                          key={idx}
                          className={`text-center font-bold text-sm ${week.saldoFinal >= 0 ? 'text-green-400' : 'text-red-400'}`}
                        >
                          {formatCurrency(week.saldoFinal)}
                        </TableCell>
                      ) : null)}
                      <TableCell className="text-center font-bold">
                        {formatCurrency(displayedTotals[displayedTotals.length - 1]?.saldoFinal || 0)}
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
                        if (!columnVisible[idx]) return null;
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
                          const finalGap = (displayedTotals[displayedTotals.length - 1]?.saldoFinal || 0) - umbralMinimoCaja;
                          return finalGap < 0 ? `(${formatCurrency(Math.abs(finalGap))})` : formatCurrency(finalGap);
                        })()}
                      </TableCell>
                    </TableRow>
                      </>
                    ) : (
                      /* ===== VISTA POR PROVEEDOR/CLIENTE ===== */
                      <>
                        {/* Filters Row */}
                        <TableRow className="bg-blue-50 border-b-2 border-blue-200">
                          <TableCell colSpan={weeklyTotals.length + 2} className="py-3">
                            <div className="flex items-center gap-4 flex-wrap">
                              <div className="flex items-center gap-2">
                                <Filter size={16} className="text-blue-600" />
                                <span className="text-sm font-medium text-blue-800">Filtros:</span>
                              </div>
                              
                              {/* Search by name */}
                              <div className="relative flex-1 min-w-[200px] max-w-[300px]">
                                <Search size={14} className="absolute left-2 top-1/2 transform -translate-y-1/2 text-gray-400" />
                                <Input
                                  placeholder="Buscar proveedor/cliente..."
                                  value={partyFilters.searchTerm}
                                  onChange={(e) => setPartyFilters(prev => ({ ...prev, searchTerm: e.target.value }))}
                                  className="pl-8 h-8 text-sm"
                                  data-testid="party-filter-search"
                                />
                              </div>
                              
                              {/* Filter by tipo */}
                              <Select
                                value={partyFilters.tipoTercero}
                                onValueChange={(value) => setPartyFilters(prev => ({ ...prev, tipoTercero: value }))}
                              >
                                <SelectTrigger className="w-[140px] h-8 text-sm" data-testid="party-filter-type">
                                  <SelectValue placeholder="Tipo" />
                                </SelectTrigger>
                                <SelectContent>
                                  <SelectItem value="todos">Todos</SelectItem>
                                  <SelectItem value="cliente">
                                    <div className="flex items-center gap-2">
                                      <User size={12} className="text-blue-500" />
                                      Clientes
                                    </div>
                                  </SelectItem>
                                  <SelectItem value="proveedor">
                                    <div className="flex items-center gap-2">
                                      <Building2 size={12} className="text-orange-500" />
                                      Proveedores
                                    </div>
                                  </SelectItem>
                                </SelectContent>
                              </Select>
                              
                              {/* Filter by saldo */}
                              <Select
                                value={partyFilters.saldoTipo}
                                onValueChange={(value) => setPartyFilters(prev => ({ ...prev, saldoTipo: value }))}
                              >
                                <SelectTrigger className="w-[150px] h-8 text-sm" data-testid="party-filter-balance">
                                  <SelectValue placeholder="Saldo" />
                                </SelectTrigger>
                                <SelectContent>
                                  <SelectItem value="todos">Todos los saldos</SelectItem>
                                  <SelectItem value="positivo">
                                    <div className="flex items-center gap-2">
                                      <TrendingUp size={12} className="text-green-500" />
                                      Saldo positivo
                                    </div>
                                  </SelectItem>
                                  <SelectItem value="negativo">
                                    <div className="flex items-center gap-2">
                                      <TrendingDown size={12} className="text-red-500" />
                                      Saldo negativo
                                    </div>
                                  </SelectItem>
                                </SelectContent>
                              </Select>
                              
                              {/* Clear filters button */}
                              {hasPartyFiltersActive() && (
                                <Button 
                                  variant="ghost" 
                                  size="sm" 
                                  className="h-8 text-xs text-blue-600 hover:text-blue-800 gap-1"
                                  onClick={resetPartyFilters}
                                  data-testid="party-filter-clear"
                                >
                                  <XIcon size={14} />
                                  Limpiar
                                </Button>
                              )}
                              
                              {/* Export button */}
                              <div className="ml-auto">
                                <Button 
                                  variant="outline" 
                                  size="sm" 
                                  className="h-8 text-xs gap-1"
                                  onClick={exportPartyReport}
                                  data-testid="party-export-btn"
                                >
                                  <Download size={14} />
                                  {hasPartyFiltersActive() ? 'Exportar Filtrado' : 'Exportar Terceros'}
                                </Button>
                              </div>
                            </div>
                          </TableCell>
                        </TableRow>

                        {/* Header + filas + TOTAL NETO comparten filteredParties */}
                        {(() => {
                          const partyData = processDataByParty(weeklyTotals);
                          const filteredParties = filterPartyData(partyData);
                          const sortedParties = [...filteredParties].sort((a, b) => {
                            const tot = (p) => Object.entries(p.weeks).filter(([i]) => columnVisible[+i]).reduce((s, [, w]) => s + Math.abs(w.ingresos - w.egresos), 0);
                            return tot(b) - tot(a);
                          });
                          const filteredWeekNet = (wi) => filteredParties.reduce((s, p) => {
                            const wd = p.weeks[wi] || { ingresos: 0, egresos: 0 };
                            return s + (wd.ingresos - wd.egresos);
                          }, 0);
                          const filteredGrandNet = weeklyTotals.reduce((s, _, i) => columnVisible[i] ? s + filteredWeekNet(i) : s, 0);

                          return (<>
                            {/* Header — totales de terceros filtrados */}
                            <TableRow className="bg-gray-100 font-bold border-b-2">
                              <TableCell className="sticky left-0 bg-gray-100">
                                <div className="flex items-center gap-2">
                                  <Building2 size={16} className="text-gray-600" />
                                  PROVEEDOR / CLIENTE
                                </div>
                              </TableCell>
                              {weeklyTotals.map((_, idx) => columnVisible[idx] ? (
                                <TableCell key={idx} className="text-center text-xs text-gray-600">
                                  Tot: {formatCurrency(filteredWeekNet(idx))}
                                </TableCell>
                              ) : null)}
                              <TableCell className="text-center bg-gray-200 font-bold">TOTAL</TableCell>
                            </TableRow>

                            {/* Filas de terceros */}
                            {sortedParties.length === 0 ? (
                              <TableRow>
                                <TableCell colSpan={weeklyTotals.length + 2} className="text-center py-8 text-gray-500">
                                  {hasPartyFiltersActive()
                                    ? 'No hay terceros que coincidan con los filtros seleccionados'
                                    : 'No hay datos de proveedores/clientes para mostrar'}
                                </TableCell>
                              </TableRow>
                            ) : sortedParties.map(party => {
                              const totalIngresos = Object.entries(party.weeks).filter(([wi]) => columnVisible[+wi]).reduce((s, [, w]) => s + w.ingresos, 0);
                              const totalEgresos  = Object.entries(party.weeks).filter(([wi]) => columnVisible[+wi]).reduce((s, [, w]) => s + w.egresos,  0);
                              const netTotal = totalIngresos - totalEgresos;
                              if (totalIngresos === 0 && totalEgresos === 0) return null;
                              return (
                                <TableRow key={party.id} className={`hover:bg-gray-50 ${party.tipo === 'cliente' ? 'hover:bg-green-50/30' : 'hover:bg-red-50/30'}`}>
                                  <TableCell className="sticky left-0 bg-white">
                                    <div className="flex items-center gap-2">
                                      {party.tipo === 'cliente' ? <User size={14} className="text-blue-500" /> : <Building2 size={14} className="text-orange-500" />}
                                      <span className="truncate max-w-[170px]" title={party.nombre}>{party.nombre}</span>
                                      <Badge variant="outline" className="text-xs ml-1">{party.tipo === 'cliente' ? 'C' : 'P'}</Badge>
                                    </div>
                                  </TableCell>
                                  {weeklyTotals.map((_, weekIdx) => {
                                    if (!columnVisible[weekIdx]) return null;
                                    const weekData = party.weeks[weekIdx] || { ingresos: 0, egresos: 0 };
                                    const netValue = weekData.ingresos - weekData.egresos;
                                    const hasItems = weekData.ingresos > 0 || weekData.egresos > 0;
                                    return (
                                      <TableCell key={weekIdx}
                                        className={`text-center text-sm ${netValue > 0 ? 'text-green-600' : netValue < 0 ? 'text-red-600' : 'text-gray-400'} ${hasItems ? 'cursor-pointer hover:bg-gray-100 hover:underline' : ''}`}
                                        onClick={() => {
                                          if (!hasItems) return;
                                          setDrillDownData({
                                            weekNum: weekIdx + 1,
                                            weekLabel: weeklyData[weekIdx]?.displayLabel || weeklyData[weekIdx]?.label || `S${weekIdx + 1}`,
                                            dateLabel: weeklyData[weekIdx]?.dateLabel || '',
                                            dataType: weeklyData[weekIdx]?.dataType,
                                            tipo: netValue >= 0 ? 'ingreso' : 'egreso',
                                            categoryName: party.nombre,
                                            subcategoryName: party.tipo === 'cliente' ? 'Cliente' : 'Proveedor',
                                            items: (weekData.items || []).map(item => ({ ...item, tercero: party.nombre, terceroTipo: party.tipo })),
                                            total: netValue
                                          });
                                          setDrillDownOpen(true);
                                        }}
                                      >
                                        {netValue !== 0 ? formatCurrency(netValue) : '-'}
                                      </TableCell>
                                    );
                                  })}
                                  <TableCell className={`text-center font-bold ${netTotal > 0 ? 'bg-green-50 text-green-700' : netTotal < 0 ? 'bg-red-50 text-red-700' : 'text-gray-500'}`}>
                                    {formatCurrency(netTotal)}
                                  </TableCell>
                                </TableRow>
                              );
                            })}

                            {/* TOTAL NETO — filtrado */}
                            <TableRow className="bg-gray-200 font-bold border-t-2">
                              <TableCell className="sticky left-0 bg-gray-200">TOTAL NETO</TableCell>
                              {weeklyTotals.map((_, idx) => columnVisible[idx] ? (
                                <TableCell key={idx} className={`text-center font-bold ${filteredWeekNet(idx) >= 0 ? 'text-green-700' : 'text-red-700'}`}>
                                  {formatCurrency(filteredWeekNet(idx))}
                                </TableCell>
                              ) : null)}
                              <TableCell className={`text-center font-bold ${filteredGrandNet >= 0 ? 'text-green-800 bg-green-100' : 'text-red-800 bg-red-100'}`}>
                                {formatCurrency(filteredGrandNet)}
                              </TableCell>
                            </TableRow>
                          </>);
                        })()}
                      </>
                    )}
                  </TableBody>
                </Table>
              </div>
            </CardContent>
          </Card>
          </div> {/* End of reportRef div for PDF export */}
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
                        <TableHead key={idx} className={`text-center min-w-[130px] capitalize ${
                          month.isCurrent ? 'bg-yellow-50 text-yellow-800' :
                          month.isPast ? 'text-gray-700' : 'text-blue-700'
                        }`}>
                          {month.label}
                          {month.isCurrent && <span className="block text-xs font-normal text-yellow-600">Actual</span>}
                          {month.isPast && <span className="block text-xs font-normal text-gray-400">Real</span>}
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
                    
                    {/* Ingresos by Category — claves reales del dato, igual que Por Categoría */}
                    {(() => {
                      const allCats = new Set();
                      monthlyData.forEach(m => Object.keys(m.ingresos.byCategory).forEach(c => allCats.add(c)));
                      return Array.from(allCats).map(catName => {
                        const monthTotals = monthlyData.map(m => m.ingresos.byCategory[catName] || 0);
                        const total = monthTotals.reduce((s, t) => s + t, 0);
                        if (total === 0) return null;
                        return (
                          <TableRow key={`monthly-ing-${catName}`} className="hover:bg-green-50">
                            <TableCell className="sticky left-0 bg-white pl-8">{catName === 'Sin categoría' ? 'Cobranza' : catName}</TableCell>
                            {monthTotals.map((t, idx) => (
                              <TableCell key={idx} className="text-center text-green-600">
                                {t > 0 ? formatCurrency(t) : '-'}
                              </TableCell>
                            ))}
                            <TableCell className="text-center bg-green-50">{formatCurrency(total)}</TableCell>
                          </TableRow>
                        );
                      });
                    })()}

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
                    
                    {/* Egresos by Category — claves reales del dato, igual que Por Categoría */}
                    {(() => {
                      const allCats = new Set();
                      monthlyData.forEach(m => Object.keys(m.egresos.byCategory).forEach(c => allCats.add(c)));
                      return Array.from(allCats).map(catName => {
                        const monthTotals = monthlyData.map(m => m.egresos.byCategory[catName] || 0);
                        const total = monthTotals.reduce((s, t) => s + t, 0);
                        if (total === 0) return null;
                        return (
                        <TableRow key={`monthly-egr-${catName}`} className="hover:bg-red-50">
                          <TableCell className="sticky left-0 bg-white pl-8">{catName === 'Sin categoría' ? 'Proveedores Costo' : catName}</TableCell>
                          {monthTotals.map((t, idx) => (
                            <TableCell key={idx} className="text-center text-red-600">
                              {t > 0 ? formatCurrency(t) : '-'}
                            </TableCell>
                          ))}
                          <TableCell className="text-center bg-red-50">{formatCurrency(total)}</TableCell>
                        </TableRow>
                        );
                      });
                    })()}

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
                        {(selectedPartyType === 'customer' ? paymentClientes : paymentProveedores).map(party => (
                          <SelectItem key={party.id} value={party.id}>
                            <div className="flex flex-col">
                              <span className="font-medium">{party.nombre}</span>
                              <span className="text-xs text-gray-500">{party.count} mov · {formatCurrency(party.total)}</span>
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
                            No hay movimientos para este {selectedPartyType === 'customer' ? 'cliente' : 'proveedor'}
                          </TableCell>
                        </TableRow>
                      ) : (
                        getPartyCfdis().map(pago => {
                          const category = categories.find(c => c.code === pago.category_id || c.id === pago.category_id);
                          const isIngreso = pago.tipo === 'cobro';
                          
                          return (
                            <TableRow key={pago.id} className="hover:bg-gray-50">
                              <TableCell className="font-mono text-xs">{pago.cfdi_uuid?.substring(0, 8) || pago.id?.substring(0, 8)}...</TableCell>
                              <TableCell>{pago.fecha_pago ? format(new Date(pago.fecha_pago), 'dd/MM/yy') : '-'}</TableCell>
                              <TableCell>
                                <span className={`text-xs px-2 py-1 rounded ${isIngreso ? 'bg-green-100 text-green-800' : 'bg-red-100 text-red-800'}`}>
                                  {isIngreso ? '↑ Cobro' : '↓ Pago'}
                                </span>
                              </TableCell>
                              <TableCell>{category?.nombre || pago.category_name || 'Sin categoría'}</TableCell>
                              <TableCell className="text-xs">{pago.moneda || 'MXN'}</TableCell>
                              <TableCell className="text-right font-mono">{formatCurrency(pago.monto)}</TableCell>
                              <TableCell className="text-right font-mono text-gray-500">-</TableCell>
                              <TableCell className="text-right font-mono font-bold">{formatCurrency(pago.monto)}</TableCell>
                              <TableCell className="text-right font-mono text-green-600">{formatCurrency(pago.monto)}</TableCell>
                              <TableCell className="text-right font-mono font-bold text-green-600">
                                {formatCurrency(0)}
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
                          {getPartyCfdis().length} movimiento(s)
                        </div>
                        <div className="flex gap-8">
                          <div className="text-right">
                            <div className="text-xs text-gray-500">Total Cobrado/Pagado</div>
                            <div className="font-bold">{formatCurrency(getPartyCfdis().reduce((s, p) => s + (p.monto || 0), 0))}</div>
                          </div>
                          <div className="text-right">
                            <div className="text-xs text-gray-500">Ingresos</div>
                            <div className="font-bold text-green-600">
                              {formatCurrency(getPartyCfdis().filter(p => p.tipo === 'cobro').reduce((s, p) => s + (p.monto || 0), 0))}
                            </div>
                          </div>
                          <div className="text-right">
                            <div className="text-xs text-gray-500">Egresos</div>
                            <div className="font-bold text-red-600">
                              {formatCurrency(getPartyCfdis().filter(p => p.tipo === 'pago').reduce((s, p) => s + (p.monto || 0), 0))}
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

      {/* ===== KPI INSIGHT MODAL ===== */}
      <Dialog open={kpiModal.open} onOpenChange={(o) => setKpiModal(prev => ({ ...prev, open: o }))}>
        <DialogContent className="max-w-xl" data-testid="kpi-insight-modal">
          <DialogHeader className="pb-3 border-b border-slate-100">
            <DialogTitle className="flex items-start justify-between gap-3">
              <div className="flex items-center gap-2.5 text-[#0F172A]">
                {kpiModal.kpiKey === 'burnRate'    && <Activity     size={20} className="text-blue-600 flex-shrink-0" />}
                {kpiModal.kpiKey === 'cashGap'     && <AlertTriangle size={20} className={kpiModal.status === 'danger' ? 'text-red-600 flex-shrink-0' : 'text-amber-600 flex-shrink-0'} />}
                {kpiModal.kpiKey === 'volatilidad' && <BarChart3    size={20} className="text-purple-600 flex-shrink-0" />}
                {kpiModal.kpiKey === 'operativos'  && <Target       size={20} className="text-amber-600 flex-shrink-0" />}
                <span className="font-bold text-base leading-tight">{kpiModal.name}</span>
              </div>
              <span className={`flex-shrink-0 text-xs font-bold px-2.5 py-1 rounded-full ${
                kpiModal.status === 'good'    ? 'bg-green-100 text-green-700 ring-1 ring-green-200'  :
                kpiModal.status === 'warning' ? 'bg-amber-100 text-amber-700 ring-1 ring-amber-200' :
                kpiModal.status === 'danger'  ? 'bg-red-100   text-red-700   ring-1 ring-red-200'   :
                'bg-slate-100 text-slate-600 ring-1 ring-slate-200'
              }`}>
                {kpiModal.status === 'good' ? '● Favorable' : kpiModal.status === 'warning' ? '● Atención' : kpiModal.status === 'danger' ? '● Riesgo' : '● Neutral'}
              </span>
            </DialogTitle>
            {kpiModal.description && (
              <p className="text-xs text-slate-500 mt-1.5 leading-relaxed">{kpiModal.description}</p>
            )}
          </DialogHeader>

          <div className="space-y-4 mt-3 max-h-[65vh] overflow-y-auto pr-0.5">
            {/* Fórmula */}
            <div className="bg-slate-50 border border-slate-200 rounded-lg p-3">
              <div className="text-[10px] font-semibold text-slate-400 uppercase tracking-wider mb-1.5">Fórmula</div>
              <code className="text-xs text-slate-700 leading-relaxed whitespace-pre-wrap font-mono">{kpiModal.formula}</code>
            </div>

            {/* Valores que entran al cálculo */}
            <div>
              <div className="text-[10px] font-semibold text-slate-400 uppercase tracking-wider mb-2">Valores que entran al cálculo</div>
              <div className="divide-y divide-slate-100 border border-slate-100 rounded-lg overflow-hidden">
                {Object.entries(kpiModal.values).map(([k, v]) => (
                  <div key={k} className="flex justify-between items-center px-3 py-2 bg-white hover:bg-slate-50 transition-colors">
                    <span className="text-xs text-slate-500 mr-4">{k}</span>
                    <span className="text-xs font-semibold text-slate-800 text-right">{v}</span>
                  </div>
                ))}
              </div>
            </div>

            {/* Análisis AI */}
            <div className={`rounded-lg p-4 border ${
              kpiModal.status === 'good'    ? 'bg-gradient-to-br from-green-50  to-emerald-50 border-green-100'  :
              kpiModal.status === 'danger'  ? 'bg-gradient-to-br from-red-50    to-rose-50    border-red-100'    :
              kpiModal.status === 'warning' ? 'bg-gradient-to-br from-amber-50  to-yellow-50  border-amber-100'  :
              'bg-gradient-to-br from-blue-50 to-indigo-50 border-blue-100'
            }`}>
              <div className="flex items-center gap-2 mb-2.5">
                <div className="w-5 h-5 rounded-full bg-[#0F172A] flex items-center justify-center text-white text-[9px] font-bold tracking-tight flex-shrink-0">AI</div>
                <span className="text-[10px] font-semibold text-slate-600 uppercase tracking-wider">Análisis CFO · Claude Sonnet</span>
              </div>
              {kpiModal.loading ? (
                <div className="flex items-center gap-2.5 text-sm text-slate-500 py-1">
                  <div className="w-4 h-4 border-2 border-slate-400 border-t-transparent rounded-full animate-spin flex-shrink-0" />
                  <span>Analizando el contexto del negocio...</span>
                </div>
              ) : (
                <p className="text-sm text-slate-700 leading-relaxed">{kpiModal.insight}</p>
              )}
            </div>
          </div>

          <DialogFooter className="border-t border-slate-100 pt-3 mt-1">
            <Button variant="outline" size="sm" onClick={() => setKpiModal(prev => ({ ...prev, open: false }))}>
              Cerrar
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>

      {/* ===== DRILL-DOWN DIALOG ===== */}
      <Dialog open={drillDownOpen} onOpenChange={setDrillDownOpen}>
        <DialogContent className="max-w-5xl max-h-[85vh] overflow-hidden flex flex-col">
          <DialogHeader>
            <DialogTitle className="flex items-center gap-3">
              <Eye size={20} className={drillDownData.tipo === 'ingreso' ? 'text-green-600' : 'text-red-600'} />
              <span>
                Detalle: {drillDownData.categoryName}
                {drillDownData.subcategoryName && ` > ${drillDownData.subcategoryName}`}
              </span>
              <Badge variant={drillDownData.dataType === 'real' ? 'default' : drillDownData.dataType === 'actual' ? 'secondary' : 'outline'}>
                {drillDownData.weekLabel} - {drillDownData.dataType === 'real' ? 'Real' : drillDownData.dataType === 'actual' ? 'Actual' : 'Proyectado'}
              </Badge>
            </DialogTitle>
          </DialogHeader>
          
          <div className="flex-1 overflow-auto">
            {/* Summary */}
            <div className="grid grid-cols-3 gap-4 mb-4 p-4 bg-gray-50 rounded-lg">
              <div>
                <div className="text-xs text-gray-500">Semana</div>
                <div className="font-bold">{drillDownData.weekLabel} ({drillDownData.dateLabel})</div>
              </div>
              <div>
                <div className="text-xs text-gray-500">Tipo</div>
                <div className={`font-bold ${drillDownData.tipo === 'ingreso' ? 'text-green-600' : 'text-red-600'}`}>
                  {drillDownData.tipo === 'ingreso' ? '↑ Ingreso' : '↓ Egreso'}
                </div>
              </div>
              <div>
                <div className="text-xs text-gray-500">Total</div>
                <div className="font-bold text-lg">{formatCurrency(drillDownData.total)}</div>
              </div>
            </div>

            {/* Items Table */}
            <Table>
              <TableHeader>
                <TableRow className="bg-gray-100">
                  <TableHead className="w-[180px]">Proveedor/Cliente</TableHead>
                  <TableHead className="w-[100px]">UUID</TableHead>
                  <TableHead className="w-[90px]">Fecha</TableHead>
                  <TableHead className="text-right w-[100px]">Monto</TableHead>
                  <TableHead className="w-[70px]">Moneda</TableHead>
                  <TableHead className="text-right w-[110px]">Monto MXN</TableHead>
                  <TableHead className="w-[180px]">Mov. Bancario</TableHead>
                  <TableHead className="w-[90px] text-center">Conciliado</TableHead>
                </TableRow>
              </TableHeader>
              <TableBody>
                {drillDownData.items.length === 0 ? (
                  <TableRow>
                    <TableCell colSpan={8} className="text-center py-8 text-gray-500">
                      No hay items para mostrar
                    </TableCell>
                  </TableRow>
                ) : (
                  drillDownData.items.map((item, idx) => (
                    <TableRow key={idx} className="hover:bg-gray-50">
                      <TableCell>
                        <div className="flex items-center gap-2">
                          {item.terceroTipo === 'cliente' ? (
                            <User size={14} className="text-blue-500" />
                          ) : (
                            <Building2 size={14} className="text-orange-500" />
                          )}
                          <span className="truncate max-w-[150px]" title={item.tercero}>
                            {item.tercero || 'Sin asignar'}
                          </span>
                        </div>
                      </TableCell>
                      <TableCell className="font-mono text-xs">
                        {item.uuid ? (
                          <span title={item.uuid}>{item.uuid.substring(0, 8)}...</span>
                        ) : '-'}
                      </TableCell>
                      <TableCell className="text-xs">
                        {item.fechaFactura ? format(new Date(item.fechaFactura), 'dd/MM/yy') : '-'}
                      </TableCell>
                      <TableCell className="text-right font-mono text-sm">
                        {formatCurrency(item.montoOriginal || item.monto)}
                      </TableCell>
                      <TableCell>
                        <Badge variant="outline" className="text-xs">
                          {item.moneda || 'MXN'}
                        </Badge>
                      </TableCell>
                      <TableCell className="text-right font-mono text-sm font-bold">
                        {formatCurrency(item.monto)}
                      </TableCell>
                      <TableCell className="text-xs">
                        {item.bankTxnDescripcion ? (
                          <span className="truncate max-w-[170px] block" title={item.bankTxnDescripcion}>
                            {item.bankTxnDescripcion}
                          </span>
                        ) : (
                          <span className="text-gray-400">-</span>
                        )}
                      </TableCell>
                      <TableCell className="text-center">
                        {item.conciliado ? (
                          <span className="inline-flex items-center justify-center w-6 h-6 bg-green-100 rounded-full">
                            <Check size={14} className="text-green-600" />
                          </span>
                        ) : (
                          <span className="inline-flex items-center justify-center w-6 h-6 bg-gray-100 rounded-full">
                            <XIcon size={14} className="text-gray-400" />
                          </span>
                        )}
                      </TableCell>
                    </TableRow>
                  ))
                )}
              </TableBody>
            </Table>
          </div>
          
          <DialogFooter className="border-t pt-4">
            <div className="flex justify-between items-center w-full">
              <div className="text-sm text-gray-500">
                {drillDownData.items.length} movimiento(s)
              </div>
              <Button variant="outline" onClick={() => setDrillDownOpen(false)}>
                Cerrar
              </Button>
            </div>
          </DialogFooter>
        </DialogContent>
      </Dialog>
    </div>
  );
};

export default CashflowProjections;
