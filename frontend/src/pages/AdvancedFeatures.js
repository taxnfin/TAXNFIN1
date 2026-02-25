import { useState } from 'react';
import api from '@/api/axios';
import { Button } from '@/components/ui/button';
import { Input } from '@/components/ui/input';
import { Label } from '@/components/ui/label';
import { Textarea } from '@/components/ui/textarea';
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card';
import { Dialog, DialogContent, DialogDescription, DialogFooter, DialogHeader, DialogTitle, DialogTrigger } from '@/components/ui/dialog';
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from '@/components/ui/select';
import { Badge } from '@/components/ui/badge';
import { Progress } from '@/components/ui/progress';
import { toast } from 'sonner';
import { Brain, Zap, Bell, Sparkles, GitBranch, Download, FileText, Cpu, TrendingUp, CheckCircle } from 'lucide-react';

const AdvancedFeatures = () => {
  const [loading, setLoading] = useState(false);
  const [analysis, setAnalysis] = useState(null);
  const [reconResult, setReconResult] = useState(null);
  const [scenarioDialog, setScenarioDialog] = useState(false);
  const [optimizationDialog, setOptimizationDialog] = useState(false);
  const [optimizationResult, setOptimizationResult] = useState(null);
  const [optimizationConfig, setOptimizationConfig] = useState({
    generaciones: 50,
    poblacion: 100,
    max_retraso_dias: 30,
    max_adelanto_dias: 15
  });
  const [scenarioForm, setScenarioForm] = useState({
    nombre: '',
    descripcion: '',
    tipo: 'adelantar_pago',
    monto: '',
    fecha: ''
  });

  const runAnalysis = async () => {
    setLoading(true);
    try {
      const res = await api.get('/ai/predictive-analysis');
      if (res.data.status === 'insufficient_data') {
        toast.warning(res.data.message);
      } else {
        setAnalysis(res.data);
        toast.success('Análisis completado');
      }
    } catch (error) {
      toast.error('Error en análisis predictivo');
    } finally {
      setLoading(false);
    }
  };

  const runAutoRecon = async () => {
    try {
      const res = await api.post('/reconciliation/auto-reconcile-batch?min_score=85');
      setReconResult(res.data);
      toast.success(`${res.data.reconciled} movimientos conciliados`);
    } catch (error) {
      toast.error('Error en conciliación automática');
    }
  };

  const checkAlerts = async () => {
    try {
      const res = await api.post('/alerts/check-and-send');
      toast.success(`${res.data.alerts_sent} alertas enviadas`);
    } catch (error) {
      toast.error('Error verificando alertas');
    }
  };

  const createScenario = async () => {
    try {
      const modificacion = {
        tipo: scenarioForm.tipo,
        nuevo_monto: scenarioForm.monto ? parseFloat(scenarioForm.monto) : undefined,
        nueva_fecha: scenarioForm.fecha || undefined,
        razon: 'Simulación desde UI'
      };

      const res = await api.post('/scenarios/create', {
        nombre: scenarioForm.nombre,
        descripcion: scenarioForm.descripcion,
        modificaciones: [modificacion]
      });

      toast.success('Escenario creado exitosamente');
      setScenarioDialog(false);
      setScenarioForm({ nombre: '', descripcion: '', tipo: 'adelantar_pago', monto: '', fecha: '' });
    } catch (error) {
      // More descriptive error messages
      if (error.response?.status === 403) {
        toast.error('No tiene permisos para crear escenarios. Se requiere rol Admin o CFO.');
      } else if (error.response?.data?.detail) {
        toast.error('Error creando escenario: ' + error.response.data.detail);
      } else {
        toast.error('Error creando escenario. Verifique que existan datos de cashflow.');
      }
    }
  };

  const exportData = async (formato) => {
    try {
      const today = new Date();
      const startDate = new Date(today.getFullYear(), today.getMonth(), 1);
      const url = `/export/${formato}?fecha_inicio=${startDate.toISOString()}&fecha_fin=${today.toISOString()}`;
      
      const res = await api.get(url, { responseType: 'blob' });
      const blob = new Blob([res.data]);
      const link = document.createElement('a');
      link.href = window.URL.createObjectURL(blob);
      link.download = `export_${formato}_${today.getTime()}.${formato === 'xml-fiscal' ? 'xml' : formato === 'alegra' ? 'json' : 'csv'}`;
      link.click();
      
      toast.success(`Exportación ${formato} completada`);
    } catch (error) {
      toast.error('Error en exportación');
    }
  };

  const runGeneticOptimization = async () => {
    setLoading(true);
    try {
      toast.info('Ejecutando optimización genética... (esto puede tomar 30-60 segundos)');
      
      const res = await api.post('/optimize/genetic', {
        objetivos: {
          maximizar_liquidez: true,
          minimizar_costos: true,
          evitar_crisis: true
        },
        restricciones: {
          max_retraso_dias: optimizationConfig.max_retraso_dias,
          max_adelanto_dias: optimizationConfig.max_adelanto_dias,
          min_saldo: 50000
        },
        parametros: {
          generaciones: optimizationConfig.generaciones,
          poblacion: optimizationConfig.poblacion,
          prob_mutacion: 0.2
        }
      });
      
      // Check if we got insufficient data response
      if (res.data.status === 'insufficient_data') {
        toast.warning(res.data.message || 'Se necesitan al menos 5 transacciones proyectadas para optimizar. Primero cargue datos en el módulo de Proyecciones.');
        setOptimizationDialog(false);
        return;
      }
      
      setOptimizationResult(res.data);
      toast.success('¡Optimización completada! Encontradas mejores soluciones');
      setOptimizationDialog(false);
    } catch (error) {
      // More descriptive error messages
      if (error.response?.status === 403) {
        toast.error('No tiene permisos para ejecutar optimizaciones. Se requiere rol Admin o CFO.');
      } else {
        toast.error('Error en optimización genética: ' + (error.response?.data?.detail || 'Error desconocido'));
      }
    } finally {
      setLoading(false);
    }
  };

  const applyOptimization = async (optimizationId) => {
    try {
      const res = await api.post(`/optimize/apply/${optimizationId}`);
      toast.success(`${res.data.modificaciones_aplicadas} modificaciones aplicadas. Mejora esperada: $${res.data.mejora_esperada.toLocaleString()}`);
      setOptimizationResult(null);
    } catch (error) {
      // More descriptive error messages
      if (error.response?.status === 404) {
        toast.error('Optimización no encontrada. Por favor ejecute una nueva optimización primero.');
      } else if (error.response?.status === 403) {
        toast.error('No tiene permisos para aplicar optimizaciones. Se requiere rol Admin o CFO.');
      } else {
        toast.error('Error aplicando optimización: ' + (error.response?.data?.detail || 'Error desconocido'));
      }
    }
  };

  return (
    <div className="p-8 space-y-6" data-testid="advanced-features-page">
      <div>
        <h1 className="text-4xl font-bold text-[#0F172A] mb-2 flex items-center gap-3" style={{fontFamily: 'Manrope'}}>
          <Sparkles className="text-[#10B981]" size={36} />
          Funcionalidades Avanzadas
        </h1>
        <p className="text-[#64748B]">IA, Automatización y Análisis Predictivo</p>
      </div>

      <div className="grid grid-cols-1 md:grid-cols-5 gap-4">
        <Card className="border-[#10B981]" data-testid="card-predictive">
          <CardHeader>
            <CardTitle className="flex items-center gap-2 text-[#10B981] text-base">
              <Brain size={20} />
              Análisis Predictivo
            </CardTitle>
            <CardDescription className="text-xs">ML + GPT-5.2</CardDescription>
          </CardHeader>
          <CardContent>
            <Button onClick={runAnalysis} disabled={loading} className="w-full bg-[#10B981]" data-testid="run-analysis-btn" size="sm">
              {loading ? 'Analizando...' : 'Ejecutar'}
            </Button>
          </CardContent>
        </Card>

        <Card className="border-[#F59E0B]">
          <CardHeader>
            <CardTitle className="flex items-center gap-2 text-[#F59E0B] text-base">
              <Zap size={20} />
              Auto-Conciliación
            </CardTitle>
            <CardDescription className="text-xs">Matching inteligente</CardDescription>
          </CardHeader>
          <CardContent>
            <Button onClick={runAutoRecon} className="w-full bg-[#F59E0B]" data-testid="run-recon-btn" size="sm">
              Ejecutar
            </Button>
          </CardContent>
        </Card>

        <Card className="border-[#EF4444]">
          <CardHeader>
            <CardTitle className="flex items-center gap-2 text-[#EF4444] text-base">
              <Bell size={20} />
              Alertas
            </CardTitle>
            <CardDescription className="text-xs">Monitoreo automático</CardDescription>
          </CardHeader>
          <CardContent>
            <Button onClick={checkAlerts} className="w-full bg-[#EF4444]" data-testid="check-alerts-btn" size="sm">
              Verificar
            </Button>
          </CardContent>
        </Card>

        <Card className="border-[#8B5CF6]">
          <CardHeader>
            <CardTitle className="flex items-center gap-2 text-[#8B5CF6] text-base">
              <GitBranch size={20} />
              Escenarios
            </CardTitle>
            <CardDescription className="text-xs">Qué pasaría si</CardDescription>
          </CardHeader>
          <CardContent>
            <Dialog open={scenarioDialog} onOpenChange={setScenarioDialog}>
              <DialogTrigger asChild>
                <Button className="w-full bg-[#8B5CF6]" data-testid="create-scenario-btn" size="sm">
                  Crear
                </Button>
              </DialogTrigger>
              <DialogContent>
                <DialogHeader>
                  <DialogTitle>Nuevo Escenario</DialogTitle>
                  <DialogDescription>Simula cambios y ve el impacto en tu flujo</DialogDescription>
                </DialogHeader>
                <div className="space-y-4">
                  <div>
                    <Label>Nombre del Escenario</Label>
                    <Input value={scenarioForm.nombre} onChange={(e) => setScenarioForm({...scenarioForm, nombre: e.target.value})} placeholder="Ej: Adelantar pago proveedor" />
                  </div>
                  <div>
                    <Label>Descripción</Label>
                    <Textarea value={scenarioForm.descripcion} onChange={(e) => setScenarioForm({...scenarioForm, descripcion: e.target.value})} placeholder="Describe el escenario..." />
                  </div>
                  <div>
                    <Label>Tipo de Modificación</Label>
                    <Select value={scenarioForm.tipo} onValueChange={(v) => setScenarioForm({...scenarioForm, tipo: v})}>
                      <SelectTrigger>
                        <SelectValue />
                      </SelectTrigger>
                      <SelectContent>
                        <SelectItem value="adelantar_pago">Adelantar Pago</SelectItem>
                        <SelectItem value="retrasar_cobro">Retrasar Cobro</SelectItem>
                        <SelectItem value="ajustar_monto">Ajustar Monto</SelectItem>
                        <SelectItem value="agregar_transaccion">Agregar Transacción</SelectItem>
                      </SelectContent>
                    </Select>
                  </div>
                </div>
                <DialogFooter>
                  <Button onClick={createScenario}>Crear Escenario</Button>
                </DialogFooter>
              </DialogContent>
            </Dialog>
          </CardContent>
        </Card>

        <Card className="border-[#EC4899] bg-gradient-to-br from-pink-50 to-white">
          <CardHeader>
            <CardTitle className="flex items-center gap-2 text-[#EC4899] text-base">
              <Cpu size={20} />
              CFO Virtual
            </CardTitle>
            <CardDescription className="text-xs">Algoritmos Genéticos</CardDescription>
          </CardHeader>
          <CardContent>
            <Dialog open={optimizationDialog} onOpenChange={setOptimizationDialog}>
              <DialogTrigger asChild>
                <Button className="w-full bg-[#EC4899]" data-testid="optimize-genetic-btn" size="sm">
                  Optimizar
                </Button>
              </DialogTrigger>
              <DialogContent>
                <DialogHeader>
                  <DialogTitle className="flex items-center gap-2">
                    <Cpu className="text-[#EC4899]" />
                    Optimización Genética
                  </DialogTitle>
                  <DialogDescription>
                    El algoritmo evaluará miles de combinaciones para encontrar la solución óptima
                  </DialogDescription>
                </DialogHeader>
                <div className="space-y-4">
                  <div>
                    <Label>Generaciones</Label>
                    <Input 
                      type="number" 
                      value={optimizationConfig.generaciones} 
                      onChange={(e) => setOptimizationConfig({...optimizationConfig, generaciones: parseInt(e.target.value)})} 
                    />
                    <p className="text-xs text-gray-500 mt-1">Más generaciones = mejor resultado (más tiempo)</p>
                  </div>
                  <div>
                    <Label>Tamaño Población</Label>
                    <Input 
                      type="number" 
                      value={optimizationConfig.poblacion} 
                      onChange={(e) => setOptimizationConfig({...optimizationConfig, poblacion: parseInt(e.target.value)})} 
                    />
                  </div>
                  <div className="grid grid-cols-2 gap-4">
                    <div>
                      <Label>Max Retraso (días)</Label>
                      <Input 
                        type="number" 
                        value={optimizationConfig.max_retraso_dias} 
                        onChange={(e) => setOptimizationConfig({...optimizationConfig, max_retraso_dias: parseInt(e.target.value)})} 
                      />
                    </div>
                    <div>
                      <Label>Max Adelanto (días)</Label>
                      <Input 
                        type="number" 
                        value={optimizationConfig.max_adelanto_dias} 
                        onChange={(e) => setOptimizationConfig({...optimizationConfig, max_adelanto_dias: parseInt(e.target.value)})} 
                      />
                    </div>
                  </div>
                </div>
                <DialogFooter>
                  <Button onClick={runGeneticOptimization} disabled={loading} data-testid="run-genetic-opt">
                    {loading ? 'Optimizando...' : 'Iniciar Optimización'}
                  </Button>
                </DialogFooter>
              </DialogContent>
            </Dialog>
          </CardContent>
        </Card>
      </div>

      {analysis && (
        <Card className="border-[#10B981]" data-testid="analysis-results">
          <CardHeader>
            <CardTitle>Resultados del Análisis Predictivo</CardTitle>
          </CardHeader>
          <CardContent>
            <div className="grid grid-cols-3 gap-4 mb-4">
              <div className="p-4 bg-[#F0FDF4] rounded">
                <p className="text-sm text-[#166534]">Ingreso Promedio Semanal</p>
                <p className="text-2xl font-bold mono text-[#10B981]">${analysis.analisis_cuantitativo.ingresos_promedio_semanal.toLocaleString('es-MX')}</p>
              </div>
              <div className="p-4 bg-[#FEF2F2] rounded">
                <p className="text-sm text-[#991B1B]">Egreso Promedio Semanal</p>
                <p className="text-2xl font-bold mono text-[#EF4444]">${analysis.analisis_cuantitativo.egresos_promedio_semanal.toLocaleString('es-MX')}</p>
              </div>
              <div className="p-4 bg-[#F8FAFC] rounded">
                <p className="text-sm text-[#64748B]">Flujo Neto Promedio</p>
                <p className="text-2xl font-bold mono text-[#0F172A]">${analysis.analisis_cuantitativo.flujo_neto_promedio.toLocaleString('es-MX')}</p>
              </div>
            </div>
            <div className="p-4 bg-[#F8FAFC] rounded">
              <h3 className="font-semibold mb-2">Predicciones (8 semanas):</h3>
              {analysis.predicciones_8_semanas.slice(0, 4).map(pred => (
                <div key={pred.semana_futura} className="text-sm mb-1">
                  S+{pred.semana_futura}: Neto ${pred.flujo_neto_predicho.toLocaleString()} ({pred.confianza})
                </div>
              ))}
            </div>
            <div className="mt-4 p-4 bg-white border rounded">
              <h3 className="font-semibold mb-2">Insights IA:</h3>
              <div className="text-sm whitespace-pre-wrap">{analysis.insights_ia}</div>
            </div>
          </CardContent>
        </Card>
      )}

      {reconResult && (
        <Card className="border-[#F59E0B]">
          <CardHeader>
            <CardTitle>Resultado Auto-Conciliación</CardTitle>
          </CardHeader>
          <CardContent>
            <div className="grid grid-cols-3 gap-4 text-center">
              <div>
                <p className="text-3xl font-bold mono text-[#10B981]">{reconResult.reconciled}</p>
                <p className="text-sm text-[#64748B]">Conciliados</p>
              </div>
              <div>
                <p className="text-3xl font-bold mono text-[#F59E0B]">{reconResult.skipped}</p>
                <p className="text-sm text-[#64748B]">Omitidos</p>
              </div>
              <div>
                <p className="text-3xl font-bold mono text-[#64748B]">{reconResult.total_processed}</p>
                <p className="text-sm text-[#64748B]">Total</p>
              </div>
            </div>
          </CardContent>
        </Card>
      )}

      {optimizationResult && (
        <Card className="border-[#EC4899] bg-gradient-to-br from-pink-50 to-white" data-testid="optimization-result">
          <CardHeader>
            <CardTitle className="flex items-center gap-2 text-[#EC4899]">
              <Cpu size={24} />
              Optimización Genética Completada
            </CardTitle>
            <CardDescription>
              {optimizationResult.generaciones} generaciones • {optimizationResult.top_5_soluciones?.length || 0} soluciones óptimas encontradas
            </CardDescription>
          </CardHeader>
          <CardContent className="space-y-4">
            <div className="p-4 bg-gradient-to-r from-pink-100 to-purple-100 rounded-lg">
              <div className="flex items-center justify-between mb-3">
                <div>
                  <p className="text-sm font-semibold text-[#BE185D]">🏆 Mejor Solución</p>
                  <Badge className="bg-[#EC4899] mt-1">Rank #1</Badge>
                </div>
                <CheckCircle className="text-[#10B981]" size={32} />
              </div>
              
              <div className="grid grid-cols-2 gap-4 mb-3">
                <div>
                  <p className="text-xs text-[#BE185D]">Mejora en Flujo Neto</p>
                  <p className="text-2xl font-bold mono text-[#10B981]">
                    +${optimizationResult.mejora_vs_baseline?.flujo_neto.toLocaleString('es-MX')}
                  </p>
                </div>
                <div>
                  <p className="text-xs text-[#BE185D]">Crisis Evitadas</p>
                  <p className="text-2xl font-bold mono text-[#10B981]">
                    {optimizationResult.mejora_vs_baseline?.semanas_criticas_resueltas} semanas
                  </p>
                </div>
              </div>

              <div className="space-y-2">
                <p className="text-sm font-semibold text-[#BE185D]">Modificaciones Sugeridas:</p>
                <div className="max-h-48 overflow-y-auto space-y-2">
                  {optimizationResult.mejor_solucion?.modificaciones?.slice(0, 5).map((mod, idx) => (
                    <div key={idx} className="p-2 bg-white rounded text-xs">
                      <span className="font-semibold">{mod.tipo.replace(/_/g, ' ')}</span>: {mod.razon}
                    </div>
                  ))}
                </div>
              </div>

              <div className="mt-4 flex gap-2">
                <Button 
                  onClick={() => applyOptimization(optimizationResult.optimization_id)} 
                  className="bg-[#10B981] flex-1"
                  data-testid="apply-optimization-btn"
                >
                  <CheckCircle size={16} className="mr-2" />
                  Aplicar Solución
                </Button>
                <Button 
                  onClick={() => setOptimizationResult(null)} 
                  variant="outline"
                >
                  Descartar
                </Button>
              </div>
            </div>

            {optimizationResult.top_5_soluciones && optimizationResult.top_5_soluciones.length > 1 && (
              <div>
                <p className="text-sm font-semibold mb-2">Otras Soluciones Óptimas:</p>
                <div className="space-y-2">
                  {optimizationResult.top_5_soluciones.slice(1, 4).map((sol) => (
                    <div key={sol.rank} className="p-3 border rounded hover:bg-gray-50">
                      <div className="flex justify-between items-center">
                        <div>
                          <Badge variant="outline">Rank #{sol.rank}</Badge>
                          <p className="text-sm mt-1">Mejora: ${sol.mejora_flujo_neto.toLocaleString()}</p>
                        </div>
                        <p className="text-xs text-gray-500">{sol.modificaciones.length} cambios</p>
                      </div>
                    </div>
                  ))}
                </div>
              </div>
            )}
          </CardContent>
        </Card>
      )}

      <Card className="border-[#3B82F6]">
        <CardHeader>
          <CardTitle className="flex items-center gap-2">
            <Download size={24} />
            Exportaciones Contables
          </CardTitle>
          <CardDescription>Formatos listos para sistemas contables</CardDescription>
        </CardHeader>
        <CardContent>
          <div className="grid grid-cols-2 md:grid-cols-4 gap-3">
            <Button onClick={() => exportData('coi')} variant="outline" className="gap-2" data-testid="export-coi">
              <FileText size={16} />
              COI
            </Button>
            <Button onClick={() => exportData('xml-fiscal')} variant="outline" className="gap-2">
              <FileText size={16} />
              XML Fiscal
            </Button>
            <Button onClick={() => exportData('alegra')} variant="outline" className="gap-2" data-testid="export-alegra">
              <FileText size={16} />
              Alegra
            </Button>
            <Button onClick={() => api.get('/export/cashflow?formato=excel', {responseType: 'blob'}).then(res => {
              const blob = new Blob([res.data]);
              const link = document.createElement('a');
              link.href = window.URL.createObjectURL(blob);
              link.download = `cashflow_${Date.now()}.csv`;
              link.click();
              toast.success('Cashflow exportado');
            })} variant="outline" className="gap-2">
              <FileText size={16} />
              Cashflow
            </Button>
          </div>
        </CardContent>
      </Card>

      <Card className="border-[#3B82F6]">
        <CardHeader>
          <CardTitle>Integraciones Bancarias</CardTitle>
          <CardDescription>APIs disponibles</CardDescription>
        </CardHeader>
        <CardContent>
          <div className="grid grid-cols-2 md:grid-cols-5 gap-3 text-sm">
            <div className="p-3 bg-[#EFF6FF] rounded text-center">
              <p className="font-semibold text-[#1E40AF]">BBVA</p>
            </div>
            <div className="p-3 bg-[#EFF6FF] rounded text-center">
              <p className="font-semibold text-[#1E40AF]">Santander</p>
            </div>
            <div className="p-3 bg-[#EFF6FF] rounded text-center">
              <p className="font-semibold text-[#1E40AF]">Banorte</p>
            </div>
            <div className="p-3 bg-[#F0FDF4] rounded text-center">
              <p className="font-semibold text-[#166534]">Bajío ✅</p>
            </div>
            <div className="p-3 bg-[#F0FDF4] rounded text-center">
              <p className="font-semibold text-[#166534]">Amex ✅</p>
            </div>
          </div>
        </CardContent>
      </Card>
    </div>
  );
};

export default AdvancedFeatures;
