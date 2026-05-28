def generate_calculation_html(zone, app_state, forces, flex_res, shear_res, skin_res):
    b = app_state.get("b", 300)
    h = app_state.get("h", 600)
    fc = app_state.get("fc", 35)
    fy = app_state.get("fy", 500)
    fyt = app_state.get("fyt", 400)
    
    Mu = round(abs(forces["M"]), 1)
    Vu = round(abs(forces["V"]), 1)
    Tu = round(abs(forces["T"]), 1)

    html = f"<html><head><style>"
    html += "body { font-family: Arial, sans-serif; font-size: 14px; color: #e8eaf0; background-color: #1a1f2b; padding: 20px; }"
    html += "h2 { color: #fbbf24; border-bottom: 1px solid #4a5568; padding-bottom: 5px; }"
    html += "h3 { color: #60a5fa; margin-top: 20px; }"
    html += "p { line-height: 1.6; }"
    html += ".formula { background-color: #2a3044; padding: 10px; border-left: 4px solid #3b82f6; font-family: monospace; font-size: 13px; margin: 10px 0; }"
    html += ".ref { color: #9ca3af; font-size: 12px; font-style: italic; }"
    html += "</style></head><body>"

    html += f"<h2>Step-by-Step Calculations: {zone} Zone</h2>"
    
    # --- FLEXURE ---
    html += "<h3>1. Flexural Strength (M<sub>n</sub>)</h3>"
    html += f"<p><b>Given:</b> b = {b} mm, h = {h} mm, f'<sub>c</sub> = {fc} MPa, f<sub>y</sub> = {fy} MPa, M<sub>u</sub> = {Mu} kNm</p>"

    html += f"<p><b>1.1 Depth of equivalent rectangular stress block (a)</b> <span class='ref'>(ACI 318-19, 22.2.2.4.1)</span></p>"
    html += f"<div class='formula'>a = &beta;<sub>1</sub> &times; c<br>"
    html += f"&beta;<sub>1</sub> = {flex_res.get('beta1', 0.85)}<br>"
    html += f"a = {flex_res.get('beta1', 0.85)} &times; {flex_res['c']} = {flex_res['a']} mm</div>"

    html += f"<p><b>1.2 Concrete Compression Force (C<sub>c</sub>)</b> <span class='ref'>(ACI 318-19, 22.2.2.4.1)</span></p>"
    html += f"<div class='formula'>C<sub>c</sub> = 0.85 &times; f'<sub>c</sub> &times; a &times; b<br>"
    html += f"C<sub>c</sub> = 0.85 &times; {fc} &times; {flex_res['a']} &times; {b} &times; 10<sup>-3</sup> = {flex_res.get('Cc', 0)} kN</div>"

    html += f"<p><b>1.3 Nominal Moment Capacity (M<sub>n</sub>)</b></p>"
    html += f"<div class='formula'>M<sub>n</sub> = C<sub>c</sub>(d - a/2) + C<sub>s</sub>(d - d')<br>"
    html += f"M<sub>n</sub> = {flex_res['Mn']} kNm</div>"

    html += f"<p><b>1.4 Design Moment Capacity (&phi;M<sub>n</sub>)</b> <span class='ref'>(ACI 318-19, 21.2.1)</span></p>"
    html += f"<div class='formula'>&phi; = {flex_res['phi']} (Strain class: {flex_res['strain_class']}, &epsilon;<sub>t</sub> = {flex_res['eps_t']})<br>"
    html += f"&phi;M<sub>n</sub> = {flex_res['phi']} &times; {flex_res['Mn']} = {flex_res['phi_Mn']} kNm</div>"
    html += f"<p><b>Check:</b> &phi;M<sub>n</sub> = {flex_res['phi_Mn']} kNm &ge; M<sub>u</sub> = {Mu} kNm &rarr; <b>{'OK' if flex_res['phi_Mn'] >= Mu else 'NG'}</b></p>"

    # --- SHEAR ---
    html += "<h3>2. Shear Strength (V<sub>n</sub>)</h3>"
    html += f"<p><b>Given:</b> V<sub>u</sub> = {Vu} kN</p>"

    html += f"<p><b>2.1 Concrete Shear Capacity (V<sub>c</sub>)</b> <span class='ref'>(ACI 318-19, Eq. 22.5.5.1)</span></p>"
    html += f"<div class='formula'>V<sub>c</sub> = 0.17 &times; &lambda; &times; &radic;f'<sub>c</sub> &times; b<sub>w</sub> &times; d<br>"
    html += f"V<sub>c</sub> = {shear_res.get('Vc', 0)} kN<br>"
    html += f"&phi;V<sub>c</sub> = 0.75 &times; {shear_res.get('Vc', 0)} = {shear_res['phi_Vc']} kN</div>"

    html += f"<p><b>2.2 Steel Shear Capacity (V<sub>s</sub>)</b> <span class='ref'>(ACI 318-19, Eq. 22.5.10.5.3)</span></p>"
    html += f"<div class='formula'>V<sub>s</sub> = A<sub>v</sub> &times; f<sub>yt</sub> &times; d / s<br>"
    html += f"V<sub>s,provided</sub> = {shear_res.get('Vs_prov', 0)} kN (using s = {shear_res['final_s']} mm)</div>"
    
    html += f"<p><b>2.3 Design Shear Capacity (&phi;V<sub>n</sub>)</b> <span class='ref'>(ACI 318-19, Eq. 22.5.1.1)</span></p>"
    html += f"<div class='formula'>&phi;V<sub>n</sub> = &phi;(V<sub>c</sub> + V<sub>s</sub>)<br>"
    html += f"&phi;V<sub>n</sub> = 0.75 &times; ({shear_res.get('Vc', 0)} + {shear_res.get('Vs_prov', 0)}) = {shear_res['phi_Vn']} kN</div>"
    html += f"<p><b>Check:</b> &phi;V<sub>n</sub> = {shear_res['phi_Vn']} kN &ge; V<sub>u</sub> = {Vu} kN &rarr; <b>{'OK' if shear_res['phi_Vn'] >= Vu else 'NG'}</b></p>"

    # --- TORSION ---
    html += "<h3>3. Torsion (T<sub>u</sub>)</h3>"
    html += f"<p><b>Given:</b> T<sub>u</sub> = {Tu} kNm</p>"
    html += f"<p><b>3.1 Torsion Threshold (T<sub>th</sub>)</b> <span class='ref'>(ACI 318-19, 22.7.4.1)</span></p>"
    html += f"<div class='formula'>T<sub>th</sub> = &phi; &times; 0.083 &times; &lambda; &times; &radic;f'<sub>c</sub> &times; (A<sub>cp</sub><sup>2</sup> / p<sub>cp</sub>)<br>"
    html += f"T<sub>th</sub> = {shear_res['T_th']} kNm</div>"
    if shear_res['needs_torsion']:
        html += f"<p><b>Check:</b> T<sub>u</sub> = {Tu} kNm > T<sub>th</sub> = {shear_res['T_th']} kNm &rarr; <b>Torsion reinforcement required</b></p>"
        html += f"<p><b>3.2 Transverse Torsional Reinforcement (A<sub>t</sub>/s)</b> <span class='ref'>(ACI 318-19, Eq. 22.7.6.1a)</span></p>"
        html += f"<div class='formula'>T<sub>n</sub> = 2 &times; A<sub>o</sub> &times; A<sub>t</sub> &times; f<sub>yt</sub> / s<br>"
        html += f"A<sub>o</sub> = {shear_res['Ao']:.0f} mm<sup>2</sup></div>"
        html += f"<p><b>3.3 Longitudinal Torsional Reinforcement (A<sub>l</sub>)</b> <span class='ref'>(ACI 318-19, Eq. 22.7.6.1b)</span></p>"
        html += f"<div class='formula'>A<sub>l,req</sub> = {shear_res['Al_req']} mm<sup>2</sup><br>"
        html += f"A<sub>l,min</sub> = {shear_res['Al_min']} mm<sup>2</sup></div>"
    else:
        html += f"<p><b>Check:</b> T<sub>u</sub> = {Tu} kNm &le; T<sub>th</sub> = {shear_res['T_th']} kNm &rarr; <b>Torsion reinforcement NOT required</b></p>"

    html += "</body></html>"
    return html
