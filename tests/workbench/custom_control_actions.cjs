'use strict';
const assert = require('node:assert/strict');
async function select(field, selection) {
  const options = await field.locator('option').evaluateAll(nodes => nodes.map(n => ({value:n.value,label:n.label,disabled:n.disabled})));
  const wanted = options.find(option => typeof selection === 'string' ? option.value === selection : option.label === selection.label);
  assert(wanted && !wanted.disabled, 'Expected an enabled custom select option');
  await field.click();
  await field.page().locator('.wb-control-popup').getByRole('option',{name:wanted.label,exact:true}).click();
  await field.page().locator('.wb-control-popup').waitFor({state:'detached'});
  assert.equal(await field.inputValue(),wanted.value);
}
async function openPicker(field) {
  const box=await field.boundingBox();assert(box);
  await field.click({position:{x:box.width-16,y:box.height/2}});
  const popup=field.page().locator('.wb-control-popup');await popup.waitFor();return popup;
}
module.exports={select,openPicker};
