
// Analytic ray intersections: the tray, spheres and shadows all share real depth.
const vertex=`attribute vec2 p;varying vec2 uv;void main(){uv=p;gl_Position=vec4(p,0.,1.);}`;
const fragment=`precision highp float;
varying vec2 uv;uniform vec2 resolution;uniform vec2 tilt;uniform float clock;uniform int count;uniform vec4 balls[6];uniform vec3 colors[6];
float sphere(vec3 ro,vec3 rd,vec3 c,float r){vec3 o=ro-c;float b=dot(o,rd),h=b*b-dot(o,o)+r*r;return h<0.?1000.:-b-sqrt(h);}
float box(vec3 ro,vec3 rd,vec3 c,vec3 s){vec3 a=(c-s-ro)/rd,b=(c+s-ro)/rd;vec3 lo=min(a,b),hi=max(a,b);float n=max(max(lo.x,lo.y),lo.z),f=min(min(hi.x,hi.y),hi.z);return n>0.&&n<f?n:1000.;}
vec3 boxNormal(vec3 p,vec3 c,vec3 s){vec3 q=(p-c)/s,aq=abs(q);return aq.x>aq.y&&aq.x>aq.z?vec3(sign(q.x),0,0):aq.y>aq.z?vec3(0,sign(q.y),0):vec3(0,0,sign(q.z));}
void main(){
vec3 ro=vec3(tilt.x*.15,2.65,1.14+tilt.y*.16),target=vec3(0.,0.,0.);vec3 f=normalize(target-ro),right=normalize(cross(f,vec3(0,1,0))),up=cross(right,f);vec2 screen=uv;screen.x*=resolution.x/resolution.y;vec3 rd=normalize(f+screen.x*.235*right+screen.y*.235*up);
float t=1000.;int material=-1;vec3 n=vec3(0,1,0),base=vec3(.025,.055,.075);vec3 wallC=vec3(0),wallS=vec3(0);
float floorT=-ro.y/rd.y;vec3 floorP=ro+rd*floorT;
if(floorT>0.&&max(abs(floorP.x),abs(floorP.z))<.51){t=floorT;material=0;}
for(int i=0;i<4;i++){vec3 c=vec3(0,.035,0),s=vec3(.55,.055,.027);if(i==0)c.z=-.53;if(i==1)c.z=.53;if(i==2){c.x=-.53;s=s.zyx;}if(i==3){c.x=.53;s=s.zyx;}float d=box(ro,rd,c,s);if(d<t){t=d;material=1;wallC=c;wallS=s;}}
for(int i=0;i<6;i++){if(i<count){vec4 b=balls[i];float d=sphere(ro,rd,b.xyz,b.w);if(d>0.&&d<t){t=d;material=i+2;}}}
vec3 col=mix(vec3(.025,.055,.075),vec3(.055,.105,.125),uv.y*.5+.5);
if(material>=0){vec3 p=ro+rd*t;vec3 light=normalize(vec3(-.5,1.,.7));float shadow=1.;
if(material==0){base=vec3(.065,.12,.145);float grid=max(pow(abs(sin(p.x*31.416)),65.),pow(abs(sin(p.z*31.416)),65.));base+=grid*.012;float edge=smoothstep(.43,.51,max(abs(p.x),abs(p.z)));base=mix(base,vec3(.035,.07,.09),edge*.65);
for(int i=0;i<6;i++){if(i<count){vec4 b=balls[i];float d=length(p.xz-b.xz)/b.w;shadow*=1.-.55*exp(-d*d*1.5);base+=colors[i]*.045*exp(-d*d*.7);float hit=sphere(p+vec3(0,.001,0),light,b.xyz,b.w*.95);if(hit>0.&&hit<2.)shadow*=.65;}}}
else if(material==1){n=boxNormal(p,wallC,wallS);base=vec3(.16,.26,.29);if(n.y>.5){float edge=min(abs(abs(p.x)-.53),abs(abs(p.z)-.53));base+=vec3(.13,.45,.43)*smoothstep(.012,.026,edge);}}
else {for(int i=0;i<6;i++){if(material==i+2){n=normalize(p-balls[i].xyz);base=colors[i];float ring=1.-smoothstep(.014,.035,abs(n.y-.05));base=mix(base,base*.28,ring*.7);}}}
float diffuse=max(dot(n,light),0.);float spec=pow(max(dot(n,normalize(light-rd)),0.),material>1?85.:110.);float fresnel=pow(1.-max(dot(n,-rd),0.),3.);col=base*(.36+.64*diffuse)*shadow+vec3(1.,.96,.89)*spec*.9+base*fresnel*.28;
if(material>1){col+=base*.09;float softbox=pow(max(dot(n,normalize(vec3(-.4,1.,-.3)-rd)),0.),24.);col+=vec3(.65,.85,1.)*softbox*.22;}}
col=pow(max(col,0.),vec3(.82));col*=1.-.1*dot(uv,uv);gl_FragColor=vec4(col,1.);
}`;
export function createPot3D(canvas){
 let gl,program,lost=false,fallback=null;
 const backup=document.createElement('canvas');backup.className=canvas.className;backup.style.cssText='position:absolute;inset:11px;width:calc(100% - 22px);height:calc(100% - 22px);pointer-events:none;display:none';backup.setAttribute('aria-hidden','true');canvas.after(backup);
 function useFallback(reason){canvas.dataset.renderer='software3d';if(!canvas.dataset.renderError)canvas.dataset.renderError=String(reason||'WebGL unavailable');lost=true;backup.style.display='block';fallback??=createSoftwarePot(backup);}
 canvas.dataset.renderer='initializing';
 canvas.addEventListener('webglcontextcreationerror',e=>{canvas.dataset.renderError=e.statusMessage||'WebGL context creation failed';});
 try{gl=canvas.getContext('webgl',{alpha:false,antialias:false,depth:false,powerPreference:'low-power'});if(!gl)throw Error(canvas.dataset.renderError||'WebGL unavailable: getContext returned null');
 const shader=(type,source)=>{if(type===gl.FRAGMENT_SHADER&&!gl.getShaderPrecisionFormat(gl.FRAGMENT_SHADER,gl.HIGH_FLOAT)?.precision)source=source.replace('precision highp float;','precision mediump float;');const s=gl.createShader(type);gl.shaderSource(s,source);gl.compileShader(s);if(!gl.getShaderParameter(s,gl.COMPILE_STATUS))throw Error((type===gl.VERTEX_SHADER?'Vertex shader: ':'Fragment shader: ')+gl.getShaderInfoLog(s));return s;};
 program=gl.createProgram();gl.attachShader(program,shader(gl.VERTEX_SHADER,vertex));gl.attachShader(program,shader(gl.FRAGMENT_SHADER,fragment));gl.linkProgram(program);if(!gl.getProgramParameter(program,gl.LINK_STATUS))throw Error('Program link: '+gl.getProgramInfoLog(program));gl.useProgram(program);
 const buffer=gl.createBuffer();gl.bindBuffer(gl.ARRAY_BUFFER,buffer);gl.bufferData(gl.ARRAY_BUFFER,new Float32Array([-1,-1,1,-1,-1,1,-1,1,1,-1,1,1]),gl.STATIC_DRAW);const p=gl.getAttribLocation(program,'p');gl.enableVertexAttribArray(p);gl.vertexAttribPointer(p,2,gl.FLOAT,false,0,0);canvas.dataset.renderer='webgl';delete canvas.dataset.renderError;
 }catch(e){console.warn('3D tray fallback:',e);useFallback(e.message);}
 canvas.addEventListener('webglcontextlost',e=>{e.preventDefault();useFallback('WebGL context lost during drawing');});
 const uniform=name=>gl.getUniformLocation(program,name),loc=!lost?{size:uniform('resolution'),tilt:uniform('tilt'),count:uniform('count'),balls:uniform('balls[0]'),colors:uniform('colors[0]')}:null;
 const positions=new Float32Array(24),colors=new Float32Array(18);let tx=0,ty=0;
 return (state,time,values)=>{if(lost){fallback(state,time,values);return;}const rect=canvas.getBoundingClientRect(),dpr=Math.min(devicePixelRatio||1,1.5),w=Math.max(1,Math.round(rect.width*dpr)),h=Math.max(1,Math.round(rect.height*dpr));if(canvas.width!==w||canvas.height!==h){canvas.width=w;canvas.height=h;gl.viewport(0,0,w,h);}tx+=(values.tiltX-tx)*.08;ty+=(values.tiltY-ty)*.08;const items=state?.balls.slice(0,6)||[];items.forEach((b,i)=>{const r=.038+.009*b.level;positions.set([b.x-.5,r,b.y-.5,r],i*4);colors.set(b.color==='cyan'?[.22,.88,.77]:[1.,.3,.36],i*3);});gl.uniform2f(loc.size,w,h);gl.uniform2f(loc.tilt,tx,ty);gl.uniform1i(loc.count,items.length);gl.uniform4fv(loc.balls,positions);gl.uniform3fv(loc.colors,colors);gl.drawArrays(gl.TRIANGLES,0,6);};
}


// CPU projection keeps the same three-dimensional vessel on devices without GPU access.
function createSoftwarePot(canvas){
 const c=canvas.getContext('2d');let tx=0,ty=0;
 const dot=(a,b)=>a[0]*b[0]+a[1]*b[1]+a[2]*b[2];
 const norm=a=>{const d=Math.hypot(...a);return a.map(x=>x/d);};
 const cross=(a,b)=>[a[1]*b[2]-a[2]*b[1],a[2]*b[0]-a[0]*b[2],a[0]*b[1]-a[1]*b[0]];
 return (state,time,values)=>{
 const rect=canvas.getBoundingClientRect(),dpr=Math.min(devicePixelRatio||1,2),w=Math.max(1,Math.round(rect.width*dpr)),h=Math.max(1,Math.round(rect.height*dpr));if(canvas.width!==w||canvas.height!==h){canvas.width=w;canvas.height=h;}
 tx+=(values.tiltX-tx)*.08;ty+=(values.tiltY-ty)*.08;
 const eye=[tx*.15,2.65,1.14+ty*.16],forward=norm(eye.map(v=>-v)),right=norm(cross(forward,[0,1,0])),up=cross(right,forward),focal=h/.47;
 const project=p=>{const v=p.map((x,i)=>x-eye[i]),z=dot(v,forward);return {x:w/2+dot(v,right)*focal/z,y:h/2-dot(v,up)*focal/z,z,scale:focal/z};};
 const path=points=>{c.beginPath();points.forEach((p,i)=>{const q=project(p);if(i)c.lineTo(q.x,q.y);else c.moveTo(q.x,q.y);});c.closePath();};
 const face=(points,fill,stroke)=>{path(points);c.fillStyle=fill;c.fill();if(stroke){c.strokeStyle=stroke;c.lineWidth=Math.max(1,dpr*.7);c.stroke();}};
 c.clearRect(0,0,w,h);const bg=c.createRadialGradient(w*.4,h*.3,0,w*.5,h*.5,w*.75);bg.addColorStop(0,'#18323d');bg.addColorStop(1,'#07151e');c.fillStyle=bg;c.fillRect(0,0,w,h);
 // Floor shadow and slab are projected geometry, not a transformed flat canvas.
 const floor=[[-.51,0,-.51],[.51,0,-.51],[.51,0,.51],[-.51,0,.51]];
 c.save();c.shadowColor='#000a';c.shadowBlur=w*.06;c.shadowOffsetY=w*.025;face(floor,'#142b35');c.restore();
 const floorGrad=c.createLinearGradient(0,h*.2,w,h*.8);floorGrad.addColorStop(0,'#243f48');floorGrad.addColorStop(1,'#102a34');face(floor,floorGrad,'#45656e');
 c.save();path(floor);c.clip();c.strokeStyle='#8bb9be10';c.lineWidth=dpr*.6;
 for(let i=-4;i<=4;i++){const a=i*.1;for(const pair of [[[a,.001,-.5],[a,.001,.5]],[[-.5,.001,a],[.5,.001,a]]]){const p=project(pair[0]),q=project(pair[1]);c.beginPath();c.moveTo(p.x,p.y);c.lineTo(q.x,q.y);c.stroke();}}
 c.restore();
 const walls=[[-.53,0,.55,.026],[.53,0,.55,.026],[0,-.53,.026,.55],[0,.53,.026,.55]].map(([x,z,sz,sx])=>({x,z,sx,sz,depth:project([x,.05,z]).z}));
 const drawWall=wall=>{const {x,z,sx,sz}=wall;const x0=x-sx,x1=x+sx,z0=z-sz,z1=z+sz,lo=-.025,hi=.085;
 // Four extruded sides plus the machined upper rim.
 const sides=[[[x0,lo,z0],[x1,lo,z0],[x1,hi,z0],[x0,hi,z0]],[[x1,lo,z0],[x1,lo,z1],[x1,hi,z1],[x1,hi,z0]],[[x1,lo,z1],[x0,lo,z1],[x0,hi,z1],[x1,hi,z1]],[[x0,lo,z1],[x0,lo,z0],[x0,hi,z0],[x0,hi,z1]]];
 sides.sort((a,b)=>project(a[0]).z-project(b[0]).z).reverse().forEach((points,i)=>face(points,['#29434d','#1b333e','#213e47','#35545c'][i]));
 const rim=c.createLinearGradient(0,h*.2,w,h*.8);rim.addColorStop(0,'#9ab9bd');rim.addColorStop(.4,'#3f636c');rim.addColorStop(1,'#76979b');face([[x0,hi,z0],[x1,hi,z0],[x1,hi,z1],[x0,hi,z1]],rim,'#8be7df70');
 };
 const middle=project([0,0,0]).z;walls.filter(wall=>wall.depth>=middle).sort((a,b)=>b.depth-a.depth).forEach(drawWall);
 const balls=(state?.balls||[]).slice(0,6).map(b=>({...b,r:.038+.009*b.level,p:[b.x-.5,.038+.009*b.level,b.y-.5]}));
 balls.forEach(b=>{const center=project([b.p[0],.002,b.p[2]]),a=project([b.p[0]+b.r,.002,b.p[2]]),d=project([b.p[0],.002,b.p[2]+b.r]);c.save();c.translate(center.x,center.y);c.transform((a.x-center.x)/b.r,(a.y-center.y)/b.r,(d.x-center.x)/b.r,(d.y-center.y)/b.r,0,0);const shadow=c.createRadialGradient(0,0,0,0,0,b.r*1.8);shadow.addColorStop(0,'#000b');shadow.addColorStop(.48,'#0007');shadow.addColorStop(1,'#0000');c.fillStyle=shadow;c.fillRect(-b.r*1.8,-b.r*1.8,b.r*3.6,b.r*3.6);c.restore();});
 balls.sort((a,b)=>project(b.p).z-project(a.p).z).forEach(b=>{const p=project(b.p),r=b.r*p.scale,cyan=b.color==='cyan';c.save();c.translate(p.x,p.y);const gradient=c.createRadialGradient(-r*.32,-r*.4,r*.03,-r*.12,-r*.1,r*1.14);gradient.addColorStop(0,cyan?'#d4fff7':'#fff1e8');gradient.addColorStop(.2,cyan?'#70eddb':'#ffb1a7');gradient.addColorStop(.52,cyan?'#2bbba9':'#ef697a');gradient.addColorStop(.82,cyan?'#126c71':'#a73354');gradient.addColorStop(1,cyan?'#16434f':'#5b2540');c.beginPath();c.arc(0,0,r,0,Math.PI*2);c.fillStyle=gradient;c.fill();c.strokeStyle=cyan?'#91fff599':'#ffc8c799';c.lineWidth=dpr*.6;c.stroke();
 c.save();c.beginPath();c.arc(0,0,r*.985,0,Math.PI*2);c.clip();c.strokeStyle=cyan?'#10495688':'#7e264d88';c.lineWidth=Math.max(1,r*.1);c.beginPath();c.ellipse(0,r*.12,r*.99,r*.27,-.12,0,Math.PI);c.stroke();c.restore();
 c.save();c.translate(-r*.28,-r*.38);c.rotate(-.5);const shine=c.createRadialGradient(0,0,0,0,0,r*.35);shine.addColorStop(0,'#fffffff2');shine.addColorStop(.45,'#ffffff8a');shine.addColorStop(1,'#ffffff00');c.scale(1,.5);c.fillStyle=shine;c.beginPath();c.arc(0,0,r*.4,0,Math.PI*2);c.fill();c.restore();
 c.font=`700 ${Math.max(9*dpr,r*.67)}px system-ui,sans-serif`;c.textAlign='center';c.textBaseline='middle';c.fillStyle=cyan?'#e7fffa':'#fff2ef';c.shadowColor='#09252c';c.shadowBlur=dpr*2;c.fillText(String(b.level),r*.12,r*.22);c.restore();});
 walls.filter(wall=>wall.depth<middle).sort((a,b)=>b.depth-a.depth).forEach(drawWall);
 if(!balls.length){c.fillStyle='#aac4c9';c.font=`${11*dpr}px system-ui,sans-serif`;c.textAlign='center';c.fillText('弾が、ここにやってくる',w*.5,h*.5);}
 };
}
