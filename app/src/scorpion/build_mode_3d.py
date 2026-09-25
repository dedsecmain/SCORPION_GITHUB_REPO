from __future__ import annotations

import math
from dataclasses import dataclass
from pathlib import Path

import numpy as np


SUPPORTED_3D_EXTENSIONS = {".obj", ".glb", ".gltf", ".stl", ".ply"}


class Build3DImportError(RuntimeError):
    pass


@dataclass(frozen=True)
class MeshAsset:
    name: str
    vertices: np.ndarray
    faces: np.ndarray
    source_path: str | None = None

    @property
    def face_count(self) -> int:
        return int(len(self.faces))


def _normalize_mesh(vertices: np.ndarray) -> np.ndarray:
    vertices = np.asarray(vertices, dtype=float).reshape((-1, 3))
    if len(vertices) == 0:
        raise Build3DImportError("3D-Modell enthält keine Vertices.")
    minimum = vertices.min(axis=0)
    maximum = vertices.max(axis=0)
    center = (minimum + maximum) / 2.0
    centered = vertices - center
    extent = float(np.max(maximum - minimum))
    if not math.isfinite(extent) or extent <= 1e-9:
        raise Build3DImportError("3D-Modell hat keine nutzbare räumliche Ausdehnung.")
    return centered / extent * 1.8


def _cap_faces(faces: np.ndarray, max_faces: int) -> np.ndarray:
    faces = np.asarray(faces, dtype=int).reshape((-1, 3))
    if len(faces) <= max_faces:
        return faces
    indices = np.linspace(0, len(faces) - 1, max_faces, dtype=int)
    return faces[indices]


def load_mesh_asset(path: str | Path, *, max_faces: int = 3200, max_bytes: int = 100_000_000) -> MeshAsset:
    source = Path(path).expanduser().resolve()
    if not source.is_file():
        raise Build3DImportError("3D-Datei wurde nicht gefunden.")
    if source.suffix.lower() not in SUPPORTED_3D_EXTENSIONS:
        raise Build3DImportError(
            "Nicht unterstütztes 3D-Format. Erlaubt: OBJ, GLB, GLTF, STL, PLY."
        )
    if source.stat().st_size > max_bytes:
        raise Build3DImportError("3D-Datei ist für den lokalen Build Mode zu groß.")

    try:
        import trimesh
    except ImportError as exc:
        raise Build3DImportError(
            "3D-Import fehlt. Führe setup_scorpion.bat erneut aus."
        ) from exc

    try:
        scene = trimesh.load_scene(source)
        mesh = scene.to_mesh()
    except Exception as exc:
        raise Build3DImportError(f"3D-Modell konnte nicht geladen werden: {exc}") from exc

    vertices = _normalize_mesh(np.asarray(mesh.vertices, dtype=float))
    faces = _cap_faces(np.asarray(mesh.faces, dtype=int), max_faces=max_faces)
    if len(faces) == 0:
        raise Build3DImportError("3D-Modell enthält keine renderbaren Flächen.")

    return MeshAsset(
        name=source.stem,
        vertices=vertices,
        faces=faces,
        source_path=str(source),
    )


def cube_asset() -> MeshAsset:
    v = np.array([
        [-1, -1, -1], [1, -1, -1], [1, 1, -1], [-1, 1, -1],
        [-1, -1, 1], [1, -1, 1], [1, 1, 1], [-1, 1, 1],
    ], dtype=float) * 0.7
    f = np.array([
        [0, 2, 1], [0, 3, 2],
        [4, 5, 6], [4, 6, 7],
        [0, 1, 5], [0, 5, 4],
        [2, 3, 7], [2, 7, 6],
        [1, 2, 6], [1, 6, 5],
        [3, 0, 4], [3, 4, 7],
    ], dtype=int)
    return MeshAsset("Cube", v, f)


def panel_asset() -> MeshAsset:
    v = np.array([
        [-1.2, -0.7, 0.0], [1.2, -0.7, 0.0],
        [1.2, 0.7, 0.0], [-1.2, 0.7, 0.0],
    ], dtype=float)
    f = np.array([[0, 1, 2], [0, 2, 3]], dtype=int)
    return MeshAsset("Panel", v, f)


def sphere_asset(*, rings: int = 10, segments: int = 16) -> MeshAsset:
    vertices = []
    for r in range(rings + 1):
        phi = math.pi * r / rings
        y = math.cos(phi)
        radius = math.sin(phi)
        for s in range(segments):
            theta = 2.0 * math.pi * s / segments
            vertices.append((radius * math.cos(theta), y, radius * math.sin(theta)))
    faces = []
    for r in range(rings):
        for s in range(segments):
            n = (s + 1) % segments
            a = r * segments + s
            b = r * segments + n
            c = (r + 1) * segments + s
            d = (r + 1) * segments + n
            faces.append((a, c, b))
            faces.append((b, c, d))
    return MeshAsset(
        "Sphere",
        np.asarray(vertices, dtype=float) * 0.8,
        np.asarray(faces, dtype=int),
    )


def primitive_asset(kind: str) -> MeshAsset:
    value = str(kind).strip().lower()
    if value == "cube":
        return cube_asset()
    if value == "sphere":
        return sphere_asset()
    if value == "panel":
        return panel_asset()
    raise ValueError(f"Kein 3D-Primitive für {kind}")


@dataclass
class Camera3D:
    yaw: float = -18.0
    pitch: float = 18.0
    distance: float = 8.5
    focal_length: float = 560.0


class Software3DRenderer:
    """Small perspective mesh renderer for Scorpion's Tk canvas."""

    def __init__(self, camera: Camera3D | None = None):
        self.camera = camera or Camera3D()
        self.light_direction = np.array([-0.35, 0.75, 0.85], dtype=float)
        self.light_direction /= np.linalg.norm(self.light_direction)

    @staticmethod
    def _rotation_y(degrees: float) -> np.ndarray:
        a = math.radians(float(degrees))
        c, s = math.cos(a), math.sin(a)
        return np.array([[c, 0, s], [0, 1, 0], [-s, 0, c]], dtype=float)

    @staticmethod
    def _rotation_x(degrees: float) -> np.ndarray:
        a = math.radians(float(degrees))
        c, s = math.cos(a), math.sin(a)
        return np.array([[1, 0, 0], [0, c, -s], [0, s, c]], dtype=float)

    def world_vertices(self, asset: MeshAsset, item) -> np.ndarray:
        vertices = np.asarray(asset.vertices, dtype=float) * float(item.scale)
        vertices = vertices @ self._rotation_y(item.rotation_y).T
        translation = np.array([
            (float(item.x) - 0.5) * 5.4,
            (0.58 - float(item.y)) * 3.4,
            float(item.z) * 2.2,
        ])
        return vertices + translation

    def camera_vertices(self, vertices: np.ndarray) -> np.ndarray:
        rotated = vertices @ self._rotation_y(self.camera.yaw).T
        rotated = rotated @ self._rotation_x(self.camera.pitch).T
        rotated[:, 2] += self.camera.distance
        return rotated

    def project(self, vertices: np.ndarray, width: int, height: int) -> np.ndarray:
        camera = self.camera_vertices(np.asarray(vertices, dtype=float))
        z = np.maximum(camera[:, 2], 0.15)
        x = width / 2.0 + camera[:, 0] * self.camera.focal_length / z
        y = height / 2.0 - camera[:, 1] * self.camera.focal_length / z
        return np.column_stack((x, y, z))

    @staticmethod
    def _shade_color(intensity: float, *, selected: bool = False) -> str:
        intensity = max(0.0, min(1.0, float(intensity)))
        if selected:
            base = np.array([120, 18, 25], dtype=float)
            boost = np.array([110, 32, 38], dtype=float) * intensity
        else:
            base = np.array([42, 45, 52], dtype=float)
            boost = np.array([82, 42, 46], dtype=float) * intensity
        rgb = np.clip(base + boost, 0, 255).astype(int)
        return "#{:02X}{:02X}{:02X}".format(*rgb)

    def draw_grid(self, canvas, width: int, height: int, *, line_color: str, axis_color: str):
        for value in np.linspace(-5.0, 5.0, 11):
            for start, end in (
                (np.array([[value, -1.35, -5.0], [value, -1.35, 5.0]])),
                (np.array([[-5.0, -1.35, value], [5.0, -1.35, value]])),
            ):
                p = self.project(start, width, height)
                canvas.create_line(
                    p[0, 0], p[0, 1], p[1, 0], p[1, 1],
                    fill=line_color,
                    width=1,
                )
        origin = self.project(np.array([
            [-5.0, -1.34, 0.0], [5.0, -1.34, 0.0],
            [0.0, -1.34, -5.0], [0.0, -1.34, 5.0],
        ]), width, height)
        canvas.create_line(*origin[0, :2], *origin[1, :2], fill=axis_color, width=2)
        canvas.create_line(*origin[2, :2], *origin[3, :2], fill=axis_color, width=2)

    def project_item_center(self, item, width: int, height: int) -> np.ndarray:
        center = np.array([[
            (float(item.x) - 0.5) * 5.4,
            (0.58 - float(item.y)) * 3.4,
            float(item.z) * 2.2,
        ]], dtype=float)
        return self.project(center, width, height)[0]

    def draw_mesh(self, canvas, asset: MeshAsset, item, width: int, height: int, *, selected: bool, accent: str):
        world = self.world_vertices(asset, item)
        projected = self.project(world, width, height)
        faces = np.asarray(asset.faces, dtype=int)

        render_faces = []
        for face in faces:
            tri_world = world[face]
            tri_screen = projected[face]
            if np.any(tri_screen[:, 2] <= 0.16):
                continue
            edge1 = tri_world[1] - tri_world[0]
            edge2 = tri_world[2] - tri_world[0]
            normal = np.cross(edge1, edge2)
            norm = float(np.linalg.norm(normal))
            if norm <= 1e-9:
                continue
            normal /= norm
            intensity = 0.2 + 0.8 * abs(float(np.dot(normal, self.light_direction)))
            depth = float(np.mean(tri_screen[:, 2]))
            points = [
                float(tri_screen[0, 0]), float(tri_screen[0, 1]),
                float(tri_screen[1, 0]), float(tri_screen[1, 1]),
                float(tri_screen[2, 0]), float(tri_screen[2, 1]),
            ]
            render_faces.append((depth, points, intensity))

        render_faces.sort(key=lambda entry: entry[0], reverse=True)
        for _depth, points, intensity in render_faces:
            canvas.create_polygon(
                points,
                fill=self._shade_color(intensity, selected=selected),
                outline=accent if selected else "#5C252B",
                width=2 if selected else 1,
            )

    def orbit(self, *, yaw_delta: float = 0.0, pitch_delta: float = 0.0):
        self.camera.yaw = (self.camera.yaw + float(yaw_delta)) % 360.0
        self.camera.pitch = max(-55.0, min(55.0, self.camera.pitch + float(pitch_delta)))

    def zoom(self, factor: float):
        self.camera.distance = max(4.5, min(16.0, self.camera.distance * float(factor)))

    def reset_camera(self):
        self.camera.yaw = -18.0
        self.camera.pitch = 18.0
        self.camera.distance = 8.5
