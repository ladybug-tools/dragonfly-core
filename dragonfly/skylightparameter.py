# coding: utf-8
"""Skylight Parameters with instructions for generating skylights."""
from __future__ import division
import math
import sys
if (sys.version_info < (3, 0)):  # python 2
    from itertools import izip as zip  # python 2

from ladybug_geometry.geometry2d import Point2D, Vector2D, Polygon2D
from ladybug_geometry.geometry3d import Vector3D, Point3D, Face3D
from ladybug_geometry.bounding import bounding_rectangle

from honeybee.typing import float_in_range, float_positive
from honeybee.altnumber import autocalculate
from honeybee.aperture import Aperture
from honeybee.door import Door


class _SkylightParameterBase(object):
    """Base object for all Skylight parameters.

    This object records the minimum number of the methods that must be overwritten
    on a skylight parameter object for it to be successfully be applied in
    dragonfly workflows.
    """
    __slots__ = ()

    def __init__(self):
        pass

    def area_from_face(self, face):
        """Get the skylight area generated by these parameters from a Room2D Face3D."""
        return 0

    def add_skylight_to_face(self, face, tolerance=0.01):
        """Add Apertures to a Honeybee Roof Face using these Skylight Parameters."""
        pass

    def scale(self, factor):
        """Get a scaled version of these SkylightParameters.

        This method is called within the scale methods of the Room2D.

        Args:
            factor: A number representing how much the object should be scaled.
        """
        return self

    @classmethod
    def from_dict(cls, data):
        """Create SkylightParameterBase from a dictionary.

        .. code-block:: python

            {
            "type": "SkylightParameterBase"
            }
        """
        assert data['type'] == 'SkylightParameterBase', \
            'Expected SkylightParameterBase dictionary. Got {}.'.format(data['type'])
        return cls()

    def to_dict(self):
        """Get SkylightParameterBase as a dictionary."""
        return {'type': 'SkylightParameterBase'}

    def duplicate(self):
        """Get a copy of this object."""
        return self.__copy__()

    def ToString(self):
        return self.__repr__()

    def __copy__(self):
        return _SkylightParameterBase()

    def __repr__(self):
        return 'SkylightParameterBase'


class GriddedSkylightArea(_SkylightParameterBase):
    """Instructions for gridded skylights defined by an absolute area.

    Args:
        skylight_area: A number for the skylight area in current model units.
            If this area is larger than the area of the roof that it is applied
            to, the skylight will fill the parent roof at a 99% ratio.
        spacing: A number for the spacing between the centers of each grid cell.
            This should be less than a third of the dimension of the Roof geometry
            if multiple, evenly-spaced skylights are desired. If None or Autocalculate,
            a spacing of one third the smaller dimension of the parent Roof will
            be automatically assumed. (Default: Autocalculate).

    Properties:
        * skylight_area
        * spacing
    """
    __slots__ = ('_skylight_area', '_spacing')

    def __init__(self, skylight_area, spacing=autocalculate):
        """Initialize GriddedSkylightArea."""
        self._skylight_area = float_positive(skylight_area, 'skylight area')
        if spacing == autocalculate:
            spacing = None
        elif spacing is not None:
            spacing = float_positive(spacing, 'skylight spacing')
            assert spacing > 0, 'GriddedSkylightArea spacing must be greater than zero.'
        self._spacing = spacing

    @property
    def skylight_area(self):
        """Get a number for the skylight area in current model units."""
        return self._skylight_area

    @property
    def spacing(self):
        """Get a number or the spacing between the skylights.

        None indicates that the spacing will always be one third of the smaller
        dimension of the parent Roof.
        """
        return self._spacing

    def area_from_face(self, face):
        """Get the skylight area generated by these parameters from a Room2D Face3D.

        Args:
            face: A Roof Face3D to which these parameters are applied.
        """
        return self._skylight_area

    def add_skylight_to_face(self, face, tolerance=0.01):
        """Add Apertures to a Honeybee Roof Face using these Skylight Parameters.

        Args:
            face: A honeybee-core Face object.
            tolerance: The maximum difference between point values for them to be
                considered distinct. (Default: 0.01, suitable for objects in meters).
        """
        if self._skylight_area == 0:
            return None
        spacing = self.spacing
        if self.spacing is None:
            min_pt, max_pt = face.min, face.max
            min_dim = min(max_pt.x - min_pt.x, max_pt.y - min_pt.y)
            spacing = (min_dim / 3) - tolerance
        skylight_ratio = self.skylight_area / face.area
        skylight_ratio = 0.99 if skylight_ratio > 0.99 else skylight_ratio
        face.apertures_by_ratio_gridded(
            skylight_ratio, spacing, tolerance=tolerance)

    def scale(self, factor):
        """Get a scaled version of these SkylightParameters.

        This method is called within the scale methods of the Room2D.

        Args:
            factor: A number representing how much the object should be scaled.
        """
        spc = self.spacing * factor if self.spacing is not None else None
        return GriddedSkylightArea(self.skylight_area * factor, spc)

    @classmethod
    def from_dict(cls, data):
        """Create GriddedSkylightArea from a dictionary.

        .. code-block:: python

            {
            "type": "GriddedSkylightArea",
            "skylight_area": 2.5,
            "spacing": 2
            }
        """
        assert data['type'] == 'GriddedSkylightArea', \
            'Expected GriddedSkylightArea dictionary. Got {}.'.format(data['type'])
        spc = data['spacing'] if 'spacing' in data and \
            data['spacing'] != autocalculate.to_dict() else None
        return cls(data['skylight_area'], spc)

    def to_dict(self):
        """Get GriddedSkylightArea as a dictionary."""
        base = {'type': 'GriddedSkylightArea', 'skylight_area': self.skylight_area}
        if self.spacing is not None:
            base['spacing'] = self.spacing
        return base

    def __copy__(self):
        return GriddedSkylightArea(
            self.skylight_area, self.spacing)

    def __key(self):
        """A tuple based on the object properties, useful for hashing."""
        return (self.skylight_area, self.spacing)

    def __hash__(self):
        return hash(self.__key())

    def __eq__(self, other):
        return isinstance(other, GriddedSkylightArea) and self.__key() == other.__key()

    def __ne__(self, other):
        return not self.__eq__(other)

    def __repr__(self):
        return 'GriddedSkylightArea: [area: {}]'.format(self.skylight_area)


class GriddedSkylightRatio(_SkylightParameterBase):
    """Instructions for gridded skylights derived from an area ratio with the roof.

    Args:
        skylight_ratio: A number between 0 and 1 for the ratio between the skylight
            area and the total Roof face area.
        spacing: A number for the spacing between the centers of each grid cell.
            This should be less than a third of the dimension of the Roof geometry
            if multiple, evenly-spaced skylights are desired. If None or Autocalculate,
            a spacing of one third the smaller dimension of the parent Roof will
            be automatically assumed. (Default: Autocalculate).

    Properties:
        * skylight_ratio
        * spacing
    """
    __slots__ = ('_skylight_ratio', '_spacing')

    def __init__(self, skylight_ratio, spacing=autocalculate):
        """Initialize GriddedSkylightRatio."""
        self._skylight_ratio = float_in_range(skylight_ratio, 0, 1.0, 'skylight ratio')
        if spacing == autocalculate:
            spacing = None
        elif spacing is not None:
            spacing = float_positive(spacing, 'skylight spacing')
            assert spacing > 0, 'GriddedSkylightRatio spacing must be greater than zero.'
        self._spacing = spacing

    @property
    def skylight_ratio(self):
        """Get a number between 0 and 1 for the skylight ratio."""
        return self._skylight_ratio

    @property
    def spacing(self):
        """Get a number or the spacing between the skylights.

        None indicates that the spacing will always be one third of the smaller
        dimension of the parent Roof.
        """
        return self._spacing

    def area_from_face(self, face):
        """Get the skylight area generated by these parameters from a Room2D Face3D.

        Args:
            face: A Roof Face3D to which these parameters are applied.
        """
        return face.area * self._skylight_ratio

    def add_skylight_to_face(self, face, tolerance=0.01):
        """Add Apertures to a Honeybee Roof Face using these Skylight Parameters.

        Args:
            face: A honeybee-core Face object.
            tolerance: The maximum difference between point values for them to be
                considered distinct. (Default: 0.01, suitable for objects in meters).
        """
        if self._skylight_ratio == 0:
            return None
        spacing = self.spacing
        if self.spacing is None:
            min_pt, max_pt = face.min, face.max
            min_dim = min(max_pt.x - min_pt.x, max_pt.y - min_pt.y)
            spacing = (min_dim / 3) - tolerance
        face.apertures_by_ratio_gridded(
            self.skylight_ratio, spacing, tolerance=tolerance)

    def scale(self, factor):
        """Get a scaled version of these SkylightParameters.

        This method is called within the scale methods of the Room2D.

        Args:
            factor: A number representing how much the object should be scaled.
        """
        spc = self.spacing * factor if self.spacing is not None else None
        return GriddedSkylightRatio(self.skylight_ratio, spc)

    @classmethod
    def from_dict(cls, data):
        """Create GriddedSkylightRatio from a dictionary.

        .. code-block:: python

            {
            "type": "GriddedSkylightRatio",
            "skylight_ratio": 0.05,
            "spacing": 2
            }
        """
        assert data['type'] == 'GriddedSkylightRatio', \
            'Expected GriddedSkylightRatio dictionary. Got {}.'.format(data['type'])
        spc = data['spacing'] if 'spacing' in data and \
            data['spacing'] != autocalculate.to_dict() else None
        return cls(data['skylight_ratio'], spc)

    def to_dict(self):
        """Get GriddedSkylightRatio as a dictionary."""
        base = {'type': 'GriddedSkylightRatio', 'skylight_ratio': self.skylight_ratio}
        if self.spacing is not None:
            base['spacing'] = self.spacing
        return base

    def __copy__(self):
        return GriddedSkylightRatio(
            self.skylight_ratio, self.spacing)

    def __key(self):
        """A tuple based on the object properties, useful for hashing."""
        return (self.skylight_ratio, self.spacing)

    def __hash__(self):
        return hash(self.__key())

    def __eq__(self, other):
        return isinstance(other, GriddedSkylightRatio) and self.__key() == other.__key()

    def __ne__(self, other):
        return not self.__eq__(other)

    def __repr__(self):
        return 'GriddedSkylightRatio: [ratio: {}]'.format(self.skylight_ratio)


class DetailedSkylights(_SkylightParameterBase):
    """Instructions for detailed skylights, defined by 2D Polygons (lists of 2D vertices).

    Note that these parameters are intended to represent skylights that are specific
    to a particular Room2D and, unlike the other SkylightsParameters, this class
    performs no automatic checks to ensure that the skylights lie within the
    boundary of the Roof that they are assigned to.

    Args:
        polygons: An array of ladybug_geometry Polygon2D objects in world XY
            coordinates with one polygon for each skylight. These coordinate
            values should lie within the Room2D's Polygon2D.
        are_doors: An array of booleans that align with the polygons and note whether
            each of the polygons represents an overhead door (True) or a skylight
            (False). If None, it will be assumed that all polygons represent skylights
            and they will be translated to Apertures in any resulting Honeybee
            model. (Default: None).

    Properties:
        * polygons
        * are_doors
    """
    __slots__ = ('_polygons', '_are_doors')

    def __init__(self, polygons, are_doors=None):
        """Initialize DetailedSkylights."""
        if not isinstance(polygons, tuple):
            polygons = tuple(polygons)
        for polygon in polygons:
            assert isinstance(polygon, Polygon2D), \
                'Expected Polygon2D for skylight polygon. Got {}'.format(type(polygon))
        assert len(polygons) != 0, \
            'There must be at least one polygon to use DetailedSkylights.'
        self._polygons = polygons
        if are_doors is None:
            self._are_doors = (False,) * len(polygons)
        else:
            if not isinstance(are_doors, tuple):
                are_doors = tuple(are_doors)
            for is_dr in are_doors:
                assert isinstance(is_dr, bool), 'Expected booleans for ' \
                    'DetailedSkylights.are_doors. Got {}'.format(type(is_dr))
            assert len(are_doors) == len(polygons), \
                'Length of DetailedSkylights.are_doors ({}) does not match the length ' \
                'of DetailedSkylights.polygons ({}).'.format(
                    len(are_doors), len(polygons))
            self._are_doors = are_doors

    @property
    def polygons(self):
        """Get an array of Polygon2Ds with one polygon for each skylight."""
        return self._polygons

    @property
    def are_doors(self):
        """Get an array of booleans that note whether each polygon is a door."""
        return self._are_doors

    def area_from_face(self, face):
        """Get the skylight area generated by these parameters from a Room2D Face3D.

        Args:
            face: A Roof Face3D to which these parameters are applied.
        """
        return sum(polygon.area for polygon in self._polygons)

    def check_overlaps(self, tolerance=0.01):
        """Check whether any polygons overlap with one another.

        Args:
            tolerance: The minimum distance that two polygons must overlap in order
                for them to be considered overlapping and invalid. (Default: 0.01,
                suitable for objects in meters).

        Returns:
            A string with the message. Will be an empty string if valid.
        """
        # group the polygons according to their overlaps
        grouped_polys = Polygon2D.group_by_overlap(self.polygons, tolerance)
        # report any polygons that overlap
        if not all(len(g) == 1 for g in grouped_polys):
            base_msg = '({} skylights overlap one another)'
            all_msg = []
            for p_group in grouped_polys:
                if len(p_group) != 1:
                    all_msg.append(base_msg.format(len(p_group)))
            return ' '.join(all_msg)
        return ''

    def check_self_intersecting(self, tolerance=0.01):
        """Check whether any polygons in these skylight parameters are self intersecting.

        Args:
            tolerance: The minimum distance between a vertex coordinates where
                they are considered equivalent. (Default: 0.01, suitable
                for objects in meters).

        Returns:
            A string with the message. Will be an empty string if valid.
        """
        self_int_i = []
        for i, polygon in enumerate(self.polygons):
            if polygon.is_self_intersecting:
                new_geo = polygon.remove_colinear_vertices(tolerance)
                if new_geo.is_self_intersecting:
                    self_int_i.append(str(i))
        if len(self_int_i) != 0:
            return 'Skylight polygons with the following indices are ' \
                'self-intersecting: ({})'.format(' '.join(self_int_i))
        return ''

    def check_valid_for_face(self, face):
        """Check that these skylight parameters are valid for a given Face3D.

        Args:
            face: A Roof Face3D to which these parameters are applied.

        Returns:
            A string with the message. Will be an empty string if valid.
        """
        # first check that the total skylight area isn't larger than the roof
        total_area = face.area
        win_area = self.area_from_face(face)
        if win_area >= total_area:
            return 'Total area of skylights [{}] is greater than the area of the ' \
                'parent roof [{}].'.format(win_area, total_area)
        # next, check to be sure that no skylight is out of the roof boundary
        msg_template = 'Skylight polygon {} is outside the range allowed ' \
            'by the parent roof.'
        verts2d = tuple(Point2D(pt.x, pt.y) for pt in face.boundary)
        parent_poly, parent_holes = Polygon2D(verts2d), None
        if face.has_holes:
            parent_holes = tuple(
                Polygon2D(Point2D(pt.x, pt.y) for pt in hole)
                for hole in face.holes
            )
        for i, p_gon in enumerate(self.polygons):
            if not self._is_sub_polygon(p_gon, parent_poly, parent_holes):
                return msg_template.format(i)
        return ''

    def offset_polygons_for_face(self, face_3d, offset_distance=0.05, tolerance=0.01):
        """Offset the polygons until all vertices are inside the boundaries of a Face3D.

        Args:
            face_3d: A horizontal Face3D representing the floor geometry of a Room2D
                to which these skylight parameters are assigned.
            offset_distance: Distance from the edge of the face_3d that
                the polygons will be offset to. (Default: 0.05, suitable for
                objects in meters).
            tolerance: The maximum difference between point values for them to be
                considered distinct. (Default: 0.01, suitable for objects in meters).
        """
        # get the polygons that represent the roof face
        face_z = face_3d[0].z
        verts2d = tuple(Point2D(pt.x, pt.y) for pt in face_3d.boundary)
        parent_poly, parent_holes = Polygon2D(verts2d), None
        if face_3d.has_holes:
            parent_holes = tuple(
                Polygon2D(Point2D(pt.x, pt.y) for pt in hole)
                for hole in face_3d.holes
            )
        # loop through the polygons and offset them if they are not correctly bounded
        new_polygons, new_are_doors = [], []
        for polygon, isd in zip(self.polygons, self.are_doors):
            if not self._is_sub_polygon(polygon, parent_poly, parent_holes):
                # find the boolean intersection of the polygon with the room
                sub_face = Face3D([Point3D.from_point2d(pt, face_z) for pt in polygon])
                bool_int = Face3D.coplanar_intersection(
                    face_3d, sub_face, tolerance, math.radians(1))
                if bool_int is None:  # skylight completely outside parent
                    continue
                # offset the result of the boolean intersection from the edge
                parent_edges = face_3d.boundary_segments if face_3d.holes is None \
                    else face_3d.boundary_segments + \
                    tuple(seg for hole in face_3d.hole_segments for seg in hole)
                for new_f in bool_int:
                    new_pts_2d = []
                    for pt in new_f.boundary:
                        for edge in parent_edges:
                            close_pt = edge.closest_point(pt)
                            if pt.distance_to_point(close_pt) < offset_distance:
                                move_vec = edge.v.rotate_xy(math.pi / 2).normalize()
                                move_vec = move_vec * offset_distance
                                pt = pt.move(move_vec)
                        new_pts_2d.append(Point2D(pt.x, pt.y))
                    new_polygons.append(Polygon2D(new_pts_2d))
            else:
                new_polygons.append(polygon)
                new_are_doors.append(isd)
        # assign the offset polygons to this face
        self._polygons = tuple(new_polygons)
        self._are_doors = tuple(new_are_doors)

    def add_skylight_to_face(self, face, tolerance=0.01):
        """Add Apertures to a Honeybee Roof Face using these Skylight Parameters.

        Args:
            face: A honeybee-core Face object.
            tolerance: The maximum difference between point values for them to be
                considered distinct. (Default: 0.01, suitable for objects in meters).
        """
        # get the polygons that represent the roof face
        verts2d = tuple(Point2D(pt.x, pt.y) for pt in face.geometry.boundary)
        parent_poly, parent_holes = Polygon2D(verts2d), None
        if face.geometry.has_holes:
            parent_holes = tuple(
                Polygon2D(Point2D(pt.x, pt.y) for pt in hole)
                for hole in face.geometry.holes
            )
        # loop through each polygon and create its geometry
        p_dir = Vector3D(0, 0, 1)
        for i, (polygon, isd) in enumerate(zip(self.polygons, self.are_doors)):
            pt_in_poly = polygon.center if polygon.is_convex else \
                polygon.pole_of_inaccessibility(tolerance)
            if not self._is_sub_point(pt_in_poly, parent_poly, parent_holes):
                continue
            pt3d = tuple(
                face.geometry.plane.project_point(Point3D(p.x, p.y, 0), p_dir)
                for p in polygon)
            s_geo = Face3D(pt3d)
            if isd:
                sub_f = Door('{}_Door{}'.format(face.identifier, i + 1), s_geo)
                face.add_door(sub_f)
            else:
                sub_f = Aperture('{}_Glz{}'.format(face.identifier, i + 1), s_geo)
                face.add_aperture(sub_f)

    def move(self, moving_vec):
        """Get this DetailedSkylights moved along a vector.

        Args:
            moving_vec: A Vector3D with the direction and distance to move the polygon.
        """
        vec2 = Vector2D(moving_vec.x, moving_vec.y)
        return DetailedSkylights(
            tuple(polygon.move(vec2) for polygon in self.polygons),
            self.are_doors)

    def scale(self, factor, origin=None):
        """Get a scaled version of these DetailedSkylights.

        This method is called within the scale methods of the Room2D.

        Args:
            factor: A number representing how much the object should be scaled.
            origin: A ladybug_geometry Point3D representing the origin from which
                to scale. If None, it will be scaled from the World origin (0, 0, 0).
        """
        ori = Point2D(origin.x, origin.y) if origin is not None else None
        return DetailedSkylights(
            tuple(polygon.scale(factor, ori) for polygon in self.polygons),
            self.are_doors)

    def rotate(self, angle, origin):
        """Get these DetailedSkylights rotated counterclockwise in the XY plane.

        Args:
            angle: An angle in degrees.
            origin: A ladybug_geometry Point3D for the origin around which the
                object will be rotated.
        """
        ori, ang = Point2D(origin.x, origin.y), math.radians(angle)
        return DetailedSkylights(
            tuple(polygon.rotate(ang, ori) for polygon in self.polygons),
            self.are_doors)

    def reflect(self, plane):
        """Get a reflected version of these DetailedSkylights across a plane.

        Args:
            plane: A ladybug_geometry Plane across which the object will be reflected.
        """
        # get the plane normal and origin in 2D space
        normal = Vector2D(plane.n.x, plane.n.y)
        origin = Point2D(plane.o.x, plane.o.y)
        # loop through the polygons and reflect them across the plane
        new_polygons = []
        for polygon in self.polygons:
            new_verts = tuple(pt.reflect(normal, origin) for pt in polygon.vertices)
            new_polygons.append(Polygon2D(tuple(reversed(new_verts))))
        return DetailedSkylights(new_polygons, self.are_doors)

    def union_overlaps(self, tolerance=0.01):
        """Union any skylight polygons that overlap with one another.

        Args:
            tolerance: The minimum distance that two polygons must overlap in order
                for them to be considered overlapping. (Default: 0.01,
                suitable for objects in meters).
        """
        # group the polygons by their overlap
        grouped_polys = Polygon2D.group_by_overlap(self.polygons, tolerance)
        # union any of the polygons that overlap
        if not all(len(g) == 1 for g in grouped_polys):
            new_polys = []
            for p_group in grouped_polys:
                if len(p_group) == 1:
                    new_polys.append(p_group[0])
                else:
                    union_poly = Polygon2D.boolean_union_all(p_group, tolerance)
                    for new_poly in union_poly:
                        new_polys.append(new_poly.remove_colinear_vertices(tolerance))
            self._reassign_are_doors(new_polys)
            self._polygons = tuple(new_polys)

    def merge_and_simplify(self, max_separation, tolerance=0.01):
        """Merge skylight polygons that are close to one another into a single polygon.

        This can be used to create a simpler set of skylights that is easier to
        edit and is in the same location as the original skylights.

        Args:
            max_separation: A number for the maximum distance between skylight polygons
                at which point they will be merged into a single geometry. Typically,
                this max_separation should be set to a value that is slightly larger
                than the window frame. Setting this equal to the tolerance will
                simply join neighboring skylights together.
            tolerance: The maximum difference between point values for them to be
                considered distinct. (Default: 0.01, suitable for objects in meters).
        """
        # gather a clean version of the polygons with colinear vertices removed
        clean_polys = []
        for poly in self.polygons:
            try:
                clean_polys.append(poly.remove_colinear_vertices(tolerance))
            except AssertionError:  # degenerate geometry to ignore
                pass
        # join the polygons together
        if max_separation <= tolerance:
            new_polys = Polygon2D.joined_intersected_boundary(
                clean_polys, tolerance)
        else:
            new_polys = Polygon2D.gap_crossing_boundary(
                clean_polys, max_separation, tolerance)
        self._reassign_are_doors(new_polys)
        self._polygons = tuple(new_polys)

    def merge_to_bounding_rectangle(self, tolerance=0.01):
        """Merge skylight polygons that touch or overlap with one another to a rectangle.

        Args:
            tolerance: The minimum distance from the edge of a neighboring polygon
                at which a point is considered to touch that polygon. (Default: 0.01,
                suitable for objects in meters).
        """
        # group the polygons by their overlap
        grouped_polys = Polygon2D.group_by_touching(self.polygons, tolerance)
        # union any of the polygons that overlap
        if not all(len(g) == 1 for g in grouped_polys):
            new_polys = []
            for p_group in grouped_polys:
                if len(p_group) == 1:
                    new_polys.append(p_group[0])
                else:
                    min_pt, max_pt = bounding_rectangle(p_group)
                    rect_verts = (
                        min_pt, Point2D(max_pt.x, min_pt.y),
                        max_pt, Point2D(min_pt.x, max_pt.y))
                    rect_poly = Polygon2D(rect_verts)
                    new_polys.append(rect_poly)
            self._reassign_are_doors(new_polys)
            self._polygons = tuple(new_polys)

    @classmethod
    def from_dict(cls, data):
        """Create DetailedSkylights from a dictionary.

        Args:
            data: A dictionary in the format below.

        .. code-block:: python

            {
            "type": "DetailedSkylights",
            "polygons": [((0.5, 0.5), (2, 0.5), (2, 2), (0.5, 2)),
                         ((3, 1), (4, 1), (4, 2))],
            "are_doors": [False]
            }
        """
        assert data['type'] == 'DetailedSkylights', \
            'Expected DetailedSkylights dictionary. Got {}.'.format(data['type'])
        are_doors = data['are_doors'] if 'are_doors' in data else None
        return cls(
            tuple(Polygon2D(tuple(Point2D.from_array(pt) for pt in poly))
                  for poly in data['polygons']),
            are_doors
        )

    def to_dict(self):
        """Get DetailedSkylights as a dictionary."""
        return {
            'type': 'DetailedSkylights',
            'polygons': [[pt.to_array() for pt in poly] for poly in self.polygons],
            'are_doors': self.are_doors
        }

    def _reassign_are_doors(self, new_polys):
        """Reset the are_doors property using a set of new polygons."""
        if len(new_polys) != len(self._polygons):
            if all(not dr for dr in self._are_doors):  # common case of no overhead doors
                self._are_doors = (False,) * len(new_polys)
            else:
                new_are_doors = []
                for n_poly in new_polys:
                    for o_poly, is_door in zip(self.polygons, self.are_doors):
                        if n_poly.is_point_inside_bound_rect(o_poly.center):
                            new_are_doors.append(is_door)
                            break
                    else:
                        new_are_doors.append(False)
                self._are_doors = tuple(new_are_doors)

    @staticmethod
    def _is_sub_polygon(sub_poly, parent_poly, parent_holes=None):
        """Check if a sub-polygon is valid for a given assumed parent polygon.

        Args:
            sub_poly: A sub-Polygon2D for which sub-face equivalency will be tested.
            parent_poly: A parent Polygon2D.
            parent_holes: An optional list of Polygon2D for any holes that may
                exist in the parent polygon. (Default: None).
        """
        if parent_holes is None:
            return parent_poly.is_polygon_inside(sub_poly)
        else:
            if not parent_poly.is_polygon_inside(sub_poly):
                return False
            for hole_poly in parent_holes:
                if not hole_poly.is_polygon_outside(sub_poly):
                    return False
            return True

    @staticmethod
    def _is_sub_point(sub_point, parent_poly, parent_holes=None):
        """Check if a point lies inside a parent polygon.

        Args:
            sub_point: A Point2D which will be checked if it lies inside the parent.
            parent_poly: A parent Polygon2D.
            parent_holes: An optional list of Polygon2D for any holes that may
                exist in the parent polygon. (Default: None).
        """
        if parent_holes is None:
            return parent_poly.is_point_inside(sub_point)
        else:
            if not parent_poly.is_point_inside(sub_point):
                return False
            for hole_poly in parent_holes:
                if hole_poly.is_point_inside(sub_point):
                    return False
            return True

    def __len__(self):
        return len(self._polygons)

    def __getitem__(self, key):
        return self._polygons[key]

    def __iter__(self):
        return iter(self._polygons)

    def __copy__(self):
        return DetailedSkylights(self._polygons, self._are_doors)

    def __key(self):
        """A tuple based on the object properties, useful for hashing."""
        return tuple(hash(polygon) for polygon in self._polygons) + self.are_doors

    def __hash__(self):
        return hash(self.__key())

    def __eq__(self, other):
        return isinstance(other, DetailedSkylights) and \
            len(self._polygons) == len(other._polygons)

    def __ne__(self, other):
        return not self.__eq__(other)

    def __repr__(self):
        return 'DetailedSkylights: [{} windows]'.format(len(self._polygons))
