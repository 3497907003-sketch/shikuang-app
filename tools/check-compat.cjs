'use strict';
const fs=require('node:fs'),path=require('node:path');
const {assertSyntax}=require('./compat-js.cjs');
const dist=path.resolve(__dirname,'../dist');
if(!fs.existsSync(dist))throw Error('Build dist before checking emitted compatibility');
const pending=[dist],names=[];
while(pending.length){const directory=pending.pop();for(const entry of fs.readdirSync(directory,{withFileTypes:true})){const filename=path.join(directory,entry.name);if(entry.isDirectory())pending.push(filename);else if(/\.(?:js|mjs)$/.test(entry.name))names.push(filename);}}
if(!names.length)throw Error('No emitted scripts to check');
for(const filename of names.sort())assertSyntax(path.relative(dist,filename),fs.readFileSync(filename,'utf8'));
console.log(`Checked ${names.length} emitted JS/MJS scripts with pinned parser and Chrome69 syntax exclusions. This is a static gate; platform APIs and WASM still require runtime tests.`);
