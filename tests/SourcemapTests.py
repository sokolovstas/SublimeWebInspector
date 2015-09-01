import unittest
import json
import re
import os
import sys

parent_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(1, parent_dir)
sys.path.insert(1, parent_dir + "\\" + "projectsystem")

import projectsystem
from projectsystem import Sourcemap

# Assets path is relative to the test folder. All the tests should be run from the root folder
assets_path = os.path.abspath("tests" + os.path.sep + "assets").lower() + os.path.sep

class SourceMapParserTests(unittest.TestCase):
    map_version_2 = '{"version":2,"file":"output.js","sources":["input1.js","input2.js","input3.js"],"names":["average","b","c","median","dataSet","i","push","Error","statisticalMess"],"mappings":"AAAA,GAAIA,SAAU,CACd,IAAIC,GAAI,CACR,IAAIC,GAAIF,QAAUC,CAGlB,OAAMD,QAAUC,EAAIC,EAAG,CACnBF,QAAUA,QAAU,ECNxB,GAAIG,QAAS,EACb,IAAIC,WACJ,KAAI,GAAIC,GAAI,EAAGA,EAAI,EAAGA,IAAK,CACvBD,QAAQE,KAAKH,QAAUE,EAAI,GAAK,GAIpC,GAAGD,QAAQ,KAAOD,OAAQ,CACtB,KAAM,IAAII,OAAM,WCRpB,GAAIC,iBAAkBR,QAAUG,MAChCK,iBAAkBR,QAAUQ,gBAAkBL,MAG9CK,iBAAkB"}' 

    map_version_3 = '{"version":3,"file":"HelloWorld.js","sourceRoot":"","sources":["HelloWorld.ts"],"names":["Printer","printer","Printer.printer"],"mappings":"AAAA,IAAO,OAAO;AAGb,CAHD,UAAO,OAAO;IACHA,QAAIA,OAAOA,GAAGA,OAAOA,CAACA,GAAGA;IAChCA,QAASA;AACbA,CAACA,6BAAA","x_ms_mediaTypes":["application/x.typescript;version=1.0.3.0"],"x_ms_compilerFlags":"--target ES3 --module commonjs","x_ms_scopes":"CU>GT<","x_ms_locals":"CC"}'

    def test_nonexistent_file_does_not_throw(self):
        file_name = Sourcemap.get_sourcemap_file("NotExistentFile")
        self.assertFalse(file_name)

    def test_valid_json_invalid_map_does_not_throw(self):
        file_name = Sourcemap.get_sourcemap_file("randomjson.js") # exists, but not valid map file
        self.assertFalse(file_name)

    def test_version_check(self):
        line_mappings = Sourcemap.SourceMapParser.calculate_line_mappings(json.loads(self.map_version_2))
        self.assertFalse(line_mappings)

        line_mappings = Sourcemap.SourceMapParser.calculate_line_mappings(json.loads(self.map_version_3))
        self.assertTrue(line_mappings)

    def test_line_mapping_count(self):
        content = json.loads(self.map_version_3)
        line_mappings = Sourcemap.SourceMapParser.calculate_line_mappings(content)
        self.assertEqual(len(line_mappings), len(re.split('[,;]', content["mappings"])))

class ParsedSourceMapTests(unittest.TestCase):
    def test_invalid_file_does_not_throw(self):
        parsed_map = Sourcemap.ParsedSourceMap("")
        self.assertFalse(parsed_map.is_valid())
        self.assertFalse(parsed_map.content)

    def test_valid_json_invalid_map_does_not_throw(self):
        parsed_map = Sourcemap.ParsedSourceMap(assets_path + "randomjson.js.map") # exists, but not valid map file
        self.assertFalse(parsed_map.is_valid())

    def test_invalid_file_returns_empty_authored_list(self):
        parsed_map = Sourcemap.ParsedSourceMap("")
        self.assertFalse(parsed_map.is_valid())
        self.assertEqual(len(parsed_map.get_authored_sources_path()), 0)

    def test_valid_map_file_parsing(self):
        parsed_map = Sourcemap.ParsedSourceMap(assets_path + "app.js.map")  
        self.assertTrue(parsed_map.is_valid())
        self.assertTrue(parsed_map.content)

    def test_valid_map_authored_list(self):
        parsed_map = Sourcemap.ParsedSourceMap(assets_path + "app.js.map")
        self.assertTrue(parsed_map.is_valid())
        self.assertEqual(parsed_map.version, 3)
        self.assertEqual(len(parsed_map.get_authored_sources_path()), 1)
        self.assertEqual(parsed_map.get_authored_sources_path(), [assets_path + "app.ts"])

class LineMappingsTests(unittest.TestCase):
    def test_empty_mappings(self):
        self.assertFalse(Sourcemap.LineMapping.binary_search([], 0, 0, Sourcemap.LineMapping.compare_source_mappings))
        self.assertFalse(Sourcemap.LineMapping.binary_search([], 0, 0, Sourcemap.LineMapping.compare_generated_mappings))

    def test_binary_search_source_mappings(self):
        parsed_map = Sourcemap.ParsedSourceMap(assets_path + "app.js.map")
        result = Sourcemap.LineMapping.binary_search(parsed_map.line_mappings, 10, 16, Sourcemap.LineMapping.compare_source_mappings)
        
        self.assertTrue(result, 16)
        mapping = parsed_map.line_mappings[result]
        self.assertEqual(mapping.generated_line, 5)
        self.assertEqual(mapping.generated_column, 16)

    def test_binary_search_generated_mappings(self):
        parsed_map = Sourcemap.ParsedSourceMap(assets_path + "app.js.map")
        result = Sourcemap.LineMapping.binary_search(parsed_map.line_mappings, 5, 16, Sourcemap.LineMapping.compare_generated_mappings)
        
        self.assertTrue(result, 16)
        mapping = parsed_map.line_mappings[result]
        self.assertEqual(mapping.source_line, 10)
        self.assertEqual(mapping.source_column, 16)

    def test_binary_search_not_existent_source_mappings(self):
        parsed_map = Sourcemap.ParsedSourceMap(assets_path + "app.js.map")
        result = Sourcemap.LineMapping.binary_search(parsed_map.line_mappings, 100, 1000, Sourcemap.LineMapping.compare_source_mappings)

        # It should return the last line mapping
        self.assertTrue(result, len(parsed_map.line_mappings))

        mapping = parsed_map.line_mappings[result]
        self.assertEqual(mapping.generated_line, 29)
        self.assertEqual(mapping.generated_column, 2)

    def test_binary_search_not_existent_generated_mappings(self):
        parsed_map = Sourcemap.ParsedSourceMap(assets_path + "app.js.map")
        result = Sourcemap.LineMapping.binary_search(parsed_map.line_mappings, 100, 1000, Sourcemap.LineMapping.compare_generated_mappings)

        # It should return the last line mapping
        self.assertTrue(result, len(parsed_map.line_mappings))

        mapping = parsed_map.line_mappings[result]
        self.assertEqual(mapping.source_line, 36)
        self.assertEqual(mapping.source_column, 2)
