"""Generated fixtures only. No institution model, photo, malware or real rights."""
import io
import json
import struct
from pathlib import Path
import tempfile
import hashlib
from PIL import Image,PngImagePlugin
from apps.api.asset_contracts import ScanResult
from apps.api.domain import utcnow


def synthetic_video(seconds=30):
    """Generated color motion and sine tone; no real people, footage or AV claim."""
    from apps.api.media_validation import MediaProcessor,MediaSettings
    from apps.api.offline_process import private_work_directory,run_bounded
    manifest=Path('runtime/tools/ffmpeg-9.0.2/bundle.json').resolve()
    processor=MediaProcessor(MediaSettings(approved=True,approval_reference='GENERATED SYNTHETIC FIXTURE ONLY',host_isolation_confirmed=True,
        manifest_path=str(manifest),manifest_sha256=hashlib.sha256(manifest.read_bytes()).hexdigest()))
    ffmpeg,_=processor._tools();parent=Path(tempfile.gettempdir()).resolve()
    with tempfile.TemporaryDirectory(prefix='fcs-generated-video-',dir=parent) as directory:
        work=Path(directory).resolve();assert work.parent==parent and work.name.startswith('fcs-generated-video-')
        private_work_directory(work);output=work/'synthetic.mp4'
        run_bounded([str(ffmpeg),'-hide_banner','-loglevel','error','-f','lavfi','-i','testsrc2=size=320x180:rate=10','-f','lavfi','-i','sine=frequency=440:sample_rate=48000',
            '-t',str(seconds),'-c:v','libx264','-threads','1','-pix_fmt','yuv420p','-c:a','aac','-metadata','artist=PRIVATE_SYNTHETIC_METADATA','-n',str(output)],work,seconds=30,output=output)
        return output.read_bytes()


class FixtureScanner:
    """Dependency injection for synthetic tests only; never an actual AV claim."""
    def __init__(self,status='CLEAN'):self.result=status;self.calls=[]
    def status(self):return {'id':'synthetic-protocol-fixture','configured':True,'real_scanner_verified':False,'reason':'합성 UI/통합시험용 검사 응답. 실제 검사기 아님.'}
    async def scan(self,data):
        self.calls.append(data)
        return ScanResult(status=self.result,provider='synthetic-protocol-fixture',at=utcnow(),detail='합성 검사 응답. 실제 악성코드 검사가 아님.')


def glb(document=None,binary=None):
    if binary is None:
        # A tetrahedron at each storey, with genuinely separate mesh nodes.
        binary=b''.join(struct.pack('<3f',*point) for point in [(-2,0,-2),(2,0,-2),(0,3,0),(0,0,2)])
        binary+=struct.pack('<12H',0,1,2,0,2,3,1,3,2,0,3,1)
    if document is None:
        document={'asset':{'version':'2.0','generator':'FIRE-COMMAND synthetic fixture'},'scene':0,'scenes':[{'nodes':[0,1,2]}],
            'nodes':[{'name':f'SYNTHETIC_FLOOR_{n+1}','mesh':0,'translation':[0,n*3,0]} for n in range(3)],
            'meshes':[{'primitives':[{'attributes':{'POSITION':0},'indices':1,'mode':4}]}],
            'buffers':[{'byteLength':len(binary)}],
            'bufferViews':[{'buffer':0,'byteOffset':0,'byteLength':48},{'buffer':0,'byteOffset':48,'byteLength':24}],
            'accessors':[{'bufferView':0,'componentType':5126,'count':4,'type':'VEC3','min':[-2,0,-2],'max':[2,3,2]},
                         {'bufferView':1,'componentType':5123,'count':12,'type':'SCALAR'}]}
    encoded=json.dumps(document,separators=(',',':')).encode()
    encoded+=b' '*((-len(encoded))%4)
    binary+=b'\0'*((-len(binary))%4)
    return struct.pack('<4sII',b'glTF',2,28+len(encoded)+len(binary))+struct.pack('<II',len(encoded),0x4E4F534A)+encoded+struct.pack('<II',len(binary),0x004E4942)+binary


def photo(metadata=True):
    image=Image.new('RGB',(64,32),'#9eafbc')
    for x in range(0,64,16):
        for y in range(0,32,8):
            image.paste('#3b5970',(x,y,x+8,y+4))
    output=io.BytesIO();info=PngImagePlugin.PngInfo()
    if metadata:info.add_text('private','SYNTHETIC_PRIVATE_METADATA_MUST_BE_STRIPPED')
    image.save(output,format='PNG',pnginfo=info)
    return output.getvalue()


def facade_photo():
    """Asymmetric synthetic color chart for visible texture orientation QA."""
    image=Image.new('RGB',(64,64),'#1656e8')
    image.paste('#ed2727',(0,0,64,32))
    image.paste('#f6ef66',(0,0,16,16))
    output=io.BytesIO();image.save(output,format='PNG');return output.getvalue()


def building_glb():
    """Three storeys and explicit facade panels; entirely generated geometry."""
    vertices=[(-16,0,-11),(16,0,-11),(16,4,-11),(-16,4,-11),(-16,0,11),(16,0,11),(16,4,11),(-16,4,11)]
    indices=[0,2,1,0,3,2,4,5,6,4,6,7,0,4,7,0,7,3,1,2,6,1,6,5,3,7,6,3,6,2,0,1,5,0,5,4]
    body=[vertices[index] for index in indices];windows=[]
    for x in [-13,-8,-3,2,7,12]:
        for z in [-11.02,11.02]:
            a,b,c,d=(x-1.4,1,z),(x+1.4,1,z),(x+1.4,3,z),(x-1.4,3,z)
            windows.extend([a,c,b,a,d,c] if z<0 else [a,b,c,a,c,d])
    binary=b''.join(struct.pack('<3f',*point) for point in body+windows)
    doc={'asset':{'version':'2.0','copyright':'Generated synthetic training building; no real facility.'},'scene':0,'scenes':[{'nodes':[0,1,2]}],
         'nodes':[{'name':f'SYNTHETIC_FLOOR_{i+1}','mesh':0,'translation':[0,i*4,0]} for i in range(3)],
         'meshes':[{'primitives':[{'attributes':{'POSITION':0},'material':0},{'attributes':{'POSITION':1},'material':1}]}],
         'materials':[{'pbrMetallicRoughness':{'baseColorFactor':[.65,.73,.78,1],'roughnessFactor':.9}},
                      {'pbrMetallicRoughness':{'baseColorFactor':[.13,.27,.35,1],'roughnessFactor':.4}}],
         'buffers':[{'byteLength':len(binary)}],
         'bufferViews':[{'buffer':0,'byteOffset':0,'byteLength':len(body)*12},{'buffer':0,'byteOffset':len(body)*12,'byteLength':len(windows)*12}],
         'accessors':[{'bufferView':0,'componentType':5126,'count':len(body),'type':'VEC3'},
                      {'bufferView':1,'componentType':5126,'count':len(windows),'type':'VEC3'}]}
    return glb(doc,binary)


def ifc_building():
    """Minimal generated IFC2X3 building with three storeys, no external refs."""
    import hashlib
    lines=[]
    def add(value):
        lines.append(f'#{len(lines)+1}={value};');return '#'+str(len(lines))
    def guid(label):return '0'+hashlib.sha256(('SYNTHETIC-'+label).encode()).hexdigest()[:21]
    person=add("IFCPERSON($,$,'SYNTHETIC',$,$,$,$,$)")
    org=add("IFCORGANIZATION($,'SYNTHETIC',$,$,$)")
    user=add(f'IFCPERSONANDORGANIZATION({person},{org},$)')
    app=add(f"IFCAPPLICATION({org},'1','Synthetic fixture','FCS')")
    history=add(f'IFCOWNERHISTORY({user},{app},$,.ADDED.,$,$,$,1)')
    origin=add('IFCCARTESIANPOINT((0.,0.,0.))');z=add('IFCDIRECTION((0.,0.,1.))');x=add('IFCDIRECTION((1.,0.,0.))')
    axes=add(f'IFCAXIS2PLACEMENT3D({origin},{z},{x})')
    context=add(f"IFCGEOMETRICREPRESENTATIONCONTEXT($,'Model',3,0.00001,{axes},$)")
    metre=add('IFCSIUNIT(*,.LENGTHUNIT.,$,.METRE.)');units=add(f'IFCUNITASSIGNMENT(({metre}))')
    project=add(f"IFCPROJECT('{guid('project')}',{history},'SYNTHETIC_PROJECT',$,$,$,$,({context}),{units})")
    placement=add(f'IFCLOCALPLACEMENT($,{axes})')
    building=add(f"IFCBUILDING('{guid('building')}',{history},'SYNTHETIC_BUILDING',$,$,{placement},$,$,.ELEMENT.,$,$,$)")
    add(f"IFCRELAGGREGATES('{guid('project-rel')}',{history},$,$,{project},({building}))")
    p2=add('IFCCARTESIANPOINT((0.,0.))');axes2=add(f'IFCAXIS2PLACEMENT2D({p2},$)')
    profile=add(f'IFCRECTANGLEPROFILEDEF(.AREA.,$,{axes2},32.,22.)')
    solid=add(f'IFCEXTRUDEDAREASOLID({profile},{axes},{z},4.)')
    representation=add(f"IFCSHAPEREPRESENTATION({context},'Body','SweptSolid',({solid}))")
    shape=add(f'IFCPRODUCTDEFINITIONSHAPE($,$,({representation}))')
    storeys=[]
    for i in range(3):
        point=add(f'IFCCARTESIANPOINT((0.,0.,{i*4}.))');axis=add(f'IFCAXIS2PLACEMENT3D({point},{z},{x})');local=add(f'IFCLOCALPLACEMENT({placement},{axis})')
        storey=add(f"IFCBUILDINGSTOREY('{guid('storey-'+str(i))}',{history},'SYNTHETIC_FLOOR_{i+1}',$,$,{local},$,$,.ELEMENT.,{i*4}.)")
        product=add(f"IFCBUILDINGELEMENTPROXY('{guid('box-'+str(i))}',{history},'SYNTHETIC_BOX_{i+1}',$,$,{local},{shape},$,.ELEMENT.)")
        add(f"IFCRELCONTAINEDINSPATIALSTRUCTURE('{guid('contains-'+str(i))}',{history},$,$,({product}),{storey})")
        storeys.append(storey)
    add(f"IFCRELAGGREGATES('{guid('storeys-rel')}',{history},$,$,{building},({','.join(storeys)}))")
    return ("ISO-10303-21;\nHEADER;\nFILE_DESCRIPTION(('SYNTHETIC TRAINING FIXTURE'),'2;1');\n"
            "FILE_NAME('synthetic.ifc','2026-11-17T00:00:00',('SYNTHETIC'),('SYNTHETIC'),'FCS','FCS','NO REAL FACILITY');\n"
            "FILE_SCHEMA(('IFC2X3'));\nENDSEC;\nDATA;\n"+'\n'.join(lines)+"\nENDSEC;\nEND-ISO-10303-21;\n").encode('utf-8')
