import { useState, useEffect, useMemo } from 'react';
import api from '@/api/axios';
import { getERPEndpoints } from '@/utils/erpHelper';
import PageHeader from '@/components/PageHeader';
import { Card, CardContent, CardHeader, CardTitle, CardDescription } from '@/components/ui/card';
import { Tabs, TabsContent, TabsList, TabsTrigger } from '@/components/ui/tabs';
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from '@/components/ui/table';
import { Button } from '@/components/ui/button';
import { Input } from '@/components/ui/input';
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from '@/components/ui/select';
import { toast } from 'sonner';
import { TrendingUp, TrendingDown, Clock, AlertTriangle, Calendar, Download, FileText, Building2, User, RefreshCw, Filter, X, Search, Tag } from 'lucide-react';
import { format, differenceInDays, parseISO, isAfter, isBefore, isValid } from 'date-fns';
import { es } from 'date-fns/locale';
import { exportAging, exportToExcel } from '@/utils/excelExport';

const AgingModule = () => {
  const [loading, setLoading] = useState(true);
  const [cfdis, setCfdis] = useState([]);
  const [customers, setCustomers] = useState([]);
  const [vendors, setVendors] = useState([]);
  const [fxRates, setFxRates] = useState({ USD: 17.5, EUR: 19.0 });
  const [syncingRates, setSyncingRates] = useState(false);
  const [displayCurrency, setDisplayCurrency] = useState('MXN');
  const [activeTab, setActiveTab] = useState('cxc'); // cxc = Cuentas por Cobrar, cxp = Cuentas por Pagar

  // Filtros para CxC
  const [cxcFilters, setCxcFilters] = useState({
    cliente: '',
    moneda: 'todas',
    antiguedad: 'todas',
    semanaProyectada: 'todas',
    fechaDesde: '',
    fechaHasta: ''
  });

  // Filtros para CxP
  const [cxpFilters, setCxpFilters] = useState({
    proveedor: '',
    moneda: 'todas',
    antiguedad: 'todas',
    semanaProyectada: 'todas',
    fechaDesde: '',
    fechaHasta: ''
  });

  const [uploadingCxC, setUploadingCxC] = useState(false);
  const [uploadingCxP, setUploadingCxP] = useState(false);
  const [oficialTotalCxC, setOficialTotalCxC] = useState(null);
  const [oficialTotalCxP, setOficialTotalCxP] = useState(null);
  const [proyecciones, setProyecciones] = useState({}); // { "CLIENTE X_cxc": "S3", ... }
  const [proyDocs, setProyDocs] = useState([]);          // docs completos de /cxc-proyecciones (incluyen monto guardado)
  const [semanaFiltro, setSemanaFiltro] = useState({ cxc: 'todas', cxp: 'todas' }); // filtro de la tabla Totales por Semana
  const [syncingProy, setSyncingProy] = useState(false);   // sincronización de montos con Aging
  const [historialSync, setHistorialSync] = useState([]);  // histórico de diferencias (cxc_proyecciones_hist)
  const [semanasModelo, setSemanasModelo] = useState([]); // semanas proyectadas del modelo
  const [categorias, setCategorias] = useState({});       // { "NOMBRE_tipo": { code, name } }
  const [catalogoCategorias, setCatalogoCategorias] = useState([]); // [{id, nombre, tipo, code}] para Alegra
  const [autoCategorizing, setAutoCategorizing] = useState(false);
  const [currentPage, setCurrentPage] = useState({ cxc: 1, cxp: 1 });

  useEffect(() => {
    loadData();
  }, []);

  const loadData = async (forceRefresh = false) => {
    setLoading(true);
    const refreshParam = forceRefresh ? '?refresh=true' : '';
    try {
      const [cxcRes, cxpRes, fxRes, proyRes, semanasRes, catRes, histRes] = await Promise.all([
        api.get(`${getERPEndpoints().cxcEndpoint}${refreshParam}`),
        api.get(`${getERPEndpoints().cxpEndpoint}${refreshParam}`),
        api.get('/fx-rates/latest'),
        api.get('/cxc-proyecciones').catch(() => ({ data: [] })),
        api.get('/cxc-proyecciones/semanas-modelo').catch(() => ({ data: [] })),
        getERPEndpoints().usaAlegra
          ? api.get('/cashflow-sync/categories').catch(() => ({ data: [] }))
          : api.get('/contalink/categorias-cxc').catch(() => ({ data: { categorias_guardadas: [] } })),
        api.get('/cxc-proyecciones/historial-sync').catch(() => ({ data: [] })),
      ]);

      const toLocal = (facturas, tipo) => (facturas || []).map(f => {
        const diasVenc = f.dias_vencido || 0;
        const fechaVencCalc = new Date();
        fechaVencCalc.setDate(fechaVencCalc.getDate() - diasVenc);
        return {
          id:               f.uuid || f.cuenta || f.nombre || Math.random().toString(36),
          uuid:             f.uuid || '',
          fecha_emision:    f.fecha_emision || '',
          fecha_vencimiento: f.fecha_vencimiento || fechaVencCalc.toISOString().split('T')[0],
          // total_original = monto en la moneda del documento (USD/EUR/MXN)
          // total          = monto en MXN (para cálculos internos del frontend)
          // pendiente      = saldo en moneda original (lo que muestra la columna "Pendiente")
          // pendienteMXN   = saldo en MXN (lo que muestra la columna "Pend. MXN")
          total:            f.total_original != null ? f.total_original : (f.total || f.saldo_pendiente || 0),
          totalMXN:         f.total || f.saldo_pendiente || 0,
          monto_cobrado:    f.monto_cobrado || 0,
          monto_pagado:     f.monto_pagado  || 0,
          moneda:           f.moneda || 'MXN',
          tipo_cfdi:        tipo === 'cxc' ? 'ingreso' : 'egreso',
          receptor_nombre:  f.cliente_nombre  || f.nombre || '',
          receptor_rfc:     f.cliente_rfc     || '',
          emisor_nombre:    f.proveedor_nombre || f.nombre || '',
          emisor_rfc:       f.proveedor_rfc    || '',
          plazo:            0,
          pendiente:        f.saldo_original != null ? f.saldo_original : (f.saldo_pendiente || f.total_original || 0),
          pendienteMXN:     f.saldo_mxn      != null ? f.saldo_mxn      : (f.saldo_pendiente || f.total || 0),
          // Desglose por bucket del Excel de Contalink (cuando existe):
          // permite repartir el saldo de un proveedor entre varias tarjetas de antigüedad
          desglose_aging: (f.por_vencer != null || f.vencido_1_30 != null || f.vencido_mas90 != null ||
                           f.vencido_91_120 != null || f.vencido_mas120 != null) ? {
            'vigente': f.por_vencer || 0,
            '1-30':    f.vencido_1_30 || 0,
            '31-60':   f.vencido_31_60 || 0,
            '61-90':   f.vencido_61_90 || 0,
            '91-120':  (f.vencido_91_120 || 0) + (f.vencido_mas90 || 0),
            '120+':    f.vencido_mas120 || 0,
          } : null,
        };
      });

      const cxcFacturas = toLocal(cxcRes.data?.facturas, 'cxc');
      const cxpFacturas = toLocal(cxpRes.data?.facturas, 'cxp');
      setCfdis([...cxcFacturas, ...cxpFacturas]);
      // Guardar totales oficiales del backend (incluyen resta de NC)
      if (cxcRes.data?.total_pendiente != null) setOficialTotalCxC(cxcRes.data.total_pendiente);
      if (cxpRes.data?.total_pendiente != null) setOficialTotalCxP(cxpRes.data.total_pendiente);

      // Construir mapa de proyecciones: { "NOMBRE_tipo": "S3" }
      const proyMap = {};
      (proyRes.data || []).forEach(p => {
        proyMap[`${p.nombre}_${p.tipo}`] = p.semana;
      });
      setProyecciones(proyMap);
      setProyDocs(proyRes.data || []);
      setSemanasModelo(semanasRes.data || []);
      setHistorialSync(histRes.data || []);

      // Construir mapa de categorías: { "NOMBRE_tipo": { code, name } }
      const catMap = {};
      if (getERPEndpoints().usaAlegra) {
        const catList = Array.isArray(catRes.data) ? catRes.data : [];
        setCatalogoCategorias(catList);
      } else {
        const catData = catRes.data?.categorias_guardadas || [];
        catData.forEach(c => {
          catMap[`${c.nombre}_${c.tipo}`] = { code: c.category_code, name: c.category_name };
        });
      }
      setCategorias(catMap);

      const rawRates = fxRes.data?.rates;
      let ratesObj = {};
      if (Array.isArray(rawRates)) {
        rawRates.forEach(r => {
          if (r.moneda && r.tasa_mxn) ratesObj[r.moneda] = r.tasa_mxn;
          else if (r.moneda_origen && r.tasa) ratesObj[r.moneda_origen] = r.tasa;
        });
      } else if (rawRates && typeof rawRates === 'object') {
        ratesObj = { ...rawRates };
      }
      if (!ratesObj.USD) ratesObj.USD = 17.5;
      if (!ratesObj.EUR) ratesObj.EUR = 19.0;
      setFxRates(ratesObj);
    } catch (error) {
      console.error('Error cargando CxC/CxP:', error);
      toast.error('Error cargando datos');
    } finally {
      setLoading(false);
    }
  };

  const handleAsignarSemana = async (nombre, tipo, semana, monto) => {
    try {
      await api.post('/cxc-proyecciones', { nombre, tipo, semana, monto, moneda: 'MXN' });
      setProyecciones(prev => ({ ...prev, [`${nombre}_${tipo}`]: semana }));
      setProyDocs(prev => {
        const rest = prev.filter(p => !(p.nombre === nombre && p.tipo === tipo));
        return [...rest, { nombre, tipo, semana, monto, moneda: 'MXN' }];
      });
      toast.success(`${nombre} asignado a ${semana || 'sin semana'}`);
    } catch (err) {
      toast.error('Error guardando proyección');
    }
  };

  const handleSincronizarMontos = async (tipo) => {
    const label = tipo === 'cxc' ? 'CxC' : 'CxP';
    const ok = window.confirm(
      `Sincronizar montos de ${label} con el Aging actual:\n\n` +
      `• Los que ya NO están en el Aging se eliminarán del Cash Flow (se asumen ${tipo === 'cxc' ? 'cobrados' : 'pagados'})\n` +
      `• Los montos desactualizados se reemplazarán por el pendiente actual\n\n` +
      `Cada cambio queda registrado en el histórico Proyectado vs Pagado. ¿Continuar?`
    );
    if (!ok) return;
    setSyncingProy(true);
    try {
      const res = await api.post(`/cxc-proyecciones/sincronizar?tipo=${tipo}`);
      const { actualizados, eliminados, sin_cambio } = res.data;
      toast.success(`Sincronizado ${label}: ${actualizados} actualizado(s), ${eliminados} eliminado(s), ${sin_cambio} sin cambio`);
      await loadData();
    } catch (err) {
      toast.error(err.response?.data?.detail || 'Error sincronizando montos');
    } finally {
      setSyncingProy(false);
    }
  };

  const handleAutoCategorize = async () => {
    setAutoCategorizing(true);
    try {
      const res = await api.post('/contalink/auto-categorize-cxc?solo_sin_categoria=true');
      const { updated, processed } = res.data;
      if (updated > 0) {
        toast.success(`✅ ${updated} de ${processed} clientes/proveedores categorizados con IA`);
        await loadData();
      } else {
        toast.info('Todos ya tienen categoría asignada');
      }
    } catch (err) {
      toast.error(err.response?.data?.detail || 'Error en categorización IA');
    } finally {
      setAutoCategorizing(false);
    }
  };

  const handleCategoriaManual = async (nombre, tipo, category_code, category_name) => {
    try {
      await api.post('/contalink/categoria-cxc', { nombre, tipo, category_code, category_name });
      setCategorias(prev => ({ ...prev, [`${nombre}_${tipo}`]: { code: category_code, name: category_name } }));
      toast.success(`Categoría actualizada: ${category_name}`);
    } catch (err) {
      toast.error('Error guardando categoría');
    }
  };

  const handleUploadExcel = async (e, tipo) => {
    const file = e.target.files[0];
    if (!file) return;
    const setter = tipo === 'cxc' ? setUploadingCxC : setUploadingCxP;
    setter(true);
    try {
      const formData = new FormData();
      formData.append('file', file);
      const res = await api.post(`/contalink/upload-${tipo}`, formData, {
        headers: { 'Content-Type': 'multipart/form-data' }
      });
      const label = tipo === 'cxc' ? 'CxC' : 'CxP';
      const count = res.data?.num_facturas || res.data?.num_clientes || res.data?.num_proveedores || 0;
      toast.success(`✅ Excel ${label}: ${count} registros · $${(res.data?.total_pendiente || 0).toLocaleString('es-MX', {minimumFractionDigits: 2})}`);
      await loadData(true); // Forzar refresh del caché después del upload
    } catch (err) {
      toast.error(err.response?.data?.detail || `Error importando Excel ${tipo.toUpperCase()}`);
    } finally {
      setter(false);
      e.target.value = '';
    }
  };

  const syncFxRates = async () => {
    setSyncingRates(true);
    try {
      const res = await api.post('/fx-rates/sync');
      if (res.data.rates) {
        const ratesObj = {};
        res.data.rates.forEach(r => {
          if (r.moneda && r.tasa_mxn) ratesObj[r.moneda] = r.tasa_mxn;
          else if (r.moneda_origen && r.tasa) ratesObj[r.moneda_origen] = r.tasa;
        });
        if (!ratesObj.USD) ratesObj.USD = 17.5;
        if (!ratesObj.EUR) ratesObj.EUR = 19.0;
        setFxRates(ratesObj);
        toast.success(`Tipos de cambio actualizados`);
      }
    } catch (error) {
      toast.error('Error sincronizando tipos de cambio');
    } finally {
      setSyncingRates(false);
    }
  };

  // Calcula la semana del modelo de proyecciones (S1, S2...) para una fecha de vencimiento
  const getProyeccionSemana = (fechaVenc) => {
    if (!fechaVenc) return null;
    const today = new Date();
    today.setHours(0, 0, 0, 0);
    const fv = new Date(fechaVenc);
    fv.setHours(0, 0, 0, 0);
    const diffDays = Math.ceil((fv - today) / 86400000);
    if (diffDays < 0) return null; // Ya vencida — no proyectar
    const semana = Math.floor(diffDays / 7) + 1;
    if (semana > 18) return null; // Fuera del horizonte de 18 semanas
    return `S${semana}`;
  };

  const formatCurrency = (amount, moneda = 'MXN') => {
    const symbol = moneda === 'USD' ? 'US$' : moneda === 'EUR' ? '€' : '$';
    return `${symbol}${(amount || 0).toLocaleString('es-MX', { minimumFractionDigits: 2, maximumFractionDigits: 2 })}`;
  };

  // Convert to MXN using fx rates
  // Prefers the invoice-level tipo_cambio when available for accuracy
  const convertToMXN = (amount, moneda, tipoCambio = null) => {
    if (!moneda || moneda === 'MXN') return amount;
    const rate = tipoCambio && tipoCambio > 0 ? tipoCambio : (fxRates[moneda] || 1);
    return amount * rate;
  };

  // Convert MXN to display currency
  const fromMXN = (amountMXN, targetCurrency) => {
    if (!targetCurrency || targetCurrency === 'MXN') return amountMXN;
    const rate = fxRates[targetCurrency] || 1;
    return amountMXN / rate;
  };

  // Get the due date for a CFDI based on:
  // 1. fecha_vencimiento if exists
  // 2. fecha_emision + plazo_pago/plazo_cobranza from vendor/customer
  // 3. fecha_emision + 30 days as default
  const getDueDate = (cfdi, tipo) => {
    // If CFDI has explicit due date, use it
    if (cfdi.fecha_vencimiento) {
      return new Date(cfdi.fecha_vencimiento);
    }
    
    const fechaEmision = cfdi.fecha_emision ? new Date(cfdi.fecha_emision) : new Date();
    let plazoDias = 30; // Default: 30 days
    
    if (tipo === 'cxc') {
      // For Accounts Receivable (CxC): use customer's plazo_cobranza
      const customer = customers.find(c => c.id === cfdi.customer_id || c.rfc === cfdi.receptor_rfc);
      if (customer && customer.plazo_cobranza !== null && customer.plazo_cobranza !== undefined) {
        plazoDias = customer.plazo_cobranza;
      }
    } else {
      // For Accounts Payable (CxP): use vendor's plazo_pago
      const vendor = vendors.find(v => v.id === cfdi.vendor_id || v.rfc === cfdi.emisor_rfc);
      if (vendor && vendor.plazo_pago !== null && vendor.plazo_pago !== undefined) {
        plazoDias = vendor.plazo_pago;
      }
    }
    
    // Add plazo days to emission date
    const dueDate = new Date(fechaEmision);
    dueDate.setDate(dueDate.getDate() + plazoDias);
    return dueDate;
  };

  // Calculate aging bucket based on days past due date
  const getAgingBucket = (cfdi, tipo) => {
    const today = new Date();
    const dueDate = getDueDate(cfdi, tipo);
    const diasVencido = differenceInDays(today, dueDate);
    
    // If due date is in the future, it's not due yet
    if (diasVencido <= 0) return 'vigente';
    if (diasVencido <= 30) return '1-30';
    if (diasVencido <= 60) return '31-60';
    if (diasVencido <= 90) return '61-90';
    if (diasVencido <= 120) return '91-120';
    return '120+';
  };

  // Get days past due for a CFDI
  const getDaysOverdue = (cfdi, tipo) => {
    const today = new Date();
    const dueDate = getDueDate(cfdi, tipo);
    return differenceInDays(today, dueDate);
  };

  // Get the plazo (credit terms) for a CFDI
  const getPlazo = (cfdi, tipo) => {
    if (tipo === 'cxc') {
      const customer = customers.find(c => c.id === cfdi.customer_id || c.rfc === cfdi.receptor_rfc);
      return customer?.plazo_cobranza ?? 30;
    } else {
      const vendor = vendors.find(v => v.id === cfdi.vendor_id || v.rfc === cfdi.emisor_rfc);
      return vendor?.plazo_pago ?? 30;
    }
  };

  // Process CFDIs for aging
  const processAging = (tipo) => {
    const isIngreso = tipo === 'cxc';
    const filtered = cfdis.filter(cfdi => {
      if (cfdi.tipo_cfdi !== (isIngreso ? 'ingreso' : 'egreso')) return false;
      if (cfdi.estado_cancelacion === 'cancelado') return false;
      
      // Check pending balance — incluir NC (pendiente negativo) para mostrar en Aging
      const amountField = isIngreso ? 'monto_cobrado' : 'monto_pagado';
      const retenciones = isIngreso ? 0 : ((cfdi.isr_retenido || 0) + (cfdi.iva_retenido || 0));
      const pendiente = (cfdi.total - retenciones) - (cfdi[amountField] || 0);
      return pendiente > 0.01 || pendiente < -0.01; // incluir NC (negativos)
    });

    // Group by aging bucket
    const buckets = {
      'vigente': { label: 'Vigente', cfdis: [], total: 0, totalMXN: 0, numFacturas: 0, color: 'bg-green-100 text-green-800' },
      '1-30': { label: '1-30 días', cfdis: [], total: 0, totalMXN: 0, numFacturas: 0, color: 'bg-yellow-100 text-yellow-800' },
      '31-60': { label: '31-60 días', cfdis: [], total: 0, totalMXN: 0, numFacturas: 0, color: 'bg-orange-100 text-orange-800' },
      '61-90': { label: '61-90 días', cfdis: [], total: 0, totalMXN: 0, numFacturas: 0, color: 'bg-red-100 text-red-800' },
      '91-120': { label: '91-120 días', cfdis: [], total: 0, totalMXN: 0, numFacturas: 0, color: 'bg-red-200 text-red-900' },
      '120+': { label: '+120 días', cfdis: [], total: 0, totalMXN: 0, numFacturas: 0, color: 'bg-red-300 text-red-900' }
    };

    filtered.forEach(cfdi => {
      const bucket = getAgingBucket(cfdi, tipo);
      const amountField = isIngreso ? 'monto_cobrado' : 'monto_pagado';
      const retenciones = isIngreso ? 0 : ((cfdi.isr_retenido || 0) + (cfdi.iva_retenido || 0));

      // pendiente = saldo en MONEDA ORIGINAL (para mostrar en columna "Pendiente")
      // pendienteMXN = saldo en MXN (para totales, aging, columna "Pend. MXN")
      const pendiente    = cfdi.pendiente    > 0 ? cfdi.pendiente    : Math.max(0, cfdi.total - retenciones - (cfdi[amountField] || 0));
      const pendienteMXN = cfdi.pendienteMXN > 0 ? cfdi.pendienteMXN : convertToMXN(pendiente, cfdi.moneda || 'MXN', cfdi.tipo_cambio);

      const moneda = cfdi.moneda || 'MXN';
      const dueDate = getDueDate(cfdi, tipo);
      const diasVencido = getDaysOverdue(cfdi, tipo);
      const plazo = getPlazo(cfdi, tipo);

      // Retención implícita — solo aplica a MXN (personas físicas)
      const esRetencion = !isIngreso && moneda === 'MXN' &&
        cfdi.isr_retenido === 0 && cfdi.iva_retenido === 0 &&
        pendiente > 0 && (pendiente / (cfdi.total || 1)) <= 0.15;

      buckets[bucket].cfdis.push({
        ...cfdi,
        pendiente,
        pendienteMXN,
        moneda,
        fechaVencimiento: dueDate,
        diasVencido,
        plazo,
        esRetencion,
        retencionSAT: esRetencion ? pendiente : 0,
      });

      // Si el Excel de Contalink trae el desglose por columnas (Vigente, 1-30...+120),
      // repartir el saldo del proveedor entre los buckets reales en lugar de
      // acumular todo en el bucket de mayor antigüedad
      const tieneDesglose = cfdi.desglose_aging &&
        Object.values(cfdi.desglose_aging).some(v => Math.abs(v) > 0.01);
      if (tieneDesglose) {
        Object.entries(cfdi.desglose_aging).forEach(([bKey, amt]) => {
          if (!amt) return;
          buckets[bKey].total += amt;
          buckets[bKey].totalMXN += convertToMXN(amt, moneda, cfdi.tipo_cambio);
          buckets[bKey].numFacturas += 1;
        });
      } else {
        buckets[bucket].total += pendiente;
        buckets[bucket].totalMXN += pendienteMXN;
        buckets[bucket].numFacturas += 1;
      }
    });

    return buckets;
  };

  // Get party name
  const getPartyName = (cfdi, tipo) => {
    if (tipo === 'cxc') {
      const customer = customers.find(c => c.id === cfdi.customer_id || c.rfc === cfdi.receptor_rfc);
      return customer?.nombre || cfdi.receptor_nombre || 'Sin asignar';
    } else {
      const vendor = vendors.find(v => v.id === cfdi.vendor_id || v.rfc === cfdi.emisor_rfc);
      return vendor?.nombre || cfdi.emisor_nombre || 'Sin asignar';
    }
  };

  // Apply filters to processed CFDIs
  const applyFilters = (allCfdis, tipo, filters) => {
    let filtered = [...allCfdis];
    
    // Filter by cliente/proveedor name
    const searchTerm = tipo === 'cxc' ? filters.cliente : filters.proveedor;
    if (searchTerm && searchTerm.trim() !== '') {
      const term = searchTerm.toLowerCase();
      filtered = filtered.filter(cfdi => {
        const partyName = getPartyName(cfdi, tipo).toLowerCase();
        return partyName.includes(term);
      });
    }
    
    // Filter by moneda
    if (filters.moneda && filters.moneda !== 'todas') {
      filtered = filtered.filter(cfdi => (cfdi.moneda || 'MXN') === filters.moneda);
    }
    
    // Filter by antiguedad bucket
    if (filters.antiguedad && filters.antiguedad !== 'todas') {
      filtered = filtered.filter(cfdi => {
        const bucket = getAgingBucket(cfdi, tipo);
        return bucket === filters.antiguedad;
      });
    }

    // Filter by semana proyectada (columna Proyección)
    if (filters.semanaProyectada && filters.semanaProyectada !== 'todas') {
      filtered = filtered.filter(cfdi => {
        const semana = proyecciones[`${getPartyName(cfdi, tipo)}_${tipo}`] || '';
        return filters.semanaProyectada === 'sin-asignar'
          ? !semana
          : semana === filters.semanaProyectada;
      });
    }
    
    // Filter by fecha desde
    if (filters.fechaDesde && filters.fechaDesde.trim() !== '') {
      const fromDate = parseISO(filters.fechaDesde);
      if (isValid(fromDate)) {
        filtered = filtered.filter(cfdi => {
          const emisionDate = cfdi.fecha_emision ? new Date(cfdi.fecha_emision) : new Date();
          return !isBefore(emisionDate, fromDate);
        });
      }
    }
    
    // Filter by fecha hasta
    if (filters.fechaHasta && filters.fechaHasta.trim() !== '') {
      const toDate = parseISO(filters.fechaHasta);
      if (isValid(toDate)) {
        filtered = filtered.filter(cfdi => {
          const emisionDate = cfdi.fecha_emision ? new Date(cfdi.fecha_emision) : new Date();
          return !isAfter(emisionDate, toDate);
        });
      }
    }
    
    return filtered;
  };

  // Get unique currencies from CFDIs
  const getUniqueCurrencies = (tipo) => {
    const isIngreso = tipo === 'cxc';
    const filtered = cfdis.filter(cfdi => {
      if (cfdi.tipo_cfdi !== (isIngreso ? 'ingreso' : 'egreso')) return false;
      if (cfdi.estado_cancelacion === 'cancelado') return false;
      const amountField = isIngreso ? 'monto_cobrado' : 'monto_pagado';
      const retenciones = isIngreso ? 0 : ((cfdi.isr_retenido || 0) + (cfdi.iva_retenido || 0));
      const pendiente = (cfdi.total - retenciones) - (cfdi[amountField] || 0);
      return pendiente > 0.01;
    });
    
    const currencies = new Set(filtered.map(cfdi => cfdi.moneda || 'MXN'));
    return Array.from(currencies).sort();
  };

  // Reset filters
  const resetFilters = (tipo) => {
    if (tipo === 'cxc') {
      setCxcFilters({
        cliente: '',
        moneda: 'todas',
        antiguedad: 'todas',
        semanaProyectada: 'todas',
        fechaDesde: '',
        fechaHasta: ''
      });
    } else {
      setCxpFilters({
        proveedor: '',
        moneda: 'todas',
        antiguedad: 'todas',
        semanaProyectada: 'todas',
        fechaDesde: '',
        fechaHasta: ''
      });
    }
  };

  // Check if filters are active
  const hasActiveFilters = (tipo) => {
    const filters = tipo === 'cxc' ? cxcFilters : cxpFilters;
    const searchTerm = tipo === 'cxc' ? filters.cliente : filters.proveedor;
    return (
      (searchTerm && searchTerm.trim() !== '') ||
      filters.moneda !== 'todas' ||
      filters.antiguedad !== 'todas' ||
      (filters.semanaProyectada || 'todas') !== 'todas' ||
      (filters.fechaDesde && filters.fechaDesde.trim() !== '') ||
      (filters.fechaHasta && filters.fechaHasta.trim() !== '')
    );
  };

  if (loading) return <div className="p-8">Cargando...</div>;

  const cxcBuckets = processAging('cxc');
  const cxpBuckets = processAging('cxp');

  const totalCxC = Object.values(cxcBuckets).reduce((s, b) => s + b.total, 0);
  const totalCxP = Object.values(cxpBuckets).reduce((s, b) => s + b.total, 0);
  const totalCxCMXN = oficialTotalCxC != null ? oficialTotalCxC : Object.values(cxcBuckets).reduce((s, b) => s + b.totalMXN, 0);
  const totalCxPMXN = oficialTotalCxP != null ? oficialTotalCxP : Object.values(cxpBuckets).reduce((s, b) => s + b.totalMXN, 0);
  const totalCxCDisplay = fromMXN(totalCxCMXN, displayCurrency);
  const totalCxPDisplay = fromMXN(totalCxPMXN, displayCurrency);

  // Currency options
  const cxcCurrencies = getUniqueCurrencies('cxc');
  const cxpCurrencies = getUniqueCurrencies('cxp');

  // Export filtered data to Excel
  const handleExportFiltered = (filteredCfdis, tipo, isFiltered) => {
    if (filteredCfdis.length === 0) {
      toast.error('No hay datos para exportar');
      return;
    }

    const exportData = filteredCfdis.map(cfdi => {
      const bucket = getAgingBucket(cfdi, tipo);
      const bucketLabel = {
        'vigente': 'Vigente',
        '1-30': '1-30 días',
        '31-60': '31-60 días',
        '61-90': '61-90 días',
        '91-120': '91-120 días',
        '120+': '+120 días'
      }[bucket] || bucket;
      
      const pagado = tipo === 'cxc' ? (cfdi.monto_cobrado || 0) : (cfdi.monto_pagado || 0);
      
      return {
        'Antigüedad': bucketLabel,
        [tipo === 'cxc' ? 'Cliente' : 'Proveedor']: getPartyName(cfdi, tipo),
        'UUID': cfdi.uuid || '',
        'Fecha Emisión': (cfdi.fecha_emision ? format(new Date(cfdi.fecha_emision), 'dd/MM/yyyy') : 'N/A'),
        'Plazo': cfdi.plazo === 0 ? 'Contado' : `${cfdi.plazo} días`,
        'Vencimiento': format(cfdi.fechaVencimiento, 'dd/MM/yyyy'),
        'Días Vencido': cfdi.diasVencido,
        'Moneda': cfdi.moneda || 'MXN',
        'Total': cfdi.total,
        'Pagado': pagado,
        'Pendiente': cfdi.pendiente,
        'Pendiente MXN': cfdi.pendienteMXN
      };
    });

    const tipoNombre = tipo === 'cxc' ? 'CxC' : 'CxP';
    const filename = isFiltered ? `Aging_${tipoNombre}_Filtrado` : `Aging_${tipoNombre}`;
    
    const success = exportToExcel(exportData, filename, `${tipoNombre} Pendientes`);
    if (success) {
      toast.success(`${isFiltered ? 'Datos filtrados exportados' : 'Datos exportados'} a Excel`);
    } else {
      toast.error('Error al exportar');
    }
  };

  // Aging bucket options
  const agingOptions = [
    { value: 'todas', label: 'Todas' },
    { value: 'vigente', label: 'Vigente' },
    { value: '1-30', label: '1-30 días' },
    { value: '31-60', label: '31-60 días' },
    { value: '61-90', label: '61-90 días' },
    { value: '91-120', label: '91-120 días' },
    { value: '120+', label: '+120 días' }
  ];

  const renderAgingTable = (buckets, tipo) => {
    const allCfdis = Object.values(buckets).flatMap(b => b.cfdis);
    const filters = tipo === 'cxc' ? cxcFilters : cxpFilters;
    const filteredCfdis = applyFilters(allCfdis, tipo, filters);
    const currencies = tipo === 'cxc' ? cxcCurrencies : cxpCurrencies;
    const isFiltered = hasActiveFilters(tipo);
    const ITEMS_PER_PAGE = 50;
    const sortedCfdis = [...filteredCfdis].sort((a, b) => b.diasVencido - a.diasVencido);
    const totalPages = Math.ceil(sortedCfdis.length / ITEMS_PER_PAGE);
    const page = currentPage[tipo];
    const pagedCfdis = sortedCfdis.slice((page - 1) * ITEMS_PER_PAGE, page * ITEMS_PER_PAGE);
    
    // Recalculate totals based on filtered data
    const filteredTotalMXN = filteredCfdis.reduce((sum, cfdi) => sum + cfdi.pendienteMXN, 0);

    // ── Totales por Semana Proyectada ──
    // Agrupa las facturas pendientes por la semana asignada en la columna Proyección
    // y las compara contra el monto guardado que pasa al Cash Flow
    const semanaInfo = new Map(semanasModelo.map((s, i) => [s.label, { ...s, idx: i }]));
    const semanaOrd = (label) => semanaInfo.has(label)
      ? semanaInfo.get(label).idx
      : 1000 + (parseInt(String(label).replace(/\D/g, ''), 10) || 0);
    const porSemana = {};
    const sinAsignar = { count: 0, totalMXN: 0 };
    allCfdis.forEach(cfdi => {
      const nombre = getPartyName(cfdi, tipo);
      const semana = proyecciones[`${nombre}_${tipo}`];
      if (!semana) {
        sinAsignar.count += 1;
        sinAsignar.totalMXN += cfdi.pendienteMXN;
        return;
      }
      if (!porSemana[semana]) porSemana[semana] = { count: 0, totalMXN: 0, montoCashflow: 0, agingItems: [], cfItems: [] };
      porSemana[semana].count += 1;
      porSemana[semana].totalMXN += cfdi.pendienteMXN;
      porSemana[semana].agingItems.push({ nombre, monto: cfdi.pendienteMXN });
    });
    // Monto guardado en cxc_proyecciones (lo que realmente pasa al Cash Flow)
    proyDocs.filter(p => p.tipo === tipo && p.semana).forEach(p => {
      if (!porSemana[p.semana]) porSemana[p.semana] = { count: 0, totalMXN: 0, montoCashflow: 0, agingItems: [], cfItems: [] };
      porSemana[p.semana].montoCashflow += p.monto || 0;
      porSemana[p.semana].cfItems.push({ nombre: p.nombre, monto: p.monto || 0 });
    });
    const semanaRows = Object.entries(porSemana).sort((a, b) => semanaOrd(a[0]) - semanaOrd(b[0]));
    const totalAsignadoMXN = semanaRows.reduce((s, [, r]) => s + r.totalMXN, 0);
    const totalCashflowMXN = semanaRows.reduce((s, [, r]) => s + r.montoCashflow, 0);

    // Analiza por qué difieren Aging vs Cash Flow en una semana:
    // - soloCF: proveedores con monto guardado en Cash Flow que ya NO están en el Aging actual
    // - soloAging: proveedores en el Aging cuya asignación no tiene monto en Cash Flow
    // - desactualizados: están en ambos pero el monto guardado difiere del pendiente actual
    const analizarSemana = (r) => {
      const agingMap = new Map(r.agingItems.map(i => [i.nombre, i.monto]));
      const cfMap = new Map(r.cfItems.map(i => [i.nombre, i.monto]));
      const soloCF = r.cfItems.filter(i => !agingMap.has(i.nombre));
      const soloAging = r.agingItems.filter(i => !cfMap.has(i.nombre));
      const desactualizados = r.cfItems.filter(i =>
        agingMap.has(i.nombre) && Math.abs(agingMap.get(i.nombre) - i.monto) > 1);
      return {
        agingMap, cfMap, soloCF, soloAging, desactualizados,
        sumSoloCF: soloCF.reduce((s, i) => s + i.monto, 0),
        sumSoloAging: soloAging.reduce((s, i) => s + i.monto, 0),
      };
    };
    const fmtD = (mxn) => formatCurrency(fromMXN(mxn, displayCurrency), displayCurrency);
    const motivoDiferencia = (a) => {
      const partes = [];
      if (a.soloCF.length) partes.push(`${a.soloCF.length} del Cash Flow no está(n) en el Aging actual (${fmtD(a.sumSoloCF)})`);
      if (a.soloAging.length) partes.push(`${a.soloAging.length} del Aging sin monto en Cash Flow (${fmtD(a.sumSoloAging)})`);
      if (a.desactualizados.length) partes.push(`${a.desactualizados.length} con monto guardado desactualizado vs pendiente actual`);
      return partes.join(' · ');
    };
    const filtroActivo = semanaFiltro[tipo] || 'todas';
    const visibleRows = filtroActivo === 'todas' ? semanaRows : semanaRows.filter(([s]) => s === filtroActivo);
    const semanaDetalle = filtroActivo !== 'todas' ? porSemana[filtroActivo] : null;

    // Semanas proyectadas en uso (para el filtro de la tabla de detalle)
    const semanasAsignadas = [...new Set(Object.entries(proyecciones)
      .filter(([k, v]) => v && k.endsWith(`_${tipo}`))
      .map(([, v]) => v))].sort((a, b) => semanaOrd(a) - semanaOrd(b));

    // ── Proyectado vs Pagado (histórico de sincronizaciones) ──
    // pagado estimado = Σ diferencias archivadas al sincronizar (lo que dejó de estar pendiente);
    // pendiente actual = monto vigente en Cash Flow; proyectado original = pagado + pendiente
    const histPorSemana = {};
    historialSync.filter(h => h.tipo === tipo && h.semana).forEach(h => {
      if (!histPorSemana[h.semana]) histPorSemana[h.semana] = { pagado: 0, eventos: 0, ultimoSync: null };
      histPorSemana[h.semana].pagado += h.diferencia || 0;
      histPorSemana[h.semana].eventos += 1;
      if (!histPorSemana[h.semana].ultimoSync || h.sync_at > histPorSemana[h.semana].ultimoSync) {
        histPorSemana[h.semana].ultimoSync = h.sync_at;
      }
    });
    const histRows = Object.entries(histPorSemana)
      .map(([semana, h]) => {
        const pendienteActual = porSemana[semana]?.montoCashflow || 0;
        const proyectado = h.pagado + pendienteActual;
        return [semana, { ...h, pendienteActual, proyectado,
          avance: proyectado > 0 ? Math.min(100, Math.max(0, (h.pagado / proyectado) * 100)) : 0 }];
      })
      .sort((a, b) => semanaOrd(a[0]) - semanaOrd(b[0]));
    const histTotales = histRows.reduce((acc, [, h]) => ({
      pagado: acc.pagado + h.pagado,
      pendiente: acc.pendiente + h.pendienteActual,
      proyectado: acc.proyectado + h.proyectado,
    }), { pagado: 0, pendiente: 0, proyectado: 0 });

    return (
      <div className="space-y-6">
        {/* Summary Cards */}
        <div className="grid grid-cols-6 gap-4">
          {Object.entries(buckets).map(([key, bucket]) => (
            <Card key={key} className={`${bucket.totalMXN > 0 ? '' : 'opacity-50'}`}>
              <CardHeader className="pb-2">
                <CardTitle className="text-sm font-medium flex items-center gap-2">
                  <Clock size={14} />
                  {bucket.label}
                </CardTitle>
              </CardHeader>
              <CardContent>
                <div className={`text-lg font-bold ${bucket.totalMXN > 0 ? (key === 'vigente' ? 'text-green-600' : 'text-red-600') : 'text-gray-400'}`}>
                  {formatCurrency(fromMXN(bucket.totalMXN, displayCurrency), displayCurrency)}
                </div>
                <div className="text-xs text-gray-500">{bucket.numFacturas} factura(s)</div>
              </CardContent>
            </Card>
          ))}
        </div>

        {/* Totales por Semana Proyectada */}
        <Card data-testid={`semana-totals-${tipo}`}>
          <CardHeader className="pb-3">
            <div className="flex justify-between items-start gap-4">
              <div>
                <CardTitle className="text-base flex items-center gap-2">
                  <Calendar size={16} />
                  Totales por Semana Proyectada
                </CardTitle>
                <CardDescription>
                  {tipo === 'cxc' ? 'Cobros' : 'Pagos'} pendientes agrupados por la semana asignada en la columna
                  Proyección — verifica que los montos pasen correctamente al Cash Flow
                </CardDescription>
              </div>
              <div className="flex items-center gap-2">
                <Button
                  variant="outline"
                  size="sm"
                  className="h-8 gap-1 text-xs border-emerald-300 text-emerald-700 hover:bg-emerald-50"
                  onClick={() => handleSincronizarMontos(tipo)}
                  disabled={syncingProy}
                  data-testid={`sync-montos-${tipo}`}
                >
                  <RefreshCw size={12} className={syncingProy ? 'animate-spin' : ''} />
                  {syncingProy ? 'Sincronizando...' : 'Sincronizar con Aging'}
                </Button>
                <label className="text-xs font-medium text-gray-600 whitespace-nowrap">Semana</label>
                <Select
                  value={filtroActivo}
                  onValueChange={(v) => setSemanaFiltro(prev => ({ ...prev, [tipo]: v }))}
                >
                  <SelectTrigger className="h-8 w-[160px] text-sm" data-testid={`semana-filtro-${tipo}`}>
                    <SelectValue placeholder="Todas" />
                  </SelectTrigger>
                  <SelectContent>
                    <SelectItem value="todas">Todas</SelectItem>
                    {semanaRows.map(([semana]) => (
                      <SelectItem key={semana} value={semana}>
                        {semana}{semanaInfo.get(semana)?.dateLabel ? ` · ${semanaInfo.get(semana).dateLabel}` : ''}
                      </SelectItem>
                    ))}
                  </SelectContent>
                </Select>
              </div>
            </div>
          </CardHeader>
          <CardContent>
            {semanaRows.length === 0 && sinAsignar.count === 0 ? (
              <div className="text-sm text-gray-500 py-4 text-center">
                No hay facturas pendientes
              </div>
            ) : semanaRows.length === 0 ? (
              <div className="text-sm text-gray-500 py-4 text-center">
                Ninguna factura tiene semana asignada. Usa la columna "Proyección" de la tabla de detalle para asignar semanas.
              </div>
            ) : (
              <Table>
                <TableHeader>
                  <TableRow className="bg-gray-50">
                    <TableHead>Semana</TableHead>
                    <TableHead>Inicio</TableHead>
                    <TableHead className="text-center">Facturas</TableHead>
                    <TableHead className="text-right">Total Pendiente (Aging)</TableHead>
                    <TableHead className="text-right bg-blue-50">Monto en Cash Flow</TableHead>
                    <TableHead className="text-right">Diferencia</TableHead>
                  </TableRow>
                </TableHeader>
                <TableBody>
                  {visibleRows.map(([semana, r]) => {
                    const diff = r.totalMXN - r.montoCashflow;
                    const cuadra = Math.abs(diff) <= 1;
                    const analisis = cuadra ? null : analizarSemana(r);
                    const motivo = analisis ? motivoDiferencia(analisis) : '';
                    return (
                      <TableRow key={semana} data-testid={`semana-total-${tipo}-${semana}`}>
                        <TableCell>
                          <span className="text-xs px-2 py-1 rounded bg-blue-100 text-blue-800 font-semibold">{semana}</span>
                        </TableCell>
                        <TableCell className="text-xs text-gray-500">
                          {semanaInfo.get(semana)?.dateLabel || '—'}
                        </TableCell>
                        <TableCell className="text-center text-sm">{r.count}</TableCell>
                        <TableCell className="text-right font-mono text-sm">
                          {formatCurrency(fromMXN(r.totalMXN, displayCurrency), displayCurrency)}
                        </TableCell>
                        <TableCell className="text-right font-mono text-sm bg-blue-50">
                          {formatCurrency(fromMXN(r.montoCashflow, displayCurrency), displayCurrency)}
                        </TableCell>
                        <TableCell
                          className={`text-right text-xs ${cuadra ? 'text-green-600 font-mono' : 'text-red-600'}`}
                          title={motivo}
                        >
                          {cuadra ? '✓' : (
                            <div className="space-y-0.5">
                              <div className="font-mono font-semibold">
                                {formatCurrency(fromMXN(diff, displayCurrency), displayCurrency)}
                              </div>
                              <div className="text-[10px] leading-tight text-gray-500 max-w-[220px] ml-auto">
                                {motivo || 'montos iguales por proveedor pero con redondeo distinto'}
                              </div>
                            </div>
                          )}
                        </TableCell>
                      </TableRow>
                    );
                  })}
                  {filtroActivo === 'todas' && sinAsignar.count > 0 && (
                    <TableRow className="bg-amber-50" data-testid={`semana-total-${tipo}-sin-asignar`}>
                      <TableCell colSpan={2}>
                        <span className="text-xs text-amber-700 font-medium flex items-center gap-1">
                          <AlertTriangle size={12} />
                          Sin asignar
                        </span>
                      </TableCell>
                      <TableCell className="text-center text-sm text-amber-700">{sinAsignar.count}</TableCell>
                      <TableCell className="text-right font-mono text-sm text-amber-700">
                        {formatCurrency(fromMXN(sinAsignar.totalMXN, displayCurrency), displayCurrency)}
                      </TableCell>
                      <TableCell className="text-right font-mono text-sm bg-blue-50 text-gray-400">—</TableCell>
                      <TableCell />
                    </TableRow>
                  )}
                  {filtroActivo === 'todas' && (
                    <TableRow className="bg-gray-100 font-semibold border-t-2">
                      <TableCell colSpan={2}>Total asignado</TableCell>
                      <TableCell className="text-center text-sm">
                        {semanaRows.reduce((s, [, r]) => s + r.count, 0)}
                      </TableCell>
                      <TableCell className="text-right font-mono text-sm">
                        {formatCurrency(fromMXN(totalAsignadoMXN, displayCurrency), displayCurrency)}
                      </TableCell>
                      <TableCell className="text-right font-mono text-sm bg-blue-50">
                        {formatCurrency(fromMXN(totalCashflowMXN, displayCurrency), displayCurrency)}
                      </TableCell>
                      <TableCell className={`text-right font-mono text-xs ${Math.abs(totalAsignadoMXN - totalCashflowMXN) <= 1 ? 'text-green-600' : 'text-red-600 font-semibold'}`}>
                        {Math.abs(totalAsignadoMXN - totalCashflowMXN) <= 1
                          ? '✓'
                          : formatCurrency(fromMXN(totalAsignadoMXN - totalCashflowMXN, displayCurrency), displayCurrency)}
                      </TableCell>
                    </TableRow>
                  )}
                </TableBody>
              </Table>
            )}

            {/* Detalle de la semana filtrada: qué facturas componen cada lado */}
            {semanaDetalle && (() => {
              const a = analizarSemana(semanaDetalle);
              return (
                <div className="mt-4 grid grid-cols-2 gap-4" data-testid={`semana-detalle-${tipo}`}>
                  {/* Lado Aging */}
                  <div className="border rounded-sm p-3">
                    <h4 className="text-xs font-semibold text-gray-700 mb-2">
                      En Aging — {filtroActivo} ({semanaDetalle.agingItems.length} factura(s) · {fmtD(semanaDetalle.totalMXN)})
                    </h4>
                    <div className="max-h-64 overflow-y-auto space-y-1">
                      {semanaDetalle.agingItems.length === 0 ? (
                        <div className="text-xs text-gray-400 py-2">Ninguna factura del Aging actual está asignada a esta semana</div>
                      ) : semanaDetalle.agingItems.map((item, i) => (
                        <div key={i} className="flex justify-between items-center text-xs py-1 border-b border-gray-100">
                          <span className="truncate max-w-[60%]" title={item.nombre}>{item.nombre}</span>
                          <span className="flex items-center gap-2">
                            <span className="font-mono">{fmtD(item.monto)}</span>
                            {!a.cfMap.has(item.nombre) && (
                              <span className="text-[10px] px-1.5 py-0.5 rounded bg-red-100 text-red-700">sin monto en Cash Flow</span>
                            )}
                          </span>
                        </div>
                      ))}
                    </div>
                  </div>
                  {/* Lado Cash Flow */}
                  <div className="border rounded-sm p-3 bg-blue-50/30">
                    <h4 className="text-xs font-semibold text-gray-700 mb-2">
                      En Cash Flow — {filtroActivo} ({semanaDetalle.cfItems.length} registro(s) · {fmtD(semanaDetalle.montoCashflow)})
                    </h4>
                    <div className="max-h-64 overflow-y-auto space-y-1">
                      {semanaDetalle.cfItems.length === 0 ? (
                        <div className="text-xs text-gray-400 py-2">Ningún monto guardado en Cash Flow para esta semana</div>
                      ) : semanaDetalle.cfItems.map((item, i) => {
                        const enAging = a.agingMap.has(item.nombre);
                        const pendienteActual = a.agingMap.get(item.nombre);
                        const desactualizado = enAging && Math.abs(pendienteActual - item.monto) > 1;
                        return (
                          <div key={i} className="flex justify-between items-center text-xs py-1 border-b border-gray-100">
                            <span className="truncate max-w-[50%]" title={item.nombre}>{item.nombre}</span>
                            <span className="flex items-center gap-2">
                              <span className="font-mono">{fmtD(item.monto)}</span>
                              {!enAging && (
                                <span className="text-[10px] px-1.5 py-0.5 rounded bg-red-100 text-red-700">no está en Aging actual</span>
                              )}
                              {desactualizado && (
                                <span className="text-[10px] px-1.5 py-0.5 rounded bg-amber-100 text-amber-700" title={`Pendiente actual en Aging: ${fmtD(pendienteActual)}`}>
                                  Aging: {fmtD(pendienteActual)}
                                </span>
                              )}
                            </span>
                          </div>
                        );
                      })}
                    </div>
                  </div>
                </div>
              );
            })()}
          </CardContent>
        </Card>

        {/* Proyectado vs Pagado por Semana (histórico de sincronizaciones) */}
        {histRows.length > 0 && (
          <Card data-testid={`proyectado-vs-pagado-${tipo}`}>
            <CardHeader className="pb-3">
              <CardTitle className="text-base flex items-center gap-2">
                <FileText size={16} />
                Proyectado vs Pagado por Semana
              </CardTitle>
              <CardDescription>
                Diferencias registradas al sincronizar con el Aging: lo proyectado originalmente vs lo que
                dejó de estar pendiente ({tipo === 'cxc' ? 'cobrado' : 'pagado'} estimado)
              </CardDescription>
            </CardHeader>
            <CardContent>
              <Table>
                <TableHeader>
                  <TableRow className="bg-gray-50">
                    <TableHead>Semana</TableHead>
                    <TableHead>Inicio</TableHead>
                    <TableHead className="text-right">Proyectado Original</TableHead>
                    <TableHead className="text-right bg-emerald-50">{tipo === 'cxc' ? 'Cobrado' : 'Pagado'} (estimado)</TableHead>
                    <TableHead className="text-right">Pendiente Actual</TableHead>
                    <TableHead className="text-right">Avance</TableHead>
                  </TableRow>
                </TableHeader>
                <TableBody>
                  {histRows.map(([semana, h]) => (
                    <TableRow key={semana} data-testid={`proy-vs-pagado-${tipo}-${semana}`}>
                      <TableCell>
                        <span className="text-xs px-2 py-1 rounded bg-blue-100 text-blue-800 font-semibold">{semana}</span>
                      </TableCell>
                      <TableCell className="text-xs text-gray-500">
                        {semanaInfo.get(semana)?.dateLabel || '—'}
                      </TableCell>
                      <TableCell className="text-right font-mono text-sm">{fmtD(h.proyectado)}</TableCell>
                      <TableCell className={`text-right font-mono text-sm bg-emerald-50 ${h.pagado > 0 ? 'text-emerald-700' : 'text-gray-400'}`}>
                        {fmtD(h.pagado)}
                      </TableCell>
                      <TableCell className="text-right font-mono text-sm">{fmtD(h.pendienteActual)}</TableCell>
                      <TableCell className="text-right">
                        <div className="flex items-center justify-end gap-2">
                          <div className="w-16 h-1.5 bg-gray-200 rounded-full overflow-hidden">
                            <div
                              className={`h-full rounded-full ${h.avance >= 100 ? 'bg-emerald-500' : 'bg-blue-500'}`}
                              style={{ width: `${h.avance}%` }}
                            />
                          </div>
                          <span className="font-mono text-xs text-gray-600 w-10 text-right">{h.avance.toFixed(0)}%</span>
                        </div>
                      </TableCell>
                    </TableRow>
                  ))}
                  <TableRow className="bg-gray-100 font-semibold border-t-2">
                    <TableCell colSpan={2}>Total</TableCell>
                    <TableCell className="text-right font-mono text-sm">{fmtD(histTotales.proyectado)}</TableCell>
                    <TableCell className="text-right font-mono text-sm bg-emerald-50 text-emerald-700">{fmtD(histTotales.pagado)}</TableCell>
                    <TableCell className="text-right font-mono text-sm">{fmtD(histTotales.pendiente)}</TableCell>
                    <TableCell className="text-right font-mono text-xs text-gray-600">
                      {histTotales.proyectado > 0 ? `${Math.min(100, Math.max(0, (histTotales.pagado / histTotales.proyectado) * 100)).toFixed(0)}%` : '—'}
                    </TableCell>
                  </TableRow>
                </TableBody>
              </Table>
            </CardContent>
          </Card>
        )}

        {/* Filters Section */}
        <Card className="border-blue-200 bg-blue-50/50">
          <CardHeader className="pb-3">
            <div className="flex justify-between items-center">
              <CardTitle className="text-sm font-medium flex items-center gap-2 text-blue-800">
                <Filter size={16} />
                Filtros
              </CardTitle>
              {isFiltered && (
                <Button 
                  variant="ghost" 
                  size="sm" 
                  className="text-blue-600 hover:text-blue-800 h-7 px-2 gap-1"
                  onClick={() => resetFilters(tipo)}
                  data-testid={`clear-filters-${tipo}`}
                >
                  <X size={14} />
                  Limpiar filtros
                </Button>
              )}
            </div>
          </CardHeader>
          <CardContent>
            <div className="grid grid-cols-6 gap-4">
              {/* Search by Cliente/Proveedor */}
              <div className="space-y-1">
                <label className="text-xs font-medium text-gray-600">
                  {tipo === 'cxc' ? 'Cliente' : 'Proveedor'}
                </label>
                <div className="relative">
                  <Search size={14} className="absolute left-2 top-1/2 transform -translate-y-1/2 text-gray-400" />
                  <Input
                    placeholder={`Buscar ${tipo === 'cxc' ? 'cliente' : 'proveedor'}...`}
                    value={tipo === 'cxc' ? filters.cliente : filters.proveedor}
                    onChange={(e) => {
                      if (tipo === 'cxc') {
                        setCxcFilters(prev => ({ ...prev, cliente: e.target.value }));
                      } else {
                        setCxpFilters(prev => ({ ...prev, proveedor: e.target.value }));
                      }
                    }}
                    className="pl-8 h-9 text-sm"
                    data-testid={`filter-${tipo}-name`}
                  />
                </div>
              </div>

              {/* Filter by Moneda */}
              <div className="space-y-1">
                <label className="text-xs font-medium text-gray-600">Moneda</label>
                <Select
                  value={filters.moneda}
                  onValueChange={(value) => {
                    if (tipo === 'cxc') {
                      setCxcFilters(prev => ({ ...prev, moneda: value }));
                    } else {
                      setCxpFilters(prev => ({ ...prev, moneda: value }));
                    }
                  }}
                >
                  <SelectTrigger className="h-9 text-sm" data-testid={`filter-${tipo}-currency`}>
                    <SelectValue placeholder="Todas" />
                  </SelectTrigger>
                  <SelectContent>
                    <SelectItem value="todas">Todas</SelectItem>
                    {currencies.map(currency => (
                      <SelectItem key={currency} value={currency}>{currency}</SelectItem>
                    ))}
                  </SelectContent>
                </Select>
              </div>

              {/* Filter by Antigüedad */}
              <div className="space-y-1">
                <label className="text-xs font-medium text-gray-600">Antigüedad</label>
                <Select
                  value={filters.antiguedad}
                  onValueChange={(value) => {
                    if (tipo === 'cxc') {
                      setCxcFilters(prev => ({ ...prev, antiguedad: value }));
                    } else {
                      setCxpFilters(prev => ({ ...prev, antiguedad: value }));
                    }
                  }}
                >
                  <SelectTrigger className="h-9 text-sm" data-testid={`filter-${tipo}-aging`}>
                    <SelectValue placeholder="Todas" />
                  </SelectTrigger>
                  <SelectContent>
                    {agingOptions.map(option => (
                      <SelectItem key={option.value} value={option.value}>{option.label}</SelectItem>
                    ))}
                  </SelectContent>
                </Select>
              </div>

              {/* Filter by Semana Proyectada */}
              <div className="space-y-1">
                <label className="text-xs font-medium text-gray-600">Semana Proyectada</label>
                <Select
                  value={filters.semanaProyectada || 'todas'}
                  onValueChange={(value) => {
                    if (tipo === 'cxc') {
                      setCxcFilters(prev => ({ ...prev, semanaProyectada: value }));
                    } else {
                      setCxpFilters(prev => ({ ...prev, semanaProyectada: value }));
                    }
                  }}
                >
                  <SelectTrigger className="h-9 text-sm" data-testid={`filter-${tipo}-semana`}>
                    <SelectValue placeholder="Todas" />
                  </SelectTrigger>
                  <SelectContent>
                    <SelectItem value="todas">Todas</SelectItem>
                    <SelectItem value="sin-asignar">— Sin asignar</SelectItem>
                    {semanasAsignadas.map(semana => (
                      <SelectItem key={semana} value={semana}>
                        {semana}{semanaInfo.get(semana)?.dateLabel ? ` · ${semanaInfo.get(semana).dateLabel}` : ''}
                      </SelectItem>
                    ))}
                  </SelectContent>
                </Select>
              </div>

              {/* Filter by Fecha Desde */}
              <div className="space-y-1">
                <label className="text-xs font-medium text-gray-600">Desde</label>
                <Input
                  type="date"
                  value={filters.fechaDesde}
                  onChange={(e) => {
                    if (tipo === 'cxc') {
                      setCxcFilters(prev => ({ ...prev, fechaDesde: e.target.value }));
                    } else {
                      setCxpFilters(prev => ({ ...prev, fechaDesde: e.target.value }));
                    }
                  }}
                  className="h-9 text-sm"
                  data-testid={`filter-${tipo}-date-from`}
                />
              </div>

              {/* Filter by Fecha Hasta */}
              <div className="space-y-1">
                <label className="text-xs font-medium text-gray-600">Hasta</label>
                <Input
                  type="date"
                  value={filters.fechaHasta}
                  onChange={(e) => {
                    if (tipo === 'cxc') {
                      setCxcFilters(prev => ({ ...prev, fechaHasta: e.target.value }));
                    } else {
                      setCxpFilters(prev => ({ ...prev, fechaHasta: e.target.value }));
                    }
                  }}
                  className="h-9 text-sm"
                  data-testid={`filter-${tipo}-date-to`}
                />
              </div>
            </div>
          </CardContent>
        </Card>

        {/* Detail Table */}
        <Card>
          <CardHeader>
            <div className="flex justify-between items-center">
              <div>
                <CardTitle>Detalle de {tipo === 'cxc' ? 'Cuentas por Cobrar' : 'Cuentas por Pagar'}</CardTitle>
                <CardDescription>
                  {isFiltered ? (
                    <span className="text-blue-600">
                      Mostrando {filteredCfdis.length} de {allCfdis.length} facturas 
                      <span className="font-semibold ml-2">(Total filtrado: {formatCurrency(filteredTotalMXN, 'MXN')})</span>
                    </span>
                  ) : (
                    `${allCfdis.length} facturas pendientes`
                  )}
                </CardDescription>
              </div>
              <Button 
                variant="outline" 
                className="gap-2"
                onClick={() => handleExportFiltered(filteredCfdis, tipo, isFiltered)}
                data-testid={`export-${tipo}-btn`}
              >
                <Download size={14} />
                {isFiltered ? 'Exportar Filtrado' : 'Exportar'}
              </Button>
              <Button
                variant="outline"
                className="gap-2 border-purple-300 text-purple-700 hover:bg-purple-50"
                onClick={handleAutoCategorize}
                disabled={autoCategorizing}
                data-testid={`categorize-${tipo}-btn`}
              >
                <Tag size={14} />
                {autoCategorizing ? 'Categorizando...' : 'Categorizar con IA'}
              </Button>
            </div>
          </CardHeader>
          <CardContent>
            <Table>
              <TableHeader>
                <TableRow className="bg-gray-50">
                  <TableHead>Antigüedad</TableHead>
                  <TableHead>{tipo === 'cxc' ? 'Cliente' : 'Proveedor'}</TableHead>
                  <TableHead className="bg-purple-50">Categoría</TableHead>
                  <TableHead>UUID</TableHead>
                  <TableHead>Fecha Emisión</TableHead>
                  <TableHead>Plazo</TableHead>
                  <TableHead>Vencimiento</TableHead>
                  <TableHead>Días Venc.</TableHead>
                  <TableHead className="bg-blue-50">Proyección</TableHead>
                  <TableHead>Moneda</TableHead>
                  <TableHead className="text-right">Total (orig.)</TableHead>
                  <TableHead className="text-right bg-green-50">Total MXN</TableHead>
                  <TableHead className="text-right">Pendiente (orig.)</TableHead>
                  <TableHead className="text-right bg-amber-50">Ret. SAT</TableHead>
                  <TableHead className="text-right bg-blue-50">Pend. MXN</TableHead>
                </TableRow>
              </TableHeader>
              <TableBody>
                {filteredCfdis.length === 0 ? (
                  <TableRow>
                    <TableCell colSpan={14} className="text-center py-8 text-gray-500">
                      {isFiltered 
                        ? 'No hay facturas que coincidan con los filtros seleccionados'
                        : `No hay facturas pendientes de ${tipo === 'cxc' ? 'cobro' : 'pago'}`
                      }
                    </TableCell>
                  </TableRow>
                ) : (
                  pagedCfdis.map(cfdi => {
                    const bucket = getAgingBucket(cfdi, tipo);
                    const bucketInfo = buckets[bucket];
                    const pagado = tipo === 'cxc' ? (cfdi.monto_cobrado || 0) : (cfdi.monto_pagado || 0);
                    
                    return (
                      <TableRow key={cfdi.id} className={`hover:bg-gray-50 ${cfdi.diasVencido > 90 ? 'bg-red-50' : ''}`}>
                        <TableCell>
                          <span className={`text-xs px-2 py-1 rounded ${bucketInfo.color}`}>
                            {bucketInfo.label}
                          </span>
                        </TableCell>
                        <TableCell className="font-medium max-w-[150px]">
                          <div
                            className="flex items-center gap-2"
                            title={getPartyName(cfdi, tipo)}
                          >
                            {tipo === 'cxc' ? <User size={14} className="text-blue-500 shrink-0" /> : <Building2 size={14} className="text-orange-500 shrink-0" />}
                            <span className="truncate text-xs font-semibold">{getPartyName(cfdi, tipo)}</span>
                          </div>
                        </TableCell>
                        <TableCell className="bg-purple-50 min-w-[160px]">
                          {(() => {
                            const key = `${getPartyName(cfdi, tipo)}_${tipo}`;
                            const catActual = categorias[key];
                            const catalogo = getERPEndpoints().usaAlegra
                              ? catalogoCategorias
                                  .filter(c => tipo === 'cxc' ? c.tipo === 'ingreso' : c.tipo === 'egreso')
                                  .map(c => `${c.code}:${c.nombre}`)
                              : tipo === 'cxc'
                                ? ['ING-001:Ventas de productos','ING-002:Prestación de servicios','ING-003:Honorarios profesionales','ING-004:Arrendamiento cobrado','ING-005:Cobro de anticipos','ING-007:Intereses cobrados','ING-099:Otros ingresos']
                                : ['EGR-001:Nómina y salarios','EGR-002:IMSS / INFONAVIT','EGR-003:ISR','EGR-004:IVA','EGR-005:Renta','EGR-006:Proveedores materia prima','EGR-007:Servicios','EGR-008:Telefonía e internet','EGR-009:Publicidad','EGR-010:Honorarios externos','EGR-011:Viáticos','EGR-012:Seguros','EGR-013:Mantenimiento','EGR-015:Software','EGR-016:Crédito bancario','EGR-017:Intereses pagados','EGR-018:Comisiones bancarias','EGR-020:Activo fijo','EGR-099:Otros egresos'];
                            return (
                              <select
                                value={catActual?.code || ''}
                                onChange={e => {
                                  const entry = catalogo.find(c => c.startsWith(e.target.value + ':'));
                                  const name = entry ? entry.split(':')[1] : '';
                                  handleCategoriaManual(getPartyName(cfdi, tipo), tipo, e.target.value, name);
                                }}
                                className={`text-xs px-2 py-1 rounded border cursor-pointer w-full ${
                                  catActual
                                    ? 'bg-purple-100 text-purple-800 border-purple-300 font-semibold'
                                    : 'bg-gray-50 text-gray-400 border-gray-200'
                                }`}
                              >
                                <option value="">— Sin categoría</option>
                                {catalogo.map(c => {
                                  const [code, name] = c.split(':');
                                  return <option key={code} value={code}>{name}</option>;
                                })}
                              </select>
                            );
                          })()}
                        </TableCell>
                        <TableCell>
                          {cfdi.uuid ? (
                            <button
                              title={`UUID completo:\n${cfdi.uuid}\n\nClic para copiar`}
                              onClick={() => {
                                navigator.clipboard.writeText(cfdi.uuid);
                                toast.success('UUID copiado');
                              }}
                              className="font-mono text-xs text-blue-600 hover:text-blue-800 hover:underline cursor-pointer bg-blue-50 hover:bg-blue-100 px-2 py-0.5 rounded transition-colors"
                            >
                              {cfdi.uuid.substring(0, 8)}…
                            </button>
                          ) : (
                            <span className="text-xs text-gray-400">—</span>
                          )}
                        </TableCell>
                        <TableCell className="text-xs">{(cfdi.fecha_emision ? format(new Date(cfdi.fecha_emision), 'dd/MM/yy') : 'N/A')}</TableCell>
                        <TableCell className="text-center">
                          <span className={`text-xs px-1.5 py-0.5 rounded ${cfdi.plazo === 0 ? 'bg-green-100 text-green-800' : 'bg-gray-100 text-gray-700'}`}>
                            {cfdi.plazo === 0 ? 'Contado' : `${cfdi.plazo}d`}
                          </span>
                        </TableCell>
                        <TableCell className="text-xs">{format(cfdi.fechaVencimiento, 'dd/MM/yy')}</TableCell>
                        <TableCell className="text-center">
                          <span className={`font-mono text-xs font-semibold px-1.5 py-0.5 rounded ${
                            cfdi.diasVencido <= 0 ? 'bg-green-100 text-green-800' :
                            cfdi.diasVencido > 90 ? 'bg-red-200 text-red-800' : 
                            cfdi.diasVencido > 30 ? 'bg-orange-100 text-orange-700' : 
                            'bg-yellow-100 text-yellow-800'
                          }`}>
                            {cfdi.diasVencido <= 0 ? `${Math.abs(cfdi.diasVencido)}d` : `+${cfdi.diasVencido}d`}
                          </span>
                        </TableCell>
                        <TableCell className="text-center bg-blue-50">
                          {(() => {
                            const nombre = getPartyName(cfdi, tipo);
                            const key = `${nombre}_${tipo}`;
                            const semanaActual = proyecciones[key] || '';
                            const proyDoc = proyDocs.find(p => p.nombre === nombre && p.tipo === tipo);
                            const isCapped = (proyDoc?.rolled_count || 0) >= 8;
                            const isRolled = proyDoc?.auto_rolled === true && !isCapped;
                            return (
                              <div className="flex flex-col items-center gap-1">
                                <select
                                  value={semanaActual}
                                  onChange={e => handleAsignarSemana(
                                    nombre, tipo,
                                    e.target.value || null,
                                    cfdi.pendiente || cfdi.total || 0
                                  )}
                                  className={`text-xs px-2 py-1 rounded border cursor-pointer ${
                                    semanaActual
                                      ? 'bg-blue-100 text-blue-800 border-blue-300 font-semibold'
                                      : 'bg-gray-50 text-gray-400 border-gray-200'
                                  }`}
                                >
                                  <option value="">— Sin asignar</option>
                                  {semanasModelo.map(s => (
                                    <option key={s.label} value={s.label}>
                                      {s.label} · {s.dateLabel}
                                    </option>
                                  ))}
                                </select>
                                {isCapped && (
                                  <span
                                    title={`Sin cobrarse ${proyDoc.rolled_count} semanas desde ${proyDoc.rolled_from}`}
                                    className="text-[10px] px-1.5 py-0.5 rounded bg-red-100 text-red-700 font-semibold cursor-help"
                                  >
                                    ⚠ Vencida +8 sem
                                  </span>
                                )}
                                {isRolled && (
                                  <span
                                    title={`Movido automáticamente de ${proyDoc.rolled_from}`}
                                    className="text-[10px] px-1.5 py-0.5 rounded bg-orange-100 text-orange-700 font-semibold cursor-help"
                                  >
                                    ⟳ Rolado
                                  </span>
                                )}
                              </div>
                            );
                          })()}
                        </TableCell>
                        <TableCell>
                          <span className={`text-xs px-2 py-1 rounded ${cfdi.moneda === 'USD' ? 'bg-green-100 text-green-800' : cfdi.moneda === 'EUR' ? 'bg-purple-100 text-purple-800' : 'bg-gray-100 text-gray-800'}`}>
                            {cfdi.moneda || 'MXN'}
                          </span>
                        </TableCell>
                        <TableCell className="text-right font-mono text-xs">
                          {formatCurrency(cfdi.total, cfdi.moneda)}
                        </TableCell>
                        <TableCell className="text-right font-mono text-xs bg-green-50 text-green-800">
                          {cfdi.moneda !== 'MXN'
                            ? formatCurrency(cfdi.totalMXN || cfdi.pendienteMXN, 'MXN')
                            : '—'}
                        </TableCell>
                        <TableCell className="text-right font-mono text-xs font-bold text-orange-600">
                          {formatCurrency(cfdi.pendiente, cfdi.moneda)}
                        </TableCell>
                        <TableCell className="text-right font-mono text-xs bg-amber-50">
                          {cfdi.esRetencion ? (
                            <span className="text-amber-700 font-bold" title="Retención para entero al SAT">
                              {formatCurrency(fromMXN(convertToMXN(cfdi.retencionSAT, cfdi.moneda), displayCurrency), displayCurrency)}
                            </span>
                          ) : (
                            <span className="text-gray-300">—</span>
                          )}
                        </TableCell>
                        <TableCell className="text-right font-mono text-xs font-bold bg-blue-50 text-blue-700">
                          {cfdi.esRetencion ? (
                            <span className="text-gray-400 line-through text-xs">{formatCurrency(fromMXN(cfdi.pendienteMXN, displayCurrency), displayCurrency)}</span>
                          ) : (
                            formatCurrency(fromMXN(cfdi.pendienteMXN, displayCurrency), displayCurrency)
                          )}
                        </TableCell>
                      </TableRow>
                    );
                  })
                )}
              </TableBody>
            </Table>
          </CardContent>
          {totalPages > 1 && (
            <div className="flex items-center justify-between px-4 py-3 border-t text-xs text-gray-600">
              <span>
                Página {page} de {totalPages} · {filteredCfdis.length} registros
              </span>
              <div className="flex gap-2">
                <button
                  onClick={() => setCurrentPage(prev => ({ ...prev, [tipo]: Math.max(1, prev[tipo] - 1) }))}
                  disabled={page === 1}
                  className="px-3 py-1 rounded border border-gray-300 hover:bg-gray-100 disabled:opacity-40 disabled:cursor-not-allowed"
                >
                  Anterior
                </button>
                <button
                  onClick={() => setCurrentPage(prev => ({ ...prev, [tipo]: Math.min(totalPages, prev[tipo] + 1) }))}
                  disabled={page === totalPages}
                  className="px-3 py-1 rounded border border-gray-300 hover:bg-gray-100 disabled:opacity-40 disabled:cursor-not-allowed"
                >
                  Siguiente
                </button>
              </div>
            </div>
          )}
        </Card>
      </div>
    );
  };

  // Export Aging to Excel
  const handleExportAging = () => {
    const cxcBucketsData = processAging('cxc');
    const cxpBucketsData = processAging('cxp');
    
    const cxcData = Object.values(cxcBucketsData).flatMap(bucket => 
      bucket.cfdis.map(cfdi => ({
        bucket: bucket.label,
        cliente: getPartyName(cfdi, 'cxc'),
        uuid: cfdi.uuid?.substring(0, 8),
        fechaEmision: cfdi.fecha_emision,
        plazo: cfdi.plazo,
        fechaVencimiento: format(cfdi.fechaVencimiento, 'yyyy-MM-dd'),
        diasVencido: cfdi.diasVencido,
        moneda: cfdi.moneda || 'MXN',
        total: cfdi.total,
        pagado: cfdi.monto_cobrado || 0,
        pendiente: cfdi.pendiente,
        pendienteMXN: cfdi.pendienteMXN
      }))
    );
    
    const cxpData = Object.values(cxpBucketsData).flatMap(bucket => 
      bucket.cfdis.map(cfdi => ({
        bucket: bucket.label,
        proveedor: getPartyName(cfdi, 'cxp'),
        uuid: cfdi.uuid?.substring(0, 8),
        fechaEmision: cfdi.fecha_emision,
        plazo: cfdi.plazo,
        fechaVencimiento: format(cfdi.fechaVencimiento, 'yyyy-MM-dd'),
        diasVencido: cfdi.diasVencido,
        moneda: cfdi.moneda || 'MXN',
        total: cfdi.total,
        pagado: cfdi.monto_pagado || 0,
        pendiente: cfdi.pendiente,
        pendienteMXN: cfdi.pendienteMXN
      }))
    );
    
    const success = exportAging(cxcData, cxpData);
    if (success) {
      toast.success('Aging exportado a Excel');
    } else {
      toast.error('Error al exportar');
    }
  };

  return (
    <div className="p-6 space-y-6 bg-[#F8FAFC] min-h-screen" data-testid="aging-page">
      {/* Header */}
      <div className="flex justify-between items-center">
        <div>
          <PageHeader title="Aging de Cartera" subtitle="Análisis de antigüedad de Cuentas por Cobrar y por Pagar" />
        </div>
        <div className="flex items-center gap-4">
          <div className="text-sm text-gray-500 bg-white border rounded px-3 py-1.5">
            TC: USD ${fxRates.USD?.toFixed(2) || '—'} | EUR ${fxRates.EUR?.toFixed(2) || '—'}
          </div>
          <Select value={displayCurrency} onValueChange={setDisplayCurrency}>
            <SelectTrigger className="w-28 h-9 text-sm">
              <SelectValue />
            </SelectTrigger>
            <SelectContent>
              <SelectItem value="MXN">MXN</SelectItem>
              <SelectItem value="USD">USD</SelectItem>
              <SelectItem value="EUR">EUR</SelectItem>
            </SelectContent>
          </Select>
          <Button 
            variant="outline" 
            className="gap-2"
            onClick={handleExportAging}
            data-testid="export-aging-btn"
          >
            <Download size={14} />
            Exportar Excel
          </Button>
          {!getERPEndpoints().usaAlegra && (
            <>
              <label className="cursor-pointer inline-flex items-center gap-2 px-3 py-2 text-sm border border-green-300 rounded-md hover:bg-green-50 text-green-700">
                <input type="file" accept=".xls,.xlsx" className="hidden" onChange={e => handleUploadExcel(e, 'cxc')} />
                {uploadingCxC ? <RefreshCw size={14} className="animate-spin" /> : <FileText size={14} />}
                {uploadingCxC ? 'Subiendo...' : 'Excel CxC'}
              </label>
              <label className="cursor-pointer inline-flex items-center gap-2 px-3 py-2 text-sm border border-red-300 rounded-md hover:bg-red-50 text-red-700">
                <input type="file" accept=".xls,.xlsx" className="hidden" onChange={e => handleUploadExcel(e, 'cxp')} />
                {uploadingCxP ? <RefreshCw size={14} className="animate-spin" /> : <FileText size={14} />}
                {uploadingCxP ? 'Subiendo...' : 'Excel CxP'}
              </label>
            </>
          )}
          <Button 
            variant="outline" 
            className="gap-2" 
            onClick={syncFxRates}
            disabled={syncingRates}
            data-testid="sync-fx-rates-btn"
          >
            <RefreshCw size={14} className={syncingRates ? 'animate-spin' : ''} />
            {syncingRates ? 'Actualizando...' : 'Actualizar T.C.'}
          </Button>
        </div>
      </div>

      {/* Summary */}
      <div className="grid grid-cols-2 gap-6">
        <Card className="border-green-200 bg-green-50">
          <CardHeader className="pb-2">
            <CardTitle className="text-lg flex items-center gap-2 text-green-800">
              <TrendingUp size={20} />
              Total Cuentas por Cobrar (CxC)
            </CardTitle>
          </CardHeader>
          <CardContent>
            <div className="text-3xl font-bold text-green-700">{formatCurrency(totalCxCDisplay, displayCurrency)}</div>
            <div className="text-sm text-green-600 mt-1">
              {Object.values(cxcBuckets).reduce((s, b) => s + b.cfdis.length, 0)} facturas pendientes de cobro
            </div>
          </CardContent>
        </Card>

        <Card className="border-red-200 bg-red-50">
          <CardHeader className="pb-2">
            <CardTitle className="text-lg flex items-center gap-2 text-red-800">
              <TrendingDown size={20} />
              Total Cuentas por Pagar (CxP)
            </CardTitle>
          </CardHeader>
          <CardContent>
            <div className="text-3xl font-bold text-red-700">{formatCurrency(totalCxPDisplay, displayCurrency)}</div>
            <div className="text-sm text-red-600 mt-1">
              {Object.values(cxpBuckets).reduce((s, b) => s + b.cfdis.length, 0)} facturas pendientes de pago
            </div>
          </CardContent>
        </Card>
      </div>

      {/* Tabs */}
      <Tabs value={activeTab} onValueChange={setActiveTab}>
        <TabsList className="grid w-full grid-cols-2 max-w-md">
          <TabsTrigger value="cxc" className="gap-2">
            <TrendingUp size={16} />
            Cuentas por Cobrar
          </TabsTrigger>
          <TabsTrigger value="cxp" className="gap-2">
            <TrendingDown size={16} />
            Cuentas por Pagar
          </TabsTrigger>
        </TabsList>

        <TabsContent value="cxc" className="mt-4">
          {renderAgingTable(cxcBuckets, 'cxc')}
        </TabsContent>

        <TabsContent value="cxp" className="mt-4">
          {renderAgingTable(cxpBuckets, 'cxp')}
        </TabsContent>
      </Tabs>
    </div>
  );
};

export default AgingModule;
