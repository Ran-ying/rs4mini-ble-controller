#!/usr/bin/env python3
"""Audit declared key annotations and source support predicates, without reflection."""
import argparse,hashlib,json
from pathlib import Path
from ronin_static import APK_SHA256
from ronin_command_audit import DERIVED_SHA256

KEY='Ldji/sdksharedlib/keycatalog/extension/Key;'
COMPLEX='Ldji/sdksharedlib/keycatalog/extension/ComplexKey;'
CATALOG='Ldji/sdksharedlib/keycatalog/GimbalKeys;'
BASE='Ldji/sdksharedlib/hardware/abstractions/gimbal/'
TARGET=BASE+'DJIGimbalHG724Abstraction;'
PROPS=('accessType','includedAbstractions','excludedAbstractions','type','types')


def select_source_keys(entries,target,ancestors):
    """Handwritten source KeyInfo model, retaining HashMap selection ambiguity."""
    class_map={};excluded=set();default=None;duplicates=[]
    for index,row in enumerate(entries):
        excluded.update(row.get('excludedAbstractions') or [])
        includes=row.get('includedAbstractions') or []
        if not includes:default=index
        for name in includes:
            if name in class_map:duplicates.append(name)
            else:class_map[name]=index
    for name in excluded:class_map.pop(name,None)
    matches=sorted({index for name,index in class_map.items() if name in ancestors}) if target is not None else []
    candidates=matches if matches else ([default] if default is not None and target is not None else [])
    supported=target is not None and target not in excluded and (default is not None or bool(matches))
    return dict(sourceSupport=supported,exactTargetExcluded=target in excluded,defaultEntryIndex=default,
                getKeyCandidateIndexes=candidates,registrationCandidateIndexes=candidates if supported else [],
                selectionUnambiguous=supported and len(candidates)==1,duplicateIncludedClasses=sorted(set(duplicates)))


def normalize_annotations(annotations,defaults):
    direct=[a for a in annotations if a['typeName']==KEY]
    complex_keys=[a for a in annotations if a['typeName']==COMPLEX]
    if len(direct)>1 or len(complex_keys)>1:raise ValueError('duplicate source annotation types')
    if direct and complex_keys:return [],'both-key-and-complex-invalid-in-source'
    values=direct if direct else (complex_keys[0]['elements'].get('value',[]) if complex_keys else [])
    rows=[]
    for item in values:
        if item['typeName']!=KEY:raise ValueError('unexpected nested key annotation')
        row={k:item['elements'].get(k,defaults.get(k)) for k in PROPS}
        if type(row['accessType']) is not int:raise ValueError('unresolved source access integer')
        for k in ('includedAbstractions','excludedAbstractions'):
            if row[k] is not None and (not isinstance(row[k],list) or any(type(x) is not str for x in row[k])):raise ValueError('unresolved abstraction list')
        rows.append(row)
    return rows,None


def trace(apk,sdk):
    if hashlib.sha256(apk.read_bytes()).hexdigest()!=APK_SHA256:raise ValueError('APK hash mismatch')
    raw=sdk.read_bytes()
    if hashlib.sha256(raw).hexdigest()!=DERIVED_SHA256:raise ValueError('SDK hash mismatch')
    from loguru import logger
    logger.disable('androguard')
    from androguard.core.dex import DEX
    dex=DEX(raw);cm=dex.get_class_manager();classes={c.get_name():c for c in dex.get_classes()};methods={}
    def annotation(a):return dict(typeName=dex.get_cm_type(a.get_type_idx()),elements={dex.get_cm_string(e.get_name_idx()):value(e.get_value()) for e in a.get_elements()})
    def value(v):
        result=v.get_value();kind=v.get_value_type()
        if kind==0x1c:return [value(e) for e in result.get_values()]
        if kind==0x1d:return annotation(result)
        return result
    def annotated_set(offset):return [annotation(o.get_annotation_item().get_annotation()) for o in cm.get_annotation_set_item(offset).get_annotation_off_item()]
    def directory(owner):return cm.get_annotations_directory_item(classes[owner].get_annotations_off())
    def take(owner,name,descriptor=None):
        found=[m for m in classes[owner].get_methods() if m.get_name()==name and (descriptor is None or m.get_descriptor()==descriptor)]
        if len(found)!=1 or not found[0].get_code():raise ValueError('missing or ambiguous key support method '+name)
        m=found[0];methods[(owner,name,m.get_descriptor())]=dict(className=owner,method=name,descriptor=m.get_descriptor(),codeOffset=m.get_code_off(),instructionSha256=hashlib.sha256(m.get_code().get_bc().get_raw()).hexdigest());return [(o.get_name(),o.get_output()) for o in m.get_instructions()]
    def require(ops,token):
        if not any(token in text for _,text in ops):raise ValueError('missing source key rule '+token)
    class_annotations=[annotation(a) for a in classes[KEY]._get_annotation_type_ids()]
    default_container=next(a['elements']['value'] for a in class_annotations if a['typeName']=='Ldalvik/annotation/AnnotationDefault;')
    defaults={k:default_container['elements'].get(k) for k in PROPS}
    if defaults['includedAbstractions']!=[] or defaults['excludedAbstractions']!=[]:raise ValueError('source class-list defaults changed')
    def ancestors(owner):
        seen=set();pending=[owner]
        while pending:
            item=pending.pop()
            if item in seen:continue
            seen.add(item)
            if item in classes:
                c=classes[item];pending.extend(c.get_interfaces());pending.append(c.get_superclassname())
        seen.discard(None);return seen
    target_ancestors=ancestors(TARGET);chain=[];owner=TARGET
    while owner in classes:chain.append(owner);owner=classes[owner].get_superclassname()
    info='Ldji/sdksharedlib/keycatalog/DJISDKCacheKeys$KeyInfo;';utils='Ldji/sdksharedlib/keycatalog/extension/Utils;';hw='Ldji/sdksharedlib/hardware/abstractions/DJISDKCacheHWAbstraction;'
    ctor=take(info,'<init>')
    for token in ('->parseAllKey(','->parseAllClass(','->defaultKey ','->containsKey(','->remove('):require(ctor,token)
    support=take(info,'support');require(support,'->contains(Ljava/lang/Object;)Z');require(support,'->isAssignableFrom(')
    get=take(info,'getKey');require(get,'->defaultKey ');require(get,'->isAssignableFrom(')
    parse=take(utils,'parseAllClass');require(parse,'->newInstance()Ljava/lang/Object;');require(parse,'->getAbstractions()')
    take(utils,'parseAllKey');take('Ldji/sdksharedlib/keycatalog/DJISDKCacheKeys;','getKeyInfoMap')
    add=take(hw,'addCharacteristics','(Ljava/lang/Class; Ljava/lang/Class;)V');require(add,'->support(');require(add,'->getKey(')
    take(hw,'createMethodMap');take(hw,'getMethodsFromSuperClass');take(BASE+'DJIGimbalAbstraction;','initializeComponentCharacteristics')
    annotated_fields={row.get_field_idx():annotated_set(row.get_annotations_off()) for row in directory(CATALOG).get_field_annotations()}
    rows=[];referenced=set()
    for field in classes[CATALOG].get_fields():
        annotations=annotated_fields.get(field.get_field_idx())
        if not annotations:continue
        if field.get_descriptor()!='Ljava/lang/String;' or field.get_access_flags()&9!=9:continue
        entries,invalid=normalize_annotations(annotations,defaults)
        if not entries and invalid is None:continue
        for entry in entries:
            referenced.update(entry.get('includedAbstractions') or []);referenced.update(entry.get('excludedAbstractions') or [])
        literal=field.get_init_value();literal=literal.get_value() if literal is not None else None
        if literal is not None and type(literal) is not str:raise ValueError('non-string key literal')
        rows.append(dict(fieldName=field.get_name(),literalKeyName=literal,entries=entries,invalidAnnotationReason=invalid,**select_source_keys(entries,TARGET,target_ancestors)))
    if any(name not in classes for name in referenced):raise ValueError('unresolved referenced abstraction class')
    group_interface='Ldji/sdksharedlib/keycatalog/extension/IAbstractionGroup;'
    group_refs=sorted(name for name in referenced if group_interface in ancestors(name))
    if group_refs:raise ValueError('group expansion needs separate static body audit; never instantiate groups')
    bindings=[]
    for owner in chain:
        if not classes[owner].get_annotations_off():continue
        by_index={m.get_method_idx():m for m in classes[owner].get_methods()}
        for row in directory(owner).get_method_annotations():
            m=by_index.get(row.get_method_idx())
            if m is None:continue
            for a in annotated_set(row.get_annotations_off()):
                if a['typeName']=='Ldji/sdksharedlib/hardware/abstractions/Action;' and a['elements'].get('value') in ('Rotate','ResetGimbal'):
                    take(owner,m.get_name(),m.get_descriptor());bindings.append(dict(className=owner,method=m.get_name(),descriptor=m.get_descriptor(),action=a['elements']['value']))
    if len(rows)!=223:raise ValueError('declared gimbal key inventory changed')
    return dict(schemaVersion=1,apkSha256=APK_SHA256,sdkSha256=DERIVED_SHA256,appCodeExecuted=False,javaReflectionExecuted=False,targetDeviceVerified=False,wholeProtocolRecovered=False,researchToolProvidesSdkInterface=False,
                scope='Declared public static annotated String fields in GimbalKeys only; not inherited catalog fields or complete BLE inventory',targetClass=TARGET,targetClassChain=chain,defaults=defaults,abstractionGroupReferences=group_refs,declaredFields=rows,selectedActionAnnotations=bindings,methods=list(methods.values()),
                sourceRules=dict(exclusionUsesExactSetContains=True,inclusionUsesAssignableFrom=True,duplicateIncludedClassKeepsFirst=True,lastDefaultKeyWins=True,getKeyUsesHashMapIteration=True,mostSpecificClassPriorityVerified=False),
                remaining=['Declared key predicate is not full runtime registration or target firmware support.', 'getFields includes inherited public fields; this report scopes only declared GimbalKeys fields.', 'Method-map order, inherited annotations, virtual invocation and duplicate key literals still need complete audit.', 'No packet layout or physical effect is established solely by key support.'])


def main():
    p=argparse.ArgumentParser(description=__doc__)
    for name in ('apk','sdk','output'):p.add_argument('--'+name,type=Path,required=True)
    a=p.parse_args();r=trace(a.apk,a.sdk);a.output.write_text(json.dumps(r,ensure_ascii=False,indent=2)+'\n');print('%d declared keys; %d source-supported, %d method fingerprints; no reflection/SDK execution.'%(len(r['declaredFields']),sum(k['sourceSupport'] for k in r['declaredFields']),len(r['methods'])))

if __name__=='__main__':main()
