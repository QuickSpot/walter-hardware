#!/usr/bin/env python3
"""Generate the Walter mechanical drawings (TikZ) for the datasheet.

The board outline, pads and test pads are read from the production gerbers.
Component bodies and connector positions come from the pick-and-place data of
the same hardware revision (v1.6). Everything is drawn in millimetres.

Usage:
    python3 generate_drawings.py <gerber_dir> <output_dir>

<gerber_dir> must contain the walter-v1.6-* gerber files.
Requires: pip install gerbonara

Output (to be \\input in walter_datasheet.tex, needs TikZ libraries
patterns and arrows.meta):
    mechanical-views.tex      top and bottom view with dimensions
    mechanical-side.tex       side view, soldered on a carrier board
    mechanical-footprint.tex  recommended carrier board footprint
    mechanical-ufl.tex        top view of the u.FL Wi-Fi/BLE variant
    mechanical-table.tex      table with connector and component positions
"""
import math
import os
import sys
import warnings

warnings.filterwarnings('ignore')
from gerbonara import GerberFile                      # noqa: E402
from gerbonara.utils import MM                        # noqa: E402
from gerbonara import graphic_primitives as gp        # noqa: E402

GDIR, ODIR = sys.argv[1], sys.argv[2]
PREFIX = 'walter-v1.6-'
os.makedirs(ODIR, exist_ok=True)

# ---------------------------------------------------------------------------
# Board facts (KiCad coordinates in mm, y pointing down)
# ---------------------------------------------------------------------------
X_USB, X_ANT, Y_MID = 100.0, 155.0, 60.0      # USB end, antenna end, centre line
LENGTH = X_ANT - X_USB
PITCH = 2.54
ROW_A_Y, ROW_B_Y = 68.89, 51.11               # pins 1-14 / pins 15-28
PIN1_X = 109.72                               # x of pin 1 and pin 28
HDR_BODY_W = 2.54                             # header insulator width
HDR_BODY_H = 3.30                             # header body height = standoff
HDR_PIN_LEN = 6.00                            # mating pin length below the body
HDR_PIN_SQ = 0.64

PCB_T = 1.60
ESP_H = 3.10                                  # ESP32-S3-WROOM-1 module height
TOP_MAX_H = 3.40                              # highest top component (USB-C receptacle)
GM02_H = 1.85
SIM_H = 1.35
CARRIER_T = 1.60

# Component bodies, KiCad coordinates (x1, x2, y1, y2)
ESP_BODY = (129.5, 155.0, 51.0, 69.0)         # 18.0 x 25.5 mm, flush with antenna end
ESP_ANT = (149.0, 155.0, 51.0, 69.0)          # PCB antenna section (keepout depth 6 mm)
ESP1U_BODY = (129.5, 148.7, 51.0, 69.0)        # WROOM-1U is 19.2 mm long
GM02_BODY = (109.125, 125.425, 51.577, 68.577)  # 16.3 x 17.0 mm
USB_CY = 64.314                               # centre of the USB-C receptacle (shell tabs)
USB_BODY = (100.0, 106.2, USB_CY - 4.47, USB_CY + 4.47)
UFL_GNSS = (104.3, 52.7)                      # J5, GNSS (SAW filter and LNA on this path)
UFL_LTE = (104.3, 57.0)                       # J6, LTE
RST = (111.3848, 70.4596)                     # SW1
SIM_BODY = (134.1, 146.3, 54.73, 64.27)       # J1, from the bottom silkscreen outline
SIM_C = (140.2, 59.5)
TP_BOX = (119.5, 128.5, 55.5, 64.5)           # test pad field (bottom)


def pin_xy(n):
    """KiCad coordinates of header pin n (1..28)."""
    if n <= 14:
        return PIN1_X + (n - 1) * PITCH, ROW_A_Y
    return PIN1_X + (28 - n) * PITCH, ROW_B_Y


# ---------------------------------------------------------------------------
# View transforms to drawing coordinates (u, v), 1 unit = 1 mm.
# Top view: USB end at the top (v = 55), antenna end at the bottom (v = 0),
# pin 1 on the left. The bottom view is the mirror image (seen from below).
# ---------------------------------------------------------------------------
def T(x, y):
    return (Y_MID - y, X_ANT - x)


def B(x, y):
    return (y - Y_MID, X_ANT - x)


def gt(view):
    """Same transform for gerber coordinates (y pointing up)."""
    return lambda x, yg: view(x, -yg)


def c(p):
    return f'({p[0]:.3f},{p[1]:.3f})'


_cache = {}


def prims(name):
    if name not in _cache:
        g = GerberFile.open(os.path.join(GDIR, PREFIX + name))
        out = []
        for o in g.objects:
            out += list(o.to_primitives(unit=MM))
        _cache[name] = out
    return _cache[name]


def arc_points(p, n=10):
    r = math.hypot(p.x1 - p.cx, p.y1 - p.cy)
    a1 = math.atan2(p.y1 - p.cy, p.x1 - p.cx)
    a2 = math.atan2(p.y2 - p.cy, p.x2 - p.cx)
    if p.clockwise:
        while a2 > a1:
            a2 -= 2 * math.pi
    else:
        while a2 < a1:
            a2 += 2 * math.pi
    return [(p.cx + r * math.cos(a1 + (a2 - a1) * i / n),
             p.cy + r * math.sin(a1 + (a2 - a1) * i / n)) for i in range(n + 1)]


def outline_loop():
    segs = []
    for p in prims('Board-Outline.gm1'):
        if isinstance(p, gp.Line):
            segs.append([(p.x1, p.y1), (p.x2, p.y2)])
        elif isinstance(p, gp.Arc):
            segs.append(arc_points(p))
    loop = segs.pop(0)

    def close(a, b):
        return abs(a[0] - b[0]) < 1e-3 and abs(a[1] - b[1]) < 1e-3

    while segs:
        for i, s in enumerate(segs):
            if close(s[0], loop[-1]):
                loop += s[1:]
                segs.pop(i)
                break
            if close(s[-1], loop[-1]):
                loop += list(reversed(s))[1:]
                segs.pop(i)
                break
        else:
            raise RuntimeError('board outline is not closed')
    return loop[:-1]


OUTLINE = outline_loop()


def outline_path(view):
    f = gt(view)
    return ' -- '.join(c(f(*p)) for p in OUTLINE) + ' -- cycle'


def pad_tikz(p, f, S, style='pad'):
    """TikZ for one gerber primitive; f maps gerber coordinates to the view.
    Fiducials (2 mm mask openings) are left out."""
    if isinstance(p, gp.Circle) and p.r >= 0.9:
        return ''
    if isinstance(p, gp.Circle):
        return f'\\fill[{style}] {c(f(p.x, p.y))} circle ({p.r:.3f});'
    if isinstance(p, gp.Rectangle):
        w, h, a = p.w, p.h, p.rotation
        ca, sa = math.cos(a), math.sin(a)
        pts = [(p.x + ca * dx - sa * dy, p.y + sa * dx + ca * dy)
               for dx, dy in ((-w / 2, -h / 2), (w / 2, -h / 2), (w / 2, h / 2), (-w / 2, h / 2))]
        return f'\\fill[{style}] ' + ' -- '.join(c(f(*q)) for q in pts) + ' -- cycle;'
    if isinstance(p, gp.Line):
        return (f'\\draw[padline, line width={p.width * S:.4f}cm] '
                f'{c(f(p.x1, p.y1))} -- {c(f(p.x2, p.y2))};')
    if isinstance(p, gp.ArcPoly):
        pts = list(p.outline)
        if len(pts) < 3:
            return ''
        return f'\\fill[{style}] ' + ' -- '.join(c(f(*q)) for q in pts) + ' -- cycle;'
    return ''


def rect(view, box, style):
    x1, x2, y1, y2 = box
    pts = [view(x1, y1), view(x2, y1), view(x2, y2), view(x1, y2)]
    return f'\\filldraw[{style}] ' + ' -- '.join(c(q) for q in pts) + ' -- cycle;'


# ---------------------------------------------------------------------------
# Dimension helpers (drawing units = mm)
# ---------------------------------------------------------------------------
GAP, OVER = 0.6, 0.9
ARR = 'Stealth[length=1.2mm,width=0.7mm]'


def _sgn(x):
    return 1 if x >= 0 else -1


def vdim(ul, v1, v2, text, e1=None, e2=None, side=None, outside=False, tpos=0.5):
    """Vertical dimension at u = ul between v1 and v2. e1/e2 are the u
    coordinates of the measured features (extension lines are drawn from
    there), or None for no extension line."""
    out = []
    for e, v in ((e1, v1), (e2, v2)):
        if e is not None:
            s = _sgn(ul - e)
            out.append(f'\\draw[extline] ({e + s * GAP:.3f},{v:.3f}) -- ({ul + s * OVER:.3f},{v:.3f});')
    if side is None:
        ref = e1 if e1 is not None else (e2 if e2 is not None else 0)
        side = 'left' if ul < ref else 'right'
    if outside:
        lo, hi = min(v1, v2), max(v1, v2)
        out.append(f'\\draw[dimline, -{{{ARR}}}] ({ul:.3f},{lo - 2.6:.3f}) -- ({ul:.3f},{lo:.3f});')
        out.append(f'\\draw[dimline, -{{{ARR}}}] ({ul:.3f},{hi + 2.6:.3f}) -- ({ul:.3f},{hi:.3f});')
        out.append(f'\\draw[dimline] ({ul:.3f},{lo:.3f}) -- ({ul:.3f},{hi:.3f});')
    else:
        out.append(f'\\draw[dimline, {{{ARR}}}-{{{ARR}}}] ({ul:.3f},{v1:.3f}) -- ({ul:.3f},{v2:.3f});')
    vm = v1 + (v2 - v1) * tpos
    anchor = 'south' if side == 'left' else 'north'
    out.append(f'\\node[dimtext, rotate=90, anchor={anchor}] at ({ul:.3f},{vm:.3f}) {{{text}}};')
    return '\n'.join(out)


def hdim(vl, u1, u2, text, e1=None, e2=None, side=None, outside=False, tpos=0.5, tanchor=None):
    """Horizontal dimension at v = vl between u1 and u2; e1/e2 are the v
    coordinates of the measured features."""
    out = []
    for e, u in ((e1, u1), (e2, u2)):
        if e is not None:
            s = _sgn(vl - e)
            out.append(f'\\draw[extline] ({u:.3f},{e + s * GAP:.3f}) -- ({u:.3f},{vl + s * OVER:.3f});')
    if side is None:
        ref = e1 if e1 is not None else (e2 if e2 is not None else 0)
        side = 'above' if vl >= ref else 'below'
    if outside:
        lo, hi = min(u1, u2), max(u1, u2)
        out.append(f'\\draw[dimline, -{{{ARR}}}] ({lo - 2.6:.3f},{vl:.3f}) -- ({lo:.3f},{vl:.3f});')
        out.append(f'\\draw[dimline, -{{{ARR}}}] ({hi + 2.6:.3f},{vl:.3f}) -- ({hi:.3f},{vl:.3f});')
        out.append(f'\\draw[dimline] ({lo:.3f},{vl:.3f}) -- ({hi:.3f},{vl:.3f});')
    else:
        out.append(f'\\draw[dimline, {{{ARR}}}-{{{ARR}}}] ({u1:.3f},{vl:.3f}) -- ({u2:.3f},{vl:.3f});')
    um = u1 + (u2 - u1) * tpos
    anchor = tanchor or ('south' if side == 'above' else 'north')
    out.append(f'\\node[dimtext, anchor={anchor}] at ({um:.3f},{vl:.3f}) {{{text}}};')
    return '\n'.join(out)


def callout(num, start, pos, via=None):
    path = c(start) + (f' -- {c(via)}' if via else '') + f' -- {c(pos)}'
    return f'\\draw[leader] {path};\n\\node[callout] at {c(pos)} {{{num}}};'


def styles(S):
    return rf"""[x={S}cm, y={S}cm,
  board/.style={{draw=black, line width=0.6pt, fill=white}},
  pad/.style={{fill=black!38}},
  padline/.style={{draw=black!38, line cap=round}},
  body/.style={{draw=black!75, line width=0.4pt, fill=black!7}},
  conn/.style={{draw=black!75, line width=0.4pt, fill=black!22}},
  extline/.style={{draw=black!70, line width=0.2pt}},
  dimline/.style={{draw=black, line width=0.3pt}},
  dimtext/.style={{font=\scriptsize, inner sep=1.2pt}},
  leader/.style={{draw=black!80, line width=0.3pt}},
  callout/.style={{circle, draw=black, line width=0.4pt, fill=white, font=\tiny\bfseries, inner sep=0pt, minimum size=3.3mm}},
  centre/.style={{draw=black!55, line width=0.3pt, dash pattern=on 4pt off 1.5pt on 1pt off 1.5pt}},
  hidden/.style={{draw=black!55, line width=0.3pt, dash pattern=on 1.2pt off 0.8pt}},
  lbl/.style={{font=\scriptsize}},
  small/.style={{font=\tiny}}]
"""


def wr(name, lines):
    with open(os.path.join(ODIR, name), 'w') as fh:
        fh.write('% Generated by generate_drawings.py from the Walter v1.6 production data.\n')
        fh.write('% Do not edit by hand, change the script and regenerate instead.\n')
        fh.write('\n'.join(x for x in lines if x))
        fh.write('\n')
    print('wrote', name)


# ---------------------------------------------------------------------------
# Top view
# ---------------------------------------------------------------------------
def top_view(S, dims=True, variant_1u=False, callouts=True):
    L = []
    f = gt(T)
    L.append(f'\\filldraw[board] {outline_path(T)};')
    for p in prims('F_Mask.gts'):
        L.append(pad_tikz(p, f, S))
    # component bodies
    if variant_1u:
        L.append(rect(T, ESP1U_BODY, 'body'))
    else:
        L.append(rect(T, ESP_BODY, 'body'))
        a, b = T(ESP_ANT[0], ESP_ANT[2]), T(ESP_ANT[1], ESP_ANT[3])
        L.append(f'\\fill[pattern=north east lines, pattern color=black!40] {c(a)} rectangle {c(b)};')
        L.append(f'\\draw[body, fill=none] {c(a)} rectangle {c(b)};')
    L.append(rect(T, GM02_BODY, 'body'))
    L.append(rect(T, USB_BODY, 'conn'))
    for pos in (UFL_GNSS, UFL_LTE):
        u, v = T(*pos)
        L.append(f'\\filldraw[conn] ({u - 1.3:.3f},{v - 1.3:.3f}) rectangle ({u + 1.3:.3f},{v + 1.3:.3f});')
        L.append(f'\\draw[black!75, line width=0.4pt, fill=white] ({u:.3f},{v:.3f}) circle (0.75);')
        L.append(f'\\fill[black!75] ({u:.3f},{v:.3f}) circle (0.22);')
    u, v = T(*RST)
    L.append(f'\\filldraw[conn] ({u - 1.2:.3f},{v - 1.65:.3f}) rectangle ({u + 1.2:.3f},{v + 1.65:.3f});')
    L.append(f'\\draw[black!75, line width=0.4pt, fill=white] ({u:.3f},{v:.3f}) circle (0.7);')
    # module labels
    if variant_1u:
        mu, mv = T((ESP1U_BODY[0] + ESP1U_BODY[1]) / 2, Y_MID)
        L.append(f'\\node[lbl, align=center] at ({mu:.3f},{mv:.3f}) {{ESP32-S3-\\\\WROOM-1U}};')
    else:
        mu, mv = T((ESP_BODY[0] + ESP_ANT[0]) / 2, Y_MID)
        L.append(f'\\node[lbl, align=center] at ({mu:.3f},{mv:.3f}) {{ESP32-S3-\\\\WROOM-1}};')
    gu, gv = T((GM02_BODY[0] + GM02_BODY[1]) / 2, (GM02_BODY[2] + GM02_BODY[3]) / 2)
    L.append(f'\\node[lbl] at ({gu:.3f},{gv:.3f}) {{GM02SP}};')
    # header pins are on the bottom side: hidden lines, pin 1 square
    for n in range(1, 29):
        pu, pv = T(*pin_xy(n))
        if n == 1:
            L.append(f'\\draw[hidden] ({pu - 0.55:.3f},{pv - 0.55:.3f}) rectangle ({pu + 0.55:.3f},{pv + 0.55:.3f});')
        else:
            L.append(f'\\draw[hidden] ({pu:.3f},{pv:.3f}) circle (0.55);')
    for n in (1, 14, 15, 28):
        pu, pv = T(*pin_xy(n))
        dx = -1.4 if pu < 0 else 1.4
        anchor = 'east' if dx < 0 else 'west'
        L.append(f'\\node[small, anchor={anchor}, inner sep=0.4pt] at ({pu + dx:.3f},{pv:.3f}) {{{n}}};')
    L.append('\\draw[centre] (0,-1.5) -- (0,56.5);')
    if callouts:
        # 1 USB-C, 2 GNSS, 3 LTE, 4 reset, 5 antenna area
        ub = T(USB_BODY[0], USB_BODY[3])
        L.append(callout(1, (ub[0], 51.0), (-13.4, 51.0)))
        g = T(*UFL_GNSS)
        L.append(callout(2, (g[0] + 1.3, g[1] + 0.6), (13.4, 52.6)))
        lt = T(*UFL_LTE)
        L.append(callout(3, (lt[0], lt[1] - 1.3), (13.4, 48.2), via=(lt[0], 48.2)))
        r = T(*RST)
        L.append(callout(4, (r[0] - 1.2, r[1]), (-14.9, r[1])))
        if not variant_1u:
            L.append(callout(5, (-6.0, 3.0), (-13.4, 3.0)))
    if not dims:
        return L
    # overall length and tab lengths (left side)
    L.append(vdim(-21.0, 0.0, LENGTH, '55.00', e1=-10.0, e2=-10.0))
    L.append(vdim(-17.2, 47.5, 55.0, '7.50', e1=-12.4))
    L.append(vdim(-17.2, 0.0, 10.0, '10.00', e2=-12.4))
    # widths
    L.append(hdim(59.0, -12.4, 12.4, '24.80', e1=47.5, e2=47.5))
    L.append(hdim(-4.2, -10.0, 10.0, '20.00', e1=0.0, e2=0.0))
    # pin row spacing, measured between pins 8 and 21 (gap between the modules)
    a, b = T(*pin_xy(8)), T(*pin_xy(21))
    L.append(hdim(a[1], a[0], b[0], '17.78').replace('dimtext, anchor=south', 'dimtext, anchor=south, fill=white, inner sep=0.6pt'))
    # pin positions along the board (right side)
    p15, p28 = T(*pin_xy(15)), T(*pin_xy(28))
    L.append(vdim(17.2, 0.0, p15[1], '12.26', e1=10.0, e2=p15[0], side='right'))
    L.append(vdim(17.2, p15[1], p28[1], '13 $\\times$ 2.54 = 33.02', e2=p28[0], side='right'))
    L.append(vdim(17.2, p28[1], LENGTH, '9.72', e2=10.0, side='right'))
    # radii
    L.append('\\draw[leader] (-9.56,54.56) -- (-12.6,57.4) node[dimtext, anchor=south east] {R1.50 (4$\\times$)};')
    L.append('\\draw[leader] (12.11,47.21) -- (13.2,57.4) node[dimtext, anchor=south west] {R1.00 (8$\\times$)};')
    return L


# ---------------------------------------------------------------------------
# Bottom view
# ---------------------------------------------------------------------------
def bottom_view(S):
    L = []
    f = gt(B)
    L.append(f'\\filldraw[board] {outline_path(B)};')
    for p in prims('B_Mask.gbs'):
        L.append(pad_tikz(p, f, S))
    L.append(rect(B, SIM_BODY, 'conn'))
    su, sv = B(*SIM_C)
    L.append(f'\\node[lbl, align=center] at ({su:.3f},{sv:.3f}) {{Nano-SIM}};')
    xb1, xb2 = PIN1_X - PITCH / 2, PIN1_X + 13 * PITCH + PITCH / 2
    for row in (ROW_A_Y, ROW_B_Y):
        L.append(rect(B, (xb1, xb2, row - HDR_BODY_W / 2, row + HDR_BODY_W / 2), 'body'))
    for n in range(1, 29):
        pu, pv = B(*pin_xy(n))
        h = HDR_PIN_SQ / 2
        L.append(f'\\fill[black!85] ({pu - h:.3f},{pv - h:.3f}) rectangle ({pu + h:.3f},{pv + h:.3f});')
    pu, pv = B(*pin_xy(1))
    L.append(f'\\draw[black, line width=0.5pt] ({pu - 0.8:.3f},{pv - 0.8:.3f}) rectangle ({pu + 0.8:.3f},{pv + 0.8:.3f});')
    for n in (1, 14, 15, 28):
        pu, pv = B(*pin_xy(n))
        dx = -1.9 if pu > 0 else 1.9
        anchor = 'east' if dx < 0 else 'west'
        L.append(f'\\node[small, anchor={anchor}, inner sep=0.4pt] at ({pu + dx:.3f},{pv:.3f}) {{{n}}};')
    # SIM card insertion from the antenna end
    L.append(f'\\draw[black, line width=0.8pt, -{{Stealth[length=2mm,width=1.4mm]}}] ({su:.3f},-3.2) -- ({su:.3f},6.0);')
    L.append('\\draw[centre] (0,-1.5) -- (0,56.5);')
    # callouts: 6 SIM holder, 7 test pads
    sb = B(SIM_BODY[0], SIM_BODY[2])
    L.append(callout(6, (sb[0], 14.8), (-13.4, 14.8)))
    tb = B(TP_BOX[0], TP_BOX[2])
    L.append(callout(7, (tb[0], 31.0), (-13.4, 31.0)))
    # header body position (right side)
    hb = B(xb1, ROW_A_Y + HDR_BODY_W / 2)
    he = B(xb2, ROW_A_Y + HDR_BODY_W / 2)
    L.append(vdim(17.2, he[1], hb[1], '35.56', e1=he[0], e2=hb[0], side='right'))
    L.append(vdim(17.2, hb[1], LENGTH, '8.45', e2=10.0, side='right'))
    L.append(hdim(-4.2, su - 4.0, su + 4.0, '', side='below') if False else '')
    return L


def views_figure():
    S = 0.14
    off = 58.0
    L = [f'\\begin{{tikzpicture}}{styles(S)}']
    L += top_view(S)
    L.append('\\begin{scope}[xshift=' + f'{off * S:.4f}' + 'cm]')
    L += bottom_view(S)
    L.append('\\end{scope}')
    for xs, title in ((0, 'Top view'), (off, 'Bottom view (seen from below)')):
        L.append(f'\\node[font=\\small\\bfseries] at ({xs},69.0) {{{title}}};')
        L.append(f'\\node[lbl, black!70] at ({xs},64.6) {{USB-C end}};')
        L.append(f'\\node[lbl, black!70] at ({xs},-10.6) {{antenna end}};')
    L.append(f'\\node[lbl, black!70, align=center] at ({off},-6.0) {{SIM card insertion}};')
    L.append('\\end{tikzpicture}')
    wr('mechanical-views.tex', L)


# ---------------------------------------------------------------------------
# Side view (soldered on a carrier board), USB end on the left
# ---------------------------------------------------------------------------
def side_figure():
    S = 0.20
    L = [f'\\begin{{tikzpicture}}{styles(S)}']
    zb, zt = HDR_BODY_H, HDR_BODY_H + PCB_T
    s = lambda x: x - X_USB  # KiCad x -> distance from the USB end
    # carrier board
    L.append(f'\\filldraw[draw=black!70, line width=0.4pt, pattern=north west lines, pattern color=black!30] '
             f'(-6,{-CARRIER_T}) rectangle (61,0);')
    # header body and pins
    xb1, xb2 = PIN1_X - PITCH / 2, PIN1_X + 13 * PITCH + PITCH / 2
    L.append(f'\\filldraw[body, fill=black!14] ({s(xb1):.3f},0) rectangle ({s(xb2):.3f},{zb:.3f});')
    for n in range(1, 15):
        x = s(pin_xy(n)[0])
        h = HDR_PIN_SQ / 2
        L.append(f'\\filldraw[draw=black, fill=black!55, line width=0.2pt] ({x - h:.3f},{-HDR_PIN_LEN:.3f}) rectangle ({x + h:.3f},0);')
    # SIM holder (bottom side, between the header rows: hidden behind the header body)
    L.append(f'\\fill[black!22] ({s(xb2):.3f},{zb - SIM_H:.3f}) rectangle ({s(SIM_BODY[1]):.3f},{zb:.3f});')
    L.append(f'\\draw[hidden] ({s(SIM_BODY[0]):.3f},{zb - SIM_H:.3f}) rectangle ({s(SIM_BODY[1]):.3f},{zb:.3f});')
    # Walter PCB
    L.append(f'\\filldraw[draw=black, line width=0.5pt, fill=black!30] (0,{zb:.3f}) rectangle ({LENGTH:.3f},{zt:.3f});')
    # top side parts
    L.append(f'\\filldraw[conn] (0,{zt:.3f}) rectangle ({s(USB_BODY[1]):.3f},{zt + TOP_MAX_H:.3f});')
    L.append(f'\\filldraw[body] ({s(GM02_BODY[0]):.3f},{zt:.3f}) rectangle ({s(GM02_BODY[1]):.3f},{zt + GM02_H:.3f});')
    L.append(f'\\filldraw[body] ({s(ESP_BODY[0]):.3f},{zt:.3f}) rectangle ({s(ESP_BODY[1]):.3f},{zt + ESP_H:.3f});')
    # labels
    L.append(f'\\node[lbl] at ({s(USB_BODY[1]) / 2:.3f},{zt + TOP_MAX_H / 2:.3f}) {{USB-C}};')
    L.append(f'\\node[lbl] at ({(s(GM02_BODY[0]) + s(GM02_BODY[1])) / 2:.3f},{zt + GM02_H / 2:.3f}) {{GM02SP}};')
    L.append(f'\\node[lbl] at ({(s(ESP_BODY[0]) + LENGTH) / 2:.3f},{zt + ESP_H / 2:.3f}) {{ESP32-S3-WROOM-1}};')
    L.append(f'\\node[lbl] at ({(s(xb1) + s(SIM_BODY[0])) / 2:.3f},{zb / 2:.3f}) {{2.54\\,mm pin header}};')
    L.append(f'\\draw[leader] ({(s(SIM_BODY[0]) + s(SIM_BODY[1])) / 2 + 3:.3f},{zb - SIM_H / 2:.3f}) -- (48.0,1.2) '
             f'node[lbl, anchor=west] {{Nano-SIM holder}};')
    L.append(f'\\node[lbl, anchor=north east, black!70] at (61,{-CARRIER_T - 0.3}) {{carrier board (example)}};')
    # dimensions, left side
    L.append(vdim(-3.0, 0.0, zb, '3.30', e1=s(xb1), e2=0.0))
    L.append(vdim(-3.0, zt, zt + TOP_MAX_H, '3.40 max.', e1=0.0, e2=0.0))
    L.append(vdim(-8.4, 0.0, zt + TOP_MAX_H, '8.30 max.', e2=-3.0 - OVER - 0.2))
    p1x = s(pin_xy(1)[0])
    L.append(vdim(p1x - 2.8, -HDR_PIN_LEN, 0.0, '6.00', e1=p1x - HDR_PIN_SQ / 2))
    # right side
    L.append(vdim(58.0, zt, zt + ESP_H, '3.10', e1=LENGTH, side='right'))
    L.append(vdim(63.0, zb, zt, '1.60', e1=LENGTH, e2=58.0 + OVER + 0.2, side='right', outside=True))
    L.append(f'\\node[lbl, black!70] at (0,{zt + TOP_MAX_H + 2.4:.3f}) {{USB-C end}};')
    L.append(f'\\node[lbl, black!70] at ({LENGTH},{zt + TOP_MAX_H + 2.4:.3f}) {{antenna end}};')
    L.append('\\end{tikzpicture}')
    wr('mechanical-side.tex', L)


# ---------------------------------------------------------------------------
# Recommended carrier footprint (top view of the carrier board)
# ---------------------------------------------------------------------------
def footprint_figure():
    S = 0.158
    L = [f'\\begin{{tikzpicture}}{styles(S)}']
    L.append(f'\\draw[hidden, line width=0.4pt] {outline_path(T)};')
    L.append('\\fill[pattern=north east lines, pattern color=black!45] (-12.4,0) rectangle (12.4,6);')
    L.append('\\draw[black!70, line width=0.4pt] (-12.4,0) rectangle (12.4,6);')
    for n in range(1, 29):
        pu, pv = T(*pin_xy(n))
        L.append(f'\\fill[black!38] ({pu:.3f},{pv:.3f}) circle (1.0);')
        L.append(f'\\fill[white] ({pu:.3f},{pv:.3f}) circle (0.51);')
    for n in (1, 14, 15, 28):
        pu, pv = T(*pin_xy(n))
        dx = 1.6 if pu < 0 else -1.6
        anchor = 'west' if dx > 0 else 'east'
        L.append(f'\\node[small, anchor={anchor}, inner sep=0.4pt] at ({pu + dx:.3f},{pv:.3f}) {{{n}}};')
    pu, pv = T(*pin_xy(1))
    L.append(f'\\fill[black] ({pu - 1.35:.3f},{pv + 1.35:.3f}) -- ({pu - 2.4:.3f},{pv + 1.35:.3f}) -- ({pu - 1.35:.3f},{pv + 2.4:.3f}) -- cycle;')
    L.append('\\draw[centre] (0,-1.5) -- (0,56.5);')
    L.append('\\node[lbl, align=center, fill=white, inner sep=1pt] at (0,3.0) {keepout};')
    # dimensions
    p1, p14, p15, p28 = (T(*pin_xy(n)) for n in (1, 14, 15, 28))
    L.append(hdim(59.0, p1[0], p28[0], '17.78', e1=p1[1] + 1.0, e2=p28[1] + 1.0))
    L.append(hdim(-4.2, -12.4, 12.4, '24.80', e1=0.0, e2=0.0))
    L.append(vdim(-17.2, 0.0, 6.0, '6.00', e1=-12.4, e2=-12.4, outside=True))
    p2 = T(*pin_xy(2))
    L.append(vdim(-13.4, p2[1], p1[1], '2.54', e1=p2[0] - 1.0, e2=p1[0] - 1.0, outside=True))
    L.append(vdim(17.2, 0.0, p15[1], '12.26', e1=10.0, e2=p15[0] + 1.0, side='right'))
    L.append(vdim(17.2, p15[1], p28[1], '13 $\\times$ 2.54 = 33.02', e2=p28[0] + 1.0, side='right'))
    L.append(vdim(17.2, p28[1], LENGTH, '9.72', e2=10.0, side='right'))
    L.append(f'\\draw[leader] ({p14[0] - 0.75:.3f},{p14[1] - 0.75:.3f}) -- (-15.0,8.6) '
             f'node[dimtext, anchor=south east, align=right] {{28$\\times$ \\O 2.00 pad\\\\\\O 1.02 drill}};')
    L.append('\\node[font=\\small\\bfseries] at (0,69.0) {Carrier board, top view};')
    L.append('\\node[lbl, black!70] at (0,64.6) {USB-C end};')
    L.append('\\node[lbl, black!70] at (0,-10.6) {antenna end};')
    L.append('\\end{tikzpicture}')
    wr('mechanical-footprint.tex', L)


def ufl_figure():
    S = 0.158
    L = [f'\\begin{{tikzpicture}}{styles(S)}']
    L += top_view(S, dims=False, variant_1u=True, callouts=False)
    top = T(ESP1U_BODY[1], Y_MID)
    L.append(f'\\draw[leader] (5.0,{top[1] + 0.5:.3f}) -- (13.4,{top[1] - 4.0:.3f}) '
             f'node[dimtext, anchor=west, align=left] {{u.FL Wi-Fi/BLE\\\\connector on\\\\the module}};')
    L.append(vdim(-15.0, 0.0, top[1], '6.30', e1=-10.0, e2=-9.0))
    L.append(f'\\node[lbl, align=center] at (0,{top[1] / 2:.3f}) {{no keepout}};')
    L.append('\\node[font=\\small\\bfseries] at (0,69.0) {P000000119, top view};')
    L.append('\\node[lbl, black!70] at (0,64.6) {USB-C end};')
    L.append('\\node[lbl, black!70] at (0,-10.6) {antenna end};')
    L.append('\\end{tikzpicture}')
    wr('mechanical-ufl.tex', L)


# ---------------------------------------------------------------------------
# Position table. X from the centre line (positive towards pins 15-28 in the
# top view), Y from the USB-C end.
# ---------------------------------------------------------------------------
def table():
    def X(y):
        return Y_MID - y

    def Y(x):
        return x - X_USB

    def f(v):
        return f'{v:+.2f}'.replace('+0.00', '0.00').replace('-', '$-$')

    rows = [
        ('1', 'USB-C receptacle, centre line', 'top', f(X(USB_CY)), 'board edge'),
        ('2', 'u.FL connector GNSS antenna', 'top', f(X(UFL_GNSS[1])), f'{Y(UFL_GNSS[0]):.2f}'),
        ('3', 'u.FL connector LTE antenna', 'top', f(X(UFL_LTE[1])), f'{Y(UFL_LTE[0]):.2f}'),
        ('4', 'Reset button', 'top', f(X(RST[1])), f'{Y(RST[0]):.2f}'),
        ('5', 'PCB antenna area (P000000100/118)', 'top', f'{f(X(ESP_ANT[3]))} to {f(X(ESP_ANT[2]))}',
         f'{Y(ESP_ANT[0]):.2f} to {Y(ESP_ANT[1]):.2f}'),
        ('6', 'Nano-SIM holder, centre', 'bottom', f(X(SIM_C[1])), f'{Y(SIM_C[0]):.2f}'),
        ('7', 'Test pads (section \\ref{testpoints})', 'bottom', f'{f(X(TP_BOX[3]))} to {f(X(TP_BOX[2]))}',
         f'{Y(TP_BOX[0]):.2f} to {Y(TP_BOX[1]):.2f}'),
        ('', 'Pin 1 / pin 28', '', f'{f(X(ROW_A_Y))} / {f(X(ROW_B_Y))}', f'{Y(PIN1_X):.2f}'),
        ('', 'ESP32-S3 module body', 'top', f'{f(X(ESP_BODY[3]))} to {f(X(ESP_BODY[2]))}',
         f'{Y(ESP_BODY[0]):.2f} to {Y(ESP_BODY[1]):.2f}'),
        ('', 'Sequans GM02SP body', 'top', f'{f(X(GM02_BODY[3]))} to {f(X(GM02_BODY[2]))}',
         f'{Y(GM02_BODY[0]):.2f} to {Y(GM02_BODY[1]):.2f}'),
    ]
    L = [r'\begin{tabular}{|c|l|c|c|c|}', r'\hline',
         r'{\bf Ref.} & {\bf Feature} & {\bf Side} & {\bf X (mm)} & {\bf Y (mm)} \\',
         r'\hline', r'\hline']
    for r in rows:
        L.append(' & '.join(r) + r' \\')
        L.append(r'\hline')
    L.append(r'\end{tabular}')
    wr('mechanical-table.tex', L)


views_figure()
side_figure()
footprint_figure()
ufl_figure()
table()
