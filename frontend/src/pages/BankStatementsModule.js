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
import { 
  Plus, CheckCircle, Building2, Trash2, DollarSign, 
  Upload, Download, Link2, RefreshCw, FileSpreadsheet,
  ArrowUpCircle, ArrowDownCircle, Search, Filter, X,
  AlertCircle, Clock, Check
} from 'lucide-react';
import { format } from 'date-fns';
import { es } from 'date-fns/locale';
import * as XLSX from 'xlsx';

const BankStatementsModule = () => {
  const [bankTransactions, setBankTransactions] = useState([]);
  const [bankAccounts, setBankAccounts] = useState([]);
  const [cfdis, setCfdis] = useState([]);
  const [loading, setLoading] = useState(true);
  const [dialogOpen, setDialogOpen] = useState(false);
  const [connectDialogOpen, setConnectDialogOpen] = useState(false);
  const [reconcileDialogOpen, setReconcileDialogOpen] = useState(false);
  const [selectedTransaction, setSelectedTransaction] = useState(null);
  const [filterAccount, setFilterAccount] = useState('all');
  const [filterStatus, setFilterStatus] = useState('all');
  const [searchTerm, setSearchTerm] = useState('');

  const [formData, setFormData] = useState({
    bank_account_id: '',
    fecha_movimiento: format(new Date(), "yyyy-MM-dd'T'HH:mm"),
    fecha_valor: format(new Date(), "yyyy-MM-dd'T'HH:mm"),
    descripcion: '',
    referencia: '',
    monto: '',
    tipo_movimiento: 'credito',
    saldo: ''
  });

  useEffect(() => {
    loadData();
  }, []);

  const loadData = async () => {
    try {
      const [txnRes, accountsRes, cfdisRes] = await Promise.all([
        api.get('/bank-transactions?limit=500'),
        api.get('/bank-accounts'),
        api.get('/cfdi?limit=500')
      ]);
      setBankTransactions(txnRes.data);
      setBankAccounts(accountsRes.data);
      setCfdis(cfdisRes.data);
    } catch (error) {
      toast.error('Error cargando datos');
    } finally {
      setLoading(false);
    }
  };

  const handleSubmit = async (e) => {
    e.preventDefault();
    if (!formData.bank_account_id) {
      toast.error('Selecciona una cuenta bancaria');
      return;
    }
    try {
      await api.post('/bank-transactions', {
        ...formData,
        monto: parseFloat(formData.monto),
        saldo: parseFloat(formData.saldo) || 0
      });
      toast.success('Movimiento agregado correctamente');
      setDialogOpen(false);
      resetForm();
      loadData();
    } catch (error) {
      toast.error(error.response?.data?.detail || 'Error guardando movimiento');
    }
  };

  const resetForm = () => {
    setFormData({
      bank_account_id: '',
      fecha_movimiento: format(new Date(), "yyyy-MM-dd'T'HH:mm"),
      fecha_valor: format(new Date(), "yyyy-MM-dd'T'HH:mm"),
      descripcion: '',
      referencia: '',
      monto: '',
      tipo_movimiento: 'credito',
      saldo: ''
    });
  };

  const handleDelete = async (id) => {
    if (!confirm('¿Eliminar este movimiento?')) return;
    try {
      await api.delete(`/bank-transactions/${id}`);
      toast.success('Movimiento eliminado');
      loadData();
    } catch (error) {
      toast.error('Error eliminando movimiento');
    }
  };

  const handleReconcile = async (cfdiId) => {
    if (!selectedTransaction) return;
    try {
      await api.post('/reconciliations', {
        bank_transaction_id: selectedTransaction.id,
        cfdi_id: cfdiId,
        metodo_conciliacion: 'manual',
        porcentaje_match: 100
      });
      toast.success('Movimiento conciliado con CFDI');
      setReconcileDialogOpen(false);
      setSelectedTransaction(null);
      loadData();
    } catch (error) {
      toast.error(error.response?.data?.detail || 'Error al conciliar');
    }
  };

  const exportToExcel = () => {
    if (filteredTransactions.length === 0) {
      toast.error('No hay movimientos para exportar');
      return;
    }

    const data = filteredTransactions.map(txn => {
      const account = bankAccounts.find(a => a.id === txn.bank_account_id);
      return {
        'Fecha': format(new Date(txn.fecha_movimiento), 'dd/MM/yyyy'),
        'Cuenta': account?.nombre || 'N/A',
        'Banco': account?.banco || 'N/A',
        'Descripción': txn.descripcion,
        'Referencia': txn.referencia || '',
        'Tipo': txn.tipo_movimiento === 'credito' ? 'Depósito' : 'Retiro',
        'Monto': txn.monto,
        'Saldo': txn.saldo,
        'Moneda': txn.moneda || account?.moneda || 'MXN',
        'Conciliado': txn.conciliado ? 'Sí' : 'No'
      };
    });

    const wb = XLSX.utils.book_new();
    const ws = XLSX.utils.json_to_sheet(data);
    XLSX.utils.book_append_sheet(wb, ws, 'Movimientos');
    XLSX.writeFile(wb, `Estados_Cuenta_${format(new Date(), 'yyyy-MM-dd')}.xlsx`);
    toast.success('Exportado a Excel');
  };

  const handleImportExcel = async (e) => {
    const file = e.target.files?.[0];
    if (!file) return;

    try {
      const reader = new FileReader();
      reader.onload = async (event) => {
        const data = new Uint8Array(event.target.result);
        const workbook = XLSX.read(data, { type: 'array' });
        const sheetName = workbook.SheetNames[0];
        const worksheet = workbook.Sheets[sheetName];
        const jsonData = XLSX.utils.sheet_to_json(worksheet);

        let imported = 0;
        for (const row of jsonData) {
          try {
            // Map Excel columns to API format
            const txnData = {
              bank_account_id: bankAccounts[0]?.id, // Default to first account
              fecha_movimiento: new Date().toISOString(),
              fecha_valor: new Date().toISOString(),
              descripcion: row['Descripción'] || row['Concepto'] || row['descripcion'] || 'Movimiento importado',
              referencia: row['Referencia'] || row['referencia'] || '',
              monto: parseFloat(row['Monto'] || row['monto'] || row['Cargo'] || row['Abono'] || 0),
              tipo_movimiento: (row['Tipo'] || '').toLowerCase().includes('dep') ? 'credito' : 'debito',
              saldo: parseFloat(row['Saldo'] || row['saldo'] || 0),
              fuente: 'excel_import'
            };

            if (txnData.monto !== 0) {
              await api.post('/bank-transactions', txnData);
              imported++;
            }
          } catch (err) {
            console.error('Error importing row:', err);
          }
        }

        toast.success(`${imported} movimientos importados`);
        loadData();
      };
      reader.readAsArrayBuffer(file);
    } catch (error) {
      toast.error('Error importando archivo');
    }
    e.target.value = '';
  };

  // Filter transactions
  const filteredTransactions = bankTransactions.filter(txn => {
    if (filterAccount !== 'all' && txn.bank_account_id !== filterAccount) return false;
    if (filterStatus === 'conciliado' && !txn.conciliado) return false;
    if (filterStatus === 'pendiente' && txn.conciliado) return false;
    if (searchTerm && !txn.descripcion?.toLowerCase().includes(searchTerm.toLowerCase()) &&
        !txn.referencia?.toLowerCase().includes(searchTerm.toLowerCase())) return false;
    return true;
  });

  // Stats
  const totalDepositos = filteredTransactions
    .filter(t => t.tipo_movimiento === 'credito')
    .reduce((sum, t) => sum + t.monto, 0);
  const totalRetiros = filteredTransactions
    .filter(t => t.tipo_movimiento === 'debito')
    .reduce((sum, t) => sum + t.monto, 0);
  const pendientesConciliar = filteredTransactions.filter(t => !t.conciliado).length;

  if (loading) return <div className="p-8">Cargando...</div>;

  return (
    <div className="p-8 space-y-6" data-testid="bank-statements-page">
      {/* Header */}
      <div className="flex justify-between items-start">
        <div>
          <h1 className="text-4xl font-bold text-[#0F172A] mb-2" style={{fontFamily: 'Manrope'}}>
            Estados de Cuenta
          </h1>
          <p className="text-[#64748B]">Gestión de movimientos bancarios y conciliación</p>
        </div>
        <div className="flex gap-2">
          <Button variant="outline" onClick={() => setConnectDialogOpen(true)} className="gap-2" data-testid="connect-bank-btn">
            <Link2 size={16} />
            Conectar Banco
          </Button>
          <label className="cursor-pointer">
            <input type="file" accept=".xlsx,.xls,.csv" onChange={handleImportExcel} className="hidden" />
            <Button variant="outline" className="gap-2" asChild>
              <span>
                <Upload size={16} />
                Importar Excel
              </span>
            </Button>
          </label>
          <Button variant="outline" onClick={exportToExcel} className="gap-2" data-testid="export-statements-btn">
            <Download size={16} />
            Exportar
          </Button>
          <Dialog open={dialogOpen} onOpenChange={setDialogOpen}>
            <DialogTrigger asChild>
              <Button className="gap-2 bg-[#0F172A]" data-testid="add-movement-btn">
                <Plus size={16} />
                Agregar Movimiento
              </Button>
            </DialogTrigger>
            <DialogContent className="max-w-lg">
              <DialogHeader>
                <DialogTitle>Nuevo Movimiento Bancario</DialogTitle>
                <DialogDescription>Captura un movimiento del estado de cuenta</DialogDescription>
              </DialogHeader>
              <form onSubmit={handleSubmit} className="space-y-4">
                <div className="space-y-2">
                  <Label>Cuenta Bancaria *</Label>
                  <Select value={formData.bank_account_id} onValueChange={(v) => setFormData({...formData, bank_account_id: v})}>
                    <SelectTrigger>
                      <SelectValue placeholder="Seleccionar cuenta..." />
                    </SelectTrigger>
                    <SelectContent>
                      {bankAccounts.map(acc => (
                        <SelectItem key={acc.id} value={acc.id}>
                          <span className="flex items-center gap-2">
                            <Building2 size={14} />
                            {acc.banco} - {acc.nombre} ({acc.moneda})
                          </span>
                        </SelectItem>
                      ))}
                    </SelectContent>
                  </Select>
                </div>
                
                <div className="grid grid-cols-2 gap-4">
                  <div className="space-y-2">
                    <Label>Fecha Movimiento *</Label>
                    <Input 
                      type="datetime-local" 
                      value={formData.fecha_movimiento}
                      onChange={(e) => setFormData({...formData, fecha_movimiento: e.target.value})}
                      required
                    />
                  </div>
                  <div className="space-y-2">
                    <Label>Fecha Valor</Label>
                    <Input 
                      type="datetime-local" 
                      value={formData.fecha_valor}
                      onChange={(e) => setFormData({...formData, fecha_valor: e.target.value})}
                    />
                  </div>
                </div>

                <div className="space-y-2">
                  <Label>Descripción / Concepto *</Label>
                  <Input 
                    value={formData.descripcion}
                    onChange={(e) => setFormData({...formData, descripcion: e.target.value})}
                    placeholder="Ej: Transferencia SPEI, Pago de nómina..."
                    required
                  />
                </div>

                <div className="space-y-2">
                  <Label>Referencia / Folio</Label>
                  <Input 
                    value={formData.referencia}
                    onChange={(e) => setFormData({...formData, referencia: e.target.value})}
                    placeholder="Número de referencia bancaria"
                  />
                </div>

                <div className="grid grid-cols-2 gap-4">
                  <div className="space-y-2">
                    <Label>Tipo de Movimiento *</Label>
                    <Select value={formData.tipo_movimiento} onValueChange={(v) => setFormData({...formData, tipo_movimiento: v})}>
                      <SelectTrigger>
                        <SelectValue />
                      </SelectTrigger>
                      <SelectContent>
                        <SelectItem value="credito">
                          <span className="flex items-center gap-2 text-green-600">
                            <ArrowUpCircle size={14} /> Depósito / Abono
                          </span>
                        </SelectItem>
                        <SelectItem value="debito">
                          <span className="flex items-center gap-2 text-red-600">
                            <ArrowDownCircle size={14} /> Retiro / Cargo
                          </span>
                        </SelectItem>
                      </SelectContent>
                    </Select>
                  </div>
                  <div className="space-y-2">
                    <Label>Monto *</Label>
                    <Input 
                      type="number" 
                      step="0.01"
                      value={formData.monto}
                      onChange={(e) => setFormData({...formData, monto: e.target.value})}
                      placeholder="0.00"
                      required
                    />
                  </div>
                </div>

                <div className="space-y-2">
                  <Label>Saldo después del movimiento</Label>
                  <Input 
                    type="number" 
                    step="0.01"
                    value={formData.saldo}
                    onChange={(e) => setFormData({...formData, saldo: e.target.value})}
                    placeholder="Saldo en el estado de cuenta"
                  />
                </div>

                <DialogFooter>
                  <Button type="button" variant="outline" onClick={() => setDialogOpen(false)}>Cancelar</Button>
                  <Button type="submit" className="bg-[#0F172A]">Guardar Movimiento</Button>
                </DialogFooter>
              </form>
            </DialogContent>
          </Dialog>
        </div>
      </div>

      {/* Summary Cards */}
      <div className="grid grid-cols-1 md:grid-cols-4 gap-4">
        <Card className="border-green-200 bg-green-50">
          <CardHeader className="pb-2">
            <CardTitle className="text-sm font-medium text-green-700 flex items-center gap-2">
              <ArrowUpCircle size={16} />
              Total Depósitos
            </CardTitle>
          </CardHeader>
          <CardContent>
            <div className="text-2xl font-bold text-green-700">
              ${totalDepositos.toLocaleString('es-MX', {minimumFractionDigits: 2})}
            </div>
          </CardContent>
        </Card>

        <Card className="border-red-200 bg-red-50">
          <CardHeader className="pb-2">
            <CardTitle className="text-sm font-medium text-red-700 flex items-center gap-2">
              <ArrowDownCircle size={16} />
              Total Retiros
            </CardTitle>
          </CardHeader>
          <CardContent>
            <div className="text-2xl font-bold text-red-700">
              ${totalRetiros.toLocaleString('es-MX', {minimumFractionDigits: 2})}
            </div>
          </CardContent>
        </Card>

        <Card className="border-blue-200 bg-blue-50">
          <CardHeader className="pb-2">
            <CardTitle className="text-sm font-medium text-blue-700 flex items-center gap-2">
              <DollarSign size={16} />
              Flujo Neto
            </CardTitle>
          </CardHeader>
          <CardContent>
            <div className={`text-2xl font-bold ${totalDepositos - totalRetiros >= 0 ? 'text-blue-700' : 'text-red-700'}`}>
              ${(totalDepositos - totalRetiros).toLocaleString('es-MX', {minimumFractionDigits: 2})}
            </div>
          </CardContent>
        </Card>

        <Card className="border-yellow-200 bg-yellow-50">
          <CardHeader className="pb-2">
            <CardTitle className="text-sm font-medium text-yellow-700 flex items-center gap-2">
              <Clock size={16} />
              Pendientes Conciliar
            </CardTitle>
          </CardHeader>
          <CardContent>
            <div className="text-2xl font-bold text-yellow-700">{pendientesConciliar}</div>
            <p className="text-xs text-yellow-600">movimientos sin conciliar</p>
          </CardContent>
        </Card>
      </div>

      {/* Filters */}
      <Card>
        <CardContent className="pt-4">
          <div className="flex flex-wrap gap-4 items-end">
            <div className="flex-1 min-w-[200px]">
              <Label className="text-xs text-gray-500">Buscar</Label>
              <div className="relative">
                <Search size={16} className="absolute left-3 top-1/2 transform -translate-y-1/2 text-gray-400" />
                <Input
                  placeholder="Buscar por descripción o referencia..."
                  value={searchTerm}
                  onChange={(e) => setSearchTerm(e.target.value)}
                  className="pl-10"
                />
              </div>
            </div>
            <div className="w-48">
              <Label className="text-xs text-gray-500">Cuenta</Label>
              <Select value={filterAccount} onValueChange={setFilterAccount}>
                <SelectTrigger>
                  <SelectValue />
                </SelectTrigger>
                <SelectContent>
                  <SelectItem value="all">Todas las cuentas</SelectItem>
                  {bankAccounts.map(acc => (
                    <SelectItem key={acc.id} value={acc.id}>
                      {acc.banco} - {acc.nombre}
                    </SelectItem>
                  ))}
                </SelectContent>
              </Select>
            </div>
            <div className="w-48">
              <Label className="text-xs text-gray-500">Estado</Label>
              <Select value={filterStatus} onValueChange={setFilterStatus}>
                <SelectTrigger>
                  <SelectValue />
                </SelectTrigger>
                <SelectContent>
                  <SelectItem value="all">Todos</SelectItem>
                  <SelectItem value="pendiente">Pendientes</SelectItem>
                  <SelectItem value="conciliado">Conciliados</SelectItem>
                </SelectContent>
              </Select>
            </div>
            {(searchTerm || filterAccount !== 'all' || filterStatus !== 'all') && (
              <Button variant="ghost" size="sm" onClick={() => {
                setSearchTerm('');
                setFilterAccount('all');
                setFilterStatus('all');
              }}>
                <X size={16} className="mr-1" /> Limpiar
              </Button>
            )}
          </div>
        </CardContent>
      </Card>

      {/* Transactions Table */}
      <Card>
        <CardHeader>
          <CardTitle>Movimientos Bancarios</CardTitle>
          <CardDescription>
            {filteredTransactions.length} movimiento{filteredTransactions.length !== 1 ? 's' : ''} encontrado{filteredTransactions.length !== 1 ? 's' : ''}
          </CardDescription>
        </CardHeader>
        <CardContent>
          {bankAccounts.length === 0 ? (
            <div className="text-center py-12 text-gray-500">
              <Building2 size={48} className="mx-auto mb-4 opacity-50" />
              <p className="font-medium">No hay cuentas bancarias</p>
              <p className="text-sm mt-2">Primero crea una cuenta bancaria en el módulo Bancario</p>
            </div>
          ) : filteredTransactions.length === 0 ? (
            <div className="text-center py-12 text-gray-500">
              <FileSpreadsheet size={48} className="mx-auto mb-4 opacity-50" />
              <p className="font-medium">No hay movimientos</p>
              <p className="text-sm mt-2">Agrega movimientos manualmente, importa desde Excel o conecta tu banco</p>
            </div>
          ) : (
            <div className="overflow-x-auto">
              <Table>
                <TableHeader>
                  <TableRow>
                    <TableHead>Fecha</TableHead>
                    <TableHead>Cuenta</TableHead>
                    <TableHead>Descripción</TableHead>
                    <TableHead>Referencia</TableHead>
                    <TableHead>Tipo</TableHead>
                    <TableHead className="text-right">Monto</TableHead>
                    <TableHead className="text-right">Saldo</TableHead>
                    <TableHead className="text-center">Estado</TableHead>
                    <TableHead className="text-center">Acciones</TableHead>
                  </TableRow>
                </TableHeader>
                <TableBody>
                  {filteredTransactions.map((txn) => {
                    const account = bankAccounts.find(a => a.id === txn.bank_account_id);
                    return (
                      <TableRow key={txn.id} className={txn.conciliado ? 'bg-green-50/50' : ''}>
                        <TableCell className="font-mono text-sm">
                          {format(new Date(txn.fecha_movimiento), 'dd/MM/yyyy', { locale: es })}
                        </TableCell>
                        <TableCell>
                          <div className="flex items-center gap-2">
                            <span className="text-xs bg-gray-100 px-2 py-1 rounded">{account?.banco}</span>
                          </div>
                        </TableCell>
                        <TableCell className="max-w-[250px]">
                          <span className="truncate block">{txn.descripcion}</span>
                        </TableCell>
                        <TableCell className="font-mono text-sm text-gray-500">{txn.referencia || '-'}</TableCell>
                        <TableCell>
                          <span className={`inline-flex items-center gap-1 text-xs px-2 py-1 rounded font-medium ${
                            txn.tipo_movimiento === 'credito' 
                              ? 'bg-green-100 text-green-700' 
                              : 'bg-red-100 text-red-700'
                          }`}>
                            {txn.tipo_movimiento === 'credito' ? (
                              <><ArrowUpCircle size={12} /> Depósito</>
                            ) : (
                              <><ArrowDownCircle size={12} /> Retiro</>
                            )}
                          </span>
                        </TableCell>
                        <TableCell className={`text-right font-mono font-semibold ${
                          txn.tipo_movimiento === 'credito' ? 'text-green-600' : 'text-red-600'
                        }`}>
                          {txn.tipo_movimiento === 'credito' ? '+' : '-'}
                          ${Math.abs(txn.monto).toLocaleString('es-MX', {minimumFractionDigits: 2})}
                        </TableCell>
                        <TableCell className="text-right font-mono">
                          ${(txn.saldo || 0).toLocaleString('es-MX', {minimumFractionDigits: 2})}
                        </TableCell>
                        <TableCell className="text-center">
                          {txn.conciliado ? (
                            <span className="inline-flex items-center gap-1 text-green-600 text-xs">
                              <Check size={14} /> Conciliado
                            </span>
                          ) : (
                            <span className="inline-flex items-center gap-1 text-yellow-600 text-xs">
                              <Clock size={14} /> Pendiente
                            </span>
                          )}
                        </TableCell>
                        <TableCell className="text-center">
                          <div className="flex justify-center gap-1">
                            {!txn.conciliado && (
                              <Button
                                variant="outline"
                                size="sm"
                                className="text-xs h-7"
                                onClick={() => {
                                  setSelectedTransaction(txn);
                                  setReconcileDialogOpen(true);
                                }}
                              >
                                <Link2 size={12} className="mr-1" />
                                Conciliar
                              </Button>
                            )}
                            <Button
                              variant="ghost"
                              size="sm"
                              className="h-7 text-red-500 hover:text-red-700"
                              onClick={() => handleDelete(txn.id)}
                            >
                              <Trash2 size={14} />
                            </Button>
                          </div>
                        </TableCell>
                      </TableRow>
                    );
                  })}
                </TableBody>
              </Table>
            </div>
          )}
        </CardContent>
      </Card>

      {/* Connect Bank Dialog */}
      <Dialog open={connectDialogOpen} onOpenChange={setConnectDialogOpen}>
        <DialogContent className="max-w-md">
          <DialogHeader>
            <DialogTitle className="flex items-center gap-2">
              <Link2 size={20} />
              Conectar Banco
            </DialogTitle>
            <DialogDescription>
              Descarga automáticamente tus movimientos bancarios
            </DialogDescription>
          </DialogHeader>
          
          <div className="space-y-4 py-4">
            <div className="bg-blue-50 border border-blue-200 rounded-lg p-4">
              <div className="flex items-start gap-3">
                <AlertCircle size={20} className="text-blue-600 mt-0.5" />
                <div>
                  <p className="font-medium text-blue-800">Próximamente</p>
                  <p className="text-sm text-blue-600 mt-1">
                    La conexión directa con bancos estará disponible próximamente. 
                    Por ahora puedes:
                  </p>
                </div>
              </div>
            </div>

            <div className="space-y-3">
              <div className="flex items-center gap-3 p-3 border rounded-lg hover:bg-gray-50">
                <Upload size={20} className="text-gray-500" />
                <div>
                  <p className="font-medium">Importar desde Excel</p>
                  <p className="text-sm text-gray-500">Descarga el estado de cuenta de tu banca en línea y súbelo aquí</p>
                </div>
              </div>
              
              <div className="flex items-center gap-3 p-3 border rounded-lg hover:bg-gray-50">
                <Plus size={20} className="text-gray-500" />
                <div>
                  <p className="font-medium">Captura manual</p>
                  <p className="text-sm text-gray-500">Agrega movimientos uno por uno desde tu estado de cuenta</p>
                </div>
              </div>
            </div>

            <div className="border-t pt-4">
              <p className="text-xs text-gray-500 text-center">
                Bancos soportados próximamente: BBVA, Santander, Banorte, HSBC, Scotiabank, Banamex
              </p>
            </div>
          </div>

          <DialogFooter>
            <Button variant="outline" onClick={() => setConnectDialogOpen(false)}>Cerrar</Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>

      {/* Reconcile Dialog */}
      <Dialog open={reconcileDialogOpen} onOpenChange={setReconcileDialogOpen}>
        <DialogContent className="max-w-2xl">
          <DialogHeader>
            <DialogTitle>Conciliar Movimiento con CFDI</DialogTitle>
            <DialogDescription>
              Selecciona el CFDI que corresponde a este movimiento bancario
            </DialogDescription>
          </DialogHeader>
          
          {selectedTransaction && (
            <div className="space-y-4">
              <div className="p-4 bg-gray-50 rounded-lg">
                <p className="text-sm font-medium text-gray-500">Movimiento a conciliar:</p>
                <p className="font-medium">{selectedTransaction.descripcion}</p>
                <div className="flex gap-4 mt-2">
                  <span className={`font-mono font-bold ${selectedTransaction.tipo_movimiento === 'credito' ? 'text-green-600' : 'text-red-600'}`}>
                    ${selectedTransaction.monto.toLocaleString('es-MX', {minimumFractionDigits: 2})}
                  </span>
                  <span className="text-sm text-gray-500">
                    {format(new Date(selectedTransaction.fecha_movimiento), 'dd/MM/yyyy')}
                  </span>
                </div>
              </div>

              <div className="space-y-2">
                <p className="text-sm font-medium">CFDIs disponibles:</p>
                <div className="max-h-64 overflow-y-auto space-y-2">
                  {cfdis.filter(c => !c.conciliado).length === 0 ? (
                    <p className="text-center text-gray-500 py-4">No hay CFDIs pendientes de conciliar</p>
                  ) : (
                    cfdis.filter(c => c.estado_conciliacion !== 'conciliado').map(cfdi => (
                      <div
                        key={cfdi.id}
                        className="p-3 border rounded-lg hover:bg-blue-50 cursor-pointer transition-colors"
                        onClick={() => handleReconcile(cfdi.id)}
                      >
                        <div className="flex justify-between items-start">
                          <div>
                            <p className="font-medium">{cfdi.emisor_nombre || cfdi.receptor_nombre}</p>
                            <p className="text-xs text-gray-500">{cfdi.tipo_cfdi?.toUpperCase()} - {cfdi.uuid?.slice(0, 8)}...</p>
                            <p className="text-xs text-gray-400">{cfdi.fecha_emision?.slice(0, 10)}</p>
                          </div>
                          <div className="text-right">
                            <p className="font-mono font-semibold">${cfdi.total?.toLocaleString('es-MX', {minimumFractionDigits: 2})}</p>
                            <p className="text-xs text-gray-500">{cfdi.moneda}</p>
                          </div>
                        </div>
                      </div>
                    ))
                  )}
                </div>
              </div>
            </div>
          )}

          <DialogFooter>
            <Button variant="outline" onClick={() => {
              setReconcileDialogOpen(false);
              setSelectedTransaction(null);
            }}>
              Cancelar
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>
    </div>
  );
};

export default BankStatementsModule;
