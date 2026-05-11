import { useState, useEffect } from 'react';
import { useNavigate } from 'react-router-dom';
import api from '@/api/axios';
import { toast } from 'sonner';
import { Check, Zap, Building2, ArrowRight, Shield, Clock } from 'lucide-react';

const PLANS = [
  {
    id: 'basic',
    name: 'Basic',
    price: 890,
    maxEmpresas: 1,
    badge: null,
    color: '#2ABFA3',
    features: [
      'Dashboard + Cashflow 13 semanas',
      'Cobranza y Pagos',
      'Aging CxC / CxP',
      'SAT y Fiscal (CFDIs)',
      'Importación Contalink / Alegra',
      'Reporte Board PDF',
      'Soporte por email',
    ],
    notIncluded: [
      'IA Ejecutiva',
      'Múltiples empresas',
      'Métricas financieras avanzadas',
    ],
  },
  {
    id: 'pro',
    name: 'Pro',
    price: 1900,
    maxEmpresas: 5,
    badge: 'Más popular',
    color: '#6366F1',
    features: [
      'Todo lo de Basic',
      'Hasta 5 empresas (modo despacho)',
      'IA Ejecutiva',
      'Métricas DuPont, ROE, EBITDA',
      'Decisiones y Alertas automáticas',
      'Escenarios what-if',
      'Estados Financieros completos',
      'TaxnFin Insights newsletter',
      'Soporte prioritario',
    ],
    notIncluded: [],
  },
];

const PricingPage = ({ user }) => {
  const navigate = useNavigate();
  const [subscription, setSubscription] = useState(null);
  const [loading, setLoading] = useState(true);
  const [starting, setStarting] = useState(null);
  const [paymentMethod, setPaymentMethod] = useState('card');
  const [showCheckout, setShowCheckout] = useState(false);
  const [selectedPlan, setSelectedPlan] = useState(null);
  const [cardToken, setCardToken] = useState('');
  const [processingPayment, setProcessingPayment] = useState(false);
  const [speiData, setSpeiData] = useState(null);

  useEffect(() => {
    loadSubscription();
  }, []);

  const loadSubscription = async () => {
    try {
      const res = await api.get('/billing/subscription/status');
      setSubscription(res.data);
    } catch {}
    finally { setLoading(false); }
  };

  const handleStartTrial = async (planId) => {
    if (!user) { navigate('/login'); return; }
    setStarting(planId);
    try {
      const res = await api.post('/billing/trial/start', { plan_id: planId });
      toast.success(res.data.message);
      await loadSubscription();
    } catch (err) {
      toast.error(err.response?.data?.detail || 'Error iniciando trial');
    } finally { setStarting(null); }
  };

  const handleSelectPlan = (plan) => {
    if (!user) { navigate('/login'); return; }
    setSelectedPlan(plan);
    setShowCheckout(true);
    setSpeiData(null);
  };

  const handlePayment = async () => {
    setProcessingPayment(true);
    try {
      const res = await api.post('/billing/subscribe', {
        plan_id: selectedPlan.id,
        token_id: paymentMethod === 'card' ? cardToken : '',
        payment_method: paymentMethod,
      });
      if (paymentMethod === 'spei') {
        setSpeiData(res.data.spei);
      } else {
        toast.success(res.data.message);
        setShowCheckout(false);
        await loadSubscription();
        navigate('/');
      }
    } catch (err) {
      toast.error(err.response?.data?.detail || 'Error procesando pago');
    } finally { setProcessingPayment(false); }
  };

  const getStatusBanner = () => {
    if (!subscription || subscription.status === 'none') return null;
    const colors = {
      trialing:     { bg: '#E0F2FE', text: '#0369A1', icon: Clock },
      active:       { bg: '#DCFCE7', text: '#15803D', icon: Check },
      trial_expired:{ bg: '#FEF3C7', text: '#92400E', icon: Shield },
      past_due:     { bg: '#FEE2E2', text: '#991B1B', icon: Shield },
      canceled:     { bg: '#F1F5F9', text: '#475569', icon: Shield },
    };
    const cfg = colors[subscription.status] || colors.canceled;
    const Icon = cfg.icon;
    const messages = {
      trialing:      `Trial activo — ${subscription.days_left} días restantes · Plan ${subscription.plan_name}`,
      active:        `Suscripción activa · Plan ${subscription.plan_name} · Renueva en ${subscription.days_left} días`,
      trial_expired: `Tu trial venció — activa tu suscripción para continuar`,
      past_due:      `Pago pendiente — actualiza tu método de pago`,
      canceled:      `Suscripción cancelada · Acceso hasta fin del período`,
    };
    return (
      <div style={{ background: cfg.bg, color: cfg.text }} className="flex items-center gap-2 px-4 py-3 rounded-xl mb-8 text-sm font-medium">
        <Icon className="w-4 h-4 flex-shrink-0" />
        {messages[subscription.status]}
      </div>
    );
  };

  if (loading) return <div className="p-8 text-center text-gray-400">Cargando...</div>;

  return (
    <div className="min-h-screen bg-[#0E1628] text-white py-16 px-4">
      <div className="max-w-4xl mx-auto">

        {/* Header */}
        <div className="text-center mb-12">
          <div className="inline-flex items-center gap-2 bg-[#2ABFA320] border border-[#2ABFA340] text-[#2ABFA3] px-4 py-1.5 rounded-full text-xs font-semibold uppercase tracking-wider mb-6">
            <Zap className="w-3.5 h-3.5" /> Planes TaxnFin
          </div>
          <h1 className="text-4xl font-bold mb-4">
            Elige tu plan
          </h1>
          <p className="text-gray-400 text-lg">
            14 días gratis sin tarjeta. Cancela cuando quieras.
          </p>
        </div>

        {/* Status Banner */}
        {getStatusBanner()}

        {/* Plans Grid */}
        <div className="grid grid-cols-1 md:grid-cols-2 gap-6 mb-12">
          {PLANS.map(plan => {
            const isCurrentPlan = subscription?.plan_id === plan.id && subscription?.status === 'active';
            const isTrialing    = subscription?.plan_id === plan.id && subscription?.status === 'trialing';
            const hasAnyPlan    = subscription && !['none', 'trial_expired', 'canceled'].includes(subscription.status);

            return (
              <div
                key={plan.id}
                className="relative rounded-2xl border overflow-hidden"
                style={{
                  borderColor: plan.badge ? plan.color : 'rgba(255,255,255,0.1)',
                  background: plan.badge ? `linear-gradient(135deg, rgba(99,102,241,0.08), rgba(14,22,40,0.9))` : 'rgba(22,32,64,0.5)',
                }}
              >
                {plan.badge && (
                  <div className="absolute top-4 right-4 text-xs font-bold px-3 py-1 rounded-full"
                    style={{ background: plan.color, color: '#fff' }}>
                    {plan.badge}
                  </div>
                )}

                <div className="p-7">
                  {/* Plan name & price */}
                  <div className="mb-6">
                    <div className="flex items-center gap-2 mb-3">
                      <Building2 className="w-5 h-5" style={{ color: plan.color }} />
                      <span className="font-bold text-lg">{plan.name}</span>
                    </div>
                    <div className="flex items-end gap-2">
                      <span className="text-4xl font-bold">${plan.price.toLocaleString()}</span>
                      <span className="text-gray-400 mb-1">MXN/mes</span>
                    </div>
                    <p className="text-xs text-gray-500 mt-1">
                      Hasta {plan.maxEmpresas} {plan.maxEmpresas === 1 ? 'empresa' : 'empresas'}
                    </p>
                  </div>

                  {/* Features */}
                  <ul className="space-y-2.5 mb-7">
                    {plan.features.map(f => (
                      <li key={f} className="flex items-start gap-2.5 text-sm text-gray-300">
                        <Check className="w-4 h-4 flex-shrink-0 mt-0.5" style={{ color: plan.color }} />
                        {f}
                      </li>
                    ))}
                    {plan.notIncluded.map(f => (
                      <li key={f} className="flex items-start gap-2.5 text-sm text-gray-600 line-through">
                        <span className="w-4 h-4 flex-shrink-0 mt-0.5 text-gray-700">✕</span>
                        {f}
                      </li>
                    ))}
                  </ul>

                  {/* CTA */}
                  {isCurrentPlan ? (
                    <div className="w-full py-3 rounded-xl text-center text-sm font-semibold bg-green-900/30 text-green-400 border border-green-800">
                      ✓ Plan activo
                    </div>
                  ) : isTrialing ? (
                    <div className="space-y-2">
                      <div className="w-full py-3 rounded-xl text-center text-sm font-semibold bg-blue-900/30 text-blue-400 border border-blue-800">
                        Trial activo — {subscription.days_left} días
                      </div>
                      <button
                        onClick={() => handleSelectPlan(plan)}
                        className="w-full py-3 rounded-xl text-sm font-semibold border transition-all"
                        style={{ borderColor: plan.color, color: plan.color }}
                      >
                        Activar ahora con pago
                      </button>
                    </div>
                  ) : subscription?.status === 'none' || !subscription ? (
                    <button
                      onClick={() => handleStartTrial(plan.id)}
                      disabled={starting === plan.id}
                      className="w-full py-3 rounded-xl text-sm font-bold transition-all flex items-center justify-center gap-2"
                      style={{ background: plan.color, color: plan.id === 'basic' ? '#0E1628' : '#fff' }}
                    >
                      {starting === plan.id ? 'Iniciando...' : (
                        <><span>Iniciar trial gratis 14 días</span><ArrowRight className="w-4 h-4" /></>
                      )}
                    </button>
                  ) : (
                    <button
                      onClick={() => handleSelectPlan(plan)}
                      className="w-full py-3 rounded-xl text-sm font-bold transition-all"
                      style={{ background: plan.color, color: plan.id === 'basic' ? '#0E1628' : '#fff' }}
                    >
                      Cambiar a {plan.name}
                    </button>
                  )}
                </div>
              </div>
            );
          })}
        </div>

        {/* Trust badges */}
        <div className="flex items-center justify-center gap-8 text-xs text-gray-500 flex-wrap">
          <span className="flex items-center gap-1.5"><Shield className="w-3.5 h-3.5 text-[#2ABFA3]" /> Pago seguro con Conekta</span>
          <span className="flex items-center gap-1.5"><Check className="w-3.5 h-3.5 text-[#2ABFA3]" /> Sin permanencia</span>
          <span className="flex items-center gap-1.5"><Clock className="w-3.5 h-3.5 text-[#2ABFA3]" /> 14 días gratis</span>
          <span className="flex items-center gap-1.5"><Zap className="w-3.5 h-3.5 text-[#2ABFA3]" /> SPEI y tarjeta</span>
        </div>
      </div>

      {/* Checkout Modal */}
      {showCheckout && selectedPlan && (
        <div className="fixed inset-0 bg-black/70 backdrop-blur-sm z-50 flex items-center justify-center p-4">
          <div className="bg-[#162040] border border-[#2ABFA320] rounded-2xl w-full max-w-md p-8">

            {speiData ? (
              // SPEI instructions
              <div>
                <h2 className="text-xl font-bold mb-2">Transferencia SPEI</h2>
                <p className="text-gray-400 text-sm mb-6">Realiza la transferencia con los siguientes datos. Tu cuenta se activa automáticamente.</p>
                <div className="space-y-3 bg-[#0E1628] rounded-xl p-5 mb-6">
                  <div className="flex justify-between text-sm">
                    <span className="text-gray-400">CLABE</span>
                    <span className="font-mono font-bold text-[#2ABFA3] text-xs">{speiData.clabe}</span>
                  </div>
                  <div className="flex justify-between text-sm">
                    <span className="text-gray-400">Banco</span>
                    <span className="font-semibold">{speiData.bank}</span>
                  </div>
                  <div className="flex justify-between text-sm">
                    <span className="text-gray-400">Monto</span>
                    <span className="font-bold text-white">${speiData.amount?.toLocaleString()} MXN</span>
                  </div>
                  <div className="flex justify-between text-sm">
                    <span className="text-gray-400">Referencia</span>
                    <span className="font-mono text-xs text-gray-300">{speiData.reference}</span>
                  </div>
                  <div className="flex justify-between text-sm">
                    <span className="text-gray-400">Vence</span>
                    <span className="text-yellow-400 text-xs">{new Date(speiData.expires_at).toLocaleDateString('es-MX')}</span>
                  </div>
                </div>
                <button
                  onClick={() => { setShowCheckout(false); navigate('/'); }}
                  className="w-full py-3 rounded-xl font-bold text-[#0E1628]"
                  style={{ background: '#2ABFA3' }}
                >
                  Entendido, haré la transferencia
                </button>
              </div>
            ) : (
              // Payment form
              <div>
                <div className="flex items-center justify-between mb-6">
                  <div>
                    <h2 className="text-xl font-bold">Activar {selectedPlan.name}</h2>
                    <p className="text-gray-400 text-sm">${selectedPlan.price.toLocaleString()} MXN/mes</p>
                  </div>
                  <button onClick={() => setShowCheckout(false)} className="text-gray-500 hover:text-white text-xl">✕</button>
                </div>

                {/* Payment method selector */}
                <div className="flex gap-3 mb-6">
                  {['card', 'spei'].map(m => (
                    <button
                      key={m}
                      onClick={() => setPaymentMethod(m)}
                      className="flex-1 py-2.5 rounded-xl text-sm font-semibold border transition-all"
                      style={{
                        borderColor: paymentMethod === m ? '#2ABFA3' : 'rgba(255,255,255,0.1)',
                        background:  paymentMethod === m ? 'rgba(42,191,163,0.1)' : 'transparent',
                        color:       paymentMethod === m ? '#2ABFA3' : '#94A3B8',
                      }}
                    >
                      {m === 'card' ? '💳 Tarjeta' : '🏦 SPEI'}
                    </button>
                  ))}
                </div>

                {paymentMethod === 'card' ? (
                  <div className="space-y-4 mb-6">
                    <p className="text-xs text-gray-400 bg-[#0E1628] rounded-lg p-3">
                      Para tarjeta necesitas integrar <strong>Conekta.js</strong> en el frontend para tokenizar el número de tarjeta de forma segura. Una vez que tengas tu API key de Conekta, lo integramos en 30 minutos.
                    </p>
                    <input
                      placeholder="Token de tarjeta (desde Conekta.js)"
                      value={cardToken}
                      onChange={e => setCardToken(e.target.value)}
                      className="w-full bg-[#0E1628] border border-[#2ABFA320] rounded-xl px-4 py-3 text-sm text-white placeholder-gray-600 outline-none focus:border-[#2ABFA3]"
                    />
                  </div>
                ) : (
                  <div className="mb-6 bg-[#0E1628] rounded-xl p-4 text-sm text-gray-400">
                    Se generará una CLABE SPEI. Transfiere el monto y tu cuenta se activa automáticamente en minutos.
                  </div>
                )}

                {/* Summary */}
                <div className="bg-[#0E1628] rounded-xl p-4 mb-6 space-y-2 text-sm">
                  <div className="flex justify-between"><span className="text-gray-400">Plan</span><span>{selectedPlan.name}</span></div>
                  <div className="flex justify-between"><span className="text-gray-400">Ciclo</span><span>Mensual</span></div>
                  <div className="flex justify-between font-bold border-t border-gray-700 pt-2 mt-2">
                    <span>Total</span>
                    <span className="text-[#2ABFA3]">${selectedPlan.price.toLocaleString()} MXN</span>
                  </div>
                </div>

                <button
                  onClick={handlePayment}
                  disabled={processingPayment || (paymentMethod === 'card' && !cardToken)}
                  className="w-full py-3 rounded-xl font-bold text-[#0E1628] disabled:opacity-50 transition-all"
                  style={{ background: '#2ABFA3' }}
                >
                  {processingPayment ? 'Procesando...' : paymentMethod === 'card' ? 'Pagar con tarjeta' : 'Generar CLABE SPEI'}
                </button>

                <p className="text-center text-xs text-gray-600 mt-4">
                  🔒 Pagos seguros con Conekta · Sin permanencia
                </p>
              </div>
            )}
          </div>
        </div>
      )}
    </div>
  );
};

export default PricingPage;
