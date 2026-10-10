import numpy as np
import pytest

from scorpion.build_mode import BuildModeSession
from scorpion.build_mode_3d import (
    Build3DImportError,
    Software3DRenderer,
    cube_asset,
    load_mesh_asset,
    primitive_asset,
    sphere_asset,
)


def test_3d_primitives_have_vertices_and_faces():
    cube = cube_asset()
    sphere = sphere_asset()
    assert cube.vertices.shape[1] == 3
    assert cube.faces.shape[1] == 3
    assert len(cube.faces) >= 12
    assert len(sphere.faces) > len(cube.faces)


def test_renderer_projects_3d_points_with_depth():
    renderer = Software3DRenderer()
    projected = renderer.project(
        np.array([[0.0, 0.0, 0.0], [1.0, 1.0, 0.0]], dtype=float),
        1000,
        700,
    )
    assert projected.shape == (2, 3)
    assert np.all(projected[:, 2] > 0)
    assert projected[0, 0] == pytest.approx(500.0, abs=80.0)


def test_import_simple_obj_mesh(tmp_path):
    obj = tmp_path / "triangle.obj"
    obj.write_text(
        "v 0 0 0\n"
        "v 1 0 0\n"
        "v 0 1 0\n"
        "f 1 2 3\n",
        encoding="utf-8",
    )

    asset = load_mesh_asset(obj)

    assert asset.name == "triangle"
    assert asset.face_count == 1
    assert asset.vertices.shape == (3, 3)
    assert asset.source_path.endswith("triangle.obj")


def test_import_rejects_unsupported_extension(tmp_path):
    path = tmp_path / "model.exe"
    path.write_bytes(b"not a model")
    with pytest.raises(Build3DImportError):
        load_mesh_asset(path)


def test_build_session_supports_imported_mesh_and_depth():
    session = BuildModeSession()
    item = session.add_object(
        "mesh",
        x=0.5,
        y=0.5,
        name="Car",
        source_path=r"C:\Models\car.glb",
    )
    session.activate()
    session.selected_id = item.id

    moved = session.move_depth(0.25)

    assert moved is not None
    assert moved.kind == "mesh"
    assert moved.name == "Car"
    assert moved.z == pytest.approx(0.25)
    assert session.get(item.id).source_path.endswith("car.glb")


def test_primitive_asset_rejects_unknown_kind():
    with pytest.raises(ValueError):
        primitive_asset("spaceship")
