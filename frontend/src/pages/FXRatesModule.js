import { useState, useEffect } from 'react';
import api from '@/api/axios';
import { Button } from '@/components/ui/button';
import { Input } from '@/components/ui/input';
import { Label } from '@/components/ui/label';
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from '@/components/ui/select';
import { Dialog, DialogContent, DialogDescription, DialogFooter, DialogHeader, DialogTitle, DialogTrigger } from '@/components/ui/dialog';
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card';
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from '@/components/ui/table';
import { toast } from 'sonner';
import { Plus, Trash2, RefreshCw, DollarSign, TrendingUp } from 'lucide-react';
import { format } from 'date-fns';

const CURRENCIES = [
  { code: 'MXN', name: 'Peso Mexicano', symbol: '$' },
  { code: 'USD', name: 'Dólar Estadounidense', symbol: '$' },
  { code: 'EUR', name: 'Euro', symbol: '€' },
  { code: 'GBP', name: 'Libra Esterlina', symbol: '£' },
  { code: 'CAD', name: 'Dólar Canadiense', symbol: '$' },
  { code: 'JPY', name: 'Yen Japonés', symbol: '¥' },
];

const FXRatesModule = () => {
  const [rates, setRates] = useState([]);
  const [latestRates, setLatestRates] = useState({});
  const [loading, setLoading] = useState(true);
  const [dialogOpen, setDialogOpen] = useState(false);
  const [formData, setFormData] = useState({
    moneda_base: 'MXN',
    moneda_cotizada: 'USD',
    tipo_cambio: '',
    fecha_vigencia: format(new Date(), "yyyy-MM-dd'T'HH:mm")
  });

  useEffect(() => {
    loadData();
  }, []);

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
          <Button variant="outline" onClick={loadData} className="gap-2">
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

      {/* Rates History Table */}
      <Card className="border-[#E2E8F0]">
        <CardHeader>
          <CardTitle>Historial de Tipos de Cambio</CardTitle>
          <CardDescription>{rates.length} registros de tipos de cambio</CardDescription>
        </CardHeader>
        <CardContent>
          <Table className="data-table">
            <TableHeader>
              <TableRow>
                <TableHead>Fecha Vigencia</TableHead>
                <TableHead>Moneda Base</TableHead>
                <TableHead>Moneda Cotizada</TableHead>
                <TableHead>Tipo de Cambio</TableHead>
                <TableHead>Equivalencia</TableHead>
                <TableHead className="text-center">Acciones</TableHead>
              </TableRow>
            </TableHeader>
            <TableBody>
              {rates.length === 0 ? (
                <TableRow>
                  <TableCell colSpan={6} className="text-center text-[#94A3B8] py-8">
                    No hay tipos de cambio registrados. Agrega el primero.
                  </TableCell>
                </TableRow>
              ) : (
                rates.map((rate) => (
                  <TableRow key={rate.id}>
                    <TableCell className="mono">{format(new Date(rate.fecha_vigencia), 'dd/MM/yyyy HH:mm')}</TableCell>
                    <TableCell>
                      <span className="px-2 py-1 bg-blue-100 text-blue-800 text-xs rounded font-medium">
                        {rate.moneda_base}
                      </span>
                    </TableCell>
                    <TableCell>
                      <span className="px-2 py-1 bg-green-100 text-green-800 text-xs rounded font-medium">
                        {rate.moneda_cotizada}
                      </span>
                    </TableCell>
                    <TableCell className="mono font-semibold">{rate.tipo_cambio.toFixed(4)}</TableCell>
                    <TableCell className="text-sm text-[#64748B]">
                      1 {rate.moneda_base} = {rate.tipo_cambio.toFixed(4)} {rate.moneda_cotizada}
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
