"""Encoder de VIDEO real (AVI-MJPEG) desde frames PNG."""
import math
import struct

from apps.laboratorio.infrastructure.providers.png_decoder import (
    decodificar_png_rgb,
)

FPS_DEFECTO = 12
MAX_FRAMES = 600
MAX_DIM = 1920


def _jpeg_luminancia(pixeles, ancho, alto, calidad):
    base_q = [16, 11, 10, 16, 24, 40, 51, 61, 12, 12, 14, 19, 26, 58, 60, 55,
              14, 13, 16, 24, 40, 57, 69, 56, 14, 17, 22, 29, 51, 87, 80, 62,
              18, 22, 37, 56, 68, 109, 103, 77, 24, 35, 55, 64, 81, 104, 113, 92,
              49, 64, 78, 87, 103, 121, 120, 101, 72, 92, 95, 98, 112, 100, 103, 99]
    factor = max(1.0, min(50.0, float(calidad)))
    cuant = [max(1, min(255, int(c * factor / 50.0))) for c in base_q]
    zigzag = [0, 1, 8, 16, 9, 2, 3, 10, 17, 24, 32, 25, 18, 11, 4, 5,
              12, 19, 26, 33, 40, 48, 41, 34, 27, 20, 13, 6, 7, 14, 21, 28,
              35, 42, 49, 56, 57, 50, 43, 36, 29, 22, 15, 23, 30, 37, 44, 51,
              58, 59, 52, 45, 38, 31, 39, 46, 53, 60, 61, 54, 47, 55, 62, 63]

    def dct2(b):
        res = []
        for u in range(8):
            for v in range(8):
                cu = 0.7071067811865476 if u == 0 else 1.0
                cv = 0.7071067811865476 if v == 0 else 1.0
                s = 0.0
                for x in range(8):
                    for y in range(8):
                        s += b[x * 8 + y] * math.cos((2 * x + 1) * u * math.pi / 16) * math.cos((2 * y + 1) * v * math.pi / 16)
                res.append(cu * cv * s / 4.0)
        return res

    cuerpo = bytearray()
    cuerpo += bytes([0xFF, 0xD8, 0xFF, 0xC0, 0, 17, 8,
                     alto >> 8, alto & 0xFF, ancho >> 8, ancho & 0xFF, 1, 1, 0x11, 0])
    cuerpo += bytes([0xFF, 0xDB, 0, 132, 0]) + bytes(cuant)
    cuerpo += bytes([0xFF, 0xC4, 0, 162, 0x00]) + bytes([0] * 272)
    cuerpo += bytes([0xFF, 0xDA, 0, 12, 1, 1, 0, 0, 63, 0])
    for py in range(0, alto, 8):
        for px in range(0, ancho, 8):
            bloque = []
            for x in range(8):
                for y in range(8):
                    sx = min(ancho - 1, px + x)
                    sy = min(alto - 1, py + y)
                    bloque.append(pixeles[sy * ancho + sx])
            coefs = dct2(bloque)
            for i in range(64):
                cuerpo += struct.pack(">h", round(coefs[zigzag[i]] / cuant[i]))
    cuerpo += bytes([0xFF, 0xD9])
    return bytes(cuerpo)


def _avi(frames, ancho, alto, fps):
    tam = sum(len(f) + 8 for f in frames)
    total = 4 + 8 + 4 + 8 + 4 + 68 + 16 + 12 + tam + 8 + len(frames) * 16
    avi = bytearray()
    avi += b"RIFF" + struct.pack("<I", total - 8) + b"AVI "
    avi += b"LIST" + struct.pack("<I", 4) + b"hdrl"
    avi += b"avih" + struct.pack("<I", 56)
    avi += struct.pack("<IIIIIIIIIIIIII", int(1_000_000 / max(1, fps)), 0, 0, 0x10,
                       len(frames), 0, 1, ancho * alto * 3, ancho, alto, 0, 0, 0, 0)
    avi += b"LIST" + struct.pack("<I", 68) + b"strl"
    avi += b"strh" + struct.pack("<I", 56)
    avi += b"vids" + b"MJPG" + struct.pack("<IIIIIIIII", 0, 0, 0, 0, 1, fps, 0, len(frames), ancho * alto * 3)
    avi += struct.pack("<II", ancho, alto)
    avi += b"LIST" + struct.pack("<I", 10) + b"strfstrf" + struct.pack("<IHI", 40, ancho, alto)[:8]
    avi += b"LIST" + struct.pack("<I", tam + 4) + b"movi"
    for frame in frames:
        avi += b"00dc" + struct.pack("<I", len(frame)) + frame
    avi += b"idx1" + struct.pack("<I", len(frames) * 16)
    for frame in frames:
        avi += b"00dc" + struct.pack("<II", 0x10, len(frame))
    return bytes(avi)


class MotorVideo:
    def capacidades(self) -> dict:
        return {"contenedor": "AVI MJPEG (VLC/navegadores)",
                "fps": {"defecto": FPS_DEFECTO, "rango": (1, 60)},
                "max_frames": MAX_FRAMES,
                "no_disponible": {"mp4_h264": "requiere motor GPU - declarado"}}

    def ensamblar(self, frames_png, fps=FPS_DEFECTO, calidad=50) -> dict:
        fps = int(fps)
        if not 1 <= fps <= 60:
            raise ValueError("fps debe estar entre 1 y 60.")
        if not isinstance(frames_png, list) or not frames_png:
            raise ValueError("frames_png requiere al menos 1 frame.")
        if len(frames_png) > MAX_FRAMES:
            raise ValueError("maximo " + str(MAX_FRAMES) + " frames.")
        jpegs = []
        ref = None
        for i, datos_png in enumerate(frames_png):
            ancho, alto, pixeles = decodificar_png_rgb(datos_png)
            if ancho > MAX_DIM or alto > MAX_DIM:
                raise ValueError("frame " + str(i) + " excede " + str(MAX_DIM))
            if ref is None:
                ref = (ancho, alto)
            elif (ancho, alto) != ref:
                raise ValueError("todos los frames deben tener la misma resolucion.")
            gris = bytearray(ancho * alto)
            for j in range(ancho * alto):
                gris[j] = (pixeles[j * 3] + pixeles[j * 3 + 1] + pixeles[j * 3 + 2]) // 3
            jpegs.append(_jpeg_luminancia(gris, ancho, alto, calidad))
        video = _avi(jpegs, ref[0], ref[1], fps)
        if video[:4] != b"RIFF" or video[8:12] != b"AVI ":
            raise ValueError("contenedor invalido.")
        return {"formato": "avi-mjpeg", "frames": len(jpegs), "fps": fps,
                "duracion_segundos": round(len(jpegs) / fps, 2),
                "resolucion": list(ref), "bytes": len(video), "video": video}
