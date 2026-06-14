export const getERPEndpoints = () => {
  try {
    const company = JSON.parse(localStorage.getItem('selectedCompany') || '{}');
    const usaAlegra = company.alegra_connected === true;
    return {
      usaAlegra,
      cxcEndpoint: usaAlegra ? '/alegra/cxc' : '/contalink/cxc',
      cxpEndpoint: usaAlegra ? '/alegra/cxp' : '/contalink/cxp',
      agingSummaryEndpoint: usaAlegra ? '/alegra/cxc-cxp-summary' : '/contalink/aging-summary',
      cxcCxpSummaryEndpoint: usaAlegra ? '/alegra/cxc-cxp-summary' : '/contalink/cxc-cxp-summary',
    };
  } catch {
    return {
      usaAlegra: false,
      cxcEndpoint: '/contalink/cxc',
      cxpEndpoint: '/contalink/cxp',
      agingSummaryEndpoint: '/contalink/aging-summary',
      cxcCxpSummaryEndpoint: '/contalink/cxc-cxp-summary',
    };
  }
};
