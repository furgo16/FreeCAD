The FreeCAD.Base Module
=======================

This module provides fundamental geometric types, core system services, and base functionalities.
Many of its classes (like Vector, Matrix, Placement) are also directly available
under the top-level ``FreeCAD`` module for convenience.

.. automodule:: FreeCAD.Base
   :members:
   :undoc-members:
   :show-inheritance:
   :exclude-members: Vector, Matrix, Placement

   .. rubric:: Core Utility Classes (Examples)

   .. autoclass:: FreeCAD.Base.TypeId
      :members:
      :undoc-members:
      :show-inheritance:

   .. autoclass:: FreeCAD.Base.Precision
      :members:
      :undoc-members:
      :show-inheritance:

   .. autoclass:: FreeCAD.Base.ProgressIndicator
      :members:
      :undoc-members:
      :show-inheritance:

   .. autoclass:: FreeCAD.Base.CoordinateSystem
      :members:
      :undoc-members:
      :show-inheritance:

   .. autoclass:: FreeCAD.Base.Vector2d
      :members:
      :undoc-members:
      :show-inheritance:

   .. autoclass:: FreeCAD.Base.Rotation
      :members:
      :undoc-members:
      :show-inheritance:

   .. autoclass:: FreeCAD.Base.Axis
      :members:
      :undoc-members:
      :show-inheritance:

   .. autoclass:: FreeCAD.Base.BoundBox
      :members:
      :undoc-members:
      :show-inheritance:

.. rubric:: Core Exception Classes

.. autoexception:: FreeCAD.Base.AbortIOException
.. autoexception:: FreeCAD.Base.BadFormatError
.. autoexception:: FreeCAD.Base.BadGraphError
.. autoexception:: FreeCAD.Base.CADKernelError
.. autoexception:: FreeCAD.Base.ExpressionError
.. autoexception:: FreeCAD.Base.FreeCADAbort
.. autoexception:: FreeCAD.Base.FreeCADError
.. autoexception:: FreeCAD.Base.ParserError
.. autoexception:: FreeCAD.Base.PropertyError
.. autoexception:: FreeCAD.Base.UnknownProgramOption
.. autoexception:: FreeCAD.Base.XMLAttributeError
.. autoexception:: FreeCAD.Base.XMLBaseException
.. autoexception:: FreeCAD.Base.XMLParseException
