// Basic test for the telegram token generation endpoint.
// This uses Node's built‑in test runner (node --test) and the built‑in fetch API (available in Node 18+).
import assert from 'assert';

async function testGenerateToken() {
  const response = await fetch('http://localhost:3000/api/telegram-token/generate', {
    method: 'POST',
    headers: { 'x-telegram-init-data': 'user={"id":12345}' },
  });
  assert.equal(response.status, 200, 'Expected 200 OK');
  const data = await response.json();
  assert.ok(data.telegramToken, 'Response should contain telegramToken');
}

await testGenerateToken();
