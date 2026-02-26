import React, { useState, useEffect } from 'react';
import { useNavigate, useSearchParams } from 'react-router-dom';
import { Card, CardContent, CardHeader, CardTitle } from '../components/ui/card';
import { Button } from '../components/ui/button';
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from '../components/ui/select';
import { toast } from 'sonner';
import api from '../api/axios';
import {
  ArrowLeft, ArrowRight, TrendingUp, TrendingDown, Scale, Percent,
  Calculator, Activity, Target, Wallet, Building2, RefreshCw,
  ChevronRight, Minus, BarChart3, GitCompare, Lightbulb
} from 'lucide-react';
import {
  LineChart, Line, XAxis, YAxis, CartesianGrid, Tooltip, Legend,
  ResponsiveContainer, ReferenceLine
} from 'recharts';

// Available metrics for comparison
const availableMetrics = [
  { id: 'gross_margin', name: 'Margen Bruto', category: 'margins', icon: TrendingUp, color: '#22c55e' },
  { id: 'ebitda_margin', name: 'Margen EBITDA', category: 'margins', icon: Activity, color: '#3b82f6' },
  { id: 'operating_margin', name: 'Margen Operativo', category: 'margins', icon: Calculator, color: '#8b5cf6' },
  { id: 'net_margin', name: 'Margen Neto', category: 'margins', icon: Target, color: '#f59e0b' },
  { id: 'roic', name: 'ROIC', category: 'returns', icon: TrendingUp, color: '#ef4444' },
  { id: 'roe', name: 'ROE', category: 'returns', icon: Target, color: '#06b6d4' },
  { id: 'roa', name: 'ROA', category: 'returns', icon: Building2, color: '#84cc16' },
  { id: 'current_ratio', name: 'Razón Circulante', category: 'liquidity', icon: Scale, color: '#f97316' },
  { id: 'quick_ratio', name: 'Prueba Ácida', category: 'liquidity', icon: Activity, color: '#14b8a6' },
  { id: 'debt_to_equity', name: 'Deuda/Capital', category: 'solvency', icon: Scale, color: '#ec4899' },
  { id: 'interest_coverage', name: 'Cobertura de Intereses', category: 'solvency', icon: Activity, color: '#6366f1' },
];

// Metric definitions (simplified from MetricDetail.js)
const metricDefinitions = {
  gross_margin: {
    formula: { numerator: 'Utilidad Bruta', denominator: 'Ingresos' },
    whatMeasures: 'Rentabilidad después de costos directos',
    goodRange: '> 30%',
    interpretation: 'Poder de precio y eficiencia en producción'
  },
  ebitda_margin: {
    formula: { numerator: 'EBITDA', denominator: 'Ingresos' },
    whatMeasures: 'Rentabilidad operativa antes de depreciación',
    goodRange: '> 15%',
    interpretation: 'Eficiencia operativa pura'
  },
  operating_margin: {
    formula: { numerator: 'Utilidad Operativa', denominator: 'Ingresos' },
    whatMeasures: 'Rentabilidad del negocio core',
    goodRange: '> 10%',
    interpretation: 'Eficiencia después de todos los gastos operativos'
  },
  net_margin: {
    formula: { numerator: 'Utilidad Neta', denominator: 'Ingresos' },
    whatMeasures: 'Rentabilidad final después de todo',
    goodRange: '> 5%',
    interpretation: 'Lo que realmente queda para accionistas'
  },
  roic: {
    formula: { numerator: 'NOPAT', denominator: 'Capital Invertido' },
    whatMeasures: 'Retorno sobre capital total invertido',
    goodRange: '> 15%',
    interpretation: 'Creación de valor vs costo de capital'
  },
  roe: {
    formula: { numerator: 'Utilidad Neta', denominator: 'Capital Contable' },
    whatMeasures: 'Retorno para accionistas',
    goodRange: '> 15%',
    interpretation: 'Eficiencia del capital de los dueños'
  },
  roa: {
    formula: { numerator: 'Utilidad Neta', denominator: 'Activos Totales' },
    whatMeasures: 'Retorno sobre activos totales',
    goodRange: '> 5%',
    interpretation: 'Eficiencia en uso de activos'
  },
  current_ratio: {
    formula: { numerator: 'Activo Circulante', denominator: 'Pasivo Circulante' },
    whatMeasures: 'Liquidez de corto plazo',
    goodRange: '1.5 - 3.0x',
    interpretation: 'Capacidad de pago inmediata'
  },
  quick_ratio: {
    formula: { numerator: 'Activo Circulante - Inventarios', denominator: 'Pasivo Circulante' },
    whatMeasures: 'Liquidez sin inventarios',
    goodRange: '> 1.0x',
    interpretation: 'Liquidez más conservadora'
  },
  debt_to_equity: {
    formula: { numerator: 'Pasivo Total', denominator: 'Capital Contable' },
    whatMeasures: 'Nivel de apalancamiento',
    goodRange: '< 1.0x',
    interpretation: 'Riesgo financiero por deuda'
  },
  interest_coverage: {
    formula: { numerator: 'EBIT', denominator: 'Gastos por Intereses' },
    whatMeasures: 'Capacidad de pagar intereses',
    goodRange: '> 5x',
    interpretation: 'Holgura para servicio de deuda'
  }
};

// Predefined comparison pairs with insights
const suggestedComparisons = [
  {
    metric1: 'roe',
    metric2: 'roic',
    title: 'ROE vs ROIC',
    insight: 'Si ROE > ROIC, el apalancamiento está amplificando retornos. Si ROIC > ROE, la deuda está destruyendo valor.',
    analysis: 'DuPont Analysis: ROE = ROA × Apalancamiento'
  },
  {
    metric1: 'gross_margin',
    metric2: 'net_margin',
    title: 'Margen Bruto vs Neto',
    insight: 'La diferencia revela el "costo de operar": gastos operativos, financieros e impuestos.',
    analysis: 'Cascada de márgenes: Bruto → Operativo → EBITDA → Neto'
  },
  {
    metric1: 'roic',
    metric2: 'roa',
    title: 'ROIC vs ROA',
    insight: 'ROIC excluye efectivo ocioso. Si ROA << ROIC, la empresa tiene exceso de liquidez.',
    analysis: 'Eficiencia de capital vs uso de activos'
  },
  {
    metric1: 'current_ratio',
    metric2: 'quick_ratio',
    title: 'Liquidez vs Prueba Ácida',
    insight: 'Si Current >> Quick, los inventarios dominan. Riesgo si inventarios son de lenta rotación.',
    analysis: 'Calidad de la liquidez'
  },
  {
    metric1: 'debt_to_equity',
    metric2: 'interest_coverage',
    title: 'Deuda vs Cobertura',
    insight: 'Alto D/E con alta cobertura = deuda manejable. Alto D/E con baja cobertura = riesgo.',
    analysis: 'Capacidad real de servicio de deuda'
  },
  {
    metric1: 'operating_margin',
    metric2: 'ebitda_margin',
    title: 'Margen Operativo vs EBITDA',
    insight: 'La diferencia = Depreciación + Amortización. Alta diferencia indica activos intensivos.',
    analysis: 'Intensidad de capital del negocio'
  }
];

const MetricCompare = () => {
  const navigate = useNavigate();
  const [searchParams, setSearchParams] = useSearchParams();
  
  const [metric1Id, setMetric1Id] = useState(searchParams.get('m1') || 'roe');
  const [metric2Id, setMetric2Id] = useState(searchParams.get('m2') || 'roic');
  const [historicalData, setHistoricalData] = useState([]);
  const [currentValues, setCurrentValues] = useState({ metric1: null, metric2: null });
  const [loading, setLoading] = useState(true);

  const metric1 = availableMetrics.find(m => m.id === metric1Id);
  const metric2 = availableMetrics.find(m => m.id === metric2Id);
  const metric1Def = metricDefinitions[metric1Id];
  const metric2Def = metricDefinitions[metric2Id];

  // Find if this is a suggested comparison
  const suggestedPair = suggestedComparisons.find(
    s => (s.metric1 === metric1Id && s.metric2 === metric2Id) ||
         (s.metric1 === metric2Id && s.metric2 === metric1Id)
  );

  useEffect(() => {
    loadComparisonData();
    // Update URL params
    setSearchParams({ m1: metric1Id, m2: metric2Id });
  }, [metric1Id, metric2Id]);

  const loadComparisonData = async () => {
    setLoading(true);
    try {
      // Get periods
      const periodsRes = await api.get('/financial-statements/periods');
      const periods = periodsRes.data || [];
      
      if (periods.length === 0) {
        setLoading(false);
        return;
      }

      // Get metrics for each period
      const historicalPromises = periods.slice(0, 6).map(async (p) => {
        try {
          const res = await api.get(`/financial-statements/metrics/${p.periodo}`);
          const metrics = res.data?.metrics;
          
          // Find values in appropriate category
          let val1 = null, val2 = null;
          
          for (const category of Object.values(metrics || {})) {
            if (category[metric1Id]) val1 = category[metric1Id].value;
            if (category[metric2Id]) val2 = category[metric2Id].value;
          }
          
          return {
            periodo: p.periodo,
            [metric1Id]: val1,
            [metric2Id]: val2
          };
        } catch {
          return { periodo: p.periodo, [metric1Id]: null, [metric2Id]: null };
        }
      });

      const historical = await Promise.all(historicalPromises);
      setHistoricalData(historical.reverse());

      // Set current values from most recent period
      if (historical.length > 0) {
        const latest = historical[historical.length - 1];
        setCurrentValues({
          metric1: latest[metric1Id],
          metric2: latest[metric2Id]
        });
      }

    } catch (error) {
      console.error('Error loading comparison data:', error);
      toast.error('Error cargando datos de comparación');
    } finally {
      setLoading(false);
    }
  };

  const formatValue = (val, metricId) => {
    if (val === null || val === undefined) return 'N/A';
    const isRatio = ['current_ratio', 'quick_ratio', 'debt_to_equity', 'interest_coverage', 'debt_to_ebitda'].includes(metricId);
    if (isRatio) return `${val.toFixed(2)}x`;
    return `${val.toFixed(1)}%`;
  };

  const getValueColor = (val, metricId) => {
    if (val === null) return 'text-gray-400';
    
    // Simple thresholds
    const thresholds = {
      gross_margin: { good: 30, bad: 15 },
      ebitda_margin: { good: 15, bad: 5 },
      operating_margin: { good: 10, bad: 3 },
      net_margin: { good: 5, bad: 0 },
      roic: { good: 15, bad: 5 },
      roe: { good: 15, bad: 5 },
      roa: { good: 5, bad: 2 },
      current_ratio: { good: 1.5, bad: 1 },
      quick_ratio: { good: 1, bad: 0.5 },
      debt_to_equity: { good: 0.5, bad: 2, inverse: true },
      interest_coverage: { good: 5, bad: 2 }
    };
    
    const t = thresholds[metricId];
    if (!t) return 'text-gray-700';
    
    if (t.inverse) {
      if (val <= t.good) return 'text-green-600';
      if (val >= t.bad) return 'text-red-600';
      return 'text-yellow-600';
    } else {
      if (val >= t.good) return 'text-green-600';
      if (val <= t.bad) return 'text-red-600';
      return 'text-yellow-600';
    }
  };

  const swapMetrics = () => {
    setMetric1Id(metric2Id);
    setMetric2Id(metric1Id);
  };

  const selectSuggestedComparison = (comp) => {
    setMetric1Id(comp.metric1);
    setMetric2Id(comp.metric2);
  };

  return (
    <div className="min-h-screen bg-gradient-to-br from-slate-50 to-indigo-50">
      {/* Header */}
      <div className="bg-white border-b border-gray-200 sticky top-0 z-10">
        <div className="max-w-7xl mx-auto px-6 py-4 flex items-center justify-between">
          <div className="flex items-center gap-4">
            <GitCompare className="w-7 h-7 text-indigo-600" />
            <div>
              <h1 className="text-2xl font-bold text-gray-900">Comparar Métricas</h1>
              <p className="text-sm text-gray-500">Análisis lado a lado de indicadores financieros</p>
            </div>
          </div>
          <Button variant="outline" onClick={() => navigate('/financial-metrics')}>
            <ArrowLeft className="w-4 h-4 mr-2" />
            Volver a métricas
          </Button>
        </div>
      </div>

      <div className="max-w-7xl mx-auto px-6 py-8">
        {/* Metric Selectors */}
        <Card className="mb-6">
          <CardContent className="p-6">
            <div className="flex flex-col md:flex-row items-center gap-4">
              {/* Metric 1 Selector */}
              <div className="flex-1 w-full">
                <label className="block text-sm font-medium text-gray-700 mb-2">Métrica 1</label>
                <Select value={metric1Id} onValueChange={setMetric1Id}>
                  <SelectTrigger className="w-full">
                    <SelectValue placeholder="Seleccionar métrica" />
                  </SelectTrigger>
                  <SelectContent>
                    {availableMetrics.map(m => (
                      <SelectItem key={m.id} value={m.id} disabled={m.id === metric2Id}>
                        <div className="flex items-center gap-2">
                          <div className="w-3 h-3 rounded-full" style={{ backgroundColor: m.color }} />
                          {m.name}
                        </div>
                      </SelectItem>
                    ))}
                  </SelectContent>
                </Select>
              </div>

              {/* Swap Button */}
              <button
                onClick={swapMetrics}
                className="p-3 rounded-full bg-indigo-100 hover:bg-indigo-200 transition-colors mt-6 md:mt-0"
                title="Intercambiar métricas"
              >
                <RefreshCw className="w-5 h-5 text-indigo-600" />
              </button>

              {/* Metric 2 Selector */}
              <div className="flex-1 w-full">
                <label className="block text-sm font-medium text-gray-700 mb-2">Métrica 2</label>
                <Select value={metric2Id} onValueChange={setMetric2Id}>
                  <SelectTrigger className="w-full">
                    <SelectValue placeholder="Seleccionar métrica" />
                  </SelectTrigger>
                  <SelectContent>
                    {availableMetrics.map(m => (
                      <SelectItem key={m.id} value={m.id} disabled={m.id === metric1Id}>
                        <div className="flex items-center gap-2">
                          <div className="w-3 h-3 rounded-full" style={{ backgroundColor: m.color }} />
                          {m.name}
                        </div>
                      </SelectItem>
                    ))}
                  </SelectContent>
                </Select>
              </div>
            </div>

            {/* Suggested Comparisons */}
            <div className="mt-6 pt-6 border-t">
              <p className="text-sm font-medium text-gray-700 mb-3">Comparaciones sugeridas:</p>
              <div className="flex flex-wrap gap-2">
                {suggestedComparisons.map((comp, idx) => (
                  <button
                    key={idx}
                    onClick={() => selectSuggestedComparison(comp)}
                    className={`px-3 py-1.5 rounded-full text-sm font-medium transition-colors ${
                      (metric1Id === comp.metric1 && metric2Id === comp.metric2) ||
                      (metric1Id === comp.metric2 && metric2Id === comp.metric1)
                        ? 'bg-indigo-600 text-white'
                        : 'bg-gray-100 text-gray-700 hover:bg-indigo-100'
                    }`}
                  >
                    {comp.title}
                  </button>
                ))}
              </div>
            </div>
          </CardContent>
        </Card>

        {/* Comparison Cards */}
        <div className="grid grid-cols-1 md:grid-cols-2 gap-6 mb-6">
          {/* Metric 1 Card */}
          <Card className="overflow-hidden">
            <div className="h-2" style={{ backgroundColor: metric1?.color }} />
            <CardHeader className="pb-2">
              <div className="flex items-center gap-3">
                {metric1 && <metric1.icon className="w-6 h-6" style={{ color: metric1.color }} />}
                <div>
                  <CardTitle className="text-lg">{metric1?.name}</CardTitle>
                  <p className="text-xs text-gray-500 capitalize">{metric1?.category}</p>
                </div>
              </div>
            </CardHeader>
            <CardContent>
              <div className="text-center py-4">
                <p className={`text-5xl font-bold ${getValueColor(currentValues.metric1, metric1Id)}`}>
                  {formatValue(currentValues.metric1, metric1Id)}
                </p>
                <p className="text-sm text-gray-500 mt-2">Valor actual</p>
              </div>
              
              {/* Formula */}
              {metric1Def && (
                <div className="mt-4 p-4 bg-gray-50 rounded-lg">
                  <div className="text-center">
                    <p className="text-sm font-mono" style={{ color: metric1?.color }}>
                      {metric1Def.formula.numerator}
                    </p>
                    <div className="border-t border-gray-300 my-1 w-3/4 mx-auto" />
                    <p className="text-sm font-mono" style={{ color: metric1?.color }}>
                      {metric1Def.formula.denominator}
                    </p>
                  </div>
                  <p className="text-xs text-center text-gray-500 mt-3">{metric1Def.whatMeasures}</p>
                  <div className="mt-2 text-center">
                    <span className="inline-block px-2 py-1 bg-green-100 text-green-700 text-xs rounded-full">
                      Meta: {metric1Def.goodRange}
                    </span>
                  </div>
                </div>
              )}
              
              <Button 
                variant="outline" 
                className="w-full mt-4"
                onClick={() => navigate(`/metrics/${metric1Id}`)}
              >
                Ver detalle completo
                <ChevronRight className="w-4 h-4 ml-2" />
              </Button>
            </CardContent>
          </Card>

          {/* Metric 2 Card */}
          <Card className="overflow-hidden">
            <div className="h-2" style={{ backgroundColor: metric2?.color }} />
            <CardHeader className="pb-2">
              <div className="flex items-center gap-3">
                {metric2 && <metric2.icon className="w-6 h-6" style={{ color: metric2.color }} />}
                <div>
                  <CardTitle className="text-lg">{metric2?.name}</CardTitle>
                  <p className="text-xs text-gray-500 capitalize">{metric2?.category}</p>
                </div>
              </div>
            </CardHeader>
            <CardContent>
              <div className="text-center py-4">
                <p className={`text-5xl font-bold ${getValueColor(currentValues.metric2, metric2Id)}`}>
                  {formatValue(currentValues.metric2, metric2Id)}
                </p>
                <p className="text-sm text-gray-500 mt-2">Valor actual</p>
              </div>
              
              {/* Formula */}
              {metric2Def && (
                <div className="mt-4 p-4 bg-gray-50 rounded-lg">
                  <div className="text-center">
                    <p className="text-sm font-mono" style={{ color: metric2?.color }}>
                      {metric2Def.formula.numerator}
                    </p>
                    <div className="border-t border-gray-300 my-1 w-3/4 mx-auto" />
                    <p className="text-sm font-mono" style={{ color: metric2?.color }}>
                      {metric2Def.formula.denominator}
                    </p>
                  </div>
                  <p className="text-xs text-center text-gray-500 mt-3">{metric2Def.whatMeasures}</p>
                  <div className="mt-2 text-center">
                    <span className="inline-block px-2 py-1 bg-green-100 text-green-700 text-xs rounded-full">
                      Meta: {metric2Def.goodRange}
                    </span>
                  </div>
                </div>
              )}
              
              <Button 
                variant="outline" 
                className="w-full mt-4"
                onClick={() => navigate(`/metrics/${metric2Id}`)}
              >
                Ver detalle completo
                <ChevronRight className="w-4 h-4 ml-2" />
              </Button>
            </CardContent>
          </Card>
        </div>

        {/* Trend Chart */}
        <Card className="mb-6">
          <CardHeader>
            <CardTitle className="flex items-center gap-2">
              <BarChart3 className="w-5 h-5 text-indigo-600" />
              Tendencia Histórica Comparada
            </CardTitle>
          </CardHeader>
          <CardContent>
            {loading ? (
              <div className="h-64 flex items-center justify-center">
                <RefreshCw className="w-8 h-8 text-gray-400 animate-spin" />
              </div>
            ) : historicalData.length > 0 ? (
              <ResponsiveContainer width="100%" height={300}>
                <LineChart data={historicalData} margin={{ top: 20, right: 30, left: 20, bottom: 5 }}>
                  <CartesianGrid strokeDasharray="3 3" stroke="#e5e7eb" />
                  <XAxis dataKey="periodo" tick={{ fontSize: 12 }} />
                  <YAxis 
                    tickFormatter={(val) => `${val}%`}
                    tick={{ fontSize: 12 }}
                  />
                  <Tooltip 
                    formatter={(val, name) => {
                      const isRatio = ['current_ratio', 'quick_ratio', 'debt_to_equity', 'interest_coverage'].includes(name);
                      return [isRatio ? `${val?.toFixed(2)}x` : `${val?.toFixed(1)}%`, 
                              name === metric1Id ? metric1?.name : metric2?.name];
                    }}
                    labelFormatter={(label) => `Período: ${label}`}
                  />
                  <Legend 
                    formatter={(value) => value === metric1Id ? metric1?.name : metric2?.name}
                  />
                  <Line 
                    type="monotone" 
                    dataKey={metric1Id} 
                    stroke={metric1?.color} 
                    strokeWidth={3}
                    dot={{ r: 5 }}
                    activeDot={{ r: 8 }}
                  />
                  <Line 
                    type="monotone" 
                    dataKey={metric2Id} 
                    stroke={metric2?.color} 
                    strokeWidth={3}
                    dot={{ r: 5 }}
                    activeDot={{ r: 8 }}
                  />
                </LineChart>
              </ResponsiveContainer>
            ) : (
              <div className="h-64 flex items-center justify-center text-gray-500">
                No hay datos históricos disponibles
              </div>
            )}
          </CardContent>
        </Card>

        {/* Insight Card (if suggested comparison) */}
        {suggestedPair && (
          <Card className="bg-gradient-to-r from-indigo-50 to-purple-50 border-indigo-200">
            <CardContent className="p-6">
              <div className="flex gap-4">
                <div className="w-12 h-12 bg-indigo-100 rounded-full flex items-center justify-center flex-shrink-0">
                  <Lightbulb className="w-6 h-6 text-indigo-600" />
                </div>
                <div>
                  <h3 className="font-semibold text-gray-900 mb-2">Análisis: {suggestedPair.title}</h3>
                  <p className="text-gray-700 mb-3">{suggestedPair.insight}</p>
                  <div className="flex items-center gap-2 text-sm text-indigo-700">
                    <Activity className="w-4 h-4" />
                    <span className="font-medium">{suggestedPair.analysis}</span>
                  </div>
                  
                  {/* Dynamic insight based on values */}
                  {currentValues.metric1 !== null && currentValues.metric2 !== null && (
                    <div className="mt-4 p-3 bg-white/50 rounded-lg">
                      <p className="text-sm text-gray-700">
                        <span className="font-semibold">Tu situación:</span>{' '}
                        {metric1Id === 'roe' && metric2Id === 'roic' ? (
                          currentValues.metric1 > currentValues.metric2 
                            ? `ROE (${formatValue(currentValues.metric1, 'roe')}) > ROIC (${formatValue(currentValues.metric2, 'roic')}): El apalancamiento está amplificando los retornos.`
                            : `ROIC (${formatValue(currentValues.metric2, 'roic')}) > ROE (${formatValue(currentValues.metric1, 'roe')}): La empresa no está maximizando el apalancamiento.`
                        ) : metric1Id === 'gross_margin' && metric2Id === 'net_margin' ? (
                          `Diferencia de ${(currentValues.metric1 - currentValues.metric2).toFixed(1)}% entre Margen Bruto y Neto. ${
                            (currentValues.metric1 - currentValues.metric2) > 30 
                              ? 'Alta carga operativa/financiera.' 
                              : 'Buena eficiencia en gastos.'
                          }`
                        ) : (
                          `${metric1?.name}: ${formatValue(currentValues.metric1, metric1Id)} vs ${metric2?.name}: ${formatValue(currentValues.metric2, metric2Id)}`
                        )}
                      </p>
                    </div>
                  )}
                </div>
              </div>
            </CardContent>
          </Card>
        )}

        {/* Quick Stats */}
        <div className="grid grid-cols-2 md:grid-cols-4 gap-4 mt-6">
          <Card className="p-4">
            <p className="text-xs text-gray-500 uppercase">Diferencia</p>
            <p className="text-2xl font-bold text-gray-900">
              {currentValues.metric1 !== null && currentValues.metric2 !== null
                ? `${Math.abs(currentValues.metric1 - currentValues.metric2).toFixed(1)}%`
                : 'N/A'}
            </p>
          </Card>
          <Card className="p-4">
            <p className="text-xs text-gray-500 uppercase">Ratio</p>
            <p className="text-2xl font-bold text-gray-900">
              {currentValues.metric1 !== null && currentValues.metric2 !== null && currentValues.metric2 !== 0
                ? `${(currentValues.metric1 / currentValues.metric2).toFixed(2)}x`
                : 'N/A'}
            </p>
          </Card>
          <Card className="p-4">
            <p className="text-xs text-gray-500 uppercase">{metric1?.name} Status</p>
            <div className={`text-lg font-bold ${getValueColor(currentValues.metric1, metric1Id)}`}>
              {currentValues.metric1 !== null ? (
                currentValues.metric1 >= (metricDefinitions[metric1Id]?.goodRange?.includes('>') 
                  ? parseFloat(metricDefinitions[metric1Id].goodRange.replace(/[>%x\s]/g, ''))
                  : 10) ? 'Saludable' : 'Atención'
              ) : 'N/A'}
            </div>
          </Card>
          <Card className="p-4">
            <p className="text-xs text-gray-500 uppercase">{metric2?.name} Status</p>
            <div className={`text-lg font-bold ${getValueColor(currentValues.metric2, metric2Id)}`}>
              {currentValues.metric2 !== null ? (
                currentValues.metric2 >= (metricDefinitions[metric2Id]?.goodRange?.includes('>') 
                  ? parseFloat(metricDefinitions[metric2Id].goodRange.replace(/[>%x\s]/g, ''))
                  : 10) ? 'Saludable' : 'Atención'
              ) : 'N/A'}
            </div>
          </Card>
        </div>
      </div>
    </div>
  );
};

export default MetricCompare;
