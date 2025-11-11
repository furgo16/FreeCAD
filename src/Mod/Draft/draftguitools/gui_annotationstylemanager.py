# SPDX-License-Identifier: LGPL-2.1-or-later

"""GUI command for the new Annotation Style Manager."""

import os
import copy
import FreeCAD as App
import FreeCADGui as Gui
from PySide import QtCore, QtGui, QtWidgets

from draftutils import annotation_styles
from draftutils import utils
from draftutils.translate import translate

# A map defining the widget type for each style property.
# This helps automate getting/setting values from the UI form.
PROPERTY_MAP = {
    "ScaleMultiplier": "float",
    "FontName": "font",
    "FontSize": "length",
    "LineSpacing": "float",
    "TextColor": "color",
    "ShowLine": "bool",
    "LineWidth": "int",
    "LineColor": "color",
    "ArrowTypeStart": "index",
    "ArrowSizeStart": "length",
    "ArrowTypeEnd": "index",
    "ArrowSizeEnd": "length",
    "ShowUnit": "bool",
    "UnitOverride": "str",
    "Decimals": "int",
    "DimOvershoot": "length",
    "ExtLines": "length",
    "ExtOvershoot": "length",
    "TextSpacing": "length",
}


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
        self.is_deleting = False  # Flag to prevent saving a deleted item

        # UI element references
        self.tree = self.form.treeWidget_Styles
        self.project_root = None
        self.user_root = None
        self.system_root = None

        self._initialize_widgets()  # New method call for setup
        self._populate_styles()
        self._connect_signals()
        self.on_selection_changed(None, None)  # Set initial state

    def _initialize_widgets(self):
        """Populate widgets that have a fixed list of items, like dropdowns."""
        # This is the UI setup logic that was missing.
        for arrow_type in utils.ARROW_TYPES:
            self.form.ArrowTypeStart.addItem(translate("draft", arrow_type))
            self.form.ArrowTypeEnd.addItem(translate("draft", arrow_type))

    def _populate_styles(self):
        """Load styles from all sources and populate the tree widget."""
        self.project_styles = annotation_styles.get_project_styles(self.doc)
        self.user_styles = annotation_styles.get_user_styles()
        self.system_styles = annotation_styles.get_system_styles()
        self.default_style_name = annotation_styles.get_default_style_name()

        self.tree.clear()

        # Create root nodes
        self.project_root = QtWidgets.QTreeWidgetItem(
            self.tree, [translate("Draft", "Document styles")]
        )
        self.project_root.setToolTip(0, "Styles saved only within this document.")
        self.user_root = QtWidgets.QTreeWidgetItem(self.tree, [translate("Draft", "User library")])
        self.user_root.setToolTip(0, "Styles available in all of your documents.")
        self.system_root = QtWidgets.QTreeWidgetItem(
            self.tree, [translate("Draft", "System styles")]
        )
        self.system_root.setToolTip(0, "Read-only template styles included with FreeCAD.")

        # Set root nodes to be bold
        font = self.project_root.font(0)
        font.setBold(True)
        for root in [self.project_root, self.user_root, self.system_root]:
            root.setFont(0, font)

        bold_font = QtGui.QFont(font)
        bold_font.setBold(True)

        # Populate children
        for name in sorted(self.project_styles.keys()):
            item = QtWidgets.QTreeWidgetItem(self.project_root, [name])
            item.setData(0, QtCore.Qt.UserRole, name)

        for name in sorted(self.user_styles.keys()):
            item = QtWidgets.QTreeWidgetItem(self.user_root, [name])
            item.setData(0, QtCore.Qt.UserRole, name)
            if name == self.default_style_name:
                item.setFont(0, bold_font)

        # System styles now have a different structure
        for style_id, style_data in sorted(self.system_styles.items()):
            if style_id.startswith("_"):
                continue  # Hide internal-use styles
            translatable_name = translate("Draft", style_data["name"])
            item = QtWidgets.QTreeWidgetItem(self.system_root, [translatable_name])
            # Make system styles italic
            italic_font = QtGui.QFont()
            italic_font.setItalic(True)
            item.setFont(0, italic_font)
            # Store the stable, non-translatable id in the item's data
            item.setData(0, QtCore.Qt.UserRole, style_id)

        self.tree.expandAll()

    def _connect_signals(self):
        """Connect all UI element signals to their corresponding slots."""
        self.form.pushButton_New.clicked.connect(self.on_new)
        self.form.pushButton_Copy.clicked.connect(self.on_copy)
        self.form.pushButton_Delete.clicked.connect(self.on_delete)
        self.form.pushButton_Rename.clicked.connect(self.on_rename)
        self.form.pushButton_SetDefault.clicked.connect(self.on_set_default)
        self.tree.currentItemChanged.connect(self.on_selection_changed)
        # Enable the context menu
        self.tree.setContextMenuPolicy(QtCore.Qt.CustomContextMenu)
        self.tree.customContextMenuRequested.connect(self.on_context_menu)

    def on_selection_changed(self, current, previous):
        """Handle when the user selects a different style in the tree."""
        # Before changing selection, save any edits to the previous item
        # unless we are in the middle of a deletion operation.
        if (
            previous
            and previous.parent()
            and not self.is_deleting
            and self.form.scrollArea_Properties.isEnabled()
        ):
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
        is_style = item is not None and item.parent() is not None
        is_project_style = is_style and item.parent() is self.project_root
        is_user_style = is_style and item.parent() is self.user_root
        is_system_style = is_style and item.parent() is self.system_root

        # Allow creating a new style if a creatable root or item is selected
        can_create = item is not None and (
            item.parent() in [self.project_root, self.user_root]
            or item in [self.project_root, self.user_root]
        )

        # Management buttons
        self.form.pushButton_New.setEnabled(can_create)
        self.form.pushButton_Copy.setEnabled(is_project_style or is_user_style)
        self.form.pushButton_Delete.setEnabled(is_project_style or is_user_style)
        self.form.pushButton_Rename.setEnabled(is_project_style or is_user_style)
        self.form.pushButton_SetDefault.setEnabled(is_user_style)

        # Property editor
        self.form.scrollArea_Properties.setEnabled(is_project_style or is_user_style)

    def _populate_editor_from_style(self, item):
        """Fill the property editor fields with values from the selected style."""
        style_id_or_name = item.data(0, QtCore.Qt.UserRole)
        style_data = {}
        if item.parent() is self.project_root:
            style_data = self.project_styles.get(style_id_or_name, {})
        elif item.parent() is self.user_root:
            style_data = self.user_styles.get(style_id_or_name, {})
        elif item.parent() is self.system_root:
            # For system styles, the name is the stable id
            style_info = self.system_styles.get(style_id_or_name, {})
            style_data = style_info.get("properties", {})

        for key, prop_type in PROPERTY_MAP.items():
            control = getattr(self.form, key)
            value = style_data.get(key)
            if value is None:
                continue

            if prop_type == "str":
                control.setText(value)
            elif prop_type == "font":
                control.setCurrentFont(QtGui.QFont(value))
            elif prop_type == "color":
                color = QtGui.QColor(utils.rgba_to_argb(value))
                control.setProperty("color", color)
            elif prop_type == "int":
                control.setValue(value)
            elif prop_type == "float":
                control.setValue(value)
            elif prop_type == "length":
                control.setText(App.Units.Quantity(value, App.Units.Length).UserString)
            elif prop_type == "bool":
                control.setChecked(value)
            elif prop_type == "index":
                control.setCurrentIndex(value)

    def _save_editor_to_style(self, item):
        """Save the current values from the property editor into the style data dict."""
        style_name = item.data(0, QtCore.Qt.UserRole)
        if not style_name:
            return

        style_data = self._get_editor_values()

        if item.parent() is self.project_root:
            self.project_styles[style_name] = style_data
        elif item.parent() is self.user_root:
            self.user_styles[style_name] = style_data

    def _get_editor_values(self):
        """Read all values from the property editor and return as a dictionary."""
        style_data = {}
        for key, prop_type in PROPERTY_MAP.items():
            control = getattr(self.form, key)
            value = None
            if prop_type == "str":
                value = control.text()
            elif prop_type == "font":
                value = control.currentFont().family()
            elif prop_type == "color":
                int_value = control.property("color").rgba()
                value = utils.argb_to_rgba(int_value)
            elif prop_type == "int":
                value = control.value()
            elif prop_type == "float":
                value = control.value()
            elif prop_type == "length":
                try:
                    value = App.Units.Quantity(control.text()).Value
                except App.Units.UnitsError:
                    value = 0.0
            elif prop_type == "bool":
                value = control.isChecked()
            elif prop_type == "index":
                value = control.currentIndex()
            style_data[key] = value
        return style_data

    def _clear_and_disable_editor(self):
        """Populate the editor with global defaults and disable it."""
        # This provides a sane baseline for the on_new() method.
        default_style_tuples = utils.get_default_annotation_style()
        default_data = {key: val[1] for key, val in default_style_tuples.items()}

        for key, prop_type in PROPERTY_MAP.items():
            control = getattr(self.form, key)
            value = default_data.get(key)
            if value is None:
                continue

            if prop_type == "str":
                control.setText(value)
            elif prop_type == "font":
                control.setCurrentFont(QtGui.QFont(value))
            elif prop_type == "color":
                color = QtGui.QColor(utils.rgba_to_argb(value))
                control.setProperty("color", color)
            elif prop_type == "int":
                control.setValue(value)
            elif prop_type == "float":
                control.setValue(value)
            elif prop_type == "length":
                control.setText(App.Units.Quantity(value, App.Units.Length).UserString)
            elif prop_type == "bool":
                control.setChecked(value)
            elif prop_type == "index":
                control.setCurrentIndex(value)

        self.form.scrollArea_Properties.setEnabled(False)

    def on_new(self):
        self._create_new_style(copy_selected=False)

    def on_copy(self):
        """Handle the 'Copy' button click to duplicate the selected style."""
        self._create_new_style(copy_selected=True)

    def _create_new_style(self, copy_selected=False):
        """Helper function to create a new style, either from defaults or by copying."""
        item = self.tree.currentItem()
        if not item:
            return

        target_root = item if not item.parent() else item.parent()
        if target_root not in [self.project_root, self.user_root]:
            # If a system style is selected, create the new style in the User library
            target_root = self.user_root

        base_name = ""
        if copy_selected and item.parent():
            base_name = item.data(0, QtCore.Qt.UserRole)

        new_name, ok = QtWidgets.QInputDialog.getText(
            self.form, "New Style Name", "Enter a name for the new style:"
        )
        if not ok or not new_name.strip():
            return

        new_name = new_name.strip()

        # Check for name conflicts across all existing styles
        if (
            new_name in self.project_styles
            or new_name in self.user_styles
            or any(new_name == translate("Draft", s["name"]) for s in self.system_styles.values())
        ):
            QtWidgets.QMessageBox.warning(
                self.form, "Style Exists", "A style with this name already exists."
            )
            return

        if copy_selected and base_name:
            new_style_data = self._get_editor_values()
        else:
            # Create a new style from the hardcoded sane defaults
            default_style_tuples = utils.get_default_annotation_style()
            new_style_data = {key: val[1] for key, val in default_style_tuples.items()}

        if target_root is self.project_root:
            self.project_styles[new_name] = new_style_data
        else:  # target_root is self.user_root
            self.user_styles[new_name] = new_style_data

        # Add the new style to the tree, and select it for immediate editing
        new_item = QtWidgets.QTreeWidgetItem(target_root, [new_name])
        new_item.setData(0, QtCore.Qt.UserRole, new_name)
        self.tree.setCurrentItem(new_item)

    def on_delete(self):
        """Handle the 'Delete' button click to remove the selected style."""
        item = self.tree.currentItem()
        if not item or not item.parent():
            return

        self.is_deleting = True
        try:
            style_name = item.data(0, QtCore.Qt.UserRole)
            display_name = item.text(0)

            reply = QtWidgets.QMessageBox.question(
                self.form,
                "Confirm Deletion",
                f"Are you sure you want to delete the style '{display_name}'?",
                QtWidgets.QMessageBox.Yes | QtWidgets.QMessageBox.No,
                QtWidgets.QMessageBox.No,
            )

            if reply == QtWidgets.QMessageBox.No:
                return

            # Remove from the correct dictionary
            if item.parent() is self.project_root:
                if style_name in self.project_styles:
                    del self.project_styles[style_name]
            elif item.parent() is self.user_root:
                if style_name in self.user_styles:
                    del self.user_styles[style_name]
                    # If the deleted style was the default, clear the setting
                    if style_name == self.default_style_name:
                        annotation_styles.set_default_style_name("")
                        self.default_style_name = ""

            # Remove from the tree widget, which will trigger on_selection_changed
            item.parent().removeChild(item)
        finally:
            self.is_deleting = False

    def on_context_menu(self, point):
        """Show the right-click context menu for the tree widget."""
        item = self.tree.itemAt(point)
        if not item or not item.parent():
            return

        menu = QtWidgets.QMenu()

        if item.parent() is self.project_root:
            export_action = menu.addAction(translate("Draft", "Copy to User Library"))
            export_action.triggered.connect(self.on_export)
        elif item.parent() in [self.user_root, self.system_root]:
            import_action = menu.addAction(translate("Draft", "Copy to Document"))
            import_action.triggered.connect(self.on_import)

        menu.exec_(self.tree.viewport().mapToGlobal(point))

    def on_rename(self):
        """Handle the 'Rename' button click to rename the selected style."""
        item = self.tree.currentItem()
        if not item or not item.parent():
            return

        old_name = item.data(0, QtCore.Qt.UserRole)

        new_name, ok = QtWidgets.QInputDialog.getText(
            self.form, "Rename Style", "Enter a new name for the style:", text=old_name
        )
        if not ok or not new_name.strip():
            return

        new_name = new_name.strip()

        if new_name == old_name:
            return

        # Check for name conflicts across all existing styles
        if (
            new_name in self.project_styles
            or new_name in self.user_styles
            or any(new_name == translate("Draft", s["name"]) for s in self.system_styles.values())
        ):
            QtWidgets.QMessageBox.warning(
                self.form, "Style Exists", "A style with this name already exists."
            )
            return

        # Update the correct dictionary
        if item.parent() is self.project_root:
            self.project_styles[new_name] = self.project_styles.pop(old_name)
        elif item.parent() is self.user_root:
            self.user_styles[new_name] = self.user_styles.pop(old_name)
            # If the renamed style was the default, update the setting
            if old_name == self.default_style_name:
                annotation_styles.set_default_style_name(new_name)
                self.default_style_name = new_name

        # Repopulate the tree to correctly update the default style indicator
        self._populate_styles()

        # Find and re-select the newly renamed item
        for i in range(self.tree.topLevelItemCount()):
            root = self.tree.topLevelItem(i)
            for j in range(root.childCount()):
                child = root.child(j)
                if child.data(0, QtCore.Qt.UserRole) == new_name:
                    self.tree.setCurrentItem(child)
                    return

    def on_set_default(self):
        """Handle the 'Set Default' button click."""
        item = self.tree.currentItem()
        if not item or item.parent() is not self.user_root:
            return

        new_default_name = item.data(0, QtCore.Qt.UserRole)

        # Update the setting in the backend
        annotation_styles.set_default_style_name(new_default_name)
        self.default_style_name = new_default_name

        # Repopulate the entire tree to correctly update bolding
        self._populate_styles()

        # Find and re-select the new default item
        for i in range(self.user_root.childCount()):
            child = self.user_root.child(i)
            if child.data(0, QtCore.Qt.UserRole) == new_default_name:
                self.tree.setCurrentItem(child)
                break

    def on_import(self):
        """Handle the 'Copy to Document' action from the context menu."""
        item = self.tree.currentItem()
        if not item or item.parent() not in [self.user_root, self.system_root]:
            return

        style_name_or_id = item.data(0, QtCore.Qt.UserRole)
        display_name = item.text(0)
        style_to_copy = None

        # Get a deep copy of the source style data
        if item.parent() is self.user_root:
            style_to_copy = self.user_styles.get(style_name_or_id)
            display_name = style_name_or_id
        else:  # System style
            style_info = self.system_styles.get(style_name_or_id, {})
            style_to_copy = style_info.get("properties", {})
            display_name = translate("Draft", style_info.get("name", style_name_or_id))

        if not style_to_copy:
            return

        # Check for conflicts
        if display_name in self.project_styles:
            reply = QtWidgets.QMessageBox.question(
                self.form,
                "Overwrite Style",
                f"A style named '{display_name}' already exists in this document. Overwrite it?",
                QtWidgets.QMessageBox.Yes | QtWidgets.QMessageBox.No,
                QtWidgets.QMessageBox.No,
            )
            if reply == QtWidgets.QMessageBox.No:
                return

        self.project_styles[display_name] = copy.deepcopy(style_to_copy)

        # Update the tree widget
        # Check if the item already exists to avoid duplicates
        found_item = None
        for i in range(self.project_root.childCount()):
            child = self.project_root.child(i)
            if child.data(0, QtCore.Qt.UserRole) == display_name:
                found_item = child
                break

        if not found_item:
            found_item = QtWidgets.QTreeWidgetItem(self.project_root, [display_name])
            found_item.setData(0, QtCore.Qt.UserRole, display_name)

        self.project_root.sortChildren(0, QtCore.Qt.AscendingOrder)
        self.tree.setCurrentItem(found_item)

    def on_export(self):
        """Handle the 'Copy to User Library' action from the context menu."""
        item = self.tree.currentItem()
        if not item or item.parent() is not self.project_root:
            return

        style_name = item.data(0, QtCore.Qt.UserRole)

        # Check for conflicts
        if style_name in self.user_styles:
            reply = QtWidgets.QMessageBox.question(
                self.form,
                "Overwrite Style",
                f"A style named '{style_name}' already exists in your user library. Overwrite it?",
                QtWidgets.QMessageBox.Yes | QtWidgets.QMessageBox.No,
                QtWidgets.QMessageBox.No,
            )
            if reply == QtWidgets.QMessageBox.No:
                return

        # Get a deep copy of the project style
        style_data = copy.deepcopy(self.project_styles[style_name])
        self.user_styles[style_name] = style_data

        # Update the tree widget
        found_item = None
        for i in range(self.user_root.childCount()):
            child = self.user_root.child(i)
            if child.data(0, QtCore.Qt.UserRole) == style_name:
                found_item = child
                break

        if not found_item:
            found_item = QtWidgets.QTreeWidgetItem(self.user_root, [style_name])
            found_item.setData(0, QtCore.Qt.UserRole, style_name)

        self.user_root.sortChildren(0, QtCore.Qt.AscendingOrder)
        self.tree.setCurrentItem(found_item)

    def execute(self):
        """Show the dialog and wait for user input."""
        if self.form.exec_():
            # OK was clicked, save the state of the currently active editor
            # before saving the dictionaries to the document.
            current_item = self.tree.currentItem()
            if current_item and current_item.parent():
                self._save_editor_to_style(current_item)

            # OK was clicked, save everything
            annotation_styles.save_project_styles(self.doc, self.project_styles)
            annotation_styles.save_user_styles(self.user_styles)
            return True
        return False


# Command to launch the dialog
class Draft_AnnotationStyleEditor:
    """The command to launch the Annotation Style Manager dialog."""

    def GetResources(self):
        # TODO: Define icon, menu text, and tooltip
        return {
            "Pixmap": "Draft_Annotation_Style",
            "MenuText": "Annotation Style Manager...",
            "ToolTip": "Manage annotation styles for this document and your user library.",
        }

    def Activated(self):
        if not App.ActiveDocument:
            App.Console.PrintWarning(
                "An active document is required to manage annotation styles.\n"
            )
            return

        dialog = AnnotationStyleManagerDialog(App.ActiveDocument)
        if dialog.execute():
            # If OK was clicked, styles may have changed. Update the toolbar.
            from draftguitools import gui_annotationstyletoolbar

            if gui_annotationstyletoolbar.SELECTOR_INSTANCE:
                gui_annotationstyletoolbar.SELECTOR_INSTANCE.update_style_list()

    def IsActive(self):
        return Gui.ActiveDocument is not None


Gui.addCommand("Draft_AnnotationStyleEditor", Draft_AnnotationStyleEditor())
