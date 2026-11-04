'use strict';
const test=require('node:test'),assert=require('node:assert/strict'),fs=require('node:fs'),vm=require('node:vm');
const source=name=>fs.readFileSync(require.resolve('../'+name),'utf8');
test('candidate browser globals coexist with CommonJS without requiring a browser loader',()=>{
  const context={module:{exports:{}}};context.window=context;
  vm.runInNewContext(source('candidate-model.js'),context);
  const model=context.ShikuangCandidateModel;
  assert.equal(model,context.module.exports);assert.equal(model.LABELS.length,87);
  context.module={exports:{}};
  vm.runInNewContext(source('candidate-inference.js'),context);
  assert.equal(context.ShikuangCandidateInference,context.module.exports);
  assert.equal(typeof context.ShikuangCandidateInference.createClient,'function');
});
test('candidate browser exports use browser dependencies when a require function also exists',()=>{
  let requires=0;const context={module:{exports:{}},require(){requires++;throw Error('browser must not require');}};context.window=context;
  vm.runInNewContext(source('candidate-model.js'),context);const model=context.ShikuangCandidateModel;
  context.module={exports:{}};vm.runInNewContext(source('candidate-inference.js'),context);
  assert.equal(requires,0);assert.equal(context.ShikuangCandidateModel,model);
  assert.equal(context.ShikuangCandidateInference,context.module.exports);
});
test('candidate modules retain ordinary Node exports and standalone worker globals',()=>{
  const C=require('../candidate-model.js'),I=require('../candidate-inference.js');
  assert.equal(C.LABELS.length,87);assert.equal(typeof I.createClient,'function');
  const context={};vm.runInNewContext(source('candidate-model.js'),context);vm.runInNewContext(source('candidate-inference.js'),context);
  assert.equal(context.ShikuangCandidateModel.LABELS.length,87);
  assert.equal(typeof context.ShikuangCandidateInference.createClient,'function');
});
