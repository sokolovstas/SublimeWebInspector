import SourcemapTests
import DocumentMappingTests
import unittest

def registerAndRunTests(className):
    print("Running tests for", className.__name__)
    suite = unittest.TestLoader().loadTestsFromTestCase(className)
    unittest.TextTestRunner(verbosity=2).run(suite)

# Source map parser tests
registerAndRunTests(SourcemapTests.SourceMapParserTests)
registerAndRunTests(SourcemapTests.ParsedSourceMapTests)
registerAndRunTests(SourcemapTests.LineMappingsTests)

# Document mapping tests
registerAndRunTests(DocumentMappingTests.PositionTests)
registerAndRunTests(DocumentMappingTests.MappingInfoTests)
registerAndRunTests(DocumentMappingTests.MappingsManagerTests)
