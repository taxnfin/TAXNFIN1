import React, { useState, useEffect, useCallback } from 'react';
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

  const loadData = useCallback(async () => {
    try {
      const response = await api.get('/treasury/dashboard?weeks_ahead=8');
      setData(response.data);
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
          <h1 className="text-2xl font-bold text-[#1E293B]">Decisiones de Tesorería</h1>
          <p className="text-[#64748B]">Análisis inteligente y recomendaciones accionables</p>
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

                  {/* Weekly Grid */}
                  <div className="grid grid-cols-1 md:grid-cols-4 gap-4">
                    {calendar.weeks.slice(0, 8).map((week, idx) => (
                      <Card key={idx} className={`${week.total > 0 ? 'border-orange-200' : 'border-gray-100'}`}>
                        <CardHeader className="pb-2">
                          <div className="flex items-center justify-between">
                            <CardTitle className="text-sm font-bold">{week.label}</CardTitle>
                            <span className="text-xs text-gray-500">{week.date_range}</span>
                          </div>
                          {week.total > 0 && (
                            <div className="text-lg font-bold text-red-600">
                              -{formatCurrency(week.total)}
                            </div>
                          )}
                        </CardHeader>
                        <CardContent className="pt-0">
                          {week.total > 0 ? (
                            <div className="space-y-2">
                              {Object.entries(week.totals).map(([cat, amount]) => (
                                amount > 0 && (
                                  <div key={cat} className="flex items-center justify-between text-sm">
                                    <div className="flex items-center gap-1">
                                      {categoryIcons[cat]}
                                      <span className="text-gray-600">
                                        {calendar.categories?.[cat]?.name || cat}
                                      </span>
                                    </div>
                                    <span className="font-medium">{formatCurrency(amount)}</span>
                                  </div>
                                )
                              ))}
                            </div>
                          ) : (
                            <div className="text-center text-gray-400 text-sm py-2">
                              Sin pagos programados
                            </div>
                          )}
                        </CardContent>
                      </Card>
                    ))}
                  </div>
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
