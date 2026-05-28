import { useState } from 'react';
import { useNavigate, useSearchParams } from 'react-router-dom';
import { Button } from '@/components/ui/button';
import { Input } from '@/components/ui/input';
import { Label } from '@/components/ui/label';
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card';
import axios from 'axios';
import { toast } from 'sonner';
import { KeyRound, LogIn } from 'lucide-react';

const BACKEND_URL = process.env.REACT_APP_BACKEND_URL;
const API = `${BACKEND_URL}/api`;

const ResetPassword = () => {
  const [searchParams] = useSearchParams();
  const navigate = useNavigate();
  const token = searchParams.get('token') || '';

  const [newPassword, setNewPassword] = useState('');
  const [confirmPassword, setConfirmPassword] = useState('');
  const [loading, setLoading] = useState(false);
  const [success, setSuccess] = useState(false);

  const handleSubmit = async (e) => {
    e.preventDefault();

    if (newPassword.length < 8) {
      toast.error('La contraseña debe tener al menos 8 caracteres');
      return;
    }
    if (newPassword !== confirmPassword) {
      toast.error('Las contraseñas no coinciden');
      return;
    }

    setLoading(true);
    try {
      await axios.post(`${API}/auth/reset-password`, {
        token,
        new_password: newPassword,
      });
      setSuccess(true);
      toast.success('Contraseña actualizada correctamente');
      setTimeout(() => navigate('/login'), 2500);
    } catch (error) {
      toast.error(error.response?.data?.detail || 'El enlace es inválido o ha expirado');
    } finally {
      setLoading(false);
    }
  };

  return (
    <div
      className="min-h-screen flex items-center justify-center p-4"
      style={{
        backgroundImage: 'url(https://images.unsplash.com/photo-1748885107428-21dc225745eb?crop=entropy&cs=srgb&fm=jpg&q=85)',
        backgroundSize: 'cover',
        backgroundPosition: 'center',
      }}
    >
      <div className="absolute inset-0 bg-[#0F172A]/60" />

      <Card className="w-full max-w-md relative z-10 border-[#CBD5E1] shadow-lg" data-testid="reset-password-card">
        <CardHeader className="space-y-1">
          <CardTitle className="text-2xl font-bold" style={{ fontFamily: 'Manrope' }}>
            Nueva contraseña
          </CardTitle>
          <CardDescription>TaxnFin Cashflow — Restablecimiento de acceso</CardDescription>
        </CardHeader>

        <CardContent>
          {!token ? (
            <div className="space-y-4" data-testid="reset-invalid-token">
              <div className="rounded-md bg-red-50 border border-red-200 p-4 text-center">
                <p className="text-sm font-medium text-red-800">
                  Enlace inválido. Solicita uno nuevo desde la pantalla de inicio de sesión.
                </p>
              </div>
              <Button
                className="w-full bg-[#0F172A] hover:bg-[#1E293B] gap-2"
                onClick={() => navigate('/login')}
              >
                <LogIn size={16} /> Ir al login
              </Button>
            </div>
          ) : success ? (
            <div className="space-y-4" data-testid="reset-success-message">
              <div className="rounded-md bg-emerald-50 border border-emerald-200 p-4 text-center">
                <p className="text-sm font-medium text-emerald-800">
                  ¡Contraseña actualizada! Redirigiendo al login...
                </p>
              </div>
              <Button
                className="w-full bg-[#0F172A] hover:bg-[#1E293B] gap-2"
                onClick={() => navigate('/login')}
              >
                <LogIn size={16} /> Ir al login ahora
              </Button>
            </div>
          ) : (
            <form onSubmit={handleSubmit} className="space-y-4" data-testid="reset-password-form">
              <div className="space-y-2">
                <Label htmlFor="new-password">Nueva contraseña</Label>
                <Input
                  id="new-password"
                  data-testid="new-password-input"
                  type="password"
                  placeholder="Mínimo 8 caracteres"
                  value={newPassword}
                  onChange={(e) => setNewPassword(e.target.value)}
                  required
                  autoFocus
                  minLength={8}
                />
              </div>
              <div className="space-y-2">
                <Label htmlFor="confirm-password">Confirmar contraseña</Label>
                <Input
                  id="confirm-password"
                  data-testid="confirm-password-input"
                  type="password"
                  placeholder="Repite tu nueva contraseña"
                  value={confirmPassword}
                  onChange={(e) => setConfirmPassword(e.target.value)}
                  required
                  minLength={8}
                />
                {confirmPassword && newPassword !== confirmPassword && (
                  <p className="text-xs text-red-500" data-testid="password-mismatch-warning">
                    Las contraseñas no coinciden
                  </p>
                )}
              </div>
              <Button
                type="submit"
                data-testid="reset-submit-button"
                className="w-full bg-[#0F172A] hover:bg-[#1E293B] gap-2"
                disabled={loading || (confirmPassword.length > 0 && newPassword !== confirmPassword)}
              >
                <KeyRound size={16} />
                {loading ? 'Guardando...' : 'Establecer nueva contraseña'}
              </Button>
            </form>
          )}
        </CardContent>
      </Card>
    </div>
  );
};

export default ResetPassword;
