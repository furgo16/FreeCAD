# SPDX-License-Identifier: LGPL-2.1-or-later
#
# Copyright (c) 2026 Furgo
#
# This file is part of the FreeCAD Arch workbench.
# You can find the full license text in the LICENSE file in the root directory.

"""The Covering object and tools.

This module provides tools to build Covering objects. Coverings are claddings, floorings,
wallpapers, etc. applied to other construction elements, but can also be independent. They support
solid 3D tiles, parametric 2D patterns, and hatch patterns.
"""

import FreeCAD
import Part
import ArchComponent
import Arch
import ArchTessellation
from draftutils import params

MIN_DIMENSION = 0.1


# Translation shims for headless and static analysis
def translate(context, sourceText, disambiguation=None, n=-1):
    return sourceText


def QT_TRANSLATE_NOOP(context, sourceText):
    return sourceText


if FreeCAD.GuiUp:
    # Runtime override using native FreeCAD.Qt abstraction
    translate = FreeCAD.Qt.translate
    QT_TRANSLATE_NOOP = FreeCAD.Qt.QT_TRANSLATE_NOOP


class _Covering(ArchComponent.Component):
    """
    A parametric object representing an architectural surface finish.

    This class manages the generation of surface treatments such as tiles, panels, flooring, or
    hatch patterns. Coverings are typically linked to a specific face of a base object and remain
    parametric, updating automatically if the underlying geometry changes.

    Parameters
    ----------
    obj : App::FeaturePython
        The base C++ object to be initialized as a Covering.

    Notes
    -----
    While the standard FreeCAD `TypeId` attribute identifies the underlying C++ class, the `Type`
    attribute is used by the Arch module to distinguish functional object types that share the same
    C++ implementation.

    Examples
    --------
    >>> print(obj.TypeId, "->", obj.Proxy.Type)
    Part::FeaturePython -> Covering
    >>> import Draft; Draft.get_type(obj)
    'Covering'
    """

    def __init__(self, obj):
        super().__init__(obj)

        # Override the parent's object type to set a specific one for Covering
        self.Type = "Covering"

        # Apply the property schema
        self.setProperties(obj)

        # Initialize properties with user preferences (params) upon object creation (but not on
        # document restore).
        # The properties mapped to parameters here are generally the ones that are editable in the
        # object's Task Panel. Since the UI binds to these properties, the Task Panel will
        # automatically display these values as the defaults without extra UI logic.
        obj.TileLength = params.get_param_arch("CoveringLength")
        obj.TileWidth = params.get_param_arch("CoveringWidth")
        obj.TileThickness = params.get_param_arch("CoveringThickness")
        obj.JointWidth = params.get_param_arch("CoveringJoint")
        obj.Rotation = params.get_param_arch("CoveringRotation")
        obj.TileAlignment = params.get_param_arch("CoveringAlignment")
        obj.FinishMode = params.get_param_arch("CoveringFinishMode")

    def setProperties(self, obj):
        """
        Overrides the parent method to define properties specific to the Covering object, including
        tiling and pattern schema, and ensures 'Base' supports sub-element face targeting.
        """
        # Override parent properties to ensure 'Base' is LinkSub (parent defines it as Link).
        # Covering objects use sub-element links (LinkSub) because they need to target specific
        # faces.
        if (
            "Base" in obj.PropertiesList
            and obj.getTypeIdOfProperty("Base") != "App::PropertyLinkSub"
        ):
            obj.setPropertyStatus("Base", "-LockDynamic")
            obj.removeProperty("Base")
        if "Base" not in obj.PropertiesList:
            obj.addProperty(
                "App::PropertyLinkSub",
                "Base",
                "Covering",
                QT_TRANSLATE_NOOP(
                    "App::Property", "The object or face this covering is applied to"
                ),
                locked=True,
            )

        # Apply the parent's property schema.
        super().setProperties(obj)

        # Snapshot properties once
        properties_list = obj.PropertiesList

        # Apply the local property schema
        # (Type, Name, Group, Tooltip, InitialValue)
        properties_schema = [
            (
                "App::PropertyEnumeration",
                "FinishMode",
                "Covering",
                "How the finish is created and displayed:\n"
                "- Solid Tiles: Physical 3D tiles with real gaps. Best for accurate detail and counting.\n"
                "- Parametric Pattern: A grid of lines on a single slab. Faster to display than real tiles.\n"
                "- Monolithic: A single smooth surface. Ideal for paint, plaster, or seamless flooring.\n"
                "- Hatch Pattern: Technical drafting symbols (hatching) on a single slab.",
                ["Solid Tiles", "Parametric Pattern", "Monolithic", "Hatch Pattern"],
            ),
            (
                "App::PropertyEnumeration",
                "TileAlignment",
                "Covering",
                "The alignment of the tile grid",
                ["Center", "TopLeft", "TopRight", "BottomLeft", "BottomRight"],
            ),
            ("App::PropertyAngle", "Rotation", "Covering", "Rotation of the finish", 0),
            ("App::PropertyLength", "TileLength", "Tiles", "The length of the tiles", 0),
            ("App::PropertyLength", "TileWidth", "Tiles", "The width of the tiles", 0),
            ("App::PropertyLength", "TileThickness", "Tiles", "The thickness of the tiles", 0),
            ("App::PropertyLength", "JointWidth", "Tiles", "The width of the joints", None),
            (
                "App::PropertyEnumeration",
                "StaggerType",
                "Tiles",
                "The running bond logic",
                [
                    "Stacked (None)",
                    "Half Bond (1/2)",
                    "Third Bond (1/3)",
                    "Quarter Bond (1/4)",
                    "Custom",
                ],
            ),
            (
                "App::PropertyLength",
                "StaggerCustom",
                "Tiles",
                "Custom offset for running bond rows",
                0.0,
            ),
            (
                "App::PropertyVector",
                "AlignmentOffset",
                "Tiles",
                "A manual offset to shift the grid origin (X=U, Y=V). The Z component is ignored",
                None,
            ),
            (
                "App::PropertyLength",
                "BorderSetback",
                "Boundaries",
                "Distance to offset the covering inwards from the base boundary",
                0.0,
            ),
            (
                "App::PropertyEnumeration",
                "PerimeterJointType",
                "Boundaries",
                "How to handle the joint between the covering and the boundary",
                ["None", "Half Interior", "Full Interior", "Custom"],
            ),
            (
                "App::PropertyLength",
                "PerimeterJointWidth",
                "Boundaries",
                "Custom width for the perimeter joint",
                0.0,
            ),
            ("App::PropertyArea", "NetArea", "Quantities", "The surface area of the base face", 0),
            (
                "App::PropertyArea",
                "GrossArea",
                "Quantities",
                "Total area of material units consumed (Full + Partial)",
                0,
            ),
            (
                "App::PropertyArea",
                "WasteArea",
                "Quantities",
                "The area of discarded material (Gross - Net)",
                0,
            ),
            (
                "App::PropertyLength",
                "TotalJointLength",
                "Quantities",
                "The total linear length of all joints",
                0,
            ),
            (
                "App::PropertyLength",
                "PerimeterLength",
                "Quantities",
                "The length of the substrate perimeter",
                0,
            ),
            ("App::PropertyInteger", "CountFullTiles", "Quantities", "The number of full tiles", 0),
            (
                "App::PropertyInteger",
                "CountPartialTiles",
                "Quantities",
                "The number of cut/partial tiles",
                0,
            ),
            (
                "App::PropertyFile",
                "PatternFile",
                "Pattern",
                "The PAT file to use for hatching",
                None,
            ),
            (
                "App::PropertyString",
                "PatternName",
                "Pattern",
                "The name of the pattern in the PAT file",
                "",
            ),
            (
                "App::PropertyFloat",
                "PatternScale",
                "Pattern",
                "The scale of the hatch pattern",
                1.0,
            ),
            (
                "App::PropertyEnumeration",
                "IfcPredefinedType",
                "IFC",
                "The specific type of covering",
                [
                    "FLOORING",
                    "CLADDING",
                    "ROOFING",
                    "MOLDING",
                    "SKIRTINGBOARD",
                    "CEILING",
                    "WRAPPING",
                    "NOTDEFINED",
                ],
            ),
        ]

        for prop_type, name, group, tooltip, default in properties_schema:
            if name not in properties_list:
                obj.addProperty(
                    prop_type, name, group, QT_TRANSLATE_NOOP("App::Property", tooltip), locked=True
                )

                # Apply defined default values
                if default is not None:
                    setattr(obj, name, default)

        # Property status configuration (Read-Only fields)
        obj.setEditorMode("NetArea", 1)
        obj.setEditorMode("GrossArea", 1)
        obj.setEditorMode("WasteArea", 1)
        obj.setEditorMode("TotalJointLength", 1)
        obj.setEditorMode("PerimeterLength", 1)
        obj.setEditorMode("CountFullTiles", 1)
        obj.setEditorMode("CountPartialTiles", 1)

    def loads(self, state):
        """
        Overrides the parent callback used by FreeCAD's persistence engine to restore the
        Python proxy instance and reset non-persistent internal attributes like 'Type'.
        """
        self.Type = "Covering"

    def onDocumentRestored(self, obj):
        """
        Overrides the parent callback triggered after the document is fully restored. Used to
        ensure property schema consistency and perform backward compatibility migrations.
        """
        super().onDocumentRestored(obj)
        self.setProperties(obj)

    def onChanged(self, obj, prop):
        """Method called when a property is changed."""
        ArchComponent.Component.onChanged(self, obj, prop)

    def _get_layout_frame(self, face):
        """
        Returns a right-handed orthonormal basis derived from the face surface.
        The basis is normalized to ensure tangents point in positive global
        directions, providing a predictable origin for semantic alignments like
        'BottomLeft'.
        """
        u_vec, v_vec, normal, center = Arch.getFaceUV(face)

        # We align the surface normal with the topological orientation of the
        # face. If the face is reversed (common in solid sub-elements), we
        # negate the normal to ensure the basis points out from the material.
        if face.Orientation == "Reversed":
            normal = -normal

        # We force the tangents into positive global directions. This ensures
        # that local coordinate calculations for grid alignment consistently
        # map to the physical orientation of the object in world space.
        for vec in [u_vec, v_vec]:
            vals = [abs(vec.x), abs(vec.y), abs(vec.z)]
            max_val = max(vals)
            if max_val > 0.1:
                if vec[vals.index(max_val)] < 0:
                    vec.multiply(-1)

        # Ensure strict orthogonality and right-handedness (U x V = N).
        u_vec.normalize()
        v_vec = normal.cross(u_vec).normalize()
        u_vec = v_vec.cross(normal).normalize()

        return u_vec, v_vec, normal, center

    def execute(self, obj):
        """
        Calculates the geometry of the finish by localizing the base face to the
        origin, applying offsets, and executing the pattern tessellator. The
        result is then moved to the original global position using the object's
        placement property to avoid double transformations.
        """
        import Part

        if self.clone(obj):
            return

        base_face = Arch.getFaceGeometry(obj.Base)
        if not base_face:
            return

        # We establish a stable coordinate system based on the global axes.
        u_vec, v_vec, normal, center = self._get_layout_frame(base_face)

        # Define the transformation to the local XY plane at the origin.
        local_pl = FreeCAD.Placement(center, FreeCAD.Rotation(u_vec, v_vec, normal))
        to_local = local_pl.inverse().toMatrix()

        # Create the localized face.
        safe_face = base_face.copy()
        safe_face.transformShape(to_local)

        effective_face = safe_face
        joint_contribution = 0.0
        if hasattr(obj, "PerimeterJointType"):
            if obj.PerimeterJointType == "Half Interior":
                joint_contribution = obj.JointWidth.Value / 2.0
            elif obj.PerimeterJointType == "Full Interior":
                joint_contribution = obj.JointWidth.Value
            elif obj.PerimeterJointType == "Custom":
                joint_contribution = obj.PerimeterJointWidth.Value

        # Apply boundary offsets in the local space.
        total_offset = obj.BorderSetback.Value + joint_contribution
        if total_offset > 0:
            shrunk = safe_face.makeOffset2D(-total_offset)
            if not shrunk.isNull() and shrunk.Area > 0:
                effective_face = shrunk

        # Determine the pattern origin in local space.
        origin_local = Arch.getFaceGridOrigin(
            effective_face,
            FreeCAD.Vector(0, 0, 0),
            FreeCAD.Vector(1, 0, 0),
            FreeCAD.Vector(0, 1, 0),
            obj.TileAlignment,
            obj.AlignmentOffset,
        )

        # Shift the origin so that the tile boundary aligns with the face edge.
        if obj.TileAlignment == "Center":
            origin_local.x -= obj.TileLength.Value / 2.0
            origin_local.y -= obj.TileWidth.Value / 2.0
        else:
            if "Right" in obj.TileAlignment:
                origin_local.x += obj.JointWidth.Value
            if "Top" in obj.TileAlignment:
                origin_local.y += obj.JointWidth.Value

        # Configure the tessellator.
        is_solid_mode = obj.FinishMode in ["Solid Tiles", "Monolithic"]
        config = {
            "TileLength": obj.TileLength.Value,
            "TileWidth": obj.TileWidth.Value,
            "JointWidth": obj.JointWidth.Value,
            "Rotation": obj.Rotation.Value,
            "PatternFile": obj.PatternFile,
            "PatternName": obj.PatternName,
            "PatternScale": obj.PatternScale,
            "TileThickness": obj.TileThickness.Value,
            "Extrude": is_solid_mode,
            "StaggerType": getattr(obj, "StaggerType", "Stacked (None)"),
            "StaggerCustom": getattr(obj, "StaggerCustom", FreeCAD.Units.Quantity(0)).Value,
        }

        tessellator = ArchTessellation.create_tessellator(obj.FinishMode, config)
        res = tessellator.compute(
            effective_face,
            origin_local,
            FreeCAD.Vector(1, 0, 0),
            FreeCAD.Vector(0, 1, 0),
            FreeCAD.Vector(0, 0, 1),
        )

        # Update the UI with any status messages from the engine.
        match res.status:
            case ArchTessellation.TessellationStatus.INVALID_DIMENSIONS:
                FreeCAD.Console.PrintWarning(
                    translate("Arch", "The specified tile size is too small to be modeled.") + "\n"
                )
                obj.Shape = Part.Shape()
                return
            case ArchTessellation.TessellationStatus.JOINT_TOO_SMALL:
                FreeCAD.Console.PrintWarning(
                    translate("Arch", "The joint width is too small to model individual units.")
                    + "\n"
                )
            case ArchTessellation.TessellationStatus.COUNT_TOO_HIGH:
                FreeCAD.Console.PrintWarning(
                    translate(
                        "Arch",
                        "The number of tiles is too high for individual units to be modeled.",
                    )
                    + "\n"
                )
            case ArchTessellation.TessellationStatus.EXTREME_COUNT:
                FreeCAD.Console.PrintWarning(
                    translate(
                        "Arch", "The number of tiles is extremely high. Layout lines are hidden."
                    )
                    + "\n"
                )
            case _:
                pass

        if res.geometry:
            # We assign the local-space geometry and update the object
            # placement to position it correctly in world space.
            obj.Shape = res.geometry
            obj.Placement = local_pl
        else:
            obj.Shape = Part.Shape()

        # Update Quantity Take-Off properties.
        obj.CountFullTiles = res.quantities.count_full
        obj.CountPartialTiles = res.quantities.count_partial
        obj.NetArea = res.quantities.area_net
        obj.GrossArea = res.quantities.area_gross
        obj.WasteArea = res.quantities.waste_area
        obj.TotalJointLength = res.quantities.length_joints
        obj.PerimeterLength = res.quantities.length_perimeter
