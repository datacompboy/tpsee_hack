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
echo "Extract kernel..."
ksize=$(dd if=$1 bs=1 count=4 skip=24 2>/dev/null | perl -e 'print unpack("l", <>);')
dd if=$1 of=$fw.unpack/01kernel bs=1 skip=1556 count=$ksize 2>/dev/null
echo "Extract filesystem..."
foff=$(dd if=$1 bs=1 count=4 skip=288 2>/dev/null | perl -e 'print unpack("l", <>);')
dd if=$1 of=$fw.unpack/02cramfs bs=$foff skip=1 2>/dev/null
echo "Unpack filesystem..."
cd $fw.unpack
fakeroot -s .fakeroot cramfsck -x root 02cramfs
chmod +r -R root/
echo "Done"
