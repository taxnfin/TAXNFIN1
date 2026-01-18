import { useState, useEffect } from 'react';
import api from '@/api/axios';
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card';
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from '@/components/ui/table';
import { toast } from 'sonner';
import { format } from 'date-fns';

const Reports = () => {
  const [cashflowWeeks, setCashflowWeeks] = useState([]);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    loadReports();
  }, []);

  const loadReports = async () => {
    try {
      const response = await api.get('/cashflow/weeks');
      setCashflowWeeks(response.data);
    } catch (error) {
      toast.error('Error cargando reportes');
    } finally {
      setLoading(false);
    }
  };

  if (loading) return <div className="p-8">Cargando...</div>;

  return (
    <div className="p-8 space-y-6" data-testid="reports-page">
      <div>
        <h1 className="text-4xl font-bold text-[#0F172A] mb-2" style={{fontFamily: 'Manrope'}}>Reportes</h1>
        <p className="text-[#64748B]">Análisis y reportes financieros</p>
      </div>

      <Card className="border-[#E2E8F0]">
        <CardHeader>
          <CardTitle>Flujo de Efectivo - 13 Semanas Rolling</CardTitle>
          <CardDescription>Vista detallada del flujo proyectado vs real</CardDescription>
        </CardHeader>
        <CardContent>
          <Table className="data-table">
            <TableHeader>
              <TableRow>
                <TableHead>Semana</TableHead>
                <TableHead>Período</TableHead>
                <TableHead>Saldo Inicial</TableHead>
                <TableHead>Ingresos Reales</TableHead>
                <TableHead>Egresos Reales</TableHead>
                <TableHead>Ingresos Proy.</TableHead>
                <TableHead>Egresos Proy.</TableHead>
                <TableHead>Saldo Final Real</TableHead>
                <TableHead>Saldo Final Proy.</TableHead>
              </TableRow>
            </TableHeader>
            <TableBody>
              {cashflowWeeks.map((week) => (
                <TableRow key={week.id} data-testid={`cashflow-week-${week.numero_semana}`}>
                  <TableCell className="mono font-semibold">S{week.numero_semana}</TableCell>
                  <TableCell className="text-sm">
                    {format(new Date(week.fecha_inicio), 'dd/MM')} - {format(new Date(week.fecha_fin), 'dd/MM')}
                  </TableCell>
                  <TableCell className="mono">${week.saldo_inicial.toLocaleString('es-MX', {minimumFractionDigits: 2})}</TableCell>
                  <TableCell className="mono text-[#10B981] font-semibold">${week.total_ingresos_reales.toLocaleString('es-MX', {minimumFractionDigits: 2})}</TableCell>
                  <TableCell className="mono text-[#EF4444] font-semibold">${week.total_egresos_reales.toLocaleString('es-MX', {minimumFractionDigits: 2})}</TableCell>
                  <TableCell className="mono text-[#64748B]">${week.total_ingresos_proyectados.toLocaleString('es-MX', {minimumFractionDigits: 2})}</TableCell>
                  <TableCell className="mono text-[#64748B]">${week.total_egresos_proyectados.toLocaleString('es-MX', {minimumFractionDigits: 2})}</TableCell>
                  <TableCell className="mono font-bold">${week.saldo_final_real.toLocaleString('es-MX', {minimumFractionDigits: 2})}</TableCell>
                  <TableCell className="mono text-[#94A3B8]">${week.saldo_final_proyectado.toLocaleString('es-MX', {minimumFractionDigits: 2})}</TableCell>
                </TableRow>
              ))}
            </TableBody>
          </Table>
        </CardContent>
      </Card>

      <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
        <Card className="border-[#E2E8F0]">
          <CardHeader>
            <CardTitle>Resumen de Variaciones</CardTitle>
            <CardDescription>Comparativo Real vs Proyectado</CardDescription>
          </CardHeader>
          <CardContent>
            <div className="space-y-3">
              {cashflowWeeks.slice(0, 5).map((week) => {
                const variacion = week.saldo_final_real - week.saldo_final_proyectado;
                return (
                  <div key={week.id} className="flex justify-between items-center p-3 bg-[#F8FAFC] rounded">
                    <div>
                      <p className="text-sm font-semibold">Semana {week.numero_semana}</p>
                      <p className="text-xs text-[#64748B]">
                        {format(new Date(week.fecha_inicio), 'dd/MM')} - {format(new Date(week.fecha_fin), 'dd/MM')}
                      </p>
                    </div>
                    <div className="text-right">
                      <p className={`mono font-bold ${variacion >= 0 ? 'text-[#10B981]' : 'text-[#EF4444]'}`}>
                        {variacion >= 0 ? '+' : ''}${variacion.toLocaleString('es-MX', {minimumFractionDigits: 2})}
                      </p>
                      <p className="text-xs text-[#94A3B8]">variación</p>
                    </div>
                  </div>
                );
              })}
            </div>
          </CardContent>
        </Card>

        <Card className="border-[#E2E8F0]">
          <CardHeader>
            <CardTitle>Indicadores Clave</CardTitle>
            <CardDescription>Métricas de desempeño</CardDescription>
          </CardHeader>
          <CardContent>
            <div className="space-y-4">
              <div className="p-4 bg-[#F8FAFC] rounded">
                <p className="text-sm text-[#64748B]">Total Ingresos (13 semanas)</p>
                <p className="text-2xl font-bold mono text-[#10B981]">
                  ${cashflowWeeks.reduce((sum, w) => sum + w.total_ingresos_reales + w.total_ingresos_proyectados, 0).toLocaleString('es-MX')}
                </p>
              </div>
              <div className="p-4 bg-[#F8FAFC] rounded">
                <p className="text-sm text-[#64748B]">Total Egresos (13 semanas)</p>
                <p className="text-2xl font-bold mono text-[#EF4444]">
                  ${cashflowWeeks.reduce((sum, w) => sum + w.total_egresos_reales + w.total_egresos_proyectados, 0).toLocaleString('es-MX')}
                </p>
              </div>
              <div className="p-4 bg-[#F8FAFC] rounded">
                <p className="text-sm text-[#64748B]">Flujo Neto (13 semanas)</p>
                <p className="text-2xl font-bold mono text-[#0F172A]">
                  ${cashflowWeeks.reduce((sum, w) => {
                    const flujo = (w.total_ingresos_reales + w.total_ingresos_proyectados) - (w.total_egresos_reales + w.total_egresos_proyectados);
                    return sum + flujo;
                  }, 0).toLocaleString('es-MX')}
                </p>
              </div>
            </div>
          </CardContent>
        </Card>
      </div>
    </div>
  );
};

export default Reports;
