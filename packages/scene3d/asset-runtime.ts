import * as THREE from 'three';
import {GLTFLoader} from 'three/addons/loaders/GLTFLoader.js';

export async function assetBytes(url:string,sha256:string,signal:AbortSignal,cache?:Map<string,ArrayBuffer>){
 const key=url+'#'+sha256,cached=cache?.get(key);
 if(cached){if(signal.aborted)throw new DOMException('Aborted','AbortError');cache!.delete(key);cache!.set(key,cached);return cached;}
 const response=await fetch(url,{signal,credentials:'same-origin',cache:'no-store'});
 if(!response.ok)throw new Error('자산 권한·승인·콘텐츠 상태를 확인하세요.');
 const bytes=await response.arrayBuffer();
 if(bytes.byteLength>15*1024*1024)throw new Error('자산 크기 제한을 초과했습니다.');
 const actual=Array.from(new Uint8Array(await crypto.subtle.digest('SHA-256',bytes))).map(v=>v.toString(16).padStart(2,'0')).join('');
 if(actual!==sha256)throw new Error('자산 해시가 발행본과 다릅니다.');
 if(signal.aborted)throw new DOMException('Aborted','AbortError');
 if(cache){cache.set(key,bytes);while(Array.from(cache.values()).reduce((n,value)=>n+value.byteLength,0)>32*1024*1024){const oldest=cache.keys().next().value;if(oldest)cache.delete(oldest);else break;}}
 return bytes;
}

export function disposeAsset(root:THREE.Object3D){
 const geometries=new Set<THREE.BufferGeometry>(),materials=new Set<THREE.Material>(),textures=new Set<THREE.Texture>();
 root.traverse(object=>{if(object instanceof THREE.Mesh){geometries.add(object.geometry);for(const material of Array.isArray(object.material)?object.material:[object.material])materials.add(material);}});
 for(const material of materials)for(const value of Object.values(material))if(value instanceof THREE.Texture)textures.add(value);
 for(const texture of textures){texture.dispose();if(typeof ImageBitmap!=='undefined'&&texture.image instanceof ImageBitmap)texture.image.close();}
 for(const material of materials)material.dispose();for(const geometry of geometries)geometry.dispose();
}

export async function loadAssetModel(url:string,sha256:string,signal:AbortSignal,cache?:Map<string,ArrayBuffer>){
 const bytes=await assetBytes(url,sha256,signal,cache);
 const manager=new THREE.LoadingManager();manager.setURLModifier(value=>{if(!value.startsWith('blob:'))throw new Error('외부 모델 의존성을 차단했습니다.');return value;});
 const loader=new GLTFLoader(manager),gltf=await loader.parseAsync(bytes,'');
 if(signal.aborted){disposeAsset(gltf.scene);throw new DOMException('Aborted','AbortError');}
 // Static nodes are flattened with their full world matrices. Filtering one
 // floor must not hide a differently mapped child node through inheritance.
 gltf.scene.updateMatrixWorld(true);
 const root=new THREE.Group(),nodes=new Map<number,THREE.Object3D>(),oldMaterials=new Set<THREE.Material>();
 gltf.scene.traverse(object=>{if(!(object instanceof THREE.Mesh))return;let parent:THREE.Object3D|null=object,index:number|undefined;
  while(parent){const association=gltf.parser.associations.get(parent);if(association?.nodes!==undefined){index=association.nodes;break;}parent=parent.parent;}
  if(index===undefined)return;let group=nodes.get(index);if(!group){group=new THREE.Group();group.userData.assetNodeIndex=index;nodes.set(index,group);root.add(group);}
  const mesh=object.clone(false);mesh.matrixAutoUpdate=false;mesh.matrix.copy(object.matrixWorld);mesh.castShadow=true;mesh.receiveShadow=true;
  const materials=Array.isArray(object.material)?object.material:[object.material];materials.forEach(material=>oldMaterials.add(material));
  const copies=materials.map(material=>material.clone());mesh.material=Array.isArray(object.material)?copies:copies[0];group.add(mesh);
 });
 oldMaterials.forEach(material=>material.dispose());
 return {root,nodes};
}

export async function loadAssetTexture(url:string,sha256:string,signal:AbortSignal,cache?:Map<string,ArrayBuffer>){
 const bytes=await assetBytes(url,sha256,signal,cache),bitmap=await createImageBitmap(new Blob([bytes],{type:'image/png'}),{imageOrientation:'flipY'});
 if(signal.aborted){bitmap.close();throw new DOMException('Aborted','AbortError');}
 const texture=new THREE.Texture(bitmap);texture.colorSpace=THREE.SRGBColorSpace;texture.needsUpdate=true;return texture;
}
