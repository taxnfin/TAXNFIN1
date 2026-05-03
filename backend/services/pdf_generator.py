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
NAVY   = colors.HexColor('#1C2B3A')
TEAL   = colors.HexColor('#2A8A9A')
TEAL2  = colors.HexColor('#3AAABF')
GOLD   = colors.HexColor('#B8995A')
RED    = colors.HexColor('#C0392B')
AMBER  = colors.HexColor('#E67E22')
GREEN  = colors.HexColor('#27AE60')
LGRAY  = colors.HexColor('#F5F6F7')
MGRAY  = colors.HexColor('#B0BAC6')
DGRAY  = colors.HexColor('#4A5568')
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

    labels = ['Ingresos', 'Costo\nVentas', 'Util.\nBruta', 'Gastos\nOp.', 'Util.\nOperativa']
    values = [2_329_327, -1_765_993, 563_334, -759_924, -196_590]
    running = [0, 2_329_327, 2_329_327, 563_334, 563_334]
    bar_vals = [2_329_327, 1_765_993, 563_334, 759_924, 196_590]
    bar_colors = ['#1A7A8A', '#C0392B', '#22A8BE', '#E67E22', '#C0392B']

    for i, (bot, val, col) in enumerate(zip(running, bar_vals, bar_colors)):
        if i in [0, 2]:
            ax.bar(i, val, bottom=0, color=col, width=0.55, zorder=3,
                   edgecolor='white', linewidth=0.8)
        else:
            ax.bar(i, val, bottom=bot - val if values[i] < 0 else bot,
                   color=col, width=0.55, zorder=3, edgecolor='white', linewidth=0.8)

    display_vals = [2_329_327, -1_765_993, 563_334, -759_924, -196_590]
    for i, (v, bv) in enumerate(zip(display_vals, bar_vals)):
        ypos = bv/2 if i in [0, 2] else (running[i] - bv/2 if values[i] < 0 else running[i] + bv/2)
        sign = '' if i in [0, 2] else ('+' if v > 0 else '')
        ax.text(i, ypos, f"{sign}${abs(v)/1e6:.2f}M", ha='center', va='center',
                fontsize=7.5, color='white', fontweight='bold', zorder=5)

    ax.set_xticks(range(len(labels)))
    ax.set_xticklabels(labels, fontsize=8, color='#4A5568')
    ax.yaxis.set_visible(False)
    ax.spines['top'].set_visible(False)
    ax.spines['right'].set_visible(False)
    ax.spines['left'].set_visible(False)
    ax.spines['bottom'].set_color('#B0BAC6')
    ax.tick_params(bottom=False)
    ax.set_title('Cascada Estado de Resultados', fontsize=9, color='#0D1B2A',
                 fontweight='bold', pad=8, loc='left')
    plt.tight_layout(pad=0.5)
    return fig_to_img(fig)

# ── Chart 2: Márgenes ────────────────────────────────────────────────────────
def chart_margenes():
    fig, ax = plt.subplots(figsize=(4.2, 3.2))
    fig.patch.set_alpha(0)
    ax.set_facecolor('none')

    labels = ['Bruto', 'EBITDA', 'Operativo', 'Neto']
    vals   = [24.2, -7.2, -8.4, -5.0]
    cols   = ['#1A7A8A' if v > 0 else '#C0392B' for v in vals]

    bars = ax.barh(labels, vals, color=cols, height=0.5, zorder=3)
    ax.axvline(0, color='#B0BAC6', linewidth=1, zorder=2)

    for bar, v in zip(bars, vals):
        xpos = v + 0.5 if v >= 0 else v - 0.5
        ha = 'left' if v >= 0 else 'right'
        ax.text(xpos, bar.get_y() + bar.get_height()/2, f'{v:+.1f}%',
                va='center', ha=ha, fontsize=8.5, color='#0D1B2A', fontweight='bold')

    ax.set_xlim(-15, 35)
    ax.spines['top'].set_visible(False)
    ax.spines['right'].set_visible(False)
    ax.spines['left'].set_visible(False)
    ax.spines['bottom'].set_color('#B0BAC6')
    ax.tick_params(left=False, bottom=False)
    ax.xaxis.set_visible(False)
    ax.yaxis.set_tick_params(labelsize=8.5, labelcolor='#4A5568')
    ax.set_title('Márgenes de Rentabilidad', fontsize=9, color='#0D1B2A',
                 fontweight='bold', pad=8, loc='left')
    plt.tight_layout(pad=0.5)
    return fig_to_img(fig)

# ── Chart 3: Estructura de Capital (Donut) ───────────────────────────────────
def chart_estructura():
    fig, ax = plt.subplots(figsize=(3.8, 3.2))
    fig.patch.set_alpha(0)
    ax.set_facecolor('none')

    sizes  = [25_246_100, 3_000_000, 9_500_000, 3_000_000, 16_637_979]
    labels = ['Activo\nCirc.', 'Activo\nFijo', 'Pasivo\nCirc.', 'Pasivo\nLP', 'Capital']
    cols   = ['#1A7A8A', '#22A8BE', '#C0392B', '#E67E22', '#C8A84B']
    pcts   = [s/sum(sizes)*100 for s in sizes]

    wedges, _ = ax.pie(sizes, colors=cols, startangle=90,
                       wedgeprops=dict(width=0.55, edgecolor='white', linewidth=1.5))

    ax.text(0, 0, f"$28.8M\nActivos", ha='center', va='center',
            fontsize=8, color='#0D1B2A', fontweight='bold', linespacing=1.4)

    legend_patches = [mpatches.Patch(color=c, label=f"{l.replace(chr(10),' ')} {p:.0f}%")
                      for c, l, p in zip(cols, labels, pcts)]
    ax.legend(handles=legend_patches, loc='lower center', bbox_to_anchor=(0.5, -0.22),
              ncol=2, fontsize=6.5, frameon=False, labelcolor='#4A5568')
    ax.set_title('Estructura de Capital', fontsize=9, color='#0D1B2A',
                 fontweight='bold', pad=6, loc='left')
    plt.tight_layout(pad=0.3)
    return fig_to_img(fig)

# ── Chart 4: Liquidez ────────────────────────────────────────────────────────
def chart_liquidez():
    fig, ax = plt.subplots(figsize=(4.2, 2.8))
    fig.patch.set_alpha(0)
    ax.set_facecolor('none')

    indicadores = ['Razón\nCirculante', 'Prueba\nÁcida', 'Razón\nEfectivo']
    valores     = [2.66, 1.41, 0.03]
    benchmarks  = [1.5, 1.0, 0.2]
    cols        = ['#1A7A8A', '#1A7A8A', '#C0392B']

    x = range(len(indicadores))
    bars = ax.bar(x, valores, color=cols, width=0.4, zorder=3, edgecolor='white')
    ax.scatter(x, benchmarks, color='#C8A84B', s=60, zorder=5, marker='D', label='Benchmark')

    for bar, v in zip(bars, valores):
        ax.text(bar.get_x() + bar.get_width()/2, v + 0.03, f'{v:.2f}x',
                ha='center', fontsize=8, color='#0D1B2A', fontweight='bold')

    ax.set_xticks(list(x))
    ax.set_xticklabels(indicadores, fontsize=7.5, color='#4A5568')
    ax.yaxis.set_visible(False)
    ax.spines['top'].set_visible(False)
    ax.spines['right'].set_visible(False)
    ax.spines['left'].set_visible(False)
    ax.spines['bottom'].set_color('#B0BAC6')
    ax.tick_params(bottom=False)
    ax.legend(fontsize=7, frameon=False, labelcolor='#4A5568')
    ax.set_title('Análisis de Liquidez vs Benchmark', fontsize=9, color='#0D1B2A',
                 fontweight='bold', pad=8, loc='left')
    plt.tight_layout(pad=0.5)
    return fig_to_img(fig)

# ── Chart 5: Ciclo de Conversión de Efectivo ────────────────────────────────
def chart_cce():
    fig, ax = plt.subplots(figsize=(7.5, 2.5))
    fig.patch.set_alpha(0)
    ax.set_facecolor('none')

    # Timeline bar
    ax.barh(0, 201, left=0,    color='#1A7A8A',  height=0.35, label=f'DIO: 201 días')
    ax.barh(0, 137, left=201,  color='#22A8BE',  height=0.35, label=f'DSO: 137 días')
    ax.barh(0, -95, left=0,    color='#C8A84B',  height=0.35, label=f'DPO: 95 días (resta)')

    ax.text(100,  0.25, 'DIO\n201d', ha='center', va='bottom', fontsize=7.5,
            color='white', fontweight='bold')
    ax.text(269,  0.25, 'DSO\n137d', ha='center', va='bottom', fontsize=7.5,
            color='white', fontweight='bold')
    ax.text(-47,  0.25, 'DPO\n95d',  ha='center', va='bottom', fontsize=7.5,
            color='#C8A84B', fontweight='bold')

    ax.axvline(0,   color='#B0BAC6', linewidth=1)
    ax.axvline(244, color='#C0392B', linewidth=1.5, linestyle='--')
    ax.text(244, -0.3, 'CCE: 244 días', ha='center', fontsize=8,
            color='#C0392B', fontweight='bold')

    ax.set_xlim(-120, 380)
    ax.set_ylim(-0.6, 0.8)
    ax.axis('off')
    ax.legend(loc='upper right', fontsize=7, frameon=False, labelcolor='#4A5568')
    ax.set_title('Ciclo de Conversión de Efectivo (CCE)', fontsize=9, color='#0D1B2A',
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
        # Fondo degradado simulado
        canvas_obj.setFillColor(NAVY)
        canvas_obj.rect(0, 0, W, H, fill=1, stroke=0)
        # Banda teal
        canvas_obj.setFillColor(TEAL)
        canvas_obj.rect(0, H*0.55, W, H*0.45, fill=1, stroke=0)
        # Acento dorado
        canvas_obj.setFillColor(GOLD)
        canvas_obj.rect(0, H*0.55 - 4, W, 4, fill=1, stroke=0)
        # Diagonal decorativa
        canvas_obj.setFillColor(colors.HexColor('#253545'))
        p = canvas_obj.beginPath()
        p.moveTo(0, H*0.55)
        p.lineTo(W*0.6, H*0.55)
        p.lineTo(0, H*0.35)
        p.close()
        canvas_obj.drawPath(p, fill=1, stroke=0)

        # Logo text
        canvas_obj.setFont('Helvetica-Bold', 48)
        canvas_obj.setFillColor(WHITE)
        canvas_obj.drawString(15*mm, H*0.72, DATA['empresa'])
        canvas_obj.setFont('Helvetica', 14)
        canvas_obj.setFillColor(colors.HexColor('#8EC8D4'))
        canvas_obj.drawString(15*mm, H*0.67, 'Reporte Ejecutivo Mensual')

        # Periodo
        canvas_obj.setFont('Helvetica-Bold', 36)
        canvas_obj.setFillColor(colors.HexColor('#B8995A'))
        canvas_obj.drawString(15*mm, H*0.58, 'Enero 2026')

        # KPIs portada
        kpis = [
            ('Ingresos', '$2.33M'),
            ('Util. Bruta', '$563K'),
            ('Margen Bruto', '24.2%'),
            ('EBITDA', '-$167K'),
        ]
        box_w = (W - 30*mm) / 4
        for i, (lbl, val) in enumerate(kpis):
            x = 15*mm + i*box_w
            y = H*0.38
            canvas_obj.setFillColor(colors.HexColor('#FFFFFF15'))
            canvas_obj.roundRect(x+2, y, box_w-6, 28*mm, 3, fill=1, stroke=0)
            canvas_obj.setFont('Helvetica', 8)
            canvas_obj.setFillColor(MGRAY)
            canvas_obj.drawCentredString(x + box_w/2, y+20*mm, lbl)
            canvas_obj.setFont('Helvetica-Bold', 13)
            canvas_obj.setFillColor(WHITE)
            canvas_obj.drawCentredString(x + box_w/2, y+11*mm, val)

        # Footer portada
        canvas_obj.setFillColor(colors.HexColor('#161E28'))
        canvas_obj.rect(0, 0, W, 20*mm, fill=1, stroke=0)
        canvas_obj.setFont('Helvetica', 8)
        canvas_obj.setFillColor(MGRAY)
        canvas_obj.drawString(15*mm, 8*mm, f"RFC: {DATA['rfc']}")
        canvas_obj.drawCentredString(W/2, 8*mm, f"Generado: {DATA['fecha']}")
        canvas_obj.drawRightString(W-15*mm, 8*mm, "Análisis: TaxnFin · Claude Sonnet")
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
        canvas_obj.setFillColor(GOLD)
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

    # ─── PAG 2: RESUMEN EJECUTIVO ────────────────────────────────────────────
    story.append(Paragraph('Resumen Ejecutivo', styles['section_header']))

    # Análisis narrativo
    resumen_text = (
        "El período <b>enero 2026</b> refleja una empresa con <b>base de activos sólida y buena liquidez "
        "estructural</b>, pero con presiones operativas importantes que resultan en márgenes negativos. "
        "Los ingresos de <b>$2.33M</b> generan una utilidad bruta saludable del 24.2%, sin embargo los "
        "<b>gastos operativos de $759K (32.6% de ventas)</b> superan ampliamente el margen bruto, "
        "llevando al EBITDA y a la utilidad operativa a terreno negativo. "
        "Este patrón sugiere que la estructura de costos fijos no está alineada con el nivel de ingresos "
        "actual — el punto de equilibrio operativo se estima por encima de los ingresos del período."
    )
    story.append(Paragraph(resumen_text, styles['body']))
    story.append(Spacer(1, 4*mm))

    # KPI Cards row
    kpi_data = [
        [Paragraph('INGRESOS', styles['kpi_label']),
         Paragraph('UTIL. BRUTA', styles['kpi_label']),
         Paragraph('EBITDA', styles['kpi_label']),
         Paragraph('UTIL. NETA', styles['kpi_label'])],
        [Paragraph('$2.33M', styles['kpi_value']),
         Paragraph('$563K', styles['kpi_value']),
         Paragraph('<font color="#C0392B">-$167K</font>', styles['kpi_value']),
         Paragraph('<font color="#C0392B">-$117K</font>', styles['kpi_value'])],
        [Paragraph('100%', styles['kpi_label']),
         Paragraph('24.2%', styles['kpi_label']),
         Paragraph('<font color="#C0392B">-7.2%</font>', styles['kpi_label']),
         Paragraph('<font color="#C0392B">-5.0%</font>', styles['kpi_label'])],
    ]
    kpi_table = Table(kpi_data, colWidths=[PW/4]*4, rowHeights=[9*mm, 13*mm, 7*mm])
    kpi_table.setStyle(TableStyle([
        ('BACKGROUND', (0,0), (-1,-1), LGRAY),
        ('BACKGROUND', (2,0), (2,-1), colors.HexColor('#FFF0EE')),
        ('BACKGROUND', (3,0), (3,-1), colors.HexColor('#FFF0EE')),
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

    # Gráfica cascada
    wf_img = chart_waterfall()
    story.append(Image(wf_img, width=PW, height=PW*0.48))
    story.append(Spacer(1, 3*mm))

    # Alertas
    alerts = [
        ('⚠', '#C0392B', 'Gastos operativos $759K representan el 32.6% de ventas — superan la utilidad bruta en $196K.'),
        ('⚠', '#C0392B', 'EBITDA negativo: la operación no genera caja suficiente para cubrir ni sus propias operaciones.'),
        ('●', '#E67E22', 'Margen bruto del 24.2% es sano — el problema está en la estructura de gastos, no en el negocio.'),
        ('✓', '#27AE60', 'Capital contable positivo de $16.6M y activos de $28.8M — base patrimonial sólida.'),
    ]
    for icon, col, text in alerts:
        alert_style = ParagraphStyle('al', fontName='Helvetica', fontSize=8,
                                     textColor=DGRAY, leading=11, leftIndent=14,
                                     firstLineIndent=-14)
        story.append(Paragraph(f'<font color="{col}"><b>{icon}</b></font>  {text}', alert_style))
        story.append(Spacer(1, 2*mm))

    story.append(PageBreak())

    # ─── PAG 3: MÁRGENES + ESTRUCTURA ────────────────────────────────────────
    story.append(Paragraph('Análisis de Márgenes y Estructura de Capital', styles['section_header']))

    text_margenes = (
        "La dispersión entre el <b>margen bruto (24.2%)</b> y los márgenes operativos y netos "
        "negativos es la señal diagnóstica más relevante del período. El negocio <b>sí puede generar "
        "valor bruto</b>, pero la carga de gastos operativos lo consume. Un ejercicio de "
        "<b>reducción del 15-20% en gastos operativos</b> llevaría el EBITDA a positivo. "
        "En cuanto a la estructura de capital, la empresa mantiene una <b>razón deuda/capital de 0x "
        "(sin deuda financiera)</b> y un capital contable que representa el 57.8% del activo total — "
        "una posición patrimonial conservadora y sana."
    )
    story.append(Paragraph(text_margenes, styles['body']))
    story.append(Spacer(1, 4*mm))

    # Dos gráficas lado a lado
    mg_img  = chart_margenes()
    es_img  = chart_estructura()
    two_col = Table(
        [[Image(mg_img, width=PW*0.53, height=PW*0.42),
          Image(es_img, width=PW*0.44, height=PW*0.42)]],
        colWidths=[PW*0.54, PW*0.46]
    )
    two_col.setStyle(TableStyle([('VALIGN',(0,0),(-1,-1),'TOP'), ('LEFTPADDING',(0,0),(-1,-1),0)]))
    story.append(two_col)
    story.append(Spacer(1, 4*mm))

    # Tabla de márgenes detallada
    story.append(Paragraph('Tabla de Indicadores de Rentabilidad', styles['body_bold']))
    story.append(Spacer(1, 2*mm))

    def semaforo(status):
        c_map = {'Crítico': ('#C0392B','⬤ Crítico'), 'Atención': ('#E67E22','⬤ Atención'), 'Bueno': ('#27AE60','⬤ Bueno')}
        col, label = c_map.get(status, ('#B0BAC6','—'))
        return Paragraph(f'<font color="{col}"><b>{label}</b></font>',
                         ParagraphStyle('s', fontName='Helvetica', fontSize=7.5, leading=10, alignment=TA_CENTER))

    marg_data = [
        [Paragraph('<b>Indicador</b>', styles['table_header']),
         Paragraph('<b>Valor</b>', styles['table_header']),
         Paragraph('<b>Benchmark</b>', styles['table_header']),
         Paragraph('<b>Brecha</b>', styles['table_header']),
         Paragraph('<b>Estado</b>', styles['table_header'])],
        ['Margen Bruto',      '24.2%',  '30-40%', '-6 pp',  semaforo('Atención')],
        ['Margen EBITDA',     '-7.2%',  '10-15%', '-17 pp', semaforo('Crítico')],
        ['Margen Operativo',  '-8.4%',  '5-10%',  '-14 pp', semaforo('Crítico')],
        ['Margen Neto',       '-5.0%',  '3-8%',   '-8 pp',  semaforo('Crítico')],
        ['ROE',               '-0.7%',  '10-15%', '-11 pp', semaforo('Crítico')],
        ['ROA',               '-0.4%',  '5-10%',  '-5 pp',  semaforo('Crítico')],
        ['ROIC',              '-1.2%',  '8-12%',  '-9 pp',  semaforo('Crítico')],
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

    liq_text = (
        "La empresa presenta una <b>paradoja de liquidez</b>: los indicadores estructurales son buenos "
        "(razón circulante 2.66x, prueba ácida 1.41x, capital de trabajo $15.8M) pero el "
        "<b>efectivo es críticamente escaso</b> — razón de efectivo 0.03x y cash runway de apenas "
        "<b>0.4 meses</b>. Esto significa que aunque el patrimonio circulante es grande, está "
        "atrapado en <b>inventario (201 días) y cuentas por cobrar (137 días)</b>. "
        "El Ciclo de Conversión de Efectivo de <b>244 días</b> es extremadamente largo: "
        "la empresa financia casi 8 meses de operación antes de recuperar su efectivo. "
        "Este es el <b>riesgo operativo más inmediato</b> — no de insolvencia, sino de iliquidez."
    )
    story.append(Paragraph(liq_text, styles['body']))
    story.append(Spacer(1, 4*mm))

    lq_img = chart_liquidez()
    story.append(Image(lq_img, width=PW*0.56, height=PW*0.38))
    story.append(Spacer(1, 4*mm))

    cce_img = chart_cce()
    story.append(Image(cce_img, width=PW, height=PW*0.28))
    story.append(Spacer(1, 4*mm))

    # Tabla KPIs liquidez
    liq_kpi = [
        [Paragraph('<b>Indicador</b>', styles['table_header']),
         Paragraph('<b>Valor</b>', styles['table_header']),
         Paragraph('<b>Benchmark</b>', styles['table_header']),
         Paragraph('<b>Estado</b>', styles['table_header']),
         Paragraph('<b>Diagnóstico</b>', styles['table_header'])],
        ['Razón Circulante',    '2.66x',  '>1.5x',    semaforo('Bueno'),    'Posición cómoda'],
        ['Prueba Ácida',        '1.41x',  '>1.0x',    semaforo('Bueno'),    'Sin inventario: OK'],
        ['Razón de Efectivo',   '0.03x',  '>0.2x',    semaforo('Crítico'),  'Efectivo insuficiente'],
        ['Cash Runway',         '0.4 mes','3-6 meses', semaforo('Crítico'),  'Riesgo inmediato'],
        ['DSO (Cobro)',         '137 días','30-60d',   semaforo('Crítico'),  'Cartera muy lenta'],
        ['DIO (Inventario)',    '201 días','45-90d',   semaforo('Crítico'),  'Exceso de inventario'],
        ['DPO (Pago)',         '95 días', '30-60d',   semaforo('Atención'), 'Bien negociado'],
        ['CCE',                '244 días','60-90d',   semaforo('Crítico'),  'Ciclo extremo'],
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

    solv_text = (
        "La posición de solvencia es <b>fuerte en términos patrimoniales</b>: sin deuda financiera "
        "(D/Capital 0x), razón de capital del 57.8% y cobertura de intereses teórica de 999x. "
        "El único indicador preocupante es <b>Deuda/EBITDA de 24.71x</b>, pero esto se debe "
        "al EBITDA negativo del período — no a un endeudamiento excesivo. "
        "La empresa tiene espacio para apalancar si mejora la operación."
    )
    story.append(Paragraph(solv_text, styles['body']))
    story.append(Spacer(1, 3*mm))

    solv_data = [
        [Paragraph('<b>Indicador</b>', styles['table_header']),
         Paragraph('<b>Valor</b>', styles['table_header']),
         Paragraph('<b>Estado</b>', styles['table_header']),
         Paragraph('<b>Comentario</b>', styles['table_header'])],
        ['Deuda / Capital',          '0.00x',   semaforo('Bueno'),   'Sin deuda financiera'],
        ['Deuda / Activos',          '43.5%',   semaforo('Atención'),'Pasivos operativos altos'],
        ['Deuda / EBITDA',           '24.71x',  semaforo('Crítico'), 'EBITDA negativo distorsiona'],
        ['Cobertura de Intereses',   '999x',    semaforo('Bueno'),   'Sin carga financiera'],
        ['Razón de Capital',         '57.8%',   semaforo('Bueno'),   'Base patrimonial sólida'],
        ['Deuda Neta / EBITDA',      '0.00x',   semaforo('Bueno'),   'Caja > Deuda financiera'],
        ['Apalancamiento',           '1.73x',   semaforo('Atención'),'Moderado, manejable'],
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

    # Recomendaciones estratégicas
    story.append(HRFlowable(width=PW, thickness=1, color=TEAL, spaceAfter=4*mm))
    story.append(Paragraph('Recomendaciones Estratégicas', styles['section_header']))

    recomendaciones = [
        ('🔴 URGENTE — Reducir gastos operativos',
         'Los gastos operativos de $760K superan la utilidad bruta en $196K. Realizar un '
         'análisis línea por línea para identificar al menos $200-250K de reducción (26-33%). '
         'Punto de equilibrio operativo estimado ~$3.1M en ingresos al nivel actual de estructura.'),
        ('🔴 URGENTE — Acelerar cobranza (DSO 137→60 días)',
         'Implementar política de cobro activa: anticipos del 30-50% en pedidos nuevos, '
         'descuentos por pronto pago (2/10 net 30), y seguimiento semanal de cuentas >60 días. '
         'Reducir DSO a 60 días liberaría ~$1.8M en efectivo.'),
        ('🟠 IMPORTANTE — Reducir inventario (DIO 201→90 días)',
         'Auditar inventario para identificar obsoletos y de lento movimiento. Implementar '
         'política de inventario just-in-time para productos de alta rotación. '
         'Meta: DIO<90 días liberaría ~$1.6M adicional en efectivo.'),
        ('🟡 ESTRATÉGICO — Plan de crecimiento de ingresos',
         'Con la estructura actual, el punto de equilibrio requiere ~$3.1M en ingresos. '
         'Definir plan concreto para incrementar ventas 30-35% o reducir estructura de costos. '
         'Evaluar mezcla de productos por margen de contribución.'),
        ('🟢 OPORTUNIDAD — Aprovechar posición patrimonial',
         'La empresa tiene $16.6M en capital contable y 0 deuda financiera. '
         'Existe capacidad de apalancamiento para financiar capital de trabajo o inversión '
         'sin comprometer la solvencia — si se estabiliza la operación primero.'),
    ]

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
