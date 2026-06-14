import React, { useState, useEffect } from 'react';
import { Card, CardContent, CardHeader, CardTitle } from '../components/ui/card';
import { Button } from '../components/ui/button';
import { Badge } from '../components/ui/badge';
import { Progress } from '../components/ui/progress';
import { Alert, AlertDescription } from '../components/ui/alert';
import api from '../api/axios';
import { toast } from 'sonner';
import {
  DollarSign,
  TrendingUp,
  TrendingDown,
  AlertTriangle,
  CheckCircle,
  Loader2,
  Sparkles,
  Calculator,
  BarChart3,
  Info,
  FileText,
} from 'lucide-react';

// ── Helpers ──────────────────────────────────────────────────────────────────

const fmt = (n, dec = 0) =>
  new Intl.NumberFormat('es-MX', {
    style: 'currency',
    currency: 'MXN',
    minimumFractionDigits: dec,
    maximumFractionDigits: dec,
  }).format(n || 0);

const limpiarMarkdown = (text) =>
  text
    ?.replace(/#{1,3}\s*/g, '')
    .replace(/\*\*(.*?)\*\*/g, '$1')
    .replace(/\*(.*?)\*/g, '$1')
    .trim() || '';

const ScoreColor = (score) => {
  if (score >= 85) return { text: 'text-emerald-600', light: 'bg-emerald-50 border-emerald-200' };
  if (score >= 60) return { text: 'text-yellow-600', light: 'bg-yellow-50 border-yellow-200' };
  return { text: 'text-red-600', light: 'bg-red-50 border-red-200' };
};

// ── Datos estáticos bancos ────────────────────────────────────────────────────

const BANCOS_MEXICO = [
  { nombre: 'Konfío', tipo: 'Fintech', tasa_min: 24, tasa_max: 60, plazo_max: 36, monto_max: 5000000, requisito: 'Facturación mínima $500K/año', logo: '🏦' },
  { nombre: 'BBVA Empresarial', tipo: 'Banco', tasa_min: 14, tasa_max: 28, plazo_max: 60, monto_max: 20000000, requisito: '2 años de operación', logo: '🔵' },
  { nombre: 'Banorte PyME', tipo: 'Banco', tasa_min: 16, tasa_max: 30, plazo_max: 60, monto_max: 15000000, requisito: 'Historial crediticio', logo: '🟠' },
  { nombre: 'Kapital', tipo: 'Fintech', tasa_min: 18, tasa_max: 48, plazo_max: 24, monto_max: 3000000, requisito: 'Conectar SAT/ERP', logo: '⚡' },
  { nombre: 'HSBC Empresas', tipo: 'Banco', tasa_min: 15, tasa_max: 26, plazo_max: 60, monto_max: 25000000, requisito: 'Cuenta HSBC activa', logo: '🔴' },
  { nombre: 'Santander Negocios', tipo: 'Banco', tasa_min: 16, tasa_max: 28, plazo_max: 48, monto_max: 10000000, requisito: '1 año de operación', logo: '🔴' },
];

// ── Sub-componentes ───────────────────────────────────────────────────────────

const CapacidadCard = ({ nivel, data, onSelect }) => {
  const colors = {
    conservadora: 'border-emerald-200 hover:border-emerald-400',
    moderada: 'border-blue-200 hover:border-blue-400',
    agresiva: 'border-orange-200 hover:border-orange-400',
  };
  const labels = { conservadora: 'Conservador', moderada: 'Moderado', agresiva: 'Agresivo' };
  const icons = {
    conservadora: <CheckCircle className="h-5 w-5 text-emerald-500" />,
    moderada: <TrendingUp className="h-5 w-5 text-blue-500" />,
    agresiva: <AlertTriangle className="h-5 w-5 text-orange-500" />,
  };
  return (
    <button
      onClick={() => onSelect(data.cuota_max, data.credito_max_24m)}
      className={`w-full text-left p-4 rounded-lg border-2 transition-colors ${colors[nivel]} bg-white hover:shadow-sm`}
      data-testid={`capacidad-${nivel}`}
    >
      <div className="flex items-center gap-2 mb-2">
        {icons[nivel]}
        <span className="font-semibold text-sm text-slate-700">{labels[nivel]}</span>
      </div>
      <div className="text-xs text-slate-500 mb-3">{data.descripcion}</div>
      <div className="space-y-1">
        <div className="flex justify-between text-xs">
          <span className="text-slate-500">Cuota máx. mensual</span>
          <span className="font-mono font-semibold text-slate-800">{fmt(data.cuota_max)}</span>
        </div>
        <div className="flex justify-between text-xs">
          <span className="text-slate-500">Crédito máx. 24 m</span>
          <span className="font-mono font-bold text-slate-900">{fmt(data.credito_max_24m)}</span>
        </div>
      </div>
    </button>
  );
};

const BancoCard = ({ banco, onSimular }) => (
  <Card className="border-slate-200 hover:shadow-sm transition-shadow">
    <CardContent className="pt-4 pb-3">
      <div className="flex items-start justify-between mb-2">
        <div className="flex items-center gap-2">
          <span className="text-lg">{banco.logo}</span>
          <div>
            <p className="font-semibold text-xs text-slate-800">{banco.nombre}</p>
            <Badge
              className={`text-xs py-0 px-1.5 mt-0.5 ${
                banco.tipo === 'Fintech'
                  ? 'bg-emerald-100 text-emerald-700'
                  : 'bg-blue-100 text-blue-700'
              }`}
            >
              {banco.tipo}
            </Badge>
          </div>
        </div>
      </div>
      <div className="space-y-1 text-xs text-slate-600 mb-3">
        <div className="flex justify-between">
          <span className="text-slate-500">Tasa anual</span>
          <span className="font-mono font-semibold">{banco.tasa_min}% – {banco.tasa_max}%</span>
        </div>
        <div className="flex justify-between">
          <span className="text-slate-500">Plazo máx.</span>
          <span className="font-mono">{banco.plazo_max} meses</span>
        </div>
        <div className="flex justify-between">
          <span className="text-slate-500">Monto máx.</span>
          <span className="font-mono">{fmt(banco.monto_max)}</span>
        </div>
      </div>
      <p className="text-xs text-slate-400 mb-3 leading-tight">{banco.requisito}</p>
      <Button
        size="sm"
        variant="outline"
        className="w-full text-xs h-7 border-[#00C9A7] text-[#00C9A7] hover:bg-[#00C9A7] hover:text-white"
        onClick={() => onSimular(banco.tasa_min)}
        data-testid={`banco-simular-${banco.nombre.replace(/\s/g, '-')}`}
      >
        Simular con {banco.tasa_min}% anual
      </Button>
    </CardContent>
  </Card>
);

// ── Componente principal ──────────────────────────────────────────────────────

export default function Financiamiento() {
  const [capacidad, setCapacidad] = useState(null);
  const [loadingCap, setLoadingCap] = useState(true);
  const [form, setForm] = useState({ monto: '', tasa_anual: '18', plazo_meses: '24' });
  const [resultado, setResultado] = useState(null);
  const [simulating, setSimulating] = useState(false);

  useEffect(() => {
    setLoadingCap(true);
    api.get('/financiamiento/capacidad-pago')
      .then(r => setCapacidad(r.data))
      .catch(() => toast.error('No se pudo cargar la capacidad de pago'))
      .finally(() => setLoadingCap(false));
  }, []);

  const fillFromCapacidad = (cuotaMax, creditoMax) => {
    const monto = Math.round(creditoMax * 0.8);
    setForm(f => ({ ...f, monto: String(monto) }));
    toast.info(`Escenario cargado: ${fmt(monto)} con cuota máx ${fmt(cuotaMax)}/mes`);
  };

  const fillFromBanco = (tasa) => {
    setForm(f => ({ ...f, tasa_anual: String(tasa) }));
    toast.info(`Tasa cargada: ${tasa}% anual`);
  };

  const simular = async () => {
    if (!form.monto || parseFloat(form.monto) <= 0) {
      toast.error('Ingresa un monto válido');
      return;
    }
    setSimulating(true);
    setResultado(null);
    try {
      const r = await api.post('/financiamiento/simular', {
        monto: parseFloat(form.monto),
        tasa_anual: parseFloat(form.tasa_anual),
        plazo_meses: parseInt(form.plazo_meses),
      });
      setResultado(r.data);
    } catch {
      toast.error('Error al simular el crédito');
    } finally {
      setSimulating(false);
    }
  };

  // Derivados del resultado (Fix 3)
  const cat = resultado ? (resultado.simulacion.tasa_anual_pct + 2).toFixed(1) : '0';
  const ivaIntereses = resultado ? (resultado.simulacion.total_intereses * 0.16).toFixed(0) : '0';
  const costoTotalConIVA = resultado
    ? (resultado.simulacion.total_pagar + parseFloat(ivaIntereses)).toFixed(0)
    : '0';

  const colors = resultado ? ScoreColor(resultado.viabilidad.score) : null;

  // Fix 5 — Exportar PDF de tabla de amortización
  const exportarAmortizacion = () => {
    if (!resultado) return;
    const printWindow = window.open('', '_blank');
    const rows = resultado.tabla_amortizacion
      .map(
        r => `<tr>
          <td>${r.mes}</td>
          <td>$${r.cuota.toLocaleString('es-MX')}</td>
          <td>$${r.capital.toLocaleString('es-MX')}</td>
          <td>$${r.interes.toLocaleString('es-MX')}</td>
          <td>$${r.saldo.toLocaleString('es-MX')}</td>
        </tr>`
      )
      .join('');

    printWindow.document.write(`
      <html><head><title>Tabla de Amortización - TaxnFin</title>
      <style>
        body { font-family: Arial; padding: 20px; }
        h2 { color: #0F172A; }
        table { width: 100%; border-collapse: collapse; margin-top: 20px; }
        th { background: #0F172A; color: white; padding: 8px; text-align: right; }
        th:first-child { text-align: center; }
        td { padding: 8px; border-bottom: 1px solid #E2E8F0; text-align: right; }
        td:first-child { text-align: center; }
        tr:nth-child(even) { background: #F8FAFC; }
        .summary { display: grid; grid-template-columns: repeat(4,1fr); gap: 16px; margin-bottom: 20px; }
        .kpi { background: #F0FDF4; padding: 12px; border-radius: 8px; }
        .kpi label { font-size: 11px; color: #64748B; }
        .kpi strong { display: block; font-size: 18px; color: #10B981; }
      </style></head>
      <body>
        <h2>Tabla de Amortización — TaxnFin</h2>
        <div class="summary">
          <div class="kpi"><label>Monto</label><strong>$${resultado.simulacion.monto.toLocaleString('es-MX')}</strong></div>
          <div class="kpi"><label>Tasa anual</label><strong>${resultado.simulacion.tasa_anual_pct}%</strong></div>
          <div class="kpi"><label>Plazo</label><strong>${resultado.simulacion.plazo_meses} meses</strong></div>
          <div class="kpi"><label>Cuota mensual</label><strong>$${resultado.simulacion.cuota_mensual.toLocaleString('es-MX')}</strong></div>
        </div>
        <table>
          <thead><tr><th>Mes</th><th>Cuota</th><th>Capital</th><th>Interés</th><th>Saldo</th></tr></thead>
          <tbody>${rows}</tbody>
        </table>
        <p style="margin-top:20px;font-size:11px;color:#64748B">
          Generado por TaxnFin · cashflow.taxnfin.com ·
          CAT Aproximado: ${cat}% · IVA sobre intereses: $${Number(ivaIntereses).toLocaleString('es-MX')}
        </p>
      </body></html>
    `);
    printWindow.document.close();
    printWindow.print();
  };

  return (
    <div className="space-y-6">
      {/* Fix 1 — Título limpio */}
      <div className="mb-6">
        <h1 className="text-2xl font-bold text-[#0F172A] flex items-center gap-2">
          <DollarSign className="text-[#10B981]" size={28} />
          Simulador de Financiamiento
        </h1>
        <p className="text-gray-500 text-sm mt-1">Evalúa el impacto de un crédito en tu Cash Flow real</p>
      </div>

      {/* Fix 4 — Opciones de financiamiento en México */}
      <Card className="border-slate-200">
        <CardHeader className="pb-3">
          <CardTitle className="text-sm font-semibold text-slate-700 flex items-center gap-2">
            <DollarSign className="h-4 w-4 text-[#00C9A7]" />
            Opciones de Financiamiento en México
            <span className="text-xs font-normal text-slate-400 ml-1">— haz clic en "Simular" para cargar la tasa</span>
          </CardTitle>
        </CardHeader>
        <CardContent>
          <div className="grid grid-cols-2 sm:grid-cols-3 lg:grid-cols-6 gap-3">
            {BANCOS_MEXICO.map(banco => (
              <BancoCard key={banco.nombre} banco={banco} onSimular={fillFromBanco} />
            ))}
          </div>
        </CardContent>
      </Card>

      {/* Grid principal */}
      <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
        {/* ── Columna izquierda: Capacidad de pago + Formulario ── */}
        <div className="lg:col-span-1 space-y-5">

          {/* Capacidad de pago */}
          <Card className="border-slate-200">
            <CardHeader className="pb-3">
              <CardTitle className="text-sm font-semibold text-slate-700 flex items-center gap-2">
                <BarChart3 className="h-4 w-4 text-[#00C9A7]" />
                Tu capacidad de pago
              </CardTitle>
            </CardHeader>
            <CardContent>
              {loadingCap ? (
                <div className="flex items-center justify-center py-6">
                  <Loader2 className="h-5 w-5 animate-spin text-slate-400" />
                </div>
              ) : !capacidad || capacidad.status === 'insufficient_data' ? (
                <Alert>
                  <Info className="h-4 w-4" />
                  <AlertDescription className="text-xs">
                    Sin datos de flujo suficientes. Asegúrate de tener CFDIs o transacciones registradas.
                  </AlertDescription>
                </Alert>
              ) : (
                <div className="space-y-3">
                  <div className="grid grid-cols-2 gap-2 mb-4">
                    <div className="bg-slate-50 rounded p-2">
                      <p className="text-xs text-slate-500">Flujo prom. mensual</p>
                      <p className="font-mono font-bold text-sm text-slate-800">{fmt(capacidad.flujo_promedio_mensual)}</p>
                    </div>
                    <div className="bg-slate-50 rounded p-2">
                      <p className="text-xs text-slate-500">Flujo mín. mensual</p>
                      <p className="font-mono font-bold text-sm text-slate-800">{fmt(capacidad.flujo_minimo_mensual)}</p>
                    </div>
                  </div>
                  <p className="text-xs text-slate-500 mb-2">Haz clic en un escenario para cargarlo al simulador:</p>
                  <div className="space-y-2">
                    {['conservadora', 'moderada', 'agresiva'].map(n => (
                      <CapacidadCard
                        key={n}
                        nivel={n}
                        data={capacidad.capacidad_pago[n]}
                        onSelect={fillFromCapacidad}
                      />
                    ))}
                  </div>
                  <p className="text-xs text-slate-400 mt-2">
                    Fuente: {capacidad.fuente} · {capacidad.semanas_analizadas} semanas analizadas
                  </p>
                </div>
              )}
            </CardContent>
          </Card>

          {/* Formulario */}
          <Card className="border-slate-200">
            <CardHeader className="pb-3">
              <CardTitle className="text-sm font-semibold text-slate-700 flex items-center gap-2">
                <Calculator className="h-4 w-4 text-[#00C9A7]" />
                Parámetros del crédito
              </CardTitle>
            </CardHeader>
            <CardContent className="space-y-4">
              <div>
                <label className="text-xs font-medium text-slate-600 block mb-1">
                  Monto solicitado (MXN)
                </label>
                <input
                  type="number"
                  value={form.monto}
                  onChange={e => setForm(f => ({ ...f, monto: e.target.value }))}
                  placeholder="500,000"
                  className="w-full border border-slate-200 rounded px-3 py-2 text-sm font-mono focus:outline-none focus:ring-2 focus:ring-[#00C9A7]"
                  data-testid="input-monto"
                />
              </div>
              <div>
                <label className="text-xs font-medium text-slate-600 block mb-1">
                  Tasa anual (%)
                </label>
                <input
                  type="number"
                  value={form.tasa_anual}
                  onChange={e => setForm(f => ({ ...f, tasa_anual: e.target.value }))}
                  step="0.5"
                  min="0"
                  className="w-full border border-slate-200 rounded px-3 py-2 text-sm font-mono focus:outline-none focus:ring-2 focus:ring-[#00C9A7]"
                  data-testid="input-tasa"
                />
              </div>
              <div>
                <label className="text-xs font-medium text-slate-600 block mb-1">
                  Plazo (meses)
                </label>
                <select
                  value={form.plazo_meses}
                  onChange={e => setForm(f => ({ ...f, plazo_meses: e.target.value }))}
                  className="w-full border border-slate-200 rounded px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-[#00C9A7]"
                  data-testid="select-plazo"
                >
                  {[6, 12, 18, 24, 36, 48, 60].map(m => (
                    <option key={m} value={m}>{m} meses</option>
                  ))}
                </select>
              </div>
              <Button
                onClick={simular}
                disabled={simulating}
                className="w-full bg-[#00C9A7] hover:bg-[#00a88c] text-white font-semibold"
                data-testid="btn-simular"
              >
                {simulating ? <Loader2 className="h-4 w-4 animate-spin mr-2" /> : <Calculator className="h-4 w-4 mr-2" />}
                {simulating ? 'Simulando...' : 'Simular crédito'}
              </Button>
            </CardContent>
          </Card>
        </div>

        {/* ── Columna derecha: Resultados ── */}
        <div className="lg:col-span-2 space-y-5">
          {!resultado && !simulating && (
            <div className="flex flex-col items-center justify-center h-64 text-slate-400">
              <Calculator className="h-12 w-12 mb-3 opacity-30" />
              <p className="text-sm">Configura los parámetros y presiona "Simular crédito"</p>
            </div>
          )}

          {simulating && (
            <div className="flex flex-col items-center justify-center h-64 text-slate-400">
              <Loader2 className="h-10 w-10 animate-spin mb-3 text-[#00C9A7]" />
              <p className="text-sm">Calculando impacto en tu Cash Flow...</p>
            </div>
          )}

          {resultado && (
            <>
              {/* Score de viabilidad */}
              <Card className={`border-2 ${colors.light}`}>
                <CardContent className="pt-5">
                  <div className="flex items-start justify-between gap-4">
                    <div className="flex-1">
                      <div className="flex items-center gap-3 mb-3">
                        {resultado.viabilidad.score >= 85 ? (
                          <CheckCircle className="h-6 w-6 text-emerald-500" />
                        ) : resultado.viabilidad.score >= 60 ? (
                          <AlertTriangle className="h-6 w-6 text-yellow-500" />
                        ) : (
                          <AlertTriangle className="h-6 w-6 text-red-500" />
                        )}
                        <div>
                          <p className={`font-bold text-base ${colors.text}`}>
                            {resultado.viabilidad.mensaje}
                          </p>
                          <p className="text-xs text-slate-500">
                            {resultado.viabilidad.semanas_criticas} semanas con flujo negativo ·{' '}
                            Cobertura: {resultado.viabilidad.cobertura_cuota_pct}%
                          </p>
                        </div>
                      </div>
                      <Progress value={resultado.viabilidad.score} className="h-2" />
                      <p className="text-xs text-slate-400 mt-1">Score de viabilidad: {resultado.viabilidad.score}/100</p>
                    </div>
                    <div className="text-right shrink-0">
                      <p className={`text-4xl font-black ${colors.text}`}>{resultado.viabilidad.score}</p>
                      <p className="text-xs text-slate-400">/ 100</p>
                    </div>
                  </div>
                </CardContent>
              </Card>

              {/* Fix 3 — KPIs del crédito (4 originales + CAT + IVA + Costo total) */}
              <div className="grid grid-cols-2 sm:grid-cols-4 gap-3">
                {[
                  { label: 'Cuota mensual', value: fmt(resultado.simulacion.cuota_mensual), sub: `${fmt(resultado.simulacion.cuota_semanal)}/sem` },
                  { label: 'Total a pagar', value: fmt(resultado.simulacion.total_pagar), sub: `${resultado.simulacion.plazo_meses} meses` },
                  { label: 'Total intereses', value: fmt(resultado.simulacion.total_intereses), sub: `${resultado.simulacion.costo_financiero_pct}% del monto` },
                  { label: 'Tasa anual', value: `${resultado.simulacion.tasa_anual_pct}%`, sub: `${(resultado.simulacion.tasa_anual_pct / 12).toFixed(2)}% mensual` },
                  { label: 'CAT Aproximado', value: `${cat}%`, sub: 'incluye comisiones est.' },
                  { label: 'IVA sobre intereses (16%)', value: `$${Number(ivaIntereses).toLocaleString('es-MX')}`, sub: 'deducible ISR' },
                  { label: 'Costo total con IVA', value: `$${Number(costoTotalConIVA).toLocaleString('es-MX')}`, sub: 'costo real total' },
                ].map(kpi => (
                  <Card key={kpi.label} className="border-slate-200">
                    <CardContent className="pt-4 pb-3">
                      <p className="text-xs text-slate-500 mb-1">{kpi.label}</p>
                      <p className="font-mono font-bold text-base text-slate-800">{kpi.value}</p>
                      <p className="text-xs text-slate-400">{kpi.sub}</p>
                    </CardContent>
                  </Card>
                ))}
              </div>

              {/* Impacto en Cash Flow */}
              <Card className="border-slate-200">
                <CardHeader className="pb-2">
                  <CardTitle className="text-sm font-semibold text-slate-700 flex items-center gap-2">
                    <TrendingDown className="h-4 w-4 text-[#00C9A7]" />
                    Impacto en Cash Flow — próximas semanas
                  </CardTitle>
                </CardHeader>
                <CardContent>
                  <div className="overflow-x-auto">
                    <table className="w-full text-xs">
                      <thead>
                        <tr className="border-b border-slate-100">
                          <th className="text-left py-2 px-2 text-slate-500 font-medium">Semana</th>
                          <th className="text-right py-2 px-2 text-slate-500 font-medium">Flujo sin crédito</th>
                          <th className="text-right py-2 px-2 text-slate-500 font-medium">Cuota</th>
                          <th className="text-right py-2 px-2 text-slate-500 font-medium">Flujo con crédito</th>
                          <th className="text-center py-2 px-2 text-slate-500 font-medium">Estado</th>
                        </tr>
                      </thead>
                      <tbody>
                        {(resultado.impacto_cashflow || []).slice(0, 8).map((sem, i) => (
                          <tr
                            key={i}
                            className={`border-b border-slate-50 ${sem.alerta ? 'bg-red-50' : ''}`}
                            data-testid={`impacto-row-${i}`}
                          >
                            <td className="py-1.5 px-2 font-medium text-slate-700">
                              {sem.label || `S${sem.numero_semana}`}
                              <span className="text-slate-400 ml-1">{sem.date_range}</span>
                            </td>
                            <td className="py-1.5 px-2 text-right font-mono text-slate-600">
                              {fmt(sem.flujo_neto_sin_credito)}
                            </td>
                            <td className="py-1.5 px-2 text-right font-mono text-red-400">
                              -{fmt(sem.cuota_credito)}
                            </td>
                            <td className={`py-1.5 px-2 text-right font-mono font-semibold ${sem.alerta ? 'text-red-600' : 'text-emerald-600'}`}>
                              {fmt(sem.flujo_neto_con_credito)}
                            </td>
                            <td className="py-1.5 px-2 text-center">
                              {sem.alerta ? (
                                <Badge variant="destructive" className="text-xs py-0">Déficit</Badge>
                              ) : (
                                <Badge className="bg-emerald-100 text-emerald-700 text-xs py-0">OK</Badge>
                              )}
                            </td>
                          </tr>
                        ))}
                      </tbody>
                    </table>
                  </div>
                </CardContent>
              </Card>

              {/* Fix 2 — Análisis IA sin markdown */}
              {resultado.analisis_ia && (
                <Card className="border-violet-200 bg-violet-50">
                  <CardHeader className="pb-2">
                    <CardTitle className="text-sm font-semibold text-violet-700 flex items-center gap-2">
                      <Sparkles className="h-4 w-4" />
                      Análisis IA — CFO Virtual
                    </CardTitle>
                  </CardHeader>
                  <CardContent>
                    <p className="text-sm text-slate-700 leading-relaxed">
                      {limpiarMarkdown(resultado.analisis_ia)}
                    </p>
                  </CardContent>
                </Card>
              )}

              {/* Fix 5 — Tabla de amortización con botón PDF */}
              <details className="group">
                <summary className="cursor-pointer text-sm font-medium text-slate-600 hover:text-slate-900 flex items-center gap-2 select-none">
                  <BarChart3 className="h-4 w-4" />
                  Ver tabla de amortización completa ({resultado.tabla_amortizacion?.length} meses)
                </summary>
                <Card className="border-slate-200 mt-3">
                  <CardHeader className="pb-2 flex flex-row items-center justify-between">
                    <CardTitle className="text-sm font-semibold text-slate-700">
                      Tabla de amortización
                    </CardTitle>
                    <Button
                      size="sm"
                      variant="outline"
                      className="h-7 text-xs gap-1.5"
                      onClick={exportarAmortizacion}
                      data-testid="btn-exportar-pdf"
                    >
                      <FileText className="h-3.5 w-3.5" />
                      Exportar PDF
                    </Button>
                  </CardHeader>
                  <CardContent className="pt-0">
                    <div className="overflow-x-auto max-h-64 overflow-y-auto">
                      <table className="w-full text-xs">
                        <thead className="sticky top-0 bg-white">
                          <tr className="border-b border-slate-100">
                            <th className="text-left py-1.5 px-2 text-slate-500">Mes</th>
                            <th className="text-right py-1.5 px-2 text-slate-500">Cuota</th>
                            <th className="text-right py-1.5 px-2 text-slate-500">Capital</th>
                            <th className="text-right py-1.5 px-2 text-slate-500">Interés</th>
                            <th className="text-right py-1.5 px-2 text-slate-500">Saldo</th>
                          </tr>
                        </thead>
                        <tbody>
                          {(resultado.tabla_amortizacion || []).map(row => (
                            <tr key={row.mes} className="border-b border-slate-50 hover:bg-slate-50">
                              <td className="py-1 px-2 text-slate-600">{row.mes}</td>
                              <td className="py-1 px-2 text-right font-mono text-slate-600">{fmt(row.cuota)}</td>
                              <td className="py-1 px-2 text-right font-mono text-emerald-600">{fmt(row.capital)}</td>
                              <td className="py-1 px-2 text-right font-mono text-red-500">{fmt(row.interes)}</td>
                              <td className="py-1 px-2 text-right font-mono text-slate-800">{fmt(row.saldo)}</td>
                            </tr>
                          ))}
                        </tbody>
                      </table>
                    </div>
                  </CardContent>
                </Card>
              </details>
            </>
          )}
        </div>
      </div>
    </div>
  );
}
