# coding: utf-8
"""Roof specification with instructions for generating sloped roofs over a Story."""
from __future__ import division
import math

from ladybug_geometry.geometry2d import Vector2D, Point2D, Ray2D, LineSegment2D, \
    Polygon2D
from ladybug_geometry.geometry3d import Vector3D, Point3D, LineSegment3D, \
    Face3D, Polyface3D
from ladybug_geometry.intersection2d import closest_point2d_on_line2d, \
    closest_point2d_on_line2d_infinite
import ladybug_geometry.boolean as pb


class RoofSpecification(object):
    """A roof specification with instructions for generating sloped roofs over a Story.

    Args:
        geometry: An array of Face3D objects representing the geometry of the Roof.
            Together, these Face3D should either completely cover or completely avoid
            each Room2D of the Story to which the RoofSpecification is assigned.
            Cases where Room2Ds are only partially covered by roofs will result in
            those Room2Ds being extruded to their floor_to_ceiling_height.

    Properties:
        * geometry
        * boundary_geometry_2d
        * planes
        * parent
        * has_parent
        * min
        * max
        * min_height
        * max_height
        * center_heights
        * azimuths
        * altitudes
        * tilts
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

    @property
    def min_height(self):
        """Get lowest Z-value of the roof geometry."""
        min_z = self._geometry[0].min.z
        for r_geo in self._geometry[1:]:
            if r_geo.min.z < min_z:
                min_z = r_geo.min.z
        return min_z

    @property
    def max_height(self):
        """Get highest Z-value of the roof geometry."""
        max_z = self._geometry[0].max.z
        for r_geo in self._geometry[1:]:
            if r_geo.max.z > max_z:
                max_z = r_geo.max.z
        return max_z

    @property
    def center_heights(self):
        """Get a tuple of average Z-values for each roof geometry."""
        return tuple(r_geo.center.z for r_geo in self._geometry)

    @property
    def azimuths(self):
        """Get a tuple of azimuths for each roof geometry in degrees.

        These values start from 0, indicating the positive Y-axis, and move clockwise
        up to 360, which indicates a return to the positive Y-axis.

        This will be zero if a geometry is perfectly horizontal.
        """
        azimuths = []
        for r_geo in self._geometry:
            r_geo = r_geo if r_geo.normal.z >= 0 else r_geo.flip()
            azimuths.append(math.degrees(r_geo.azimuth))
        return tuple(azimuths)

    @property
    def altitudes(self):
        """Get a tuple of altitudes for each roof geometry in degrees.

        These values range from 0 (vertical) up to 90 (horizontal).
        """
        return tuple(abs(math.degrees(r_geo.altitude)) for r_geo in self._geometry)

    @property
    def tilts(self):
        """Get a tuple of tilts for each roof geometry in degrees.

        These values range from 0 (horizontal) up to 90 (vertical).
        """
        return tuple(90 - alt for alt in self.altitudes)

    def union_coplanar(self, tolerance=0.01, angle_tolerance=1.0):
        """Union coplanar and overlapping geometries on this Roof together.

        This is useful for removing duplicated roof geometries that would
        otherwise slow down the translation process and potentially create
        unwanted results.

        Args:
            tolerance: The minimum distance between two roof geometries at which
                point they will be unioned together. (Default: 0.01, suitable
                for objects in meters).
            angle_tolerance: The max angle difference in degrees that planes
                can differ from one another for them to be considered
                coplanar. (Default: 1.0).
        """
        # remove colinear vertices from all roof geometries
        roof_geo = []
        for geo in self.geometry:
            try:
                roof_geo.append(geo.remove_colinear_vertices(tolerance))
            except AssertionError:  # degenerate geometry to ignore
                pass

        # group the roof geometries by the same plane
        a_tol = math.radians(angle_tolerance)
        tol = tolerance
        plane_dict = {roof_geo[0].plane: [roof_geo[0]]}
        for face in roof_geo[1:]:
            for test_plane in plane_dict:
                if test_plane.is_coplanar_tolerance(face.plane, tol, a_tol):
                    plane_dict[test_plane].append(face)
                    break
            else:
                plane_dict[face.plane] = [face]

        # group the geometries by overlap
        overlap_groups = []
        for pl_group in plane_dict.values():
            if len(pl_group) == 1:
                overlap_groups.append(pl_group)
            else:
                overlap_groups.extend(Face3D.group_by_coplanar_overlap(pl_group, tol))

        # union the overlapping groups together
        clean_geo = []
        for o_group in overlap_groups:
            if len(o_group) == 1:
                clean_geo.append(o_group[0])
            else:
                union_geo = Face3D.coplanar_union_all(o_group, tol, a_tol)
                if union_geo is not None:
                    clean_geo.extend(union_geo)
                else:
                    clean_geo.extend(o_group)

        # assign the new unioned geometry to this object
        if len(clean_geo) != 0:
            self._geometry = tuple(clean_geo)
            self._ridge_line_info = None
            self._ridge_line_tolerance = None

    def resolved_geometry(self, tolerance=0.01):
        """Get a version of this object's geometry with all overlaps in plan resolved.

        In the case of overlaps, the roof geometry that has the lowest average
        z-value for the overlap will become the "correct" one that actually
        bounds the room geometry.

        Args:
            tolerance: The minimum distance that two Roof geometries can overlap
                with one another and still be considered distinct. (Default: 0.01,
                suitable for objects in meters).

        Returns:
            A list of Face3D that have no overlaps in plan.
        """
        # first check to see if an overlap is possible
        if len(self._geometry) == 1:
            return self._geometry

        # set up global variables
        proj_dir = Vector3D(0, 0, 1)
        planes, geo_2d = [], []
        sort_obj = sorted(zip(self.boundary_geometry_2d, self.planes),
                          key=lambda pair: pair[0].area, reverse=True)

        # remove colinear vertices from all roof polygons
        for geo, pl in sort_obj:
            try:
                clean_geo = geo.remove_colinear_vertices(tolerance)
                geo_2d.append(clean_geo)
                planes.append(pl)
            except AssertionError:  # degenerate geometry to ignore
                pass

        # loop through the geometries and test for any overlaps
        remove_i = []
        gei = list(range(len(geo_2d)))
        overlap_count = 0
        for i in gei:
            poly_1 = geo_2d[i]
            pln_1 = planes[i]
            for j in gei[i + 1:]:
                poly_2 = geo_2d[j]
                pln_2 = planes[j]
                poly_relationship = poly_1.polygon_relationship(poly_2, tolerance)
                tol = tolerance  # temporary tolerance value that may be adjusted
                if poly_relationship == 0:
                    # resolve the overlap between the polygons
                    overlap_count += 1
                    try:
                        overlap_polys = poly_1.boolean_intersect(poly_2, tol)
                    except Exception as e:  # tolerance is likely not correct
                        try:  # make an attempt at a slightly lower tol
                            tol = tol / 10
                            overlap_polys = poly_1.boolean_intersect(poly_1, tol)
                        except Exception:
                            print('Failed to get boolean intersect.\n{}'.format(e))
                            continue
                    for o_poly in overlap_polys:
                        o_face_1, o_face_2 = [], []
                        for pt in o_poly.vertices:
                            pt1 = pln_1.project_point(Point3D(pt.x, pt.y), proj_dir)
                            pt2 = pln_2.project_point(Point3D(pt.x, pt.y), proj_dir)
                            o_face_1.append(pt1)
                            o_face_2.append(pt2)
                        o_face_1 = Face3D(o_face_1, plane=pln_1)
                        o_face_2 = Face3D(o_face_2, plane=pln_2)
                        if o_face_1.center.z > o_face_2.center.z:
                            try:  # remove the overlap from the first polygon
                                np = poly_1.boolean_difference(o_poly, tol)
                                if len(np) == 0:  # eliminated the polygon
                                    remove_i.append(i)
                                else:  # part-removed
                                    try:
                                        poly_1 = np[0].remove_colinear_vertices(tol)
                                        geo_2d[i] = poly_1
                                    except AssertionError:  # degenerate result
                                        remove_i.append(i)
                                    if len(np) > 1:  # split the polygon to multiple
                                        for ply in np[1:]:
                                            try:
                                                cp = ply.remove_colinear_vertices(tol)
                                                geo_2d.append(cp)
                                                planes.append(pln_1)
                                                gei.append(len(gei))
                                            except AssertionError:  # degenerate result
                                                pass
                            except Exception as e:  # tolerance is likely not correct
                                print('Failed to get boolean difference.\n{}'.format(e))
                                pass
                        else:  # remove the overlap from the second polygon
                            try:
                                np = poly_2.boolean_difference(o_poly, tol)
                                if len(np) == 0:  # eliminated the polygon
                                    remove_i.append(j)
                                else:  # part-removed
                                    try:
                                        poly_2 = np[0].remove_colinear_vertices(tol)
                                        geo_2d[j] = poly_2
                                    except AssertionError:  # degenerate result
                                        remove_i.append(j)
                                    if len(np) > 1:  # split the polygon to multiple
                                        for ply in np[1:]:
                                            try:
                                                cp = ply.remove_colinear_vertices(tol)
                                                geo_2d.append(cp)
                                                planes.append(pln_2)
                                                gei.append(len(gei))
                                            except AssertionError:  # degenerate result
                                                pass
                            except Exception as e:  # tolerance is likely not correct
                                print('Failed to get boolean difference.\n{}'.format(e))
                                pass
                elif poly_relationship == 1:
                    # polygon is completely inside the other; remove it
                    remove_i.append(j)

        # if any overlaps were found, rebuild the 3D roof geometry
        if overlap_count != 0 or len(remove_i) != 0:
            resolved_geo = []
            for i, (r_poly, r_pln) in enumerate(zip(geo_2d, planes)):
                if i not in remove_i:
                    r_face = []
                    for pt2 in r_poly.vertices:
                        pt3 = r_pln.project_point(Point3D(pt2.x, pt2.y), proj_dir)
                        r_face.append(pt3)
                    resolved_geo.append(Face3D(r_face, plane=r_pln))
            return resolved_geo
        return self._geometry  # no overlaps in the geometry; just return as is

    def overlap_count(self, tolerance=0.01):
        """Get the number of times that the Roof geometries overlap with one another.

        This should be zero for the RoofSpecification to be be translated to
        Honeybee without any loss of geometry.

        Args:
            tolerance: The minimum distance that two Roof geometries can overlap
                with one another and still be considered distinct. (Default: 0.01,
                suitable for objects in meters).

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

    def align(self, line_ray, distance, tolerance=0.01):
        """Move roof vertices within a given distance of a line to be on that line.

        This is useful for coordinating the Roof specification with the alignment
        of Room2Ds that belong to the same Story as this Roof.

        Note that the planes of the input roof Face3Ds will be preserved. This way,
        the internal structure of the roof geometry will be conserved but the roof will
        be extended to cover Room2Ds that might have otherwise been aligned to
        have no Roof geometry above them.

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

        # get the polygons and planes
        polygons, planes = self.boundary_geometry_2d, self.planes

        # loop through the roof polygons and align the vertices
        aligned_polygons = []
        for poly in polygons:
            new_poly = []
            for pt in poly:
                close_pt = closest_func(pt, line_ray)
                if pt.distance_to_point(close_pt) <= distance:
                    new_poly.append(close_pt)
                else:
                    new_poly.append(pt)
            aligned_polygons.append(Polygon2D(new_poly))

        # constrain the roof edges, which typically preserves roof ridge lines
        new_polygons = []
        for old_poly, new_poly in zip(polygons, aligned_polygons):
            con_poly = self._constrain_edges(old_poly, new_poly, [line_ray], tolerance)
            new_polygons.append(con_poly)

        # project the points back onto the roof
        proj_dir = Vector3D(0, 0, 1)
        new_geo = []
        for poly, r_pl in zip(new_polygons, planes):
            new_pts3d = []
            for pt2 in poly:
                new_pts3d.append(r_pl.project_point(Point3D.from_point2d(pt2), proj_dir))
            new_geo.append(Face3D(new_pts3d, plane=r_pl))
        self.geometry = new_geo

    def pull_to_segments(self, line_segments, distance, snap_vertices=True,
                         selected_indices=None, tolerance=0.01):
        """Pull the vertices of this roof to several LineSegment2D.

        This includes both an alignment to the line segments as well as an optional
        snapping to the line end points. The planes of the input roof Face3Ds
        will be preserved.

        The benefit of calling this method as opposed to iterating over the segments
        and calling align is that this method will only align and snap to the
        closest segment across all of the input line_segments. This often helps
        avoid snapping to undesirable line segments, particularly when there are
        two ore more segments that are within the distance.

        Args:
            line_segments: A list of ladybug_geometry LineSegment2D to which this
                roof's vertices will be pulled.
            distance: The maximum distance between a roof vertex and the line_segments
                where the vertex will be moved to lie on the segments. Vertices beyond
                this distance will be left as they are.
            snap_vertices: A boolean to note whether roof vertices that are close
                to the segment end points within the distance should be snapped
                to the end point instead of simply being aligned to the nearest
                segment. (Default: True).
            selected_indices: An optional list of indices for specific roof
                geometries to be split with the input polygon. If None, all of
                the roof geometry will be tested for intersection with the
                input polygon. (Default: None).
            tolerance: The minimum difference between the coordinate values at
                which they are considered co-located. (Default: 0.01,
                suitable for objects in meters).
        """
        # check that the input is as expected
        if len(line_segments) == 0:
            return
        for line in line_segments:
            if not isinstance(line, LineSegment2D):
                msg = 'Expected LineSegment2D. Got {}.'.format(type(line))
                raise TypeError(msg)

        # get the polygons and planes
        polygons, planes = self.boundary_geometry_2d, self.planes

        # loop through the roof polygons and align the vertices
        aligned_polygons = []
        for i, poly in enumerate(polygons):
            if selected_indices is None or i in selected_indices:
                new_boundary = []
                for pt in poly:
                    dists, c_pts = [], []
                    for line_ray in line_segments:
                        close_pt = closest_point2d_on_line2d(pt, line_ray)
                        c_pts.append(close_pt)
                        dists.append(pt.distance_to_point(close_pt))
                    sort_pt = sorted(zip(dists, c_pts), key=lambda pair: pair[0])
                    if sort_pt[0][0] <= distance:
                        new_boundary.append(sort_pt[0][1])
                    else:
                        new_boundary.append(pt)
                aligned_polygons.append(Polygon2D(new_boundary))
            else:
                aligned_polygons.append(poly)

        # if snap_vertices was requested, perform an additional operation to snap them
        if snap_vertices:
            vertices = []
            for line in line_segments:
                vertices.append(line.p1)
                vertices.append(line.p2)
            new_polygons = []
            for i, poly in enumerate(aligned_polygons):
                if selected_indices is None or i in selected_indices:
                    new_boundary = []
                    for pt in poly:
                        dists = [pt.distance_to_point(pt_2d) for pt_2d in vertices]
                        sort_pt = sorted(zip(dists, vertices), key=lambda pair: pair[0])
                        if sort_pt[0][0] <= distance:
                            new_boundary.append(sort_pt[0][1])
                        else:
                            new_boundary.append(pt)
                    new_polygons.append(Polygon2D(new_boundary))
                else:
                    new_polygons.append(poly)
            aligned_polygons = new_polygons

        # constrain the roof edges, which typically preserves roof ridge lines
        new_polygons = []
        for i, (old_poly, new_poly) in enumerate(zip(polygons, aligned_polygons)):
            if selected_indices is None or i in selected_indices:
                con_poly = self._constrain_edges(
                    old_poly, new_poly, line_segments, tolerance)
                new_polygons.append(con_poly)
            else:
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

    def subtract_roofs(self, minuend_index, subtrahend_indices, tolerance=0.01):
        """Subtract one or more geometries in this roof from a given geometry.

        This is useful for resolving overlaps between geometries in the roof,
        particularly when one geometry above another one should take precedence.

        Args:
            minuend_index: The index of a geometry in this roof from which the
                subtrahend roof geometries will be subtracted.
            subtrahend_indices: A list of indices for geometries in this roof
                that will be used to remove part of the geometry at the minuend_index.
            tolerance: The maximum difference between point values for them to be
                considered distinct from one another. (Default: 0.01; suitable
                for objects in Meters).
        """
        # get the minuend and subtrahend polygons
        polygons, planes = self.boundary_geometry_2d, self.planes
        minuend_poly = polygons[minuend_index]
        minuend_plane = planes[minuend_index]
        subtrahend_polys = [polygons[s_i] for s_i in subtrahend_indices]

        # define the subtrahend boolean polygon
        try:
            minuend_poly = minuend_poly.remove_colinear_vertices(tolerance)
        except AssertionError:  # degenerate roof geometry selected
            return
        minuend_bp = [(pb.BooleanPoint(pt.x, pt.y) for pt in minuend_poly.vertices)]
        minuend_bp = pb.BooleanPolygon(minuend_bp)

        # pre-process the roofs to be subtracted with
        relevant_b_polys = []
        for f2_poly in subtrahend_polys:
            # test whether the two polygons have any overlap in 2D space
            if minuend_poly.polygon_relationship(f2_poly, tolerance) == -1:
                continue
            # snap the polygons to one another to avoid tolerance issues
            try:
                f2_poly = f2_poly.remove_colinear_vertices(tolerance)
            except AssertionError:  # degenerate polygon
                continue
            s2_poly = minuend_poly.snap_to_polygon(f2_poly, tolerance)
            # create the BooleanPolygon
            f2_polys = [(pb.BooleanPoint(pt.x, pt.y) for pt in s2_poly.vertices)]
            b_poly2 = pb.BooleanPolygon(f2_polys)
            relevant_b_polys.append(b_poly2)

        # if no relevant polygons were found, don't perform any operation
        if len(relevant_b_polys) == 0:
            return

        # loop through the boolean polygons and subtract them
        int_tol = tolerance / 100
        for b_poly2 in relevant_b_polys:
            try:  # subtract the boolean polygons
                minuend_bp = pb.difference(minuend_bp, b_poly2, int_tol)
            except Exception:
                return  # typically a tolerance issue causing failure
        minuend_polys = Polygon2D._from_bool_poly(minuend_bp)
        if len(minuend_polys) == 0:
            return

        # project the points back onto the roof
        proj_dir = Vector3D(0, 0, 1)
        new_geo = []
        for poly in minuend_polys:
            new_pts3d = []
            for pt2 in poly:
                pt3 = minuend_plane.project_point(Point3D.from_point2d(pt2), proj_dir)
                new_pts3d.append(pt3)
            new_geo.append(Face3D(new_pts3d, plane=minuend_plane))

        # update the geometry
        updated_geo = list(self.geometry)
        updated_geo[minuend_index] = new_geo[0]
        for ng in new_geo[1:]:
            updated_geo.append(ng)
        self.geometry = updated_geo

    def split_with_polygon(self, polygon, selected_indices=None, tolerance=0.01):
        """Split the geometry of this roof using a polygon.

        If the input polygon does not intersect the roof geometry in a manner
        that splits it, this roof will remain unaltered.

        Args:
            polygon: A Polygon2D object that will be used to split the roof geometry.
            selected_indices: An optional list of indices for specific roof
                geometries to be split with the input polygon. If None, all of
                the roof geometry will be tested for intersection with the
                input polygon. (Default: None).
            tolerance: The maximum difference between point values for them to be
                considered distinct from one another. (Default: 0.01; suitable
                for objects in Meters).
        """
        # check the inputs
        if not isinstance(polygon, Polygon2D):
            msg = 'Expected Polygon2D. Got {}.'.format(type(polygon))
            raise TypeError(msg)

        # split the geometries with the polygon
        ang_tol = math.radians(1)
        proj_dir = Vector3D(0, 0, 1)
        split_geometries = []
        for i, geo in enumerate(self.geometry):
            if selected_indices is None or i in selected_indices:
                # project the polygon into the plane of the roof geometry
                new_pts3d = []
                for pt2 in polygon:
                    pt3 = geo.plane.project_point(Point3D.from_point2d(pt2), proj_dir)
                    new_pts3d.append(pt3)
                face_3d = Face3D(new_pts3d, plane=geo.plane)
                # split the roof geometry with the polygon
                new_geos, _ = Face3D.coplanar_split(geo, face_3d, tolerance, ang_tol)
                if new_geos is None or len(new_geos) == 1:
                    split_geometries.append(geo)  # no overlap with one another
                else:
                    split_geometries.extend(new_geos)  # roof successfully split
            else:
                split_geometries.append(geo)

        # update the geometry
        self.geometry = split_geometries

    def split_with_lines(self, lines, selected_indices=None, tolerance=0.01):
        """Split the geometry of this roof using multiple line segments together.

        If the input lines do not intersect the roof geometry in a manner
        that splits it, this roof will remain unaltered.

        Args:
            lines: A list of LineSegment2D objects that will be used to split
                this roof geometry.
            selected_indices: An optional list of indices for specific roof
                geometries to be split with the input lines. If None, all of
                the roof geometry will be tested for intersection with the
                input polygon. (Default: None).
            tolerance: The maximum difference between point values for them to be
                considered distinct from one another. (Default: 0.01; suitable
                for objects in Meters).

        Returns:
            A list of Room2D for the result of splitting this Room2D with the
            input line. Will be a list with only the current Room2D if the line
            does not split it into two or more pieces.
        """
        # check the inputs
        for line in lines:
            if not isinstance(line, LineSegment2D):
                msg = 'Expected LineSegment2D. Got {}.'.format(type(line))
                raise TypeError(msg)

        # split the geometries with the lines
        rt = self._rounding_tolerance(tolerance)
        proj_dir = Vector3D(0, 0, 1)
        split_geometries = []
        for i, geo in enumerate(self.geometry):
            if selected_indices is None or i in selected_indices:
                # project the lines into the plane of the roof geometry
                lines_3d = []
                for seg in lines:
                    pt1 = geo.plane.project_point(Point3D.from_point2d(seg.p1), proj_dir)
                    pt2 = geo.plane.project_point(Point3D.from_point2d(seg.p2), proj_dir)
                    pt1 = Point3D(round(pt1.x, rt), round(pt1.y, rt), round(pt1.z, rt))
                    pt2 = Point3D(round(pt2.x, rt), round(pt2.y, rt), round(pt2.z, rt))
                    lines_3d.append(LineSegment3D.from_end_points(pt1, pt2))
                # split the roof geometry with the lines
                new_geos = geo.split_with_lines(lines_3d, tolerance)
                if new_geos is None or len(new_geos) == 1:
                    split_geometries.append(geo)  # no overlap
                else:
                    split_geometries.extend(new_geos)  # roof successfully split
            else:
                split_geometries.append(geo)

        # update the geometry
        self.geometry = split_geometries

    def to_dict(self):
        """Return RoofSpecification as a dictionary."""
        base = {'type': 'RoofSpecification'}
        base['geometry'] = [geo.to_dict() for geo in self._geometry]
        return base

    def duplicate(self):
        """Get a copy of this object."""
        return self.__copy__()

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

    @staticmethod
    def _constrain_edges(original_polygon, new_polygon, pull_segments, tolerance):
        """Move 2D vertices to constrain original edges not on the pull_segments."""
        # get all of the vertices and segments needed for the operation
        new_verts = new_polygon.vertices
        new_segs = new_polygon.segments
        old_segs = original_polygon.segments

        # loop through the vertices and figure out which ones are along the pull_segments
        pts_moved, any_moved = [], False
        for seg in new_segs:
            for o_seg in pull_segments:
                close_pt = closest_point2d_on_line2d(seg.p1, o_seg)
                if seg.p1.distance_to_point(close_pt) <= tolerance:
                    pts_moved.append(True)
                    any_moved = True
                    break
            else:
                pts_moved.append(False)
        if not any_moved:
            return new_polygon

        # set a maximum distance for which constrained points can move
        o_geo = original_polygon
        max_dist = max((o_geo.max.x - o_geo.min.x, o_geo.max.y - o_geo.min.y))
        max_d = max_dist * 10

        # identify the start and end points of each stretch and move them
        edit_boundary = []
        last_vert_i = len(new_verts) - 1
        for i, (pt, moved) in enumerate(zip(new_verts, pts_moved)):
            if moved:
                prev_i = i - 1
                next_i = i + 1 if i != last_vert_i else 0
                if pts_moved[prev_i] and pts_moved[next_i]:  # middle of a stretch
                    edit_boundary.append(pt)
                elif not pts_moved[prev_i] and not pts_moved[next_i]:  # lone moved point
                    edit_boundary.append(pt)
                elif pts_moved[prev_i]:  # the end of a stretch
                    prev_seg, next_new_seg = new_segs[prev_i], new_segs[i]
                    for o_seg in old_segs:
                        if o_seg.p2.is_equivalent(next_new_seg.p2, tolerance):
                            next_seg = o_seg
                            break
                    else:  # failed to find the original segment
                        edit_boundary.append(pt)
                        continue
                    ray_1 = Ray2D(prev_seg.p1, prev_seg.v)
                    ray_2 = Ray2D(next_seg.p2, -next_seg.v)
                    int_pt = ray_1.intersect_line_ray(ray_2)
                    if int_pt is None or int_pt.distance_to_point(next_seg.p1) > max_d:
                        edit_boundary.append(pt)
                    else:
                        edit_boundary.append(Point2D(int_pt.x, int_pt.y))
                else:  # the beginning of a stretch
                    prev_new_seg, next_seg = new_segs[prev_i], new_segs[i]
                    for o_seg in old_segs:
                        if o_seg.p1.is_equivalent(prev_new_seg.p1, tolerance):
                            prev_seg = o_seg
                            break
                    else:  # failed to find the original segment
                        edit_boundary.append(pt)
                        continue
                    ray_1 = Ray2D(prev_seg.p1, prev_seg.v)
                    ray_2 = Ray2D(next_seg.p2, -next_seg.v)
                    int_pt = ray_1.intersect_line_ray(ray_2)
                    if int_pt is None or int_pt.distance_to_point(next_seg.p1) > max_d:
                        edit_boundary.append(pt)
                    else:
                        edit_boundary.append(Point2D(int_pt.x, int_pt.y))
            else:
                edit_boundary.append(pt)

        # rebuild the input geometry
        return Polygon2D(edit_boundary)

    @staticmethod
    def _calculate_min(geometry_objects):
        """Calculate min Point2D around an array of geometry with min attributes.

        This is used in all functions that calculate bounding rectangles around
        dragonfly objects and assess when two objects are in close proximity.
        """
        min_pt = [geometry_objects[0].min.x, geometry_objects[0].min.y]
        for r_geo in geometry_objects[1:]:
            if r_geo.min.x < min_pt[0]:
                min_pt[0] = r_geo.min.x
            if r_geo.min.y < min_pt[1]:
                min_pt[1] = r_geo.min.y
        return Point2D(min_pt[0], min_pt[1])

    @staticmethod
    def _calculate_max(geometry_objects):
        """Calculate max Point2D around an array of geometry with max attributes.

        This is used in all functions that calculate bounding rectangles around
        dragonfly objects and assess when two objects are in close proximity.
        """
        max_pt = [geometry_objects[0].max.x, geometry_objects[0].max.y]
        for r_geo in geometry_objects[1:]:
            if r_geo.max.x > max_pt[0]:
                max_pt[0] = r_geo.max.x
            if r_geo.max.y > max_pt[1]:
                max_pt[1] = r_geo.max.y
        return Point2D(max_pt[0], max_pt[1])

    @staticmethod
    def _rounding_tolerance(tolerance):
        """Get the number of integers to round to based on tolerance.

        This is used to resolve issues when projecting points into the planes
        of roof geometries.
        """
        try:  # get the relative tolerance using a log function
            rtol = int(math.log10(tolerance)) * -1
        except ValueError:
            rtol = 0  # the tol is equal to 1 (out of range for log)
        # account for the fact that the tolerance may not be base 10
        base = int(tolerance * 10 ** (rtol + 1))
        if base == 10 or base == 0:  # tolerance is base 10 (eg. 0.001)
            base = 1
        else:  # tolerance is not base 10 (eg. 0.003)
            rtol += 1
        return rtol

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
