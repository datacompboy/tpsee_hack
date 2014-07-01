#!/usr/bin/python
import sys, re
from elftools.elf.elffile import ELFFile
DEBUG = False
fname = sys.argv[1]

blockMask = """
  ; makeSocketBlocking
 mm
  ?? ?? 2D E9 ; STMFD SP!, ....
  03 10 A0 E3 ; MOV R1, #3 ; cmd
  00 20 A0 E3 ; MOV R2, #0
  00 ?? A0 E1 ; MOV Rx, R0 ; save fd
  ?? ?? FF EB ; BL fcntl
  04 10 A0 E3 ; MOV R1, #4 ; cmd
  02 2B C0 E3 ; clear O_NONBLOCK
  ?? 00 A0 E1 ; restore fd
  ?? ?? FF EB ; BL fcntl
  00 00 E0 E1 ; MVN R0, R0
  A0 0F A0 E1 ; MOV R0, R0,LSR#31
  ?? ?? BD E8 ; LDMFD SP!, ....
 mm
  ; makeSocketNonblocking
  ?? ?? 2D E9
  03 10 A0 E3
  00 20 A0 E3
  00 ?? A0 E1
  ?? ?? FF EB
  04 10 A0 E3
  02 2B 80 E3
  ?? 00 A0 E1
  ?? ?? FF EB
  00 00 E0 E1
  A0 0F A0 E1
  ?? ?? BD E8
"""

sendLoopMask = """
  ?? 00 00 EA ;               B       loopBody
              ; ---------------------------------------------------------------------------
 mm           ;loopNext                               ; CODE XREF: SendPacket+74j
  ?? ?? ?? E5 ;               LDR     R4, [R4,#4] (or R5)
  00 00 ?? E3 ;               CMP     R4, #0      (or R5)
  ?? 00 00 0A ;               BEQ     loc_6CA74
              ;loopBody                               ; CODE XREF: SendPacket+4Cj
 mm           ;                                       ; SendPacket+D0nj
  ?? ?? A0 E1 ;               MOV     R3, R4      (or R5)
  ?? ?? A0 E1 ;               MOV     R1, R5
  ?? ?? A0 E1 ;               MOV     R2, R7
  ?? ?? A0 E1 ;               MOV     R0, R6
 mm
  ?? ?? ?? EB ;               BL      SendRTPOverTCP
  00 00 50 E3 ;               CMP     R0, #0
  F5 FF FF AA ;               BGE     loopNext
"""

def maskToRegex(mask):
    mask = re.sub( ";.*$", "", mask, flags=re.MULTILINE)
    mask = re.sub( "\s+", "", mask, flags=re.MULTILINE)
    masks = re.findall( "..", mask)
    rgx = ""
    for m in masks:
        if m == "??":
            rgx += "."
        elif m == "mm":
            rgx += "()"
        else:
            rgx += "\\x"+m
    return rgx

def BinArg(off):
    return ord(fw[off])+ord(fw[off+1])*256+ord(fw[off+2])*256*256
def ArgToBin(arg):
    return chr(arg%256)+chr(arg/256%256)+chr(arg/256/256%256)

def cmdTargetOffset(cmdoff):
    d1 = BinArg(cmdoff)
    if d1 >= 0x800000: d1 -= 0x1000000
    return (cmdoff+(d1+1)*4+4)

def cmdTargetArg(cmdoff, target):
    d1 = (target - (cmdoff+4))/4 - 1
    if d1 < 0:
        d1 += 0x1000000
    return d1

f = open(fname, "r+b")
f.seek(0, 2)
size = f.tell()
f.seek(0, 0)
fw = f.read(size)
f.seek(0, 0)
Elf = ELFFile(f)

# Array of patches to apply on file
patches = []
# Every patch is tuple: (offset, newBodyString)

# Convert offset to virtual address
def offToVA(offset):
    for k in Elf.iter_segments():
        if offset >= k['p_offset'] and offset <= k['p_offset']+k['p_filesz']:
            return k['p_vaddr']+(offset-k['p_offset'])

# Find previous function begin offset (nearest STMFD SP!, {...} instruction)
def findFuncBegin(offset, maxLen = 0x1000):
    maxStart = max(0, offset-maxLen)
    offset -= 4
    while offset > maxStart:
        if fw[offset+2:offset+4]=="\x2D\xE9":
            return offset
        offset -= 4
    return None

def findStringLink(s):
    ## Find string itself
    offStr = re.findall(s+"\x00", fw)
    if len(offStr)==1:
        offStr = re.search(s+"\x00", fw)
        offStrVA = offToVA(offStr.start(0))
        if DEBUG: print "offStr["+s+"] =", hex(offStrVA)
    elif len(offStr)==0:
        print s, "string marker not found"
    else:
        print "Too many", s, "string markers found"
    ## Find offset to string
    reStrLink = "\\x%02X\\x%02X\\x%02X\\x%02X" % (
                (offStrVA)%256, 
                (offStrVA/256)%256, 
                (offStrVA/256/256)%256, 
                (offStrVA/256/256/256)%256 )
    offLink = re.findall(reStrLink, fw)
    if len(offLink)==1:
        offLink = re.search(reStrLink, fw)
        offLink = offLink.start(0)
        if DEBUG: print "offLink["+s+"] = ", hex(offToVA(offLink))
        return offLink
    else:
        print "Can't find usage of sendPacket"


### 1. Find offset of makeSocketBlocking and makeSocketNonblocking
makeBlock = None
makeNonBlock = None
for find in re.finditer(maskToRegex(blockMask), fw, re.DOTALL):
    if makeBlock is None and makeNonBlock is None:
        makeBlock = find.start(1)
        makeNonBlock = find.start(2)
        if DEBUG: print "Found makeNonBlock at ", hex(offToVA(makeNonBlock))
        if DEBUG: print "Found makeBlock at ", hex(offToVA(makeBlock))
    else:
        print "Non-unqiue makeNonBlock/makeBlocking functions found"
        break
if makeBlock is None or makeNonBlock is None:
    print "makeNonBlock/makeBlocking functions not found"

### 2. Find sendPacket function
sendPacketEnd = findStringLink("sendPacket")
sendPacketStart = findFuncBegin(sendPacketEnd)
if sendPacketStart is not None:
    if DEBUG: print "sendPacketStart = ", hex(offToVA(sendPacketStart))
else:
    print "Can't find start of sendPacket"

### 3. Find sendRTPOverTCP function
sendRTPOverTCPStart = findFuncBegin(findStringLink("sendRTPOverTCP"))
if sendRTPOverTCPStart is not None:
    if DEBUG: print "sendRTPOverTCPStart = ", hex(offToVA(sendRTPOverTCPStart))
else:
    print "Can't find start of sendPacket"

### 4. find loop in sendPacket
sendPacketLoopRx = maskToRegex(sendLoopMask)
sendPacketLoop = re.findall(sendPacketLoopRx, fw, re.DOTALL)
if len(sendPacketLoop)==1:
    sendPacketLoop = re.search(sendPacketLoopRx, fw, re.DOTALL)
    sendPacketLoopNext = sendPacketLoop.start(1)
    sendPacketLoopBL = sendPacketLoop.start(3)
    sendPacketLoop = sendPacketLoop.start(2)
    if DEBUG: print "sendPacket loop at ", hex(offToVA(sendPacketLoop))
elif len(sendPacketLoop)==0:
    print "Loop inside sendPacket not found"
else:
    print "Non-unqiue loops masks for sendPacket found"
## 4.1. check that loop link is really to sendRTPOverTCP
if cmdTargetOffset(sendPacketLoopBL) != sendRTPOverTCPStart:
    print "Loop's first call is not sendRTPOverTCP"
if cmdTargetArg(sendPacketLoopBL, sendRTPOverTCPStart)!=BinArg(sendPacketLoopBL):
    print "BUG! cmdTargetArg inconsistent with cmdTargetOffset!"
if ArgToBin(cmdTargetArg(sendPacketLoopBL, sendRTPOverTCPStart)) != fw[sendPacketLoopBL:sendPacketLoopBL+3]:
    print "BUG! ArgToBin inconsistent with cmdTargetOffset!"

### 5. Find next two printfs
printf1 = sendPacketLoopBL+4
while printf1 < sendPacketEnd:
    if fw[printf1+3]=="\xEB":
        printfStart = cmdTargetOffset(printf1)
        break
    printf1 += 4
printf1 += 4
printf2 = printf1 + 4
while printf2 < sendPacketEnd:
    if fw[printf2+3]=="\xEB":
        if cmdTargetOffset(printf2) != printfStart:
            print "ERROR! After loop not two printfs!"
        break
    printf2 += 4
printf2 += 4
if (printf1-sendPacketLoop)/4-7 != 5:
    print "WARN! First printf not 5 instructions"
if (printf1-sendPacketLoop)/4-7 > 5:
    printf2 = printf1 # no need to cleanup 2nd printf

### 6. Generate new loop body
PatchSendPacket = ""

## 6.1. LDR R0, Socket(Rx#8)
ldrSock = "\x08\x00"+fw[sendPacketLoopNext+2]+"\xE5"
PatchSendPacket += ldrSock

## 6.2. BL makeSocketBlocking
tgtSocketBlock = cmdTargetArg(sendPacketLoop+len(PatchSendPacket), makeBlock)
PatchSendPacket += ArgToBin(tgtSocketBlock)+"\xEB"

## 6.3. Copy 4 MOVs
PatchSendPacket += fw[sendPacketLoop:sendPacketLoopBL]

## 6.4. BL sendRTPOverTCP
tgtSendRTPOverTCP = cmdTargetArg(sendPacketLoop+len(PatchSendPacket), sendRTPOverTCPStart)
PatchSendPacket += ArgToBin(tgtSendRTPOverTCP)+"\xEB"

## 6.5. STMFD   SP!, {R0}
PatchSendPacket += "\x01\x00\x2D\xE9"

## 6.6. LDR R0, Socket
PatchSendPacket += ldrSock

## 6.7. BL makeSocketNonBlocking
tgtSocketNonBlock = cmdTargetArg(sendPacketLoop+len(PatchSendPacket), makeNonBlock)
PatchSendPacket += ArgToBin(tgtSocketNonBlock)+"\xEB"

## 6.8. LDMFD   SP!, {R0}
PatchSendPacket += "\x01\x00\xBD\xE8"

## 6.9. CMP     R0, #0
PatchSendPacket += "\x00\x00\x50\xE3"

## 6.A. BGE     loopNext
tgtLoopNext = cmdTargetArg(sendPacketLoop+len(PatchSendPacket), sendPacketLoopNext)
PatchSendPacket += ArgToBin(tgtLoopNext)+"\xAA"

## 6.B. Fill up to printf2 with NOPs
Nops = (printf2 - (sendPacketLoop + len(PatchSendPacket))) / 4
PatchSendPacket += "\x00\x00\xA0\xE1" * Nops

## 6.C. Save generated patch
patches.append( (sendPacketLoop, PatchSendPacket) )
print "Successfully patched"

### FIN: save patched file
if True:
    f = open(fname+".fixed", "w+b")
    patches.sort()
    last = 0
    for p in patches:
        f.write( fw[last:p[0]] )
        f.write( p[1] )
        last = p[0]+len(p[1])
    f.write(fw[last:])
    f.close()

