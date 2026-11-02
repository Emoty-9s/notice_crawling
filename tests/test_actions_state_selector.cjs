// Optional offline check: node --test tests/test_actions_state_selector.cjs
// Uses only Node built-ins; executes the actual workflow script with fake APIs.
const {test} = require('node:test');
const assert = require('node:assert/strict');
const {readFileSync} = require('node:fs');
const {resolve} = require('node:path');

const workflow = JSON.parse(readFileSync(resolve(__dirname, '../.github/workflows/central-notice-pages.yml'), 'utf8'));
const script = workflow.jobs.build.steps.find(step => step.id === 'state').with.script;
const AsyncFunction = Object.getPrototypeOf(async function () {}).constructor;
const select = new AsyncFunction('github', 'context', 'core', 'process', script);

function artifact(id, overrides = {}) {
  return {id, expired: false, workflow_run: {id: id + 100, head_branch: 'main', head_repository_id: 42}, ...overrides};
}

async function run(artifacts, bootstrap = false) {
  const outputs = {};
  const warnings = [];
  const listArtifactsForRepo = () => {throw new Error('pagination must be used');};
  await select({rest: {actions: {listArtifactsForRepo}}, paginate: async (endpoint, options) => {
    assert.equal(endpoint, listArtifactsForRepo);
    assert.equal(options.name, 'central-state-v1');
    assert.equal(options.per_page, 100);
    assert.equal(options.owner, 'example');
    return artifacts;
  }}, {repo: {owner: 'example', repo: 'notices'}, payload: {repository: {id: 42, default_branch: 'main'}}},
  {setOutput: (key, value) => {outputs[key] = value;}, warning: value => warnings.push(value), info() {}},
  {env: {ALLOW_BOOTSTRAP: String(bootstrap)}});
  return {outputs, warnings};
}

test('missing state fails without explicit bootstrap', async () => {
  await assert.rejects(run([]), /STATE_MISSING/);
});

test('first explicit bootstrap starts empty and warns', async () => {
  const result = await run([], true);
  assert.deepEqual(result.outputs, {});
  assert.equal(result.warnings.length, 1);
});

test('latest ID selected regardless of API order', async () => {
  const result = await run([artifact(5), artifact(9), artifact(2)]);
  assert.deepEqual(result.outputs, {artifact_id: '9', run_id: '109'});
});

test('other branch/repository and missing provenance ignored', async () => {
  const result = await run([artifact(3), artifact(10, {workflow_run: {id: 110, head_branch: 'feature', head_repository_id: 42}}),
    artifact(11, {workflow_run: {id: 111, head_branch: 'main', head_repository_id: 99}}), artifact(12, {workflow_run: null})]);
  assert.equal(result.outputs.artifact_id, '3');
});

test('expired latest state never silently falls back or bootstraps', async () => {
  for (const bootstrap of [false, true]) {
    await assert.rejects(run([artifact(2), artifact(9, {expired: true})], bootstrap), /STATE_EXPIRED/);
  }
});

test('bootstrap still restores existing valid state', async () => {
  const result = await run([artifact(7)], true);
  assert.equal(result.outputs.artifact_id, '7');
  assert.equal(result.warnings.length, 0);
});
