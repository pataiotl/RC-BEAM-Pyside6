from fpdf import FPDF
from beam_engine import ZONES

def create_pdf_report(groups, input_mode):
    def to_float(value):
        try:
            return float(value)
        except (TypeError, ValueError):
            return None

    def status(dc_value):
        dc_numeric = to_float(dc_value)
        if dc_numeric is None:
            return "N/A"
        return "OK" if dc_numeric <= 1.0 else "NG"

    def wrap_text(text, width, font_size=9):
        pdf.set_font("Arial", "", font_size)
        words = str(text).split()
        if not words:
            return [""]

        lines = []
        current_line = words[0]
        for word in words[1:]:
            candidate = f"{current_line} {word}"
            if pdf.get_string_width(candidate) <= (width - 2):
                current_line = candidate
            else:
                lines.append(current_line)
                current_line = word
        lines.append(current_line)
        return lines

    def table_row(col1, col2, col3, col4):
        col_widths = [28, 52, 72, 28]
        values = [str(col1), str(col2), str(col3), str(col4)]
        wrapped_cells = [wrap_text(v, w) for v, w in zip(values, col_widths)]
        max_lines = max(len(lines) for lines in wrapped_cells)
        line_h = 4.2
        row_h = max_lines * line_h + 1
        x0 = pdf.get_x()
        y0 = pdf.get_y()

        pdf.set_font("Arial", "", 8)
        for idx, (width, lines) in enumerate(zip(col_widths, wrapped_cells)):
            x_cell = x0 + sum(col_widths[:idx])
            pdf.rect(x_cell, y0, width, row_h)
            text_y = y0 + 0.5
            for line in lines:
                pdf.set_xy(x_cell + 1, text_y)
                pdf.cell(width - 2, line_h, line, border=0)
                text_y += line_h
        pdf.set_xy(x0, y0 + row_h)

    def subheading(text):
        pdf.set_font("Arial", "B", 9)
        pdf.set_fill_color(233, 238, 248)
        pdf.cell(0, 6, text, ln=True, fill=True)

    pdf = FPDF(orientation="P", unit="mm", format="A4")
    pdf.set_margins(15, 15, 15)
    pdf.set_auto_page_break(auto=True, margin=15)
    
    for grp in groups:
        b = grp.get("b", 0)
        h = grp.get("h", 0)
        fc = grp.get("fc", 0)
        fy = grp.get("fy", 0)
        fyt = grp.get("fyt", 0)
        frame_name = grp.get("group_name", "Unnamed")
        zone_data = grp.get("zone_data", {})
        
        pdf.add_page()
        pdf.set_text_color(0, 0, 0)

        pdf.set_font("Arial", "B", 13)
        pdf.cell(0, 6, "REINFORCED CONCRETE BEAM", ln=True, align="C")
        pdf.cell(0, 6, "CALCULATION REPORT", ln=True, align="C")
        pdf.ln(1)
        pdf.set_draw_color(80, 80, 80)
        pdf.line(15, pdf.get_y(), 195, pdf.get_y())
        pdf.ln(2)

        subheading("Project / Member Information")
        pdf.set_font("Arial", "", 8)
        pdf.cell(45, 5, "Frame / Beam ID", border=1)
        pdf.cell(45, 5, str(frame_name), border=1)
        pdf.cell(45, 5, "Design Code", border=1)
        pdf.cell(45, 5, "ACI 318-19", border=1, ln=True)
        pdf.cell(45, 5, "Input Source", border=1)
        pdf.cell(45, 5, str(input_mode), border=1)
        pdf.cell(45, 5, "Section Size", border=1)
        pdf.cell(45, 5, f"{b} mm x {h} mm", border=1, ln=True)
        pdf.cell(45, 5, "Concrete Strength (fc')", border=1)
        pdf.cell(45, 5, f"{fc} MPa", border=1)
        pdf.cell(45, 5, "Steel Yield (fy / fyt)", border=1)
        pdf.cell(45, 5, f"{fy} / {fyt} MPa", border=1, ln=True)
        pdf.ln(2)

        subheading("Design Results by Zone")
        for zone in ZONES:
            data = zone_data.get(zone)
            pdf.set_font("Arial", "B", 9)
            pdf.set_fill_color(245, 245, 245)
            pdf.cell(0, 6, f"{zone.upper()} ZONE", ln=True, border=1, fill=True)

            if not data:
                pdf.set_font("Arial", "B", 8)
                pdf.cell(0, 6, "DESIGN ABORTED: reinforcement layers do not fit within the section width.", border=1, ln=True, align="C")
                pdf.ln(1)
                continue

            pdf.set_font("Arial", "B", 8)
            pdf.cell(28, 5, "Check Item", border=1)
            pdf.cell(52, 5, "Demand", border=1)
            pdf.cell(72, 5, "Capacity / Details", border=1)
            pdf.cell(28, 5, "Result", border=1, ln=True)

            table_row("Flexure", f"Mu = {data['Mu']} kNm ({data['M_combo']})", f"phiMn = {data['phi_Mn']} kNm | D/C = {data['DC_flex']}", status(data["DC_flex"]))
            table_row("Shear", f"Vu = {data['Vu']} kN ({data['V_combo']})", f"phiVn = {data['phi_Vn']} kN | D/C = {data['DC_shear']}", status(data["DC_shear"]))
            table_row("Torsion", f"Tu = {data['Tu']} kNm ({data['T_combo']})", f"Status: {data['torsion_status']} | Al req = {data['Al_req']} mm2", "CHECK")
            table_row("Skin Reinforcement", f"Skin Al = {data['skin_Al']} mm2", f"Bars: {data['skin_detail']}", "PROVIDED")

            pdf.set_font("Arial", "B", 8)
            pdf.cell(0, 5, "Detailing / Serviceability", border=1, ln=True)
            pdf.set_font("Arial", "", 8)
            pdf.multi_cell(
                0,
                4,
                (
                    f"- Stirrups: {data['stirrups']}\n"
                    f"- Strain data: eps_t = {data['eps_t']}, phi = {data['phi']}, class = {data['strain_class']}\n"
                    f"- Development / lap lengths: top hook = {data['dev_top']} mm, "
                    f"top lap = {data['dev_top_lap']} mm, bottom lap = {data['dev_bot']} mm"
                ),
                border=1,
            )
            pdf.ln(1)

        pdf.set_font("Arial", "I", 7)
        pdf.set_text_color(90, 90, 90)
        pdf.multi_cell(
            0,
            3,
            "Note: This report summarizes governing strength and detailing checks from the design workspace. "
            "Final engineering approval and project-specific compliance remain the responsibility of the designer.",
        )

    output = pdf.output(dest="S")
    return bytes(output) if isinstance(output, (bytes, bytearray)) else output.encode("latin-1")
