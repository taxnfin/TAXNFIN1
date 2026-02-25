import { useState, useEffect, useMemo, useRef } from 'react';
import api from '@/api/axios';
import { Card, CardContent, CardHeader, CardTitle, CardDescription } from '@/components/ui/card';
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from '@/components/ui/select';
import { Tabs, TabsContent, TabsList, TabsTrigger } from '@/components/ui/tabs';
import { Button } from '@/components/ui/button';
import { toast } from 'sonner';
import { format } from 'date-fns';
import { 
  TrendingUp, TrendingDown, Minus, Download, FileText, FileSpreadsheet,
  BarChart3, PieChart, DollarSign, Building2, Target, Activity, Scale,
  Wallet, RefreshCw, Globe, ArrowUpRight, ArrowDownRight, CheckCircle,
  AlertTriangle, XCircle, Percent, Calculator, Calendar
} from 'lucide-react';
import {
  ResponsiveContainer, BarChart, Bar, LineChart, Line, XAxis, YAxis, 
  CartesianGrid, Tooltip, Legend, ComposedChart, Area, Sankey, Layer,
  Cell, PieChart as RechartsPie, Pie
} from 'recharts';
import * as XLSX from 'xlsx';
import { saveAs } from 'file-saver';
import html2canvas from 'html2canvas';
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
  const [periods, setPeriods] = useState([]);
  const [trendsData, setTrendsData] = useState([]);
  const [currentMetrics, setCurrentMetrics] = useState(null);
  const [sankeyData, setSankeyData] = useState(null);
  const [company, setCompany] = useState(null);
  const [loading, setLoading] = useState(true);
  const [exporting, setExporting] = useState(false);
  const [activeTab, setActiveTab] = useState('summary');
  
  const reportRef = useRef(null);
  const t = translations[language];

  useEffect(() => {
    loadData();
  }, []);

  useEffect(() => {
    if (selectedPeriod) {
      loadPeriodData(selectedPeriod);
    }
  }, [selectedPeriod]);

  const loadData = async () => {
    setLoading(true);
    try {
      const [companyRes, periodsRes, trendsRes] = await Promise.all([
        api.get('/companies'),
        api.get('/financial-statements/periods'),
        api.get('/financial-statements/trends')
      ]);
      
      if (companyRes.data?.length > 0) setCompany(companyRes.data[0]);
      setPeriods(periodsRes.data || []);
      setTrendsData(trendsRes.data?.data || []);
      
      if (periodsRes.data?.length > 0) {
        setSelectedPeriod(periodsRes.data[0].periodo);
      }
    } catch (error) {
      toast.error('Error loading data');
    } finally {
      setLoading(false);
    }
  };

  const loadPeriodData = async (periodo) => {
    try {
      const [metricsRes, sankeyRes] = await Promise.all([
        api.get(`/financial-statements/metrics/${periodo}`),
        api.get(`/financial-statements/sankey/${periodo}`)
      ]);
      setCurrentMetrics(metricsRes.data);
      setSankeyData(sankeyRes.data);
    } catch (error) {
      console.error('Error loading period data:', error);
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
    return { nodes: sankeyData.nodes, links: sankeyData.links };
  }, [sankeyData]);

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

  // Export to Excel
  const exportToExcel = () => {
    try {
      const wb = XLSX.utils.book_new();
      
      // Summary
      if (currentMetrics) {
        const inc = currentMetrics.income_statement || {};
        const bal = currentMetrics.balance_sheet || {};
        const summaryData = [
          { [t.keyMetrics]: t.revenue, Value: inc.ingresos || 0 },
          { [t.keyMetrics]: t.grossProfit, Value: inc.utilidad_bruta || 0 },
          { [t.keyMetrics]: t.ebitda, Value: inc.ebitda || inc.utilidad_operativa || 0 },
          { [t.keyMetrics]: t.netProfit, Value: inc.utilidad_neta || 0 },
          { [t.keyMetrics]: t.totalAssets, Value: bal.activo_total || 0 },
          { [t.keyMetrics]: t.totalLiabilities, Value: bal.pasivo_total || 0 },
          { [t.keyMetrics]: t.equity, Value: bal.capital_contable || 0 },
        ];
        XLSX.utils.book_append_sheet(wb, XLSX.utils.json_to_sheet(summaryData), t.tabSummary);
      }
      
      // Margins
      if (currentMetrics?.metrics?.margins) {
        const marginsData = Object.entries(currentMetrics.metrics.margins).map(([key, val]) => ({
          Metric: val.label || key,
          Value: val.value || 0,
          Interpretation: val.interpretation || ''
        }));
        XLSX.utils.book_append_sheet(wb, XLSX.utils.json_to_sheet(marginsData), t.tabMargins);
      }
      
      // Returns
      if (currentMetrics?.metrics?.returns) {
        const returnsData = Object.entries(currentMetrics.metrics.returns).map(([key, val]) => ({
          Metric: val.label || key,
          Value: val.value || 0,
          Interpretation: val.interpretation || ''
        }));
        XLSX.utils.book_append_sheet(wb, XLSX.utils.json_to_sheet(returnsData), t.tabReturns);
      }
      
      // Efficiency
      if (currentMetrics?.metrics?.efficiency) {
        const efficiencyData = Object.entries(currentMetrics.metrics.efficiency).map(([key, val]) => ({
          Metric: val.label || key,
          Value: val.value || 0,
          Interpretation: val.interpretation || ''
        }));
        XLSX.utils.book_append_sheet(wb, XLSX.utils.json_to_sheet(efficiencyData), t.tabEfficiency);
      }
      
      // Liquidity
      if (currentMetrics?.metrics?.liquidity) {
        const liquidityData = Object.entries(currentMetrics.metrics.liquidity).map(([key, val]) => ({
          Metric: val.label || key,
          Value: val.value || 0,
          Interpretation: val.interpretation || ''
        }));
        XLSX.utils.book_append_sheet(wb, XLSX.utils.json_to_sheet(liquidityData), t.tabLiquidity);
      }
      
      // Solvency
      if (currentMetrics?.metrics?.solvency) {
        const solvencyData = Object.entries(currentMetrics.metrics.solvency).map(([key, val]) => ({
          Metric: val.label || key,
          Value: val.value || 0,
          Interpretation: val.interpretation || ''
        }));
        XLSX.utils.book_append_sheet(wb, XLSX.utils.json_to_sheet(solvencyData), t.tabSolvency);
      }
      
      // Trends
      if (trendsData.length > 0) {
        const trendsExport = trendsData.map(p => ({
          [t.period]: p.periodo,
          [t.revenue]: p.income_statement?.ingresos || 0,
          [t.grossProfit]: p.income_statement?.utilidad_bruta || 0,
          [t.ebitda]: p.income_statement?.utilidad_operativa || 0,
          [t.netProfit]: p.income_statement?.utilidad_neta || 0,
          [t.grossMargin + ' %']: p.metrics?.margins?.gross_margin?.value || 0,
          [t.netMargin + ' %']: p.metrics?.margins?.net_margin?.value || 0,
          ['ROE %']: p.metrics?.returns?.roe?.value || 0,
          ['ROIC %']: p.metrics?.returns?.roic?.value || 0,
        }));
        XLSX.utils.book_append_sheet(wb, XLSX.utils.json_to_sheet(trendsExport), t.tabTrends);
      }
      
      const fileName = `${t.title}_${company?.nombre || 'Company'}_${selectedPeriod}.xlsx`;
      const excelBuffer = XLSX.write(wb, { bookType: 'xlsx', type: 'array' });
      saveAs(new Blob([excelBuffer], { type: 'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet' }), fileName);
      toast.success(language === 'es' ? 'Excel exportado exitosamente' : language === 'pt' ? 'Excel exportado com sucesso' : 'Excel exported successfully');
    } catch (error) {
      toast.error('Error exporting Excel');
    }
  };

  // Export to PDF
  const exportToPDF = async () => {
    setExporting(true);
    try {
      const pdf = new jsPDF('p', 'mm', 'a4');
      const pageWidth = pdf.internal.pageSize.getWidth();
      const margin = 15;
      let y = margin;
      
      // Header
      pdf.setFontSize(24);
      pdf.setFont('helvetica', 'bold');
      pdf.setTextColor(15, 23, 42);
      pdf.text(company?.nombre || 'Company', margin, y);
      y += 10;
      
      pdf.setFontSize(16);
      pdf.setTextColor(100, 116, 139);
      pdf.text(t.title, margin, y);
      y += 7;
      
      pdf.setFontSize(10);
      pdf.text(`${t.period}: ${selectedPeriod} | ${t.generatedOn}: ${format(new Date(), 'dd/MM/yyyy HH:mm')}`, margin, y);
      y += 15;
      
      // Executive Summary
      pdf.setFontSize(14);
      pdf.setFont('helvetica', 'bold');
      pdf.setTextColor(15, 23, 42);
      pdf.text(t.executiveSummary, margin, y);
      y += 8;
      
      if (currentMetrics) {
        const inc = currentMetrics.income_statement || {};
        const bal = currentMetrics.balance_sheet || {};
        const metrics = currentMetrics.metrics || {};
        
        pdf.setFontSize(10);
        pdf.setFont('helvetica', 'normal');
        
        const summaryItems = [
          [t.revenue, formatCurrency(inc.ingresos)],
          [t.grossProfit, formatCurrency(inc.utilidad_bruta)],
          [t.ebitda, formatCurrency(inc.ebitda || inc.utilidad_operativa)],
          [t.netProfit, formatCurrency(inc.utilidad_neta)],
          [t.grossMargin, formatPercent(metrics.margins?.gross_margin?.value)],
          [t.netMargin, formatPercent(metrics.margins?.net_margin?.value)],
          [t.totalAssets, formatCurrency(bal.activo_total)],
          [t.equity, formatCurrency(bal.capital_contable)],
        ];
        
        summaryItems.forEach(([label, value]) => {
          pdf.text(label + ':', margin, y);
          pdf.text(value, margin + 50, y);
          y += 5;
        });
        
        y += 10;
        
        // Returns Section
        pdf.setFontSize(12);
        pdf.setFont('helvetica', 'bold');
        pdf.text(t.returnsOnInvestment, margin, y);
        y += 6;
        
        pdf.setFontSize(10);
        pdf.setFont('helvetica', 'normal');
        
        const returnItems = [
          ['ROIC', formatPercent(metrics.returns?.roic?.value)],
          ['ROE', formatPercent(metrics.returns?.roe?.value)],
          ['ROA', formatPercent(metrics.returns?.roa?.value)],
        ];
        
        returnItems.forEach(([label, value]) => {
          pdf.text(label + ':', margin, y);
          pdf.text(value, margin + 30, y);
          y += 5;
        });
        
        y += 10;
        
        // Liquidity Section
        pdf.setFontSize(12);
        pdf.setFont('helvetica', 'bold');
        pdf.text(t.liquidityAnalysis, margin, y);
        y += 6;
        
        pdf.setFontSize(10);
        pdf.setFont('helvetica', 'normal');
        
        const liquidityItems = [
          [t.currentRatio, formatNumber(metrics.liquidity?.current_ratio?.value) + 'x'],
          [t.quickRatio, formatNumber(metrics.liquidity?.quick_ratio?.value) + 'x'],
          [t.workingCapital, formatCurrency(metrics.liquidity?.working_capital?.value)],
        ];
        
        liquidityItems.forEach(([label, value]) => {
          pdf.text(label + ':', margin, y);
          pdf.text(value, margin + 50, y);
          y += 5;
        });
        
        y += 10;
        
        // Solvency Section
        pdf.setFontSize(12);
        pdf.setFont('helvetica', 'bold');
        pdf.text(t.solvencyAnalysis, margin, y);
        y += 6;
        
        pdf.setFontSize(10);
        pdf.setFont('helvetica', 'normal');
        
        const solvencyItems = [
          [t.debtToEquity, formatNumber(metrics.solvency?.debt_to_equity?.value) + 'x'],
          [t.debtToEbitda, formatNumber(metrics.solvency?.debt_to_ebitda?.value) + 'x'],
          [t.interestCoverage, formatNumber(metrics.solvency?.interest_coverage?.value) + 'x'],
        ];
        
        solvencyItems.forEach(([label, value]) => {
          pdf.text(label + ':', margin, y);
          pdf.text(value, margin + 50, y);
          y += 5;
        });
      }
      
      // Capture Sankey if available
      if (reportRef.current) {
        pdf.addPage();
        y = margin;
        
        pdf.setFontSize(14);
        pdf.setFont('helvetica', 'bold');
        pdf.text(t.sankeyTitle, margin, y);
        y += 10;
        
        try {
          const canvas = await html2canvas(reportRef.current, { scale: 1.5, backgroundColor: '#ffffff' });
          const imgData = canvas.toDataURL('image/png');
          const imgWidth = pageWidth - (margin * 2);
          const imgHeight = Math.min((canvas.height * imgWidth) / canvas.width, 150);
          pdf.addImage(imgData, 'PNG', margin, y, imgWidth, imgHeight);
        } catch (e) {
          console.log('Could not capture chart');
        }
      }
      
      const fileName = `${t.title}_${company?.nombre || 'Company'}_${selectedPeriod}.pdf`;
      pdf.save(fileName);
      toast.success(language === 'es' ? 'PDF exportado exitosamente' : language === 'pt' ? 'PDF exportado com sucesso' : 'PDF exported successfully');
    } catch (error) {
      toast.error('Error exporting PDF');
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
          <div className="flex items-center justify-between">
            <div>
              <h1 className="text-3xl font-bold">{company?.nombre || 'Company'}</h1>
              <p className="text-slate-300 mt-1 text-lg">{t.title}</p>
              <p className="text-slate-400 text-sm mt-2">
                {t.period}: {selectedPeriod} • {t.generatedOn}: {format(new Date(), 'dd/MM/yyyy HH:mm')}
              </p>
            </div>
            <div className="flex items-center gap-3">
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
              
              {/* Period Selector */}
              <Select value={selectedPeriod} onValueChange={setSelectedPeriod}>
                <SelectTrigger className="w-32 bg-white/10 border-white/20 text-white" data-testid="period-selector">
                  <Calendar className="w-4 h-4 mr-2" />
                  <SelectValue />
                </SelectTrigger>
                <SelectContent>
                  {periods.map(p => (
                    <SelectItem key={p.periodo} value={p.periodo}>{p.periodo}</SelectItem>
                  ))}
                </SelectContent>
              </Select>
              
              {/* Export Buttons */}
              <Button variant="outline" onClick={exportToExcel} className="bg-white/10 border-white/20 text-white hover:bg-white/20" data-testid="export-excel-btn">
                <FileSpreadsheet className="w-4 h-4 mr-2" />
                Excel
              </Button>
              <Button onClick={exportToPDF} disabled={exporting} className="bg-blue-600 hover:bg-blue-700" data-testid="export-pdf-btn">
                <FileText className="w-4 h-4 mr-2" />
                {exporting ? t.exporting : 'PDF'}
              </Button>
            </div>
          </div>
        </div>
      </div>

      {/* Main Content */}
      <div className="max-w-7xl mx-auto px-6 py-8">
        <Tabs value={activeTab} onValueChange={setActiveTab} className="w-full">
          <TabsList className="grid w-full grid-cols-7 mb-8 bg-white shadow-sm">
            <TabsTrigger value="summary" className="gap-2"><BarChart3 className="w-4 h-4" />{t.tabSummary}</TabsTrigger>
            <TabsTrigger value="margins" className="gap-2"><Percent className="w-4 h-4" />{t.tabMargins}</TabsTrigger>
            <TabsTrigger value="returns" className="gap-2"><Target className="w-4 h-4" />{t.tabReturns}</TabsTrigger>
            <TabsTrigger value="efficiency" className="gap-2"><Activity className="w-4 h-4" />{t.tabEfficiency}</TabsTrigger>
            <TabsTrigger value="liquidity" className="gap-2"><Wallet className="w-4 h-4" />{t.tabLiquidity}</TabsTrigger>
            <TabsTrigger value="solvency" className="gap-2"><Scale className="w-4 h-4" />{t.tabSolvency}</TabsTrigger>
            <TabsTrigger value="trends" className="gap-2"><TrendingUp className="w-4 h-4" />{t.tabTrends}</TabsTrigger>
          </TabsList>

          {/* SUMMARY TAB */}
          <TabsContent value="summary" className="space-y-6">
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
