import React, { useState, useEffect } from 'react';
import { useParams, useNavigate } from 'react-router-dom';
import { Card, CardContent, CardHeader, CardTitle } from '../components/ui/card';
import { Button } from '../components/ui/button';
import { toast } from 'sonner';
import api from '../api/axios';
import {
  ArrowLeft, HelpCircle, Lightbulb, Star, Calculator, Link2,
  ChevronRight, ChevronDown, TrendingUp, TrendingDown, Building2,
  Monitor, ShoppingCart, Cpu, CreditCard, Megaphone, Activity,
  Quote
} from 'lucide-react';

// Comprehensive metric definitions with formulas, benchmarks, and industry data
const metricDefinitions = {
  // MARGINS
  gross_margin: {
    id: 'gross_margin',
    name: 'Margen Bruto',
    nameEn: 'Gross Margin',
    category: 'margins',
    question: '¿Qué tan rentable es el producto/servicio antes de gastos operativos?',
    whatMeasures: 'Mide el porcentaje de ingresos que queda después de deducir los costos directos de producción o venta (costo de ventas). Representa la eficiencia de la empresa para generar ganancias de sus operaciones principales.',
    reasoning: 'Un margen bruto alto indica que la empresa puede cubrir sus costos operativos y generar utilidades. Es fundamental para evaluar la competitividad de precios y la eficiencia en la cadena de suministro.',
    relevance: 'Clave para empresas manufactureras y comerciales. Permite comparar la eficiencia productiva entre competidores del mismo sector.',
    formula: {
      numerator: 'Utilidad Bruta',
      denominator: 'Ingresos Totales',
      expression: 'Margen Bruto = (Ingresos - Costo de Ventas) / Ingresos × 100',
      variables: ['Ingresos Totales', 'Costo de Ventas', 'Utilidad Bruta']
    },
    relatedMetrics: ['operating_margin', 'net_margin', 'ebitda_margin'],
    evaluation: [
      { level: 'Excelente', color: 'blue', range: '> 50%', description: 'Poder de precio excepcional, alta diferenciación del producto.' },
      { level: 'Bueno', color: 'green', range: '30 - 50%', description: 'Margen saludable que permite cubrir gastos operativos y generar utilidades.' },
      { level: 'Aceptable', color: 'yellow', range: '20 - 30%', description: 'Margen funcional pero con espacio limitado para errores.' },
      { level: 'Bajo', color: 'orange', range: '10 - 20%', description: 'Margen estrecho, requiere alto volumen para rentabilidad.' },
      { level: 'Crítico', color: 'red', range: '< 10%', description: 'Margen insuficiente, riesgo de pérdidas con cualquier aumento de costos.' }
    ],
    bestPerformers: [
      { industry: 'Software', icon: 'Monitor', typical: '70-85%' },
      { industry: 'Farmacéutica', icon: 'Activity', typical: '65-80%' },
      { industry: 'Tecnología', icon: 'Cpu', typical: '50-70%' },
      { industry: 'Consultoría', icon: 'Lightbulb', typical: '40-60%' },
    ],
    worstPerformers: [
      { industry: 'Retail/Comercio', icon: 'ShoppingCart', typical: '20-35%' },
      { industry: 'Distribución', icon: 'Building2', typical: '15-25%' },
      { industry: 'Supermercados', icon: 'ShoppingCart', typical: '25-30%' },
    ],
    expertQuote: {
      text: '"El margen bruto es el primer indicador de la salud financiera de un negocio. Sin un margen bruto adecuado, no hay modelo de negocio sostenible."',
      author: 'Warren Buffett',
      source: 'Berkshire Hathaway Annual Letter'
    }
  },
  
  // ROIC
  roic: {
    id: 'roic',
    name: 'ROIC',
    nameEn: 'Return on Invested Capital',
    category: 'returns',
    question: '¿Qué tan eficientemente genera retornos el capital invertido?',
    whatMeasures: 'Mide la rentabilidad obtenida sobre el capital total invertido en la empresa (deuda + capital propio). Indica qué tan bien la empresa convierte sus inversiones en ganancias.',
    reasoning: 'El ROIC es la métrica más completa para evaluar la creación de valor. Si el ROIC supera el costo de capital (WACC), la empresa está creando valor para los accionistas.',
    relevance: 'Esencial para decisiones de inversión y valoración de empresas. Permite comparar eficiencia de capital entre empresas de diferentes tamaños y sectores.',
    formula: {
      numerator: 'NOPAT',
      denominator: 'Capital Invertido',
      expression: 'ROIC = NOPAT / (Deuda + Capital Contable)',
      variables: ['NOPAT (Utilidad Operativa × (1 - Tasa Impuestos))', 'Deuda Total', 'Capital Contable']
    },
    relatedMetrics: ['roe', 'roa', 'roce'],
    evaluation: [
      { level: 'Excelente inversión', color: 'blue', range: '> 25%', description: 'Retorno excepcional, la empresa genera valor masivo por cada peso invertido.' },
      { level: 'Buena inversión', color: 'green', range: '15 - 25%', description: 'Retorno sólido sobre el nuevo capital, la empresa crece creando valor real.' },
      { level: 'Inversión aceptable', color: 'yellow', range: '8 - 15%', description: 'Retorno moderado, cubre el costo de capital con margen pequeño.' },
      { level: 'Inversión estrecha', color: 'orange', range: '5 - 8%', description: 'Apenas cubre el costo de capital, difícil crear valor.' },
      { level: 'Mala inversión', color: 'red', range: '< 5%', description: 'Destrucción de valor, el costo de capital supera los retornos.' }
    ],
    bestPerformers: [
      { industry: 'Software', icon: 'Monitor', typical: '25-40%' },
      { industry: 'Publicidad Digital', icon: 'Megaphone', typical: '20-35%' },
      { industry: 'Tecnología', icon: 'Cpu', typical: '15-30%' },
      { industry: 'E-Commerce', icon: 'ShoppingCart', typical: '15-25%' },
      { industry: 'Pagos', icon: 'CreditCard', typical: '15-25%' },
    ],
    worstPerformers: [
      { industry: 'Utilities', icon: 'Activity', typical: '5-8%' },
      { industry: 'Aerolíneas', icon: 'Building2', typical: '3-7%' },
      { industry: 'Retail Tradicional', icon: 'ShoppingCart', typical: '5-10%' },
    ],
    expertQuote: {
      text: '"El crecimiento solo crea valor cuando el retorno sobre el capital invertido es mayor que el costo de capital. Si el retorno es menor, crecer solo acelera la destrucción de valor."',
      author: 'Michael Mauboussin',
      source: 'Morgan Stanley IM / Consilience Energy'
    }
  },

  // ROE
  roe: {
    id: 'roe',
    name: 'ROE',
    nameEn: 'Return on Equity',
    category: 'returns',
    question: '¿Qué retorno genera la empresa para los accionistas?',
    whatMeasures: 'Mide la rentabilidad obtenida exclusivamente sobre el capital aportado por los accionistas. Indica cuánto gana la empresa por cada peso de inversión de los dueños.',
    reasoning: 'El ROE muestra la eficiencia con que la empresa usa el capital de los accionistas. Sin embargo, puede inflarse artificialmente con alto apalancamiento.',
    relevance: 'Fundamental para accionistas e inversionistas. Debe analizarse junto con el nivel de deuda para evitar confusiones.',
    formula: {
      numerator: 'Utilidad Neta',
      denominator: 'Capital Contable',
      expression: 'ROE = Utilidad Neta / Capital Contable × 100',
      variables: ['Utilidad Neta', 'Capital Contable Promedio']
    },
    relatedMetrics: ['roic', 'roa', 'dupont_analysis'],
    evaluation: [
      { level: 'Excelente', color: 'blue', range: '> 20%', description: 'Retorno excepcional para accionistas, alta creación de valor.' },
      { level: 'Bueno', color: 'green', range: '15 - 20%', description: 'Retorno sólido, supera la mayoría de alternativas de inversión.' },
      { level: 'Aceptable', color: 'yellow', range: '10 - 15%', description: 'Retorno moderado, comparable con el mercado.' },
      { level: 'Bajo', color: 'orange', range: '5 - 10%', description: 'Retorno pobre, mejor invertir en otras opciones.' },
      { level: 'Crítico', color: 'red', range: '< 5%', description: 'Retorno insuficiente, destruyendo valor del accionista.' }
    ],
    bestPerformers: [
      { industry: 'Tecnología', icon: 'Cpu', typical: '20-35%' },
      { industry: 'Fintech', icon: 'CreditCard', typical: '18-30%' },
      { industry: 'Software SaaS', icon: 'Monitor', typical: '15-25%' },
    ],
    worstPerformers: [
      { industry: 'Construcción', icon: 'Building2', typical: '8-12%' },
      { industry: 'Manufactura', icon: 'Activity', typical: '10-15%' },
    ],
    expertQuote: {
      text: '"El ROE alto sostenido es el santo grial de las finanzas corporativas. Pero cuidado: un ROE alto con mucha deuda es un castillo de naipes."',
      author: 'Peter Lynch',
      source: 'One Up on Wall Street'
    }
  },

  // ROA
  roa: {
    id: 'roa',
    name: 'ROA',
    nameEn: 'Return on Assets',
    category: 'returns',
    question: '¿Qué tan eficientemente usa la empresa sus activos para generar ganancias?',
    whatMeasures: 'Mide la rentabilidad generada por cada peso de activos totales de la empresa. Indica la eficiencia operativa independiente de la estructura de financiamiento.',
    reasoning: 'El ROA elimina el efecto del apalancamiento, mostrando la verdadera eficiencia operativa. Útil para comparar empresas con diferentes niveles de deuda.',
    relevance: 'Ideal para comparar empresas del mismo sector. Empresas con activos intensivos (manufactura) tendrán ROA más bajo que empresas de servicios.',
    formula: {
      numerator: 'Utilidad Neta',
      denominator: 'Activos Totales',
      expression: 'ROA = Utilidad Neta / Activos Totales × 100',
      variables: ['Utilidad Neta', 'Activos Totales Promedio']
    },
    relatedMetrics: ['roic', 'roe', 'asset_turnover'],
    evaluation: [
      { level: 'Excelente', color: 'blue', range: '> 15%', description: 'Uso excepcional de activos, muy eficiente.' },
      { level: 'Bueno', color: 'green', range: '10 - 15%', description: 'Buena eficiencia en uso de activos.' },
      { level: 'Aceptable', color: 'yellow', range: '5 - 10%', description: 'Eficiencia promedio del mercado.' },
      { level: 'Bajo', color: 'orange', range: '2 - 5%', description: 'Activos subutilizados.' },
      { level: 'Crítico', color: 'red', range: '< 2%', description: 'Muy ineficiente, activos no generan retorno.' }
    ],
    bestPerformers: [
      { industry: 'Software', icon: 'Monitor', typical: '15-25%' },
      { industry: 'Consultoría', icon: 'Lightbulb', typical: '12-20%' },
    ],
    worstPerformers: [
      { industry: 'Bancos', icon: 'Building2', typical: '1-2%' },
      { industry: 'Utilities', icon: 'Activity', typical: '3-5%' },
    ],
    expertQuote: {
      text: '"El ROA te dice qué tan bien la gerencia está usando los activos de la empresa, independiente de cómo fueron financiados."',
      author: 'Benjamin Graham',
      source: 'The Intelligent Investor'
    }
  },

  // LIQUIDITY RATIOS
  current_ratio: {
    id: 'current_ratio',
    name: 'Razón Circulante',
    nameEn: 'Current Ratio',
    category: 'liquidity',
    question: '¿Puede la empresa pagar sus deudas de corto plazo?',
    whatMeasures: 'Mide la capacidad de la empresa para cubrir sus obligaciones de corto plazo con sus activos de corto plazo. Indica la liquidez general de la empresa.',
    reasoning: 'Un ratio mayor a 1 significa que hay más activos circulantes que pasivos circulantes, proporcionando un colchón de seguridad.',
    relevance: 'Fundamental para acreedores y bancos. Un ratio muy alto puede indicar activos ociosos; muy bajo indica riesgo de liquidez.',
    formula: {
      numerator: 'Activo Circulante',
      denominator: 'Pasivo Circulante',
      expression: 'Razón Circulante = Activo Circulante / Pasivo Circulante',
      variables: ['Efectivo', 'Cuentas por Cobrar', 'Inventarios', 'Cuentas por Pagar', 'Deuda Corto Plazo']
    },
    relatedMetrics: ['quick_ratio', 'cash_ratio', 'working_capital'],
    evaluation: [
      { level: 'Muy alto', color: 'blue', range: '> 3.0x', description: 'Exceso de liquidez, posibles activos ociosos.' },
      { level: 'Saludable', color: 'green', range: '1.5 - 3.0x', description: 'Liquidez adecuada con margen de seguridad.' },
      { level: 'Aceptable', color: 'yellow', range: '1.0 - 1.5x', description: 'Liquidez justa, monitorear de cerca.' },
      { level: 'Bajo', color: 'orange', range: '0.8 - 1.0x', description: 'Riesgo de liquidez, puede necesitar financiamiento.' },
      { level: 'Crítico', color: 'red', range: '< 0.8x', description: 'Problema serio de liquidez, riesgo de impago.' }
    ],
    bestPerformers: [
      { industry: 'Software', icon: 'Monitor', typical: '2.0-4.0x' },
      { industry: 'Tecnología', icon: 'Cpu', typical: '1.8-3.0x' },
    ],
    worstPerformers: [
      { industry: 'Retail', icon: 'ShoppingCart', typical: '1.0-1.5x' },
      { industry: 'Restaurantes', icon: 'Building2', typical: '0.8-1.2x' },
    ],
    expertQuote: {
      text: '"La liquidez es como el oxígeno - no piensas en ella hasta que te falta. Entonces es demasiado tarde."',
      author: 'Howard Marks',
      source: 'Oaktree Capital Memos'
    }
  },

  // NET MARGIN
  net_margin: {
    id: 'net_margin',
    name: 'Margen Neto',
    nameEn: 'Net Margin',
    category: 'margins',
    question: '¿Qué porcentaje de cada peso de ventas se convierte en ganancia?',
    whatMeasures: 'Mide el porcentaje de ingresos que queda como utilidad neta después de todos los gastos, impuestos e intereses. Es el indicador final de rentabilidad.',
    reasoning: 'El margen neto muestra la eficiencia total de la empresa. Incluye todos los costos y gastos, dando una imagen completa de la rentabilidad.',
    relevance: 'El indicador más importante para inversionistas. Permite comparar la rentabilidad final entre empresas de cualquier tamaño.',
    formula: {
      numerator: 'Utilidad Neta',
      denominator: 'Ingresos Totales',
      expression: 'Margen Neto = Utilidad Neta / Ingresos Totales × 100',
      variables: ['Utilidad Neta', 'Ingresos Totales']
    },
    relatedMetrics: ['gross_margin', 'operating_margin', 'ebitda_margin'],
    evaluation: [
      { level: 'Excelente', color: 'blue', range: '> 20%', description: 'Rentabilidad excepcional, negocio muy eficiente.' },
      { level: 'Bueno', color: 'green', range: '10 - 20%', description: 'Rentabilidad saludable, buen control de costos.' },
      { level: 'Aceptable', color: 'yellow', range: '5 - 10%', description: 'Rentabilidad moderada, promedio del mercado.' },
      { level: 'Bajo', color: 'orange', range: '2 - 5%', description: 'Rentabilidad estrecha, vulnerable a cambios.' },
      { level: 'Crítico', color: 'red', range: '< 2%', description: 'Rentabilidad insuficiente, modelo de negocio en riesgo.' }
    ],
    bestPerformers: [
      { industry: 'Software', icon: 'Monitor', typical: '20-35%' },
      { industry: 'Fintech', icon: 'CreditCard', typical: '15-25%' },
    ],
    worstPerformers: [
      { industry: 'Supermercados', icon: 'ShoppingCart', typical: '1-3%' },
      { industry: 'Aerolíneas', icon: 'Activity', typical: '2-5%' },
    ],
    expertQuote: {
      text: '"El margen neto es lo que queda después de que todos han cobrado. Es la prueba definitiva de si el negocio funciona."',
      author: 'Charlie Munger',
      source: 'Berkshire Hathaway Annual Meeting'
    }
  },

  // EBITDA MARGIN
  ebitda_margin: {
    id: 'ebitda_margin',
    name: 'Margen EBITDA',
    nameEn: 'EBITDA Margin',
    category: 'margins',
    question: '¿Qué tan rentable es la operación antes de decisiones financieras y contables?',
    whatMeasures: 'Mide la rentabilidad operativa antes de intereses, impuestos, depreciación y amortización. Muestra la eficiencia de las operaciones core del negocio.',
    reasoning: 'El EBITDA elimina efectos de estructura de capital, políticas fiscales y contables, permitiendo comparar la eficiencia operativa pura.',
    relevance: 'Muy usado en valoraciones y comparaciones sectoriales. Importante para empresas con altos activos fijos o intangibles.',
    formula: {
      numerator: 'EBITDA',
      denominator: 'Ingresos Totales',
      expression: 'Margen EBITDA = (Utilidad Operativa + Depreciación + Amortización) / Ingresos × 100',
      variables: ['Utilidad Operativa', 'Depreciación', 'Amortización', 'Ingresos Totales']
    },
    relatedMetrics: ['operating_margin', 'gross_margin', 'net_margin'],
    evaluation: [
      { level: 'Excelente', color: 'blue', range: '> 30%', description: 'Operación altamente eficiente y rentable.' },
      { level: 'Bueno', color: 'green', range: '15 - 30%', description: 'Operación saludable con buenos márgenes.' },
      { level: 'Aceptable', color: 'yellow', range: '10 - 15%', description: 'Eficiencia operativa promedio.' },
      { level: 'Bajo', color: 'orange', range: '5 - 10%', description: 'Operación con márgenes estrechos.' },
      { level: 'Crítico', color: 'red', range: '< 5%', description: 'Operación ineficiente, difícil generar valor.' }
    ],
    bestPerformers: [
      { industry: 'Software SaaS', icon: 'Monitor', typical: '25-40%' },
      { industry: 'Telecomunicaciones', icon: 'Activity', typical: '30-40%' },
    ],
    worstPerformers: [
      { industry: 'Retail', icon: 'ShoppingCart', typical: '5-10%' },
      { industry: 'Restaurantes', icon: 'Building2', typical: '8-15%' },
    ],
    expertQuote: {
      text: '"EBITDA es útil para comparar operaciones, pero no olvides que depreciación y amortización representan gastos reales de capital."',
      author: 'Warren Buffett',
      source: 'Berkshire Hathaway Annual Letter'
    }
  },

  // OPERATING MARGIN
  operating_margin: {
    id: 'operating_margin',
    name: 'Margen Operativo',
    nameEn: 'Operating Margin',
    category: 'margins',
    question: '¿Qué tan eficiente es la operación del negocio?',
    whatMeasures: 'Mide el porcentaje de ingresos que queda después de cubrir todos los costos y gastos operativos, antes de intereses e impuestos.',
    reasoning: 'El margen operativo muestra la eficiencia del negocio core, independiente de la estructura de financiamiento y situación fiscal.',
    relevance: 'Clave para evaluar la eficiencia operativa. Permite comparar empresas con diferentes estructuras de capital.',
    formula: {
      numerator: 'Utilidad Operativa',
      denominator: 'Ingresos Totales',
      expression: 'Margen Operativo = Utilidad Operativa / Ingresos × 100',
      variables: ['Utilidad Operativa (EBIT)', 'Ingresos Totales']
    },
    relatedMetrics: ['gross_margin', 'ebitda_margin', 'net_margin'],
    evaluation: [
      { level: 'Excelente', color: 'blue', range: '> 25%', description: 'Operación muy eficiente con alto poder de precio.' },
      { level: 'Bueno', color: 'green', range: '15 - 25%', description: 'Operación saludable y bien gestionada.' },
      { level: 'Aceptable', color: 'yellow', range: '8 - 15%', description: 'Eficiencia operativa promedio.' },
      { level: 'Bajo', color: 'orange', range: '3 - 8%', description: 'Márgenes estrechos, vulnerable a costos.' },
      { level: 'Crítico', color: 'red', range: '< 3%', description: 'Operación ineficiente, difícil sostenibilidad.' }
    ],
    bestPerformers: [
      { industry: 'Software', icon: 'Monitor', typical: '20-35%' },
      { industry: 'Farmacéutica', icon: 'Activity', typical: '20-30%' },
    ],
    worstPerformers: [
      { industry: 'Supermercados', icon: 'ShoppingCart', typical: '2-5%' },
      { industry: 'Construcción', icon: 'Building2', typical: '5-10%' },
    ],
    expertQuote: {
      text: '"El margen operativo es donde se gana o se pierde la batalla. Todo lo demás son excusas."',
      author: 'Jack Welch',
      source: 'Former CEO of General Electric'
    }
  },

  // DEBT TO EQUITY
  debt_to_equity: {
    id: 'debt_to_equity',
    name: 'Deuda/Capital',
    nameEn: 'Debt to Equity',
    category: 'solvency',
    question: '¿Qué tan apalancada está la empresa?',
    whatMeasures: 'Mide la proporción de financiamiento vía deuda versus capital propio. Indica el nivel de apalancamiento financiero de la empresa.',
    reasoning: 'Un ratio alto significa más riesgo financiero pero potencialmente mayores retornos. Un ratio bajo indica conservadurismo pero menor riesgo.',
    relevance: 'Crucial para evaluar riesgo financiero. Empresas con alto D/E son más vulnerables en tiempos de crisis.',
    formula: {
      numerator: 'Deuda Total',
      denominator: 'Capital Contable',
      expression: 'D/E = Pasivo Total / Capital Contable',
      variables: ['Pasivo Total', 'Capital Contable']
    },
    relatedMetrics: ['interest_coverage', 'debt_to_assets', 'current_ratio'],
    evaluation: [
      { level: 'Conservador', color: 'blue', range: '< 0.5x', description: 'Bajo apalancamiento, muy seguro pero posiblemente subóptimo.' },
      { level: 'Saludable', color: 'green', range: '0.5 - 1.0x', description: 'Balance adecuado entre riesgo y retorno.' },
      { level: 'Moderado', color: 'yellow', range: '1.0 - 1.5x', description: 'Apalancamiento moderado, monitorear capacidad de pago.' },
      { level: 'Alto', color: 'orange', range: '1.5 - 2.5x', description: 'Alto apalancamiento, riesgo elevado.' },
      { level: 'Crítico', color: 'red', range: '> 2.5x', description: 'Apalancamiento excesivo, alto riesgo de insolvencia.' }
    ],
    bestPerformers: [
      { industry: 'Tecnología', icon: 'Cpu', typical: '0.2-0.5x' },
      { industry: 'Software', icon: 'Monitor', typical: '0.1-0.4x' },
    ],
    worstPerformers: [
      { industry: 'Utilities', icon: 'Activity', typical: '1.0-2.0x' },
      { industry: 'Real Estate', icon: 'Building2', typical: '1.5-3.0x' },
    ],
    expertQuote: {
      text: '"La deuda es como cualquier otra trampa, fácil de entrar pero difícil de salir."',
      author: 'Josh Billings',
      source: 'American Humorist'
    }
  },

  // INTEREST COVERAGE
  interest_coverage: {
    id: 'interest_coverage',
    name: 'Cobertura de Intereses',
    nameEn: 'Interest Coverage',
    category: 'solvency',
    question: '¿Puede la empresa pagar sus intereses con sus ganancias operativas?',
    whatMeasures: 'Mide cuántas veces la utilidad operativa cubre los gastos por intereses. Indica la capacidad de servicio de deuda.',
    reasoning: 'Un ratio alto indica que la empresa puede manejar cómodamente su deuda. Menos de 1.5x es señal de estrés financiero.',
    relevance: 'Fundamental para acreedores y tenedores de bonos. Indica sostenibilidad de la estructura de deuda.',
    formula: {
      numerator: 'EBIT',
      denominator: 'Gastos por Intereses',
      expression: 'Cobertura = EBIT / Gastos por Intereses',
      variables: ['Utilidad Operativa (EBIT)', 'Gastos Financieros']
    },
    relatedMetrics: ['debt_to_equity', 'debt_to_ebitda', 'cash_flow_coverage'],
    evaluation: [
      { level: 'Excelente', color: 'blue', range: '> 10x', description: 'Cobertura excepcional, deuda muy manejable.' },
      { level: 'Saludable', color: 'green', range: '5 - 10x', description: 'Cobertura sólida, sin problemas para pagar intereses.' },
      { level: 'Aceptable', color: 'yellow', range: '2.5 - 5x', description: 'Cobertura adecuada, monitorear.' },
      { level: 'Bajo', color: 'orange', range: '1.5 - 2.5x', description: 'Cobertura estrecha, vulnerable a caídas.' },
      { level: 'Crítico', color: 'red', range: '< 1.5x', description: 'Riesgo de impago, estrés financiero.' }
    ],
    bestPerformers: [
      { industry: 'Software', icon: 'Monitor', typical: '20-50x' },
      { industry: 'Tecnología', icon: 'Cpu', typical: '15-30x' },
    ],
    worstPerformers: [
      { industry: 'Aerolíneas', icon: 'Activity', typical: '2-5x' },
      { industry: 'Hotelería', icon: 'Building2', typical: '3-6x' },
    ],
    expertQuote: {
      text: '"Una empresa que no puede cubrir sus intereses es una empresa que está muriendo lentamente."',
      author: 'Ray Dalio',
      source: 'Bridgewater Associates'
    }
  },

  // EFFICIENCY METRICS
  asset_turnover: {
    id: 'asset_turnover',
    name: 'Rotación de Activos',
    nameEn: 'Asset Turnover',
    category: 'efficiency',
    question: '¿Qué tan eficientemente usa la empresa sus activos para generar ventas?',
    whatMeasures: 'Mide cuántos pesos de ventas genera la empresa por cada peso invertido en activos. Indica la eficiencia con que la empresa utiliza su base de activos para producir ingresos.',
    reasoning: 'Una rotación alta significa que la empresa genera más ventas con menos activos, lo cual es señal de eficiencia operativa. Empresas de servicios típicamente tienen rotación más alta que manufactura.',
    relevance: 'Clave para comparar eficiencia entre empresas del mismo sector. Componente fundamental del análisis DuPont de ROA.',
    formula: {
      numerator: 'Ingresos Totales',
      denominator: 'Activos Totales Promedio',
      expression: 'Rotación = Ventas / Activos Totales',
      variables: ['Ingresos Totales', 'Activos Totales', 'Activos Promedio del Período']
    },
    relatedMetrics: ['roa', 'inventory_turnover', 'receivables_turnover'],
    evaluation: [
      { level: 'Excelente', color: 'blue', range: '> 2.0x', description: 'Muy eficiente, genera muchas ventas por peso de activos.' },
      { level: 'Bueno', color: 'green', range: '1.0 - 2.0x', description: 'Eficiencia adecuada en uso de activos.' },
      { level: 'Aceptable', color: 'yellow', range: '0.5 - 1.0x', description: 'Eficiencia moderada, común en industrias de capital intensivo.' },
      { level: 'Bajo', color: 'orange', range: '0.3 - 0.5x', description: 'Activos subutilizados o negocio de lenta rotación.' },
      { level: 'Crítico', color: 'red', range: '< 0.3x', description: 'Muy baja rotación, posibles activos ociosos.' }
    ],
    bestPerformers: [
      { industry: 'Retail', icon: 'ShoppingCart', typical: '2.0-3.5x' },
      { industry: 'Restaurantes', icon: 'Building2', typical: '1.5-2.5x' },
      { industry: 'Servicios', icon: 'Activity', typical: '1.5-2.0x' },
    ],
    worstPerformers: [
      { industry: 'Utilities', icon: 'Activity', typical: '0.3-0.5x' },
      { industry: 'Real Estate', icon: 'Building2', typical: '0.1-0.3x' },
      { industry: 'Telecomunicaciones', icon: 'Monitor', typical: '0.4-0.6x' },
    ],
    expertQuote: {
      text: '"La rotación de activos te dice qué tan duro trabajan tus activos. Es la diferencia entre capital dormido y capital productivo."',
      author: 'Peter Lynch',
      source: 'Beating the Street'
    }
  },

  dso: {
    id: 'dso',
    name: 'DSO (Días de Cobro)',
    nameEn: 'Days Sales Outstanding',
    category: 'efficiency',
    question: '¿Cuántos días tarda en promedio la empresa en cobrar sus ventas a crédito?',
    whatMeasures: 'Mide el número promedio de días que tarda la empresa en convertir sus cuentas por cobrar en efectivo. Indica la eficiencia en la gestión de crédito y cobranza.',
    reasoning: 'Un DSO bajo significa cobro rápido y mejor flujo de efectivo. Un DSO alto puede indicar problemas de cobranza, clientes morosos o políticas de crédito laxas.',
    relevance: 'Fundamental para gestión de capital de trabajo. Impacta directamente el ciclo de conversión de efectivo y necesidades de financiamiento.',
    formula: {
      numerator: 'Cuentas por Cobrar × 365',
      denominator: 'Ventas a Crédito (Ingresos)',
      expression: 'DSO = (Cuentas por Cobrar / Ventas) × 365 días',
      variables: ['Cuentas por Cobrar', 'Ventas Netas', 'Días del Período']
    },
    relatedMetrics: ['dpo', 'cash_conversion_cycle', 'current_ratio'],
    evaluation: [
      { level: 'Excelente', color: 'blue', range: '< 30 días', description: 'Cobranza muy eficiente, excelente flujo de efectivo.' },
      { level: 'Bueno', color: 'green', range: '30 - 45 días', description: 'Cobranza saludable, dentro de términos comerciales normales.' },
      { level: 'Aceptable', color: 'yellow', range: '45 - 60 días', description: 'Cobranza moderada, monitorear tendencia.' },
      { level: 'Alto', color: 'orange', range: '60 - 90 días', description: 'Cobranza lenta, posibles problemas con clientes.' },
      { level: 'Crítico', color: 'red', range: '> 90 días', description: 'Cobranza deficiente, alto riesgo de incobrables.' }
    ],
    bestPerformers: [
      { industry: 'Retail (contado)', icon: 'ShoppingCart', typical: '0-15 días' },
      { industry: 'E-Commerce', icon: 'Monitor', typical: '5-20 días' },
      { industry: 'Restaurantes', icon: 'Building2', typical: '0-10 días' },
    ],
    worstPerformers: [
      { industry: 'Construcción', icon: 'Building2', typical: '60-120 días' },
      { industry: 'Gobierno/Público', icon: 'Activity', typical: '90-180 días' },
      { industry: 'B2B Industrial', icon: 'Cpu', typical: '45-75 días' },
    ],
    expertQuote: {
      text: '"DSO es el termómetro de tu departamento de cobranza. Si sube, estás financiando gratis a tus clientes."',
      author: 'CFO Magazine',
      source: 'Working Capital Management Guide'
    }
  },

  dpo: {
    id: 'dpo',
    name: 'DPO (Días de Pago)',
    nameEn: 'Days Payable Outstanding',
    category: 'efficiency',
    question: '¿Cuántos días tarda en promedio la empresa en pagar a sus proveedores?',
    whatMeasures: 'Mide el número promedio de días que la empresa tarda en pagar sus cuentas por pagar. Indica la política de pagos y el poder de negociación con proveedores.',
    reasoning: 'Un DPO alto significa que la empresa retiene efectivo más tiempo, mejorando liquidez. Sin embargo, demasiado alto puede dañar relaciones con proveedores o perder descuentos.',
    relevance: 'Componente clave del ciclo de conversión de efectivo. Refleja la capacidad de negociación y la salud de las relaciones con proveedores.',
    formula: {
      numerator: 'Cuentas por Pagar × 365',
      denominator: 'Costo de Ventas',
      expression: 'DPO = (Cuentas por Pagar / Costo de Ventas) × 365 días',
      variables: ['Cuentas por Pagar', 'Costo de Ventas', 'Días del Período']
    },
    relatedMetrics: ['dso', 'cash_conversion_cycle', 'current_ratio'],
    evaluation: [
      { level: 'Muy bajo', color: 'orange', range: '< 20 días', description: 'Pago muy rápido, posible pérdida de float de efectivo.' },
      { level: 'Bajo', color: 'yellow', range: '20 - 30 días', description: 'Pago rápido, buena relación pero menos efectivo disponible.' },
      { level: 'Óptimo', color: 'green', range: '30 - 45 días', description: 'Balance adecuado entre relación con proveedores y liquidez.' },
      { level: 'Alto', color: 'blue', range: '45 - 60 días', description: 'Buen uso del crédito de proveedores, maximiza float.' },
      { level: 'Muy alto', color: 'red', range: '> 60 días', description: 'Posible tensión con proveedores o problemas de liquidez.' }
    ],
    bestPerformers: [
      { industry: 'Retail grande', icon: 'ShoppingCart', typical: '45-90 días' },
      { industry: 'Supermercados', icon: 'ShoppingCart', typical: '30-60 días' },
      { industry: 'Tech grandes', icon: 'Cpu', typical: '60-90 días' },
    ],
    worstPerformers: [
      { industry: 'Startups', icon: 'Lightbulb', typical: '15-30 días' },
      { industry: 'PyMEs', icon: 'Building2', typical: '20-35 días' },
    ],
    expertQuote: {
      text: '"El DPO refleja tu poder de negociación. Las empresas más fuertes pueden estirar los pagos, las débiles pagan de contado."',
      author: 'Harvard Business Review',
      source: 'Supply Chain Finance'
    }
  },

  cash_conversion_cycle: {
    id: 'cash_conversion_cycle',
    name: 'Ciclo de Conversión de Efectivo',
    nameEn: 'Cash Conversion Cycle',
    category: 'efficiency',
    question: '¿Cuántos días tarda la empresa en convertir su inversión en inventario en efectivo?',
    whatMeasures: 'Mide el tiempo total desde que la empresa paga por inventario hasta que cobra la venta. Es la suma de DSO + DIO - DPO. Indica la eficiencia del capital de trabajo.',
    reasoning: 'Un ciclo corto o negativo significa que la empresa genera efectivo rápidamente de sus operaciones. Un ciclo largo indica que el efectivo está "atrapado" en operaciones.',
    relevance: 'El indicador más completo de eficiencia de capital de trabajo. Empresas como Amazon tienen ciclos negativos, lo que significa que cobran antes de pagar.',
    formula: {
      numerator: 'DSO + DIO - DPO',
      denominator: 'N/A',
      expression: 'CCC = Días de Cobro + Días de Inventario - Días de Pago',
      variables: ['DSO (Días de Cobro)', 'DIO (Días de Inventario)', 'DPO (Días de Pago)']
    },
    relatedMetrics: ['dso', 'dpo', 'inventory_turnover', 'working_capital'],
    evaluation: [
      { level: 'Excelente', color: 'blue', range: '< 0 días', description: 'Ciclo negativo: cobras antes de pagar. Modelo ideal.' },
      { level: 'Muy bueno', color: 'green', range: '0 - 30 días', description: 'Ciclo corto, excelente eficiencia de capital de trabajo.' },
      { level: 'Aceptable', color: 'yellow', range: '30 - 60 días', description: 'Ciclo moderado, hay espacio para mejorar.' },
      { level: 'Alto', color: 'orange', range: '60 - 90 días', description: 'Ciclo largo, efectivo atrapado en operaciones.' },
      { level: 'Crítico', color: 'red', range: '> 90 días', description: 'Ciclo muy largo, altas necesidades de financiamiento.' }
    ],
    bestPerformers: [
      { industry: 'Amazon/E-commerce', icon: 'ShoppingCart', typical: '-30 a 0 días' },
      { industry: 'Supermercados', icon: 'ShoppingCart', typical: '0-15 días' },
      { industry: 'Restaurantes', icon: 'Building2', typical: '5-20 días' },
    ],
    worstPerformers: [
      { industry: 'Manufactura', icon: 'Cpu', typical: '60-120 días' },
      { industry: 'Construcción', icon: 'Building2', typical: '90-180 días' },
      { industry: 'Aeroespacial', icon: 'Activity', typical: '120-200 días' },
    ],
    expertQuote: {
      text: '"El ciclo de conversión de efectivo es el pulso del negocio. Un ciclo negativo es como tener a tus proveedores financiando tu crecimiento."',
      author: 'Jeff Bezos',
      source: 'Amazon Annual Letter'
    }
  },

  quick_ratio: {
    id: 'quick_ratio',
    name: 'Prueba Ácida',
    nameEn: 'Quick Ratio / Acid Test',
    category: 'liquidity',
    question: '¿Puede la empresa pagar sus deudas de corto plazo sin vender inventario?',
    whatMeasures: 'Mide la capacidad de la empresa para cubrir sus obligaciones de corto plazo usando solo sus activos más líquidos (efectivo, inversiones temporales y cuentas por cobrar), excluyendo inventarios.',
    reasoning: 'Es una prueba más estricta que la razón circulante porque excluye inventarios, que pueden ser difíciles de convertir en efectivo rápidamente o a su valor total.',
    relevance: 'Especialmente relevante para empresas con inventarios de lenta rotación. Indica la verdadera capacidad de respuesta ante obligaciones inmediatas.',
    formula: {
      numerator: 'Activo Circulante - Inventarios',
      denominator: 'Pasivo Circulante',
      expression: 'Prueba Ácida = (Efectivo + CxC + Inversiones) / Pasivo Circulante',
      variables: ['Efectivo', 'Cuentas por Cobrar', 'Inversiones Temporales', 'Pasivo Circulante']
    },
    relatedMetrics: ['current_ratio', 'cash_ratio', 'working_capital'],
    evaluation: [
      { level: 'Excelente', color: 'blue', range: '> 2.0x', description: 'Muy alta liquidez sin depender de inventarios.' },
      { level: 'Saludable', color: 'green', range: '1.0 - 2.0x', description: 'Liquidez adecuada para cubrir obligaciones inmediatas.' },
      { level: 'Aceptable', color: 'yellow', range: '0.7 - 1.0x', description: 'Liquidez justa, monitorear de cerca.' },
      { level: 'Bajo', color: 'orange', range: '0.5 - 0.7x', description: 'Dependencia de inventarios para cubrir deudas.' },
      { level: 'Crítico', color: 'red', range: '< 0.5x', description: 'Riesgo serio de liquidez, dificultad para pagar.' }
    ],
    bestPerformers: [
      { industry: 'Software', icon: 'Monitor', typical: '2.0-5.0x' },
      { industry: 'Servicios', icon: 'Lightbulb', typical: '1.5-3.0x' },
      { industry: 'Tecnología', icon: 'Cpu', typical: '1.5-2.5x' },
    ],
    worstPerformers: [
      { industry: 'Retail', icon: 'ShoppingCart', typical: '0.3-0.8x' },
      { industry: 'Manufactura', icon: 'Building2', typical: '0.5-1.0x' },
      { industry: 'Automotriz', icon: 'Activity', typical: '0.4-0.8x' },
    ],
    expertQuote: {
      text: '"La prueba ácida te dice la verdad cruda: ¿puedes pagar sin vender inventario? Si no, estás un paso más cerca del precipicio."',
      author: 'Benjamin Graham',
      source: 'Security Analysis'
    }
  },

  cash_ratio: {
    id: 'cash_ratio',
    name: 'Razón de Efectivo',
    nameEn: 'Cash Ratio',
    category: 'liquidity',
    question: '¿Puede la empresa pagar todas sus deudas de corto plazo solo con efectivo disponible?',
    whatMeasures: 'Mide la capacidad de la empresa para cubrir sus obligaciones de corto plazo usando únicamente efectivo y equivalentes de efectivo. Es el indicador de liquidez más conservador.',
    reasoning: 'Excluye cuentas por cobrar e inventarios. Muestra la posición de efectivo puro de la empresa. Un ratio muy alto puede indicar efectivo ocioso que debería invertirse.',
    relevance: 'Importante en momentos de crisis o incertidumbre. Indica la capacidad de supervivencia si las ventas se detienen completamente.',
    formula: {
      numerator: 'Efectivo + Equivalentes de Efectivo',
      denominator: 'Pasivo Circulante',
      expression: 'Razón de Efectivo = Efectivo / Pasivo Circulante',
      variables: ['Efectivo en Caja y Bancos', 'Inversiones Temporales', 'Pasivo Circulante']
    },
    relatedMetrics: ['current_ratio', 'quick_ratio', 'working_capital'],
    evaluation: [
      { level: 'Muy alto', color: 'blue', range: '> 1.0x', description: 'Puede pagar todo con efectivo. ¿Hay efectivo ocioso?' },
      { level: 'Saludable', color: 'green', range: '0.5 - 1.0x', description: 'Buena posición de efectivo sin excesos.' },
      { level: 'Aceptable', color: 'yellow', range: '0.2 - 0.5x', description: 'Efectivo moderado, depende de cobranza.' },
      { level: 'Bajo', color: 'orange', range: '0.1 - 0.2x', description: 'Poco efectivo disponible inmediatamente.' },
      { level: 'Crítico', color: 'red', range: '< 0.1x', description: 'Efectivo muy bajo, vulnerabilidad alta.' }
    ],
    bestPerformers: [
      { industry: 'Tech (cash-rich)', icon: 'Cpu', typical: '0.8-2.0x' },
      { industry: 'Farmacéuticas', icon: 'Activity', typical: '0.5-1.5x' },
    ],
    worstPerformers: [
      { industry: 'Retail', icon: 'ShoppingCart', typical: '0.05-0.2x' },
      { industry: 'Manufactura', icon: 'Building2', typical: '0.1-0.3x' },
    ],
    expertQuote: {
      text: '"El efectivo es el oxígeno de los negocios. Sin él, mueres. Con demasiado, te vuelves perezoso."',
      author: 'Warren Buffett',
      source: 'Berkshire Hathaway Meeting'
    }
  },

  working_capital: {
    id: 'working_capital',
    name: 'Capital de Trabajo',
    nameEn: 'Working Capital',
    category: 'liquidity',
    question: '¿Cuántos recursos tiene la empresa disponibles para operar después de pagar sus deudas de corto plazo?',
    whatMeasures: 'Mide la diferencia entre activos circulantes y pasivos circulantes. Representa el colchón financiero disponible para operaciones diarias.',
    reasoning: 'Un capital de trabajo positivo significa que la empresa puede cubrir sus obligaciones y seguir operando. Negativo indica dependencia de financiamiento adicional.',
    relevance: 'Fundamental para la operación diaria. Determina si la empresa necesita financiamiento externo para operar o si genera suficiente liquidez internamente.',
    formula: {
      numerator: 'Activo Circulante',
      denominator: 'Pasivo Circulante',
      expression: 'Capital de Trabajo = Activo Circulante - Pasivo Circulante',
      variables: ['Activo Circulante Total', 'Pasivo Circulante Total', 'Diferencia Absoluta']
    },
    relatedMetrics: ['current_ratio', 'quick_ratio', 'cash_conversion_cycle'],
    evaluation: [
      { level: 'Muy alto', color: 'blue', range: '> 50% de ventas', description: 'Exceso de capital, posible ineficiencia.' },
      { level: 'Saludable', color: 'green', range: '20 - 50% de ventas', description: 'Capital de trabajo adecuado para operaciones.' },
      { level: 'Aceptable', color: 'yellow', range: '10 - 20% de ventas', description: 'Capital ajustado, monitorear flujos.' },
      { level: 'Bajo', color: 'orange', range: '0 - 10% de ventas', description: 'Capital de trabajo limitado.' },
      { level: 'Negativo', color: 'red', range: '< 0', description: 'Déficit de capital, necesita financiamiento.' }
    ],
    bestPerformers: [
      { industry: 'Software', icon: 'Monitor', typical: 'Alto positivo' },
      { industry: 'Servicios', icon: 'Lightbulb', typical: 'Positivo estable' },
    ],
    worstPerformers: [
      { industry: 'Retail rápido', icon: 'ShoppingCart', typical: 'Bajo o negativo' },
      { industry: 'Restaurantes', icon: 'Building2', typical: 'Bajo' },
    ],
    expertQuote: {
      text: '"El capital de trabajo es el lubricante que mantiene funcionando la maquinaria del negocio. Sin él, todo se detiene."',
      author: 'Joel Greenblatt',
      source: 'The Little Book That Beats the Market'
    }
  },

  nopat_margin: {
    id: 'nopat_margin',
    name: 'Margen NOPAT',
    nameEn: 'NOPAT Margin',
    category: 'margins',
    question: '¿Qué porcentaje de ventas se convierte en utilidad operativa después de impuestos?',
    whatMeasures: 'Mide la rentabilidad operativa neta de impuestos como porcentaje de las ventas. NOPAT = Net Operating Profit After Taxes.',
    reasoning: 'Elimina el efecto de la estructura de capital (deuda) y muestra la rentabilidad pura de las operaciones. Es el numerador del ROIC.',
    relevance: 'Clave para calcular el ROIC y evaluar la eficiencia operativa real sin distorsiones de financiamiento.',
    formula: {
      numerator: 'NOPAT',
      denominator: 'Ingresos Totales',
      expression: 'Margen NOPAT = (EBIT × (1 - Tasa de Impuestos)) / Ingresos',
      variables: ['Utilidad Operativa (EBIT)', 'Tasa de Impuestos', 'Ingresos Totales']
    },
    relatedMetrics: ['roic', 'operating_margin', 'net_margin'],
    evaluation: [
      { level: 'Excelente', color: 'blue', range: '> 15%', description: 'Alta rentabilidad operativa neta.' },
      { level: 'Bueno', color: 'green', range: '10 - 15%', description: 'Rentabilidad operativa saludable.' },
      { level: 'Aceptable', color: 'yellow', range: '5 - 10%', description: 'Rentabilidad moderada.' },
      { level: 'Bajo', color: 'orange', range: '2 - 5%', description: 'Márgenes operativos estrechos.' },
      { level: 'Crítico', color: 'red', range: '< 2%', description: 'Operación apenas rentable.' }
    ],
    bestPerformers: [
      { industry: 'Software', icon: 'Monitor', typical: '15-30%' },
      { industry: 'Farmacéutica', icon: 'Activity', typical: '15-25%' },
    ],
    worstPerformers: [
      { industry: 'Retail', icon: 'ShoppingCart', typical: '2-5%' },
      { industry: 'Aerolíneas', icon: 'Activity', typical: '2-6%' },
    ],
    expertQuote: {
      text: '"NOPAT es la utilidad que pertenece a todos los proveedores de capital. Es la métrica más pura de rentabilidad operativa."',
      author: 'McKinsey & Company',
      source: 'Valuation: Measuring and Managing Value'
    }
  },

  roce: {
    id: 'roce',
    name: 'ROCE',
    nameEn: 'Return on Capital Employed',
    category: 'returns',
    question: '¿Qué tan eficientemente genera la empresa retornos sobre todo el capital empleado?',
    whatMeasures: 'Mide la rentabilidad generada sobre el capital total empleado en la empresa (activos totales menos pasivos circulantes). Similar al ROIC pero con diferente definición de capital.',
    reasoning: 'Muestra la eficiencia con que la empresa usa su capital a largo plazo. Es útil para comparar empresas con diferentes estructuras de capital.',
    relevance: 'Muy usado en UK y Europa. Complementa al ROIC para análisis de eficiencia de capital.',
    formula: {
      numerator: 'EBIT',
      denominator: 'Capital Empleado',
      expression: 'ROCE = EBIT / (Activos Totales - Pasivos Circulantes)',
      variables: ['Utilidad Operativa (EBIT)', 'Activos Totales', 'Pasivos Circulantes']
    },
    relatedMetrics: ['roic', 'roe', 'roa'],
    evaluation: [
      { level: 'Excelente', color: 'blue', range: '> 20%', description: 'Uso excepcional del capital empleado.' },
      { level: 'Bueno', color: 'green', range: '12 - 20%', description: 'Buena eficiencia de capital.' },
      { level: 'Aceptable', color: 'yellow', range: '8 - 12%', description: 'Eficiencia promedio.' },
      { level: 'Bajo', color: 'orange', range: '5 - 8%', description: 'Capital subutilizado.' },
      { level: 'Crítico', color: 'red', range: '< 5%', description: 'Pobre uso del capital.' }
    ],
    bestPerformers: [
      { industry: 'Software', icon: 'Monitor', typical: '20-40%' },
      { industry: 'Tecnología', icon: 'Cpu', typical: '15-30%' },
    ],
    worstPerformers: [
      { industry: 'Utilities', icon: 'Activity', typical: '5-10%' },
      { industry: 'Telecomunicaciones', icon: 'Monitor', typical: '8-12%' },
    ],
    expertQuote: {
      text: '"ROCE es particularmente útil para empresas capital-intensivas donde la inversión en activos fijos es significativa."',
      author: 'Aswath Damodaran',
      source: 'NYU Stern School of Business'
    }
  },

  debt_to_assets: {
    id: 'debt_to_assets',
    name: 'Deuda/Activos',
    nameEn: 'Debt to Assets Ratio',
    category: 'solvency',
    question: '¿Qué porcentaje de los activos de la empresa están financiados con deuda?',
    whatMeasures: 'Mide la proporción de activos totales que está financiada por acreedores versus propietarios. Indica el nivel de apalancamiento financiero.',
    reasoning: 'Un ratio alto significa mayor dependencia de deuda y mayor riesgo financiero. Un ratio bajo indica financiamiento más conservador.',
    relevance: 'Importante para acreedores y análisis de riesgo. Complementa el ratio deuda/capital.',
    formula: {
      numerator: 'Pasivo Total',
      denominator: 'Activo Total',
      expression: 'Deuda/Activos = Pasivo Total / Activo Total × 100',
      variables: ['Pasivo Total', 'Activo Total']
    },
    relatedMetrics: ['debt_to_equity', 'interest_coverage', 'equity_ratio'],
    evaluation: [
      { level: 'Conservador', color: 'blue', range: '< 30%', description: 'Bajo apalancamiento, muy seguro.' },
      { level: 'Saludable', color: 'green', range: '30 - 50%', description: 'Balance adecuado de financiamiento.' },
      { level: 'Moderado', color: 'yellow', range: '50 - 60%', description: 'Apalancamiento moderado.' },
      { level: 'Alto', color: 'orange', range: '60 - 70%', description: 'Alta dependencia de deuda.' },
      { level: 'Crítico', color: 'red', range: '> 70%', description: 'Muy apalancado, alto riesgo.' }
    ],
    bestPerformers: [
      { industry: 'Tecnología', icon: 'Cpu', typical: '20-40%' },
      { industry: 'Software', icon: 'Monitor', typical: '15-35%' },
    ],
    worstPerformers: [
      { industry: 'Utilities', icon: 'Activity', typical: '55-70%' },
      { industry: 'Bancos', icon: 'CreditCard', typical: '85-95%' },
    ],
    expertQuote: {
      text: '"Cuanto más alto el ratio deuda/activos, más de tu empresa pertenece realmente a los bancos."',
      author: 'John Bogle',
      source: 'Common Sense on Mutual Funds'
    }
  },

  equity_ratio: {
    id: 'equity_ratio',
    name: 'Razón de Patrimonio',
    nameEn: 'Equity Ratio',
    category: 'solvency',
    question: '¿Qué porcentaje de los activos pertenece a los accionistas?',
    whatMeasures: 'Mide la proporción de activos totales financiados con capital propio de los accionistas. Es el complemento de Deuda/Activos.',
    reasoning: 'Un ratio alto indica que los accionistas tienen mayor participación en la empresa. Proporciona un colchón contra pérdidas.',
    relevance: 'Indica la solidez patrimonial de la empresa. Mayor ratio = menor riesgo para acreedores.',
    formula: {
      numerator: 'Capital Contable',
      denominator: 'Activo Total',
      expression: 'Razón de Patrimonio = Capital Contable / Activo Total × 100',
      variables: ['Capital Contable (Patrimonio)', 'Activo Total']
    },
    relatedMetrics: ['debt_to_equity', 'debt_to_assets', 'roe'],
    evaluation: [
      { level: 'Muy alto', color: 'blue', range: '> 70%', description: 'Muy sólido, bajo apalancamiento.' },
      { level: 'Saludable', color: 'green', range: '50 - 70%', description: 'Buena proporción de capital propio.' },
      { level: 'Moderado', color: 'yellow', range: '40 - 50%', description: 'Balance entre deuda y capital.' },
      { level: 'Bajo', color: 'orange', range: '30 - 40%', description: 'Mayor dependencia de acreedores.' },
      { level: 'Crítico', color: 'red', range: '< 30%', description: 'Alta dependencia de deuda externa.' }
    ],
    bestPerformers: [
      { industry: 'Tecnología', icon: 'Cpu', typical: '60-80%' },
      { industry: 'Software', icon: 'Monitor', typical: '65-85%' },
    ],
    worstPerformers: [
      { industry: 'Bancos', icon: 'CreditCard', typical: '5-15%' },
      { industry: 'Utilities', icon: 'Activity', typical: '30-45%' },
    ],
    expertQuote: {
      text: '"El patrimonio es el colchón que absorbe las pérdidas antes de que afecten a los acreedores."',
      author: 'Jamie Dimon',
      source: 'JPMorgan Annual Report'
    }
  },
};

// Icon mapping
const getIcon = (iconName) => {
  const icons = {
    Monitor: Monitor,
    ShoppingCart: ShoppingCart,
    Cpu: Cpu,
    CreditCard: CreditCard,
    Megaphone: Megaphone,
    Activity: Activity,
    Building2: Building2,
    Lightbulb: Lightbulb,
  };
  return icons[iconName] || Building2;
};

// Color mapping
const getColorClasses = (color) => {
  const colors = {
    blue: { bg: 'bg-blue-50', border: 'border-blue-300', text: 'text-blue-700', dot: 'bg-blue-500', arrow: 'text-blue-500' },
    green: { bg: 'bg-green-50', border: 'border-green-300', text: 'text-green-700', dot: 'bg-green-500', arrow: 'text-green-500' },
    yellow: { bg: 'bg-yellow-50', border: 'border-yellow-300', text: 'text-yellow-700', dot: 'bg-yellow-500', arrow: 'text-yellow-500' },
    orange: { bg: 'bg-orange-50', border: 'border-orange-300', text: 'text-orange-700', dot: 'bg-orange-500', arrow: 'text-orange-500' },
    red: { bg: 'bg-red-50', border: 'border-red-300', text: 'text-red-700', dot: 'bg-red-500', arrow: 'text-red-500' },
  };
  return colors[color] || colors.blue;
};

const MetricDetail = () => {
  const { metricId } = useParams();
  const navigate = useNavigate();
  const [activeSection, setActiveSection] = useState('whatMeasures');
  const [activeEvaluation, setActiveEvaluation] = useState(1); // Default to "Bueno"
  const [currentValue, setCurrentValue] = useState(null);
  const [loading, setLoading] = useState(true);
  const [performerTab, setPerformerTab] = useState('best');

  const metric = metricDefinitions[metricId];

  useEffect(() => {
    // Load current metric value from API
    const loadMetricValue = async () => {
      try {
        const periodsRes = await api.get('/financial-statements/periods');
        if (periodsRes.data?.length > 0) {
          const latestPeriod = periodsRes.data[0].periodo;
          const metricsRes = await api.get(`/financial-statements/metrics/${latestPeriod}`);
          
          // Find the metric value in the response
          const metrics = metricsRes.data?.metrics;
          if (metrics) {
            // Search in all categories
            for (const category of Object.values(metrics)) {
              if (category[metricId]) {
                setCurrentValue(category[metricId].value);
                // Determine which evaluation level the current value falls into
                const evalLevel = determineEvaluationLevel(category[metricId].value, metric?.evaluation);
                setActiveEvaluation(evalLevel);
                break;
              }
            }
          }
        }
      } catch (error) {
        console.error('Error loading metric value:', error);
      } finally {
        setLoading(false);
      }
    };

    if (metric) {
      loadMetricValue();
    } else {
      setLoading(false);
    }
  }, [metricId, metric]);

  const determineEvaluationLevel = (value, evaluations) => {
    if (!evaluations || value === null || value === undefined) return 1;
    
    // Parse the range and determine which level the value falls into
    for (let i = 0; i < evaluations.length; i++) {
      const range = evaluations[i].range;
      
      // Parse ranges like "> 25%", "15 - 25%", "< 5%", "> 3.0x", etc.
      if (range.includes('>')) {
        const threshold = parseFloat(range.replace(/[>%x\s]/g, ''));
        if (value > threshold) return i;
      } else if (range.includes('<')) {
        const threshold = parseFloat(range.replace(/[<%x\s]/g, ''));
        if (value < threshold) return i;
      } else if (range.includes('-')) {
        const [min, max] = range.split('-').map(s => parseFloat(s.replace(/[%x\s]/g, '')));
        if (value >= min && value <= max) return i;
      }
    }
    return evaluations.length - 1; // Default to last (worst)
  };

  if (!metric) {
    return (
      <div className="min-h-screen bg-gray-50 flex items-center justify-center">
        <Card className="p-8 text-center">
          <h2 className="text-xl font-bold text-gray-800 mb-4">Métrica no encontrada</h2>
          <p className="text-gray-600 mb-4">La métrica "{metricId}" no existe en el sistema.</p>
          <Button onClick={() => navigate('/financial-metrics')}>
            <ArrowLeft className="w-4 h-4 mr-2" />
            Volver a Métricas
          </Button>
        </Card>
      </div>
    );
  }

  const sections = [
    { id: 'whatMeasures', label: '¿Qué mide?', icon: HelpCircle },
    { id: 'reasoning', label: 'Razonamiento', icon: Lightbulb },
    { id: 'relevance', label: 'Relevancia', icon: Star },
    { id: 'formula', label: 'Fórmula', icon: Calculator },
    { id: 'relatedMetrics', label: 'Métricas relacionadas', icon: Link2 },
  ];

  const formatValue = (val) => {
    if (val === null || val === undefined) return 'N/A';
    
    // Metrics that should show as "x" (ratios)
    const ratioMetrics = ['current_ratio', 'quick_ratio', 'cash_ratio', 'debt_to_equity', 'interest_coverage', 'debt_to_ebitda', 'asset_turnover'];
    
    // Metrics that should show as "días" (days)
    const dayMetrics = ['dso', 'dpo', 'cash_conversion_cycle'];
    
    if (ratioMetrics.includes(metric.id)) {
      return `${val.toFixed(2)}x`;
    }
    if (dayMetrics.includes(metric.id)) {
      return `${Math.round(val)} días`;
    }
    // Everything else is a percentage
    return `${val.toFixed(1)}%`;
  };

  return (
    <div className="min-h-screen bg-gradient-to-br from-slate-50 to-blue-50">
      {/* Header */}
      <div className="bg-white border-b border-gray-200 sticky top-0 z-10">
        <div className="max-w-7xl mx-auto px-6 py-4 flex items-center justify-between">
          <div className="flex items-center gap-4">
            <h1 className="text-2xl font-bold text-gray-900">{metric.name}</h1>
            <span className="text-sm text-gray-500 bg-gray-100 px-3 py-1 rounded-full">{metric.nameEn}</span>
          </div>
          <Button variant="outline" onClick={() => navigate('/financial-metrics')}>
            Volver a métricas
          </Button>
        </div>
      </div>

      <div className="max-w-7xl mx-auto px-6 py-8">
        <div className="grid grid-cols-1 lg:grid-cols-3 gap-8">
          
          {/* Left Column - Metric Card & Evaluation */}
          <div className="space-y-6">
            {/* Metric Overview Card */}
            <Card className="overflow-hidden">
              <div className="bg-gradient-to-br from-blue-500 to-indigo-600 p-6 text-white">
                <div className="w-24 h-24 bg-white/20 rounded-xl flex items-center justify-center mb-4 backdrop-blur-sm">
                  <Calculator className="w-12 h-12 text-white" />
                </div>
                <h2 className="text-2xl font-bold">{metric.name}</h2>
                <p className="text-blue-100 mt-2 text-sm">{metric.question}</p>
              </div>
              <CardContent className="p-4">
                <div className="flex items-center gap-2 text-sm text-gray-500">
                  <Activity className="w-4 h-4" />
                  <span className="capitalize">{metric.category === 'margins' ? 'Márgenes' : metric.category === 'returns' ? 'Retornos' : metric.category === 'liquidity' ? 'Liquidez' : 'Solvencia'}</span>
                </div>
                {currentValue !== null && (
                  <div className="mt-4 p-4 bg-gray-50 rounded-lg">
                    <p className="text-xs text-gray-500 uppercase tracking-wide">Valor Actual</p>
                    <p className="text-3xl font-bold text-gray-900">{formatValue(currentValue)}</p>
                  </div>
                )}
              </CardContent>
            </Card>

            {/* Evaluation Card */}
            <Card>
              <CardHeader className="pb-3">
                <CardTitle className="text-lg">Evaluación de métrica</CardTitle>
              </CardHeader>
              <CardContent className="space-y-2">
                {metric.evaluation.map((eval_, idx) => {
                  const colors = getColorClasses(eval_.color);
                  const isActive = idx === activeEvaluation;
                  
                  return (
                    <div key={idx}>
                      <button
                        onClick={() => setActiveEvaluation(idx)}
                        className={`w-full flex items-center justify-between p-3 rounded-lg transition-all ${
                          isActive ? `${colors.bg} ${colors.border} border-2` : 'hover:bg-gray-50'
                        }`}
                      >
                        <div className="flex items-center gap-3">
                          <div className={`w-3 h-3 rounded-full ${colors.dot}`} />
                          <span className={`font-medium ${isActive ? colors.text : 'text-gray-700'}`}>
                            {eval_.level}
                          </span>
                        </div>
                        {isActive ? (
                          <ChevronDown className={`w-5 h-5 ${colors.arrow}`} />
                        ) : (
                          <ChevronRight className={`w-5 h-5 ${colors.arrow}`} />
                        )}
                      </button>
                      
                      {isActive && (
                        <div className={`mt-2 p-4 ${colors.bg} rounded-lg border ${colors.border}`}>
                          <p className={`text-xl font-bold ${colors.text} mb-2`}>{eval_.range}</p>
                          <p className="text-gray-700 text-sm">{eval_.description}</p>
                        </div>
                      )}
                    </div>
                  );
                })}
              </CardContent>
            </Card>
          </div>

          {/* Middle Column - Sections & Content */}
          <div className="lg:col-span-2 space-y-6">
            {/* Interactive Sections */}
            <Card>
              <div className="grid grid-cols-1 md:grid-cols-2 gap-0">
                {/* Section Buttons */}
                <div className="border-r border-gray-200">
                  {sections.map((section) => {
                    const Icon = section.icon;
                    const isActive = activeSection === section.id;
                    
                    return (
                      <button
                        key={section.id}
                        onClick={() => setActiveSection(section.id)}
                        className={`w-full flex items-center justify-between p-4 border-b border-gray-100 transition-all ${
                          isActive 
                            ? 'bg-blue-600 text-white' 
                            : 'hover:bg-gray-50 text-blue-600'
                        }`}
                      >
                        <div className="flex items-center gap-3">
                          <Icon className="w-5 h-5" />
                          <span className="font-medium">{section.label}</span>
                        </div>
                        <ChevronRight className={`w-5 h-5 ${isActive ? 'text-white' : ''}`} />
                      </button>
                    );
                  })}
                </div>

                {/* Section Content */}
                <div className="p-6">
                  <div className="flex items-center gap-3 mb-4">
                    {React.createElement(sections.find(s => s.id === activeSection)?.icon || HelpCircle, {
                      className: 'w-6 h-6 text-blue-600'
                    })}
                    <h3 className="text-xl font-semibold text-gray-900">
                      {sections.find(s => s.id === activeSection)?.label}
                    </h3>
                  </div>

                  {activeSection === 'whatMeasures' && (
                    <p className="text-gray-700 leading-relaxed">{metric.whatMeasures}</p>
                  )}

                  {activeSection === 'reasoning' && (
                    <p className="text-gray-700 leading-relaxed">{metric.reasoning}</p>
                  )}

                  {activeSection === 'relevance' && (
                    <p className="text-gray-700 leading-relaxed">{metric.relevance}</p>
                  )}

                  {activeSection === 'formula' && (
                    <div className="space-y-4">
                      <div className="bg-blue-50 border-2 border-blue-200 rounded-xl p-6">
                        <div className="text-center">
                          <div className="inline-block">
                            <div className="text-lg font-mono text-blue-800 mb-2">{metric.formula.numerator}</div>
                            <div className="border-t-2 border-blue-400 my-2"></div>
                            <div className="text-lg font-mono text-blue-800">{metric.formula.denominator}</div>
                          </div>
                        </div>
                        <p className="text-center mt-4 text-sm text-blue-700 font-medium">
                          {metric.name} = {metric.formula.numerator} / {metric.formula.denominator}
                        </p>
                      </div>
                      <div className="bg-gray-50 rounded-lg p-4">
                        <p className="text-xs uppercase tracking-wide text-gray-500 mb-2">Variables</p>
                        <ul className="space-y-1">
                          {metric.formula.variables.map((v, i) => (
                            <li key={i} className="flex items-center gap-2 text-sm text-gray-700">
                              <span className="w-1.5 h-1.5 bg-blue-500 rounded-full" />
                              {v}
                            </li>
                          ))}
                        </ul>
                      </div>
                    </div>
                  )}

                  {activeSection === 'relatedMetrics' && (
                    <div className="space-y-2">
                      {metric.relatedMetrics.map((relId) => {
                        const relMetric = metricDefinitions[relId];
                        return relMetric ? (
                          <button
                            key={relId}
                            onClick={() => navigate(`/metrics/${relId}`)}
                            className="w-full flex items-center justify-between p-3 bg-gray-50 rounded-lg hover:bg-blue-50 transition-colors"
                          >
                            <div>
                              <span className="font-medium text-gray-900">{relMetric.name}</span>
                              <span className="text-sm text-gray-500 ml-2">({relMetric.nameEn})</span>
                            </div>
                            <ChevronRight className="w-5 h-5 text-gray-400" />
                          </button>
                        ) : null;
                      })}
                    </div>
                  )}
                </div>
              </div>
            </Card>

            {/* Best/Worst Performers */}
            <Card>
              <CardHeader className="pb-2">
                <div className="flex gap-2">
                  <button
                    onClick={() => setPerformerTab('best')}
                    className={`px-4 py-2 rounded-lg font-medium flex items-center gap-2 transition-colors ${
                      performerTab === 'best' 
                        ? 'bg-blue-600 text-white' 
                        : 'bg-gray-100 text-gray-600 hover:bg-gray-200'
                    }`}
                  >
                    <TrendingUp className="w-4 h-4" />
                    Best Performers
                  </button>
                  <button
                    onClick={() => setPerformerTab('worst')}
                    className={`px-4 py-2 rounded-lg font-medium flex items-center gap-2 transition-colors ${
                      performerTab === 'worst' 
                        ? 'bg-red-500 text-white' 
                        : 'bg-gray-100 text-gray-600 hover:bg-gray-200'
                    }`}
                  >
                    <TrendingDown className="w-4 h-4" />
                    Worst Performers
                  </button>
                </div>
              </CardHeader>
              <CardContent>
                <p className="text-sm text-gray-600 mb-4">
                  {performerTab === 'best' 
                    ? `A continuación se muestran las industrias con mejor desempeño en "${metric.name}", donde esta métrica alcanza los valores más altos del mercado.`
                    : `Estas industrias típicamente muestran los valores más bajos de "${metric.name}" debido a la naturaleza de sus operaciones.`
                  }
                </p>
                <div className="grid grid-cols-2 sm:grid-cols-3 md:grid-cols-4 gap-4">
                  {(performerTab === 'best' ? metric.bestPerformers : metric.worstPerformers).map((perf, idx) => {
                    const Icon = getIcon(perf.icon);
                    return (
                      <div key={idx} className="bg-blue-50 rounded-xl p-4 text-center hover:shadow-md transition-shadow">
                        <div className="w-12 h-12 bg-white rounded-lg flex items-center justify-center mx-auto mb-2 shadow-sm">
                          <Icon className="w-6 h-6 text-blue-600" />
                        </div>
                        <p className="font-medium text-gray-800 text-sm">{perf.industry}</p>
                        <p className="text-xs text-blue-600 font-medium mt-1">{perf.typical}</p>
                      </div>
                    );
                  })}
                </div>
              </CardContent>
            </Card>

            {/* Expert Quote */}
            {metric.expertQuote && (
              <Card className="bg-gradient-to-r from-gray-50 to-blue-50">
                <CardContent className="p-6">
                  <div className="flex gap-4">
                    <div className="w-12 h-12 bg-blue-100 rounded-full flex items-center justify-center flex-shrink-0">
                      <Quote className="w-6 h-6 text-blue-600" />
                    </div>
                    <div>
                      <p className="text-gray-800 italic leading-relaxed">{metric.expertQuote.text}</p>
                      <p className="mt-3 text-sm">
                        <span className="font-semibold text-gray-900">— {metric.expertQuote.author}</span>
                        <span className="text-gray-500"> ({metric.expertQuote.source})</span>
                      </p>
                    </div>
                  </div>
                </CardContent>
              </Card>
            )}
          </div>
        </div>
      </div>
    </div>
  );
};

export default MetricDetail;
