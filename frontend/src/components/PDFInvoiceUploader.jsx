import React, { useState, useCallback } from 'react';
import { useDropzone } from 'react-dropzone';
import { 
  FileText, 
  Upload, 
  CheckCircle, 
  XCircle, 
  Loader2, 
  DollarSign,
  Building2,
  Calendar,
  Hash,
  ArrowDownCircle,
  ArrowUpCircle
} from 'lucide-react';
import { Dialog, DialogContent, DialogHeader, DialogTitle, DialogFooter } from '../components/ui/dialog';
import { Button } from '../components/ui/button';
import { Label } from '../components/ui/label';
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from '../components/ui/select';
import { Input } from '../components/ui/input';
import { toast } from 'sonner';

const API_URL = process.env.REACT_APP_BACKEND_URL || '';

const PDFInvoiceUploader = ({ 
  isOpen, 
  onClose, 
  onSuccess,
  categories = [],
  bankAccounts = []
}) => {
  const [extractedData, setExtractedData] = useState(null);
  const [isExtracting, setIsExtracting] = useState(false);
  const [isCreating, setIsCreating] = useState(false);
  const [selectedFile, setSelectedFile] = useState(null);
  const [categoryId, setCategoryId] = useState('');
  const [subcategoryId, setSubcategoryId] = useState('');
  const [bankAccountId, setBankAccountId] = useState('');
  const [notas, setNotas] = useState('');

  const onDrop = useCallback(async (acceptedFiles) => {
    const file = acceptedFiles[0];
    if (!file) return;

    if (!file.name.toLowerCase().endsWith('.pdf')) {
      toast.error('Solo se aceptan archivos PDF');
      return;
    }

    setSelectedFile(file);
    setIsExtracting(true);
    setExtractedData(null);

    try {
      const formData = new FormData();
      formData.append('file', file);

      const token = localStorage.getItem('token');
      const response = await fetch(`${API_URL}/api/pdf-invoices/extract`, {
        method: 'POST',
        headers: {
          'Authorization': `Bearer ${token}`
        },
        body: formData
      });

      const result = await response.json();

      if (result.success) {
        setExtractedData(result);
        
        // Show duplicate warning if applicable
        if (result.is_duplicate) {
          toast.warning(`⚠️ DUPLICADO: ${result.duplicate_message}`, {
            duration: 8000
          });
        } else {
          toast.success(result.message);
        }
      } else {
        toast.error(result.detail || 'Error al extraer datos del PDF');
      }
    } catch (error) {
      console.error('Error extracting PDF:', error);
      toast.error('Error al procesar el PDF');
    } finally {
      setIsExtracting(false);
    }
  }, []);

  const { getRootProps, getInputProps, isDragActive } = useDropzone({
    onDrop,
    accept: {
      'application/pdf': ['.pdf']
    },
    maxFiles: 1,
    disabled: isExtracting
  });

  const handleConfirm = async () => {
    if (!extractedData?.data) return;

    setIsCreating(true);

    try {
      const token = localStorage.getItem('token');
      const response = await fetch(`${API_URL}/api/pdf-invoices/confirm`, {
        method: 'POST',
        headers: {
          'Authorization': `Bearer ${token}`,
          'Content-Type': 'application/json'
        },
        body: JSON.stringify({
          extracted_data: extractedData.data,
          category_id: categoryId || null,
          subcategory_id: subcategoryId || null,
          bank_account_id: bankAccountId || null,
          notas: notas || null
        })
      });

      const result = await response.json();

      if (result.success) {
        toast.success(result.message);
        onSuccess && onSuccess(result.payment);
        handleClose();
      } else {
        toast.error(result.detail || 'Error al crear el registro');
      }
    } catch (error) {
      console.error('Error creating payment:', error);
      toast.error('Error al crear el registro');
    } finally {
      setIsCreating(false);
    }
  };

  const handleClose = () => {
    setExtractedData(null);
    setSelectedFile(null);
    setCategoryId('');
    setSubcategoryId('');
    setBankAccountId('');
    setNotas('');
    onClose();
  };

  // Get subcategories for selected category
  const getSubcategories = () => {
    if (!categoryId) return [];
    const category = categories.find(c => c.id === categoryId);
    return category?.subcategorias?.filter(s => s.activo !== false) || [];
  };

  // Filter categories based on type (pago = egreso, cobro = ingreso)
  const getFilteredCategories = () => {
    if (!extractedData?.data) return categories;
    const tipo = extractedData.data.es_pago ? 'egreso' : 'ingreso';
    return categories.filter(c => c.tipo === tipo && c.activo !== false);
  };

  const formatCurrency = (amount, currency = 'MXN') => {
    return new Intl.NumberFormat('es-MX', {
      style: 'currency',
      currency: currency === 'USD' ? 'USD' : 'MXN',
      minimumFractionDigits: 2
    }).format(amount || 0);
  };

  return (
    <Dialog open={isOpen} onOpenChange={handleClose}>
      <DialogContent className="max-w-2xl max-h-[90vh] overflow-y-auto">
        <DialogHeader>
          <DialogTitle className="flex items-center gap-2">
            <FileText className="w-5 h-5" />
            Importar Factura PDF
          </DialogTitle>
        </DialogHeader>

        <div className="space-y-4">
          {/* Dropzone */}
          {!extractedData && (
            <div
              {...getRootProps()}
              className={`
                border-2 border-dashed rounded-lg p-8 text-center cursor-pointer transition-colors
                ${isDragActive ? 'border-blue-500 bg-blue-50' : 'border-gray-300 hover:border-gray-400'}
                ${isExtracting ? 'opacity-50 cursor-not-allowed' : ''}
              `}
            >
              <input {...getInputProps()} />
              {isExtracting ? (
                <div className="flex flex-col items-center gap-3">
                  <Loader2 className="w-12 h-12 text-blue-500 animate-spin" />
                  <p className="text-gray-600">Extrayendo datos del PDF...</p>
                  <p className="text-sm text-gray-400">Esto puede tomar unos segundos</p>
                </div>
              ) : (
                <div className="flex flex-col items-center gap-3">
                  <Upload className="w-12 h-12 text-gray-400" />
                  <p className="text-gray-600">
                    {isDragActive
                      ? 'Suelta el archivo aquí...'
                      : 'Arrastra un PDF aquí o haz clic para seleccionar'}
                  </p>
                  <p className="text-sm text-gray-400">Solo archivos PDF</p>
                </div>
              )}
            </div>
          )}

          {/* Extracted Data Preview */}
          {extractedData?.data && (
            <div className="space-y-4">
              {/* Type Badge */}
              <div className={`
                flex items-center gap-2 p-3 rounded-lg
                ${extractedData.data.es_pago 
                  ? 'bg-red-50 border border-red-200' 
                  : 'bg-green-50 border border-green-200'}
              `}>
                {extractedData.data.es_pago ? (
                  <>
                    <ArrowUpCircle className="w-6 h-6 text-red-600" />
                    <div>
                      <p className="font-semibold text-red-700">PAGO (Gasto/Compra)</p>
                      <p className="text-sm text-red-600">Factura de proveedor a pagar</p>
                    </div>
                  </>
                ) : (
                  <>
                    <ArrowDownCircle className="w-6 h-6 text-green-600" />
                    <div>
                      <p className="font-semibold text-green-700">COBRANZA (Ingreso/Venta)</p>
                      <p className="text-sm text-green-600">Factura a cliente por cobrar</p>
                    </div>
                  </>
                )}
              </div>

              {/* Invoice Details */}
              <div className="grid grid-cols-2 gap-4 p-4 bg-gray-50 rounded-lg">
                <div className="flex items-start gap-2">
                  <Building2 className="w-4 h-4 text-gray-500 mt-1" />
                  <div>
                    <p className="text-xs text-gray-500">
                      {extractedData.data.es_pago ? 'Proveedor' : 'Cliente'}
                    </p>
                    <p className="font-medium">{extractedData.tercero}</p>
                    <p className="text-xs text-gray-400">
                      RFC: {extractedData.data.es_pago 
                        ? extractedData.data.emisor_rfc 
                        : extractedData.data.receptor_rfc}
                    </p>
                  </div>
                </div>

                <div className="flex items-start gap-2">
                  <DollarSign className="w-4 h-4 text-gray-500 mt-1" />
                  <div>
                    <p className="text-xs text-gray-500">Total</p>
                    <p className="font-medium text-lg">
                      {formatCurrency(extractedData.data.total, extractedData.data.moneda)}
                    </p>
                    {extractedData.data.moneda === 'USD' && extractedData.data.tipo_cambio && (
                      <p className="text-xs text-gray-400">
                        TC: {extractedData.data.tipo_cambio}
                      </p>
                    )}
                  </div>
                </div>

                <div className="flex items-start gap-2">
                  <Hash className="w-4 h-4 text-gray-500 mt-1" />
                  <div>
                    <p className="text-xs text-gray-500">Folio</p>
                    <p className="font-medium">{extractedData.data.folio || 'N/A'}</p>
                  </div>
                </div>

                <div className="flex items-start gap-2">
                  <Calendar className="w-4 h-4 text-gray-500 mt-1" />
                  <div>
                    <p className="text-xs text-gray-500">Fecha</p>
                    <p className="font-medium">{extractedData.data.fecha || 'N/A'}</p>
                  </div>
                </div>

                <div className="col-span-2">
                  <p className="text-xs text-gray-500">Concepto</p>
                  <p className="font-medium text-sm">{extractedData.data.concepto || 'N/A'}</p>
                </div>

                {extractedData.data.subtotal && extractedData.data.iva && (
                  <div className="col-span-2 flex gap-4 text-sm">
                    <span className="text-gray-500">
                      Subtotal: {formatCurrency(extractedData.data.subtotal, extractedData.data.moneda)}
                    </span>
                    <span className="text-gray-500">
                      IVA: {formatCurrency(extractedData.data.iva, extractedData.data.moneda)}
                    </span>
                  </div>
                )}
              </div>

              {/* Category Selection */}
              <div className="grid grid-cols-2 gap-4">
                <div>
                  <Label>Categoría</Label>
                  <Select value={categoryId} onValueChange={(v) => {
                    setCategoryId(v);
                    setSubcategoryId('');
                  }}>
                    <SelectTrigger data-testid="pdf-categoria">
                      <SelectValue placeholder="Seleccionar categoría" />
                    </SelectTrigger>
                    <SelectContent>
                      {getFilteredCategories().map(cat => (
                        <SelectItem key={cat.id} value={cat.id}>{cat.nombre}</SelectItem>
                      ))}
                    </SelectContent>
                  </Select>
                </div>

                <div>
                  <Label>Subcategoría</Label>
                  <Select 
                    value={subcategoryId} 
                    onValueChange={setSubcategoryId}
                    disabled={!categoryId || getSubcategories().length === 0}
                  >
                    <SelectTrigger data-testid="pdf-subcategoria">
                      <SelectValue placeholder={categoryId ? "Seleccionar subcategoría" : "Primero selecciona categoría"} />
                    </SelectTrigger>
                    <SelectContent>
                      {getSubcategories().map(sub => (
                        <SelectItem key={sub.id} value={sub.id}>{sub.nombre}</SelectItem>
                      ))}
                    </SelectContent>
                  </Select>
                </div>
              </div>

              {/* Bank Account Selection */}
              <div>
                <Label>Cuenta Bancaria (opcional)</Label>
                <Select value={bankAccountId} onValueChange={setBankAccountId}>
                  <SelectTrigger data-testid="pdf-bank-account">
                    <SelectValue placeholder="Seleccionar cuenta" />
                  </SelectTrigger>
                  <SelectContent>
                    {bankAccounts.map(acc => (
                      <SelectItem key={acc.id} value={acc.id}>
                        <div className="flex items-center gap-2">
                          <span className="font-medium">{acc.banco}</span>
                          <span className="text-gray-500">-</span>
                          <span>{acc.nombre}</span>
                          <span className={`ml-1 text-xs px-1.5 py-0.5 rounded font-bold ${
                            acc.moneda === 'USD' ? 'bg-blue-100 text-blue-700' :
                            acc.moneda === 'EUR' ? 'bg-purple-100 text-purple-700' :
                            'bg-green-100 text-green-700'
                          }`}>
                            {acc.moneda}
                          </span>
                        </div>
                      </SelectItem>
                    ))}
                  </SelectContent>
                </Select>
              </div>

              {/* Notes */}
              <div>
                <Label>Notas (opcional)</Label>
                <Input
                  value={notas}
                  onChange={(e) => setNotas(e.target.value)}
                  placeholder="Agregar notas o comentarios..."
                  data-testid="pdf-notas"
                />
              </div>
            </div>
          )}
        </div>

        <DialogFooter className="flex gap-2">
          <Button variant="outline" onClick={handleClose}>
            Cancelar
          </Button>
          {extractedData?.data && (
            <Button 
              onClick={handleConfirm} 
              disabled={isCreating}
              className={extractedData.data.es_pago 
                ? 'bg-red-600 hover:bg-red-700' 
                : 'bg-green-600 hover:bg-green-700'}
            >
              {isCreating ? (
                <>
                  <Loader2 className="w-4 h-4 mr-2 animate-spin" />
                  Creando...
                </>
              ) : (
                <>
                  <CheckCircle className="w-4 h-4 mr-2" />
                  Crear {extractedData.data.es_pago ? 'Pago' : 'Cobranza'}
                </>
              )}
            </Button>
          )}
        </DialogFooter>
      </DialogContent>
    </Dialog>
  );
};

export default PDFInvoiceUploader;
