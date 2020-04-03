# coding=utf-8
import pytest

from dragonfly.shadingparameter import ExtrudedBorder, Overhang, LouversByDistance, \
    LouversByCount

from honeybee.face import Face

from ladybug_geometry.geometry2d.pointvector import Vector2D
from ladybug_geometry.geometry3d.pointvector import Point3D, Vector3D
from ladybug_geometry.geometry3d.line import LineSegment3D
from ladybug_geometry.geometry3d.face import Face3D


def test_extruded_border_init():
    """Test the initalization of ExtrudedBorder objects and basic properties."""
    simple_border = ExtrudedBorder(0.3)
    str(simple_border)  # test the string representation

    assert simple_border.depth == 0.3


def test_extruded_border_equality():
    """Test the equality of ExtrudedBorder objects."""
    simple_border = ExtrudedBorder(0.3)
    simple_border_dup = simple_border.duplicate()
    simple_border_alt = ExtrudedBorder(0.5)

    assert simple_border is simple_border
    assert simple_border is not simple_border_dup
    assert simple_border == simple_border_dup
    assert simple_border != simple_border_alt


def test_extruded_border_scale():
    """Test the scale method."""
    simple_border = ExtrudedBorder(0.3)

    new_simple_border  = simple_border.scale(2)
    assert new_simple_border.depth == 0.6


def test_extruded_border_dict_methods():
    """Test the to/from dict methods."""
    simple_border = ExtrudedBorder(0.3)

    shd_dict = simple_border.to_dict()
    new_simple_border = ExtrudedBorder.from_dict(shd_dict)
    assert new_simple_border == simple_border
    assert shd_dict == new_simple_border.to_dict()


def test_extruded_border_add_shading_to_face():
    """Test the add_shading_to_face method."""
    simple_border = ExtrudedBorder(0.3)
    height = 3
    width = 10
    seg = LineSegment3D.from_end_points(Point3D(0, 0, 2), Point3D(width, 0, 2))
    face_1 = Face('test_face', Face3D.from_extrusion(seg, Vector3D(0, 0, height)))
    face_2 = face_1.duplicate()
    face_2.apertures_by_ratio(0.4)
    simple_border.add_shading_to_face(face_1, 0.01)
    simple_border.add_shading_to_face(face_2, 0.01)

    assert len(face_1.apertures) == 0
    assert len(face_1.outdoor_shades) == 0
    assert len(face_2.apertures) == 1
    assert len(face_2.apertures[0].outdoor_shades) == 4
    shd_area = sum([shd.area for shd in face_2.apertures[0].outdoor_shades])
    assert shd_area == pytest.approx(0.3 * face_2.apertures[0].perimeter, rel=1e-3)


def test_overhang_init():
    """Test the initalization of Overhang objects and basic properties."""
    simple_awning = Overhang(2, 10)
    str(simple_awning)  # test the string representation

    assert simple_awning.depth == 2
    assert simple_awning.angle == 10


def test_overhang_equality():
    """Test the equality of Overhang objects."""
    simple_awning = Overhang(2, 10)
    simple_awning_dup = simple_awning.duplicate()
    simple_awning_alt = Overhang(3, 10)

    assert simple_awning is simple_awning
    assert simple_awning is not simple_awning_dup
    assert simple_awning == simple_awning_dup
    assert simple_awning != simple_awning_alt


def test_overhang_scale():
    """Test the scale method."""
    simple_awning = Overhang(2, 10)

    new_simple_awning  = simple_awning.scale(2)
    assert new_simple_awning.depth == 4
    assert new_simple_awning.angle == 10


def test_overhang_dict_methods():
    """Test the to/from dict methods."""
    simple_awning = Overhang(2, 10)

    shd_dict = simple_awning.to_dict()
    new_simple_awning = Overhang.from_dict(shd_dict)
    assert new_simple_awning == simple_awning
    assert shd_dict == new_simple_awning.to_dict()


def test_overhang_add_shading_to_face():
    """Test the add_shading_to_face method."""
    simple_awning = Overhang(2, 0)
    height = 3
    width = 10
    seg = LineSegment3D.from_end_points(Point3D(0, 0, 2), Point3D(width, 0, 2))
    face = Face('test_face', Face3D.from_extrusion(seg, Vector3D(0, 0, height)))
    simple_awning.add_shading_to_face(face, 0.01)

    assert len(face.outdoor_shades) == 1
    assert face.outdoor_shades[0].center.z == pytest.approx(2 + 3, rel=1e-1)
    assert face.outdoor_shades[0].area == pytest.approx(20, rel=1e-3)


def test_louvers_by_distance_init():
    """Test the initalization of LouversByDistance objects and basic properties."""
    louvers = LouversByDistance(0.5, 0.3, 1, 30)
    str(louvers)  # test the string representation

    assert louvers.distance == 0.5
    assert louvers.depth == 0.3
    assert louvers.offset == 1
    assert louvers.angle == 30
    assert louvers.contour_vector == Vector2D(0, 1)
    assert louvers.flip_start_side is False


def test_louvers_by_distance_equality():
    """Test the equality of LouversByDistance objects."""
    louvers = LouversByDistance(0.5, 0.3, 1, 30)
    louvers_dup = louvers.duplicate()
    louvers_alt = LouversByDistance(0.3, 0.3, 1, 30)

    assert louvers is louvers
    assert louvers is not louvers_dup
    assert louvers == louvers_dup
    assert louvers != louvers_alt


def test_louvers_by_distance_scale():
    """Test the scale method."""
    louvers = LouversByDistance(0.5, 0.3, 1, 30)

    new_louvers  = louvers.scale(2)
    assert new_louvers.distance == 1
    assert new_louvers.depth == 0.6
    assert new_louvers.offset == 2


def test_louvers_by_distance_dict_methods():
    """Test the to/from dict methods."""
    louvers = LouversByDistance(0.5, 0.3, 1, 30)

    shd_dict = louvers.to_dict()
    new_louvers = LouversByDistance.from_dict(shd_dict)
    assert new_louvers == louvers
    assert shd_dict == new_louvers.to_dict()


def test_louvers_by_distance_add_shading_to_face():
    """Test the add_shading_to_face method."""
    louvers = LouversByDistance(0.5, 0.3, 1, 30)
    height = 3
    width = 10
    seg = LineSegment3D.from_end_points(Point3D(0, 0, 2), Point3D(width, 0, 2))
    face = Face('test_face', Face3D.from_extrusion(seg, Vector3D(0, 0, height)))
    louvers.add_shading_to_face(face, 0.01)

    assert len(face.outdoor_shades) == 6
    shd_area = sum([shd.area for shd in face.outdoor_shades])
    assert shd_area == pytest.approx(0.3 * width * 6, rel=1e-3)


def test_louvers_by_count_init():
    """Test the initalization of LouversByCount objects and basic properties."""
    louvers = LouversByCount(3, 0.3, 1, 30)
    str(louvers)  # test the string representation

    assert louvers.louver_count == 3
    assert louvers.depth == 0.3
    assert louvers.offset == 1
    assert louvers.angle == 30
    assert louvers.contour_vector == Vector2D(0, 1)
    assert louvers.flip_start_side is False


def test_louvers_by_count_equality():
    """Test the equality of LouversByCount objects."""
    louvers = LouversByCount(3, 0.3, 1, 30)
    louvers_dup = louvers.duplicate()
    louvers_alt = LouversByCount(6, 0.3, 1, 30)

    assert louvers is louvers
    assert louvers is not louvers_dup
    assert louvers == louvers_dup
    assert louvers != louvers_alt


def test_louvers_by_distance_scale():
    """Test the scale method."""
    louvers = LouversByCount(3, 0.3, 1, 30)

    new_louvers  = louvers.scale(2)
    assert new_louvers.depth == 0.6
    assert new_louvers.offset == 2


def test_louvers_by_count_dict_methods():
    """Test the to/from dict methods."""
    louvers = LouversByCount(3, 0.3, 1, 30)

    shd_dict = louvers.to_dict()
    new_louvers = LouversByCount.from_dict(shd_dict)
    assert new_louvers == louvers
    assert shd_dict == new_louvers.to_dict()


def test_louvers_by_count_add_shading_to_face():
    """Test the add_shading_to_face method."""
    louvers = LouversByCount(6, 0.3, 1, 30)
    height = 3
    width = 10
    seg = LineSegment3D.from_end_points(Point3D(0, 0, 2), Point3D(width, 0, 2))
    face = Face('test_face', Face3D.from_extrusion(seg, Vector3D(0, 0, height)))

    louvers.add_shading_to_face(face, 0.01)

    assert len(face.outdoor_shades) == 6
    shd_area = sum([shd.area for shd in face.outdoor_shades])
    assert shd_area == pytest.approx(0.3 * width * 6, rel=1e-3)
