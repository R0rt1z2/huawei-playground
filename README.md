# Huawei playground

![License](https://img.shields.io/github/license/R0rt1z2/huawei-playground)
![GitHub Issues](https://img.shields.io/github/issues-raw/R0rt1z2/huawei-playground?color=red)

In my journey of exploring Huawei devices, I've created a variety of scripts and tools, each serving different purposes.<br><br>
To make these tools readily available and easily accessible for anyone interested in reverse engineering (RE) Huawei devices, I have centralized all of them into a single repository. I will keep updating the collection with new scripts and tools.

## Description
* `cm2parser.py`: Script designed to parse CM3 images, including modem, hifi, or mcu images. It will print the header information and will dump all the sections of the image.
* `fastbootimage.py`: Script designed to parse bootloader (fastboot.img) images. It will print the header information (i.e: load address, end address and first cmd).
* `oeminfo.py`: Script to unpack and repack oeminfo images. Repacking data with higher size will result in a brick.
* `update-extractor.py`: Script to extract `UPDATE.APP` files. It will extract and print information about the images contained in the update file.

## Usage
Each tool comes with its unique functionality. To understand how to use them, you can access the help documentation by invoking it with the `-h` parameter.

## License
This project is licensed under the GPL-3.0 License - see the [LICENSE](https://github.com/R0rt1z2/huawei_playground/tree/master/LICENSE) file for details.
