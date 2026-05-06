import { useState } from 'react';
import SATIntegration from '@/components/SATIntegration';
import AlegraIntegration from '@/components/AlegraIntegration';
import ContalinkIntegration from './ContalinkIntegration';
import { Building2, Cloud, Link2 } from 'lucide-react';

const TABS = [
  {
    key: 'sat',
    label: 'SAT (e.firma / FIEL)',
    icon: Cloud,
    color: 'text-blue-600',
    bg: 'bg-blue-50',
    border: 'border-blue-200',
    activeBg: 'bg-blue-600',
  },
  {
    key: 'alegra',
    label: 'Alegra',
    icon: Building2,
    color: 'text-purple-600',
    bg: 'bg-purple-50',
    border: 'border-purple-200',
    activeBg: 'bg-purple-600',
  },
  {
    key: 'contalink',
    label: 'Contalink',
    icon: Link2,
    color: 'text-blue-700',
    bg: 'bg-blue-50',
    border: 'border-blue-300',
    activeBg: 'bg-blue-700',
  },
];

const Integrations = () => {
  const [activeTab, setActiveTab] = useState('sat');

  return (
    <div className="p-8 space-y-6">
      {/* Header */}
      <div>
        <h1 className="text-4xl font-bold text-[#0F172A] mb-2" style={{ fontFamily: 'Manrope' }}>
          Integraciones
        </h1>
        <p className="text-[#64748B]">
          Conecta TaxnFin con tus herramientas contables y fiscales
        </p>
      </div>

      {/* Tab buttons */}
      <div className="flex gap-3 border-b border-gray-200 pb-0">
        {TABS.map(tab => {
          const Icon = tab.icon;
          const isActive = activeTab === tab.key;
          return (
            <button
              key={tab.key}
              onClick={() => setActiveTab(tab.key)}
              className={`flex items-center gap-2 px-5 py-3 text-sm font-medium rounded-t-lg border-b-2 transition-all ${
                isActive
                  ? `border-[#0F172A] text-[#0F172A] bg-white`
                  : `border-transparent text-[#64748B] hover:text-[#0F172A] hover:bg-gray-50`
              }`}
            >
              <Icon size={16} />
              {tab.label}
            </button>
          );
        })}
      </div>

      {/* Tab content */}
      <div className="mt-0">
        {activeTab === 'sat' && (
          <SATIntegration onSyncComplete={() => {}} />
        )}
        {activeTab === 'alegra' && (
          <AlegraIntegration />
        )}
        {activeTab === 'contalink' && (
          <ContalinkIntegration />
        )}
      </div>
    </div>
  );
};

export default Integrations;
