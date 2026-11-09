"""Data Hall 1 (MDC-2026-014, dc_model hall_seed000_d000) - coordinated IFC4 model.

Builds the coordination background exactly as drawn on the seven-sheet set
(A-101, A-301, A-601, A-602, M-101, E-101, F-101) and routes the three
services (CT-1 telecom ladder tray, BW-1 busway, CHW-1 chilled water) as
straight axis-aligned segments.  Everything read off the drawings is baked in
below as literals; the PNG sheets are never opened.

Run:  python solution.py [out.ifc]      (default: model.ifc next to this file)

Units: millimetres throughout (IfcSIUnit LENGTHUNIT MILLI METRE).  All
placements are written directly as IfcAxis2Placement3D in project units (mm).

Coordinate frame (A-101 note 3): origin = south-west internal corner of the
hall, +X east, +Y north, Z = 0 at finished floor (top of the 35 mm panel).
"""
import hashlib
import json
import os
import re
import sys
import uuid

import ifcopenshell
import ifcopenshell.guid

OUT_PATH = (sys.argv[1] if len(sys.argv) > 1 else
            os.path.join(os.path.dirname(os.path.abspath(__file__)), "model.ifc"))

# =============================================================================
# 1. DRAWING DATA (literals transcribed from the sheets)
# =============================================================================
TILE = 600.0                       # A-101 note 3, A-602: 600 tile grid
ROOM_X, ROOM_Y = 27000.0, 21000.0  # A-101 overall dimensions
# --- vertical datums, A-301 section 1 / A-602 general construction data ----
FFL = 0.0                          # finished floor = top of access-floor panel
SLAB_TOP = -900.0                  # top of structural slab
PANEL_T = 35.0                     # access floor panel thickness
SOFFIT = 3600.0                    # ceiling slab soffit
DEFLECTOR = SOFFIT - 25.4          # ceiling-head deflector plane (+3574.6)
STANDOFF = 460.0                   # keep-clear below every deflector
STANDOFF_PLANE = DEFLECTOR - STANDOFF   # +3114.6
CLEAR_MIN = 2600.0                 # ANSI/TIA-942 minimum clear height
UNDER_PANEL_CLEAR = 20.0           # TIA-942-B 8.6.2 under-floor tray clearance
COLUMN_TOP = SOFFIT                # A-301 note 4: FF (+0) to soffit
# --- equipment sizes, A-601 / A-602 ----------------------------------------
CAB = {"C1": (600.0, 1200.0, 2000.0, "SERVER CABINET, 600 WIDE"),
       "N1": (800.0, 1200.0, 2000.0, "DISTRIBUTOR CABINET, 800 WIDE")}
CAB_RU, CAB_KW, CAB_KG = 42, 8.0, 1363.0
INROW_CRAH = (600.0, 1200.0, 2000.0)     # 600 x 1200, H 2000, 50 kW, 9000 m3/h
PERIM_CRAH = (1200.0, 900.0, 2000.0)     # 1200 x 900, H 2000, 100 kW, 20000 m3/h
PDU_SIZE = (762.0, 813.0, 1959.0)        # 762 x 813, H 1959, 225 kVA
COLUMN_SIZE = 600.0                      # 600 sq (A-101 / F-101 detail 2)
# --- rows: A-601 cabinet schedule + A-101 row centrelines --------------------
ROW_START_X = 3 * TILE                   # first tile column "D" for every row
CROSS_AISLE_EAST = 11400.0               # A-101 note 5: common east edge
CROSS_AISLE_CLEAR = 1200.0               # A-101 "1200 CLEAR"
ROWS = [  # row, centreline Y, front faces, bay sequence W->E, qty, first, last
    ("A", 3000.0, "SOUTH", "4C1 CU 3C1 N1 3C1 CU CA 6C1 SP CU 5C1", 22, "D05", "AF05"),
    ("B", 6000.0, "NORTH", "4C1 CU 5C1 2N1 CU CA 7C1 SP CU 5C1", 23, "D10", "AG10"),
    ("C", 8400.0, "SOUTH", "3C1 CU 6C1 2-600 CU CA N1 4C1 CU SP C1 2-600 3C1", 18, "D14", "AF14"),
    ("D", 11400.0, "NORTH", "4C1 CU 3C1 2N1 2C1 CU CA 7C1 SP CU 5C1", 23, "D19", "AG19"),
    ("E", 13800.0, "SOUTH", "4C1 CU 5C1 N1 C1 CU CA 6C1 SP CU 5C1", 22, "D23", "AF23"),
    ("F", 16800.0, "NORTH", "4C1 CU 5C1 2-600 CU CA 2N1 5C1 SP -600 CU 4C1", 20, "D28", "AG28"),
]
BAY_W = {"C1": 600.0, "N1": 800.0, "CU": 600.0, "SP": 600.0, "-600": 600.0, "-800": 800.0}
# --- structural grid (A-101): A/B/C at X 8400/16800/25200, 1/2 at Y 8400/16800
GRID_X = {"A": 8400.0, "B": 16800.0, "C": 25200.0}
GRID_Y = {"1": 8400.0, "2": 16800.0}
# --- perimeter CRAH gallery (A-601 CRAH schedule, tiles B01 P01 AC01 AQ01) ---
PERIM_CRAHS = [("CRAH-01", "B01"), ("CRAH-02", "P01"), ("CRAH-03", "AC01"), ("CRAH-04", "AQ01")]
# --- PDUs (A-601 PDU schedule; A-101 note 8 front flush with row front;
#     E-101: PDU line 1800 east of each row end, "4238" to the east wall) -------
PDUS = [("PDU-01", "A", "AJ05"), ("PDU-02", "B", "AK10"), ("PDU-03", "C", "AJ14"),
        ("PDU-04", "D", "AK19"), ("PDU-05", "E", "AJ23"), ("PDU-06", "F", "AK28")]
PDU_GAP_FROM_ROW_END = 1800.0
PDU_WORKING_SPACE = 900.0          # E-101 note 8
PDU_DEDICATED = 1800.0             # E-101 note 7 (NFPA 70 110.26(E))
# --- cold-aisle containment (A-602 schedule, A-101 plan) ---------------------
CONTAINMENT = [("CAC-BC", "ROWS B / C", "B", "C"), ("CAC-DE", "ROWS D / E", "D", "E")]
ROOF_W, ROOF_T, ROOF_UNDERSIDE = 1400.0, 55.5, 2000.0
DOOR_T, DOOR_H = 60.0, 2055.5
# --- sprinklers (F-101, A-301) -----------------------------------------------
SPK_FIRST, SPK_PITCH, SPK_NX, SPK_NY = 1500.0, 3000.0, 9, 7   # 63 ceiling heads
SPK_RELOCATE = 75.0                # heads interrupted by a column nudged clear
INAISLE_DEFLECTOR = 1890.0         # A-301 detail 3 (110 below roof soffit)
INAISLE_PER_SEGMENT = 4            # 16 in-aisle heads = 2 aisles x 2 roofs x 4
INAISLE_END_OFFSET = 500.0
HEAD_R = 25.0                      # modelled head/deflector radius
# --- services (A-602 pathway schedule, E-101 / M-101 notes) ------------------
TRAY_W, TRAY_H = 683.0, 127.0      # CT-1 ladder tray 683 W x 127 H
BUS_W, BUS_H = 128.0, 147.0        # BW-1 busway 128 W x 147 H
PIPE_OD = 114.3                    # CHW-1 DN100 steel, bare OD
PIPE_INS = 25.4                    # insulation (counts in clashes)
PIPE_JACKET_OD = 168.3             # ASTM C585 jacket OD (M-101 note 4)
ENTRY = (0.0, 9900.0)              # M-101 / E-101 entry on the west wall

# =============================================================================
# 2. LAYOUT DERIVED FROM THE DATA
# =============================================================================
def col_letters(i):
    s, i = "", i + 1
    while i:
        i, r = divmod(i - 1, 26)
        s = chr(65 + r) + s
    return s


def col_index(letters):
    n = 0
    for ch in letters:
        n = n * 26 + (ord(ch) - 64)
    return n - 1


def tile_of(x, y):
    return "%s%02d" % (col_letters(int(x // TILE)), int(y // TILE) + 1)


def tile_origin(addr):
    m = re.match(r"([A-Z]+)(\d+)$", addr)
    return col_index(m.group(1)) * TILE, (int(m.group(2)) - 1) * TILE


racks, inrow_crahs, row_info = [], [], {}
for rid, yc, face, seq, qty, first, last in ROWS:
    x, bay_no, n_rack, n_cu = ROW_START_X, 0, 0, 0
    for term in seq.split():
        m = re.match(r"(\d*)(C1|N1|CU|SP|CA|-600|-800)$", term)
        cnt, kind = int(m.group(1) or 1), m.group(2)
        for _ in range(cnt):
            if kind == "CA":
                x = CROSS_AISLE_EAST
                continue
            w = BAY_W[kind]
            bay_no += 1
            if kind in CAB:
                n_rack += 1
                racks.append(dict(tag="RACK-%s%02d" % (rid, n_rack), row=rid, kind=kind,
                                  x0=x, x1=x + w, yc=yc, face=face, bay=bay_no))
            elif kind == "CU":
                n_cu += 1
                inrow_crahs.append(dict(tag="CRAH-%s%02d" % (rid, n_cu), row=rid,
                                        x0=x, x1=x + w, yc=yc, face=face, bay=bay_no))
            x += w
    row_racks = [r for r in racks if r["row"] == rid]
    row_info[rid] = dict(yc=yc, face=face, x0=ROW_START_X, x1=x, qty=qty,
                         first=first, last=last, n=len(row_racks))
    # self-consistency with the A-601 schedule (QTY, FIRST TILE, LAST TILE)
    assert len(row_racks) == qty, rid
    assert tile_of(row_racks[0]["x0"], yc - 600.0) == first, rid
    assert tile_of(row_racks[-1]["x0"], yc - 600.0) == last, rid


def front_y(rid):
    ri = row_info[rid]
    return ri["yc"] + (600.0 if ri["face"] == "NORTH" else -600.0)


# PDUs: front flush with the served row's front face, 1800 east of row end
pdus = []
for tag, rid, addr in PDUS:
    ri = row_info[rid]
    w, d, h = PDU_SIZE
    x0 = ri["x1"] + PDU_GAP_FROM_ROW_END
    if ri["face"] == "NORTH":
        y1 = front_y(rid)
        y0 = y1 - d
    else:
        y0 = front_y(rid)
        y1 = y0 + d
    assert tile_of(x0, y0) == addr, tag
    pdus.append(dict(tag=tag, row=rid, addr=addr, x0=x0, x1=x0 + w, y0=y0, y1=y1,
                     face=ri["face"]))

perim_crahs = []
for tag, addr in PERIM_CRAHS:
    x0, y0 = tile_origin(addr)
    w, d, h = PERIM_CRAH
    perim_crahs.append(dict(tag=tag, addr=addr, x0=x0, x1=x0 + w, y0=y0, y1=y0 + d,
                            face="NORTH"))

columns = []
for gy_name, gy in sorted(GRID_Y.items()):
    for gx_name, gx in sorted(GRID_X.items()):
        columns.append(dict(tag="COL-%s%s" % (gx_name, gy_name), gx=gx_name, gy=gy_name,
                            x=gx, y=gy))

# containment: roofs from the row start to the cross aisle (11400 - 1200) and
# from the cross aisle east edge to the longer row's end; doors outside each end
containment = []
for tag, contains, ra, rb in CONTAINMENT:
    ya, yb = sorted([front_y(ra), front_y(rb)])
    yc = 0.5 * (ya + yb)
    east = max(row_info[ra]["x1"], row_info[rb]["x1"])
    segs = [("W", ROW_START_X, CROSS_AISLE_EAST - CROSS_AISLE_CLEAR),
            ("E", CROSS_AISLE_EAST, east)]
    containment.append(dict(tag=tag, contains=contains, y0=yc - ROOF_W / 2.0,
                            y1=yc + ROOF_W / 2.0, yc=yc, aisle=(ya, yb), segs=segs))

# sprinkler heads
heads = []
col_boxes = [(c["x"] - COLUMN_SIZE / 2, c["x"] + COLUMN_SIZE / 2,
              c["y"] - COLUMN_SIZE / 2, c["y"] + COLUMN_SIZE / 2) for c in columns]
n = 0
for j in range(SPK_NY):
    for i in range(SPK_NX):
        x = SPK_FIRST + i * SPK_PITCH
        y = SPK_FIRST + j * SPK_PITCH
        nx, ny, reloc = x, y, False
        for (cx0, cx1, cy0, cy1) in col_boxes:
            if cx0 - HEAD_R <= x <= cx1 + HEAD_R and cy0 - HEAD_R <= y <= cy1 + HEAD_R:
                reloc = True
                # F-101 note 3: nudged clear of the column, not omitted
                if x - SPK_RELOCATE < cx0 - HEAD_R:      # move west clears it
                    nx = x - SPK_RELOCATE
                else:                                     # otherwise move south
                    ny = y - SPK_RELOCATE
        n += 1
        heads.append(dict(tag="SPK-C%02d" % n, kind="CEILING", x=nx, y=ny, z0=DEFLECTOR,
                          z1=SOFFIT, nominal=(x, y), relocated=reloc))
n = 0
for c in containment:
    for side, sx0, sx1 in c["segs"]:
        pitch = (sx1 - sx0 - 2 * INAISLE_END_OFFSET) / (INAISLE_PER_SEGMENT - 1)
        for k in range(INAISLE_PER_SEGMENT):
            n += 1
            heads.append(dict(tag="SPK-IA%02d" % n, kind="IN-AISLE",
                              x=sx0 + INAISLE_END_OFFSET + k * pitch, y=c["yc"],
                              z0=INAISLE_DEFLECTOR, z1=ROOF_UNDERSIDE, nominal=None,
                              relocated=False, aisle=c["tag"]))
assert len([h for h in heads if h["kind"] == "CEILING"]) == 63
assert len([h for h in heads if h["kind"] == "IN-AISLE"]) == 16

# =============================================================================
# 3. ROUTES
# =============================================================================
# Tier assignment (elevations relative to FF):
#  * BW-1 busway   : overhead, bottom +2750 / top +2897 (inside the 2600-3114.6
#                    overhead pathway zone; >= 460 below every deflector).
#  * CHW-1 pipe    : under-floor plenum, centreline -170 (jacket top -85.85,
#                    still >= 20 below the panel underside at -35).
#  * CT-1 tray     : under-floor plenum, top -300 / bottom -427.
# Tray and busway are therefore separated by > 3000 vertically everywhere, CHW
# never enters the dedicated space over a PDU, and no element crosses the
# access-floor panel.  Every service is a comb: a header run from the west-wall
# entry along the C/D hot aisle, a north-south spine at X 1800 (west end of the
# rows) and headers along the A/B and E/F aisles; CHW adds branches to the
# perimeter gallery CRAH-01..04.  Header lanes (Y): tray/busway 5000, 9900,
# 14800 (<= 2000 across from each row they serve); CHW 4000, 9900, 14800.
# Headers run to X 17100 / 17100 / 17350 so every row is covered > 80 % by
# extent, by cabinet width and by bay count; CHW passes within 2000 (plan) of
# every CRAH centre.  Runs are split at every junction (endpoint-to-endpoint).
BUS_Z0 = 2750.0
CHW_ZC = -170.0
TRAY_Z1 = -300.0

SPINE_X = ROW_START_X
END_AB, END_CD, END_EF = 17100.0, 17100.0, 17350.0   # >80 % of every row


def route(points):
    """points: list of (x, y) vertices of a straight-run polyline."""
    return list(zip(points[:-1], points[1:]))


SERVICES = {
    "CT-1": dict(
        name="CT-1 TELECOM CABLE TRAY", service="TELECOM", kind="TRAY", zone="PLENUM",
        zc=TRAY_Z1 - TRAY_H / 2.0, w=TRAY_W, h=TRAY_H,
        segs=(route([ENTRY, (SPINE_X, 9900.0)]) + route([(SPINE_X, 9900.0), (END_CD, 9900.0)]) +
              route([(SPINE_X, 9900.0), (SPINE_X, 5000.0)]) +
              route([(SPINE_X, 9900.0), (SPINE_X, 14800.0)]) +
              route([(SPINE_X, 5000.0), (END_AB, 5000.0)]) +
              route([(SPINE_X, 14800.0), (END_EF, 14800.0)]))),
    "BW-1": dict(
        name="BW-1 POWER BUSWAY", service="POWER", kind="BUSWAY", zone="OVERHEAD",
        zc=BUS_Z0 + BUS_H / 2.0, w=BUS_W, h=BUS_H,
        segs=(route([ENTRY, (SPINE_X, 9900.0)]) + route([(SPINE_X, 9900.0), (END_CD, 9900.0)]) +
              route([(SPINE_X, 9900.0), (SPINE_X, 5000.0)]) +
              route([(SPINE_X, 9900.0), (SPINE_X, 14800.0)]) +
              route([(SPINE_X, 5000.0), (END_AB, 5000.0)]) +
              route([(SPINE_X, 14800.0), (END_EF, 14800.0)]))),
    "CHW-1": dict(
        name="CHW-1 CHILLED WATER", service="CHILLED WATER", kind="PIPE", zone="PLENUM",
        zc=CHW_ZC, w=PIPE_OD, h=PIPE_OD,
        segs=(route([ENTRY, (SPINE_X, 9900.0)]) + route([(SPINE_X, 9900.0), (END_CD, 9900.0)]) +
              route([(SPINE_X, 9900.0), (SPINE_X, 4000.0)]) +
              route([(SPINE_X, 4000.0), (SPINE_X, 2358.0)]) +          # CRAH-01
              route([(SPINE_X, 9900.0), (SPINE_X, 14800.0)]) +
              route([(SPINE_X, 4000.0), (9600.0, 4000.0)]) +
              route([(9600.0, 4000.0), (END_AB, 4000.0)]) +
              route([(9600.0, 4000.0), (9600.0, 2450.0)]) +            # CRAH-02
              route([(END_AB, 4000.0), (END_AB, 1864.0)]) +            # CRAH-03
              route([(END_AB, 1864.0), (24386.0, 1864.0)]) +           # CRAH-04
              route([(SPINE_X, 14800.0), (END_EF, 14800.0)]))),
}

# =============================================================================
# 4. IFC HELPERS
# =============================================================================
f = ifcopenshell.file(schema="IFC4")
f.header.file_name.name = "model.ifc"
f.header.file_name.time_stamp = "2026-07-27T00:00:00"
f.header.file_name.author = ("MEP coordinator",)
f.header.file_name.organization = ("Meridian Digital Infrastructure",)
f.header.file_name.authorization = "A. OKONKWO, PE"
f.header.file_description.description = ("ViewDefinition [DesignTransferView_V1.0]",)


def gid(key):
    h = hashlib.md5(("dc_model/hall_seed000_d000/" + key).encode("utf-8")).hexdigest()
    return ifcopenshell.guid.compress(uuid.UUID(h).hex)


def pt3(p):
    return f.create_entity("IfcCartesianPoint", Coordinates=tuple(float(v) for v in p))


def pt2(p):
    return f.create_entity("IfcCartesianPoint", Coordinates=(float(p[0]), float(p[1])))


def dirn(v):
    return f.create_entity("IfcDirection", DirectionRatios=tuple(float(c) for c in v))


def axis3(loc, z=(0.0, 0.0, 1.0), x=(1.0, 0.0, 0.0)):
    return f.create_entity("IfcAxis2Placement3D", Location=pt3(loc), Axis=dirn(z),
                           RefDirection=dirn(x))


ORIGIN2 = f.create_entity("IfcAxis2Placement2D", Location=pt2((0.0, 0.0)))
_profiles = {}


def rect_profile(xd, yd):
    k = ("R", round(xd, 3), round(yd, 3))
    if k not in _profiles:
        _profiles[k] = f.create_entity("IfcRectangleProfileDef", ProfileType="AREA",
                                       Position=ORIGIN2, XDim=float(xd), YDim=float(yd))
    return _profiles[k]


def circle_profile(r):
    k = ("C", round(r, 3))
    if k not in _profiles:
        _profiles[k] = f.create_entity("IfcCircleProfileDef", ProfileType="AREA",
                                       Position=ORIGIN2, Radius=float(r))
    return _profiles[k]


def extrusion(profile, depth):
    return f.create_entity("IfcExtrudedAreaSolid", SweptArea=profile,
                           Position=axis3((0.0, 0.0, 0.0)),
                           ExtrudedDirection=dirn((0.0, 0.0, 1.0)), Depth=float(depth))


def sv(name, value):
    if isinstance(value, bool):
        nv = f.create_entity("IfcBoolean", value)
    elif isinstance(value, int):
        nv = f.create_entity("IfcInteger", value)
    elif isinstance(value, float):
        nv = f.create_entity("IfcReal", value)
    else:
        nv = f.create_entity("IfcLabel", str(value))
    return f.create_entity("IfcPropertySingleValue", Name=name, NominalValue=nv)


def add_pset(obj, pname, props):
    pset = f.create_entity("IfcPropertySet", GlobalId=gid(obj.GlobalId + "/" + pname),
                           Name=pname, HasProperties=[sv(k, v) for k, v in props.items()])
    f.create_entity("IfcRelDefinesByProperties", GlobalId=gid(obj.GlobalId + "/rel/" + pname),
                    RelatedObjects=[obj], RelatingPropertyDefinition=pset)
    return pset


# ---------------------------------------------------------------------------
# project, units, contexts, spatial structure
# ---------------------------------------------------------------------------
units = f.create_entity("IfcUnitAssignment", Units=[
    f.create_entity("IfcSIUnit", UnitType="LENGTHUNIT", Prefix="MILLI", Name="METRE"),
    f.create_entity("IfcSIUnit", UnitType="AREAUNIT", Name="SQUARE_METRE"),
    f.create_entity("IfcSIUnit", UnitType="VOLUMEUNIT", Name="CUBIC_METRE"),
    f.create_entity("IfcSIUnit", UnitType="PLANEANGLEUNIT", Name="RADIAN"),
    f.create_entity("IfcSIUnit", UnitType="MASSUNIT", Prefix="KILO", Name="GRAM"),
    f.create_entity("IfcSIUnit", UnitType="POWERUNIT", Name="WATT"),
])
model_ctx = f.create_entity("IfcGeometricRepresentationContext", ContextType="Model",
                            CoordinateSpaceDimension=3, Precision=1.0e-5,
                            WorldCoordinateSystem=axis3((0.0, 0.0, 0.0)),
                            TrueNorth=dirn((0.0, 1.0)))
body_ctx = f.create_entity("IfcGeometricRepresentationSubContext", ContextIdentifier="Body",
                           ContextType="Model", ParentContext=model_ctx,
                           TargetView="MODEL_VIEW")
axis_ctx = f.create_entity("IfcGeometricRepresentationSubContext", ContextIdentifier="Axis",
                           ContextType="Model", ParentContext=model_ctx,
                           TargetView="GRAPH_VIEW")
project = f.create_entity("IfcProject", GlobalId=gid("project"), Name="MDC-2026-014",
                          LongName="Meridian Data Center Phase 1 - Data Hall 1",
                          Description="Coordinated MEP model, dc_model hall_seed000_d000",
                          Phase="ISSUED FOR CONSTRUCTION",
                          RepresentationContexts=[model_ctx], UnitsInContext=units)
site_pl = f.create_entity("IfcLocalPlacement", RelativePlacement=axis3((0.0, 0.0, 0.0)))
site = f.create_entity("IfcSite", GlobalId=gid("site"), Name="Meridian Data Center Site",
                       ObjectPlacement=site_pl, CompositionType="ELEMENT")
bldg_pl = f.create_entity("IfcLocalPlacement", PlacementRelTo=site_pl,
                          RelativePlacement=axis3((0.0, 0.0, 0.0)))
building = f.create_entity("IfcBuilding", GlobalId=gid("building"),
                           Name="Meridian Data Center", LongName="MERIDIAN DATA CENTER PHASE 1",
                           ObjectPlacement=bldg_pl, CompositionType="ELEMENT")
storey_pl = f.create_entity("IfcLocalPlacement", PlacementRelTo=bldg_pl,
                            RelativePlacement=axis3((0.0, 0.0, 0.0)))
storey = f.create_entity("IfcBuildingStorey", GlobalId=gid("storey"), Name="Data Hall 1",
                         LongName="DATA HALL 1", ObjectPlacement=storey_pl,
                         CompositionType="ELEMENT", Elevation=0.0)
space_pl = f.create_entity("IfcLocalPlacement", PlacementRelTo=storey_pl,
                           RelativePlacement=axis3((0.0, 0.0, 0.0)))
space = f.create_entity("IfcSpace", GlobalId=gid("space"), Name="DATA HALL 1",
                        LongName="Data Hall 1 (27000 x 21000, FF to soffit 3600)",
                        ObjectPlacement=space_pl, CompositionType="ELEMENT",
                        PredefinedType="INTERNAL")
f.create_entity("IfcRelAggregates", GlobalId=gid("agg/project"), RelatingObject=project,
                RelatedObjects=[site])
f.create_entity("IfcRelAggregates", GlobalId=gid("agg/site"), RelatingObject=site,
                RelatedObjects=[building])
f.create_entity("IfcRelAggregates", GlobalId=gid("agg/building"), RelatingObject=building,
                RelatedObjects=[storey])
f.create_entity("IfcRelAggregates", GlobalId=gid("agg/storey"), RelatingObject=storey,
                RelatedObjects=[space])
add_pset(space, "Pset_DCM_Hall", {
    "Tag": "DATA HALL 1", "RoomLength": ROOM_X, "RoomWidth": ROOM_Y,
    "FinishedFloorElevation": FFL, "StructuralSlabElevation": SLAB_TOP,
    "SoffitElevation": SOFFIT, "MinimumClearHeight": CLEAR_MIN,
    "SprinklerDeflectorElevation": DEFLECTOR, "SprinklerStandoff": STANDOFF,
    "OverheadZoneBottom": CLEAR_MIN, "OverheadZoneTop": STANDOFF_PLANE,
    "PlenumZoneBottom": SLAB_TOP, "PlenumZoneTop": -PANEL_T - UNDER_PANEL_CLEAR,
    "TileSize": TILE, "GridOrigin": "SOUTH-WEST INTERNAL CORNER"})

contained = []


def make_element(ifc_class, key, name, placement, items, rep_type="SweptSolid",
                 axis_items=None, **attrs):
    reps = [f.create_entity("IfcShapeRepresentation", ContextOfItems=body_ctx,
                            RepresentationIdentifier="Body", RepresentationType=rep_type,
                            Items=items)]
    if axis_items:
        reps.append(f.create_entity("IfcShapeRepresentation", ContextOfItems=axis_ctx,
                                    RepresentationIdentifier="Axis",
                                    RepresentationType="Curve3D", Items=axis_items))
    shape = f.create_entity("IfcProductDefinitionShape", Representations=reps)
    el = f.create_entity(ifc_class, GlobalId=gid(key), Name=name, ObjectPlacement=placement,
                         Representation=shape, **attrs)
    contained.append(el)
    return el


def local_pl(loc, z=(0.0, 0.0, 1.0), x=(1.0, 0.0, 0.0)):
    return f.create_entity("IfcLocalPlacement", PlacementRelTo=storey_pl,
                           RelativePlacement=axis3(loc, z, x))


FACING_REFDIR = {"NORTH": (1.0, 0.0, 0.0), "SOUTH": (-1.0, 0.0, 0.0),
                 "EAST": (0.0, -1.0, 0.0), "WEST": (0.0, 1.0, 0.0)}
FACING_DEG = {"NORTH": 0.0, "SOUTH": 180.0, "EAST": -90.0, "WEST": 90.0}


def oriented_box(ifc_class, key, name, x0, x1, y0, y1, z0, height, facing, **attrs):
    """Box on footprint [x0,x1]x[y0,y1]; placement origin at the footprint
    centre, rotated about it so that local +Y is the front (facing) direction."""
    cx, cy = 0.5 * (x0 + x1), 0.5 * (y0 + y1)
    wx, wy = x1 - x0, y1 - y0
    if facing in ("NORTH", "SOUTH"):
        prof = rect_profile(wx, wy)
    else:
        prof = rect_profile(wy, wx)
    pl = local_pl((cx, cy, z0), (0.0, 0.0, 1.0), FACING_REFDIR[facing])
    return make_element(ifc_class, key, name, pl, [extrusion(prof, height)], **attrs)


# =============================================================================
# 5. BACKGROUND
# =============================================================================
# access floor: 35 panel following the room outline, top at FF
af = make_element("IfcSlab", "accessfloor", "ACCESS FLOOR",
                  local_pl((ROOM_X / 2.0, ROOM_Y / 2.0, FFL - PANEL_T)),
                  [extrusion(rect_profile(ROOM_X, ROOM_Y), PANEL_T)],
                  ObjectType="AccessFloor", Tag="AF-1", PredefinedType="FLOOR",
                  Description="35 mm access floor panel, top at +0, 600 grid")
add_pset(af, "Pset_DCM_AccessFloor", {
    "Tag": "AF-1", "PanelThickness": PANEL_T, "TopElevation": FFL,
    "BottomElevation": FFL - PANEL_T, "TileSize": TILE, "PlenumDepth": 865.0,
    "StructuralSlabElevation": SLAB_TOP, "UnderPanelClearance": UNDER_PANEL_CLEAR})
add_pset(af, "Pset_SlabCommon", {"IsExternal": False, "LoadBearing": False})

# racks
for r in racks:
    w, d, h, desc = CAB[r["kind"]]
    y0, y1 = r["yc"] - d / 2.0, r["yc"] + d / 2.0
    el = oriented_box("IfcFurniture", "rack/" + r["tag"], r["tag"], r["x0"], r["x1"], y0, y1,
                      FFL, h, r["face"], ObjectType="Rack", Tag=r["tag"],
                      PredefinedType="USERDEFINED", Description=desc)
    add_pset(el, "Pset_DCM_Rack", {
        "Tag": r["tag"], "Row": r["row"], "BayIndex": r["bay"], "Position": r["bay"],
        "CabinetType": r["kind"], "Type": r["kind"],
        "Width": w, "Depth": d, "Height": h, "RackUnits": CAB_RU,
        "FrontFaces": r["face"], "Facing": r["face"], "RotationDeg": FACING_DEG[r["face"]],
        "TileAddress": tile_of(r["x0"], y0), "Tile": tile_of(r["x0"], y0),
        "kWPerCabinet": CAB_KW, "LoadKg": CAB_KG,
        "RowCentrelineY": r["yc"], "FootprintCentreX": 0.5 * (r["x0"] + r["x1"]),
        "FootprintCentreY": r["yc"], "Heavy800Distributor": r["kind"] == "N1"})

# in-row CRAH units
for c in inrow_crahs:
    w, d, h = INROW_CRAH
    y0, y1 = c["yc"] - d / 2.0, c["yc"] + d / 2.0
    el = oriented_box("IfcUnitaryEquipment", "crah/" + c["tag"], c["tag"], c["x0"], c["x1"],
                      y0, y1, FFL, h, c["face"], ObjectType="CRAH", Tag=c["tag"],
                      PredefinedType="USERDEFINED",
                      Description="IN-ROW CRAH, 50 kW, CHILLED WATER DN50")
    add_pset(el, "Pset_DCM_CRAH", {
        "Tag": c["tag"], "Placement": "IN ROW", "Row": c["row"], "BayIndex": c["bay"],
        "Width": w, "Depth": d, "Height": h, "CapacityKW": 50.0, "AirflowM3h": 9000.0,
        "FrontFaces": c["face"], "Facing": c["face"], "RotationDeg": FACING_DEG[c["face"]],
        "TileAddress": tile_of(c["x0"], y0), "Tile": tile_of(c["x0"], y0),
        "Service": "CHILLED WATER, DN50",
        "ServiceClearance": 914.0})

# perimeter gallery CRAHs
for c in perim_crahs:
    w, d, h = PERIM_CRAH
    el = oriented_box("IfcUnitaryEquipment", "crah/" + c["tag"], c["tag"], c["x0"], c["x1"],
                      c["y0"], c["y1"], FFL, h, c["face"], ObjectType="CRAH", Tag=c["tag"],
                      PredefinedType="USERDEFINED",
                      Description="PERIMETER CRAH, 100 kW, CHILLED WATER DN100")
    add_pset(el, "Pset_DCM_CRAH", {
        "Tag": c["tag"], "Placement": "PERIMETER", "Row": "-", "Width": w, "Depth": d,
        "Height": h, "CapacityKW": 100.0, "AirflowM3h": 20000.0, "FrontFaces": c["face"],
        "Facing": c["face"], "RotationDeg": FACING_DEG[c["face"]], "TileAddress": c["addr"],
        "Tile": c["addr"],
        "Service": "CHILLED WATER, DN100"})

# PDUs
for p in pdus:
    w, d, h = PDU_SIZE
    el = oriented_box("IfcElectricDistributionBoard", "pdu/" + p["tag"], p["tag"], p["x0"],
                      p["x1"], p["y0"], p["y1"], FFL, h, p["face"], ObjectType="PDU",
                      Tag=p["tag"], PredefinedType="USERDEFINED",
                      Description="POWER DISTRIBUTION UNIT 225 kVA, SERVES ROW " + p["row"])
    add_pset(el, "Pset_DCM_PDU", {
        "Tag": p["tag"], "ServesRow": p["row"], "Row": p["row"], "TileAddress": p["addr"],
        "Tile": p["addr"], "Width": w, "Depth": d, "Height": h, "RatingKVA": 225.0,
        "FrontFaces": p["face"], "Facing": p["face"],
        "RotationDeg": FACING_DEG[p["face"]], "WorkingSpaceDepth": PDU_WORKING_SPACE,
        "DedicatedSpaceHeight": PDU_DEDICATED,
        "DedicatedSpaceTop": h + PDU_DEDICATED, "FedFrom": "BW-1"})

# structural columns: 600 sq, FF to soffit, hard obstructions
for c in columns:
    s = COLUMN_SIZE
    el = make_element("IfcColumn", "column/" + c["tag"], c["tag"], local_pl((c["x"], c["y"], FFL)),
                      [extrusion(rect_profile(s, s), COLUMN_TOP - FFL)], ObjectType="Column",
                      Tag=c["tag"], PredefinedType="COLUMN",
                      Description="STRUCTURAL COLUMN GRID %s/%s" % (c["gx"], c["gy"]))
    add_pset(el, "Pset_DCM_Column", {
        "Tag": c["tag"], "GridX": c["gx"], "GridY": c["gy"], "Width": s, "Depth": s,
        "BaseElevation": FFL, "TopElevation": COLUMN_TOP, "HardObstruction": True,
        "SprinklerKeepOut": 1500.0})
    add_pset(el, "Pset_ColumnCommon", {"LoadBearing": True, "IsExternal": False})

# cold-aisle containment: 2 roof panels + 4 end doors per aisle
for c in containment:
    for side, sx0, sx1 in c["segs"]:
        nm = "%s ROOF %s" % (c["tag"], side)
        el = make_element("IfcBuildingElementProxy", "cac/%s/roof/%s" % (c["tag"], side), nm,
                          local_pl((0.5 * (sx0 + sx1), c["yc"], ROOF_UNDERSIDE)),
                          [extrusion(rect_profile(sx1 - sx0, ROOF_W), ROOF_T)],
                          ObjectType="ContainmentRoof", Tag=nm, PredefinedType="USERDEFINED",
                          Description="COLD-AISLE CONTAINMENT ROOF, " + c["contains"])
        add_pset(el, "Pset_DCM_Containment", {
            "Tag": c["tag"], "Contains": c["contains"], "Component": "ROOF PANEL",
            "Segment": side, "RoofWidth": ROOF_W, "RoofThickness": ROOF_T,
            "RoofUndersideElevation": ROOF_UNDERSIDE, "StartX": sx0, "EndX": sx1,
            "AisleWidth": c["aisle"][1] - c["aisle"][0], "HeadsBeneath": True})
    door_x = []
    for side, sx0, sx1 in c["segs"]:
        door_x += [(side + "-W", sx0 - DOOR_T, sx0), (side + "-E", sx1, sx1 + DOOR_T)]
    for dname, dx0, dx1 in door_x:
        nm = "%s DOOR %s" % (c["tag"], dname)
        el = make_element("IfcDoor", "cac/%s/door/%s" % (c["tag"], dname), nm,
                          local_pl((0.5 * (dx0 + dx1), c["yc"], FFL)),
                          [extrusion(rect_profile(DOOR_T, ROOF_W), DOOR_H)],
                          ObjectType="ContainmentDoor", Tag=nm, OverallHeight=DOOR_H,
                          OverallWidth=ROOF_W, PredefinedType="DOOR",
                          OperationType="SLIDING_TO_LEFT",
                          Description="CONTAINMENT END DOOR 60 x 2055.5, " + c["contains"])
        add_pset(el, "Pset_DCM_Containment", {
            "Tag": c["tag"], "Contains": c["contains"], "Component": "END DOOR",
            "Segment": dname, "DoorThickness": DOOR_T, "DoorHeight": DOOR_H,
            "DoorWidth": ROOF_W})

# sprinkler heads (pendent at the soffit; in-aisle hanging from the roof soffit)
for hd in heads:
    el = make_element("IfcFireSuppressionTerminal", "spk/" + hd["tag"], hd["tag"],
                      local_pl((hd["x"], hd["y"], hd["z0"])),
                      [extrusion(circle_profile(HEAD_R), hd["z1"] - hd["z0"])],
                      ObjectType="Sprinkler", Tag=hd["tag"], PredefinedType="SPRINKLER",
                      Description=("PENDENT CEILING HEAD" if hd["kind"] == "CEILING"
                                   else "IN-AISLE HEAD UNDER CONTAINMENT ROOF"))
    props = {"Tag": hd["tag"], "HeadType": hd["kind"], "DeflectorElevation": hd["z0"],
             "StandoffBelowDeflector": STANDOFF, "KeepClearBottom": hd["z0"] - STANDOFF,
             "Relocated": hd["relocated"], "X": hd["x"], "Y": hd["y"]}
    if hd["nominal"]:
        props["NominalX"], props["NominalY"] = hd["nominal"]
    if hd["kind"] == "IN-AISLE":
        props["Containment"] = hd["aisle"]
    add_pset(el, "Pset_DCM_Sprinkler", props)

# =============================================================================
# 6. SERVICE ROUTES
# =============================================================================
SYS_TYPE = {"CT-1": "DATA", "BW-1": "ELECTRICAL", "CHW-1": "CHILLEDWATER"}
route_elems = {}
for skey, s in SERVICES.items():
    elems = []
    for i, (p0, p1) in enumerate(s["segs"], start=1):
        x0, y0 = p0
        x1, y1 = p1
        dx, dy = x1 - x0, y1 - y0
        L = abs(dx) + abs(dy)
        assert (dx == 0.0) != (dy == 0.0) and L > 0.0, (skey, i)
        d = (1.0 if dx > 0 else -1.0 if dx < 0 else 0.0,
             1.0 if dy > 0 else -1.0 if dy < 0 else 0.0, 0.0)
        xdir = (-d[1], d[0], 0.0)          # horizontal, perpendicular; local Y = up
        start = (x0, y0, s["zc"])
        pl = local_pl(start, d, xdir)
        if s["kind"] == "PIPE":
            prof = circle_profile(PIPE_OD / 2.0)
        else:
            prof = rect_profile(s["w"], s["h"])
        axis_poly = f.create_entity("IfcPolyline", Points=[pt3((0.0, 0.0, 0.0)),
                                                           pt3((0.0, 0.0, L))])
        name = "%s SEG %02d" % (skey, i)
        common = dict(Tag=name, Description="%s, %s, %s" % (s["name"], s["zone"],
                                                            "X RUN" if dx else "Y RUN"))
        if s["kind"] == "TRAY":
            el = make_element("IfcCableCarrierSegment", "route/" + name, name, pl,
                              [extrusion(prof, L)], axis_items=[axis_poly],
                              ObjectType="CableTray", PredefinedType="CABLETRAYSEGMENT",
                              **common)
        elif s["kind"] == "BUSWAY":
            el = make_element("IfcCableSegment", "route/" + name, name, pl,
                              [extrusion(prof, L)], axis_items=[axis_poly],
                              ObjectType="Busway", PredefinedType="BUSBARSEGMENT", **common)
        else:
            el = make_element("IfcPipeSegment", "route/" + name, name, pl,
                              [extrusion(prof, L)], axis_items=[axis_poly],
                              ObjectType="ChilledWaterPipe", PredefinedType="RIGIDSEGMENT",
                              **common)
        zc = s["zc"]
        half = s["h"] / 2.0
        props = {
            "Service": s["service"], "ServiceTag": skey, "ServiceType": s["kind"],
            "System": skey, "SystemName": s["name"], "SegmentIndex": i, "Zone": s["zone"],
            "Tier": "OVERHEAD +%d" % round(zc) if s["zone"] == "OVERHEAD" else
                    "PLENUM %d" % round(zc),
            "Elevation": zc, "ElevationCentre": zc, "ElevationBottom": zc - half,
            "ElevationTop": zc + half,
            "ElevationReference": "FINISHED FLOOR +0",
            "StartX": x0, "StartY": y0, "StartZ": zc, "EndX": x1, "EndY": y1, "EndZ": zc,
            "Length": L, "Axis": "X" if dx else "Y", "Width": s["w"], "Height": s["h"]}
        if s["kind"] == "PIPE":
            props.update({"NominalDiameter": "DN100", "OuterDiameter": PIPE_OD,
                          "InsulationThickness": PIPE_INS,
                          "InsulatedOuterDiameter": PIPE_OD + 2 * PIPE_INS,
                          "JacketOuterDiameter": PIPE_JACKET_OD,
                          "ElevationTopOfJacket": zc + PIPE_JACKET_OD / 2.0,
                          "ElevationBottomOfJacket": zc - PIPE_JACKET_OD / 2.0})
        if s["kind"] == "TRAY":
            props.update({"TrayType": "CABLE TRAY, LADDER", "NominalWidth": 610.0,
                          "SeparationFromPower": 300.0})
        if s["kind"] == "BUSWAY":
            props.update({"MaxSupportSpacing": 1500.0})
        add_pset(el, "Pset_DCM_Route", props)
        elems.append(el)
    route_elems[skey] = elems
    system = f.create_entity("IfcDistributionSystem", GlobalId=gid("system/" + skey),
                             Name=s["name"], LongName=skey, ObjectType=s["service"],
                             PredefinedType=SYS_TYPE[skey])
    add_pset(system, "Pset_DCM_Service", {
        "ServiceTag": skey, "Service": s["service"], "Zone": s["zone"],
        "EntryX": ENTRY[0], "EntryY": ENTRY[1], "SegmentCount": len(elems),
        "TotalLength": float(sum(abs(b[0] - a[0]) + abs(b[1] - a[1]) for a, b in s["segs"]))})
    f.create_entity("IfcRelAssignsToGroup", GlobalId=gid("assign/" + skey),
                    RelatedObjects=elems, RelatingGroup=system)
    f.create_entity("IfcRelServicesBuildings", GlobalId=gid("serves/" + skey),
                    RelatingSystem=system, RelatedBuildings=[building])

f.create_entity("IfcRelContainedInSpatialStructure", GlobalId=gid("contain/storey"),
                RelatingStructure=storey, RelatedElements=contained)

# =============================================================================
# 7. DRAWING-NOTE RECONCILIATION LOG (side file, optional)
# =============================================================================
RECON = [
    ("A-101", "Room 27000 x 21000, 600 tile grid, origin SW internal corner",
     "Hall frame and tile addresses (col letters A..Z,AA.., rows 1.. north)"),
    ("A-101", "Row centrelines 3000/6000/8400/11400/13800/16800 (dims 3000,3000,2400,3000,2400,3000,4200)",
     "Cabinet footprints = centreline +/- 600 (depth 1200 per A-601)"),
    ("A-101 n.5", "Cross aisle east edge common to every row (11400); 1200 CLEAR",
     "Bays after CA restart at 11400; containment breaks at 10200 / 11400"),
    ("A-101 n.6 / A-601", "Bay sequences accumulated from tile D (1800); C1 600, N1 800, CU 600, SP 600, -600 omitted",
     "128 racks, 18 in-row CRAHs; QTY/first/last tile cross-checked"),
    ("A-101 n.8 / E-101", "PDU front flush with row front; PDU line 1800 east of row end; 4238 to east wall",
     "PDU-01..06 placed and checked against tiles AJ05..AK28"),
    ("A-101", "Structural grid 8400 x 8400: columns at X 8400/16800/25200, Y 8400/16800, 600 sq",
     "6 IfcColumn FF to soffit; all routes keep clear of their footprints at every elevation"),
    ("A-301 / A-602", "FF +0, slab -900, panel 35, soffit +3600, min clear 2600, standoff 460, deflector +3574.6",
     "Overhead pathway zone +2600..+3114.6 (515); plenum -900..-55"),
    ("A-301 n.3", "Under-floor tray top >= 20 below panel underside (-35)",
     "CT-1 top at -300; CHW-1 jacket top -85.85"),
    ("A-602", "Containment roof 1400 W x 55.5 THK, underside +2000; 2 roof panels + 4 doors 60 x 2055.5 per aisle",
     "CAC-BC / CAC-DE roofs [1800,10200] and [11400,19800]; doors outside each end"),
    ("A-602", "CT-1 683 x 127, BW-1 128 x 147, CHW-1 OD 114.3 insulate 25 min; zone OVERHEAD OR PLENUM",
     "Section sizes used for every segment"),
    ("E-101 n.4", "Busway support 1500 max", "Supports not modelled (optional); recorded in Pset"),
    ("E-101 n.6", "300 clear tray-to-busway on at least one axis",
     "Tray in plenum (top -300), busway overhead (bottom +2750): 3050 vertical everywhere"),
    ("E-101 n.7 / M-101 n.5", "1800 dedicated space above each PDU, no piping",
     "CHW-1 runs entirely in the plenum"),
    ("M-101 n.3", "CHW to every CRAH incl. perimeter gallery; header along every row",
     "Row headers at Y 4000/9900/14800 plus branches to CRAH-01..04 (<= 2000 plan)"),
    ("M-101 n.4", "Jacket OD 168.3 over insulation for clash",
     "Clearances designed for OD 168.3 + 25.4 margin"),
    ("F-101", "63 ceiling heads on 3000 grid from 1500; heads at columns nudged clear (2 heads, 75 mm)",
     "63 pendent heads at +3574.6; SPK at B/2 and C/2 relocated"),
    ("F-101 n.8 / A-301 d.3", "In-aisle heads beneath containment roofs, deflector +1890",
     "16 in-aisle heads, 4 per roof panel"),
    ("M-101 / E-101", "Service entries on west wall at Y 9900",
     "All three services start at (0, 9900)"),
]
try:
    with open(os.path.join(os.path.dirname(os.path.abspath(OUT_PATH)), "reconciliation.json"),
              "w") as fh:
        json.dump({"model": "hall_seed000_d000",
                   "notes": [{"sheet": a, "note": b, "applied": c} for a, b, c in RECON],
                   "service_lengths_mm": {
                       k: float(sum(abs(b[0] - a[0]) + abs(b[1] - a[1]) for a, b in v["segs"]))
                       for k, v in SERVICES.items()}}, fh, indent=1)
except Exception:
    pass

# =============================================================================
# 8. WRITE (last action)
# =============================================================================
f.write(OUT_PATH)
