# Copyright 2022 Ashley R. Thomas
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.
r"""Simple reporting with columns supporting word wrap.
"""

from textwrap import TextWrapper


class FieldDef:
    def __init__(self, header: str, max_width: int) -> None:
        self.header = header
        self.max_width = max_width


class SimpleReport:
    def __init__(self, field_defs: list[FieldDef]):
        self.field_defs = field_defs

    def render_report_header(self) -> list[str]:
        header = ""
        header_underline = ""
        for fdef in self.field_defs:
            if len(header) > 0:
                header += " "
                header_underline += " "
            header += fdef.header.ljust(fdef.max_width)
            header_underline += "-" * fdef.max_width
        return [header, header_underline]

    def render_detail_lines(self, detail_line_data: list) -> list[str]:
        if len(detail_line_data) != len(self.field_defs):
            raise ValueError(f"field_data must have the same length as field_defs")
        detail_lines = []
        tw = TextWrapper(break_long_words=True)
        all_fields_output_lines = []
        for i, fdata in enumerate(detail_line_data):
            field_def = self.field_defs[i]
            tw.width = field_def.max_width
            field_output_lines = tw.wrap(fdata)
            all_fields_output_lines.append(field_output_lines)
        line_idx = 0
        while True:
            line_str = ""
            a_field_had_data = False
            for fidx, field_output_lines in enumerate(all_fields_output_lines):
                max_width = self.field_defs[fidx].max_width
                if (
                    line_idx < len(field_output_lines)
                    and len(field_output_lines[line_idx]) > 0
                ):
                    line_str += field_output_lines[line_idx].ljust(max_width)
                    a_field_had_data = True
                else:
                    line_str += " " * max_width
                line_str += " "
            if not a_field_had_data:
                break
            detail_lines.append(line_str)
            line_idx += 1
        return detail_lines
