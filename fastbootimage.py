#!/usr/bin/env python3

from struct import pack, unpack
from argparse import ArgumentParser

DEFAULT_START_OFFSET = 0x800

def main():
    parser = ArgumentParser()
    parser.add_argument('image', help='Bootloader image (fastboot.img)')
    parser.add_argument('--start-offset', type=lambda x: int(x, 0), default=DEFAULT_START_OFFSET, 
                        help='Specify start offset (e.g., 0x20)')
    args = parser.parse_args()

    with open(args.image, 'rb') as f:
        f.seek(args.start_offset)
        header = unpack('<I16sII', f.read(28))

    print('First command: 0x%08x' % header[0])
    print('Magic: %s' % header[1].decode('ascii'))
    print('Load address: 0x%08x' % header[2])
    print('End address: 0x%08x' % header[3])

if __name__ == '__main__':
    main()
