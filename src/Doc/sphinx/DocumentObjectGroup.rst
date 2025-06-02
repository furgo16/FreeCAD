The DocumentObjectGroup Class
=============================

Represents a group of objects within a FreeCAD document. It inherits
capabilities from :class:`~FreeCAD.DocumentObject` and :class:`~FreeCAD.PropertyContainer`.

For managing the objects within the group (e.g., adding, removing, querying objects),
``DocumentObjectGroup`` instances utilize the functionality provided by
:class:`~FreeCAD.GroupExtension`. Please refer to the documentation for
:class:`~FreeCAD.GroupExtension` for methods like ``addObject()``,
``addObjects()``, ``hasObject()``, etc.

The primary instance attribute to access the list of contained objects directly
is typically ``Group``. Standard properties like ``Label`` and ``Visibility`` are
inherited from :class:`~FreeCAD.DocumentObject`.

.. currentmodule:: FreeCAD

.. autoclass:: DocumentObjectGroup
   :show-inheritance:

   .. autoattribute:: Name
   .. autoattribute:: Content
