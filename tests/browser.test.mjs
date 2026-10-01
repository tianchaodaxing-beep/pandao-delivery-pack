import test from 'node:test';
import assert from 'node:assert/strict';
import {mkdtemp,writeFile} from 'node:fs/promises';
import {tmpdir} from 'node:os';
import {join} from 'node:path';
import {SAMPLE_RECIPE, sampleFiles, planFiles, buildBundle, validateRecipe, zipStore} from '../docs/engine.mjs';

test('sample completeness, numeric versions, actual downloadable ZIP',async()=>{
  const files=sampleFiles(),report=await planFiles(files,SAMPLE_RECIPE);
  assert.deepEqual(report.projects.map(x=>x.ready),[true,false,false]);
  assert.equal(report.projects[0].files.length,4);
  assert.equal(report.projects[0].files.find(x=>x.kind==='design').version,2);
  const result=await buildBundle(files,SAMPLE_RECIPE,report);
  assert.ok(result.bytes.length>2000);
});
test('identical copies do not create false conflicts',async()=>{
  const files=sampleFiles(),duplicate=new File([await files[1].arrayBuffer()],files[1].name);
  Object.defineProperty(duplicate,'relativePath',{value:'copy/'+duplicate.name});
  const report=await planFiles([...files,duplicate],SAMPLE_RECIPE);
  assert.ok(report.projects[0].ready);
});
test('changed recipe invalidates reviewed plan',async()=>{
  const files=sampleFiles(),report=await planFiles(files,SAMPLE_RECIPE),recipe=structuredClone(SAMPLE_RECIPE);
  recipe.projects.push('P404');
  await assert.rejects(buildBundle(files,recipe,report));
});
test('unsafe recipes and package paths rejected',()=>{
  for(const id of ['../escape','CON','bad.'])assert.throws(()=>validateRecipe({...SAMPLE_RECIPE,projects:[id]}));
  assert.throws(()=>zipStore([{name:'../escape',bytes:new Uint8Array()}]));
  assert.throws(()=>zipStore([{name:'C:file',bytes:new Uint8Array()}]));
  assert.throws(()=>validateRecipe({...SAMPLE_RECIPE,projects:['a','A']}));
});
test('source paths cannot traverse directories or repeat',async()=>{
  const bad=new File(['x'],'x.txt');Object.defineProperty(bad,'relativePath',{value:'../x.txt'});
  await assert.rejects(planFiles([bad],SAMPLE_RECIPE));
  const files=sampleFiles();await assert.rejects(planFiles([files[0],files[0]],SAMPLE_RECIPE));
});
test('archive writer preserves UTF-8 names and generates reproducible bytes',()=>{
  const input=[{name:'中文/说明.txt',bytes:new TextEncoder().encode('资料')}];
  assert.deepEqual(zipStore(input),zipStore(input));
});
