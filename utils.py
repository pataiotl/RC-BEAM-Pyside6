import json
import re
import math
import html
from io import BytesIO
import pandas as pd

from engine import ZONES, BAR_OPTIONS, STIRRUP_OPTIONS, SKIN_BAR_OPTIONS

def build_default_app_state():
    state = {
        "input_mode": "Manual Input",
        "beam_length": 6.0,
        "mu_left": 200.0,
        "vu_left": 150.0,
        "tu_left": 0.0,
        "mu_mid": 180.0,
        "vu_mid": 60.0,
        "tu_mid": 0.0,
        "mu_right": 220.0,
        "vu_right": 155.0,
        "tu_right": 0.0,
        "b": 300,
        "h": 600,
        "fc": 35,
        "fy": 500,
        "lambda_c": 1.0,
        "fyt": 400,
        "bar_v_name": "DB10",
        "n_legs": 2,
        "cover_clear": 40,
        "clear_space": 25,
        "stirrup_spacing": 150,
        "skin_bar_qty": 2,
        "skin_bar_name": "DB12",
        "skin_layers": 2,
        "grouping_mode": "Single frame",
        "selected_frame_single": "Manual",
        "selected_frames_group": [],
        "design_results_visible": False,
        "sap_raw_json": "",
    }
    for zone in ZONES:
        default_top, default_bottom = {"Left": (4, 2), "Mid": (2, 4), "Right": (4, 2)}[zone]
        state.update(
            {
                f"t1_{zone}": default_top,
                f"td1_{zone}": "DB25",
                f"t2_{zone}": 0,
                f"td2_{zone}": "DB20",
                f"t3_{zone}": 0,
                f"td3_{zone}": "DB20",
                f"b1_{zone}": default_bottom,
                f"bd1_{zone}": "DB25",
                f"b2_{zone}": 0,
                f"bd2_{zone}": "DB20",
                f"b3_{zone}": 0,
                f"bd3_{zone}": "DB20",
            }
        )
    return state

DEFAULT_APP_STATE = build_default_app_state()

def esc(value):
    return html.escape(str(value), quote=True)

def is_blank_excel_cell(value):
    try:
        return bool(pd.isna(value))
    except (TypeError, ValueError):
        return False

def state_options_for_key(key):
    if key == "input_mode":
        return ["Manual Input", "SAP2000 CSV Upload"]
    if key == "grouping_mode":
        return ["Single frame", "Grouped frames (envelope)"]
    if key == "lambda_c":
        return [1.0, 0.85, 0.75]
    if key == "bar_v_name":
        return list(STIRRUP_OPTIONS.keys())
    if key == "skin_bar_name":
        return list(SKIN_BAR_OPTIONS.keys())
    if key.startswith(("td", "bd")):
        return list(BAR_OPTIONS.keys())
    return None

def state_min_value_for_key(key):
    minimums = {
        "beam_length": 1.0,
        "b": 150,
        "h": 200,
        "fc": 20,
        "fy": 300,
        "fyt": 240,
        "n_legs": 2,
        "cover_clear": 20,
        "clear_space": 20,
        "skin_bar_qty": 0,
        "skin_layers": 1,
    }
    for zone in ZONES:
        minimums.update(
            {
                f"mu_{zone.lower()}": 0.0,
                f"vu_{zone.lower()}": 0.0,
                f"tu_{zone.lower()}": 0.0,
                f"t1_{zone}": 0,
                f"t2_{zone}": 0,
                f"t3_{zone}": 0,
                f"b1_{zone}": 0,
                f"b2_{zone}": 0,
                f"b3_{zone}": 0,
            }
        )
    return minimums.get(key)

def parse_editable_number(value):
    if isinstance(value, (int, float)) and not isinstance(value, bool):
        return float(value)
    text = str(value).strip().replace(",", "")
    match = re.search(r"[-+]?\d*\.?\d+(?:[eE][-+]?\d+)?", text)
    if not match:
        raise ValueError(f"Expected a number, got {value!r}")
    return float(match.group(0))

def normalize_option_value(key, value):
    options = state_options_for_key(key)
    if options is None:
        return value

    if key == "lambda_c":
        number = parse_editable_number(value)
        for option in options:
            if abs(float(option) - number) < 1e-9:
                return option
        raise ValueError(f"{key} must be one of {options}")

    text = str(value).strip()
    if key == "bar_v_name" or key == "skin_bar_name" or key.startswith(("td", "bd")):
        compact_text = re.sub(r"\s+", "", text).upper()
        for option in options:
            if compact_text == str(option).upper():
                return option
        diameter_match = re.search(r"\d+", compact_text)
        if diameter_match:
            diameter = int(diameter_match.group(0))
            for option in options:
                if int(re.search(r"\d+", str(option)).group(0)) == diameter:
                    return option
        raise ValueError(f"{key} must be one of {options}")

    aliases = {
        "manual": "Manual Input",
        "manual input": "Manual Input",
        "sap": "SAP2000 CSV Upload",
        "sap2000": "SAP2000 CSV Upload",
        "sap2000 csv": "SAP2000 CSV Upload",
        "sap2000 csv upload": "SAP2000 CSV Upload",
        "single": "Single frame",
        "single frame": "Single frame",
        "group": "Grouped frames (envelope)",
        "grouped": "Grouped frames (envelope)",
        "grouped frames": "Grouped frames (envelope)",
        "grouped frames (envelope)": "Grouped frames (envelope)",
    }
    lowered = text.lower()
    if lowered in aliases and aliases[lowered] in options:
        return aliases[lowered]
    for option in options:
        if text.lower() == str(option).lower():
            return option
    raise ValueError(f"{key} must be one of {options}")

def serialize_editable_value(value):
    if isinstance(value, list):
        return ", ".join(str(item) for item in value)
    if isinstance(value, bool):
        return "TRUE" if value else "FALSE"
    if value is None:
        return ""
    return value

def get_first_present(row, candidate_names):
    normalized = {
        str(column).strip().lower().replace(" ", "_"): column
        for column in row.index
    }
    for name in candidate_names:
        column = normalized.get(name.strip().lower().replace(" ", "_"))
        if column is not None:
            return row[column]
    return None

def coerce_workspace_value(key, value):
    default = DEFAULT_APP_STATE[key]
    if is_blank_excel_cell(value):
        return default
    if isinstance(value, str) and value.startswith("__json__:"):
        value = json.loads(value[len("__json__:") :])

    if isinstance(default, bool):
        if isinstance(value, bool):
            coerced = value
        else:
            text = str(value).strip().lower()
            if text in {"true", "yes", "y", "1"}:
                coerced = True
            elif text in {"false", "no", "n", "0"}:
                coerced = False
            else:
                raise ValueError(f"{key} must be TRUE or FALSE")
    elif isinstance(default, int) and not isinstance(default, bool):
        coerced = int(round(parse_editable_number(value)))
    elif isinstance(default, float):
        coerced = parse_editable_number(value)
    elif isinstance(default, list):
        if isinstance(value, list):
            coerced = [str(item).strip() for item in value if str(item).strip()]
        else:
            text = str(value).strip()
            if not text:
                coerced = []
            else:
                try:
                    decoded = json.loads(text)
                    if isinstance(decoded, list):
                        coerced = [str(item).strip() for item in decoded if str(item).strip()]
                    else:
                        coerced = [str(decoded).strip()] if str(decoded).strip() else []
                except json.JSONDecodeError:
                    coerced = [item.strip() for item in re.split(r"[,;]", text) if item.strip()]
    else:
        coerced = str(value).strip()

    minimum = state_min_value_for_key(key)
    if minimum is not None and isinstance(coerced, (int, float)) and coerced < minimum:
        raise ValueError(f"{key} must be at least {minimum}")
    return normalize_option_value(key, coerced)

PROJECT_INPUT_ROWS = [
    ("Section and Materials", "Width b (mm)", "b"),
    ("Section and Materials", "Total depth h (mm)", "h"),
    ("Section and Materials", "Concrete fc' (MPa)", "fc"),
    ("Section and Materials", "Main steel fy (MPa)", "fy"),
    ("Section and Materials", "Concrete type lambda", "lambda_c"),
    ("Transverse Steel", "Stirrup fy (MPa)", "fyt"),
    ("Transverse Steel", "Stirrup size", "bar_v_name"),
    ("Transverse Steel", "Stirrup legs", "n_legs"),
    ("Transverse Steel", "Clear cover to stirrup (mm)", "cover_clear"),
    ("Transverse Steel", "Minimum clear bar spacing (mm)", "clear_space"),
    ("Skin Bars", "Skin bars/layer", "skin_bar_qty"),
    ("Skin Bars", "Skin bar size", "skin_bar_name"),
    ("Skin Bars", "Skin layers", "skin_layers"),
]

def build_project_input_dataframe(export_state):
    rows = []
    for group, label, key in PROJECT_INPUT_ROWS:
        options = state_options_for_key(key)
        rows.append(
            {
                "group": group,
                "label": label,
                "key": key,
                "value": serialize_editable_value(export_state.get(key)),
                "allowed_values": ", ".join(str(option) for option in options) if options else "",
            }
        )
    return pd.DataFrame(rows)

def build_zone_reinforcement_dataframe(export_state):
    rows = []
    for zone in ZONES:
        rows.extend(
            [
                {
                    "zone": zone,
                    "face": "Top",
                    "layer": 1,
                    "quantity_key": f"t1_{zone}",
                    "quantity": export_state.get(f"t1_{zone}"),
                    "bar_size_key": f"td1_{zone}",
                    "bar_size": export_state.get(f"td1_{zone}"),
                },
                {
                    "zone": zone,
                    "face": "Top",
                    "layer": 2,
                    "quantity_key": f"t2_{zone}",
                    "quantity": export_state.get(f"t2_{zone}"),
                    "bar_size_key": f"td2_{zone}",
                    "bar_size": export_state.get(f"td2_{zone}"),
                },
                {
                    "zone": zone,
                    "face": "Top",
                    "layer": 3,
                    "quantity_key": f"t3_{zone}",
                    "quantity": export_state.get(f"t3_{zone}"),
                    "bar_size_key": f"td3_{zone}",
                    "bar_size": export_state.get(f"td3_{zone}"),
                },
                {
                    "zone": zone,
                    "face": "Bottom",
                    "layer": 1,
                    "quantity_key": f"b1_{zone}",
                    "quantity": export_state.get(f"b1_{zone}"),
                    "bar_size_key": f"bd1_{zone}",
                    "bar_size": export_state.get(f"bd1_{zone}"),
                },
                {
                    "zone": zone,
                    "face": "Bottom",
                    "layer": 2,
                    "quantity_key": f"b2_{zone}",
                    "quantity": export_state.get(f"b2_{zone}"),
                    "bar_size_key": f"bd2_{zone}",
                    "bar_size": export_state.get(f"bd2_{zone}"),
                },
                {
                    "zone": zone,
                    "face": "Bottom",
                    "layer": 3,
                    "quantity_key": f"b3_{zone}",
                    "quantity": export_state.get(f"b3_{zone}"),
                    "bar_size_key": f"bd3_{zone}",
                    "bar_size": export_state.get(f"bd3_{zone}"),
                },
            ]
        )
    return pd.DataFrame(rows)

def apply_project_input_dataframe(project_df):
    updates = {}
    if project_df.empty:
        return updates
        
    if "key" in project_df.columns and "value" in project_df.columns:
        for _, row in project_df.iterrows():
            key = str(row["key"]).strip()
            if key in DEFAULT_APP_STATE:
                updates[key] = coerce_workspace_value(key, row["value"])
        return updates

    if "label" in project_df.columns and "value" in project_df.columns:
        label_to_key = {
            label.strip().lower(): key
            for _, label, key in PROJECT_INPUT_ROWS
        }
        for _, row in project_df.iterrows():
            label = str(row["label"]).strip().lower()
            key = label_to_key.get(label)
            if key:
                updates[key] = coerce_workspace_value(key, row["value"])
    return updates

def apply_zone_reinforcement_dataframe(zone_df):
    updates = {}
    if zone_df.empty:
        return updates
        
    for _, row in zone_df.iterrows():
        qty_key = get_first_present(row, ["quantity_key"])
        qty_value = get_first_present(row, ["quantity", "qty", "number"])
        size_key = get_first_present(row, ["bar_size_key", "size_key"])
        size_value = get_first_present(row, ["bar_size", "size", "diameter"])

        if isinstance(qty_key, str) and qty_key.strip() in DEFAULT_APP_STATE and qty_value is not None:
            key = qty_key.strip()
            updates[key] = coerce_workspace_value(key, qty_value)
        if isinstance(size_key, str) and size_key.strip() in DEFAULT_APP_STATE and size_value is not None:
            key = size_key.strip()
            updates[key] = coerce_workspace_value(key, size_value)
            
    return updates

def build_app_state_dataframe(export_state, active_input_mode, active_beam_length, active_forces, force_meta, selected_frame_label):
    rows = [
        {
            "section": "active force source",
            "key": "active_force_source",
            "value": active_input_mode,
            "note": "Read-only helper row. The app imports input_mode below.",
        },
        {
            "section": "active force source",
            "key": "active_frame_or_group",
            "value": selected_frame_label,
            "note": "Read-only helper row.",
        },
        {
            "section": "active force source",
            "key": "active_beam_length_m",
            "value": round(float(active_beam_length), 6),
            "note": "Current design span from manual input or SAP stations.",
        },
    ]
    for zone in ZONES:
        zone_key = zone.lower()
        for label, short_key in [("Mu", "M"), ("Vu", "V"), ("Tu", "T")]:
            rows.append(
                {
                    "section": "active force source",
                    "key": f"active_{label.lower()}_{zone_key}",
                    "value": round(float(active_forces[zone][short_key]), 6),
                    "note": force_meta[zone][short_key],
                }
            )

    for key in DEFAULT_APP_STATE:
        if key == "input_mode":
            note = "Edit to Manual Input or SAP2000 CSV Upload."
        elif key in {"beam_length", "mu_left", "vu_left", "tu_left", "mu_mid", "vu_mid", "tu_mid", "mu_right", "vu_right", "tu_right"}:
            note = "Exported as the active design value. In SAP mode, edit sap_raw_data for SAP-derived forces."
        elif isinstance(DEFAULT_APP_STATE[key], list):
            note = "Use comma-separated values, for example B1, B2."
        else:
            note = ""
        rows.append(
            {
                "section": "editable app_state",
                "key": key,
                "value": serialize_editable_value(export_state.get(key)),
                "note": note,
            }
        )
    return pd.DataFrame(rows)

def build_workspace_excel_bytes(export_state, active_input_mode, active_beam_length, active_forces, force_meta, selected_frame_label, sap_raw_json, last_design_summary, last_design_zone_results):
    output = BytesIO()
    app_state_df = build_app_state_dataframe(
        export_state,
        active_input_mode,
        active_beam_length,
        active_forces,
        force_meta,
        selected_frame_label,
    )

    with pd.ExcelWriter(output, engine="openpyxl") as writer:
        app_state_df.to_excel(writer, sheet_name="app_state", index=False)
        build_project_input_dataframe(export_state).to_excel(writer, sheet_name="project_input_workspace", index=False)
        build_zone_reinforcement_dataframe(export_state).to_excel(writer, sheet_name="zone_reinforcement", index=False)

        if sap_raw_json:
            sap_df = pd.read_json(BytesIO(str(sap_raw_json).encode("utf-8")), orient="split")
            sap_df.to_excel(writer, sheet_name="sap_raw_data", index=False)

        if last_design_summary:
            pd.DataFrame(last_design_summary).to_excel(writer, sheet_name="design_summary", index=False)

        if last_design_zone_results:
            zone_rows = []
            for zone, data in last_design_zone_results.items():
                if data is None:
                    zone_rows.append({"Zone": zone, "Status": "Design aborted: bars do not fit"})
                else:
                    row = {"Zone": zone}
                    row.update(data)
                    zone_rows.append(row)
            pd.DataFrame(zone_rows).to_excel(writer, sheet_name="zone_results", index=False)

    return output.getvalue()

def load_workspace_excel(uploaded_excel_bytes):
    workbook = pd.ExcelFile(uploaded_excel_bytes)
    updates = {}
    sap_raw_json = ""
    
    if "app_state" not in workbook.sheet_names:
        if "project_input_workspace" not in workbook.sheet_names and "zone_reinforcement" not in workbook.sheet_names:
            raise ValueError("Missing app_state sheet")
    else:
        app_state = pd.read_excel(workbook, sheet_name="app_state")
        if app_state.empty:
            raise ValueError("app_state sheet is empty")

        if {"key", "value_json"}.issubset(app_state.columns):
            for _, row in app_state.iterrows():
                key = row["key"]
                if key in DEFAULT_APP_STATE:
                    updates[key] = coerce_workspace_value(key, json.loads(row["value_json"]))
        elif {"key", "value"}.issubset(app_state.columns):
            for _, row in app_state.iterrows():
                key = str(row["key"]).strip()
                if key in DEFAULT_APP_STATE:
                    updates[key] = coerce_workspace_value(key, row["value"])
        else:
            first_row = app_state.iloc[0].to_dict()
            for key in DEFAULT_APP_STATE:
                if key in first_row:
                    updates[key] = coerce_workspace_value(key, first_row[key])

    if "project_input_workspace" in workbook.sheet_names:
        proj_updates = apply_project_input_dataframe(pd.read_excel(workbook, sheet_name="project_input_workspace"))
        updates.update(proj_updates)
        
    if "zone_reinforcement" in workbook.sheet_names:
        zone_updates = apply_zone_reinforcement_dataframe(pd.read_excel(workbook, sheet_name="zone_reinforcement"))
        updates.update(zone_updates)

    if "sap_raw_data" in workbook.sheet_names:
        sap_df = pd.read_excel(workbook, sheet_name="sap_raw_data")
        sap_raw_json = sap_df.to_json(orient="split")

    return updates, sap_raw_json

def governing_value_and_combo(data, value_col, abs_col=None):
    if data is None or data.empty or value_col not in data.columns:
        return 0.0, "No data"
    target_col = abs_col or value_col
    if target_col == value_col:
        idx = data[target_col].abs().idxmax()
    else:
        idx = data[target_col].idxmax()
    value = abs(float(data.loc[idx, value_col]))
    combo = str(data.loc[idx, "OutputCase"]) if "OutputCase" in data.columns else "Manual"
    station = data.loc[idx, "Station"] if "Station" in data.columns else None
    combo_label = f"{combo} @ {station:.2f}m" if station is not None and pd.notna(station) else combo
    return value, combo_label

def safe_filename(value):
    cleaned = re.sub(r"[^A-Za-z0-9_.-]+", "_", str(value)).strip("_")
    return cleaned or "Manual"
