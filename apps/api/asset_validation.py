"""Bounded core-glTF validation and metadata-free photograph normalization.

Called only after the upload's malware scan is CLEAN. No URL is ever fetched.
Unsupported glTF features fail explicitly instead of invoking remote decoders.
"""
import io
import json
import math
import struct
import warnings

from PIL import Image,ImageOps,PngImagePlugin,UnidentifiedImageError

from .domain import AssetManifest,AssetNode
from .safety import MAX_ASSET_BYTES,validate_glb

PngImagePlugin.MAX_TEXT_CHUNK=262144
PngImagePlugin.MAX_TEXT_MEMORY=1048576


class AssetValidationError(ValueError):pass


def fail(message='모델 버퍼·정점·객체 계약이 올바르지 않습니다.'):
    raise AssetValidationError(message)


def integer(value,low,high):
    if type(value) is not int or not low<=value<=high:fail()
    return value


def vector(value,length,limit=1e6):
    if not isinstance(value,list) or len(value)!=length or any(type(v) not in (int,float) or not math.isfinite(v) or abs(v)>limit for v in value):fail()
    return value


def image_pixels(data,embedded=False):
    try:
        with warnings.catch_warnings():
            warnings.simplefilter('error',Image.DecompressionBombWarning)
            with Image.open(io.BytesIO(data),formats=['PNG','JPEG']) as original:
                if original.width>4096 or original.height>4096 or original.width*original.height>16777216 or getattr(original,'n_frames',1)!=1:
                    fail('사진은4096px·1600만 화소 이하의 단일 PNG/JPEG여야 합니다.')
                if embedded and set(original.info)-{'jfif','jfif_version','jfif_unit','jfif_density','dpi','adobe','adobe_transform','gamma','srgb'}:
                    fail('내장 이미지의 EXIF/주석/프로필을 제거한 GLB를 사용하세요.')
                original.load()
                result=ImageOps.exif_transpose(original).convert('RGB')
                # New image storage strips inherited EXIF/XMP/ICC and PNG text.
                clean=Image.new('RGB',result.size)
                clean.paste(result)
                if not embedded:clean.thumbnail((2048,2048),Image.Resampling.LANCZOS)
                notice=original.getexif().get(33432,'')
                if not isinstance(notice,str) or len(notice)>500:fail('사진 저작권 표시는500자 이하 문자열이어야 합니다.')
                return clean,notice
    except AssetValidationError:raise
    except (OSError,ValueError,UnidentifiedImageError,Image.DecompressionBombError,Image.DecompressionBombWarning,struct.error):
        fail('사진 형식·압축·픽셀 검사를 통과하지 못했습니다.')


def normalize_photo(data):
    image,notice=image_pixels(data)
    output=io.BytesIO();image.save(output,format='PNG',optimize=False)
    content=output.getvalue()
    if len(content)>MAX_ASSET_BYTES:fail('정규화한 사진이 크기 제한을 초과했습니다.')
    manifest=AssetManifest(width=image.width,height=image.height,texture_pixels=image.width*image.height,copyright_notice=notice)
    image.close()
    return content,manifest


def _multiply(a,b):
    return [sum(a[k*4+r]*b[c*4+k] for k in range(4)) for c in range(4) for r in range(4)]


IDENTITY=[1,0,0,0,0,1,0,0,0,0,1,0,0,0,0,1]


def _matrix(node):
    if 'matrix' in node:
        if any(key in node for key in ['translation','rotation','scale']):fail()
        matrix=vector(node['matrix'],16)
        if [matrix[i] for i in [3,7,11,15]]!=[0,0,0,1]:fail()
        return matrix
    tx,ty,tz=vector(node.get('translation',[0,0,0]),3)
    sx,sy,sz=vector(node.get('scale',[1,1,1]),3,1000)
    if min(sx,sy,sz)<=0:fail('반전/영점 스케일 모델은 오프라인 정규화가 필요합니다.')
    x,y,z,w=vector(node.get('rotation',[0,0,0,1]),4,1)
    if abs(x*x+y*y+z*z+w*w-1)>0.0001:fail()
    return [(1-2*(y*y+z*z))*sx,2*(x*y+z*w)*sx,2*(x*z-y*w)*sx,0,
            2*(x*y-z*w)*sy,(1-2*(x*x+z*z))*sy,2*(y*z+x*w)*sy,0,
            2*(x*z+y*w)*sz,2*(y*z-x*w)*sz,(1-2*(x*x+y*y))*sz,0,tx,ty,tz,1]


def validate_model(data):
    try:return _validate_model(data)
    except AssetValidationError:raise
    except (KeyError,IndexError,TypeError,ValueError,OverflowError,struct.error,RecursionError):fail()


def _validate_model(data):
    # The diagnostic validator additionally bounds recursive JSON and all URIs.
    try:validate_glb(data)
    except Exception:fail('GLB 헤더·청크·JSON·외부 의존성 검사를 통과하지 못했습니다.')
    json_size,json_kind=struct.unpack_from('<II',data,12)
    bin_offset=20+json_size
    if bin_offset+8>len(data):fail()
    bin_size,bin_kind=struct.unpack_from('<II',data,bin_offset)
    if bin_kind!=0x004E4942 or bin_offset+8+bin_size!=len(data):fail('GLB는 JSON과 단일 BIN 청크여야 합니다.')
    doc=json.loads(data[20:20+json_size]);binary=data[bin_offset+8:]
    def core(value):
        if isinstance(value,dict):
            if any(k in value for k in ['extensions','extensionsUsed','extensionsRequired','sparse','uri']):
                fail('확장·압축·sparse·외부/데이터 URI는 지원하지 않습니다. 오프라인 정규화하세요.')
            return {k:core(v) for k,v in value.items() if k!='extras'}
        if isinstance(value,list):return [core(v) for v in value]
        if isinstance(value,float) and not math.isfinite(value):fail()
        return value
    doc=core(doc)
    if doc['asset'].get('minVersion','2.0')!='2.0':fail('지원하는 모델 최소 버전은 glTF2.0입니다.')
    notice=doc['asset'].get('copyright','')
    if not isinstance(notice,str) or len(notice)>500:fail('모델 저작권 표시는500자 이하 문자열이어야 합니다.')
    if any(doc.get(k) for k in ['animations','skins','cameras']):fail('애니메이션·스킨·카메라 없는 정적 건물 GLB를 사용하세요.')
    buffers=doc.get('buffers',[])
    if len(buffers)!=1:fail()
    declared=integer(buffers[0].get('byteLength'),1,MAX_ASSET_BYTES)
    if not declared<=len(binary)<=declared+3:fail()
    views=doc.get('bufferViews',[]);accessors=doc.get('accessors',[])
    if len(views)>10000 or len(accessors)>10000:fail()
    for view in views:
        if view.get('buffer')!=0:fail()
        start=integer(view.get('byteOffset',0),0,declared)
        size=integer(view.get('byteLength'),1,declared)
        if start+size>declared:fail()
        if 'byteStride' in view:
            stride=integer(view['byteStride'],4,252)
            if stride%4:fail()
    cache={};decoded=0
    def read(index):
        nonlocal decoded
        index=integer(index,0,len(accessors)-1)
        if index in cache:return cache[index]
        accessor=accessors[index]
        components={'SCALAR':1,'VEC2':2,'VEC3':3,'VEC4':4}.get(accessor.get('type'))
        fmt={5120:'b',5121:'B',5122:'h',5123:'H',5125:'I',5126:'f'}.get(accessor.get('componentType'))
        if not components or not fmt:fail()
        if type(accessor.get('normalized',False)) is not bool or accessor.get('normalized') and fmt=='f':fail()
        count=integer(accessor.get('count'),1,1000000);decoded+=count*components
        if decoded>4000000:fail('모델 접근자 총량 제한 초과')
        view=views[integer(accessor.get('bufferView'),0,len(views)-1)]
        unit=struct.calcsize(fmt);width=components*unit
        offset=integer(accessor.get('byteOffset',0),0,view['byteLength'])
        stride=view.get('byteStride',width)
        start=view.get('byteOffset',0)+offset
        if stride<width or start%unit or offset+(count-1)*stride+width>view['byteLength']:fail()
        values=[struct.unpack_from('<'+fmt*components,binary,start+i*stride) for i in range(count)]
        if any(not math.isfinite(v) or abs(v)>1e6 for point in values for v in point):fail('유한 좌표·속성 범위를 벗어났습니다.')
        cache[index]=values
        accessor['min']=[min(v[i] for v in values) for i in range(components)]
        accessor['max']=[max(v[i] for v in values) for i in range(components)]
        return values
    images=doc.get('images',[]);textures=doc.get('textures',[]);samplers=doc.get('samplers',[]);materials=doc.get('materials',[])
    for values,limit in [(images,16),(textures,16),(samplers,64),(materials,500)]:
        if not isinstance(values,list) or len(values)>limit or any(not isinstance(item,dict) for item in values):fail()
    for sampler in samplers:
        if sampler.get('magFilter',9729) not in [9728,9729] or sampler.get('minFilter',9987) not in [9728,9729,9984,9985,9986,9987]:fail()
        if any(sampler.get(key,10497) not in [33071,33648,10497] for key in ['wrapS','wrapT']):fail()
    for texture in textures:
        integer(texture.get('source'),0,len(images)-1)
        if 'sampler' in texture:integer(texture['sampler'],0,len(samplers)-1)
    def texture_info(info):
        if not isinstance(info,dict) or info.get('texCoord',0)!=0:fail('현재 재질은 UV0만 지원합니다.')
        integer(info.get('index'),0,len(textures)-1)
    def factor(value,length=None):
        values=vector(value,length,1) if length else [value]
        if any(type(v) not in (int,float) or not math.isfinite(v) or not 0<=v<=1 for v in values):fail()
    for material in materials:
        if material.get('alphaMode','OPAQUE') not in ['OPAQUE','MASK','BLEND'] or type(material.get('doubleSided',False)) is not bool:fail()
        pbr=material.get('pbrMetallicRoughness',{})
        if not isinstance(pbr,dict):fail()
        for key,length in [('baseColorFactor',4)]:
            if key in pbr:factor(pbr[key],length)
        for key in ['metallicFactor','roughnessFactor']:
            if key in pbr:factor(pbr[key])
        for key in ['baseColorTexture','metallicRoughnessTexture']:
            if key in pbr:texture_info(pbr[key])
        for key in ['normalTexture','occlusionTexture','emissiveTexture']:
            if key in material:texture_info(material[key])
        if 'emissiveFactor' in material:factor(material['emissiveFactor'],3)
        if 'alphaCutoff' in material:factor(material['alphaCutoff'])
        if 'normalTexture' in material:
            scale=material['normalTexture'].get('scale',1)
            if type(scale) not in (int,float) or not 0<=scale<=4:fail()
        if 'occlusionTexture' in material:factor(material['occlusionTexture'].get('strength',1))
    meshes=doc.get('meshes',[])
    if not meshes or len(meshes)>2000:fail()
    local=[]
    for mesh in meshes:
        primitives=mesh.get('primitives',[])
        if not isinstance(primitives,list) or not 1<=len(primitives)<=2000:fail()
        points=[];triangles=0
        for primitive in primitives:
            if not isinstance(primitive,dict) or primitive.get('mode',4)!=4 or primitive.get('targets'):fail('삼각형 정적 메시만 지원합니다.')
            if 'material' in primitive:integer(primitive['material'],0,len(materials)-1)
            attrs=primitive.get('attributes',{})
            if not isinstance(attrs,dict) or not set(attrs)<= {'POSITION','NORMAL','TANGENT','TEXCOORD_0','COLOR_0'} or 'POSITION' not in attrs:fail()
            accessor=accessors[integer(attrs['POSITION'],0,len(accessors)-1)]
            if accessor.get('type')!='VEC3' or accessor.get('componentType')!=5126:fail()
            vertices=read(attrs['POSITION']);points.extend(vertices)
            for key,index in attrs.items():
                values=read(index)
                if len(values)!=len(vertices):fail()
                expected={'POSITION':{3},'NORMAL':{3},'TANGENT':{4},'TEXCOORD_0':{2},'COLOR_0':{3,4}}[key]
                if len(values[0]) not in expected:fail()
            if 'indices' in primitive:
                index=integer(primitive['indices'],0,len(accessors)-1);indices=read(index)
                if accessors[index].get('componentType') not in [5121,5123,5125] or accessors[index].get('type')!='SCALAR' or any(v[0]>=len(vertices) for v in indices):fail()
                count=len(indices)
            else:count=len(vertices)
            if count%3:fail()
            triangles+=count//3
            if triangles>200000:fail('모델 삼각형 예산 초과')
        local.append(([[min(p[i] for p in points) for i in range(3)],[max(p[i] for p in points) for i in range(3)]],triangles))
    nodes=doc.get('nodes',[])
    if not 1<=len(nodes)<=2000:fail()
    scenes=doc.get('scenes',[])
    scene=scenes[integer(doc.get('scene',0),0,len(scenes)-1)]
    roots=scene.get('nodes',[])
    seen=set();render_nodes=[];world_points=[];triangles=0
    def visit(index,parent,depth):
        nonlocal triangles
        index=integer(index,0,len(nodes)-1)
        if index in seen or depth>40:fail('객체 계층에 순환·다중 부모 또는 과도한 중첩이 있습니다.')
        seen.add(index);node=nodes[index]
        if node.get('skin') is not None or node.get('camera') is not None:fail()
        matrix=_multiply(parent,_matrix(node))
        if any(not math.isfinite(v) or abs(v)>1e6 for v in matrix):fail()
        if 'mesh' in node:
            bounds,count=local[integer(node['mesh'],0,len(meshes)-1)]
            triangles+=count
            if triangles>200000:fail('배치된 메시의 삼각형 예산 초과')
            name=node.get('name',f'객체{index}')
            if not isinstance(name,str) or len(name)>200:fail()
            node_points=[]
            for x in [bounds[0][0],bounds[1][0]]:
                for y in [bounds[0][1],bounds[1][1]]:
                    for z in [bounds[0][2],bounds[1][2]]:
                        point=[sum(matrix[k*4+r]*v for k,v in enumerate([x,y,z,1])) for r in range(3)]
                        world_points.append(point);node_points.append(point)
            render_nodes.append(AssetNode(index=index,name=name,bounds=[[min(p[i] for p in node_points) for i in range(3)],[max(p[i] for p in node_points) for i in range(3)]]))
        children=node.get('children',[])
        if not isinstance(children,list) or len(children)>2000:fail()
        for child in children:visit(child,matrix,depth+1)
    if not isinstance(roots,list):fail()
    for index in roots:visit(index,IDENTITY,0)
    if len(seen)!=len(nodes) or not world_points:fail('기본 장면에 연결되지 않은 객체가 있습니다.')
    texture_pixels=0
    for image in images:
        if image.get('mimeType') not in ['image/png','image/jpeg']:fail()
        view=views[integer(image.get('bufferView'),0,len(views)-1)]
        start=view.get('byteOffset',0);raw=binary[start:start+view['byteLength']]
        clean,_=image_pixels(raw,True);texture_pixels+=clean.width*clean.height;clean.close()
        if texture_pixels>8388608:fail('내장 텍스처 총 화소 예산 초과')
    if len(doc.get('images',[]))>16:fail('내장 이미지 수 제한 초과')
    # Remove extras/generator metadata, preserve checked core geometry and images.
    doc['asset']={'version':'2.0'}
    if notice:doc['asset']['copyright']=notice
    encoded=json.dumps(doc,separators=(',',':'),ensure_ascii=False,allow_nan=False).encode()
    encoded+=b' '*((-len(encoded))%4)
    canonical=struct.pack('<4sII',b'glTF',2,28+len(encoded)+len(binary))+struct.pack('<II',len(encoded),json_kind)+encoded+struct.pack('<II',len(binary),bin_kind)+binary
    bounds=[[min(p[i] for p in world_points) for i in range(3)],[max(p[i] for p in world_points) for i in range(3)]]
    if any(not math.isfinite(v) or abs(v)>1e6 for p in bounds for v in p) or any(bounds[0][i]>=bounds[1][i] for i in range(3)):fail('입체 모델 범위가 올바르지 않습니다.')
    return canonical,AssetManifest(bounds=bounds,nodes=render_nodes,triangles=triangles,texture_pixels=texture_pixels,copyright_notice=notice)
