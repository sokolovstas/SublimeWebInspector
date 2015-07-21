import json
import os
from projectsystem import VLQDecoder

def get_sourcemap_file(file_name):
    sourcemap_prefix = "//# sourceMappingURL="
    map_file = ""
    with open(file_name, "r") as f:
        sourcemap_info = f.readlines()[-1]

        if (len(sourcemap_info) > 0 and sourcemap_info.index(sourcemap_prefix) is 0):
            map_file = sourcemap_info[len(sourcemap_prefix):].strip()
            map_file = os.path.dirname(file_name) + os.path.sep + map_file
        f.close()

    return map_file


class ParsedSourceMap:
    def __init__(self, file_name):
        with open(file_name, "r") as f:
            self.content = json.loads(f.read())
            f.close()

        if self.content:
            self.root_path = os.path.abspath(os.path.dirname(file_name) + os.path.sep + self.content["sourceRoot"]) 
            self.version = self.content["version"]
            self.authored_sources = self.content["sources"]
            self.line_mappings = SourceMapParser.calculate_line_mappings(self.content)

    def get_authored_sources_path(self):
        return [os.path.abspath(self.root_path + os.path.sep + x) for x in self.authored_sources]


class LineMapping:
        # All line mappings are zero based
        def __init__(self):
            self.generated_line = 0
            self.generated_column = 0
            self.source_line = 0
            self.source_column = 0
            self.file_num = 0

        @staticmethod
        def compare_generated_mappings(mapping, line, column):
            return (column - mapping.generated_column) if (mapping.generated_line == line) else line - mapping.generated_line

        @staticmethod
        def compare_source_mappings(mapping, line, column):
            return (column - mapping.source_column) if (mapping.source_line == line) else line - mapping.source_line 

        @staticmethod
        def binary_search(line_mappings, line, column, comparator):
            max_index = len(line_mappings) - 1
            min_index = 0

            while (min_index <= max_index):
                mid = (max_index + min_index) >> 1

                comparison = comparator(line_mappings[mid], line, column)
                if (comparison > 0):
                    min_index = mid + 1
                elif (comparison < 0):
                    max_index = mid - 1
                else:
                    max_index = mid
                    break

            # Find the closest match
            result = max(min(len(line_mappings) - 1, max_index), 0)
            while (result + 1 < len(line_mappings) and comparator(line_mappings[result + 1], line, column) == 0):
                result += 1

            return result


class SourceMapParser:
    StartScopeSegmentDelimiter = '>'
    EndScopeSegmentDelimiter = '<'
    SegmentDelimiter = ','
    ScopeOrLineDelimiter = ';'

    @staticmethod
    def calculate_line_mappings(content):
        if (not content or
            content["version"] != 3 or
            not content["mappings"] or
            type(content["mappings"]) is not str or
            not content["sources"] or
            len(content["sources"]) is 0):
            return None

        max_file_num = len(content["sources"])
        last_mapping = LineMapping()
        generated_line = 0
        encoded_mappings = content["mappings"]
        current_file = 0
        parsing_index = 0
        length = len(encoded_mappings)

        mapping_list = []

        while parsing_index < length:
            if (encoded_mappings[parsing_index] == SourceMapParser.ScopeOrLineDelimiter):
                generated_line += 1
                parsing_index += 1
                last_mapping.generated_column = 0
            elif (encoded_mappings[parsing_index] == SourceMapParser.SegmentDelimiter):
                parsing_index += 1
            else:
                mapping = LineMapping()
                mapping.generated_line = generated_line

                # Get relative column offset
                result = VLQDecoder.decode(encoded_mappings, parsing_index)
                mapping.generated_column = last_mapping.generated_column + result["value"]
                last_mapping.generated_column = mapping.generated_column
                parsing_index += result["chars_read"]

                # Relative source index
                if (parsing_index < length and
                    encoded_mappings[parsing_index] != SourceMapParser.ScopeOrLineDelimiter and
                    encoded_mappings[parsing_index] != SourceMapParser.SegmentDelimiter):
                    result = VLQDecoder.decode(encoded_mappings, parsing_index)
                    current_file += result["value"]

                    if current_file > max_file_num:
                        return None

                    parsing_index += result["chars_read"]

                mapping.file_num = current_file

                # Relative source line
                if (parsing_index < length and
                    encoded_mappings[parsing_index] != SourceMapParser.ScopeOrLineDelimiter and
                    encoded_mappings[parsing_index] != SourceMapParser.SegmentDelimiter):
                    result = VLQDecoder.decode(encoded_mappings, parsing_index)
                    mapping.source_line = last_mapping.source_line + result["value"]
                    last_mapping.source_line = mapping.source_line
                    parsing_index += result["chars_read"]

                # Relative source column
                if (parsing_index < length and
                    encoded_mappings[parsing_index] != SourceMapParser.ScopeOrLineDelimiter and
                    encoded_mappings[parsing_index] != SourceMapParser.SegmentDelimiter):
                    result = VLQDecoder.decode(encoded_mappings, parsing_index)
                    mapping.source_column = last_mapping.source_column + result["value"]
                    last_mapping.source_column = mapping.source_column
                    parsing_index += result["chars_read"]

                # Check if there is a name, ignore it
                if (parsing_index < length and
                    encoded_mappings[parsing_index] != SourceMapParser.ScopeOrLineDelimiter and
                    encoded_mappings[parsing_index] != SourceMapParser.SegmentDelimiter):
                    result = VLQDecoder.decode(encoded_mappings, parsing_index)
                    parsing_index += result["chars_read"]

                mapping_list.append(mapping)

        return mapping_list
