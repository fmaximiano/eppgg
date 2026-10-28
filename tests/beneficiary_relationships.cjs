// Run with node tests/beneficiary_relationships.cjs.
const fs = require('node:fs');
const vm = require('node:vm');
const assert = require('node:assert/strict');
const source = fs.readFileSync('app/static/app.js', 'utf8');
let rows = [];
const context = {
  $$: () => rows,
  $: (_, row) => ({ value: row.relationship }),
};
vm.createContext(context);
vm.runInContext(
  source.slice(source.indexOf('function compatibleBeneficiaryRelationships'), source.indexOf('function beneficiaryRow')),
  context,
);
const choices = (except) => Array.from(context.compatibleBeneficiaryRelationships(except));
const all = ['child', 'spouse', 'parent', 'sibling'];
assert.deepEqual(choices(), all);
rows = [{ relationship: '' }];
assert.deepEqual(choices(), all);
for (const [relationship, expected] of [
  ['parent', ['parent']], ['sibling', ['sibling']],
  ['child', ['spouse']], ['spouse', ['child']],
]) {
  rows = [{ relationship }];
  assert.deepEqual(choices(), expected);
  assert.deepEqual(choices(rows[0]), all);
}
for (const relationships of [['parent', 'parent'], ['spouse', 'child']]) {
  rows = relationships.map((relationship) => ({ relationship }));
  assert.deepEqual(choices(), []);
  rows.pop();
  assert.ok(choices().length);
}
rows = Array.from({ length: 3 }, () => ({ relationship: 'sibling' }));
assert.deepEqual(choices(), ['sibling']);
rows.push({ relationship: 'child' });
assert.deepEqual(choices(), []);
console.log('PASS: opções iniciais, grupos, limites, edição e remoção');
