import matplotlib.pyplot as plt
from matplotlib.patches import Circle

plt.rcParams.update(
    {
        "font.size": 11,
        "figure.facecolor": "white",
    }
)

C_BASE = "#1f4e78"  # Granatowy - odcinek bazowy (u, w)
C_DETOUR = "#1b7837"  # Zielony - nowy przebieg (u -> v -> w)
C_HEIGHT = "#e67e22"  # Pomarańczowy - odsunięcie boczne h
C_ZONE = "#d62728"  # Czerwony - strefa ochronna wokół u i w

fig, ax = plt.subplots(figsize=(5.0, 3.5))

u = (0.0, 0.0)
w = (10.0, 0.0)
v = (5.8, 4.3)
proj = (5.8, 0.0)

# Strefy ochronne wokół punktów u i w
for pt in (u, w):
    zone = Circle(pt, 1.7, facecolor=C_ZONE, edgecolor=C_ZONE, alpha=0.10, ls="--", lw=1.2)
    zone_edge = Circle(pt, 1.7, facecolor="none", edgecolor=C_ZONE, alpha=0.45, ls="--", lw=1.2)
    ax.add_patch(zone)
    ax.add_patch(zone_edge)

# Odcinek bazowy u - w
ax.plot([u[0], w[0]], [u[1], w[1]], color=C_BASE, lw=2.0, ls="--", label="Odcinek bazowy $d(u,w)$")

# Nowa ścieżka u -> v -> w
ax.plot([u[0], v[0], w[0]], [u[1], v[1], w[1]], color=C_DETOUR, lw=2.5, label="Objazd $d(u,v)+d(v,w)$")

# Wysokość trójkąta h_perp
ax.plot([v[0], proj[0]], [v[1], proj[1]], color=C_HEIGHT, lw=2.0, ls=":")
ax.text(v[0] + 0.25, v[1] * 0.48, r"$h_{\perp}$", color=C_HEIGHT, fontsize=13, fontweight="bold")

# Kąt prosty przy rzucie
sq = 0.35
ax.plot([proj[0], proj[0] + sq, proj[0] + sq], [sq, sq, 0], color=C_HEIGHT, lw=1.2)

# Punkty u, w, v
ax.scatter([u[0], w[0]], [u[1], w[1]], color=C_BASE, s=85, zorder=5)
ax.scatter([v[0]], [v[1]], color=C_DETOUR, s=95, zorder=6)

ax.text(u[0] - 0.3, u[1] - 0.65, "$u$", fontsize=12, fontweight="bold", color=C_BASE)
ax.text(w[0] + 0.1, w[1] - 0.65, "$w$", fontsize=12, fontweight="bold", color=C_BASE)
ax.text(v[0] - 0.15, v[1] + 0.32, "$v$", fontsize=12, fontweight="bold", color=C_DETOUR)
ax.text(u[0], -1.35, "Strefa ochronna", fontsize=8.5, color=C_ZONE, ha="center")

ax.set_xlim(-2.0, 12.0)
ax.set_ylim(-1.95, 5.5)
ax.set_aspect("equal")
ax.axis("off")
ax.legend(loc="upper left", framealpha=0.95, fontsize=9.0, borderpad=0.35)

plt.savefig("objazd_trojkat.png", dpi=300, bbox_inches="tight", pad_inches=0.04)
plt.close()
