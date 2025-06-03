The FreeCAD Document
====================
.. currentmodule:: FreeCAD

.. autoclass:: Document
   :members:
   :undoc-members:
   :show-inheritance:

   .. attribute:: Meta
      :type: dict

      A dictionary-like object holding the document's metadata
      (e.g., 'Author', 'Comment', 'Company', 'CreatedBy',
      'CreationDate', 'LastModifiedBy', 'LastModifiedDate', 'License',
      'LicenseURL').
      Example: ``my_author = doc.Meta.get('Author', 'Unknown Author')``