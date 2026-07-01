import path from "path";
import { fileURLToPath } from "url";
import sharp from "sharp";

const __dirname = path.dirname(fileURLToPath(import.meta.url));

function buildSvg(fill) {
  const font =
    'font-family="Arial, Helvetica, sans-serif" font-size="72" font-weight="700" letter-spacing="-2.2"';
  return `<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 377 218" fill="none">
  <rect x="218" y="14" width="17" height="164" rx="2" fill="${fill}"/>
  <text x="0" y="92" fill="${fill}" ${font}>Prime</text>
  <text x="49" y="195" fill="${fill}" ${font}>Sca</text>
  <text x="242" y="195" fill="${fill}" ${font}>e</text>
</svg>`;
}

const publicDir = path.join(__dirname, "..", "public");
await sharp(Buffer.from(buildSvg("#FFFFFF")))
  .png()
  .toFile(path.join(publicDir, "primescale-logo.png"));
await sharp(Buffer.from(buildSvg("#00338D")))
  .png()
  .toFile(path.join(publicDir, "primescale-logo-dark.png"));
console.log("Generated logo PNGs");
