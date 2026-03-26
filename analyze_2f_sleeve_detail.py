#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Deep-dive analysis of sleeve blocks and [衛生]スリーブ layer in 2F DXF.
"""

import ezdxf
from collections import defaultdict
import re

DXF_PATH = r"C:/Users/2530r/Documents/aice/Takenakaver4/dxf_output/2階床スリーブ図.dxf"

doc = ezdxf.readfile(DXF_PATH)
msp = doc.modelspace()

print("=" * 70)
print("DEEP DIVE: SLEEVE BLOCKS INTERNAL CONTENT")
print("=" * 70)

# Examine internal content of typical sleeve block
sleeve_block_names = []
for block in doc.blocks:
    name = block.name
    if 'スリーブ' in name or 'sleeve' in name.lower():
        sleeve_block_names.append(name)

print(f"\nTotal sleeve-type blocks: {len(sleeve_block_names)}")

# Look at first few sleeve blocks in detail
print("\nFirst 5 sleeve block details (スリーブ(S)-Z... pattern):")
sanit_sleeve_blocks = [n for n in sleeve_block_names if n.startswith('\u885b') or 'S\u0029' in n or '\u0028S\u0029' in n]

# Just look at the first 5 blocks starting with スリーブ
sample_blocks = [n for n in sleeve_block_names if not n.startswith('INS-')][:5]

for bname in sample_blocks:
    block = doc.blocks.get(bname)
    if block is None:
        continue
    print(f"\n  Block: {repr(bname)}")
    for ent in block:
        etype = ent.dxftype()
        if etype == 'CIRCLE':
            print(f"    CIRCLE: center={ent.dxf.center}, radius={round(ent.dxf.radius, 3)}, diameter={round(ent.dxf.radius*2,3)}")
        elif etype == 'LINE':
            print(f"    LINE: {ent.dxf.start} -> {ent.dxf.end}")
        elif etype == 'TEXT':
            print(f"    TEXT: {repr(ent.dxf.text)}, pos={ent.dxf.insert}")
        elif etype == 'LWPOLYLINE':
            pts = list(ent.get_points())
            print(f"    LWPOLYLINE: {len(pts)} pts, first: {pts[:2]}")

# Look at the INS-G86SL block (160 entities, likely the big sleeve symbol)
print("\n\nINS-G86SL block (160 entities):")
g86sl = doc.blocks.get('INS-G86SL')
if g86sl:
    circles = []
    for ent in g86sl:
        if ent.dxftype() == 'CIRCLE':
            circles.append(round(ent.dxf.radius, 3))
    circle_radii = sorted(set(circles))
    print(f"  Circle radii: {circle_radii}")
    print(f"  Circle diameters: {[r*2 for r in circle_radii]}")

# Look at INS-G5YSL (14 entities with TEXT)
print("\n\nINS-G5YSL block (14 entities, has TEXT):")
g5ysl = doc.blocks.get('INS-G5YSL')
if g5ysl:
    for ent in g5ysl:
        etype = ent.dxftype()
        if etype == 'CIRCLE':
            print(f"  CIRCLE: radius={ent.dxf.radius}, diameter={ent.dxf.radius*2}")
        elif etype == 'TEXT':
            print(f"  TEXT: {repr(ent.dxf.text)}, pos={ent.dxf.insert}")
        elif etype == 'ARC':
            print(f"  ARC: center={ent.dxf.center}, radius={ent.dxf.radius}")
        elif etype == 'LINE':
            print(f"  LINE: {ent.dxf.start} -> {ent.dxf.end}")

print("\n" + "=" * 70)
print("[衛生]スリーブ LAYER: ALL INSERT INSTANCES WITH NEARBY TEXTS")
print("=" * 70)

# Get all inserts on [衛生]スリーブ
sanit_sleeve_inserts = []
for ent in msp:
    if ent.dxftype() == 'INSERT':
        layer = ent.dxf.layer
        if 'スリーブ' in layer and ('衛生' in layer or '\u885b\u751f' in layer):
            pos = (ent.dxf.insert.x, ent.dxf.insert.y)
            sanit_sleeve_inserts.append({
                'block': ent.dxf.name,
                'pos': pos,
                'layer': layer,
                'scale': (getattr(ent.dxf, 'xscale', 1), getattr(ent.dxf, 'yscale', 1))
            })

print(f"\n[衛生]スリーブ INSERT count: {len(sanit_sleeve_inserts)}")
for ins in sanit_sleeve_inserts[:10]:
    print(f"  Block: {repr(ins['block'])}, Pos: ({round(ins['pos'][0],1)}, {round(ins['pos'][1],1)}), Scale: {ins['scale']}")

print("\n" + "=" * 70)
print("[衛生]スリーブ LAYER TEXT CONTENT FULL")
print("=" * 70)

# Get all texts on [衛生]スリーブ layer
sanit_texts = []
for ent in msp:
    if ent.dxftype() in ('TEXT', 'MTEXT'):
        layer = ent.dxf.layer
        if 'スリーブ' in layer and ('衛生' in layer or '\u885b\u751f' in layer):
            if ent.dxftype() == 'TEXT':
                txt = ent.dxf.text
            else:
                txt = ent.plain_mtext()
            pos = (round(ent.dxf.insert.x, 1), round(ent.dxf.insert.y, 1))
            sanit_texts.append({'text': txt, 'pos': pos, 'layer': layer})

print(f"\n[衛生]スリーブ TEXT count: {len(sanit_texts)}")
for t in sanit_texts:
    print(f"  {repr(t['text'])}, Pos: {t['pos']}")

print("\n" + "=" * 70)
print("[衛生]スリーブ NUMBER LAYER FULL CONTENT")
print("=" * 70)

# [衛生]スリーブ番号(SG) layer
for ent in msp:
    if ent.dxftype() == 'TEXT':
        layer = ent.dxf.layer
        if 'スリーブ番号' in layer or 'SG' in layer:
            pos = (round(ent.dxf.insert.x, 1), round(ent.dxf.insert.y, 1))
            print(f"  [{layer}] {repr(ent.dxf.text)}, Pos: {pos}")

print("\n" + "=" * 70)
print("[衛生] スリーブ: FULL P-N-x SLEEVE NUMBER TEXTS")
print("=" * 70)

# Find all P-N-x style sleeve numbers
pn_pattern = re.compile(r'P-[A-Z]?-?\d+|P-\w+-\d+')
pn_texts = []
for ent in msp:
    if ent.dxftype() == 'TEXT':
        txt = ent.dxf.text
        if pn_pattern.search(txt or ''):
            layer = ent.dxf.layer
            pos = (round(ent.dxf.insert.x, 1), round(ent.dxf.insert.y, 1))
            pn_texts.append({'text': txt, 'layer': layer, 'pos': pos})

print(f"\nP-N-x sleeve number texts: {len(pn_texts)}")
for t in pn_texts[:20]:
    print(f"  [{t['layer']}] {repr(t['text'])}, Pos: {t['pos']}")

print("\n" + "=" * 70)
print("SLEEVE INSERTS IN [衛生] LAYER: BLOCK INTERNAL ANALYSIS")
print("=" * 70)

# Get the full [衛生]スリーブ layer inserts and their block contents
print("\nAnalyzing スリーブ(S)-Z... blocks for circle sizes:")
sizes_found = {}
for bname in sleeve_block_names:
    if not bname.startswith('INS-'):
        block = doc.blocks.get(bname)
        if block is None:
            continue
        for ent in block:
            if ent.dxftype() == 'CIRCLE':
                r = round(ent.dxf.radius, 2)
                d = round(r * 2, 2)
                if bname not in sizes_found:
                    sizes_found[bname] = []
                sizes_found[bname].append(d)

# Count unique sizes
all_diameters = []
for bname, diams in sizes_found.items():
    all_diameters.extend(diams)

from collections import Counter
diam_counts = Counter(all_diameters)
print("\nCircle diameters found in sleeve blocks (diameter: count of blocks using it):")
for d, cnt in sorted(diam_counts.items()):
    print(f"  {d}mm: {cnt} block instances")

print("\n" + "=" * 70)
print("FULL [衛生]スリーブ INSERT POSITIONS (all 113 inserts)")
print("=" * 70)

# All [衛生]スリーブ inserts in modelspace
all_sanit_sleeve = []
for ent in msp:
    if ent.dxftype() == 'INSERT':
        layer = ent.dxf.layer
        if 'スリーブ' in layer:
            block_name = ent.dxf.name
            pos = (round(ent.dxf.insert.x, 2), round(ent.dxf.insert.y, 2))
            # Get block content for size
            block = doc.blocks.get(block_name)
            circle_radii = []
            block_texts = []
            if block:
                for bent in block:
                    if bent.dxftype() == 'CIRCLE':
                        circle_radii.append(round(bent.dxf.radius, 2))
                    elif bent.dxftype() == 'TEXT':
                        block_texts.append(bent.dxf.text)

            all_sanit_sleeve.append({
                'layer': layer,
                'block': block_name,
                'pos': pos,
                'circle_radii': sorted(set(circle_radii)),
                'block_texts': block_texts
            })

print(f"\nTotal スリーブ INSERT entities: {len(all_sanit_sleeve)}")

# Group by layer
by_layer = defaultdict(list)
for ins in all_sanit_sleeve:
    by_layer[ins['layer']].append(ins)

for layer, inserts in sorted(by_layer.items()):
    print(f"\n  Layer: {layer} ({len(inserts)} inserts)")
    for ins in inserts[:5]:
        radii_str = str([r*2 for r in ins['circle_radii']]) if ins['circle_radii'] else 'no circles'
        texts_str = str(ins['block_texts'][:3]) if ins['block_texts'] else 'no texts'
        print(f"    Pos: {ins['pos']}, Diameters: {radii_str}, BlockTexts: {texts_str}")
    if len(inserts) > 5:
        print(f"    ... and {len(inserts)-5} more")

print("\n" + "=" * 70)
print("4. DIMENSION ENTITIES SAMPLE")
print("=" * 70)

dim_count = 0
for ent in msp:
    if ent.dxftype() == 'DIMENSION':
        layer = ent.dxf.layer
        try:
            meas = ent.dxf.actual_measurement
        except:
            meas = None
        try:
            text = ent.dxf.text
        except:
            text = ''
        try:
            defpt = ent.dxf.defpoint
            defpt2 = ent.dxf.defpoint2
        except:
            defpt = defpt2 = None

        if dim_count < 20:
            meas_str = f", meas={round(meas,1)}" if meas else ""
            pt_str = f", pts: {(round(defpt.x,0),round(defpt.y,0))} to {(round(defpt2.x,0),round(defpt2.y,0))}" if defpt and defpt2 else ""
            print(f"  [{layer}] text={repr(text)}{meas_str}{pt_str}")
        dim_count += 1

print(f"\nTotal DIMENSION entities: {dim_count}")

print("\n" + "=" * 70)
print("SUMMARY STATS")
print("=" * 70)

print(f"\nTotal sleeve blocks (unique definitions): {len(sleeve_block_names)}")
print(f"  - INS-G8MSL (1 entity LWPOLYLINE): 1")
print(f"  - INS-G5YSL (14 entities, has CIRCLE+TEXT): 1")
print(f"  - INS-G86SL (160 entities, CIRCLE+LINE set): 1")
print(f"  - スリーブ(S)-Z... (dynamic, CIRCLE+LINE): {len([n for n in sleeve_block_names if not n.startswith('INS-')])}")

print(f"\nCoordinate ranges:")
print(f"  Main drawing area: X 0-80000, Y 0-35000 (mm)")
print(f"  Detail area: X -50000 to -35000, Y 107000-122000 (mm)")
print(f"  (Two separate drawing areas in one file)")
