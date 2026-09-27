import * as THREE from 'three';
import { OrbitControls } from './vendor/OrbitControls.js';

// Visual projection of observer snapshots only. No domain state or simulation clock here.
const $ = id => document.getElementById(id);
const viewport = $('factory-viewport');
const canvas = $('factory-canvas');
try { createFactory(); }
catch (error) {
  $('scene-loading').classList.add('hidden');
  $('scene-error').classList.remove('hidden');
  $('scene-error').textContent = 'Không khởi tạo được 3D. Cần WebGL 2; các nút mô phỏng vẫn dùng được.';
  console.error('Factory view:', error);
}

function createFactory() {
  const renderer = new THREE.WebGLRenderer({canvas, antialias:true, alpha:true, powerPreference:'high-performance'});
  renderer.setPixelRatio(Math.min(window.devicePixelRatio,1.75));
  renderer.shadowMap.enabled = true;
  renderer.shadowMap.type = THREE.PCFSoftShadowMap;
  renderer.toneMapping = THREE.ACESFilmicToneMapping;
  renderer.toneMappingExposure = 1.25;
  const scene = new THREE.Scene();
  const camera = new THREE.PerspectiveCamera(38,1,0.1,180);
  camera.position.set(29,27,33);
  const controls = new OrbitControls(camera,canvas);
  controls.target.set(0,0,0);
  controls.enableDamping = true;
  controls.dampingFactor = 0.085;
  controls.minDistance = 7;
  controls.maxDistance = 72;
  controls.maxPolarAngle = Math.PI/2.13;
  controls.minPolarAngle = 0.12;
  controls.enablePan = true;
  controls.panSpeed = 0.6;
  controls.zoomSpeed = 0.75;
  controls.listenToKeyEvents(canvas);
  const hemi = new THREE.HemisphereLight(0xcde8ff,0x253944,2.6);
  scene.add(hemi);
  const sun = new THREE.DirectionalLight(0xfff0d8,3.1);
  sun.position.set(-10,23,14);sun.castShadow=true;
  sun.shadow.mapSize.set(2048,2048);
  Object.assign(sun.shadow.camera,{left:-23,right:23,top:19,bottom:-19,near:1,far:65});
  sun.shadow.bias=-0.0004;sun.shadow.normalBias=0.04;
  scene.add(sun);
  const fill = new THREE.DirectionalLight(0x82cce5,1.2);fill.position.set(18,10,-15);scene.add(fill);
  const factory = new THREE.Group();scene.add(factory);
  const mat = (color, metalness=0.1, roughness=0.65) => new THREE.MeshStandardMaterial({color,metalness,roughness});
  const m = {
    floor:mat(0x85999e,.12,.9), foundation:mat(0x344955,.15,.7), tile:mat(0x8c9fa4),
    white:mat(0xc1d0d1,.25,.36), light:mat(0xd9e2df,.22,.38), steel:mat(0x667f8a,.68,.28),
    dark:mat(0x1b303d,.38,.4), rubber:mat(0x12242e,.15,.75), blue:mat(0x426377,.4,.4),
    accent:mat(0x45b697,.4,.3), orange:mat(0xb88647,.48,.4), black:mat(0x081d2b,.2,.2),
    idle:mat(0x546776,.2,.6), pipe:mat(0x79a8ac,.6,.34), wall:mat(0x8fa6ad,.1,.8),
    glass:new THREE.MeshStandardMaterial({color:0x9ddde5,transparent:true,opacity:.14,metalness:.1,roughness:.12,depthWrite:false}),
    screen:new THREE.MeshStandardMaterial({color:0x163f4e,emissive:0x1c6170,emissiveIntensity:.35,roughness:.3}),
    led:new THREE.MeshStandardMaterial({color:0x63e4bc,emissive:0x42cc9d,emissiveIntensity:1.4}),
    aisle:mat(0x728c93,.1,.85), stripe:mat(0x48b7a5,.05,.65), amber:mat(0xc3a261,.2,.7)
  };
  function box(parent,x,y,z,w,h,d,material,shadow=true) {
    const mesh = new THREE.Mesh(new THREE.BoxGeometry(w,h,d),material);
    mesh.position.set(x,y,z);mesh.castShadow=shadow;mesh.receiveShadow=true;parent.add(mesh);return mesh;
  }
  function cylinder(parent,x,y,z,r,h,material,segments=32) {
    const mesh=new THREE.Mesh(new THREE.CylinderGeometry(r,r,h,segments),material);
    mesh.position.set(x,y,z);mesh.castShadow=true;mesh.receiveShadow=true;parent.add(mesh);return mesh;
  }
  function pipe(parent,from,to,r,material) {
    const a=new THREE.Vector3(...from), b=new THREE.Vector3(...to);
    const mesh=new THREE.Mesh(new THREE.CylinderGeometry(r,r,a.distanceTo(b),12),material);
    mesh.position.copy(a).add(b).multiplyScalar(.5);
    mesh.quaternion.setFromUnitVectors(new THREE.Vector3(0,1,0),b.sub(a).normalize());
    mesh.castShadow=true;parent.add(mesh);return mesh;
  }
  function label(parent,text,x,y,z,width,color='#a7bdc8',floor=false) {
    const surface=document.createElement('canvas');surface.width=768;surface.height=128;
    const ctx=surface.getContext('2d');ctx.font='600 43px Segoe UI, sans-serif';ctx.textAlign='center';ctx.textBaseline='middle';ctx.fillStyle=color;ctx.fillText(text,384,64);
    const texture=new THREE.CanvasTexture(surface);texture.colorSpace=THREE.SRGBColorSpace;
    const mesh=new THREE.Mesh(new THREE.PlaneGeometry(width,width/6),new THREE.MeshBasicMaterial({map:texture,transparent:true,depthWrite:false,side:THREE.DoubleSide}));
    mesh.position.set(x,y,z);if(floor)mesh.rotation.x=-Math.PI/2;parent.add(mesh);return mesh;
  }

  // A cutaway building: architecture and unconnected equipment are context only.
  box(factory,0,-.42,0,29,.75,19,m.foundation);
  box(factory,0,-.015,0,28.5,.12,18.5,m.floor);
  for(let x=-13.5;x<=13.5;x+=1.5)box(factory,x,.052,0,.016,.006,18,m.steel,false);
  for(let z=-9;z<=9;z+=1.5)box(factory,0,.053,z,28,.006,.016,m.steel,false);
  box(factory,0,.065,0,27,.016,3.5,m.aisle,false);
  for(const z of [-1.75,1.75])box(factory,0,.08,z,27,.015,.055,m.stripe,false);
  for(let x=-12;x<13;x+=2)box(factory,x,.085,0,.75,.01,.055,m.white,false);
  label(factory,'FABSCOPE  /  CLEANROOM',0,.08,8.2,10,'#344e5c',true);
  label(factory,'PROCESS BAY 01',3,.088,1.05,5,'#25434f',true);
  label(factory,'LAYOUT ONLY',-7,.09,-1.03,4,'#4c6471',true);
  // Low front edge and two open side walls preserve visibility from the default angle.
  box(factory,0,1.8,-9.15,28.5,3.6,.2,m.wall);
  box(factory,-14.15,1.8,-.4,.2,3.6,17.5,m.wall);
  for(let x=-12;x<=12;x+=4) {
    box(factory,x,2.2,-9.01,3.45,1.45,.04,m.dark);
    box(factory,x,2.23,-8.96,3.15,1.15,.035,m.glass,false);
    box(factory,x,3.28,-8.98,3.5,.075,.08,m.light);
  }
  for(const z of [-6,-1,4]) {
    box(factory,-14.0,2.1,z,.05,1.7,3.8,m.dark);
    box(factory,-13.95,2.15,z,.02,1.4,3.5,m.glass,false);
  }
  for(const x of [-14,0,14]) {
    box(factory,x,2.75,-8.9,.27,5.5,.3,m.light);
    box(factory,x,5.47,-8.9,.45,.15,.45,m.steel);
  }
  for(const x of [-14,14])box(factory,x,2.75,8.8,.25,5.5,.25,m.steel);
  // Overhead rails and utility runs, static by design.
  for(const z of [-7.5,7]) {
    pipe(factory,[-14,5.3,z],[14,5.3,z],.1,m.steel);
    pipe(factory,[-14,5.6,z+.25],[14,5.6,z+.25],.075,m.pipe);
    for(const x of [-10,-3,4,11])pipe(factory,[x,5.3,z],[x,4.75,z],.032,m.steel);
  }
  for(const x of [-11.5,11.5])pipe(factory,[x,5.3,-7.5],[x,5.3,7],.09,m.steel);
  for(const x of [-10,-3,4,11]) {
    box(factory,x,5.05,-7.5,2.2,.11,.38,m.dark);
    box(factory,x,4.98,-7.5,1.98,.025,.29,m.light,false);
  }
  label(factory,'FABSCOPE  /  SIMULATION LAB',-2,3.04,-8.97,12,'#d7eeed');

  function foup(parent,x,z) {
    box(parent,x,.76,z,.76,1.22,.63,m.orange);
    box(parent,x,.79,z+.34,.64,1.05,.08,m.dark);
    box(parent,x,1.42,z,.4,.12,.25,m.steel);
    for(let y=.35;y<1.3;y+=.12)box(parent,x,y,z+.39,.49,.025,.025,m.steel,false);
  }
  function equipment(x,z,active=false,flip=false) {
    const group=new THREE.Group();group.position.set(x,0,z);if(flip)group.rotation.y=Math.PI;factory.add(group);
    box(group,0,.17,0,4.45,.25,3.3,m.dark);
    for(const px of [-1.75,1.75])for(const pz of [-1.2,1.2])cylinder(group,px,.16,pz,.14,.3,m.steel,12);
    box(group,-1.58,1.54,-.08,1.05,2.6,2.85,active?m.light:m.white);
    box(group,1.62,1.54,-.08,1.05,2.6,2.85,active?m.light:m.white);
    for(const px of [-1.58,1.62]) {
      box(group,px,1.55,1.37,.86,2.34,.04,m.white);
      box(group,px+.27,1.68,1.41,.045,.4,.035,m.steel);
      for(let y=.54;y<1.05;y+=.1)box(group,px,y,1.402,.57,.022,.014,m.dark,false);
      box(group,px,2.7,1.402,.65,.055,.02,active?m.accent:m.blue,false);
    }
    box(group,.02,.55,-.15,2.15,.55,2.5,m.blue);
    box(group,.02,2.76,1.06,2.25,.2,.12,active?m.light:m.white);
    box(group,.02,2.76,-1.52,2.25,.2,.12,m.white);
    box(group,.02,1.64,-1.55,2.2,2.1,.12,m.steel);
    const glass=box(group,.02,1.82,1.1,2.16,1.67,.045,m.glass,false);
    const top=box(group,.02,2.91,-.26,2.2,.13,2.6,m.white);
    cylinder(group,.04,1.01,-.28,.83,.34,m.dark);
    cylinder(group,.04,1.26,-.28,.74,.16,m.steel);
    const chamberLid=cylinder(group,.04,2.38,-.28,.88,.2,m.steel);
    const chamberShell=cylinder(group,.04,1.84,-.28,.86,1.0,m.glass);
    chamberShell.castShadow=false;
    for(const dx of [-.7,.7])pipe(group,[dx,1.24,-.83],[dx,2.4,-.83],.045,m.steel);
    box(group,0,.57,1.98,2.95,.65,.82,m.dark);
    for(const dx of [-.85,.85]) {
      box(group,dx,.95,1.98,.94,.13,.84,m.steel);foup(group,dx,2.02);
    }
    box(group,2.04,1.8,1.98,.18,.12,.8,m.steel);
    box(group,2.18,2.04,2.13,.73,.68,.16,m.dark);
    box(group,2.18,2.06,2.226,.61,.48,.025,m.screen,false);
    for(let i=0;i<3;i++)box(group,2.18,2.2-i*.11,2.245,.38,.025,.008,active?m.accent:m.steel,false);
    pipe(group,[1.57,2.8,-.85],[1.57,3.34,-.85],.045,m.steel);
    const lampMat=active?m.led.clone():m.idle;
    cylinder(group,1.57,3.47,-.85,.13,.24,lampMat,16);
    cylinder(group,1.57,3.64,-.85,.13,.1,m.dark,16);
    label(group,active?'SIM-ETCH-01':'BỐ TRÍ',0,2.71,1.24,1.75,active?'#a9f7d6':'#91a4b0');
    for(const px of [-1.6,1.6]) {
      pipe(group,[px,2.76,-1.2],[px,3.66,-1.2],.055,m.pipe);
      pipe(group,[px,3.66,-1.2],[px,3.66,-1.8],.055,m.pipe);
    }
    if(!active)return;
    const waferMat=new THREE.MeshPhysicalMaterial({color:0x6edfd1,metalness:.86,roughness:.2,iridescence:1,iridescenceIOR:1.4,clearcoat:1});
    const wafer=cylinder(group,.04,1.42,-.28,.63,.045,waferMat,64);
    const waferLines=new THREE.Group();wafer.add(waferLines);
    for(let p=-.45;p<=.46;p+=.15) {
      const length=2*Math.sqrt(.58*.58-p*p);
      box(waferLines,p,.025,0,.008,.001,length,m.light,false);
      box(waferLines,0,.026,p,length,.001,.008,m.light,false);
    }
    const halo=new THREE.Mesh(new THREE.TorusGeometry(.76,.023,8,64),m.led.clone());
    halo.rotation.x=Math.PI/2;halo.position.set(.04,1.44,-.28);group.add(halo);
    const processLight=new THREE.PointLight(0x53edbb,0,4,2);processLight.position.set(0,1.9,.1);group.add(processLight);
    const arm=new THREE.Group();arm.position.set(.82,1.23,.65);group.add(arm);
    cylinder(arm,0,0,0,.18,.2,m.steel,20);
    box(arm,-.35,.06,0,.72,.12,.13,m.orange);
    cylinder(arm,-.7,.06,0,.115,.17,m.steel,16);
    box(arm,-.99,.08,0,.55,.09,.1,m.orange);
    const activeBorder=new THREE.LineSegments(new THREE.EdgesGeometry(new THREE.BoxGeometry(4.7,.025,4.8)),new THREE.LineBasicMaterial({color:0x69e0b6,transparent:true,opacity:.85}));
    activeBorder.position.set(0,.08,.48);group.add(activeBorder);
    return {group,wafer,halo,lampMat,processLight,arm,glass,top,chamberShell,chamberLid,activeBorder};
  }
  equipment(-9,-5);equipment(-1.8,-5);equipment(6.2,-5);
  equipment(-8.7,4,false,true);
  const active=equipment(2.1,3.7,true);
  // Stocker racks and entry airlock add context without inventing more simulated machines.
  const rack=new THREE.Group();rack.position.set(10.5,0,4.8);factory.add(rack);
  box(rack,0,1.55,0,2.2,3.1,2.6,m.dark);
  for(const y of [.2,1.2,2.2,3.12])box(rack,0,y,0,2.32,.12,2.75,m.steel);
  for(const x of [-1,1])for(const z of [-1.2,1.2])box(rack,x,1.6,z,.1,3.2,.1,m.white);
  for(const y of [.32,1.34,2.36])for(const x of [-.54,.54]) {
    box(rack,x,y+.35,.48,.72,.7,1.05,m.orange);
    box(rack,x,y+.36,1.025,.59,.58,.035,m.dark);
  }
  label(rack,'STOCKER / BỐ TRÍ',0,3.4,1.4,2.8,'#c4d7df');
  box(factory,-11.7,1.55,7.2,3,3.1,.12,m.white);
  box(factory,-11.7,1.35,7.3,1.6,2.65,.07,m.dark);
  box(factory,-11.7,1.7,7.36,1.28,1.46,.03,m.glass,false);
  box(factory,-10.55,2.2,7.33,.35,.25,.08,m.accent);
  // Two stationary cleanroom silhouettes provide scale; not simulated operators.
  function operator(x,z,rotation=0) {
    const person=new THREE.Group();person.position.set(x,0,z);person.rotation.y=rotation;factory.add(person);
    box(person,0,.92,0,.4,.68,.26,m.light);
    for(const side of [-1,1]) {
      pipe(person,[side*.12,.6,0],[side*.14,.16,.03],.086,m.white);
      box(person,side*.14,.09,.09,.18,.12,.32,m.dark);
      pipe(person,[side*.24,1.14,0],[side*.3,.66,.08],.078,m.light);
    }
    const head=new THREE.Mesh(new THREE.SphereGeometry(.18,16,12),m.light);head.position.y=1.47;person.add(head);
    box(person,0,1.48,.154,.25,.1,.045,m.blue);
  }
  operator(-4.5,.55,-.5);operator(10,-.55,2.8);

  let snapshot=null,cutaway=true,cameraMove=null,stale=false;
  const pinPoint=new THREE.Vector3(2.1,3.9,3.7);
  const projected=new THREE.Vector3();
  function focus(mode) {
    const views={overview:{position:[29,27,33],target:[0,0,0]},machine:{position:[9.2,8.6,14.5],target:[2.1,1.3,3.9]},top:{position:[.1,39,.1],target:[0,0,0]}};
    const view=views[mode];cameraMove={position:new THREE.Vector3(...view.position),target:new THREE.Vector3(...view.target)};
    for(const id of ['overview','machine','top'])$('view-'+id).classList.toggle('selected',id===mode);
  }
  controls.addEventListener('start',()=>{cameraMove=null;});
  function update(s) {
    snapshot=s;stale=false;
    const progress=s.signals.step_progress_pct/100;
    active.wafer.visible=Boolean(s.wafer_id);
    const preparing=s.state==='PREPARING',processing=s.state==='PROCESSING';
    const travel=preparing?progress:(['PROCESSING','COMPLETED','FAULT'].includes(s.state)?1:0);
    active.wafer.position.set(.04,1.42,1.08-1.36*travel);
    active.arm.rotation.y=preparing?-.4+progress*1.7:1.3;
    active.halo.visible=processing;
    active.halo.material.emissiveIntensity=processing ? .7+progress*.7 : 0;
    active.processLight.intensity=processing?2+progress:0;
    const color=s.state==='FAULT'?0xe8b864:(s.state==='EMPTY'?0x537187:0x64e3bc);
    active.lampMat.color.setHex(color);active.lampMat.emissive.setHex(color);
    active.lampMat.emissiveIntensity=s.state==='EMPTY' ? .1 : 1.1;
    $('scene-state').textContent=s.state;
    $('machine-pin').title=`${s.machine_id} · ${s.state} · ${s.wafer_id||'Buồng trống'}`;
    canvas.setAttribute('aria-label',`Nhà xưởng 3D. ${s.machine_id}: ${s.state}, wafer ${s.wafer_id||'chưa nạp'}, t=${s.sim_time_s}s. Kéo xoay, cuộn zoom.`);
  }
  window.fabScene={update,setStale(value){stale=value;if(stale)$('scene-state').textContent='DỮ LIỆU CŨ';}};
  if(window.fabSnapshot)update(window.fabSnapshot);
  for(const mode of ['overview','machine','top'])$('view-'+mode).onclick=()=>focus(mode);
  $('machine-pin').onclick=()=>focus('machine');
  $('cutaway').onclick=()=>{
    cutaway=!cutaway;active.top.visible=!cutaway;active.glass.visible=!cutaway;active.chamberShell.visible=!cutaway;active.chamberLid.visible=!cutaway;
    $('cutaway').setAttribute('aria-pressed',String(cutaway));$('cutaway').textContent=cutaway?'◉ Mở vỏ máy':'◎ Đóng vỏ máy';
  };
  active.top.visible=false;active.glass.visible=false;active.chamberShell.visible=false;active.chamberLid.visible=false;
  // A click picks the actual 3D machine; drag remains an orbit gesture.
  const raycaster=new THREE.Raycaster(),pointer=new THREE.Vector2();let down=null;
  canvas.addEventListener('pointerdown',event=>{down=[event.clientX,event.clientY];});
  canvas.addEventListener('pointerup',event=>{
    if(!down||Math.hypot(event.clientX-down[0],event.clientY-down[1])>5)return;
    const rect=canvas.getBoundingClientRect();pointer.set((event.clientX-rect.left)/rect.width*2-1,-(event.clientY-rect.top)/rect.height*2+1);
    raycaster.setFromCamera(pointer,camera);if(raycaster.intersectObject(active.group,true).length)focus('machine');
  });
  canvas.addEventListener('keydown',event=>{const mode={'1':'overview','2':'machine','3':'top'}[event.key];if(mode){event.preventDefault();focus(mode);}});
  canvas.addEventListener('webglcontextlost',event=>{event.preventDefault();$('scene-error').classList.remove('hidden');$('scene-error').textContent='Mất ngữ cảnh 3D. Tải lại trang để khôi phục.';});
  function resize(){const {width,height}=viewport.getBoundingClientRect();renderer.setSize(width,height,false);camera.aspect=width/height;camera.updateProjectionMatrix();}
  const observer=new ResizeObserver(resize);observer.observe(viewport);resize();
  $('scene-loading').classList.add('hidden');
  canvas.dataset.ready='true';
  let lastFrame=0;
  renderer.setAnimationLoop(time=>{
    if(document.hidden||time-lastFrame<30)return;lastFrame=time;
    if(cameraMove) {
      camera.position.lerp(cameraMove.position,.12);controls.target.lerp(cameraMove.target,.12);
      if(camera.position.distanceTo(cameraMove.position)<.015){camera.position.copy(cameraMove.position);controls.target.copy(cameraMove.target);cameraMove=null;}
    }
    controls.update();
    projected.copy(pinPoint).project(camera);
    const rect=viewport.getBoundingClientRect();
    const x=(projected.x*.5+.5)*rect.width,y=(-projected.y*.5+.5)*rect.height;
    $('machine-pin').style.left=x+'px';$('machine-pin').style.top=y+'px';
    $('machine-pin').style.opacity=projected.z<1&&x>60&&x<rect.width-60&&y>110&&y<rect.height-70?'1':'0';
    $('machine-pin').style.pointerEvents=$('machine-pin').style.opacity==='1'?'auto':'none';
    renderer.render(scene,camera);
  });
}
