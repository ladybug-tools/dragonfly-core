# coding=utf-8
import pytest

from dragonfly.windowparameter import SingleWindow, SimpleWindowRatio, \
    RepeatingWindowRatio

from honeybee.face import Face

from ladybug_geometry.geometry3d.pointvector import Point3D, Vector3D
from ladybug_geometry.geometry3d.line import LineSegment3D
from ladybug_geometry.geometry3d.face import Face3D


def test_single_window_init():
    """Test the initalization of SingleWindow objects and basic properties."""
    simple_window = SingleWindow(5, 2, 0.8)
    str(simple_window)  # test the string representation

    assert simple_window.width == 5
    assert simple_window.height == 2
    assert simple_window.sill_height == 0.8


def test_single_window_equality():
    """Test the equality of SingleWindow objects."""
    simple_window = SingleWindow(5, 2, 0.8)
    simple_window_dup = simple_window.duplicate()
    simple_window_alt = SingleWindow(8, 2, 0.8)

    assert simple_window is simple_window
    assert simple_window is not simple_window_dup
    assert simple_window == simple_window_dup
    assert simple_window != simple_window_alt


def test_single_window_dict_methods():
    """Test the to/from dict methods."""
    simple_window = SingleWindow(5, 2, 0.8)

    glz_dict = simple_window.to_dict()
    new_simple_window = SingleWindow.from_dict(glz_dict)
    assert new_simple_window == simple_window
    assert glz_dict == new_simple_window.to_dict()


def test_single_window_scale():
    """Test the scale method."""
    simple_window = SingleWindow(5, 2, 0.8)

    new_simple_window  = simple_window.scale(2)
    assert new_simple_window.width == 10
    assert new_simple_window.height == 4
    assert new_simple_window.sill_height == 1.6


def test_single_window_add_window_to_face():
    """Test the add_window_to_face method."""
    simple_window = SingleWindow(5, 2, 0.8)
    height = 3
    width = 10
    seg = LineSegment3D.from_end_points(Point3D(0, 0, 2), Point3D(width, 0, 2))
    face = Face('test face', Face3D.from_extrusion(seg, Vector3D(0, 0, height)))
    simple_window.add_window_to_face(face, 0.01)

    assert len(face.apertures) == 1
    assert face.center.x == face.apertures[0].center.x
    assert face.center.y == face.apertures[0].center.y
    assert simple_window.area_from_segment(seg, height) == face.apertures[0].area == 10


def test_simple_window_ratio_init():
    """Test the initalization of SimpleWindowRatio objects and basic properties."""
    ashrae_base = SimpleWindowRatio(0.4)
    str(ashrae_base)  # test the string representation

    assert ashrae_base.window_ratio == 0.4


def test_simple_window_ratio_equality():
    """Test the equality of SimpleWindowRatio objects."""
    ashrae_base = SimpleWindowRatio(0.4)
    ashrae_base_dup = ashrae_base.duplicate()
    ashrae_base_alt = SimpleWindowRatio(0.25)

    assert ashrae_base is ashrae_base
    assert ashrae_base is not ashrae_base_dup
    assert ashrae_base == ashrae_base_dup
    assert ashrae_base != ashrae_base_alt


def test_simple_window_ratio_dict_methods():
    """Test the to/from dict methods."""
    ashrae_base = SimpleWindowRatio(0.4)

    glz_dict = ashrae_base.to_dict()
    new_ashrae_base = SimpleWindowRatio.from_dict(glz_dict)
    assert new_ashrae_base == ashrae_base
    assert glz_dict == new_ashrae_base.to_dict()


def test_simple_window_ratio_add_window_to_face():
    """Test the add_window_to_face method."""
    ashrae_base = SimpleWindowRatio(0.4)
    height = 3
    width = 10
    seg = LineSegment3D.from_end_points(Point3D(0, 0, 2), Point3D(width, 0, 2))
    face = Face('test face', Face3D.from_extrusion(seg, Vector3D(0, 0, height)))
    ashrae_base.add_window_to_face(face, 0.01)

    assert len(face.apertures) == 1
    assert face.center == face.apertures[0].center
    assert ashrae_base.area_from_segment(seg, height) == face.apertures[0].area == \
        width * height * 0.4


def test_repeating_window_ratio_init():
    """Test the initalization of RepeatingWindowRatio objects and basic properties."""
    ashrae_base = RepeatingWindowRatio(0.4, 2, 0.8, 3)
    str(ashrae_base)  # test the string representation

    assert ashrae_base.window_ratio == 0.4
    assert ashrae_base.window_height == 2
    assert ashrae_base.sill_height == 0.8
    assert ashrae_base.horizontal_separation == 3
    assert ashrae_base.vertical_separation == 0


def test_repeating_window_ratio_equality():
    """Test the equality of RepeatingWindowRatio objects."""
    ashrae_base = RepeatingWindowRatio(0.4, 2, 0.8, 3)
    ashrae_base_dup = ashrae_base.duplicate()
    ashrae_base_alt = RepeatingWindowRatio(0.25, 2, 0.8, 3)

    assert ashrae_base is ashrae_base
    assert ashrae_base is not ashrae_base_dup
    assert ashrae_base == ashrae_base_dup
    assert ashrae_base != ashrae_base_alt


def test_repeating_window_scale():
    """Test the scale method."""
    ashrae_base = RepeatingWindowRatio(0.4, 2, 0.8, 3)

    new_ashrae_base  = ashrae_base.scale(2)
    assert new_ashrae_base.window_ratio == ashrae_base.window_ratio
    assert new_ashrae_base.window_height == 4
    assert new_ashrae_base.sill_height == 1.6
    assert new_ashrae_base.horizontal_separation == 6


def test_repeating_window_ratio_dict_methods():
    """Test the to/from dict methods."""
    ashrae_base = RepeatingWindowRatio(0.4, 2, 0.8, 3)

    glz_dict = ashrae_base.to_dict()
    new_ashrae_base = RepeatingWindowRatio.from_dict(glz_dict)
    assert new_ashrae_base == ashrae_base
    assert glz_dict == new_ashrae_base.to_dict()


def test_repeating_window_ratio_add_window_to_face():
    """Test the add_window_to_face method."""
    ashrae_base = RepeatingWindowRatio(0.4, 2, 0.8, 3)
    height = 3
    width = 10
    seg = LineSegment3D.from_end_points(Point3D(0, 0, 2), Point3D(width, 0, 2))
    face = Face('test face', Face3D.from_extrusion(seg, Vector3D(0, 0, height)))
    ashrae_base.add_window_to_face(face, 0.01)

    assert len(face.apertures) == 3
    ap_area = sum([ap.area for ap in face.apertures])
    assert ashrae_base.area_from_segment(seg, height) == \
        pytest.approx(ap_area, rel=1e-3) == width * height * 0.4
