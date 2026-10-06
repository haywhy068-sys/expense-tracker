import {test} from 'node:test';import assert from 'node:assert/strict';import {totalCents,csv} from '../src/money.mjs';
test('decimal sums stay accurate in cents',()=>assert.equal(totalCents([{amount:0.1},{amount:0.2},{amount:120.5}]),12080));
test('CSV preserves headers, decimals and Excel formula safety',()=>{const output=csv([{id:1,date:'2026-10-05',category:'Food',description:'=SUM(1,2) "test"',amount:120.5}]);assert.ok(output.startsWith('\uFEFF"id","date","category","description","amount"'));assert.ok(output.includes('"\'=SUM(1,2) ""test"""'));assert.ok(output.includes('"120.50"'));});
