import {SAMPLE_RECIPE, sampleFiles, planFiles, buildBundle} from './engine.mjs';
const $=id=>document.getElementById(id);
const messages={zh:{brand:'交付包',source:'源码',local:'下载本机版',eyebrow:'把资料变成交付成果',headline:'几十个项目，<br>一次备齐交付包。',intro:'放入资料，按交付清单检查。齐全的项目直接打包，缺件和版本冲突单独列出。',sample:'用示例试一次 ↗',privacy:'文件在当前浏览器内处理，不上传。大批资料可使用本机版。',workspace:'组装工作区',empty:'还没有选择资料',step1:'1 选择资料',step2:'2 检查清单',step3:'3 下载交付包',files:'资料文件夹',chooseHint:'选择包含多个项目资料的文件夹',chooseFolder:'选择文件夹',chooseFiles:'或选择多个文件',naming:'示例文件名',recipe:'交付清单',recipeDownload:'下载清单',recipeHint:'示例要求：每个项目有一份设计文件、一份说明文件、两张配图。可修改项目编号、类别和数量。',recipeLabel:'清单内容',check:'检查资料',download:'下载交付包',results:'项目检查结果',usageTitle:'适合需要按项目交资料的工作',use1:'设计交付',use1text:'源文件、导出图、使用说明，按客户或项目分别组装。',use2:'工程与制造',use2text:'图纸、检验文件、配套资料，缺一项就列出来。',use3:'客户服务',use3text:'培训、说明和附件按清单备齐，再生成每个客户的交付包。',footer:'PANDAO · 交付包自动组装',directory:'查看其他工具 ↗',sampleMode:'示例资料',localMode:'已选择的资料',count:n=>`已选择 ${n} 个文件`,totals:(n,r)=>`${n} 个项目 · ${r} 个齐全 · ${n-r} 个需要处理`,ready:'资料齐全',blocked:'需要处理',selected:n=>`已选 ${n} 个文件`,discarded:n=>`跳过旧版本或相同副本 ${n} 个`,missing:x=>`${x.kind}：需要 ${x.need} 个，已有 ${x.have} 个`,conflict:x=>`${x.kind}：同版本存在不同内容，请保留正确文件`,excess:x=>`${x.kind}：${x.have} 个文件超过上限 ${x.limit}`,destination_collision:()=> '输出文件名重复，请调整文件名',ignored:n=>`${n} 个文件未匹配清单`,checking:'正在检查资料…',finished:'检查完成。齐全的项目可以下载交付包。',noFiles:'请先选择资料或载入示例。',building:'正在生成交付包…',downloaded:'交付包已生成，请查看下载文件。',limit:'网页适合不超过 250 MB 的资料。更大的文件夹请使用本机版。'},en:{brand:'Delivery pack',source:'Source',local:'Download local tool',eyebrow:'FROM FILES TO HANDOVER',headline:'Dozens of projects.<br>One packaging run.',intro:'Choose your files and a delivery recipe. Complete projects become packages. Missing files and version conflicts stay visible.',sample:'Try sample files ↗',privacy:'Files stay in this browser. Nothing is uploaded. Use the local tool for large batches.',workspace:'Assembly workspace',empty:'No files selected',step1:'1 Choose files',step2:'2 Check recipe',step3:'3 Download packages',files:'Source folder',chooseHint:'Choose a folder containing files for several projects',chooseFolder:'Choose folder',chooseFiles:'Or choose multiple files',naming:'Example filename',recipe:'Delivery recipe',recipeDownload:'Download recipe',recipeHint:'The sample needs one design, one guide and two images per project. Edit the project IDs, item types and quantities.',recipeLabel:'Recipe contents',check:'Check files',download:'Download packages',results:'Project results',usageTitle:'For work that delivers files by project',use1:'Design handover',use1text:'Assemble source files, exported images and instructions for each client or project.',use2:'Engineering & manufacturing',use2text:'Collect drawings, inspection records and supporting files. See what is missing.',use3:'Client services',use3text:'Gather training materials, guides and attachments into a package for each client.',footer:'PANDAO · Delivery pack',directory:'More tools ↗',sampleMode:'Sample files',localMode:'Selected files',count:n=>`${n} files selected`,totals:(n,r)=>`${n} projects · ${r} ready · ${n-r} need attention`,ready:'Ready',blocked:'Needs attention',selected:n=>`${n} files selected`,discarded:n=>`${n} old versions or identical copies skipped`,missing:x=>`${x.kind}: ${x.have} of ${x.need} required`,conflict:x=>`${x.kind}: same version has different contents; keep the correct file`,excess:x=>`${x.kind}: ${x.have} files exceeds the limit of ${x.limit}`,destination_collision:()=> 'Output names collide; rename the files',ignored:n=>`${n} files did not match the recipe`,checking:'Checking files…',finished:'Check complete. Ready projects can be downloaded.',noFiles:'Choose files or load the sample first.',building:'Building packages…',downloaded:'Packages are ready. Check your downloaded file.',limit:'Use up to 250 MB in the browser. For larger folders, use the local tool.'}};
let lang=new URLSearchParams(location.search).get('lang')==='en'?'en':'zh';
let files=[],report=null,sampleMode=false,busy=false,lastStatus='';
const t=()=>messages[lang];
function translate(){
  document.documentElement.lang=lang==='zh'?'zh-CN':'en';document.title=lang==='zh'?'交付包自动组装 · PANDAO':'Delivery pack · PANDAO';
  document.querySelectorAll('[data-t]').forEach(el=>{const key=el.dataset.t;if(key==='headline')el.innerHTML=t()[key];else if(typeof t()[key]==='string')el.textContent=t()[key];});
  $('language').textContent=lang==='zh'?'English':'中文';$('language').setAttribute('aria-label',lang==='zh'?'切换到英文':'Switch to Chinese');
  $('folder').setAttribute('aria-label',t().chooseFolder);$('files').setAttribute('aria-label',t().chooseFiles);
  if(files.length)$('mode').textContent=sampleMode?t().sampleMode:t().localMode;
  $('fileCount').textContent=files.length?t().count(files.length):'';
  if(lastStatus)status(lastStatus,$('status').className==='error');
  if(report)render();
}
function status(key,error=false){lastStatus=key;const raw=t()[key]||key;$('status').textContent=error&&raw.includes(' / ')?raw.split(' / ')[lang==='en'?1:0]:raw;$('status').className=error?'error':'';}
function invalidate(){report=null;$('results').hidden=true;$('download').disabled=true;lastStatus='';$('status').textContent='';}
function setFiles(next,isSample=false){
  if(next.reduce((n,x)=>n+x.size,0)>250*1024*1024){files=[];invalidate();$('fileList').replaceChildren();translate();status('limit',true);return;}
  files=next;sampleMode=isSample;invalidate();$('fileList').replaceChildren();
  for(const file of files.slice(0,25)){const li=document.createElement('li');li.textContent=file.relativePath||file.webkitRelativePath||file.name;$('fileList').append(li);}
  translate();
}
function render(){
  $('results').hidden=false;$('totals').textContent=t().totals(report.projects.length,report.projects.filter(x=>x.ready).length);$('projectList').replaceChildren();
  for(const project of report.projects){
    const row=document.createElement('div');row.className='project';
    const id=document.createElement('strong');id.textContent=project.id;
    const badge=document.createElement('span');badge.className='badge'+(project.ready?' ready':'');badge.textContent=project.ready?t().ready:t().blocked;
    const detail=document.createElement('div');detail.className='project-detail';
    const selected=document.createElement('p');selected.textContent=t().selected(project.files.length);detail.append(selected);
    for(const issue of project.issues){const p=document.createElement('p');const label=report.recipe.items.find(x=>x.kind===issue.kind)?.label;const kind=typeof label==='string'?label:label?.[lang]||issue.kind;p.textContent=t()[issue.code]({...issue,kind});detail.append(p);if(issue.paths){const s=document.createElement('small');s.textContent=issue.paths.join(' · ');detail.append(s);}}
    if(project.ready){const chosen=document.createElement('small');chosen.textContent=project.files.map(x=>x.path.split('/').at(-1)).join(' · ');detail.append(chosen);}
    const skipped=document.createElement('small');skipped.textContent=t().discarded(project.discarded.length);detail.append(skipped);row.append(id,badge,detail);$('projectList').append(row);
  }
  $('ignored').textContent=t().ignored(report.ignored.length);$('download').disabled=busy||!report.projects.some(x=>x.ready);
}
function download(bytes,name,type='application/zip'){const url=URL.createObjectURL(new Blob([bytes],{type}));const a=document.createElement('a');a.href=url;a.download=name;document.body.append(a);a.click();a.remove();setTimeout(()=>URL.revokeObjectURL(url),10000);}
function controls(value){busy=value;for(const id of ['check','sample','folderButton','filesButton'])$(id).disabled=value;$('recipe').disabled=value;$('download').disabled=value||!report?.projects.some(x=>x.ready);}
$('language').addEventListener('click',()=>{lang=lang==='zh'?'en':'zh';history.replaceState({},'', '?lang='+lang);translate();});
$('recipe').value=JSON.stringify(SAMPLE_RECIPE,null,2);$('recipe').addEventListener('input',invalidate);
$('sample').addEventListener('click',()=>{$('recipe').value=JSON.stringify(SAMPLE_RECIPE,null,2);setFiles(sampleFiles(),true);$('check').click();});
$('folderButton').addEventListener('click',()=>$('folder').click());$('filesButton').addEventListener('click',()=>$('files').click());
$('folder').addEventListener('change',()=>{const selected=[...$('folder').files];for(const f of selected)Object.defineProperty(f,'relativePath',{value:f.webkitRelativePath.split('/').slice(1).join('/')});setFiles(selected);});
$('files').addEventListener('change',()=>setFiles([...$('files').files]));
$('recipeDownload').addEventListener('click',()=>download($('recipe').value,'delivery-recipe.json','application/json'));
$('check').addEventListener('click',async()=>{
  if(!files.length){status('noFiles',true);return;}
  invalidate();controls(true);status('checking');
  try{report=await planFiles(files,JSON.parse($('recipe').value));render();status('finished');}
  catch(error){status(error.message,true);}finally{controls(false);}
});
$('download').addEventListener('click',async()=>{
  controls(true);status('building');
  try{const result=await buildBundle(files,JSON.parse($('recipe').value),report);download(result.bytes,'pandao-delivery-result.zip');status('downloaded');}
  catch(error){invalidate();status(error.message,true);}finally{controls(false);}
});
translate();
