import React, { useState, useEffect, useCallback } from 'react';
import PageHeader from '../components/PageHeader';
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '../components/ui/card';
import { Button } from '../components/ui/button';
import { Badge } from '../components/ui/badge';
import { Alert, AlertDescription } from '../components/ui/alert';
import { Progress } from '../components/ui/progress';
import { Tabs, TabsContent, TabsList, TabsTrigger } from '../components/ui/tabs';
import api from '../api/axios';
import { toast } from 'sonner';
import {
  AlertTriangle,
  TrendingUp,
  TrendingDown,
  Calendar,
  Users,
  Building2,
  DollarSign,
  RefreshCw,
  Loader2,
  Bell,
  Lightbulb,
  PieChart,
  Activity,
  Clock,
  ArrowRight,
  CheckCircle,
  XCircle,
  MinusCircle,
  Banknote,
  CreditCard,
  Briefcase,
  Home,
  Zap,
  FileText
} from 'lucide-react';

const formatCurrency = (amount, decimals = 0) => {
  return new Intl.NumberFormat('es-MX', {
    style: 'currency',
    currency: 'MXN',
    minimumFractionDigits: decimals,
    maximumFractionDigits: decimals
  }).format(amount || 0);
};

const RiskBadge = ({ level }) => {
  const config = {
    high: { color: 'bg-red-500', icon: '🔴', label: 'Alto Riesgo' },
    medium: { color: 'bg-yellow-500', icon: '🟡', label: 'Riesgo Medio' },
    low: { color: 'bg-green-500', icon: '🟢', label: 'Bajo Riesgo' }
  };
  const { color, icon, label } = config[level] || config.low;
  return (
    <Badge className={`${color} text-white`}>
      {icon} {label}
    </Badge>
  );
};

const HealthIndicator = ({ health }) => {
  const config = {
    excellent: { color: 'text-green-600', bg: 'bg-green-100', icon: <CheckCircle className="h-4 w-4" /> },
    good: { color: 'text-blue-600', bg: 'bg-blue-100', icon: <CheckCircle className="h-4 w-4" /> },
    fair: { color: 'text-yellow-600', bg: 'bg-yellow-100', icon: <MinusCircle className="h-4 w-4" /> },
    poor: { color: 'text-red-600', bg: 'bg-red-100', icon: <XCircle className="h-4 w-4" /> }
  };
  const { color, bg, icon } = config[health] || config.fair;
  return (
    <div className={`inline-flex items-center gap-1 px-2 py-1 rounded ${bg} ${color}`}>
      {icon}
      <span className="text-xs font-medium capitalize">{health}</span>
    </div>
  );
};

const TrendIndicator = ({ trend, value }) => {
  if (trend === 'improving') {
    return <span className="text-green-600 text-sm flex items-center gap-1"><TrendingDown className="h-4 w-4" /> ↓ Mejorando</span>;
  } else if (trend === 'worsening') {
    return <span className="text-red-600 text-sm flex items-center gap-1"><TrendingUp className="h-4 w-4" /> ↑ Empeorando</span>;
  }
  return <span className="text-gray-500 text-sm">→ Estable</span>;
};

export default function TreasuryDecisions() {
  const [data, setData] = useState(null);
  const [loading, setLoading] = useState(true);
  const [refreshing, setRefreshing] = useState(false);
  // Fix 2: normalizar week_start a string ISO antes de comparar (puede llegar como datetime)
  const hoy = new Date().toISOString().slice(0, 10);
  const calendarWeeks = (data?.calendar?.weeks || [])
    .sort((a, b) => {
      const fa = String(a.week_start || a.fecha_inicio || '');
      const fb = String(b.week_start || b.fecha_inicio || '');
      return fa.localeCompare(fb);
    })
    .filter(w => {
      const weekStart = String(w.week_start || w.fecha_inicio || '').slice(0, 10);
      const tieneDatos = (w.total_ingresos || 0) > 0 || (w.total_egresos || 0) > 0;
      const esFutura = weekStart >= hoy;
      return tieneDatos || esFutura;
    });

  // Fix 3: compute mesesDisponibles before useState so initial value is correct
  const mesesDisponibles = [...new Set(
    calendarWeeks.map(w => {
      const fecha = new Date((w.week_start || w.fecha_inicio) + 'T00:00:00');
      return `${fecha.getFullYear()}-${String(fecha.getMonth() + 1).padStart(2, '0')}`;
    })
  )].sort();

  const mesActual = new Date().toISOString().slice(0, 7);
  const [mesSeleccionado, setMesSeleccionado] = useState(
    mesesDisponibles.includes(mesActual) ? mesActual : (mesesDisponibles[0] || mesActual)
  );

  const loadData = useCallback(async () => {
    try {
      // Usar /treasury/dashboard — calcula todo correctamente en el backend
      const dashRes = await api.get('/treasury/dashboard?weeks_ahead=52');
      const dash = dashRes.data || {};

      const cash_position = dash.cash_position || {
        saldo_actual: 0, cuentas_por_cobrar: 0, cuentas_por_pagar: 0,
        flujo_neto_esperado: 0, posicion_proyectada: 0,
      };

      // Usar datos del backend directamente
      const alerts          = dash.alerts          || [];
      const recommendations = dash.recommendations || [];
      const calendar        = dash.calendar        || { weeks: [], categories: {}, totals_by_category: {} };
      const concentration_kpis = dash.concentration_kpis || {};
      const working_capital = dash.working_capital || {};

      setData({ cash_position, alerts, recommendations, calendar, concentration_kpis, working_capital });
    } catch (error) {
      console.error('Error loading treasury data:', error);
      toast.error('Error cargando datos de tesorería');
    } finally {
      setLoading(false);
      setRefreshing(false);
    }
  }, []);

  useEffect(() => {
    loadData();
  }, [loadData]);

  const handleRefresh = () => {
    setRefreshing(true);
    loadData();
  };

  if (loading) {
    return (
      <div className="flex items-center justify-center min-h-[400px]">
        <Loader2 className="h-8 w-8 animate-spin text-[#0EA5E9]" />
        <span className="ml-2 text-[#64748B]">Analizando datos de tesorería...</span>
      </div>
    );
  }

  const { alerts, recommendations, calendar, concentration_kpis, working_capital, cash_position } = data || {};

  // ── Calendario: filtrar por mes, conservar labels originales del backend (S1-S52) ──
  const formatearMes = (mesStr) => {
    const [year, month] = mesStr.split('-');
    const nombre = new Date(year, month - 1, 1).toLocaleDateString('es-MX', {
      month: 'long', year: 'numeric',
    });
    return nombre.charAt(0).toUpperCase() + nombre.slice(1);
  };

  // Fix 1: una semana pertenece al mes donde empieza — sin fin.setDate redundante
  const semanasFiltradas = calendarWeeks.filter(w => {
    const inicio = new Date((w.week_start || w.fecha_inicio) + 'T00:00:00');
    const mesInicio = `${inicio.getFullYear()}-${String(inicio.getMonth() + 1).padStart(2, '0')}`;
    return mesInicio === mesSeleccionado;
  });

  const categoryIcons = {
    nomina: <Users className="h-4 w-4" />,
    impuestos: <Building2 className="h-4 w-4" />,
    creditos: <Banknote className="h-4 w-4" />,
    rentas: <Home className="h-4 w-4" />,
    servicios: <Zap className="h-4 w-4" />,
    otros: <FileText className="h-4 w-4" />
  };

  return (
    <div className="space-y-6" data-testid="treasury-decisions-page">
      {/* Header */}
      <div className="flex items-center justify-between">
        <div>
          <PageHeader title="Decisiones de Tesorería" subtitle="Calendario de pagos y proyecciones" breadcrumb="Decisiones de Tesorería" />
        </div>
        <Button onClick={handleRefresh} disabled={refreshing} variant="outline">
          {refreshing ? <Loader2 className="h-4 w-4 mr-2 animate-spin" /> : <RefreshCw className="h-4 w-4 mr-2" />}
          Actualizar
        </Button>
      </div>

      {/* Cash Position Summary */}
      {cash_position && (
        <div className="grid grid-cols-1 md:grid-cols-5 gap-4">
          <Card className="bg-gradient-to-br from-blue-500 to-blue-600 text-white">
            <CardContent className="pt-4">
              <div className="text-sm opacity-80">Saldo Actual</div>
              <div className="text-2xl font-bold">{formatCurrency(cash_position.saldo_actual)}</div>
            </CardContent>
          </Card>
          <Card className="bg-gradient-to-br from-green-500 to-green-600 text-white">
            <CardContent className="pt-4">
              <div className="text-sm opacity-80">Por Cobrar</div>
              <div className="text-2xl font-bold">{formatCurrency(cash_position.cuentas_por_cobrar)}</div>
            </CardContent>
          </Card>
          <Card className="bg-gradient-to-br from-red-500 to-red-600 text-white">
            <CardContent className="pt-4">
              <div className="text-sm opacity-80">Por Pagar</div>
              <div className="text-2xl font-bold">{formatCurrency(cash_position.cuentas_por_pagar)}</div>
            </CardContent>
          </Card>
          <Card className="bg-gradient-to-br from-purple-500 to-purple-600 text-white">
            <CardContent className="pt-4">
              <div className="text-sm opacity-80">Flujo Neto Esperado</div>
              <div className="text-2xl font-bold">{formatCurrency(cash_position.flujo_neto_esperado)}</div>
            </CardContent>
          </Card>
          <Card className={`bg-gradient-to-br ${cash_position.posicion_proyectada >= 0 ? 'from-emerald-500 to-emerald-600' : 'from-orange-500 to-orange-600'} text-white`}>
            <CardContent className="pt-4">
              <div className="text-sm opacity-80">Posición Proyectada</div>
              <div className="text-2xl font-bold">{formatCurrency(cash_position.posicion_proyectada)}</div>
            </CardContent>
          </Card>
        </div>
      )}

      <Tabs defaultValue="alerts" className="w-full">
        <TabsList className="grid w-full grid-cols-5">
          <TabsTrigger value="alerts" className="flex items-center gap-2">
            <Bell className="h-4 w-4" />
            Alertas
          </TabsTrigger>
          <TabsTrigger value="recommendations" className="flex items-center gap-2">
            <Lightbulb className="h-4 w-4" />
            Recomendaciones
          </TabsTrigger>
          <TabsTrigger value="calendar" className="flex items-center gap-2">
            <Calendar className="h-4 w-4" />
            Calendario
          </TabsTrigger>
          <TabsTrigger value="concentration" className="flex items-center gap-2">
            <PieChart className="h-4 w-4" />
            Concentración
          </TabsTrigger>
          <TabsTrigger value="working-capital" className="flex items-center gap-2">
            <Activity className="h-4 w-4" />
            Working Capital
          </TabsTrigger>
        </TabsList>

        {/* ALERTS TAB */}
        <TabsContent value="alerts" className="mt-4">
          <Card>
            <CardHeader>
              <CardTitle className="flex items-center gap-2">
                <Bell className="h-5 w-5 text-orange-500" />
                Alertas Accionables
              </CardTitle>
              <CardDescription>Situaciones que requieren tu atención inmediata</CardDescription>
            </CardHeader>
            <CardContent>
              {alerts && alerts.length > 0 ? (
                <div className="space-y-3">
                  {alerts.map((alert, idx) => (
                    <Alert 
                      key={idx} 
                      className={`
                        ${alert.severity === 'high' ? 'border-red-300 bg-red-50' : ''}
                        ${alert.severity === 'medium' ? 'border-yellow-300 bg-yellow-50' : ''}
                        ${alert.severity === 'low' ? 'border-green-300 bg-green-50' : ''}
                      `}
                    >
                      <div className="flex items-start justify-between w-full">
                        <div className="flex-1">
                          <div className="flex items-center gap-2 mb-1">
                            <span className="text-lg">
                              {alert.severity === 'high' ? '🔴' : alert.severity === 'medium' ? '🟡' : '🟢'}
                            </span>
                            <span className="font-semibold text-sm">{alert.week} ({alert.week_date})</span>
                            <Badge variant="outline" className="text-xs">
                              {alert.type === 'balance_critical' ? 'Saldo Crítico' : 
                               alert.type === 'collection_delay_risk' ? 'Riesgo Cobranza' :
                               alert.type === 'payment_flexibility' ? 'Flexibilidad Pago' : alert.type}
                            </Badge>
                          </div>
                          <AlertDescription className="text-sm">
                            <strong>{alert.message}</strong>
                            <div className="text-gray-600 mt-1">{alert.detail}</div>
                            <div className="mt-2 flex items-center gap-2">
                              <ArrowRight className="h-3 w-3 text-blue-500" />
                              <span className="text-blue-600 text-xs">{alert.action}</span>
                            </div>
                          </AlertDescription>
                        </div>
                        <div className={`text-right font-bold ${alert.impact >= 0 ? 'text-green-600' : 'text-red-600'}`}>
                          {alert.impact >= 0 ? '+' : ''}{formatCurrency(alert.impact)}
                        </div>
                      </div>
                    </Alert>
                  ))}
                </div>
              ) : (
                <div className="text-center py-8 text-gray-500">
                  <CheckCircle className="h-12 w-12 mx-auto mb-2 text-green-500" />
                  <p>No hay alertas críticas en este momento</p>
                </div>
              )}
            </CardContent>
          </Card>
        </TabsContent>

        {/* RECOMMENDATIONS TAB */}
        <TabsContent value="recommendations" className="mt-4">
          <Card>
            <CardHeader>
              <CardTitle className="flex items-center gap-2">
                <Lightbulb className="h-5 w-5 text-yellow-500" />
                Recomendaciones
              </CardTitle>
              <CardDescription>Acciones sugeridas para optimizar tu flujo de efectivo</CardDescription>
            </CardHeader>
            <CardContent>
              {recommendations && recommendations.length > 0 ? (
                <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
                  {recommendations.map((rec, idx) => (
                    <Card key={idx} className={`
                      ${rec.priority === 'high' ? 'border-red-200 bg-red-50/50' : ''}
                      ${rec.priority === 'medium' ? 'border-yellow-200 bg-yellow-50/50' : ''}
                      ${rec.priority === 'info' ? 'border-blue-200 bg-blue-50/50' : ''}
                    `}>
                      <CardContent className="pt-4">
                        <div className="flex items-start gap-3">
                          <span className="text-2xl">{rec.icon}</span>
                          <div className="flex-1">
                            <h4 className="font-semibold text-sm">{rec.title}</h4>
                            <p className="text-sm text-gray-600 mt-1">{rec.message}</p>
                            <div className="mt-2 flex items-center justify-between">
                              <Badge variant="outline" className="text-green-600">
                                Impacto: {rec.impact}
                              </Badge>
                              <Badge className={`
                                ${rec.priority === 'high' ? 'bg-red-500' : ''}
                                ${rec.priority === 'medium' ? 'bg-yellow-500' : ''}
                                ${rec.priority === 'info' ? 'bg-blue-500' : ''}
                              `}>
                                {rec.priority === 'high' ? 'Urgente' : rec.priority === 'medium' ? 'Importante' : 'Info'}
                              </Badge>
                            </div>
                          </div>
                        </div>
                      </CardContent>
                    </Card>
                  ))}
                </div>
              ) : (
                <div className="text-center py-8 text-gray-500">
                  <Lightbulb className="h-12 w-12 mx-auto mb-2 text-yellow-400" />
                  <p>No hay recomendaciones disponibles</p>
                </div>
              )}
            </CardContent>
          </Card>
        </TabsContent>

        {/* CALENDAR TAB */}
        <TabsContent value="calendar" className="mt-4">
          <Card>
            <CardHeader>
              <CardTitle className="flex items-center gap-2">
                <Calendar className="h-5 w-5 text-blue-500" />
                Calendario de Tesorería
              </CardTitle>
              <CardDescription>Pagos fijos y compromisos por semana</CardDescription>
            </CardHeader>
            <CardContent>
              {calendar && calendar.weeks ? (
                <div className="space-y-4">
                  {/* Category Legend */}
                  <div className="flex flex-wrap gap-4 pb-4 border-b">
                    {calendar.categories && Object.entries(calendar.categories).map(([key, cat]) => (
                      <div key={key} className="flex items-center gap-2 text-sm">
                        {categoryIcons[key] || <FileText className="h-4 w-4" />}
                        <span>{cat.name}</span>
                        {calendar.totals_by_category?.[key] > 0 && (
                          <Badge variant="outline">{formatCurrency(calendar.totals_by_category[key])}</Badge>
                        )}
                      </div>
                    ))}
                  </div>

                  {/* Month selector */}
                  <div className="flex gap-2 flex-wrap">
                    {mesesDisponibles.map(mes => (
                      <button
                        key={mes}
                        onClick={() => setMesSeleccionado(mes)}
                        className={`px-3 py-1 rounded-full text-sm font-medium transition-colors ${
                          mesSeleccionado === mes
                            ? 'bg-[#0F172A] text-white'
                            : 'bg-gray-100 text-gray-600 hover:bg-gray-200'
                        }`}
                      >
                        {formatearMes(mes)}
                      </button>
                    ))}
                  </div>

                  {/* Weekly Grid — semanas del mes seleccionado */}
                  {semanasFiltradas.length > 0 ? (
                    <div className="grid grid-cols-1 md:grid-cols-4 gap-4">
                      {semanasFiltradas.map((week, idx) => (
                        <div
                          key={idx}
                          className={`border rounded-lg p-4 ${
                            week.total_ingresos === 0 && week.total_egresos === 0
                              ? 'border-gray-200 bg-gray-50'
                              : week.flujo_neto < 0
                                ? 'border-red-200 bg-red-50'
                                : 'border-green-100'
                          }`}
                        >
                          <div className="flex justify-between items-center mb-2">
                            <span className="font-bold text-sm">{week.label}</span>
                            <span className="text-xs text-gray-400">{week.date_range}</span>
                          </div>

                          {week.total_ingresos === 0 && week.total_egresos === 0 ? (
                            <p className="text-xs text-gray-400 text-center py-2">Sin movimientos</p>
                          ) : (
                            <>
                              <p className={`text-lg font-bold ${week.flujo_neto >= 0 ? 'text-[#10B981]' : 'text-[#EF4444]'}`}>
                                {week.flujo_neto >= 0 ? '+' : ''}${Math.abs(week.flujo_neto || 0).toLocaleString('es-MX', { maximumFractionDigits: 0 })}
                              </p>
                              {week.total_ingresos > 0 && (
                                <div className="flex justify-between text-xs mt-1">
                                  <span className="text-gray-500">Cobranza</span>
                                  <span className="text-[#10B981] font-medium">${week.total_ingresos.toLocaleString('es-MX', { maximumFractionDigits: 0 })}</span>
                                </div>
                              )}
                              {week.total_egresos > 0 && (
                                <div className="flex justify-between text-xs mt-1">
                                  <span className="text-gray-500">Pagos</span>
                                  <span className="text-[#EF4444] font-medium">${week.total_egresos.toLocaleString('es-MX', { maximumFractionDigits: 0 })}</span>
                                </div>
                              )}
                              {week.top_ingresos?.slice(0, 2).map((item, i) => (
                                <div key={i} className="flex justify-between text-xs text-gray-500 mt-0.5">
                                  <span className="truncate max-w-[65%]">{item.concepto || item.nombre}</span>
                                  <span className="text-[#10B981]">${(item.monto || 0).toLocaleString('es-MX', { maximumFractionDigits: 0 })}</span>
                                </div>
                              ))}
                              {week.top_egresos?.slice(0, 2).map((item, i) => (
                                <div key={i} className="flex justify-between text-xs text-gray-500 mt-0.5">
                                  <span className="truncate max-w-[65%]">{item.concepto || item.nombre}</span>
                                  <span className="text-[#EF4444]">${(item.monto || 0).toLocaleString('es-MX', { maximumFractionDigits: 0 })}</span>
                                </div>
                              ))}
                            </>
                          )}
                          {/* Notas manuales */}
                          <div className="mt-2 border-t border-gray-100 pt-2">
                            <textarea
                              className="w-full text-xs text-gray-500 resize-none border-none outline-none bg-transparent placeholder-gray-300"
                              placeholder="Agregar nota..."
                              rows={2}
                              defaultValue={week.notas || ''}
                              onBlur={async (e) => {
                                if (e.target.value !== (week.notas || '')) {
                                  await api.patch(`/treasury/weeks/${week.id}/notas`, { notas: e.target.value });
                                }
                              }}
                            />
                          </div>
                        </div>
                      ))}
                    </div>
                  ) : (
                    <div className="text-center py-8 text-gray-400 text-sm">
                      Sin semanas disponibles para este mes
                    </div>
                  )}
                </div>
              ) : (
                <div className="text-center py-8 text-gray-500">
                  <Calendar className="h-12 w-12 mx-auto mb-2 text-gray-300" />
                  <p>No hay datos de calendario disponibles</p>
                </div>
              )}
            </CardContent>
          </Card>
        </TabsContent>

        {/* CONCENTRATION TAB */}
        <TabsContent value="concentration" className="mt-4">
          <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
            {/* Top 3 Clients */}
            {concentration_kpis?.top_3_clients && (
              <Card className="border-green-200">
                <CardHeader>
                  <CardTitle className="flex items-center justify-between text-sm">
                    <span className="flex items-center gap-2">
                      <Users className="h-4 w-4 text-green-600" />
                      Top 3 Clientes en Cobranza
                    </span>
                    <RiskBadge level={concentration_kpis.top_3_clients.risk_level} />
                  </CardTitle>
                </CardHeader>
                <CardContent>
                  <div className="text-4xl font-bold text-green-600 mb-2">
                    {concentration_kpis.top_3_clients.percentage}%
                  </div>
                  <Progress 
                    value={concentration_kpis.top_3_clients.percentage} 
                    className="h-2 mb-4"
                  />
                  <div className="space-y-2">
                    {concentration_kpis.top_3_clients.names.map((name, idx) => (
                      <div key={idx} className="flex items-center justify-between text-sm">
                        <span className="truncate flex-1">{name || 'N/A'}</span>
                        <span className="font-medium ml-2">
                          {formatCurrency(concentration_kpis.top_3_clients.amounts[idx])}
                        </span>
                      </div>
                    ))}
                  </div>
                  <p className="text-xs text-gray-500 mt-3">
                    {concentration_kpis.top_3_clients.detail}
                  </p>
                </CardContent>
              </Card>
            )}

            {/* Top 5 Vendors */}
            {concentration_kpis?.top_5_vendors && (
              <Card className="border-red-200">
                <CardHeader>
                  <CardTitle className="flex items-center justify-between text-sm">
                    <span className="flex items-center gap-2">
                      <Building2 className="h-4 w-4 text-red-600" />
                      Top 5 Proveedores en Egresos
                    </span>
                    <RiskBadge level={concentration_kpis.top_5_vendors.risk_level} />
                  </CardTitle>
                </CardHeader>
                <CardContent>
                  <div className="text-4xl font-bold text-red-600 mb-2">
                    {concentration_kpis.top_5_vendors.percentage}%
                  </div>
                  <Progress 
                    value={concentration_kpis.top_5_vendors.percentage} 
                    className="h-2 mb-4"
                  />
                  <div className="space-y-2">
                    {concentration_kpis.top_5_vendors.names.slice(0, 5).map((name, idx) => (
                      <div key={idx} className="flex items-center justify-between text-sm">
                        <span className="truncate flex-1">{name || 'N/A'}</span>
                        <span className="font-medium ml-2">
                          {formatCurrency(concentration_kpis.top_5_vendors.amounts[idx])}
                        </span>
                      </div>
                    ))}
                  </div>
                  <p className="text-xs text-gray-500 mt-3">
                    {concentration_kpis.top_5_vendors.detail}
                  </p>
                </CardContent>
              </Card>
            )}

            {/* Single Client Dependency */}
            {concentration_kpis?.single_client_dependency && (
              <Card className="border-purple-200">
                <CardHeader>
                  <CardTitle className="flex items-center justify-between text-sm">
                    <span className="flex items-center gap-2">
                      <Clock className="h-4 w-4 text-purple-600" />
                      Dependencia de Cliente
                    </span>
                    <RiskBadge level={concentration_kpis.single_client_dependency.risk_level} />
                  </CardTitle>
                </CardHeader>
                <CardContent>
                  <div className="text-4xl font-bold text-purple-600 mb-2">
                    {concentration_kpis.single_client_dependency.weeks_dependent} 
                    <span className="text-lg ml-1">semanas</span>
                  </div>
                  <div className="text-sm mb-4">
                    <strong>{concentration_kpis.single_client_dependency.client_name}</strong>
                    <div className="text-gray-600">
                      Pendiente: {formatCurrency(concentration_kpis.single_client_dependency.pending_amount)}
                    </div>
                    <div className="text-gray-600">
                      {concentration_kpis.single_client_dependency.percentage_of_pending}% de la cobranza pendiente
                    </div>
                  </div>
                  <p className="text-xs text-gray-500">
                    {concentration_kpis.single_client_dependency.detail}
                  </p>
                </CardContent>
              </Card>
            )}
          </div>
        </TabsContent>

        {/* WORKING CAPITAL TAB */}
        <TabsContent value="working-capital" className="mt-4">
          <div className="grid grid-cols-1 md:grid-cols-3 gap-4 mb-4">
            {/* DSO */}
            {working_capital?.dso && (
              <Card>
                <CardHeader>
                  <CardTitle className="flex items-center justify-between text-sm">
                    <span>DSO (Días de Cobranza)</span>
                    <HealthIndicator health={working_capital.dso.health} />
                  </CardTitle>
                </CardHeader>
                <CardContent>
                  <div className="text-4xl font-bold text-blue-600 mb-1">
                    {working_capital.dso.value} <span className="text-lg">días</span>
                  </div>
                  <p className="text-sm text-gray-600 mb-2">{working_capital.dso.description}</p>
                  <TrendIndicator trend={working_capital.dso.trend} value={working_capital.dso.trend_value} />
                  <p className="text-xs text-gray-500 mt-1">{working_capital.dso.trend_description}</p>
                </CardContent>
              </Card>
            )}

            {/* DPO */}
            {working_capital?.dpo && (
              <Card>
                <CardHeader>
                  <CardTitle className="flex items-center justify-between text-sm">
                    <span>DPO (Días de Pago)</span>
                    <HealthIndicator health={working_capital.dpo.health} />
                  </CardTitle>
                </CardHeader>
                <CardContent>
                  <div className="text-4xl font-bold text-orange-600 mb-1">
                    {working_capital.dpo.value} <span className="text-lg">días</span>
                  </div>
                  <p className="text-sm text-gray-600 mb-2">{working_capital.dpo.description}</p>
                  <TrendIndicator trend={working_capital.dpo.trend} />
                </CardContent>
              </Card>
            )}

            {/* CCC */}
            {working_capital?.ccc && (
              <Card className={working_capital.ccc.is_positive ? 'border-green-300 bg-green-50/30' : 'border-red-300 bg-red-50/30'}>
                <CardHeader>
                  <CardTitle className="flex items-center justify-between text-sm">
                    <span>Ciclo de Conversión</span>
                    <HealthIndicator health={working_capital.ccc.health} />
                  </CardTitle>
                </CardHeader>
                <CardContent>
                  <div className={`text-4xl font-bold mb-1 ${working_capital.ccc.is_positive ? 'text-green-600' : 'text-red-600'}`}>
                    {working_capital.ccc.value} <span className="text-lg">días</span>
                  </div>
                  <p className="text-sm text-gray-600 mb-2">{working_capital.ccc.description}</p>
                  <Badge className={working_capital.ccc.is_positive ? 'bg-green-500' : 'bg-red-500'}>
                    {working_capital.ccc.interpretation}
                  </Badge>
                </CardContent>
              </Card>
            )}
          </div>

          {/* Summary */}
          {working_capital?.summary && (
            <Card className="bg-gradient-to-r from-blue-50 to-purple-50">
              <CardContent className="pt-4">
                <div className="flex items-center gap-4">
                  <Activity className="h-8 w-8 text-blue-600" />
                  <div>
                    <h4 className="font-semibold">{working_capital.summary.message}</h4>
                    <p className="text-sm text-gray-600">{working_capital.summary.recommendation}</p>
                  </div>
                </div>
              </CardContent>
            </Card>
          )}
        </TabsContent>
      </Tabs>
    </div>
  );
}
