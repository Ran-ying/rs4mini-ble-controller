#!/usr/bin/env python3
"""Restore all eight pinned DEX views using an independently implemented SM4 transform.

Only file parsing and owned Python cryptography run; no vendor instructions, JNI,
App, UI or hardware execution. Native analysis views are never emitted by this tool.
"""
import argparse,hashlib,json,struct,zipfile,zlib
from pathlib import Path
from ronin_static import APK_SHA256,maps_in
from ronin_code_restore import backup_table,restore_image,checked
from ronin_save_trace import BANKS as LEGACY_BANKS
PREFIX_BYTES=0x20000
NATIVE_PATH='lib/arm64-v8a/libAppGuard.so'
NATIVE_SHA256='fe1b0224cb5011efef6c8f4331bd0f3e13f49a38629f9ad48ae075bf60840ecb'
PACKAGE=b'com.dji.ronin'
EMBEDDED_OFFSET=0x18000
XOR_BYTE=0xba
FK=(0xa3b1bac6,0x56aa3350,0x677d9197,0xb27022dc)
PREFIX_BANKS={
0:'2229f1f19aa8fe8d819c7b3cecbd844928da817e2bc9cfddfda1c0e120e4cc59',
1:'0083e9f9e0e615602470ea148cfd581a0c7413a012ef5494b613242d55754f99',
2:'f75800c8edb40823c72afdd0eee575135e995440da9a5fd9bfb3e5b3e9e6fe68',
3:'861be662ee36ce3b195c0c1aa179642e34793df3a88e933fa1dfe2a7202a9528',
4:'2fd9aa02f5c9f4217e7e6ef75d724a1ce64efa7c1f365ddb20c93be1fef85f77',
5:'f78b34474816ca253b4133bdbd79ebcbf725f52d58ac00b63f921ff7082470d2',
6:'4da9764901f753190e0c88b5a142a4f9cf1eed9b1b9214bdf97a21f00edcb990',
7:'3fc2c4adccd59794f5c28b898d577ed414758875cadb7ce7f6782ffd5b64b723'}


def rol(word,shift):
    return ((word<<shift)|(word>>(32-shift)))&0xffffffff


def tau(word,sbox):
    return (sbox[word>>24]<<24)|(sbox[(word>>16)&255]<<16)|(sbox[(word>>8)&255]<<8)|sbox[word&255]


def round_keys(key,sbox,constants):
    if not isinstance(key,bytes) or len(key)!=16 or len(sbox)!=256 or set(sbox)!=set(range(256)) or len(constants)!=32:raise ValueError('SM4 key/table dimensions')
    words=[x^y for x,y in zip(struct.unpack('>4I',key),FK)]
    for i,ck in enumerate(constants):
        t=tau(words[i+1]^words[i+2]^words[i+3]^ck,sbox)
        words.append(words[i]^t^rol(t,13)^rol(t,23))
    return tuple(words[4:])


def decrypt_ecb(data,key,sbox,constants):
    if not isinstance(data,bytes) or not data or len(data)%16:raise ValueError('nonempty whole SM4 blocks required')
    keys=round_keys(key,sbox,constants)[::-1]
    tables=[]
    for shift in (24,16,8,0):
        table=[]
        for b in sbox:
            t=b<<shift;table.append(t^rol(t,2)^rol(t,10)^rol(t,18)^rol(t,24))
        tables.append(table)
    a,b,c,d=tables;out=bytearray(len(data))
    for off in range(0,len(data),16):
        x0,x1,x2,x3=struct.unpack_from('>4I',data,off)
        for rk in keys:
            t=x1^x2^x3^rk
            x0,x1,x2,x3=x1,x2,x3,x0^a[t>>24]^b[(t>>16)&255]^c[(t>>8)&255]^d[t&255]
        struct.pack_into('>4I',out,off,x3,x2,x1,x0)
    return bytes(out)


def native_material(raw):
    if hashlib.sha256(raw).hexdigest()!=NATIVE_SHA256:raise ValueError('pinned AppGuard library hash mismatch')
    if checked(raw,0xc010,8)!=b'd!a@t#a$' or struct.unpack_from('<I',raw,0xc020)[0]!=EMBEDDED_OFFSET:raise ValueError('pinned native wrapper structure mismatch')
    body=bytes(v^XOR_BYTE for v in raw[EMBEDDED_OFFSET:])
    # Header64 remains outside the candidate claim; verify intact program/dynamic structures.
    first=struct.unpack_from('<II6Q',body,64)
    if first!=(1,5,0,0,0,0xee5fc,0xee5fc,0x4000):raise ValueError('embedded load segment mismatch')
    if b'com/AppGuard/AppGuard/BDOVL\0' not in body or b'JNI_OnLoad\0' not in body:raise ValueError('embedded loader strings missing')
    sbox=checked(body,0xcdf88,256);ck=struct.unpack('<32I',checked(body,0xcdf08,128))
    expected=tuple(sum((((4*i+j)*7)&255)<<(24-8*j) for j in range(4)) for i in range(32))
    if tuple(ck)!=expected or sbox[:16]!=bytes.fromhex('d690e9fecce13db716b614c228fb2c05'):raise ValueError('SM4 table structure mismatch')
    seed=checked(body,0xca9b0,16);key=bytes(v^(PACKAGE[i] if i<len(PACKAGE) else 0) for i,v in enumerate(seed))
    regions=[]
    for name,offset,size in [('outerXor',0x8cec,0xbc),('prefixDispatch',0x213fc,0x98),('keySchedule',0x26bbc,0x14c),('decryptRoundEntry',0x26d08,0x100)]:
        source=raw if name=='outerXor' else body
        regions.append(dict(name=name,offset=offset,size=size,sha256=hashlib.sha256(checked(source,offset,size)).hexdigest()))
    return key,sbox,ck,dict(path=NATIVE_PATH,sha256=NATIVE_SHA256,embeddedOffset=EMBEDDED_OFFSET,outerXorByte=XOR_BYTE,embeddedDataViewSha256=hashlib.sha256(body).hexdigest(),nativeElfHeaderRecovered=False,nativeLibraryExecuted=False,sourcePackage=PACKAGE.decode(),derivedKeySha256=hashlib.sha256(key).hexdigest(),constantTableSha256=hashlib.sha256(sbox+struct.pack('<32I',*ck)).hexdigest(),selectedRegionFingerprints=regions)


def check_plain_header(image,mapping,bank):
    if image[:8]!=b'dex\n039\0':raise ValueError('decrypted DEX magic mismatch')
    declared,header,endian=struct.unpack_from('<3I',image,32)
    if header!=112 or endian!=0x12345678 or not bank['originalSize']<=declared<=len(image):raise ValueError('decrypted DEX header bounds mismatch')
    if struct.unpack_from('<I',image,52)[0]!=mapping['mapOffset']:raise ValueError('decrypted map pointer mismatch')
    for kind,off in [(1,56),(2,64),(3,72),(4,80),(5,88),(6,96)]:
        if struct.unpack_from('<II',image,off)!=mapping['items'][kind]:raise ValueError('decrypted id-table map mismatch')
    data_size,data_off=struct.unpack_from('<II',image,104)
    if data_off!=mapping['items'][0x1000][1] or data_size+data_off!=bank['originalSize']:raise ValueError('decrypted original data bounds mismatch')
    image=bytes(image[:declared]);source_adler=struct.unpack_from('<I',image,8)[0]
    if source_adler!=zlib.adler32(image[12:])&0xffffffff:raise ValueError('decrypted protected-container Adler32 mismatch')
    return image,dict(declaredContainerSize=declared,sourceProtectedContainerAdler32Matched=True,sourceHeaderSha1MatchesProtectedContainer=image[12:32]==hashlib.sha1(image[32:]).digest(),decryptedPrefixSha256=hashlib.sha256(image[:PREFIX_BYTES]).hexdigest())


def restore_apk(apk,output,baseline_dir):
    if hashlib.sha256(apk.read_bytes()).hexdigest()!=APK_SHA256:raise ValueError('APK hash mismatch')
    with zipfile.ZipFile(apk) as z:data=z.read('classes.dex');native=z.read(NATIVE_PATH)
    key,sbox,ck,source=native_material(native);maps=maps_in(data)
    if len(maps)!=8:raise ValueError('expected eight hidden maps')
    rows=[];pending=[]
    for i,m in enumerate(maps):
        base=m['base'];limit=maps[i+1]['base'] if i+1<len(maps) else len(data);name=('classes%s.dex.dgc2'%('' if i==0 else i+1)).encode();bank=backup_table(data,base,limit,name)
        image=bytearray(data[base:limit]);image[:PREFIX_BYTES]=decrypt_ecb(bytes(image[:PREFIX_BYTES]),key,sbox,ck);plain,checks=check_plain_header(image,m,bank)
        restored,records=restore_image(plain,bank);digest=hashlib.sha256(restored).hexdigest()
        if digest!=PREFIX_BANKS[i]:raise ValueError('independent normalized DEX view hash mismatch')
        old_match=None
        if i in LEGACY_BANKS:
            old=(baseline_dir/('business-%02d-code-restored.dex'%i)).read_bytes()
            if hashlib.sha256(old).hexdigest()!=LEGACY_BANKS[i]:raise ValueError('legacy six-bank view hash mismatch')
            old_match=old[112:bank['originalSize']]==restored[112:bank['originalSize']]
            if not old_match:raise ValueError('legacy named metadata/code bytes differ')
        filename='business-%02d-prefix-code-restored.dex'%i;pending.append((filename,restored))
        rows.append(dict(segment=i,backupName=name.decode(),bankSha256=bank['bankSha256'],originalSize=bank['originalSize'],restoredBackupCodeItems=len(records),derivedFile=filename,derivedSha256=digest,stringIds=m['items'][1][0],typeIds=m['items'][2][0],protoIds=m['items'][3][0],classDefinitions=m['items'][6][0],legacySemanticBytes112ToOriginalSizeMatch=old_match,normalizedViewChecksumsRegenerated=True,**checks))
    output.mkdir(parents=True,exist_ok=True)
    for filename,raw in pending:(output/filename).write_bytes(raw)
    report=dict(schemaVersion=1,apkSha256=APK_SHA256,appCodeExecuted=False,liveUiExecuted=False,nativeLibraryExecuted=False,targetDeviceVerified=False,wholeAppRecovered=False,wholeProtocolRecovered=False,researchToolProvidesSdkInterface=False,sdkSendAdded=False,sdkReceiveAdded=False,sourceNative=source,transform='owned SM4-ECB decrypt of first min(0x20000,size) whole blocks; fixed banks exceed 0x20000',namedDexViewsRecovered=8,restoredBackupCodeItems=sum(r['restoredBackupCodeItems'] for r in rows),previousSixFilesModified=False,legacyCallerEvidenceScopeAutomaticallyExpanded=False,banks=rows,remaining=['Normalized view checksums do not establish byte-for-byte identity with an original unprotected vendor DEX.','Source header SHA1 does not match protected container; preserve this fact rather than calling it verified.','New named views do not prove full App/native/VM or protocol inventory recovery.','Prior six-bank caller audits retain historical scope; new bank01/07 references require separate semantic and model review.'])
    (output/'prefix-restoration.json').write_text(json.dumps(report,ensure_ascii=False,indent=2)+'\n');return report


def inspect_new_banks(directory):
    # Import optional parser only after pinned file hashes have all passed.
    images=[]
    for bank in (1,7):
        raw=(directory/('business-%02d-prefix-code-restored.dex'%bank)).read_bytes()
        if hashlib.sha256(raw).hexdigest()!=PREFIX_BANKS[bank]:raise ValueError('new named DEX hash mismatch')
        images.append((bank,raw))
    from loguru import logger
    logger.disable('androguard')
    from androguard.core.dex import DEX
    import re
    rows=[];callers=[]
    prefixes=('Ldji/midware/data/model/P3/DataGimbal','Ldji/sdksharedlib/hardware/abstractions/gimbal/','Ldji/midware/data/config/P3/CmdIdGimbal')
    for bank,raw in images:
        d=DEX(raw);classes=d.get_classes();method_count=0;instruction_methods=0;refs_count=0
        for c in classes:
            c.get_superclassname()
            for m in c.get_methods():
                method_count+=1;m.get_name();m.get_descriptor()
                if not m.get_code():continue
                instruction_methods+=1;refs=[]
                for i in m.get_instructions():
                    if not i.get_name().startswith('invoke-'):continue
                    match=re.search(r'(L[^\s,]+;)->([^\s(]+)\(',i.get_output())
                    if match and match.group(1).startswith(prefixes):refs.append(dict(className=match.group(1),method=match.group(2)))
                if refs:
                    refs_count+=len(refs);callers.append(dict(bank=bank,className=c.get_name(),method=m.get_name(),descriptor=m.get_descriptor(),codeOffset=m.get_code_off(),instructionSha256=hashlib.sha256(m.get_code().get_bc().get_raw()).hexdigest(),references=refs))
        rows.append(dict(segment=bank,classDefinitions=len(classes),declaredMethods=method_count,instructionMethodsParsed=instruction_methods,gimbalDirectInvocations=refs_count))
    return dict(schemaVersion=1,apkSha256=APK_SHA256,bankSha256={str(b):PREFIX_BANKS[b] for b in (1,7)},appCodeExecuted=False,targetDeviceVerified=False,wholeProtocolRecovered=False,researchToolProvidesSdkInterface=False,sdkSendAdded=False,sdkReceiveAdded=False,modelPathsVerified=False,banks=rows,directCallerMethods=callers,cameraApisAdded=False,activationCommandsAdded=False)


def main():
    p=argparse.ArgumentParser(description=__doc__)
    for name in ('apk','output','baseline-dir'):p.add_argument('--'+name,type=Path,required=True)
    p.add_argument('--inspect-new-banks',action='store_true');a=p.parse_args();r=restore_apk(a.apk,a.output,a.baseline_dir)
    if a.inspect_new_banks:(a.output/'new-bank-callers.json').write_text(json.dumps(inspect_new_banks(a.output),ensure_ascii=False,indent=2)+'\n')
    print('%d named DEX views; %d exact code backups; native/App/hardware not executed.'%(r['namedDexViewsRecovered'],r['restoredBackupCodeItems']))
if __name__=='__main__':main()
