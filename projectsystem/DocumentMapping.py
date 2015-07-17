from projectsystem import Sourcemap

class Position:
    def __init__(self, file_name, line, column):
        # zero-based line and column values
        self.__file_name = file_name
        self.__line = line
        self.__column = column

    def one_based_line(self):
        return self.__line + 1

    def one_based_column(self):
        return self.__column + 1

    def zero_based_line(self):
        return self.__line

    def zero_based_column(self):
        return self.__column

    def file_name(self):
        return self.__file_name


class MappingsMannager:
    def __init__(self):
        self.file_mappings = {}

    def create_mapping(self, file_name):
        mapping = MappingInfo(file_name)
        self.file_mappings[file_name.lower()] = mapping

    def get_mapping(self, file_name):
        file_name = file_name.lower()
        if file_name in self.file_mappings:
            return self.file_mappings[file_name]

    def delete_mapping(self, file_name):
        file_name = file_name.lower()
        if file_name in self.file_mappings:
            self.file_mappings.pop(file_name)

    def delete_all_mappings(self):
        self.file_mappings.clear()


class MappingInfo:
    def __init__(self, generated_file):
        source_map_file = Sourcemap.get_sourcemap_file(generated_file)
        self.parsed_source_map = Sourcemap.ParsedSourceMap(source_map_file)
        self.generated_file = generated_file

        self.authored_sources = []
        if self.parsed_source_map: 
            self.authored_sources = self.parsed_source_map.get_authored_sources_path()
            self.line_mappings = self.parsed_source_map.line_mappings

    def get_mapped_files(self):
        return self.authored_sources

    def get_generated_file(self):
        return self.generated_file

    def get_mapped_location(self, zero_based_line, zero_based_column):
        # Invalid line and column values or line mappings do not exist
        if (zero_based_line < 0 or zero_based_column < 0 or len(self.line_mappings) <= 0):
            return None

        mapping_index = Sourcemap.LineMapping.binary_search(self.line_mappings,
                                                            zero_based_line,
                                                            zero_based_column,
                                                            lambda line_mapping, line, column: Sourcemap.LineMapping.compare_generated_mappings(line_mapping, line, column))

        line_number = max(self.line_mappings[mapping_index].source_line, 0)
        column_number = max(self.line_mappings[mapping_index].source_column, 0)
        file_number = max(self.line_mappings[mapping_index].file_num, 0)

        return Position(self.authored_sources[file_number], line_number, column_number)

    def get_generated_location(self, authored_file_name, zero_based_line, zero_based_column):
        return None

# Create a mappings manager object to maintain file source mappings
mappings_manager = MappingsMannager()