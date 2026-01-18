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
import { Plus, Edit2, Trash2, FolderPlus, Tag, TrendingUp, TrendingDown, Download } from 'lucide-react';

const CATEGORY_COLORS = [
  { value: '#EF4444', label: 'Rojo', bg: 'bg-red-100' },
  { value: '#F97316', label: 'Naranja', bg: 'bg-orange-100' },
  { value: '#EAB308', label: 'Amarillo', bg: 'bg-yellow-100' },
  { value: '#22C55E', label: 'Verde', bg: 'bg-green-100' },
  { value: '#10B981', label: 'Esmeralda', bg: 'bg-emerald-100' },
  { value: '#0EA5E9', label: 'Azul', bg: 'bg-sky-100' },
  { value: '#6366F1', label: 'Índigo', bg: 'bg-indigo-100' },
  { value: '#8B5CF6', label: 'Violeta', bg: 'bg-violet-100' },
  { value: '#EC4899', label: 'Rosa', bg: 'bg-pink-100' },
  { value: '#6B7280', label: 'Gris', bg: 'bg-gray-100' },
];

const CATEGORY_ICONS = [
  { value: 'folder', label: 'Carpeta' },
  { value: 'briefcase', label: 'Negocio' },
  { value: 'building', label: 'Edificio' },
  { value: 'truck', label: 'Logística' },
  { value: 'users', label: 'Personal' },
  { value: 'shopping-cart', label: 'Compras' },
  { value: 'credit-card', label: 'Finanzas' },
  { value: 'tool', label: 'Servicios' },
  { value: 'zap', label: 'Operaciones' },
  { value: 'star', label: 'Especial' },
];

const CategoriesModule = () => {
  const [categories, setCategories] = useState([]);
  const [loading, setLoading] = useState(true);
  const [dialogOpen, setDialogOpen] = useState(false);
  const [subcatDialogOpen, setSubcatDialogOpen] = useState(false);
  const [editingCategory, setEditingCategory] = useState(null);
  const [filterTipo, setFilterTipo] = useState('all');
  const [selectedCategoryForSubcat, setSelectedCategoryForSubcat] = useState(null);
  const [exportDialogOpen, setExportDialogOpen] = useState(false);
  const [exportDateRange, setExportDateRange] = useState({ desde: '', hasta: '' });

  const [formData, setFormData] = useState({
    nombre: '',
    tipo: 'egreso',
    color: '#6B7280',
    icono: 'folder'
  });

  const [subcatFormData, setSubcatFormData] = useState({
    category_id: '',
    nombre: ''
  });

  useEffect(() => {
    loadCategories();
  }, [filterTipo]);

  const loadCategories = async () => {
    try {
      let url = '/categories';
      if (filterTipo !== 'all') url += `?tipo=${filterTipo}`;
      const response = await api.get(url);
      setCategories(response.data);
    } catch (error) {
      toast.error('Error cargando categorías');
    } finally {
      setLoading(false);
    }
  };

  const handleSubmit = async (e) => {
    e.preventDefault();
    try {
      if (editingCategory) {
        await api.put(`/categories/${editingCategory.id}`, formData);
        toast.success('Categoría actualizada');
      } else {
        await api.post('/categories', formData);
        toast.success('Categoría creada');
      }
      setDialogOpen(false);
      setEditingCategory(null);
      loadCategories();
      resetForm();
    } catch (error) {
      toast.error(error.response?.data?.detail || 'Error guardando categoría');
    }
  };

  const handleSubcatSubmit = async (e) => {
    e.preventDefault();
    try {
      await api.post('/subcategories', subcatFormData);
      toast.success('Subcategoría creada');
      setSubcatDialogOpen(false);
      loadCategories();
      setSubcatFormData({ category_id: '', nombre: '' });
    } catch (error) {
      toast.error(error.response?.data?.detail || 'Error creando subcategoría');
    }
  };

  const handleDelete = async (categoryId) => {
    if (!window.confirm('¿Eliminar esta categoría? Las subcategorías también serán eliminadas.')) return;
    try {
      await api.delete(`/categories/${categoryId}`);
      toast.success('Categoría eliminada');
      loadCategories();
    } catch (error) {
      toast.error('Error eliminando categoría');
    }
  };

  const handleDeleteSubcat = async (subcatId) => {
    if (!window.confirm('¿Eliminar esta subcategoría?')) return;
    try {
      await api.delete(`/subcategories/${subcatId}`);
      toast.success('Subcategoría eliminada');
      loadCategories();
    } catch (error) {
      toast.error('Error eliminando subcategoría');
    }
  };

  const handleEdit = (category) => {
    setEditingCategory(category);
    setFormData({
      nombre: category.nombre,
      tipo: category.tipo,
      color: category.color,
      icono: category.icono
    });
    setDialogOpen(true);
  };

  const openSubcatDialog = (category) => {
    setSelectedCategoryForSubcat(category);
    setSubcatFormData({ category_id: category.id, nombre: '' });
    setSubcatDialogOpen(true);
  };

  const resetForm = () => {
    setFormData({
      nombre: '',
      tipo: 'egreso',
      color: '#6B7280',
      icono: 'folder'
    });
  };

  const handleExportDIOT = async () => {
    try {
      let url = '/export/diot';
      const params = new URLSearchParams();
      if (exportDateRange.desde) params.append('fecha_desde', exportDateRange.desde);
      if (exportDateRange.hasta) params.append('fecha_hasta', exportDateRange.hasta);
      if (params.toString()) url += `?${params.toString()}`;

      const response = await api.get(url, { responseType: 'blob' });
      const blob = new Blob([response.data], { type: 'text/csv' });
      const downloadUrl = window.URL.createObjectURL(blob);
      const link = document.createElement('a');
      link.href = downloadUrl;
      link.download = `DIOT_export_${new Date().toISOString().split('T')[0]}.csv`;
      document.body.appendChild(link);
      link.click();
      link.remove();
      window.URL.revokeObjectURL(downloadUrl);
      toast.success('Archivo DIOT exportado');
      setExportDialogOpen(false);
    } catch (error) {
      toast.error('Error exportando DIOT');
    }
  };

  const downloadBankTemplate = async () => {
    try {
      const response = await api.get('/bank-transactions/template', { responseType: 'blob' });
      const blob = new Blob([response.data], { 
        type: 'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet' 
      });
      const downloadUrl = window.URL.createObjectURL(blob);
      const link = document.createElement('a');
      link.href = downloadUrl;
      link.download = 'plantilla_estado_cuenta.xlsx';
      document.body.appendChild(link);
      link.click();
      link.remove();
      window.URL.revokeObjectURL(downloadUrl);
      toast.success('Plantilla descargada');
    } catch (error) {
      toast.error('Error descargando plantilla');
    }
  };

  const ingresoCategories = categories.filter(c => c.tipo === 'ingreso');
  const egresoCategories = categories.filter(c => c.tipo === 'egreso');

  if (loading) return <div className="p-8">Cargando...</div>;

  return (
    <div className="p-8 space-y-6" data-testid="categories-page">
      <div className="flex justify-between items-center">
        <div>
          <h1 className="text-4xl font-bold text-[#0F172A] mb-2" style={{fontFamily: 'Manrope'}}>Categorías</h1>
          <p className="text-[#64748B]">Organiza tus ingresos y egresos para reportes fiscales</p>
        </div>
        <div className="flex gap-2">
          {/* Export DIOT Button */}
          <Dialog open={exportDialogOpen} onOpenChange={setExportDialogOpen}>
            <DialogTrigger asChild>
              <Button variant="outline" className="gap-2" data-testid="export-diot-button">
                <Download size={16} />
                Exportar DIOT
              </Button>
            </DialogTrigger>
            <DialogContent>
              <DialogHeader>
                <DialogTitle>Exportar DIOT</DialogTitle>
                <DialogDescription>
                  Genera el archivo CSV para la declaración DIOT con tus CFDIs categorizados
                </DialogDescription>
              </DialogHeader>
              <div className="space-y-4 py-4">
                <div className="grid grid-cols-2 gap-4">
                  <div className="space-y-2">
                    <Label>Fecha Desde</Label>
                    <Input
                      type="date"
                      value={exportDateRange.desde}
                      onChange={(e) => setExportDateRange({...exportDateRange, desde: e.target.value})}
                    />
                  </div>
                  <div className="space-y-2">
                    <Label>Fecha Hasta</Label>
                    <Input
                      type="date"
                      value={exportDateRange.hasta}
                      onChange={(e) => setExportDateRange({...exportDateRange, hasta: e.target.value})}
                    />
                  </div>
                </div>
                <p className="text-sm text-[#64748B]">
                  Deja vacío para exportar todos los CFDIs registrados.
                </p>
              </div>
              <DialogFooter>
                <Button variant="outline" onClick={() => setExportDialogOpen(false)}>Cancelar</Button>
                <Button onClick={handleExportDIOT} className="gap-2">
                  <Download size={16} />
                  Descargar CSV
                </Button>
              </DialogFooter>
            </DialogContent>
          </Dialog>

          {/* Download Bank Template */}
          <Button variant="outline" className="gap-2" onClick={downloadBankTemplate} data-testid="download-template-button">
            <Download size={16} />
            Plantilla Estado Cuenta
          </Button>

          {/* New Category Button */}
          <Dialog open={dialogOpen} onOpenChange={(open) => {
            setDialogOpen(open);
            if (!open) {
              setEditingCategory(null);
              resetForm();
            }
          }}>
            <DialogTrigger asChild>
              <Button className="bg-[#0F172A] hover:bg-[#1E293B] gap-2" data-testid="new-category-button">
                <Plus size={16} />
                Nueva Categoría
              </Button>
            </DialogTrigger>
            <DialogContent>
              <DialogHeader>
                <DialogTitle>{editingCategory ? 'Editar Categoría' : 'Nueva Categoría'}</DialogTitle>
                <DialogDescription>
                  {editingCategory ? 'Modifica los datos de la categoría' : 'Crea una categoría para organizar tus movimientos'}
                </DialogDescription>
              </DialogHeader>
              <form onSubmit={handleSubmit} className="space-y-4">
                <div className="space-y-2">
                  <Label>Nombre</Label>
                  <Input
                    value={formData.nombre}
                    onChange={(e) => setFormData({...formData, nombre: e.target.value})}
                    placeholder="Ej: Gastos Operativos"
                    required
                    data-testid="category-name-input"
                  />
                </div>

                <div className="space-y-2">
                  <Label>Tipo</Label>
                  <Select value={formData.tipo} onValueChange={(v) => setFormData({...formData, tipo: v})}>
                    <SelectTrigger data-testid="category-type-select">
                      <SelectValue />
                    </SelectTrigger>
                    <SelectContent>
                      <SelectItem value="egreso">Egreso (Gasto)</SelectItem>
                      <SelectItem value="ingreso">Ingreso</SelectItem>
                    </SelectContent>
                  </Select>
                </div>

                <div className="space-y-2">
                  <Label>Color</Label>
                  <div className="flex flex-wrap gap-2">
                    {CATEGORY_COLORS.map((color) => (
                      <button
                        key={color.value}
                        type="button"
                        onClick={() => setFormData({...formData, color: color.value})}
                        className={`w-8 h-8 rounded-full border-2 transition-all ${
                          formData.color === color.value ? 'border-[#0F172A] scale-110' : 'border-transparent'
                        }`}
                        style={{ backgroundColor: color.value }}
                        title={color.label}
                      />
                    ))}
                  </div>
                </div>

                <div className="space-y-2">
                  <Label>Icono</Label>
                  <Select value={formData.icono} onValueChange={(v) => setFormData({...formData, icono: v})}>
                    <SelectTrigger>
                      <SelectValue />
                    </SelectTrigger>
                    <SelectContent>
                      {CATEGORY_ICONS.map((icon) => (
                        <SelectItem key={icon.value} value={icon.value}>{icon.label}</SelectItem>
                      ))}
                    </SelectContent>
                  </Select>
                </div>

                <DialogFooter>
                  <Button type="submit" data-testid="save-category-button">
                    {editingCategory ? 'Guardar Cambios' : 'Crear Categoría'}
                  </Button>
                </DialogFooter>
              </form>
            </DialogContent>
          </Dialog>
        </div>
      </div>

      {/* Subcategory Dialog */}
      <Dialog open={subcatDialogOpen} onOpenChange={setSubcatDialogOpen}>
        <DialogContent>
          <DialogHeader>
            <DialogTitle>Nueva Subcategoría</DialogTitle>
            <DialogDescription>
              Agregar subcategoría a: {selectedCategoryForSubcat?.nombre}
            </DialogDescription>
          </DialogHeader>
          <form onSubmit={handleSubcatSubmit} className="space-y-4">
            <div className="space-y-2">
              <Label>Nombre de Subcategoría</Label>
              <Input
                value={subcatFormData.nombre}
                onChange={(e) => setSubcatFormData({...subcatFormData, nombre: e.target.value})}
                placeholder="Ej: Renta de oficina"
                required
                data-testid="subcategory-name-input"
              />
            </div>
            <DialogFooter>
              <Button type="submit" data-testid="save-subcategory-button">Crear Subcategoría</Button>
            </DialogFooter>
          </form>
        </DialogContent>
      </Dialog>

      {/* Summary Cards */}
      <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
        <Card className="border-[#E2E8F0]">
          <CardHeader className="pb-2">
            <CardTitle className="text-sm font-medium text-[#64748B] flex items-center gap-2">
              <Tag size={16} />
              Total Categorías
            </CardTitle>
          </CardHeader>
          <CardContent>
            <div className="text-3xl font-bold text-[#0F172A]">{categories.length}</div>
          </CardContent>
        </Card>

        <Card className="border-[#10B981] bg-green-50">
          <CardHeader className="pb-2">
            <CardTitle className="text-sm font-medium text-[#059669] flex items-center gap-2">
              <TrendingUp size={16} />
              Categorías Ingresos
            </CardTitle>
          </CardHeader>
          <CardContent>
            <div className="text-3xl font-bold text-[#059669]">{ingresoCategories.length}</div>
            <div className="text-xs text-[#64748B]">
              {ingresoCategories.reduce((acc, c) => acc + (c.subcategorias?.length || 0), 0)} subcategorías
            </div>
          </CardContent>
        </Card>

        <Card className="border-[#EF4444] bg-red-50">
          <CardHeader className="pb-2">
            <CardTitle className="text-sm font-medium text-[#DC2626] flex items-center gap-2">
              <TrendingDown size={16} />
              Categorías Egresos
            </CardTitle>
          </CardHeader>
          <CardContent>
            <div className="text-3xl font-bold text-[#DC2626]">{egresoCategories.length}</div>
            <div className="text-xs text-[#64748B]">
              {egresoCategories.reduce((acc, c) => acc + (c.subcategorias?.length || 0), 0)} subcategorías
            </div>
          </CardContent>
        </Card>
      </div>

      {/* Filter */}
      <Card className="border-[#E2E8F0]">
        <CardContent className="py-4">
          <div className="flex gap-4 items-center">
            <Label className="text-xs">Filtrar por tipo:</Label>
            <Select value={filterTipo} onValueChange={setFilterTipo}>
              <SelectTrigger className="w-40" data-testid="filter-type-select">
                <SelectValue />
              </SelectTrigger>
              <SelectContent>
                <SelectItem value="all">Todas</SelectItem>
                <SelectItem value="ingreso">Ingresos</SelectItem>
                <SelectItem value="egreso">Egresos</SelectItem>
              </SelectContent>
            </Select>
          </div>
        </CardContent>
      </Card>

      {/* Categories Table */}
      <Card className="border-[#E2E8F0]">
        <CardHeader>
          <CardTitle>Listado de Categorías</CardTitle>
          <CardDescription>{categories.length} categorías registradas</CardDescription>
        </CardHeader>
        <CardContent>
          <Table className="data-table">
            <TableHeader>
              <TableRow>
                <TableHead>Color</TableHead>
                <TableHead>Nombre</TableHead>
                <TableHead>Tipo</TableHead>
                <TableHead>Subcategorías</TableHead>
                <TableHead className="text-center">Acciones</TableHead>
              </TableRow>
            </TableHeader>
            <TableBody>
              {categories.length === 0 ? (
                <TableRow>
                  <TableCell colSpan={5} className="text-center text-[#94A3B8] py-8">
                    No hay categorías registradas. Crea la primera.
                  </TableCell>
                </TableRow>
              ) : (
                categories.map((category) => (
                  <TableRow key={category.id} data-testid={`category-row-${category.id}`}>
                    <TableCell>
                      <div 
                        className="w-6 h-6 rounded-full"
                        style={{ backgroundColor: category.color }}
                      />
                    </TableCell>
                    <TableCell className="font-medium">{category.nombre}</TableCell>
                    <TableCell>
                      <span className={`text-xs px-2 py-1 rounded ${
                        category.tipo === 'ingreso' 
                          ? 'bg-green-100 text-green-800' 
                          : 'bg-red-100 text-red-800'
                      }`}>
                        {category.tipo === 'ingreso' ? '↑ Ingreso' : '↓ Egreso'}
                      </span>
                    </TableCell>
                    <TableCell>
                      <div className="space-y-1">
                        {category.subcategorias && category.subcategorias.length > 0 ? (
                          category.subcategorias.map((subcat) => (
                            <div key={subcat.id} className="flex items-center gap-2 text-sm">
                              <span className="text-[#64748B]">└</span>
                              <span>{subcat.nombre}</span>
                              <Button
                                variant="ghost"
                                size="sm"
                                className="h-5 w-5 p-0 text-red-500 hover:text-red-700"
                                onClick={() => handleDeleteSubcat(subcat.id)}
                                title="Eliminar subcategoría"
                              >
                                <Trash2 size={12} />
                              </Button>
                            </div>
                          ))
                        ) : (
                          <span className="text-xs text-[#94A3B8]">Sin subcategorías</span>
                        )}
                      </div>
                    </TableCell>
                    <TableCell>
                      <div className="flex justify-center gap-1">
                        <Button
                          variant="ghost"
                          size="sm"
                          onClick={() => openSubcatDialog(category)}
                          title="Agregar subcategoría"
                          data-testid={`add-subcategory-${category.id}`}
                        >
                          <FolderPlus size={16} className="text-[#0EA5E9]" />
                        </Button>
                        <Button
                          variant="ghost"
                          size="sm"
                          onClick={() => handleEdit(category)}
                          title="Editar categoría"
                          data-testid={`edit-category-${category.id}`}
                        >
                          <Edit2 size={16} className="text-[#64748B]" />
                        </Button>
                        <Button
                          variant="ghost"
                          size="sm"
                          onClick={() => handleDelete(category.id)}
                          title="Eliminar categoría"
                          data-testid={`delete-category-${category.id}`}
                        >
                          <Trash2 size={16} className="text-[#EF4444]" />
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

      {/* DIOT Info Card */}
      <Card className="border-[#0EA5E9] bg-sky-50">
        <CardHeader>
          <CardTitle className="text-[#0369A1] flex items-center gap-2">
            <Download size={20} />
            Exportación DIOT
          </CardTitle>
        </CardHeader>
        <CardContent className="text-sm text-[#64748B] space-y-2">
          <p>
            La <strong>DIOT (Declaración Informativa de Operaciones con Terceros)</strong> es una obligación fiscal en México.
          </p>
          <p>
            Para generar un archivo correcto, asegúrate de:
          </p>
          <ul className="list-disc list-inside space-y-1 ml-2">
            <li>Categorizar tus CFDIs de egreso (gastos)</li>
            <li>Verificar que los RFCs de tus proveedores estén correctos</li>
            <li>Revisar el estado de conciliación de cada CFDI</li>
          </ul>
          <p className="pt-2">
            El archivo CSV exportado incluye: Tipo de Tercero, RFC, Nombre, Montos, IVA y Estado de Conciliación.
          </p>
        </CardContent>
      </Card>
    </div>
  );
};

export default CategoriesModule;
