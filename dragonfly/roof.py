# coding: utf-8
"""Roof specification with instructions for generating sloped roofs over a Story."""
from __future__ import division
import math

from ladybug_geometry.geometry2d import Vector2D, Point2D, Ray2D, LineSegment2D, \
    Polygon2D
from ladybug_geometry.geometry3d import Vector3D, Point3D, Face3D, Polyface3D
from ladybug_geometry.intersection2d import closest_point2d_on_line2d, \
    closest_point2d_on_line2d_infinite


class RoofSpecification(object):
    """A roof specification with instructions for generating sloped roofs over a Story.

    Args:
        geometry: An array of Face3D objects representing the geometry of the Roof.
            None of these geometries should overlap in plan and, together, these
            Face3D should either completely cover or skip each Room2D of the Story
            to which the RoofSpecification is assigned.

    Properties:
        * geometry
        * boundary_geometry_2d
        * planes
        * parent
        * has_parent
        * min
        * max
    """
    __slots__ = ('_geometry', '_parent', '_ridge_line_info', '_ridge_line_tolerance')

    def __init__(self, geometry):
        """Initialize RoofSpecification."""
        self.geometry = geometry
        self._parent = None  # will be set when RoofSpecification is added to a Story

    @classmethod
    def from_dict(cls, data):
        """Initialize an RoofSpecification from a dictionary.

        Args:
            data: A dictionary representation of an RoofSpecification object.
        """
        # check the type of dictionary
        assert data['type'] == 'RoofSpecification', 'Expected RoofSpecification ' \
            'dictionary. Got {}.'.format(data['type'])
        geometry = tuple(Face3D.from_dict(shd_geo) for shd_geo in data['geometry'])
        return cls(geometry)

    @property
    def geometry(self):
        """Get or set a tuple of Face3D objects representing the geometry of the Roof.
        """
        return self._geometry

    @geometry.setter
    def geometry(self, value):
        if not isinstance(value, tuple):
            value = tuple(value)
        assert len(value) > 0, 'RoofSpecification must have at least one Face3D.'
        for geo in value:
            assert isinstance(geo, Face3D), \
                'Expected Face3D for RoofSpecification. Got {}'.format(type(geo))
        self._geometry = value
        self._ridge_line_info = None
        self._ridge_line_tolerance = None

    @property
    def boundary_geometry_2d(self):
        """Get a tuple of Polygon2D for the boundaries around each Face3D in geometry.

        These Polygons will be in the World XY coordinate system instead of the
        coordinate system of the Face3D's plane.
        """
        return tuple(
            Polygon2D(tuple(Point2D(pt.x, pt.y) for pt in geo.boundary))
            for geo in self._geometry)

    @property
    def planes(self):
        """Get a tuple of Planes for each Face3D in geometry.
        """
        return tuple(geo.plane for geo in self._geometry)

    @property
    def parent(self):
        """Parent Story if assigned. None if not assigned."""
        return self._parent

    @property
    def has_parent(self):
        """Boolean noting whether this RoofSpecification has a parent Story."""
        return self._parent is not None

    @property
    def min(self):
        """Get a Point2D for the min bounding rectangle vertex in the XY plane.

        This is useful in calculations to determine if this RoofSpecification is in
        proximity to other objects.
        """
        return self._calculate_min(self._geometry)

    @property
    def max(self):
        """Get a Point2D for the max bounding rectangle vertex in the XY plane.

        This is useful in calculations to determine if this RoofSpecification is in
        proximity to other objects.
        """
        return self._calculate_max(self._geometry)

    def overlap_count(self, tolerance=0.01):
        """Get the number of times that the Roof geometries overlap with one another.

        This should be zero for the RoofSpecification to be valid.

        Args:
            tolerance: The minimum distance that two Roof geometries can overlap
                with one another and still be considered valid. Default: 0.01,
                suitable for objects in meters.

        Returns:
            An integer for the number of times that the roof geometries overlap
            with one another beyond the tolerance.
        """
        geo_2d = self.boundary_geometry_2d
        overlap_count = 0
        for i, poly_1 in enumerate(geo_2d):
            try:
                for poly_2 in geo_2d[i + 1:]:
                    if poly_1.polygon_relationship(poly_2, tolerance) >= 0:
                        overlap_count += 1
            except IndexError:
                pass  # we have reached the end of the list
        return overlap_count

    def move(self, moving_vec):
        """Move this RoofSpecification along a vector.

        Args:
            moving_vec: A ladybug_geometry Vector3D with the direction and distance
                to move the object.
        """
        self._geometry = tuple(geo.move(moving_vec) for geo in self._geometry)

    def rotate_xy(self, angle, origin):
        """Rotate RoofSpecification counterclockwise in the XY plane by a certain angle.

        Args:
            angle: An angle in degrees.
            origin: A ladybug_geometry Point3D for the origin around which the
                object will be rotated.
        """
        self._geometry = tuple(geo.rotate_xy(math.radians(angle), origin)
                               for geo in self._geometry)

    def reflect(self, plane):
        """Reflect this RoofSpecification across a plane.

        Args:
            plane: A ladybug_geometry Plane across which the object will be reflected.
        """
        self._geometry = tuple(geo.reflect(plane.n, plane.o) for geo in self._geometry)

    def scale(self, factor, origin=None):
        """Scale this RoofSpecification by a factor from an origin point.

        Args:
            factor: A number representing how much the object should be scaled.
            origin: A ladybug_geometry Point3D representing the origin from which
                to scale. If None, it will be scaled from the World origin (0, 0, 0).
        """
        self._geometry = tuple(geo.scale(factor, origin) for geo in self._geometry)

    def update_geometry_3d(self, new_face_3d, face_index):
        """Change one of the Face3D in this RoofSpecification.geometry.

        This method is intended to be used when the roof geometry has been edited
        by some external means and this RoofSpecification should be updated
        for coordination.

        Args:
            new_face_3d: A Face3D for a new roof geometry that is to replace one
                of the existing Face3D in the roof.
            face_index: An integer for the index of the Face3D in the roof to
                be replaced.
        """
        assert isinstance(new_face_3d, Face3D), \
            'Expected Face3D for RoofSpecification.update_geometry_3d. ' \
            'Got {}'.format(type(new_face_3d))
        geo_list = list(self._geometry)
        geo_list[face_index] = new_face_3d
        self._geometry = tuple(geo_list)
        self._ridge_line_info = None
        self._ridge_line_tolerance = None

    def update_geometry_2d(self, new_polygon_2d, polygon_index):
        """Change one of the Face3D in this roof by supplying a 2D Polygon.

        This method is intended to be used when the roof geometry has been edited
        by some external means and this RoofSpecification should be updated
        for coordination. It it particularly helpful when the external means
        of editing has happened in 2D plan view and only the boundary of the
        roof should be updated while the plane of the roof geometry is held
        constant.

        Args:
            new_polygon_2d: A Polygon2D for a new roof geometry that is to replace
                one of the existing geometries in the roof. Ideally, this is
                one of this RoofSpecification's boundary_geometry_2d polygons
                that has been edited.
            polygon_index: An integer for the index of the boundary polygon in
                the roof to be replaced.
        """
        assert isinstance(new_polygon_2d, Polygon2D), \
            'Expected Polygon2D for RoofSpecification.update_geometry_2d. ' \
            'Got {}'.format(type(new_polygon_2d))
        proj_dir = Vector3D(0, 0, 1)  # direction to project onto Roof planes
        roof_plane = self.geometry[polygon_index].plane
        roof_verts = []
        for pt2 in new_polygon_2d.vertices:
            pt3 = roof_plane.project_point(Point3D(pt2.x, pt2.y), proj_dir)
            roof_verts.append(pt3)
        new_face_3d = Face3D(roof_verts, plane=roof_plane)
        self.update_geometry_3d(new_face_3d, polygon_index)

    def align(self, line_ray, distance, tolerance=0.01):
        """Move naked roof vertices within a given distance of a line to be on that line.

        This is useful for coordinating the Roof specification with the alignment
        of Room2Ds that belong to the same Story as this Roof.

        Note that the planes of the input roof Face3Ds will be preserved. This way,
        the internal structure of the roof geometry will be conserved but the roof will
        be extended to cover Room2Ds that might have otherwise been aligned to
        the point that they have no Roof geometry above them.

        Args:
            line_ray: A ladybug_geometry Ray2D or LineSegment2D to which the roof
                vertices will be aligned. Ray2Ds will be interpreted as being infinite
                in both directions while LineSegment2Ds will be interpreted as only
                existing between two points.
            distance: The maximum distance between a vertex and the line_ray where
                the vertex will be moved to lie on the line_ray. Vertices beyond
                this distance will be left as they are.
            tolerance: The minimum distance between vertices below which they are
                considered co-located. This is used to ensure that the alignment process
                does not create new overlaps in the roof geometry. (Default: 0.01,
                suitable for objects in meters).
        """
        # check the input line_ray
        if isinstance(line_ray, Ray2D):
            closest_func = closest_point2d_on_line2d_infinite
        elif isinstance(line_ray, LineSegment2D):
            closest_func = closest_point2d_on_line2d
        else:
            msg = 'Expected Ray2D or LineSegment2D. Got {}.'.format(type(line_ray))
            raise TypeError(msg)
        
        # get the polygons and intersect them for matching segments
        polygons, planes = self.boundary_geometry_2d, self.planes
        poly_ridge_info = self._compute_ridge_line_info(tolerance)

        # loop through the polygons and align the vertices
        new_polygons = []
        for poly, poly_info in zip(polygons, poly_ridge_info):
            new_poly = []
            for pt, pt_info in zip(poly, poly_info):
                if len(pt_info) == 0:  # not on a ridge line; move it anywhere
                    close_pt = closest_func(pt, line_ray)
                    if pt.distance_to_point(close_pt) <= distance:
                        new_poly.append(close_pt)
                    else:
                        new_poly.append(pt)
                elif len(pt_info) == 1:  # only move it along a singe ridge line
                    r_line = pt_info[0]
                    vec_ang = math.degrees(r_line.v.angle(line_ray.v))
                    if 1 <= vec_ang <= 179:  # not parallel; ridge will be intact
                        close_pt = closest_func(pt, line_ray)
                        if pt.distance_to_point(close_pt) <= distance:
                            new_poly.append(close_pt)
                        else:
                            new_poly.append(pt)
                    else:
                        new_poly.append(pt)
                else:  # multiple ridge lines; don't move that point!
                    new_poly.append(pt)
            new_polygons.append(new_poly)

        # project the points back onto the roof
        proj_dir = Vector3D(0, 0, 1)
        new_geo = []
        for poly, r_pl in zip(new_polygons, planes):
            new_pts3d = []
            for pt2 in poly:
                new_pts3d.append(r_pl.project_point(Point3D.from_point2d(pt2), proj_dir))
            new_geo.append(Face3D(new_pts3d, plane=r_pl))
        self.geometry = new_geo

    def snap_to_grid(self, grid_increment, tolerance=0.01):
        """Snap naked roof vertices to the nearest grid node defined by an increment.

        This is useful for coordinating the Roof specification with the grid snapping
        of Room2Ds that belong to the same Story as this Roof.

        Note that the planes of the input roof Face3Ds will be preserved. This way,
        the internal structure of the roof geometry will be conserved but the roof
        will be extended to cover Room2Ds that might have otherwise been snapped to
        the a node where they have no Roof geometry above them.

        Args:
            grid_increment: A positive number for dimension of each grid cell. This
                typically should be equal to the tolerance or larger but should
                not be larger than the smallest detail of the Room2D that you
                wish to resolve.
            tolerance: The minimum distance between vertices below which they are
                considered co-located. (Default: 0.01,
                suitable for objects in meters).
        """
        # get the polygons and intersect them for matching segments
        polygons, planes = self.boundary_geometry_2d, self.planes
        poly_ridge_info = self._compute_ridge_line_info(tolerance)

        # loop through the polygons and snap the vertices
        new_polygons = []
        for poly, poly_info in zip(polygons, poly_ridge_info):
            new_poly = []
            for pt, pt_info in zip(poly, poly_info):
                if len(pt_info) == 0:  # not on a ridge line; move it anywhere
                    new_x = grid_increment * round(pt.x / grid_increment)
                    new_y = grid_increment * round(pt.y / grid_increment)
                    new_poly.append(Point2D(new_x, new_y, pt.z))
                else:  # on a ridge line; don't move that point!
                    new_poly.append(pt)
            new_polygons.append(new_poly)

        # project the points back onto the roof
        proj_dir = Vector3D(0, 0, 1)
        new_geo = []
        for poly, r_pl in zip(new_polygons, planes):
            new_pts3d = []
            for pt2 in poly:
                new_pts3d.append(r_pl.project_point(Point3D.from_point2d(pt2), proj_dir))
            new_geo.append(Face3D(new_pts3d, plane=r_pl))
        self.geometry = new_geo

    def _compute_ridge_line_info(self, tolerance):
        """Get a matrix of values for the ridge lines associated with each vertex.

        Ridge lines are defined as lines shared between two roof geometries.

        The matrix will have one sub-list for each polygon in the boundary_geometry_2d
        and each sub-list will contain a sub-sub-list for each vertex. This sub-sub-list
        with contain LineSegment2Ds for each ridge line that the vertex is a part of.
        Vertices that belong to only one roof geometry will get an empty list in
        the matrix, indicating that the vertex can be moved in any direction without
        changing the roof structure. Vertices belonging to two roof geometries will
        get a single ridge line LineSegment2D in the list, indicating that the vertex can
        be moved along this vector without changing the structure of the whole roof.
        Vertices belonging to more than one roof geometry will get multiple
        LineSegment2Ds in the list, which usually means that moving the vertex in
        any direction will change the Roof structure.

        This method is hidden because it caches the results, meaning that it does
        not need to be recomputed for multiple alignment lines when the roof geometry
        or the tolerance does not change.
        """
        if self._ridge_line_info is None or self._ridge_line_tolerance != tolerance:
            # turn the polygons into Face3D in the XY plane
            proj_faces = []
            for poly in self.boundary_geometry_2d:
                proj_face = Face3D(tuple(Point3D(pt.x, pt.y) for pt in poly))
                proj_faces.append(proj_face)
            # join the projected Face3D into a Polyface3D and get all naked edges
            roof_p_face = Polyface3D.from_faces(proj_faces, tolerance)
            roof_p_face = roof_p_face.merge_overlapping_edges(
                tolerance, math.radians(1))
            internal_ed = roof_p_face.internal_edges
            # check whether each Face3D vertex lies on an internal edge
            ridge_info = []
            for proj_face in proj_faces:
                face_info = []
                for pt in proj_face.boundary:
                    pt_rid = []
                    for ed in internal_ed:
                        if ed.distance_to_point(pt) <= tolerance:
                            ln_2 = LineSegment2D(
                                Point2D(ed.p.x, ed.p.y), Vector2D(ed.v.x, ed.v.y))
                            pt_rid.append(ln_2)
                    face_info.append(pt_rid)
                ridge_info.append(face_info)
            self._ridge_line_info = ridge_info
            self._ridge_line_tolerance = tolerance
        return self._ridge_line_info

    def to_dict(self):
        """Return RoofSpecification as a dictionary."""
        base = {'type': 'RoofSpecification'}
        base['geometry'] = [geo.to_dict() for geo in self._geometry]
        return base

    def duplicate(self):
        """Get a copy of this object."""
        return self.__copy__()

    @staticmethod
    def _calculate_min(geometry_objects):
        """Calculate min Point2D around an array of geometry with min attributes.

        This is used in all functions that calculate bounding rectangles around
        dragonfly objects and assess when two objects are in close proximity.
        """
        min_pt = [geometry_objects[0].min.x, geometry_objects[0].min.y]

        for room in geometry_objects[1:]:
            if room.min.x < min_pt[0]:
                min_pt[0] = room.min.x
            if room.min.y < min_pt[1]:
                min_pt[1] = room.min.y

        return Point2D(min_pt[0], min_pt[1])

    @staticmethod
    def _calculate_max(geometry_objects):
        """Calculate max Point2D around an array of geometry with max attributes.

        This is used in all functions that calculate bounding rectangles around
        dragonfly objects and assess when two objects are in close proximity.
        """
        max_pt = [geometry_objects[0].max.x, geometry_objects[0].max.y]

        for room in geometry_objects[1:]:
            if room.max.x > max_pt[0]:
                max_pt[0] = room.max.x
            if room.max.y > max_pt[1]:
                max_pt[1] = room.max.y

        return Point2D(max_pt[0], max_pt[1])

    def __copy__(self):
        return RoofSpecification(self._geometry)

    def __len__(self):
        return len(self._geometry)

    def __getitem__(self, key):
        return self._geometry[key]

    def __iter__(self):
        return iter(self._geometry)

    def ToString(self):
        """Overwrite .NET ToString."""
        return self.__repr__()

    def __repr__(self):
        return 'RoofSpecification: [{} geometries]'.format(len(self._geometry))
