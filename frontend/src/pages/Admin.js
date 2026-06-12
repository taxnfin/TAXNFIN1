import { useState, useEffect } from 'react';
import api from '@/api/axios';
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card';
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from '@/components/ui/table';
import { Badge } from '@/components/ui/badge';
import { Button } from '@/components/ui/button';
import { Download, FileText } from 'lucide-react';
import { toast } from 'sonner';
import { format } from 'date-fns';

const Admin = () => {
  const [auditLogs, setAuditLogs] = useState([]);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    loadAuditLogs();
  }, []);

  const loadAuditLogs = async () => {
    try {
      const response = await api.get('/audit-logs?limit=100');
      setAuditLogs(response.data);
    } catch (error) {
      if (error.response?.status === 403) {
        toast.error('No tienes permisos para ver los logs de auditoría');
      } else {
        toast.error('Error cargando logs');
      }
    } finally {
      setLoading(false);
    }
  };

  if (loading) return <div className="p-8">Cargando...</div>;

  return (
    <div className="p-8 space-y-6" data-testid="admin-page">
      <div>
        <h1 className="text-4xl font-bold text-[#0F172A] mb-2" style={{fontFamily: 'Manrope'}}>Administración</h1>
        <p className="text-[#64748B]">Auditoría y administración del sistema</p>
      </div>

      <Card className="border-[#E2E8F0]">
        <CardHeader>
          <CardTitle>Logs de Auditoría</CardTitle>
          <CardDescription>{auditLogs.length} eventos registrados</CardDescription>
        </CardHeader>
        <CardContent>
          <Table className="data-table">
            <TableHeader>
              <TableRow>
                <TableHead>Fecha/Hora</TableHead>
                <TableHead>Usuario</TableHead>
                <TableHead>Entidad</TableHead>
                <TableHead>Acción</TableHead>
                <TableHead>ID Entidad</TableHead>
              </TableRow>
            </TableHeader>
            <TableBody>
              {auditLogs.map((log) => (
                <TableRow key={log.id} data-testid={`audit-log-${log.id}`}>
                  <TableCell className="mono text-sm">{format(new Date(log.timestamp), 'dd/MM/yyyy HH:mm:ss')}</TableCell>
                  <TableCell className="text-sm">{log.user_id.substring(0, 8)}...</TableCell>
                  <TableCell>
                    <span className="text-xs px-2 py-1 bg-[#F1F5F9] rounded">{log.entidad}</span>
                  </TableCell>
                  <TableCell>
                    <span className={`text-xs px-2 py-1 rounded ${
                      log.accion === 'CREATE' ? 'bg-green-100 text-green-800' :
                      log.accion === 'UPDATE' ? 'bg-blue-100 text-blue-800' :
                      log.accion === 'DELETE' ? 'bg-red-100 text-red-800' :
                      'bg-gray-100 text-gray-800'
                    }`}>
                      {log.accion}
                    </span>
                  </TableCell>
                  <TableCell className="mono text-xs text-[#64748B]">{log.entity_id.substring(0, 13)}...</TableCell>
                </TableRow>
              ))}
            </TableBody>
          </Table>
        </CardContent>
      </Card>

      <Card className="border-[#E2E8F0] bg-[#F8FAFC]">
        <CardHeader>
          <CardTitle>Información del Sistema</CardTitle>
        </CardHeader>
        <CardContent>
          <div className="grid grid-cols-2 gap-4 text-sm">
            <div>
              <p className="text-[#64748B]">Versión del Sistema</p>
              <p className="font-semibold mono">1.0.0</p>
            </div>
            <div>
              <p className="text-[#64748B]">Base de Datos</p>
              <p className="font-semibold">MongoDB</p>
            </div>
            <div>
              <p className="text-[#64748B]">Backend</p>
              <p className="font-semibold">FastAPI + Python</p>
            </div>
            <div>
              <p className="text-[#64748B]">Frontend</p>
              <p className="font-semibold">React + Tailwind CSS</p>
            </div>
          </div>
        </CardContent>
      </Card>

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
            <Button onClick={() => api.get('/export/coi', { responseType: 'blob' }).then(res => {
              const link = document.createElement('a');
              link.href = window.URL.createObjectURL(new Blob([res.data]));
              link.download = `coi_${Date.now()}.csv`;
              link.click();
              toast.success('COI exportado');
            })} variant="outline" className="gap-2" data-testid="export-coi">
              <FileText size={16} />COI
            </Button>
            <Button onClick={() => api.get('/export/xml-fiscal', { responseType: 'blob' }).then(res => {
              const link = document.createElement('a');
              link.href = window.URL.createObjectURL(new Blob([res.data]));
              link.download = `balanza_sat_${Date.now()}.xml`;
              link.click();
              toast.success('XML Fiscal exportado');
            })} variant="outline" className="gap-2">
              <FileText size={16} />XML Fiscal
            </Button>
            <Button onClick={() => api.get('/export/alegra', { responseType: 'blob' }).then(res => {
              const link = document.createElement('a');
              link.href = window.URL.createObjectURL(new Blob([res.data]));
              link.download = `alegra_${Date.now()}.json`;
              link.click();
              toast.success('Alegra exportado');
            })} variant="outline" className="gap-2" data-testid="export-alegra">
              <FileText size={16} />Alegra
            </Button>
            <Button onClick={() => api.get('/export/cashflow?formato=excel', { responseType: 'blob' }).then(res => {
              const link = document.createElement('a');
              link.href = window.URL.createObjectURL(new Blob([res.data]));
              link.download = `cashflow_${Date.now()}.csv`;
              link.click();
              toast.success('Cashflow exportado');
            })} variant="outline" className="gap-2">
              <FileText size={16} />Cashflow
            </Button>
          </div>
        </CardContent>
      </Card>

      <Card className="border-[#3B82F6]">
        <CardHeader>
          <CardTitle>Integraciones Bancarias</CardTitle>
          <CardDescription>Conexión directa vía API con bancos mexicanos — en desarrollo</CardDescription>
        </CardHeader>
        <CardContent>
          <div className="grid grid-cols-2 md:grid-cols-5 gap-3 text-sm">
            {['BBVA', 'Santander', 'Banorte', 'Bajío', 'Amex'].map(bank => (
              <div key={bank} className="p-3 bg-[#F8FAFC] border border-gray-200 rounded text-center">
                <p className="font-semibold text-[#64748B] mb-2">{bank}</p>
                <Badge variant="secondary" className="text-xs text-gray-500">Próximamente</Badge>
              </div>
            ))}
          </div>
        </CardContent>
      </Card>
    </div>
  );
};

export default Admin;
