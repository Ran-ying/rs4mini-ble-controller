#!/usr/bin/env python3
"""Six-bank gimbal enum references and conservative literal packet candidates.

No vendor execution, DUML construction, SDK dependency or hardware access.
"""
import argparse,hashlib,json,re
from pathlib import Path
from ronin_static import APK_SHA256
from ronin_save_trace import BANKS
from ronin_subscription_trace import constructor_records
ENUM='Ldji/midware/data/config/P3/CmdIdGimbal$CmdIdType;'
CMDSET='Ldji/midware/data/config/P3/CmdSet;'
PACK='Ldji/midware/data/packages/P3/SendPack;'
EXCLUDED={'FocusControl','NotiFyCameraId','Other'}
HYPOTHESIZED_ONOFF_CLASS='Ldji/midware/data/model/P3/DataGimbalSetOnOrOff;'


def enum_reference(op,text,names):
    if op not in ('sget-object','sput-object'):return None
    match=re.search(re.escape(ENUM)+r'->([A-Za-z0-9_$]+) ',text)
    return match[1] if match and match[1] in names else None


def literal_packet_candidates(operations,known_ids,gimbal_value=4):
    """Syntactic candidates only; branches reset state, no full CFG/try analysis."""
    registers={};packets={};pending=None;found=[]
    for offset,(op,text) in enumerate(operations):
        args=text.split(', ')
        if op.startswith(('if-','goto','return','throw')) or 'switch' in op:
            registers.clear();packets.clear();pending=None;continue
        if op.startswith('invoke-'):
            pending=None
            if CMDSET+'->value()I' in text and registers.get(args[0])==('gimbal',gimbal_value):pending=('literal',gimbal_value)
            continue
        if op.startswith('move-result'):
            registers.pop(args[0],None)
            if 'wide' in op and re.fullmatch(r'v\d+',args[0]):registers.pop('v'+str(int(args[0][1:])+1),None)
            if pending is not None and op=='move-result':registers[args[0]]=pending
            pending=None;continue
        pending=None
        if op=='iput' and len(args)==3 and args[2] in (PACK+'->cmdId I',PACK+'->cmdSet I'):
            packet=registers.get(args[1]);value=registers.get(args[0])
            if not packet or packet[0]!='packet':continue
            fields=packets.setdefault(packet[1],{});key='cmdId' if '->cmdId ' in args[2] else 'cmdSet'
            fields.pop(key,None)
            if value and value[0]=='literal':fields[key]=value[1]
            if fields.get('cmdSet')==gimbal_value and fields.get('cmdId') in known_ids:
                found.append(dict(instructionIndex=offset,packetCreationInstructionIndex=packet[1],commandId=fields['cmdId']))
            continue
        if op.startswith(('move-wide','const-wide')):
            registers.pop(args[0],None)
            if re.fullmatch(r'v\d+',args[0]):registers.pop('v'+str(int(args[0][1:])+1),None)
        elif op.startswith('move') and len(args)==2:
            source=registers.get(args[1]);registers.pop(args[0],None)
            if source is not None:registers[args[0]]=source
        elif op in ('const/4','const/16','const'):
            registers.pop(args[0],None)
            if len(args)==2 and re.fullmatch(r'-?\d+',args[1]):registers[args[0]]=('literal',int(args[1]))
        elif op=='new-instance':
            registers.pop(args[0],None)
            if len(args)==2 and args[1]==PACK:registers[args[0]]=('packet',offset)
        elif op=='sget-object':
            registers.pop(args[0],None)
            if CMDSET+'->GIMBAL '+CMDSET in text:registers[args[0]]=('gimbal',gimbal_value)
        elif op.startswith(('const','iget','aget','sget','new','check-cast','array-length','instance-of','add-','sub-','mul-','div-','and-','or-','xor-','shl-','shr-','ushr-','int-to-','long-to-','float-to-','double-to-','neg-','not-','cmp')):
            registers.pop(args[0],None)
        elif re.fullmatch(r'v\d+',args[0]) and not op.startswith(('iput','sput','aput','monitor-','fill-array-data')):
            registers.pop(args[0],None)
    return found


def gimbal_command_set_value(operations):
    registers={}
    for op,text in operations:
        args=text.split(', ')
        if op.startswith('if-') or op.startswith('goto') or 'switch' in op:raise ValueError('unsupported CmdSet control flow')
        if op.startswith('const-string'):registers[args[0]]=args[1]
        elif op in ('const/4','const/16','const'):registers[args[0]]=int(args[1])
        elif op=='new-instance':registers[args[0]]=('instance',args[1])
        elif op.startswith('invoke-direct') and CMDSET+'-><init>(' in text:
            raw=text.split(', '+CMDSET)[0];regs=re.findall(r'v\d+',raw)
            if ' ... ' in raw:regs=['v%d'%i for i in range(int(regs[0][1:]),int(regs[-1][1:])+1)]
            values=[registers.get(r) for r in regs[1:]]
            if values and values[0]=='GIMBAL':
                if len(values)!=4 or type(values[1]) is not int or type(values[2]) is not int or values[3]!=('instance','Ldji/midware/data/config/P3/CmdIdGimbal;'):raise ValueError('unresolved GIMBAL CmdSet constructor')
                return values[2]
        elif op.startswith(('move','iget','sget','aget')):registers.pop(args[0],None)
    raise ValueError('missing GIMBAL command set')


def scan(apk,bank_dir):
    if hashlib.sha256(apk.read_bytes()).hexdigest()!=APK_SHA256:raise ValueError('APK hash mismatch')
    images=[]
    for bank,pin in BANKS.items():
        raw=(bank_dir/('business-%02d-code-restored.dex'%bank)).read_bytes()
        if hashlib.sha256(raw).hexdigest()!=pin:raise ValueError('restored bank hash mismatch: %02d'%bank)
        images.append((bank,raw))
    from loguru import logger
    logger.disable('androguard')
    from androguard.core.dex import DEX
    sdk=DEX(next(raw for bank,raw in images if bank==5));classes={c.get_name():c for c in sdk.get_classes()}
    def get(owner,name,descriptor=None):
        ms=[m for m in classes[owner].get_methods() if m.get_name()==name and (descriptor is None or m.get_descriptor()==descriptor)]
        if len(ms)!=1:raise ValueError('ambiguous command enum method')
        return ms[0]
    def ops(m):return [(i.get_name(),i.get_output()) for i in m.get_instructions()]
    def fingerprint(m,bank):return dict(segment=bank,className=m.get_class_name(),method=m.get_name(),descriptor=m.get_descriptor(),codeOffset=m.get_code_off(),instructionSha256=hashlib.sha256(m.get_code().get_bc().get_raw()).hexdigest())
    enum_method=get(ENUM,'<clinit>');entries=constructor_records(ops(enum_method),ENUM)
    targets={name:r for name,r in entries.items() if name not in EXCLUDED}
    if len(targets)!=40 or targets['SetOnOrOff']['arguments']!=['SetOnOrOff',5,13]:raise ValueError('non-camera command inventory changed')
    cmdset_method=get(CMDSET,'<clinit>');gimbal=gimbal_command_set_value(ops(cmdset_method))
    if gimbal!=4:raise ValueError('gimbal command set changed')
    onoff=targets['SetOnOrOff'];ctor=get(ENUM,'<init>',onoff['descriptor'])
    if any('->cls ' in text or '->dataBase ' in text for _,text in ops(ctor)):raise ValueError('short command constructor now binds a data class')
    known_ids={r['arguments'][2] for r in targets.values()};rows=[];methods=[];guessed=[]
    for bank,raw in images:
        dex=sdk if bank==5 else DEX(raw);class_list=dex.get_classes();count=0;instructions=0
        for c in class_list:
            if c.get_name()==HYPOTHESIZED_ONOFF_CLASS:guessed.append(bank)
            for m in c.get_methods():
                if not m.get_code():continue
                count+=1;operations=ops(m);instructions+=len(operations);refs=[]
                for index,(op,text) in enumerate(operations):
                    name=enum_reference(op,text,targets)
                    if name:refs.append(dict(name=name,instructionIndex=index,kind='enum-self-reference' if c.get_name()==ENUM else 'external-enum-reference'))
                candidates=literal_packet_candidates(operations,known_ids,gimbal)
                if refs or candidates:methods.append(dict(fingerprint(m,bank),enumReferences=refs,literalPacketCandidates=candidates))
        rows.append(dict(segment=bank,derivedSha256=BANKS[bank],methodWithCodeCount=count,instructionCount=instructions))
        print('bank%02d: %d methods with code, %d instructions'%(bank,count,instructions),flush=True)
    commands=[]
    for name,entry in targets.items():
        external=[i for i,m in enumerate(methods) if any(r['name']==name and r['kind']=='external-enum-reference' for r in m['enumReferences'])]
        commands.append(dict(name=name,ordinal=entry['arguments'][1],commandId=entry['arguments'][2],constructorDescriptor=entry['descriptor'],hasExplicitClassArgument='Ljava/lang/Class;' in entry['descriptor'],externalReferenceMethodIndexes=external))
    onoff_enum=[i for i,m in enumerate(methods) if any(r['name']=='SetOnOrOff' and r['kind']=='external-enum-reference' for r in m['enumReferences'])]
    onoff_literal=[i for i,m in enumerate(methods) if any(r['commandId']==13 for r in m['literalPacketCandidates'])]
    return dict(schemaVersion=1,apkSha256=APK_SHA256,appCodeExecuted=False,targetDeviceVerified=False,wholeProtocolRecovered=False,wholeAppRecovered=False,allScannedBodiesRecovered=False,indirectDispatchResolved=False,literalResolutionComplete=False,literalCandidatesProveSend=False,researchToolProvidesSdkInterface=False,
                scannedBanks=list(BANKS),unrestoredBanks=[1,7],excludedNames=sorted(EXCLUDED),gimbalCommandSet=gimbal,
                enumSourceMethods=[fingerprint(enum_method,5),fingerprint(cmdset_method,5),fingerprint(ctor,5)],commands=commands,banks=rows,methods=methods,
                onOff=dict(commandId=13,enumOrdinal=5,constructorDescriptor=onoff['descriptor'],hasExplicitClassArgument=False,hypothesizedClassName=HYPOTHESIZED_ONOFF_CLASS,hypothesizedClassDefinitionBanks=guessed,externalEnumMethodIndexes=onoff_enum,literalCandidateMethodIndexes=onoff_literal,payloadRecovered=False,hg724CallPathEstablished=False),
                limits=['Only static field references to 40 non-camera enum entries are inventoried; enum use is not execution proof.','Literal SendPack candidates use linear syntax with branch resets, not complete CFG/exception/alias/dataflow analysis.','Missing banks1/7, protected bodies, reflection/dynamic/native paths and firmware-only commands remain unresolved.','No guessed class name or constructor class argument is treated as an outgoing implementation mapping.'])


def main():
    p=argparse.ArgumentParser(description=__doc__)
    for name in ('apk','bank-dir','output'):p.add_argument('--'+name,type=Path,required=True)
    a=p.parse_args();r=scan(a.apk,a.bank_dir);a.output.write_text(json.dumps(r,indent=2)+'\n');print('%d command entries; %d referencing/candidate methods; 0D external refs=%d literal candidates=%d'%(len(r['commands']),len(r['methods']),len(r['onOff']['externalEnumMethodIndexes']),len(r['onOff']['literalCandidateMethodIndexes'])))
if __name__=='__main__':main()
