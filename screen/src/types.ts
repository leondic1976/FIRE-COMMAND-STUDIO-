export type Side='A'|'B'|'C'|'D';
export type Source={name:string;reference:string;accuracy:'fictional'|'approximate'|'surveyed';rights:string};
export type Site={name:string;address:string;latitude:number;longitude:number;front_bearing:number;target_mode:'VIRTUAL'|'APPROXIMATE'|'REAL';source:Source};
export type Building={id:string;name:string;x:number;z:number;width:number;depth:number;floors:number;floor_height:number;style:'warehouse'|'office'|'apartment';color:string;model_asset_id:string|null;facade_assets:Partial<Record<Side,string>>};
export type Kind='fire'|'victim'|'engine'|'ladder'|'ambulance'|'command'|'hydrant'|'crew'|'cordon';
export type Entity={id:string;kind:Kind;label:string;x:number;z:number;y:number;heading:number;building_id:string|null;floor:number;side:Side;visible:boolean;smoke:number;fire:number;status:'standby'|'active'|'waiting'|'rescued'|'unknown'|'unavailable';spraying:boolean;target_id:string|null};
export type Weather={wind_degrees:number;wind_speed:number;rain:number;daylight:number;fog:number};
export type Patch={entities:Record<string,Partial<Pick<Entity,'visible'|'smoke'|'fire'|'spraying'|'status'|'x'|'z'>>>;weather:Weather|null;damage:Record<string,number>;water:boolean|null;power:boolean|null};
export type Incident={id:string;at_seconds:number;catalog_id:string;title:string;message:string;source_label:string;certainty:'fictional'|'unverified'|'confirmed';priority:'info'|'attention'|'urgent';side:Side;patch:Patch;private_prompt:string};
export type Scenario={schema_version:1;id:string;title:string;description:string;mode:'auto'|'confirm';site:Site;buildings:Building[];entities:Entity[];weather:Weather;events:Incident[];duration_seconds:number};
export type SceneState=Pick<Scenario,'site'|'buildings'|'entities'|'weather'>&{damage:Record<string,number>;water:boolean;power:boolean};
export type Message=Pick<Incident,'id'|'title'|'message'|'source_label'|'certainty'|'priority'|'side'>&{elapsed:number};
export type Snapshot={id:string;title:string;status:'READY'|'RUNNING'|'PAUSED'|'ENDED';scene:SceneState;messages:Message[];seq:number;state_version:number;elapsed:number;server_time:number;mode?:'auto'|'confirm';due_at?:number|null;duration_seconds?:number;event_count?:number;released_count?:number;notes?:{text:string;elapsed:number;event_id:string|null}[];log?:{seq:number;kind:string;elapsed:number;detail:string}[]};
export type Asset={id:string;kind:'GLB'|'PHOTO';source:Source;status:'QUARANTINED'|'VALIDATED'|'APPROVED';state_version:number;reason:string;bytes:number};
export type CatalogItem={id:string;category:string;title:string;message:string};
export type User={id:string;name:string;role:string;organization_id:string};
export const sideNames:Record<Side,string>={A:'전면',B:'측면',C:'후면',D:'측면'};
export const kindNames:Record<Kind,string>={fire:'화재 위치',victim:'요구조자',engine:'소방차',ladder:'고가차',ambulance:'구급차',command:'지휘대',hydrant:'소화전',crew:'대원',cordon:'통제선'};
export const timeText=(value:number)=>{const s=Math.max(0,Math.floor(value));return `${String(Math.floor(s/60)).padStart(2,'0')}:${String(s%60).padStart(2,'0')}`;};
export function entityPosition(entity:Entity,buildings:Building[]):[number,number,number]{
 const b=buildings.find(v=>v.id===entity.building_id);
 if(!b||!['fire','victim'].includes(entity.kind)||entity.status==='rescued')return [entity.x,entity.y,entity.z];
 const y=(entity.floor-1)*b.floor_height+2.1+entity.y;
 return entity.side==='A'?[b.x+entity.x,y,b.z+b.depth/2+.4]:entity.side==='B'?[b.x-b.width/2-.4,y,b.z+entity.z]:entity.side==='C'?[b.x-entity.x,y,b.z-b.depth/2-.4]:[b.x+b.width/2+.4,y,b.z-entity.z];
}
export function initialScene(scenario:Scenario):SceneState{return {site:scenario.site,buildings:scenario.buildings,entities:scenario.entities,weather:scenario.weather,damage:{},water:true,power:true};}
