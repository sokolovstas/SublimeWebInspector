import unittest
import os

import projectsystem
from projectsystem import DocumentMapping

# Assets path is relative to the test folder. All the tests should be run from the root folder
assets_path = os.path.abspath("tests" + os.path.sep + "assets").lower() + os.path.sep

class PositionTests(unittest.TestCase):
    def test_invalid_input_line(self):
        caught_exception = False
        try:
            position = DocumentMapping.Position("app.js", -1, 0)
        except ValueError:
            caught_exception = True

        self.assertTrue(caught_exception)

    def test_invalid_input_column(self):
        caught_exception = False
        try:
            position = DocumentMapping.Position("app.js", 0, -1)
        except ValueError:
            caught_exception = True

        self.assertTrue(caught_exception)

    def test_invalid_input(self):
        caught_exception = False
        try:
            position = DocumentMapping.Position("app.js", -4, -3)
        except ValueError:
            caught_exception = True

        self.assertTrue(caught_exception)

    def test_zero_based_position(self):
        position = DocumentMapping.Position("app.js", 1, 1)
        self.assertEqual(position.file_name(), "app.js")
        self.assertEqual(position.zero_based_line(), 1)
        self.assertEqual(position.zero_based_column(), 1)

    def test_one_based_position(self):
        position = DocumentMapping.Position("app.js", 1, 1)
        self.assertEqual(position.file_name(), "app.js")
        self.assertEqual(position.one_based_line(), 2)
        self.assertEqual(position.one_based_column(), 2)

class MappingInfoTests(unittest.TestCase):
    def test_invalid_generated_file_does_not_throw(self):
        mapping = DocumentMapping.MappingInfo("foobar.js")
        self.assertFalse(mapping.is_valid())

    def test_invalid_map_file_does_not_throw(self):
        mapping = DocumentMapping.MappingInfo(assets_path + "garbage.js")
        self.assertFalse(mapping.is_valid())

    def test_valid_generated_file(self):
        mapping = DocumentMapping.MappingInfo(assets_path + "app.js")
        self.assertTrue(mapping.is_valid())

    def test_authored_sources(self):
        mapping = DocumentMapping.MappingInfo(assets_path + "app.js")
        self.assertEqual(len(mapping.get_authored_files()), 1)
        self.assertEqual(mapping.get_authored_files(), [assets_path + "app.ts"])

    def test_generated_file(self):
        mapping = DocumentMapping.MappingInfo(assets_path + "app.js")
        self.assertEqual(mapping.get_generated_file(), assets_path + "app.js")

    def test_authored_position(self):
        mapping = DocumentMapping.MappingInfo(assets_path + "app.js")
        position = mapping.get_authored_position(10, 12)

        self.assertEqual(position.file_name(), assets_path + "app.ts")
        self.assertEqual(position.zero_based_line(), 16)
        self.assertEqual(position.zero_based_column(), 12)

    def test_generated_position_casing(self):
        ''' Should match case insensitively (note map already has name aPp.Ts) '''
        mapping = DocumentMapping.MappingInfo(assets_path + "app.js")
        position = mapping.get_generated_position(assets_path.upper() + "APP.ts", 16, 12)
        self.assertIsNotNone(position)

    def test_generated_position(self):
        mapping = DocumentMapping.MappingInfo(assets_path + "app.js")
        position = mapping.get_generated_position(assets_path + "app.ts", 16, 12)

        self.assertEqual(position.file_name(), assets_path + "app.js")
        self.assertEqual(position.zero_based_line(), 10)
        self.assertEqual(position.zero_based_column(), 12)

    def test_invalid_authored_position(self):
        mapping = DocumentMapping.MappingInfo(assets_path + "app.js")

        # Should map to last line and column in the authored file
        position = mapping.get_authored_position(300, 3000)

        self.assertEqual(position.file_name(), assets_path + "app.ts")
        self.assertEqual(position.zero_based_line(), 36)
        self.assertEqual(position.zero_based_column(), 2)

    def test_invalid_generated_position(self):
        mapping = DocumentMapping.MappingInfo(assets_path + "app.js")

        # Should map to last line and column in the generated file
        position = mapping.get_generated_position(assets_path + "app.ts", 300, 3000)

        self.assertEqual(position.file_name(), assets_path + "app.js")
        self.assertEqual(position.zero_based_line(), 29)
        self.assertEqual(position.zero_based_column(), 2)

class MappingsManagerTests(unittest.TestCase):
    def test_create_invalid_mapping(self):
        file_name = "Foobar.js"
        DocumentMapping.MappingsManager.create_mapping(file_name)
        mapping = DocumentMapping.MappingsManager.get_mapping(file_name)

        self.assertFalse(mapping.is_valid())

    def test_get_all_source_file_mappings_invalid(self):
        file_name = assets_path + "garbage.js"
        DocumentMapping.MappingsManager.create_mapping(file_name)
        result = DocumentMapping.MappingsManager.get_all_source_file_mappings()

        self.assertEqual(len(result[file_name]), 0)

    def test_create_valid_mapping(self):
        file_name = assets_path + "app.js"
        DocumentMapping.MappingsManager.create_mapping(file_name)
        mapping = DocumentMapping.MappingsManager.get_mapping(file_name)

        self.assertTrue(mapping.is_valid())

    def test_get_authored_mapping(self):
        file_name = assets_path + "app.js"
        DocumentMapping.MappingsManager.create_mapping(file_name)

        # Now request the mapping using its authored file name
        mapping = DocumentMapping.MappingsManager.get_mapping(assets_path + "app.ts")

        self.assertTrue(mapping.is_valid())

    def test_is_authored_file(self):
        file_name = assets_path + "app.js"
        DocumentMapping.MappingsManager.create_mapping(file_name)

        self.assertTrue(DocumentMapping.MappingsManager.is_authored_file(assets_path + "app.ts"))
        self.assertFalse(DocumentMapping.MappingsManager.is_authored_file(file_name))
        self.assertFalse(DocumentMapping.MappingsManager.is_authored_file("Foo.js"))

    def test_is_generated_file(self):
        file_name = assets_path + "app.js"
        DocumentMapping.MappingsManager.create_mapping(file_name)

        self.assertTrue(DocumentMapping.MappingsManager.is_generated_file(file_name))
        self.assertFalse(DocumentMapping.MappingsManager.is_generated_file(assets_path + "app.ts"))
        self.assertFalse(DocumentMapping.MappingsManager.is_generated_file("Foo.js"))

    def test_delete_mapping(self):
        file_name = assets_path + "app.js"
        DocumentMapping.MappingsManager.create_mapping(file_name)

        DocumentMapping.MappingsManager.delete_mapping(file_name)

        # Ensure both the generated and authored files do not have mappings
        self.assertFalse(DocumentMapping.MappingsManager.get_mapping(file_name))
        self.assertFalse(DocumentMapping.MappingsManager.get_mapping(assets_path + "app.ts"))

    def test_delete_all_mapping(self):
        file_name = assets_path + "app.js"
        DocumentMapping.MappingsManager.create_mapping(file_name)
        DocumentMapping.MappingsManager.create_mapping("Foo.js")

        DocumentMapping.MappingsManager.delete_all_mappings()

        # Ensure both the generated and authored files do not have mappings
        self.assertFalse(DocumentMapping.MappingsManager.get_mapping("Foo.js"))
        self.assertFalse(DocumentMapping.MappingsManager.get_mapping(file_name))
        self.assertFalse(DocumentMapping.MappingsManager.get_mapping(assets_path + "app.ts"))