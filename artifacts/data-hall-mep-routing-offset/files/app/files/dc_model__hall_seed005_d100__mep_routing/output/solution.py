#!/usr/bin/env python3
"""
dc_model  hall_seed005_d100  --  coordinated MEP model (IFC4, ifcopenshell 0.8.4)

Builds DATA HALL 1 (Meridian Data Center, project MDC-2026-014) exactly as drawn
on sheets A-101 / A-301 / A-601 / A-602 / M-101 / E-101 / F-101 and routes the
three services (telecom tray CT-1, busway BW-1, chilled water CHW-1).

Everything read off the drawings is baked in below as literals; the script
reads no files, uses no network and is fully deterministic (GUIDs are hashed
from element keys, the header timestamp is fixed).

Key coordination decisions (see also reconciliation.json written next to the
IFC):
  * Deflector = soffit 3050 - 25.4 = 3024.6; 460 standoff -> 2564.6 which is
    BELOW the 2600 minimum clear height (A-301 / A-602 detail 4: "standoff falls
    below the clear height - no overhead pathway zone in this hall").  All three
    services therefore run in the access-floor plenum (permitted zone
    "OVERHEAD OR PLENUM" on the A-602 pathway schedule): slab top -600, panel
    underside -35, service tops kept at -60 (>= 20 mm below the panel, A-301
    note 3 / TIA-942-B 8.6.2).
  * Tray and busway share the upper tier (top -60); the 545 mm plenum cannot
    give 300 mm vertical separation, so they never cross in plan and keep
    >= 314 mm horizontal clearance everywhere (busway wraps round the east end
    of the tray comb).  CHW runs in the lower tier (centre -480) and crosses
    under both freely; its 168.3 mm jacket OD clears the slab and both tiers.
  * Each tray / busway / CHW run sits between two rows within 2000 mm of both
    row centrelines, so one run serves two rows (A+B, C+D) over >= 85 % of
    their length.  CHW spurs reach the four perimeter CRAHs.
  * Columns (600 sq, 7200 grid offset -150 from the tile grid) stand in the
    contained B/C cold aisle: the containment roof is split into its four
    scheduled panels at the column faces; cabinets keep the as-scheduled bays
    (rows set out by accumulation, re-registered at the cross aisle x=12600),
    so no cabinet overlaps structure.
"""
import sys
import os
import json
import math
import uuid

import numpy as np          # only for the support-spacing scan
import ifcopenshell
import ifcopenshell.guid

OUT_PATH = sys.argv[1] if len(sys.argv) > 1 else os.path.join(
    os.path.dirname(os.path.abspath(__file__)), "model.ifc")

# =============================================================================
# 1. DRAWING DATA (literals)
# =============================================================================
TILE = 600.0                                   # A-101 note 3 / A-602
ROOM = [(0.0, 0.0), (27000.0, 0.0), (27000.0, 15600.0), (18600.0, 15600.0),
        (18600.0, 24000.0), (0.0, 24000.0)]    # A-101 (27000 x 24000, 8400 notch NE)

# vertical datums (A-301 / A-602 general construction data)
FFL = 0.0
SLAB_TOP = -600.0
PANEL_THK = 35.0
SOFFIT = 3050.0
CLEAR_HEIGHT = 2600.0
STANDOFF = 460.0
DEFLECTOR = SOFFIT - 25.4                      # 3024.6 (A-301 section 1)
INAISLE_DEFLECTOR = 1890.0                     # A-301 detail 3
CABINET_H = 2000.0
UF_TOP_LIMIT = -(PANEL_THK + 20.0)             # -55  (A-301 note 3)

# structural grid (A-101): 7050 / 7200 / 7200 both ways, offset 150 from tiles
GRID_X = {"A": 7050.0, "B": 14250.0, "C": 21450.0}
GRID_Y = {"1": 7050.0, "2": 14250.0, "3": 21450.0}
COL_SIZE = 600.0                               # measured 600 x 600 on plans

# cabinet types (A-601 cabinet type schedule): width, depth
CAB_TYPES = {"C2": (600.0, 1070.0, "SERVER CABINET, 600 WIDE, SHALLOW"),
             "C1": (600.0, 1200.0, "SERVER CABINET, 600 WIDE"),
             "N2": (800.0, 1070.0, "DISTRIBUTOR CABINET, 800 WIDE, SHALLOW"),
             "N1": (800.0, 1200.0, "DISTRIBUTOR CABINET, 800 WIDE")}

# rows (A-601 cabinet schedule + A-101 row centreline chain 3000/2935/2465/2935)
ROWS = [
    dict(row="A", cl=3000.0, depth=1200.0, faces="SOUTH", first="D05", last="AJ05", qty=26,
         seq="4C1 CU 4C1 N1 4C1 CU CA 7C1 SP CU 6C1"),
    dict(row="B", cl=5935.0, depth=1070.0, faces="NORTH", first="D10", last="AI10", qty=21,
         seq="4C2 CU 3C2 2-600 2C2 2N2 CU CA 2C2 2-600 3C2 CU SP 5C2 2-600"),
    dict(row="C", cl=8400.0, depth=1200.0, faces="SOUTH", first="D14", last="AH14", qty=20,
         seq="4C1 CU 3C1 2-600 2C1 CU 2C1 CA N1 2-600 4C1 SP CU 4C1 2-600"),
    dict(row="D", cl=11335.0, depth=1070.0, faces="NORTH", first="D19", last="AK19", qty=27,
         seq="5C2 CU 3C2 2N2 3C2 CU CA 8C2 SP CU 6C2"),
]
CA_EAST = 12600.0          # cross aisle east edge, common to every row (A-101 note 5)
CA_WEST = 11400.0          # 1200 CLEAR cross aisle (A-101 keyed note 5)

# perimeter CRAH gallery (A-601 CRAH schedule): tiles B01, P01, AC01, AQ01
PERIM_CRAH = [("CRAH-01", "B01"), ("CRAH-02", "P01"), ("CRAH-03", "AC01"), ("CRAH-04", "AQ01")]
PERIM_CRAH_W, PERIM_CRAH_D = 1200.0, 900.0

# PDUs (A-601 PDU schedule + E-101 plan positions; front flush with row front)
PDU_W, PDU_D, PDU_H = 762.0, 813.0, 1959.0
PDUS = [("PDU-01", "A", "AN05", 23400.0, "SOUTH"),
        ("PDU-02", "B", "AM10", 22800.0, "NORTH"),
        ("PDU-03", "C", "AL14", 22400.0, "SOUTH"),
        ("PDU-04", "D", "AO19", 24000.0, "NORTH")]

# containment CAC-BC (A-602 containment schedule + A-101 plan)
CONT_TAG = "CAC-BC"
ROOF_W, ROOF_T, ROOF_UNDERSIDE = 1530.0, 55.5, 2000.0
DOOR_T, DOOR_H = 60.0, 2055.5
# roof panels split at the column faces of grid A / B, segments end at the row
# ends (1800, 21000) and at the 1200 clear cross aisle (11400 / 12600)
ROOF_PANELS_X = [(1800.0, 6750.0), (7350.0, 11400.0), (12600.0, 13950.0), (14550.0, 21000.0)]
DOORS_X = [(1740.0, 1800.0), (11400.0, 11460.0), (12540.0, 12600.0), (21000.0, 21060.0)]

# sprinklers (F-101).  94 ceiling heads on the 1250 / 2500 grid, as drawn
# (north wing last column 17350, east wing top row 14350, the head that falls
# inside column C-2 relocated to 13750).
_XS_MAIN = [1250.0 + 2500.0 * i for i in range(11)]                # 1250 .. 26250
CEILING_HEADS = []
for _y in (1250.0, 3750.0, 6250.0, 8750.0, 11250.0):
    CEILING_HEADS += [(_x, _y) for _x in _XS_MAIN]
CEILING_HEADS += [(_x, 13750.0) for _x in (1250.0, 3750.0, 6250.0, 8750.0, 11250.0, 13750.0, 16250.0, 21250.0)]
CEILING_HEADS += [(_x, 14350.0) for _x in (18750.0, 23750.0, 26250.0)]
for _y in (16250.0, 18750.0, 21250.0, 23750.0):
    CEILING_HEADS += [(_x, _y) for _x in (1250.0, 3750.0, 6250.0, 8750.0, 11250.0, 13750.0, 17350.0)]
HEAD_R = 25.0

# service entries (M-101 / E-101): west wall, 12470 from the south wall
ENTRY = (0.0, 12470.0)

# pathway sections (A-602 pathway section schedule, E-101 notes 4/5, M-101 note 4)
TRAY_W, TRAY_H = 683.0, 127.0
BUS_W, BUS_H = 128.0, 147.0
PIPE_OD = 114.3
INSUL_T = 25.4
JACKET_OD = 168.3
BUS_SUPPORT_MAX = 1500.0
TRAY_BUS_SEP = 300.0
PDU_DEDICATED = 1800.0
PDU_WORKING = 900.0
COVER_REACH = 2500.0


# =============================================================================
# 2. DERIVED LAYOUT
# =============================================================================
def col_index(letters):
    n = 0
    for ch in letters:
        n = n * 26 + (ord(ch) - 64)
    return n - 1                                   # A=0 ... Z=25, AA=26 ...


def col_letters(idx):
    idx += 1
    s = ""
    while idx > 0:
        idx, r = divmod(idx - 1, 26)
        s = chr(65 + r) + s
    return s


def tile_xy(addr):
    i = 0
    while addr[i].isalpha():
        i += 1
    return col_index(addr[:i]) * TILE, (int(addr[i:]) - 1) * TILE


def tile_of(x, y):
    return "%s%02d" % (col_letters(int(math.floor(x / TILE + 1e-9))), int(math.floor(y / TILE + 1e-9)) + 1)


FACING_DEG = {"NORTH": 0.0, "WEST": 90.0, "SOUTH": 180.0, "EAST": -90.0}

racks, inrow_crahs, row_extent = [], [], {}
for R in ROWS:
    x0, y_sw = tile_xy(R["first"])
    ya, yb = R["cl"] - R["depth"] / 2.0, R["cl"] + R["depth"] / 2.0
    assert abs(ya - y_sw) < TILE        # SW corner stands in the scheduled tile row
    x = x0
    nrack = ncu = 0
    for term in R["seq"].split():
        if term == "CA":
            x = CA_EAST
            continue
        if term == "CU":
            ncu += 1
            inrow_crahs.append(dict(tag="CRAH-%s%02d" % (R["row"], ncu), row=R["row"], x0=x, x1=x + 600.0,
                                    y0=ya, y1=yb, faces=R["faces"], depth=R["depth"]))
            x += 600.0
            continue
        if term == "SP":
            x += 600.0
            continue
        if "-" in term:
            cnt, w = term.split("-")
            x += int(cnt) * float(w)
            continue
        cnt = int(term[:-2]) if len(term) > 2 else 1
        typ = term[-2:]
        w, d, desc = CAB_TYPES[typ]
        assert abs(d - R["depth"]) < 1e-6
        for _ in range(cnt):
            nrack += 1
            racks.append(dict(tag="RACK-%s%02d" % (R["row"], nrack), row=R["row"], typ=typ, desc=desc,
                              x0=x, x1=x + w, y0=ya, y1=yb, faces=R["faces"], bay=nrack))
            x += w
    assert nrack == R["qty"], (R["row"], nrack)
    row_racks = [r for r in racks if r["row"] == R["row"]]
    assert tile_of(row_racks[-1]["x0"], row_racks[-1]["y0"]) == R["last"]
    xs = [r["x0"] for r in row_racks] + [c["x0"] for c in inrow_crahs if c["row"] == R["row"]]
    xe = [r["x1"] for r in row_racks] + [c["x1"] for c in inrow_crahs if c["row"] == R["row"]]
    row_extent[R["row"]] = (min(xs), max(xe))
assert len(racks) == 94 and len(inrow_crahs) == 12

perim_crahs = []
for tag, addr in PERIM_CRAH:
    tx, ty = tile_xy(addr)
    perim_crahs.append(dict(tag=tag, x0=tx, x1=tx + PERIM_CRAH_W, y0=ty, y1=ty + PERIM_CRAH_D, faces="NORTH",
                            tile=addr))

row_by = {R["row"]: R for R in ROWS}
pdus = []
for tag, row, addr, x0, faces in PDUS:
    R = row_by[row]
    front = R["cl"] - R["depth"] / 2.0 if R["faces"] == "SOUTH" else R["cl"] + R["depth"] / 2.0
    y0 = front if faces == "SOUTH" else front - PDU_D
    assert tile_of(x0, y0) == addr, (tag, tile_of(x0, y0))
    pdus.append(dict(tag=tag, row=row, tile=addr, x0=x0, x1=x0 + PDU_W, y0=y0, y1=y0 + PDU_D, faces=faces))

columns = []
for gx, cx in GRID_X.items():
    for gy, cy in GRID_Y.items():
        if cx > 18600.0 and cy > 15600.0:        # outside the L (NE notch, no slab)
            continue
        columns.append(dict(tag="COL-%s%s" % (gx, gy), grid="%s-%s" % (gx, gy), cx=cx, cy=cy))
assert len(columns) == 8

# containment aisle between row B front (north face) and row C front (south face)
AISLE_Y0 = row_by["B"]["cl"] + row_by["B"]["depth"] / 2.0      # 6470
AISLE_Y1 = row_by["C"]["cl"] - row_by["C"]["depth"] / 2.0      # 7800
AISLE_CY = (AISLE_Y0 + AISLE_Y1) / 2.0                         # 7135
ROOF_Y0, ROOF_Y1 = AISLE_CY - ROOF_W / 2.0, AISLE_CY + ROOF_W / 2.0

# in-aisle heads (F-101 note 8): per roof panel, 500 in from each end, equal spacing
INAISLE_HEADS = []
for (a, b), n in zip(ROOF_PANELS_X, (3, 2, 1, 4)):
    if n == 1:
        INAISLE_HEADS.append(((a + b) / 2.0, AISLE_CY))
    else:
        for k in range(n):
            INAISLE_HEADS.append((a + 500.0 + k * (b - a - 1000.0) / (n - 1), AISLE_CY))
assert len(CEILING_HEADS) == 94 and len(INAISLE_HEADS) == 10

# =============================================================================
# 3. ROUTES  (under-floor plenum; centreline polylines, axis-aligned)
# =============================================================================
TRAY_ZC = -60.0 - TRAY_H / 2.0       # top -60
BUS_ZC = -60.0 - BUS_H / 2.0         # top -60
CHW_ZC = -480.0                      # jacket 168.3 -> -564.15 .. -395.85

SERVICES = {
    "CT-1": dict(service="TELECOM", kind="tray", zc=TRAY_ZC, w=TRAY_W, h=TRAY_H,
                 type="CABLE TRAY, LADDER", section="683 x 127", tier="UF-UPPER (top -60)",
                 segs=[((0.0, 12110.0), (1800.0, 12110.0)),
                       ((1800.0, 12110.0), (1800.0, 9500.0)),
                       ((1800.0, 9500.0), (1800.0, 4850.0)),
                       ((1800.0, 9500.0), (19200.0, 9500.0)),      # serves rows C + D
                       ((1800.0, 4850.0), (19200.0, 4850.0))]),    # serves rows A + B
    "BW-1": dict(service="POWER", kind="busway", zc=BUS_ZC, w=BUS_W, h=BUS_H,
                 type="BUSWAY", section="128 x 147", tier="UF-UPPER (top -60)",
                 segs=[((0.0, 12830.0), (2525.0, 12830.0)),
                       ((2525.0, 12830.0), (2525.0, 10230.0)),
                       ((2525.0, 10230.0), (19580.0, 10230.0)),     # serves rows C + D
                       ((19580.0, 10230.0), (19580.0, 4120.0)),
                       ((19580.0, 4120.0), (1800.0, 4120.0))]),     # serves rows A + B
    "CHW-1": dict(service="CHILLED WATER", kind="pipe", zc=CHW_ZC, w=PIPE_OD, h=PIPE_OD,
                  type="STEEL PIPE, DN100", section="OD 114.3 (jacket OD 168.3)", tier="UF-LOWER (centre -480)",
                  segs=[((0.0, 12470.0), (1800.0, 12470.0)),
                        ((1800.0, 12470.0), (1800.0, 9867.0)),
                        ((1800.0, 9867.0), (1800.0, 4467.0)),
                        ((1800.0, 4467.0), (1800.0, 1950.0)),       # CRAH-01
                        ((1800.0, 9867.0), (19200.0, 9867.0)),      # header rows C + D
                        ((1800.0, 4467.0), (9600.0, 4467.0)),       # header rows A + B
                        ((9600.0, 4467.0), (17400.0, 4467.0)),
                        ((17400.0, 4467.0), (19200.0, 4467.0)),
                        ((9600.0, 4467.0), (9600.0, 1950.0)),       # CRAH-02
                        ((17400.0, 4467.0), (17400.0, 1950.0)),     # CRAH-03
                        ((17400.0, 1950.0), (25800.0, 1950.0))]),   # CRAH-04
}
IFC_CLASS = {"tray": ("IfcCableCarrierSegment", "CABLETRAYSEGMENT", "Cable Tray"),
             "busway": ("IfcCableSegment", "BUSBARSEGMENT", "Busway"),
             "pipe": ("IfcPipeSegment", "RIGIDSEGMENT", "Chilled Water Pipe")}


def seg_box(svc, seg, envelope=False):
    """World AABB of a route segment: (x0, y0, z0, x1, y1, z1)."""
    (xa, ya), (xb, yb) = seg
    S = SERVICES[svc]
    if S["kind"] == "pipe":
        r = (JACKET_OD if envelope else PIPE_OD) / 2.0
        hw = hh = r
    else:
        hw, hh = S["w"] / 2.0, S["h"] / 2.0
    if abs(ya - yb) < 1e-9:      # along X
        return (min(xa, xb), ya - hw, S["zc"] - hh, max(xa, xb), ya + hw, S["zc"] + hh)
    return (xa - hw, min(ya, yb), S["zc"] - hh, xa + hw, max(ya, yb), S["zc"] + hh)


def seg_len(seg):
    (xa, ya), (xb, yb) = seg
    return abs(xa - xb) + abs(ya - yb)


def box_gaps(a, b):
    return tuple(max(a[i], b[i]) - min(a[i + 3], b[i + 3]) for i in range(3))   # >0 = clear


# busway supports (E-101 note 4: support at 1500 max) -> <= 1400 centres,
# kept clear of the CHW crossings below the busway.
def busway_supports():
    keep_out = []
    for seg in SERVICES["CHW-1"]["segs"]:
        keep_out.append(seg_box("CHW-1", seg, envelope=True))
    out = []
    for si, seg in enumerate(SERVICES["BW-1"]["segs"]):
        (xa, ya), (xb, yb) = seg
        L = seg_len(seg)
        ux, uy = (xb - xa) / L, (yb - ya) / L
        along_x = abs(uy) < 1e-9

        def ok(s):
            px, py = xa + ux * s, ya + uy * s
            if along_x:
                bx = (px - 25.0, py - BUS_W / 2.0, px + 25.0, py + BUS_W / 2.0)
            else:
                bx = (px - BUS_W / 2.0, py - 25.0, px + BUS_W / 2.0, py + 25.0)
            for k in keep_out:
                if bx[0] < k[3] + 40 and bx[2] > k[0] - 40 and bx[1] < k[4] + 40 and bx[3] > k[1] - 40:
                    return False
            return True
        cands = [s for s in np.arange(0.0, L + 1e-6, 10.0) if ok(float(s))]
        if not cands:
            continue
        chosen = [cands[0]]
        while chosen[-1] < L - 1e-6:
            nxt = [c for c in cands if chosen[-1] < c <= chosen[-1] + 1400.0 + 1e-6]
            if not nxt:
                if L - chosen[-1] <= 400.0:      # short end cantilever over a CHW crossing
                    break
                raise RuntimeError("support spacing cannot be met")
            if L - chosen[-1] <= 1400.0 and ok(L):
                chosen.append(L)
                break
            chosen.append(max(nxt))
        for s in chosen:
            out.append(dict(seg=si, s=float(s), x=xa + ux * float(s), y=ya + uy * float(s), along_x=along_x))
    # de-duplicate shared corner supports
    ded = []
    for p in out:
        if all(abs(p["x"] - q["x"]) + abs(p["y"] - q["y"]) > 100.0 for q in ded):
            ded.append(p)
    return ded


SUPPORTS = busway_supports()

# =============================================================================
# 4. IFC HELPERS
# =============================================================================
f = ifcopenshell.file(schema="IFC4")
f.header.file_name.name = os.path.basename(OUT_PATH)
f.header.file_name.time_stamp = "2026-07-27T00:00:00"
f.header.file_name.author = ("JRK",)
f.header.file_name.organization = ("MERIDIAN DIGITAL INFRASTRUCTURE",)

_NS = uuid.UUID("6f1d2b4e-9c1a-4c55-8a10-5d0c0c0dc005")


def gid(key):
    return ifcopenshell.guid.compress(uuid.uuid5(_NS, key).hex)


def P3(x, y, z):
    return f.createIfcCartesianPoint((float(x), float(y), float(z)))


def P2(x, y):
    return f.createIfcCartesianPoint((float(x), float(y)))


def D3(x, y, z):
    return f.createIfcDirection((float(x), float(y), float(z)))


def ax3(o=(0.0, 0.0, 0.0), z=None, x=None):
    return f.createIfcAxis2Placement3D(P3(*o), D3(*z) if z else None, D3(*x) if x else None)


ORIGIN2 = f.createIfcAxis2Placement2D(P2(0.0, 0.0), None)

# units: millimetre project length unit
units = f.createIfcUnitAssignment([
    f.createIfcSIUnit(None, "LENGTHUNIT", "MILLI", "METRE"),
    f.createIfcSIUnit(None, "AREAUNIT", None, "SQUARE_METRE"),
    f.createIfcSIUnit(None, "VOLUMEUNIT", None, "CUBIC_METRE"),
    f.createIfcSIUnit(None, "PLANEANGLEUNIT", None, "RADIAN"),
    f.createIfcSIUnit(None, "MASSUNIT", "KILO", "GRAM"),
])
ctx = f.createIfcGeometricRepresentationContext(None, "Model", 3, 1.0e-5, ax3(), None)
body_ctx = f.createIfcGeometricRepresentationSubContext("Body", "Model", None, None, None, None, ctx, None,
                                                         "MODEL_VIEW", None)

project = f.createIfcProject(gid("project"), None, "MDC-2026-014", "Meridian Data Center - Phase 1",
                             None, "MDC-2026-014", "ISSUED FOR CONSTRUCTION", [ctx], units)
site_pl = f.createIfcLocalPlacement(None, ax3())
site = f.createIfcSite(gid("site"), None, "Meridian Data Center Site", None, None, site_pl, None, None,
                       "ELEMENT", None, None, None, None, None)
bldg_pl = f.createIfcLocalPlacement(site_pl, ax3())
building = f.createIfcBuilding(gid("building"), None, "Meridian Data Center", "Phase 1", None, bldg_pl, None,
                               None, "ELEMENT", None, None, None)
storey_pl = f.createIfcLocalPlacement(bldg_pl, ax3())
storey = f.createIfcBuildingStorey(gid("storey"), None, "DATA HALL 1", "Finished floor +-0 = top of access floor",
                                   None, storey_pl, None, None, "ELEMENT", 0.0)
f.createIfcRelAggregates(gid("agg-project"), None, None, None, project, [site])
f.createIfcRelAggregates(gid("agg-site"), None, None, None, site, [building])
f.createIfcRelAggregates(gid("agg-building"), None, None, None, building, [storey])

CONTAINED = []


def shape(items, rtype="SweptSolid"):
    rep = f.createIfcShapeRepresentation(body_ctx, "Body", rtype, items)
    return f.createIfcProductDefinitionShape(None, None, [rep])


def extrude_rect(xdim, ydim, depth, pos=None):
    prof = f.createIfcRectangleProfileDef("AREA", None, ORIGIN2, float(xdim), float(ydim))
    return f.createIfcExtrudedAreaSolid(prof, pos or ax3(), D3(0, 0, 1), float(depth))


def extrude_circle(r, depth, pos=None):
    prof = f.createIfcCircleProfileDef("AREA", None, ORIGIN2, float(r))
    return f.createIfcExtrudedAreaSolid(prof, pos or ax3(), D3(0, 0, 1), float(depth))


def placement(x, y, z, angle_deg=0.0, zdir=None, xdir=None):
    if zdir is not None:
        a = ax3((x, y, z), zdir, xdir)
    elif abs(angle_deg) < 1e-12:
        a = ax3((x, y, z))
    else:
        t = math.radians(angle_deg)
        c, s = round(math.cos(t), 12), round(math.sin(t), 12)
        a = ax3((x, y, z), (0.0, 0.0, 1.0), (c, s, 0.0))
    return f.createIfcLocalPlacement(storey_pl, a)


def _val(v):
    if isinstance(v, bool):
        return f.createIfcBoolean(v)
    if isinstance(v, int):
        return f.createIfcInteger(v)
    if isinstance(v, float):
        return f.createIfcReal(round(v, 3))
    s = str(v)
    return f.createIfcText(s) if len(s) > 120 else f.createIfcLabel(s)


def _len(v):
    return f.createIfcLengthMeasure(round(float(v), 3))


def pset(obj, name, props, lengths=()):
    vals = []
    for k, v in props.items():
        if v is None:
            continue
        nv = _len(v) if (k in lengths and isinstance(v, (int, float)) and not isinstance(v, bool)) else _val(v)
        vals.append(f.createIfcPropertySingleValue(k, None, nv, None))
    ps = f.createIfcPropertySet(gid("pset-%s-%s" % (obj.GlobalId, name)), None, name, None, vals)
    f.createIfcRelDefinesByProperties(gid("rdp-%s-%s" % (obj.GlobalId, name)), None, None, None, [obj], ps)
    return ps


def add(cls, key, name, objtype, plc, items, tag=None, desc=None, **attrs):
    el = f.create_entity(cls, GlobalId=gid(key), Name=name, Description=desc, ObjectType=objtype,
                         ObjectPlacement=plc, Representation=shape(items) if items else None, Tag=tag, **attrs)
    CONTAINED.append(el)
    pset(el, "Pset_DCM_Common", dict(Tag=tag or name, Category=objtype, IfcClass=cls,
                                    Discipline=("MEP ROUTE" if cls in ("IfcCableCarrierSegment", "IfcCableSegment",
                                                                       "IfcPipeSegment") else "COORDINATION BACKGROUND"
                                                if cls not in ("IfcElementAssembly", "IfcBuildingElementProxy")
                                                else "DIAGNOSTIC"),
                                    SourceSheets=SOURCE_SHEETS.get(objtype, "A-101")))
    return el


SOURCE_SHEETS = {"Rack": "A-101 / A-601", "CRAH": "A-101 / A-601 / M-101", "PDU": "A-601 / E-101",
                 "Structural Column": "A-101 / A-301", "Access Floor": "A-301 / A-602",
                 "Containment Roof": "A-101 / A-602", "Containment Door": "A-101 / A-602",
                 "Sprinkler Head": "F-101 / A-301", "Cable Tray": "E-101 / A-602", "Busway": "E-101 / A-602",
                 "Chilled Water Pipe": "M-101 / A-602", "Busway Support": "E-101"}


# =============================================================================
# 5. BACKGROUND MODEL
# =============================================================================
# 5.1 access floor: 35 mm panel, top at +-0, following the room outline
poly = f.createIfcPolyline([P2(x, y) for x, y in ROOM] + [P2(*ROOM[0])])
floor_prof = f.createIfcArbitraryClosedProfileDef("AREA", "DATA HALL 1 OUTLINE", poly)
floor_solid = f.createIfcExtrudedAreaSolid(floor_prof, ax3(), D3(0, 0, 1), PANEL_THK)
acc_floor = add("IfcCovering", "access-floor", "ACCESS FLOOR", "Access Floor", placement(0, 0, -PANEL_THK),
                [floor_solid], tag="AF-01", desc="600 x 600 raised access floor panel, 35 thk, top at FF +-0",
                PredefinedType="FLOORING")
pset(acc_floor, "Pset_DCM_AccessFloor", dict(PanelThickness=PANEL_THK, TopElevation=FFL, TileGrid=TILE,
                                             GridOrigin="SOUTH-WEST INTERNAL CORNER", PlenumDepth=565.0,
                                             SlabTopElevation=SLAB_TOP, UnderFloorPathwayZone=545.0,
                                             PedestalsModelled=False),
     lengths=("PanelThickness", "TopElevation", "TileGrid", "PlenumDepth", "SlabTopElevation",
              "UnderFloorPathwayZone"))

# 5.2 structural columns (FF to soffit, A-301 note 4)
for c in columns:
    el = add("IfcColumn", "col-" + c["tag"], c["tag"], "Structural Column",
             placement(c["cx"], c["cy"], FFL), [extrude_rect(COL_SIZE, COL_SIZE, SOFFIT - FFL)],
             tag=c["grid"], desc="Structural column, grid %s, FF to soffit" % c["grid"], PredefinedType="COLUMN")
    pset(el, "Pset_DCM_Column", dict(GridReference=c["grid"], GridX=c["cx"], GridY=c["cy"], Width=COL_SIZE,
                                     Depth=COL_SIZE, BaseElevation=FFL, TopElevation=SOFFIT,
                                     HardObstruction=True, TileAddress=tile_of(c["cx"] - 300, c["cy"] - 300)),
         lengths=("GridX", "GridY", "Width", "Depth", "BaseElevation", "TopElevation"))

# 5.3 racks
for r in racks:
    w, d = r["x1"] - r["x0"], r["y1"] - r["y0"]
    cx, cy = (r["x0"] + r["x1"]) / 2.0, (r["y0"] + r["y1"]) / 2.0
    ang = FACING_DEG[r["faces"]]
    el = add("IfcFurniture", "rack-" + r["tag"], r["tag"], "Rack", placement(cx, cy, FFL, ang),
             [extrude_rect(w, d, CABINET_H)], tag=r["tag"], desc=r["desc"], PredefinedType="USERDEFINED")
    pset(el, "Pset_DCM_Rack", dict(Tag=r["tag"], Row=r["row"], BayIndex=r["bay"], CabinetType=r["typ"],
                                   Width=w, Depth=d, Height=CABINET_H, RackUnits=42, FrontFaces=r["faces"],
                                   FacingAngle=ang, TileAddress=tile_of(r["x0"], r["y0"]),
                                   FootprintMinX=r["x0"], FootprintMinY=r["y0"], FootprintMaxX=r["x1"],
                                   FootprintMaxY=r["y1"], CentreX=cx, CentreY=cy, PowerKW=8.0, LoadKg=1363.0,
                                   RowCentreline=row_by[r["row"]]["cl"]),
         lengths=("Width", "Depth", "Height", "FootprintMinX", "FootprintMinY", "FootprintMaxX", "FootprintMaxY",
                  "CentreX", "CentreY", "RowCentreline"))

# 5.4 CRAH units
CRAH_ELS = {}
for c in perim_crahs + inrow_crahs:
    w, d = c["x1"] - c["x0"], c["y1"] - c["y0"]
    cx, cy = (c["x0"] + c["x1"]) / 2.0, (c["y0"] + c["y1"]) / 2.0
    ang = FACING_DEG[c["faces"]]
    perim = "row" not in c
    el = add("IfcUnitaryEquipment", "crah-" + c["tag"], c["tag"], "CRAH", placement(cx, cy, FFL, ang),
             [extrude_rect(w, d, CABINET_H)], tag=c["tag"],
             desc=("Perimeter CRAH, chilled water DN100" if perim else "In-row CRAH, chilled water DN50"),
             PredefinedType="AIRHANDLER")
    CRAH_ELS[c["tag"]] = (el, c)
    pset(el, "Pset_DCM_CRAH", dict(Tag=c["tag"], Placement=("PERIMETER" if perim else "IN-ROW"),
                                   Row=(None if perim else c["row"]), Width=w, Depth=d, Height=CABINET_H,
                                   CapacityKW=(100.0 if perim else 50.0), AirflowM3h=(20000.0 if perim else 9000.0),
                                   FrontFaces=c["faces"], FacingAngle=ang, TileAddress=tile_of(c["x0"], c["y0"]),
                                   ChilledWaterBranch=("DN100" if perim else "DN50"), CentreX=cx, CentreY=cy,
                                   ServiceClearance=914.0),
         lengths=("Width", "Depth", "Height", "CentreX", "CentreY", "ServiceClearance"))

# 5.5 PDUs
PDU_ELS = {}
for p in pdus:
    cx, cy = (p["x0"] + p["x1"]) / 2.0, (p["y0"] + p["y1"]) / 2.0
    ang = FACING_DEG[p["faces"]]
    el = add("IfcElectricDistributionBoard", "pdu-" + p["tag"], p["tag"], "PDU", placement(cx, cy, FFL, ang),
             [extrude_rect(PDU_W, PDU_D, PDU_H)], tag=p["tag"], desc="Power distribution unit 225 kVA",
             PredefinedType="DISTRIBUTIONBOARD")
    PDU_ELS[p["tag"]] = (el, p)

# 5.6 cold-aisle containment CAC-BC: 4 roof panels + 4 end doors
for i, (a, b) in enumerate(ROOF_PANELS_X, 1):
    el = add("IfcCovering", "roof-%d" % i, "%s-ROOF-%d" % (CONT_TAG, i), "Containment Roof",
             placement((a + b) / 2.0, AISLE_CY, ROOF_UNDERSIDE), [extrude_rect(b - a, ROOF_W, ROOF_T)],
             tag="%s-R%d" % (CONT_TAG, i), desc="Cold-aisle containment roof panel (rows B / C)",
             PredefinedType="ROOFING")
    pset(el, "Pset_DCM_Containment", dict(Tag=CONT_TAG, Contains="ROWS B / C", Component="ROOF PANEL", PanelIndex=i,
                                          PanelCount=4, RoofWidth=ROOF_W, RoofThickness=ROOF_T,
                                          RoofUnderside=ROOF_UNDERSIDE, StartX=a, EndX=b, AisleMinY=AISLE_Y0,
                                          AisleMaxY=AISLE_Y1, FixedObstructionWiderThan1200=True,
                                          HeadsBeneath=sum(1 for hx, hy in INAISLE_HEADS if a < hx < b)),
         lengths=("RoofWidth", "RoofThickness", "RoofUnderside", "StartX", "EndX", "AisleMinY", "AisleMaxY"))
for i, (a, b) in enumerate(DOORS_X, 1):
    el = add("IfcDoor", "door-%d" % i, "%s-DOOR-%d" % (CONT_TAG, i), "Containment Door",
             placement((a + b) / 2.0, AISLE_CY, FFL), [extrude_rect(b - a, ROOF_W, DOOR_H)],
             tag="%s-D%d" % (CONT_TAG, i), desc="Containment end door 60 x 2055.5",
             OverallHeight=DOOR_H, OverallWidth=ROOF_W, PredefinedType="DOOR", OperationType="SLIDING_TO_LEFT")
    pset(el, "Pset_DCM_Containment", dict(Tag=CONT_TAG, Contains="ROWS B / C", Component="END DOOR", DoorIndex=i,
                                          DoorCount=4, DoorThickness=DOOR_T, DoorHeight=DOOR_H, StartX=a, EndX=b),
         lengths=("DoorThickness", "DoorHeight", "StartX", "EndX"))

# 5.7 sprinkler heads
HEAD_ELS = []
for i, (x, y) in enumerate(CEILING_HEADS, 1):
    el = add("IfcFireSuppressionTerminal", "spk-c-%03d" % i, "SPK-C%03d" % i, "Sprinkler Head",
             placement(x, y, DEFLECTOR), [extrude_circle(HEAD_R, SOFFIT - DEFLECTOR)], tag="SPK-C%03d" % i,
             desc="Pendent sprinkler, ceiling, wet pipe", PredefinedType="SPRINKLER")
    HEAD_ELS.append((el, x, y, DEFLECTOR, "CEILING"))
for i, (x, y) in enumerate(INAISLE_HEADS, 1):
    el = add("IfcFireSuppressionTerminal", "spk-a-%03d" % i, "SPK-A%03d" % i, "Sprinkler Head",
             placement(x, y, INAISLE_DEFLECTOR), [extrude_circle(HEAD_R, ROOF_UNDERSIDE - INAISLE_DEFLECTOR)],
             tag="SPK-A%03d" % i, desc="Pendent sprinkler, in-aisle under containment roof",
             PredefinedType="SPRINKLER")
    HEAD_ELS.append((el, x, y, INAISLE_DEFLECTOR, "IN-AISLE"))

# =============================================================================
# 6. ROUTED SERVICES
# =============================================================================
SYS_ENUM = {"CT-1": "DATA", "BW-1": "ELECTRICAL", "CHW-1": "CHILLEDWATER"}
SVC_TYPE = {"tray": "CABLE_TRAY", "busway": "BUSWAY", "pipe": "CHILLED_WATER"}
SEG_ELS = {}
for svc, S in SERVICES.items():
    cls, ptype, otype = IFC_CLASS[S["kind"]]
    els = []
    for i, seg in enumerate(S["segs"], 1):
        (xa, ya), (xb, yb) = seg
        L = seg_len(seg)
        d = ((xb - xa) / L, (yb - ya) / L, 0.0)
        xdir = (-d[1], d[0], 0.0)                     # up x d  -> profile Y = world Z
        plc = placement(xa, ya, S["zc"], zdir=d, xdir=xdir)
        if S["kind"] == "pipe":
            solid = extrude_circle(PIPE_OD / 2.0, L)
        else:
            solid = extrude_rect(S["w"], S["h"], L)
        name = "%s-%02d" % (svc, i)
        el = add(cls, "seg-%s-%02d" % (svc, i), name, otype, plc, [solid], tag=name,
                 desc="%s %s segment %d (under-floor plenum)" % (svc, S["type"], i), PredefinedType=ptype)
        bx = seg_box(svc, seg)
        top = bx[5] if S["kind"] != "pipe" else S["zc"] + JACKET_OD / 2.0
        bot = bx[2] if S["kind"] != "pipe" else S["zc"] - JACKET_OD / 2.0
        props = dict(ServiceTag=svc, Service=S["service"], ServiceType=SVC_TYPE[S["kind"]], System=svc,
                     PathwayType=S["type"], Section=S["section"],
                     SegmentIndex=i, StartX=xa, StartY=ya, EndX=xb, EndY=yb, CentrelineElevation=S["zc"],
                     TopElevation=top, BottomElevation=bot, Length=L, Zone="UNDER-FLOOR PLENUM",
                     ElevationBand="BELOW FINISHED FLOOR", Tier=S["tier"], Direction=("EW" if abs(d[0]) > 0.5 else "NS"),
                     UnderFloorLength=L, OverheadLength=0.0, ClearBandLength=0.0)
        if S["kind"] == "pipe":
            props.update(OuterDiameter=PIPE_OD, InsulationThickness=INSUL_T, InsulatedOuterDiameter=JACKET_OD,
                         NominalDiameter="DN100")
        else:
            props.update(Width=S["w"], Height=S["h"])
        pset(el, "Pset_DCM_Service", props,
             lengths=("StartX", "StartY", "EndX", "EndY", "CentrelineElevation", "TopElevation", "BottomElevation",
                      "Length", "UnderFloorLength", "OverheadLength", "ClearBandLength", "OuterDiameter",
                      "InsulationThickness", "InsulatedOuterDiameter", "Width", "Height"))
        els.append(el)
    SEG_ELS[svc] = els

# MEP ports: every segment has a start port (SINK) and one end port (SOURCE) per
# downstream segment; junctions are connected port-to-port (IfcRelConnectsPorts).
PORT_TYPE = {"tray": "CABLECARRIER", "busway": "CABLE", "pipe": "PIPE"}
for svc, S in SERVICES.items():
    segs, els = S["segs"], SEG_ELS[svc]

    def mkport(el, seg_i, local_z, flow, label):
        plc = f.createIfcLocalPlacement(el.ObjectPlacement, ax3((0.0, 0.0, float(local_z))))
        pt = f.createIfcDistributionPort(gid("port-%s-%02d-%s" % (svc, seg_i + 1, label)), None,
                                         "%s-%02d-%s" % (svc, seg_i + 1, label), None, None, plc, None, flow,
                                         PORT_TYPE[S["kind"]], SYS_ENUM[svc])
        return pt
    nested = {i: [] for i in range(len(segs))}
    starts = {}
    for i, seg in enumerate(segs):
        starts[i] = mkport(els[i], i, 0.0, "SINK", "IN")
        nested[i].append(starts[i])
    for i, seg in enumerate(segs):
        children = [j for j, sj in enumerate(segs) if j != i and sj[0] == seg[1]]
        if not children:
            nested[i].append(mkport(els[i], i, seg_len(seg), "SOURCE", "END"))
        for k, j in enumerate(children):
            op = mkport(els[i], i, seg_len(seg), "SOURCE", "OUT%d" % (k + 1))
            nested[i].append(op)
            f.createIfcRelConnectsPorts(gid("conn-%s-%02d-%02d" % (svc, i + 1, j + 1)), None,
                                        "%s-%02d>%02d" % (svc, i + 1, j + 1), None, op, starts[j], None)
    for i in nested:
        f.createIfcRelNests(gid("nest-%s-%02d" % (svc, i + 1)), None, None, None, els[i], nested[i])

# distribution systems (grouping) with length split diagnostics
LEN_SPLIT = {}
for svc, S in SERVICES.items():
    tot = sum(seg_len(s) for s in S["segs"])
    LEN_SPLIT[svc] = dict(total=tot, under_floor=tot, overhead=0.0, clear_band=0.0, above_band=0.0)
    sysobj = f.createIfcDistributionSystem(gid("sys-" + svc), None, svc, "%s - %s" % (S["service"], S["type"]),
                                           S["service"], None, SYS_ENUM[svc])
    f.createIfcRelAssignsToGroup(gid("grp-" + svc), None, None, None, SEG_ELS[svc], None, sysobj)
    f.createIfcRelServicesBuildings(gid("srv-" + svc), None, None, None, sysobj, [storey])
    pset(sysobj, "Pset_DCM_ServiceSummary",
         dict(ServiceTag=svc, Service=S["service"], SegmentCount=len(S["segs"]), TotalCentrelineLength=tot,
              UnderFloorCentrelineLength=tot, OverheadCentrelineLength=0.0, ClearHeightBandLength=0.0,
              AboveClearBandLength=0.0, EntryX=ENTRY[0], EntryY=ENTRY[1],
              EntryOffset=min(math.hypot(s[0][0] - ENTRY[0], s[0][1] - ENTRY[1]) for s in S["segs"]),
              Tier=S["tier"]),
         lengths=("TotalCentrelineLength", "UnderFloorCentrelineLength", "OverheadCentrelineLength",
                  "ClearHeightBandLength", "AboveClearBandLength", "EntryX", "EntryY", "EntryOffset"))

# busway supports (floor stands from slab to underside of busway, 1 mm gap)
BUS_BOT = BUS_ZC - BUS_H / 2.0
sup_spans = []
for i, s in enumerate(SUPPORTS, 1):
    h = (BUS_BOT - 1.0) - SLAB_TOP
    xd, yd = (50.0, BUS_W) if s["along_x"] else (BUS_W, 50.0)
    el = add("IfcElementAssembly", "sup-%03d" % i, "BW-1-SUP-%03d" % i, "Busway Support",
             placement(s["x"], s["y"], SLAB_TOP), [extrude_rect(xd, yd, h)], tag="BW-1-SUP-%03d" % i,
             desc="Busway floor-stand support, 1500 max centres (E-101 note 4)", PredefinedType="USERDEFINED",
             AssemblyPlace="SITE")
    pset(el, "Pset_DCM_Support", dict(SupportsService="BW-1", SupportType="FLOOR STAND (UNDER-FLOOR)",
                                      MaxSpacingRequired=BUS_SUPPORT_MAX, SegmentIndex=s["seg"] + 1,
                                      PositionAlongSegment=s["s"]),
         lengths=("MaxSpacingRequired", "PositionAlongSegment"))
# maximum unsupported span per busway segment
MAX_SPAN = 0.0
for si, seg in enumerate(SERVICES["BW-1"]["segs"]):
    (xa, ya), (xb, yb) = seg
    pos = sorted([abs(p["x"] - xa) + abs(p["y"] - ya) for p in SUPPORTS
                  if (abs(p["y"] - ya) < 1e-6 and abs(ya - yb) < 1e-6 and min(xa, xb) - 1 <= p["x"] <= max(xa, xb) + 1)
                  or (abs(p["x"] - xa) < 1e-6 and abs(xa - xb) < 1e-6 and min(ya, yb) - 1 <= p["y"] <= max(ya, yb) + 1)])
    pts = [0.0] + pos + [seg_len(seg)]
    MAX_SPAN = max(MAX_SPAN, max(b - a for a, b in zip(pts[:-1], pts[1:])))

# terminations / taps (diagnostic markers, small solids clear of everything)
TERMS = []


def term_marker(key, name, otype, x, y, z0, serves, svc):
    el = add("IfcBuildingElementProxy", "term-" + key, name, otype, placement(x, y, z0),
             [extrude_rect(50.0, 50.0, 30.0 if svc == "CHW-1" else 50.0)], tag=name,
             desc="%s termination / tap serving %s" % (svc, serves), PredefinedType="USERDEFINED")
    pset(el, "Pset_DCM_Termination", dict(TerminatesService=svc, Serves=serves, TapX=x, TapY=y),
         lengths=("TapX", "TapY"))
    TERMS.append(dict(service=svc, serves=serves, x=x, y=y, z=z0))


CHW_TOP_ENV = CHW_ZC + JACKET_OD / 2.0          # -395.85
for c in inrow_crahs:
    cx = (c["x0"] + c["x1"]) / 2.0
    hy = 4467.0 if c["row"] in ("A", "B") else 9867.0
    hy += -35.0 if c["row"] in ("A", "C") else 35.0       # tap on the side facing the served row
    term_marker("chw-" + c["tag"], "CHW-1-TAP-" + c["tag"], "CHW Tap Termination", cx, hy, -360.0, c["tag"], "CHW-1")
for c, (tx, ty) in zip(perim_crahs, [(1800.0, 1950.0), (9600.0, 1950.0), (17400.0, 1950.0), (25800.0, 1950.0)]):
    term_marker("chw-" + c["tag"], "CHW-1-TAP-" + c["tag"], "CHW Tap Termination", tx, ty, -360.0, c["tag"], "CHW-1")
for row, yy in (("A", 4850.0 - TRAY_W / 2.0 - 10.0 - 25.0), ("B", 4850.0 + TRAY_W / 2.0 + 10.0 + 25.0),
                ("C", 9500.0 - TRAY_W / 2.0 - 10.0 - 25.0), ("D", 9500.0 + TRAY_W / 2.0 + 10.0 + 25.0)):
    term_marker("ct-" + row, "CT-1-DROP-ROW-" + row, "Tray Drop Termination", 10500.0, yy, TRAY_ZC - 25.0,
                "ROW " + row, "CT-1")
for row, yy in (("A", 4120.0 - BUS_W / 2.0 - 10.0 - 25.0), ("B", 4120.0 + BUS_W / 2.0 + 10.0 + 25.0),
                ("C", 10230.0 - BUS_W / 2.0 - 10.0 - 25.0), ("D", 10230.0 + BUS_W / 2.0 + 10.0 + 25.0)):
    term_marker("bw-" + row, "BW-1-TAP-ROW-" + row, "Busway Tap Termination", 10500.0, yy, BUS_ZC - 25.0,
                "ROW " + row, "BW-1")

# =============================================================================
# 7. DIAGNOSTICS (achieved clearances)
# =============================================================================
def service_top(svc):
    S = SERVICES[svc]
    return S["zc"] + (JACKET_OD / 2.0 if S["kind"] == "pipe" else S["h"] / 2.0)


HEAD_CLEAR = []
for el, x, y, zdef, kind in HEAD_ELS:
    props = dict(Tag=el.Name, HeadType=kind, DeflectorElevation=zdef, StandoffRequired=STANDOFF,
                 StandoffZoneBottom=zdef - STANDOFF, ProtectionAreaMax="20.9 m2", MaxSpacing=4600.0)
    rec = {"head": el.Name, "x": x, "y": y, "deflector": zdef}
    for svc, key in (("CT-1", "Tray"), ("BW-1", "Busway"), ("CHW-1", "ChilledWater")):
        under = [s for s in SERVICES[svc]["segs"]
                 if (lambda b: b[0] - HEAD_R <= x <= b[3] + HEAD_R and b[1] - HEAD_R <= y <= b[4] + HEAD_R)(
                     seg_box(svc, s, envelope=True))]
        if under:
            cl = zdef - service_top(svc)
            props["ClearanceToTopOf" + key] = cl
            rec[svc] = cl
        else:
            props["ClearanceToTopOf" + key] = "NO %s RUN BENEATH" % key.upper()
            rec[svc] = None
    # nearest service in plan and its vertical clearance
    best = None
    for svc in SERVICES:
        for s in SERVICES[svc]["segs"]:
            b = seg_box(svc, s, envelope=True)
            dx = max(b[0] - x, 0.0, x - b[3])
            dy = max(b[1] - y, 0.0, y - b[4])
            dpl = math.hypot(dx, dy)
            if best is None or dpl < best[0]:
                best = (dpl, svc, zdef - b[5])
    props.update(NearestServicePlanDistance=best[0], NearestService=best[1], NearestServiceVerticalClearance=best[2],
                 StandoffCompliant=True)
    rec.update(nearest_plan=best[0], nearest_service=best[1], nearest_vertical=best[2])
    HEAD_CLEAR.append(rec)
    pset(el, "Pset_DCM_Clearance", props,
         lengths=("DeflectorElevation", "StandoffRequired", "StandoffZoneBottom", "MaxSpacing",
                  "ClearanceToTopOfTray", "ClearanceToTopOfBusway", "ClearanceToTopOfChilledWater",
                  "NearestServicePlanDistance", "NearestServiceVerticalClearance"))

PDU_CLEAR = []
for tag, (el, p) in PDU_ELS.items():
    pb = (p["x0"], p["y0"], FFL, p["x1"], p["y1"], PDU_H)
    best = None
    for s in SERVICES["CHW-1"]["segs"]:
        b = seg_box("CHW-1", s, envelope=True)
        g = box_gaps(pb, b)
        d3 = math.sqrt(sum(max(v, 0.0) ** 2 for v in g))
        if best is None or d3 < best[0]:
            best = (d3, b, s)
    vert = PDU_H - best[1][5]
    PDU_CLEAR.append(dict(pdu=tag, nearest_chw_3d=best[0], pdu_top_to_chw_top_vertical=vert,
                          chw_below_floor=True, chw_in_dedicated_space=False))
    pset(el, "Pset_DCM_PDU", dict(Tag=tag, ServesRow=p["row"], Width=PDU_W, Depth=PDU_D, Height=PDU_H,
                                  RatingKVA=225.0, FrontFaces=p["faces"], FacingAngle=FACING_DEG[p["faces"]],
                                  TileAddress=p["tile"], WorkingSpaceFront=PDU_WORKING,
                                  DedicatedSpaceAbove=PDU_DEDICATED, DedicatedSpaceTop=PDU_H + PDU_DEDICATED,
                                  NearestCHWDistance3D=best[0], VerticalOffsetTopToNearestCHW=vert,
                                  NearestCHWLocation="BELOW ACCESS FLOOR", CHWInDedicatedSpace=False,
                                  CentreX=(p["x0"] + p["x1"]) / 2.0, CentreY=(p["y0"] + p["y1"]) / 2.0),
         lengths=("Width", "Depth", "Height", "WorkingSpaceFront", "DedicatedSpaceAbove", "DedicatedSpaceTop",
                  "NearestCHWDistance3D", "VerticalOffsetTopToNearestCHW", "CentreX", "CentreY"))

PAIR_SEP = []
for i, ts in enumerate(SERVICES["CT-1"]["segs"]):
    tb = seg_box("CT-1", ts)
    worst = None
    for j, bs in enumerate(SERVICES["BW-1"]["segs"]):
        bb = seg_box("BW-1", bs)
        g = box_gaps(tb, bb)
        sep = max(g)
        ax = "XYZ"[g.index(sep)]
        PAIR_SEP.append(dict(tray="CT-1-%02d" % (i + 1), busway="BW-1-%02d" % (j + 1), gap_x=g[0], gap_y=g[1],
                             gap_z=g[2], separation=sep, axis=ax))
        if worst is None or sep < worst[0]:
            worst = (sep, ax, "BW-1-%02d" % (j + 1))
    pset(SEG_ELS["CT-1"][i], "Pset_DCM_Clearance",
         dict(MinSeparationToBusway=worst[0], GoverningAxis=worst[1], GoverningBuswaySegment=worst[2],
              RequiredSeparation=TRAY_BUS_SEP, SeparationCompliant=bool(worst[0] >= TRAY_BUS_SEP)),
         lengths=("MinSeparationToBusway", "RequiredSeparation"))
for j, bs in enumerate(SERVICES["BW-1"]["segs"]):
    rows_ = [p for p in PAIR_SEP if p["busway"] == "BW-1-%02d" % (j + 1)]
    w = min(rows_, key=lambda p: p["separation"])
    pset(SEG_ELS["BW-1"][j], "Pset_DCM_Clearance",
         dict(MinSeparationToTray=w["separation"], GoverningAxis=w["axis"], GoverningTraySegment=w["tray"],
              RequiredSeparation=TRAY_BUS_SEP, SeparationCompliant=bool(w["separation"] >= TRAY_BUS_SEP),
              MaxUnsupportedSpanAllSegments=MAX_SPAN),
         lengths=("MinSeparationToTray", "RequiredSeparation", "MaxUnsupportedSpanAllSegments"))

# row coverage (plan, perpendicular reach 2500) for the record
COVERAGE = {}
for R in ROWS:
    x0r, x1r = row_extent[R["row"]]
    COVERAGE[R["row"]] = {}
    for svc, S in SERVICES.items():
        iv = []
        for (xa, ya), (xb, yb) in S["segs"]:
            if abs(ya - yb) < 1e-9 and abs(ya - R["cl"]) <= COVER_REACH:
                a, b = max(min(xa, xb), x0r), min(max(xa, xb), x1r)
                if b > a:
                    iv.append((a, b))
        iv.sort()
        tot, cur = 0.0, None
        for a, b in iv:
            if cur is None or a > cur[1]:
                if cur:
                    tot += cur[1] - cur[0]
                cur = [a, b]
            else:
                cur[1] = max(cur[1], b)
        if cur:
            tot += cur[1] - cur[0]
        COVERAGE[R["row"]][svc] = round(tot / (x1r - x0r), 4)

pset(storey, "Pset_DCM_Hall", dict(HallName="DATA HALL 1", ProjectNumber="MDC-2026-014", FinishedFloor=FFL,
                                   SlabTop=SLAB_TOP, AccessFloorPanel=PANEL_THK, CeilingSoffit=SOFFIT,
                                   MinimumClearHeight=CLEAR_HEIGHT, SprinklerStandoff=STANDOFF,
                                   DeflectorElevation=DEFLECTOR, StandoffZoneBottom=DEFLECTOR - STANDOFF,
                                   OverheadPathwayZoneAvailable=False, RoutingZone="UNDER-FLOOR PLENUM",
                                   TileGrid=TILE, StructuralGridOffsetFromTiles=150.0, CrossAisleEastEdge=CA_EAST,
                                   CrossAisleWestEdge=CA_WEST, Racks=len(racks), CRAHs=len(perim_crahs) + len(inrow_crahs),
                                   PDUs=len(pdus), Columns=len(columns), SprinklerHeads=len(HEAD_ELS)),
     lengths=("FinishedFloor", "SlabTop", "AccessFloorPanel", "CeilingSoffit", "MinimumClearHeight",
              "SprinklerStandoff", "DeflectorElevation", "StandoffZoneBottom", "TileGrid",
              "StructuralGridOffsetFromTiles", "CrossAisleEastEdge", "CrossAisleWestEdge"))

f.createIfcRelContainedInSpatialStructure(gid("contained-storey"), None, "DATA HALL 1 CONTENTS", None,
                                          CONTAINED, storey)

# =============================================================================
# 8. RECONCILIATION LOG (side file next to the IFC)
# =============================================================================
TOTAL_LEN = sum(v["total"] for v in LEN_SPLIT.values())
recon = {
    "project": "MDC-2026-014  DATA HALL 1  (dc_model hall_seed005_d100)",
    "units": "millimetres; elevations relative to finished floor (top of access floor = 0)",
    "routing_summary": {
        "zone": "all three services in the access-floor plenum (no compliant overhead zone exists)",
        "tiers": {"CT-1 tray": "top -60 / bottom -187", "BW-1 busway": "top -60 / bottom -207",
                  "CHW-1 pipe": "centre -480, bare OD 114.3, jacket OD 168.3 -> -564.15 .. -395.85"},
        "centreline_length_mm": {k: v["total"] for k, v in LEN_SPLIT.items()},
        "total_centreline_length_mm": TOTAL_LEN,
        "length_split_mm": LEN_SPLIT,
        "row_coverage_fraction_plan_2500": COVERAGE,
        "min_tray_busway_separation_mm": min(p["separation"] for p in PAIR_SEP),
        "busway_supports": len(SUPPORTS), "busway_max_unsupported_span_mm": MAX_SPAN,
        "terminations": len(TERMS),
    },
    "notes": [
        {"sheet": "A-101", "note": "Access floor tile grid 600 mm, origin SW internal corner, columns lettered A.. east, rows 1.. north",
         "applied": "Tile addresses read spreadsheet-style (A=0..Z=25, AA=26..). The plan axis labels print AA..BT for lines 0..45; the schedule addresses (B01, P01, AC01, AQ01, AN05 ...) only agree with the drawn positions when read A=0, so positions were taken from the plan geometry and addresses checked against them (every row end, PDU and perimeter CRAH verified in-script)."},
        {"sheet": "A-101", "note": "Structural grid 7050 / 7200 / 7200 to column centrelines (both directions), grid offset 150 from tile grid",
         "applied": "8 columns at x,y in {7050, 14250, 21450} inside the L-shaped room (C-3 falls in the no-slab notch); 600 x 600 as measured; modelled FF to soffit (A-301 note 4)."},
        {"sheet": "A-101", "note": "Room 27000 x 24000 with 8400 x 8400 NE notch (keyed note 1 'no slab this area')",
         "applied": "Room / access-floor outline (0,0)-(27000,0)-(27000,15600)-(18600,15600)-(18600,24000)-(0,24000)."},
        {"sheet": "A-101", "note": "Row centreline chain 3000 / 2935 / 2465 / 2935 / 12665 (total 24000)",
         "applied": "Row centrelines A 3000, B 5935, C 8400, D 11335; footprint = centreline +- depth/2 (A-601 note 2)."},
        {"sheet": "A-101", "note": "Pitch class C: cold 1200 clear, hot 1800 clear",
         "applied": "Hot aisles A/B and C/D are 1800 clear; contained cold aisle B/C is 1330 clear (>= 1200)."},
        {"sheet": "A-101", "note": "900 to CRAH face; perimeter CRAH dims 8400 / 7800 / 8400; rows overall 20400; 27000 overall",
         "applied": "Perimeter CRAHs 1200 x 900 at x = 600, 9000, 16800, 25200 (centres 1200/9600/17400/25800); rows run 1800..22200."},
        {"sheet": "A-101", "note": "Cross aisle per ANSI/BICSI 002 6.6.4.3 caps continuous runs at 16 m; east edge common; '1200 CLEAR'",
         "applied": "Every row re-registers at x = 12600 after the CA term; cross-aisle clear zone 11400..12600 kept free of equipment; containment stops and restarts there with a door each side."},
        {"sheet": "A-101", "note": "Heavy outline = 800 distributor cabinet; dashed = spare position, not in contract",
         "applied": "N1 / N2 modelled 800 wide; SP bays left empty (not modelled)."},
        {"sheet": "A-101", "note": "Keyed note 2 west service strip carries the service trunks and risers",
         "applied": "Trunks run N-S in the west strip (x <= 2600) below the floor; strip kept clear of cabinets."},
        {"sheet": "A-101", "note": "Keyed note 4 area reserved for future rows - do not model", "applied": "Nothing modelled there."},
        {"sheet": "A-101", "note": "Detail 2 contained aisle end (1:75): end door outside the row ends, door spans the 1530 roof width",
         "applied": "Doors 60 x 1530 x 2055.5 at x 1740-1800, 11400-11460, 12540-12600, 21000-21060."},
        {"sheet": "A-301", "note": "Ceiling slab soffit +3050; sprinkler deflector plane 25.4 below soffit; 460 keep clear below",
         "applied": "Ceiling deflectors at +3024.6; standoff zone bottom +2564.6 checked against every route (all routes are below FF)."},
        {"sheet": "A-301", "note": "Minimum clear height 2600 (ANSI/TIA-942) - nothing below",
         "applied": "Enforced as headroom rule: no service between FF and 2600. Because 2564.6 < 2600 there is no overhead pathway band, so services were placed below FF."},
        {"sheet": "A-301", "note": "565 plenum, 600 access floor, top of structural slab -600, 35 mm panel, 20 clear under panel (TIA-942-B 8.6.2)",
         "applied": "Under-floor service tops at -60 (25 below the -35 panel underside, >= 20 required); bottoms >= -564.15 (slab -600)."},
        {"sheet": "A-301", "note": "Column height 3050 FF to soffit; columns hard obstructions at every elevation",
         "applied": "Columns 0..3050; under-floor routes also kept clear of column footprints in plan."},
        {"sheet": "A-301", "note": "2000 cabinet; 55.5 containment roof; detail 3 roof 1530 wide, in-aisle head +1890",
         "applied": "Racks / CRAHs 2000 high; roof 2000..2055.5; 10 in-aisle heads with deflector +1890 under the roof."},
        {"sheet": "A-601", "note": "Cabinet schedule: qty 26/21/20/27, first/last tiles, bay sequences, depth 1200/1070, 42 RU, 2000 high, faces S/N/S/N, 8.0 kW, 1363 kg",
         "applied": "94 racks set out by accumulating bay widths from the first tile; last-tile addresses verified."},
        {"sheet": "A-601", "note": "Bay terms: CU in-row cooling 600, SP spare 600, n-600 omitted bays",
         "applied": "Omitted bays (columns A/B/C lines) and spares left empty; rows not re-spaced."},
        {"sheet": "A-601", "note": "Cabinet types C2 600x1070, C1 600x1200, N2 800x1070, N1 800x1200; qty 44/44/4/2",
         "applied": "Type counts reproduced exactly."},
        {"sheet": "A-601", "note": "CRAH schedule: perimeter 1200 x 900 x 2000, 100 kW, 20000 m3/h, faces north, DN100; in-row 600 x 1070 (B,D) / 600 x 1200 (A,C), 50 kW, DN50",
         "applied": "16 CRAHs modelled; in-row units face their row."},
        {"sheet": "A-601", "note": "PDU schedule 762 x 813 x 1959, 225 kVA, 900 front working space; tiles AN05 / AM10 / AL14 / AO19",
         "applied": "PDUs at x 23400 / 22800 / 22400 / 24000 (E-101 plan), front flush with the served row front (A-101 note 8)."},
        {"sheet": "A-601", "note": "Typical cabinet elevation 2000 overall, 42U = 1867, 1U = 44.45; row D elevation 20400 overall",
         "applied": "Height 2000; row D extent 1800..22200 = 20400 confirmed."},
        {"sheet": "A-602", "note": "Containment CAC-BC: rows B/C, 4 roof panels, roof 1530 wide, 55.5 thk, underside 2000, 4 end doors 60 x 2055.5",
         "applied": "Roof split into 4 panels at the column faces (1800-6750, 7350-11400, 12600-13950, 14550-21000) so the grid A/B columns pass clear; 4 doors."},
        {"sheet": "A-602", "note": "Pathway CT-1 cable tray ladder 683 x 127, 300 from power",
         "applied": "Tray 683 x 127; min clear to busway on governing axis %.1f mm (>= 300)." % min(p["separation"] for p in PAIR_SEP)},
        {"sheet": "A-602", "note": "Pathway BW-1 busway 128 x 147, support at 1500 max",
         "applied": "%d floor-stand supports at <= 1400 centres; max unsupported span %.0f mm." % (len(SUPPORTS), MAX_SPAN)},
        {"sheet": "A-602", "note": "Pathway CHW-1 steel pipe DN100 OD 114.3, insulate 25 min",
         "applied": "Pipe modelled at bare OD 114.3; clash envelope uses the 168.3 jacket OD (M-101 note 4) which also covers 114.3 + 2 x 25.4."},
        {"sheet": "A-602", "note": "General construction data FF 0 / slab -600 / panel 35 / soffit +3050 / clear height 2600 / standoff 460",
         "applied": "Used as the governing datums (note 2: schedule governs over section)."},
        {"sheet": "A-602", "note": "Detail 4 pathway zones: deflector +3025, standoff 425 band, 2600 clear height, 545 under-floor zone; 'no overhead pathway zone in this hall'",
         "applied": "All routes in the 545 under-floor zone (-600 .. -55)."},
        {"sheet": "A-602", "note": "Note 4 roof is a fixed obstruction wider than 1200 - heads beneath",
         "applied": "In-aisle heads modelled beneath every roof panel (3/2/1/4 heads)."},
        {"sheet": "M-101", "note": "CHW supply + return entry 2 x DN100 at 12470 from the south wall (west wall)",
         "applied": "CHW-1 network starts at (0, 12470), modelled as one coordinated main (S+R pair)."},
        {"sheet": "M-101", "note": "Pipe to every CRAH, perimeter gallery and in-row alike; header along every row",
         "applied": "Headers at y 4467 (rows A+B) and 9867 (rows C+D), each <= 1468 from both served row centrelines and in-row CRAH centres; spurs end 1500 from each perimeter CRAH centre."},
        {"sheet": "M-101", "note": "914 service clearance at in-row CRAH", "applied": "Kept clear above the floor (all piping below the floor)."},
        {"sheet": "M-101", "note": "Insulation 25 min, jacket OD 168.3 coordinated for clash", "applied": "Clash envelope 168.3."},
        {"sheet": "M-101 / E-101", "note": "No piping within the 1800 dedicated electrical space over a PDU (NFPA 70 110.26(E))",
         "applied": "No CHW within any PDU footprint even in plan; nearest CHW below the floor (see Pset_DCM_PDU)."},
        {"sheet": "E-101", "note": "Busway feed + telecom riser entry at 12470 from the south wall",
         "applied": "Tray enters at y 12110 and busway at y 12830 (360 either side of the marked point) to hold the 300 mm separation from the first segment."},
        {"sheet": "E-101", "note": "Maintain 300 mm clear between telecom tray and busway on at least one axis (TIA-942 7.3.1)",
         "applied": "Tray and busway never cross in plan; every tray/busway pair has >= 314 mm clear horizontally."},
        {"sheet": "E-101", "note": "900 working space at every PDU front", "applied": "No element placed in the working spaces."},
        {"sheet": "E-101", "note": "One-line: service entry -> busway BW-1 -> PDU-01..04 225 kVA -> rows A..D",
         "applied": "Busway serves every row; PDU feeders not modelled (not required by the routing brief)."},
        {"sheet": "F-101", "note": "94 ceiling heads + 10 in-aisle heads; grid 1250 / 2500 typical",
         "applied": "104 heads modelled at the drawn positions."},
        {"sheet": "F-101", "note": "Head interrupted by structure relocated to the nearest clear tile, not omitted; 1500 column keep-out",
         "applied": "Head at (21250, 14350) falls inside column C-2 and is drawn/modelled at (21250, 13750)."},
        {"sheet": "F-101", "note": "Maintain 460 clear below every deflector; NFPA 13 obstruction rule",
         "applied": "Nothing within 460 below any deflector (routes are below FF); clearances stored per head (Pset_DCM_Clearance)."},
        {"sheet": "F-101", "note": "Protection area 20.9 m2 per head max, 4600 max spacing; coverage check 1100 / 600 / 0.7 / 2300",
         "applied": "Recorded only; sprinkler layout is background and not re-designed."},
        {"sheet": "F-101", "note": "No sprinklers below the access floor", "applied": "None modelled; under-floor routes need no heads beneath."},
        {"sheet": "F-101", "note": "In-aisle deflector hangs from the roof soffit", "applied": "In-aisle heads 1890..2000."},
        {"sheet": "brief", "note": "Diagnostic item 3 prefers the 0-2600 clear-height band",
         "applied": "Not applied: placing services in that band would breach the 2600 headroom rule (A-301 / A-602) and clash with cabinets. All services are unambiguously below FF (100 % under-floor, 0 % in band, 0 % above)."},
        {"sheet": "brief", "note": "Diagnostic item 5 drops / terminations",
         "applied": "%d marker elements (ObjectType '... Termination') at the tap points of every CRAH and of every row for tray and busway; modelled as small solids clear of all other elements so they add no route length." % len(TERMS)},
    ],
    "pdu_clearances": PDU_CLEAR,
    "tray_busway_pairs": PAIR_SEP,
    "sprinkler_clearances_with_service_beneath": [h for h in HEAD_CLEAR if any(h.get(s) is not None for s in SERVICES)],
    "sprinkler_clearance_summary": {
        "heads": len(HEAD_CLEAR),
        "heads_with_a_service_directly_beneath": sum(1 for h in HEAD_CLEAR if any(h.get(s) is not None for s in SERVICES)),
        "min_vertical_clearance_deflector_to_nearest_service_top_mm": min(h["nearest_vertical"] for h in HEAD_CLEAR),
        "standoff_required_mm": STANDOFF,
        "per_head_nearest_service": [dict(head=h["head"], x=h["x"], y=h["y"], deflector=h["deflector"],
                                          nearest_service=h["nearest_service"],
                                          plan_distance=round(h["nearest_plan"], 1),
                                          vertical_clearance=round(h["nearest_vertical"], 2)) for h in HEAD_CLEAR],
    },
}

out_dir = os.path.dirname(os.path.abspath(OUT_PATH))
if out_dir and not os.path.isdir(out_dir):
    os.makedirs(out_dir, exist_ok=True)
try:
    with open(os.path.join(out_dir, "reconciliation.json"), "w") as fh:
        json.dump(recon, fh, indent=1, sort_keys=False)
except OSError:
    pass

# =============================================================================
# 9. WRITE IFC (last action)
# =============================================================================
f.write(OUT_PATH)
