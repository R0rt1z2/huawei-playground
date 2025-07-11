#!/usr/bin/env python3

from enum import Enum
from pathlib import Path
from typing import Union
from struct import unpack
from argparse import ArgumentParser

START_OFFSET = 0x800
LPM3_MAGIC_OFFSET = 0x3F8

class DspImageType(Enum):
    DSP_IMAGE_SEC_TYPE_CODE = 0
    DSP_IMAGE_SEC_TYPE_DATA = 1
    DSP_IMAGE_SEC_TYPE_BUTT = 2

class DspImageLoad(Enum):
    DSP_IMAGE_SEC_LOAD_STATIC = 0
    DSP_IMAGE_SEC_LOAD_DYNAMIC = 1
    DSP_IMAGE_SEC_LOAD_BUFFER = 2
    DSP_IMAGE_SEC_LOAD_MODEM_ENTRY = 3
    DSP_IMAGE_SEC_LOAD_BUTT = 4

class InvalidCM3Image(Exception):
    def __init__(self, image: bytes) -> None:
        super().__init__()
        self.image = image

    def __str__(self) -> str:
        return "Invalid CM3 image '%s'." % self.image

class DspImageSec:
    def __init__(self, index: int, type: DspImageType, load: DspImageLoad,
                 src_off: int, dst_off: int, size: int) -> None:
        self.index = index
        self.type = type
        self.load = load
        self.src_off = src_off
        self.dst_off = dst_off
        self.size = size

    @classmethod
    def from_bytes(cls, data: bytes) -> 'DspImageSec':
        (index, type_code, load_code,
         src_off, dst_off, size) = unpack('<HBBLLL', data)
        return cls(index, DspImageType(type_code), DspImageLoad(load_code),
                   src_off, dst_off, size)

class CM3Header:
    def __init__(self, timestamp: str, image_size: int,
                 sec_num: int, sections: list[DspImageSec]) -> None:
        self.timestamp = timestamp
        self.image_size = image_size
        self.sec_num = sec_num
        self.sections = sections

    @classmethod
    def from_bytes(cls, data: bytes) -> 'CM3Header':
        sections = []
        timestamp, image_size, sec_num = unpack('<24sLL', data[:32])

        offset = 32
        for _ in range(min(sec_num, 30)):
            sections.append(DspImageSec.from_bytes(data[offset:offset + 16]))
            offset += 16

        return cls(timestamp.decode('utf-8'), image_size, sec_num, sections)

class CM3Image:
    def __init__(self, image: Union[Path, bytes]) -> None:
        if isinstance(image, Path):
            with open(image, 'rb') as fp:
                fp.seek(START_OFFSET)
                self.image = fp.read()
        else:
            self.image = image

        self.header: CM3Header = (
            CM3Header.from_bytes(self.image)
        )

        if self.header.image_size == 0:
            raise InvalidCM3Image(image)

def main():
    parser = ArgumentParser()
    parser.add_argument('image', type=Path, help='Path to the image.')
    args = parser.parse_args()

    image = CM3Image(args.image)

    print('Header')
    print('|- Timestamp: %s' % image.header.timestamp)
    print('|- Image size: %d' % image.header.image_size)
    print('|- Sections: %d' % image.header.sec_num)
    print('|')

    for section in image.header.sections:
        print('|-- Section %d' % section.index)
        print('   |- Type: %s' % section.type.name)
        print('   |- Load: %s' % section.load.name)
        print('   |- Source offset: 0x%x' % section.src_off)
        print('   |- Destination offset: 0x%x' % section.dst_off)
        print('   |- Size: 0x%x' % section.size)

if __name__ == '__main__':
    main()
