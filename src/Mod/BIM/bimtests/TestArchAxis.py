# SPDX-License-Identifier: LGPL-2.1-or-later

# ***************************************************************************
# *                                                                         *
# *   Copyright (c) 2025 Furgo                                              *
# *                                                                         *
# *   This file is part of FreeCAD.                                         *
# *                                                                         *
# *   FreeCAD is free software: you can redistribute it and/or modify it    *
# *   under the terms of the GNU Lesser General Public License as           *
# *   published by the Free Software Foundation, either version 2.1 of the  *
# *   License, or (at your option) any later version.                       *
# *                                                                         *
# *   FreeCAD is distributed in the hope that it will be useful, but        *
# *   WITHOUT ANY WARRANTY; without even the implied warranty of            *
# *   MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE. See the GNU      *
# *   Lesser General Public License for more details.                       *
# *                                                                         *
# *   You should have received a copy of the GNU Lesser General Public      *
# *   License along with FreeCAD. If not, see                               *
# *   <https://www.gnu.org/licenses/>.                                      *
# *                                                                         *
# ***************************************************************************

import unittest
import FreeCAD as App
import Arch
from bimtests import TestArchBase

class TestArchMakeAxis(TestArchBase.TestArchBase):

    def test_make_axis_default(self):
        axis = Arch.makeAxis()
        self.assertIsNotNone(axis, "Failed to create a default axis")

    def test_make_axis_custom(self):
        axis = Arch.makeAxis(num=3, size=2000)
        self.assertEqual(len(axis.Distances), 3, "Incorrect number of axes created")
        self.assertEqual(axis.Distances[1], 2000, "Axis size is incorrect")

    def test_axis_properties(self):
        axis = Arch.makeAxis()
        self.assertEqual(axis.Label, "Axes", "Default label is incorrect")