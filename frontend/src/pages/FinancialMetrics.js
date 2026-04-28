import React, { useState, useEffect } from 'react';
import { Card, CardContent, CardHeader, CardTitle, CardDescription } from '../components/ui/card';
import { Button } from '../components/ui/button';
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from '../components/ui/select';
import { Dialog, DialogContent, DialogHeader, DialogTitle, DialogTrigger, DialogFooter, DialogDescription } from '../components/ui/dialog';
import { Tabs, TabsContent, TabsList, TabsTrigger } from '../components/ui/tabs';
import { Label } from '../components/ui/label';
import { Input } from '../components/ui/input';
import { toast } from 'sonner';
import api from '../api/axios';
import { 
  TrendingUp, TrendingDown, Upload, FileSpreadsheet, Calendar, 
  DollarSign, Percent, Activity, BarChart3, PieChart, RefreshCw,
  Target, Wallet, Building2, ChevronRight, Info, Trash2,
  ArrowUpRight, ArrowDownRight, Minus, Calculator, Scale, Globe,
  ChevronDown, ChevronUp, BookOpen, Bell
} from 'lucide-react';
import { Tooltip as ShadcnTooltip, TooltipTrigger, TooltipContent, TooltipProvider } from '../components/ui/tooltip';
import { 
  BarChart, Bar, LineChart, Line, XAxis, YAxis, CartesianGrid, 
  Tooltip, Legend, ResponsiveContainer, ComposedChart, Area,
  RadarChart, PolarGrid, PolarAngleAxis, PolarRadiusAxis, Radar
} from 'recharts';
import { financialTranslations, languages } from '../utils/financialTranslations';
import MetricEncyclopedia from './MetricEncyclopedia';
import KpiAlertConfig from './KpiAlertConfig';

const FinancialMetrics = () => {
  const [language, setLanguage] = useState('es');
  const [periods, setPeriods] = useState([]);
  const [selectedPeriod, setSelectedPeriod] = useState('');
  const [metrics, setMetrics] = useState(null);
  const [prevMetrics, setPrevMetrics] = useState(null);
  const [prevPeriod, setPrevPeriod] = useState('');
  const [loading, setLoading] = useState(false);
  const [uploadDialogOpen, setUploadDialogOpen] = useState(false);
  const [uploadType, setUploadType] = useState('');
  const [uploadPeriodo, setUploadPeriodo] = useState('');
  const [uploading, setUploading] = useState(false);
  
  const t = financialTranslations[language];

  useEffect(() => {
    loadPeriods();
  }, []);

  useEffect(() => {
    if (selectedPeriod) {
      loadMetrics(selectedPeriod);
    }
  }, [selectedPeriod]);

  const loadPeriods = async () => {
    try {
      const response = await api.get('/financial-statements/periods');
      setPeriods(response.data || []);
      if (response.data && response.data.length > 0) {
        setSelectedPeriod(response.data[0].periodo);
      }
    } catch (error) {
      console.error('Error loading periods:', error);
    }
  };

  const loadMetrics = async (periodo) => {
    setLoading(true);
    try {
      const response = await api.get(`/financial-statements/metrics/${periodo}`);
      setMetrics(response.data);
      
      // Find and load previous period for trend comparison
      const currentIdx = periods.findIndex(p => p.periodo === periodo);
      if (currentIdx >= 0 && currentIdx < periods.length - 1) {
        const prev = periods[currentIdx + 1].periodo;
        setPrevPeriod(prev);
        try {
          const prevRes = await api.get(`/financial-statements/metrics/${prev}`);
          setPrevMetrics(prevRes.data);
        } catch { setPrevMetrics(null); }
      } else {
        setPrevMetrics(null);
        setPrevPeriod('');
      }
    } catch (error) {
      if (error.response?.status === 404) {
        setMetrics(null);
      } else {
        toast.error(t.errorLoadingMetrics);
      }
    } finally {
      setLoading(false);
    }
  };

  const handleFileUpload = async (e) => {
    const file = e.target.files?.[0];
    if (!file || !uploadPeriodo) {
      toast.error(t.selectFileAndPeriod);
      return;
    }

    setUploading(true);
    const formData = new FormData();
    formData.append('file', file);

    const endpoint = uploadType === 'income' 
      ? `/financial-statements/upload/income-statement?periodo=${uploadPeriodo}`
      : `/financial-statements/upload/balance-sheet?periodo=${uploadPeriodo}`;

    try {
      await api.post(endpoint, formData, {
        headers: { 'Content-Type': 'multipart/form-data' }
      });
      toast.success(uploadType === 'income' ? t.incomeStatementUploaded : t.balanceSheetUploaded);
      setUploadDialogOpen(false);
      loadPeriods();
      if (uploadPeriodo === selectedPeriod) {
        loadMetrics(selectedPeriod);
      }
    } catch (error) {
      toast.error(error.response?.data?.detail || t.errorUploadingFile);
    } finally {
      setUploading(false);
    }
  };

  const handleDeletePeriod = async (periodo) => {
    if (!window.confirm(`${t.confirmDeletePeriod} ${periodo}?`)) return;
    try {
      await api.delete(`/financial-statements/${periodo}`);
      toast.success(t.periodDeleted);
      loadPeriods();
      if (periodo === selectedPeriod) {
        setMetrics(null);
        setSelectedPeriod('');
      }
    } catch (error) {
      toast.error(t.errorDeleting);
    }
  };

  const formatCurrency = (value) => {
    if (value === undefined || value === null) return '$0';
    return new Intl.NumberFormat('es-MX', {
      style: 'currency',
      currency: 'MXN',
      minimumFractionDigits: 0,
      maximumFractionDigits: 0
    }).format(value);
  };

  const formatPercent = (value) => {
    if (value === undefined || value === null) return '0%';
    return `${value.toFixed(1)}%`;
  };

  const formatNumber = (value, decimals = 2) => {
    if (value === undefined || value === null) return '0';
    return value.toFixed(decimals);
  };

  const getMetricColor = (value, thresholds) => {
    if (!thresholds) return 'text-gray-900';
    if (value >= thresholds.good) return 'text-green-600';
    if (value >= thresholds.warning) return 'text-amber-600';
    return 'text-red-600';
  };

  const getMetricBg = (value, thresholds) => {
    if (!thresholds) return 'bg-gray-50';
    if (value >= thresholds.good) return 'bg-green-50';
    if (value >= thresholds.warning) return 'bg-amber-50';
    return 'bg-red-50';
  };

  const [expandedMetric, setExpandedMetric] = useState(null);

  const formatCompValue = (v) => {
    if (v === undefined || v === null) return '$0';
    if (Math.abs(v) >= 1_000_000) return `$${(v / 1_000_000).toFixed(2)}M`;
    if (Math.abs(v) >= 1_000) return `$${(v / 1_000).toFixed(1)}K`;
    return `$${v.toLocaleString('es-MX', { maximumFractionDigits: 2 })}`;
  };

  const MetricCard = ({ metric, icon: Icon, thresholds, isPercent = true, suffix = '%', metricKey }) => {
    const value = metric?.value ?? 0;
    const color = getMetricColor(value, thresholds);
    const bg = getMetricBg(value, thresholds);
    const isExpanded = expandedMetric === metricKey;
    const hasComponents = metric?.components?.length > 0;
    
    return (
      <TooltipProvider delayDuration={300}>
        <ShadcnTooltip>
          <TooltipTrigger asChild>
            <div 
              className={`p-4 rounded-lg ${bg} border cursor-pointer transition-all duration-200 hover:shadow-md hover:scale-[1.02] ${isExpanded ? 'ring-2 ring-blue-300' : ''}`}
              onClick={() => hasComponents && setExpandedMetric(isExpanded ? null : metricKey)}
              data-testid={`metric-card-${metricKey}`}
            >
              <div className="flex items-start justify-between">
                <div className="flex-1 min-w-0">
                  <p className="text-xs font-medium text-gray-500 uppercase tracking-wider">{metric?.label}</p>
                  <p className={`text-2xl font-bold mt-1 ${color}`}>
                    {isPercent ? formatPercent(value) : formatNumber(value, 2)}{!isPercent && suffix !== '%' ? suffix : ''}
                  </p>
                </div>
                <div className="flex items-center gap-1">
                  <Icon className={`w-5 h-5 ${color}`} />
                  {hasComponents && (
                    isExpanded ? <ChevronUp className="w-3 h-3 text-gray-400" /> : <ChevronDown className="w-3 h-3 text-gray-400" />
                  )}
                </div>
              </div>
              <p className="text-xs text-gray-500 mt-2 line-clamp-2">{metric?.interpretation}</p>
              
              {isExpanded && hasComponents && (
                <div className="mt-3 pt-3 border-t border-gray-200 space-y-2 animate-in slide-in-from-top-2 duration-200" data-testid={`metric-breakdown-${metricKey}`}>
                  <p className="text-xs font-semibold text-gray-700 flex items-center gap-1">
                    <Calculator className="w-3 h-3" /> {metric?.formula}
                  </p>
                  <div className="space-y-1">
                    {metric.components.map((comp, idx) => (
                      <div key={idx} className="flex justify-between items-center text-xs">
                        <span className="text-gray-600">{comp.label}</span>
                        <span className="font-mono font-semibold text-gray-800">{formatCompValue(comp.value)}</span>
                      </div>
                    ))}
                  </div>
                  <div className="flex justify-between items-center text-xs pt-1 border-t border-dashed border-gray-300">
                    <span className="font-semibold text-gray-700">Resultado</span>
                    <span className={`font-mono font-bold ${color}`}>
                      {isPercent ? formatPercent(value) : formatNumber(value, 2)}{!isPercent && suffix !== '%' ? suffix : ''}
                    </span>
                  </div>
                </div>
              )}
            </div>
          </TooltipTrigger>
          <TooltipContent side="top" className="max-w-xs bg-gray-900 text-white px-3 py-2">
            <p className="font-semibold text-xs">{metric?.formula}</p>
            <p className="text-xs opacity-80 mt-0.5">Clic para ver desglose</p>
          </TooltipContent>
        </ShadcnTooltip>
      </TooltipProvider>
    );
  };

  const ValueCard = ({ label, value, icon: Icon, color = 'blue' }) => {
    const colors = {
      blue: 'bg-blue-50 text-blue-600 border-blue-100',
      green: 'bg-green-50 text-green-600 border-green-100',
      red: 'bg-red-50 text-red-600 border-red-100',
      amber: 'bg-amber-50 text-amber-600 border-amber-100',
      purple: 'bg-purple-50 text-purple-600 border-purple-100',
    };
    
    return (
      <div className={`p-4 rounded-lg border ${colors[color]}`}>
        <div className="flex items-center justify-between">
          <p className="text-xs font-medium uppercase tracking-wider opacity-80">{label}</p>
          <Icon className="w-4 h-4" />
        </div>
        <p className="text-xl font-bold mt-2">{formatCurrency(value)}</p>
      </div>
    );
  };

  // Prepare chart data for margins
  const marginsChartData = metrics?.metrics?.margins ? [
    { name: 'Margen Bruto', value: metrics.metrics.margins.gross_margin?.value || 0 },
    { name: 'Margen EBITDA', value: metrics.metrics.margins.ebitda_margin?.value || 0 },
    { name: 'Margen Operativo', value: metrics.metrics.margins.operating_margin?.value || 0 },
    { name: 'Margen Neto', value: metrics.metrics.margins.net_margin?.value || 0 },
  ] : [];

  // Prepare radar data for comprehensive view
  const radarData = metrics?.metrics ? [
    { metric: 'Margen Bruto', value: Math.min(metrics.metrics.margins?.gross_margin?.value || 0, 100) },
    { metric: 'ROE', value: Math.min(metrics.metrics.returns?.roe?.value || 0, 100) },
    { metric: 'ROIC', value: Math.min(metrics.metrics.returns?.roic?.value || 0, 100) },
    { metric: 'Liquidez', value: Math.min((metrics.metrics.liquidity?.current_ratio?.value || 0) * 50, 100) },
    { metric: 'Cobertura Int.', value: Math.min((metrics.metrics.solvency?.interest_coverage?.value || 0) * 20, 100) },
  ] : [];

  // Get current date for default period
  const getCurrentPeriod = () => {
    const now = new Date();
    return `${now.getFullYear()}-${String(now.getMonth() + 1).padStart(2, '0')}`;
  };

  return (
    <div className="p-6 space-y-6 bg-gray-50 min-h-screen" data-testid="financial-metrics-page">
      {/* Header */}
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-bold text-gray-900">{t.financialMetrics}</h1>
          <p className="text-sm text-gray-500 mt-1">{t.financialAnalysis}</p>
        </div>
        <div className="flex items-center gap-3">
          {/* Language Selector */}
          <Select value={language} onValueChange={setLanguage}>
            <SelectTrigger className="w-36" data-testid="language-selector">
              <Globe className="w-4 h-4 mr-2" />
              <SelectValue />
            </SelectTrigger>
            <SelectContent>
              {languages.map(lang => (
                <SelectItem key={lang.code} value={lang.code}>
                  {lang.flag} {lang.name}
                </SelectItem>
              ))}
            </SelectContent>
          </Select>
          
          <Select value={selectedPeriod} onValueChange={setSelectedPeriod}>
            <SelectTrigger className="w-40" data-testid="period-selector">
              <SelectValue placeholder={t.period} />
            </SelectTrigger>
            <SelectContent>
              {periods.map((p) => (
                <SelectItem key={p.periodo} value={p.periodo}>
                  {p.periodo}
                  {p.has_income_statement && p.has_balance_sheet && ' ✓'}
                </SelectItem>
              ))}
            </SelectContent>
          </Select>

          <Dialog open={uploadDialogOpen} onOpenChange={setUploadDialogOpen}>
            <DialogTrigger asChild>
              <Button data-testid="upload-btn" className="gap-2">
                <Upload className="w-4 h-4" />
                {t.uploadExcel}
              </Button>
            </DialogTrigger>
            <DialogContent>
              <DialogHeader>
                <DialogTitle>{t.uploadStatement}</DialogTitle>
                <DialogDescription>
                  {t.uploadInstructions}
                </DialogDescription>
              </DialogHeader>
              <div className="space-y-4 py-4">
                <div className="space-y-2">
                  <Label>{t.conceptType}</Label>
                  <Select value={uploadType} onValueChange={setUploadType}>
                    <SelectTrigger data-testid="upload-type-selector">
                      <SelectValue placeholder={t.selectPeriod} />
                    </SelectTrigger>
                    <SelectContent>
                      <SelectItem value="income">{t.incomeStatement}</SelectItem>
                      <SelectItem value="balance">{t.balanceSheet}</SelectItem>
                    </SelectContent>
                  </Select>
                </div>
                <div className="space-y-2">
                  <Label>{t.period} (YYYY-MM)</Label>
                  <Input 
                    type="month"
                    value={uploadPeriodo}
                    onChange={(e) => setUploadPeriodo(e.target.value)}
                    data-testid="upload-period-input"
                  />
                </div>
                <div className="space-y-2">
                  <Label>{t.selectFile}</Label>
                  <Input 
                    type="file" 
                    accept=".xlsx,.xls"
                    onChange={handleFileUpload}
                    disabled={!uploadType || !uploadPeriodo || uploading}
                    data-testid="upload-file-input"
                  />
                </div>
              </div>
              <DialogFooter>
                <Button variant="outline" onClick={() => setUploadDialogOpen(false)}>
                  {t.cancel}
                </Button>
              </DialogFooter>
            </DialogContent>
          </Dialog>

          <Button 
            variant="outline" 
            size="icon"
            onClick={() => selectedPeriod && loadMetrics(selectedPeriod)}
            disabled={loading}
            data-testid="refresh-btn"
          >
            <RefreshCw className={`w-4 h-4 ${loading ? 'animate-spin' : ''}`} />
          </Button>
        </div>
      </div>

      {/* Main Tabs */}
      <Tabs defaultValue="metrics" className="w-full">
        <TabsList className="mb-4">
          <TabsTrigger value="metrics" className="gap-2" data-testid="tab-metrics">
            <BarChart3 className="w-4 h-4" />
            {t.financialMetrics || 'Métricas'}
          </TabsTrigger>
          <TabsTrigger value="encyclopedia" className="gap-2" data-testid="tab-encyclopedia">
            <BookOpen className="w-4 h-4" />
            Enciclopedia de Métricas
          </TabsTrigger>
          <TabsTrigger value="alerts" className="gap-2" data-testid="tab-alerts">
            <Bell className="w-4 h-4" />
            Alertas KPI
          </TabsTrigger>
        </TabsList>

        <TabsContent value="encyclopedia">
          <MetricEncyclopedia metricsData={metrics} selectedPeriod={selectedPeriod} prevMetricsData={prevMetrics} prevPeriod={prevPeriod} />
        </TabsContent>

        <TabsContent value="alerts">
          <KpiAlertConfig />
        </TabsContent>

        <TabsContent value="metrics" className="space-y-6">

      {/* Status Cards */}
      {periods.length > 0 && (
        <div className="grid grid-cols-1 md:grid-cols-4 gap-4">
          {periods.slice(0, 4).map((p) => (
            <Card key={p.periodo} className={`cursor-pointer transition-all ${selectedPeriod === p.periodo ? 'ring-2 ring-blue-500' : ''}`}
              onClick={() => setSelectedPeriod(p.periodo)}>
              <CardContent className="p-4">
                <div className="flex items-center justify-between">
                  <div>
                    <p className="font-semibold">{p.periodo}</p>
                    <div className="flex gap-2 mt-1">
                      <span className={`text-xs px-2 py-0.5 rounded ${p.has_income_statement ? 'bg-green-100 text-green-700' : 'bg-gray-100 text-gray-500'}`}>
                        {language === 'es' ? 'EdR' : language === 'pt' ? 'DRE' : 'IS'}
                      </span>
                      <span className={`text-xs px-2 py-0.5 rounded ${p.has_balance_sheet ? 'bg-blue-100 text-blue-700' : 'bg-gray-100 text-gray-500'}`}>
                        {language === 'es' ? 'BG' : language === 'pt' ? 'BP' : 'BS'}
                      </span>
                    </div>
                  </div>
                  <Button 
                    variant="ghost" 
                    size="icon" 
                    className="text-red-500 hover:text-red-700 hover:bg-red-50"
                    onClick={(e) => { e.stopPropagation(); handleDeletePeriod(p.periodo); }}
                  >
                    <Trash2 className="w-4 h-4" />
                  </Button>
                </div>
              </CardContent>
            </Card>
          ))}
        </div>
      )}

      {/* No data state */}
      {!metrics && !loading && (
        <Card>
          <CardContent className="py-12 text-center">
            <FileSpreadsheet className="w-12 h-12 mx-auto text-gray-400 mb-4" />
            <h3 className="text-lg font-medium text-gray-900">{t.noFinancialData}</h3>
            <p className="text-sm text-gray-500 mt-1 mb-4">
              {t.uploadIncomeStatement}
            </p>
            <Button onClick={() => setUploadDialogOpen(true)} className="gap-2">
              <Upload className="w-4 h-4" />
              {t.uploadExcel}
            </Button>
          </CardContent>
        </Card>
      )}

      {/* Loading state */}
      {loading && (
        <Card>
          <CardContent className="py-12 text-center">
            <RefreshCw className="w-8 h-8 mx-auto text-blue-500 animate-spin mb-4" />
            <p className="text-gray-500">{t.loading}</p>
          </CardContent>
        </Card>
      )}

      {/* Main content when data exists */}
      {metrics && !loading && (
        <>
          {/* Absolute Values - Summary */}
          <div className="grid grid-cols-2 md:grid-cols-4 lg:grid-cols-6 gap-4">
            <ValueCard label={t.revenue} value={metrics.metrics?.absolute_values?.ingresos} icon={DollarSign} color="green" />
            <ValueCard label={t.ebitda} value={metrics.metrics?.absolute_values?.ebitda} icon={TrendingUp} color="blue" />
            <ValueCard label={t.netProfit} value={metrics.metrics?.absolute_values?.utilidad_neta} icon={Target} color="purple" />
            <ValueCard label={t.totalAssets} value={metrics.metrics?.absolute_values?.activo_total} icon={Building2} color="amber" />
            <ValueCard label={t.totalLiabilities} value={metrics.metrics?.absolute_values?.pasivo_total} icon={Scale} color="red" />
            <ValueCard label={t.equity} value={metrics.metrics?.absolute_values?.capital_contable} icon={Wallet} color="green" />
          </div>

          {/* Charts Row */}
          <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
            {/* Margins Chart */}
            <Card>
              <CardHeader>
                <CardTitle className="text-base flex items-center gap-2">
                  <BarChart3 className="w-5 h-5 text-blue-500" />
                  {t.profitabilityMargins}
                </CardTitle>
              </CardHeader>
              <CardContent>
                <ResponsiveContainer width="100%" height={250}>
                  <BarChart data={[
                    { name: t.grossMargin, value: metrics.metrics?.margins?.gross_margin?.value || 0 },
                    { name: t.ebitdaMargin, value: metrics.metrics?.margins?.ebitda_margin?.value || 0 },
                    { name: t.operatingMargin, value: metrics.metrics?.margins?.operating_margin?.value || 0 },
                    { name: t.netMargin, value: metrics.metrics?.margins?.net_margin?.value || 0 },
                  ]}>
                    <CartesianGrid strokeDasharray="3 3" />
                    <XAxis dataKey="name" tick={{ fontSize: 11 }} />
                    <YAxis unit="%" />
                    <Tooltip formatter={(value) => `${value.toFixed(1)}%`} />
                    <Bar dataKey="value" fill="#3B82F6" radius={[4, 4, 0, 0]} />
                  </BarChart>
                </ResponsiveContainer>
              </CardContent>
            </Card>

            {/* Radar Chart */}
            <Card>
              <CardHeader>
                <CardTitle className="text-base flex items-center gap-2">
                  <PieChart className="w-5 h-5 text-purple-500" />
                  {t.generalOverview}
                </CardTitle>
              </CardHeader>
              <CardContent>
                <ResponsiveContainer width="100%" height={250}>
                  <RadarChart data={[
                    { metric: t.grossMargin, value: Math.min(metrics.metrics?.margins?.gross_margin?.value || 0, 100) },
                    { metric: 'ROE', value: Math.min(metrics.metrics?.returns?.roe?.value || 0, 100) },
                    { metric: 'ROIC', value: Math.min(metrics.metrics?.returns?.roic?.value || 0, 100) },
                    { metric: t.liquidity, value: Math.min((metrics.metrics?.liquidity?.current_ratio?.value || 0) * 50, 100) },
                    { metric: t.interestCoverage, value: Math.min((metrics.metrics?.solvency?.interest_coverage?.value || 0) * 20, 100) },
                  ]}>
                    <PolarGrid />
                    <PolarAngleAxis dataKey="metric" tick={{ fontSize: 10 }} />
                    <PolarRadiusAxis angle={30} domain={[0, 100]} tick={{ fontSize: 9 }} />
                    <Radar name="Valor" dataKey="value" stroke="#8B5CF6" fill="#8B5CF6" fillOpacity={0.4} />
                    <Tooltip />
                  </RadarChart>
                </ResponsiveContainer>
              </CardContent>
            </Card>
          </div>

          {/* Margins Section */}
          <Card>
            <CardHeader>
              <CardTitle className="flex items-center gap-2">
                <Percent className="w-5 h-5 text-blue-500" />
                {t.margins}
              </CardTitle>
              <CardDescription>{t.profitabilityOnSales}</CardDescription>
            </CardHeader>
            <CardContent>
              <div className="grid grid-cols-2 md:grid-cols-3 lg:grid-cols-5 gap-4">
                <MetricCard 
                  metric={metrics.metrics?.margins?.gross_margin} 
                  icon={TrendingUp}
                  thresholds={{ good: 30, warning: 15 }}
                  metricKey="gross_margin"
                />
                <MetricCard 
                  metric={metrics.metrics?.margins?.ebitda_margin} 
                  icon={Activity}
                  thresholds={{ good: 20, warning: 10 }}
                  metricKey="ebitda_margin"
                />
                <MetricCard 
                  metric={metrics.metrics?.margins?.operating_margin} 
                  icon={Calculator}
                  thresholds={{ good: 15, warning: 5 }}
                  metricKey="operating_margin"
                />
                <MetricCard 
                  metric={metrics.metrics?.margins?.net_margin} 
                  icon={Target}
                  thresholds={{ good: 10, warning: 3 }}
                  metricKey="net_margin"
                />
                <MetricCard 
                  metric={metrics.metrics?.margins?.nopat_margin} 
                  icon={DollarSign}
                  thresholds={{ good: 10, warning: 3 }}
                  metricKey="nopat_margin"
                />
              </div>
            </CardContent>
          </Card>

          {/* Returns Section */}
          <Card>
            <CardHeader>
              <CardTitle className="flex items-center gap-2">
                <ArrowUpRight className="w-5 h-5 text-green-500" />
                {t.returnOnInvestment}
              </CardTitle>
              <CardDescription>{t.capitalEfficiency}</CardDescription>
            </CardHeader>
            <CardContent>
              <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
                <MetricCard 
                  metric={metrics.metrics?.returns?.roic} 
                  icon={TrendingUp}
                  thresholds={{ good: 15, warning: 8 }}
                  metricKey="roic"
                />
                <MetricCard 
                  metric={metrics.metrics?.returns?.roe} 
                  icon={Target}
                  thresholds={{ good: 15, warning: 8 }}
                  metricKey="roe"
                />
                <MetricCard 
                  metric={metrics.metrics?.returns?.roce} 
                  icon={Activity}
                  thresholds={{ good: 12, warning: 6 }}
                  metricKey="roce"
                />
                <MetricCard 
                  metric={metrics.metrics?.returns?.roa} 
                  icon={Building2}
                  thresholds={{ good: 8, warning: 4 }}
                  metricKey="roa"
                />
              </div>
            </CardContent>
          </Card>

          {/* Efficiency Section */}
          <Card>
            <CardHeader>
              <CardTitle className="flex items-center gap-2">
                <RefreshCw className="w-5 h-5 text-amber-500" />
                {t.operationalEfficiency}
              </CardTitle>
              <CardDescription>{t.rotationAndCycles}</CardDescription>
            </CardHeader>
            <CardContent>
              <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
                <MetricCard 
                  metric={metrics.metrics?.efficiency?.asset_turnover} 
                  icon={Activity}
                  isPercent={false}
                  suffix="x"
                  thresholds={{ good: 1.5, warning: 0.8 }}
                  metricKey="asset_turnover"
                />
                <MetricCard 
                  metric={metrics.metrics?.efficiency?.dso} 
                  icon={Calendar}
                  isPercent={false}
                  suffix=" días"
                  thresholds={{ good: 30, warning: 60 }}
                  metricKey="dso"
                />
                <MetricCard 
                  metric={metrics.metrics?.efficiency?.dpo} 
                  icon={Calendar}
                  isPercent={false}
                  suffix=" días"
                  thresholds={{ good: 45, warning: 30 }}
                  metricKey="dpo"
                />
                <MetricCard 
                  metric={metrics.metrics?.efficiency?.cash_conversion_cycle} 
                  icon={RefreshCw}
                  isPercent={false}
                  suffix=" días"
                  thresholds={{ good: 30, warning: 60 }}
                  metricKey="cash_conversion_cycle"
                />
              </div>
            </CardContent>
          </Card>

          {/* Liquidity Section */}
          <Card>
            <CardHeader>
              <CardTitle className="flex items-center gap-2">
                <Wallet className="w-5 h-5 text-cyan-500" />
                {t.liquidity}
              </CardTitle>
              <CardDescription>{t.shortTermPaymentCapacity}</CardDescription>
            </CardHeader>
            <CardContent>
              <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
                <MetricCard 
                  metric={metrics.metrics?.liquidity?.current_ratio} 
                  icon={Scale}
                  isPercent={false}
                  suffix="x"
                  thresholds={{ good: 2, warning: 1 }}
                  metricKey="current_ratio"
                />
                <MetricCard 
                  metric={metrics.metrics?.liquidity?.quick_ratio} 
                  icon={Activity}
                  isPercent={false}
                  suffix="x"
                  thresholds={{ good: 1, warning: 0.5 }}
                  metricKey="quick_ratio"
                />
                <MetricCard 
                  metric={metrics.metrics?.liquidity?.cash_ratio} 
                  icon={DollarSign}
                  isPercent={false}
                  suffix="x"
                  thresholds={{ good: 0.5, warning: 0.2 }}
                  metricKey="cash_ratio"
                />
                <TooltipProvider delayDuration={300}>
                  <ShadcnTooltip>
                    <TooltipTrigger asChild>
                      <div 
                        className={`p-4 rounded-lg bg-blue-50 border cursor-pointer transition-all duration-200 hover:shadow-md hover:scale-[1.02] ${expandedMetric === 'working_capital' ? 'ring-2 ring-blue-300' : ''}`}
                        onClick={() => setExpandedMetric(expandedMetric === 'working_capital' ? null : 'working_capital')}
                        data-testid="metric-card-working_capital"
                      >
                        <div className="flex items-start justify-between">
                          <div>
                            <p className="text-xs font-medium text-gray-500 uppercase tracking-wider">
                              {metrics.metrics?.liquidity?.working_capital?.label}
                            </p>
                            <p className={`text-2xl font-bold mt-1 ${(metrics.metrics?.liquidity?.working_capital?.value || 0) >= 0 ? 'text-green-600' : 'text-red-600'}`}>
                              {formatCurrency(metrics.metrics?.liquidity?.working_capital?.value)}
                            </p>
                          </div>
                          <div className="flex items-center gap-1">
                            <Wallet className="w-5 h-5 text-blue-500" />
                            {expandedMetric === 'working_capital' ? <ChevronUp className="w-3 h-3 text-gray-400" /> : <ChevronDown className="w-3 h-3 text-gray-400" />}
                          </div>
                        </div>
                        <p className="text-xs text-gray-500 mt-2">{metrics.metrics?.liquidity?.working_capital?.interpretation}</p>
                        {expandedMetric === 'working_capital' && metrics.metrics?.liquidity?.working_capital?.components && (
                          <div className="mt-3 pt-3 border-t border-gray-200 space-y-2 animate-in slide-in-from-top-2 duration-200" data-testid="metric-breakdown-working_capital">
                            <p className="text-xs font-semibold text-gray-700 flex items-center gap-1">
                              <Calculator className="w-3 h-3" /> {metrics.metrics?.liquidity?.working_capital?.formula}
                            </p>
                            {metrics.metrics.liquidity.working_capital.components.map((comp, idx) => (
                              <div key={idx} className="flex justify-between items-center text-xs">
                                <span className="text-gray-600">{comp.label}</span>
                                <span className="font-mono font-semibold text-gray-800">{formatCurrency(comp.value)}</span>
                              </div>
                            ))}
                            <div className="flex justify-between items-center text-xs pt-1 border-t border-dashed border-gray-300">
                              <span className="font-semibold text-gray-700">Resultado</span>
                              <span className={`font-mono font-bold ${(metrics.metrics?.liquidity?.working_capital?.value || 0) >= 0 ? 'text-green-600' : 'text-red-600'}`}>
                                {formatCurrency(metrics.metrics?.liquidity?.working_capital?.value)}
                              </span>
                            </div>
                          </div>
                        )}
                      </div>
                    </TooltipTrigger>
                    <TooltipContent side="top" className="max-w-xs bg-gray-900 text-white px-3 py-2">
                      <p className="font-semibold text-xs">{metrics.metrics?.liquidity?.working_capital?.formula}</p>
                      <p className="text-xs opacity-80 mt-0.5">Clic para ver desglose</p>
                    </TooltipContent>
                  </ShadcnTooltip>
                </TooltipProvider>
              </div>
            </CardContent>
          </Card>

          {/* Solvency Section */}
          <Card>
            <CardHeader>
              <CardTitle className="flex items-center gap-2">
                <Scale className="w-5 h-5 text-red-500" />
                {t.solvency}
              </CardTitle>
              <CardDescription>{t.capitalStructure}</CardDescription>
            </CardHeader>
            <CardContent>
              <div className="grid grid-cols-2 md:grid-cols-5 gap-4">
                <MetricCard 
                  metric={metrics.metrics?.solvency?.debt_to_equity} 
                  icon={Scale}
                  isPercent={false}
                  suffix="x"
                  thresholds={{ good: 1, warning: 2 }}
                  metricKey="debt_to_equity"
                />
                <MetricCard 
                  metric={metrics.metrics?.solvency?.debt_to_assets} 
                  icon={Building2}
                  thresholds={{ good: 40, warning: 60 }}
                  metricKey="debt_to_assets"
                />
                <MetricCard 
                  metric={metrics.metrics?.solvency?.debt_to_ebitda} 
                  icon={TrendingDown}
                  isPercent={false}
                  suffix="x"
                  thresholds={{ good: 3, warning: 5 }}
                  metricKey="debt_to_ebitda"
                />
                <MetricCard 
                  metric={metrics.metrics?.solvency?.interest_coverage} 
                  icon={Activity}
                  isPercent={false}
                  suffix="x"
                  thresholds={{ good: 5, warning: 2 }}
                  metricKey="interest_coverage"
                />
                <MetricCard 
                  metric={metrics.metrics?.solvency?.equity_ratio} 
                  icon={Wallet}
                  thresholds={{ good: 40, warning: 20 }}
                  metricKey="equity_ratio"
                />
              </div>
            </CardContent>
          </Card>

          {/* Raw Data Section (Collapsible) */}
          <Card>
            <CardHeader>
              <CardTitle className="flex items-center gap-2">
                <Info className="w-5 h-5 text-gray-500" />
                {t.periodData}
              </CardTitle>
              <CardDescription>
                {metrics.has_income_statement ? `✓ ${t.hasIncomeStatement}` : `✗ ${t.missingIncomeStatement}`} | 
                {metrics.has_balance_sheet ? ` ✓ ${t.hasBalanceSheet}` : ` ✗ ${t.missingBalanceSheet}`}
              </CardDescription>
            </CardHeader>
            <CardContent>
              <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
                {/* Income Statement Summary */}
                {metrics.income_statement && (
                  <div>
                    <h4 className="font-medium text-sm text-gray-700 mb-3">{t.incomeStatement}</h4>
                    <div className="space-y-2 text-sm">
                      <div className="flex justify-between py-1 border-b">
                        <span className="text-gray-600">{t.revenue}</span>
                        <span className="font-medium">{formatCurrency(metrics.income_statement.ingresos)}</span>
                      </div>
                      <div className="flex justify-between py-1 border-b">
                        <span className="text-gray-600">{t.costOfSales}</span>
                        <span className="font-medium text-red-600">-{formatCurrency(metrics.income_statement.costo_ventas)}</span>
                      </div>
                      <div className="flex justify-between py-1 border-b font-medium">
                        <span>{t.grossProfit}</span>
                        <span>{formatCurrency(metrics.income_statement.utilidad_bruta)}</span>
                      </div>
                      <div className="flex justify-between py-1 border-b">
                        <span className="text-gray-600">{t.operatingExpenses}</span>
                        <span className="font-medium text-red-600">
                          -{formatCurrency((metrics.income_statement.gastos_venta || 0) + (metrics.income_statement.gastos_administracion || 0) + (metrics.income_statement.gastos_generales || 0))}
                        </span>
                      </div>
                      <div className="flex justify-between py-1 border-b font-medium">
                        <span>{t.ebitda}</span>
                        <span>{formatCurrency(metrics.income_statement.ebitda)}</span>
                      </div>
                      <div className="flex justify-between py-1 border-b font-medium bg-blue-50 px-2 rounded">
                        <span>{t.netProfit}</span>
                        <span className="text-blue-600">{formatCurrency(metrics.income_statement.utilidad_neta)}</span>
                      </div>
                    </div>
                  </div>
                )}

                {/* Balance Sheet Summary */}
                {metrics.balance_sheet && (
                  <div>
                    <h4 className="font-medium text-sm text-gray-700 mb-3">{t.balanceSheet}</h4>
                    <div className="space-y-2 text-sm">
                      <div className="flex justify-between py-1 border-b">
                        <span className="text-gray-600">{t.cash}</span>
                        <span className="font-medium">{formatCurrency(metrics.balance_sheet.efectivo)}</span>
                      </div>
                      <div className="flex justify-between py-1 border-b">
                        <span className="text-gray-600">{t.accountsReceivable}</span>
                        <span className="font-medium">{formatCurrency(metrics.balance_sheet.cuentas_por_cobrar)}</span>
                      </div>
                      <div className="flex justify-between py-1 border-b">
                        <span className="text-gray-600">{t.inventory}</span>
                        <span className="font-medium">{formatCurrency(metrics.balance_sheet.inventarios)}</span>
                      </div>
                      <div className="flex justify-between py-1 border-b font-medium">
                        <span>{t.currentAssets}</span>
                        <span>{formatCurrency(metrics.balance_sheet.activo_circulante)}</span>
                      </div>
                      <div className="flex justify-between py-1 border-b font-medium bg-amber-50 px-2 rounded">
                        <span>{t.totalAssets}</span>
                        <span className="text-amber-600">{formatCurrency(metrics.balance_sheet.activo_total)}</span>
                      </div>
                      <div className="flex justify-between py-1 border-b font-medium bg-red-50 px-2 rounded">
                        <span>{t.totalLiabilities}</span>
                        <span className="text-red-600">{formatCurrency(metrics.balance_sheet.pasivo_total)}</span>
                      </div>
                      <div className="flex justify-between py-1 border-b font-medium bg-green-50 px-2 rounded">
                        <span>{t.equity}</span>
                        <span className="text-green-600">{formatCurrency(metrics.balance_sheet.capital_contable)}</span>
                      </div>
                    </div>
                  </div>
                )}
              </div>
            </CardContent>
          </Card>
        </>
      )}

        </TabsContent>
      </Tabs>
    </div>
  );
};

export default FinancialMetrics;
