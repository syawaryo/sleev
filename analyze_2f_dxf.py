#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Comprehensive analysis of 2F sleeve drawing DXF file.
"""

import ezdxf
from ezdxf import units
from collections import defaultdict
import re
import sys

DXF_PATH = r"C:/Users/2530r/Documents/aice/Takenakaver4/dxf_output/2階床スリーブ図.dxf"

def safe_str(s):
    """Safely convert to string, handling encoding issues."""
    if isinstance(s, bytes):
        try:
            return s.decode('utf-8')
        except:
            return s.decode('cp932', errors='replace')
    return str(s)

def load_doc():
    doc = ezdxf.readfile(DXF_PATH)
    return doc

def section(title):
    print("\n" + "="*80)
    print(f"  {title}")
    print("="*80)

def subsection(title):
    print(f"\n--- {title} ---")

def analyze_layers(doc):
    section("1. ALL LAYER NAMES (grouped by prefix)")

    layers = [layer.dxf.name for layer in doc.layers]
    layers.sort()

    print(f"\nTotal layers: {len(layers)}")

    # Group by prefix pattern
    groups = defaultdict(list)
    for name in layers:
        # Check for bracket prefix like [衛生]
        m = re.match(r'^(\[[^\]]+\])', name)
        if m:
            groups[m.group(1)].append(name)
        # Check for F-prefix like F108_
        elif re.match(r'^F\d+', name):
            m2 = re.match(r'^(F\d+_\d+)', name)
            if m2:
                groups[m2.group(1)].append(name)
            else:
                groups['F-prefix'].append(name)
        # Check for C-prefix
        elif re.match(r'^C\d', name):
            groups['C-prefix (Grid)'].append(name)
        # Check for S-prefix
        elif re.match(r'^S\d', name):
            groups['S-prefix'].append(name)
        # 0 or default
        elif name == '0' or name.startswith('Defpoints'):
            groups['Default'].append(name)
        else:
            # Try to extract first Japanese word
            m3 = re.match(r'^([ぁ-ん\u30A0-\u30FF\u4E00-\u9FFF]+)', name)
            if m3:
                groups[m3.group(1)].append(name)
            else:
                groups['Other'].append(name)

    for group, names in sorted(groups.items()):
        print(f"\n  [{group}] ({len(names)} layers):")
        for n in names:
            print(f"    {n}")

    return layers

def analyze_entities_per_layer(doc):
    section("2. ENTITY TYPES PER LAYER")

    msp = doc.modelspace()
    layer_entities = defaultdict(lambda: defaultdict(int))

    for entity in msp:
        layer = entity.dxf.layer
        etype = entity.dxftype()
        layer_entities[layer][etype] += 1

    # Sort by layer name
    print(f"\nTotal entities in modelspace: {sum(sum(v.values()) for v in layer_entities.values())}")
    print("\n{:<55} {:<15} {:<8}".format("Layer", "EntityType", "Count"))
    print("-"*80)

    for layer in sorted(layer_entities.keys()):
        type_counts = layer_entities[layer]
        total = sum(type_counts.values())
        types_str = ", ".join(f"{t}:{c}" for t, c in sorted(type_counts.items()))
        print(f"  {layer:<53} {types_str}")

    return layer_entities

def find_sleeve_entities(doc):
    section("3. SLEEVE-RELATED DATA")

    msp = doc.modelspace()

    # Keywords that indicate sleeve layers
    sleeve_keywords = ['スリーブ', 'sleeve', 'SLEEVE', 'SL', '開口']

    sleeve_layers = []
    for layer in doc.layers:
        name = layer.dxf.name
        for kw in sleeve_keywords:
            if kw in name:
                sleeve_layers.append(name)
                break

    print(f"\nSleeve-related layers found: {len(sleeve_layers)}")
    for l in sleeve_layers:
        print(f"  {l}")

    # Find circles (likely sleeve symbols)
    subsection("CIRCLE entities on sleeve layers")
    circles = []
    for entity in msp:
        if entity.dxftype() == 'CIRCLE':
            layer = entity.dxf.layer
            # Include circles on any likely sleeve layer
            circles.append({
                'layer': layer,
                'center': (round(entity.dxf.center.x, 2), round(entity.dxf.center.y, 2)),
                'radius': round(entity.dxf.radius, 2),
                'diameter_mm': round(entity.dxf.radius * 2, 2)
            })

    print(f"\nTotal CIRCLE entities: {len(circles)}")

    # Group circles by layer
    circles_by_layer = defaultdict(list)
    for c in circles:
        circles_by_layer[c['layer']].append(c)

    for layer, circs in sorted(circles_by_layer.items()):
        print(f"\n  Layer: {layer} ({len(circs)} circles)")
        for c in circs[:5]:
            print(f"    Center: {c['center']}, Radius: {c['radius']}, Diameter: {c['diameter_mm']}")
        if len(circs) > 5:
            print(f"    ... and {len(circs)-5} more")

    # Find INSERT (block references) on sleeve layers
    subsection("INSERT (Block references) on sleeve-related layers")
    inserts_by_layer = defaultdict(list)
    all_inserts = []

    for entity in msp:
        if entity.dxftype() == 'INSERT':
            layer = entity.dxf.layer
            block_name = entity.dxf.name
            pos = (round(entity.dxf.insert.x, 2), round(entity.dxf.insert.y, 2))
            scale_x = getattr(entity.dxf, 'xscale', 1.0)
            scale_y = getattr(entity.dxf, 'yscale', 1.0)
            rotation = getattr(entity.dxf, 'rotation', 0.0)

            entry = {
                'layer': layer,
                'block': block_name,
                'pos': pos,
                'scale_x': round(scale_x, 3),
                'scale_y': round(scale_y, 3),
                'rotation': round(rotation, 2)
            }
            all_inserts.append(entry)
            inserts_by_layer[layer].append(entry)

    print(f"\nTotal INSERT entities: {len(all_inserts)}")

    # Check which inserts are on sleeve-related layers
    sleeve_inserts = []
    for kw in sleeve_keywords:
        for layer, inserts in inserts_by_layer.items():
            if kw in layer:
                sleeve_inserts.extend(inserts)

    print(f"INSERT entities on sleeve layers: {len(sleeve_inserts)}")
    for ins in sleeve_inserts[:10]:
        print(f"  Layer: {ins['layer']}, Block: {ins['block']}, Pos: {ins['pos']}, Scale: ({ins['scale_x']},{ins['scale_y']}), Rot: {ins['rotation']}")

    # Show all unique block names used in inserts
    subsection("All block names used in INSERT entities")
    block_usage = defaultdict(int)
    for ins in all_inserts:
        block_usage[ins['block']] += 1

    for bname, cnt in sorted(block_usage.items(), key=lambda x: -x[1])[:30]:
        print(f"  {bname}: {cnt} uses")

    return sleeve_layers, circles, all_inserts

def analyze_dimensions(doc):
    section("4. DIMENSION ENTITIES")

    msp = doc.modelspace()
    dims = []

    for entity in msp:
        if entity.dxftype() == 'DIMENSION':
            layer = entity.dxf.layer
            try:
                dim_type = entity.dxf.dimtype
            except:
                dim_type = None

            try:
                text_val = entity.dxf.text
            except:
                text_val = ''

            try:
                defpoint = entity.dxf.defpoint
                defpoint_str = f"({round(defpoint.x,2)}, {round(defpoint.y,2)})"
            except:
                defpoint_str = 'N/A'

            try:
                defpoint2 = entity.dxf.defpoint2
                defpoint2_str = f"({round(defpoint2.x,2)}, {round(defpoint2.y,2)})"
            except:
                defpoint2_str = 'N/A'

            try:
                defpoint3 = entity.dxf.defpoint3
                defpoint3_str = f"({round(defpoint3.x,2)}, {round(defpoint3.y,2)})"
            except:
                defpoint3_str = 'N/A'

            # Try to get actual measurement
            try:
                actual_measurement = entity.dxf.actual_measurement
            except:
                actual_measurement = None

            dims.append({
                'layer': layer,
                'dim_type': dim_type,
                'text': text_val,
                'defpoint': defpoint_str,
                'defpoint2': defpoint2_str,
                'defpoint3': defpoint3_str,
                'measurement': actual_measurement
            })

    dims_by_layer = defaultdict(list)
    for d in dims:
        dims_by_layer[d['layer']].append(d)

    print(f"\nTotal DIMENSION entities: {len(dims)}")
    print(f"Layers with dimensions: {len(dims_by_layer)}")

    for layer, layer_dims in sorted(dims_by_layer.items()):
        print(f"\n  Layer: {layer} ({len(layer_dims)} dims)")
        for d in layer_dims[:5]:
            meas_str = f", Measured: {round(d['measurement'],2)}" if d['measurement'] is not None else ""
            print(f"    Text: {repr(d['text'])}, Type: {d['dim_type']}, Def1: {d['defpoint']}, Def2: {d['defpoint2']}{meas_str}")
        if len(layer_dims) > 5:
            print(f"    ... and {len(layer_dims)-5} more")

    return dims

def analyze_text_entities(doc):
    section("5. TEXT / MTEXT ENTITIES")

    msp = doc.modelspace()

    # Patterns to look for
    patterns = {
        'sleeve_num': re.compile(r'[A-Z]{1,3}-[A-Z]?-?\d+|[A-Z]{2,3}\d{3}|P-\d+'),
        'pipe_size': re.compile(r'\d+[φΦ]|φ\d+|Φ\d+|外径\d+|DN\d+|\d+A\b'),
        'level_ref': re.compile(r'FL[+\-]\d+|EL[+\-]?\d+|SL[+\-]\d+|▽\d+'),
        'slope': re.compile(r'\d+/\d+|勾配|SLOPE|slope|\d+%'),
        'japanese_size': re.compile(r'\d+×\d+|\d+x\d+'),
    }

    texts = []
    mtexts = []

    for entity in msp:
        if entity.dxftype() == 'TEXT':
            try:
                text_val = entity.dxf.text
                layer = entity.dxf.layer
                pos = entity.dxf.insert
                height = entity.dxf.height
                texts.append({
                    'layer': layer,
                    'text': text_val,
                    'pos': (round(pos.x, 2), round(pos.y, 2)),
                    'height': round(height, 2)
                })
            except Exception as e:
                pass

        elif entity.dxftype() == 'MTEXT':
            try:
                text_val = entity.plain_mtext()
                layer = entity.dxf.layer
                pos = entity.dxf.insert
                height = entity.dxf.char_height
                mtexts.append({
                    'layer': layer,
                    'text': text_val,
                    'pos': (round(pos.x, 2), round(pos.y, 2)),
                    'height': round(height, 2)
                })
            except Exception as e:
                try:
                    text_val = entity.dxf.text
                    layer = entity.dxf.layer
                    pos = entity.dxf.insert
                    mtexts.append({
                        'layer': layer,
                        'text': text_val,
                        'pos': (round(pos.x, 2), round(pos.y, 2)),
                        'height': 0
                    })
                except:
                    pass

    print(f"\nTotal TEXT entities: {len(texts)}")
    print(f"Total MTEXT entities: {len(mtexts)}")

    all_text_entities = texts + mtexts

    # Match patterns
    subsection("Pattern matches in text entities")
    for pat_name, pattern in patterns.items():
        matches = []
        for t in all_text_entities:
            txt = t['text']
            if txt and pattern.search(txt):
                matches.append(t)
        print(f"\n  Pattern '{pat_name}': {len(matches)} matches")
        for m in matches[:10]:
            print(f"    Layer: {m['layer']}, Text: {repr(m['text'])}, Pos: {m['pos']}")
        if len(matches) > 10:
            print(f"    ... and {len(matches)-10} more")

    # Show texts by layer (sample)
    subsection("TEXT entities by layer (sample)")
    texts_by_layer = defaultdict(list)
    for t in all_text_entities:
        texts_by_layer[t['layer']].append(t)

    for layer, layer_texts in sorted(texts_by_layer.items()):
        print(f"\n  Layer: {layer} ({len(layer_texts)} texts)")
        for t in layer_texts[:5]:
            print(f"    {repr(t['text'])}, Pos: {t['pos']}")
        if len(layer_texts) > 5:
            print(f"    ... and {len(layer_texts)-5} more")

    return texts, mtexts

def analyze_grid_lines(doc):
    section("6. GRID LINES (通り芯)")

    msp = doc.modelspace()

    # Find grid-related layers
    grid_keywords = ['通り芯', '通芯', 'C1', 'GRID', 'grid', '軸']
    grid_layers = []

    for layer in doc.layers:
        name = layer.dxf.name
        for kw in grid_keywords:
            if kw in name:
                grid_layers.append(name)
                break

    print(f"\nGrid-related layers: {len(grid_layers)}")
    for l in grid_layers:
        print(f"  {l}")

    # Get lines on grid layers
    grid_lines = []
    grid_texts = []

    for entity in msp:
        layer = entity.dxf.layer
        is_grid = any(kw in layer for kw in grid_keywords)

        if is_grid:
            if entity.dxftype() == 'LINE':
                start = entity.dxf.start
                end = entity.dxf.end
                grid_lines.append({
                    'layer': layer,
                    'start': (round(start.x, 2), round(start.y, 2)),
                    'end': (round(end.x, 2), round(end.y, 2))
                })
            elif entity.dxftype() in ('TEXT', 'MTEXT'):
                try:
                    if entity.dxftype() == 'TEXT':
                        txt = entity.dxf.text
                        pos = entity.dxf.insert
                    else:
                        txt = entity.plain_mtext()
                        pos = entity.dxf.insert
                    grid_texts.append({
                        'layer': layer,
                        'text': txt,
                        'pos': (round(pos.x, 2), round(pos.y, 2))
                    })
                except:
                    pass

    print(f"\nGrid LINE entities: {len(grid_lines)}")
    print(f"Grid TEXT entities: {len(grid_texts)}")

    subsection("Sample grid lines (first 10)")
    for gl in grid_lines[:10]:
        print(f"  Layer: {gl['layer']}, Start: {gl['start']}, End: {gl['end']}")

    subsection("Sample grid texts (first 10)")
    for gt in grid_texts[:10]:
        print(f"  Layer: {gt['layer']}, Text: {repr(gt['text'])}, Pos: {gt['pos']}")

    # Try to identify X and Y grid lines
    subsection("Grid line analysis (horizontal vs vertical)")
    h_lines = [l for l in grid_lines if abs((l['end'][1] - l['start'][1])) < abs((l['end'][0] - l['start'][0]))]
    v_lines = [l for l in grid_lines if abs((l['end'][1] - l['start'][1])) >= abs((l['end'][0] - l['start'][0]))]

    print(f"\n  Horizontal grid lines: {len(h_lines)}")
    # Get unique Y values for horizontal lines
    y_vals = sorted(set(round((l['start'][1] + l['end'][1])/2, 0) for l in h_lines))
    print(f"  Unique Y positions: {y_vals[:15]}")

    print(f"\n  Vertical grid lines: {len(v_lines)}")
    x_vals = sorted(set(round((l['start'][0] + l['end'][0])/2, 0) for l in v_lines))
    print(f"  Unique X positions: {x_vals[:15]}")

    return grid_layers, grid_lines, grid_texts

def analyze_walls(doc):
    section("7. WALL DATA (壁)")

    msp = doc.modelspace()

    wall_keywords = ['壁', 'WALL', 'wall']
    wall_layers = []

    for layer in doc.layers:
        name = layer.dxf.name
        for kw in wall_keywords:
            if kw in name:
                wall_layers.append(name)
                break

    print(f"\nWall-related layers: {len(wall_layers)}")
    for l in wall_layers:
        print(f"  {l}")

    wall_entities = defaultdict(list)

    for entity in msp:
        layer = entity.dxf.layer
        is_wall = any(kw in layer for kw in wall_keywords)

        if is_wall:
            if entity.dxftype() == 'LINE':
                start = entity.dxf.start
                end = entity.dxf.end
                wall_entities[layer].append({
                    'type': 'LINE',
                    'start': (round(start.x, 2), round(start.y, 2)),
                    'end': (round(end.x, 2), round(end.y, 2))
                })
            elif entity.dxftype() == 'LWPOLYLINE':
                pts = [(round(p[0], 2), round(p[1], 2)) for p in entity.get_points()]
                wall_entities[layer].append({
                    'type': 'LWPOLYLINE',
                    'points': pts[:4],
                    'total_pts': len(pts)
                })

    for layer, entities in sorted(wall_entities.items()):
        print(f"\n  Layer: {layer} ({len(entities)} entities)")
        for e in entities[:5]:
            if e['type'] == 'LINE':
                print(f"    LINE: {e['start']} -> {e['end']}")
            else:
                print(f"    LWPOLYLINE: {e['total_pts']} pts, first 4: {e['points']}")
        if len(entities) > 5:
            print(f"    ... and {len(entities)-5} more")

    return wall_layers

def analyze_slab_steps(doc):
    section("8. SLAB STEP LINES (段差線)")

    msp = doc.modelspace()

    step_keywords = ['段差', 'スラブ段差', 'RCスラブ段差']
    step_layers = []

    for layer in doc.layers:
        name = layer.dxf.name
        for kw in step_keywords:
            if kw in name:
                step_layers.append(name)
                break

    print(f"\nSlab step layers: {len(step_layers)}")
    for l in step_layers:
        print(f"  {l}")

    step_entities = defaultdict(list)

    for entity in msp:
        layer = entity.dxf.layer
        is_step = any(kw in layer for kw in step_keywords)

        if is_step:
            if entity.dxftype() == 'LINE':
                start = entity.dxf.start
                end = entity.dxf.end
                step_entities[layer].append({
                    'type': 'LINE',
                    'start': (round(start.x, 2), round(start.y, 2)),
                    'end': (round(end.x, 2), round(end.y, 2))
                })
            elif entity.dxftype() == 'LWPOLYLINE':
                pts = [(round(p[0], 2), round(p[1], 2)) for p in entity.get_points()]
                step_entities[layer].append({
                    'type': 'LWPOLYLINE',
                    'points': pts
                })

    for layer, entities in sorted(step_entities.items()):
        print(f"\n  Layer: {layer} ({len(entities)} entities)")
        for e in entities[:8]:
            if e['type'] == 'LINE':
                print(f"    LINE: {e['start']} -> {e['end']}")
            else:
                print(f"    LWPOLYLINE: {e['points']}")
        if len(entities) > 8:
            print(f"    ... and {len(entities)-8} more")

    return step_layers

def analyze_blocks(doc):
    section("9. BLOCK DEFINITIONS")

    sleeve_keywords = ['スリーブ', 'sleeve', 'SLEEVE', 'SL', '開口', 'PIPE', 'pipe']

    print(f"\nAll block definitions:")
    sleeve_blocks = []

    for block in doc.blocks:
        name = block.name
        # Count entities in block
        entity_count = sum(1 for _ in block)
        entity_types = defaultdict(int)
        for ent in block:
            entity_types[ent.dxftype()] += 1

        types_str = ", ".join(f"{t}:{c}" for t, c in sorted(entity_types.items()))

        is_sleeve = any(kw in name for kw in sleeve_keywords)
        marker = " [SLEEVE]" if is_sleeve else ""

        print(f"  {name}: {entity_count} entities ({types_str}){marker}")

        if is_sleeve:
            sleeve_blocks.append(name)

    if sleeve_blocks:
        print(f"\nSleeve-related blocks: {sleeve_blocks}")

    return sleeve_blocks

def analyze_coordinate_range(doc):
    section("COORDINATE SYSTEM & SCALE")

    msp = doc.modelspace()

    min_x, max_x = float('inf'), float('-inf')
    min_y, max_y = float('inf'), float('-inf')

    for entity in msp:
        try:
            if entity.dxftype() == 'LINE':
                for pt in [entity.dxf.start, entity.dxf.end]:
                    min_x = min(min_x, pt.x)
                    max_x = max(max_x, pt.x)
                    min_y = min(min_y, pt.y)
                    max_y = max(max_y, pt.y)
            elif entity.dxftype() == 'CIRCLE':
                c = entity.dxf.center
                r = entity.dxf.radius
                min_x = min(min_x, c.x - r)
                max_x = max(max_x, c.x + r)
                min_y = min(min_y, c.y - r)
                max_y = max(max_y, c.y + r)
            elif entity.dxftype() == 'INSERT':
                pt = entity.dxf.insert
                min_x = min(min_x, pt.x)
                max_x = max(max_x, pt.x)
                min_y = min(min_y, pt.y)
                max_y = max(max_y, pt.y)
            elif entity.dxftype() in ('TEXT', 'MTEXT'):
                pt = entity.dxf.insert
                min_x = min(min_x, pt.x)
                max_x = max(max_x, pt.x)
                min_y = min(min_y, pt.y)
                max_y = max(max_y, pt.y)
        except:
            pass

    print(f"\n  X range: {round(min_x,2)} to {round(max_x,2)} (span: {round(max_x-min_x,2)})")
    print(f"  Y range: {round(min_y,2)} to {round(max_y,2)} (span: {round(max_y-min_y,2)})")
    print(f"\n  NOTE: Coordinates appear to be in mm (typical for Japanese construction DXF)")
    print(f"  Drawing likely uses 1:1 scale (1 unit = 1mm)")

def analyze_lwpolylines(doc):
    section("LWPOLYLINE ANALYSIS")

    msp = doc.modelspace()
    poly_by_layer = defaultdict(list)

    for entity in msp:
        if entity.dxftype() == 'LWPOLYLINE':
            layer = entity.dxf.layer
            pts = [(round(p[0], 2), round(p[1], 2)) for p in entity.get_points()]
            is_closed = entity.is_closed
            poly_by_layer[layer].append({
                'pts': pts,
                'closed': is_closed,
                'count': len(pts)
            })

    print(f"\nTotal LWPOLYLINE entities: {sum(len(v) for v in poly_by_layer.values())}")
    print(f"Layers with LWPOLYLINE: {len(poly_by_layer)}")

    for layer, polys in sorted(poly_by_layer.items()):
        print(f"\n  Layer: {layer} ({len(polys)} polylines)")
        for p in polys[:3]:
            closed_str = " [CLOSED]" if p['closed'] else ""
            pts_preview = str(p['pts'][:3]) + ('...' if p['count'] > 3 else '')
            print(f"    {p['count']} pts{closed_str}: {pts_preview}")

def main():
    print("Loading DXF file...")
    doc = load_doc()
    print(f"DXF version: {doc.dxfversion}")
    print(f"Units: {doc.units}")

    analyze_coordinate_range(doc)
    layers = analyze_layers(doc)
    layer_entities = analyze_entities_per_layer(doc)
    sleeve_layers, circles, inserts = find_sleeve_entities(doc)
    dims = analyze_dimensions(doc)
    texts, mtexts = analyze_text_entities(doc)
    grid_layers, grid_lines, grid_texts = analyze_grid_lines(doc)
    analyze_walls(doc)
    analyze_slab_steps(doc)
    sleeve_blocks = analyze_blocks(doc)
    analyze_lwpolylines(doc)

    section("SUMMARY")
    print(f"\n  Total layers: {len(layers)}")
    print(f"  Total CIRCLE entities: {len(circles)}")
    print(f"  Total INSERT entities: {len(inserts)}")
    print(f"  Total DIMENSION entities: {len(dims)}")
    print(f"  Total TEXT entities: {len(texts)}")
    print(f"  Total MTEXT entities: {len(mtexts)}")
    print(f"  Grid layers found: {len(grid_layers)}")
    print(f"  Grid lines found: {len(grid_lines)}")

if __name__ == '__main__':
    main()
