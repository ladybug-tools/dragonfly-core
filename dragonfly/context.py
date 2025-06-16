# coding: utf-8
"""Dragonfly Context Shade."""
from __future__ import division
import math

from ladybug_geometry.geometry2d import Vector2D, Point2D, Ray2D, LineSegment2D, \
    Polygon2D
from ladybug_geometry.geometry3d import Vector3D, Point3D, Plane, Face3D, Mesh3D
from ladybug_geometry.intersection2d import closest_point2d_on_line2d, \
    closest_point2d_on_line2d_infinite

from honeybee.shade import Shade
from honeybee.shademesh import ShadeMesh
from honeybee.typing import clean_string

from ._base import _BaseGeometry
from .properties import ContextShadeProperties
import dragonfly.writer.context as writer


class ContextShade(_BaseGeometry):
    """A Context Shade object defined by an array of Face3Ds and/or Mesh3Ds.

    Args:
        identifier: Text string for a unique ContextShade ID. Must be < 100 characters
            and not contain any spaces or special characters.
        geometry: An array of ladybug_geometry Face3D and/or Mesh3D objects
            that together represent the context shade.
        is_detached: Boolean to note whether this object is detached from other
            geometry. Cases where this should be True include shade representing
            surrounding buildings or context. (Default: True).

    Properties:
        * identifier
        * display_name
        * geometry
        * is_detached
        * area
        * min
        * max
        * user_data
    """
    __slots__ = ('_geometry', '_is_detached')

    def __init__(self, identifier, geometry, is_detached=True):
        """Initialize ContextShade."""
        _BaseGeometry.__init__(self, identifier)  # process the identifier

        # process the geometry
        if not isinstance(geometry, tuple):
            geometry = tuple(geometry)
        assert len(geometry) > 0, 'ContextShade must have at least one geometry.'
        for shd_geo in geometry:
            assert isinstance(shd_geo, (Face3D, Mesh3D)), 'Expected ladybug_geometry ' \
                'Face3D or Mesh3D. Got {}'.format(type(shd_geo))
        self._geometry = geometry
        self.is_detached = is_detached

        self._properties = ContextShadeProperties(self)  # properties for extensions

    @classmethod
    def from_dict(cls, data):
        """Initialize an ContextShade from a dictionary.

        Note that this method will automatically remove invalid geometries
        detected in the input like Face3Ds with fewer than three vertices,
        Mesh3Ds that lack all faces, etc.

        If all geometry in the ContextShade is invalid, this method will
        raise a ValueError exception with a message reporting what is wrong
        with the geometry.

        Args:
            data: A dictionary representation of an ContextShade object.
        """
        # check the type of dictionary
        assert data['type'] == 'ContextShade', 'Expected ContextShade dictionary. ' \
            'Got {}.'.format(data['type'])

        # serialize the geometry, removing invalid geometries in the process
        is_detached = data['is_detached'] if 'is_detached' in data else True
        geometry, err_msgs = [], []
        for shd_geo in data['geometry']:
            if shd_geo['type'] == 'Face3D':
                try:
                    geometry.append(Face3D.from_dict(shd_geo))
                except AssertionError as e:  # invalid Face3D to ignore
                    err_msgs.append(str(e))
            else:
                try:
                    geometry.append(Mesh3D.from_dict(shd_geo))
                except AssertionError as e:  # invalid Mesh3D to ignore
                    err_msgs.append(str(e))
        if len(geometry) == 0:
            shade_name = data['display_name'] if 'display_name' in data and \
                data['display_name'] is not None else data['identifier']
            msg = 'All geometry of ContextShade "{}" is invalid: {}'.format(
                shade_name, '. '.join(err_msgs))
            raise ValueError(msg)

        # create the ContextShade
        shade = cls(data['identifier'], geometry, is_detached)
        if 'display_name' in data and data['display_name'] is not None:
            shade.display_name = data['display_name']
        if 'user_data' in data and data['user_data'] is not None:
            shade.user_data = data['user_data']

        if data['properties']['type'] == 'ContextShadeProperties':
            shade.properties._load_extension_attr_from_dict(data['properties'])
        return shade

    @classmethod
    def from_honeybee(cls, shade):
        """Initialize an ContextShade from a Honeybee Shade or ShadeMesh.

        Args:
            shade: A Honeybee Shade or ShadeMesh object.
        """
        con_shade = cls(shade.identifier, [shade.geometry], shade.is_detached)
        con_shade._display_name = shade.display_name
        con_shade._user_data = None if shade.user_data is None \
            else shade.user_data.copy()
        con_shade.properties.from_honeybee(shade.properties)
        return con_shade

    @property
    def geometry(self):
        """Get a tuple of Face3D and/or Mesh3D objects that represent the context shade.
        """
        return self._geometry

    @property
    def is_detached(self):
        """Get or set a boolean for whether this object is detached from other geometry.
        """
        return self._is_detached

    @is_detached.setter
    def is_detached(self, value):
        try:
            self._is_detached = bool(value)
        except TypeError:
            raise TypeError(
                'Expected boolean for ContextShade.is_detached. Got {}.'.format(value))

    @property
    def area(self):
        """Get a number for the total surface area of the ContextShade."""
        return sum([geo.area for geo in self._geometry])

    @property
    def min(self):
        """Get a Point2D for the min bounding rectangle vertex in the XY plane.

        This is useful in calculations to determine if this ContextShade is in
        proximity to other objects.
        """
        return self._calculate_min(self._geometry)

    @property
    def max(self):
        """Get a Point2D for the max bounding rectangle vertex in the XY plane.

        This is useful in calculations to determine if this ContextShade is in
        proximity to other objects.
        """
        return self._calculate_max(self._geometry)

    def add_prefix(self, prefix):
        """Change the identifier of this object by inserting a prefix.

        This is particularly useful in workflows where you duplicate and edit
        a starting object and then want to combine it with the original object
        into one Model (like making a model of repeated shades) since all objects
        within a Model must have unique identifiers.

        Args:
            prefix: Text that will be inserted at the start of this object's identifier
                and display_name. It is recommended that this prefix be short to
                avoid maxing out the 100 allowable characters for dragonfly identifiers.
        """
        self._identifier = clean_string('{}_{}'.format(prefix, self.identifier))
        self.display_name = '{}_{}'.format(prefix, self.display_name)
        self.properties.add_prefix(prefix)

    def move(self, moving_vec):
        """Move this ContextShade along a vector.

        Args:
            moving_vec: A ladybug_geometry Vector3D with the direction and distance
                to move the object.
        """
        self._geometry = tuple(shd_geo.move(moving_vec) for shd_geo in self._geometry)
        self.properties.move(moving_vec)

    def rotate_xy(self, angle, origin):
        """Rotate this ContextShade counterclockwise in the XY plane by a certain angle.

        Args:
            angle: An angle in degrees.
            origin: A ladybug_geometry Point3D for the origin around which the
                object will be rotated.
        """
        self._geometry = tuple(shd_geo.rotate_xy(math.radians(angle), origin)
                               for shd_geo in self._geometry)
        self.properties.rotate_xy(angle, origin)

    def reflect(self, plane):
        """Reflect this ContextShade across a plane.

        Args:
            plane: A ladybug_geometry Plane across which the object will be reflected.
        """
        self._geometry = tuple(shd_geo.reflect(plane.n, plane.o)
                               for shd_geo in self._geometry)
        self.properties.reflect(plane)

    def scale(self, factor, origin=None):
        """Scale this ContextShade by a factor from an origin point.

        Args:
            factor: A number representing how much the object should be scaled.
            origin: A ladybug_geometry Point3D representing the origin from which
                to scale. If None, it will be scaled from the World origin (0, 0, 0).
        """
        self._geometry = tuple(shd_geo.scale(factor, origin)
                               for shd_geo in self._geometry)
        self.properties.scale(factor, origin)

    def is_conforming(self, plane, angle_tolerance=1.0, min_length=0.01):
        """Get a boolean for whether this objects's vertices conform with a plane.

        Args:
            plane: A ladybug-geometry Plane that will be used to evaluate whether
                each geometry vertex conforms to the plane or not.
            angle_tolerance: A number for the maximum difference in degrees that the
                geometry segments can differ from the XY axes of the plane for it
                to be considered non-conforming. (Default: 1.0).
            min_length: A number for the minimum length that a Room2D segment must
                be for it to be considered for non-conformity. Setting this to
                zero will evaluate all Room2D segments. (Default: 0.01; suitable
                for objects in meters).

        Returns:
            True if the ContextShade conforms to the plane. False if it does not.
        """
        # define variables to be used throughout the evaluation
        min_ang = math.radians(angle_tolerance)
        max_ang = math.pi - min_ang
        x_axis, y_axis = plane.x, plane.y
        # loop through the geometries and build up a vertex map
        for geo in self.geometry:
            if isinstance(geo, Face3D):
                seg_loops = [geo.boundary_segments]
                if geo.has_holes:
                    seg_loops.extend(geo.hole_segments)
                # loop through the segments and evaluate their non-conformity
                for seg_loop in seg_loops:
                    for seg in seg_loop:
                        if seg.length < min_length:
                            continue
                        if seg.is_vertical(min_length):
                            continue
                        try:
                            ang = seg.v.angle(x_axis)
                        except ZeroDivisionError:  # vertical segment
                            continue
                        if ang < min_ang or ang > max_ang:
                            continue
                        try:
                            ang = seg.v.angle(y_axis)
                        except ZeroDivisionError:  # vertical segment
                            continue
                        if ang < min_ang or ang > max_ang:
                            continue
                        return False
            else:  # meshes are always considered un-conforming
                return False
        return True

    def unconforming_vertex_map(self, plane, angle_tolerance=1.0, min_length=0.01):
        """Analyze this object's vertices for conformity with a plane's XY axes.

        Vertices of this object that do not conform to the plane will be
        highted in the result.

        Args:
            plane: A ladybug-geometry Plane that will be used to evaluate whether
                each geometry vertex conforms to the plane or not.
            angle_tolerance: A number for the maximum difference in degrees that the
                geometry segments can differ from the XY axes of the plane for it
                to be considered non-conforming. (Default: 1.0).
            min_length: A number for the minimum length that a Room2D segment must
                be for it to be considered for non-conformity. Setting this to
                zero will evaluate all Room2D segments. (Default: 0.01; suitable
                for objects in meters).

        Returns:
            A list of lists where each sub-list represents a Face3D or Mesh3D
            in this object. Each Face3D is represented with a list of lists where
            each sub-list is a loop of the Face3D. The first sub-list represents
            the boundary and subsequent sub-lists represent holes. Each item in
            each sub-list represents a vertex. If a given vertex is conforming
            to the plane, it will show up as None in the sub-list. Otherwise,
            the Point3D for the non-conforming vertex will appear in the sub-list.
        """
        # define variables to be used throughout the evaluation
        min_ang = math.radians(angle_tolerance)
        max_ang = math.pi - min_ang
        x_axis, y_axis = plane.x, plane.y
        vertex_map = []

        # loop through the geometries and build up a vertex map
        for geo in self.geometry:
            if isinstance(geo, Face3D):
                seg_loops = [geo.boundary_segments]
                if geo.has_holes:
                    seg_loops.extend(geo.hole_segments)
                # loop through the segments and evaluate their non-conformity
                conform = []
                for seg_loop in seg_loops:
                    loop_conform, correct_first = [], False
                    for seg in seg_loop:
                        if seg.length < min_length:
                            loop_conform.append(True)
                            continue
                        try:
                            ang = seg.v.angle(x_axis)
                        except ZeroDivisionError:  # vertical segment
                            try:
                                loop_conform.append(loop_conform[-1])
                            except IndexError:
                                correct_first = True
                                ang = 0
                        if ang < min_ang or ang > max_ang:
                            loop_conform.append(True)
                            continue
                        try:
                            ang = seg.v.angle(y_axis)
                        except ZeroDivisionError:  # vertical segment
                            try:
                                loop_conform.append(loop_conform[-1])
                            except IndexError:
                                correct_first = True
                                ang = 0
                        if ang < min_ang or ang > max_ang:
                            loop_conform.append(True)
                            continue
                        loop_conform.append(False)
                    if correct_first:
                        loop_conform[0] = loop_conform[1]
                    conform.append(loop_conform)
                # evaluate vertices in relation to surrounding segments
                points_to_keep = []
                for seg_loop, conformity in zip(seg_loops, conform):
                    loop_points = []
                    for i, (seg, con) in enumerate(zip(seg_loop, conformity)):
                        if con or conformity[i - 1]:
                            loop_points.append(None)
                        else:
                            loop_points.append(seg.p)
                    points_to_keep.append(loop_points)
                vertex_map.append(points_to_keep)
            else:  # meshes are always considered un-conforming
                vertex_map.append(geo.vertices)

        return vertex_map

    def apply_vertex_map(self, vertex_map):
        """Apply a vertex map to this object's vertices.

        Vertex maps are helpful for restoring vertices in geometry after performing
        a series of complex operations. For example, when performing a series of
        operations that edit the geometry in relation to a plane, a
        ContextShade.unconforming_vertex_map() can be generated to put back the
        vertices that did not relate to the plane of the grid.

        Args:
            vertex_map: A list of lists where each sub-list represents a Face3D or Mesh3D
            in this object. Each Face3D is represented with a list of lists where
            each sub-list is a loop of the Face3D. The first sub-list represents
            the boundary and subsequent sub-lists represent holes. Each item in
            each sub-list represents a vertex. If a given vertex on this object
            is to be left as it is, it should be represented as None in the sub-list.
            Otherwise, the Point3D to replace the vertex on this object should
            appear in the sub-list.
        """
        if all(pt is None for sub_l in vertex_map for pt in sub_l):
            return
        new_geometry = []
        for geo, v_map in zip(self.geometry, vertex_map):
            if isinstance(geo, Face3D):
                if all(pt is None for sub_l in v_map for pt in sub_l):
                    new_geometry.append(geo)
                    continue
                final_boundary, final_holes = [], None
                for new_pt, old_pt in zip(geo.boundary, v_map[0]):
                    final_pt = new_pt if old_pt is None else old_pt
                    final_boundary.append(final_pt)
                if geo.has_holes:
                    final_holes = []
                    for new_hole, old_hole in zip(geo.holes, v_map[1:]):
                        final_hole = []
                        for new_pt, old_pt in zip(new_hole, old_hole):
                            final_pt = new_pt if old_pt is None else old_pt
                            final_hole.append(final_pt)
                        final_holes.append(final_hole)
                f_pl = geo.plane
                new_geometry.append(Face3D(final_boundary, f_pl, final_holes))
            else:  # meshes are always considered un-conforming
                new_geometry.append(Mesh3D(v_map, geo.faces))
        self._geometry = tuple(new_geometry)

    def snap_to_grid(self, grid_increment, base_plane=None):
        """Snap this object to the nearest XY grid node defined by an increment.

        Note that, even though ContextShade geometry is defined using 3D vertices,
        only the X and Y coordinates will be snapped, which is consistent with
        how the Room2D.snap_to_grid method works.

        All properties assigned to the ContextShade will be preserved and any
        degenerate geometries are automatically cleaned out of the result.

        Args:
            grid_increment: A positive number for dimension of each grid cell. This
                typically should be equal to the tolerance or larger but should
                not be larger than the smallest detail of the ContextShade that you
                wish to resolve.
            base_plane: An optional ladybug-geometry Plane object to set the coordinate
                system of the grid in which this Room will be snapped. If None, the
                World XY coordinate system will be used. (Default: None).
        """
        # if the base plane is specified, convert to the plane's coordinate system
        pl_ang = None
        if isinstance(base_plane, Plane) and base_plane.n.z != 0:
            origin = base_plane.o
            x_axis = Vector2D(base_plane.x.x, base_plane.x.y)
            pl_ang = x_axis.angle_counterclockwise(Vector2D(1, 0))

        # loop through the current geometry and snap the vertices
        new_geometry = []
        for geo in self._geometry:
            if isinstance(geo, Face3D):
                boundary, holes = geo.boundary, geo.holes
                if pl_ang is not None:
                    boundary = [pt.rotate_xy(pl_ang, origin) for pt in boundary]
                    if holes is not None:
                        holes = [[pt.rotate_xy(pl_ang, origin) for pt in hole]
                                 for hole in holes]
                new_boundary, new_holes = [], None
                for pt in boundary:
                    new_x = grid_increment * round(pt.x / grid_increment)
                    new_y = grid_increment * round(pt.y / grid_increment)
                    new_boundary.append(Point3D(new_x, new_y, pt.z))
                if geo.holes is not None:
                    new_holes = []
                    for hole in holes:
                        new_hole = []
                        for pt in hole:
                            new_x = grid_increment * round(pt.x / grid_increment)
                            new_y = grid_increment * round(pt.y / grid_increment)
                            new_hole.append(Point3D(new_x, new_y, pt.z))
                        new_holes.append(new_hole)
                if pl_ang is not None:
                    new_boundary = [pt.rotate_xy(-pl_ang, origin) for pt in new_boundary]
                    if new_holes is not None:
                        new_holes = [[pt.rotate_xy(-pl_ang, origin) for pt in hole]
                                     for hole in new_holes]
                n_geo = Face3D(new_boundary, geo.plane, new_holes)
                new_geometry.append(n_geo)
            elif isinstance(geo, Mesh3D):
                vertices = geo.vertices
                if pl_ang is not None:
                    vertices = [pt.rotate_xy(pl_ang, origin) for pt in vertices]
                new_vertices = []
                for pt in vertices:
                    new_x = grid_increment * round(pt.x / grid_increment)
                    new_y = grid_increment * round(pt.y / grid_increment)
                    new_vertices.append(Point3D(new_x, new_y, pt.z))
                if pl_ang is not None:
                    new_vertices = [pt.rotate_xy(-pl_ang, origin) for pt in new_vertices]
                n_geo = Mesh3D(new_vertices, geo.faces)
                new_geometry.append(n_geo)

        # rebuild the new floor geometry and assign it to the Room2D
        if len(new_geometry) != 0:
            self._geometry = tuple(new_geometry)

    def align(self, line_ray, distance, tolerance=0.01):
        """Move Shade vertices within a given distance of a line to be on that line.

        This is useful for coordinating the ContextShade with the alignment of Room2Ds.

        Note that the planes of the shade Face3Ds will be preserved unless the
        shade is perfectly vertical.

        Args:
            line_ray: A ladybug_geometry Ray2D or LineSegment2D to which the shade
                vertices will be aligned. Ray2Ds will be interpreted as being infinite
                in both directions while LineSegment2Ds will be interpreted as only
                existing between two points.
            distance: The maximum distance between a vertex and the line_ray where
                the vertex will be moved to lie on the line_ray. Vertices beyond
                this distance will be left as they are.
            tolerance: The minimum distance between vertices below which they are
                considered co-located. This is used to evaluate whether a given
                geometry is perfectly vertical. (Default: 0.01,
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

        # loop through the current geometry and snap the vertices
        new_geo = []
        for geo in self._geometry:
            if isinstance(geo, Face3D):
                is_vert = any(s.is_vertical(tolerance) for s in geo.boundary_segments)
                if is_vert:  # snap all vertices to the plane preserving the Z
                    new_boundary, new_holes = [], None
                    for pt in geo.boundary:
                        pt2 = Point2D(pt.x, pt.y)
                        close_pt = closest_func(pt, line_ray)
                        if pt2.distance_to_point(close_pt) <= distance:
                            new_boundary.append(Point3D(close_pt.x, close_pt.y, pt.z))
                        else:
                            new_boundary.append(pt)
                    if geo.has_holes:
                        new_holes = []
                        for hole in geo.holes:
                            new_hole = []
                            for pt in hole:
                                pt2 = Point2D(pt.x, pt.y)
                                cl_pt = closest_func(pt, line_ray)
                                if pt2.distance_to_point(close_pt) <= distance:
                                    new_hole.append(Point3D(cl_pt.x, cl_pt.y, pt.z))
                                else:
                                    new_hole.append(pt)
                            new_holes.append(new_hole)
                    new_geo.append(Face3D(new_boundary, holes=new_holes))
                else:
                    polygons = [Polygon2D(Point2D(pt.x, pt.y) for pt in geo.boundary)]
                    if geo.has_holes:
                        for hole in geo.holes:
                            hp = Polygon2D(Point2D(pt.x, pt.y) for pt in hole)
                            polygons.append(hp)
                    # loop through the polygons and align the vertices
                    new_polygons = []
                    for poly in polygons:
                        new_poly = []
                        for pt in poly:
                            close_pt = closest_func(pt, line_ray)
                            if pt.distance_to_point(close_pt) <= distance:
                                new_poly.append(close_pt)
                            else:
                                new_poly.append(pt)
                        new_polygons.append(Polygon2D(new_poly))
                    # project the points back onto the shade
                    proj_dir = Vector3D(0, 0, 1)
                    new_loops = []
                    for poly in new_polygons:
                        new_pts3d = []
                        for pt2 in poly:
                            pt3 = Point3D.from_point2d(pt2)
                            new_pts3d.append(geo.plane.project_point(pt3, proj_dir))
                        new_loops.append(new_pts3d)
                    new_geo.append(Face3D(new_loops[0], holes=new_loops[1:]))
            else:  # meshes are never aligned
                new_geo.append(geo)
        self._geometry = tuple(new_geo)

    def to_honeybee(self):
        """Convert Dragonfly ContextShade to a list of Honeybee Shades and ShadeMeshes.
        """
        shades = []
        for i, shd_geo in enumerate(self._geometry):
            if isinstance(shd_geo, Face3D):
                shade = Shade('{}_{}'.format(self.identifier, i), shd_geo,
                              is_detached=self.is_detached)
                shade._properties = self.properties.to_honeybee(shade, False)
            else:
                shade = ShadeMesh('{}_{}'.format(self.identifier, i), shd_geo,
                                  is_detached=self.is_detached)
                shade._properties = self.properties.to_honeybee(shade, True)
            shade.display_name = self.display_name
            shade.user_data = None if self.user_data is None else self.user_data.copy()
            shades.append(shade)
        return shades

    def to_dict(self, abridged=False, included_prop=None):
        """Return ContextShade as a dictionary.

        Args:
            abridged: Boolean to note whether the extension properties of the
                object (ie. materials, transmittance schedule) should be included in
                detail (False) or just referenced by identifier (True). Default: False.
            included_prop: List of properties to filter keys that must be included in
                output dictionary. For example ['energy'] will include 'energy' key if
                available in properties to_dict. By default all the keys will be
                included. To exclude all the keys from extensions use an empty list.
        """
        base = {'type': 'ContextShade'}
        base['identifier'] = self.identifier
        base['display_name'] = self.display_name
        base['properties'] = self.properties.to_dict(abridged, included_prop)
        base['geometry'] = [shd_geo.to_dict() for shd_geo in self._geometry]
        if not self.is_detached:
            base['is_detached'] = self.is_detached
        if self.user_data is not None:
            base['user_data'] = self.user_data
        return base

    @property
    def to(self):
        """ContextShade writer object.

        Use this method to access Writer class to write the context in other formats.
        """
        return writer

    def __copy__(self):
        new_shd = ContextShade(self.identifier, self._geometry, self.is_detached)
        new_shd._display_name = self.display_name
        new_shd._user_data = None if self.user_data is None else self.user_data.copy()
        new_shd._properties._duplicate_extension_attr(self._properties)
        return new_shd

    def __len__(self):
        return len(self._geometry)

    def __getitem__(self, key):
        return self._geometry[key]

    def __iter__(self):
        return iter(self._geometry)

    def __repr__(self):
        return 'ContextShade: %s' % self.display_name
