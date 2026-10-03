import { access, mkdir, readdir, unlink } from "node:fs/promises";
import path from "node:path";
import { pathToFileURL } from "node:url";

const modulePath = process.env.SHARP_MODULE;
if (!modulePath) throw new Error("Set SHARP_MODULE to the installed sharp entry point.");
const { default: sharp } = await import(pathToFileURL(modulePath).href);
const [work, dest] = process.argv.slice(2);
await mkdir(path.join(dest, "layers"), { recursive: true });
await mkdir(path.join(dest, "effects"), { recursive: true });
for (const name of ["day-master", "intro", "star"]) {
  await unlink(path.join(dest, "effects", `${name}.png.png`))
    .catch(error => { if (error.code !== "ENOENT") throw error; });
}
for (const file of await readdir(work)) {
  if (file.startsWith("layer-")) {
    await sharp(path.join(work, file), { density: 240 }).resize(1000, 1000)
      .png({ compressionLevel: 9 }).toFile(path.join(dest, "layers", file.slice(6).replace(".svg", ".png")));
  }
  if (file.startsWith("effect-")) {
    const name = file.slice(7).replace(".svg", "");
    const size = name === "intro" ? [804, 1748] : name === "star" ? [64, 64] : [240, 240];
    await sharp(path.join(work, file), { density: 240 }).resize(size[0], size[1])
      .png({ palette: true }).toFile(path.join(dest, "effects", `${name}.png`));
  }
}
await sharp(path.join(work, "wheel.svg"), { density: 240 })
  .resize(1000, 1000).png({ compressionLevel: 9 }).toFile(path.join(dest, "wheel.png"));
await sharp(path.join(work, "taiji.svg"), { density: 240 })
  .resize(160, 160).png().toFile(path.join(dest, "taiji.png"));
for (const name of ["needle", "wedge"]) {
  if (await access(path.join(work, `${name}.svg`)).then(() => true, () => false)) {
    await sharp(path.join(work, `${name}.svg`), { density: 240 })
      .resize(1000, 1000).png({ compressionLevel: 9 }).toFile(path.join(dest, `${name}.png`));
  }
}
const features = path.resolve(dest, "../features");
await mkdir(path.join(dest, "icons"), { recursive: true });
for (const file of await readdir(features)) {
  if (!file.endsWith(".png")) continue;
  const source = path.join(work, `icon-${path.basename(file, ".png")}.svg`);
  if (await access(source).then(() => true, () => false)) {
    await sharp(source, { density: 240 }).resize(160, 124)
      .png().toFile(path.join(dest, "icons", file));
  } else {
    await sharp(path.join(features, file)).grayscale().tint("#f0a886")
      .png().toFile(path.join(dest, "icons", file));
  }
}
console.log("Rendered source wheel, taiji and topic icons.");
