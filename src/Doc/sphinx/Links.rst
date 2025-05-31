App::Link and Related Classes
=============================

FreeCAD's App::Link framework allows creating parametric links between objects,
both within the same document and across different documents.

.. currentmodule:: FreeCAD

.. rubric:: Core Link Class

.. autoclass:: Link
   :members: Link, LinkedObject, LinkPlacement, LinkSubList, LinkSubName, setLink, setLinkSub, getLinkSubEntry, expandLink, resolveGlobalLink, expandSubname
   :undoc-members:
   :show-inheritance:

   .. autoattribute:: LinkedObject
      The object this link points to.

   .. autoattribute:: LinkPlacement
      Controls how the link's placement is handled relative to the linked object.

   .. attribute:: LinkSubList
      For linking to sub-elements, this lists the names of the sub-elements.

   .. attribute:: LinkSubName
      The full sub-element name string (e.g., "Box.Face1").

   .. method:: setLink(obj)

      Sets the main linked object.

   .. method:: setLinkSub(obj, subelements)

      Sets the link to specific sub-elements of an object.


.. rubric:: Link Container Classes

.. autoclass:: LinkGroup
   :members:
   :undoc-members:
   :show-inheritance:

.. autoclass:: LinkElement
   :members:
   :undoc-members:
   :show-inheritance:

.. note::
   The actual properties for linking (like ``LinkedObject``, ``LinkSubList``, etc.)
   are often added dynamically or are part of specific PropertyLink types.
   The methods above are common interactions.
