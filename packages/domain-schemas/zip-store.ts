/** Small bounded STORE ZIP writer; no paths, compression, or external inputs. */
const table=Uint32Array.from({length:256},(_,n)=>{let c=n;for(let i=0;i<8;i++)c=c&1?0xedb88320^(c>>>1):c>>>1;return c>>>0;});
export function crc32(bytes:Uint8Array){let c=0xffffffff;for(const byte of bytes)c=table[(c^byte)&255]^(c>>>8);return (c^0xffffffff)>>>0;}
export function zipStored(entries:{name:string;bytes:Uint8Array}[]){
 if(entries.length<1||entries.length>10||new Set(entries.map(e=>e.name)).size!==entries.length||entries.some(e=>! /^[a-zA-Z0-9_-]+\.(glb|json|txt)$/.test(e.name))||entries.reduce((n,e)=>n+e.bytes.length,0)>32*1024*1024)throw new Error('장면 묶음의 파일 이름·개수·크기 제한입니다.');
 const encoder=new TextEncoder(),local:Uint8Array[]=[],central:Uint8Array[]=[];let offset=0,centralSize=0;
 for(const entry of entries){const name=encoder.encode(entry.name),crc=crc32(entry.bytes),header=new Uint8Array(30+name.length),view=new DataView(header.buffer);
  view.setUint32(0,0x04034b50,true);view.setUint16(4,20,true);view.setUint16(6,0x800,true);view.setUint16(12,33,true);view.setUint32(14,crc,true);view.setUint32(18,entry.bytes.length,true);view.setUint32(22,entry.bytes.length,true);view.setUint16(26,name.length,true);header.set(name,30);local.push(header,entry.bytes);
  const item=new Uint8Array(46+name.length),dv=new DataView(item.buffer);dv.setUint32(0,0x02014b50,true);dv.setUint16(4,20,true);dv.setUint16(6,20,true);dv.setUint16(8,0x800,true);dv.setUint16(14,33,true);dv.setUint32(16,crc,true);dv.setUint32(20,entry.bytes.length,true);dv.setUint32(24,entry.bytes.length,true);dv.setUint16(28,name.length,true);dv.setUint32(42,offset,true);item.set(name,46);central.push(item);centralSize+=item.length;offset+=header.length+entry.bytes.length;
 }
 const end=new Uint8Array(22),ev=new DataView(end.buffer);ev.setUint32(0,0x06054b50,true);ev.setUint16(8,entries.length,true);ev.setUint16(10,entries.length,true);ev.setUint32(12,centralSize,true);ev.setUint32(16,offset,true);
 const output=new Uint8Array(offset+centralSize+end.length);let position=0;for(const part of [...local,...central,end]){output.set(part,position);position+=part.length;}return output;
}
