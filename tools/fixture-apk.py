#!/usr/bin/env python3
"""Make an unsigned previous-version fixture from the CI APK; never distribute this."""
import struct
import sys
import zipfile

def previous_manifest(data):
    data=bytearray(data)
    offset=8
    strings=[]
    changed=False
    while offset<len(data):
        kind,header,size=struct.unpack_from('<HHI',data,offset)
        assert size>=header>0
        if kind==1:
            count,_,flags,start=struct.unpack_from('<IIII',data,offset+8)
            def length(pos,utf8):
                if utf8:
                    n=data[pos];return (((n&127)<<8)|data[pos+1],pos+2) if n&128 else (n,pos+1)
                n=struct.unpack_from('<H',data,pos)[0]
                return (((n&32767)<<16)|struct.unpack_from('<H',data,pos+2)[0],pos+4) if n&32768 else (n,pos+2)
            for i in range(count):
                pos=offset+start+struct.unpack_from('<I',data,offset+header+i*4)[0]
                if flags&256:
                    _,pos=length(pos,True);n,pos=length(pos,True)
                    strings.append(bytes(data[pos:pos+n]).decode('utf-8'))
                else:
                    n,pos=length(pos,False);strings.append(bytes(data[pos:pos+n*2]).decode('utf-16le'))
        elif kind==0x102:
            start,stride,count=struct.unpack_from('<HHH',data,offset+24)
            for i in range(count):
                attr=offset+16+start+i*stride
                name=struct.unpack_from('<I',data,attr+4)[0]
                if strings[name]=='versionCode':
                    assert data[attr+15]==0x10
                    code, = struct.unpack_from('<I',data,attr+16)
                    assert code > 0
                    struct.pack_into('<I',data,attr+16,code-1);changed=True
        offset+=size
    assert changed,'versionCode attribute missing'
    return data

with zipfile.ZipFile(sys.argv[1]) as src,zipfile.ZipFile(sys.argv[2],'w') as dst:
    for entry in src.infolist():
        if entry.filename.startswith('META-INF/'):continue
        data=src.read(entry)
        if entry.filename=='AndroidManifest.xml':data=previous_manifest(data)
        dst.writestr(entry,data)
