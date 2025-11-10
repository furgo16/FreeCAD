# SPDX-License-Identifier: LGPL-2-or-later

"""Backend utilities for managing annotation styles."""

import os
import json
import FreeCAD as App

# Define the standard paths for style files. These will be mocked during testing.
USER_STYLES_PATH = os.path.join(App.getUserAppDataDir(), "Draft", "AnnotationStyles.json")
LEGACY_PATH = os.path.join(App.getUserAppDataDir(), "Draft", "StylePresets.json")
# This will eventually point to a file in the Mod/Draft/Resources directory
SYSTEM_STYLES_PATH = os.path.join(
    App.getResourceDir(), "Mod", "Draft", "Resources", "presets", "SystemAnnotationStyles.json"
)
# Path for the new annotation preferences group in FreeCAD's parameter editor
ANNOTATION_PREFERENCES_PATH = "User parameter:BaseApp/Preferences/Mod/Draft/Annotation"

# A set of all known annotation-related keys from legacy style files.
# This will be used to filter out shape-only properties during migration.
ANNOTATION_KEYS = {
    # Text properties
    "TextColor",
    "TextFont",
    "FontName",
    "TextSize",
    "FontSize",
    "LineSpacing",
    # General annotation properties
    "ScaleMultiplier",
    # Line and Arrow properties (includes legacy and ambiguous names)
    "AnnoLineColor",
    "LineColor",
    "AnnoLineWidth",
    "LineWidth",
    "ShowLine",
    "ArrowStyleStart",
    "ArrowTypeStart",
    "ArrowSizeStart",
    "ArrowStyleEnd",
    "ArrowTypeEnd",
    "ArrowSizeEnd",
    "ArrowType",
    # Dimension properties
    "ShowUnit",
    "UnitOverride",
    "Decimals",
    "DimOvershoot",
    "ExtLines",
    "ExtOvershoot",
    "TextSpacing",
}


def _migrate_legacy_styles():
    """Check for a legacy StylePresets.json, filter it for annotation styles,
    save it to the new location, and rename the old file.

    Returns the migrated styles dictionary, or None if no migration occurred.
    """
    if not os.path.exists(LEGACY_PATH):
        return None

    try:
        with open(LEGACY_PATH, "r") as f:
            legacy_styles = json.load(f)
    except (json.JSONDecodeError, IOError):
        # If the legacy file is unreadable, we can't migrate it.
        return None

    migrated_styles = {}
    for style_name, properties in legacy_styles.items():
        migrated_properties = {
            key: value for key, value in properties.items() if key in ANNOTATION_KEYS
        }

        if migrated_properties:  # Only add styles that had annotation properties
            migrated_styles[style_name] = migrated_properties

    # Save the new filtered styles and rename the old file
    save_user_styles(migrated_styles)
    try:
        os.rename(LEGACY_PATH, LEGACY_PATH + ".migrated")
    except OSError:
        # If renaming fails (e.g., permissions), we can still proceed.
        # The existence of the new file will prevent this from running again.
        pass

    return migrated_styles


def get_user_styles():
    """Read and return the contents of the user's global AnnotationStyles.json.

    If the file does not exist, it checks for a legacy StylePresets.json and
    migrates it. Otherwise, returns an empty dictionary.
    """
    # If the new styles file already exists, use it and do nothing else.
    if os.path.exists(USER_STYLES_PATH):
        with open(USER_STYLES_PATH, "r") as f:
            try:
                styles = json.load(f)
            except json.JSONDecodeError:
                App.Console.PrintWarning(
                    f"Warning: Failed to decode JSON in user annotation styles file at {USER_STYLES_PATH}.\n"
                )
                styles = {}
        return styles

    # If no new file, attempt to migrate a legacy one.
    migrated_styles = _migrate_legacy_styles()
    if migrated_styles is not None:
        return migrated_styles

    # If no new file and no migration, return empty.
    return {}


def save_user_styles(styles_dict):
    """Write the given dictionary to the user's AnnotationStyles.json."""
    # Ensure the target directory exists
    folder = os.path.dirname(USER_STYLES_PATH)
    if not os.path.exists(folder):
        os.makedirs(folder)

    with open(USER_STYLES_PATH, "w") as f:
        json.dump(styles_dict, f, indent=4)


def get_system_styles():
    """Read and return the read-only system styles."""
    if not os.path.exists(SYSTEM_STYLES_PATH):
        App.Console.PrintWarning(
            f"Warning: System annotation styles file not found at {SYSTEM_STYLES_PATH}."
        )
        # This case should ideally not happen in a proper installation
        return {}

    with open(SYSTEM_STYLES_PATH, "r") as f:
        try:
            styles = json.load(f)
        except json.JSONDecodeError:
            styles = {}
            App.Console.PrintWarning(
                f"Warning: Failed to decode JSON in system annotation styles file at {SYSTEM_STYLES_PATH}."
            )
    return styles


def get_project_styles(doc):
    """Read annotation styles from the given document's .Meta attribute."""
    styles = {}
    meta = doc.Meta
    for key, value in meta.items():
        if key.startswith("Draft_Style_"):
            style_name = key[12:]
            try:
                styles[style_name] = json.loads(value)
            except json.JSONDecodeError:
                # Ignore corrupted style entries in the document
                App.Console.PrintWarning(
                    f"Warning: Failed to decode JSON in document annotation style entry '{style_name}' in document '{doc.Name}'."
                )
                pass
    return styles


def save_project_styles(doc, styles_dict):
    """Save annotation styles to the given document's .Meta attribute."""
    meta = doc.Meta

    # Remove styles from the document that are not in the new dictionary.
    keys_to_delete = []
    for key in meta.keys():
        if key.startswith("Draft_Style_"):
            style_name = key[12:]
            if style_name not in styles_dict:
                keys_to_delete.append(key)

    for key in keys_to_delete:
        del meta[key]

    # Add or update the styles from the new dictionary.
    for style_name, style_properties in styles_dict.items():
        meta_key = "Draft_Style_" + style_name
        meta[meta_key] = json.dumps(style_properties)

    # Reassign the Meta object to ensure changes are saved
    doc.Meta = meta


def get_default_style_name():
    """Read the default annotation style name from the FreeCAD preferences."""
    param = App.ParamGet(ANNOTATION_PREFERENCES_PATH)
    return param.GetString("DefaultStyle", "")


def set_default_style_name(name):
    """Write the default annotation style name to the FreeCAD preferences."""
    param = App.ParamGet(ANNOTATION_PREFERENCES_PATH)
    param.SetString("DefaultStyle", name)
