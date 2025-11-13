# SPDX-License-Identifier: LGPL-2.1-or-later

"""GUI logic for Draft preference pages."""

import FreeCAD as App
import FreeCADGui as Gui
from PySide import QtCore, QtGui, QtWidgets

from draftutils import annotation_styles
from draftutils.translate import translate


def create_preference_page_class(parameter_path):
    """
    A class factory that creates a new preference page class type,
    configured with a specific parameter path. This allows the same UI
    and logic to be reused by different workbenches (e.g., Draft and BIM)
    with their own independent settings.
    """

    class _PreferencePage:
        """The dynamically created preference page class for Texts and Dimensions."""

        def __init__(self):
            # The parameter_path is "baked in" from the factory's scope
            self.param_path = parameter_path
            self.form = Gui.PySideUic.loadUi(":/ui/preferences-drafttexts.ui")

            # Remove the extra indentation of the page being wrapped in a layout by adjusting the
            # layout's margins
            layout = self.form.layout()
            if layout:
                layout.setContentsMargins(0, 0, 0, 0)

            self.combo_box = self.form.findChild(QtWidgets.QComboBox, "pref_DefaultAnnotationStyle")
            self.manage_button = self.form.findChild(
                QtWidgets.QPushButton, "pushButton_ManageStyles"
            )

            if self.combo_box:
                # The save logic is connected directly here. When the user changes
                # the selection, the parameter is saved immediately.
                self.combo_box.currentIndexChanged.connect(self._on_style_changed)

            if self.manage_button:
                self.manage_button.clicked.connect(self.on_manage_styles)

        def on_manage_styles(self):
            """Launch the style manager and refresh the dropdown when it closes."""
            Gui.runCommand("Draft_AnnotationStyleEditor", 0)
            # After the manager closes, reload the settings to refresh the combobox
            self.loadSettings()

        def loadSettings(self):
            """Called by the framework to load the page's settings."""
            if not self.combo_box:
                return

            # Block signals during programmatic changes to avoid accidental saves
            self.combo_box.blockSignals(True)
            try:
                self.combo_box.clear()
                user_styles = annotation_styles.get_user_styles()
                system_styles = annotation_styles.get_system_styles()

                for name in sorted(user_styles.keys()):
                    self.combo_box.addItem(name, name)

                if user_styles and system_styles:
                    self.combo_box.insertSeparator(self.combo_box.count())

                for style_id, style_data in sorted(system_styles.items()):
                    if style_id.startswith("_"):
                        continue
                    translatable_name = translate("Draft", style_data["name"])
                    display_text = f"{translatable_name} [{translate('Draft', 'System')}]"
                    self.combo_box.addItem(display_text, style_id)

                # Load the current setting and set the index
                current_style_id = annotation_styles.get_default_style_name(path=self.param_path)

                # Default to the internal fallback if no preference is set
                if not current_style_id:
                    current_style_id = "_freecad_default_style"

                found_index = -1
                for i in range(self.combo_box.count()):
                    if self.combo_box.itemData(i) == current_style_id:
                        found_index = i
                        break

                if found_index != -1:
                    self.combo_box.setCurrentIndex(found_index)

            finally:
                # Always re-enable signals
                self.combo_box.blockSignals(False)

        def saveSettings(self):
            """
            Called by the framework when the user clicks OK.
            The logic is handled by the currentIndexChanged signal, but it
            can be triggered here one last time to be safe.
            """
            self._on_style_changed(self.combo_box.currentIndex())
            return True

        def _on_style_changed(self, index):
            """Internal slot to save the parameter when the user makes a choice."""
            if not self.combo_box:
                return
            style_id = self.combo_box.itemData(index)
            if style_id:
                annotation_styles.set_default_style_name(style_id, path=self.param_path)

    return _PreferencePage
