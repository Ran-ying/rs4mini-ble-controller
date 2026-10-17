#!/usr/bin/env python3
"""Read inherited key metadata and HG724 initialization/action declarations only."""
import argparse, hashlib, json
from pathlib import Path
from ronin_key_support import (trace as key_trace, CATALOG, TARGET, BASE,
                               normalize_annotations, select_source_keys)

HW='Ldji/sdksharedlib/hardware/abstractions/DJISDKCacheHWAbstraction;'
INIT='(Ljava/lang/String; I Ldji/sdksharedlib/store/DJISDKCacheStoreLayer; Ldji/sdksharedlib/hardware/abstractions/DJISDKCacheHWAbstraction$OnValueChangeListener;)V'
ACTION='Ldji/sdksharedlib/hardware/abstractions/Action;'


def nearest_declaration(classes, owner, name, descriptor):
    """Resolve exact class-chain declarations, never execute or simulate reflection."""
    visited=set()
    while owner in classes:
        if owner in visited:raise ValueError('cyclic class chain')
        visited.add(owner);row=classes[owner]
        matches=[m for m in row['methods'] if m['method']==name and m['descriptor']==descriptor]
        if len(matches)>1:raise ValueError('duplicate exact method declaration')
        if matches:return dict(className=owner,**matches[0])
        owner=row['superclass']
    raise ValueError('unresolved declaration '+name)


def literal_collisions(fields):
    groups={}
    for row in fields:
        if row['literalKeyName'] is None:raise ValueError('unresolved compiled key literal')
        groups.setdefault(row['literalKeyName'],[]).append(row['declaringClass']+'->'+row['fieldName'])
    return {key:names for key,names in groups.items() if len(names)>1}


def trace(apk,sdk):
    # Reuses pinned-input validation before any optional parser import.
    keys=key_trace(apk,sdk)
    from loguru import logger
    logger.disable('androguard')
    from androguard.core.dex import DEX
    dex=DEX(sdk.read_bytes());cm=dex.get_class_manager();cs={c.get_name():c for c in dex.get_classes()}
    def annotation(a):return dict(typeName=dex.get_cm_type(a.get_type_idx()),elements={dex.get_cm_string(e.get_name_idx()):value(e.get_value()) for e in a.get_elements()})
    def value(v):
        result=v.get_value();kind=v.get_value_type()
        if kind==0x1c:return [value(e) for e in result.get_values()]
        if kind==0x1d:return annotation(result)
        return result
    def aset(offset):return [annotation(o.get_annotation_item().get_annotation()) for o in cm.get_annotation_set_item(offset).get_annotation_off_item()]
    def directory(c):return cm.get_annotations_directory_item(c.get_annotations_off())
    declarations={name:dict(superclass=c.get_superclassname(),methods=[dict(method=m.get_name(),descriptor=m.get_descriptor(),accessFlags=m.get_access_flags()) for m in c.get_methods()]) for name,c in cs.items()}
    methods={}
    def take(owner,name,descriptor=None):
        found=[m for m in cs[owner].get_methods() if m.get_name()==name and (descriptor is None or m.get_descriptor()==descriptor)]
        if len(found)!=1 or not found[0].get_code():raise ValueError('missing or ambiguous code '+name)
        m=found[0];methods[(owner,name,m.get_descriptor())]=dict(className=owner,method=name,descriptor=m.get_descriptor(),codeOffset=m.get_code_off(),instructionSha256=hashlib.sha256(m.get_code().get_bc().get_raw()).hexdigest())
        return [(i.get_name(),i.get_output()) for i in m.get_instructions()]
    def require(ops,token):
        if not any(token in operand for _,operand in ops):raise ValueError('missing audited source token '+token)
    target_chain=keys['targetClassChain']
    if any(cs[c].get_interfaces() for c in target_chain):raise ValueError('interface dispatch requires separate audit')
    initializers=[]
    for owner in target_chain:
        if any(m.get_name()=='init' and m.get_descriptor()==INIT for m in cs[owner].get_methods()):
            ops=take(owner,'init',INIT)
            initializers.append(dict(className=owner,superInvokes=[operand for op,operand in ops if op.startswith('invoke-super')]))
    init_all=take(HW,'initializeAllCharacteristics')
    require(init_all,'->initializeCommonCharacteristics()V');require(init_all,'->initializeComponentCharacteristics()V')
    take(HW,'initializeCommonCharacteristics')
    init_hw=take(HW,'init',INIT)
    require(init_hw,'->initializeAllCharacteristics()V');require(init_hw,'->createMethodMap()V')
    component=[]
    for owner in target_chain:
        if any(m.get_name()=='initializeComponentCharacteristics' and m.get_code() for m in cs[owner].get_methods()):
            ops=take(owner,'initializeComponentCharacteristics')
            component.append(dict(className=owner,superInvokes=[operand for op,operand in ops if op.startswith('invoke-super')]))
    root_ops=take(BASE+'DJIGimbalAbstraction;','initializeComponentCharacteristics')
    require(root_ops,CATALOG);require(root_ops,'->getClass()');require(root_ops,'->addCharacteristics(')
    method_map=take(HW,'createMethodMap');require(method_map,'->actionMethodMap ');require(method_map,'->getMethodsFromSuperClass(')
    take(HW,'getMethodsFromSuperClass')
    invocation=take(HW,'performAction')
    for token in ('->characteristicsMap ','->actionMethodMap ','->isParamTypeCorrect(','->prepend(','Ljava/lang/reflect/Method;->invoke('):require(invocation,token)
    take(HW,'prepend');take(HW,'handleActionCustom');take(HW,'addActionMethod')
    inherited=[];catalog_chain=[];owner=CATALOG
    while owner in cs:
        c=cs[owner];catalog_chain.append(owner)
        if owner!=CATALOG:
            anns={r.get_field_idx():aset(r.get_annotations_off()) for r in directory(c).get_field_annotations()} if c.get_annotations_off() else {}
            for f in c.get_fields():
                if f.get_descriptor()!='Ljava/lang/String;' or f.get_access_flags()&9!=9:continue
                entries,error=normalize_annotations(anns.get(f.get_field_idx(),[]),keys['defaults'])
                if not entries and error is None:continue
                v=f.get_init_value();literal=v.get_value() if v else None
                inherited.append(dict(declaringClass=owner,fieldName=f.get_name(),literalKeyName=literal,entries=entries,invalidAnnotationReason=error,**select_source_keys(entries,TARGET,set(target_chain)|{'Ljava/lang/Object;'})))
        owner=c.get_superclassname()
    all_fields=[dict(declaringClass=CATALOG,**f) for f in keys['declaredFields']]+inherited
    action_declarations=[]
    for owner in target_chain:
        c=cs[owner]
        if not c.get_annotations_off():continue
        by_index={m.get_method_idx():m for m in c.get_methods()}
        for row in directory(c).get_method_annotations():
            m=by_index.get(row.get_method_idx())
            if m is None:continue
            for a in aset(row.get_annotations_off()):
                if a['typeName']==ACTION and a['elements'].get('value') in ('Rotate','ResetGimbal'):
                    if m.get_access_flags()&1==0:raise ValueError('non-public selected action')
                    take(owner,m.get_name(),m.get_descriptor())
                    action_declarations.append(dict(action=a['elements']['value'],declaringClass=owner,method=m.get_name(),descriptor=m.get_descriptor(),nearestTargetDeclaration=nearest_declaration(declarations,TARGET,m.get_name(),m.get_descriptor())))
    return dict(schemaVersion=1,apkSha256=keys['apkSha256'],sdkSha256=keys['sdkSha256'],appCodeExecuted=False,javaReflectionExecuted=False,targetDeviceVerified=False,wholeProtocolRecovered=False,researchToolProvidesSdkInterface=False,
                scope='Inherited annotated catalog fields, HG724 initializer declarations and only Rotate/ResetGimbal action dispatch evidence; no Android reflection execution or complete runtime registry',
                catalogClassChain=catalog_chain,inheritedFields=inherited,catalogLiteralCollisions=literal_collisions(all_fields),annotatedCatalogFieldCount=len(all_fields),
                initDeclarations=initializers,nearestComponentInitializer=nearest_declaration(declarations,TARGET,'initializeComponentCharacteristics','()V'),componentInitializerDeclarations=component,
                selectedActionDeclarations=action_declarations,methods=list(methods.values()),
                sourceActionGuards=['non-subcomponent key','nonempty parameter key','characteristicsMap contains key','actionMethodMap contains key','isParamTypeCorrect(arguments)'],
                sourceActionInvocation='prepend DefaultActionInnerCallback then Method.invoke(this, arguments); source execution not performed',
                runtimeMethodMapOrderVerified=False,actualHg724InstantiationVerified=False,fullRegistryVerified=False,
                remaining=['Caller instantiation/index and live Android cache initialization are not verified.', 'getMethods order and all other annotation collisions/overrides remain unaudited; addActionMethod may mutate maps.', 'Selected action method resolution is not proof of packet route, device acceptance, stopping or physical completion.'])


def main():
    p=argparse.ArgumentParser(description=__doc__)
    for name in ('apk','sdk','output'):p.add_argument('--'+name,type=Path,required=True)
    a=p.parse_args();r=trace(a.apk,a.sdk);a.output.write_text(json.dumps(r,ensure_ascii=False,indent=2)+'\n')
    print('%d annotated fields (%d inherited); %d method fingerprints; no reflection execution.'%(r['annotatedCatalogFieldCount'],len(r['inheritedFields']),len(r['methods'])))

if __name__=='__main__':main()
