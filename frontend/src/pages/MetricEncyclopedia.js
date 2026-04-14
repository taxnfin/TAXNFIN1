import React, { useState } from 'react';
import { Card, CardContent } from '../components/ui/card';
import { Button } from '../components/ui/button';
import {
  ChevronRight, ChevronDown, HelpCircle, Lightbulb, Star,
  Calculator, Link2, TrendingUp, TrendingDown, CheckCircle2,
  ArrowLeft, Clock, Monitor, Gem, Sparkles, Wine, Pill, ShoppingCart,
  Wheat, Truck, Car, Package, Mountain, Radio, Zap, Building2,
  Landmark, Briefcase, Cpu, Plane, UtensilsCrossed, Factory,
  Hotel, Users, Megaphone, Smartphone, RefreshCw, Cloud, Store,
  HeartPulse, Cog, Flame, Rocket, Code, GraduationCap
} from 'lucide-react';
import metricsEncyclopedia from '../data/metricsEncyclopedia';

const iconMap = {
  Monitor, Gem, Sparkles, Wine, Pill, ShoppingCart, Wheat, Truck, Car, Package,
  Mountain, Radio, Zap, Building2, Landmark, Briefcase, Cpu, Plane,
  UtensilsCrossed, Factory, Hotel, Users, Megaphone, Smartphone,
  RefreshCw, Cloud, Store, HeartPulse, Cog, Flame, Rocket, Code, GraduationCap,
  HardHat: Briefcase,
};

// Mapping from encyclopedia metric key to API metrics data path
const metricPathMap = {
  gross_margin: 'margins.gross_margin',
  ebitda_margin: 'margins.ebitda_margin',
  operating_margin: 'margins.operating_margin',
  net_margin: 'margins.net_margin',
  nopat_margin: 'margins.nopat_margin',
  roic: 'returns.roic',
  roe: 'returns.roe',
  roce: 'returns.roce',
  roa: 'returns.roa',
  asset_turnover: 'efficiency.asset_turnover',
  dso: 'efficiency.dso',
  dpo: 'efficiency.dpo',
  cash_conversion_cycle: 'efficiency.cash_conversion_cycle',
  current_ratio: 'liquidity.current_ratio',
  quick_ratio: 'liquidity.quick_ratio',
  cash_ratio: 'liquidity.cash_ratio',
  working_capital: 'liquidity.working_capital',
  debt_to_equity: 'solvency.debt_to_equity',
  debt_to_assets: 'solvency.debt_to_assets',
  interest_coverage: 'solvency.interest_coverage',
  equity_ratio: 'solvency.equity_ratio',
};

const getMetricValue = (metricsData, key) => {
  const path = metricPathMap[key];
  if (!path || !metricsData?.metrics) return null;
  const [section, metric] = path.split('.');
  return metricsData.metrics[section]?.[metric]?.value ?? null;
};

const formatVal = (value, key) => {
  if (value === null || value === undefined) return null;
  const pctMetrics = ['gross_margin','ebitda_margin','operating_margin','net_margin','nopat_margin','debt_to_assets','equity_ratio'];
  const xMetrics = ['asset_turnover','current_ratio','quick_ratio','cash_ratio','debt_to_equity','interest_coverage','roce','roic','roe','roa'];
  const dayMetrics = ['dso','dpo','cash_conversion_cycle'];
  const currencyMetrics = ['working_capital'];
  if (pctMetrics.includes(key)) return `${value.toFixed(1)}%`;
  if (xMetrics.includes(key)) return `${value.toFixed(2)}x`;
  if (dayMetrics.includes(key)) return `${value.toFixed(1)} días`;
  if (currencyMetrics.includes(key)) return `$${Math.round(value).toLocaleString('es-MX')}`;
  return value.toFixed(2);
};

const MetricEncyclopedia = ({ metricsData, selectedPeriod }) => {
  const [selectedMetric, setSelectedMetric] = useState(metricsEncyclopedia.metrics[0]);
  const [activeSection, setActiveSection] = useState('queMide');
  const [expandedEval, setExpandedEval] = useState(null);
  const [performerTab, setPerformerTab] = useState('best');
  const [showImprove, setShowImprove] = useState(false);

  const sectionItems = [
    { key: 'queMide', label: '¿Qué mide?', icon: HelpCircle },
    { key: 'razonamiento', label: 'Razonamiento', icon: Lightbulb },
    { key: 'relevancia', label: 'Relevancia', icon: Star },
    { key: 'formula', label: 'Fórmula', icon: Calculator },
    { key: 'metricasRelacionadas', label: 'Métricas relacionadas', icon: Link2 },
  ];

  const categoryColor = metricsEncyclopedia.categories.find(c => c.key === selectedMetric.category)?.color || '#10B981';

  const PerformerIcon = ({ iconName }) => {
    const IconComp = iconMap[iconName] || Package;
    return <IconComp className="w-8 h-8" style={{ color: categoryColor }} />;
  };

  const relatedMetrics = (selectedMetric.sections.metricasRelacionadas || [])
    .map(k => metricsEncyclopedia.metrics.find(m => m.key === k))
    .filter(Boolean);

  // Benchmark: Get current company value and determine evaluation level
  const currentValue = getMetricValue(metricsData, selectedMetric.key);
  const formattedValue = formatVal(currentValue, selectedMetric.key);
  
  const getBenchmarkLevel = () => {
    if (currentValue === null) return null;
    const evals = selectedMetric.evaluacion;
    // Parse thresholds to determine which level the value falls into
    // Evaluation is ordered from best (index 0) to worst (index 4)
    // For most metrics, higher = better. For some (DSO, debt ratios, CCC) lower = better
    const invertedMetrics = ['dso', 'dpo', 'cash_conversion_cycle', 'debt_to_equity', 'debt_to_assets', 'debt_to_ebitda'];
    const isInverted = invertedMetrics.includes(selectedMetric.key);
    
    // Define numeric thresholds for each metric based on evaluation data
    const thresholdMap = {
      gross_margin: [60, 40, 20, 10],
      ebitda_margin: [30, 20, 10, 5],
      operating_margin: [25, 15, 8, 3],
      net_margin: [20, 10, 5, 1],
      nopat_margin: [20, 12, 6, 2],
      roic: [20, 12, 8, 4],
      roe: [25, 15, 10, 5],
      roce: [20, 12, 8, 4],
      roa: [15, 8, 4, 2],
      asset_turnover: [2.0, 1.0, 0.5, 0.25],
      dso: [30, 45, 60, 90],         // inverted: lower is better
      dpo: [90, 60, 45, 30],         // special: mid-range is best
      cash_conversion_cycle: [0, 30, 60, 120], // inverted
      current_ratio: [3.0, 2.0, 1.5, 1.0],
      quick_ratio: [2.0, 1.5, 1.0, 0.5],
      cash_ratio: [1.0, 0.5, 0.2, 0.1],
      working_capital: [1000000, 500000, 100000, 0], // absolute
      debt_to_equity: [0.5, 1.0, 2.0, 3.0], // inverted
      debt_to_assets: [30, 50, 60, 75],       // inverted
      interest_coverage: [10, 5, 3, 1.5],
      equity_ratio: [70, 50, 40, 25],
    };
    
    const thresholds = thresholdMap[selectedMetric.key];
    if (!thresholds) return { level: evals[2], index: 2 }; // default middle
    
    if (isInverted) {
      if (currentValue <= thresholds[0]) return { level: evals[0], index: 0 };
      if (currentValue <= thresholds[1]) return { level: evals[1], index: 1 };
      if (currentValue <= thresholds[2]) return { level: evals[2], index: 2 };
      if (currentValue <= thresholds[3]) return { level: evals[3], index: 3 };
      return { level: evals[4], index: 4 };
    } else {
      if (currentValue >= thresholds[0]) return { level: evals[0], index: 0 };
      if (currentValue >= thresholds[1]) return { level: evals[1], index: 1 };
      if (currentValue >= thresholds[2]) return { level: evals[2], index: 2 };
      if (currentValue >= thresholds[3]) return { level: evals[3], index: 3 };
      return { level: evals[4], index: 4 };
    }
  };

  const benchmark = getBenchmarkLevel();

  return (
    <div className="flex gap-6" data-testid="metric-encyclopedia">
      {/* LEFT SIDEBAR: Metric Navigation + Detail Card */}
      <div className="w-80 flex-shrink-0 space-y-4">
        {/* Metric List by Category */}
        <Card className="overflow-hidden">
          <CardContent className="p-0">
            {metricsEncyclopedia.categories.map(cat => (
              <div key={cat.key}>
                <div className="px-4 py-2 text-xs font-bold uppercase tracking-wider" style={{ backgroundColor: cat.color + '15', color: cat.color }}>
                  {cat.label}
                </div>
                {metricsEncyclopedia.metrics.filter(m => m.category === cat.key).map(m => {
                  const MetricIcon = m.icon;
                  const navVal = getMetricValue(metricsData, m.key);
                  const navFormatted = formatVal(navVal, m.key);
                  return (
                    <button
                      key={m.key}
                      onClick={() => { setSelectedMetric(m); setActiveSection('queMide'); setExpandedEval(null); setShowImprove(false); }}
                      className={`w-full flex items-center gap-2 px-4 py-2.5 text-left text-sm transition-colors ${
                        selectedMetric.key === m.key
                          ? 'bg-gray-100 font-semibold border-l-3'
                          : 'hover:bg-gray-50'
                      }`}
                      style={selectedMetric.key === m.key ? { borderLeftColor: cat.color, borderLeftWidth: '3px' } : {}}
                      data-testid={`enc-nav-${m.key}`}
                    >
                      <MetricIcon className="w-4 h-4 flex-shrink-0" style={{ color: cat.color }} />
                      <span className="truncate flex-1">{m.name}</span>
                      {navFormatted && (
                        <span className="text-[10px] font-mono font-semibold text-gray-500 flex-shrink-0">{navFormatted}</span>
                      )}
                    </button>
                  );
                })}
              </div>
            ))}
          </CardContent>
        </Card>
      </div>

      {/* RIGHT CONTENT: Selected Metric Detail */}
      <div className="flex-1 space-y-5">
        {/* Header */}
        <div className="flex items-center justify-between">
          <h2 className="text-3xl font-bold text-gray-900">{selectedMetric.name}</h2>
          <span className="text-sm text-gray-400 font-mono">{selectedMetric.englishName}</span>
        </div>

        {/* Benchmark Banner */}
        {benchmark && formattedValue && (
          <div
            className="rounded-xl p-4 flex items-center gap-4 border-2 shadow-sm"
            style={{ borderColor: benchmark.level.color + '50', background: `linear-gradient(135deg, ${benchmark.level.color}08, ${benchmark.level.color}15)` }}
            data-testid="benchmark-banner"
          >
            <div className="w-14 h-14 rounded-xl flex items-center justify-center flex-shrink-0 shadow-inner" style={{ backgroundColor: benchmark.level.color + '20' }}>
              <span className="text-lg font-bold" style={{ color: benchmark.level.color }}>{formattedValue}</span>
            </div>
            <div className="flex-1 min-w-0">
              <div className="flex items-center gap-2">
                <div className="w-2.5 h-2.5 rounded-full" style={{ backgroundColor: benchmark.level.color }} />
                <span className="text-sm font-bold" style={{ color: benchmark.level.color }}>{benchmark.level.nivel}</span>
                <span className="text-xs text-gray-400">|</span>
                <span className="text-xs text-gray-500">Período {selectedPeriod}</span>
              </div>
              <p className="text-sm text-gray-600 mt-1">
                Tu <strong>{selectedMetric.name}</strong> de <strong>{formattedValue}</strong> se ubica en el rango <strong style={{ color: benchmark.level.color }}>{benchmark.level.threshold}</strong>
              </p>
            </div>
            {/* Mini progress bar showing position */}
            <div className="w-40 flex-shrink-0">
              <div className="flex gap-0.5 h-3 rounded-full overflow-hidden">
                {selectedMetric.evaluacion.map((ev, idx) => (
                  <div
                    key={idx}
                    className="flex-1 relative transition-all"
                    style={{
                      backgroundColor: idx === benchmark.index ? ev.color : ev.color + '30',
                      boxShadow: idx === benchmark.index ? `0 0 8px ${ev.color}60` : 'none',
                    }}
                  >
                    {idx === benchmark.index && (
                      <div className="absolute inset-0 flex items-center justify-center">
                        <div className="w-1.5 h-1.5 rounded-full bg-white" />
                      </div>
                    )}
                  </div>
                ))}
              </div>
              <div className="flex justify-between mt-1">
                <span className="text-[9px] text-gray-400">Mejor</span>
                <span className="text-[9px] text-gray-400">Peor</span>
              </div>
            </div>
          </div>
        )}
        {!benchmark && !formattedValue && (
          <div className="rounded-xl p-3 bg-gray-50 border border-dashed border-gray-300 text-center" data-testid="benchmark-no-data">
            <p className="text-sm text-gray-400">Selecciona un período con datos financieros para ver tu benchmark</p>
          </div>
        )}

        {/* Top Row: Metric Card + Sections */}
        <div className="grid grid-cols-12 gap-5">
          {/* Metric Identity Card */}
          <div className="col-span-4">
            <div className="rounded-xl overflow-hidden border" style={{ borderColor: categoryColor + '40' }}>
              <div className="p-6 flex items-center justify-center" style={{ background: `linear-gradient(135deg, ${categoryColor}20, ${categoryColor}08)` }}>
                {React.createElement(selectedMetric.icon, { className: 'w-16 h-16', style: { color: categoryColor } })}
              </div>
              <div className="p-4 bg-white space-y-3">
                <h3 className="font-bold text-lg" style={{ color: categoryColor }}>{selectedMetric.name}</h3>
                <p className="text-sm text-gray-700 font-medium">{selectedMetric.question}</p>
                <div className="flex items-center gap-2 text-xs text-gray-500">
                  <Clock className="w-3.5 h-3.5" />
                  {selectedMetric.frequency}
                </div>
                <p className="text-xs text-gray-400 italic">{selectedMetric.alternativeNames}</p>
              </div>
            </div>
          </div>

          {/* Sections Panel */}
          <div className="col-span-8 space-y-3">
            {/* Section Tabs */}
            <div className="flex flex-col gap-1">
              {sectionItems.map(s => {
                const SIcon = s.icon;
                const isActive = activeSection === s.key;
                return (
                  <button
                    key={s.key}
                    onClick={() => setActiveSection(s.key)}
                    className={`flex items-center gap-3 px-4 py-2.5 rounded-lg text-sm font-medium transition-all ${
                      isActive
                        ? 'text-white shadow-md'
                        : 'text-gray-700 bg-gray-50 hover:bg-gray-100'
                    }`}
                    style={isActive ? { backgroundColor: categoryColor } : {}}
                    data-testid={`enc-section-${s.key}`}
                  >
                    <SIcon className="w-4 h-4" />
                    {s.label}
                    <ChevronRight className={`w-4 h-4 ml-auto transition-transform ${isActive ? 'rotate-90' : ''}`} />
                  </button>
                );
              })}
            </div>

            {/* Active Section Content */}
            <div className="rounded-xl border-2 p-5 bg-white" style={{ borderColor: categoryColor + '30' }} data-testid="enc-section-content">
              <h4 className="text-lg font-bold text-gray-800 flex items-center gap-2 mb-3">
                {React.createElement(sectionItems.find(s => s.key === activeSection)?.icon || HelpCircle, { className: 'w-5 h-5', style: { color: categoryColor } })}
                {sectionItems.find(s => s.key === activeSection)?.label}
              </h4>
              {activeSection === 'metricasRelacionadas' ? (
                <div className="flex flex-wrap gap-2">
                  {relatedMetrics.map(rm => (
                    <button
                      key={rm.key}
                      onClick={() => { setSelectedMetric(rm); setActiveSection('queMide'); }}
                      className="flex items-center gap-2 px-3 py-2 rounded-lg border hover:shadow-md transition-all text-sm"
                      style={{ borderColor: categoryColor + '40' }}
                    >
                      {React.createElement(rm.icon, { className: 'w-4 h-4', style: { color: categoryColor } })}
                      {rm.name}
                      <ChevronRight className="w-3 h-3 text-gray-400" />
                    </button>
                  ))}
                </div>
              ) : (
                <p className="text-sm text-gray-700 leading-relaxed whitespace-pre-line">
                  {selectedMetric.sections[activeSection]}
                </p>
              )}
            </div>
          </div>
        </div>

        {/* Evaluation Section */}
        <Card>
          <CardContent className="p-5">
            <h3 className="text-lg font-bold text-gray-800 mb-4">Evaluación de métrica</h3>
            <div className="space-y-2">
              {selectedMetric.evaluacion.map((ev, idx) => {
                const isCurrent = benchmark && benchmark.index === idx;
                return (
                <div key={idx}>
                  <button
                    onClick={() => setExpandedEval(expandedEval === idx ? null : idx)}
                    className={`w-full flex items-center gap-3 px-4 py-3 rounded-lg text-left transition-all ${
                      expandedEval === idx ? 'shadow-md' : 'hover:bg-gray-50'
                    } ${isCurrent ? 'ring-2' : ''}`}
                    style={{
                      ...(expandedEval === idx ? { backgroundColor: ev.color + '10', border: `1px solid ${ev.color}30` } : {}),
                      ...(isCurrent ? { ringColor: ev.color, boxShadow: `0 0 0 2px ${ev.color}40` } : {}),
                    }}
                    data-testid={`enc-eval-${idx}`}
                  >
                    <div className="w-3 h-3 rounded-full flex-shrink-0" style={{ backgroundColor: ev.color }} />
                    <span className="text-sm font-medium text-gray-800 flex-1">{ev.nivel}</span>
                    {isCurrent && (
                      <span className="text-[10px] font-bold px-2 py-0.5 rounded-full text-white" style={{ backgroundColor: ev.color }} data-testid="benchmark-indicator">
                        TU EMPRESA
                      </span>
                    )}
                    {expandedEval === idx ? (
                      <ChevronDown className="w-4 h-4 text-gray-400" />
                    ) : (
                      <ChevronRight className="w-4 h-4 text-gray-400" />
                    )}
                  </button>
                  {expandedEval === idx && (
                    <div className="ml-10 mt-1 mb-3 p-3 rounded-lg animate-in slide-in-from-top-2 duration-200" style={{ backgroundColor: ev.color + '08' }}>
                      <p className="text-lg font-bold" style={{ color: ev.color }}>{ev.threshold}</p>
                      <p className="text-sm text-gray-600 mt-1">{ev.description}</p>
                    </div>
                  )}
                </div>
              );
              })}
            </div>
          </CardContent>
        </Card>

        {/* Best / Worst Performers */}
        <Card>
          <CardContent className="p-5">
            <div className="flex gap-2 mb-4">
              <button
                onClick={() => setPerformerTab('best')}
                className={`flex items-center gap-2 px-4 py-2 rounded-lg text-sm font-medium transition-all ${
                  performerTab === 'best' ? 'text-white shadow-md' : 'bg-gray-100 text-gray-700'
                }`}
                style={performerTab === 'best' ? { backgroundColor: categoryColor } : {}}
                data-testid="enc-tab-best"
              >
                <TrendingUp className="w-4 h-4" /> Best Performers
              </button>
              <button
                onClick={() => setPerformerTab('worst')}
                className={`flex items-center gap-2 px-4 py-2 rounded-lg text-sm font-medium transition-all ${
                  performerTab === 'worst' ? 'text-white shadow-md' : 'bg-gray-100 text-gray-700'
                }`}
                style={performerTab === 'worst' ? { backgroundColor: categoryColor } : {}}
                data-testid="enc-tab-worst"
              >
                <TrendingDown className="w-4 h-4" /> Worst Performers
              </button>
            </div>

            <p className="text-sm text-gray-600 mb-4">
              {performerTab === 'best'
                ? `Industrias con mejor desempeño en "${selectedMetric.name}", donde esta métrica alcanza los valores más altos del mercado.`
                : `Industrias con peor desempeño en "${selectedMetric.name}", donde esta métrica tiende a mostrar los valores más bajos.`
              }
            </p>

            <div className="grid grid-cols-5 gap-3">
              {(performerTab === 'best' ? selectedMetric.bestPerformers : selectedMetric.worstPerformers).map((p, idx) => (
                <div key={idx} className="flex flex-col items-center gap-2 p-4 rounded-xl" style={{ backgroundColor: categoryColor + '08' }}>
                  <PerformerIcon iconName={p.icon} />
                  <span className="text-xs font-medium text-gray-700 text-center">{p.name}</span>
                </div>
              ))}
            </div>
          </CardContent>
        </Card>

        {/* Quote */}
        <div className="rounded-xl border-2 p-5 flex items-start gap-4" style={{ borderColor: categoryColor + '30', backgroundColor: categoryColor + '05' }}>
          <div className="w-12 h-12 rounded-full flex-shrink-0 flex items-center justify-center text-white text-lg font-bold" style={{ backgroundColor: categoryColor }}>
            {selectedMetric.quote.author.charAt(0)}
          </div>
          <div>
            <p className="text-sm italic text-gray-700 leading-relaxed">"{selectedMetric.quote.text}"</p>
            <p className="text-xs font-semibold text-gray-500 mt-2">— {selectedMetric.quote.author} ({selectedMetric.quote.company})</p>
          </div>
        </div>

        {/* How to Improve */}
        <Card>
          <CardContent className="p-0">
            <button
              onClick={() => setShowImprove(!showImprove)}
              className="w-full flex items-center gap-3 px-5 py-4 text-left"
              data-testid="enc-how-to-improve"
            >
              <CheckCircle2 className="w-5 h-5" style={{ color: categoryColor }} />
              <span className="text-sm font-bold text-gray-800">¿Cómo mejorar esta métrica?</span>
              <ChevronDown className={`w-4 h-4 ml-auto text-gray-400 transition-transform ${showImprove ? 'rotate-180' : ''}`} />
            </button>
            {showImprove && (
              <div className="px-5 pb-5 space-y-2 animate-in slide-in-from-top-2 duration-200">
                {selectedMetric.comoMejorar.map((tip, idx) => (
                  <div key={idx} className="flex items-start gap-3 text-sm">
                    <div className="w-5 h-5 rounded-full flex items-center justify-center flex-shrink-0 mt-0.5 text-xs font-bold text-white" style={{ backgroundColor: categoryColor }}>
                      {idx + 1}
                    </div>
                    <p className="text-gray-700">{tip}</p>
                  </div>
                ))}
              </div>
            )}
          </CardContent>
        </Card>
      </div>
    </div>
  );
};

export default MetricEncyclopedia;
