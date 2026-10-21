// Build a small, reproducible static UI bundle. Historical JSON lives in
// the GitHub repository and is served through Vercel's /data/* rewrite.
// Never ship the multi-GB research archives in each Vercel deployment.
import {cp, copyFile, mkdir, readdir, rm} from 'node:fs/promises';
import {dirname, join, resolve, sep} from 'node:path';
import {fileURLToPath} from 'node:url';

const source = dirname(fileURLToPath(import.meta.url));
const destination = resolve(process.cwd(), 'dist');
if (destination === source || source.startsWith(destination + sep)) {
  throw new Error('Unsafe dist destination: would erase the source directory');
}
await rm(destination, {recursive: true, force: true});
await mkdir(destination, {recursive: true});

const uiExtension = /\.(?:html|js|css|webmanifest)$/;
const copied = [];
for (const item of await readdir(source, {withFileTypes: true})) {
  if (item.isDirectory() && item.name === 'icons') {
    await cp(join(source, 'icons'), join(destination, 'icons'), {recursive: true});
    copied.push('icons/');
  } else if (item.isFile() && uiExtension.test(item.name)) {
    await copyFile(join(source, item.name), join(destination, item.name));
    copied.push(item.name);
  }
}
if (!copied.includes('index.html') || !copied.includes('snapshot-loader.js') || !copied.includes('kell-dataset-loader.js')) {
  throw new Error('Incomplete static UI bundle');
}
console.log('Lightweight Vercel UI built: ' + copied.join(', '));
console.log('Excluded lab/data/ (JSON files served from the public GitHub source).');
