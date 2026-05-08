import { useState, useCallback } from 'react';
import api from '@/api/axios';
import { toast } from 'sonner';
import { Card, CardContent, CardHeader, CardTitle, CardDescription } from '@/components/ui/card';
import { Button } from '@/components/ui/button';
import {
  Upload, FileSpreadsheet, CheckCircle2, AlertCircle,
  TrendingUp, TrendingDown, Building2, DollarSign,
  RefreshCw, ChevronDown, ChevronRight, Save, History,
} from 'lucide-react';

// ─── Helpers ─────────────────────────────────────────────────────────────────

const fmt = (n, decimals = 0) =>
  (n ?? 0).toLocaleString('es-MX', {
    minimumFractionDigits: decimals,
    maximumFractionDigits: decimals,
  });

const fmtM = (n) => `$${fmt(n, 2)}`;

const colorVal = (n, invert = false) => {
  if (n === 0) return 'text-gray-400';
  const pos = invert ? n < 0 : n > 0;
  return pos ? 'text-emerald-600' : 'text-red-500';
};

// ─── Sub-componentes ──────────────────────────────────────────────────────────

const KPICard = ({ label, value, sub, color = 'blue', icon: Icon }) => {
  const colors = {
    blue:   { bg: 'bg-blue-50',   border: 'border-blue-200',   text: 'text-blue-700',   val: 'text-blue-900'   },
    green:  { bg: 'bg-emerald-50', border: 'border-emerald-200', text: 'text-emerald-700', val: 'text-emerald-900' },
    red:    { bg: 'bg-red-50',    border: 'border-red-200',    text: 'text-red-700',    val: 'text-red-900'    },
    purple: { bg: 'bg-purple-50', border: 'border-purple-200', text: 'text-purple-700', val: 'text-purple-900' },
  };
  const c = colors[color] || colors.blue;
  return (
    <div className={`${c.bg} ${c.border} border rounded-xl p-4`}>
      <div className={`flex items-center gap-2 text-xs font-semibold uppercase tracking-wide ${c.text} mb-2`}>
        {Icon && <Icon size={14} />}
        {label}
      </div>
      <div className={`text-xl font-bold font-mono ${c.val}`}>{value}</div>
      {sub && <div className="text-xs text-gray-400 mt-1">{sub}</div>}
    </div>
  );
};

const CollapsibleSection = ({ title, total, items = [], defaultOpen = false }) => {
  const [open, setOpen] = useState(defaultOpen);
  const mainItems = items.filter(i => i.level <= 1 && i.value !== 0);

  return (
    <div className="border border-gray-100 rounded-lg overflow-hidden">
      <button
        onClick={() => setOpen(o => !o)}
        className="w-full flex items-center justify-between px-4 py-3 bg-gray-50 hover:bg-gray-100 transition-colors"
      >
        <div className="flex items-center gap-3">
          {open ? <ChevronDown size={15} /> : <ChevronRight size={15} />}
          <span className="font-semibold text-sm text-gray-800">{title}</span>
          <span className="text-xs text-gray-400">{mainItems.length} rubros</span>
        </div>
        <span className="font-bold font-mono text-sm text-gray-800">{fmtM(total)}</span>
      </button>
      {open && (
        <div className="divide-y divide-gray-50">
          {mainItems.map((item, idx) => (
            <div key={idx} className="flex justify-between items-center px-4 py-2.5 hover:bg-gray-50">
              <span className="text-sm text-gray-600">{item.label}</span>
              <span className={`text-sm font-mono font-medium ${colorVal(item.value)}`}>
                {fmtM(item.value)}
              </span>
            </div>
          ))}
        </div>
      )}
    </div>
  );
};

const BalanceView = ({ data }) => {
  const { resumen, activo, pasivo, capital, kpis } = data;

  return (
    <div className="space-y-6">
      {/* KPIs */}
      <div className="grid grid-cols-2 md:grid-cols-4 gap-3">
        <KPICard label="Total Activo"   value={fmtM(resumen.total_activo)}  color="blue"   icon={TrendingUp} />
        <KPICard label="Total Pasivo"   value={fmtM(resumen.total_pasivo)}  color="red"    icon={TrendingDown} />
        <KPICard label="Capital Contable" value={fmtM(resumen.total_capital)} color="green"  icon={Building2} />
        <KPICard label="Razón Circulante" value={fmt(kpis.razon_circulante, 2) + 'x'}
          color={kpis.razon_circulante >= 1 ? 'green' : 'red'}
          icon={DollarSign}
          sub={kpis.razon_circulante >= 1 ? 'Liquidez sana' : 'Liquidez ajustada'}
        />
      </div>

      {/* KPIs secundarios */}
      <div className="grid grid-cols-2 gap-3">
        <div className="bg-gray-50 rounded-xl p-4 flex justify-between items-center">
          <div>
            <div className="text-xs text-gray-500 uppercase tracking-wide font-semibold mb-1">Deuda / Capital</div>
            <div className="text-lg font-bold font-mono text-gray-800">{fmt(kpis.deuda_capital, 2)}x</div>
          </div>
          <div>
            <div className="text-xs text-gray-500 uppercase tracking-wide font-semibold mb-1">Solidez (Activo/Pasivo)</div>
            <div className="text-lg font-bold font-mono text-gray-800">{fmt(kpis.solidez, 2)}x</div>
          </div>
        </div>
        <div className="bg-gray-50 rounded-xl p-4 flex justify-between items-center">
          <div>
            <div className="text-xs text-gray-500 uppercase tracking-wide font-semibold mb-1">Activo Circulante</div>
            <div className="text-lg font-bold font-mono text-blue-700">{fmtM(resumen.activo_circulante)}</div>
          </div>
          <div>
            <div className="text-xs text-gray-500 uppercase tracking-wide font-semibold mb-1">Pasivo Corto Plazo</div>
            <div className="text-lg font-bold font-mono text-red-600">{fmtM(resumen.pasivo_corto_plazo)}</div>
          </div>
        </div>
      </div>

      {/* Detalle colapsable */}
      <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
        <div className="space-y-2">
          <div className="text-xs font-bold text-gray-400 uppercase tracking-widest mb-2">ACTIVO</div>
          <CollapsibleSection title="Activo" total={activo.total} items={activo.secciones} defaultOpen />
        </div>
        <div className="space-y-2">
          <div className="text-xs font-bold text-gray-400 uppercase tracking-widest mb-2">PASIVO Y CAPITAL</div>
          <CollapsibleSection title="Pasivo" total={pasivo.total} items={pasivo.secciones} defaultOpen />
          <CollapsibleSection title="Capital Contable" total={capital.total} items={capital.secciones} />
        </div>
      </div>

      {/* Ecuación contable */}
      <div className="bg-gray-900 text-white rounded-xl p-4 flex items-center justify-center gap-4 text-sm font-mono">
        <span className="text-blue-400">Activo: {fmtM(resumen.total_activo)}</span>
        <span className="text-gray-500">=</span>
        <span className="text-red-400">Pasivo: {fmtM(resumen.total_pasivo)}</span>
        <span className="text-gray-500">+</span>
        <span className="text-emerald-400">Capital: {fmtM(resumen.total_capital || resumen.total_activo - resumen.total_pasivo)}</span>
      </div>
    </div>
  );
};

const ResultadosView = ({ data }) => {
  const { resumen, detalle = [] } = data;
  const [showDetalle, setShowDetalle] = useState(false);
  const ingresos = resumen.ventas_netas || resumen.ingresos || 0;
  const resultado = resumen.utilidad_neta || resumen.ebita || resumen.ebitda || 0;

  return (
    <div className="space-y-6">
      {/* Cascada de resultados */}
      <div className="grid grid-cols-2 md:grid-cols-4 gap-3">
        <KPICard label="Ventas Brutas"   value={fmtM(resumen.ventas_brutas || ingresos)}
          color="blue" icon={TrendingUp} />
        <KPICard label="Ventas Netas"    value={fmtM(ingresos)}
          color="blue" icon={TrendingUp}
          sub={resumen.devoluciones ? `Devol: ${fmtM(resumen.devoluciones)}` : null} />
        <KPICard label="Utilidad Bruta"  value={fmtM(resumen.utilidad_bruta)}
          color="green" icon={TrendingUp}
          sub={`Margen: ${fmt(resumen.margen_bruto, 1)}%`} />
        <KPICard label="Costo de Ventas" value={fmtM(resumen.costo_ventas)}
          color="red" icon={TrendingDown} />
      </div>

      <div className="grid grid-cols-2 md:grid-cols-4 gap-3">
        {resumen.ebitda > 0 && (
          <KPICard label="EBITDA" value={fmtM(resumen.ebitda)}
            color={resumen.ebitda >= 0 ? 'green' : 'red'} icon={TrendingUp}
            sub={`Margen: ${fmt(resumen.margen_ebitda, 1)}%`} />
        )}
        {resumen.ebita > 0 && (
          <KPICard label="EBITA" value={fmtM(resumen.ebita)}
            color={resumen.ebita >= 0 ? 'green' : 'red'} icon={TrendingUp} />
        )}
        {resumen.gastos_admin > 0 && (
          <KPICard label="Gastos Admin" value={fmtM(resumen.gastos_admin)}
            color="purple" icon={TrendingDown} />
        )}
        {resumen.gastos_fin > 0 && (
          <KPICard label="Gastos Financieros" value={fmtM(resumen.gastos_fin)}
            color="red" icon={TrendingDown} />
        )}
        {resumen.utilidad_neta !== 0 && (
          <KPICard label="Utilidad Neta" value={fmtM(resumen.utilidad_neta)}
            color={resumen.utilidad_neta >= 0 ? 'green' : 'red'} icon={DollarSign}
            sub={`Margen: ${fmt(resumen.margen_neto, 1)}%`} />
        )}
      </div>

      {/* Cascada visual */}
      <div className="bg-gray-900 text-white rounded-xl p-4 space-y-1 text-sm font-mono">
        <div className="flex justify-between"><span className="text-blue-300">Ventas Netas</span><span>{fmtM(ingresos)}</span></div>
        <div className="flex justify-between text-gray-500"><span>- Costo de ventas</span><span>({fmtM(resumen.costo_ventas)})</span></div>
        <div className="flex justify-between border-t border-gray-700 pt-1"><span className="text-emerald-400">= Utilidad Bruta</span><span className="text-emerald-400">{fmtM(resumen.utilidad_bruta)}</span></div>
        {resumen.gastos_admin > 0 && <div className="flex justify-between text-gray-500"><span>- Gastos Admin</span><span>({fmtM(resumen.gastos_admin)})</span></div>}
        {resumen.ebitda > 0 && <div className="flex justify-between border-t border-gray-700 pt-1"><span className="text-yellow-400">= EBITDA</span><span className="text-yellow-400">{fmtM(resumen.ebitda)}</span></div>}
        {resumen.depreciacion > 0 && <div className="flex justify-between text-gray-500"><span>- Depreciación</span><span>({fmtM(resumen.depreciacion)})</span></div>}
        {resumen.gastos_fin > 0 && <div className="flex justify-between text-gray-500"><span>- Gastos Financieros</span><span>({fmtM(resumen.gastos_fin)})</span></div>}
        {resumen.ebita > 0 && <div className="flex justify-between border-t border-gray-700 pt-1"><span className="text-orange-400">= EBITA</span><span className="text-orange-400">{fmtM(resumen.ebita)}</span></div>}
        {resumen.utilidad_neta !== 0 && <div className="flex justify-between border-t border-gray-700 pt-1"><span className={resultado >= 0 ? 'text-emerald-400' : 'text-red-400'}>= Utilidad Neta</span><span className={resultado >= 0 ? 'text-emerald-400' : 'text-red-400'}>{fmtM(resultado)}</span></div>}
      </div>

      {/* Toggle detalle */}
      {detalle.length > 0 && (
        <button onClick={() => setShowDetalle(s => !s)}
          className="text-xs text-gray-400 hover:text-gray-600 flex items-center gap-1">
          {showDetalle ? <ChevronDown size={13}/> : <ChevronRight size={13}/>}
          {showDetalle ? 'Ocultar' : 'Ver'} detalle completo ({detalle.length} líneas)
        </button>
      )}
      {showDetalle && (
        <div className="border border-gray-100 rounded-lg overflow-hidden text-sm">
          {detalle.map((item, i) => (
            <div key={i} className={`flex justify-between px-4 py-2 ${
              item.is_total ? 'bg-gray-900 text-white font-semibold' : 'hover:bg-gray-50 text-gray-700'
            } border-b border-gray-50`}>
              <span>{item.label}</span>
              <span className="font-mono">{item.value ? fmtM(item.value) : ''}</span>
            </div>
          ))}
        </div>
      )}
    </div>
  );
};


// ─── Centro de Costo View ─────────────────────────────────────────────────────
const CentroCostoView = ({ data }) => {
  const { resumen, ranking_centros = [], por_centro } = data;
  const maxAbs = Math.max(...ranking_centros.map(c => Math.abs(c.utilidad)), 1);

  return (
    <div className="space-y-6">
      {/* KPIs consolidados */}
      <div className="grid grid-cols-2 md:grid-cols-4 gap-3">
        <KPICard label="Ingresos Netos"   value={fmtM(resumen.ingresos)}      color="blue"  icon={TrendingUp} />
        <KPICard label="Utilidad Bruta"   value={fmtM(resumen.utilidad_bruta)}
          color={resumen.utilidad_bruta >= 0 ? 'green' : 'red'} icon={TrendingUp}
          sub={`Margen: ${fmt(resumen.margen_bruto, 1)}%`} />
        <KPICard label="Gastos Totales"   value={fmtM(resumen.gastos)}        color="purple" icon={TrendingDown} />
        <KPICard label="Utilidad Neta"    value={fmtM(resumen.utilidad_neta)}
          color={resumen.utilidad_neta >= 0 ? 'green' : 'red'} icon={DollarSign}
          sub={`Margen: ${fmt(resumen.margen_neto, 1)}%`} />
      </div>

      {/* Ranking por centro */}
      <div className="border border-gray-100 rounded-xl overflow-hidden">
        <div className="px-4 py-3 bg-gray-50 border-b border-gray-100">
          <div className="text-xs font-bold text-gray-500 uppercase tracking-wider">
            Utilidad Neta por Centro de Costo
          </div>
        </div>
        <div className="divide-y divide-gray-50">
          {ranking_centros.map((c, i) => {
            const pct = (c.utilidad / maxAbs) * 100;
            const pos = c.utilidad >= 0;
            return (
              <div key={i} className="px-4 py-3">
                <div className="flex items-center justify-between mb-1.5">
                  <div className="flex items-center gap-2">
                    <span className={`text-xs font-bold w-5 h-5 rounded-full flex items-center justify-center
                      ${pos ? 'bg-emerald-100 text-emerald-700' : 'bg-red-100 text-red-600'}`}>
                      {i + 1}
                    </span>
                    <span className="text-sm font-medium text-gray-700 capitalize">
                      {c.centro.replace('~', '').trim()}
                    </span>
                  </div>
                  <div className="text-right">
                    <span className={`text-sm font-bold font-mono ${pos ? 'text-emerald-600' : 'text-red-500'}`}>
                      {fmtM(c.utilidad)}
                    </span>
                    {c.ingresos > 0 && (
                      <span className="block text-xs text-gray-400">
                        {fmt(c.utilidad / c.ingresos * 100, 1)}% margen
                      </span>
                    )}
                  </div>
                </div>
                {/* Barra */}
                <div className="h-1.5 bg-gray-100 rounded-full overflow-hidden">
                  <div
                    className={`h-full rounded-full transition-all ${pos ? 'bg-emerald-400' : 'bg-red-400'}`}
                    style={{ width: `${Math.abs(pct)}%` }}
                  />
                </div>
              </div>
            );
          })}
        </div>
      </div>

      {/* Top ganadores y perdedores */}
      <div className="grid grid-cols-2 gap-4">
        <div className="bg-emerald-50 border border-emerald-100 rounded-xl p-4">
          <div className="text-xs font-bold text-emerald-600 uppercase tracking-wide mb-3">
            ✓ Centros rentables
          </div>
          {ranking_centros.filter(c => c.utilidad > 0).map((c, i) => (
            <div key={i} className="flex justify-between text-sm py-1 border-b border-emerald-100 last:border-0">
              <span className="text-gray-700">{c.centro.replace('~','').trim()}</span>
              <span className="font-mono font-semibold text-emerald-700">{fmtM(c.utilidad)}</span>
            </div>
          ))}
        </div>
        <div className="bg-red-50 border border-red-100 rounded-xl p-4">
          <div className="text-xs font-bold text-red-500 uppercase tracking-wide mb-3">
            ✗ Centros con pérdida
          </div>
          {ranking_centros.filter(c => c.utilidad < 0).map((c, i) => (
            <div key={i} className="flex justify-between text-sm py-1 border-b border-red-100 last:border-0">
              <span className="text-gray-700">{c.centro.replace('~','').trim()}</span>
              <span className="font-mono font-semibold text-red-600">{fmtM(c.utilidad)}</span>
            </div>
          ))}
        </div>
      </div>
    </div>
  );
};

// ─── Componente principal ─────────────────────────────────────────────────────

const ContalinkFinancialImport = () => {
  const [dragging,   setDragging]   = useState(false);
  const [uploading,  setUploading]  = useState(false);
  const [saving,     setSaving]     = useState(false);
  const [result,     setResult]     = useState(null);  // datos parseados
  const [error,      setError]      = useState(null);
  const [history,    setHistory]    = useState([]);
  const [showHistory, setShowHistory] = useState(false);

  // ── Upload ──────────────────────────────────────────────────────────────────
  const uploadFile = useCallback(async (file) => {
    if (!file) return;
    if (!file.name.match(/\.(xlsx|xls)$/i)) {
      toast.error('Solo se aceptan archivos Excel (.xlsx, .xls)');
      return;
    }

    setUploading(true);
    setError(null);
    setResult(null);

    const formData = new FormData();
    formData.append('file', file);

    try {
      const res = await api.post('/contalink-financial/import', formData, {
        headers: { 'Content-Type': 'multipart/form-data' },
      });
      setResult(res.data.data);
      toast.success(`✓ ${res.data.data.tipo === 'balance_general'
        ? 'Balance General' : 'Estado de Resultados'} importado correctamente`);
    } catch (err) {
      const msg = err.response?.data?.detail || 'Error procesando el archivo';
      setError(msg);
      toast.error(msg);
    } finally {
      setUploading(false);
    }
  }, []);

  // ── Drag & Drop ─────────────────────────────────────────────────────────────
  const onDrop = useCallback((e) => {
    e.preventDefault();
    setDragging(false);
    const file = e.dataTransfer.files[0];
    if (file) uploadFile(file);
  }, [uploadFile]);

  const onFileInput = (e) => {
    const file = e.target.files[0];
    if (file) uploadFile(file);
    e.target.value = '';
  };

  // ── Guardar en DB ───────────────────────────────────────────────────────────
  const saveToDb = async () => {
    if (!result) return;
    setSaving(true);
    try {
      const res = await api.post('/contalink-financial/save', result);
      toast.success(res.data.action === 'created'
        ? 'Estado financiero guardado en historial'
        : 'Estado financiero actualizado en historial');
    } catch (err) {
      toast.error('Error guardando en historial');
    } finally {
      setSaving(false);
    }
  };

  // ── Historial ───────────────────────────────────────────────────────────────
  const loadHistory = async () => {
    try {
      const res = await api.get('/contalink-financial/history');
      setHistory(res.data.data || []);
      setShowHistory(true);
    } catch {
      toast.error('Error cargando historial');
    }
  };

  const tipoLabel = result?.tipo === 'balance_general' ? 'Balance General'
    : result?.tipo === 'er_centro_costo' ? 'ER por Centro de Costo'
    : 'Estado de Resultados';

  return (
    <div className="p-6 space-y-6 max-w-5xl mx-auto">

      {/* Header */}
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-bold text-gray-900">Estados Financieros</h1>
          <p className="text-sm text-gray-500 mt-0.5">
            Importa desde Contalink · Balance General o Estado de Resultados
          </p>
        </div>
        <Button variant="outline" size="sm" onClick={loadHistory} className="gap-2">
          <History size={14} />
          Historial
        </Button>
      </div>

      {/* Instrucciones */}
      <Card className="border-blue-100 bg-blue-50">
        <CardContent className="py-4">
          <div className="flex gap-3 items-start">
            <FileSpreadsheet size={18} className="text-blue-600 mt-0.5 flex-shrink-0" />
            <div className="text-sm text-blue-800">
              <p className="font-semibold mb-1">¿Cómo exportar desde Contalink?</p>
              <ol className="list-decimal list-inside space-y-0.5 text-blue-700">
                <li>Entra a <strong>Contabilidad → Reportes financieros</strong></li>
                <li>Selecciona <strong>Balance General</strong> o <strong>Estado de Resultados</strong></li>
                <li>Elige el período y da clic en <strong>Generar</strong></li>
                <li>Descarga el archivo en formato <strong>Excel (.xlsx)</strong></li>
                <li>Sube el archivo aquí abajo</li>
              </ol>
            </div>
          </div>
        </CardContent>
      </Card>

      {/* Drop zone */}
      <div
        onDragOver={(e) => { e.preventDefault(); setDragging(true); }}
        onDragLeave={() => setDragging(false)}
        onDrop={onDrop}
        className={`relative border-2 border-dashed rounded-2xl transition-all duration-200 ${
          dragging
            ? 'border-blue-400 bg-blue-50 scale-[1.01]'
            : 'border-gray-200 bg-gray-50 hover:border-gray-300 hover:bg-gray-100'
        }`}
      >
        <label className="flex flex-col items-center justify-center py-12 cursor-pointer">
          <div className={`w-14 h-14 rounded-2xl flex items-center justify-center mb-4 transition-colors ${
            dragging ? 'bg-blue-100' : 'bg-white shadow-sm border border-gray-200'
          }`}>
            {uploading
              ? <RefreshCw size={24} className="text-blue-500 animate-spin" />
              : <Upload size={24} className={dragging ? 'text-blue-500' : 'text-gray-400'} />
            }
          </div>
          <p className="text-sm font-semibold text-gray-700 mb-1">
            {uploading ? 'Procesando...' : 'Arrastra tu Excel aquí'}
          </p>
          <p className="text-xs text-gray-400 mb-4">o haz clic para seleccionar</p>
          <span className="px-4 py-2 bg-white border border-gray-200 rounded-lg text-xs font-medium text-gray-600 shadow-sm">
            Seleccionar archivo .xlsx
          </span>
          <input type="file" accept=".xlsx,.xls" onChange={onFileInput} className="hidden" />
        </label>
      </div>

      {/* Error */}
      {error && (
        <Card className="border-red-200 bg-red-50">
          <CardContent className="py-4 flex items-center gap-3">
            <AlertCircle size={18} className="text-red-500 flex-shrink-0" />
            <p className="text-sm text-red-700">{error}</p>
          </CardContent>
        </Card>
      )}

      {/* Resultado */}
      {result && (
        <Card className="border-gray-200">
          <CardHeader className="flex flex-row items-start justify-between pb-2">
            <div>
              <div className="flex items-center gap-2 mb-1">
                <CheckCircle2 size={16} className="text-emerald-500" />
                <CardTitle className="text-lg">{tipoLabel}</CardTitle>
              </div>
              <CardDescription className="flex items-center gap-3 text-sm">
                <span className="font-medium text-gray-700">{result.empresa}</span>
                {result.rfc && <span className="font-mono text-gray-400">{result.rfc}</span>}
                {result.fecha && (
                  <span className="bg-gray-100 px-2 py-0.5 rounded text-xs">
                    {new Date(result.fecha + 'T12:00:00').toLocaleDateString('es-MX', {
                      year: 'numeric', month: 'long', day: 'numeric'
                    })}
                  </span>
                )}
                <span className="bg-blue-100 text-blue-700 px-2 py-0.5 rounded text-xs font-medium">
                  {result.moneda}
                </span>
              </CardDescription>
            </div>
            <div className="flex gap-2">
              <Button
                variant="outline"
                size="sm"
                onClick={() => { setResult(null); setError(null); }}
                className="gap-2 text-xs"
              >
                <Upload size={13} />
                Nuevo archivo
              </Button>
              <Button
                size="sm"
                onClick={saveToDb}
                disabled={saving}
                className="gap-2 text-xs bg-gray-900 hover:bg-gray-800 text-white"
              >
                {saving
                  ? <RefreshCw size={13} className="animate-spin" />
                  : <Save size={13} />}
                Guardar en historial
              </Button>
            </div>
          </CardHeader>
          <CardContent className="pt-2">
            {result.tipo === 'balance_general'
              ? <BalanceView data={result} />
              : result.tipo === 'er_centro_costo'
              ? <CentroCostoView data={result} />
              : <ResultadosView data={result} />
            }
          </CardContent>
        </Card>
      )}

      {/* Historial modal */}
      {showHistory && (
        <Card className="border-gray-200">
          <CardHeader className="flex flex-row items-center justify-between pb-2">
            <CardTitle className="text-base">Historial de importaciones</CardTitle>
            <Button variant="ghost" size="sm" onClick={() => setShowHistory(false)}>✕</Button>
          </CardHeader>
          <CardContent>
            {history.length === 0 ? (
              <p className="text-sm text-gray-400 text-center py-4">
                No hay estados financieros guardados aún.
              </p>
            ) : (
              <div className="space-y-2">
                {history.map((h, i) => (
                  <div key={i} className="flex items-center justify-between p-3 bg-gray-50 rounded-lg">
                    <div className="flex items-center gap-3">
                      <FileSpreadsheet size={15} className="text-gray-400" />
                      <div>
                        <p className="text-sm font-medium text-gray-800">
                          {h.tipo === 'balance_general' ? 'Balance General' : 'Estado de Resultados'}
                        </p>
                        <p className="text-xs text-gray-400">{h.empresa} · {h.fecha}</p>
                      </div>
                    </div>
                    <div className="text-right">
                      {h.resumen?.total_activo && (
                        <p className="text-sm font-mono text-blue-700">
                          Activo: ${h.resumen.total_activo?.toLocaleString('es-MX')}
                        </p>
                      )}
                      {h.resumen?.ingresos && (
                        <p className="text-sm font-mono text-blue-700">
                          Ingresos: ${h.resumen.ingresos?.toLocaleString('es-MX')}
                        </p>
                      )}
                      <p className="text-xs text-gray-400">
                        {new Date(h.importado_en).toLocaleDateString('es-MX')}
                      </p>
                    </div>
                  </div>
                ))}
              </div>
            )}
          </CardContent>
        </Card>
      )}
    </div>
  );
};

export default ContalinkFinancialImport;
