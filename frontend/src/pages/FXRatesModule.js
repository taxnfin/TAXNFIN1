import { useState, useEffect } from 'react';
import api from '@/api/axios';
import { Button } from '@/components/ui/button';
import { Input } from '@/components/ui/input';
import { Label } from '@/components/ui/label';
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from '@/components/ui/select';
import { Dialog, DialogContent, DialogDescription, DialogFooter, DialogHeader, DialogTitle, DialogTrigger } from '@/components/ui/dialog';
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card';
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from '@/components/ui/table';
import { Tabs, TabsContent, TabsList, TabsTrigger } from '@/components/ui/tabs';
import { toast } from 'sonner';
import { Plus, Trash2, RefreshCw, DollarSign, TrendingUp, Calendar, ChevronLeft, ChevronRight } from 'lucide-react';
import { format } from 'date-fns';
import { es } from 'date-fns/locale';

const CURRENCIES = [
  { code: 'MXN', name: 'Peso Mexicano', symbol: '$' },
  { code: 'USD', name: 'Dólar Estadounidense', symbol: '$' },
  { code: 'EUR', name: 'Euro', symbol: '€' },
  { code: 'GBP', name: 'Libra Esterlina', symbol: '£' },
  { code: 'CAD', name: 'Dólar Canadiense', symbol: '$' },
  { code: 'JPY', name: 'Yen Japonés', symbol: '¥' },
  { code: 'CHF', name: 'Franco Suizo', symbol: 'CHF' },
  { code: 'CNY', name: 'Yuan Chino', symbol: '¥' },
];

const MONTH_NAMES = ['Ene', 'Feb', 'Mar', 'Abr', 'May', 'Jun', 'Jul', 'Ago', 'Sep', 'Oct', 'Nov', 'Dic'];

const FXRatesModule = () => {
  const [rates, setRates] = useState([]);
  const [latestRates, setLatestRates] = useState({});
  const [yearData, setYearData] = useState(null);
  const [selectedYear, setSelectedYear] = useState(new Date().getFullYear());
  const [loading, setLoading] = useState(true);
  const [loadingYear, setLoadingYear] = useState(false);
  const [dialogOpen, setDialogOpen] = useState(false);
  const [activeTab, setActiveTab] = useState('latest');
  const [formData, setFormData] = useState({
    moneda_base: 'MXN',
    moneda_cotizada: 'USD',
    tipo_cambio: '',
    fecha_vigencia: format(new Date(), "yyyy-MM-dd'T'HH:mm")
  });

  useEffect(() => {
    loadData();
  }, []);

  useEffect(() => {
    if (activeTab === 'year') {
      loadYearData();
    }
  }, [activeTab, selectedYear]);

  const loadData = async () => {
    try {
      const [ratesRes, latestRes] = await Promise.all([
        api.get('/fx-rates'),
        api.get('/fx-rates/latest')
      ]);
      setRates(ratesRes.data);
      setLatestRates(latestRes.data);
    } catch (error) {
      toast.error('Error cargando tipos de cambio');
    } finally {
      setLoading(false);
    }
  };

  const loadYearData = async () => {
    setLoadingYear(true);
    try {
      const res = await api.get(`/fx-rates/year/${selectedYear}`);
      setYearData(res.data);
    } catch (error) {
      toast.error('Error cargando tipos de cambio del año');
    } finally {
      setLoadingYear(false);
    }
  };

  const handleSync = async () => {
    try {
      toast.info('Sincronizando tipos de cambio...');
      const res = await api.post('/fx-rates/sync');
      if (res.data.success) {
        toast.success(res.data.message || `Se actualizaron ${res.data.updated} tasas`);
        loadData();
      } else {
        toast.error('Error en la sincronización');
      }
    } catch (error) {
      toast.error(error.response?.data?.detail || 'Error sincronizando tipos de cambio');
    }
  };

  const handleSubmit = async (e) => {
    e.preventDefault();
    try {
      await api.post('/fx-rates', {
        ...formData,
        tipo_cambio: parseFloat(formData.tipo_cambio)
      });
      toast.success('Tipo de cambio registrado');
      setDialogOpen(false);
      loadData();
      setFormData({
        moneda_base: 'MXN',
        moneda_cotizada: 'USD',
        tipo_cambio: '',
        fecha_vigencia: format(new Date(), "yyyy-MM-dd'T'HH:mm")
      });
    } catch (error) {
      toast.error(error.response?.data?.detail || 'Error registrando tipo de cambio');
    }
  };

  const handleDelete = async (rateId) => {
    if (!confirm('¿Eliminar este tipo de cambio?')) return;
    try {
      await api.delete(`/fx-rates/${rateId}`);
      toast.success('Tipo de cambio eliminado');
      loadData();
    } catch (error) {
      toast.error('Error eliminando tipo de cambio');
    }
  };

  if (loading) return <div className="p-8">Cargando...</div>;

  return (
    <div className="p-8 space-y-6" data-testid="fx-rates-page">
      <div className="flex justify-between items-center">
        <div>
          <h1 className="text-4xl font-bold text-[#0F172A] mb-2" style={{fontFamily: 'Manrope'}}>Tipos de Cambio</h1>
          <p className="text-[#64748B]">Gestión de tasas de cambio para conversión de monedas</p>
        </div>
        <div className="flex gap-2">
          <Button variant="outline" onClick={handleSync} className="gap-2" data-testid="sync-fx-rates-button">
            <RefreshCw size={16} />
            Actualizar
          </Button>
          <Dialog open={dialogOpen} onOpenChange={setDialogOpen}>
            <DialogTrigger asChild>
              <Button className="bg-[#0F172A] hover:bg-[#1E293B] gap-2" data-testid="add-fx-rate-button">
                <Plus size={16} />
                Nuevo Tipo de Cambio
              </Button>
            </DialogTrigger>
            <DialogContent>
              <DialogHeader>
                <DialogTitle>Registrar Tipo de Cambio</DialogTitle>
                <DialogDescription>Ingresa la tasa de conversión entre dos monedas</DialogDescription>
              </DialogHeader>
              <form onSubmit={handleSubmit} className="space-y-4">
                <div className="grid grid-cols-2 gap-4">
                  <div className="space-y-2">
                    <Label>Moneda Base</Label>
                    <Select value={formData.moneda_base} onValueChange={(v) => setFormData({...formData, moneda_base: v})}>
                      <SelectTrigger>
                        <SelectValue />
                      </SelectTrigger>
                      <SelectContent>
                        {CURRENCIES.map(c => (
                          <SelectItem key={c.code} value={c.code}>{c.code} - {c.name}</SelectItem>
                        ))}
                      </SelectContent>
                    </Select>
                  </div>
                  <div className="space-y-2">
                    <Label>Moneda Cotizada</Label>
                    <Select value={formData.moneda_cotizada} onValueChange={(v) => setFormData({...formData, moneda_cotizada: v})}>
                      <SelectTrigger>
                        <SelectValue />
                      </SelectTrigger>
                      <SelectContent>
                        {CURRENCIES.map(c => (
                          <SelectItem key={c.code} value={c.code}>{c.code} - {c.name}</SelectItem>
                        ))}
                      </SelectContent>
                    </Select>
                  </div>
                </div>

                <div className="space-y-2">
                  <Label>Tipo de Cambio</Label>
                  <div className="flex items-center gap-2">
                    <span className="text-sm text-[#64748B]">1 {formData.moneda_base} =</span>
                    <Input
                      type="number"
                      step="0.0001"
                      value={formData.tipo_cambio}
                      onChange={(e) => setFormData({...formData, tipo_cambio: e.target.value})}
                      placeholder="0.0000"
                      required
                      className="flex-1"
                    />
                    <span className="text-sm text-[#64748B]">{formData.moneda_cotizada}</span>
                  </div>
                </div>

                <div className="space-y-2">
                  <Label>Fecha de Vigencia</Label>
                  <Input
                    type="datetime-local"
                    value={formData.fecha_vigencia}
                    onChange={(e) => setFormData({...formData, fecha_vigencia: e.target.value})}
                    required
                  />
                </div>

                <DialogFooter>
                  <Button type="submit">Registrar</Button>
                </DialogFooter>
              </form>
            </DialogContent>
          </Dialog>
        </div>
      </div>

      {/* Current Rates Cards */}
      <div className="grid grid-cols-1 md:grid-cols-4 gap-4">
        <Card className="border-[#0EA5E9] bg-blue-50">
          <CardHeader className="pb-2">
            <CardTitle className="text-sm font-medium text-[#0369A1] flex items-center gap-2">
              <DollarSign size={16} />
              Moneda Base
            </CardTitle>
          </CardHeader>
          <CardContent>
            <div className="text-2xl font-bold text-[#0369A1]">
              {latestRates.moneda_base || 'MXN'}
            </div>
          </CardContent>
        </Card>

        {Object.entries(latestRates.rates || {}).filter(([k]) => k !== latestRates.moneda_base).slice(0, 3).map(([currency, rate]) => (
          <Card key={currency} className="border-[#E2E8F0]">
            <CardHeader className="pb-2">
              <CardTitle className="text-sm font-medium text-[#64748B] flex items-center gap-2">
                <TrendingUp size={16} />
                {currency}
              </CardTitle>
            </CardHeader>
            <CardContent>
              <div className="text-2xl font-bold mono text-[#0F172A]">
                {typeof rate === 'number' ? rate.toFixed(4) : rate}
              </div>
              <div className="text-xs text-[#94A3B8]">
                1 {latestRates.moneda_base} = {rate} {currency}
              </div>
            </CardContent>
          </Card>
        ))}
      </div>

      {/* Tabs for different views */}
      <Tabs value={activeTab} onValueChange={setActiveTab} className="w-full">
        <TabsList className="grid w-full grid-cols-2 mb-4">
          <TabsTrigger value="latest" className="gap-2">
            <TrendingUp size={16} />
            Últimos Registros
          </TabsTrigger>
          <TabsTrigger value="year" className="gap-2">
            <Calendar size={16} />
            Vista Anual
          </TabsTrigger>
        </TabsList>

        <TabsContent value="latest">
          {/* Rates History Table */}
          <Card className="border-[#E2E8F0]">
            <CardHeader>
              <CardTitle>Historial de Tipos de Cambio</CardTitle>
              <CardDescription>{rates.length} registros de tipos de cambio (Banxico + OpenExchange + Manual)</CardDescription>
            </CardHeader>
            <CardContent>
              <Table className="data-table">
                <TableHeader>
              <TableRow>
                <TableHead>Fecha Vigencia</TableHead>
                <TableHead>Moneda</TableHead>
                <TableHead>Tipo de Cambio (MXN)</TableHead>
                <TableHead>Fuente</TableHead>
                <TableHead className="text-center">Acciones</TableHead>
              </TableRow>
            </TableHeader>
            <TableBody>
              {rates.length === 0 ? (
                <TableRow>
                  <TableCell colSpan={5} className="text-center text-[#94A3B8] py-8">
                    No hay tipos de cambio registrados. Sincroniza con Banxico o agrega uno manualmente.
                  </TableCell>
                </TableRow>
              ) : (
                rates.map((rate) => (
                  <TableRow key={rate.id}>
                    <TableCell className="mono">{format(new Date(rate.fecha_vigencia), 'dd/MM/yyyy HH:mm')}</TableCell>
                    <TableCell>
                      <span className={`px-2 py-1 text-xs rounded font-medium ${
                        rate.moneda_cotizada === 'USD' ? 'bg-green-100 text-green-800' :
                        rate.moneda_cotizada === 'EUR' ? 'bg-purple-100 text-purple-800' :
                        rate.moneda_cotizada === 'GBP' ? 'bg-blue-100 text-blue-800' :
                        'bg-gray-100 text-gray-800'
                      }`}>
                        {rate.moneda_cotizada}
                      </span>
                    </TableCell>
                    <TableCell className="mono font-semibold">
                      ${rate.tipo_cambio?.toFixed(4) || '0.0000'}
                    </TableCell>
                    <TableCell>
                      <span className={`px-2 py-1 text-xs rounded ${
                        rate.fuente === 'banxico' ? 'bg-blue-100 text-blue-800' :
                        rate.fuente === 'openexchange' ? 'bg-orange-100 text-orange-800' :
                        'bg-gray-100 text-gray-600'
                      }`}>
                        {rate.fuente || 'manual'} {rate.auto_sync && '🔄'}
                      </span>
                    </TableCell>
                    <TableCell className="text-center">
                      <Button
                        variant="ghost"
                        size="sm"
                        className="text-red-500 hover:text-red-700 hover:bg-red-50"
                        onClick={() => handleDelete(rate.id)}
                      >
                        <Trash2 size={16} />
                      </Button>
                    </TableCell>
                  </TableRow>
                ))
              )}
            </TableBody>
          </Table>
        </CardContent>
      </Card>
        </TabsContent>

        <TabsContent value="year">
          {/* Year selector */}
          <div className="flex items-center gap-4 mb-4">
            <Button 
              variant="outline" 
              size="sm" 
              onClick={() => setSelectedYear(selectedYear - 1)}
            >
              <ChevronLeft size={16} />
            </Button>
            <span className="text-xl font-bold">{selectedYear}</span>
            <Button 
              variant="outline" 
              size="sm" 
              onClick={() => setSelectedYear(selectedYear + 1)}
              disabled={selectedYear >= new Date().getFullYear()}
            >
              <ChevronRight size={16} />
            </Button>
          </div>

          {loadingYear ? (
            <Card className="border-[#E2E8F0]">
              <CardContent className="py-8 text-center text-gray-500">
                Cargando tipos de cambio del año...
              </CardContent>
            </Card>
          ) : yearData ? (
            <div className="space-y-4">
              {/* Year Summary */}
              <Card className="border-[#E2E8F0]">
                <CardHeader>
                  <CardTitle>Resumen del Año {selectedYear}</CardTitle>
                  <CardDescription>
                    {yearData.total_rates} registros | {yearData.currencies?.length || 0} monedas
                  </CardDescription>
                </CardHeader>
              </Card>

              {/* Monthly Averages Table */}
              {yearData.currencies?.length > 0 && (
                <Card className="border-[#E2E8F0]">
                  <CardHeader>
                    <CardTitle>Promedios Mensuales</CardTitle>
                    <CardDescription>Tipo de cambio promedio por mes (respecto a MXN)</CardDescription>
                  </CardHeader>
                  <CardContent>
                    <div className="overflow-x-auto">
                      <Table className="data-table">
                        <TableHeader>
                          <TableRow>
                            <TableHead>Moneda</TableHead>
                            {MONTH_NAMES.map((m, i) => (
                              <TableHead key={i} className="text-center">{m}</TableHead>
                            ))}
                          </TableRow>
                        </TableHeader>
                        <TableBody>
                          {yearData.currencies?.filter(c => c !== 'MXN').map(currency => (
                            <TableRow key={currency}>
                              <TableCell className="font-semibold">
                                <span className="px-2 py-1 text-xs rounded bg-blue-100 text-blue-800">
                                  {currency}
                                </span>
                              </TableCell>
                              {MONTH_NAMES.map((_, i) => {
                                const avg = yearData.monthly_averages?.[currency]?.[i + 1];
                                return (
                                  <TableCell key={i} className="text-center mono">
                                    {avg ? avg.toFixed(2) : '-'}
                                  </TableCell>
                                );
                              })}
                            </TableRow>
                          ))}
                        </TableBody>
                      </Table>
                    </div>
                  </CardContent>
                </Card>
              )}

              {/* Detailed rates by currency */}
              {yearData.currencies?.filter(c => c !== 'MXN').map(currency => (
                <Card key={currency} className="border-[#E2E8F0]">
                  <CardHeader>
                    <CardTitle className="flex items-center gap-2">
                      <span className="px-2 py-1 text-sm rounded bg-green-100 text-green-800">
                        {currency}
                      </span>
                      Historial {selectedYear}
                    </CardTitle>
                    <CardDescription>
                      {yearData.by_currency?.[currency]?.length || 0} registros
                    </CardDescription>
                  </CardHeader>
                  <CardContent>
                    <div className="max-h-64 overflow-y-auto">
                      <Table className="data-table">
                        <TableHeader>
                          <TableRow>
                            <TableHead>Fecha</TableHead>
                            <TableHead>Tasa</TableHead>
                            <TableHead>Fuente</TableHead>
                          </TableRow>
                        </TableHeader>
                        <TableBody>
                          {yearData.by_currency?.[currency]?.slice(-50).reverse().map((rate, idx) => (
                            <TableRow key={idx}>
                              <TableCell>
                                {rate.fecha ? format(new Date(rate.fecha), 'dd MMM yyyy', { locale: es }) : '-'}
                              </TableCell>
                              <TableCell className="mono font-semibold">
                                {rate.tasa?.toFixed(4)}
                              </TableCell>
                              <TableCell>
                                <span className={`px-2 py-1 text-xs rounded ${
                                  rate.fuente === 'banxico' ? 'bg-blue-100 text-blue-800' :
                                  rate.fuente === 'openexchange' ? 'bg-orange-100 text-orange-800' :
                                  'bg-gray-100 text-gray-600'
                                }`}>
                                  {rate.fuente || 'manual'}
                                </span>
                              </TableCell>
                            </TableRow>
                          ))}
                        </TableBody>
                      </Table>
                    </div>
                  </CardContent>
                </Card>
              ))}

              {yearData.currencies?.length === 0 && (
                <Card className="border-[#E2E8F0]">
                  <CardContent className="py-8 text-center text-gray-500">
                    No hay tipos de cambio registrados para {selectedYear}
                  </CardContent>
                </Card>
              )}
            </div>
          ) : (
            <Card className="border-[#E2E8F0]">
              <CardContent className="py-8 text-center text-gray-500">
                No hay datos disponibles
              </CardContent>
            </Card>
          )}
        </TabsContent>
      </Tabs>

      {/* Info Card */}
      <Card className="border-[#F59E0B] bg-[#FFFBEB]">
        <CardHeader>
          <CardTitle className="text-[#92400E] flex items-center gap-2">
            <DollarSign size={20} />
            Información sobre Tipos de Cambio
          </CardTitle>
        </CardHeader>
        <CardContent className="text-[#92400E] text-sm space-y-2">
          <p>• Los tipos de cambio se utilizan para convertir CFDIs y transacciones a la moneda base de la empresa.</p>
          <p>• Registra el tipo de cambio del día para mantener tus reportes actualizados.</p>
          <p>• Se recomienda registrar el tipo de cambio publicado por el DOF o Banxico.</p>
        </CardContent>
      </Card>
    </div>
  );
};

export default FXRatesModule;
