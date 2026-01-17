# SPDX-License-Identifier: LGPL-2.1-or-later
#
# Copyright (c) 2026 Furgo
#
# This file is part of the FreeCAD Arch workbench.
# You can find the full license text in the LICENSE file in the root directory.

"""Command to create and configure Arch Covering objects.

This command creates an Arch Covering object, used to represent surface finishes like flooring, wall
cladding, or ceiling tiles. It opens a task panel allowing the user to select a base face or object
and configure parameters for solid tiles, parametric patterns, or standard hatch patterns.
"""

import FreeCAD

if FreeCAD.GuiUp:
    from PySide import QtCore, QtGui
    import FreeCADGui

    QT_TRANSLATE_NOOP = FreeCAD.Qt.QT_TRANSLATE_NOOP
    translate = FreeCAD.Qt.translate
else:

    def translate(ctxt, txt):
        return txt

    def QT_TRANSLATE_NOOP(ctxt, txt):
        return txt


class BIM_Covering:
    def GetResources(self):
        return {
            "Pixmap": "BIM_Covering",
            "MenuText": QT_TRANSLATE_NOOP("BIM_Covering", "Covering"),
            "ToolTip": QT_TRANSLATE_NOOP(
                "BIM_Covering", "Creates a covering (floor finish, cladding) on a selected face"
            ),
            "Accel": "C, V",
        }

    def IsActive(self):
        return hasattr(FreeCADGui.getMainWindow().getActiveWindow(), "getSceneGraph")

    def Activated(self):
        self.doc = FreeCAD.ActiveDocument
        self.view = FreeCADGui.ActiveDocument.ActiveView

        # Show Task Panel
        import ArchCovering

        self.task = ArchCovering.ArchCoveringTaskPanel(command=self)
        FreeCADGui.Control.showDialog(self.task)

    def finish(self):
        FreeCADGui.Control.closeDialog()
