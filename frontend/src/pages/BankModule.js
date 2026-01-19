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
import { Plus, CheckCircle, Building2, Edit2, Trash2, DollarSign, CreditCard } from 'lucide-react';
import { format } from 'date-fns';

const BANKS = [
  'BBVA', 'Santander', 'Banorte', 'HSBC', 'Scotiabank', 'Banamex', 
  'BanBajío', 'Afirme', 'Banregio', 'Inbursa', 'Banco Azteca',
  'Albo', 'Clara', 'Clip', 'MercadoPago', 'Stripe', 'PayPal'
];

const CURRENCIES = ['MXN', 'USD', 'EUR', 'GBP', 'CAD'];

const BankModule = () => {
  const [bankTransactions, setBankTransactions] = useState([]);
  const [reconciliations, setReconciliations] = useState([]);
  const [bankAccounts, setBankAccounts] = useState([]);
  const [accountsSummary, setAccountsSummary] = useState(null);
  const [cashflowTransactions, setCashflowTransactions] = useState([]);
  const [loading, setLoading] = useState(true);
  const [dialogOpen, setDialogOpen] = useState(false);
  const [accountDialogOpen, setAccountDialogOpen] = useState(false);
  const [editingAccount, setEditingAccount] = useState(null);
  const [reconcileDialogOpen, setReconcileDialogOpen] = useState(false);
  const [selectedBankTxn, setSelectedBankTxn] = useState(null);
  
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

  const [accountFormData, setAccountFormData] = useState({
    nombre: '',
    numero_cuenta: '',
    banco: 'BBVA',
    moneda: 'MXN',
    pais_banco: 'México',
    saldo_inicial: '',
    fecha_saldo: format(new Date(), "yyyy-MM-dd")
  });

  useEffect(() => {
    loadData();
  }, []);

  const loadData = async () => {
    try {
      const [bankTxnRes, reconRes, accountsRes, summaryRes, cashflowTxnRes] = await Promise.all([
        api.get('/bank-transactions?limit=100'),
        api.get('/reconciliations?limit=100'),
        api.get('/bank-accounts'),
        api.get('/bank-accounts/summary'),
        api.get('/transactions?limit=100')
      ]);
      setBankTransactions(bankTxnRes.data);
      setReconciliations(reconRes.data);
      setBankAccounts(accountsRes.data);
      setAccountsSummary(summaryRes.data);
      setCashflowTransactions(cashflowTxnRes.data);
    } catch (error) {
      toast.error('Error cargando datos');
    } finally {
      setLoading(false);
    }
  };

  const handleSubmit = async (e) => {
    e.preventDefault();
    try {
      await api.post('/bank-transactions', {
        ...formData,
        monto: parseFloat(formData.monto),
        saldo: parseFloat(formData.saldo)
      });
      toast.success('Movimiento bancario creado');
      setDialogOpen(false);
      loadData();
    } catch (error) {
      toast.error(error.response?.data?.detail || 'Error creando movimiento');
    }
  };

  const handleAccountSubmit = async (e) => {
    e.preventDefault();
    try {
      const data = {
        ...accountFormData,
        saldo_inicial: parseFloat(accountFormData.saldo_inicial) || 0
      };
      
      if (editingAccount) {
        await api.put(`/bank-accounts/${editingAccount.id}`, data);
        toast.success('Cuenta actualizada');
      } else {
        await api.post('/bank-accounts', data);
        toast.success('Cuenta bancaria creada');
      }
      
      setAccountDialogOpen(false);
      setEditingAccount(null);
      setAccountFormData({
        nombre: '',
        numero_cuenta: '',
        banco: 'BBVA',
        moneda: 'MXN',
        pais_banco: 'México',
        saldo_inicial: ''
      });
      loadData();
    } catch (error) {
      toast.error(error.response?.data?.detail || 'Error guardando cuenta');
    }
  };

  const handleEditAccount = (account) => {
    setEditingAccount(account);
    setAccountFormData({
      nombre: account.nombre,
      numero_cuenta: account.numero_cuenta,
      banco: account.banco,
      moneda: account.moneda,
      pais_banco: account.pais_banco || 'México',
      saldo_inicial: account.saldo_inicial?.toString() || '0'
    });
    setAccountDialogOpen(true);
  };

  const handleDeleteAccount = async (accountId) => {
    if (!confirm('¿Eliminar esta cuenta bancaria?')) return;
    try {
      await api.delete(`/bank-accounts/${accountId}`);
      toast.success('Cuenta eliminada');
      loadData();
    } catch (error) {
      toast.error('Error eliminando cuenta');
    }
  };

  const handleReconcile = async (transactionId) => {
    if (!selectedBankTxn) return;
    try {
      await api.post('/reconciliations', {
        bank_transaction_id: selectedBankTxn.id,
        transaction_id: transactionId,
        metodo_conciliacion: 'manual',
        porcentaje_match: 100
      });
      toast.success('Conciliación realizada');
      setReconcileDialogOpen(false);
      setSelectedBankTxn(null);
      loadData();
    } catch (error) {
      toast.error(error.response?.data?.detail || 'Error conciliando');
    }
  };

  if (loading) return <div className="p-8">Cargando...</div>;

  const unreconciled = bankTransactions.filter(t => !t.conciliado);

  return (
    <div className="p-8 space-y-6" data-testid="bank-page">
      <div className="flex justify-between items-center">
        <div>
          <h1 className="text-4xl font-bold text-[#0F172A] mb-2" style={{fontFamily: 'Manrope'}}>Módulo Bancario</h1>
          <p className="text-[#64748B]">Cuentas bancarias, movimientos y conciliación</p>
        </div>
        <div className="flex gap-2">
          <Dialog open={accountDialogOpen} onOpenChange={(open) => {
            setAccountDialogOpen(open);
            if (!open) {
              setEditingAccount(null);
              setAccountFormData({
                nombre: '',
                numero_cuenta: '',
                banco: 'BBVA',
                moneda: 'MXN',
                pais_banco: 'México',
                saldo_inicial: ''
              });
            }
          }}>
            <DialogTrigger asChild>
              <Button variant="outline" className="gap-2" data-testid="add-bank-account-button">
                <Building2 size={16} />
                Nueva Cuenta
              </Button>
            </DialogTrigger>
            <DialogContent>
              <DialogHeader>
                <DialogTitle>{editingAccount ? 'Editar Cuenta Bancaria' : 'Nueva Cuenta Bancaria'}</DialogTitle>
                <DialogDescription>Configura los datos de la cuenta bancaria</DialogDescription>
              </DialogHeader>
              <form onSubmit={handleAccountSubmit} className="space-y-4">
                <div className="space-y-2">
                  <Label>Nombre de la Cuenta</Label>
                  <Input
                    value={accountFormData.nombre}
                    onChange={(e) => setAccountFormData({...accountFormData, nombre: e.target.value})}
                    placeholder="Ej: Cuenta Operativa Principal"
                    required
                  />
                </div>

                <div className="grid grid-cols-2 gap-4">
                  <div className="space-y-2">
                    <Label>Banco</Label>
                    <Select value={accountFormData.banco} onValueChange={(v) => setAccountFormData({...accountFormData, banco: v})}>
                      <SelectTrigger>
                        <SelectValue />
                      </SelectTrigger>
                      <SelectContent>
                        {BANKS.map(b => (
                          <SelectItem key={b} value={b}>{b}</SelectItem>
                        ))}
                      </SelectContent>
                    </Select>
                  </div>
                  <div className="space-y-2">
                    <Label>Moneda</Label>
                    <Select value={accountFormData.moneda} onValueChange={(v) => setAccountFormData({...accountFormData, moneda: v})}>
                      <SelectTrigger>
                        <SelectValue />
                      </SelectTrigger>
                      <SelectContent>
                        {CURRENCIES.map(c => (
                          <SelectItem key={c} value={c}>{c}</SelectItem>
                        ))}
                      </SelectContent>
                    </Select>
                  </div>
                </div>

                <div className="space-y-2">
                  <Label>Número de Cuenta</Label>
                  <Input
                    value={accountFormData.numero_cuenta}
                    onChange={(e) => setAccountFormData({...accountFormData, numero_cuenta: e.target.value})}
                    placeholder="Últimos 4 dígitos o CLABE"
                    required
                  />
                </div>

                <div className="space-y-2">
                  <Label className="flex items-center gap-2">
                    <DollarSign size={16} className="text-[#0EA5E9]" />
                    Balance Inicial
                    <span className="text-xs text-[#64748B] font-normal">(importante para flujo de efectivo)</span>
                  </Label>
                  <Input
                    type="number"
                    step="0.01"
                    value={accountFormData.saldo_inicial}
                    onChange={(e) => setAccountFormData({...accountFormData, saldo_inicial: e.target.value})}
                    placeholder="0.00"
                    className="text-lg font-mono"
                  />
                </div>

                <div className="space-y-2">
                  <Label className="flex items-center gap-2">
                    Fecha del Saldo
                    <span className="text-xs text-[#64748B] font-normal">(para tipo de cambio histórico)</span>
                  </Label>
                  <Input
                    type="date"
                    value={accountFormData.fecha_saldo}
                    onChange={(e) => setAccountFormData({...accountFormData, fecha_saldo: e.target.value})}
                    className="font-mono"
                  />
                  <p className="text-xs text-[#94A3B8]">Se usará el tipo de cambio de esta fecha para convertir a MXN</p>
                </div>

                <DialogFooter>
                  <Button type="submit">{editingAccount ? 'Actualizar' : 'Crear'} Cuenta</Button>
                </DialogFooter>
              </form>
            </DialogContent>
          </Dialog>

          <Dialog open={dialogOpen} onOpenChange={setDialogOpen}>
            <DialogTrigger asChild>
              <Button className="bg-[#0F172A] hover:bg-[#1E293B] gap-2" data-testid="create-bank-transaction-button">
                <Plus size={16} />
                Nuevo Movimiento
              </Button>
            </DialogTrigger>
            <DialogContent>
              <DialogHeader>
                <DialogTitle>Nuevo Movimiento Bancario</DialogTitle>
                <DialogDescription>Registra un movimiento bancario</DialogDescription>
              </DialogHeader>
              <form onSubmit={handleSubmit} className="space-y-4">
                <div className="space-y-2">
                  <Label>Cuenta Bancaria</Label>
                  <Select value={formData.bank_account_id} onValueChange={(v) => setFormData({...formData, bank_account_id: v})}>
                    <SelectTrigger>
                      <SelectValue placeholder="Selecciona cuenta" />
                    </SelectTrigger>
                    <SelectContent>
                      {bankAccounts.map(acc => (
                        <SelectItem key={acc.id} value={acc.id}>{acc.nombre} - {acc.banco} ({acc.moneda})</SelectItem>
                      ))}
                    </SelectContent>
                  </Select>
                </div>

                <div className="space-y-2">
                  <Label>Descripción</Label>
                  <Input
                    value={formData.descripcion}
                    onChange={(e) => setFormData({...formData, descripcion: e.target.value})}
                    required
                  />
                </div>

                <div className="grid grid-cols-2 gap-4">
                  <div className="space-y-2">
                    <Label>Monto</Label>
                    <Input
                      type="number"
                      step="0.01"
                      value={formData.monto}
                      onChange={(e) => setFormData({...formData, monto: e.target.value})}
                      required
                    />
                  </div>
                  <div className="space-y-2">
                    <Label>Saldo Resultante</Label>
                    <Input
                      type="number"
                      step="0.01"
                      value={formData.saldo}
                      onChange={(e) => setFormData({...formData, saldo: e.target.value})}
                      required
                    />
                  </div>
                </div>

                <div className="space-y-2">
                  <Label>Tipo</Label>
                  <Select value={formData.tipo_movimiento} onValueChange={(v) => setFormData({...formData, tipo_movimiento: v})}>
                    <SelectTrigger>
                      <SelectValue />
                    </SelectTrigger>
                    <SelectContent>
                      <SelectItem value="credito">Crédito (Abono)</SelectItem>
                      <SelectItem value="debito">Débito (Cargo)</SelectItem>
                    </SelectContent>
                  </Select>
                </div>

                <div className="grid grid-cols-2 gap-4">
                  <div className="space-y-2">
                    <Label>Fecha Movimiento</Label>
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
                      required
                    />
                  </div>
                </div>

                <DialogFooter>
                  <Button type="submit">Crear Movimiento</Button>
                </DialogFooter>
              </form>
            </DialogContent>
          </Dialog>
        </div>
      </div>

      {/* Summary Cards */}
      <div className="grid grid-cols-1 md:grid-cols-4 gap-4">
        <Card className="border-[#0EA5E9] bg-blue-50">
          <CardHeader className="pb-2">
            <CardTitle className="text-sm font-medium text-[#0369A1] flex items-center gap-2">
              <Building2 size={16} />
              Balance Total (MXN)
            </CardTitle>
          </CardHeader>
          <CardContent>
            <div className="text-2xl font-bold mono text-[#0369A1]">
              ${(accountsSummary?.total_mxn || 0).toLocaleString('es-MX', {minimumFractionDigits: 2})}
            </div>
            <div className="text-xs text-[#64748B]">{accountsSummary?.total_cuentas || 0} cuentas activas</div>
          </CardContent>
        </Card>

        {Object.entries(accountsSummary?.por_moneda || {}).map(([moneda, data]) => (
          <Card key={moneda} className="border-[#E2E8F0]">
            <CardHeader className="pb-2">
              <CardTitle className="text-sm font-medium text-[#64748B] flex items-center gap-2">
                <CreditCard size={16} />
                {moneda}
              </CardTitle>
            </CardHeader>
            <CardContent>
              <div className="text-2xl font-bold mono text-[#0F172A]">
                ${data.saldo.toLocaleString('es-MX', {minimumFractionDigits: 2})}
              </div>
              <div className="text-xs text-[#64748B]">{data.cuentas} cuenta(s)</div>
            </CardContent>
          </Card>
        ))}

        <Card className="border-[#F59E0B] bg-yellow-50">
          <CardHeader className="pb-2">
            <CardTitle className="text-sm font-medium text-[#92400E] flex items-center gap-2">
              Sin Conciliar
            </CardTitle>
          </CardHeader>
          <CardContent>
            <div className="text-2xl font-bold mono text-[#92400E]">{unreconciled.length}</div>
            <div className="text-xs text-[#64748B]">movimientos pendientes</div>
          </CardContent>
        </Card>
      </div>

      <Tabs defaultValue="accounts" className="w-full">
        <TabsList>
          <TabsTrigger value="accounts">Cuentas Bancarias</TabsTrigger>
          <TabsTrigger value="movements">Movimientos</TabsTrigger>
          <TabsTrigger value="reconciliations">Conciliaciones</TabsTrigger>
        </TabsList>

        <TabsContent value="accounts">
          <Card className="border-[#E2E8F0]">
            <CardHeader>
              <CardTitle>Cuentas Bancarias</CardTitle>
              <CardDescription>{bankAccounts.length} cuentas registradas</CardDescription>
            </CardHeader>
            <CardContent>
              <Table className="data-table">
                <TableHeader>
                  <TableRow>
                    <TableHead>Banco</TableHead>
                    <TableHead>Nombre Cuenta</TableHead>
                    <TableHead>Número</TableHead>
                    <TableHead>Moneda</TableHead>
                    <TableHead>Balance Inicial</TableHead>
                    <TableHead className="text-center">Acciones</TableHead>
                  </TableRow>
                </TableHeader>
                <TableBody>
                  {bankAccounts.length === 0 ? (
                    <TableRow>
                      <TableCell colSpan={6} className="text-center text-[#94A3B8] py-8">
                        No hay cuentas bancarias. Crea la primera.
                      </TableCell>
                    </TableRow>
                  ) : (
                    bankAccounts.map((acc) => (
                      <TableRow key={acc.id}>
                        <TableCell>
                          <div className="flex items-center gap-2">
                            <div className="w-8 h-8 rounded-full bg-[#F1F5F9] flex items-center justify-center">
                              <Building2 size={16} className="text-[#64748B]" />
                            </div>
                            <span className="font-medium">{acc.banco}</span>
                          </div>
                        </TableCell>
                        <TableCell>{acc.nombre}</TableCell>
                        <TableCell className="mono text-sm">****{acc.numero_cuenta?.slice(-4)}</TableCell>
                        <TableCell>
                          <span className={`text-xs px-2 py-1 rounded font-medium ${
                            acc.moneda === 'USD' ? 'bg-blue-100 text-blue-800' :
                            acc.moneda === 'EUR' ? 'bg-purple-100 text-purple-800' :
                            'bg-gray-100 text-gray-800'
                          }`}>
                            {acc.moneda}
                          </span>
                        </TableCell>
                        <TableCell className="mono font-semibold text-[#0F172A]">
                          ${(acc.saldo_inicial || 0).toLocaleString('es-MX', {minimumFractionDigits: 2})}
                        </TableCell>
                        <TableCell className="text-center">
                          <div className="flex justify-center gap-1">
                            <Button
                              variant="ghost"
                              size="sm"
                              onClick={() => handleEditAccount(acc)}
                              className="text-[#64748B] hover:text-[#0F172A]"
                            >
                              <Edit2 size={16} />
                            </Button>
                            <Button
                              variant="ghost"
                              size="sm"
                              onClick={() => handleDeleteAccount(acc.id)}
                              className="text-red-500 hover:text-red-700"
                            >
                              <Trash2 size={16} />
                            </Button>
                          </div>
                        </TableCell>
                      </TableRow>
                    ))
                  )}
                </TableBody>
              </Table>
            </CardContent>
          </Card>
        </TabsContent>

        <TabsContent value="movements">
          <Card className="border-[#E2E8F0]">
            <CardHeader>
              <CardTitle>Movimientos Bancarios</CardTitle>
              <CardDescription>{bankTransactions.length} movimientos registrados</CardDescription>
            </CardHeader>
            <CardContent>
              <Table className="data-table">
                <TableHeader>
                  <TableRow>
                    <TableHead>Fecha</TableHead>
                    <TableHead>Descripción</TableHead>
                    <TableHead>Tipo</TableHead>
                    <TableHead>Monto</TableHead>
                    <TableHead>Saldo</TableHead>
                    <TableHead>Conciliado</TableHead>
                    <TableHead>Acción</TableHead>
                  </TableRow>
                </TableHeader>
                <TableBody>
                  {bankTransactions.length === 0 ? (
                    <TableRow>
                      <TableCell colSpan={7} className="text-center text-[#94A3B8] py-8">
                        No hay movimientos bancarios.
                      </TableCell>
                    </TableRow>
                  ) : (
                    bankTransactions.map((txn) => (
                      <TableRow key={txn.id}>
                        <TableCell className="mono">{format(new Date(txn.fecha_movimiento), 'dd/MM/yyyy')}</TableCell>
                        <TableCell>{txn.descripcion}</TableCell>
                        <TableCell>
                          <span className={`px-2 py-1 text-xs rounded ${txn.tipo_movimiento === 'credito' ? 'bg-green-100 text-green-800' : 'bg-red-100 text-red-800'}`}>
                            {txn.tipo_movimiento}
                          </span>
                        </TableCell>
                        <TableCell className="mono font-semibold">${txn.monto.toLocaleString('es-MX', {minimumFractionDigits: 2})}</TableCell>
                        <TableCell className="mono">${txn.saldo.toLocaleString('es-MX', {minimumFractionDigits: 2})}</TableCell>
                        <TableCell>
                          {txn.conciliado ? (
                            <CheckCircle className="text-[#10B981]" size={20} />
                          ) : (
                            <span className="text-xs text-[#94A3B8]">Pendiente</span>
                          )}
                        </TableCell>
                        <TableCell>
                          {!txn.conciliado && (
                            <Button
                              size="sm"
                              variant="outline"
                              onClick={() => {
                                setSelectedBankTxn(txn);
                                setReconcileDialogOpen(true);
                              }}
                            >
                              Conciliar
                            </Button>
                          )}
                        </TableCell>
                      </TableRow>
                    ))
                  )}
                </TableBody>
              </Table>
            </CardContent>
          </Card>
        </TabsContent>

        <TabsContent value="reconciliations">
          <Card className="border-[#E2E8F0]">
            <CardHeader>
              <CardTitle>Conciliaciones Realizadas</CardTitle>
              <CardDescription>{reconciliations.length} conciliaciones completadas</CardDescription>
            </CardHeader>
            <CardContent>
              <Table className="data-table">
                <TableHeader>
                  <TableRow>
                    <TableHead>Fecha</TableHead>
                    <TableHead>Método</TableHead>
                    <TableHead>% Match</TableHead>
                    <TableHead>Notas</TableHead>
                  </TableRow>
                </TableHeader>
                <TableBody>
                  {reconciliations.length === 0 ? (
                    <TableRow>
                      <TableCell colSpan={4} className="text-center text-[#94A3B8] py-8">
                        No hay conciliaciones realizadas.
                      </TableCell>
                    </TableRow>
                  ) : (
                    reconciliations.map((recon) => (
                      <TableRow key={recon.id}>
                        <TableCell className="mono">{format(new Date(recon.fecha_conciliacion), 'dd/MM/yyyy HH:mm')}</TableCell>
                        <TableCell>
                          <span className="text-xs px-2 py-1 bg-[#F1F5F9] rounded">{recon.metodo_conciliacion}</span>
                        </TableCell>
                        <TableCell className="mono">{recon.porcentaje_match}%</TableCell>
                        <TableCell className="text-sm text-[#64748B]">{recon.notas || '-'}</TableCell>
                      </TableRow>
                    ))
                  )}
                </TableBody>
              </Table>
            </CardContent>
          </Card>
        </TabsContent>
      </Tabs>

      <Dialog open={reconcileDialogOpen} onOpenChange={setReconcileDialogOpen}>
        <DialogContent className="max-w-2xl">
          <DialogHeader>
            <DialogTitle>Conciliar Movimiento Bancario</DialogTitle>
            <DialogDescription>
              Selecciona la transacción de cashflow que corresponde a este movimiento bancario
            </DialogDescription>
          </DialogHeader>
          {selectedBankTxn && (
            <div className="space-y-4">
              <div className="p-4 bg-[#F1F5F9] rounded">
                <p className="text-sm font-semibold">Movimiento Bancario:</p>
                <p className="text-sm">{selectedBankTxn.descripcion}</p>
                <p className="mono font-bold text-lg">${selectedBankTxn.monto.toLocaleString('es-MX')}</p>
              </div>

              <div className="space-y-2">
                <p className="text-sm font-semibold">Transacciones Disponibles:</p>
                <div className="max-h-64 overflow-y-auto space-y-2">
                  {cashflowTransactions.filter(t => !t.es_real).map(txn => (
                    <div
                      key={txn.id}
                      className="p-3 border border-[#E2E8F0] rounded hover:bg-[#F1F5F9] cursor-pointer"
                      onClick={() => handleReconcile(txn.id)}
                    >
                      <div className="flex justify-between items-start">
                        <div>
                          <p className="text-sm font-medium">{txn.concepto}</p>
                          <p className="text-xs text-[#64748B]">{format(new Date(txn.fecha_transaccion), 'dd/MM/yyyy')}</p>
                        </div>
                        <p className="mono font-semibold">${txn.monto.toLocaleString('es-MX')}</p>
                      </div>
                    </div>
                  ))}
                </div>
              </div>
            </div>
          )}
        </DialogContent>
      </Dialog>
    </div>
  );
};

export default BankModule;
