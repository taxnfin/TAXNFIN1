import { useState, useEffect } from 'react';
import api from '@/api/axios';
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card';
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from '@/components/ui/table';
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from '@/components/ui/select';
import { toast } from 'sonner';
import { format, isBefore, startOfWeek, endOfWeek, isAfter } from 'date-fns';
import { es } from 'date-fns/locale';
import { TrendingUp, TrendingDown, Calendar, RefreshCw } from 'lucide-react';
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
  const [cashflowWeeks, setCashflowWeeks] = useState([]);
  const [payments, setPayments] = useState([]);
  const [reconciliations, setReconciliations] = useState([]);
  const [loading, setLoading] = useState(true);
  const [selectedCurrency, setSelectedCurrency] = useState('MXN');
  const [fxRates, setFxRates] = useState({ MXN: 1, USD: 17.50, EUR: 19.00, GBP: 22.00, JPY: 0.13, CHF: 20.00, CAD: 13.00, CNY: 2.40 });

  useEffect(() => {
    loadData();
  }, []);

  const loadData = async () => {
    setLoading(true);
    try {
      const [weeksRes, paymentsRes, reconRes, fxRes] = await Promise.all([
        api.get('/cashflow/weeks'),
        api.get('/payments'),
        api.get('/reconciliations'),
        api.get('/fx-rates/latest')
      ]);
      setCashflowWeeks(weeksRes.data);
      setPayments(paymentsRes.data || []);
      setReconciliations(reconRes.data || []);
      
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

  // Convert amount from MXN to selected currency
  const convertFromMXN = (amountMXN) => {
    if (selectedCurrency === 'MXN') return amountMXN;
    const rate = fxRates[selectedCurrency] || 1;
    return amountMXN / rate; // Divide to get target currency amount
  };

  // Format currency amount
  const formatCurrency = (amount) => {
    const converted = convertFromMXN(amount);
    const currency = CURRENCIES.find(c => c.code === selectedCurrency);
    const symbol = currency?.symbol || '$';
    return `${symbol}${converted.toLocaleString('es-MX', {minimumFractionDigits: 2, maximumFractionDigits: 2})}`;
  };

  // Determine if a week is in the past, current, or future
  const getWeekStatus = (weekData) => {
    const now = new Date();
    const weekStart = new Date(weekData.fecha_inicio);
    const weekEnd = new Date(weekData.fecha_fin);
    
    if (isAfter(now, weekEnd)) {
      return 'past'; // Week has ended - should show REAL data
    } else if (isBefore(now, weekStart)) {
      return 'future'; // Week hasn't started - should show PROJECTED data
    } else {
      return 'current'; // Current week - mix
    }
  };

  // Calculate real data from payments and reconciliations for a specific week
  const getRealDataForWeek = (weekData) => {
    const weekStart = new Date(weekData.fecha_inicio);
    const weekEnd = new Date(weekData.fecha_fin);
    
    // Filter payments within this week that are completed (real)
    const weekPayments = payments.filter(p => {
      if (!p.fecha_pago && !p.fecha_vencimiento) return false;
      const paymentDate = new Date(p.fecha_pago || p.fecha_vencimiento);
      return paymentDate >= weekStart && paymentDate <= weekEnd && 
             (p.estatus === 'completado' || p.es_real === true);
    });
    
    // Calculate totals from completed payments
    let ingresos = 0;
    let egresos = 0;
    
    weekPayments.forEach(p => {
      // Convert to MXN if needed
      let monto = p.monto || 0;
      if (p.moneda && p.moneda !== 'MXN') {
        const rate = fxRates[p.moneda] || 1;
        monto = monto * rate;
      }
      
      if (p.tipo === 'cobro') {
        ingresos += monto;
      } else {
        egresos += monto;
      }
    });
    
    return { ingresos, egresos };
  };

  // Process weeks with real vs projected separation
  const processedWeeks = cashflowWeeks.map(week => {
    const status = getWeekStatus(week);
    const realData = getRealDataForWeek(week);
    
    // For past weeks, use REAL data; for future weeks, use PROJECTED
    let displayIngresos, displayEgresos;
    let isReal = false;
    
    if (status === 'past') {
      // Past weeks: show real data (from payments/reconciliations)
      displayIngresos = realData.ingresos > 0 ? realData.ingresos : week.total_ingresos_reales;
      displayEgresos = realData.egresos > 0 ? realData.egresos : week.total_egresos_reales;
      isReal = true;
    } else if (status === 'future') {
      // Future weeks: show projected data
      displayIngresos = week.total_ingresos_proyectados;
      displayEgresos = week.total_egresos_proyectados;
      isReal = false;
    } else {
      // Current week: show mix (real what's happened + projected for rest)
      displayIngresos = realData.ingresos || week.total_ingresos_reales || week.total_ingresos_proyectados;
      displayEgresos = realData.egresos || week.total_egresos_reales || week.total_egresos_proyectados;
      isReal = realData.ingresos > 0 || realData.egresos > 0;
    }
    
    return {
      ...week,
      status,
      isReal,
      displayIngresos,
      displayEgresos,
      displayFlujoNeto: displayIngresos - displayEgresos,
      realIngresos: realData.ingresos,
      realEgresos: realData.egresos
    };
  });

  // Calculate running balance
  const weeksWithBalance = processedWeeks.reduce((acc, week, idx) => {
    const prevBalance = idx === 0 ? week.saldo_inicial : acc[idx - 1].saldoFinal;
    const saldoFinal = prevBalance + week.displayFlujoNeto;
    
    acc.push({
      ...week,
      saldoInicial: prevBalance,
      saldoFinal
    });
    
    return acc;
  }, []);

  // Calculate totals
  const totals = weeksWithBalance.reduce((acc, week) => {
    if (week.isReal) {
      acc.ingresosReales += week.displayIngresos;
      acc.egresosReales += week.displayEgresos;
    } else {
      acc.ingresosProyectados += week.displayIngresos;
      acc.egresosProyectados += week.displayEgresos;
    }
    return acc;
  }, { ingresosReales: 0, egresosReales: 0, ingresosProyectados: 0, egresosProyectados: 0 });

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
              <span className="w-3 h-3 rounded-full bg-green-500"></span> Real (semanas pasadas)
            </span>
            <span className="inline-flex items-center gap-2">
              <span className="w-3 h-3 rounded-full bg-gray-400"></span> Proyectado (semanas futuras)
            </span>
          </CardDescription>
        </CardHeader>
        <CardContent>
          <div className="overflow-x-auto">
            <Table className="data-table">
              <TableHeader>
                <TableRow>
                  <TableHead className="w-16">Semana</TableHead>
                  <TableHead className="w-28">Período</TableHead>
                  <TableHead className="w-20">Estado</TableHead>
                  <TableHead className="text-right">Saldo Inicial</TableHead>
                  <TableHead className="text-right">Ingresos</TableHead>
                  <TableHead className="text-right">Egresos</TableHead>
                  <TableHead className="text-right">Flujo Neto</TableHead>
                  <TableHead className="text-right">Saldo Final</TableHead>
                </TableRow>
              </TableHeader>
              <TableBody>
                {weeksWithBalance.map((week) => (
                  <TableRow 
                    key={week.id} 
                    data-testid={`cashflow-week-${week.numero_semana}`}
                    className={week.status === 'current' ? 'bg-yellow-50' : ''}
                  >
                    <TableCell className="mono font-semibold">S{week.numero_semana}</TableCell>
                    <TableCell className="text-sm">
                      {format(new Date(week.fecha_inicio), 'dd/MM')} - {format(new Date(week.fecha_fin), 'dd/MM')}
                    </TableCell>
                    <TableCell>
                      {week.status === 'past' && (
                        <span className="px-2 py-1 text-xs rounded-full bg-green-100 text-green-800">Real</span>
                      )}
                      {week.status === 'current' && (
                        <span className="px-2 py-1 text-xs rounded-full bg-yellow-100 text-yellow-800">Actual</span>
                      )}
                      {week.status === 'future' && (
                        <span className="px-2 py-1 text-xs rounded-full bg-gray-100 text-gray-600">Proy.</span>
                      )}
                    </TableCell>
                    <TableCell className="mono text-right">
                      {formatCurrency(week.saldoInicial)}
                    </TableCell>
                    <TableCell className={`mono text-right font-semibold ${week.isReal ? 'text-green-600' : 'text-gray-500'}`}>
                      {formatCurrency(week.displayIngresos)}
                    </TableCell>
                    <TableCell className={`mono text-right font-semibold ${week.isReal ? 'text-red-600' : 'text-gray-500'}`}>
                      {formatCurrency(week.displayEgresos)}
                    </TableCell>
                    <TableCell className={`mono text-right font-bold ${week.displayFlujoNeto >= 0 ? 'text-green-700' : 'text-red-700'}`}>
                      {week.displayFlujoNeto >= 0 ? '+' : ''}{formatCurrency(week.displayFlujoNeto)}
                    </TableCell>
                    <TableCell className="mono text-right font-bold">
                      {formatCurrency(week.saldoFinal)}
                    </TableCell>
                  </TableRow>
                ))}
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
              Ingresos Reales
            </CardTitle>
          </CardHeader>
          <CardContent>
            <p className="text-2xl font-bold mono text-green-700">
              {formatCurrency(totals.ingresosReales)}
            </p>
            <p className="text-xs text-green-600 mt-1">Semanas pasadas (confirmado)</p>
          </CardContent>
        </Card>

        {/* Real Expenses */}
        <Card className="border-red-200 bg-red-50">
          <CardHeader className="pb-2">
            <CardTitle className="text-sm text-red-800 flex items-center gap-2">
              <TrendingDown size={16} />
              Egresos Reales
            </CardTitle>
          </CardHeader>
          <CardContent>
            <p className="text-2xl font-bold mono text-red-700">
              {formatCurrency(totals.egresosReales)}
            </p>
            <p className="text-xs text-red-600 mt-1">Semanas pasadas (confirmado)</p>
          </CardContent>
        </Card>

        {/* Projected Income */}
        <Card className="border-blue-200 bg-blue-50">
          <CardHeader className="pb-2">
            <CardTitle className="text-sm text-blue-800 flex items-center gap-2">
              <TrendingUp size={16} />
              Ingresos Proyectados
            </CardTitle>
          </CardHeader>
          <CardContent>
            <p className="text-2xl font-bold mono text-blue-700">
              {formatCurrency(totals.ingresosProyectados)}
            </p>
            <p className="text-xs text-blue-600 mt-1">Semanas futuras (estimado)</p>
          </CardContent>
        </Card>

        {/* Projected Expenses */}
        <Card className="border-purple-200 bg-purple-50">
          <CardHeader className="pb-2">
            <CardTitle className="text-sm text-purple-800 flex items-center gap-2">
              <TrendingDown size={16} />
              Egresos Proyectados
            </CardTitle>
          </CardHeader>
          <CardContent>
            <p className="text-2xl font-bold mono text-purple-700">
              {formatCurrency(totals.egresosProyectados)}
            </p>
            <p className="text-xs text-purple-600 mt-1">Semanas futuras (estimado)</p>
          </CardContent>
        </Card>
      </div>

      {/* Variance Analysis */}
      <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
        <Card className="border-[#E2E8F0]">
          <CardHeader>
            <CardTitle>Varianza Real vs Proyectado</CardTitle>
            <CardDescription>Comparativo por semana (solo semanas pasadas)</CardDescription>
          </CardHeader>
          <CardContent>
            <div className="space-y-3">
              {weeksWithBalance.filter(w => w.status === 'past').slice(0, 5).map((week) => {
                const proyectadoIngresos = week.total_ingresos_proyectados || 0;
                const proyectadoEgresos = week.total_egresos_proyectados || 0;
                const proyectadoNeto = proyectadoIngresos - proyectadoEgresos;
                const variacion = week.displayFlujoNeto - proyectadoNeto;
                const variacionPct = proyectadoNeto !== 0 ? ((variacion / Math.abs(proyectadoNeto)) * 100) : 0;
                
                return (
                  <div key={week.id} className="flex justify-between items-center p-3 bg-[#F8FAFC] rounded">
                    <div>
                      <p className="text-sm font-semibold">Semana {week.numero_semana}</p>
                      <p className="text-xs text-[#64748B]">
                        {format(new Date(week.fecha_inicio), 'dd/MM')} - {format(new Date(week.fecha_fin), 'dd/MM')}
                      </p>
                    </div>
                    <div className="text-right">
                      <p className={`mono font-bold ${variacion >= 0 ? 'text-[#10B981]' : 'text-[#EF4444]'}`}>
                        {variacion >= 0 ? '+' : ''}{formatCurrency(variacion)}
                      </p>
                      <p className="text-xs text-[#94A3B8]">
                        {variacionPct >= 0 ? '+' : ''}{variacionPct.toFixed(1)}% variación
                      </p>
                    </div>
                  </div>
                );
              })}
              {weeksWithBalance.filter(w => w.status === 'past').length === 0 && (
                <p className="text-center text-gray-500 py-4">No hay semanas pasadas para comparar</p>
              )}
            </div>
          </CardContent>
        </Card>

        <Card className="border-[#E2E8F0]">
          <CardHeader>
            <CardTitle>Resumen General</CardTitle>
            <CardDescription>Métricas de desempeño</CardDescription>
          </CardHeader>
          <CardContent>
            <div className="space-y-4">
              <div className="p-4 bg-[#F8FAFC] rounded">
                <p className="text-sm text-[#64748B]">Flujo Neto Real (confirmado)</p>
                <p className={`text-2xl font-bold mono ${totals.ingresosReales - totals.egresosReales >= 0 ? 'text-green-600' : 'text-red-600'}`}>
                  {formatCurrency(totals.ingresosReales - totals.egresosReales)}
                </p>
              </div>
              <div className="p-4 bg-[#F8FAFC] rounded">
                <p className="text-sm text-[#64748B]">Flujo Neto Proyectado (estimado)</p>
                <p className={`text-2xl font-bold mono ${totals.ingresosProyectados - totals.egresosProyectados >= 0 ? 'text-blue-600' : 'text-purple-600'}`}>
                  {formatCurrency(totals.ingresosProyectados - totals.egresosProyectados)}
                </p>
              </div>
              <div className="p-4 bg-gradient-to-r from-green-50 to-blue-50 rounded border border-green-200">
                <p className="text-sm text-[#64748B]">Flujo Total (Real + Proyectado)</p>
                <p className={`text-2xl font-bold mono ${
                  (totals.ingresosReales + totals.ingresosProyectados) - (totals.egresosReales + totals.egresosProyectados) >= 0 
                    ? 'text-[#0F172A]' 
                    : 'text-red-600'
                }`}>
                  {formatCurrency(
                    (totals.ingresosReales + totals.ingresosProyectados) - 
                    (totals.egresosReales + totals.egresosProyectados)
                  )}
                </p>
              </div>
            </div>
          </CardContent>
        </Card>
      </div>
    </div>
  );
};

export default Reports;
