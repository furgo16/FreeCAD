from Arch import createBlocks
import FreeCAD
import Part
from FreeCAD import Vector
import ArchStructure

class _Slab(ArchStructure._Structure):
    """The Slab object."""

    def __init__(self, obj):
        super().__init__(obj)
        self.setProperties(obj)
        obj.IfcType = "Slab"

    def setProperties(self, obj):
        """Add slab-specific properties, including MakeBlocks."""
        super().setProperties(obj)

        if not "MakeBlocks" in obj.PropertiesList:
            obj.addProperty("App::PropertyBool", "MakeBlocks", "Blocks",
                            "Enable this to make the slab generate blocks").MakeBlocks = False
        if not "BlockLength" in obj.PropertiesList:
            obj.addProperty("App::PropertyLength", "BlockLength", "Blocks",
                            "The length of each block").BlockLength = 1000
        if not "BlockHeight" in obj.PropertiesList:
            obj.addProperty("App::PropertyLength", "BlockHeight", "Blocks",
                            "The height of each block").BlockHeight = 500
        if not "OffsetFirst" in obj.PropertiesList:
            obj.addProperty("App::PropertyLength", "OffsetFirst", "Blocks",
                            "The horizontal offset of the first line of blocks").OffsetFirst = 0
        if not "OffsetSecond" in obj.PropertiesList:
            obj.addProperty("App::PropertyLength", "OffsetSecond", "Blocks",
                            "The horizontal offset of the second line of blocks").OffsetSecond = 500
        if not "Joint" in obj.PropertiesList:
            obj.addProperty("App::PropertyLength", "Joint", "Blocks",
                            "The size of the joints between each block").Joint = 50

    def execute(self, obj):
        """Recompute the slab and generate blocks if MakeBlocks is enabled."""
        if obj.MakeBlocks:
            base_shape = obj.Base.Shape
            extrusion_vector = Vector(0, 0, obj.Height.Value)
            base_wires = [base_shape.Wires] if hasattr(base_shape, "Wires") else []
            blocks = createBlocks(base_shape, obj, extrusion_vector, base_wires)
            if blocks:
                obj.Shape = blocks
            else:
                FreeCAD.Console.PrintWarning("Cannot compute blocks for slab.\n")
        else:
            super().execute(obj)