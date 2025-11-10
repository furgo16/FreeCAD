# SPDX-License-Identifier: LGPL-2.1-or-later

"""GUI commands for the new Annotation Style Toolbar."""

import copy
import FreeCAD as App
import FreeCADGui as Gui
from PySide import QtCore, QtGui, QtWidgets

from draftutils import annotation_styles
from draftguitools.gui_annotationstylemanager import AnnotationStyleManagerDialog

# A global reference that will hold the single instance of our selector command
SELECTOR_INSTANCE = None


def _ensure_style_in_document(full_style_name):
    """
    Parses a style name from the dropdown. If it's a User or System style,
    it ensures a copy exists in the current document.
    Returns the clean style name upon success, or None on failure.
    """
    if not App.ActiveDocument or not full_style_name:
        return None

    clean_name = full_style_name
    source = "document"

    if full_style_name.endswith(" [User]"):
        clean_name = full_style_name[:-7]
        source = "user"
    elif full_style_name.endswith(" [System]"):
        clean_name = full_style_name[:-9]
        source = "system"

    if source in ["user", "system"]:
        doc_styles = annotation_styles.get_project_styles(App.ActiveDocument)
        if clean_name not in doc_styles:
            App.Console.PrintLog(
                f"Implicitly copying '{clean_name}' from {source} library to the document.\n"
            )
            # Implicit copy is needed
            if source == "user":
                all_user_styles = annotation_styles.get_user_styles()
                style_data = all_user_styles.get(clean_name)
            else:  # source == "system"
                all_system_styles = annotation_styles.get_system_styles()
                style_data = all_system_styles.get(clean_name)

            if style_data:
                doc_styles[clean_name] = copy.deepcopy(style_data)
                annotation_styles.save_project_styles(App.ActiveDocument, doc_styles)
                # Let the main selector instance know it needs to refresh
                if SELECTOR_INSTANCE:
                    SELECTOR_INSTANCE.update_style_list()
                    # After refresh, restore the selection to the newly copied style
                    SELECTOR_INSTANCE.style_combo.setCurrentText(clean_name)

    return clean_name


class Draft_ApplyStyleToSelection:
    """The command to apply the active style to the selection."""

    def GetResources(self):
        return {
            "Pixmap": "document-apply",  # Placeholder icon
            "MenuText": "Apply Style to Selection",
            "ToolTip": "Apply the active style to selected annotations",
        }

    def Activated(self):
        if not SELECTOR_INSTANCE:
            return

        full_style_name = SELECTOR_INSTANCE.get_current_full_style_name()
        style_name = _ensure_style_in_document(full_style_name)
        if not style_name:
            return

        for obj in Gui.Selection.getSelection():
            if "AnnotationStyle" in obj.ViewObject.PropertiesList:
                obj.ViewObject.AnnotationStyle = style_name

    def IsActive(self):
        return Gui.ActiveDocument is not None and not Gui.Selection.isEmpty()


class Draft_ApplyStyleToAll:
    """The command to apply the active style to all annotations."""

    def GetResources(self):
        return {
            "Pixmap": "edit-select-all",  # Placeholder icon
            "MenuText": "Apply Style to All",
            "ToolTip": "Apply the active style to all annotations in the document",
        }

    def Activated(self):
        if not SELECTOR_INSTANCE:
            return

        full_style_name = SELECTOR_INSTANCE.get_current_full_style_name()
        style_name = _ensure_style_in_document(full_style_name)
        if not style_name or not App.ActiveDocument:
            return

        for obj in App.ActiveDocument.Objects:
            if "AnnotationStyle" in obj.ViewObject.PropertiesList:
                obj.ViewObject.AnnotationStyle = style_name

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

    def get_current_full_style_name(self):
        """Returns the full text of the current item, e.g. 'My Style [User]'"""
        return self.style_combo.currentText()

    def update_style_list(self):
        """Reload the list of styles from all sources into the dropdown."""
        self.style_combo.blockSignals(True)
        try:
            current_full_text = self.style_combo.currentText()
            self.style_combo.clear()

            if not App.ActiveDocument:
                self.style_combo.setEnabled(False)
                return

            doc_styles = annotation_styles.get_project_styles(App.ActiveDocument)
            user_styles = annotation_styles.get_user_styles()
            system_styles = annotation_styles.get_system_styles()

            # 1. Add Document Styles
            if doc_styles:
                self.style_combo.addItems(sorted(doc_styles.keys()))

            # 2. Add User Library Styles
            if user_styles:
                if self.style_combo.count() > 0:
                    self.style_combo.insertSeparator(self.style_combo.count())
                for name in sorted(user_styles.keys()):
                    self.style_combo.addItem(f"{name} [User]")

            # 3. Add System Styles
            if system_styles:
                if self.style_combo.count() > 0:
                    self.style_combo.insertSeparator(self.style_combo.count())
                for name in sorted(system_styles.keys()):
                    if name.startswith("_"):
                        continue  # Hide internal-use styles
                    self.style_combo.addItem(f"{name} [System]")

            # Restore previous selection if possible
            idx = self.style_combo.findText(current_full_text)
            if idx != -1:
                self.style_combo.setCurrentIndex(idx)

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
                # Find the plain name, as it must be a document style
                idx = self.style_combo.findText(style_name, QtCore.Qt.MatchExactly)
                if idx != -1:
                    self.style_combo.setCurrentIndex(idx)
        finally:
            self.style_combo.blockSignals(False)

    def onDocumentActivated(self, doc):
        self.update_style_list()

    def onDocumentCreated(self, doc):
        self.update_style_list()

    def onDocumentClosed(self, doc):
        if not App.listDocuments():
            self.update_style_list()

    def GetResources(self):
        """A command must have GetResources. This will not be visible."""
        return {
            "Pixmap": "no-icon",
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
