#!/usr/bin/env python3
"""Audit unresolved banks' intact method slots and code backups, without rebuilding DEX."""
import argparse,hashlib,json,struct,zipfile
from pathlib import Path
from ronin_static import APK_SHA256,maps_in,uleb
from ronin_code_restore import backup_table,encoded_methods,code_item_length,checked
PREFIX=0x20000
TARGETS=(1,7)
WIDTHS={0:112,1:4,2:4,3:12,4:8,5:8,6:32}


def table_damage(items,prefix=PREFIX):
    rows=[]
    for kind,width in WIDTHS.items():
        count,offset=items[kind];length=count*width
        damaged=max(0,min(offset+length,prefix)-offset)
        rows.append(dict(mapType=kind,count=count,offset=offset,entryBytes=width,bytesInsideObservedDamagedPrefix=damaged,entriesIntersectingPrefix=(damaged+width-1)//width))
    return rows


def require_disjoint(spans):
    rows=sorted(spans)
    if any(a[1]>b[0] for a,b in zip(rows,rows[1:])):raise ValueError('overlapping code destinations')


def audit_bank(image,items,bank):
    """Only numeric indices and intact regions. Never infer strings, types or prototypes."""
    if len(image)!=bank['originalSize']:raise ValueError('original region size mismatch')
    for kind in (5,6):
        count,offset=items[kind]
        if offset<PREFIX:raise ValueError('required metadata intersects damaged prefix')
        checked(image,offset,count*WIDTHS[kind])
    type_count=items[2][0];proto_count=items[3][0];string_count=items[1][0]
    method_count,method_off=items[5];class_count,class_off=items[6]
    code_start=items[0x2001][1];code_end=items[0x2002][1]
    class_data_start=items[0x2000][1]
    if not PREFIX<=class_data_start<code_start<code_end<=len(image):raise ValueError('unsafe class-data/code region')
    owners={};class_types=[];seen_data=set();data_spans=[]
    for i in range(class_count):
        typ=struct.unpack_from('<I',image,class_off+i*32)[0]
        if typ>=type_count or typ in class_types:raise ValueError('invalid or duplicate class type index')
        class_types.append(typ)
        data_off=struct.unpack_from('<I',image,class_off+i*32+24)[0]
        if not data_off:continue
        if not class_data_start<=data_off<code_start or data_off in seen_data:raise ValueError('class data outside intact mapped region')
        seen_data.add(data_off);pos=data_off;counts=[]
        for _ in range(4):n,pos=uleb(image,pos);counts.append(n)
        for _ in range(counts[0]+counts[1]):_,pos=uleb(image,pos);_,pos=uleb(image,pos)
        for count in counts[2:]:
            index=0
            for _ in range(count):
                delta,pos=uleb(image,pos);index+=delta;_,pos=uleb(image,pos);slot=pos;_,pos=uleb(image,pos)
                if index>=method_count or slot in owners:raise ValueError('invalid class-data method slot')
                owners[slot]=typ
        if pos>code_start:raise ValueError('class data extends into code region')
        data_spans.append((data_off,pos))
    require_disjoint(data_spans)
    if len(seen_data)!=items[0x2000][0]:raise ValueError('class-data map count mismatch')
    method_rows=[]
    for i in range(method_count):
        owner,proto,name=struct.unpack_from('<HHI',image,method_off+i*8)
        if owner>=type_count or proto>=proto_count or name>=string_count:raise ValueError('method-id numeric index outside declared table')
        method_rows.append((owner,name,proto))
    if method_rows!=sorted(method_rows) or len(set(method_rows))!=len(method_rows):raise ValueError('method-id ordering/uniqueness mismatch')
    # Count/offset shim solely for the existing bounded class-data reader.
    # No DEX magic, type/prototype/string repairs, checksums or derived DEX output.
    scratch=bytearray(image)
    struct.pack_into('<I',scratch,88,method_count);struct.pack_into('<II',scratch,96,class_count,class_off)
    slots=encoded_methods(scratch)
    if set(slots)!=set(owners):raise ValueError('independent slot readers disagree')
    if len({r['methodIndex'] for r in slots.values()})!=len(slots):raise ValueError('duplicate encoded method index')
    for slot,method in slots.items():
        if method_rows[method['methodIndex']][0]!=owners[slot]:raise ValueError('method-id/class-data owner index mismatch')
    records=[];spans=[];seen_slots=set()
    for row in bank['rows']:
        slot=row['slot']
        if slot in seen_slots or slot not in slots:raise ValueError('backup has no unique exact method slot')
        seen_slots.add(slot);method=slots[slot];offset=method['codeOffset'];size=row['size']
        if offset%4 or offset<code_start or offset+size>code_end:raise ValueError('backup destination outside intact code region')
        current=checked(image,offset,size);original=row['code']
        if len(original)!=size or code_item_length(current,0,type_count)!=size or code_item_length(original,0,type_count)!=size or current[12:16]!=original[12:16]:raise ValueError('code footprint mismatch')
        spans.append((offset,offset+size))
        records.append(dict(methodIndex=method['methodIndex'],ownerTypeIndex=owners[slot],slot=slot,codeOffset=offset,size=size,dataOffset=row['dataOffset'],currentSha256=hashlib.sha256(current).hexdigest(),backupSha256=hashlib.sha256(original).hexdigest()))
    require_disjoint(spans)
    records.sort(key=lambda r:r['slot'])
    digest=hashlib.sha256(json.dumps(records,sort_keys=True,separators=(',',':')).encode()).hexdigest()
    return dict(originalSize=len(image),intactMethodIds=method_count,intactClassDefinitions=class_count,intactClassDataItems=len(seen_data),numericMethodSlots=len(slots),matchedBackupCodeItems=len(records),matchedCodeBytes=sum(r['size'] for r in records),slotRecordSha256=digest,allBackupSlotsMatched=True,methodOwnerIndicesConsistent=True,currentAndBackupFootprintsMatch=True,destinationsNonOverlapping=True,tableDamage=table_damage(items),namedMetadataRestored=False,stringOrderIndependentlyCorroborated=False,typeIdentityRecovered=False,prototypeIdentityRecovered=False,parseableDexProduced=False),records


def audit_apk(apk):
    if hashlib.sha256(apk.read_bytes()).hexdigest()!=APK_SHA256:raise ValueError('APK hash mismatch')
    with zipfile.ZipFile(apk) as z:data=z.read('classes.dex')
    maps=maps_in(data)
    if len(maps)!=8:raise ValueError('expected eight hidden maps')
    banks=[];full={}
    for b in TARGETS:
        mapping=maps[b];base=mapping['base'];limit=maps[b+1]['base'] if b+1<len(maps) else len(data)
        name=('classes%d.dex.dgc2'%(b+1)).encode();bank=backup_table(data,base,limit,name)
        summary,records=audit_bank(checked(data,base,bank['originalSize']),mapping['items'],bank)
        banks.append(dict(segment=b,backupName=name.decode(),bankSha256=bank['bankSha256'],**summary));full[b]=records
    return dict(schemaVersion=1,apkSha256=APK_SHA256,appCodeExecuted=False,liveUiExecuted=False,targetDeviceVerified=False,wholeAppRecovered=False,wholeProtocolRecovered=False,researchToolProvidesSdkInterface=False,sdkSendAdded=False,sdkReceiveAdded=False,observedDamagedPrefixBytes=PREFIX,banks=banks,additionalBackupSlotsAudited=sum(r['matchedBackupCodeItems'] for r in banks),namedMetadataStillUnresolvedBanks=list(TARGETS),existingSixRestoredDexViewsChanged=False,remaining=['Matching numeric method slots and code footprints does not restore string/type/prototype identities.','01 type-id prefix and07 type/prototype/field regions intersect the observed damaged prefix.','No parseable/rebuilt DEX is emitted for these banks; existing six-bank named caller scans retain their scope.','These are source-file code backups, not target BLE inventory, routing or hardware verification.']),full


def main():
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--apk',type=Path,required=True);p.add_argument('--output',type=Path,required=True);p.add_argument('--slots-dir',type=Path)
    a=p.parse_args();summary,records=audit_apk(a.apk)
    if a.slots_dir:
        a.slots_dir.mkdir(parents=True,exist_ok=True)
        for b,rows in records.items():(a.slots_dir/('bank-%02d-code-slot-records.json'%b)).write_text(json.dumps(rows,indent=2)+'\n')
    a.output.write_text(json.dumps(summary,ensure_ascii=False,indent=2)+'\n');print('%d additional exact backup slots audited; banks01/07 named metadata unresolved; no DEX emitted.'%summary['additionalBackupSlotsAudited'])
if __name__=='__main__':main()
