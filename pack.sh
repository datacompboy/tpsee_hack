dir=${1?Please give path to a directory with unpacked firmware}
nfw=${2?Please give name for a newly packed firmware}
if [ ! -e $dir ]; then
    echo "Directory not exists: $dir"
    exit 1
fi
if [ -e $nfw ]; then
    echo "Firmware already exists: $nfw"
    exit 1
fi
# repack rootfs
if [ -e $dir/02cramfs ]; then
    if [ ! -e $dir/02cramfs.bak ]; then
        mv $dir/02cramfs $dir/02cramfs.bak 2>/dev/null
    fi
    fakeroot -i $dir/.fakeroot mkcramfs $dir/root/ $dir/02cramfs
elif [ -e $dir/02squashfs -o -e $dir/02squashfs.bak ]; then
    if [ ! -e $dir/02squashfs.bak ]; then
        mv $dir/02squashfs $dir/02squashfs.bak 2>/dev/null
    fi
    rm $dir/02squashfs 2>/dev/null
    fakeroot -i $dir/.fakeroot mksquashfs $dir/root/ $dir/02squashfs
else
    echo "Unknown root fs type"
fi
# construct new firmware
dd if=$dir/00header bs=1556 of=$nfw conv=notrunc 2>/dev/null
blocks=$(dd if=$nfw bs=1 count=4 skip=16 2>/dev/null | perl -e 'print unpack("l", <>);')
# remove old header crc32
dd if=/dev/zero bs=1 seek=8 count=4 of=$nfw conv=notrunc 2>/dev/null
# save kernel size
if [ $blocks -eq 3 ]; then
    kernsize=$(stat -c %s $dir/01kernel)
    if [ $kernsize -ge 2097152 ]; then
        echo "WARN: size of kernel is more than 0x200000. FW probably will not flash"
    fi
    perl -e 'print pack("l", -s "'$dir/01kernel'")' | dd bs=1 seek=24 count=4 of=$nfw conv=notrunc 2>/dev/null
    # save kernel crc32
    crc32 $dir/01kernel | perl -e 'print pack("l", oct("0x".<>));' | dd bs=1 seek=28 count=4 of=$nfw conv=notrunc 2>/dev/null
else
    kernsize=0
fi
# save fs offset
perl -e 'print pack("l", 1556+'$kernsize')' | dd bs=1 seek=288 count=4 of=$nfw conv=notrunc 2>/dev/null
# save fs size
if [ $(stat -c %s $dir/02*fs) -lt 8388608 ]; then
    echo "WARN: size of filesystem is less than 0x800000."
fi
if [ $(stat -c %s $dir/02*fs) -ge 15728640 ]; then
    echo "WARN: size of filesystem is more than 0xF00000."
fi
perl -e 'print pack("l", -s "'$(echo -n $dir/02*fs)'")' | dd bs=1 seek=292 count=4 of=$nfw conv=notrunc 2>/dev/null
# save fs crc32
crc32 $dir/02*fs | perl -e 'print pack("l", oct("0x".<>));' | dd bs=1 seek=552 count=4 of=$nfw conv=notrunc 2>/dev/null
# save full FW size
perl -e 'print pack("l", 1556+(-s "'$(echo -n $dir/02*fs)'")+(-s "'$dir/01kernel'"))' | dd bs=1 seek=12 count=4 of=$nfw conv=notrunc 2>/dev/null
# Update header crc32
crc32 $nfw | perl -e 'print pack("l", oct("0x".<>));' | dd bs=1 seek=8 count=4 of=$nfw conv=notrunc 2>/dev/null
# concat rest
if [ $blocks -eq 3 ]; then
    cat $dir/01kernel >> $nfw
fi
cat $dir/02*fs >> $nfw
echo "Done"
