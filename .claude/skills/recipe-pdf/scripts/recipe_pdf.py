# -*- coding: utf-8 -*-
"""레시피 JSON -> A4 PDF 렌더러.

사용법:
    python recipe_pdf.py <recipe.json> <output.pdf>

JSON 스키마는 SKILL.md 참고. 모듈로 import 해서 build(path, dict) 로도 쓸 수 있다.
"""
import io
import json
import os
import sys

from reportlab.lib import colors
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle
from reportlab.lib.units import mm
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
from reportlab.platypus import (HRFlowable, KeepTogether, Paragraph,
                                SimpleDocTemplate, Spacer, Table, TableStyle)

# --- 한글 폰트 -------------------------------------------------------------
# 맑은 고딕(윈도우 기본)을 우선 쓰고, 없으면 흔한 대체 폰트를 순서대로 찾는다.
FONT_CANDIDATES = [
    ('C:/Windows/Fonts/malgun.ttf', 'C:/Windows/Fonts/malgunbd.ttf'),
    ('/System/Library/Fonts/AppleSDGothicNeo.ttc', None),
    ('/usr/share/fonts/truetype/nanum/NanumGothic.ttf',
     '/usr/share/fonts/truetype/nanum/NanumGothicBold.ttf'),
]


def _register_fonts():
    for regular, bold in FONT_CANDIDATES:
        if not os.path.exists(regular):
            continue
        pdfmetrics.registerFont(TTFont('RecipeKR', regular))
        if bold and os.path.exists(bold):
            pdfmetrics.registerFont(TTFont('RecipeKR-Bd', bold))
        else:
            # 볼드 파일이 없으면 레귤러를 볼드 자리에 등록한다(글자 깨짐 방지 우선).
            pdfmetrics.registerFont(TTFont('RecipeKR-Bd', regular))
        pdfmetrics.registerFontFamily('RecipeKR', normal='RecipeKR', bold='RecipeKR-Bd',
                                      italic='RecipeKR', boldItalic='RecipeKR-Bd')
        return
    raise RuntimeError(
        '한글 TTF 폰트를 찾지 못했습니다. FONT_CANDIDATES에 경로를 추가하세요.')


_register_fonts()

# --- 팔레트 ---------------------------------------------------------------
ACCENT = colors.HexColor('#B4632A')   # 제목/구분선 강조색
INK = colors.HexColor('#22201D')      # 본문
MUTED = colors.HexColor('#6B665F')    # 보조 텍스트
LINE = colors.HexColor('#DCD5CA')     # 표 괘선
BAND = colors.HexColor('#F6F1E8')     # 음영 배경

FOOTER_DEFAULT = 'habor 레시피북'


def S(name, **kw):
    base = dict(fontName='RecipeKR', fontSize=10.5, leading=17, textColor=INK)
    base.update(kw)
    return ParagraphStyle(name, **base)


def build(path, r):
    """레시피 dict를 path에 PDF로 렌더링한다."""
    title = S('title', fontName='RecipeKR-Bd', fontSize=25, leading=31, spaceAfter=6)
    lede = S('lede', fontSize=11, leading=18, textColor=MUTED, spaceAfter=12)
    h2 = S('h2', fontName='RecipeKR-Bd', fontSize=14, leading=19, textColor=ACCENT,
           spaceBefore=16, spaceAfter=7)
    step_h = S('step_h', fontName='RecipeKR-Bd', fontSize=11.5, leading=17)
    bullet = S('bullet', leftIndent=11, bulletIndent=1, spaceAfter=5)
    cell = S('cell', fontSize=10, leading=14)
    cellb = S('cellb', fontName='RecipeKR-Bd', fontSize=10, leading=14, textColor=ACCENT)
    meta_s = S('meta', fontSize=9.5, leading=13, textColor=MUTED)

    doc = SimpleDocTemplate(path, pagesize=A4,
                            leftMargin=22*mm, rightMargin=22*mm,
                            topMargin=20*mm, bottomMargin=18*mm,
                            title=r['title'], author=r.get('footer', FOOTER_DEFAULT))
    st = [Paragraph(r['title'], title)]
    if r.get('lede'):
        st.append(Paragraph(r['lede'], lede))
    st.append(HRFlowable(width='100%', thickness=1, color=LINE, spaceAfter=10))

    # 조리 시간 / 분량 / 난이도 3칸 박스
    meta = Table([[Paragraph('<b>조리 시간</b>  %s' % r['time'], meta_s),
                   Paragraph('<b>분량</b>  %s' % r['serves'], meta_s),
                   Paragraph('<b>난이도</b>  %s' % r['level'], meta_s)]],
                 colWidths=[55*mm, 55*mm, 56*mm])
    meta.setStyle(TableStyle([
        ('BACKGROUND', (0, 0), (-1, -1), BAND),
        ('BOX', (0, 0), (-1, -1), 0.5, LINE),
        ('INNERGRID', (0, 0), (-1, -1), 0.5, LINE),
        ('LEFTPADDING', (0, 0), (-1, -1), 9), ('RIGHTPADDING', (0, 0), (-1, -1), 9),
        ('TOPPADDING', (0, 0), (-1, -1), 7), ('BOTTOMPADDING', (0, 0), (-1, -1), 7),
    ]))
    st.append(meta)

    # 재료 표 — 분량이 null인 행은 "소스" 같은 소제목 행으로 음영 처리한다.
    st.append(Paragraph('재료', h2))
    data = [[Paragraph('재료', cellb), Paragraph('분량', cellb)]]
    sec_rows = []
    for i, item in enumerate(r['ingredients'], start=1):
        name, amount = item[0], item[1]
        if amount is None:
            sec_rows.append(i)
            data.append([Paragraph(name, cellb), Paragraph('', cell)])
        else:
            data.append([Paragraph(name, cell), Paragraph(amount, cell)])
    t = Table(data, colWidths=[95*mm, 71*mm], repeatRows=1)
    ts = [('LINEBELOW', (0, 0), (-1, 0), 0.9, ACCENT),
          ('LINEBELOW', (0, 1), (-1, -2), 0.4, LINE),
          ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
          ('LEFTPADDING', (0, 0), (-1, -1), 4), ('RIGHTPADDING', (0, 0), (-1, -1), 4),
          ('TOPPADDING', (0, 0), (-1, -1), 5), ('BOTTOMPADDING', (0, 0), (-1, -1), 5)]
    for row in sec_rows:
        ts.append(('BACKGROUND', (0, row), (-1, row), BAND))
        ts.append(('SPAN', (0, row), (-1, row)))
    t.setStyle(TableStyle(ts))
    st.append(t)

    # 조리 단계 — 각 단계는 제목과 본문이 갈라지지 않게 KeepTogether로 묶는다.
    st.append(Paragraph('만드는 법', h2))
    for i, step in enumerate(r['steps'], start=1):
        head, when, txt = step[0], step[1], step[2]
        label = '%d. %s' % (i, head)
        if when:
            label += ' <font color="#6B665F" size="9">(%s)</font>' % when
        st.append(KeepTogether([
            Paragraph(label, step_h),
            Spacer(1, 2),
            Paragraph(txt, S('sbody', leftIndent=13, spaceAfter=9))]))

    for head, key in (('성공 포인트', 'tips'), ('응용', 'variations')):
        items = r.get(key) or []
        if not items:
            continue
        st.append(Paragraph(head, h2))
        for b in items:
            st.append(Paragraph(b, bullet, bulletText='\u2022'))

    footer_text = r.get('footer', FOOTER_DEFAULT)

    def footer(canvas, d):
        canvas.saveState()
        canvas.setFont('RecipeKR', 8)
        canvas.setFillColor(MUTED)
        canvas.drawString(22*mm, 12*mm, footer_text)
        canvas.drawRightString(A4[0]-22*mm, 12*mm, '%d' % d.page)
        canvas.setStrokeColor(LINE)
        canvas.line(22*mm, 15.5*mm, A4[0]-22*mm, 15.5*mm)
        canvas.restoreState()

    doc.build(st, onFirstPage=footer, onLaterPages=footer)
    return path


def main(argv):
    if len(argv) != 3:
        print(__doc__)
        return 2
    with io.open(argv[1], encoding='utf-8') as f:
        recipe = json.load(f)
    out = build(argv[2], recipe)
    print('wrote %s' % out)
    return 0


if __name__ == '__main__':
    sys.exit(main(sys.argv))
