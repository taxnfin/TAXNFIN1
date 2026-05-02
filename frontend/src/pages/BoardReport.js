import { useState, useEffect, useMemo, useRef } from 'react';
import api from '@/api/axios';
import { Card, CardContent, CardHeader, CardTitle, CardDescription } from '@/components/ui/card';
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from '@/components/ui/select';
import { Tabs, TabsContent, TabsList, TabsTrigger } from '@/components/ui/tabs';
import { Button } from '@/components/ui/button';
import { Dialog, DialogContent, DialogHeader, DialogTitle, DialogFooter } from '@/components/ui/dialog';
import { Label } from '@/components/ui/label';
import { Input } from '@/components/ui/input';
import { toast } from 'sonner';
import { format } from 'date-fns';
import { 
  TrendingUp, TrendingDown, Minus, Download, FileText, FileSpreadsheet,
  BarChart3, PieChart, DollarSign, Building2, Target, Activity, Scale,
  Wallet, RefreshCw, Globe, ArrowUpRight, ArrowDownRight, CheckCircle,
  AlertTriangle, XCircle, Percent, Calculator, Calendar, Clock, Brain,
  Sparkles, Lightbulb, Settings
} from 'lucide-react';
import {
  ResponsiveContainer, BarChart, Bar, LineChart, Line, XAxis, YAxis, 
  CartesianGrid, Tooltip, Legend, ComposedChart, Area, Sankey, Layer,
  Cell, PieChart as RechartsPie, Pie
} from 'recharts';
import * as XLSX from 'xlsx';
import { saveAs } from 'file-saver';
import jsPDF from 'jspdf';
import { translations, languages } from '@/utils/boardReportTranslations';

// Sankey Node Component
const SankeyNode = ({ x, y, width, height, index, payload, containerWidth }) => {
  const isOut = x + width + 6 > containerWidth;
  const colors = ['#3B82F6', '#EF4444', '#22C55E', '#F97316', '#F97316', '#F97316', '#10B981', '#EF4444', '#A855F7', '#059669'];
  return (
    <Layer key={`CustomNode${index}`}>
      <rect x={x} y={y} width={width} height={height} fill={colors[index % colors.length]} fillOpacity="0.9" rx={4} />
      <text textAnchor={isOut ? 'end' : 'start'} x={isOut ? x - 6 : x + width + 6} y={y + height / 2} fontSize="11" fontWeight="600" fill="#374151" dominantBaseline="middle">
        {payload.name}
      </text>
    </Layer>
  );
};

// Sankey Link Component
const SankeyLink = ({ sourceX, targetX, sourceY, targetY, sourceControlX, targetControlX, linkWidth, index, payload }) => {
  const gradientId = `linkGradient${index}`;
  const color = payload?.color || '#94A3B8';
  return (
    <Layer key={`CustomLink${index}`}>
      <defs>
        <linearGradient id={gradientId}>
          <stop offset="0%" stopColor={color} stopOpacity={0.5} />
          <stop offset="100%" stopColor={color} stopOpacity={0.3} />
        </linearGradient>
      </defs>
      <path d={`M${sourceX},${sourceY} C${sourceControlX},${sourceY} ${targetControlX},${targetY} ${targetX},${targetY} L${targetX},${targetY + linkWidth} C${targetControlX},${targetY + linkWidth} ${sourceControlX},${sourceY + linkWidth} ${sourceX},${sourceY + linkWidth} Z`} fill={`url(#${gradientId})`} strokeWidth="0" />
    </Layer>
  );
};

const BoardReport = () => {
  const [language, setLanguage] = useState('es');
  const [selectedPeriod, setSelectedPeriod] = useState('');
  const [periodType, setPeriodType] = useState('monthly'); // monthly, quarterly, annual
  const [availablePeriods, setAvailablePeriods] = useState({
    specific_months: [],
    quarters: [],
    annual: [],
    generic: []
  });
  const [periods, setPeriods] = useState([]);
  const [trendsData, setTrendsData] = useState([]);
  const [currentMetrics, setCurrentMetrics] = useState(null);
  const [sankeyData, setSankeyData] = useState(null);
  const [company, setCompany] = useState(null);
  const [loading, setLoading] = useState(true);
  const [exporting, setExporting] = useState(false);
  const [activeTab, setActiveTab] = useState('summary');
  const [periodsIncluded, setPeriodsIncluded] = useState([]);
  const [aiAnalysis, setAiAnalysis] = useState(null);
  const [loadingAnalysis, setLoadingAnalysis] = useState(false);
  const prevLanguageRef = useRef(language);
  
  // PDF Configuration State
  const [pdfConfigOpen, setPdfConfigOpen] = useState(false);
  const [pdfConfig, setPdfConfig] = useState({
    fontFamily: 'helvetica',
    titleSize: 28,
    subtitleSize: 16,
    sectionHeaderSize: 11,
    bodySize: 10,
    smallSize: 8
  });
  
  const reportRef = useRef(null);
  const t = translations[language];

  useEffect(() => {
    loadData();
  }, []);

  useEffect(() => {
    if (selectedPeriod && periodType) {
      loadPeriodData(selectedPeriod, periodType);
    }
  }, [selectedPeriod, periodType]);

  // Reload AI analysis when language changes (only if we have data)
  useEffect(() => {
    // Only reload if language actually changed and we have period data
    if (prevLanguageRef.current !== language && selectedPeriod && periodType && currentMetrics) {
      prevLanguageRef.current = language;
      loadAIAnalysis(selectedPeriod, periodType, language);
    }
  }, [language, selectedPeriod, periodType, currentMetrics]);

  const loadData = async () => {
    setLoading(true);
    try {
      const [companyRes, periodsRes, trendsRes, availablePeriodsRes] = await Promise.all([
        api.get('/companies'),
        api.get('/financial-statements/periods'),
        api.get('/financial-statements/trends'),
        api.get('/financial-statements/available-periods')
      ]);
      
      if (companyRes.data?.length > 0) setCompany(companyRes.data[0]);
      setPeriods(periodsRes.data || []);
      setTrendsData(trendsRes.data?.data || []);
      setAvailablePeriods(availablePeriodsRes.data || {
        specific_months: [],
        quarters: [],
        annual: [],
        generic: []
      });
      
      // Default to first available month
      if (periodsRes.data?.length > 0) {
        setSelectedPeriod(periodsRes.data[0].periodo);
        setPeriodType('monthly');
      }
    } catch (error) {
      console.error('Error loading data:', error);
      toast.error('Error loading data');
    } finally {
      setLoading(false);
    }
  };

  const loadPeriodData = async (periodo, type) => {
    try {
      let metricsRes;
      
      if (type === 'monthly') {
        // Direct monthly data
        metricsRes = await api.get(`/financial-statements/metrics/${periodo}`);
        setPeriodsIncluded([periodo]);
      } else {
        // Aggregated data
        metricsRes = await api.get('/financial-statements/aggregated', {
          params: {
            period_type: type,
            period_value: periodo
          }
        });
        setPeriodsIncluded(metricsRes.data?.periods_included || []);
      }
      
      setCurrentMetrics(metricsRes.data);
      
      // Load Sankey for first period in selection
      const firstPeriod = type === 'monthly' ? periodo : (metricsRes.data?.periods_included?.[0] || periodo);
      try {
        const sankeyRes = await api.get(`/financial-statements/sankey/${firstPeriod}`);
        setSankeyData(sankeyRes.data);
      } catch (e) {
        console.log('Sankey not available for this period');
      }
      
      // Load AI Analysis
      loadAIAnalysis(periodo, type);
    } catch (error) {
      console.error('Error loading period data:', error);
      toast.error('Error al cargar datos del período');
    }
  };

  const loadAIAnalysis = async (periodo, type, lang = language) => {
    if (!periodo || !type) return;
    
    setLoadingAnalysis(true);
    try {
      const res = await api.get('/financial-statements/ai-analysis', {
        params: {
          period_type: type,
          period_value: periodo,
          language: lang
        }
      });
      setAiAnalysis(res.data?.analysis || null);
    } catch (error) {
      console.error('Error loading AI analysis:', error);
      // Don't clear analysis on error, keep the previous one
    } finally {
      setLoadingAnalysis(false);
    }
  };

  const handlePeriodTypeChange = (newType) => {
    setPeriodType(newType);
    // Reset selected period based on type
    if (newType === 'monthly' && availablePeriods.specific_months?.length > 0) {
      setSelectedPeriod(availablePeriods.specific_months[0].value);
    } else if (newType === 'quarterly' && availablePeriods.quarters?.length > 0) {
      setSelectedPeriod(availablePeriods.quarters[0].value);
    } else if (newType === 'annual' && availablePeriods.annual?.length > 0) {
      setSelectedPeriod(availablePeriods.annual[0].value);
    }
  };

  const getCurrentPeriodOptions = () => {
    switch (periodType) {
      case 'monthly':
        return availablePeriods.specific_months || [];
      case 'quarterly':
        return availablePeriods.quarters || [];
      case 'annual':
        return availablePeriods.annual || [];
      default:
        return availablePeriods.specific_months || [];
    }
  };

  const formatCurrency = (value) => {
    if (value === undefined || value === null) return '$0';
    return new Intl.NumberFormat('es-MX', { style: 'currency', currency: 'MXN', minimumFractionDigits: 0, maximumFractionDigits: 0 }).format(value);
  };

  const formatPercent = (value) => {
    if (value === undefined || value === null) return '0%';
    return `${value.toFixed(1)}%`;
  };

  const formatNumber = (value, decimals = 2) => {
    if (value === undefined || value === null) return '0';
    return value.toFixed(decimals);
  };

  const getTrendIcon = (value, threshold = 0) => {
    if (value > threshold) return <TrendingUp className="w-4 h-4 text-green-500" />;
    if (value < -threshold) return <TrendingDown className="w-4 h-4 text-red-500" />;
    return <Minus className="w-4 h-4 text-gray-400" />;
  };

  const getStatusIcon = (value, goodThreshold, warningThreshold, inverse = false) => {
    const isGood = inverse ? value <= goodThreshold : value >= goodThreshold;
    const isWarning = inverse ? value <= warningThreshold : value >= warningThreshold;
    
    if (isGood) return <CheckCircle className="w-5 h-5 text-green-500" />;
    if (isWarning) return <AlertTriangle className="w-5 h-5 text-amber-500" />;
    return <XCircle className="w-5 h-5 text-red-500" />;
  };

  const getStatusColor = (value, goodThreshold, warningThreshold, inverse = false) => {
    const isGood = inverse ? value <= goodThreshold : value >= goodThreshold;
    const isWarning = inverse ? value <= warningThreshold : value >= warningThreshold;
    
    if (isGood) return 'bg-green-50 border-green-200 text-green-700';
    if (isWarning) return 'bg-amber-50 border-amber-200 text-amber-700';
    return 'bg-red-50 border-red-200 text-red-700';
  };

  // Prepare chart data
  const trendsChartData = useMemo(() => trendsData.map(p => ({
    periodo: p.periodo,
    ingresos: (p.income_statement?.ingresos || 0) / 1000000,
    utilidadNeta: (p.income_statement?.utilidad_neta || 0) / 1000000,
    utilidadBruta: (p.income_statement?.utilidad_bruta || 0) / 1000000,
    margenBruto: p.metrics?.margins?.gross_margin?.value || 0,
    margenNeto: p.metrics?.margins?.net_margin?.value || 0,
    margenEbitda: p.metrics?.margins?.ebitda_margin?.value || 0,
    roe: p.metrics?.returns?.roe?.value || 0,
    roic: p.metrics?.returns?.roic?.value || 0,
    roa: p.metrics?.returns?.roa?.value || 0,
  })), [trendsData]);

  const sankeyChartData = useMemo(() => {
    if (!sankeyData) return null;
    
    // Translations for Sankey node names
    const nodeTranslations = {
      es: {
        'Ingresos': 'Ingresos',
        'Costo de Ventas': 'Costo de Ventas',
        'Utilidad Bruta': 'Utilidad Bruta',
        'Gastos de Venta': 'Gastos de Venta',
        'Gastos Admin': 'Gastos Admin',
        'Gastos Generales': 'Gastos Generales',
        'Utilidad Operativa': 'Utilidad Operativa',
        'Otros Gastos': 'Otros Gastos',
        'Impuestos': 'Impuestos',
        'Utilidad Neta': 'Utilidad Neta'
      },
      en: {
        'Ingresos': 'Revenue',
        'Costo de Ventas': 'Cost of Sales',
        'Utilidad Bruta': 'Gross Profit',
        'Gastos de Venta': 'Sales Expenses',
        'Gastos Admin': 'Admin Expenses',
        'Gastos Generales': 'General Expenses',
        'Utilidad Operativa': 'Operating Profit',
        'Otros Gastos': 'Other Expenses',
        'Impuestos': 'Taxes',
        'Utilidad Neta': 'Net Profit'
      },
      pt: {
        'Ingresos': 'Receita',
        'Costo de Ventas': 'Custo de Vendas',
        'Utilidad Bruta': 'Lucro Bruto',
        'Gastos de Venta': 'Despesas de Vendas',
        'Gastos Admin': 'Despesas Admin',
        'Gastos Generales': 'Despesas Gerais',
        'Utilidad Operativa': 'Lucro Operacional',
        'Otros Gastos': 'Outras Despesas',
        'Impuestos': 'Impostos',
        'Utilidad Neta': 'Lucro Líquido'
      }
    };
    
    const translateNode = (name) => {
      return nodeTranslations[language]?.[name] || name;
    };
    
    // Translate node names
    const translatedNodes = sankeyData.nodes.map(node => ({
      ...node,
      name: translateNode(node.name)
    }));
    
    return { nodes: translatedNodes, links: sankeyData.links };
  }, [sankeyData, language]);

  // Waterfall data for margins
  const waterfallData = useMemo(() => {
    if (!currentMetrics?.income_statement) return [];
    const inc = currentMetrics.income_statement;
    const total = inc.ingresos || 1;
    return [
      { name: t.revenue, value: 100, fill: '#3B82F6' },
      { name: t.costOfSales, value: -((inc.costo_ventas || 0) / total * 100), fill: '#EF4444' },
      { name: t.grossMargin, value: ((inc.utilidad_bruta || 0) / total * 100), fill: '#22C55E' },
      { name: t.operatingExpenses, value: -(((inc.gastos_venta || 0) + (inc.gastos_administracion || 0) + (inc.gastos_generales || 0)) / total * 100), fill: '#F97316' },
      { name: t.ebitdaMargin, value: ((inc.utilidad_operativa || 0) / total * 100), fill: '#10B981' },
      { name: t.otherExpenses, value: -(((inc.otros_gastos || 0) + (inc.gastos_financieros || 0)) / total * 100), fill: '#EF4444' },
      { name: t.taxes, value: -((inc.impuestos || 0) / total * 100), fill: '#A855F7' },
      { name: t.netMargin, value: ((inc.utilidad_neta || 0) / total * 100), fill: '#059669' },
    ];
  }, [currentMetrics, t]);

  // Capital structure data
  const capitalStructureData = useMemo(() => {
    if (!currentMetrics?.balance_sheet) return [];
    const bal = currentMetrics.balance_sheet;
    return [
      { name: t.currentAssets, value: bal.activo_circulante || 0, fill: '#3B82F6' },
      { name: t.fixedAssets, value: bal.activo_fijo || 0, fill: '#6366F1' },
      { name: t.currentLiabilities, value: bal.pasivo_circulante || 0, fill: '#EF4444' },
      { name: t.longTermLiabilities, value: bal.pasivo_largo_plazo || 0, fill: '#F97316' },
      { name: t.equity, value: bal.capital_contable || 0, fill: '#22C55E' },
    ];
  }, [currentMetrics, t]);

  // Export to Excel - Complete with all metrics and AI analysis
  const exportToExcel = () => {
    try {
      const wb = XLSX.utils.book_new();
      
      // 1. RESUMEN EJECUTIVO con análisis de IA
      if (currentMetrics) {
        const inc = currentMetrics.income_statement || {};
        const bal = currentMetrics.balance_sheet || {};
        
        const summaryData = [
          { Concepto: t.revenue, Valor: inc.ingresos || 0, Porcentaje: '100%' },
          { Concepto: t.costOfSales, Valor: inc.costo_ventas || 0, Porcentaje: `${((inc.costo_ventas || 0) / (inc.ingresos || 1) * 100).toFixed(1)}%` },
          { Concepto: t.grossProfit, Valor: inc.utilidad_bruta || 0, Porcentaje: `${((inc.utilidad_bruta || 0) / (inc.ingresos || 1) * 100).toFixed(1)}%` },
          { Concepto: t.operatingExpenses, Valor: (inc.gastos_venta || 0) + (inc.gastos_administracion || 0) + (inc.gastos_generales || 0), Porcentaje: '' },
          { Concepto: t.ebitda, Valor: inc.ebitda || inc.utilidad_operativa || 0, Porcentaje: `${((inc.ebitda || inc.utilidad_operativa || 0) / (inc.ingresos || 1) * 100).toFixed(1)}%` },
          { Concepto: t.netProfit, Valor: inc.utilidad_neta || 0, Porcentaje: `${((inc.utilidad_neta || 0) / (inc.ingresos || 1) * 100).toFixed(1)}%` },
          { Concepto: '', Valor: '', Porcentaje: '' },
          { Concepto: t.totalAssets, Valor: bal.activo_total || 0, Porcentaje: '' },
          { Concepto: t.currentAssets, Valor: bal.activo_circulante || 0, Porcentaje: '' },
          { Concepto: t.fixedAssets, Valor: bal.activo_fijo || 0, Porcentaje: '' },
          { Concepto: t.totalLiabilities, Valor: bal.pasivo_total || 0, Porcentaje: '' },
          { Concepto: t.equity, Valor: bal.capital_contable || 0, Porcentaje: '' },
        ];
        XLSX.utils.book_append_sheet(wb, XLSX.utils.json_to_sheet(summaryData), t.tabSummary);
      }
      
      // 2. ANÁLISIS DE IA
      if (aiAnalysis) {
        const aiData = [
          { Sección: t.executiveSummary || 'Resumen Ejecutivo', Análisis: aiAnalysis.executive_summary || '' },
          { Sección: t.profitabilityAnalysis || 'Análisis de Rentabilidad', Análisis: aiAnalysis.profitability_analysis || '' },
          { Sección: t.returnsAnalysis || 'Análisis de Retornos', Análisis: aiAnalysis.returns_analysis || '' },
          { Sección: t.liquidityAnalysisAI || 'Análisis de Liquidez', Análisis: aiAnalysis.liquidity_analysis || '' },
          { Sección: t.solvencyAnalysisAI || 'Análisis de Solvencia', Análisis: aiAnalysis.solvency_analysis || '' },
          { Sección: t.strategicRecommendations || 'Recomendaciones', Análisis: aiAnalysis.recommendations || '' },
        ];
        XLSX.utils.book_append_sheet(wb, XLSX.utils.json_to_sheet(aiData), t.aiAnalysis || 'Análisis IA');
      }
      
      // 3. MÁRGENES
      if (currentMetrics?.metrics?.margins) {
        const metrics = currentMetrics.metrics;
        const marginsData = [
          { Métrica: t.grossMargin, Valor: `${(metrics.margins?.gross_margin?.value || 0).toFixed(1)}%`, Estado: metrics.margins?.gross_margin?.value >= 30 ? 'Bueno' : metrics.margins?.gross_margin?.value >= 15 ? 'Atención' : 'Crítico' },
          { Métrica: t.ebitdaMargin, Valor: `${(metrics.margins?.ebitda_margin?.value || 0).toFixed(1)}%`, Estado: metrics.margins?.ebitda_margin?.value >= 20 ? 'Bueno' : metrics.margins?.ebitda_margin?.value >= 10 ? 'Atención' : 'Crítico' },
          { Métrica: t.operatingMargin, Valor: `${(metrics.margins?.operating_margin?.value || 0).toFixed(1)}%`, Estado: metrics.margins?.operating_margin?.value >= 15 ? 'Bueno' : metrics.margins?.operating_margin?.value >= 5 ? 'Atención' : 'Crítico' },
          { Métrica: t.netMargin, Valor: `${(metrics.margins?.net_margin?.value || 0).toFixed(1)}%`, Estado: metrics.margins?.net_margin?.value >= 10 ? 'Bueno' : metrics.margins?.net_margin?.value >= 3 ? 'Atención' : 'Crítico' },
          { Métrica: t.nopatMargin, Valor: `${(metrics.margins?.nopat_margin?.value || 0).toFixed(1)}%`, Estado: '' },
        ];
        XLSX.utils.book_append_sheet(wb, XLSX.utils.json_to_sheet(marginsData), t.tabMargins);
      }
      
      // 4. RETORNOS
      if (currentMetrics?.metrics?.returns) {
        const metrics = currentMetrics.metrics;
        const returnsData = [
          { Métrica: 'ROIC', Valor: `${(metrics.returns?.roic?.value || 0).toFixed(1)}%`, Estado: metrics.returns?.roic?.value >= 15 ? 'Bueno' : metrics.returns?.roic?.value >= 8 ? 'Atención' : 'Crítico' },
          { Métrica: 'ROE', Valor: `${(metrics.returns?.roe?.value || 0).toFixed(1)}%`, Estado: metrics.returns?.roe?.value >= 15 ? 'Bueno' : metrics.returns?.roe?.value >= 8 ? 'Atención' : 'Crítico' },
          { Métrica: 'ROCE', Valor: `${(metrics.returns?.roce?.value || 0).toFixed(1)}%`, Estado: metrics.returns?.roce?.value >= 12 ? 'Bueno' : metrics.returns?.roce?.value >= 6 ? 'Atención' : 'Crítico' },
          { Métrica: 'ROA', Valor: `${(metrics.returns?.roa?.value || 0).toFixed(1)}%`, Estado: metrics.returns?.roa?.value >= 8 ? 'Bueno' : metrics.returns?.roa?.value >= 4 ? 'Atención' : 'Crítico' },
          { Métrica: 'RONIC', Valor: `${(metrics.returns?.ronic?.value || 0).toFixed(1)}%`, Estado: '' },
          { Métrica: 'GMROI', Valor: `${(metrics.returns?.gmroi?.value || 0).toFixed(2)}x`, Estado: '' },
        ];
        XLSX.utils.book_append_sheet(wb, XLSX.utils.json_to_sheet(returnsData), t.tabReturns);
      }
      
      // 5. EFICIENCIA
      if (currentMetrics?.metrics?.efficiency) {
        const metrics = currentMetrics.metrics;
        const efficiencyData = [
          { Métrica: t.assetTurnover, Valor: `${(metrics.efficiency?.asset_turnover?.value || 0).toFixed(2)}x` },
          { Métrica: t.receivablesTurnover, Valor: `${(metrics.efficiency?.receivables_turnover?.value || 0).toFixed(2)}x` },
          { Métrica: t.inventoryTurnover, Valor: `${(metrics.efficiency?.inventory_turnover?.value || 0).toFixed(2)}x` },
          { Métrica: t.payablesTurnover, Valor: `${(metrics.efficiency?.payables_turnover?.value || 0).toFixed(2)}x` },
          { Métrica: t.dso, Valor: `${(metrics.efficiency?.dso?.value || 0).toFixed(0)} ${t.days}` },
          { Métrica: t.dpo, Valor: `${(metrics.efficiency?.dpo?.value || 0).toFixed(0)} ${t.days}` },
          { Métrica: t.dio, Valor: `${(metrics.efficiency?.dio?.value || 0).toFixed(0)} ${t.days}` },
          { Métrica: t.cashConversionCycle, Valor: `${(metrics.efficiency?.cash_conversion_cycle?.value || 0).toFixed(0)} ${t.days}` },
        ];
        XLSX.utils.book_append_sheet(wb, XLSX.utils.json_to_sheet(efficiencyData), t.tabEfficiency);
      }
      
      // 6. LIQUIDEZ
      if (currentMetrics?.metrics?.liquidity) {
        const metrics = currentMetrics.metrics;
        const liquidityData = [
          { Métrica: t.currentRatio, Valor: `${(metrics.liquidity?.current_ratio?.value || 0).toFixed(2)}x`, Estado: metrics.liquidity?.current_ratio?.value >= 2 ? 'Bueno' : metrics.liquidity?.current_ratio?.value >= 1 ? 'Atención' : 'Crítico' },
          { Métrica: t.quickRatio, Valor: `${(metrics.liquidity?.quick_ratio?.value || 0).toFixed(2)}x`, Estado: metrics.liquidity?.quick_ratio?.value >= 1 ? 'Bueno' : metrics.liquidity?.quick_ratio?.value >= 0.5 ? 'Atención' : 'Crítico' },
          { Métrica: t.cashRatio, Valor: `${(metrics.liquidity?.cash_ratio?.value || 0).toFixed(2)}x`, Estado: metrics.liquidity?.cash_ratio?.value >= 0.5 ? 'Bueno' : metrics.liquidity?.cash_ratio?.value >= 0.2 ? 'Atención' : 'Crítico' },
          { Métrica: t.workingCapital, Valor: formatCurrency(metrics.liquidity?.working_capital?.value || 0), Estado: (metrics.liquidity?.working_capital?.value || 0) >= 0 ? 'Bueno' : 'Crítico' },
          { Métrica: t.cashRunway, Valor: `${(metrics.liquidity?.cash_runway?.value || 0).toFixed(1)} meses`, Estado: metrics.liquidity?.cash_runway?.value >= 6 ? 'Bueno' : metrics.liquidity?.cash_runway?.value >= 3 ? 'Atención' : 'Crítico' },
          { Métrica: t.cashEfficiency, Valor: `${(metrics.liquidity?.cash_efficiency?.value || 0).toFixed(1)}%`, Estado: '' },
        ];
        XLSX.utils.book_append_sheet(wb, XLSX.utils.json_to_sheet(liquidityData), t.tabLiquidity);
      }
      
      // 7. SOLVENCIA
      if (currentMetrics?.metrics?.solvency) {
        const metrics = currentMetrics.metrics;
        const solvencyData = [
          { Métrica: t.debtToEquity, Valor: `${(metrics.solvency?.debt_to_equity?.value || 0).toFixed(2)}x`, Estado: metrics.solvency?.debt_to_equity?.value <= 1 ? 'Bueno' : metrics.solvency?.debt_to_equity?.value <= 2 ? 'Atención' : 'Crítico' },
          { Métrica: t.debtToAssets, Valor: `${(metrics.solvency?.debt_to_assets?.value || 0).toFixed(1)}%`, Estado: metrics.solvency?.debt_to_assets?.value <= 40 ? 'Bueno' : metrics.solvency?.debt_to_assets?.value <= 60 ? 'Atención' : 'Crítico' },
          { Métrica: t.debtToEbitda, Valor: `${(metrics.solvency?.debt_to_ebitda?.value || 0).toFixed(2)}x`, Estado: metrics.solvency?.debt_to_ebitda?.value <= 3 ? 'Bueno' : metrics.solvency?.debt_to_ebitda?.value <= 5 ? 'Atención' : 'Crítico' },
          { Métrica: t.interestCoverage, Valor: `${(metrics.solvency?.interest_coverage?.value || 0).toFixed(2)}x`, Estado: metrics.solvency?.interest_coverage?.value >= 5 ? 'Bueno' : metrics.solvency?.interest_coverage?.value >= 2 ? 'Atención' : 'Crítico' },
          { Métrica: t.financialLeverage, Valor: `${(metrics.solvency?.financial_leverage?.value || 0).toFixed(2)}x`, Estado: '' },
          { Métrica: t.netDebtToEbitda, Valor: `${(metrics.solvency?.net_debt_to_ebitda?.value || 0).toFixed(2)}x`, Estado: metrics.solvency?.net_debt_to_ebitda?.value <= 2 ? 'Bueno' : metrics.solvency?.net_debt_to_ebitda?.value <= 3.5 ? 'Atención' : 'Crítico' },
          { Métrica: t.equityRatio, Valor: `${(metrics.solvency?.equity_ratio?.value || 0).toFixed(1)}%`, Estado: metrics.solvency?.equity_ratio?.value >= 40 ? 'Bueno' : metrics.solvency?.equity_ratio?.value >= 20 ? 'Atención' : 'Crítico' },
          { Métrica: language === 'es' ? 'Costo de Deuda' : 'Cost of Debt', Valor: `${(metrics.solvency?.cost_of_debt?.value || 0).toFixed(1)}%`, Estado: '' },
        ];
        XLSX.utils.book_append_sheet(wb, XLSX.utils.json_to_sheet(solvencyData), t.tabSolvency);
      }
      
      // 8. TENDENCIAS MENSUALES
      if (trendsData.length > 0) {
        const trendsExport = trendsData.map(p => ({
          [t.period]: p.periodo,
          [t.revenue]: p.income_statement?.ingresos || 0,
          [t.grossProfit]: p.income_statement?.utilidad_bruta || 0,
          [t.ebitda]: p.income_statement?.utilidad_operativa || 0,
          [t.netProfit]: p.income_statement?.utilidad_neta || 0,
          [t.grossMargin]: `${(p.metrics?.margins?.gross_margin?.value || 0).toFixed(1)}%`,
          [t.netMargin]: `${(p.metrics?.margins?.net_margin?.value || 0).toFixed(1)}%`,
          ['ROE']: `${(p.metrics?.returns?.roe?.value || 0).toFixed(1)}%`,
          ['ROIC']: `${(p.metrics?.returns?.roic?.value || 0).toFixed(1)}%`,
        }));
        XLSX.utils.book_append_sheet(wb, XLSX.utils.json_to_sheet(trendsExport), t.tabTrends);
      }
      
      const periodLabel = periodType === 'monthly' ? selectedPeriod : `${periodType}_${selectedPeriod}`;
      const fileName = `${t.title}_${company?.nombre || 'Company'}_${periodLabel}.xlsx`;
      const excelBuffer = XLSX.write(wb, { bookType: 'xlsx', type: 'array' });
      saveAs(new Blob([excelBuffer], { type: 'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet' }), fileName);
      toast.success(language === 'es' ? 'Excel exportado exitosamente' : language === 'pt' ? 'Excel exportado com sucesso' : 'Excel exported successfully');
    } catch (error) {
      console.error('Error exporting Excel:', error);
      toast.error('Error exporting Excel');
    }
  };

  // Export to PDF - Complete Multi-Page Report with AI Analysis
  const exportToPDF = async () => {
    if (!currentMetrics || !currentMetrics.income_statement) {
      toast.error(language === 'es' ? 'No hay datos financieros para exportar' : 'No financial data to export');
      return;
    }
    
    setExporting(true);
    toast.info(t.pdfGenerating || 'Generando PDF completo...');
    
    try {
      const pdf = new jsPDF('p', 'mm', 'a4');
      const pageWidth = pdf.internal.pageSize.getWidth();
      const pageHeight = pdf.internal.pageSize.getHeight();
      const margin = 15;
      const contentWidth = pageWidth - (margin * 2);
      let y = margin;
      let currentPage = 1;
      
      // Use PDF config for font sizes
      const { fontFamily, titleSize, subtitleSize, sectionHeaderSize, bodySize, smallSize } = pdfConfig;
      
      // Set default font
      pdf.setFont(fontFamily, 'normal');
      
      // Helper function to wrap text - fixed to avoid character spacing issues
      const wrapText = (text, maxWidth, fontSize = bodySize) => {
        if (!text) return [];
        pdf.setFont(fontFamily, 'normal');
        pdf.setFontSize(fontSize);
        
        // Use jsPDF's built-in text splitting
        const lines = pdf.splitTextToSize(String(text), maxWidth);
        return lines;
      };
      
      const addNewPageIfNeeded = (requiredSpace = 30) => {
        if (y + requiredSpace > pageHeight - 25) {
          // Add footer before new page
          addPageFooter();
          pdf.addPage();
          currentPage++;
          y = margin;
          return true;
        }
        return false;
      };
      
      const addPageFooter = () => {
        const footerY = pageHeight - 8;
        // Thin line separator
        pdf.setDrawColor(200, 200, 200);
        pdf.setLineWidth(0.3);
        pdf.line(margin, footerY - 4, pageWidth - margin, footerY - 4);
        
        pdf.setFontSize(7);
        pdf.setFont(fontFamily, 'normal');
        pdf.setTextColor(160, 160, 160);
        
        // Left: Company name
        pdf.text(company?.nombre || '', margin, footerY);
        
        // Center: Page number
        const pageText = `${currentPage}`;
        const pageTextWidth = pdf.getTextWidth(pageText);
        pdf.text(pageText, (pageWidth - pageTextWidth) / 2, footerY);
        
        // Right: AI attribution
        const rightText = 'Análisis: Claude Sonnet';
        pdf.text(rightText, pageWidth - margin - pdf.getTextWidth(rightText), footerY);
        
        pdf.setTextColor(0, 0, 0);
      };
      
      const drawSectionHeader = (title, color = [15, 23, 42]) => {
        addNewPageIfNeeded(20);
        // Elegant line + text style (no filled rectangle)
        pdf.setDrawColor(...color);
        pdf.setLineWidth(0.8);
        pdf.line(margin, y + 1, margin + 35, y + 1);
        pdf.setFontSize(sectionHeaderSize + 1);
        pdf.setFont(fontFamily, 'bold');
        pdf.setTextColor(...color);
        pdf.text(title, margin, y + 8);
        // Subtle line after title
        const titleW = pdf.getTextWidth(title);
        pdf.setDrawColor(220, 220, 220);
        pdf.setLineWidth(0.3);
        pdf.line(margin + titleW + 4, y + 6, pageWidth - margin, y + 6);
        pdf.setTextColor(0, 0, 0);
        y += 14;
      };
      
      const drawAnalysisText = (text) => {
        if (!text) return;
        pdf.setFont(fontFamily, 'normal');
        pdf.setFontSize(bodySize);
        pdf.setTextColor(75, 85, 99);
        const lines = wrapText(text, contentWidth - 8, bodySize);
        lines.forEach(line => {
          addNewPageIfNeeded(6);
          pdf.text(line, margin + 4, y);
          y += 5.2;
        });
        pdf.setTextColor(0, 0, 0);
        y += 4;
      };
      
      let metricRowIndex = 0;
      const drawMetricRow = (label, value, status = null) => {
        addNewPageIfNeeded(7);
        metricRowIndex++;
        
        // Subtle zebra striping
        if (metricRowIndex % 2 === 0) {
          pdf.setFillColor(248, 250, 252);
          pdf.rect(margin, y - 4, contentWidth, 6.5, 'F');
        }
        
        pdf.setFontSize(bodySize);
        pdf.setFont(fontFamily, 'normal');
        pdf.setTextColor(55, 65, 81);
        pdf.text(label, margin + 3, y);
        
        pdf.setFont(fontFamily, 'bold');
        pdf.setTextColor(17, 24, 39);
        pdf.text(String(value), margin + 90, y);
        
        if (status) {
          if (status === 'good') pdf.setTextColor(16, 185, 129);
          else if (status === 'warning') pdf.setTextColor(245, 158, 11);
          else if (status === 'critical') pdf.setTextColor(220, 38, 38);
          const statusLabels = {
            es: { good: 'Bueno', warning: 'Atención', critical: 'Crítico' },
            en: { good: 'Good', warning: 'Warning', critical: 'Critical' },
            pt: { good: 'Bom', warning: 'Atenção', critical: 'Crítico' }
          };
          const statusText = statusLabels[language]?.[status] || statusLabels.es[status];
          pdf.setFontSize(bodySize - 1);
          pdf.text(statusText, margin + 140, y);
          pdf.setTextColor(0, 0, 0);
        }
        y += 6.5;
      };
      
      const getStatus = (value, goodThreshold, warningThreshold, inverse = false) => {
        if (value === undefined || value === null) return null;
        const isGood = inverse ? value <= goodThreshold : value >= goodThreshold;
        const isWarning = inverse ? value <= warningThreshold : value >= warningThreshold;
        if (isGood) return 'good';
        if (isWarning) return 'warning';
        return 'critical';
      };
      
      // ====== CHART HELPERS (pure jsPDF primitives) ======
      
      // Compact compact-currency label for chart axes ($1.2M / $850K)
      const compactCurrency = (v) => {
        if (v === undefined || v === null || isNaN(v)) return '0';
        const abs = Math.abs(v);
        const sign = v < 0 ? '-' : '';
        if (abs >= 1_000_000) return `${sign}$${(abs / 1_000_000).toFixed(1)}M`;
        if (abs >= 1_000) return `${sign}$${(abs / 1_000).toFixed(0)}K`;
        return `${sign}$${abs.toFixed(0)}`;
      };
      
      // Vertical grouped bar chart (e.g. Revenue + Net Profit by period)
      // series = [{name, color:[r,g,b], values:[]}], labels = []
      const drawVerticalBarChart = (xPos, yPos, w, h, labels, series, opts = {}) => {
        const titleH = opts.title ? 7 : 0;
        const legendH = series.length > 0 ? 6 : 0;
        const padBottom = 10; // for x labels
        const padLeft = 18; // for y labels
        const padTop = titleH + 2;
        
        const chartX = xPos + padLeft;
        const chartY = yPos + padTop;
        const chartW = w - padLeft - 4;
        const chartH = h - padTop - padBottom - legendH;
        
        // Title
        if (opts.title) {
          pdf.setFont(fontFamily, 'bold');
          pdf.setFontSize(bodySize);
          pdf.setTextColor(31, 41, 55);
          pdf.text(opts.title, xPos, yPos + 5);
        }
        
        // Determine min/max across all series
        const allVals = series.flatMap(s => s.values);
        const maxVal = Math.max(...allVals, 0);
        const minVal = Math.min(...allVals, 0);
        const range = (maxVal - minVal) || 1;
        
        // Y-axis grid (4 lines)
        pdf.setDrawColor(229, 231, 235);
        pdf.setLineWidth(0.2);
        pdf.setFontSize(smallSize - 1);
        pdf.setFont(fontFamily, 'normal');
        pdf.setTextColor(120, 120, 120);
        for (let i = 0; i <= 4; i++) {
          const ratio = i / 4;
          const yLine = chartY + chartH - (ratio * chartH);
          pdf.line(chartX, yLine, chartX + chartW, yLine);
          const labelVal = minVal + ratio * range;
          pdf.text(compactCurrency(labelVal), xPos + padLeft - 2, yLine + 1.5, { align: 'right' });
        }
        
        // X-axis baseline (zero line)
        const zeroY = chartY + chartH - ((0 - minVal) / range) * chartH;
        pdf.setDrawColor(180, 180, 180);
        pdf.setLineWidth(0.4);
        pdf.line(chartX, zeroY, chartX + chartW, zeroY);
        
        // Bars
        const groupCount = labels.length;
        if (groupCount === 0) return;
        const groupW = chartW / groupCount;
        const seriesCount = series.length;
        const barW = Math.max(1.5, (groupW * 0.7) / seriesCount);
        const groupGap = (groupW - barW * seriesCount) / 2;
        
        labels.forEach((lbl, i) => {
          const groupStartX = chartX + i * groupW + groupGap;
          series.forEach((s, sIdx) => {
            const v = s.values[i] || 0;
            const barH = Math.abs(v / range) * chartH;
            const barX = groupStartX + sIdx * barW;
            const barY = v >= 0 ? zeroY - barH : zeroY;
            pdf.setFillColor(...s.color);
            pdf.rect(barX, barY, barW * 0.95, barH, 'F');
          });
          
          // X-label
          pdf.setFontSize(smallSize - 1);
          pdf.setTextColor(80, 80, 80);
          const lblShort = String(lbl).length > 7 ? String(lbl).slice(2) : String(lbl);
          pdf.text(lblShort, chartX + i * groupW + groupW / 2, chartY + chartH + 5, { align: 'center' });
        });
        
        // Legend
        if (series.length > 0) {
          let legendX = chartX;
          const legendY = yPos + h - 2;
          pdf.setFontSize(smallSize);
          pdf.setFont(fontFamily, 'normal');
          pdf.setTextColor(60, 60, 60);
          series.forEach(s => {
            pdf.setFillColor(...s.color);
            pdf.rect(legendX, legendY - 3, 3, 3, 'F');
            pdf.text(s.name, legendX + 5, legendY);
            legendX += pdf.getTextWidth(s.name) + 12;
          });
        }
        
        pdf.setTextColor(0, 0, 0);
      };
      
      // Horizontal bar chart: items = [{label, value, color:[r,g,b], unit:'%'}]
      const drawHorizontalBarChart = (xPos, yPos, w, h, items, opts = {}) => {
        const titleH = opts.title ? 7 : 0;
        const padTop = titleH + 2;
        const labelW = 38;
        const valueW = 18;
        const chartX = xPos + labelW;
        const chartY = yPos + padTop;
        const chartW = w - labelW - valueW - 2;
        const chartH = h - padTop - 2;
        
        if (opts.title) {
          pdf.setFont(fontFamily, 'bold');
          pdf.setFontSize(bodySize);
          pdf.setTextColor(31, 41, 55);
          pdf.text(opts.title, xPos, yPos + 5);
        }
        
        const maxAbs = Math.max(...items.map(it => Math.abs(it.value || 0)), 1);
        const rowH = chartH / items.length;
        const barH = Math.min(rowH * 0.6, 5);
        
        items.forEach((it, i) => {
          const rowY = chartY + i * rowH + rowH / 2;
          
          // Label
          pdf.setFont(fontFamily, 'normal');
          pdf.setFontSize(smallSize);
          pdf.setTextColor(55, 65, 81);
          pdf.text(it.label, xPos + labelW - 2, rowY + 1.5, { align: 'right' });
          
          // Bar background
          pdf.setFillColor(243, 244, 246);
          pdf.rect(chartX, rowY - barH / 2, chartW, barH, 'F');
          
          // Bar fill
          const barWidth = (Math.abs(it.value) / maxAbs) * chartW;
          pdf.setFillColor(...(it.color || [59, 130, 246]));
          pdf.rect(chartX, rowY - barH / 2, barWidth, barH, 'F');
          
          // Value label
          pdf.setFont(fontFamily, 'bold');
          pdf.setFontSize(smallSize);
          pdf.setTextColor(17, 24, 39);
          const valStr = it.unit === '%' ? `${(it.value || 0).toFixed(1)}%` :
                         it.unit === 'x' ? `${(it.value || 0).toFixed(2)}x` :
                         compactCurrency(it.value);
          pdf.text(valStr, chartX + chartW + 2, rowY + 1.5);
        });
        
        pdf.setTextColor(0, 0, 0);
      };
      
      // Stacked horizontal bar (for capital structure)
      // segments = [{label, value, color:[r,g,b]}]
      const drawStackedBar = (xPos, yPos, w, h, segments, opts = {}) => {
        const titleH = opts.title ? 7 : 0;
        if (opts.title) {
          pdf.setFont(fontFamily, 'bold');
          pdf.setFontSize(bodySize);
          pdf.setTextColor(31, 41, 55);
          pdf.text(opts.title, xPos, yPos + 5);
        }
        
        const total = segments.reduce((sum, s) => sum + Math.abs(s.value || 0), 0) || 1;
        const barY = yPos + titleH;
        const barH = 8;
        let cursorX = xPos;
        
        segments.forEach((seg) => {
          const segW = (Math.abs(seg.value || 0) / total) * w;
          pdf.setFillColor(...(seg.color || [156, 163, 175]));
          pdf.rect(cursorX, barY, segW, barH, 'F');
          cursorX += segW;
        });
        
        // Legend below the bar (2 columns)
        const legendStartY = barY + barH + 4;
        const colW = w / 2;
        segments.forEach((seg, i) => {
          const col = i % 2;
          const row = Math.floor(i / 2);
          const lx = xPos + col * colW;
          const ly = legendStartY + row * 5;
          pdf.setFillColor(...(seg.color || [156, 163, 175]));
          pdf.rect(lx, ly - 2.5, 3, 3, 'F');
          pdf.setFont(fontFamily, 'normal');
          pdf.setFontSize(smallSize - 1);
          pdf.setTextColor(55, 65, 81);
          const pct = ((Math.abs(seg.value || 0) / total) * 100).toFixed(0);
          pdf.text(`${seg.label}: ${compactCurrency(seg.value)} (${pct}%)`, lx + 5, ly);
        });
        
        pdf.setTextColor(0, 0, 0);
      };
      
      // Sparkline drawing
      const drawSparkline = (xPos, yPos, w, h, values, color = [59, 130, 246]) => {
        if (!values || values.length < 2) return;
        const maxV = Math.max(...values);
        const minV = Math.min(...values);
        const range = (maxV - minV) || 1;
        const step = w / (values.length - 1);
        
        pdf.setDrawColor(...color);
        pdf.setLineWidth(0.6);
        for (let i = 0; i < values.length - 1; i++) {
          const x1 = xPos + i * step;
          const y1 = yPos + h - ((values[i] - minV) / range) * h;
          const x2 = xPos + (i + 1) * step;
          const y2 = yPos + h - ((values[i + 1] - minV) / range) * h;
          pdf.line(x1, y1, x2, y2);
        }
        
        // End point dot
        const lastX = xPos + (values.length - 1) * step;
        const lastY = yPos + h - ((values[values.length - 1] - minV) / range) * h;
        pdf.setFillColor(...color);
        pdf.circle(lastX, lastY, 0.8, 'F');
      };
      
      // ====== PAGE 1: PROFESSIONAL COVER PAGE ======
      // Full page dark navy background
      pdf.setFillColor(12, 20, 36);
      pdf.rect(0, 0, pageWidth, pageHeight, 'F');
      
      // Subtle geometric accent - gold vertical bar on left
      pdf.setFillColor(180, 142, 58);
      pdf.rect(0, 0, 3, pageHeight, 'F');
      
      // Top accent line
      pdf.setFillColor(180, 142, 58);
      pdf.rect(margin + 40, 30, contentWidth - 80, 0.5, 'F');
      
      // Add company logo if available (centered near top)
      if (company?.logo_url) {
        try {
          const logoSize = 36;
          const logoX = (pageWidth - logoSize) / 2;
          pdf.addImage(company.logo_url, 'PNG', logoX, 40, logoSize, logoSize);
          y = 90;
        } catch (logoErr) {
          console.warn('Could not add logo to PDF:', logoErr);
          y = 65;
        }
      } else {
        y = 65;
      }
      
      // Company name - large and centered (handle long names)
      const companyName = company?.nombre || 'Company';
      pdf.setFont(fontFamily, 'bold');
      pdf.setTextColor(255, 255, 255);
      
      // Adjust font size based on name length
      let nameFontSize = titleSize;
      pdf.setFontSize(nameFontSize);
      let companyNameWidth = pdf.getTextWidth(companyName);
      
      // Reduce font size if name is too wide
      while (companyNameWidth > contentWidth - 20 && nameFontSize > 14) {
        nameFontSize -= 2;
        pdf.setFontSize(nameFontSize);
        companyNameWidth = pdf.getTextWidth(companyName);
      }
      
      // If still too wide, split into lines
      if (companyNameWidth > contentWidth - 20) {
        const nameLines = pdf.splitTextToSize(companyName, contentWidth - 20);
        nameLines.forEach((line, idx) => {
          const lineWidth = pdf.getTextWidth(line);
          pdf.text(line, (pageWidth - lineWidth) / 2, y + (idx * (nameFontSize * 0.4)));
        });
        y += nameLines.length * (nameFontSize * 0.4) + 10;
      } else {
        pdf.text(companyName, (pageWidth - companyNameWidth) / 2, y);
        y += 20;
      }
      
      // Report title
      pdf.setFontSize(subtitleSize);
      pdf.setFont(fontFamily, 'normal');
      pdf.setTextColor(148, 163, 184);
      const titleText = t.title || 'Executive Board Report';
      const titleWidth = pdf.getTextWidth(titleText);
      pdf.text(titleText, (pageWidth - titleWidth) / 2, y);
      y += 15;
      
      // Decorative gold line
      pdf.setDrawColor(180, 142, 58);
      pdf.setLineWidth(0.8);
      pdf.line(margin + 50, y, pageWidth - margin - 50, y);
      y += 20;
      
      // Period information box - refined with gold border
      pdf.setDrawColor(180, 142, 58);
      pdf.setLineWidth(0.5);
      pdf.setFillColor(18, 28, 48);
      pdf.roundedRect(margin + 30, y - 5, contentWidth - 60, 35, 2, 2, 'FD');
      
      // Period type and value
      const periodTypeLabels = { monthly: t.monthly, quarterly: t.quarterly, annual: t.annual };
      pdf.setFontSize(sectionHeaderSize);
      pdf.setFont(fontFamily, 'normal');
      pdf.setTextColor(148, 163, 184);
      const periodLabel = periodTypeLabels[periodType] || periodType;
      const periodLabelText = `${periodLabel}`;
      const periodLabelWidth = pdf.getTextWidth(periodLabelText);
      pdf.text(periodLabelText, (pageWidth - periodLabelWidth) / 2, y + 8);
      
      pdf.setFontSize(subtitleSize + 2);
      pdf.setFont(fontFamily, 'bold');
      pdf.setTextColor(255, 255, 255);
      const periodValueWidth = pdf.getTextWidth(selectedPeriod);
      pdf.text(selectedPeriod, (pageWidth - periodValueWidth) / 2, y + 23);
      
      y += 50;
      
      // Periods included (if aggregated)
      if (periodsIncluded.length > 1) {
        pdf.setFontSize(smallSize + 1);
        pdf.setFont(fontFamily, 'italic');
        pdf.setTextColor(100, 116, 139);
        const periodsText = `${t.periodsIncluded}: ${periodsIncluded.join(', ')}`;
        const periodsTextWidth = pdf.getTextWidth(periodsText);
        pdf.text(periodsText, (pageWidth - periodsTextWidth) / 2, y);
        y += 12;
      }
      
      // Generation date at bottom
      pdf.setFontSize(bodySize);
      pdf.setFont(fontFamily, 'normal');
      pdf.setTextColor(100, 116, 139);
      const dateText = `${t.generatedOn}: ${format(new Date(), 'dd/MM/yyyy HH:mm')}`;
      const dateWidth = pdf.getTextWidth(dateText);
      pdf.text(dateText, (pageWidth - dateWidth) / 2, pageHeight - 30);
      
      // RFC at very bottom
      if (company?.rfc) {
        pdf.setFontSize(9);
        pdf.setTextColor(71, 85, 105);
        const rfcText = `RFC: ${company.rfc}`;
        const rfcWidth = pdf.getTextWidth(rfcText);
        pdf.text(rfcText, (pageWidth - rfcWidth) / 2, pageHeight - 20);
      }
      
      // ====== PAGE 2: EXECUTIVE SUMMARY ======
      pdf.addPage();
      currentPage++;
      y = margin;
      pdf.setTextColor(0, 0, 0);
      
      if (currentMetrics) {
        const inc = currentMetrics.income_statement || {};
        const bal = currentMetrics.balance_sheet || {};
        const metrics = currentMetrics.metrics || {};
        
        // ====== AI EXECUTIVE SUMMARY ======
        drawSectionHeader(t.executiveSummary, [99, 102, 241]);
        
        if (aiAnalysis?.executive_summary) {
          pdf.setFillColor(249, 250, 251);
          const summaryLines = wrapText(aiAnalysis.executive_summary, contentWidth - 8);
          const boxHeight = Math.max(summaryLines.length * 5 + 8, 20);
          pdf.rect(margin, y - 2, contentWidth, boxHeight, 'F');
          
          pdf.setFont('helvetica', 'normal');
          pdf.setFontSize(9);
          pdf.setTextColor(55, 65, 81);
          summaryLines.forEach((line, idx) => {
            pdf.text(line, margin + 4, y + 4 + (idx * 5));
          });
          y += boxHeight + 5;
          pdf.setTextColor(0, 0, 0);
        }
        
        // ====== FINANCIAL SUMMARY ======
        drawSectionHeader(t.financialSummary || 'Resumen Financiero', [59, 130, 246]);
        
        // Two columns layout
        const col2X = contentWidth / 2;
        const startY = y;
        
        // Column 1: Income Statement
        pdf.setFontSize(10);
        pdf.setFont('helvetica', 'bold');
        pdf.setTextColor(59, 130, 246);
        pdf.text(t.incomeStatement, margin, y);
        pdf.setTextColor(0, 0, 0);
        y += 6;
        
        const incomeItems = [
          [t.revenue, formatCurrency(inc.ingresos)],
          [t.costOfSales, formatCurrency(inc.costo_ventas)],
          [t.grossProfit, formatCurrency(inc.utilidad_bruta)],
          [t.ebitda, formatCurrency(inc.ebitda || inc.utilidad_operativa)],
          [t.netProfit, formatCurrency(inc.utilidad_neta)],
        ];
        
        incomeItems.forEach(([label, value], idx) => {
          pdf.setFontSize(8);
          pdf.setFont('helvetica', 'normal');
          pdf.text(label + ':', margin, y);
          pdf.setFont('helvetica', 'bold');
          if (idx === incomeItems.length - 1) pdf.setTextColor(16, 185, 129);
          pdf.text(value, margin + 40, y);
          pdf.setTextColor(0, 0, 0);
          y += 5;
        });
        
        // Column 2: Balance Sheet
        y = startY;
        pdf.setFontSize(10);
        pdf.setFont('helvetica', 'bold');
        pdf.setTextColor(34, 197, 94);
        pdf.text(t.balanceSheet, margin + col2X, y);
        pdf.setTextColor(0, 0, 0);
        y += 6;
        
        const balanceItems = [
          [t.totalAssets, formatCurrency(bal.activo_total)],
          [t.currentAssets, formatCurrency(bal.activo_circulante)],
          [t.totalLiabilities, formatCurrency(bal.pasivo_total)],
          [t.equity, formatCurrency(bal.capital_contable)],
        ];
        
        balanceItems.forEach(([label, value]) => {
          pdf.setFontSize(8);
          pdf.setFont('helvetica', 'normal');
          pdf.text(label + ':', margin + col2X, y);
          pdf.setFont('helvetica', 'bold');
          pdf.text(value, margin + col2X + 40, y);
          y += 5;
        });
        
        y = Math.max(y, startY + incomeItems.length * 5 + 6) + 8;
        
        // ====== TREND CHART: Revenue + Net Profit (last 6 months) ======
        if (trendsData.length >= 2) {
          addNewPageIfNeeded(75);
          const trendSlice = trendsData.slice(-6);
          const trendLabels = trendSlice.map(p => p.periodo);
          const revenues = trendSlice.map(p => p.income_statement?.ingresos || 0);
          const netProfits = trendSlice.map(p => p.income_statement?.utilidad_neta || 0);
          
          drawVerticalBarChart(margin, y, contentWidth, 65, trendLabels, [
            { name: t.revenue, color: [59, 130, 246], values: revenues },
            { name: t.netProfit, color: [16, 185, 129], values: netProfits }
          ], { title: language === 'es' ? 'Ingresos y Utilidad Neta - Tendencia' : language === 'pt' ? 'Receita e Lucro Líquido - Tendência' : 'Revenue & Net Profit - Trend' });
          y += 70;
        }
        
        // ====== CAPITAL STRUCTURE CHART ======
        if (bal.activo_total || bal.pasivo_total) {
          addNewPageIfNeeded(35);
          drawStackedBar(margin, y, contentWidth, 25, [
            { label: t.currentAssets, value: bal.activo_circulante || 0, color: [59, 130, 246] },
            { label: t.fixedAssets, value: bal.activo_fijo || 0, color: [99, 102, 241] },
            { label: t.currentLiabilities, value: bal.pasivo_circulante || 0, color: [239, 68, 68] },
            { label: t.longTermLiabilities, value: bal.pasivo_largo_plazo || 0, color: [249, 115, 22] },
            { label: t.equity, value: bal.capital_contable || 0, color: [34, 197, 94] },
          ], { title: language === 'es' ? 'Estructura de Capital' : language === 'pt' ? 'Estrutura de Capital' : 'Capital Structure' });
          y += 30;
        }
        
        // ====== MARGINS SECTION ======
        addNewPageIfNeeded(50);
        drawSectionHeader(t.marginsAnalysis, [34, 197, 94]);
        
        if (aiAnalysis?.profitability_analysis) {
          drawAnalysisText(aiAnalysis.profitability_analysis);
        }
        
        const marginsItems = [
          [t.grossMargin, metrics.margins?.gross_margin?.value, 30, 15],
          [t.ebitdaMargin, metrics.margins?.ebitda_margin?.value, 20, 10],
          [t.operatingMargin, metrics.margins?.operating_margin?.value, 15, 5],
          [t.netMargin, metrics.margins?.net_margin?.value, 10, 3],
        ];
        
        // Margins chart
        addNewPageIfNeeded(35);
        drawHorizontalBarChart(margin, y, contentWidth, 28, marginsItems.map(([lbl, v]) => ({
          label: lbl,
          value: v || 0,
          color: [34, 197, 94],
          unit: '%'
        })));
        y += 32;
        
        marginsItems.forEach(([label, value, good, warn]) => {
          drawMetricRow(label, formatPercent(value), getStatus(value, good, warn));
        });
        y += 5;
        
        // ====== RETURNS SECTION ======
        addNewPageIfNeeded(50);
        drawSectionHeader(t.returnsOnInvestment, [139, 92, 246]);
        
        if (aiAnalysis?.returns_analysis) {
          drawAnalysisText(aiAnalysis.returns_analysis);
        }
        
        const returnsItems = [
          ['ROIC', metrics.returns?.roic?.value, 15, 8, '%'],
          ['ROE', metrics.returns?.roe?.value, 15, 8, '%'],
          ['ROA', metrics.returns?.roa?.value, 8, 4, '%'],
          ['ROCE', metrics.returns?.roce?.value, 12, 6, '%'],
        ];
        
        // Returns chart
        addNewPageIfNeeded(35);
        drawHorizontalBarChart(margin, y, contentWidth, 28, returnsItems.map(([lbl, v]) => ({
          label: lbl,
          value: v || 0,
          color: [139, 92, 246],
          unit: '%'
        })));
        y += 32;
        
        returnsItems.forEach(([label, value, good, warn]) => {
          drawMetricRow(label, formatPercent(value), getStatus(value, good, warn));
        });
        y += 5;
        
        // ====== EFFICIENCY SECTION ======
        addNewPageIfNeeded(60);
        drawSectionHeader(t.operationalEfficiency, [249, 115, 22]);
        
        const efficiencyItems = [
          [t.assetTurnover, formatNumber(metrics.efficiency?.asset_turnover?.value) + 'x'],
          [t.receivablesTurnover, formatNumber(metrics.efficiency?.receivables_turnover?.value) + 'x'],
          [t.inventoryTurnover, formatNumber(metrics.efficiency?.inventory_turnover?.value) + 'x'],
          [t.payablesTurnover, formatNumber(metrics.efficiency?.payables_turnover?.value) + 'x'],
          [t.dso, formatNumber(metrics.efficiency?.dso?.value, 0) + ' ' + t.days],
          [t.dpo, formatNumber(metrics.efficiency?.dpo?.value, 0) + ' ' + t.days],
          [t.dio, formatNumber(metrics.efficiency?.dio?.value, 0) + ' ' + t.days],
          [t.cashConversionCycle, formatNumber(metrics.efficiency?.cash_conversion_cycle?.value, 0) + ' ' + t.days],
        ];
        
        efficiencyItems.forEach(([label, value]) => {
          drawMetricRow(label, value);
        });
        y += 5;
        
        // ====== LIQUIDITY SECTION ======
        addNewPageIfNeeded(60);
        drawSectionHeader(t.liquidityAnalysis, [6, 182, 212]);
        
        if (aiAnalysis?.liquidity_analysis) {
          drawAnalysisText(aiAnalysis.liquidity_analysis);
        }
        
        const liquidityItems = [
          [t.currentRatio, metrics.liquidity?.current_ratio?.value, 2, 1, 'x'],
          [t.quickRatio, metrics.liquidity?.quick_ratio?.value, 1, 0.5, 'x'],
          [t.cashRatio, metrics.liquidity?.cash_ratio?.value, 0.5, 0.2, 'x'],
          [t.workingCapital, metrics.liquidity?.working_capital?.value, 0, -Infinity, '$'],
          [t.cashRunway, metrics.liquidity?.cash_runway?.value, 6, 3, 'months'],
          [t.cashEfficiency, metrics.liquidity?.cash_efficiency?.value, null, null, '%'],
        ];
        
        liquidityItems.forEach(([label, value, good, warn, unit]) => {
          let formatted;
          if (unit === '$') formatted = formatCurrency(value);
          else if (unit === 'x') formatted = formatNumber(value) + 'x';
          else if (unit === '%') formatted = formatPercent(value);
          else if (unit === 'months') formatted = formatNumber(value, 1) + ' ' + (language === 'es' ? 'meses' : 'months');
          else formatted = formatNumber(value);
          const status = good !== null ? getStatus(value, good, warn) : null;
          drawMetricRow(label, formatted, status);
        });
        y += 5;
        
        // ====== SOLVENCY SECTION ======
        addNewPageIfNeeded(70);
        drawSectionHeader(t.solvencyAnalysis, [239, 68, 68]);
        
        if (aiAnalysis?.solvency_analysis) {
          drawAnalysisText(aiAnalysis.solvency_analysis);
        }
        
        const solvencyItems = [
          [t.debtToEquity, metrics.solvency?.debt_to_equity?.value, 1, 2, 'x', true],
          [t.debtToAssets, metrics.solvency?.debt_to_assets?.value, 40, 60, '%', true],
          [t.debtToEbitda, metrics.solvency?.debt_to_ebitda?.value, 3, 5, 'x', true],
          [t.interestCoverage, metrics.solvency?.interest_coverage?.value, 5, 2, 'x', false],
          [t.financialLeverage, metrics.solvency?.financial_leverage?.value, null, null, 'x', null],
          [t.netDebtToEbitda, metrics.solvency?.net_debt_to_ebitda?.value, 2, 3.5, 'x', true],
          [t.equityRatio, metrics.solvency?.equity_ratio?.value, 40, 20, '%', false],
          [language === 'es' ? 'Costo de Deuda' : 'Cost of Debt', metrics.solvency?.cost_of_debt?.value, null, null, '%', null],
        ];
        
        solvencyItems.forEach(([label, value, good, warn, unit, inverse]) => {
          const formatted = unit === '%' ? formatPercent(value) : formatNumber(value) + 'x';
          const status = good !== null ? getStatus(value, good, warn, inverse) : null;
          drawMetricRow(label, formatted, status);
        });
        y += 5;
        
        // ====== RECOMMENDATIONS ======
        if (aiAnalysis?.recommendations) {
          addNewPageIfNeeded(40);
          drawSectionHeader(language === 'es' ? 'Recomendaciones Estratégicas' : 'Strategic Recommendations', [5, 150, 105]);
          drawAnalysisText(aiAnalysis.recommendations);
        }
        
        // ====== TRENDS TABLE WITH AI ANALYSIS ======
        if (trendsData.length > 1) {
          pdf.addPage();
          currentPage++;
          y = margin;
          
          drawSectionHeader(t.monthlyTrends, [99, 102, 241]);
          
          // ====== TRENDS BAR CHART (full series) ======
          {
            const allLabels = trendsData.map(p => p.periodo);
            const allRevenues = trendsData.map(p => p.income_statement?.ingresos || 0);
            const allGross = trendsData.map(p => p.income_statement?.utilidad_bruta || 0);
            const allNet = trendsData.map(p => p.income_statement?.utilidad_neta || 0);
            
            addNewPageIfNeeded(80);
            drawVerticalBarChart(margin, y, contentWidth, 70, allLabels, [
              { name: t.revenue, color: [59, 130, 246], values: allRevenues },
              { name: t.grossProfit, color: [16, 185, 129], values: allGross },
              { name: t.netProfit, color: [139, 92, 246], values: allNet },
            ], { title: language === 'es' ? 'Evolución Mensual: Ingresos, Utilidad Bruta y Neta' : language === 'pt' ? 'Evolução Mensal: Receita, Lucro Bruto e Líquido' : 'Monthly Evolution: Revenue, Gross & Net Profit' });
            y += 75;
          }
          
          // Add AI trends analysis if available
          if (aiAnalysis?.trends_analysis) {
            pdf.setFont(fontFamily, 'normal');
            pdf.setFontSize(bodySize);
            pdf.setTextColor(60, 60, 60);
            const trendLines = wrapText(aiAnalysis.trends_analysis, contentWidth - 6, bodySize);
            trendLines.forEach(line => {
              addNewPageIfNeeded(6);
              pdf.text(line, margin + 3, y);
              y += 5;
            });
            y += 6;
          }
          
          // Generate inline trends analysis if no AI analysis
          if (!aiAnalysis?.trends_analysis && trendsData.length >= 2) {
            // Calculate changes between periods
            const analysisPoints = [];
            for (let i = 1; i < trendsData.length; i++) {
              const current = trendsData[i];
              const prev = trendsData[i - 1];
              const revenueChange = ((current.income_statement?.ingresos - prev.income_statement?.ingresos) / prev.income_statement?.ingresos * 100).toFixed(1);
              const netProfitCurrent = current.income_statement?.utilidad_neta || 0;
              const netProfitPrev = prev.income_statement?.utilidad_neta || 0;
              
              if (netProfitCurrent < 0 && netProfitPrev > 0) {
                analysisPoints.push(language === 'es' 
                  ? `En ${current.periodo} hubo una caída significativa a utilidad neta negativa (${formatCurrency(netProfitCurrent)}), requiriendo investigación de costos.`
                  : `In ${current.periodo} there was a significant drop to negative net profit (${formatCurrency(netProfitCurrent)}), requiring cost investigation.`);
              } else if (netProfitCurrent > 0 && netProfitPrev < 0) {
                analysisPoints.push(language === 'es'
                  ? `${current.periodo} muestra recuperación con utilidad neta positiva de ${formatCurrency(netProfitCurrent)}.`
                  : `${current.periodo} shows recovery with positive net profit of ${formatCurrency(netProfitCurrent)}.`);
              }
              
              if (Math.abs(parseFloat(revenueChange)) > 20) {
                analysisPoints.push(language === 'es'
                  ? `Los ingresos ${parseFloat(revenueChange) > 0 ? 'aumentaron' : 'disminuyeron'} ${Math.abs(parseFloat(revenueChange))}% de ${prev.periodo} a ${current.periodo}.`
                  : `Revenue ${parseFloat(revenueChange) > 0 ? 'increased' : 'decreased'} ${Math.abs(parseFloat(revenueChange))}% from ${prev.periodo} to ${current.periodo}.`);
              }
            }
            
            if (analysisPoints.length > 0) {
              pdf.setFont(fontFamily, 'italic');
              pdf.setFontSize(bodySize - 1);
              pdf.setTextColor(80, 80, 80);
              analysisPoints.forEach(point => {
                const pointLines = wrapText(point, contentWidth - 8, bodySize - 1);
                pointLines.forEach(line => {
                  addNewPageIfNeeded(6);
                  pdf.text('• ' + line, margin + 3, y);
                  y += 5;
                });
              });
              y += 6;
            }
          }
          
          // Table header
          pdf.setFillColor(240, 240, 240);
          pdf.rect(margin, y, contentWidth, 7, 'F');
          pdf.setFontSize(smallSize);
          pdf.setFont(fontFamily, 'bold');
          
          const cols = [
            [t.period, 0],
            [t.revenue, 25],
            [t.grossProfit, 55],
            [t.netProfit, 85],
            [t.grossMargin, 115],
            [t.netMargin, 140],
          ];
          cols.forEach(([text, x]) => pdf.text(text, margin + x, y + 5));
          y += 10;
          
          trendsData.forEach((p) => {
            addNewPageIfNeeded(8);
            pdf.setFontSize(smallSize);
            pdf.setFont(fontFamily, 'normal');
            pdf.text(p.periodo, margin, y);
            pdf.text(formatCurrency(p.income_statement?.ingresos).replace('$', ''), margin + 25, y);
            pdf.text(formatCurrency(p.income_statement?.utilidad_bruta).replace('$', ''), margin + 55, y);
            
            const netProfit = p.income_statement?.utilidad_neta || 0;
            pdf.setTextColor(netProfit >= 0 ? 34 : 239, netProfit >= 0 ? 197 : 68, netProfit >= 0 ? 94 : 68);
            pdf.text(formatCurrency(netProfit).replace('$', ''), margin + 85, y);
            pdf.setTextColor(0, 0, 0);
            
            pdf.text(formatPercent(p.metrics?.margins?.gross_margin?.value), margin + 115, y);
            pdf.text(formatPercent(p.metrics?.margins?.net_margin?.value), margin + 140, y);
            y += 6;
          });
        }
        
        // ====== SANKEY BREAKDOWN ======
        if (sankeyData?.summary) {
          pdf.addPage();
          currentPage++;
          y = margin;
          
          drawSectionHeader(t.sankeyTitle, [59, 130, 246]);
          
          // Add AI analysis for income statement flow if available
          if (aiAnalysis?.income_flow_analysis) {
            pdf.setFont(fontFamily, 'normal');
            pdf.setFontSize(bodySize);
            pdf.setTextColor(60, 60, 60);
            const flowLines = wrapText(aiAnalysis.income_flow_analysis, contentWidth - 6, bodySize);
            flowLines.forEach(line => {
              addNewPageIfNeeded(6);
              pdf.text(line, margin + 3, y);
              y += 5;
            });
            y += 8;
          }
          
          const sankeyItems = [
            [t.revenue, sankeyData.summary.ingresos, '100%', [59, 130, 246]],
            ['(-) ' + t.costOfSales, sankeyData.summary.costo_ventas, ((sankeyData.summary.costo_ventas / sankeyData.summary.ingresos) * 100).toFixed(1) + '%', [239, 68, 68]],
            ['= ' + t.grossProfit, sankeyData.summary.utilidad_bruta, ((sankeyData.summary.utilidad_bruta / sankeyData.summary.ingresos) * 100).toFixed(1) + '%', [34, 197, 94]],
            ['(-) ' + t.operatingExpenses, sankeyData.summary.gastos_operativos, ((sankeyData.summary.gastos_operativos / sankeyData.summary.ingresos) * 100).toFixed(1) + '%', [249, 115, 22]],
            ['= ' + t.operatingProfit, sankeyData.summary.utilidad_operativa, ((sankeyData.summary.utilidad_operativa / sankeyData.summary.ingresos) * 100).toFixed(1) + '%', [16, 185, 129]],
            ['(-) ' + t.taxes, sankeyData.summary.impuestos, ((sankeyData.summary.impuestos / sankeyData.summary.ingresos) * 100).toFixed(1) + '%', [168, 85, 247]],
            ['= ' + t.netProfit.toUpperCase(), sankeyData.summary.utilidad_neta, ((sankeyData.summary.utilidad_neta / sankeyData.summary.ingresos) * 100).toFixed(1) + '%', [5, 150, 105]],
          ];
          
          sankeyItems.forEach(([label, value, pct, color]) => {
            const isTotal = label.startsWith('=');
            if (isTotal) {
              pdf.setFillColor(240, 249, 255);
              pdf.rect(margin, y - 2, contentWidth, 7, 'F');
            }
            pdf.setFontSize(bodySize);
            pdf.setFont(fontFamily, isTotal ? 'bold' : 'normal');
            pdf.setTextColor(...color);
            pdf.text(label, margin + 2, y + 2);
            pdf.setTextColor(0, 0, 0);
            pdf.text(formatCurrency(value), margin + 80, y + 2);
            pdf.text(pct, margin + 140, y + 2);
            y += 8;
          });
        }
      }
      
      // Add footer to all pages
      const totalPages = pdf.internal.getNumberOfPages();
      for (let i = 1; i <= totalPages; i++) {
        pdf.setPage(i);
        
        // Skip footer on cover page (page 1)
        if (i === 1) continue;
        
        pdf.setFontSize(smallSize);
        pdf.setTextColor(120, 120, 120);
        pdf.setFont(fontFamily, 'normal');
        
        // Footer line
        pdf.setDrawColor(200, 200, 200);
        pdf.line(margin, pageHeight - 15, pageWidth - margin, pageHeight - 15);
        
        // Left side: Company name
        pdf.text(company?.nombre || 'Company', margin, pageHeight - 10);
        
        // Center: Report info
        const reportInfoText = `${t.title}  •  ${selectedPeriod}`;
        const reportInfoWidth = pdf.getTextWidth(reportInfoText);
        pdf.text(reportInfoText, (pageWidth - reportInfoWidth) / 2, pageHeight - 10);
        
        // Right side: Page number
        const pageNumText = `${t.page} ${i} ${t.of} ${totalPages}`;
        const pageNumWidth = pdf.getTextWidth(pageNumText);
        pdf.text(pageNumText, pageWidth - margin - pageNumWidth, pageHeight - 10);
        
        // AI badge on second line if applicable
        if (aiAnalysis?.generated_by === 'AI') {
          pdf.setFontSize(smallSize - 1);
          pdf.setTextColor(100, 100, 150);
          const aiText = language === 'es' ? 'Análisis generado por IA (Claude Sonnet)' : 'Analysis generated by AI (Claude Sonnet)';
          const aiTextWidth = pdf.getTextWidth(aiText);
          pdf.text(aiText, (pageWidth - aiTextWidth) / 2, pageHeight - 5);
        }
      }
      
      const periodLabel2 = periodType === 'monthly' ? selectedPeriod : `${periodType}_${selectedPeriod}`;
      const fileName = `${t.title.replace(/\s/g, '_')}_${company?.nombre || 'Company'}_${periodLabel2}.pdf`;
      pdf.save(fileName);
      toast.success(t.pdfSuccess);
    } catch (error) {
      console.error('Error exporting PDF:', error);
      toast.error(t.pdfError);
    } finally {
      setExporting(false);
    }
  };

  // Metric Card Component
  const MetricCard = ({ label, value, format: fmt = 'currency', icon: Icon, color = 'blue', trend, threshold }) => {
    const colors = {
      blue: 'bg-blue-50 border-blue-200',
      green: 'bg-green-50 border-green-200',
      red: 'bg-red-50 border-red-200',
      amber: 'bg-amber-50 border-amber-200',
      purple: 'bg-purple-50 border-purple-200',
    };
    
    const textColors = {
      blue: 'text-blue-700',
      green: 'text-green-700',
      red: 'text-red-700',
      amber: 'text-amber-700',
      purple: 'text-purple-700',
    };
    
    const displayValue = fmt === 'currency' ? formatCurrency(value) 
      : fmt === 'percent' ? formatPercent(value) 
      : fmt === 'number' ? formatNumber(value) + 'x'
      : fmt === 'days' ? formatNumber(value, 0) + ' ' + t.days
      : value;
    
    return (
      <div className={`p-4 rounded-xl border-2 ${colors[color]} transition-all hover:shadow-md`}>
        <div className="flex items-start justify-between">
          <div className="flex-1">
            <p className="text-xs font-semibold uppercase tracking-wider text-gray-500">{label}</p>
            <p className={`text-2xl font-bold mt-1 ${textColors[color]}`}>{displayValue}</p>
          </div>
          {Icon && <Icon className={`w-5 h-5 ${textColors[color]}`} />}
        </div>
        {trend !== undefined && (
          <div className="flex items-center gap-1 mt-2">
            {getTrendIcon(trend)}
            <span className={`text-xs ${trend > 0 ? 'text-green-600' : trend < 0 ? 'text-red-600' : 'text-gray-500'}`}>
              {trend > 0 ? '+' : ''}{trend.toFixed(1)}% {t.vsPreviousPeriod}
            </span>
          </div>
        )}
      </div>
    );
  };

  if (loading) {
    return (
      <div className="p-8 flex items-center justify-center min-h-screen">
        <RefreshCw className="w-8 h-8 animate-spin text-blue-500" />
      </div>
    );
  }

  if (!currentMetrics) {
    return (
      <div className="p-8">
        <Card>
          <CardContent className="py-12 text-center">
            <BarChart3 className="w-12 h-12 mx-auto text-gray-400 mb-4" />
            <h3 className="text-lg font-medium text-gray-900">{language === 'es' ? 'Sin datos financieros' : 'No financial data'}</h3>
            <p className="text-sm text-gray-500 mt-1">
              {language === 'es' ? 'Carga estados financieros desde el módulo de Métricas' : 'Load financial statements from Metrics module'}
            </p>
          </CardContent>
        </Card>
      </div>
    );
  }

  const inc = currentMetrics.income_statement || {};
  const bal = currentMetrics.balance_sheet || {};
  const metrics = currentMetrics.metrics || {};

  return (
    <div className="min-h-screen bg-gradient-to-br from-slate-50 to-slate-100" data-testid="board-report-page">
      {/* Header */}
      <div className="bg-gradient-to-r from-slate-800 to-slate-900 text-white">
        <div className="max-w-7xl mx-auto px-6 py-8">
          <div className="flex flex-col lg:flex-row lg:items-center lg:justify-between gap-4">
            <div>
              <h1 className="text-3xl font-bold">{company?.nombre || 'Company'}</h1>
              <p className="text-slate-300 mt-1 text-lg">{t.title}</p>
              <p className="text-slate-400 text-sm mt-2">
                {t.generatedOn}: {format(new Date(), 'dd/MM/yyyy HH:mm')}
              </p>
              {periodsIncluded.length > 1 && (
                <p className="text-slate-400 text-xs mt-1">
                  {t.periodsIncluded || 'Períodos incluidos'}: {periodsIncluded.join(', ')}
                </p>
              )}
            </div>
            <div className="flex flex-wrap items-center gap-3">
              {/* Language Selector */}
              <Select value={language} onValueChange={setLanguage}>
                <SelectTrigger className="w-36 bg-white/10 border-white/20 text-white" data-testid="language-selector">
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
              
              {/* Period Type Selector */}
              <Select value={periodType} onValueChange={handlePeriodTypeChange}>
                <SelectTrigger className="w-36 bg-white/10 border-white/20 text-white" data-testid="period-type-selector">
                  <Clock className="w-4 h-4 mr-2" />
                  <SelectValue />
                </SelectTrigger>
                <SelectContent>
                  <SelectItem value="monthly">{t.monthly || 'Mensual'}</SelectItem>
                  <SelectItem value="quarterly">{t.quarterly || 'Trimestral'}</SelectItem>
                  <SelectItem value="annual">{t.annual || 'Anual'}</SelectItem>
                </SelectContent>
              </Select>
              
              {/* Period Selector */}
              <Select value={selectedPeriod} onValueChange={setSelectedPeriod}>
                <SelectTrigger className="w-40 bg-white/10 border-white/20 text-white" data-testid="period-selector">
                  <Calendar className="w-4 h-4 mr-2" />
                  <SelectValue />
                </SelectTrigger>
                <SelectContent>
                  {getCurrentPeriodOptions().map(p => (
                    <SelectItem key={p.value} value={p.value}>
                      {p.label}
                      {p.months_available && p.months_total && p.months_available < p.months_total && (
                        <span className="text-xs text-gray-400 ml-1">
                          ({p.months_available}/{p.months_total})
                        </span>
                      )}
                    </SelectItem>
                  ))}
                </SelectContent>
              </Select>
              
              {/* Export Buttons */}
              <Button variant="outline" onClick={exportToExcel} className="bg-white/10 border-white/20 text-white hover:bg-white/20" data-testid="export-excel-btn">
                <FileSpreadsheet className="w-4 h-4 mr-2" />
                Excel
              </Button>
              <Button 
                variant="outline" 
                onClick={() => setPdfConfigOpen(true)} 
                className="bg-white/10 border-white/20 text-white hover:bg-white/20" 
                data-testid="pdf-config-btn"
              >
                <Settings className="w-4 h-4" />
              </Button>
              <Button onClick={exportToPDF} disabled={exporting} className="bg-blue-600 hover:bg-blue-700" data-testid="export-pdf-btn">
                <FileText className="w-4 h-4 mr-2" />
                {exporting ? t.exporting : 'PDF'}
              </Button>
            </div>
          </div>
        </div>
      </div>
      
      {/* PDF Configuration Dialog */}
      <Dialog open={pdfConfigOpen} onOpenChange={setPdfConfigOpen}>
        <DialogContent className="max-w-md">
          <DialogHeader>
            <DialogTitle className="flex items-center gap-2">
              <Settings className="w-5 h-5" />
              {language === 'es' ? 'Configuración del PDF' : 'PDF Settings'}
            </DialogTitle>
          </DialogHeader>
          <div className="space-y-4">
            {/* Font Family */}
            <div className="space-y-2">
              <Label>{language === 'es' ? 'Fuente' : 'Font Family'}</Label>
              <Select value={pdfConfig.fontFamily} onValueChange={(v) => setPdfConfig({...pdfConfig, fontFamily: v})}>
                <SelectTrigger>
                  <SelectValue />
                </SelectTrigger>
                <SelectContent>
                  <SelectItem value="helvetica">Helvetica</SelectItem>
                  <SelectItem value="times">Times</SelectItem>
                  <SelectItem value="courier">Courier</SelectItem>
                </SelectContent>
              </Select>
            </div>
            
            {/* Font Sizes */}
            <div className="grid grid-cols-2 gap-4">
              <div className="space-y-2">
                <Label>{language === 'es' ? 'Título Portada' : 'Cover Title'}</Label>
                <Input 
                  type="number" 
                  min="14" 
                  max="48" 
                  value={pdfConfig.titleSize}
                  onChange={(e) => setPdfConfig({...pdfConfig, titleSize: parseInt(e.target.value) || 28})}
                />
              </div>
              <div className="space-y-2">
                <Label>{language === 'es' ? 'Subtítulos' : 'Subtitles'}</Label>
                <Input 
                  type="number" 
                  min="10" 
                  max="24" 
                  value={pdfConfig.subtitleSize}
                  onChange={(e) => setPdfConfig({...pdfConfig, subtitleSize: parseInt(e.target.value) || 16})}
                />
              </div>
            </div>
            
            <div className="grid grid-cols-2 gap-4">
              <div className="space-y-2">
                <Label>{language === 'es' ? 'Encabezados Sección' : 'Section Headers'}</Label>
                <Input 
                  type="number" 
                  min="8" 
                  max="14" 
                  value={pdfConfig.sectionHeaderSize}
                  onChange={(e) => setPdfConfig({...pdfConfig, sectionHeaderSize: parseInt(e.target.value) || 11})}
                />
              </div>
              <div className="space-y-2">
                <Label>{language === 'es' ? 'Texto Normal' : 'Body Text'}</Label>
                <Input 
                  type="number" 
                  min="7" 
                  max="12" 
                  value={pdfConfig.bodySize}
                  onChange={(e) => setPdfConfig({...pdfConfig, bodySize: parseInt(e.target.value) || 10})}
                />
              </div>
            </div>
            
            <div className="space-y-2">
              <Label>{language === 'es' ? 'Texto Pequeño (footer, notas)' : 'Small Text (footer, notes)'}</Label>
              <Input 
                type="number" 
                min="6" 
                max="10" 
                value={pdfConfig.smallSize}
                onChange={(e) => setPdfConfig({...pdfConfig, smallSize: parseInt(e.target.value) || 8})}
              />
            </div>
            
            {/* Preview */}
            <div className="border rounded-lg p-4 bg-gray-50">
              <p className="text-xs text-gray-500 mb-2">{language === 'es' ? 'Vista previa:' : 'Preview:'}</p>
              <p style={{fontFamily: pdfConfig.fontFamily === 'times' ? 'Times New Roman' : pdfConfig.fontFamily === 'courier' ? 'Courier New' : 'Arial', fontSize: `${pdfConfig.titleSize * 0.5}px`, fontWeight: 'bold'}}>
                {company?.nombre || 'Company Name'}
              </p>
              <p style={{fontFamily: pdfConfig.fontFamily === 'times' ? 'Times New Roman' : pdfConfig.fontFamily === 'courier' ? 'Courier New' : 'Arial', fontSize: `${pdfConfig.bodySize * 0.9}px`}} className="mt-2">
                {language === 'es' ? 'Este es el texto normal del reporte' : 'This is the normal body text'}
              </p>
            </div>
          </div>
          <DialogFooter>
            <Button variant="outline" onClick={() => setPdfConfigOpen(false)}>
              {language === 'es' ? 'Cerrar' : 'Close'}
            </Button>
            <Button onClick={() => {
              setPdfConfigOpen(false);
              exportToPDF();
            }}>
              {language === 'es' ? 'Generar PDF' : 'Generate PDF'}
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>

      {/* Main Content */}
      <div className="max-w-7xl mx-auto px-6 py-8">
        <Tabs value={activeTab} onValueChange={setActiveTab} className="w-full">
          <TabsList className="grid w-full grid-cols-8 mb-8 bg-white shadow-sm">
            <TabsTrigger value="summary" className="gap-2"><BarChart3 className="w-4 h-4" />{t.tabSummary}</TabsTrigger>
            <TabsTrigger value="analysis" className="gap-2"><Brain className="w-4 h-4" />{t.aiAnalysis || 'IA'}</TabsTrigger>
            <TabsTrigger value="margins" className="gap-2"><Percent className="w-4 h-4" />{t.tabMargins}</TabsTrigger>
            <TabsTrigger value="returns" className="gap-2"><Target className="w-4 h-4" />{t.tabReturns}</TabsTrigger>
            <TabsTrigger value="efficiency" className="gap-2"><Activity className="w-4 h-4" />{t.tabEfficiency}</TabsTrigger>
            <TabsTrigger value="liquidity" className="gap-2"><Wallet className="w-4 h-4" />{t.tabLiquidity}</TabsTrigger>
            <TabsTrigger value="solvency" className="gap-2"><Scale className="w-4 h-4" />{t.tabSolvency}</TabsTrigger>
            <TabsTrigger value="trends" className="gap-2"><TrendingUp className="w-4 h-4" />{t.tabTrends}</TabsTrigger>
          </TabsList>

          {/* SUMMARY TAB */}
          <TabsContent value="summary" className="space-y-6">
            {/* AI Executive Summary */}
            {aiAnalysis && (
              <Card className="border-2 border-indigo-100 bg-gradient-to-br from-indigo-50/50 to-purple-50/50">
                <CardHeader className="pb-3">
                  <div className="flex items-center gap-2">
                    <Sparkles className="w-5 h-5 text-indigo-500" />
                    <CardTitle className="text-indigo-900">{t.executiveSummary}</CardTitle>
                    {aiAnalysis.generated_by === 'AI' && (
                      <span className="text-xs bg-indigo-100 text-indigo-600 px-2 py-0.5 rounded-full">Claude Sonnet</span>
                    )}
                  </div>
                </CardHeader>
                <CardContent>
                  <p className="text-gray-700 leading-relaxed">{aiAnalysis.executive_summary}</p>
                </CardContent>
              </Card>
            )}

            {/* Key Metrics */}
            <div className="grid grid-cols-2 md:grid-cols-4 lg:grid-cols-7 gap-4">
              <MetricCard label={t.revenue} value={inc.ingresos} icon={DollarSign} color="blue" />
              <MetricCard label={t.grossProfit} value={inc.utilidad_bruta} icon={TrendingUp} color="green" />
              <MetricCard label={t.ebitda} value={inc.ebitda || inc.utilidad_operativa} icon={Activity} color="purple" />
              <MetricCard label={t.netProfit} value={inc.utilidad_neta} icon={Target} color="green" />
              <MetricCard label={t.totalAssets} value={bal.activo_total} icon={Building2} color="blue" />
              <MetricCard label={t.totalLiabilities} value={bal.pasivo_total} icon={Scale} color="red" />
              <MetricCard label={t.equity} value={bal.capital_contable} icon={Wallet} color="green" />
            </div>

            {/* Sankey Diagram */}
            <Card ref={reportRef}>
              <CardHeader>
                <CardTitle className="flex items-center gap-2">
                  <PieChart className="w-5 h-5 text-blue-500" />
                  {t.sankeyTitle}
                </CardTitle>
                <CardDescription>{t.sankeyDesc}</CardDescription>
              </CardHeader>
              <CardContent>
                {sankeyChartData && (
                  <div className="h-[400px] w-full">
                    <ResponsiveContainer width="100%" height="100%">
                      <Sankey data={sankeyChartData} node={<SankeyNode />} link={<SankeyLink />} nodePadding={40} nodeWidth={10} margin={{ top: 20, right: 200, bottom: 20, left: 20 }}>
                        <Tooltip formatter={(value) => formatCurrency(value)} />
                      </Sankey>
                    </ResponsiveContainer>
                  </div>
                )}
              </CardContent>
            </Card>

            {/* Capital Structure */}
            <Card>
              <CardHeader>
                <CardTitle className="flex items-center gap-2">
                  <Building2 className="w-5 h-5 text-purple-500" />
                  {t.capitalStructure}
                </CardTitle>
              </CardHeader>
              <CardContent>
                <div className="grid grid-cols-1 md:grid-cols-2 gap-8">
                  <ResponsiveContainer width="100%" height={250}>
                    <RechartsPie>
                      <Pie data={capitalStructureData.slice(0, 2)} dataKey="value" nameKey="name" cx="50%" cy="50%" outerRadius={80} label={({ name, percent }) => `${name}: ${(percent * 100).toFixed(0)}%`}>
                        {capitalStructureData.slice(0, 2).map((entry, idx) => <Cell key={idx} fill={entry.fill} />)}
                      </Pie>
                      <Tooltip formatter={(value) => formatCurrency(value)} />
                      <Legend />
                    </RechartsPie>
                  </ResponsiveContainer>
                  <div className="space-y-3">
                    {capitalStructureData.map((item, idx) => (
                      <div key={idx} className="flex items-center justify-between p-3 rounded-lg bg-gray-50">
                        <div className="flex items-center gap-2">
                          <div className="w-3 h-3 rounded" style={{ backgroundColor: item.fill }} />
                          <span className="text-sm font-medium">{item.name}</span>
                        </div>
                        <span className="font-semibold">{formatCurrency(item.value)}</span>
                      </div>
                    ))}
                  </div>
                </div>
              </CardContent>
            </Card>
          </TabsContent>

          {/* AI ANALYSIS TAB */}
          <TabsContent value="analysis" className="space-y-6">
            <Card className="border-2 border-indigo-100 bg-gradient-to-br from-indigo-50 to-purple-50">
              <CardHeader>
                <div className="flex items-center justify-between">
                  <div className="flex items-center gap-3">
                    <div className="p-2 bg-indigo-100 rounded-lg">
                      <Brain className="w-6 h-6 text-indigo-600" />
                    </div>
                    <div>
                      <CardTitle className="text-indigo-900">{t.aiAnalysis}</CardTitle>
                      <CardDescription>{t.aiAnalysisDesc}</CardDescription>
                    </div>
                  </div>
                  <Button 
                    variant="outline" 
                    size="sm" 
                    onClick={() => loadAIAnalysis(selectedPeriod, periodType)}
                    disabled={loadingAnalysis}
                    className="border-indigo-200 text-indigo-700 hover:bg-indigo-100"
                  >
                    <RefreshCw className={`w-4 h-4 mr-2 ${loadingAnalysis ? 'animate-spin' : ''}`} />
                    {t.refreshAnalysis}
                  </Button>
                </div>
              </CardHeader>
              <CardContent>
                {loadingAnalysis ? (
                  <div className="flex items-center justify-center py-12">
                    <RefreshCw className="w-8 h-8 animate-spin text-indigo-500" />
                    <span className="ml-3 text-indigo-600">{t.loadingAnalysis}</span>
                  </div>
                ) : aiAnalysis ? (
                  <div className="space-y-6">
                    {/* Executive Summary */}
                    <div className="bg-white rounded-xl p-5 shadow-sm border border-indigo-100">
                      <div className="flex items-center gap-2 mb-3">
                        <Sparkles className="w-5 h-5 text-indigo-500" />
                        <h3 className="font-semibold text-lg text-indigo-900">{t.executiveSummaryAI}</h3>
                      </div>
                      <p className="text-gray-700 leading-relaxed">{aiAnalysis.executive_summary}</p>
                    </div>

                    <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
                      {/* Profitability Analysis */}
                      <div className="bg-white rounded-xl p-5 shadow-sm border border-green-100">
                        <div className="flex items-center gap-2 mb-3">
                          <div className="p-1.5 bg-green-100 rounded">
                            <Percent className="w-4 h-4 text-green-600" />
                          </div>
                          <h3 className="font-semibold text-green-900">{t.profitabilityAnalysis}</h3>
                        </div>
                        <p className="text-gray-700 text-sm leading-relaxed">{aiAnalysis.profitability_analysis}</p>
                      </div>

                      {/* Returns Analysis */}
                      <div className="bg-white rounded-xl p-5 shadow-sm border border-purple-100">
                        <div className="flex items-center gap-2 mb-3">
                          <div className="p-1.5 bg-purple-100 rounded">
                            <Target className="w-4 h-4 text-purple-600" />
                          </div>
                          <h3 className="font-semibold text-purple-900">{t.returnsAnalysis}</h3>
                        </div>
                        <p className="text-gray-700 text-sm leading-relaxed">{aiAnalysis.returns_analysis}</p>
                      </div>

                      {/* Liquidity Analysis */}
                      <div className="bg-white rounded-xl p-5 shadow-sm border border-cyan-100">
                        <div className="flex items-center gap-2 mb-3">
                          <div className="p-1.5 bg-cyan-100 rounded">
                            <Wallet className="w-4 h-4 text-cyan-600" />
                          </div>
                          <h3 className="font-semibold text-cyan-900">{t.liquidityAnalysisAI}</h3>
                        </div>
                        <p className="text-gray-700 text-sm leading-relaxed">{aiAnalysis.liquidity_analysis}</p>
                      </div>

                      {/* Solvency Analysis */}
                      <div className="bg-white rounded-xl p-5 shadow-sm border border-red-100">
                        <div className="flex items-center gap-2 mb-3">
                          <div className="p-1.5 bg-red-100 rounded">
                            <Scale className="w-4 h-4 text-red-600" />
                          </div>
                          <h3 className="font-semibold text-red-900">{t.solvencyAnalysisAI}</h3>
                        </div>
                        <p className="text-gray-700 text-sm leading-relaxed">{aiAnalysis.solvency_analysis}</p>
                      </div>
                    </div>

                    {/* Strategic Recommendations */}
                    <div className="bg-gradient-to-r from-emerald-50 to-teal-50 rounded-xl p-5 border border-emerald-200">
                      <div className="flex items-center gap-2 mb-3">
                        <Lightbulb className="w-5 h-5 text-emerald-600" />
                        <h3 className="font-semibold text-lg text-emerald-900">{t.strategicRecommendations}</h3>
                      </div>
                      <p className="text-gray-700 leading-relaxed">{aiAnalysis.recommendations}</p>
                    </div>

                    {aiAnalysis.generated_by === 'AI' && (
                      <div className="text-center text-xs text-gray-400 flex items-center justify-center gap-1">
                        <Sparkles className="w-3 h-3" />
                        {t.generatedByAI} • Claude Sonnet
                      </div>
                    )}
                  </div>
                ) : (
                  <div className="text-center py-12 text-gray-500">
                    <Brain className="w-12 h-12 mx-auto mb-3 text-gray-300" />
                    <p>No hay análisis disponible para este período</p>
                    <Button 
                      variant="outline" 
                      className="mt-4"
                      onClick={() => loadAIAnalysis(selectedPeriod, periodType)}
                    >
                      Generar Análisis
                    </Button>
                  </div>
                )}
              </CardContent>
            </Card>
          </TabsContent>

          {/* MARGINS TAB */}
          <TabsContent value="margins" className="space-y-6">
            <div className="grid grid-cols-2 md:grid-cols-5 gap-4">
              <MetricCard label={t.grossMargin} value={metrics.margins?.gross_margin?.value} format="percent" icon={Percent} color={metrics.margins?.gross_margin?.value >= 30 ? 'green' : metrics.margins?.gross_margin?.value >= 15 ? 'amber' : 'red'} />
              <MetricCard label={t.ebitdaMargin} value={metrics.margins?.ebitda_margin?.value} format="percent" icon={Activity} color={metrics.margins?.ebitda_margin?.value >= 20 ? 'green' : metrics.margins?.ebitda_margin?.value >= 10 ? 'amber' : 'red'} />
              <MetricCard label={t.operatingMargin} value={metrics.margins?.operating_margin?.value} format="percent" icon={Calculator} color={metrics.margins?.operating_margin?.value >= 15 ? 'green' : metrics.margins?.operating_margin?.value >= 5 ? 'amber' : 'red'} />
              <MetricCard label={t.netMargin} value={metrics.margins?.net_margin?.value} format="percent" icon={Target} color={metrics.margins?.net_margin?.value >= 10 ? 'green' : metrics.margins?.net_margin?.value >= 3 ? 'amber' : 'red'} />
              <MetricCard label={t.nopatMargin} value={metrics.margins?.nopat_margin?.value} format="percent" icon={DollarSign} color="purple" />
            </div>

            <Card>
              <CardHeader>
                <CardTitle>{t.marginWaterfall}</CardTitle>
              </CardHeader>
              <CardContent>
                <ResponsiveContainer width="100%" height={350}>
                  <BarChart data={waterfallData} layout="vertical">
                    <CartesianGrid strokeDasharray="3 3" />
                    <XAxis type="number" unit="%" />
                    <YAxis type="category" dataKey="name" width={120} tick={{ fontSize: 11 }} />
                    <Tooltip formatter={(value) => `${value.toFixed(1)}%`} />
                    <Bar dataKey="value" radius={[0, 4, 4, 0]}>
                      {waterfallData.map((entry, idx) => <Cell key={idx} fill={entry.fill} />)}
                    </Bar>
                  </BarChart>
                </ResponsiveContainer>
              </CardContent>
            </Card>
          </TabsContent>

          {/* RETURNS TAB */}
          <TabsContent value="returns" className="space-y-6">
            <div className="grid grid-cols-2 md:grid-cols-3 lg:grid-cols-6 gap-4">
              <MetricCard label="ROIC" value={metrics.returns?.roic?.value} format="percent" icon={Target} color={metrics.returns?.roic?.value >= 15 ? 'green' : metrics.returns?.roic?.value >= 8 ? 'amber' : 'red'} />
              <MetricCard label="ROE" value={metrics.returns?.roe?.value} format="percent" icon={TrendingUp} color={metrics.returns?.roe?.value >= 15 ? 'green' : metrics.returns?.roe?.value >= 8 ? 'amber' : 'red'} />
              <MetricCard label="ROCE" value={metrics.returns?.roce?.value} format="percent" icon={Activity} color={metrics.returns?.roce?.value >= 12 ? 'green' : metrics.returns?.roce?.value >= 6 ? 'amber' : 'red'} />
              <MetricCard label="ROA" value={metrics.returns?.roa?.value} format="percent" icon={Building2} color={metrics.returns?.roa?.value >= 8 ? 'green' : metrics.returns?.roa?.value >= 4 ? 'amber' : 'red'} />
              <MetricCard label="RONIC" value={metrics.returns?.ronic?.value} format="percent" icon={ArrowUpRight} color="purple" />
              <MetricCard label="GMROI" value={metrics.returns?.gmroi?.value} format="number" icon={DollarSign} color="blue" />
            </div>

            <Card>
              <CardHeader>
                <CardTitle>{t.returnsTrend}</CardTitle>
              </CardHeader>
              <CardContent>
                <ResponsiveContainer width="100%" height={300}>
                  <LineChart data={trendsChartData}>
                    <CartesianGrid strokeDasharray="3 3" />
                    <XAxis dataKey="periodo" />
                    <YAxis unit="%" />
                    <Tooltip formatter={(value) => `${value.toFixed(1)}%`} />
                    <Legend />
                    <Line type="monotone" dataKey="roe" name="ROE" stroke="#8B5CF6" strokeWidth={2} dot={{ fill: '#8B5CF6' }} />
                    <Line type="monotone" dataKey="roic" name="ROIC" stroke="#F97316" strokeWidth={2} dot={{ fill: '#F97316' }} />
                    <Line type="monotone" dataKey="roa" name="ROA" stroke="#3B82F6" strokeWidth={2} dot={{ fill: '#3B82F6' }} />
                  </LineChart>
                </ResponsiveContainer>
              </CardContent>
            </Card>
          </TabsContent>

          {/* EFFICIENCY TAB */}
          <TabsContent value="efficiency" className="space-y-6">
            <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
              <MetricCard label={t.assetTurnover} value={metrics.efficiency?.asset_turnover?.value} format="number" icon={RefreshCw} color="blue" />
              <MetricCard label={t.receivablesTurnover} value={metrics.efficiency?.receivables_turnover?.value} format="number" icon={Activity} color="green" />
              <MetricCard label={t.inventoryTurnover} value={metrics.efficiency?.inventory_turnover?.value} format="number" icon={RefreshCw} color="purple" />
              <MetricCard label={t.payablesTurnover} value={metrics.efficiency?.payables_turnover?.value} format="number" icon={Activity} color="amber" />
            </div>
            
            <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
              <MetricCard label={t.dso} value={metrics.efficiency?.dso?.value} format="days" icon={Calendar} color={metrics.efficiency?.dso?.value <= 30 ? 'green' : metrics.efficiency?.dso?.value <= 60 ? 'amber' : 'red'} />
              <MetricCard label={t.dpo} value={metrics.efficiency?.dpo?.value} format="days" icon={Calendar} color={metrics.efficiency?.dpo?.value >= 45 ? 'green' : metrics.efficiency?.dpo?.value >= 30 ? 'amber' : 'red'} />
              <MetricCard label={t.dio} value={metrics.efficiency?.dio?.value} format="days" icon={Calendar} color="blue" />
              <MetricCard label={t.cashConversionCycle} value={metrics.efficiency?.cash_conversion_cycle?.value} format="days" icon={RefreshCw} color={metrics.efficiency?.cash_conversion_cycle?.value <= 30 ? 'green' : metrics.efficiency?.cash_conversion_cycle?.value <= 60 ? 'amber' : 'red'} />
            </div>
          </TabsContent>

          {/* LIQUIDITY TAB */}
          <TabsContent value="liquidity" className="space-y-6">
            <div className="grid grid-cols-2 md:grid-cols-3 lg:grid-cols-6 gap-4">
              <MetricCard label={t.currentRatio} value={metrics.liquidity?.current_ratio?.value} format="number" icon={Scale} color={metrics.liquidity?.current_ratio?.value >= 2 ? 'green' : metrics.liquidity?.current_ratio?.value >= 1 ? 'amber' : 'red'} />
              <MetricCard label={t.quickRatio} value={metrics.liquidity?.quick_ratio?.value} format="number" icon={Activity} color={metrics.liquidity?.quick_ratio?.value >= 1 ? 'green' : metrics.liquidity?.quick_ratio?.value >= 0.5 ? 'amber' : 'red'} />
              <MetricCard label={t.cashRatio} value={metrics.liquidity?.cash_ratio?.value} format="number" icon={DollarSign} color={metrics.liquidity?.cash_ratio?.value >= 0.5 ? 'green' : metrics.liquidity?.cash_ratio?.value >= 0.2 ? 'amber' : 'red'} />
              <MetricCard label={t.workingCapital} value={metrics.liquidity?.working_capital?.value} format="currency" icon={Wallet} color={metrics.liquidity?.working_capital?.value >= 0 ? 'green' : 'red'} />
              <MetricCard label={t.cashRunway} value={metrics.liquidity?.cash_runway?.value} format="number" icon={Calendar} color={metrics.liquidity?.cash_runway?.value >= 6 ? 'green' : metrics.liquidity?.cash_runway?.value >= 3 ? 'amber' : 'red'} />
              <MetricCard label={t.cashEfficiency} value={metrics.liquidity?.cash_efficiency?.value} format="percent" icon={Target} color="purple" />
            </div>
          </TabsContent>

          {/* SOLVENCY TAB */}
          <TabsContent value="solvency" className="space-y-6">
            <div className="grid grid-cols-2 md:grid-cols-3 lg:grid-cols-5 gap-4">
              <MetricCard label={t.debtToEquity} value={metrics.solvency?.debt_to_equity?.value} format="number" icon={Scale} color={metrics.solvency?.debt_to_equity?.value <= 1 ? 'green' : metrics.solvency?.debt_to_equity?.value <= 2 ? 'amber' : 'red'} />
              <MetricCard label={t.debtToAssets} value={metrics.solvency?.debt_to_assets?.value} format="percent" icon={Building2} color={metrics.solvency?.debt_to_assets?.value <= 40 ? 'green' : metrics.solvency?.debt_to_assets?.value <= 60 ? 'amber' : 'red'} />
              <MetricCard label={t.debtToEbitda} value={metrics.solvency?.debt_to_ebitda?.value} format="number" icon={Activity} color={metrics.solvency?.debt_to_ebitda?.value <= 3 ? 'green' : metrics.solvency?.debt_to_ebitda?.value <= 5 ? 'amber' : 'red'} />
              <MetricCard label={t.interestCoverage} value={metrics.solvency?.interest_coverage?.value} format="number" icon={Target} color={metrics.solvency?.interest_coverage?.value >= 5 ? 'green' : metrics.solvency?.interest_coverage?.value >= 2 ? 'amber' : 'red'} />
              <MetricCard label={t.financialLeverage} value={metrics.solvency?.financial_leverage?.value} format="number" icon={TrendingUp} color="purple" />
            </div>

            <div className="grid grid-cols-2 md:grid-cols-3 gap-4">
              <MetricCard label={t.netDebtToEbitda} value={metrics.solvency?.net_debt_to_ebitda?.value} format="number" icon={Calculator} color={metrics.solvency?.net_debt_to_ebitda?.value <= 2 ? 'green' : metrics.solvency?.net_debt_to_ebitda?.value <= 3.5 ? 'amber' : 'red'} />
              <MetricCard label={t.equityRatio} value={metrics.solvency?.equity_ratio?.value} format="percent" icon={Wallet} color={metrics.solvency?.equity_ratio?.value >= 40 ? 'green' : metrics.solvency?.equity_ratio?.value >= 20 ? 'amber' : 'red'} />
              <MetricCard label={language === 'es' ? 'Costo de Deuda' : 'Cost of Debt'} value={metrics.solvency?.cost_of_debt?.value} format="percent" icon={Percent} color="blue" />
            </div>
          </TabsContent>

          {/* TRENDS TAB */}
          <TabsContent value="trends" className="space-y-6">
            {/* AI Analysis for Trends */}
            {aiAnalysis?.trends_analysis && (
              <Card className="border-l-4 border-l-purple-500 bg-gradient-to-r from-purple-50 to-white">
                <CardHeader className="pb-2">
                  <CardTitle className="flex items-center gap-2 text-purple-800">
                    <Sparkles className="w-5 h-5" />
                    {language === 'es' ? 'Análisis de Tendencias' : 'Trends Analysis'}
                    <span className="text-xs bg-purple-100 text-purple-700 px-2 py-0.5 rounded-full ml-2">Claude Sonnet</span>
                  </CardTitle>
                </CardHeader>
                <CardContent>
                  <p className="text-gray-700 leading-relaxed">{aiAnalysis.trends_analysis}</p>
                </CardContent>
              </Card>
            )}
            
            <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
              <Card>
                <CardHeader>
                  <CardTitle className="flex items-center gap-2">
                    <DollarSign className="w-5 h-5 text-blue-500" />
                    {t.revenueAndProfit}
                  </CardTitle>
                </CardHeader>
                <CardContent>
                  <ResponsiveContainer width="100%" height={300}>
                    <ComposedChart data={trendsChartData}>
                      <CartesianGrid strokeDasharray="3 3" />
                      <XAxis dataKey="periodo" tick={{ fontSize: 11 }} />
                      <YAxis tickFormatter={(v) => `$${v.toFixed(1)}M`} />
                      <Tooltip formatter={(value) => `$${(value * 1000000).toLocaleString()}`} />
                      <Legend />
                      <Bar dataKey="ingresos" name={t.revenue} fill="#3B82F6" radius={[4, 4, 0, 0]} />
                      <Bar dataKey="utilidadBruta" name={t.grossProfit} fill="#22C55E" radius={[4, 4, 0, 0]} />
                      <Line type="monotone" dataKey="utilidadNeta" name={t.netProfit} stroke="#8B5CF6" strokeWidth={3} dot={{ fill: '#8B5CF6' }} />
                    </ComposedChart>
                  </ResponsiveContainer>
                </CardContent>
              </Card>

              <Card>
                <CardHeader>
                  <CardTitle className="flex items-center gap-2">
                    <TrendingUp className="w-5 h-5 text-green-500" />
                    {t.marginsTrend}
                  </CardTitle>
                </CardHeader>
                <CardContent>
                  <ResponsiveContainer width="100%" height={300}>
                    <LineChart data={trendsChartData}>
                      <CartesianGrid strokeDasharray="3 3" />
                      <XAxis dataKey="periodo" tick={{ fontSize: 11 }} />
                      <YAxis unit="%" />
                      <Tooltip formatter={(value) => `${value.toFixed(1)}%`} />
                      <Legend />
                      <Line type="monotone" dataKey="margenBruto" name={t.grossMargin} stroke="#22C55E" strokeWidth={2} dot={{ fill: '#22C55E' }} />
                      <Line type="monotone" dataKey="margenEbitda" name={t.ebitdaMargin} stroke="#8B5CF6" strokeWidth={2} dot={{ fill: '#8B5CF6' }} />
                      <Line type="monotone" dataKey="margenNeto" name={t.netMargin} stroke="#3B82F6" strokeWidth={2} dot={{ fill: '#3B82F6' }} />
                    </LineChart>
                  </ResponsiveContainer>
                </CardContent>
              </Card>
            </div>

            {/* Comparison Table */}
            <Card>
              <CardHeader>
                <CardTitle>{t.comparison}</CardTitle>
              </CardHeader>
              <CardContent>
                <div className="overflow-x-auto">
                  <table className="w-full text-sm">
                    <thead>
                      <tr className="border-b bg-gray-50">
                        <th className="text-left py-3 px-4 font-semibold">{t.period}</th>
                        <th className="text-right py-3 px-4 font-semibold">{t.revenue}</th>
                        <th className="text-right py-3 px-4 font-semibold">{t.grossProfit}</th>
                        <th className="text-right py-3 px-4 font-semibold">{t.ebitda}</th>
                        <th className="text-right py-3 px-4 font-semibold">{t.netProfit}</th>
                        <th className="text-right py-3 px-4 font-semibold">{t.grossMargin}</th>
                        <th className="text-right py-3 px-4 font-semibold">{t.netMargin}</th>
                      </tr>
                    </thead>
                    <tbody>
                      {trendsData.map((p, idx) => {
                        const prev = idx > 0 ? trendsData[idx - 1] : null;
                        const ingChange = prev ? ((p.income_statement?.ingresos || 0) - (prev.income_statement?.ingresos || 0)) / (prev.income_statement?.ingresos || 1) * 100 : 0;
                        
                        return (
                          <tr key={p.periodo} className="border-b hover:bg-gray-50">
                            <td className="py-3 px-4 font-medium">{p.periodo}</td>
                            <td className="py-3 px-4 text-right">
                              <div>{formatCurrency(p.income_statement?.ingresos)}</div>
                              {prev && (
                                <span className={`text-xs ${ingChange >= 0 ? 'text-green-600' : 'text-red-600'}`}>
                                  {ingChange >= 0 ? '+' : ''}{ingChange.toFixed(1)}%
                                </span>
                              )}
                            </td>
                            <td className="py-3 px-4 text-right">{formatCurrency(p.income_statement?.utilidad_bruta)}</td>
                            <td className="py-3 px-4 text-right">{formatCurrency(p.income_statement?.utilidad_operativa)}</td>
                            <td className={`py-3 px-4 text-right ${(p.income_statement?.utilidad_neta || 0) >= 0 ? 'text-green-600' : 'text-red-600'}`}>
                              {formatCurrency(p.income_statement?.utilidad_neta)}
                            </td>
                            <td className="py-3 px-4 text-right">{formatPercent(p.metrics?.margins?.gross_margin?.value)}</td>
                            <td className="py-3 px-4 text-right">{formatPercent(p.metrics?.margins?.net_margin?.value)}</td>
                          </tr>
                        );
                      })}
                    </tbody>
                  </table>
                </div>
              </CardContent>
            </Card>
          </TabsContent>
        </Tabs>
      </div>
    </div>
  );
};

export default BoardReport;
