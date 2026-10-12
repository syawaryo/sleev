import { createHash } from 'node:crypto';
import { readdir, readFile, writeFile } from 'node:fs/promises';

// Precache exactly this build, including both drawings and the lazy drawing UI.
const root = new URL('../dist/', import.meta.url);
async function files(dir, prefix = '') {
  const entries = await readdir(dir, { withFileTypes: true });
  const nested = await Promise.all(entries.map((entry) => entry.isDirectory()
    ? files(new URL(`${entry.name}/`, dir), `${prefix}${entry.name}/`)
    : [`${prefix}${entry.name}`]));
  return nested.flat().filter((name) => name !== 'sw.js').sort();
}
const paths = await files(root);
const hash = createHash('sha256');
for (const path of paths) hash.update(await readFile(new URL(path, root)));
const version = hash.digest('hex').slice(0, 16);
const worker = `
const CACHE = 'sleeve-demo-${version}';
const FILES = ${JSON.stringify(['./', ...paths.map((p) => './' + p)])};
self.addEventListener('install', (event) => {
  event.waitUntil(caches.open(CACHE).then((cache) => cache.addAll(FILES)));
});
self.addEventListener('activate', (event) => {
  event.waitUntil(caches.keys().then((keys) => Promise.all(keys
    .filter((key) => key.startsWith('sleeve-demo-') && key !== CACHE)
    .map((key) => caches.delete(key)))).then(() => self.clients.claim()));
});
self.addEventListener('fetch', (event) => {
  if (event.request.method !== 'GET' || new URL(event.request.url).origin !== self.location.origin) return;
  const path = new URL(event.request.url).pathname;
  if (path.includes('/api/')) return;
  event.respondWith(caches.open(CACHE).then(async (cache) => {
    const saved = await cache.match(event.request);
    if (saved) return saved;
    if (event.request.mode === 'navigate') return (await cache.match('./index.html')) || fetch(event.request);
    return fetch(event.request);
  }));
});
`;
await writeFile(new URL('sw.js', root), worker);
console.log(`Offline build ${version}: ${paths.length} files`);
