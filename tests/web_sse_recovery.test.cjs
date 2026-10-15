// Exercise the shipped UI handlers with network/DOM ports replaced, without a browser build.
const { readFileSync } = require('node:fs');
const vm = require('node:vm');
const assert = require('node:assert/strict');
const { test } = require('node:test');
const source = readFileSync('src/adapters/web/static/app.js', 'utf8');

function handler(name) {
  const start = source.search(new RegExp(`(?:async )?function ${name}\\(`));
  assert.ok(start >= 0);
  const tail = source.slice(start);
  const next = tail.slice(1).search(/\n(?:(?:async )?function |\/\/ ---)/);
  return next < 0 ? tail : tail.slice(0, next + 1);
}

function harness() {
  const messages = [];
  const state = {
    threadId: 'thread', waiting: true, pendingMessageId: 'new-request',
    seenReplies: new Set(), steps: [], streamReady: false,
  };
  const context = {
    state, messages,
    el: {
      send: {}, draft: { value: '' },
      trace: { classList: { add() {} } }, traceHead: { setAttribute() {} },
    },
    api: { messages: async () => [], send: async () => ({ messageId: 'new-request' }) },
    appendMessage: (text, fromBot) => messages.push({ text, fromBot }),
    setWaiting: value => { state.waiting = value; },
    renderMessages: values => { messages.splice(0, messages.length, ...values); },
    renderSteps() {}, collapseTrace() {}, refreshThreads() {}, showError() {}, autoGrow() {},
  };
  vm.createContext(context);
  for (const name of ['handleEvent', 'recoverPendingReply', 'submit']) {
    vm.runInContext(handler(name), context);
  }
  return context;
}

test('cached/live overlap displays a final once and completes the matching request', () => {
  const ctx = harness();
  const event = { type: 'final', text: 'public answer', reply_to: 'new-request' };
  ctx.handleEvent(event);
  ctx.handleEvent(event);
  assert.equal(ctx.messages.length, 1);
  assert.equal(ctx.state.waiting, false);
});

test('an older replay cannot finish a newer pending request', () => {
  const ctx = harness();
  ctx.handleEvent({ type: 'final', text: 'old', reply_to: 'old-request' });
  assert.equal(ctx.state.waiting, true);
  assert.equal(ctx.state.pendingMessageId, 'new-request');
});

test('POST acknowledgement can follow the matching final', async () => {
  const ctx = harness();
  ctx.state.waiting = false;
  ctx.state.pendingMessageId = null;
  ctx.state.streamReady = true;
  ctx.api.send = async () => {
    ctx.handleEvent({ type: 'final', text: 'fast answer', reply_to: 'new-request' });
    return { messageId: 'new-request' };
  };
  await ctx.submit('question');
  assert.equal(ctx.state.waiting, false);
  assert.equal(ctx.state.pendingMessageId, null);
  assert.equal(ctx.messages.length, 2);
});

test('composer rejects requests before replay/ready handshake', async () => {
  const ctx = harness();
  ctx.state.waiting = false;
  let calls = 0;
  ctx.api.send = async () => { calls++; };
  await ctx.submit('question');
  assert.equal(calls, 0);
});

test('a final older than cache TTL is recovered from persisted history', async () => {
  const ctx = harness();
  ctx.api.messages = async () => [{ fromBot: true, replyTo: 'new-request', text: 'persisted' }];
  await ctx.recoverPendingReply();
  assert.equal(ctx.state.waiting, false);
  assert.equal(ctx.messages[0].text, 'persisted');
});

test('a delayed history response cannot overwrite another selected thread', async () => {
  const ctx = harness();
  ctx.api.messages = async () => {
    ctx.state.threadId = 'other-thread';
    return [{ fromBot: true, replyTo: 'new-request', text: 'stale' }];
  };
  await ctx.recoverPendingReply();
  assert.equal(ctx.messages.length, 0);
});
