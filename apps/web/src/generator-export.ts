import * as THREE from 'three';
import {GLTFExporter} from 'three/addons/exporters/GLTFExporter.js';
import type {Exercise} from '../../../packages/domain-schemas';
import {sceneObjectBudget} from '../../../packages/domain-schemas/building-plan';
import {zipStored} from '../../../packages/domain-schemas/zip-store';
import {proceduralBuilding,proceduralInterior,proceduralSiteResource} from '../../../packages/scene3d/procedural-building';

const bytes=(value:unknown)=>new TextEncoder().encode(JSON.stringify(value,null,2)+'\n');
const sha=async(value:Uint8Array)=>Array.from(new Uint8Array(await crypto.subtle.digest('SHA-256',value as Uint8Array<ArrayBuffer>)),b=>b.toString(16).padStart(2,'0')).join('');
export async function exportScenePackage(exercise:Exercise){
 const subject=exercise.subject;
 if(subject.target_mode!=='VIRTUAL'||subject.source.classification!=='SYNTHETIC'||subject.source.rights!=='approved'||subject.asset_bindings?.length||subject.external_layers?.length||subject.features.some(f=>f.data_origin==='REFERENCE'))throw new Error('직접 만든 가상 기하만 내보낼 수 있습니다. 실제/참조 자료·승인 자산의 재배포 권리는 별도 검토가 필요합니다.');
 if(sceneObjectBudget(subject.buildings,subject.features)>15000)throw new Error('장면 생성 예산을 초과했습니다. 건물·층·내부 요소를 줄이세요.');
 const root=new THREE.Group();root.name=subject.id;root.userData={trainingOnly:true,illustrative:true,units:'metres',axes:'X east, Y up, Z south',latitude:subject.latitude,longitude:subject.longitude,northRotation:subject.north_rotation};
 try{
  for(const b of subject.buildings){const group=new THREE.Group();group.position.set(b.x,0,b.z);group.rotation.y=THREE.MathUtils.degToRad(b.rotation+subject.north_rotation);group.add(proceduralBuilding(b));for(const feature of subject.features.filter(f=>f.building_id===b.id)){const interior=proceduralInterior(feature,b,feature.state);if(interior)group.add(interior);}root.add(group);}
  for(const feature of subject.features.filter(f=>!f.building_id)){const resource=proceduralSiteResource(feature,feature.state);if(resource)root.add(resource);}
  let nodes=0,triangles=0;root.traverse(item=>{nodes++;if(item instanceof THREE.Mesh)triangles+=(item.geometry.index?.count||item.geometry.getAttribute('position').count)/3;});if(nodes>1800||triangles>200000)throw new Error('재사용 GLB의 객체/삼각형 예산을 초과했습니다. 장면을 줄이세요.');
  root.updateMatrixWorld(true);const result=await new GLTFExporter().parseAsync(root,{binary:true});if(!(result instanceof ArrayBuffer)||result.byteLength>15*1024*1024)throw new Error('GLB 생성 결과가15MiB를 초과했습니다.');
  const glb=new Uint8Array(result),scene=bytes({format:'FIRE_COMMAND_SCENE_V1',training_only:true,exercise_id:exercise.id,revision:exercise.revision,published:exercise.published,subject});
  const provenance=bytes({format:'FIRE_COMMAND_SCENE_PROVENANCE_V1',training_only:true,created_at:new Date().toISOString(),exercise_id:exercise.id,revision:exercise.revision,published:exercise.published,source:subject.source,geometry:'Project-authored procedural geometry; no external models or texture files included.',accuracy:'Illustrative synthetic building/interior, not measured architecture, evacuation analysis or engineering prediction.',files:{'scene.glb':await sha(glb),'scene.json':await sha(scene)}});
  return new Blob([zipStored([{name:'scene.glb',bytes:glb},{name:'scene.json',bytes:scene},{name:'provenance.json',bytes:provenance},{name:'TRAINING_ONLY.txt',bytes:new TextEncoder().encode('TRAINING ONLY. Synthetic procedural geometry. Source and accuracy restrictions are in provenance.json. No actual dispatch or engineering prediction.\n')}])],{type:'application/zip'});
 }finally{root.traverse(item=>{if(item instanceof THREE.Mesh){item.geometry.dispose();for(const material of Array.isArray(item.material)?item.material:[item.material])material.dispose();}});}
}
