export interface MapConfiguration {approved:boolean;key:string}
let configuration:Promise<MapConfiguration>|undefined;
export function desktopMapConfiguration(fallback:MapConfiguration):Promise<MapConfiguration>{
 return configuration??=fetch('/_desktop/map-config',{credentials:'same-origin',cache:'no-store'}).then(async response=>{
  if(!response.ok||!response.headers.get('Content-Type')?.includes('application/json'))return fallback;
  const value=await response.json();const key=typeof value.public_key==='string'?value.public_key:'';
  return {approved:value.approved===true&&/^[a-f0-9]{32}$/i.test(key),key:/^[a-f0-9]{32}$/i.test(key)?key:''};
 }).catch(()=>fallback);
}
