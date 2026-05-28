import math
from dataclasses import dataclass

RESULTS_FONT_SCALE = 1.25
ZONES = ["Left", "Mid", "Right"]
BAR_OPTIONS = {"DB12": 12, "DB16": 16, "DB20": 20, "DB25": 25, "DB28": 28, "DB32": 32}
STIRRUP_OPTIONS = {"RB9": 9, "DB10": 10, "DB12": 12, "DB16": 16}
SKIN_BAR_OPTIONS = {"DB10": 10, "DB12": 12, "DB16": 16, "DB20": 20}

@dataclass
class RebarGroup:
    area: float
    centroid: float
    extreme_fiber: float
    width_req: float
    layers: list


def get_rebar_group(n1, dia1, n2, dia2, n3, dia3, cover_clear, tie_dia, clear_space_input=25):
    if (n1 + n2 + n3) == 0:
        return RebarGroup(0.0, 0.0, 0.0, 0.0, [])

    max_dia = max(dia1 if n1 > 0 else 0, dia2 if n2 > 0 else 0, dia3 if n3 > 0 else 0)
    eff_clear_space = max(clear_space_input, 25, max_dia)
    widths = [
        2 * (cover_clear + tie_dia) + n * dia + (n - 1) * eff_clear_space
        for n, dia in [(n1, dia1), (n2, dia2), (n3, dia3)]
        if n > 0
    ]

    layers = []
    areas = []
    ys = []
    prev_y = None
    prev_dia = None
    for n, dia in [(n1, dia1), (n2, dia2), (n3, dia3)]:
        area = n * math.pi * dia**2 / 4 if n > 0 else 0
        if n > 0:
            if prev_y is None:
                y = cover_clear + tie_dia + dia / 2
            else:
                y = prev_y + prev_dia / 2 + eff_clear_space + dia / 2
            layers.append((n, dia, y))
            prev_y, prev_dia = y, dia
        else:
            y = 0
        areas.append(area)
        ys.append(y)

    total_area = sum(areas)
    y_centroid = sum(a * y for a, y in zip(areas, ys)) / total_area if total_area else 0
    y_extreme = layers[0][2] if layers else 0
    return RebarGroup(total_area, y_centroid, y_extreme, max(widths) if widths else 0, layers)


def calculate_beam_flexure(b, h, d, dt, d_prime, fc, fy, As, As_prime):
    if As <= 0 or d <= 0:
        return {
            "phi_Mn": 0,
            "passes_As_min": False,
            "is_ductile": False,
            "converged": False,
            "As_min": 0,
            "As_max_tc": 0,
            "passes_As_max_tc": False,
            "strain_class": "N/A",
            "c": 0,
            "a": 0,
            "eps_t": 0,
            "phi": 0,
            "Mn": 0,
        }

    Es = 200000
    ecu = 0.003
    eps_y = fy / Es
    tension_control_limit = eps_y + 0.003
    beta1 = 0.85 if fc <= 28 else max(0.65, 0.85 - 0.05 * ((fc - 28) / 7))
    As_min = max((0.25 * math.sqrt(fc) / fy) * b * d, (1.4 / fy) * b * d)
    rho_max_tc = 0.85 * beta1 * (fc / fy) * (ecu / (ecu + tension_control_limit))
    As_max_tc = rho_max_tc * b * d

    def section_state(c):
        c = max(c, 1e-6)
        a = min(beta1 * c, h)
        Cc = 0.85 * fc * a * b

        eps_s_prime = ecu * (c - d_prime) / c
        fs_prime = min(fy, max(-fy, eps_s_prime * Es))
        Cs = As_prime * fs_prime
        if d_prime <= a and eps_s_prime > 0:
            Cs -= As_prime * 0.85 * fc

        eps_s = ecu * (d - c) / c
        fs = min(fy, max(-fy, eps_s * Es))
        T = As * fs
        balance = Cc + Cs - T
        Mn_kNm = max((Cc * (d - a / 2) + Cs * (d - d_prime)) / 1_000_000, 0)
        return balance, a, Cc, Cs, T, Mn_kNm

    lo = 1e-6
    hi = max(h, d, d_prime, 1.0) * 2
    f_lo = section_state(lo)[0]
    f_hi = section_state(hi)[0]
    converged = f_lo <= 0 <= f_hi

    if converged:
        c = hi
        for _ in range(80):
            c = 0.5 * (lo + hi)
            f_mid = section_state(c)[0]
            if abs(f_mid) < 1e-3:
                break
            if f_mid > 0:
                hi = c
            else:
                lo = c
    else:
        c = max(min(d, h), 1.0)
        for test_c in [max(d, h) - i * 0.5 for i in range(int(max(d, h) * 2))]:
            if test_c <= 1:
                break
            if section_state(test_c)[0] <= 0:
                c = test_c
                converged = True
                break

    _, a, Cc, Cs, T, Mn_kNm = section_state(c)
    eps_t = ecu * (dt - c) / c if c > 0 else 0
    if eps_t <= eps_y:
        phi = 0.65
        strain_class = "Compression-controlled"
    elif eps_t >= tension_control_limit:
        phi = 0.90
        strain_class = "Tension-controlled"
    else:
        phi = 0.65 + 0.25 * ((eps_t - eps_y) / 0.003)
        strain_class = "Transition zone"

    return {
        "phi_Mn": round(phi * Mn_kNm, 1),
        "is_ductile": eps_t >= tension_control_limit,
        "As_min": round(As_min, 1),
        "passes_As_min": As >= As_min,
        "As_max_tc": round(As_max_tc, 1),
        "passes_As_max_tc": As <= As_max_tc,
        "strain_class": strain_class,
        "converged": converged,
        "c": round(c, 2),
        "a": round(a, 2),
        "eps_t": round(eps_t, 5),
        "phi": round(phi, 3),
        "Mn": round(Mn_kNm, 1),
        "beta1": round(beta1, 3),
        "Cc": round(Cc / 1000, 1), # converted to kN
        "Cs": round(Cs / 1000, 1), # converted to kN
        "T": round(T / 1000, 1), # converted to kN
    }


def calculate_shear_torsion(b, h, d, fc, fyt, fyl, cover_clear, Vu_kN, Tu_kNm, n_legs, bar_dia, lambda_c, stirrup_spacing=None):
    if d <= 0:
        return {
            "final_s": 0,
            "section_fails": True,
            "needs_torsion": False,
            "Al_req": 0,
            "Al_min": 0,
            "T_th": 0,
            "phi_Vc": 0,
            "phi_Vn": 0,
            "lambda_s": 0,
            "s_calc": 0,
            "s_exact": 0,
            "s_max": 0,
            "combined_stress": 0,
            "stress_limit": 0,
            "Aoh": 0,
            "Ao": 0,
            "ph": 0,
            "spacing_ok": False,
        }

    phi_v = 0.75
    Vu = abs(Vu_kN) * 1000
    Tu = abs(Tu_kNm) * 1_000_000
    A_leg = math.pi * bar_dia**2 / 4
    lambda_s = min(1.0, math.sqrt(2 / (1 + 0.004 * d)))
    Vc = 0.17 * lambda_c * math.sqrt(fc) * b * d
    phi_Vc = phi_v * Vc

    x1 = max(1, b - 2 * (cover_clear + bar_dia / 2))
    y1 = max(1, h - 2 * (cover_clear + bar_dia / 2))
    Aoh = x1 * y1
    Ao = 0.85 * Aoh
    ph = 2 * (x1 + y1)
    Acp = b * h
    pcp = 2 * (b + h)
    T_th = phi_v * 0.083 * lambda_c * math.sqrt(fc) * (Acp**2 / pcp)
    needs_torsion = Tu > T_th

    Vs_req = max((Vu / phi_v) - Vc, 0) if Vu > phi_Vc / 2 else 0
    Av_s_req = Vs_req / (fyt * d) if Vs_req > 0 else 0

    if needs_torsion:
        At_s_req = (Tu / phi_v) / (2 * Ao * fyt)
        At_s_for_min = max(At_s_req, 0.175 * b / fyt)
        Al_min = max(0, (0.42 * math.sqrt(fc) * Acp / fyl) - (At_s_for_min * ph * (fyt / fyl)))
        Al_req = max(At_s_req * ph * (fyt / fyl), Al_min)
    else:
        At_s_req = 0
        Al_req = 0
        Al_min = 0

    req_per_outer_leg = (Av_s_req / max(n_legs, 1)) + At_s_req
    s_calc = A_leg / req_per_outer_leg if req_per_outer_leg > 0 else 9999
    min_combined_ratio = max(0.062 * math.sqrt(fc) * b / fyt, 0.35 * b / fyt)
    s_min_steel = (n_legs * A_leg) / min_combined_ratio
    s_req = min(s_calc, s_min_steel)
    s_max_shear = min(d / 4, 300) if Vs_req > (0.33 * math.sqrt(fc) * b * d) else min(d / 2, 600)
    s_max = min(s_max_shear, ph / 8, 300) if needs_torsion else s_max_shear
    s_exact = min(s_req, s_max)
    auto_s = math.floor(s_exact / 25) * 25
    final_s = float(stirrup_spacing) if stirrup_spacing else auto_s

    Vs_prov = (n_legs * A_leg * fyt * d / final_s) if final_s > 0 else 0
    phi_Vn = phi_v * (Vc + Vs_prov)
    v_stress = Vu / (b * d)
    t_stress = (Tu * ph) / (1.7 * Aoh**2) if needs_torsion else 0
    combined_stress = math.sqrt(v_stress**2 + t_stress**2)
    stress_limit = phi_v * ((Vc / (b * d)) + 0.66 * math.sqrt(fc))
    section_fails = combined_stress > stress_limit
    spacing_ok = 50 <= final_s <= s_max

    return {
        "final_s": round(final_s, 1),
        "section_fails": section_fails,
        "needs_torsion": needs_torsion,
        "Al_req": round(Al_req, 1),
        "Al_min": round(Al_min, 1),
        "T_th": round(T_th / 1_000_000, 1),
        "phi_Vc": round(phi_Vc / 1000, 1),
        "phi_Vn": round(phi_Vn / 1000, 1),
        "lambda_s": round(lambda_s, 3),
        "s_calc": round(s_calc, 1),
        "s_exact": round(s_exact, 1),
        "s_max": round(s_max, 1),
        "combined_stress": round(combined_stress, 2),
        "stress_limit": round(stress_limit, 2),
        "Aoh": Aoh,
        "Ao": Ao,
        "ph": ph,
        "spacing_ok": spacing_ok,
        "Vc": round(Vc / 1000, 1),
        "Vs_prov": round(Vs_prov / 1000, 1),
    }


def calculate_development_length(db, fy, fc, is_top_bar, cover_clear, clear_spacing, lambda_c):
    if db == 0:
        return {"ld": 0, "lap": 0, "ldh": 0}
    psi_t = 1.3 if is_top_bar else 1.0
    psi_e = 1.0
    psi_s = 0.8 if db <= 20 else 1.0
    psi_g = 1.0 if fy <= 420 else 1.15
    cb = min(cover_clear + db / 2, clear_spacing / 2 + db / 2)
    conf_term = min(cb / db, 2.5)
    ld_calc = (fy / (1.1 * lambda_c * math.sqrt(fc))) * ((psi_t * psi_e * psi_s * psi_g) / conf_term) * db
    ld = max(ld_calc, 300)
    lap_splice = max(1.3 * ld, 300)
    ldh_calc = max(((fy * psi_e * psi_t * psi_g) / (23 * lambda_c * math.sqrt(fc))) * db**1.5, 8 * db, 150)
    return {
        "ld": math.ceil(ld / 50) * 50,
        "lap": math.ceil(lap_splice / 50) * 50,
        "ldh": math.ceil(ldh_calc / 50) * 50,
    }


def calculate_skin_reinforcement(h, d, skin_bar_dia, skin_bar_qty, skin_layers):
    required = h > 900
    s_limit = min(d / 6, 300) if d > 0 else 300
    zone_height = h / 2
    bar_area = math.pi * skin_bar_dia**2 / 4
    provided_layers = max(1, int(skin_layers))
    bars_per_layer = max(0, int(skin_bar_qty))

    if provided_layers > 1:
        available_height = max(0, zone_height - 100)
        spacing = available_height / (provided_layers - 1)
    else:
        spacing = zone_height

    total_bars = bars_per_layer * provided_layers
    quantity_ok = bars_per_layer >= 2 and total_bars > 0
    spacing_ok = (not required) or (quantity_ok and spacing <= s_limit)
    area_total = total_bars * bar_area
    return {
        "required": required,
        "s_limit": round(s_limit, 1),
        "bars_per_side": total_bars / 2,
        "bars_per_layer": bars_per_layer,
        "layers": provided_layers,
        "spacing": round(spacing, 1),
        "spacing_ok": spacing_ok,
        "quantity_ok": quantity_ok,
        "area_per_side": round(area_total / 2, 1),
        "area_total": round(area_total, 1),
        "zone_height": round(zone_height, 1),
    }
