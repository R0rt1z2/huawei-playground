#!/usr/bin/env python3

from enum import Enum
from pathlib import Path
from typing import Union, List
from struct import unpack, pack
from argparse import ArgumentParser

MAGIC = b'OEM_INFO'

class Operation(Enum):
    OINV_OP_MIN = 0
    OEMINFO_WRITE = 1
    OEMINFO_READ = 2
    OEMINFO_GETAGE = 3
    OEMINFO_GETINFO = 4
    OEMINFO_ERASE = 5

class OemInfoEntry:
    def __init__(self, header: bytes, version: int, id: int,
                 type: int, length: int, age: int, data: bytes, start: int):
        self.header = header
        self.version = version
        self.id = id
        self.type = type
        self.length = length
        self.age = age
        self.data = data
        self.start = start

        assert len(data) == length, "Data length mismatch."

    def __str__(self):
        return "%d-%d-%d-%d-0x%x" % (self.version, self.id,
                                    self.type, self.age, self.start)

    @classmethod
    def from_bytes(cls, data: bytes, offset: int = 0):
        (header, version, id, type,
         length, age) = unpack('<8sIIIII', data[offset:offset+28])
        return cls(header, version, id, type, length, age,
                   data[offset+0x200:offset+0x200+length], offset)

class OemInfoImage:
    def __init__(self, image : Union[bytes, Path]):
        if isinstance(image, Path):
            with open(image, 'rb') as fp:
                self.image = bytearray(fp.read())
        else:
            self.image = image

        self.entries: List[OemInfoEntry] = []
        self.parse_entries()

    def parse_entries(self):
        offset = self.image.find(MAGIC)
        while offset != -1:
            self.entries.append(
                OemInfoEntry.from_bytes(self.image, offset))
            offset = self.image.find(MAGIC, offset + 1)

    def extract_entries(self, output: Path):
        Path(output).mkdir(parents=True, exist_ok=True)
        for entry in self.entries:
            with open("%s/%s.bin" %
                      (output, str(entry)), 'wb') as fp:
                fp.write(entry.data)
        print("Extracted %d entries to '%s'." %
              (len(self.entries), output))

    def repack_entries(self, input: Path, output: Path):
        for entry in self.entries:
            with open("%s/%s.bin" %
                      (input, str(entry)), 'rb') as fp:
                self.image[entry.start+0x200:
                           entry.start+0x200+entry.length] = fp.read()

        with open(output, 'wb') as fp:
            fp.write(self.image)

        print("Repacked %d entries to '%s'." %
                (len(self.entries), output))

def main():
    parser = ArgumentParser()
    subparsers = parser.add_subparsers(dest='action')

    parser_extract = subparsers.add_parser('extract', help='Extract entries.')
    parser_extract.add_argument('image', help='Path to the oeminfo image.', type=Path)
    parser_extract.add_argument('-o', '--output', help='Output path.', default='output', type=Path)
    parser_extract.add_argument('-p', '--print', help='Print entries.', action='store_true')

    parser_repack = subparsers.add_parser('repack', help='Repack entries.')
    parser_repack.add_argument('image', help='Path to the oeminfo image.', type=Path)
    parser_repack.add_argument('input', help='Path to the extracted folder.', type=Path)
    parser_repack.add_argument('-o', '--output', help='Output file.', default='oeminfo.pack', type=Path)

    args = parser.parse_args()
    image = OemInfoImage(args.image)

    if args.action == 'extract':
        image.extract_entries(args.output)
    elif args.action == 'repack':
        image.repack_entries(args.input,
                             args.output)

if __name__ == '__main__':
    main()
