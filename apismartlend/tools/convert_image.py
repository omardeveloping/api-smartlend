import argparse
from pathlib import Path

from PIL import Image


def convert(source: Path, destination: Path, format_: str = "JPEG"):
    with Image.open(source) as img:
        converted = img.convert("RGB")
        converted.save(destination, format=format_, quality=95)
    return destination


def main():
    parser = argparse.ArgumentParser(
        description="Convierte una imagen al formato RGB 8-bit (JPEG por defecto)."
    )
    parser.add_argument("source", type=Path, help="Ruta al archivo original")
    parser.add_argument(
        "-o",
        "--output",
        type=Path,
        default=None,
        help="Ruta de salida (por defecto agrega _rgb.jpg al nombre)",
    )
    parser.add_argument(
        "-f",
        "--format",
        default="JPEG",
        choices=["JPEG", "PNG"],
        help="Formato de salida (JPEG/PNG)",
    )

    args = parser.parse_args()
    output = args.output or args.source.with_name(f"{args.source.stem}_rgb.jpg")
    result = convert(args.source, output, args.format)
    print(f"Imagen convertida: {result}")


if __name__ == "__main__":
    main()
