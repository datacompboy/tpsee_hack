fw=${1?Please give firmware bin as argument}
if [ -e $fw.unpack ]; then
    echo "Already exists: $fw.unpack"
    exit 1
fi
# Check format
if [ "$(dd if=$1 bs=8 count=1 2>/dev/null)" != "FIRMWARE" ]; then
    echo "Wrong file"
    exit 1
fi
mkdir -p $fw.unpack
echo "Extract header..."
dd if=$1 of=$fw.unpack/00header bs=1556 count=1 2>/dev/null
blocks=$(dd if=$1 bs=1 count=4 skip=16 2>/dev/null | perl -e 'print unpack("l", <>);')
if [ $blocks -eq 3 ]; then
    echo "Extract kernel..."
    ksize=$(dd if=$1 bs=1 count=4 skip=24 2>/dev/null | perl -e 'print unpack("l", <>);')
    dd if=$1 of=$fw.unpack/01kernel bs=1 skip=1556 count=$ksize 2>/dev/null
fi
echo "Extract filesystem..."
foff=$(dd if=$1 bs=1 count=4 skip=288 2>/dev/null | perl -e 'print unpack("l", <>);')
dd if=$1 of=$fw.unpack/02cramfs bs=$foff skip=1 2>/dev/null
file $fw.unpack/02cramfs | grep Squash >/dev/null && mv $fw.unpack/02cramfs $fw.unpack/02squashfs
echo "Unpack filesystem..."
cd $fw.unpack
if [ -f 02cramfs ]; then
    fakeroot -s .fakeroot cramfsck -x root 02cramfs
elif [ -f 02squashfs ]; then
    fakeroot -s .fakeroot unsquashfs -d root 02squashfs
fi
chmod +r -R root/
echo "Done"
