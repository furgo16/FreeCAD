# SPDX-License-Identifier: LGPL-2.1-or-later

"""GUI commands for the new Annotation Style Toolbar."""

import copy
import FreeCAD as App
import FreeCADGui as Gui
from PySide import QtCore, QtGui, QtWidgets

from draftutils import annotation_styles
from draftutils import utils, gui_utils
from draftutils.translate import translate
from draftguitools.gui_annotationstylemanager import AnnotationStyleManagerDialog

# A global reference that will hold the single instance of our selector command
SELECTOR_INSTANCE = None


class Draft_ApplyStyleToSelection:
    """The command to apply the active style to the selection."""

    def GetResources(self):
        return {
            "Pixmap": "Draft_ApplyStyleToSelection",
            "MenuText": "Apply Style to Selection",
            "ToolTip": "Apply the active style to selected annotations",
        }

    def Activated(self):
        if not SELECTOR_INSTANCE:
            return
        style_data = SELECTOR_INSTANCE.get_current_user_data()
        if not style_data:
            return
        style_name = style_data.get("name")
        gui_utils.apply_style_to_objects(style_name, Gui.Selection.getSelection())

    def IsActive(self):
        # This button is always enabled when a document is active.
        # The Activated method will handle the case of an empty selection.
        return Gui.ActiveDocument is not None


class Draft_ApplyStyleToAll:
    """The command to apply the active style to all annotations."""

    def GetResources(self):
        return {
            "Pixmap": "Draft_ApplyStyleToAll",
            "MenuText": "Apply Style to All",
            "ToolTip": "Apply the active style to all annotations in the document",
        }

    def Activated(self):
        if not SELECTOR_INSTANCE:
            return
        style_data = SELECTOR_INSTANCE.get_current_user_data()
        if not style_data:
            return
        style_name = style_data.get("name")
        if not App.ActiveDocument:
            return
        gui_utils.apply_style_to_objects(style_name, App.ActiveDocument.Objects)

    def IsActive(self):
        return Gui.ActiveDocument is not None


class Draft_AnnotationSelector:
    """A command that acts as a placeholder and manager for the style dropdown."""

    def __init__(self):
        # Explicitly parent the combo box to the main window to ensure correct geometry
        self.style_combo = QtWidgets.QComboBox(Gui.getMainWindow())
        self.style_combo.setMinimumWidth(200)
        self.style_combo.setToolTip("Active Annotation Style")

        self.selection_observer = Gui.Selection.addObserver(self)
        App.addDocumentObserver(self)

    def get_current_user_data(self):
        """Returns the user data dictionary of the current item."""
        return self.style_combo.currentData()

    def set_active_style_by_name(self, style_name):
        """Finds a style by its clean document name and sets it as the current item."""
        for i in range(self.style_combo.count()):
            user_data = self.style_combo.itemData(i)
            if user_data and user_data.get("name") == style_name:
                self.style_combo.setCurrentIndex(i)
                return

    def _prepopulate_document_if_needed(self, doc):
        """Checks if a document is uninitialized and adds default styles if so."""
        if not hasattr(doc, "Meta") or doc.Meta.get("Draft_AnnotationStylesInitialized"):
            return

        App.Console.PrintLog(
            f"Performing one-time initialization of annotation styles for document '{doc.Label}'.\n"
        )

        # 1. Find the best default style to add
        default_style_id = annotation_styles.get_default_style_name()
        style_to_add = None
        source_lib = None

        if default_style_id:
            user_styles = annotation_styles.get_user_styles()
            if default_style_id in user_styles:
                style_to_add = user_styles[default_style_id]
                source_lib = "User"
            else:
                system_styles = annotation_styles.get_system_styles()
                style_info = system_styles.get(default_style_id)
                if style_info:
                    style_to_add = style_info.get("properties")
                    source_lib = "System"

        # 2. Fallback if preferred default is not found
        if not style_to_add:
            default_style_id = "_freecad_default_style"
            system_styles = annotation_styles.get_system_styles()
            style_info = system_styles.get(default_style_id, {})
            style_to_add = style_info.get("properties")
            source_lib = "System fallback"

        # 3. Add the style to the document
        if style_to_add:
            style_name = translate("Draft", style_info.get("name", default_style_id))
            App.Console.PrintLog(
                f"Adding default style '{style_name}' from {source_lib} library.\n"
            )
            doc_styles = {style_name: copy.deepcopy(style_to_add)}
            annotation_styles.save_project_styles(doc, doc_styles)

        # 4. Mark document as initialized
        meta = doc.Meta
        meta["Draft_AnnotationStylesInitialized"] = "True"
        doc.Meta = meta

    def update_style_list(self):
        """Reload the list of styles from the active document into the dropdown."""
        self.style_combo.blockSignals(True)
        try:
            current_data = self.style_combo.currentData()
            self.style_combo.clear()

            doc = App.ActiveDocument
            if not doc:
                self.style_combo.setEnabled(False)
                return

            # This is the new pre-population hook
            self._prepopulate_document_if_needed(doc)

            doc_styles = annotation_styles.get_project_styles(doc)

            # The dropdown now only shows document styles
            if doc_styles:
                for name in sorted(doc_styles.keys()):
                    self.style_combo.addItem(name, {"name": name, "source": "document"})

            # Restore previous selection if possible
            if current_data:
                for i in range(self.style_combo.count()):
                    if self.style_combo.itemData(i) == current_data:
                        self.style_combo.setCurrentIndex(i)
                        break

            self.style_combo.setEnabled(self.style_combo.count() > 0)
        finally:
            self.style_combo.blockSignals(False)

    def onSelectionChanged(self, doc, obj, sub, func):
        """Update the dropdown to show the style of the selected object."""
        self.style_combo.blockSignals(True)
        try:
            selection = Gui.Selection.getSelection()
            if (
                len(selection) == 1
                and hasattr(selection[0], "ViewObject")
                and "AnnotationStyle" in selection[0].ViewObject.PropertiesList
            ):
                style_name = selection[0].ViewObject.AnnotationStyle
                # Perform a robust search to find the correct item in the combo box
                self.set_active_style_by_name(style_name)
        finally:
            self.style_combo.blockSignals(False)

        # This is the correct way to force an update of command states
        try:
            Gui.CommandManager.testActive()
        except AttributeError:  # Handles cases where CommandManager might not be available
            Gui.updateGui()

    def onDocumentActivated(self, doc):
        self.update_style_list()

    def onDocumentCreated(self, doc):
        # We don't call update_style_list here, because the document is not yet fully active.
        # The onDocumentActivated event will fire immediately after and handle it.
        pass

    def onDocumentClosed(self, doc):
        if not App.listDocuments():
            self.update_style_list()

    def GetResources(self):
        """A command must have GetResources. This will not be visible."""
        return {
            "Pixmap": "Draft_Annotation_Style",
            "MenuText": "Annotation Style Selector Placeholder",
            "ToolTip": "Internal placeholder for the annotation style widget",
        }

    def Activated(self):
        pass

    def IsActive(self):
        return True


# --- Registration ---

# Register all the commands with FreeCAD
Gui.addCommand("Draft_ApplyStyleToSelection", Draft_ApplyStyleToSelection())
Gui.addCommand("Draft_ApplyStyleToAll", Draft_ApplyStyleToAll())

# First, create the single instance of our command/manager class
SELECTOR_INSTANCE = Draft_AnnotationSelector()
# Then, register that specific instance with FreeCAD
Gui.addCommand("Draft_AnnotationSelector", SELECTOR_INSTANCE)
