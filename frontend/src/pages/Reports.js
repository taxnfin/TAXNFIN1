import { useState, useEffect, useMemo } from 'react';
import api from '@/api/axios';
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card';
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from '@/components/ui/table';
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from '@/components/ui/select';
import { toast } from 'sonner';
import { format, startOfWeek, addWeeks, addDays, isBefore, isAfter, parseISO } from 'date-fns';
import { es } from 'date-fns/locale';
import { TrendingUp, TrendingDown, Calendar, RefreshCw, ArrowUpRight, ArrowDownRight } from 'lucide-react';
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
  const [fxRates, setFxRates] = useState({ MXN: 1, USD: 17.599, EUR: 20.4852, GBP: 22.00, JPY: 0.13, CHF: 20.00, CAD: 13.00, CNY: 2.40 });
  const weekStartDay = 1; // Monday = 1

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

  // Convert amount to MXN
  const convertToMXN = (amount, currency) => {
    if (!amount) return 0;
    if (currency === 'MXN' || !currency) return amount;
    const rate = fxRates[currency] || 17.599;
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
    const diff = d.getDate() - day + (day === 0 ? -6 : 1); // Adjust when day is Sunday
    return new Date(d.setDate(diff));
  };

  // Generate weeks based on actual payment data
  const weeksData = useMemo(() => {
    const today = new Date();
    const currentMonday = getMonday(today);
    
    // Find the earliest payment date to determine start
    let earliestDate = currentMonday;
    payments.forEach(p => {
      if (p.estatus !== 'completado') return;
      const fecha = p.fecha_pago;
      if (fecha) {
        const d = new Date(fecha);
        if (d < earliestDate) earliestDate = d;
      }
    });
    
    // Start from 4 weeks before current week or earliest payment
    const fourWeeksAgo = addWeeks(currentMonday, -4);
    const startMonday = getMonday(earliestDate < fourWeeksAgo ? fourWeeksAgo : earliestDate);
    
    // Generate 17 weeks (4 past + current + 12 future)
    const weeks = [];
    for (let i = 0; i < 17; i++) {
      const weekStart = addWeeks(startMonday, i);
      const weekEnd = addDays(weekStart, 6); // Sunday
      const weekEndForComparison = addWeeks(weekStart, 1); // Next Monday for comparison
      const isPast = weekEndForComparison <= today;
      const isCurrent = weekStart <= today && today < weekEndForComparison;
      
      // Calculate week number relative to current week
      const weeksDiff = Math.round((weekStart.getTime() - currentMonday.getTime()) / (7 * 24 * 60 * 60 * 1000));
      let label;
      if (weeksDiff < 0) {
        label = `S${weeksDiff}`; // S-3, S-2, S-1
      } else if (weeksDiff === 0) {
        label = 'S0'; // Current week
      } else {
        label = `S${weeksDiff}`; // S1, S2, S3...
      }
      
      weeks.push({
        weekNum: i,
        label,
        weekStart,
        weekEnd,
        weekEndForComparison,
        isPast,
        isCurrent,
        dateRange: `${format(weekStart, 'dd/MM')} - ${format(weekEnd, 'dd/MM')}`,
        cobrosReales: 0,
        pagosReales: 0,
        cobrosProyectados: 0,
        pagosProyectados: 0
      });
    }
    
    // Track processed bank transactions to avoid duplicates
    const processedBankTxns = new Set();
    
    // Process REAL payments (completed)
    payments.forEach(payment => {
      if (payment.estatus !== 'completado') return;
      
      // Skip duplicates by bank_transaction_id
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
      
      // Find the week this payment belongs to
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
    
    // Process PROJECTED data from pending CFDIs (for future weeks only)
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
      
      // Estimate payment date (30 days from emission if no vencimiento)
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
      // Only add to future weeks
      if (weeks[weekIdx].isPast && !weeks[weekIdx].isCurrent) return;
      
      if (cfdi.tipo_cfdi === 'ingreso') {
        weeks[weekIdx].cobrosProyectados += pendienteMXN;
      } else if (cfdi.tipo_cfdi === 'egreso') {
        weeks[weekIdx].pagosProyectados += pendienteMXN;
      }
    });
    
    // Filter out weeks with no data that are too far in the past or future
    const firstWeekWithData = weeks.findIndex(w => 
      w.cobrosReales > 0 || w.pagosReales > 0 || w.isCurrent
    );
    const lastWeekWithData = weeks.findLastIndex(w => 
      w.cobrosReales > 0 || w.pagosReales > 0 || w.cobrosProyectados > 0 || w.pagosProyectados > 0 || w.isCurrent
    );
    
    // Keep from first data week to at least 13 weeks from current
    const start = Math.max(0, firstWeekWithData);
    const end = Math.max(lastWeekWithData + 1, weeks.findIndex(w => w.isCurrent) + 13);
    
    return weeks.slice(start, Math.min(end, weeks.length));
  }, [payments, cfdis, fxRates]);

  // Calculate totals
  const totals = useMemo(() => {
    return weeksData.reduce((acc, week) => {
      acc.cobrosReales += week.cobrosReales;
      acc.pagosReales += week.pagosReales;
      acc.cobrosProyectados += week.cobrosProyectados;
      acc.pagosProyectados += week.pagosProyectados;
      return acc;
    }, { cobrosReales: 0, pagosReales: 0, cobrosProyectados: 0, pagosProyectados: 0 });
  }, [weeksData]);

  if (loading) return <div className="p-8">Cargando...</div>;

  return (
    <div className="p-8 space-y-6" data-testid="reports-page">
      {/* Header */}
      <div className="flex justify-between items-start">
        <div>
          <h1 className="text-4xl font-bold text-[#0F172A] mb-2" style={{fontFamily: 'Manrope'}}>Reportes</h1>
          <p className="text-[#64748B]">Flujo de Efectivo Real vs Proyectado (Semanas = Lunes a Domingo)</p>
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
            Flujo de Efectivo Semanal
          </CardTitle>
          <CardDescription>
            <span className="inline-flex items-center gap-1 mr-4">
              <span className="w-2 h-2 rounded-full bg-green-500"></span> Cobrado
            </span>
            <span className="inline-flex items-center gap-1 mr-4">
              <span className="w-2 h-2 rounded-full bg-red-500"></span> Pagado
            </span>
            <span className="inline-flex items-center gap-1">
              <span className="w-2 h-2 rounded-full bg-gray-400"></span> Proyectado
            </span>
          </CardDescription>
        </CardHeader>
        <CardContent>
          <div className="overflow-x-auto">
            <Table className="text-sm">
              <TableHeader>
                <TableRow>
                  <TableHead className="w-16 font-bold">Sem</TableHead>
                  <TableHead className="w-28">Período</TableHead>
                  <TableHead className="w-16 text-center">Tipo</TableHead>
                  <TableHead className="text-right">Cobros Real</TableHead>
                  <TableHead className="text-right">Pagos Real</TableHead>
                  <TableHead className="text-right bg-gray-50">Cobros Proy.</TableHead>
                  <TableHead className="text-right bg-gray-50">Pagos Proy.</TableHead>
                  <TableHead className="text-right font-bold">Flujo Neto</TableHead>
                </TableRow>
              </TableHeader>
              <TableBody>
                {weeksData.map((week) => {
                  const flujoNeto = (week.cobrosReales + week.cobrosProyectados) - (week.pagosReales + week.pagosProyectados);
                  
                  return (
                    <TableRow 
                      key={week.label} 
                      className={week.isCurrent ? 'bg-blue-50' : week.isPast ? '' : 'bg-gray-50/50'}
                    >
                      <TableCell className="mono font-bold">{week.label}</TableCell>
                      <TableCell className="text-xs">{week.dateRange}</TableCell>
                      <TableCell className="text-center">
                        {week.isPast && !week.isCurrent && (
                          <span className="px-1.5 py-0.5 text-xs rounded bg-green-100 text-green-800">Real</span>
                        )}
                        {week.isCurrent && (
                          <span className="px-1.5 py-0.5 text-xs rounded bg-blue-100 text-blue-800">Actual</span>
                        )}
                        {!week.isPast && !week.isCurrent && (
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
                      <TableCell className={`mono text-right font-bold ${flujoNeto >= 0 ? 'text-green-700' : 'text-red-700'}`}>
                        {flujoNeto !== 0 ? (
                          <>{flujoNeto >= 0 ? '+' : ''}{formatCurrency(flujoNeto)}</>
                        ) : '-'}
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
                  <TableCell className={`mono text-right font-bold ${(totals.cobrosReales - totals.pagosReales) >= 0 ? 'text-green-400' : 'text-red-400'}`}>
                    {formatCurrency(totals.cobrosReales - totals.pagosReales)}
                  </TableCell>
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

        <Card className={`border-2 ${(totals.cobrosReales - totals.pagosReales) >= 0 ? 'border-green-400 bg-green-100' : 'border-red-400 bg-red-100'}`}>
          <CardHeader className="pb-2">
            <CardTitle className="text-sm text-gray-800">Flujo Neto Real</CardTitle>
          </CardHeader>
          <CardContent>
            <p className={`text-2xl font-bold mono ${(totals.cobrosReales - totals.pagosReales) >= 0 ? 'text-green-700' : 'text-red-700'}`}>
              {(totals.cobrosReales - totals.pagosReales) >= 0 ? '+' : ''}{formatCurrency(totals.cobrosReales - totals.pagosReales)}
            </p>
          </CardContent>
        </Card>

        <Card className="border-blue-200 bg-blue-50">
          <CardHeader className="pb-2">
            <CardTitle className="text-sm text-blue-800">Por Cobrar/Pagar (Proy.)</CardTitle>
          </CardHeader>
          <CardContent>
            <p className="text-lg font-bold mono text-green-600">+{formatCurrency(totals.cobrosProyectados)}</p>
            <p className="text-lg font-bold mono text-red-600">-{formatCurrency(totals.pagosProyectados)}</p>
          </CardContent>
        </Card>
      </div>
    </div>
  );
};

export default Reports;
