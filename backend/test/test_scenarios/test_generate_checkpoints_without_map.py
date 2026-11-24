import math

import matplotlib.pyplot as plt
from matplotlib.patches import Circle, Ellipse, FancyArrowPatch

plt.rcParams.update(
    {
        "font.size": 11,
        "axes.titlesize": 12,
        "axes.titleweight": "bold",
        "figure.facecolor": "white",
        "axes.facecolor": "#f8f9fa",
    }
)

C_AREA = "#95a5a6"  # Szary - cały dopuszczalny obszar (promień R)
C_START = "#d62728"  # Czerwony - punkt startu
C_ELLIPSE = "#1f4e78"  # Granatowy - elipsa poszukiwań
C_POINT = "#2b5c8f"  # Niebieski - punkty pośrednie
C_CENTROID = "#e67e22"  # Pomarańczowy - centroid
C_BAD = "#bdc3c7"  # Jasnoszary - kolejność przed sortowaniem
C_LOOP = "#1b7837"  # Zielony - finalna pętla


def generate_example_data(radius: float = 1500.0):
    theta_center = math.radians(45)
    d_center = 0.42 * radius
    cx = d_center * math.cos(theta_center)
    cy = d_center * math.sin(theta_center)

    alpha_cloud = math.radians(-35)
    aspect_ratio = 1.22
    b = 0.48 * radius
    a = b * aspect_ratio

    # Celowo zamieniona kolejność sektorów (0, 2, 1), żeby przed sortowaniem było wyraźne przecięcie
    base_sector_angle = math.radians(10)
    sector_order = [0, 2, 1]
    angle_offsets = [0.35, 0.55, 0.50]
    r_norms = [0.92, 0.88, 0.90]

    raw_points = []
    for idx, i in enumerate(sector_order):
        sector_start = base_sector_angle + i * (2.0 / 3.0 * math.pi)
        sector_span = 2.0 / 3.0 * math.pi
        angle = sector_start + angle_offsets[idx] * sector_span

        lx = r_norms[idx] * a * math.cos(angle)
        ly = r_norms[idx] * b * math.sin(angle)

        cos_a, sin_a = math.cos(alpha_cloud), math.sin(alpha_cloud)
        rx = lx * cos_a - ly * sin_a
        ry = lx * sin_a + ly * cos_a
        raw_points.append((cx + rx, cy + ry))

    sector_angles = [base_sector_angle + i * (2.0 / 3.0 * math.pi) for i in range(3)]

    start = (0.0, 0.0)
    loop_vertices = [start] + raw_points
    centroid_x = sum(p[0] for p in loop_vertices) / 4.0
    centroid_y = sum(p[1] for p in loop_vertices) / 4.0
    centroid = (centroid_x, centroid_y)

    sorted_by_angle = sorted(
        loop_vertices,
        key=lambda p: math.atan2(p[1] - centroid_y, p[0] - centroid_x),
    )
    start_idx = sorted_by_angle.index(start)
    ordered_cycle = [sorted_by_angle[(start_idx + i) % 4] for i in range(4)]

    return {
        "radius": radius,
        "start": start,
        "center": (cx, cy),
        "a": a,
        "b": b,
        "alpha_cloud": alpha_cloud,
        "sector_angles": sector_angles,
        "raw_points": raw_points,
        "centroid": centroid,
        "ordered_cycle": ordered_cycle,
    }


def setup_canvas(ax, data, title: str):
    R = data["radius"]
    lim = (-R * 1.15, R * 1.15)
    ax.set_xlim(lim)
    ax.set_ylim(lim)
    ax.set_aspect("equal")
    ax.set_xticks([])
    ax.set_yticks([])
    ax.set_title(title, pad=10)

    # Cały dopuszczalny obszar (okrąg o promieniu R wokół startu)
    area_fill = Circle((0, 0), R, facecolor="#ecf0f1", edgecolor="none", zorder=1)
    area_border = Circle(
        (0, 0), R, facecolor="none", edgecolor=C_AREA, lw=1.6, ls="--", label="Obszar dopuszczalny ($R$)", zorder=2
    )
    ax.add_patch(area_fill)
    ax.add_patch(area_border)


def draw_ellipse(ax, data, alpha_fill=0.14):
    cx, cy = data["center"]
    ell_fill = Ellipse(
        (cx, cy),
        2 * data["a"],
        2 * data["b"],
        angle=math.degrees(data["alpha_cloud"]),
        facecolor=C_ELLIPSE,
        edgecolor="none",
        alpha=alpha_fill,
        zorder=2,
    )
    ell_edge = Ellipse(
        (cx, cy),
        2 * data["a"],
        2 * data["b"],
        angle=math.degrees(data["alpha_cloud"]),
        facecolor="none",
        edgecolor=C_ELLIPSE,
        lw=2,
        zorder=3,
    )
    ax.add_patch(ell_fill)
    ax.add_patch(ell_edge)


def plot_step1(data):
    fig, ax = plt.subplots(figsize=(5.2, 5.2))
    setup_canvas(ax, data, "1. Przesunięta chmura eliptyczna")
    draw_ellipse(ax, data, alpha_fill=0.16)

    sx, sy = data["start"]
    cx, cy = data["center"]

    ax.annotate("", xy=(cx, cy), xytext=(sx, sy), arrowprops=dict(arrowstyle="->", color=C_ELLIPSE, lw=1.8), zorder=4)
    ax.scatter([sx], [sy], color=C_START, s=90, zorder=6, label="Start / Meta")
    ax.scatter([cx], [cy], color=C_ELLIPSE, s=55, marker="x", lw=2, zorder=6, label="Środek elipsy")

    ax.legend(loc="lower left", framealpha=0.95, fontsize=9.5)
    plt.tight_layout()
    plt.savefig("krok1_elipsa.png", dpi=300)
    plt.close()


def plot_step2(data):
    fig, ax = plt.subplots(figsize=(5.2, 5.2))
    setup_canvas(ax, data, "2. Podział sektorowy (3 × 120°)")
    draw_ellipse(ax, data, alpha_fill=0.08)

    sx, sy = data["start"]
    cx, cy = data["center"]
    alpha = data["alpha_cloud"]

    for ang in data["sector_angles"]:
        lx = data["a"] * math.cos(ang)
        ly = data["b"] * math.sin(ang)
        rx = lx * math.cos(alpha) - ly * math.sin(alpha)
        ry = lx * math.sin(alpha) + ly * math.cos(alpha)
        ax.plot([cx, cx + rx], [cy, cy + ry], color=C_ELLIPSE, lw=1.2, ls=":", zorder=3)

    pts = data["raw_points"]
    ax.scatter([p[0] for p in pts], [p[1] for p in pts], color=C_POINT, s=85, zorder=5, label="Punkty pośrednie")
    ax.scatter([sx], [sy], color=C_START, s=90, zorder=6, label="Start / Meta")

    ax.legend(loc="lower left", framealpha=0.95, fontsize=9.5)
    plt.tight_layout()
    plt.savefig("krok2_sektory.png", dpi=300)
    plt.close()


def plot_step3(data):
    fig, ax = plt.subplots(figsize=(5.2, 5.2))
    setup_canvas(ax, data, "3. Sortowanie wokół centroidu")

    sx, sy = data["start"]
    cent_x, cent_y = data["centroid"]
    raw_cycle = [data["start"]] + data["raw_points"] + [data["start"]]
    ord_cycle = data["ordered_cycle"] + [data["ordered_cycle"][0]]

    ax.plot(
        [p[0] for p in raw_cycle],
        [p[1] for p in raw_cycle],
        color=C_BAD,
        lw=1.8,
        ls="--",
        zorder=3,
        label="Przed sortowaniem",
    )
    ax.plot([p[0] for p in ord_cycle], [p[1] for p in ord_cycle], color=C_LOOP, lw=2.3, zorder=4, label="Po sortowaniu")

    ax.scatter([cent_x], [cent_y], color=C_CENTROID, s=90, marker="P", zorder=6, label="Centroid")
    pts = data["raw_points"]
    ax.scatter([p[0] for p in pts], [p[1] for p in pts], color=C_POINT, s=75, zorder=5)
    ax.scatter([sx], [sy], color=C_START, s=90, zorder=6)

    ax.legend(loc="lower left", framealpha=0.95, fontsize=9.5)
    plt.tight_layout()
    plt.savefig("krok3_centroid.png", dpi=300)
    plt.close()


def plot_step4(data):
    fig, ax = plt.subplots(figsize=(5.2, 5.2))
    setup_canvas(ax, data, "4. Wyznaczenie kierunku obiegu")

    cycle = data["ordered_cycle"]
    sx, sy = data["start"]

    for i in range(4):
        arrow = FancyArrowPatch(
            cycle[i],
            cycle[(i + 1) % 4],
            arrowstyle="-|>,head_length=8,head_width=5",
            color=C_LOOP,
            lw=2.3,
            shrinkA=6,
            shrinkB=6,
            zorder=4,
        )
        ax.add_patch(arrow)

    pts = cycle[1:]
    ax.scatter([p[0] for p in pts], [p[1] for p in pts], color=C_POINT, s=80, zorder=5, label="Punkty kontrolne")
    ax.scatter([sx], [sy], color=C_START, s=95, zorder=6, label="Start / Meta")

    ax.legend(loc="lower left", framealpha=0.95, fontsize=9.5)
    plt.tight_layout()
    plt.savefig("krok4_mapa.png", dpi=300)
    plt.close()


if __name__ == "__main__":
    data = generate_example_data(radius=1500.0)
    plot_step1(data)
    plot_step2(data)
    plot_step3(data)
    plot_step4(data)
