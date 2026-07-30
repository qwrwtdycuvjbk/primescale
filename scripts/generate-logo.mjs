import path from "path";
import { fileURLToPath } from "url";
import sharp from "sharp";

const __dirname = path.dirname(fileURLToPath(import.meta.url));

function buildSvg(fill) {
  const font =
    'font-family="Arial, Helvetica, sans-serif" font-size="56" font-weight="700" letter-spacing="-1.8"';
  return `<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 420 200" fill="none">
  <text x="0" y="78" fill="${fill}" ${font}>People</text>
  <text x="0" y="155" fill="${fill}" ${font}>Remotely</text>
</svg>`;
}

const publicDir = path.join(__dirname, "..", "public");
await sharp(Buffer.from(buildSvg("#FFFFFF")))
  .png()
  .toFile(path.join(publicDir, "peopleremotely-logo.png"));
await sharp(Buffer.from(buildSvg("#00338D")))
  .png()
  .toFile(path.join(publicDir, "peopleremotely-logo-dark.png"));
console.log("Generated logo PNGs");
