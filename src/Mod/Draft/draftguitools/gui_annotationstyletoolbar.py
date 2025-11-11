# SPDX-License-Identifier: LGPL-2.1-or-later

"""GUI commands for the new Annotation Style Toolbar."""

import copy
import FreeCAD as App
import FreeCADGui as Gui
from PySide import QtCore, QtGui, QtWidgets

from draftutils import annotation_styles
from draftutils import utils
from draftutils.translate import translate
from draftguitools.gui_annotationstylemanager import AnnotationStyleManagerDialog

# A global reference that will hold the single instance of our selector command
SELECTOR_INSTANCE = None


def _ensure_style_in_document(style_data):
    """
    Parses a style's data from the dropdown. If it's a User or System style,
    it ensures a copy exists in the current document.
    Returns the clean style name upon success, or None on failure.
    """
    if not App.ActiveDocument or not style_data:
        return None

    clean_name = style_data.get("name")
    source = style_data.get("source")

    if not clean_name or not source:
        return None

    doc_styles = annotation_styles.get_project_styles(App.ActiveDocument)
    if source in ["user", "system"]:
        # For system styles, the name of the new document style should be the translated one.
        display_name = clean_name
        if source == "system":
            all_system_styles_info = annotation_styles.get_system_styles()
            style_info = all_system_styles_info.get(clean_name, {})
            display_name = translate("Draft", style_info.get("name", clean_name))

        if display_name not in doc_styles:
            App.Console.PrintLog(
                f"Implicitly copying '{display_name}' from {source} library to the document.\n"
            )
            # Implicit copy is needed
            if source == "user":
                all_user_styles = annotation_styles.get_user_styles()
                properties_to_copy = all_user_styles.get(clean_name)
            else:  # source == "system"
                all_system_styles = annotation_styles.get_system_styles()
                style_info = all_system_styles.get(clean_name, {})  # clean_name is the stable id
                properties_to_copy = style_info.get("properties")

            if properties_to_copy:
                doc_styles[display_name] = copy.deepcopy(properties_to_copy)
                annotation_styles.save_project_styles(App.ActiveDocument, doc_styles)
                # Let the main selector instance know it needs to refresh
                if SELECTOR_INSTANCE:
                    SELECTOR_INSTANCE.update_style_list()
                    # After refresh, restore the selection to the newly copied style
                    SELECTOR_INSTANCE.set_active_style_by_name(display_name)
            return display_name
        return display_name

    return clean_name


def _apply_style_to_objects(style_name, objects):
    """
    Helper function to apply a given style to a list of objects,
    correctly handling the enumeration update and visual property propagation.
    """
    if not style_name or not objects:
        return

    # Get the complete dictionary of styles now present in the document
    all_doc_styles = annotation_styles.get_project_styles(App.ActiveDocument)
    style_properties = all_doc_styles.get(style_name)

    if not style_properties:
        return

    style_names_list = sorted(all_doc_styles.keys())

    for obj in objects:
        if "AnnotationStyle" in obj.ViewObject.PropertiesList:
            try:
                # This is the correct, evidence-based pattern.
                vobj = obj.ViewObject
                # 1. Assign the list to update the enumeration.
                vobj.AnnotationStyle = style_names_list
                # 2. Assign the string value to set the logical style.
                vobj.AnnotationStyle = style_name

                # 3. Manually propagate all visual properties to force a refresh.
                for attr, value in style_properties.items():
                    if hasattr(vobj, attr):
                        try:
                            # PropertyColor expects an integer (packed RGBA)
                            setattr(vobj, attr, value)
                        except Exception as e:
                            App.Console.PrintWarning(
                                f"Could not set property '{attr}' on {obj.Name}: {e}\n"
                            )

            except Exception as e:
                App.Console.PrintError(f"Failed to apply style to {obj.Name}: {e}\n")


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
        style_data = SELECTOR_INSTANCE.get_current_user_data()
        style_name = _ensure_style_in_document(style_data)
        _apply_style_to_objects(style_name, Gui.Selection.getSelection())

    def IsActive(self):
        # Per "Option C", this button is always enabled when a document is active.
        # The Activated method will handle the case of an empty selection.
        return Gui.ActiveDocument is not None


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
        style_data = SELECTOR_INSTANCE.get_current_user_data()
        style_name = _ensure_style_in_document(style_data)
        if not App.ActiveDocument:
            return
        _apply_style_to_objects(style_name, App.ActiveDocument.Objects)

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
            if (
                user_data
                and user_data.get("source") == "document"
                and user_data.get("name") == style_name
            ):
                self.style_combo.setCurrentIndex(i)
                return

    def update_style_list(self):
        """Reload the list of styles from all sources into the dropdown."""
        self.style_combo.blockSignals(True)
        try:
            current_data = self.style_combo.currentData()
            self.style_combo.clear()

            if not App.ActiveDocument:
                self.style_combo.setEnabled(False)
                return

            doc_styles = annotation_styles.get_project_styles(App.ActiveDocument)
            user_styles = annotation_styles.get_user_styles()
            system_styles = annotation_styles.get_system_styles()

            # 1. Add Document Styles
            if doc_styles:
                for name in sorted(doc_styles.keys()):
                    self.style_combo.addItem(name, {"name": name, "source": "document"})

            # 2. Add User Library Styles
            if user_styles:
                if self.style_combo.count() > 0:
                    self.style_combo.insertSeparator(self.style_combo.count())
                for name in sorted(user_styles.keys()):
                    display_text = f"{name} {translate('Draft', '[User]')}"
                    self.style_combo.addItem(display_text, {"name": name, "source": "user"})

            # 3. Add System Styles
            if system_styles:
                if self.style_combo.count() > 0:
                    self.style_combo.insertSeparator(self.style_combo.count())
                for style_id, style_data in sorted(system_styles.items()):
                    if style_id.startswith("_"):
                        continue  # Hide internal-use styles
                    translatable_name = translate("Draft", style_data["name"])
                    display_text = f"{translatable_name} {translate('Draft', '[System]')}"
                    self.style_combo.addItem(display_text, {"name": style_id, "source": "system"})

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
