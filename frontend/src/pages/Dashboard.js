import { useState, useEffect } from 'react';
import api from '@/api/axios';
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card';
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from '@/components/ui/select';
import { Button } from '@/components/ui/button';
import { Input } from '@/components/ui/input';
import { 
  LineChart, Line, XAxis, YAxis, CartesianGrid, Tooltip, ResponsiveContainer, 
  BarChart, Bar, Area, AreaChart, ComposedChart, Legend, ReferenceLine
} from 'recharts';
import { 
  TrendingUp, TrendingDown, DollarSign, FileText, CheckCircle2, ArrowRightLeft, 
  Wallet, Building2, AlertTriangle, AlertCircle, PiggyBank, Layers, RefreshCw,
  Filter, ArrowUpRight, ArrowDownRight, Minus, Calendar
} from 'lucide-react';
import { toast } from 'sonner';

const CURRENCIES = [
  { value: 'MXN', label: 'MXN - Peso Mexicano', symbol: '$' },
  { value: 'USD', label: 'USD - Dólar USA', symbol: '$' },
  { value: 'EUR', label: 'EUR - Euro', symbol: '€' },
  { value: 'GBP', label: 'GBP - Libra Esterlina', symbol: '£' },
  { value: 'JPY', label: 'JPY - Yen Japonés', symbol: '¥' },
  { value: 'CHF', label: 'CHF - Franco Suizo', symbol: 'Fr' },
  { value: 'CAD', label: 'CAD - Dólar Canadiense', symbol: 'C$' },
  { value: 'CNY', label: 'CNY - Yuan Chino', symbol: '¥' }
];

const Dashboard = () => {
  const [dashboardData, setDashboardData] = useState(null);
  const [loading, setLoading] = useState(true);
  const [viewCurrency, setViewCurrency] = useState('MXN');
  const [selectedAccount, setSelectedAccount] = useState('all');
  const [bankAccounts, setBankAccounts] = useState([]);
  const [dateFrom, setDateFrom] = useState('');
  const [dateTo, setDateTo] = useState('');
  const [syncingRates, setSyncingRates] = useState(false);
  const [lastRateSync, setLastRateSync] = useState(null);
  const [schedulerStatus, setSchedulerStatus] = useState(null);
  const [fxAlerts, setFxAlerts] = useState(null);

  useEffect(() => {
    loadBankAccounts();
    loadSchedulerStatus();
    loadFxAlerts();
    // Set default date range (last 13 weeks)
    const today = new Date();
    const thirteenWeeksAgo = new Date(today);
    thirteenWeeksAgo.setDate(today.getDate() - 91);
    setDateFrom(thirteenWeeksAgo.toISOString().split('T')[0]);
    setDateTo(today.toISOString().split('T')[0]);
  }, []);

  useEffect(() => {
    if (dateFrom && dateTo) {
      loadDashboardData();
    }
  }, [viewCurrency, selectedAccount, dateFrom, dateTo]);

  const loadBankAccounts = async () => {
    try {
      const response = await api.get('/bank-accounts');
      setBankAccounts(response.data);
    } catch (error) {
      console.error('Error loading bank accounts');
    }
  };

  const loadSchedulerStatus = async () => {
    try {
      const response = await api.get('/fx-rates/scheduler-status');
      setSchedulerStatus(response.data);
    } catch (error) {
      console.error('Error loading scheduler status');
    }
  };

  const loadFxAlerts = async () => {
    try {
      const response = await api.get('/fx-rates/alerts');
      setFxAlerts(response.data);
    } catch (error) {
      console.error('Error loading FX alerts');
    }
  };

  const syncFxRates = async () => {
    setSyncingRates(true);
    try {
      const response = await api.post('/fx-rates/sync');
      setLastRateSync(response.data);
      toast.success(`${response.data.message} desde Banxico y Open Exchange`);
      // Reload dashboard with new rates
      loadDashboardData();
      loadSchedulerStatus();
      loadFxAlerts();
    } catch (error) {
      toast.error('Error sincronizando tasas de cambio');
    } finally {
      setSyncingRates(false);
    }
  };

  const loadDashboardData = async () => {
    setLoading(true);
    try {
      // Use the new endpoint that generates data from payments
      let url = `/reports/dashboard-from-payments?moneda_vista=${viewCurrency}`;
      if (selectedAccount && selectedAccount !== 'all') {
        url += `&bank_account_id=${selectedAccount}`;
      }
      const response = await api.get(url);
      setDashboardData(response.data);
    } catch (error) {
      toast.error('Error cargando dashboard');
    } finally {
      setLoading(false);
    }
  };

  const setQuickDateRange = (range) => {
    const today = new Date();
    let from = new Date(today);
    
    switch(range) {
      case '1w':
        from.setDate(today.getDate() - 7);
        break;
      case '1m':
        from.setMonth(today.getMonth() - 1);
        break;
      case '3m':
        from.setMonth(today.getMonth() - 3);
        break;
      case '6m':
        from.setMonth(today.getMonth() - 6);
        break;
      case '1y':
        from.setFullYear(today.getFullYear() - 1);
        break;
      case '13w':
      default:
        from.setDate(today.getDate() - 91);
        break;
    }
    
    setDateFrom(from.toISOString().split('T')[0]);
    setDateTo(today.toISOString().split('T')[0]);
  };

  const formatCurrency = (amount) => {
    const curr = CURRENCIES.find(c => c.value === viewCurrency) || CURRENCIES[0];
    return `${curr.symbol}${amount.toLocaleString('es-MX', {minimumFractionDigits: 2, maximumFractionDigits: 2})}`;
  };

  if (loading && !dashboardData) {
    return <div className="p-8">Cargando dashboard...</div>;
  }

  // Map weeks data from new endpoint - use display values for selected currency
  const chartData = (dashboardData?.weeks || []).map((week, idx) => ({
    semana: week.week_label || `S${idx + 1}`,
    date_label: week.date_label || '',
    ingresos: week.ingresos_display ?? week.ingresos ?? 0,
    egresos: week.egresos_display ?? week.egresos ?? 0,
    flujo_neto: week.flujo_neto_display ?? week.flujo_neto ?? 0,
    saldo_inicial: week.saldo_inicial_display ?? week.saldo_inicial ?? 0,
    saldo_final: week.saldo_final_display ?? week.saldo_final ?? 0,
    venta_usd: week.venta_usd || 0,
    compra_usd: week.compra_usd || 0,
    num_payments: week.num_payments || 0,
    varianza: week.varianza_display ?? week.varianza ?? 0,
    varianza_pct: week.varianza_pct || 0,
    is_past: week.is_past,
    is_current: week.is_current
  }));

  const kpis = dashboardData?.kpis || {};
  const saldoInicial = dashboardData?.saldo_bancos || 0;
  const saldoFinalProyectado = dashboardData?.saldo_proyectado || 0;
  const burnRate = dashboardData?.burn_rate || 0;
  const runwayWeeks = dashboardData?.runway_weeks;
  const criticalWeek = dashboardData?.critical_week;
  const cobranzaVsPagos = dashboardData?.cobranza_vs_pagos || 100;
  const totalIngresos = dashboardData?.total_ingresos || 0;
  const totalEgresos = dashboardData?.total_egresos || 0;
  
  // Calculate trend from weekly data
  const recentWeeks = chartData.filter(w => w.is_past || w.is_current).slice(-4);
  const trend = recentWeeks.length >= 2 ? {
    direction: recentWeeks[recentWeeks.length - 1].flujo_neto > recentWeeks[0].flujo_neto ? 'up' : 
               recentWeeks[recentWeeks.length - 1].flujo_neto < recentWeeks[0].flujo_neto ? 'down' : 'stable',
    avg_flow_4w: recentWeeks.reduce((sum, w) => sum + w.flujo_neto, 0) / recentWeeks.length
  } : { direction: 'stable', avg_flow_4w: 0 };
  
  const risks = {
    liquidez_critica: saldoFinalProyectado < 50000,
    tendencia_negativa: trend.direction === 'down' && trend.avg_flow_4w < 0,
    semanas_con_deficit: chartData.filter(w => w.saldo_final < 0).length
  };
  const accounts = dashboardData?.bank_accounts || [];
  
  // Build cashPool from endpoint data
  const cashPool = dashboardData?.cash_pool || {};

  const TrendIcon = trend.direction === 'up' ? ArrowUpRight : trend.direction === 'down' ? ArrowDownRight : Minus;
  const trendColor = trend.direction === 'up' ? 'text-green-600' : trend.direction === 'down' ? 'text-red-600' : 'text-gray-500';

  const hasRiskAlerts = risks.liquidez_critica || risks.tendencia_negativa || risks.semanas_con_deficit > 0;
  const hasFxAlerts = fxAlerts?.has_alerts;

  return (
    <div className="p-6 space-y-6 bg-[#F8FAFC] min-h-screen" data-testid="dashboard-page">
      {/* FX Rate Alerts Banner */}
      {hasFxAlerts && (
        <div className={`rounded-lg border-l-4 p-4 ${fxAlerts.critical_count > 0 ? 'bg-red-50 border-red-500' : 'bg-amber-50 border-amber-500'}`} data-testid="fx-alerts-banner">
          <div className="flex items-start gap-3">
            <AlertTriangle className={`w-5 h-5 mt-0.5 ${fxAlerts.critical_count > 0 ? 'text-red-600' : 'text-amber-600'}`} />
            <div className="flex-1">
              <h3 className={`font-semibold ${fxAlerts.critical_count > 0 ? 'text-red-800' : 'text-amber-800'}`}>
                {fxAlerts.critical_count > 0 ? '⚠️ Alerta Crítica de Tipo de Cambio' : '📊 Variación en Tipos de Cambio'}
              </h3>
              <div className="mt-2 space-y-1">
                {fxAlerts.alerts.map((alert, idx) => (
                  <div key={idx} className={`text-sm flex items-center gap-2 ${alert.type === 'critical' ? 'text-red-700 font-medium' : 'text-amber-700'}`}>
                    {alert.direction === 'subió' ? (
                      <TrendingUp size={14} className="text-red-500" />
                    ) : (
                      <TrendingDown size={14} className="text-green-500" />
                    )}
                    <span>{alert.message}</span>
                    <span className="text-xs text-gray-500">({alert.source})</span>
                  </div>
                ))}
              </div>
              <p className="text-xs text-gray-500 mt-2">
                Umbral de alerta: variación mayor al {fxAlerts.threshold_percent}% respecto al día anterior
              </p>
            </div>
            <Button 
              variant="ghost" 
              size="sm" 
              onClick={() => setFxAlerts(null)}
              className="text-gray-400 hover:text-gray-600"
            >
              ✕
            </Button>
          </div>
        </div>
      )}

      {/* Header */}
      <div className="flex flex-col gap-4">
        <div className="flex flex-col md:flex-row md:items-center md:justify-between gap-4">
          <div>
            <h1 className="text-3xl font-bold text-[#0F172A]" style={{fontFamily: 'Manrope'}}>Dashboard Ejecutivo</h1>
            <p className="text-[#64748B] text-sm">Flujo de efectivo • 13 semanas rolling</p>
          </div>
          <div className="flex items-center gap-2 self-start md:self-auto">
            <Button 
              variant="outline" 
              size="sm" 
              onClick={syncFxRates} 
              disabled={syncingRates}
              className="gap-2 text-blue-600 border-blue-200 hover:bg-blue-50"
              data-testid="sync-rates-btn"
            >
              <DollarSign size={14} className={syncingRates ? 'animate-spin' : ''} />
              {syncingRates ? 'Sincronizando...' : 'Actualizar Tasas'}
            </Button>
            <Button variant="outline" size="sm" onClick={loadDashboardData} className="gap-2">
              <RefreshCw size={14} />
              Actualizar
            </Button>
          </div>
        </div>
        
        {/* Scheduler status and rate sync info */}
        <div className="flex flex-wrap items-center gap-3">
          {/* Auto-sync scheduler status */}
          {schedulerStatus?.scheduler?.running && (
            <div className="flex items-center gap-2 text-xs text-blue-700 bg-blue-50 rounded-md px-3 py-1.5">
              <div className="w-2 h-2 bg-blue-500 rounded-full animate-pulse" />
              <span className="font-medium">Auto-sync activo</span>
              <span className="text-blue-500">|</span>
              <span>Próxima: {schedulerStatus.scheduler.jobs?.[0]?.next_run_formatted?.split(' ').slice(1, 3).join(' ')}</span>
            </div>
          )}
          
          {/* Rate sync info */}
          {lastRateSync && (
            <div className="flex items-center gap-2 text-xs text-green-700 bg-green-50 rounded-md px-3 py-1.5">
              <CheckCircle2 size={12} />
              Tasas: {lastRateSync.rates?.map(r => `${r.moneda}: ${r.tasa_mxn.toFixed(2)}`).join(' | ')}
            </div>
          )}
        </div>
        
        {/* Filters Row */}
        <div className="flex flex-wrap items-center gap-3 p-3 bg-white rounded-lg border shadow-sm">
          <span className="text-sm font-medium text-[#64748B] flex items-center gap-1">
            <Filter size={14} /> Filtros:
          </span>
          
          {/* Currency Selector */}
          <div className="flex items-center gap-2 bg-[#F8FAFC] rounded-md px-3 py-1.5 border">
            <DollarSign size={14} className="text-[#64748B]" />
            <Select value={viewCurrency} onValueChange={setViewCurrency}>
              <SelectTrigger className="w-44 border-0 bg-transparent p-0 h-7 focus:ring-0" data-testid="currency-selector">
                <SelectValue />
              </SelectTrigger>
              <SelectContent>
                {CURRENCIES.map(c => (
                  <SelectItem key={c.value} value={c.value}>{c.label}</SelectItem>
                ))}
              </SelectContent>
            </Select>
          </div>

          {/* Account Filter */}
          <div className="flex items-center gap-2 bg-[#F8FAFC] rounded-md px-3 py-1.5 border">
            <Building2 size={14} className="text-[#64748B]" />
            <Select value={selectedAccount} onValueChange={setSelectedAccount}>
              <SelectTrigger className="w-40 border-0 bg-transparent p-0 h-7 focus:ring-0" data-testid="account-filter">
                <SelectValue placeholder="Todas las cuentas" />
              </SelectTrigger>
              <SelectContent>
                <SelectItem value="all">Todas las cuentas</SelectItem>
                {bankAccounts.map(acc => (
                  <SelectItem key={acc.id} value={acc.id}>{acc.nombre}</SelectItem>
                ))}
              </SelectContent>
            </Select>
          </div>

          {/* Date Range Filter */}
          <div className="flex items-center gap-2 bg-[#F8FAFC] rounded-md px-3 py-1.5 border">
            <Calendar size={14} className="text-[#64748B]" />
            <Input 
              type="date" 
              value={dateFrom} 
              onChange={(e) => setDateFrom(e.target.value)}
              className="w-32 h-7 border-0 bg-transparent p-0 text-sm"
              data-testid="date-from"
            />
            <span className="text-[#64748B] text-sm">-</span>
            <Input 
              type="date" 
              value={dateTo} 
              onChange={(e) => setDateTo(e.target.value)}
              className="w-32 h-7 border-0 bg-transparent p-0 text-sm"
              data-testid="date-to"
            />
          </div>

          {/* Quick Date Buttons */}
          <div className="flex items-center gap-1">
            <Button variant="ghost" size="sm" onClick={() => setQuickDateRange('1w')} className="h-7 px-2 text-xs">1S</Button>
            <Button variant="ghost" size="sm" onClick={() => setQuickDateRange('1m')} className="h-7 px-2 text-xs">1M</Button>
            <Button variant="ghost" size="sm" onClick={() => setQuickDateRange('3m')} className="h-7 px-2 text-xs">3M</Button>
            <Button variant="ghost" size="sm" onClick={() => setQuickDateRange('6m')} className="h-7 px-2 text-xs">6M</Button>
            <Button variant="ghost" size="sm" onClick={() => setQuickDateRange('1y')} className="h-7 px-2 text-xs">1A</Button>
            <Button variant="ghost" size="sm" onClick={() => setQuickDateRange('13w')} className="h-7 px-2 text-xs bg-[#E0F2FE]">13S</Button>
          </div>
        </div>
      </div>

      {/* Risk Alerts Banner */}
      {hasRiskAlerts && (
        <Card className="border-amber-300 bg-amber-50">
          <CardContent className="py-3">
            <div className="flex items-center gap-3">
              <AlertTriangle className="h-5 w-5 text-amber-600" />
              <div className="flex-1 flex flex-wrap gap-4 text-sm">
                {risks.liquidez_critica && (
                  <span className="flex items-center gap-1 text-red-700">
                    <AlertCircle size={14} /> Liquidez crítica proyectada
                  </span>
                )}
                {risks.tendencia_negativa && (
                  <span className="flex items-center gap-1 text-red-700">
                    <TrendingDown size={14} /> Tendencia negativa
                  </span>
                )}
                {risks.saldos_ociosos > 0 && (
                  <span className="flex items-center gap-1 text-amber-700">
                    <PiggyBank size={14} /> {risks.saldos_ociosos} cuenta(s) con saldo ocioso
                  </span>
                )}
                {risks.cuentas_bajo_saldo > 0 && (
                  <span className="flex items-center gap-1 text-amber-700">
                    <AlertTriangle size={14} /> {risks.cuentas_bajo_saldo} cuenta(s) con bajo saldo
                  </span>
                )}
                {risks.semanas_con_deficit > 0 && (
                  <span className="flex items-center gap-1 text-amber-700">
                    <AlertCircle size={14} /> {risks.semanas_con_deficit} semana(s) con déficit
                  </span>
                )}
              </div>
            </div>
          </CardContent>
        </Card>
      )}

      {/* Main KPIs - Saldos */}
      <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
        <Card className="border-l-4 border-l-green-500 shadow-sm">
          <CardHeader className="pb-2">
            <CardTitle className="text-sm font-medium text-[#64748B] flex items-center justify-between">
              <span>Saldo Inicial</span>
              <Building2 className="h-4 w-4" />
            </CardTitle>
          </CardHeader>
          <CardContent>
            <div className="text-2xl font-bold mono text-[#0F172A]">
              {formatCurrency(saldoInicial)}
            </div>
            <p className="text-xs text-[#94A3B8] mt-1">Consolidado en {viewCurrency}</p>
          </CardContent>
        </Card>

        <Card className="border-l-4 border-l-blue-500 shadow-sm">
          <CardHeader className="pb-2">
            <CardTitle className="text-sm font-medium text-[#64748B] flex items-center justify-between">
              <span>Saldo Final Proyectado (S13)</span>
              <Wallet className="h-4 w-4" />
            </CardTitle>
          </CardHeader>
          <CardContent>
            <div className={`text-2xl font-bold mono ${saldoFinalProyectado >= 0 ? 'text-[#0F172A]' : 'text-red-600'}`}>
              {formatCurrency(saldoFinalProyectado)}
            </div>
            <div className="flex items-center gap-1 mt-1">
              <TrendIcon size={14} className={trendColor} />
              <span className={`text-xs ${trendColor}`}>
                Tendencia {trend.direction === 'up' ? 'positiva' : trend.direction === 'down' ? 'negativa' : 'estable'}
              </span>
            </div>
          </CardContent>
        </Card>

        <Card className="border-l-4 border-l-purple-500 shadow-sm">
          <CardHeader className="pb-2">
            <CardTitle className="text-sm font-medium text-[#64748B] flex items-center justify-between">
              <span>Flujo Promedio (4 sem)</span>
              <TrendingUp className="h-4 w-4" />
            </CardTitle>
          </CardHeader>
          <CardContent>
            <div className={`text-2xl font-bold mono ${trend.avg_flow_4w >= 0 ? 'text-green-600' : 'text-red-600'}`}>
              {trend.avg_flow_4w >= 0 ? '+' : ''}{formatCurrency(trend.avg_flow_4w)}
            </div>
            <p className="text-xs text-[#94A3B8] mt-1">por semana</p>
          </CardContent>
        </Card>
      </div>

      {/* Charts Row */}
      <div className="grid grid-cols-1 lg:grid-cols-2 gap-4">
        {/* Main Cashflow Chart */}
        <Card className="shadow-sm">
          <CardHeader className="pb-2">
            <CardTitle className="text-sm font-medium">Flujo de Efectivo - 13 Semanas</CardTitle>
            <CardDescription>Ingresos, egresos y saldo acumulado</CardDescription>
          </CardHeader>
          <CardContent>
            <div className="h-[280px]">
              <ResponsiveContainer width="100%" height="100%">
                <ComposedChart data={chartData}>
                  <CartesianGrid strokeDasharray="3 3" stroke="#E2E8F0" />
                  <XAxis dataKey="semana" tick={{fontSize: 11}} stroke="#94A3B8" />
                  <YAxis tick={{fontSize: 11}} stroke="#94A3B8" tickFormatter={(v) => `${(v/1000).toFixed(0)}k`} />
                  <Tooltip 
                    formatter={(value, name) => [formatCurrency(value), name]}
                    contentStyle={{backgroundColor: '#fff', border: '1px solid #E2E8F0', borderRadius: '8px'}}
                  />
                  <Legend />
                  <Bar dataKey="ingresos" name="Ingresos" fill="#10B981" radius={[2, 2, 0, 0]} />
                  <Bar dataKey="egresos" name="Egresos" fill="#EF4444" radius={[2, 2, 0, 0]} />
                  <Line type="monotone" dataKey="saldo_final" name="Saldo" stroke="#6366F1" strokeWidth={2} dot={{ fill: '#6366F1', r: 3 }} />
                  <ReferenceLine y={0} stroke="#94A3B8" strokeDasharray="3 3" />
                </ComposedChart>
              </ResponsiveContainer>
            </div>
          </CardContent>
        </Card>

        {/* Variance Chart */}
        <Card className="shadow-sm">
          <CardHeader className="pb-2">
            <CardTitle className="text-sm font-medium">Varianza Semanal</CardTitle>
            <CardDescription>Cambio vs semana anterior</CardDescription>
          </CardHeader>
          <CardContent>
            <div className="h-[280px]">
              <ResponsiveContainer width="100%" height="100%">
                <BarChart data={chartData.slice(1)}>
                  <CartesianGrid strokeDasharray="3 3" stroke="#E2E8F0" />
                  <XAxis dataKey="semana" tick={{fontSize: 11}} stroke="#94A3B8" />
                  <YAxis tick={{fontSize: 11}} stroke="#94A3B8" tickFormatter={(v) => `${(v/1000).toFixed(0)}k`} />
                  <Tooltip 
                    formatter={(value, name) => [formatCurrency(value), 'Varianza']}
                    contentStyle={{backgroundColor: '#fff', border: '1px solid #E2E8F0', borderRadius: '8px'}}
                  />
                  <ReferenceLine y={0} stroke="#94A3B8" />
                  <Bar 
                    dataKey="varianza" 
                    name="Varianza"
                    fill={(entry) => entry.varianza >= 0 ? '#10B981' : '#EF4444'}
                  >
                    {chartData.slice(1).map((entry, index) => (
                      <rect key={index} fill={entry.varianza >= 0 ? '#10B981' : '#EF4444'} />
                    ))}
                  </Bar>
                </BarChart>
              </ResponsiveContainer>
            </div>
          </CardContent>
        </Card>
      </div>

      {/* Cash Pooling & Account Details */}
      <div className="grid grid-cols-1 lg:grid-cols-3 gap-4">
        {/* Cash Pooling by Currency */}
        <Card className="shadow-sm">
          <CardHeader className="pb-2">
            <CardTitle className="text-sm font-medium flex items-center gap-2">
              <Layers size={16} className="text-[#6366F1]" />
              Cash Pooling por Moneda
            </CardTitle>
          </CardHeader>
          <CardContent>
            <div className="space-y-3">
              {Object.entries(cashPool).map(([currency, data]) => (
                <div key={currency} className="flex items-center justify-between p-3 bg-[#F1F5F9] rounded-lg">
                  <div>
                    <div className="font-semibold text-[#0F172A]">{currency}</div>
                    <div className="text-xs text-[#64748B]">{data.cuentas} cuenta(s)</div>
                  </div>
                  <div className="text-right">
                    <div className="font-bold mono text-[#0F172A]">
                      ${data.total.toLocaleString('es-MX', {minimumFractionDigits: 2})}
                    </div>
                  </div>
                </div>
              ))}
              {Object.keys(cashPool).length === 0 && (
                <p className="text-sm text-[#94A3B8] text-center py-4">Sin datos de cash pooling</p>
              )}
            </div>
          </CardContent>
        </Card>

        {/* Account Details with Risk Indicators */}
        <Card className="shadow-sm lg:col-span-2">
          <CardHeader className="pb-2">
            <CardTitle className="text-sm font-medium flex items-center gap-2">
              <Building2 size={16} className="text-[#0EA5E9]" />
              Detalle de Cuentas
            </CardTitle>
          </CardHeader>
          <CardContent>
            <div className="space-y-2 max-h-[250px] overflow-y-auto">
              {accounts.map((acc) => (
                <div key={acc.id} className={`flex items-center justify-between p-3 rounded-lg border ${
                  acc.riesgo_ocioso ? 'border-amber-300 bg-amber-50' : 
                  acc.riesgo_bajo_saldo ? 'border-red-300 bg-red-50' : 
                  'border-[#E2E8F0] bg-white'
                }`}>
                  <div className="flex items-center gap-3">
                    <div className={`w-2 h-8 rounded-full ${
                      acc.riesgo_ocioso ? 'bg-amber-400' : 
                      acc.riesgo_bajo_saldo ? 'bg-red-400' : 
                      'bg-green-400'
                    }`} />
                    <div>
                      <div className="font-medium text-[#0F172A]">{acc.nombre}</div>
                      <div className="text-xs text-[#64748B]">{acc.banco} • {acc.moneda}</div>
                    </div>
                  </div>
                  <div className="text-right">
                    <div className="font-bold mono">
                      ${acc.saldo_inicial?.toLocaleString('es-MX', {minimumFractionDigits: 2})} {acc.moneda}
                    </div>
                    {acc.moneda !== 'MXN' && (
                      <div className="text-xs text-[#64748B]">
                        ≈ ${acc.saldo_mxn?.toLocaleString('es-MX', {minimumFractionDigits: 2})} MXN
                      </div>
                    )}
                    {(acc.riesgo_ocioso || acc.riesgo_bajo_saldo) && (
                      <div className="flex items-center justify-end gap-1 mt-1">
                        {acc.riesgo_ocioso && (
                          <span className="text-xs text-amber-700 flex items-center gap-0.5">
                            <PiggyBank size={12} /> Ocioso
                          </span>
                        )}
                        {acc.riesgo_bajo_saldo && (
                          <span className="text-xs text-red-700 flex items-center gap-0.5">
                            <AlertTriangle size={12} /> Bajo
                          </span>
                        )}
                      </div>
                    )}
                  </div>
                </div>
              ))}
              {accounts.length === 0 && (
                <p className="text-sm text-[#94A3B8] text-center py-4">No hay cuentas bancarias</p>
              )}
            </div>
          </CardContent>
        </Card>
      </div>

      {/* Secondary KPIs */}
      <div className="grid grid-cols-2 md:grid-cols-5 gap-3">
        <Card className="shadow-sm">
          <CardContent className="pt-4">
            <div className="flex items-center justify-between">
              <ArrowRightLeft className="h-5 w-5 text-[#64748B]" />
              <span className="text-2xl font-bold mono">{kpis.total_transactions || 0}</span>
            </div>
            <p className="text-xs text-[#64748B] mt-1">Transacciones</p>
          </CardContent>
        </Card>

        <Card className="shadow-sm">
          <CardContent className="pt-4">
            <div className="flex items-center justify-between">
              <FileText className="h-5 w-5 text-[#64748B]" />
              <span className="text-2xl font-bold mono">{kpis.total_cfdis || 0}</span>
            </div>
            <p className="text-xs text-[#64748B] mt-1">CFDIs</p>
          </CardContent>
        </Card>

        <Card className="shadow-sm">
          <CardContent className="pt-4">
            <div className="flex items-center justify-between">
              <CheckCircle2 className="h-5 w-5 text-[#64748B]" />
              <span className="text-2xl font-bold mono">{kpis.total_reconciliations || 0}</span>
            </div>
            <p className="text-xs text-[#64748B] mt-1">Conciliaciones</p>
          </CardContent>
        </Card>

        <Card className="shadow-sm">
          <CardContent className="pt-4">
            <div className="flex items-center justify-between">
              <span className="text-blue-600">👤</span>
              <span className="text-2xl font-bold mono">{kpis.total_customers || 0}</span>
            </div>
            <p className="text-xs text-[#64748B] mt-1">Clientes</p>
          </CardContent>
        </Card>

        <Card className="shadow-sm">
          <CardContent className="pt-4">
            <div className="flex items-center justify-between">
              <span className="text-orange-600">🏢</span>
              <span className="text-2xl font-bold mono">{kpis.total_vendors || 0}</span>
            </div>
            <p className="text-xs text-[#64748B] mt-1">Proveedores</p>
          </CardContent>
        </Card>
      </div>

      {/* ============ SECTION: DIAGNÓSTICO Y ACCIONES ============ */}
      <div className="grid grid-cols-1 lg:grid-cols-2 gap-4">
        {/* Cash Flow KPIs Clave */}
        <Card className="shadow-sm border-t-4 border-t-blue-500">
          <CardHeader className="pb-2">
            <CardTitle className="text-sm font-medium flex items-center gap-2">
              <Wallet size={16} className="text-blue-600" />
              KPIs Clave de Liquidez
            </CardTitle>
          </CardHeader>
          <CardContent>
            <div className="space-y-3">
              {/* Runway - Semanas de operación */}
              <div className="flex justify-between items-center p-3 bg-blue-50 rounded-lg">
                <div>
                  <div className="text-xs text-blue-700 font-medium">RUNWAY</div>
                  <div className="text-xs text-gray-500">Semanas de operación con saldo actual</div>
                </div>
                <div className="text-right">
                  <span className={`text-2xl font-bold ${
                    (trend.avg_flow_4w < 0 && saldoInicial > 0) 
                      ? (Math.abs(saldoInicial / trend.avg_flow_4w) > 13 ? 'text-green-600' : 
                         Math.abs(saldoInicial / trend.avg_flow_4w) > 6 ? 'text-amber-600' : 'text-red-600')
                      : 'text-green-600'
                  }`}>
                    {trend.avg_flow_4w < 0 && saldoInicial > 0 
                      ? Math.round(Math.abs(saldoInicial / trend.avg_flow_4w))
                      : '∞'
                    }
                  </span>
                  <span className="text-sm text-gray-500 ml-1">semanas</span>
                </div>
              </div>

              {/* Burn Rate */}
              <div className="flex justify-between items-center p-3 bg-gray-50 rounded-lg">
                <div>
                  <div className="text-xs text-gray-700 font-medium">BURN RATE</div>
                  <div className="text-xs text-gray-500">Promedio de egresos semanales</div>
                </div>
                <div className="text-right">
                  <span className="text-lg font-bold text-red-600">
                    {formatCurrency(chartData.reduce((sum, w) => sum + (w.egresos || 0), 0) / Math.max(chartData.length, 1))}
                  </span>
                  <span className="text-xs text-gray-500 ml-1">/sem</span>
                </div>
              </div>

              {/* Cash Conversion */}
              <div className="flex justify-between items-center p-3 bg-gray-50 rounded-lg">
                <div>
                  <div className="text-xs text-gray-700 font-medium">COBRANZA VS PAGOS</div>
                  <div className="text-xs text-gray-500">Ratio ingresos / egresos</div>
                </div>
                <div className="text-right">
                  {(() => {
                    const totalIng = chartData.reduce((sum, w) => sum + (w.ingresos || 0), 0);
                    const totalEgr = chartData.reduce((sum, w) => sum + (w.egresos || 0), 0);
                    const ratio = totalEgr > 0 ? (totalIng / totalEgr) : 1;
                    return (
                      <span className={`text-lg font-bold ${ratio >= 1 ? 'text-green-600' : 'text-red-600'}`}>
                        {(ratio * 100).toFixed(0)}%
                      </span>
                    );
                  })()}
                </div>
              </div>

              {/* Week with lowest balance */}
              <div className="flex justify-between items-center p-3 bg-amber-50 rounded-lg">
                <div>
                  <div className="text-xs text-amber-700 font-medium">SEMANA CRÍTICA</div>
                  <div className="text-xs text-gray-500">Menor saldo proyectado</div>
                </div>
                <div className="text-right">
                  {(() => {
                    const minWeek = chartData.reduce((min, w, i) => 
                      (!min || w.saldo_final < min.saldo_final) ? {...w, idx: i} : min, null);
                    return minWeek ? (
                      <>
                        <span className={`text-lg font-bold ${minWeek.saldo_final < 0 ? 'text-red-600' : 'text-amber-600'}`}>
                          {minWeek.semana}
                        </span>
                        <div className="text-xs text-gray-500">{formatCurrency(minWeek.saldo_final)}</div>
                      </>
                    ) : '-';
                  })()}
                </div>
              </div>
            </div>
          </CardContent>
        </Card>

        {/* Acciones Recomendadas */}
        <Card className="shadow-sm border-t-4 border-t-green-500">
          <CardHeader className="pb-2">
            <CardTitle className="text-sm font-medium flex items-center gap-2">
              <CheckCircle2 size={16} className="text-green-600" />
              ¿Qué Hacer Ahora?
            </CardTitle>
            <CardDescription>Acciones recomendadas basadas en tu flujo</CardDescription>
          </CardHeader>
          <CardContent>
            <div className="space-y-2">
              {/* Dynamic recommendations based on data */}
              {(() => {
                const recommendations = [];
                const totalIng = chartData.reduce((sum, w) => sum + (w.ingresos || 0), 0);
                const totalEgr = chartData.reduce((sum, w) => sum + (w.egresos || 0), 0);
                const minWeek = chartData.reduce((min, w) => 
                  (!min || w.saldo_final < min.saldo_final) ? w : min, null);
                const weeksWithDeficit = chartData.filter(w => w.saldo_final < 0).length;

                // Liquidez crítica
                if (risks.liquidez_critica || (minWeek && minWeek.saldo_final < 0)) {
                  recommendations.push({
                    priority: 'alta',
                    icon: '🚨',
                    text: 'Acelerar cobranza o buscar línea de crédito',
                    detail: `Semana ${minWeek?.semana} proyecta déficit de ${formatCurrency(Math.abs(minWeek?.saldo_final || 0))}`
                  });
                }

                // Cobranza baja
                if (totalIng < totalEgr * 0.8) {
                  recommendations.push({
                    priority: 'alta',
                    icon: '📞',
                    text: 'Intensificar gestión de cobranza',
                    detail: `Los ingresos cubren solo ${((totalIng/totalEgr)*100).toFixed(0)}% de los egresos`
                  });
                }

                // Saldos ociosos
                if (risks.saldos_ociosos > 0) {
                  recommendations.push({
                    priority: 'media',
                    icon: '💰',
                    text: 'Invertir saldos excedentes',
                    detail: `${risks.saldos_ociosos} cuenta(s) con más de $500K sin rendimiento`
                  });
                }

                // Tendencia positiva
                if (trend.direction === 'up' && trend.avg_flow_4w > 0) {
                  recommendations.push({
                    priority: 'baja',
                    icon: '📈',
                    text: 'Aprovechar tendencia positiva',
                    detail: `Flujo promedio +${formatCurrency(trend.avg_flow_4w)}/semana`
                  });
                }

                // CFDIs sin conciliar
                if (kpis.total_cfdis > kpis.total_reconciliations) {
                  recommendations.push({
                    priority: 'media',
                    icon: '📋',
                    text: 'Conciliar CFDIs pendientes',
                    detail: `${kpis.total_cfdis - kpis.total_reconciliations} facturas sin conciliar`
                  });
                }

                // Default if no issues
                if (recommendations.length === 0) {
                  recommendations.push({
                    priority: 'baja',
                    icon: '✅',
                    text: 'Flujo de efectivo saludable',
                    detail: 'Continuar con el monitoreo semanal'
                  });
                }

                return recommendations.map((rec, idx) => (
                  <div key={idx} className={`flex items-start gap-3 p-3 rounded-lg ${
                    rec.priority === 'alta' ? 'bg-red-50 border border-red-200' :
                    rec.priority === 'media' ? 'bg-amber-50 border border-amber-200' :
                    'bg-green-50 border border-green-200'
                  }`}>
                    <span className="text-xl">{rec.icon}</span>
                    <div>
                      <div className={`font-medium text-sm ${
                        rec.priority === 'alta' ? 'text-red-800' :
                        rec.priority === 'media' ? 'text-amber-800' :
                        'text-green-800'
                      }`}>{rec.text}</div>
                      <div className="text-xs text-gray-600">{rec.detail}</div>
                    </div>
                  </div>
                ));
              })()}
            </div>
          </CardContent>
        </Card>
      </div>

      {/* Escenarios de Liquidez */}
      <Card className="shadow-sm">
        <CardHeader className="pb-2">
          <CardTitle className="text-sm font-medium flex items-center gap-2">
            <AlertTriangle size={16} className="text-amber-600" />
            Análisis de Escenarios
          </CardTitle>
          <CardDescription>Proyección de liquidez bajo diferentes condiciones</CardDescription>
        </CardHeader>
        <CardContent>
          <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
            {/* Escenario Pesimista */}
            <div className="p-4 bg-red-50 rounded-lg border border-red-200">
              <div className="flex items-center gap-2 mb-2">
                <TrendingDown size={16} className="text-red-600" />
                <span className="font-medium text-red-800">Escenario Pesimista</span>
              </div>
              <p className="text-xs text-gray-600 mb-3">Cobranza baja 30%, gastos suben 15%</p>
              {(() => {
                const avgIng = chartData.reduce((sum, w) => sum + (w.ingresos || 0), 0) / Math.max(chartData.length, 1);
                const avgEgr = chartData.reduce((sum, w) => sum + (w.egresos || 0), 0) / Math.max(chartData.length, 1);
                const pesimista = saldoInicial + ((avgIng * 0.7) - (avgEgr * 1.15)) * 13;
                return (
                  <div className={`text-xl font-bold ${pesimista < 0 ? 'text-red-600' : 'text-gray-800'}`}>
                    {formatCurrency(pesimista)}
                    {pesimista < 0 && <span className="text-xs ml-2 text-red-500">⚠️ Déficit</span>}
                  </div>
                );
              })()}
              <p className="text-xs text-gray-500 mt-1">Saldo al final de S13</p>
            </div>

            {/* Escenario Base */}
            <div className="p-4 bg-blue-50 rounded-lg border border-blue-200">
              <div className="flex items-center gap-2 mb-2">
                <Minus size={16} className="text-blue-600" />
                <span className="font-medium text-blue-800">Escenario Base</span>
              </div>
              <p className="text-xs text-gray-600 mb-3">Tendencia actual continúa</p>
              <div className={`text-xl font-bold ${saldoFinalProyectado < 0 ? 'text-red-600' : 'text-blue-800'}`}>
                {formatCurrency(saldoFinalProyectado)}
              </div>
              <p className="text-xs text-gray-500 mt-1">Saldo al final de S13</p>
            </div>

            {/* Escenario Optimista */}
            <div className="p-4 bg-green-50 rounded-lg border border-green-200">
              <div className="flex items-center gap-2 mb-2">
                <TrendingUp size={16} className="text-green-600" />
                <span className="font-medium text-green-800">Escenario Optimista</span>
              </div>
              <p className="text-xs text-gray-600 mb-3">Cobranza mejora 20%, gastos bajan 10%</p>
              {(() => {
                const avgIng = chartData.reduce((sum, w) => sum + (w.ingresos || 0), 0) / Math.max(chartData.length, 1);
                const avgEgr = chartData.reduce((sum, w) => sum + (w.egresos || 0), 0) / Math.max(chartData.length, 1);
                const optimista = saldoInicial + ((avgIng * 1.2) - (avgEgr * 0.9)) * 13;
                return (
                  <div className="text-xl font-bold text-green-800">
                    {formatCurrency(optimista)}
                  </div>
                );
              })()}
              <p className="text-xs text-gray-500 mt-1">Saldo al final de S13</p>
            </div>
          </div>
        </CardContent>
      </Card>
    </div>
  );
};

export default Dashboard;
