import {test} from 'node:test';import assert from 'node:assert/strict';import fs from 'node:fs/promises';import ts from 'typescript';
test('mock auth and expense CRUD operate in memory with category/date filters',async()=>{
 const source=await fs.readFile(new URL('../src/mock.ts',import.meta.url),'utf8');const code=ts.transpileModule(source,{compilerOptions:{target:ts.ScriptTarget.ES2022,module:ts.ModuleKind.ESNext}}).outputText;const {mockRequest}=await import('data:text/javascript;base64,'+Buffer.from(code).toString('base64'));const h={'Authorization':'Bearer mock-session-only'};
 const auth=await mockRequest('/api/auth/login',{method:'POST',body:JSON.stringify({email:'demo@example.com',password:'sample-only'})});assert.equal(auth.user.email,'demo@example.com');
 await assert.rejects(()=>mockRequest('/api/expenses'),/sample dashboard/);
 let rows=await mockRequest('/api/expenses',{headers:h});assert.equal(rows.length,6);const month=rows[0].date.slice(0,7);
 const food=await mockRequest(`/api/expenses?category=Food&start_date=${month}-01&end_date=${month}-05`,{headers:h});assert.equal(food.length,2);assert.equal(food.reduce((s,e)=>s+e.amount,0),18550);
 const payload={date:month+'-05',category:'Food',description:'Test coffee',amount:2500};const e=await mockRequest('/api/expenses',{headers:h,method:'POST',body:JSON.stringify(payload)});assert.equal(e.id,7);
 await mockRequest('/api/expenses/7',{headers:h,method:'PUT',body:JSON.stringify({...payload,amount:3000})});rows=await mockRequest('/api/expenses',{headers:h});assert.equal(rows.find(e=>e.id===7).amount,3000);rows[0].description='Mutated client copy';assert.notEqual((await mockRequest('/api/expenses',{headers:h}))[0].description,'Mutated client copy');
 await mockRequest('/api/expenses/7',{headers:h,method:'DELETE'});assert.equal((await mockRequest('/api/expenses',{headers:h})).length,6);
});
