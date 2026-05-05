# coding=utf-8
import pytest

from ladybug_geometry.geometry2d import Point2D, LineSegment2D, Polygon2D
from ladybug_geometry.geometry3d import Vector3D, LineSegment3D, Plane, Face3D
from honeybee.face import Face

from dragonfly.clearstoryparameter import DetailedClearstory


def test_detailed_init():
    """Test the initialization of DetailedClearstory and basic properties."""
    base_line = LineSegment2D.from_end_points(Point2D(10, 5), Point2D(10, 15))
    pts_1 = (Point2D(2, 1), Point2D(3, 1), Point2D(3, 2), Point2D(2, 2))
    pts_2 = (Point2D(5, 0.5), Point2D(8, 0.5), Point2D(8, 2.5), Point2D(5, 2.5))
    clearstory = DetailedClearstory(base_line, 5, (Polygon2D(pts_1), Polygon2D(pts_2)))
    str(clearstory)  # test the string representation

    assert clearstory.base_line == base_line
    assert clearstory.elevation == 5
    assert clearstory.polygons[0].vertices == pts_1
    assert clearstory.polygons[1].vertices == pts_2
    assert all(not is_door for is_door in clearstory.are_doors)
    assert isinstance(clearstory.base_line_3d, LineSegment3D)
    assert isinstance(clearstory.base_plane, Plane)
    assert clearstory.base_plane.o == clearstory.base_line_3d.p2


def test_detailed_equality():
    """Test the equality of DetailedClearstory."""
    base_line = LineSegment2D.from_end_points(Point2D(10, 5), Point2D(10, 15))
    pts_1 = (Point2D(2, 1), Point2D(3, 1), Point2D(3, 2), Point2D(2, 2))
    pts_2 = (Point2D(5, 0.5), Point2D(8, 0.5), Point2D(8, 2.5), Point2D(5, 2.5))
    clearstory = DetailedClearstory(base_line, 5, (Polygon2D(pts_1), Polygon2D(pts_2)))
    clearstory_dup = clearstory.duplicate()
    clearstory_alt = DetailedClearstory(base_line, 5, (Polygon2D(pts_1),))

    assert clearstory is clearstory
    assert clearstory is not clearstory_dup
    assert clearstory == clearstory_dup
    assert hash(clearstory) == hash(clearstory_dup)
    assert clearstory != clearstory_alt
    assert hash(clearstory) != hash(clearstory_alt)


def test_detailed_dict_methods():
    """Test the to/from dict methods."""
    base_line = LineSegment2D.from_end_points(Point2D(10, 5), Point2D(10, 15))
    pts_1 = (Point2D(2, 1), Point2D(3, 1), Point2D(3, 2), Point2D(2, 2))
    pts_2 = (Point2D(5, 0.5), Point2D(8, 0.5), Point2D(8, 2.5), Point2D(5, 2.5))
    clearstory = DetailedClearstory(base_line, 5, (Polygon2D(pts_1), Polygon2D(pts_2)))

    glz_dict = clearstory.to_dict()
    new_clearstory = DetailedClearstory.from_dict(glz_dict)
    assert new_clearstory == clearstory
    assert glz_dict == new_clearstory.to_dict()


def test_detailed_move():
    """Test the move method."""
    base_line = LineSegment2D.from_end_points(Point2D(10, 5), Point2D(10, 15))
    pts_1 = (Point2D(2, 1), Point2D(3, 1), Point2D(3, 2), Point2D(2, 2))
    pts_2 = (Point2D(5, 0.5), Point2D(8, 0.5), Point2D(8, 2.5), Point2D(5, 2.5))
    clearstory = DetailedClearstory(base_line, 5, (Polygon2D(pts_1), Polygon2D(pts_2)))

    m_vec = Vector3D(0, 10, 0)
    new_clearstory = clearstory.move(m_vec)
    assert new_clearstory.polygons == clearstory.polygons
    assert new_clearstory.base_line_3d == clearstory.base_line_3d.move(m_vec)


def test_detailed_scale():
    """Test the scale method."""
    base_line = LineSegment2D.from_end_points(Point2D(10, 5), Point2D(10, 15))
    pts_1 = (Point2D(2, 1), Point2D(3, 1), Point2D(3, 2), Point2D(2, 2))
    pts_2 = (Point2D(5, 0.5), Point2D(8, 0.5), Point2D(8, 2.5), Point2D(5, 2.5))
    clearstory = DetailedClearstory(base_line, 5, (Polygon2D(pts_1), Polygon2D(pts_2)))

    new_clearstory = clearstory.scale(2)
    assert new_clearstory.polygons[0].vertices == \
        (Point2D(4, 2), Point2D(6, 2), Point2D(6, 4), Point2D(4, 4))
    assert new_clearstory.polygons[1].vertices == \
        (Point2D(10, 1), Point2D(16, 1), Point2D(16, 5), Point2D(10, 5))
    assert new_clearstory.base_line.length == 2 * clearstory.base_line.length


def test_add_clearstory_to_face():
    """Test the add_clearstory_to_face method."""
    base_line = LineSegment2D.from_end_points(Point2D(10, 5), Point2D(10, 15))
    pts_1 = (Point2D(2, 1), Point2D(3, 1), Point2D(3, 2), Point2D(2, 2))
    pts_2 = (Point2D(5, 0.5), Point2D(8, 0.5), Point2D(8, 2.5), Point2D(5, 2.5))
    clearstory = DetailedClearstory(base_line, 5, (Polygon2D(pts_1), Polygon2D(pts_2)))
    height = 3
    seg = clearstory.base_line_3d
    face = Face('test_face', Face3D.from_extrusion(seg, Vector3D(0, 0, height)))
    clearstory.add_clearstory_to_face(face, 0.01)

    assert len(face.apertures) == 2
    assert len(face.apertures[0].vertices) == 4
    assert len(face.apertures[1].vertices) == 4

    new_clearstory = DetailedClearstory.from_honeybee(face.apertures)
    assert len(new_clearstory.polygons) == 2
    assert len(new_clearstory.polygons[0].vertices) == 4
    assert len(new_clearstory.polygons[1].vertices) == 4
    assert new_clearstory.base_line_3d.length < clearstory.base_line_3d.length

    original_aps = face.apertures
    face.remove_sub_faces()
    new_clearstory.add_clearstory_to_face(face, 0.01)

    assert len(face.apertures) == 2
    assert face.apertures[0].center.x == pytest.approx(original_aps[0].center.x, rel=1e-3)
    assert face.apertures[0].center.y == pytest.approx(original_aps[0].center.y, rel=1e-3)
    assert face.apertures[0].center.z == pytest.approx(original_aps[0].center.z, rel=1e-3)
    assert face.apertures[1].center.x == pytest.approx(original_aps[1].center.x, rel=1e-3)
    assert face.apertures[1].center.y == pytest.approx(original_aps[1].center.y, rel=1e-3)
    assert face.apertures[1].center.z == pytest.approx(original_aps[1].center.z, rel=1e-3)
    assert face.apertures[0].area == pytest.approx(original_aps[0].area, rel=1e-3)
    assert face.apertures[1].area == pytest.approx(original_aps[1].area, rel=1e-3)
