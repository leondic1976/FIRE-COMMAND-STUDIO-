import { readFile, mkdir, cp, writeFile } from 'node:fs/promises';
import { fileURLToPath } from 'node:url';
import path from 'node:path';

const root = path.dirname(fileURLToPath(import.meta.url));
const release = JSON.parse(await readFile(path.join(root, 'release.json'), 'utf8'));
const version = release.version;
if (release.status !== 'released' || !/^\d+\.\d+\.\d+$/.test(version) ||
    !/^[a-f0-9]{64}$/.test(release.sha256) || !Number.isSafeInteger(release.bytes) || release.bytes < 1000000 ||
    release.download_url !== `https://github.com/leondic1976/FIRE-COMMAND-STUDIO-/releases/download/v${version}/FIRE-Command-Studio-Setup-${version}-x64.exe` ||
    release.release_url !== `https://github.com/leondic1976/FIRE-COMMAND-STUDIO-/releases/tag/v${version}`) {
  throw new Error('A verified, published installer and checksum are required before building.');
}
if (version !== '0.1.0' && (!release.server ||
    release.server.download_url !== `https://github.com/leondic1976/FIRE-COMMAND-STUDIO-/releases/download/v${version}/FIRE-Command-Studio-Web-${version}.zip` ||
    !/^[a-f0-9]{64}$/.test(release.server.sha256) || !Number.isSafeInteger(release.server.bytes) || release.server.bytes < 100000)) {
  throw new Error('A verified server package and checksum are required for the dual-track release.');
}
const output = path.join(root, 'dist');
await mkdir(output, { recursive: true });
for (const name of ['index.html', 'style.css', 'app.js', 'release.json', 'assets']) {
  await cp(path.join(root, name), path.join(output, name), { recursive: true });
}
await writeFile(path.join(output, 'robots.txt'), 'User-agent: *\nAllow: /\n');
console.log(`Built download site for v${version}; installer SHA256 ${release.sha256}`);
