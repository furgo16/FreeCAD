# SPDX-License-Identifier: LGPL-2.1-or-later

"""GUI commands for the new Annotation Style Toolbar."""

import FreeCAD as App
import FreeCADGui as Gui
from PySide import QtCore, QtGui, QtWidgets

from draftutils import annotation_styles

# Global reference to hold the single instance of the selector command
SELECTOR_INSTANCE = None

# --- Command Classes ---


class Draft_ApplyStyleToSelection:
    """The command to apply the active style to the selection."""

    def GetResources(self):
        return {
            "Pixmap": "document-apply",  # Placeholder icon
            "MenuText": "Apply Style to Selection",
            "ToolTip": "Apply the active style to selected annotations",
        }

    def Activated(self):
        selector = Gui.getCommand("Draft_AnnotationSelector")
        style_name = selector.get_current_style_name()
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
            "ToolTip": "Apply the active style to ALL annotations in the document",
        }

    def Activated(self):
        selector = Gui.getCommand("Draft_AnnotationSelector")
        style_name = selector.get_current_style_name()
        if not style_name or not App.ActiveDocument:
            return

        for obj in App.ActiveDocument.Objects:
            if "AnnotationStyle" in obj.ViewObject.PropertiesList:
                obj.ViewObject.AnnotationStyle = style_name

    def IsActive(self):
        return Gui.ActiveDocument is not None


class Draft_AnnotationSelector:
    """A command that acts as a placeholder and manager for the style dropdown."""

    _instance = None

    def __new__(cls):
        if cls._instance is None:
            cls._instance = super(Draft_AnnotationSelector, cls).__new__(cls)
        return cls._instance

    def __init__(self):
        self.style_combo = QtWidgets.QComboBox()
        self.style_combo.setMinimumWidth(150)
        self.style_combo.setToolTip("Active Annotation Style")
        self.style_combo.currentIndexChanged.connect(self.on_combo_changed)

        self.selection_observer = Gui.Selection.addObserver(self)
        App.addDocumentObserver(self)

    def get_current_style_name(self):
        return self.style_combo.currentText()

    def update_style_list(self):
        """Reload the list of styles from the active document."""
        self.style_combo.blockSignals(True)
        try:
            current = self.style_combo.currentText()
            self.style_combo.clear()
            if App.ActiveDocument:
                styles = annotation_styles.get_project_styles(App.ActiveDocument)
                if styles:
                    self.style_combo.addItems(sorted(styles.keys()))
                    idx = self.style_combo.findText(current)
                    if idx != -1:
                        self.style_combo.setCurrentIndex(idx)
            self.style_combo.setEnabled(self.style_combo.count() > 0)
        finally:
            self.style_combo.blockSignals(False)

    def on_combo_changed(self, index):
        """Called when the user manually changes the style in the dropdown."""
        # This can be used in the future to auto-apply styles on change if desired,
        # but for now our explicit "Apply" buttons handle this.
        pass

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
                idx = self.style_combo.findText(style_name)
                if idx != -1:
                    self.style_combo.setCurrentIndex(idx)
            # If multiple or non-annotation objects are selected, do not change the combobox
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
        return {
            "Pixmap": "no-icon",
            "MenuText": "Annotation Style Selector",
            "ToolTip": "A placeholder for the annotation style widget",
        }

    def Activated(self):
        pass  # This command does nothing when clicked

    def IsActive(self):
        return True


# Register all the commands with FreeCAD
Gui.addCommand("Draft_ApplyStyleToSelection", Draft_ApplyStyleToSelection())
Gui.addCommand("Draft_ApplyStyleToAll", Draft_ApplyStyleToAll())

# First, create the single instance of our command/manager class
SELECTOR_INSTANCE = Draft_AnnotationSelector()
# Then, register that specific instance with FreeCAD
Gui.addCommand("Draft_AnnotationSelector", SELECTOR_INSTANCE)
