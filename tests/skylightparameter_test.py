# coding=utf-8
import pytest

from dragonfly.skylightparameter import GriddedSkylightArea, GriddedSkylightRatio

from honeybee.face import Face

from ladybug_geometry.geometry3d.pointvector import Point3D
from ladybug_geometry.geometry3d.face import Face3D


def test_gridded_skylight_area_init():
    """Test the initialization of GriddedSkylightArea objects and basic properties."""
    ashrae_base = GriddedSkylightArea(4.5)
    str(ashrae_base)  # test the string representation

    assert ashrae_base.skylight_area == 4.5


def test_gridded_skylight_area_equality():
    """Test the equality of GriddedSkylightArea objects."""
    ashrae_base = GriddedSkylightArea(4.5)
    ashrae_base_dup = ashrae_base.duplicate()
    ashrae_base_alt = GriddedSkylightArea(2.5)

    assert ashrae_base is ashrae_base
    assert ashrae_base is not ashrae_base_dup
    assert ashrae_base == ashrae_base_dup
    assert hash(ashrae_base) == hash(ashrae_base_dup)
    assert ashrae_base != ashrae_base_alt
    assert hash(ashrae_base) != hash(ashrae_base_alt)


def test_gridded_skylight_area_dict_methods():
    """Test the to/from dict methods."""
    ashrae_base = GriddedSkylightArea(4.5)

    glz_dict = ashrae_base.to_dict()
    new_ashrae_base = GriddedSkylightArea.from_dict(glz_dict)
    assert new_ashrae_base == ashrae_base
    assert glz_dict == new_ashrae_base.to_dict()


def test_gridded_skylight_area_add_skylight_to_face():
    """Test the add_skylight_to_face method."""
    ashrae_base = GriddedSkylightArea(4.5)
    pts = (Point3D(0, 10, 3), Point3D(10, 10, 3), Point3D(10, 0, 3), Point3D(0, 0, 3))
    face = Face('test_face', Face3D(pts))
    ashrae_base.add_skylight_to_face(face, 0.01)

    assert len(face.apertures) > 0
    assert ashrae_base.area_from_face(face) == \
        pytest.approx(face.aperture_area, rel=1e-3) == \
        pytest.approx(4.5, rel=1e-3)


def test_gridded_skylight_ratio_init():
    """Test the initialization of GriddedSkylightRatio objects and basic properties."""
    ashrae_base = GriddedSkylightRatio(0.4)
    str(ashrae_base)  # test the string representation

    assert ashrae_base.skylight_ratio == 0.4


def test_gridded_skylight_ratio_equality():
    """Test the equality of GriddedSkylightRatio objects."""
    ashrae_base = GriddedSkylightRatio(0.4)
    ashrae_base_dup = ashrae_base.duplicate()
    ashrae_base_alt = GriddedSkylightRatio(0.25)

    assert ashrae_base is ashrae_base
    assert ashrae_base is not ashrae_base_dup
    assert ashrae_base == ashrae_base_dup
    assert hash(ashrae_base) == hash(ashrae_base_dup)
    assert ashrae_base != ashrae_base_alt
    assert hash(ashrae_base) != hash(ashrae_base_alt)


def test_gridded_skylight_ratio_dict_methods():
    """Test the to/from dict methods."""
    ashrae_base = GriddedSkylightRatio(0.4)

    glz_dict = ashrae_base.to_dict()
    new_ashrae_base = GriddedSkylightRatio.from_dict(glz_dict)
    assert new_ashrae_base == ashrae_base
    assert glz_dict == new_ashrae_base.to_dict()


def test_gridded_skylight_ratio_add_skylight_to_face():
    """Test the add_skylight_to_face method."""
    ashrae_base = GriddedSkylightRatio(0.4)
    pts = (Point3D(0, 10, 3), Point3D(10, 10, 3), Point3D(10, 0, 3), Point3D(0, 0, 3))
    face = Face('test_face', Face3D(pts))
    ashrae_base.add_skylight_to_face(face, 0.01)

    assert len(face.apertures) > 0
    assert ashrae_base.area_from_face(face) == \
        pytest.approx(face.aperture_area, rel=1e-3) == \
        pytest.approx(0.4 * face.area, rel=1e-3)

