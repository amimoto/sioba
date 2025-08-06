from .base import Buffer, register_buffer
import re

@register_buffer("line")
class LineBuffer(Buffer):
    """
    Raw buffer implementation that does not process input.
    This is a simple buffer that can be used for testing or debugging.
    """
    buffer_lines: list[bytes]

    def initialize(self, **extra):
        self.buffer_lines = [ b"" ]

    def append_to_buffer(self, buffer_lines: list[bytes], data: bytes) -> None:
        """ Append data to the buffer lines. This is a separate method
            to make testing easier.
        """
        while data:
            splits = re.split(rb"(\r\n|\n\r|\n)", data, maxsplit=1)
            if len(splits) == 1:
                buffer_lines[-1] += splits[0]
                break

            elif len(splits) == 3:
                line, _, data = splits
                buffer_lines[-1] += line
                buffer_lines.append(b"")

            else:
                raise ValueError("Unexpected split result")

            # Crop any excess lines
            scrollback_buffer_size = self.context.scrollback_buffer_size \
                            + self.context.rows

            if scrollback_buffer_size > 0:
                while len(buffer_lines) > scrollback_buffer_size:
                    buffer_lines.pop(0)

        # Fix the cursor position
        row = len(self.buffer_lines) - 1
        col = len(self.buffer_lines[-1])

        if col > self.interface.context.cols:
            row += int(col / self.interface.context.cols)
            col %= self.interface.context.cols

        if row > self.interface.context.rows:
            row = self.interface.context.rows - 1

        self.interface.context.cursor_row = row
        self.interface.context.cursor_col = col

    async def feed(self, data: bytes) -> None:
        """ This intercepts data sent to the frontend. """
        self.append_to_buffer(self.buffer_lines, data)

    def dump_screen_state(self) -> bytes:
        return b"\n".join(self.buffer_lines).rstrip(b"\n")




