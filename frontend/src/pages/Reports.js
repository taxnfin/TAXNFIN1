import { useState, useEffect, useMemo } from 'react';
import api from '@/api/axios';
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card';
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from '@/components/ui/table';
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from '@/components/ui/select';
import { toast } from 'sonner';
import { format, startOfWeek, addWeeks, isBefore, isAfter } from 'date-fns';
import { es } from 'date-fns/locale';
import { TrendingUp, TrendingDown, Calendar, RefreshCw, ArrowUpRight, ArrowDownRight, Minus } from 'lucide-react';
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

const Reports = () => {
  const [payments, setPayments] = useState([]);
  const [cfdis, setCfdis] = useState([]);
  const [loading, setLoading] = useState(true);
  const [selectedCurrency, setSelectedCurrency] = useState('MXN');
  const [fxRates, setFxRates] = useState({ MXN: 1, USD: 17.50, EUR: 19.00, GBP: 22.00, JPY: 0.13, CHF: 20.00, CAD: 13.00, CNY: 2.40 });
  const [weekStartDay, setWeekStartDay] = useState(1); // Monday

  useEffect(() => {
    loadData();
  }, []);

  const loadData = async () => {
    setLoading(true);
    try {
      const [paymentsRes, cfdisRes, fxRes] = await Promise.all([
        api.get('/payments'),
        api.get('/cfdi?limit=500'),
        api.get('/fx-rates/latest')
      ]);
      setPayments(paymentsRes.data || []);
      setCfdis(cfdisRes.data || []);
      
      // Load FX rates
      if (fxRes.data?.rates) {
        setFxRates(prev => ({ ...prev, ...fxRes.data.rates }));
      }
    } catch (error) {
      toast.error('Error cargando reportes');
    } finally {
      setLoading(false);
    }
  };

  // Convert amount to MXN first, then to target currency
  const convertToMXN = (amount, currency) => {
    if (!amount) return 0;
    if (currency === 'MXN' || !currency) return amount;
    const rate = fxRates[currency] || 17.50;
    return amount * rate;
  };

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

  // Generate 13 weeks starting from current week
  const weeksData = useMemo(() => {
    const weeks = [];
    const today = new Date();
    const currentWeekStart = startOfWeek(today, { weekStartsOn: weekStartDay });
    
    // Start from 2 weeks ago to include historical data
    const startDate = addWeeks(currentWeekStart, -2);
    
    for (let i = 0; i < 15; i++) { // 2 past + 13 future
      const weekStart = addWeeks(startDate, i);
      const weekEnd = addWeeks(weekStart, 1);
      const isPast = weekEnd <= today;
      const isCurrent = weekStart <= today && today < weekEnd;
      
      weeks.push({
        weekNum: i - 1, // -1, 0, 1, 2, ... (0 = current week)
        label: i <= 1 ? (i === 0 ? 'S-2' : 'S-1') : `S${i - 1}`,
        weekStart,
        weekEnd,
        isPast,
        isCurrent,
        dateRange: `${format(weekStart, 'dd/MM')} - ${format(weekEnd, 'dd/MM')}`,
        // Real data (from completed payments)
        cobrosReales: 0,
        pagosReales: 0,
        // Projected data (from pending CFDIs)
        cobrosProyectados: 0,
        pagosProyectados: 0
      });
    }
    
    // Process REAL payments (completed)
    payments.forEach(payment => {
      if (payment.estatus !== 'completado') return;
      
      const fechaStr = payment.fecha_pago || payment.fecha_vencimiento;
      if (!fechaStr) return;
      
      let paymentDate;
      try {
        paymentDate = new Date(fechaStr);
        if (isNaN(paymentDate.getTime())) return;
      } catch { return; }
      
      const weekIdx = weeks.findIndex(w => paymentDate >= w.weekStart && paymentDate < w.weekEnd);
      if (weekIdx === -1) return;
      
      const montoMXN = convertToMXN(payment.monto, payment.moneda);
      
      if (payment.tipo === 'cobro') {
        weeks[weekIdx].cobrosReales += montoMXN;
      } else {
        weeks[weekIdx].pagosReales += montoMXN;
      }
    });
    
    // Process PROJECTED data from pending CFDIs (for future weeks)
    cfdis.forEach(cfdi => {
      // Skip if already fully paid/collected
      const total = cfdi.total || 0;
      const pagado = cfdi.monto_pagado || 0;
      const cobrado = cfdi.monto_cobrado || 0;
      
      // Calculate pending amount
      let pendiente = 0;
      if (cfdi.tipo_cfdi === 'ingreso') {
        pendiente = total - cobrado;
      } else if (cfdi.tipo_cfdi === 'egreso') {
        pendiente = total - pagado;
      }
      
      if (pendiente <= 0) return;
      
      // Convert to MXN
      const pendienteMXN = convertToMXN(pendiente, cfdi.moneda);
      
      // Use fecha_vencimiento if available, otherwise estimate based on payment terms (30 days default)
      let estimatedDate;
      if (cfdi.fecha_vencimiento) {
        estimatedDate = new Date(cfdi.fecha_vencimiento);
      } else {
        const emision = new Date(cfdi.fecha_emision);
        estimatedDate = new Date(emision.getTime() + 30 * 24 * 60 * 60 * 1000); // 30 days default
      }
      
      // Find the week for this projected payment
      const weekIdx = weeks.findIndex(w => estimatedDate >= w.weekStart && estimatedDate < w.weekEnd);
      if (weekIdx === -1 || (weeks[weekIdx].isPast && !weeks[weekIdx].isCurrent)) return; // Only add to future weeks
      
      if (cfdi.tipo_cfdi === 'ingreso') {
        weeks[weekIdx].cobrosProyectados += pendienteMXN;
      } else if (cfdi.tipo_cfdi === 'egreso') {
        weeks[weekIdx].pagosProyectados += pendienteMXN;
      }
    });
    
    // Calculate running balance
    let saldoInicial = 0; // Will be updated with actual bank balance if available
    weeks.forEach(week => {
      // For past weeks: use REAL data only
      // For current/future weeks: combine real + projected
      if (week.isPast) {
        week.ingresos = week.cobrosReales;
        week.egresos = week.pagosReales;
      } else {
        week.ingresos = week.cobrosReales + week.cobrosProyectados;
        week.egresos = week.pagosReales + week.pagosProyectados;
      }
      
      week.flujoNeto = week.ingresos - week.egresos;
      week.saldoInicial = saldoInicial;
      week.saldoFinal = saldoInicial + week.flujoNeto;
      saldoInicial = week.saldoFinal;
      
      // Calculate variance (only for past weeks where we have both real and projected)
      if (week.isPast && (week.cobrosProyectados > 0 || week.pagosProyectados > 0)) {
        week.variacionCobros = week.cobrosReales - week.cobrosProyectados;
        week.variacionPagos = week.pagosReales - week.pagosProyectados;
        week.variacionNeto = week.flujoNeto - (week.cobrosProyectados - week.pagosProyectados);
      }
    });
    
    // Remove first week if empty
    if (weeks[0].cobrosReales === 0 && weeks[0].pagosReales === 0) {
      weeks.shift();
    }
    
    return weeks.slice(0, 13); // Return 13 weeks
  }, [payments, cfdis, fxRates, weekStartDay]);

  // Calculate totals
  const totals = useMemo(() => {
    return weeksData.reduce((acc, week) => {
      acc.cobrosReales += week.cobrosReales;
      acc.pagosReales += week.pagosReales;
      acc.cobrosProyectados += week.cobrosProyectados;
      acc.pagosProyectados += week.pagosProyectados;
      acc.ingresos += week.ingresos;
      acc.egresos += week.egresos;
      acc.flujoNeto += week.flujoNeto;
      return acc;
    }, { cobrosReales: 0, pagosReales: 0, cobrosProyectados: 0, pagosProyectados: 0, ingresos: 0, egresos: 0, flujoNeto: 0 });
  }, [weeksData]);

  if (loading) return <div className="p-8">Cargando...</div>;

  return (
    <div className="p-8 space-y-6" data-testid="reports-page">
      {/* Header with Currency Selector */}
      <div className="flex justify-between items-start">
        <div>
          <h1 className="text-4xl font-bold text-[#0F172A] mb-2" style={{fontFamily: 'Manrope'}}>Reportes</h1>
          <p className="text-[#64748B]">Análisis y reportes financieros - Real vs Proyectado</p>
        </div>
        <div className="flex gap-2 items-center">
          <Select value={selectedCurrency} onValueChange={setSelectedCurrency}>
            <SelectTrigger className="w-40" data-testid="currency-selector">
              <SelectValue />
            </SelectTrigger>
            <SelectContent>
              {CURRENCIES.map(c => (
                <SelectItem key={c.code} value={c.code}>
                  {c.symbol} {c.code} - {c.name}
                </SelectItem>
              ))}
            </SelectContent>
          </Select>
          <Button variant="outline" size="icon" onClick={loadData}>
            <RefreshCw size={16} />
          </Button>
        </div>
      </div>

      {/* Currency conversion notice */}
      {selectedCurrency !== 'MXN' && (
        <div className="bg-blue-50 border border-blue-200 rounded-lg p-3 text-sm text-blue-800">
          <strong>Tipo de cambio:</strong> 1 {selectedCurrency} = ${fxRates[selectedCurrency]?.toFixed(4) || '?'} MXN
        </div>
      )}

      {/* Main Cashflow Table */}
      <Card className="border-[#E2E8F0]">
        <CardHeader>
          <CardTitle className="flex items-center gap-2">
            <Calendar size={20} />
            Flujo de Efectivo - 13 Semanas Rolling
          </CardTitle>
          <CardDescription>
            <span className="inline-flex items-center gap-2 mr-4">
              <span className="w-3 h-3 rounded-full bg-green-500"></span> Cobrado/Pagado (Real)
            </span>
            <span className="inline-flex items-center gap-2 mr-4">
              <span className="w-3 h-3 rounded-full bg-gray-400"></span> Proyectado
            </span>
            <span className="inline-flex items-center gap-2">
              <span className="w-3 h-3 rounded-full bg-yellow-500"></span> Variación
            </span>
          </CardDescription>
        </CardHeader>
        <CardContent>
          <div className="overflow-x-auto">
            <Table className="data-table text-sm">
              <TableHeader>
                <TableRow>
                  <TableHead className="w-20 font-bold">Semana</TableHead>
                  <TableHead className="w-28">Período</TableHead>
                  <TableHead className="w-20">Estado</TableHead>
                  <TableHead className="text-right">Cobros Real</TableHead>
                  <TableHead className="text-right">Pagos Real</TableHead>
                  <TableHead className="text-right bg-gray-50">Cobros Proy.</TableHead>
                  <TableHead className="text-right bg-gray-50">Pagos Proy.</TableHead>
                  <TableHead className="text-right bg-yellow-50">Var. Cobros</TableHead>
                  <TableHead className="text-right bg-yellow-50">Var. Pagos</TableHead>
                  <TableHead className="text-right font-bold">Flujo Neto</TableHead>
                </TableRow>
              </TableHeader>
              <TableBody>
                {weeksData.map((week) => {
                  const varCobros = week.variacionCobros || 0;
                  const varPagos = week.variacionPagos || 0;
                  
                  return (
                    <TableRow 
                      key={week.label} 
                      data-testid={`cashflow-week-${week.label}`}
                      className={week.isCurrent ? 'bg-blue-50' : week.isPast ? 'bg-gray-50' : ''}
                    >
                      <TableCell className="mono font-bold">{week.label}</TableCell>
                      <TableCell className="text-xs">{week.dateRange}</TableCell>
                      <TableCell>
                        {week.isPast && !week.isCurrent && (
                          <span className="px-2 py-0.5 text-xs rounded-full bg-green-100 text-green-800">Real</span>
                        )}
                        {week.isCurrent && (
                          <span className="px-2 py-0.5 text-xs rounded-full bg-blue-100 text-blue-800">Actual</span>
                        )}
                        {!week.isPast && !week.isCurrent && (
                          <span className="px-2 py-0.5 text-xs rounded-full bg-gray-100 text-gray-600">Proy.</span>
                        )}
                      </TableCell>
                      
                      {/* Real Data */}
                      <TableCell className="mono text-right text-green-600 font-semibold">
                        {week.cobrosReales > 0 ? formatCurrency(week.cobrosReales) : '-'}
                      </TableCell>
                      <TableCell className="mono text-right text-red-600 font-semibold">
                        {week.pagosReales > 0 ? formatCurrency(week.pagosReales) : '-'}
                      </TableCell>
                      
                      {/* Projected Data */}
                      <TableCell className="mono text-right text-gray-500 bg-gray-50">
                        {week.cobrosProyectados > 0 ? formatCurrency(week.cobrosProyectados) : '-'}
                      </TableCell>
                      <TableCell className="mono text-right text-gray-500 bg-gray-50">
                        {week.pagosProyectados > 0 ? formatCurrency(week.pagosProyectados) : '-'}
                      </TableCell>
                      
                      {/* Variance */}
                      <TableCell className={`mono text-right bg-yellow-50 ${varCobros >= 0 ? 'text-green-600' : 'text-red-600'}`}>
                        {week.isPast && week.cobrosProyectados > 0 ? (
                          <span className="flex items-center justify-end gap-1">
                            {varCobros >= 0 ? <ArrowUpRight size={12} /> : <ArrowDownRight size={12} />}
                            {formatCurrency(Math.abs(varCobros))}
                          </span>
                        ) : '-'}
                      </TableCell>
                      <TableCell className={`mono text-right bg-yellow-50 ${varPagos <= 0 ? 'text-green-600' : 'text-red-600'}`}>
                        {week.isPast && week.pagosProyectados > 0 ? (
                          <span className="flex items-center justify-end gap-1">
                            {varPagos <= 0 ? <ArrowDownRight size={12} /> : <ArrowUpRight size={12} />}
                            {formatCurrency(Math.abs(varPagos))}
                          </span>
                        ) : '-'}
                      </TableCell>
                      
                      {/* Net Flow */}
                      <TableCell className={`mono text-right font-bold ${week.flujoNeto >= 0 ? 'text-green-700' : 'text-red-700'}`}>
                        {week.flujoNeto !== 0 ? (
                          <>
                            {week.flujoNeto >= 0 ? '+' : ''}{formatCurrency(week.flujoNeto)}
                          </>
                        ) : '-'}
                      </TableCell>
                    </TableRow>
                  );
                })}
                
                {/* TOTALS Row */}
                <TableRow className="bg-[#0F172A] text-white font-bold">
                  <TableCell className="font-bold">TOTAL</TableCell>
                  <TableCell></TableCell>
                  <TableCell></TableCell>
                  <TableCell className="mono text-right text-green-400">{formatCurrency(totals.cobrosReales)}</TableCell>
                  <TableCell className="mono text-right text-red-400">{formatCurrency(totals.pagosReales)}</TableCell>
                  <TableCell className="mono text-right text-gray-400">{formatCurrency(totals.cobrosProyectados)}</TableCell>
                  <TableCell className="mono text-right text-gray-400">{formatCurrency(totals.pagosProyectados)}</TableCell>
                  <TableCell className="text-right"></TableCell>
                  <TableCell className="text-right"></TableCell>
                  <TableCell className={`mono text-right font-bold ${totals.flujoNeto >= 0 ? 'text-green-400' : 'text-red-400'}`}>
                    {totals.flujoNeto >= 0 ? '+' : ''}{formatCurrency(totals.flujoNeto)}
                  </TableCell>
                </TableRow>
              </TableBody>
            </Table>
          </div>
        </CardContent>
      </Card>

      {/* Summary Cards */}
      <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-4">
        {/* Real Income */}
        <Card className="border-green-200 bg-green-50">
          <CardHeader className="pb-2">
            <CardTitle className="text-sm text-green-800 flex items-center gap-2">
              <TrendingUp size={16} />
              Cobrado (Real)
            </CardTitle>
          </CardHeader>
          <CardContent>
            <p className="text-2xl font-bold mono text-green-700">
              {formatCurrency(totals.cobrosReales)}
            </p>
            <p className="text-xs text-green-600 mt-1">Total cobrado confirmado</p>
          </CardContent>
        </Card>

        {/* Real Expenses */}
        <Card className="border-red-200 bg-red-50">
          <CardHeader className="pb-2">
            <CardTitle className="text-sm text-red-800 flex items-center gap-2">
              <TrendingDown size={16} />
              Pagado (Real)
            </CardTitle>
          </CardHeader>
          <CardContent>
            <p className="text-2xl font-bold mono text-red-700">
              {formatCurrency(totals.pagosReales)}
            </p>
            <p className="text-xs text-red-600 mt-1">Total pagado confirmado</p>
          </CardContent>
        </Card>

        {/* Net Real Flow */}
        <Card className={`border-2 ${totals.cobrosReales - totals.pagosReales >= 0 ? 'border-green-400 bg-green-100' : 'border-red-400 bg-red-100'}`}>
          <CardHeader className="pb-2">
            <CardTitle className="text-sm text-gray-800 flex items-center gap-2">
              {totals.cobrosReales - totals.pagosReales >= 0 ? <TrendingUp size={16} /> : <TrendingDown size={16} />}
              Flujo Neto Real
            </CardTitle>
          </CardHeader>
          <CardContent>
            <p className={`text-2xl font-bold mono ${totals.cobrosReales - totals.pagosReales >= 0 ? 'text-green-700' : 'text-red-700'}`}>
              {totals.cobrosReales - totals.pagosReales >= 0 ? '+' : ''}{formatCurrency(totals.cobrosReales - totals.pagosReales)}
            </p>
            <p className="text-xs text-gray-600 mt-1">Cobrado - Pagado</p>
          </CardContent>
        </Card>

        {/* Projected */}
        <Card className="border-blue-200 bg-blue-50">
          <CardHeader className="pb-2">
            <CardTitle className="text-sm text-blue-800 flex items-center gap-2">
              <Calendar size={16} />
              Proyectado Pendiente
            </CardTitle>
          </CardHeader>
          <CardContent>
            <p className="text-xl font-bold mono text-blue-700">
              <span className="text-green-600">+{formatCurrency(totals.cobrosProyectados)}</span>
            </p>
            <p className="text-xl font-bold mono text-blue-700">
              <span className="text-red-600">-{formatCurrency(totals.pagosProyectados)}</span>
            </p>
            <p className="text-xs text-blue-600 mt-1">Por cobrar / Por pagar</p>
          </CardContent>
        </Card>
      </div>
    </div>
  );
};

export default Reports;
