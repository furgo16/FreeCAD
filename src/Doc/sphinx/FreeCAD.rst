The FreeCAD module
==================

.. automodule:: FreeCAD
   :members:
   :undoc-members:
   :show-inheritance:
   :exclude-members: Vector, Matrix, Placement, Document, DocumentObject, Console, Units, Extension, DocumentObjectExtension, LinkBaseExtension, DocumentObjectGroup

.. rubric:: Global Document Access

.. attribute:: ActiveDocument
   :annotation: :

   :type: :class:`~Document` or None

   Reference to the currently active document. If no document is active,
   this attribute is ``None``.

   It provides the same reference as calling :func:`~FreeCAD.activeDocument`.

   Example:

   >>> doc = FreeCAD.ActiveDocument
   >>> if doc:
   ...     obj = doc.getObject("MyObjectName")

.. rubric:: Key Core Classes (Exposed on FreeCAD module)

.. autoclass:: FreeCAD.Material
   :members:
   :undoc-members:
   :show-inheritance:
.. autoclass:: FreeCAD.Metadata
   :members:
   :undoc-members:
   :show-inheritance:
.. autoclass:: FreeCAD.Logger
   :members:
   :undoc-members:
   :show-inheritance:

.. rubric:: Core Enums (Exposed on FreeCAD module)
.. autoclass:: FreeCAD.PropertyType
   :members:
.. autoclass:: FreeCAD.ReturnType
   :members:
.. autoclass:: FreeCAD.ScaleType
   :members: