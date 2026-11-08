"""Validate exported STLs and create geometry-only 3MF plates (no printer/G-code)."""
from pathlib import Path
from collections import Counter, defaultdict
import json
import xml.etree.ElementTree as E
import zipfile

ROOT = Path(__file__).resolve().parent
PARTS = ROOT / 'print_parts'
NS = 'http://schemas.microsoft.com/3dmanufacturing/core/2015/02'
E.register_namespace('', NS)
def tag(s): return '{'+NS+'}'+s

def load_mesh(name):
    vertices, indices, triangles = [], {}, []
    for line in (PARTS / (name+'.stl')).read_text().splitlines():
        fields=line.split()
        if fields and fields[0]=='vertex':
            p=tuple(float(v) for v in fields[1:])
            if p not in indices:
                indices[p]=len(vertices); vertices.append(p)
            triangles.append(indices[p])
    faces=[tuple(triangles[i:i+3]) for i in range(0,len(triangles),3)]
    edges=Counter(tuple(sorted((a,b))) for face in faces for a,b in zip(face,face[1:]+face[:1]))
    assert edges and all(n==2 for n in edges.values()), name+' is not watertight'
    adjacent=defaultdict(set)
    for a,b in edges:
        adjacent[a].add(b); adjacent[b].add(a)
    seen={0}; todo=[0]
    while todo:
        for other in adjacent[todo.pop()]-seen:
            seen.add(other); todo.append(other)
    assert len(seen)==len(vertices), name+' contains disconnected solids'
    bounds=[[min(v[i] for v in vertices),max(v[i] for v in vertices)] for i in range(3)]
    assert abs(bounds[2][0])<0.001, name+' is not on z=0'
    return vertices,faces,bounds

names=['base','socket_gear','idler','pinion','foot','washer','motor_clip','locking_key','fit_coupon','test_peg']
meshes={name:load_mesh(name) for name in names}

def plate(filename,items):
    model=E.Element(tag('model'),{'unit':'millimeter','{http://www.w3.org/XML/1998/namespace}lang':'en-US'})
    E.SubElement(model,tag('metadata'),{'name':'Title'}).text=filename+' - unsliced separate objects'
    resources=E.SubElement(model,tag('resources')); build=E.SubElement(model,tag('build'))
    ids={}
    for name,_,_ in items:
        if name in ids: continue
        oid=str(len(ids)+1); ids[name]=oid
        obj=E.SubElement(resources,tag('object'),{'id':oid,'type':'model','name':name})
        mesh=E.SubElement(obj,tag('mesh'))
        vs=E.SubElement(mesh,tag('vertices')); fs=E.SubElement(mesh,tag('triangles'))
        for x,y,z in meshes[name][0]:
            E.SubElement(vs,tag('vertex'),{'x':str(x),'y':str(y),'z':str(z)})
        for a,b,c in meshes[name][1]:
            E.SubElement(fs,tag('triangle'),{'v1':str(a),'v2':str(b),'v3':str(c)})
    bounds=[]
    for name,x,y in items:
        E.SubElement(build,tag('item'),{'objectid':ids[name],'transform':f'1 0 0 0 1 0 0 0 1 {x} {y} 0'})
        b=meshes[name][2]
        bounds.append((name,b[0][0]+x,b[0][1]+x,b[1][0]+y,b[1][1]+y))
    for i,a in enumerate(bounds):
        for b in bounds[i+1:]:
            assert a[2]<b[1] or b[2]<a[1] or a[4]<b[3] or b[4]<a[3], 'Overlapping plate objects'
    with zipfile.ZipFile(PARTS/filename,'w',zipfile.ZIP_DEFLATED) as z:
        z.writestr('[Content_Types].xml','<?xml version="1.0"?><Types xmlns="http://schemas.openxmlformats.org/package/2006/content-types"><Default Extension="rels" ContentType="application/vnd.openxmlformats-package.relationships+xml"/><Default Extension="model" ContentType="application/vnd.ms-package.3dmanufacturing-3dmodel+xml"/></Types>')
        z.writestr('_rels/.rels','<?xml version="1.0"?><Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships"><Relationship Target="/3D/3dmodel.model" Id="rel0" Type="http://schemas.microsoft.com/3dmanufacturing/2013/01/3dmodel"/></Relationships>')
        z.writestr('3D/3dmodel.model',E.tostring(model,encoding='utf-8',xml_declaration=True))
    return {'objects':len(items),'bounds_xy':bounds}

report={name:{'triangles':len(m[1]),'bounds_mm':m[2],'watertight':True,'connected_solids':1} for name,m in meshes.items()}
report['gears_and_legs.3mf']=plate('gears_and_legs.3mf',[
    ('socket_gear',25,25),('socket_gear',75,25),('socket_gear',125,25),
    ('idler',25,65),('idler',55,65),('pinion',85,65),
    *[('foot',x,100) for x in [20,45,70,95]],
    *[('washer',x,130) for x in [20,45,70,95,120]]])
report['base_plate.3mf']=plate('base_plate.3mf',[('base',128,70)])
report['base_and_legs.3mf']=plate('base_and_legs.3mf',[
    ('base',128,70), *[('foot',x,135) for x in [50,90,130,170]],
    *[('motor_clip',x,165) for x in [50,90]],
    *[('locking_key',x,200) for x in [40,75,110,145,180,215]]])
report['boltless_fit_test.3mf']=plate('boltless_fit_test.3mf',[
    ('fit_coupon',60,90),('test_peg',100,90),('motor_clip',137,90),('locking_key',180,78)])
report['locking_key_retry.3mf']=plate('locking_key_retry.3mf',[
    ('locking_key',100,100),('locking_key',150,100)])
report['gears_only_P1P.3mf']=plate('gears_only_P1P.3mf',[
    ('socket_gear',78,100),('socket_gear',128,100),('socket_gear',178,100),
    ('idler',98,150),('idler',128,150),('pinion',158,150)])
report['gears_and_spacers_P1P.3mf']=plate('gears_and_spacers_P1P.3mf',[
    ('socket_gear',78,100),('socket_gear',128,100),('socket_gear',178,100),
    ('idler',98,150),('idler',128,150),('pinion',158,150),
    *[('washer',x,180) for x in [78,103,128,153,178]]])
(PARTS/'mesh_validation.json').write_text(json.dumps(report,indent=2))
with zipfile.ZipFile(ROOT/'three_tube_print_package.zip','w',zipfile.ZIP_DEFLATED) as bundle:
    for path in sorted(PARTS.iterdir()):
        if path.is_file(): bundle.write(path,'print_parts/'+path.name)
    for name in ['three_tube_gear_scanner.scad','separate_print_parts.png','three_tube_preview.png']:
        bundle.write(ROOT/name,name)
print('Six STLs: watertight, one solid each, z=0. Two unsliced 3MF plates: separate non-overlapping objects.')
