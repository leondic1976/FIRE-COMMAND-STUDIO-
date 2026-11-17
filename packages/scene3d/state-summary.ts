import {StateValue,Subject} from '../domain-schemas';
import {floorLabel,interiorKinds} from '../domain-schemas/building-plan';

export function sceneStateSummary(subject:Subject,state:Record<string,Record<string,StateValue>>){
 const names=new Map([...subject.buildings,...subject.features].map(item=>[item.id,item.name]));
 const kinds=new Map(subject.features.map(item=>[item.id,item.kind]));
 const features=new Map(subject.features.map(item=>[item.id,item]));
 const buildings=new Set(subject.buildings.map(item=>item.id));
 const statusLabels:Record<string,string>={WAITING:'대기',AVAILABLE:'가용',WORKING:'작업 중',WITHDRAWN:'철수',UNAVAILABLE:'사용 불가',UNCONFIRMED:'미확인',NORMAL:'정상',FAILED:'장애'};
 return Object.entries(state).flatMap(([id,value])=>{
  const details:string[]=[];
  const feature=features.get(id);
  if(feature&&feature.kind in interiorKinds)details.push(`${floorLabel(feature.floor)} · 가상 ${interiorKinds[feature.kind as keyof typeof interiorKinds]} · ${feature.width??4}×${feature.depth??4}m`);
  if(typeof value.smoke==='number'&&value.smoke>0)details.push(`연기 ${value.smoke}단계`);
  if(typeof value.fire==='number'&&value.fire>0)details.push(`화염 ${value.fire}단계`);
  if(typeof value.water==='number'&&value.water>0)details.push(`침수 ${value.water}단계`);
  if(value.water==='UNCONFIRMED')details.push('소방용수 미확인');
  if(value.water==='UNAVAILABLE')details.push('소방용수 사용 불가');
  if(value.water==='AVAILABLE')details.push('소방용수 사용 가능');
  if(value.warning===true)details.push(buildings.has(id)&&id!==subject.buildings[0]?.id?'인접동 노출 주의':'위험 주의');
  if(value.closed===true)details.push(kinds.get(id)==='ENTRANCE'?'출입구 폐쇄':'진입 통제');
  if(typeof value.radius==='number')details.push(`통제 반경 ${value.radius}m`);
  if(value.communication==='FAILED')details.push('통신 장애');
  else if(typeof value.communication==='string'&&value.communication!=='NORMAL')details.push(`통신 ${statusLabels[value.communication]||value.communication}`);
  if(value.power===false)details.push('정전 (연출)');
  if(typeof value.rain==='number'&&value.rain>0)details.push(`강우 연출 ${value.rain}단계`);
  if(typeof value.wind==='number'&&value.wind>0)details.push(`바람 강도 ${value.wind} (연출)`);
  if(typeof value.status==='string'&&value.status)details.push(`자원 상태 ${statusLabels[value.status]||value.status}`);
  if(typeof value.casualties==='number'&&value.casualties>0)details.push(`요구조자 ${value.casualties}명`);
  return details.length?[{id,name:names.get(id)||id,details:details.join(' · ')}]:[];
 });
}
