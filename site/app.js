const state=document.querySelector('#download-state');
let release;
function trustedRelease(value){
 if(value.status!=='released'||!/^\d+\.\d+\.\d+$/.test(value.version)||!Number.isSafeInteger(value.bytes)||value.bytes<1000000||!/^[a-f0-9]{64}$/.test(value.sha256))throw Error('배포 정보가 아직 준비되지 않았습니다.');
 const expected=`https://github.com/leondic1976/FIRE-COMMAND-STUDIO-/releases/download/v${value.version}/FIRE-Command-Studio-Setup-${value.version}-x64.exe`;
 if(value.download_url!==expected||value.release_url!==`https://github.com/leondic1976/FIRE-COMMAND-STUDIO-/releases/tag/v${value.version}`)throw Error('다운로드 출처를 확인할 수 없습니다.');
 if(value.version!=='0.1.0'){
  const server=value.server;
  if(!server||server.download_url!==`https://github.com/leondic1976/FIRE-COMMAND-STUDIO-/releases/download/v${value.version}/FIRE-Command-Studio-Web-${value.version}.zip`||!/^[a-f0-9]{64}$/.test(server.sha256)||!Number.isSafeInteger(server.bytes)||server.bytes<100000)throw Error('웹서버 패키지의 출처와 체크섬을 확인할 수 없습니다.');
 }
 return value;
}
for(const link of document.querySelectorAll('.download,.server-download'))link.addEventListener('click',event=>{if(link.getAttribute('aria-disabled')==='true')event.preventDefault();});
try{
 const response=await fetch('release.json',{cache:'no-store'});if(!response.ok)throw Error('배포 정보를 불러오지 못했습니다.');release=trustedRelease(await response.json());
 document.querySelector('#version').textContent=`v${release.version} · ${release.published_date}`;
 document.querySelector('#file-size').textContent=`${(release.bytes/1048576).toFixed(1)} MB · 64비트 설치 프로그램`;
 document.querySelector('#signature').textContent=release.authenticode==='Valid'?'전자서명 확인됨':'전자서명 없음 · SHA256 확인 가능';
 document.querySelector('#sha').textContent=release.sha256;document.querySelector('#copy-sha').disabled=false;
 document.querySelector('#release-link').href=release.release_url;
 for(const link of document.querySelectorAll('.download')){link.href=release.download_url;link.removeAttribute('aria-disabled');}
 if(release.server){
  for(const link of document.querySelectorAll('.server-download')){link.href=release.server.download_url;link.removeAttribute('aria-disabled');}
  document.querySelector('#server-sha').textContent=release.server.sha256;
  document.querySelector('#server-size').textContent=`${(release.server.bytes/1048576).toFixed(2)} MB · Python 서버·빌드된 웹 화면·Docker/HTTPS 구성`;
 }
 state.textContent=`v${release.version} · Windows 64비트 · ${(release.bytes/1048576).toFixed(1)} MB · 로컬 훈련 시범판`;
}catch(error){state.textContent=error instanceof Error?error.message:'다운로드 상태를 확인할 수 없습니다.';}
document.querySelector('#copy-sha').addEventListener('click',async()=>{
 if(!release)return;try{await navigator.clipboard.writeText(release.sha256);document.querySelector('#copy-status').textContent='SHA256을 복사했습니다.';}catch{document.querySelector('#copy-status').textContent='자동 복사를 사용할 수 없습니다. 위 체크섬을 직접 선택해 복사하세요.';}
});
