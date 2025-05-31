The GeoFeature Class
====================

``GeoFeature`` is a base class for document objects that possess a
Part geometry (a TopoShape). It provides the ``Shape`` property.

.. currentmodule:: FreeCAD
.. autoclass:: GeoFeature
   :members:
   :undoc-members:
   :show-inheritance:
   :exclude-members: Shape

   .. autoattribute:: Shape
      The geometric shape associated with this feature.
      (Type: :class:`Part.TopoShape`)
