export const SAMPLE_RECIPE = {
  schema: 1,
  filename_pattern: '(?P<project>[^_]+)_(?P<kind>[^_]+)_(?P<slot>[^_]+)_v(?P<version>\\d+)\\.[^.]+',
  projects: ['P001', 'P002', 'P003'],
  items: [
    {kind:'design',label:{zh:'设计文件',en:'Design'},extensions:['.svg'],min_count:1,max_count:1},
    {kind:'guide',label:{zh:'说明文件',en:'Guide'},extensions:['.txt'],min_count:1,max_count:1},
    {kind:'image',label:{zh:'配图',en:'Images'},extensions:['.svg'],min_count:2,max_count:2}
  ]
};
const encoder = new TextEncoder();
const reserved = /^(CON|PRN|AUX|NUL|COM[1-9]|LPT[1-9])(\.|$)/i;
function safeName(name) {
  if (typeof name !== 'string' || !/^[\p{L}\p{N}_.-]+$/u.test(name) || ['.','..'].includes(name) || name.endsWith('.') || reserved.test(name))
    throw Error('名称无效 / Invalid name');
}
export function validateRecipe(recipe) {
  if (!recipe || recipe.schema !== 1) throw Error('清单需要 schema: 1 / Recipe requires schema: 1');
  if (!Array.isArray(recipe.projects) || !recipe.projects.length || new Set(recipe.projects).size !== recipe.projects.length)
    throw Error('请列出不重复的项目编号 / Provide unique project IDs');
  recipe.projects.forEach(safeName);
  if(new Set(recipe.projects.map(x=>x.toLowerCase())).size!==recipe.projects.length)throw Error('项目编号不能重复 / Duplicate project IDs');
  if (!Array.isArray(recipe.items) || !recipe.items.length) throw Error('请添加资料类别 / Add at least one item');
  const kinds = new Set();
  for (const item of recipe.items) {
    safeName(item.kind);
    if (kinds.has(item.kind)) throw Error('资料类别不能重复 / Duplicate item kind');
    kinds.add(item.kind);
    const low=item.min_count ?? 1, high=item.max_count ?? 1;
    if (!Number.isInteger(low) || !Number.isInteger(high) || low<0 || high<low || high>10000)
      throw Error('资料数量范围无效 / Invalid item count range');
    if (!Array.isArray(item.extensions) || !item.extensions.length || item.extensions.some(x=>typeof x!=='string' || !/^\.[A-Za-z0-9]+$/.test(x)))
      throw Error('扩展名无效 / Invalid extension');
  }
  if (typeof recipe.filename_pattern !== 'string') throw Error('匹配规则无效 / Invalid pattern');
  for (const key of ['project','kind','version'])
    if (!recipe.filename_pattern.includes(`(?P<${key}>`)) throw Error('匹配规则需要 project、kind、version / Pattern requires project, kind and version');
  return new RegExp('^(?:'+recipe.filename_pattern.replaceAll('(?P<','(?<')+')$','u');
}
export async function hash(bytes) {
  return [...new Uint8Array(await crypto.subtle.digest('SHA-256',bytes))].map(x=>x.toString(16).padStart(2,'0')).join('');
}
const order = (a,b)=>a.path<b.path?-1:a.path>b.path?1:0;
export async function planFiles(files, recipe) {
  const pattern=validateRecipe(recipe), rules=new Map(recipe.items.map(x=>[x.kind,x]));
  const buckets=new Map(), ignored=[], inputs=new Map();
  for (const file of files) {
    const path=file.relativePath || file.webkitRelativePath || file.name;
    if (typeof path!=='string' || path.startsWith('/') || path.includes('\\') || path.includes(':') || path.split('/').some(x=>['','..','.'].includes(x)))
      throw Error('文件路径无效 / Invalid file path');
    if (inputs.has(path)) throw Error('文件路径重复 / Duplicate file path: '+path);
    inputs.set(path,file);
    const name=path.split('/').at(-1), match=pattern.exec(name);
    if (!match) {ignored.push({path,reason:'unmatched'});continue;}
    const {project,kind,version,slot='main'}=match.groups;
    if (!recipe.projects.includes(project) || !rules.has(kind)) {ignored.push({path,reason:'outside_recipe'});continue;}
    const extension=name.slice(name.lastIndexOf('.')).toLowerCase();
    if (!rules.get(kind).extensions.map(x=>x.toLowerCase()).includes(extension)) {ignored.push({path,reason:'extension'});continue;}
    if (!/^[0-9]+$/.test(version) || !Number.isSafeInteger(Number(version))) throw Error('版本无效 / Invalid version: '+path);
    const bytes=new Uint8Array(await file.arrayBuffer());
    const record={path,sha256:await hash(bytes),bytes:bytes.length,version:Number(version),kind,slot:slot||'main'};
    const key=JSON.stringify([project,kind,record.slot]);
    if (!buckets.has(key)) buckets.set(key,[]);
    buckets.get(key).push(record);
  }
  const projects=[];
  for (const id of recipe.projects) {
    const selected=[],issues=[],discarded=[];
    for (const [key,candidates] of [...buckets].sort((a,b)=>a[0]<b[0]?-1:1)) {
      const [owner,kind,slot]=JSON.parse(key);if(owner!==id)continue;
      const latest=Math.max(...candidates.map(x=>x.version));
      const current=candidates.filter(x=>x.version===latest).sort(order);
      discarded.push(...candidates.filter(x=>x.version<latest));
      if (new Set(current.map(x=>x.sha256)).size>1) {issues.push({code:'conflict',kind,slot,paths:current.map(x=>x.path)});continue;}
      selected.push(current[0]);discarded.push(...current.slice(1));
    }
    for (const [kind,rule] of rules) {
      const count=selected.filter(x=>x.kind===kind).length;
      if(count<(rule.min_count??1))issues.push({code:'missing',kind,have:count,need:rule.min_count??1});
      if(count>(rule.max_count??1))issues.push({code:'excess',kind,have:count,limit:rule.max_count??1});
    }
    const destinations=selected.map(x=>(x.kind+'/'+x.path.split('/').at(-1)).toLowerCase());
    if(new Set(destinations).size!==destinations.length)issues.push({code:'destination_collision',kind:''});
    projects.push({id,ready:!issues.length,files:selected.sort(order),issues,discarded:discarded.sort(order)});
  }
  return {schema:1,recipe,projects,ignored:ignored.sort(order)};
}
export function inventory(project) {
  return {schema:1,project:project.id,files:project.files.map(x=>({member:x.kind+'/'+x.path.split('/').at(-1),sha256:x.sha256,bytes:x.bytes,source:x.path,version:x.version}))};
}
const crcTable=Uint32Array.from({length:256},(_,i)=>{let c=i;for(let j=0;j<8;j++)c=c&1?0xedb88320^(c>>>1):c>>>1;return c>>>0;});
function crc32(bytes){let c=0xffffffff;for(const b of bytes)c=crcTable[(c^b)&255]^(c>>>8);return (c^0xffffffff)>>>0;}
function join(arrays){const all=new Uint8Array(arrays.reduce((n,x)=>n+x.length,0));let offset=0;for(const x of arrays){all.set(x,offset);offset+=x.length;}return all;}
export function zipStore(entries) {
  if(entries.length>65535)throw Error('文件太多，请使用本机版 / Too many files; use the local tool');
  const local=[],central=[],names=new Set();let offset=0;
  for(const {name,bytes} of entries){
    if(names.has(name) || name.startsWith('/') || name.includes('\\') || name.includes(':') || name.split('/').some(x=>['','..','.'].includes(x)))throw Error('交付包路径无效 / Invalid package path');
    names.add(name);
    const filename=encoder.encode(name),size=bytes.length,crc=crc32(bytes);
    if(size>0xffffffff || offset+size>0xffffffff || filename.length>65535)throw Error('资料太大，请使用本机版 / Files too large; use the local tool');
    const head=new Uint8Array(30),h=new DataView(head.buffer);
    h.setUint32(0,0x04034b50,true);h.setUint16(4,20,true);h.setUint16(6,0x800,true);h.setUint16(12,20513,true);
    h.setUint32(14,crc,true);h.setUint32(18,size,true);h.setUint32(22,size,true);h.setUint16(26,filename.length,true);
    local.push(head,filename,bytes);
    const dir=new Uint8Array(46),d=new DataView(dir.buffer);
    d.setUint32(0,0x02014b50,true);d.setUint16(4,20,true);d.setUint16(6,20,true);d.setUint16(8,0x800,true);d.setUint16(14,20513,true);
    d.setUint32(16,crc,true);d.setUint32(20,size,true);d.setUint32(24,size,true);d.setUint16(28,filename.length,true);d.setUint32(42,offset,true);
    central.push(dir,filename);offset+=head.length+filename.length+size;
  }
  const end=new Uint8Array(22),e=new DataView(end.buffer),directory=join(central);
  e.setUint32(0,0x06054b50,true);e.setUint16(8,entries.length,true);e.setUint16(10,entries.length,true);e.setUint32(12,directory.length,true);e.setUint32(16,offset,true);
  return join([...local,directory,end]);
}
export function summary(report,lang='zh') {
  const ready=report.projects.filter(x=>x.ready).length;
  const lines=[lang==='en'?`Projects: ${report.projects.length}; ready: ${ready}; blocked: ${report.projects.length-ready}`:`项目：${report.projects.length}；资料齐全：${ready}；需要补齐或处理：${report.projects.length-ready}`];
  for(const project of report.projects){
    lines.push(project.id+(lang==='en'?(project.ready?': ready':': blocked'):(project.ready?'：资料齐全':'：未生成交付包')));
    for(const issue of project.issues)lines.push('  '+issue.kind+': '+(issue.code==='missing'?`${issue.have}/${issue.need}`:issue.code==='conflict'?(lang==='en'?'same version has different contents':'同版本存在不同内容'):issue.code==='excess'?(lang==='en'?'too many files':'文件数量超过要求'):(lang==='en'?'colliding names':'输出文件名重复')));
  }
  return lines.join('\n')+'\n';
}
export async function buildBundle(files,recipe,planned=null){
  const current=await planFiles(files,recipe);
  if(planned && JSON.stringify(current)!==JSON.stringify(planned))throw Error('资料已变化，请重新检查 / Files changed; review a new plan');
  const inputs=new Map(files.map(f=>[f.relativePath||f.webkitRelativePath||f.name,f])),entries=[];
  for(const project of current.projects){
    if(!project.ready)continue;
    const records=inventory(project),parts=[];
    for(let i=0;i<records.files.length;i++){
      const bytes=new Uint8Array(await inputs.get(project.files[i].path).arrayBuffer());
      if(await hash(bytes)!==records.files[i].sha256)throw Error('资料已变化 / Source changed');
      parts.push({name:records.files[i].member,bytes});
    }
    parts.push({name:'inventory.json',bytes:encoder.encode(JSON.stringify(records))});
    entries.push({name:project.id+'.zip',bytes:zipStore(parts)});
  }
  entries.push({name:'Report.json',bytes:encoder.encode(JSON.stringify(current,null,2))});
  for(const lang of ['zh','en'])entries.push({name:`Summary.${lang}.txt`,bytes:encoder.encode(summary(current,lang))});
  return {report:current,bytes:zipStore(entries)};
}
export function sampleFiles(){
  const files=[];
  function add(path,content){const f=new File([content],path.split('/').at(-1));Object.defineProperty(f,'relativePath',{value:path});files.push(f);}
  for(let i=0;i<3;i++){
    const project=SAMPLE_RECIPE.projects[i];
    const svg=`<svg xmlns="http://www.w3.org/2000/svg" width="320" height="200"><rect width="320" height="200" fill="#d8edf3"/><text x="30" y="100">Sample ${project}</text></svg>`;
    add(`${project}/${project}_design_main_v1.svg`,svg.replace('Sample','Old sample'));
    add(`${project}/${project}_design_main_v2.svg`,svg);
    for(const slot of ['front','back'])add(`${project}/${project}_image_${slot}_v1.svg`,svg.replace('Sample',slot));
    if(i!==1)add(`${project}/${project}_guide_main_v1.txt`,'模拟说明 / Sample guide\n'+project);
    if(i===2)add(`${project}/另一份/${project}_design_main_v2.svg`,svg.replace('Sample','Different sample'));
  }
  return files;
}
