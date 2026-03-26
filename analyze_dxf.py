#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
DXF Analysis Script for 1F Floor Sleeve Drawing
"""

import ezdxf
from ezdxf import recover
from collections import defaultdict
import re
import sys

DXF_PATH = "C:/Users/2530r/Documents/aice/Takenakaver4/dxf_output/1階床スリーブ図.dxf"

print("=" * 80)
print("DXF ANALYSIS REPORT: 1階床スリーブ図.dxf")
print("=" * 80)

# Load the DXF file
try:
    doc, auditor = recover.readfile(DXF_PATH)
    print(f"\n[File loaded successfully]")
    print(f"DXF Version: {doc.dxfversion}")
    if auditor.has_errors:
        print(f"Audit errors: {len(auditor.errors)}")
except Exception as e:
    print(f"Error loading file: {e}")
    sys.exit(1)

msp = doc.modelspace()

# ============================================================
# 1. ALL LAYER NAMES
# ============================================================
print("\n" + "=" * 80)
print("SECTION 1: ALL LAYER NAMES (grouped by prefix)")
print("=" * 80)

all_layers = [layer.dxf.name for layer in doc.layers]
all_layers.sort()

# Group by prefix pattern
prefix_groups = defaultdict(list)
for layer in all_layers:
    # Extract bracket prefix like [衛生], [空調], etc.
    bracket_match = re.match(r'^\[([^\]]+)\]', layer)
    if bracket_match:
        prefix = f"[{bracket_match.group(1)}]"
    else:
        # Try underscore prefix or first segment
        parts = layer.split('_')
        if len(parts) > 1:
            prefix = parts[0]
        else:
            prefix = "OTHER"
    prefix_groups[prefix].append(layer)

print(f"\nTotal layers: {len(all_layers)}")
print(f"Total prefix groups: {len(prefix_groups)}")

for prefix in sorted(prefix_groups.keys()):
    layers = prefix_groups[prefix]
    print(f"\n  Prefix: {repr(prefix)} ({len(layers)} layers)")
    for l in layers:
        print(f"    {repr(l)}")

# ============================================================
# 2. ENTITY TYPES PER LAYER
# ============================================================
print("\n" + "=" * 80)
print("SECTION 2: ENTITY TYPES PER LAYER")
print("=" * 80)

layer_entities = defaultdict(lambda: defaultdict(int))
total_entities = defaultdict(int)

for entity in msp:
    layer = entity.dxf.layer if entity.dxf.hasattr('layer') else 'NO_LAYER'
    etype = entity.dxftype()
    layer_entities[layer][etype] += 1
    total_entities[etype] += 1

print(f"\nTotal entity counts across all layers:")
for etype, count in sorted(total_entities.items(), key=lambda x: -x[1]):
    print(f"  {etype}: {count}")

print(f"\nPer-layer breakdown:")
for layer in sorted(layer_entities.keys()):
    entities = layer_entities[layer]
    total = sum(entities.values())
    print(f"\n  Layer: {repr(layer)} (total: {total})")
    for etype, count in sorted(entities.items(), key=lambda x: -x[1]):
        print(f"    {etype}: {count}")

# ============================================================
# 3. SLEEVE-RELATED DATA
# ============================================================
print("\n" + "=" * 80)
print("SECTION 3: SLEEVE-RELATED DATA")
print("=" * 80)

# Find sleeve-related layers
sleeve_keywords = ['スリーブ', 'sleeve', 'Sleeve', 'SLEEVE', 'スリーブ']
sleeve_layers = [l for l in all_layers if any(kw in l for kw in sleeve_keywords)]
print(f"\nSleeve-related layers: {len(sleeve_layers)}")
for l in sleeve_layers:
    print(f"  {repr(l)}")

# Find CIRCLE entities on sleeve layers
print("\n--- CIRCLE entities on sleeve layers (first 10) ---")
circle_count = 0
for entity in msp:
    if entity.dxftype() == 'CIRCLE':
        layer = entity.dxf.layer if entity.dxf.hasattr('layer') else ''
        if any(kw in layer for kw in sleeve_keywords):
            if circle_count < 10:
                cx, cy = entity.dxf.center.x, entity.dxf.center.y
                r = entity.dxf.radius
                print(f"  Circle: layer={repr(layer)}, center=({cx:.2f}, {cy:.2f}), radius={r:.2f}, diameter={r*2:.2f}")
            circle_count += 1
print(f"  Total circles on sleeve layers: {circle_count}")

# Find INSERT (block references) on sleeve layers
print("\n--- INSERT entities on sleeve layers (first 10) ---")
insert_count = 0
insert_blocks = set()
for entity in msp:
    if entity.dxftype() == 'INSERT':
        layer = entity.dxf.layer if entity.dxf.hasattr('layer') else ''
        if any(kw in layer for kw in sleeve_keywords):
            block_name = entity.dxf.name
            insert_blocks.add(block_name)
            if insert_count < 10:
                pos = entity.dxf.insert
                sx = entity.dxf.xscale if entity.dxf.hasattr('xscale') else 1.0
                sy = entity.dxf.yscale if entity.dxf.hasattr('yscale') else 1.0
                rot = entity.dxf.rotation if entity.dxf.hasattr('rotation') else 0.0
                print(f"  Insert: layer={repr(layer)}, block={repr(block_name)}, pos=({pos.x:.2f},{pos.y:.2f}), scale=({sx:.3f},{sy:.3f}), rot={rot:.1f}")
            insert_count += 1
print(f"  Total inserts on sleeve layers: {insert_count}")
print(f"  Unique block names: {sorted(insert_blocks)}")

# ALL circles regardless of layer (for understanding)
print("\n--- ALL CIRCLE entities (first 15, by layer) ---")
all_circles = defaultdict(list)
for entity in msp:
    if entity.dxftype() == 'CIRCLE':
        layer = entity.dxf.layer if entity.dxf.hasattr('layer') else 'NO_LAYER'
        all_circles[layer].append(entity)

for layer in sorted(all_circles.keys()):
    circles = all_circles[layer]
    print(f"\n  Layer {repr(layer)}: {len(circles)} circles")
    for c in circles[:3]:
        cx, cy = c.dxf.center.x, c.dxf.center.y
        r = c.dxf.radius
        print(f"    center=({cx:.2f},{cy:.2f}), r={r:.2f}, d={r*2:.2f}")

# ============================================================
# 4. DIMENSION ENTITIES
# ============================================================
print("\n" + "=" * 80)
print("SECTION 4: DIMENSION ENTITIES")
print("=" * 80)

dim_by_layer = defaultdict(list)
for entity in msp:
    if entity.dxftype() == 'DIMENSION':
        layer = entity.dxf.layer if entity.dxf.hasattr('layer') else 'NO_LAYER'
        dim_by_layer[layer].append(entity)

print(f"\nDimension entities by layer:")
for layer in sorted(dim_by_layer.keys()):
    dims = dim_by_layer[layer]
    print(f"\n  Layer {repr(layer)}: {len(dims)} dimensions")
    for d in dims[:5]:
        try:
            text = d.dxf.text if d.dxf.hasattr('text') else ''
            defpoint = d.dxf.defpoint if d.dxf.hasattr('defpoint') else None
            text_midpoint = d.dxf.text_midpoint if d.dxf.hasattr('text_midpoint') else None
            dim_type = d.dxf.dimtype if d.dxf.hasattr('dimtype') else 'unknown'
            actual_measurement = d.dxf.actual_measurement if d.dxf.hasattr('actual_measurement') else None
            print(f"    text={repr(text)}, dimtype={dim_type}, measurement={actual_measurement}")
            if defpoint:
                print(f"    defpoint=({defpoint.x:.2f},{defpoint.y:.2f})")
            if text_midpoint:
                print(f"    text_midpoint=({text_midpoint.x:.2f},{text_midpoint.y:.2f})")
        except Exception as e:
            print(f"    Error reading dimension: {e}")

# ============================================================
# 5. TEXT AND MTEXT ENTITIES
# ============================================================
print("\n" + "=" * 80)
print("SECTION 5: TEXT AND MTEXT ENTITIES")
print("=" * 80)

text_entities = []
mtext_entities = []

for entity in msp:
    layer = entity.dxf.layer if entity.dxf.hasattr('layer') else 'NO_LAYER'
    if entity.dxftype() == 'TEXT':
        try:
            text = entity.dxf.text
            pos = entity.dxf.insert
            height = entity.dxf.height if entity.dxf.hasattr('height') else 0
            text_entities.append({'text': text, 'layer': layer, 'pos': pos, 'height': height})
        except:
            pass
    elif entity.dxftype() == 'MTEXT':
        try:
            text = entity.text
            pos = entity.dxf.insert
            height = entity.dxf.char_height if entity.dxf.hasattr('char_height') else 0
            mtext_entities.append({'text': text, 'layer': layer, 'pos': pos, 'height': height})
        except:
            pass

print(f"\nTotal TEXT entities: {len(text_entities)}")
print(f"Total MTEXT entities: {len(mtext_entities)}")

# Pattern matching
sleeve_num_pattern = re.compile(r'[PSD]\w*-\d+', re.IGNORECASE)
pipe_size_pattern = re.compile(r'\d+[φΦφ]|外径|φ\d+', re.IGNORECASE)
fl_pattern = re.compile(r'FL[+\-±]\d+', re.IGNORECASE)
slope_pattern = re.compile(r'\d+/\d+|勾配|SLOPE', re.IGNORECASE)

print("\n--- TEXT entities with sleeve numbers (P-, SD-, etc.) ---")
found = 0
for t in text_entities:
    if sleeve_num_pattern.search(t['text']):
        if found < 20:
            print(f"  {repr(t['text'])} | layer={repr(t['layer'])} | pos=({t['pos'].x:.1f},{t['pos'].y:.1f})")
        found += 1
print(f"  Total: {found}")

print("\n--- TEXT entities with pipe sizes (φ, Φ) ---")
found = 0
for t in text_entities:
    if pipe_size_pattern.search(t['text']):
        if found < 20:
            print(f"  {repr(t['text'])} | layer={repr(t['layer'])} | pos=({t['pos'].x:.1f},{t['pos'].y:.1f})")
        found += 1
print(f"  Total: {found}")

print("\n--- TEXT entities with FL references ---")
found = 0
for t in text_entities:
    if fl_pattern.search(t['text']):
        if found < 20:
            print(f"  {repr(t['text'])} | layer={repr(t['layer'])} | pos=({t['pos'].x:.1f},{t['pos'].y:.1f})")
        found += 1
print(f"  Total: {found}")

print("\n--- MTEXT entities with FL references ---")
found = 0
for t in mtext_entities:
    if fl_pattern.search(t['text']):
        if found < 20:
            print(f"  {repr(t['text'][:100])} | layer={repr(t['layer'])} | pos=({t['pos'].x:.1f},{t['pos'].y:.1f})")
        found += 1
print(f"  Total: {found}")

print("\n--- All TEXT entities by layer (first 5 per layer) ---")
text_by_layer = defaultdict(list)
for t in text_entities:
    text_by_layer[t['layer']].append(t)

for layer in sorted(text_by_layer.keys()):
    texts = text_by_layer[layer]
    print(f"\n  Layer {repr(layer)}: {len(texts)} texts")
    for t in texts[:5]:
        print(f"    {repr(t['text'])} @ ({t['pos'].x:.1f},{t['pos'].y:.1f})")

# ============================================================
# 6. GRID LINES (通り芯)
# ============================================================
print("\n" + "=" * 80)
print("SECTION 6: GRID LINES (通り芯)")
print("=" * 80)

grid_keywords = ['通り芯', '通芯', 'C1', 'GRID', 'AXIS']
grid_layers = [l for l in all_layers if any(kw in l for kw in grid_keywords)]
print(f"\nGrid-related layers: {len(grid_layers)}")
for l in grid_layers:
    print(f"  {repr(l)}")

print("\n--- LINE entities on grid layers (first 10) ---")
for layer in grid_layers:
    lines_on_layer = []
    for entity in msp:
        if entity.dxftype() == 'LINE':
            if entity.dxf.layer == layer:
                lines_on_layer.append(entity)
    print(f"\n  Layer {repr(layer)}: {len(lines_on_layer)} lines")
    for line in lines_on_layer[:5]:
        s = line.dxf.start
        e = line.dxf.end
        print(f"    ({s.x:.1f},{s.y:.1f}) -> ({e.x:.1f},{e.y:.1f})")

print("\n--- INSERT entities on grid layers ---")
for layer in grid_layers:
    inserts_on_layer = []
    for entity in msp:
        if entity.dxftype() == 'INSERT':
            if entity.dxf.layer == layer:
                inserts_on_layer.append(entity)
    if inserts_on_layer:
        print(f"\n  Layer {repr(layer)}: {len(inserts_on_layer)} inserts")
        for ins in inserts_on_layer[:5]:
            pos = ins.dxf.insert
            print(f"    block={repr(ins.dxf.name)}, pos=({pos.x:.1f},{pos.y:.1f})")

# ============================================================
# 7. WALL DATA (壁)
# ============================================================
print("\n" + "=" * 80)
print("SECTION 7: WALL DATA (壁)")
print("=" * 80)

wall_layers = [l for l in all_layers if '壁' in l or 'WALL' in l.upper()]
print(f"\nWall-related layers: {len(wall_layers)}")
for l in wall_layers:
    print(f"  {repr(l)}")

for layer in wall_layers:
    layer_ents = [e for e in msp if e.dxf.hasattr('layer') and e.dxf.layer == layer]
    print(f"\n  Layer {repr(layer)}: {len(layer_ents)} entities")
    lines = [e for e in layer_ents if e.dxftype() == 'LINE']
    polys = [e for e in layer_ents if e.dxftype() == 'LWPOLYLINE']
    print(f"    LINE: {len(lines)}, LWPOLYLINE: {len(polys)}")
    for line in lines[:5]:
        s = line.dxf.start
        e2 = line.dxf.end
        print(f"    LINE: ({s.x:.1f},{s.y:.1f}) -> ({e2.x:.1f},{e2.y:.1f})")
    for poly in polys[:3]:
        pts = list(poly.get_points())
        print(f"    LWPOLY: {len(pts)} points, first: {pts[:3]}")

# ============================================================
# 8. SLAB STEP LINES (段差線)
# ============================================================
print("\n" + "=" * 80)
print("SECTION 8: SLAB STEP LINES (段差線)")
print("=" * 80)

slab_layers = [l for l in all_layers if '段差' in l or 'スラブ' in l]
print(f"\nSlab-related layers: {len(slab_layers)}")
for l in slab_layers:
    print(f"  {repr(l)}")

target_layer = 'F108_3_RCスラブ段差線'
print(f"\n--- Layer {repr(target_layer)} ---")
step_lines = [e for e in msp if e.dxf.hasattr('layer') and e.dxf.layer == target_layer and e.dxftype() == 'LINE']
print(f"LINE count: {len(step_lines)}")
for line in step_lines[:10]:
    s = line.dxf.start
    e2 = line.dxf.end
    print(f"  ({s.x:.2f},{s.y:.2f}) -> ({e2.x:.2f},{e2.y:.2f})")

for slayer in slab_layers:
    if slayer != target_layer:
        ents = [e for e in msp if e.dxf.hasattr('layer') and e.dxf.layer == slayer]
        print(f"\n  Layer {repr(slayer)}: {len(ents)} entities")
        lines = [e for e in ents if e.dxftype() == 'LINE']
        for line in lines[:5]:
            s = line.dxf.start
            e2 = line.dxf.end
            print(f"    LINE: ({s.x:.2f},{s.y:.2f}) -> ({e2.x:.2f},{e2.y:.2f})")

# ============================================================
# 9. BLOCK DEFINITIONS
# ============================================================
print("\n" + "=" * 80)
print("SECTION 9: BLOCK DEFINITIONS")
print("=" * 80)

blocks = list(doc.blocks)
print(f"\nTotal block definitions: {len(blocks)}")

sleeve_blocks = []
other_blocks = []
for block in blocks:
    name = block.name
    if name.startswith('*'):  # Skip internal blocks
        continue
    if any(kw in name for kw in sleeve_keywords):
        sleeve_blocks.append(block)
    else:
        other_blocks.append(block)

print(f"\nSleeve-related blocks: {len(sleeve_blocks)}")
for b in sleeve_blocks:
    ent_types = defaultdict(int)
    for e in b:
        ent_types[e.dxftype()] += 1
    print(f"  Block: {repr(b.name)}")
    print(f"    Entities: {dict(ent_types)}")

print(f"\nOther blocks (first 30): {len(other_blocks)}")
for b in other_blocks[:30]:
    ent_types = defaultdict(int)
    for e in b:
        ent_types[e.dxftype()] += 1
    print(f"  Block: {repr(b.name)}, Entities: {dict(ent_types)}")

# ============================================================
# 10. COORDINATE SYSTEM SUMMARY
# ============================================================
print("\n" + "=" * 80)
print("SECTION 10: COORDINATE SYSTEM SUMMARY")
print("=" * 80)

all_x = []
all_y = []
for entity in msp:
    try:
        if entity.dxftype() == 'LINE':
            all_x.extend([entity.dxf.start.x, entity.dxf.end.x])
            all_y.extend([entity.dxf.start.y, entity.dxf.end.y])
        elif entity.dxftype() in ('CIRCLE', 'ARC'):
            all_x.append(entity.dxf.center.x)
            all_y.append(entity.dxf.center.y)
        elif entity.dxftype() in ('TEXT', 'INSERT'):
            all_x.append(entity.dxf.insert.x)
            all_y.append(entity.dxf.insert.y)
    except:
        pass

if all_x:
    print(f"\nX range: {min(all_x):.2f} to {max(all_x):.2f} (span: {max(all_x)-min(all_x):.2f})")
    print(f"Y range: {min(all_y):.2f} to {max(all_y):.2f} (span: {max(all_y)-min(all_y):.2f})")

# ============================================================
# 11. SAMPLE INSERT DATA (ALL INSERT ENTITIES)
# ============================================================
print("\n" + "=" * 80)
print("SECTION 11: ALL INSERT ENTITIES BY BLOCK NAME")
print("=" * 80)

insert_by_block = defaultdict(list)
for entity in msp:
    if entity.dxftype() == 'INSERT':
        block_name = entity.dxf.name
        layer = entity.dxf.layer if entity.dxf.hasattr('layer') else 'NO_LAYER'
        pos = entity.dxf.insert
        sx = entity.dxf.xscale if entity.dxf.hasattr('xscale') else 1.0
        sy = entity.dxf.yscale if entity.dxf.hasattr('yscale') else 1.0
        rot = entity.dxf.rotation if entity.dxf.hasattr('rotation') else 0.0
        insert_by_block[block_name].append({
            'layer': layer, 'pos': pos, 'sx': sx, 'sy': sy, 'rot': rot
        })

print(f"\nTotal unique block types referenced: {len(insert_by_block)}")
for block_name in sorted(insert_by_block.keys()):
    inserts = insert_by_block[block_name]
    layers_used = set(i['layer'] for i in inserts)
    print(f"\n  Block {repr(block_name)}: {len(inserts)} instances, layers: {[repr(l) for l in sorted(layers_used)]}")
    for ins in inserts[:5]:
        print(f"    pos=({ins['pos'].x:.2f},{ins['pos'].y:.2f}), scale=({ins['sx']:.3f},{ins['sy']:.3f}), rot={ins['rot']:.1f}, layer={repr(ins['layer'])}")

print("\n" + "=" * 80)
print("END OF REPORT")
print("=" * 80)
