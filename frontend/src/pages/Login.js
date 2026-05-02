import { useState, useEffect } from 'react';
import { Button } from '@/components/ui/button';
import { Input } from '@/components/ui/input';
import { Label } from '@/components/ui/label';
import { Card, CardContent, CardDescription, CardFooter, CardHeader, CardTitle } from '@/components/ui/card';
import { Tabs, TabsContent, TabsList, TabsTrigger } from '@/components/ui/tabs';
import axios from 'axios';
import { toast } from 'sonner';
import { LogIn, Building2 } from 'lucide-react';

const BACKEND_URL = process.env.REACT_APP_BACKEND_URL;
const API = `${BACKEND_URL}/api`;

const Login = ({ onLogin }) => {
  const [loginData, setLoginData] = useState({ email: '', password: '' });
  const [registerData, setRegisterData] = useState({ 
    email: '', 
    password: '', 
    nombre: '',
    company_name: '',
    company_rfc: ''
  });
  const [loading, setLoading] = useState(false);
  const [auth0Loading, setAuth0Loading] = useState(false);
  const [auth0Config, setAuth0Config] = useState(null);

  useEffect(() => {
    loadAuth0Config();
  }, []);

  const loadAuth0Config = async () => {
    try {
      const response = await axios.get(`${API}/auth/auth0/config`);
      if (response.data.enabled) {
        setAuth0Config(response.data);
      }
    } catch (error) {
      console.log('Auth0 not configured');
    }
  };

  const handleAuth0Login = async () => {
    if (!auth0Config) return;
    
    setAuth0Loading(true);
    try {
      const redirectUri = `${window.location.origin}/auth/callback`;
      const response = await axios.get(`${API}/auth/auth0/login-url`, {
        params: { redirect_uri: redirectUri }
      });
      
      // Store state for CSRF protection
      sessionStorage.setItem('auth0_state', response.data.state);
      
      // Redirect to Auth0
      window.location.href = response.data.login_url;
    } catch (error) {
      toast.error('Error iniciando Auth0');
      setAuth0Loading(false);
    }
  };

  const handleLogin = async (e) => {
    e.preventDefault();
    setLoading(true);
    try {
      const response = await axios.post(`${API}/auth/login`, loginData);
      toast.success('Inicio de sesión exitoso');
      onLogin(response.data.user, response.data.access_token);
    } catch (error) {
      toast.error(error.response?.data?.detail || 'Error al iniciar sesión');
    } finally {
      setLoading(false);
    }
  };

  const handleRegister = async (e) => {
    e.preventDefault();
    setLoading(true);
    try {
      await axios.post(`${API}/auth/register`, registerData);
      toast.success('Registro exitoso. Ahora puedes iniciar sesión.');
      setRegisterData({ email: '', password: '', nombre: '', company_name: '', company_rfc: '' });
    } catch (error) {
      toast.error(error.response?.data?.detail || 'Error al registrar');
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
        backgroundPosition: 'center'
      }}
    >
      <div className="absolute inset-0 bg-[#0F172A]/60"></div>
      
      <Card className="w-full max-w-md relative z-10 border-[#CBD5E1] shadow-lg" data-testid="login-card">
        <CardHeader className="space-y-1">
          <CardTitle className="text-2xl font-bold" style={{fontFamily: 'Manrope'}}>TaxnFin Cashflow</CardTitle>
          <CardDescription>Gestión financiera y fiscal empresarial</CardDescription>
        </CardHeader>
        <CardContent>
          {/* Auth0 Button */}
          {auth0Config && (
            <div className="mb-6">
              <Button 
                onClick={handleAuth0Login}
                disabled={auth0Loading}
                className="w-full bg-gradient-to-r from-blue-600 to-indigo-600 hover:from-blue-700 hover:to-indigo-700 gap-2 h-11"
                data-testid="auth0-login-button"
              >
                <Building2 size={18} />
                {auth0Loading ? 'Conectando...' : 'Iniciar con Cuenta Empresarial'}
              </Button>
              <div className="relative my-4">
                <div className="absolute inset-0 flex items-center">
                  <div className="w-full border-t border-gray-200"></div>
                </div>
                <div className="relative flex justify-center text-sm">
                  <span className="px-2 bg-white text-gray-500">o continúa con email</span>
                </div>
              </div>
            </div>
          )}

          <Tabs defaultValue="login" className="w-full">
            <TabsList className="grid w-full grid-cols-2">
              <TabsTrigger value="login" data-testid="login-tab">Iniciar Sesión</TabsTrigger>
              <TabsTrigger value="register" data-testid="register-tab">Registrar</TabsTrigger>
            </TabsList>
            
            <TabsContent value="login">
              <form onSubmit={handleLogin} className="space-y-4">
                <div className="space-y-2">
                  <Label htmlFor="login-email">Email</Label>
                  <Input
                    id="login-email"
                    data-testid="login-email-input"
                    type="email"
                    placeholder="tu@email.com"
                    value={loginData.email}
                    onChange={(e) => setLoginData({ ...loginData, email: e.target.value })}
                    required
                  />
                </div>
                <div className="space-y-2">
                  <Label htmlFor="login-password">Contraseña</Label>
                  <Input
                    id="login-password"
                    data-testid="login-password-input"
                    type="password"
                    value={loginData.password}
                    onChange={(e) => setLoginData({ ...loginData, password: e.target.value })}
                    required
                  />
                </div>
                <Button 
                  type="submit" 
                  data-testid="login-submit-button"
                  className="w-full bg-[#0F172A] hover:bg-[#1E293B] gap-2" 
                  disabled={loading}
                >
                  <LogIn size={16} />
                  {loading ? 'Iniciando...' : 'Iniciar Sesión'}
                </Button>
              </form>
            </TabsContent>
            
            <TabsContent value="register">
              <form onSubmit={handleRegister} className="space-y-4">
                <div className="space-y-2">
                  <Label htmlFor="register-name">Nombre</Label>
                  <Input
                    id="register-name"
                    data-testid="register-name-input"
                    type="text"
                    placeholder="Tu nombre"
                    value={registerData.nombre}
                    onChange={(e) => setRegisterData({ ...registerData, nombre: e.target.value })}
                    required
                  />
                </div>
                <div className="space-y-2">
                  <Label htmlFor="register-email">Email</Label>
                  <Input
                    id="register-email"
                    data-testid="register-email-input"
                    type="email"
                    placeholder="tu@email.com"
                    value={registerData.email}
                    onChange={(e) => setRegisterData({ ...registerData, email: e.target.value })}
                    required
                  />
                </div>
                <div className="space-y-2">
                  <Label htmlFor="register-password">Contraseña</Label>
                  <Input
                    id="register-password"
                    data-testid="register-password-input"
                    type="password"
                    value={registerData.password}
                    onChange={(e) => setRegisterData({ ...registerData, password: e.target.value })}
                    required
                  />
                </div>
                <div className="space-y-2">
                  <Label htmlFor="register-company">Nombre de la Empresa</Label>
                  <Input
                    id="register-company"
                    data-testid="register-company-input"
                    type="text"
                    placeholder="Ej. Mi Empresa SA de CV"
                    value={registerData.company_name}
                    onChange={(e) => setRegisterData({ ...registerData, company_name: e.target.value })}
                    required
                  />
                </div>
                <div className="space-y-2">
                  <Label htmlFor="register-rfc">RFC <span className="text-xs text-gray-400">(opcional)</span></Label>
                  <Input
                    id="register-rfc"
                    data-testid="register-rfc-input"
                    type="text"
                    placeholder="RFC de tu empresa"
                    value={registerData.company_rfc}
                    onChange={(e) => setRegisterData({ ...registerData, company_rfc: e.target.value.toUpperCase() })}
                  />
                </div>
                <Button 
                  type="submit" 
                  data-testid="register-submit-button"
                  className="w-full bg-[#0F172A] hover:bg-[#1E293B]" 
                  disabled={loading}
                >
                  {loading ? 'Registrando...' : 'Registrar'}
                </Button>
              </form>
            </TabsContent>
          </Tabs>
        </CardContent>
      </Card>
    </div>
  );
};

export default Login;
