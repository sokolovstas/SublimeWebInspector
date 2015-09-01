import SourcemapTests
import DocumentMappingTests
import unittest
import os

def registerAndRunTests(className):
    print("Running tests for", className.__name__)
    suite = unittest.TestLoader().loadTestsFromTestCase(className)
    unittest.TextTestRunner(verbosity=2).run(suite)

if 'PAUSETESTS' in os.environ:
    input("Press Enter to continue...")

# Source map parser tests
registerAndRunTests(SourcemapTests.SourceMapParserTests)
registerAndRunTests(SourcemapTests.ParsedSourceMapTests)
registerAndRunTests(SourcemapTests.LineMappingsTests)

# Document mapping tests
registerAndRunTests(DocumentMappingTests.PositionTests)
registerAndRunTests(DocumentMappingTests.MappingInfoTests)
registerAndRunTests(DocumentMappingTests.MappingsManagerTests)

print("Done tests...")
