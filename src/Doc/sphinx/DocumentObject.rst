The FreeCAD Document Object
===========================
.. currentmodule:: FreeCAD
.. autoclass:: DocumentObject
   :show-inheritance:
   :members:

   .. method:: __setstate__(value)
      allows to save custom attributes of this object as strings, so they can be saved when saving the FreeCAD document

   .. method:: __getstate__()
      reads values previously saved with __setstate__()
