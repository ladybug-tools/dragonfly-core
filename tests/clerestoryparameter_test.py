# coding=utf-8
import pytest

from ladybug_geometry.geometry2d import Point2D, LineSegment2D, Polygon2D
from ladybug_geometry.geometry3d import Vector3D, LineSegment3D, Plane, Face3D
from honeybee.face import Face

from dragonfly.clerestoryparameter import DetailedClerestory


def test_detailed_init():
    """Test the initialization of DetailedClerestory and basic properties."""
    base_line = LineSegment2D.from_end_points(Point2D(10, 5), Point2D(10, 15))
    pts_1 = (Point2D(2, 1), Point2D(3, 1), Point2D(3, 2), Point2D(2, 2))
    pts_2 = (Point2D(5, 0.5), Point2D(8, 0.5), Point2D(8, 2.5), Point2D(5, 2.5))
    clerestory = DetailedClerestory(base_line, 5, (Polygon2D(pts_1), Polygon2D(pts_2)))
    str(clerestory)  # test the string representation

    assert clerestory.base_line == base_line
    assert clerestory.elevation == 5
    assert clerestory.polygons[0].vertices == pts_1
    assert clerestory.polygons[1].vertices == pts_2
    assert all(not is_door for is_door in clerestory.are_doors)
    assert isinstance(clerestory.base_line_3d, LineSegment3D)
    assert isinstance(clerestory.base_plane, Plane)
    assert clerestory.base_plane.o == clerestory.base_line_3d.p2


def test_detailed_equality():
    """Test the equality of DetailedClerestory."""
    base_line = LineSegment2D.from_end_points(Point2D(10, 5), Point2D(10, 15))
    pts_1 = (Point2D(2, 1), Point2D(3, 1), Point2D(3, 2), Point2D(2, 2))
    pts_2 = (Point2D(5, 0.5), Point2D(8, 0.5), Point2D(8, 2.5), Point2D(5, 2.5))
    clerestory = DetailedClerestory(base_line, 5, (Polygon2D(pts_1), Polygon2D(pts_2)))
    clerestory_dup = clerestory.duplicate()
    clerestory_alt = DetailedClerestory(base_line, 5, (Polygon2D(pts_1),))

    assert clerestory is clerestory
    assert clerestory is not clerestory_dup
    assert clerestory == clerestory_dup
    assert hash(clerestory) == hash(clerestory_dup)
    assert clerestory != clerestory_alt
    assert hash(clerestory) != hash(clerestory_alt)


def test_detailed_dict_methods():
    """Test the to/from dict methods."""
    base_line = LineSegment2D.from_end_points(Point2D(10, 5), Point2D(10, 15))
    pts_1 = (Point2D(2, 1), Point2D(3, 1), Point2D(3, 2), Point2D(2, 2))
    pts_2 = (Point2D(5, 0.5), Point2D(8, 0.5), Point2D(8, 2.5), Point2D(5, 2.5))
    clerestory = DetailedClerestory(base_line, 5, (Polygon2D(pts_1), Polygon2D(pts_2)))

    glz_dict = clerestory.to_dict()
    new_clerestory = DetailedClerestory.from_dict(glz_dict)
    assert new_clerestory == clerestory
    assert glz_dict == new_clerestory.to_dict()


def test_detailed_move():
    """Test the move method."""
    base_line = LineSegment2D.from_end_points(Point2D(10, 5), Point2D(10, 15))
    pts_1 = (Point2D(2, 1), Point2D(3, 1), Point2D(3, 2), Point2D(2, 2))
    pts_2 = (Point2D(5, 0.5), Point2D(8, 0.5), Point2D(8, 2.5), Point2D(5, 2.5))
    clerestory = DetailedClerestory(base_line, 5, (Polygon2D(pts_1), Polygon2D(pts_2)))

    m_vec = Vector3D(0, 10, 0)
    new_clerestory = clerestory.move(m_vec)
    assert new_clerestory.polygons == clerestory.polygons
    assert new_clerestory.base_line_3d == clerestory.base_line_3d.move(m_vec)


def test_detailed_scale():
    """Test the scale method."""
    base_line = LineSegment2D.from_end_points(Point2D(10, 5), Point2D(10, 15))
    pts_1 = (Point2D(2, 1), Point2D(3, 1), Point2D(3, 2), Point2D(2, 2))
    pts_2 = (Point2D(5, 0.5), Point2D(8, 0.5), Point2D(8, 2.5), Point2D(5, 2.5))
    clerestory = DetailedClerestory(base_line, 5, (Polygon2D(pts_1), Polygon2D(pts_2)))

    new_clerestory = clerestory.scale(2)
    assert new_clerestory.polygons[0].vertices == \
        (Point2D(4, 2), Point2D(6, 2), Point2D(6, 4), Point2D(4, 4))
    assert new_clerestory.polygons[1].vertices == \
        (Point2D(10, 1), Point2D(16, 1), Point2D(16, 5), Point2D(10, 5))
    assert new_clerestory.base_line.length == 2 * clerestory.base_line.length


def test_add_clerestory_to_face():
    """Test the add_clerestory_to_face method."""
    base_line = LineSegment2D.from_end_points(Point2D(10, 5), Point2D(10, 15))
    pts_1 = (Point2D(2, 1), Point2D(3, 1), Point2D(3, 2), Point2D(2, 2))
    pts_2 = (Point2D(5, 0.5), Point2D(8, 0.5), Point2D(8, 2.5), Point2D(5, 2.5))
    clerestory = DetailedClerestory(base_line, 5, (Polygon2D(pts_1), Polygon2D(pts_2)))
    height = 3
    seg = clerestory.base_line_3d
    face = Face('test_face', Face3D.from_extrusion(seg, Vector3D(0, 0, height)))
    clerestory.add_clerestory_to_face(face, 0.01)

    assert len(face.apertures) == 2
    assert len(face.apertures[0].vertices) == 4
    assert len(face.apertures[1].vertices) == 4

    new_clerestory = DetailedClerestory.from_honeybee(face.apertures)
    assert len(new_clerestory.polygons) == 2
    assert len(new_clerestory.polygons[0].vertices) == 4
    assert len(new_clerestory.polygons[1].vertices) == 4
    assert new_clerestory.base_line_3d.length < clerestory.base_line_3d.length

    original_aps = face.apertures
    face.remove_sub_faces()
    new_clerestory.add_clerestory_to_face(face, 0.01)

    assert len(face.apertures) == 2
    assert face.apertures[0].center.x == pytest.approx(original_aps[0].center.x, rel=1e-3)
    assert face.apertures[0].center.y == pytest.approx(original_aps[0].center.y, rel=1e-3)
    assert face.apertures[0].center.z == pytest.approx(original_aps[0].center.z, rel=1e-3)
    assert face.apertures[1].center.x == pytest.approx(original_aps[1].center.x, rel=1e-3)
    assert face.apertures[1].center.y == pytest.approx(original_aps[1].center.y, rel=1e-3)
    assert face.apertures[1].center.z == pytest.approx(original_aps[1].center.z, rel=1e-3)
    assert face.apertures[0].area == pytest.approx(original_aps[0].area, rel=1e-1)
    assert face.apertures[1].area == pytest.approx(original_aps[1].area, rel=1e-1)
