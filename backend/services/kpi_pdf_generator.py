import io
from reportlab.lib.pagesizes import A4
from reportlab.lib import colors
from reportlab.lib.units import mm
from reportlab.pdfgen import canvas


def semaforo(valor, bueno, regular, inverso=False):
    if inverso:
        if valor <= bueno: return ('#E8F8F0', '#0F6E56', '#059669')
        if valor <= regular: return ('#FEF3E2', '#92400E', '#D97706')
        return ('#FEF2F2', '#991B1B', '#DC2626')
    else:
        if valor >= bueno: return ('#E8F8F0', '#0F6E56', '#059669')
        if valor >= regular: return ('#FEF3E2', '#92400E', '#D97706')
        return ('#FEF2F2', '#991B1B', '#DC2626')


# Azul corporativo — neutral para cards de info
INFO_CARD = ('#EFF6FF', '#1E40AF', '#1A56A8')


def build_kpi_pdf(data_dict: dict) -> io.BytesIO:
    buffer = io.BytesIO()
    W, H = A4
    c = canvas.Canvas(buffer, pagesize=A4)

    empresa = data_dict.get('empresa', 'Empresa')
    periodo = data_dict.get('periodo', '')
    rfc     = data_dict.get('rfc', '')

    NAVY  = colors.HexColor('#0D2B5E')   # Azul profundo corporativo
    BLUE  = colors.HexColor('#1A56A8')   # Azul medio corporativo
    BLUE2 = colors.HexColor('#3B82F6')   # Azul claro acento
    SLATE = colors.HexColor('#64748B')   # Slate gris
    WHITE = colors.white
    MGRAY = colors.HexColor('#64748B')

    def fmt(v):
        if v is None: return '$0'
        av = abs(v); s = '-' if v < 0 else ''
        if av >= 1_000_000: return f'{s}${av/1_000_000:.2f}M'
        if av >= 1_000: return f'{s}${av/1_000:.0f}K'
        return f'{s}${av:,.0f}'
    def fmtp(v): return f'{v:.1f}%'
    def fmtx(v): return f'{v:.2f}x'
    def fmtd(v): return f'{int(v)}d'

    # ── HEADER ─────────────────────────────────────────────────────────
    c.setFillColor(NAVY)
    c.rect(0, H - 32*mm, W, 32*mm, fill=1, stroke=0)
    c.setFillColor(BLUE)
    c.rect(0, H - 34*mm, W, 2*mm, fill=1, stroke=0)
    c.setFillColor(BLUE2)
    c.rect(0, H - 36*mm, W, 2*mm, fill=1, stroke=0)

    c.setFont('Helvetica-Bold', 20)
    c.setFillColor(WHITE)
    c.drawString(15*mm, H - 16*mm, empresa)
    c.setFont('Helvetica', 9)
    c.setFillColor(colors.HexColor('#93C5FD'))  # azul claro texto
    c.drawString(15*mm, H - 24*mm, f'Dashboard de Indicadores Financieros  •  {periodo}')
    c.setFont('Helvetica', 8)
    c.setFillColor(colors.HexColor('#BFDBFE'))
    c.drawRightString(W - 15*mm, H - 16*mm, f'RFC: {rfc}')
    c.drawRightString(W - 15*mm, H - 24*mm, 'TaxnFin · Claude Sonnet')

    # ── KPI CARD ───────────────────────────────────────────────────────
    def kpi_card(x, y, w, h, titulo, valor, subtitulo, sem_tuple):
        bg_hex, dark_hex, mid_hex = sem_tuple
        bg   = colors.HexColor(bg_hex)
        dark = colors.HexColor(dark_hex)
        mid  = colors.HexColor(mid_hex)

        # Sombra sutil
        c.setFillColor(colors.HexColor('#CBD5E1'))
        c.roundRect(x+0.8, y-0.8, w, h, 5, fill=1, stroke=0)
        # Fondo card
        c.setFillColor(bg)
        c.roundRect(x, y, w, h, 5, fill=1, stroke=0)
        # Barra top
        c.setFillColor(mid)
        c.roundRect(x, y+h-3.5, w, 3.5, 2, fill=1, stroke=0)
        # Borde izquierdo
        c.setFillColor(mid)
        c.rect(x, y, 3, h, fill=1, stroke=0)

        # Título
        c.setFont('Helvetica-Bold', 6.5)
        c.setFillColor(dark)
        c.drawString(x + 5.5*mm, y + h - 8.5*mm, titulo.upper())

        # Valor
        font_size = 15 if len(str(valor)) <= 8 else 12
        c.setFont('Helvetica-Bold', font_size)
        c.setFillColor(colors.HexColor('#0F172A'))
        c.drawString(x + 5.5*mm, y + h - 17*mm, str(valor))

        # Subtítulo
        c.setFont('Helvetica', 6.5)
        c.setFillColor(MGRAY)
        c.drawString(x + 5.5*mm, y + h - 24*mm, subtitulo)

        # Dot indicador
        c.setFillColor(mid)
        c.circle(x + w - 5.5*mm, y + h - 8.5*mm, 2.3, fill=1, stroke=0)

    # ── SECCIÓN ────────────────────────────────────────────────────────
    def seccion(y_pos, titulo):
        c.setFillColor(BLUE)
        c.rect(15*mm, y_pos - 2*mm, 3, 14, fill=1, stroke=0)
        c.setFont('Helvetica-Bold', 9.5)
        c.setFillColor(NAVY)
        c.drawString(20*mm, y_pos + 1.5*mm, titulo)
        c.setStrokeColor(colors.HexColor('#E2E8F0'))
        c.setLineWidth(0.5)
        c.line(20*mm, y_pos - 1*mm, W - 15*mm, y_pos - 1*mm)
        return y_pos - 8.5*mm

    d = data_dict
    cw  = (W - 32*mm) / 4
    ch  = 28*mm
    mg  = 15*mm
    gap = 1.5
    y   = H - 48*mm

    # 1. Estado de Resultados
    y = seccion(y, 'Estado de Resultados')
    for i, (t, v, s, sem) in enumerate([
        ('Ingresos',    fmt(d.get('ingresos',0)),        '100% base',                    INFO_CARD),
        ('Util. Bruta', fmt(d.get('utilidad_bruta',0)),  fmtp(d.get('margen_bruto',0)),  semaforo(d.get('margen_bruto',0),30,15)),
        ('EBITDA',      fmt(d.get('ebitda',0)),           fmtp(d.get('margen_ebitda',0)), semaforo(d.get('margen_ebitda',0),10,0)),
        ('Util. Neta',  fmt(d.get('utilidad_neta',0)),   fmtp(d.get('margen_neto',0)),   semaforo(d.get('margen_neto',0),5,0)),
    ]):
        kpi_card(mg + i*(cw+gap), y-ch, cw, ch, t, v, s, sem)
    y -= ch + 6*mm

    # 2. Márgenes y Retornos
    y = seccion(y, 'Márgenes y Retornos')
    for i, (t, v, s, sem) in enumerate([
        ('Margen Bruto',  fmtp(d.get('margen_bruto',0)),  'Meta: ≥30%', semaforo(d.get('margen_bruto',0),30,15)),
        ('Margen EBITDA', fmtp(d.get('margen_ebitda',0)), 'Meta: ≥10%', semaforo(d.get('margen_ebitda',0),10,0)),
        ('ROE',           fmtp(d.get('roe',0)),            'Meta: ≥10%', semaforo(d.get('roe',0),10,5)),
        ('ROIC',          fmtp(d.get('roic',0)),           'Meta: ≥8%',  semaforo(d.get('roic',0),8,3)),
    ]):
        kpi_card(mg + i*(cw+gap), y-ch, cw, ch, t, v, s, sem)
    y -= ch + 6*mm

    # 3. Liquidez
    y = seccion(y, 'Liquidez')
    for i, (t, v, s, sem) in enumerate([
        ('Razón Circ.',  fmtx(d.get('razon_circ',0)),    'Meta: ≥1.5x', semaforo(d.get('razon_circ',0),1.5,1.0)),
        ('Prueba Ácida', fmtx(d.get('prueba_acida',0)),  'Meta: ≥1.0x', semaforo(d.get('prueba_acida',0),1.0,0.5)),
        ('Cash Runway',  f"{d.get('cash_runway',0):.1f}m", 'Meta: ≥3m', semaforo(d.get('cash_runway',0),3,1)),
        ('ROA',          fmtp(d.get('roa',0)),            'Meta: ≥5%',   semaforo(d.get('roa',0),5,2)),
    ]):
        kpi_card(mg + i*(cw+gap), y-ch, cw, ch, t, v, s, sem)
    y -= ch + 6*mm

    # 4. Ciclo Operativo
    y = seccion(y, 'Ciclo Operativo')
    for i, (t, v, s, sem) in enumerate([
        ('DSO Cobro', fmtd(d.get('dso',0)), 'Meta: ≤60d',  semaforo(d.get('dso',0),60,90,True)),
        ('DIO Inv.',  fmtd(d.get('dio',0)), 'Meta: ≤90d',  semaforo(d.get('dio',0),90,120,True)),
        ('DPO Pago',  fmtd(d.get('dpo',0)), 'Meta: ≥45d',  semaforo(d.get('dpo',0),45,30)),
        ('CCE',       fmtd(d.get('ccc',0)), 'Meta: ≤90d',  semaforo(d.get('ccc',0),90,120,True)),
    ]):
        kpi_card(mg + i*(cw+gap), y-ch, cw, ch, t, v, s, sem)
    y -= ch + 6*mm

    # 5. Solvencia y Balance
    y = seccion(y, 'Solvencia y Balance')
    for i, (t, v, s, sem) in enumerate([
        ('Deuda/Activos', fmtp(d.get('deuda_activos',0)), 'Meta: ≤40%',      semaforo(d.get('deuda_activos',0),40,60,True)),
        ('Deuda/EBITDA',  fmtx(d.get('deuda_ebitda',0)), 'Meta: ≤3x',       semaforo(d.get('deuda_ebitda',0),3,5,True)),
        ('Activo Total',  fmt(d.get('activo_total',0)),   'Base patrimonial', INFO_CARD),
        ('Capital',       fmt(d.get('capital',0)),        'Patrimonio neto',  semaforo(d.get('capital',0),0,0)),
    ]):
        kpi_card(mg + i*(cw+gap), y-ch, cw, ch, t, v, s, sem)

    # ── FOOTER ─────────────────────────────────────────────────────────
    c.setFillColor(NAVY)
    c.rect(0, 0, W, 11*mm, fill=1, stroke=0)
    c.setFillColor(BLUE2)
    c.rect(0, 11*mm, W, 1, fill=1, stroke=0)
    c.setFont('Helvetica', 7)
    c.setFillColor(colors.HexColor('#93C5FD'))
    c.drawString(15*mm, 4*mm, f'{empresa}  •  Dashboard KPIs  •  {periodo}  •  RFC: {rfc}')
    c.drawRightString(W-15*mm, 4*mm, 'Analisis: TaxnFin · Claude Sonnet')

    c.save()
    buffer.seek(0)
    return buffer
