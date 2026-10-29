from datetime import date, datetime
from decimal import Decimal
from io import BytesIO
from xml.sax.saxutils import escape

from django.http import HttpResponse
from django.utils import timezone
from reportlab.lib import colors
from reportlab.lib.enums import TA_LEFT
from reportlab.lib.pagesizes import A4, landscape
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.units import mm
from reportlab.platypus import LongTable, Paragraph, SimpleDocTemplate, Spacer, TableStyle


def cell_text(value):
    if value is None:
        return '-'
    if isinstance(value, Decimal):
        return f'{value:,.2f}'
    if isinstance(value, datetime):
        if timezone.is_aware(value):
            value = timezone.localtime(value)
        return value.strftime('%d %b %Y %H:%M')
    if isinstance(value, date):
        return value.strftime('%d %b %Y')
    return str(value)


def report_pdf(title, headers, rows, filename, query=''):
    buffer = BytesIO()
    doc = SimpleDocTemplate(buffer, pagesize=landscape(A4),
                            leftMargin=14*mm, rightMargin=14*mm,
                            topMargin=14*mm, bottomMargin=16*mm,
                            title=title, author='NFSI Training Management')
    styles = getSampleStyleSheet()
    cell = ParagraphStyle('ReportCell', fontName='Helvetica', fontSize=8,
                          leading=11, alignment=TA_LEFT, wordWrap='CJK')
    heading = ParagraphStyle('ReportHeader', parent=cell, fontName='Helvetica-Bold',
                             textColor=colors.white)

    def paragraph(value, style=cell):
        return Paragraph(escape(cell_text(value)).replace('\n', '<br/>'), style)

    story = [Paragraph('NFSI · Training Management', styles['Normal']),
             Paragraph(escape(title), styles['Title']),
             Paragraph(f'{len(rows):,} matching records · Generated '
                       f'{timezone.localtime():%d %b %Y %H:%M} EAT', styles['Normal'])]
    if query:
        story.append(Paragraph('Filter: ' + escape(query), styles['Normal']))
    story.append(Spacer(1, 7*mm))
    data = [[paragraph(header, heading) for header in headers]]
    data.extend([[paragraph(value) for value in row] for row in rows])
    if not rows:
        data.append([paragraph('No matching records.')] + [''] * (len(headers)-1))
    # Give names and message columns more room while keeping all columns on-page.
    weights = [3 if h.lower() in ('message', 'course', 'trainee', 'trainer') else 1.6
               for h in headers]
    widths = [doc.width * weight / sum(weights) for weight in weights]
    table = LongTable(data, colWidths=widths, repeatRows=1, hAlign='LEFT')
    table.setStyle(TableStyle([
        ('BACKGROUND', (0,0), (-1,0), colors.HexColor('#16634e')),
        ('ROWBACKGROUNDS', (0,1), (-1,-1), [colors.white, colors.HexColor('#f3f6f2')]),
        ('VALIGN', (0,0), (-1,-1), 'TOP'),
        ('LEFTPADDING', (0,0), (-1,-1), 7),
        ('RIGHTPADDING', (0,0), (-1,-1), 7),
        ('TOPPADDING', (0,0), (-1,-1), 7),
        ('BOTTOMPADDING', (0,0), (-1,-1), 7),
        ('LINEBELOW', (0,0), (-1,-1), .3, colors.HexColor('#dde5df')),
    ]))
    story.append(table)

    def footer(canvas, document):
        canvas.saveState()
        canvas.setFont('Helvetica', 8)
        canvas.setFillColor(colors.HexColor('#71817b'))
        canvas.drawString(doc.leftMargin, 9*mm, 'TMIS · NFSI')
        canvas.drawRightString(landscape(A4)[0]-doc.rightMargin, 9*mm,
                               f'Page {document.page}')
        canvas.restoreState()

    doc.build(story, onFirstPage=footer, onLaterPages=footer)
    response = HttpResponse(buffer.getvalue(), content_type='application/pdf')
    response['Content-Disposition'] = f'attachment; filename="{filename}.pdf"'
    return response
