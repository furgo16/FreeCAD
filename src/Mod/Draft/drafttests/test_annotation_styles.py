# SPDX-License-Identifier: LGPL-2.1-or-later

"""Unit tests for the Draft annotation styles utility module."""

import os
import json
import shutil
import tempfile
from unittest import mock

from drafttests import test_base
from draftutils import annotation_styles


class TestAnnotationStyles(test_base.DraftTestCaseDoc):
    """Test the annotation_styles utility module."""

    def setUp(self):
        """Set up a temporary directory to act as the user's config folder."""
        super().setUp()
        self.temp_dir = tempfile.mkdtemp()

        # Define paths to mock files within the temporary directory
        self.user_styles_path = os.path.join(self.temp_dir, "AnnotationStyles.json")
        self.legacy_styles_path = os.path.join(self.temp_dir, "StylePresets.json")
        self.system_styles_path = os.path.join(self.temp_dir, "SystemAnnotationStyles.json")

        # Mock the constants in the annotation_styles module to point to our temp files.
        # This isolates the tests from the actual user's file system.
        self.user_patcher = mock.patch(
            "draftutils.annotation_styles.USER_STYLES_PATH", self.user_styles_path
        )
        self.legacy_patcher = mock.patch(
            "draftutils.annotation_styles.LEGACY_PATH", self.legacy_styles_path
        )
        self.system_patcher = mock.patch(
            "draftutils.annotation_styles.SYSTEM_STYLES_PATH", self.system_styles_path
        )
        self.user_patcher.start()
        self.legacy_patcher.start()
        self.system_patcher.start()

    def tearDown(self):
        """Clean up the temporary directory and stop the patchers."""
        super().tearDown()
        shutil.rmtree(self.temp_dir)
        self.user_patcher.stop()
        self.legacy_patcher.stop()
        self.system_patcher.stop()

    def test_get_user_styles_file_not_found(self):
        """Test that getting styles returns an empty dict if the file doesn't exist."""
        # Arrange
        # The setUp method ensures no file exists by creating an empty temp dir.

        # Act
        styles = annotation_styles.get_user_styles()

        # Assert
        # We expect an empty dictionary, not a FileNotFoundError.
        self.assertEqual(styles, {})

    def test_save_and_get_user_styles(self):
        """Test saving styles to a file and reading them back."""
        # Arrange
        expected_styles = {
            "Test Style": {
                "TextSize": 150.0,
                "TextColor": [1.0, 0.0, 0.0, 0.0],
                "FontName": "Arial",
            }
        }

        # Act
        annotation_styles.save_user_styles(expected_styles)
        read_styles = annotation_styles.get_user_styles()

        # Assert
        self.assertTrue(os.path.exists(self.user_styles_path), "The style file was not created.")
        self.assertEqual(read_styles, expected_styles)

    def test_get_system_styles(self):
        """Test reading the built-in, read-only system styles."""
        # Arrange
        system_styles_list = [
            {
                "id": "bim_meters",
                "name": "BIM (Meters)",
                "properties": {"TextSize": 250.0, "ArrowSize": 200.0},
            },
            {
                "id": "draft_mm",
                "name": "Draft (mm)",
                "properties": {"TextSize": 3.5, "ArrowSize": 3.5},
            },
        ]

        # The expected output of the function is a dictionary keyed by the id
        expected_styles_dict = {
            "bim_meters": {
                "name": "BIM (Meters)",
                "properties": {"TextSize": 250.0, "ArrowSize": 200.0},
            },
            "draft_mm": {"name": "Draft (mm)", "properties": {"TextSize": 3.5, "ArrowSize": 3.5}},
        }

        with open(self.system_styles_path, "w") as f:
            json.dump(system_styles_list, f)

        # Act
        read_styles = annotation_styles.get_system_styles()

        # Assert
        self.assertEqual(read_styles, expected_styles_dict)

    def test_get_project_styles_from_empty_doc(self):
        """Test that a document with no styles returns an empty dictionary."""
        # Arrange: self.doc is a new, empty document from the base class.

        # Act
        styles = annotation_styles.get_project_styles(self.doc)

        # Assert
        self.assertEqual(styles, {})

    def test_save_and_get_project_styles(self):
        """Test saving styles to a document's Meta object and reading them back."""
        # Arrange
        expected_styles = {"Project Style A": {"TextSize": 250.0, "ArrowSize": 200.0}}

        # Act
        annotation_styles.save_project_styles(self.doc, expected_styles)
        read_styles = annotation_styles.get_project_styles(self.doc)

        # Assert
        # 1. The function returns the correct dictionary
        self.assertEqual(read_styles, expected_styles)
        # 2. The data is physically present in the document's Meta object
        #    in the expected format (prefixed key, json-serialized value).
        expected_key = "Draft_Style_Project Style A"
        self.assertIn(expected_key, self.doc.Meta)
        self.assertEqual(
            json.loads(self.doc.Meta[expected_key]), expected_styles["Project Style A"]
        )

    def test_migration_of_legacy_styles_file(self):
        """Test that a legacy preset file is migrated correctly on first run."""
        # Arrange: Create a legacy StylePresets.json file with mixed properties.
        legacy_data = {
            "My Old Style": {
                "TextSize": 12.0,  # Annotation property - should be kept
                "ArrowType": "Arrow",  # Annotation property - should be kept
                "ShapeColor": [1, 0, 0, 0],  # Shape property - should be removed
                "Transparency": 50,  # Shape property - should be removed
                "LineWidth": 2,  # Shape/Annotation property - should be kept for annotations
            }
        }
        expected_migrated_data = {
            "My Old Style": {
                "TextSize": 12.0,
                "ArrowType": "Arrow",
                "LineWidth": 2,
            }
        }
        with open(self.legacy_styles_path, "w") as f:
            json.dump(legacy_data, f)

        # The new user styles file does not exist yet, simulating a first run.
        self.assertFalse(os.path.exists(self.user_styles_path))

        # Act: The migration should be triggered by the first call to get_user_styles.
        migrated_styles = annotation_styles.get_user_styles()

        # Assert
        # 1. The function returned the correctly filtered data.
        self.assertEqual(migrated_styles, expected_migrated_data)

        # 2. The new user styles file was created with the filtered data.
        self.assertTrue(os.path.exists(self.user_styles_path))
        with open(self.user_styles_path, "r") as f:
            new_file_content = json.load(f)
        self.assertEqual(new_file_content, expected_migrated_data)

        # 3. The old legacy file was renamed.
        self.assertFalse(os.path.exists(self.legacy_styles_path))
        self.assertTrue(os.path.exists(self.legacy_styles_path + ".migrated"))

    def test_migration_does_not_run_if_new_file_exists(self):
        """Test that migration is skipped if AnnotationStyles.json already exists."""
        # Arrange: Create both a new user styles file and a legacy file.
        user_data = {"Modern Style": {"TextSize": 10.0}}
        legacy_data = {"Legacy Style": {"TextSize": 20.0}}

        with open(self.user_styles_path, "w") as f:
            json.dump(user_data, f)
        with open(self.legacy_styles_path, "w") as f:
            json.dump(legacy_data, f)

        # Act: Call the function. It should read the modern file and ignore the legacy one.
        styles = annotation_styles.get_user_styles()

        # Assert
        # 1. The returned data is from the modern file.
        self.assertEqual(styles, user_data)

        # 2. The legacy file was not renamed.
        self.assertTrue(os.path.exists(self.legacy_styles_path))
        self.assertFalse(os.path.exists(self.legacy_styles_path + ".migrated"))

    @mock.patch("draftutils.annotation_styles.App.ParamGet")
    def test_get_default_style_name(self, mock_param_get):
        """Test reading the default style name from FreeCAD's parameters."""
        # Arrange
        # Configure the mock to simulate a stored preference.
        mock_pg = mock_param_get.return_value
        mock_pg.GetString.return_value = "My Default Style"

        # Act
        default_name = annotation_styles.get_default_style_name()

        # Assert
        # 1. Check that the function returns the expected value.
        self.assertEqual(default_name, "My Default Style")

        # 2. Verify that the correct parameter path was requested.
        param_path = "User parameter:BaseApp/Preferences/Mod/Draft/Annotation"
        mock_param_get.assert_called_with(param_path)
        mock_pg.GetString.assert_called_with("DefaultStyle", "")

    @mock.patch("draftutils.annotation_styles.App.ParamGet")
    def test_get_default_style_name_when_not_set(self, mock_param_get):
        """Test that getting the default style returns an empty string if not set."""
        # Arrange
        # Configure the mock to simulate that the preference is not set.
        mock_pg = mock_param_get.return_value
        mock_pg.GetString.return_value = ""  # Default return value

        # Act
        default_name = annotation_styles.get_default_style_name()

        # Assert
        self.assertEqual(default_name, "")

    @mock.patch("draftutils.annotation_styles.App.ParamGet")
    def test_set_default_style_name(self, mock_param_get):
        """Test writing the default style name to FreeCAD's parameters."""
        # Arrange
        mock_pg = mock_param_get.return_value
        style_name_to_set = "My New Default"

        # Act
        annotation_styles.set_default_style_name(style_name_to_set)

        # Assert
        # Verify that the parameter group was opened and the string was set.
        param_path = "User parameter:BaseApp/Preferences/Mod/Draft/Annotation"
        mock_param_get.assert_called_with(param_path)
        mock_pg.SetString.assert_called_with("DefaultStyle", style_name_to_set)
