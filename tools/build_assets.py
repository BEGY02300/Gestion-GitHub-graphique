from __future__ import annotations

from pathlib import Path

from PIL import Image, ImageDraw


def make_icon(size: int = 1024) -> Image.Image:
    scale = size / 128
    image = Image.new("RGBA", (size, size), (0, 0, 0, 0))
    draw = ImageDraw.Draw(image)

    def box(x: int, y: int, width: int, height: int) -> tuple[int, int, int, int]:
        return (
            round(x * scale),
            round(y * scale),
            round((x + width) * scale),
            round((y + height) * scale),
        )

    top = (23, 34, 60)
    bottom = (38, 59, 104)
    for y in range(size):
        ratio = y / max(size - 1, 1)
        color = tuple(round(a + (b - a) * ratio) for a, b in zip(top, bottom))
        draw.line((0, y, size, y), fill=(*color, 255))

    corner = round(29 * scale)
    mask = Image.new("L", (size, size), 0)
    ImageDraw.Draw(mask).rounded_rectangle((0, 0, size - 1, size - 1), radius=corner, fill=255)
    image.putalpha(mask)
    draw = ImageDraw.Draw(image)

    draw.rounded_rectangle(
        box(25, 24, 78, 80),
        radius=round(16 * scale),
        fill="#10182b",
        outline="#7186b0",
        width=max(1, round(2 * scale)),
    )
    draw.line(
        (round(25 * scale), round(42 * scale), round(103 * scale), round(42 * scale)),
        fill="#7186b0",
        width=max(1, round(2 * scale)),
    )
    for x, color in ((37, "#ff8293"), (48, "#ffd075"), (59, "#63dfb2")):
        radius = round(3 * scale)
        draw.ellipse(box(x - 3, 30, 6, 6), fill=color)

    blue = "#73a5ff"
    cyan = "#48dfcf"
    points = [
        (round(48 * scale), round(61 * scale)),
        (round(48 * scale), round(88 * scale)),
        (round(79 * scale), round(74 * scale)),
        (round(80 * scale), round(61 * scale)),
        (round(80 * scale), round(88 * scale)),
    ]
    draw.line((points[0], points[1]), fill=blue, width=round(6 * scale))
    draw.line((points[1], points[2]), fill=cyan, width=round(6 * scale))
    draw.line((points[2], points[3]), fill=cyan, width=round(6 * scale))
    draw.line((points[2], points[4]), fill=blue, width=round(6 * scale))
    for (x, y), color in zip(
        ((48, 60), (48, 88), (80, 61), (80, 88)),
        (blue, cyan, cyan, blue),
    ):
        radius = round(7 * scale)
        center = (round(x * scale), round(y * scale))
        draw.ellipse(
            (
                center[0] - radius,
                center[1] - radius,
                center[0] + radius,
                center[1] + radius,
            ),
            fill=color,
        )
    return image


def main() -> None:
    output = Path("build") / "assets"
    output.mkdir(parents=True, exist_ok=True)
    icon = make_icon()
    icon.save(output / "github-desk.png")
    icon.save(
        output / "github-desk.ico",
        format="ICO",
        sizes=[(16, 16), (24, 24), (32, 32), (48, 48), (64, 64), (128, 128), (256, 256)],
    )
    iconset = output / "github-desk.iconset"
    iconset.mkdir(exist_ok=True)
    for size in (16, 32, 64, 128, 256, 512):
        resized = icon.resize((size, size), Image.Resampling.LANCZOS)
        resized.save(iconset / f"icon_{size}x{size}.png")
        resized.save(iconset / f"icon_{size}x{size}@2x.png")


if __name__ == "__main__":
    main()
