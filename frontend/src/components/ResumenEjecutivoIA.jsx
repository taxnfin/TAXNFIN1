import { useState, useEffect, useRef } from "react";

const TEAL = "#1A7A8A";
const NAVY = "#0D1B2A";
const GOLD = "#C8A84B";

const fmt = (n) => {
  if (Math.abs(n) >= 1_000_000) return `$${(n / 1_000_000).toFixed(2)}M`;
  if (Math.abs(n) >= 1_000) return `$${(n / 1_000).toFixed(0)}K`;
  return `$${n.toLocaleString()}`;
};

const defaultFinancialData = {
  empresa: "KARY",
  periodo: "Enero 2026",
  rfc: "VICK8997654",
  ingresos: 2_329_327,
  costoVentas: 1_765_993,
  utilidadBruta: 563_334,
  gastosOp: 759_924,
  ebitda: -167_339,
  utilidadNeta: -117_430,
  activoTotal: 28_771_329,
  activoCirc: 25_246_100,
  pasivoTotal: 12_503_539,
  capital: 16_637_979,
  margenBruto: 24.2,
  margenEbitda: -7.2,
  margenNeto: -5.0,
  razonCirculante: 2.66,
  pruebaAcida: 1.41,
  cashRunway: 0.4,
  dso: 137,
  dio: 201,
  dpo: 95,
  ccc: 244,
};

const KPICard = ({ label, value, sub, status }) => {
  const statusColors = {
    good:    { bg: "#F0F7EC", labelColor: "#5A8A3A", valueColor: "#1E4A0E", subColor: "#5A8A3A", border: "#A8D080", accent: "#5A8A3A" },
    warn:    { bg: "#FDF5E8", labelColor: "#8A6020", valueColor: "#4A2E08", subColor: "#8A6020", border: "#D4A855", accent: "#B07A28" },
    bad:     { bg: "#FBF0EF", labelColor: "#8A3030", valueColor: "#5A1818", subColor: "#8A3030", border: "#D08080", accent: "#C04040" },
    neutral: { bg: "#F0F4F8", labelColor: "#506070", valueColor: "#1C2B3A", subColor: "#506070", border: "#C0CDD8", accent: "#506070" },
  };
  const c = statusColors[status] || statusColors.neutral;
  return (
    <div style={{
      background: c.bg,
      border: `1px solid ${c.border}`,
      borderTop: `3px solid ${c.accent}`,
      borderRadius: 8,
      padding: "14px 16px 12px",
      minWidth: 0,
    }}>
      <div style={{ fontSize: 10, color: c.labelColor, fontWeight: 700, marginBottom: 6, letterSpacing: 0.8, textTransform: "uppercase" }}>{label}</div>
      <div style={{ fontSize: 24, fontWeight: 800, color: c.valueColor, lineHeight: 1, marginBottom: 5 }}>{value}</div>
      {sub && <div style={{ fontSize: 11, color: c.subColor, fontWeight: 500 }}>{sub}</div>}
    </div>
  );
};

const SemaforoBadge = ({ status }) => {
  const map = {
    "Crítico": { bg: "#FCEBEB", text: "#A32D2D", dot: "#E24B4A" },
    "Atención": { bg: "#FAEEDA", text: "#854F0B", dot: "#BA7517" },
    "Bueno": { bg: "#EAF3DE", text: "#3B6D11", dot: "#639922" },
  };
  const s = map[status] || map["Atención"];
  return (
    <span style={{ background: s.bg, color: s.text, border: `1px solid ${s.dot}`, borderRadius: 20, padding: "2px 9px", fontSize: 11, fontWeight: 600, whiteSpace: "nowrap" }}>
      <span style={{ color: s.dot, marginRight: 4 }}>●</span>{status}
    </span>
  );
};

const StreamingText = ({ text, isStreaming }) => {
  const endRef = useRef(null);
  useEffect(() => {
    if (isStreaming) endRef.current?.scrollIntoView({ behavior: "smooth", block: "nearest" });
  }, [text, isStreaming]);

  const lines = text.split("\n");
  return (
    <div style={{ fontSize: 14, lineHeight: 1.75, color: "#2D3748" }}>
      {lines.map((line, i) => {
        if (line.startsWith("## ")) return <h3 key={i} style={{ fontSize: 15, fontWeight: 700, color: NAVY, margin: "16px 0 6px", borderBottom: `2px solid ${TEAL}`, paddingBottom: 4 }}>{line.slice(3)}</h3>;
        if (line.startsWith("### ")) return <h4 key={i} style={{ fontSize: 13, fontWeight: 700, color: TEAL, margin: "12px 0 4px" }}>{line.slice(4)}</h4>;
        if (line.startsWith("**") && line.endsWith("**")) return <p key={i} style={{ fontWeight: 700, color: NAVY, margin: "8px 0 2px" }}>{line.slice(2, -2)}</p>;
        if (line.startsWith("- ") || line.startsWith("• ")) return (
          <div key={i} style={{ display: "flex", gap: 8, margin: "3px 0" }}>
            <span style={{ color: TEAL, fontWeight: 700, flexShrink: 0 }}>▸</span>
            <span>{parseBold(line.slice(2))}</span>
          </div>
        );
        if (line.trim() === "") return <div key={i} style={{ height: 8 }} />;
        return <p key={i} style={{ margin: "4px 0" }}>{parseBold(line)}</p>;
      })}
      <div ref={endRef} />
    </div>
  );
};

function parseBold(text) {
  const parts = text.split(/(\*\*[^*]+\*\*)/g);
  return parts.map((p, i) =>
    p.startsWith("**") && p.endsWith("**")
      ? <strong key={i} style={{ color: NAVY }}>{p.slice(2, -2)}</strong>
      : p
  );
}

const ProgressBar = ({ value, max = 100, color }) => (
  <div style={{ background: "#E8ECF0", borderRadius: 6, height: 8, overflow: "hidden" }}>
    <div style={{ width: `${Math.min(Math.abs(value / max) * 100, 100)}%`, background: color, height: "100%", borderRadius: 6, transition: "width 0.8s ease" }} />
  </div>
);

export default function ResumenEjecutivoIA({ financialData = defaultFinancialData }) {
  const [analysis, setAnalysis] = useState("");
  const [isLoading, setIsLoading] = useState(false);
  const [isStreaming, setIsStreaming] = useState(false);
  const [activeTab, setActiveTab] = useState("resumen");
  const [error, setError] = useState("");
  const [generated, setGenerated] = useState(false);

  const d = financialData;

  const kpis = [
    { label: "Ingresos", value: fmt(d.ingresos), sub: "100%", status: "neutral" },
    { label: "Util. Bruta", value: fmt(d.utilidadBruta), sub: `${d.margenBruto}%`, status: d.margenBruto >= 25 ? "good" : "warn" },
    { label: "EBITDA", value: fmt(d.ebitda), sub: `${d.margenEbitda}%`, status: d.ebitda >= 0 ? "good" : "bad" },
    { label: "Util. Neta", value: fmt(d.utilidadNeta), sub: `${d.margenNeto}%`, status: d.utilidadNeta >= 0 ? "good" : "bad" },
  ];

  const liquidezKpis = [
    { label: "Razón Circulante", value: `${d.razonCirculante}x`, status: d.razonCirculante >= 1.5 ? "Bueno" : "Crítico" },
    { label: "Prueba Ácida", value: `${d.pruebaAcida}x`, status: d.pruebaAcida >= 1.0 ? "Bueno" : "Atención" },
    { label: "Cash Runway", value: `${d.cashRunway} meses`, status: d.cashRunway >= 3 ? "Bueno" : "Crítico" },
    { label: "CCE", value: `${d.ccc} días`, status: d.ccc <= 90 ? "Bueno" : d.ccc <= 150 ? "Atención" : "Crítico" },
  ];

  const buildPrompt = () => `Eres el CFO IA de TaxnFin. Analiza estos datos financieros de ${d.empresa} para el período ${d.periodo} y genera un Resumen Ejecutivo profesional y accionable en español.

DATOS FINANCIEROS:
- Ingresos: $${d.ingresos.toLocaleString()} MXN
- Costo de Ventas: $${d.costoVentas.toLocaleString()} (${((d.costoVentas/d.ingresos)*100).toFixed(1)}% de ventas)
- Utilidad Bruta: $${d.utilidadBruta.toLocaleString()} (Margen: ${d.margenBruto}%)
- Gastos Operativos: $${d.gastosOp.toLocaleString()} (${((d.gastosOp/d.ingresos)*100).toFixed(1)}% de ventas)
- EBITDA: $${d.ebitda.toLocaleString()} (${d.margenEbitda}%)
- Utilidad Neta: $${d.utilidadNeta.toLocaleString()} (${d.margenNeto}%)
- Activo Total: $${d.activoTotal.toLocaleString()}
- Capital Contable: $${d.capital.toLocaleString()}
- Razón Circulante: ${d.razonCirculante}x | Prueba Ácida: ${d.pruebaAcida}x | Cash Runway: ${d.cashRunway} meses
- DSO (días cobro): ${d.dso} | DIO (días inventario): ${d.dio} | DPO (días pago): ${d.dpo} | CCE: ${d.ccc} días

INSTRUCCIONES:
1. Genera un análisis narrativo profundo en 3 secciones usando formato Markdown con ## para títulos
2. Sección 1 ## Diagnóstico Principal — Qué está pasando realmente, cuál es la historia detrás de los números
3. Sección 2 ## Riesgos Críticos — Top 3 riesgos con impacto cuantificado cuando sea posible
4. Sección 3 ## Acciones Inmediatas — 3-5 acciones concretas con métricas objetivo
5. Usa lenguaje directo, financiero y ejecutivo. Nada de frases genéricas.
6. Cuantifica todo lo posible. Si hay brecha vs benchmark, menciónala.
7. Tono: CFO hablando a otro CFO. Conciso, honesto, orientado a resultados.`;

  const generateAnalysis = async () => {
    setIsLoading(true);
    setIsStreaming(false);
    setError("");
    setAnalysis("");
    setGenerated(false);

    try {
      const response = await fetch("https://api.anthropic.com/v1/messages", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          model: "claude-sonnet-4-20250514",
          max_tokens: 1000,
          stream: true,
          messages: [{ role: "user", content: buildPrompt() }],
        }),
      });

      if (!response.ok) throw new Error(`API error ${response.status}`);

      setIsLoading(false);
      setIsStreaming(true);

      const reader = response.body.getReader();
      const decoder = new TextDecoder();
      let buffer = "";

      while (true) {
        const { done, value } = await reader.read();
        if (done) break;
        buffer += decoder.decode(value, { stream: true });
        const lines = buffer.split("\n");
        buffer = lines.pop();

        for (const line of lines) {
          if (!line.startsWith("data: ")) continue;
          const raw = line.slice(6).trim();
          if (raw === "[DONE]") continue;
          try {
            const evt = JSON.parse(raw);
            if (evt.type === "content_block_delta" && evt.delta?.text) {
              setAnalysis(prev => prev + evt.delta.text);
            }
          } catch {}
        }
      }

      setIsStreaming(false);
      setGenerated(true);
    } catch (err) {
      setIsLoading(false);
      setIsStreaming(false);
      setError(`Error al generar el análisis: ${err.message}`);
    }
  };

  const tabs = [
    { id: "resumen", label: "Resumen" },
    { id: "liquidez", label: "Liquidez" },
    { id: "ia", label: "Análisis IA" },
  ];

  return (
    <div style={{ fontFamily: "'Inter', system-ui, sans-serif", maxWidth: 860, margin: "0 auto", background: "#fff" }}>

      {/* Header */}
      <div style={{ background: "#1C2B3A", borderRadius: "12px 12px 0 0", padding: "20px 24px 16px", display: "flex", justifyContent: "space-between", alignItems: "flex-end" }}>
        <div>
          <div style={{ fontSize: 11, color: "#A8D8E0", letterSpacing: 1.5, textTransform: "uppercase", marginBottom: 4 }}>Reporte Ejecutivo Mensual</div>
          <div style={{ fontSize: 24, fontWeight: 800, color: "#fff", letterSpacing: -0.5 }}>{d.empresa}</div>
          <div style={{ fontSize: 13, color: GOLD, fontWeight: 600, marginTop: 2 }}>{d.periodo} · RFC: {d.rfc}</div>
        </div>
        <div style={{ textAlign: "right" }}>
          <div style={{ fontSize: 11, color: "#6B8A9A", marginBottom: 2 }}>Análisis por</div>
          <div style={{ fontSize: 13, color: TEAL, fontWeight: 600 }}>TaxnFin · Claude Sonnet</div>
        </div>
      </div>

      {/* Accent bar */}
      <div style={{ height: 3, background: `linear-gradient(90deg, ${TEAL} 0%, ${GOLD} 100%)` }} />

      {/* KPI Cards */}
      <div style={{ padding: "16px 24px", background: "#F8FAFC", borderBottom: "1px solid #DDE3EA" }}>
        <div style={{ display: "grid", gridTemplateColumns: "repeat(4, 1fr)", gap: 10 }}>
          {kpis.map(k => <KPICard key={k.label} {...k} />)}
        </div>
      </div>

      {/* Tabs */}
      <div style={{ display: "flex", borderBottom: "1px solid #DDE3EA", padding: "0 24px", background: "#FFFFFF" }}>
        {tabs.map(t => (
          <button key={t.id} onClick={() => setActiveTab(t.id)} style={{
            padding: "10px 18px", border: "none", cursor: "pointer", fontSize: 13, fontWeight: activeTab === t.id ? 700 : 500,
            color: activeTab === t.id ? TEAL : "#64748B",
            borderBottom: `2.5px solid ${activeTab === t.id ? TEAL : "transparent"}`,
            background: "transparent", transition: "all 0.2s", marginBottom: -1,
          }}>{t.label}{t.id === "ia" && <span style={{ marginLeft: 6, background: "#E1F5EE", color: "#0F6E56", fontSize: 9, fontWeight: 700, padding: "2px 6px", borderRadius: 10, letterSpacing: 0.5 }}>IA</span>}
          </button>
        ))}
      </div>

      {/* Tab content */}
      <div style={{ padding: "20px 24px", minHeight: 300, background: "#FFFFFF" }}>

        {/* RESUMEN TAB */}
        {activeTab === "resumen" && (
          <div>
            <div style={{ marginBottom: 16 }}>
              <h3 style={{ fontSize: 14, fontWeight: 700, color: NAVY, marginBottom: 12 }}>Estado de Resultados</h3>
              {[
                { label: "Ingresos", value: d.ingresos, pct: 100, color: TEAL },
                { label: "(-) Costo Ventas", value: -d.costoVentas, pct: (d.costoVentas/d.ingresos)*100, color: "#C0392B" },
                { label: "= Util. Bruta", value: d.utilidadBruta, pct: d.margenBruto, color: TEAL, bold: true },
                { label: "(-) Gastos Op.", value: -d.gastosOp, pct: (d.gastosOp/d.ingresos)*100, color: "#E67E22" },
                { label: "= EBITDA", value: d.ebitda, pct: Math.abs(d.margenEbitda), color: "#C0392B", bold: true },
                { label: "= Util. Neta", value: d.utilidadNeta, pct: Math.abs(d.margenNeto), color: "#C0392B", bold: true },
              ].map((row, i) => (
                <div key={i} style={{ display: "grid", gridTemplateColumns: "180px 100px 1fr 50px", gap: 10, alignItems: "center", padding: "5px 0", borderBottom: row.bold ? `1px solid #E8ECF0` : "none" }}>
                  <span style={{ fontSize: 13, fontWeight: row.bold ? 700 : 400, color: row.bold ? NAVY : "#4A5568" }}>{row.label}</span>
                  <span style={{ fontSize: 13, fontWeight: row.bold ? 700 : 500, color: row.value >= 0 ? "#27AE60" : "#C0392B", textAlign: "right" }}>{fmt(row.value)}</span>
                  <ProgressBar value={row.pct} max={100} color={row.color} />
                  <span style={{ fontSize: 11, color: "#718096", textAlign: "right" }}>{row.pct.toFixed(1)}%</span>
                </div>
              ))}
            </div>

            <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: 16, marginTop: 20 }}>
              <div style={{ background: "#F8FAFC", borderRadius: 8, padding: "14px 16px", border: "1px solid #E8ECF0" }}>
                <div style={{ fontSize: 12, fontWeight: 700, color: NAVY, marginBottom: 10, textTransform: "uppercase", letterSpacing: 0.5 }}>Balance — Estructura</div>
                {[
                  ["Activo Total", fmt(d.activoTotal)],
                  ["Activo Circulante", fmt(d.activoCirc)],
                  ["Pasivo Total", fmt(d.pasivoTotal)],
                  ["Capital Contable", fmt(d.capital)],
                ].map(([l, v]) => (
                  <div key={l} style={{ display: "flex", justifyContent: "space-between", fontSize: 13, padding: "3px 0", borderBottom: "1px solid #EDF2F7" }}>
                    <span style={{ color: "#718096" }}>{l}</span>
                    <span style={{ fontWeight: 600, color: NAVY }}>{v}</span>
                  </div>
                ))}
              </div>
              <div style={{ background: "#FFF8F0", borderRadius: 8, padding: "14px 16px", border: "1px solid #FDEBD0" }}>
                <div style={{ fontSize: 12, fontWeight: 700, color: "#854F0B", marginBottom: 10, textTransform: "uppercase", letterSpacing: 0.5 }}>⚠ Puntos de Atención</div>
                {[
                  "Gastos Op. $759K > Util. Bruta $563K",
                  "EBITDA negativo: -$167K (-7.2%)",
                  "Cash Runway crítico: 0.4 meses",
                  "CCE de 244 días (benchmark: 60-90d)",
                ].map((t, i) => (
                  <div key={i} style={{ fontSize: 12, color: "#7D3C00", padding: "3px 0", display: "flex", gap: 6 }}>
                    <span style={{ color: "#E67E22", flexShrink: 0 }}>▸</span>{t}
                  </div>
                ))}
              </div>
            </div>
          </div>
        )}

        {/* LIQUIDEZ TAB */}
        {activeTab === "liquidez" && (
          <div>
            <div style={{ display: "grid", gridTemplateColumns: "repeat(4, 1fr)", gap: 10, marginBottom: 20 }}>
              {liquidezKpis.map(k => (
                <div key={k.label} style={{ background: "#F8FAFC", borderRadius: 8, padding: "12px", border: "1px solid #E8ECF0", textAlign: "center" }}>
                  <div style={{ fontSize: 11, color: "#718096", marginBottom: 4, fontWeight: 600 }}>{k.label}</div>
                  <div style={{ fontSize: 20, fontWeight: 700, color: NAVY, marginBottom: 6 }}>{k.value}</div>
                  <SemaforoBadge status={k.status} />
                </div>
              ))}
            </div>

            <div style={{ marginBottom: 20 }}>
              <h3 style={{ fontSize: 14, fontWeight: 700, color: NAVY, marginBottom: 12 }}>Ciclo de Conversión de Efectivo — {d.ccc} días</h3>
              <div style={{ position: "relative", height: 70, background: "#F8FAFC", borderRadius: 8, border: "1px solid #E8ECF0", overflow: "hidden", marginBottom: 8 }}>
                <div style={{ position: "absolute", left: 0, top: 14, height: 42, width: `${(d.dio/(d.dio+d.dso))*100}%`, background: TEAL, opacity: 0.85, display: "flex", alignItems: "center", justifyContent: "center" }}>
                  <span style={{ fontSize: 11, fontWeight: 700, color: "#fff" }}>DIO {d.dio}d</span>
                </div>
                <div style={{ position: "absolute", left: `${(d.dio/(d.dio+d.dso))*100}%`, top: 14, height: 42, width: `${(d.dso/(d.dio+d.dso))*100}%`, background: "#1A9ABE", opacity: 0.85, display: "flex", alignItems: "center", justifyContent: "center" }}>
                  <span style={{ fontSize: 11, fontWeight: 700, color: "#fff" }}>DSO {d.dso}d</span>
                </div>
              </div>
              <div style={{ fontSize: 12, color: "#718096", background: "#FAEEDA", borderRadius: 6, padding: "8px 12px", border: "1px solid #F5CBA7" }}>
                <strong style={{ color: "#7D3C00" }}>Diagnóstico:</strong> El inventario (201 días) y la cartera (137 días) atrapan efectivo. Reducir ambos a benchmarks (90d/60d) liberaría aprox. <strong style={{ color: NAVY }}>$3.4M en efectivo</strong>.
              </div>
            </div>

            <table style={{ width: "100%", borderCollapse: "collapse", fontSize: 13 }}>
              <thead>
                <tr style={{ background: NAVY }}>
                  {["Indicador", "Valor", "Benchmark", "Brecha", "Estado"].map(h => (
                    <th key={h} style={{ padding: "8px 10px", color: "#fff", fontWeight: 600, textAlign: h === "Indicador" ? "left" : "center", fontSize: 11 }}>{h}</th>
                  ))}
                </tr>
              </thead>
              <tbody>
                {[
                  ["Razón Circulante", "2.66x", ">1.5x", "+1.16x", "Bueno"],
                  ["Prueba Ácida", "1.41x", ">1.0x", "+0.41x", "Bueno"],
                  ["Razón de Efectivo", "0.03x", ">0.2x", "-0.17x", "Crítico"],
                  ["Cash Runway", "0.4 meses", "3-6m", "-2.6m", "Crítico"],
                  ["DSO", "137 días", "30-60d", "+77d", "Crítico"],
                  ["DIO", "201 días", "45-90d", "+111d", "Crítico"],
                  ["DPO", "95 días", "30-60d", "+35d", "Atención"],
                  ["CCE", "244 días", "60-90d", "+154d", "Crítico"],
                ].map(([ind, val, bm, br, st], i) => (
                  <tr key={i} style={{ background: i % 2 === 0 ? "#fff" : "#F8FAFC" }}>
                    <td style={{ padding: "7px 10px", color: "#4A5568" }}>{ind}</td>
                    <td style={{ padding: "7px 10px", textAlign: "center", fontWeight: 600, color: NAVY }}>{val}</td>
                    <td style={{ padding: "7px 10px", textAlign: "center", color: "#718096" }}>{bm}</td>
                    <td style={{ padding: "7px 10px", textAlign: "center", color: br.startsWith("+") ? "#27AE60" : "#C0392B", fontWeight: 600 }}>{br}</td>
                    <td style={{ padding: "7px 10px", textAlign: "center" }}><SemaforoBadge status={st} /></td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}

        {/* IA TAB */}
        {activeTab === "ia" && (
          <div>
            {!generated && !isLoading && !isStreaming && (
              <div style={{ textAlign: "center", padding: "40px 20px" }}>
                <div style={{ fontSize: 40, marginBottom: 16 }}>🤖</div>
                <div style={{ fontSize: 16, fontWeight: 700, color: NAVY, marginBottom: 8 }}>Análisis Ejecutivo con IA</div>
                <div style={{ fontSize: 13, color: "#718096", maxWidth: 420, margin: "0 auto 24px", lineHeight: 1.6 }}>
                  Genera un análisis narrativo profundo de los KPIs financieros con diagnóstico, riesgos y recomendaciones accionables.
                </div>
                <button onClick={generateAnalysis} style={{
                  background: TEAL, color: "#fff", border: "none", borderRadius: 8,
                  padding: "12px 28px", fontSize: 14, fontWeight: 700, cursor: "pointer",
                  display: "inline-flex", alignItems: "center", gap: 8,
                }}>
                  ✦ Generar Análisis IA
                </button>
              </div>
            )}

            {isLoading && (
              <div style={{ display: "flex", flexDirection: "column", alignItems: "center", padding: "40px 0", gap: 16 }}>
                <div style={{ width: 40, height: 40, border: `3px solid #E8ECF0`, borderTop: `3px solid ${TEAL}`, borderRadius: "50%", animation: "spin 1s linear infinite" }} />
                <div style={{ fontSize: 13, color: "#718096" }}>Conectando con Claude Sonnet...</div>
                <style>{`@keyframes spin { to { transform: rotate(360deg); } }`}</style>
              </div>
            )}

            {error && (
              <div style={{ background: "#FCEBEB", border: "1px solid #E24B4A", borderRadius: 8, padding: "12px 16px", color: "#A32D2D", fontSize: 13, marginBottom: 16 }}>
                {error}
                <button onClick={generateAnalysis} style={{ marginLeft: 12, background: "none", border: "1px solid #E24B4A", borderRadius: 4, padding: "3px 10px", color: "#A32D2D", cursor: "pointer", fontSize: 12 }}>Reintentar</button>
              </div>
            )}

            {(isStreaming || generated) && analysis && (
              <div>
                {isStreaming && (
                  <div style={{ display: "flex", alignItems: "center", gap: 8, marginBottom: 12, fontSize: 12, color: TEAL, fontWeight: 600 }}>
                    <span style={{ width: 8, height: 8, borderRadius: "50%", background: TEAL, animation: "pulse 1s infinite" }} />
                    Generando análisis...
                    <style>{`@keyframes pulse { 0%,100%{opacity:1} 50%{opacity:0.3} }`}</style>
                  </div>
                )}
                <div style={{ background: "#F8FAFC", borderRadius: 10, padding: "20px", border: "1px solid #E8ECF0", maxHeight: 480, overflowY: "auto" }}>
                  <StreamingText text={analysis} isStreaming={isStreaming} />
                </div>
                {generated && (
                  <div style={{ display: "flex", justifyContent: "flex-end", marginTop: 12 }}>
                    <button onClick={generateAnalysis} style={{
                      background: "none", border: `1px solid ${TEAL}`, borderRadius: 6,
                      padding: "7px 16px", color: TEAL, cursor: "pointer", fontSize: 12, fontWeight: 600,
                    }}>↻ Regenerar análisis</button>
                  </div>
                )}
              </div>
            )}
          </div>
        )}
      </div>

      {/* Footer */}
      <div style={{ background: "#1C2B3A", borderRadius: "0 0 12px 12px", padding: "10px 24px", display: "flex", justifyContent: "space-between", alignItems: "center" }}>
        <span style={{ fontSize: 11, color: "#6B8A9A" }}>TaxnFin · cashflow.taxnfin.com</span>
        <span style={{ fontSize: 11, color: "#6B8A9A" }}>Cifras en MXN · {d.periodo}</span>
      </div>
    </div>
  );
}
