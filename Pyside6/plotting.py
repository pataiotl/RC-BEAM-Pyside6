import math
import pandas as pd
import matplotlib.pyplot as plt
import matplotlib.patches as patches
import matplotlib.ticker as mticker

def draw_beam_section(b, h, cover, tie_dia, top_rg, bot_rg, flex, zone, skin=None, skin_bar_dia=10, compression_face="top"):
    fig, ax = plt.subplots(figsize=(1.35, 1.15), dpi=160)
    fig.patch.set_facecolor("#0f1117")
    ax.set_facecolor("#0f1117")
    ax.set_aspect("equal")
    ax.axis("off")

    pad = max(b, h) * 0.18
    ax.set_xlim(-pad, b + pad * 1.65)
    ax.set_ylim(h + pad * 0.78, -pad)

    ax.add_patch(patches.Rectangle((0, 0), b, h, facecolor="#1e2330", edgecolor="#4f8ef7", lw=1.2))
    ax.add_patch(
        patches.Rectangle(
            (cover + tie_dia / 2, cover + tie_dia / 2),
            b - 2 * (cover + tie_dia / 2),
            h - 2 * (cover + tie_dia / 2),
            fill=False,
            edgecolor="#c084fc",
            lw=1.1,
        )
    )
    ax.add_patch(
        patches.Rectangle(
            (cover, cover),
            b - 2 * cover,
            h - 2 * cover,
            fill=False,
            edgecolor="#7a84a0",
            lw=0.8,
        )
    )

    a = max(0, min(h, flex.get("a", 0)))
    c = max(0, min(h, flex.get("c", 0)))
    if compression_face == "top":
        ax.add_patch(patches.Rectangle((0, 0), b, a, facecolor="#4f8ef7", alpha=0.20, edgecolor="none"))
        c_y = c
        a_label_y = max(12, a / 2)
    else:
        ax.add_patch(patches.Rectangle((0, h - a), b, a, facecolor="#4f8ef7", alpha=0.20, edgecolor="none"))
        c_y = h - c
        a_label_y = min(h - 12, h - a / 2)
    ax.plot([-pad * 0.18, b + pad * 0.18], [c_y, c_y], color="#f87171", lw=0.8, ls=(0, (4, 3)))
    ax.text(b + pad * 0.25, a_label_y, f"a={flex.get('a', 0):.0f}", color="#93c5fd", fontsize=4.6)
    ax.text(b + pad * 0.25, c_y, f"c={flex.get('c', 0):.0f}", color="#f87171", fontsize=4.6, va="center")

    def plot_layers(group, from_top=True):
        for n, dia, y_from_face in group.layers:
            y = y_from_face if from_top else h - y_from_face
            usable = b - 2 * (cover + tie_dia + dia / 2)
            x0 = cover + tie_dia + dia / 2
            xs = [b / 2] if n == 1 else [x0 + i * usable / (n - 1) for i in range(n)]
            for x in xs:
                ax.add_patch(patches.Circle((x, y), max(dia / 2, 4), facecolor="#fbbf24", edgecolor="#92400e", lw=0.5))

    plot_layers(top_rg, True)
    plot_layers(bot_rg, False)

    corner_offset = cover + tie_dia + 10
    for x, y in [
        (corner_offset, corner_offset),
        (b - corner_offset, corner_offset),
        (corner_offset, h - corner_offset),
        (b - corner_offset, h - corner_offset),
    ]:
        ax.add_patch(patches.Circle((x, y), 5, facecolor="#c084fc", edgecolor="#5b21b6", lw=0.5))

    if skin and skin["bars_per_layer"] > 0:
        if skin["layers"] == 1:
            y_vals = [h / 2]
        else:
            total_height = skin["spacing"] * (skin["layers"] - 1)
            y_top = h / 2 - total_height / 2
            y_vals = [y_top + i * skin["spacing"] for i in range(skin["layers"])]

        def offsets(count):
            if count <= 0:
                return []
            if count == 1:
                return [0]
            return [(i - (count - 1) / 2) * (skin_bar_dia * 0.75) for i in range(count)]

        left_count = math.ceil(skin["bars_per_layer"] / 2)
        right_count = skin["bars_per_layer"] // 2
        left_base = cover + tie_dia + skin_bar_dia / 2
        right_base = b - cover - tie_dia - skin_bar_dia / 2
        for y in y_vals:
            for offset in offsets(left_count):
                ax.add_patch(patches.Circle((left_base + offset, y), max(skin_bar_dia / 2, 3.5), facecolor="#38bdf8", edgecolor="#164e63", lw=0.45))
            for offset in offsets(right_count):
                ax.add_patch(patches.Circle((right_base - offset, y), max(skin_bar_dia / 2, 3.5), facecolor="#38bdf8", edgecolor="#164e63", lw=0.45))

    ax.annotate("", xy=(0, h + pad * 0.25), xytext=(b, h + pad * 0.25), arrowprops=dict(arrowstyle="<->", color="#7a84a0", lw=0.55))
    ax.text(b / 2, h + pad * 0.34, f"b={b:.0f}", color="#e8eaf0", ha="center", fontsize=4.6)
    ax.annotate("", xy=(b + pad * 0.55, 0), xytext=(b + pad * 0.55, h), arrowprops=dict(arrowstyle="<->", color="#7a84a0", lw=0.55))
    ax.text(b + pad * 0.66, h / 2, f"h={h:.0f}", color="#e8eaf0", va="center", fontsize=4.8)
    ax.text(0, -pad * 0.18, zone, color="#98a2b8", fontsize=5.4, weight="bold")
    return fig


def draw_force_diagrams(forces, beam_length, df=None, selected_frame="Manual"):
    fig, (ax_m, ax_v) = plt.subplots(2, 1, figsize=(3.15, 1.55), dpi=180, sharex=True)
    fig.patch.set_facecolor("#0f1117")
    for ax in (ax_m, ax_v):
        ax.set_facecolor("#181c24")
        ax.grid(True, color="#364060", alpha=0.36, linestyle="--", linewidth=0.28)
        ax.axhline(0, color="#e8eaf0", linewidth=0.45, alpha=0.75)
        ax.tick_params(colors="#98a2b8", labelsize=4.0, length=2, pad=1)
        ax.yaxis.set_major_locator(mticker.MaxNLocator(3))
        ax.xaxis.set_major_locator(mticker.MaxNLocator(5))
        for spine in ax.spines.values():
            spine.set_color("#2a3044")

    if df is not None and not df.empty and {"Station", "M3", "V2"}.issubset(df.columns):
        df_env = (
            df.groupby("Station")
            .agg(M3_Max=("M3", "max"), M3_Min=("M3", "min"), V2_Max=("V2", "max"), V2_Min=("V2", "min"))
            .reset_index()
            .sort_values("Station")
        )
        x = df_env["Station"]
        ax_m.plot(x, df_env["M3_Max"], color="#4f8ef7", linewidth=0.75, label="+M")
        ax_m.plot(x, df_env["M3_Min"], color="#f87171", linewidth=0.75, label="-M")
        ax_m.fill_between(x, df_env["M3_Min"], df_env["M3_Max"], color="#7a84a0", alpha=0.18)
        ax_v.plot(x, df_env["V2_Max"], color="#22c55e", linewidth=0.75, label="+V")
        ax_v.plot(x, df_env["V2_Min"], color="#fbbf24", linewidth=0.75, label="-V")
        ax_v.fill_between(x, df_env["V2_Min"], df_env["V2_Max"], color="#22c55e", alpha=0.12)
        title = f"Frame {selected_frame} - SAP2000 Envelope"
    else:
        L = max(float(beam_length or 0), 1.0)
        x = [0, 0.5 * L, L]
        m = [-abs(forces["Left"]["M"]), abs(forces["Mid"]["M"]), -abs(forces["Right"]["M"])]
        v = [abs(forces["Left"]["V"]), 0, -abs(forces["Right"]["V"])]
        ax_m.plot(x, m, color="#4f8ef7", linewidth=0.9, marker="o", markersize=2.2, label="M")
        ax_m.fill_between(x, m, 0, color="#4f8ef7", alpha=0.13)
        ax_v.plot(x, v, color="#22c55e", linewidth=0.9, marker="o", markersize=2.2, label="V")
        ax_v.fill_between(x, v, 0, color="#22c55e", alpha=0.13)
        ax_m.annotate(f"i -{abs(forces['Left']['M']):.0f}", (x[0], m[0]), color="#f87171", fontsize=4.8, xytext=(2, -7), textcoords="offset points")
        ax_m.annotate(f"mid +{abs(forces['Mid']['M']):.0f}", (x[1], m[1]), color="#4f8ef7", fontsize=4.8, xytext=(2, 4), textcoords="offset points")
        ax_m.annotate(f"j -{abs(forces['Right']['M']):.0f}", (x[2], m[2]), color="#f87171", fontsize=4.8, xytext=(-23, -7), textcoords="offset points")
        title = "Manual Design Demands"

    ax_m.set_title(title, color="#e8eaf0", fontsize=4.6, fontweight="bold", pad=2)
    ax_m.set_ylabel("M", color="#98a2b8", fontsize=4.2, labelpad=1)
    ax_v.set_ylabel("V", color="#98a2b8", fontsize=4.2, labelpad=1)
    ax_v.set_xlabel("Station (m)", color="#98a2b8", fontsize=4.2, labelpad=1)
    for ax in (ax_m, ax_v):
        ax.legend(
            facecolor="#181c24",
            edgecolor="#2a3044",
            labelcolor="#e8eaf0",
            fontsize=3.5,
            loc="upper left",
            borderpad=0.2,
            handlelength=1.6,
        )
    plt.tight_layout(pad=0.25, h_pad=0.25)
    return fig
