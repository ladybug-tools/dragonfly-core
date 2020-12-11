"""Test the ColorRoom and ColorFace classes."""
from dragonfly.room2d import Room2D
from dragonfly.colorobj import ColorRoom2D

from ladybug.graphic import GraphicContainer
from ladybug_geometry.geometry3d.pointvector import Point3D, Vector3D
from ladybug_geometry.geometry3d.plane import Plane
from ladybug_geometry.geometry3d.face import Face3D

import pytest


def test_color_room2d():
    """Test ColorRoom2D."""
    pts_1 = (Point3D(0, 0, 3), Point3D(10, 0, 3), Point3D(10, 10, 3), Point3D(0, 10, 3))
    pts_2 = (Point3D(10, 0, 3), Point3D(20, 0, 3), Point3D(20, 10, 3), Point3D(10, 10, 3))
    room2d_1 = Room2D('SouthZone', Face3D(pts_1), 3)
    room2d_2 = Room2D('NorthZone', Face3D(pts_2), 3)
    Room2D.solve_adjacency([room2d_1, room2d_2], 0.01)

    color_room1 = ColorRoom2D([room2d_1, room2d_2], 'display_name')
    color_room2 = ColorRoom2D([room2d_1, room2d_2], 'floor_area')
    
    assert len(color_room1.room_2ds) == len(color_room2.room_2ds) == 2
    assert color_room1.attr_name == color_room1.attr_name_end == 'display_name'
    assert color_room2.attr_name == color_room2.attr_name_end == 'floor_area'
    assert color_room1.attributes == ('SouthZone', 'NorthZone')
    assert color_room2.attributes == ('100.0', '100.0')
    assert isinstance(color_room1.graphic_container, GraphicContainer)
    assert len(color_room1.attributes_unique) == \
        len(color_room1.graphic_container.legend.segment_colors) == 2
    assert len(color_room2.attributes_unique) == \
        len(color_room2.graphic_container.legend.segment_colors) == 1
    assert len(color_room1.floor_faces) == len(color_room2.floor_faces) == 2
    assert isinstance(color_room1.min_point, Point3D)
    assert isinstance(color_room1.max_point, Point3D)
