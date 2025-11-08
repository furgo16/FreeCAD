# SPDX-License-Identifier: LGPL-2.1-or-later

"""GUI command for the new Annotation Style Manager."""

import FreeCAD as App
import FreeCADGui as Gui
from PySide import QtCore, QtGui, QtWidgets

from draftutils import annotation_styles
from draftutils.translate import translate
import os


class AnnotationStyleManagerDialog:
    """The Annotation Style Manager dialog class."""

    def __init__(self, doc):
        self.doc = doc

        # Load the UI file
        # This path is an alias defined in Draft.qrc
        self.form = Gui.PySideUic.loadUi(":/ui/dialog_AnnotationStyleManager.ui")

        # Data storage
        self.project_styles = {}
        self.user_styles = {}
        self.system_styles = {}
        self.default_style_name = ""

        # UI element references
        self.tree = self.form.treeWidget_Styles
        self.project_root = None
        self.user_root = None
        self.system_root = None

        self._populate_styles()
        self._connect_signals()

    def _populate_styles(self):
        """Load styles from all sources and populate the tree widget."""
        self.project_styles = annotation_styles.get_project_styles(self.doc)
        self.user_styles = annotation_styles.get_user_styles()
        self.system_styles = annotation_styles.get_system_styles()
        self.default_style_name = annotation_styles.get_default_style_name()

        self.tree.clear()

        # Create root nodes
        self.project_root = QtWidgets.QTreeWidgetItem(self.tree, ["Project Styles"])
        self.user_root = QtWidgets.QTreeWidgetItem(self.tree, ["User Library"])
        self.system_root = QtWidgets.QTreeWidgetItem(self.tree, ["System Styles"])

        # Set root nodes to be bold and non-selectable
        font = self.project_root.font(0)
        font.setBold(True)
        for root in [self.project_root, self.user_root, self.system_root]:
            root.setFont(0, font)
            root.setFlags(root.flags() & ~QtCore.Qt.ItemIsSelectable)

        # Populate children
        for name in sorted(self.project_styles.keys()):
            QtWidgets.QTreeWidgetItem(self.project_root, [name])

        for name in sorted(self.user_styles.keys()):
            item = QtWidgets.QTreeWidgetItem(self.user_root, [name])
            if name == self.default_style_name:
                item.setText(0, f"{name} (default)")
                item.setFont(0, font)

        for name in sorted(self.system_styles.keys()):
            item = QtWidgets.QTreeWidgetItem(self.system_root, [name])
            # Make system styles appear italicized to indicate they are read-only
            font.setItalic(True)
            item.setFont(0, font)

        self.tree.expandAll()

    def _connect_signals(self):
        """Connect all UI element signals to their corresponding slots."""
        self.form.pushButton_New.clicked.connect(self.on_new)
        self.form.pushButton_Delete.clicked.connect(self.on_delete)
        self.form.pushButton_Rename.clicked.connect(self.on_rename)
        self.form.pushButton_SetDefault.clicked.connect(self.on_set_default)
        self.form.pushButton_Import.clicked.connect(self.on_import)
        self.form.pushButton_Export.clicked.connect(self.on_export)
        self.tree.currentItemChanged.connect(self.on_selection_changed)

        # TODO: Connect signals for all property editor widgets (e.g., self.form.FontSize.textChanged)
        # to an `on_property_changed` slot to update the style data in real-time.

    def on_selection_changed(self, current, previous):
        """Handle when the user selects a different style in the tree."""
        # First, save any changes made to the previously selected style
        if previous and previous.parent():  # Ensure it's a style, not a root
            self._save_editor_to_style(previous)

        # Update button enable states and populate the editor
        self._update_ui_state()
        if current and current.parent():  # Ensure it's a style, not a root
            self._populate_editor_from_style(current)
        else:
            self._clear_and_disable_editor()

    def _update_ui_state(self):
        """Update the enabled/disabled state of all buttons based on selection."""
        item = self.tree.currentItem()
        is_style = item and item.parent() is not None
        is_project_style = is_style and item.parent() is self.project_root
        is_user_style = is_style and item.parent() is self.user_root
        is_system_style = is_style and item.parent() is self.system_root

        # Management buttons
        self.form.pushButton_Delete.setEnabled(is_project_style or is_user_style)
        self.form.pushButton_Rename.setEnabled(is_project_style or is_user_style)
        self.form.pushButton_SetDefault.setEnabled(is_user_style)

        # Import/Export buttons
        self.form.pushButton_Import.setEnabled(is_user_style or is_system_style)
        self.form.pushButton_Export.setEnabled(is_project_style)

        # Property editor
        self.form.scrollArea_Properties.setEnabled(is_project_style or is_user_style)

    def _populate_editor_from_style(self, item):
        """Fill the property editor fields with values from the selected style."""
        # TODO: Implement the logic to get the style dict and set all widget values.
        # This will be similar to the old `fill_editor` method.
        # For example:
        # style_name = item.text(0).split(" (default)")[0]
        # if item.parent() is self.project_root:
        #     style_data = self.project_styles.get(style_name, {})
        # ...
        # self.form.FontSize.setText(str(style_data.get("FontSize", 0)))
        pass

    def _save_editor_to_style(self, item):
        """Save the current values from the property editor into the style data dict."""
        # TODO: Implement the logic to get all widget values and update the correct
        # self.project_styles or self.user_styles dictionary.
        # This will be similar to the old `get_editor_values` method.
        pass

    def _clear_and_disable_editor(self):
        """Clear all fields and disable the property editor."""
        # TODO: Clear all input fields in the property editor.
        self.form.scrollArea_Properties.setEnabled(False)

    def on_new(self):
        # TODO: Implement logic to create a new style
        pass

    def on_delete(self):
        # TODO: Implement logic to delete the selected style
        pass

    def on_rename(self):
        # TODO: Implement logic to rename the selected style
        pass

    def on_set_default(self):
        # TODO: Implement logic to set the selected user style as default
        pass

    def on_import(self):
        # TODO: Implement logic to copy a user/system style to project styles
        pass

    def on_export(self):
        # TODO: Implement logic to copy a project style to user styles
        pass

    def execute(self):
        """Show the dialog and wait for user input."""
        if self.form.exec_():
            # OK was clicked, save everything

            # Final save of the currently selected item in the editor
            current_item = self.tree.currentItem()
            if current_item and current_item.parent():
                self._save_editor_to_style(current_item)

            annotation_styles.save_project_styles(self.doc, self.project_styles)
            annotation_styles.save_user_styles(self.user_styles)
            return True
        return False


# Command to launch the dialog
class Draft_AnnotationStyleEditor_Command:
    """The command to launch the Annotation Style Manager dialog."""

    def GetResources(self):
        # TODO: Define icon, menu text, and tooltip
        return {
            "Pixmap": "Draft_Annotation_Style",
            "MenuText": "Annotation Style Editor...",
            "ToolTip": "Manage annotation styles for this document and your user library.",
        }

    def Activated(self):
        if not App.ActiveDocument:
            App.Console.PrintWarning(
                "An active document is required to manage annotation styles.\n"
            )
            return

        dialog = AnnotationStyleManagerDialog(App.ActiveDocument)
        dialog.execute()

    def IsActive(self):
        return Gui.ActiveDocument is not None


Gui.addCommand("Draft_AnnotationStyleEditor", Draft_AnnotationStyleEditor_Command())
