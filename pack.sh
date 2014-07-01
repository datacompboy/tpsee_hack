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
# repack cramfs
if [ ! -e $dir/02cramfs.bak ]; then
    mv $dir/02cramfs $dir/02cramfs.bak 2>/dev/null
fi
fakeroot -i $dir/.fakeroot mkcramfs $dir/root/ $dir/02cramfs
# construct new firmware
dd if=$dir/00header bs=1556 of=$nfw conv=notrunc 2>/dev/null
# remove old header crc32
dd if=/dev/zero bs=1 seek=8 count=4 of=$nfw conv=notrunc 2>/dev/null
# save kernel size
if [ $(stat -c %s $dir/01kernel) -ge 2097152 ]; then
    echo "WARN: size of kernel is more than 0x200000. FW probably will not flash"
fi
perl -e 'print pack("l", -s "'$dir/01kernel'")' | dd bs=1 seek=24 count=4 of=$nfw conv=notrunc 2>/dev/null
# save kernel crc32
crc32 $dir/01kernel | perl -e 'print pack("l", oct("0x".<>));' | dd bs=1 seek=28 count=4 of=$nfw conv=notrunc 2>/dev/null
# save fs offset
perl -e 'print pack("l", 1556+(-s "'$dir/01kernel'"))' | dd bs=1 seek=288 count=4 of=$nfw conv=notrunc 2>/dev/null
# save fs size
if [ $(stat -c %s $dir/02cramfs) -lt 8388608 ]; then
    echo "WARN: size of filesystem is less than 0x800000. FW probably will not flash"
fi
if [ $(stat -c %s $dir/02cramfs) -ge 15728640 ]; then
    echo "WARN: size of filesystem is more than 0xF00000. FW probably will not flash"
fi
perl -e 'print pack("l", -s "'$dir/02cramfs'")' | dd bs=1 seek=292 count=4 of=$nfw conv=notrunc 2>/dev/null
# save fs crc32
crc32 $dir/02cramfs | perl -e 'print pack("l", oct("0x".<>));' | dd bs=1 seek=552 count=4 of=$nfw conv=notrunc 2>/dev/null
# save full FW size
perl -e 'print pack("l", 1556+(-s "'$dir/02cramfs'")+(-s "'$dir/01kernel'"))' | dd bs=1 seek=12 count=4 of=$nfw conv=notrunc 2>/dev/null
# Update header crc32
crc32 $nfw | perl -e 'print pack("l", oct("0x".<>));' | dd bs=1 seek=8 count=4 of=$nfw conv=notrunc 2>/dev/null
# concat rest
cat $dir/01kernel >> $nfw
cat $dir/02cramfs >> $nfw
echo "Done"
