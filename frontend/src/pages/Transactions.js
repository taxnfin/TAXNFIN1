import { useState, useEffect } from 'react';
import api from '@/api/axios';
import { Card, CardContent, CardHeader, CardTitle, CardDescription } from '@/components/ui/card';
import { Tabs, TabsContent, TabsList, TabsTrigger } from '@/components/ui/tabs';
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from '@/components/ui/table';
import { Button } from '@/components/ui/button';
import { toast } from 'sonner';
import { TrendingUp, TrendingDown, Clock, AlertTriangle, Calendar, Download, FileText, Building2, User, RefreshCw } from 'lucide-react';
import { format, differenceInDays } from 'date-fns';
import { es } from 'date-fns/locale';

const AgingModule = () => {
  const [loading, setLoading] = useState(true);
  const [cfdis, setCfdis] = useState([]);
  const [customers, setCustomers] = useState([]);
  const [vendors, setVendors] = useState([]);
  const [fxRates, setFxRates] = useState({});
  const [syncingRates, setSyncingRates] = useState(false);
  const [activeTab, setActiveTab] = useState('cxc'); // cxc = Cuentas por Cobrar, cxp = Cuentas por Pagar

  useEffect(() => {
    loadData();
  }, []);

  const loadData = async () => {
    setLoading(true);
    try {
      const [cfdiRes, custRes, vendRes, fxRes] = await Promise.all([
        api.get('/cfdi?limit=500'),
        api.get('/customers'),
        api.get('/vendors'),
        api.get('/fx-rates/latest')
      ]);
      setCfdis(cfdiRes.data);
      setCustomers(custRes.data);
      setVendors(vendRes.data);
      setFxRates(fxRes.data || {});
    } catch (error) {
      toast.error('Error cargando datos');
    } finally {
      setLoading(false);
    }
  };

  const syncFxRates = async () => {
    setSyncingRates(true);
    try {
      const res = await api.post('/fx-rates/sync');
      if (res.data.rates) {
        setFxRates(res.data.rates);
        toast.success(`Tipos de cambio actualizados desde ${Object.keys(res.data.rates).join(', ')}`);
      }
    } catch (error) {
      toast.error('Error sincronizando tipos de cambio');
    } finally {
      setSyncingRates(false);
    }
  };

  const formatCurrency = (amount, moneda = 'MXN') => {
    const symbol = moneda === 'USD' ? 'US$' : moneda === 'EUR' ? '€' : '$';
    return `${symbol}${(amount || 0).toLocaleString('es-MX', { minimumFractionDigits: 2, maximumFractionDigits: 2 })}`;
  };

  // Convert to MXN using fx rates
  const convertToMXN = (amount, moneda) => {
    if (!moneda || moneda === 'MXN') return amount;
    const rate = fxRates[moneda] || 1;
    return amount * rate;
  };

  // Calculate aging bucket
  const getAgingBucket = (fechaEmision) => {
    const today = new Date();
    const emision = new Date(fechaEmision);
    const dias = differenceInDays(today, emision);
    
    if (dias <= 0) return 'vigente';
    if (dias <= 30) return '1-30';
    if (dias <= 60) return '31-60';
    if (dias <= 90) return '61-90';
    if (dias <= 120) return '91-120';
    return '120+';
  };

  // Process CFDIs for aging
  const processAging = (tipo) => {
    const isIngreso = tipo === 'cxc';
    const filtered = cfdis.filter(cfdi => {
      if (cfdi.tipo_cfdi !== (isIngreso ? 'ingreso' : 'egreso')) return false;
      if (cfdi.estado_cancelacion === 'cancelado') return false;
      
      // Check pending balance
      const amountField = isIngreso ? 'monto_cobrado' : 'monto_pagado';
      const pendiente = cfdi.total - (cfdi[amountField] || 0);
      return pendiente > 0.01;
    });

    // Group by aging bucket
    const buckets = {
      'vigente': { label: 'Vigente', cfdis: [], total: 0, totalMXN: 0, color: 'bg-green-100 text-green-800' },
      '1-30': { label: '1-30 días', cfdis: [], total: 0, totalMXN: 0, color: 'bg-yellow-100 text-yellow-800' },
      '31-60': { label: '31-60 días', cfdis: [], total: 0, totalMXN: 0, color: 'bg-orange-100 text-orange-800' },
      '61-90': { label: '61-90 días', cfdis: [], total: 0, totalMXN: 0, color: 'bg-red-100 text-red-800' },
      '91-120': { label: '91-120 días', cfdis: [], total: 0, totalMXN: 0, color: 'bg-red-200 text-red-900' },
      '120+': { label: '+120 días', cfdis: [], total: 0, totalMXN: 0, color: 'bg-red-300 text-red-900' }
    };

    filtered.forEach(cfdi => {
      const bucket = getAgingBucket(cfdi.fecha_emision);
      const amountField = isIngreso ? 'monto_cobrado' : 'monto_pagado';
      const pendiente = cfdi.total - (cfdi[amountField] || 0);
      const moneda = cfdi.moneda || 'MXN';
      const pendienteMXN = convertToMXN(pendiente, moneda);
      
      buckets[bucket].cfdis.push({
        ...cfdi,
        pendiente,
        pendienteMXN,
        moneda,
        diasVencido: differenceInDays(new Date(), new Date(cfdi.fecha_emision))
      });
      buckets[bucket].total += pendiente;
      buckets[bucket].totalMXN += pendienteMXN;
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

  if (loading) return <div className="p-8">Cargando...</div>;

  const cxcBuckets = processAging('cxc');
  const cxpBuckets = processAging('cxp');

  const totalCxC = Object.values(cxcBuckets).reduce((s, b) => s + b.total, 0);
  const totalCxP = Object.values(cxpBuckets).reduce((s, b) => s + b.total, 0);
  const totalCxCMXN = Object.values(cxcBuckets).reduce((s, b) => s + b.totalMXN, 0);
  const totalCxPMXN = Object.values(cxpBuckets).reduce((s, b) => s + b.totalMXN, 0);

  const renderAgingTable = (buckets, tipo) => {
    const allCfdis = Object.values(buckets).flatMap(b => b.cfdis);
    
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
                  {formatCurrency(bucket.totalMXN, 'MXN')}
                </div>
                <div className="text-xs text-gray-500">{bucket.cfdis.length} factura(s)</div>
              </CardContent>
            </Card>
          ))}
        </div>

        {/* Detail Table */}
        <Card>
          <CardHeader>
            <div className="flex justify-between items-center">
              <div>
                <CardTitle>Detalle de {tipo === 'cxc' ? 'Cuentas por Cobrar' : 'Cuentas por Pagar'}</CardTitle>
                <CardDescription>{allCfdis.length} facturas pendientes</CardDescription>
              </div>
              <Button variant="outline" className="gap-2">
                <Download size={14} />
                Exportar
              </Button>
            </div>
          </CardHeader>
          <CardContent>
            <Table>
              <TableHeader>
                <TableRow className="bg-gray-50">
                  <TableHead>Antigüedad</TableHead>
                  <TableHead>{tipo === 'cxc' ? 'Cliente' : 'Proveedor'}</TableHead>
                  <TableHead>UUID</TableHead>
                  <TableHead>Fecha Emisión</TableHead>
                  <TableHead>Días</TableHead>
                  <TableHead>Moneda</TableHead>
                  <TableHead className="text-right">Total Original</TableHead>
                  <TableHead className="text-right">Pagado</TableHead>
                  <TableHead className="text-right">Pendiente</TableHead>
                  <TableHead className="text-right bg-blue-50">Pendiente MXN</TableHead>
                </TableRow>
              </TableHeader>
              <TableBody>
                {allCfdis.length === 0 ? (
                  <TableRow>
                    <TableCell colSpan={10} className="text-center py-8 text-gray-500">
                      No hay facturas pendientes de {tipo === 'cxc' ? 'cobro' : 'pago'}
                    </TableCell>
                  </TableRow>
                ) : (
                  allCfdis.sort((a, b) => b.diasVencido - a.diasVencido).map(cfdi => {
                    const bucket = getAgingBucket(cfdi.fecha_emision);
                    const bucketInfo = buckets[bucket];
                    const pagado = tipo === 'cxc' ? (cfdi.monto_cobrado || 0) : (cfdi.monto_pagado || 0);
                    
                    return (
                      <TableRow key={cfdi.id} className="hover:bg-gray-50">
                        <TableCell>
                          <span className={`text-xs px-2 py-1 rounded ${bucketInfo.color}`}>
                            {bucketInfo.label}
                          </span>
                        </TableCell>
                        <TableCell className="font-medium max-w-[180px] truncate">
                          <div className="flex items-center gap-2">
                            {tipo === 'cxc' ? <User size={14} className="text-blue-500" /> : <Building2 size={14} className="text-orange-500" />}
                            {getPartyName(cfdi, tipo)}
                          </div>
                        </TableCell>
                        <TableCell className="font-mono text-xs">{cfdi.uuid?.substring(0, 8)}...</TableCell>
                        <TableCell>{format(new Date(cfdi.fecha_emision), 'dd/MM/yyyy')}</TableCell>
                        <TableCell>
                          <span className={`font-mono ${cfdi.diasVencido > 90 ? 'text-red-600 font-bold' : cfdi.diasVencido > 30 ? 'text-orange-600' : 'text-gray-600'}`}>
                            {cfdi.diasVencido} días
                          </span>
                        </TableCell>
                        <TableCell>
                          <span className={`text-xs px-2 py-1 rounded ${cfdi.moneda === 'USD' ? 'bg-green-100 text-green-800' : cfdi.moneda === 'EUR' ? 'bg-purple-100 text-purple-800' : 'bg-gray-100 text-gray-800'}`}>
                            {cfdi.moneda || 'MXN'}
                          </span>
                        </TableCell>
                        <TableCell className="text-right font-mono">{formatCurrency(cfdi.total, cfdi.moneda)}</TableCell>
                        <TableCell className="text-right font-mono text-green-600">{formatCurrency(pagado, cfdi.moneda)}</TableCell>
                        <TableCell className="text-right font-mono font-bold text-orange-600">{formatCurrency(cfdi.pendiente, cfdi.moneda)}</TableCell>
                        <TableCell className="text-right font-mono font-bold bg-blue-50 text-blue-700">{formatCurrency(cfdi.pendienteMXN, 'MXN')}</TableCell>
                      </TableRow>
                    );
                  })
                )}
              </TableBody>
            </Table>
          </CardContent>
        </Card>
      </div>
    );
  };

  return (
    <div className="p-6 space-y-6 bg-[#F8FAFC] min-h-screen" data-testid="aging-page">
      {/* Header */}
      <div className="flex justify-between items-center">
        <div>
          <h1 className="text-3xl font-bold text-[#0F172A]" style={{fontFamily: 'Manrope'}}>
            Aging de Cartera
          </h1>
          <p className="text-[#64748B]">Análisis de antigüedad de Cuentas por Cobrar y por Pagar</p>
        </div>
        <div className="flex items-center gap-4">
          <div className="text-sm text-gray-500">
            TC: USD ${fxRates.USD?.toFixed(2) || 'N/A'} | EUR ${fxRates.EUR?.toFixed(2) || 'N/A'}
          </div>
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
            <div className="text-3xl font-bold text-green-700">{formatCurrency(totalCxCMXN, 'MXN')}</div>
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
            <div className="text-3xl font-bold text-red-700">{formatCurrency(totalCxP)}</div>
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
