#!/bin/sh

rm -rf tempdir digicamdir destinationdir
mkdir tempdir 
mkdir digicamdir 
mkdir destinationdir
rm *img_053* 
cp example_images/IMG_053* .
../fetchphotos -v IMG_053*

#end
