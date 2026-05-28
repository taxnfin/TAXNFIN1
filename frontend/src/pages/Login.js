import { useState, useEffect } from 'react';
import { Button } from '@/components/ui/button';
import { Input } from '@/components/ui/input';
import { Label } from '@/components/ui/label';
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card';
import { Tabs, TabsContent, TabsList, TabsTrigger } from '@/components/ui/tabs';
import axios from 'axios';
import { toast } from 'sonner';
import { LogIn, Building2, ArrowLeft, Mail } from 'lucide-react';

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

  // Forgot-password state
  const [forgotMode, setForgotMode] = useState(false);
  const [forgotEmail, setForgotEmail] = useState('');
  const [forgotLoading, setForgotLoading] = useState(false);
  const [forgotSent, setForgotSent] = useState(false);

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

  const handleForgotPassword = async (e) => {
    e.preventDefault();
    setForgotLoading(true);
    try {
      await axios.post(`${API}/auth/forgot-password`, { email: forgotEmail });
      setForgotSent(true);
    } catch (error) {
      toast.error('Error al enviar instrucciones. Intenta de nuevo.');
    } finally {
      setForgotLoading(false);
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
              {!forgotMode ? (
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
                  <div className="text-center">
                    <button
                      type="button"
                      data-testid="forgot-password-link"
                      onClick={() => { setForgotMode(true); setForgotSent(false); setForgotEmail(''); }}
                      className="text-sm text-slate-500 hover:text-[#0F172A] underline underline-offset-2 transition-colors"
                    >
                      ¿Olvidaste tu contraseña?
                    </button>
                  </div>
                </form>
              ) : (
                <div className="space-y-4" data-testid="forgot-password-panel">
                  {!forgotSent ? (
                    <form onSubmit={handleForgotPassword} className="space-y-4">
                      <div className="space-y-1">
                        <p className="text-sm text-slate-600">
                          Ingresa tu email y te enviaremos instrucciones para restablecer tu contraseña.
                        </p>
                      </div>
                      <div className="space-y-2">
                        <Label htmlFor="forgot-email">Email</Label>
                        <Input
                          id="forgot-email"
                          data-testid="forgot-email-input"
                          type="email"
                          placeholder="tu@email.com"
                          value={forgotEmail}
                          onChange={(e) => setForgotEmail(e.target.value)}
                          required
                          autoFocus
                        />
                      </div>
                      <Button
                        type="submit"
                        data-testid="forgot-submit-button"
                        className="w-full bg-[#0F172A] hover:bg-[#1E293B] gap-2"
                        disabled={forgotLoading}
                      >
                        <Mail size={16} />
                        {forgotLoading ? 'Enviando...' : 'Enviar instrucciones'}
                      </Button>
                      <div className="text-center">
                        <button
                          type="button"
                          onClick={() => setForgotMode(false)}
                          className="text-sm text-slate-500 hover:text-[#0F172A] flex items-center gap-1 mx-auto transition-colors"
                        >
                          <ArrowLeft size={14} /> Volver al inicio de sesión
                        </button>
                      </div>
                    </form>
                  ) : (
                    <div className="space-y-4 py-2" data-testid="forgot-sent-message">
                      <div className="rounded-md bg-emerald-50 border border-emerald-200 p-4 text-center">
                        <p className="text-sm font-medium text-emerald-800">
                          Si el email existe en nuestro sistema, recibirás las instrucciones en breve.
                        </p>
                        <p className="text-xs text-emerald-600 mt-1">Revisa también tu carpeta de spam.</p>
                      </div>
                      <div className="text-center">
                        <button
                          type="button"
                          onClick={() => { setForgotMode(false); setForgotSent(false); }}
                          className="text-sm text-slate-500 hover:text-[#0F172A] flex items-center gap-1 mx-auto transition-colors"
                        >
                          <ArrowLeft size={14} /> Volver al inicio de sesión
                        </button>
                      </div>
                    </div>
                  )}
                </div>
              )}
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
