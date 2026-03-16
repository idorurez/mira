"""Generate layer extraction workflow using FaceSegment + LaMa (ComfyUI-RMBG) for Inochi2D.

Multi-stage pipeline:
  1. Load reference image
  2. Segment hair → grow mask → LaMa inpaint to remove hair
  3. Manually mask eyebrows from the hair-removed image (LoadImage masks)
  4. Auto-segment skin from hair-removed image
  5. Auto-segment eyes, mouth, nose, hair, ears from original image

Eyebrows are done manually because FaceSegment (trained on real faces)
confuses anime face markings with eyebrows. The hair-removed image makes
manual masking easy since the full eyebrow shape is revealed.

Requirements:
  - ComfyUI-RMBG extension (https://github.com/1038lab/ComfyUI-RMBG)
  - Models (download from HuggingFace on first run):
    - 1038lab/segformer_face (face parsing)
    - Big-Lama (inpainting)

Run:  python comfyui/generate_layer_extraction_workflow.py
"""
import json

# ═══════════════════════════════════════════════════════════════════════
# FACESEGMENT TOGGLES
# ═══════════════════════════════════════════════════════════════════════

ALL_TOGGLES = [
    "Skin", "Nose", "Eyeglasses", "Left-eye", "Right-eye",
    "Left-eyebrow", "Right-eyebrow", "Left-ear", "Right-ear",
    "Mouth", "Upper-lip", "Lower-lip", "Hair", "Earring", "Neck",
]


def make_widgets(enabled_toggles, process_res=512, mask_blur=0, mask_offset=0,
                 invert=False, background="Alpha", bg_color="#222222"):
    """Build widgets_values list for FaceSegment node."""
    vals = [t in enabled_toggles for t in ALL_TOGGLES]
    vals.extend([process_res, mask_blur, mask_offset, invert, background, bg_color])
    return vals


# ═══════════════════════════════════════════════════════════════════════
# WORKFLOW BUILDER
# ═══════════════════════════════════════════════════════════════════════

nodes = []
links = []
link_id = 0
node_idx = {}


def L():
    global link_id
    link_id += 1
    return link_id


def add(node):
    node_idx[node["id"]] = len(nodes)
    nodes.append(node)


def out_links(nid, slot=0):
    return nodes[node_idx[nid]]["outputs"][slot]["links"]


def link(src_id, src_slot, dst_id, dst_slot, dtype):
    """Create a link between two nodes."""
    lid = L()
    links.append([lid, src_id, src_slot, dst_id, dst_slot, dtype])
    out_links(src_id, src_slot).append(lid)
    dst_node = nodes[node_idx[dst_id]]
    dst_node["inputs"][dst_slot]["link"] = lid
    return lid


# ═══════════════════════════════════════════════════════════════════════
# STAGE 1: LOAD IMAGE
# ═══════════════════════════════════════════════════════════════════════

add({
    "id": 1, "type": "LoadImage",
    "pos": [-500, 0], "size": [315, 400],
    "properties": {},
    "widgets_values": ["mira_reference.png", "image"],
    "outputs": [
        {"name": "IMAGE", "type": "IMAGE", "links": [], "slot_index": 0},
        {"name": "MASK", "type": "MASK", "links": [], "slot_index": 1},
    ],
    "title": "1. Load Reference Character"
})

# ═══════════════════════════════════════════════════════════════════════
# STAGE 2: HAIR REMOVAL PIPELINE
# Segment hair → enhance mask → LaMa inpaint to remove hair
# ═══════════════════════════════════════════════════════════════════════

# 10: FaceSegment - hair only
add({
    "id": 10, "type": "FaceSegment",
    "pos": [0, -200], "size": [315, 450],
    "properties": {},
    "widgets_values": make_widgets(["Hair"]),
    "inputs": [
        {"name": "images", "type": "IMAGE", "link": None},
    ],
    "outputs": [
        {"name": "IMAGE", "type": "IMAGE", "links": [], "slot_index": 0},
        {"name": "MASK", "type": "MASK", "links": [], "slot_index": 1},
        {"name": "MASK_IMAGE", "type": "IMAGE", "links": [], "slot_index": 2},
    ],
    "title": "2a. Segment Hair"
})
link(1, 0, 10, 0, "IMAGE")

# 11: MaskEnhancer - grow hair mask for full coverage
add({
    "id": 11, "type": "AILab_MaskEnhancer",
    "pos": [370, -200], "size": [315, 200],
    "properties": {},
    "widgets_values": [1.0, 3, 5, 2.0, True, False],
    "inputs": [
        {"name": "mask", "type": "MASK", "link": None},
    ],
    "outputs": [
        {"name": "MASK", "type": "MASK", "links": [], "slot_index": 0},
    ],
    "title": "2b. Grow Hair Mask (+5px)"
})
link(10, 1, 11, 0, "MASK")

# 12: LamaRemover - inpaint away the hair
add({
    "id": 12, "type": "AILab_LamaRemover",
    "pos": [740, -200], "size": [315, 150],
    "properties": {},
    "widgets_values": [255, 10],
    "inputs": [
        {"name": "images", "type": "IMAGE", "link": None},
        {"name": "masks", "type": "MASK", "link": None},
    ],
    "outputs": [
        {"name": "IMAGE", "type": "IMAGE", "links": [], "slot_index": 0},
    ],
    "title": "2c. Remove Hair (LaMa)"
})
link(1, 0, 12, 0, "IMAGE")
link(11, 0, 12, 1, "MASK")

# 13: Save hair-removed preview
add({
    "id": 13, "type": "SaveImage",
    "pos": [1110, -200], "size": [300, 250],
    "properties": {},
    "widgets_values": ["mira_debug_hair_removed"],
    "inputs": [{"name": "images", "type": "IMAGE", "link": None}],
    "title": "2d. Save Hair-Removed (use for eyebrow masking)"
})
link(12, 0, 13, 0, "IMAGE")

# ═══════════════════════════════════════════════════════════════════════
# STAGE 3: MANUAL EYEBROW MASKS (from hair-removed image)
# Paint eyebrow masks in white on black, load them here.
# The hair-removed image gives you the full eyebrow shape to trace.
# Use JoinImageWithAlpha to cut eyebrows from hair-removed image.
# ═══════════════════════════════════════════════════════════════════════

EYEBROW_LAYERS = [
    ("eyebrow_left",  "mira_mask_eyebrow_left.png"),
    ("eyebrow_right", "mira_mask_eyebrow_right.png"),
]

STAGE3_Y = 300

for i, (name, mask_file) in enumerate(EYEBROW_LAYERS):
    y = STAGE3_Y + i * 350

    load_id = 20 + i * 10     # LoadImage (manual mask)
    join_id = 21 + i * 10     # JoinImageWithAlpha
    save_id = 22 + i * 10     # SaveImage

    # Load the manually-painted eyebrow mask (white on black RGB PNG)
    add({
        "id": load_id, "type": "LoadImage",
        "pos": [0, y], "size": [315, 250],
        "properties": {},
        "widgets_values": [mask_file, "image"],
        "outputs": [
            {"name": "IMAGE", "type": "IMAGE", "links": [], "slot_index": 0},
            {"name": "MASK", "type": "MASK", "links": [], "slot_index": 1},
        ],
        "title": f"3. Load Mask: {name} (manual)"
    })

    # Convert loaded image (white-on-black RGB) to a mask
    # ImageToMask extracts a single channel to use as mask
    convert_id = load_id + 4
    add({
        "id": convert_id, "type": "ImageToMask",
        "pos": [370, y], "size": [200, 60],
        "properties": {},
        "widgets_values": ["red"],  # channel to extract
        "inputs": [
            {"name": "image", "type": "IMAGE", "link": None},
        ],
        "outputs": [
            {"name": "MASK", "type": "MASK", "links": [], "slot_index": 0},
        ],
        "title": f"3. Convert to Mask: {name}"
    })
    link(load_id, 0, convert_id, 0, "IMAGE")

    # Invert mask: ComfyUI convention is white=masked, but we want
    # white=visible for alpha. Flip so painted white areas become opaque.
    invert_id = load_id + 5
    add({
        "id": invert_id, "type": "InvertMask",
        "pos": [620, y], "size": [200, 40],
        "properties": {},
        "widgets_values": [],
        "inputs": [
            {"name": "mask", "type": "MASK", "link": None},
        ],
        "outputs": [
            {"name": "MASK", "type": "MASK", "links": [], "slot_index": 0},
        ],
        "title": f"3. Invert Mask: {name}"
    })
    link(convert_id, 0, invert_id, 0, "MASK")

    # JoinImageWithAlpha: hair-removed image + inverted mask → transparent PNG
    add({
        "id": join_id, "type": "JoinImageWithAlpha",
        "pos": [870, y], "size": [250, 80],
        "properties": {},
        "widgets_values": [],
        "inputs": [
            {"name": "image", "type": "IMAGE", "link": None},
            {"name": "alpha", "type": "MASK", "link": None},
        ],
        "outputs": [
            {"name": "IMAGE", "type": "IMAGE", "links": [], "slot_index": 0},
        ],
        "title": f"3. Apply Mask: {name}"
    })
    link(12, 0, join_id, 0, "IMAGE")        # hair-removed image
    link(invert_id, 0, join_id, 1, "MASK")   # inverted mask

    # Save result
    add({
        "id": save_id, "type": "SaveImage",
        "pos": [1170, y], "size": [300, 250],
        "properties": {},
        "widgets_values": [f"mira_layer_{name}"],
        "inputs": [{"name": "images", "type": "IMAGE", "link": None}],
        "title": f"3. Save: {name}"
    })
    link(join_id, 0, save_id, 0, "IMAGE")

# ═══════════════════════════════════════════════════════════════════════
# STAGE 4: AUTO LAYERS - OCCLUDED (from hair-removed image)
# Skin is segmented from the hair-removed image for full coverage
# ═══════════════════════════════════════════════════════════════════════

OCCLUDED_LAYERS = [
    ("face_skin", ["Skin"]),
]

STAGE4_Y = STAGE3_Y + len(EYEBROW_LAYERS) * 350 + 100
ROW_H = 300

for i, (name, toggles) in enumerate(OCCLUDED_LAYERS):
    y = STAGE4_Y + i * ROW_H

    seg_id = 40 + i * 10
    save_id = 41 + i * 10

    add({
        "id": seg_id, "type": "FaceSegment",
        "pos": [0, y], "size": [315, 450],
        "properties": {},
        "widgets_values": make_widgets(toggles),
        "inputs": [
            {"name": "images", "type": "IMAGE", "link": None},
        ],
        "outputs": [
            {"name": "IMAGE", "type": "IMAGE", "links": [], "slot_index": 0},
            {"name": "MASK", "type": "MASK", "links": [], "slot_index": 1},
            {"name": "MASK_IMAGE", "type": "IMAGE", "links": [], "slot_index": 2},
        ],
        "title": f"4. {name} (from hair-removed)"
    })
    link(12, 0, seg_id, 0, "IMAGE")

    add({
        "id": save_id, "type": "SaveImage",
        "pos": [370, y], "size": [300, 250],
        "properties": {},
        "widgets_values": [f"mira_layer_{name}"],
        "inputs": [{"name": "images", "type": "IMAGE", "link": None}],
        "title": f"4. Save: {name}"
    })
    link(seg_id, 0, save_id, 0, "IMAGE")

# ═══════════════════════════════════════════════════════════════════════
# STAGE 5: AUTO LAYERS - DIRECT (from original image)
# ═══════════════════════════════════════════════════════════════════════

DIRECT_LAYERS = [
    ("eye_left",  ["Left-eye"]),
    ("eye_right", ["Right-eye"]),
    ("mouth",     ["Mouth", "Upper-lip", "Lower-lip"]),
    ("nose",      ["Nose"]),
    ("hair",      ["Hair"]),
    ("ears",      ["Left-ear", "Right-ear"]),
]

STAGE5_Y = STAGE4_Y + len(OCCLUDED_LAYERS) * ROW_H + 100

for i, (name, toggles) in enumerate(DIRECT_LAYERS):
    y = STAGE5_Y + i * ROW_H

    seg_id = 50 + i * 10
    save_id = 51 + i * 10

    add({
        "id": seg_id, "type": "FaceSegment",
        "pos": [0, y], "size": [315, 450],
        "properties": {},
        "widgets_values": make_widgets(toggles),
        "inputs": [
            {"name": "images", "type": "IMAGE", "link": None},
        ],
        "outputs": [
            {"name": "IMAGE", "type": "IMAGE", "links": [], "slot_index": 0},
            {"name": "MASK", "type": "MASK", "links": [], "slot_index": 1},
            {"name": "MASK_IMAGE", "type": "IMAGE", "links": [], "slot_index": 2},
        ],
        "title": f"5. {name} (from original)"
    })
    link(1, 0, seg_id, 0, "IMAGE")

    add({
        "id": save_id, "type": "SaveImage",
        "pos": [370, y], "size": [300, 250],
        "properties": {},
        "widgets_values": [f"mira_layer_{name}"],
        "inputs": [{"name": "images", "type": "IMAGE", "link": None}],
        "title": f"5. Save: {name}"
    })
    link(seg_id, 0, save_id, 0, "IMAGE")

# ═══════════════════════════════════════════════════════════════════════
# NOTES
# ═══════════════════════════════════════════════════════════════════════

NOTE_TEXT = """=== LAYER EXTRACTION FOR INOCHI2D ===

Multi-stage pipeline using FaceSegment + LaMa + manual eyebrow masks.

PIPELINE:
  Stage 1: Load reference image
  Stage 2: Hair removal (FaceSegment -> MaskEnhancer -> LaMa)
  Stage 3: MANUAL eyebrow masks applied to hair-removed image
  Stage 4: Auto skin from hair-removed image
  Stage 5: Auto eyes, mouth, nose, hair, ears from original

EYEBROW WORKFLOW:
  1. Run the workflow once to get mira_debug_hair_removed.png
  2. Open that image in Photoshop/GIMP
  3. Paint white-on-black masks for each eyebrow
  4. Save as:
     - mira_mask_eyebrow_left.png
     - mira_mask_eyebrow_right.png
  5. Place in ComfyUI input/ folder
  6. Re-run workflow - eyebrows will be cut from hair-removed image

WHY MANUAL EYEBROWS:
  FaceSegment (trained on real photos) confuses anime face markings
  with eyebrows. Manual masking on the hair-removed image is fast
  and gives clean results.

OUTPUT FILES:
  mira_layer_eyebrow_left.png   (manual mask on hair-removed)
  mira_layer_eyebrow_right.png  (manual mask on hair-removed)
  mira_layer_face_skin.png      (auto from hair-removed)
  mira_layer_eye_left.png       (auto from original)
  mira_layer_eye_right.png      (auto from original)
  mira_layer_mouth.png          (auto from original)
  mira_layer_nose.png           (auto from original)
  mira_layer_hair.png           (auto from original)
  mira_layer_ears.png           (auto from original)
  mira_debug_hair_removed.png   (reference for manual masking)
"""

add({
    "id": 100, "type": "Note",
    "pos": [-500, 450], "size": [450, 750],
    "properties": {},
    "widgets_values": [NOTE_TEXT],
    "title": "Instructions"
})

# ═══════════════════════════════════════════════════════════════════════
# ASSEMBLE
# ═══════════════════════════════════════════════════════════════════════

workflow = {
    "last_node_id": max(n["id"] for n in nodes),
    "last_link_id": link_id,
    "nodes": nodes,
    "links": links,
    "groups": [
        {
            "title": "Stage 1: Input",
            "bounding": [-520, -50, 360, 500],
            "color": "#3f789e",
        },
        {
            "title": "Stage 2: Hair Removal Pipeline",
            "bounding": [-20, -250, 1450, 500],
            "color": "#8e443f",
        },
        {
            "title": "Stage 3: Manual Eyebrow Masks (from hair-removed)",
            "bounding": [-20, STAGE3_Y - 50, 1020, len(EYEBROW_LAYERS) * 350 + 50],
            "color": "#8e7f3f",
        },
        {
            "title": "Stage 4: Skin (from hair-removed)",
            "bounding": [-20, STAGE4_Y - 50, 720, len(OCCLUDED_LAYERS) * ROW_H + 50],
            "color": "#3f8e5a",
        },
        {
            "title": "Stage 5: Direct Layers (from original)",
            "bounding": [-20, STAGE5_Y - 50, 720, len(DIRECT_LAYERS) * ROW_H + 50],
            "color": "#6f3f8e",
        },
    ],
    "config": {},
    "extra": {},
    "version": 0.4,
}

out_path = __file__.replace("generate_layer_extraction_workflow.py", "mira_layer_extraction.json")
with open(out_path, "w", encoding="utf-8") as f:
    json.dump(workflow, f, indent=2, ensure_ascii=False)

print(f"Wrote {out_path}")
print(f"  {len(nodes)} nodes, {link_id} links")
print(f"  Manual layers: {[l[0] for l in EYEBROW_LAYERS]}")
print(f"  Auto occluded: {[l[0] for l in OCCLUDED_LAYERS]}")
print(f"  Auto direct:   {[l[0] for l in DIRECT_LAYERS]}")
