import { useState, useEffect, useMemo } from 'react';
import api from '@/api/axios';
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card';
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from '@/components/ui/table';
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from '@/components/ui/select';
import { toast } from 'sonner';
import { format, addWeeks, addDays } from 'date-fns';
import { TrendingUp, TrendingDown, Calendar, RefreshCw, Wallet, AlertTriangle } from 'lucide-react';
import { Button } from '@/components/ui/button';

// All available currencies
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

// Threshold for highlighting significant variances (percentage)
const VARIANCE_THRESHOLD = 20; // 20% deviation from projected

const Reports = () => {
  const [payments, setPayments] = useState([]);
  const [cfdis, setCfdis] = useState([]);
  const [bankSummary, setBankSummary] = useState(null);
  const [loading, setLoading] = useState(true);
  const [selectedCurrency, setSelectedCurrency] = useState('MXN');
  const [fxRates, setFxRates] = useState({ MXN: 1, USD: 17.4545, EUR: 20.4852, GBP: 22.00, JPY: 0.13, CHF: 20.00, CAD: 13.00, CNY: 2.40 });

  useEffect(() => {
    loadData();
  }, []);

  const loadData = async () => {
    setLoading(true);
    try {
      const [paymentsRes, cfdisRes, fxRes, bankRes] = await Promise.all([
        api.get('/payments'),
        api.get('/cfdi?limit=500'),
        api.get('/fx-rates/latest'),
        api.get('/bank-accounts/summary')
      ]);
      setPayments(paymentsRes.data || []);
      setCfdis(cfdisRes.data || []);
      setBankSummary(bankRes.data || null);
      
      // Use FX rates from bank summary (which uses fecha_saldo) as primary source
      if (bankRes.data?.tipos_cambio) {
        setFxRates(prev => ({ ...prev, ...bankRes.data.tipos_cambio }));
      } else if (fxRes.data?.rates) {
        setFxRates(prev => ({ ...prev, ...fxRes.data.rates }));
      }
    } catch (error) {
      toast.error('Error cargando reportes');
    } finally {
      setLoading(false);
    }
  };

  // Get initial bank balance in MXN
  const saldoInicialBancos = useMemo(() => {
    if (!bankSummary) return 0;
    return bankSummary.total_mxn || 0;
  }, [bankSummary]);

  // Convert amount to MXN
  const convertToMXN = (amount, currency) => {
    if (!amount) return 0;
    if (currency === 'MXN' || !currency) return amount;
    const rate = fxRates[currency] || 17.4545;
    return amount * rate;
  };

  // Convert from MXN to selected currency for display
  const convertFromMXN = (amountMXN) => {
    if (selectedCurrency === 'MXN') return amountMXN;
    const rate = fxRates[selectedCurrency] || 1;
    return amountMXN / rate;
  };

  const formatCurrency = (amount) => {
    const converted = convertFromMXN(amount || 0);
    const currency = CURRENCIES.find(c => c.code === selectedCurrency);
    const symbol = currency?.symbol || '$';
    return `${symbol}${converted.toLocaleString('es-MX', {minimumFractionDigits: 2, maximumFractionDigits: 2})}`;
  };

  // Helper to get Monday of a given date
  const getMonday = (date) => {
    const d = new Date(date);
    const day = d.getDay();
    const diff = d.getDate() - day + (day === 0 ? -6 : 1);
    return new Date(d.setDate(diff));
  };

  // ROLLING CASH FLOW MODEL:
  // - S1-S4: 4 semanas históricas (Real)
  // - S5: Semana actual (Actual)  
  // - S6-S18: 13 semanas futuras proyectadas (Proy)
  const HISTORICAL_WEEKS = 4;
  const FORECAST_WEEKS = 13;
  
  const weeksData = useMemo(() => {
    const today = new Date();
    const currentMonday = getMonday(today);
    
    const weeks = [];
    
    // S1-S4: Semanas históricas (Real)
    for (let i = HISTORICAL_WEEKS; i >= 1; i--) {
      const weekStart = addWeeks(currentMonday, -i);
      const weekEnd = addDays(weekStart, 6);
      const weekEndForComparison = addWeeks(weekStart, 1);
      
      weeks.push({
        weekNum: HISTORICAL_WEEKS - i + 1,
        label: `S${HISTORICAL_WEEKS - i + 1}`,
        weekStart,
        weekEnd,
        weekEndForComparison,
        type: 'REAL',
        isPast: true,
        isCurrent: false,
        isFuture: false,
        dateRange: `${format(weekStart, 'dd/MM')} - ${format(weekEnd, 'dd/MM')}`,
        cobrosReales: 0,
        pagosReales: 0,
        cobrosProyectados: 0,
        pagosProyectados: 0,
        // Store original projections for variance calculation
        cobrosProyectadosOriginal: 0,
        pagosProyectadosOriginal: 0
      });
    }
    
    // S5: Semana actual (Actual)
    const currentWeekStart = currentMonday;
    const currentWeekEnd = addDays(currentWeekStart, 6);
    weeks.push({
      weekNum: HISTORICAL_WEEKS + 1,
      label: `S${HISTORICAL_WEEKS + 1}`,
      weekStart: currentWeekStart,
      weekEnd: currentWeekEnd,
      weekEndForComparison: addWeeks(currentWeekStart, 1),
      type: 'ACTUAL',
      isPast: false,
      isCurrent: true,
      isFuture: false,
      dateRange: `${format(currentWeekStart, 'dd/MM')} - ${format(currentWeekEnd, 'dd/MM')}`,
      cobrosReales: 0,
      pagosReales: 0,
      cobrosProyectados: 0,
      pagosProyectados: 0,
      cobrosProyectadosOriginal: 0,
      pagosProyectadosOriginal: 0
    });
    
    // S6-S18: 13 semanas futuras proyectadas (Proy)
    for (let i = 1; i <= FORECAST_WEEKS; i++) {
      const weekStart = addWeeks(currentMonday, i);
      const weekEnd = addDays(weekStart, 6);
      const weekEndForComparison = addWeeks(weekStart, 1);
      
      weeks.push({
        weekNum: HISTORICAL_WEEKS + 1 + i,
        label: `S${HISTORICAL_WEEKS + 1 + i}`,
        weekStart,
        weekEnd,
        weekEndForComparison,
        type: 'PROYECTADO',
        isPast: false,
        isCurrent: false,
        isFuture: true,
        dateRange: `${format(weekStart, 'dd/MM')} - ${format(weekEnd, 'dd/MM')}`,
        cobrosReales: 0,
        pagosReales: 0,
        cobrosProyectados: 0,
        pagosProyectados: 0,
        cobrosProyectadosOriginal: 0,
        pagosProyectadosOriginal: 0
      });
    }
    
    // Track processed bank transactions to avoid duplicates
    const processedBankTxns = new Set();
    
    // Process REAL payments (completed)
    payments.forEach(payment => {
      if (payment.estatus !== 'completado') return;
      
      const bankTxnId = payment.bank_transaction_id;
      if (bankTxnId) {
        if (processedBankTxns.has(bankTxnId)) return;
        processedBankTxns.add(bankTxnId);
      }
      
      const fechaStr = payment.fecha_pago || payment.fecha_vencimiento;
      if (!fechaStr) return;
      
      let paymentDate;
      try {
        paymentDate = new Date(fechaStr);
        if (isNaN(paymentDate.getTime())) return;
      } catch { return; }
      
      const weekIdx = weeks.findIndex(w => 
        paymentDate >= w.weekStart && paymentDate < w.weekEndForComparison
      );
      
      if (weekIdx === -1) return;
      
      const montoMXN = convertToMXN(payment.monto, payment.moneda);
      
      if (payment.tipo === 'cobro') {
        weeks[weekIdx].cobrosReales += montoMXN;
      } else {
        weeks[weekIdx].pagosReales += montoMXN;
      }
    });
    
    // Process PROJECTED data from pending CFDIs
    cfdis.forEach(cfdi => {
      const total = cfdi.total || 0;
      const pagado = cfdi.monto_pagado || 0;
      const cobrado = cfdi.monto_cobrado || 0;
      
      let pendiente = 0;
      if (cfdi.tipo_cfdi === 'ingreso') {
        pendiente = total - cobrado;
      } else if (cfdi.tipo_cfdi === 'egreso') {
        pendiente = total - pagado;
      }
      
      if (pendiente <= 0) return;
      
      const pendienteMXN = convertToMXN(pendiente, cfdi.moneda);
      
      let estimatedDate;
      if (cfdi.fecha_vencimiento) {
        estimatedDate = new Date(cfdi.fecha_vencimiento);
      } else {
        const emision = new Date(cfdi.fecha_emision);
        estimatedDate = new Date(emision.getTime() + 30 * 24 * 60 * 60 * 1000);
      }
      
      const weekIdx = weeks.findIndex(w => 
        estimatedDate >= w.weekStart && estimatedDate < w.weekEndForComparison
      );
      
      if (weekIdx === -1) return;
      
      // Add projections to current and future weeks
      if (weeks[weekIdx].type === 'ACTUAL' || weeks[weekIdx].type === 'PROYECTADO') {
        if (cfdi.tipo_cfdi === 'ingreso') {
          weeks[weekIdx].cobrosProyectados += pendienteMXN;
          weeks[weekIdx].cobrosProyectadosOriginal += pendienteMXN;
        } else if (cfdi.tipo_cfdi === 'egreso') {
          weeks[weekIdx].pagosProyectados += pendienteMXN;
          weeks[weekIdx].pagosProyectadosOriginal += pendienteMXN;
        }
      }
      
      // For historical weeks, store what was projected (for variance)
      if (weeks[weekIdx].type === 'REAL') {
        if (cfdi.tipo_cfdi === 'ingreso') {
          weeks[weekIdx].cobrosProyectadosOriginal += pendienteMXN;
        } else if (cfdi.tipo_cfdi === 'egreso') {
          weeks[weekIdx].pagosProyectadosOriginal += pendienteMXN;
        }
      }
    });
    
    return weeks;
  }, [payments, cfdis, fxRates]);

  // Calculate running bank balance for each week
  const weeksWithBalance = useMemo(() => {
    let runningBalance = saldoInicialBancos;
    
    return weeksData.map((week, idx) => {
      // For historical weeks, use real data
      // For current/future, mix real + projected
      const cobros = week.cobrosReales + (week.isFuture || week.isCurrent ? week.cobrosProyectados : 0);
      const pagos = week.pagosReales + (week.isFuture || week.isCurrent ? week.pagosProyectados : 0);
      const flujoNeto = cobros - pagos;
      
      // Calculate balance at end of week
      const saldoInicial = runningBalance;
      const saldoFinal = runningBalance + flujoNeto;
      runningBalance = saldoFinal;
      
      // Calculate variance (Real vs Projected) for historical weeks
      let variacionCobros = 0;
      let variacionPagos = 0;
      let variacionPorcentajeCobros = 0;
      let variacionPorcentajePagos = 0;
      let hasSignificantVariance = false;
      
      if (week.isPast && (week.cobrosProyectadosOriginal > 0 || week.pagosProyectadosOriginal > 0)) {
        // Cobros variance
        if (week.cobrosProyectadosOriginal > 0) {
          variacionCobros = week.cobrosReales - week.cobrosProyectadosOriginal;
          variacionPorcentajeCobros = ((week.cobrosReales - week.cobrosProyectadosOriginal) / week.cobrosProyectadosOriginal) * 100;
          if (Math.abs(variacionPorcentajeCobros) > VARIANCE_THRESHOLD) {
            hasSignificantVariance = true;
          }
        }
        
        // Pagos variance
        if (week.pagosProyectadosOriginal > 0) {
          variacionPagos = week.pagosReales - week.pagosProyectadosOriginal;
          variacionPorcentajePagos = ((week.pagosReales - week.pagosProyectadosOriginal) / week.pagosProyectadosOriginal) * 100;
          if (Math.abs(variacionPorcentajePagos) > VARIANCE_THRESHOLD) {
            hasSignificantVariance = true;
          }
        }
      }
      
      return {
        ...week,
        saldoInicial,
        saldoFinal,
        flujoNeto,
        variacionCobros,
        variacionPagos,
        variacionPorcentajeCobros,
        variacionPorcentajePagos,
        hasSignificantVariance
      };
    });
  }, [weeksData, saldoInicialBancos]);

  // Calculate totals
  const totals = useMemo(() => {
    return weeksWithBalance.reduce((acc, week) => {
      acc.cobrosReales += week.cobrosReales;
      acc.pagosReales += week.pagosReales;
      acc.cobrosProyectados += week.cobrosProyectados;
      acc.pagosProyectados += week.pagosProyectados;
      return acc;
    }, { cobrosReales: 0, pagosReales: 0, cobrosProyectados: 0, pagosProyectados: 0 });
  }, [weeksWithBalance]);

  // Get final projected balance
  const saldoFinalProyectado = weeksWithBalance.length > 0 
    ? weeksWithBalance[weeksWithBalance.length - 1].saldoFinal 
    : saldoInicialBancos;

  if (loading) return <div className="p-8">Cargando...</div>;

  return (
    <div className="p-8 space-y-6" data-testid="reports-page">
      {/* Header */}
      <div className="flex justify-between items-start">
        <div>
          <h1 className="text-4xl font-bold text-[#0F172A] mb-2" style={{fontFamily: 'Manrope'}}>Reportes</h1>
          <p className="text-[#64748B]">Rolling Cash Flow - 18 Semanas (4 Real + 1 Actual + 13 Proy)</p>
          <p className="text-xs text-[#94A3B8] mt-1">
            S1-S4 = Historial • S5 = Semana actual • S6-S18 = Proyección 13 semanas
          </p>
        </div>
        <div className="flex gap-2 items-center">
          <Select value={selectedCurrency} onValueChange={setSelectedCurrency}>
            <SelectTrigger className="w-40" data-testid="currency-selector">
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
          <Button variant="outline" size="icon" onClick={loadData}>
            <RefreshCw size={16} />
          </Button>
        </div>
      </div>

      {/* Bank Balance Summary Cards */}
      <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
        <Card className="border-blue-200 bg-gradient-to-br from-blue-50 to-blue-100">
          <CardHeader className="pb-2">
            <CardTitle className="text-sm text-blue-800 flex items-center gap-2">
              <Wallet size={16} />
              Saldo Inicial Bancos
            </CardTitle>
          </CardHeader>
          <CardContent>
            <p className="text-2xl font-bold mono text-blue-700">
              {formatCurrency(saldoInicialBancos)}
            </p>
            <p className="text-xs text-blue-600 mt-1">
              {bankSummary?.por_moneda ? Object.keys(bankSummary.por_moneda).length : 0} moneda(s) • 
              {bankSummary?.total_cuentas || 0} cuenta(s)
            </p>
            {bankSummary?.por_moneda && Object.entries(bankSummary.por_moneda).length > 0 && (
              <div className="mt-2 text-xs space-y-1">
                {Object.entries(bankSummary.por_moneda).map(([moneda, info]) => (
                  <div key={moneda} className="flex justify-between text-blue-700">
                    <span>{moneda}:</span>
                    <span className="mono">{moneda === 'MXN' ? '$' : ''}{info.saldo?.toLocaleString('es-MX', {minimumFractionDigits: 2})} {moneda !== 'MXN' && `(TC: ${bankSummary.tipos_cambio?.[moneda] || '?'})`}</span>
                  </div>
                ))}
              </div>
            )}
          </CardContent>
        </Card>

        <Card className={`border-2 ${(totals.cobrosReales - totals.pagosReales) >= 0 ? 'border-green-400 bg-gradient-to-br from-green-50 to-green-100' : 'border-red-400 bg-gradient-to-br from-red-50 to-red-100'}`}>
          <CardHeader className="pb-2">
            <CardTitle className="text-sm text-gray-800 flex items-center gap-2">
              {(totals.cobrosReales - totals.pagosReales) >= 0 ? <TrendingUp size={16} /> : <TrendingDown size={16} />}
              Flujo Neto Real (S1-S5)
            </CardTitle>
          </CardHeader>
          <CardContent>
            <p className={`text-2xl font-bold mono ${(totals.cobrosReales - totals.pagosReales) >= 0 ? 'text-green-700' : 'text-red-700'}`}>
              {(totals.cobrosReales - totals.pagosReales) >= 0 ? '+' : ''}{formatCurrency(totals.cobrosReales - totals.pagosReales)}
            </p>
          </CardContent>
        </Card>

        <Card className={`border-2 ${saldoFinalProyectado >= 0 ? 'border-emerald-400 bg-gradient-to-br from-emerald-50 to-emerald-100' : 'border-red-400 bg-gradient-to-br from-red-50 to-red-100'}`}>
          <CardHeader className="pb-2">
            <CardTitle className="text-sm text-gray-800 flex items-center gap-2">
              <Calendar size={16} />
              Saldo Proyectado S18
            </CardTitle>
          </CardHeader>
          <CardContent>
            <p className={`text-2xl font-bold mono ${saldoFinalProyectado >= 0 ? 'text-emerald-700' : 'text-red-700'}`}>
              {formatCurrency(saldoFinalProyectado)}
            </p>
            <p className="text-xs text-gray-600 mt-1">
              Al {weeksWithBalance.length > 0 ? format(weeksWithBalance[weeksWithBalance.length - 1].weekEnd, 'dd/MM/yyyy') : '-'}
            </p>
          </CardContent>
        </Card>
      </div>

      {/* FX Rate notice */}
      {selectedCurrency !== 'MXN' && (
        <div className="bg-blue-50 border border-blue-200 rounded-lg p-3 text-sm text-blue-800">
          <strong>TC:</strong> 1 {selectedCurrency} = ${fxRates[selectedCurrency]?.toFixed(4) || '?'} MXN
        </div>
      )}

      {/* Main Table */}
      <Card className="border-[#E2E8F0]">
        <CardHeader className="pb-2">
          <CardTitle className="flex items-center gap-2 text-lg">
            <Calendar size={20} />
            Flujo de Efectivo con Saldo de Bancos
          </CardTitle>
          <CardDescription className="flex flex-wrap gap-4">
            <span className="inline-flex items-center gap-1">
              <span className="w-2 h-2 rounded-full bg-green-500"></span> Cobrado (Real)
            </span>
            <span className="inline-flex items-center gap-1">
              <span className="w-2 h-2 rounded-full bg-red-500"></span> Pagado (Real)
            </span>
            <span className="inline-flex items-center gap-1">
              <span className="w-2 h-2 rounded-full bg-gray-400"></span> Proyectado
            </span>
            <span className="inline-flex items-center gap-1">
              <AlertTriangle size={12} className="text-amber-500" /> Variación &gt;{VARIANCE_THRESHOLD}%
            </span>
          </CardDescription>
        </CardHeader>
        <CardContent>
          <div className="overflow-x-auto">
            <Table className="text-sm">
              <TableHeader>
                <TableRow className="bg-gray-50">
                  <TableHead className="w-14 font-bold">Sem</TableHead>
                  <TableHead className="w-28">Período</TableHead>
                  <TableHead className="w-16 text-center">Tipo</TableHead>
                  <TableHead className="text-right">Cobros Real</TableHead>
                  <TableHead className="text-right">Pagos Real</TableHead>
                  <TableHead className="text-right bg-gray-100">Cobros Proy.</TableHead>
                  <TableHead className="text-right bg-gray-100">Pagos Proy.</TableHead>
                  <TableHead className="text-right font-bold">Flujo Neto</TableHead>
                  <TableHead className="text-right font-bold bg-blue-50">Saldo Bancos</TableHead>
                  <TableHead className="text-center">Variación</TableHead>
                </TableRow>
              </TableHeader>
              <TableBody>
                {/* Initial Balance Row */}
                <TableRow className="bg-blue-50 border-b-2 border-blue-200">
                  <TableCell colSpan={8} className="font-semibold text-blue-800">
                    SALDO INICIAL DE BANCOS
                  </TableCell>
                  <TableCell className="mono text-right font-bold text-blue-700 bg-blue-100">
                    {formatCurrency(saldoInicialBancos)}
                  </TableCell>
                  <TableCell></TableCell>
                </TableRow>
                
                {weeksWithBalance.map((week) => {
                  const isNegativeBalance = week.saldoFinal < 0;
                  
                  return (
                    <TableRow 
                      key={week.label} 
                      className={`
                        ${week.isCurrent ? 'bg-blue-50 border-l-4 border-l-blue-500' : ''} 
                        ${week.isPast ? '' : 'bg-gray-50/50'}
                        ${week.hasSignificantVariance ? 'bg-amber-50' : ''}
                        ${isNegativeBalance ? 'bg-red-50' : ''}
                      `}
                    >
                      <TableCell className="mono font-bold">{week.label}</TableCell>
                      <TableCell className="text-xs">{week.dateRange}</TableCell>
                      <TableCell className="text-center">
                        {week.type === 'REAL' && (
                          <span className="px-1.5 py-0.5 text-xs rounded bg-green-100 text-green-800 font-medium">Real</span>
                        )}
                        {week.type === 'ACTUAL' && (
                          <span className="px-1.5 py-0.5 text-xs rounded bg-blue-100 text-blue-800 font-semibold">Actual</span>
                        )}
                        {week.type === 'PROYECTADO' && (
                          <span className="px-1.5 py-0.5 text-xs rounded bg-gray-100 text-gray-600">Proy</span>
                        )}
                      </TableCell>
                      <TableCell className="mono text-right text-green-600 font-semibold">
                        {week.cobrosReales > 0 ? formatCurrency(week.cobrosReales) : '-'}
                      </TableCell>
                      <TableCell className="mono text-right text-red-600 font-semibold">
                        {week.pagosReales > 0 ? formatCurrency(week.pagosReales) : '-'}
                      </TableCell>
                      <TableCell className="mono text-right text-gray-500 bg-gray-50">
                        {week.cobrosProyectados > 0 ? formatCurrency(week.cobrosProyectados) : '-'}
                      </TableCell>
                      <TableCell className="mono text-right text-gray-500 bg-gray-50">
                        {week.pagosProyectados > 0 ? formatCurrency(week.pagosProyectados) : '-'}
                      </TableCell>
                      <TableCell className={`mono text-right font-bold ${week.flujoNeto >= 0 ? 'text-green-700' : 'text-red-700'}`}>
                        {week.flujoNeto !== 0 ? (
                          <>{week.flujoNeto >= 0 ? '+' : ''}{formatCurrency(week.flujoNeto)}</>
                        ) : '-'}
                      </TableCell>
                      <TableCell className={`mono text-right font-bold bg-blue-50 ${isNegativeBalance ? 'text-red-700 bg-red-100' : 'text-blue-700'}`}>
                        {formatCurrency(week.saldoFinal)}
                      </TableCell>
                      <TableCell className="text-center">
                        {week.isPast && week.hasSignificantVariance && (
                          <div className="flex flex-col items-center gap-1">
                            <AlertTriangle size={14} className="text-amber-500" />
                            {week.variacionPorcentajeCobros !== 0 && Math.abs(week.variacionPorcentajeCobros) > VARIANCE_THRESHOLD && (
                              <span className={`text-xs px-1 py-0.5 rounded ${week.variacionPorcentajeCobros > 0 ? 'bg-green-100 text-green-700' : 'bg-red-100 text-red-700'}`}>
                                C: {week.variacionPorcentajeCobros > 0 ? '+' : ''}{week.variacionPorcentajeCobros.toFixed(0)}%
                              </span>
                            )}
                            {week.variacionPorcentajePagos !== 0 && Math.abs(week.variacionPorcentajePagos) > VARIANCE_THRESHOLD && (
                              <span className={`text-xs px-1 py-0.5 rounded ${week.variacionPorcentajePagos < 0 ? 'bg-green-100 text-green-700' : 'bg-red-100 text-red-700'}`}>
                                P: {week.variacionPorcentajePagos > 0 ? '+' : ''}{week.variacionPorcentajePagos.toFixed(0)}%
                              </span>
                            )}
                          </div>
                        )}
                      </TableCell>
                    </TableRow>
                  );
                })}
                
                {/* TOTALS */}
                <TableRow className="bg-[#0F172A] text-white font-bold">
                  <TableCell colSpan={3} className="font-bold">TOTAL</TableCell>
                  <TableCell className="mono text-right text-green-400">{formatCurrency(totals.cobrosReales)}</TableCell>
                  <TableCell className="mono text-right text-red-400">{formatCurrency(totals.pagosReales)}</TableCell>
                  <TableCell className="mono text-right text-gray-400">{formatCurrency(totals.cobrosProyectados)}</TableCell>
                  <TableCell className="mono text-right text-gray-400">{formatCurrency(totals.pagosProyectados)}</TableCell>
                  <TableCell className={`mono text-right font-bold ${(totals.cobrosReales + totals.cobrosProyectados - totals.pagosReales - totals.pagosProyectados) >= 0 ? 'text-green-400' : 'text-red-400'}`}>
                    {formatCurrency(totals.cobrosReales + totals.cobrosProyectados - totals.pagosReales - totals.pagosProyectados)}
                  </TableCell>
                  <TableCell className={`mono text-right font-bold ${saldoFinalProyectado >= 0 ? 'text-blue-400' : 'text-red-400'}`}>
                    {formatCurrency(saldoFinalProyectado)}
                  </TableCell>
                  <TableCell></TableCell>
                </TableRow>
              </TableBody>
            </Table>
          </div>
        </CardContent>
      </Card>

      {/* Summary Cards */}
      <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-4">
        <Card className="border-green-200 bg-green-50">
          <CardHeader className="pb-2">
            <CardTitle className="text-sm text-green-800 flex items-center gap-2">
              <TrendingUp size={16} />
              Total Cobrado (Real)
            </CardTitle>
          </CardHeader>
          <CardContent>
            <p className="text-2xl font-bold mono text-green-700">
              {formatCurrency(totals.cobrosReales)}
            </p>
          </CardContent>
        </Card>

        <Card className="border-red-200 bg-red-50">
          <CardHeader className="pb-2">
            <CardTitle className="text-sm text-red-800 flex items-center gap-2">
              <TrendingDown size={16} />
              Total Pagado (Real)
            </CardTitle>
          </CardHeader>
          <CardContent>
            <p className="text-2xl font-bold mono text-red-700">
              {formatCurrency(totals.pagosReales)}
            </p>
          </CardContent>
        </Card>

        <Card className="border-blue-200 bg-blue-50">
          <CardHeader className="pb-2">
            <CardTitle className="text-sm text-blue-800">Por Cobrar (Proy.)</CardTitle>
          </CardHeader>
          <CardContent>
            <p className="text-2xl font-bold mono text-green-600">+{formatCurrency(totals.cobrosProyectados)}</p>
          </CardContent>
        </Card>

        <Card className="border-orange-200 bg-orange-50">
          <CardHeader className="pb-2">
            <CardTitle className="text-sm text-orange-800">Por Pagar (Proy.)</CardTitle>
          </CardHeader>
          <CardContent>
            <p className="text-2xl font-bold mono text-red-600">-{formatCurrency(totals.pagosProyectados)}</p>
          </CardContent>
        </Card>
      </div>
    </div>
  );
};

export default Reports;
