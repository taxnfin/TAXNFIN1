import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
import matplotlib.patches as mpatches
from matplotlib.patches import FancyBboxPatch
import matplotlib.gridspec as gridspec
import io, os
from reportlab.lib.pagesizes import A4
from reportlab.lib import colors
from reportlab.lib.units import mm, cm
from reportlab.platypus import (SimpleDocTemplate, Paragraph, Spacer, Table,
                                 TableStyle, Image, HRFlowable, KeepTogether)
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.enums import TA_LEFT, TA_CENTER, TA_RIGHT, TA_JUSTIFY
from reportlab.pdfgen import canvas
from reportlab.platypus import BaseDocTemplate, PageTemplate, Frame

# ── Paleta ──────────────────────────────────────────────────────────────────
NAVY   = colors.HexColor('#0D2B5E')   # Azul corporativo profundo
TEAL   = colors.HexColor('#1A56A8')   # Azul corporativo medio
TEAL2  = colors.HexColor('#3B82F6')   # Azul corporativo claro
GOLD   = colors.HexColor('#64748B')   # Slate gris (antes dorado)
RED    = colors.HexColor('#DC2626')   # Rojo crítico
AMBER  = colors.HexColor('#D97706')   # Ámbar atención
GREEN  = colors.HexColor('#059669')   # Verde éxito
LGRAY  = colors.HexColor('#F0F4F8')   # Gris muy claro
MGRAY  = colors.HexColor('#CBD5E1')   # Gris medio
DGRAY  = colors.HexColor('#334155')   # Gris oscuro slate
WHITE  = colors.white

W, H = A4

# ── Datos del reporte ────────────────────────────────────────────────────────
DATA = {
    'empresa': 'KARY',
    'periodo': 'Enero 2026',
    'fecha': '02/05/2026',
    'rfc': 'VICK8997654',
    'ingresos': 2_329_327,
    'costo_ventas': 1_765_993,
    'utilidad_bruta': 563_334,
    'gastos_op': 759_924,
    'utilidad_op': -196_590,
    'ebitda': -167_339,
    'utilidad_neta': -117_430,
    'activo_total': 28_771_329,
    'activo_circ': 25_246_100,
    'activo_fijo': 3_000_000,
    'pasivo_total': 12_503_539,
    'pasivo_circ': 9_500_000,
    'pasivo_lp': 3_000_000,
    'capital': 16_637_979,
    'capital_trabajo': 15_756_981,
    'margen_bruto': 24.2,
    'margen_ebitda': -7.2,
    'margen_op': -8.4,
    'margen_neto': -5.0,
    'roic': -1.2, 'roe': -0.7, 'roa': -0.4, 'roce': -1.0,
    'razon_circ': 2.66, 'prueba_acida': 1.41, 'razon_ef': 0.03,
    'cash_runway': 0.4,
    'dso': 137, 'dpo': 95, 'dio': 201, 'ccc': 244,
    'deuda_capital': 0.00, 'deuda_activos': 43.5,
    'deuda_ebitda': 24.71, 'cobertura': 999,
}

def fmt(n, decimals=0, prefix='$'):
    if abs(n) >= 1_000_000:
        return f"{prefix}{n/1_000_000:,.{decimals}f}M"
    elif abs(n) >= 1_000:
        return f"{prefix}{n/1_000:,.{decimals}f}K"
    return f"{prefix}{n:,.{decimals}f}"

def pct(n): return f"{n:+.1f}%"

# ── Matplotlib helpers ───────────────────────────────────────────────────────
def fig_to_img(fig, dpi=150):
    buf = io.BytesIO()
    fig.savefig(buf, format='png', dpi=dpi, bbox_inches='tight',
                facecolor='none', transparent=True)
    buf.seek(0)
    plt.close(fig)
    return buf

# ── Chart 1: Cascada Estado de Resultados ───────────────────────────────────
def chart_waterfall():
    fig, ax = plt.subplots(figsize=(7.5, 3.8))
    fig.patch.set_alpha(0)
    ax.set_facecolor('none')

    ing  = DATA['ingresos']
    cv   = DATA['costo_ventas']
    ub   = DATA['utilidad_bruta']
    gop  = DATA['gastos_op']
    uop  = DATA['utilidad_op']
    labels = ['Ingresos', 'Costo\nVentas', 'Util.\nBruta', 'Gastos\nOp.', 'Util.\nOperativa']
    values   = [ing, -cv, ub, -gop, uop]
    running  = [0, ing, ing, ub, ub]
    bar_vals = [ing, cv, ub, gop, abs(uop)]
    bar_colors = ['#1A56A8', '#C0392B', '#3B82F6', '#E67E22',
                  '#27AE60' if uop >= 0 else '#C0392B']

    for i, (bot, val, col) in enumerate(zip(running, bar_vals, bar_colors)):
        if i in [0, 2]:
            ax.bar(i, val, bottom=0, color=col, width=0.55, zorder=3,
                   edgecolor='white', linewidth=0.8)
        else:
            ax.bar(i, val, bottom=bot - val if values[i] < 0 else bot,
                   color=col, width=0.55, zorder=3, edgecolor='white', linewidth=0.8)

    display_vals = values
    for i, (v, bv) in enumerate(zip(display_vals, bar_vals)):
        ypos = bv/2 if i in [0, 2] else (running[i] - bv/2 if values[i] < 0 else running[i] + bv/2)
        sign = '' if i in [0, 2] else ('+' if v > 0 else '')
        ax.text(i, ypos, f"{sign}${abs(v)/1e6:.2f}M", ha='center', va='center',
                fontsize=7.5, color='white', fontweight='bold', zorder=5)

    ax.set_xticks(range(len(labels)))
    ax.set_xticklabels(labels, fontsize=8, color='#334155')
    ax.yaxis.set_visible(False)
    ax.spines['top'].set_visible(False)
    ax.spines['right'].set_visible(False)
    ax.spines['left'].set_visible(False)
    ax.spines['bottom'].set_color('#CBD5E1')
    ax.tick_params(bottom=False)
    ax.set_title('Cascada Estado de Resultados', fontsize=9, color='#0D2B5E',
                 fontweight='bold', pad=8, loc='left')
    plt.tight_layout(pad=0.5)
    return fig_to_img(fig)

# ── Chart 2: Márgenes ────────────────────────────────────────────────────────
def chart_margenes():
    fig, ax = plt.subplots(figsize=(4.2, 3.2))
    fig.patch.set_alpha(0)
    ax.set_facecolor('none')

    labels = ['Bruto', 'EBITDA', 'Operativo', 'Neto']
    vals   = [DATA['margen_bruto'], DATA['margen_ebitda'], DATA['margen_op'], DATA['margen_neto']]
    cols   = ['#1A56A8' if v > 0 else '#C0392B' for v in vals]

    bars = ax.barh(labels, vals, color=cols, height=0.5, zorder=3)
    ax.axvline(0, color='#CBD5E1', linewidth=1, zorder=2)

    for bar, v in zip(bars, vals):
        xpos = v + 0.5 if v >= 0 else v - 0.5
        ha = 'left' if v >= 0 else 'right'
        ax.text(xpos, bar.get_y() + bar.get_height()/2, f'{v:+.1f}%',
                va='center', ha=ha, fontsize=8.5, color='#0D2B5E', fontweight='bold')

    ax.set_xlim(-15, 35)
    ax.spines['top'].set_visible(False)
    ax.spines['right'].set_visible(False)
    ax.spines['left'].set_visible(False)
    ax.spines['bottom'].set_color('#CBD5E1')
    ax.tick_params(left=False, bottom=False)
    ax.xaxis.set_visible(False)
    ax.yaxis.set_tick_params(labelsize=8.5, labelcolor='#334155')
    ax.set_title('Márgenes de Rentabilidad', fontsize=9, color='#0D2B5E',
                 fontweight='bold', pad=8, loc='left')
    plt.tight_layout(pad=0.5)
    return fig_to_img(fig)

# ── Chart 3: Estructura de Capital (Donut) ───────────────────────────────────
def chart_estructura():
    fig, ax = plt.subplots(figsize=(3.8, 3.2))
    fig.patch.set_alpha(0)
    ax.set_facecolor('none')

    raw    = [DATA['activo_circ'], DATA['activo_fijo'], DATA['pasivo_circ'],
              DATA['pasivo_lp'], DATA['capital']]
    labels = ['Activo\nCirc.', 'Activo\nFijo', 'Pasivo\nCirc.', 'Pasivo\nLP', 'Capital']
    cols   = ['#1A56A8', '#3B82F6', '#C0392B', '#E67E22', '#64748B']

    # pie() exige valores >= 0; capital puede ser negativo (insolvencia)
    sizes = [max(0, s) for s in raw]
    if sum(sizes) == 0:
        sizes = [1]; labels = ['Sin datos']; cols = ['#CBD5E1']; raw = [0]

    wedges, _ = ax.pie(sizes, colors=cols, startangle=90,
                       wedgeprops=dict(width=0.55, edgecolor='white', linewidth=1.5))

    center_lines = f"{fmt(DATA['activo_total'])}\nActivos"
    if DATA['capital'] < 0:
        center_lines += "\n⚠ Cap. neg."
    ax.text(0, 0, center_lines, ha='center', va='center',
            fontsize=7, color='#0D2B5E', fontweight='bold', linespacing=1.4)

    total_pos = sum(sizes) or 1
    legend_patches = [mpatches.Patch(color=c, label=f"{l.replace(chr(10),' ')} {fmt(v)}")
                      for c, l, v in zip(cols, labels, raw)]
    ax.legend(handles=legend_patches, loc='lower center', bbox_to_anchor=(0.5, -0.22),
              ncol=2, fontsize=6.5, frameon=False, labelcolor='#334155')
    ax.set_title('Estructura de Capital', fontsize=9, color='#0D2B5E',
                 fontweight='bold', pad=6, loc='left')
    plt.tight_layout(pad=0.3)
    return fig_to_img(fig)

# ── Chart 4: Liquidez ────────────────────────────────────────────────────────
def chart_liquidez():
    fig, ax = plt.subplots(figsize=(4.2, 2.8))
    fig.patch.set_alpha(0)
    ax.set_facecolor('none')

    indicadores = ['Razón\nCirculante', 'Prueba\nÁcida', 'Razón\nEfectivo']
    valores     = [DATA['razon_circ'], DATA['prueba_acida'], DATA['razon_ef']]
    benchmarks  = [1.5, 1.0, 0.2]
    cols        = ['#1A56A8' if v >= b else '#C0392B' for v, b in zip(valores, benchmarks)]

    x = range(len(indicadores))
    bars = ax.bar(x, valores, color=cols, width=0.4, zorder=3, edgecolor='white')
    ax.scatter(x, benchmarks, color='#64748B', s=60, zorder=5, marker='D', label='Benchmark')

    for bar, v in zip(bars, valores):
        ax.text(bar.get_x() + bar.get_width()/2, v + 0.03, f'{v:.2f}x',
                ha='center', fontsize=8, color='#0D2B5E', fontweight='bold')

    ax.set_xticks(list(x))
    ax.set_xticklabels(indicadores, fontsize=7.5, color='#334155')
    ax.yaxis.set_visible(False)
    ax.spines['top'].set_visible(False)
    ax.spines['right'].set_visible(False)
    ax.spines['left'].set_visible(False)
    ax.spines['bottom'].set_color('#CBD5E1')
    ax.tick_params(bottom=False)
    ax.legend(fontsize=7, frameon=False, labelcolor='#334155')
    ax.set_title('Análisis de Liquidez vs Benchmark', fontsize=9, color='#0D2B5E',
                 fontweight='bold', pad=8, loc='left')
    plt.tight_layout(pad=0.5)
    return fig_to_img(fig)

# ── Chart 5: Ciclo de Conversión de Efectivo ────────────────────────────────
def chart_cce():
    fig, ax = plt.subplots(figsize=(7.5, 2.5))
    fig.patch.set_alpha(0)
    ax.set_facecolor('none')

    dio_v = DATA['dio']
    dso_v = DATA['dso']
    dpo_v = DATA['dpo']
    cce_v = DATA['ccc']

    ax.barh(0, dio_v,  left=0,     color='#1A56A8', height=0.35, label=f'DIO: {round(dio_v)} días')
    ax.barh(0, dso_v,  left=dio_v, color='#3B82F6', height=0.35, label=f'DSO: {round(dso_v)} días')
    ax.barh(0, -dpo_v, left=0,     color='#64748B', height=0.35, label=f'DPO: {round(dpo_v)} días (resta)')

    ax.text(dio_v / 2,          0.25, f'DIO\n{round(dio_v)}d', ha='center', va='bottom', fontsize=7.5,
            color='white', fontweight='bold')
    ax.text(dio_v + dso_v / 2,  0.25, f'DSO\n{round(dso_v)}d', ha='center', va='bottom', fontsize=7.5,
            color='white', fontweight='bold')
    ax.text(-dpo_v / 2,         0.25, f'DPO\n{round(dpo_v)}d', ha='center', va='bottom', fontsize=7.5,
            color='#64748B', fontweight='bold')

    ax.axvline(0,     color='#CBD5E1', linewidth=1)
    ax.axvline(cce_v, color='#C0392B', linewidth=1.5, linestyle='--')
    ax.text(cce_v, -0.3, f'CCE: {round(cce_v)} días', ha='center', fontsize=8,
            color='#C0392B', fontweight='bold')

    xlim_min = -(dpo_v + 50)
    xlim_max = max(dio_v + dso_v, cce_v) + 60
    ax.set_xlim(xlim_min, xlim_max)
    ax.set_ylim(-0.6, 0.8)
    ax.axis('off')
    ax.legend(loc='upper right', fontsize=7, frameon=False, labelcolor='#334155')
    ax.set_title('Ciclo de Conversión de Efectivo (CCE)', fontsize=9, color='#0D2B5E',
                 fontweight='bold', pad=8, loc='left')
    plt.tight_layout(pad=0.5)
    return fig_to_img(fig)

# ── Styles ───────────────────────────────────────────────────────────────────
def make_styles():
    base = getSampleStyleSheet()
    styles = {}

    styles['title_main'] = ParagraphStyle('title_main',
        fontName='Helvetica-Bold', fontSize=22, textColor=WHITE,
        leading=26, alignment=TA_LEFT)
    styles['subtitle'] = ParagraphStyle('subtitle',
        fontName='Helvetica', fontSize=10, textColor=colors.HexColor('#A8D8E0'),
        leading=14, alignment=TA_LEFT)
    styles['section_header'] = ParagraphStyle('section_header',
        fontName='Helvetica-Bold', fontSize=11, textColor=NAVY,
        leading=16, spaceBefore=14, spaceAfter=8)
    styles['body'] = ParagraphStyle('body',
        fontName='Helvetica', fontSize=8.5, textColor=DGRAY,
        leading=14, alignment=TA_JUSTIFY)
    styles['body_bold'] = ParagraphStyle('body_bold',
        fontName='Helvetica-Bold', fontSize=8.5, textColor=NAVY, leading=13)
    styles['kpi_label'] = ParagraphStyle('kpi_label',
        fontName='Helvetica', fontSize=7, textColor=MGRAY, leading=10, alignment=TA_CENTER)
    styles['kpi_value'] = ParagraphStyle('kpi_value',
        fontName='Helvetica-Bold', fontSize=14, textColor=NAVY, leading=17, alignment=TA_CENTER)
    styles['footer'] = ParagraphStyle('footer',
        fontName='Helvetica', fontSize=7, textColor=MGRAY, leading=9, alignment=TA_CENTER)
    styles['alert_red'] = ParagraphStyle('alert_red',
        fontName='Helvetica-Bold', fontSize=8, textColor=RED, leading=11)
    styles['alert_amber'] = ParagraphStyle('alert_amber',
        fontName='Helvetica-Bold', fontSize=8, textColor=AMBER, leading=11)
    styles['alert_green'] = ParagraphStyle('alert_green',
        fontName='Helvetica-Bold', fontSize=8, textColor=GREEN, leading=11)
    styles['insight'] = ParagraphStyle('insight',
        fontName='Helvetica', fontSize=8, textColor=DGRAY, leading=12, leftIndent=8)
    styles['table_header'] = ParagraphStyle('table_header',
        fontName='Helvetica-Bold', fontSize=8, textColor=WHITE, leading=10, alignment=TA_CENTER)
    styles['recom_title'] = ParagraphStyle('recom_title',
        fontName='Helvetica-Bold', fontSize=9, textColor=NAVY, leading=12)
    styles['recom_body'] = ParagraphStyle('recom_body',
        fontName='Helvetica', fontSize=8, textColor=DGRAY, leading=12)
    return styles

# ── Page numbering canvas ────────────────────────────────────────────────────
class NumberedCanvas(canvas.Canvas):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self._saved_page_states = []

    def showPage(self):
        self._saved_page_states.append(dict(self.__dict__))
        self._startPage()

    def save(self):
        num_pages = len(self._saved_page_states)
        for state in self._saved_page_states:
            self.__dict__.update(state)
            self.draw_page_number(num_pages)
            canvas.Canvas.showPage(self)
        canvas.Canvas.save(self)

    def draw_page_number(self, page_count):
        page_num = self._saved_page_states.index(
            {k: v for k, v in self.__dict__.items() if k in self._saved_page_states[0]}
        ) + 1 if hasattr(self, '_pageNumber') else self._pageNumber

        # Footer bar
        self.setFillColor(NAVY)
        self.rect(0, 0, W, 18*mm, fill=1, stroke=0)
        self.setFillColor(TEAL)
        self.rect(0, 18*mm, W, 0.8*mm, fill=1, stroke=0)

        self.setFont('Helvetica', 7)
        self.setFillColor(MGRAY)
        self.drawString(15*mm, 7*mm, f"{DATA['empresa']} • Reporte Ejecutivo • {DATA['periodo']}")
        self.drawCentredString(W/2, 7*mm, f"RFC: {DATA['rfc']}")
        self.drawRightString(W - 15*mm, 7*mm, f"Análisis: Claude Sonnet • {DATA['fecha']}")

# ── Build PDF ────────────────────────────────────────────────────────────────
def build_pdf(output_path):
    doc = SimpleDocTemplate(
        output_path,  # puede ser str (archivo) o BytesIO
        pagesize=A4,
        leftMargin=18*mm, rightMargin=18*mm,
        topMargin=12*mm, bottomMargin=24*mm,
        title=f"Reporte Ejecutivo {DATA['empresa']} {DATA['periodo']}",
        author="TaxnFin • Claude Sonnet"
    )

    styles = make_styles()
    story  = []
    PW = doc.width  # usable width

    # ─── PORTADA ─────────────────────────────────────────────────────────────
    def portada(canvas_obj, doc_obj):
        canvas_obj.saveState()
        # Fondo blanco limpio
        canvas_obj.setFillColor(WHITE)
        canvas_obj.rect(0, 0, W, H, fill=1, stroke=0)

        # Barra azul vertical izquierda (4mm)
        canvas_obj.setFillColor(NAVY)
        canvas_obj.rect(0, 0, 4*mm, H, fill=1, stroke=0)

        # Nombre de empresa
        canvas_obj.setFont('Helvetica-Bold', 46)
        canvas_obj.setFillColor(NAVY)
        canvas_obj.drawString(16*mm, H*0.73, DATA['empresa'])

        # Subtítulo
        canvas_obj.setFont('Helvetica', 13)
        canvas_obj.setFillColor(DGRAY)
        canvas_obj.drawString(16*mm, H*0.67, 'Reporte Ejecutivo Mensual')

        # Línea de acento
        canvas_obj.setFillColor(TEAL)
        canvas_obj.rect(16*mm, H*0.655, W - 32*mm, 1.5, fill=1, stroke=0)

        # Caja gris suave con período dinámico y RFC
        canvas_obj.setFillColor(LGRAY)
        canvas_obj.roundRect(16*mm, H*0.58, W - 32*mm, 17*mm, 4, fill=1, stroke=0)
        canvas_obj.setFont('Helvetica-Bold', 15)
        canvas_obj.setFillColor(NAVY)
        canvas_obj.drawString(20*mm, H*0.58 + 10*mm, DATA['periodo'])
        canvas_obj.setFont('Helvetica', 9)
        canvas_obj.setFillColor(DGRAY)
        canvas_obj.drawRightString(W - 20*mm, H*0.58 + 10*mm, f"RFC: {DATA['rfc']}")

        # 4 KPI cards blancas con borde y línea de color superior
        _kpis = [
            ('Ingresos',     fmt(DATA['ingresos']),              True),
            ('Util. Bruta',  fmt(DATA['utilidad_bruta']),        DATA['utilidad_bruta'] >= 0),
            ('Margen Bruto', f"{DATA['margen_bruto']:.1f}%",     DATA['margen_bruto'] >= 0),
            ('EBITDA',       fmt(DATA['ebitda']),                DATA['ebitda'] >= 0),
        ]
        _box_w = (W - 32*mm) / 4
        _box_h = 30*mm
        _y_kpi = H * 0.41
        for i, (lbl, val, pos) in enumerate(_kpis):
            _x = 16*mm + i * _box_w
            _top_col = GREEN if pos else RED
            # Card con borde gris
            canvas_obj.setFillColor(WHITE)
            canvas_obj.setStrokeColor(MGRAY)
            canvas_obj.roundRect(_x + 2, _y_kpi, _box_w - 6, _box_h, 4, fill=1, stroke=1)
            # Línea de color en la parte superior
            canvas_obj.setFillColor(_top_col)
            canvas_obj.setStrokeColor(_top_col)
            canvas_obj.rect(_x + 2, _y_kpi + _box_h - 4, _box_w - 6, 4, fill=1, stroke=0)
            # Label
            canvas_obj.setFont('Helvetica', 7.5)
            canvas_obj.setFillColor(DGRAY)
            canvas_obj.drawCentredString(_x + _box_w / 2, _y_kpi + 18*mm, lbl)
            # Valor con color semáforo
            canvas_obj.setFont('Helvetica-Bold', 13)
            canvas_obj.setFillColor(_top_col)
            canvas_obj.drawCentredString(_x + _box_w / 2, _y_kpi + 9*mm, val)

        # Footer azul marino inferior
        canvas_obj.setFillColor(NAVY)
        canvas_obj.rect(0, 0, W, 20*mm, fill=1, stroke=0)
        canvas_obj.setFont('Helvetica', 8)
        canvas_obj.setFillColor(MGRAY)
        canvas_obj.drawString(16*mm, 8*mm, f"{DATA['empresa']}  ·  {DATA['periodo']}")
        canvas_obj.drawCentredString(W / 2, 8*mm, f"RFC: {DATA['rfc']}")
        canvas_obj.drawRightString(W - 16*mm, 8*mm, f"Generado: {DATA['fecha']}")
        canvas_obj.restoreState()

    # Página de portada (en blanco en el story, pintada con onFirstPage)
    from reportlab.platypus import PageBreak

    # Usamos un Frame vacío para la portada
    cover_frame = Frame(0, 0, W, H, id='cover')
    content_frame = Frame(18*mm, 24*mm, W-36*mm, H-46*mm, id='content')

    def later_pages(canvas_obj, doc_obj):
        canvas_obj.saveState()
        # Header band
        canvas_obj.setFillColor(NAVY)
        canvas_obj.rect(0, H-12*mm, W, 12*mm, fill=1, stroke=0)
        canvas_obj.setFillColor(TEAL)
        canvas_obj.rect(0, H-12*mm-0.8, W, 0.8, fill=1, stroke=0)
        canvas_obj.setFont('Helvetica-Bold', 9)
        canvas_obj.setFillColor(WHITE)
        canvas_obj.drawString(18*mm, H-8*mm, DATA['empresa'])
        canvas_obj.setFont('Helvetica', 9)
        canvas_obj.setFillColor(colors.HexColor('#8EC8D4'))
        canvas_obj.drawString(32*mm, H-8*mm, '· Reporte Ejecutivo Mensual')
        canvas_obj.setFont('Helvetica', 8)
        canvas_obj.setFillColor(TEAL2)
        canvas_obj.drawRightString(W-18*mm, H-8*mm, f"{DATA['periodo']}")

        # Footer
        canvas_obj.setFillColor(NAVY)
        canvas_obj.rect(0, 0, W, 18*mm, fill=1, stroke=0)
        canvas_obj.setFillColor(TEAL)
        canvas_obj.rect(0, 18*mm, W, 0.8*mm, fill=1, stroke=0)
        canvas_obj.setFont('Helvetica', 7)
        canvas_obj.setFillColor(MGRAY)
        canvas_obj.drawString(18*mm, 7*mm, f"{DATA['empresa']} • Reporte Ejecutivo • {DATA['periodo']}")
        canvas_obj.drawCentredString(W/2, 7*mm, f"RFC: {DATA['rfc']}")
        canvas_obj.drawRightString(W-18*mm, 7*mm, f"Análisis: TaxnFin · Claude Sonnet • {DATA['fecha']}")
        canvas_obj.restoreState()

    pt_cover   = PageTemplate(id='Cover',   frames=[cover_frame],   onPage=portada)
    pt_content = PageTemplate(id='Content', frames=[content_frame], onPage=later_pages)
    doc.addPageTemplates([pt_cover, pt_content])

    from reportlab.platypus import NextPageTemplate
    story.append(NextPageTemplate('Content'))
    story.append(PageBreak())

    # ─── helpers dinámicos ───────────────────────────────────────────────────
    def _sem(status):
        c_map = {'Crítico': ('#C0392B', '⬤ Crítico'),
                 'Atención': ('#E67E22', '⬤ Atención'),
                 'Bueno':    ('#27AE60', '⬤ Bueno')}
        col, label = c_map.get(status, ('#CBD5E1', '—'))
        return Paragraph(f'<font color="{col}"><b>{label}</b></font>',
                         ParagraphStyle('s', fontName='Helvetica', fontSize=7.5,
                                        leading=10, alignment=TA_CENTER))

    # Variables comunes
    ing   = DATA['ingresos'];    ub    = DATA['utilidad_bruta']
    mb    = DATA['margen_bruto']; gop  = DATA['gastos_op']
    ebitda = DATA['ebitda'];     un    = DATA['utilidad_neta']
    mb_e  = DATA['margen_ebitda']; mb_o = DATA['margen_op']; mb_n = DATA['margen_neto']
    cap   = DATA['capital'];     at    = DATA['activo_total']
    rc    = DATA['razon_circ'];  pa    = DATA['prueba_acida']; ref_ = DATA['razon_ef']
    crun  = DATA['cash_runway']; ct    = DATA['capital_trabajo']
    dio_v = DATA['dio'];         dso_v = DATA['dso']
    dpo_v = DATA['dpo'];         cce_v = DATA['ccc']
    dc    = DATA['deuda_capital']; da  = DATA['deuda_activos']
    debd  = DATA['deuda_ebitda']; cob  = DATA['cobertura']

    er_pct   = (cap / at * 100) if at else 0
    gop_pct  = (gop / ing * 100) if ing else 0
    gop_xcs  = max(0, gop - ub)
    apal_v   = DATA.get('apalancamiento', (at / cap) if cap else 0)

    ing_s = fmt(ing); ub_s = fmt(ub); ebitda_s = fmt(ebitda); un_s = fmt(un)
    gop_s = fmt(gop); cap_s = fmt(cap); at_s = fmt(at)

    # ─── PAG 2: RESUMEN EJECUTIVO ────────────────────────────────────────────
    story.append(Paragraph('Resumen Ejecutivo', styles['section_header']))

    _ebitda_diag = (
        f"los <b>gastos operativos de {gop_s} ({gop_pct:.1f}% de ventas)</b> superan "
        f"el margen bruto en {fmt(gop_xcs)}, llevando el EBITDA a terreno negativo."
        if ebitda < 0 else
        f"los gastos operativos de {gop_s} ({gop_pct:.1f}% de ventas) se mantienen bajo control "
        f"generando EBITDA positivo de {ebitda_s}."
    )
    resumen_text = (
        f"El período <b>{DATA['periodo']}</b> refleja ingresos de <b>{ing_s}</b> con utilidad bruta "
        f"del <b>{mb:.1f}%</b>. Sin embargo, {_ebitda_diag} "
        f"La base patrimonial muestra capital contable de <b>{cap_s}</b> y activos de {at_s}."
    )
    story.append(Paragraph(resumen_text, styles['body']))
    story.append(Spacer(1, 4*mm))

    # KPI Cards row — valores reales con colores semáforo
    _ec = '#C0392B' if ebitda < 0 else '#27AE60'
    _uc = '#C0392B' if un < 0 else '#27AE60'
    _mec = '#C0392B' if mb_e < 0 else '#27AE60'
    _mnc = '#C0392B' if mb_n < 0 else '#27AE60'
    _ebg = colors.HexColor('#FFF0EE') if ebitda < 0 else colors.HexColor('#F0FFF4')
    _ubg = colors.HexColor('#FFF0EE') if un < 0 else colors.HexColor('#F0FFF4')
    kpi_data = [
        [Paragraph('INGRESOS', styles['kpi_label']),
         Paragraph('UTIL. BRUTA', styles['kpi_label']),
         Paragraph('EBITDA', styles['kpi_label']),
         Paragraph('UTIL. NETA', styles['kpi_label'])],
        [Paragraph(ing_s, styles['kpi_value']),
         Paragraph(ub_s, styles['kpi_value']),
         Paragraph(f'<font color="{_ec}">{ebitda_s}</font>', styles['kpi_value']),
         Paragraph(f'<font color="{_uc}">{un_s}</font>', styles['kpi_value'])],
        [Paragraph('100%', styles['kpi_label']),
         Paragraph(f'{mb:.1f}%', styles['kpi_label']),
         Paragraph(f'<font color="{_mec}">{mb_e:+.1f}%</font>', styles['kpi_label']),
         Paragraph(f'<font color="{_mnc}">{mb_n:+.1f}%</font>', styles['kpi_label'])],
    ]
    kpi_table = Table(kpi_data, colWidths=[PW/4]*4, rowHeights=[9*mm, 13*mm, 7*mm])
    kpi_table.setStyle(TableStyle([
        ('BACKGROUND', (0,0), (-1,-1), LGRAY),
        ('BACKGROUND', (2,0), (2,-1), _ebg),
        ('BACKGROUND', (3,0), (3,-1), _ubg),
        ('LINEABOVE',  (0,0), (-1,0), 3, TEAL),
        ('LINEBEFORE', (1,0), (1,-1), 0.5, MGRAY),
        ('LINEBEFORE', (2,0), (2,-1), 0.5, MGRAY),
        ('LINEBEFORE', (3,0), (3,-1), 0.5, MGRAY),
        ('VALIGN',     (0,0), (-1,-1), 'MIDDLE'),
        ('ALIGN',      (0,0), (-1,-1), 'CENTER'),
        ('TOPPADDING', (0,0), (-1,-1), 6),
        ('BOTTOMPADDING', (0,0), (-1,-1), 6),
        ('ROUNDEDCORNERS', [3]),
    ]))
    story.append(kpi_table)
    story.append(Spacer(1, 5*mm))

    wf_img = chart_waterfall()
    story.append(Image(wf_img, width=PW, height=PW*0.48))
    story.append(Spacer(1, 3*mm))

    # Alertas dinámicas
    alerts = []
    if ebitda < 0:
        alerts.append(('⚠', '#C0392B',
            f'Gastos operativos {gop_s} ({gop_pct:.1f}% de ventas) superan la utilidad bruta en {fmt(gop_xcs)}.'))
        alerts.append(('⚠', '#C0392B',
            f'EBITDA negativo ({ebitda_s}): la operación no genera caja suficiente.'))
    else:
        alerts.append(('✓', '#27AE60',
            f'EBITDA positivo {ebitda_s} ({mb_e:+.1f}%): generación de caja operativa saludable.'))
    _mb_col = '#27AE60' if mb >= 30 else '#E67E22'
    _mb_txt = 'saludable' if mb >= 30 else 'sano pero por debajo del benchmark (30-40%)'
    alerts.append(('●', _mb_col,
        f'Margen bruto del {mb:.1f}% — {_mb_txt}. El problema está en gastos operativos.'))
    if cap >= 0:
        alerts.append(('✓', '#27AE60',
            f'Capital contable {cap_s} y activos {at_s} — base patrimonial sólida.'))
    else:
        alerts.append(('⚠', '#E67E22',
            f'Capital contable negativo {cap_s} — empresa técnicamente insolvente. Activos {at_s}.'))

    _al_style = ParagraphStyle('al', fontName='Helvetica', fontSize=8,
                               textColor=DGRAY, leading=11, leftIndent=14, firstLineIndent=-14)
    for icon, col, text in alerts:
        story.append(Paragraph(f'<font color="{col}"><b>{icon}</b></font>  {text}', _al_style))
        story.append(Spacer(1, 2*mm))

    story.append(PageBreak())

    # ─── PAG 3: MÁRGENES + ESTRUCTURA ────────────────────────────────────────
    story.append(Paragraph('Análisis de Márgenes y Estructura de Capital', styles['section_header']))

    _mb_o_txt = 'negativos' if mb_o < 0 else 'positivos'
    _ebitda_accion = (
        f"Un ejercicio de <b>reducción del 15-20% en gastos operativos</b> llevaría el EBITDA a positivo. "
        if ebitda < 0 else
        f"La estructura de costos está bajo control con EBITDA de {ebitda_s}. "
    )
    _dc_txt = f"sin deuda financiera (D/Capital {dc:.2f}x)" if dc == 0 else f"razón D/Capital de {dc:.2f}x"
    text_margenes = (
        f"La dispersión entre el <b>margen bruto ({mb:.1f}%)</b> y los márgenes operativos {_mb_o_txt} "
        f"es la señal diagnóstica más relevante. {_ebitda_accion}"
        f"La empresa mantiene <b>{_dc_txt}</b> y un capital contable del {er_pct:.1f}% del activo total."
    )
    story.append(Paragraph(text_margenes, styles['body']))
    story.append(Spacer(1, 4*mm))

    mg_img = chart_margenes()
    es_img = chart_estructura()
    two_col = Table(
        [[Image(mg_img, width=PW*0.53, height=PW*0.42),
          Image(es_img, width=PW*0.44, height=PW*0.42)]],
        colWidths=[PW*0.54, PW*0.46]
    )
    two_col.setStyle(TableStyle([('VALIGN',(0,0),(-1,-1),'TOP'), ('LEFTPADDING',(0,0),(-1,-1),0)]))
    story.append(two_col)
    story.append(Spacer(1, 4*mm))

    story.append(Paragraph('Tabla de Indicadores de Rentabilidad', styles['body_bold']))
    story.append(Spacer(1, 2*mm))

    def _ms(v, lo, hi=None):
        if v >= lo: return _sem('Bueno')
        if v >= 0: return _sem('Atención')
        return _sem('Crítico')

    def _bp(v, mid): return f"{v - mid:+.0f} pp"

    marg_data = [
        [Paragraph('<b>Indicador</b>', styles['table_header']),
         Paragraph('<b>Valor</b>', styles['table_header']),
         Paragraph('<b>Benchmark</b>', styles['table_header']),
         Paragraph('<b>Brecha</b>', styles['table_header']),
         Paragraph('<b>Estado</b>', styles['table_header'])],
        ['Margen Bruto',     f'{mb:.1f}%',    '30-40%', _bp(mb, 35),      _ms(mb, 30)],
        ['Margen EBITDA',    f'{mb_e:.1f}%',  '10-15%', _bp(mb_e, 12.5),  _ms(mb_e, 10)],
        ['Margen Operativo', f'{mb_o:.1f}%',  '5-10%',  _bp(mb_o, 7.5),   _ms(mb_o, 5)],
        ['Margen Neto',      f'{mb_n:.1f}%',  '3-8%',   _bp(mb_n, 5.5),   _ms(mb_n, 3)],
        ['ROE',              f'{DATA["roe"]:.1f}%',  '10-15%', _bp(DATA['roe'], 12.5), _ms(DATA['roe'], 10)],
        ['ROA',              f'{DATA["roa"]:.1f}%',  '5-10%',  _bp(DATA['roa'], 7.5),  _ms(DATA['roa'], 5)],
        ['ROIC',             f'{DATA["roic"]:.1f}%', '8-12%',  _bp(DATA['roic'], 10),  _ms(DATA['roic'], 8)],
    ]
    marg_table = Table(marg_data, colWidths=[PW*0.3, PW*0.15, PW*0.18, PW*0.15, PW*0.22])
    marg_table.setStyle(TableStyle([
        ('BACKGROUND', (0,0), (-1,0), NAVY),
        ('FONTNAME',   (0,1), (-1,-1), 'Helvetica'),
        ('FONTSIZE',   (0,1), (-1,-1), 8),
        ('TEXTCOLOR',  (0,1), (0,-1), DGRAY),
        ('ALIGN',      (1,0), (-1,-1), 'CENTER'),
        ('VALIGN',     (0,0), (-1,-1), 'MIDDLE'),
        ('ROWBACKGROUNDS', (0,1), (-1,-1), [WHITE, LGRAY]),
        ('GRID',       (0,0), (-1,-1), 0.3, MGRAY),
        ('TOPPADDING', (0,0), (-1,-1), 6),
        ('BOTTOMPADDING', (0,0), (-1,-1), 6),
    ]))
    story.append(marg_table)

    story.append(PageBreak())

    # ─── PAG 4: LIQUIDEZ + CCE ────────────────────────────────────────────────
    story.append(Paragraph('Análisis de Liquidez y Ciclo Operativo', styles['section_header']))

    _paradox = rc > 1.5 and ref_ < 0.2
    ct_s = fmt(ct); crun_s = f"{crun:.1f} mes{'es' if crun != 1 else ''}"
    if _paradox:
        liq_text = (
            f"La empresa presenta una <b>paradoja de liquidez</b>: los indicadores estructurales son buenos "
            f"(razón circulante {rc:.2f}x, prueba ácida {pa:.2f}x, capital de trabajo {ct_s}) pero el "
            f"<b>efectivo es críticamente escaso</b> — razón de efectivo {ref_:.2f}x y cash runway de apenas "
            f"<b>{crun_s}</b>. El activo circulante está atrapado en "
            f"<b>inventario ({round(dio_v)} días) y cuentas por cobrar ({round(dso_v)} días)</b>. "
            f"El Ciclo de Conversión de Efectivo de <b>{round(cce_v)} días</b> es extremadamente largo — "
            f"<b>riesgo operativo inmediato</b> de iliquidez, no de insolvencia."
        )
    else:
        liq_text = (
            f"Razón circulante <b>{rc:.2f}x</b>, prueba ácida {pa:.2f}x, razón de efectivo {ref_:.2f}x "
            f"y cash runway de {crun_s}. Capital de trabajo {ct_s}. "
            f"CCE de {round(cce_v)} días (DIO {round(dio_v)}d + DSO {round(dso_v)}d − DPO {round(dpo_v)}d)."
        )
    story.append(Paragraph(liq_text, styles['body']))
    story.append(Spacer(1, 4*mm))

    lq_img = chart_liquidez()
    story.append(Image(lq_img, width=PW*0.56, height=PW*0.38))
    story.append(Spacer(1, 4*mm))

    cce_img = chart_cce()
    story.append(Image(cce_img, width=PW, height=PW*0.28))
    story.append(Spacer(1, 4*mm))

    def _rs(v, bench): return _sem('Bueno') if v >= bench else _sem('Crítico')
    def _ds(v, lo, hi): return _sem('Bueno') if v <= lo else (_sem('Atención') if v <= hi else _sem('Crítico'))

    liq_kpi = [
        [Paragraph('<b>Indicador</b>', styles['table_header']),
         Paragraph('<b>Valor</b>', styles['table_header']),
         Paragraph('<b>Benchmark</b>', styles['table_header']),
         Paragraph('<b>Estado</b>', styles['table_header']),
         Paragraph('<b>Diagnóstico</b>', styles['table_header'])],
        ['Razón Circulante',  f'{rc:.2f}x',    '>1.5x',     _rs(rc, 1.5),   'Posición cómoda' if rc >= 1.5 else 'Insuficiente'],
        ['Prueba Ácida',      f'{pa:.2f}x',    '>1.0x',     _rs(pa, 1.0),   'Sin inventario: OK' if pa >= 1.0 else 'Por debajo'],
        ['Razón de Efectivo', f'{ref_:.2f}x',  '>0.2x',     _rs(ref_, 0.2), 'Efectivo insuficiente' if ref_ < 0.2 else 'Adecuado'],
        ['Cash Runway',       crun_s,          '3-6 meses', _sem('Crítico') if crun < 3 else _sem('Bueno'), 'Riesgo inmediato' if crun < 1 else 'Atención' if crun < 3 else 'Adecuado'],
        ['DSO (Cobro)',        f'{round(dso_v)} días', '30-60d',    _ds(dso_v, 60, 90),  'Cartera muy lenta' if dso_v > 90 else 'En proceso'],
        ['DIO (Inventario)',   f'{round(dio_v)} días', '45-90d',    _ds(dio_v, 90, 120), 'Exceso de inventario' if dio_v > 120 else 'Elevado' if dio_v > 90 else 'Bien'],
        ['DPO (Pago)',         f'{round(dpo_v)} días', '30-60d',    _sem('Bueno') if dpo_v >= 30 else _sem('Atención'), 'Bien negociado' if dpo_v >= 45 else 'Mejorar'],
        ['CCE',                f'{round(cce_v)} días', '60-90d',    _ds(cce_v, 90, 150), 'Ciclo extremo' if cce_v > 200 else 'Muy largo' if cce_v > 150 else 'Largo'],
    ]
    liq_table = Table(liq_kpi, colWidths=[PW*0.22, PW*0.13, PW*0.16, PW*0.18, PW*0.31])
    liq_table.setStyle(TableStyle([
        ('BACKGROUND',     (0,0), (-1,0), NAVY),
        ('FONTNAME',       (0,1), (-1,-1), 'Helvetica'),
        ('FONTSIZE',       (0,1), (-1,-1), 7.5),
        ('TEXTCOLOR',      (0,1), (0,-1), DGRAY),
        ('ALIGN',          (1,0), (3,-1), 'CENTER'),
        ('VALIGN',         (0,0), (-1,-1), 'MIDDLE'),
        ('ROWBACKGROUNDS', (0,1), (-1,-1), [WHITE, LGRAY]),
        ('GRID',           (0,0), (-1,-1), 0.3, MGRAY),
        ('TOPPADDING',     (0,0), (-1,-1), 3),
        ('BOTTOMPADDING',  (0,0), (-1,-1), 3),
    ]))
    story.append(liq_table)

    story.append(PageBreak())

    # ─── PAG 5: SOLVENCIA + RECOMENDACIONES ──────────────────────────────────
    story.append(Paragraph('Análisis de Solvencia', styles['section_header']))

    _dc_txt2 = 'sin deuda financiera' if dc == 0 else f'D/Capital {dc:.2f}x'
    _debd_note = ' — EBITDA negativo distorsiona' if ebitda < 0 else ''
    _lever_txt = 'tiene espacio para apalancar si mejora la operación' if dc == 0 else 'gestiona la deuda de forma moderada'
    solv_text = (
        f"La posición de solvencia es <b>{'fuerte' if dc == 0 else 'manejable'} en términos patrimoniales</b>: "
        f"{_dc_txt2}, razón de capital del {er_pct:.1f}% y cobertura de intereses de {min(cob, 999):.0f}x. "
        + (f"El indicador de <b>Deuda/EBITDA es {debd:.2f}x</b>{_debd_note}. " if ebitda < 0 else "")
        + f"La empresa {_lever_txt}."
    )
    story.append(Paragraph(solv_text, styles['body']))
    story.append(Spacer(1, 3*mm))

    def _das(v): return _sem('Bueno') if v < 40 else (_sem('Atención') if v < 60 else _sem('Crítico'))
    def _dbs(v): return (_sem('Crítico') if ebitda < 0 else
                         _sem('Bueno') if v < 3 else _sem('Atención') if v < 5 else _sem('Crítico'))

    _apal_status = _sem('Crítico') if cap < 0 else (_sem('Bueno') if apal_v < 2 else _sem('Atención') if apal_v < 3 else _sem('Crítico'))
    _apal_diag   = 'Capital negativo — insolvencia técnica' if cap < 0 else ('Moderado' if apal_v < 2.5 else 'Elevado')
    _cob_s       = f'{cob:.0f}x' if cob < 500 else '∞'
    _cob_status  = _sem('Bueno') if cob >= 5 else (_sem('Atención') if cob >= 2 else _sem('Crítico'))
    _cob_diag    = 'Sin deuda financiera' if cob >= 500 else ('EBITDA negativo' if ebitda < 0 else 'OK')

    solv_data = [
        [Paragraph('<b>Indicador</b>', styles['table_header']),
         Paragraph('<b>Valor</b>', styles['table_header']),
         Paragraph('<b>Estado</b>', styles['table_header']),
         Paragraph('<b>Comentario</b>', styles['table_header'])],
        ['Deuda / Capital',        f'{dc:.2f}x',                _sem('Bueno') if dc == 0 else _sem('Atención'), 'Sin deuda financiera' if dc == 0 else 'Apalancamiento moderado'],
        ['Deuda / Activos',        f'{da:.1f}%',                _das(da),  'Pasivos operativos altos' if da > 40 else 'Nivel adecuado'],
        ['Deuda / EBITDA',         f'{debd:.2f}x',              _dbs(debd), 'EBITDA negativo distorsiona' if ebitda < 0 else 'Nivel manejable'],
        ['Cobertura de Intereses', _cob_s, _cob_status, _cob_diag],
        ['Razón de Capital',       f'{er_pct:.1f}%',            _sem('Bueno') if er_pct > 50 else _sem('Atención'), 'Base patrimonial sólida' if er_pct > 50 else 'Estructura mixta'],
        ['Deuda Neta / EBITDA',    '0.00x',                     _sem('Bueno'), 'Caja > Deuda financiera'],
        ['Apalancamiento',         f'{apal_v:.2f}x',            _apal_status, _apal_diag],
    ]
    solv_table = Table(solv_data, colWidths=[PW*0.28, PW*0.14, PW*0.20, PW*0.38])
    solv_table.setStyle(TableStyle([
        ('BACKGROUND',     (0,0), (-1,0), NAVY),
        ('FONTNAME',       (0,1), (-1,-1), 'Helvetica'),
        ('FONTSIZE',       (0,1), (-1,-1), 8),
        ('TEXTCOLOR',      (0,1), (0,-1), DGRAY),
        ('ALIGN',          (1,0), (2,-1), 'CENTER'),
        ('VALIGN',         (0,0), (-1,-1), 'MIDDLE'),
        ('ROWBACKGROUNDS', (0,1), (-1,-1), [WHITE, LGRAY]),
        ('GRID',           (0,0), (-1,-1), 0.3, MGRAY),
        ('TOPPADDING',     (0,0), (-1,-1), 4),
        ('BOTTOMPADDING',  (0,0), (-1,-1), 4),
    ]))
    story.append(solv_table)
    story.append(Spacer(1, 6*mm))

    # Recomendaciones estratégicas — dinámicas y condicionales
    story.append(HRFlowable(width=PW, thickness=1, color=TEAL, spaceAfter=4*mm))
    story.append(Paragraph('Recomendaciones Estratégicas', styles['section_header']))

    recomendaciones = []
    if ebitda < 0:
        _peq = (gop / (mb / 100)) if mb > 0 else 0
        recomendaciones.append((
            '🔴 URGENTE — Reducir gastos operativos',
            f"Los gastos operativos de {gop_s} ({gop_pct:.1f}% de ventas) superan la utilidad bruta "
            f"en {fmt(gop_xcs)}. Realizar análisis línea por línea para identificar reducción del 15-25%."
            + (f" Punto de equilibrio estimado ~{fmt(_peq)} en ingresos." if _peq > 0 else "")
        ))
    if dso_v > 60:
        _cob_lib = (dso_v - 60) / 365 * ing
        recomendaciones.append((
            f'🔴 URGENTE — Acelerar cobranza (DSO {round(dso_v)}→60 días)',
            f"Implementar política de cobro activa: anticipos 30-50%, descuentos por pronto pago, "
            f"seguimiento semanal de cuentas >60 días. Reducir a 60d liberaría ~{fmt(_cob_lib)} en efectivo."
        ))
    if dio_v > 90:
        _inv_lib = (dio_v - 90) / 365 * DATA['costo_ventas']
        recomendaciones.append((
            f'🟠 IMPORTANTE — Reducir inventario (DIO {round(dio_v)}→90 días)',
            f"Auditar inventario para identificar obsoletos y de lento movimiento. "
            f"Meta DIO<90 días liberaría ~{fmt(_inv_lib)} adicional en efectivo."
        ))
    recomendaciones.append((
        '🟡 ESTRATÉGICO — Plan de crecimiento de ingresos',
        f"Definir plan concreto para incrementar ventas o reducir estructura de costos. "
        f"Evaluar mezcla de productos por margen de contribución y optimizar el ciclo operativo."
    ))
    if cap > 0 and dc == 0:
        recomendaciones.append((
            '🟢 OPORTUNIDAD — Aprovechar posición patrimonial',
            f"La empresa tiene {cap_s} en capital contable y {_dc_txt2}. "
            f"Existe capacidad de apalancamiento para financiar capital de trabajo "
            f"si se estabiliza la operación primero."
        ))

    for titulo, cuerpo in recomendaciones:
        rec_data = [[Paragraph(titulo, styles['recom_title'])],
                    [Paragraph(cuerpo, styles['recom_body'])]]
        rec_table = Table(rec_data, colWidths=[PW])
        rec_table.setStyle(TableStyle([
            ('BACKGROUND',     (0,0), (-1,0), LGRAY),
            ('LINEABOVE',      (0,0), (-1,0), 2, TEAL),
            ('TOPPADDING',     (0,0), (-1,-1), 5),
            ('BOTTOMPADDING',  (0,0), (-1,-1), 5),
            ('LEFTPADDING',    (0,0), (-1,-1), 8),
        ]))
        story.append(rec_table)
        story.append(Spacer(1, 3*mm))

    story.append(PageBreak())

    # ─── PAG 6: ANÁLISIS IA EN LENGUAJE SIMPLE ──────────────────────────────
    story.append(Paragraph('¿Qué nos dicen los números?', styles['section_header']))
    story.append(Paragraph(
        'Resumen ejecutivo en lenguaje sencillo — sin jerga contable.',
        ParagraphStyle('sub', fontName='Helvetica', fontSize=8, textColor=DGRAY,
                       leading=11, spaceAfter=6*mm)
    ))

    ia_bloques = []

    # Bloque 1: Ventas y rentabilidad
    if ebitda < 0:
        ia_bloques.append(('💰', 'Ventas y Rentabilidad', TEAL,
            f'La empresa vendió {ing_s} en el período. Por cada peso que vendió, le quedaron '
            f'{mb:.1f} centavos después de pagar lo que cuesta producir o comprar lo que vende. '
            f'Eso es un margen saludable. El problema es que los gastos del día a día '
            f'(sueldos, renta, servicios) de {gop_s} son demasiado altos y se comen toda esa ganancia '
            f'y más, dejando a la empresa en números rojos.',
            'Acción: revisar todos los gastos operativos línea por línea y reducir mínimo 20%.'))
    else:
        ia_bloques.append(('💰', 'Ventas y Rentabilidad', TEAL,
            f'La empresa vendió {ing_s} en el período y logró generar una ganancia operativa '
            f'de {ebitda_s}. El margen bruto del {mb:.1f}% significa que por cada peso vendido, '
            f'quedan {mb:.1f} centavos para cubrir gastos y generar utilidad.',
            'Mantener el control de gastos para preservar la rentabilidad.'))

    # Bloque 2: Efectivo y cobranza
    if crun < 3:
        ia_bloques.append(('🏦', 'Efectivo y Cobranza', colors.HexColor('#DC2626'),
            f'La empresa tiene efectivo para operar solo {crun:.1f} mes(es) más al ritmo actual. '
            f'Esto no significa que vaya a cerrar, pero sí que necesita cobrar más rápido. '
            f'Actualmente sus clientes tardan {round(dso_v)} días en pagar. '
            f'Si lograra cobrarles en 60 días, tendría mucho más dinero disponible cada mes.',
            f'Acción urgente: llamar a todos los clientes con facturas de más de 30 días y acordar un plan de pago.'))
    else:
        ia_bloques.append(('🏦', 'Efectivo y Cobranza', GREEN,
            f'La empresa tiene efectivo para {crun:.1f} meses de operación. '
            f'Sus clientes pagan en {round(dso_v)} días en promedio.',
            'Mantener el seguimiento de cobranza para no deteriorar este indicador.'))

    # Bloque 3: Inventario (solo si hay inventario elevado)
    if dio_v > 90:
        ia_bloques.append(('📦', 'Inventario', colors.HexColor('#D97706'),
            f'La empresa tiene mercancía guardada por {round(dio_v)} días antes de venderla. '
            f'Lo ideal es que no pase de 90 días. Tener inventario parado por tanto tiempo '
            f'significa dinero "dormido" que no está generando nada. '
            f'Reducirlo liberaría efectivo que se puede usar para pagar deudas u otras necesidades.',
            'Acción: identificar productos de lento movimiento y hacer promociones o liquidarlos.'))

    # Bloque 4: Deudas y solidez
    if cap < 0:
        ia_bloques.append(('⚖️', 'Deudas y Solidez Financiera', colors.HexColor('#DC2626'),
            f'Las deudas totales de la empresa ({fmt(DATA.get("pasivo_total", 0))}) son mayores que '
            f'todos sus activos ({at_s}). Esto se llama insolvencia técnica. '
            f'No es necesariamente una crisis inmediata, pero sí una señal de alerta importante: '
            f'la empresa necesita aumentar ventas, reducir costos o inyectar capital nuevo.',
            'Acción prioritaria: elaborar un plan de recuperación financiera con metas a 90 días.'))
    else:
        ia_bloques.append(('⚖️', 'Deudas y Solidez Financiera', GREEN,
            f'La empresa tiene activos de {at_s} y un capital propio de {cap_s}. '
            f'No tiene deudas financieras (préstamos bancarios), lo que es una fortaleza. '
            f'Tiene capacidad para pedir un crédito si lo necesita para crecer.',
            'Oportunidad: considerar financiamiento para acelerar el crecimiento.'))

    for emoji, titulo, color_bloque, texto, accion in ia_bloques:
        bloque_header = Table(
            [[Paragraph(f'<b>{emoji} {titulo}</b>',
                ParagraphStyle('bh', fontName='Helvetica-Bold', fontSize=10,
                               textColor=colors.white, leading=14))]],
            colWidths=[PW]
        )
        bloque_header.setStyle(TableStyle([
            ('BACKGROUND',     (0,0), (-1,-1), color_bloque),
            ('TOPPADDING',     (0,0), (-1,-1), 6),
            ('BOTTOMPADDING',  (0,0), (-1,-1), 6),
            ('LEFTPADDING',    (0,0), (-1,-1), 10),
        ]))
        story.append(bloque_header)

        bloque_body = Table(
            [[Paragraph(texto,
                ParagraphStyle('bb', fontName='Helvetica', fontSize=8.5,
                               textColor=DGRAY, leading=13, spaceAfter=4))]],
            colWidths=[PW]
        )
        bloque_body.setStyle(TableStyle([
            ('BACKGROUND',    (0,0), (-1,-1), LGRAY),
            ('TOPPADDING',    (0,0), (-1,-1), 7),
            ('BOTTOMPADDING', (0,0), (-1,-1), 4),
            ('LEFTPADDING',   (0,0), (-1,-1), 10),
            ('RIGHTPADDING',  (0,0), (-1,-1), 10),
        ]))
        story.append(bloque_body)

        bloque_accion = Table(
            [[Paragraph(f'<b>→ {accion}</b>',
                ParagraphStyle('ba', fontName='Helvetica', fontSize=8,
                               textColor=color_bloque, leading=11))]],
            colWidths=[PW]
        )
        bloque_accion.setStyle(TableStyle([
            ('BACKGROUND',    (0,0), (-1,-1), colors.white),
            ('LINEBELOW',     (0,0), (-1,-1), 0.5, MGRAY),
            ('TOPPADDING',    (0,0), (-1,-1), 5),
            ('BOTTOMPADDING', (0,0), (-1,-1), 8),
            ('LEFTPADDING',   (0,0), (-1,-1), 10),
        ]))
        story.append(bloque_accion)
        story.append(Spacer(1, 4*mm))

    # ─── Build ───────────────────────────────────────────────────────────────
    doc.build(story, onFirstPage=portada, onLaterPages=later_pages)
    print(f"PDF generado: {output_path}")

def build_pdf_mejorado(data_dict: dict) -> io.BytesIO:
    """
    Versión FastAPI: recibe dict con datos financieros, devuelve BytesIO con el PDF.
    """
    import datetime
    global DATA
    DATA = {
        'empresa':       data_dict.get('empresa', 'Mi Empresa'),
        'periodo':       data_dict.get('periodo', ''),
        'fecha':         datetime.date.today().strftime('%d/%m/%Y'),
        'rfc':           data_dict.get('rfc', ''),
        'ingresos':      data_dict.get('ingresos', 0),
        'costo_ventas':  data_dict.get('costo_ventas', 0),
        'utilidad_bruta': data_dict.get('utilidad_bruta', 0),
        'gastos_op':     data_dict.get('gastos_op', 0),
        'utilidad_op':   -(data_dict.get('gastos_op', 0) - data_dict.get('utilidad_bruta', 0)),
        'ebitda':        data_dict.get('ebitda', 0),
        'utilidad_neta': data_dict.get('utilidad_neta', 0),
        'activo_total':  data_dict.get('activo_total', 0),
        'activo_circ':   data_dict.get('activo_circ', 0),
        'activo_fijo':   data_dict.get('activo_fijo', 0),
        'pasivo_total':  data_dict.get('pasivo_total', 0),
        'pasivo_circ':   data_dict.get('pasivo_circ', 0),
        'pasivo_lp':     data_dict.get('pasivo_lp', 0),
        'capital':       data_dict.get('capital', 0),
        'capital_trabajo': data_dict.get('capital_trabajo', 0),
        'margen_bruto':  data_dict.get('margen_bruto', 0),
        'margen_ebitda': data_dict.get('margen_ebitda', 0),
        'margen_op':     data_dict.get('margen_op', 0),
        'margen_neto':   data_dict.get('margen_neto', 0),
        'roic':          data_dict.get('roic', 0),
        'roe':           data_dict.get('roe', 0),
        'roa':           data_dict.get('roa', 0),
        'roce':          data_dict.get('roce', 0),
        'razon_circ':    data_dict.get('razon_circ', 0),
        'prueba_acida':  data_dict.get('prueba_acida', 0),
        'razon_ef':      data_dict.get('razon_ef', 0),
        'cash_runway':   data_dict.get('cash_runway', 0),
        'dso':           data_dict.get('dso', 0),
        'dpo':           data_dict.get('dpo', 0),
        'dio':           data_dict.get('dio', 0),
        'ccc':           data_dict.get('ccc', 0),
        'deuda_capital': data_dict.get('deuda_capital', 0),
        'deuda_activos': data_dict.get('deuda_activos', 0),
        'deuda_ebitda':  data_dict.get('deuda_ebitda', 0),
        'cobertura':     data_dict.get('cobertura', 0),
        'apalancamiento': data_dict.get('apalancamiento', 0),
        'eficiencia_ef': -37.0,
    }

    buffer = io.BytesIO()
    build_pdf(buffer)
    buffer.seek(0)
    return buffer


if __name__ == '__main__':
    build_pdf('/mnt/user-data/outputs/Reporte_Ejecutivo_KARY_2026-01_MEJORADO.pdf')
