import { useState, useEffect, useMemo, useRef } from 'react';
import api from '@/api/axios';
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card';
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from '@/components/ui/table';
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from '@/components/ui/select';
import { Tabs, TabsContent, TabsList, TabsTrigger } from '@/components/ui/tabs';
import { toast } from 'sonner';
import { format, addWeeks, addDays } from 'date-fns';
import { 
  TrendingUp, TrendingDown, Calendar, RefreshCw, Wallet, AlertTriangle,
  BarChart3, PieChart, DollarSign, Building2, FileSpreadsheet, Download, FileText, Globe
} from 'lucide-react';
import { Button } from '@/components/ui/button';
import {
  ResponsiveContainer, BarChart, Bar, LineChart, Line, XAxis, YAxis, 
  CartesianGrid, Tooltip, Legend, ComposedChart, Area, Sankey, Layer
} from 'recharts';
import * as XLSX from 'xlsx';
import { saveAs } from 'file-saver';
import html2canvas from 'html2canvas';
import jsPDF from 'jspdf';
import { financialTranslations, languages } from '../utils/financialTranslations';

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

const VARIANCE_THRESHOLD = 20;

// Custom Sankey Node Component
const SankeyNode = ({ x, y, width, height, index, payload, containerWidth }) => {
  const isOut = x + width + 6 > containerWidth;
  const colors = ['#3B82F6', '#EF4444', '#22C55E', '#F97316', '#F97316', '#F97316', '#10B981', '#EF4444', '#A855F7', '#059669'];
  
  return (
    <Layer key={`CustomNode${index}`}>
      <rect
        x={x}
        y={y}
        width={width}
        height={height}
        fill={colors[index % colors.length]}
        fillOpacity="0.9"
        rx={4}
      />
      <text
        textAnchor={isOut ? 'end' : 'start'}
        x={isOut ? x - 6 : x + width + 6}
        y={y + height / 2}
        fontSize="12"
        fontWeight="600"
        fill="#374151"
        dominantBaseline="middle"
      >
        {payload.name}
      </text>
    </Layer>
  );
};

// Custom Sankey Link Component
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
      <path
        d={`
          M${sourceX},${sourceY}
          C${sourceControlX},${sourceY} ${targetControlX},${targetY} ${targetX},${targetY}
          L${targetX},${targetY + linkWidth}
          C${targetControlX},${targetY + linkWidth} ${sourceControlX},${sourceY + linkWidth} ${sourceX},${sourceY + linkWidth}
          Z
        `}
        fill={`url(#${gradientId})`}
        strokeWidth="0"
      />
    </Layer>
  );
};

const Reports = () => {
  const [language, setLanguage] = useState('es');
  const [activeTab, setActiveTab] = useState('cashflow');
  const [payments, setPayments] = useState([]);
  const [cfdis, setCfdis] = useState([]);
  const [bankSummary, setBankSummary] = useState(null);
  const [loading, setLoading] = useState(true);
  const [selectedCurrency, setSelectedCurrency] = useState('MXN');
  const [fxRates, setFxRates] = useState({ MXN: 1, USD: 17.4545 });
  
  // Translation helper
  const t = financialTranslations[language];
  
  // Financial Reports State
  const [trendsData, setTrendsData] = useState([]);
  const [sankeyData, setSankeyData] = useState(null);
  const [selectedPeriod, setSelectedPeriod] = useState('');
  const [periods, setPeriods] = useState([]);
  const [company, setCompany] = useState(null);
  const [exporting, setExporting] = useState(false);

  // Refs for PDF export
  const sankeyRef = useRef(null);
  const financialRef = useRef(null);

  // Export to Excel
  const exportToExcel = () => {
    try {
      const wb = XLSX.utils.book_new();
      
      // Sheet 1: Cash Flow Summary
      const cashflowData = weeksWithBalance.map(w => ({
        'Semana': w.label,
        'Período': w.dateRange,
        'Tipo': w.type,
        'Cobros Real': w.cobrosReales,
        'Pagos Real': w.pagosReales,
        'Cobros Proyectado': w.cobrosProyectados,
        'Pagos Proyectado': w.pagosProyectados,
        'Flujo Neto': w.flujoNeto,
        'Saldo Bancos': w.saldoFinal
      }));
      const wsCashflow = XLSX.utils.json_to_sheet(cashflowData);
      XLSX.utils.book_append_sheet(wb, wsCashflow, 'Flujo de Efectivo');
      
      // Sheet 2: Financial Trends
      if (trendsData.length > 0) {
        const financialData = trendsData.map(p => ({
          'Período': p.periodo,
          'Ingresos': p.income_statement?.ingresos || 0,
          'Costo de Ventas': p.income_statement?.costo_ventas || 0,
          'Utilidad Bruta': p.income_statement?.utilidad_bruta || 0,
          'Gastos Operativos': (p.income_statement?.gastos_venta || 0) + (p.income_statement?.gastos_administracion || 0) + (p.income_statement?.gastos_generales || 0),
          'Utilidad Operativa': p.income_statement?.utilidad_operativa || 0,
          'Utilidad Neta': p.income_statement?.utilidad_neta || 0,
          'Margen Bruto %': p.metrics?.margins?.gross_margin?.value || 0,
          'Margen Neto %': p.metrics?.margins?.net_margin?.value || 0,
          'ROE %': p.metrics?.returns?.roe?.value || 0,
          'ROIC %': p.metrics?.returns?.roic?.value || 0,
          'Activo Total': p.balance_sheet?.activo_total || 0,
          'Pasivo Total': p.balance_sheet?.pasivo_total || 0,
          'Capital Contable': p.balance_sheet?.capital_contable || 0,
        }));
        const wsFinancial = XLSX.utils.json_to_sheet(financialData);
        XLSX.utils.book_append_sheet(wb, wsFinancial, 'Estados Financieros');
      }
      
      // Sheet 3: Detailed Metrics (latest period)
      if (trendsData.length > 0) {
        const latest = trendsData[trendsData.length - 1];
        const metricsData = [];
        
        // Margins
        const margins = latest.metrics?.margins || {};
        Object.keys(margins).forEach(key => {
          metricsData.push({
            'Categoría': 'Márgenes',
            'Métrica': margins[key]?.label || key,
            'Valor': margins[key]?.value || 0,
            'Interpretación': margins[key]?.interpretation || ''
          });
        });
        
        // Returns
        const returns = latest.metrics?.returns || {};
        Object.keys(returns).forEach(key => {
          metricsData.push({
            'Categoría': 'Retorno',
            'Métrica': returns[key]?.label || key,
            'Valor': returns[key]?.value || 0,
            'Interpretación': returns[key]?.interpretation || ''
          });
        });
        
        // Liquidity
        const liquidity = latest.metrics?.liquidity || {};
        Object.keys(liquidity).forEach(key => {
          metricsData.push({
            'Categoría': 'Liquidez',
            'Métrica': liquidity[key]?.label || key,
            'Valor': liquidity[key]?.value || 0,
            'Interpretación': liquidity[key]?.interpretation || ''
          });
        });
        
        // Solvency
        const solvency = latest.metrics?.solvency || {};
        Object.keys(solvency).forEach(key => {
          metricsData.push({
            'Categoría': 'Solvencia',
            'Métrica': solvency[key]?.label || key,
            'Valor': solvency[key]?.value || 0,
            'Interpretación': solvency[key]?.interpretation || ''
          });
        });
        
        const wsMetrics = XLSX.utils.json_to_sheet(metricsData);
        XLSX.utils.book_append_sheet(wb, wsMetrics, 'Métricas Detalladas');
      }
      
      // Sheet 4: Sankey Summary
      if (sankeyData) {
        const sankeyExport = [
          { 'Concepto': 'Ingresos', 'Monto': sankeyData.summary?.ingresos || 0, '% Ingresos': '100%' },
          { 'Concepto': 'Costo de Ventas', 'Monto': sankeyData.summary?.costo_ventas || 0, '% Ingresos': ((sankeyData.summary?.costo_ventas / sankeyData.summary?.ingresos) * 100).toFixed(1) + '%' },
          { 'Concepto': 'Utilidad Bruta', 'Monto': sankeyData.summary?.utilidad_bruta || 0, '% Ingresos': ((sankeyData.summary?.utilidad_bruta / sankeyData.summary?.ingresos) * 100).toFixed(1) + '%' },
          { 'Concepto': 'Gastos Operativos', 'Monto': sankeyData.summary?.gastos_operativos || 0, '% Ingresos': ((sankeyData.summary?.gastos_operativos / sankeyData.summary?.ingresos) * 100).toFixed(1) + '%' },
          { 'Concepto': 'Utilidad Operativa', 'Monto': sankeyData.summary?.utilidad_operativa || 0, '% Ingresos': ((sankeyData.summary?.utilidad_operativa / sankeyData.summary?.ingresos) * 100).toFixed(1) + '%' },
          { 'Concepto': 'Otros Gastos', 'Monto': sankeyData.summary?.otros_gastos || 0, '% Ingresos': ((sankeyData.summary?.otros_gastos / sankeyData.summary?.ingresos) * 100).toFixed(1) + '%' },
          { 'Concepto': 'Impuestos', 'Monto': sankeyData.summary?.impuestos || 0, '% Ingresos': ((sankeyData.summary?.impuestos / sankeyData.summary?.ingresos) * 100).toFixed(1) + '%' },
          { 'Concepto': 'Utilidad Neta', 'Monto': sankeyData.summary?.utilidad_neta || 0, '% Ingresos': ((sankeyData.summary?.utilidad_neta / sankeyData.summary?.ingresos) * 100).toFixed(1) + '%' },
        ];
        const wsSankey = XLSX.utils.json_to_sheet(sankeyExport);
        XLSX.utils.book_append_sheet(wb, wsSankey, 'Estado de Resultados');
      }
      
      // Generate file
      const excelBuffer = XLSX.write(wb, { bookType: 'xlsx', type: 'array' });
      const data = new Blob([excelBuffer], { type: 'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet' });
      const fileName = `Reportes_Financieros_${company?.nombre || 'Empresa'}_${format(new Date(), 'yyyy-MM-dd')}.xlsx`;
      saveAs(data, fileName);
      toast.success('Reporte Excel exportado exitosamente');
    } catch (error) {
      console.error('Error exporting Excel:', error);
      toast.error('Error exportando Excel');
    }
  };

  // Export to PDF
  const exportToPDF = async () => {
    setExporting(true);
    try {
      const pdf = new jsPDF('p', 'mm', 'a4');
      const pageWidth = pdf.internal.pageSize.getWidth();
      const pageHeight = pdf.internal.pageSize.getHeight();
      const margin = 15;
      let yPosition = margin;
      
      // Header
      pdf.setFontSize(20);
      pdf.setFont('helvetica', 'bold');
      pdf.text(company?.nombre || 'Empresa', margin, yPosition);
      yPosition += 8;
      
      pdf.setFontSize(12);
      pdf.setFont('helvetica', 'normal');
      pdf.text('Reporte Financiero', margin, yPosition);
      yPosition += 5;
      
      pdf.setFontSize(10);
      pdf.setTextColor(100);
      pdf.text(`Generado: ${format(new Date(), 'dd/MM/yyyy HH:mm')}`, margin, yPosition);
      pdf.setTextColor(0);
      yPosition += 15;
      
      // Sankey Section
      if (sankeyRef.current && sankeyData) {
        pdf.setFontSize(14);
        pdf.setFont('helvetica', 'bold');
        pdf.text(`Estado de Resultados - ${selectedPeriod}`, margin, yPosition);
        yPosition += 10;
        
        // Capture Sankey as image
        const canvas = await html2canvas(sankeyRef.current, { scale: 2, backgroundColor: '#ffffff' });
        const imgData = canvas.toDataURL('image/png');
        const imgWidth = pageWidth - (margin * 2);
        const imgHeight = (canvas.height * imgWidth) / canvas.width;
        
        if (yPosition + imgHeight > pageHeight - margin) {
          pdf.addPage();
          yPosition = margin;
        }
        
        pdf.addImage(imgData, 'PNG', margin, yPosition, imgWidth, Math.min(imgHeight, 100));
        yPosition += Math.min(imgHeight, 100) + 10;
        
        // Sankey Summary Table
        pdf.setFontSize(10);
        pdf.setFont('helvetica', 'normal');
        
        const summaryData = [
          ['Ingresos', formatMXN(sankeyData.summary?.ingresos), '100%'],
          ['Costo de Ventas', formatMXN(sankeyData.summary?.costo_ventas), ((sankeyData.summary?.costo_ventas / sankeyData.summary?.ingresos) * 100).toFixed(1) + '%'],
          ['Utilidad Bruta', formatMXN(sankeyData.summary?.utilidad_bruta), ((sankeyData.summary?.utilidad_bruta / sankeyData.summary?.ingresos) * 100).toFixed(1) + '%'],
          ['Gastos Operativos', formatMXN(sankeyData.summary?.gastos_operativos), ((sankeyData.summary?.gastos_operativos / sankeyData.summary?.ingresos) * 100).toFixed(1) + '%'],
          ['Utilidad Neta', formatMXN(sankeyData.summary?.utilidad_neta), ((sankeyData.summary?.utilidad_neta / sankeyData.summary?.ingresos) * 100).toFixed(1) + '%'],
        ];
        
        summaryData.forEach(row => {
          if (yPosition > pageHeight - margin) {
            pdf.addPage();
            yPosition = margin;
          }
          pdf.text(row[0], margin, yPosition);
          pdf.text(row[1], margin + 60, yPosition);
          pdf.text(row[2], margin + 110, yPosition);
          yPosition += 6;
        });
      }
      
      // Save PDF
      const fileName = `Reporte_Financiero_${company?.nombre || 'Empresa'}_${selectedPeriod}.pdf`;
      pdf.save(fileName);
      toast.success('Reporte PDF exportado exitosamente');
    } catch (error) {
      console.error('Error exporting PDF:', error);
      toast.error('Error exportando PDF');
    } finally {
      setExporting(false);
    }
  };

  useEffect(() => {
    loadData();
    loadFinancialData();
    loadCompany();
  }, []);

  useEffect(() => {
    if (selectedPeriod) {
      loadSankeyData(selectedPeriod);
    }
  }, [selectedPeriod]);

  const loadCompany = async () => {
    try {
      const res = await api.get('/companies');
      if (res.data && res.data.length > 0) {
        setCompany(res.data[0]);
      }
    } catch (error) {
      console.error('Error loading company:', error);
    }
  };

  const loadData = async () => {
    setLoading(true);
    try {
      const [paymentsRes, cfdisRes, fxRes, bankRes] = await Promise.all([
        api.get('/payments'),
        api.get('/cfdi?limit=500'),
        api.get('/fx-rates/latest'),
        api.get('/bank-accounts/summary')
      ]);
      setPayments(paymentsRes.data || []);
      setCfdis(cfdisRes.data || []);
      setBankSummary(bankRes.data || null);
      
      if (bankRes.data?.tipos_cambio) {
        setFxRates(prev => ({ ...prev, ...bankRes.data.tipos_cambio }));
      } else if (fxRes.data?.rates) {
        setFxRates(prev => ({ ...prev, ...fxRes.data.rates }));
      }
    } catch (error) {
      toast.error('Error cargando reportes');
    } finally {
      setLoading(false);
    }
  };

  const loadFinancialData = async () => {
    try {
      const [trendsRes, periodsRes] = await Promise.all([
        api.get('/financial-statements/trends'),
        api.get('/financial-statements/periods')
      ]);
      
      setTrendsData(trendsRes.data?.data || []);
      setPeriods(periodsRes.data || []);
      
      if (periodsRes.data?.length > 0) {
        setSelectedPeriod(periodsRes.data[0].periodo);
      }
    } catch (error) {
      console.error('Error loading financial data:', error);
    }
  };

  const loadSankeyData = async (periodo) => {
    try {
      const res = await api.get(`/financial-statements/sankey/${periodo}`);
      setSankeyData(res.data);
    } catch (error) {
      console.error('Error loading sankey:', error);
      setSankeyData(null);
    }
  };

  // Get initial bank balance in MXN
  const saldoInicialBancos = useMemo(() => {
    if (!bankSummary) return 0;
    return bankSummary.total_mxn || 0;
  }, [bankSummary]);

  // Convert amount to MXN
  const convertToMXN = (amount, currency) => {
    if (!amount) return 0;
    if (currency === 'MXN' || !currency) return amount;
    const rate = fxRates[currency] || 17.4545;
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

  const formatMXN = (amount) => {
    return `$${(amount || 0).toLocaleString('es-MX', {minimumFractionDigits: 0, maximumFractionDigits: 0})}`;
  };

  // Helper to get Monday of a given date
  const getMonday = (date) => {
    const d = new Date(date);
    const day = d.getDay();
    const diff = d.getDate() - day + (day === 0 ? -6 : 1);
    return new Date(d.setDate(diff));
  };

  const HISTORICAL_WEEKS = 4;
  const FORECAST_WEEKS = 13;
  
  const weeksData = useMemo(() => {
    const today = new Date();
    const currentMonday = getMonday(today);
    
    const weeks = [];
    
    // S1-S4: Semanas históricas (Real)
    for (let i = HISTORICAL_WEEKS; i >= 1; i--) {
      const weekStart = addWeeks(currentMonday, -i);
      const weekEnd = addDays(weekStart, 6);
      const weekEndForComparison = addWeeks(weekStart, 1);
      
      weeks.push({
        weekNum: HISTORICAL_WEEKS - i + 1,
        label: `S${HISTORICAL_WEEKS - i + 1}`,
        weekStart,
        weekEnd,
        weekEndForComparison,
        type: 'REAL',
        isPast: true,
        isCurrent: false,
        isFuture: false,
        dateRange: `${format(weekStart, 'dd/MM')} - ${format(weekEnd, 'dd/MM')}`,
        cobrosReales: 0,
        pagosReales: 0,
        cobrosProyectados: 0,
        pagosProyectados: 0,
        cobrosProyectadosOriginal: 0,
        pagosProyectadosOriginal: 0
      });
    }
    
    // S5: Semana actual (Actual)
    const currentWeekStart = currentMonday;
    const currentWeekEnd = addDays(currentWeekStart, 6);
    weeks.push({
      weekNum: HISTORICAL_WEEKS + 1,
      label: `S${HISTORICAL_WEEKS + 1}`,
      weekStart: currentWeekStart,
      weekEnd: currentWeekEnd,
      weekEndForComparison: addWeeks(currentWeekStart, 1),
      type: 'ACTUAL',
      isPast: false,
      isCurrent: true,
      isFuture: false,
      dateRange: `${format(currentWeekStart, 'dd/MM')} - ${format(currentWeekEnd, 'dd/MM')}`,
      cobrosReales: 0,
      pagosReales: 0,
      cobrosProyectados: 0,
      pagosProyectados: 0,
      cobrosProyectadosOriginal: 0,
      pagosProyectadosOriginal: 0
    });
    
    // S6-S18: 13 semanas futuras proyectadas (Proy)
    for (let i = 1; i <= FORECAST_WEEKS; i++) {
      const weekStart = addWeeks(currentMonday, i);
      const weekEnd = addDays(weekStart, 6);
      const weekEndForComparison = addWeeks(weekStart, 1);
      
      weeks.push({
        weekNum: HISTORICAL_WEEKS + 1 + i,
        label: `S${HISTORICAL_WEEKS + 1 + i}`,
        weekStart,
        weekEnd,
        weekEndForComparison,
        type: 'PROYECTADO',
        isPast: false,
        isCurrent: false,
        isFuture: true,
        dateRange: `${format(weekStart, 'dd/MM')} - ${format(weekEnd, 'dd/MM')}`,
        cobrosReales: 0,
        pagosReales: 0,
        cobrosProyectados: 0,
        pagosProyectados: 0,
        cobrosProyectadosOriginal: 0,
        pagosProyectadosOriginal: 0
      });
    }
    
    const processedBankTxns = new Set();
    
    // Process REAL payments
    payments.forEach(payment => {
      if (payment.estatus !== 'completado') return;
      
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
    
    // Process PROJECTED data
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
      
      if (weeks[weekIdx].type === 'ACTUAL' || weeks[weekIdx].type === 'PROYECTADO') {
        if (cfdi.tipo_cfdi === 'ingreso') {
          weeks[weekIdx].cobrosProyectados += pendienteMXN;
          weeks[weekIdx].cobrosProyectadosOriginal += pendienteMXN;
        } else if (cfdi.tipo_cfdi === 'egreso') {
          weeks[weekIdx].pagosProyectados += pendienteMXN;
          weeks[weekIdx].pagosProyectadosOriginal += pendienteMXN;
        }
      }
      
      if (weeks[weekIdx].type === 'REAL') {
        if (cfdi.tipo_cfdi === 'ingreso') {
          weeks[weekIdx].cobrosProyectadosOriginal += pendienteMXN;
        } else if (cfdi.tipo_cfdi === 'egreso') {
          weeks[weekIdx].pagosProyectadosOriginal += pendienteMXN;
        }
      }
    });
    
    return weeks;
  }, [payments, cfdis, fxRates]);

  const weeksWithBalance = useMemo(() => {
    let runningBalance = saldoInicialBancos;
    
    return weeksData.map((week) => {
      const cobros = week.cobrosReales + (week.isFuture || week.isCurrent ? week.cobrosProyectados : 0);
      const pagos = week.pagosReales + (week.isFuture || week.isCurrent ? week.pagosProyectados : 0);
      const flujoNeto = cobros - pagos;
      
      const saldoInicial = runningBalance;
      const saldoFinal = runningBalance + flujoNeto;
      runningBalance = saldoFinal;
      
      let variacionCobros = 0;
      let variacionPagos = 0;
      let variacionPorcentajeCobros = 0;
      let variacionPorcentajePagos = 0;
      let hasSignificantVariance = false;
      
      if (week.isPast && (week.cobrosProyectadosOriginal > 0 || week.pagosProyectadosOriginal > 0)) {
        if (week.cobrosProyectadosOriginal > 0) {
          variacionCobros = week.cobrosReales - week.cobrosProyectadosOriginal;
          variacionPorcentajeCobros = ((week.cobrosReales - week.cobrosProyectadosOriginal) / week.cobrosProyectadosOriginal) * 100;
          if (Math.abs(variacionPorcentajeCobros) > VARIANCE_THRESHOLD) {
            hasSignificantVariance = true;
          }
        }
        
        if (week.pagosProyectadosOriginal > 0) {
          variacionPagos = week.pagosReales - week.pagosProyectadosOriginal;
          variacionPorcentajePagos = ((week.pagosReales - week.pagosProyectadosOriginal) / week.pagosProyectadosOriginal) * 100;
          if (Math.abs(variacionPorcentajePagos) > VARIANCE_THRESHOLD) {
            hasSignificantVariance = true;
          }
        }
      }
      
      return {
        ...week,
        saldoInicial,
        saldoFinal,
        flujoNeto,
        variacionCobros,
        variacionPagos,
        variacionPorcentajeCobros,
        variacionPorcentajePagos,
        hasSignificantVariance
      };
    });
  }, [weeksData, saldoInicialBancos]);

  const totals = useMemo(() => {
    return weeksWithBalance.reduce((acc, week) => {
      acc.cobrosReales += week.cobrosReales;
      acc.pagosReales += week.pagosReales;
      acc.cobrosProyectados += week.cobrosProyectados;
      acc.pagosProyectados += week.pagosProyectados;
      return acc;
    }, { cobrosReales: 0, pagosReales: 0, cobrosProyectados: 0, pagosProyectados: 0 });
  }, [weeksWithBalance]);

  const saldoFinalProyectado = weeksWithBalance.length > 0 
    ? weeksWithBalance[weeksWithBalance.length - 1].saldoFinal 
    : saldoInicialBancos;

  // Prepare trends chart data
  const trendsChartData = useMemo(() => {
    return trendsData.map(p => ({
      periodo: p.periodo,
      ingresos: p.income_statement?.ingresos || 0,
      utilidadNeta: p.income_statement?.utilidad_neta || 0,
      utilidadBruta: p.income_statement?.utilidad_bruta || 0,
      margenBruto: p.metrics?.margins?.gross_margin?.value || 0,
      margenNeto: p.metrics?.margins?.net_margin?.value || 0,
      roe: p.metrics?.returns?.roe?.value || 0,
      roic: p.metrics?.returns?.roic?.value || 0,
    }));
  }, [trendsData]);

  // Prepare Sankey data for Recharts
  const sankeyChartData = useMemo(() => {
    if (!sankeyData) return null;
    return {
      nodes: sankeyData.nodes.map((n, i) => ({ ...n, fill: ['#3B82F6', '#EF4444', '#22C55E', '#F97316', '#F97316', '#F97316', '#10B981', '#EF4444', '#A855F7', '#059669'][i] })),
      links: sankeyData.links
    };
  }, [sankeyData]);

  if (loading) return <div className="p-8">{t.loading}</div>;

  return (
    <div className="p-8 space-y-6" data-testid="reports-page">
      {/* Header */}
      <div className="flex justify-between items-start">
        <div>
          <h1 className="text-4xl font-bold text-[#0F172A] mb-2" style={{fontFamily: 'Manrope'}}>{t.reports}</h1>
          <p className="text-[#64748B]">{t.financialAnalysisAndCashflow}</p>
        </div>
        <div className="flex gap-2 items-center">
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
          
          <Button variant="outline" onClick={exportToExcel} className="gap-2" data-testid="export-excel-btn">
            <FileSpreadsheet size={16} />
            Excel
          </Button>
          <Button variant="outline" onClick={exportToPDF} disabled={exporting} className="gap-2" data-testid="export-pdf-btn">
            <FileText size={16} />
            {exporting ? t.exporting : 'PDF'}
          </Button>
          <Button variant="outline" size="icon" onClick={() => { loadData(); loadFinancialData(); }}>
            <RefreshCw size={16} />
          </Button>
        </div>
      </div>

      {/* Tabs */}
      <Tabs value={activeTab} onValueChange={setActiveTab} className="w-full">
        <TabsList className="grid w-full grid-cols-3 lg:w-[600px]">
          <TabsTrigger value="cashflow" className="gap-2" data-testid="tab-cashflow">
            <Wallet size={16} /> {t.cashflow}
          </TabsTrigger>
          <TabsTrigger value="financial" className="gap-2" data-testid="tab-financial">
            <BarChart3 size={16} /> {t.financialStatements}
          </TabsTrigger>
          <TabsTrigger value="sankey" className="gap-2" data-testid="tab-sankey">
            <PieChart size={16} /> Sankey P&L
          </TabsTrigger>
        </TabsList>

        {/* CASH FLOW TAB */}
        <TabsContent value="cashflow" className="space-y-6">
          <div className="flex justify-between items-center">
            <p className="text-xs text-[#94A3B8]">
              S1-S4 = Historial • S5 = Semana actual • S6-S18 = Proyección 13 semanas
            </p>
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
          </div>

          {/* Bank Balance Summary Cards */}
          <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
            <Card className="border-blue-200 bg-gradient-to-br from-blue-50 to-blue-100">
              <CardHeader className="pb-2">
                <CardTitle className="text-sm text-blue-800 flex items-center gap-2">
                  <Wallet size={16} />
                  {t.initialBankBalance}
                </CardTitle>
              </CardHeader>
              <CardContent>
                <p className="text-2xl font-bold mono text-blue-700">
                  {formatCurrency(saldoInicialBancos)}
                </p>
              </CardContent>
            </Card>

            <Card className={`border-2 ${(totals.cobrosReales - totals.pagosReales) >= 0 ? 'border-green-400 bg-gradient-to-br from-green-50 to-green-100' : 'border-red-400 bg-gradient-to-br from-red-50 to-red-100'}`}>
              <CardHeader className="pb-2">
                <CardTitle className="text-sm text-gray-800 flex items-center gap-2">
                  {(totals.cobrosReales - totals.pagosReales) >= 0 ? <TrendingUp size={16} /> : <TrendingDown size={16} />}
                  {t.realNetFlow} (S1-S5)
                </CardTitle>
              </CardHeader>
              <CardContent>
                <p className={`text-2xl font-bold mono ${(totals.cobrosReales - totals.pagosReales) >= 0 ? 'text-green-700' : 'text-red-700'}`}>
                  {(totals.cobrosReales - totals.pagosReales) >= 0 ? '+' : ''}{formatCurrency(totals.cobrosReales - totals.pagosReales)}
                </p>
              </CardContent>
            </Card>

            <Card className={`border-2 ${saldoFinalProyectado >= 0 ? 'border-emerald-400 bg-gradient-to-br from-emerald-50 to-emerald-100' : 'border-red-400 bg-gradient-to-br from-red-50 to-red-100'}`}>
              <CardHeader className="pb-2">
                <CardTitle className="text-sm text-gray-800 flex items-center gap-2">
                  <Calendar size={16} />
                  {t.projectedBalance} S18
                </CardTitle>
              </CardHeader>
              <CardContent>
                <p className={`text-2xl font-bold mono ${saldoFinalProyectado >= 0 ? 'text-emerald-700' : 'text-red-700'}`}>
                  {formatCurrency(saldoFinalProyectado)}
                </p>
              </CardContent>
            </Card>
          </div>

          {/* Main Table */}
          <Card className="border-[#E2E8F0]">
            <CardHeader className="pb-2">
              <CardTitle className="flex items-center gap-2 text-lg">
                <Calendar size={20} />
                {t.cashflowWithBankBalance}
              </CardTitle>
            </CardHeader>
            <CardContent>
              <div className="overflow-x-auto">
                <Table className="text-sm">
                  <TableHeader>
                    <TableRow className="bg-gray-50">
                      <TableHead className="w-14 font-bold">{t.wk}</TableHead>
                      <TableHead className="w-28">{t.period}</TableHead>
                      <TableHead className="w-16 text-center">{t.type}</TableHead>
                      <TableHead className="text-right">{t.realCollections}</TableHead>
                      <TableHead className="text-right">{t.realPayments}</TableHead>
                      <TableHead className="text-right bg-gray-100">{t.projCollections}</TableHead>
                      <TableHead className="text-right bg-gray-100">{t.projPayments}</TableHead>
                      <TableHead className="text-right font-bold">{t.netFlow}</TableHead>
                      <TableHead className="text-right font-bold bg-blue-50">{t.bankBalance}</TableHead>
                    </TableRow>
                  </TableHeader>
                  <TableBody>
                    <TableRow className="bg-blue-50 border-b-2 border-blue-200">
                      <TableCell colSpan={8} className="font-semibold text-blue-800">
                        {t.initialBankBalanceRow}
                      </TableCell>
                      <TableCell className="mono text-right font-bold text-blue-700 bg-blue-100">
                        {formatCurrency(saldoInicialBancos)}
                      </TableCell>
                    </TableRow>
                    
                    {weeksWithBalance.map((week) => (
                      <TableRow 
                        key={week.label} 
                        className={`
                          ${week.isCurrent ? 'bg-blue-50 border-l-4 border-l-blue-500' : ''} 
                          ${week.isPast ? '' : 'bg-gray-50/50'}
                          ${week.saldoFinal < 0 ? 'bg-red-50' : ''}
                        `}
                      >
                        <TableCell className="mono font-bold">{week.label}</TableCell>
                        <TableCell className="text-xs">{week.dateRange}</TableCell>
                        <TableCell className="text-center">
                          {week.type === 'REAL' && (
                            <span className="px-1.5 py-0.5 text-xs rounded bg-green-100 text-green-800 font-medium">{t.real}</span>
                          )}
                          {week.type === 'ACTUAL' && (
                            <span className="px-1.5 py-0.5 text-xs rounded bg-blue-100 text-blue-800 font-semibold">{t.current}</span>
                          )}
                          {week.type === 'PROYECTADO' && (
                            <span className="px-1.5 py-0.5 text-xs rounded bg-gray-100 text-gray-600">{t.proj}</span>
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
                        <TableCell className={`mono text-right font-bold ${week.flujoNeto >= 0 ? 'text-green-700' : 'text-red-700'}`}>
                          {week.flujoNeto !== 0 ? (
                            <>{week.flujoNeto >= 0 ? '+' : ''}{formatCurrency(week.flujoNeto)}</>
                          ) : '-'}
                        </TableCell>
                        <TableCell className={`mono text-right font-bold bg-blue-50 ${week.saldoFinal < 0 ? 'text-red-700 bg-red-100' : 'text-blue-700'}`}>
                          {formatCurrency(week.saldoFinal)}
                        </TableCell>
                      </TableRow>
                    ))}
                    
                    <TableRow className="bg-[#0F172A] text-white font-bold">
                      <TableCell colSpan={3} className="font-bold">{t.total}</TableCell>
                      <TableCell className="mono text-right text-green-400">{formatCurrency(totals.cobrosReales)}</TableCell>
                      <TableCell className="mono text-right text-red-400">{formatCurrency(totals.pagosReales)}</TableCell>
                      <TableCell className="mono text-right text-gray-400">{formatCurrency(totals.cobrosProyectados)}</TableCell>
                      <TableCell className="mono text-right text-gray-400">{formatCurrency(totals.pagosProyectados)}</TableCell>
                      <TableCell className={`mono text-right font-bold ${(totals.cobrosReales + totals.cobrosProyectados - totals.pagosReales - totals.pagosProyectados) >= 0 ? 'text-green-400' : 'text-red-400'}`}>
                        {formatCurrency(totals.cobrosReales + totals.cobrosProyectados - totals.pagosReales - totals.pagosProyectados)}
                      </TableCell>
                      <TableCell className={`mono text-right font-bold ${saldoFinalProyectado >= 0 ? 'text-blue-400' : 'text-red-400'}`}>
                        {formatCurrency(saldoFinalProyectado)}
                      </TableCell>
                    </TableRow>
                  </TableBody>
                </Table>
              </div>
            </CardContent>
          </Card>
        </TabsContent>

        {/* FINANCIAL STATEMENTS TAB */}
        <TabsContent value="financial" className="space-y-6">
          {trendsData.length === 0 ? (
            <Card>
              <CardContent className="py-12 text-center">
                <FileSpreadsheet className="w-12 h-12 mx-auto text-gray-400 mb-4" />
                <h3 className="text-lg font-medium text-gray-900">{t.noFinancialData}</h3>
                <p className="text-sm text-gray-500 mt-1">
                  {t.uploadFromFinancialMetrics}
                </p>
              </CardContent>
            </Card>
          ) : (
            <>
              {/* Summary Cards */}
              <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
                <Card className="bg-gradient-to-br from-blue-50 to-blue-100 border-blue-200">
                  <CardHeader className="pb-2">
                    <CardTitle className="text-sm text-blue-800">{t.periods}</CardTitle>
                  </CardHeader>
                  <CardContent>
                    <p className="text-3xl font-bold text-blue-700">{trendsData.length}</p>
                  </CardContent>
                </Card>
                <Card className="bg-gradient-to-br from-green-50 to-green-100 border-green-200">
                  <CardHeader className="pb-2">
                    <CardTitle className="text-sm text-green-800">{t.revenueLastPeriod}</CardTitle>
                  </CardHeader>
                  <CardContent>
                    <p className="text-2xl font-bold text-green-700">
                      {formatMXN(trendsData[trendsData.length - 1]?.income_statement?.ingresos)}
                    </p>
                  </CardContent>
                </Card>
                <Card className="bg-gradient-to-br from-purple-50 to-purple-100 border-purple-200">
                  <CardHeader className="pb-2">
                    <CardTitle className="text-sm text-purple-800">{t.netProfitLast}</CardTitle>
                  </CardHeader>
                  <CardContent>
                    <p className="text-2xl font-bold text-purple-700">
                      {formatMXN(trendsData[trendsData.length - 1]?.income_statement?.utilidad_neta)}
                    </p>
                  </CardContent>
                </Card>
                <Card className="bg-gradient-to-br from-amber-50 to-amber-100 border-amber-200">
                  <CardHeader className="pb-2">
                    <CardTitle className="text-sm text-amber-800">{t.roeLastPeriod}</CardTitle>
                  </CardHeader>
                  <CardContent>
                    <p className="text-2xl font-bold text-amber-700">
                      {(trendsData[trendsData.length - 1]?.metrics?.returns?.roe?.value || 0).toFixed(1)}%
                    </p>
                  </CardContent>
                </Card>
              </div>

              {/* Trends Charts */}
              <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
                {/* Revenue & Profit Chart */}
                <Card>
                  <CardHeader>
                    <CardTitle className="text-base flex items-center gap-2">
                      <DollarSign className="w-5 h-5 text-blue-500" />
                      {t.revenueAndProfitByPeriod}
                    </CardTitle>
                  </CardHeader>
                  <CardContent>
                    <ResponsiveContainer width="100%" height={300}>
                      <ComposedChart data={trendsChartData}>
                        <CartesianGrid strokeDasharray="3 3" />
                        <XAxis dataKey="periodo" tick={{ fontSize: 11 }} />
                        <YAxis tickFormatter={(v) => `$${(v/1000000).toFixed(1)}M`} />
                        <Tooltip formatter={(value) => formatMXN(value)} />
                        <Legend />
                        <Bar dataKey="ingresos" name={t.revenue} fill="#3B82F6" radius={[4, 4, 0, 0]} />
                        <Bar dataKey="utilidadBruta" name={t.grossProfit} fill="#22C55E" radius={[4, 4, 0, 0]} />
                        <Line type="monotone" dataKey="utilidadNeta" name={t.netProfit} stroke="#8B5CF6" strokeWidth={3} dot={{ fill: '#8B5CF6' }} />
                      </ComposedChart>
                    </ResponsiveContainer>
                  </CardContent>
                </Card>

                {/* Margins Chart */}
                <Card>
                  <CardHeader>
                    <CardTitle className="text-base flex items-center gap-2">
                      <TrendingUp className="w-5 h-5 text-green-500" />
                      {t.marginsByPeriod}
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
                        <Line type="monotone" dataKey="margenNeto" name={t.netMargin} stroke="#3B82F6" strokeWidth={2} dot={{ fill: '#3B82F6' }} />
                      </LineChart>
                    </ResponsiveContainer>
                  </CardContent>
                </Card>

                {/* Return Metrics Chart */}
                <Card>
                  <CardHeader>
                    <CardTitle className="text-base flex items-center gap-2">
                      <Building2 className="w-5 h-5 text-purple-500" />
                      {t.returnOnInvestment}
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
                        <Line type="monotone" dataKey="roe" name="ROE" stroke="#8B5CF6" strokeWidth={2} dot={{ fill: '#8B5CF6' }} />
                        <Line type="monotone" dataKey="roic" name="ROIC" stroke="#F97316" strokeWidth={2} dot={{ fill: '#F97316' }} />
                      </LineChart>
                    </ResponsiveContainer>
                  </CardContent>
                </Card>

                {/* Comparative Table */}
                <Card>
                  <CardHeader>
                    <CardTitle className="text-base flex items-center gap-2">
                      <BarChart3 className="w-5 h-5 text-amber-500" />
                      {t.periodComparison}
                    </CardTitle>
                  </CardHeader>
                  <CardContent>
                    <Table className="text-sm">
                      <TableHeader>
                        <TableRow>
                          <TableHead>{t.period}</TableHead>
                          <TableHead className="text-right">{t.revenue}</TableHead>
                          <TableHead className="text-right">{t.netProfit}</TableHead>
                          <TableHead className="text-right">{t.margin} %</TableHead>
                        </TableRow>
                      </TableHeader>
                      <TableBody>
                        {trendsData.map((p, idx) => {
                          const prev = idx > 0 ? trendsData[idx - 1] : null;
                          const ingChange = prev ? ((p.income_statement?.ingresos || 0) - (prev.income_statement?.ingresos || 0)) / (prev.income_statement?.ingresos || 1) * 100 : 0;
                          
                          return (
                            <TableRow key={p.periodo}>
                              <TableCell className="font-medium">{p.periodo}</TableCell>
                              <TableCell className="text-right">
                                <div>{formatMXN(p.income_statement?.ingresos)}</div>
                                {prev && (
                                  <span className={`text-xs ${ingChange >= 0 ? 'text-green-600' : 'text-red-600'}`}>
                                    {ingChange >= 0 ? '+' : ''}{ingChange.toFixed(1)}%
                                  </span>
                                )}
                              </TableCell>
                              <TableCell className={`text-right ${(p.income_statement?.utilidad_neta || 0) >= 0 ? 'text-green-600' : 'text-red-600'}`}>
                                {formatMXN(p.income_statement?.utilidad_neta)}
                              </TableCell>
                              <TableCell className="text-right font-medium">
                                {(p.metrics?.margins?.net_margin?.value || 0).toFixed(1)}%
                              </TableCell>
                            </TableRow>
                          );
                        })}
                      </TableBody>
                    </Table>
                  </CardContent>
                </Card>
              </div>
            </>
          )}
        </TabsContent>

        {/* SANKEY TAB */}
        <TabsContent value="sankey" className="space-y-6">
          {/* Company Header */}
          <Card className="bg-gradient-to-r from-slate-800 to-slate-900 text-white">
            <CardContent className="py-6">
              <div className="flex items-center justify-between">
                <div>
                  <h2 className="text-2xl font-bold">{company?.nombre || t.company}</h2>
                  <p className="text-slate-300 mt-1">{t.incomeStatementSankeyDiagram}</p>
                </div>
                <div className="flex items-center gap-4">
                  <Select value={selectedPeriod} onValueChange={setSelectedPeriod}>
                    <SelectTrigger className="w-40 bg-white/10 border-white/20 text-white" data-testid="sankey-period-selector">
                      <SelectValue placeholder={t.period} />
                    </SelectTrigger>
                    <SelectContent>
                      {periods.map((p) => (
                        <SelectItem key={p.periodo} value={p.periodo}>
                          {p.periodo}
                        </SelectItem>
                      ))}
                    </SelectContent>
                  </Select>
                </div>
              </div>
            </CardContent>
          </Card>

          {!sankeyData ? (
            <Card>
              <CardContent className="py-12 text-center">
                <PieChart className="w-12 h-12 mx-auto text-gray-400 mb-4" />
                <h3 className="text-lg font-medium text-gray-900">{t.noData}</h3>
                <p className="text-sm text-gray-500 mt-1">
                  {t.selectPeriod}
                </p>
              </CardContent>
            </Card>
          ) : (
            <>
              {/* Sankey Diagram */}
              <Card ref={sankeyRef}>
                <CardHeader>
                  <CardTitle className="flex items-center gap-2">
                    <PieChart className="w-5 h-5 text-blue-500" />
                    {t.sankeyTitle} - {selectedPeriod}
                  </CardTitle>
                  <CardDescription>
                    {t.sankeyDesc}
                  </CardDescription>
                </CardHeader>
                <CardContent>
                  <div className="h-[500px] w-full">
                    <ResponsiveContainer width="100%" height="100%">
                      <Sankey
                        data={sankeyChartData}
                        node={<SankeyNode />}
                        link={<SankeyLink />}
                        nodePadding={50}
                        nodeWidth={10}
                        margin={{ top: 20, right: 200, bottom: 20, left: 20 }}
                      >
                        <Tooltip 
                          formatter={(value) => formatMXN(value)}
                          labelFormatter={(name) => name}
                        />
                      </Sankey>
                    </ResponsiveContainer>
                  </div>
                </CardContent>
              </Card>

              {/* Summary Cards */}
              <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
                <Card className="bg-blue-50 border-blue-200">
                  <CardHeader className="pb-2">
                    <CardTitle className="text-sm text-blue-800">Ingresos</CardTitle>
                  </CardHeader>
                  <CardContent>
                    <p className="text-2xl font-bold text-blue-700">{formatMXN(sankeyData.summary?.ingresos)}</p>
                    <p className="text-xs text-blue-600 mt-1">100%</p>
                  </CardContent>
                </Card>
                <Card className="bg-red-50 border-red-200">
                  <CardHeader className="pb-2">
                    <CardTitle className="text-sm text-red-800">Costo de Ventas</CardTitle>
                  </CardHeader>
                  <CardContent>
                    <p className="text-2xl font-bold text-red-700">{formatMXN(sankeyData.summary?.costo_ventas)}</p>
                    <p className="text-xs text-red-600 mt-1">
                      {((sankeyData.summary?.costo_ventas / sankeyData.summary?.ingresos) * 100 || 0).toFixed(1)}%
                    </p>
                  </CardContent>
                </Card>
                <Card className="bg-green-50 border-green-200">
                  <CardHeader className="pb-2">
                    <CardTitle className="text-sm text-green-800">Utilidad Bruta</CardTitle>
                  </CardHeader>
                  <CardContent>
                    <p className="text-2xl font-bold text-green-700">{formatMXN(sankeyData.summary?.utilidad_bruta)}</p>
                    <p className="text-xs text-green-600 mt-1">
                      {((sankeyData.summary?.utilidad_bruta / sankeyData.summary?.ingresos) * 100 || 0).toFixed(1)}%
                    </p>
                  </CardContent>
                </Card>
                <Card className="bg-emerald-50 border-emerald-200">
                  <CardHeader className="pb-2">
                    <CardTitle className="text-sm text-emerald-800">Utilidad Neta</CardTitle>
                  </CardHeader>
                  <CardContent>
                    <p className="text-2xl font-bold text-emerald-700">{formatMXN(sankeyData.summary?.utilidad_neta)}</p>
                    <p className="text-xs text-emerald-600 mt-1">
                      {((sankeyData.summary?.utilidad_neta / sankeyData.summary?.ingresos) * 100 || 0).toFixed(1)}%
                    </p>
                  </CardContent>
                </Card>
              </div>

              {/* Detailed Breakdown */}
              <Card>
                <CardHeader>
                  <CardTitle className="text-base">Desglose del Estado de Resultados</CardTitle>
                </CardHeader>
                <CardContent>
                  <div className="space-y-4">
                    <div className="flex items-center justify-between py-3 border-b">
                      <span className="font-medium text-blue-700">Ingresos</span>
                      <span className="font-bold text-blue-700">{formatMXN(sankeyData.summary?.ingresos)}</span>
                    </div>
                    <div className="flex items-center justify-between py-2 pl-4">
                      <span className="text-red-600">(-) Costo de Ventas</span>
                      <span className="text-red-600">{formatMXN(sankeyData.summary?.costo_ventas)}</span>
                    </div>
                    <div className="flex items-center justify-between py-3 border-b bg-green-50 px-2 rounded">
                      <span className="font-medium text-green-700">= Utilidad Bruta</span>
                      <span className="font-bold text-green-700">{formatMXN(sankeyData.summary?.utilidad_bruta)}</span>
                    </div>
                    <div className="flex items-center justify-between py-2 pl-4">
                      <span className="text-orange-600">(-) Gastos Operativos</span>
                      <span className="text-orange-600">{formatMXN(sankeyData.summary?.gastos_operativos)}</span>
                    </div>
                    <div className="flex items-center justify-between py-3 border-b bg-blue-50 px-2 rounded">
                      <span className="font-medium text-blue-700">= Utilidad Operativa</span>
                      <span className="font-bold text-blue-700">{formatMXN(sankeyData.summary?.utilidad_operativa)}</span>
                    </div>
                    <div className="flex items-center justify-between py-2 pl-4">
                      <span className="text-red-600">(-) Otros Gastos</span>
                      <span className="text-red-600">{formatMXN(sankeyData.summary?.otros_gastos)}</span>
                    </div>
                    <div className="flex items-center justify-between py-2 pl-4">
                      <span className="text-purple-600">(-) Impuestos</span>
                      <span className="text-purple-600">{formatMXN(sankeyData.summary?.impuestos)}</span>
                    </div>
                    <div className="flex items-center justify-between py-3 border-t-2 bg-emerald-100 px-2 rounded">
                      <span className="font-bold text-emerald-800">= UTILIDAD NETA</span>
                      <span className="font-bold text-emerald-800 text-xl">{formatMXN(sankeyData.summary?.utilidad_neta)}</span>
                    </div>
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

export default Reports;
