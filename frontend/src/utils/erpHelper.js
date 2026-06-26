export const getERPEndpoints = () => {
  try {
    const company = JSON.parse(localStorage.getItem('selectedCompany') || '{}');

    // Prioridad: campo erp explícito → alegra_connected → default contalink
    const erp = company.erp
      || (company.alegra_connected === true ? 'alegra' : 'contalink');

    const usaAlegra    = erp === 'alegra';
    const usaContalink = erp === 'contalink';

    return {
      erp,
      usaAlegra,
      usaContalink,
      cxcEndpoint:          usaAlegra ? '/alegra/cxc'              : '/contalink/cxc',
      cxpEndpoint:          usaAlegra ? '/alegra/cxp'              : '/contalink/cxp',
      agingSummaryEndpoint: usaAlegra ? '/alegra/cxc-cxp-summary'  : '/contalink/aging-summary',
      cxcCxpSummaryEndpoint:usaAlegra ? '/alegra/cxc-cxp-summary'  : '/contalink/cxc-cxp-summary',
    };
  } catch {
    return {
      erp: 'contalink',
      usaAlegra: false,
      usaContalink: true,
      cxcEndpoint:           '/contalink/cxc',
      cxpEndpoint:           '/contalink/cxp',
      agingSummaryEndpoint:  '/contalink/aging-summary',
      cxcCxpSummaryEndpoint: '/contalink/cxc-cxp-summary',
    };
  }
};
